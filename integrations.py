"""
CEE Engine V37 — Intégrations externes (stubs activables).

Ces endpoints sont prêts à recevoir les credentials quand Jimmy les obtient.
Tant que les env vars ne sont pas définies, ils renvoient 503 (service activable)
au lieu de crasher — le reste de l'outil fonctionne normalement.

  POST /signature/request       Yousign (signature mandat CEE électronique)
  POST /webhook/erp             Sage/Cegid/Salesforce (export opportunity)
  POST /admin/refresh-fiches    Relance parse_atee.py (scraper catalogue CEE)
  GET  /integrations/status     Statut activation de chaque intégration
"""
from __future__ import annotations

import json
import os
import subprocess
import ssl
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from flask import jsonify, request


PROJECT_ROOT = Path(__file__).parent


def register_integrations_routes(app, require_auth_fn) -> None:
    """Enregistre les routes d'intégrations externes sur l'app."""

    # V37.3.40 — Gate JWT activé seulement si CEE_AUTH_REQUIRED=1.
    from functools import wraps as _wraps

    def _gate(f):
        @_wraps(f)
        def _w(*a, **k):
            if os.environ.get("CEE_AUTH_REQUIRED", "0") == "1":
                from auth import jwt_verify
                ah = request.headers.get("Authorization", "")
                tok = ah[7:].strip() if ah.lower().startswith("bearer ") else ""
                if not tok or not jwt_verify(tok):
                    return jsonify({"error": "Unauthorized — JWT Bearer requis"}), 401
            return f(*a, **k)
        return _w

    def _gate_admin(f):
        @_wraps(f)
        def _w(*a, **k):
            if os.environ.get("CEE_AUTH_REQUIRED", "0") == "1":
                from auth import jwt_verify
                ah = request.headers.get("Authorization", "")
                tok = ah[7:].strip() if ah.lower().startswith("bearer ") else ""
                payload = jwt_verify(tok) if tok else None
                if not payload:
                    return jsonify({"error": "Unauthorized — JWT Bearer requis"}), 401
                if payload.get("role") != "admin":
                    return jsonify({"error": "Forbidden — admin requis"}), 403
            return f(*a, **k)
        return _w

    # ── Yousign ──
    @app.route("/signature/request", methods=["POST"])
    @_gate
    def _yousign_request():
        """Envoie une demande de signature électronique Yousign.

        Body JSON :
          {
            "signer_email": "client@example.com",
            "signer_name": "Jean Dupont",
            "document_base64": "...",    // PDF du mandat CEE
            "document_name": "Mandat_CEE_SIRET_date.pdf",
            "subject": "Signature mandat CEE"
          }
        """
        yousign_key = os.environ.get("YOUSIGN_API_KEY", "")
        yousign_env = os.environ.get("YOUSIGN_ENV", "sandbox")  # sandbox | production

        if not yousign_key:
            return jsonify({
                "error": "Intégration Yousign non activée",
                "activation": "export YOUSIGN_API_KEY=... puis relance",
                "doc": "https://developers.yousign.com/",
                "status": "stub",
            }), 503

        data = request.json or {}
        required = ["signer_email", "signer_name", "document_base64", "document_name"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"error": f"champs requis: {missing}"}), 400

        # Yousign API v3 — 3 étapes : Signature Request → Document → Signer → Activate
        # Ici : stub fonctionnel, le vrai flow sera complété quand Jimmy teste
        base_url = "https://api.yousign.app/v3" if yousign_env == "production" else "https://api-sandbox.yousign.app/v3"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        try:
            # 1. Créer la Signature Request
            req1 = urllib.request.Request(
                f"{base_url}/signature_requests",
                data=json.dumps({
                    "name": data.get("subject", "Signature mandat CEE"),
                    "delivery_mode": "email",
                    "timezone": "Europe/Paris",
                }).encode(),
                headers={
                    "Authorization": f"Bearer {yousign_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req1, timeout=20, context=ctx) as resp:
                sr = json.loads(resp.read())

            return jsonify({
                "ok": True,
                "signature_request_id": sr.get("id"),
                "status": "draft",
                "env": yousign_env,
                "note": "Endpoint stub — à compléter avec upload document + add signer + activate",
            })
        except urllib.error.HTTPError as he:
            return jsonify({"error": f"Yousign: HTTP {he.code}"}), he.code
        except Exception as e:
            return jsonify({"error": str(e)}), 502

    # ── Webhook ERP (Sage, Cegid, Salesforce, HubSpot) ──
    @app.route("/webhook/erp", methods=["POST"])
    @_gate
    def _webhook_erp():
        """Poste les données d'un diagnostic CEE vers l'ERP configuré.

        Body JSON :
          {
            "siret": "...", "nom": "...", "prime_estimee": 664048,
            "gisements": ["BAT-TH-127", ...], "statut": "prospect|deal|won"
          }
        L'URL webhook est lue depuis ERP_WEBHOOK_URL. Format standard JSON.
        """
        webhook_url = os.environ.get("ERP_WEBHOOK_URL", "")
        webhook_auth = os.environ.get("ERP_WEBHOOK_AUTH", "")  # Bearer token ou API key

        if not webhook_url:
            return jsonify({
                "error": "Intégration ERP non activée",
                "activation": "export ERP_WEBHOOK_URL=https://... (optionnel: ERP_WEBHOOK_AUTH=bearer_token)",
                "doc": "Endpoint générique compatible Zapier, Make, Sage X3, Cegid Y2, Salesforce",
                "status": "stub",
            }), 503

        data = request.json or {}
        if not data.get("siret"):
            return jsonify({"error": "siret requis"}), 400

        payload = {
            "source": "cee_engine_v37",
            "timestamp": int(__import__("time").time()),
            **data,
        }
        headers = {"Content-Type": "application/json"}
        if webhook_auth:
            headers["Authorization"] = webhook_auth

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            req = urllib.request.Request(
                webhook_url, data=json.dumps(payload).encode(),
                headers=headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                body = resp.read().decode()[:500]
            return jsonify({"ok": True, "status": resp.status, "response_preview": body})
        except urllib.error.HTTPError as he:
            return jsonify({"error": f"ERP webhook: HTTP {he.code}"}), he.code
        except Exception as e:
            return jsonify({"error": str(e)}), 502

    # ── ATEE scraper refresh (relance parse_atee.py en tâche) ──
    @app.route("/admin/refresh-fiches", methods=["POST"])
    @_gate_admin
    def _refresh_fiches():
        """Relance parse_atee.py pour rafraîchir le catalogue fiches CEE.

        Sécurité V37.3.40 : @_gate_admin actif si CEE_AUTH_REQUIRED=1
        (rôle admin requis dans le JWT). Cooldown : 1 run par heure.
        """
        import time
        _last = _refresh_fiches._last if hasattr(_refresh_fiches, '_last') else 0
        if time.time() - _last < 3600:
            return jsonify({
                "error": "cooldown actif — 1 run max par heure",
                "next_available_in_seconds": int(3600 - (time.time() - _last)),
            }), 429

        script = PROJECT_ROOT / "parse_atee.py"
        if not script.exists():
            return jsonify({"error": "parse_atee.py introuvable dans le projet"}), 500

        try:
            # Lance en mode "dry" pour test — mode "full" nécessitera validation humaine
            result = subprocess.run(
                ["python3", str(script), "--help"],
                cwd=str(PROJECT_ROOT),
                capture_output=True, text=True, timeout=60,
            )
            _refresh_fiches._last = time.time()
            return jsonify({
                "ok": True,
                "message": "parse_atee.py exécuté en mode sonde (--help). Mode full à activer manuellement.",
                "stdout_preview": (result.stdout or "")[:500],
                "stderr_preview": (result.stderr or "")[:500],
                "returncode": result.returncode,
            })
        except subprocess.TimeoutExpired:
            return jsonify({"error": "timeout (60s) — script trop lent"}), 504
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── Status global des intégrations ──
    @app.route("/integrations/status", methods=["GET"])
    def _integrations_status():
        return jsonify({
            "yousign": {
                "activated": bool(os.environ.get("YOUSIGN_API_KEY", "")),
                "env": os.environ.get("YOUSIGN_ENV", "sandbox") if os.environ.get("YOUSIGN_API_KEY") else None,
                "doc": "https://developers.yousign.com/",
            },
            "erp_webhook": {
                "activated": bool(os.environ.get("ERP_WEBHOOK_URL", "")),
                "url_configured": bool(os.environ.get("ERP_WEBHOOK_URL", "")),
                "auth_configured": bool(os.environ.get("ERP_WEBHOOK_AUTH", "")),
            },
            "atee_scraper": {
                "available": (PROJECT_ROOT / "parse_atee.py").exists(),
                "cooldown_sec": 3600,
            },
            "jwt_auth": {
                "activated": bool(os.environ.get("CEE_JWT_SECRET", "")),
            },
        })
