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


def create_user(email: str, password: str, name: str = "", role: str = "user") -> dict:
    users = _load_users()
    if email in users:
        raise ValueError("user déjà existant")
    user = {
        "email": email,
        "name": name or email.split("@")[0],
        "role": role,  # 'admin' | 'user' | 'readonly'
        "password_hash": hash_password(password),
        "created_at": int(time.time()),
    }
    users[email] = user
    _save_users(users)
    # Ne pas renvoyer le hash
    return {k: v for k, v in user.items() if k != "password_hash"}


def authenticate(email: str, password: str) -> dict | None:
    users = _load_users()
    user = users.get(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {k: v for k, v in user.items() if k != "password_hash"}


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
        user = authenticate(email, password)
        if not user:
            # Délai fixe anti-bruteforce (pauvre mais mieux que rien)
            time.sleep(0.3)
            return jsonify({"error": "identifiants invalides"}), 401
        token = jwt_sign({"sub": user["email"], "role": user["role"], "name": user["name"]})
        return jsonify({"token": token, "user": user})

    @app.route("/auth/register", methods=["POST"])
    def _register():
        if not JWT_SECRET:
            return jsonify({"error": "CEE_JWT_SECRET non configuré côté serveur"}), 500
        data = request.json or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        name = data.get("name", "")
        role = data.get("role", "user")

        users = _load_users()
        # Premier utilisateur = admin automatique (bootstrap)
        is_bootstrap = len(users) == 0
        if not is_bootstrap:
            # Sinon exige un token admin
            token = _extract_token()
            payload = jwt_verify(token) if token else None
            if not payload or payload.get("role") != "admin":
                return jsonify({"error": "admin requis pour créer des utilisateurs"}), 403

        if not email or not password or len(password) < 8:
            return jsonify({"error": "email + password (min 8 chars) requis"}), 400

        try:
            new_role = "admin" if is_bootstrap else role
            u = create_user(email, password, name, new_role)
            return jsonify({"user": u, "bootstrap_admin": is_bootstrap})
        except ValueError as e:
            return jsonify({"error": str(e)}), 409

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
