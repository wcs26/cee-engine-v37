"""
V37.1 P4 — Tests pncee.py : scoring conformité dossiers.

Couvre les cas critiques :
- Dossier propre → GO
- Dossier vide → STOP
- Fiche inconnue / inactive → blocker
- Pas de RGE sur BAR/BAT → blocker
- Non-cumul détecté → blocker
- SIRET invalide → blocker
- DPE absent sur fiche rénovation globale → blocker
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CEE_JWT_SECRET", "x" * 64)
os.environ.setdefault("CEE_ENV", "dev")

from pncee import score_dossier  # noqa: E402


def _dossier_propre() -> dict:
    return {
        "siret": "12345678900012",
        "raison_sociale": "SARL Test Pro",
        "surface": 250,
        "departement": "75",
        "fiches": ["BAT-EN-103"],
        "rge_installateur": True,
        "date_engagement": "2026-04-01",
    }


def test_score_dossier_propre_go():
    r = score_dossier(_dossier_propre())
    assert r["verdict"] == "GO", f"dossier propre devrait passer : {r['blockers']}"
    assert r["score"] >= 85
    assert not r["blockers"]


def test_score_dossier_vide_stop():
    r = score_dossier({"fiches": [], "siret": "12345678900012"})
    assert r["verdict"] == "STOP"
    assert any("vide" in b.lower() for b in r["blockers"])


def test_score_fiche_inconnue_blocker():
    d = _dossier_propre()
    d["fiches"] = ["FAKE-XX-999"]
    r = score_dossier(d)
    assert r["verdict"] == "STOP"
    assert any("inconnue" in b.lower() for b in r["blockers"])


def test_score_pas_de_rge_bloque():
    d = _dossier_propre()
    d["rge_installateur"] = False
    r = score_dossier(d)
    assert r["verdict"] == "STOP"
    assert any("RGE" in b for b in r["blockers"])


def test_score_siret_invalide_blocker():
    d = _dossier_propre()
    d["siret"] = "abc"
    r = score_dossier(d)
    assert any("SIRET" in b for b in r["blockers"])
    assert r["checks"]["siret_valide"] is False


def test_score_non_cumul_bloque():
    d = _dossier_propre()
    d["fiches"] = ["BAR-TH-104", "BAR-TH-113"]  # non-cumul connu
    r = score_dossier(d)
    assert r["verdict"] == "STOP"
    assert any("non-cumul" in b.lower() or "Non-cumul" in b for b in r["blockers"])


def test_score_renovation_globale_sans_dpe_bloque():
    d = _dossier_propre()
    d["fiches"] = ["BAR-TH-164"]  # rénovation globale, exige DPE
    d["dpe_date"] = None
    r = score_dossier(d)
    assert any("DPE" in b for b in r["blockers"])


def test_score_renovation_globale_dpe_ancien_warn():
    d = _dossier_propre()
    d["fiches"] = ["BAR-TH-164"]
    d["dpe_date"] = "2018-06-01"  # avant 2021
    r = score_dossier(d)
    assert any("2021" in w for w in r["warnings"])


def test_score_meta_present():
    r = score_dossier(_dossier_propre())
    assert "meta" in r
    assert r["meta"]["fiches_count"] == 1
    assert r["meta"]["scoring_version"].startswith("V37")


def test_score_borne_0_100():
    """Pire dossier possible : score borné à 0, pas négatif."""
    d = {"fiches": ["FAKE-XX-1", "FAKE-XX-2", "FAKE-XX-3"], "siret": "abc", "rge_installateur": False, "surface": 0}
    r = score_dossier(d)
    assert 0 <= r["score"] <= 100


def test_score_aucun_blocker_dans_dossier_propre():
    """Tous les checks du dossier propre doivent être OK."""
    r = score_dossier(_dossier_propre())
    assert len(r["blockers"]) == 0
    assert r["checks"]["fiche_BAT-EN-103_existe"] is True
    assert r["checks"]["fiche_BAT-EN-103_active"] is True
    assert r["checks"]["siret_valide"] is True
    assert r["checks"]["rge_conforme"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
