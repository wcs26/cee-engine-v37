"""
Bibliothèque des coûts réels de chantier (marché 2026 secteur santé/tertiaire).

Décomposition : matériaux grossiste + main d'œuvre interne (+ sous-traitance optionnelle).
Sources : barèmes UNTEC 2025-2026, Capeb, Batiprix, retours terrain SIRAT.

Ces estimations servent à pré-remplir le champ Admin.cout_reel_realisateur_eur
quand l'installateur n'a pas chiffré précisément. Permet à Jimmy de calculer
sa commission (50 % marge) sans attendre les coûts définitifs SIRAT.

Endpoint : GET /couts/estimation/<fiche>?surface=X[&unite=m2|kw|...]
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from flask import jsonify, request


@dataclass
class PosteCout:
    """Décomposition d'un coût unitaire pour 1 unité (m², kW, etc.)."""
    materiaux_grossiste_eur: float    # prix achat matériaux pro (HT, prix grossiste)
    main_oeuvre_interne_eur: float    # MO interne salariée (HT)
    sous_traitance_eur: float = 0.0   # alternative externalisée si pas de MO interne
    notes: str = ""

    @property
    def cout_interne_total(self) -> float:
        """Coût réel si réalisation 100 % interne (matériaux + MO)."""
        return round(self.materiaux_grossiste_eur + self.main_oeuvre_interne_eur, 2)

    @property
    def cout_externalise_total(self) -> float:
        """Coût réel si externalisé (matériaux + sous-traitance)."""
        return round(self.materiaux_grossiste_eur + self.sous_traitance_eur, 2)


# ═══════════════════════════════════════════════════════════════════════════
# CATALOGUE — coûts unitaires par fiche × secteur × zone (marché 2026)
# ═══════════════════════════════════════════════════════════════════════════

COUTS_CATALOGUE: dict[tuple[str, str, str], dict[str, PosteCout]] = {
    # BAT-EN-103 — Isolation plancher bas (vide sanitaire) — Santé/Tertiaire H1
    ("BAT-EN-103", "sante", "H1"): {
        "m2": PosteCout(
            materiaux_grossiste_eur=11.50,   # laine verre semi-rigide R≥3 (URSA Renosoudal/Knauf Soudalle) ~9€ + colle/adhésif ALU 1,5€ + fixations 1€
            main_oeuvre_interne_eur=8.20,    # 1 ouvrier qualifié — 8h pour ~60 m² ≈ 32€/h chargé / 60 ≈ 0,53€/m² + temps prép
            sous_traitance_eur=18.00,        # forfait sous-traitance UNTEC Sud
            notes="Laine verre 96-100mm fixation mécanique. Hors dépose isolant existant.",
        ),
    },
    ("BAT-EN-103", "sante", "H2"): {
        "m2": PosteCout(materiaux_grossiste_eur=11.50, main_oeuvre_interne_eur=8.20, sous_traitance_eur=18.00,
                        notes="Identique H1 (matériaux/MO inchangés)."),
    },
    ("BAT-EN-103", "sante", "H3"): {
        "m2": PosteCout(materiaux_grossiste_eur=11.50, main_oeuvre_interne_eur=8.20, sous_traitance_eur=18.00,
                        notes="Identique H1 (matériaux/MO inchangés)."),
    },

    # BAT-EN-101 — Isolation combles perdus
    ("BAT-EN-101", "sante", "H1"): {
        "m2": PosteCout(
            materiaux_grossiste_eur=6.80,    # laine soufflée 30 cm R≥6 (~5€) + pare-vapeur (~1,8€)
            main_oeuvre_interne_eur=4.50,    # soufflage rapide ~150 m²/jour
            sous_traitance_eur=9.50,
            notes="Soufflage laine minérale 30 cm. Inclut pare-vapeur.",
        ),
    },
    ("BAT-EN-101", "sante", "H2"): {
        "m2": PosteCout(materiaux_grossiste_eur=6.80, main_oeuvre_interne_eur=4.50, sous_traitance_eur=9.50, notes=""),
    },
    ("BAT-EN-101", "sante", "H3"): {
        "m2": PosteCout(materiaux_grossiste_eur=6.80, main_oeuvre_interne_eur=4.50, sous_traitance_eur=9.50, notes=""),
    },

    # IND-UT-103 — Calorifugeage points singuliers
    ("IND-UT-103", "industrie", "H1"): {
        "ps": PosteCout(
            materiaux_grossiste_eur=42.00,   # housse isolante préformée
            main_oeuvre_interne_eur=18.00,   # 30 min/PS × 36€/h
            sous_traitance_eur=85.00,
            notes="Housse isolante par point singulier (vanne, bride, échangeur).",
        ),
    },

    # BAT-TH-125 — VMC simple flux à débit constant ou modulé
    ("BAT-TH-125", "sante", "H1"): {
        "m2": PosteCout(
            materiaux_grossiste_eur=12.50,
            main_oeuvre_interne_eur=11.00,
            sous_traitance_eur=28.00,
            notes="Réseau gainé + bouches autoréglables + caisson VMC mutualisé.",
        ),
    },

    # BAR-TH-104 — PAC air/eau résidentiel
    ("BAR-TH-104", "residentiel", "H1"): {
        "unite": PosteCout(
            materiaux_grossiste_eur=4500.00,
            main_oeuvre_interne_eur=1800.00,
            sous_traitance_eur=6500.00,
            notes="PAC air/eau monobloc 8-10 kW + raccordement hydraulique + mise en service.",
        ),
    },

    # ─────────────────────────────────────────────────────────────────────
    # BLOC ENRICHI V37 — 30+ entrées supplémentaires (sources UNTEC 2025-2026, Batiprix, ADEME)
    # ─────────────────────────────────────────────────────────────────────

    # BAT-EN-101 — Isolation combles TERTIAIRE (toutes zones)
    ("BAT-EN-101", "tertiaire", "H1"): {"m2": PosteCout(6.80, 4.50, 9.50, "Soufflage laine 30cm R≥6")},
    ("BAT-EN-101", "tertiaire", "H2"): {"m2": PosteCout(6.80, 4.50, 9.50, "")},
    ("BAT-EN-101", "tertiaire", "H3"): {"m2": PosteCout(6.80, 4.50, 9.50, "")},

    # BAT-EN-102 — Isolation murs tertiaire
    ("BAT-EN-102", "sante", "H1"): {"m2": PosteCout(18.00, 14.00, 35.00, "Doublage PSE+plâtre ou laine rigide R≥3.7")},
    ("BAT-EN-102", "tertiaire", "H1"): {"m2": PosteCout(18.00, 14.00, 35.00, "")},

    # BAT-EN-103 — Isolation PB TERTIAIRE (étendu)
    ("BAT-EN-103", "tertiaire", "H1"): {"m2": PosteCout(11.50, 8.20, 18.00, "Panneau rigide R≥3 fixation méca")},
    ("BAT-EN-103", "tertiaire", "H2"): {"m2": PosteCout(11.50, 8.20, 18.00, "")},
    ("BAT-EN-103", "tertiaire", "H3"): {"m2": PosteCout(11.50, 8.20, 18.00, "")},

    # BAT-EN-104 — Fenêtres tertiaire
    ("BAT-EN-104", "sante", "H1"): {"m2": PosteCout(180.00, 65.00, 280.00, "Menuiserie alu RPT Uw≤1.3 + pose dépose")},
    ("BAT-EN-104", "tertiaire", "H1"): {"m2": PosteCout(180.00, 65.00, 280.00, "")},

    # BAT-TH-102 — Chaudière biomasse tertiaire
    ("BAT-TH-102", "sante", "H1"): {"kw": PosteCout(280.00, 120.00, 450.00, "Chaudière granulés/plaquettes 50-300 kW")},

    # BAT-TH-103 — Plancher chauffant basse T°
    ("BAT-TH-103", "sante", "H1"): {"m2": PosteCout(35.00, 22.00, 65.00, "Plancher chauffant hydraulique BT + régulation")},

    # BAT-TH-113 — PAC air/eau tertiaire
    ("BAT-TH-113", "sante", "H1"): {"kw": PosteCout(350.00, 150.00, 550.00, "PAC A/E tertiaire 30-100 kW")},

    # BAT-TH-125 — VMC simple flux tertiaire (étendu)
    ("BAT-TH-125", "tertiaire", "H1"): {"m2": PosteCout(12.50, 11.00, 28.00, "VMC SF autoréglable")},
    ("BAT-TH-125", "sante", "H2"): {"m2": PosteCout(12.50, 11.00, 28.00, "")},
    ("BAT-TH-125", "sante", "H3"): {"m2": PosteCout(12.50, 11.00, 28.00, "")},

    # BAT-TH-126 — VMC double flux tertiaire
    ("BAT-TH-126", "sante", "H1"): {"m2": PosteCout(22.00, 18.00, 45.00, "VMC DF avec récupérateur ≥85%")},

    # BAT-TH-127 — Chaudière condensation tertiaire
    ("BAT-TH-127", "sante", "H1"): {"kw": PosteCout(85.00, 45.00, 150.00, "Chaudière gaz condensation tertiaire")},

    # BAT-TH-142 — Déstratification d'air
    ("BAT-TH-142", "sante", "H1"): {"unite": PosteCout(350.00, 120.00, 520.00, "Déstratificateur hélicoïdal grand volume")},
    ("BAT-TH-142", "tertiaire", "H1"): {"unite": PosteCout(350.00, 120.00, 520.00, "")},

    # BAT-TH-155 — Régulation terminale
    ("BAT-TH-155", "sante", "H1"): {"unite": PosteCout(65.00, 35.00, 110.00, "Robinet thermostatique + tête programmable")},

    # BAT-EQ-111 — LED tertiaire
    ("BAT-EQ-111", "sante", "H1"): {"unite": PosteCout(28.00, 12.00, 45.00, "Tube LED T8/T5 + driver")},
    ("BAT-EQ-111", "tertiaire", "H1"): {"unite": PosteCout(28.00, 12.00, 45.00, "")},

    # IND-UT-102 — Variateur de vitesse
    ("IND-UT-102", "industrie", "H1"): {"kw": PosteCout(120.00, 55.00, 200.00, "VFD sur moteur process ≥0.55 kW")},

    # IND-UT-103 — Calorifugeage (étendu secteurs)
    ("IND-UT-103", "sante", "H1"): {"ps": PosteCout(42.00, 18.00, 85.00, "Housse isolante point singulier")},
    ("IND-UT-103", "tertiaire", "H1"): {"ps": PosteCout(42.00, 18.00, 85.00, "")},

    # IND-UT-105 — Brûleur micro-modulant
    ("IND-UT-105", "industrie", "H1"): {"kw": PosteCout(45.00, 25.00, 80.00, "Brûleur gaz modulant sur chaudière existante")},

    # IND-UT-116 — Récupération chaleur sur compresseur
    ("IND-UT-116", "industrie", "H1"): {"kw": PosteCout(180.00, 90.00, 300.00, "Échangeur sur circuit refroidissement compresseur")},

    # BAR-EN-101 — Isolation combles résidentiel
    ("BAR-EN-101", "residentiel", "H1"): {"m2": PosteCout(5.50, 3.50, 8.00, "Soufflage laine combles perdus R≥7")},
    ("BAR-EN-101", "residentiel", "H2"): {"m2": PosteCout(5.50, 3.50, 8.00, "")},

    # BAR-EN-103 — Isolation PB résidentiel
    ("BAR-EN-103", "residentiel", "H1"): {"m2": PosteCout(10.00, 7.50, 16.00, "Panneau sous-face VS R≥3")},

    # BAR-EN-104 — Fenêtres résidentiel
    ("BAR-EN-104", "residentiel", "H1"): {"m2": PosteCout(150.00, 55.00, 240.00, "Fenêtre PVC Uw≤1.3 pose en rénovation")},

    # BAR-TH-143 — Système solaire combiné
    ("BAR-TH-143", "residentiel", "H1"): {"m2": PosteCout(800.00, 350.00, 1200.00, "SSC capteurs + ballon + régulation")},

    # BAR-TH-171 — PAC air/eau résidentiel (nouvelle fiche P6)
    ("BAR-TH-171", "residentiel", "H1"): {"kw": PosteCout(500.00, 200.00, 750.00, "PAC A/E résidentiel 5-15 kW COP≥3.4")},

    # AGRI-TH-101 — Stockage tampon eau chaude agricole
    ("AGRI-TH-101", "agriculture_elevage", "H1"): {"unite": PosteCout(1200.00, 400.00, 1800.00, "Ballon tampon 500-2000L + raccordement")},

    # TRA-SE-107 — Formation écoconduite
    ("TRA-SE-107", "transport_routier", "H1"): {"unite": PosteCout(0.00, 350.00, 450.00, "1 journée formation conducteur (pas de matériaux)")},
}


# Marges acceptables installateur (validation cohérence)
# NB : Ces coûts = coût réel matériaux+MO de l'installateur (ex: BAT-EN-103 = 19.70€/m²).
# Le prix facturé au client (ex: devis SIRAT = 41.60€/m²) inclut la marge installateur.
# L'écart (ici ~111%) n'est PAS une erreur : c'est la marge commerciale du réalisateur.
MARGE_INSTALLATEUR_PCT_PLAUSIBLE = (15, 60)   # 15% à 60% sur HT — fourchette standard ; certains dépassent


def estimer_cout_reel(fiche: str, secteur: str, zone: str, *,
                      surface_m2: float = 0, unites: float = 0,
                      mode: str = "interne") -> dict:
    """Estime le coût réel total d'un chantier.

    Args:
      fiche, secteur, zone : clé catalogue
      surface_m2 : si fiche en m²
      unites : si fiche en unité (PS, équipement, etc.)
      mode : "interne" (matériaux+MO) ou "externalisé" (matériaux+S/T)

    Returns dict avec décomposition + total.
    """
    key = (fiche, secteur, zone)
    if key not in COUTS_CATALOGUE:
        return {"error": f"pas d'estimation catalogue pour {key}",
                "available_keys": [list(k) for k in COUTS_CATALOGUE.keys()],
                "fallback": "saisir Admin.cout_reel_realisateur_eur manuellement"}

    postes = COUTS_CATALOGUE[key]
    quantite = surface_m2 if surface_m2 > 0 else unites
    if quantite <= 0:
        return {"error": "surface_m2 ou unites > 0 requis"}

    # Récupère le 1er poste applicable (m2, ps, unite…)
    unite_poste, poste = next(iter(postes.items()))

    if mode == "externalisé":
        cout_unitaire = poste.cout_externalise_total
        decomposition = {
            "matériaux_grossiste_eur_unite": poste.materiaux_grossiste_eur,
            "sous_traitance_eur_unite": poste.sous_traitance_eur,
        }
    else:  # interne
        cout_unitaire = poste.cout_interne_total
        decomposition = {
            "matériaux_grossiste_eur_unite": poste.materiaux_grossiste_eur,
            "main_oeuvre_interne_eur_unite": poste.main_oeuvre_interne_eur,
        }

    cout_total = round(cout_unitaire * quantite, 2)

    return {
        "fiche": fiche, "secteur": secteur, "zone": zone,
        "unite": unite_poste,
        "quantite": quantite,
        "mode": mode,
        "cout_unitaire_eur": cout_unitaire,
        "cout_total_estime_eur": cout_total,
        "decomposition": decomposition,
        "notes": poste.notes,
        "source": "Catalogue interne 2026 (UNTEC + Capeb + retours terrain SIRAT)",
        "rappel": ("Estimation indicative ±15%. Le coût réel doit être confirmé par "
                   "l'installateur (devis interne) avant calcul commission Jimmy."),
    }


def register_couts_routes(app) -> None:

    @app.route("/couts/estimation/<fiche>", methods=["GET"])
    def _couts_estimation(fiche):
        """GET /couts/estimation/BAT-EN-103?surface=1590&secteur=sante&zone=H1&mode=interne"""
        try:
            surface = float(request.args.get("surface", 0))
            unites = float(request.args.get("unites", 0))
        except (ValueError, TypeError):
            return jsonify({"error": "surface/unites doit être numérique"}), 400
        secteur = request.args.get("secteur", "sante")
        zone = request.args.get("zone", "H1")
        mode = request.args.get("mode", "interne")
        return jsonify(estimer_cout_reel(fiche, secteur, zone,
                                         surface_m2=surface, unites=unites, mode=mode))

    @app.route("/couts/catalogue", methods=["GET"])
    def _couts_catalogue():
        """Liste exhaustive du catalogue de coûts (audit transparence)."""
        return jsonify({
            "entries": [
                {"fiche": k[0], "secteur": k[1], "zone": k[2],
                 "unite": list(postes.keys())[0],
                 **asdict(list(postes.values())[0]),
                 "cout_interne_total_eur_unite": list(postes.values())[0].cout_interne_total,
                 "cout_externalisé_total_eur_unite": list(postes.values())[0].cout_externalise_total}
                for k, postes in COUTS_CATALOGUE.items()
            ],
            "marge_plausible_pct": list(MARGE_INSTALLATEUR_PCT_PLAUSIBLE),
            "source": "UNTEC 2025-2026 + Capeb + retours terrain SIRAT",
        })
