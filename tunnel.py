"""
V37.1 — Tunnel commercial unifié CEE Engine.

Orchestrateur du parcours unique du lead au paiement, mesurable bout-à-bout.

6 macro-stages alignés sur la méthodo Jimmy (R0→R4 + Maestro 10 commandements) :
    1. lead          — SIRET capturé, pas encore qualifié
    2. audit         — cumac estimé, fiches éligibles, prime calculée
    3. r1            — 1er rendez-vous (qualification + cadrage SPIN)
    4. r2            — 2e rendez-vous (closing Maestro)
    5. signature     — mandat signé (= mandat_signe de post_signature)
    6. post_signature — délègue au module post_signature (8 sous-étapes : travaux, COFRAC, PNCEE, paiement)

Persistance : tunnel_data/<tunnel_id>.json
Index : tunnel_data/_index.json (pour /tunnel GET liste)

Endpoints exposés par register_tunnel_routes(app) :
    POST   /tunnel                   — crée un tunnel (siret, vendor, source)
    GET    /tunnel/<id>              — état complet
    POST   /tunnel/<id>/advance      — avance au stage suivant (ou spécifié) avec data
    GET    /tunnel                   — liste tous (filtres : stage, vendor)
    GET    /analytics/sales-velocity — KPI dashboard (signatures/mois/vendor + objectif V38 +2)
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import jsonify, request

# Path déjà importé via import standard





TUNNEL_STAGES = ["lead", "audit", "r1", "r2", "signature", "post_signature"]


# V37.1 P2 — Persistance Fly volume (même mécanique que dossiers/conformite/post_signature).
def _resolve_data_dir(subdir: str) -> Path:
    base = os.environ.get("CEE_DATA_DIR")
    target = Path(base) / subdir if base else Path(__file__).parent / subdir
    target.mkdir(parents=True, exist_ok=True)
    return target


TUNNEL_DIR = _resolve_data_dir("tunnel_data")
INDEX_FILE = TUNNEL_DIR / "_index.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _new_id() -> str:
    return "T-" + uuid.uuid4().hex[:12]


def _path(tunnel_id: str) -> Path:
    return TUNNEL_DIR / f"{tunnel_id}.json"


def _load(tunnel_id: str) -> dict | None:
    p = _path(tunnel_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _save(t: dict) -> None:
    _path(t["tunnel_id"]).write_text(json.dumps(t, ensure_ascii=False, indent=2))
    _refresh_index()


def _refresh_index() -> None:
    """Index léger pour la liste — pas de re-load de chaque tunnel à chaque /tunnel GET.
    V37.3.3 : ajout raison_sociale + source + monday_item_id pour /tunnel & /tunnel/alerts."""
    idx = []
    for f in TUNNEL_DIR.glob("T-*.json"):
        try:
            t = json.loads(f.read_text())
            idx.append({
                "tunnel_id": t["tunnel_id"],
                "siret": t.get("siret"),
                "raison_sociale": t.get("raison_sociale"),
                "current_stage": t.get("current_stage"),
                "vendor": t.get("vendor"),
                "source": t.get("source"),
                "created_at": t.get("created_at"),
                "updated_at": t.get("updated_at"),
                "monday_item_id": t.get("monday_item_id"),
            })
        except Exception:
            continue
    INDEX_FILE.write_text(json.dumps(idx, ensure_ascii=False, indent=2))


def create_tunnel(siret: str, vendor: str = "", source: str = "manual",
                  raison_sociale: str = "") -> dict:
    """Crée un tunnel à l'étape 'lead'."""
    if not siret or len(siret) < 9:
        raise ValueError("SIRET requis (>= 9 chars)")
    tunnel_id = _new_id()
    now = _now()
    t = {
        "tunnel_id": tunnel_id,
        "siret": siret.replace(" ", "").strip(),
        "raison_sociale": raison_sociale,
        "vendor": vendor,
        "source": source,
        "current_stage": "lead",
        "created_at": now,
        "updated_at": now,
        "history": [{"stage": "lead", "ts": now, "data": {}}],
        "kpi": {},  # rempli au fur et à mesure des advance
    }
    _save(t)
    return t


def _preflight_signature(t: dict, data: dict) -> tuple[bool, list[str]]:
    """V37.3 — Pré-validation bloquante avant advance vers 'signature'.
    Vérifie la conformité juridique P6 (46 règles) + non-cumul + RGE.
    Retourne (ok, blockers). En mode strict (CEE_TUNNEL_STRICT=1), bloque si !ok.
    Sinon log seulement.
    """
    blockers = []
    # 1. Conformité 46 règles P6
    try:
        from conformite import executer_controles
        dossier = {
            "siret": t.get("siret", ""),
            "raison_sociale": t.get("raison_sociale", ""),
            "adresse": data.get("adresse", ""),
            "fiches": data.get("fiches") or [],
            "surface": data.get("surface", 0),
            "rge_installateur": data.get("rge_installateur", False),
            "rge_qualifications": data.get("rge_qualifications") or [],
            "rge_date_validite": data.get("rge_date_validite"),
            "date_engagement": data.get("date_engagement", ""),
            "date_signature": data.get("date_signature", ""),
        }
        rapport = executer_controles(dossier)
        if rapport.get("nb_bloquants", 0) > 0:
            for r in rapport.get("resultats", []):
                if r.get("statut") == "bloquant":
                    blockers.append(f"P6 {r.get('id')}: {r.get('description')}")
    except Exception:
        pass  # ne pas bloquer si conformite plante

    # 2. PNCEE score < 65 = STOP
    pncee = (t.get("checks", {}) or {}).get("pncee", {})
    if pncee.get("verdict") == "STOP":
        for b in pncee.get("blockers") or []:
            blockers.append(f"PNCEE: {b}")

    return (len(blockers) == 0), blockers


def advance_tunnel(tunnel_id: str, target_stage: str | None = None,
                   data: dict | None = None) -> dict | None:
    """Avance le tunnel au stage suivant (ou spécifié) avec data attachée.

    target_stage = None → stage suivant dans TUNNEL_STAGES
    target_stage = "r2" → saute directement (cas où R1 sauté, etc.)

    V37.2 hooks automatiques (sources tracées dans tunnel.kpi/data) :
    - entrée 'audit'        → pncee.score_dossier auto si fiches/siret présents
    - entrée 'signature'    → post_signature.init auto + dates cibles calculées
    - chaque advance        → push Monday best-effort si MONDAY_API_TOKEN set
    """
    t = _load(tunnel_id)
    if not t:
        return None
    current_idx = TUNNEL_STAGES.index(t["current_stage"])
    if target_stage:
        if target_stage not in TUNNEL_STAGES:
            raise ValueError(f"stage inconnu : {target_stage}")
        new_stage = target_stage
    else:
        if current_idx == len(TUNNEL_STAGES) - 1:
            return t  # déjà au bout
        new_stage = TUNNEL_STAGES[current_idx + 1]

    # V37.3 — Pré-validation conformité bloquante avant signature en mode strict
    if new_stage == "signature" and os.environ.get("CEE_TUNNEL_STRICT") == "1":
        ok, blockers = _preflight_signature(t, data or {})
        if not ok:
            raise PermissionError("STRICT_BLOCKED:" + "|".join(blockers[:3]))

    now = _now()
    t["current_stage"] = new_stage
    t["updated_at"] = now
    entry = {"stage": new_stage, "ts": now, "data": data or {}}
    t["history"].append(entry)

    # KPI : durée entre stages successifs (en heures)
    if len(t["history"]) >= 2:
        prev = t["history"][-2]
        try:
            d_prev = datetime.fromisoformat(prev["ts"].replace("Z", "")).timestamp()
            d_now = datetime.fromisoformat(now.replace("Z", "")).timestamp()
            t["kpi"][f"duree_{prev['stage']}_to_{new_stage}_h"] = round((d_now - d_prev) / 3600, 2)
        except Exception:
            pass

    # V37.2 hooks — best-effort, jamais bloquants (cf. self_pillars : vérité, pas de fake)
    _fire_stage_hooks(t, new_stage, entry)

    _save(t)
    return t


def _fire_stage_hooks(t: dict, new_stage: str, entry: dict) -> None:
    """Exécute les hooks métier à l'entrée d'un stage. Best-effort : log les
    erreurs dans entry['hooks'] mais ne casse jamais l'advance.

    V37.3 — Hooks complets :
    - audit       : score PNCEE + prime exacte (moteur_cee_master) + cross-sell PV + sources
    - r2          : délégataire optimal (comparer_acheteurs)
    - signature   : post_signature.init + push Monday (déjà présents)
    Sources tracées dans entry['hooks'] avec format 'ok via <module>:<fn>'.
    """
    hooks_log: dict[str, str] = {}

    # Hook audit → score PNCEE auto si data métier disponible
    if new_stage == "audit":
        d = entry.get("data") or {}
        try:
            from pncee import score_dossier
            payload = {
                "siret": t.get("siret", ""),
                "fiches": d.get("fiches") or [],
                "surface": d.get("surface", 0),
                "departement": d.get("departement", ""),
                "rge_installateur": d.get("rge_installateur", False),
                "date_engagement": d.get("date_engagement", ""),
            }
            if payload["fiches"]:
                score = score_dossier(payload)
                t.setdefault("checks", {})["pncee"] = {
                    "score": score.get("score"),
                    "verdict": score.get("verdict"),
                    "blockers_count": len(score.get("blockers") or []),
                    "blockers": score.get("blockers", [])[:5],  # top 5 pour traçabilité
                    "warnings": score.get("warnings", [])[:5],
                    "source": "pncee.score_dossier",
                    "ts": _now(),
                }
                hooks_log["pncee_score"] = f"ok verdict={score.get('verdict')} score={score.get('score')}"
        except Exception as e:
            hooks_log["pncee_score"] = f"err: {type(e).__name__}: {e}"

        # V37.3 — Calcul prime exacte (moteur expert) + cross-sell PV intelligent
        # V37.3.2 fix : adapter au vrai schéma de retour {results, pack, total_prime, summary}
        try:
            from auto_detect import moteur_expert_v2
            naf = d.get("naf") or d.get("ape", "")
            surface = float(d.get("surface", 0) or 0)
            dpt = d.get("departement", "") or ""
            if naf and surface > 0 and dpt:
                m = moteur_expert_v2(entreprise={"naf": naf}, surface=surface, energie=d.get("energie"), departement=dpt)
                if isinstance(m, dict):
                    pack = m.get("pack") or []
                    total_prime = float(m.get("total_prime") or 0)
                    cumac_total = sum(int(p.get("cumac") or 0) for p in pack)
                    top_fiches = [{"ref": p.get("fiche"), "prime": p.get("prime"), "cumac": p.get("cumac"),
                                   "score": p.get("score"), "pitch": p.get("pitch", "")[:140]}
                                  for p in pack[:5]]
                    t.setdefault("checks", {})["prime"] = {
                        "prime_brute_eur": int(total_prime),
                        "cumac_total": cumac_total,
                        "nb_fiches": len(pack),
                        "top_fiches": top_fiches,
                        "summary": (m.get("summary") or "")[:200],
                        "source": "auto_detect.moteur_expert_v2",
                        "ts": _now(),
                    }
                    hooks_log["prime_exacte"] = f"ok prime_brute={int(total_prime)}€ cumac={cumac_total} fiches={len(pack)}"
                else:
                    hooks_log["prime_exacte"] = "skip retour non-dict"
        except Exception as e:
            hooks_log["prime_exacte"] = f"err: {type(e).__name__}: {str(e)[:80]}"

        # Cross-sell PV : tertiaire + surface > 100 m² → suggérer audit PV
        # V37.3.11 — préfixes NAF tertiaire élargis (55=hébergement, 56=restauration,
        # 47=commerce détail, 70=bureau, 85=enseignement, 86=santé, 87=social,
        # 90=arts/spectacle, 91=biblio/musée, 93=sport, 96=services personnels)
        try:
            secteur = (d.get("secteur") or "").upper()
            surface = float(d.get("surface", 0) or 0)
            naf = (d.get("naf") or "").replace(".", "")[:2]
            naf_tertiaire = naf in {"47","55","56","68","70","85","86","87","88","90","91","93","94","96"}
            tertiaire = secteur in ("BAT", "TRA", "BAR") or naf_tertiaire
            if tertiaire and surface > 100 and not t.get("suggestions", {}).get("pv"):
                # Estimation rapide : 1 kWc / 6 m² toiture, plafond raisonnable
                kwc_estime = round(min(surface / 6, 250), 1)
                t.setdefault("suggestions", {})["pv"] = {
                    "raison": "secteur tertiaire + surface > 100 m² = potentiel autoconsommation PV",
                    "puissance_kwc_estimee": kwc_estime,
                    "endpoint": "/pv/cotation",
                    "url_tunnel_pv": f"POST /tunnel avec source='cross_sell_pv' siret={t.get('siret', '')}",
                    "source": "tunnel.heuristique_cross_sell_v37_3",
                    "ts": _now(),
                }
                hooks_log["cross_sell_pv"] = f"ok kwc≈{kwc_estime}"
        except Exception as e:
            hooks_log["cross_sell_pv"] = f"skip: {type(e).__name__}"

    # V37.3 — Hook r2 → suggérer délégataire optimal (max prime nette)
    if new_stage == "r2":
        try:
            from negociation import comparer_acheteurs
            cumac = (t.get("checks", {}).get("prime") or {}).get("cumac_total") or 0
            secteurs_t = [t.get("secteur")] if t.get("secteur") else None
            cout_travaux = (entry.get("data") or {}).get("cout_travaux_ttc", 0)
            if cumac > 0:
                comp = comparer_acheteurs(volume_kwhc=cumac, secteurs=secteurs_t, cout_travaux_ttc=cout_travaux)
                # comp peut être dict ou list selon impl ; on extrait le top
                top = None
                if isinstance(comp, dict):
                    cands = comp.get("scenarios") or comp.get("acheteurs") or list(comp.values())
                else:
                    cands = comp
                if cands:
                    cands_ok = [c for c in cands if isinstance(c, dict) and c.get("statut") not in ("REFUSE", "VOLUME_INSUFFISANT")]
                    cands_ok.sort(key=lambda c: -float(c.get("prime_nette") or c.get("prime_brute") or 0))
                    if cands_ok:
                        top = cands_ok[0]
                if top:
                    t.setdefault("suggestions", {})["delegataire"] = {
                        "acheteur": top.get("acheteur"),
                        "type": top.get("type"),
                        "prime_nette_eur": top.get("prime_nette") or top.get("prime_brute"),
                        "prix_mwhc": top.get("prix_mwhc"),
                        "source": "negociation.comparer_acheteurs",
                        "ts": _now(),
                    }
                    hooks_log["delegataire_optimal"] = f"ok {top.get('acheteur')} prime≈{top.get('prime_nette') or top.get('prime_brute'):.0f}€"
        except Exception as e:
            hooks_log["delegataire_optimal"] = f"skip: {type(e).__name__}: {str(e)[:80]}"

    # Hook signature → post_signature.init auto si pas déjà créé
    # V37.2.1 fix : dossier_id = tunnel_id (toujours unique, aucune collision SIRET)
    if new_stage == "signature":
        d = entry.get("data") or {}
        try:
            import post_signature
            dossier_id = t["tunnel_id"]  # canonique : tunnel_id, pas siret
            if not post_signature._load_dossier(dossier_id):
                date_sig = d.get("date_signature") or now_str()
                dates = post_signature._compute_dates_cibles(date_sig)
                ps_dossier = {
                    "dossier_id": dossier_id,
                    "date_signature": date_sig,
                    "installateur": d.get("installateur", ""),
                    "delegataire": d.get("delegataire", ""),
                    "fiches": d.get("fiches") or [],
                    "dates_cibles": dates,
                    "etapes": {k: {"date_reelle": None, "en_cours": False, "notes": ""}
                               for k in post_signature.ETAPES_ORDRE},
                    "tunnel_id": t["tunnel_id"],
                    "siret": t.get("siret", ""),
                    "vendor": t.get("vendor", ""),
                    "created_at": _now(),
                    "updated_at": _now(),
                }
                post_signature._save_dossier(dossier_id, ps_dossier)
                t.setdefault("links", {})["post_signature_dossier_id"] = dossier_id
                t.setdefault("links", {})["post_signature_url"] = f"/post-signature/{dossier_id}"
                hooks_log["post_signature_init"] = f"ok dossier_id={dossier_id}"
            else:
                hooks_log["post_signature_init"] = "skip déjà existant"
        except Exception as e:
            hooks_log["post_signature_init"] = f"err: {type(e).__name__}: {e}"

    # Hook universel → push Monday best-effort si token configuré
    # V37.2.1 fix : log explicitement chaque outcome (succès, erreur monday, skip), plus jamais silent.
    # V37.3.1 fix : skip si tunnel test (source commence par "test" / "smoke" / "retest" / "ci")
    #               pour ne plus polluer le board prod pendant les tests.
    # V37.3.8 : si item Monday existe déjà → MAJ position group + colonnes au lieu de skip.
    src = (t.get("source") or "").lower()
    is_test_tunnel = any(src.startswith(p) for p in ("test_", "smoke", "retest", "ci_"))
    if is_test_tunnel:
        hooks_log["monday_push"] = f"skip tunnel test source={src}"
    elif t.get("monday_item_id") and os.environ.get("MONDAY_API_TOKEN"):
        # V37.3.8 — Item existe : déplacer vers le bon group selon stage + MAJ colonnes
        try:
            from monday_sync import (
                STAGE_TO_MONDAY_GROUP, move_monday_item_to_group,
                update_monday_item_columns, MONDAY_DEFAULT_BOARD,
            )
            group_id = STAGE_TO_MONDAY_GROUP.get(new_stage)
            results = []
            if group_id:
                r1 = move_monday_item_to_group(t["monday_item_id"], group_id, MONDAY_DEFAULT_BOARD)
                if r1 and "error" not in r1:
                    results.append(f"moved→{group_id}")
                else:
                    results.append(f"move_err:{str(r1)[:60]}")
            # MAJ colonnes : prime + cumac si calculées
            cv = {}
            prime = (t.get("checks", {}) or {}).get("prime") or {}
            if prime.get("prime_brute_eur"):
                cv["chiffres"] = str(prime["prime_brute_eur"])
            if t.get("siret") and not t["siret"].startswith("PIPE"):
                cv["texte56"] = t["siret"]
            if cv:
                r2 = update_monday_item_columns(t["monday_item_id"], MONDAY_DEFAULT_BOARD, cv)
                if r2 and "error" not in r2:
                    results.append(f"cols={list(cv.keys())}")
                else:
                    results.append(f"cols_err:{str(r2)[:60]}")
            hooks_log["monday_sync"] = " · ".join(results) if results else "no-op"
        except Exception as e:
            hooks_log["monday_sync"] = f"err: {type(e).__name__}: {e}"
    elif not t.get("monday_item_id"):
        token_present = bool(os.environ.get("MONDAY_API_TOKEN"))
        if not token_present:
            hooks_log["monday_push"] = "skip MONDAY_API_TOKEN absent"
        else:
            try:
                from monday_sync import push_dossier_to_monday
                payload = {
                    "client": {"raison_sociale": t.get("raison_sociale", ""), "siret": t.get("siret", "")},
                    "operation": {"nom_chantier": f"Tunnel {t.get('tunnel_id', '')[:10]} stage={new_stage}"},
                    "calcul": {},
                    "admin": {},
                }
                r = push_dossier_to_monday(payload) or {}
                if r.get("ok") and r.get("monday_item_id"):
                    t["monday_item_id"] = r["monday_item_id"]
                    t.setdefault("links", {})["monday_url"] = r.get("url", "")
                    hooks_log["monday_push"] = f"ok item={r['monday_item_id']}"
                elif r.get("error"):
                    hooks_log["monday_push"] = f"err: {str(r['error'])[:120]}"
                else:
                    hooks_log["monday_push"] = f"err response inattendue: {str(r)[:120]}"
            except Exception as e:
                hooks_log["monday_push"] = f"err exception: {type(e).__name__}: {e}"

    if hooks_log:
        entry["hooks"] = hooks_log


def now_str() -> str:
    """Date courante au format ISO court (YYYY-MM-DD)."""
    return datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")


def list_tunnels(stage: str | None = None, vendor: str | None = None) -> list:
    """Liste les tunnels avec filtres optionnels."""
    if not INDEX_FILE.exists():
        _refresh_index()
    try:
        idx = json.loads(INDEX_FILE.read_text())
    except Exception:
        idx = []
    if stage:
        idx = [t for t in idx if t.get("current_stage") == stage]
    if vendor:
        idx = [t for t in idx if t.get("vendor") == vendor]
    return idx


# V37.3.32 — Helper multi-tenant : extrait l'utilisateur courant via JWT (optionnel)
def _current_user() -> dict | None:
    """Retourne {role, name, sub} depuis le JWT Authorization header, ou None.
    Utilisé par les endpoints pour appliquer le filtrage propriétaire."""
    try:
        from flask import request as _req
        from auth import jwt_verify
        auth_h = _req.headers.get("Authorization", "")
        if not auth_h.lower().startswith("bearer "):
            return None
        token = auth_h[7:].strip()
        payload = jwt_verify(token)
        if not payload:
            return None
        return {
            "sub": payload.get("sub"),
            "name": payload.get("name") or payload.get("sub", "").split("@")[0],
            "role": payload.get("role", "user"),
        }
    except Exception:
        return None


def _filter_for_user(tunnels: list, user: dict | None) -> list:
    """V37.3.32 — Multi-tenant filter :
    - admin → voit tous les tunnels (omniscient)
    - user / readonly → voit uniquement ses tunnels (vendor == user.name OR user.sub)
    - aucun user → comportement legacy (tout visible) — mode dev uniquement
    """
    if user is None:
        # Mode legacy : si CEE_AUTH_REQUIRED=1, rien n'est visible sans token
        if os.environ.get("CEE_AUTH_REQUIRED", "0") == "1":
            return []
        return tunnels
    if user.get("role") == "admin":
        return tunnels  # omniscient
    name = (user.get("name") or "").lower()
    sub = (user.get("sub") or "").lower()
    return [
        t for t in tunnels
        if (t.get("vendor") or "").lower() in (name, sub)
    ]


# V37.3.16 → V37.3.18 — Contexte pipeline pour prospection (4 couleurs commerciales + groupement).
WON_DELIVERED_STAGES = {"post_signature"}            # 🟢 référence aboutie = preuve de foi
WON_IN_PROGRESS_STAGES = {"signature"}                # 🟡 chantier en cours = argument groupement
WON_STAGES = WON_DELIVERED_STAGES | WON_IN_PROGRESS_STAGES
ACTIVE_STAGES = {"audit", "r1", "r2"} | WON_STAGES


def get_pipeline_context() -> dict:
    """Retourne le contexte du pipeline pour enrichir la prospection.

    Mappage 4 couleurs commerciales (V37.3.18) :
    - 🔴 ROUGE   : déjà en pipeline (audit→post_sig) — ne pas re-prospecter
    - 🟢 VERT    : référence aboutie (post_signature) sur même APE/zone — preuve de foi
    - 🟡 JAUNE   : chantier en cours (signature) sur même APE/zone — propose groupement
    - 🔵 BLEU    : prospect normal (pas de match contextuel)

    Sortie :
    - `siren_to_stage` : {siren9: stage}
    - `naf_prefix_to_fiches` : {naf2: [fiches]} agrégé sur gagnés
    - `naf_prefix_to_won_count` : {naf2: nb gagnés}
    - `references_by_naf_dept` : {(naf2, dept): [{tunnel_id, raison_sociale, fiches}, ...]}
                                 → dossiers ABOUTIS à citer comme preuve sociale
    - `groupement_by_naf_dept` : {(naf2, dept): [{tunnel_id, raison_sociale, fiches}, ...]}
                                 → chantiers EN COURS pour pitch mutualisation
    """
    siren_to_stage: dict[str, str] = {}
    naf_to_fiches: dict[str, set] = {}
    naf_to_won_count: dict[str, int] = {}
    references_by_naf_dept: dict[str, list] = {}     # clé "NAF2|DEPT2"
    groupement_by_naf_dept: dict[str, list] = {}

    for f in TUNNEL_DIR.glob("T-*.json"):
        try:
            t = json.loads(f.read_text())
        except Exception:
            continue
        siret = (t.get("siret") or "").strip()
        stage = t.get("current_stage", "")
        if siret and stage in ACTIVE_STAGES:
            digits_only = "".join(c for c in siret if c.isdigit())
            if len(digits_only) >= 9:
                siren_to_stage[digits_only[:9]] = stage

        if stage in WON_STAGES:
            naf_full = ""
            dept = ""
            fiches: list = []
            for h in t.get("history", []) or []:
                d = (h.get("data") or {})
                if not naf_full:
                    naf_full = (d.get("naf") or "").strip()
                if not dept:
                    dept = (d.get("departement") or "").strip()[:2]
                if not fiches:
                    fiches = list(d.get("fiches") or [])
                if naf_full and dept and fiches:
                    break
            if naf_full and fiches:
                prefix = naf_full[:2]
                naf_to_fiches.setdefault(prefix, set()).update(fiches)
                naf_to_won_count[prefix] = naf_to_won_count.get(prefix, 0) + 1
                key = f"{prefix}|{dept}"
                bucket = references_by_naf_dept if stage in WON_DELIVERED_STAGES else groupement_by_naf_dept
                bucket.setdefault(key, []).append({
                    "tunnel_id": t.get("tunnel_id"),
                    "raison_sociale": t.get("raison_sociale"),
                    "fiches": fiches[:5],
                    "naf": naf_full,
                    "departement": dept,
                    "stage": stage,
                })

    return {
        "siren_to_stage": siren_to_stage,
        "naf_prefix_to_fiches": {k: sorted(v) for k, v in naf_to_fiches.items()},
        "naf_prefix_to_won_count": naf_to_won_count,
        "references_by_naf_dept": references_by_naf_dept,
        "groupement_by_naf_dept": groupement_by_naf_dept,
    }


def sales_velocity(month: str | None = None, objectif_par_personne: int = 2) -> dict:
    """KPI dashboard pour objectif V38 +2 signatures/mois/personne.

    month = "YYYY-MM" (défaut : mois courant)
    """
    if not month:
        month = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m")
    tunnels = list_tunnels()
    # Compter signatures = tunnels qui ont atteint stage 'signature' OU 'post_signature' dans le mois
    by_vendor: dict[str, dict] = {}
    for entry in tunnels:
        # Charger le tunnel complet pour parcourir l'historique (signature timestamp)
        t = _load(entry["tunnel_id"])
        if not t:
            continue
        vendor = t.get("vendor") or "non_assigné"
        v = by_vendor.setdefault(vendor, {
            "name": vendor, "leads": 0, "audits": 0, "r1": 0, "r2": 0, "signatures": 0,
        })
        # Compter chaque stage atteint dans le mois
        seen = set()
        for h in t.get("history", []):
            if h.get("ts", "")[:7] != month:
                continue
            s = h.get("stage")
            if s in seen:
                continue
            seen.add(s)
            if s == "lead":
                v["leads"] += 1
            elif s == "audit":
                v["audits"] += 1
            elif s == "r1":
                v["r1"] += 1
            elif s == "r2":
                v["r2"] += 1
            elif s in ("signature", "post_signature"):
                v["signatures"] += 1

    vendors = list(by_vendor.values())
    for v in vendors:
        v["conversion_lead_to_signature"] = round(v["signatures"] / v["leads"], 3) if v["leads"] else 0
        v["conversion_r2_to_signature"] = round(v["signatures"] / v["r2"], 3) if v["r2"] else 0
        v["objectif_atteint"] = v["signatures"] >= objectif_par_personne
    total_sig = sum(v["signatures"] for v in vendors)
    return {
        "période": month,
        "objectif_par_personne": objectif_par_personne,
        "objectif_global_calcule": objectif_par_personne * len(vendors),
        "total_signatures": total_sig,
        "vendors": sorted(vendors, key=lambda v: -v["signatures"]),
    }


# ─────────────────────────────────────────────────────────────
# V37.2 — alertes stagnants + prédictif next-action
# ─────────────────────────────────────────────────────────────

# Seuils en jours par stage (au-delà = stagnant). Ajustable par env CEE_TUNNEL_SLA_<STAGE>_D.
DEFAULT_SLA_DAYS = {
    "lead": 2,        # un lead pas qualifié en 2j = signal froid
    "audit": 1,       # audit = automatique, doit pop en quelques min
    "r1": 7,          # 1 semaine pour caler R1
    "r2": 14,         # 2 semaines pour passer R1→R2
    "signature": 21,  # 3 semaines pour closer post-R2
    "post_signature": 165,  # 165j = délai paiement (cf. post_signature dates_cibles)
}


def _stage_sla_days(stage: str) -> int:
    return int(os.environ.get(f"CEE_TUNNEL_SLA_{stage.upper()}_D", DEFAULT_SLA_DAYS.get(stage, 14)))


def detect_stagnants(now_iso: str | None = None) -> list[dict]:
    """Retourne les tunnels dont le current_stage stagne au-delà du SLA."""
    nw = datetime.now(timezone.utc).replace(tzinfo=None)
    if now_iso:
        try:
            nw = datetime.fromisoformat(now_iso.replace("Z", ""))
        except Exception:
            pass
    alerts = []
    for entry in list_tunnels():
        t = _load(entry["tunnel_id"])
        if not t:
            continue
        stage = t.get("current_stage", "lead")
        if stage == "post_signature":
            continue  # phase finale, gérée par post_signature.alertes (workflow propre)
        try:
            updated = datetime.fromisoformat(t["updated_at"].replace("Z", ""))
        except Exception:
            continue
        days_in_stage = (nw - updated).total_seconds() / 86400
        sla = _stage_sla_days(stage)
        if days_in_stage > sla:
            alerts.append({
                "tunnel_id": t["tunnel_id"],
                "siret": t.get("siret"),
                "raison_sociale": t.get("raison_sociale"),
                "vendor": t.get("vendor"),
                "stage": stage,
                "days_in_stage": round(days_in_stage, 1),
                "sla_days": sla,
                "depassement_pct": round((days_in_stage / sla - 1) * 100, 0),
                "severity": "critique" if days_in_stage > sla * 2 else "haute",
                "next_action": _next_action_for_stage(stage),
            })
    return sorted(alerts, key=lambda a: -a["days_in_stage"])


def _next_action_for_stage(stage: str) -> str:
    """Recommandation prochaine action en fonction du stage courant.
    Sourcée méthodo Jimmy R0→R4 + Maestro 10 commandements (mémoire)."""
    return {
        "lead": "Qualif téléphonique 4 min (trame G1T) — appeler dans 24h",
        "audit": "Lancer /analyse via oracle.html → cumac + prime + score PNCEE",
        "r1": "RDV R1 SPIN : Situation, Problème, Implication, besoin Need-payoff. Booker R2 sous 7j",
        "r2": "Closing Maestro 10 commandements : valider devis, signer mandat, fixer travaux",
        "signature": "Init post_signature, planifier travaux, COFRAC, dépôt PNCEE",
        "post_signature": "Cf. /post-signature/<id>/alertes pour le détail des 8 sous-étapes",
    }.get(stage, "Avancer au stage suivant")


def predict_next(tunnel_id: str) -> dict | None:
    """Pour un tunnel donné, retourne action prioritaire + risque + alertes
    (abrogation imminente, COFRAC probable, délégataire suggéré). V37.3 enrichi.
    Toutes les sources sont tracées dans le retour."""
    t = _load(tunnel_id)
    if not t:
        return None
    stage = t.get("current_stage", "lead")
    sla = _stage_sla_days(stage)
    try:
        updated = datetime.fromisoformat(t["updated_at"].replace("Z", ""))
        nw = datetime.now(timezone.utc).replace(tzinfo=None)
        days = (nw - updated).total_seconds() / 86400
    except Exception:
        days = 0
    pct = days / sla if sla else 0

    alerts: list[dict] = []

    # 1. Abrogation imminente sur les fiches du dossier (lecture deadlines.json)
    fiches = []
    for h in t.get("history", []):
        f = (h.get("data") or {}).get("fiches") or []
        for ref in f:
            if ref not in fiches:
                fiches.append(ref)
    try:
        deadlines_path = Path(__file__).parent / "deadlines.json"
        if deadlines_path.exists() and fiches:
            dl = json.loads(deadlines_path.read_text())
            today = datetime.now(timezone.utc).replace(tzinfo=None)
            for ref in fiches:
                if ref in dl:
                    try:
                        d_abrog = datetime.strptime(dl[ref], "%Y-%m-%d")
                        days_to_abrog = (d_abrog - today).days
                        if days_to_abrog < 0:
                            alerts.append({"type": "abrogation_passee", "fiche": ref, "depuis_j": -days_to_abrog,
                                          "message": f"Fiche {ref} ABROGÉE depuis {-days_to_abrog}j — dossier non recevable",
                                          "severite": "critique", "source": "deadlines.json"})
                        elif days_to_abrog < 90:
                            alerts.append({"type": "abrogation_imminente", "fiche": ref, "dans_j": days_to_abrog,
                                          "message": f"Fiche {ref} abrogée dans {days_to_abrog}j — déposer PNCEE avant",
                                          "severite": "haute" if days_to_abrog < 30 else "moyenne",
                                          "source": "deadlines.json"})
                    except Exception:
                        pass
    except Exception:
        pass

    # 2. COFRAC probable (volume > 10 MWhc)
    cumac = (t.get("checks", {}).get("prime") or {}).get("cumac_total") or 0
    if cumac > 10_000_000:  # > 10 MWhc
        alerts.append({
            "type": "cofrac_probable", "volume_kwhc": cumac,
            "message": f"Volume {cumac/1e6:.1f} MWhc > 10 MWhc → contrôle COFRAC probable (30% en P6). Prévoir photos avant/après géolocalisées.",
            "severite": "info", "source": "tunnel.predict_next + pncee.score_dossier",
        })

    # 3. SLA dépassement
    if pct > 0.7:
        alerts.append({
            "type": "stagnant", "stage": stage, "days_in_stage": round(days, 1), "sla_days": sla,
            "message": f"Stage {stage} stagne {round(days, 1)}j (SLA {sla}j)",
            "severite": "critique" if pct > 1.5 else "haute",
            "source": "tunnel._stage_sla_days",
        })

    # 4. Délégataire suggéré (depuis le hook r2 si déjà set)
    delegataire_sug = (t.get("suggestions", {}) or {}).get("delegataire")

    return {
        "tunnel_id": tunnel_id,
        "stage": stage,
        "next_action": _next_action_for_stage(stage),
        "days_in_stage": round(days, 1),
        "sla_days": sla,
        "risk": "STOP" if pct > 1.5 else ("PRUDENCE" if pct > 0.7 else "GO"),
        "alerts": alerts,
        "alerts_count": len(alerts),
        "alerts_critique": sum(1 for a in alerts if a.get("severite") == "critique"),
        "checks": t.get("checks", {}),
        "links": t.get("links", {}),
        "suggestions": t.get("suggestions", {}),
        "delegataire_suggere": delegataire_sug,
        "_meta": {"version": "V37.3", "ts": _now()},
    }


def register_tunnel_routes(app) -> None:
    """Enregistre les routes /tunnel/* + /analytics/sales-velocity."""

    # V37.3.40 — Gate JWT activé seulement si CEE_AUTH_REQUIRED=1.
    # No-op par défaut → zéro régression.
    from functools import wraps as _wraps

    def _gate(f):
        @_wraps(f)
        def _w(*a, **k):
            if os.environ.get("CEE_AUTH_REQUIRED", "0") == "1":
                from auth import jwt_verify
                ah = request.headers.get("Authorization", "")
                tok = ah[7:].strip() if ah.lower().startswith("bearer ") else ""
                if not tok or not jwt_verify(tok):
                    return jsonify({"error": "Unauthorized — JWT Bearer requis"}), 401
            return f(*a, **k)
        return _w


    def _can_access_tunnel(t: dict, user: dict | None) -> bool:
        """V37.3.32 — Vérifie si user peut accéder à ce tunnel."""
        if user is None:
            return os.environ.get("CEE_AUTH_REQUIRED", "0") != "1"
        if user.get("role") == "admin":
            return True
        name = (user.get("name") or "").lower()
        sub = (user.get("sub") or "").lower()
        return (t.get("vendor") or "").lower() in (name, sub)

    @app.route("/tunnel", methods=["POST"])
    @_gate
    def _tunnel_create():
        d = request.json or {}
        siret = d.get("siret", "")
        try:
            t = create_tunnel(
                siret=siret,
                # V37.3.32 — auto-assign vendor depuis JWT si non fourni
                vendor=d.get("vendor") or (_current_user() or {}).get("name", ""),
                source=d.get("source", "manual"),
                raison_sociale=d.get("raison_sociale", ""),
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify(t), 201

    @app.route("/tunnel/<tunnel_id>", methods=["GET"])
    @_gate
    def _tunnel_get(tunnel_id):
        t = _load(tunnel_id)
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        # V37.3.32 — contrôle accès propriétaire
        if not _can_access_tunnel(t, _current_user()):
            return jsonify({"error": "tunnel non accessible (réservé propriétaire ou admin)"}), 403
        return jsonify(t)

    @app.route("/tunnel/<tunnel_id>/advance", methods=["POST"])
    @_gate
    def _tunnel_advance(tunnel_id):
        # V37.3.44 — IDOR fix : vérif ownership avant advance.
        _t_check = _load(tunnel_id)
        if _t_check and not _can_access_tunnel(_t_check, _current_user()):
            return jsonify({"error": "Forbidden — tunnel non accessible (réservé propriétaire ou admin)"}), 403
        d = request.json or {}
        try:
            t = advance_tunnel(tunnel_id, target_stage=d.get("target_stage"), data=d.get("data"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except PermissionError as e:
            # V37.3 — strict mode : conformité bloquante
            msg = str(e)
            blockers = msg.replace("STRICT_BLOCKED:", "").split("|") if msg.startswith("STRICT_BLOCKED:") else [msg]
            return jsonify({
                "error": "Advance refusé : conformité non atteinte (mode strict CEE_TUNNEL_STRICT=1)",
                "blockers": blockers,
                "action": "Corriger les bloquants ci-dessus puis réessayer, ou retirer CEE_TUNNEL_STRICT pour bypass (non recommandé en prod)",
            }), 422
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        return jsonify(t)

    @app.route("/tunnel/<tunnel_id>/backdate", methods=["POST"])
    @_gate
    def _tunnel_backdate(tunnel_id):
        """V37.3.4 — Réécrit created_at/updated_at + dates des stages dans history.
        Body : {"created_at":"YYYY-MM-DDTHH:MM:SSZ", "updated_at":"...",
                "history_dates":[{"stage":"audit","ts":"..."},...]}
        Permet de refléter la chronologie réelle quand on importe un dossier seedé."""
        t = _load(tunnel_id)
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        # V37.3.44 — IDOR fix
        if not _can_access_tunnel(t, _current_user()):
            return jsonify({"error": "Forbidden — tunnel non accessible"}), 403
        d = request.json or {}
        if "created_at" in d:
            t["created_at"] = d["created_at"]
        if "updated_at" in d:
            t["updated_at"] = d["updated_at"]
        for new_h in d.get("history_dates", []) or []:
            stage = new_h.get("stage")
            ts = new_h.get("ts")
            if not stage or not ts:
                continue
            for h in t.get("history", []):
                if h.get("stage") == stage:
                    h["ts"] = ts
                    break
        _save(t)
        return jsonify(t)

    @app.route("/tunnel/<tunnel_id>/link-post-signature", methods=["POST"])
    @_gate
    def _tunnel_link_post_signature(tunnel_id):
        """V37.3.4 — Lie un tunnel à un dossier post_signature existant
        (cas AHBFC Magritte déjà persisté avant V37.3)."""
        t = _load(tunnel_id)
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        # V37.3.44 — IDOR fix
        if not _can_access_tunnel(t, _current_user()):
            return jsonify({"error": "Forbidden — tunnel non accessible"}), 403
        d = request.json or {}
        ps_id = d.get("post_signature_dossier_id")
        if not ps_id:
            return jsonify({"error": "post_signature_dossier_id requis"}), 400
        try:
            import post_signature
            existing = post_signature._load_dossier(ps_id)
            if not existing:
                return jsonify({"error": f"post_signature dossier {ps_id} introuvable"}), 404
            # Cross-link
            existing["tunnel_id"] = t["tunnel_id"]
            existing.setdefault("vendor", t.get("vendor"))
            post_signature._save_dossier(ps_id, existing)
            t.setdefault("links", {})["post_signature_dossier_id"] = ps_id
            t["links"]["post_signature_url"] = f"/post-signature/{ps_id}"
            _save(t)
            return jsonify({"ok": True, "tunnel_links": t.get("links"), "post_signature_tunnel_id": ps_id})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/tunnel/<tunnel_id>/update", methods=["PATCH", "POST"])
    @_gate
    def _tunnel_update(tunnel_id):
        """V37.3.7 — Met à jour les champs identité d'un tunnel (siret, raison_sociale, vendor).
        Utile pour remplacer un placeholder par les vraies infos une fois connues.
        V37.3.44 — vendor réservé admin (sinon attaquant pourrait s'auto-attribuer un tunnel)."""
        t = _load(tunnel_id)
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        # V37.3.44 — IDOR fix
        user = _current_user()
        if not _can_access_tunnel(t, user):
            return jsonify({"error": "Forbidden — tunnel non accessible"}), 403
        d = request.json or {}
        ALLOWED = {"siret", "raison_sociale", "vendor", "source"}
        # V37.3.44 — non-admin ne peut PAS changer vendor (sinon self-promotion bypass)
        if user and user.get("role") != "admin":
            ALLOWED = ALLOWED - {"vendor"}
        for k, v in d.items():
            if k in ALLOWED and v is not None:
                t[k] = v
        t["updated_at"] = _now()
        _save(t)
        return jsonify(t)

    @app.route("/tunnel/<tunnel_id>", methods=["DELETE"])
    @_gate
    def _tunnel_delete(tunnel_id):
        """V37.3.15 — Supprime un tunnel (résidu test, doublon, erreur de seed).
        Le fichier <tunnel_id>.json est effacé du volume + index rafraîchi.
        Le monday_item_id éventuel n'est PAS supprimé côté Monday (à faire manuellement
        ou via un futur hook monday_delete pour rester explicite côté board).
        V37.3.44 — owner check : seul propriétaire ou admin peut supprimer."""
        p = _path(tunnel_id)
        if not p.exists():
            return jsonify({"error": "tunnel inconnu"}), 404
        try:
            t_snapshot = json.loads(p.read_text())
        except Exception:
            t_snapshot = {"tunnel_id": tunnel_id}
        # V37.3.44 — IDOR fix : check ownership avant suppression
        if not _can_access_tunnel(t_snapshot, _current_user()):
            return jsonify({"error": "Forbidden — tunnel non accessible"}), 403
        p.unlink()
        _refresh_index()
        return jsonify({
            "ok": True,
            "deleted_tunnel_id": tunnel_id,
            "raison_sociale": t_snapshot.get("raison_sociale"),
            "monday_item_id": t_snapshot.get("monday_item_id"),
            "note": "monday_item non supprimé (à faire manuellement si besoin)",
        })

    @app.route("/tunnel/<tunnel_id>/rollback-stage", methods=["POST"])
    @_gate
    def _tunnel_rollback(tunnel_id):
        """V37.3.15 — Recule current_stage à un stage antérieur dans la chronologie.
        Body : {"target_stage": "r2"} — doit exister dans history et être < current_stage.
        Truncate history aux events ≤ target_stage. Utile pour corriger un seed inventé
        (ex: tunnel poussé en signature sans preuve)."""
        t = _load(tunnel_id)
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        # V37.3.44 — IDOR fix
        if not _can_access_tunnel(t, _current_user()):
            return jsonify({"error": "Forbidden — tunnel non accessible"}), 403
        d = request.json or {}
        target = d.get("target_stage")
        if target not in TUNNEL_STAGES:
            return jsonify({"error": f"target_stage invalide. Valeurs : {TUNNEL_STAGES}"}), 400
        cur_idx = TUNNEL_STAGES.index(t["current_stage"]) if t.get("current_stage") in TUNNEL_STAGES else -1
        tgt_idx = TUNNEL_STAGES.index(target)
        if tgt_idx >= cur_idx:
            return jsonify({"error": f"rollback impossible : current={t.get('current_stage')} → target={target} (target doit être strictement antérieur)"}), 400
        # Truncate history aux events dont stage est dans [stages 0..target]
        allowed_stages = set(TUNNEL_STAGES[: tgt_idx + 1])
        new_history = [h for h in t.get("history", []) if h.get("stage") in allowed_stages]
        t["history"] = new_history
        t["current_stage"] = target
        t["updated_at"] = _now()
        t.setdefault("rollbacks", []).append({
            "from": TUNNEL_STAGES[cur_idx] if cur_idx >= 0 else None,
            "to": target,
            "ts": t["updated_at"],
            "reason": d.get("reason", ""),
        })
        _save(t)
        return jsonify(t)

    @app.route("/tunnel/<tunnel_id>/push-monday", methods=["POST"])
    @_gate
    def _tunnel_push_monday_now(tunnel_id):
        """V37.3.6 — Force le push d'un tunnel vers Monday board.
        Idempotent : retourne le monday_item_id existant si déjà pushé.
        Utilisé pour seeding initial du pipeline + sync manuel ad-hoc."""
        t = _load(tunnel_id)
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        # V37.3.44 — IDOR fix
        if not _can_access_tunnel(t, _current_user()):
            return jsonify({"error": "Forbidden — tunnel non accessible"}), 403
        if t.get("monday_item_id"):
            return jsonify({"ok": True, "skip": "déjà pushé", "monday_item_id": t["monday_item_id"]})
        if not os.environ.get("MONDAY_API_TOKEN"):
            return jsonify({"ok": False, "error": "MONDAY_API_TOKEN non configuré"}), 503
        try:
            from monday_sync import push_dossier_to_monday
            payload = {
                "client": {"raison_sociale": t.get("raison_sociale", ""), "siret": t.get("siret", "")},
                "operation": {"nom_chantier": f"{t.get('raison_sociale') or t['tunnel_id'][:10]} ({t['current_stage']})"},
                "calcul": {},
                "admin": {},
            }
            r = push_dossier_to_monday(payload) or {}
            if r.get("ok") and r.get("monday_item_id"):
                t["monday_item_id"] = r["monday_item_id"]
                t.setdefault("links", {})["monday_url"] = r.get("url", "")
                _save(t)
                return jsonify({"ok": True, "monday_item_id": r["monday_item_id"], "url": r.get("url")})
            return jsonify({"ok": False, "error": r.get("error", str(r))}), 502
        except Exception as e:
            return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

    @app.route("/tunnel/<tunnel_id>/full", methods=["GET"])
    @_gate
    def _tunnel_full(tunnel_id):
        """V37.3 — Vue contextuelle complète : tunnel + prédictif + alertes + sources tracées.
        À utiliser comme endpoint principal côté UI commercial pour avoir tout le contexte d'un coup."""
        t = _load(tunnel_id)
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        # V37.3.44 — IDOR fix
        if not _can_access_tunnel(t, _current_user()):
            return jsonify({"error": "Forbidden — tunnel non accessible"}), 403
        pred = predict_next(tunnel_id)
        return jsonify({
            "tunnel": t,
            "predict_next": pred,
            "stages_remaining": [s for s in TUNNEL_STAGES if TUNNEL_STAGES.index(s) > TUNNEL_STAGES.index(t["current_stage"])],
        })

    @app.route("/tunnel", methods=["GET"])
    @_gate
    def _tunnel_list():
        # V37.3.32 — multi-tenant : non-admin ne voit que ses tunnels
        user = _current_user()
        all_t = list_tunnels(stage=request.args.get("stage"), vendor=request.args.get("vendor"))
        visible = _filter_for_user(all_t, user)
        return jsonify({
            "stages": TUNNEL_STAGES,
            "tunnels": visible,
            "_filter": {
                "user": user["name"] if user else "anonyme",
                "role": user["role"] if user else "anonyme",
                "total": len(all_t),
                "visible": len(visible),
            },
        })

    @app.route("/analytics/sales-velocity", methods=["GET"])
    @_gate
    def _tunnel_velocity():
        try:
            obj = int(request.args.get("objectif", 2))
        except Exception:
            obj = 2
        # V37.3.32 — admin voit tous les vendors, vendor non-admin voit seulement le sien
        full = sales_velocity(month=request.args.get("month"), objectif_par_personne=obj)
        user = _current_user()
        if user and user.get("role") != "admin":
            name = (user.get("name") or "").lower()
            full["vendors"] = [v for v in full.get("vendors", [])
                               if (v.get("name") or "").lower() == name]
            full["_scope"] = f"vendor {user['name']} uniquement"
        else:
            full["_scope"] = "admin / omniscient" if user else "anonyme"
        return jsonify(full)

    @app.route("/tunnel/alerts", methods=["GET"])
    @_gate
    def _tunnel_alerts():
        """Tunnels stagnants au-delà du SLA par stage. Source : SLA codé + env CEE_TUNNEL_SLA_<STAGE>_D.
        V37.3.44 — multi-tenant : non-admin ne voit que ses propres alertes (sinon enumeration leak)."""
        all_alerts = detect_stagnants()
        visible = _filter_for_user(all_alerts, _current_user())
        return jsonify({
            "count": len(visible),
            "critique": sum(1 for a in visible if a["severity"] == "critique"),
            "haute": sum(1 for a in visible if a["severity"] == "haute"),
            "alerts": visible,
            "sla": {s: _stage_sla_days(s) for s in TUNNEL_STAGES},
        })

    @app.route("/tunnel/<tunnel_id>/predict-next", methods=["GET"])
    @_gate
    def _tunnel_predict(tunnel_id):
        """Recommandation prédictive : prochaine action + ETA + niveau de risque.
        V37.3.44 — IDOR fix : check ownership avant la prédiction (sinon enumeration leak)."""
        _t_check = _load(tunnel_id)
        if _t_check and not _can_access_tunnel(_t_check, _current_user()):
            return jsonify({"error": "Forbidden — tunnel non accessible"}), 403
        r = predict_next(tunnel_id)
        if not r:
            return jsonify({"error": "tunnel inconnu"}), 404
        return jsonify(r)
