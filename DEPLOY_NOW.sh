#!/bin/bash
cd "$(dirname "$0")"
echo "1/3 — Connexion Railway..."
railway login
echo "2/3 — Liaison projet..."
railway link  
echo "3/3 — Déploiement..."
railway up --detach
echo ""
echo "✅ Déployé ! Exécuter:"
echo "  railway domain  → obtenir l'URL publique"
echo "  railway logs    → voir les logs"
