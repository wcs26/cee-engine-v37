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
# V37.4.12 — Source : C2E Market relais Emmy. Moyenne pondérée Q1 2026 :
#   janv 9,07 / févr 8,96 / mars 9,02 / avril 8,97 → MOY 9,00 €/MWhc
# ⚠️ Distinguer du prix NÉGOCIÉ obligé (gisement_sirat.PRIX_CUMAC_DEFAUT_EUR_MWHC = 8.00 €/MWhc)
# Le prix marché sert à estimer la valeur théorique. Le prix obligé sert à calculer la prime réelle.
# Override possible via env var pour pitch conservateur (ex : PRIX_CUMAC=0.00720)
PRIX_CUMAC = float(os.environ.get("PRIX_CUMAC", 0.00900))  # V37.4.12 — Q1 2026 marché Emmy

# Prix cumac PRÉCARITÉ en €/kWhc
# V37.4.12 — Q1 2026 Emmy : janv 16,15 / févr 16,49 / mars 16,34 / avril 16,66 → MOY 16,40
PRIX_CUMAC_PRECARITE = float(os.environ.get("PRIX_CUMAC_PRECARITE", 0.01640))  # V37.4.12

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
# V37.4.11 — chauffage tertiaire prolongé par arrêté du 27/12/2025 :
# travaux engagés jusqu'au 31/12/2030, achevés au plus tard 31/12/2032.
# Source : JORF n°0301 du 28/12/2025, JORFTEXT000053202091
P6_DEADLINES = {
    "chauffage": "2030-12-31",  # ex 2025-12-31 (avant prolongation)
    "vehicules": "2026-12-31",  # à confirmer source officielle
}

# ═══════════════════════════════════════════════
# APIS EXTERNES
# ═══════════════════════════════════════════════

# Token INSEE pour API SIRENE
INSEE_TOKEN = os.environ.get("INSEE_TOKEN", "")

# Port API
API_PORT = int(os.environ.get("CEE_API_PORT", 5001))
