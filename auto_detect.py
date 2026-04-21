"""
AUTO-DETECT CEE - WCS Pro
SIREN → données entreprise → analyse CEE → pitch commercial
"""

import json
import os
import sys

# =========================
# CONFIG API
# =========================

# L'API SIRENE nécessite un token INSEE
# Obtenir sur https://api.insee.fr/catalogue/site/themes/wso2/subthemes/developer/pages/item-info.jag?name=Sirene&version=V3&provider=insee
from config import PRIX_CUMAC, INSEE_TOKEN

# =========================
# SIRENE LOOKUP
# =========================

def get_sirene(siren):
    """Récupère les infos entreprise depuis l'API SIRENE."""
    try:
        import requests
    except ImportError:
        print("pip install requests requis")
        return None

    siren = str(siren).replace(" ", "")
    url = f"https://api.insee.fr/entreprises/sirene/V3/siren/{siren}"

    headers = {
        "Accept": "application/json",
    }
    if INSEE_TOKEN:
        headers["Authorization"] = f"Bearer {INSEE_TOKEN}"

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 401:
            print("  Token INSEE manquant ou expiré.")
            print("  export INSEE_TOKEN=votre_token")
            return None
        if r.status_code == 404:
            print(f"  SIREN {siren} non trouvé.")
            return None
        if r.status_code != 200:
            print(f"  Erreur API INSEE: {r.status_code}")
            return None

        data = r.json()
        ul = data.get("uniteLegale", {})
        periode = ul.get("periodesUniteLegale", [{}])[0]

        naf = periode.get("activitePrincipaleUniteLegale", "")
        nom = ul.get("denominationUniteLegale", "") or periode.get("denominationUsuelleUniteLegale", "")
        categorie = ul.get("categorieEntreprise", "")

        # Adresse du siège
        adresse_etab = ul.get("adresseEtablissement", {})
        cp = adresse_etab.get("codePostalEtablissement", "")
        commune = adresse_etab.get("libelleCommuneEtablissement", "")

        return {
            "siren": siren,
            "nom": nom,
            "naf": naf,
            "categorie": categorie,
            "cp": cp,
            "departement": cp[:2] if len(cp) >= 2 else "",
            "commune": commune,
        }

    except Exception as e:
        print(f"  Erreur: {e}")
        return None


# =========================
# SIRET (établissement)
# =========================

def get_siret(siret):
    """Récupère infos établissement via API gouv gratuite (fallback INSEE)."""
    siret = str(siret).replace(" ", "")

    # 1. API gratuite recherche-entreprises.api.gouv.fr (pas de token requis)
    result = _get_siret_gouv(siret)
    if result:
        return result

    # 2. Fallback: API INSEE (requiert token)
    if INSEE_TOKEN:
        result = _get_siret_insee(siret)
        if result:
            return result

    return None


_siret_gouv_cache = {}

def _get_siret_gouv(siret):
    """Lookup via recherche-entreprises.api.gouv.fr (gratuit, sans token). Cache + retry 429."""
    import urllib.request
    import urllib.error
    import ssl
    import json as _json
    import time

    # Cache
    if siret in _siret_gouv_cache:
        return _siret_gouv_cache[siret]

    url = f"https://recherche-entreprises.api.gouv.fr/search?q={siret}&page=1&per_page=1"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = _json.loads(resp.read().decode())

            results = data.get("results", [])
            if not results:
                return None

            e = results[0]
            s = e.get("siege", {})
            cp = s.get("code_postal", "")
            dep = s.get("departement", cp[:2] if len(cp) >= 2 else "")

            result = {
                "siret": siret,
                "siren": siret[:9],
                "nom": e.get("nom_complet", ""),
                "naf": s.get("activite_principale", ""),
                "cp": cp,
                "departement": dep,
                "commune": s.get("libelle_commune", ""),
                "voie": f"{s.get('numero_voie', '')} {s.get('type_voie', '')} {s.get('libelle_voie', '')}".strip(),
                "tranche_effectif": e.get("tranche_effectif_salarie", ""),
                "nature_juridique": e.get("nature_juridique", ""),
            }
            _siret_gouv_cache[siret] = result
            return result
        except urllib.error.HTTPError as he:
            if he.code == 429 and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            print(f"  API gouv HTTP {he.code}")
            return None
        except Exception as e:
            print(f"  Erreur API gouv: {e}")
            return None
    return None


def _get_siret_insee(siret):
    """Lookup via API INSEE (requiert token)."""
    try:
        import requests
    except ImportError:
        return None

    url = f"https://api.insee.fr/entreprises/sirene/V3/siret/{siret}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {INSEE_TOKEN}"}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None

        data = r.json()
        etab = data.get("etablissement", {})
        adresse = etab.get("adresseEtablissement", {})
        ul = etab.get("uniteLegale", {})
        periode = ul.get("periodesUniteLegale", [{}])[0]

        cp = adresse.get("codePostalEtablissement", "")

        return {
            "siret": siret,
            "siren": siret[:9],
            "nom": ul.get("denominationUniteLegale", ""),
            "naf": periode.get("activitePrincipaleUniteLegale", ""),
            "cp": cp,
            "departement": cp[:2] if len(cp) >= 2 else "",
            "commune": adresse.get("libelleCommuneEtablissement", ""),
            "voie": f"{adresse.get('numeroVoieEtablissement', '')} {adresse.get('typeVoieEtablissement', '')} {adresse.get('libelleVoieEtablissement', '')}".strip(),
        }

    except Exception as e:
        print(f"  Erreur INSEE: {e}")
        return None


# =========================
# DEDUCTION USAGE
# =========================

NAF_INDUSTRIE = ["10","11","13","14","15","16","17","20","21","22","23","24","25","26","27","28","29","30","31","32","33"]
NAF_COMMERCE = ["45","46","47"]
NAF_TERTIAIRE = ["55","56","58","59","60","61","62","63","64","65","66","68","69","70","71","72","73","74","75","77","78","79","80","81","82","84","85","86","87","88"]
NAF_AGRICULTURE = ["01","02","03"]

def deduce_usage(naf):
    """Déduit le type d'usage depuis le code NAF."""
    if not naf:
        return "inconnu"
    prefix = naf[:2]
    if prefix in NAF_INDUSTRIE:
        return "industrie"
    elif prefix in NAF_COMMERCE:
        return "commerce"
    elif prefix in NAF_AGRICULTURE:
        return "agriculture"
    elif prefix in NAF_TERTIAIRE:
        return "tertiaire"
    return "tertiaire"


# =========================
# FIABILISATION DATA
# =========================

RATIOS_SURFACE_NAF = {
    "47": 300,    # commerce
    "56": 150,    # restauration
    "10": 800,    # industrie agro
    "25": 1200,   # industrie metal
    "28": 1000,   # fabrication machines
    "22": 900,    # plasturgie
    "46": 500,    # commerce gros
    "55": 400,    # hebergement
    "86": 250,    # sante
}


def resolve_surface(entreprise, bdnb):
    """Résout la surface : BDNB > estimation NAF > défaut."""
    if bdnb and bdnb.get("surface"):
        return bdnb["surface"], "BDNB"

    naf = entreprise.get("naf", "")
    for prefix, ratio in RATIOS_SURFACE_NAF.items():
        if naf.startswith(prefix):
            return ratio, "ESTIMATION_NAF"

    return 200, "DEFAULT"


def resolve_energie(bdnb, naf):
    """Résout l'énergie : BDNB > estimation NAF > défaut."""
    if bdnb and bdnb.get("energie_chauffage"):
        mapping = {
            "Électricité": "electricite",
            "Gaz naturel": "gaz",
            "Fioul domestique": "fioul",
            "GPL": "gaz",
            "Réseau de chaleur": "gaz",
        }
        return mapping.get(bdnb["energie_chauffage"], "electricite"), "BDNB"

    if naf.startswith("47") or naf.startswith("56"):
        return "electricite", "ESTIMATION_NAF"
    if naf.startswith("10") or naf.startswith("25") or naf.startswith("28"):
        return "gaz", "ESTIMATION_NAF"

    return "electricite", "DEFAULT"


# =========================
# DETECTION GISEMENTS CEE
# =========================

# =========================
# MATRICE GISEMENTS CEE
# =========================

GISEMENTS = {
    "tertiaire": {
        "commerce": [
            {"type": "eclairage", "fiches": ["BAT-EQ-127"], "roi": 1},
            {"type": "climatisation", "fiches": ["BAT-TH-145"], "roi": 2},
            {"type": "chauffage", "fiches": ["BAT-TH-104"], "roi": 2},
            {"type": "GTB", "fiches": ["BAT-TH-116"], "roi": 3},
            {"type": "froid_commercial", "fiches": ["IND-UT-134"], "roi": 4},
        ],
        "bureaux": [
            {"type": "eclairage", "fiches": ["BAT-EQ-127"], "roi": 1},
            {"type": "GTB", "fiches": ["BAT-TH-116", "BAT-TH-145"], "roi": 3},
            {"type": "chauffage", "fiches": ["BAT-TH-104"], "roi": 2},
            {"type": "isolation", "fiches": ["BAT-EN-101", "BAT-EN-102"], "roi": 3},
        ],
        "sante": [
            {"type": "eclairage", "fiches": ["BAT-EQ-127"], "roi": 1},
            {"type": "GTB", "fiches": ["BAT-TH-145"], "roi": 3},
            {"type": "chauffage", "fiches": ["BAT-TH-104"], "roi": 2},
        ],
        "hebergement": [
            {"type": "eclairage", "fiches": ["BAT-EQ-127"], "roi": 1},
            {"type": "chauffage", "fiches": ["BAT-TH-104"], "roi": 2},
            {"type": "isolation", "fiches": ["BAT-EN-101", "BAT-EN-102"], "roi": 3},
        ],
    },
    "industrie": {
        "agroalimentaire": [
            {"type": "air_comprime", "fiches": ["IND-UT-117"], "roi": 5},
            {"type": "moteurs", "fiches": ["IND-UT-113"], "roi": 4},
            {"type": "recuperation_chaleur", "fiches": ["IND-UT-117"], "roi": 5},
            {"type": "froid_industriel", "fiches": ["IND-UT-134"], "roi": 5},
        ],
        "metal": [
            {"type": "moteurs", "fiches": ["IND-UT-113"], "roi": 5},
            {"type": "air_comprime", "fiches": ["IND-UT-117"], "roi": 5},
        ],
        "chimie": [
            {"type": "recuperation_chaleur", "fiches": ["IND-UT-117"], "roi": 5},
            {"type": "moteurs", "fiches": ["IND-UT-113"], "roi": 4},
            {"type": "froid_industriel", "fiches": ["IND-UT-134"], "roi": 4},
        ],
        "general": [
            {"type": "moteurs", "fiches": ["IND-UT-113"], "roi": 4},
            {"type": "air_comprime", "fiches": ["IND-UT-117"], "roi": 4},
        ],
    },
    "agriculture": {
        "cultures": [
            {"type": "serre_chauffage", "fiches": ["AGRI-TH-104", "AGRI-TH-110", "AGRI-TH-109"], "roi": 5},
            {"type": "serre_isolation", "fiches": ["AGRI-EQ-107", "AGRI-EQ-109", "AGRI-EQ-111", "AGRI-EQ-112"], "roi": 4},
            {"type": "serre_ecran_thermique", "fiches": ["AGRI-EQ-102", "AGRI-EQ-104", "AGRI-EQ-111"], "roi": 4},
            {"type": "serre_deshumidification", "fiches": ["AGRI-TH-117", "AGRI-TH-119"], "roi": 3},
            {"type": "serre_stockage_chaleur", "fiches": ["AGRI-TH-101", "AGRI-TH-102", "AGRI-EQ-108"], "roi": 3},
            {"type": "serre_chauffage_tube", "fiches": ["AGRI-TH-118"], "roi": 3},
            {"type": "regulation_temperature", "fiches": ["AGRI-EQ-101"], "roi": 3},
            {"type": "moteurs_variateurs", "fiches": ["AGRI-UT-101", "AGRI-UT-102"], "roi": 4},
            {"type": "regulation_froid", "fiches": ["AGRI-UT-103", "AGRI-UT-104"], "roi": 3},
            {"type": "sechage_solaire", "fiches": ["AGRI-EQ-110"], "roi": 2},
        ],
        "elevage": [
            {"type": "chauffage_batiment", "fiches": ["AGRI-TH-108"], "roi": 5},
            {"type": "recuperation_chaleur_lait", "fiches": ["AGRI-TH-103", "AGRI-TH-105"], "roi": 5},
            {"type": "ventilation_echangeur", "fiches": ["AGRI-TH-113"], "roi": 4},
            {"type": "moteurs_variateurs", "fiches": ["AGRI-UT-101", "AGRI-UT-102"], "roi": 4},
            {"type": "regulation_froid", "fiches": ["AGRI-UT-103", "AGRI-UT-104"], "roi": 3},
            {"type": "stop_start_agri", "fiches": ["AGRI-EQ-105"], "roi": 2},
            {"type": "ventilation_silo", "fiches": ["AGRI-EQ-106"], "roi": 2},
            {"type": "controle_moteur", "fiches": ["AGRI-SE-101"], "roi": 2},
        ],
        "general": [
            {"type": "moteurs_variateurs", "fiches": ["AGRI-UT-101", "AGRI-UT-102"], "roi": 4},
            {"type": "regulation_froid", "fiches": ["AGRI-UT-103", "AGRI-UT-104"], "roi": 3},
            {"type": "chauffage_pac", "fiches": ["AGRI-TH-108"], "roi": 3},
            {"type": "controle_moteur", "fiches": ["AGRI-SE-101"], "roi": 2},
            {"type": "stop_start_agri", "fiches": ["AGRI-EQ-105"], "roi": 2},
        ],
    },
    "transport": {
        "routier": [
            {"type": "formation_conduite_pl", "fiches": ["TRA-SE-101"], "roi": 5},
            {"type": "formation_conduite_vl", "fiches": ["TRA-SE-102"], "roi": 4},
            {"type": "telematique", "fiches": ["TRA-EQ-103"], "roi": 4},
            {"type": "pneumatiques_vl", "fiches": ["TRA-EQ-106"], "roi": 3},
            {"type": "lubrifiant_eco_vl", "fiches": ["TRA-EQ-104"], "roi": 3},
            {"type": "lubrifiant_eco_pl", "fiches": ["TRA-EQ-113"], "roi": 3},
            {"type": "gestion_pneus_pl", "fiches": ["TRA-SE-108", "TRA-SE-110"], "roi": 3},
            {"type": "gestion_pneus_vl", "fiches": ["TRA-SE-109", "TRA-SE-111"], "roi": 3},
            {"type": "vehicule_electrique_vl", "fiches": ["TRA-EQ-114", "TRA-EQ-117"], "roi": 5},
            {"type": "vehicule_electrique_pl", "fiches": ["TRA-EQ-129"], "roi": 5},
            {"type": "vehicule_optimise", "fiches": ["TRA-EQ-115"], "roi": 4},
            {"type": "froid_transport", "fiches": ["TRA-EQ-111"], "roi": 3},
            {"type": "suivi_conso", "fiches": ["TRA-SE-106", "TRA-SE-113"], "roi": 3},
            {"type": "velo_electrique", "fiches": ["TRA-EQ-121"], "roi": 2},
            {"type": "autocar_electrique", "fiches": ["TRA-EQ-128"], "roi": 4},
            {"type": "quadricycle_elec", "fiches": ["TRA-EQ-130"], "roi": 2},
            {"type": "stop_start_engin", "fiches": ["TRA-EQ-122"], "roi": 2},
            {"type": "simulateur_conduite", "fiches": ["TRA-EQ-123"], "roi": 2},
            {"type": "station_gonflage", "fiches": ["TRA-SE-104"], "roi": 2},
            {"type": "recreusage_pneus", "fiches": ["TRA-SE-105"], "roi": 2},
            {"type": "autopartage", "fiches": ["TRA-SE-112"], "roi": 3},
        ],
        "ferroviaire": [
            {"type": "stop_start_ferro", "fiches": ["TRA-EQ-125"], "roi": 3},
            {"type": "fret_ferroviaire", "fiches": ["TRA-SE-116"], "roi": 4},
        ],
        "fluvial": [
            {"type": "barge_fluviale", "fiches": ["TRA-EQ-109"], "roi": 4},
            {"type": "automoteur_fluvial", "fiches": ["TRA-EQ-110"], "roi": 4},
            {"type": "helice_tuyere", "fiches": ["TRA-EQ-120"], "roi": 3},
            {"type": "remotorisation_elec", "fiches": ["TRA-EQ-126"], "roi": 5},
            {"type": "bateau_elec_neuf", "fiches": ["TRA-EQ-127"], "roi": 5},
            {"type": "carenage", "fiches": ["TRA-SE-107"], "roi": 2},
            {"type": "fret_fluvial", "fiches": ["TRA-SE-117"], "roi": 4},
        ],
        "maritime": [
            {"type": "branchement_quai", "fiches": ["TRA-EQ-124"], "roi": 4},
            {"type": "lubrifiant_peche", "fiches": ["TRA-EQ-118"], "roi": 2},
            {"type": "optimisation_combustion", "fiches": ["TRA-EQ-119"], "roi": 3},
            {"type": "mesure_analyse_navire", "fiches": ["TRA-EQ-132"], "roi": 3},
        ],
        "intermodal": [
            {"type": "transport_intermodal", "fiches": ["TRA-EQ-101", "TRA-EQ-107"], "roi": 4},
            {"type": "wagon_autoroute", "fiches": ["TRA-EQ-108"], "roi": 3},
        ],
        "general": [
            {"type": "formation_conduite", "fiches": ["TRA-SE-101", "TRA-SE-102"], "roi": 4},
            {"type": "vehicule_electrique", "fiches": ["TRA-EQ-114", "TRA-EQ-129"], "roi": 5},
            {"type": "suivi_conso", "fiches": ["TRA-SE-106", "TRA-SE-113"], "roi": 3},
            {"type": "velo_electrique", "fiches": ["TRA-EQ-121"], "roi": 2},
        ],
    },
    "reseau_chaleur": {
        "general": [
            {"type": "rehab_poste_livraison", "fiches": ["RES-CH-103", "RES-CH-104"], "roi": 4},
            {"type": "basse_temperature", "fiches": ["RES-CH-105"], "roi": 5},
            {"type": "calorifugeage", "fiches": ["RES-CH-106"], "roi": 4},
            {"type": "recup_chaleur_fatale", "fiches": ["RES-CH-108"], "roi": 5},
            {"type": "eclairage_exterieur", "fiches": ["RES-EC-104"], "roi": 2},
        ],
    },
}

# NAF → (secteur, sous-secteur)
NAF_TO_GISEMENT = {
    # Tertiaire
    "47": ("tertiaire", "commerce"),
    "46": ("tertiaire", "commerce"),
    "56": ("tertiaire", "commerce"),
    "55": ("tertiaire", "hebergement"),
    "62": ("tertiaire", "bureaux"),
    "69": ("tertiaire", "bureaux"),
    "70": ("tertiaire", "bureaux"),
    "71": ("tertiaire", "bureaux"),
    "86": ("tertiaire", "sante"),
    "87": ("tertiaire", "sante"),
    # Industrie
    "10": ("industrie", "agroalimentaire"),
    "11": ("industrie", "agroalimentaire"),
    "25": ("industrie", "metal"),
    "24": ("industrie", "metal"),
    "20": ("industrie", "chimie"),
    "21": ("industrie", "chimie"),
    "22": ("industrie", "general"),
    "23": ("industrie", "general"),
    "26": ("industrie", "general"),
    "27": ("industrie", "general"),
    "28": ("industrie", "general"),
    "29": ("industrie", "general"),
    "30": ("industrie", "general"),
    # Agriculture
    "01": ("agriculture", "cultures"),
    "02": ("agriculture", "cultures"),
    "03": ("agriculture", "elevage"),
    # Transport
    "49": ("transport", "routier"),
    "50": ("transport", "general"),
    "51": ("transport", "general"),
    "52": ("transport", "general"),
    "53": ("transport", "general"),
}


def detect_gisements(entreprise, surface, energie):
    """Détecte les gisements via la matrice secteur x sous-secteur."""
    naf = entreprise.get("naf", "")
    prefix = naf[:2]

    # Lookup NAF → gisement, avec sous-détection agri élevage
    secteur, sous_secteur = NAF_TO_GISEMENT.get(prefix, (None, None))

    # Affinage agriculture: 011-013 = cultures/serres, 014-015 = élevage
    if prefix in ["01", "02", "03"] and len(naf) >= 4:
        sub = naf[2:4] if naf[2:4].isdigit() else "13"
        if int(sub) >= 40:
            sous_secteur = "elevage"
        else:
            sous_secteur = "cultures"

    # Affinage transport
    if prefix == "49" and len(naf) >= 4:
        sub = naf[2:4] if naf[2:4].isdigit() else "41"
        if sub in ["41", "42"]:
            sous_secteur = "routier"
        elif sub == "10":
            sous_secteur = "ferroviaire"
        elif sub == "50":
            sous_secteur = "fluvial"

    # Réseaux de chaleur / énergie
    if prefix == "35":
        secteur, sous_secteur = "reseau_chaleur", "general"

    # Fallback intelligent selon NAF
    if not secteur:
        if prefix in ["36", "37", "38", "39"]:
            secteur, sous_secteur = "industrie", "general"
        elif prefix in ["41", "42", "43"]:
            secteur, sous_secteur = "industrie", "general"
        elif prefix in ["64", "65", "66"]:
            secteur, sous_secteur = "tertiaire", "bureaux"
        elif prefix in ["84", "85"]:
            secteur, sous_secteur = "tertiaire", "bureaux"
        else:
            secteur, sous_secteur = "tertiaire", "bureaux"
    gisements = GISEMENTS.get(secteur, {}).get(sous_secteur, [])

    # Copie pour ne pas modifier la matrice
    result = [dict(g) for g in gisements]

    # Bonus énergie fossile → PAC
    # V36 FIX: Ne PAS ajouter PAC_remplacement si énergie = électricité ou PAC existante
    if energie in ["gaz", "fioul"]:
        refs_existantes = {g["type"] for g in result}
        if "PAC_remplacement" not in refs_existantes:
            result.append({"type": "PAC_remplacement", "fiches": ["BAT-TH-104"], "roi": 5})
    elif energie in ["electricite", "electrique", "pac"]:
        # V36: Retirer PAC_remplacement si présent (énergie déjà électrique/PAC)
        result = [g for g in result if g["type"] != "PAC_remplacement"]

    # Bonus grande surface → isolation
    if surface > 500 and secteur == "tertiaire":
        refs_existantes = {g["type"] for g in result}
        if "isolation" not in refs_existantes:
            result.append({"type": "isolation", "fiches": ["BAT-EN-101", "BAT-EN-102"], "roi": 3})

    return result


def prioriser_gisements(gisements, surface):
    """Trie par ROI décroissant, bonus surface."""
    for g in gisements:
        score = g.get("roi", 1)
        if surface > 1000:
            score += 1
        g["score"] = score

    return sorted(gisements, key=lambda x: x["score"], reverse=True)


# =========================
# ESTIMATION EQUIPEMENTS
# =========================

FOURCHETTES_SURFACE_NAF = {
    "47": (300, 1500),    # commerce
    "46": (500, 3000),    # commerce gros
    "56": (100, 400),     # restauration
    "55": (200, 1000),    # hébergement
    "10": (1000, 5000),   # industrie agro
    "11": (500, 2000),    # boissons
    "25": (800, 4000),    # métal
    "28": (1000, 5000),   # machines
    "20": (1000, 5000),   # chimie
    "62": (200, 800),     # informatique
    "69": (100, 500),     # comptabilité/juridique
    "86": (500, 3000),    # santé
    "87": (300, 2000),    # hébergement médicalisé
}


def estimate_surface_from_naf(naf):
    """Retourne (surface_min, surface_max) estimée depuis le NAF."""
    for prefix, fourchette in FOURCHETTES_SURFACE_NAF.items():
        if naf.startswith(prefix):
            return fourchette
    return (200, 800)


RATIOS_EQUIPEMENTS = {
    "eclairage": {
        "bureaux": 12, "commerce": 7, "hebergement": 10,
        "sante": 10, "agroalimentaire": 20, "metal": 20,
        "chimie": 20, "general": 15, "standard": 10,
    },
    "climatisation": {
        "bureaux": 30, "commerce": 25, "sante": 25,
        "standard": 30,
    },
    "chauffage": {
        "bureaux": 30, "commerce": 25, "hebergement": 20,
        "standard": 30,
    },
    "froid_commercial": {
        "commerce": 20, "standard": 30,
    },
    "froid_industriel": {
        "agroalimentaire": 15, "chimie": 20, "standard": 25,
    },
}


# =========================
# COEFFICIENT USAGE REEL
# =========================

# NAF alimentaire : 4711 (supermarché), 4721 (fruits/légumes), 4723 (poissons)...
NAF_ALIMENTAIRE = ["4711", "4721", "4722", "4723", "4724", "4725", "4729"]


def apply_usage_factor(type_gisement, naf):
    """Coefficient correctif selon usage réel du NAF."""
    factor = 1.0

    # Commerce alimentaire → froid boosté
    if any(naf.startswith(p) for p in NAF_ALIMENTAIRE):
        if type_gisement == "froid_commercial":
            factor = 1.5

    # Restauration → froid + chauffage boosté
    if naf.startswith("56"):
        if type_gisement in ["froid_commercial", "chauffage"]:
            factor = 1.3

    # Industrie agro → froid + air comprimé boosté
    if naf[:2] in ["10", "11"]:
        if type_gisement in ["froid_industriel", "air_comprime"]:
            factor = 1.4

    # Bureaux → éclairage boosté (heures d'utilisation)
    if naf[:2] in ["62", "69", "70", "71"]:
        if type_gisement == "eclairage":
            factor = 1.2

    # Santé → chauffage + éclairage boosté (24/7)
    if naf[:2] in ["86", "87"]:
        if type_gisement in ["eclairage", "chauffage"]:
            factor = 1.3

    return factor


def apply_surface_factor(surface, quantite):
    """Facteur correctif selon taille du site."""
    if surface < 300:
        factor = 0.9
    elif surface < 1000:
        factor = 1.0
    elif surface < 3000:
        factor = 1.1
    elif surface < 10000:
        factor = 1.2
    else:
        factor = 1.3
    return max(1, int(quantite * factor))


def estimate_quantites(surface, type_gisement, sous_secteur="standard"):
    """Estime le nombre d'équipements depuis la surface et le type."""
    if type_gisement in RATIOS_EQUIPEMENTS:
        ratios = RATIOS_EQUIPEMENTS[type_gisement]
        ratio = ratios.get(sous_secteur, ratios.get("standard", 30))
        quantite = max(1, int(surface / ratio))
        return apply_surface_factor(surface, quantite)

    # Cas industriels spécifiques
    if type_gisement == "air_comprime":
        quantite = max(1, int(surface / 800))
    elif type_gisement == "moteurs":
        quantite = max(1, int(surface / 400))
    elif type_gisement == "recuperation_chaleur":
        quantite = max(1, int(surface / 1000))
    else:
        quantite = 1

    return apply_surface_factor(surface, quantite)


# =========================
# SCORING BUSINESS
# =========================

GISEMENTS_FACILES = ["eclairage", "chauffage", "climatisation", "isolation"]
GISEMENTS_COMPLEXES = ["air_comprime", "froid_industriel", "recuperation_chaleur"]


def is_relevant(prime, surface, type_gisement=""):
    """Filtre les résultats non pertinents commercialement.
    V36: seuil abaissé à 50€ pour cohérence avec moteur_expert_v2."""
    if prime < 50:
        return False
    if surface > 100 and (prime / max(surface, 1)) < 0.3:
        return False
    return True


def classify_opportunity(prime, score):
    """Classifie l'opportunité pour le commercial."""
    if prime > 2000 and score > 12:
        return "HIGH VALUE"
    elif prime > 800:
        return "QUICK WIN"
    elif score > 10:
        return "EASY SIGN"
    else:
        return "LOW PRIORITY"


def score_rentabilite_surface(prime, surface):
    """€ de prime par m² — indicateur de densité de valeur."""
    return round(prime / max(surface, 1), 2)


INCOMPATIBILITES = {
    "eclairage": ["eclairage"],
    "chauffage": ["PAC_remplacement"],
    "PAC_remplacement": ["chauffage"],
    "GTB": ["GTB"],
}


def is_compatible(selected_types, current_type):
    """Vérifie qu'un gisement n'est pas incompatible avec ceux déjà retenus."""
    for t in selected_types:
        if current_type in INCOMPATIBILITES.get(t, []):
            return False
    return True


def build_optimal_pack(results):
    """Construit le pack optimal de fiches compatibles, trié par score."""
    pack = []
    total_prime = 0
    for r in results:
        if is_compatible([p["type"] for p in pack], r["type"]):
            pack.append(r)
            total_prime += r["prime"]
    return pack, total_prime


def compute_cumac(cu, quantite):
    """Calcul cumac sécurisé."""
    cumac = quantite * cu
    return max(0, int(cumac))


def compute_business_score(ref_fiche, prime, cumac, type_gisement, surface=0):
    """Score multicritère pour prioriser les actions commerciales."""
    score = 0

    # 1. Volume financier (40%)
    score += min(prime / 1000, 10) * 4

    # 2. Densité €/m² (clé pour la rentabilité commerciale)
    densite = prime / max(surface, 1)
    if densite > 5:
        score += 4
    elif densite > 2:
        score += 2

    # 3. Facilité terrain (30%)
    if type_gisement in GISEMENTS_FACILES:
        score += 3

    # 4. Probabilité acceptation client — V36: tous les secteurs, pas seulement BAT
    if ref_fiche.startswith("BAT") or ref_fiche.startswith("BAR"):
        score += 2
    elif ref_fiche.startswith("AGRI"):
        score += 2  # V36: AGRI = fiches faciles à vendre (0€ fréquent)
    elif ref_fiche.startswith("IND"):
        score += 1  # V36: IND = légèrement plus complexe mais gros volumes

    # 5. Complexité (malus)
    if type_gisement in GISEMENTS_COMPLEXES:
        score -= 2

    return round(score, 2)


# =========================
# MOTEUR EXPERT
# =========================

def moteur_expert_v2(entreprise, surface, energie, departement):
    """
    V2: Détecte TOUTES les fiches CEE par code APE via mapping complet.
    Puis scoring + questions intelligentes sur les gisements intéressants.
    """
    from mapping_naf_fiches import get_fiches_for_naf
    from moteur_cee_master import get_zone, load_fiches, get_cumac, compute, compute_full, is_eligible

    naf = entreprise.get("naf", "")
    zone = get_zone(departement)
    if not zone:
        return {"results": [], "pack": [], "total_prime": 0, "summary": "Departement inconnu"}

    # 1. Toutes les fiches éligibles pour ce NAF
    fiches_eligibles = get_fiches_for_naf(naf)
    fiches_db = {f["ref"]: f for f in load_fiches()}

    # 2. Calculer chaque fiche
    results = []
    questions_par_gisement = {}

    _, sous_secteur = NAF_TO_GISEMENT.get(naf[:2], ("tertiaire", "standard"))

    for fe in fiches_eligibles:
        ref = fe["ref"]
        fiche = fiches_db.get(ref)
        if not fiche:
            continue

        if fiche.get("actif") is False:
            continue

        # Calcul cumac
        if fiche.get("type") == "complexe":
            cumac = 0  # besoin réponses client
        elif fiche.get("type") == "surface":
            cu = get_cumac(fiche, zone, energie)
            cumac = surface * cu if cu else 0
        else:
            # Unitaire : estimer quantité
            usage_factor = apply_usage_factor(fe.get("sous_activite", ""), naf)
            quantite_est = estimate_quantites(surface, fe.get("sous_activite", "general"), sous_secteur)
            quantite_est = max(1, int(quantite_est * usage_factor))
            cu = get_cumac(fiche, zone, energie)
            if cu:
                fparams = fiche.get("params", [])
                if "puissance" in fparams and "quantite" in fparams:
                    cumac = compute_cumac(cu, quantite_est * 5)
                else:
                    cumac = compute_cumac(cu, quantite_est)
            else:
                cumac = 0

        prime = cumac * PRIX_CUMAC

        # Filtrer non pertinents
        if prime < 50 and fiche.get("type") != "complexe":
            continue

        score = compute_business_score(ref, prime, cumac, fe.get("sous_activite", ""), surface)

        entry = {
            "fiche": ref,
            "nom": fiche.get("nom", fe.get("description", "")),
            "type": fe.get("sous_activite", ""),
            "cumac": int(cumac),
            "prime": int(prime),
            "score": score,
            "opportunite": classify_opportunity(prime, score),
            "rentabilite_m2": score_rentabilite_surface(prime, surface) if surface else 0,
        }

        # Questions intelligentes pour gisements intéressants
        if fiche.get("type") == "complexe":
            entry["status"] = "A COMPLETER"
            entry["questions"] = generate_questions(fiche)
            entry["pitch"] = f"{fiche.get('nom', ref)} - donnees client necessaires pour calcul precis"
        elif prime >= 150:
            entry["pitch"] = generate_pitch_gisement(fe.get("sous_activite", ""), int(prime), quantite_est if fiche.get("type") != "surface" else int(surface))
        else:
            entry["pitch"] = ""

        results.append(entry)

    # Tri par score
    results = sorted(results, key=lambda x: x["score"], reverse=True)

    # Pack optimal
    pack, total_prime = build_optimal_pack(results)
    summary = generate_summary(pack, total_prime)

    # Questions d'affinage pour les top opportunités
    questions_affinage = []
    for r in pack[:5]:
        fiche = fiches_db.get(r["fiche"])
        if not fiche:
            continue
        sa = r["type"]

        # Questions contextuelles selon le type
        if sa in ["eclairage", "eclairage_agri"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Quel type d'eclairage actuel ? (fluorescent/LED/halogene)", "impact": "high"})
            questions_affinage.append({"fiche": r["fiche"], "q": "Combien de points lumineux ?", "impact": "high"})
        if sa in ["froid", "froid_commercial", "froid_transport"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Combien d'equipements frigorifiques ?", "impact": "high"})
            questions_affinage.append({"fiche": r["fiche"], "q": "Meubles ouverts ou fermes ?", "impact": "medium"})
        if sa in ["chauffage", "chauffage_batiment"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Type de chauffage actuel ? (gaz/fioul/electrique)", "impact": "high"})
            questions_affinage.append({"fiche": r["fiche"], "q": "Age de la chaudiere ?", "impact": "medium"})
        if sa in ["moteurs", "moteurs_variateurs", "moteurs_pompes"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Puissance totale des moteurs (kW) ?", "impact": "high"})
            questions_affinage.append({"fiche": r["fiche"], "q": "Nombre de moteurs ?", "impact": "high"})
        if sa in ["air_comprime"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Nombre de compresseurs ?", "impact": "high"})
            questions_affinage.append({"fiche": r["fiche"], "q": "Puissance compresseurs (kW) ?", "impact": "high"})
        if sa in ["gtb"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Existe-t-il deja un systeme de regulation ?", "impact": "high"})
        if sa in ["isolation", "enveloppe", "serre_isolation"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Le batiment est-il deja isole ?", "impact": "high"})
            questions_affinage.append({"fiche": r["fiche"], "q": "Surface a isoler (m2) ?", "impact": "high"})
        if sa in ["serres", "serre_chauffage", "serre_ecran_thermique"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Surface de serre (m2) ?", "impact": "high"})
            questions_affinage.append({"fiche": r["fiche"], "q": "Type de chauffage serre actuel ?", "impact": "medium"})
        if sa in ["recuperation_chaleur_lait", "elevage_laitier"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Nombre de vaches laitieres ?", "impact": "high"})
            questions_affinage.append({"fiche": r["fiche"], "q": "Tank a lait existant ?", "impact": "medium"})
        if sa in ["formation", "formation_conduite_pl", "formation_conduite_vl"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Nombre de conducteurs a former ?", "impact": "high"})
        if sa in ["vehicule_electrique", "vehicule_electrique_vl", "vehicule_electrique_pl", "electrique"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Nombre de vehicules a remplacer ?", "impact": "high"})
        if sa in ["routier"]:
            questions_affinage.append({"fiche": r["fiche"], "q": "Taille de la flotte (nb vehicules) ?", "impact": "high"})

    # Dédupliquer questions
    seen = set()
    unique_questions = []
    for q in questions_affinage:
        key = q["q"]
        if key not in seen:
            seen.add(key)
            unique_questions.append(q)

    return {
        "results": results,
        "pack": pack,
        "total_prime": total_prime,
        "summary": summary,
        "nb_fiches_eligibles": len(fiches_eligibles),
        "nb_fiches_calculees": len(results),
        "questions_affinage": unique_questions,
    }


def moteur_expert(entreprise, surface, energie, departement):
    """
    Pipeline complet : NAF → gisements → fiches → calcul → scoring.
    Retourne les résultats triés par score.
    """
    from moteur_cee_master import get_zone, load_fiches, get_cumac, is_eligible

    zone = get_zone(departement)
    if not zone:
        return []

    # 1. Détecter gisements
    gisements = detect_gisements(entreprise, surface, energie)

    # 2. Charger fiches réelles
    fiches_db = {f["ref"]: f for f in load_fiches()}

    # 3. Calculer chaque fiche des gisements
    results = []
    seen_refs = set()

    for g in gisements:
        for ref in g["fiches"]:
            if ref in seen_refs:
                continue
            seen_refs.add(ref)

            fiche = fiches_db.get(ref)
            if not fiche:
                continue

            if fiche.get("actif") is False:
                continue

            # Éligibilité
            params = {
                "zone": zone, "surface": surface, "energie": energie,
                "quantite": 1, "puissance": 0,
                "nb_logements": 0, "puissance_froid": 0,
            }
            if not is_eligible(fiche, params):
                continue

            # Cumac
            cu = get_cumac(fiche, zone, energie)
            if not cu:
                continue

            # Résoudre sous-secteur pour estimation
            naf = entreprise.get("naf", "")
            _, sous_secteur = NAF_TO_GISEMENT.get(naf[:2], ("tertiaire", "standard"))

            usage_factor = apply_usage_factor(g["type"], naf)

            if fiche["type"] == "surface":
                cumac = compute_cumac(cu, surface)
            else:
                quantite_est = estimate_quantites(surface, g["type"], sous_secteur)
                quantite_est = int(quantite_est * usage_factor)
                quantite_est = max(1, quantite_est)

                fparams = fiche.get("params", [])
                if "puissance" in fparams and "quantite" in fparams:
                    puissance_moy = 5  # kW moyen par équipement
                    cumac = compute_cumac(cu, quantite_est * puissance_moy)
                else:
                    cumac = compute_cumac(cu, quantite_est)

            prime = cumac * PRIX_CUMAC

            if not is_relevant(prime, surface, g["type"]):
                continue

            # Scoring business multicritère
            score = compute_business_score(ref, prime, cumac, g["type"], surface)

            # Quantité pour le pitch
            if fiche["type"] == "surface":
                q_pitch = int(surface)
            else:
                q_pitch = quantite_est

            result_entry = {
                "fiche": ref,
                "nom": fiche.get("nom", ""),
                "type": g["type"],
                "cumac": int(cumac),
                "prime": int(prime),
                "score": score,
                "opportunite": classify_opportunity(prime, score),
                "rentabilite_m2": score_rentabilite_surface(prime, surface),
                "pitch": generate_pitch_gisement(g["type"], int(prime), q_pitch),
            }

            if fiche.get("type") == "complexe":
                result_entry["status"] = "A COMPLETER AVEC CLIENT"
                result_entry["questions"] = generate_questions(fiche)

            results.append(result_entry)

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    pack, total_prime = build_optimal_pack(results)
    summary = generate_summary(pack, total_prime)

    return {
        "results": results,
        "pack": pack,
        "total_prime": total_prime,
        "summary": summary,
    }


# =========================
# PITCH COMMERCIAL
# =========================

def analyse_siret(siret):
    """Pipeline complet : SIRET → données → surface → moteur expert → résultats."""
    entreprise = get_siret(siret)
    if not entreprise:
        return {"error": "SIRET introuvable"}

    naf = entreprise.get("naf", "")
    dep = entreprise.get("departement", "")

    if not dep:
        return {"error": "Departement non trouve"}

    # Surface : BDNB ou estimation NAF
    bdnb = None
    if entreprise.get("voie") and entreprise.get("commune"):
        adresse = f"{entreprise['voie']} {entreprise.get('cp','')} {entreprise['commune']}"
        try:
            from bdnb_client import enrichir_adresse
            bdnb = enrichir_adresse(adresse)
        except Exception:
            pass

    surface, src_surface = resolve_surface(entreprise, bdnb)
    energie, src_energie = resolve_energie(bdnb, naf)

    # Si pas de BDNB, utiliser moyenne fourchette NAF
    if src_surface != "BDNB":
        s_min, s_max = estimate_surface_from_naf(naf)
        surface = int((s_min + s_max) / 2)
        src_surface = "ESTIMATION_NAF_MOYENNE"

    results = moteur_expert(
        entreprise=entreprise,
        surface=surface,
        energie=energie,
        departement=dep,
    )

    return {
        "entreprise": {
            "nom": entreprise.get("nom", ""),
            "naf": naf,
            "departement": dep,
            "commune": entreprise.get("commune", ""),
        },
        "surface_estimee": surface,
        "source_surface": src_surface,
        "energie": energie,
        "source_energie": src_energie,
        "resultats": results,
    }


QUESTIONS_VARIABLES = {
    "puissance": "Quelle est la puissance installée (kW) ?",
    "nb_compresseurs": "Combien de compresseurs ?",
    "nb_logements": "Combien de logements concernés ?",
    "surface": "Quelle est la surface (m²) ?",
    "cop": "Quel est le COP de l'équipement ?",
    "eer": "Quel est l'EER du groupe froid ?",
    "debit": "Quel est le débit nominal ?",
    "rendement": "Quel est le rendement thermique ?",
    "quantite": "Combien d'équipements concernés ?",
    "duree_fonctionnement": "Quelle est la durée annuelle de fonctionnement (h) ?",
}


def generate_questions(fiche):
    """Génère les questions à poser au client pour une fiche complexe."""
    variables = fiche.get("variables", fiche.get("params", []))
    questions = []
    for v in variables:
        q = QUESTIONS_VARIABLES.get(v, f"Valeur de {v} ?")
        questions.append(q)
    return questions


def generate_summary(pack, total_prime):
    """Résumé exécutif du pack optimal."""
    if not pack:
        return "Aucune opportunite pertinente detectee."

    top = pack[0]

    lines = [
        f"\n  POTENTIEL TOTAL : {int(total_prime):,} EUR",
        f"\n  ACTION PRIORITAIRE :",
        f"  → {top['type']} ({top['prime']:,} EUR) [{top['opportunite']}]",
        f"\n  PLAN RECOMMANDE :",
        f"  → {len(pack)} actions combinees",
    ]

    for p in pack:
        lines.append(f"     - {p['fiche']:15} {p['type']:18} {p['prime']:>6,} EUR")

    lines.append(f"\n  Dossier financable rapidement.")

    return "\n".join(lines)


def generate_pitch_gisement(type_gisement, prime, quantite):
    """Pitch court par type de gisement."""
    pitches = {
        "eclairage": f"Remplacement LED simple, {quantite} points lumineux, gain immediat sans perturbation. Prime estimee {prime} EUR.",
        "froid_commercial": f"Optimisation du froid, gros levier d'economie energetique. {quantite} equipements concernes. Prime {prime} EUR.",
        "froid_industriel": f"Modernisation groupe froid process, {quantite} unites. Prime {prime} EUR.",
        "chauffage": f"Modernisation chauffage, reduction facture + confort. Prime {prime} EUR.",
        "PAC_remplacement": f"Remplacement chaudiere par PAC, forte prime CEE. Prime {prime} EUR.",
        "GTB": f"Pilotage intelligent du batiment (GTB), economies 15-25%. Prime {prime} EUR.",
        "isolation": f"Isolation thermique, economies durables sur 30 ans. Prime {prime} EUR.",
        "climatisation": f"Optimisation climatisation, confort + economies. Prime {prime} EUR.",
        "air_comprime": f"Recuperation chaleur sur compresseur, {quantite} unites. Prime {prime} EUR.",
        "moteurs": f"Remplacement moteurs haut rendement IE3/IE4, {quantite} unites. Prime {prime} EUR.",
    }
    return pitches.get(type_gisement, f"Optimisation energetique, prime estimee {prime} EUR.")


def generate_pitch(resultats, params, entreprise=None):
    """Génère un pitch commercial personnalisé."""
    if not resultats:
        return "Aucune opportunite detectee."

    top = resultats[0]
    nom = entreprise.get("nom", "") if entreprise else ""
    header = f"Bonjour{' ' + nom if nom else ''},"

    return f"""
{header}

Apres analyse de votre batiment (~{int(params.get('surface', 0))} m2),
nous avons identifie une optimisation energetique immediate.

  Dispositif principal : {top['ref']} - {top.get('nom', '')}
  Gain estime : {top['prime']:,} EUR

Ce dispositif est finance en grande partie par les CEE,
avec un reste a charge tres faible voire nul selon votre situation.

Ce type d'operation est actuellement prioritaire (financements eleves).

Je vous propose une simulation rapide + validation d'eligibilite (2 min).

On regarde ca ensemble ?
"""


# =========================
# MAIN
# =========================

def main():
    print("\n===== AUTO-DETECT CEE =====\n")

    choix = input("  SIREN (9 chiffres) ou SIRET (14 chiffres): ").strip()

    if len(choix.replace(" ", "")) == 14:
        print("  Recherche SIRET...")
        entreprise = get_siret(choix)
    elif len(choix.replace(" ", "")) == 9:
        print("  Recherche SIREN...")
        entreprise = get_sirene(choix)
    else:
        print("  Format invalide (9 ou 14 chiffres)")
        return

    if not entreprise:
        print("  Entreprise non trouvee.")
        return

    usage = deduce_usage(entreprise["naf"])

    print(f"\n  Nom         : {entreprise['nom']}")
    print(f"  NAF         : {entreprise['naf']}")
    print(f"  Usage deduit: {usage}")
    print(f"  Dept        : {entreprise['departement']}")
    if entreprise.get("commune"):
        print(f"  Commune     : {entreprise['commune']}")

    # Auto-détection surface via BDNB/DPE
    from moteur_cee_master import get_zone, analyser, afficher

    zone = get_zone(entreprise["departement"])
    if not zone:
        print(f"  Departement {entreprise['departement']} non reconnu")
        return

    # Auto-détection BDNB
    bdnb = None
    if entreprise.get("voie") and entreprise.get("commune"):
        adresse_complete = f"{entreprise['voie']} {entreprise.get('cp','')} {entreprise['commune']}"
        print(f"\n  Recherche batiment: {adresse_complete}")
        try:
            from bdnb_client import enrichir_adresse
            bdnb = enrichir_adresse(adresse_complete)
            if bdnb:
                if bdnb.get("dpe"):
                    print(f"  DPE: {bdnb['dpe']}")
                if bdnb.get("conso_kwh_m2"):
                    print(f"  Conso: {bdnb['conso_kwh_m2']} kWh/m2/an")
        except Exception as e:
            print(f"  BDNB non disponible: {e}")

    # Fiabilisation surface + énergie
    surface, src_surface = resolve_surface(entreprise, bdnb)
    energie, src_energie = resolve_energie(bdnb, entreprise.get("naf", ""))

    print(f"\n  Surface    : {surface} m2 (source: {src_surface})")
    print(f"  Energie    : {energie} (source: {src_energie})")

    if src_surface != "BDNB":
        correction = input(f"  Corriger surface ? (entree = garder {surface}): ").strip()
        if correction:
            surface = float(correction)

    # Détection + priorisation gisements
    gisements = detect_gisements(entreprise, surface, energie)
    gisements = prioriser_gisements(gisements, surface)

    if gisements:
        print(f"\n  GISEMENTS CEE ({len(gisements)})")
        print("  " + "-" * 40)
        for g in gisements:
            print(f"    {g['type']:20} score {g['score']}/5")
            print(f"    {'':20} fiches: {', '.join(g['fiches'])}")

    quantite = int(input("\n  Quantite equipements: ") or "0")
    puissance = float(input("  Puissance kW (ou 0): ") or "0")

    params = {
        "departement": entreprise["departement"],
        "zone": zone,
        "surface": surface,
        "quantite": quantite,
        "puissance": puissance,
        "energie": energie,
        "nb_logements": 0,
        "puissance_froid": 0,
    }

    resultats = analyser(params)
    afficher(resultats, params)

    # Pitch
    print(generate_pitch(resultats, params, entreprise))


if __name__ == "__main__":
    main()
