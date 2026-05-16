"""Tests pytest CEE Engine V37 — couverture des 34+ endpoints + edge cases.

Usage :
    cd /Users/azert/CEE_ENGINE
    pip install -r requirements-dev.txt  # pytest, pytest-timeout
    pytest tests/ -v                      # tous les tests
    pytest tests/ -v -m "not network"     # sans appels externes

Convention :
- @pytest.mark.network   → nécessite internet (API gouv, IGN, ADEME)
- @pytest.mark.ai        → nécessite une clé IA valide (env var)
- pas de marker          → peut tourner sans internet
"""
import json
import os
import sys
import pytest

# Import l'app Flask sans lancer un serveur HTTP
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api import app  # noqa: E402


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════════
# CORE — pas d'internet nécessaire (endpoints qui tapent dans la config locale)
# ═══════════════════════════════════════════════════════════════════════════

class TestCore:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        d = r.get_json()
        assert d["status"] == "ok"
        assert d["fiches"] >= 200, "au moins 200 fiches catalogue"
        assert d["version"].startswith("V"), "version commence par V"
        # V39.0 — brand Cumac exposé pour usage externe
        assert d.get("brand") == "Cumac"

    def test_cumac_track_v39(self, client):
        """V39.0 — /api/track accepte n'importe quel JSON, répond 204, fail-silent.

        L'endpoint anonymise l'IP /16 et écrit en JSONL append. On vérifie juste
        qu'il ne plante jamais (fail-silent même sur JSON cassé).
        """
        # Cas nominal
        r = client.post("/api/track", json={
            "event": "test_pageview",
            "props": {"v": "39.0"},
            "session": "sid_pytest",
        })
        assert r.status_code == 204
        # Cas dégradé : body vide → toujours 204 (fail-silent)
        r2 = client.post("/api/track", data="", content_type="application/json")
        assert r2.status_code == 204
        # Cas dégradé : JSON malformé → toujours 204
        r3 = client.post("/api/track", data="{not json", content_type="application/json")
        assert r3.status_code == 204

    def test_deadlines(self, client):
        r = client.get("/deadlines")
        assert r.status_code == 200
        assert isinstance(r.get_json(), dict)

    def test_acheteurs_liste(self, client):
        r = client.get("/acheteurs")
        assert r.status_code == 200
        d = r.get_json()
        assert len(d) >= 5, "au moins 5 acheteurs CEE modélisés"

    def test_regulatory_changelog(self, client):
        r = client.get("/regulatory/changelog?limit=5")
        assert r.status_code == 200
        d = r.get_json()
        assert "changelog" in d
        assert isinstance(d["changelog"], list)

    def test_regulatory_intelligence_5_lentilles(self, client):
        r = client.get("/regulatory/intelligence?sectors=BAT&zone=H1&surface=500")
        assert r.status_code == 200
        d = r.get_json()
        assert "lentilles" in d
        for lens in ["optimiste", "pessimiste", "opportuniste"]:
            assert lens in d["lentilles"], f"lentille {lens} manquante"
            assert 0 <= d["lentilles"][lens]["score"] <= 100
        assert "predictif" in d
        assert "proactif" in d
        assert "prixActuel" in d

    def test_regulatory_dashboard(self, client):
        r = client.get("/regulatory")
        assert r.status_code == 200
        d = r.get_json()
        assert "alertes" in d
        assert "prixMWhc" in d


class TestRegles:
    def test_regle_75pct_dominant(self, client):
        r = client.post("/regles/75pct", json={
            "secteurs_surfaces": {"BAT": 800, "BAR": 200}
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["secteur_applicable"] == "BAT"
        assert d["pourcentage_dominant"] == 80.0
        assert d["regle"] == "75%"

    def test_regle_75pct_plus_defavorable(self, client):
        r = client.post("/regles/75pct", json={
            "secteurs_surfaces": {"BAT": 500, "BAR": 400, "IND": 100}
        })
        assert r.status_code == 200
        assert r.get_json()["regle"] == "plus_defavorable"

    def test_tolerance_mixte_tertiaire(self, client):
        r = client.post("/regles/tolerance-mixte", json={
            "surface_tertiaire": 600, "surface_residentielle": 200
        })
        assert r.status_code == 200
        assert r.get_json()["secteur_applicable"] == "BAT"

    def test_tolerance_mixte_residentiel(self, client):
        r = client.post("/regles/tolerance-mixte", json={
            "surface_tertiaire": 100, "surface_residentielle": 600
        })
        assert r.status_code == 200
        assert r.get_json()["secteur_applicable"] == "BAR"


class TestMoteurCalcul:
    def test_expert_calcul_prime(self, client):
        r = client.post("/expert", json={
            "naf": "68.20A", "surface": 500, "departement": "75", "energie": "gaz"
        })
        assert r.status_code == 200
        d = r.get_json()
        assert "oracle" in d
        assert d["oracle"]["globaux"]["nb_fiches"] > 0

    def test_expert_commission_zero_par_defaut(self, client):
        """Règle Jimmy : 0% commission par défaut — prime brute = prime nette."""
        r = client.post("/expert", json={
            "naf": "68.20A", "surface": 500, "departement": "75", "energie": "gaz"
        })
        g = r.get_json()["oracle"]["globaux"]
        brute = g.get("total_prime_brute", 0)
        nette = g.get("total_prime_nette", 0)
        assert abs(brute - nette) < 1.0, "commission 0% → brute == nette"

    def test_expert_oracle_pur(self, client):
        r = client.post("/expert/oracle", json={
            "departement": "75", "surface": 500, "quantite": 20
        })
        assert r.status_code == 200
        d = r.get_json()
        assert "pack" in d and "globaux" in d

    def test_recalcul(self, client):
        r = client.post("/recalcul", json={
            "naf": "68.20A", "departement": "75",
            "reponses": {"surface": 500, "puissance": 100}
        })
        assert r.status_code == 200
        assert r.get_json()["source"] == "recalcul_oracle"

    def test_predictions(self, client):
        r = client.post("/predictions", json={
            "question_id": "surface", "naf": "68.20A", "surface": 500
        })
        assert r.status_code == 200
        assert "predictions" in r.get_json()


class TestMultisite:
    def test_multisite_strategie(self, client):
        r = client.post("/multisite/strategie", json={
            "nb_sites": 5, "surface_par_site": 800, "departement": "75"
        })
        assert r.status_code == 200
        d = r.get_json()
        assert "surface_totale" in d

    def test_multisite_optimiser(self, client):
        r = client.post("/multisite/optimiser", json={
            "profil": "bureaux", "nb_sites": 3, "surface_moyenne": 800,
            "departement": "75"
        })
        assert r.status_code == 200

    def test_closing(self, client):
        r = client.post("/closing", json={"departement": "75", "surface": 800})
        assert r.status_code == 200
        d = r.get_json()
        assert "pitch_client" in d or "objections" in d


class TestNegociation:
    def test_comparer_acheteurs_post(self, client):
        r = client.post("/negociation", json={
            "volume_kwhc": 2_000_000, "secteurs": ["BAT"]
        })
        assert r.status_code == 200
        d = r.get_json()
        assert "recommandation" in d
        assert "scenarios" in d
        assert len(d["scenarios"]) >= 5

    def test_negociation_get_comparatif(self, client):
        r = client.get("/negociation/comparatif?kwhc=500000&secteurs=BAT")
        assert r.status_code == 200


class TestValidation:
    def test_validation_complete(self, client):
        r = client.post("/validation/complete", json={
            "siret": "44288422700012", "surface": 500,
            "fiches": ["BAT-EQ-127"]
        })
        assert r.status_code == 200
        d = r.get_json()
        assert "est_valide" in d
        assert "erreurs" in d


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES — inputs invalides, bornes
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_analyse_siret_vide(self, client):
        r = client.post("/analyse", json={})
        assert r.status_code == 400

    def test_analyse_siret_bidon(self, client):
        r = client.post("/analyse", json={"siret": "00000000000000"})
        # Peut être 404 (introuvable) ou 200 avec fallback selon ODS
        assert r.status_code in (200, 404)

    def test_expert_params_manquants(self, client):
        r = client.post("/expert", json={"naf": "68.20A"})
        assert r.status_code == 400

    def test_cadastre_lat_lon_manquants(self, client):
        r = client.get("/cadastre")
        assert r.status_code == 400

    def test_cadastre_coords_invalides(self, client):
        r = client.get("/cadastre?lat=abc&lon=xyz")
        assert r.status_code == 400

    def test_batiment_sans_coords(self, client):
        r = client.get("/batiment")
        assert r.status_code == 400

    def test_etablissements_siren_court(self, client):
        r = client.get("/etablissements/12345")
        assert r.status_code == 400

    def test_proxy_url_manquante(self, client):
        r = client.get("/proxy")
        assert r.status_code == 400

    def test_proxy_domaine_non_autorise(self, client):
        r = client.get("/proxy?url=https%3A%2F%2Fevil.example.com%2F")
        assert r.status_code == 403

    def test_dpe_query_manquante(self, client):
        r = client.get("/dpe")
        assert r.status_code == 400

    def test_regulatory_intelligence_sans_context(self, client):
        """Doit répondre même sans contexte (valeurs defaults)."""
        r = client.get("/regulatory/intelligence")
        assert r.status_code == 200
        d = r.get_json()
        assert "lentilles" in d


# ═══════════════════════════════════════════════════════════════════════════
# IA — sans clé doit renvoyer 400 (pas 500)
# ═══════════════════════════════════════════════════════════════════════════

class TestAIEndpointsSecurity:
    """V37 SEC — Sans clé, chaque endpoint IA doit refuser proprement (400)."""

    def test_keys_status_structure(self, client):
        r = client.get("/ai/keys/status")
        assert r.status_code == 200
        d = r.get_json()
        # Doit renvoyer uniquement des booléens (pas de valeurs de clés)
        for k in ["groq", "gemini", "claude", "kimi", "openai"]:
            assert k in d
            assert isinstance(d[k], bool), f"{k} doit être un booléen"

    def test_groq_sans_cle(self, client):
        r = client.post("/ai/groq", json={"messages": []})
        assert r.status_code in (400, 502)

    def test_gemini_sans_cle(self, client):
        r = client.post("/ai/gemini", json={})
        assert r.status_code in (400, 502)

    def test_claude_sans_cle(self, client):
        r = client.post("/ai/claude", json={"messages": [{"role": "user", "content": "x"}]})
        assert r.status_code in (200, 400, 502)

    def test_kimi_sans_cle(self, client):
        r = client.post("/ai/kimi", json={"messages": [{"role": "user", "content": "x"}]})
        assert r.status_code in (200, 400, 502)

    def test_openai_sans_cle(self, client):
        r = client.post("/ai/openai", json={"messages": [{"role": "user", "content": "x"}]})
        assert r.status_code in (200, 400, 502)

    def test_gpt_alias(self, client):
        r = client.post("/ai/gpt", json={"messages": [{"role": "user", "content": "x"}]})
        assert r.status_code in (400, 200, 502)


# ═══════════════════════════════════════════════════════════════════════════
# NETWORK — nécessitent internet (API gouv / IGN / ADEME)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.network
class TestOpenData:
    def test_siret_search_google(self, client):
        r = client.get("/siret/search?q=44306184100047&per_page=1")
        assert r.status_code == 200
        d = r.get_json()
        assert d["results"]
        assert "GOOGLE" in d["results"][0]["nom_complet"].upper()

    def test_siret_patch_branche(self, client):
        """FIX V37 : SIRET branche Google doit renvoyer son adresse, pas celle du siège."""
        r = client.get("/siret/search?q=44306184100070&per_page=1")
        assert r.status_code == 200
        d = r.get_json()
        if d.get("results"):
            siege = d["results"][0]["siege"]
            # Le siège retourné doit être patché avec la branche
            assert siege["siret"] == "44306184100070" or d["results"][0].get("_siret_branch_patch")

    def test_siret_avec_espaces(self, client):
        r = client.get("/siret/search?q=443%20061%20841%2000047&per_page=1")
        assert r.status_code == 200

    def test_etablissements_filtre_actifs(self, client):
        r = client.get("/etablissements/443061841")
        assert r.status_code == 200
        d = r.get_json()
        assert "_filtre" in d
        assert all(e["etat_administratif"] == "A" for e in d["etablissements"])

    def test_cadastre_paris(self, client):
        r = client.get("/cadastre?lat=48.876958&lon=2.330008")
        assert r.status_code == 200
        d = r.get_json()
        assert d["found"] is True
        assert d["reference_cadastrale"]

    def test_cadastre_ocean(self, client):
        r = client.get("/cadastre?lat=0&lon=0")
        assert r.status_code == 200
        assert r.get_json()["found"] is False

    def test_batiment_eiffel(self, client):
        """BD TOPO doit trouver la Tour Eiffel (FIX V37 : bbox CRS correct)."""
        r = client.get("/batiment?lat=48.8584&lon=2.2945")
        assert r.status_code == 200
        d = r.get_json()
        assert d["count"] > 0
        assert d["best"]["surface_sol_m2"] > 100

    def test_dpe_recherche(self, client):
        r = client.get("/dpe?q=rue+de+rivoli+paris+75001")
        # Peut retourner 0 résultats mais pas d'erreur
        assert r.status_code == 200


class TestPhase3:
    """V37 P3 — auth, RAG local, intégrations, vision IA."""

    # ── P3.1 PWA ──
    def test_pwa_manifest_served(self, client):
        r = client.get("/manifest.json")
        assert r.status_code == 200
        d = r.get_json()
        assert d["name"]
        assert "icons" in d

    def test_pwa_sw_served(self, client):
        r = client.get("/sw.js")
        assert r.status_code == 200
        assert b"cee-engine" in r.data.lower()

    # ── P3.2 Vision IA ──
    def test_vision_sans_image(self, client):
        r = client.post("/ai/vision", json={"mode": "equipement"})
        # Sans clé Gemini env, on a 400 sur l'auth; avec clé mais sans image, 400 aussi
        assert r.status_code == 400

    def test_vision_mode_invalide(self, client):
        r = client.post("/ai/vision", json={
            "mode": "truc", "image_base64": "xxx"
        })
        # mode invalide → 400 si env GEMINI_API_KEY définie, sinon 400 auth
        assert r.status_code in (400,)

    # ── P3.3 Auth ──
    def test_auth_status(self, client):
        r = client.get("/auth/status")
        assert r.status_code == 200
        d = r.get_json()
        assert "auth_enabled" in d
        assert "users_count" in d

    def test_auth_login_sans_credentials(self, client):
        r = client.post("/auth/login", json={})
        # 400 si champs manquants, 500 si JWT_SECRET absent
        assert r.status_code in (400, 500)

    def test_auth_me_sans_token(self, client):
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_auth_protected_route_401(self, client):
        """/auth/me sans token → 401."""
        r = client.get("/auth/me", headers={"Authorization": "Bearer invalid"})
        assert r.status_code == 401

    # ── P3.4 RAG ──
    def test_rag_search_pac(self, client):
        r = client.get("/rag/search?q=pompe%20%C3%A0%20chaleur%20tertiaire&top_k=5")
        assert r.status_code == 200
        d = r.get_json()
        assert "results" in d
        # Au moins un BAT-TH doit remonter pour "pompe à chaleur tertiaire"
        refs = [x["ref"] for x in d["results"]]
        assert any(ref.startswith("BAT-TH") or ref.startswith("BAR-TH") for ref in refs)

    def test_rag_search_isolation(self, client):
        r = client.get("/rag/search?q=isolation%20combles%20toiture&top_k=3")
        assert r.status_code == 200
        refs = [x["ref"] for x in r.get_json()["results"]]
        assert any("EN" in ref for ref in refs), f"devrait remonter fiches EN (enveloppe) : {refs}"

    def test_rag_query_vide(self, client):
        r = client.get("/rag/search?q=")
        assert r.status_code == 400

    def test_rag_reindex(self, client):
        r = client.post("/rag/reindex")
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert d["n_docs"] > 200

    # ── P3.5 Intégrations ──
    def test_integrations_status(self, client):
        r = client.get("/integrations/status")
        assert r.status_code == 200
        d = r.get_json()
        for svc in ["yousign", "erp_webhook", "atee_scraper", "jwt_auth"]:
            assert svc in d

    def test_yousign_non_active_sans_cle(self, client):
        r = client.post("/signature/request", json={
            "signer_email": "x@y.fr", "signer_name": "x",
            "document_base64": "xx", "document_name": "test.pdf"
        })
        # 503 si YOUSIGN_API_KEY absente (stub)
        assert r.status_code in (503, 400)

    def test_erp_webhook_non_active(self, client):
        r = client.post("/webhook/erp", json={"siret": "12345678901234"})
        # 503 si ERP_WEBHOOK_URL absente
        assert r.status_code in (503, 400)


class TestPhase4:
    """V37 P4 — PNCEE scoring + export, OpenAPI, portail, chat."""

    def test_pncee_score_valide(self, client):
        r = client.post("/pncee/score", json={
            "siret": "44288422700012", "surface": 500,
            "fiches": ["BAT-TH-127"], "rge_installateur": True,
            "dpe_date": "2023-05-12",
        })
        assert r.status_code == 200
        d = r.get_json()
        assert 0 <= d["score"] <= 100
        assert d["verdict"] in ("GO", "PRUDENCE", "STOP")

    def test_pncee_score_sans_rge(self, client):
        r = client.post("/pncee/score", json={
            "siret": "44288422700012", "surface": 500,
            "fiches": ["BAT-TH-127"], "rge_installateur": False,
        })
        d = r.get_json()
        assert any("RGE" in b for b in d["blockers"])

    def test_pncee_score_siret_invalide(self, client):
        r = client.post("/pncee/score", json={
            "siret": "123", "fiches": ["BAT-TH-127"],
        })
        assert any("SIRET" in b for b in r.get_json()["blockers"])

    def test_pncee_score_sans_fiches(self, client):
        r = client.post("/pncee/score", json={"siret": "44288422700012"})
        assert r.status_code == 400

    def test_export_pncee_xml(self, client):
        r = client.post("/export/pncee?format=xml", json={
            "siret": "44288422700012", "raison_sociale": "TEST",
            "operations": [{"ref": "BAT-TH-127", "nom": "PAC", "volume_kwhc": 100000, "prime_eur": 1000}],
        })
        assert r.status_code == 200
        assert r.content_type.startswith("application/xml")
        assert b"BordereauCEE" in r.data

    def test_export_pncee_csv(self, client):
        r = client.post("/export/pncee?format=csv", json={
            "siret": "44288422700012",
            "operations": [{"ref": "BAT-TH-127", "volume_kwhc": 100000}],
        })
        assert r.status_code == 200
        assert "text/csv" in r.content_type

    def test_export_pncee_sans_operations(self, client):
        r = client.post("/export/pncee", json={"siret": "12345"})
        assert r.status_code == 400

    def test_openapi_spec(self, client):
        r = client.get("/api/openapi.json")
        assert r.status_code == 200
        d = r.get_json()
        assert d["openapi"].startswith("3.")
        assert len(d["paths"]) >= 40

    def test_swagger_ui(self, client):
        r = client.get("/api/docs")
        assert r.status_code == 200
        assert b"swagger-ui" in r.data.lower()

    def test_portail_generate(self, client):
        r = client.post("/portail/generate", json={
            "siret": "44288422700012", "raison_sociale": "TEST",
            "operations": [{"ref": "BAT-TH-127", "prime_eur": 10000}],
        })
        assert r.status_code == 200
        assert "token" in r.get_json()

    def test_portail_view_then_invalid(self, client):
        gen = client.post("/portail/generate", json={
            "siret": "44288422700012", "raison_sociale": "TEST",
            "operations": [{"ref": "BAT-TH-127", "prime_eur": 10000}],
        })
        token = gen.get_json()["token"]
        r = client.get(f"/portail/{token}")
        assert r.status_code == 200
        assert b"TEST" in r.data
        r2 = client.get("/portail/bidon.invalid")
        assert r2.status_code == 404

    def test_chat_sans_ia(self, client):
        r = client.post("/ai/chat", json={"message": "test"})
        # 503 si aucune clé IA env, sinon 200
        assert r.status_code in (503, 200)

    def test_chat_message_vide(self, client):
        r = client.post("/ai/chat", json={"message": ""})
        assert r.status_code == 400


class TestConformite:
    """V37 P5 — Système de conformité (équivalent Tessi fonctionnel)."""

    def test_regles_listees(self, client):
        r = client.get("/conformite/regles")
        assert r.status_code == 200
        d = r.get_json()
        assert d["nb_regles"] >= 30
        assert len(d["categories"]) >= 10
        # Chaque règle a id, sev, check, desc, reference
        for regle in d["regles"]:
            assert all(k in regle for k in ["id", "sev", "check", "desc", "reference"])

    def test_check_dossier_parfait(self, client):
        r = client.post("/conformite/check", json={
            "siret": "44288422700012", "raison_sociale": "SCI PLB",
            "adresse": "Test", "cp": "05250",
            "surface": 500, "fiches": ["BAT-EN-101"],
            "rge_installateur": True, "rge_qualification": "Qualibat",
            "date_engagement": "2026-03-15",
            "cout_travaux_ht": 40000, "devis_detaille": True,
            "ah_signee": True, "mandat_signe": True,
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["rapport"]["verdict"] in ("CONFORME", "CONFORME_AVEC_RESERVES")
        assert d["rapport"]["nb_bloquants"] == 0
        assert "content_sha256" in d["horodatage"]
        assert "signature_hmac_sha256" in d["horodatage"]

    def test_check_dossier_defectueux(self, client):
        r = client.post("/conformite/check", json={
            "siret": "INVALIDE", "fiches": [], "surface": 0
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["rapport"]["verdict"] == "NON_CONFORME"
        assert d["rapport"]["nb_bloquants"] >= 3

    def test_check_non_cumul_detecte(self, client):
        r = client.post("/conformite/check", json={
            "siret": "44288422700012",
            "fiches": ["BAR-TH-104", "BAR-TH-113"],  # mutuellement exclusives
            "rge_installateur": True, "surface": 500,
            "date_engagement": "2026-03-15",
        })
        d = r.get_json()
        has_non_cumul = any("non-cumul" in x["detail"].lower() for x in d["rapport"]["resultats"])
        assert has_non_cumul

    def test_archivage_worm_chainage(self, client):
        # Archiver 2 dossiers
        r1 = client.post("/conformite/archive", json={
            "siret": "11111111111111", "raison_sociale": "A",
            "fiches": ["BAT-EN-101"], "rge_installateur": True,
            "surface": 100, "date_engagement": "2026-01-01"
        })
        r2 = client.post("/conformite/archive", json={
            "siret": "22222222222222", "raison_sociale": "B",
            "fiches": ["BAT-EN-102"], "rge_installateur": True,
            "surface": 200, "date_engagement": "2026-02-01"
        })
        assert r1.status_code == 200 and r2.status_code == 200
        # Vérifier intégrité de la chaîne
        v = client.get("/conformite/verifier-integrite")
        assert v.status_code == 200
        d = v.get_json()
        assert d["ok"] is True
        assert d["count"] >= 2
        assert len(d["errors"]) == 0

    def test_journal_audit(self, client):
        # Tracer une action puis lire le journal
        client.post("/conformite/check", json={"siret": "33333333333333"})
        r = client.get("/conformite/journal?limit=5")
        assert r.status_code == 200
        entries = r.get_json()["entries"]
        assert len(entries) > 0
        assert all("ts" in e and "action" in e and "details" in e for e in entries)

    def test_rapport_texte(self, client):
        r = client.post("/conformite/rapport?format=text", json={
            "siret": "44288422700012", "raison_sociale": "TEST",
            "fiches": ["BAT-EN-101"], "rge_installateur": True,
            "surface": 500, "date_engagement": "2026-03-15"
        })
        assert r.status_code == 200
        body = r.data.decode()
        assert "RAPPORT DE CONFORMITÉ" in body
        assert "HORODATAGE CRYPTOGRAPHIQUE" in body
        assert "SHA-256" in body


class TestStatus:
    """V37 P2.3 — page /status HTML."""

    def test_status_dashboard_html(self, client):
        r = client.get("/status")
        assert r.status_code == 200
        assert r.content_type.startswith("text/html")
        body = r.data.decode()
        assert "CEE Engine V37" in body
        # Au moins une source doit apparaître
        assert "IGN Cadastre" in body or "ADEME" in body


# ═══════════════════════════════════════════════════════════════════════════
# V37 P7–P11 — Post-signature, Prospection, Analytics, Fidélisation, Formation
# ═══════════════════════════════════════════════════════════════════════════

class TestPostSignature:
    _INIT_BODY = {
        "dossier_id": "TEST-001",
        "fiches": ["BAT-TH-127"],
        "date_signature": "2026-04-01",
        "installateur": "ACME",
        "delegataire": "EDF",
    }

    def test_init(self, client):
        r = client.post("/post-signature/init", json=self._INIT_BODY)
        assert r.status_code == 200
        d = r.get_json()
        assert d["dossier_id"] == "TEST-001"

    def test_get_etat(self, client):
        client.post("/post-signature/init", json=self._INIT_BODY)
        r2 = client.get("/post-signature/TEST-001")
        assert r2.status_code == 200

    def test_marquer_etape(self, client):
        client.post("/post-signature/init", json=self._INIT_BODY)
        r2 = client.put("/post-signature/TEST-001/etape/travaux_planifies", json={"notes": "ok"})
        assert r2.status_code == 200

    def test_alertes(self, client):
        client.post("/post-signature/init", json=self._INIT_BODY)
        r2 = client.get("/post-signature/TEST-001/alertes")
        assert r2.status_code == 200

    def test_dashboard(self, client):
        r = client.get("/post-signature/dashboard")
        assert r.status_code == 200


@pytest.mark.network
class TestProspection:
    @pytest.mark.timeout(10)
    def test_score_lead(self, client):
        r = client.get("/prospection/score-lead/40039525700043")
        assert r.status_code in (200, 404)  # 404 si API gouv rate-limited
        if r.status_code == 200:
            d = r.get_json()
            assert 0 <= d["score"] <= 100

    def test_score_lead_siret_invalide(self, client):
        r = client.get("/prospection/score-lead/123")
        # L'endpoint accepte tout SIRET mais retourne un score bas pour les invalides
        assert r.status_code in (200, 400, 404)
        if r.status_code == 200:
            assert r.get_json()["score"] <= 50


class TestAnalytics:
    def test_pipeline(self, client):
        r = client.get("/analytics/pipeline")
        assert r.status_code == 200

    def test_performance(self, client):
        r = client.get("/analytics/performance")
        assert r.status_code == 200

    def test_forecast(self, client):
        r = client.get("/analytics/forecast")
        assert r.status_code == 200

    def test_activite(self, client):
        r = client.get("/analytics/activite")
        assert r.status_code == 200


class TestFidelisation:
    def test_opportunites(self, client):
        r = client.get("/fidelisation/40039525700043")
        assert r.status_code == 200


class TestFormation:
    def test_modules(self, client):
        r = client.get("/formation/modules")
        assert r.status_code == 200
        d = r.get_json()
        assert len(d["modules"]) >= 5

    def test_module_detail(self, client):
        r = client.get("/formation/module/1")
        assert r.status_code == 200
        d = r.get_json()
        assert len(d.get("questions", [])) > 0

    def test_evaluer(self, client):
        # Récupérer les questions du module 1 pour construire des réponses
        mod = client.get("/formation/module/1").get_json()
        reponses = {str(i): "a" for i in range(len(mod.get("questions", [])))}
        r = client.post("/formation/evaluer", json={
            "module_id": 1, "reponses": reponses,
        })
        assert r.status_code == 200
        assert "score" in r.get_json()

    def test_module_inexistant(self, client):
        r = client.get("/formation/module/99")
        assert r.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
