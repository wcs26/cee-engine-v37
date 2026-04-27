"""
Synchronisation bidirectionnelle CEE Engine ↔ Monday CRM.

Flux :
  1. SIRET saisi dans CEE Engine → audit → résultat
  2. Bouton "Envoyer vers Monday" → crée/update un item dans le board OXEO
  3. Statut Monday mis à jour → webhook callback → met à jour le dossier CEE Engine

Board cible : configurable (OXEO 1303097067 par défaut)
Workspace : WCS - MA MEILLEURE ENERGIE (ID 2468250)

Endpoints :
  POST /monday/push-dossier       — pousse un dossier CEE vers Monday
  POST /monday/webhook             — callback Monday (changement statut)
  GET  /monday/pull/<item_id>      — récupère un item Monday dans le format CEE Engine
  GET  /monday/boards              — liste les boards disponibles
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from flask import jsonify, request

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_DEFAULT_BOARD = int(os.environ.get("MONDAY_BOARD_ID", "1303097067"))
MONDAY_REPORTING_BOARD = int(os.environ.get("MONDAY_REPORTING_BOARD_ID", "5094840479"))


def _monday_token() -> str:
    return os.environ.get("MONDAY_API_TOKEN", "")


def _ssl_ctx():
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _monday_query(query: str, variables: dict | None = None) -> dict:
    """Exécute une requête GraphQL Monday.com."""
    import urllib.request
    token = _monday_token()
    if not token:
        return {"error": "MONDAY_API_TOKEN non configuré"}
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        MONDAY_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": token,
            "API-Version": "2024-10",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx()) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def push_dossier_to_monday(dossier: dict, board_id: int | None = None) -> dict:
    """Crée un item Monday à partir d'un dossier CEE Engine.

    Mapping champs CEE Engine → colonnes Monday OXEO :
      - nom_chantier → Name
      - prime_obligé → chiffres (CA)
      - surface → produit_vendu1 (puissance vendu)
      - statut → status (Leads non traités par défaut)
      - date → sembly_date
    """
    bid = board_id or MONDAY_DEFAULT_BOARD
    client = dossier.get("client", {})
    op = dossier.get("operation", {})
    calc = dossier.get("calcul", {})
    admin = dossier.get("admin", {})

    item_name = f"{client.get('raison_sociale', '')} — {op.get('nom_chantier', '')}".strip(" —")
    if not item_name:
        item_name = f"CEE {op.get('fiche', '')} {op.get('surface_m2', '')}m²"

    column_values = {}
    if op.get("surface_m2"):
        column_values["produit_vendu1"] = str(op["surface_m2"])
    if calc.get("prime_obligé_eur"):
        column_values["chiffres"] = str(calc["prime_obligé_eur"])
    if admin.get("devis_date"):
        column_values["sembly_date"] = {"date": admin["devis_date"]}
    if client.get("siret"):
        column_values["texte56"] = client["siret"]

    query = """
    mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
        create_item(
            board_id: $boardId,
            item_name: $itemName,
            column_values: $columnValues
        ) {
            id
            name
            board { id name }
        }
    }
    """
    result = _monday_query(query, {
        "boardId": str(bid),
        "itemName": item_name,
        "columnValues": json.dumps(column_values),
    })

    if "error" in result:
        return result
    data = result.get("data", {}).get("create_item", {})
    return {
        "ok": True,
        "monday_item_id": data.get("id"),
        "monday_item_name": data.get("name"),
        "board": data.get("board", {}),
        "url": f"https://wcspro.monday.com/boards/{bid}/pulses/{data.get('id', '')}",
    }


def pull_monday_item(item_id: int) -> dict:
    """Récupère un item Monday et le convertit en format CEE Engine."""
    query = """
    query ($itemId: [ID!]!) {
        items(ids: $itemId) {
            id name
            column_values { id title text value }
            board { id name }
        }
    }
    """
    result = _monday_query(query, {"itemId": [str(item_id)]})
    if "error" in result:
        return result
    items = result.get("data", {}).get("items", [])
    if not items:
        return {"error": f"Item {item_id} introuvable"}
    item = items[0]
    cols = {c["id"]: c.get("text") or c.get("value", "") for c in item.get("column_values", [])}

    return {
        "monday_item_id": item["id"],
        "monday_item_name": item["name"],
        "board": item.get("board", {}),
        "mapping_cee": {
            "raison_sociale": item["name"].split("—")[0].strip() if "—" in item["name"] else item["name"],
            "nom_chantier": item["name"].split("—")[1].strip() if "—" in item["name"] else "",
            "siret": cols.get("texte56", ""),
            "surface_m2": cols.get("produit_vendu1", ""),
            "prime_eur": cols.get("chiffres", ""),
            "statut_monday": cols.get("status", ""),
            "date": cols.get("sembly_date", ""),
            "vendeur": cols.get("statut", ""),
        },
    }


def register_monday_routes(app) -> None:

    @app.route("/monday/status", methods=["GET"])
    def _monday_status():
        token = _monday_token()
        if not token:
            return jsonify({"connected": False, "error": "MONDAY_API_TOKEN non configuré. Ajouter dans .env"})
        result = _monday_query("query { me { id name email } }")
        if "error" in result:
            return jsonify({"connected": False, "error": result["error"]})
        me = result.get("data", {}).get("me", {})
        return jsonify({"connected": True, "user": me, "default_board": MONDAY_DEFAULT_BOARD})

    @app.route("/monday/boards", methods=["GET"])
    def _monday_boards():
        result = _monday_query("""
            query { boards(limit: 20, order_by: used_at) {
                id name items_count workspace { id name }
            }}
        """)
        if "error" in result:
            return jsonify(result), 502
        return jsonify({"boards": result.get("data", {}).get("boards", [])})

    @app.route("/monday/push-dossier", methods=["POST"])
    def _monday_push():
        """Pousse un dossier CEE Engine vers Monday CRM."""
        data = request.json or {}
        board_id = data.get("board_id", MONDAY_DEFAULT_BOARD)
        result = push_dossier_to_monday(data, board_id=board_id)
        if "error" in result:
            return jsonify(result), 502
        return jsonify(result), 201

    @app.route("/monday/pull/<int:item_id>", methods=["GET"])
    def _monday_pull(item_id):
        """Récupère un item Monday et retourne au format CEE Engine."""
        result = pull_monday_item(item_id)
        if "error" in result:
            return jsonify(result), 404
        return jsonify(result)

    @app.route("/monday/push-reporting", methods=["POST"])
    def _monday_push_reporting():
        """Pousse un audit CEE complet vers le board Reporting (colonnes enrichies).
        Body = dossier CEE Engine complet (client/operation/calcul/dispositif/admin)."""
        data = request.json or {}
        client = data.get("client", {})
        op = data.get("operation", {})
        calc = data.get("calcul", {})
        admin = data.get("admin", {})
        disp = data.get("dispositif", {})

        item_name = f"{client.get('raison_sociale', 'Sans nom')} — {op.get('nom_chantier', op.get('fiche', ''))}"

        # IDs colonnes réels du board 5094841405 (récupérés via API)
        col_vals = {}
        if client.get("siret"): col_vals["text_mm2hf5xa"] = client["siret"]
        if op.get("surface_m2"): col_vals["numeric_mm2hsk7a"] = str(op["surface_m2"])
        if calc.get("prime_obligé_eur"): col_vals["numeric_mm2hq3gr"] = str(calc["prime_obligé_eur"])
        if calc.get("reste_a_charge_eur") is not None: col_vals["numeric_mm2httv8"] = str(calc["reste_a_charge_eur"])
        if calc.get("commission_jimmy_eur"): col_vals["numeric_mm2hndqk"] = str(calc["commission_jimmy_eur"])
        if op.get("fiche"): col_vals["text_mm2h688t"] = op["fiche"]
        if disp.get("delegataire_nom"): col_vals["text_mm2hvnx8"] = disp["delegataire_nom"]
        if admin.get("devis_date"): col_vals["date_mm2hg2h5"] = {"date": admin["devis_date"]}
        if admin.get("devis_date"): col_vals["date_mm2hrcrf"] = {"date": admin["devis_date"]}
        if data.get("dossier_url"): col_vals["link_mm2haqmh"] = {"url": data["dossier_url"], "text": "Ouvrir dossier"}
        col_vals["text_mm2hrkex"] = data.get("ia_consultees", "GROQ+Gemini+Kimi+OpenAI")

        group_id = data.get("group_id", "group_mm2hvk6b")  # R0 — Lead reçu par défaut

        query = """
        mutation ($boardId: ID!, $groupId: String!, $itemName: String!, $columnValues: JSON!) {
            create_item(
                board_id: $boardId,
                group_id: $groupId,
                item_name: $itemName,
                column_values: $columnValues
            ) { id name }
        }
        """
        result = _monday_query(query, {
            "boardId": str(MONDAY_REPORTING_BOARD),
            "groupId": group_id,
            "itemName": item_name,
            "columnValues": json.dumps(col_vals),
        })
        if "error" in result:
            return jsonify(result), 502
        item_data = (result.get("data") or {}).get("create_item")
        if not item_data:
            errors = result.get("errors") or result.get("error_message") or str(result)
            return jsonify({"error": f"Monday create_item échoué: {str(errors)[:200]}"}), 502
        return jsonify({
            "ok": True,
            "board": "CEE Engine — Reporting & Suivi",
            "board_id": MONDAY_REPORTING_BOARD,
            "item_id": item_data.get("id"),
            "item_name": item_data.get("name"),
            "url": f"https://wcspro.monday.com/boards/{MONDAY_REPORTING_BOARD}/pulses/{item_data.get('id', '')}",
            "group": group_id,
        }), 201

    def _verify_monday_jwt(token: str, secret: str) -> bool:
        """Verify a JWT HS256 signed by Monday using shared signature_secret.
        Monday envoie Authorization: <jwt> sur chaque event si signature_secret
        a été défini à la création du webhook (config: {signature_secret: ...}).
        """
        import hmac as _hmac
        import hashlib as _hashlib
        import base64 as _base64
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return False
            h, p, s = parts
            expected = _hmac.new(secret.encode(), f"{h}.{p}".encode(), _hashlib.sha256).digest()
            pad = "=" * (-len(s) % 4)
            provided = _base64.urlsafe_b64decode(s + pad)
            return _hmac.compare_digest(provided, expected)
        except Exception:
            return False

    @app.route("/monday/webhook", methods=["POST"])
    def _monday_webhook():
        """Callback webhook Monday (changement de statut).

        V37.1.1 sécu :
        - Challenge Monday traité AVANT toute vérification (Monday ne signe pas le challenge initial)
        - Sur events réels : 2 modes de validation acceptés
            (a) JWT HS256 signé avec MONDAY_WEBHOOK_SECRET (Monday natif quand config.signature_secret est set)
            (b) Authorization brut == MONDAY_WEBHOOK_SECRET (compat tests / clients custom)
        """
        import hmac as _hmac
        import os as _os
        data = request.json or {}
        # 1. Challenge Monday — non signé, doit passer pour que Monday accepte de créer le webhook.
        if "challenge" in data:
            return jsonify({"challenge": data["challenge"]})
        # 2. Vérification token si secret configuré.
        # Monday natif n'accepte pas signature_secret sur l'event change_column_value.
        # Pattern utilisé : token en query param de l'URL configurée côté Monday
        # (ex: https://cee-engine-v37.fly.dev/monday/webhook?token=<MONDAY_WEBHOOK_SECRET>).
        # Acceptés aussi : Authorization brut (compat) et JWT signé (si Monday le supporte un jour).
        webhook_secret = _os.environ.get("MONDAY_WEBHOOK_SECRET", "")
        if webhook_secret:
            url_token = request.args.get("token", "")
            auth_header = request.headers.get("Authorization", "")
            valid = False
            if url_token and _hmac.compare_digest(url_token, webhook_secret):
                valid = True  # mode URL ?token=...
            elif auth_header:
                if _verify_monday_jwt(auth_header, webhook_secret):
                    valid = True  # mode JWT Monday (futur)
                elif _hmac.compare_digest(auth_header, webhook_secret):
                    valid = True  # mode header brut
            if not valid:
                return jsonify({"error": "Webhook signature invalide"}), 403
        elif _os.environ.get("CEE_ENV", "dev") == "prod":
            return jsonify({"error": "MONDAY_WEBHOOK_SECRET non configuré côté serveur"}), 503
        event = data.get("event", {})
        item_id = event.get("pulseId")
        column_id = event.get("columnId")
        new_value = event.get("value", {})
        from conformite import journal
        journal("monday_webhook", {
            "item_id": item_id,
            "column_id": column_id,
            "new_value": str(new_value)[:200],
        })

        # V37.3.6 — Monday → tunnel : MAJ stage tunnel correspondant
        # Mapping group_id Monday → stage tunnel (depuis post_signature.MONDAY_GROUPS)
        tunnel_synced = None
        try:
            if item_id:
                from tunnel import list_tunnels, advance_tunnel, _load
                # Trouver le tunnel avec ce monday_item_id
                target_tunnel = None
                for t_meta in list_tunnels():
                    full = _load(t_meta["tunnel_id"])
                    if full and str(full.get("monday_item_id", "")) == str(item_id):
                        target_tunnel = full
                        break
                if target_tunnel:
                    # Mapping group_id Monday → stage tunnel (basé sur post_signature.MONDAY_GROUPS inversé)
                    new_group = (new_value or {}).get("value", {}) if isinstance(new_value, dict) else {}
                    new_group_id = None
                    if isinstance(new_value, dict):
                        new_group_id = new_value.get("value", {}).get("post_id") if isinstance(new_value.get("value"), dict) else None
                    # Mapping inversé : group monday → stage tunnel
                    monday_group_to_stage = {
                        "group_mm2hvk6b": "lead",        # R0
                        "group_mm2hpegm": "r1",           # R1
                        "group_mm2hqh5y": "r1",           # VT
                        "group_mm2hegvh": "r2",           # R2
                        "group_mm2hds6w": "signature",    # devis_signe
                        "group_mm2hwd61": "post_signature",  # travaux_en_cours
                        "group_mm2hrxfp": "post_signature",  # cofrac_pncee
                        "group_mm2h6t12": "post_signature",  # commission_encaissee
                    }
                    target_stage = monday_group_to_stage.get(new_group_id)
                    if target_stage and target_stage != target_tunnel.get("current_stage"):
                        try:
                            advance_tunnel(target_tunnel["tunnel_id"], target_stage=target_stage,
                                          data={"source": "monday_webhook", "monday_item_id": item_id, "ts_event": data.get("event", {}).get("triggerTime")})
                            tunnel_synced = {"tunnel_id": target_tunnel["tunnel_id"], "stage": target_stage}
                        except Exception:
                            pass
        except Exception:
            pass

        return jsonify({"ok": True, "processed": True, "tunnel_synced": tunnel_synced})
