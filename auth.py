"""
CEE Engine V37 — Auth basic + JWT (fondation multi-utilisateurs)

Stratégie : minimaliste pour démarrer. Users stockés localement dans users.json
(passwords hashés via hashlib + salt). Tokens JWT signés HS256 avec CEE_JWT_SECRET.

Prépare une migration Supabase/Auth0 future — l'interface middleware reste stable.

Usage :
    from auth import require_auth, login_user, create_user

    @app.route("/admin/secret", methods=["GET"])
    @require_auth(role="admin")
    def secret(current_user): ...

Endpoints exposés par register_auth_routes(app) :
    POST /auth/login    {email, password} → {token, user}
    POST /auth/register {email, password, name, role}  (admin only si existants)
    GET  /auth/me       → user courant (JWT Bearer)
    POST /auth/logout   → no-op côté serveur (client supprime le token)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from functools import wraps
from pathlib import Path
from typing import Callable

from flask import jsonify, request


USERS_FILE = Path(__file__).parent / "users.json"
JWT_SECRET = os.environ.get("CEE_JWT_SECRET", "")
JWT_ALG = "HS256"
JWT_TTL_SECONDS = 24 * 3600  # 24h
PBKDF_ITERATIONS = 120_000


# V37.1 sécu : refuser un secret faible au boot (vérité plutôt que faux semblant).
# Mode strict si CEE_ENV=prod ; sinon warning seulement.
def _validate_jwt_secret_strength(secret: str) -> tuple[bool, str]:
    if not secret:
        return False, "CEE_JWT_SECRET non défini"
    if len(secret) < 32:
        return False, f"CEE_JWT_SECRET trop court ({len(secret)} chars, min 32)"
    weak_markers = ("dev", "test", "change", "secret", "password", "default", "qwerty")
    low = secret.lower()
    if any(w in low for w in weak_markers):
        return False, f"CEE_JWT_SECRET contient un marqueur faible (dev/test/change/secret...). Régénère via: openssl rand -hex 32"
    return True, "OK"


_jwt_ok, _jwt_msg = _validate_jwt_secret_strength(JWT_SECRET)
if not _jwt_ok:
    if os.environ.get("CEE_ENV", "dev") == "prod":
        raise RuntimeError(f"[SÉCU] CEE_JWT_SECRET invalide en prod : {_jwt_msg}")
    else:
        import sys
        print(f"[SÉCU WARNING] {_jwt_msg} (toléré en dev, fatal si CEE_ENV=prod)", file=sys.stderr)


# ─────────────────────────────────────────────────────────────
# Password hashing (PBKDF2-SHA256 + salt)
# ─────────────────────────────────────────────────────────────

def hash_password(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# JWT (HS256) — implémentation minimale sans dépendance externe
# ─────────────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def jwt_sign(payload: dict) -> str:
    if not JWT_SECRET:
        raise RuntimeError("CEE_JWT_SECRET non configuré (env var requise)")
    header = {"alg": JWT_ALG, "typ": "JWT"}
    now = int(time.time())
    payload = {**payload, "iat": now, "exp": now + JWT_TTL_SECONDS}
    h = _b64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url(sig)}"


def jwt_verify(token: str) -> dict | None:
    if not JWT_SECRET or not token:
        return None
    try:
        h, p, s = token.split(".")
        expected = hmac.new(JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_decode(s), expected):
            return None
        payload = json.loads(_b64url_decode(p))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Users storage (users.json)
# ─────────────────────────────────────────────────────────────

def _load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    try:
        return json.loads(USERS_FILE.read_text())
    except Exception:
        return {}


def _save_users(users: dict) -> None:
    USERS_FILE.write_text(json.dumps(users, indent=2, ensure_ascii=False))


def create_user(email: str, password: str, name: str = "", role: str = "user",
                status: str = "active") -> dict:
    """V37.3.36 — Crée un user avec status :
    - 'active' : peut se logger (admin créé via bootstrap, ou validé par admin)
    - 'pending' : créé par self-service, en attente de validation admin
    - 'rejected' : refusé par l'admin
    """
    users = _load_users()
    if email in users:
        raise ValueError("user déjà existant")
    user = {
        "email": email,
        "name": name or email.split("@")[0],
        "role": role,  # 'admin' | 'user' | 'readonly'
        "status": status,
        "password_hash": hash_password(password),
        "created_at": int(time.time()),
    }
    users[email] = user
    _save_users(users)
    return {k: v for k, v in user.items() if k != "password_hash"}


def authenticate(email: str, password: str) -> dict | None:
    """V37.3.36 — Login refusé si status != active.
    Retourne user si OK, None sinon. Lève ValueError si compte non-validé pour
    permettre à l'UI d'afficher un message dédié."""
    users = _load_users()
    user = users.get(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    status = user.get("status", "active")  # users existants pré-V37.3.36 = active
    if status == "pending":
        raise PermissionError("Compte en attente de validation par l'admin")
    if status == "rejected":
        raise PermissionError("Compte refusé par l'admin")
    return {k: v for k, v in user.items() if k != "password_hash"}


def list_users_with_status(status_filter: str | None = None) -> list:
    """V37.3.36 — Liste users (sans password_hash). Filtre optionnel par status."""
    users = _load_users()
    out = []
    for email, u in users.items():
        if status_filter and u.get("status", "active") != status_filter:
            continue
        out.append({k: v for k, v in u.items() if k != "password_hash"})
    return sorted(out, key=lambda x: x.get("created_at", 0), reverse=True)


def _send_whatsapp_notification(message: str, new_user: dict, log) -> None:
    """V37.3.37 — Envoie notification WhatsApp via 3 modes au choix.

    Modes (sélectionnés automatiquement selon env vars présentes) :

    A) CallMeBot (gratuit, MVP, sans API officielle)
       env: CEE_WA_CALLMEBOT_PHONE (+855xxx), CEE_WA_CALLMEBOT_APIKEY
       Setup: WhatsApp +34 644 51 95 23 → message "I allow callmebot to send me messages"
              → reçois apikey gratuit

    B) Twilio WhatsApp Sandbox (test gratuit, prod ~$0.005/msg)
       env: CEE_WA_TWILIO_SID, CEE_WA_TWILIO_TOKEN,
            CEE_WA_TWILIO_FROM (whatsapp:+14155238886 sandbox par défaut),
            CEE_WA_TO (whatsapp:+855xxx)
       Setup: console.twilio.com → WhatsApp Sandbox

    C) Meta WhatsApp Cloud API (officielle, gratuit < 1000 conv/mois)
       env: CEE_WA_META_PHONE_ID, CEE_WA_META_TOKEN, CEE_WA_TO (+855xxx)
       Setup: developers.facebook.com → WhatsApp Business → numéro test gratuit
    """
    import urllib.request as _req
    import urllib.parse as _parse
    import json as _json
    import base64 as _b64

    # Tronquer le message pour WhatsApp (limite ~4096 chars, mais on aime court)
    short = message[:1500]

    # ── Mode A : CallMeBot ───────────────────────────────────
    cmb_phone = os.environ.get("CEE_WA_CALLMEBOT_PHONE", "").strip()
    cmb_key = os.environ.get("CEE_WA_CALLMEBOT_APIKEY", "").strip()
    if cmb_phone and cmb_key:
        try:
            url = (
                "https://api.callmebot.com/whatsapp.php?"
                + _parse.urlencode({"phone": cmb_phone, "text": short, "apikey": cmb_key})
            )
            req = _req.Request(url, headers={"User-Agent": "CEE-Engine/V37.3"})
            with _req.urlopen(req, timeout=8) as resp:
                resp.read()
            log.info("whatsapp callmebot sent to %s", cmb_phone)
            return
        except Exception as e:
            log.warning("whatsapp callmebot err: %s", e)

    # ── Mode B : Twilio ───────────────────────────────────────
    tw_sid = os.environ.get("CEE_WA_TWILIO_SID", "").strip()
    tw_tok = os.environ.get("CEE_WA_TWILIO_TOKEN", "").strip()
    tw_from = os.environ.get("CEE_WA_TWILIO_FROM", "whatsapp:+14155238886").strip()
    tw_to = os.environ.get("CEE_WA_TO", "").strip()
    if tw_sid and tw_tok and tw_to:
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{tw_sid}/Messages.json"
            data = _parse.urlencode({"From": tw_from, "To": tw_to, "Body": short}).encode()
            auth = _b64.b64encode(f"{tw_sid}:{tw_tok}".encode()).decode()
            req = _req.Request(url, data=data, headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            }, method="POST")
            with _req.urlopen(req, timeout=8) as resp:
                resp.read()
            log.info("whatsapp twilio sent to %s", tw_to)
            return
        except Exception as e:
            log.warning("whatsapp twilio err: %s", e)

    # ── Mode C : Meta Cloud API ──────────────────────────────
    meta_pid = os.environ.get("CEE_WA_META_PHONE_ID", "").strip()
    meta_tok = os.environ.get("CEE_WA_META_TOKEN", "").strip()
    meta_to = os.environ.get("CEE_WA_TO", "").strip().lstrip("+")
    if meta_pid and meta_tok and meta_to:
        try:
            url = f"https://graph.facebook.com/v18.0/{meta_pid}/messages"
            payload = {
                "messaging_product": "whatsapp",
                "to": meta_to,
                "type": "text",
                "text": {"body": short},
            }
            data = _json.dumps(payload).encode()
            req = _req.Request(url, data=data, headers={
                "Authorization": f"Bearer {meta_tok}",
                "Content-Type": "application/json",
            }, method="POST")
            with _req.urlopen(req, timeout=8) as resp:
                resp.read()
            log.info("whatsapp meta sent to %s", meta_to)
            return
        except Exception as e:
            log.warning("whatsapp meta err: %s", e)


def _notify_admin_pending(new_user: dict) -> None:
    """V37.3.36 — Notifie l'admin d'un nouveau compte en attente.

    Mécaniques actives selon les env vars configurées (best-effort, en fallback
    on logue juste — ne casse jamais le register) :

    1. Email SMTP : si CEE_SMTP_HOST + CEE_SMTP_USER + CEE_SMTP_PASS + CEE_ADMIN_EMAIL
    2. Webhook URL : si CEE_NOTIFY_WEBHOOK (POST JSON, compatible Slack/Discord)
    3. Sinon : log de niveau INFO (visible dans `fly logs`)
    """
    import logging
    log = logging.getLogger("cee_auth")
    msg = (
        f"[CEE Engine] Nouveau compte en attente de validation\n"
        f"Email : {new_user.get('email')}\n"
        f"Nom : {new_user.get('name')}\n"
        f"Action : aller sur /admin/users/pending et POST /admin/users/<email>/approve\n"
        f"Ou via UI : panel Admin (👑) → onglet Comptes en attente"
    )

    # 1. Webhook générique (Slack/Discord — payload {"text":...})
    webhook = os.environ.get("CEE_NOTIFY_WEBHOOK", "").strip()
    if webhook:
        try:
            import urllib.request as _req
            import json as _json
            payload = _json.dumps({"text": msg, "user": new_user}).encode()
            r = _req.Request(webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with _req.urlopen(r, timeout=4) as resp:
                resp.read()
            log.info("admin notify webhook ok")
        except Exception as e:
            log.warning("admin notify webhook err: %s", e)

    # 1bis. V37.3.38 — Telegram natif (plus fiable que WhatsApp CallMeBot)
    tg_token = os.environ.get("CEE_TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat = os.environ.get("CEE_TELEGRAM_CHAT_ID", "").strip()
    if tg_token and tg_chat:
        try:
            import urllib.request as _req
            import urllib.parse as _parse
            url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            data = _parse.urlencode({"chat_id": tg_chat, "text": msg, "parse_mode": "Markdown"}).encode()
            r = _req.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
            with _req.urlopen(r, timeout=6) as resp:
                resp.read()
            log.info("telegram notify sent to chat %s", tg_chat)
        except Exception as e:
            log.warning("telegram notify err: %s", e)

    # 1bis. V37.3.37 — WhatsApp (3 modes au choix selon env vars configurées)
    try:
        _send_whatsapp_notification(msg, new_user, log)
    except Exception as e:
        log.warning("whatsapp notify err: %s", e)

    # 2. Email SMTP
    host = os.environ.get("CEE_SMTP_HOST", "").strip()
    admin_email = os.environ.get("CEE_ADMIN_EMAIL", "").strip()
    if host and admin_email:
        try:
            import smtplib
            from email.message import EmailMessage
            em = EmailMessage()
            em["Subject"] = f"[CEE Engine] Nouveau compte en attente : {new_user.get('email')}"
            em["From"] = os.environ.get("CEE_SMTP_FROM", admin_email)
            em["To"] = admin_email
            em.set_content(msg)
            port = int(os.environ.get("CEE_SMTP_PORT", "587"))
            with smtplib.SMTP(host, port, timeout=8) as s:
                s.starttls()
                user_smtp = os.environ.get("CEE_SMTP_USER", "")
                pass_smtp = os.environ.get("CEE_SMTP_PASS", "")
                if user_smtp and pass_smtp:
                    s.login(user_smtp, pass_smtp)
                s.send_message(em)
            log.info("admin notify email sent to %s", admin_email)
        except Exception as e:
            log.warning("admin notify email err: %s", e)

    # 3. Log fallback (toujours)
    log.info("PENDING_USER %s", msg.replace("\n", " | "))


def update_user_status(email: str, new_status: str) -> dict | None:
    """V37.3.36 — Admin met à jour le status d'un user (approve / reject / suspend)."""
    if new_status not in ("active", "pending", "rejected"):
        raise ValueError("status invalide")
    users = _load_users()
    if email not in users:
        return None
    users[email]["status"] = new_status
    users[email]["status_updated_at"] = int(time.time())
    _save_users(users)
    return {k: v for k, v in users[email].items() if k != "password_hash"}


# ─────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────

def _extract_token() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def require_auth(role: str | None = None) -> Callable:
    """Décorateur — protège une route, injecte `current_user` en kwarg."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            token = _extract_token()
            payload = jwt_verify(token) if token else None
            if not payload:
                return jsonify({"error": "Unauthorized — JWT Bearer requis"}), 401
            if role and payload.get("role") != role:
                # 'admin' peut accéder à tout, sinon stricte équivalence
                if payload.get("role") != "admin":
                    return jsonify({"error": f"Forbidden — rôle {role} requis"}), 403
            kwargs["current_user"] = payload
            return f(*args, **kwargs)
        return wrapper
    return decorator


def register_auth_routes(app) -> None:
    """Enregistre les routes /auth/* sur l'app Flask fournie."""

    @app.route("/auth/login", methods=["POST"])
    def _login():
        if not JWT_SECRET:
            return jsonify({"error": "CEE_JWT_SECRET non configuré côté serveur"}), 500
        data = request.json or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        if not email or not password:
            return jsonify({"error": "email et password requis"}), 400
        try:
            user = authenticate(email, password)
        except PermissionError as e:
            # V37.3.36 — compte pending ou rejected
            return jsonify({"error": str(e), "status": "pending_or_rejected"}), 403
        if not user:
            time.sleep(0.3)
            return jsonify({"error": "identifiants invalides"}), 401
        token = jwt_sign({"sub": user["email"], "role": user["role"], "name": user["name"]})
        return jsonify({"token": token, "user": user})

    @app.route("/auth/register", methods=["POST"])
    def _register():
        """V37.3.36 — Self-service register avec validation admin :
        - 1er user créé = admin automatique status=active (bootstrap)
        - Sans token : compte créé en status=pending → admin doit approuver
        - Avec token admin : peut créer directement en status=active + role choisi
        """
        if not JWT_SECRET:
            return jsonify({"error": "CEE_JWT_SECRET non configuré côté serveur"}), 500
        data = request.json or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        name = data.get("name", "")
        role = data.get("role", "user")

        if not email or not password or len(password) < 8:
            return jsonify({"error": "email + password (min 8 chars) requis"}), 400

        users = _load_users()
        is_bootstrap = len(users) == 0
        token = _extract_token()
        payload = jwt_verify(token) if token else None
        is_admin = payload and payload.get("role") == "admin"

        try:
            if is_bootstrap:
                # Bootstrap : 1er user = admin actif
                u = create_user(email, password, name, "admin", status="active")
                return jsonify({"user": u, "bootstrap_admin": True})
            elif is_admin:
                # Admin crée directement un compte actif
                u = create_user(email, password, name, role, status="active")
                return jsonify({"user": u, "created_by_admin": True})
            else:
                # Self-service public : compte créé en pending
                u = create_user(email, password, name, "user", status="pending")
                # Hook notification admin (best-effort, ne casse pas le register)
                try:
                    _notify_admin_pending(u)
                except Exception:
                    pass
                return jsonify({
                    "user": u,
                    "status": "pending",
                    "message": "Compte créé avec succès. Il sera activé après validation par l'administrateur. Vous recevrez confirmation par email.",
                }), 202
        except ValueError as e:
            return jsonify({"error": str(e)}), 409

    @app.route("/admin/users/pending", methods=["GET"])
    @require_auth(role="admin")
    def _admin_pending(current_user=None):
        """V37.3.36 — Liste les comptes en attente de validation."""
        return jsonify({"pending": list_users_with_status("pending")})

    @app.route("/admin/users/all", methods=["GET"])
    @require_auth(role="admin")
    def _admin_users_all(current_user=None):
        """V37.3.36 — Liste tous les comptes (active + pending + rejected)."""
        return jsonify({
            "active": list_users_with_status("active"),
            "pending": list_users_with_status("pending"),
            "rejected": list_users_with_status("rejected"),
        })

    @app.route("/admin/users/<email>/approve", methods=["POST"])
    @require_auth(role="admin")
    def _admin_approve(email, current_user=None):
        """V37.3.36 — Approuve un compte pending → status=active."""
        u = update_user_status(email.lower(), "active")
        if not u:
            return jsonify({"error": "user inconnu"}), 404
        return jsonify({"ok": True, "user": u, "action": "approved"})

    @app.route("/admin/users/<email>/reject", methods=["POST"])
    @require_auth(role="admin")
    def _admin_reject(email, current_user=None):
        """V37.3.36 — Rejette un compte pending ou suspend un actif."""
        u = update_user_status(email.lower(), "rejected")
        if not u:
            return jsonify({"error": "user inconnu"}), 404
        return jsonify({"ok": True, "user": u, "action": "rejected"})

    @app.route("/auth/me", methods=["GET"])
    @require_auth()
    def _me(current_user=None):
        return jsonify(current_user)

    @app.route("/auth/logout", methods=["POST"])
    def _logout():
        # Stateless JWT : le client supprime le token. Ici on confirme juste.
        return jsonify({"ok": True})

    @app.route("/auth/status", methods=["GET"])
    def _auth_status():
        """Expose si l'auth est configurée (booléen uniquement)."""
        users = _load_users()
        return jsonify({
            "auth_enabled": bool(JWT_SECRET),
            "users_count": len(users),
            "bootstrap_available": bool(JWT_SECRET) and len(users) == 0,
        })
