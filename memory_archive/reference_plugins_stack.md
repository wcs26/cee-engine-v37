---
name: plugins_stack
description: Inventaire plugins Claude Code Jimmy. Vérifié 2026-05-08 : 5 plugins + 1 MCP installés et activés. superpowers réinstallé 2026-05-08.
type: reference
originSessionId: 77f696d7-e327-4ff8-9534-f54fec80bc4b
---

## ✅ État vérifié 2026-05-08 (post-ultrathink Jimmy)

Vérification via `claude plugin list` + `~/.claude/plugins/installed_plugins.json` :

| Plugin | Version | Statut |
|--------|---------|--------|
| claude-mem@thedotmack | 12.4.7 | ✅ enabled |
| code-review@claude-plugins-official | unknown | ✅ enabled |
| frontend-design@claude-plugins-official | unknown | ✅ enabled |
| planning-with-files@planning-with-files | 2.35.0 | ✅ enabled |
| superpowers@superpowers-marketplace | 5.0.7 | ✅ enabled (réinstallé 2026-05-08) |

MCP servers (`~/.claude.json`) :
| MCP | Statut |
|-----|--------|
| mempalace | ✅ actif (palace dir ~/.mempalace/palace existe) |

Anomalie corrigée 2026-05-08 : superpowers absent de installed_plugins.json malgré marketplace ajouté. Réinstallé via `claude plugin install superpowers@superpowers-marketplace`.

---

## Historique installation

Stack plugins activés au **2026-04-27** sur `/Users/azert/.claude/` :

| Plugin | Marketplace | Source GitHub | Rôle |
|---|---|---|---|
| `claude-mem` | thedotmack | thedotmack/claude-mem | Capture auto des sessions Claude Code, observations typées (bugfix/discovery/decision) |
| `code-review` | claude-plugins-official | anthropics/claude-plugins-public | Code review automatisé multi-agents avec scoring confiance |
| `frontend-design` | claude-plugins-official | anthropics/claude-plugins-public | Design frontend distinctif, anti-AI-slop, parfait pour oracle.html |
| `superpowers` | superpowers-marketplace | obra/superpowers-marketplace | Skills framework : TDD red-green-refactor, debug systématique, brainstorming socratique, subagent-driven development |
| `planning-with-files` | planning-with-files | OthmanAdi/planning-with-files | Pattern Manus (acquisition $2B) : 3-File pattern task_plan.md / findings.md / progress.md pour planification persistante |
| `mempalace` (MCP) | n/a | milla-jovovich/mempalace + PyPI | Mémoire sémantique ChromaDB, 19 outils MCP, organisation wings/halls/rooms (méthode des loci) |

## Configuration
- **`~/.claude/settings.json`** : 3 marketplaces dans `extraKnownMarketplaces` (thedotmack, superpowers-marketplace, planning-with-files), 5 plugins dans `enabledPlugins`. claude-plugins-official est marketplace par défaut (pas listé dans extraKnownMarketplaces).
- **`~/.claude.json`** : MCP server `mempalace` pointe vers `/Users/azert/.mempalace-venv/bin/mempalace mcp`.

## Activation
Au prochain démarrage de Claude Code, tous les plugins seront chargés. Les skills exposées par chaque plugin apparaîtront dans le menu skills.

## Backups préventifs (multiples points de restauration)
- `~/.claude/backups/memory-cee-engine-2026-04-27.tar.gz` (mémoire CEE 19 fichiers initiale)
- `~/.claude/backups/settings-pre-claudemem-2026-04-27.json` (avant claude-mem)
- `~/.claude/backups/settings-pre-multiplugin-2026-04-27-XXXX.json` (avant code-review/frontend-design)
- `~/.claude/backups/settings-pre-superpowers-2026-04-27-XXXX.json` (avant superpowers/planning-with-files)
- `~/.claude/backups/claude.json-pre-mempalace-2026-04-27-XXXX.json` (avant MCP mempalace)

## Mémoire CEE Engine
22 fichiers dans `~/.claude/projects/-Users-azert-CEE-ENGINE/memory/`. **Intacte**, aucun fichier touché par les installs. Sources de vérité pour toute prise de décision :
- `feedback_engine_pillars.md` — 4 piliers (ludique + connaissances + anticipation + précision + vérité)
- `feedback_north_star.md` — boussole projet (simple + juste + vérifié + intelligent + prédictif)
- `feedback_engine_ux_suggestions.md` — questions en suggestions, pas questionnaire
- `feedback_never_regress.md` — jamais écraser par version simple
- `feedback_agent_strategie.md` — pré-réflexion + jamais 2 agents oracle.html + post-vérification
- `project_dossier_ahbfc.md` — dossier vivant, irreplaçable

## Désinstallation propre (si besoin)
```
# Désinstaller un plugin = retirer du enabledPlugins + extraKnownMarketplaces si seul plugin de son marketplace
node -e "const fs=require('fs');const p='/Users/azert/.claude/settings.json';const j=JSON.parse(fs.readFileSync(p,'utf8'));delete j.enabledPlugins['<plugin>@<marketplace>'];fs.writeFileSync(p,JSON.stringify(j,null,2));"
# Optionnel : supprimer le clone marketplace
rm -rf /Users/azert/.claude/plugins/marketplaces/<marketplace-name>
```
