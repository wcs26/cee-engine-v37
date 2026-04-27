# Runbook sécurité V37.1 — actions Jimmy

3 critiques sécu identifiées par l'audit du 2026-04-25. Code-side patché ce 2026-04-27. Reste les actions provider-side qui demandent ton login.

## P0.1 — Rotater les 5 clés LLM + token Monday (compromis dans `.env` historique)

Les clés visibles dans `.env` doivent être considérées **brûlées** (passées dans le pipeline d'audit). Rotation = obligatoire.

```bash
# 1. Révoquer + régénérer chaque clé chez le provider
#    Anthropic   → https://console.anthropic.com/settings/keys
#    OpenAI      → https://platform.openai.com/api-keys
#    Groq        → https://console.groq.com/keys
#    Google AI   → https://aistudio.google.com/app/apikey  (Gemini)
#    Moonshot    → https://platform.moonshot.cn/console/api-keys  (Kimi)
#    Monday      → https://wcspro.monday.com/admin/integrations/api  (regenerate token)

# 2. Pousser les nouvelles clés sur Fly (jamais dans .env)
fly secrets set \
  ANTHROPIC_API_KEY='sk-ant-...' \
  OPENAI_API_KEY='sk-...' \
  GROQ_API_KEY='gsk_...' \
  GEMINI_API_KEY='AIza...' \
  MOONSHOT_API_KEY='sk-...' \
  MONDAY_API_TOKEN='eyJ...' \
  --app cee-engine-v37

# 3. Vider .env local des secrets et committer un .env vide / template
echo "# Secrets désormais dans 'fly secrets list --app cee-engine-v37'" > .env
echo "# Voir SECURITE_RUNBOOK.md pour rotation" >> .env
git add .env && git commit -m "sécu: rotation clés, secrets via fly secrets"

# 4. Installer gitleaks en pre-commit (1 fois)
brew install gitleaks
echo '#!/bin/sh
gitleaks protect --staged --no-banner || exit 1' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## P0.2 — Régénérer un CEE_JWT_SECRET fort

```bash
# Générer un secret de 64 chars hex (256 bits) — refuse "dev"/"test"/"change"
NEW_SECRET=$(openssl rand -hex 32)
fly secrets set CEE_JWT_SECRET="$NEW_SECRET" --app cee-engine-v37
fly secrets set CEE_DOSSIERS_SECRET="$(openssl rand -hex 32)" --app cee-engine-v37

# Le code vérifie maintenant la force au boot (auth.py, dossiers.py).
# Si CEE_ENV=prod (ce qui est le cas dans fly.toml V37.1), le boot échoue avec un secret faible.
```

## P0.3 — Webhook Monday : ajouter une signature HMAC

```bash
# Générer + déclarer un secret webhook Monday
WH_SECRET=$(openssl rand -hex 32)
fly secrets set MONDAY_WEBHOOK_SECRET="$WH_SECRET" --app cee-engine-v37

# Configurer le secret côté Monday.com lors de la création du webhook
# (Authorization header : ce $WH_SECRET).
# Côté code, monday_sync.py:267-285 doit vérifier hmac.compare_digest(header, MONDAY_WEBHOOK_SECRET)
# → patch à faire dans une prochaine itération.
```

## P0.4 — Provisionner le volume Fly pour la persistance

```bash
# 1x — création du volume (sinon AHBFC, dossiers, conformité, post-signature s'effacent au redeploy)
fly volumes create cee_data --region cdg --size 3 --app cee-engine-v37

# fly.toml V37.1 mounte déjà ce volume sur /data, dossiers.py + conformite.py + post_signature.py
# sont patchés pour utiliser CEE_DATA_DIR=/data avec migration auto au 1er boot.
```

## Vérification post-rotation

```bash
fly secrets list --app cee-engine-v37
# Doit lister : CEE_JWT_SECRET, CEE_DOSSIERS_SECRET, ANTHROPIC_API_KEY, OPENAI_API_KEY,
# GROQ_API_KEY, GEMINI_API_KEY, MOONSHOT_API_KEY, MONDAY_API_TOKEN, MONDAY_WEBHOOK_SECRET, CEE_DATA_DIR

fly deploy --app cee-engine-v37
fly logs --app cee-engine-v37 | grep -E "SÉCU|JWT_SECRET"
# Doit montrer "OK" pas "WARNING"

curl -i https://cee-engine-v37.fly.dev/ai/groq -H "Origin: https://malicious.example" -X POST
# Doit retourner 403 Origin non autorisée
```

## Backups disponibles si rollback nécessaire

- `~/.claude/backups/settings-pre-claudemem-2026-04-27.json`
- `~/.claude/backups/memory-cee-engine-2026-04-27.tar.gz`

Pour le code Python : `git diff` des changements V37.1 + `git stash` si urgence.
