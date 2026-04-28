# CEE Engine V37.3 PRO

**Audit CEE prédictif, proactif, intelligent** pour PME tertiaires, industries, multi-sites et copropriétés.

> **V37.3 (2026-04-28)** — Tunnel commercial unifié `lead → audit → R1 → R2 → signature → post_signature` avec hooks auto (PNCEE score, prime exacte, cross-sell PV, push Monday), boot guards sécu (JWT secret, CORS allowlist, origin guard `/ai/*`, webhook Monday HMAC), sync bidirectionnelle Monday (URL token), persistance Fly volume `/data/`, dashboard objectif V38 (`/analytics/sales-velocity`), 5 IA orchestrées. **192 tests verts**. Détails déploiement : `JIMMY_TODO.md` + `SECURITE_RUNBOOK.md` + `scripts/smoke.sh`.

---

## 🎯 Positionnement

| Axe | CEE Engine | Concurrents (Effy, Renolib, NR-PRO, France CEE) |
|---|---|---|
| **Cible** | PME tertiaire/industrielle directe | Artisans RGE ou leads particuliers |
| **Commission** | **0 % par défaut** (prime intégrale au client) | 10-20 % sur la prime |
| **Fiches** | 234 (6 secteurs : AGRI, BAR, BAT, IND, RES, TRA) | 100-200 |
| **Sources open data** | 5 (Cadastre IGN + BD TOPO + DPE + Audit ADEME + Sirene) | 0-2 |
| **Intelligence IA** | Penta-IA régulée + Conseil 5×3 (15 agents) | Aucune |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  oracle.html  (V37 PRO — parcours audit Step 1→5)           │
│  ├─ Hero headline : SIRET → prime + gisements + proactif    │
│  ├─ Drawer 🧰 Outils : CRM, comparateur acheteurs, PDFs     │
│  └─ Panneau IA : Penta simple · Conseil 5×3 (15 agents)     │
└─────────────────────────────────────────────────────────────┘
                          │ fetch()
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  api.py  (Flask, port 5001 — 34 endpoints)                  │
│  ├─ /analyse, /expert, /recalcul, /predictions              │
│  ├─ /multisite/{strategie,optimiser}, /closing              │
│  ├─ /regulatory/{,intelligence,changelog}                   │
│  ├─ /acheteurs, /negociation, /validation/complete          │
│  ├─ /siret/search, /etablissements/<siren>, /cadastre       │
│  ├─ /batiment, /dpe, /proxy                                 │
│  └─ /ai/{groq,gemini,claude,kimi,openai,gpt} + keys/status  │
└─────────────────────────────────────────────────────────────┘
          │           │           │           │
          ▼           ▼           ▼           ▼
  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
  │ moteur │  │ open   │  │ intel  │  │ 5 IA   │
  │ cee    │  │ data   │  │ 5      │  │ Penta/ │
  │ master │  │ API    │  │ lenses │  │ Conseil│
  │ 234 fi.│  │ gouv   │  │        │  │ 5×3    │
  └────────┘  └────────┘  └────────┘  └────────┘
```

---

## 🚀 Installation

### Prérequis
- Python 3.11+
- Node.js 18+ (uniquement pour `node --check` en dev)

### Dépendances runtime
```bash
pip install flask requests groq
```

### Dépendances dev (tests)
```bash
pip install -r requirements-dev.txt
```

---

## 🔐 Configuration des 5 IA (V37 SEC)

**Règle V37 SEC** : **AUCUNE clé API en dur**. Deux sources possibles :

### Source 1 (recommandée) — env serveur
```bash
export GROQ_API_KEY=gsk_...
export GEMINI_API_KEY=AIza...
export ANTHROPIC_API_KEY=sk-ant-...
export MOONSHOT_API_KEY=sk-...
export OPENAI_API_KEY=sk-...
```
Clés jamais exposées au navigateur. Utilisées uniquement côté Python.

### Source 2 (fallback) — localStorage navigateur
Via l'UI, bouton **🔑 Clés API** dans le panneau Multi-IA. Utile pour tests ponctuels.

### Vérification
```bash
curl http://localhost:5001/ai/keys/status
# → {"groq": true, "gemini": false, "claude": true, ...}
```

---

## ▶️ Lancement

### Mode développement (logs lisibles, reloader)
```bash
python3 api.py
# → http://localhost:5001
```

### Mode production (logs JSON pour agrégateur type Datadog/Loki/ELK)
```bash
LOG_FORMAT=json python3 api.py
```

Exemple de log structuré :
```json
{"ts":"2026-04-15T06:31:50","level":"INFO","logger":"cee_api","msg":"http GET /health 200 28ms","http_method":"GET","http_path":"/health","http_status":200,"latency_ms":28}
```

### Mode WSGI (gunicorn, uwsgi pour prod)
```bash
pip install gunicorn
LOG_FORMAT=json gunicorn -w 4 -b 0.0.0.0:5001 api:app
```

---

## 🧪 Tests

```bash
# Tous les tests (181 tests, ~75s)
CEE_ENV=dev CEE_JWT_SECRET="$(openssl rand -hex 32)" \
CEE_CONFORMITE_SECRET="$(openssl rand -hex 32)" \
python3 -m pytest tests/ -v

# Smoke test live post-deploy
./scripts/smoke.sh https://cee-engine-v37.fly.dev
```

**Suite V37.1 (181 tests)** :
- `tests/test_api.py` — 99 tests endpoints + intégration
- `tests/test_auth.py` — 15 tests crypto, JWT roundtrip + détection altération + validation force secret
- `tests/test_pncee.py` — 11 tests scoring dossier (GO/STOP/blockers)
- `tests/test_conformite.py` — 16 tests structure 46 règles + executer_controles + horodatage HMAC
- `tests/test_snapshot_ahbfc.py` — 9 tests verrouillant le dossier AHBFC vivant (BAT-EN-103 cumac, FOST, calcul prime témoin)
- `tests/test_negociation.py` — 11 tests comparateur acheteurs (refus secteur/mixité, COFRAC, précarité)
- `tests/test_pv_cotation.py` — 8 tests cotation PV (zones, modes, orientation, proportionnalité)
- `tests/test_tunnel.py` — 12 tests orchestrateur commercial + KPI sales velocity

---

## 📋 Règles métier critiques (user_jimmy)

### Zéro invention
**Jamais de pré-remplissage sans source vérifiée.**
- Surface : BD TOPO > saisie user > estimation profil (marquée comme telle) > `null`
- Prime : ne s'affiche que si une surface fiable existe
- DPE : pas de déduction si confiance `low`

### Commission 0 % par défaut
`COMMISSION_RATE` env = 0 (prime intégrale au client). Modifiable par cas.

### Outil PRO uniquement
- Cible : entreprises (tertiaire, industrie, agri, copro, bailleurs)
- **MPR** : uniquement copros, bailleurs, SCI (pas particuliers)

### Conformité juridique P6
- Dispositif 2026-2030, décret n°2025-1048
- Art. 441-7 Code pénal (fausse déclaration)
- RGE obligatoire, contrôle COFRAC
- Règle des 75 % + tolérance mixte tertiaire/résidentiel

---

## 🧠 Intelligence — 5 lentilles + Conseil 5×3

### Penta-IA simple (3 s, 5 agents)
Chaque IA a un **rôle distinct** :
- ⚡ **GROQ** — tactique temps réel
- 💎 **GEMINI** — documents & multimodal
- 🧠 **CLAUDE** — conformité réglementaire
- 🌙 **KIMI** — vérification calculs
- 🟢 **CHATGPT** — synthèse commerciale

### Conseil approfondi 5×3 (8 s, 15 agents)
Chaque IA en 3 passes :
1. **DRAFT** — première analyse spécialisée
2. **CRITIC** — round-robin pentagone, voit 2 voisins
3. **VERIFIER** — confirme/infirme avec données moteur réelles

Synthèse pondérée par `cohérence × fiabilité`. Escalade automatique du verdict :
- ≥ 2 contradictions → **PRUDENCE** forcé
- ≥ 3 contradictions → **STOP** forcé

### 5 lentilles réglementaires (`/regulatory/intelligence`)
- **Optimiste** : signaux positifs + actions ROI
- **Pessimiste** : risques + protections
- **Opportuniste** : fenêtres temporelles + couplages
- **Prédictif** : projections P6 + évolution prix
- **Proactif** : actions immédiates + calendrier 90 j

---

## 🛰️ Sources open data (toutes API gouv/ADEME gratuites)

| Source | Endpoint | Usage |
|---|---|---|
| `recherche-entreprises.api.gouv.fr` | `/siret/search`, `/etablissements/<siren>` | Identification, filtrage actifs |
| `public.opendatasoft.com` (Sirene) | `/siret/search` fallback | SIRET fermés/non-diffusibles |
| `apicarto.ign.fr` | `/cadastre` | Parcelle cadastrale, contenance |
| `data.geopf.fr` (BD TOPO V3) | `/batiment` | Surface sol, hauteur, matériaux, année |
| `data.ademe.fr` (3 datasets) | `/dpe` | DPE logement + tertiaire + audits |
| `api-adresse.data.gouv.fr` | `/proxy` | Géocodage BAN |

### 📜 Licences & conformité des données

**CEE Engine utilise les données en mode `lookup` uniquement — aucune redistribution, aucun stockage durable.**

| Source | Licence | Respecté ? |
|---|---|:-:|
| recherche-entreprises.api.gouv.fr | [Licence Ouverte 2.0](https://etalab.gouv.fr/licence-ouverte-open-licence) | ✅ libre |
| IGN Cadastre + BD TOPO | [Licence Ouverte 2.0](https://www.ign.fr/institut/licences) | ✅ libre |
| ADEME DPE/Audit | [Licence Ouverte 2.0](https://data.ademe.fr/) | ✅ libre |
| OpenDataSoft Sirene | INSEE CC-BY 4.0 (lookup) | ✅ non redistribué |
| BAN (adresses) | [Licence Ouverte 2.0](https://adresse.data.gouv.fr/) | ✅ libre |

**Rule V37 SEC** : toutes les données externes sont **cachées 24h max** (cache SIRET LRU 500 entrées) et servent uniquement à l'enrichissement du diagnostic en cours. Aucune base de données persistante ne stocke les données brutes open data.

---

## 📂 Structure projet

```
CEE_ENGINE/
├── api.py                    # Flask app, 34 endpoints
├── oracle.html               # Frontend V37 PRO
├── config.py                 # PRIX_CUMAC, COMMISSION_RATE=0, PORT
├── moteur_cee_master.py      # Calcul cumac, zones, coefficients
├── auto_detect.py            # SIRET → NAF → gisements → pack
├── negociation.py            # 9 acheteurs CEE modélisés
├── multisite.py              # Optimisation parc
├── closing.py                # Pitch, objections, commissions
├── cee_excellence_pro.py     # Validateurs juridiques P6
├── pipeline.py               # Enrichissement audit
├── predictions.py            # Estimations ML
├── bdnb_client.py            # BDNB + BAN + DPE
├── fiches.json               # 234 fiches CEE (catalogue)
├── cout_travaux.json         # 246 coûts marché min/moy/max
├── deadlines.json            # Dates abrogations
├── activity_factors.json     # Facteurs d'activité par secteur
├── mapping_naf_fiches.py     # APE → fiches pertinentes
├── tests/test_api.py         # 47 tests pytest
├── pytest.ini                # Config tests
├── requirements-dev.txt      # pytest, pytest-timeout
└── README.md                 # ce fichier
```

---

## 🔄 Release notes V37

### V37-FUSED (2026-04-15)
- ✅ **Penta-IA** : GROQ + GEMINI + CLAUDE + KIMI + CHATGPT, chacune avec rôle unique
- ✅ **Conseil 5×3** : 15 agents en 3 passes, round-robin critic, verifier tool-augmented
- ✅ **V37 SEC** : clés API env only (plus aucune clé en dur)
- ✅ **Tests pytest** : 47 tests, 34 endpoints couverts
- ✅ **Logs structurés JSON** : production-ready via `LOG_FORMAT=json`
- ✅ **/health enrichi** : modules, IA, cache, uptime
- ✅ **/regulatory/intelligence** : 5 lentilles contextuelles
- ✅ **/cadastre** : parcelle IGN
- ✅ **/batiment** : BD TOPO V3 avec surface au sol exacte, matériaux, année
- ✅ **Hero headline** : big number animé + sources + top 3 gisements
- ✅ **Escalade verdict** : ≥2 contradictions → PRUDENCE forcé
- ✅ **Commission 0 %** par défaut (corrigé de 10 %)

### Règles métier héritées des sessions précédentes
- `feedback_never_regress` : jamais écraser par version plus simple
- `feedback_nature_outil` : parcours audit pur, outils annexes compartimentés
- `feedback_ui_ludique` : densifier, pas complexifier
- `feedback_esprit_critique` : contredire Jimmy si direction mauvaise

---

## 🐛 Debug

### L'API ne répond pas
```bash
lsof -ti:5001 | xargs kill -9
python3 api.py
```

### Tests échouent
```bash
# Vérifier que l'API n'est PAS déjà lancée (Flask test_client l'instancie lui-même)
pkill -9 -f "python3 api.py"
python3 -m pytest tests/ -v
```

### Voir les logs d'une requête spécifique
```bash
LOG_FORMAT=json python3 api.py 2>&1 | grep '"http_path":"/analyse"'
```

---

## 🤝 Contribution

L'outil est conçu pour Jimmy (commercial CEE PRO) mais le code est structuré pour être maintenu par une équipe. Avant tout commit :

```bash
python3 -m pytest tests/          # 47 tests doivent passer
node --check /tmp/oracle_check.js # JS valide
```

---

## 📞 Support

- Endpoint `/health` pour monitoring
- Logs JSON agrégeables (Datadog, Loki, ELK)
- 47 tests couvrant 34 endpoints

**Licence** : usage interne. Ne pas redistribuer les clés API dur-codées historiquement présentes (toutes retirées V37 SEC).
