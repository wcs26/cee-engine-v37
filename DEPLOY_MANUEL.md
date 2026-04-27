# Deploy manuel V37.1 — copy-paste exact (~30 min)

Tout ce qui suit est **obligatoirement par toi**. Ouvre un terminal dans `/Users/azert/CEE_ENGINE` et suis dans l'ordre. Copie-colle les blocs entiers.

```bash
cd /Users/azert/CEE_ENGINE
```

---

## ÉTAPE 1 — Rotation des clés providers (~10 min, web UIs)

Les 6 secrets visibles dans `.env` sont **brûlés**. Régénère-les avant tout deploy.

| Provider | URL | Action |
|---|---|---|
| Anthropic | https://console.anthropic.com/settings/keys | Révoque l'ancienne, crée une nouvelle, copie `sk-ant-…` |
| OpenAI | https://platform.openai.com/api-keys | Idem `sk-…` |
| Groq | https://console.groq.com/keys | Idem `gsk_…` |
| Google AI (Gemini) | https://aistudio.google.com/app/apikey | Idem `AIza…` |
| Moonshot (Kimi) | https://platform.moonshot.cn/console/api-keys | Idem `sk-…` |
| Monday | https://wcspro.monday.com/admin/integrations/api | Regenerate token (`eyJ…`) |

Garde les 6 valeurs au chaud (un fichier `~/secrets-temp.txt` par exemple), tu vas les coller à l'étape 3.

---

## ÉTAPE 2 — Vider `.env` (les anciennes clés ne doivent plus traîner)

```bash
cat > .env <<'EOF'
# V37.1 — Tous les secrets sont désormais dans Fly secrets.
# Voir : fly secrets list --app cee-engine-v37
# Ne JAMAIS recoller des clés ici.
EOF
```

---

## ÉTAPE 3 — Login Fly + push des secrets

```bash
# Login (ouvre un browser, callback OAuth)
fly auth login

# Génère les 3 secrets internes en une seule commande (pas besoin de les retenir)
fly secrets set \
  CEE_JWT_SECRET="$(openssl rand -hex 32)" \
  CEE_DOSSIERS_SECRET="$(openssl rand -hex 32)" \
  CEE_CONFORMITE_SECRET="$(openssl rand -hex 32)" \
  MONDAY_WEBHOOK_SECRET="$(openssl rand -hex 32)" \
  --app cee-engine-v37
```

Puis colle les 6 clés providers (remplace les valeurs par celles de l'étape 1) :

```bash
fly secrets set \
  ANTHROPIC_API_KEY='sk-ant-XXXXXXX' \
  OPENAI_API_KEY='sk-XXXXXXX' \
  GROQ_API_KEY='gsk_XXXXXXX' \
  GEMINI_API_KEY='AIzaXXXXXXX' \
  MOONSHOT_API_KEY='sk-XXXXXXX' \
  MONDAY_API_TOKEN='eyJXXXXXXX' \
  --app cee-engine-v37
```

Vérification :

```bash
fly secrets list --app cee-engine-v37
# Doit lister 10 secrets (4 internes + 6 providers)
```

---

## ÉTAPE 4 — Créer le volume Fly (1× pour la vie de l'app)

```bash
fly volumes create cee_data --region cdg --size 3 --app cee-engine-v37
# Confirme avec "y" si demandé
```

Vérifie :

```bash
fly volumes list --app cee-engine-v37
# Doit lister cee_data, 3 GB, région cdg
```

---

## ÉTAPE 5 — Déploiement

```bash
fly deploy --app cee-engine-v37
```

Pendant le déploiement, surveille les logs sécu :

```bash
fly logs --app cee-engine-v37 | grep -E "SÉCU|JWT_SECRET|started"
```

Tu dois voir :
- ✅ `cee_api starting`
- ✅ aucune ligne `[SÉCU WARNING]` (= JWT secret fort accepté)
- ❌ si `[SÉCU] CEE_JWT_SECRET invalide en prod` → secret pas pris, refais étape 3

---

## ÉTAPE 6 — Smoke test live

```bash
./scripts/smoke.sh https://cee-engine-v37.fly.dev
```

Lecture du résultat :
- `✓ N / N checks PASS` → vert, prod opérationnelle
- `✗ X FAIL` → liste des problèmes + commandes investigation incluses

Si webhook Monday FAIL : colle `MONDAY_WEBHOOK_SECRET` dans la config webhook côté Monday admin (https://wcspro.monday.com/admin/integrations/api → Edit webhook → Authorization).

---

## ÉTAPE 7 — Activer les 5 plugins Claude Code (~30s)

```bash
# 1. Quitte la session Claude Code actuelle (Ctrl+D ou /exit)
# 2. Relance dans le projet
cd /Users/azert/CEE_ENGINE
claude
```

Au démarrage de la nouvelle session :
- claude-mem auto-installe Bun (1ère fois, ~30s) puis crée `~/.claude-mem/`
- mempalace MCP server connecté (palace déjà initialisé)
- Skills `superpowers`, `planning-with-files`, `code-review`, `frontend-design` chargées

Vérifie dans la session :
```
/plugin list
# Doit montrer 5 plugins activés
```

---

## ÉTAPE 8 (optionnelle) — Push git si tu veux versionner

```bash
git log --oneline -5
# Doit montrer 4 commits V37.1 wave 1-4

# Si tout est OK, push (état partagé donc je ne le fais jamais sans demande explicite)
git push origin main
```

---

## ÉTAPE 9 (recommandée) — Pre-commit gitleaks pour ne plus jamais committer un secret

```bash
brew install gitleaks
cat > .git/hooks/pre-commit <<'EOF'
#!/bin/sh
gitleaks protect --staged --no-banner || exit 1
EOF
chmod +x .git/hooks/pre-commit

# Test
echo "test_key=sk-ant-fake12345" > /tmp/test_leak.txt
git add /tmp/test_leak.txt
# Doit refuser le commit
```

---

## Si ça plante quelque part

| Symptôme | Action |
|---|---|
| `fly: command not found` | `brew install flyctl` |
| `fly auth login` redirige indéfiniment | Tape `Ctrl+C` puis `fly auth signup` ou login depuis https://fly.io/dashboard |
| `[SÉCU] CEE_JWT_SECRET invalide` au boot | Re-set le secret avec `openssl rand -hex 32` (jamais "dev"/"test"/"change") |
| Volume `cee_data` already exists | Bon signe, skip étape 4 |
| Smoke test FAIL sur `/auth/status` | App down. `fly status --app cee-engine-v37` puis `fly logs` |
| AHBFC manquant après deploy | Volume mal mounté. Vérifie `fly.toml` `[[mounts]]` + `fly volumes list` |

---

## Rollback total (si nécessaire)

```bash
# Revert le déploiement
fly releases --app cee-engine-v37
fly releases rollback <version_id> --app cee-engine-v37

# Restaurer settings.json local
cp ~/.claude/backups/settings-pre-claudemem-2026-04-27.json ~/.claude/settings.json

# Désinstaller les plugins
npx --yes claude-mem@latest uninstall
```

Tous les backups V37.1 dans `~/.claude/backups/` (7 fichiers).

---

## Récap : ce qui sera vivant après l'étape 6

| Item | URL / commande | Effet |
|---|---|---|
| Sécu JWT fort | boot fail si faible | Refuse les secrets compromis |
| CORS allowlist | `Origin: malicious` → 403 | Plus d'abus public des proxies LLM |
| Webhook Monday HMAC | signature obligatoire | Anti-spoof |
| Volume Fly persistant | `/data/` | AHBFC + dossiers survivent aux redeploys |
| Tunnel commercial | `POST /tunnel` + dashboard | Mesure objectif V38 +2 sig/mois/personne |
| Widget Pipeline | drawer 🧰 → 📊 Pipeline | Vue commerciale live |
| Smoke test | `./scripts/smoke.sh` | Filet sécu post-deploy à relancer à chaque release |

**Total durée hors UI : ~25-30 minutes.** Étape 7 + 9 optionnelles selon ton appétit.
