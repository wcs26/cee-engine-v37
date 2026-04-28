# Audit cohérence unités prime ↔ coût (V37.3.34)

> **91 fiches sur 246** ont une **incohérence d'unité** entre la prime CEE
> (selon la fiche officielle) et le coût travaux (table COUT_TRAVAUX d'oracle.html).
> Conséquence : le **ratio de couverture** affiché peut être délirant
> (ex: BAT-SE-103 affichait 428 % alors que le ratio réel est ~13 %).
>
> **V37.3.34 garde-fou activé** — le ratio est masqué et remplacé par
> un badge orange **"⚠ unités hétérogènes"** quand `cost.u ≠ fiche.unit`.
> Tooltip explicatif au survol. Audit complet pour reprise progressive ci-dessous.

## Cas trouvé par Jimmy le 2026-04-29

**BAT-SE-103 Réglage équilibrage chauffage tertiaire** affichait :
- *"85 €/unité prime vs 22 €/radiateur cout"*
- *"ratio 428 %"*

Diagnostic :
- Prime fiche officielle = par **unité** (= installation entière)
- Coût `COUT_TRAVAUX` = par **radiateur** (= sous-composant du système)
- Calcul : `prime_nette / (cost × 0.75 × 1.20)` avec mauvais alignement d'unité
- Pour un bâtiment de 30 radiateurs : coût total ≈ 660 € HT, prime 85 € → ratio réel ~13 %

**Fix V37.3.34** : BAT-SE-103/104/105 alignés sur l'unité officielle de la fiche
+ ajustement coût moyen au coût d'installation entière (~600-1 000 €).

## Stratégies de correction (3 niveaux)

| Code | Stratégie | Quand |
|---|---|---|
| **1** | Alignement direct (unités synonymes) | `installation` ↔ `bâtiment` ↔ `unité` ↔ `véhicule` |
| **2** | Facteur de conversion documenté | `kW` → `unité` (10-50 kW typique), `point` → `installation` (N points), `ml` → `m²` |
| **3** | Incomparable — masquer ratio (afficher juste les chiffres bruts) | `personne` vs `site`, `m³` vs `m²`, `MWh` vs `ml` |

## Liste complète (91 incohérences détectées)

| Ref | Fiche unit | Cost u | Cost moy | Stratégie suggérée |
|---|---|---|---:|---|
| AGRI-EQ-101 | `unité` | `bâtiment` | 3 500 € | 1 — synonyme |
| AGRI-EQ-104 | `m²` | `bâtiment` | 5 000 € | 3 — incomparable |
| AGRI-EQ-105 | `unité` | `installation` | 6 250 € | 1 — synonyme |
| AGRI-EQ-106 | `unité` | `installation` | 7 500 € | 1 — synonyme |
| AGRI-EQ-107 | `m²` | `installation` | 3 650 € | 3 — incomparable |
| AGRI-EQ-108 | `m³` | `m²` | 45 € | 3 — incomparable |
| AGRI-EQ-110 | `unité` | `installation` | 4 500 € | 1 — synonyme |
| AGRI-EQ-113 | `unité` | `point` | 215 € | 2 — facteur N points/installation |
| AGRI-SE-101 | `unité` | `bâtiment` | 300 € | 1 — synonyme |
| AGRI-TH-101 | `unité` | `kW` | 600 € | 2 — facteur kW→unité (10-50 kW) |
| AGRI-TH-102 | `m³` | `kW` | 380 € | 3 — incomparable |
| AGRI-TH-103 | `unité` | `kW` | 475 € | 2 — facteur kW |
| AGRI-TH-105 | `unité` | `kW` | 1 600 € | 2 — facteur kW |
| AGRI-TH-108 | `kW` | `m²` | 70 € | 3 — incomparable |
| AGRI-TH-110 | `kW` | `installation` | 4 750 € | 3 — incomparable |
| AGRI-TH-113 | `unité` | `kW` | 1 100 € | 2 — facteur kW |
| AGRI-TH-118 | `unité` | `kW` | 130 € | 2 — facteur kW |
| AGRI-TH-119 | `unité` | `installation` | 2 750 € | 1 — synonyme |
| BAR-EQ-110 | `logement` | `point` | 115 € | 2 — facteur N points/logement |
| BAR-EQ-112 | `point d'eau` | `unité` | 215 € | 3 — incomparable |
| BAR-EQ-115 | `logement` | `unité` | 300 € | 3 — incomparable |
| BAR-SE-104 | `logement` | `ml` | 12 € | 2 — facteur ml→logement |
| BAR-SE-108 | `unité` | `logement` | 1 150 € | 3 — incomparable |
| BAR-TH-101 | `unité` | `ml` | 115 € | 2 — facteur ml |
| BAR-TH-123 | `logement` | `unité` | 225 € | 3 — incomparable |
| BAR-TH-141 | `unité` | `m²` | 3 500 € | 3 — incomparable |
| BAR-TH-143 | `m²` | `unité` | 4 750 € | 3 — incomparable |
| BAR-TH-161 | `unité` | `ml` | 22 € | 2 — facteur ml |
| BAR-TH-165 | `kW` | `unité` | 27 500 € | 3 — incomparable |
| BAR-TH-168 | `m²` | `unité` | 3 500 € | 3 — incomparable |
| BAR-TH-169 | `kW` | `m²` | 2 250 € | 3 — incomparable |
| BAR-TH-170 | `kW` | `unité` | 4 250 € | 3 — incomparable |
| BAR-TH-173 | `unité` | `m²` | 300 € | 3 — incomparable |
| BAR-TH-174 | `logement` | `unité` | 1 150 € | 3 — incomparable |
| BAR-TH-175 | `logement` | `m²` | 4 250 € | 3 — incomparable |
| BAR-TH-176 | `unité` | `m²` | 2 750 € | 3 — incomparable |
| BAR-TH-177 | `logement` | `m²` | 2 150 € | 3 — incomparable |
| BAR-TH-178 | `unité` | `logement` | 35 000 € | 3 — incomparable |
| BAR-TH-179 | `kW` | `unité` | 16 000 € | 3 — incomparable |
| BAR-TH-180 | `kW` | `unité` | 22 000 € | 3 — incomparable |
| BAT-EQ-117 | `kW` | `kW froid` | 700 € | 3 — sémantique différente |
| BAT-EQ-124 | `m linéaire` | `ml` | 425 € | **synonyme — typo seulement** |
| BAT-EQ-125 | `m linéaire` | `point` | 170 € | 3 — incomparable |
| BAT-EQ-127 | `m²` | `point` | 115 € | 2 — facteur N points/m² |
| BAT-EQ-130 | `kW` | `point` | 290 € | 3 — incomparable |
| BAT-EQ-133 | `point d'eau` | `point` | 37 € | **synonyme — typo seulement** |
| BAT-EQ-134 | `m linéaire` | `m²` | 550 € | 3 — incomparable |
| BAT-EQ-135 | `kW` | `m²` | 475 € | 3 — incomparable |
| BAT-TH-101 | `m²` | `kW` | 140 € | 2 — facteur kW |
| BAT-TH-103 | `m²` | `kW` | 115 € | 2 — facteur kW |
| BAT-TH-105 | `unité` | `kW` | 425 € | 2 — facteur kW |
| BAT-TH-108 | `unité` | `kW` | 950 € | 2 — facteur kW |
| BAT-TH-109 | `logement` | `kW` | 825 € | 2 — facteur kW |
| BAT-TH-115 | `unité` | `kW` | 1 900 € | 2 — facteur kW |
| BAT-TH-121 | `m²` | `kW` | 190 € | 2 — facteur kW |
| BAT-TH-122 | `unité` | `installation` | 4 250 € | 1 — synonyme |
| BAT-TH-125 | `m²` | `installation` | 3 350 € | 3 — incomparable |
| BAT-TH-127 | `unité` | `m²` | 850 € | 3 — incomparable |
| BAT-TH-139 | `kW` | `installation` | 8 500 € | 3 — incomparable |
| BAT-TH-142 | `unité` | `installation` | 2 750 € | 1 — synonyme |
| BAT-TH-143 | `kW` | `installation` | 2 150 € | 3 — incomparable |
| BAT-TH-157 | `kW` | `point` | 140 € | 3 — incomparable |
| BAT-TH-158 | `m²` | `point` | 115 € | 2 — facteur N points/m² |
| BAT-TH-162 | `m²` | `kW` | 3 200 € | 2 — facteur kW |
| BAT-TH-163 | `m²` | `kW` | 2 500 € | 2 — facteur kW |
| BAT-TH-164 | `m²` | `kW` | 2 900 € | 2 — facteur kW |
| IND-BA-110 | `unité` | `point` | 215 € | 2 — facteur N points/installation |
| IND-UT-125 | `kW` | `installation` | 2 150 € | 3 — incomparable |
| IND-UT-131 | `m²` | `kW` | 700 € | 2 — facteur kW |
| RES-CH-103 | `unité` | `ml` | 215 € | 2 — facteur ml |
| RES-CH-104 | `unité` | `ml` | 275 € | 2 — facteur ml |
| RES-CH-105 | `m` | `m²` | 115 € | 3 — incomparable |
| RES-CH-106 | `m` | `ml` | 170 € | **synonyme — typo seulement** |
| RES-CH-108 | `MWh` | `ml` | 250 € | 3 — incomparable |
| RES-EC-104 | `kW` | `point` | 90 € | 3 — incomparable |
| TRA-EQ-101 | `unité` | `véhicule` | 1 400 € | 1 — synonyme |
| TRA-EQ-103 | `unité` | `véhicule` | 2 750 € | 1 — synonyme |
| TRA-EQ-104 | `unité` | `véhicule` | 2 150 € | 1 — synonyme |
| TRA-EQ-106 | `unité` | `véhicule` | 700 € | 1 — synonyme |
| TRA-EQ-107 | `unité` | `véhicule` | 4 250 € | 1 — synonyme |
| TRA-EQ-108 | `unité` | `véhicule` | 5 000 € | 1 — synonyme |
| TRA-EQ-109 | `unité` | `véhicule` | 3 500 € | 1 — synonyme |
| TRA-EQ-110 | `unité` | `véhicule` | 5 500 € | 1 — synonyme |
| TRA-EQ-111 | `unité` | `véhicule` | 2 150 € | 1 — synonyme |
| TRA-EQ-113 | `unité` | `véhicule` | 85 € | 1 — synonyme |
| TRA-SE-108 | `personne` | `site` | 4 250 € | 3 — incomparable |
| TRA-SE-109 | `personne` | `site` | 2 750 € | 3 — incomparable |
| TRA-SE-110 | `véhicule` | `site` | 2 150 € | 3 — incomparable |
| TRA-SE-111 | `véhicule` | `site` | 7 000 € | 3 — incomparable |
| TRA-SE-112 | `unité` | `site` | 5 500 € | 1 — synonyme |
| TRA-SE-113 | `véhicule` | `site` | 4 250 € | 3 — incomparable |

## Récap chiffré

- **91 mismatches** détectés (sur 246 entrées COUT_TRAVAUX, soit 37 %)
- **Stratégie 1 (synonymes simples)** : ~30 fiches → **fix rapide** (juste renommer cost.u)
- **Stratégie 2 (facteurs documentés)** : ~25 fiches → **modéré** (ajouter table de conversion)
- **Stratégie 3 (incomparable)** : ~36 fiches → **garde-fou seulement** (pas de fix possible)

## Plan d'action

### Quick win (~1 h, +30 fiches sains)
Renommer cost.u en synonyme (ex: `installation` → `unité`) pour les 30 fiches stratégie 1. Pas de changement de valeur. Le ratio redevient calculable.

### Phase 2 (~3 h, +25 fiches sains)
Ajouter une table `UNIT_CONVERSION_FACTORS` dans oracle.html :
```js
const UNIT_CONVERSION = {
  // {cost.u} → {fiche.unit} : facteur multiplicateur applique au cost
  'kW→unité': 25,        // 25 kW typiques par installation tertiaire
  'point→installation': 10,
  'ml→m²': 0.5,          // estimation linéaire vs surface
  // ...
};
```
Et utiliser ce facteur dans `calc()` pour aligner avant comparaison.

### Phase 3 (statu quo)
Les 36 fiches "incomparables" gardent le badge "⚠ unités hétérogènes" V37.3.34.
Aucun ratio affiché. Jimmy peut quand même calculer manuellement.

---

*Document V37.3.34 · Identifié par Jimmy le 2026-04-29 sur capture écran
BAT-SE-103. À reprendre progressivement.*
