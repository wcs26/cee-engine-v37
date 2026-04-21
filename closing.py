"""
MOTEUR DE CLOSING CEE — Ne perdre aucun marché
Analyse chaque situation et produit la stratégie de vente optimale.

Principes:
1. Toujours trouver AU MOINS une opération 0€ client (closing facile)
2. Identifier les quick wins (ROI immédiat, pas de reste à charge)
3. Calculer la commission commerciale
4. Préparer les réponses aux objections
5. Proposer un plan de déploiement (pilote → généralisation)
6. Si un acheteur refuse → fallback automatique
"""

from negociation import comparer_acheteurs, ACHETEURS, COUT_COFRAC


# Pitchs adaptés au type de client
PITCHS_TYPE_CLIENT = {
    "pmi": {
        "accroche": "Transformez votre facture énergétique en revenu",
        "ton": "direct",
        "arguments_cles": [
            "Financez 100% de vos travaux sans avance de trésorerie",
            "Aucun investissement initial — la prime couvre les travaux",
            "Économies immédiates sur vos factures dès le mois suivant",
        ],
    },
    "grand_compte": {
        "accroche": "Optimisez votre stratégie RSE et Décret Tertiaire",
        "ton": "institutionnel",
        "arguments_cles": [
            "Atteignez vos objectifs réglementaires (Décret Tertiaire -40% en 2030)",
            "Valorisez votre engagement RSE avec des résultats mesurables",
            "Contrat-cadre multi-sites = économies d'échelle sur tout le parc",
        ],
    },
    "collectivite": {
        "accroche": "Rénovez votre patrimoine public sans impacter le budget",
        "ton": "institutionnel",
        "arguments_cles": [
            "Les CEE financent la rénovation des bâtiments publics",
            "Obligation Décret Tertiaire — les CEE sont la solution de financement",
            "Montage en tiers-financement possible (CPE)",
        ],
    },
    "bailleur": {
        "accroche": "Rénovez vos logements et valorisez votre patrimoine",
        "ton": "technique",
        "arguments_cles": [
            "Coup de Pouce P6 = prime ×5 pour sortie fossile",
            "Opérations 0€ pour les parties communes (isolation, VMC)",
            "Amélioration DPE = revalorisation des loyers",
        ],
    },
}


def detecter_type_client(nb_sites, surface, secteurs):
    """Détecte le type de client pour adapter le pitch."""
    if nb_sites > 10 or surface > 5000:
        return "grand_compte"
    if "BAR" in secteurs:
        return "bailleur"
    if any(s in secteurs for s in ["BAT"]) and surface > 1000:
        return "grand_compte"
    return "pmi"


def analyser_closing(resultats_pack, globaux, secteurs, nb_sites=1,
                     qualite="standard", surface=0, type_client=None):
    """Analyse complète orientée closing commercial."""

    if not resultats_pack:
        return {"strategie": "AUCUNE_OPPORTUNITE", "actions": []}

    # === 1. TRIER PAR FACILITÉ DE CLOSING ===

    # Opérations 0€ client (couverture ≥ 100%)
    zero_euro = [r for r in resultats_pack if r.get("coverage", 0) >= 100]
    zero_euro.sort(key=lambda x: x["prime_nette"], reverse=True)

    # Quick wins : prime > 500€, pas COFRAC, pas complexe
    quick_wins = [r for r in resultats_pack
                  if r.get("prime_nette", 0) > 500
                  and not r.get("cofrac", False)
                  and r.get("type", "") != "complexe"
                  and r.get("coverage", 0) >= 40]
    quick_wins.sort(key=lambda x: x["coverage"], reverse=True)

    # Gros volumes : les fiches qui rapportent le plus
    gros_volumes = sorted(resultats_pack,
                          key=lambda x: x.get("prime_nette", 0), reverse=True)[:5]

    # Coup de Pouce : les multiplicateurs
    coup_pouce = [r for r in resultats_pack if r.get("p6_active")]

    # === 2. STRATÉGIE D'APPROCHE ===

    # Pitch principal = commencer par le 0€ pour accrocher
    pitch_order = []

    if zero_euro:
        pitch_order.append({
            "phase": "ACCROCHE",
            "message": f"{len(zero_euro)} opération(s) entièrement financée(s) — le client ne paie rien",
            "fiches": [{"ref": r["ref"], "nom": r["nom"], "prime": r["prime_nette"],
                        "coverage": r["coverage"]} for r in zero_euro[:3]],
            "script": "Ces travaux sont intégralement pris en charge par les CEE. "
                      "Zéro euro de reste à charge. On peut démarrer immédiatement.",
        })

    if coup_pouce:
        pitch_order.append({
            "phase": "LEVIER",
            "message": f"Coup de Pouce P6 actif sur {len(coup_pouce)} opération(s) — bonus ×{coup_pouce[0].get('p6_bonus', 1)}",
            "fiches": [{"ref": r["ref"], "nom": r["nom"], "prime": r["prime_nette"],
                        "p6_bonus": r.get("p6_bonus", 1)} for r in coup_pouce[:3]],
            "script": "En plus, vous bénéficiez du Coup de Pouce P6 qui multiplie "
                      "la prime. Cette aide est temporaire — il faut en profiter maintenant.",
        })

    if quick_wins:
        non_zero = [r for r in quick_wins if r not in zero_euro][:3]
        if non_zero:
            pitch_order.append({
                "phase": "APPROFONDISSEMENT",
                "message": f"{len(non_zero)} opération(s) avec reste à charge modéré",
                "fiches": [{"ref": r["ref"], "nom": r["nom"], "prime": r["prime_nette"],
                            "rac": r["rac"], "coverage": r["coverage"]}
                           for r in non_zero],
                "script": "Pour compléter, ces opérations ont un reste à charge très "
                          "raisonnable, amorti en moins de 2 ans sur vos factures.",
            })

    if gros_volumes and gros_volumes[0] not in zero_euro:
        pitch_order.append({
            "phase": "VOLUME",
            "message": "Opérations à fort potentiel pour maximiser les économies",
            "fiches": [{"ref": r["ref"], "nom": r["nom"], "prime": r["prime_nette"],
                        "cumac": r["cumac"]} for r in gros_volumes[:3]],
            "script": "Ces opérations représentent le plus gros volume d'économies "
                      "d'énergie — et donc les primes les plus importantes.",
        })

    # === 3. COMMISSION COMMERCIALE ===
    total_prime = globaux.get("total_prime_nette", 0)

    commissions = {
        "solo_8pct": round(total_prime * 0.08, 2),
        "binome_4pct": round(total_prime * 0.04, 2),
        "wcs_15pct": round(total_prime * 0.15, 2),
    }

    if nb_sites > 1:
        commissions["solo_8pct_parc"] = round(commissions["solo_8pct"] * nb_sites, 2)
        commissions["binome_4pct_parc"] = round(commissions["binome_4pct"] * nb_sites, 2)
        commissions["wcs_15pct_parc"] = round(commissions["wcs_15pct"] * nb_sites, 2)

    # === 4. OBJECTIONS & RÉPONSES ===
    objections = []

    objections.append({
        "objection": "C'est quoi les CEE ? C'est fiable ?",
        "reponse": "Les CEE sont un dispositif légal obligatoire (loi POPE 2005). "
                   "Les fournisseurs d'énergie DOIVENT financer ces travaux. "
                   "C'est garanti par l'État, pas une subvention.",
        "preuve": "Arrêté du 21/12/2025 — 6ème période CEE (2026-2030)"
    })

    if zero_euro:
        objections.append({
            "objection": "Ça va me coûter combien ?",
            "reponse": f"Pour {len(zero_euro)} opération(s), le coût est de ZÉRO euro. "
                       "La prime CEE couvre 100% des travaux. Vous n'avancez rien.",
            "preuve": f"Couverture {zero_euro[0]['coverage']:.0f}% sur {zero_euro[0]['ref']}"
        })
    else:
        rac = globaux.get("total_rac", 0)
        objections.append({
            "objection": "Ça va me coûter combien ?",
            "reponse": f"Reste à charge estimé : {rac:,.0f}€ — amorti par les économies "
                       "d'énergie en 2-4 ans selon les opérations.",
            "preuve": f"Couverture globale {globaux.get('total_coverage', 0):.0f}%"
        })

    objections.append({
        "objection": "Je n'ai pas le temps / pas le budget",
        "reponse": "On s'occupe de tout : montage du dossier, choix de l'installateur, "
                   "suivi des travaux. Et la prime est versée directement, "
                   "souvent avant même la fin des travaux.",
        "preuve": "Délai paiement : 30-60 jours selon l'acheteur"
    })

    if nb_sites > 1:
        objections.append({
            "objection": "C'est trop compliqué avec nos " + str(nb_sites) + " sites",
            "reponse": "On commence par 3-5 sites pilotes pour valider le process, "
                       "puis on déploie sur tous les sites avec un contrat-cadre. "
                       "Un seul interlocuteur, un seul dossier groupé.",
            "preuve": "Stratégie pilote → déploiement (économie 15-25% sur contrat-cadre)"
        })

    objections.append({
        "objection": "Mon bâtiment est récent / bien isolé",
        "reponse": "Même les bâtiments récents ont des gisements CEE : GTB, "
                   "régulation, VMC, PAC... Le Décret Tertiaire impose -40% "
                   "d'ici 2030 — les CEE financent cette mise en conformité.",
        "preuve": "Décret Tertiaire (loi Élan) + BAT-TH-116 GTB"
    })

    # === 5. URGENCES / DEADLINES ===
    urgences = []

    fiches_deadline = [r for r in resultats_pack
                       if r.get("deadline", {}).get("status") == "attention"]
    if fiches_deadline:
        urgences.append({
            "type": "deadline",
            "message": f"{len(fiches_deadline)} fiche(s) bientôt abrogée(s) — dépôt urgent",
            "fiches": [r["ref"] for r in fiches_deadline[:5]],
        })

    urgences.append({
        "type": "prix",
        "message": "Début P6 (2026) = prix hauts. Les obligés achètent cher pour "
                   "remplir leur quota. En fin de période (2029-2030), les prix baissent.",
    })

    if surface >= 1000:
        urgences.append({
            "type": "reglementaire",
            "message": f"Décret Tertiaire : {surface:,.0f}m² → obligation -40% en 2030. "
                       "Les CEE financent la mise en conformité.",
        })

    # === 6. PLAN D'ACTION MULTI-SITE ===
    plan_deploiement = None
    if nb_sites > 1:
        nb_pilotes = min(5, max(2, nb_sites // 10))
        plan_deploiement = {
            "phase_1": {
                "label": f"Pilote ({nb_pilotes} sites)",
                "duree": "2-3 mois",
                "action": f"Démarrer sur {nb_pilotes} sites représentatifs pour valider "
                          "le process, les économies et le ROI",
                "prime_estimee": round(total_prime * nb_pilotes, 2),
            },
            "phase_2": {
                "label": f"Déploiement ({nb_sites // 3} sites)",
                "duree": "4-6 mois",
                "action": "Étendre aux sites les plus rentables (couverture > 70%)",
                "prime_estimee": round(total_prime * nb_sites // 3, 2),
            },
            "phase_3": {
                "label": f"Généralisation ({nb_sites} sites)",
                "duree": "6-12 mois",
                "action": "Tout le parc avec contrat-cadre installateur (-20% travaux)",
                "prime_estimee": round(total_prime * nb_sites, 2),
            },
        }

    # === 7. SCORING DEAL ===
    score = 0
    score_details = []

    if zero_euro:
        score += 30
        score_details.append(f"+30 : {len(zero_euro)} opération(s) 0€")
    if coup_pouce:
        score += 15
        score_details.append(f"+15 : Coup de Pouce P6 actif")
    if total_prime > 10000:
        score += 20
        score_details.append(f"+20 : Prime > 10k€")
    elif total_prime > 1000:
        score += 10
        score_details.append(f"+10 : Prime > 1k€")
    if nb_sites > 1:
        score += 15
        score_details.append(f"+15 : Multi-sites ({nb_sites})")
    if surface >= 1000:
        score += 10
        score_details.append(f"+10 : Décret Tertiaire")
    if globaux.get("total_coverage", 0) >= 70:
        score += 10
        score_details.append(f"+10 : Couverture ≥ 70%")

    score = min(100, score)

    verdict = "GO" if score >= 60 else "PRUDENCE" if score >= 30 else "DIFFICILE"
    probabilite = "85%" if score >= 80 else "70%" if score >= 60 else "50%" if score >= 40 else "25%"

    # Type client + pitch adapté
    if type_client is None:
        type_client = detecter_type_client(nb_sites, surface, secteurs)
    pitch_client = PITCHS_TYPE_CLIENT.get(type_client, PITCHS_TYPE_CLIENT["pmi"])

    return {
        "score": score,
        "verdict": verdict,
        "probabilite": probabilite,
        "type_client": type_client,
        "pitch_client": pitch_client,
        "score_details": score_details,
        "pitch_order": pitch_order,
        "zero_euro_count": len(zero_euro),
        "quick_wins_count": len(quick_wins),
        "coup_pouce_count": len(coup_pouce),
        "commissions": commissions,
        "objections": objections,
        "urgences": urgences,
        "plan_deploiement": plan_deploiement,
        "resume": {
            "prime_site": round(total_prime, 2),
            "prime_parc": round(total_prime * nb_sites, 2) if nb_sites > 1 else None,
            "nb_fiches": len(resultats_pack),
            "coverage": globaux.get("total_coverage", 0),
        },
    }


# Alias compatibilité
def generer_rapport_closing(validation_data, type_client="pmi"):
    """Alias compatible — génère un rapport closing depuis des données de validation."""
    return {
        "score": validation_data.get("score_confiance", 50),
        "niveau": "BON" if validation_data.get("score_confiance", 0) >= 60 else "MOYEN",
        "probabilite": "70%" if validation_data.get("score_confiance", 0) >= 60 else "50%",
        "points_forts": validation_data.get("messages", []),
        "points_faibles": validation_data.get("erreurs", []) + validation_data.get("avertissements", []),
        "pitch": PITCHS_TYPE_CLIENT.get(type_client, PITCHS_TYPE_CLIENT["pmi"]),
        "objections": [
            {"objection": "C'est compliqué", "reponse": "Nous prenons en charge 100% de la démarche", "technique": "Simplification"},
            {"objection": "On va attendre", "reponse": "Chaque mois d'attente = revenu perdu (prix P6 baissent en fin de période)", "technique": "Urgence"},
        ],
        "recommandation": "GO" if validation_data.get("est_valide", False) else "OPTIMISER",
    }
