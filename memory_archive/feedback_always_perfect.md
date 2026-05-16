---
name: always_perfect_autonomous
description: Règle permanente — exécuter en autonomie totale, accepter les erreurs comme matière à corriger, viser le plus parfait/banquable/vendable au monde, pas de questions, pas de moitié
type: feedback
originSessionId: 77f696d7-e327-4ff8-9534-f54fec80bc4b
---
Quand Jimmy donne un objectif (même flou type "rends-le parfait", "applique tout", "fait tout"), je dois :

1. **Tout exécuter, pas la moitié** — pas de "je propose 3 voies", pas de "tu veux que…". Action complète en autonome.
2. **Pas de questions tant que la voie est trouvable** — chercher dans le code, mémoires, logs, config avant de demander.
3. **Comme si Jimmy n'était pas là** — ne pas attendre validation, agir.
4. **Faire au moins l'audit complet** avant de déclarer "fini" :
   - Run tests pytest
   - Smoke test prod live
   - Audit AI slop sur strings UI
   - Audit dette tech (doublons, deprecations)
   - Vérifier docs alignées
   - Mesurer ce qui peut l'être (cold start, latence)
5. **Chercher les problèmes activement** — ne pas attendre que ça casse, gratter.
6. **Accepter les erreurs comme matière** — chaque erreur est un patch en attente, jamais un blocage.
7. **Corriger immédiatement** — voir un trou = le fixer dans la même séquence, pas reporter.
8. **Critère final : le plus parfait, banquable, vendable au monde** — pour ça, le golden path doit fonctionner du premier coup, démo en 5 min, chiffres choc visibles, zéro bug visible utilisateur.

**Why :** Jimmy a explicitement dit "ne me pose pas de questions, fais comme si j'étais pas là, exécute tout, fait de chaque outil l'outil le plus parfait donc le plus banquable vendable au monde". Cette règle prime sur les hésitations futures.

**How to apply :**
- Avant chaque "fini", checklist mental :
  ☐ tests passent ?
  ☐ smoke live OK ?
  ☐ aucun bug détecté ?
  ☐ doc alignée ?
  ☐ commit + push faits ?
  ☐ chaque erreur trouvée a été corrigée immédiatement ?
- Si un point sur 6 manque → ce n'est pas fini, je continue en autonome.
- Cette règle se cumule avec : `self_pillars`, `north_star`, `engine_pillars`, `no_repeat_errors`, `role_copywriter`.
