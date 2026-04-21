"""
pv_cotation.py — Module de cotation photovoltaïque automatique
CEE ENGINE V37 — PV Pro

Sources prix/tarifs :
- Prix installé : moyennes marché installateurs France T1 2026
- Tarifs OA EDF : arrêté tarifaire S1 2026 (CRE)
- Production par zone : données Météo-France / ADEME moyennes pluriannuelles
"""

import math
from flask import Blueprint, request, jsonify

# ============================================================
# CONSTANTES MARCHÉ PV 2026
# ============================================================

# Prix moyen installé HT en €/Wc par tranche de puissance
PRIX_WC_HT = [
    (9,    1.10),   # ≤ 9 kWc
    (36,   0.95),   # 9–36 kWc
    (100,  0.85),   # 36–100 kWc
    (500,  0.75),   # 100–500 kWc
]

# Tarifs rachat OA EDF S1 2026 en €/kWh (revente totale)
TARIF_OA = [
    (3,    0.1297),
    (9,    0.1123),
    (36,   0.0801),
    (100,  0.0701),
]

# Tarif revente surplus (autoconsommation avec injection)
TARIF_SURPLUS = 0.10  # €/kWh

# Production annuelle moyenne par zone climatique (kWh/kWc/an)
# H1=Nord/Centre, H2=Ouest/Atlantique, H3=Sud/Méditerranée
PRODUCTION_ZONE = {
    "H1":  1100,
    "H2":  1250,
    "H3":  1400,
    "DOM": 1500,  # Outre-mer — estimation conservatrice
}

# Facteurs d'orientation (référence : plein sud = 1.0)
FACTEUR_ORIENTATION = {
    "sud":        1.00,
    "est-ouest":  0.90,
    "est":        0.85,
    "ouest":      0.85,
    "nord":       0.65,
}

# Dégradation panneaux (%/an)
DEGRADATION_AN = 0.005  # 0.5%/an

# Surface par kWc (panneaux 400 Wc standard 2026)
M2_PAR_KWC = 5.5

# TVA
TVA_PV = 0.20  # 20% pour installations > 3 kWc tertiaire

# Leasing
TAUX_LEASING_ANNUEL = 0.045  # 4.5%
DUREE_LEASING_MOIS = 120     # 10 ans

# Durée d'analyse
DUREE_ANALYSE_ANS = 25

# Zones climatiques — même mapping que moteur_cee_master.py
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


# ============================================================
# HELPERS
# ============================================================

def _get_zone(dep):
    """Détermine la zone climatique depuis le département."""
    dep = str(dep).strip().zfill(2)
    if dep.startswith("97") or len(dep) == 3:
        return "DOM"
    for z, deps in ZONES.items():
        if dep in deps:
            return z
    return "H2"  # défaut prudent


def _get_zone_from_cp(cp):
    """Extrait le département depuis un code postal."""
    cp = str(cp).strip()
    if cp.startswith("97"):
        return _get_zone(cp[:3])
    return _get_zone(cp[:2])


def _prix_wc(puissance_kwc):
    """Prix HT en €/Wc selon la tranche de puissance."""
    for seuil, prix in PRIX_WC_HT:
        if puissance_kwc <= seuil:
            return prix
    return PRIX_WC_HT[-1][1]


def _tarif_oa(puissance_kwc):
    """Tarif OA en €/kWh selon la tranche de puissance."""
    for seuil, tarif in TARIF_OA:
        if puissance_kwc <= seuil:
            return tarif
    return TARIF_OA[-1][1]


def _facteur_inclinaison(deg):
    """
    Facteur de correction inclinaison.
    Optimal = 30° (1.0), plat 0° (0.90), vertical 90° (0.70).
    Interpolation linéaire par morceaux.
    """
    deg = max(0, min(90, deg))
    if deg <= 30:
        # 0° → 0.90, 30° → 1.0
        return 0.90 + (deg / 30) * 0.10
    else:
        # 30° → 1.0, 90° → 0.70
        return 1.0 - ((deg - 30) / 60) * 0.30


def _production_cumulee_25_ans(prod_an1):
    """Production cumulée sur 25 ans avec dégradation 0.5%/an."""
    total = 0
    for annee in range(DUREE_ANALYSE_ANS):
        total += prod_an1 * (1 - DEGRADATION_AN) ** annee
    return total


def _leasing_mensuel(montant_ttc):
    """Mensualité leasing à taux fixe (annuités constantes)."""
    r = TAUX_LEASING_ANNUEL / 12
    n = DUREE_LEASING_MOIS
    if r == 0:
        return montant_ttc / n
    return montant_ttc * r / (1 - (1 + r) ** (-n))


# ============================================================
# MOTEUR DE COTATION
# ============================================================

def cotation_pv(puissance_kwc, zone, mode="autoconsommation",
                orientation="sud", inclinaison_deg=30,
                prix_elec=0.25, conso_annuelle_kwh=None,
                surface_toiture_m2=None):
    """
    Calcule une cotation PV complète.
    Retourne un dict avec tous les indicateurs financiers.
    """
    # --- Dimensionnement ---
    nb_panneaux = math.ceil(puissance_kwc / 0.4)  # panneaux 400 Wc
    surface_nec = puissance_kwc * M2_PAR_KWC

    faisabilite_ok = True
    if surface_toiture_m2 and surface_nec > surface_toiture_m2:
        faisabilite_ok = False

    # --- Production ---
    prod_base = PRODUCTION_ZONE.get(zone, 1250)
    f_orient = FACTEUR_ORIENTATION.get(orientation, 1.0)
    f_incl = _facteur_inclinaison(inclinaison_deg)
    production_an1 = puissance_kwc * prod_base * f_orient * f_incl
    prod_cumul_25 = _production_cumulee_25_ans(production_an1)

    # --- Coûts ---
    prix_wc = _prix_wc(puissance_kwc)
    cout_ht = puissance_kwc * 1000 * prix_wc
    cout_ttc = cout_ht * (1 + TVA_PV)

    # --- Revenus/économies selon le mode ---
    tarif_oa = _tarif_oa(puissance_kwc)

    if mode == "revente_totale":
        revenu_an = production_an1 * tarif_oa
        economie_an = 0
    elif mode == "autoconsommation":
        # Sans conso fournie : on suppose 100% autoconsommé
        conso = conso_annuelle_kwh or production_an1
        part_autoconso = min(production_an1, conso)
        surplus = max(0, production_an1 - conso)
        economie_an = part_autoconso * prix_elec
        revenu_an = 0  # pas de revente en autoconso pure
    else:  # surplus
        conso = conso_annuelle_kwh or (production_an1 * 0.7)
        taux_autoconso = 0.70 if conso >= production_an1 else min(0.70, conso / production_an1)
        part_autoconso = production_an1 * taux_autoconso
        surplus = production_an1 * (1 - taux_autoconso)
        economie_an = part_autoconso * prix_elec + surplus * TARIF_SURPLUS
        revenu_an = surplus * TARIF_SURPLUS

    gain_annuel = economie_an + revenu_an

    # --- ROI ---
    roi_pct = (gain_annuel / cout_ttc * 100) if cout_ttc > 0 else 0
    temps_retour = cout_ttc / gain_annuel if gain_annuel > 0 else 99

    # Gain total 25 ans (avec dégradation)
    gain_total_25 = 0
    for a in range(DUREE_ANALYSE_ANS):
        facteur_deg = (1 - DEGRADATION_AN) ** a
        if mode == "revente_totale":
            gain_total_25 += production_an1 * facteur_deg * tarif_oa
        elif mode == "autoconsommation":
            c = conso_annuelle_kwh or production_an1
            p = production_an1 * facteur_deg
            gain_total_25 += min(p, c) * prix_elec
        else:
            p = production_an1 * facteur_deg
            ac = p * taux_autoconso
            su = p * (1 - taux_autoconso)
            gain_total_25 += ac * prix_elec + su * TARIF_SURPLUS
    gain_total_25 -= cout_ttc

    # --- LCOE ---
    lcoe = cout_ttc / prod_cumul_25 if prod_cumul_25 > 0 else 0

    # --- Leasing ---
    leasing_mens = _leasing_mensuel(cout_ttc)

    return {
        "puissance_kwc": round(puissance_kwc, 2),
        "nb_panneaux": nb_panneaux,
        "surface_necessaire_m2": round(surface_nec, 1),
        "faisabilite_surface": faisabilite_ok,
        "zone_climatique": zone,
        "production_annuelle_kwh": round(production_an1),
        "facteurs": {
            "zone": prod_base,
            "orientation": f_orient,
            "inclinaison": round(f_incl, 3),
        },
        "cout_installation_ht": round(cout_ht, 2),
        "cout_installation_ttc": round(cout_ttc, 2),
        "mode": mode,
        "economie_annuelle_eur": round(economie_an, 2),
        "revenu_revente_annuel_eur": round(revenu_an, 2),
        "gain_annuel_total_eur": round(gain_annuel, 2),
        "roi_annuel_pct": round(roi_pct, 2),
        "temps_retour_annees": round(temps_retour, 1),
        "gain_total_25_ans_eur": round(gain_total_25, 2),
        "lcoe_eur_kwh": round(lcoe, 4),
        "leasing_mensuel_eur": round(leasing_mens, 2),
        "comptant_eur": round(cout_ttc, 2),
        "tarif_oa_applique": tarif_oa,
        "prix_wc_applique": prix_wc,
    }


# ============================================================
# ROUTES FLASK
# ============================================================

pv_bp = Blueprint("pv", __name__, url_prefix="/pv")


@pv_bp.route("/cotation", methods=["POST"])
def route_cotation():
    """POST /pv/cotation — Cotation PV complète."""
    data = request.get_json(force=True)
    puissance = data.get("puissance_kwc")
    if not puissance or puissance <= 0:
        return jsonify({"error": "puissance_kwc requis (> 0)"}), 400

    # Zone depuis localisation
    loc = data.get("localisation", {})
    dep = loc.get("departement") or (str(loc.get("cp", ""))[:2] if loc.get("cp") else None)
    if loc.get("cp") and str(loc["cp"]).startswith("97"):
        dep = str(loc["cp"])[:3]
    zone = _get_zone(dep) if dep else "H2"

    mode = data.get("mode", "autoconsommation")
    if mode not in ("autoconsommation", "revente_totale", "surplus"):
        return jsonify({"error": "mode invalide (autoconsommation|revente_totale|surplus)"}), 400

    result = cotation_pv(
        puissance_kwc=float(puissance),
        zone=zone,
        mode=mode,
        orientation=data.get("orientation", "sud"),
        inclinaison_deg=float(data.get("inclinaison_deg", 30)),
        prix_elec=float(data.get("prix_elec_actuel", 0.25)),
        conso_annuelle_kwh=data.get("conso_annuelle_kwh"),
        surface_toiture_m2=data.get("surface_toiture_m2"),
    )
    return jsonify(result)


@pv_bp.route("/tarifs", methods=["GET"])
def route_tarifs():
    """GET /pv/tarifs — Tarifs OA et prix marché actuels."""
    return jsonify({
        "prix_installe_eur_wc": [
            {"seuil_kwc": s, "prix_ht": p} for s, p in PRIX_WC_HT
        ],
        "tarifs_oa_eur_kwh": [
            {"seuil_kwc": s, "tarif": t} for s, t in TARIF_OA
        ],
        "tarif_surplus_eur_kwh": TARIF_SURPLUS,
        "production_kwh_kwc_an": PRODUCTION_ZONE,
        "surface_m2_par_kwc": M2_PAR_KWC,
        "degradation_an_pct": DEGRADATION_AN * 100,
        "tva_pct": TVA_PV * 100,
        "source": "Arrêté tarifaire CRE S1 2026 / moyennes marché installateurs France",
        "mise_a_jour": "2026-04",
    })


@pv_bp.route("/simulation-rapide", methods=["POST"])
def route_simulation_rapide():
    """POST /pv/simulation-rapide — Simulation express depuis SIRET ou surface."""
    data = request.get_json(force=True)
    siret = data.get("siret")
    surface = data.get("surface_toiture_m2")

    # Tentative récupération localisation via SIRET (API INSEE)
    dep = None
    if siret:
        try:
            import requests as http_req
            r = http_req.get(
                f"https://api.insee.fr/entreprises/sirene/V3.11/siret/{siret}",
                headers={"Accept": "application/json"},
                timeout=5,
            )
            if r.ok:
                etab = r.json().get("etablissement", {})
                adr = etab.get("adresseEtablissement", {})
                cp = adr.get("codePostalEtablissement", "")
                dep = cp[:3] if cp.startswith("97") else cp[:2]
        except Exception:
            pass

    if not dep:
        dep = data.get("departement", "75")

    zone = _get_zone(dep)

    # Estimer puissance depuis surface toiture
    if not surface:
        surface = 100  # défaut 100 m² tertiaire
    puissance_estimee = surface / M2_PAR_KWC  # kWc max

    # Plafonner à 100 kWc pour simulation rapide
    puissance_estimee = min(puissance_estimee, 100)

    result = cotation_pv(
        puissance_kwc=round(puissance_estimee, 1),
        zone=zone,
        mode="surplus",
        surface_toiture_m2=surface,
    )
    result["source_estimation"] = "surface_toiture"
    result["siret"] = siret
    result["departement_detecte"] = dep
    return jsonify(result)


@pv_bp.route("/comparatif", methods=["POST"])
def route_comparatif():
    """POST /pv/comparatif — Compare 3 scénarios (autoconso / surplus / revente totale)."""
    data = request.get_json(force=True)
    puissance = data.get("puissance_kwc")
    if not puissance or puissance <= 0:
        return jsonify({"error": "puissance_kwc requis"}), 400

    loc = data.get("localisation", {})
    dep = loc.get("departement") or (str(loc.get("cp", ""))[:2] if loc.get("cp") else None)
    zone = _get_zone(dep) if dep else "H2"

    orientation = data.get("orientation", "sud")
    inclinaison = float(data.get("inclinaison_deg", 30))
    prix_elec = float(data.get("prix_elec_actuel", 0.25))
    conso = data.get("conso_annuelle_kwh")

    scenarios = {}
    for mode in ("autoconsommation", "surplus", "revente_totale"):
        scenarios[mode] = cotation_pv(
            puissance_kwc=float(puissance),
            zone=zone,
            mode=mode,
            orientation=orientation,
            inclinaison_deg=inclinaison,
            prix_elec=prix_elec,
            conso_annuelle_kwh=conso,
        )

    # Recommandation : meilleur gain 25 ans
    best = max(scenarios, key=lambda m: scenarios[m]["gain_total_25_ans_eur"])

    return jsonify({
        "scenarios": scenarios,
        "recommandation": best,
        "motif": f"Meilleur gain net sur 25 ans : {scenarios[best]['gain_total_25_ans_eur']:,.0f} €",
    })


def register_pv_routes(app):
    """Enregistre les routes PV sur l'application Flask."""
    app.register_blueprint(pv_bp)
