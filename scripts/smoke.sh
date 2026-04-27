#!/usr/bin/env bash
#
# V37.1 — Smoke test live post-deploy CEE Engine.
# Vérifie que les endpoints critiques répondent correctement en prod.
#
# Usage :
#   ./scripts/smoke.sh                                  # cible https://cee-engine-v37.fly.dev
#   ./scripts/smoke.sh http://localhost:5001            # ciblage local pour debug
#   CEE_BEARER_TOKEN=eyJ... ./scripts/smoke.sh         # tests endpoints authentifiés
#
# Critère succès : tous les checks PASS, aucun FAIL.
#

set -u
HOST="${1:-https://cee-engine-v37.fly.dev}"
BEARER="${CEE_BEARER_TOKEN:-}"
PASS=0
FAIL=0
FAILURES=()

green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }
ylw()   { printf "\033[33m%s\033[0m\n" "$*"; }

check() {
  local label="$1" expected="$2" got="$3"
  if [[ "$got" == "$expected" ]]; then
    green "  ✓ $label (HTTP $got)"
    PASS=$((PASS+1))
  else
    red "  ✗ $label (attendu $expected, obtenu $got)"
    FAIL=$((FAIL+1))
    FAILURES+=("$label")
  fi
}

echo "=========================================="
echo " CEE Engine smoke test"
echo " Host: $HOST"
echo " Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=========================================="

# 1. Health/index — doit répondre
echo
echo "--- 1. Endpoints publics ---"
status=$(curl -s -o /dev/null -w "%{http_code}" "$HOST/")
check "GET / (oracle.html)" "200" "$status"

status=$(curl -s -o /dev/null -w "%{http_code}" "$HOST/auth/status")
check "GET /auth/status" "200" "$status"

# 2. CORS strict — origin malicious doit être refusé
echo
echo "--- 2. CORS allowlist (sécu) ---"
ALLOW_HEADER=$(curl -s -D - -o /dev/null \
  -H "Origin: https://malicious.example.com" \
  "$HOST/auth/status" | grep -i "access-control-allow-origin" || echo "absent")
if [[ "$ALLOW_HEADER" == *"malicious"* ]]; then
  red "  ✗ CORS leak — Origin malicious autorisé : $ALLOW_HEADER"
  FAIL=$((FAIL+1)); FAILURES+=("CORS allow malicious")
else
  green "  ✓ Origin malicious non listé dans Allow-Origin"
  PASS=$((PASS+1))
fi

# 3. /ai/* origin guard
echo
echo "--- 3. Origin guard /ai/* (sécu critique) ---"
status=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$HOST/ai/groq" \
  -H "Origin: https://malicious.example.com" \
  -H "Content-Type: application/json" \
  -d '{"messages":[]}')
check "POST /ai/groq Origin malicious → 403" "403" "$status"

# 4. JWT secret strength (boot guard) — auth/status doit dire auth_enabled=true
echo
echo "--- 4. JWT secret en place ---"
auth_enabled=$(curl -s "$HOST/auth/status" | grep -o '"auth_enabled":[^,}]*' | cut -d: -f2 | tr -d ' "')
if [[ "$auth_enabled" == "true" ]]; then
  green "  ✓ auth_enabled=true (CEE_JWT_SECRET configuré côté serveur)"
  PASS=$((PASS+1))
else
  red "  ✗ auth_enabled=$auth_enabled — CEE_JWT_SECRET manquant ou serveur down"
  FAIL=$((FAIL+1)); FAILURES+=("JWT_SECRET")
fi

# 5. Headers de sécurité
echo
echo "--- 5. Security headers ---"
HEADERS=$(curl -s -D - -o /dev/null "$HOST/")
for h in "x-content-type-options" "x-frame-options" "referrer-policy"; do
  if echo "$HEADERS" | grep -qi "^$h:"; then
    green "  ✓ Header $h présent"
    PASS=$((PASS+1))
  else
    ylw "  ⚠ Header $h manquant"
    # Non-bloquant
  fi
done

# 6. Tunnel V37.1 — endpoint disponible
echo
echo "--- 6. Tunnel commercial V37.1 ---"
status=$(curl -s -o /dev/null -w "%{http_code}" "$HOST/tunnel")
check "GET /tunnel (liste)" "200" "$status"

status=$(curl -s -o /dev/null -w "%{http_code}" "$HOST/analytics/sales-velocity")
check "GET /analytics/sales-velocity" "200" "$status"

# 7. Webhook Monday : sans signature en prod → 503 (fail-secure)
echo
echo "--- 7. Webhook Monday HMAC ---"
status=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$HOST/monday/webhook" \
  -H "Content-Type: application/json" \
  -d '{"challenge":"test"}')
if [[ "$status" == "200" ]]; then
  green "  ✓ Webhook répond 200 (challenge OK ou MONDAY_WEBHOOK_SECRET non configuré en dev)"
  PASS=$((PASS+1))
elif [[ "$status" == "503" ]]; then
  green "  ✓ Webhook 503 fail-secure (MONDAY_WEBHOOK_SECRET requis en prod)"
  PASS=$((PASS+1))
elif [[ "$status" == "403" ]]; then
  green "  ✓ Webhook 403 (signature attendue)"
  PASS=$((PASS+1))
else
  red "  ✗ Webhook réponse inattendue : $status"
  FAIL=$((FAIL+1)); FAILURES+=("monday webhook")
fi

# 8. AHBFC dossier accessible (si endpoint existe et auth OK)
if [[ -n "$BEARER" ]]; then
  echo
  echo "--- 8. AHBFC dossier (avec token) ---"
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $BEARER" \
    "$HOST/post-signature/ahbfc-magritte")
  check "GET /post-signature/ahbfc-magritte" "200" "$status"
fi

echo
echo "=========================================="
echo " RÉSULTAT"
echo "=========================================="
if [[ $FAIL -eq 0 ]]; then
  green " ✓ $PASS / $((PASS+FAIL)) checks PASS — déploiement vert"
  exit 0
else
  red " ✗ $FAIL FAIL sur $((PASS+FAIL)) checks"
  echo
  red " Échecs :"
  for f in "${FAILURES[@]}"; do
    red "   - $f"
  done
  echo
  ylw " Investiguer :"
  ylw "   fly logs --app cee-engine-v37 | tail -50"
  ylw "   fly secrets list --app cee-engine-v37"
  exit 1
fi
