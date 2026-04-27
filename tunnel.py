"""
V37.1 — Tunnel commercial unifié CEE Engine.

Orchestrateur du parcours unique du lead au paiement, mesurable bout-à-bout.

6 macro-stages alignés sur la méthodo Jimmy (R0→R4 + Maestro 10 commandements) :
    1. lead          — SIRET capturé, pas encore qualifié
    2. audit         — cumac estimé, fiches éligibles, prime calculée
    3. r1            — 1er rendez-vous (qualification + cadrage SPIN)
    4. r2            — 2e rendez-vous (closing Maestro)
    5. signature     — mandat signé (= mandat_signe de post_signature)
    6. post_signature — délègue au module post_signature (8 sous-étapes : travaux, COFRAC, PNCEE, paiement)

Persistance : tunnel_data/<tunnel_id>.json
Index : tunnel_data/_index.json (pour /tunnel GET liste)

Endpoints exposés par register_tunnel_routes(app) :
    POST   /tunnel                   — crée un tunnel (siret, vendor, source)
    GET    /tunnel/<id>              — état complet
    POST   /tunnel/<id>/advance      — avance au stage suivant (ou spécifié) avec data
    GET    /tunnel                   — liste tous (filtres : stage, vendor)
    GET    /analytics/sales-velocity — KPI dashboard (signatures/mois/vendor + objectif V38 +2)
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import jsonify, request


TUNNEL_STAGES = ["lead", "audit", "r1", "r2", "signature", "post_signature"]


# V37.1 P2 — Persistance Fly volume (même mécanique que dossiers/conformite/post_signature).
def _resolve_data_dir(subdir: str) -> Path:
    base = os.environ.get("CEE_DATA_DIR")
    target = Path(base) / subdir if base else Path(__file__).parent / subdir
    target.mkdir(parents=True, exist_ok=True)
    return target


TUNNEL_DIR = _resolve_data_dir("tunnel_data")
INDEX_FILE = TUNNEL_DIR / "_index.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _new_id() -> str:
    return "T-" + uuid.uuid4().hex[:12]


def _path(tunnel_id: str) -> Path:
    return TUNNEL_DIR / f"{tunnel_id}.json"


def _load(tunnel_id: str) -> dict | None:
    p = _path(tunnel_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _save(t: dict) -> None:
    _path(t["tunnel_id"]).write_text(json.dumps(t, ensure_ascii=False, indent=2))
    _refresh_index()


def _refresh_index() -> None:
    """Index léger pour la liste — pas de re-load de chaque tunnel à chaque /tunnel GET."""
    idx = []
    for f in TUNNEL_DIR.glob("T-*.json"):
        try:
            t = json.loads(f.read_text())
            idx.append({
                "tunnel_id": t["tunnel_id"],
                "siret": t.get("siret"),
                "current_stage": t.get("current_stage"),
                "vendor": t.get("vendor"),
                "created_at": t.get("created_at"),
                "updated_at": t.get("updated_at"),
            })
        except Exception:
            continue
    INDEX_FILE.write_text(json.dumps(idx, ensure_ascii=False, indent=2))


def create_tunnel(siret: str, vendor: str = "", source: str = "manual",
                  raison_sociale: str = "") -> dict:
    """Crée un tunnel à l'étape 'lead'."""
    if not siret or len(siret) < 9:
        raise ValueError("SIRET requis (>= 9 chars)")
    tunnel_id = _new_id()
    now = _now()
    t = {
        "tunnel_id": tunnel_id,
        "siret": siret.replace(" ", "").strip(),
        "raison_sociale": raison_sociale,
        "vendor": vendor,
        "source": source,
        "current_stage": "lead",
        "created_at": now,
        "updated_at": now,
        "history": [{"stage": "lead", "ts": now, "data": {}}],
        "kpi": {},  # rempli au fur et à mesure des advance
    }
    _save(t)
    return t


def advance_tunnel(tunnel_id: str, target_stage: str | None = None,
                   data: dict | None = None) -> dict | None:
    """Avance le tunnel au stage suivant (ou spécifié) avec data attachée.

    target_stage = None → stage suivant dans TUNNEL_STAGES
    target_stage = "r2" → saute directement (cas où R1 sauté, etc.)
    """
    t = _load(tunnel_id)
    if not t:
        return None
    current_idx = TUNNEL_STAGES.index(t["current_stage"])
    if target_stage:
        if target_stage not in TUNNEL_STAGES:
            raise ValueError(f"stage inconnu : {target_stage}")
        new_stage = target_stage
    else:
        if current_idx == len(TUNNEL_STAGES) - 1:
            return t  # déjà au bout
        new_stage = TUNNEL_STAGES[current_idx + 1]

    now = _now()
    t["current_stage"] = new_stage
    t["updated_at"] = now
    t["history"].append({"stage": new_stage, "ts": now, "data": data or {}})

    # KPI : durée entre stages successifs (en heures)
    if len(t["history"]) >= 2:
        prev = t["history"][-2]
        try:
            d_prev = datetime.fromisoformat(prev["ts"].replace("Z", "")).timestamp()
            d_now = datetime.fromisoformat(now.replace("Z", "")).timestamp()
            t["kpi"][f"duree_{prev['stage']}_to_{new_stage}_h"] = round((d_now - d_prev) / 3600, 2)
        except Exception:
            pass

    _save(t)
    return t


def list_tunnels(stage: str | None = None, vendor: str | None = None) -> list:
    """Liste les tunnels avec filtres optionnels."""
    if not INDEX_FILE.exists():
        _refresh_index()
    try:
        idx = json.loads(INDEX_FILE.read_text())
    except Exception:
        idx = []
    if stage:
        idx = [t for t in idx if t.get("current_stage") == stage]
    if vendor:
        idx = [t for t in idx if t.get("vendor") == vendor]
    return idx


def sales_velocity(month: str | None = None, objectif_par_personne: int = 2) -> dict:
    """KPI dashboard pour objectif V38 +2 signatures/mois/personne.

    month = "YYYY-MM" (défaut : mois courant)
    """
    if not month:
        month = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m")
    tunnels = list_tunnels()
    # Compter signatures = tunnels qui ont atteint stage 'signature' OU 'post_signature' dans le mois
    by_vendor: dict[str, dict] = {}
    for entry in tunnels:
        # Charger le tunnel complet pour parcourir l'historique (signature timestamp)
        t = _load(entry["tunnel_id"])
        if not t:
            continue
        vendor = t.get("vendor") or "non_assigné"
        v = by_vendor.setdefault(vendor, {
            "name": vendor, "leads": 0, "audits": 0, "r1": 0, "r2": 0, "signatures": 0,
        })
        # Compter chaque stage atteint dans le mois
        seen = set()
        for h in t.get("history", []):
            if h.get("ts", "")[:7] != month:
                continue
            s = h.get("stage")
            if s in seen:
                continue
            seen.add(s)
            if s == "lead":
                v["leads"] += 1
            elif s == "audit":
                v["audits"] += 1
            elif s == "r1":
                v["r1"] += 1
            elif s == "r2":
                v["r2"] += 1
            elif s in ("signature", "post_signature"):
                v["signatures"] += 1

    vendors = list(by_vendor.values())
    for v in vendors:
        v["conversion_lead_to_signature"] = round(v["signatures"] / v["leads"], 3) if v["leads"] else 0
        v["conversion_r2_to_signature"] = round(v["signatures"] / v["r2"], 3) if v["r2"] else 0
        v["objectif_atteint"] = v["signatures"] >= objectif_par_personne
    total_sig = sum(v["signatures"] for v in vendors)
    return {
        "période": month,
        "objectif_par_personne": objectif_par_personne,
        "objectif_global_calcule": objectif_par_personne * len(vendors),
        "total_signatures": total_sig,
        "vendors": sorted(vendors, key=lambda v: -v["signatures"]),
    }


def register_tunnel_routes(app) -> None:
    """Enregistre les routes /tunnel/* + /analytics/sales-velocity."""

    @app.route("/tunnel", methods=["POST"])
    def _tunnel_create():
        d = request.json or {}
        siret = d.get("siret", "")
        try:
            t = create_tunnel(
                siret=siret,
                vendor=d.get("vendor", ""),
                source=d.get("source", "manual"),
                raison_sociale=d.get("raison_sociale", ""),
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify(t), 201

    @app.route("/tunnel/<tunnel_id>", methods=["GET"])
    def _tunnel_get(tunnel_id):
        t = _load(tunnel_id)
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        return jsonify(t)

    @app.route("/tunnel/<tunnel_id>/advance", methods=["POST"])
    def _tunnel_advance(tunnel_id):
        d = request.json or {}
        try:
            t = advance_tunnel(tunnel_id, target_stage=d.get("target_stage"), data=d.get("data"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        if not t:
            return jsonify({"error": "tunnel inconnu"}), 404
        return jsonify(t)

    @app.route("/tunnel", methods=["GET"])
    def _tunnel_list():
        return jsonify({
            "stages": TUNNEL_STAGES,
            "tunnels": list_tunnels(
                stage=request.args.get("stage"),
                vendor=request.args.get("vendor"),
            ),
        })

    @app.route("/analytics/sales-velocity", methods=["GET"])
    def _tunnel_velocity():
        try:
            obj = int(request.args.get("objectif", 2))
        except Exception:
            obj = 2
        return jsonify(sales_velocity(
            month=request.args.get("month"),
            objectif_par_personne=obj,
        ))
