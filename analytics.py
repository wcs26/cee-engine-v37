"""
Analytics & Reporting — CEE Engine V37
=======================================
Dashboards décisionnels pour Jimmy : pipeline, forecast, performance, ROI fiches, activité.

Endpoints :
  GET /analytics/pipeline      — pipeline commercial par étape
  GET /analytics/forecast      — forecast commission J+30/60/90
  GET /analytics/performance   — KPIs globaux
  GET /analytics/roi-fiches    — ROI par fiche CEE
  GET /analytics/activite      — activité récente (série temporelle)
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flask import jsonify, request

# ═══════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).resolve().parent
DOSSIERS_DIR = BASE_DIR / "dossiers_data"
POST_SIG_DIR = BASE_DIR / "post_signature_data"
AUDIT_LOG = BASE_DIR / "conformite_data" / "audit_log.jsonl"

# ═══════════════════════════════════════════════════════════════════════════
# CACHE (5 min TTL)
# ═══════════════════════════════════════════════════════════════════════════

_cache: dict[str, Any] = {}
_cache_ts: dict[str, float] = {}
CACHE_TTL = 300  # 5 minutes


def _cached(key: str):
    """Retourne la valeur cachée si < 5 min, sinon None."""
    if key in _cache and (time.time() - _cache_ts.get(key, 0)) < CACHE_TTL:
        return _cache[key]
    return None


def _set_cache(key: str, value: Any):
    _cache[key] = value
    _cache_ts[key] = time.time()


# ═══════════════════════════════════════════════════════════════════════════
# DATA LOADERS
# ═══════════════════════════════════════════════════════════════════════════

def _load_all_dossiers() -> list[dict]:
    """Charge tous les JSON de dossiers_data/."""
    dossiers = []
    if not DOSSIERS_DIR.exists():
        return dossiers
    for f in DOSSIERS_DIR.glob("*.json"):
        try:
            dossiers.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return dossiers


def _load_all_post_signature() -> list[dict]:
    """Charge tous les JSON de post_signature_data/."""
    items = []
    if not POST_SIG_DIR.exists():
        return items
    for f in POST_SIG_DIR.glob("*.json"):
        try:
            items.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return items


def _load_audit_log() -> list[dict]:
    """Parse audit_log.jsonl ligne par ligne."""
    entries = []
    if not AUDIT_LOG.exists():
        return entries
    try:
        for line in AUDIT_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return entries


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

# Étapes du pipeline commercial CEE (ordre logique)
PIPELINE_ETAPES = [
    "brouillon", "qualification", "devis_envoye", "signature",
    "travaux_planifies", "travaux_termines", "doe_recu",
    "cofrac_planifie", "cofrac_valide", "pncee_depose",
    "paiement_recu", "commission"
]


def _get_statut(d: dict) -> str:
    """Détermine le statut effectif d'un dossier."""
    return d.get("statut", "brouillon")


def _get_prime(d: dict) -> float:
    calc = d.get("calcul", {})
    if isinstance(calc, dict):
        return float(calc.get("prime_eur", 0) or calc.get("prime_totale_eur", 0) or 0)
    return 0.0


def _get_commission(d: dict) -> float:
    calc = d.get("calcul", {})
    if isinstance(calc, dict):
        return float(calc.get("commission_eur", 0) or calc.get("commission_totale_eur", 0) or 0)
    return 0.0


def _get_fiche(d: dict) -> str:
    return d.get("operation", {}).get("fiche", "inconnue")


# ═══════════════════════════════════════════════════════════════════════════
# 1. PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

def _build_pipeline() -> dict:
    cached = _cached("pipeline")
    if cached:
        return cached

    dossiers = _load_all_dossiers()
    etape_data: dict[str, dict] = {e: {"nb": 0, "prime": 0.0, "commission": 0.0} for e in PIPELINE_ETAPES}

    for d in dossiers:
        statut = _get_statut(d)
        if statut not in etape_data:
            etape_data[statut] = {"nb": 0, "prime": 0.0, "commission": 0.0}
        etape_data[statut]["nb"] += 1
        etape_data[statut]["prime"] += _get_prime(d)
        etape_data[statut]["commission"] += _get_commission(d)

    etapes_list = []
    for nom in PIPELINE_ETAPES:
        info = etape_data.get(nom, {"nb": 0, "prime": 0.0, "commission": 0.0})
        etapes_list.append({
            "nom": nom,
            "nb_dossiers": info["nb"],
            "montant_prime": round(info["prime"], 2),
            "montant_commission": round(info["commission"], 2),
        })
    # Ajouter les étapes hors nomenclature standard
    for nom, info in etape_data.items():
        if nom not in PIPELINE_ETAPES and info["nb"] > 0:
            etapes_list.append({
                "nom": nom,
                "nb_dossiers": info["nb"],
                "montant_prime": round(info["prime"], 2),
                "montant_commission": round(info["commission"], 2),
            })

    total = sum(e["montant_prime"] + e["montant_commission"] for e in etapes_list)
    nb_total = sum(e["nb_dossiers"] for e in etapes_list)
    nb_signe = sum(
        e["nb_dossiers"] for e in etapes_list
        if e["nom"] not in ("brouillon", "qualification")
    )

    result = {
        "etapes": etapes_list,
        "total_pipeline_eur": round(total, 2),
        "nb_dossiers": nb_total,
        "conversion_rates": {
            "qualification_to_signature": round(nb_signe / nb_total * 100, 1) if nb_total else 0,
        }
    }
    _set_cache("pipeline", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 2. FORECAST
# ═══════════════════════════════════════════════════════════════════════════

def _build_forecast() -> dict:
    cached = _cached("forecast")
    if cached:
        return cached

    post_sigs = _load_all_post_signature()
    dossiers_by_id = {d.get("id"): d for d in _load_all_dossiers()}
    now = datetime.utcnow()
    j30 = now + timedelta(days=30)
    j60 = now + timedelta(days=60)
    j90 = now + timedelta(days=90)

    buckets = {
        "j30": {"nb": 0, "montant": 0.0},
        "j60": {"nb": 0, "montant": 0.0},
        "j90": {"nb": 0, "montant": 0.0},
    }

    for ps in post_sigs:
        dates_cibles = ps.get("dates_cibles", {})
        date_paiement_str = dates_cibles.get("paiement_recu", "")
        if not date_paiement_str:
            continue

        try:
            date_paiement = datetime.fromisoformat(date_paiement_str)
        except (ValueError, TypeError):
            continue

        # Déjà payé ? On skip
        etapes = ps.get("etapes", {})
        if etapes.get("paiement_recu", {}).get("date_reelle"):
            continue

        # Chercher la commission dans le dossier lié
        did = ps.get("dossier_id", "")
        dossier = dossiers_by_id.get(did, {})
        commission = _get_commission(dossier)
        prime = _get_prime(dossier)
        montant = commission if commission > 0 else prime

        if date_paiement <= j30:
            buckets["j30"]["nb"] += 1
            buckets["j30"]["montant"] += montant
        elif date_paiement <= j60:
            buckets["j60"]["nb"] += 1
            buckets["j60"]["montant"] += montant
        elif date_paiement <= j90:
            buckets["j90"]["nb"] += 1
            buckets["j90"]["montant"] += montant

    for k in buckets:
        buckets[k]["montant"] = round(buckets[k]["montant"], 2)

    total = sum(b["montant"] for b in buckets.values())
    result = {
        "j30": buckets["j30"],
        "j60": buckets["j60"],
        "j90": buckets["j90"],
        "total_prevu": round(total, 2),
    }
    _set_cache("forecast", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 3. PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════

def _build_performance() -> dict:
    cached = _cached("performance")
    if cached:
        return cached

    dossiers = _load_all_dossiers()
    audit_entries = _load_audit_log()

    nb_dossiers = len(dossiers)
    nb_audits = len(audit_entries)

    # Taux de conversion
    nb_signes = sum(
        1 for d in dossiers
        if _get_statut(d) not in ("brouillon", "qualification")
    )
    taux_conversion = round(nb_signes / nb_dossiers * 100, 1) if nb_dossiers else 0

    # Prime moyenne
    primes = [_get_prime(d) for d in dossiers if _get_prime(d) > 0]
    prime_moyenne = round(sum(primes) / len(primes), 2) if primes else 0

    # Top 5 fiches
    fiche_counter: Counter = Counter()
    for d in dossiers:
        fiche = _get_fiche(d)
        if fiche and fiche != "inconnue":
            fiche_counter[fiche] += 1
    top_fiches = [{"fiche": f, "nb_dossiers": n} for f, n in fiche_counter.most_common(5)]

    # Temps moyen par étape (post_signature)
    post_sigs = _load_all_post_signature()
    etape_durees: dict[str, list[float]] = defaultdict(list)
    for ps in post_sigs:
        dates_cibles = ps.get("dates_cibles", {})
        etapes_ordered = list(dates_cibles.keys())
        for i in range(1, len(etapes_ordered)):
            prev_key = etapes_ordered[i - 1]
            curr_key = etapes_ordered[i]
            try:
                d1 = datetime.fromisoformat(dates_cibles[prev_key])
                d2 = datetime.fromisoformat(dates_cibles[curr_key])
                delta = (d2 - d1).days
                if delta > 0:
                    etape_durees[curr_key].append(delta)
            except (ValueError, TypeError, KeyError):
                continue

    temps_moyen_etapes = {
        k: round(sum(v) / len(v), 1) for k, v in etape_durees.items() if v
    }

    result = {
        "nb_audits": nb_audits,
        "nb_dossiers": nb_dossiers,
        "taux_conversion_pct": taux_conversion,
        "prime_moyenne_eur": prime_moyenne,
        "top_5_fiches": top_fiches,
        "temps_moyen_etapes_jours": temps_moyen_etapes,
    }
    _set_cache("performance", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 4. ROI FICHES
# ═══════════════════════════════════════════════════════════════════════════

def _build_roi_fiches() -> dict:
    cached = _cached("roi_fiches")
    if cached:
        return cached

    dossiers = _load_all_dossiers()
    fiches: dict[str, dict] = defaultdict(lambda: {"nb": 0, "prime": 0.0, "commission": 0.0})

    for d in dossiers:
        fiche = _get_fiche(d)
        if not fiche or fiche == "inconnue":
            continue
        fiches[fiche]["nb"] += 1
        fiches[fiche]["prime"] += _get_prime(d)
        fiches[fiche]["commission"] += _get_commission(d)

    result_list = []
    for fiche, info in fiches.items():
        result_list.append({
            "fiche": fiche,
            "nb_dossiers": info["nb"],
            "prime_totale_eur": round(info["prime"], 2),
            "commission_totale_eur": round(info["commission"], 2),
            "prime_moyenne_eur": round(info["prime"] / info["nb"], 2) if info["nb"] else 0,
        })

    result_list.sort(key=lambda x: x["commission_totale_eur"], reverse=True)

    result = {"fiches": result_list, "nb_fiches_utilisees": len(result_list)}
    _set_cache("roi_fiches", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 5. ACTIVITE
# ═══════════════════════════════════════════════════════════════════════════

def _build_activite(jours: int = 30) -> dict:
    cache_key = f"activite_{jours}"
    cached = _cached(cache_key)
    if cached:
        return cached

    entries = _load_audit_log()
    cutoff = datetime.utcnow() - timedelta(days=jours)

    par_jour: dict[str, int] = defaultdict(int)
    par_type: Counter = Counter()

    for entry in entries:
        ts_str = entry.get("ts", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if ts.replace(tzinfo=None) < cutoff:
            continue

        jour = ts.strftime("%Y-%m-%d")
        par_jour[jour] += 1
        action = entry.get("action", "autre")
        par_type[action] += 1

    # Série temporelle triée
    serie = [{"date": d, "nb_actions": n} for d, n in sorted(par_jour.items())]

    result = {
        "jours": jours,
        "nb_actions_total": sum(par_jour.values()),
        "par_jour": serie,
        "par_type": dict(par_type.most_common()),
    }
    _set_cache(cache_key, result)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# ROUTE REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════

def register_analytics_routes(app):
    """Enregistre les 5 endpoints analytics sur l'app Flask."""

    @app.route("/analytics/pipeline", methods=["GET"])
    def analytics_pipeline():
        """Pipeline commercial — dossiers par étape + montants."""
        return jsonify(_build_pipeline())

    @app.route("/analytics/forecast", methods=["GET"])
    def analytics_forecast():
        """Forecast commission — J+30/60/90."""
        return jsonify(_build_forecast())

    @app.route("/analytics/performance", methods=["GET"])
    def analytics_performance():
        """Performance globale — KPIs."""
        return jsonify(_build_performance())

    @app.route("/analytics/roi-fiches", methods=["GET"])
    def analytics_roi_fiches():
        """ROI par fiche CEE — trié par commission."""
        return jsonify(_build_roi_fiches())

    @app.route("/analytics/activite", methods=["GET"])
    def analytics_activite():
        """Activité récente — série temporelle audit log."""
        jours = request.args.get("jours", 30, type=int)
        if jours < 1:
            jours = 1
        if jours > 365:
            jours = 365
        return jsonify(_build_activite(jours))
