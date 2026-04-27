#!/usr/bin/env bash
#
# V37.1.1 — Rotation orchestrée des 6 clés compromises + push Fly secrets + smoke + cleanup.
# Conçu pour t'éviter le copy-paste manuel : ouvre les URLs, demande la valeur, push à Fly, vérifie.
#
# Usage :
#   ./scripts/rotate_keys.sh
#
# Pré-requis (déjà OK sur ta machine au 2026-04-27) :
#   - flyctl installé + fly auth login fait (gmeet.mameilleureenergie@gmail.com)
#   - openssl, curl
#

set -u
APP="cee-engine-v37"
HOST="https://${APP}.fly.dev"
RECOVERED_FILE="${HOME}/.cee_keys_recovered_2026-04-27.txt"

green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }
ylw()   { printf "\033[33m%s\033[0m\n" "$*"; }
cyan()  { printf "\033[36m%s\033[0m\n" "$*"; }

cyan "════════════════════════════════════════════════════════════"
cyan " CEE Engine V37.1.1 — Rotation des 6 clés compromises"
cyan "════════════════════════════════════════════════════════════"
echo
ylw "Pour chaque provider, ce script va :"
echo "  1. Ouvrir l'URL de gestion des clés dans ton browser"
echo "  2. Te demander de copier la NOUVELLE clé (révoque l'ancienne, génère une nouvelle, copie)"
echo "  3. Pousser la valeur sur Fly secrets (déclenche redeploy auto)"
echo "  4. Passer au suivant"
echo
read -rp "Prêt ? [y/N] " ok
[[ "${ok,,}" == "y" ]] || { red "Aborté."; exit 1; }
echo

# Liste des clés à rotater : nom_secret_fly | URL provider | label
ROTATIONS=(
  "ANTHROPIC_API_KEY|https://console.anthropic.com/settings/keys|Anthropic Console"
  "OPENAI_API_KEY|https://platform.openai.com/api-keys|OpenAI Platform"
  "GROQ_API_KEY|https://console.groq.com/keys|Groq Console"
  "GEMINI_API_KEY|https://aistudio.google.com/app/apikey|Google AI Studio (Gemini)"
  "MOONSHOT_API_KEY|https://platform.moonshot.cn/console/api-keys|Moonshot Platform (Kimi)"
  "MONDAY_API_TOKEN|https://wcspro.monday.com/admin/integrations/api|Monday Admin"
)

ROTATED=()
SKIPPED=()

for row in "${ROTATIONS[@]}"; do
  IFS='|' read -r KEY URL LABEL <<< "$row"
  echo
  cyan "━━ $LABEL ━━"
  echo "  Secret Fly  : $KEY"
  echo "  URL         : $URL"
  echo
  read -rp "Ouvrir $LABEL dans ton browser ? [y/skip/q] " act
  case "${act,,}" in
    q) red "Arrêt utilisateur."; break;;
    skip|s) ylw "  ⊘ skipé"; SKIPPED+=("$KEY"); continue;;
    *) open "$URL" 2>/dev/null || ylw "  (open a échoué — copie l'URL manuellement)";;
  esac
  echo
  echo "  → Révoque l'ANCIENNE clé chez $LABEL"
  echo "  → Génère la NOUVELLE clé"
  echo "  → Copie-la"
  echo
  read -rsp "Colle la nouvelle valeur ici (input masqué) : " NEW_VAL
  echo
  if [[ -z "$NEW_VAL" ]]; then
    ylw "  ⊘ valeur vide, skipé"
    SKIPPED+=("$KEY")
    continue
  fi
  if [[ ${#NEW_VAL} -lt 20 ]]; then
    red "  ⚠ valeur trop courte (${#NEW_VAL} chars). Confirme ? [y/N] "
    read -r conf
    [[ "${conf,,}" == "y" ]] || { ylw "  ⊘ skipé"; SKIPPED+=("$KEY"); continue; }
  fi
  echo
  echo "  Push sur Fly secrets..."
  if fly secrets set "${KEY}=${NEW_VAL}" --stage --app "$APP" >/dev/null 2>&1; then
    green "  ✓ $KEY staged sur Fly"
    ROTATED+=("$KEY")
  else
    red "  ✗ fly secrets set a échoué pour $KEY"
    SKIPPED+=("$KEY (FAIL)")
  fi
  unset NEW_VAL
done

# Internes V37.1 (au cas où non encore set, ou si on veut tout rotater)
echo
read -rp "Régénérer aussi les 4 secrets internes (CEE_JWT_SECRET, CEE_DOSSIERS_SECRET, CEE_CONFORMITE_SECRET, MONDAY_WEBHOOK_SECRET) ? [y/N] " regen
if [[ "${regen,,}" == "y" ]]; then
  ylw "  ⚠ Si MONDAY_WEBHOOK_SECRET change, le webhook id 166166984 doit être recréé avec le nouveau token URL"
  fly secrets set \
    CEE_JWT_SECRET="$(openssl rand -hex 32)" \
    CEE_DOSSIERS_SECRET="$(openssl rand -hex 32)" \
    CEE_CONFORMITE_SECRET="$(openssl rand -hex 32)" \
    --stage --app "$APP" >/dev/null 2>&1 \
    && green "  ✓ 3 secrets internes régénérés (JWT/DOSSIERS/CONFORMITE)" \
    || red "  ✗ régen secrets internes a échoué"
  ROTATED+=("CEE_JWT_SECRET" "CEE_DOSSIERS_SECRET" "CEE_CONFORMITE_SECRET")
fi

# Apply staged + redeploy
echo
echo "════════════════════════════════════════════════════════════"
if [[ ${#ROTATED[@]} -gt 0 ]]; then
  cyan "Rotation effectuée pour : ${ROTATED[*]}"
  echo
  read -rp "Lancer le redeploy maintenant pour appliquer ? [y/N] " dep
  if [[ "${dep,,}" == "y" ]]; then
    fly deploy --app "$APP" 2>&1 | tail -8
  else
    ylw "Secrets staged. Lance manuellement : fly deploy --app $APP"
  fi
else
  ylw "Aucune rotation effectuée."
fi

if [[ ${#SKIPPED[@]} -gt 0 ]]; then
  ylw "Skipés : ${SKIPPED[*]}"
fi

echo
echo "════════════════════════════════════════════════════════════"
read -rp "Lancer le smoke test post-rotation ? [Y/n] " sm
if [[ "${sm,,}" != "n" ]]; then
  ./scripts/smoke.sh "$HOST" || red "Smoke test KO"
fi

# Cleanup
if [[ ${#ROTATED[@]} -ge 6 ]] && [[ -f "$RECOVERED_FILE" ]]; then
  echo
  read -rp "Détruire $RECOVERED_FILE (les anciennes clés ne servent plus) ? [Y/n] " dest
  if [[ "${dest,,}" != "n" ]]; then
    if command -v shred >/dev/null; then
      shred -u "$RECOVERED_FILE" && green "✓ $RECOVERED_FILE shredded"
    else
      rm -P "$RECOVERED_FILE" 2>/dev/null && green "✓ $RECOVERED_FILE rm -P"
    fi
  fi
fi

echo
green "════════════════════════════════════════════════════════════"
green " Rotation terminée."
green "════════════════════════════════════════════════════════════"
