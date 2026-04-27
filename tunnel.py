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
    """Index léger pour la liste — pas de re-load de chaque tunnel à chaque /tunnel GET."""
    idx = []
    for f in TUNNEL_DIR.glob("T-*.json"):
        try:
            t = json.loads(f.read_text())
            idx.append({
                "tunnel_id": t["tunnel_id"],
                "siret": t.get("siret"),
                "current_stage": t.get("current_stage"),
                "vendor": t.get("vendor"),
                "created_at": t.get("created_at"),
                "updated_at": t.get("updated_at"),
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
    erreurs dans entry['hooks'] mais ne casse jamais l'advance."""
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
                }
                hooks_log["pncee_score"] = "ok"
        except Exception as e:
            hooks_log["pncee_score"] = f"err: {e}"

    # Hook signature → post_signature.init auto si pas déjà créé
    if new_stage == "signature":
        d = entry.get("data") or {}
        try:
            import post_signature
            dossier_id = t.get("siret") or t.get("tunnel_id")
            if dossier_id and not post_signature._load_dossier(dossier_id):
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
                    "vendor": t.get("vendor", ""),
                    "created_at": _now(),
                    "updated_at": _now(),
                }
                post_signature._save_dossier(dossier_id, ps_dossier)
                t.setdefault("links", {})["post_signature_dossier_id"] = dossier_id
                hooks_log["post_signature_init"] = "ok"
        except Exception as e:
            hooks_log["post_signature_init"] = f"err: {e}"

    # Hook universel → push Monday best-effort si token configuré
    if os.environ.get("MONDAY_API_TOKEN") and not t.get("monday_item_id"):
        try:
            from monday_sync import push_dossier_to_monday
            payload = {
                "client": {"raison_sociale": t.get("raison_sociale", ""), "siret": t.get("siret", "")},
                "operation": {"nom_chantier": f"Tunnel {t.get('tunnel_id', '')[:10]} stage={new_stage}"},
                "calcul": {},
                "admin": {},
            }
            r = push_dossier_to_monday(payload)
            if r.get("ok") and r.get("monday_item_id"):
                t["monday_item_id"] = r["monday_item_id"]
                t.setdefault("links", {})["monday_url"] = r.get("url", "")
                hooks_log["monday_push"] = f"item={r['monday_item_id']}"
        except Exception as e:
            hooks_log["monday_push"] = f"err: {e}"

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
    """Pour un tunnel donné, retourne action + ETA + risque."""
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
    return {
        "tunnel_id": tunnel_id,
        "stage": stage,
        "next_action": _next_action_for_stage(stage),
        "days_in_stage": round(days, 1),
        "sla_days": sla,
        "risk": "STOP" if pct > 1.5 else ("PRUDENCE" if pct > 0.7 else "GO"),
        "checks": t.get("checks", {}),
        "links": t.get("links", {}),
    }


def register_tunnel_routes(app) -> None:
    """Enregistre les routes /tunnel/* + /analytics/sales-velocity."""

    @app.route("/tunnel", methods=["POST"])
    def _tunnel_create():
        d = request.json or {}
        siret = d.get("siret", "")
        try:
            t = create_tunnel(
                siret=siret,
                vendor=d.get("vendor", ""),
                source=d.get("source", "manual"),
                raison_sociale=d.get("raison_sociale", ""),
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify(t), 201

    @app.route("/tunnel/<tunnel_id>", methods=["GET"])
    def _tunnel_get(tunnel_id):
        t = _load(tunnel_id)
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        return jsonify(t)

    @app.route("/tunnel/<tunnel_id>/advance", methods=["POST"])
    def _tunnel_advance(tunnel_id):
        d = request.json or {}
        try:
            t = advance_tunnel(tunnel_id, target_stage=d.get("target_stage"), data=d.get("data"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        return jsonify(t)

    @app.route("/tunnel", methods=["GET"])
    def _tunnel_list():
        return jsonify({
            "stages": TUNNEL_STAGES,
            "tunnels": list_tunnels(
                stage=request.args.get("stage"),
                vendor=request.args.get("vendor"),
            ),
        })

    @app.route("/analytics/sales-velocity", methods=["GET"])
    def _tunnel_velocity():
        try:
            obj = int(request.args.get("objectif", 2))
        except Exception:
            obj = 2
        return jsonify(sales_velocity(
            month=request.args.get("month"),
            objectif_par_personne=obj,
        ))

    @app.route("/tunnel/alerts", methods=["GET"])
    def _tunnel_alerts():
        """Tunnels stagnants au-delà du SLA par stage. Source : SLA codé + env CEE_TUNNEL_SLA_<STAGE>_D."""
        alerts = detect_stagnants()
        return jsonify({
            "count": len(alerts),
            "critique": sum(1 for a in alerts if a["severity"] == "critique"),
            "haute": sum(1 for a in alerts if a["severity"] == "haute"),
            "alerts": alerts,
            "sla": {s: _stage_sla_days(s) for s in TUNNEL_STAGES},
        })

    @app.route("/tunnel/<tunnel_id>/predict-next", methods=["GET"])
    def _tunnel_predict(tunnel_id):
        """Recommandation prédictive : prochaine action + ETA + niveau de risque."""
        r = predict_next(tunnel_id)
        if not r:
            return jsonify({"error": "tunnel inconnu"}), 404
        return jsonify(r)
