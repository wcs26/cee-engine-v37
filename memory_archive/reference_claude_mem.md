---
name: claude_mem
description: Plugin claude-mem (thedotmack) installé 2026-04-27 pour capture auto des sessions Claude Code. Coexiste avec memory/ existant sans conflit.
type: reference
originSessionId: 77f696d7-e327-4ff8-9534-f54fec80bc4b
---
`claude-mem` v12.4.7 installé le **2026-04-27** sur la machine de Jimmy.

## Ce que c'est
Plugin Claude Code qui auto-capture chaque session de code, compresse via agent-sdk Claude, et ré-injecte le contexte au démarrage de la session suivante (observations typées : bugfix, discovery, decision).

## Où c'est stocké
- Plugin : `~/.claude/plugins/marketplaces/thedotmack/`
- Data plugin : `~/.claude-mem/` (créé à la 1re session active après install — peut ne pas exister à l'instant t)
- Settings hook : `~/.claude/settings.json` → `enabledPlugins["claude-mem@thedotmack"] = true`
- Marketplace entry : `~/.claude/settings.json` → `extraKnownMarketplaces.thedotmack`

## Coexistence avec mémoire existante
Le système `memory/` ici (auto-loadé par le harness via le bloc `# auto memory` du system prompt) **n'est pas touché** par claude-mem. Les 19 fichiers de cette mémoire restent la source de vérité humaine (feedback, project, user, reference). claude-mem capture en plus la trace technique des sessions.

→ **Ne jamais supprimer ou migrer cette mémoire vers claude-mem sans validation explicite Jimmy** (cf. `feedback_never_regress`).

## Dépendances runtime
- **Bun** : requis pour le worker (start/stop/status/search) — auto-installé par les hooks au 1er lancement de session active. Si absent au moment de cette note, normal.
- **uv** : requis pour vector search — idem auto-installé.
- Worker port par défaut : **37701** (HTTP API + UI web `http://localhost:37701`).

## Commandes utiles
- `npx --yes claude-mem@latest status` — état du worker
- `npx --yes claude-mem@latest start` — démarrer le worker (besoin de Bun)
- `npx --yes claude-mem@latest search "query"` — chercher dans l'historique
- `/mem-search` — slash command in-Claude-Code (post-install)
- `npx --yes claude-mem@latest uninstall` — désinstaller proprement (fermer toutes les sessions Claude Code avant, sinon les hooks recréent le dossier)

## Backups préventifs effectués
- `~/.claude/backups/memory-cee-engine-2026-04-27.tar.gz` (26K — 19 fichiers mémoire)
- `~/.claude/backups/settings-pre-claudemem-2026-04-27.json`
- `~/.claude/backups/settings.local-pre-claudemem-2026-04-27.json`

## Si problème
Rollback :
```
npx --yes claude-mem@latest uninstall
cp ~/.claude/backups/settings-pre-claudemem-2026-04-27.json ~/.claude/settings.json
rm -rf ~/.claude-mem/
```
