# AUDIT FINAL V43 — CEE Engine
**Date** : 2026-05-23
**Version** : V43.3 prod (cee-engine-v37.fly.dev)

## 1. Couverture catalogue (best of toutes versions)

| Métrique | Valeur | Source |
|----------|--------|--------|
| Fiches totales | 253 | fiches.json |
| Fiches actives | 222 | V39 cleanup |
| Complexes opérationnels | 32 (table_str 14 + table_2d 7 + formule 6 + formule_tranches 4 + table 1) | V39.2/V39.3 |
| Couverture NAF | 100% (227 mappings) | V39.1 |
| sect_factors backend ↔ V1 catalog | 100% aligné | V41.6 / V41.7 |
| Bugs étiquettes coûts corrigés | 8 | V41.2 / V41.6 |
| Postes métier mappés | 23 catégories, 158/222 fiches (72%) | V43.3 |

## 2. Cartographie POSTE × NB FICHES

| Poste métier | Icône | Fiches actives |
|--------------|-------|----------------|
| Régulation & GTB | 🎛 | 24 |
| Process industriel | ⚙ | 18 |
| Chaudière | 🔥 | 13 |
| Serres agricoles | 🌾 | 12 |
| Pompe à chaleur | 🌡 | 11 |
| Eau chaude sanitaire | 💧 | 10 |
| Toiture & combles | 🏠 | 9 |
| Transport / Flotte | 🚛 | 8 |
| Fenêtres & vitrage | 🪟 | 8 |
| Ventilation | 🌀 | 6 |
| Murs (ITE/ITI) | 🧱 | 6 |
| Plancher bas | ⬛ | 6 |
| Climatisation / Froid | ❄ | 6 |
| Récup chaleur fatale | ♻ | ~5 |
| Élevage | 🐄 | 4 |
| CPE / Rénovation globale | 📋 | 4 |
| Réseau de chaleur | 🌡 | 4 |
| Émetteurs chauffage | ♨ | 2 |
| Déstratification | 💨 | 2 |
| Éclairage LED | 💡 | 2 |
| Solaire PV/PVT | ☀ | 1 |
| Audit / ISO 50001 | 📊 | 1 |
| Calorifugeage | 🔗 | 1 |
| Brûleur | 🔥 | 2 |
| Autres | 📦 | 64 (28%) |

## 3. Flow utilisateur (best of all versions)

```
┌─ SETUP (face cachée vendeur) ───────────────────────────────────────────┐
│ P20 Setup Dossier — opérateur, COFRAC, délégataire, prix cumac, %       │
│      commissions, templates docs                            (V40.0)     │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ OUVERTURE VISIO CLIENT ────────────────────────────────────────────────┐
│ P21 Déroulement projet CEE — 4 étapes pédagogiques + descente 2 temps   │
│      (travaux 0€ puis économies)                            (V40.1)     │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ AMONT — qualifier le potentiel ────────────────────────────────────────┐
│ P1  Identifier — SIRET → APE auto + 5 badges sources légitimes (V42.6.1)│
│ P2  Énergie/facture/CdP + bandeau "infos connues"                        │
│ P18 Précisions techniques (V42.10 + V43.0) :                            │
│       • Auto-mapping NAF → micro-activité (12 catégories) (V42.9)       │
│       • 100 questions ciblées CEE par micro-activité (V42.10)           │
│       • Split ✓ Validé / ? Présumé avec confidence indicators (V43.0)   │
│       • Présumées repliables (1-2 questions vraies visibles)            │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ PACK + AVAL ───────────────────────────────────────────────────────────┐
│ P5  Pack CEE :                                                          │
│   ◇ RÉCAP PAR POSTE — 23 catégories triées par prime (V43.3)            │
│   ◇ Bandeau Impact CO₂/an + économie facture/an (V43.2)                 │
│   ◇ Opérations 0€ reste à charge                                        │
│   ◇ Opportunités complémentaires (couverture 50-90%) (V42.3)            │
│   ◇ AVAL : Questions précises par fiche retenue pour calcul exact       │
│       (V42.11)                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─ CLOSING ───────────────────────────────────────────────────────────────┐
│ P7  Économies — 6 KPI (Prime, Éco facture/an, CO₂/an, MWh cumac,        │
│      Coût TTC, Couverture) + bandeau impact 15 ans + équivalences       │
│      voitures/arbres                                        (V43.2)     │
│ P9  Documents — convention, AH, mandat, devis (3 exports BO masqués)    │
│ P10 Synthèse projet CEE                                     (V42.6.3)   │
└─────────────────────────────────────────────────────────────────────────┘
```

## 4. Dualité Mode Vendeur / Mode Complet

| Élément | Mode Complet (BO) | Mode Vendeur (visio client) |
|---------|-------------------|------------------------------|
| Stepper | 17 onglets | 9 nœuds logiques |
| Phase labels | Visibles | Cachés (flow continu) |
| Sections jargon V1 / audit trail | Visibles | `.bo-only` |
| Jarvis FAB Penta-IA | Visible | Caché |
| Indicateur Étape X/9 + barre | — | Affiché |
| Cartes opportunités Rothschild | — | P2 + P5 (V41.1) |
| Confidence ✓ / ? sur questions | Visible aussi | Mis en avant |
| Backend & calculs | Identique | Identique |

## 5. Promesses originelles vs livré

| # | Promesse | État |
|---|----------|------|
| 1 | Détecteur CEE prédictif depuis SIRET | ✅ |
| 2 | APE auto-déduit | ✅ |
| 3 | Bonnes questions par fiche, pas généraliste | ✅ V42.10 |
| 4 | UN outil intelligence V1 dans slides V2 | ✅ V42 |
| 5 | Face cachée riche / face visible épurée | ✅ V41.0 toggle |
| 6 | Mode Vendeur / Mode Complet | ✅ |
| 7 | Précis, prédictif sans le montrer | ✅ V43.0 skip intelligent |
| 8 | Honnête (accepte de ne pas savoir) | ✅ V43.0 ?/✓ |
| 9 | Anticipateur (prime estimée live) | ✅ V41.1 cartes |
| 10 | Adaptatif (skip questions connues) | ✅ V43.0 |
| 11 | Ne demande que ce qui manque | ✅ V43.0 collapsable |
| 12 | Simple, précis, compréhensible | ✅ V42.6 polish |
| 13 | Mentalité Gates/Jobs/Zuck | ✅ logique épurée |
| 14 | Pertinence Rothschild | ✅ V41.1 + V42.6 |
| 15 | Présenté comme opportunité | ✅ cartes opportunités |
| 16 | Légitime/professionnel | ✅ V42.6.1 badges sources |
| 17 | Pitch Total CEE plusieurs millions | ✅ catalogue + UI premium |
| 18 | Anticipation par poste métier | ✅ V43.3 récap par poste |
| 19 | CO₂ / économie facture sans saisie | ✅ V43.2 |
| 20 | Documents auto-générés | ✅ V40.0 + P9 |

## 6. Trous restants (ouverture pour V44+)

- 28% fiches restées en `autres` lors de la classification poste → enrichir mots-clés
- BAT-EQ-124/125 (meubles frigo) sans micro-activity dédiée commerce — déjà partiellement couvert
- Pas de calcul "économie facture par poste" (agrégé seulement global)
- Pas de zoom interactif sur les cartes poste P5 (juste hover)
- Documents générés pas testés end-to-end avec données réelles depuis Setup Dossier

## 7. Versions clés (best of)

| Version | Apport |
|---------|--------|
| V39.0-3 | Data quality + 222 actives + 32 complexes + questions précises par fiche |
| V40.0-1 | Setup Dossier + Déroulement Projet (slides BO + visio) |
| V41.0-1 | Toggle Mode Vendeur ↔ Complet + cartes opportunités Rothschild |
| V41.2-7 | Audit data complet (bugs LED/PAC, sect_factors, cohérence prime/cover) |
| V42.0-8 | Refonte unifiée V2 default + flow vendeur 9 étapes + polish slides |
| V42.9-11 | Auto-mapping NAF + 100 questions amont/aval/sectoriel enrichies |
| V43.0    | Skip intelligent ?/✓ sur P18 |
| V43.2    | CO₂ + économie facture auto |
| V43.3    | Récap par poste métier en P5 |
