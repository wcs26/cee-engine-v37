"""
MOTEUR MULTI-SITE CEE — Stratégie optimale bâtiment par bâtiment
Applique la même intelligence à chaque site puis optimise le lot.

Règles légales appliquées:
- Règle des 75% (secteur dominant par bâtiment)
- Tolérance mixte tertiaire/résidentiel (65m² = 1 logement)
- Seuil dossier séparé > 400m² par bâtiment
- EFA (Entité Fonctionnelle Assujettie) si même unité foncière
- Décret Tertiaire si surface cumulée ≥ 1000m²
- Scoring potentiel par classe DPE + type bâtiment + QPV
"""

from dataclasses import dataclass, field as dc_field
from typing import List, Dict, Optional
from enum import Enum

from moteur_cee_master import (
    get_zone, load_fiches, analyser, analyser_global,
    regle_75_pct, tolerance_mixte, strategie_multisite,
    SEUIL_DOSSIER_SEPARE, SEUIL_DECRET_TERTIAIRE,
)
from negociation import comparer_acheteurs


# ═══════════════════════════════════════════════
# STRUCTURES SITE (scoring potentiel)
# ═══════════════════════════════════════════════

class TypeBatiment(Enum):
    BUREAUX = "bureaux"
    COMMERCE = "commerce"
    ENTREPOT = "entrepot"
    INDUSTRIE = "industrie"
    AGRICOLE = "agricole"
    SANTE = "sante"
    ENSEIGNEMENT = "enseignement"
    LOGEMENT = "logement"
    SPORT = "sport"
    RESTAURANT = "restaurant"


# Facteur gisement par classe DPE (G = 2× plus de potentiel que D)
FACTEUR_DPE = {"A": 0.3, "B": 0.5, "C": 0.7, "D": 1.0, "E": 1.3, "F": 1.6, "G": 2.0}

# Facteur gisement par type de bâtiment
FACTEUR_TYPE = {
    TypeBatiment.BUREAUX: 1.0,
    TypeBatiment.COMMERCE: 1.2,
    TypeBatiment.ENTREPOT: 0.8,
    TypeBatiment.INDUSTRIE: 1.5,
    TypeBatiment.AGRICOLE: 0.9,
    TypeBatiment.SANTE: 1.3,
    TypeBatiment.ENSEIGNEMENT: 1.1,
    TypeBatiment.LOGEMENT: 1.0,
    TypeBatiment.SPORT: 1.1,
    TypeBatiment.RESTAURANT: 1.2,
}


@dataclass
class SiteInfo:
    """Informations détaillées d'un site pour l'optimisation."""
    id: str = ""
    nom: str = ""
    adresse: str = ""
    surface_m2: float = 0
    type_batiment: str = "bureaux"
    classe_dpe: str = ""
    est_qpv: bool = False
    qpv_multiplicateur: float = 1.0

    @property
    def potentiel_gisement_kwhc(self) -> float:
        """Estime le potentiel CEE en kWhc depuis surface + DPE + type."""
        base = self.surface_m2 * 150  # 150 kWhc/m² moyenne
        f_dpe = FACTEUR_DPE.get(self.classe_dpe, 1.0)
        try:
            f_type = FACTEUR_TYPE.get(TypeBatiment(self.type_batiment), 1.0)
        except ValueError:
            f_type = 1.0
        f_qpv = self.qpv_multiplicateur if self.est_qpv else 1.0
        return base * f_dpe * f_type * f_qpv

    @property
    def priorite_score(self) -> float:
        """Score de priorité pour le tri (plus haut = traiter en premier)."""
        score = self.potentiel_gisement_kwhc / 1000  # normaliser
        if self.classe_dpe in ("F", "G"):
            score *= 1.5  # Passoires énergétiques = urgence
        if self.est_qpv:
            score *= 1.3
        return score


def scorer_sites(sites_data):
    """Score et trie une liste de sites par potentiel.
    sites_data: list of dict avec au minimum {surface, type}
    Retourne la liste triée par priorité décroissante."""
    sites = []
    for d in sites_data:
        s = SiteInfo(
            id=d.get("id", ""),
            nom=d.get("nom", ""),
            adresse=d.get("adresse", ""),
            surface_m2=d.get("surface", 0),
            type_batiment=d.get("type", "bureaux"),
            classe_dpe=d.get("classe_dpe", ""),
            est_qpv=d.get("qpv", False),
            qpv_multiplicateur=d.get("qpv_mult", 1.0),
        )
        sites.append({
            **d,
            "potentiel_kwhc": round(s.potentiel_gisement_kwhc),
            "priorite": round(s.priorite_score, 1),
        })
    return sorted(sites, key=lambda x: x["priorite"], reverse=True)


# ═══════════════════════════════════════════════
# PROFILS TYPES PAR SECTEUR
# ═══════════════════════════════════════════════

# Profils types par secteur d'activité pour générer les sites automatiquement
PROFILS_SITES = {
    "hebergement_social": [
        {"label": "EHPAD / Foyer", "pct": 0.45, "secteurs": {"BAT": 0.6, "BAR": 0.4}, "surface_moy": 1200,
         "params_type": {"energie": "gaz", "nb_logements": 40, "puissance": 80}},
        {"label": "Atelier / ESAT", "pct": 0.25, "secteurs": {"IND": 0.8, "BAT": 0.2}, "surface_moy": 600,
         "params_type": {"energie": "electricite", "puissance": 30}},
        {"label": "Bureau / Siège", "pct": 0.15, "secteurs": {"BAT": 1.0}, "surface_moy": 300,
         "params_type": {"energie": "electricite"}},
        {"label": "Logement autonome", "pct": 0.15, "secteurs": {"BAR": 1.0}, "surface_moy": 200,
         "params_type": {"energie": "gaz", "nb_logements": 8}},
    ],
    "commerce_alimentaire": [
        {"label": "Supermarché", "pct": 0.7, "secteurs": {"BAT": 0.9, "IND": 0.1}, "surface_moy": 800,
         "params_type": {"energie": "electricite", "puissance_froid": 50}},
        {"label": "Entrepôt / Réserve", "pct": 0.2, "secteurs": {"BAT": 1.0}, "surface_moy": 400,
         "params_type": {"energie": "electricite"}},
        {"label": "Bureau", "pct": 0.1, "secteurs": {"BAT": 1.0}, "surface_moy": 100,
         "params_type": {"energie": "electricite"}},
    ],
    "enseignement": [
        {"label": "Bâtiment enseignement", "pct": 0.6, "secteurs": {"BAT": 1.0}, "surface_moy": 1500,
         "params_type": {"energie": "gaz", "puissance": 100}},
        {"label": "Gymnase / Sport", "pct": 0.2, "secteurs": {"BAT": 1.0}, "surface_moy": 800,
         "params_type": {"energie": "gaz"}},
        {"label": "Cantine / Restaurant", "pct": 0.1, "secteurs": {"BAT": 0.7, "IND": 0.3}, "surface_moy": 300,
         "params_type": {"energie": "gaz"}},
        {"label": "Logement fonction", "pct": 0.1, "secteurs": {"BAR": 1.0}, "surface_moy": 150,
         "params_type": {"energie": "gaz", "nb_logements": 4}},
    ],
    "hotellerie": [
        {"label": "Hôtel principal", "pct": 0.8, "secteurs": {"BAT": 1.0}, "surface_moy": 2000,
         "params_type": {"energie": "gaz", "puissance": 150}},
        {"label": "Restaurant", "pct": 0.15, "secteurs": {"BAT": 0.8, "IND": 0.2}, "surface_moy": 300,
         "params_type": {"energie": "gaz"}},
        {"label": "Spa / Piscine", "pct": 0.05, "secteurs": {"BAT": 1.0}, "surface_moy": 200,
         "params_type": {"energie": "electricite"}},
    ],
    "sante": [
        {"label": "Bâtiment soins", "pct": 0.5, "secteurs": {"BAT": 1.0}, "surface_moy": 3000,
         "params_type": {"energie": "gaz", "puissance": 200}},
        {"label": "Hébergement patients", "pct": 0.3, "secteurs": {"BAT": 0.6, "BAR": 0.4}, "surface_moy": 2000,
         "params_type": {"energie": "gaz", "nb_logements": 60}},
        {"label": "Logistique / Cuisine", "pct": 0.15, "secteurs": {"IND": 0.7, "BAT": 0.3}, "surface_moy": 500,
         "params_type": {"energie": "gaz"}},
        {"label": "Administration", "pct": 0.05, "secteurs": {"BAT": 1.0}, "surface_moy": 300,
         "params_type": {"energie": "electricite"}},
    ],
    "industrie": [
        {"label": "Atelier production", "pct": 0.6, "secteurs": {"IND": 1.0}, "surface_moy": 2000,
         "params_type": {"energie": "gaz", "puissance": 200}},
        {"label": "Entrepôt", "pct": 0.25, "secteurs": {"IND": 0.5, "BAT": 0.5}, "surface_moy": 1500,
         "params_type": {"energie": "electricite"}},
        {"label": "Bureau / Administratif", "pct": 0.15, "secteurs": {"BAT": 1.0}, "surface_moy": 400,
         "params_type": {"energie": "electricite"}},
    ],
    "logement_collectif": [
        {"label": "Immeuble résidentiel", "pct": 0.85, "secteurs": {"BAR": 1.0}, "surface_moy": 1500,
         "params_type": {"energie": "gaz", "nb_logements": 25}},
        {"label": "Local commercial RDC", "pct": 0.1, "secteurs": {"BAT": 1.0}, "surface_moy": 150,
         "params_type": {"energie": "electricite"}},
        {"label": "Parking / Communs", "pct": 0.05, "secteurs": {"BAT": 1.0}, "surface_moy": 200,
         "params_type": {"energie": "electricite"}},
    ],
    # Fallback pour profils non listés
    "_default": [
        {"label": "Bâtiment principal", "pct": 0.8, "secteurs": {"BAT": 1.0}, "surface_moy": 500,
         "params_type": {}},
        {"label": "Annexe", "pct": 0.2, "secteurs": {"BAT": 1.0}, "surface_moy": 150,
         "params_type": {}},
    ],
}


def generer_sites(profil_key, nb_sites, surface_moyenne, departement):
    """Génère la liste des sites avec leur typologie depuis le profil.
    Distribution DÉTERMINISTE (pas de random) — mêmes entrées = mêmes résultats."""
    profils = PROFILS_SITES.get(profil_key, PROFILS_SITES["_default"])
    sites = []

    # Calculer le nombre de sites par type (déterministe)
    type_assignments = []
    remaining = nb_sites
    for j, p in enumerate(profils):
        if j == len(profils) - 1:
            count = max(0, remaining)
        else:
            count = max(1, round(nb_sites * p["pct"]))
            remaining -= count
        type_assignments.append((p, count))

    # Générer les sites
    idx = 0
    for type_site, count in type_assignments:
        for _ in range(count):
            if idx >= nb_sites:
                break
            i = idx
            idx += 1

            surf = round(surface_moyenne * (type_site["surface_moy"] / profils[0]["surface_moy"]))
            surf = max(50, surf)

        # Secteur applicable (règle des 75%)
        secteur_applicable = regle_75_pct(
            {k: v * surf for k, v in type_site["secteurs"].items()}
        )

        sites.append({
            "index": i + 1,
            "label": type_site["label"],
            "surface": surf,
            "secteurs": type_site["secteurs"],
            "secteur_applicable": secteur_applicable,
            "params_type": type_site["params_type"],
            "departement": departement,
        })

    return sites


def analyser_site(site, departement):
    """Analyse CEE complète pour un site individuel."""
    zone = get_zone(departement)
    if not zone:
        return None

    surf = site["surface"]
    p = site.get("params_type", {})

    params = {
        "departement": departement,
        "zone": zone,
        "surface": surf,
        "quantite": max(1, round(surf / 25)),
        "puissance": p.get("puissance", round(surf * 0.05)),
        "energie": p.get("energie"),
        "nb_logements": p.get("nb_logements", 0),
        "puissance_froid": p.get("puissance_froid", 0),
        "longueur": 0,
    }

    resultats = analyser(params)
    if not resultats:
        return {"site": site, "pack": [], "globaux": {}}

    globaux = analyser_global(resultats)

    # Top 5 fiches par prime
    top = sorted(resultats, key=lambda x: x["prime_nette"], reverse=True)[:5]

    return {
        "site": site,
        "pack_count": len(resultats),
        "top_fiches": [{
            "ref": r["ref"], "nom": r["nom"],
            "prime_nette": r["prime_nette"], "coverage": r["coverage"],
            "cov_level": r["cov_level"],
        } for r in top],
        "globaux": globaux,
    }


def optimiser_parc(profil_key, nb_sites, surface_moyenne, departement,
                   qualite_dossier="standard"):
    """Analyse complète d'un parc multi-sites avec stratégie optimale."""

    # Générer les sites
    sites = generer_sites(profil_key, min(nb_sites, 20), surface_moyenne, departement)

    # Analyser chaque type de site (pas les 79, juste les types uniques)
    types_vus = {}
    analyses_par_type = {}
    for site in sites:
        label = site["label"]
        if label not in types_vus:
            types_vus[label] = site
            analyses_par_type[label] = analyser_site(site, departement)

    # Extrapoler au parc complet
    # Compter combien de chaque type
    compteur_types = {}
    for site in sites:
        l = site["label"]
        compteur_types[l] = compteur_types.get(l, 0) + 1

    # Ratio d'extrapolation au parc réel
    ratio = nb_sites / len(sites) if len(sites) > 0 else 1

    # Construire le résumé par type
    resume_types = []
    total_cumac = 0
    total_prime = 0
    total_cost = 0
    total_surface = 0

    for label, analyse in analyses_par_type.items():
        if not analyse or not analyse.get("globaux"):
            continue
        g = analyse["globaux"]
        nb_de_ce_type = round(compteur_types.get(label, 1) * ratio)
        surf_type = analyse["site"]["surface"]

        type_cumac = g.get("total_cumac", 0) * nb_de_ce_type
        type_prime = g.get("total_prime_nette", 0) * nb_de_ce_type
        type_cost = g.get("total_cost_ttc", 0) * nb_de_ce_type

        total_cumac += type_cumac
        total_prime += type_prime
        total_cost += type_cost
        total_surface += surf_type * nb_de_ce_type

        resume_types.append({
            "label": label,
            "nb_sites": nb_de_ce_type,
            "surface_unitaire": surf_type,
            "surface_totale": surf_type * nb_de_ce_type,
            "secteur": analyse["site"]["secteur_applicable"],
            "nb_fiches": g.get("nb_fiches", 0),
            "cumac_unitaire": g.get("total_cumac", 0),
            "cumac_total": type_cumac,
            "prime_unitaire": round(g.get("total_prime_nette", 0), 2),
            "prime_totale": round(type_prime, 2),
            "cost_unitaire": round(g.get("total_cost_ttc", 0), 2),
            "cost_total": round(type_cost, 2),
            "coverage": g.get("total_coverage", 0),
            "top_fiches": analyse.get("top_fiches", [])[:3],
        })

    # Stratégie de dépôt
    sites_data = [{"surface": t["surface_unitaire"]} for t in resume_types for _ in range(t["nb_sites"])]
    strat = strategie_multisite(sites_data)

    # Secteurs cumulés
    tous_secteurs = list(set(s["secteur"] for s in resume_types))

    # Négociation optimale sur le volume total
    nego = comparer_acheteurs(
        int(total_cumac), tous_secteurs, nb_sites,
        qualite_dossier, False, total_cost
    )

    # Coverage globale
    coverage_globale = round(total_prime / total_cost * 100, 1) if total_cost > 0 else 0

    return {
        "profil": profil_key,
        "nb_sites_reel": nb_sites,
        "nb_types_batiment": len(resume_types),
        "surface_totale": round(total_surface),
        "total_cumac": int(total_cumac),
        "total_mwhc": round(total_cumac / 1000, 1),
        "total_prime_nette": round(total_prime, 2),
        "total_cost_ttc": round(total_cost, 2),
        "coverage_globale": coverage_globale,
        "rac_global": round(max(0, total_cost - total_prime), 2),
        "types_batiment": resume_types,
        "strategie_depot": strat,
        "negociation": nego,
        "decret_tertiaire": total_surface >= SEUIL_DECRET_TERTIAIRE,
        "secteurs": tous_secteurs,
    }


# Alias compatibilité
def analyser_parc_multisite(sites_data):
    """Alias compatible — score et analyse rapide d'une liste de sites."""
    return scorer_sites(sites_data)
