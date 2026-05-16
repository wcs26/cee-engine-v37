---
name: mempalace
description: MemPalace v3.3.3 installé 2026-04-27 dans venv Python 3.11 dédié, MCP server wired dans ~/.claude.json. Mémoire sémantique locale ChromaDB, complémentaire de claude-mem.
type: reference
originSessionId: 77f696d7-e327-4ff8-9534-f54fec80bc4b
---
`MemPalace` v3.3.3 installé le **2026-04-27** sur la machine de Jimmy, MCP server wired.

## Pourquoi un venv 3.11 dédié ?
Python 3.13 (système) + Python 3.14 (brew) sur la machine. **Aucun ne supporte chromadb / pulsar-client / onnxruntime** (pas de wheels disponibles). Solution : `brew install python@3.11` puis venv isolé pour mempalace seulement, sans toucher au Python système.

## Localisation
- Binary : `/Users/azert/.mempalace-venv/bin/mempalace`
- Venv Python 3.11 : `/Users/azert/.mempalace-venv/`
- Data palace par défaut (créé à `init`) : `/Users/azert/.mempalace/palace/`
- MCP wiring : `~/.claude.json` → `mcpServers.mempalace = {command, args:["mcp"]}`

## Différence avec claude-mem
- **claude-mem** (déjà installé v12.4.7) : capture auto session-by-session, observations typées (bugfix, discovery, decision), via plugin Claude Code natif
- **mempalace** : organisation hiérarchique (wings → halls → rooms), 19 outils MCP, recherche sémantique ChromaDB, méthode des loci. Init manuel (`mempalace init <dir>` puis `mempalace mine <dir>`)

→ **Complémentaires, pas concurrents** : claude-mem = passif/auto, mempalace = actif/structuré.

## Pour activer
Au prochain démarrage de session Claude Code, le MCP server mempalace sera auto-discovered. Pour initialiser un palace pour le projet CEE Engine :
```
/Users/azert/.mempalace-venv/bin/mempalace init /Users/azert/CEE_ENGINE
/Users/azert/.mempalace-venv/bin/mempalace mine /Users/azert/CEE_ENGINE
```

## Backups préventifs
- `~/.claude/backups/claude.json-pre-mempalace-2026-04-27-XXXX.json` (avant ajout du MCP block)

## Désinstaller
```
rm -rf /Users/azert/.mempalace-venv /Users/azert/.mempalace
node -e "const fs=require('fs');const p='/Users/azert/.claude.json';const j=JSON.parse(fs.readFileSync(p,'utf8'));delete j.mcpServers.mempalace;fs.writeFileSync(p,JSON.stringify(j,null,2));"
```

## Dépendances installées dans le venv
chromadb 1.5.8, onnxruntime 1.19.2, opentelemetry, pydantic, kubernetes, huggingface-hub, etc. (~80 packages, ~500 Mo dans le venv)
