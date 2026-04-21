"""
CEE Engine V37 P4.8 — Chat compagnon contextualisé multi-tours.

Utilise l'IA la plus disponible (CLAUDE > GEMINI > GROQ > KIMI > OPENAI)
selon les clés env présentes. Context-aware sur le diagnostic en cours.
Routage intelligent : questions techniques → CLAUDE, docs → GEMINI, etc.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.request

from flask import jsonify, request


def _pick_ai() -> str | None:
    """Choisir la 1ère IA disponible selon les env vars."""
    order = [
        ("claude",  "ANTHROPIC_API_KEY"),
        ("gemini",  "GEMINI_API_KEY"),
        ("groq",    "GROQ_API_KEY"),
        ("kimi",    "MOONSHOT_API_KEY"),
        ("openai",  "OPENAI_API_KEY"),
    ]
    for name, envvar in order:
        if os.environ.get(envvar):
            return name
    return None


def _route_by_topic(user_msg: str) -> str | None:
    """Heuristique simple : détecter le sujet pour router vers la bonne IA."""
    msg = user_msg.lower()
    if any(w in msg for w in ["calcul", "cumac", "prime", "kwhc", "coefficient", "fost", "vérifier"]):
        return "kimi" if os.environ.get("MOONSHOT_API_KEY") else None
    if any(w in msg for w in ["document", "dpe", "audit", "photo", "image", "facture"]):
        return "gemini" if os.environ.get("GEMINI_API_KEY") else None
    if any(w in msg for w in ["loi", "arrêté", "réglementation", "conformité", "rge", "cofrac", "pncee", "juridique"]):
        return "claude" if os.environ.get("ANTHROPIC_API_KEY") else None
    if any(w in msg for w in ["urgent", "rapide", "dès maintenant", "coup de pouce", "deadline"]):
        return "groq" if os.environ.get("GROQ_API_KEY") else None
    if any(w in msg for w in ["argumentaire", "pitch", "vendre", "convaincre", "email", "synthèse"]):
        return "openai" if os.environ.get("OPENAI_API_KEY") else None
    return None


SYSTEM_PROMPT = (
    "Tu es l'assistant CEE Engine V37 — expert CEE senior 15 ans d'expérience en France. "
    "Tu réponds aux questions de Jimmy (commercial CEE pro) ou de ses clients (DAF, BE). "
    "Langue : français. Ton : direct, précis, factuel. "
    "Tu as accès au contexte du diagnostic en cours : SIRET, gisements, prime estimée. "
    "Si tu ne sais pas : dis-le. Si une vérification juridique est nécessaire : oriente vers le PNCEE. "
    "Citations : Légifrance, DGEC, arrêtés précis (ex: arrêté 22/12/2014). "
    "Règles métier : 0% commission par défaut, MPR uniquement copro/bailleur/SCI, jamais d'invention sans source."
)


def _call_ai(which: str, user_msg: str, diag_context: dict, history: list) -> tuple[dict | None, str | None]:
    """Appelle l'IA choisie, renvoie (answer_dict, error)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    ctx_str = json.dumps(diag_context, ensure_ascii=False)[:3000]  # cap taille
    enriched_user = f"[CONTEXTE DIAGNOSTIC]\n{ctx_str}\n\n[QUESTION]\n{user_msg}"

    try:
        if which == "claude":
            body = {
                "model": "claude-sonnet-4-6",
                "max_tokens": 1500,
                "temperature": 0.2,
                "system": SYSTEM_PROMPT,
                "messages": history + [{"role": "user", "content": enriched_user}],
            }
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(body).encode(),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                raw = json.loads(resp.read())
            text = "".join(b.get("text", "") for b in raw.get("content", []) if b.get("type") == "text")
            return {"answer": text, "ia": "CLAUDE", "role": "conformité"}, None

        if which == "gemini":
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.5-flash:generateContent?key={os.environ['GEMINI_API_KEY']}"
            )
            # Reconstituer historique au format Gemini
            contents = []
            for h in history:
                contents.append({"role": "user" if h["role"] == "user" else "model", "parts": [{"text": h["content"]}]})
            contents.append({"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + enriched_user}]})
            body = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.2, "maxOutputTokens": 1500,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            }
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                raw = json.loads(resp.read())
            text = raw["candidates"][0]["content"]["parts"][0]["text"]
            return {"answer": text, "ia": "GEMINI", "role": "documents"}, None

        # GROQ / KIMI / OPENAI — tous compatibles OpenAI format
        endpoint_map = {
            "groq":   ("https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile", os.environ.get("GROQ_API_KEY")),
            "kimi":   ("https://api.moonshot.ai/v1/chat/completions", "kimi-k2-0711-preview", os.environ.get("MOONSHOT_API_KEY")),
            "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4o", os.environ.get("OPENAI_API_KEY")),
        }
        if which not in endpoint_map:
            return None, f"provider '{which}' inconnu"
        url, model, key = endpoint_map[which]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": enriched_user}]
        body = {"model": model, "messages": messages, "max_tokens": 1500, "temperature": 0.2}
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            raw = json.loads(resp.read())
        text = raw["choices"][0]["message"]["content"]
        return {"answer": text, "ia": which.upper(), "role": {"groq": "tactique", "kimi": "calculs", "openai": "commercial"}.get(which, "assistant")}, None

    except urllib.error.HTTPError as he:
        try:
            err = json.loads(he.read()).get("error", {})
            msg = err.get("message") if isinstance(err, dict) else str(err)
        except Exception:
            msg = f"HTTP {he.code}"
        return None, f"{which}: {msg}"
    except Exception as e:
        return None, str(e)


def register_chat_routes(app) -> None:
    @app.route("/ai/chat", methods=["POST"])
    def _chat():
        """
        Body JSON :
          {
            "message": "ma chaudière fioul est éligible à BAR-TH-104 ?",
            "history": [{"role":"user","content":"..."},{"role":"assistant","content":"..."}],
            "context": {"siret":"...", "ape":"...", "prime":0, "fiches":[...]},
            "preferred_ia": "auto|groq|gemini|claude|kimi|openai"
          }
        """
        data = request.json or {}
        msg = (data.get("message") or "").strip()
        if not msg:
            return jsonify({"error": "message requis"}), 400
        history = data.get("history") or []
        context = data.get("context") or {}
        preferred = data.get("preferred_ia", "auto")

        # Sélection IA
        if preferred == "auto":
            routed = _route_by_topic(msg)
            which = routed or _pick_ai()
        else:
            which = preferred if os.environ.get({
                "groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY",
                "claude": "ANTHROPIC_API_KEY", "kimi": "MOONSHOT_API_KEY",
                "openai": "OPENAI_API_KEY",
            }.get(preferred, "___")) else _pick_ai()

        if not which:
            return jsonify({
                "error": "Aucune IA configurée côté serveur. Activez au moins une clé (ANTHROPIC/GEMINI/GROQ/MOONSHOT/OPENAI).",
                "status": "no_ia_available",
            }), 503

        answer, err = _call_ai(which, msg, context, history)
        if err:
            return jsonify({"error": err, "ia_attempted": which}), 502
        return jsonify(answer)
