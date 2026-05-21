# AUDIT_REFONTE — CEE Engine vers outil double-vue unifié

**Date** : 2026-05-21
**Contexte** : Refondre `oracle.html` (21 197 lignes) en un seul outil avec dualité native VUE [Complet ↔ Vendeur]. Fin de la coexistence V1 legacy / V2 slides en parallèle. Pitch Total CEE à terme — exigence pro.

---

## 1. État des lieux chiffré

| Mesure | Valeur |
|--------|--------|
| Total lignes `oracle.html` | **21 197** |
| Taille fichier | 1 432 KB |
| Sections marquées par bandeau commentaire | 255 |
| Bloc V1 legacy (L1–L16550) | ~16 000 lignes · 75 % |
| Bloc V2 slides (L16551–fin) | ~5 200 lignes · 25 % |
| Champs `STATE.*` (V1) | 31 distincts · 727 usages |
| Champs `V2.state.*` | 25 distincts · 247 usages |
| Champs communs V1↔V2 | **1 seul** (`sellerMode`) |

**Conclusion** : V2 a été construit **en parallèle** de V1, pas dessus. C'est pour ça que les deux coexistent dans le même fichier avec leurs propres états, calculs, rendus. Le toggle 🚀 Mode Clair bascule la `<body class="v2-mode">` qui cache l'une et révèle l'autre.

---

## 2. Cartographie V1 ↔ V2

### Frontières dans le code

```
L 3756  STATE V1 init (var STATE = { … })
L 4152  FICHES_CATALOGUE V1 (234 fiches × 7 modèles, ~6 000 lignes)
L 5045  getEffectiveKwhc — moteur calcul V1
L10142  renderFiches — rendu pertinence/secteurs V1
L10606  calculateResults — flow résultats V1 (Étape 4)
L16550  var V2 = { … }  ← début bloc V2
L16551  V2.init()
L16576  V2.setUiMode (V41.0)
L17521  V2._drawP2 (Page 2 — Affiner)
```

### Doublons fonctionnels (8 majeurs)

| Fonctionnalité | V1 | V2 |
|---|---|---|
| Calcul cumac unitaire | `getFullCalc(fiche, qty, zone, eType)` | `/expert` backend |
| Calcul global pack | `getGlobalCalc()` retourne `gc.details + gc.totals` | lit `window.pack` retourné par `/expert` |
| Catalogue fiches | `FICHES_CATALOGUE` JS inline (234 entrées) | `fiches.json` backend (253 entrées) |
| Rendu fiches éligibles | `renderFiches()` + `filterFiches(sector)` | `_renderPrimesZero` + `_renderPrimesReco` |
| Questionnaire universel | `renderUniversalQuestionnaire()` 6 thèmes hardcodés | `_drawP2` Section D appelle même fonction |
| Score qualification | `calculateScore()` retourne 0-100 | `/expert` calcule côté backend |
| Multi-IA Penta | `v32ComputeEnhancedCalc()` + `v32RenderAiResult` | `_renderP3` (P3 Analyser) |
| Push CRM Monday | helpers V1 | `_renderPushCRM` |

---

## 3. Inventaire des slides V2 actuelles

### Slides implémentées (16 sur 17 prévues)

| ID | Slide | Fonction render | Statut | Garder ? |
|---|---|---|---|---|
| 0 | Focus Appel cockpit | `_focusUpdateKPI` | ✅ utilisé | ❓ |
| 1 | Identifier prospect | `renderP1*` | ✅ utilisé | **✓ flow vendeur** |
| 2 | Affiner (questions précises) | `_drawP2` (Section A→F) | ✅ utilisé | **✓ flow vendeur** |
| 3 | Analyser IA | `renderP3` (Penta-IA) | ✅ utilisé | **✓ mode complet seul** |
| 4 | Pack (V37.4.17 R1) | `_renderAnalyse` | ⚠ partiel | à fusionner |
| 5 | Primes 0€ reste à charge | `_renderPrimesZero` | ✅ utilisé | **✓ flow vendeur** |
| 6 | Primes recommandées | `_renderPrimesReco` | ✅ utilisé | à fusionner avec 5 |
| 7 | Économies facture | `renderP5` | ✅ utilisé | **✓ flow vendeur** |
| 8 | Conformité PNCEE | `_renderConformite` | ✅ utilisé | mode complet seul |
| 9 | Documents | `_renderDocuments` | ✅ utilisé | **✓ flow vendeur** |
| 10 | Rapport final + PDF | `_renderRapport` | ✅ utilisé | **✓ flow vendeur** |
| 11 | Hunt prospects (placeholder) | `_renderHunt` | ⚠ placeholder | mode complet |
| 12 | Cartes & PLU (placeholder) | `_renderCartes` | ⚠ placeholder | mode complet |
| 13 | 15 Gisements (placeholder) | `_renderGisementsR1` | ⚠ placeholder | mode complet |
| 14 | Catalogue 234 fiches | `_renderCatalog` | ✅ utilisé | mode complet seul |
| 15 | Closing armé | `_renderClosingArme` | ✅ utilisé | mode complet seul |
| 16 | Push CRM | `_renderPushCRM` | ✅ utilisé | mode complet seul |
| 17 | Suivi 9 ans | `_renderSuivi9Ans` | ✅ utilisé | mode complet seul |
| 18 | Précision inputs | `_renderPrecisionInputs` | ✅ utilisé | à fusionner P2 |
| 19 | Opérations avec RAC | `_renderOperationsAvecRAC` | ✅ utilisé | à fusionner P6 |
| 20 | Setup Dossier (V40.0) | `_renderSetupDossier` | ✅ utilisé | **✓ flow vendeur** |
| 21 | Déroulement projet (V40.1) | `_renderDeroulement` | ✅ utilisé | **✓ flow vendeur** |

---

## 4. Flow cible proposé (8 slides Mode Vendeur)

```
┌─ MODE VENDEUR (visio client, 8 slides épurées) ──────────────────────────┐
│                                                                          │
│  ⚙ Setup Dossier   →   🎬 Déroulement   →   📞 Identifier   →   🎯 Affiner │
│  (face cachée)         projet CEE           prospect            questions  │
│   (P20)                (P21)                (P1)                (P2)       │
│                                                                          │
│      ↓ vers closing ↓                                                    │
│                                                                          │
│  💚 Travaux 0€    →   💰 Économies    →   📄 Documents   →   🏁 Synthèse  │
│  (P5+P6 fusion)        facture (P7)         (P9)              (P10)        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

┌─ MODE COMPLET (BO vendeur en prépa, +9 onglets backoffice) ──────────────┐
│  P3 Penta-IA · P8 Conformité PNCEE · P11 Hunt · P12 Cartes & PLU         │
│  P13 15 Gisements · P14 Catalogue 234 fiches · P15 Closing armé          │
│  P16 Push CRM · P17 Suivi 9 ans                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Plus de basculement 🚀 Mode Clair vers V1 legacy.** L'intelligence V1 (FICHES_CATALOGUE, getFullCalc, calc*PerXXX) devient le moteur sous-jacent appelé par les slides — on supprime ses rendus dupliqués, on garde son cerveau.

---

## 5. Décisions à prendre (5 questions structurantes)

### Décision 1 — Sort de V1 legacy

- **A** Supprimer entièrement V1 (étapes Wizard 5 étapes, `calculateResults`, `renderFiches` …) → catalogue récupéré dans `fiches.json` backend. ~10 000 lignes en moins.
- **B** Garder V1 derrière le toggle, le placer en "Mode Debug avancé" caché par défaut. 0 ligne supprimée.
- **C** Vider V1 mais préserver `FICHES_CATALOGUE` JS (les calculs `calcAbsolutePerXXX` qui sont la formule officielle ADEME) — V2 appelle ces helpers. ~5 000 lignes supprimées.

### Décision 2 — `FICHES_CATALOGUE` JS inline vs `fiches.json` backend

Aujourd'hui deux sources de vérité (234 fiches V1 vs 253 fiches backend). Lequel devient unique ?

- **A** `fiches.json` backend → V2 récupère via `/fiches` ou `/expert`, V1 catalog supprimé.
- **B** Garder V1 inline pour le calcul ADEME officiel (formules JS), backend = méta seulement.
- **C** Fusionner les deux (sync au build time).

### Décision 3 — Slides à fusionner

- P5 Primes 0€ + P6 Primes recommandées → une seule slide "Pack final" avec tri couverture ? (recommandé)
- P4 Analyse + P3 Penta-IA → garder P3 seul (Penta-IA = la vraie intelligence) ?
- P18 Précision inputs + Section F P2 → fusionner dans P2 (déjà fait V39.3.2) ?
- P19 Opérations avec RAC → fusionner dans P6 ?

### Décision 4 — État unifié

- Aujourd'hui 2 états séparés (`STATE` V1 + `V2.state`).
- Cible : **1 seul état `App.state`** lu/écrit partout. Migration 31+25 champs à mapper.

### Décision 5 — Méthode de bascule

- **A** Refacto in-place sur `oracle.html` actuel, par commits incrémentaux (4 commits prévus V42.0→V42.3).
- **B** Nouveau fichier `oracle.html` from scratch, ancien renommé `oracle-legacy.html`, migration sur 2-3 semaines.

---

## 6. Plan de migration proposé (option A in-place)

| Phase | Scope | Lignes touchées | Risque |
|---|---|---|---|
| **V42.0** Activer V2 par défaut | Retirer bascule V1 défaut → V2 défaut. Le toggle 🚀 reste accessible en debug. | ~10 lignes | Très faible |
| **V42.1** Unifier état | Migrer `V2.state` à utiliser `STATE.diagnostic` quand possible. Plus de duplication. | ~200 lignes | Moyen (tests) |
| **V42.2** Marquer `.bo-only` | Toutes les sections du Mode Complet seul (P3 Penta, P8 Conformité, P11-17 BO) reçoivent `class="bo-only"`. Le toggle V41.0 les cache en Mode Vendeur. | ~50 lignes | Très faible |
| **V42.3** Fusionner slides | P5+P6 → "Pack final unifié". P18+P19 absorbées dans P2/P6. | ~400 lignes | Moyen |
| **V42.4** Polish flow vendeur | Bouton "Suivant" cohérent entre slides. Progression visuelle. Transitions. | ~150 lignes | Faible |
| **V42.5** Cleanup V1 (optionnel) | Supprimer `renderFiches`, `calculateResults`, `STATE.detectedSectors`, etc. → si Décision 1 = A ou C. | -5 000 à -10 000 lignes | Élevé (régression visible) |

**Total estimation** : V42.0 → V42.4 = ~5-8h de code + tests. V42.5 = +3-4h supplémentaires si retrait V1.

---

## 7. Risques techniques

| Risque | Détail | Mitigation |
|---|---|---|
| Cassage UI sur retrait V1 | Certains liens internes pointent peut-être sur V1 (`scrollIntoView(detailTable)` …) | Audit `getElementById` pré-retrait |
| Perte de l'intelligence calc V1 | `calcAbsolutePerXXX` (formules officielles ADEME inline JS) | Préserver dans `FICHES_CATALOGUE` ou porter en `moteur_cee_master.py` |
| 193 tests existants | Tournent contre backend, OK même si V1 supprimé. | À surveiller — `pytest` sur chaque commit |
| Production live | Vendeurs WCS Pro l'utilisent peut-être actuellement | Feature flag ou rollout progressif |

---

## 8. Recommandation

**Décision 1 = C** (vider V1 mais préserver les formules ADEME inline) — équilibre entre nettoyage et préservation de l'IP métier.

**Décision 2 = A** (`fiches.json` backend = source unique). Les formules JS ADEME deviennent des helpers purs, appelés sur demande par les slides.

**Décision 3 = oui** sur P5+P6, oui sur fusion P18/P19, non sur P3+P4 (Penta-IA reste isolée).

**Décision 4** = État unifié `App.state` créé en V42.1.

**Décision 5 = A** (in-place incrémental). Le fichier reste un, on coupe les couches mortes au fur et à mesure. Pas de big bang.

**Ordre recommandé** : V42.0 → V42.2 (sécuriser le Mode Vendeur) puis V42.3 → V42.4 (consolider) puis seulement V42.5 si tu valides le retrait V1 après revue.

---

## 9. Prochaine étape

Tu valides les **5 décisions** (sections 5), je produis un plan de code précis V42.0 à V42.5 commit par commit, et je commence par V42.0 (10 lignes, faible risque) — uniquement après ton GO sur les décisions.

Pas de code tant que ce document n'est pas accepté ou amendé.
