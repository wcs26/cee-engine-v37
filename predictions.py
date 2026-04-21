"""
REPONSES PREDICTIVES CONTEXTUELLES
Propose des réponses intelligentes selon NAF, surface, gisement.
"""


def get_predictions(question_id, naf="", surface=0, type_gisement="", energie=""):
    """Retourne des suggestions de réponses contextuelles."""
    prefix = naf[:2] if naf else ""

    predictions = {
        # Surface
        "surface": _predict_surface(prefix, surface),

        # Énergie
        "energie": _predict_energie(prefix),

        # Éclairage
        "type_eclairage": _predict_eclairage(prefix),
        "nb_luminaires": _predict_nb_luminaires(prefix, surface),

        # Chauffage
        "type_chauffage": _predict_chauffage(prefix, energie),
        "age_chaudiere": [
            {"value": "< 5 ans", "label": "Moins de 5 ans (récent)"},
            {"value": "5-10 ans", "label": "5 à 10 ans"},
            {"value": "10-15 ans", "label": "10 à 15 ans (à remplacer)"},
            {"value": "> 15 ans", "label": "Plus de 15 ans (urgent)"},
        ],

        # Froid
        "type_meubles_froids": _predict_froid(prefix),
        "nb_equipements_froid": _predict_nb_froid(prefix, surface),

        # Industrie
        "puissance": _predict_puissance(prefix, surface),
        "nb_compresseurs": _predict_nb_compresseurs(surface),
        "nb_moteurs": _predict_nb_moteurs(surface),
        "age_equipements": [
            {"value": "< 3 ans", "label": "Moins de 3 ans (récent)"},
            {"value": "3-7 ans", "label": "3 à 7 ans"},
            {"value": "7-12 ans", "label": "7 à 12 ans (rentable)"},
            {"value": "> 12 ans", "label": "Plus de 12 ans (prioritaire)"},
        ],

        # GTB
        "gtb_existant": [
            {"value": "non", "label": "Aucun système de régulation"},
            {"value": "basique", "label": "Régulation basique (thermostat)"},
            {"value": "programmable", "label": "Programmateur horaire"},
            {"value": "gtb_ancienne", "label": "GTB existante > 10 ans"},
        ],

        # Isolation
        "isolation_existante": [
            {"value": "aucune", "label": "Aucune isolation"},
            {"value": "partielle", "label": "Isolation partielle (< 50%)"},
            {"value": "ancienne", "label": "Isolation ancienne (> 15 ans)"},
            {"value": "recente", "label": "Isolation récente (non éligible)"},
        ],

        # Qualification générale
        "activite_site": _predict_activite(prefix),
        "budget": [
            {"value": "< 5000", "label": "Moins de 5 000 EUR"},
            {"value": "5000-20000", "label": "5 000 à 20 000 EUR"},
            {"value": "20000-50000", "label": "20 000 à 50 000 EUR"},
            {"value": "> 50000", "label": "Plus de 50 000 EUR"},
            {"value": "a_definir", "label": "À définir selon prime CEE"},
        ],

        # Closing
        "disponibilite": [
            {"value": "immediat", "label": "Disponible immédiatement"},
            {"value": "1_mois", "label": "Dans le mois"},
            {"value": "3_mois", "label": "Dans les 3 mois"},
            {"value": "6_mois", "label": "D'ici 6 mois"},
            {"value": "a_voir", "label": "À voir selon proposition"},
        ],
        "travaux_recents": [
            {"value": "non", "label": "Non, aucun travaux récent"},
            {"value": "oui_petit", "label": "Oui, petits travaux"},
            {"value": "oui_gros", "label": "Oui, gros travaux (attention cumul)"},
        ],
    }

    return predictions.get(question_id, [])


# =============================
# PREDICTIONS CONTEXTUELLES
# =============================

def _predict_surface(naf_prefix, surface_estimee):
    """Fourchettes de surface selon NAF."""
    fourchettes = {
        "47": [200, 400, 600, 1000, 2000, 5000],
        "56": [80, 150, 250, 400],
        "55": [300, 600, 1000, 2000, 5000],
        "10": [500, 1000, 2000, 5000, 10000],
        "25": [500, 1000, 2000, 4000, 8000],
        "62": [100, 200, 400, 800],
        "86": [300, 800, 1500, 3000, 5000],
    }
    vals = fourchettes.get(naf_prefix, [200, 500, 1000, 2000])
    return [{"value": v, "label": f"{v} m²"} for v in vals]


def _predict_energie(naf_prefix):
    """Énergies probables selon NAF."""
    if naf_prefix in ["10", "11", "25", "28"]:
        return [
            {"value": "gaz", "label": "Gaz naturel (le plus probable)"},
            {"value": "electricite", "label": "Électricité"},
            {"value": "fioul", "label": "Fioul"},
        ]
    return [
        {"value": "electricite", "label": "Électricité (le plus probable)"},
        {"value": "gaz", "label": "Gaz naturel"},
        {"value": "fioul", "label": "Fioul"},
    ]


def _predict_eclairage(naf_prefix):
    """Type d'éclairage probable."""
    return [
        {"value": "fluorescent", "label": "Tubes fluorescents (T8/T5)"},
        {"value": "halogene", "label": "Halogène / spots"},
        {"value": "led_partiel", "label": "LED partiel (mix)"},
        {"value": "led_complet", "label": "Déjà tout en LED (non éligible)"},
    ]


def _predict_nb_luminaires(naf_prefix, surface):
    """Estimation nombre de luminaires."""
    ratios = {"47": 7, "56": 8, "62": 12, "86": 10}
    ratio = ratios.get(naf_prefix, 10)
    base = max(1, int(surface / ratio)) if surface else 50
    return [
        {"value": max(1, int(base * 0.5)), "label": f"~{max(1, int(base * 0.5))} (petit site)"},
        {"value": base, "label": f"~{base} (estimation)"},
        {"value": int(base * 1.5), "label": f"~{int(base * 1.5)} (grand site)"},
    ]


def _predict_chauffage(naf_prefix, energie):
    """Type de chauffage probable."""
    options = [
        {"value": "chaudiere_gaz", "label": "Chaudière gaz"},
        {"value": "chaudiere_fioul", "label": "Chaudière fioul"},
        {"value": "radiateurs_elec", "label": "Radiateurs électriques"},
        {"value": "pac", "label": "Pompe à chaleur (déjà installée)"},
        {"value": "reseau_chaleur", "label": "Réseau de chaleur"},
    ]
    # Remonter l'option la plus probable
    if energie == "gaz":
        options = [o for o in options if o["value"] == "chaudiere_gaz"] + [o for o in options if o["value"] != "chaudiere_gaz"]
    elif energie == "fioul":
        options = [o for o in options if o["value"] == "chaudiere_fioul"] + [o for o in options if o["value"] != "chaudiere_fioul"]
    return options


def _predict_froid(naf_prefix):
    """Type de meubles froids."""
    if naf_prefix in ["47"]:
        return [
            {"value": "ouvert", "label": "Meubles ouverts (gros gisement CEE)"},
            {"value": "ferme", "label": "Meubles fermés (vitrines)"},
            {"value": "chambre_froide", "label": "Chambre froide"},
            {"value": "mix", "label": "Mix ouvert + fermé"},
        ]
    return [
        {"value": "chambre_froide", "label": "Chambre froide"},
        {"value": "vitrine", "label": "Vitrine réfrigérée"},
    ]


def _predict_nb_froid(naf_prefix, surface):
    """Estimation nombre d'équipements froid."""
    base = max(1, int(surface / 25)) if surface else 10
    return [
        {"value": max(1, int(base * 0.5)), "label": f"~{max(1, int(base * 0.5))}"},
        {"value": base, "label": f"~{base} (estimation)"},
        {"value": int(base * 2), "label": f"~{int(base * 2)} (gros site)"},
    ]


def _predict_puissance(naf_prefix, surface):
    """Estimation puissance installée."""
    ratios = {"10": 0.1, "25": 0.15, "28": 0.12}
    ratio = ratios.get(naf_prefix, 0.08)
    base = max(10, int(surface * ratio)) if surface else 50
    return [
        {"value": max(10, int(base * 0.5)), "label": f"{max(10, int(base * 0.5))} kW"},
        {"value": base, "label": f"{base} kW (estimation)"},
        {"value": int(base * 2), "label": f"{int(base * 2)} kW (gros site)"},
    ]


def _predict_nb_compresseurs(surface):
    base = max(1, int(surface / 800))
    return [
        {"value": max(1, base), "label": f"{max(1, base)} compresseur(s)"},
        {"value": max(2, base + 1), "label": f"{max(2, base + 1)} compresseurs"},
        {"value": max(3, base + 3), "label": f"{max(3, base + 3)} compresseurs (gros site)"},
    ]


def _predict_nb_moteurs(surface):
    base = max(1, int(surface / 400))
    return [
        {"value": max(1, base), "label": f"{max(1, base)} moteur(s)"},
        {"value": max(2, base * 2), "label": f"{max(2, base * 2)} moteurs"},
        {"value": max(5, base * 4), "label": f"{max(5, base * 4)} moteurs (gros site)"},
    ]


def _predict_activite(naf_prefix):
    """Activité détaillée selon NAF."""
    activites = {
        "47": [
            {"value": "supermarche", "label": "Supermarché / hypermarché"},
            {"value": "boutique", "label": "Boutique / commerce spécialisé"},
            {"value": "bricolage", "label": "Bricolage / jardinage"},
        ],
        "56": [
            {"value": "restaurant", "label": "Restaurant traditionnel"},
            {"value": "fast_food", "label": "Restauration rapide"},
            {"value": "cantine", "label": "Cantine / restauration collective"},
        ],
        "10": [
            {"value": "boulangerie_indus", "label": "Boulangerie industrielle"},
            {"value": "viande", "label": "Transformation viande"},
            {"value": "laiterie", "label": "Laiterie / fromagerie"},
            {"value": "conserverie", "label": "Conserverie"},
        ],
        "25": [
            {"value": "chaudronnerie", "label": "Chaudronnerie / soudure"},
            {"value": "usinage", "label": "Usinage / mécanique"},
            {"value": "assemblage", "label": "Assemblage"},
        ],
    }
    return activites.get(naf_prefix, [
        {"value": "tertiaire", "label": "Tertiaire / bureaux"},
        {"value": "industrie", "label": "Industrie"},
        {"value": "commerce", "label": "Commerce"},
    ])
