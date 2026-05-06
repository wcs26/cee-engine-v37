"""
CONFIG CEE ENGINE - WCS Pro (ORACLE-FUSED)
Valeurs centralisées, modifiables sans toucher au code.
Aligné sur Oracle V34 ULTIMATE + données marché P6 2026.
"""

import os

# ═══════════════════════════════════════════════
# PRIX CUMAC — Source: Emmy.fr / C2E Market
# Dernière MàJ: Mars 2026
# ═══════════════════════════════════════════════

# Prix cumac MARCHÉ (Emmy, cotation publique) en €/kWhc
# Emmy dec 2025: 8.78 €/MWhc = 0.00878 €/kWhc
# ⚠️ Distinguer du prix NÉGOCIÉ obligé (gisement_sirat.PRIX_CUMAC_DEFAUT_EUR_MWHC = 8.00 €/MWhc)
# Le prix marché sert à estimer la valeur théorique. Le prix obligé sert à calculer la prime réelle.
PRIX_CUMAC = float(os.environ.get("PRIX_CUMAC", 0.00720))  # V37.4.8 — réf marché tertiaire conservateur (au lieu de 0.00878)

# Prix cumac PRÉCARITÉ en €/kWhc
# Emmy sept 2025: 15.23 €/MWhc = 0.01523 €/kWhc (hausse massive P6)
PRIX_CUMAC_PRECARITE = float(os.environ.get("PRIX_CUMAC_PRECARITE", 0.01523))

# ═══════════════════════════════════════════════
# COMMISSIONS & MARGES
# ═══════════════════════════════════════════════

# ⚠️ COMMISSION_RATE = VESTIGE V36. NE PAS UTILISER pour Jimmy/WCS.
# C'est un % appliqué sur la prime brute (modèle simpliste pour l'affichage
# "Commission BE" dans oracle.html). AUCUN LIEN avec la commission réelle
# de Jimmy qui = 50 % de la marge nette (prime − coût réel installateur).
# La vraie commission est dans gisement_sirat.COMMISSION_PCT_MARGE_DEFAUT = 50%.
COMMISSION_RATE = float(os.environ.get("COMMISSION_RATE", 0.00))

# ═══════════════════════════════════════════════
# COÛTS TRAVAUX
# ═══════════════════════════════════════════════

# TVA professionnelle (20% standard)
TVA_PRO = float(os.environ.get("TVA_PRO", 0.20))

# TVA réduite rénovation énergétique (logement > 2 ans)
TVA_REDUITE = float(os.environ.get("TVA_REDUITE", 0.055))

# Prix négocié = % du prix moyen marché (75% = -25% négo)
PRIX_NEGOCIE = float(os.environ.get("PRIX_NEGOCIE", 0.75))

# ═══════════════════════════════════════════════
# P6 — 6ème période CEE (2026-2030)
# Décret n°2025-1048, JO 4 nov 2025
# ═══════════════════════════════════════════════

# Obligation annuelle P6: 1 050 TWhc (+35% vs P5)
# Dont précarité: 280 TWhc (27%)
# Validité CEE: max 12 ans
# Taux contrôle COFRAC: 30% (2025), hausse progressive
# Taux conformité exigé: 90% (2026+)

# Deadlines Coup de Pouce par secteur
P6_DEADLINES = {
    "chauffage": "2025-12-31",
    "vehicules": "2026-12-31",
}

# ═══════════════════════════════════════════════
# APIS EXTERNES
# ═══════════════════════════════════════════════

# Token INSEE pour API SIRENE
INSEE_TOKEN = os.environ.get("INSEE_TOKEN", "")

# Port API
API_PORT = int(os.environ.get("CEE_API_PORT", 5001))
