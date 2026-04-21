#!/bin/bash
# CEE Engine V37 — Déploiement Railway en 1 commande
# Prérequis : railway login (fait une seule fois)

set -e

echo "═══════════════════════════════════════"
echo "  CEE ENGINE V37 — DÉPLOIEMENT RAILWAY"
echo "═══════════════════════════════════════"

# 1. Init Git si nécessaire
if [ ! -d .git ]; then
    echo "→ Initialisation Git..."
    git init
    echo ".env" >> .gitignore
    echo "__pycache__/" >> .gitignore
    echo "*.pyc" >> .gitignore
    echo "dossiers_data/" >> .gitignore
    echo "post_signature_data/" >> .gitignore
    echo "conformite_data/" >> .gitignore
    echo ".DS_Store" >> .gitignore
    git add -A
    git commit -m "CEE Engine V37 PRO — déploiement initial"
fi

# 2. Login Railway (ouvre le navigateur 1 seule fois)
railway whoami 2>/dev/null || railway login

# 3. Init projet Railway
railway init 2>/dev/null || true

# 4. Configurer les variables d'env depuis .env
echo "→ Configuration des variables..."
while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    [[ -z "$value" ]] && continue
    railway vars set "$key=$value" 2>/dev/null || true
done < .env

# 5. Déployer
echo "→ Déploiement en cours..."
railway up --detach

echo ""
echo "✅ Déploiement lancé !"
echo "→ railway open  (ouvrir dans le navigateur)"
echo "→ railway logs  (voir les logs)"
echo "→ railway domain (obtenir l'URL publique)"
