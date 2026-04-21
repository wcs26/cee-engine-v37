"""
CEE Engine V37 P4.6 — OpenAPI 3.0 + Swagger UI auto-générés.

/api/docs         → page HTML Swagger UI (onboarding partenaires)
/api/openapi.json → spec OpenAPI 3.0
"""
from __future__ import annotations

import re
from flask import jsonify, Response


SWAGGER_HTML = """<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="UTF-8">
<title>CEE Engine V37 — API Docs</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
<style>body{margin:0;background:#0d1117;} .swagger-ui .topbar{background:#161b22;}</style>
</head><body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  SwaggerUIBundle({
    url: "/api/openapi.json",
    dom_id: "#swagger-ui",
    deepLinking: true,
    tryItOutEnabled: true,
    displayOperationId: false,
    defaultModelsExpandDepth: 1,
    filter: true,
  });
</script>
</body></html>"""


# Description des tags par catégorie
TAGS_INFO = [
    {"name": "Core", "description": "Health, status, veille réglementaire"},
    {"name": "Moteur CEE", "description": "Calcul cumac, prime, diagnostic"},
    {"name": "Open Data", "description": "SIRET, cadastre, BD TOPO, DPE, BAN"},
    {"name": "IA", "description": "Penta-IA (GROQ, Gemini, Claude, Kimi, OpenAI) + Vision"},
    {"name": "Auth", "description": "JWT login, bootstrap admin, gestion users"},
    {"name": "RAG", "description": "Recherche sémantique TF-IDF sur 234 fiches CEE"},
    {"name": "PNCEE", "description": "Scoring avant dépôt + export XML/CSV officiel"},
    {"name": "Intégrations", "description": "Yousign, ERP Sage/Cegid, ATEE scraper"},
    {"name": "Multi-site", "description": "Optimisation parc, règles 75%, tolérance"},
    {"name": "Négociation", "description": "Comparateur 9 acheteurs CEE"},
]


def _classify_route(path: str) -> list[str]:
    if path.startswith("/auth"): return ["Auth"]
    if path.startswith("/rag"): return ["RAG"]
    if path.startswith("/pncee") or path.startswith("/export/pncee"): return ["PNCEE"]
    if path.startswith("/ai/"): return ["IA"]
    if path.startswith("/signature") or path.startswith("/webhook") or path.startswith("/integrations"): return ["Intégrations"]
    if path.startswith("/multisite") or path.startswith("/regles"): return ["Multi-site"]
    if path.startswith("/negociation") or path.startswith("/acheteurs"): return ["Négociation"]
    if path.startswith("/siret") or path.startswith("/etablissements") or path.startswith("/cadastre") or path.startswith("/batiment") or path.startswith("/dpe") or path.startswith("/proxy"): return ["Open Data"]
    if path in ("/analyse", "/expert", "/expert/oracle", "/recalcul", "/predictions", "/closing", "/validation/complete"): return ["Moteur CEE"]
    return ["Core"]


def build_openapi_spec(app) -> dict:
    """Génère une spec OpenAPI 3.0 minimaliste depuis les routes Flask."""
    paths = {}
    for rule in app.url_map.iter_rules():
        if rule.endpoint in ("static", "_rate_limit_check", "_rate_limit_headers"):
            continue
        path = str(rule)
        # Convertir <siren> en {siren} (format OpenAPI)
        oapi_path = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", path)
        methods = {m for m in rule.methods if m not in ("HEAD", "OPTIONS")}
        if not methods:
            continue

        handler = app.view_functions.get(rule.endpoint)
        doc = (handler.__doc__ or "").strip().split("\n")[0] if handler else ""
        tags = _classify_route(path)

        for method in methods:
            method_lower = method.lower()
            path_params = [
                {
                    "name": m.group(1),
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
                for m in re.finditer(r"<(?:\w+:)?(\w+)>", path)
            ]
            op = {
                "summary": doc or f"{method} {path}",
                "tags": tags,
                "operationId": f"{method_lower}_{rule.endpoint}",
                "parameters": path_params,
                "responses": {
                    "200": {"description": "OK"},
                    "400": {"description": "Requête invalide"},
                    "401": {"description": "Non authentifié"},
                    "403": {"description": "Interdit"},
                    "404": {"description": "Non trouvé"},
                    "429": {"description": "Rate limit dépassé"},
                    "500": {"description": "Erreur serveur"},
                },
            }
            if method in ("POST", "PUT", "PATCH"):
                op["requestBody"] = {
                    "required": False,
                    "content": {"application/json": {"schema": {"type": "object"}}},
                }
            paths.setdefault(oapi_path, {})[method_lower] = op

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "CEE Engine V37 PRO",
            "version": "V37-FUSED",
            "description": (
                "API **CEE Engine V37 PRO** — Audit prédictif/proactif/intelligent pour PME tertiaire "
                "et industrielle. 234 fiches CEE, 5 sources open data, Penta-IA, Conseil 5×3.\n\n"
                "**Positionnement** : 0 % commission, prime intégrale au client.\n\n"
                "**Auth** : certains endpoints requièrent JWT Bearer. Voir `/auth/login`.\n\n"
                "**Rate limiting** : 30 req/min sur /ai/*, 120 req/min sur /analyse et /expert, 300 req/min autres."
            ),
            "contact": {"name": "Jimmy · CEE Engine", "url": "/status"},
            "license": {"name": "Usage interne"},
        },
        "servers": [{"url": "/", "description": "Serveur courant"}],
        "tags": TAGS_INFO,
        "paths": paths,
        "components": {
            "securitySchemes": {
                "JWTBearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
                "GroqKey": {"type": "apiKey", "in": "header", "name": "X-Groq-Key"},
                "ClaudeKey": {"type": "apiKey", "in": "header", "name": "X-Claude-Key"},
                "KimiKey": {"type": "apiKey", "in": "header", "name": "X-Kimi-Key"},
                "OpenAIKey": {"type": "apiKey", "in": "header", "name": "X-OpenAI-Key"},
            }
        },
    }


def register_apidocs_routes(app) -> None:
    @app.route("/api/docs", methods=["GET"])
    def _swagger_ui():
        return Response(SWAGGER_HTML, mimetype="text/html; charset=utf-8")

    @app.route("/api/openapi.json", methods=["GET"])
    def _openapi_spec():
        return jsonify(build_openapi_spec(app))
