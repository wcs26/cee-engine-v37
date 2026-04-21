"""
Générateur de Rapport Gisement CEE format SIRAT — calibré sur AHBFC (5 sites validés).

Constantes mesurées sur 5 devis réels (Magritte, Renoir, Gauguin, Courbet, EAM Gray) :
  - BAT-EN-103 santé H1 : 6,24 MWhc/m²
  - Prix cumac obligé moyen marché AHBFC : 8,00 €/MWhc
  - HT travaux SIRAT moyen : 41,60 €/m²

⚠️ COMMISSION : la commission Jimmy = 50 % de la MARGE NETTE (variable, paramétrable),
PAS le barème historique SIRAT ci-dessous (ce barème ne s'applique qu'aux autres
apporteurs SIRAT, pas à Jimmy/WCS Bulgarie). Voir documents_client.Admin.commission_pct_marge.

Endpoints :
  POST /gisement/calcul       — calcul rapide (sans génération HTML)
  POST /gisement/rapport-html — rapport gisement complet HTML (imprimable, format SIRAT)
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass
from datetime import datetime

from flask import jsonify, request, Response


# ─────────────────────────────────────────────────────────────────────
# Coefficients calibrés sur 5 devis SIRAT réels AHBFC (BAT-EN-103 santé H1)
# Pour étendre : ajouter (fiche, secteur, zone) → coeff
# ─────────────────────────────────────────────────────────────────────
COEFF_CUMAC = {
    # (fiche, secteur, zone) : MWhc/m²
    ("BAT-EN-103", "sante", "H1"): 6.24,
    ("BAT-EN-103", "sante", "H2"): 5.20,    # estimation pondérée P6 (à confirmer)
    ("BAT-EN-103", "sante", "H3"): 3.85,    # estimation pondérée P6 (à confirmer)
    ("BAT-EN-101", "sante", "H1"): 2.96,    # estimation 6 m².K/W
}

PRIX_CUMAC_DEFAUT_EUR_MWHC = 8.00            # prix obligé Abokine / Économie d'Énergie SAS

PRIX_TRAVAUX_HT_M2 = {
    "BAT-EN-103": 41.60,
    "BAT-EN-101": 18.00,
}

from config import TVA_PRO as TVA_DEFAUT  # source unique : config.py

# Barème SIRAT historique pour APPORTEURS TIERS (pas Jimmy)
# Conservé en référence : permet d'estimer la commission compétitive vs SIRAT direct.
# Pour Jimmy/WCS : commission = 50 % de la marge nette (cf. Admin.commission_pct_marge).
BAREME_SIRAT_APPORTEUR_TIERS = {
    ("BAT-EN-103", "sante", "H1"): 8.57,
    ("BAT-EN-101", "sante", "H1"): 3.58,
}
COMMISSION_PCT_MARGE_DEFAUT = 50.0   # Jimmy WCS = 50 % de marge nette par défaut

DELEGATAIRES_CONNUS = [
    {"nom": "Abokine",                  "ref": "749843090",   "type": "délégataire CEE"},
    {"nom": "Économie d'Énergie SAS",   "ref": "499 388 544", "type": "obligé/délégataire CEE (ex-Effy)"},
]


@dataclass
class Site:
    nom: str
    adresse: str
    cp: str
    ville: str
    zone: str = "H1"
    secteur: str = "sante"
    type_batiment: str = "tertiaire - Santé"
    surface_m2: float = 0
    fiche: str = "BAT-EN-103"
    hauteur_vs_m: float = 2.0
    isolant: str = "URSA RENOSOUDAL ALU 96mm R=3,00 m².K/W"
    delegataire: str = "Abokine"
    delegataire_ref: str = "749843090"
    referent_nom: str = ""
    referent_tel: str = ""
    beneficiaire: str = "AHBFC"
    siret_beneficiaire: str = ""
    signataire_nom: str = ""
    signataire_fonction: str = ""
    devis_num: str = ""


def calcul_gisement(site: Site, *, coeff_override: float | None = None,
                    prix_cumac_override: float | None = None,
                    prix_ht_m2_override: float | None = None,
                    cout_reel_realisateur_eur: float | None = None,
                    commission_pct_marge: float | None = None) -> dict:
    """Calcule cumac + prime obligé + marge réelle + commission Jimmy.

    Formules :
      - prime obligé = MWhc × prix_cumac          (réglementaire)
      - reste à charge = max(0, TTC − prime)      (vrai 0€ ssi prime ≥ TTC)
      - marge nette = prime obligé − coût réel    (modèle B confirmé Jimmy)
      - commission Jimmy = marge × pct (50% défaut, paramétrable par dossier)

    Si coût réel non fourni → commission non calculable, on marque le champ.
    """
    key = (site.fiche, site.secteur, site.zone)
    coeff = coeff_override if coeff_override is not None else COEFF_CUMAC.get(key)
    if coeff is None:
        return {"error": f"coefficient cumac inconnu pour {key} — fournir coeff_override",
                "available": list(COEFF_CUMAC.keys())}

    mwhc = round(site.surface_m2 * coeff, 1)
    gwhc = round(mwhc / 1000, 3)

    prix_cumac = prix_cumac_override if prix_cumac_override is not None else PRIX_CUMAC_DEFAUT_EUR_MWHC
    ht_m2 = prix_ht_m2_override if prix_ht_m2_override is not None else PRIX_TRAVAUX_HT_M2.get(site.fiche, 0)

    ht = round(site.surface_m2 * ht_m2, 2)
    tva = round(ht * TVA_DEFAUT, 2)
    ttc = round(ht + tva, 2)

    prime_obligé = round(mwhc * prix_cumac, 2)
    reste_a_charge = round(max(0.0, ttc - prime_obligé), 2)
    couvre_ttc = prime_obligé >= ttc

    # Marge nette modèle B : prime obligé encaissée − coût réel SIRAT (saisi)
    pct = commission_pct_marge if commission_pct_marge is not None else COMMISSION_PCT_MARGE_DEFAUT
    marge_calculable = cout_reel_realisateur_eur is not None and cout_reel_realisateur_eur >= 0
    if marge_calculable:
        marge_nette = round(prime_obligé - cout_reel_realisateur_eur, 2)
        commission = round(marge_nette * pct / 100, 2)
    else:
        marge_nette = None
        commission = None

    # Référence : ce qu'aurait pris un apporteur SIRAT tiers (barème historique)
    ref_apporteur_tiers = round(site.surface_m2 * BAREME_SIRAT_APPORTEUR_TIERS.get(key, 0), 2)

    return {
        "site": site.nom,
        "fiche": site.fiche, "zone": site.zone, "secteur": site.secteur,
        "surface_m2": site.surface_m2,
        "coeff_mwhc_m2": coeff,
        "coeff_source": "override" if coeff_override is not None else "calibré (5 devis SIRAT AHBFC)",
        "mwhc": mwhc, "gwhc": gwhc,
        "prix_cumac_eur_mwhc": prix_cumac,
        "prix_travaux_ht_m2": ht_m2,
        "ht_eur": ht, "tva_eur": tva, "ttc_eur": ttc,
        "prime_obligé_eur": prime_obligé,
        "reste_a_charge_eur": reste_a_charge,
        "modele_0_euro": couvre_ttc,
        "cout_reel_realisateur_eur": cout_reel_realisateur_eur,
        "marge_nette_eur": marge_nette,
        "commission_pct_marge_applique": pct,
        "commission_jimmy_eur": commission,
        "commission_calculable": marge_calculable,
        "reference_apporteur_tiers_eur": ref_apporteur_tiers,
    }


def register_gisement_routes(app) -> None:

    @app.route("/gisement/coefficients", methods=["GET"])
    def _gisement_coefs():
        return jsonify({
            "coefficients_cumac_mwhc_m2": [
                {"fiche": k[0], "secteur": k[1], "zone": k[2], "coeff": v}
                for k, v in COEFF_CUMAC.items()
            ],
            "prix_travaux_ht_m2": PRIX_TRAVAUX_HT_M2,
            "prix_cumac_eur_mwhc_defaut": PRIX_CUMAC_DEFAUT_EUR_MWHC,
            "commission_pct_marge_defaut": COMMISSION_PCT_MARGE_DEFAUT,
            "bareme_sirat_apporteur_tiers": [
                {"fiche": k[0], "secteur": k[1], "zone": k[2], "eur_m2": v}
                for k, v in BAREME_SIRAT_APPORTEUR_TIERS.items()
            ],
            "tva_defaut": TVA_DEFAUT,
            "delegataires_connus": DELEGATAIRES_CONNUS,
            "source": "Calibré sur 5 devis SIRAT AHBFC (Magritte, Renoir, Gauguin, Courbet, EAM Gray)",
            "note": "Commission Jimmy = commission_pct_marge_defaut % de (prime_obligé − coût_réel_installateur)",
        })

    @app.route("/gisement/calcul", methods=["POST"])
    def _gisement_calcul():
        """POST body : fiche, secteur, zone, surface_m2, nom, adresse, cp, ville,
        [coeff_cumac_override, prix_cumac_override, prix_travaux_ht_m2_override,
         cout_reel_realisateur_eur, commission_pct_marge]"""
        d = request.json or {}
        site_fields = {k: v for k, v in d.items() if k in Site.__annotations__}
        try:
            site = Site(**site_fields)
        except TypeError as e:
            return jsonify({"error": f"champ invalide: {e}"}), 400
        if site.surface_m2 <= 0:
            return jsonify({"error": "surface_m2 > 0 requis"}), 400
        return jsonify(calcul_gisement(
            site,
            coeff_override=d.get("coeff_cumac_override"),
            prix_cumac_override=d.get("prix_cumac_override"),
            prix_ht_m2_override=d.get("prix_travaux_ht_m2_override"),
            cout_reel_realisateur_eur=d.get("cout_reel_realisateur_eur"),
            commission_pct_marge=d.get("commission_pct_marge"),
        ))
