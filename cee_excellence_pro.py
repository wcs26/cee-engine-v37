"""
CEE EXCELLENCE PRO — Module central d'intelligence CEE
Consolide tous les moteurs en une seule interface unifiée.

Architecture:
  cee_excellence_pro.py  ← CE FICHIER (orchestrateur)
  ├── moteur_cee_master.py  (calcul cumac, eligibilite, compute_full)
  ├── negociation.py        (comparaison acheteurs, prix rachat)
  ├── multisite.py          (optimisation parc batiment par batiment)
  ├── closing.py            (strategie vente, pitch, objections)
  ├── config.py             (prix, commissions, seuils P6)
  └── fiches.json + deadlines.json + cout_travaux.json

Usage:
  from cee_excellence_pro import diagnostic_complet
  result = diagnostic_complet(siret="77559092000788")
  # ou
  result = diagnostic_complet(departement="89", surface=968, energie="electricite", naf="47.11B")
"""

import json
import os
from datetime import datetime

# ═══════════════════════════════════════════════
# IMPORTS INTERNES
# ═══════════════════════════════════════════════

from config import (
    PRIX_CUMAC, PRIX_CUMAC_PRECARITE,
    COMMISSION_RATE, TVA_PRO, TVA_REDUITE, PRIX_NEGOCIE,
)
from moteur_cee_master import (
    get_zone, load_fiches, load_deadlines, load_cout_travaux,
    analyser, analyser_global, compute_full, check_deadline,
    is_eligible, get_cumac,
    regle_75_pct, tolerance_mixte, check_remplacement_premature,
    strategie_multisite, P6_SEUILS,
    SEUIL_DECRET_TERTIAIRE, SEUIL_DOSSIER_SEPARE,
)
from negociation import comparer_acheteurs, ACHETEURS, COUT_COFRAC
from multisite import optimiser_parc, PROFILS_SITES
from closing import analyser_closing
from auto_detect import get_siret, deduce_usage


# ═══════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════

VERSION = "V35-EXCELLENCE"

# Section INSEE → profil métier
SECTION_OVERRIDE = {
    "A": "agriculture_elevage",
    "C": "industrie",
    "F": "construction",
    "G": "commerce_alimentaire",
    "H": "logistique",
    "I": "hotellerie",
    "L": "logement_collectif",
    "O": "administration",
    "P": "enseignement",
    "Q": "hebergement_social",
}

# NAF prefix → profil (pour les cas sans section)
NAF_PROFILS = {
    "01": "agriculture_elevage", "02": "sylviculture_peche", "03": "sylviculture_peche",
    "10": "agroalimentaire", "11": "agroalimentaire", "12": "agroalimentaire",
    "41": "construction", "42": "construction", "43": "construction",
    "45": "garage_auto",
    "46": "commerce_gros",
    "4711": "commerce_alimentaire", "4721": "commerce_alimentaire",
    "4773": "pharmacie",
    "55": "hotellerie",
    "56": "restauration",
    "61": "informatique_telecom",
    "62": "bureaux", "63": "bureaux",
    "64": "banque_assurance", "65": "banque_assurance", "66": "banque_assurance",
    "68": "logement_collectif",
    "84": "administration",
    "85": "enseignement",
    "86": "sante", "862": "medical_liberal",
    "87": "hebergement_social", "881": "hebergement_social",
    "90": "arts_spectacle", "91": "arts_spectacle",
    "92": "sport_loisirs", "93": "sport_loisirs",
    "9601": "pressing_laverie",
    "9602": "coiffure_beaute",
    "9603": "funeraire",
}

# Secteurs CEE par profil
PROFIL_SECTEURS = {
    "commerce_alimentaire": ["BAT", "IND"],
    "commerce_non_alim": ["BAT"],
    "restauration": ["BAT", "IND"],
    "hotellerie": ["BAT"],
    "sante": ["BAT"],
    "bureaux": ["BAT"],
    "enseignement": ["BAT"],
    "industrie": ["IND", "BAT"],
    "logistique": ["TRA", "BAT", "IND"],
    "agriculture_elevage": ["AGRI", "BAT", "IND"],
    "agriculture_cultures": ["AGRI", "BAT"],
    "sylviculture_peche": ["AGRI", "IND"],
    "agroalimentaire": ["IND", "BAT"],
    "boulangerie": ["BAT", "IND"],
    "pharmacie": ["BAT"],
    "garage_auto": ["BAT", "IND"],
    "commerce_gros": ["BAT", "IND"],
    "coiffure_beaute": ["BAT"],
    "pressing_laverie": ["IND", "BAT"],
    "sport_loisirs": ["BAT"],
    "administration": ["BAT"],
    "logement_collectif": ["BAR", "BAT"],
    "logement_individuel": ["BAR"],
    "construction": ["IND", "BAT"],
    "informatique_telecom": ["BAT", "IND"],
    "banque_assurance": ["BAT"],
    "medical_liberal": ["BAT"],
    "hebergement_social": ["BAT", "BAR"],
    "arts_spectacle": ["BAT"],
    "funeraire": ["BAT"],
    "services_divers": ["BAT"],
}


# ═══════════════════════════════════════════════
# DETECTION PROFIL
# ═══════════════════════════════════════════════

def detecter_profil(naf, section_activite=None):
    """Détecte le profil métier depuis le code NAF et la section INSEE.
    La section override le NAF pour les sièges sociaux (70.10Z etc.)."""

    naf_clean = (naf or "").replace(".", "")
    profil = "services_divers"

    # 1. Match NAF spécifique (du plus précis au plus générique)
    for prefix_len in [4, 3, 2]:
        prefix = naf_clean[:prefix_len]
        if prefix in NAF_PROFILS:
            profil = NAF_PROFILS[prefix]
            break
    else:
        # Fallback par tranche
        try:
            n = int(naf_clean[:2])
            if 10 <= n <= 33:
                profil = "industrie"
            elif 69 <= n <= 82:
                profil = "bureaux"
        except ValueError:
            pass

    # 2. Override section INSEE si le profil est générique
    if section_activite and section_activite in SECTION_OVERRIDE:
        if profil in ("bureaux", "services_divers", "banque_assurance"):
            profil = SECTION_OVERRIDE[section_activite]

    return profil


def get_secteurs(profil):
    """Retourne les secteurs CEE pour un profil donné."""
    return PROFIL_SECTEURS.get(profil, ["BAT"])


# ═══════════════════════════════════════════════
# SCORING CONFIANCE
# ═══════════════════════════════════════════════

def scorer_confiance(donnees):
    """Calcule un score de confiance (0-100) sur les données disponibles.
    Plus le score est haut, plus le diagnostic est fiable."""
    score = 0
    details = []

    if donnees.get("siret"):
        score += 15
        details.append("+15 SIRET vérifié")
    if donnees.get("naf"):
        score += 10
        details.append("+10 Code NAF")
    if donnees.get("surface") and donnees["surface"] > 0:
        score += 15
        details.append("+15 Surface renseignée")
    if donnees.get("dpe"):
        score += 20
        details.append("+20 DPE officiel")
    if donnees.get("energie"):
        score += 10
        details.append("+10 Énergie connue")
    if donnees.get("annee_construction"):
        score += 10
        details.append("+10 Année construction")
    if donnees.get("nb_logements") and donnees["nb_logements"] > 0:
        score += 5
        details.append("+5 Nb logements")
    if donnees.get("effectifs"):
        score += 5
        details.append("+5 Effectifs")
    if donnees.get("nb_etablissements") and donnees["nb_etablissements"] > 1:
        score += 5
        details.append("+5 Multi-sites")
    if donnees.get("cofrac"):
        score += 5
        details.append("+5 COFRAC prévu")

    return {"score": min(100, score), "details": details}


# ═══════════════════════════════════════════════
# DIAGNOSTIC COMPLET
# ═══════════════════════════════════════════════

def diagnostic_complet(siret=None, departement=None, surface=0, energie=None,
                       naf=None, nb_sites=1, activity_sector=None,
                       precarite=False, coup_de_pouce=False,
                       qualite_dossier="standard", prix_cumac=None,
                       nb_logements=0, puissance=0, section_activite=None):
    """
    Point d'entrée unique — diagnostic CEE complet.

    Depuis un SIRET ou des paramètres manuels, retourne:
    - Profil métier détecté
    - Fiches éligibles avec primes
    - Comparaison acheteurs CEE
    - Stratégie de closing
    - Optimisation multi-site si applicable
    - Score de confiance
    - Alertes réglementaires
    """

    now = datetime.now()
    entreprise = None

    # === ÉTAPE 1 : Résolution SIRET ===
    if siret:
        entreprise = get_siret(siret)
        if entreprise:
            naf = naf or entreprise.get("naf", "")
            departement = departement or entreprise.get("departement", "")
            # section_activite doit venir de l'API SIRET (champ non standard dans get_siret)
            # On le passe en paramètre si connu

    if not departement:
        return {"error": "Département requis (ou SIRET valide)"}

    zone = get_zone(departement)
    if not zone:
        return {"error": f"Département {departement} invalide"}

    # === ÉTAPE 2 : Détection profil ===
    profil = detecter_profil(naf, section_activite)
    secteurs = get_secteurs(profil)

    # Surface par défaut si pas renseignée
    if not surface or surface <= 0:
        surface = 500  # estimation conservatrice

    # === ÉTAPE 3 : Calcul CEE ===
    params = {
        "departement": departement,
        "zone": zone,
        "surface": surface,
        "quantite": max(1, round(surface / 25)),
        "puissance": puissance or round(surface * 0.05),
        "energie": energie,
        "nb_logements": nb_logements,
        "puissance_froid": 0,
        "longueur": 0,
    }

    resultats = analyser(
        params,
        activity_sector=activity_sector,
        coup_de_pouce=coup_de_pouce,
        prix_cumac=prix_cumac,
        precarite=precarite,
    )

    globaux = analyser_global(resultats) if resultats else {}

    # === ÉTAPE 4 : Négociation acheteurs ===
    volume = globaux.get("total_cumac", 0)
    cout_ttc = globaux.get("total_cost_ttc", 0)
    nego = comparer_acheteurs(
        volume, secteurs, nb_sites, qualite_dossier, precarite, cout_ttc
    )

    # === ÉTAPE 5 : Closing ===
    closing = analyser_closing(
        resultats, globaux, secteurs, nb_sites, qualite_dossier, surface
    )

    # === ÉTAPE 6 : Multi-site ===
    multisite = None
    if nb_sites > 1:
        multisite = optimiser_parc(
            profil, nb_sites, surface, departement, qualite_dossier
        )

    # === ÉTAPE 7 : Score confiance ===
    confiance = scorer_confiance({
        "siret": siret,
        "naf": naf,
        "surface": surface,
        "dpe": None,  # sera enrichi par le frontend si DPE trouvé
        "energie": energie,
        "annee_construction": None,
        "nb_logements": nb_logements,
        "effectifs": entreprise.get("tranche_effectif") if entreprise else None,
        "nb_etablissements": nb_sites,
        "cofrac": qualite_dossier == "cofrac",
    })

    # === ÉTAPE 8 : Veille réglementaire ===
    deadlines = load_deadlines()
    alertes_reglementaires = []

    # Fiches bientôt abrogées dans les résultats
    for r in resultats:
        dl = r.get("deadline", {})
        if dl.get("status") == "attention":
            alertes_reglementaires.append({
                "type": "deadline",
                "ref": r["ref"],
                "message": f"{r['ref']} abrogée dans {dl.get('jours_restants', '?')} jours",
                "urgence": "haute",
            })

    # Décret Tertiaire
    surf_totale = surface * nb_sites
    if surf_totale >= SEUIL_DECRET_TERTIAIRE and any(s in secteurs for s in ["BAT"]):
        alertes_reglementaires.append({
            "type": "decret_tertiaire",
            "message": f"Surface {surf_totale:,.0f}m² ≥ 1000m² — Décret Tertiaire applicable (-40% en 2030)",
            "urgence": "info",
        })

    # COFRAC
    fiches_cofrac = [r for r in resultats if r.get("cofrac")]
    if fiches_cofrac:
        alertes_reglementaires.append({
            "type": "cofrac",
            "message": f"{len(fiches_cofrac)} fiche(s) avec contrôle COFRAC obligatoire (30% P6)",
            "urgence": "info",
        })

    # === RÉSULTAT FINAL ===
    return {
        "version": VERSION,
        "timestamp": now.isoformat(),

        # Identification
        "entreprise": {
            "siret": siret,
            "nom": entreprise.get("nom") if entreprise else None,
            "naf": naf,
            "departement": departement,
            "zone": zone,
            "nb_sites": nb_sites,
        },

        # Profil
        "profil": {
            "key": profil,
            "secteurs_cee": secteurs,
            "section_insee": section_activite,
        },

        # Résultats CEE
        "resultats": {
            "pack": resultats,
            "globaux": globaux,
            "nb_fiches": len(resultats),
            "zero_euro": sum(1 for r in resultats if r.get("coverage", 0) >= 100),
        },

        # Négociation
        "negociation": nego,

        # Closing
        "closing": closing,

        # Multi-site
        "multisite": multisite,

        # Confiance
        "confiance": confiance,

        # Réglementaire
        "alertes": alertes_reglementaires,

        # Prix
        "prix": {
            "classique_mwhc": round(PRIX_CUMAC * 1000, 2),
            "precarite_mwhc": round(PRIX_CUMAC_PRECARITE * 1000, 2),
            "utilise": "precarite" if precarite else "classique",
            "commission_rate": COMMISSION_RATE,
        },

        # Seuils P6
        "p6": P6_SEUILS,
    }


# ═══════════════════════════════════════════════
# RACCOURCIS
# ═══════════════════════════════════════════════

def diagnostic_siret(siret, **kwargs):
    """Diagnostic complet depuis un SIRET."""
    return diagnostic_complet(siret=siret, **kwargs)


def diagnostic_params(departement, surface, energie=None, naf=None, **kwargs):
    """Diagnostic complet depuis des paramètres manuels."""
    return diagnostic_complet(
        departement=departement, surface=surface,
        energie=energie, naf=naf, **kwargs
    )


def lister_acheteurs():
    """Liste tous les acheteurs CEE avec leurs conditions."""
    return {k: {
        "nom": v["nom"], "type": v["type"],
        "prix_classic": v["prix_classic_mwhc"],
        "prix_precarite": v["prix_precarite_mwhc"],
        "tolerance": v["tolerance"],
        "multisite": v["multisite"],
        "exige_cofrac": v["exige_cofrac"],
    } for k, v in ACHETEURS.items()}


def veille_reglementaire():
    """Retourne l'état réglementaire actuel."""
    fiches = load_fiches()
    deadlines = load_deadlines()
    now = datetime.now()

    actives = sum(1 for f in fiches if f.get("actif", True))
    abrogees = []
    a_venir = []

    for ref, dl in deadlines.items():
        try:
            deadline = datetime.strptime(dl, "%Y-%m-%d")
            if now >= deadline:
                abrogees.append({"ref": ref, "date": dl})
            elif (deadline - now).days <= 180:
                a_venir.append({"ref": ref, "date": dl, "jours": (deadline - now).days})
        except (ValueError, TypeError, KeyError):
            pass

    return {
        "version": VERSION,
        "fiches_actives": actives,
        "fiches_totales": len(fiches),
        "abrogees_count": len(abrogees),
        "abrogees": abrogees,
        "a_venir": a_venir,
        "prix_classique": PRIX_CUMAC * 1000,
        "prix_precarite": PRIX_CUMAC_PRECARITE * 1000,
        "p6_seuils": P6_SEUILS,
    }


# ═══════════════════════════════════════════════
# VALIDATEURS JURIDIQUES (DPE, QPV, Non-cumul, Double comptage)
# Source: Option C excellence — arrêté 4 sept 2014 modifié, P6
# ═══════════════════════════════════════════════

from dataclasses import dataclass, field as dc_field
from typing import List, Dict, Optional, Tuple

# Fiches abrogées (mises à jour depuis deadlines.json)
FICHES_ABROGEES = ["BAR-EQ-110", "BAT-EQ-127", "IND-BA-116",
                   "BAT-EQ-133", "BAT-TH-102", "BAR-TH-112"]

# Fiches exigeant DPE 2021+ (fiches BAT thermiques)
FICHES_EXIGENT_DPE2021 = [
    "BAT-TH-101", "BAT-TH-102", "BAT-TH-103", "BAT-TH-104",
    "BAT-TH-105", "BAT-TH-106", "BAT-TH-107", "BAT-TH-108",
    "BAT-TH-109", "BAT-TH-110", "BAT-TH-111", "BAT-TH-112",
    "BAT-TH-113", "BAT-TH-116", "BAT-TH-125", "BAT-TH-127",
    "BAT-TH-142", "BAT-TH-143", "BAT-TH-155", "BAT-TH-157",
]

# Règles de non-cumul entre types d'opérations
REGLES_NON_CUMUL = {
    ("OP", "OC"): "Même équipement: non cumul OP/OC",
    ("OC", "OP"): "Même équipement: non cumul OC/OP",
    ("OB", "OP"): "Même bâtiment: OB exclusif (rénovation globale)",
    ("OB", "OC"): "Même bâtiment: OB exclusif (rénovation globale)",
    ("OP", "OB"): "Même bâtiment: OP impossible si OB déjà déposé",
    ("OC", "OB"): "Même bâtiment: OC impossible si OB déjà déposé",
}

# Fiches mutuellement incompatibles (même poste)
FICHES_INCOMPATIBLES = {
    "BAT-TH-101": ["BAT-TH-102", "BAT-TH-103"],
    "BAT-TH-102": ["BAT-TH-101", "BAT-TH-103"],
    "BAT-TH-103": ["BAT-TH-101", "BAT-TH-102"],
    "BAT-TH-104": ["BAT-TH-105"],
    "BAT-TH-105": ["BAT-TH-104"],
    "BAT-TH-106": ["BAT-TH-107"],
    "BAT-TH-107": ["BAT-TH-106"],
    "BAR-TH-171": ["BAR-TH-172"],  # PAC air/air vs PAC air/eau
    "BAR-TH-172": ["BAR-TH-171"],
    "BAT-EN-101": ["BAT-EN-109"],   # Isolation combles vs toiture
    "BAT-EN-109": ["BAT-EN-101"],
}

# Période de carence double comptage (5 ans = durée de vie min)
PERIODE_CARENCE_JOURS = 5 * 365


def verifier_fiches_abrogees(fiches_refs):
    """Vérifie qu'aucune fiche sélectionnée n'est abrogée."""
    # Charger aussi les deadlines dynamiques
    dl = load_deadlines()
    now = datetime.now()
    abrogees = []
    for ref in fiches_refs:
        if ref in FICHES_ABROGEES:
            abrogees.append(ref)
        elif ref in dl:
            try:
                if now >= datetime.strptime(dl[ref], "%Y-%m-%d"):
                    abrogees.append(ref)
            except (ValueError, TypeError, KeyError):
                pass
    return abrogees


def verifier_non_cumul(fiches_refs):
    """Vérifie la compatibilité entre fiches sélectionnées.
    Retourne (ok, compatibles, incompatibles)."""
    incompatibles = []

    for i, f1 in enumerate(fiches_refs):
        for j, f2 in enumerate(fiches_refs):
            if i >= j:
                continue
            # Vérifier incompatibilité directe
            if f1 in FICHES_INCOMPATIBLES and f2 in FICHES_INCOMPATIBLES[f1]:
                incompatibles.append(
                    f"{f1} ↔ {f2}: Fiches incompatibles (même poste)"
                )

    compatibles = [f for f in fiches_refs
                   if not any(f in inc for inc in incompatibles)]
    return len(incompatibles) == 0, compatibles, incompatibles


def verifier_dpe_requis(fiches_refs, dpe_date=None):
    """Vérifie si un DPE 2021+ est requis et disponible.
    Retourne (ok, fiches_concernees, message)."""
    fiches_need = [f for f in fiches_refs if f in FICHES_EXIGENT_DPE2021]
    if not fiches_need:
        return True, [], "Aucune fiche ne requiert de DPE 2021+"

    if dpe_date is None:
        return False, fiches_need, f"DPE 2021+ obligatoire pour {len(fiches_need)} fiche(s)"

    if isinstance(dpe_date, str):
        try:
            dpe_date = datetime.strptime(dpe_date, "%Y-%m-%d")
        except (ValueError, TypeError, KeyError):
            return False, fiches_need, "Date DPE invalide"

    if dpe_date < datetime(2021, 7, 1):
        return False, fiches_need, f"DPE du {dpe_date.strftime('%d/%m/%Y')} antérieur au 01/07/2021"

    return True, fiches_need, f"DPE 2021+ valide ({dpe_date.strftime('%d/%m/%Y')})"


def verifier_remplacement_premature(fiche_ref, age_equipement_annees, fiches_db=None):
    """Vérifie la règle anti-remplacement prématuré (P6 renforcé).
    Âge doit être > 2/3 de la durée de vie conventionnelle."""
    if fiches_db is None:
        fiches_db = {f["ref"]: f for f in load_fiches()}

    fiche = fiches_db.get(fiche_ref)
    if not fiche:
        return True, None

    duree_vie = fiche.get("duree_vie")
    if not duree_vie or duree_vie <= 0:
        return True, None

    seuil = duree_vie * 2 / 3
    if age_equipement_annees < seuil:
        return False, (f"Remplacement prématuré: {age_equipement_annees} ans "
                       f"< {seuil:.0f} ans (2/3 de {duree_vie} ans)")
    return True, None


def valider_projet_complet(siret, adresse, surface, fiches_selectionnees,
                           dpe_date=None, date_travaux=None, energie=None):
    """Validation complète d'un projet CEE — tous les contrôles juridiques.

    Retourne un dict avec:
    - est_valide: bool
    - score_confiance: 0-100
    - erreurs: list (bloquants)
    - avertissements: list (non bloquants)
    - messages: list (confirmations)
    - non_cumul_valide: bool
    - fiches_abrogees: list
    - dpe_requis: dict
    - opportunites: list
    """
    erreurs = []
    avertissements = []
    messages = []
    opportunites = []
    score = 0

    # 1. Fiches abrogées
    abrogees = verifier_fiches_abrogees(fiches_selectionnees)
    if abrogees:
        erreurs.append(f"❌ FICHES ABROGÉES: {', '.join(abrogees)}")
    else:
        score += 15
        messages.append("✅ Aucune fiche abrogée")

    # 2. Non-cumul
    ok_nc, compatibles, incompatibles = verifier_non_cumul(fiches_selectionnees)
    if not ok_nc:
        for inc in incompatibles:
            erreurs.append(f"❌ NON-CUMUL: {inc}")
    else:
        score += 20
        messages.append("✅ Fiches compatibles (non-cumul respecté)")

    # 3. DPE 2021+
    ok_dpe, fiches_dpe, msg_dpe = verifier_dpe_requis(fiches_selectionnees, dpe_date)
    if fiches_dpe:
        if ok_dpe:
            score += 20
            messages.append(f"✅ {msg_dpe}")
        else:
            erreurs.append(f"❌ {msg_dpe}: {', '.join(fiches_dpe)}")

    # 4. Surface > 0
    if surface and surface > 0:
        score += 10
        messages.append(f"✅ Surface renseignée: {surface}m²")
    else:
        avertissements.append("⚠️ Surface non renseignée — calculs approximatifs")

    # 5. Énergie connue
    if energie:
        score += 10
        messages.append(f"✅ Énergie renseignée: {energie}")
        if energie in ("fioul", "gaz"):
            opportunites.append({
                "type": "sortie_fossile",
                "description": f"Chauffage {energie} → éligible Coup de Pouce P6",
                "impact": "Multiplicateur ×3 à ×5 sur certaines fiches",
            })
    else:
        avertissements.append("⚠️ Énergie non renseignée — Coup de Pouce P6 non calculable")

    # 6. SIRET vérifié
    if siret:
        score += 10
        messages.append(f"✅ SIRET: {siret}")

    # 7. Adresse vérifiée
    if adresse:
        score += 5

    # 8. Fiches avec COFRAC
    fiches_db = {f["ref"]: f for f in load_fiches()}
    fiches_cofrac = [f for f in fiches_selectionnees if fiches_db.get(f, {}).get("cofrac")]
    if fiches_cofrac:
        avertissements.append(
            f"🔍 {len(fiches_cofrac)} fiche(s) avec contrôle COFRAC obligatoire: "
            f"{', '.join(fiches_cofrac)}"
        )

    # 9. Deadlines proches
    for ref in fiches_selectionnees:
        dl_info = check_deadline(ref)
        if dl_info.get("status") == "attention":
            avertissements.append(
                f"⏰ {ref}: abrogation dans {dl_info['jours_restants']} jours — dépôt urgent"
            )

    # 10. Décret Tertiaire
    if surface and surface >= 1000:
        opportunites.append({
            "type": "decret_tertiaire",
            "description": f"Surface {surface}m² ≥ 1000m² — Décret Tertiaire applicable",
            "impact": "Obligation -40% en 2030 — les CEE financent la conformité",
        })

    score = min(100, score)
    est_valide = len(erreurs) == 0 and score >= 40

    return {
        "est_valide": est_valide,
        "score_confiance": score,
        "erreurs": erreurs,
        "avertissements": avertissements,
        "messages": messages,
        "non_cumul_valide": ok_nc,
        "fiches_abrogees": abrogees,
        "fiches_compatibles": compatibles,
        "fiches_incompatibles": incompatibles,
        "dpe_requis": {"ok": ok_dpe, "fiches": fiches_dpe, "message": msg_dpe},
        "opportunites": opportunites,
        "nb_fiches_cofrac": len(fiches_cofrac),
    }


# ═══════════════════════════════════════════════
# ALIASES (compatibilité imports anciens noms)
# ═══════════════════════════════════════════════

# Alias classe pour import style CEEProValidator
class CEEProValidator:
    """Wrapper classe pour valider_projet_complet (compatibilité)."""
    def __init__(self):
        pass

    def valider_projet(self, siret, adresse, surface, fiches, date_travaux=None):
        return valider_projet_complet(siret, adresse, surface, fiches,
                                      date_travaux=date_travaux)

class DPETertiaireConnector:
    """Recherche DPE tertiaire via l'API backend /dpe."""
    def rechercher_par_adresse(self, adresse):
        # En production, appeler /dpe endpoint
        return []

class QPVDetector:
    """Détection QPV — à implémenter via API géo.api.gouv.fr."""
    def detecter_par_coordonnees(self, lon, lat):
        return {"est_qpv": False, "multiplicateur": 1.0}
    def detecter_par_adresse(self, adresse):
        return {"est_qpv": False, "multiplicateur": 1.0}

class NonCumulManager:
    """Wrapper pour verifier_non_cumul."""
    def verifier_compatibilite(self, fiches):
        return verifier_non_cumul(fiches)

class DoubleComptageDetector:
    """Détection double comptage — basé sur historique SIRET."""
    PERIODE_CARENCE_JOURS = PERIODE_CARENCE_JOURS
    def verifier_historique(self, siret, fiches, date_travaux=None):
        # Pas d'historique local — toujours OK pour l'instant
        return True, []

# Alias fonction
valider_projet_cee = valider_projet_complet


# ═══════════════════════════════════════════════
# MAIN (test)
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        siret = sys.argv[1]
        print(f"\n  DIAGNOSTIC COMPLET — SIRET {siret}\n")
        result = diagnostic_siret(siret)
    else:
        print(f"\n  DIAGNOSTIC COMPLET — Commerce 968m² Auxerre\n")
        result = diagnostic_params("89", 968, "electricite", "47.11B")

    if "error" in result:
        print(f"  ERREUR: {result['error']}")
        sys.exit(1)

    e = result["entreprise"]
    p = result["profil"]
    r = result["resultats"]
    g = r["globaux"]
    c = result["closing"]
    n = result["negociation"]
    conf = result["confiance"]

    print(f"  Entreprise: {e.get('nom') or '?'} | NAF: {e['naf']} | Zone: {e['zone']}")
    print(f"  Profil: {p['key']} | Secteurs: {p['secteurs_cee']}")
    print(f"  Confiance: {conf['score']}/100")
    print()
    print(f"  RÉSULTATS CEE")
    print(f"  {r['nb_fiches']} fiches | {r['zero_euro']} opérations 0€")
    print(f"  Cumac: {g.get('total_cumac', 0):,} kWhc")
    print(f"  Prime nette: {g.get('total_prime_nette', 0):,.0f}€")
    print(f"  Couverture: {g.get('total_coverage', 0)}%")
    print()
    print(f"  CLOSING")
    print(f"  Score: {c['score']}/100 — {c['verdict']}")
    print(f"  Commission solo: {c['commissions']['solo_8pct']:,.0f}€")
    print()
    reco = n.get("recommandation")
    if reco:
        print(f"  ACHETEUR RECOMMANDÉ")
        print(f"  {reco['acheteur']} | {reco['prime_nette']:,.0f}€ | +{reco['gain_pct']}% vs pire")
    print()
    print(f"  ALERTES")
    for a in result["alertes"]:
        print(f"  [{a['urgence']}] {a['message']}")
    print()
