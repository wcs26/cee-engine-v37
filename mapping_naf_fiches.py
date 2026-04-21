"""
MAPPING NAF → FICHES CEE
Chaque fiche CEE est reliée aux codes APE éligibles.
Détection automatique des fiches pertinentes par code NAF.
"""

# ============================================================
# MAPPING FICHE → CODES NAF ELIGIBLES
# ============================================================
# Chaque fiche a ses NAF éligibles (prefix 2 ou 4 chiffres)
# "*" = tous secteurs

FICHE_NAF_MAP = {

    # ============================
    # AGRICULTURE (AGRI)
    # ============================
    "AGRI-EQ-101": {
        "naf": ["01"],
        "description": "Module integration temperature serre",
        "sous_activite": "serres",
    },
    "AGRI-EQ-102": {
        "naf": ["01"],
        "description": "Double ecran thermique serre",
        "sous_activite": "serres",
    },
    "AGRI-EQ-104": {
        "naf": ["01"],
        "description": "Ecrans thermiques lateraux serre",
        "sous_activite": "serres",
    },
    "AGRI-EQ-105": {
        "naf": ["01"],
        "description": "Stop & Start vehicule agricole",
        "sous_activite": "general",
    },
    "AGRI-EQ-106": {
        "naf": ["01"],
        "description": "Regulation ventilation silos",
        "sous_activite": "stockage",
    },
    "AGRI-EQ-107": {
        "naf": ["01"],
        "description": "Isolation parois serre",
        "sous_activite": "serres",
    },
    "AGRI-EQ-108": {
        "naf": ["01"],
        "description": "Stockage eau serre bioclimatique",
        "sous_activite": "serres",
    },
    "AGRI-EQ-109": {
        "naf": ["01"],
        "description": "Couverture performante serre",
        "sous_activite": "serres",
    },
    "AGRI-EQ-110": {
        "naf": ["01"],
        "description": "Sechage solaire produits agricoles",
        "sous_activite": "stockage",
    },
    "AGRI-EQ-111": {
        "naf": ["01"],
        "description": "Simple ecran thermique serre",
        "sous_activite": "serres",
    },
    "AGRI-EQ-112": {
        "naf": ["01"],
        "description": "Double paroi gonflable serre",
        "sous_activite": "serres",
    },
    "AGRI-SE-101": {
        "naf": ["01"],
        "description": "Controle reglage moteur tracteur",
        "sous_activite": "general",
    },
    "AGRI-TH-101": {
        "naf": ["01"],
        "description": "Stockage eau chaude Open Buffer serre",
        "sous_activite": "serres",
    },
    "AGRI-TH-102": {
        "naf": ["01"],
        "description": "Stockage eau chaude serre",
        "sous_activite": "serres",
    },
    "AGRI-TH-103": {
        "naf": ["0141", "0142", "0143", "0145", "0146", "0147"],
        "description": "Pre-refroidisseur de lait",
        "sous_activite": "elevage_laitier",
    },
    "AGRI-TH-104": {
        "naf": ["0141", "0142", "0143", "0145", "0146", "0147"],
        "description": "Recuperation chaleur groupe froid",
        "sous_activite": "elevage",
    },
    "AGRI-TH-105": {
        "naf": ["0141", "0142", "0143", "0145", "0146", "0147"],
        "description": "Recuperateur chaleur tank a lait",
        "sous_activite": "elevage_laitier",
    },
    "AGRI-TH-108": {
        "naf": ["01"],
        "description": "PAC air/eau ou eau/eau agricole",
        "sous_activite": "general",
    },
    "AGRI-TH-109": {
        "naf": ["01"],
        "description": "Recuperateur chaleur condensation serre",
        "sous_activite": "serres",
    },
    "AGRI-TH-110": {
        "naf": ["01"],
        "description": "Chaudiere haute performance serre",
        "sous_activite": "serres",
    },
    "AGRI-TH-113": {
        "naf": ["01"],
        "description": "Echangeur recuperateur chaleur air/air",
        "sous_activite": "elevage",
    },
    "AGRI-TH-117": {
        "naf": ["01"],
        "description": "Deshumidification thermodynamique serre",
        "sous_activite": "serres",
    },
    "AGRI-TH-118": {
        "naf": ["01"],
        "description": "Double tube chauffage serre",
        "sous_activite": "serres",
    },
    "AGRI-TH-119": {
        "naf": ["01"],
        "description": "Deshumidification air exterieur serre",
        "sous_activite": "serres",
    },
    "AGRI-UT-101": {
        "naf": ["01"],
        "description": "Moto-variateur synchrone agricole",
        "sous_activite": "general",
    },
    "AGRI-UT-102": {
        "naf": ["01"],
        "description": "Variateur electronique vitesse agricole",
        "sous_activite": "general",
    },
    "AGRI-UT-103": {
        "naf": ["01"],
        "description": "Regulation groupe froid positif agri",
        "sous_activite": "froid",
    },
    "AGRI-UT-104": {
        "naf": ["01"],
        "description": "Regulation groupe froid negatif agri",
        "sous_activite": "froid",
    },

    # ============================
    # BATIMENT TERTIAIRE (BAT)
    # ============================

    # Enveloppe
    "BAT-EN-101": {
        "naf": ["*"],
        "description": "Isolation combles/toiture tertiaire",
        "sous_activite": "enveloppe",
        "exclude_naf": ["01", "02", "03"],
    },
    "BAT-EN-102": {
        "naf": ["*"],
        "description": "Isolation murs tertiaire",
        "sous_activite": "enveloppe",
        "exclude_naf": ["01", "02", "03"],
    },
    "BAT-EN-103": {
        "naf": ["*"],
        "description": "Isolation plancher tertiaire",
        "sous_activite": "enveloppe",
        "exclude_naf": ["01", "02", "03"],
    },
    "BAT-EN-104": {
        "naf": ["*"],
        "description": "Fenetre vitrage isolant tertiaire",
        "sous_activite": "enveloppe",
        "exclude_naf": ["01", "02", "03"],
    },
    "BAT-EN-106": {
        "naf": ["*"],
        "description": "Isolation combles (variante)",
        "sous_activite": "enveloppe",
    },
    "BAT-EN-107": {
        "naf": ["*"],
        "description": "Isolation toitures-terrasses",
        "sous_activite": "enveloppe",
    },
    "BAT-EN-108": {
        "naf": ["*"],
        "description": "Isolation murs outre-mer",
        "sous_activite": "enveloppe_om",
        "zone": ["OM"],
    },
    "BAT-EN-109": {
        "naf": ["*"],
        "description": "Reduction apports solaires toiture outre-mer",
        "sous_activite": "enveloppe_om",
        "zone": ["OM"],
    },
    "BAT-EN-111": {
        "naf": ["*"],
        "description": "Fenetre vitrage parieto-dynamique",
        "sous_activite": "enveloppe",
    },
    "BAT-EN-112": {
        "naf": ["*"],
        "description": "Revetements reflectifs toiture",
        "sous_activite": "enveloppe",
    },
    "BAT-EN-113": {
        "naf": ["*"],
        "description": "Facade rideau vitrage isolant",
        "sous_activite": "enveloppe",
    },

    # Equipements
    "BAT-EQ-117": {
        "naf": ["10", "11", "46", "47", "52", "55", "56"],
        "description": "Installation frigo CO2 subcritique",
        "sous_activite": "froid",
    },
    "BAT-EQ-124": {
        "naf": ["47"],
        "description": "Fermeture meubles frigo temp positive",
        "sous_activite": "froid_commercial",
    },
    "BAT-EQ-125": {
        "naf": ["47"],
        "description": "Fermeture meubles frigo temp negative",
        "sous_activite": "froid_commercial",
    },
    "BAT-EQ-127": {
        "naf": ["*"],
        "description": "Luminaire LED tertiaire",
        "sous_activite": "eclairage",
        "exclude_naf": ["01", "02", "03"],
    },
    "BAT-EQ-129": {
        "naf": ["*"],
        "description": "Lanterneaux eclairage zenithal",
        "sous_activite": "eclairage",
    },
    "BAT-EQ-130": {
        "naf": ["10", "11", "46", "47", "52", "55", "56"],
        "description": "Condensation frigo haute efficacite",
        "sous_activite": "froid",
    },
    "BAT-EQ-131": {
        "naf": ["*"],
        "description": "Conduits lumiere naturelle",
        "sous_activite": "eclairage",
    },
    "BAT-EQ-134": {
        "naf": ["47"],
        "description": "Meuble frigo performant",
        "sous_activite": "froid_commercial",
    },
    "BAT-EQ-135": {
        "naf": ["62", "63"],
        "description": "Alimentation sans interruption performante",
        "sous_activite": "datacenter",
    },

    # Thermique
    "BAT-TH-103": {
        "naf": ["*"],
        "description": "Plancher chauffant basse temperature",
        "sous_activite": "chauffage",
        "exclude_naf": ["01", "02", "03"],
    },
    "BAT-TH-104": {
        "naf": ["*"],
        "description": "PAC air/eau tertiaire",
        "sous_activite": "chauffage",
        "exclude_naf": ["01", "02", "03"],
    },
    "BAT-TH-105": {
        "naf": ["*"],
        "description": "Radiateur basse temperature",
        "sous_activite": "chauffage",
    },
    "BAT-TH-108": {
        "naf": ["*"],
        "description": "Regulation programmation intermittence",
        "sous_activite": "regulation",
    },
    "BAT-TH-109": {
        "naf": ["*"],
        "description": "Optimiseur relance chauffage collectif",
        "sous_activite": "regulation",
    },
    "BAT-TH-110": {
        "naf": ["*"],
        "description": "Recuperateur chaleur condensation",
        "sous_activite": "chauffage",
    },
    "BAT-TH-111": {
        "naf": ["*"],
        "description": "Chauffe-eau solaire collectif",
        "sous_activite": "ecs",
    },
    "BAT-TH-112": {
        "naf": ["*"],
        "description": "Variateur vitesse pompe chauffage",
        "sous_activite": "chauffage",
    },
    "BAT-TH-115": {
        "naf": ["*"],
        "description": "Climatiseur performant",
        "sous_activite": "climatisation",
    },
    "BAT-TH-116": {
        "naf": ["*"],
        "description": "GTB chauffage",
        "sous_activite": "gtb",
        "exclude_naf": ["01", "02", "03"],
    },
    "BAT-TH-122": {
        "naf": ["*"],
        "description": "Programmateur intermittence climatisation",
        "sous_activite": "climatisation",
    },
    "BAT-TH-125": {
        "naf": ["*"],
        "description": "VMC simple flux",
        "sous_activite": "ventilation",
    },
    "BAT-TH-126": {
        "naf": ["*"],
        "description": "VMC double flux echangeur",
        "sous_activite": "ventilation",
    },
    "BAT-TH-127": {
        "naf": ["*"],
        "description": "Raccordement reseau chaleur tertiaire",
        "sous_activite": "chauffage",
    },
    "BAT-TH-134": {
        "naf": ["10", "11", "46", "47", "52", "55", "56"],
        "description": "Regulation groupe froid positif",
        "sous_activite": "froid",
    },
    "BAT-TH-135": {
        "naf": ["10", "11", "46", "47", "52", "55", "56"],
        "description": "Regulation groupe froid negatif",
        "sous_activite": "froid",
    },
    "BAT-TH-139": {
        "naf": ["10", "11", "46", "47", "52", "55", "56"],
        "description": "Recuperation chaleur groupe froid",
        "sous_activite": "froid",
    },
    "BAT-TH-142": {
        "naf": ["*"],
        "description": "Destratification air",
        "sous_activite": "chauffage",
    },
    "BAT-TH-143": {
        "naf": ["*"],
        "description": "Ventilo-convecteurs haute performance",
        "sous_activite": "chauffage",
    },
    "BAT-TH-145": {
        "naf": ["*"],
        "description": "GTB chauffage + climatisation",
        "sous_activite": "gtb",
        "exclude_naf": ["01", "02", "03"],
    },
    "BAT-TH-153": {
        "naf": ["62", "63"],
        "description": "Confinement allees datacenter",
        "sous_activite": "datacenter",
    },
    "BAT-TH-154": {
        "naf": ["*"],
        "description": "Recuperation chaleur eaux grises",
        "sous_activite": "ecs",
    },
    "BAT-TH-156": {
        "naf": ["62", "63"],
        "description": "Freecooling datacenter",
        "sous_activite": "datacenter",
    },
    "BAT-TH-157": {
        "naf": ["*"],
        "description": "Chaudiere biomasse collective tertiaire",
        "sous_activite": "chauffage",
    },
    "BAT-TH-158": {
        "naf": ["*"],
        "description": "PAC reversible air/air outre-mer",
        "sous_activite": "climatisation_om",
        "zone": ["OM"],
    },
    "BAT-TH-159": {
        "naf": ["*"],
        "description": "Raccordement reseau froid tertiaire",
        "sous_activite": "climatisation",
    },
    "BAT-TH-161": {
        "naf": ["*"],
        "description": "Maintien temperature groupe electrogene",
        "sous_activite": "equipement",
    },
    "BAT-TH-162": {
        "naf": ["*"],
        "description": "Systeme geothermique",
        "sous_activite": "chauffage",
    },
    "BAT-TH-163": {
        "naf": ["*"],
        "description": "PAC air/eau tertiaire",
        "sous_activite": "chauffage",
    },
    "BAT-TH-164": {
        "naf": ["*"],
        "description": "PAC eau/eau geothermie",
        "sous_activite": "chauffage",
    },
    "BAT-SE-103": {
        "naf": ["*"],
        "description": "Reglage equilibrage installation chauffage",
        "sous_activite": "regulation",
    },
    "BAT-SE-104": {
        "naf": ["*"],
        "description": "CPE Services",
        "sous_activite": "services",
    },
    "BAT-SE-105": {
        "naf": ["*"],
        "description": "Abaissement temperature retour reseau",
        "sous_activite": "regulation",
    },

    # ============================
    # INDUSTRIE (IND)
    # ============================
    "IND-BA-110": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Destratification air industrie",
        "sous_activite": "batiment",
    },
    "IND-BA-113": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Lanterneaux eclairage zenithal industrie",
        "sous_activite": "eclairage",
    },
    "IND-BA-114": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Conduits lumiere naturelle industrie",
        "sous_activite": "eclairage",
    },
    "IND-BA-116": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "LED industrie",
        "sous_activite": "eclairage",
    },
    "IND-BA-117": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Chauffage decentralise performant",
        "sous_activite": "chauffage",
    },
    "IND-EN-101": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Isolation murs industrie outre-mer",
        "sous_activite": "enveloppe_om",
        "zone": ["OM"],
    },
    "IND-EN-102": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Isolation combles industrie outre-mer",
        "sous_activite": "enveloppe_om",
        "zone": ["OM"],
    },
    "IND-UT-102": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Variateur vitesse industrie",
        "sous_activite": "moteurs",
    },
    "IND-UT-103": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Recuperation chaleur compresseur air",
        "sous_activite": "air_comprime",
    },
    "IND-UT-104": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Economiseur effluents gazeux",
        "sous_activite": "process",
    },
    "IND-UT-105": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Bruleur micro-modulant chaudiere",
        "sous_activite": "chaudiere",
    },
    "IND-UT-113": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Condensation frigo haute efficacite",
        "sous_activite": "froid",
    },
    "IND-UT-114": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Moto-variateur synchrone industrie",
        "sous_activite": "moteurs",
    },
    "IND-UT-115": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Regulation groupe froid positif industrie",
        "sous_activite": "froid",
    },
    "IND-UT-116": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Regulation groupe froid negatif industrie",
        "sous_activite": "froid",
    },
    "IND-UT-117": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Recuperation chaleur compresseur",
        "sous_activite": "air_comprime",
    },
    "IND-UT-118": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Bruleur recuperation chaleur",
        "sous_activite": "chaudiere",
    },
    "IND-UT-120": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Compresseur air basse pression",
        "sous_activite": "air_comprime",
    },
    "IND-UT-122": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Secheur air comprime adsorption",
        "sous_activite": "air_comprime",
    },
    "IND-UT-124": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Sequenceur electronique air comprime",
        "sous_activite": "air_comprime",
    },
    "IND-UT-125": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Traitement eau chaudiere",
        "sous_activite": "chaudiere",
    },
    "IND-UT-129": {
        "naf": ["22"],
        "description": "Presse injecter tout electrique",
        "sous_activite": "plasturgie",
    },
    "IND-UT-130": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Condenseur effluents gazeux",
        "sous_activite": "process",
    },
    "IND-UT-131": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Isolation thermique parois industrielles",
        "sous_activite": "isolation",
    },
    "IND-UT-132": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Moteur IE4",
        "sous_activite": "moteurs",
    },
    "IND-UT-133": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Pilotage electronique moteur",
        "sous_activite": "moteurs",
    },
    "IND-UT-134": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "46", "47", "52"],
        "description": "Mesurage indicateurs performance energetique",
        "sous_activite": "management",
    },
    "IND-UT-135": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Freecooling industrie",
        "sous_activite": "froid",
    },
    "IND-UT-137": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "PAC industrie",
        "sous_activite": "chauffage",
    },
    "IND-UT-138": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Conversion chaleur fatale en electricite",
        "sous_activite": "chaleur_fatale",
    },
    "IND-UT-139": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Stockage chaleur fatale",
        "sous_activite": "chaleur_fatale",
    },
    "IND-UT-140": {
        "naf": ["10", "11", "13", "14", "15", "16", "17", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33"],
        "description": "Mise en veille automatique machine",
        "sous_activite": "process",
    },

    # ============================
    # RESEAU (RES)
    # ============================
    "RES-CH-103": {
        "naf": ["35"],
        "description": "Rehab poste livraison chaleur",
        "sous_activite": "reseau",
    },
    "RES-CH-104": {
        "naf": ["35"],
        "description": "Rehab poste livraison chaleur (variante)",
        "sous_activite": "reseau",
    },
    "RES-CH-105": {
        "naf": ["35"],
        "description": "Passage basse temperature reseau",
        "sous_activite": "reseau",
    },
    "RES-CH-106": {
        "naf": ["35"],
        "description": "Calorifugeage canalisations reseau",
        "sous_activite": "reseau",
    },
    "RES-CH-108": {
        "naf": ["35"],
        "description": "Recuperation chaleur fatale reseau",
        "sous_activite": "reseau",
    },
    "RES-EC-104": {
        "naf": ["*"],
        "description": "Renovation eclairage exterieur",
        "sous_activite": "eclairage",
    },

    # ============================
    # TRANSPORT (TRA) - voir fiches détaillées ci-dessus
    # ============================
    "TRA-EQ-101": {"naf": ["49", "50", "51", "52", "53"], "description": "Transport intermodal combine", "sous_activite": "intermodal"},
    "TRA-EQ-103": {"naf": ["49", "50", "51", "52", "53"], "description": "Telematique embarquee", "sous_activite": "routier"},
    "TRA-EQ-104": {"naf": ["*"], "description": "Lubrifiant eco VL", "sous_activite": "routier"},
    "TRA-EQ-106": {"naf": ["*"], "description": "Pneus basse resistance VL", "sous_activite": "routier"},
    "TRA-EQ-107": {"naf": ["49", "50", "51", "52", "53"], "description": "Transport intermodal (variante)", "sous_activite": "intermodal"},
    "TRA-EQ-108": {"naf": ["49"], "description": "Wagon autoroute ferroviaire", "sous_activite": "ferroviaire"},
    "TRA-EQ-109": {"naf": ["50"], "description": "Barge fluviale", "sous_activite": "fluvial"},
    "TRA-EQ-110": {"naf": ["50"], "description": "Automoteur fluvial", "sous_activite": "fluvial"},
    "TRA-EQ-111": {"naf": ["49", "52"], "description": "Groupe frigo transport haute efficacite", "sous_activite": "froid_transport"},
    "TRA-EQ-113": {"naf": ["49", "52", "53"], "description": "Lubrifiant eco PL", "sous_activite": "routier"},
    "TRA-EQ-114": {"naf": ["*"], "description": "Vehicule leger electrique neuf", "sous_activite": "electrique"},
    "TRA-EQ-115": {"naf": ["49", "52", "53"], "description": "Vehicule transport marchandises optimise", "sous_activite": "routier"},
    "TRA-EQ-117": {"naf": ["*"], "description": "Vehicule leger electrique occasion", "sous_activite": "electrique"},
    "TRA-EQ-118": {"naf": ["03"], "description": "Lubrifiant eco peche", "sous_activite": "maritime"},
    "TRA-EQ-119": {"naf": ["50"], "description": "Optimisation combustion navire", "sous_activite": "maritime"},
    "TRA-EQ-120": {"naf": ["50"], "description": "Helice tuyere fluvial", "sous_activite": "fluvial"},
    "TRA-EQ-121": {"naf": ["*"], "description": "Velo assistance electrique", "sous_activite": "mobilite_douce"},
    "TRA-EQ-122": {"naf": ["*"], "description": "Stop Start engin non routier", "sous_activite": "engins"},
    "TRA-EQ-123": {"naf": ["49", "52", "53"], "description": "Simulateur conduite", "sous_activite": "formation"},
    "TRA-EQ-124": {"naf": ["50", "52"], "description": "Branchement electrique quai", "sous_activite": "maritime"},
    "TRA-EQ-125": {"naf": ["49"], "description": "Stop Start ferroviaire", "sous_activite": "ferroviaire"},
    "TRA-EQ-126": {"naf": ["50"], "description": "Remotorisation electrique navire", "sous_activite": "fluvial"},
    "TRA-EQ-127": {"naf": ["50"], "description": "Bateau electrique neuf", "sous_activite": "fluvial"},
    "TRA-EQ-128": {"naf": ["49"], "description": "Autocar autobus electrique", "sous_activite": "transport_commun"},
    "TRA-EQ-129": {"naf": ["49", "52", "53"], "description": "Vehicule lourd electrique", "sous_activite": "electrique"},
    "TRA-EQ-130": {"naf": ["*"], "description": "Quadricycle electrique", "sous_activite": "electrique"},
    "TRA-EQ-131": {"naf": ["*"], "description": "Achat location longue duree eco", "sous_activite": "general"},
    "TRA-EQ-132": {"naf": ["50"], "description": "Mesure analyse optimisation navire", "sous_activite": "maritime"},
    "TRA-SE-101": {"naf": ["49", "52", "53"], "description": "Formation eco-conduite PL", "sous_activite": "formation"},
    "TRA-SE-102": {"naf": ["*"], "description": "Formation eco-conduite VL", "sous_activite": "formation"},
    "TRA-SE-104": {"naf": ["*"], "description": "Station gonflage pneumatiques", "sous_activite": "routier"},
    "TRA-SE-105": {"naf": ["49", "52", "53"], "description": "Recreusage pneumatiques", "sous_activite": "routier"},
    "TRA-SE-106": {"naf": ["49", "52", "53"], "description": "Mesure optimisation conso carburant PL", "sous_activite": "routier"},
    "TRA-SE-107": {"naf": ["50"], "description": "Carenage fluvial", "sous_activite": "fluvial"},
    "TRA-SE-108": {"naf": ["49", "52", "53"], "description": "Gestion externalisee pneus PL", "sous_activite": "routier"},
    "TRA-SE-109": {"naf": ["*"], "description": "Gestion externalisee pneus VL", "sous_activite": "routier"},
    "TRA-SE-110": {"naf": ["49", "52", "53"], "description": "Gestion optimisee pneus PL", "sous_activite": "routier"},
    "TRA-SE-111": {"naf": ["*"], "description": "Gestion optimisee pneus VL", "sous_activite": "routier"},
    "TRA-SE-112": {"naf": ["*"], "description": "Autopartage boucle", "sous_activite": "mobilite_douce"},
    "TRA-SE-113": {"naf": ["49", "52", "53"], "description": "Suivi conso carburant", "sous_activite": "routier"},
    "TRA-SE-116": {"naf": ["49"], "description": "Fret ferroviaire", "sous_activite": "ferroviaire"},
    "TRA-SE-117": {"naf": ["50"], "description": "Fret fluvial", "sous_activite": "fluvial"},
}


# ============================================================
# FONCTION DE DETECTION
# ============================================================

def get_fiches_for_naf(naf_code):
    """
    Retourne toutes les fiches CEE éligibles pour un code NAF donné.
    """
    prefix2 = naf_code[:2]
    prefix4 = naf_code[:4] if len(naf_code) >= 4 else ""

    fiches_eligibles = []

    for ref, mapping in FICHE_NAF_MAP.items():
        naf_list = mapping.get("naf", [])
        exclude = mapping.get("exclude_naf", [])

        # Vérifier exclusion
        if prefix2 in exclude:
            continue

        # Vérifier éligibilité
        eligible = False
        if "*" in naf_list:
            eligible = True
        elif prefix2 in naf_list:
            eligible = True
        elif prefix4 in naf_list:
            eligible = True

        if eligible:
            fiches_eligibles.append({
                "ref": ref,
                "description": mapping.get("description", ""),
                "sous_activite": mapping.get("sous_activite", ""),
            })

    return fiches_eligibles


def print_fiches_for_naf(naf_code):
    """Affiche toutes les fiches pour un code NAF."""
    fiches = get_fiches_for_naf(naf_code)
    print(f"\nNAF {naf_code}: {len(fiches)} fiches CEE eligibles\n")

    # Grouper par sous-activité
    groups = {}
    for f in fiches:
        sa = f["sous_activite"]
        groups.setdefault(sa, []).append(f)

    for sa in sorted(groups):
        print(f"  {sa.upper()}:")
        for f in groups[sa]:
            print(f"    {f['ref']:15} {f['description']}")
    print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print_fiches_for_naf(sys.argv[1])
    else:
        # Démo
        for naf in ["0113Z", "0141Z", "4711D", "2562A", "4941A", "5610A", "6201Z", "3530Z"]:
            fiches = get_fiches_for_naf(naf)
            print(f"  {naf}: {len(fiches)} fiches")
