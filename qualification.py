"""
Trame de qualification téléphonique CEE — héritage GET1TECH 2021 (ENOPTEA→G1T).

Objectif : 4 minutes au téléphone pour pré-qualifier un prospect CEE
(personne morale uniquement) et déclencher RDV de visite technique.

8 questions techniques + 3 sondages → décision éligible/non éligible.

Exposé via /script/qualification (JSON) — utilisable par UI, chatbot WhatsApp,
script vendeur, ou simulateur formation.
"""

from flask import jsonify, request


TRAME_QUALIFICATION = {
    "version": "G1T-V2026",
    "duree_max_minutes": 4,
    "cible": "Personne morale (entreprise, copro, collectivité, bailleur, association)",
    "etapes": [
        {"n": 1,  "phase": "ouverture",     "titre": "Prise de contact",
         "script": "Rappel 1ʳᵉ opération, interlocuteur d'origine, satisfaction courtage."},
        {"n": 2,  "phase": "ouverture",     "titre": "But de l'appel",
         "script": "Annoncer la suite : « Dans le cadre du dispositif CEE 2026, "
                   "vous êtes classé bâtiment FAVORISÉ → étude éligibilité gratuite. »"},
        {"n": 3,  "phase": "credibilite",   "titre": "Que fait le BE",
         "script": "« Notre BE est en charge de la distribution des subventions CEE "
                   "pour le secteur tertiaire (P6 2026-2030). »"},
        {"n": 4,  "phase": "credibilite",   "titre": "Pourquoi ces subventions",
         "script": "Décret tertiaire : -40 % CO₂ en 2030, -50 % en 2040, -60 % en 2050. "
                   "L'État impose, finance via les obligés énergie (TotalEnergies, EDF…)."},
        {"n": 5,  "phase": "valeur",        "titre": "En quoi c'est profitable",
         "script": "Travaux subventionnés jusqu'à 100 % (selon fiche), SANS dépense, "
                   "SANS avance de frais. Économies facture 15-25 %."},
        {"n": 6,  "phase": "valeur",        "titre": "Montant indicatif",
         "script": "Selon le bâtiment éligible : de 5 000 € à plusieurs centaines de "
                   "milliers d'euros (ex AHBFC, isolation industrielle…). "
                   "À chiffrer après vérification technique."},
        {"n": 7,  "phase": "valeur",        "titre": "Autres avantages",
         "script": "Conformité décret tertiaire / image éco-responsable / "
                   "valorisation patrimoine / bonus réversion CEE/m²."},
        {"n": 8,  "phase": "qualification", "titre": "Comment savoir si éligible",
         "script": "Conditions UNIQUEMENT TECHNIQUES (pas de revenu, pas de score "
                   "social pour PRO). Je vous pose 8 questions, 4 minutes."},
        {"n": 9,  "phase": "qualification", "titre": "Rôle du coordinateur",
         "script": "Accompagner A→Z. 8 questions techniques + 3 sondages → "
                   "décision éligibilité, RDV BE si plusieurs bâtiments."},
        {"n": 10, "phase": "engagement",    "titre": "Calendrier",
         "script": "RDV 24-48h pour réponse éligibilité après passage BE."},
        {"n": 11, "phase": "engagement",    "titre": "Coordonnées",
         "script": "Email pro, mobile direct, SIREN. Mail de présentation + récap immédiat."},
        {"n": 12, "phase": "engagement",    "titre": "(saut volontaire — anti-script)",
         "script": "Laisser un silence calme avant la décision. Le silence vaut « oui »."},
        {"n": 13, "phase": "decision",      "titre": "Préparer le prochain appel",
         "script": "DEUX options claires :\n"
                   "  A) NON éligible → « Vous aurez essayé, on garde votre dossier. »\n"
                   "  B) ÉLIGIBLE → 1ʳᵉ sub déplacement métreur + estimation économies "
                   "+ bonus réversion CEE/m² + signature convention en ligne."},
        {"n": 14, "phase": "cloture",       "titre": "Étape de clôture",
         "script": "Récap : bâtiment activité prioritaire / postes éligibles / "
                   "prise en charge totale sans avance / économie immédiate / "
                   "réversion € ou audit DPE / RDV suivant call2.\n"
                   "Remercier (« bouquet de fleurs »), prise de congé."},
        {"n": 15, "phase": "interne",       "titre": "Mail présentation immédiat",
         "script": "Toutes infos admin + établissements + contacts. "
                   "Sous 30 minutes max pour ancrer la décision."},
        {"n": 16, "phase": "interne",       "titre": "Mise à jour CRM",
         "script": "RDV / rappels / commentaires / changement statut + "
                   "fiches Insee + capture Geoportail (surface au sol)."},
    ],

    "questions_techniques": [
        {"q": "Vous êtes propriétaire ou locataire des locaux ?",
         "type": "choix", "options": ["proprietaire", "locataire", "bailleur"],
         "but": "Bailleur OK pour CEE tertiaire ; locataire = bail à clarifier"},
        {"q": "Surface totale du ou des bâtiments concernés ?",
         "type": "nombre", "unite": "m²",
         "but": "Détermine seuil dossier séparé (>400 m²) et décret tertiaire (>1000 m²)"},
        {"q": "Code NAF (APE) de l'activité principale ?",
         "type": "texte",
         "but": "Mappe vers fiches éligibles : industrie / tertiaire / agricole / résidentiel"},
        {"q": "Type de chauffage actuel ?",
         "type": "choix", "options": ["gaz", "fioul", "électrique", "réseau_chaleur", "autre"],
         "but": "Coup de Pouce = uniquement gaz/fioul"},
        {"q": "Année de construction du bâtiment ?",
         "type": "nombre",
         "but": "Pré-1986 chauffé combustible = cible historique haut potentiel"},
        {"q": "Avez-vous déjà engagé une demande CEE sur ce bâtiment ?",
         "type": "choix", "options": ["oui", "non", "ne_sait_pas"],
         "but": "Non-cumul avec autre obligé requis (R092 conformité)"},
        {"q": "Avez-vous un DPE ou audit énergétique récent (<10 ans) ?",
         "type": "choix", "options": ["oui_post_2021", "oui_pre_2021", "non"],
         "but": "Requis pour rénovation globale (BAR-TH-164/174/175)"},
        {"q": "Toiture amiante ou contraintes (ombrière, monument historique) ?",
         "type": "choix", "options": ["aucune", "amiante", "monument", "autre"],
         "but": "Amiante / MH = surcoût ou KO Tech"},
    ],

    "sondages_engagement": [
        {"q": "Sur une échelle de 1 à 10, à quel point la maîtrise de votre énergie "
              "est prioritaire pour vous cette année ?",
         "but": "Mesure l'urgence ressentie, pas la solvabilité"},
        {"q": "Si on validait l'éligibilité, qui d'autre devrait être impliqué dans "
              "la décision (associé, DAF, conseil) ?",
         "but": "Identifier les décideurs cachés AVANT R2"},
        {"q": "Quel est le délai dans lequel vous aimeriez voir des travaux engagés "
              "si tout est financé ?",
         "but": "Calibrer urgence + détecter le faux-oui prudent"},
    ],

    "regles_or": [
        "Posture : technicien mandaté, PAS commercial",
        "Tu poses la question, tu fermes la bouche, tu laisses répondre",
        "JAMAIS de prix au téléphone (la prime se chiffre après VT)",
        "Si > 2 bâtiments → RDV BE direct, ne pas chiffrer en live",
        "Cible = personne morale uniquement (refus particulier dès l'ouverture)",
        "Si entendu : « j'ai déjà signé avec X » → R013 non-cumul, fermer poliment",
        "Note Monday IMMÉDIATE en fin d'appel, pas en fin de journée",
    ],

    "lien_methodologie": {
        "entonnoir_phase": "1-2 (ARRIVÉE + AUDIT)",
        "spin_phase": "S + P (Situation, Problème) — pas encore Implication",
        "pipeline": "R0 → R1",
        "interdits_closing_maestro": [
            "Ne pas dire « On signe ? »",
            "Ne pas annoncer un prix",
            "Ne pas parler des aides en premier",
        ],
    },

    "source": "GET1TECH / ENOPTEA fusion 2021 — adapté P6 CEE 2026",
}


def register_qualification_routes(app) -> None:
    @app.route("/script/qualification", methods=["GET"])
    def _script_qualification():
        """Renvoie la trame G1T 16 étapes pour la qualification téléphonique."""
        return jsonify(TRAME_QUALIFICATION)

    @app.route("/script/qualification/etape/<int:n>", methods=["GET"])
    def _script_qualification_etape(n: int):
        """Renvoie une étape précise (1 à 16) — utile pour UI guidée pas-à-pas."""
        for et in TRAME_QUALIFICATION["etapes"]:
            if et["n"] == n:
                return jsonify(et)
        return jsonify({"error": f"étape {n} introuvable (1-16)"}), 404
