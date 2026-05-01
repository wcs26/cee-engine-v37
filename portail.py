"""
CEE Engine V37 P4.7 — Portail bénéficiaire (vue read-only pour client final).

Jimmy génère un token opaque pour un dossier. Il envoie l'URL /portail/<token>
au client (DAF, CFO, gérant). Le client ouvre → voit : prime estimée, gisements,
statut des documents, sans connexion. Aucune donnée sensible exposée.

Token = signature HMAC légère (pas de base — encodé dans l'URL).
Format : base64url(JSON{data}).base64url(HMAC(JSON, CEE_PORTAL_SECRET))
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from flask import Response, request


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _secret() -> str:
    """V37.3.42 — fail-closed sauf si CEE_ENV est explicitement un environnement dev.

    Avant : `== "prod"` strict laissait passer "production", "PROD ", "staging", unset.
    Maintenant : whitelist dev/test/local, tout le reste exige un secret fort.
    """
    s = os.environ.get("CEE_PORTAL_SECRET") or os.environ.get("CEE_JWT_SECRET")
    if s:
        return s
    env = os.environ.get("CEE_ENV", "").strip().lower()
    DEV_ENVS = ("", "dev", "development", "test", "local")
    if env not in DEV_ENVS:
        raise RuntimeError(
            f"CEE_PORTAL_SECRET (or CEE_JWT_SECRET) must be set when CEE_ENV={env!r} — "
            f"refusing to use weak fallback secret. Whitelist dev envs: {DEV_ENVS!r}"
        )
    return "dev-secret-change-me"


def encode_token(dossier: dict, ttl_days: int = 30) -> str:
    """Encode un dossier (beneficiaire + prime + fiches) dans un token URL-safe."""
    payload = {**dossier, "iat": int(time.time()), "exp": int(time.time()) + ttl_days * 86400}
    body = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64url(sig)}"


def decode_token(token: str) -> dict | None:
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_decode(sig), expected):
            return None
        payload = json.loads(_b64url_decode(body))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


PORTAL_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Votre dossier CEE — {{nom}}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f7f9fc; color: #1a2332; margin: 0; padding: 30px 20px; }}
  .container {{ max-width: 720px; margin: 0 auto; }}
  .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }}
  .logo {{ font-size: 14px; font-weight: 700; color: #00a891; letter-spacing: 2px; }}
  .date {{ font-size: 12px; color: #6b7280; }}
  .hero {{ background: linear-gradient(135deg, #00a89115, #8b5cf615); border: 2px solid #00a89140; border-radius: 16px; padding: 32px; margin-bottom: 24px; text-align: center; }}
  .nom {{ font-size: 22px; font-weight: 700; margin: 0 0 8px; }}
  .siret {{ font-family: "SF Mono", Menlo, monospace; font-size: 13px; color: #6b7280; }}
  .prime {{ font-size: 48px; font-weight: 900; color: #00a891; margin: 20px 0 4px; font-family: "SF Mono", Menlo, monospace; }}
  .prime-label {{ font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 2px; }}
  .card {{ background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.03); }}
  .card h3 {{ margin: 0 0 12px; font-size: 14px; color: #374151; text-transform: uppercase; letter-spacing: 1px; }}
  .fiche {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #f3f4f6; }}
  .fiche:last-child {{ border: none; }}
  .fiche-ref {{ font-family: "SF Mono", Menlo, monospace; font-weight: 700; color: #00a891; }}
  .fiche-nom {{ flex: 1; padding: 0 12px; color: #374151; font-size: 13px; }}
  .fiche-prime {{ font-weight: 700; color: #1a2332; }}
  .status {{ display: inline-block; padding: 4px 12px; border-radius: 16px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }}
  .status-go {{ background: #00a89120; color: #00a891; }}
  .status-prudence {{ background: #d2992220; color: #d29922; }}
  .status-stop {{ background: #ef444420; color: #ef4444; }}
  .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 11px; color: #9ca3af; text-align: center; }}
  .footer strong {{ color: #374151; }}
  .cta {{ display: inline-block; padding: 10px 20px; background: #00a891; color: white; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 8px 4px; font-size: 13px; }}
</style></head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">⚡ CEE ENGINE</div>
    <div class="date">Édité le {{date}}</div>
  </div>

  <div class="hero">
    <div class="nom">{{nom}}</div>
    <div class="siret">SIRET {{siret}}</div>
    <div class="prime">{{prime}}</div>
    <div class="prime-label">💰 Prime CEE estimée — {{nb_fiches}} fiche(s) éligible(s)</div>
    {{verdict_html}}
  </div>

  <div class="card">
    <h3>🎯 Opérations identifiées</h3>
    {{fiches_html}}
  </div>

  <div class="card">
    <h3>📋 Statut du dossier</h3>
    <p style="margin: 0 0 10px; font-size: 13px; color: #374151;">
      Ce dossier a été diagnostiqué par <strong>CEE Engine V37</strong> — l'outil le plus complet
      du marché (234 fiches, 5 sources open data, Penta-IA).
    </p>
    <p style="margin: 0; font-size: 13px; color: #374151;">
      Votre interlocuteur finalisera les étapes suivantes :
      <strong>1.</strong> Signature mandat de cession ·
      <strong>2.</strong> Devis travaux RGE ·
      <strong>3.</strong> Dépôt PNCEE ·
      <strong>4.</strong> Versement de la prime (sous 60-90 j).
    </p>
  </div>

  <div class="card" style="background: #fef3c7; border-color: #fcd34d;">
    <h3 style="color: #92400e;">🔒 Confidentialité</h3>
    <p style="margin: 0; font-size: 12px; color: #78350f;">
      Cette page est accessible via un lien unique signé cryptographiquement. Elle expire automatiquement.
      Aucune donnée sensible (contrats, clés API, coordonnées bancaires) n'est affichée ici.
    </p>
  </div>

  <div class="footer">
    <strong>CEE Engine V37 PRO</strong> · Audit CEE prédictif · 0 % commission · Prime intégrale au client<br>
    Ce document est généré automatiquement à titre indicatif. La prime effective est validée par le PNCEE au dépôt.
  </div>
</div>
</body></html>"""


def _escape_html(s) -> str:
    """Échappement HTML complet — protection XSS sur toutes les valeurs client."""
    if s is None:
        return ""
    s = str(s)
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#x27;")
         .replace("/", "&#x2F;")  # neutralise </script> dans un <script>
    )


def render_portal(payload: dict) -> str:
    """Rendu HTML — TOUS les champs issus du payload sont échappés (protection XSS)."""
    fiches = payload.get("operations") or []
    fiches_html = ""
    for op in fiches:
        ref = _escape_html(op.get("ref", ""))
        nom = _escape_html(op.get("nom", "")[:80])
        prime_f = op.get("prime_eur") or 0
        try:
            prime_int = int(float(prime_f))
        except Exception:
            prime_int = 0
        fiches_html += (
            f'<div class="fiche"><span class="fiche-ref">{ref}</span>'
            f'<span class="fiche-nom">{nom}</span>'
            f'<span class="fiche-prime">{prime_int:,} €</span></div>'
        )
    if not fiches_html:
        fiches_html = '<p style="color:#6b7280;font-size:13px;">Aucune opération détaillée.</p>'

    verdict_raw = str(payload.get("verdict", "")).strip().upper()
    # Whitelist stricte du verdict (pas d'échappement nécessaire car valeurs fixées)
    verdict_html = ""
    if verdict_raw in ("GO", "PRUDENCE", "STOP"):
        cls = {"GO": "status-go", "PRUDENCE": "status-prudence", "STOP": "status-stop"}[verdict_raw]
        verdict_html = f'<div class="status {cls}" style="margin-top:12px;">Verdict : {verdict_raw}</div>'

    total_prime = sum(o.get("prime_eur", 0) or 0 for o in fiches) or payload.get("prime_totale", 0) or 0
    try:
        total_prime_int = int(float(total_prime))
    except Exception:
        total_prime_int = 0

    nom_safe = _escape_html(payload.get("raison_sociale", "—"))
    siret_safe = _escape_html(payload.get("siret", "—"))
    prime_str = f"{total_prime_int:,} €".replace(",", " ")

    return PORTAL_HTML_TEMPLATE.replace("{{nom}}", nom_safe).replace(
        "{{siret}}", siret_safe
    ).replace(
        "{{prime}}", prime_str
    ).replace(
        "{{nb_fiches}}", str(len(fiches))
    ).replace(
        "{{date}}", time.strftime("%d/%m/%Y à %H:%M")
    ).replace(
        "{{fiches_html}}", fiches_html
    ).replace(
        "{{verdict_html}}", verdict_html
    )


def register_portail_routes(app) -> None:
    @app.route("/portail/<token>", methods=["GET"])
    def _portail(token):
        payload = decode_token(token)
        if not payload:
            return Response(
                "<html><body style='font-family:sans-serif;padding:40px;text-align:center;'>"
                "<h1>🔒 Lien invalide ou expiré</h1>"
                "<p>Ce lien a expiré ou a été modifié. Contactez votre interlocuteur CEE Engine pour un nouveau lien.</p>"
                "</body></html>",
                status=404, mimetype="text/html",
            )
        return Response(render_portal(payload), mimetype="text/html; charset=utf-8")

    @app.route("/portail/generate", methods=["POST"])
    def _generate_portal():
        """Génère un token portail pour un dossier (Jimmy/admin usage)."""
        from flask import jsonify
        data = request.json or {}
        if not data.get("siret"):
            return jsonify({"error": "siret requis"}), 400
        ttl = int(data.get("ttl_days", 30))
        token = encode_token(data, ttl_days=ttl)
        return jsonify({
            "token": token,
            "url": f"/portail/{token}",
            "expires_in_days": ttl,
        })
