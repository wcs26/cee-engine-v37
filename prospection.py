"""
Prospection active CEE — Recherche automatique de prospects.

CEE Engine attend un SIRET. Ce module va CHERCHER les prospects automatiquement
via l'API recherche-entreprises.api.gouv.fr, scorer les leads et lancer des
audits batch.

Endpoints :
  POST /prospection/scan-zone               — scan géographique (lat/lon/rayon)
  POST /prospection/scan-secteur            — scan sectoriel national (NAF + départements)
  POST /prospection/batch-audit             — audit batch depuis liste SIRET (max 20)
  GET  /prospection/score-lead/<siret>      — score lead prédictif d'un SIRET
  GET  /prospection/sirene-lookalike/<siret> — V37.3.45 lookalike RGPD-clean (gratuit Sirene)
  POST /prospection/apify/google-maps       — V37.3.45 scraping Google Maps via Apify (token requis)
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
import urllib.parse
import urllib.error
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
    """V37.3.16 → V37.3.18 — Enrichit chaque prospect avec 4 couleurs commerciales.

    Champs injectés (selon match avec l'historique) :
    - already_in_pipeline_stage   → 🔴 rouge : déjà en cours, ne pas re-prospecter
    - references_abouties         → 🟢 vert  : dossiers post_signature même APE+dept
                                              = preuve sociale ("voilà qui s'est fait, en zone X")
    - groupement_possible         → 🟡 jaune : chantiers signature en cours même APE+dept
                                              = pitch "rejoignez le groupement, mutualisation"
    - fiches_suggerees            → fiches CEE qui ont marché sur le préfixe APE
    - naf_prefix_won_count        → nb dossiers gagnés sur même préfixe APE
    - pitch_argument              → speech commercial pré-construit (string court UI)
    """
    try:
        from tunnel import get_pipeline_context
        ctx = get_pipeline_context()
    except Exception:
        return prospects  # fallback silencieux : prospects bruts si tunnel indispo
    siren_to_stage = ctx.get("siren_to_stage", {})
    naf_to_fiches = ctx.get("naf_prefix_to_fiches", {})
    naf_to_won = ctx.get("naf_prefix_to_won_count", {})
    refs_by_key = ctx.get("references_by_naf_dept", {})
    grp_by_key = ctx.get("groupement_by_naf_dept", {})

    for p in prospects:
        siren = (p.get("siren") or "").strip()
        naf_full = (p.get("naf") or "")
        naf_prefix = naf_full[:2]
        dept = (p.get("departement") or "")[:2]
        key = f"{naf_prefix}|{dept}"

        if siren and siren in siren_to_stage:
            p["already_in_pipeline_stage"] = siren_to_stage[siren]

        if naf_prefix and naf_prefix in naf_to_fiches:
            p["fiches_suggerees"] = naf_to_fiches[naf_prefix][:3]
            p["naf_prefix_won_count"] = naf_to_won.get(naf_prefix, 0)

        # 🟢 références abouties (preuve sociale) — même APE + même dept en priorité,
        # fallback même APE seul si pas de dept matché
        refs_strict = refs_by_key.get(key, [])
        if not refs_strict:
            # Élargir au préfixe NAF national si rien dans le dept
            for k, lst in refs_by_key.items():
                if k.startswith(naf_prefix + "|"):
                    refs_strict = refs_strict + lst
        if refs_strict:
            p["references_abouties"] = refs_strict[:3]

        # 🟡 groupement possible — même logique
        grp_strict = grp_by_key.get(key, [])
        if not grp_strict:
            for k, lst in grp_by_key.items():
                if k.startswith(naf_prefix + "|"):
                    grp_strict = grp_strict + lst
        if grp_strict:
            p["groupement_possible"] = grp_strict[:3]

        # V37.3.19 — Speech commercial : QUE DES FAITS, plus de % inventés.
        # Les "70 % seul → 100 % groupé" précédents étaient faux : la prime CEE est en
        # €/MWhc, pas un %. Reformulé en valeur absolue + argument groupement réel
        # (mutualisation frais fixes : étude/COFRAC/mobilisation).
        pitch_parts = []
        if p.get("references_abouties"):
            n = len(refs_by_key.get(key, [])) or len(p["references_abouties"])
            ref0 = p["references_abouties"][0]
            pitch_parts.append(
                f"📍 {n} site{'s' if n>1 else ''} déjà livré{'s' if n>1 else ''} dans votre secteur "
                f"(ex : {ref0.get('raison_sociale','')[:35]}) — référence vérifiable à votre disposition"
            )
        if p.get("groupement_possible"):
            n = len(grp_by_key.get(key, [])) or len(p["groupement_possible"])
            pitch_parts.append(
                f"🤝 {n} chantier{'s' if n>1 else ''} en cours sur même APE+département — "
                f"groupement = mutualisation des frais fixes (étude, COFRAC, mobilisation chantier) "
                f"qui réduit le reste à charge en valeur absolue"
            )
        if pitch_parts:
            p["pitch_argument"] = " · ".join(pitch_parts)

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

    # ───────────────────────────────────────────────────────────────────────
    # V37.3.45 — Lookalike RGPD-clean (Sirene gratuit, instant, zéro API tier)
    # ───────────────────────────────────────────────────────────────────────

    @app.route("/prospection/sirene-lookalike/<siret>", methods=["GET"])
    def prospection_sirene_lookalike(siret: str):
        """Trouve N prospects similaires au SIRET source via Sirene open data.
        Critères : même code NAF + même département + même tranche d'effectifs.
        ?per_page=20 (default), ?dept_only=1 pour restreindre au département source.
        Données 100 % open data publique, RGPD-clean (aucun email/tel).
        """
        try:
            per_page = min(int(request.args.get("per_page", "20")), 100)
        except (ValueError, TypeError):
            per_page = 20
        _journal("sirene-lookalike", {"siret": siret, "per_page": per_page})

        # 1. Récupérer le SIRET source
        url_src = f"{RECHERCHE_API}?q={urllib.parse.quote(siret)}&per_page=1"
        try:
            data = _fetch_json(url_src)
        except Exception as e:
            return jsonify({"error": f"Sirene API error: {e}"}), 502
        entreprises = data.get("results", [])
        if not entreprises:
            return jsonify({"error": "SIRET non trouvé", "siret": siret}), 404
        src = entreprises[0]
        naf = src.get("activite_principale", "")
        nom_src = src.get("nom_complet", "")
        # extraire dept depuis le siège social
        siege = src.get("siege") or {}
        cp = siege.get("code_postal") or ""
        dept = cp[:2] if len(cp) >= 2 else ""
        tranche = src.get("tranche_effectif_salarie")

        if not naf:
            return jsonify({"error": "NAF source absent — lookalike impossible"}), 422

        # 2. Cherche similaires : même NAF + même département (par défaut)
        params = {
            "activite_principale": naf,
            "per_page": str(per_page + 5),  # +5 pour buffer après exclusion source
            "minimal": "true",
            "include": "siege",
        }
        if dept:
            params["departement"] = dept
        if tranche:
            params["tranche_effectif_salarie"] = tranche
        url_sim = f"{RECHERCHE_API}?{urllib.parse.urlencode(params)}"
        try:
            data_sim = _fetch_json(url_sim)
        except Exception as e:
            return jsonify({"error": f"Sirene API error: {e}"}), 502

        results = data_sim.get("results", [])
        # 3. Exclure SIRET source + normaliser
        siren_source = siret[:9]
        prospects = []
        for ent in results:
            ent_siren = ent.get("siren", "")
            if ent_siren == siren_source:
                continue
            siege_e = ent.get("siege") or {}
            prospects.append({
                "siret": siege_e.get("siret", ""),
                "siren": ent_siren,
                "nom": ent.get("nom_complet", ""),
                "naf": ent.get("activite_principale", ""),
                "tranche_effectif": ent.get("tranche_effectif_salarie"),
                "adresse": siege_e.get("adresse", ""),
                "code_postal": siege_e.get("code_postal", ""),
                "ville": siege_e.get("libelle_commune", ""),
                "etat_administratif": siege_e.get("etat_administratif", ""),
            })
            if len(prospects) >= per_page:
                break

        return jsonify({
            "source": {
                "siret": siret,
                "nom": nom_src,
                "naf": naf,
                "departement": dept,
                "tranche_effectif": tranche,
            },
            "criteres_lookalike": {
                "naf": naf,
                "departement": dept,
                "tranche_effectif_salarie": tranche,
            },
            "nb_resultats": len(prospects),
            "prospects": prospects,
            "source_data": "Sirene open data (recherche-entreprises.api.gouv.fr)",
            "rgpd": "Données pro publiques uniquement — aucun email/tel/contact.",
        })

    # ───────────────────────────────────────────────────────────────────────
    # V37.3.45 — Apify Google Maps (consomme APIFY_TOKEN, payant ~$0.20/1k)
    # ───────────────────────────────────────────────────────────────────────

    @app.route("/prospection/apify/google-maps", methods=["POST"])
    def prospection_apify_google_maps():
        """Scrape Google Maps via Apify Actor compass/crawler-google-places.
        Body : {query: "chauffage industriel", location: "Lyon, France", limit: 20, language: "fr"}
        Coût ~$0.20 / 1000 places sur ton compte Apify.
        """
        token = _apify_token()
        if not token:
            return jsonify({
                "error": "APIFY_TOKEN non configuré côté serveur",
                "activation": "fly secrets set APIFY_TOKEN=apify_api_xxx --app cee-engine-v37",
                "doc": "https://console.apify.com/account/integrations",
                "status": "stub",
            }), 503

        body = request.get_json(force=True, silent=True) or {}
        query = (body.get("query") or "").strip()
        location = (body.get("location") or "").strip()
        if not query:
            return jsonify({"error": "query requis (ex: 'chauffage industriel')"}), 400

        # Cap dur pour éviter blowup coût
        try:
            limit = min(int(body.get("limit", 20)), 100)
        except (ValueError, TypeError):
            limit = 20
        language = body.get("language", "fr")

        _journal("apify-google-maps", {"query": query, "location": location, "limit": limit})

        actor_input = {
            "searchStringsArray": [query],
            "maxCrawledPlacesPerSearch": limit,
            "language": language,
            "includeImages": False,
            "includeReviews": False,
        }
        if location:
            actor_input["locationQuery"] = location

        try:
            items = _apify_run_actor("compass~crawler-google-places", actor_input, token)
        except urllib.error.HTTPError as he:
            return jsonify({"error": f"Apify HTTP {he.code}: {he.reason}"}), 502
        except Exception as e:
            return jsonify({"error": f"Apify run error: {type(e).__name__}: {e}"}), 502

        # Normaliser les résultats Google Maps en format CEE Engine
        prospects = []
        for it in (items or [])[:limit]:
            prospects.append({
                "nom": it.get("title") or it.get("name", ""),
                "adresse": it.get("address", ""),
                "code_postal": it.get("postalCode", ""),
                "ville": it.get("city", ""),
                "departement": (it.get("postalCode") or "")[:2],
                "tel": it.get("phone", ""),
                "site_web": it.get("website", ""),
                "categorie": it.get("categoryName", ""),
                "rating": it.get("totalScore"),
                "nb_avis": it.get("reviewsCount"),
                "google_place_id": it.get("placeId", ""),
                "google_maps_url": it.get("url", ""),
            })

        return jsonify({
            "query": query,
            "location": location,
            "nb_resultats": len(prospects),
            "prospects": prospects,
            "source_data": f"Apify Actor compass/crawler-google-places (limit={limit})",
            "cout_estime_usd": round(0.0002 * len(prospects), 4),
            "next_step": "Cross-check chaque prospect avec Sirene via /siret/search?q=<nom>",
        })


# ===========================================================================
# V37.3.45 — Apify integration helpers (module-level)
# ===========================================================================

def _apify_token() -> str:
    """Retourne le token Apify depuis l'env, ou string vide si absent.
    Ne JAMAIS log le token — on retourne juste sa présence/absence."""
    return os.environ.get("APIFY_TOKEN", "").strip()


def _apify_run_actor(actor_id: str, input_payload: dict, token: str,
                     timeout: int = 120) -> list:
    """Lance un Actor Apify en mode synchrone et retourne les items du dataset.

    Utilise l'endpoint REST `run-sync-get-dataset-items` qui :
    - démarre l'actor avec input_payload (JSON)
    - attend la fin (timeout côté serveur Apify aussi)
    - renvoie directement le contenu du dataset par défaut

    actor_id : slug Apify avec '~' comme séparateur (ex: 'compass~crawler-google-places').
    """
    url = (
        f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
        f"?token={urllib.parse.quote(token)}"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(input_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    ctx = _ssl_ctx()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return []
