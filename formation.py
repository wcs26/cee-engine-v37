"""
Module Formation — Simulateur QCM equipe commerciale
=====================================================
GET  /formation/modules       → liste des modules disponibles
GET  /formation/module/<id>   → questions d'un module
POST /formation/evaluer       → evaluation des reponses

Methodologie Jimmy : R1 Decouverte, R2 Presentation, Closing MAESTRO,
Objections ADERA, Conformite PNCEE 12 erreurs.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

# ---------------------------------------------------------------------------
# Banque de questions statique
# ---------------------------------------------------------------------------

MODULES = {
    "1": {
        "id": "1",
        "titre": "R1 — L'Art de la Decouverte",
        "description": "10 questions sur les regles du R1 : ecoute, timing, posture.",
        "nb_questions": 10,
        "questions": [
            {
                "id": "q1",
                "question": "Quelle est la duree ideale d'un R1 selon la methodologie ?",
                "options": ["A. 10-15 min", "B. 20-30 min", "C. 45-60 min", "D. 1h30"],
                "reponse_correcte": "B",
                "explication": "Le R1 doit durer 20-30 min max. Au-dela, le prospect decroche et on perd l'effet de rarete.",
                "source": "Methodologie Jimmy — Regle R1 #1",
            },
            {
                "id": "q2",
                "question": "Quand faut-il parler des aides financieres (CEE, MaPrimeRenov) en R1 ?",
                "options": ["A. Des le debut pour accrocher", "B. Au milieu pour relancer", "C. Jamais en R1", "D. Seulement si le client demande"],
                "reponse_correcte": "C",
                "explication": "Jamais parler d'aides en R1. Le R1 sert a decouvrir les douleurs. Les aides sont l'arme du R2.",
                "source": "Methodologie Jimmy — Regle R1 #3",
            },
            {
                "id": "q3",
                "question": "Quel ratio parole vendeur / client est vise en R1 ?",
                "options": ["A. 80/20 vendeur parle", "B. 50/50", "C. 20/80 client parle", "D. 30/70 client parle"],
                "reponse_correcte": "C",
                "explication": "En R1 le client parle 80% du temps. Le vendeur pose des questions ouvertes et ecoute.",
                "source": "Methodologie Jimmy — Regle R1 #2",
            },
            {
                "id": "q4",
                "question": "Quelle est la premiere question a poser en R1 ?",
                "options": [
                    "A. Quel est votre budget ?",
                    "B. Qu'est-ce qui vous a motive a accepter ce rendez-vous ?",
                    "C. Connaissez-vous les CEE ?",
                    "D. Combien mesurent vos locaux ?",
                ],
                "reponse_correcte": "B",
                "explication": "On demarre par la motivation du RDV. Ca revele la douleur principale sans orienter la reponse.",
                "source": "Methodologie Jimmy — Regle R1 #4",
            },
            {
                "id": "q5",
                "question": "Faut-il prendre des mesures en R1 ?",
                "options": ["A. Oui, toujours", "B. Non, jamais", "C. Seulement si le client insiste", "D. Oui mais approximatives"],
                "reponse_correcte": "A",
                "explication": "Toujours prendre les mesures en R1. Ca professionnalise, ca justifie le R2, et ca donne les m2 pour le chiffrage.",
                "source": "Methodologie Jimmy — Regle R1 #5",
            },
            {
                "id": "q6",
                "question": "Comment conclure un R1 ?",
                "options": [
                    "A. Envoyer un devis par mail",
                    "B. Fixer le R2 sur place avec date et heure",
                    "C. Dire qu'on rappellera",
                    "D. Laisser sa carte de visite",
                ],
                "reponse_correcte": "B",
                "explication": "Toujours fixer le R2 sur place, cale dans l'agenda. Un R1 sans R2 cale = R1 perdu.",
                "source": "Methodologie Jimmy — Regle R1 #7",
            },
            {
                "id": "q7",
                "question": "Quel document emporter en R1 ?",
                "options": [
                    "A. Plaquette commerciale complete",
                    "B. Rien, juste un carnet",
                    "C. Trame de decouverte + metre laser",
                    "D. Contrat pre-rempli",
                ],
                "reponse_correcte": "C",
                "explication": "Trame de decouverte pour structurer les questions + metre laser pour les mesures. Pas de plaquette en R1.",
                "source": "Methodologie Jimmy — Regle R1 #6",
            },
            {
                "id": "q8",
                "question": "Le prospect dit 'envoyez-moi un devis par mail'. Que faire ?",
                "options": [
                    "A. Envoyer le devis",
                    "B. Expliquer que le devis necessite une etude sur place",
                    "C. Refuser poliment",
                    "D. Envoyer une fourchette de prix",
                ],
                "reponse_correcte": "B",
                "explication": "Jamais de devis par mail sans R2. Le devis mail = prix sans contexte = comparaison pure = on perd.",
                "source": "Methodologie Jimmy — Regle R1 #8",
            },
            {
                "id": "q9",
                "question": "Combien de douleurs minimum identifier en R1 ?",
                "options": ["A. 1 suffit", "B. 2 minimum", "C. 3 minimum", "D. 5 minimum"],
                "reponse_correcte": "C",
                "explication": "3 douleurs minimum : une economique, une confort, une reglementaire. Ca donne 3 leviers pour le R2.",
                "source": "Methodologie Jimmy — Regle R1 #9",
            },
            {
                "id": "q10",
                "question": "Faut-il visiter tout le batiment en R1 ?",
                "options": [
                    "A. Non, juste la zone concernee",
                    "B. Oui, tout visiter",
                    "C. Seulement les combles",
                    "D. Pas de visite, rester au bureau",
                ],
                "reponse_correcte": "B",
                "explication": "Visiter tout le batiment permet de detecter des opportunites complementaires (toiture, chaufferie, eclairage, VMC).",
                "source": "Methodologie Jimmy — Regle R1 #10",
            },
        ],
    },
    "2": {
        "id": "2",
        "titre": "R2 — Presentation et Validation",
        "description": "10 questions sur les 5 phases du R2 et les 20 points cles.",
        "nb_questions": 10,
        "questions": [
            {
                "id": "q1",
                "question": "Quelle est la premiere phase du R2 ?",
                "options": [
                    "A. Presentation du prix",
                    "B. Ancrage emotionnel (rappel des douleurs R1)",
                    "C. Tour de table",
                    "D. Presentation de l'entreprise",
                ],
                "reponse_correcte": "B",
                "explication": "Phase 1 = ancrage emotionnel. On rappelle les 3 douleurs identifiees en R1 pour reactiver la motivation.",
                "source": "Methodologie Jimmy — R2 Phase 1",
            },
            {
                "id": "q2",
                "question": "Quel argument prime sur la rentabilite en R2 ?",
                "options": ["A. Le prix bas", "B. La coherence du projet", "C. Les subventions", "D. La marque du materiel"],
                "reponse_correcte": "B",
                "explication": "'Coherence > Rentabilite'. Le client achete parce que le projet fait sens pour LUI, pas pour un tableur Excel.",
                "source": "Methodologie Jimmy — R2 Point cle #4",
            },
            {
                "id": "q3",
                "question": "Combien de temps de silence apres l'annonce du prix ?",
                "options": ["A. 0 sec, enchaîner vite", "B. 1 sec", "C. 3 sec minimum", "D. 10 sec"],
                "reponse_correcte": "C",
                "explication": "Silence 3 secondes apres le prix. Celui qui parle en premier perd. Le silence cree la tension positive.",
                "source": "Methodologie Jimmy — R2 Point cle #12",
            },
            {
                "id": "q4",
                "question": "Le decideur n'est pas present au R2. Que faire ?",
                "options": [
                    "A. Presenter quand meme",
                    "B. Reporter le R2 avec le decideur",
                    "C. Laisser le dossier",
                    "D. Faire le R2 puis rappeler le decideur",
                ],
                "reponse_correcte": "B",
                "explication": "Jamais de R2 sans decideur. Reporter systematiquement. Un R2 sans decideur = closing impossible.",
                "source": "Methodologie Jimmy — R2 Point cle #1",
            },
            {
                "id": "q5",
                "question": "Comment presenter le prix en R2 ?",
                "options": [
                    "A. Prix brut d'abord, puis les aides",
                    "B. Prix net directement",
                    "C. Investissement global puis decomposition (travaux - aides = reste)",
                    "D. Fourchette de prix",
                ],
                "reponse_correcte": "C",
                "explication": "Presenter l'investissement global, decomposer, puis montrer le reste a charge. Le client voit la valeur totale.",
                "source": "Methodologie Jimmy — R2 Phase 4",
            },
            {
                "id": "q6",
                "question": "Quel support utiliser pour la presentation R2 ?",
                "options": [
                    "A. PowerPoint generique",
                    "B. Dossier personnalise avec photos du site + mesures R1",
                    "C. Plaquette standard",
                    "D. Tablette avec catalogue",
                ],
                "reponse_correcte": "B",
                "explication": "Dossier 100% personnalise avec les photos et mesures prises en R1. Le client se reconnait = engagement.",
                "source": "Methodologie Jimmy — R2 Point cle #3",
            },
            {
                "id": "q7",
                "question": "Quelle phrase utiliser pour introduire les economies ?",
                "options": [
                    "A. 'Vous allez economiser X euros'",
                    "B. 'Votre facture actuelle de X va passer a Y'",
                    "C. 'Avec les aides, ca ne coute presque rien'",
                    "D. 'C'est rentabilise en 2 ans'",
                ],
                "reponse_correcte": "B",
                "explication": "Partir du connu (facture actuelle) vers le resultat. C'est concret et verifiable par le client.",
                "source": "Methodologie Jimmy — R2 Point cle #8",
            },
            {
                "id": "q8",
                "question": "A quel moment presenter les references clients ?",
                "options": [
                    "A. Au debut du R2",
                    "B. Apres l'annonce du prix, en renfort",
                    "C. Jamais, ca fait pretentieux",
                    "D. Seulement si le client demande",
                ],
                "reponse_correcte": "B",
                "explication": "Les references arrivent apres le prix pour rassurer. Preuve sociale au moment ou le doute s'installe.",
                "source": "Methodologie Jimmy — R2 Phase 5",
            },
            {
                "id": "q9",
                "question": "Faut-il laisser le dossier au client a la fin du R2 ?",
                "options": [
                    "A. Oui, toujours",
                    "B. Non, jamais",
                    "C. Seulement s'il signe",
                    "D. Seulement la synthese, pas le devis detaille",
                ],
                "reponse_correcte": "D",
                "explication": "Laisser la synthese mais garder le devis detaille. Ca evite la comparaison ligne a ligne avec un concurrent.",
                "source": "Methodologie Jimmy — R2 Point cle #15",
            },
            {
                "id": "q10",
                "question": "Le client dit 'je vais reflechir'. Quelle reponse ?",
                "options": [
                    "A. D'accord, prenez votre temps",
                    "B. A quoi souhaitez-vous reflechir exactement ?",
                    "C. Je vous rappelle la semaine prochaine",
                    "D. Je baisse le prix de 10%",
                ],
                "reponse_correcte": "B",
                "explication": "Isoler l'objection. 'Reflechir' n'est pas une objection, c'est un cache. Il faut decouvrir ce qui bloque.",
                "source": "Methodologie Jimmy — R2 Point cle #18",
            },
        ],
    },
    "3": {
        "id": "3",
        "titre": "Closing MAESTRO",
        "description": "10 questions sur les 10 commandements du closing.",
        "nb_questions": 10,
        "questions": [
            {
                "id": "q1",
                "question": "Quelle phrase est INTERDITE en closing ?",
                "options": [
                    "A. 'Souhaitez-vous demarrer ?'",
                    "B. 'On signe ?'",
                    "C. 'Quel planning vous conviendrait ?'",
                    "D. 'Preferez-vous la version A ou B ?'",
                ],
                "reponse_correcte": "B",
                "explication": "'On signe ?' est interdit. Ca met une pression brute. Utiliser l'illusion du choix ou la projection.",
                "source": "Methodologie Jimmy — Maestro Commandement #1",
            },
            {
                "id": "q2",
                "question": "Qu'est-ce que l'illusion du choix ?",
                "options": [
                    "A. Proposer 2 options qui menent toutes les deux au oui",
                    "B. Faire croire qu'il y a une promo",
                    "C. Donner un faux delai",
                    "D. Mentir sur le stock",
                ],
                "reponse_correcte": "A",
                "explication": "L'illusion du choix = 2 options positives. 'On demarre en juin ou en septembre ?' Les deux = signature.",
                "source": "Methodologie Jimmy — Maestro Commandement #2",
            },
            {
                "id": "q3",
                "question": "Quand tenter le closing ?",
                "options": [
                    "A. A la fin de la presentation",
                    "B. Des le premier signal d'achat",
                    "C. Apres avoir tout explique",
                    "D. Quand le client dit 'c'est interessant'",
                ],
                "reponse_correcte": "B",
                "explication": "Closer au premier signal d'achat. Attendre = refroidir. Signal = question sur le planning, le financement, les details.",
                "source": "Methodologie Jimmy — Maestro Commandement #3",
            },
            {
                "id": "q4",
                "question": "Le client hesite entre deux options. Que faire ?",
                "options": [
                    "A. Choisir pour lui",
                    "B. Ajouter une troisieme option",
                    "C. Reformuler les avantages de chaque puis recommander",
                    "D. Baisser le prix de l'option la plus chere",
                ],
                "reponse_correcte": "C",
                "explication": "Reformuler + recommander. Le vendeur est l'expert. Le client attend un conseil, pas un choix impose.",
                "source": "Methodologie Jimmy — Maestro Commandement #4",
            },
            {
                "id": "q5",
                "question": "Qu'est-ce que la technique de la projection ?",
                "options": [
                    "A. Montrer des photos de chantier",
                    "B. Parler au futur comme si c'etait deja decide",
                    "C. Projeter un PowerPoint",
                    "D. Envoyer un mail de confirmation",
                ],
                "reponse_correcte": "B",
                "explication": "Projection = parler au futur. 'Quand les travaux seront faits, vous constaterez...' Le client se projette = il achete.",
                "source": "Methodologie Jimmy — Maestro Commandement #5",
            },
            {
                "id": "q6",
                "question": "Combien de tentatives de closing maximum par R2 ?",
                "options": ["A. 1 seule", "B. 2", "C. 3", "D. Autant que necessaire"],
                "reponse_correcte": "C",
                "explication": "3 tentatives max. Au-dela, ca devient de la pression et on perd la relation de confiance.",
                "source": "Methodologie Jimmy — Maestro Commandement #6",
            },
            {
                "id": "q7",
                "question": "Le client dit oui. Quelle est la PREMIERE chose a faire ?",
                "options": [
                    "A. Sortir le contrat",
                    "B. Le feliciter pour sa decision",
                    "C. Parler des details techniques",
                    "D. Appeler le bureau",
                ],
                "reponse_correcte": "B",
                "explication": "Feliciter d'abord. Renforcer la decision. Puis seulement sortir les papiers. L'ordre compte.",
                "source": "Methodologie Jimmy — Maestro Commandement #7",
            },
            {
                "id": "q8",
                "question": "Apres la signature, faut-il rester longtemps ?",
                "options": [
                    "A. Oui, pour consolider",
                    "B. Non, partir rapidement apres les formalites",
                    "C. Rester pour un cafe",
                    "D. Attendre que le client pose des questions",
                ],
                "reponse_correcte": "B",
                "explication": "Apres signature = depart rapide. Rester trop longtemps peut creer le remords d'achat (buyer's remorse).",
                "source": "Methodologie Jimmy — Maestro Commandement #8",
            },
            {
                "id": "q9",
                "question": "Le client veut en parler a son comptable. Meilleure reponse ?",
                "options": [
                    "A. D'accord, je rappelle dans 3 jours",
                    "B. Appelons-le ensemble maintenant",
                    "C. Le comptable n'a pas besoin de valider ca",
                    "D. Je vous laisse le dossier",
                ],
                "reponse_correcte": "B",
                "explication": "Proposer d'appeler ensemble. Ca montre la transparence et ca evite le filtre deformant du client.",
                "source": "Methodologie Jimmy — Maestro Commandement #9",
            },
            {
                "id": "q10",
                "question": "Faut-il mentionner le delai de retractation ?",
                "options": [
                    "A. Non, ca donne envie d'annuler",
                    "B. Oui, c'est obligatoire et ca rassure",
                    "C. Seulement si le client le demande",
                    "D. Le mentionner en petit dans le contrat",
                ],
                "reponse_correcte": "B",
                "explication": "Toujours mentionner le delai de retractation. C'est legal ET ca rassure le client sur notre transparence.",
                "source": "Methodologie Jimmy — Maestro Commandement #10",
            },
        ],
    },
    "4": {
        "id": "4",
        "titre": "Objections ADERA",
        "description": "5 questions sur la methode ADERA (Accueillir, Decouvrir, Empathiser, Repondre, Ancrer).",
        "nb_questions": 5,
        "questions": [
            {
                "id": "q1",
                "question": "Que signifie le A de ADERA ?",
                "options": ["A. Argumenter", "B. Accueillir", "C. Analyser", "D. Accepter"],
                "reponse_correcte": "B",
                "explication": "A = Accueillir l'objection. Ne jamais contredire frontalement. 'Je comprends votre point...'",
                "source": "Methodologie Jimmy — ADERA Etape 1",
            },
            {
                "id": "q2",
                "question": "Le client dit 'c'est trop cher'. Quelle est l'etape D (Decouvrir) ?",
                "options": [
                    "A. Baisser le prix",
                    "B. Demander 'trop cher par rapport a quoi ?'",
                    "C. Montrer les aides",
                    "D. Ignorer et continuer",
                ],
                "reponse_correcte": "B",
                "explication": "D = Decouvrir la vraie objection derriere. 'Trop cher' peut signifier budget, priorite, comparaison...",
                "source": "Methodologie Jimmy — ADERA Etape 2",
            },
            {
                "id": "q3",
                "question": "Quel est le role de l'etape E (Empathiser) ?",
                "options": [
                    "A. Plaindre le client",
                    "B. Valider le ressenti sans valider l'objection",
                    "C. Raconter une anecdote personnelle",
                    "D. Proposer une remise",
                ],
                "reponse_correcte": "B",
                "explication": "E = Empathiser. Valider le ressenti : 'C'est normal de vouloir comparer'. Pas valider l'objection.",
                "source": "Methodologie Jimmy — ADERA Etape 3",
            },
            {
                "id": "q4",
                "question": "A l'etape R (Repondre), quel type d'argument est le plus efficace ?",
                "options": [
                    "A. Un argument generique",
                    "B. Un temoignage client similaire",
                    "C. Une remise commerciale",
                    "D. Un argument technique detaille",
                ],
                "reponse_correcte": "B",
                "explication": "R = Repondre avec preuve sociale. Un client similaire qui avait la meme objection et qui est satisfait.",
                "source": "Methodologie Jimmy — ADERA Etape 4",
            },
            {
                "id": "q5",
                "question": "Que fait-on a l'etape A finale (Ancrer) ?",
                "options": [
                    "A. Repeter l'argument",
                    "B. Verifier que l'objection est levee puis re-closer",
                    "C. Passer a l'objection suivante",
                    "D. Proposer un delai de reflexion",
                ],
                "reponse_correcte": "B",
                "explication": "A final = Ancrer. Verifier : 'Est-ce que ca repond a votre question ?' Si oui, re-closer immediatement.",
                "source": "Methodologie Jimmy — ADERA Etape 5",
            },
        ],
    },
    "5": {
        "id": "5",
        "titre": "Conformite PNCEE — 12 erreurs",
        "description": "12 questions sur les 12 erreurs fatales de conformite dossier CEE (G1T).",
        "nb_questions": 12,
        "questions": [
            {
                "id": "q1",
                "question": "Quelle couleur d'encre est obligatoire pour la signature du beneficiaire ?",
                "options": ["A. Noire", "B. Bleue", "C. Noire ou bleue", "D. Peu importe"],
                "reponse_correcte": "B",
                "explication": "Encre BLEUE obligatoire. Ca prouve que c'est un original et non une photocopie.",
                "source": "G1T — Erreur #1",
            },
            {
                "id": "q2",
                "question": "Peut-on imprimer l'attestation sur l'honneur en recto-verso ?",
                "options": ["A. Oui, pour economiser le papier", "B. Non, jamais", "C. Oui si c'est agrafe", "D. Oui si le client est d'accord"],
                "reponse_correcte": "B",
                "explication": "JAMAIS de recto-verso sur l'AH. Chaque page doit etre un recto seul pour eviter tout soupcon de falsification.",
                "source": "G1T — Erreur #2",
            },
            {
                "id": "q3",
                "question": "Ou doit etre appose le tampon de l'entreprise beneficiaire ?",
                "options": [
                    "A. Sur la signature",
                    "B. A cote de la signature, sans la toucher",
                    "C. En haut de page",
                    "D. Au dos du document",
                ],
                "reponse_correcte": "B",
                "explication": "Le tampon doit etre A COTE de la signature, pas dessus. Sinon ca rend la signature illisible = rejet.",
                "source": "G1T — Erreur #3",
            },
            {
                "id": "q4",
                "question": "Quel delai maximum entre la date de signature et la date des travaux ?",
                "options": ["A. Pas de delai", "B. 6 mois", "C. 12 mois", "D. La signature doit etre AVANT le devis"],
                "reponse_correcte": "D",
                "explication": "L'engagement CEE (AH signee) doit etre date AVANT le devis. C'est l'anteriorite qui compte.",
                "source": "G1T — Erreur #4",
            },
            {
                "id": "q5",
                "question": "Le SIRET sur l'AH est different de celui sur le devis. Consequence ?",
                "options": ["A. Pas grave", "B. Rejet systematique", "C. Demande de correction", "D. Accepte avec reserve"],
                "reponse_correcte": "B",
                "explication": "SIRET incoherent = rejet systematique. Verifier la concordance AH / devis / facture / RGE avant envoi.",
                "source": "G1T — Erreur #5",
            },
            {
                "id": "q6",
                "question": "La mention 'lu et approuve' est-elle obligatoire sur l'AH ?",
                "options": [
                    "A. Non, la signature suffit",
                    "B. Oui, manuscrite obligatoire",
                    "C. Seulement pour les montants > 10 000 EUR",
                    "D. Seulement en B2C",
                ],
                "reponse_correcte": "B",
                "explication": "Mention 'lu et approuve' manuscrite obligatoire sur l'AH. Son absence = motif de rejet PNCEE.",
                "source": "G1T — Erreur #6",
            },
            {
                "id": "q7",
                "question": "Le certificat RGE de l'installateur expire 3 jours apres la fin des travaux. Valide ?",
                "options": [
                    "A. Oui, il etait valide pendant les travaux",
                    "B. Non, il doit etre valide a la date de depot",
                    "C. Oui si les travaux sont finis",
                    "D. Non, il doit couvrir toute la duree de vie cumac",
                ],
                "reponse_correcte": "B",
                "explication": "Le RGE doit etre valide au moment du depot du dossier chez l'oblige, pas seulement pendant les travaux.",
                "source": "G1T — Erreur #7",
            },
            {
                "id": "q8",
                "question": "Faut-il joindre la facture de l'isolant avec les caracteristiques techniques ?",
                "options": [
                    "A. Non, le devis suffit",
                    "B. Oui, avec R thermique, epaisseur, marque, certification ACERMI",
                    "C. Seulement la fiche technique",
                    "D. Seulement pour BAT-EN-103",
                ],
                "reponse_correcte": "B",
                "explication": "Facture avec R, epaisseur, marque ET numero ACERMI. Toute info manquante = demande complementaire = delai.",
                "source": "G1T — Erreur #8",
            },
            {
                "id": "q9",
                "question": "Le cadre 'Contribution' sur l'AH est vide. Consequence ?",
                "options": ["A. Pas grave, c'est optionnel", "B. Rejet", "C. Demande complementaire", "D. Accepte si le montant est sur le devis"],
                "reponse_correcte": "B",
                "explication": "Le cadre Contribution (role actif et incitatif de l'oblige) doit etre rempli. Vide = non-conformite = rejet.",
                "source": "G1T — Erreur #9",
            },
            {
                "id": "q10",
                "question": "Peut-on envoyer le dossier CEE par email a l'oblige ?",
                "options": [
                    "A. Oui, scan PDF suffit",
                    "B. Non, originaux papier uniquement",
                    "C. Depend de l'oblige",
                    "D. Oui si signature electronique",
                ],
                "reponse_correcte": "C",
                "explication": "Ca depend de l'oblige. Certains acceptent le numerique, d'autres exigent les originaux. Verifier AVANT.",
                "source": "G1T — Erreur #10",
            },
            {
                "id": "q11",
                "question": "La date de fin de travaux sur la facture est posterieure a la date sur l'AH de fin de travaux. Probleme ?",
                "options": [
                    "A. Non, c'est normal",
                    "B. Oui, incoherence de dates = rejet",
                    "C. Pas si l'ecart est < 30 jours",
                    "D. Seulement pour les gros chantiers",
                ],
                "reponse_correcte": "B",
                "explication": "Toute incoherence de dates entre AH et facture = motif de rejet. Les dates doivent etre parfaitement alignees.",
                "source": "G1T — Erreur #11",
            },
            {
                "id": "q12",
                "question": "Le paraphe est-il obligatoire sur chaque page de l'AH ?",
                "options": [
                    "A. Non, seule la derniere page",
                    "B. Oui, chaque page doit etre paraphee",
                    "C. Seulement les pages avec du texte",
                    "D. Le paraphe est facultatif",
                ],
                "reponse_correcte": "B",
                "explication": "Paraphe obligatoire sur CHAQUE page de l'AH. Page non paraphee = page contestable = risque de rejet.",
                "source": "G1T — Erreur #12",
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# Conseil IA selon score
# ---------------------------------------------------------------------------

def _conseil_ia(score_pct: float, module_titre: str) -> str:
    if score_pct >= 90:
        return f"Excellent ! Tu maitrises {module_titre}. Continue comme ca, tu es pret pour le terrain."
    elif score_pct >= 70:
        return f"Bon niveau sur {module_titre}. Revois les points rates — ce sont souvent ceux qui font perdre des deals."
    elif score_pct >= 50:
        return f"Moyen sur {module_titre}. Je te recommande de relire la methodologie et de refaire le quiz dans 48h."
    else:
        return f"Alerte sur {module_titre}. Score critique. Bloque 30 min pour revoir la methodo avant ton prochain RDV."


# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

formation_bp = Blueprint("formation", __name__)


@formation_bp.route("/formation/modules", methods=["GET"])
def list_modules():
    """Liste des modules de formation disponibles."""
    modules_list = []
    for m in MODULES.values():
        modules_list.append({
            "id": m["id"],
            "titre": m["titre"],
            "description": m["description"],
            "nb_questions": m["nb_questions"],
        })
    return jsonify({"modules": modules_list})


@formation_bp.route("/formation/module/<module_id>", methods=["GET"])
def get_module(module_id):
    """Contenu d'un module (questions + reponses)."""
    module = MODULES.get(module_id)
    if not module:
        return jsonify({"error": f"Module {module_id} introuvable. Modules disponibles : 1-5."}), 404
    return jsonify(module)


@formation_bp.route("/formation/evaluer", methods=["POST"])
def evaluer():
    """Evaluer les reponses d'un vendeur."""
    data = request.get_json(force=True, silent=True) or {}
    module_id = str(data.get("module_id", ""))
    reponses = data.get("reponses", {})

    module = MODULES.get(module_id)
    if not module:
        return jsonify({"error": f"Module {module_id} introuvable."}), 404

    if not reponses:
        return jsonify({"error": "Champ 'reponses' requis. Format : {q1: 'A', q2: 'B', ...}"}), 400

    details = []
    nb_correct = 0
    for q in module["questions"]:
        qid = q["id"]
        reponse_donnee = reponses.get(qid, "").upper().strip()
        correct = reponse_donnee == q["reponse_correcte"]
        if correct:
            nb_correct += 1
        details.append({
            "question_id": qid,
            "question": q["question"],
            "reponse_donnee": reponse_donnee or "(pas de reponse)",
            "reponse_correcte": q["reponse_correcte"],
            "correct": correct,
            "explication": q["explication"],
        })

    nb_total = len(module["questions"])
    score_pct = round(nb_correct / nb_total * 100, 1) if nb_total > 0 else 0

    return jsonify({
        "module_id": module_id,
        "module_titre": module["titre"],
        "score": f"{score_pct}%",
        "nb_correct": nb_correct,
        "nb_total": nb_total,
        "details": details,
        "conseil_ia": _conseil_ia(score_pct, module["titre"]),
    })


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def register_formation_routes(app):
    """Enregistre le blueprint formation sur l'app Flask."""
    app.register_blueprint(formation_bp)
