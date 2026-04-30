"""
Persistance des dossiers CEE — fichier JSON par dossier (file-based, zéro dépendance DB).

Chaque dossier a un UUID stable → URL retrouvable demain ("même lien" Jimmy).
Stockage : dossiers_data/<uuid>.json
Index    : dossiers_data/_index.json (cache liste pour /dossiers GET)

Endpoints :
  POST   /dossiers                  → crée dossier (retourne ID + URL)
  GET    /dossiers                  → liste tous (filtres : statut, client, date)
  GET    /dossiers/<id>             → récupère dossier complet
  PUT    /dossiers/<id>             → met à jour
  DELETE /dossiers/<id>             → archive (soft-delete)
  POST   /dossiers/<id>/recalculer  → force recalcul après modif
  GET    /dossiers/synthese         → dashboard mandataire (totaux primes/marges/commissions)
  GET    /dossiers/<id>/lien        → URL stable + token signé pour partage
"""

from __future__ import annotations

import json
import uuid
import hmac
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from flask import jsonify, request, Response

# V37.1 P2 — Persistance Fly volume : si CEE_DATA_DIR est set (volume monté en prod), on l'utilise ;
# sinon on retombe sur le path local (dev). Migration auto au boot si volume vide.
def _resolve_data_dir(subdir: str) -> Path:
    base = os.environ.get("CEE_DATA_DIR")
    target = Path(base) / subdir if base else Path(__file__).parent / subdir
    target.mkdir(parents=True, exist_ok=True)
    # Migration one-shot : si on est passé sur volume mais qu'il est vide ET que le path local existe avec des données → recopier
    if base:
        local = Path(__file__).parent / subdir
        if local.exists() and local != target and not any(target.glob("*.json")):
            for f in local.glob("*.json"):
                try:
                    (target / f.name).write_bytes(f.read_bytes())
                except Exception:
                    pass
    return target


DOSSIERS_DIR = _resolve_data_dir("dossiers_data")
INDEX_FILE = DOSSIERS_DIR / "_index.json"


def _secret() -> str:
    # V37.1 sécu : pas de fallback faible. En prod, échoue clairement plutôt que de signer avec un secret prévisible.
    s = os.environ.get("CEE_DOSSIERS_SECRET") or os.environ.get("CEE_JWT_SECRET") or ""
    weak = (not s) or len(s) < 32 or any(w in s.lower() for w in ("dev", "test", "change", "secret", "default", "qwerty"))
    if weak:
        if os.environ.get("CEE_ENV", "dev") == "prod":
            raise RuntimeError("[SÉCU] CEE_DOSSIERS_SECRET ou CEE_JWT_SECRET requis (>= 32 chars, pas de marqueur faible) en prod")
        return "DEV-ONLY-NOT-FOR-PROD-" + (s or "no-secret")
    return s


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _path(dossier_id: str) -> Path:
    return DOSSIERS_DIR / f"{dossier_id}.json"


def _load(dossier_id: str) -> dict | None:
    p = _path(dossier_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save(dossier_id: str, data: dict) -> None:
    _path(dossier_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _refresh_index()


def _refresh_index() -> None:
    """Reconstruit l'index léger pour listing rapide."""
    entries = []
    for p in DOSSIERS_DIR.glob("*.json"):
        if p.name.startswith("_"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            entries.append({
                "id": d.get("id"),
                "client_raison_sociale": (d.get("client") or {}).get("raison_sociale", ""),
                "client_siret": (d.get("client") or {}).get("siret", ""),
                "operation_fiche": (d.get("operation") or {}).get("fiche", ""),
                "operation_surface_m2": (d.get("operation") or {}).get("surface_m2", 0),
                "operation_chantier": (d.get("operation") or {}).get("nom_chantier", ""),
                "statut": d.get("statut", "brouillon"),
                "prime_obligé_eur": (d.get("calcul") or {}).get("prime_obligé_eur", 0),
                "commission_jimmy_eur": (d.get("calcul") or {}).get("commission_jimmy_eur"),
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
            })
        except Exception:
            continue
    INDEX_FILE.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
                          encoding="utf-8")


def _read_index() -> list:
    if not INDEX_FILE.exists():
        _refresh_index()
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8")).get("entries", [])
    except Exception:
        return []


def _sign_token(dossier_id: str, vue: str = "client") -> str:
    """Token HMAC pour partager un lien lecture seule (vue verrouillée)."""
    payload = f"{dossier_id}|{vue}"
    sig = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{dossier_id}.{vue}.{sig}"


def _verify_token(token: str) -> tuple[str, str] | None:
    try:
        dossier_id, vue, sig = token.split(".")
    except ValueError:
        return None
    expected = hmac.new(_secret().encode(), f"{dossier_id}|{vue}".encode(),
                        hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(expected, sig):
        return None
    return dossier_id, vue


def _recalculer(dossier: dict) -> dict:
    """Recalcule le bloc `calcul` à partir des saisies actuelles."""
    from gisement_sirat import Site, calcul_gisement
    op = dossier.get("operation") or {}
    admin = dossier.get("admin") or {}
    if not op.get("surface_m2"):
        return {"error": "surface_m2 absente, recalcul impossible"}
    site = Site(
        nom=op.get("nom_chantier", ""), adresse=op.get("adresse_chantier", ""),
        cp=op.get("cp_chantier", ""), ville=op.get("ville_chantier", ""),
        zone=op.get("zone", "H1"), secteur=op.get("secteur", "sante"),
        surface_m2=float(op.get("surface_m2", 0)),
        fiche=op.get("fiche", "BAT-EN-103"),
        hauteur_vs_m=float(op.get("hauteur_vs_m", 2.0)),
        isolant=op.get("isolant", ""),
    )
    return calcul_gisement(
        site,
        coeff_override=op.get("coeff_cumac_override"),
        prix_cumac_override=op.get("prix_cumac_override"),
        prix_ht_m2_override=op.get("prix_travaux_ht_m2_override"),
        cout_reel_realisateur_eur=admin.get("cout_reel_realisateur_eur"),
        commission_pct_marge=admin.get("commission_pct_marge"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════

def register_dossiers_routes(app) -> None:

    # V37.3.40 — Gate JWT activé seulement si CEE_AUTH_REQUIRED=1.
    # No-op par défaut → zéro régression si Jimmy n'a pas activé la sécu.
    # Active : `fly secrets set CEE_AUTH_REQUIRED=1 --app cee-engine-v37`
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

    @app.route("/dossiers", methods=["POST"])
    @_gate
    def _create():
        """Crée un dossier. Body = mêmes champs que /documents/pack (client/operation/...)."""
        body = request.json or {}
        did = _new_id()
        now = _now_iso()
        dossier = {
            "id": did,
            "created_at": now,
            "updated_at": now,
            "statut": body.get("statut", "brouillon"),
            "client": body.get("client", {}),
            "operation": body.get("operation", {}),
            "emetteur": body.get("emetteur", {}),
            "dispositif": body.get("dispositif", {}),
            "admin": body.get("admin", {}),
            "vue_par_defaut": body.get("vue_par_defaut", "client"),
        }
        dossier["calcul"] = _recalculer(dossier)
        _save(did, dossier)
        return jsonify({
            "id": did,
            "url_interne": f"/dossiers/{did}",
            "url_pack": f"/dossiers/{did}/pack",
            "url_partage_client":  f"/dossiers/lien/{_sign_token(did, 'client')}",
            "url_partage_interne": f"/dossiers/lien/{_sign_token(did, 'interne')}",
            "calcul": dossier["calcul"],
        }), 201

    @app.route("/dossiers", methods=["GET"])
    @_gate
    def _list():
        entries = _read_index()
        # filtres
        statut = request.args.get("statut")
        if statut:
            entries = [e for e in entries if e.get("statut") == statut]
        siret = request.args.get("siret")
        if siret:
            entries = [e for e in entries if siret in (e.get("client_siret") or "")]
        return jsonify({"count": len(entries), "entries": entries})

    @app.route("/dossiers/<dossier_id>", methods=["GET"])
    @_gate
    def _get(dossier_id):
        d = _load(dossier_id)
        if d is None:
            return jsonify({"error": "dossier introuvable"}), 404
        return jsonify(d)

    @app.route("/dossiers/<dossier_id>", methods=["PUT"])
    @_gate
    def _update(dossier_id):
        d = _load(dossier_id)
        if d is None:
            return jsonify({"error": "dossier introuvable"}), 404
        body = request.json or {}
        for k in ("client", "operation", "emetteur", "dispositif", "admin", "statut", "vue_par_defaut"):
            if k in body:
                d[k] = body[k]
        d["updated_at"] = _now_iso()
        d["calcul"] = _recalculer(d)
        _save(dossier_id, d)
        return jsonify(d)

    @app.route("/dossiers/<dossier_id>", methods=["DELETE"])
    @_gate
    def _delete(dossier_id):
        d = _load(dossier_id)
        if d is None:
            return jsonify({"error": "dossier introuvable"}), 404
        d["statut"] = "archive"
        d["updated_at"] = _now_iso()
        _save(dossier_id, d)
        return jsonify({"ok": True, "id": dossier_id, "statut": "archive"})

    @app.route("/dossiers/<dossier_id>/recalculer", methods=["POST"])
    @_gate
    def _recalc(dossier_id):
        d = _load(dossier_id)
        if d is None:
            return jsonify({"error": "dossier introuvable"}), 404
        d["calcul"] = _recalculer(d)
        d["updated_at"] = _now_iso()
        _save(dossier_id, d)
        return jsonify({"id": dossier_id, "calcul": d["calcul"]})

    @app.route("/dossiers/<dossier_id>/pack", methods=["GET"])
    @_gate
    def _pack(dossier_id):
        """Renvoie les 4 docs HTML d'un dossier (vue=client par défaut, ?vue=interne pour mode vendeur)."""
        d = _load(dossier_id)
        if d is None:
            return jsonify({"error": "dossier introuvable"}), 404
        from documents_client import (
            ClientHeader, Operation, Emetteur, DispositifCEE, Admin,
            doc_gisement, doc_devis, doc_convention, doc_ah,
            _filter_calc_for_vue,
        )
        cli = ClientHeader(**{k: v for k, v in (d.get("client") or {}).items()
                              if k in ClientHeader.__annotations__})
        op = Operation(**{k: v for k, v in (d.get("operation") or {}).items()
                          if k in Operation.__annotations__})
        em = Emetteur(**{k: v for k, v in (d.get("emetteur") or {}).items()
                         if k in Emetteur.__annotations__})
        disp = DispositifCEE(**{k: v for k, v in (d.get("dispositif") or {}).items()
                                if k in DispositifCEE.__annotations__})
        admin = Admin(**{k: v for k, v in (d.get("admin") or {}).items()
                         if k in Admin.__annotations__})
        calc = d.get("calcul") or {}
        if "error" in calc:
            return jsonify({"error": calc["error"]}), 400
        vue = (request.args.get("vue") or d.get("vue_par_defaut") or "client").lower()
        if vue not in ("client", "interne"):
            vue = "client"
        devis_num = admin.devis_num or f"DE-{dossier_id[:6]}"
        return jsonify({
            "id": dossier_id,
            "vue": vue,
            "calcul": _filter_calc_for_vue(calc, vue),
            "documents": {
                "gisement_html":   doc_gisement(cli, op, em, disp, admin, calc, vue),
                "devis_html":      doc_devis(cli, op, em, disp, admin, calc, devis_num, vue),
                "convention_html": doc_convention(cli, op, em, disp, admin),
                "ah_html":         doc_ah(cli, op, em, disp, admin, calc, devis_num),
            },
        })

    @app.route("/dossiers/lien/<token>", methods=["GET"])
    def _shared_link(token):
        """Lien partageable (token HMAC) — rendu HTML lecture seule, vue verrouillée."""
        verified = _verify_token(token)
        if verified is None:
            return Response("Lien invalide ou altéré.", status=403, mimetype="text/plain")
        dossier_id, vue = verified
        d = _load(dossier_id)
        if d is None:
            return Response("Dossier introuvable.", status=404, mimetype="text/plain")
        # Render HTML standalone des 4 docs (onglets simples)
        from documents_client import (
            ClientHeader, Operation, Emetteur, DispositifCEE, Admin,
            doc_gisement, doc_devis, doc_convention, doc_ah,
        )
        cli = ClientHeader(**{k: v for k, v in (d.get("client") or {}).items() if k in ClientHeader.__annotations__})
        op = Operation(**{k: v for k, v in (d.get("operation") or {}).items() if k in Operation.__annotations__})
        em = Emetteur(**{k: v for k, v in (d.get("emetteur") or {}).items() if k in Emetteur.__annotations__})
        disp = DispositifCEE(**{k: v for k, v in (d.get("dispositif") or {}).items() if k in DispositifCEE.__annotations__})
        admin = Admin(**{k: v for k, v in (d.get("admin") or {}).items() if k in Admin.__annotations__})
        calc = d.get("calcul") or {}
        devis_num = admin.devis_num or f"DE-{dossier_id[:6]}"
        return _render_pack_with_tabs(dossier_id, vue, {
            "Gisement":   doc_gisement(cli, op, em, disp, admin, calc, vue),
            "Devis":      doc_devis(cli, op, em, disp, admin, calc, devis_num, vue),
            "Convention": doc_convention(cli, op, em, disp, admin),
            "AH":         doc_ah(cli, op, em, disp, admin, calc, devis_num),
        })

    @app.route("/dossiers/synthese", methods=["GET"])
    @_gate
    def _synthese():
        """Dashboard mandataire — totaux multi-dossiers."""
        entries = [e for e in _read_index() if e.get("statut") != "archive"]
        total_prime = sum((e.get("prime_obligé_eur") or 0) for e in entries)
        total_commission = sum((e.get("commission_jimmy_eur") or 0) for e in entries
                               if e.get("commission_jimmy_eur") is not None)
        nb_avec_commission = sum(1 for e in entries if e.get("commission_jimmy_eur") is not None)
        nb_sans_cout = sum(1 for e in entries if e.get("commission_jimmy_eur") is None)
        return jsonify({
            "nb_dossiers_actifs": len(entries),
            "prime_obligé_total_eur": round(total_prime, 2),
            "commission_jimmy_calculée_total_eur": round(total_commission, 2),
            "dossiers_avec_commission_calculée": nb_avec_commission,
            "dossiers_sans_coût_réel_saisi": nb_sans_cout,
            "par_statut": _aggregate_by(entries, "statut"),
            "par_fiche": _aggregate_by(entries, "operation_fiche"),
        })


def _aggregate_by(entries: list, key: str) -> dict:
    out = {}
    for e in entries:
        k = e.get(key) or "—"
        if k not in out:
            out[k] = {"count": 0, "prime_total": 0, "commission_total": 0}
        out[k]["count"] += 1
        out[k]["prime_total"] = round(out[k]["prime_total"] + (e.get("prime_obligé_eur") or 0), 2)
        out[k]["commission_total"] = round(out[k]["commission_total"]
                                          + (e.get("commission_jimmy_eur") or 0), 2)
    return out


def _render_pack_with_tabs(dossier_id: str, vue: str, docs: dict[str, str]) -> Response:
    """HTML standalone avec onglets pour les 4 docs + bouton imprimer."""
    import html
    tabs_btn = "".join(
        f'<button class="tab" onclick="showTab(\'tab-{i}\')">{html.escape(name)}</button>'
        for i, name in enumerate(docs.keys())
    )
    tabs_content = "".join(
        f'<div id="tab-{i}" class="tabc"><iframe srcdoc="{html.escape(content)}" '
        f'style="width:100%;height:80vh;border:1px solid #ccc;"></iframe></div>'
        for i, content in enumerate(docs.values())
    )
    page = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>Dossier {dossier_id} ({vue})</title>
<style>
body {{ font-family:-apple-system,Helvetica,Arial,sans-serif; margin:0; padding:14px; background:#f4f7fb; }}
header {{ display:flex; justify-content:space-between; align-items:center; padding:10px 16px;
          background:#1f4068; color:white; border-radius:6px; margin-bottom:14px; }}
header h1 {{ margin:0; font-size:18px; }}
.badge-vue {{ background:{"#b00" if vue == "interne" else "#08a"}; padding:4px 10px; border-radius:4px; font-size:12px; font-weight:bold; }}
.tabs {{ display:flex; gap:4px; margin-bottom:8px; }}
.tab {{ padding:8px 16px; border:none; background:#e8ecf3; cursor:pointer;
         border-radius:4px 4px 0 0; font-weight:600; }}
.tab:hover {{ background:#d0d7e2; }}
.tab.active {{ background:white; border-bottom:2px solid #1f4068; }}
.tabc {{ display:none; background:white; padding:8px; border-radius:0 4px 4px 4px; }}
.tabc.active {{ display:block; }}
button.action {{ padding:8px 14px; background:#1f4068; color:white; border:none; border-radius:4px;
                  cursor:pointer; margin-left:8px; }}
</style></head><body>
<header>
  <h1>Dossier <code>{dossier_id}</code></h1>
  <div>
    <span class="badge-vue">VUE {vue.upper()}</span>
    <button class="action" onclick="window.print()">🖨 Imprimer onglet actif</button>
  </div>
</header>
<div class="tabs">{tabs_btn}</div>
{tabs_content}
<script>
function showTab(id){{
  document.querySelectorAll('.tabc').forEach(e=>e.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(e=>e.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  event.target.classList.add('active');
}}
showTab('tab-0');
document.querySelector('.tab').classList.add('active');
</script>
</body></html>"""
    return Response(page, mimetype="text/html; charset=utf-8")
