# CR CNIG — GT Bâti 12 mars 2026 — Synthèse pour CEE Engine

> Source : https://cnig.gouv.fr/IMG/pdf/cr-cnig-jeudi-12-mars-2026.pdf
> Lecture : V37.3.31 par CEE Engine (extraction PDF + synthèse stratégique).

## Contexte institutionnel — confirmation du RNB comme pivot national

- Le **comité stratégique "Numérique et données pour la planification écologique"**
  (co-présidé par **SGPE** + **DINUM**) a priorisé en décembre 2025 le chantier
  de structuration de la donnée bâtiment **autour du RNB**.
- **Plan de convergence piloté avec DHUP et DGFIP**, points hebdomadaires,
  restitutions au comité stratégique des **14 avril 2026** puis **juin-juillet 2026**.
- Approche **"briques de Lego"** : fabriquer d'abord les briques (identifiants,
  liens entre entités) → assembler ensuite par cas d'usage.

→ **Implication CEE Engine** : nous misons sur la bonne brique. L'État aligne
ses référentiels nationaux sur le RNB. Notre intégration V37.3.30 est
au cœur de la stratégie nationale.

## Architecture en 2 cercles concentriques

### Premier cercle — pivots d'interopérabilité (priorité absolue)
> *"Le cœur du travail, c'est le référentiel national des bâtiments (RNB) et
> ses relations avec les autres référentiels socles — adresse (BAN), parcelle
> (cadastre), locaux (RIAL), commune, copropriété."*

Pivots reconnus par le CNIG :
- **RNB** (bâtiment) ← clé de voûte
- **BAN** (adresse) ← déjà intégré V37.3.30
- **Cadastre** (parcelle) ← non intégré CEE Engine
- **RIAL** (logements et locaux) ← non intégré
- Commune (codes INSEE)
- Copropriété (registre national)

→ **Action CEE Engine** : V37.3.30 nous a connecté à 2/6 (RNB + BAN). Étapes
suivantes pour rejoindre 100 % du premier cercle :
1. **Cadastre** : récupérer la parcelle via API IGN cadastre par lat/lon (~2 j)
2. **RIAL** : croiser avec API RIAL pour identifier les locaux dans le bâtiment (~2 j)
3. Code INSEE : déjà partiellement (via dept SIRENE) — étendre à 5 chiffres

### Second cercle — données métiers
> *"Consommation d'eau potable, données énergétiques (points de livraison),
> rénovation (ANAH), construction neuve (RE2020), santé, équipements sportifs,
> etc. Chacune de ces thématiques nécessite de raccrocher un objet métier à
> des identifiants du socle de référence."*

→ **Implication majeure CEE Engine** : le **CEE/audit énergétique** est
**explicitement** dans le second cercle ("données énergétiques (points de
livraison)" + "rénovation (ANAH)"). CEE Engine a vocation à devenir un
**producteur de données métier** raccroché au socle RNB.

→ **Opportunité stratégique** : se positionner comme **implémentation de
référence** pour la donnée métier "audit CEE", attendue par le CNIG :
> *"Dans tous les cas il faudra des implémentations de référence pour se
> confronter à la réalité des données. […] Pas de norme contraignante
> exhaustive, mais un cadre informationnel."*

## Convergence DATA-BIM — validation de l'approche

> *"Les standards descriptifs détaillés (IFC, CityGML) ne sont pas adaptés à
> l'échelle nationale et aux usages décisionnels grande masse. Ce qui permet
> réellement l'interopérabilité, c'est le pivot commun par l'identifiant
> bâtiment/logement."*

→ **CEE Engine valide cette approche** : nous ne tentons pas de modéliser
finement chaque bâtiment (BIM), nous nous raccrochons à l'ID-RNB pour
l'interopérabilité.

## Gouvernance des données

### Frontière socles vs métiers
- **Données socles** (RNB, BAN, cadastre, RIAL) : corrigeables collectivement
  via contribution ouverte (token API)
- **Données métiers** (DPE, fiscal, etc.) : **à la main du producteur seul**
  (modification stricte par admin émettrice)

→ **CEE Engine en tant que producteur de données métier** : nous gérons nos
audits CEE en propre. Mais nous **contribuons** aux données socles RNB quand
nous détectons des écarts terrain (cf. V37.3.31 endpoint `/rnb/contribute`).

### Stabilité des identifiants — demande forte
> *"La Direction de l'Immobilier de l'État a besoin que les identifiants RNB
> ne changent pas constamment pour assurer le lien avec ses propres SI."*

→ **Confirmation pour CEE Engine** : on peut intégrer l'ID-RNB dans nos
tunnels avec la garantie de pérennité officielle. Documentation officielle du
cycle de vie : https://rnb-fr.gitbook.io/documentation/cycle-de-vie-de-la-donnee

### "La qualité par l'usage"
> *"L'idée a été avancée que la qualité des données augmente naturellement
> quand elles sont utilisées."*

→ **Validation de notre rôle** : chaque audit CEE Engine = un usage du RNB =
contribue à la qualité globale. Plus on l'utilise, plus la donnée s'améliore.

## Schéma vs standard — différence importante
> *"Un schéma de données seul ne suffit pas à assurer l'interopérabilité :
> il faut aussi les règles de remplissage (valeurs possibles, définitions
> des champs)."*

→ **À surveiller** : le travail commence par un schéma simple, mais évoluera
vers un standard complet. CEE Engine doit s'aligner sur les définitions
officielles dès qu'elles sortent (date de mise à jour : juin-juillet 2026).

## Prochaines étapes annoncées

| Date | Action | Impact CEE Engine |
|---|---|---|
| Avril 2026 | SGPE partage nouvelle version schéma de données | Adapter modèle de données tunnel |
| 14 avril 2026 | Restitution comité stratégique | Lire pour aligner roadmap |
| Mai 2026 | RNB propose un GT sur règles de gouvernance | **Y participer** comme acteur écosystème |
| Juin-juillet 2026 | Restitution intermédiaire | Aligner V37.4 sur livrables |

## 5 actions concrètes CEE Engine post-CR CNIG

1. ✅ **Intégrer BAN + RNB dans tunnel** — fait V37.3.30
2. **S'inscrire comme contributeur RNB** (token) — V37.3.31 endpoint prêt
3. **Soumettre CEE Engine comme cas d'usage métier officiel** sur rnb.beta.gouv.fr
   → références institutionnelles + entrée dans le 2ᵉ cercle reconnu par État
4. **Suivre la prochaine version du schéma SGPE** (avril 2026)
5. **Participer au prochain GT RNB** sur règles de gouvernance (mai 2026) au
   nom de WCS Bulgaria EOOD comme acteur SaaS européen — réponse publique
   utile pour visibilité

---

*Document V37.3.31 · Synthèse stratégique extraite du CR CNIG officiel.*
