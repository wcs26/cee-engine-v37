"""
DOSSIER_PROFILE — Gestion du profil opérateur (Slide 0 V40)

Persiste les paramètres business config-once du vendeur :
  - Entreprise réalisant l'ouvrage (apporteur RGE)
  - Maître d'œuvre / COFRAC vérificateur / Délégataire oblige CEE
  - Prix rachat cumac (classique + précarité)
  - % commission apporteur d'affaires + % vendeur
  - % marge opérateur
  - Templates docs (convention/AH/mandat/devis)

Storage :
  - JSON file ~/.cee_engine/dossier_profile.json (fallback)
  - Override par user JWT (futur)
"""
import os
import json

PROFILE_DIR = os.path.expanduser("~/.cee_engine")
PROFILE_FILE = os.path.join(PROFILE_DIR, "dossier_profile.json")

DEFAULT_PROFILE = {
    "version": "V40.0",
    "operateur": {
        "raison_sociale": "",
        "siret": "",
        "rge_qualibat": "",
        "adresse": "",
        "tel": "",
        "email": "",
    },
    "maitre_oeuvre": {
        "raison_sociale": "",
        "siret": "",
        "contact": "",
    },
    "cofrac": {
        "raison_sociale": "",
        "siret": "",
        "accreditation": "",
    },
    "delegataire": {
        "raison_sociale": "",
        "siret": "",
        "ref_pncee": "",
    },
    "pricing": {
        "prix_cumac_eur_mwh_classique": 8.78,
        "prix_cumac_eur_mwh_precarite": 16.40,
        "pct_apporteur_affaires": 5.0,
        "pct_vendeur": 8.0,
        "pct_marge_operateur": 15.0,
    },
    "templates_actifs": {
        "convention_partenariat": True,
        "attestation_honneur": True,
        "mandat_delegataire": True,
        "devis_prerempli": True,
    },
}


def load_profile():
    """Charge le profil (fallback default si absent)."""
    if not os.path.exists(PROFILE_FILE):
        return dict(DEFAULT_PROFILE)
    try:
        with open(PROFILE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        # Merge avec defaults pour les nouvelles clés
        merged = dict(DEFAULT_PROFILE)
        _deep_merge(merged, data)
        return merged
    except Exception:
        return dict(DEFAULT_PROFILE)


def save_profile(profile):
    """Persiste le profil sur disque."""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    merged = dict(DEFAULT_PROFILE)
    _deep_merge(merged, profile)
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return merged


def _deep_merge(target, source):
    """Merge récursif (source écrase target sauf si valeur vide)."""
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge(target[k], v)
        else:
            target[k] = v


def is_complete(profile=None):
    """Profil minimum pour usage : raison_sociale opérateur + prix cumac."""
    p = profile or load_profile()
    op = p.get("operateur", {})
    pricing = p.get("pricing", {})
    return bool(op.get("raison_sociale")) and bool(pricing.get("prix_cumac_eur_mwh_classique"))


def compute_commissions(prime_totale_eur, profile=None):
    """Calcule la répartition commissions selon profil.

    Retourne dict : {prime, apporteur, vendeur, marge_operateur, prime_nette_client}
    """
    p = profile or load_profile()
    pr = p.get("pricing", {})
    pct_app = pr.get("pct_apporteur_affaires", 0) / 100.0
    pct_vd = pr.get("pct_vendeur", 0) / 100.0
    pct_mg = pr.get("pct_marge_operateur", 0) / 100.0

    apporteur = round(prime_totale_eur * pct_app, 2)
    vendeur = round(prime_totale_eur * pct_vd, 2)
    marge = round(prime_totale_eur * pct_mg, 2)
    prime_nette = round(prime_totale_eur - apporteur - vendeur - marge, 2)

    return {
        "prime_totale": prime_totale_eur,
        "pct_apporteur": pr.get("pct_apporteur_affaires", 0),
        "pct_vendeur": pr.get("pct_vendeur", 0),
        "pct_marge": pr.get("pct_marge_operateur", 0),
        "apporteur_affaires": apporteur,
        "vendeur": vendeur,
        "marge_operateur": marge,
        "prime_nette_client": prime_nette,
    }
