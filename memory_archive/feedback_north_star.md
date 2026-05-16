---
name: north_star
description: Boussole projet CEE Engine — toujours filtrer chaque action par "sert-elle la volonté principale du projet ?" Mécanique cible : simple + juste + vérifiée + intelligente + prédictive
type: feedback
originSessionId: 77f696d7-e327-4ff8-9534-f54fec80bc4b
---
**Volonté principale du projet** (énoncée par Jimmy) : CEE Engine doit être l'outil de diagnostic CEE le plus complet du marché, **PRO uniquement**, avec une mécanique :
- **Simple** — un dossier facile reste facile à l'écran ; pas de questionnaire déroulé d'un coup (cf. `engine_ux_suggestions`)
- **Juste / fair** — chiffres réels, jamais inventés (cf. `engine_pillars` → vérité)
- **Vérifiée** — chaque donnée affichée porte sa source visible (`· INSEE`, `· IGN BD TOPO`, `· cadastre`)
- **Intelligente** — auto-détection multi-sources (10+ data points depuis SIRET seul), inférence APE→secteur CEE, top 3 fiches par impact
- **Prédictive** — anticipe la prochaine action ("Continuer → voir mes 8 gisements"), pré-calcule avant que l'utilisateur demande, alerte sur abrogation à venir

**Why :** Jimmy a explicitement demandé "toujours chercher la volonté principale du projet et trouver sa mécanique parfaite simple juste vérifiée intelligente prédictive". C'est une boussole pour TOUTES les décisions techniques et UX, pas une simple liste de qualités.

**How to apply :**
- Avant tout patch / agent / install / refacto : passer par le filtre "ça simplifie ? ça reste juste ? c'est vérifiable ? c'est plus intelligent ? c'est plus prédictif ?". Si la réponse est non sur 3 axes → ne pas faire.
- Toute fonctionnalité ajoutée doit surfacer **proactivement** ce qu'elle sait, sans attendre que l'utilisateur cherche.
- Toute donnée affichée doit être traçable à sa source en un coup d'œil.
- Tout flow = chemin court par défaut + optionnel pour aller plus loin (jamais l'inverse).
- Cette règle se cumule avec `engine_pillars` (ludique + connaissances + anticipation + précision + vérité) — ce sont les MÊMES qualités exprimées sous deux angles, à appliquer ensemble.
