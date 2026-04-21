# CEE ENGINE V37 PRO — ARBORESCENCE COMPLETE (First Principles)

```
CEE ENGINE V37 PRO — WCS / Jimmy Wilner
Outil d'audit predictif CEE le plus complet du marche
Positionnement : diagnostic commercial PRO direct entreprise (pas artisan, pas particulier)
Stack : Python Flask (port 5001) + oracle.html (735 Ko, 10 675 lignes)
========================================================================

├── 1. FIRST PRINCIPLE : IDENTIFICATION (qui est le client ?)
│   ├── 1.1 SIRET → Identite entreprise (api.py /siret/search, /analyse)
│   │   ├── 1.1.1 API recherche-entreprises.api.gouv.fr
│   │   │   ├── Raison sociale
│   │   │   ├── Code NAF / APE (243+ codes mappes)
│   │   │   ├── Adresse siege
│   │   │   ├── Forme juridique
│   │   │   ├── Effectif salarie
│   │   │   └── Etat administratif (actif/ferme)
│   │   ├── 1.1.2 FIX V37 : SIRET branches — patch siege avec matching_etablissements[0]
│   │   │   └── Avant V37 : renvoyait adresse siege pour toute branche → mauvaise commune/zone/APE
│   │   ├── 1.1.3 /etablissements/<siren> — liste TOUS les etablissements actifs
│   │   │   └── FIX V37 : limite_matching_etablissements=100 (avant : bloque a 10)
│   │   ├── 1.1.4 Fallback SIREN retry (14→9 chiffres)
│   │   ├── 1.1.5 Fallback OpenDataSoft Sirene
│   │   ├── 1.1.6 Cache SIRET LRU 500 entrees (24h TTL)
│   │   │   └── FIX V37 : borne pour eviter fuite memoire
│   │   └── 1.1.7 URL-encoding systematique query params (urllib.parse.quote) ✅
│   │
│   ├── 1.2 Enrichissement Open Data (bdnb_client.py, pipeline.py)
│   │   ├── 1.2.1 Cadastre IGN (parcelle)
│   │   │   └── Lien carte cadastre z=19 cible sur le batiment
│   │   ├── 1.2.2 BD TOPO V3 IGN (/batiment endpoint)
│   │   │   ├── Surface au sol
│   │   │   ├── Hauteur batiment
│   │   │   ├── Materiaux construction
│   │   │   └── FIX V37 : selection plus grand batiment < 50m (pas le plus proche)
│   │   ├── 1.2.3 DPE ADEME (/dpe endpoint) — 3 datasets
│   │   │   ├── DPE logement (14,5M entries)
│   │   │   ├── DPE tertiaire (516K entries)
│   │   │   ├── Audits energetiques (50K+ entries)
│   │   │   ├── Validation GPS Haversine + score confiance (high/medium/low)
│   │   │   ├── Surface cross-validation (alerte si ecart >30%)
│   │   │   └── Liens telechargement DPE/audit (observatoire ADEME)
│   │   ├── 1.2.4 BAN — geocodage adresse → lat/lon
│   │   ├── 1.2.5 BODACC — procedures judiciaires (alerte risque)
│   │   └── 1.2.6 Liens cartes cibles
│   │       ├── Satellite 100m
│   │       ├── Street View
│   │       ├── Cadastre z=19
│   │       └── PLU
│   │
│   └── 1.3 Intelligence sectorielle (auto_detect.py, mapping_naf_fiches.py)
│       ├── 1.3.1 Mapping NAF → secteur (243+ codes APE)
│       ├── 1.3.2 Profil pro (32+ profils Intelligence Pro)
│       │   ├── Equipements probables par APE
│       │   └── Repartition energie estimee
│       ├── 1.3.3 16 profils micro-activites
│       │   ├── 5 AGRI (serres, batiment elevage, sechage, irrigation, stockage)
│       │   ├── 3 IND (process thermique, froid industriel, moteurs)
│       │   ├── 4 BAT (bureaux, commerce, sante, enseignement)
│       │   ├── 2 BAR (copro, bailleur SCI)
│       │   ├── 1 TRA (transport)
│       │   └── 1 RES (reseau)
│       ├── 1.3.4 Zones d'usage detectees (BAT principal + IND secondaire)
│       └── 1.3.5 Scoring business auto (auto_detect.py)
│           └── Pack optimal recommande + PAC remplacement logique V36
│
├── 2. FIRST PRINCIPLE : ELIGIBILITE (a quelles aides le client a droit ?)
│   ├── 2.1 Catalogue fiches CEE (moteur_cee_master.py, 224 fiches)
│   │   ├── 2.1.1 6 secteurs couverts
│   │   │   ├── BAT — Batiment tertiaire (47 fiches avec FOST verifie)
│   │   │   ├── BAR — Batiment residentiel
│   │   │   ├── IND — Industrie
│   │   │   ├── AGRI — Agriculture
│   │   │   ├── TRA — Transport
│   │   │   └── RES — Reseaux
│   │   ├── 2.1.2 Top fiches par secteur (top_fiches_secteur.py)
│   │   ├── 2.1.3 Extraction fiches ATEE (parse_atee.py)
│   │   ├── 2.1.4 Scraping fiches (scrape_fiches.py)
│   │   └── 2.1.5 Validation fiches (validate_fiches.py)
│   │       └── Verification abrogations, dates fin, modifications
│   │
│   ├── 2.2 Filtrage eligibilite (moteur_cee_master.py → analyser())
│   │   ├── 2.2.1 Zone climatique (H1/H2/H3/DOM)
│   │   │   └── Corse 2A/2B ajoutes en zone H3
│   │   ├── 2.2.2 Code NAF → fiches applicables
│   │   ├── 2.2.3 Surface batiment
│   │   ├── 2.2.4 Type energie (combustible/electricite via z_elec)
│   │   ├── 2.2.5 Regle des 75% (/regles/75pct)
│   │   │   └── Mixite secteurs : si >75% surface = un secteur → tout le batiment bascule
│   │   ├── 2.2.6 Tolerance batiment mixte (/regles/tolerance-mixte)
│   │   │   └── Surface tertiaire vs residentielle
│   │   └── 2.2.7 Verification remplacement premature (check_remplacement_premature)
│   │
│   ├── 2.3 Validations juridiques (cee_excellence_pro.py)
│   │   ├── 2.3.1 Non-cumul CEE (operations incompatibles)
│   │   ├── 2.3.2 DPE 2021+ obligatoire (si applicable)
│   │   ├── 2.3.3 Fiches abrogees (date fin depassee)
│   │   ├── 2.3.4 Double comptage interdit
│   │   ├── 2.3.5 Seuils P6 Coup de Pouce (P6_SEUILS)
│   │   │   └── Condition : remplacement energie fossile obligatoire
│   │   ├── 2.3.6 Validation complete (/validation/complete)
│   │   └── 2.3.7 Conformite PNCEE (pncee.py)
│   │       └── Registre national, controles, sanctions
│   │
│   └── 2.4 Deadlines reglementaires (/deadlines endpoint)
│       ├── 2.4.1 Dates fin fiches CEE
│       ├── 2.4.2 Alertes expiration proche
│       └── 2.4.3 Status par fiche (check_deadline)
│
├── 3. FIRST PRINCIPLE : CALCUL (combien ca vaut ?)
│   ├── 3.1 Moteur cumac (moteur_cee_master.py → compute_full)
│   │   ├── 3.1.1 Facteur FOST par fiche (47 BAT verifies)
│   │   │   └── Secteur factor (sectFactors) valide par fiche
│   │   ├── 3.1.2 Coefficient isolation existante (getIsolationCoefficient)
│   │   │   └── Epaisseur exacte en entree
│   │   ├── 3.1.3 Formule : Surface × FOST × Zone × Secteur × Coefficient
│   │   ├── 3.1.4 Unite : kWh cumac (MWhc pour affichage)
│   │   └── 3.1.5 Constante calibree BAT-EN-103 sante H1 : 6,24 MWhc/m²
│   │
│   ├── 3.2 Valorisation financiere (config.py)
│   │   ├── 3.2.1 Prix rachat cumac = VARIABLE CENTRALE
│   │   │   ├── Classique : configurable (defaut ~8 €/MWhc)
│   │   │   ├── Precarite : majore
│   │   │   └── Marche reference : 8,78 €/MWhc
│   │   ├── 3.2.2 Coup de Pouce P6 (p6Bonus ×3 a ×5)
│   │   │   └── Condition fossile obligatoire
│   │   ├── 3.2.3 Prime brute = cumac × prix rachat
│   │   ├── 3.2.4 Commission intermediaire (0% par defaut)
│   │   │   ├── % ajustable selon volume
│   │   │   └── Suggestion intelligente
│   │   ├── 3.2.5 Prime nette = prime brute × (1 - commission%)
│   │   ├── 3.2.6 TVA 20% (tertiaire)
│   │   └── 3.2.7 Constantes calibrees AHBFC
│   │       ├── Prix cumac oblige : 8,00 €/MWhc
│   │       ├── HT travaux : 41,60 €/m²
│   │       ├── TTC = Prime CEE : 49,92 €/m²
│   │       └── Commission Jimmy : 8,57 €/m² TTC (17,2% de la prime)
│   │
│   ├── 3.3 Couts travaux marche (couts_chantier.py)
│   │   ├── 3.3.1 246 entrees couts (min / moy / max)
│   │   ├── 3.3.2 Couverture = primeNette / coutTTC
│   │   ├── 3.3.3 Reste a charge = coutTTC - primeNette
│   │   └── 3.3.4 Seuil 0€ net a payer (modele AHBFC)
│   │
│   ├── 3.4 Cumul aides MPR (copro/bailleur/SCI uniquement)
│   │   ├── 3.4.1 MaPrimeRenov copropriete
│   │   ├── 3.4.2 MaPrimeRenov bailleur
│   │   ├── 3.4.3 JAMAIS de particulier (regle absolue)
│   │   └── 3.4.4 Cumul CEE + MPR = couverture totale
│   │
│   └── 3.5 Simulation multi-scenarios (config.py)
│       ├── 3.5.1 Scenario 1 : prix cumac bas
│       ├── 3.5.2 Scenario 2 : prix cumac moyen (marche)
│       ├── 3.5.3 Scenario 3 : prix cumac haut
│       ├── 3.5.4 Scenario 4 : Coup de Pouce P6
│       └── 3.5.5 Projection 15 ans ROI
│
├── 4. FIRST PRINCIPLE : INTELLIGENCE (que recommander ?)
│   ├── 4.1 Questions predictives (pipeline.py, qualification.py)
│   │   ├── 4.1.1 ~150 questions MICRO (specifiques metier, sans doublon)
│   │   ├── 4.1.2 ~24 questions UNIVERSAL (isolation, chauffage, VMC, GTB, LED, froid)
│   │   ├── 4.1.3 ~19 questions AFFINAGE (generees dynamiquement selon DPE)
│   │   ├── 4.1.4 Recalcul live apres reponses (/recalcul endpoint)
│   │   └── 4.1.5 Predictions ML variables (/predictions endpoint, predictions.py)
│   │
│   ├── 4.2 IA en consensus (5 moteurs)
│   │   ├── 4.2.1 Groq LLM (/ai/groq — SDK Python Groq)
│   │   ├── 4.2.2 Gemini LLM (/ai/gemini — proxy Google)
│   │   ├── 4.2.3 Moteur interne regle (cee_excellence_pro.py)
│   │   ├── 4.2.4 Auto-detect scoring (auto_detect.py)
│   │   ├── 4.2.5 Consensus : croisement des 5 resultats
│   │   └── 4.2.6 RAG contextuel (rag.py) — enrichissement par documents
│   │
│   ├── 4.3 Veille reglementaire (/regulatory, /regulatory/changelog)
│   │   ├── 4.3.1 Modifications reglementaires CEE en temps reel
│   │   ├── 4.3.2 Changelog versionne
│   │   └── 4.3.3 Alertes proactives
│   │
│   └── 4.4 Chat expert (chat.py)
│       └── 4.4.1 Interface conversationnelle expert CEE
│
├── 5. FIRST PRINCIPLE : NEGOCIATION (a qui vendre les cumac ?)
│   ├── 5.1 Comparateur acheteurs CEE (negociation.py)
│   │   ├── 5.1.1 9 acheteurs CEE modelises
│   │   │   └── Dont : Abokine (749843090), Economie d'Energie SAS (499388544)
│   │   ├── 5.1.2 Prix rachat par acheteur
│   │   ├── 5.1.3 Tolerance par acheteur
│   │   ├── 5.1.4 Score multi-criteres
│   │   ├── 5.1.5 Date MAJ prix + alerte 90 jours
│   │   └── 5.1.6 Scenario acheteur (calculer_scenario_acheteur)
│   │
│   ├── 5.2 Negociation parc (/negociation endpoint)
│   │   ├── 5.2.1 Volume kWhc total → pouvoir de negociation
│   │   ├── 5.2.2 GET /negociation/comparatif (query params)
│   │   └── 5.2.3 GET /acheteurs (liste complete)
│   │
│   └── 5.3 Gisement SIRAT (gisement_sirat.py)
│       ├── 5.3.1 Bareme SIRAT apporteur tiers : 8,57 €/m² (BAT-EN-103), 3,58 €/m² (BAT-EN-101)
│       ├── 5.3.2 Commission reelle Jimmy = 50% marge nette (ajustable)
│       │   └── Formule : Marge nette = Prime oblige - Cout reel installateur
│       └── 5.3.3 Template rapport gisement 10 pages (modele AHBFC)
│
├── 6. FIRST PRINCIPLE : MULTI-SITE (comment gerer un parc ?)
│   ├── 6.1 Strategie parc (multisite.py)
│   │   ├── 6.1.1 Optimisation batiment par batiment
│   │   ├── 6.1.2 Scoring DPE par site
│   │   ├── 6.1.3 Profils sites (type, zone, surface)
│   │   ├── 6.1.4 /multisite/strategie endpoint
│   │   └── 6.1.5 /multisite/optimiser endpoint
│   │
│   └── 6.2 Cas d'usage reference
│       ├── 6.2.1 ADAPEI : 79 sites
│       ├── 6.2.2 AHBFC : 15+ batiments (convention peintres)
│       │   ├── Magritte Cezanne (1 590 m², 9 922 MWhc, 79 372,80 € prime) ✅
│       │   ├── Renoir (1 900 m², 11 856 MWhc, 94 848 € prime) ✅
│       │   ├── Gauguin (1 600 m², 9 984 MWhc, 81 968,64 € prime) ✅
│       │   ├── Courbet Matisse (2 150 m², 13 416 MWhc, 107 328 € prime) ✅
│       │   ├── EAM Gray (2 159 m², 13 470 MWhc, 107 777,28 € prime) ✅
│       │   ├── Total engage : 9 449 m², 58 648 MWhc, 471 294,72 € ✅
│       │   └── Potentiel 11+ batiments restants : 300K-500K€ commissions 🟡
│       └── 6.2.3 Multi-etablissements par SIREN (modele G1T CRM)
│
├── 7. FIRST PRINCIPLE : CLOSING (comment conclure la vente ?)
│   ├── 7.1 Module closing (closing.py)
│   │   ├── 7.1.1 Pitch par type client
│   │   │   ├── PMI
│   │   │   ├── Grand Compte
│   │   │   ├── Bailleur
│   │   │   └── Collectivite
│   │   ├── 7.1.2 Strategie closing (/closing endpoint)
│   │   ├── 7.1.3 Gestion objections (methode ADERA)
│   │   │   ├── Accueillir
│   │   │   ├── Decouvrir
│   │   │   ├── Empathiser
│   │   │   ├── Repondre
│   │   │   └── Ancrer (RDV)
│   │   └── 7.1.4 Commissions simulees
│   │
│   ├── 7.2 Methodologie commerciale Jimmy (R0→R4)
│   │   ├── 7.2.1 R0 — Lead recu, 1er contact tel (<24h)
│   │   ├── 7.2.2 R1 — Decouverte tel/visio (PAS vendre)
│   │   │   ├── Methode SPIN (Situation→Probleme→Implication→Necessite)
│   │   │   ├── Regle 70/30 : ecouter 70%, parler 30%
│   │   │   ├── 10 regles dures (20-30 min max, jamais devis au R1, etc.)
│   │   │   └── Question d'or : "Qu'est-ce qui vous a donne envie de vous renseigner ?"
│   │   ├── 7.2.3 VT — Visite technique sur site
│   │   ├── 7.2.4 R2 — Presentation etude + closing (5 phases)
│   │   │   ├── Phase 1 : Ancrage emotionnel (reformulation R1)
│   │   │   ├── Phase 2 : Presentation technique (Production→Economies→Financement)
│   │   │   ├── Phase 3 : Contraste narratif (vie avec / sans)
│   │   │   ├── Phase 4 : Tension + silence 3 sec
│   │   │   └── Phase 5 : Cloture ("On valide qu'on passe a la VT")
│   │   ├── 7.2.5 R3 — Suivi post-signature montage dossier
│   │   └── 7.2.6 R4 — Installation + mise en service
│   │
│   ├── 7.3 Closing MAESTRO — 10 commandements
│   │   ├── 7.3.1 Valider la decision, pas obtenir signature
│   │   ├── 7.3.2 Closing commence 20 min avant la fin
│   │   ├── 7.3.3 Silence 2-4 sec apres le prix = arme principale
│   │   ├── 7.3.4 "On signe ?" INTERDIT → "On valide qu'on lance la preparation ?"
│   │   ├── 7.3.5 Detecter faux "oui"
│   │   ├── 7.3.6 Baisser l'energie en fin (stylo pose, voix calme)
│   │   ├── 7.3.7 Objection tardive = cadeau
│   │   ├── 7.3.8 Client ne doit pas avoir impression d'avoir dit "oui"
│   │   ├── 7.3.9 SMS d'ancrage immediat post-closing
│   │   └── 7.3.10 Illusion du choix ("8 kWc ou 9 ?")
│   │
│   ├── 7.4 Grammaire CEE vs PV
│   │   ├── 7.4.1 CEE 0€ reste a charge : evidence, no-brainer, opportunite limitee
│   │   │   └── "On lance le dossier, c'est finance a 100%"
│   │   ├── 7.4.2 CEE avec reste a charge : appliquer MAESTRO PV complet
│   │   └── 7.4.3 PV : MAESTRO complet, 5 phases R2, 10 commandements
│   │
│   └── 7.5 KPI 5S quotidien
│       ├── 7.5.1 Speed (<24h traitement)
│       ├── 7.5.2 Skill (taux VT/R1)
│       ├── 7.5.3 Strike (signature/R2)
│       ├── 7.5.4 Stamina (volume)
│       ├── 7.5.5 Spirit (posture)
│       └── 7.5.6 Cibles : R1/Leads >45%, VT/R1 >50%, chute <15%
│
├── 8. FIRST PRINCIPLE : DOCUMENTS (quels livrables produire ?)
│   ├── 8.1 Rapport 6 pages (oracle.html, jsPDF + autoTable)
│   │   ├── 8.1.1 Page 1 : Bilan General executif
│   │   │   ├── KPIs cles
│   │   │   ├── Tableau operations
│   │   │   ├── Cumul aides
│   │   │   └── Verdict
│   │   ├── 8.1.2 Page 2 : Detail par operation
│   │   │   ├── kWhc par fiche
│   │   │   ├── Avant / apres
│   │   │   └── Economies estimees
│   │   ├── 8.1.3 Page 3 : Equipements & Couts
│   │   │   ├── Renouvellement equipements
│   │   │   └── Sources officielles
│   │   ├── 8.1.4 Page 4 : Comparatif financier
│   │   │   ├── 3 scenarios compares
│   │   │   └── Projection 15 ans
│   │   ├── 8.1.5 Page 5 : Analyse IA & Recommandations
│   │   │   ├── Groq analysis
│   │   │   ├── Gemini analysis
│   │   │   └── Consensus
│   │   └── 8.1.6 Page 6 : Suivi dossier
│   │       ├── 8 statuts
│   │       ├── Dates + notes + progression
│   │       └── Export CSV
│   │
│   ├── 8.2 Documents CEE officiels (documents_client.py)
│   │   ├── 8.2.1 Mandat CEE
│   │   ├── 8.2.2 Attestation sur l'honneur
│   │   ├── 8.2.3 Cadre Contribution
│   │   └── 8.2.4 Convention multi-acteurs (template AHBFC/SIRAT)
│   │
│   ├── 8.3 Formats d'export
│   │   ├── 8.3.1 PDF multi-pages (jsPDF + autoTable)
│   │   ├── 8.3.2 CSV (UTF-8 BOM)
│   │   ├── 8.3.3 Excel (.xlsx si SheetJS, sinon CSV enrichi)
│   │   └── 8.3.4 Print A4 (page-break par section)
│   │
│   └── 8.4 Conformite signature PNCEE — 12 erreurs G1T (conformite.py)
│       ├── 8.4.1 Imprimer en COULEUR (N&B refuse)
│       ├── 8.4.2 PAS de recto-verso
│       ├── 8.4.3 Date MANUSCRITE stylo encre BLEUE
│       ├── 8.4.4 Annee COMPLETE (2026, jamais 26)
│       ├── 8.4.5 "Bon pour accord" manuscrit encre bleue
│       ├── 8.4.6 Signature manuscrite encre bleue
│       ├── 8.4.7 AUCUNE mention ajoutee ("au nom de", "P/O")
│       ├── 8.4.8 PAS de signature electronique (interdit pour CEE)
│       ├── 8.4.9 Meme ecriture, meme stylo (date + BPA + signature)
│       ├── 8.4.10 Tampon A COTE de la signature (pas dessus)
│       ├── 8.4.11 Tampon ORIGINAL complet lisible (scannes refuses)
│       └── 8.4.12 UN SEUL tampon, pas double, pas a l'envers
│
├── 9. FIRST PRINCIPLE : INTEGRATION (comment se connecter a l'ecosysteme ?)
│   ├── 9.1 Monday CRM (monday_sync.py)
│   │   ├── 9.1.1 Synchronisation bi-directionnelle 🟡
│   │   ├── 9.1.2 Pipeline PV Monday (cotations Dupas/Delquie/Linlaud)
│   │   └── 9.1.3 AHBFC = exception CEE dans Monday
│   │
│   ├── 9.2 Integrations externes (integrations.py)
│   │   ├── 9.2.1 GetAccept (signature electronique)
│   │   ├── 9.2.2 Sembly (notes RDV auto)
│   │   └── 9.2.3 Webhooks 🟡
│   │
│   ├── 9.3 Gestion dossiers (dossiers.py, dossier_ui.html)
│   │   ├── 9.3.1 8 statuts de suivi dossier
│   │   ├── 9.3.2 Interface UI dossier (dossier_ui.html)
│   │   └── 9.3.3 Workflow 6 etapes SIRAT
│   │       ├── Pre-visite
│   │       ├── Compte-rendu + offre
│   │       ├── Validation offre
│   │       ├── Visite technique avant travaux
│   │       ├── Planification + realisation (4-6 sem, 10 sem si >2000 m²)
│   │       └── DOE + Controle COFRAC + Validation
│   │
│   └── 9.4 Portail (portail.py)
│       └── 9.4.1 Interface portail client
│
├── 10. FIRST PRINCIPLE : SECURITE & INFRASTRUCTURE
│   ├── 10.1 Authentification (auth.py)
│   │   ├── 10.1.1 Decorator require_auth
│   │   └── 10.1.2 Routes auth (register_auth_routes)
│   │
│   ├── 10.2 Rate limiting (ratelimit.py)
│   │   └── 10.2.1 Protection endpoints
│   │
│   ├── 10.3 CORS (api.py)
│   │   └── 10.3.1 FIX V37 : Preflight OPTIONS handler propre
│   │
│   ├── 10.4 Logging (api.py)
│   │   ├── 10.4.1 FIX V37 : format texte ou JSON structure (LOG_FORMAT env)
│   │   ├── 10.4.2 Compatible Datadog/ELK/Loki
│   │   └── 10.4.3 FIX V37 : remplace les print eparpilles
│   │
│   ├── 10.5 Helper HTTP centralise (_fetch_json)
│   │   ├── 10.5.1 Retry 429 (rate limit externe)
│   │   ├── 10.5.2 SSL relaxe
│   │   └── 10.5.3 Cache LRU borne
│   │
│   └── 10.6 Documentation API (apidocs.py)
│       └── 10.6.1 27 endpoints documentes
│
├── 11. FIRST PRINCIPLE : FRONTEND (comment l'utilisateur interagit ?)
│   ├── 11.1 Oracle V37 PRO (oracle.html — 735 Ko, 10 675 lignes)
│   │   ├── 11.1.1 Step 1 : Identification (SIRET + enrichissement)
│   │   ├── 11.1.2 Step 2 : Gisements detectes (fiches eligibles)
│   │   ├── 11.1.3 Step 3 : Selection operations
│   │   ├── 11.1.4 Step 4 : Detail operations (calcul cumac + prime)
│   │   ├── 11.1.5 Step 5 : Rapport complet (6 pages)
│   │   └── 11.1.6 Flux pur : JAMAIS polluer Step 1→5 (regle nature_outil)
│   │
│   ├── 11.2 Outils annexes (compartimentes, jamais inlines)
│   │   ├── 11.2.1 Panneau negociation acheteurs
│   │   ├── 11.2.2 Modal documents CEE
│   │   ├── 11.2.3 Drawer comparateur
│   │   └── 11.2.4 Point d'acces unique "Outils" dans le header
│   │
│   ├── 11.3 UI ludique + proactive
│   │   ├── 11.3.1 Headlines proactives
│   │   ├── 11.3.2 Animations
│   │   ├── 11.3.3 Celebrations (aucune section ajoutee — densifier l'existant)
│   │   └── 11.3.4 Regle : simple, ludique, verifie
│   │
│   └── 11.4 Pages secondaires
│       ├── 11.4.1 index.html (landing)
│       └── 11.4.2 dossier_ui.html (suivi dossier)
│
├── 12. ACTEURS METIER
│   ├── 12.1 WCS (Wilner Consulting Services EOOD)
│   │   ├── Societe bulgare EIK 207143227
│   │   ├── Gerant : Jimmy Jackie Joseph WILNER
│   │   ├── Siege : 132 rue Mimi Balkanska Sofia 1540
│   │   ├── Preleve 15% sur CA Oxeo
│   │   └── TVA : autoliquidation art. 44 Directive 2006/112/CE
│   │
│   ├── 12.2 SIRAT (SARL, installateur RGE)
│   │   ├── SIRET 95117449900016
│   │   ├── Gerant : Fouhad KHEMICI
│   │   ├── Code APE 4329A
│   │   └── Assurance : MIC INSURANCE (decennale)
│   │
│   ├── 12.3 AHBFC (Association Hospitaliere Bourgogne Franche-Comte)
│   │   ├── SIREN 400 395 257
│   │   ├── Signataire : Frederic BONNET (Dir. Achats)
│   │   └── Referent terrain : Apolonia DURAND (06 81 88 73 26)
│   │
│   ├── 12.4 Abokine (delegataire CEE, ref 749843090)
│   ├── 12.5 Economie d'Energie SAS (SIREN 499388544, groupe Effy)
│   ├── 12.6 H2D (Habitat 2 Demain, entite Jimmy courtage)
│   ├── 12.7 OXEO (coeur 830 items, MC Consulting, PB, Krimo MME)
│   └── 12.8 Equipe commerciale
│       ├── Nicolas
│       ├── Anthony
│       └── Aurelien
│
├── 13. MODES OPERATOIRES — 13 CHEAT CODES
│   ├── 13.1 /godmode — Mode agressif, reponse maximale, pas de filtre prudent
│   ├── 13.2 /devil — Steelman l'opposition, argumenter contre Jimmy
│   ├── 13.3 /10x — Reecrire 10x plus tranchant, couper le gras
│   ├── 13.4 /pitch — Pitch 30 secondes investisseur/client, punchline
│   ├── 13.5 /ghost — Reponse "humaine", pas robotique
│   ├── 13.6 /compare — Analyse side-by-side avec tableau
│   ├── 13.7 /scout — Trouver les risques + angles morts
│   ├── 13.8 /artifacts — Construire des apps live en chat
│   ├── 13.9 /ooda — Resolution code probleme complexe (Observe-Orient-Decide-Act)
│   ├── 13.10 /critique — Ameliorer + trouver les defauts
│   ├── 13.11 /explainlikeim5 — Explication ultra claire enfant 5 ans
│   ├── 13.12 /brief — Plus court possible, zero remplissage (100 mots max)
│   └── 13.13 /teacher — Mode mentor / debat pedagogique
│   Regles : cumulables (/brief /devil), auto-declenchables si contexte justifie
│
├── 14. CONCURRENCE & POSITIONNEMENT
│   ├── 14.1 Effy Pro — BAR residentiel via artisans RGE (5000+), 100K foyers/an ✅ concurrent indirect
│   ├── 14.2 NR-PRO — Comparateur independant/courtier lead-gen, pas de profondeur ✅ concurrent indirect
│   ├── 14.3 France CEE — Mandataire artisans (1000+), jamais entreprises finales ✅ concurrent indirect
│   ├── 14.4 Renolib — SaaS gestion CEE artisans (199-399 €/mois) ✅ concurrent direct SaaS
│   └── 14.5 TROU DE MARCHE exploite par CEE Engine
│       ├── Aucun concurrent ne cible l'entreprise tertiaire/industrielle beneficiaire finale
│       ├── Zero commission (prime integrale au client)
│       ├── 224 fiches couvertes (vs ~50 chez les concurrents)
│       ├── 150+ questions expertes
│       └── Rapport 6 pages + enrichissement open data
│
├── 15. ROADMAP IA — 12 GISEMENTS PRIORITES
│   ├── 15.1 TIER 1 (ROI immediat)
│   │   ├── GIS-01 Agent Qualification Leads Auto (+15% taux contact, gain 2h/jour) 🟡
│   │   ├── GIS-02 Generateur Devis/Etude PV Auto (gain 7.5h/sem) ❌
│   │   ├── GIS-03 Assistant Closing R2 temps reel (+10% closing = +40K€ CA/an) ❌
│   │   ├── GIS-04 Rapport Hebdo Monday→Claude→PDF (gain 3h/sem) ❌
│   │   └── GIS-05 Scoring CEE AHBFC + Serres (19 879 € PAC + AGRI-TH-117) 🟡
│   │
│   ├── 15.2 TIER 2 (ROI moyen terme)
│   │   ├── GIS-06 Chatbot WhatsApp B2B (+20% leads qualifies 24/7) ❌
│   │   ├── GIS-07 Detecteur Anomalies Pipeline (fraude/negligence) ❌
│   │   ├── GIS-08 Formation Vendeur IA Simulateur R1/R2 (+15% skill) ❌
│   │   └── GIS-09 Prospection CEE Auto Serres+Industrie (x10 volume) ❌
│   │
│   └── 15.3 TIER 3 (vision)
│       ├── GIS-10 JARVIS CEO Dashboard (decision 30s vs 30min) ❌
│       ├── GIS-11 Multi-Agent JARVIS Orchestration (~1.5 ETP auto) ❌
│       └── GIS-12 API Courtage Energie + IA ❌
│
└── 16. REGLES DE DEVELOPPEMENT (meta)
    ├── 16.1 never_regress : JAMAIS ecraser un fichier par version plus simple, toujours fusionner
    ├── 16.2 nature_outil : audit predictif/proactif/intelligent, complements compartimentes
    ├── 16.3 ui_ludique : densifier l'existant, jamais ajouter de sections
    ├── 16.4 esprit_critique : contredire Jimmy quand direction mauvaise, avec arguments chiffres
    ├── 16.5 Outil PRO uniquement (pas de particulier)
    ├── 16.6 Prix rachat = variable centrale (tout en decoule)
    ├── 16.7 Commission = 0% par defaut (prime integrale au client)
    ├── 16.8 Aucune donnee inventee sans source
    └── 16.9 Maintenance trimestrielle : checklist 224 fiches + prix cumac + abrogations

├── 0. PROSPECTION (avant identification — scan open data)
│   ├── 0.1 Scan geographique (SIRET par rayon + NAF eligible) ❌ MANQUE
│   ├── 0.2 Scan sectoriel (tous EHPAD/supermarches/garages de France) ❌ MANQUE
│   ├── 0.3 Import batch Monday → audit auto ❌ MANQUE
│   ├── 0.4 Score lead predictif (0 contact, open data seul) ❌ MANQUE
│   └── 0.5 Alertes prospect chaud ❌ MANQUE
│
├── 17. POST-SIGNATURE (apres closing/documents)
│   ├── 17.1 Mandat cession CEE signe 🔜 À CONSTRUIRE
│   ├── 17.2 Planification travaux (dates, acces, coordination SIRAT) 🔜 À CONSTRUIRE
│   ├── 17.3 Suivi chantier (photos avant/pendant/apres, geolocalisees) 🔜 À CONSTRUIRE
│   ├── 17.4 Reception DOE 🔜 À CONSTRUIRE
│   ├── 17.5 Controle COFRAC (planif + rapport) 🔜 À CONSTRUIRE
│   ├── 17.6 Constitution dossier PNCEE complet (AH + devis + facture + DOE + COFRAC + photos + checklist 12 erreurs) 🔜 À CONSTRUIRE
│   ├── 17.7 Depot EMMY 🔜 À CONSTRUIRE
│   └── 17.8 Suivi paiement (oblige → installateur → apporteur, J+45 post-COFRAC, relance auto) 🔜 À CONSTRUIRE
│
├── 18. ANALYTICS
│   ├── 18.1 Dashboard CA pipeline temps reel ❌ MANQUE
│   ├── 18.2 Forecast commission 30/60/90j ❌ MANQUE
│   ├── 18.3 Taux conversion R0→R4 ❌ MANQUE
│   ├── 18.4 Performance vendeur ❌ MANQUE
│   └── 18.5 ROI par fiche ❌ MANQUE
│
├── 19. FIDELISATION
│   ├── 19.1 CEE → PV → IRVE → maintenance ❌ MANQUE
│   ├── 19.2 Reversion CEE/m² ❌ MANQUE
│   └── 19.3 Cycle de vie batiment ❌ MANQUE
│
├── 20. FORMATION
│   ├── 20.1 Simulateur R1/R2 ❌ MANQUE
│   ├── 20.2 QCM Maestro ❌ MANQUE
│   └── 20.3 Coaching IA post-RDV ❌ MANQUE

MODULES PYTHON (37 fichiers) :
├── api.py              — 27 endpoints, routeur principal
├── apidocs.py          — documentation API auto
├── auth.py             — authentification + require_auth
├── auto_detect.py      — SIRET→NAF→gisements, scoring, pack optimal
├── bdnb_client.py      — enrichissement BDNB/BAN/DPE
├── cee_excellence_pro.py — orchestrateur + validateurs juridiques
├── chat.py             — interface conversationnelle expert
├── closing.py          — strategie vente, pitch, objections
├── config.py           — prix cumac, commissions, TVA, seuils P6
├── conformite.py       — conformite PNCEE + 12 erreurs G1T
├── couts_chantier.py   — 246 couts travaux marche
├── documents_client.py — mandat, attestation, cadre contribution
├── dossiers.py         — gestion dossiers + statuts
├── extract_fiches.py   — extraction fiches catalogue
├── gisement_sirat.py   — gisement SIRAT + baremes + commissions
├── integrations.py     — connexions externes
├── mapping_naf_fiches.py — 243+ codes APE → fiches eligibles
├── merge_oracle.py     — fusion oracle
├── monday_sync.py      — sync Monday CRM
├── moteur_cee_master.py — calcul cumac, eligibilite, P6, zones
├── multisite.py        — optimisation parc multi-sites
├── negociation.py      — 9 acheteurs, prix, scoring
├── oracle.html         — frontend 10 675 lignes
├── parse_atee.py       — parsing fiches ATEE
├── parse_pdf.py        — extraction PDF
├── pipeline.py         — enrichissement audit, generation questions
├── pncee.py            — registre PNCEE
├── portail.py          — portail client
├── predictions.py      — predictions ML
├── qualification.py    — qualification leads
├── rag.py              — RAG contextuel
├── ratelimit.py        — rate limiting
├── scrape_fiches.py    — scraping fiches CEE
├── top_fiches_secteur.py — top fiches par secteur
└── validate_fiches.py  — validation catalogue fiches
```
