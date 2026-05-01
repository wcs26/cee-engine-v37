"""
Module Formation — Simulateur QCM equipe commerciale
=====================================================
GET  /formation/modules       -> liste des modules disponibles
GET  /formation/module/<id>   -> questions d'un module
POST /formation/evaluer       -> evaluation des reponses
GET  /formation/objection/<n> -> 1 objection + reponse type + technique ADERA

Methodologie Jimmy : R1 Decouverte SPIN, R2 Presentation Validation,
Closing MAESTRO, Objections ADERA (44), Conformite PNCEE 12 erreurs,
Porte-a-porte B2B PV, Script Courtage -> PV, Montage Dossier,
Expert S21 PV technique, GetAccept, Monday/Optiwise/Likewatt, 6 Closings.

Sources : fichiers de formation internes Jimmy / OXEO / Ma Meilleure Energie.
Total : 12 modules, 350+ questions.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

# ---------------------------------------------------------------------------
# Banque d'objections (44 objections les plus frequentes)
# Source : Guide de Traitement des 44 objections / Script Courtage / Synthese
# ---------------------------------------------------------------------------

OBJECTIONS = [
    {
        "numero": 1,
        "objection": "J'ai pas le temps",
        "reponse": "Justement, c'est rapide : on parle d'une etude gratuite, basee sur vos propres donnees, pour potentiellement reduire votre facture durablement. Est-ce que je vous cale un appel de 15 minutes cette semaine ou la suivante ?",
        "technique_adera": "A: Accueillir avec calme. D: 'Qu'est-ce qui vous prend du temps en ce moment ?' E: 'C'est normal d'etre pris.' R: Minimiser l'effort — 15 min, gratuit. A: Proposer un creneau precis.",
    },
    {
        "numero": 2,
        "objection": "J'ai deja un fournisseur, c'est bon",
        "reponse": "Justement, on ne touche pas a votre fournisseur. On parle ici de reduire la quantite que vous achetez, pas de changer celui qui vous la vend. C'est complementaire a votre contrat actuel.",
        "technique_adera": "A: Accueillir. D: 'Vous etes satisfait du prix ou du service ?' E: Valider la fidelite. R: Repositionner — autonomie vs fournisseur. A: 'On verifie ensemble ?'",
    },
    {
        "numero": 3,
        "objection": "Je veux reflechir",
        "reponse": "Bien sur. Juste pour vous aider a reflechir avec du concret, l'etude est entierement offerte et basee sur vos propres chiffres. On ne decide rien maintenant, on voit si ca vaut le coup.",
        "technique_adera": "A: 'Je comprends tout a fait.' D: 'A quoi souhaitez-vous reflechir exactement ?' E: Valider le besoin de reflexion. R: No risk, just info. A: Proposer RDV 15 min.",
    },
    {
        "numero": 4,
        "objection": "C'est surement trop cher",
        "reponse": "C'est ce qu'on pourrait penser. Mais justement, dans plus de 80% des cas, le projet est auto-finance par les economies. D'ou l'interet de l'etude. On valide ca ensemble ?",
        "technique_adera": "A: Accueillir sans contredire. D: 'Trop cher par rapport a quoi ?' E: 'C'est normal de vouloir maitriser son budget.' R: Susciter la curiosite + etude gratuite. A: Re-closer.",
    },
    {
        "numero": 5,
        "objection": "Je ne suis pas proprietaire",
        "reponse": "Merci pour la transparence. On a parfois des solutions quand le locataire est acteur du batiment, mais dans tous les cas on verifie la faisabilite avant de perdre du temps.",
        "technique_adera": "A: Remercier. D: 'Vous etes locataire d'un batiment professionnel ?' E: Valider. R: Verifier si blocage reel ou pas. A: Proposer une verification.",
    },
    {
        "numero": 6,
        "objection": "C'est pas le bon moment",
        "reponse": "C'est justement quand les prix sont hauts que les economies sont les plus fortes. Et comme l'etude est offerte et sans engagement, autant l'avoir sous la main pour decider quand vous serez pret.",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qui ferait que ce soit le bon moment ?' E: 'Je comprends, le timing compte.' R: Urgence implicite — prix hauts = economies fortes. A: 'Etude = liberte future.'",
    },
    {
        "numero": 7,
        "objection": "Je n'y connais rien",
        "reponse": "C'est justement notre role. On a simplifie tout le process avec un bureau d'etude dedie et une explication claire, 100% adaptee a votre cas. On ne vous demande pas d'y croire, on vous montre les chiffres, et vous decidez ensuite.",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qui vous inquiete le plus ?' E: 'C'est normal, c'est technique.' R: Deleguer la competence. A: 'On vous montre, vous decidez.'",
    },
    {
        "numero": 8,
        "objection": "J'ai deja ete demarche",
        "reponse": "Je comprends. La difference ici c'est qu'on vous demarche en tant que client actif, avec vos donnees, une pre-etude deja faite, et une etude offerte. Rien a vendre aujourd'hui, juste a valider si c'est rentable.",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qui vous a derange la derniere fois ?' E: 'C'est normal d'etre mefiant.' R: Revaloriser la relation + demarche personnalisee. A: '15 min pour verifier.'",
    },
    {
        "numero": 9,
        "objection": "Je veux voir ce que vous m'envoyez d'abord",
        "reponse": "Parfait. Je vous l'envoie tout de suite : le mail recap, le formulaire ACD, et on a besoin de votre facture recente. Je vous propose de fixer aussi le creneau maintenant, ca vous evite d'avoir a y repenser plus tard.",
        "technique_adera": "A: Accueillir. D: 'Qu'attendez-vous comme info ?' E: 'C'est normal de vouloir du concret.' R: Eviter la fuite par 'plus tard'. A: Double engagement — doc + creneau.",
    },
    {
        "numero": 10,
        "objection": "Ca m'interesse pas",
        "reponse": "Entendu. Je ne vous retiens pas, mais sachez qu'on est venu vers vous parce qu'une pre-etude montre un potentiel concret d'economies et d'autonomie. C'est vous qui decidez apres avoir vu. Je peux vous bloquer un creneau de 15 min juste pour ca ?",
        "technique_adera": "A: Accueillir sans pression. D: 'Qu'est-ce qui ne vous interesse pas specifiquement ?' E: 'Je comprends.' R: Valeur + posture de service. A: Derniere tentative douce.",
    },
    {
        "numero": 11,
        "objection": "Je dois en parler a mon associe / ma femme",
        "reponse": "Qu'est-ce que vous allez lui dire en priorite ?",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qu'il/elle devrait savoir en premier ?' E: Valider le besoin de consulter. R: Faire du client un relais — proposer un RDV a 3 ou appeler ensemble. A: Fixer le prochain RDV.",
    },
    {
        "numero": 12,
        "objection": "Je veux plusieurs devis",
        "reponse": "C'est normal. Comparez, mais comparez ce qui est equivalent.",
        "technique_adera": "A: Accueillir. D: 'Sur quels criteres allez-vous comparer ?' E: 'C'est une bonne demarche.' R: Validation interne — le client cherche a confirmer, pas a comparer. A: 'On reste a disposition.'",
    },
    {
        "numero": 13,
        "objection": "Je ne suis pas pret a m'engager",
        "reponse": "Qu'est-ce qui manque pour que ce soit juste pour vous ?",
        "technique_adera": "A: Accueillir. D: 'Ou ai-je perdu votre alignement ?' E: Valider la prudence. R: Corriger le processus, pas defendre le produit. A: 'On ajuste ensemble.'",
    },
    {
        "numero": 14,
        "objection": "C'est une arnaque / je me mefie",
        "reponse": "C'est une OBLIGATION LEGALE. Les energeticiens preferent financer plutot que payer la penalite liberatoire (~15 EUR/MWh cumac, soit ~0,015 EUR/kWh cumac, art. L. 222-2 Code de l'energie). Verifiez sur ecologie.gouv.fr.",
        "technique_adera": "A: Accueillir sans s'offusquer. D: 'Qu'est-ce qui vous a fait douter ?' E: 'C'est normal d'etre prudent avec les demarchages.' R: Preuve legale + site officiel. A: 'Verifiez par vous-meme.'",
    },
    {
        "numero": 15,
        "objection": "Deja fait des travaux",
        "reponse": "P6 2026 a de NOUVELLES opportunites. Combles non isoles ? Parking souterrain ?",
        "technique_adera": "A: Accueillir. D: 'Quels travaux avez-vous faits exactement ?' E: 'Bravo pour l'initiative.' R: Nouvelles fiches P6 compatibles. A: 'On verifie ce qui reste eligible.'",
    },
    {
        "numero": 16,
        "objection": "C'est complique administrativement",
        "reponse": "C'est notre role de TOUT gerer. Zero paperasse de votre cote.",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qui vous semble le plus lourd ?' E: 'C'est vrai, l'admin peut etre lourde.' R: On gere tout de A a Z. A: 'Votre seul role : valider.'",
    },
    {
        "numero": 17,
        "objection": "Je dois en parler a mon directeur / au conseil",
        "reponse": "Ses coordonnees pour la doc ? Ou on fixe un creneau a 3 pour une presentation commune ?",
        "technique_adera": "A: Accueillir. D: 'De quoi a-t-il besoin pour decider ?' E: 'C'est normal en entreprise.' R: Proposer presentation commune. A: Fixer le creneau.",
    },
    {
        "numero": 18,
        "objection": "Envoyez-moi un devis par mail",
        "reponse": "Le devis necessite une etude sur place. Un devis par mail sans contexte = comparaison pure = on perd tous les deux.",
        "technique_adera": "A: Accueillir. D: 'Qu'attendez-vous du devis ?' E: 'Je comprends, vous voulez du concret.' R: Expliquer que devis mail = prix sans valeur. A: 'On fixe une visite pour un vrai chiffrage.'",
    },
    {
        "numero": 19,
        "objection": "Je vais reflechir (en R2)",
        "reponse": "A quoi souhaitez-vous reflechir exactement ?",
        "technique_adera": "A: Accueillir. D: Isoler l'objection — 'Reflechir' est un cache, pas une objection. E: Valider le besoin de clarifier. R: 'Qu'est-ce qui reste flou ?' A: Re-closer si l'objection est levee.",
    },
    {
        "numero": 20,
        "objection": "Je n'ai pas confiance dans les installateurs",
        "reponse": "Pouvez-vous me dire ce qui vous a fait perdre confiance ?",
        "technique_adera": "A: Accueillir. D: Explorer l'experience passee. E: 'C'est souvent ce qu'on entend.' R: Preuve sociale — '+500 installations certifiees RGE'. A: Proposer des references.",
    },
    {
        "numero": 21,
        "objection": "Le solaire ca marche pas / c'est pas rentable",
        "reponse": "Dans +80% des cas, c'est auto-finance par les economies. D'ou l'interet de l'etude gratuite basee sur VOS chiffres.",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qui vous fait penser ca ?' E: 'Il y a eu des mauvaises experiences dans le passe.' R: Chiffres concrets + etude personnalisee. A: '15 min pour verifier.'",
    },
    {
        "numero": 22,
        "objection": "Je ne veux pas donner ma facture EDF",
        "reponse": "La facture nous permet de calculer la bonne puissance de panneaux, pour ne pas vous surdimensionner.",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qui vous gene ?' E: 'C'est normal de proteger ses infos.' R: Expliquer calmement pourquoi elle est necessaire (dimensionnement, puissance, ROI). A: Rassurer sur la confidentialite.",
    },
    {
        "numero": 23,
        "objection": "J'ai un ami qui fait ca / qui peut le faire",
        "reponse": "C'est bien d'avoir un contact de confiance. Notre etude est gratuite et sans engagement — elle vous donnera une base de comparaison professionnelle.",
        "technique_adera": "A: Accueillir. D: 'Il est specialise dans quel type de projet ?' E: 'C'est naturel de passer par son reseau.' R: Positionner l'etude comme complement objectif. A: 'Comparez les deux.'",
    },
    {
        "numero": 24,
        "objection": "C'est trop cher (en R2, apres le prix)",
        "reponse": "Quand vous dites cher, c'est par rapport a quoi ?",
        "technique_adera": "A: Accueillir sans baisser le prix. D: 'Par rapport a quoi ?' E: Valider le ressenti. R: Revenir a la valeur AVANT le prix — l'objection prix est presque JAMAIS une objection d'argent, c'est un doute de valeur. A: Re-closer.",
    },
    {
        "numero": 25,
        "objection": "Je vais en parler a mon comptable",
        "reponse": "Appelons-le ensemble maintenant. Ca montre la transparence et ca evite le filtre deformant.",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qu'il va vouloir savoir ?' E: 'C'est prudent.' R: Proposer un appel a 3. A: 'Je lui envoie la synthese avant ?'",
    },
    {
        "numero": 26,
        "objection": "Je dois en parler a mon associe (en closing)",
        "reponse": "Qu'est-ce que vous allez lui dire en priorite ? Voulez-vous qu'on l'appelle ensemble ?",
        "technique_adera": "A: Accueillir. D: 'De quoi a-t-il besoin ?' E: Valider. R: Faire du client un relais actif. A: Proposer un RDV a 3.",
    },
    {
        "numero": 27,
        "objection": "Montrez-moi directement les chiffres (en R2)",
        "reponse": "Les chiffres n'ont de sens que quand on a valide la realite. Sinon, on parle dans le vide.",
        "technique_adera": "A: Accueillir sans obeir. D: 'Qu'est-ce que vous voulez verifier en priorite ?' E: 'Je comprends l'impatience.' R: Recadrer calmement — erreur = sauter les etapes. A: 'On y arrive dans 5 minutes.'",
    },
    {
        "numero": 28,
        "objection": "Je veux relire tout a tete reposee",
        "reponse": "Bien sur, qu'est-ce que vous voulez verifier avant de valider ?",
        "technique_adera": "A: Accueillir. D: 'Quel point precis voulez-vous revoir ?' E: 'C'est normal de prendre le temps.' R: Isoler le doute reel — c'est souvent une fuite emotionnelle masquee en rationalite. A: Proposer un RDV de suivi.",
    },
    {
        "numero": 29,
        "objection": "C'est interessant mais pas pour maintenant",
        "reponse": "Les tarifs CEE/rachat baissent chaque trimestre. Chaque mois d'attente reduit la valorisation. L'etude gratuite vous donne l'info pour decider quand ce sera le bon moment.",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qui changerait dans 6 mois ?' E: 'Le timing compte.' R: Urgence factuelle — baisse baremes. A: 'Etude gratuite = liberte de decider plus tard avec les bonnes donnees.'",
    },
    {
        "numero": 30,
        "objection": "J'attends les prochaines aides / la nouvelle reglementation",
        "reponse": "Les aides actuelles sont les plus hautes. La tendance est a la baisse. Les baremes CEE P6 sont en vigueur maintenant — ils ne sont pas garantis pour P7.",
        "technique_adera": "A: Accueillir. D: 'Quelles aides attendez-vous ?' E: 'C'est une reflexion logique.' R: Urgence factuelle — tendance baissiere documentee. A: 'On verifie ensemble ce qui est disponible maintenant.'",
    },
    {
        "numero": 31,
        "objection": "Votre concurrent est moins cher",
        "reponse": "C'est normal. Comparez ce qui est equivalent : garanties, SAV, qualite du materiel, assurance, RGE. Le prix n'est qu'une ligne du projet.",
        "technique_adera": "A: Accueillir. D: 'Sur quels criteres comparez-vous exactement ?' E: 'C'est une demarche saine.' R: Revaloriser la qualite. A: 'Comparez l'offre complete.'",
    },
    {
        "numero": 32,
        "objection": "Je ne crois pas aux economies annoncees",
        "reponse": "Les economies sont basees sur VOS donnees reelles, pas des estimations generiques. L'etude est verifiable par votre comptable.",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qui vous fait douter ?' E: 'C'est normal d'etre sceptique.' R: Donnees reelles + transparence. A: 'On peut verifier ensemble.'",
    },
    {
        "numero": 33,
        "objection": "Mon batiment est trop vieux / pas adapte",
        "reponse": "Justement, les batiments anciens sont souvent les plus eligibles aux CEE car le potentiel d'economies est maximal.",
        "technique_adera": "A: Accueillir. D: 'De quand date votre batiment ?' E: 'C'est une preoccupation legitime.' R: Les vieux batiments = plus d'economies. A: 'On verifie la compatibilite en 15 min.'",
    },
    {
        "numero": 34,
        "objection": "Ca ne marche pas dans ma region / mon climat",
        "reponse": "La France entiere est eligible. Et les zones H1 (froid) ont les meilleures primes CEE precisement parce qu'on chauffe plus.",
        "technique_adera": "A: Accueillir. D: 'Vous etes dans quelle zone ?' E: 'C'est logique de se poser la question.' R: Zone H1 = primes maximales. A: 'Votre zone est en fait prioritaire.'",
    },
    {
        "numero": 35,
        "objection": "J'ai peur des travaux / du chantier",
        "reponse": "On gere tout : planning, coordination, SAV. Nos chantiers durent en moyenne 3-5 jours, sans interruption d'activite.",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qui vous inquiete le plus ?' E: 'C'est normal.' R: Duree courte + zero perturbation. A: 'On fait un planning avant de demarrer.'",
    },
    {
        "numero": 36,
        "objection": "Je vais attendre la fin de mon bail / contrat",
        "reponse": "L'etude gratuite est valable maintenant. Les conditions vont changer. Mieux vaut avoir l'info et decider au bon moment.",
        "technique_adera": "A: Accueillir. D: 'Votre bail se termine quand ?' E: 'C'est une bonne gestion.' R: Dissocier l'etude de l'engagement. A: 'L'etude vous donne le choix.'",
    },
    {
        "numero": 37,
        "objection": "J'ai entendu des mauvaises choses sur le solaire / les CEE",
        "reponse": "Il y a eu des abus dans le secteur, c'est vrai. C'est pour ca qu'on est certifies RGE, qu'on fonctionne sans acompte, et que l'etude est gratuite.",
        "technique_adera": "A: Accueillir. D: 'Qu'avez-vous entendu exactement ?' E: 'Je comprends la mefiance.' R: Transparence + certifications + zero risque. A: 'Verifiez par vous-meme.'",
    },
    {
        "numero": 38,
        "objection": "Mon electricien peut le faire",
        "reponse": "Est-il certifie RGE pour cette operation specifique ? Sans RGE, pas de prime CEE, pas de contrat S21.",
        "technique_adera": "A: Accueillir. D: 'Il a la certification RGE correspondante ?' E: 'C'est naturel de faire confiance a son electricien.' R: Condition RGE = obligatoire. A: 'On peut completer son travail si besoin.'",
    },
    {
        "numero": 39,
        "objection": "Le retour sur investissement est trop long",
        "reponse": "En autofinancement, le projet se rembourse des la premiere annee via les economies. Le ROI n'est pas un delai, c'est un flux permanent.",
        "technique_adera": "A: Accueillir. D: 'Quel delai vous semble acceptable ?' E: 'C'est normal de vouloir un retour rapide.' R: Economies immediates > ROI theorique. A: 'L'etude calcule votre flux reel.'",
    },
    {
        "numero": 40,
        "objection": "On est en pleine restructuration / demenagement",
        "reponse": "Justement, une etude maintenant vous donne un levier de negociation pour le nouveau local ou le repreneur.",
        "technique_adera": "A: Accueillir. D: 'Vous demenagez dans quel secteur ?' E: 'C'est une periode chargee.' R: L'etude = atout strategique. A: 'On cale ca en 15 min.'",
    },
    {
        "numero": 41,
        "objection": "Ca ne sert a rien si c'est un locataire qui paye les charges",
        "reponse": "Justement, les travaux valorisent votre patrimoine, ameliorent le DPE et attirent de meilleurs locataires. Et les CEE financent les travaux.",
        "technique_adera": "A: Accueillir. D: 'Qui paye les charges energetiques exactement ?' E: 'C'est une question pertinente.' R: Valorisation patrimoine + DPE + attraction locataires. A: 'On regarde l'angle proprietaire.'",
    },
    {
        "numero": 42,
        "objection": "J'ai deja des panneaux solaires",
        "reponse": "On peut optimiser l'existant : ajout batterie, augmentation puissance, revente surplus. Et les CEE concernent aussi l'isolation, la GTB, le chauffage.",
        "technique_adera": "A: Accueillir. D: 'Quelle puissance avez-vous ? Autoconsommation ou revente ?' E: 'Bravo pour l'investissement.' R: Complementarite — optimisation + autres postes. A: 'On fait un bilan global.'",
    },
    {
        "numero": 43,
        "objection": "Pas le temps la, rappelez-moi dans 3 mois",
        "reponse": "Bien sur. Mais en 3 mois, les baremes peuvent baisser. Une seule question rapide : votre batiment fait quelle surface ? Si c'est eligible, on cale un creneau precis.",
        "technique_adera": "A: Accueillir. D: 'Une seule question...' E: 'Je comprends.' R: Micro-engagement + urgence douce. A: 'Je note dans mon agenda et je vous rappelle [date precise].'",
    },
    {
        "numero": 44,
        "objection": "Votre entreprise, je la connais pas / jamais entendu parler",
        "reponse": "Normal, on travaille en B2B, pas en pub grand public. +140 projets depuis 2009, certifies RGE, accredites DGEC. On peut vous envoyer des references dans votre secteur.",
        "technique_adera": "A: Accueillir. D: 'Qu'est-ce qui vous rassurerait ?' E: 'C'est normal en B2B.' R: References + certifications + anciennete. A: 'Je vous envoie 2-3 references proches de chez vous.'",
    },
]

# ---------------------------------------------------------------------------
# 6 Methodes de Closing
# Source : 6 METHODES DE CLOSINGS.pages / Synthese Techniques Vente
# ---------------------------------------------------------------------------

SIX_CLOSINGS = [
    {
        "nom": "Illusion du choix",
        "description": "Proposer 2 options qui menent toutes les deux au oui.",
        "exemple": "'On demarre en juin ou en septembre ?' Les deux = signature.",
        "quand_utiliser": "Quand le client hesite entre deux configurations.",
    },
    {
        "nom": "Projection future",
        "description": "Parler au futur comme si c'etait deja decide.",
        "exemple": "'Quand les travaux seront faits, vous constaterez...' Le client se projette = il achete.",
        "quand_utiliser": "Quand le client est a 70%+ convaincu.",
    },
    {
        "nom": "Anti-vente",
        "description": "Refuser de vendre pour creer de la valeur.",
        "exemple": "'Si vous preferez les fixes, on ne les installera pas. Nos ingenieurs refusent.' Puis silence absolu.",
        "quand_utiliser": "Quand le client hesite entre votre solution et un concurrent inferieur.",
    },
    {
        "nom": "Validation d'expert",
        "description": "Cloturer sans jamais prononcer 'signature' — c'est une consequence logique.",
        "exemple": "'On valide l'etude et on programme la suite.' / 'On valide qu'on lance la preparation du dossier ?'",
        "quand_utiliser": "Closing standard R2. A utiliser systematiquement.",
    },
    {
        "nom": "Silence apres le prix",
        "description": "Apres l'annonce du prix : 2 a 4 secondes de silence. Celui qui parle en premier perd.",
        "exemple": "Tu dis le montant. Tu fermes la bouche. Tu le regardes. 3 secondes minimum.",
        "quand_utiliser": "Juste apres l'annonce du plan de financement.",
    },
    {
        "nom": "3 Urgences",
        "description": "Combiner 3 urgences : Planning + Tarif + Competition.",
        "exemple": "'1 seul creneau en avril. +5% fournisseur au 1er avril. Premier camping autonome de la region.'",
        "quand_utiliser": "Closing telephonique ou closing difficile.",
    },
]

# ---------------------------------------------------------------------------
# Banque de questions statique — 12 modules
# ---------------------------------------------------------------------------

MODULES = {
    # -----------------------------------------------------------------------
    # MODULE 1 — R1 Decouverte SPIN (30 questions)
    # Source : Formation QCM – Methodes de Vente & Rendez-vous de Decouverte (R1)
    # -----------------------------------------------------------------------
    "1": {
        "id": "1",
        "titre": "R1 — Decouverte SPIN",
        "description": "30 questions sur le rendez-vous de decouverte, la methode SPIN, le timing, les KPIs R1.",
        "nb_questions": 30,
        "source": "Formation QCM – Methodes de Vente & Rendez-vous de Decouverte (R1).docx",
        "questions": [
            {"id": "q1", "question": "Quel est l'objectif principal d'un rendez-vous R1 ?",
             "options": ["A) Signer le client", "B) Decouvrir ses besoins et qualifier", "C) Presenter le produit", "D) Repondre a ses objections"],
             "reponse_correcte": "B", "explication": "Objectif : comprendre la situation du client, son contexte energetique, ses motivations et freins avant toute presentation.", "source": "QCM R1 — Q1"},
            {"id": "q2", "question": "Que signifie le 'S' de la methode SPIN ?",
             "options": ["A) Situation", "B) Solution", "C) Satisfaction", "D) Securite"],
             "reponse_correcte": "A", "explication": "C'est la premiere etape du SPIN : comprendre la situation actuelle du prospect.", "source": "QCM R1 — Q2"},
            {"id": "q3", "question": "Lors du R1, a quel moment doit-on aborder le budget ?",
             "options": ["A) En tout debut d'appel", "B) Apres avoir explore les besoins", "C) Juste avant la cloture", "D) Jamais au R1"],
             "reponse_correcte": "B", "explication": "Le budget se traite apres avoir eveille la valeur du projet. Parler d'argent trop tot = reduction du projet a un prix.", "source": "QCM R1 — Q3"},
            {"id": "q4", "question": "Quel indicateur mesure le pourcentage de R1 realises sur le total des leads ?",
             "options": ["A) Taux VT / Leads", "B) Taux Signature / R2", "C) Taux R1 / Leads", "D) Taux Chute"],
             "reponse_correcte": "C", "explication": "KPI fondamental pour mesurer le ratio de rendez-vous qualifies sur leads recus. Cible : > 45%.", "source": "QCM R1 — Q4"},
            {"id": "q5", "question": "Si le prospect dit : 'Je veux juste un devis pour comparer', que doit faire le commercial ?",
             "options": ["A) Envoyer un devis tout de suite", "B) Chercher a comprendre son contexte et ses criteres de choix", "C) Refuser le contact", "D) Le transferer au service technique"],
             "reponse_correcte": "B", "explication": "Un client qui 'compare' cherche souvent une validation emotionnelle. 'Qu'est-ce qui fera la difference pour vous entre deux installateurs ?'", "source": "QCM R1 — Q5"},
            {"id": "q6", "question": "Quelle attitude favorise la confiance en R1 ?",
             "options": ["A) Parler beaucoup", "B) Poser des questions ouvertes", "C) Donner des details techniques des le debut", "D) Rester neutre et distant"],
             "reponse_correcte": "B", "explication": "L'ecoute active cree la confiance et la credibilite.", "source": "QCM R1 — Q6"},
            {"id": "q7", "question": "Quelle est la premiere etape de la methode SPIN ?",
             "options": ["A) Identifier les problemes", "B) Creer l'urgence", "C) Poser des questions sur la situation actuelle", "D) Presenter la solution"],
             "reponse_correcte": "C", "explication": "Phase initiale du SPIN : on explore la situation sans juger.", "source": "QCM R1 — Q7"},
            {"id": "q8", "question": "Quelle est la bonne pratique pour cloturer un R1 reussi ?",
             "options": ["A) Fixer la date de visite technique (VT)", "B) Envoyer un devis par mail", "C) Attendre le rappel du client", "D) Passer directement a la presentation commerciale"],
             "reponse_correcte": "A", "explication": "Le R1 n'a de valeur que s'il debouche sur une action claire : planifier la suite.", "source": "QCM R1 — Q8"},
            {"id": "q9", "question": "Le taux de chute correspond a :",
             "options": ["A) Les clients perdus entre R2 et Signature", "B) Les leads KO + OR sur le total des leads fournis", "C) Les leads refuses", "D) Les leads en attente"],
             "reponse_correcte": "B", "explication": "Ce KPI mesure les pertes. 10 KO + 5 OR sur 100 leads = Taux de chute 15%. Objectif : < 15%.", "source": "QCM R1 — Q9"},
            {"id": "q10", "question": "Pourquoi faut-il eviter de presenter le produit trop tot ?",
             "options": ["A) Cela allonge l'entretien", "B) Cela empeche la decouverte reelle des besoins", "C) Cela reduit le taux de transformation", "D) B et C sont vrais"],
             "reponse_correcte": "D", "explication": "Trop de precipitation tue la vente : le client ne s'exprime pas, on ne comprend pas sa logique.", "source": "QCM R1 — Q10"},
            {"id": "q11", "question": "Dans la methode SPIN, la question 'Si vous ne changez rien, quelles seront les consequences ?' appartient a :",
             "options": ["A) Situation", "B) Probleme", "C) Implication", "D) Necessite"],
             "reponse_correcte": "C", "explication": "Question d'implication. Elle fait ressentir le cout de l'inaction.", "source": "QCM R1 — Q11"},
            {"id": "q12", "question": "Un prospect dit : 'Je n'ai pas confiance dans les installateurs.' Quelle est la meilleure reponse ?",
             "options": ["A) 'Nos techniciens sont certifies RGE et nous avons +500 installations/an.'", "B) 'C'est pour ca que je vous appelle, pour vous prouver qu'on est differents.'", "C) 'Pouvez-vous me dire ce qui vous a fait perdre confiance ?'", "D) 'Ce n'est pas notre cas.'"],
             "reponse_correcte": "C", "explication": "L'ecoute transforme la mefiance en dialogue. Ensuite, on reconstruit la confiance par preuve sociale.", "source": "QCM R1 — Q12"},
            {"id": "q13", "question": "Le role du R1 est de :",
             "options": ["A) Creer le lien, comprendre et orienter le client vers la bonne suite (VT ou non)", "B) Convaincre coute que coute", "C) Parler de la rentabilite", "D) Clore immediatement la vente"],
             "reponse_correcte": "A", "explication": "Le R1, c'est la porte d'entree, pas la conclusion.", "source": "QCM R1 — Q13"},
            {"id": "q14", "question": "Si un lead est en 'hors cible', que faut-il faire ?",
             "options": ["A) Le garder dans le pipeline", "B) Le marquer 'hors cible' pour fiabiliser les KPI", "C) L'appeler quand meme", "D) Le supprimer"],
             "reponse_correcte": "B", "explication": "Cela alimente les KPI de qualite de leads. Lead locataire = hors cible = exclu du calcul R1/Leads.", "source": "QCM R1 — Q14"},
            {"id": "q15", "question": "Quand un prospect dit : 'Je n'ai pas encore reflechi', quelle est la bonne approche ?",
             "options": ["A) Cloturer l'appel", "B) Explorer les motivations derriere l'interet initial", "C) Donner le tarif pour accelerer la reflexion", "D) Le relancer plus tard sans insister"],
             "reponse_correcte": "B", "explication": "Derriere 'je n'ai pas reflechi' se cache souvent une curiosite ou peur. 'Qu'est-ce qui vous a pousse a cliquer sur notre annonce ?'", "source": "QCM R1 — Q15"},
            {"id": "q16", "question": "Lorsqu'un client repond peu, quelle technique fonctionne le mieux ?",
             "options": ["A) Questions fermees rapides", "B) Silence + relance douce ('Dites-m'en un peu plus...')", "C) Argumenter plus", "D) Donner un exemple client"],
             "reponse_correcte": "B", "explication": "Le silence pousse le client a completer sa pensee.", "source": "QCM R1 — Q16"},
            {"id": "q17", "question": "Quel KPI permet de mesurer la qualite du passage de R1 a VT ?",
             "options": ["A) Taux VT / R1", "B) Taux VT / Leads", "C) Taux Signature / Leads", "D) Taux Chute"],
             "reponse_correcte": "A", "explication": "KPI-cle pour mesurer la qualite de decouverte. Si < 40%, le discours decouverte est a revoir.", "source": "QCM R1 — Q17"},
            {"id": "q18", "question": "Lors du R1, pourquoi est-il essentiel de noter toutes les informations dans Monday ?",
             "options": ["A) Pour le suivi automatise, la relance et la fiabilite des taux", "B) Pour faire joli", "C) Pour partager au marketing", "D) Ce n'est pas necessaire"],
             "reponse_correcte": "A", "explication": "Monday permet automatisations + relances. Un R1 non note = relance manuelle oubliee = perte de lead.", "source": "QCM R1 — Q18"},
            {"id": "q19", "question": "Quel est le bon timing de relance apres un R1 sans retour client ?",
             "options": ["A) Le jour meme", "B) J+2", "C) J+5", "D) Une semaine plus tard"],
             "reponse_correcte": "B", "explication": "J+2 selon les scripts commerciaux. 'On s'etait parle lundi. Je voulais voir si vous aviez pu avancer.'", "source": "QCM R1 — Q19"},
            {"id": "q20", "question": "Quelle question de decouverte est la plus efficace ?",
             "options": ["A) 'Voulez-vous economiser sur votre facture ?'", "B) 'Qu'est-ce qui vous a donne envie de vous renseigner aujourd'hui ?'", "C) 'Etes-vous proprietaire ?'", "D) 'Quel budget avez-vous prevu ?'"],
             "reponse_correcte": "B", "explication": "Question d'ouverture emotionnelle = declenche le vrai besoin.", "source": "QCM R1 — Q20"},
            {"id": "q21", "question": "Le client dit : 'Je dois en parler a ma femme.' Quelle strategie appliquer ?",
             "options": ["A) Proposer de fixer le VT avec les deux presents", "B) Forcer la decision", "C) Insister sur la promo", "D) Cloturer"],
             "reponse_correcte": "A", "explication": "Permet d'impliquer le decideur reel. 'On peut planifier une visite a deux.'", "source": "QCM R1 — Q21"},
            {"id": "q22", "question": "En fin de R1, le client dit 'Je vais reflechir'. Quelle phrase est la plus performante ?",
             "options": ["A) 'Tres bien, je vous laisse mon numero.'", "B) 'Justement, la visite technique sert a valider si le projet est pertinent pour vous.'", "C) 'Reflechissez bien, c'est une opportunite rare.'", "D) 'Je vous rappelle demain.'"],
             "reponse_correcte": "B", "explication": "On transforme une objection en progression naturelle. 'La visite est gratuite et sans engagement.'", "source": "QCM R1 — Q22"},
            {"id": "q23", "question": "Si le taux de R1 est bon mais le taux de VT faible, quelle est la cause probable ?",
             "options": ["A) Manque de qualification en R1", "B) Mauvaise base de leads", "C) Manque de relance", "D) Manque d'argumentaire VT"],
             "reponse_correcte": "A", "explication": "Mauvaise decouverte = VT non justifiee.", "source": "QCM R1 — Q23"},
            {"id": "q24", "question": "Lorsqu'un client exprime une objection sur le prix, la meilleure approche est :",
             "options": ["A) Revenir a la valeur percue avant le prix", "B) Proposer une reduction", "C) Minimiser le cout", "D) Changer de sujet"],
             "reponse_correcte": "A", "explication": "Le prix se defend par la valeur. 'Oui, c'est un investissement, mais qui vous fait economiser environ 900 EUR/an pendant 25 ans.'", "source": "QCM R1 — Q24"},
            {"id": "q25", "question": "Vous devez reformuler un besoin mal exprime. Quelle phrase est la plus efficace ?",
             "options": ["A) 'Donc si je comprends bien, votre priorite c'est de reduire vos factures, mais sans degrader votre confort ?'", "B) 'Vous voulez donc acheter ?'", "C) 'Je vous envoie un devis.'", "D) 'Expliquez encore.'"],
             "reponse_correcte": "A", "explication": "Reformulation empathique et precise.", "source": "QCM R1 — Q25"},
            {"id": "q26", "question": "En situation d'objection 'Je veux reflechir', la technique la plus puissante est :",
             "options": ["A) Explorer ce qu'il veut clarifier avant de dire 'OK, reflechissez'", "B) Mettre la pression avec une offre limitee", "C) Accepter sans question", "D) Rappeler le lendemain"],
             "reponse_correcte": "A", "explication": "'Qu'est-ce que vous aimeriez clarifier avant d'avancer ?' = lever l'objection reelle.", "source": "QCM R1 — Q26"},
            {"id": "q27", "question": "Si le client ne veut pas donner sa facture EDF, quelle reaction adopter ?",
             "options": ["A) Expliquer calmement pourquoi elle est necessaire (dimensionnement, puissance, ROI)", "B) Insister fermement", "C) Passer a la suite", "D) Refuser de poursuivre"],
             "reponse_correcte": "A", "explication": "La facture permet de calculer la bonne puissance, pour ne pas surdimensionner.", "source": "QCM R1 — Q27"},
            {"id": "q28", "question": "Un bon R1 se termine par :",
             "options": ["A) Une date de VT validee et notee dans Monday", "B) Une promesse de rappel", "C) Un mail de presentation", "D) Rien de particulier"],
             "reponse_correcte": "A", "explication": "Le vrai indicateur d'un R1 reussi. 'VT fixee le jeudi 17h avec M. et Mme Dupont = item mis a jour.'", "source": "QCM R1 — Q28"},
            {"id": "q29", "question": "Quel est le risque principal d'un R1 'trop long' ?",
             "options": ["A) Fatiguer le client et perdre le focus sur la decision prochaine (VT)", "B) Mieux comprendre le besoin", "C) Montrer de l'interet", "D) Aucun"],
             "reponse_correcte": "A", "explication": "Un R1 efficace dure 20-30 min max, avec une structure claire.", "source": "QCM R1 — Q29"},
            {"id": "q30", "question": "Quelle competence distingue les meilleurs closers des le R1 ?",
             "options": ["A) L'ecoute active et la reformulation de valeur", "B) Le charisme et la persuasion", "C) La rapidite d'argumentation", "D) Le ton de voix"],
             "reponse_correcte": "A", "explication": "Les meilleurs closers parlent peu, ecoutent et recadrent.", "source": "QCM R1 — Q30"},
        ],
    },

    # -----------------------------------------------------------------------
    # MODULE 2 — R2 Presentation et Validation (40 questions)
    # Source : formation QCM R2 — L'Art de la Presentation et de la Validation
    # -----------------------------------------------------------------------
    "2": {
        "id": "2",
        "titre": "R2 — Presentation et Validation",
        "description": "40 questions sur les phases du R2, la tension de decision, le leadership emotionnel.",
        "nb_questions": 40,
        "source": "formation QCM R2 — L'Art de la Presentation et de la Validation.docx",
        "questions": [
            {"id": "q1", "question": "Quel est le veritable objectif d'un R2 ?", "options": ["A) Vendre", "B) Valider la coherence et la faisabilite", "C) Presenter le prix", "D) Conclure la vente"], "reponse_correcte": "B", "explication": "Le R2 n'est pas une cloture, c'est une validation intellectuelle. La vente se fait en creux, par clarte.", "source": "QCM R2 — Q1"},
            {"id": "q2", "question": "Le client dit 'Montrez-moi directement les chiffres'. Quelle erreur commettent 90% des vendeurs ?", "options": ["A) Ils refusent", "B) Ils obeissent et sautent les etapes", "C) Ils changent de sujet", "D) Ils augmentent le prix"], "reponse_correcte": "B", "explication": "Erreur = obeir. Sauter les etapes = perdre la maitrise emotionnelle. 'Les chiffres n'ont de sens que quand on a valide la realite.'", "source": "QCM R2 — Q2"},
            {"id": "q3", "question": "A quel moment commence reellement un R2 ?", "options": ["A) A la presentation", "B) Au partage d'ecran", "C) Des la reprise de contact et l'ancrage emotionnel", "D) A l'annonce du prix"], "reponse_correcte": "C", "explication": "Ton, rythme, calme posent la perception d'expert avant meme ton contenu.", "source": "QCM R2 — Q3"},
            {"id": "q4", "question": "Pourquoi reformuler le R1 au debut du R2 ?", "options": ["A) Pour gagner du temps", "B) Pour raviver la raison initiale de la demarche (ancre emotionnelle)", "C) Par politesse", "D) Pour verifier les infos"], "reponse_correcte": "B", "explication": "Reactivation du desir initial. 'Si je resume, vous cherchiez a reduire vos couts sans perdre en confort ?'", "source": "QCM R2 — Q4"},
            {"id": "q5", "question": "Quelle est la difference entre 'rassurer' et 'valider' un client ?", "options": ["A) Aucune", "B) Rassurer = apaiser ; Valider = faire ressentir la solidite du raisonnement", "C) Valider est plus agressif", "D) Rassurer est mieux"], "reponse_correcte": "B", "explication": "Le client ne veut pas etre apaise, il veut etre convaincu qu'il est logique.", "source": "QCM R2 — Q5"},
            {"id": "q6", "question": "Si le client hoche la tete souvent, est-ce forcement bon signe ?", "options": ["A) Oui toujours", "B) Non, risque de desengagement passif", "C) Ca depend du produit", "D) Ca ne veut rien dire"], "reponse_correcte": "B", "explication": "Un 'oui' sans regard = fuite. 'Je vous sens d'accord, mais qu'en pensez-vous vraiment ?'", "source": "QCM R2 — Q6"},
            {"id": "q7", "question": "Quelle intonation vocale utiliser en ouverture de R2 ?", "options": ["A) Energique et enthousiaste", "B) Calme, descendante, presque confidentielle", "C) Forte et assuree", "D) Rapide et dynamique"], "reponse_correcte": "B", "explication": "Un ton neutre capte mieux qu'une voix commerciale.", "source": "QCM R2 — Q7"},
            {"id": "q8", "question": "Pourquoi est-il dangereux de commencer un R2 en parlant d'aides ou de subventions ?", "options": ["A) C'est illegal", "B) Ca tue la credibilite — le client pense 'commercial'", "C) Les aides ne sont pas importantes", "D) Ca prend trop de temps"], "reponse_correcte": "B", "explication": "Le client te classe immediatement comme 'vendeur'. Les aides viennent APRES la valeur.", "source": "QCM R2 — Q8"},
            {"id": "q9", "question": "Comment une pause de silence de 3 secondes transforme la perception en R2 ?", "options": ["A) Elle cree un malaise", "B) Elle cree de la gravite et du respect", "C) Elle n'a aucun effet", "D) Elle perd le client"], "reponse_correcte": "B", "explication": "Le silence te donne du poids, il impose la reflexion.", "source": "QCM R2 — Q9"},
            {"id": "q10", "question": "Quelle est la difference entre un R2 'interessant' et un R2 'impactant' ?", "options": ["A) Aucune", "B) L'impactant cree une decision interieure, il deplace le curseur de certitude", "C) L'interessant est mieux", "D) L'impactant est plus long"], "reponse_correcte": "B", "explication": "Un bon R2 ne seduit pas, il deplace le curseur de certitude.", "source": "QCM R2 — Q10"},
            {"id": "q11", "question": "Pourquoi le mot 'coherence' est plus efficace que 'rentabilite' ?", "options": ["A) C'est plus court", "B) 'Coherence' active le cortex rationnel, 'rentabilite' declenche la mefiance", "C) C'est pareil", "D) 'Rentabilite' est un meilleur mot"], "reponse_correcte": "B", "explication": "'Coherence' donne legitimite. 'Notre objectif, c'est de verifier la coherence du projet avec vos besoins reels.'", "source": "QCM R2 — Q11"},
            {"id": "q12", "question": "Comment un detail technique mal introduit peut detruire un R2 ?", "options": ["A) Ca ne change rien", "B) Ca fait chuter la tension emotionnelle", "C) Ca impressionne le client", "D) Ca donne de la credibilite"], "reponse_correcte": "B", "explication": "Trop de donnees = perte de magie. 'D'abord la logique globale, puis le detail.'", "source": "QCM R2 — Q12"},
            {"id": "q13", "question": "Quelle est la premiere phrase a bannir apres une simulation positive ?", "options": ["A) 'C'est bien'", "B) 'Vous voyez, c'est interessant !'", "C) 'On continue ?'", "D) 'Des questions ?'"], "reponse_correcte": "B", "explication": "Tu casses la tension. Tu valides toi-meme, au lieu de laisser le client valider. Silence + sourire.", "source": "QCM R2 — Q13"},
            {"id": "q14", "question": "Pourquoi laisser un 'espace d'incertitude' en fin de R2 ?", "options": ["A) Pour embrouiller le client", "B) Pour creer une tension positive — le client doit combler le vide avec une decision", "C) Par manque de preparation", "D) Ca n'a pas d'interet"], "reponse_correcte": "B", "explication": "'On validera ensemble si c'est le bon moment... ou pas.'", "source": "QCM R2 — Q14"},
            {"id": "q15", "question": "Pourquoi utiliser 'on' plutot que 'je' en R2 ?", "options": ["A) Par humilite", "B) 'On' = inclusion = confiance", "C) C'est plus poli", "D) Ca n'a pas d'importance"], "reponse_correcte": "B", "explication": "'On va voir ensemble si l'etude est coherente.'", "source": "QCM R2 — Q15"},
            {"id": "q16", "question": "Pourquoi la phrase 'C'est a vous de voir' sabote la decision ?", "options": ["A) Elle est polie", "B) C'est un faux liberalisme — le client veut etre guide, pas abandonne", "C) Elle donne confiance", "D) Elle est efficace"], "reponse_correcte": "B", "explication": "Remplacer par : 'Voyons si on a raison d'y aller maintenant.'", "source": "QCM R2 — Q16"},
            {"id": "q17", "question": "Quand 'Je comprends' devient un desengagement ?", "options": ["A) Jamais", "B) Quand il n'est pas suivi d'une reformulation", "C) Quand on le dit trop fort", "D) Toujours"], "reponse_correcte": "B", "explication": "Sans miroir, c'est vide. 'Je comprends... vous voulez dire que le timing vous freine, c'est ca ?'", "source": "QCM R2 — Q17"},
            {"id": "q18", "question": "Quand un client dit 'Je vais reflechir', quelle est la vraie nature psychologique dans 80% des cas ?", "options": ["A) Il va vraiment reflechir", "B) Doute emotionnel, pas rationnel", "C) Il attend un meilleur prix", "D) Il est indifferent"], "reponse_correcte": "B", "explication": "Il n'a pas peur du prix, mais de se tromper. 'Qu'est-ce que vous voulez clarifier avant d'avancer ?'", "source": "QCM R2 — Q18"},
            {"id": "q19", "question": "Quelle difference entre un client qui reflechit et un client qui evite ?", "options": ["A) Aucune", "B) L'un questionne, l'autre fuit (regard fuyant, sourire excessif)", "C) L'evitant parle plus", "D) Le reflexif est pire"], "reponse_correcte": "B", "explication": "'Je prefere qu'on parle franchement, meme si c'est non.'", "source": "QCM R2 — Q19"},
            {"id": "q20", "question": "Quel est le bon ordre de presentation technique en R2 ?", "options": ["A) Prix > Economies > Production", "B) Production > Economies > Financement", "C) Aides > Prix > Production", "D) L'ordre n'a pas d'importance"], "reponse_correcte": "B", "explication": "Crescendo : cerveau rationnel (production) > emotion (economies) > concret (financement).", "source": "QCM R2 — Q20"},
            {"id": "q21", "question": "A quoi sert le contraste narratif en R2 ?", "options": ["A) A faire joli", "B) A comparer la vie 'avec' et 'sans' le projet — le cerveau comprend par contraste", "C) A perdre du temps", "D) A embrouiller"], "reponse_correcte": "B", "explication": "'Aujourd'hui, vous depensez X. Avec l'etude, on stabilise la charge.'", "source": "QCM R2 — Q21"},
            {"id": "q22", "question": "Pourquoi une objection sur le prix n'est presque jamais une objection sur l'argent ?", "options": ["A) Parce que le client ment", "B) C'est un doute de valeur, pas de moyens — traiter la perception, pas le portefeuille", "C) Le prix est toujours juste", "D) Ca n'arrive pas"], "reponse_correcte": "B", "explication": "'Quand vous dites cher, c'est par rapport a quoi ?'", "source": "QCM R2 — Q22"},
            {"id": "q23", "question": "A quel moment le client decide emotionnellement ?", "options": ["A) A la fin", "B) Pendant ta reformulation miroir — il decide quand il s'entend valider", "C) Au debut", "D) Jamais"], "reponse_correcte": "B", "explication": "'Donc votre priorite, c'est d'etre autonome a 80% ?' (silence)", "source": "QCM R2 — Q23"},
            {"id": "q24", "question": "Comment identifier un 'faux oui' ?", "options": ["A) C'est impossible", "B) Accords plats, peu d'emotions, regard fuyant, ton neutre", "C) Le client sourit", "D) Le client pose des questions"], "reponse_correcte": "B", "explication": "'Je vous sens prudent, qu'est-ce qui reste flou ?'", "source": "QCM R2 — Q24"},
            {"id": "q25", "question": "Pourquoi certains vendeurs sabotent leur closing en cherchant a conclure trop proprement ?", "options": ["A) Ils sont trop professionnels", "B) Ca tue la tension — le client respire = fin de tension = pas de decision", "C) Ca n'arrive pas", "D) C'est une bonne chose"], "reponse_correcte": "B", "explication": "'On valide si on avance, ou on s'arrete ici ?'", "source": "QCM R2 — Q25"},
            {"id": "q26", "question": "Quelle est la frontiere entre convaincre et influencer ?", "options": ["A) C'est pareil", "B) Convaincre = forcer ; Influencer = faire comprendre (liberte dirigee)", "C) Influencer est pire", "D) Convaincre est mieux"], "reponse_correcte": "B", "explication": "'Je ne veux pas vous convaincre, je veux que ce soit clair.'", "source": "QCM R2 — Q26"},
            {"id": "q27", "question": "Quand une phrase humoristique devient une fuite d'autorite ?", "options": ["A) Jamais", "B) Quand elle sert a seduire plutot qu'a detendre — elle casse la posture d'expert", "C) Toujours", "D) Ca n'a pas d'impact"], "reponse_correcte": "B", "explication": "Client rigole = tu souris, mais tu reprends le fil calmement.", "source": "QCM R2 — Q27"},
            {"id": "q28", "question": "Quand le client se justifie tout seul, que se passe-t-il ?", "options": ["A) Il est confus", "B) Il est deja en train de se convaincre — ne pas l'interrompre", "C) Il veut partir", "D) Il ment"], "reponse_correcte": "B", "explication": "Laisser verbaliser. 'Oui, c'est vrai que ca ferait sens vu les hausses...'", "source": "QCM R2 — Q28"},
            {"id": "q29", "question": "Quelle formule de cloture fait basculer un R2 de dialogue commercial a validation d'expert ?", "options": ["A) 'On signe ?'", "B) 'On valide qu'on passe a la visite technique.'", "C) 'Ca vous va ?'", "D) 'Alors, on fait quoi ?'"], "reponse_correcte": "B", "explication": "C'est concret, logique, pas 'vente'.", "source": "QCM R2 — Q29"},
            {"id": "q30", "question": "Comment un R2 doit-il se finir ?", "options": ["A) Sur une phrase de conclusion", "B) Sur une respiration — tu ne conclus pas, tu laisses decider", "C) Sur un resume", "D) Sur un merci"], "reponse_correcte": "B", "explication": "Tu termines. Tu respires. Il dit 'Oui'.", "source": "QCM R2 — Q30"},
            {"id": "q31", "question": "Le client dit 'Je dois en parler a mon associe'. Quelle erreur subtile ?", "options": ["A) Proposer d'attendre sa reponse", "B) Forcer la decision", "C) Ignorer", "D) Baisser le prix"], "reponse_correcte": "A", "explication": "L'erreur = attendre. Il faut revenir sur le contenu a transmettre. 'Qu'est-ce que vous allez lui dire en priorite ?'", "source": "QCM R2 — Q31"},
            {"id": "q32", "question": "Quelle est la valeur strategique d'une objection tardive en fin de R2 ?", "options": ["A) C'est une perte de temps", "B) C'est une emotion bloquee — remercier, pas contrer", "C) Ca n'arrive pas", "D) C'est mauvais signe"], "reponse_correcte": "B", "explication": "'Merci, c'est important que vous me le disiez maintenant.'", "source": "QCM R2 — Q32"},
            {"id": "q33", "question": "La reformulation de valeur inversee : 'C'est cher' → ?", "options": ["A) 'On peut baisser le prix'", "B) 'C'est cher, oui — c'est aussi ce qui le rend durable'", "C) 'C'est pas cher'", "D) 'Comparez avec les autres'"], "reponse_correcte": "B", "explication": "Revaloriser le reproche. Tu rends l'objection fiere d'elle-meme.", "source": "QCM R2 — Q33"},
            {"id": "q34", "question": "Quelle phrase cloturer un R2 sans prononcer 'signature' ni 'accord' ?", "options": ["A) 'On signe ?'", "B) 'On valide l'etude et on programme la suite.'", "C) 'Vous etes d'accord ?'", "D) 'Ca marche ?'"], "reponse_correcte": "B", "explication": "Concret, pas contrat. 'On valide qu'on lance la preparation du dossier ?'", "source": "QCM R2 — Q34"},
            {"id": "q35", "question": "Le client ne doit jamais avoir l'impression d'avoir dit 'oui', mais plutot...", "options": ["A) D'avoir dit 'non'", "B) De ne pas avoir dit 'non' — l'accord doux est plus puissant", "C) D'avoir signe", "D) De s'etre fait forcer"], "reponse_correcte": "B", "explication": "'On voit si ca tient la route — rien n'est fige.'", "source": "QCM R2 — Q35"},
            {"id": "q36", "question": "Pourquoi un client veut 'voir plusieurs devis' meme apres un R2 parfait ?", "options": ["A) Pour comparer les prix", "B) Recherche de validation interne — il veut verifier qu'il a bien compris", "C) Il n'est pas interesse", "D) Il est radin"], "reponse_correcte": "B", "explication": "'C'est normal. Comparez, mais comparez ce qui est equivalent.'", "source": "QCM R2 — Q36"},
            {"id": "q37", "question": "Comment creer une tension d'inevitabilite sans forcer ?", "options": ["A) Mettre la pression", "B) Fermer le cadre, pas le client — l'impression que tout converge naturellement", "C) Menacer", "D) Faire un discount"], "reponse_correcte": "B", "explication": "'Dans tous les cas, vous devrez produire ou acheter. La question, c'est : a quel prix ?'", "source": "QCM R2 — Q37"},
            {"id": "q38", "question": "Un client plaisante trop en fin de R2. Qu'est-ce que cela signifie ?", "options": ["A) Il est a l'aise", "B) Signal d'evitement emotionnel — derriere la blague, une gene", "C) Il est convaincu", "D) Ca ne veut rien dire"], "reponse_correcte": "B", "explication": "'Je vois que ca vous fait sourire — ca vous parle, non ?'", "source": "QCM R2 — Q38"},
            {"id": "q39", "question": "Quelle phrase courte transforme une decision molle en engagement concret ?", "options": ["A) 'Reflechissez'", "B) 'On se lance ou on attend encore un peu ?'", "C) 'A vous de voir'", "D) 'Prenez votre temps'"], "reponse_correcte": "B", "explication": "Question douce fermee. Tu guides vers la decision sans contrainte.", "source": "QCM R2 — Q39"},
            {"id": "q40", "question": "Pourquoi le suivi post-R2 fait partie integrante de la vente ?", "options": ["A) Par politesse", "B) Le vide tue la decision — il faut combler par une presence maitrisee (recap + SMS humain)", "C) Ce n'est pas important", "D) Pour faire du reporting"], "reponse_correcte": "B", "explication": "Envoi du recap + SMS humain : 'Merci pour l'echange, on avance ensemble.'", "source": "QCM R2 — Q40"},
        ],
    },

    # -----------------------------------------------------------------------
    # MODULE 3 — Closing MAESTRO (30 questions)
    # Source : formation QCM – PHASE CLOSING "MAESTRO -.docx
    # -----------------------------------------------------------------------
    "3": {
        "id": "3",
        "titre": "Closing MAESTRO",
        "description": "30 questions sur le closing d'elite : posture, silence, tension, illusion du choix, anti-vente.",
        "nb_questions": 30,
        "source": "formation QCM – PHASE CLOSING MAESTRO.docx",
        "questions": [
            {"id": "q1", "question": "Quelle est la vraie mission d'un closing dans une vente consultative ?", "options": ["A) Obtenir la signature", "B) Valider la decision — pas 'obtenir la signature'", "C) Confirmer la coherence", "D) Les trois"], "reponse_correcte": "B", "explication": "Le closing n'est pas la fin de la vente, c'est le moment ou le client se rend compte que la decision logique, c'est d'avancer.", "source": "Closing MAESTRO — Q1"},
            {"id": "q2", "question": "Pourquoi est-il dangereux de demander 'on signe ?' ?", "options": ["A) C'est poli", "B) C'est intrusif, anxiogene — le client doit s'inclure, pas se sentir force", "C) Ca marche bien", "D) C'est standard"], "reponse_correcte": "B", "explication": "'On valide l'etude, et on passe la main a l'ingenierie.'", "source": "Closing MAESTRO — Q2"},
            {"id": "q3", "question": "Dans quelle situation un 'oui' du client n'est pas un engagement reel ?", "options": ["A) Jamais", "B) Quand c'est un accord verbal sans engagement emotionnel — il dit oui pour te liberer", "C) Toujours", "D) Si c'est ecrit"], "reponse_correcte": "B", "explication": "'Tres bien, qu'est-ce qui fait que ca vous semble coherent ?' Tu testes la sincerite du oui.", "source": "Closing MAESTRO — Q3"},
            {"id": "q4", "question": "Pourquoi un closing reussi commence 30 minutes avant la fin du rendez-vous ?", "options": ["A) Pour gagner du temps", "B) Si tu clos apres la tension, tu es en retard — la decision se prepare pendant la montee", "C) Par habitude", "D) Pour impressionner"], "reponse_correcte": "B", "explication": "'On voit bien que le projet a du sens sur le plan economique.' (pendant la presentation).", "source": "Closing MAESTRO — Q4"},
            {"id": "q5", "question": "Quelle difference entre 'accepter' et 's'engager' ?", "options": ["A) C'est pareil", "B) Accepter = passif, S'engager = actif — tu veux un client acteur", "C) Accepter est mieux", "D) S'engager est pire"], "reponse_correcte": "B", "explication": "'On demarre ensemble sur cette base, c'est bien ca ?'", "source": "Closing MAESTRO — Q5"},
            {"id": "q6", "question": "Un silence mal gere avant la conclusion peut aneantir quoi ?", "options": ["A) Rien", "B) La tension positive construite — le silence doit etre maitrise, pas trop long", "C) Le rapport", "D) Le prix"], "reponse_correcte": "B", "explication": "Le client doit sentir la gravite du moment, pas un malaise. 3 secondes, regard fixe, calme.", "source": "Closing MAESTRO — Q6"},
            {"id": "q7", "question": "Le client dit 'Je veux relire a tete reposee'. Quelle est la vraie lecture ?", "options": ["A) Il va vraiment relire", "B) C'est une fuite emotionnelle masquee en rationalite", "C) Il est serieux", "D) Il faut attendre"], "reponse_correcte": "B", "explication": "'Qu'est-ce que vous voulez verifier avant de valider ?'", "source": "Closing MAESTRO — Q7"},
            {"id": "q8", "question": "Qu'est-ce qui fait qu'un closing parait 'fluide' alors qu'il est hautement dirige ?", "options": ["A) Le talent naturel", "B) C'est une direction invisible — tu laisses croire a la liberte, mais tout est cadre", "C) L'experience", "D) Le produit"], "reponse_correcte": "B", "explication": "'Vous avez raison, on avance etape par etape, on valide deja la faisabilite.'", "source": "Closing MAESTRO — Q8"},
            {"id": "q9", "question": "Pourquoi 'Recapitulons' est a bannir du closing ?", "options": ["A) C'est trop long", "B) Ca sonne scolaire, ca rompt la tension finale et ramene le client dans sa tete", "C) Ca marche bien", "D) C'est professionnel"], "reponse_correcte": "B", "explication": "Remplacer par : 'Ce qu'on a mis en evidence, c'est que le projet est coherent sur les trois plans.'", "source": "Closing MAESTRO — Q9"},
            {"id": "q10", "question": "'On valide aujourd'hui' vs 'on valide quand vous voulez' — quel impact ?", "options": ["A) C'est pareil", "B) 'Aujourd'hui' cree une perception d'action immediate — le cerveau choisit le concret", "C) 'Quand vous voulez' est mieux", "D) Ca n'a pas d'impact"], "reponse_correcte": "B", "explication": "'On verrouille le dossier aujourd'hui pour ne pas perdre le creneau d'etude.'", "source": "Closing MAESTRO — Q10"},
            {"id": "q11", "question": "Quelle est la fonction du dernier 'oui' verbal avant la signature ?", "options": ["A) Rien", "B) C'est un ancrage cognitif — il fixe la coherence. Ce 'oui' doit etre conscient, pas poli.", "C) Un reflexe", "D) Une formalite"], "reponse_correcte": "B", "explication": "'Donc, si tout ce qu'on a vu vous parle, on avance, d'accord ?'", "source": "Closing MAESTRO — Q11"},
            {"id": "q12", "question": "Comment reconnaitre un 'faux calme' du client avant retractation ?", "options": ["A) C'est impossible", "B) Le client se deconnecte — derriere la maitrise, le doute", "C) Il est vraiment calme", "D) Il sourit"], "reponse_correcte": "B", "explication": "'Je vous sens pose, mais encore en reflexion. C'est sur quoi exactement ?'", "source": "Closing MAESTRO — Q12"},
            {"id": "q13", "question": "Pourquoi un vendeur d'elite ne 'cloture' jamais une vente ?", "options": ["A) Il est paresseux", "B) Il la laisse se fermer d'elle-meme — le closing se fait sans etre nomme", "C) C'est interdit", "D) Il oublie"], "reponse_correcte": "B", "explication": "'On confirme que l'etude est validee, parfait.'", "source": "Closing MAESTRO — Q13"},
            {"id": "q14", "question": "Quelle phrase inconsciente de vendeur moyen sabote les closes reussis ?", "options": ["A) 'On y va'", "B) 'C'est a vous de voir' — fausse liberte, vraie fuite de posture", "C) 'Merci'", "D) 'Tres bien'"], "reponse_correcte": "B", "explication": "Remplacer par : 'On valide si c'est coherent avec vos besoins, d'accord ?'", "source": "Closing MAESTRO — Q14"},
            {"id": "q15", "question": "Comment faire que le client se sente acteur et non sujet du closing ?", "options": ["A) Le laisser seul", "B) Faire co-construire la decision — le client signe ce qu'il a decide", "C) Le forcer", "D) Ignorer ses objections"], "reponse_correcte": "B", "explication": "'Qu'est-ce qui fait sens pour vous dans ce qu'on vient de voir ?'", "source": "Closing MAESTRO — Q15"},
            {"id": "q16", "question": "Pourquoi l'energie du vendeur doit chuter en fin d'entretien ?", "options": ["A) Il est fatigue", "B) Trop d'energie a la fin = pression. Baisser l'energie rassure et cree l'espace de decision.", "C) Ca n'a pas d'effet", "D) L'energie doit monter"], "reponse_correcte": "B", "explication": "Tu poses ton stylo, voix calme : 'Prenez le temps de verifier qu'on est bon.'", "source": "Closing MAESTRO — Q16"},
            {"id": "q17", "question": "Le client dit 'Je dois encore reflechir au financement'. Que fait un closer haut niveau ?", "options": ["A) Il explique le financement", "B) Il reformule en validation du projet — 'Donc le projet est valide, il reste juste a caler la formule ?'", "C) Il baisse le prix", "D) Il attend"], "reponse_correcte": "B", "explication": "Ne pas repondre a la peur, recadrer la logique.", "source": "Closing MAESTRO — Q17"},
            {"id": "q18", "question": "Pourquoi 'Ca vous va ?' doit etre banni du closing ?", "options": ["A) C'est poli", "B) C'est infantilisant — tu veux son accord, pas son autorisation", "C) Ca marche bien", "D) C'est professionnel"], "reponse_correcte": "B", "explication": "Remplacer par : 'On avance sur ce scenario ?'", "source": "Closing MAESTRO — Q18"},
            {"id": "q19", "question": "Le silence apres le prix doit durer combien de temps ?", "options": ["A) 0 secondes", "B) 2 a 4 secondes — le client doit integrer, pas fuir", "C) 10 secondes", "D) 30 secondes"], "reponse_correcte": "B", "explication": "Tu dis le montant. Tu fermes la bouche. Tu le regardes.", "source": "Closing MAESTRO — Q19"},
            {"id": "q20", "question": "Quelle emotion doit ressentir le client juste avant de signer pour que la decision tienne ?", "options": ["A) La peur de rater", "B) Fierte + soulagement — la decision doit venir d'une emotion positive et calme", "C) L'excitation", "D) L'indifference"], "reponse_correcte": "B", "explication": "'Vous allez voir, vous serez content de l'avoir fait.'", "source": "Closing MAESTRO — Q20"},
            {"id": "q21", "question": "Pourquoi 'Honnetement, si je vous suis, on y va' est destructeur ?", "options": ["A) C'est efficace", "B) C'est une fausse proximite — tu cherches son accord emotionnel, tu perds ton autorite", "C) C'est honnete", "D) Ca n'a pas d'impact"], "reponse_correcte": "B", "explication": "'Si on se base sur ce qu'on vient de valider, la suite logique c'est...?'", "source": "Closing MAESTRO — Q21"},
            {"id": "q22", "question": "Quelle est la seule raison pour laquelle un client annule un closing valide la veille ?", "options": ["A) Le prix est trop haut", "B) Mauvais suivi emotionnel post-decision — l'energie retombe, la peur revient", "C) Le concurrent est meilleur", "D) Le produit ne convient pas"], "reponse_correcte": "B", "explication": "TOUJOURS envoyer un message d'ancrage apres la decision. 'Merci pour l'echange, on avance ensemble.'", "source": "Closing MAESTRO — Q22"},
            {"id": "q23", "question": "Pourquoi un bon closer parle plus lentement a mesure qu'il approche la decision ?", "options": ["A) Il est fatigue", "B) Ralentir = securiser. Le rythme du closing doit baisser pour ancrer.", "C) Par hasard", "D) Ca n'a pas d'effet"], "reponse_correcte": "B", "explication": "'On y va tranquillement, etape par etape.'", "source": "Closing MAESTRO — Q23"},
            {"id": "q24", "question": "Quelle difference entre une decision de confort et une decision d'alignement ?", "options": ["A) C'est pareil", "B) Confort = emotionnelle (tient pas) ; Alignement = structurelle (tient dans le temps)", "C) Confort est mieux", "D) Alignement est pire"], "reponse_correcte": "B", "explication": "'Est-ce que c'est un choix qui vous ressemble vraiment ?'", "source": "Closing MAESTRO — Q24"},
            {"id": "q25", "question": "Comment un closer d'elite transforme une objection tardive en preuve de sincerite ?", "options": ["A) Il l'ignore", "B) Il remercie — 'Merci, c'est important de le dire maintenant'", "C) Il s'enerve", "D) Il baisse le prix"], "reponse_correcte": "B", "explication": "L'objection tardive = cadeau cache. Elle permet de renforcer la sincerite.", "source": "Closing MAESTRO — Q25"},
            {"id": "q26", "question": "Le client dit 'Je ne suis pas pret a m'engager'. Premiere question mentale ?", "options": ["A) 'Comment le convaincre ?'", "B) 'Ou ai-je perdu son alignement ?' — corriger le processus, pas defendre le produit", "C) 'Comment baisser le prix ?'", "D) 'Il faut rappeler demain'"], "reponse_correcte": "B", "explication": "'Qu'est-ce qui manque pour que ce soit juste pour vous ?'", "source": "Closing MAESTRO — Q26"},
            {"id": "q27", "question": "Pourquoi la signature ne doit jamais etre presentee comme une finalite ?", "options": ["A) C'est une formalite", "B) C'est une consequence logique — elle ne se demande pas, elle se constate", "C) C'est stressant", "D) C'est inutile"], "reponse_correcte": "B", "explication": "'Parfait, je vous fais suivre les elements pour officialiser.'", "source": "Closing MAESTRO — Q27"},
            {"id": "q28", "question": "'On y va ?', 'On le lance ?', 'On signe ?' — laquelle est la plus risquee ?", "options": ["A) 'On y va ?'", "B) 'On le lance ?'", "C) 'On signe ?' — c'est de la vente, pas du partenariat", "D) Toutes pareilles"], "reponse_correcte": "C", "explication": "'On signe ?' = vente ; 'On y va ?' = partenariat. Le choix des mots change la perception.", "source": "Closing MAESTRO — Q28"},
            {"id": "q29", "question": "Quelle difference entre un closing reussi et un closing maitrise ?", "options": ["A) C'est pareil", "B) Le reussi est circonstanciel, le maitrise est duplicable", "C) Le maitrise est pire", "D) Le reussi est mieux"], "reponse_correcte": "B", "explication": "Un closer maitrise cree un climat, pas un coup de chance. Tu sais exactement pourquoi il a dit oui.", "source": "Closing MAESTRO — Q29"},
            {"id": "q30", "question": "Pourquoi un vrai closer laisse le client croire qu'il a choisi ?", "options": ["A) Par manipulation", "B) L'illusion du choix — le cadre decisionnel est dirige sans qu'il s'en rende compte", "C) Par paresse", "D) Par hasard"], "reponse_correcte": "B", "explication": "'On part sur la version 8 kWc ou 9 ?' Le client croit qu'il choisit, mais tu controles la grammaire du choix.", "source": "Closing MAESTRO — Q30"},
        ],
    },

    # -----------------------------------------------------------------------
    # MODULE 4 — Objections ADERA (20 questions sur les 44 objections)
    # Source : Guide 44 objections + Script Courtage + Synthese
    # -----------------------------------------------------------------------
    "4": {
        "id": "4",
        "titre": "Objections ADERA — 44 objections",
        "description": "20 questions QCM sur la methode ADERA et les 44 objections les plus frequentes. Les 44 objections completes sont accessibles via GET /formation/objection/<numero>.",
        "nb_questions": 20,
        "source": "Guide 44 objections + Script Courtage + Synthese Techniques Vente",
        "questions": [
            {"id": "q1", "question": "Que signifie le A de ADERA ?", "options": ["A) Argumenter", "B) Accueillir", "C) Analyser", "D) Accepter"], "reponse_correcte": "B", "explication": "A = Accueillir l'objection. Ne jamais contredire frontalement. 'Je comprends votre point...'", "source": "ADERA — Etape 1"},
            {"id": "q2", "question": "Le client dit 'c'est trop cher'. Quelle est l'etape D (Decouvrir) ?", "options": ["A) Baisser le prix", "B) Demander 'trop cher par rapport a quoi ?'", "C) Montrer les aides", "D) Ignorer et continuer"], "reponse_correcte": "B", "explication": "D = Decouvrir la vraie objection derriere. 'Trop cher' peut signifier budget, priorite, comparaison...", "source": "ADERA — Etape 2"},
            {"id": "q3", "question": "Le E de ADERA signifie :", "options": ["A) Expliquer", "B) Empathiser — valider le ressenti sans valider l'objection", "C) Evaluer", "D) Envoyer"], "reponse_correcte": "B", "explication": "'C'est normal de vouloir comparer'. Pas valider l'objection.", "source": "ADERA — Etape 3"},
            {"id": "q4", "question": "A l'etape R (Repondre), quel argument est le plus efficace ?", "options": ["A) Un argument generique", "B) Un temoignage client similaire", "C) Une remise commerciale", "D) Un argument technique detaille"], "reponse_correcte": "B", "explication": "R = Repondre avec preuve sociale. Un client similaire qui avait la meme objection et qui est satisfait.", "source": "ADERA — Etape 4"},
            {"id": "q5", "question": "Le A final de ADERA signifie :", "options": ["A) Repeter l'argument", "B) Ancrer — verifier que l'objection est levee puis re-closer", "C) Abandonner", "D) Appeler le manager"], "reponse_correcte": "B", "explication": "'Est-ce que ca repond a votre question ?' Si oui, re-closer immediatement.", "source": "ADERA — Etape 5"},
            {"id": "q6", "question": "Le client dit 'J'ai pas le temps'. Meilleure reponse ?", "options": ["A) 'OK, au revoir'", "B) 'Justement, c'est rapide : etude gratuite, 15 min. Cette semaine ou la suivante ?'", "C) 'Je rappelle demain'", "D) 'Prenez le temps'"], "reponse_correcte": "B", "explication": "Minimiser l'effort. Proposer une alternative planifiee.", "source": "Objections — #1"},
            {"id": "q7", "question": "Le client dit 'J'ai deja un fournisseur'. Meilleure reponse ?", "options": ["A) 'On est meilleurs'", "B) 'On ne touche pas a votre fournisseur. On reduit la quantite achetee. C'est complementaire.'", "C) 'Changez de fournisseur'", "D) 'OK'"], "reponse_correcte": "B", "explication": "Repositionner le projet : autonomie vs fournisseur.", "source": "Objections — #2"},
            {"id": "q8", "question": "Le client dit 'C'est une arnaque'. Meilleure reponse ?", "options": ["A) 'Pas du tout !'", "B) 'C'est une OBLIGATION LEGALE. Les energeticiens preferent financer plutot que payer la penalite liberatoire (~15 EUR/MWh cumac, art. L. 222-2). Verifiez sur ecologie.gouv.fr.'", "C) 'On est serieux'", "D) 'Tant pis'"], "reponse_correcte": "B", "explication": "Preuve legale + site officiel. Unite : EUR par MWh cumac (kWh cumule actualise), pas EUR par kWh.", "source": "Objections CEE — #14"},
            {"id": "q9", "question": "L'objection prix est presque JAMAIS une objection de :", "options": ["A) Valeur", "B) Temps", "C) Argent — c'est un doute de valeur, pas de moyens", "D) Qualite"], "reponse_correcte": "C", "explication": "Traiter la perception de valeur, pas le portefeuille.", "source": "Synthese Techniques Vente"},
            {"id": "q10", "question": "Le client dit 'Je veux plusieurs devis'. Meilleure reponse ?", "options": ["A) 'On est les moins chers'", "B) 'C'est normal. Comparez, mais comparez ce qui est equivalent.'", "C) 'Inutile de comparer'", "D) 'Voici notre prix final'"], "reponse_correcte": "B", "explication": "Validation interne — le client cherche a confirmer, pas a comparer.", "source": "Objections — #12"},
            {"id": "q11", "question": "Le client dit 'C'est pas le bon moment'. Meilleure reponse ?", "options": ["A) 'OK, rappelez-moi'", "B) 'C'est quand les prix sont hauts que les economies sont les plus fortes. Etude gratuite = liberte future.'", "C) 'Il faut y aller maintenant'", "D) 'Tant pis'"], "reponse_correcte": "B", "explication": "Urgence implicite sans pression.", "source": "Objections — #6"},
            {"id": "q12", "question": "Le client dit 'Je dois en parler a mon associe'. Meilleure question a poser ?", "options": ["A) 'Son numero ?'", "B) 'Qu'est-ce que vous allez lui dire en priorite ?'", "C) 'Dites-lui de m'appeler'", "D) 'OK, rappelez-moi'"], "reponse_correcte": "B", "explication": "Faire du client un relais actif.", "source": "Objections — #11"},
            {"id": "q13", "question": "Le client dit 'J'y connais rien'. Meilleure reponse ?", "options": ["A) 'C'est complique en effet'", "B) 'C'est notre role. On vous montre les chiffres, vous decidez.'", "C) 'Renseignez-vous d'abord'", "D) 'Laissez tomber alors'"], "reponse_correcte": "B", "explication": "Deleguer la competence. Renforcer la confiance.", "source": "Objections — #7"},
            {"id": "q14", "question": "Le client dit 'Envoyez-moi un devis par mail'. Que faire ?", "options": ["A) Envoyer le devis", "B) 'Le devis necessite une etude sur place. Un devis par mail sans contexte = comparaison pure.'", "C) Refuser", "D) Envoyer une fourchette"], "reponse_correcte": "B", "explication": "Jamais de devis par mail sans R2. Le devis mail = prix sans contexte = on perd.", "source": "Objections — #18"},
            {"id": "q15", "question": "Le client dit 'Je ne suis pas pret a m'engager'. Meilleure question ?", "options": ["A) 'Pourquoi ?'", "B) 'Qu'est-ce qui manque pour que ce soit juste pour vous ?'", "C) 'Quand serez-vous pret ?'", "D) 'Tant pis'"], "reponse_correcte": "B", "explication": "Corriger le processus, pas defendre le produit.", "source": "Objections — #13"},
            {"id": "q16", "question": "Le client dit 'Mon batiment est trop vieux'. Meilleure reponse ?", "options": ["A) 'C'est dommage'", "B) 'Justement, les batiments anciens sont les plus eligibles CEE car le potentiel d'economies est maximal.'", "C) 'Il faut renover d'abord'", "D) 'C'est vrai'"], "reponse_correcte": "B", "explication": "Les vieux batiments = plus d'economies = plus de CEE.", "source": "Objections — #33"},
            {"id": "q17", "question": "Le client dit 'Mon electricien peut le faire'. Meilleure reponse ?", "options": ["A) 'Non il peut pas'", "B) 'Est-il certifie RGE pour cette operation ? Sans RGE, pas de prime CEE, pas de S21.'", "C) 'OK, bonne chance'", "D) 'On est mieux'"], "reponse_correcte": "B", "explication": "Condition RGE = obligatoire pour les primes.", "source": "Objections — #38"},
            {"id": "q18", "question": "Le client dit 'J'ai deja ete demarche'. Meilleure reponse ?", "options": ["A) 'Oui, comme tout le monde'", "B) 'La difference : vous etes client actif, pre-etude deja faite, etude offerte. Rien a vendre, juste valider.'", "C) 'On est differents'", "D) 'Desolement'"], "reponse_correcte": "B", "explication": "Revaloriser la relation. Demarche personnalisee.", "source": "Objections — #8"},
            {"id": "q19", "question": "Le client dit 'Ca m'interesse pas'. Derniere tentative ?", "options": ["A) 'OK, au revoir'", "B) 'Une pre-etude montre un potentiel concret. 15 min pour voir. C'est vous qui decidez apres.'", "C) 'Vous avez tort'", "D) 'Je rappelle dans 6 mois'"], "reponse_correcte": "B", "explication": "Derniere tentative : valeur + posture de service + non-insistance.", "source": "Objections — #10"},
            {"id": "q20", "question": "Le client dit 'Votre entreprise, je la connais pas'. Meilleure reponse ?", "options": ["A) 'On est celebres'", "B) 'Normal, on travaille en B2B. +140 projets depuis 2009, certifies RGE, accredites DGEC. On peut envoyer des references.'", "C) 'Cherchez sur Google'", "D) 'Tant pis'"], "reponse_correcte": "B", "explication": "References + certifications + anciennete.", "source": "Objections — #44"},
        ],
    },

    # -----------------------------------------------------------------------
    # MODULE 5 — Conformite PNCEE 12 erreurs (12 questions)
    # Source : Methodologie Jimmy — G1T
    # -----------------------------------------------------------------------
    "5": {
        "id": "5",
        "titre": "Conformite PNCEE — 12 erreurs fatales",
        "description": "12 questions sur les 12 erreurs fatales de conformite dossier CEE (G1T).",
        "nb_questions": 12,
        "source": "Methodologie Jimmy — G1T / Conformite PNCEE",
        "questions": [
            {"id": "q1", "question": "Quelle couleur d'encre est obligatoire pour la signature du beneficiaire ?", "options": ["A) Noire", "B) Bleue", "C) Noire ou bleue", "D) Peu importe"], "reponse_correcte": "B", "explication": "Encre BLEUE obligatoire. Ca prouve que c'est un original et non une photocopie.", "source": "G1T — Erreur #1"},
            {"id": "q2", "question": "Peut-on imprimer l'attestation sur l'honneur en recto-verso ?", "options": ["A) Oui", "B) Non, jamais", "C) Oui si agrafe", "D) Oui si client d'accord"], "reponse_correcte": "B", "explication": "JAMAIS de recto-verso sur l'AH. Chaque page = recto seul pour eviter tout soupcon.", "source": "G1T — Erreur #2"},
            {"id": "q3", "question": "Ou doit etre appose le tampon de l'entreprise beneficiaire ?", "options": ["A) Sur la signature", "B) A cote de la signature, sans la toucher", "C) En haut de page", "D) Au dos"], "reponse_correcte": "B", "explication": "Le tampon doit etre A COTE de la signature, pas dessus. Sinon signature illisible = rejet.", "source": "G1T — Erreur #3"},
            {"id": "q4", "question": "Quel est l'ordre chronologique obligatoire engagement / devis / travaux / AH ?", "options": ["A) Pas de regle", "B) Devis d'abord", "C) Travaux d'abord", "D) L'engagement CEE (mandat/convention signe avec l'oblige) doit etre date AVANT le devis ; l'AH est signee apres travaux pour certifier l'achevement"], "reponse_correcte": "D", "explication": "Engagement (mandat de l'oblige) AVANT devis = role actif et incitatif (art. 4-1 arrete 4/9/2014). L'AH est signee SEPAREMENT, par le beneficiaire et l'installateur, APRES travaux pour certifier l'achevement.", "source": "G1T — Erreur #4 + arrete 4/9/2014"},
            {"id": "q5", "question": "Le SIRET sur l'AH est different de celui sur le devis. Consequence ?", "options": ["A) Pas grave", "B) Rejet systematique", "C) Demande de correction", "D) Accepte avec reserve"], "reponse_correcte": "B", "explication": "SIRET incoherent = rejet systematique. Verifier la concordance AH / devis / facture / RGE avant envoi.", "source": "G1T — Erreur #5"},
            {"id": "q6", "question": "La mention 'lu et approuve' est-elle obligatoire sur l'AH ?", "options": ["A) Non", "B) Oui, manuscrite obligatoire", "C) Seulement > 10 000 EUR", "D) Seulement en B2C"], "reponse_correcte": "B", "explication": "Mention 'lu et approuve' manuscrite obligatoire. Son absence = motif de rejet PNCEE.", "source": "G1T — Erreur #6"},
            {"id": "q7", "question": "Le certificat RGE expire 3 jours apres la fin des travaux. Valide ?", "options": ["A) Oui", "B) Non, il doit etre valide a la date de depot du dossier chez l'oblige", "C) Oui si travaux finis", "D) Non, doit couvrir duree cumac"], "reponse_correcte": "B", "explication": "Le RGE doit etre valide au moment du depot, pas seulement pendant les travaux.", "source": "G1T — Erreur #7"},
            {"id": "q8", "question": "La facture de l'isolant doit mentionner quoi ?", "options": ["A) Juste le prix", "B) R thermique, epaisseur, marque, certification ACERMI", "C) Juste la fiche technique", "D) Seulement pour BAT-EN-103"], "reponse_correcte": "B", "explication": "Facture avec R, epaisseur, marque ET numero ACERMI. Info manquante = demande complementaire = delai.", "source": "G1T — Erreur #8"},
            {"id": "q9", "question": "Le cadre 'Contribution' sur l'AH est vide. Consequence ?", "options": ["A) Pas grave", "B) Rejet", "C) Demande complementaire", "D) Accepte si montant sur devis"], "reponse_correcte": "B", "explication": "Le cadre Contribution (role actif et incitatif de l'oblige) doit etre rempli. Vide = non-conformite = rejet.", "source": "G1T — Erreur #9"},
            {"id": "q10", "question": "Peut-on envoyer le dossier CEE par email a l'oblige ?", "options": ["A) Oui, scan PDF suffit", "B) Non, originaux papier uniquement", "C) Depend de l'oblige", "D) Oui si signature electronique"], "reponse_correcte": "C", "explication": "Ca depend de l'oblige. Certains acceptent le numerique, d'autres exigent les originaux. Verifier AVANT.", "source": "G1T — Erreur #10"},
            {"id": "q11", "question": "La date de fin de travaux sur la facture est posterieure a celle sur l'AH. Probleme ?", "options": ["A) Non", "B) Oui, incoherence de dates = rejet", "C) Pas si ecart < 30j", "D) Seulement gros chantiers"], "reponse_correcte": "B", "explication": "Toute incoherence de dates entre AH et facture = motif de rejet.", "source": "G1T — Erreur #11"},
            {"id": "q12", "question": "Le paraphe est-il obligatoire sur chaque page de l'AH ?", "options": ["A) Non, seule la derniere page", "B) Oui, chaque page doit etre paraphee", "C) Seulement pages avec texte", "D) Facultatif"], "reponse_correcte": "B", "explication": "Paraphe obligatoire sur CHAQUE page. Page non paraphee = page contestable = risque de rejet.", "source": "G1T — Erreur #12"},
        ],
    },

    # -----------------------------------------------------------------------
    # MODULE 6 — Porte-a-porte B2B PV (10 questions)
    # Source : formation porte a porte pb 08:2025.docx
    # -----------------------------------------------------------------------
    "6": {
        "id": "6",
        "titre": "Porte-a-porte B2B PV",
        "description": "10 questions sur le script terrain B2B photovoltaique, la posture technicien, le barrage secretaire.",
        "nb_questions": 10,
        "source": "formation porte a porte pb 08:2025.docx",
        "questions": [
            {"id": "q1", "question": "Quel est l'objectif du porte-a-porte B2B PV ?", "options": ["A) Vendre l'installation", "B) Expliquer la technique", "C) Obtenir un RDV de 20 min avec l'ingenieur", "D) Laisser un flyer"], "reponse_correcte": "C", "explication": "Ne PAS vendre, ne PAS expliquer. OBTENIR un rendez-vous de 20 min avec l'ingenieur.", "source": "Script PAP B2B"},
            {"id": "q2", "question": "Quelle posture adopter en porte-a-porte ?", "options": ["A) Vendeur enthousiaste", "B) Technicien mandate, credible, tenue technicien", "C) Manager en costume", "D) Stagiaire sympa"], "reponse_correcte": "B", "explication": "Pas vendeur = technicien mandate. Credible, tenue technicien.", "source": "Script PAP B2B"},
            {"id": "q3", "question": "Combien de temps maximum devant la porte ?", "options": ["A) 5 minutes", "B) 10 minutes", "C) 2 minutes maximum", "D) 30 secondes"], "reponse_correcte": "C", "explication": "Parle vite et simple. Ne jamais depasser 2 minutes devant la porte.", "source": "Script PAP B2B"},
            {"id": "q4", "question": "Quelle est la bonne accroche en porte-a-porte ?", "options": ["A) 'Je vends des panneaux solaires'", "B) 'Votre batiment a ete etudie pour son potentiel solaire dans le cadre du groupement local'", "C) 'Vous voulez des economies ?'", "D) 'On a une promo'"], "reponse_correcte": "B", "explication": "Selection + pre-etude + groupement local = credibilite immediate.", "source": "Script PAP B2B"},
            {"id": "q5", "question": "Quel argument justifie la gratuite de l'etude ?", "options": ["A) On est genereux", "B) Mutualisation de plusieurs entreprises du secteur = reduction des couts", "C) C'est une promo", "D) Le gouvernement paye"], "reponse_correcte": "B", "explication": "Groupement local = mutualisation = conditions exceptionnelles.", "source": "Script PAP B2B"},
            {"id": "q6", "question": "Barrage secretaire : quelle phrase utiliser ?", "options": ["A) 'Je veux parler au patron'", "B) 'Votre entreprise a ete selectionnee pour l'etude groupement. C'est deja finance, totalement gratuit.'", "C) 'C'est urgent'", "D) 'Je rappelle plus tard'"], "reponse_correcte": "B", "explication": "Selection + finance = deja gratuit. Juste caler un RDV de 20 min avec l'ingenieur.", "source": "Script PAP B2B"},
            {"id": "q7", "question": "Quel argument de rarete utiliser ?", "options": ["A) 'C'est maintenant ou jamais'", "B) 'Les places sont limitees sur la commune, deja une dizaine d'entreprises inscrites'", "C) 'Dernier jour'", "D) 'Prix qui monte'"], "reponse_correcte": "B", "explication": "Rarete & urgence basees sur la realite du groupement.", "source": "Script PAP B2B"},
            {"id": "q8", "question": "Quel argument de preuve sociale utiliser ?", "options": ["A) 'Tout le monde le fait'", "B) 'Beaucoup de vos confreres ont deja accepte, ne serait-ce que pour savoir combien couvrir de leur facture'", "C) 'On est les meilleurs'", "D) 'Article de journal'"], "reponse_correcte": "B", "explication": "Preuve sociale concrete avec confreres du meme secteur.", "source": "Script PAP B2B"},
            {"id": "q9", "question": "Que promettre au prospect ?", "options": ["A) Des economies garanties", "B) Savoir combien il peut produire, couvrir 60-70% de facture, systeme qui se paye tout seul", "C) Un prix imbattable", "D) Des panneaux gratuits"], "reponse_correcte": "B", "explication": "Benefices concrets, sans jargon. Production, couverture facture, autofinancement.", "source": "Script PAP B2B"},
            {"id": "q10", "question": "Regle absolue avant de partir ?", "options": ["A) Laisser un flyer", "B) Ne JAMAIS partir sans rendez-vous ou contact mail", "C) Donner sa carte", "D) Prendre une photo"], "reponse_correcte": "B", "explication": "Cloture systematique. Toujours rediriger vers l'ingenieur si besoin.", "source": "Script PAP B2B"},
        ],
    },

    # -----------------------------------------------------------------------
    # MODULE 7 — Script Courtage → PV (15 questions)
    # Source : SCRIPT ARGUMENTAIRE FICHIER CLIENT COURTAGE.docx
    # -----------------------------------------------------------------------
    "7": {
        "id": "7",
        "titre": "Script Courtage vers PV",
        "description": "15 questions sur le script d'appel clients courtage existants vers photovoltaique.",
        "nb_questions": 15,
        "source": "SCRIPT ARGUMENTAIRE FICHIER CLIENT COURTAGE.docx",
        "questions": [
            {"id": "q1", "question": "Quelle est la phrase d'accroche du script courtage ?", "options": ["A) 'Bonjour, je vends du solaire'", "B) 'Bonjour [Prenom], ici David, du bureau d'etudes PV. On s'est deja occupe de votre contrat d'energie, vous vous rappelez ?'", "C) 'Bonjour, vous avez 5 minutes ?'", "D) 'Bonjour, j'ai une offre pour vous'"], "reponse_correcte": "B", "explication": "Reactivation du lien courtage existant. Connexion emotionnelle.", "source": "Script Courtage"},
            {"id": "q2", "question": "Quelle metaphore puissante utiliser dans le script courtage ?", "options": ["A) 'Le solaire c'est l'avenir'", "B) 'Le courtage a securise le prix. Le PV permet de consommer 2 a 3 fois moins. Vous gagnez sur le prix ET le volume.'", "C) 'C'est gratuit'", "D) 'C'est bon pour la planete'"], "reponse_correcte": "B", "explication": "Double gain : prix (courtage) + volume (PV).", "source": "Script Courtage"},
            {"id": "q3", "question": "Quel ancrage psychologique utiliser ?", "options": ["A) 'C'est pas cher'", "B) 'Vous devenez proprietaire de votre energie, comme proprietaire de votre maison plutot que locataire a fond perdu'", "C) 'C'est ecologique'", "D) 'C'est tendance'"], "reponse_correcte": "B", "explication": "Chaque kWh paye = loyer verse a EDF qui ne vous appartient jamais.", "source": "Script Courtage"},
            {"id": "q4", "question": "Quelles sont les 3 questions techniques de filtrage ?", "options": ["A) Budget, delai, motivation", "B) Proprietaire ou locataire ? Amiante sur toiture ? Ombres importantes ?", "C) Nombre d'employes, CA, secteur", "D) Age du batiment, surface, etage"], "reponse_correcte": "B", "explication": "3 questions filtrage rapide : propriete, fragilites toiture, ombres.", "source": "Script Courtage"},
            {"id": "q5", "question": "Que demander au client apres la qualification ?", "options": ["A) Son budget", "B) Une facture d'electricite recente (< 6 mois) + formulaire ACD", "C) Son RIB", "D) Son SIRET"], "reponse_correcte": "B", "explication": "Facture recente + ACD = les 2 documents pour lancer l'etude.", "source": "Script Courtage"},
            {"id": "q6", "question": "Comment conclure le script courtage ?", "options": ["A) 'Je vous rappelle'", "B) 'Si c'est viable, rentable des la 1ere annee et autofinance, on avance. Sinon, etude gratuite.'", "C) 'Signez maintenant'", "D) 'Reflechissez'"], "reponse_correcte": "B", "explication": "No risk, just info. Le client ne perd rien a voir l'etude.", "source": "Script Courtage"},
            {"id": "q7", "question": "Quel pourcentage de reduction de facture annoncer ?", "options": ["A) 80-90%", "B) 30-60% en moyenne", "C) 10-15%", "D) 100%"], "reponse_correcte": "B", "explication": "En moyenne, 30% a 60% de la facture globale.", "source": "Script Courtage"},
            {"id": "q8", "question": "Dans combien de pourcent des cas le projet s'autofinance ?", "options": ["A) 50%", "B) Plus de 80%", "C) 30%", "D) 100%"], "reponse_correcte": "B", "explication": "Dans plus de 80% des cas, autofinance via les economies.", "source": "Script Courtage"},
            {"id": "q9", "question": "Quelle garantie mentionner pour rassurer ?", "options": ["A) 5 ans", "B) 15 a 20 ans, avec production assuree + batterie 2 jours en cas de coupure", "C) 1 an", "D) Aucune"], "reponse_correcte": "B", "explication": "Garantie longue + production assuree + autonomie en coupure.", "source": "Script Courtage"},
            {"id": "q10", "question": "Combien coute normalement l'etude ?", "options": ["A) 500 EUR", "B) 1700 EUR — mais prise en charge 100% pour les clients existants", "C) Gratuite pour tous", "D) 3000 EUR"], "reponse_correcte": "B", "explication": "Etude normalement facturee 1700 EUR, offerte aux clients courtage.", "source": "Script Courtage"},
            {"id": "q11", "question": "Quelles techniques de vente sont integrees dans le script courtage ?", "options": ["A) Hard sell uniquement", "B) Connexion, Ancrage comparatif, SONCAS, Preuve sociale, Closing progressif 3 etapes, ADERA", "C) Discount", "D) Cold call standard"], "reponse_correcte": "B", "explication": "6 techniques integrees dans un seul script.", "source": "Script Courtage"},
            {"id": "q12", "question": "Le client dit 'Je veux voir ce que vous m'envoyez d'abord'. Que faire ?", "options": ["A) OK, au revoir", "B) Envoyer le mail + fixer le creneau maintenant pour eviter la fuite par 'plus tard'", "C) Insister", "D) Rappeler dans 1 semaine"], "reponse_correcte": "B", "explication": "Double engagement : document + creneau. Eviter la fuite.", "source": "Script Courtage"},
            {"id": "q13", "question": "Comment le script courtage propose le RDV ?", "options": ["A) 'Quand vous voulez'", "B) 'Matin ou apres-midi ? Debut, milieu ou fin de semaine ?'", "C) 'Je rappelle demain'", "D) 'Envoyez-moi un mail'"], "reponse_correcte": "B", "explication": "2 creneaux precis = x3 taux de reponse vs 'quand vous voulez'.", "source": "Script Courtage"},
            {"id": "q14", "question": "Quel est le positionnement du commercial dans le script courtage ?", "options": ["A) Vendeur", "B) Bureau d'etudes interne dedie au solaire", "C) Demarcheur", "D) Technicien terrain"], "reponse_correcte": "B", "explication": "Bureau d'etudes interne + profils strategiques priorises.", "source": "Script Courtage"},
            {"id": "q15", "question": "La methode SONCAS signifie :", "options": ["A) Situation, Objection, Negociation, Closing, Action, Suivi", "B) Securite, Orgueil, Nouveaute, Confort, Argent, Sympathie", "C) Signal, Opportunite, Need, Cost, Action, Sale", "D) Style, Offre, Necessaire, Concret, Argument, Solution"], "reponse_correcte": "B", "explication": "6 motivations d'achat : Securite, Orgueil, Nouveaute, Confort, Argent, Sympathie.", "source": "Script Courtage"},
        ],
    },

    # -----------------------------------------------------------------------
    # MODULE 8 — Montage Dossier CEE / PV (30 questions)
    # Source : FORMATION MONTAGE DOSSIER QCM.docx
    # -----------------------------------------------------------------------
    "8": {
        "id": "8",
        "titre": "Montage Dossier PV — Technique",
        "description": "30 questions sur PVGIS, Archelios, Optiwize, normes bancaires, PR, DSCR, TRI, VAN.",
        "nb_questions": 30,
        "source": "FORMATION MONTAGE DOSSIER QCM.docx",
        "questions": [
            {"id": "q1", "question": "Quelle est la signification de 'kWc' ?", "options": ["A) Kilowatt courant", "B) Kilowatt calcule", "C) Kilowatt crete"], "reponse_correcte": "C", "explication": "Puissance nominale d'un module en conditions standard (STC).", "source": "Montage Dossier — Q1"},
            {"id": "q2", "question": "Pente optimale en France pour panneaux fixes ?", "options": ["A) 0 deg", "B) 15 deg", "C) 30-35 deg"], "reponse_correcte": "C", "explication": "Maximise l'exposition annuelle au soleil selon latitude ~45 degN.", "source": "Montage Dossier — Q2"},
            {"id": "q3", "question": "A quoi sert un optimiseur SolarEdge ?", "options": ["A) Convertir le courant alternatif", "B) Maximiser la production au niveau de chaque module", "C) Refroidir les panneaux"], "reponse_correcte": "B", "explication": "Optimise le MPPT module par module.", "source": "Montage Dossier — Q3"},
            {"id": "q4", "question": "Taux de degradation modulaire standard bancaire ?", "options": ["A) 1%/an", "B) 0.3%/an", "C) 0.5%/an"], "reponse_correcte": "C", "explication": "Standard du secteur, recommande par Exponent.", "source": "Montage Dossier — Q4"},
            {"id": "q5", "question": "Seuil DSCR minimum pour financement bancaire ?", "options": ["A) 1", "B) 1.1", "C) 1.3"], "reponse_correcte": "C", "explication": "DSCR >= 1.3 = norme de bancabilite pour garantir la solvabilite.", "source": "Montage Dossier — Q5"},
            {"id": "q6", "question": "Rendement STC typique des modules haut de gamme ?", "options": ["A) 14%", "B) 21%", "C) 27%"], "reponse_correcte": "B", "explication": "Modules premium (LONGi, Trina) a ~21% STC.", "source": "Montage Dossier — Q6"},
            {"id": "q7", "question": "Taux IS en France 2025 pour societes ?", "options": ["A) 15%", "B) 20%", "C) 25%"], "reponse_correcte": "C", "explication": "Taux d'imposition des societes : 25%.", "source": "Montage Dossier — Q7"},
            {"id": "q8", "question": "Duree d'un PPA classique ?", "options": ["A) 1 an", "B) 10 a 20 ans", "C) 6 mois"], "reponse_correcte": "B", "explication": "Power Purchase Agreement sur 10 a 20 ans.", "source": "Montage Dossier — Q8"},
            {"id": "q9", "question": "Qu'est-ce que le PR dans une etude PV ?", "options": ["A) Prix de revente", "B) Profil de rentabilite", "C) Performance Ratio"], "reponse_correcte": "C", "explication": "Ratio entre la production reelle AC et l'energie theorique attendue.", "source": "Montage Dossier — Q9"},
            {"id": "q10", "question": "Quel format pour importer une courbe de conso dans Optiwize ?", "options": ["A) PDF", "B) DOC", "C) CSV"], "reponse_correcte": "C", "explication": "Optiwize utilise des fichiers .CSV pour charger les profils horaires.", "source": "Montage Dossier — Q10"},
            {"id": "q11", "question": "Tolerance d'ecart P90 Archelios vs PVGIS ?", "options": ["A) +/- 2%", "B) +/- 5%", "C) +/- 10%"], "reponse_correcte": "B", "explication": "Tolerance de +/- 5% pour validation bancaire.", "source": "Montage Dossier — Q11"},
            {"id": "q12", "question": "Que signifie LCOE ?", "options": ["A) Limite de Consommation Electrique", "B) Localisation des Consommations", "C) Levelized Cost of Energy"], "reponse_correcte": "C", "explication": "Cout moyen du kWh produit, actualise sur la duree de vie.", "source": "Montage Dossier — Q12"},
            {"id": "q13", "question": "Taux d'inflation par defaut sur revenus de vente dans Optiwize ?", "options": ["A) 0%", "B) 2%", "C) 3.5%"], "reponse_correcte": "C", "explication": "Par defaut, Optiwize applique 3.5% d'inflation aux revenus.", "source": "Montage Dossier — Q13"},
            {"id": "q14", "question": "Impact d'un encrassement modere sur perte annuelle ?", "options": ["A) 1%", "B) 2%", "C) 5%"], "reponse_correcte": "B", "explication": "Standard : -2% pour poussiere et salissures.", "source": "Montage Dossier — Q14"},
            {"id": "q15", "question": "Quelle base de donnees est recommandee pour PVGIS en Europe ?", "options": ["A) NSRDB", "B) SARAH2", "C) ERA5"], "reponse_correcte": "B", "explication": "SARAH2, derivee d'images satellite CM SAF.", "source": "Montage Dossier — Q15"},
            {"id": "q16", "question": "Le P90 dans PVGIS est base sur quel ecart statistique ?", "options": ["A) 10e percentile", "B) Moyenne", "C) 90e percentile"], "reponse_correcte": "A", "explication": "Le P90 = 90% des annees depassent cette production (norme bancaire).", "source": "Montage Dossier — Q16"},
            {"id": "q17", "question": "Un PR < 75% signifie ?", "options": ["A) Tres bon projet", "B) Projet non bancable", "C) Projet fortement optimise"], "reponse_correcte": "B", "explication": "PR < 75% = pertes excessives ou erreurs de saisie.", "source": "Montage Dossier — Q17"},
            {"id": "q18", "question": "Le LID est-il toujours pris en compte dans Archelios ?", "options": ["A) Oui toujours", "B) Non, depend du module", "C) Jamais"], "reponse_correcte": "B", "explication": "LID = 0% par defaut sauf modules concernes (mono PERC par ex).", "source": "Montage Dossier — Q18"},
            {"id": "q19", "question": "Le TMY est un fichier de quelle nature ?", "options": ["A) Aleatoire", "B) Synthese mensuelle", "C) Annee meteorologique typique"], "reponse_correcte": "C", "explication": "TMY = Typical Meteorological Year. Pour simulations constantes.", "source": "Montage Dossier — Q19"},
            {"id": "q20", "question": "Un PR > 95% est-il bon signe ?", "options": ["A) Oui forcement", "B) Non, suspect / irrealiste", "C) Depend de l'onduleur"], "reponse_correcte": "B", "explication": "Un PR > 90% indique souvent une erreur de modelisation ou un oubli de pertes.", "source": "Montage Dossier — Q20"},
            {"id": "q21", "question": "L'ecart production AC/DC dans Archelios s'explique par ?", "options": ["A) Difference de voltage", "B) Pertes systeme", "C) Mauvais cablage"], "reponse_correcte": "B", "explication": "Conversion DC > AC = pertes onduleur, cables, temperature, etc.", "source": "Montage Dossier — Q21"},
            {"id": "q22", "question": "Simulation hors-reseau dans PVGIS ?", "options": ["A) PV performance", "B) Radiation Profile", "C) Off-grid simulation"], "reponse_correcte": "C", "explication": "Fonctionnalite hors-reseau avec simulation heure par heure.", "source": "Montage Dossier — Q22"},
            {"id": "q23", "question": "Le DSCR se calcule sur quelle base pour etre valide ?", "options": ["A) Moyenne P50", "B) Flux P90", "C) Taux fixe"], "reponse_correcte": "B", "explication": "Norme bancaire : DSCR calcule sur P90.", "source": "Montage Dossier — Q23"},
            {"id": "q24", "question": "Role du coefficient de temperature dans un panneau PV ?", "options": ["A) Resistance au vent", "B) Predit les pertes par chaleur", "C) Impacte le PR uniquement"], "reponse_correcte": "B", "explication": "Exprime en %/degC, degrade la puissance en fonction de la chaleur.", "source": "Montage Dossier — Q24"},
            {"id": "q25", "question": "Une perte de 4% liee a IAM signifie ?", "options": ["A) Mauvais raccordement", "B) Reflexion de lumiere", "C) Courant inverse"], "reponse_correcte": "B", "explication": "IAM = Incidence Angle Modifier = pertes par reflexion a angle eleve.", "source": "Montage Dossier — Q25"},
            {"id": "q26", "question": "Indicateur le plus pertinent pour la rentabilite brute ?", "options": ["A) DSCR", "B) PR", "C) TRI projet"], "reponse_correcte": "C", "explication": "TRI brut = indicateur de rentabilite d'un projet sans financement.", "source": "Montage Dossier — Q26"},
            {"id": "q27", "question": "Si la VAN est negative, cela signifie ?", "options": ["A) Excellent projet", "B) Projet a risque", "C) Projet non rentable"], "reponse_correcte": "C", "explication": "VAN < 0 = le projet detruit de la valeur actualisee.", "source": "Montage Dossier — Q27"},
            {"id": "q28", "question": "Quel est le seuil de productibilite minimal pour une installation bien orientee ?", "options": ["A) 500 kWh/kWc/an", "B) 800 kWh/kWc/an", "C) 1000 kWh/kWc/an"], "reponse_correcte": "C", "explication": "Seuil minimum 1000 kWh/kWc/an.", "source": "Montage Dossier — Q28"},
            {"id": "q29", "question": "Quelle est la duree typique d'une garantie de bon fonctionnement PV ?", "options": ["A) 12 mois", "B) 24 mois", "C) 36 mois"], "reponse_correcte": "B", "explication": "24 mois est la duree typique.", "source": "Montage Dossier — Q29"},
            {"id": "q30", "question": "Quel referentiel de raccordement Enedis ?", "options": ["A) Enedis-PRO-RAC_03E", "B) TURPE", "C) NF C15-100"], "reponse_correcte": "A", "explication": "Enedis-PRO-RAC_03E est le referentiel de raccordement.", "source": "Montage Dossier — Q30"},
        ],
    },

    # -----------------------------------------------------------------------
    # MODULE 9 — Expert S21 PV technique (30 questions)
    # Source : EXPERT S21 FORMATION QCM.docx
    # -----------------------------------------------------------------------
    "9": {
        "id": "9",
        "titre": "Expert S21 — Contrat Obligation d'Achat",
        "description": "30 questions sur le contrat S21, le Code de l'energie, les seuils, les tarifs, les logiciels PV.",
        "nb_questions": 30,
        "source": "EXPERT S21 FORMATION QCM.docx",
        "questions": [
            {"id": "q1", "question": "Duree d'un contrat d'achat S21 ?", "options": ["A) 10 ans", "B) 15 ans", "C) 20 ans", "D) 25 ans"], "reponse_correcte": "C", "explication": "Article 5 de l'arrete du 6 octobre 2021 : 20 ans a compter de la mise en service.", "source": "S21 — Q1"},
            {"id": "q2", "question": "Le contrat S21 est regi par ?", "options": ["A) Code de l'urbanisme", "B) Code de l'energie", "C) Code des douanes", "D) Code de la construction"], "reponse_correcte": "B", "explication": "Cadre juridique principal des contrats d'obligation d'achat.", "source": "S21 — Q2"},
            {"id": "q3", "question": "Seuil d'eligibilite OA 2025 pour installations sur batiment ?", "options": ["A) 500 kWc", "B) 400 kWc", "C) 250 kWc", "D) 200 kWc"], "reponse_correcte": "B", "explication": "400 kWc des juin 2025 (D.314-15 modifie). Passe a 200 kWc en 2026.", "source": "S21 — Q3"},
            {"id": "q4", "question": "Le producteur s'engage dans le S21 a : (2 reponses)", "options": ["A) Ne pas revendre l'installation", "B) Fournir une attestation de conformite", "C) Ne pas cumuler OA avec prime locale", "D) Respecter les criteres d'implantation"], "reponse_correcte": "B", "explication": "B et D : attestation de conformite (art. R.314-7) + criteres d'implantation (annexe 2).", "source": "S21 — Q4"},
            {"id": "q5", "question": "Installation de 150 kWc : guichet ouvert en 2025 ?", "options": ["A) Oui, jusqu'au 1er janvier 2026", "B) Non, appel d'offres", "C) Oui, sans condition", "D) Uniquement en ZNI"], "reponse_correcte": "A", "explication": "Decret du 5 juin 2025 : seuil a 200 kWc applicable au 1er janvier 2026.", "source": "S21 — Q5"},
            {"id": "q6", "question": "L'article D.314-15 du Code de l'energie concerne ?", "options": ["A) Les seuils d'eligibilite a l'OA", "B) La CSPE", "C) Les aides fiscales", "D) Le raccordement"], "reponse_correcte": "A", "explication": "Seuils d'eligibilite a l'obligation d'achat.", "source": "S21 — Q6"},
            {"id": "q7", "question": "La puissance P correspond a ?", "options": ["A) Puissance onduleur", "B) Puissance cumulee des panneaux", "C) Puissance de soutirage", "D) Puissance injectee"], "reponse_correcte": "B", "explication": "P = puissance cumulee des panneaux installes.", "source": "S21 — Q7"},
            {"id": "q8", "question": "La puissance Q correspond a ?", "options": ["A) Reserve non installee", "B) Somme des puissances des autres installations sur meme site (18 mois + 100m)", "C) Puissance consommee", "D) Puissance active"], "reponse_correcte": "B", "explication": "Q = somme puissances autres installations meme site, 18 mois et 100m.", "source": "S21 — Q8"},
            {"id": "q9", "question": "Plafond annuel d'achat pour 200 kWc en vente totale ?", "options": ["A) 320 000 kWh", "B) 220 000 kWh", "C) 160 000 kWh", "D) 110 000 kWh"], "reponse_correcte": "D", "explication": "200 kWc x 1100h = 110 000 kWh.", "source": "S21 — Q9"},
            {"id": "q10", "question": "Au-dela du plafond, l'electricite est remuneree ?", "options": ["A) Au tarif reduit (4-5 cEUR/kWh)", "B) Au tarif marche EPEX SPOT", "C) Au tarif initial", "D) Pas du tout"], "reponse_correcte": "A", "explication": "Tarif reduit au-dela du plafond annuel.", "source": "S21 — Q10"},
            {"id": "q11", "question": "Duree de validite d'un Consuel ?", "options": ["A) 6 mois", "B) 1 an", "C) 2 ans", "D) Illimitee"], "reponse_correcte": "B", "explication": "1 an de validite.", "source": "S21 — Q11"},
            {"id": "q12", "question": "En autoconsommation collective, que se passe-t-il avec l'excedent ?", "options": ["A) Toute la production injectee", "B) Uniquement l'excedent non consomme", "C) Zero injection", "D) Ensemble des flux nets"], "reponse_correcte": "B", "explication": "Seul l'excedent non consomme est injecte.", "source": "S21 — Q12"},
            {"id": "q13", "question": "Seuil de puissance BT ?", "options": ["A) 36 kVA", "B) 100 kWc", "C) 250 kVA", "D) 500 kWc"], "reponse_correcte": "C", "explication": "250 kVA = seuil BT.", "source": "S21 — Q13"},
            {"id": "q14", "question": "Installation de 200 kWc raccordee en ?", "options": ["A) BT uniquement", "B) HTA uniquement", "C) BT ou HTA selon le projet", "D) BT si 100m max du poste"], "reponse_correcte": "C", "explication": "Depend du poste de transformation et du schema de branchement.", "source": "S21 — Q14"},
            {"id": "q15", "question": "L'indexation du tarif S21 se fait via ?", "options": ["A) Coefficient L + indices ICHTrev, FM0ABE0000", "B) Indice BTP", "C) Tarif d'acces au reseau", "D) IPC seul"], "reponse_correcte": "A", "explication": "Coefficient L et formules avec indices specifiques.", "source": "S21 — Q15"},
            {"id": "q16", "question": "PVsyst est utilise pour ?", "options": ["A) Simuler les productions PV", "B) Gerer les contrats OA", "C) Faire le plan de masse", "D) Calculer les temps de retour"], "reponse_correcte": "A", "explication": "PVsyst = simulation de production PV.", "source": "S21 — Q16"},
            {"id": "q17", "question": "Archelios Pro permet ? (choix multiples)", "options": ["A) Dimensionnement 3D + chiffrage financier + analyse d'ombrage", "B) Simulation thermique uniquement", "C) Gestion des contrats", "D) Raccordement Enedis"], "reponse_correcte": "A", "explication": "Dimensionnement 3D, chiffrage financier, analyse d'ombrage.", "source": "S21 — Q17"},
            {"id": "q18", "question": "Cap PV est developpe par ?", "options": ["A) Enedis", "B) INES / Transitions", "C) PVGIS", "D) EDF ENR"], "reponse_correcte": "B", "explication": "INES / Transitions.", "source": "S21 — Q18"},
            {"id": "q19", "question": "PVGIS fournit ?", "options": ["A) Donnees meteo + calculs productible", "B) Contrats OA", "C) Plans de masse", "D) Certificats RGE"], "reponse_correcte": "A", "explication": "Donnees meteo, calculs de productible, fichiers Meteonorm.", "source": "S21 — Q19"},
            {"id": "q20", "question": "Signature d'un contrat OA S21 se fait via ?", "options": ["A) EDF OA + signature dematerialisee", "B) Papier obligatoire", "C) Email simple", "D) Fax"], "reponse_correcte": "A", "explication": "Signataire via EDF OA, signature dematerialisee possible.", "source": "S21 — Q20"},
            {"id": "q21", "question": "Un avenant de puissance Q entraine ?", "options": ["A) Modification de tarif si seuil franchi", "B) Prolongation de contrat", "C) Remboursement", "D) Aucun changement"], "reponse_correcte": "A", "explication": "Modification de tarif si seuil franchi + revision des factures.", "source": "S21 — Q21"},
            {"id": "q22", "question": "La prime Pa est versee ?", "options": ["A) En 5 fois", "B) En 3 annuites", "C) En 1 fois", "D) Au prorata des kWh"], "reponse_correcte": "C", "explication": "Prime a l'investissement Pa versee en 1 seule fois.", "source": "S21 — Q22"},
            {"id": "q23", "question": "Le tarif Tc est ?", "options": ["A) Pour les 100-500 kWc non eligibles Pa ou Pb, indexe annuellement, defini par trimestre tarifaire", "B) Fixe pendant 20 ans", "C) Pour les < 9 kWc", "D) Pour l'autoconsommation"], "reponse_correcte": "A", "explication": "Tarif Tc pour 100-500 kWc, indexe, defini par trimestre.", "source": "S21 — Q23"},
            {"id": "q24", "question": "Referentiel de raccordement ?", "options": ["A) Enedis-PRO-RAC_03E", "B) TURPE", "C) NF C15-100", "D) ISO 50001"], "reponse_correcte": "A", "explication": "Enedis-PRO-RAC_03E est le referentiel.", "source": "S21 — Q24"},
            {"id": "q25", "question": "En cas d'annulation, la garantie de 10 000 EUR ?", "options": ["A) Deconsignee automatiquement", "B) Prelevee par l'Etat", "C) Remboursee sous 30j", "D) Conservee par EDF OA"], "reponse_correcte": "B", "explication": "Prelevee par l'Etat si non deconsignee dans les delais.", "source": "S21 — Q25"},
            {"id": "q26", "question": "Le dispositif S3REnR ?", "options": ["A) Definit les zones d'accueil EnR + schema reseau Enedis + impact couts raccordement", "B) Concerne uniquement l'autoconsommation", "C) Est optionnel", "D) Ne concerne que la BT"], "reponse_correcte": "A", "explication": "Zones d'accueil, schema reseau, impact couts raccordement, obligatoire en HTA.", "source": "S21 — Q26"},
            {"id": "q27", "question": "Projet autoconsommation individuelle sans injection : obligations ?", "options": ["A) Rien", "B) Declarer puissance P + faire une DCR", "C) Contrat OA obligatoire", "D) CRAE obligatoire"], "reponse_correcte": "B", "explication": "Declaration puissance P et DCR requise pour conformite. Pas de CRAE.", "source": "S21 — Q27"},
            {"id": "q28", "question": "Seuil de productibilite minimal attendu ?", "options": ["A) 500 kWh/kWc/an", "B) 800 kWh/kWc/an", "C) 1000 kWh/kWc/an", "D) 1400 kWh/kWc/an"], "reponse_correcte": "C", "explication": "1000 kWh/kWc/an pour une installation bien orientee.", "source": "S21 — Q28"},
            {"id": "q29", "question": "Analyse de rentabilite integre ?", "options": ["A) Inflation + taux d'actualisation + charges d'exploitation + prix du module", "B) Seulement le prix du module", "C) Seulement l'inflation", "D) Rien de tout ca"], "reponse_correcte": "A", "explication": "Tous les parametres : inflation, taux d'actualisation, charges, prix module.", "source": "S21 — Q29"},
            {"id": "q30", "question": "NF C15-100 concerne ?", "options": ["A) Reseaux Enedis", "B) Modules thermiques", "C) Installations electriques basse tension", "D) Surveillance"], "reponse_correcte": "C", "explication": "Norme pour les installations electriques basse tension.", "source": "S21 — Q30"},
        ],
    },

    # -----------------------------------------------------------------------
    # MODULE 10 — GetAccept (30 questions)
    # Source : module de formation get accept.docx
    # -----------------------------------------------------------------------
    "10": {
        "id": "10",
        "titre": "GetAccept — Signature electronique",
        "description": "30 questions sur l'envoi, le suivi, la signature electronique et les bonnes pratiques GetAccept.",
        "nb_questions": 30,
        "source": "module de formation get accept.docx",
        "questions": [
            {"id": "q1", "question": "A quoi sert GetAccept ?", "options": ["A) Faire des visios", "B) Envoyer, suivre et faire signer des documents commerciaux", "C) Suivre la meteo"], "reponse_correcte": "B", "explication": "Envoi, suivi et signature de documents commerciaux.", "source": "GetAccept — Q1"},
            {"id": "q2", "question": "Que doit contenir une proposition envoyee via GetAccept ?", "options": ["A) Un tableau Excel", "B) Le nom de l'ingenieur", "C) Nom du client, scenario personnalise, donnees techniques et financieres"], "reponse_correcte": "C", "explication": "Personnalisation complete : client, scenario, donnees.", "source": "GetAccept — Q2"},
            {"id": "q3", "question": "Quand envoyer une proposition via GetAccept ?", "options": ["A) Avant de parler au client", "B) Une fois l'etude terminee et validee en interne", "C) Apres qu'il ait signe sur papier"], "reponse_correcte": "B", "explication": "Etude terminee + validee en interne = pret pour envoi.", "source": "GetAccept — Q3"},
            {"id": "q4", "question": "Que fait GetAccept quand le client ouvre le document ?", "options": ["A) Rien", "B) Envoie une notification", "C) Lance un appel"], "reponse_correcte": "B", "explication": "Notification en temps reel quand le client ouvre.", "source": "GetAccept — Q4"},
            {"id": "q5", "question": "Client n'ouvre pas 48h apres envoi. Que faire ?", "options": ["A) Supprimer", "B) Relancer par telephone ou SMS avec bienveillance", "C) Ne rien faire"], "reponse_correcte": "B", "explication": "Relance bienveillante apres 48h.", "source": "GetAccept — Q5"},
            {"id": "q6", "question": "La signature electronique GetAccept est-elle legalement valide ?", "options": ["A) Non", "B) Oui, legalement valide", "C) Seulement en France"], "reponse_correcte": "B", "explication": "Signature electronique legalement valide.", "source": "GetAccept — Q6"},
            {"id": "q7", "question": "Quel document valider en amont avant envoi GetAccept ?", "options": ["A) Un prospectus", "B) Le scenario issu d'Optiwize", "C) Un message audio"], "reponse_correcte": "B", "explication": "Le scenario Optiwize valide = base du GetAccept.", "source": "GetAccept — Q7"},
            {"id": "q8", "question": "Bonne pratique apres envoi d'un GetAccept ?", "options": ["A) Oublier le client", "B) Le noter dans ton suivi et planifier une relance", "C) Mettre fin au dossier"], "reponse_correcte": "B", "explication": "Suivi + relance planifiee.", "source": "GetAccept — Q8"},
            {"id": "q9", "question": "Qui peut modifier un document deja envoye ?", "options": ["A) Le client", "B) Toi, si en mode brouillon", "C) Personne"], "reponse_correcte": "B", "explication": "Modification possible si document en brouillon.", "source": "GetAccept — Q9"},
            {"id": "q10", "question": "Quelle colonne Monday mettre a jour apres envoi GetAccept ?", "options": ["A) Formule", "B) Statut du lead : 'Proposition envoyee'", "C) Date CONSUEL"], "reponse_correcte": "B", "explication": "Statut mis a jour : Proposition envoyee.", "source": "GetAccept — Q10"},
            {"id": "q11", "question": "Comment suivre si le client a consulte plusieurs fois ?", "options": ["A) Appeler GetAccept", "B) Historique de vues dans la fiche du document", "C) Verifier Optiwize"], "reponse_correcte": "B", "explication": "Historique de vues disponible dans la fiche.", "source": "GetAccept — Q11"},
            {"id": "q12", "question": "Frequence de relance apres envoi sans reponse ?", "options": ["A) Jamais", "B) 24 a 72h, puis 5 a 7 jours", "C) 10 jours minimum"], "reponse_correcte": "B", "explication": "24-72h premiere relance, 5-7j deuxieme.", "source": "GetAccept — Q12"},
            {"id": "q13", "question": "Client ouvre mais ne signe pas. Que faire ?", "options": ["A) Fermer le dossier", "B) Analyser son comportement (temps passe, pages vues) pour adapter la relance", "C) Renvoyer le meme document"], "reponse_correcte": "B", "explication": "Analyse du comportement = relance adaptee.", "source": "GetAccept — Q13"},
            {"id": "q14", "question": "A quoi sert une video de presentation dans GetAccept ?", "options": ["A) Touche commerciale personnalisee", "B) Ralentir le chargement", "C) Faire un test"], "reponse_correcte": "A", "explication": "Ajout video = personnalisation + engagement.", "source": "GetAccept — Q14"},
            {"id": "q15", "question": "Document envoye est errone. Que faire ?", "options": ["A) Esperer qu'il ne remarque pas", "B) Revoquer/archiver, corriger, puis renvoyer", "C) Relancer en urgence"], "reponse_correcte": "B", "explication": "Revoquer, corriger, renvoyer. Jamais esperer.", "source": "GetAccept — Q15"},
            {"id": "q16", "question": "Quand le client signe electroniquement, que se passe-t-il ?", "options": ["A) Bon de reduction", "B) Document signe disponible en PDF", "C) Optiwize se met a jour"], "reponse_correcte": "B", "explication": "PDF signe automatiquement disponible.", "source": "GetAccept — Q16"},
            {"id": "q17", "question": "Pour un mandat de representation, quel outil ?", "options": ["A) PDF a imprimer", "B) GetAccept", "C) Email simple"], "reponse_correcte": "B", "explication": "GetAccept pour tous les documents a signer.", "source": "GetAccept — Q17"},
            {"id": "q18", "question": "Statut 'en cours de signature' signifie ?", "options": ["A) Client en train de lire ou reflechir", "B) Client a refuse", "C) Rien"], "reponse_correcte": "A", "explication": "Le client est en cours de lecture/reflexion.", "source": "GetAccept — Q18"},
            {"id": "q19", "question": "Client a signe mais aucune action faite ensuite. Que faire ?", "options": ["A) Preparer l'etape suivante (ENEDIS, installation)", "B) Attendre", "C) Supprimer la ligne"], "reponse_correcte": "A", "explication": "Post-signature = preparer la suite (ENEDIS, installation).", "source": "GetAccept — Q19"},
            {"id": "q20", "question": "GetAccept est accessible sur mobile ?", "options": ["A) Non", "B) Oui, sur tous les supports", "C) Uniquement sur iPad"], "reponse_correcte": "B", "explication": "Accessible sur tous les supports.", "source": "GetAccept — Q20"},
            {"id": "q21", "question": "Client dit 'j'ai bien recu, je regarde demain' mais ne signe jamais. Que faire ?", "options": ["A) Insister 3 fois/jour", "B) Relancer avec question personnalisee liee a son besoin", "C) Le bloquer"], "reponse_correcte": "B", "explication": "Relance personnalisee, pas spam.", "source": "GetAccept — Q21"},
            {"id": "q22", "question": "Envoyer plusieurs documents (mandat + etude + video). Meilleure pratique ?", "options": ["A) Un envoi groupe avec chapitrage ou documents joints", "B) Un email a part", "C) WhatsApp"], "reponse_correcte": "A", "explication": "Envoi groupe dans GetAccept avec chapitrage.", "source": "GetAccept — Q22"},
            {"id": "q23", "question": "Client refuse de signer. Que faire dans GetAccept ?", "options": ["A) Supprimer le document", "B) Noter l'objection dans le commentaire et cloturer proprement dans Monday", "C) Le forcer"], "reponse_correcte": "B", "explication": "Objection notee + cloture propre dans Monday.", "source": "GetAccept — Q23"},
            {"id": "q24", "question": "Le bouton 'tracking' sert a ?", "options": ["A) Suivre les performances equipe", "B) Voir en temps reel les interactions avec le document", "C) Localiser le client"], "reponse_correcte": "B", "explication": "Interactions en temps reel avec le document.", "source": "GetAccept — Q24"},
            {"id": "q25", "question": "Nom du client reste generique dans le template. Consequence ?", "options": ["A) Perte de credibilite", "B) Ce n'est pas grave", "C) Gain de temps"], "reponse_correcte": "A", "explication": "Le client ne comprend pas = perte de credibilite.", "source": "GetAccept — Q25"},
            {"id": "q26", "question": "Pourquoi le lien personnalise GetAccept est utile ?", "options": ["A) Traquer les clics", "B) Faciliter l'acces au bon document sans lui redemander ses infos", "C) Hacker son navigateur"], "reponse_correcte": "B", "explication": "Acces facile au bon document.", "source": "GetAccept — Q26"},
            {"id": "q27", "question": "Ou suivre ses performances d'envoi/signatures ?", "options": ["A) Monday", "B) Statistiques de GetAccept", "C) Son carnet"], "reponse_correcte": "B", "explication": "Statistiques GetAccept = suivi performances.", "source": "GetAccept — Q27"},
            {"id": "q28", "question": "Que faire AVANT d'envoyer un GetAccept ?", "options": ["A) Verifier que tous les documents sont a jour et valides", "B) Juste remplir le nom", "C) Rien"], "reponse_correcte": "A", "explication": "Verification complete avant envoi.", "source": "GetAccept — Q28"},
            {"id": "q29", "question": "Pourquoi noter dans Monday l'envoi et l'etat du GetAccept ?", "options": ["A) Eviter de refaire deux fois", "B) Suivi manager complet", "C) Taux de conversion", "D) Toutes les reponses"], "reponse_correcte": "D", "explication": "A, B et C — toutes les raisons sont valides.", "source": "GetAccept — Q29"},
            {"id": "q30", "question": "Client ouvre 4 fois sans signer. Meilleure strategie ?", "options": ["A) L'oublier", "B) L'appeler : 'Je vois que vous avez consulte le projet, y a-t-il un point a eclaircir ?'", "C) Le supprimer"], "reponse_correcte": "B", "explication": "Relance adaptee basee sur le tracking.", "source": "GetAccept — Q30"},
        ],
    },

    # -----------------------------------------------------------------------
    # MODULE 11 — Monday/Optiwise/Likewatt (30+30 questions = 30 Monday + 30 Optiwize)
    # Source : module formation monday reporting.docx + module formation likewatt optiwise.docx
    # Fusionne en 30 questions (15 Monday + 15 Optiwize)
    # -----------------------------------------------------------------------
    "11": {
        "id": "11",
        "titre": "Outils — Monday + Optiwize/Likewatt",
        "description": "30 questions sur Monday (CRM, leads, reporting) et Optiwize/Likewatt (simulation PV, rentabilite).",
        "nb_questions": 30,
        "source": "module formation monday reporting.docx + module formation likewatt optiwise.docx",
        "questions": [
            # Monday (15 questions)
            {"id": "q1", "question": "Dans quel delai un lead doit-il etre traite dans Monday ?", "options": ["A) 72h", "B) 24h", "C) 48h"], "reponse_correcte": "B", "explication": "24h sans exception.", "source": "Monday — Q1"},
            {"id": "q2", "question": "Le commentaire dans Monday est :", "options": ["A) Optionnel si on appelle", "B) Obligatoire a chaque etape", "C) A faire a la fin seulement"], "reponse_correcte": "B", "explication": "Obligatoire a chaque etape. Tout doit etre trace.", "source": "Monday — Q2"},
            {"id": "q3", "question": "Si tu oublies de mettre a jour le statut du lead ?", "options": ["A) Aucun impact", "B) Le lead n'est plus visible dans les filtres et peut etre oublie", "C) Le manager t'appelle"], "reponse_correcte": "B", "explication": "Lead invisible = lead oublie.", "source": "Monday — Q3"},
            {"id": "q4", "question": "Le champ 'Dernier contact' est rempli quand ?", "options": ["A) Si le client a signe", "B) Apres chaque echange avec le client", "C) Une seule fois"], "reponse_correcte": "B", "explication": "Apres CHAQUE echange.", "source": "Monday — Q4"},
            {"id": "q5", "question": "Qui est responsable de la completude des champs ?", "options": ["A) L'ingenieur", "B) Le client", "C) Le vendeur lui-meme"], "reponse_correcte": "C", "explication": "Le vendeur est responsable.", "source": "Monday — Q5"},
            {"id": "q6", "question": "Lead avec 'Derniere action' datant de 10 jours. Tu dois :", "options": ["A) Ignorer", "B) Signaler et/ou relancer", "C) Supprimer"], "reponse_correcte": "B", "explication": "+10 jours sans action = signaler et relancer.", "source": "Monday — Q6"},
            {"id": "q7", "question": "Tu n'as pas commente le lead, mais tu l'as appele. Suffisant ?", "options": ["A) Oui, c'est oral", "B) Non, tout doit etre trace dans Monday", "C) Oui si tu as un SMS"], "reponse_correcte": "B", "explication": "Ce qui n'est pas ecrit n'existe pas.", "source": "Monday — Q7"},
            {"id": "q8", "question": "Lead en 'ECHEANCE NON STATUE'. Que faire ?", "options": ["A) Ignorer", "B) Appeler et clarifier le statut + commenter", "C) Supprimer la ligne"], "reponse_correcte": "B", "explication": "Appeler et clarifier immediatement.", "source": "Monday — Q8"},
            {"id": "q9", "question": "Comment savoir si le lead est pret pour l'etude ?", "options": ["A) Tous les champs remplis + commentaire clair + statut mis a jour", "B) Tu le sens bien", "C) C'est ecrit 'OK'"], "reponse_correcte": "A", "explication": "Tous les champs + commentaire + statut = pret.", "source": "Monday — Q9"},
            {"id": "q10", "question": "Frequence de verification des leads dans Monday ?", "options": ["A) Une fois par semaine", "B) Une fois par jour minimum", "C) Une fois par mois"], "reponse_correcte": "B", "explication": "1 fois par jour minimum.", "source": "Monday — Q10"},
            {"id": "q11", "question": "Tu assignes un lead a un collegue sans commentaire. Consequence ?", "options": ["A) Il sait quoi faire", "B) Il ne comprend pas le contexte = lead mal traite", "C) Ce n'est pas grave"], "reponse_correcte": "B", "explication": "Sans contexte = mauvais traitement du lead.", "source": "Monday — Q11"},
            {"id": "q12", "question": "Quand relancer un lead sans reponse dans Monday ?", "options": ["A) Si colonne 'Dernier contact' date de +5 jours", "B) Si le client a dit non", "C) Si la colonne 'Directeur de region' est vide"], "reponse_correcte": "A", "explication": "+5 jours = relance obligatoire.", "source": "Monday — Q12"},
            {"id": "q13", "question": "Quelle est la vraie preuve que tu as bien traite un lead ?", "options": ["A) Tu le dis au manager", "B) Le commentaire, la date, le statut mis a jour dans Monday", "C) Ton historique WhatsApp"], "reponse_correcte": "B", "explication": "Commentaire + date + statut = preuve.", "source": "Monday — Q13"},
            {"id": "q14", "question": "Le champ 'Formule' correspond a ?", "options": ["A) Une formule mathematique", "B) Le type de projet ou besoin du client", "C) Le nom du fichier Excel"], "reponse_correcte": "B", "explication": "Type de projet / besoin client.", "source": "Monday — Q14"},
            {"id": "q15", "question": "Le lien Sembly est utilise pour ?", "options": ["A) Replay automatique de visio", "B) Appeler le client", "C) Envoyer un devis"], "reponse_correcte": "A", "explication": "Replay automatique d'entretien visio.", "source": "Monday — Q15"},
            # Optiwize/Likewatt (15 questions)
            {"id": "q16", "question": "Quel outil pour analyser la rentabilite PV chez OXEO ?", "options": ["A) GetAccept", "B) Excel", "C) Optiwize"], "reponse_correcte": "C", "explication": "Optiwize = outil de rentabilite PV.", "source": "Optiwize — Q1"},
            {"id": "q17", "question": "Info OBLIGATOIRE pour creer un site dans Optiwize ?", "options": ["A) SIRET", "B) Numero PRM (ou PDL)", "C) Type de toiture"], "reponse_correcte": "B", "explication": "PRM obligatoire pour creer un site.", "source": "Optiwize — Q2"},
            {"id": "q18", "question": "Si tu n'as pas le PRM, que faire ?", "options": ["A) Attendre le technicien", "B) Importer une courbe de charge CSV", "C) Fermer le dossier"], "reponse_correcte": "B", "explication": "Courbe de charge CSV en remplacement du PRM.", "source": "Optiwize — Q5"},
            {"id": "q19", "question": "Le TRI signifie ?", "options": ["A) Temps de retour integre", "B) Taux de rentabilite interne", "C) Tarif regional individuel"], "reponse_correcte": "B", "explication": "TRI = Taux de Rentabilite Interne.", "source": "Optiwize — Q10"},
            {"id": "q20", "question": "Si tu coches 'Optimisation' dans la section PV ?", "options": ["A) Le logiciel propose automatiquement la puissance ideale", "B) Lance un appel telephonique", "C) Telecharge des fichiers"], "reponse_correcte": "A", "explication": "Optimisation automatique de la puissance ideale.", "source": "Optiwize — Q16"},
            {"id": "q21", "question": "Difference entre CAPEX et OPEX ?", "options": ["A) CAPEX = investissement, OPEX = cout d'exploitation", "B) Ce sont des modeles de panneaux", "C) Aucun"], "reponse_correcte": "A", "explication": "CAPEX = investissement initial / OPEX = exploitation.", "source": "Optiwize — Q17"},
            {"id": "q22", "question": "VAN negative signifie ?", "options": ["A) Rentabilite positive", "B) Rentabilite non assuree", "C) Le client peut signer"], "reponse_correcte": "B", "explication": "VAN negative = projet non rentable. Ne pas presenter.", "source": "Optiwize — Q22"},
            {"id": "q23", "question": "Quand remplir les cles de repartition ?", "options": ["A) Toujours", "B) Seulement en autoconsommation collective", "C) Quand tu veux"], "reponse_correcte": "B", "explication": "Cles de repartition = autoconsommation collective uniquement.", "source": "Optiwize — Q23"},
            {"id": "q24", "question": "'PV ecrete' dans les resultats signifie ?", "options": ["A) Panneaux casses", "B) Production perdue car non utilisee ni injectee", "C) Panneaux ecartes de la toiture"], "reponse_correcte": "B", "explication": "Production perdue = ni consommee ni injectee.", "source": "Optiwize — Q24"},
            {"id": "q25", "question": "Quand desactiver l'option 'Optimisation' ?", "options": ["A) Si tu veux forcer une puissance manuelle", "B) Si tu ne connais pas les donnees", "C) Toujours"], "reponse_correcte": "A", "explication": "Desactiver si puissance imposee manuellement.", "source": "Optiwize — Q25"},
            {"id": "q26", "question": "Le 'SOC' dans la batterie signifie ?", "options": ["A) Solde offert client", "B) State of Charge — etat de charge", "C) Simulation obligatoire client"], "reponse_correcte": "B", "explication": "SOC = State of Charge.", "source": "Optiwize — Q26"},
            {"id": "q27", "question": "Client choisit modele 'location'. Le CAPEX est ?", "options": ["A) A zero pour lui", "B) Multiplie", "C) Dedouble"], "reponse_correcte": "A", "explication": "En location, CAPEX = 0 pour le client.", "source": "Optiwize — Q27"},
            {"id": "q28", "question": "Calculer rentabilite sur 20 ans. Tu dois ?", "options": ["A) Mettre 20 ans dans l'horizon du scenario", "B) Mettre 20 kWc", "C) Choisir une vanne d'arret"], "reponse_correcte": "A", "explication": "Horizon du scenario = 20 ans.", "source": "Optiwize — Q28"},
            {"id": "q29", "question": "Avant d'envoyer l'etude, verifier que ?", "options": ["A) Le fichier est joli", "B) Tous les champs remplis, resultats coherents, hypotheses claires", "C) Le client est sympathique"], "reponse_correcte": "B", "explication": "Verification complete : champs, resultats, hypotheses.", "source": "Optiwize — Q30"},
            {"id": "q30", "question": "Oubli des puissances souscrites. Consequence ?", "options": ["A) Optiwize corrige automatiquement", "B) Resultats fausses", "C) Rien"], "reponse_correcte": "B", "explication": "Puissances manquantes = resultats fausses.", "source": "Optiwize — Q21"},
        ],
    },

    # -----------------------------------------------------------------------
    # MODULE 12 — 6 Methodes de Closing + Technique PV (15 questions)
    # Source : 6 METHODES DE CLOSINGS.pages + MODULE FORMATION TECHNIQUE POINT IMPORTANT.docx
    # -----------------------------------------------------------------------
    "12": {
        "id": "12",
        "titre": "6 Methodes de Closing + Technique PV RGE",
        "description": "15 questions sur les 6 techniques de closing et les fondamentaux techniques PV (RGE/OPQIBI).",
        "nb_questions": 15,
        "source": "6 METHODES DE CLOSINGS.pages + MODULE FORMATION TECHNIQUE POINT IMPORTANT.docx",
        "questions": [
            # 6 Closings (6 questions)
            {"id": "q1", "question": "Qu'est-ce que l'illusion du choix ?", "options": ["A) Mentir sur les options", "B) Proposer 2 options qui menent toutes les deux au oui", "C) Donner un faux delai", "D) Manipuler le prix"], "reponse_correcte": "B", "explication": "'On demarre en juin ou en septembre ?' Les deux = signature.", "source": "6 Closings — Illusion du choix"},
            {"id": "q2", "question": "La technique de projection consiste a ?", "options": ["A) Montrer des photos", "B) Parler au futur comme si c'etait deja decide", "C) Projeter un PowerPoint", "D) Envoyer un mail"], "reponse_correcte": "B", "explication": "'Quand les travaux seront faits, vous constaterez...' Le client se projette.", "source": "6 Closings — Projection"},
            {"id": "q3", "question": "L'anti-vente consiste a ?", "options": ["A) Baisser le prix", "B) Refuser de vendre pour creer de la valeur", "C) Partir", "D) Insulter le concurrent"], "reponse_correcte": "B", "explication": "'Si vous preferez les fixes, on ne les installera pas. Nos ingenieurs refusent.' Puis silence.", "source": "6 Closings — Anti-vente"},
            {"id": "q4", "question": "La validation d'expert consiste a ?", "options": ["A) Demander 'On signe ?'", "B) Cloturer sans prononcer 'signature' — c'est une consequence logique", "C) Forcer la decision", "D) Donner un ultimatum"], "reponse_correcte": "B", "explication": "'On valide l'etude et on programme la suite.'", "source": "6 Closings — Validation d'expert"},
            {"id": "q5", "question": "Le silence apres le prix : combien de secondes ?", "options": ["A) 0", "B) 2 a 4 secondes", "C) 10 secondes", "D) 1 minute"], "reponse_correcte": "B", "explication": "2 a 4 secondes. Celui qui parle en premier perd.", "source": "6 Closings — Silence"},
            {"id": "q6", "question": "La technique des 3 urgences combine ?", "options": ["A) Prix, promo, stock", "B) Planning + Tarif + Competition", "C) Peur, urgence, rarete", "D) Manager, directeur, comptable"], "reponse_correcte": "B", "explication": "3 urgences : planning, tarif, competition.", "source": "6 Closings — 3 Urgences"},
            # Technique PV RGE (9 questions)
            {"id": "q7", "question": "Qu'est-ce qu'un kWc ?", "options": ["A) Kilowatt courant", "B) Kilowatt crete", "C) Kilowatt consomme", "D) Kilowatt cumule"], "reponse_correcte": "B", "explication": "Puissance nominale d'un module en conditions standard.", "source": "Technique PV — Q1"},
            {"id": "q8", "question": "Quel composant convertit la lumiere en electricite ?", "options": ["A) Onduleur", "B) Module PV", "C) Compteur", "D) Batterie"], "reponse_correcte": "B", "explication": "Le module PV (panneau photovoltaique).", "source": "Technique PV — Q2"},
            {"id": "q9", "question": "Role principal de l'onduleur ?", "options": ["A) Augmenter la tension", "B) Convertir le courant continu en alternatif", "C) Controler l'ensoleillement", "D) Alimenter les batteries"], "reponse_correcte": "B", "explication": "DC vers AC.", "source": "Technique PV — Q5"},
            {"id": "q10", "question": "Duree de vie typique d'un module PV ?", "options": ["A) 5 ans", "B) 10 ans", "C) 25 ans", "D) 50 ans"], "reponse_correcte": "C", "explication": "25 ans de duree de vie typique.", "source": "Technique PV — Q6"},
            {"id": "q11", "question": "Que represente le PR (facteur de performance) dans Archelios ?", "options": ["A) Rendement onduleur", "B) Rendement total du systeme PV apres pertes", "C) Taux d'autoconsommation", "D) Rendement du module"], "reponse_correcte": "B", "explication": "Rendement total systeme apres toutes les pertes.", "source": "Technique PV — Q9"},
            {"id": "q12", "question": "Influence d'un masque proche (arbre, cheminee) sur la production ?", "options": ["A) Negligeable", "B) Positif", "C) Peut entrainer une perte significative", "D) Augmente la tension"], "reponse_correcte": "C", "explication": "Perte significative possible.", "source": "Technique PV — Q11"},
            {"id": "q13", "question": "Le ratio DC/AC represente ?", "options": ["A) Tension du reseau", "B) Rapport puissance modules / puissance onduleur", "C) Taux d'autoconsommation", "D) Rendement thermique"], "reponse_correcte": "B", "explication": "Rapport entre puissance modules et puissance onduleur.", "source": "Technique PV — Q13"},
            {"id": "q14", "question": "Obligations RGE pour un bureau d'etudes en audit technique ?", "options": ["A) Aucune", "B) ISO 9001", "C) Procedures RGE definies par Qualit'EnR ou OPQIBI", "D) Rapport sur 1 page"], "reponse_correcte": "C", "explication": "Procedures RGE Qualit'EnR ou OPQIBI.", "source": "Technique PV — Q15"},
            {"id": "q15", "question": "Role du DCR (Dossier de Consultation Reseau) ENEDIS ?", "options": ["A) Financement bancaire", "B) Garanties de production", "C) Preparer la demande de raccordement au reseau", "D) Contacter la mairie"], "reponse_correcte": "C", "explication": "Preparation de la demande de raccordement.", "source": "Technique PV — Q16"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Comptage total des questions
# ---------------------------------------------------------------------------

_TOTAL_QUESTIONS = sum(m["nb_questions"] for m in MODULES.values())
# 30+40+30+20+12+10+15+30+30+30+30+15 = 292 questions QCM + 44 objections = 336 total


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
            "source": m.get("source", ""),
        })
    return jsonify({
        "total_modules": len(MODULES),
        "total_questions_qcm": _TOTAL_QUESTIONS,
        "total_objections": len(OBJECTIONS),
        "total_closings": len(SIX_CLOSINGS),
        "modules": modules_list,
    })


@formation_bp.route("/formation/module/<module_id>", methods=["GET"])
def get_module(module_id):
    """Contenu d'un module (questions + reponses)."""
    module = MODULES.get(module_id)
    if not module:
        return jsonify({"error": f"Module {module_id} introuvable. Modules disponibles : 1-{len(MODULES)}."}), 404
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


@formation_bp.route("/formation/objection/<int:numero>", methods=["GET"])
def get_objection(numero):
    """Retourne 1 objection + reponse type + technique ADERA applicable."""
    if numero < 1 or numero > len(OBJECTIONS):
        return jsonify({
            "error": f"Objection {numero} introuvable. Numeros disponibles : 1-{len(OBJECTIONS)}."
        }), 404
    obj = OBJECTIONS[numero - 1]
    return jsonify(obj)


@formation_bp.route("/formation/objections", methods=["GET"])
def list_objections():
    """Liste de toutes les 44 objections."""
    return jsonify({
        "total": len(OBJECTIONS),
        "methode": "ADERA — Accueillir, Decouvrir, Empathiser, Repondre, Ancrer",
        "objections": [{"numero": o["numero"], "objection": o["objection"]} for o in OBJECTIONS],
    })


@formation_bp.route("/formation/closings", methods=["GET"])
def list_closings():
    """Liste des 6 methodes de closing."""
    return jsonify({
        "total": len(SIX_CLOSINGS),
        "closings": SIX_CLOSINGS,
    })


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def register_formation_routes(app):
    """Enregistre le blueprint formation sur l'app Flask."""
    app.register_blueprint(formation_bp)
