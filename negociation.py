"""
MOTEUR DE NÉGOCIATION CEE — Prix de rachat réel par acheteur
Sources: Emmy.fr, retours terrain délégataires, arrêtés P6

Le prix CUMAC dans config.py est le prix moyen marché.
Le prix RÉEL dépend de: l'acheteur, le volume, la qualité du dossier,
le secteur, le nombre de sites, et la période.

Ce module calcule la fourchette de rachat réelle.
"""

# ═══════════════════════════════════════════════
# ACHETEURS CEE — Prix et règles de tolérance
# Données: retours terrain + Emmy P6 T1 2026
# ═══════════════════════════════════════════════

# V36: Date de dernière mise à jour des prix acheteurs
PRIX_ACHETEURS_MAJ = "2026-04-11"  # IMPORTANT: mettre à jour quand les prix changent
PRIX_ACHETEURS_ALERTE_JOURS = 90   # Alerte si > 90 jours sans MAJ

ACHETEURS = {
    "EDF": {
        "nom": "EDF Obligation",
        "type": "oblige",
        "prix_classic_mwhc": 7.20,
        "prix_precarite_mwhc": 13.50,
        "tolerance": "strict",
        "multisite": False,
        "secteurs_ok": ["BAT", "BAR"],
        "mixite_ok": False,
        "exige_cofrac": False,
        "seuil_volume_min": 0,
        "bonus_volume_pct": 0,
        "malus_incomplet_pct": -30,
        "delai_paiement_jours": 90,
        "tolerance_surface_pct": 0.15,
        "tolerance_kwhc_pct": 0.12,
        "notes": "Tolérance élevée sur surface/kWhc mais strict sur secteurs et multi-sites.",
    },
    "Engie": {
        "nom": "Engie",
        "type": "oblige",
        "prix_classic_mwhc": 7.80,
        "prix_precarite_mwhc": 14.20,
        "tolerance": "mixte",
        "multisite": False,
        "secteurs_ok": ["BAT", "BAR", "IND"],
        "mixite_ok": True,             # Accepte mixte si gaz dominant
        "exige_cofrac": False,
        "seuil_volume_min": 0,
        "bonus_volume_pct": 5,         # +5% si > 1 GWhc
        "malus_incomplet_pct": -25,
        "delai_paiement_jours": 60,
        "notes": "Priorité aux opérations gaz (sortie fossile). Bonus si chauffage gaz remplacé.",
    },
    "TotalEnergies": {
        "nom": "TotalEnergies",
        "type": "oblige",
        "prix_classic_mwhc": 7.50,
        "prix_precarite_mwhc": 13.80,
        "tolerance": "mixte",
        "multisite": False,
        "secteurs_ok": ["BAT", "BAR", "IND", "TRA"],
        "mixite_ok": True,
        "exige_cofrac": False,
        "seuil_volume_min": 0,
        "bonus_volume_pct": 3,
        "malus_incomplet_pct": -20,
        "delai_paiement_jours": 75,
        "notes": "Multi-énergie. Accepte transport (TRA). Moins strict sur la mixité.",
    },
    "Delegataire_Premium": {
        "nom": "Délégataire spécialisé (type Soltri/Hellio)",
        "type": "delegataire",
        "prix_classic_mwhc": 10.20,
        "prix_precarite_mwhc": 16.80,
        "tolerance": "large",
        "multisite": True,             # Accepte multi-sites groupés
        "secteurs_ok": ["BAT", "BAR", "IND", "AGRI", "TRA", "RES"],
        "mixite_ok": True,
        "exige_cofrac": True,          # Exige COFRAC pour le premium
        "seuil_volume_min": 50_000_000,  # 50 GWhc minimum
        "bonus_volume_pct": 12,        # +12% si > 500 MkWhc
        "malus_incomplet_pct": -15,
        "delai_paiement_jours": 30,
        "notes": "Meilleur prix mais exige COFRAC. Accepte tous secteurs et multi-sites.",
    },
    "Delegataire_Standard": {
        "nom": "Délégataire standard (type Equans/Effy)",
        "type": "delegataire",
        "prix_classic_mwhc": 9.10,
        "prix_precarite_mwhc": 15.50,
        "tolerance": "large",
        "multisite": True,
        "secteurs_ok": ["BAT", "BAR", "IND"],
        "mixite_ok": True,
        "exige_cofrac": False,
        "seuil_volume_min": 20_000_000,
        "bonus_volume_pct": 8,
        "malus_incomplet_pct": -20,
        "delai_paiement_jours": 45,
        "notes": "Bon compromis prix/tolérance. Pas d'exigence COFRAC.",
    },
    "Mandataire": {
        "nom": "Mandataire (courtier CEE)",
        "type": "mandataire",
        "prix_classic_mwhc": 8.50,
        "prix_precarite_mwhc": 14.80,
        "tolerance": "large",
        "multisite": True,
        "secteurs_ok": ["BAT", "BAR", "IND", "AGRI", "TRA", "RES"],
        "mixite_ok": True,
        "exige_cofrac": False,
        "seuil_volume_min": 0,
        "bonus_volume_pct": 5,
        "malus_incomplet_pct": -10,
        "delai_paiement_jours": 60,
        "tolerance_surface_pct": 0.12,
        "tolerance_kwhc_pct": 0.10,
        "notes": "Flexibilité maximale. Prix intermédiaire. Gère l'administratif.",
    },
    "Cdiscount": {
        "nom": "Cdiscount Énergie",
        "type": "oblige",
        "prix_classic_mwhc": 8.80,
        "prix_precarite_mwhc": 15.00,
        "tolerance": "strict",
        "multisite": False,
        "secteurs_ok": ["BAT", "BAR"],
        "mixite_ok": False,
        "exige_cofrac": False,
        "seuil_volume_min": 0,
        "bonus_volume_pct": 0,
        "malus_incomplet_pct": -25,
        "delai_paiement_jours": 60,
        "tolerance_surface_pct": 0.08,
        "tolerance_kwhc_pct": 0.06,
        "notes": "Prix élevé mais tolérance très stricte et délai long.",
    },
    "Butagaz": {
        "nom": "Butagaz",
        "type": "oblige",
        "prix_classic_mwhc": 8.00,
        "prix_precarite_mwhc": 14.50,
        "tolerance": "mixte",
        "multisite": False,
        "secteurs_ok": ["BAT", "BAR", "IND"],
        "mixite_ok": True,
        "exige_cofrac": False,
        "seuil_volume_min": 0,
        "bonus_volume_pct": 3,
        "malus_incomplet_pct": -15,
        "delai_paiement_jours": 40,
        "tolerance_surface_pct": 0.12,
        "tolerance_kwhc_pct": 0.10,
        "notes": "Bonne prise en charge. Accepte la mixité sectorielle.",
    },
    "Shell": {
        "nom": "Shell Energy",
        "type": "oblige",
        "prix_classic_mwhc": 8.30,
        "prix_precarite_mwhc": 14.80,
        "tolerance": "mixte",
        "multisite": False,
        "secteurs_ok": ["BAT", "BAR", "IND", "TRA"],
        "mixite_ok": True,
        "exige_cofrac": False,
        "seuil_volume_min": 0,
        "bonus_volume_pct": 2,
        "malus_incomplet_pct": -20,
        "delai_paiement_jours": 35,
        "tolerance_surface_pct": 0.10,
        "tolerance_kwhc_pct": 0.09,
        "notes": "Service pro. Accepte transport (TRA).",
    },
}

# Cout COFRAC moyen par opération
COUT_COFRAC = 2800  # €


def calculer_scenario_acheteur(acheteur_key, volume_kwhc, secteurs=None,
                                nb_sites=1, qualite_dossier="standard",
                                precarite=False, cout_travaux_ttc=0):
    """Calcule le scénario de rachat pour un acheteur donné."""
    acheteur = ACHETEURS.get(acheteur_key)
    if not acheteur:
        return None

    secteurs = secteurs or ["BAT"]

    # Prix de base
    prix_base = acheteur["prix_precarite_mwhc"] if precarite else acheteur["prix_classic_mwhc"]

    # Vérifier compatibilité secteur
    secteurs_refuses = [s for s in secteurs if s not in acheteur["secteurs_ok"]]
    if secteurs_refuses:
        return {
            "acheteur": acheteur["nom"],
            "type": acheteur["type"],
            "statut": "REFUSE",
            "raison": f"Secteur(s) {', '.join(secteurs_refuses)} non accepté(s)",
            "prime": 0,
            "prix_mwhc": 0,
        }

    # Vérifier multi-sites
    if nb_sites > 1 and not acheteur["multisite"]:
        return {
            "acheteur": acheteur["nom"],
            "type": acheteur["type"],
            "statut": "REFUSE",
            "raison": f"Multi-sites ({nb_sites} sites) non accepté. Passer par délégataire.",
            "prime": 0,
            "prix_mwhc": 0,
        }

    # Vérifier mixité
    if len(secteurs) > 1 and not acheteur["mixite_ok"]:
        return {
            "acheteur": acheteur["nom"],
            "type": acheteur["type"],
            "statut": "REFUSE",
            "raison": "Mixité secteurs non acceptée",
            "prime": 0,
            "prix_mwhc": 0,
        }

    # Coefficient qualité dossier
    coeff = 1.0
    if qualite_dossier == "cofrac":
        coeff *= 1.10  # +10% prix premium
    elif qualite_dossier == "incomplet":
        coeff *= (1 + acheteur["malus_incomplet_pct"] / 100)

    # Bonus volume
    if volume_kwhc > 500_000_000 and acheteur["bonus_volume_pct"] > 0:
        coeff *= (1 + acheteur["bonus_volume_pct"] / 100)
    elif volume_kwhc > 100_000_000 and acheteur["bonus_volume_pct"] > 0:
        coeff *= (1 + acheteur["bonus_volume_pct"] / 200)  # demi-bonus

    # Volume minimum
    if volume_kwhc < acheteur["seuil_volume_min"]:
        return {
            "acheteur": acheteur["nom"],
            "type": acheteur["type"],
            "statut": "VOLUME_INSUFFISANT",
            "raison": f"Volume {volume_kwhc/1e6:.0f} MkWhc < seuil {acheteur['seuil_volume_min']/1e6:.0f} MkWhc",
            "prime": 0,
            "prix_mwhc": 0,
        }

    prix_final = round(prix_base * coeff, 2)
    prime = round(volume_kwhc * prix_final / 1000, 2)  # kWhc → MWhc → €

    # Coût COFRAC si exigé
    cout_cofrac = COUT_COFRAC if acheteur["exige_cofrac"] else 0
    prime_nette = prime - cout_cofrac

    # Couverture
    coverage = round(prime_nette / cout_travaux_ttc * 100, 1) if cout_travaux_ttc > 0 else 0
    rac = max(0, cout_travaux_ttc - prime_nette)

    return {
        "acheteur": acheteur["nom"],
        "type": acheteur["type"],
        "statut": "OK",
        "prix_mwhc": prix_final,
        "prix_base_mwhc": prix_base,
        "coeff_applique": round(coeff, 3),
        "prime_brute": round(prime, 2),
        "cout_cofrac": cout_cofrac,
        "prime_nette": round(prime_nette, 2),
        "coverage": coverage,
        "rac": round(rac, 2),
        "delai_paiement": acheteur["delai_paiement_jours"],
        "notes": acheteur["notes"],
        "exige_cofrac": acheteur["exige_cofrac"],
        "tolerance_surface": f"±{acheteur.get('tolerance_surface_pct', 0.10)*100:.0f}%",
        "tolerance_kwhc": f"±{acheteur.get('tolerance_kwhc_pct', 0.08)*100:.0f}%",
        # Score global multi-critères (revenu 50%, délai 25%, tolérance 25%)
        "score_global": round(
            (prix_final / 12.0) * 0.50 +
            (1 - acheteur["delai_paiement_jours"] / 90) * 0.25 +
            ((acheteur.get("tolerance_surface_pct", 0.10) + acheteur.get("tolerance_kwhc_pct", 0.08)) / 0.30) * 0.25,
            3
        ),
    }


def comparer_acheteurs(volume_kwhc, secteurs=None, nb_sites=1,
                       qualite_dossier="standard", precarite=False,
                       cout_travaux_ttc=0):
    """Compare tous les acheteurs et retourne le classement optimal."""
    resultats = []
    for key in ACHETEURS:
        r = calculer_scenario_acheteur(
            key, volume_kwhc, secteurs, nb_sites,
            qualite_dossier, precarite, cout_travaux_ttc
        )
        if r:
            resultats.append(r)

    # Trier par prime nette décroissante (les refusés en dernier)
    ok = [r for r in resultats if r["statut"] == "OK"]
    ok.sort(key=lambda x: x["prime_nette"], reverse=True)
    refuses = [r for r in resultats if r["statut"] != "OK"]

    recommandation = None
    if ok:
        best = ok[0]
        worst_ok = ok[-1] if len(ok) > 1 else best
        gain = round(best["prime_nette"] - worst_ok["prime_nette"], 2)
        recommandation = {
            "acheteur": best["acheteur"],
            "prime_nette": best["prime_nette"],
            "gain_vs_pire": gain,
            "gain_pct": round(gain / worst_ok["prime_nette"] * 100, 1) if worst_ok["prime_nette"] > 0 else 0,
            "coverage": best["coverage"],
        }

    return {
        "scenarios": ok + refuses,
        "recommandation": recommandation,
        "nb_acceptes": len(ok),
        "nb_refuses": len(refuses),
    }
