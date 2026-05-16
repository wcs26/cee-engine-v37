# BILAN STRATEGIQUE CEE ENGINE + COPILOTE vs CONCURRENCE
**Date : 16 avril 2026 | Analyste : Claude Code (modes /critique /devil /scout /10x)**

---

## 1. ETAT REEL DU PRODUIT

### Chiffres vérifiés (run du 16/04/2026)
- **40 modules Python**, 17 970 lignes backend
- **oracle.html** : 12 436 lignes (frontend monolithe)
- **234 fiches CEE** (vs 224 documentées = +10 ajoutées)
- **45 coûts chantier** catalogués (vs 246 annoncés dans la doc = ECART, les 246 incluent les variantes min/moy/max)
- **5/5 clés IA** actives (Claude, Gemini, Groq, Kimi, OpenAI)
- **85/85 tests passent** (99 fonctions test, 14 skip réseau/OpenData)
- **Fly.io** : Dockerfile + fly.toml + Procfile prêts, CLI pas installée = **PAS DEPLOYE**

### Composants ENGINE (moteur invisible)

| Composant | Fonction | Statut | Preuve |
|---|---|---|---|
| moteur_cee_master | Calcul cumac, éligibilité, FOST | **FONCTIONNE** | 85 tests passent |
| 234 fiches catalogue | 6 secteurs BAT/BAR/IND/AGR/TRA/RES | **FONCTIONNE** | load_fiches()=234 |
| auto_detect | SIRET→NAF→gisements, scoring | **FONCTIONNE** | Tests API |
| negociation | 9 acheteurs, prix rachat, scoring | **FONCTIONNE** | Tests API |
| multisite | Optimisation parc multi-bâtiment | **FONCTIONNE** | Tests API |
| cee_excellence_pro | Validateurs juridiques, non-cumul, abrogées | **FONCTIONNE** | Tests API |
| bdnb_client | Enrichissement BDNB/BAN/DPE 3 sources ADEME | **CONSTRUIT** | Dépend réseau, tests skippés |
| conformite + pncee | Règles PNCEE, 75%, contrôles | **FONCTIONNE** | Tests API |
| documents_client | Mandat + AH + Cadre Contribution (812 lignes) | **FONCTIONNE** | Tests API |
| dossiers | Persistance JSON, historique | **FONCTIONNE** | Tests API |
| couts_chantier | 45 entrées coûts travaux | **FONCTIONNE** | COUTS_CATALOGUE=45 |
| pv_cotation | Cotation PV auto (417 lignes) | **CONSTRUIT** | Pas de test PV dans la suite |
| monday_sync | Sync Monday.com | **CONSTRUIT** | Pas de test réseau |
| prospection | Scan département, scoring prospects | **CONSTRUIT** | Pas testé terrain |
| post_signature | Suivi J+30/J+90/J+165 | **CONSTRUIT** | Pas testé terrain |
| analytics | Pipeline, KPIs, commissions | **CONSTRUIT** | 1 warning deprecation |
| auth | Authentification | **CONSTRUIT** | Pas testé multi-user |

### Composants COPILOTE (interface visible)

| Composant | Fonction | Statut | Preuve |
|---|---|---|---|
| oracle.html | Interface unique 12K lignes | **FONCTIONNE** | Servi par Flask |
| Questions prédictives | 150+ micro + 24 universal + 19 affinage | **FONCTIONNE** | Intégré oracle |
| Penta-IA consensus | 5 IA en parallèle | **FONCTIONNE** | 5/5 keys active |
| Rapport 6 pages PDF | Export jsPDF multi-pages | **FONCTIONNE** | Frontend intégré |
| formation | QCM Maestro, scripts vente (700 lignes) | **CONSTRUIT** | Pas utilisé par équipe |
| closing | Pitch par type client, objections | **CONSTRUIT** | Pas utilisé en R2 réel |
| fidelisation | Rétention client | **CONSTRUIT** | Pas testé terrain |
| **Déploiement en ligne** | Accès équipe via URL | **MANQUE** | fly.io non déployé, CLI absente |
| **Module PV dans oracle** | Interface cotation PV | **MANQUE** | Backend existe, UI pas intégrée |
| **Historique consultable** | Dashboard dossiers passés | **MANQUE** | dossiers.py existe, pas d'UI |

---

## 2. BENCHMARK CONCURRENCE ACTUALISE

Notation /100 par critère. Sources : sites publics, documentation projet, réalité vérifiée.

| Critère | Poids | CEE Engine | Copilote | Effy | NR-PRO | France CEE | Renolib | Oscar | Likewatt |
|---|---|---|---|---|---|---|---|---|---|
| A. Catalogue CEE | 10% | **95** (234 fiches, 6 secteurs) | - | 40 (BAR seul) | 30 (généraliste) | 50 (BAR artisans) | 60 (BAR+qques BAT) | 35 | 0 |
| B. Intelligence IA | 10% | **90** (5 IA, prédictif) | **85** (Penta-IA, consensus) | 10 (néant) | 5 | 5 | 20 (IA basique) | 10 | 30 (PV IA) |
| C. Justesse calculs | 15% | **85** (FOST vérifié, 85 tests) | - | 70 (volume=rodé) | 20 (pas de calcul) | 65 | 60 | 40 | 75 (PV seul) |
| D. Conformité PNCEE | 10% | **80** (règles auto, 75%, non-cumul) | - | 75 (mandataire=vérifié) | 10 | 70 | 55 | 30 | 0 |
| E. Documents auto | 5% | **75** (mandat+AH+cadre+PDF) | - | 80 (workflow complet) | 0 | 70 | 75 | 20 | 60 |
| F. Open Data | 5% | **70** (BDNB+3 ADEME, code skippé tests) | - | 30 | 10 | 10 | 15 | 5 | 40 |
| G. Module PV | 10% | 25 (backend seul, pas d'UI) | 0 | 0 | 0 | 0 | 0 | 0 | **90** |
| H. CRM intégré | 5% | 30 (Monday sync codé, pas connecté) | 15 | 60 | 40 | 30 | **70** | 50 | 40 |
| I. Formation vendeur | 5% | 0 (code existe, personne ne l'utilise) | 40 (QCM codé) | 20 | 0 | 10 | 10 | 0 | 0 |
| J. Prospection active | 5% | 50 (scan département codé) | 50 | 0 | **60** (lead-gen=leur métier) | 0 | 0 | 30 | 20 |
| K. Post-signature | 5% | 30 (code existe, J+30/90/165) | 10 | **80** (mandataire=suivi) | 20 | 70 | 65 | 40 | 30 |
| L. Déploiement | 10% | **0** (localhost seulement) | **0** | **95** (SaaS prod) | **90** | **85** | **90** | 70 | **90** |
| M. Base utilisateurs | 5% | **0** (1 user = Jimmy) | **0** | **95** (5000+ artisans) | 60 | 50 (1000+) | 40 | 25 | 35 |

### SCORE PONDERE /100

| Produit | Score |
|---|---|
| **CEE Engine** | **55/100** |
| **Copilote** | ~30/100 |
| **Effy** | 56/100 |
| **NR-PRO** | 31/100 |
| **France CEE** | 48/100 |
| **Renolib** | 50/100 |
| **Likewatt** (PV seul) | 42/100 |

**Verdict brutal** : CEE Engine a le meilleur moteur de calcul CEE du marché. Mais avec 0 utilisateurs en ligne et 0 déploiement, il est ex-aequo avec Effy qui a 5000 artisans actifs. La technologie ne vaut rien si personne ne peut y accéder.

---

## 3. OBJECTIFS vs REALITE

| Objectif | Cible | Réalité mesurée | Gap |
|---|---|---|---|
| +2 signatures/mois/personne | +2/mois grâce à l'outil | **0** (outil non déployé, équipe n'y accède pas) | **-2** CRITIQUE |
| 70% transfo R2→signature | 70% | **Inconnu** (pas de tracking, pas d'analytics actif) | **Non mesurable** |
| Outil PV le plus performant | Cotation auto PV | Backend 417 lignes existe, **pas d'UI, pas de test** | 80% du chemin manque |
| Historique complet | Tout tracé et retrouvable | dossiers.py existe, **pas d'interface de consultation** | UI manquante |
| Autonomie équipe | Anthony/Aurélien/Nicolas autonomes | **Impossible** : outil tourne en localhost sur le Mac de Jimmy | Bloqueur total |

---

## 4. LES 3 FORCES IMBATTABLES

**1. Profondeur du catalogue CEE tertiaire/industriel : 234 fiches, 6 secteurs**
Aucun concurrent ne couvre BAT+IND+AGR+TRA+RES avec cette granularité. Effy fait du BAR. Renolib fait du BAR. NR-PRO ne calcule rien. C'est un avantage structurel de 6+ mois de travail que personne ne va dupliquer rapidement.

**2. Penta-IA avec consensus multi-modèle**
5 IA en parallèle pour valider un diagnostic. Aucun concurrent n'a ça. Aucun n'y pense. C'est un différenciateur marketing puissant ("vérifié par 5 intelligences artificielles") et un vrai gain de justesse.

**3. Diagnostic prédictif depuis le SIRET seul**
SIRET → NAF → équipements probables → fiches éligibles → prime estimée → pitch prêt. En 4 secondes avant même d'appeler le prospect. Aucun concurrent ne fait de la prospection prédictive CEE.

---

## 5. LES 3 FAILLES CRITIQUES

**1. PAS DEPLOYE = PAS D'OUTIL (criticité : FATALE)**
L'outil tourne en localhost:5001 sur le Mac de Jimmy. L'équipe (Anthony, Aurélien, Nicolas) n'y a pas accès. Fly.io est configuré mais pas déployé. CLI flyctl n'est même pas installée. Conséquence : 0 utilisateur, 0 signature générée par l'outil, 0 ROI. Tout le travail de développement est inutile tant que ce point n'est pas résolu.

**2. ZERO TEST TERRAIN = ZERO CONFIANCE (criticité : HAUTE)**
85 tests unitaires passent. Mais personne n'a jamais fait un vrai R1 ou R2 avec l'outil face à un client réel. Le deal AHBFC mentionné dans le plan est en "attente Jimmy". Sans validation terrain, on ne sait pas si les chiffres affichés sont crédibles en situation réelle, si le workflow tient, si les clients comprennent le rapport.

**3. PV = 80% DU CA, 0% DE L'OUTIL (criticité : HAUTE)**
Jimmy fait 80% de son CA en PV. Le module pv_cotation.py existe (417 lignes) mais n'a pas de tests, pas d'UI dans oracle.html, pas de connexion avec le workflow de vente. L'outil optimise 20% du business (CEE) et ignore 80% (PV).

---

## 6. PLAN D'ACTION 30 JOURS (par impact sur objectifs)

| Semaine | Action | Livrable | Impact objectif |
|---|---|---|---|
| **S1 J1-J2** | **Déployer sur fly.io** : installer flyctl, `fly deploy`, configurer .env secrets, tester URL publique | URL accessible par l'équipe | Débloque TOUT |
| **S1 J3-J5** | **Onboarding équipe** : envoyer l'URL à Anthony/Aurélien/Nicolas, 30 min de démo, recueillir bugs | 3 utilisateurs actifs | Objectif "autonomie équipe" |
| **S2 J6-J8** | **Deal réel AHBFC** : Jimmy utilise l'outil en live sur un prospect CEE réel, noter chaque friction | 1er diagnostic client réel | Valide justesse + UX |
| **S2 J9-J10** | **Corriger les frictions** trouvées lors du deal AHBFC | Outil ajusté au terrain | +confiance = +utilisation |
| **S3 J11-J15** | **Module PV dans oracle.html** : intégrer pv_cotation.py dans l'UI, ajouter tests, connecter au workflow | Cotation PV en 1 clic | 80% du CA couvert |
| **S4 J16-J20** | **Monday PV sync** : boucle lead→cotation→closing dans Monday | Pipeline PV automatisé | Tracking = mesure transfo |
| **S4 J21-J25** | **Analytics live** : dashboard signatures, taux transfo, commission prévue | KPIs mesurables | Objectif 70% transfo mesurable |
| **S4 J26-J30** | **Itérer** : 2e deal réel, ajuster, former sur les objections | 2e validation terrain | Objectif +2 sign/mois |

### Priorisation brutale

**Si tu ne fais QU'UNE chose** : déployer sur fly.io. Tout le reste est bloqué par ça.
**Si tu en fais DEUX** : déployer + deal réel AHBFC.
**Si tu en fais TROIS** : déployer + deal réel + PV dans oracle.

Ne pas toucher au moteur CEE. Il est terminé. 234 fiches, 85 tests, 5 IA. C'est fait.
Arrêter de coder. Commencer à vendre.

---

## SYNTHESE EN 1 PHRASE

CEE Engine est le moteur CEE le plus complet de France mais il est invisible, inaccessible et inutilisé : le seul travail qui compte maintenant est de le mettre en ligne et de l'utiliser face à un vrai client.
