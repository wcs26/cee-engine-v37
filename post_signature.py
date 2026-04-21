"""
POST-SIGNATURE — Branche 7 : suivi complet post-closing
=========================================================
Endpoints :
  POST /post-signature/init              → initialise suivi dossier
  GET  /post-signature/<id>              → état du dossier
  PUT  /post-signature/<id>/etape/<e>    → marquer étape complétée
  GET  /post-signature/<id>/alertes      → alertes actives
  GET  /post-signature/dashboard         → vue d'ensemble
  POST /post-signature/<id>/push-monday  → sync Monday
"""

from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Any

from flask import Flask, request, jsonify

logger = logging.getLogger(__name__)

# TODO [Railway] : filesystem ephemere — les donnees post_signature_data/ sont perdues a chaque redeploy.
# Migration future : Cloudflare D1, SQLite sur volume persistant Railway, ou S3.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "post_signature_data")

# Monday board 5094841405 — group IDs
MONDAY_BOARD_ID = "5094841405"
MONDAY_GROUPS = {
    "R0": "group_mm2hvk6b",
    "R1": "group_mm2hpegm",
    "VT": "group_mm2hqh5y",
    "R2": "group_mm2hegvh",
    "devis_signe": "group_mm2hds6w",
    "travaux_en_cours": "group_mm2hwd61",
    "cofrac_pncee": "group_mm2hrxfp",
    "commission_encaissee": "group_mm2h6t12",
    "KO": "group_mm2h3p80",
}

ETAPES_ORDRE = [
    "mandat_signe",
    "travaux_planifies",
    "travaux_termines",
    "doe_recu",
    "cofrac_planifie",
    "cofrac_valide",
    "pncee_depose",
    "paiement_recu",
]

ETAPES_LABELS = {
    "mandat_signe": "Mandat cession CEE signé",
    "travaux_planifies": "Planification travaux",
    "travaux_termines": "Travaux terminés",
    "doe_recu": "Réception DOE",
    "cofrac_planifie": "Contrôle COFRAC planifié",
    "cofrac_valide": "Contrôle COFRAC validé",
    "pncee_depose": "Dossier PNCEE déposé (EMMY)",
    "paiement_recu": "Paiement reçu",
}

# Mapping étape → group Monday pour push
ETAPE_TO_MONDAY_GROUP = {
    "mandat_signe": "devis_signe",
    "travaux_planifies": "travaux_en_cours",
    "travaux_termines": "travaux_en_cours",
    "doe_recu": "cofrac_pncee",
    "cofrac_planifie": "cofrac_pncee",
    "cofrac_valide": "cofrac_pncee",
    "pncee_depose": "cofrac_pncee",
    "paiement_recu": "commission_encaissee",
}


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _dossier_path(dossier_id: str) -> str:
    return os.path.join(DATA_DIR, f"{dossier_id}.json")


def _load_dossier(dossier_id: str) -> dict | None:
    path = _dossier_path(dossier_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_dossier(dossier_id: str, data: dict):
    _ensure_data_dir()
    with open(_dossier_path(dossier_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _compute_dates_cibles(date_signature: str) -> dict:
    """Calcule les dates cibles à partir de la date de signature."""
    d0 = datetime.strptime(date_signature, "%Y-%m-%d")
    return {
        "mandat_signe": date_signature,
        "travaux_planifies": (d0 + timedelta(days=30)).strftime("%Y-%m-%d"),
        "travaux_termines": (d0 + timedelta(days=60)).strftime("%Y-%m-%d"),
        "doe_recu": (d0 + timedelta(days=75)).strftime("%Y-%m-%d"),
        "cofrac_planifie": (d0 + timedelta(days=80)).strftime("%Y-%m-%d"),
        "cofrac_valide": (d0 + timedelta(days=90)).strftime("%Y-%m-%d"),
        "pncee_depose": (d0 + timedelta(days=120)).strftime("%Y-%m-%d"),
        "paiement_recu": (d0 + timedelta(days=165)).strftime("%Y-%m-%d"),
    }


def _statut_etape(etape_data: dict, date_cible: str) -> str:
    """Détermine le statut d'une étape."""
    if etape_data.get("date_reelle"):
        return "fait"
    today = datetime.now().strftime("%Y-%m-%d")
    if today > date_cible:
        return "en_retard"
    if etape_data.get("en_cours"):
        return "en_cours"
    return "a_faire"


def _get_alertes(dossier: dict) -> list[dict]:
    """Retourne les alertes actives pour un dossier."""
    alertes = []
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    dans_7j = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    dates_cibles = dossier["dates_cibles"]
    etapes = dossier["etapes"]

    for etape_key in ETAPES_ORDRE:
        date_cible = dates_cibles[etape_key]
        etape_data = etapes.get(etape_key, {})

        if etape_data.get("date_reelle"):
            continue  # déjà fait

        if today_str > date_cible:
            jours_retard = (today - datetime.strptime(date_cible, "%Y-%m-%d")).days
            alertes.append({
                "etape": etape_key,
                "label": ETAPES_LABELS[etape_key],
                "date_cible": date_cible,
                "jours_retard": jours_retard,
                "action_requise": f"URGENT: {ETAPES_LABELS[etape_key]} en retard de {jours_retard}j",
                "urgence": "critique" if jours_retard > 14 else "haute",
            })
        elif date_cible <= dans_7j:
            jours_restants = (datetime.strptime(date_cible, "%Y-%m-%d") - today).days
            alertes.append({
                "etape": etape_key,
                "label": ETAPES_LABELS[etape_key],
                "date_cible": date_cible,
                "jours_retard": 0,
                "action_requise": f"{ETAPES_LABELS[etape_key]} dans {jours_restants}j",
                "urgence": "moyenne" if jours_restants > 3 else "haute",
            })

    return alertes


def register_post_signature_routes(app: Flask):
    """Enregistre les routes post-signature sur l'app Flask."""

    @app.route("/post-signature/init", methods=["POST"])
    def post_signature_init():
        data = request.get_json(force=True)
        dossier_id = data.get("dossier_id")
        if not dossier_id:
            return jsonify({"error": "dossier_id requis"}), 400

        date_signature = data.get("date_signature", datetime.now().strftime("%Y-%m-%d"))
        installateur = data.get("installateur", "")
        delegataire = data.get("delegataire", "")
        fiches = data.get("fiches", [])

        dates_cibles = _compute_dates_cibles(date_signature)

        dossier = {
            "dossier_id": dossier_id,
            "date_signature": date_signature,
            "installateur": installateur,
            "delegataire": delegataire,
            "fiches": fiches,
            "dates_cibles": dates_cibles,
            "etapes": {k: {"date_reelle": None, "en_cours": False, "notes": ""} for k in ETAPES_ORDRE},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        _save_dossier(dossier_id, dossier)
        logger.info("Post-signature init: dossier %s", dossier_id)

        return jsonify({
            "status": "ok",
            "dossier_id": dossier_id,
            "planning": dates_cibles,
            "message": f"Dossier {dossier_id} initialisé — travaux J+30, COFRAC J+90, PNCEE J+120, paiement J+165",
        })

    @app.route("/post-signature/<dossier_id>", methods=["GET"])
    def post_signature_etat(dossier_id: str):
        dossier = _load_dossier(dossier_id)
        if not dossier:
            return jsonify({"error": f"Dossier {dossier_id} introuvable"}), 404

        etapes_avec_statut = []
        for etape_key in ETAPES_ORDRE:
            date_cible = dossier["dates_cibles"][etape_key]
            etape_data = dossier["etapes"].get(etape_key, {})
            statut = _statut_etape(etape_data, date_cible)
            jours_retard = 0
            if statut == "en_retard":
                jours_retard = (datetime.now() - datetime.strptime(date_cible, "%Y-%m-%d")).days

            etapes_avec_statut.append({
                "etape": etape_key,
                "label": ETAPES_LABELS[etape_key],
                "date_cible": date_cible,
                "date_reelle": etape_data.get("date_reelle"),
                "statut": statut,
                "jours_retard": jours_retard,
                "notes": etape_data.get("notes", ""),
            })

        return jsonify({
            "dossier_id": dossier_id,
            "date_signature": dossier["date_signature"],
            "installateur": dossier["installateur"],
            "delegataire": dossier["delegataire"],
            "fiches": dossier["fiches"],
            "etapes": etapes_avec_statut,
        })

    @app.route("/post-signature/<dossier_id>/etape/<etape>", methods=["PUT"])
    def post_signature_marquer(dossier_id: str, etape: str):
        if etape not in ETAPES_ORDRE:
            return jsonify({"error": f"Étape inconnue: {etape}. Valides: {ETAPES_ORDRE}"}), 400

        dossier = _load_dossier(dossier_id)
        if not dossier:
            return jsonify({"error": f"Dossier {dossier_id} introuvable"}), 404

        body = request.get_json(force=True) if request.data else {}
        now = datetime.now().strftime("%Y-%m-%d")

        dossier["etapes"][etape]["date_reelle"] = body.get("date", now)
        dossier["etapes"][etape]["en_cours"] = False
        dossier["etapes"][etape]["notes"] = body.get("notes", dossier["etapes"][etape].get("notes", ""))
        dossier["updated_at"] = datetime.now().isoformat()

        _save_dossier(dossier_id, dossier)
        logger.info("Post-signature: dossier %s — étape %s marquée fait", dossier_id, etape)

        return jsonify({
            "status": "ok",
            "dossier_id": dossier_id,
            "etape": etape,
            "date_reelle": dossier["etapes"][etape]["date_reelle"],
            "message": f"{ETAPES_LABELS[etape]} validé",
        })

    @app.route("/post-signature/<dossier_id>/alertes", methods=["GET"])
    def post_signature_alertes(dossier_id: str):
        dossier = _load_dossier(dossier_id)
        if not dossier:
            return jsonify({"error": f"Dossier {dossier_id} introuvable"}), 404

        alertes = _get_alertes(dossier)
        return jsonify({
            "dossier_id": dossier_id,
            "nb_alertes": len(alertes),
            "alertes": alertes,
        })

    @app.route("/post-signature/dashboard", methods=["GET"])
    def post_signature_dashboard():
        _ensure_data_dir()
        files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]

        stats = {k: 0 for k in ETAPES_ORDRE}
        stats["total"] = len(files)
        dossiers_en_retard = []
        montant_attente = 0.0
        prochain_paiement = None

        for fname in files:
            path = os.path.join(DATA_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                dossier = json.load(f)

            # Trouver l'étape courante (première non faite)
            etape_courante = None
            for ek in ETAPES_ORDRE:
                if not dossier["etapes"].get(ek, {}).get("date_reelle"):
                    etape_courante = ek
                    break

            if etape_courante:
                stats[etape_courante] = stats.get(etape_courante, 0) + 1

                # En retard ?
                date_cible = dossier["dates_cibles"].get(etape_courante, "")
                if date_cible and datetime.now().strftime("%Y-%m-%d") > date_cible:
                    dossiers_en_retard.append({
                        "dossier_id": dossier["dossier_id"],
                        "etape": etape_courante,
                        "date_cible": date_cible,
                        "jours_retard": (datetime.now() - datetime.strptime(date_cible, "%Y-%m-%d")).days,
                    })

            # Paiement en attente
            if not dossier["etapes"].get("paiement_recu", {}).get("date_reelle"):
                montant_attente += dossier.get("prime_eur", 0)

                date_paie = dossier["dates_cibles"].get("paiement_recu")
                if date_paie:
                    if prochain_paiement is None or date_paie < prochain_paiement:
                        prochain_paiement = date_paie

        return jsonify({
            "total_dossiers": stats["total"],
            "par_etape": {ETAPES_LABELS.get(k, k): v for k, v in stats.items() if k != "total"},
            "montant_attente_paiement": round(montant_attente, 2),
            "dossiers_en_retard": dossiers_en_retard,
            "nb_en_retard": len(dossiers_en_retard),
            "prochain_paiement_attendu": prochain_paiement,
        })

    @app.route("/post-signature/<dossier_id>/push-monday", methods=["POST"])
    def post_signature_push_monday(dossier_id: str):
        dossier = _load_dossier(dossier_id)
        if not dossier:
            return jsonify({"error": f"Dossier {dossier_id} introuvable"}), 404

        # Trouver la dernière étape complétée
        derniere_etape = None
        for ek in ETAPES_ORDRE:
            if dossier["etapes"].get(ek, {}).get("date_reelle"):
                derniere_etape = ek

        if not derniere_etape:
            target_group = "devis_signe"
        else:
            target_group = ETAPE_TO_MONDAY_GROUP.get(derniere_etape, "devis_signe")

        group_id = MONDAY_GROUPS.get(target_group, target_group)

        # Tentative de push Monday via monday_sync
        monday_result = {"simulated": True, "message": "Monday API non appelée (dry run)"}
        try:
            from monday_sync import get_monday_api_key
            api_key = get_monday_api_key()
            if api_key:
                import urllib.request
                query = """mutation ($item_id: ID!, $group_id: String!, $board_id: ID!) {
                    move_item_to_group(item_id: $item_id, group_id: $group_id) { id }
                }"""
                body = request.get_json(force=True) if request.data else {}
                monday_item_id = body.get("monday_item_id")
                if monday_item_id:
                    payload = json.dumps({
                        "query": query,
                        "variables": {
                            "item_id": str(monday_item_id),
                            "group_id": group_id,
                            "board_id": MONDAY_BOARD_ID,
                        }
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        "https://api.monday.com/v2",
                        data=payload,
                        headers={
                            "Authorization": api_key,
                            "Content-Type": "application/json",
                        },
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        monday_result = json.loads(resp.read().decode("utf-8"))
                else:
                    monday_result = {"simulated": True, "message": "monday_item_id non fourni dans le body"}
        except Exception as e:
            monday_result = {"error": str(e)}
            logger.warning("Push Monday failed for %s: %s", dossier_id, e)

        return jsonify({
            "status": "ok",
            "dossier_id": dossier_id,
            "derniere_etape": derniere_etape,
            "target_group": target_group,
            "group_id": group_id,
            "board_id": MONDAY_BOARD_ID,
            "monday_result": monday_result,
        })
