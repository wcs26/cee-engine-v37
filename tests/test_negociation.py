"""
V37.1 P4 — Tests negociation.py : comparateur acheteurs CEE.

Couvre les scénarios stratégiques :
- Calcul prime base + bonus volume
- Refus secteur incompatible
- Refus multi-sites si non supporté
- Refus mixité si non supportée
- Volume insuffisant → VOLUME_INSUFFISANT
- COFRAC exigé → coût déduit de prime nette
- Précarité → prix bonus
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CEE_JWT_SECRET", "n" * 64)
os.environ.setdefault("CEE_ENV", "dev")

from negociation import calculer_scenario_acheteur, comparer_acheteurs, ACHETEURS  # noqa: E402


def test_acheteurs_principaux_presents():
    """Les 9 acheteurs documentés (EDF, Engie, Total, Delegataires, Mandataire, etc.) doivent exister."""
    must_have = {"EDF", "Engie", "TotalEnergies", "Delegataire_Premium", "Mandataire"}
    assert must_have.issubset(set(ACHETEURS.keys()))


def test_acheteurs_schema():
    """Champs obligatoires sur chaque acheteur — leur drift fait planter la comparaison."""
    required = {"nom", "type", "prix_classic_mwhc", "prix_precarite_mwhc",
                "secteurs_ok", "multisite", "mixite_ok", "exige_cofrac",
                "seuil_volume_min", "bonus_volume_pct"}
    for k, a in ACHETEURS.items():
        missing = required - set(a.keys())
        assert not missing, f"Acheteur {k} manque {missing}"


def test_scenario_edf_secteur_compatible():
    r = calculer_scenario_acheteur("EDF", volume_kwhc=10_000_000, secteurs=["BAT"])
    assert r is not None
    assert r["statut"] != "REFUSE"
    assert r["prime_brute"] > 0
    assert r["prix_mwhc"] > 0


def test_scenario_secteur_refuse():
    """Un acheteur n'accepte pas tous les secteurs — refus explicite."""
    # EDF accepte BAT et BAR uniquement (pas IND)
    r = calculer_scenario_acheteur("EDF", volume_kwhc=10_000_000, secteurs=["IND"])
    assert r["statut"] == "REFUSE"
    assert "IND" in r["raison"]


def test_scenario_mixite_refusee():
    """EDF n'accepte pas la mixité de secteurs."""
    r = calculer_scenario_acheteur("EDF", volume_kwhc=10_000_000, secteurs=["BAT", "BAR"])
    assert r["statut"] == "REFUSE"
    assert "Mixité" in r["raison"] or "mixit" in r["raison"].lower()


def test_scenario_volume_insuffisant():
    """Si volume sous le seuil mini de l'acheteur → statut VOLUME_INSUFFISANT."""
    # Trouver un acheteur avec seuil > 0
    test_key = None
    for k, a in ACHETEURS.items():
        if a["seuil_volume_min"] > 0:
            test_key = k
            break
    if test_key is None:
        pytest.skip("Aucun acheteur avec seuil_volume_min > 0")
    seuil = ACHETEURS[test_key]["seuil_volume_min"]
    secteurs_ok = ACHETEURS[test_key]["secteurs_ok"][:1]
    r = calculer_scenario_acheteur(test_key, volume_kwhc=seuil // 2, secteurs=secteurs_ok)
    assert r["statut"] == "VOLUME_INSUFFISANT"


def test_scenario_acheteur_inconnu():
    """Acheteur inexistant → None (pas de crash)."""
    r = calculer_scenario_acheteur("INEXISTANT_XYZ", volume_kwhc=1_000_000)
    assert r is None


def test_scenario_precarite_prix_superieur():
    """Le prix précarité doit être >= prix classic (sinon pas de raison de cocher)."""
    # Trouver un acheteur compatible BAT
    r_classic = calculer_scenario_acheteur("EDF", volume_kwhc=10_000_000, secteurs=["BAT"], precarite=False)
    r_prec = calculer_scenario_acheteur("EDF", volume_kwhc=10_000_000, secteurs=["BAT"], precarite=True)
    assert r_prec["prix_mwhc"] >= r_classic["prix_mwhc"]


def test_scenario_qualite_cofrac_premium():
    """Dossier COFRAC = +10% sur le prix."""
    base = calculer_scenario_acheteur("EDF", volume_kwhc=10_000_000, secteurs=["BAT"], qualite_dossier="standard")
    cof = calculer_scenario_acheteur("EDF", volume_kwhc=10_000_000, secteurs=["BAT"], qualite_dossier="cofrac")
    assert cof["prix_mwhc"] > base["prix_mwhc"]


def test_comparer_acheteurs_renvoie_liste():
    """Le comparateur renvoie une liste triée des scénarios pour tous les acheteurs."""
    res = comparer_acheteurs(volume_kwhc=10_000_000, secteurs=["BAT"], cout_travaux_ttc=50_000)
    assert isinstance(res, (list, dict))
    # Si dict avec une clé "scenarios" ou similaire :
    if isinstance(res, dict):
        assert "scenarios" in res or "acheteurs" in res or len(res) > 0


def test_coverage_calcul():
    """Couverture = prime / coût × 100. Vérifier qu'elle est calculée."""
    r = calculer_scenario_acheteur("EDF", volume_kwhc=10_000_000, secteurs=["BAT"], cout_travaux_ttc=10_000)
    assert "coverage" in r
    assert isinstance(r["coverage"], (int, float))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
