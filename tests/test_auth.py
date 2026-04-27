"""
V37.1 P4 — Tests auth.py : crypto + JWT + secret strength.

Couvre les cas critiques de sécurité :
- Hash password roundtrip (pbkdf2-sha256 + salt)
- JWT sign/verify roundtrip
- JWT expiré → rejeté
- JWT signature altérée → rejeté
- Secret faible → détecté
- Secret fort → accepté
"""
from __future__ import annotations

import importlib
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────
# Validation force du secret (fonction pure, pas de side-effect)
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_module():
    # Charger auth avec un secret fort pour ne pas crasher au boot prod
    os.environ["CEE_JWT_SECRET"] = "a" * 64  # 64 chars valides (pas de marqueur faible)
    os.environ.setdefault("CEE_ENV", "dev")
    if "auth" in sys.modules:
        importlib.reload(sys.modules["auth"])
    import auth
    return auth


def test_validate_secret_vide(auth_module):
    ok, msg = auth_module._validate_jwt_secret_strength("")
    assert ok is False
    assert "non défini" in msg


def test_validate_secret_court(auth_module):
    ok, msg = auth_module._validate_jwt_secret_strength("a" * 31)
    assert ok is False
    assert "trop court" in msg


def test_validate_secret_marqueur_faible(auth_module):
    for weak in ["dev-secret-v37-very-long-string-padding-padding", "test-key-12345-padded-padded-padded-padding", "default-1234567890-padded-padded-pad"]:
        ok, msg = auth_module._validate_jwt_secret_strength(weak)
        assert ok is False, f"secret '{weak}' aurait dû être rejeté"
        assert "marqueur faible" in msg


def test_validate_secret_fort(auth_module):
    strong = "f3e8a1b2c9d04567890abcdef0123456789fedcba9876543210abcdef0123456"
    ok, msg = auth_module._validate_jwt_secret_strength(strong)
    assert ok is True
    assert msg == "OK"


# ─────────────────────────────────────────────────────────────
# Password hash + verify
# ─────────────────────────────────────────────────────────────

def test_hash_password_format(auth_module):
    h = auth_module.hash_password("mon-password-secret")
    parts = h.split("$")
    assert len(parts) == 4
    assert parts[0] == "pbkdf2_sha256"
    assert int(parts[1]) >= 100_000  # itérations OWASP


def test_hash_password_different_salt(auth_module):
    h1 = auth_module.hash_password("password123")
    h2 = auth_module.hash_password("password123")
    assert h1 != h2, "deux hashes du même mot de passe doivent différer (salt aléatoire)"


def test_verify_password_correct(auth_module):
    h = auth_module.hash_password("Mot$de@Passe!")
    assert auth_module.verify_password("Mot$de@Passe!", h) is True


def test_verify_password_incorrect(auth_module):
    h = auth_module.hash_password("good")
    assert auth_module.verify_password("bad", h) is False
    assert auth_module.verify_password("", h) is False


def test_verify_password_format_corrompu(auth_module):
    assert auth_module.verify_password("anything", "") is False
    assert auth_module.verify_password("anything", "garbage") is False
    assert auth_module.verify_password("anything", "wrong$algo$salt$hash") is False


# ─────────────────────────────────────────────────────────────
# JWT sign + verify
# ─────────────────────────────────────────────────────────────

def test_jwt_sign_returns_three_parts(auth_module):
    token = auth_module.jwt_sign({"sub": "test@x.com", "role": "user"})
    assert len(token.split(".")) == 3


def test_jwt_roundtrip(auth_module):
    payload_in = {"sub": "jimmy@x.com", "role": "admin"}
    token = auth_module.jwt_sign(payload_in)
    payload_out = auth_module.jwt_verify(token)
    assert payload_out is not None
    assert payload_out["sub"] == "jimmy@x.com"
    assert payload_out["role"] == "admin"
    assert "iat" in payload_out
    assert "exp" in payload_out


def test_jwt_expire(auth_module, monkeypatch):
    """Token avec exp dans le passé → None."""
    # Patch time.time pour générer un token qui expire instantanément
    real_time = time.time
    monkeypatch.setattr(auth_module.time, "time", lambda: real_time() - auth_module.JWT_TTL_SECONDS - 100)
    expired_token = auth_module.jwt_sign({"sub": "test@x.com", "role": "user"})
    monkeypatch.setattr(auth_module.time, "time", real_time)
    assert auth_module.jwt_verify(expired_token) is None


def test_jwt_signature_alteree(auth_module):
    token = auth_module.jwt_sign({"sub": "test@x.com", "role": "user"})
    h, p, s = token.split(".")
    # Modifier la signature
    forged = f"{h}.{p}.{s[:-4]}AAAA"
    assert auth_module.jwt_verify(forged) is None


def test_jwt_payload_altere(auth_module):
    """Modifier le payload sans re-signer → rejet."""
    token = auth_module.jwt_sign({"sub": "user@x.com", "role": "user"})
    h, p, s = token.split(".")
    # Forger un payload "admin" en gardant l'ancienne signature
    import base64, json
    payload = json.loads(base64.urlsafe_b64decode(p + "=="))
    payload["role"] = "admin"
    forged_p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    forged = f"{h}.{forged_p}.{s}"
    assert auth_module.jwt_verify(forged) is None, "élévation de privilège non détectée"


def test_jwt_token_vide(auth_module):
    assert auth_module.jwt_verify("") is None
    assert auth_module.jwt_verify("a.b") is None
    assert auth_module.jwt_verify("garbage") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
