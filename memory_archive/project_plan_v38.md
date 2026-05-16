---
name: Plan V38 — 5 priorités par ROI (21 avril 2026)
description: Plan stratégique validé par agent pré-réflexion. Ordre : deal réel → déploiement → PV → closing R2 → Monday PV. CEE = FINI.
type: project
originSessionId: 2df11f34-7c9e-449e-84cf-ffec1837e5ed
---
## Statut CEE Engine : TERMINÉ
39 modules, 85 tests, 5/5 IA, 10/10 vérifiés. Plus rien à ajouter côté CEE.

## 5 priorités par ROI

| # | Action | Temps | Impact | Statut |
|---|---|---|---|---|
| 1 | **Deal réel AHBFC** (utiliser l'outil, pas coder) | 2h | Valide tout | ⏳ Jimmy doit tester |
| 2 | **Déploiement** Railway/fly.io (pas Cloudflare Workers = pas Python) | 3h | Équipe accède | 🔜 |
| 3 | **Module PV MVP** (cotation auto depuis puissance + localisation) | 5h | 80% du CA | 🔜 |
| 4 | **Closing R2 live** (assistant temps réel en RDV) | 4h | +40K€/an documenté | ⏳ |
| 5 | **Monday PV sync** (boucle lead → cotation → closing) | 2h | Flux complet | ⏳ |

## Données PV disponibles sur PC Jimmy
- Cotations : Dupas (3 versions), Delquie, Gilbert
- Budget PV 2025 (.numbers + .pdf + .xlsx)
- Critères sélection fiche PV
- Guide stratégique PV OA S21
- Tblx découverte client pro PV
- 18+ transcriptions Sembly de RDV PV réels
- Datasheet AESOLAR

## /devil — Ne PAS faire
- Ne PAS ajouter de modules CEE (c'est fini)
- Ne PAS utiliser Cloudflare Workers pour Python Flask
- Ne PAS commencer PV avant déploiement (sinon équipe ne peut pas l'utiliser)
