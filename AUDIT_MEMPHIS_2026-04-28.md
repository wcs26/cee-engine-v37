# Audit Memphis 4 — checklist matin du 2026-04-28

## URL principal
https://cee-engine-v37.fly.dev

## Tunnel pré-créé (placeholder)
- **tunnel_id** : `T-8ac5d6a8d36e`
- **raison_sociale** : Memphis 4 (audit programmé 2026-04-28 matin)
- **stage** : audit
- **siret placeholder** : `PIPE-MEMPHIS-04` (à remplacer par le vrai dès saisie)

## Étapes audit

### 1. À l'arrivée du SIRET réel Memphis 4 (3 voies, choisis la plus rapide)

**Voie A — via oracle.html (recommandée)**
1. Ouvre https://cee-engine-v37.fly.dev
2. Saisis le SIRET réel → Lancer l'audit
3. Le système crée AUTOMATIQUEMENT un nouveau tunnel via le hook `/analyse`
4. Tu peux ensuite supprimer le placeholder `T-8ac5d6a8d36e` (cf. section nettoyage)

**Voie B — mettre à jour le placeholder existant**
```bash
curl -X PATCH https://cee-engine-v37.fly.dev/tunnel/T-8ac5d6a8d36e/update \
  -H "Content-Type: application/json" \
  -d '{"siret":"<14 CHIFFRES VRAI SIRET>","raison_sociale":"<vrai nom>"}'
```

**Voie C — direct via /tunnel POST**
```bash
curl -X POST https://cee-engine-v37.fly.dev/tunnel \
  -H "Content-Type: application/json" \
  -d '{"siret":"<SIRET>","vendor":"Jimmy","raison_sociale":"Memphis 4","source":"audit_terrain_2026_04_28"}'
```

### 2. Pendant l'audit avec le client

Pour chaque advance de stage, utilise :
```bash
curl -X POST https://cee-engine-v37.fly.dev/tunnel/<TID>/advance \
  -H "Content-Type: application/json" \
  -d '{"target_stage":"audit","data":{"fiches":["BAT-EN-103",...],"naf":"<NAF>","surface":<m²>,"departement":"<2 chiffres>","secteur":"BAT","energie":"electricite","rge_installateur":true,"date_engagement":"2026-04-28"}}'
```

À chaque advance vers `audit` → **score PNCEE auto** + **prime exacte calculée** + **cross-sell PV si tertiaire >100 m²** + **push Monday auto**.

### 3. Vue commerciale complète d'un dossier
```bash
curl https://cee-engine-v37.fly.dev/tunnel/<TID>/full
```
Retourne : tunnel + predict_next + alertes + sources tracées + stages restants.

### 4. Tableau de bord équipe
```bash
curl https://cee-engine-v37.fly.dev/analytics/sales-velocity?objectif=2
```

### 5. Alertes pipeline du matin (à scanner avant l'audit)
```bash
curl https://cee-engine-v37.fly.dev/tunnel/alerts
```
État au 2026-04-27 : **8 alertes** (6 critique + 2 haute) — à traiter en priorité avant Memphis :
- MECA Peaucellier 71.5j lead → Qualif G1T sous 24h
- MAS Village de la Forge 66.3j r2 → Closing Maestro
- KS Coaching, Bouafles, DSInnovations, Yves Rezeau → idem

### 6. Côté Monday board CEE
- Board : https://wcspro.monday.com/boards/5094841405
- Les 10 dossiers du pipeline ont leur item Monday
- Sync bidirectionnelle armée : déplacer l'item entre groups → tunnel auto-MAJ

## Si problème pendant l'audit

```bash
# 1. Logs prod en direct
fly logs --app cee-engine-v37 | tail -50

# 2. État VM
fly status --app cee-engine-v37

# 3. Healthcheck
curl https://cee-engine-v37.fly.dev/health

# 4. Smoke test 11 checks
./scripts/smoke.sh https://cee-engine-v37.fly.dev
```

## Cleanup placeholder Memphis 4 (après audit avec vrai SIRET)

```bash
# Si voie A utilisée, supprimer le placeholder qui n'a plus d'utilité
fly ssh console --app cee-engine-v37 --command "rm -f /data/tunnel_data/T-8ac5d6a8d36e.json"
```

## Critères "audit réussi"

- ✅ Tunnel créé avec le vrai SIRET Memphis
- ✅ Score PNCEE = GO (verdict, score >= 85, 0 blockers)
- ✅ Prime brute calculée (en €) avec source `auto_detect.moteur_expert_v2`
- ✅ Top 3 fiches éligibles affichées avec pitch
- ✅ Cross-sell PV proposé si tertiaire >100 m²
- ✅ Item Monday créé sur le board CEE
- ✅ Devis générable via `/documents/pack`
- ✅ Stage avancé jusqu'à `r2` ou `signature` selon le résultat de l'audit terrain

## Récap pré-audit (ce qui est en place)

- Backend live cee-engine-v37.fly.dev — V37.3.6
- 11 tunnels (10 pipeline + Memphis 4 placeholder)
- 192 tests verts CI
- Sécu : JWT 64 chars, CORS allowlist, origin guard /ai/*, headers défensifs
- Persistance : volume Fly /data/ avec dossiers/conformite/post_signature/tunnel
- Sync Monday bidirectionnelle armée
- 5 IA configurées (Anthropic + OpenAI + Groq + Gemini + Moonshot)
- 222/234 fiches CEE actives chargées
