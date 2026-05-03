#!/usr/bin/env bash
# rotate_keys.sh — V37.3.49
# Aide-mémoire interactif pour la rotation des 6 clés API + APIFY_TOKEN.
#
# Pourquoi ce script existe : aucun de ces providers n'expose une API CRUD
# pour ses propres API tokens (mesure sécu universelle). La création passe
# obligatoirement par leur console web. Ce script automatise tout le reste :
# ouverture des URLs dans ton browser + commande fly pré-remplie pour chaque.
#
# Usage :
#   ./rotate_keys.sh                  # tout en mode interactif
#   ./rotate_keys.sh apify             # une seule clé
#   ./rotate_keys.sh anthropic openai  # un sous-ensemble
#
# Prérequis : Mac (open command), fly CLI authentifié (fly auth whoami).

set -e

APP="cee-engine-v37"

# Couleurs
B='\033[1m'; G='\033[32m'; Y='\033[33m'; R='\033[31m'; X='\033[0m'

echo -e "${B}═══════════════════════════════════════════════════════════════════════════${X}"
echo -e "${B}  CEE Engine — Rotation interactive des clés API${X}"
echo -e "${B}  App Fly cible : ${G}${APP}${X}"
echo -e "${B}═══════════════════════════════════════════════════════════════════════════${X}"
echo ""

# Vérif fly auth
if ! fly auth whoami >/dev/null 2>&1; then
  echo -e "${R}❌ fly CLI non authentifié.${X} Run : fly auth login"
  exit 1
fi
echo -e "${G}✓${X} fly CLI authentifié : $(fly auth whoami)"
echo ""

# Définition des 7 clés à roter : nom secret Fly + URL console + intitulé
declare -a KEYS=(
  "APIFY_TOKEN|https://console.apify.com/settings/integrations|Apify (Personal API tokens)"
  "ANTHROPIC_API_KEY|https://console.anthropic.com/settings/keys|Anthropic Claude (API keys)"
  "OPENAI_API_KEY|https://platform.openai.com/api-keys|OpenAI GPT (API keys)"
  "GROQ_API_KEY|https://console.groq.com/keys|Groq Llama (API keys)"
  "GEMINI_API_KEY|https://aistudio.google.com/app/apikey|Google Gemini (API keys)"
  "MOONSHOT_API_KEY|https://platform.moonshot.ai/console/api-keys|Moonshot Kimi (API keys)"
  "MONDAY_API_TOKEN|https://monday.com/admin/integrations/api|Monday.com (Personal API tokens)"
)

# Filtre par argument(s) CLI si fournis
SELECTED=()
if [ $# -gt 0 ]; then
  for arg in "$@"; do
    arg_upper=$(echo "$arg" | tr '[:lower:]' '[:upper:]')
    for k in "${KEYS[@]}"; do
      key_name=$(echo "$k" | cut -d'|' -f1)
      if [[ "$key_name" == *"$arg_upper"* ]]; then
        SELECTED+=("$k")
      fi
    done
  done
else
  SELECTED=("${KEYS[@]}")
fi

echo -e "${B}Plan${X} : ${#SELECTED[@]} clé(s) à roter."
echo ""

idx=0
for k in "${SELECTED[@]}"; do
  idx=$((idx + 1))
  name=$(echo "$k" | cut -d'|' -f1)
  url=$(echo "$k" | cut -d'|' -f2)
  label=$(echo "$k" | cut -d'|' -f3)

  echo -e "${B}[$idx/${#SELECTED[@]}] ${Y}${name}${X} — ${label}"
  echo -e "    Console : ${url}"
  echo ""
  read -p "  → Appuyer ENTER pour ouvrir la console et révoquer/créer la clé..." _
  open "$url"
  echo "  Console ouverte. Quand tu as la nouvelle clé en presse-papier (Cmd+C) :"
  echo ""
  read -s -p "  Colle la nouvelle valeur de ${name} (input masqué, ENTER pour valider) : " new_val
  echo ""
  if [ -z "$new_val" ]; then
    echo -e "  ${R}✗ Valeur vide, on saute cette clé.${X}"
    echo ""
    continue
  fi
  echo "  Pose dans Fly secrets..."
  if fly secrets set "${name}=${new_val}" --app "${APP}" >/dev/null 2>&1; then
    echo -e "  ${G}✓ ${name} mis à jour dans Fly. Machine redémarrée.${X}"
  else
    echo -e "  ${R}✗ Échec fly secrets set.${X} Lance manuellement :"
    echo -e "    ${Y}fly secrets set ${name}=\"<valeur>\" --app ${APP}${X}"
  fi
  unset new_val
  echo ""
done

echo -e "${B}═══════════════════════════════════════════════════════════════════════════${X}"
echo -e "${G}  ✓ Rotation terminée${X}"
echo -e "${B}═══════════════════════════════════════════════════════════════════════════${X}"
echo ""
echo "Vérification de l'état des secrets :"
fly secrets list --app "${APP}" 2>&1 | grep -E "$(IFS='|'; echo "${SELECTED[*]%%|*}" | tr ' ' '|')" || true
echo ""
echo "Test rapide /health post-rotation :"
curl -s -o /dev/null -w "  https://${APP}.fly.dev/health → HTTP %{http_code} en %{time_total}s\n" "https://${APP}.fly.dev/health"
echo ""
echo "Pour tester un endpoint qui consomme une clé (ex: Anthropic) :"
echo -e "  ${Y}curl https://${APP}.fly.dev/ai/claude -H 'Content-Type: application/json' \\${X}"
echo -e "  ${Y}  -d '{\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}]}'${X}"
