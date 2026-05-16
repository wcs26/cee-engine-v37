---
name: engine_ux_suggestions
description: Règle UX absolue de l'audit CEE Engine — questions en suggestions (pas questionnaire déroulé), simple reste simple, secondaire seulement si pertinent
type: feedback
originSessionId: 77f696d7-e327-4ff8-9534-f54fec80bc4b
---
Dans oracle.html / l'audit CEE Engine, les questions doivent **venir en suggestions** classées par impact, pas être déroulées d'un coup à l'utilisateur. Un dossier simple doit rester simple à l'écran. Le secondaire / l'avancé ne se révèle que si l'utilisateur clique "Approfondir" ou si le contexte le rend pertinent.

**Why :** Jimmy a explicitement reproché "tu prends la tête à quelqu'un de simple, t'es trop complet, les questions doivent venir en suggestions pas tout dérouler des le départ". Le commercial CEE doit pouvoir afficher un dossier rapidement sans noyer le client / le commercial sous 12 questions.

**How to apply :**
- Step 1 oracle.html : ne jamais montrer 11 champs d'un coup. SIRET seul → autodétection (APE, zone, surface IGN, DPE) → headline résumée immédiate avec prime estimée. Champs supplémentaires uniquement si Tier 0 incomplet.
- Step 2 / `renderQuestionnaire()` : ne sortir que **top 3 questions par impact cumac** + bouton "Approfondir (N autres)" pour révéler le reste.
- Step 4 : résultat = 3 lignes lisibles par défaut, détails repliés.
- Affichage dossier : résumé court d'abord, tableau complet seulement sur action utilisateur.
- Logique de tri des suggestions : `impact_€ = cumac × prix_MWh × proba_éligibilité`, déjà calculable via `naf-to-fiches` et `predict-elig` skills.

Cette règle prime sur "exhaustivité" — vaut aussi pour les explications/réponses moi → user (cf. critique "t es trop complet, fais pas un dossier simple lourd").
