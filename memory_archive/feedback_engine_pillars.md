---
name: engine_pillars
description: 4 piliers non-négociables de CEE Engine — ludique / surprend par connaissances / anticipation / précision / vérité. Toute UX doit les honorer ensemble
type: feedback
originSessionId: 77f696d7-e327-4ff8-9534-f54fec80bc4b
---
CEE Engine doit être :
1. **Ludique** — animations, chips qui se cochent, célébrations (confetti déjà présent). Jamais ennuyeux.
2. **Surprend par ses connaissances** — afficher explicitement les 10+ data points auto-détectés (SIRET, APE, zone, surface IGN, cadastre, DPE, tranche effectifs) avec leurs sources visibles. Le wow ne doit pas s'arrêter au premier coup.
3. **Anticipation** — le système pré-calcule et pré-suggère avant que l'utilisateur demande. Les CTA disent ce qu'il y a après ("Continuer → voir mes 8 gisements", pas "Continuer").
4. **Précision** — chiffres exacts, sources tracées. Estimation labellée "estimation" avec range quand précision non atteignable.
5. **Vérité** — **JAMAIS de fake data**. Pas de compteur social inventé ("47K€ analysés aujourd'hui"), pas de prime affichée sans source calculable, pas de badge "détecté" si la donnée manque. Si la donnée n'est pas là, le badge n'apparaît pas. Silence plutôt que mensonge.

**Why :** Jimmy ("ludique qui surprend par ses connaissances et son anticipation précision vérité") vend un outil PRO. La crédibilité du diagnostic = bascule entre closing et rejet. Un fake counter flashy = perte de confiance immédiate du prospect pro. À l'inverse, afficher "280 m² · source IGN BDNB" ouvertement = crédibilité max.

**How to apply :**
- Avant toute animation / chip / célébration : vérifier que la donnée est réelle (STATE.diagnostic.X !== undefined / null / '')
- Préfixer les estimations par label + range ("~8 200 € · estimation large" plutôt que "8 200 €")
- Afficher la source de chaque data visible (badge suffix : "· IGN", "· INSEE", "· cadastre")
- Si une source API échoue, NE PAS fabriquer de fallback qui ressemble à du vrai
- Les CTA doivent anticiper ce qu'il y a après ("→ voir mes N gisements" avec N dynamique)
- Les 4 piliers sont liés — ludique SANS vérité = clownesque ; précision SANS ludique = froid.
