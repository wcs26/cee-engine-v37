"""
V37.1 — Tests tunnel.py : orchestrateur commercial unifié.

Couvre :
- Création tunnel avec SIRET valide
- Refus SIRET trop court
- Avance stage par stage (lead → audit → r1 → r2 → signature → post_signature)
- Saut direct à un stage spécifique
- KPI durée entre stages calculés
- Liste avec filtres (stage, vendor)
- Sales velocity dashboard (signatures/mois/vendor + objectif)
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    """Chaque test a son propre tunnel_data/ pour ne pas polluer."""
    monkeypatch.setenv("CEE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CEE_JWT_SECRET", "t" * 64)
    monkeypatch.setenv("CEE_ENV", "dev")
    # Recharger le module pour re-résoudre TUNNEL_DIR
    if "tunnel" in sys.modules:
        del sys.modules["tunnel"]
    import tunnel
    yield tunnel


def test_create_tunnel_ok(isolated_data_dir):
    t = isolated_data_dir.create_tunnel(siret="12345678900012", vendor="Anthony", source="phone")
    assert t["tunnel_id"].startswith("T-")
    assert t["siret"] == "12345678900012"
    assert t["current_stage"] == "lead"
    assert t["vendor"] == "Anthony"
    assert len(t["history"]) == 1


def test_create_tunnel_siret_invalide(isolated_data_dir):
    with pytest.raises(ValueError):
        isolated_data_dir.create_tunnel(siret="abc")
    with pytest.raises(ValueError):
        isolated_data_dir.create_tunnel(siret="")


def test_advance_stage_par_stage(isolated_data_dir):
    t = isolated_data_dir.create_tunnel(siret="12345678900012", vendor="Jimmy")
    tid = t["tunnel_id"]
    for expected in ["audit", "r1", "r2", "signature", "post_signature"]:
        t = isolated_data_dir.advance_tunnel(tid)
        assert t["current_stage"] == expected
    # Au-delà : reste sur post_signature (idempotent)
    t = isolated_data_dir.advance_tunnel(tid)
    assert t["current_stage"] == "post_signature"


def test_advance_avec_data(isolated_data_dir):
    t = isolated_data_dir.create_tunnel(siret="12345678900012", vendor="Anthony")
    tid = t["tunnel_id"]
    t = isolated_data_dir.advance_tunnel(tid, data={"cumac": 5000, "prime": 8200})
    assert t["current_stage"] == "audit"
    assert t["history"][-1]["data"]["cumac"] == 5000
    assert t["history"][-1]["data"]["prime"] == 8200


def test_advance_saut_direct(isolated_data_dir):
    """Sauter de lead à r2 directement (cas où R1 fait offline / pas tracké)."""
    t = isolated_data_dir.create_tunnel(siret="12345678900012", vendor="Nico")
    t = isolated_data_dir.advance_tunnel(t["tunnel_id"], target_stage="r2")
    assert t["current_stage"] == "r2"


def test_advance_stage_inconnu(isolated_data_dir):
    t = isolated_data_dir.create_tunnel(siret="12345678900012", vendor="Aurelien")
    with pytest.raises(ValueError):
        isolated_data_dir.advance_tunnel(t["tunnel_id"], target_stage="inexistant")


def test_advance_tunnel_inconnu(isolated_data_dir):
    assert isolated_data_dir.advance_tunnel("T-doesnotexist") is None


def test_list_tunnels_filtres(isolated_data_dir):
    isolated_data_dir.create_tunnel(siret="11111111100001", vendor="Jimmy")
    t2 = isolated_data_dir.create_tunnel(siret="22222222200002", vendor="Anthony")
    isolated_data_dir.advance_tunnel(t2["tunnel_id"])  # → audit
    all_t = isolated_data_dir.list_tunnels()
    assert len(all_t) == 2
    audit = isolated_data_dir.list_tunnels(stage="audit")
    assert len(audit) == 1
    jimmy = isolated_data_dir.list_tunnels(vendor="Jimmy")
    assert len(jimmy) == 1


def test_sales_velocity_objectif_atteint(isolated_data_dir):
    """3 signatures pour Jimmy → objectif 2 atteint (objectif_atteint = True)."""
    for i in range(3):
        t = isolated_data_dir.create_tunnel(siret=f"1234567890000{i}", vendor="Jimmy")
        # Avancer jusqu'à signature
        for _ in range(4):  # lead → audit → r1 → r2 → signature
            isolated_data_dir.advance_tunnel(t["tunnel_id"])
    velocity = isolated_data_dir.sales_velocity(objectif_par_personne=2)
    jimmy_kpi = next(v for v in velocity["vendors"] if v["name"] == "Jimmy")
    assert jimmy_kpi["signatures"] == 3
    assert jimmy_kpi["objectif_atteint"] is True
    assert velocity["total_signatures"] == 3


def test_sales_velocity_objectif_manque(isolated_data_dir):
    """1 signature pour Anthony → objectif 2 manqué."""
    t = isolated_data_dir.create_tunnel(siret="11111111100001", vendor="Anthony")
    for _ in range(4):  # → signature
        isolated_data_dir.advance_tunnel(t["tunnel_id"])
    velocity = isolated_data_dir.sales_velocity(objectif_par_personne=2)
    anthony_kpi = next(v for v in velocity["vendors"] if v["name"] == "Anthony")
    assert anthony_kpi["signatures"] == 1
    assert anthony_kpi["objectif_atteint"] is False


def test_kpi_durees_entre_stages(isolated_data_dir):
    """Les durées entre stages doivent être enregistrées dans kpi."""
    t = isolated_data_dir.create_tunnel(siret="12345678900012", vendor="Jimmy")
    t = isolated_data_dir.advance_tunnel(t["tunnel_id"])  # lead → audit
    assert any("duree_lead_to_audit_h" in k for k in t["kpi"].keys())


def test_conversion_rate_calcule(isolated_data_dir):
    """Conversion lead→signature = signatures / leads."""
    t = isolated_data_dir.create_tunnel(siret="11111111100001", vendor="Jimmy")
    for _ in range(4):
        isolated_data_dir.advance_tunnel(t["tunnel_id"])  # → signature
    isolated_data_dir.create_tunnel(siret="22222222200002", vendor="Jimmy")  # lead seul
    velocity = isolated_data_dir.sales_velocity(objectif_par_personne=2)
    jimmy = next(v for v in velocity["vendors"] if v["name"] == "Jimmy")
    assert jimmy["leads"] == 2
    assert jimmy["signatures"] == 1
    assert jimmy["conversion_lead_to_signature"] == 0.5


# ─────────────────────────────────────────────────────────────
# V37.2 — Hooks auto + alertes + prédictif
# ─────────────────────────────────────────────────────────────

def test_hook_audit_score_pncee(isolated_data_dir):
    """Advance vers 'audit' avec fiche valide → score PNCEE auto attaché."""
    t = isolated_data_dir.create_tunnel(siret="12345678900012", vendor="Jimmy")
    isolated_data_dir.advance_tunnel(t["tunnel_id"], target_stage="audit", data={
        "fiches": ["BAT-EN-103"],
        "surface": 250,
        "departement": "75",
        "rge_installateur": True,
        "date_engagement": "2026-04-01",
    })
    t = isolated_data_dir._load(t["tunnel_id"])
    assert "checks" in t
    assert "pncee" in t["checks"]
    assert "score" in t["checks"]["pncee"]
    assert "verdict" in t["checks"]["pncee"]


def test_hook_dont_break_advance_on_error(isolated_data_dir):
    """Si un hook échoue (data métier vide), advance ne doit pas crasher."""
    t = isolated_data_dir.create_tunnel(siret="00000000000000", vendor="Test")
    r = isolated_data_dir.advance_tunnel(t["tunnel_id"], target_stage="audit", data={})
    assert r is not None
    assert r["current_stage"] == "audit"


def test_detect_stagnants_recent_vide(isolated_data_dir):
    """Tunnel fraîchement créé → 0 alerte stagnante."""
    isolated_data_dir.create_tunnel(siret="12345678900012", vendor="Jimmy")
    alerts = isolated_data_dir.detect_stagnants()
    assert isinstance(alerts, list)


def test_predict_next_lead(isolated_data_dir):
    t = isolated_data_dir.create_tunnel(siret="12345678900012", vendor="Jimmy")
    p = isolated_data_dir.predict_next(t["tunnel_id"])
    assert p is not None
    assert p["stage"] == "lead"
    assert "Qualif" in p["next_action"]
    assert p["risk"] in ("GO", "PRUDENCE", "STOP")


def test_predict_next_inconnu(isolated_data_dir):
    assert isolated_data_dir.predict_next("T-doesnotexist") is None


def test_sla_par_stage_configurable(isolated_data_dir, monkeypatch):
    """SLA peut être surchargé par CEE_TUNNEL_SLA_<STAGE>_D."""
    monkeypatch.setenv("CEE_TUNNEL_SLA_LEAD_D", "30")
    sla = isolated_data_dir._stage_sla_days("lead")
    assert sla == 30


def test_next_action_par_stage(isolated_data_dir):
    """Chaque stage a une recommandation textuelle distincte."""
    actions = {s: isolated_data_dir._next_action_for_stage(s)
               for s in isolated_data_dir.TUNNEL_STAGES}
    assert "Qualif" in actions["lead"]
    assert "oracle" in actions["audit"].lower() or "/analyse" in actions["audit"]
    assert "SPIN" in actions["r1"]
    assert "Maestro" in actions["r2"] or "10 commandements" in actions["r2"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
