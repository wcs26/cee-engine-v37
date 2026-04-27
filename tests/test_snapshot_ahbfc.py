"""
V37.1 P3 — Snapshot de non-régression sur le dossier AHBFC vivant.

Verrouille les valeurs critiques :
- Présence et structure du dossier ahbfc-magritte
- Fiche BAT-EN-103 active + cumac H1/H2/H3/DOM gelés
- Sect_factors (FOST) gelés
- Calcul prime pour surface témoin

Si un test échoue, le dossier ou la fiche a dérivé. NE PAS DÉPLOYER avant compréhension.

Cf. mémoire `project_dossier_ahbfc` : trio SIRAt+H2D+WCS, financeur Abokine 749843090,
2 devis 0€ (Magritte 79K€ + Renoir 95K€).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FICHES_PATH = ROOT / "fiches.json"
AHBFC_PATH = ROOT / "post_signature_data" / "ahbfc-magritte.json"

# Valeurs gelées (snapshot 2026-04-27) — toute modif intentionnelle = update + commit séparé.
EXPECTED_BAT_EN_103 = {
    "ref": "BAT-EN-103",
    "nom": "Isolation plancher tertiaire",
    "secteur": "BAT",
    "sous_secteur": "EN",
    "type": "surface",
    "actif": True,
    "cumac_unitaire": {"H1": 5200, "H2": 4200, "H3": 2800, "DOM": 1700},
    "unite": "kWhc par m²",
    "duree_vie": 15,
    "zero_euro": True,
    "cofrac": True,
    "sect_factors_partial": {
        "bureaux": 0.6,
        "sante": 1.2,
        "hotellerie_restauration": 0.7,
    },
}

EXPECTED_AHBFC_DOSSIER = {
    "dossier_id": "ahbfc-magritte",
    "installateur": "SIRAT",
    "delegataire": "Abokine",
    "fiches": ["BAT-EN-103"],
    "etapes_keys": [
        "mandat_signe", "travaux_planifies", "travaux_termines",
        "doe_recu", "cofrac_planifie", "cofrac_valide",
        "pncee_depose", "paiement_recu",
    ],
}


def _load_fiche(ref: str) -> dict:
    fiches = json.loads(FICHES_PATH.read_text())
    for f in fiches:
        if f.get("ref") == ref:
            return f
    raise AssertionError(f"Fiche {ref} introuvable dans fiches.json")


def test_ahbfc_dossier_existe():
    """Le dossier ahbfc-magritte doit exister et être lisible."""
    assert AHBFC_PATH.exists(), f"Fichier {AHBFC_PATH} manquant — dossier AHBFC perdu ?"
    data = json.loads(AHBFC_PATH.read_text())
    assert data["dossier_id"] == EXPECTED_AHBFC_DOSSIER["dossier_id"]
    assert data["installateur"] == EXPECTED_AHBFC_DOSSIER["installateur"]
    assert data["delegataire"] == EXPECTED_AHBFC_DOSSIER["delegataire"]
    assert data["fiches"] == EXPECTED_AHBFC_DOSSIER["fiches"]


def test_ahbfc_etapes_workflow_intact():
    """L'ordre et la liste des 8 étapes post-signature ne doit pas changer sans intention."""
    data = json.loads(AHBFC_PATH.read_text())
    assert list(data["etapes"].keys()) == EXPECTED_AHBFC_DOSSIER["etapes_keys"]


def test_bat_en_103_active():
    """BAT-EN-103 = fiche pivot du dossier AHBFC. Si abrogée, AHBFC est mort."""
    fiche = _load_fiche("BAT-EN-103")
    assert fiche["actif"] is True, "BAT-EN-103 marquée inactive — dossier AHBFC bloqué"


def test_bat_en_103_cumac_gele():
    """Cumac unitaire BAT-EN-103 verrouillé. Drift > 0 = arrêté ADEME modifié → review nécessaire."""
    fiche = _load_fiche("BAT-EN-103")
    for zone, expected in EXPECTED_BAT_EN_103["cumac_unitaire"].items():
        actual = fiche["cumac_unitaire"][zone]
        assert actual == expected, (
            f"BAT-EN-103 cumac {zone} dérivé : {actual} (attendu {expected}). "
            f"Vérifier arrêté ADEME + impact sur AHBFC Magritte/Renoir."
        )


def test_bat_en_103_sect_factors_geles():
    """Facteurs FOST sectoriels = leviers prime. Drift = recalc tous devis ouverts."""
    fiche = _load_fiche("BAT-EN-103")
    for sect, expected in EXPECTED_BAT_EN_103["sect_factors_partial"].items():
        actual = fiche["sect_factors"].get(sect)
        assert actual == expected, f"FOST {sect} dérivé : {actual} (attendu {expected})"


def test_bat_en_103_metadata_critique():
    """Champs critiques de la fiche : type, durée vie, zéro-euro, cofrac."""
    fiche = _load_fiche("BAT-EN-103")
    assert fiche["type"] == EXPECTED_BAT_EN_103["type"]
    assert fiche["duree_vie"] == EXPECTED_BAT_EN_103["duree_vie"]
    assert fiche["zero_euro"] == EXPECTED_BAT_EN_103["zero_euro"]
    assert fiche["cofrac"] == EXPECTED_BAT_EN_103["cofrac"]
    assert fiche["unite"] == EXPECTED_BAT_EN_103["unite"]


def test_calcul_prime_temoin_zone_h2():
    """Calcul prime sur cas témoin : 1000 m² zone H2, secteur hôtellerie-restauration.
    cumac = 1000 × 4200 × 0.7 = 2 940 000 kWhc.
    À 8.78 €/MWh cumac → 25 813,20 €.
    Tolérance : ±1 € pour arrondis."""
    fiche = _load_fiche("BAT-EN-103")
    surface = 1000
    cumac_h2 = fiche["cumac_unitaire"]["H2"]
    fost_hotel = fiche["sect_factors"]["hotellerie_restauration"]
    cumac_total = surface * cumac_h2 * fost_hotel
    prix_mwhc = 8.78
    prime_eur = cumac_total / 1000 * prix_mwhc
    expected = 25813.20
    assert abs(prime_eur - expected) < 1.0, (
        f"Prime témoin dérivée : {prime_eur:.2f} € (attendu {expected} €). "
        f"Possible drift cumac ou facteur FOST."
    )


def test_fiches_json_count_stable():
    """Volume catalogue fiches stable (drift > 5 = scrape ADEME a buggé OU vraie évolution)."""
    fiches = json.loads(FICHES_PATH.read_text())
    count = len(fiches)
    # Snapshot 2026-04-27 : 234 fiches. Tolérance large pour absorber ajouts/retraits ADEME.
    assert 220 <= count <= 260, (
        f"Catalogue fiches.json a {count} entrées (attendu 220-260). "
        f"Lancer `validate_fiches.py` + revue ADEME."
    )


def test_ahbfc_pas_de_siret_vide():
    """Anomalie historique connue (mémoire `project_dossier_ahbfc`) : SIRET vides parfois.
    Si présent, doit déclencher review."""
    data = json.loads(AHBFC_PATH.read_text())
    # Le JSON de tracking n'a pas de champ siret direct, mais on vérifie qu'aucun
    # champ identifiant critique n'est vide.
    assert data["installateur"], "installateur AHBFC vide"
    assert data["delegataire"], "delegataire AHBFC vide"
    assert data["fiches"] and all(data["fiches"]), "fiches AHBFC vides"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
