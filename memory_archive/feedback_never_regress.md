---
name: never_regress
description: RÈGLE ABSOLUE - Ne jamais faire régresser l'outil, toujours améliorer, prendre le meilleur de tout
type: feedback
---

Ne JAMAIS écraser un fichier existant par une version plus simple. Toujours FUSIONNER en gardant le meilleur des deux.

**Why:** L'utilisateur a construit un système complexe incrémentalement. Chaque fichier contient des fonctionnalités critiques accumulées sur de nombreuses sessions. Un écrasement = perte de travail = perte de marché.

**How to apply:**
- Quand un nouveau code est proposé (cat > fichier.py), TOUJOURS lire l'existant d'abord
- Comparer les deux versions, identifier ce qui est NOUVEAU dans le code proposé
- FUSIONNER : ajouter les nouveautés dans l'existant sans supprimer les fonctionnalités en place
- Si le nouveau code est plus simple que l'existant → ne prendre que les éléments manquants
- Vérifier après fusion que tous les imports/appels existants fonctionnent encore
