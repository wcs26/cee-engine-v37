"""
PIPELINE CEE CONVERSATIONNEL - WCS Pro
INPUT → détection → QUESTIONS → enrichissement → recalcul → closing
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from auto_detect import (
    get_sirene, get_siret, deduce_usage,
    resolve_surface, resolve_energie,
    detect_gisements, prioriser_gisements,
    moteur_expert, generate_questions,
    estimate_surface_from_naf,
)
from moteur_cee_master import get_zone, load_fiches
from config import PRIX_CUMAC


def run_pipeline(siret=None, params_manuels=None):
    """
    Pipeline conversationnel complet.
    Retourne un dict avec état, résultats, questions en attente.
    """
    state = {
        "etape": "input",
        "entreprise": None,
        "params": {},
        "gisements": [],
        "resultats": None,
        "questions_pending": [],
        "closing": None,
    }

    # =============================
    # ETAPE 1: INPUT (SIRET ou manuel)
    # =============================

    if siret:
        siret_clean = siret.replace(" ", "")
        if len(siret_clean) == 14:
            entreprise = get_siret(siret_clean)
        elif len(siret_clean) == 9:
            entreprise = get_sirene(siret_clean)
        else:
            return {"error": "SIRET/SIREN invalide"}

        if not entreprise:
            return {"error": "Entreprise non trouvée"}

        state["entreprise"] = entreprise

    elif params_manuels:
        state["entreprise"] = {
            "naf": params_manuels.get("naf", ""),
            "nom": params_manuels.get("nom", ""),
            "departement": params_manuels.get("departement", ""),
        }
    else:
        return {"error": "siret ou params_manuels requis"}

    entreprise = state["entreprise"]
    naf = entreprise.get("naf", "")
    dep = entreprise.get("departement", "")

    zone = get_zone(dep)
    if not zone:
        return {"error": f"Département {dep} inconnu"}

    # =============================
    # ETAPE 2: DETECTION AUTO
    # =============================

    state["etape"] = "detection"

    # Surface
    bdnb = None  # TODO: appel BDNB si adresse dispo
    surface, src_surface = resolve_surface(entreprise, bdnb)
    if src_surface != "BDNB":
        s_min, s_max = estimate_surface_from_naf(naf)
        surface = int((s_min + s_max) / 2)
        src_surface = "ESTIMATION_NAF"

    # Energie
    energie, src_energie = resolve_energie(bdnb, naf)

    state["params"] = {
        "departement": dep,
        "zone": zone,
        "surface": surface,
        "surface_source": src_surface,
        "energie": energie,
        "energie_source": src_energie,
        "naf": naf,
        "usage": deduce_usage(naf),
    }

    # Gisements
    gisements = detect_gisements(entreprise, surface, energie)
    gisements = prioriser_gisements(gisements, surface)
    state["gisements"] = gisements

    # =============================
    # ETAPE 3: QUESTIONS
    # =============================

    state["etape"] = "questions"

    questions = []

    # Surface estimée → demander confirmation
    if src_surface != "BDNB":
        questions.append({
            "id": "surface",
            "question": f"Surface estimée à {surface} m². Quelle est la surface réelle ?",
            "type": "number",
            "default": surface,
        })

    # Énergie estimée → demander confirmation
    if src_energie != "BDNB":
        questions.append({
            "id": "energie",
            "question": f"Énergie de chauffage estimée : {energie}. Confirmer ?",
            "type": "choice",
            "options": ["electricite", "gaz", "fioul"],
            "default": energie,
        })

    # Quantités selon gisements
    for g in gisements[:3]:  # Top 3
        if g["type"] == "eclairage":
            questions.append({
                "id": "nb_luminaires",
                "question": "Combien de points lumineux environ ?",
                "type": "number",
                "default": None,
            })
        elif g["type"] in ["air_comprime", "moteurs"]:
            questions.append({
                "id": "puissance",
                "question": "Puissance installée (kW) ?",
                "type": "number",
                "default": None,
            })

    # Fiches complexes
    fiches_db = {f["ref"]: f for f in load_fiches()}
    for g in gisements:
        for ref in g["fiches"]:
            fiche = fiches_db.get(ref)
            if fiche and fiche.get("type") == "complexe":
                for q in generate_questions(fiche):
                    questions.append({
                        "id": f"complex_{ref}",
                        "question": q,
                        "type": "number",
                        "fiche": ref,
                    })

    state["questions_pending"] = questions

    # =============================
    # ETAPE 4: CALCUL (avec estimations)
    # =============================

    state["etape"] = "calcul"

    resultats = moteur_expert(
        entreprise=entreprise,
        surface=surface,
        energie=energie,
        departement=dep,
    )
    state["resultats"] = resultats

    # Questions audit terrain
    contexte = {"age_batiment": 15}
    state["audit_questions"] = enrichir_audit(resultats, contexte)

    # Questions structurées par phase pour chaque fiche du pack
    fiches_db = {f["ref"]: f for f in load_fiches()}
    pack = resultats.get("pack", [])
    questions_par_fiche = {}
    for r in pack:
        fiche = fiches_db.get(r["fiche"])
        if fiche:
            questions_par_fiche[r["fiche"]] = generate_full_questions(fiche)
    state["questions_structurees"] = questions_par_fiche

    # =============================
    # ETAPE 5: CLOSING
    # =============================

    state["etape"] = "closing"

    pack = resultats.get("pack", [])
    total = resultats.get("total_prime", 0)

    if total > 2000:
        closing = "CHAUD"
        action = "Proposer RDV technique immédiat"
    elif total > 500:
        closing = "TIEDE"
        action = "Envoyer simulation par mail + relance J+2"
    else:
        closing = "FROID"
        action = "Nurturing — envoyer doc CEE générique"

    state["closing"] = {
        "temperature": closing,
        "action": action,
        "total_prime": total,
        "nb_actions": len(pack),
        "message": resultats.get("summary", ""),
    }

    return state


def generate_full_questions(fiche):
    """OBSOLÈTE — Remplacé par generate_smart_questions(fiches, contexte).
    Conservé pour rétro-compatibilité API."""
    return generate_smart_questions([fiche], {}).get("par_fiche", {}).get(fiche.get("ref", ""), {})


def generate_smart_questions(fiches, contexte):
    """Système de questions intelligent V37.

    Principes :
      1. Ne JAMAIS poser une question dont la réponse est déjà connue (SIRET→APE, surface saisie, DPE)
      2. Regrouper par THÈME (chauffage/isolation/éclairage/froid) pas par fiche
      3. Questions closing = 1 seule fois à la fin
      4. Multi-bâtiment = uniquement si multisite détecté
      5. Prédictif : si le moteur est SÛR → pré-remplir au lieu de poser

    Args:
      fiches: liste des fiches éligibles (résultat moteur)
      contexte: dict avec les infos déjà connues {ape, surface, energie, zone, dpe_classe, ...}

    Returns:
      dict structuré {globales:[], par_theme:{}, par_fiche:{}, closing:[]}
    """
    connu = set()
    if contexte.get("ape"): connu.add("activite")
    if contexte.get("surface") and contexte["surface"] > 0: connu.add("surface")
    if contexte.get("energie"): connu.add("energie")
    if contexte.get("zone"): connu.add("zone")
    if contexte.get("dpe_classe"): connu.add("dpe")
    if contexte.get("annee_construction"): connu.add("age")

    # Questions globales — seulement si pas déjà connu
    globales = []
    if "energie" not in connu:
        globales.append({"id": "energie", "question": "Quel est le mode de chauffage principal ? (gaz, fioul, électrique, réseau de chaleur, autre)", "impact": "Détermine éligibilité Coup de Pouce et fiches de remplacement chaudière", "obligatoire": True})
    if "age" not in connu:
        globales.append({"id": "annee_construction", "question": "Quelle est l'année de construction approximative du bâtiment ?", "impact": "Bâtiment pré-1986 = potentiel isolation élevé", "obligatoire": False})

    # Détection des thèmes présents dans les fiches éligibles
    themes_detectes = set()
    for f in fiches:
        ref = f.get("ref", "") if isinstance(f, dict) else ""
        conditions = " ".join(f.get("conditions_texte", [])).lower() if isinstance(f, dict) else ""
        if any(k in ref for k in ["EN-101", "EN-102", "EN-103", "EN-104"]): themes_detectes.add("isolation")
        if any(k in ref for k in ["TH-102", "TH-103", "TH-104", "TH-113", "TH-127"]): themes_detectes.add("chauffage")
        if any(k in ref for k in ["TH-125", "TH-126"]): themes_detectes.add("ventilation")
        if any(k in ref for k in ["EQ-111", "EQ-117", "EQ-125", "EQ-127"]): themes_detectes.add("eclairage_froid")
        if any(k in ref for k in ["TH-142", "BA-110"]): themes_detectes.add("destratification")
        if "compresseur" in conditions or "moteur" in conditions: themes_detectes.add("process")

    # Questions par thème (1 question clé par thème, jamais répétée)
    par_theme = {}
    if "isolation" in themes_detectes:
        par_theme["isolation"] = [
            {"question": "Le bâtiment a-t-il déjà été isolé (murs, toiture, plancher) ?", "impact": "Si déjà isolé → complément d'isolation possible mais cumac réduit"},
            {"question": "Y a-t-il un vide sanitaire accessible sous le bâtiment ?", "impact": "VS accessible = BAT-EN-103 faisable (0€ fréquent)"},
        ]
    if "chauffage" in themes_detectes and "energie" not in connu:
        par_theme["chauffage"] = [
            {"question": "Quel âge a la chaudière/système de chauffage actuel ?", "impact": "Chaudière >15 ans = remplacement éligible CEE"},
        ]
    if "eclairage_froid" in themes_detectes:
        par_theme["eclairage_froid"] = [
            {"question": "L'éclairage est-il en LED ou encore en néon/fluorescent ?", "impact": "Néon → LED = BAT-EQ-111 (souvent 0€)"},
        ]
        if any("EQ-125" in (f.get("ref","") if isinstance(f,dict) else "") for f in fiches):
            par_theme["eclairage_froid"].append(
                {"question": "Les meubles frigos sont-ils ouverts ou fermés ?", "impact": "Ouverts → fermeture = BAT-EQ-125 (économie énergie majeure)"}
            )
    if "ventilation" in themes_detectes:
        par_theme["ventilation"] = [
            {"question": "Y a-t-il une VMC installée ? Simple flux ou double flux ?", "impact": "Pas de VMC ou SF → DF = BAT-TH-126 (récupération chaleur)"},
        ]
    if "destratification" in themes_detectes:
        par_theme["destratification"] = [
            {"question": "Le bâtiment a-t-il des plafonds hauts (>4m) ?", "impact": "Plafond haut = déstratificateur d'air souvent à 0€"},
        ]
    if "process" in themes_detectes:
        par_theme["process"] = [
            {"question": "Combien de compresseurs / moteurs électriques sur le site ?", "impact": "Variateurs de vitesse = IND-UT-102 (ROI rapide)"},
        ]

    # Questions spécifiques par fiche (uniquement les fiches complexes qui NÉCESSITENT une réponse client)
    par_fiche = {}
    for f in fiches:
        if not isinstance(f, dict): continue
        ref = f.get("ref", "")
        conditions = " ".join(f.get("conditions_texte", [])).lower()
        fiche_qs = []
        if "puissance" in conditions and ref not in par_fiche:
            fiche_qs.append({"question": f"Puissance installée pour {ref} (kW) ?", "type": "nombre", "unite": "kW"})
        if fiche_qs:
            par_fiche[ref] = fiche_qs

    # Closing — 1 seule fois, à la fin
    closing = [
        {"question": "Avez-vous déjà engagé une demande CEE sur ce bâtiment avec un autre prestataire ?", "impact": "Non-cumul obligatoire — si oui, dossier bloqué (art. 441-7 Code pénal)"},
        {"question": "Si la prime couvre 100% des travaux (0€ reste à charge), souhaitez-vous planifier une visite technique ?", "impact": "Closing direct — grammaire Maestro : 'On valide qu'on passe à la VT'"},
    ]

    total = len(globales) + sum(len(v) for v in par_theme.values()) + len(closing)

    return {
        "total_questions": total,
        "questions_evitees": len(connu),
        "infos_deja_connues": list(connu),
        "globales": globales,
        "par_theme": par_theme,
        "themes_detectes": sorted(themes_detectes),
        "par_fiche": par_fiche,
        "closing": closing,
    }


def enrichir_audit(resultats, contexte):
    """Génère des questions terrain intelligentes — V37 refonte."""
    pack = resultats.get("pack", [])
    return generate_smart_questions(pack, contexte)


def recalculer(state, reponses):
    """
    Recalcule après réponses du client.
    reponses = {"surface": 800, "energie": "gaz", "puissance": 50, ...}
    """
    params = state["params"]

    if "surface" in reponses:
        params["surface"] = float(reponses["surface"])
        params["surface_source"] = "CLIENT"

    if "energie" in reponses:
        params["energie"] = reponses["energie"]
        params["energie_source"] = "CLIENT"

    resultats = moteur_expert(
        entreprise=state["entreprise"],
        surface=params["surface"],
        energie=params["energie"],
        departement=params["departement"],
    )

    state["resultats"] = resultats
    state["questions_pending"] = []
    state["etape"] = "closing"

    total = resultats.get("total_prime", 0)
    pack = resultats.get("pack", [])

    if total > 2000:
        closing = "CHAUD"
        action = "Proposer RDV technique immédiat"
    elif total > 500:
        closing = "TIEDE"
        action = "Envoyer simulation par mail + relance J+2"
    else:
        closing = "FROID"
        action = "Nurturing — envoyer doc CEE générique"

    state["closing"] = {
        "temperature": closing,
        "action": action,
        "total_prime": total,
        "nb_actions": len(pack),
        "message": resultats.get("summary", ""),
    }

    return state


# =============================
# MAIN (démo interactive)
# =============================

def main():
    print("\n===== PIPELINE CEE =====\n")

    siret = input("  SIRET (ou vide pour manuel): ").strip()

    if siret:
        state = run_pipeline(siret=siret)
    else:
        naf = input("  Code NAF: ").strip()
        dep = input("  Département: ").strip()
        state = run_pipeline(params_manuels={"naf": naf, "departement": dep})

    if "error" in state:
        print(f"\n  ERREUR: {state['error']}")
        return

    # Afficher détection
    params = state["params"]
    print(f"\n  Usage: {params['usage']}")
    print(f"  Surface: {params['surface']} m² ({params['surface_source']})")
    print(f"  Énergie: {params['energie']} ({params['energie_source']})")
    print(f"  Gisements: {len(state['gisements'])}")

    # Questions
    if state["questions_pending"]:
        print(f"\n  QUESTIONS ({len(state['questions_pending'])})")
        reponses = {}
        for q in state["questions_pending"]:
            rep = input(f"  {q['question']} ").strip()
            if rep:
                reponses[q["id"]] = rep

        if reponses:
            state = recalculer(state, reponses)

    # Résultats
    resultats = state["resultats"]
    if resultats:
        print(resultats.get("summary", ""))

    # Closing
    closing = state["closing"]
    print(f"\n  CLOSING: {closing['temperature']}")
    print(f"  ACTION: {closing['action']}")


if __name__ == "__main__":
    main()
