"""
Prospection active CEE — Recherche automatique de prospects.

CEE Engine attend un SIRET. Ce module va CHERCHER les prospects automatiquement
via l'API recherche-entreprises.api.gouv.fr, scorer les leads et lancer des
audits batch.

Endpoints :
  POST /prospection/scan-zone        — scan géographique (lat/lon/rayon)
  POST /prospection/scan-secteur     — scan sectoriel national (NAF + départements)
  POST /prospection/batch-audit      — audit batch depuis liste SIRET (max 20)
  GET  /prospection/score-lead/<siret> — score lead prédictif d'un SIRET
"""

from __future__ import annotations

import json
import ssl
import urllib.request
import urllib.parse
import logging
from datetime import datetime
from flask import jsonify, request

logger = logging.getLogger("cee.prospection")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RECHERCHE_API = "https://recherche-entreprises.api.gouv.fr/search"

# Mapping secteur → préfixes NAF
SECTEUR_NAF = {
    "sante":     ["86"],
    "commerce":  ["47", "45", "46"],
    "industrie": ["10", "11", "12", "13", "14", "15", "16", "17", "18", "19",
                  "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
                  "30", "31", "32", "33"],
    "hotellerie": ["55", "56"],
    "enseignement": ["85"],
    "bureaux":   ["69", "70", "71", "73"],
}

# NAF considérés "santé/EHPAD" pour le scoring
NAF_SANTE = {"86.10Z", "86.21Z", "87.10A", "87.10B", "87.10C", "87.20A",
             "87.20B", "87.30A", "87.30B", "87.90A", "87.90B", "86.90A"}

# Départements zone climatique H1 (primes plus élevées)
ZONE_H1_DEPTS = {
    "01", "02", "03", "05", "07", "08", "10", "14", "15", "18", "19", "21",
    "23", "25", "26", "27", "28", "36", "38", "39", "41", "42", "43", "45",
    "51", "52", "54", "55", "57", "58", "59", "60", "61", "62", "63", "67",
    "68", "69", "70", "71", "73", "74", "75", "76", "77", "78", "80", "87",
    "88", "89", "90", "91", "92", "93", "94", "95",
}


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch_json(url: str, timeout: int = 15) -> dict:
    """GET JSON depuis une URL avec SSL permissif."""
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                "User-Agent": "CEE-Engine/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            return json.loads(resp.read())
    except Exception as e:
        logger.warning("Fetch %s failed: %s", url, e)
        return {"error": str(e)}


def _journal(action: str, details: dict):
    """Log dans conformite.journal si disponible."""
    try:
        from conformite import journal
        journal(action, details)
    except Exception:
        logger.info("PROSPECTION %s: %s", action, json.dumps(details, default=str))


# ---------------------------------------------------------------------------
# Score lead
# ---------------------------------------------------------------------------

def _extract_dept(etablissement: dict) -> str:
    """Extrait le département depuis un établissement."""
    cp = (etablissement.get("adresse", "") or "")
    # Chercher code postal dans l'adresse
    for part in cp.split():
        if len(part) == 5 and part.isdigit():
            return part[:2]
    cp2 = etablissement.get("code_postal") or etablissement.get("commune", "")
    if cp2 and len(str(cp2)) >= 2:
        return str(cp2)[:2]
    return ""


def compute_score_lead(data: dict) -> dict:
    """Calcule le score lead (0-100) à partir des données entreprise."""
    score = 0
    raisons = []

    # NAF / secteur santé-EHPAD
    naf = data.get("activite_principale") or data.get("naf") or ""
    if naf in NAF_SANTE or naf[:2] in ("86", "87"):
        score += 30
        raisons.append("Secteur santé/EHPAD — gros bâtiments, budget public")

    # Effectif
    effectif = 0
    tranche = data.get("tranche_effectif_salarie") or ""
    # L'API retourne des tranches comme "50 à 99", "100 à 199" etc.
    if isinstance(tranche, str):
        for part in tranche.replace("à", " ").split():
            if part.isdigit():
                effectif = max(effectif, int(part))
                break
    nb_salaries = data.get("nombre_etablissements_ouverts") or 0
    if effectif > 50 or (isinstance(nb_salaries, int) and nb_salaries > 50):
        score += 20
        raisons.append(f"Effectif important ({effectif or nb_salaries}+) — surface probable élevée")

    # Âge du bâtiment (année création)
    creation = data.get("date_creation") or data.get("date_creation_entreprise") or ""
    if creation:
        try:
            annee = int(str(creation)[:4])
            age = datetime.now().year - annee
            if age > 15:
                score += 15
                raisons.append(f"Bâtiment ancien ({annee}) — isolation faible probable")
        except (ValueError, TypeError):
            pass

    # Zone H1
    dept = _extract_dept(data)
    if not dept and data.get("siege", {}).get("code_postal"):
        dept = str(data["siege"]["code_postal"])[:2]
    if dept in ZONE_H1_DEPTS:
        score += 15
        raisons.append(f"Zone H1 (dept {dept}) — primes plus élevées")

    # Multi-établissements
    nb_etabs = data.get("nombre_etablissements_ouverts", 1)
    if isinstance(nb_etabs, int) and nb_etabs > 1:
        score += 10
        raisons.append(f"Multi-établissements ({nb_etabs}) — volume")

    # Pas de procédure BODACC (pas en difficulté)
    procedures = data.get("complements", {}).get("collectivite_territoriale") if isinstance(data.get("complements"), dict) else None
    bodacc = data.get("procedures_collectives") or data.get("complements", {}).get("est_entrepreneur_individuel") if isinstance(data.get("complements"), dict) else None
    # Simple heuristique : si pas de mention procédure collective
    if not data.get("statut_diffusion") == "N":
        score += 10
        raisons.append("Pas de procédure BODACC détectée")

    score = min(score, 100)

    if score >= 60:
        qualification = "chaud"
    elif score >= 35:
        qualification = "tiede"
    else:
        qualification = "froid"

    # Estimation prime grossière (basée sur secteur)
    prime_estimee = 0
    if naf[:2] in ("86", "87"):
        prime_estimee = 85000  # EHPAD/clinique type
    elif naf[:2] in ("55", "56"):
        prime_estimee = 45000  # hôtel/restaurant
    elif naf[:2] in ("47",):
        prime_estimee = 35000  # commerce
    elif naf[:2] in ("85",):
        prime_estimee = 60000  # enseignement
    else:
        prime_estimee = 25000  # défaut tertiaire/industrie

    if nb_etabs and isinstance(nb_etabs, int) and nb_etabs > 1:
        prime_estimee *= min(nb_etabs, 10)

    return {
        "score": score,
        "qualification": qualification,
        "raisons": raisons,
        "prime_estimee": prime_estimee,
    }


# ---------------------------------------------------------------------------
# Recherche entreprises
# ---------------------------------------------------------------------------

def _search_entreprises(params: dict) -> list:
    """Appelle l'API recherche-entreprises.api.gouv.fr."""
    qs = urllib.parse.urlencode(params)
    url = f"{RECHERCHE_API}?{qs}"
    data = _fetch_json(url)
    if "error" in data:
        return []
    return data.get("results", [])


def scan_zone(lat: float, lon: float, rayon_km: float = 30,
              secteur: str | None = None, limit: int = 50) -> list:
    """Scan géographique : entreprises autour d'un point."""
    params = {
        "lat": lat,
        "lon": lon,
        "radius": int(rayon_km),
        "per_page": min(limit, 100),
        "page": 1,
    }
    if secteur and secteur in SECTEUR_NAF:
        # Rechercher par premier NAF du secteur
        params["activite_principale"] = SECTEUR_NAF[secteur][0]

    results = _search_entreprises(params)
    scored = []
    for r in results:
        lead = compute_score_lead(r)
        scored.append({
            "siret": (r.get("siege", {}).get("siret") or ""),
            "siren": r.get("siren", ""),
            "nom": r.get("nom_complet", ""),
            "naf": r.get("activite_principale", ""),
            "adresse": r.get("siege", {}).get("adresse", ""),
            "commune": r.get("siege", {}).get("commune", ""),
            "effectif": r.get("tranche_effectif_salarie", ""),
            "nb_etablissements": r.get("nombre_etablissements_ouverts", 1),
            **lead,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return _enrich_with_pipeline_context(scored[:limit])


def scan_secteur(naf: str, departements: list[str], limit: int = 50) -> list:
    """Scan sectoriel national : entreprises d'un NAF dans des départements."""
    all_results = []
    for dept in departements[:20]:  # max 20 départements
        params = {
            "activite_principale": naf,
            "departement": dept,
            "per_page": min(limit, 25),
            "page": 1,
        }
        results = _search_entreprises(params)
        all_results.extend(results)

    scored = []
    for r in all_results:
        lead = compute_score_lead(r)
        scored.append({
            "siret": (r.get("siege", {}).get("siret") or ""),
            "siren": r.get("siren", ""),
            "nom": r.get("nom_complet", ""),
            "naf": r.get("activite_principale", ""),
            "commune": r.get("siege", {}).get("commune", ""),
            "departement": r.get("siege", {}).get("departement", ""),
            "effectif": r.get("tranche_effectif_salarie", ""),
            **lead,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return _enrich_with_pipeline_context(scored[:limit])


def _enrich_with_pipeline_context(prospects: list) -> list:
    """V37.3.16 — Enrichit chaque prospect avec :
    - already_in_pipeline_stage : si SIREN déjà dans un tunnel actif (audit→post_signature)
                                  → l'UI le rendra ROUGE pour signaler "ne pas re-prospecter"
    - fiches_suggerees : top fiches CEE déjà gagnées sur le même préfixe NAF (2 digits)
                         → "ce qui marche déjà sur le secteur APE"
    - naf_prefix_won_count : nb de tunnels gagnés sur le même secteur
    """
    try:
        from tunnel import get_pipeline_context
        ctx = get_pipeline_context()
    except Exception:
        return prospects  # fallback silencieux : prospects bruts si tunnel indispo
    siren_to_stage = ctx.get("siren_to_stage", {})
    naf_to_fiches = ctx.get("naf_prefix_to_fiches", {})
    naf_to_won = ctx.get("naf_prefix_to_won_count", {})

    for p in prospects:
        siren = (p.get("siren") or "").strip()
        naf_prefix = (p.get("naf") or "")[:2]
        if siren and siren in siren_to_stage:
            p["already_in_pipeline_stage"] = siren_to_stage[siren]
        if naf_prefix and naf_prefix in naf_to_fiches:
            p["fiches_suggerees"] = naf_to_fiches[naf_prefix][:3]
            p["naf_prefix_won_count"] = naf_to_won.get(naf_prefix, 0)
    return prospects


def batch_audit(sirets: list[str]) -> list:
    """Audit batch : appelle /expert pour chaque SIRET (max 20)."""
    sirets = sirets[:20]
    results = []
    for siret in sirets:
        try:
            # Appel interne via l'API recherche-entreprises pour les données
            url = f"{RECHERCHE_API}?q={siret}&per_page=1"
            data = _fetch_json(url)
            entreprises = data.get("results", [])
            if not entreprises:
                results.append({"siret": siret, "error": "SIRET non trouvé"})
                continue
            ent = entreprises[0]
            lead = compute_score_lead(ent)
            naf = ent.get("activite_principale", "")

            # Estimation fiches via mapping
            try:
                from mapping_naf_fiches import FICHE_NAF_MAP
                nb_fiches = sum(1 for f, v in FICHE_NAF_MAP.items()
                                if any(naf.startswith(p) for p in v.get("naf", [])))
            except Exception:
                nb_fiches = 0

            results.append({
                "siret": siret,
                "nom": ent.get("nom_complet", ""),
                "naf": naf,
                "nb_fiches_eligibles": nb_fiches,
                **lead,
            })
        except Exception as e:
            results.append({"siret": siret, "error": str(e)})

    results.sort(key=lambda x: x.get("prime_estimee", 0), reverse=True)
    return results


# ---------------------------------------------------------------------------
# Routes Flask
# ---------------------------------------------------------------------------

def register_prospection_routes(app) -> None:
    """Enregistre les endpoints de prospection active."""

    @app.route("/prospection/scan-zone", methods=["POST"])
    def prospection_scan_zone():
        body = request.get_json(force=True, silent=True) or {}
        lat = body.get("lat")
        lon = body.get("lon")
        if lat is None or lon is None:
            return jsonify({"error": "lat et lon requis"}), 400
        rayon = body.get("rayon_km", 30)
        secteur = body.get("secteur")
        limit = body.get("limit", 50)

        _journal("scan-zone", {"lat": lat, "lon": lon, "rayon_km": rayon,
                                "secteur": secteur, "limit": limit})

        prospects = scan_zone(float(lat), float(lon), float(rayon), secteur, int(limit))
        return jsonify({
            "zone": {"lat": lat, "lon": lon, "rayon_km": rayon},
            "secteur": secteur,
            "nb_resultats": len(prospects),
            "prospects": prospects,
        })

    @app.route("/prospection/scan-secteur", methods=["POST"])
    def prospection_scan_secteur():
        body = request.get_json(force=True, silent=True) or {}
        naf = body.get("naf")
        departements = body.get("departements", [])
        limit = body.get("limit", 50)
        if not naf:
            return jsonify({"error": "naf requis (ex: '86.10Z')"}), 400
        if not departements:
            return jsonify({"error": "departements requis (liste, ex: ['70','90'])"}), 400

        _journal("scan-secteur", {"naf": naf, "departements": departements, "limit": limit})

        prospects = scan_secteur(naf, departements, int(limit))
        return jsonify({
            "naf": naf,
            "departements": departements,
            "nb_resultats": len(prospects),
            "prospects": prospects,
        })

    @app.route("/prospection/batch-audit", methods=["POST"])
    def prospection_batch_audit():
        body = request.get_json(force=True, silent=True) or {}
        sirets = body.get("sirets", [])
        if not sirets:
            return jsonify({"error": "sirets requis (liste)"}), 400
        if len(sirets) > 20:
            return jsonify({"error": "Maximum 20 SIRET par batch (rate limit)"}), 400

        _journal("batch-audit", {"nb_sirets": len(sirets)})

        results = batch_audit(sirets)
        return jsonify({
            "nb_audites": len(results),
            "resultats": results,
        })

    @app.route("/prospection/score-lead/<siret>", methods=["GET"])
    def prospection_score_lead(siret: str):
        _journal("score-lead", {"siret": siret})

        # Recherche via API
        url = f"{RECHERCHE_API}?q={urllib.parse.quote(siret)}&per_page=1"
        data = _fetch_json(url)
        entreprises = data.get("results", [])
        if not entreprises:
            return jsonify({"error": "SIRET non trouvé", "siret": siret}), 404

        ent = entreprises[0]
        lead = compute_score_lead(ent)
        return jsonify({
            "siret": siret,
            "nom": ent.get("nom_complet", ""),
            "naf": ent.get("activite_principale", ""),
            **lead,
        })
