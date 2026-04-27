# Actions résiduelles — uniquement par toi

Tout ce qui pouvait être fait côté machine est fait. Voici la liste exacte de ce qui demande **tes credentials** ou **un redémarrage de session**.

## A — Sécu prod (P0, le plus critique)

### A.1 — Rotater les 5 clés LLM + token Monday
Les clés visibles dans `.env` sont **brûlées** (passées dans pipeline d'audit). Action :
```bash
# 1) Révoquer + régénérer chez chaque provider :
#    Anthropic   → https://console.anthropic.com/settings/keys
#    OpenAI      → https://platform.openai.com/api-keys
#    Groq        → https://console.groq.com/keys
#    Google AI   → https://aistudio.google.com/app/apikey
#    Moonshot    → https://platform.moonshot.cn/console/api-keys
#    Monday      → https://wcspro.monday.com/admin/integrations/api

# 2) Pousser les nouvelles vers Fly :
fly secrets set \
  ANTHROPIC_API_KEY='sk-ant-...' OPENAI_API_KEY='sk-...' \
  GROQ_API_KEY='gsk_...' GEMINI_API_KEY='AIza...' \
  MOONSHOT_API_KEY='sk-...' MONDAY_API_TOKEN='eyJ...' \
  --app cee-engine-v37
```

### A.2 — Régénérer un CEE_JWT_SECRET fort (le code refusera de booter avec un secret faible en prod)
```bash
fly secrets set \
  CEE_JWT_SECRET="$(openssl rand -hex 32)" \
  CEE_DOSSIERS_SECRET="$(openssl rand -hex 32)" \
  CEE_CONFORMITE_SECRET="$(openssl rand -hex 32)" \
  --app cee-engine-v37
```

### A.3 — Vider le `.env` local des secrets
```bash
> .env
echo "# Secrets désormais dans 'fly secrets list --app cee-engine-v37'" > .env
```

## B — Persistance Fly volume

```bash
# 1× : créer le volume (sans ça, AHBFC saute au prochain redeploy)
fly volumes create cee_data --region cdg --size 3 --app cee-engine-v37
```

`fly.toml` est déjà patché avec le mount `/data`. Au 1er boot post-volume, les données locales `dossiers_data/`, `conformite_data/`, `post_signature_data/` migreront automatiquement vers `/data/` (testé en local : OK).

## C — Webhook Monday (signature HMAC)

Audit sécu : webhook actuellement non vérifié.
```bash
WH_SECRET=$(openssl rand -hex 32)
fly secrets set MONDAY_WEBHOOK_SECRET="$WH_SECRET" --app cee-engine-v37
# Configurer le même secret côté Monday dans la conf du webhook
```
Patch côté `monday_sync.py:267-285` à faire en V37.2.

## D — Déploiement
```bash
cd /Users/azert/CEE_ENGINE
fly deploy --app cee-engine-v37
fly logs --app cee-engine-v37 | grep -E "SÉCU|JWT_SECRET"
# Doit montrer "OK", pas "WARNING"
```

## E — Activer les plugins Claude Code
Tous activés dans `~/.claude/settings.json`. Pour qu'ils se chargent réellement :
```
1. Quitte la session Claude Code actuelle
2. Relance : `claude` (ou ouvre nouveau terminal)
3. Au démarrage tu verras :
   - claude-mem auto-installer Bun (1ère fois) puis créer ~/.claude-mem/
   - mempalace MCP server connecté (palace déjà initialisé)
   - skills superpowers + planning-with-files + code-review + frontend-design disponibles
```

## F — Pre-commit gitleaks (détecte secrets accidentels)
```bash
brew install gitleaks
cat > .git/hooks/pre-commit <<'EOF'
#!/bin/sh
gitleaks protect --staged --no-banner || exit 1
EOF
chmod +x .git/hooks/pre-commit
```

## Vérification finale

```bash
fly secrets list --app cee-engine-v37
# Doit lister : CEE_JWT_SECRET, CEE_DOSSIERS_SECRET, CEE_CONFORMITE_SECRET,
# ANTHROPIC_API_KEY, OPENAI_API_KEY, GROQ_API_KEY, GEMINI_API_KEY,
# MOONSHOT_API_KEY, MONDAY_API_TOKEN, MONDAY_WEBHOOK_SECRET

curl -i https://cee-engine-v37.fly.dev/ai/groq -H "Origin: https://malicious.example" -X POST
# Doit retourner 403 (origin guard actif)

curl -i https://cee-engine-v37.fly.dev/auth/status
# Doit retourner {"auth_enabled":true,...} (JWT secret valide)
```

## Ordre conseillé
1. A.1 + A.2 + A.3 (~15 min)
2. B (~2 min)
3. D deploy (~5 min)
4. C (~5 min, peut attendre V37.2)
5. E (~30s, juste relance Claude Code)
6. F (~2 min)

**Total ~30 min de toi.** Sans ces actions, le code défensif est prêt mais les clés exposées restent compromises.
