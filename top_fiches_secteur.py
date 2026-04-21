"""
TOP 5 fiches CEE les plus rentables par secteur d'activité.

Pré-calcule pour chaque secteur les fiches avec la meilleure prime estimée,
en utilisant les vraies formules du moteur (compute_full).

Endpoint : GET /top-fiches/<secteur>?zone=H1&surface=1000
"""

from __future__ import annotations

import logging
from flask import jsonify, request

from moteur_cee_master import (
    load_fiches, load_deadlines, is_eligible, compute_full,
    _sectors_from_activity, PRIX_CUMAC,
)
from couts_chantier import COUTS_CATALOGUE

log = logging.getLogger(__name__)

SECTEURS_PRINCIPAUX = [
    "sante", "commerce", "commerce_alimentaire", "industrie",
    "bureaux", "enseignement", "logement_collectif", "hotellerie",
    "agriculture_elevage",
]


def _cout_chantier_estime(ref: str, secteur: str, zone: str, surface: float) -> dict | None:
    """Cherche le cout dans COUTS_CATALOGUE. Retourne {cout_total, unite} ou None."""
    key = (ref, secteur, zone)
    if key not in COUTS_CATALOGUE:
        # Essayer "tertiaire" comme fallback pour les secteurs tertiaires
        if secteur in ("sante", "commerce", "commerce_alimentaire", "bureaux",
                       "enseignement", "hotellerie"):
            key = (ref, "tertiaire", zone)
        if key not in COUTS_CATALOGUE:
            return None

    postes = COUTS_CATALOGUE[key]
    unite_poste, poste = next(iter(postes.items()))

    if unite_poste == "m2":
        quantite = surface
    else:
        # Pour les unites/kw/ps, estimer une quantite raisonnable
        quantite = max(1, surface / 100)  # heuristique : 1 unite pour 100 m2

    cout_total = round(poste.cout_interne_total * quantite, 2)
    return {"cout_total": cout_total, "unite": unite_poste, "quantite": quantite}


def top_fiches_pour_secteur(secteur: str, zone: str = "H1", surface: float = 1000) -> list[dict]:
    """Retourne les TOP 5 fiches les plus rentables pour un secteur.

    Utilise les vraies formules du moteur CEE (compute_full).
    """
    fiches = load_fiches()
    deadlines = load_deadlines()
    allowed_sectors = _sectors_from_activity(secteur)

    params = {
        "zone": zone,
        "surface": surface,
        "quantite": 10,       # defaut pour fiches unitaires
        "puissance": 50,      # defaut pour fiches unitaires (kW)
        "nb_logements": 20,   # defaut logement collectif
        "longueur": 100,      # defaut pour fiches lineaires
    }

    resultats = []

    for f in fiches:
        if not is_eligible(f, params, _deadlines=deadlines, allowed_sectors=allowed_sectors):
            continue

        result = compute_full(f, params, zone, activity_sector=secteur)
        if not result or result["cumac"] <= 0:
            continue

        # Cout chantier depuis COUTS_CATALOGUE
        cout_info = _cout_chantier_estime(f["ref"], secteur, zone, surface)

        if cout_info:
            cout_travaux = cout_info["cout_total"]
            couverture = round(result["prime_brute"] / cout_travaux * 100, 1) if cout_travaux > 0 else 0
            modele_0_euro = couverture >= 100
            cout_label = f"{cout_travaux:,.0f} EUR"
        else:
            cout_travaux = None
            couverture = None
            modele_0_euro = result.get("zero_euro", False) or result.get("cov_level") in ("ZERO_EURO", "MARGE_POSITIVE")
            cout_label = "cout inconnu"

        resultats.append({
            "ref": result["ref"],
            "nom": result["nom"],
            "cumac_estime": result["cumac"],
            "prime_estimee": result["prime_brute"],
            "cout_travaux_estime": cout_travaux,
            "cout_travaux_label": cout_label,
            "couverture_pct": couverture,
            "modele_0_euro": modele_0_euro,
        })

    # Trier par prime decroissante, garder top 5
    resultats.sort(key=lambda x: x["prime_estimee"], reverse=True)
    return resultats[:5]


# ═══════════════════════════════════════════════════════════════════════════
# DICT PRE-CALCULE pour les 9 secteurs principaux (zone H1, 1000 m2)
# ═══════════════════════════════════════════════════════════════════════════

def _build_top_par_secteur() -> dict[str, list[dict]]:
    """Construit le cache TOP 5 par secteur au chargement."""
    result = {}
    for secteur in SECTEURS_PRINCIPAUX:
        try:
            result[secteur] = top_fiches_pour_secteur(secteur)
        except Exception as e:
            log.warning("top_fiches_pour_secteur(%s) erreur: %s", secteur, e)
            result[secteur] = []
    return result


try:
    TOP_PAR_SECTEUR = _build_top_par_secteur()
except Exception as e:
    log.error("Impossible de pre-calculer TOP_PAR_SECTEUR: %s", e)
    TOP_PAR_SECTEUR = {}


# ═══════════════════════════════════════════════════════════════════════════
# ROUTES FLASK
# ═══════════════════════════════════════════════════════════════════════════

def register_top_fiches_routes(app) -> None:

    @app.route("/top-fiches/<secteur>", methods=["GET"])
    def _top_fiches(secteur):
        """GET /top-fiches/sante?zone=H1&surface=1000"""
        zone = request.args.get("zone", "H1")
        try:
            surface = float(request.args.get("surface", 1000))
        except (ValueError, TypeError):
            return jsonify({"error": "surface doit etre numerique"}), 400

        if secteur not in SECTEURS_PRINCIPAUX:
            return jsonify({
                "error": f"secteur '{secteur}' inconnu",
                "secteurs_valides": SECTEURS_PRINCIPAUX,
            }), 400

        # Utiliser le cache si parametres par defaut
        if zone == "H1" and surface == 1000 and secteur in TOP_PAR_SECTEUR:
            data = TOP_PAR_SECTEUR[secteur]
        else:
            data = top_fiches_pour_secteur(secteur, zone=zone, surface=surface)

        return jsonify({
            "secteur": secteur,
            "zone": zone,
            "surface_m2": surface,
            "top_fiches": data,
            "nb_resultats": len(data),
        })

    @app.route("/top-fiches", methods=["GET"])
    def _top_fiches_all():
        """GET /top-fiches — retourne le cache pre-calcule pour les 9 secteurs."""
        return jsonify({
            "secteurs": SECTEURS_PRINCIPAUX,
            "top_par_secteur": TOP_PAR_SECTEUR,
            "parametres_defaut": {"zone": "H1", "surface_m2": 1000},
        })
