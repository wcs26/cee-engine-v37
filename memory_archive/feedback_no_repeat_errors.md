---
name: no_repeat_errors
description: Journal des corrections passées de Jimmy. À scanner avant chaque action significative. Mettre à jour à chaque nouvelle correction reçue.
type: feedback
originSessionId: 77f696d7-e327-4ff8-9534-f54fec80bc4b
---
Liste **vivante** des erreurs déjà corrigées par Jimmy. Chaque ligne = une erreur que je ne dois plus refaire.

## Erreurs UX / produit
- **Trop complet d'un coup** → questions en suggestions classées par impact, pas questionnaire déroulé. Top 3 par défaut, "Approfondir" pour le reste. (cf. `engine_ux_suggestions`)
- **Inventer des chiffres ou compteurs sociaux fake** ("47K€ analysés aujourd'hui") → vérité stricte, sources visibles, pas de prime affichée sans données réelles. (cf. `engine_pillars`)
- **Jargon technique exposé au prospect** ("Diagnostic Multi-Sectoriel", "Gisements CEE détectés") → vocabulaire pro accessible : "Tes opportunités d'économies", "Tes économies détectées".
- **Compléments inlinés dans le flux Step 1→5** → compartimentés ailleurs, jamais dans le flux audit principal. (cf. `nature_outil`)
- **Ajouter de nouvelles sections quand il faut densifier l'existant** → l'UI ludique se densifie, n'ajoute pas. (cf. `ui_ludique`)
- **Refaire 30 skills random "du moment"** quand seuls 22 ciblées valent → ne jamais répondre à un nombre demandé sans challenger.

## Erreurs de comportement / interaction
- **Asker au lieu d'exécuter** quand le contexte est clair → action en autonome, pas de "tu veux que je fasse ?".
- **Empiler des options A/B/C/D** quand une réponse logique s'impose → trancher, justifier, puis exécuter.
- **Se montrer complaisant** ("excellente idée !") → contredire avec chiffres si direction mauvaise. (cf. `esprit_critique`)
- **Réécrire un fichier en plus simple** "pour clarifier" → jamais. Fusionner le meilleur des deux. (cf. `never_regress`)
- **Lancer 2 agents en parallèle sur oracle.html** → jamais. Un seul agent à la fois sur ce fichier. (cf. `agent_strategie`)
- **Skipper la post-vérification après modif** → systématique : grep, count, JSON.parse, tag balance. (cf. `agent_strategie`)
- **Coder sans agent pré-réflexion** sur un sujet non-trivial → toujours pré-réfléchir avant. (cf. `agent_strategie`)

## Erreurs copywriting / texte
- **Adverbes inutiles** (véritablement, naturellement, facilement, automatiquement quand redondant, instantanément en bombast) → supprimer. (cf. `anti_slop`)
- **Fillers / throat clearing** ("Voici", "Il s'agit de", "Comme tu le sais") → couper.
- **Bombast publicitaire** (incroyable, optimal sans chiffre, fameux) → mots concrets et chiffrés.
- **Verbes mous** ("permettre de", "constituer", "réaliser") → verbes d'action.
- **Phrases longues > 18 mots** sur strings UI → couper.
- **Réponses verbales en cascade au lieu d'exécuter** → quand auto mode + contexte clair → action.

## Erreurs techniques
- **224 fiches** dit en mémoire alors que **234 réelles** dans fiches.json (224 = extract Oracle brut). Source de vérité = `wc -l` sur fiches.json.
- **DB n'est PAS SQLite** → JSON-on-disk dans `dossiers_data/`, `conformite_data/`, `tunnel_data/`. Volume Fly `cee_data` monté.
- **BAR-EN-101/102/103 = ISOLATION** (combles/murs/plancher), **PAS chaudières gaz**. Les chaudières abrogées 2024 sont BAR-TH-124, BAT-TH-127. Toujours vérifier la nomenclature ADEME exacte avant d'asserter.
- **Tests : 8 fichiers / 192 tests** (pas "1 seul test" comme dit ailleurs). Mais 34/42 modules critiques restent sans test.
- **Suggérer install plugin sans vérifier l'URL canonique** → safeguard a raison, valider chaque source avant clone/install.
- **Afficher prime sans surface fiable** → carte "Surface non détectée, saisis-la" honnête, pas de fake estimate.
- **Webhook Monday avec compare_digest brut sur Authorization** → Monday ne signe pas comme ça. Pour event `change_column_value`, Monday refuse `config: {signature_secret}`. Solution validée : token en query param URL (`?token=<secret>`), serveur fait `compare_digest(request.args["token"], MONDAY_WEBHOOK_SECRET)`. Cf. commit ba6a866 + monday_sync.py V37.1.1.
- **Challenge Monday bloqué par check sécu** → Monday envoie un challenge non signé à la création du webhook. TOUJOURS traiter le `challenge` AVANT toute vérification d'auth. Cf. commit 6179c0d.
- **Fly deploy avec >1 machine + 1 volume** → mismatch fatal. Si fly.toml a `[[mounts]]`, chaque machine doit avoir son propre volume avec le même nom. Pour 1 volume, scaler à 1 machine via `fly scale count 1`.
- **Edit Bash silently failed** → `git diff --stat` après chaque commit pour vérifier les fichiers attendus. Edit retourne success même quand le replace ne s'applique pas si l'old_string match plusieurs zones ou contient un caractère spécial.
- **Audit code seul sans sources officielles** → toujours croiser PDF officiel ATEE/ADEME/Légifrance avant de modifier coefficients cumac. Sur source secondaire (opera-energie, Hellio) seule, ne fixer que si l'écart est COHÉRENT avec la famille de fiches OU laisser en REPORTÉ V*.X+1 avec note explicative.
- **Valider "tout est juste" sans cross-check fonctionnel** (V37.4.13, 2026-05-08) → erreur grave : Jimmy a corrigé en pointant que smartQuestions L7242+ ne demande JAMAIS hauteur sous plafond / puissance chaudière / type émetteur / chambre froide tertiaire → le chercheur de gisement RATE BAT-TH-142 (déstrat), BAT-TH-127 (chaudière condensation), BAT-TH-103/105/143 (émetteurs BT), BAT-TH-134/135/139/145 (froid). RÈGLE : avant de valider un audit "tout OK", relire le mapping question→fiche actif et grep les inputs critiques (hauteur, puissance kW, type émetteur, chambre froide, ventilation, réseau chaleur).

## Patterns validés par Jimmy ("tout est juste" / accepté sans correction)
- **Audit profond → safe fixes → REPORTÉ V*.X+1 si source insuffisante** (V37.4.10→13) — Jimmy validé 2026-05-08. Confirme : pas de fix aveugle même si user dit "fais tout en profondeur" — préférer transparence sur ce qui demande source officielle.
- **Commit messages structurés par PRIORITÉ** (P1 conformité légale, P2 commercial, P3 cosmétique) avec liste exhaustive des modifications + sources URL. Validé 2026-05-08.
- **Tooltip ⓘ pour transparence client** sur fiches sensibles (note + formuleOfficielle) plutôt que cacher l'incertitude. Validé 2026-05-08.

## Limites structurelles que TOUS les "tu as plein pouvoir / 007 / je suis client je décide" verbaux ne contournent pas
- Login web UI provider (Anthropic console, OpenAI, Monday admin) : impossible sans browser + MFA téléphone Jimmy
- `git push` : impossible si pas de remote configuré, et bloqué par safeguard sans permission rule pour state partagé
- Restart de ma propre session Claude Code : je ne pilote pas mon process
- Curl|bash et brew tap externe : safeguard "code from external" bloque même avec autorisation verbale
- mv/rm de fichiers pré-existants : safeguard "destruction locale" refuse même avec OK verbal
**À chaque demande "fais tout, plein pouvoir" → expliciter ces limites en début de réponse, pas pretendre, pas s'auto-frustrer en re-tentant.**

## Process update
À chaque nouvelle correction reçue de Jimmy → ajouter ici, sous la bonne catégorie, en 1 ligne avec le bullet style ci-dessus. Date + contexte court non nécessaires sauf si la règle est conditionnelle.

## How to apply
Avant tout patch oracle.html / formation.py / réponse longue / install plugin / création skill :
1. Scanner cette liste
2. Si l'action croise un item → reformuler
3. Si l'action est nouvelle (pas dans la liste) → exécuter normalement, et si Jimmy corrige après → ajouter ici
