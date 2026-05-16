---
name: Reviewer checklist trimestriel — maintenance catalogue CEE
description: Liste des vérifications que Jimmy (ou un CEE Reviewer humain) doit faire chaque trimestre pour garantir l'exactitude des 224 fiches et éviter les erreurs juridiques.
type: reference
originSessionId: 2df11f34-7c9e-449e-84cf-ffec1837e5ed
---
## Pourquoi un reviewer trimestriel ?

224 fiches CEE = 224 pièces réglementaires qui peuvent être modifiées par :
- Arrêtés du ministère de la Transition Écologique (publications DGEC)
- Notes techniques ATEE
- Décisions PNCEE (Pôle National CEE)
- Évolutions coefficients FOST (Forfait Opération Standard Travaux)

Une fiche devenue obsolète = risque juridique (CEE rejeté, amende L. 222-10 code énergie).

## Checklist à exécuter chaque trimestre (< 2h de travail)

### 1. Veille arrêtés DGEC (15 min)
- [ ] Consulter [Légifrance](https://www.legifrance.gouv.fr/) recherche "CEE" ou "certificats économies énergie"
- [ ] Vérifier [ministère écologie](https://www.ecologie.gouv.fr/politiques-publiques/dispositif-certificats-deconomies-denergie)
- [ ] Identifier les arrêtés publiés depuis le dernier review

### 2. Mise à jour deadlines.json (15 min)
- [ ] Ajouter les nouvelles abrogations avec leur date d'effet
- [ ] Marquer dans fiches.json les fiches `actif: false` pour celles abrogées
- [ ] Vérifier automatiquement avec `curl http://localhost:5001/regulatory`

### 3. Validation coefficients FOST (30 min)
- [ ] Pour chaque fiche BAT avec sectFactors modifié par arrêté → mettre à jour fiches.json
- [ ] Pour les nouvelles fiches → ajouter entrée dans mapping_naf_fiches.py

### 4. Prix cumac EMMY (5 min)
- [ ] Aller sur [emmy.fr](https://www.emmy.fr/) vérifier prix du mois
- [ ] Mettre à jour `PRIX_CUMAC` dans config.py si écart > 10%
- [ ] Relancer `/regulatory/intelligence` pour voir que la tendance est cohérente

### 5. Tests non-régression (10 min)
- [ ] `python3 -m pytest tests/` → 47/47 doivent passer
- [ ] `curl http://localhost:5001/health` → status "ok", 234+ fiches
- [ ] Test live SIRET connu (ex : 44306184100047 Google) → prime dans fourchette attendue

### 6. Scan abrogations émergentes (15 min)
- [ ] `curl http://localhost:5001/regulatory` → `alertes` avec urgence=haute
- [ ] Croiser avec Légifrance → confirmer les abrogations annoncées

### 7. Audit opérationnel (15 min)
- [ ] `curl http://localhost:5001/status` → toutes sources UP (ou SLOW acceptable)
- [ ] Vérifier logs `/tmp/cee_api.log` → aucune erreur récurrente
- [ ] `/health` → cache SIRET entries raisonnable (<300)

### 8. Back-up données (5 min)
- [ ] Copier `fiches.json`, `deadlines.json`, `cout_travaux.json`, `config.py` dans un backup daté
- [ ] Commit git si repo (sinon dossier `backups/YYYY-MM-DD/`)

## Cadence

- **Chaque 15 du mois** : scan rapide (1, 2, 4) — 35 min
- **Chaque trimestre** (15/01, 15/04, 15/07, 15/10) : review complet — 2h
- **Après publication d'un arrêté majeur** : review ciblé — 1h

## Signaux d'alerte qui imposent un review immédiat

- `/regulatory` renvoie une alerte `urgence: haute` type `abrogation`
- Un client remonte un écart entre la prime estimée et la prime effectivement versée
- Un obligé refuse un dossier → la fiche utilisée est peut-être obsolète
- Les tests pytest commencent à échouer sans modif code

## Qui fait ce review ?

- **Jimmy** (connaissance métier CEE) — idéal
- **Consultant CEE externe** trimestriel — si Jimmy n'a pas le temps
- **Automatisation partielle via Gemini/Claude** — parser les PDFs DGEC et pré-remplir un draft de diff, validation humaine indispensable

## Historique

Chaque review produit un fichier `review_YYYY-MM-DD.md` daté avec :
- Arrêtés consultés (URLs Légifrance)
- Fiches modifiées (avant/après)
- Coefficients ajustés
- Tests validés
