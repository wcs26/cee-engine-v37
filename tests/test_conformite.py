"""
V37.1 P4 — Tests conformite.py : 46 contrôles P6 + horodatage.

Couvre :
- Structure des règles (toutes ont id/cat/sev/check/desc/reference)
- Sévérités valides (bloquant/avertissement/info)
- Exécution sur dossier minimal vs complet
- Quelques checks individuels critiques
- Horodatage HMAC roundtrip
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CEE_JWT_SECRET", "y" * 64)
os.environ.setdefault("CEE_CONFORMITE_SECRET", "z" * 64)
os.environ.setdefault("CEE_ENV", "dev")

import conformite  # noqa: E402


# ─────────────────────────────────────────────────────────────
# Structure des règles
# ─────────────────────────────────────────────────────────────

def test_regles_juridiques_count():
    """Les règles documentées comme '46 contrôles P6'. Tolère 40-60 pour évolutions."""
    assert 40 <= len(conformite.REGLES_JURIDIQUES) <= 60


def test_regles_juridiques_schema():
    """Chaque règle a les 5 champs obligatoires."""
    required = {"id", "cat", "sev", "check", "desc", "reference"}
    for r in conformite.REGLES_JURIDIQUES:
        missing = required - set(r.keys())
        assert not missing, f"règle {r.get('id', '?')} manque {missing}"


def test_regles_severites_valides():
    """Sévérités acceptables : bloquant, avertissement, info."""
    valid = {"bloquant", "avertissement", "info"}
    for r in conformite.REGLES_JURIDIQUES:
        assert r["sev"] in valid, f"règle {r['id']} a sev='{r['sev']}' invalide"


def test_regles_ids_uniques():
    ids = [r["id"] for r in conformite.REGLES_JURIDIQUES]
    assert len(ids) == len(set(ids)), "IDs de règles dupliqués"


# ─────────────────────────────────────────────────────────────
# Exécution checks
# ─────────────────────────────────────────────────────────────

def test_executer_controles_dossier_vide():
    """Dossier vide → NON_CONFORME, plusieurs bloquants. Score peut rester moyen
    si beaucoup de règles sont 'info' ou 'non_implemente'."""
    rapport = conformite.executer_controles({})
    assert rapport["verdict"] == "NON_CONFORME"
    assert rapport["nb_bloquants"] >= 3, f"un dossier vide doit déclencher >= 3 bloquants (got {rapport['nb_bloquants']})"


def test_executer_controles_dossier_minimal_valide():
    """Dossier minimal mais valide pour les checks d'identité."""
    dossier = {
        "siret": "12345678900012",
        "raison_sociale": "SARL Test Pro",
        "adresse": "12 rue de la Paix, 75002 Paris",
        "fiches": ["BAT-EN-103"],
        "surface": 250,
        "rge_installateur": True,
        "rge_qualifications": ["Qualibat RGE"],
        "rge_date_validite": "2027-12-31",
        "date_engagement": "2026-04-01",
    }
    rapport = conformite.executer_controles(dossier)
    assert rapport["nb_ok"] >= 5  # Au moins SIRET, raison, adresse, fiches, surface
    assert "verdict" in rapport
    assert rapport["score_conformite"] >= 0


def test_executer_controles_score_dans_borne():
    rapport = conformite.executer_controles({"siret": "12345678900012"})
    assert 0 <= rapport["score_conformite"] <= 100


def test_executer_controles_resultats_structure():
    rapport = conformite.executer_controles({"siret": "12345678900012"})
    for r in rapport["resultats"]:
        assert "id" in r
        assert "statut" in r
        assert r["statut"] in ("ok", "bloquant", "avertissement", "info", "non_implemente")


# ─────────────────────────────────────────────────────────────
# Checks individuels (échantillons critiques)
# ─────────────────────────────────────────────────────────────

def test_check_siret_valide_ok():
    ok, _ = conformite._check_siret_valide({"siret": "12345678900012"})
    assert ok is True


def test_check_siret_valide_ko():
    ok, _ = conformite._check_siret_valide({"siret": "abc"})
    assert ok is False
    ok, _ = conformite._check_siret_valide({"siret": "12345"})
    assert ok is False
    ok, _ = conformite._check_siret_valide({})
    assert ok is False


def test_check_raison_sociale():
    ok, _ = conformite._check_raison_sociale({"raison_sociale": "Ma Boîte"})
    assert ok is True
    ok, _ = conformite._check_raison_sociale({"raison_sociale": ""})
    assert ok is False
    ok, _ = conformite._check_raison_sociale({})
    assert ok is False


def test_check_fiches_non_vides():
    ok, _ = conformite._check_fiches_non_vides({"fiches": ["BAR-EN-101"]})
    assert ok is True
    ok, _ = conformite._check_fiches_non_vides({"fiches": []})
    assert ok is False
    ok, _ = conformite._check_fiches_non_vides({})
    assert ok is False


# ─────────────────────────────────────────────────────────────
# Horodatage HMAC
# ─────────────────────────────────────────────────────────────

def test_horodater_format():
    token = conformite.horodater({"dossier_id": "test123"})
    assert "content_sha256" in token
    assert "signature_hmac_sha256" in token
    assert "algorithm" in token
    assert token["algorithm"] == "HMAC-SHA256"
    assert len(token["content_sha256"]) == 64
    assert len(token["signature_hmac_sha256"]) == 64


def test_horodatage_roundtrip():
    """Vérifier qu'un horodatage validé est reconnu."""
    data = {"dossier_id": "test456", "fiches": ["BAR-EN-101"]}
    token = conformite.horodater(data)
    assert conformite.verifier_horodatage(data, token) is True


def test_horodatage_data_alteree_detectee():
    """Si on change la data après horodatage, la vérification doit échouer."""
    data = {"dossier_id": "test789", "fiches": ["BAR-EN-101"]}
    token = conformite.horodater(data)
    altered = {"dossier_id": "test789", "fiches": ["BAR-EN-102"]}  # fiche changée
    assert conformite.verifier_horodatage(altered, token) is False


def test_horodatage_token_altere_detecte():
    data = {"dossier_id": "test-alt", "fiches": ["BAR-EN-101"]}
    token = conformite.horodater(data)
    forged = {**token, "signature_hmac_sha256": "0" * 64}
    assert conformite.verifier_horodatage(data, forged) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
