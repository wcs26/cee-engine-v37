"""
API CEE - WCS Pro (ORACLE-FUSED) — V37
========================================
POST /analyse              {siret}                        → analyse complète depuis SIRET
POST /expert               {naf, surface, departement}    → moteur expert direct
POST /expert/oracle        {departement, surface, ...}    → moteur Oracle pur (FOST, P6, couts)
POST /recalcul             {naf, departement, reponses}   → recalcul après réponses client
POST /predictions          {question_id, naf, surface}    → prédictions ML variables
POST /multisite/strategie  {sites|nb_sites, ...}          → stratégie parc
POST /multisite/optimiser  {profil, nb_sites, ...}        → optimisation parc par type
POST /closing              {departement, surface, ...}    → stratégie closing
POST /regles/75pct         {secteurs_surfaces}            → règle des 75%
POST /regles/tolerance-mixte {surface_tertiaire, surface_residentielle} → bâtiment mixte
POST /negociation          {volume_kwhc|surface, ...}     → comparatif acheteurs + parc
POST /validation/complete  {siret, adresse, surface, ...} → validation juridique
GET  /deadlines                                           → deadlines + status
GET  /regulatory                                          → veille réglementaire live
GET  /regulatory/changelog                                → changelog réglementaire
GET  /acheteurs                                           → liste acheteurs CEE
GET  /negociation/comparatif                              → comparatif (GET + query params)
GET  /siret/search         ?q=...&per_page=N              → proxy SIRET avec cache + fix branches
GET  /siret                (alias de /siret/search pour compat cache nav)
GET  /etablissements/<siren>                              → liste établissements actifs
GET  /proxy                ?url=...                       → proxy générique APIs gouv
GET  /dpe                  ?q=adresse&lat=&lon=           → lookup DPE/audit ADEME multi-datasets
GET  /batiment             ?lat=&lon=                     → BD TOPO IGN
POST /ai/groq              (SDK Python Groq)              → proxy GROQ LLM
POST /ai/gemini            ?key=...                       → proxy Gemini LLM
GET  /health                                              → status

V37 — Correctifs:
  • Fix SIRET branches : /siret/search patch `siege` avec matching_etablissements[0]
    quand la query est un SIRET 14 chiffres (auparavant renvoyait l'adresse du siège
    pour toute branche → mauvaise commune/zone/APE).
  • URL-encoding systématique des query params externes (urllib.parse.quote).
  • Helper HTTP centralisé (_fetch_json) avec retry 429 + SSL relaxé + cache LRU borné.
  • Logging structuré (remplace les print éparpillés).
  • Préflight CORS OPTIONS handler propre.
  • Cache SIRET borné (LRU 500) pour éviter fuite mémoire.
  • /etablissements/<siren> : limite_matching_etablissements=100 pour récupérer TOUS
    les établissements d'un SIREN (auparavant bloqué à 10 par défaut).

Tous les endpoints existants sont préservés à l'identique (never_regress).
"""

from __future__ import annotations

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import hmac
import json as _json
import logging
import math
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from datetime import datetime
from typing import Any

from flask import Flask, request, jsonify

from auto_detect import analyse_siret, moteur_expert, moteur_expert_v2
from auth import register_auth_routes, require_auth
from rag import register_rag_routes
from integrations import register_integrations_routes
from pncee import register_pncee_routes
from ratelimit import register_rate_limiter
from apidocs import register_apidocs_routes
from portail import register_portail_routes
from chat import register_chat_routes
from conformite import register_conformite_routes
from qualification import register_qualification_routes
from gisement_sirat import register_gisement_routes
from documents_client import register_documents_routes
from couts_chantier import register_couts_routes
from dossiers import register_dossiers_routes
from monday_sync import register_monday_routes
from top_fiches_secteur import register_top_fiches_routes
from post_signature import register_post_signature_routes
from tunnel import register_tunnel_routes
from analytics import register_analytics_routes
from prospection import register_prospection_routes
from fidelisation import register_fidelisation_routes
from formation import register_formation_routes
from pv_cotation import register_pv_routes
from pipeline import enrichir_audit, generate_full_questions
from negociation import (
    comparer_acheteurs, calculer_scenario_acheteur,
    ACHETEURS, PRIX_ACHETEURS_MAJ, PRIX_ACHETEURS_ALERTE_JOURS,
)
from multisite import optimiser_parc
from closing import analyser_closing
from moteur_cee_master import (
    get_zone, load_fiches, analyser, analyser_global,
    compute_full, check_deadline, load_deadlines,
    regle_75_pct, tolerance_mixte, check_remplacement_premature,
    strategie_multisite, P6_SEUILS,
)
import config


# ═══════════════════════════════════════════════════════════════════════════
# LOGGING & APP — V37 : format texte ou JSON structuré selon LOG_FORMAT env
# ═══════════════════════════════════════════════════════════════════════════

class _JsonFormatter(logging.Formatter):
    """Log structuré JSON — utilisable par les agrégateurs (Datadog, ELK, Loki)."""
    def format(self, record: logging.LogRecord) -> str:
        import os as _os
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Attributs extra injectés via logger.info("...", extra={...})
        for k, v in record.__dict__.items():
            if k not in {"args", "asctime", "created", "exc_info", "exc_text",
                         "filename", "funcName", "levelname", "levelno", "lineno",
                         "message", "module", "msecs", "msg", "name", "pathname",
                         "process", "processName", "relativeCreated", "stack_info",
                         "thread", "threadName", "taskName"}:
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return _json.dumps(payload, ensure_ascii=False)


_log_format = os.environ.get("LOG_FORMAT", "text").lower()
_log_handler = logging.StreamHandler()
if _log_format == "json":
    _log_handler.setFormatter(_JsonFormatter())
else:
    _log_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
logging.basicConfig(level=logging.INFO, handlers=[_log_handler], force=True)
logger = logging.getLogger("cee_api")
logger.info("cee_api starting", extra={"log_format": _log_format, "version": "V37-FUSED"})

app = Flask(__name__, static_folder=".", static_url_path="")

# V37 P3.3 — routes auth (/auth/login, /register, /me, /logout, /status)
# Active uniquement si CEE_JWT_SECRET env var définie. Sinon endpoints /auth/*
# renvoient 500 pour login/register mais /auth/status reste accessible.
register_auth_routes(app)
register_rag_routes(app)  # V37 P3.4 — /rag/search, /rag/reindex (TF-IDF local)
register_integrations_routes(app, require_auth)  # V37 P3.5 — Yousign, ERP, ATEE scraper
register_pncee_routes(app)  # V37 P4.1+P4.2 — Scoring PNCEE + Export XML/CSV officiel
register_rate_limiter(app)  # V37 P4.3 — rate limiting in-memory (30/120/300 req/min)
register_apidocs_routes(app)  # V37 P4.6 — /api/docs Swagger UI + /api/openapi.json
register_portail_routes(app)  # V37 P4.7 — /portail/<token> vue read-only client final
register_chat_routes(app)  # V37 P4.8 — /ai/chat compagnon contextualisé multi-tours
register_conformite_routes(app)  # V37 P5 — conformité Tessi-like (32 règles + WORM + horodatage + audit log)
register_qualification_routes(app)  # V37 P5.1 — trame G1T 16 étapes (qualification téléphonique 4 min)
register_gisement_routes(app)  # V37 P5.2 — gisement SIRAT (calibré 5 devis AHBFC : 6,24 MWhc/m² · 41,60€/m² · 8€/MWhc)
register_documents_routes(app)  # V37 P5.3 — pack docs unifié (header client réutilisé : gisement+devis+convention+AH)
register_couts_routes(app)      # V37 P5.4 — bibliothèque coûts réels chantier (matériaux + MO interne)
register_dossiers_routes(app)   # V37 P5.5 — persistance dossiers (UUID + lien partageable + dashboard)
register_monday_routes(app)     # V37 P5.6 — synchronisation bidirectionnelle Monday CRM
register_top_fiches_routes(app) # V37 P5.7 — TOP 5 fiches CEE par secteur (ROI pre-calcule)
register_post_signature_routes(app)  # V37 P7 — suivi post-signature (mandat→travaux→COFRAC→PNCEE→paiement)
register_tunnel_routes(app)  # V37.1 — Tunnel commercial unifié (lead→audit→R1→R2→signature→post_signature) + /analytics/sales-velocity
register_prospection_routes(app)     # V37 P8 — prospection active CEE (scan zone/secteur + batch audit + score lead)
register_analytics_routes(app)       # V37 P9 — analytics/reporting (pipeline, forecast, performance, ROI fiches, activité)
register_fidelisation_routes(app)    # V37 P10 — fidélisation client (PV, IRVE, maintenance, réversion CEE/m²)
register_formation_routes(app)       # V37 P11 — formation équipe (QCM R1/R2/Closing/ADERA/PNCEE)
register_pv_routes(app)              # V37 P12 — cotation photovoltaïque automatique (cotation/tarifs/simulation/comparatif)


@app.before_request
def _log_request_start():
    """Mesure de latence pour chaque requête."""
    import time as _time
    from flask import g
    g._req_t0 = _time.time()


@app.after_request
def _log_request_end(response):
    """Log structuré de la requête complétée (latence + code + path)."""
    try:
        import time as _time
        from flask import g
        dt_ms = int((_time.time() - getattr(g, "_req_t0", _time.time())) * 1000)
        # Ne logger que les endpoints API (pas les assets statiques)
        path = request.path or ""
        if not path.startswith("/static") and path != "/favicon.ico":
            level = logging.WARNING if response.status_code >= 400 else logging.INFO
            logger.log(level, "http %s %s %d %dms",
                       request.method, path, response.status_code, dt_ms,
                       extra={
                           "http_method": request.method,
                           "http_path": path,
                           "http_status": response.status_code,
                           "latency_ms": dt_ms,
                           "remote": request.remote_addr or "",
                       })
    except Exception:
        pass  # jamais faire planter la réponse à cause du logging
    return response


# V37.1 sécu : allowlist d'origines au lieu de "*". Évite que n'importe quel site web
# puisse appeler /ai/* et brûler les crédits LLM. Liste configurable via CEE_CORS_ORIGINS (CSV).
import os as _os_cors
_default_origins = "https://cee-engine-v37.fly.dev,http://localhost:5001,http://localhost:8080,http://127.0.0.1:5001"
ALLOWED_ORIGINS = set(o.strip() for o in _os_cors.environ.get("CEE_CORS_ORIGINS", _default_origins).split(",") if o.strip())


@app.after_request
def cors(response):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    elif not origin:
        # Same-origin requests (Origin header absent) : autorisé tacitement par le browser, pas besoin de header.
        pass
    # else : origin non listé → on ne pose pas le header, le browser bloque la réponse.
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Groq-Key, X-Claude-Key, X-Kimi-Key, X-OpenAI-Key, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Max-Age"] = "3600"
    # Headers de sécurité défensifs
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # Forcer rechargement des fichiers statiques (pas de cache navigateur)
    if response.content_type and ("html" in response.content_type or "javascript" in response.content_type):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        return ("", 204)


@app.before_request
def _ai_origin_guard():
    """V37.1 sécu : refuse les requêtes /ai/* qui ne viennent pas d'une origine autorisée
    (sauf same-origin où Origin n'est pas envoyé). Bloque l'abus public des proxies LLM."""
    if request.path.startswith("/ai/") and request.method != "OPTIONS":
        origin = request.headers.get("Origin", "")
        if origin and origin not in ALLOWED_ORIGINS:
            return jsonify({"error": "Origin non autorisée pour /ai/*"}), 403
        # Pas d'Origin = soit same-origin (toléré), soit client non-navigateur (curl, etc.).
        # Pour les non-navigateur on exige X-App-Token si CEE_AI_REQUIRE_TOKEN est activé.
        if not origin and _os_cors.environ.get("CEE_AI_REQUIRE_TOKEN") == "1":
            expected = _os_cors.environ.get("CEE_APP_TOKEN", "")
            provided = request.headers.get("X-App-Token", "")
            if not expected or not provided or not hmac.compare_digest(expected, provided):
                return jsonify({"error": "X-App-Token requis pour clients non-navigateur"}), 403


# ═══════════════════════════════════════════════════════════════════════════
# CACHE LRU BORNÉ (SIRET + générique)
# ═══════════════════════════════════════════════════════════════════════════

_siret_cache_ttl = 86400  # 24 h
_SIRET_CACHE_MAX = 500


class _LRUCache(OrderedDict):
    """OrderedDict avec éviction LRU quand max dépassé."""

    def __init__(self, maxsize: int = 500) -> None:
        super().__init__()
        self.maxsize = maxsize

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.maxsize:
            self.popitem(last=False)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value


# Historiquement un dict : on garde le nom (_siret_cache) et l'API d'accès
# pour compatibilité avec d'éventuels imports externes, mais avec éviction LRU.
_siret_cache: _LRUCache = _LRUCache(maxsize=_SIRET_CACHE_MAX)


def _cache_get(key: str):
    """Lit une valeur (data, ts) du cache si non expirée."""
    if key not in _siret_cache:
        return None
    data, ts = _siret_cache[key]
    if time.time() - ts >= _siret_cache_ttl:
        return None
    return data


def _cache_set(key: str, value: Any) -> None:
    _siret_cache[key] = (value, time.time())


# ═══════════════════════════════════════════════════════════════════════════
# HTTP HELPERS (SSL relaxé + retry 429)
# ═══════════════════════════════════════════════════════════════════════════

def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch_json(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str | None = None,
    timeout: int = 10,
    retries: int = 3,
):
    """GET/POST JSON avec retry exponentiel sur 429.

    Retourne (data_dict, None) en cas de succès, (None, (code, message)) sinon.
    """
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    ctx = _ssl_ctx()

    last_err: tuple[int, str] | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                raw = resp.read()
                return _json.loads(raw.decode("utf-8")), None
        except urllib.error.HTTPError as he:
            last_err = (he.code, f"HTTP {he.code}")
            if he.code == 429 and attempt < retries - 1:
                wait = 2 * (attempt + 1)
                logger.warning("429 %s, retry in %ss (attempt %d)", url, wait, attempt + 1)
                time.sleep(wait)
                continue
            return None, last_err
        except Exception as e:
            last_err = (502, str(e))
            logger.warning("fetch %s error: %s", url, e)
            return None, last_err
    return None, (last_err or (500, "unknown"))


def _qs(params: dict[str, Any]) -> str:
    """Construit une query string URL-encodée."""
    safe = {k: ("" if v is None else str(v)) for k, v in params.items()}
    return urllib.parse.urlencode(safe)


# ═══════════════════════════════════════════════════════════════════════════
# ROUTES STATIQUES
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return app.send_static_file("oracle.html")


@app.route("/legacy")
def legacy_index():
    return app.send_static_file("index.html")


_APP_BOOT_TS = None  # défini à la première requête (uptime)

@app.route("/health", methods=["GET"])
def health():
    """V37 — Health check enrichi pour monitoring.

    Expose : version, fiches, IAs configurées (booléens uniquement, JAMAIS les clés),
    cache SIRET stats, uptime, modules Python critiques OK.
    """
    import os as _os
    import time as _time
    global _APP_BOOT_TS
    if _APP_BOOT_TS is None:
        _APP_BOOT_TS = _time.time()

    fiches = load_fiches()
    fiches_actives = sum(1 for f in fiches if f.get("actif", True))

    # Stats cache SIRET (sans exposer les données)
    cache_size = len(_siret_cache) if isinstance(_siret_cache, (dict,)) or hasattr(_siret_cache, '__len__') else 0

    # IAs configurées (env serveur — booléens uniquement)
    ai_status = {
        "groq":    bool(_os.environ.get("GROQ_API_KEY", "")),
        "gemini":  bool(_os.environ.get("GEMINI_API_KEY", "")),
        "claude":  bool(_os.environ.get("ANTHROPIC_API_KEY", "")),
        "kimi":    bool(_os.environ.get("MOONSHOT_API_KEY", "")),
        "openai":  bool(_os.environ.get("OPENAI_API_KEY", "")),
    }
    ai_configured = sum(1 for v in ai_status.values() if v)

    # Modules critiques
    modules_ok = {}
    for mod in ["moteur_cee_master", "auto_detect", "negociation", "multisite",
                "closing", "cee_excellence_pro", "pipeline", "predictions"]:
        try:
            __import__(mod)
            modules_ok[mod] = True
        except Exception:
            modules_ok[mod] = False
    modules_healthy = all(modules_ok.values())

    # V37.3.5 — stats business pipeline (lecture légère via list_tunnels + alerts)
    pipeline = {"size": 0, "by_stage": {}, "alertes_critique": 0, "alertes_haute": 0, "signatures_mois_courant": 0}
    try:
        from tunnel import list_tunnels, detect_stagnants, sales_velocity, TUNNEL_STAGES
        all_t = list_tunnels()
        pipeline["size"] = len(all_t)
        for s in TUNNEL_STAGES:
            pipeline["by_stage"][s] = sum(1 for t in all_t if t.get("current_stage") == s)
        alerts = detect_stagnants()
        pipeline["alertes_critique"] = sum(1 for a in alerts if a.get("severity") == "critique")
        pipeline["alertes_haute"] = sum(1 for a in alerts if a.get("severity") == "haute")
        sv = sales_velocity()
        pipeline["signatures_mois_courant"] = sv.get("total_signatures", 0)
        pipeline["objectif_global"] = sv.get("objectif_global_calcule", 0)
        pipeline["vendors_actifs"] = len(sv.get("vendors", []))
    except Exception as e:
        pipeline["error"] = str(e)[:80]

    return jsonify({
        "status": "ok" if modules_healthy else "degraded",
        "service": "CEE Engine V37.3",
        "version": "V37.3.18",
        "fiches": len(fiches),
        "fiches_actives": fiches_actives,
        "uptime_seconds": int(_time.time() - _APP_BOOT_TS),
        "pipeline": pipeline,  # V37.3.5 — signal métier pour monitoring/dashboard
        "config": {
            "prix_cumac_eur_mwh": round(config.PRIX_CUMAC * 1000, 2),
            "prix_cumac_precarite_eur_mwh": round(config.PRIX_CUMAC_PRECARITE * 1000, 2),
            "commission_defaut_pct": round(config.COMMISSION_RATE * 100, 2),
        },
        "ai": {
            "configured_count": ai_configured,
            "available": ai_status,  # booléens seulement
        },
        "cache": {
            "siret_entries": cache_size,
            "ttl_seconds": _siret_cache_ttl,
        },
        "modules": modules_ok,
        "log_format": _os.environ.get("LOG_FORMAT", "text"),
    })


# ═══════════════════════════════════════════════════════════════════════════
# CORE CEE — analyse / expert / recalcul / predictions
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/analyse", methods=["POST"])
def analyse():
    data = request.json or {}
    siret = str(data.get("siret", "")).strip().replace(" ", "")

    if not siret:
        return jsonify({"error": "siret requis"}), 400

    result = analyse_siret(siret)

    if "error" in result:
        return jsonify(result), 404

    # V37.2 → V37.3.10 — Auto-création tunnel + extraction data métier depuis /analyse.
    # Format réel observé : entreprise.{naf, nom, departement, commune}, surface_estimee top-level,
    # energie top-level, resultats (au lieu de oracle).
    if os.environ.get("CEE_TUNNEL_AUTO", "1") == "1":
        try:
            from tunnel import create_tunnel, list_tunnels, advance_tunnel
            existing = [t for t in list_tunnels() if t.get("siret") == siret]
            if existing and isinstance(result, dict):
                # V37.3.17 — expose le tunnel existant à l'UI (sinon Jimmy croit qu'il n'a rien)
                result["tunnel_id"] = existing[0]["tunnel_id"]
                result["tunnel_existing_stage"] = existing[0].get("current_stage")
            if not existing and isinstance(result, dict):
                ent = result.get("entreprise", {}) or {}
                vendor = data.get("vendor", "") or result.get("vendor", "")
                rs = ent.get("nom", "") or ent.get("raison_sociale", "")
                t = create_tunnel(siret=siret, vendor=vendor, source="oracle_audit", raison_sociale=rs)
                # Extraction data métier — noms de champs réels du retour /analyse
                naf = ent.get("naf", "") or ent.get("ape", "")
                dpt = ent.get("departement", "") or (ent.get("cp", "") or "")[:2]
                surface = (result.get("surface_estimee", 0) or
                           ent.get("surface_estimee_m2", 0) or
                           ent.get("surface", 0) or 0)
                energie = result.get("energie") or ent.get("energie") or ""
                # resultats peut être dict avec pack ou list — défensif
                res_obj = result.get("resultats") or result.get("oracle") or {}
                if isinstance(res_obj, dict):
                    pack = res_obj.get("pack") or []
                elif isinstance(res_obj, list):
                    pack = res_obj
                else:
                    pack = []
                fiches = [f.get("ref") or f.get("fiche") for f in pack
                          if isinstance(f, dict) and (f.get("ref") or f.get("fiche"))]
                # V37.3.12 — par défaut rge_installateur=True (cas le plus fréquent en CEE pro).
                # Le commercial corrige manuellement si l'installateur n'est pas RGE.
                # Sinon le verdict PNCEE est systématiquement STOP par défaut, pénalisant l'audit initial.
                advance_tunnel(t["tunnel_id"], target_stage="audit", data={
                    "fiches": fiches[:10],
                    "naf": naf,
                    "ape": naf,
                    "surface": float(surface) if surface else 0,
                    "departement": dpt,
                    "secteur": result.get("secteur", ""),
                    "energie": energie,
                    "rge_installateur": True,  # défaut optimiste, ajustable
                    "date_engagement": "",
                })
                result["tunnel_id"] = t["tunnel_id"]
        except Exception:
            pass  # ne casse jamais l'audit principal

    return jsonify(result)


@app.route("/expert", methods=["POST"])
def expert():
    data = request.json or {}

    naf = data.get("naf", "")
    surface = float(data.get("surface", 0))
    departement = str(data.get("departement", ""))
    energie = data.get("energie")
    prix_cumac = float(data.get("prix_cumac", config.PRIX_CUMAC))
    activity_sector = data.get("activity_sector")
    coup_de_pouce = data.get("coup_de_pouce", False)

    if not naf or not surface or not departement:
        return jsonify({"error": "naf, surface, departement requis"}), 400

    # Override temporaire du prix cumac
    original = config.PRIX_CUMAC
    config.PRIX_CUMAC = prix_cumac

    try:
        # Moteur expert V2 (detection NAF)
        result = moteur_expert_v2(
            entreprise={"naf": naf},
            surface=surface,
            energie=energie,
            departement=departement,
        )
    finally:
        config.PRIX_CUMAC = original

    # Enrichir avec calculs Oracle-level
    zone = get_zone(departement)
    if zone:
        params = {
            "departement": departement,
            "zone": zone,
            "surface": surface,
            "quantite": int(data.get("quantite", 0)),
            "puissance": float(data.get("puissance", 0)),
            "energie": energie,
            "nb_logements": int(data.get("nb_logements", 0)),
            "puissance_froid": float(data.get("puissance_froid", 0)),
        }

        oracle_results = analyser(
            params,
            activity_sector=activity_sector,
            coup_de_pouce=coup_de_pouce,
            prix_cumac=prix_cumac,
        )

        globaux = analyser_global(oracle_results)

        result["oracle"] = {
            "pack": oracle_results,
            "globaux": globaux,
        }

    result["prix_cumac"] = prix_cumac
    result["audit_questions"] = enrichir_audit(result, {"age_batiment": 15})

    # Questions structurées par fiche
    fiches_db = {f["ref"]: f for f in load_fiches()}
    qs = {}
    for r in result.get("pack", []):
        fiche = fiches_db.get(r["fiche"])
        if fiche:
            qs[r["fiche"]] = generate_full_questions(fiche)
    result["questions_structurees"] = qs

    # ── Confiance factuelle (données + calcul) ──
    surface_source = data.get("surface_source", "")  # "client", "estimee", ""
    dpe_connu = bool(data.get("dpe"))
    has_surface_client = surface_source == "client" or (surface > 0 and not surface_source)

    if has_surface_client and dpe_connu:
        conf_donnees = "haute"
    elif surface > 0:
        conf_donnees = "moyenne"
    else:
        conf_donnees = "basse"

    pack = result.get("pack", [])
    nb_fiches = len(pack)
    nb_surface = sum(1 for r in pack if r.get("type") == "surface")
    if nb_fiches > 0 and nb_surface == nb_fiches:
        conf_calcul = "haute"
    elif nb_fiches > 0 and nb_surface >= nb_fiches / 2:
        conf_calcul = "moyenne"
    else:
        conf_calcul = "basse"

    _conf_rank = {"haute": 3, "moyenne": 2, "basse": 1}
    _conf_label = {3: "haute", 2: "moyenne", 1: "basse"}
    conf_globale = _conf_label[min(_conf_rank[conf_donnees], _conf_rank[conf_calcul])]

    note_parts = []
    if conf_donnees == "haute":
        note_parts.append("Surface declaree par le client, DPE connu")
    elif conf_donnees == "moyenne":
        note_parts.append("Surface fournie (source non confirmee)")
    else:
        note_parts.append("Aucune donnee terrain")
    note_parts.append(f"calcul FOST direct sur {nb_surface}/{nb_fiches} fiches")

    result["confiance"] = {
        "confiance_donnees": conf_donnees,
        "confiance_calcul": conf_calcul,
        "confiance_globale": conf_globale,
        "note": ", ".join(note_parts),
    }

    return jsonify(result)


@app.route("/expert/oracle", methods=["POST"])
def expert_oracle():
    """Endpoint Oracle-level pur : calculs complets avec FOST, P6, couts, coverage."""
    data = request.json or {}

    departement = str(data.get("departement", ""))
    zone = get_zone(departement)
    if not zone:
        return jsonify({"error": "departement invalide"}), 400

    surface = float(data.get("surface", 0))
    energie = data.get("energie")
    activity_sector = data.get("activity_sector")
    coup_de_pouce = data.get("coup_de_pouce", False)
    precarite = data.get("precarite", False)
    tva_reduite = data.get("tva_reduite", False)
    prix_cumac = float(data.get("prix_cumac", 0)) or None  # None = auto

    params = {
        "departement": departement,
        "zone": zone,
        "surface": surface,
        "quantite": int(data.get("quantite", 0)),
        "puissance": float(data.get("puissance", 0)),
        "energie": energie,
        "nb_logements": int(data.get("nb_logements", 0)),
        "puissance_froid": float(data.get("puissance_froid", 0)),
        "longueur": float(data.get("longueur", 0)),
    }

    resultats = analyser(
        params,
        activity_sector=activity_sector,
        coup_de_pouce=coup_de_pouce,
        prix_cumac=prix_cumac,
        precarite=precarite,
        tva_reduite=tva_reduite,
    )

    globaux = analyser_global(resultats)

    prix_utilise = config.PRIX_CUMAC_PRECARITE if precarite else config.PRIX_CUMAC
    if prix_cumac:
        prix_utilise = prix_cumac

    return jsonify({
        "pack": resultats,
        "globaux": globaux,
        "params": params,
        "prix_cumac_mwhc": round(prix_utilise * 1000, 2),
        "precarite": precarite,
        "prix_classique_mwhc": round(config.PRIX_CUMAC * 1000, 2),
        "prix_precarite_mwhc": round(config.PRIX_CUMAC_PRECARITE * 1000, 2),
        "activity_sector": activity_sector,
        "coup_de_pouce": coup_de_pouce,
    })


@app.route("/predictions", methods=["POST"])
def predictions():
    from predictions import get_predictions
    data = request.json or {}
    question_id = data.get("question_id", "")
    naf = data.get("naf", "")
    surface = float(data.get("surface", 0))
    preds = get_predictions(question_id, naf=naf, surface=surface)
    return jsonify({"question_id": question_id, "predictions": preds})


@app.route("/recalcul", methods=["POST"])
def recalcul():
    data = request.json or {}
    naf = data.get("naf", "")
    departement = str(data.get("departement", ""))
    reponses = data.get("reponses", {})
    prix_cumac = float(data.get("prix_cumac", config.PRIX_CUMAC))
    activity_sector = data.get("activity_sector")
    coup_de_pouce = data.get("coup_de_pouce", False)

    surface = float(reponses.get("surface", data.get("surface", 0)))
    energie = reponses.get("energie", data.get("energie"))

    if not naf or not departement:
        return jsonify({"error": "naf et departement requis"}), 400

    zone = get_zone(departement)
    if not zone:
        return jsonify({"error": "departement invalide"}), 400

    params = {
        "departement": departement,
        "zone": zone,
        "surface": surface,
        "quantite": int(reponses.get("quantite", 0) or 0),
        "puissance": float(reponses.get("puissance", 0) or 0),
        "energie": energie,
        "nb_logements": int(reponses.get("nb_logements", 0) or 0),
        "puissance_froid": float(reponses.get("puissance_froid", 0) or 0),
        "longueur": float(reponses.get("longueur", 0) or 0),
    }

    # Calcul Oracle-level
    resultats = analyser(
        params,
        activity_sector=activity_sector,
        coup_de_pouce=coup_de_pouce,
        prix_cumac=prix_cumac,
    )

    globaux = analyser_global(resultats)

    return jsonify({
        "pack": resultats,
        "globaux": globaux,
        "params": params,
        "prix_cumac": prix_cumac,
        "source": "recalcul_oracle",
    })


# ═══════════════════════════════════════════════════════════════════════════
# MULTISITE / CLOSING / RÈGLES
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/multisite/strategie", methods=["POST"])
def multisite_strategie():
    """Calcule la stratégie optimale pour un parc multi-bâtiments."""
    data = request.json or {}
    sites = data.get("sites", [])
    if not sites:
        nb = int(data.get("nb_sites", 1))
        surf = float(data.get("surface_par_site", 500))
        secteur = data.get("secteur", "BAT")
        sites = [{"surface": surf, "secteur": secteur} for _ in range(nb)]

    strat = strategie_multisite(sites)

    # Calcul prime estimée par site + total
    dep = str(data.get("departement", "75"))
    zone = get_zone(dep)
    if zone:
        params = {
            "departement": dep, "zone": zone,
            "surface": sites[0].get("surface", 500) if sites else 500,
            "quantite": 20, "puissance": 50,
            "energie": data.get("energie"),
            "nb_logements": 0, "puissance_froid": 0, "longueur": 0,
        }
        resultats = analyser(params)
        globaux = analyser_global(resultats)
        strat["prime_par_site"] = round(globaux.get("total_prime_nette", 0), 2)
        strat["prime_totale_parc"] = round(globaux.get("total_prime_nette", 0) * len(sites), 2)
        strat["nb_fiches_par_site"] = globaux.get("nb_fiches", 0)

    # Règles P6
    strat["regles_p6"] = {
        "seuil_delegation_partielle": "2 TWhc",
        "volume_min_delegataire": "300 MkWhc",
        "duree_contrat": "5 ans (personnes morales)",
        "maintien_fonctionnement": "6 ans minimum",
        "taux_controle_cofrac": "30%",
        "conseil": (
            "Volume parc important → négocier directement avec un délégataire (meilleur prix/kWhc)"
            if strat.get("surface_totale", 0) > 5000 else
            "Passer par un mandataire pour simplifier la gestion administrative"
        ),
    }

    return jsonify(strat)


@app.route("/closing", methods=["POST"])
def closing():
    """Stratégie de closing : ne perdre aucun marché."""
    data = request.json or {}
    dep = str(data.get("departement", "75"))
    zone = get_zone(dep)
    if not zone:
        return jsonify({"error": "departement invalide"}), 400

    surface = float(data.get("surface", 500))
    energie = data.get("energie")
    nb_sites = int(data.get("nb_sites", 1))
    activity_sector = data.get("activity_sector")

    params = {
        "departement": dep, "zone": zone, "surface": surface,
        "quantite": max(1, round(surface / 25)),
        "puissance": float(data.get("puissance", round(surface * 0.05))),
        "energie": energie,
        "nb_logements": int(data.get("nb_logements", 0)),
        "puissance_froid": float(data.get("puissance_froid", 0)),
        "longueur": 0,
    }

    resultats = analyser(params, activity_sector=activity_sector)
    globaux = analyser_global(resultats)
    secteurs = list(set(r.get("secteur", "BAT") for r in resultats))

    result = analyser_closing(
        resultats, globaux, secteurs, nb_sites,
        data.get("qualite_dossier", "standard"), surface
    )
    return jsonify(result)


@app.route("/multisite/optimiser", methods=["POST"])
def multisite_optimiser():
    """Analyse complète d'un parc multi-sites : chaque type de bâtiment analysé
    individuellement, puis stratégie globale optimisée."""
    data = request.json or {}

    profil = data.get("profil", "_default")
    nb_sites = int(data.get("nb_sites", 1))
    surface_moy = float(data.get("surface_moyenne", 500))
    dep = str(data.get("departement", "75"))
    qualite = data.get("qualite_dossier", "standard")

    result = optimiser_parc(profil, nb_sites, surface_moy, dep, qualite)
    return jsonify(result)


@app.route("/regles/75pct", methods=["POST"])
def regles_75pct():
    """Applique la règle des 75% pour un bâtiment multi-secteur."""
    data = request.json or {}
    secteurs = data.get("secteurs_surfaces", {})
    secteur = regle_75_pct(secteurs)
    total = sum(secteurs.values())
    dominant_pct = round(secteurs.get(secteur, 0) / total * 100, 1) if total > 0 else 0
    return jsonify({
        "secteur_applicable": secteur,
        "pourcentage_dominant": dominant_pct,
        "regle": "75%" if dominant_pct >= 75 else "plus_defavorable",
        "explication": (
            f"Secteur {secteur} représente {dominant_pct}% (≥ 75%) → seul secteur retenu"
            if dominant_pct >= 75 else
            f"Aucun secteur ≥ 75% → secteur {secteur} retenu (plus défavorable)"
        ),
    })


@app.route("/regles/tolerance-mixte", methods=["POST"])
def regles_tolerance_mixte():
    """Tolérance bâtiment mixte tertiaire/résidentiel."""
    data = request.json or {}
    surf_tert = float(data.get("surface_tertiaire", 0))
    surf_res = float(data.get("surface_residentielle", 0))
    secteur, nb_log = tolerance_mixte(surf_tert, surf_res)
    return jsonify({
        "secteur_applicable": secteur,
        "nb_logements_equivalents": nb_log,
        "explication": (
            f"Tertiaire dominant ({surf_tert}m² vs {surf_res}m² résidentiel) → secteur BAT"
            if secteur == "BAT" else
            f"Résidentiel dominant → {surf_tert}m² tertiaire = {nb_log} logement(s) équivalent(s) (65m²/logement)"
        ),
    })


# ═══════════════════════════════════════════════════════════════════════════
# RÉGLEMENTAIRE
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/deadlines", methods=["GET"])
def deadlines():
    """Retourne toutes les deadlines avec status."""
    dl = load_deadlines()
    result = {}
    for ref, date in dl.items():
        result[ref] = check_deadline(ref, dl)
    return jsonify(result)


@app.route("/regulatory", methods=["GET"])
def regulatory():
    """Veille réglementaire temps réel — deadlines, prix, alertes."""
    dl = load_deadlines()
    fiches = load_fiches()
    now = datetime.now()

    # Abrogations
    abrogations = {}
    for ref, date_str in dl.items():
        try:
            deadline = datetime.strptime(date_str, "%Y-%m-%d")
            if now >= deadline:
                abrogations[ref] = {"date": date_str, "status": "abrogee"}
            elif (deadline - now).days <= 180:
                abrogations[ref] = {
                    "date": date_str,
                    "status": "attention",
                    "jours_restants": (deadline - now).days,
                }
        except (ValueError, TypeError, KeyError):
            pass

    # Alertes réglementaires P6
    alertes = []
    abrogees_recentes = [
        (ref, info) for ref, info in abrogations.items()
        if info["status"] == "abrogee"
        and (now - datetime.strptime(info["date"], "%Y-%m-%d")).days < 90
    ]
    if abrogees_recentes:
        refs = [r for r, _ in abrogees_recentes[:5]]
        alertes.append({
            "urgence": "haute",
            "message": f"{len(abrogees_recentes)} fiche(s) abrogée(s) récemment: {', '.join(refs)}",
            "type": "abrogation",
        })

    a_venir = [
        (ref, info) for ref, info in abrogations.items()
        if info["status"] == "attention"
    ]
    if a_venir:
        alertes.append({
            "urgence": "haute",
            "message": f"{len(a_venir)} fiche(s) bientôt abrogée(s) (< 6 mois)",
            "type": "deadline",
        })

    # P6 infos
    alertes.append({
        "urgence": "info",
        "message": "P6 (2026-2030): obligation 1 050 TWhc/an, précarité 280 TWhc, COFRAC 30%",
        "type": "reglementation",
    })

    # V36: Alerte prix acheteurs périmés
    try:
        prix_maj = datetime.strptime(PRIX_ACHETEURS_MAJ, "%Y-%m-%d")
        jours_depuis_maj = (now - prix_maj).days
        if jours_depuis_maj > PRIX_ACHETEURS_ALERTE_JOURS:
            alertes.append({
                "urgence": "haute",
                "message": f"Prix acheteurs CEE non mis à jour depuis {jours_depuis_maj} jours (dernière MAJ: {PRIX_ACHETEURS_MAJ}). Les estimations de prime peuvent être inexactes.",
                "type": "prix_perime",
            })
    except (ValueError, TypeError):
        pass

    # Prix cumac
    prix_info = {
        "valeur": round(config.PRIX_CUMAC * 1000, 2),
        "unite": "EUR/MWhc",
        "source": "config CEE Engine",
        "classique": round(config.PRIX_CUMAC * 1000, 2),
        "precarite": round(config.PRIX_CUMAC_PRECARITE * 1000, 2),
        "acheteurs_maj": PRIX_ACHETEURS_MAJ,
    }

    # Opportunités récentes (fiches actives à fort potentiel)
    opportunites = []
    for f in fiches:
        if not f.get("actif", True):
            continue
        if f.get("p6_bonus", 1) > 1:
            opportunites.append({
                "ref": f["ref"],
                "desc": f"Coup de Pouce P6 ×{f['p6_bonus']} — {f.get('nom','')}",
            })
        if f.get("zero_euro"):
            opportunites.append({
                "ref": f["ref"],
                "desc": f"Opération 0€ client — {f.get('nom','')}",
            })

    # Stats
    actives = sum(1 for f in fiches if f.get("actif", True))
    inactives = len(fiches) - actives

    return jsonify({
        "version": "V37-LIVE",
        "timestamp": now.isoformat(),
        "fiches_actives": actives,
        "fiches_inactives": inactives,
        "abrogations": abrogations,
        "alertes": alertes,
        "prixMWhc": prix_info,
        "opportunites": opportunites[:20],
        "lastArrete": "Arrêté du 22/12/2025 (P6)",
    })


@app.route("/regulatory/changelog", methods=["GET"])
def regulatory_changelog():
    """Changelog réglementaire — format versionné (compat frontend).

    Le frontend itère `entry.version` + `entry.changes[]`. On regroupe les
    événements par trimestre (pseudo-version) pour cohérence visuelle.
    """
    dl = load_deadlines()
    raw_entries = []
    for ref, date_str in sorted(dl.items(), key=lambda x: x[1], reverse=True):
        raw_entries.append({"date": date_str, "ref": ref, "type": "abrogation",
                            "desc": f"Abrogation {ref}"})
    raw_entries.insert(0, {"date": "2025-11-04", "ref": "P6", "type": "prix",
                           "desc": "Décret P6 publié — obligation 1 050 TWhc/an dès 2026"})
    raw_entries.insert(0, {"date": "2026-02-25", "ref": "LED", "type": "abrogation",
                           "desc": "Abrogation fiches LED (BAR-EQ-110, BAT-EQ-127, IND-BA-116)"})

    # Regrouper par "version" (trimestre)
    from collections import OrderedDict
    grouped = OrderedDict()
    for e in raw_entries:
        d = e["date"]
        try:
            y, m, _ = d.split("-", 2)
            quarter = (int(m) - 1) // 3 + 1
            version = f"{y}.Q{quarter}"
        except (ValueError, AttributeError):
            version = d[:7] if d else "?"
        if version not in grouped:
            grouped[version] = {"version": version, "date": d, "changes": []}
        grouped[version]["changes"].append({"type": e["type"], "ref": e["ref"], "desc": e["desc"]})

    versioned = list(grouped.values())
    limit = int(request.args.get("limit", 20))
    return jsonify({
        "changelog": versioned[:limit],
        # Compat ancienne : garder `entries` à plat pour scripts éventuels
        "entries": raw_entries[:limit],
    })


@app.route("/regulatory/intelligence", methods=["GET"])
def regulatory_intelligence():
    """V37 — Intelligence réglementaire contextuelle, 5 lentilles.

    Cœur de l'outil "audit prédictif/proactif/intelligent" :
      - optimiste  : signaux positifs + actions à fort ROI
      - pessimiste : risques + protections
      - opportuniste : fenêtres temporelles + couplages multi-fiches
      - predictif : projections P6 (abrogations probables, évolution prix)
      - proactif : actions immédiates + calendrier

    Query params (optionnels mais recommandés pour contextualiser) :
      sectors=BAT,BAR,IND,TRA,AGRI  |  zone=H1|H2|H3  |  surface=500  |  ape=68.20A
    """
    from datetime import datetime, timedelta
    ctx_sectors = [s.strip() for s in request.args.get("sectors", "").split(",") if s.strip()]
    ctx_zone = request.args.get("zone", "")
    try:
        ctx_surface = float(request.args.get("surface", 0) or 0)
    except (ValueError, TypeError):
        ctx_surface = 0.0
    ctx_ape = request.args.get("ape", "")

    now = datetime.now()
    dl = load_deadlines()
    fiches = load_fiches()
    fiches_actives = [f for f in fiches if f.get("actif", True)]

    # Filtrer fiches sur le contexte sectoriel si fourni
    def secteur_of(ref: str) -> str:
        return ref.split("-")[0] if "-" in ref else ""

    relevant_fiches = fiches_actives
    if ctx_sectors:
        relevant_fiches = [f for f in fiches_actives if secteur_of(f.get("ref", "")) in ctx_sectors]

    # Fiches à fort bonus P6 ou 0€
    p6_bonus = [f for f in relevant_fiches if f.get("p6_bonus", 1) > 1]
    zero_euro = [f for f in relevant_fiches if f.get("zero_euro")]

    # Abrogations (passées et à venir)
    abrog_passed = []
    abrog_upcoming = []
    for ref, date_str in dl.items():
        try:
            dd = datetime.strptime(date_str, "%Y-%m-%d")
            days = (dd - now).days
            if days < 0:
                abrog_passed.append({"ref": ref, "date": date_str, "days_ago": -days})
            elif days <= 365:
                abrog_upcoming.append({"ref": ref, "date": date_str, "days_remaining": days})
        except (ValueError, TypeError):
            pass
    abrog_upcoming.sort(key=lambda x: x["days_remaining"])

    # Prix historique simulé (dernières évolutions connues marché)
    prix_hist = [
        {"date": "2025-06-01", "valeur": 7.80},
        {"date": "2025-09-01", "valeur": 8.30},
        {"date": "2025-12-01", "valeur": 8.78},
        {"date": "2026-03-01", "valeur": 8.78},
        {"date": now.strftime("%Y-%m-%d"), "valeur": round(config.PRIX_CUMAC * 1000, 2)},
    ]
    prix_actuel = round(config.PRIX_CUMAC * 1000, 2)
    # Tendance
    if len(prix_hist) >= 2:
        delta = prix_hist[-1]["valeur"] - prix_hist[0]["valeur"]
        tendance = "hausse" if delta > 0.2 else ("baisse" if delta < -0.2 else "stable")
    else:
        tendance = "stable"

    # Deadline Coup de Pouce chauffage (fin période P5) ~ 2025-12-31 dans config
    cdp_deadline = datetime(2025, 12, 31)
    cdp_mois = max(0, int((cdp_deadline - now).days / 30)) if now < cdp_deadline else 0
    # Après CDP P5, P6 ouvre 2026-01-01
    if now >= cdp_deadline:
        cdp_deadline_p6 = datetime(2026, 12, 31)
        cdp_mois = max(0, int((cdp_deadline_p6 - now).days / 30))

    # Vélocité réglementaire
    velocite = "acceleration" if len(abrog_upcoming) >= 3 or len(abrog_passed[:5]) >= 3 else "stable"

    # ═══ LENTILLE 1 — OPTIMISTE ═══
    signaux = []
    if p6_bonus:
        signaux.append({"force": "forte", "desc": f"{len(p6_bonus)} fiche(s) avec bonus P6 ×{max((f.get('p6_bonus',1) for f in p6_bonus), default=1)} actives",
                        "verifie": "Arrêté 22/12/2025"})
    if zero_euro:
        signaux.append({"force": "forte", "desc": f"{len(zero_euro)} opération(s) 0€ client disponibles (précarité)", "verifie": "Fiches actives"})
    if tendance == "hausse":
        signaux.append({"force": "moyenne", "desc": f"Prix cumac en hausse ({prix_hist[0]['valeur']}→{prix_actuel} €/MWhc)",
                        "verifie": "EMMY marché"})
    if not signaux:
        signaux.append({"force": "moyenne", "desc": "Conditions de marché stables", "verifie": "EMMY"})

    actions_opt = []
    for f in sorted(p6_bonus, key=lambda x: -x.get("p6_bonus", 1))[:3]:
        actions_opt.append({"ref": f.get("ref", ""), "action": f"Prioriser {f.get('nom','')}",
                            "roi": f"Bonus ×{f.get('p6_bonus',1)}"})
    for f in zero_euro[:2]:
        actions_opt.append({"ref": f.get("ref", ""), "action": f"Activer {f.get('nom','')} en 0€ précarité",
                            "roi": "Prime couvre 100% du coût"})

    score_opt = min(100, 40 + len(signaux) * 10 + min(30, len(p6_bonus) * 3))

    # ═══ LENTILLE 2 — PESSIMISTE ═══
    risques = []
    for a in abrog_upcoming[:3]:
        gravite = "haute" if a["days_remaining"] <= 90 else "moyenne"
        risques.append({"gravite": gravite, "desc": f"Abrogation {a['ref']} dans {a['days_remaining']} jours",
                        "prediction": "Dossiers à déposer avant la date limite",
                        "verifie": a["date"]})
    if velocite == "acceleration":
        risques.append({"gravite": "moyenne", "desc": "Vélocité réglementaire élevée — arrêtés fréquents",
                        "prediction": "Risque d'obsolescence de fiches en cours de projet", "verifie": "P6 transition"})
    if tendance == "baisse":
        risques.append({"gravite": "haute", "desc": "Prix cumac en baisse",
                        "prediction": "Valoriser rapidement les dossiers", "verifie": "EMMY"})
    if not risques:
        risques.append({"gravite": "basse", "desc": "Aucune abrogation critique < 12 mois sur votre contexte",
                        "verifie": "Deadlines"})

    protections = [
        {"urgence": "haute", "action": "Sécuriser prix cumac par contrat ferme sur 12 mois"},
        {"urgence": "moyenne", "action": "Déposer les dossiers avant deadline d'abrogation"},
    ]
    if ctx_surface >= 1000 and "BAT" in (ctx_sectors or []):
        protections.insert(0, {"urgence": "haute",
                               "action": "Décret Tertiaire > 1000 m² : intégrer CEE dans plan -40% 2030"})

    score_pess = min(100, 20 + len(risques) * 15)

    # ═══ LENTILLE 3 — OPPORTUNISTE ═══
    fenetres = []
    if cdp_mois > 0 and cdp_mois <= 12:
        fenetres.append({"type": "coup_de_pouce_chauffage",
                         "desc": f"Coup de Pouce Chauffage encore actif {cdp_mois} mois",
                         "action": "Lancer BAR-TH/BAT-TH avant la fin"})
    if abrog_upcoming:
        fenetres.append({"type": "anti_abrogation",
                         "desc": f"{len(abrog_upcoming)} fiche(s) à abroger — dépôt prioritaire",
                         "action": f"Cibler {abrog_upcoming[0]['ref']} avant {abrog_upcoming[0]['date']}"})
    if p6_bonus:
        fenetres.append({"type": "bonus_p6",
                         "desc": f"Bonus P6 actifs sur {len(p6_bonus)} fiches",
                         "action": "Coupler plusieurs bonus sur un même projet"})
    if not fenetres:
        fenetres.append({"type": "marche_stable", "desc": "Marché stable, bon moment pour packager",
                         "action": "Consolider portefeuille multi-fiches"})

    # Couplages stratégiques par secteur
    couplages = []
    if "BAT" in (ctx_sectors or []):
        couplages.append({"combo": ["BAT-EN-102", "BAT-EN-103", "BAT-EN-101"],
                          "desc": "Enveloppe complète (murs + plancher + toiture)",
                          "gain": "Jusqu'à 40 % de prime supplémentaire vs fiches isolées"})
        couplages.append({"combo": ["BAT-TH-127", "BAT-EQ-127"],
                          "desc": "PAC + pilotage GTB",
                          "gain": "Double levier thermique + numérique"})
    if "BAR" in (ctx_sectors or []):
        couplages.append({"combo": ["BAR-TH-104", "BAR-EN-101"],
                          "desc": "PAC air/eau + isolation combles (rénovation globale)",
                          "gain": "Bonus rénovation ampleur (+20%)"})
    if "IND" in (ctx_sectors or []):
        couplages.append({"combo": ["IND-UT-117", "IND-UT-121"],
                          "desc": "Variateur moteur + compresseur air efficient",
                          "gain": "Process utilitaire complet"})

    score_opp = min(100, 30 + len(fenetres) * 15 + len(couplages) * 5)

    # ═══ LENTILLE 4 — PRÉDICTIF ═══
    predictions = []
    if abrog_upcoming:
        predictions.append({
            "sujet": "Vagues d'abrogations P6",
            "scenario": f"{len(abrog_upcoming)} abrogation(s) confirmée(s) dans les 12 mois à venir",
            "base": "Arrêtés publiés",
            "probabilite": 95,
            "cibles_probables": [a["ref"] for a in abrog_upcoming[:5]],
        })
    predictions.append({
        "sujet": "Évolution du prix cumac P6",
        "scenario": "Montée à 9.5-10 €/MWhc d'ici fin 2026 (obligation +27%)",
        "base": f"Décret P6 + tendance marché ({tendance})",
        "probabilite": 70,
    })
    predictions.append({
        "sujet": "Nouvelles fiches P6 tertiaire",
        "scenario": "Extension fiches PAC tertiaire + géothermie attendue Q2 2026",
        "base": "Feuille de route DGEC",
        "probabilite": 60,
    })
    if velocite == "acceleration":
        predictions.append({
            "sujet": "Tension contrôles COFRAC",
            "scenario": "Taux de contrôle passant de 30% à ~40% courant P6",
            "base": "Décret 2025-1048",
            "probabilite": 75,
        })

    # ═══ LENTILLE 5 — PROACTIF ═══
    actions_immediates = []
    if cdp_mois > 0 and cdp_mois <= 3:
        actions_immediates.append({"priorite": 1, "action": "Déposer les dossiers Coup de Pouce Chauffage",
                                   "delai": f"J-{cdp_mois*30}", "verifie": True})
    if abrog_upcoming and abrog_upcoming[0]["days_remaining"] <= 90:
        a = abrog_upcoming[0]
        actions_immediates.append({"priorite": 1, "action": f"Déposer {a['ref']} avant abrogation",
                                   "delai": f"J-{a['days_remaining']}", "verifie": True})
    if ctx_surface >= 1000 and "BAT" in (ctx_sectors or []):
        actions_immediates.append({"priorite": 2, "action": "Audit énergétique Décret Tertiaire (obligatoire)",
                                   "delai": "J-0 conseillé", "verifie": True})
    if not actions_immediates:
        actions_immediates.append({"priorite": 2, "action": "Cadrer le périmètre audit (identifier gisements)",
                                   "delai": "cette semaine", "verifie": False})

    # Calendrier proactif 90 jours
    calendrier = []
    for a in abrog_upcoming[:5]:
        d = a["days_remaining"]
        if d <= 90:
            urg = "critique"
        elif d <= 180:
            urg = "haute"
        elif d <= 270:
            urg = "strategique"
        else:
            urg = "standard"
        calendrier.append({"date": a["date"], "desc": f"Abrogation {a['ref']}",
                           "urgence": urg, "joursRestants": d})
    # Ajout deadline P6 / décret
    if now < datetime(2026, 12, 31):
        j = (datetime(2026, 12, 31) - now).days
        calendrier.append({"date": "2026-12-31", "desc": "Fin 1re année P6 — obligation annuelle à couvrir",
                           "urgence": "strategique", "joursRestants": j})
    calendrier.sort(key=lambda x: x["joursRestants"])

    score_pred = 70 + (10 if velocite == "acceleration" else 0)

    return jsonify({
        # En-tête UI
        "prixActuel": prix_actuel,
        "prixTendance": tendance,
        "cdpMoisRestants": cdp_mois,
        "velociteReglementaire": velocite,
        "versionBase": "V37-FUSED",
        "contexte": {
            "sectors": ctx_sectors,
            "zone": ctx_zone,
            "surface": ctx_surface,
            "ape": ctx_ape,
        },
        "meta": {
            "prixHistorique": prix_hist,
            "nb_fiches_actives": len(fiches_actives),
            "nb_fiches_contexte": len(relevant_fiches),
            "nb_abrogations_a_venir": len(abrog_upcoming),
            "timestamp": now.isoformat(),
        },
        "lentilles": {
            "optimiste": {
                "score": score_opt,
                "signaux": signaux,
                "actions": actions_opt,
            },
            "pessimiste": {
                "score": score_pess,
                "risques": risques,
                "protections": protections,
            },
            "opportuniste": {
                "score": score_opp,
                "fenetres": fenetres,
                "couplages": couplages,
            },
        },
        # Ces deux-là sont lus à la racine par le frontend
        "predictif": {
            "score": score_pred,
            "horizon": "12 mois",
            "predictions": predictions,
        },
        "proactif": {
            "actions_immediates": actions_immediates,
            "calendrier": calendrier,
        },
    })


# ═══════════════════════════════════════════════════════════════════════════
# NÉGOCIATION / ACHETEURS / VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/negociation", methods=["POST"])
def negociation():
    """Compare les acheteurs CEE et recommande le meilleur canal de cession."""
    data = request.json or {}

    volume_kwhc = int(data.get("volume_kwhc", 0))
    secteurs = data.get("secteurs", ["BAT"])
    nb_sites = int(data.get("nb_sites", 1))
    qualite = data.get("qualite_dossier", "standard")
    precarite = data.get("precarite", False)
    cout_ttc = float(data.get("cout_travaux_ttc", 0))

    # Si pas de volume, calculer depuis les params
    if volume_kwhc <= 0:
        dep = str(data.get("departement", "75"))
        zone = get_zone(dep)
        surface = float(data.get("surface", 500))
        if zone:
            params = {
                "departement": dep, "zone": zone, "surface": surface,
                "quantite": int(data.get("quantite", 20)),
                "puissance": float(data.get("puissance", 50)),
                "energie": data.get("energie"),
                "nb_logements": 0, "puissance_froid": 0, "longueur": 0,
            }
            resultats = analyser(params)
            globaux = analyser_global(resultats)
            volume_kwhc = globaux.get("total_cumac", 0)
            if cout_ttc <= 0:
                cout_ttc = globaux.get("total_cost_ttc", 0)

    result = comparer_acheteurs(
        volume_kwhc, secteurs, nb_sites, qualite, precarite, cout_ttc
    )
    result["volume_kwhc"] = volume_kwhc
    result["cout_travaux_ttc"] = cout_ttc

    # Multi-site : multiplier
    if nb_sites > 1:
        result["volume_parc_kwhc"] = volume_kwhc * nb_sites
        result["cout_parc_ttc"] = cout_ttc * nb_sites
        result_parc = comparer_acheteurs(
            volume_kwhc * nb_sites, secteurs, nb_sites, qualite, precarite, cout_ttc * nb_sites
        )
        result["parc"] = result_parc

    return jsonify(result)


@app.route("/acheteurs", methods=["GET"])
def acheteurs():
    """Liste les acheteurs CEE disponibles avec leurs conditions."""
    return jsonify({k: {
        "nom": v["nom"], "type": v["type"],
        "prix_classic": v["prix_classic_mwhc"],
        "prix_precarite": v["prix_precarite_mwhc"],
        "tolerance": v["tolerance"],
        "multisite": v["multisite"],
        "exige_cofrac": v["exige_cofrac"],
        "notes": v["notes"],
    } for k, v in ACHETEURS.items()})


@app.route("/negociation/comparatif", methods=["GET"])
def negociation_comparatif():
    """Comparatif acheteurs CEE (GET avec query params)."""
    kwhc = int(request.args.get("kwhc", 0))
    secteurs = request.args.get("secteurs", "BAT").split(",")
    nb_sites = int(request.args.get("nb_sites", 1))
    qualite = request.args.get("qualite", "standard")
    precarite = request.args.get("precarite", "false").lower() == "true"

    result = comparer_acheteurs(kwhc, secteurs, nb_sites, qualite, precarite, 0)
    return jsonify(result)


@app.route("/validation/complete", methods=["POST"])
def validation_complete():
    """Validation juridique complète d'un projet CEE."""
    from cee_excellence_pro import valider_projet_complet
    data = request.json or {}
    result = valider_projet_complet(
        siret=data.get("siret", ""),
        adresse=data.get("adresse", ""),
        surface=float(data.get("surface", 0)),
        fiches_selectionnees=data.get("fiches", []),
        dpe_date=data.get("dpe_date"),
        energie=data.get("energie"),
    )
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════
# SIRET / ENRICHISSEMENT EXTERNE
# ═══════════════════════════════════════════════════════════════════════════

_SIRET_RX = re.compile(r"^\d{14}$")
_SIREN_RX = re.compile(r"^\d{9}$")


def _normalize_establishment(src: dict) -> dict:
    """Renvoie une vue normalisée d'un établissement renvoyé par recherche-entreprises."""
    if not src:
        return {}
    # Le format diffère légèrement entre `siege` et `matching_etablissements[i]`.
    return {
        "siret": src.get("siret", ""),
        "activite_principale": src.get("activite_principale", ""),
        "activite_principale_naf25": src.get("activite_principale_naf25", ""),
        "adresse": src.get("adresse") or src.get("geo_adresse") or "",
        "geo_adresse": src.get("geo_adresse") or src.get("adresse") or "",
        "code_postal": src.get("code_postal", ""),
        "commune": src.get("commune", ""),
        "libelle_commune": src.get("libelle_commune") or src.get("commune", ""),
        "departement": src.get("departement") or str(src.get("code_postal", ""))[:2],
        "numero_voie": src.get("numero_voie", ""),
        "type_voie": src.get("type_voie", ""),
        "libelle_voie": src.get("libelle_voie", ""),
        "complement_adresse": src.get("complement_adresse", ""),
        "latitude": src.get("latitude"),
        "longitude": src.get("longitude"),
        "tranche_effectif_salarie": src.get("tranche_effectif_salarie", ""),
        "est_siege": bool(src.get("est_siege", False)),
        "etat_administratif": src.get("etat_administratif", ""),
        "date_creation": src.get("date_creation", ""),
    }


def _opendatasoft_to_gouv_format(siret: str) -> dict | None:
    """Fallback: cherche un SIRET sur OpenDataSoft (miroir Sirene INSEE gratuit).

    Retourne un dict au format recherche-entreprises.api.gouv.fr (même shape)
    pour que le frontend puisse parser la réponse sans modification.
    Fonctionne même pour les établissements FERMÉS.
    """
    url = (
        "https://public.opendatasoft.com/api/records/1.0/search/?"
        + _qs({
            "dataset": "economicref-france-sirene-v3@public",
            "q": f"siret:{siret}",
            "rows": 1,
        })
    )
    data, err = _fetch_json(url, timeout=10, retries=2)
    if err is not None or not data or not data.get("records"):
        return None

    f = data["records"][0].get("fields", {})
    if not f.get("siret"):
        return None

    cp = f.get("codepostaletablissement", "") or ""
    dep = cp[:2] if len(cp) >= 2 else ""
    numero = str(f.get("numerovoieetablissement", "") or "")
    type_voie = str(f.get("typevoieetablissement", "") or "")
    libelle_voie = str(f.get("libellevoieetablissement", "") or "")
    commune = str(f.get("libellecommuneetablissement", "") or "")
    adresse_parts = [numero, type_voie, libelle_voie, cp, commune]
    adresse = " ".join(str(p) for p in adresse_parts if p).strip()
    ape = f.get("activiteprincipaleetablissement", "") or ""
    # Format APE: "6202A" → "62.02A"
    if len(ape) >= 4 and "." not in ape:
        ape = ape[:2] + "." + ape[2:]

    siren = f.get("siren", siret[:9])
    nom = (
        f.get("denominationunitelegale")
        or f.get("denominationusuelle1unitelegale")
        or f.get("nomusageunitelegale")
        or f.get("nomunitelegale", "")
        or ""
    )
    prenom = f.get("prenomsetablissement") or f.get("prenom1unitelegale") or ""
    nom_patronyme = f.get("nomunitelegale", "") or ""
    if not nom and prenom and nom_patronyme:
        nom = f"{prenom} {nom_patronyme}"

    etat_raw = (f.get("etatadministratifetablissement", "") or "").lower()
    etat_admin = "A" if "actif" in etat_raw or etat_raw == "a" else "F"

    # Fabriquer une réponse au format recherche-entreprises.api.gouv.fr
    siege = {
        "siret": siret,
        "activite_principale": ape,
        "adresse": adresse,
        "code_postal": cp,
        "departement": dep,
        "commune": commune,
        "libelle_commune": commune,
        "numero_voie": numero,
        "type_voie": type_voie,
        "libelle_voie": libelle_voie,
        "latitude": f.get("coordonneeetablissement_lat"),
        "longitude": f.get("coordonneeetablissement_lon"),
        "tranche_effectif_salarie": f.get("trancheeffectifsetablissement", ""),
        "etat_administratif": etat_admin,
        "date_creation": f.get("datecreationetablissement", ""),
        "est_siege": str(f.get("etablissementsiege", "")).lower() in ("true", "1", "oui"),
    }

    nature_juridique = f.get("categoriejuridiqueunitelegale", "")
    section_naf = ape[:2] if ape else ""
    # Mapping section NAF simplifié
    sections_map = {
        "01": "A", "02": "A", "03": "A",
        "05": "B", "06": "B", "07": "B", "08": "B", "09": "B",
        "10": "C", "11": "C", "12": "C", "13": "C", "14": "C", "15": "C",
        "16": "C", "17": "C", "18": "C", "19": "C", "20": "C", "21": "C",
        "22": "C", "23": "C", "24": "C", "25": "C", "26": "C", "27": "C",
        "28": "C", "29": "C", "30": "C", "31": "C", "32": "C", "33": "C",
        "35": "D", "36": "E", "37": "E", "38": "E", "39": "E",
        "41": "F", "42": "F", "43": "F",
        "45": "G", "46": "G", "47": "G",
        "49": "H", "50": "H", "51": "H", "52": "H", "53": "H",
        "55": "I", "56": "I",
        "58": "J", "59": "J", "60": "J", "61": "J", "62": "J", "63": "J",
        "64": "K", "65": "K", "66": "K",
        "68": "L",
        "69": "M", "70": "M", "71": "M", "72": "M", "73": "M", "74": "M", "75": "M",
        "77": "N", "78": "N", "79": "N", "80": "N", "81": "N", "82": "N",
        "84": "O", "85": "P",
        "86": "Q", "87": "Q", "88": "Q",
        "90": "R", "91": "R", "92": "R", "93": "R",
        "94": "S", "95": "S", "96": "S",
    }

    return {
        "page": 1,
        "per_page": 1,
        "total_results": 1,
        "total_pages": 1,
        "results": [{
            "siren": siren,
            "nom_complet": nom,
            "nom_raison_sociale": nom,
            "nombre_etablissements": 1,
            "nombre_etablissements_ouverts": 1 if etat_admin == "A" else 0,
            "siege": siege,
            "activite_principale": ape,
            "etat_administratif": etat_admin,
            "nature_juridique": str(nature_juridique),
            "section_activite_principale": sections_map.get(section_naf, ""),
            "tranche_effectif_salarie": f.get("trancheeffectifsunitelegale", ""),
            "date_creation": f.get("datecreationunitelegale", ""),
            "dirigeants": [],
            "complements": {
                "convention_collective_renseignee": False,
                "est_bio": False,
            },
            "_source": "opendatasoft_sirene",
        }],
    }


def _patch_siege_for_branch(data: dict, siret: str) -> None:
    """Patch siege avec matching_etablissements[0] si le SIRET est une branche."""
    if not data or not data.get("results"):
        return
    for ent in data["results"]:
        matching = ent.get("matching_etablissements") or []
        siege = ent.get("siege") or {}
        match = next(
            (m for m in matching if m.get("siret") == siret),
            None,
        )
        if match and siege.get("siret") != siret:
            merged = dict(siege)
            merged.update({k: v for k, v in match.items() if v not in (None, "")})
            merged["est_siege"] = False
            merged["siret"] = siret
            ent["siege"] = merged
            ent["_siret_matched"] = siret
            ent["_siret_branch_patch"] = True
            logger.info("SIRET %s = branche — siege patché (siège social = %s)",
                        siret, siege.get("siret"))


@app.route("/siret/search", methods=["GET"])
@app.route("/siret", methods=["GET"])  # V36: alias pour compatibilité cache navigateur
def siret_search():
    """Proxy SIRET avec cache + triple fallback + fix branches.

    Chaîne de résolution (s'arrête au premier succès) :
      1. recherche-entreprises.api.gouv.fr (SIRET exact)
      2. recherche-entreprises.api.gouv.fr (SIREN = 9 premiers chiffres)
      3. OpenDataSoft miroir Sirene INSEE (inclut les fermés/non-diffusibles)

    FIX V37 : patch siege pour branches + SIRET avec espaces.
    """
    q_raw = request.args.get("q", "")
    q = q_raw.strip()
    q_compact = q.replace(" ", "")
    per_page = request.args.get("per_page", "1")

    if not q:
        return jsonify({"error": "q requis"}), 400

    looks_like_siret = bool(_SIRET_RX.match(q_compact))
    looks_like_siren = bool(_SIREN_RX.match(q_compact))
    q_api = q_compact if (looks_like_siret or looks_like_siren) else q

    cache_key = f"{q_api}_{per_page}"
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.info("SIRET cache hit for %s", q_api)
        return jsonify(cached)
    logger.info("SIRET cache miss for %s", q_api)

    # ── Source 1 : recherche-entreprises (SIRET/SIREN/nom exact) ──
    url = "https://recherche-entreprises.api.gouv.fr/search?" + _qs({
        "q": q_api,
        "page": 1,
        "per_page": per_page,
    })
    data, err = _fetch_json(url, timeout=10, retries=3)

    has_results = (data and data.get("results") and len(data["results"]) > 0)

    # ── Source 2 : retry par SIREN si SIRET retourne rien ──
    if not has_results and looks_like_siret:
        siren_part = q_compact[:9]
        logger.info("SIRET %s: 0 résultats, retry avec SIREN %s", q_compact, siren_part)
        url2 = "https://recherche-entreprises.api.gouv.fr/search?" + _qs({
            "q": siren_part,
            "page": 1,
            "per_page": per_page,
        })
        data2, err2 = _fetch_json(url2, timeout=10, retries=2)
        if data2 and data2.get("results") and len(data2["results"]) > 0:
            data = data2
            has_results = True
            # On a trouvé l'entreprise par SIREN, patcher le siege avec le bon SIRET
            _patch_siege_for_branch(data, q_compact)
            logger.info("SIRET %s trouvé via SIREN %s", q_compact, siren_part)

    # ── Source 3 : OpenDataSoft miroir Sirene (fermés, non-diffusibles) ──
    if not has_results and looks_like_siret:
        logger.info("SIRET %s: introuvable via API gouv, tentative OpenDataSoft Sirene", q_compact)
        ods_data = _opendatasoft_to_gouv_format(q_compact)
        if ods_data:
            data = ods_data
            has_results = True
            logger.info("SIRET %s trouvé via OpenDataSoft Sirene", q_compact)

    # Erreur complète si toujours rien
    if not has_results:
        if err is not None:
            code, msg = err
            if code == 429:
                return jsonify({"error": "API gouv: trop de requêtes, réessayez"}), 429
            return jsonify({"error": f"API gouv: {msg}"}), (code if 400 <= code < 600 else 502)
        # Retourner la réponse vide telle quelle (total_results: 0)
        if data:
            _cache_set(cache_key, data)
            return jsonify(data)
        return jsonify({"error": "SIRET introuvable sur toutes les sources"}), 404

    # Patch siege pour branches (source 1)
    if looks_like_siret and data.get("results"):
        _patch_siege_for_branch(data, q_compact)

    _cache_set(cache_key, data)
    return jsonify(data)


@app.route("/proxy", methods=["GET"])
def proxy():
    """Proxy générique pour les appels Open Data (CORS bypass)."""
    url = request.args.get("url", "")
    if not url:
        return jsonify({"error": "url requis"}), 400

    # Whitelist: seulement les APIs publiques françaises
    allowed = [
        "recherche-entreprises.api.gouv.fr",
        "entreprise.data.gouv.fr",
        "data.ademe.fr",
        "geo.api.gouv.fr",
        "api-adresse.data.gouv.fr",
        "koumoul.com",
        "opendatasoft.com",
        "apicarto.ign.fr",
        "data.geopf.fr",
    ]
    host = urllib.parse.urlparse(url).hostname or ""
    if not any(a in host for a in allowed):
        return jsonify({"error": "domaine non autorisé"}), 403

    data, err = _fetch_json(url, timeout=10, retries=2)
    if err is not None:
        code, msg = err
        return jsonify({"error": msg}), (code if 400 <= code < 600 else 502)
    return jsonify(data)


@app.route("/dpe", methods=["GET"])
def dpe_lookup():
    """Lookup DPE ADEME avec filtrage par adresse exacte.
    Cherche dans dpe-france (logements) + dpe-tertiaire + audit-opendata,
    filtre par rue, retourne le plus récent."""
    q = request.args.get("q", "")
    if not q:
        return jsonify({"error": "q requis (adresse)"}), 400

    # Extraire numéro et rue de la query pour filtrage
    parts = q.strip().split()
    cp = ""
    rue_words = []
    numero = ""
    for p in parts:
        if re.match(r"^\d{5}$", p):
            cp = p
        elif re.match(r"^\d+[A-Za-z]?$", p) and not numero:
            numero = p
        elif p.upper() not in ("RUE", "AVENUE", "BOULEVARD", "PLACE", "CHEMIN",
                                "IMPASSE", "ALLÉE", "ALLEE", "ROUTE", "COURS",
                                "B", "BIS", "TER"):
            rue_words.append(p.upper())

    # Datasets à chercher (logements + tertiaire + audits énergétiques)
    datasets = ["dpe-france", "dpe-tertiaire", "audit-opendata"]
    all_results: list[dict] = []

    for ds in datasets:
        url = (
            f"https://data.ademe.fr/data-fair/api/v1/datasets/{ds}/lines?"
            + _qs({"q": q, "size": 20})
        )
        data, err = _fetch_json(url, timeout=8, retries=1)
        if err is not None:
            logger.warning("DPE %s: %s", ds, err[1])
            continue
        for r in (data or {}).get("results", []):
            r["_source"] = ds
            all_results.append(r)

    if not all_results:
        return jsonify({"results": [], "message": "Aucun DPE trouvé"})

    # Filtrage par adresse : scorer chaque résultat
    def score_match(r: dict) -> int:
        s = 0
        adr = (
            r.get("adresse_bien") or r.get("adresse_brut")
            or f"{r.get('numero_rue','')} {r.get('nom_rue','')}"
        ).upper()
        if numero and numero in adr.split():
            s += 50
        for w in rue_words:
            if w in adr:
                s += 20
        dpe_cp = str(r.get("code_postal_bien") or r.get("code_postal") or "")
        if cp and dpe_cp == cp:
            s += 30
        date = r.get("date_etablissement_dpe") or r.get("date_visite_diagnostiqueur") or ""
        if date:
            try:
                s += int(date[:4]) - 2000
            except (ValueError, TypeError, KeyError):
                pass
        return s

    # V36: Validation GPS — si coordonnées du site disponibles, scorer la distance
    site_lat_raw = request.args.get("lat")
    site_lon_raw = request.args.get("lon")
    site_lat = site_lon = None
    if site_lat_raw and site_lon_raw:
        try:
            site_lat = float(site_lat_raw)
            site_lon = float(site_lon_raw)
        except (ValueError, TypeError):
            site_lat, site_lon = None, None

    def _gps_distance(r: dict):
        """Distance en mètres entre le DPE et le site (Haversine)."""
        if site_lat is None or site_lon is None:
            return None
        dpe_lat = r.get("latitude") or r.get("geo_lat")
        dpe_lon = r.get("longitude") or r.get("geo_lng")
        if not dpe_lat and r.get("_geopoint"):
            try:
                gp = str(r["_geopoint"]).split(",")
                dpe_lat, dpe_lon = float(gp[0]), float(gp[1])
            except (ValueError, IndexError):
                return None
        if not dpe_lat or not dpe_lon:
            return None
        try:
            dpe_lat_f, dpe_lon_f = float(dpe_lat), float(dpe_lon)
        except (ValueError, TypeError):
            return None
        dlat = math.radians(dpe_lat_f - site_lat)
        dlon = math.radians(dpe_lon_f - site_lon)
        a = (math.sin(dlat/2)**2
             + math.cos(math.radians(site_lat))
             * math.cos(math.radians(dpe_lat_f))
             * math.sin(dlon/2)**2)
        return 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    # V36: Enrichir chaque résultat avec distance et score de confiance
    for r in all_results:
        dist = _gps_distance(r)
        r["_distance_m"] = round(dist, 1) if dist is not None else None
        addr_score = score_match(r)
        gps_bonus = 0
        if dist is not None:
            if dist < 30:
                gps_bonus = 40
            elif dist < 100:
                gps_bonus = 10
            elif dist > 200:
                gps_bonus = -30
        r["_match_score"] = addr_score + gps_bonus
        total = r["_match_score"]
        if total >= 80 and (dist is None or dist < 50):
            r["_confidence"] = "high"
        elif total >= 50:
            r["_confidence"] = "medium"
        else:
            r["_confidence"] = "low"

    all_results.sort(key=lambda r: r.get("_match_score", 0), reverse=True)

    best = all_results[:5]
    top_score = best[0].get("_match_score", 0) if best else 0

    # V36: Ne garder que les résultats avec confiance >= medium
    filtered = (
        [r for r in best
         if r.get("_match_score", 0) >= top_score * 0.6
         and r.get("_confidence") != "low"]
        if top_score > 30 else []
    )
    if not filtered and best:
        filtered = best[:1]
        filtered[0]["_confidence"] = "low"

    # Normaliser les champs pour compatibilité Oracle
    for r in filtered:
        # V36: Audits énergétiques ADEME (audit-opendata) → format unifié
        if r.get("_source") == "audit-opendata":
            r["_type"] = "audit"
            if not r.get("etiquette_dpe") and r.get("classe_bilan_dpe_initial"):
                r["etiquette_dpe"] = r["classe_bilan_dpe_initial"]
            if not r.get("etiquette_ges") and r.get("classe_emission_ges_initial"):
                r["etiquette_ges"] = r["classe_emission_ges_initial"]
            if not r.get("surface_habitable_logement"):
                r["surface_habitable_logement"] = (
                    r.get("surface_habitable_logement")
                    or r.get("surface_habitable") or 0
                )
            if not r.get("date_etablissement_dpe"):
                r["date_etablissement_dpe"] = r.get("date_etablissement_audit")
            if not r.get("numero_dpe"):
                r["numero_dpe"] = r.get("numero_audit")
            if not r.get("code_postal_bien"):
                r["code_postal_bien"] = r.get("code_postal_ban")
            if not r.get("adresse_bien"):
                r["adresse_bien"] = r.get("adresse_ban") or ""
            # Données enrichies spécifiques aux audits
            r["_audit_scenarios"] = []
            if r.get("classe_bilan_dpe_apres_travaux_scenario_1"):
                r["_audit_scenarios"].append({
                    "type": "par_geste",
                    "classe_avant": r.get("classe_bilan_dpe_initial"),
                    "classe_apres": r.get("classe_bilan_dpe_apres_travaux_scenario_1"),
                    "cout_total": r.get("cout_total_ttc_scenario_1"),
                    "conso_apres": r.get("conso_5_usages_ep_m2_apres_travaux_scenario_1"),
                })
            if r.get("classe_bilan_dpe_apres_travaux_scenario_2"):
                r["_audit_scenarios"].append({
                    "type": "global",
                    "classe_avant": r.get("classe_bilan_dpe_initial"),
                    "classe_apres": r.get("classe_bilan_dpe_apres_travaux_scenario_2"),
                    "cout_total": r.get("cout_total_ttc_scenario_2"),
                    "conso_apres": r.get("conso_5_usages_ep_m2_apres_travaux_scenario_2"),
                })
            r["_has_audit"] = True
        else:
            r["_type"] = "dpe"
            r["_has_audit"] = False

        if r.get("_source") == "dpe-tertiaire":
            if not r.get("etiquette_dpe") and r.get("classe_consommation_energie"):
                r["etiquette_dpe"] = r["classe_consommation_energie"]
            if not r.get("etiquette_ges") and r.get("classe_estimation_ges"):
                r["etiquette_ges"] = r["classe_estimation_ges"]
            if not r.get("surface_habitable_logement"):
                r["surface_habitable_logement"] = (
                    r.get("surface_habitable") or r.get("surface_thermique_lot")
                )
            if not r.get("type_batiment_dpe"):
                r["type_batiment_dpe"] = r.get("tr002_type_batiment_libelle", "tertiaire")
            if not r.get("date_etablissement_dpe"):
                r["date_etablissement_dpe"] = (
                    r.get("date_reception_dpe") or r.get("date_visite_diagnostiqueur")
                )
            if not r.get("code_postal_bien"):
                r["code_postal_bien"] = r.get("code_postal")
            if not r.get("nombre_niveau_immeuble") and r.get("nombre_etage"):
                r["nombre_niveau_immeuble"] = r["nombre_etage"]
            if not r.get("annee_construction_dpe") and r.get("annee_construction"):
                r["annee_construction_dpe"] = str(r["annee_construction"])
            if not r.get("adresse_bien"):
                r["adresse_bien"] = (
                    r.get("geo_adresse")
                    or f"{r.get('numero_rue','')} {r.get('nom_rue','')} "
                       f"{r.get('code_postal','')} {r.get('commune','')}"
                )

    return jsonify({
        "results": filtered,
        "total": len(all_results),
        "query": q,
        "match_score": top_score,
        "best_confidence": filtered[0].get("_confidence", "low") if filtered else "none",
        "best_distance_m": filtered[0].get("_distance_m") if filtered else None,
    })


@app.route("/cadastre", methods=["GET"])
def cadastre_lookup():
    """Retourne la parcelle cadastrale IGN pour un point (lat, lon).

    Source : apicarto.ign.fr (gratuit, sans token).
    Retourne : section, numéro, code INSEE commune, contenance (m²),
    référence cadastrale complète (ex: 75056AK0109).
    """
    lat = request.args.get("lat", "")
    lon = request.args.get("lon", "")
    if not lat or not lon:
        return jsonify({"error": "lat et lon requis"}), 400
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        return jsonify({"error": "lat/lon invalides"}), 400

    geom = _json.dumps({"type": "Point", "coordinates": [lon_f, lat_f]})
    url = "https://apicarto.ign.fr/api/cadastre/parcelle?" + _qs({"geom": geom})

    data, err = _fetch_json(url, timeout=10, retries=2)
    if err is not None:
        return jsonify({"error": err[1]}), 502

    features = (data or {}).get("features", [])
    if not features:
        return jsonify({"found": False, "message": "Aucune parcelle trouvée à ces coordonnées"})

    p = features[0].get("properties", {}) or {}
    geom_out = features[0].get("geometry", {})
    code_insee = p.get("code_insee") or ""
    section = p.get("section") or ""
    numero = p.get("numero") or ""
    # Référence cadastrale standard : {code_insee}{section padded 2}{numero padded 4}
    section_pad = section.rjust(2, "0") if section else ""
    numero_pad = numero.lstrip("0").rjust(4, "0") if numero else ""
    reference = f"{code_insee}{section_pad}{numero_pad}" if (code_insee and section and numero) else ""

    return jsonify({
        "found": True,
        "reference_cadastrale": reference,
        "section": section,
        "numero": numero,
        "code_insee": code_insee,
        "code_departement": p.get("code_dep", ""),
        "code_commune": p.get("code_com", ""),
        "code_arrondissement": p.get("code_arr", ""),
        "commune": p.get("nom_com", ""),
        "feuille": p.get("feuille", ""),
        "contenance_m2": p.get("contenance"),
        "idu": p.get("idu", ""),
        "geometry": geom_out,
    })


# ── BD TOPO : mappings matériaux (codes IGN officiels) ──
_BDTOPO_MATERIAUX_TOITURE = {
    "00": "Non renseigné", "0": "Non renseigné",
    "10": "Terre cuite (tuile)", "1": "Terre cuite (tuile)",
    "20": "Ardoise", "2": "Ardoise",
    "30": "Métal (zinc, acier)", "3": "Métal (zinc, acier)",
    "40": "Béton", "4": "Béton",
    "50": "Verre", "5": "Verre",
    "60": "Tuiles photovoltaïques",
    "70": "Chaume/végétal",
    "80": "Membrane bitumineuse/PVC",
    "90": "Autre",
}
_BDTOPO_MATERIAUX_MURS = {
    "00": "Non renseigné", "0": "Non renseigné",
    "10": "Maçonnerie traditionnelle (pierre/brique)", "1": "Maçonnerie traditionnelle (pierre/brique)",
    "20": "Pan de bois/colombage", "2": "Pan de bois/colombage",
    "30": "Béton/parpaing", "3": "Béton/parpaing",
    "40": "Bardage métal/bois", "4": "Bardage métal/bois",
    "50": "Verre/rideau", "5": "Verre/rideau",
    "90": "Autre",
}


def _polygon_area_m2(coords_lonlat: list) -> float:
    """Surface d'un anneau (lon,lat) en m² via projection équi-rectangulaire locale.

    Précise pour des emprises < 1 km (bâtiments). Utilise la formule du lacet
    (shoelace) sur les coordonnées projetées localement en mètres autour du
    centroïde moyen. Erreur < 0.1 % à l'échelle d'un bâtiment.
    """
    if not coords_lonlat or len(coords_lonlat) < 3:
        return 0.0
    # Latitude de référence = moyenne (pour facteur cos)
    lat0 = sum(pt[1] for pt in coords_lonlat) / len(coords_lonlat)
    cos_lat = math.cos(math.radians(lat0))
    # Conversion lat/lon → mètres (approximation sphérique locale)
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * cos_lat
    # Shoelace
    area = 0.0
    n = len(coords_lonlat)
    for i in range(n):
        x1 = coords_lonlat[i][0] * m_per_deg_lon
        y1 = coords_lonlat[i][1] * m_per_deg_lat
        x2 = coords_lonlat[(i + 1) % n][0] * m_per_deg_lon
        y2 = coords_lonlat[(i + 1) % n][1] * m_per_deg_lat
        area += (x1 * y2) - (x2 * y1)
    return abs(area) / 2.0


def _geom_surface_m2(geom: dict) -> float:
    """Surface en m² d'une géométrie GeoJSON (Polygon, MultiPolygon).

    Pour MultiPolygon : somme les polygones, soustrait les trous.
    """
    if not geom:
        return 0.0
    t = geom.get("type")
    coords = geom.get("coordinates") or []
    if t == "Polygon":
        if not coords:
            return 0.0
        outer = _polygon_area_m2(coords[0])
        holes = sum(_polygon_area_m2(ring) for ring in coords[1:])
        return outer - holes
    if t == "MultiPolygon":
        total = 0.0
        for poly in coords:
            if not poly:
                continue
            total += _polygon_area_m2(poly[0])
            total -= sum(_polygon_area_m2(r) for r in poly[1:])
        return total
    return 0.0


def _geom_centroid(geom: dict) -> tuple[float, float] | None:
    """Centroïde (lon, lat) approximatif (moyenne des points outer ring)."""
    if not geom:
        return None
    t = geom.get("type")
    coords = geom.get("coordinates") or []
    if t == "Polygon" and coords:
        ring = coords[0]
    elif t == "MultiPolygon" and coords and coords[0]:
        ring = coords[0][0]
    else:
        return None
    if not ring:
        return None
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    return (lon, lat)


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance Haversine en m."""
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon/2)**2)
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


@app.route("/batiment", methods=["GET"])
def batiment_lookup():
    """BD TOPO IGN enrichi : surface au sol, étages, hauteur, matériaux,
    date de construction (date_d_apparition), identifiant RNB, usage.

    Corrige le bug bbox V37 : WFS requiert le CRS dans la bbox sinon
    interprète les coordonnées en Lambert 93 (native) → zéro résultat.

    Params:
      lat, lon       (obligatoires) — point du site
      radius         (optionnel, défaut 0.001° ≈ 110m) — demi-côté de la bbox

    Retourne :
      {
        "features": [...],            # format GeoJSON BD TOPO brut (compat)
        "best": { ... },              # bâtiment le plus proche + enrichi
        "count": N
      }
    """
    lat = request.args.get("lat", "")
    lon = request.args.get("lon", "")
    if not lat or not lon:
        return jsonify({"error": "lat et lon requis"}), 400

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        return jsonify({"error": "lat/lon invalides"}), 400

    try:
        radius = float(request.args.get("radius", 0.001))
    except (ValueError, TypeError):
        radius = 0.001

    # FIX V37.1: bbox WFS DOIT inclure le CRS (,EPSG:4326) sinon BDTOPO
    # interprète les coords en Lambert 93 (CRS natif) → 0 feature.
    bbox = f"{lon_f-radius},{lat_f-radius},{lon_f+radius},{lat_f+radius},EPSG:4326"
    url = (
        "https://data.geopf.fr/wfs?service=WFS&version=2.0.0&request=GetFeature"
        "&typeName=BDTOPO_V3:batiment&outputFormat=application/json"
        f"&bbox={urllib.parse.quote(bbox, safe=',:')}&count=20"
    )

    data, err = _fetch_json(url, timeout=12, retries=2)
    if err is not None:
        return jsonify({"error": err[1]}), 502

    features = (data or {}).get("features") or []

    # Enrichir chaque feature : surface au sol + distance au point cible
    enriched = []
    for feat in features:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        surf_sol = round(_geom_surface_m2(geom), 1)
        centroid = _geom_centroid(geom)
        dist = None
        if centroid:
            dist = round(_distance_m(lat_f, lon_f, centroid[1], centroid[0]), 1)

        # Mappings lisibles
        mat_toit_code = str(props.get("materiaux_de_la_toiture") or "").strip()
        mat_mur_code = str(props.get("materiaux_des_murs") or "").strip()
        mat_toit = _BDTOPO_MATERIAUX_TOITURE.get(mat_toit_code, f"Code {mat_toit_code}" if mat_toit_code else "Non renseigné")
        mat_mur = _BDTOPO_MATERIAUX_MURS.get(mat_mur_code, f"Code {mat_mur_code}" if mat_mur_code else "Non renseigné")

        # Hauteur calculée depuis altitudes toit/sol (plus fiable que 'hauteur' seul)
        alt_sol = props.get("altitude_minimale_sol")
        alt_toit = props.get("altitude_minimale_toit") or props.get("altitude_maximale_toit")
        hauteur_alt = None
        if alt_sol is not None and alt_toit is not None:
            try:
                hauteur_alt = round(float(alt_toit) - float(alt_sol), 2)
            except (ValueError, TypeError):
                hauteur_alt = None

        # Date de construction (date_d_apparition = 1ère mention cadastrale)
        date_app = props.get("date_d_apparition") or ""
        annee_construction = None
        if date_app and len(str(date_app)) >= 4:
            try:
                annee_construction = int(str(date_app)[:4])
            except (ValueError, TypeError):
                annee_construction = None

        # SHON/SHAB estimée (surface au sol × nb étages, approximation)
        etages = props.get("nombre_d_etages")
        surface_plancher_estimee = None
        try:
            if surf_sol > 0 and etages and int(etages) > 0:
                surface_plancher_estimee = round(surf_sol * int(etages), 1)
        except (ValueError, TypeError):
            pass

        props["_surface_sol_m2"] = surf_sol
        props["_distance_m"] = dist
        props["_materiau_toiture"] = mat_toit
        props["_materiau_murs"] = mat_mur
        props["_hauteur_calculee_m"] = hauteur_alt
        props["_annee_construction"] = annee_construction
        props["_surface_plancher_estimee_m2"] = surface_plancher_estimee
        enriched.append(feat)

    # V37 FIX : sélectionner le bâtiment le plus PERTINENT, pas juste le plus proche.
    # Logique : parmi les bâtiments à < 50m, prendre le plus GRAND (surface au sol).
    # Un abri de 15 m² à 8m ne doit pas masquer un supermarché de 800 m² à 30m.
    # Si aucun bâtiment > 50 m² à < 50m, fallback sur le plus proche.
    close_buildings = [f for f in enriched
                       if (f.get("properties") or {}).get("_distance_m", 1e9) < 50]
    if close_buildings:
        # Parmi les proches, prendre le plus grand
        close_buildings.sort(
            key=lambda f: (f.get("properties") or {}).get("_surface_sol_m2", 0),
            reverse=True
        )
        enriched_sorted = close_buildings + [f for f in enriched if f not in close_buildings]
    else:
        # Aucun bâtiment proche → fallback distance
        enriched_sorted = sorted(enriched,
            key=lambda f: (f.get("properties") or {}).get("_distance_m") or 1e9)
    enriched = enriched_sorted

    best = None
    if enriched:
        b = enriched[0]
        p = b.get("properties") or {}
        best = {
            # Identifiants
            "cleabs": p.get("cleabs"),
            "rnb_id": p.get("identifiants_rnb"),
            # Dimensions
            "surface_sol_m2": p.get("_surface_sol_m2"),
            "surface_plancher_estimee_m2": p.get("_surface_plancher_estimee_m2"),
            "hauteur_m": p.get("hauteur"),
            "hauteur_calculee_m": p.get("_hauteur_calculee_m"),
            "nombre_etages": p.get("nombre_d_etages"),
            "nombre_logements": p.get("nombre_de_logements"),
            "altitude_sol_m": p.get("altitude_minimale_sol"),
            "altitude_toit_m": p.get("altitude_minimale_toit") or p.get("altitude_maximale_toit"),
            # Usages / nature
            "usage_1": p.get("usage_1"),
            "usage_2": p.get("usage_2"),
            "nature": p.get("nature"),
            "etat": p.get("etat_de_l_objet"),
            "leger": p.get("construction_legere"),
            # Matériaux (codes + libellés)
            "materiau_toiture": p.get("_materiau_toiture"),
            "materiau_toiture_code": str(p.get("materiaux_de_la_toiture") or ""),
            "materiau_murs": p.get("_materiau_murs"),
            "materiau_murs_code": str(p.get("materiaux_des_murs") or ""),
            # Dates
            "annee_construction": p.get("_annee_construction"),
            "date_apparition": p.get("date_d_apparition"),
            "date_modification": p.get("date_modification"),
            # Origine / précision
            "origine": p.get("origine_du_batiment"),
            "precision_planimetrique_m": p.get("precision_planimetrique"),
            "precision_altimetrique_m": p.get("precision_altimetrique"),
            # Position
            "distance_m": p.get("_distance_m"),
            "centroid": _geom_centroid(b.get("geometry") or {}),
            # Géométrie complète
            "geometry": b.get("geometry"),
        }

    return jsonify({
        "features": enriched,
        "best": best,
        "count": len(enriched),
        "query": {"lat": lat_f, "lon": lon_f, "radius_deg": radius},
        "crs": (data or {}).get("crs"),
    })


@app.route("/etablissements/<siren>", methods=["GET"])
def etablissements(siren):
    """Liste tous les établissements actifs d'un SIREN.

    V37 : utilise `limite_matching_etablissements=100` pour récupérer
    tous les établissements (limite par défaut = 10).
    """
    siren = siren.strip()[:9]
    if len(siren) < 9 or not siren.isdigit():
        return jsonify({"error": "SIREN invalide (9 chiffres)"}), 400

    cache_key = f"etab_{siren}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return jsonify(cached)

    url = "https://recherche-entreprises.api.gouv.fr/search?" + _qs({
        "q": siren,
        "page": 1,
        "per_page": 1,
        "limite_matching_etablissements": 100,
    })
    data, err = _fetch_json(url, timeout=15, retries=3)
    if err is not None:
        code, msg = err
        if code == 429:
            return jsonify({"error": "API surchargée"}), 429
        return jsonify({"error": f"API gouv: {msg}"}), (code if 400 <= code < 600 else 502)

    if not data or not data.get("results"):
        empty = {"siren": siren, "etablissements": [], "nb_total": 0}
        _cache_set(cache_key, empty)
        return jsonify(empty)

    ent = data["results"][0]
    siege = ent.get("siege", {}) or {}
    etabs_raw = ent.get("matching_etablissements", []) or []

    # V37 : ne retourner QUE les établissements ACTIFS (etat_administratif == "A")
    # Le siège n'est inclus que s'il est actif. Les fermés/radiés sont exclus.
    etabs = []
    siege_etat = siege.get("etat_administratif", "A")  # défaut A si absent (API gouv)
    if siege.get("siret") and siege_etat == "A":
        etabs.append({
            "siret": siege.get("siret"),
            "adresse": siege.get("adresse") or siege.get("geo_adresse", ""),
            "cp": siege.get("code_postal", ""),
            "commune": siege.get("libelle_commune") or siege.get("commune", ""),
            "departement": siege.get("departement", ""),
            "ape": siege.get("activite_principale", ""),
            "est_siege": True,
            "etat_administratif": siege_etat,
            "lat": siege.get("latitude"),
            "lon": siege.get("longitude"),
        })
    elif siege.get("siret"):
        logger.info("SIREN %s : siège %s inactif (état=%s) → exclu",
                    siren, siege.get("siret"), siege_etat)

    seen_sirets = {e["siret"] for e in etabs}
    for e in etabs_raw:
        # Filtrage strict : uniquement les établissements ACTIFS
        if e.get("etat_administratif") != "A":
            continue
        if e.get("siret") in seen_sirets:
            continue
        etabs.append({
            "siret": e.get("siret", ""),
            "adresse": e.get("adresse") or e.get("geo_adresse", ""),
            "cp": e.get("code_postal", ""),
            "commune": e.get("libelle_commune") or e.get("commune", ""),
            "departement": e.get("departement") or str(e.get("code_postal", ""))[:2],
            "ape": e.get("activite_principale", ""),
            "est_siege": False,
            "etat_administratif": "A",
            "lat": e.get("latitude"),
            "lon": e.get("longitude"),
        })
        seen_sirets.add(e.get("siret", ""))

    result = {
        "siren": siren,
        "nom": ent.get("nom_complet", ""),
        "nb_total": ent.get("nombre_etablissements", len(etabs)),
        "nb_ouverts_api": ent.get("nombre_etablissements_ouverts", len(etabs)),
        "nb_actifs": len(etabs),
        "etablissements": etabs,
        "_filtre": "etat_administratif=A uniquement (fermés/radiés exclus)",
    }
    _cache_set(cache_key, result)
    return jsonify(result)


# ═══════════════════════════════════════════════════════════════════════════
# AI PROXIES (GROQ / Gemini)
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/status", methods=["GET"])
def status_dashboard():
    """V37 P2.3 — Page HTML dashboard monitoring.

    Ping en live les 6 sources externes critiques + le moteur local.
    Utile pour Jimmy + monitoring externe (Pingdom, Uptimerobot).
    """
    import time as _time
    probes = [
        ("api.gouv.fr SIRET", "https://recherche-entreprises.api.gouv.fr/search?q=test&per_page=1"),
        ("IGN Cadastre",      'https://apicarto.ign.fr/api/cadastre/parcelle?geom={"type":"Point","coordinates":[2.33,48.87]}'),
        ("IGN BD TOPO",       "https://data.geopf.fr/wfs?service=WFS&request=GetCapabilities"),
        ("ADEME DPE",         "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-france/lines?size=1"),
        ("OpenDataSoft Sirene", "https://public.opendatasoft.com/api/records/1.0/search/?dataset=economicref-france-sirene-v3@public&rows=1"),
        ("BAN (adresse)",     "https://api-adresse.data.gouv.fr/search/?q=paris&limit=1"),
    ]
    # Backend locaux critiques
    local_ok = True
    try:
        fiches_n = len(load_fiches())
        _ = get_zone("75")
    except Exception:
        local_ok = False
        fiches_n = 0

    # V37 P4-fix : probes PARALLÈLES (sinon /status prend 12s+ en séquentiel)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    def _probe_one(name, url):
        t0 = _time.time()
        try:
            data, err = _fetch_json(url, timeout=4, retries=1)
            latency = int((_time.time() - t0) * 1000)
            if err is None:
                return {"name": name, "status": "UP" if latency < 1500 else "SLOW", "latency": latency, "detail": f"{latency} ms"}
            return {"name": name, "status": "DOWN", "latency": latency, "detail": str(err[1])[:60]}
        except Exception as e:
            return {"name": name, "status": "DOWN", "latency": int((_time.time() - t0) * 1000), "detail": str(e)[:60]}

    results = [None] * len(probes)
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_probe_one, n, u): (i, n) for i, (n, u) in enumerate(probes)}
        # Timeout global 10s, probes restantes marquées DOWN (timeout)
        try:
            for fut in as_completed(futures, timeout=10):
                i, _ = futures[fut]
                results[i] = fut.result()
        except Exception:
            pass
    # Fallback pour celles qui n'ont pas répondu à temps
    for idx, (i_name, name) in enumerate(zip(probes, [p[0] for p in probes])):
        if results[idx] is None:
            results[idx] = {"name": probes[idx][0], "status": "DOWN", "latency": 10000, "detail": "timeout"}

    # HTML dashboard simple
    overall_ok = local_ok and all(r["status"] in ("UP", "SLOW") for r in results)
    global_color = "#3fb950" if overall_ok else "#f85149"
    rows = ""
    for r in results:
        color = {"UP": "#3fb950", "SLOW": "#d29922", "DOWN": "#f85149"}.get(r["status"], "#888")
        rows += f"""
        <tr>
          <td style="padding:8px 12px;font-weight:600;">{r['name']}</td>
          <td style="padding:8px 12px;text-align:center;"><span style="padding:3px 10px;border-radius:4px;background:{color};color:#fff;font-size:11px;font-weight:700;">{r['status']}</span></td>
          <td style="padding:8px 12px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:12px;color:#aaa;">{r['latency']} ms</td>
          <td style="padding:8px 12px;font-size:11px;color:#888;">{r['detail']}</td>
        </tr>"""

    ai_env = {
        "GROQ": bool(os.environ.get("GROQ_API_KEY", "")),
        "GEMINI": bool(os.environ.get("GEMINI_API_KEY", "")),
        "CLAUDE": bool(os.environ.get("ANTHROPIC_API_KEY", "")),
        "KIMI": bool(os.environ.get("MOONSHOT_API_KEY", "")),
        "OPENAI": bool(os.environ.get("OPENAI_API_KEY", "")),
    }
    ai_rows = ""
    for k, v in ai_env.items():
        c = "#3fb950" if v else "#555"
        lbl = "configurée" if v else "absente"
        ai_rows += f'<span style="padding:4px 10px;background:{c};color:#fff;border-radius:4px;font-size:11px;margin-right:6px;">{k}: {lbl}</span>'

    html = f"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CEE Engine V37.3 — Status</title>
<meta http-equiv="refresh" content="30">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 30px; }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 24px; margin-top: 0; }}
  .badge {{ padding: 6px 16px; border-radius: 20px; background: {global_color}; color: #fff; font-weight: 700; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; margin: 16px 0; }}
  thead {{ background: #21262d; }}
  th {{ text-align: left; padding: 10px 12px; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #8b949e; }}
  tr {{ border-bottom: 1px solid #30363d; }}
  tr:last-child {{ border: none; }}
  .section {{ background: #161b22; padding: 16px 20px; border-radius: 8px; margin-bottom: 16px; }}
  .muted {{ color: #8b949e; font-size: 12px; }}
</style></head>
<body><div class="container">
<h1>CEE Engine V37.3 <span class="badge">{'✓ OPERATIONAL' if overall_ok else '⚠ DEGRADED'}</span></h1>
<p class="muted">Auto-refresh toutes les 30 s · Heure serveur : {_time.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>

<div class="section">
  <h3 style="margin:0 0 10px;font-size:14px;">🧠 Moteur local</h3>
  <span style="padding:4px 10px;background:{'#3fb950' if local_ok else '#f85149'};color:#fff;border-radius:4px;font-size:11px;">{'UP' if local_ok else 'DOWN'}</span>
  <span class="muted" style="margin-left:10px;">{fiches_n} fiches catalogue chargées · 34 endpoints exposés</span>
</div>

<div class="section">
  <h3 style="margin:0 0 10px;font-size:14px;">🛰️ Sources open data externes</h3>
  <table>
    <thead><tr><th>Source</th><th style="text-align:center;">Status</th><th style="text-align:right;">Latence</th><th>Détail</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>

<div class="section">
  <h3 style="margin:0 0 10px;font-size:14px;">🤖 Clés IA (env serveur — V37 SEC)</h3>
  {ai_rows}
  <p class="muted" style="margin-top:10px;">Aucune clé en dur dans le code. Source : variables d'environnement uniquement.</p>
</div>

<p class="muted">Sources API : SIRENE, IGN Cadastre, IGN BD TOPO V3, ADEME DPE, OpenDataSoft Sirene, BAN · Licences : lookup uniquement (non redistribué)</p>
</div></body></html>"""
    return html, 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}


@app.route("/ai/vision", methods=["POST"])
def ai_vision():
    """V37 P3.2 — Analyse d'image via Gemini Vision (photo équipement OU OCR facture).

    Body JSON :
      {
        "mode": "equipement" | "facture",
        "image_base64": "...",         // base64 pur (sans data:image/...)
        "mime_type": "image/jpeg",     // ou image/png
        "prompt_extra": "..."          // optionnel, pour contextualiser
      }
    Clé : query ?key= OU env GEMINI_API_KEY.

    Réponse structurée JSON selon le mode :
      equipement : { marque, modele, puissance_kw, cop, energie, fiche_cee_suggeree, confiance }
      facture    : { fournisseur, kwh_annuel, cout_eur_annuel, puissance_kva, periode, site, confiance }
    """
    gemini_key = request.args.get("key", "") or os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        return jsonify({"error": "GEMINI_API_KEY env ou ?key= requis"}), 400

    data = request.json or {}
    mode = data.get("mode", "equipement")
    image_b64 = data.get("image_base64", "")
    mime = data.get("mime_type", "image/jpeg")
    prompt_extra = data.get("prompt_extra", "")

    if not image_b64:
        return jsonify({"error": "image_base64 requis"}), 400
    # Limite taille image à 5 MB base64 (sinon refus)
    if len(image_b64) > 7_000_000:
        return jsonify({"error": "image trop grande (max ~5 MB)"}), 413

    if mode == "equipement":
        system = (
            "Tu es un expert en équipements énergétiques CEE. Analyse cette photo "
            "d'équipement (chaudière, PAC, climatisation, éclairage, moteur, compresseur...). "
            "Identifie la marque, le modèle, la puissance, l'énergie, et suggère la fiche CEE "
            "la plus pertinente parmi : BAR-TH-104 (PAC air/eau), BAR-TH-112 (poêle granulés), "
            "BAT-TH-127 (PAC tertiaire), BAT-EQ-127 (GTB), IND-UT-117 (variateur moteur), "
            "IND-UT-121 (compresseur air), BAT-EQ-135 (LED). "
            "Réponds UNIQUEMENT en JSON strict."
        )
        schema = (
            '{"marque":"...","modele":"...","puissance_kw":0,"cop":0,'
            '"energie":"gaz|fioul|electrique|hybride","fiche_cee_suggeree":"BAT-TH-127",'
            '"confiance":0-100,"commentaire":"..."}'
        )
    elif mode == "facture":
        system = (
            "Tu es un expert OCR factures énergétiques françaises (EDF, Engie, TotalEnergies, "
            "Enedis, GRDF...). Extrait les données clés : fournisseur, consommation annuelle "
            "en kWh, coût TTC annuel en €, puissance souscrite en kVA, période de facturation, "
            "adresse site. Réponds UNIQUEMENT en JSON strict."
        )
        schema = (
            '{"fournisseur":"...","kwh_annuel":0,"cout_eur_annuel":0,"puissance_kva":0,'
            '"periode":"AAAA-MM à AAAA-MM","site_adresse":"...","site_cp":"","confiance":0-100}'
        )
    else:
        return jsonify({"error": "mode doit être 'equipement' ou 'facture'"}), 400

    user_prompt = f"{system}\n\n{prompt_extra}\n\nFormat JSON strict attendu : {schema}"

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={urllib.parse.quote(gemini_key, safe='')}"
    )
    body = {
        "contents": [{
            "parts": [
                {"text": user_prompt},
                {"inline_data": {"mime_type": mime, "data": image_b64}}
            ]
        }],
        "generationConfig": {
            "temperature": 0.05,
            "maxOutputTokens": 1500,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        }
    }

    ctx = _ssl_ctx()
    try:
        req = urllib.request.Request(
            url,
            data=_json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            raw = _json.loads(resp.read().decode("utf-8"))

        if raw.get("error"):
            return jsonify({"error": str(raw["error"])[:200]}), 502
        text = raw["candidates"][0]["content"]["parts"][0]["text"]
        # Nettoyer control chars
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        try:
            parsed = _json.loads(text)
        except Exception:
            parsed = {"_raw_response": text, "_parse_error": True}
        return jsonify({
            "mode": mode,
            "result": parsed,
            "tokens": raw.get("usageMetadata", {}).get("totalTokenCount", 0),
        })
    except urllib.error.HTTPError as he:
        try:
            err_body = _json.loads(he.read().decode("utf-8"))
            msg = err_body.get("error", {}).get("message", f"HTTP {he.code}")
        except Exception:
            msg = f"HTTP {he.code}"
        return jsonify({"error": f"Gemini Vision: {msg}"}), he.code
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/ai/keys/status", methods=["GET"])
def ai_keys_status():
    """V37 SEC — Expose quelle IA a une clé configurée en env serveur.
    NE renvoie JAMAIS les valeurs, uniquement des booléens.
    """
    import os as _os
    return jsonify({
        "groq":    bool(_os.environ.get("GROQ_API_KEY", "")),
        "gemini":  bool(_os.environ.get("GEMINI_API_KEY", "")),
        "claude":  bool(_os.environ.get("ANTHROPIC_API_KEY", "")),
        "kimi":    bool(_os.environ.get("MOONSHOT_API_KEY", "")),
        "openai":  bool(_os.environ.get("OPENAI_API_KEY", "")),
    })


@app.route("/ai/groq", methods=["POST"])
def ai_groq():
    """Proxy GROQ — clé prioritaire : header X-Groq-Key, fallback env GROQ_API_KEY."""
    try:
        from groq import Groq
    except ImportError:
        return jsonify({"error": "pip install groq requis"}), 500

    import os as _os
    groq_key = request.headers.get("X-Groq-Key", "") or _os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        return jsonify({"error": "X-Groq-Key header ou GROQ_API_KEY env requis"}), 400

    data = request.json or {}
    model = data.get("model", "llama-3.3-70b-versatile")
    messages = data.get("messages", [])
    max_tokens = data.get("max_tokens", 2500)
    temperature = data.get("temperature", 0.1)

    try:
        client = Groq(api_key=groq_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        # Retourner au format OpenAI compatible (ce qu'Oracle attend)
        return jsonify({
            "choices": [{
                "message": {
                    "content": response.choices[0].message.content,
                    "role": "assistant",
                },
                "finish_reason": response.choices[0].finish_reason,
            }],
            "model": model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/ai/gemini", methods=["POST"])
def ai_gemini():
    """Proxy Gemini — clé via query param ?key= OU env GEMINI_API_KEY."""
    import os as _os
    data = request.get_data()
    gemini_key = request.args.get("key", "") or _os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        return jsonify({"error": "query ?key= ou GEMINI_API_KEY env requis"}), 400

    ctx = _ssl_ctx()
    try:
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={urllib.parse.quote(gemini_key, safe='')}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return app.response_class(resp.read(), content_type="application/json")
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/ai/claude", methods=["POST"])
def ai_claude():
    """V37 — Proxy Anthropic Claude API (3e IA de l'orchestrateur).

    Accepte la clé via header `X-Claude-Key` OU via env `ANTHROPIC_API_KEY`
    (sécurisation serveur possible sans exposer la clé côté navigateur).

    Format de requête (frontend) :
      { "model": "claude-opus-4-6|claude-sonnet-4-6|claude-haiku-4-5-20251001",
        "messages": [{"role": "user", "content": "..."}],
        "max_tokens": 2500,
        "system": "optional system prompt" }

    Réponse normalisée au format OpenAI-compatible :
      { "choices": [{"message": {"content": "...", "role": "assistant"}}],
        "model": "...", "usage": {...} }
    """
    import os as _os

    # Clé : priorité au header navigateur, fallback env serveur
    claude_key = request.headers.get("X-Claude-Key", "") or _os.environ.get("ANTHROPIC_API_KEY", "")
    if not claude_key:
        return jsonify({"error": "X-Claude-Key header ou ANTHROPIC_API_KEY env requis"}), 400

    data = request.json or {}
    model = data.get("model", "claude-sonnet-4-6")
    messages = data.get("messages", [])
    max_tokens = int(data.get("max_tokens", 2500))
    system_prompt = data.get("system", "")
    temperature = float(data.get("temperature", 0.1))

    if not messages:
        return jsonify({"error": "messages requis"}), 400

    # Anthropic API n'accepte pas role=system dans messages[] — on l'extrait
    clean_messages = []
    extracted_system = system_prompt
    for m in messages:
        if m.get("role") == "system":
            if not extracted_system:
                extracted_system = m.get("content", "")
            continue
        clean_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

    # Body Anthropic
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": clean_messages,
        "temperature": temperature,
    }
    if extracted_system:
        body["system"] = extracted_system

    ctx = _ssl_ctx()
    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=_json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": claude_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            raw = _json.loads(resp.read().decode("utf-8"))

        # Extraction du texte réponse (Anthropic renvoie content: [{type: "text", text: "..."}])
        text = ""
        for block in raw.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        stop_reason = raw.get("stop_reason", "end_turn")

        # Normaliser en format OpenAI-compatible (ce qu'Oracle consomme)
        return jsonify({
            "choices": [{
                "message": {"content": text, "role": "assistant"},
                "finish_reason": stop_reason,
            }],
            "model": raw.get("model", model),
            "usage": {
                "prompt_tokens": raw.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": raw.get("usage", {}).get("output_tokens", 0),
            },
            "_raw_provider": "anthropic",
        })
    except urllib.error.HTTPError as he:
        try:
            body_err = _json.loads(he.read().decode("utf-8"))
            msg = body_err.get("error", {}).get("message", f"HTTP {he.code}")
        except Exception:
            msg = f"HTTP {he.code}"
        return jsonify({"error": f"Claude API: {msg}"}), he.code
    except Exception as e:
        return jsonify({"error": str(e)}), 502


def _openai_compat_call(base_url: str, default_model: str, api_key: str, data: dict,
                        provider_name: str = "provider"):
    """Helper générique pour toute API OpenAI-compatible (OpenAI, Kimi, Together, etc.)."""
    model = data.get("model", default_model)
    messages = data.get("messages", [])
    max_tokens = int(data.get("max_tokens", 2500))
    temperature = float(data.get("temperature", 0.1))
    if not messages:
        return jsonify({"error": "messages requis"}), 400

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    # OpenAI accepte response_format pour JSON mode
    if data.get("response_format"):
        body["response_format"] = data["response_format"]

    ctx = _ssl_ctx()
    try:
        req = urllib.request.Request(
            base_url,
            data=_json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            raw = _json.loads(resp.read().decode("utf-8"))
        return jsonify(raw)  # format OpenAI direct
    except urllib.error.HTTPError as he:
        try:
            body_err = _json.loads(he.read().decode("utf-8"))
            msg = body_err.get("error", {}).get("message", f"HTTP {he.code}")
        except Exception:
            msg = f"HTTP {he.code}"
        return jsonify({"error": f"{provider_name}: {msg}"}), he.code
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/ai/kimi", methods=["POST"])
def ai_kimi():
    """V37 — Proxy Moonshot Kimi (rôle : vérification calculs, long contexte).

    API OpenAI-compatible. Clé : header `X-Kimi-Key` OU env `MOONSHOT_API_KEY`.
    Base URL globale : api.moonshot.ai — fallback Chine : api.moonshot.cn.
    Modèle par défaut : kimi-k2-0711-preview (contexte étendu, excellent en math).
    """
    import os as _os
    kimi_key = request.headers.get("X-Kimi-Key", "") or _os.environ.get("MOONSHOT_API_KEY", "")
    if not kimi_key:
        return jsonify({"error": "X-Kimi-Key header ou MOONSHOT_API_KEY env requis"}), 400

    data = request.json or {}
    # Moonshot AI global endpoint
    base = "https://api.moonshot.ai/v1/chat/completions"
    return _openai_compat_call(base, "kimi-k2-0711-preview", kimi_key, data, provider_name="Kimi")


@app.route("/ai/openai", methods=["POST"])
@app.route("/ai/gpt", methods=["POST"])
def ai_openai():
    """V37 — Proxy OpenAI ChatGPT (rôle : synthèse commerciale, rédaction pitch).

    Clé : header `X-OpenAI-Key` OU env `OPENAI_API_KEY`.
    Modèle par défaut : gpt-4o (fiable, coût maîtrisé, FR natif).
    """
    import os as _os
    openai_key = (
        request.headers.get("X-OpenAI-Key", "")
        or request.headers.get("X-Openai-Key", "")  # casse tolérante
        or _os.environ.get("OPENAI_API_KEY", "")
    )
    if not openai_key:
        return jsonify({"error": "X-OpenAI-Key header ou OPENAI_API_KEY env requis"}), 400

    data = request.json or {}
    base = "https://api.openai.com/v1/chat/completions"
    return _openai_compat_call(base, "gpt-4o", openai_key, data, provider_name="OpenAI")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("CEE Engine API V37 starting on port %d", config.API_PORT)
    # V37 : debug désactivé si LOG_FORMAT=json (reloader Flask casse le handler JSON)
    import os as _os_run
    _debug = _os_run.environ.get("LOG_FORMAT", "text").lower() != "json"
    app.run(debug=_debug, port=config.API_PORT, use_reloader=_debug)
