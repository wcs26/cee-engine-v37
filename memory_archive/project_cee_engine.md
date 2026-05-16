---
name: project_cee_engine
description: Architecture CEE Engine V36 PRO - Oracle fusionné avec moteur Python, état complet des modules
type: project
originSessionId: 2d739e73-9717-4b97-9190-077c3d3670b3
---
**Architecture actuelle (2026-04-11) — V36 PRO:**

Backend Python (Flask, port 5001):
- `api.py` — 27 endpoints (health, expert, oracle, negociation, closing, multisite, regulatory, dpe+audit, siret, batiment, proxy, ai/groq, ai/gemini, regles/75pct, etc.)
- `moteur_cee_master.py` — calcul cumac, eligibilité, compute_full, règles juridiques P6
- `auto_detect.py` — SIRET→NAF→gisements, scoring business, pack optimal, PAC_remplacement logique V36
- `negociation.py` — 9 acheteurs CEE, prix rachat, tolérance, score multi-critères, date MAJ prix avec alerte 90j
- `multisite.py` — optimisation parc bâtiment par bâtiment, scoring DPE, profils sites
- `closing.py` — stratégie vente, pitch par type client (PMI/Grand Compte/Bailleur/Collectivité), commissions, objections
- `cee_excellence_pro.py` — orchestrateur + validateurs juridiques (non-cumul, DPE 2021+, abrogées, double comptage)
- `bdnb_client.py` — enrichissement BDNB/BAN/DPE
- `config.py` — prix cumac classique/précarité, commissions, TVA, seuils P6
- `pipeline.py` — enrichissement audit, génération questions

Frontend (Oracle V36 PRO, servi par Flask):
- `oracle.html` — 13 188 lignes (mesuré 2026-04-30), interface complète Step 1→5 + 234 fiches inline JS (lignes 3200-11000)

**Moteur de calcul (getFullCalc):**
- Zone (H1/H2/H3/DOM) + énergie (combustible/électricité via z_elec)
- Facteur FOST par fiche (47 fiches BAT avec sectFactors vérifié)
- Coefficient isolation existante (getIsolationCoefficient) avec épaisseur exacte
- Coup de Pouce P6 (p6Bonus ×3-5, condition fossile)
- Coûts travaux marché (246 entrées min/moy/max)
- Commission 0% par défaut (% intermédiaire variable)
- Couverture = primeNette / coûtTTC
- Cumul aides MPR copro/bailleur

**Questions prédictives:**
- 16 profils micro-activités (5 AGRI + 3 IND + 4 BAT + 2 BAR + 1 TRA + 1 RES)
- ~150 questions MICRO (spécifiques métier, sans doublon avec UNIVERSAL)
- ~24 questions UNIVERSAL (isolation, chauffage, VMC, GTB, LED, froid, etc.)
- ~19 questions AFFINAGE (générées dynamiquement selon DPE)

**Enrichissement open data (3 sources ADEME + BDNB + INSEE):**
- DPE logement (14.5M), DPE tertiaire (516K), Audits énergétiques (50K+)
- Validation GPS distance (Haversine) + score confiance (high/medium/low)
- Surface cross-validation (alerte si écart >30%)
- Liens téléchargement DPE/audit (observatoire ADEME)

**Rapport 6 pages:**
1. Bilan Général exécutif (KPIs, tableau ops, cumul aides, verdict)
2. Détail par opération (kWhc, avant/après, économies)
3. Équipements & Coûts (renouvellement, sources officielles)
4. Comparatif financier (3 scénarios + projection 15 ans)
5. Analyse IA & Recommandations (Groq + Gemini + consensus)
6. Suivi dossier (8 statuts, dates, notes, progression, export CSV)

**Export:**
- PDF multi-pages (jsPDF + autoTable)
- CSV (UTF-8 BOM)
- Excel (.xlsx si SheetJS, sinon CSV enrichi)
- Documents CEE (Mandat + Attestation sur l'honneur + Cadre Contribution)
- Print A4 (page-break par section)

**Configuration financière:**
- Prix de rachat délégataire (modifiable, protégé contre écrasement)
- % Commission intermédiaire (0% défaut, suggestion intelligente selon volume)
- Simulation impact prix (4 scénarios comparés)
- Liens cartes ciblés (satellite 100m, Street View, cadastre z=19, PLU)

**Données (audit 2026-04-30):**
- **234 fiches** catalogue dans fiches.json (6 secteurs : AGRI 29, AGR 1 typo, BAR 51, BAT 60, IND 40, RES 10, TRA 43). 222 actives, 12 inactives. 15 fiches avec cumac=0 sur toutes zones (HIGH risk simul prime à 0€).
- 246 coûts travaux marché
- 47 fiches BAT avec FOST vérifié
- 9 acheteurs CEE modélisés
- 32+ profils Intelligence Pro (APE→équipements probables)

**Why:** Jimmy construit l'outil CEE pro le plus complet du marché pour ne perdre aucun deal.
**How to apply:** Toujours fusionner les améliorations, jamais régresser. L'outil est PRO uniquement (pas de particulier). MPR = copro/bailleur/SCI seulement. Prix rachat = variable clé centrale. Commission = 0% par défaut.
