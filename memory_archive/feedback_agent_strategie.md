---
name: Agent stratégique — réflexion avant action
description: Toujours lancer un agent "pré-réflexion" avant de coder. Leçons des 18 agents lancés en 3 jours — volume sans qualité = régressions.
type: feedback
originSessionId: 2df11f34-7c9e-449e-84cf-ffec1837e5ed
---
**RÈGLE** : Avant chaque batch de travail, lancer un agent stratégique qui pense AVANT moi.

**Why** : En 3 jours, 18 agents ont produit beaucoup mais aussi causé 3 régressions majeures (clés IA écrasées 3×, surface_ratio oubliée, TVA résidentiel). Jimmy a dû signaler les mêmes bugs plusieurs fois. Inacceptable.

**How to apply** :

1. AVANT de modifier quoi que ce soit, lancer :
```
Agent "Pré-réflexion" :
- Quel est l'objectif exact ?
- Quels fichiers seront touchés ?
- Qu'est-ce qui peut casser ?
- Quel test vérifiera que ça marche ?
- Y a-t-il un conflit avec une modification récente ?
```

2. APRÈS chaque modification, lancer :
```
Agent "Post-vérification" :
- Les tests passent-ils tous ?
- Le calcul est-il cohérent frontend/backend ?
- Les 5 IA répondent-elles ?
- Le SIRET AHBFC (40039525700043) donne-t-il le bon résultat ?
```

3. JAMAIS annoncer "100%" sans avoir exécuté les 2 agents ci-dessus.

4. JAMAIS 2 agents sur oracle.html en parallèle.

5. 1 agent = 1 fichier = 1 responsabilité.
