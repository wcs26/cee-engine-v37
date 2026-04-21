"""
CLIENT BDNB - WCS Pro
Récupère les données bâtiment réelles depuis la BDNB (data.ademe.fr)
Surface, DPE, année construction, usage...

API BDNB : https://data.ademe.fr/datasets/bdnb
"""

import os
import sys

# =========================
# CONFIG
# =========================

# API publique BDNB - pas de token requis
BDNB_BASE = "https://data.ademe.fr/data-fair/api/v1/datasets/bdnb-2023"
# Alternative: API gorenove
GORENOVE_BASE = "https://api.bdnb.io/v1"

# API BAN (géocodage) - gratuite, pas de token
BAN_BASE = "https://api-adresse.data.gouv.fr"

# API DPE ADEME - gratuite
DPE_BASE = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants"
DPE_TERTIAIRE_BASE = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-tertiaire-existant"


def _get(url, params=None):
    try:
        import requests
    except ImportError:
        print("pip install requests requis")
        return None

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        print(f"  API erreur {r.status_code}: {url}")
        return None
    except Exception as e:
        print(f"  Erreur: {e}")
        return None


# =========================
# GEOCODAGE (BAN)
# =========================

def geocoder(adresse):
    """Géocode une adresse → lat, lon, code commune."""
    data = _get(f"{BAN_BASE}/search/", {"q": adresse, "limit": 1})
    if not data or not data.get("features"):
        return None

    f = data["features"][0]
    props = f["properties"]
    coords = f["geometry"]["coordinates"]

    return {
        "lat": coords[1],
        "lon": coords[0],
        "label": props.get("label", ""),
        "code_commune": props.get("citycode", ""),
        "code_postal": props.get("postcode", ""),
        "commune": props.get("city", ""),
        "departement": props.get("postcode", "")[:2],
        "score": props.get("score", 0),
    }


# =========================
# DPE (ADEME)
# =========================

def get_dpe_tertiaire(adresse=None, code_commune=None):
    """Cherche les DPE tertiaire par adresse ou commune."""
    params = {"size": 5}

    if adresse:
        params["q"] = adresse
    elif code_commune:
        params["qs"] = f"code_insee_commune_actualise:{code_commune}"

    data = _get(f"{DPE_TERTIAIRE_BASE}/lines", params)
    if not data or not data.get("results"):
        return []

    resultats = []
    for r in data["results"]:
        resultats.append({
            "adresse": r.get("adresse_brut", ""),
            "surface": r.get("surface_habitable", 0) or r.get("surface_thermique_lot", 0),
            "dpe": r.get("classe_consommation_energie", ""),
            "ges": r.get("classe_estimation_ges", ""),
            "conso_kwh_m2": r.get("consommation_energie", 0),
            "annee_construction": r.get("annee_construction", ""),
            "type_batiment": r.get("type_batiment", ""),
            "energie_chauffage": r.get("type_energie_principale_chauffage", ""),
        })

    return resultats


def get_dpe_residentiel(adresse=None, code_commune=None):
    """Cherche les DPE résidentiel."""
    params = {"size": 5}

    if adresse:
        params["q"] = adresse
    elif code_commune:
        params["qs"] = f"code_insee_commune_actualise:{code_commune}"

    data = _get(f"{DPE_BASE}/lines", params)
    if not data or not data.get("results"):
        return []

    resultats = []
    for r in data["results"]:
        resultats.append({
            "adresse": r.get("adresse_brut", ""),
            "surface": r.get("surface_habitable", 0),
            "dpe": r.get("classe_consommation_energie", ""),
            "ges": r.get("classe_estimation_ges", ""),
            "conso_kwh_m2": r.get("consommation_energie", 0),
            "annee_construction": r.get("annee_construction", ""),
            "energie_chauffage": r.get("type_energie_principale_chauffage", ""),
        })

    return resultats


# =========================
# ENRICHISSEMENT COMPLET
# =========================

def enrichir_adresse(adresse):
    """
    Depuis une adresse :
    1. Géocode (BAN)
    2. Cherche DPE tertiaire + résidentiel
    3. Retourne surface, DPE, énergie...
    """
    print(f"  Geocodage: {adresse}")
    geo = geocoder(adresse)
    if not geo:
        print("  Adresse non trouvee")
        return None

    print(f"  Trouvé: {geo['label']} (dept {geo['departement']})")

    # Chercher DPE
    print("  Recherche DPE tertiaire...")
    dpe_t = get_dpe_tertiaire(adresse=adresse)

    print("  Recherche DPE résidentiel...")
    dpe_r = get_dpe_residentiel(adresse=adresse)

    dpe_all = dpe_t + dpe_r

    # Prendre le meilleur match (plus grande surface)
    best = None
    if dpe_all:
        best = max(dpe_all, key=lambda x: x.get("surface", 0) or 0)

    result = {
        "geo": geo,
        "departement": geo["departement"],
        "commune": geo["commune"],
        "dpe_count": len(dpe_all),
    }

    if best and best.get("surface"):
        result["surface"] = best["surface"]
        result["dpe"] = best.get("dpe", "")
        result["ges"] = best.get("ges", "")
        result["conso_kwh_m2"] = best.get("conso_kwh_m2", 0)
        result["annee_construction"] = best.get("annee_construction", "")
        result["energie_chauffage"] = best.get("energie_chauffage", "")

    return result


# =========================
# INTEGRATION MOTEUR CEE
# =========================

def auto_params_from_adresse(adresse):
    """
    Depuis une adresse, génère automatiquement les params
    pour le moteur CEE master.
    """
    from moteur_cee_master import get_zone

    data = enrichir_adresse(adresse)
    if not data:
        return None

    dep = data["departement"]
    zone = get_zone(dep)
    surface = data.get("surface", 0)

    # Déduire énergie depuis DPE
    energie_map = {
        "Électricité": "electricite",
        "Gaz naturel": "gaz",
        "Fioul domestique": "fioul",
        "GPL": "gaz",
        "Réseau de chaleur": "gaz",
    }
    energie_brut = data.get("energie_chauffage", "")
    energie = energie_map.get(energie_brut)

    params = {
        "departement": dep,
        "zone": zone,
        "surface": surface,
        "quantite": 0,
        "puissance": 0,
        "energie": energie,
        "nb_logements": 0,
        "puissance_froid": 0,
    }

    return {
        "params": params,
        "data": data,
    }


# =========================
# MAIN
# =========================

def main():
    print("\n===== BDNB CLIENT - WCS Pro =====\n")

    adresse = input("  Adresse complete: ").strip()
    if not adresse:
        print("  Adresse requise")
        return

    result = auto_params_from_adresse(adresse)
    if not result:
        return

    data = result["data"]
    params = result["params"]

    print(f"\n  {'='*45}")
    print(f"  DONNEES BATIMENT DETECTEES")
    print(f"  {'='*45}")
    print(f"  Commune    : {data.get('commune', '?')}")
    print(f"  Dept       : {data['departement']} (zone {params['zone']})")
    if data.get("surface"):
        print(f"  Surface    : {data['surface']} m2")
    if data.get("dpe"):
        print(f"  DPE        : {data['dpe']}")
    if data.get("ges"):
        print(f"  GES        : {data['ges']}")
    if data.get("conso_kwh_m2"):
        print(f"  Conso      : {data['conso_kwh_m2']} kWh/m2/an")
    if data.get("energie_chauffage"):
        print(f"  Chauffage  : {data['energie_chauffage']}")
    if data.get("annee_construction"):
        print(f"  Construction: {data['annee_construction']}")
    print(f"  DPE trouves: {data['dpe_count']}")

    # Compléments manuels si surface manquante
    if not params["surface"]:
        s = input("\n  Surface non detectee. Surface m2: ").strip()
        params["surface"] = float(s) if s else 0

    quantite = input("  Quantite equipements (ou 0): ").strip()
    params["quantite"] = int(quantite) if quantite else 0

    puissance = input("  Puissance kW (ou 0): ").strip()
    params["puissance"] = float(puissance) if puissance else 0

    # Lancer le moteur
    from moteur_cee_master import analyser, afficher
    resultats = analyser(params)
    afficher(resultats, params)


if __name__ == "__main__":
    main()
