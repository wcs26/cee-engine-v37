# Devenir contributeur RNB — procédure (~30 min, gratuit)

> Le RNB accepte les contributions externes pour signaler des erreurs sur
> les bâtiments (mauvaise géométrie, statut démoli, fusion/séparation).
> Pour CEE Engine, ça matérialise notre engagement dans l'écosystème +
> renforce la qualité des audits + crédibilité institutionnelle.

## ✅ État technique côté CEE Engine (déjà fait V37.3.31)

L'application est **déjà prête à utiliser un token RNB** :

- Variable d'environnement attendue : **`RNB_API_TOKEN`**
- Endpoints exposés :
  - `GET /rnb/status` — diagnostic (token configuré ou pas)
  - `POST /rnb/contribute` — signaler une anomalie
- Fonctions Python : `rnb_client.signal_anomalie()`, `is_contributeur_actif()`

Tant que `RNB_API_TOKEN` n'est pas défini, l'engine reste en **mode lecture
seule** (recherche d'ID-RNB possible, modification impossible) — comportement
sûr par défaut.

## 📋 Procédure d'inscription (à faire par toi, ~30 min)

### Étape 1 — Créer un compte RNB (5 min)
1. Aller sur https://rnb.beta.gouv.fr/login
2. "Créer un compte" → email + mot de passe
3. Validation email immédiate

### Étape 2 — Identifier la société (10 min)
Dans **Mon compte → Profil**, indiquer :
- Nom : **WCS Bulgaria EOOD**
- Activité : SaaS audit énergétique CEE / Référentiel multi-pays
- Site web : https://cee-engine-v37.fly.dev
- Adresse : 132 rue Mimi Balkanska, Sofia 1540, Bulgarie
- Représentant : Jimmy WILNER (gérant)

ℹ️ Le RNB accepte les sociétés étrangères qui contribuent à la qualité de la
donnée française. Aucune obligation de présence physique en France.

### Étape 3 — Générer un token API (5 min)
1. Aller dans **Mon compte → Mes Clés API**
2. "Générer une nouvelle clé" → donner un nom (ex: "CEE Engine prod")
3. **Copier le token immédiatement** (40 caractères hex, par exemple
   `9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b`)
4. Garder précieusement (le portail ne le réaffichera plus)

### Étape 4 — Configurer le token sur Fly.io (5 min)
Tu lances **toi-même** la commande suivante depuis ton terminal local
(ne JAMAIS poster ce token dans un chat) :

```bash
fly secrets set RNB_API_TOKEN="9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" \
  --app cee-engine-v37
```

Cela redémarre automatiquement l'app avec le token actif. ~30 sec.

### Étape 5 — Vérifier l'activation (2 min)
```bash
curl https://cee-engine-v37.fly.dev/rnb/status
```

Doit retourner :
```json
{
  "token_configured": true,
  "token_preview": "9944b0…ee4b",
  "mode": "contributeur",
  "doc": "https://rnb.beta.gouv.fr/login → Mon compte → Mes Clés API"
}
```

## 🛠️ Utilisation (après token configuré)

### Cas 1 — Signaler un bâtiment démoli pendant un audit terrain
```bash
curl -X POST https://cee-engine-v37.fly.dev/rnb/contribute \
  -H "Content-Type: application/json" \
  -d '{
    "rnb_id": "TSQCP5PA7KX8",
    "motif": "Démolition observée audit Memphis 2026-04-28",
    "comment": "Photo du chantier disponible · adresse 132 rue test 75001",
    "new_status": "demolished"
  }'
```

Statuts possibles :
- `constructed` — construit (par défaut)
- `demolished` — démoli
- `construction_in_progress` — chantier de construction
- `demolished_in_progress` — chantier de démolition

### Cas 2 — Simple commentaire sans changement de statut
```bash
curl -X POST https://cee-engine-v37.fly.dev/rnb/contribute \
  -H "Content-Type: application/json" \
  -d '{
    "rnb_id": "TSQCP5PA7KX8",
    "motif": "Adresse RNB obsolète",
    "comment": "Le bâtiment est référencé 132 rue X mais l'adresse réelle terrain est 134 rue X (audit Jimmy WCS Bulgaria)"
  }'
```

## 🚦 Quotas et limites RNB

- **20 requêtes/seconde** maximum (rate limit global)
- **500 opérations** initiales par utilisateur (évolutif après vérification
  par l'équipe RNB des premières contributions)
- Quota augmenté automatiquement si les contributions sont jugées de qualité

## 🎁 Bénéfices stratégiques pour CEE Engine

| Bénéfice | Impact |
|---|---|
| Reconnaissance par l'État comme acteur de l'écosystème bâti | Crédibilité institutionnelle |
| Trace publique des contributions → cas d'usage RNB référencé | Visibilité gratuite sur rnb.beta.gouv.fr |
| Qualité des audits améliorée par le feedback RNB | Moins d'erreurs métier |
| Argument pitch grands comptes : *"Nous contribuons activement au RNB"* | +5-10 % valorisation |
| Possibilité d'être consulté lors des prochains GT CNIG | Influence schéma de données |

## ⚠️ Bonnes pratiques

- **Ne JAMAIS poster le token dans un chat ou commit git** (utiliser Fly secrets)
- **Documenter chaque contribution** dans `comment` avec source audit + date
- **Préfixer commentaires** par `[CEE Engine WCS Bulgaria EOOD]` (déjà fait
  automatiquement dans `signal_anomalie()`)
- **Limiter à 1-2 contributions/jour au début** pour rester sous le radar
  du quota et avoir du feedback RNB

## 🔄 Si tu veux désactiver plus tard

```bash
fly secrets unset RNB_API_TOKEN --app cee-engine-v37
```

Cela retire le token et l'engine repasse automatiquement en mode lecture seule.

---

*Document V37.3.31 · Le code RNB contributeur est prêt côté CEE Engine. Il
suffit de générer un token + le configurer en variable d'env Fly.*
