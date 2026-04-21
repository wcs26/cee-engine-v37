"""
Module Fidélisation — Récurrence client
========================================
GET /fidelisation/<siret>           → opportunités complémentaires (PV, IRVE, maintenance)
GET /fidelisation/cycle-vie/<siret> → timeline cycle de vie bâtiment post-CEE

1 client CEE = 4 opportunités (CEE + PV + IRVE + maintenance).
Réversion CEE/m² = bonus fidélité calculé sur prime / durée cumac.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from flask import Blueprint, jsonify

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DOSSIERS_DIR = os.path.join(os.path.dirname(__file__), "dossiers_data")

# Durée cumac par fiche (ans) — valeurs réglementaires courantes
DUREE_CUMAC = {
    "BAT-EN-101": 12, "BAT-EN-102": 30, "BAT-EN-103": 30,
    "BAT-EN-104": 12, "BAT-EN-106": 12, "BAT-EN-107": 30,
    "BAT-EN-108": 30, "BAT-EN-109": 12,
    "BAT-TH-102": 12, "BAT-TH-104": 17, "BAT-TH-113": 17,
    "BAT-TH-116": 17, "BAT-TH-127": 17, "BAT-TH-139": 17,
    "BAT-TH-140": 17, "BAT-TH-141": 12, "BAT-TH-155": 17,
    "BAT-TH-157": 17, "BAT-TH-159": 12,
    "BAT-EQ-111": 12, "BAT-EQ-117": 12, "BAT-EQ-133": 12,
}

# NAF tertiaire avec parking probable
NAF_PARKING = {
    "4711", "4719", "4720", "4730", "4741", "4742", "4743",  # commerce
    "5510", "5520",  # hôtellerie
    "8610", "8621", "8622", "8710", "8720", "8730",  # santé
    "8510", "8520", "8531", "8532",  # enseignement
    "6820",  # immobilier
}

NAF_SANTE_EHPAD = {"8610", "8621", "8622", "8710", "8720", "8730"}


def _load_dossiers_for_siret(siret: str) -> list[dict]:
    """Charge tous les dossiers d'un SIRET depuis dossiers_data/."""
    index_path = os.path.join(DOSSIERS_DIR, "_index.json")
    if not os.path.exists(index_path):
        return []
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    results = []
    for entry in index.get("entries", []):
        if entry.get("client_siret") == siret:
            # Charger le fichier détail si existant
            detail_path = os.path.join(DOSSIERS_DIR, f"{entry['id']}.json")
            if os.path.exists(detail_path):
                with open(detail_path, "r", encoding="utf-8") as df:
                    detail = json.load(df)
                    results.append({**entry, **detail})
            else:
                results.append(entry)
    return results


def _detect_opportunites(dossiers: list[dict]) -> list[dict]:
    """Détecte les opportunités complémentaires à partir des dossiers CEE réalisés."""
    opps = []
    fiches_faites = {d.get("operation_fiche", "") for d in dossiers}
    naf_codes = {d.get("naf", d.get("client_naf", ""))[:4] for d in dossiers}

    # 1) BAT-EN-103 fait → PV
    if "BAT-EN-103" in fiches_faites:
        opps.append({
            "type": "PV",
            "label": "Photovoltaique autoconsommation",
            "argumentaire": (
                "La toiture vient d'etre isolee (BAT-EN-103). "
                "L'etancheite est neuve, la charge admissible connue : "
                "conditions ideales pour poser des panneaux PV sans redepose. "
                "ROI autoconso tertiaire = 5-7 ans."
            ),
            "estimation_ca": 35000,
        })

    # 2) BAT-TH-113 ou PAC fait → maintenance
    fiches_pac = {"BAT-TH-113", "BAT-TH-127", "BAT-TH-139", "BAT-TH-140", "BAT-TH-155", "BAT-TH-159"}
    if fiches_faites & fiches_pac:
        opps.append({
            "type": "MAINTENANCE_PAC",
            "label": "Contrat maintenance PAC / CTA annuel",
            "argumentaire": (
                "Une PAC ou CTA vient d'etre installee. "
                "La maintenance annuelle est obligatoire (decret 2020-912). "
                "Contrat P2/P3 = recurrence garantie 5-10 ans."
            ),
            "estimation_ca": 2500,
        })

    # 3) Tertiaire avec parking → IRVE
    if naf_codes & NAF_PARKING:
        opps.append({
            "type": "IRVE",
            "label": "Bornes de recharge vehicules electriques",
            "argumentaire": (
                "Site tertiaire avec parking : obligation pre-equipement IRVE "
                "(loi LOM art. 64). Subventions ADVENIR jusqu'a 50%. "
                "Facturation a l'usage = revenu passif."
            ),
            "estimation_ca": 18000,
        })

    # 4) Sante/EHPAD → maintenance ENR
    if naf_codes & NAF_SANTE_EHPAD:
        opps.append({
            "type": "MAINTENANCE_ENR",
            "label": "Contrat maintenance ENR global (chaufferie + VMC + GTB)",
            "argumentaire": (
                "Etablissement de sante : les equipements ENR necessitent "
                "un contrat de maintenance multi-lots (chaufferie, VMC double-flux, GTB). "
                "Conformite ARS + economies garanties par CPE."
            ),
            "estimation_ca": 8000,
        })

    return opps


def _calc_reversion_cee_m2(dossiers: list[dict]) -> float | None:
    """Calcule la réversion CEE/m² = prime / (surface * durée cumac)."""
    total_rev = 0.0
    total_surface = 0.0
    for d in dossiers:
        prime = d.get("prime_obligé_eur") or d.get("prime_oblige_eur") or 0
        surface = d.get("operation_surface_m2") or d.get("surface") or 0
        fiche = d.get("operation_fiche", "")
        duree = DUREE_CUMAC.get(fiche, 15)
        if prime > 0 and surface > 0:
            total_rev += prime / duree
            total_surface += surface
    if total_surface == 0:
        return None
    return round(total_rev / total_surface, 2)


# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

fidelisation_bp = Blueprint("fidelisation", __name__)


@fidelisation_bp.route("/fidelisation/<siret>", methods=["GET"])
def get_fidelisation(siret):
    """Opportunités récurrentes pour un client identifié par SIRET."""
    dossiers = _load_dossiers_for_siret(siret)
    if not dossiers:
        return jsonify({
            "siret": siret,
            "message": "Aucun dossier CEE trouve pour ce SIRET. Creer un dossier d'abord.",
            "opportunites": [],
            "reversion_cee_m2": None,
        }), 404

    opps = _detect_opportunites(dossiers)
    reversion = _calc_reversion_cee_m2(dossiers)

    return jsonify({
        "siret": siret,
        "nb_dossiers_cee": len(dossiers),
        "opportunites": opps,
        "estimation_ca_total": sum(o["estimation_ca"] for o in opps),
        "reversion_cee_m2": reversion,
        "reversion_explication": (
            "Reversion = prime CEE annualisee / m². "
            "Represente le 'cheque environnement' annuel que le client "
            "economise grace aux travaux CEE. Argument de fidelisation."
        ),
    })


@fidelisation_bp.route("/fidelisation/cycle-vie/<siret>", methods=["GET"])
def get_cycle_vie(siret):
    """Timeline cycle de vie batiment post-CEE."""
    dossiers = _load_dossiers_for_siret(siret)

    # Date J0 = date du dernier dossier ou aujourd'hui
    j0 = None
    for d in dossiers:
        dt_str = d.get("updated_at") or d.get("created_at")
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                if j0 is None or dt > j0:
                    j0 = dt
            except (ValueError, TypeError):
                pass
    if j0 is None:
        j0 = datetime.utcnow()

    timeline = [
        {
            "jour": 0,
            "date": j0.strftime("%Y-%m-%d"),
            "action": "CEE realise",
            "detail": "Dossier CEE finalise. Demarrage du cycle de fidelisation.",
            "statut": "fait",
        },
        {
            "jour": 30,
            "date": (j0 + timedelta(days=30)).strftime("%Y-%m-%d"),
            "action": "Appel satisfaction + questionnaire NPS",
            "detail": "Verifier la satisfaction post-travaux. Collecter un temoignage.",
            "statut": "a_faire",
        },
        {
            "jour": 180,
            "date": (j0 + timedelta(days=180)).strftime("%Y-%m-%d"),
            "action": "Proposition PV (photovoltaique)",
            "detail": (
                "6 mois apres les travaux, la toiture est stabilisee. "
                "Proposer une etude PV autoconsommation."
            ),
            "statut": "a_faire",
        },
        {
            "jour": 365,
            "date": (j0 + timedelta(days=365)).strftime("%Y-%m-%d"),
            "action": "Proposition IRVE (bornes recharge)",
            "detail": (
                "1 an : le client a constate les economies CEE. "
                "Moment ideal pour proposer IRVE (subventions ADVENIR)."
            ),
            "statut": "a_faire",
        },
        {
            "jour": 545,
            "date": (j0 + timedelta(days=545)).strftime("%Y-%m-%d"),
            "action": "Bilan energetique annuel",
            "detail": (
                "18 mois : envoyer un bilan des economies realisees. "
                "Renforce la confiance et prepare la prochaine action."
            ),
            "statut": "a_faire",
        },
        {
            "jour": 730,
            "date": (j0 + timedelta(days=730)).strftime("%Y-%m-%d"),
            "action": "Proposition maintenance ENR",
            "detail": (
                "2 ans : proposer un contrat de maintenance ENR global. "
                "Garantie de performance + conformite reglementaire."
            ),
            "statut": "a_faire",
        },
        {
            "jour": 1095,
            "date": (j0 + timedelta(days=1095)).strftime("%Y-%m-%d"),
            "action": "Renouvellement / nouvelles fiches CEE",
            "detail": (
                "3 ans : certaines fiches CEE permettent un renouvellement. "
                "Verifier les evolutions reglementaires et proposer un nouveau cycle."
            ),
            "statut": "a_faire",
        },
    ]

    return jsonify({
        "siret": siret,
        "j0": j0.strftime("%Y-%m-%d"),
        "nb_dossiers_cee": len(dossiers),
        "timeline": timeline,
    })


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def register_fidelisation_routes(app):
    """Enregistre le blueprint fidélisation sur l'app Flask."""
    app.register_blueprint(fidelisation_bp)
