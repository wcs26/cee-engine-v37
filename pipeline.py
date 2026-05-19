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

    # V37.3.51 — Questions DÉDUPLIQUÉES en 1 appel global (vs boucle fiche-par-fiche).
    # AVANT : 234 fiches × 4 questions globales = 936 questions répétées (chauffage, surface, age, zone).
    # APRÈS : 1 appel à generate_smart_questions(all_fiches, contexte) → questions uniques + groupées par thème.
    fiches_db = {f["ref"]: f for f in load_fiches()}
    pack_data = resultats.get("pack", [])
    pack_fiches = [fiches_db.get(r["fiche"]) for r in pack_data if fiches_db.get(r["fiche"])]
    contexte_q = {
        "ape": state.get("naf") or state.get("ape", ""),
        "surface": surface,
        "energie": energie,
        "zone": state.get("zone", ""),
        "dpe_classe": state.get("dpe_classe", ""),
        "annee_construction": state.get("annee_construction"),
    }
    smart = generate_smart_questions(pack_fiches, contexte_q)
    state["questions"] = smart
    state["questions_structurees"] = smart.get("par_fiche", {})  # rétro-compat

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


# V39.1.4 — Mots-clés par thème (recherche dans le nom de la fiche en lowercase)
_THEME_KEYWORDS = {
    "isolation":            ["isolation", "isolant", "calorifug", "parois", "rideau"],
    "fenetres":             ["fenêtre", "fenetre", "porte-fenêtre", "vitrage", "pariétodynamique"],
    "chauffage":            ["chaudière", "chaudiere", "biomasse", "émetteur", "emetteur", "chauffe-bain"],
    "pac":                  ["pac ", "pompe à chaleur", "pompe a chaleur", "géothermique", "geothermique", "hybride"],
    "ecs":                  ["chauffe-eau", "ecs", "thermodynamique"],
    "solaire":              ["solaire", "pvt", "capteurs hybrides", "photovoltaïque"],
    "ventilation":          ["vmc", "ventilation", "double flux"],
    "climatisation":        ["clim", "climatiseur", "vrv", "multi-split"],
    "eclairage":            ["éclairage", "eclairage", "led", "luminaire", "lanterneau"],
    "froid":                ["frigo", "froid", "groupe de production", "fermeture meubles"],
    "moteur":               ["moteur", "variateur", "vev", "moto-variateur"],
    "air_comprime":         ["air comprimé", "air comprime", "compresseur", "séquenceur"],
    "regulation":           ["régulation", "regulation", "optimiseur", "robinet thermostatique", "sonde", "programmable"],
    "destratification":     ["destratifi", "déstratifi", "stratification"],
    "renovation_globale":   ["rénovation globale", "renovation globale", "rénovation d'ampleur", "ampleur"],
    "management_energetique": ["iso 50001", "management énergétique", "mesurage", "indicateurs énergétiques"],
    "recuperation_chaleur": ["récupér", "recuper", "chaleur fatale", "récup chaleur", "fumées"],
    "reseau_chaleur":       ["réseau de chaleur", "reseau de chaleur", "raccordement réseau", "raccordement reseau", "calorifug"],
    "cpe":                  ["cpe ", "contrat performance"],
    "monitoring":           ["affichage conso", "suivi conso", "monitoring"],
    "process_industrie":    ["four ", "brûleur", "bruleur", "haute pression", "transmission performant"],
    "transport":            ["pneus", "véhicule", "vehicule", "écoconduite", "ecoconduite", "automoteur", "fret", "navire", "bateau"],
}

# Sous-secteurs → thèmes implicites (fallback si le nom ne matche pas)
_SS_IMPLICIT = {
    "EN": {"isolation"},
    "TH": {"chauffage"},
    "CH": {"reseau_chaleur"},
    "EC": {"reseau_chaleur"},
    "BA": {"eclairage", "isolation"},
}


def classify_themes(fiches):
    """V39.1.4 — Détecte les thèmes présents dans la liste de fiches éligibles.
    Data-driven : utilise sous_secteur (data structurée) + mots-clés du nom.
    Retourne un set de thèmes.
    """
    themes = set()
    for f in fiches:
        if not isinstance(f, dict):
            continue
        nom_lc = (f.get("nom") or "").lower()
        ref = f.get("ref", "")
        ss = f.get("sous_secteur") or (ref.split("-")[1] if "-" in ref else "")

        # 1. Détection par mots-clés du nom (priorité)
        matched_kw = False
        for theme, keywords in _THEME_KEYWORDS.items():
            if any(kw in nom_lc for kw in keywords):
                themes.add(theme)
                matched_kw = True

        # 2. Fallback par sous_secteur si aucun mot-clé matché
        if not matched_kw and ss in _SS_IMPLICIT:
            themes |= _SS_IMPLICIT[ss]

    return themes


# V39.1.4 — Questions ciblées par thème
_THEME_QUESTIONS = {
    "isolation": [
        ("Le bâtiment a-t-il déjà été isolé (murs/toiture/plancher) ?", "Si oui, complément possible mais cumac réduit (épaisseur add'l)"),
        ("Y a-t-il un vide sanitaire accessible sous le bâtiment ?", "VS accessible = isolation plancher faisable (souvent 0€ reste à charge)"),
    ],
    "fenetres": [
        ("Quel type de vitrage actuel (simple/double/triple) ?", "Simple/double ancien → remplacement éligible"),
    ],
    "chauffage": [
        ("Quel âge a le système de chauffage actuel ?", "Chaudière >15 ans = remplacement éligible (coup de pouce possible)"),
    ],
    "pac": [
        ("Y a-t-il déjà une PAC installée ? Si oui, quel modèle/année ?", "Remplacement PAC <15 ans non éligible (règle 2/3 durée de vie)"),
    ],
    "ecs": [
        ("Quel est le mode de production ECS actuel (cumulus, chaudière, solaire) ?", "ECS électrique → chauffe-eau thermodynamique = gain massif"),
    ],
    "solaire": [
        ("L'orientation et la pente de toiture permettent-elles un solaire (S/SE/SO, ≥20°) ?", "Mauvaise orientation = cumac réduit voire fiche non éligible"),
        ("Le bâtiment est-il en zone classée monuments historiques ?", "Si oui, capteurs solaires généralement interdits"),
    ],
    "ventilation": [
        ("Y a-t-il une VMC installée ? Simple flux ou double flux ?", "Pas de VMC ou SF → DF avec récupération chaleur = gain confort + cumac"),
    ],
    "climatisation": [
        ("Quel mode de climatisation actuel (split, VRV, centrale) ?", "Clim ancienne = remplacement éligible si COP/SCOP < seuil"),
    ],
    "eclairage": [
        ("L'éclairage est-il déjà en LED ou encore en néon/halogène/fluorescent ?", "Non-LED → LED tertiaire = ROI rapide, souvent 0€"),
        ("Combien de points lumineux environ ?", "Volume = clé du calcul cumac"),
    ],
    "froid": [
        ("Les meubles frigorifiques sont-ils ouverts ou fermés (avec portes) ?", "Ouverts → installation portes = économie 40-60% (fiche BAT-EQ-124/125)"),
        ("Type de fluide frigorigène utilisé (HFC, CO2, NH3) ?", "Migration HFC → CO2 sub/trans-critique = éligible BAT-EQ-117"),
    ],
    "moteur": [
        ("Combien de moteurs/compresseurs sur le site et quelle puissance moyenne ?", "Variateur de vitesse (VEV) sur moteur >7kW = ROI rapide"),
        ("Les moteurs actuels sont-ils en classe IE3/IE4 ou plus anciens (IE1/IE2) ?", "Remplacement IE1/IE2 → IE4 = éligible IND-UT-132"),
    ],
    "air_comprime": [
        ("Y a-t-il un réseau d'air comprimé ? Quelle puissance compresseurs ?", "Air comprimé = 10-30% facture industrie → multiples fiches"),
        ("Détection de fuites déjà réalisée dans les 12 derniers mois ?", "Fuites représentent 20-30% conso air comprimé"),
    ],
    "regulation": [
        ("Le système de chauffage a-t-il une régulation centralisée existante ?", "Pas de régulation = robinet thermostatique + sonde extérieure souvent gratuits"),
    ],
    "destratification": [
        ("Le bâtiment a-t-il des plafonds hauts (>4m) ?", "Plafond haut = déstratificateur d'air souvent à 0€"),
    ],
    "renovation_globale": [
        ("Combien de logements concernés et année de construction ?", "Rénovation globale = cumac très élevé (4000+ €/logement)"),
        ("DPE actuel et DPE visé après travaux ?", "Saut ≥2 classes = bonification BAR-TH-174/175"),
    ],
    "management_energetique": [
        ("L'entreprise a-t-elle déjà une démarche ISO 50001 ou un système de mesurage ?", "Pas de SME = ISO 50001 éligible (7000+ €/site, IND-UT-101)"),
    ],
    "recuperation_chaleur": [
        ("Y a-t-il des sources de chaleur fatale identifiées (process, fumées, compresseurs) ?", "Chaleur fatale = gisement majeur pour récupération"),
    ],
    "reseau_chaleur": [
        ("Le bâtiment est-il à proximité d'un réseau de chaleur urbain (≤200m) ?", "Raccordement éligible si réseau EnR&R (RES-CH-101)"),
    ],
    "cpe": [
        ("L'entreprise est-elle ouverte à un Contrat de Performance Énergétique ?", "CPE = prestation pluri-annuelle, cumac élevé"),
    ],
    "monitoring": [
        ("Suivi conso énergétique en place (compteurs, logiciel) ?", "Pas de monitoring = mise en place éligible"),
    ],
    "process_industrie": [
        ("Type de process industriel principal (four, brûleur, chaudière) et puissance ?", "Process haute température = nombreuses fiches IND-UT"),
    ],
    "transport": [
        ("Taille de flotte (poids lourds / véhicules légers) ?", "Flotte importante = formation écoconduite + suivi conso = cumac vol."),
    ],
}


# V39.3.0 — Questions précises par fiche selon vraies variables compute
_PARAM_LABEL = {
    "surface":         ("Surface (m²)", "nombre", "m²"),
    "puissance":       ("Puissance installée (kW)", "nombre", "kW"),
    "puissance_froid": ("Puissance frigorifique (kW)", "nombre", "kW"),
    "quantite":        ("Nombre d'unités", "nombre", "unités"),
    "nb_logements":    ("Nombre de logements", "nombre", "logements"),
    "longueur":        ("Longueur installée (m)", "nombre", "m"),
    "debit":           ("Débit (m³/h)", "nombre", "m³/h"),
    "rendement":       ("Rendement (%)", "nombre", "%"),
    "temperature":     ("Température (°C)", "nombre", "°C"),
    "application":     ("Application", "choix", ""),
    "type":            ("Type d'usage", "choix", ""),
    "efficacite":      ("Classe efficacité (COP/ηs)", "choix", ""),
    "classe":          ("Classe énergétique", "choix", ""),
    "mode":            ("Mode de fonctionnement", "choix", ""),
    "zone":            ("Zone d'application", "choix", ""),
    # V39.3.1 — variables pour fiches activées avec formules ADEME
    "secteur":         ("Secteur d'activité", "choix", ""),
    "branche":         ("Branche d'activité", "choix", ""),
    "dn":              ("Diamètre nominal canalisation (mm)", "nombre", "mm"),
    "type_eau":        ("Type fluide (eau chaude / surchauffée / vapeur)", "choix", ""),
    "delta_t":         ("Gain température consigne (°C)", "nombre", "°C"),
    "q_kwh":           ("Énergie thermique annuelle Q (kWh/an)", "nombre", "kWh/an"),
    "e_elec_kwh":      ("Énergie électrique absorbée (kWh/an)", "nombre", "kWh/an"),
    "d_heures":        ("Durée annuelle fonctionnement (h)", "nombre", "h/an"),
    "p_recup":         ("Puissance récupérée fluide caloporteur (kW)", "nombre", "kW"),
    "p_conso":         ("Puissance électrique auxiliaires (kW)", "nombre", "kW"),
    "capacite_kwh":    ("Capacité maximale stockage (kWh)", "nombre", "kWh"),
    "nb_cycles":       ("Nombre annuel de cycles équivalents", "nombre", "cycles"),
    "n_a":             ("Nombre pneus classe A", "nombre", "pneus"),
    "n_b":             ("Nombre pneus classe B", "nombre", "pneus"),
    "n_c":             ("Nombre pneus classe C", "nombre", "pneus"),
    "y_km":            ("Kilométrage annuel moyen par véhicule", "nombre", "km/an"),
}


def build_questions_for_fiche(fiche, connu):
    """V39.3.0 — Génère les questions PRÉCISES pour calculer cumac d'1 fiche.

    Lit fiche.params + fiche.mode_calcul + fiche.variables + fiche.table_cumac
    et produit les questions exactement nécessaires au compute (numérique ou choix
    parmi liste finie pour les fiches complexes table_str/table_2d).
    """
    questions = []
    ref = fiche.get("ref", "")
    nom_short = (fiche.get("nom") or "")[:40]
    ftype = fiche.get("type", "")
    mode = fiche.get("mode_calcul", "")
    variables = fiche.get("variables", []) or []
    params = fiche.get("params", []) or []
    table = fiche.get("table_cumac", {})

    def add_q(param_name, label, qtype, unite="", choices=None, impact=""):
        questions.append({
            "question": f"[{ref}] {label}",
            "type": qtype,
            "unite": unite,
            "param": param_name,
            "choices": choices,
            "fiche_nom": nom_short,
            "impact": impact or f"Calcul cumac {ref}",
        })

    # === Cas 1 : type surface simple (50 fiches) ===
    if ftype == "surface" and not mode:
        if "surface" not in connu:
            ratio = fiche.get("surface_ratio")
            if ratio and 0 < ratio < 1:
                add_q("surface", f"Surface bâtiment (m²) — ratio {int(ratio*100)}% appliqué pour cette fiche", "nombre", "m²",
                      impact=f"Ex: 1000m² × {int(ratio*100)}% = {int(1000*ratio)}m² éligibles")
            else:
                add_q("surface", "Surface concernée (m²)", "nombre", "m²")
        return questions

    # === Cas 2 : type unitaire simple (140 fiches) ===
    if ftype == "unitaire" and not mode:
        for p in params:
            if p == "surface" and "surface" in connu:
                continue
            label, qtype, unite = _PARAM_LABEL.get(p, (p.capitalize(), "nombre", ""))
            add_q(p, label, qtype, unite)
        return questions

    # === Cas 3 : type complexe — mode table_str (10 fiches) ===
    # User doit choisir 1 application dans la liste + éventuellement quantité
    if mode == "table_str":
        if variables:
            key_var = variables[0]
            choices = list(table.keys()) if isinstance(table, dict) else []
            add_q(key_var, f"Quelle application ? (choix exact pour valeur cumac)",
                  "choix", "", choices=choices,
                  impact=f"{len(choices)} options possibles — cumac varie de {min((v for v in table.values() if isinstance(v,(int,float))), default=0)} à {max((v for v in table.values() if isinstance(v,(int,float))), default=0)} kWhc/unité")
            # Param mult (puissance/quantite)
            for p in params:
                if p != key_var:
                    label, qtype, unite = _PARAM_LABEL.get(p, (p.capitalize(), "nombre", ""))
                    add_q(p, label, qtype, unite)
        return questions

    # === Cas 4 : type complexe — mode table_2d (4 fiches) ===
    if mode == "table_2d":
        if len(variables) >= 2:
            v1, v2 = variables[0], variables[1]
            # Choix sur clé1
            choices1 = list(table.keys()) if isinstance(table, dict) else []
            label1, _, _ = _PARAM_LABEL.get(v1, (v1.capitalize(), "choix", ""))
            add_q(v1, label1, "choix", "", choices=choices1)
            # Choix sur clé2 (depuis 1ère valeur de table)
            choices2 = []
            if choices1 and isinstance(table.get(choices1[0]), dict):
                choices2 = list(table[choices1[0]].keys())
            label2, _, _ = _PARAM_LABEL.get(v2, (v2.capitalize(), "choix", ""))
            add_q(v2, label2, "choix", "", choices=choices2)
            # Mult var si présent (3ème variable)
            if len(variables) > 2:
                m = variables[2]
                label3, qtype, unite = _PARAM_LABEL.get(m, (m.capitalize(), "nombre", ""))
                add_q(m, label3, qtype, unite)
        return questions

    # === Cas 5 : type complexe — formule_tranches (4 fiches) ===
    if mode == "formule_tranches":
        if variables:
            var = variables[0]
            label, qtype, unite = _PARAM_LABEL.get(var, (var.capitalize(), "nombre", ""))
            tranches = fiche.get("tranches", [])
            tr_descr = " | ".join(f"{t.get('min',0)}-{t.get('max','∞')}: {t.get('a',0)}×{var}+{t.get('b',0)}" for t in tranches[:3])
            add_q(var, f"{label} (formule par tranche)", qtype, unite,
                  impact=f"Tranches: {tr_descr}")
        return questions

    # === Cas 6 : type complexe — mode formule (eval avec multi-variables) ===
    if mode == "formule":
        for v in variables:
            label, qtype, unite = _PARAM_LABEL.get(v, (v.capitalize().replace('_',' '), "nombre", ""))
            add_q(v, label, qtype, unite)
        return questions

    # === Cas 7 : type complexe — table legacy (1 fiche) ===
    if mode == "table":
        if variables:
            key_var = variables[0]
            mult_var = variables[1] if len(variables) > 1 else None
            label, qtype, unite = _PARAM_LABEL.get(key_var, (key_var.capitalize(), "nombre", ""))
            add_q(key_var, f"{label} (lookup table)", qtype, unite)
            if mult_var:
                label_m, qt_m, u_m = _PARAM_LABEL.get(mult_var, (mult_var.capitalize(), "nombre", ""))
                add_q(mult_var, label_m, qt_m, u_m)
        return questions

    # === Fallback : juste params (compatibilité) ===
    for p in params:
        if p == "surface" and "surface" in connu:
            continue
        label, qtype, unite = _PARAM_LABEL.get(p, (p.capitalize(), "nombre", ""))
        add_q(p, label, qtype, unite)
    return questions


def build_par_theme(themes_detectes, fiches, connu):
    """V39.1.4 — Génère les questions par thème détecté.
    Filtre les questions devenues inutiles selon contexte connu.
    """
    par_theme = {}
    for theme in themes_detectes:
        questions = _THEME_QUESTIONS.get(theme, [])
        if not questions:
            continue
        # Filtres : éviter de poser des questions sur des trucs déjà connus
        if theme == "chauffage" and "energie" in connu:
            # On sait déjà l'énergie, mais on peut quand même demander l'âge
            pass
        par_theme[theme] = [
            {"question": q, "impact": impact}
            for q, impact in questions
        ]
    return par_theme


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

    # V39.1.4 — Détection thèmes DATA-DRIVEN (sous_secteur + mots-clés nom)
    # Avant : hardcodé sur refs EN-101/TH-104/EQ-125... ratait 90% du catalogue.
    # Après : classification déduite de la sémantique structurée + nom.
    themes_detectes = classify_themes(fiches)

    # Questions par thème : 1-2 questions ciblées par thème détecté
    par_theme = build_par_theme(themes_detectes, fiches, connu)

    # Questions spécifiques par fiche — V39.1.2 FIX: data-driven via fiche.params
    # (au lieu de chercher des mots dans conditions_texte qui ratait 90% des cas)
    PARAM_QUESTIONS = {
        "puissance":       ("Puissance installée (kW) ?", "nombre", "kW"),
        "puissance_froid": ("Puissance frigorifique (kW) ?", "nombre", "kW"),
        "quantite":        ("Nombre d'unités ?", "nombre", "unités"),
        "nb_logements":    ("Nombre de logements ?", "nombre", "logements"),
        "longueur":        ("Longueur installée (m) ?", "nombre", "m"),
        "debit":           ("Débit (m³/h) ?", "nombre", "m³/h"),
        "rendement":       ("Rendement de l'installation (%) ?", "nombre", "%"),
    }
    # V39.3.0 — questions précises selon vraies variables compute (params + mode_calcul + variables)
    par_fiche = {}
    for f in fiches:
        if not isinstance(f, dict): continue
        ref = f.get("ref", "")
        if not ref or ref in par_fiche: continue
        questions = build_questions_for_fiche(f, connu)
        if questions:
            par_fiche[ref] = questions

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
