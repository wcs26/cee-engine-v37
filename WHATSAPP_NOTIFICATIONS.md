# Notifications WhatsApp — recevoir un message à chaque inscription

> CEE Engine V37.3.37 supporte **3 méthodes WhatsApp** pour notifier l'admin
> des nouveaux comptes en attente. Choisis selon ton besoin.

## 🎯 Recommandation rapide

| Profil Jimmy | Méthode | Coût | Mise en place |
|---|---|---|---|
| Démarrage solo, MVP, juste pour soi | **A — CallMeBot** | **0 €** | 5 min |
| Production sérieuse, plusieurs admin | **C — Meta Cloud API officielle** | **0 €** (< 1000 conv/mois) | 30 min |
| Volume élevé + intégration entreprise | **B — Twilio** | ~5 €/mois en prod | 15 min |

→ **Pour toi maintenant : option A (CallMeBot)** — 100 % gratuit, marche en 5 min depuis le Cambodge.

---

## A — CallMeBot (gratuit, MVP)

**Limites** : service tiers non officiel maintenu par un dev espagnol, pas de garantie SLA. Idéal pour notifications perso, pas pour business critique.

### Setup (5 min)

1. **Sur ton téléphone Cambodge**, ouvre WhatsApp
2. Ajoute le contact **+34 644 51 95 23** (n° WhatsApp du bot CallMeBot)
3. Envoie-lui le message exact :
   ```
   I allow callmebot to send me messages
   ```
4. Tu reçois une réponse automatique avec ton **API key** (chaîne ~10 chars)
5. Note ton numéro WhatsApp avec indicatif (ex: `+855 12 345 678`)
6. Configure les secrets Fly :
   ```bash
   fly secrets set CEE_WA_CALLMEBOT_PHONE="+85512345678" \
                   CEE_WA_CALLMEBOT_APIKEY="ta_apikey_recue" \
                   --app cee-engine-v37
   ```
   (ne mets PAS d'espace dans le numéro)

### Test
1. Ouvre la session incognito → crée un compte test sur cee-engine-v37.fly.dev
2. Quelques secondes plus tard → tu reçois le message WhatsApp sur ton téléphone

---

## B — Twilio (pro, payant)

### Setup Sandbox (gratuit pour tests)

1. Crée un compte sur https://www.twilio.com/try-twilio (gratuit)
2. Va sur **Messaging → Try it out → Send a WhatsApp message**
3. Tu vois un numéro Twilio sandbox (ex: `+1 415 523 8886`) + un code (ex: `join silver-knight`)
4. Sur ton WhatsApp, envoie ce code au numéro Twilio → ton numéro est connecté au sandbox
5. Récupère depuis le dashboard :
   - **Account SID** (commence par `AC...`)
   - **Auth Token** (sous la SID, clic révéler)

### Configuration Fly

```bash
fly secrets set CEE_WA_TWILIO_SID="ACxxxxxxxxxxxxxxxxxx" \
                CEE_WA_TWILIO_TOKEN="yyyyyyyyyyyyyyyyy" \
                CEE_WA_TWILIO_FROM="whatsapp:+14155238886" \
                CEE_WA_TO="whatsapp:+85512345678" \
                --app cee-engine-v37
```

(remplace `+85512345678` par ton vrai numéro Cambodge avec indicatif)

### Production (payant)
Pour utiliser ton propre numéro WhatsApp Business (sans sandbox) :
1. Vérification Meta Business Manager
2. Achat d'un numéro WhatsApp Business via Twilio (~5 € setup, 0,005 €/msg)
3. Délais administratifs Meta : 1-3 semaines

---

## C — Meta WhatsApp Cloud API (officielle, gratuit)

**Le plus pro et durable** — API officielle Meta, gratuit jusqu'à 1000 conversations/mois.

### Setup (30 min)

1. Crée un compte développeur Meta : https://developers.facebook.com/
2. Crée une app type "Business" → ajoute le produit **WhatsApp**
3. Dans WhatsApp → API Setup, Meta te fournit gratuitement :
   - Un **numéro de test** (ex: `+1 555 010 1234`)
   - Un **Phone Number ID** (chiffres)
   - Un **token temporaire** (24h, à renouveler)
4. Ajoute ton numéro Cambodge dans la liste **"To" recipient phone numbers** (max 5 en gratuit)
5. Tu reçois un code SMS sur Cambodge → entre le code dans Meta pour valider
6. Configure les secrets Fly :
   ```bash
   fly secrets set CEE_WA_META_PHONE_ID="123456789012345" \
                   CEE_WA_META_TOKEN="EAAxxxxxxxxxxxx" \
                   CEE_WA_TO="+85512345678" \
                   --app cee-engine-v37
   ```

### Token permanent (recommandé)
Le token initial expire en 24h. Pour un token permanent :
1. Meta Business Manager → System Users → créer un user système
2. Donner accès "WhatsApp Business" à cet user
3. Générer un token avec `whatsapp_business_messaging` scope, expiration "Never"
4. Remplace `CEE_WA_META_TOKEN` avec ce token permanent

---

## Tester les 3 modes en local (sans Fly)

```bash
export CEE_WA_CALLMEBOT_PHONE="+85512345678"
export CEE_WA_CALLMEBOT_APIKEY="xxxxxxxxxx"
python3 -c "
import logging; logging.basicConfig(level=logging.INFO)
from auth import _send_whatsapp_notification
_send_whatsapp_notification('Test CEE Engine V37.3.37', {'email':'test@x.fr','name':'Test'}, logging.getLogger())
"
```

Tu dois recevoir le message sur ton WhatsApp.

## Diagnostic en prod

Si tu reçois rien après une inscription :
```bash
fly logs --app cee-engine-v37 | grep -i "whatsapp\|callmebot\|twilio\|meta"
```

Tu verras :
- `whatsapp callmebot sent to +855...` ✅
- `whatsapp callmebot err: ...` ❌ avec raison

## Ordre de priorité interne

Le code essaie dans l'ordre A → B → C. Si A est configuré et marche, B/C ne sont pas appelés. Tu peux donc en avoir plusieurs configurés (failover).

Toutes les méthodes sont **best-effort** : si la notif échoue, le compte est quand même créé en pending et apparaît dans le panel admin (cf `/admin/users/pending`). Tu ne rates jamais un signup, juste la notif push.

---

*Document V37.3.37 · WhatsApp natif sans dépendance Python externe (urllib seulement).*
