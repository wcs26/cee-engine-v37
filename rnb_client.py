"""
V37.3.30 — Client API RNB (Référentiel National des Bâtiments).

Le RNB fournit un identifiant unique stable pour chaque bâtiment français.
Cet ID-RNB est diffusé dans 60+ bases publiques (DPE-ADEME, BAN, Cadastre,
RIAL...) et permet l'interopérabilité entre toutes ces sources.

Pour CEE Engine, intégrer l'ID-RNB sur chaque tunnel apporte :
- Traçabilité officielle du bâtiment audité (clé d'État stable)
- Croisement automatique avec autres bases publiques (DPE, cadastre, BDNB)
- Crédibilité institutionnelle (cas d'usage référencable sur rnb.beta.gouv.fr)
- Possibilité future de signaler des anomalies (contributeur RNB)

Endpoints utilisés :
- BAN api-adresse.data.gouv.fr : géocodage adresse → cle_interop_ban
- RNB rnb-api.beta.gouv.fr   : cle_interop_ban → ID-RNB

Aucune authentification requise (API publique gratuite).
"""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
import logging

logger = logging.getLogger("cee.rnb_client")

BAN_BASE = "https://api-adresse.data.gouv.fr/search/"
RNB_BASE = "https://rnb-api.beta.gouv.fr/api/alpha/buildings/"


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch_json(url: str, timeout: int = 8) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CEE-Engine/V37.3"})
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        logger.warning("rnb fetch err url=%s err=%s", url, e)
        return {"_error": str(e)[:120]}


def geocode_address(address: str) -> dict:
    """Géocode une adresse via la BAN. Retourne :
    {label, cle_interop_ban, lon, lat, postcode, citycode, type, score}
    ou {_error: ...}
    """
    if not address:
        return {"_error": "address vide"}
    url = BAN_BASE + "?" + urllib.parse.urlencode({"q": address, "limit": 1})
    d = _fetch_json(url)
    if "_error" in d:
        return d
    feats = d.get("features") or []
    if not feats:
        return {"_error": "adresse non trouvée"}
    f = feats[0]
    p = f.get("properties", {}) or {}
    coords = f.get("geometry", {}).get("coordinates", [None, None])
    return {
        "label": p.get("label", ""),
        "cle_interop_ban": p.get("id", ""),  # ex: 75101_8249_00132
        "lon": coords[0] if len(coords) >= 2 else None,
        "lat": coords[1] if len(coords) >= 2 else None,
        "postcode": p.get("postcode", ""),
        "citycode": p.get("citycode", ""),
        "type": p.get("type", ""),       # housenumber / street / locality
        "score": p.get("score", 0),
    }


def get_rnb_id_from_ban_key(cle_interop_ban: str) -> dict:
    """Cherche l'ID-RNB du bâtiment correspondant à une clé BAN.
    Retourne {rnb_id, status, point, shape, source} ou {_error: ...}
    """
    if not cle_interop_ban:
        return {"_error": "cle_interop_ban vide"}
    url = RNB_BASE + "?" + urllib.parse.urlencode({
        "cle_interop_ban": cle_interop_ban,
        "page_size": 1,
    })
    d = _fetch_json(url)
    if "_error" in d:
        return d
    results = d.get("results") or []
    if not results:
        return {"_error": "aucun bâtiment RNB pour cette clé BAN"}
    b = results[0]
    return {
        "rnb_id": b.get("rnb_id"),
        "status": b.get("status"),
        "point": b.get("point"),
        "source": "rnb-api.beta.gouv.fr/api/alpha/buildings + cle_interop_ban",
    }


def get_rnb_id_from_address(address: str) -> dict:
    """Workflow complet : adresse texte → géocodage BAN → ID-RNB.
    Retourne {rnb_id, label_ban, cle_interop_ban, score_geocode, status, ...}
    ou {_error: ...} si étape échoue.
    """
    if not address:
        return {"_error": "address vide"}
    geo = geocode_address(address)
    if "_error" in geo:
        return {"_error": f"géocodage BAN : {geo['_error']}"}
    if not geo.get("cle_interop_ban"):
        return {"_error": "BAN sans cle_interop_ban (adresse imprécise)"}
    if geo.get("score", 0) < 0.5:
        # Adresse géocodée avec faible confiance : risque d'erreur
        return {
            "_error": f"géocodage BAN faible confiance (score {geo.get('score',0):.2f})",
            "ban_partial": geo,
        }

    rnb = get_rnb_id_from_ban_key(geo["cle_interop_ban"])
    if "_error" in rnb:
        return {
            "_error": f"recherche RNB : {rnb['_error']}",
            "ban": geo,
        }

    return {
        "rnb_id": rnb["rnb_id"],
        "rnb_status": rnb.get("status"),
        "rnb_point": rnb.get("point"),
        "ban_label": geo["label"],
        "cle_interop_ban": geo["cle_interop_ban"],
        "score_geocode": geo.get("score"),
        "source": "BAN + RNB combinés",
    }


# ─────────────────────────────────────────────────────────────────────────
# V37.3.31 — API édition (contributeur RNB authentifié)
# Pour utiliser : créer compte sur https://rnb.beta.gouv.fr/login → Mon compte
# → Mes Clés API → générer un token → exporter env var RNB_API_TOKEN.
# Auth format : "Authorization: Token <token>" (pas Bearer).
# Quota : 20 req/s + 500 ops/utilisateur (évolutif après vérif contributions).
# ─────────────────────────────────────────────────────────────────────────


def _auth_headers() -> dict:
    """Construit les headers HTTP avec le token RNB si disponible.
    Retourne dict vide si RNB_API_TOKEN absent (mode lecture seule)."""
    import os as _os
    token = _os.environ.get("RNB_API_TOKEN", "").strip()
    if not token:
        return {}
    return {"Authorization": f"Token {token}", "Content-Type": "application/json"}


def signal_anomalie(rnb_id: str, motif: str, comment: str = "",
                     new_status: str | None = None) -> dict:
    """V37.3.31 — Signale une anomalie sur un bâtiment via PATCH RNB.

    Cas d'usage CEE Engine : pendant un audit terrain, on détecte que le
    bâtiment référencé RNB est en réalité démoli/reconstruit/inadéquat.
    On peut le signaler officiellement.

    Args:
      rnb_id   : ID-RNB à modifier (12 chars)
      motif    : raison courte du signalement (ex: "démolition observée 2026-04-28")
      comment  : commentaire long pour traçabilité (audit Jimmy WCS Bulgaria)
      new_status : statut à appliquer (constructed | demolished |
                   construction_in_progress | demolished_in_progress)

    Retourne {ok, rnb_id, response} ou {_error, ...}
    """
    if not _auth_headers():
        return {"_error": "RNB_API_TOKEN non configuré (export env var)"}
    if not rnb_id or len(rnb_id) < 8:
        return {"_error": "rnb_id invalide"}

    url = RNB_BASE + rnb_id + "/"
    body = {"comment": f"[CEE Engine WCS Bulgaria EOOD] {motif} | {comment}".strip()[:480]}
    if new_status:
        body["status"] = new_status

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=_auth_headers(),
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx()) as r:
            resp = json.loads(r.read().decode("utf-8"))
        return {"ok": True, "rnb_id": rnb_id, "response": resp}
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}: {e.reason}", "rnb_id": rnb_id}
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {str(e)[:120]}", "rnb_id": rnb_id}


def is_contributeur_actif() -> dict:
    """Diagnostic simple : token configuré ou pas ?"""
    import os as _os
    token = _os.environ.get("RNB_API_TOKEN", "").strip()
    return {
        "token_configured": bool(token),
        "token_preview": (token[:6] + "…" + token[-4:]) if token else None,
        "mode": "contributeur" if token else "lecture seule (anonyme)",
        "doc": "https://rnb.beta.gouv.fr/login → Mon compte → Mes Clés API",
    }
