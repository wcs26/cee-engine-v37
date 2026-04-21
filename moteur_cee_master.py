import json
import os
from datetime import datetime

# =========================
# CONFIG
# =========================

from config import (
    PRIX_CUMAC, PRIX_CUMAC_PRECARITE,
    COMMISSION_RATE, TVA_PRO, TVA_REDUITE, PRIX_NEGOCIE,
)

ZONES = {
    "H1": ["01","02","03","05","08","10","14","15","19","21","23","25","27",
           "28","38","39","42","43","45","51","52","54","55","57","58","59",
           "60","61","62","63","67","68","69","70","71","73","74","75","76",
           "77","78","80","88","89","90","91","92","93","94","95"],
    "H2": ["04","07","09","12","16","17","18","22","24","26","29","31","32",
           "33","35","36","37","40","41","44","46","47","48","49","50","53",
           "56","64","65","72","79","81","82","85","86","87"],
    "H3": ["06","11","13","20","2A","2B","30","34","66","83","84"],
    "DOM": ["971","972","973","974","976"],
}

# Mapping secteur activité → clé FOST
FOST_MAP = {
    "bureaux": "bureaux",
    "enseignement": "enseignement",
    "sante": "sante",
    "hotellerie": "hotellerie_restauration",
    "restauration": "hotellerie_restauration",
    "commerce": "commerces",
    "logistique": "autres",
    "sport": "autres",
    "culture": "autres",
    "administration": "bureaux",
    "social": "sante",
    "autres": "autres",
}

# =========================
# CHARGEMENT DONNÉES
# =========================

_ENGINE_DIR = os.path.dirname(__file__)


def _load_json(filename):
    path = os.path.join(_ENGINE_DIR, filename)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_fiches():
    return _load_json("fiches.json")


def load_cout_travaux():
    return _load_json("cout_travaux.json")


def load_deadlines():
    return _load_json("deadlines.json")


# =========================
# UTILS
# =========================

def get_zone(dep):
    dep = str(dep).zfill(2)
    # DOM: 3 chiffres
    if len(dep) == 3 or dep.startswith("97"):
        return "DOM"
    for z, deps in ZONES.items():
        if dep in deps:
            return z
    return None


def get_cumac(fiche, zone, energie=None, activity_sector=None):
    """Calcul cumac unitaire avec FOST factors et variante élec."""
    # Variante électricité
    if energie == "electricite" and fiche.get("cumac_elec"):
        cu_dict = fiche["cumac_elec"]
    else:
        cu_dict = fiche.get("cumac_unitaire")

    if isinstance(cu_dict, (int, float)):
        cu = cu_dict
    elif isinstance(cu_dict, dict):
        # Essayer zone_energie d'abord
        if energie:
            cle = f"{zone}_{energie}"
            if cle in cu_dict:
                cu = cu_dict[cle]
            else:
                cu = cu_dict.get(zone, cu_dict.get("H2", 0))
        else:
            cu = cu_dict.get(zone, cu_dict.get("H2", 0))
    else:
        return 0

    # Appliquer facteur FOST (fiches BAT avec sectFactors)
    if fiche.get("sect_factors") and activity_sector:
        fost_key = FOST_MAP.get(activity_sector, "autres")
        factor = fiche["sect_factors"].get(fost_key, fiche["sect_factors"].get("autres", 0.6))
        cu = round(cu * factor)

    return cu


# =========================
# RÈGLES JURIDIQUES P6
# =========================

# Règle des 75% : si un secteur ≥ 75% de la surface → seul secteur retenu
# Sinon : secteur le plus défavorable (celui donnant le moins de CEE)
def regle_75_pct(secteurs_surfaces):
    """Applique la règle des 75% pour déterminer le secteur applicable.
    secteurs_surfaces: dict {secteur: surface_m2}
    Retourne le secteur applicable."""
    if not secteurs_surfaces:
        return "BAT"
    total = sum(secteurs_surfaces.values())
    if total <= 0:
        return list(secteurs_surfaces.keys())[0]
    for secteur, surf in secteurs_surfaces.items():
        if surf / total >= 0.75:
            return secteur
    # Aucun secteur ≥ 75% → retourner le plus défavorable (plus petite surface)
    return min(secteurs_surfaces, key=secteurs_surfaces.get)


# Tolérance bâtiment mixte tertiaire/résidentiel
# Si tertiaire dominant : surfaces résidentielles comptées comme "bureaux"
# Si résidentiel dominant : 1 logement pour 65 m² de locaux tertiaires
def tolerance_mixte(surface_tertiaire, surface_residentielle):
    """Retourne (secteur_applicable, nb_logements_equivalent)."""
    total = surface_tertiaire + surface_residentielle
    if total <= 0:
        return "BAT", 0
    if surface_tertiaire / total >= 0.5:
        return "BAT", 0  # Tertiaire dominant
    else:
        nb_log = int(surface_tertiaire / 65)  # partie entière
        return "BAR", nb_log


# Validation remplacement prématuré (arrêté 4 sept 2014 modifié, renforcé P6)
def check_remplacement_premature(fiche, age_equipement_annees=None):
    """Vérifie si l'équipement est trop récent pour être remplacé.
    Règle : âge réel doit être > 2/3 de la durée de vie conventionnelle."""
    if age_equipement_annees is None:
        return {"eligible": True, "warning": None}
    duree_vie = fiche.get("duree_vie")
    if not duree_vie or duree_vie <= 0:
        return {"eligible": True, "warning": None}
    seuil = duree_vie * 2 / 3
    if age_equipement_annees < seuil:
        return {
            "eligible": False,
            "warning": f"Remplacement prématuré : équipement de {age_equipement_annees} ans, "
                       f"minimum requis {seuil:.0f} ans (2/3 de {duree_vie} ans)"
        }
    return {"eligible": True, "warning": None}


# Règles multi-bâtiment (EFA - Entité Fonctionnelle Assujettie)
SEUIL_DECRET_TERTIAIRE = 1000  # m² surface cumulée
SEUIL_DOSSIER_SEPARE = 400     # m² par bâtiment pour dossier unique

def strategie_multisite(sites):
    """Calcule la stratégie optimale pour un parc multi-bâtiments.
    sites: list of dict {surface, secteur, adresse}
    Retourne la stratégie recommandée."""
    if not sites:
        return {"strategie": "mono", "dossiers": 1}

    total_surface = sum(s.get("surface", 0) for s in sites)
    nb_sites = len(sites)
    sites_gros = [s for s in sites if s.get("surface", 0) > SEUIL_DOSSIER_SEPARE]
    sites_petits = [s for s in sites if s.get("surface", 0) <= SEUIL_DOSSIER_SEPARE]

    decret_tertiaire = total_surface >= SEUIL_DECRET_TERTIAIRE
    nb_dossiers = len(sites_gros) + (1 if sites_petits else 0)

    return {
        "strategie": "groupe" if nb_sites > 1 else "mono",
        "nb_sites": nb_sites,
        "surface_totale": total_surface,
        "decret_tertiaire": decret_tertiaire,
        "nb_dossiers_min": nb_dossiers,
        "sites_dossier_separe": len(sites_gros),
        "sites_regroupables": len(sites_petits),
        "conseil": (
            f"{len(sites_gros)} dossier(s) séparé(s) (sites > {SEUIL_DOSSIER_SEPARE}m²) + "
            f"1 dossier groupé ({len(sites_petits)} petits sites)"
            if sites_gros and sites_petits else
            f"1 dossier groupé ({nb_sites} sites ≤ {SEUIL_DOSSIER_SEPARE}m²)"
            if not sites_gros else
            f"{len(sites_gros)} dossiers séparés"
        ),
    }


# Seuils P6 délégataires
P6_SEUILS = {
    "delegation_partielle_min": 2_000_000_000,  # 2 TWhc en kWhc
    "delegation_totale_si_inf": 2_000_000_000,
    "volume_min_delegataire": 300_000_000,      # 300 MkWhc
    "duree_contrat_pm": 5,                       # 5 ans (arrêté 21/12/2025)
    "maintien_fonctionnement": 6,                # 6 ans minimum
    "seuil_depot_std": 50_000_000,               # 50 GWhc
    "seuil_depot_spec": 20_000_000,              # 20 GWhc
    "taux_controle_cofrac": 0.30,                # 30%
    "taux_conformite_exige": 0.90,               # 90%
}


# =========================
# ELIGIBILITE
# =========================

def is_eligible(fiche, params, _deadlines=None, allowed_sectors=None):
    """Vérifie éligibilité d'une fiche CEE pour les params donnés.

    V37 FIX : ajout filtre secteur. Si allowed_sectors est fourni
    (ex: ["BAR", "BAT"] pour une SCI), les fiches AGRI/IND/TRA/RES sont exclues.
    Corrige la pertinence des résultats (avant: TOUT le catalogue était proposé).
    """
    # Fiche inactive
    if not fiche.get("actif", True):
        return False

    # Deadline dépassée
    deadlines = _deadlines if _deadlines is not None else load_deadlines()
    dl = deadlines.get(fiche["ref"])
    if dl:
        try:
            if datetime.now() >= datetime.strptime(dl, "%Y-%m-%d"):
                return False
        except (ValueError, TypeError, KeyError):
            pass

    # V37 FIX : filtre par secteur (BAR/BAT/IND/TRA/AGRI/RES)
    if allowed_sectors:
        ref = fiche.get("ref", "")
        fiche_secteur = ref.split("-")[0] if "-" in ref else ""
        if fiche_secteur and fiche_secteur not in allowed_sectors:
            return False

    cond = fiche.get("conditions", {})

    zones_ok = cond.get("zone", [])
    if zones_ok and params.get("zone") not in zones_ok:
        return False

    energies_ok = cond.get("energie", [])
    if energies_ok and params.get("energie") and params["energie"] not in energies_ok:
        return False

    for p, seuil in cond.get("seuils_min", {}).items():
        if params.get(p, 0) < seuil:
            return False

    return True


def check_deadline(fiche_ref, deadlines=None):
    """Vérifie si une fiche est abrogée ou bientôt abrogée."""
    if deadlines is None:
        deadlines = load_deadlines()

    dl = deadlines.get(fiche_ref)
    if not dl:
        return {"status": "active", "deadline": None}

    try:
        deadline = datetime.strptime(dl, "%Y-%m-%d")
    except ValueError:
        return {"status": "active", "deadline": dl}

    now = datetime.now()
    if now >= deadline:
        return {"status": "abrogee", "deadline": dl}
    elif (deadline - now).days <= 180:
        return {"status": "attention", "deadline": dl, "jours_restants": (deadline - now).days}
    else:
        return {"status": "active", "deadline": dl}


# =========================
# CALCUL
# =========================

def compute(fiche, params, zone, energie=None, activity_sector=None):
    """Calcul cumac total pour une fiche."""
    # Fiches complexes
    if fiche.get("type") == "complexe":
        return compute_complexe(fiche, params)

    cu = get_cumac(fiche, zone, energie, activity_sector)
    if cu == 0:
        return 0

    fparams = fiche.get("params", [])

    if fiche["type"] == "surface":
        # V37 FIX : surface_ratio pour fiches dont m² ≠ m² bâtiment
        # (fenêtres, capteurs solaires, lanterneaux)
        surface = params.get("surface", 0)
        ratio = fiche.get("surface_ratio")
        if ratio and 0 < ratio < 1:
            surface = surface * ratio
        return surface * cu

    elif fiche["type"] == "unitaire":
        if "puissance" in fparams and "quantite" in fparams:
            return params.get("puissance", 0) * params.get("quantite", 0) * cu
        elif "puissance" in fparams:
            return params.get("puissance", 0) * cu
        elif "puissance_froid" in fparams:
            return params.get("puissance_froid", 0) * cu
        elif "nb_logements" in fparams:
            return params.get("nb_logements", 0) * cu
        elif "longueur" in fparams:
            return params.get("longueur", 0) * cu
        else:
            return params.get("quantite", 0) * cu

    return 0


def compute_complexe(fiche, params):
    """Calcul pour fiches avec table multi-paramètres."""
    table = fiche.get("table_cumac", {})
    if not table:
        return 0

    mode = fiche.get("mode_calcul", "table")
    variables = fiche.get("variables", [])

    if mode == "table":
        key_var = variables[0] if variables else None
        mult_var = variables[1] if len(variables) > 1 else None

        if key_var:
            key_val = params.get(key_var, 0)
            cumac_unitaire = table.get(str(int(key_val)), 0)

            if not cumac_unitaire and table:
                int_keys = sorted([int(k) for k in table.keys() if k.isdigit()])
                if int_keys:
                    closest = min(int_keys, key=lambda k: abs(k - int(key_val)))
                    cumac_unitaire = table.get(str(closest), 0)

            if mult_var:
                return cumac_unitaire * params.get(mult_var, 1)
            return cumac_unitaire

    elif mode == "formule":
        formule = fiche.get("formule", "")
        if formule:
            try:
                # V37 SEC: eval sécurisé — builtins désactivés, formules issues de
                # fiches.json (fichier contrôlé par l'équipe CEE Engine), params = dict
                # Pas de risque d'injection car aucun input utilisateur dans la formule.
                return float(eval(formule, {"__builtins__": {}}, params))  # nosec B307
            except Exception:
                return 0

    return 0


def _build_alertes(fiche, deadline_info, cofrac=False):
    """Construit les alertes juridiques/réglementaires pour une fiche."""
    alertes = []
    # Deadline proche
    if deadline_info.get("status") == "attention":
        j = deadline_info.get("jours_restants", 0)
        alertes.append(f"⚠️ Abrogation dans {j} jours — dépôt urgent")
    # COFRAC
    if cofrac:
        alertes.append("🔍 Contrôle COFRAC obligatoire (30% taux P6) — prévoir budget inspection")
    # Durée de vie
    dv = fiche.get("duree_vie")
    if dv and dv > 0:
        alertes.append(f"📋 Maintien fonctionnement {dv} ans minimum (P6: 6 ans plancher)")
    # P6 renforcé
    if fiche.get("p6_bonus", 1) > 1:
        alertes.append(f"🔥 Coup de Pouce P6 ×{fiche['p6_bonus']} — rôle actif et incitatif AVANT signature devis")
    return alertes


# =========================
# CALCUL COMPLET (ORACLE-LEVEL)
# =========================

def compute_full(fiche, params, zone, energie=None, activity_sector=None,
                 prix_cumac=None, coup_de_pouce=False, precarite=False,
                 tva_reduite=False):
    """
    Calcul complet Oracle-level:
    cumac → prime brute (+ coup de pouce) → commission → prime nette
    → cout travaux → couverture → reste à charge

    Supporte:
    - Double pricing classique/précarité (Emmy)
    - Coup de Pouce P6 (multiplicateur gaz/fioul)
    - TVA réduite 5.5% (logement > 2 ans)
    - FOST factors par secteur d'activité
    - Cumac élec vs combustible
    """
    # Prix cumac: précarité (15.23 €/MWhc) vs classique (8.78 €/MWhc)
    if prix_cumac is None:
        prix_cumac = PRIX_CUMAC_PRECARITE if precarite else PRIX_CUMAC

    cumac = compute(fiche, params, zone, energie, activity_sector)
    if cumac <= 0:
        return None

    prime_brute = cumac * prix_cumac

    # Coup de Pouce P6
    p6_active = False
    p6_bonus = fiche.get("p6_bonus", 1)
    if p6_bonus and p6_bonus > 1 and coup_de_pouce and energie in ("gaz", "fioul"):
        prime_brute *= p6_bonus
        p6_active = True

    # Commission mandataire
    commission = prime_brute * COMMISSION_RATE
    prime_nette = prime_brute - commission

    # Comparaison classique vs précarité (calcul indépendant, même P6)
    _p6 = p6_bonus if p6_active else 1
    prime_classique_nette = round(cumac * PRIX_CUMAC * _p6 * (1 - COMMISSION_RATE), 2)
    prime_precarite_nette = round(cumac * PRIX_CUMAC_PRECARITE * _p6 * (1 - COMMISSION_RATE), 2)

    # Cout travaux
    cout_travaux = load_cout_travaux()
    ct = cout_travaux.get(fiche["ref"])
    cost_unit_warning = None

    if ct:
        # V37 FIX — Respecter l'unité DU COÛT pour déterminer la quantité,
        # pas l'unité du CUMAC. Corrige les 114 fiches où les unités divergent
        # (ex: BAR-TH-143 : cumac par m² plancher, coût par unité = 1 système).
        qty_cost = _get_qty_for_cost(fiche, params, ct.get("u", ""))
        if qty_cost is None:
            # Fallback si on ne sait pas quelle quantité utiliser
            qty_cost = _get_qty(fiche, params)
            cost_unit_warning = f"unité coût '{ct.get('u','?')}' non standard — estimation approximative"
        cost_ht = ct["moy"] * qty_cost * PRIX_NEGOCIE
        cost_min = ct["min"] * qty_cost
        cost_max = ct["max"] * qty_cost
        has_cout_marche = True
    else:
        ratio = 0.9 if fiche.get("zero_euro") else 0.5
        cost_ht = prime_brute / ratio if prime_brute > 0 else 0
        cost_min = cost_ht * 0.7
        cost_max = cost_ht * 1.3
        has_cout_marche = False

    # TVA: 5.5% rénovation énergétique résidentiel, 20% pro
    tva_rate = TVA_REDUITE if tva_reduite else TVA_PRO
    cost_ttc = cost_ht * (1 + tva_rate)
    coverage = (prime_nette / cost_ttc * 100) if cost_ttc > 0 else 0
    rac = max(0, cost_ttc - prime_nette)

    # Niveau couverture
    if coverage >= 120:
        cov_level = "MARGE_POSITIVE"
    elif coverage >= 100:
        cov_level = "ZERO_EURO"
    elif coverage >= 70:
        cov_level = "RAC_MODERE"
    elif coverage >= 40:
        cov_level = "RAC_SIGNIFICATIF"
    else:
        cov_level = "PRIME_FAIBLE"

    # Deadline
    deadline_info = check_deadline(fiche["ref"])

    return {
        "ref": fiche["ref"],
        "nom": fiche.get("nom", ""),
        "secteur": fiche.get("secteur", ""),
        "categorie": fiche.get("categorie", ""),
        "type": fiche.get("type", ""),
        "cumac": int(cumac),
        # Pricing
        "prime_brute": round(prime_brute, 2),
        "prime_nette": round(prime_nette, 2),
        "commission": round(commission, 2),
        "prix_cumac_utilise": round(prix_cumac * 1000, 2),  # en €/MWhc pour affichage
        "precarite": precarite,
        # Comparaison classique vs précarité (nettes, même P6)
        "prime_classique": prime_classique_nette,
        "prime_precarite": prime_precarite_nette,
        "bonus_precarite_pct": round((PRIX_CUMAC_PRECARITE / PRIX_CUMAC - 1) * 100, 1),
        # Coûts
        "cost_ht": round(cost_ht, 2),
        "cost_ttc": round(cost_ttc, 2),
        "cost_min": round(cost_min, 2),
        "cost_max": round(cost_max, 2),
        "tva_rate": tva_rate,
        "coverage": round(coverage, 1),
        "rac": round(rac, 2),
        "cov_level": cov_level,
        "has_cout_marche": has_cout_marche,
        # Flags
        "p6_active": p6_active,
        "p6_bonus": fiche.get("p6_bonus", 1),
        "zero_euro": fiche.get("zero_euro", False),
        "cofrac": fiche.get("cofrac", False),
        "deadline": deadline_info,
        "gisements": fiche.get("gisements", []),
        "note": fiche.get("note", ""),
        "duree_vie": fiche.get("duree_vie"),
        "type_operation": "OP",  # Standardisée par défaut
        # Alertes juridiques P6
        "alertes": _build_alertes(fiche, deadline_info, cofrac=fiche.get("cofrac", False)),
    }


def _get_qty(fiche, params):
    """Détermine la quantité effective pour le calcul de CUMAC (basée sur params fiche)."""
    fparams = fiche.get("params", [])
    if fiche.get("type") == "surface":
        return params.get("surface", 0)
    if "puissance" in fparams:
        return params.get("puissance", 0)
    if "nb_logements" in fparams:
        return params.get("nb_logements", 0)
    if "longueur" in fparams:
        return params.get("longueur", 0)
    return params.get("quantite", 0)


def _get_qty_for_cost(fiche, params, cost_unit):
    """V37 — Quantité pour calcul COÛT, basée sur l'unité du cout_travaux.json.
    Fix critique : corrige les 114 fiches où unité cumac ≠ unité coût.
    V37 FIX2 : applique surface_ratio aussi sur le coût quand u=m²
    (ex: BAT-TH-111 CES solaire : le coût est par m² de capteur, pas par m² bâtiment).
    Returns None si l'unité n'est pas reconnue (→ fallback vers _get_qty)."""
    u = (cost_unit or "").strip().lower()
    if u in ("m²", "m2"):
        surface = params.get("surface", 0) or 0
        ratio = fiche.get("surface_ratio")
        if ratio and 0 < ratio < 1:
            surface = surface * ratio
        return surface
    if u == "kw":
        # Puissance explicite OU estimation depuis surface (50 W/m² tertiaire moyen)
        p = params.get("puissance", 0) or 0
        if p <= 0 and params.get("surface", 0):
            p = max(1, round(params["surface"] * 0.05))  # 50 W/m² typique
        return p
    if u in ("unité", "unite", "installation", "bâtiment", "batiment", "chaudiere", "chaudière"):
        # 1 installation par défaut (un bâtiment = 1 installation type)
        return params.get("quantite", 0) or 1
    if u in ("point", "luminaire", "appareil"):
        # Éclairage LED : qté points = user, fallback surface/12 (1 point LED pour 12 m²)
        q = params.get("quantite", 0) or 0
        if q <= 0 and params.get("surface", 0):
            q = max(1, round(params["surface"] / 12))
        return q
    if u in ("logement", "logements"):
        return params.get("nb_logements", 0) or 1
    if u in ("m³", "m3"):
        return params.get("quantite", 0) or 0
    if u == "m":  # longueur (réseau tuyaux, câbles...)
        return params.get("longueur", 0) or 0
    if u == "kva":
        # Puissance apparente : fallback sur puissance kW
        return params.get("puissance", 0) or 0
    return None  # unité non reconnue → fallback _get_qty


# =========================
# SCORING BUSINESS
# =========================

def score_business(result, params):
    """Scoring enrichi avec coverage et gisements."""
    s = 0
    cumac = result["cumac"]
    prime = result["prime_nette"]
    coverage = result["coverage"]

    # Volume cumac
    if cumac > 50000:
        s += 3
    elif cumac > 20000:
        s += 2
    elif cumac > 5000:
        s += 1

    # Prime nette
    if prime > 1000:
        s += 2
    elif prime > 300:
        s += 1

    # Couverture (nouveau critère Oracle)
    if coverage >= 100:
        s += 3  # Opération 0€ = closing facile
    elif coverage >= 70:
        s += 2
    elif coverage >= 40:
        s += 1

    # Surface
    if params.get("surface", 0) > 1000:
        s += 1

    # Coup de pouce actif
    if result.get("p6_active"):
        s += 1

    return s


# =========================
# ANALYSE COMPLÈTE
# =========================

def _sectors_from_activity(activity_sector):
    """Déduit les secteurs CEE pertinents depuis le type d'activité.

    V37 FIX STRICT — quand on est en industrie, on ne voit QUE des fiches IND.
    Quand on est en tertiaire, on ne voit QUE BAT+BAR. Pas de mélange.

    Raison : Jimmy (commercial CEE) dit « il met du BAT à où on est en industrie,
    ce qui me parait impossible ». Réglementairement les BAT peuvent s'appliquer
    aux bureaux d'une usine, mais c'est trompeur pour le diagnostic initial.
    Si le client a besoin de fiches BAT pour ses bureaux d'usine, Jimmy
    lancera un 2e diagnostic avec activity_sector="bureaux" sur cette partie.

    Si activity_sector None → pas de filtre (rétro-compatibilité).
    """
    if not activity_sector:
        return None
    m = {
        # Tertiaire pur — BAT uniquement (pas de BAR résidentiel)
        # Si logements attenants → 2ème diagnostic avec activity_sector=logement
        "bureaux": ["BAT"],
        "commerce": ["BAT"],
        "commerce_alimentaire": ["BAT"],
        "commerce_non_alim": ["BAT"],
        "sante": ["BAT"],
        "enseignement": ["BAT"],
        "hotellerie": ["BAT"],
        "restauration": ["BAT"],
        "hebergement_social": ["BAT"],
        "administration": ["BAT"],
        "sport": ["BAT"],
        "culture": ["BAT"],
        "services_divers": ["BAT"],
        "services_personne": ["BAT"],
        "banque_assurance": ["BAT"],
        # Résidentiel / patrimoine — BAR (+ BAT si copro avec parties communes tertiaires)
        "logement_collectif": ["BAR", "RES"],
        "patrimoine_sci": ["BAR", "BAT"],
        # Industrie pure (PAS de BAT — si besoin BAT bureaux, faire un 2e diagnostic)
        "industrie": ["IND"],
        "logistique": ["IND"],
        "agroalimentaire": ["IND"],
        "metallurgie": ["IND"],
        "construction": ["IND"],
        # Agriculture pure
        "agriculture_elevage": ["AGRI"],
        # Transport pur
        "transport_routier": ["TRA"],
    }
    return m.get(activity_sector)


def analyser(params, activity_sector=None, coup_de_pouce=False, prix_cumac=None,
             precarite=False, tva_reduite=False):
    """Analyse complète avec calculs Oracle-level.
    V37 FIX : filtre par secteur si activity_sector fourni."""
    fiches = load_fiches()
    deadlines = load_deadlines()
    zone = params["zone"]
    energie = params.get("energie")
    allowed_sectors = _sectors_from_activity(activity_sector)

    resultats = []

    for f in fiches:
        if not is_eligible(f, params, _deadlines=deadlines, allowed_sectors=allowed_sectors):
            continue

        result = compute_full(
            f, params, zone, energie,
            activity_sector=activity_sector,
            prix_cumac=prix_cumac,
            coup_de_pouce=coup_de_pouce,
            precarite=precarite,
            tva_reduite=tva_reduite,
        )
        if not result:
            continue

        result["score"] = score_business(result, params)
        resultats.append(result)

    return sorted(resultats, key=lambda x: x["score"], reverse=True)


def analyser_global(resultats):
    """Calcul global sur l'ensemble des résultats (comme getGlobalCalc Oracle)."""
    total_cumac = sum(r["cumac"] for r in resultats)
    total_prime_brute = sum(r["prime_brute"] for r in resultats)
    total_prime_nette = sum(r["prime_nette"] for r in resultats)
    total_cost_ht = sum(r["cost_ht"] for r in resultats)
    total_cost_ttc = sum(r["cost_ttc"] for r in resultats)
    total_commission = sum(r["commission"] for r in resultats)
    total_rac = max(0, total_cost_ttc - total_prime_nette)
    total_coverage = (total_prime_nette / total_cost_ttc * 100) if total_cost_ttc > 0 else 0

    zero_count = sum(1 for r in resultats if r.get("zero_euro"))
    zero_prime = sum(r["prime_brute"] for r in resultats if r.get("zero_euro"))
    fiches_marche = sum(1 for r in resultats if r["has_cout_marche"])
    fiches_estimees = len(resultats) - fiches_marche

    if total_coverage >= 120:
        cov_level = "MARGE_POSITIVE"
    elif total_coverage >= 100:
        cov_level = "ZERO_EURO"
    elif total_coverage >= 70:
        cov_level = "RAC_MODERE"
    elif total_coverage >= 40:
        cov_level = "RAC_SIGNIFICATIF"
    else:
        cov_level = "PRIME_FAIBLE"

    return {
        "total_cumac": int(total_cumac),
        "total_mwhc": round(total_cumac / 1000, 1),
        "total_prime_brute": round(total_prime_brute, 2),
        "total_prime_nette": round(total_prime_nette, 2),
        "total_commission": round(total_commission, 2),
        "total_cost_ht": round(total_cost_ht, 2),
        "total_cost_ttc": round(total_cost_ttc, 2),
        "total_rac": round(total_rac, 2),
        "total_coverage": round(total_coverage, 1),
        "cov_level": cov_level,
        "zero_count": zero_count,
        "zero_prime": round(zero_prime, 2),
        "fiches_marche": fiches_marche,
        "fiches_estimees": fiches_estimees,
        "nb_fiches": len(resultats),
    }


# =========================
# AFFICHAGE
# =========================

def afficher(resultats, params, top=5):
    print(f"\n{'='*60}")
    print(f"  ANALYSE BUSINESS CEE (ORACLE-LEVEL)")
    print(f"{'='*60}")
    print(f"  Dept: {params['departement']} | Zone: {params['zone']}")
    print(f"  Surface: {params.get('surface',0)} m2")
    if params.get("puissance"):
        print(f"  Puissance: {params['puissance']} kW")
    if params.get("quantite", 0) > 0:
        print(f"  Quantite: {params['quantite']}")
    if params.get("energie"):
        print(f"  Energie: {params['energie']}")

    affiche = resultats[:top]
    globaux = analyser_global(resultats)

    print(f"\n  TOP {len(affiche)} OPPORTUNITES\n")

    for i, r in enumerate(affiche, 1):
        etoiles = "*" * r["score"]
        p6 = " [P6]" if r.get("p6_active") else ""
        dl = ""
        if r["deadline"]["status"] == "abrogee":
            dl = " [ABROGÉE]"
        elif r["deadline"]["status"] == "attention":
            dl = f" [J-{r['deadline']['jours_restants']}]"

        print(f"  #{i} {r['ref']} - {r['nom']}{p6}{dl}")
        print(f"     Cumac: {r['cumac']:>10,} kWhc")
        print(f"     Prime nette: {r['prime_nette']:>8,.0f} EUR")
        print(f"     Cout TTC:    {r['cost_ttc']:>8,.0f} EUR")
        print(f"     Couverture:  {r['coverage']:>7.0f}% ({r['cov_level']})")
        print(f"     RAC:         {r['rac']:>8,.0f} EUR")
        print(f"     Score: {r['score']}/10 {etoiles}")
        print()

    if len(resultats) > top:
        print(f"  + {len(resultats) - top} autres fiches eligibles\n")

    print(f"  {'-'*55}")
    print(f"  TOTAL CUMAC:      {globaux['total_cumac']:>10,} kWhc ({globaux['total_mwhc']} MWhc)")
    print(f"  PRIME BRUTE:      {globaux['total_prime_brute']:>10,.0f} EUR")
    print(f"  COMMISSION:       {globaux['total_commission']:>10,.0f} EUR")
    print(f"  PRIME NETTE:      {globaux['total_prime_nette']:>10,.0f} EUR")
    print(f"  COUT TTC:         {globaux['total_cost_ttc']:>10,.0f} EUR")
    print(f"  COUVERTURE:       {globaux['total_coverage']:>9.0f}%  ({globaux['cov_level']})")
    print(f"  RESTE A CHARGE:   {globaux['total_rac']:>10,.0f} EUR")
    print(f"  Fiches 0€:        {globaux['zero_count']}")
    print(f"  {'='*60}\n")


# =========================
# API (legacy compatible)
# =========================

def api_analyse(dep, surface=0, quantite=0, puissance=0, energie=None,
                nb_logements=0, puissance_froid=0):
    zone = get_zone(dep)
    if not zone:
        return {"erreur": f"Departement {dep} inconnu"}

    params = {
        "departement": dep, "zone": zone, "surface": surface,
        "quantite": quantite, "puissance": puissance, "energie": energie,
        "nb_logements": nb_logements, "puissance_froid": puissance_froid,
    }
    return analyser(params)


# =========================
# MAIN
# =========================

def main():
    print("\n===== MOTEUR CEE MASTER (ORACLE-FUSED) =====\n")

    dep = input("  Departement: ").strip()
    zone = get_zone(dep)
    if not zone:
        print(f"  Departement {dep} inconnu")
        return
    print(f"  Zone: {zone}")

    surface = float(input("  Surface m2: ") or "0")
    quantite = int(input("  Quantite: ") or "0")
    puissance = float(input("  Puissance kW (ou 0): ") or "0")
    energie = input("  Energie (electricite/gaz/fioul ou vide): ").strip() or None
    sector = input("  Secteur activite (bureaux/commerce/sante/...): ").strip() or None

    params = {
        "departement": dep, "zone": zone, "surface": surface,
        "quantite": quantite, "puissance": puissance, "energie": energie,
        "nb_logements": 0, "puissance_froid": 0,
    }

    resultats = analyser(params, activity_sector=sector)
    afficher(resultats, params)


if __name__ == "__main__":
    main()
