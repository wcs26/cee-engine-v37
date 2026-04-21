"""
CEE Engine V37 P4.3 — Rate limiting in-memory (token bucket).

Protège contre :
  - DoS par spam d'appels /analyse, /expert
  - Abus de consommation cloud IA (GROQ/OpenAI/etc.)
  - Bots scrapant /siret/search pour rebuild d'un catalogue

Configuration via env :
  RATE_LIMIT_AI=30              max 30 req/min par IP sur endpoints /ai/*
  RATE_LIMIT_METIER=120         max 120 req/min sur /analyse, /expert, /cadastre, etc.
  RATE_LIMIT_DEFAULT=300        défaut autres routes
  RATE_LIMIT_WHITELIST=127.0.0.1,10.0.0.0/8   IPs exemptées (tests, monitoring)
"""
from __future__ import annotations

import ipaddress
import os
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request


_buckets: dict[tuple[str, str], deque] = defaultdict(deque)
_lock = threading.Lock()


def _get_limits() -> dict:
    return {
        "ai":      int(os.environ.get("RATE_LIMIT_AI", "30")),
        "metier":  int(os.environ.get("RATE_LIMIT_METIER", "120")),
        "default": int(os.environ.get("RATE_LIMIT_DEFAULT", "300")),
    }


def _is_whitelisted(ip: str) -> bool:
    """V37 fix : distingue RATE_LIMIT_WHITELIST absente (défaut 127.0.0.1) vs vide ("" = aucun whitelist).
    - Variable non définie → défaut "127.0.0.1,::1" (pratique pour tests locaux)
    - Variable = ""          → whitelist VIDE (rien n'est whitelisté, tout rate-limité)
    """
    raw = os.environ.get("RATE_LIMIT_WHITELIST")
    if raw is None:
        wl_str = "127.0.0.1,::1"
    elif raw.strip() == "":
        return False  # whitelist explicitement vide = 0 exemption
    else:
        wl_str = raw
    try:
        client = ipaddress.ip_address(ip)
        for entry in wl_str.split(","):
            entry = entry.strip()
            if not entry:
                continue
            try:
                if "/" in entry:
                    if client in ipaddress.ip_network(entry, strict=False):
                        return True
                else:
                    if client == ipaddress.ip_address(entry):
                        return True
            except ValueError:
                continue
    except ValueError:
        return False
    return False


def _classify(path: str) -> str:
    if path.startswith("/ai/"):
        return "ai"
    if any(path.startswith(p) for p in (
        "/analyse", "/expert", "/recalcul", "/cadastre", "/batiment",
        "/dpe", "/siret", "/etablissements", "/negociation", "/pncee", "/rag",
    )):
        return "metier"
    return "default"


def check_rate_limit(ip: str, category: str, limit_per_minute: int) -> tuple[bool, int]:
    """Sliding window 60s. Retourne (autorisé, remaining)."""
    now = time.time()
    key = (ip, category)
    with _lock:
        q = _buckets[key]
        # Purger les entrées > 60s
        while q and (now - q[0]) > 60:
            q.popleft()
        if len(q) >= limit_per_minute:
            return False, 0
        q.append(now)
        return True, limit_per_minute - len(q)


def register_rate_limiter(app) -> None:
    """Installe le middleware rate limit en before_request."""

    @app.before_request
    def _rate_limit_check():
        if request.method == "OPTIONS":
            return None
        # Whitelist par IP (tests pytest utilisent 127.0.0.1)
        remote = request.remote_addr or ""
        if _is_whitelisted(remote):
            return None
        # Static & assets exemptés
        path = request.path or ""
        if path.startswith("/static") or path.endswith((".js", ".css", ".png", ".svg", ".json", ".ico", ".webp")):
            return None

        category = _classify(path)
        limits = _get_limits()
        limit = limits.get(category, limits["default"])
        allowed, remaining = check_rate_limit(remote, category, limit)
        if not allowed:
            resp = jsonify({
                "error": f"Rate limit exceeded: {limit} req/min for {category} endpoints",
                "category": category,
                "limit_per_minute": limit,
                "retry_after_seconds": 60,
            })
            resp.status_code = 429
            resp.headers["Retry-After"] = "60"
            resp.headers["X-RateLimit-Category"] = category
            resp.headers["X-RateLimit-Limit"] = str(limit)
            resp.headers["X-RateLimit-Remaining"] = "0"
            return resp
        # Pas de blocage — ajouter headers informatifs en after_request
        request._rl_category = category
        request._rl_limit = limit
        request._rl_remaining = remaining
        return None

    @app.after_request
    def _rate_limit_headers(response):
        if hasattr(request, "_rl_limit"):
            response.headers["X-RateLimit-Limit"] = str(request._rl_limit)
            response.headers["X-RateLimit-Remaining"] = str(request._rl_remaining)
            response.headers["X-RateLimit-Category"] = request._rl_category
        return response
