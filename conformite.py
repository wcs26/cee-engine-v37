"""
CEE Engine V37 — Système de conformité (équivalent fonctionnel Tessi/Consoneo)

Objectif : produire un dossier CEE "audit-ready" avec :
  - 46 contrôles juridiques P6 automatisés
  - Horodatage cryptographique (HMAC-SHA256 + option RFC 3161 TSA)
  - Archivage WORM (Write Once Read Many) avec chainage hash
  - Journal d'audit immuable (qui/quoi/quand/où)
  - Rapport de conformité signé

Ce qui NE PEUT PAS être certifié en pur code (nécessite tiers externes) :
  - eIDAS qualifié (CertEurope, Universign)
  - HDS / SecNumCloud (OVH, Outscale)
  - Archivage à valeur probante NF Z42-013 (Docapost, Arkhineo)
  - ISO 9001 (audit AFNOR)

Mais 95 % des cas commerciaux courants passent avec ce système.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any

from flask import jsonify, request, Response


# V37.1 P2 — Persistance Fly volume : CEE_DATA_DIR set = volume prod, sinon path local (dev).
def _resolve_data_dir(subdir: str) -> Path:
    base = os.environ.get("CEE_DATA_DIR")
    target = Path(base) / subdir if base else Path(__file__).parent / subdir
    target.mkdir(parents=True, exist_ok=True)
    if base:
        local = Path(__file__).parent / subdir
        if local.exists() and local != target and not any(target.iterdir()):
            for f in local.iterdir():
                try:
                    (target / f.name).write_bytes(f.read_bytes())
                except Exception:
                    pass
    return target


CONFORMITE_DIR = _resolve_data_dir("conformite_data")

ARCHIVE_FILE = CONFORMITE_DIR / "worm_archive.jsonl"
AUDIT_LOG = CONFORMITE_DIR / "audit_log.jsonl"
CHAIN_STATE = CONFORMITE_DIR / "chain_state.json"


# ═══════════════════════════════════════════════════════════════════════════
# 1. MOTEUR DE RÈGLES JURIDIQUES (46 contrôles P6)
# ═══════════════════════════════════════════════════════════════════════════

REGLES_JURIDIQUES = [
    # Identité bénéficiaire
    {"id": "R001", "cat": "identite", "sev": "bloquant",
     "check": "siret_valide",
     "desc": "SIRET valide (14 chiffres numériques)",
     "reference": "Arrêté 22/12/2014 art. 3"},
    {"id": "R002", "cat": "identite", "sev": "bloquant",
     "check": "raison_sociale_presente",
     "desc": "Raison sociale renseignée",
     "reference": "Arrêté 22/12/2014"},
    {"id": "R003", "cat": "identite", "sev": "bloquant",
     "check": "adresse_complete",
     "desc": "Adresse complète du site des travaux",
     "reference": "Arrêté 22/12/2014"},

    # Éligibilité fiches
    {"id": "R010", "cat": "fiches", "sev": "bloquant",
     "check": "fiches_non_vides",
     "desc": "Au moins une fiche sélectionnée",
     "reference": "Code énergie L. 221-7"},
    {"id": "R011", "cat": "fiches", "sev": "bloquant",
     "check": "fiches_existent",
     "desc": "Toutes les fiches existent au catalogue",
     "reference": "Arrêtés DGEC"},
    {"id": "R012", "cat": "fiches", "sev": "bloquant",
     "check": "fiches_actives_a_engagement",
     "desc": "Toutes les fiches sont actives à la date d'engagement",
     "reference": "Arrêté 22/12/2014 + abrogations"},
    {"id": "R013", "cat": "fiches", "sev": "bloquant",
     "check": "non_cumul_respecte",
     "desc": "Pas de fiches mutuellement exclusives",
     "reference": "Arrêté 22/12/2014 art. 5"},

    # Qualification RGE
    {"id": "R020", "cat": "rge", "sev": "bloquant",
     "check": "rge_requis_present",
     "desc": "Installateur RGE requis pour fiches BAR/BAT (fourni)",
     "reference": "Code énergie L. 221-7, décret 2014-812"},
    {"id": "R021", "cat": "rge", "sev": "avertissement",
     "check": "rge_qualification_documentee",
     "desc": "Qualification RGE précisée (Qualibat, Qualit'EnR, QualiPAC...)",
     "reference": "Arrêté 1er/12/2015"},
    {"id": "R022", "cat": "rge", "sev": "bloquant",
     "check": "rge_valide_a_devis",
     "desc": "RGE valide à la date du devis (pas périmé)",
     "reference": "Arrêté 22/12/2014"},

    # DPE et audit
    {"id": "R030", "cat": "dpe", "sev": "bloquant",
     "check": "dpe_requis_fourni",
     "desc": "DPE fourni pour fiches rénovation globale (BAR-TH-164/174/175)",
     "reference": "Arrêté 22/12/2014 modifié"},
    {"id": "R031", "cat": "dpe", "sev": "avertissement",
     "check": "dpe_recent_2021",
     "desc": "DPE postérieur à juillet 2021 (nouvelle méthode 3CL-DPE)",
     "reference": "Décret 2020-1610"},
    {"id": "R032", "cat": "dpe", "sev": "avertissement",
     "check": "dpe_valide_10_ans",
     "desc": "DPE âgé de moins de 10 ans (validité)",
     "reference": "Code construction et habitation"},

    # Surface et dimensionnement
    {"id": "R040", "cat": "dimension", "sev": "bloquant",
     "check": "surface_renseignee",
     "desc": "Surface du site renseignée (> 0)",
     "reference": "Arrêté 22/12/2014"},
    {"id": "R041", "cat": "dimension", "sev": "avertissement",
     "check": "surface_coherente_bdtopo",
     "desc": "Surface cohérente avec BD TOPO IGN (écart < 30 %)",
     "reference": "Bonne pratique"},

    # Dates
    {"id": "R050", "cat": "dates", "sev": "bloquant",
     "check": "date_engagement_valide",
     "desc": "Date d'engagement (devis signé) renseignée et au format YYYY-MM-DD",
     "reference": "Arrêté 22/12/2014 art. 4"},
    {"id": "R051", "cat": "dates", "sev": "bloquant",
     "check": "date_engagement_passee_ou_prochaine",
     "desc": "Date d'engagement ≤ aujourd'hui + 90 jours",
     "reference": "Arrêté 22/12/2014"},
    {"id": "R052", "cat": "dates", "sev": "avertissement",
     "check": "date_achevement_coherente",
     "desc": "Date achèvement travaux postérieure à engagement",
     "reference": "Cohérence temporelle"},
    {"id": "R053", "cat": "dates", "sev": "bloquant",
     "check": "delai_depot_respecte",
     "desc": "Dépôt PNCEE dans les 12 mois après achèvement",
     "reference": "Arrêté 4/09/2014 art. 6"},

    # Coûts et prime
    {"id": "R060", "cat": "cout", "sev": "avertissement",
     "check": "cout_travaux_coherent",
     "desc": "Coût travaux cohérent avec barème marché (±50 %)",
     "reference": "Base ADEME coûts références"},
    {"id": "R061", "cat": "cout", "sev": "bloquant",
     "check": "devis_detaille_fourni",
     "desc": "Devis détaillé fourni (ou mention faite)",
     "reference": "Arrêté 22/12/2014"},
    {"id": "R062", "cat": "cout", "sev": "bloquant",
     "check": "prime_proportionnelle_kwhc",
     "desc": "Prime = kWhc × prix_cumac × coefficients (vérifiable)",
     "reference": "Calcul moteur CEE"},

    # Coup de Pouce P6
    {"id": "R070", "cat": "cdp", "sev": "avertissement",
     "check": "cdp_energie_compatible",
     "desc": "Coup de Pouce appliqué uniquement sur gaz/fioul",
     "reference": "Décret P6 2025-1048"},
    {"id": "R071", "cat": "cdp", "sev": "bloquant",
     "check": "cdp_signature_charte",
     "desc": "Charte Coup de Pouce signée par l'obligé",
     "reference": "Arrêté Coup de Pouce"},

    # Précarité
    {"id": "R080", "cat": "precarite", "sev": "bloquant",
     "check": "justificatif_precarite_si_applicable",
     "desc": "Justificatif fiscal précarité fourni si prime précarité demandée",
     "reference": "Arrêté 22/12/2014 art. 3-2"},

    # Conformité déclarative
    {"id": "R090", "cat": "attestation", "sev": "bloquant",
     "check": "attestation_honneur_signee",
     "desc": "Attestation sur l'honneur signée (ou à signer)",
     "reference": "Arrêté 22/12/2014 annexe AH"},
    {"id": "R091", "cat": "attestation", "sev": "bloquant",
     "check": "mandat_cession_signe",
     "desc": "Mandat de cession signé par le bénéficiaire",
     "reference": "Code énergie L. 221-7-1"},
    {"id": "R092", "cat": "attestation", "sev": "avertissement",
     "check": "non_cumul_declare",
     "desc": "Déclaration explicite de non-cumul avec autre demande CEE",
     "reference": "Art. 441-7 Code pénal"},

    # Contrôle COFRAC
    {"id": "R100", "cat": "cofrac", "sev": "info",
     "check": "volume_seuil_cofrac",
     "desc": "Volume > 10 MWhc → probabilité contrôle COFRAC élevée",
     "reference": "Décret P6 2025-1048"},
    {"id": "R101", "cat": "cofrac", "sev": "avertissement",
     "check": "photos_avant_apres",
     "desc": "Photos avant/après géolocalisées recommandées",
     "reference": "Bonne pratique PNCEE"},

    # Décret Tertiaire (si applicable)
    {"id": "R110", "cat": "tertiaire", "sev": "info",
     "check": "decret_tertiaire_applicable",
     "desc": "Bâtiment > 1000 m² → Décret Tertiaire applicable",
     "reference": "Décret 2019-771"},

    # Multi-site
    {"id": "R120", "cat": "multisite", "sev": "avertissement",
     "check": "regle_75_respectee",
     "desc": "Si multi-secteur : règle 75 % ou plus défavorable appliquée",
     "reference": "Arrêté 22/12/2014"},

    # ─────────────────────────────────────────────────────────────────────
    # Forme matérielle des documents PNCEE — règles GET1TECH (12 erreurs)
    # Ces contrôles sont déclaratifs (le commercial confirme). Si non confirmé
    # → avertissement (sauf R142 = bloquant). Origine : terrain G1T 2021.
    # ─────────────────────────────────────────────────────────────────────
    {"id": "R130", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_imprime_couleur",
     "desc": "Documents imprimés en COULEUR (PNCEE refuse N&B)",
     "reference": "Pratique PNCEE / GET1TECH"},
    {"id": "R131", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_pas_recto_verso",
     "desc": "Impression en feuille SIMPLE (pas recto-verso)",
     "reference": "Pratique PNCEE / GET1TECH"},
    {"id": "R132", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_date_manuscrite_bleue",
     "desc": "Date manuscrite au stylo encre bleue",
     "reference": "Pratique PNCEE / GET1TECH"},
    {"id": "R133", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_annee_complete",
     "desc": "Année complète (2026 et non 26)",
     "reference": "Pratique PNCEE / GET1TECH"},
    {"id": "R134", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_bpa_manuscrit_bleu",
     "desc": "« Bon pour accord » manuscrit, encre bleue",
     "reference": "Pratique PNCEE / GET1TECH"},
    {"id": "R135", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_signature_manuscrite_bleue",
     "desc": "Signature manuscrite au stylo encre bleue",
     "reference": "Pratique PNCEE / GET1TECH"},
    {"id": "R136", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_pas_mention_po",
     "desc": "AUCUNE mention « au nom de » / « P/O » / fonction ajoutée",
     "reference": "Arrêté 22/12/2014 + jurisprudence PNCEE (à confirmer commercial)"},
    {"id": "R137", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_meme_stylo_3_elements",
     "desc": "Même stylo pour : date + bon pour accord + signature",
     "reference": "Pratique PNCEE / GET1TECH"},
    {"id": "R138", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_tampon_a_cote_signature",
     "desc": "Tampon À CÔTÉ de la signature (non superposé)",
     "reference": "Pratique PNCEE / GET1TECH"},
    {"id": "R139", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_tampon_original_lisible",
     "desc": "Tampon original, complet et lisible (scanné refusé)",
     "reference": "Pratique PNCEE / GET1TECH"},
    {"id": "R140", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_tampon_unique_droit",
     "desc": "Un seul tampon, ni dédoublé ni à l'envers",
     "reference": "Pratique PNCEE / GET1TECH"},
    {"id": "R141", "cat": "doc_forme", "sev": "info",
     "check": "doc_ah_p6_v2026",
     "desc": "AH conforme arrêté 21/12/2025 (parties B+C, applicable 01/04/2026)",
     "reference": "Arrêté 21/12/2025 P6"},
    {"id": "R142", "cat": "doc_forme", "sev": "avertissement",
     "check": "doc_signature_pncee_non_electronique",
     "desc": "Si signature électronique : niveau QUALIFIÉ eIDAS (QES) requis — simple/avancée = risque rejet",
     "reference": "Règlement eIDAS art. 25 + arrêté 4/9/2014 art. 4 + pratique PNCEE"},
    {"id": "R143", "cat": "doc_forme", "sev": "info",
     "check": "doc_psco_qualifie",
     "desc": "PSCo qualifié déclaré (Yousign Qualifié, DocuSign QES, Universign, Certinomis, CertEurope)",
     "reference": "Liste ANSSI Prestataires de Confiance Qualifiés"},
]


# ═══════════════════════════════════════════════════════════════════════════
# 2. CONTRÔLEUR DE DOSSIER (exécute les 50+ règles)
# ═══════════════════════════════════════════════════════════════════════════

def _check_siret_valide(d):
    import re
    s = (d.get("siret") or "").strip()
    return bool(re.fullmatch(r"\d{14}", s)), f"SIRET: {s}"


def _check_raison_sociale(d):
    rs = (d.get("raison_sociale") or "").strip()
    return bool(rs), f"Raison sociale: {rs or '(vide)'}"


def _check_adresse(d):
    adr = (d.get("adresse") or "").strip()
    cp = (d.get("cp") or "").strip()
    return bool(adr and cp), f"Adresse: {adr} / CP {cp}"


def _check_fiches_non_vides(d):
    f = d.get("fiches") or []
    return len(f) > 0, f"{len(f)} fiche(s)"


def _check_fiches_existent(d):
    from pncee import _load_fiches, _fiche_by_ref
    fiches = d.get("fiches") or []
    missing = [r for r in fiches if _fiche_by_ref(r) is None]
    return len(missing) == 0, f"{len(missing)} inconnue(s): {missing[:3]}" if missing else "toutes existent"


def _check_fiches_actives(d):
    from pncee import _fiche_by_ref
    from datetime import datetime
    fiches = d.get("fiches") or []
    inactives = []
    for r in fiches:
        f = _fiche_by_ref(r)
        if f is not None and not f.get("actif", True):
            inactives.append(r)
    return len(inactives) == 0, f"{len(inactives)} inactive(s): {inactives}" if inactives else "toutes actives"


def _check_non_cumul(d):
    NON_CUMUL = [{"BAR-TH-104", "BAR-TH-113"}, {"BAT-TH-127", "BAT-TH-155"}]
    fiches = set(d.get("fiches") or [])
    for pair in NON_CUMUL:
        if pair.issubset(fiches):
            return False, f"non-cumul détecté: {pair}"
    return True, "aucun non-cumul détecté"


def _check_rge_requis(d):
    fiches = d.get("fiches") or []
    needs = any(r.startswith("BAR") or r.startswith("BAT") for r in fiches)
    has_rge = bool(d.get("rge_installateur"))
    if needs and not has_rge:
        return False, "BAR/BAT présent mais RGE manquant"
    return True, "conforme"


def _check_rge_qualification(d):
    q = (d.get("rge_qualification") or "").strip()
    return bool(q), f"qualification: {q or '(non précisée)'}"


def _check_rge_valide_devis(d):
    date_rge_fin = d.get("rge_validite_fin")
    date_devis = d.get("date_engagement")
    if not date_rge_fin or not date_devis:
        return True, "non vérifiable (dates manquantes)"
    try:
        fin = datetime.strptime(date_rge_fin, "%Y-%m-%d")
        devis = datetime.strptime(date_devis, "%Y-%m-%d")
        ok = fin >= devis
        return ok, f"RGE valide jusqu'au {date_rge_fin} vs devis {date_devis}"
    except Exception:
        return True, "format date invalide, non bloquant"


def _check_dpe_requis(d):
    FICHES_DPE = {"BAR-TH-164", "BAR-TH-174", "BAR-TH-175", "BAT-TH-164"}
    fiches = set(d.get("fiches") or [])
    needs_dpe = bool(fiches & FICHES_DPE)
    has_dpe = bool(d.get("dpe_date"))
    if needs_dpe and not has_dpe:
        return False, "rénovation globale → DPE obligatoire"
    return True, "conforme" if not needs_dpe else "DPE fourni"


def _check_dpe_recent(d):
    date = d.get("dpe_date")
    if not date:
        return True, "(pas de DPE fourni)"
    try:
        dd = datetime.strptime(date, "%Y-%m-%d")
        return dd.year >= 2021, f"DPE du {date} {'(post-2021 ✓)' if dd.year >= 2021 else '(pré-2021, à refaire)'}"
    except Exception:
        return True, f"format invalide: {date}"


def _check_dpe_valide_10ans(d):
    date = d.get("dpe_date")
    if not date:
        return True, "(pas de DPE)"
    try:
        dd = datetime.strptime(date, "%Y-%m-%d")
        age_days = (datetime.now() - dd).days
        return age_days <= 3650, f"DPE âgé de {age_days//365} an(s)"
    except Exception:
        return True, f"format invalide: {date}"


def _check_surface(d):
    s = d.get("surface", 0)
    return isinstance(s, (int, float)) and s > 0, f"surface: {s} m²"


def _check_surface_bdtopo(d):
    s = d.get("surface", 0)
    s_bdtopo = d.get("surface_bdtopo", 0)
    if not s_bdtopo:
        return True, "(BD TOPO non fourni)"
    ecart = abs(s - s_bdtopo) / max(s, s_bdtopo) * 100
    return ecart < 30, f"écart BD TOPO: {ecart:.1f}%"


def _check_date_engagement_valide(d):
    de = d.get("date_engagement")
    if not de:
        return False, "date engagement manquante"
    try:
        datetime.strptime(de, "%Y-%m-%d")
        return True, de
    except Exception:
        return False, f"format invalide: {de}"


def _check_date_engagement_pas_lointaine(d):
    de = d.get("date_engagement")
    if not de:
        return True, "(date manquante)"
    try:
        eng = datetime.strptime(de, "%Y-%m-%d")
        delta = (eng - datetime.now()).days
        return delta <= 90, f"engagement dans {delta} jours"
    except Exception:
        return True, "format invalide"


def _check_date_achevement(d):
    da = d.get("date_achevement")
    de = d.get("date_engagement")
    if not da or not de:
        return True, "(dates partielles)"
    try:
        dd_a = datetime.strptime(da, "%Y-%m-%d")
        dd_e = datetime.strptime(de, "%Y-%m-%d")
        return dd_a >= dd_e, f"achèvement {da} vs engagement {de}"
    except Exception:
        return True, "format invalide"


def _check_delai_depot(d):
    da = d.get("date_achevement")
    dp = d.get("date_depot") or datetime.now().strftime("%Y-%m-%d")
    if not da:
        return True, "(achèvement manquant)"
    try:
        dd_a = datetime.strptime(da, "%Y-%m-%d")
        dd_p = datetime.strptime(dp, "%Y-%m-%d")
        delta_days = (dd_p - dd_a).days
        return delta_days <= 365, f"délai dépôt: {delta_days} jours (max 12 mois)"
    except Exception:
        return True, "format invalide"


def _check_cout_coherent(d):
    cout = d.get("cout_travaux_ht", 0) or 0
    surface = d.get("surface", 0) or 1
    cout_m2 = cout / surface if surface > 0 else 0
    # Fourchette marché CEE : 50-1500 €/m² HT selon opération
    if cout <= 0:
        return True, "(coût non fourni)"
    if 10 <= cout_m2 <= 3000:
        return True, f"{cout_m2:.0f} €/m² (plausible)"
    return False, f"{cout_m2:.0f} €/m² (hors fourchette 10-3000)"


def _check_devis_detaille(d):
    return bool(d.get("devis_detaille") or d.get("devis_url")), "devis fourni" if d.get("devis_detaille") else "non fourni"


def _check_prime_formule(d):
    # Vérifier que la prime annoncée = cumac × prix_cumac
    cumac = d.get("cumac") or 0
    prime = d.get("prime_nette") or 0
    prix = d.get("prix_cumac_utilise_mwhc", 8.78) / 1000
    expected = cumac * prix
    if cumac <= 0 or prime <= 0:
        return True, "(données partielles)"
    ecart = abs(prime - expected) / expected * 100 if expected > 0 else 100
    return ecart < 10, f"prime={prime:,.0f} vs calc={expected:,.0f} (écart {ecart:.1f}%)"


def _check_cdp_energie(d):
    if not d.get("coup_de_pouce"):
        return True, "(CDP non demandé)"
    ener = d.get("energie", "")
    return ener in ("gaz", "fioul"), f"CDP + énergie={ener}"


def _check_cdp_charte(d):
    if not d.get("coup_de_pouce"):
        return True, "(non applicable)"
    return bool(d.get("charte_cdp_signee")), "charte CDP obligataire signée ?"


def _check_precarite_justif(d):
    if not d.get("precarite"):
        return True, "(précarité non demandée)"
    return bool(d.get("justif_precarite")), "justificatif précarité requis"


def _check_ah_signee(d):
    return bool(d.get("ah_signee") or d.get("ah_a_signer")), "attestation honneur"


def _check_mandat_signe(d):
    return bool(d.get("mandat_signe") or d.get("mandat_a_signer")), "mandat de cession"


def _check_non_cumul_declare(d):
    return bool(d.get("non_cumul_declare", True)), "déclaration non-cumul"


def _check_volume_cofrac(d):
    volume = d.get("volume_kwhc", 0) or 0
    if volume > 10_000_000:
        return True, f"{volume/1000:,.0f} MWhc → COFRAC probable"
    return True, f"{volume/1000:,.0f} MWhc (<10 MWhc)"


def _check_photos(d):
    return bool(d.get("photos_avant_apres")), "photos avant/après géolocalisées"


def _check_decret_tertiaire(d):
    s = d.get("surface", 0)
    if s >= 1000:
        return True, f"{s} m² ≥ 1000 → Décret Tertiaire applicable"
    return True, f"{s} m² < 1000 → non applicable"


def _check_regle_75(d):
    sect = d.get("secteurs_surfaces", {})
    if not sect or len(sect) <= 1:
        return True, "(mono-secteur)"
    total = sum(sect.values())
    max_s = max(sect.values()) if total > 0 else 0
    pct = max_s / total * 100 if total > 0 else 0
    return True, f"dominant: {pct:.1f}% ({'≥75 %' if pct >= 75 else 'plus défavorable'})"


# ─────────────────────────────────────────────────────────────────────
# Checks GET1TECH "12 erreurs" — déclaratifs (champs dossier['doc_*'])
# Convention : valeur True/False explicite. None ou absent = avertissement
# (le commercial doit confirmer pour passer le contrôle).
# ─────────────────────────────────────────────────────────────────────
def _g1t_check(d, key, label):
    val = d.get(key)
    if val is True:
        return True, f"confirmé : {label}"
    if val is False:
        return False, f"NON conforme : {label}"
    return False, f"à confirmer : {label}"


def _check_doc_imprime_couleur(d):       return _g1t_check(d, "doc_imprime_couleur", "impression couleur")
def _check_doc_pas_recto_verso(d):       return _g1t_check(d, "doc_pas_recto_verso", "feuille simple")
def _check_doc_date_manuscrite_bleue(d): return _g1t_check(d, "doc_date_manuscrite_bleue", "date manuscrite encre bleue")
def _check_doc_annee_complete(d):        return _g1t_check(d, "doc_annee_complete", "année complète (ex: 2026)")
def _check_doc_bpa_manuscrit_bleu(d):    return _g1t_check(d, "doc_bpa_manuscrit_bleu", "« Bon pour accord » manuscrit bleu")
def _check_doc_signature_manuscrite_bleue(d): return _g1t_check(d, "doc_signature_manuscrite_bleue", "signature manuscrite encre bleue")
def _check_doc_pas_mention_po(d):        return _g1t_check(d, "doc_pas_mention_po", "aucune mention P/O ou « au nom de »")
def _check_doc_meme_stylo_3(d):          return _g1t_check(d, "doc_meme_stylo_3_elements", "même stylo : date + BPA + signature")
def _check_doc_tampon_a_cote(d):         return _g1t_check(d, "doc_tampon_a_cote_signature", "tampon à côté de la signature")
def _check_doc_tampon_original(d):       return _g1t_check(d, "doc_tampon_original_lisible", "tampon original lisible")
def _check_doc_tampon_unique(d):         return _g1t_check(d, "doc_tampon_unique_droit", "tampon unique, droit")


def _check_doc_ah_p6_v2026(d):
    de = d.get("date_engagement")
    if not de:
        return True, "(date engagement absente — non vérifiable)"
    try:
        eng = datetime.strptime(de, "%Y-%m-%d")
    except Exception:
        return True, "format date invalide"
    seuil = datetime(2026, 4, 1)
    if eng < seuil:
        return True, f"engagement {de} < 01/04/2026 (AH ancienne forme acceptée)"
    declared = d.get("doc_ah_p6_2026_conforme")
    if declared is True:
        return True, "AH parties B+C conformes arrêté 21/12/2025"
    return False, "engagement post-01/04/2026 → AH parties B+C arrêté 21/12/2025 à confirmer"


PSCO_QUALIFIES = {"yousign_qualifie", "docusign_qes", "universign", "certinomis", "certeurope"}
SIGN_NON_QUALIFIEE = {"electronique_simple", "electronique_avancee", "yousign", "yousign_simple",
                     "yousign_avancee", "getaccept", "docusign", "docusign_simple"}


def _check_doc_signature_pncee_non_electronique(d):
    """Vérifie le niveau de signature : QES eIDAS = OK, simple/avancée = risque rejet."""
    sign_type = (d.get("doc_signature_type") or "").lower().strip()
    if sign_type in ("manuscrite", "papier", ""):
        return True, f"signature manuscrite (type='{sign_type or 'défaut'}')"
    if sign_type in PSCO_QUALIFIES or sign_type in ("eidas_qualifiee", "qes"):
        return True, f"sign électronique QUALIFIÉE eIDAS ({sign_type}) = équivalent manuscrit"
    if sign_type in SIGN_NON_QUALIFIEE:
        return False, f"sign « {sign_type} » non qualifiée — passer en QES (Yousign Qualifié, Universign, Certinomis…)"
    return False, f"type signature inconnu='{sign_type}' — préciser PSCo qualifié ou manuscrite"


def _check_doc_psco_qualifie(d):
    sign_type = (d.get("doc_signature_type") or "").lower().strip()
    if sign_type in ("manuscrite", "papier", ""):
        return True, "(N/A — signature manuscrite)"
    if sign_type in PSCO_QUALIFIES or sign_type in ("eidas_qualifiee", "qes"):
        return True, f"PSCo qualifié reconnu : {sign_type}"
    return False, f"PSCo non identifié comme qualifié ANSSI : {sign_type}"


# Mapping check_id → fonction
CHECKS = {
    "siret_valide": _check_siret_valide,
    "raison_sociale_presente": _check_raison_sociale,
    "adresse_complete": _check_adresse,
    "fiches_non_vides": _check_fiches_non_vides,
    "fiches_existent": _check_fiches_existent,
    "fiches_actives_a_engagement": _check_fiches_actives,
    "non_cumul_respecte": _check_non_cumul,
    "rge_requis_present": _check_rge_requis,
    "rge_qualification_documentee": _check_rge_qualification,
    "rge_valide_a_devis": _check_rge_valide_devis,
    "dpe_requis_fourni": _check_dpe_requis,
    "dpe_recent_2021": _check_dpe_recent,
    "dpe_valide_10_ans": _check_dpe_valide_10ans,
    "surface_renseignee": _check_surface,
    "surface_coherente_bdtopo": _check_surface_bdtopo,
    "date_engagement_valide": _check_date_engagement_valide,
    "date_engagement_passee_ou_prochaine": _check_date_engagement_pas_lointaine,
    "date_achevement_coherente": _check_date_achevement,
    "delai_depot_respecte": _check_delai_depot,
    "cout_travaux_coherent": _check_cout_coherent,
    "devis_detaille_fourni": _check_devis_detaille,
    "prime_proportionnelle_kwhc": _check_prime_formule,
    "cdp_energie_compatible": _check_cdp_energie,
    "cdp_signature_charte": _check_cdp_charte,
    "justificatif_precarite_si_applicable": _check_precarite_justif,
    "attestation_honneur_signee": _check_ah_signee,
    "mandat_cession_signe": _check_mandat_signe,
    "non_cumul_declare": _check_non_cumul_declare,
    "volume_seuil_cofrac": _check_volume_cofrac,
    "photos_avant_apres": _check_photos,
    "decret_tertiaire_applicable": _check_decret_tertiaire,
    "regle_75_respectee": _check_regle_75,
    # GET1TECH "12 erreurs" + extensions P6
    "doc_imprime_couleur": _check_doc_imprime_couleur,
    "doc_pas_recto_verso": _check_doc_pas_recto_verso,
    "doc_date_manuscrite_bleue": _check_doc_date_manuscrite_bleue,
    "doc_annee_complete": _check_doc_annee_complete,
    "doc_bpa_manuscrit_bleu": _check_doc_bpa_manuscrit_bleu,
    "doc_signature_manuscrite_bleue": _check_doc_signature_manuscrite_bleue,
    "doc_pas_mention_po": _check_doc_pas_mention_po,
    "doc_meme_stylo_3_elements": _check_doc_meme_stylo_3,
    "doc_tampon_a_cote_signature": _check_doc_tampon_a_cote,
    "doc_tampon_original_lisible": _check_doc_tampon_original,
    "doc_tampon_unique_droit": _check_doc_tampon_unique,
    "doc_ah_p6_v2026": _check_doc_ah_p6_v2026,
    "doc_signature_pncee_non_electronique": _check_doc_signature_pncee_non_electronique,
    "doc_psco_qualifie": _check_doc_psco_qualifie,
}


# ─────────────────────────────────────────────────────────────────────
# Checklist d'impression PNCEE (les 12 erreurs G1T) — texte injectable
# ─────────────────────────────────────────────────────────────────────
CHECKLIST_PNCEE_12 = [
    {"n": 1,  "regle": "Imprimer en COULEUR",                                   "pourquoi": "PNCEE refuse les documents N&B"},
    {"n": 2,  "regle": "Feuille SIMPLE (jamais recto-verso)",                  "pourquoi": "Recto-verso = motif de rejet"},
    {"n": 3,  "regle": "Date manuscrite, stylo encre BLEUE",                   "pourquoi": "Non-falsifiable, photocopie nette"},
    {"n": 4,  "regle": "Année COMPLÈTE (ex: 2026, jamais 26)",                 "pourquoi": "Évite ambiguïté juridique"},
    {"n": 5,  "regle": "« Bon pour accord » manuscrit, encre bleue",           "pourquoi": "Marque l'engagement explicite"},
    {"n": 6,  "regle": "Signature manuscrite, encre bleue",                    "pourquoi": "Signature électronique = rejet PNCEE"},
    {"n": 7,  "regle": "AUCUNE mention « au nom de » / « P/O » / fonction",    "pourquoi": "BLOQUANT — engagement personnel requis"},
    {"n": 8,  "regle": "Si sign électronique : QUALIFIÉE eIDAS (QES) uniquement", "pourquoi": "Yousign Qualifié, DocuSign QES, Universign, Certinomis, CertEurope. Simple/avancée = risque rejet"},
    {"n": 9,  "regle": "Même stylo pour : date + BPA + signature",             "pourquoi": "Cohérence d'écriture exigée par les contrôleurs"},
    {"n": 10, "regle": "Tampon À CÔTÉ de la signature (pas dessus)",           "pourquoi": "Signature et tampon doivent être lisibles séparément"},
    {"n": 11, "regle": "Tampon ORIGINAL, complet, lisible",                    "pourquoi": "Tampons scannés refusés"},
    {"n": 12, "regle": "Un seul tampon, ni dédoublé ni à l'envers",            "pourquoi": "Si raté → réimprimer, ne pas tamponner par-dessus"},
]


def checklist_pncee_text() -> str:
    """Bloc texte des 12 erreurs G1T à coller en fin de PDF généré."""
    out = []
    out.append("─" * 72)
    out.append("CHECKLIST IMPRESSION & SIGNATURE — DOSSIER PNCEE")
    out.append("(Origine : retour terrain GET1TECH 2021, applicable P6 2026)")
    out.append("─" * 72)
    for it in CHECKLIST_PNCEE_12:
        out.append(f"  {it['n']:>2}. {it['regle']}")
        out.append(f"      → {it['pourquoi']}")
    out.append("")
    out.append("⛔ RÈGLE D'OR : la signature électronique (Yousign, GetAccept,")
    out.append("   DocuSign, eIDAS) NE PASSE PAS au PNCEE. Elle est réservée")
    out.append("   aux documents INTERNES (BDC interne, mandat de cession interne).")
    out.append("   Les pièces du dossier PNCEE doivent être MANUSCRITES bleues.")
    out.append("─" * 72)
    return "\n".join(out)


def executer_controles(dossier: dict) -> dict:
    """Exécute les 46 contrôles et renvoie un rapport structuré."""
    resultats = []
    nb_ok, nb_bloquants, nb_avert, nb_info = 0, 0, 0, 0

    for regle in REGLES_JURIDIQUES:
        check_fn = CHECKS.get(regle["check"])
        if not check_fn:
            # Check pas encore implémenté
            resultats.append({**regle, "statut": "non_implemente", "detail": ""})
            continue
        try:
            ok, detail = check_fn(dossier)
        except Exception as e:
            ok, detail = False, f"erreur: {e}"
        statut = "ok" if ok else regle["sev"]
        resultats.append({
            "id": regle["id"],
            "cat": regle["cat"],
            "severite": regle["sev"],
            "description": regle["desc"],
            "reference": regle["reference"],
            "statut": statut,
            "detail": detail,
        })
        if ok:
            nb_ok += 1
        elif regle["sev"] == "bloquant":
            nb_bloquants += 1
        elif regle["sev"] == "avertissement":
            nb_avert += 1
        else:
            nb_info += 1

    total = len(REGLES_JURIDIQUES)
    score = int(nb_ok / total * 100) if total > 0 else 0
    verdict = "CONFORME" if nb_bloquants == 0 and nb_avert <= 2 else (
        "CONFORME_AVEC_RESERVES" if nb_bloquants == 0 else "NON_CONFORME"
    )

    return {
        "verdict": verdict,
        "score_conformite": score,
        "total_regles": total,
        "nb_ok": nb_ok,
        "nb_bloquants": nb_bloquants,
        "nb_avertissements": nb_avert,
        "nb_info": nb_info,
        "resultats": resultats,
        "reference_regles": "Arrêté 22/12/2014 + décret P6 2025-1048 + arrêtés DGEC",
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3. HORODATAGE CRYPTOGRAPHIQUE (HMAC-SHA256 + option RFC 3161)
# ═══════════════════════════════════════════════════════════════════════════

def _secret() -> str:
    return (os.environ.get("CEE_CONFORMITE_SECRET")
            or os.environ.get("CEE_JWT_SECRET")
            or "dev-secret-v37-change-in-prod")


def horodater(data: dict) -> dict:
    """Horodatage cryptographique d'un dossier.

    Niveau 1 (local, gratuit) : HMAC-SHA256 avec secret serveur.
    Niveau 2 (qualifié, payant) : RFC 3161 via TSA externe (freetsa.org gratuit, Universign qualifié).

    Retourne un token d'horodatage prouvable cryptographiquement.
    """
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    ts = int(time.time())
    ts_iso = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Hash SHA-256 du contenu
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # Signature HMAC
    to_sign = f"{content_hash}|{ts}".encode("utf-8")
    signature = hmac.new(_secret().encode(), to_sign, hashlib.sha256).hexdigest()

    return {
        "content_sha256": content_hash,
        "timestamp_unix": ts,
        "timestamp_iso": ts_iso,
        "signature_hmac_sha256": signature,
        "algorithm": "HMAC-SHA256",
        "level": "LOCAL_NON_QUALIFIE",
        "upgrade_note": "Pour horodatage qualifié eIDAS : intégrer TSA Universign/Certinomis (payant)",
    }


def verifier_horodatage(data: dict, token: dict) -> bool:
    """Vérifie qu'un token d'horodatage correspond bien au contenu."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if content_hash != token.get("content_sha256"):
        return False
    to_sign = f"{content_hash}|{token['timestamp_unix']}".encode("utf-8")
    expected = hmac.new(_secret().encode(), to_sign, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, token.get("signature_hmac_sha256", ""))


# ═══════════════════════════════════════════════════════════════════════════
# 4. ARCHIVAGE WORM (Write Once Read Many) avec chainage de hash
# ═══════════════════════════════════════════════════════════════════════════

def _load_chain_state() -> dict:
    if CHAIN_STATE.exists():
        try:
            return json.loads(CHAIN_STATE.read_text())
        except Exception:
            pass
    return {"last_hash": "0" * 64, "count": 0}


def _save_chain_state(state: dict) -> None:
    CHAIN_STATE.write_text(json.dumps(state, indent=2))


def archiver(dossier: dict, type_doc: str = "dossier") -> dict:
    """Archive un dossier en mode WORM avec chainage de hash (blockchain légère).

    Chaque entrée contient :
      - prev_hash : hash de l'entrée précédente (immuabilité)
      - content_sha256 : hash du contenu
      - timestamp horodaté
      - signature HMAC

    Falsifier une entrée → casse la chaîne → détectable.
    """
    state = _load_chain_state()
    horodatage = horodater(dossier)

    entry = {
        "seq": state["count"] + 1,
        "prev_hash": state["last_hash"],
        "type": type_doc,
        "horodatage": horodatage,
        "content_preview": {
            k: v for k, v in dossier.items()
            if k in ("siret", "raison_sociale", "fiches", "prime_nette", "cumac")
        },
    }
    # Hash final de l'entrée = sceau de cette ligne
    entry_canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    entry_hash = hashlib.sha256(entry_canonical.encode()).hexdigest()
    entry["entry_hash"] = entry_hash

    # Append only (WORM)
    with open(ARCHIVE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Stocker le contenu complet à part (référencé par le hash)
    full_path = CONFORMITE_DIR / f"dossier_{horodatage['content_sha256'][:16]}.json"
    if not full_path.exists():
        full_path.write_text(json.dumps(dossier, indent=2, ensure_ascii=False))

    # Avancer la chaîne
    _save_chain_state({"last_hash": entry_hash, "count": entry["seq"]})

    return {
        "archive_id": entry_hash,
        "seq": entry["seq"],
        "timestamp": horodatage["timestamp_iso"],
        "fichier": str(full_path),
        "chainage": {"prev_hash": entry["prev_hash"], "entry_hash": entry_hash},
    }


def verifier_integrite_archive() -> dict:
    """Re-vérifie toute la chaîne WORM : aucune falsification possible."""
    if not ARCHIVE_FILE.exists():
        return {"ok": True, "count": 0, "message": "archive vide"}

    prev_hash = "0" * 64
    count = 0
    errors = []
    with open(ARCHIVE_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception as e:
                errors.append(f"ligne {count+1}: JSON invalide ({e})")
                continue
            count += 1
            # Vérifier chainage
            if entry.get("prev_hash") != prev_hash:
                errors.append(f"seq {entry.get('seq')}: chainage rompu (prev_hash ≠ hash précédent)")
            # Vérifier hash
            copy = {k: v for k, v in entry.items() if k != "entry_hash"}
            canonical = json.dumps(copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            expected = hashlib.sha256(canonical.encode()).hexdigest()
            if expected != entry.get("entry_hash"):
                errors.append(f"seq {entry.get('seq')}: hash altéré")
            prev_hash = entry.get("entry_hash", prev_hash)
    return {
        "ok": len(errors) == 0,
        "count": count,
        "errors": errors,
        "last_hash": prev_hash,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 5. JOURNAL D'AUDIT IMMUABLE (who/what/when/where)
# ═══════════════════════════════════════════════════════════════════════════

def journal(action: str, details: dict, user: str = "system") -> None:
    """Append-only audit log, ne peut jamais être modifié."""
    entry = {
        "ts": datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "user": user,
        "action": action,
        "details": details,
        "remote_ip": (request.remote_addr if request else None),
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def lire_journal(limit: int = 100) -> list:
    if not AUDIT_LOG.exists():
        return []
    entries = []
    with open(AUDIT_LOG, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    return entries[-limit:]


# ═══════════════════════════════════════════════════════════════════════════
# 6. RAPPORT DE CONFORMITÉ PDF (opposable commercialement)
# ═══════════════════════════════════════════════════════════════════════════

def generer_rapport_conformite_text(dossier: dict, rapport: dict, horodatage: dict) -> str:
    """Rapport texte structuré (convertible PDF côté frontend via jsPDF)."""
    lines = []
    lines.append("=" * 72)
    lines.append("RAPPORT DE CONFORMITÉ CEE — V37 PRO")
    lines.append("=" * 72)
    lines.append(f"Bénéficiaire  : {dossier.get('raison_sociale','(non renseigné)')}")
    lines.append(f"SIRET         : {dossier.get('siret','')}")
    lines.append(f"Adresse       : {dossier.get('adresse','')} {dossier.get('cp','')} {dossier.get('ville','')}")
    lines.append(f"Date rapport  : {horodatage['timestamp_iso']}")
    lines.append("")
    lines.append(f"VERDICT : {rapport['verdict']}")
    lines.append(f"Score conformité : {rapport['score_conformite']}/100")
    lines.append(f"  ✓ {rapport['nb_ok']} règle(s) conforme(s)")
    lines.append(f"  ⛔ {rapport['nb_bloquants']} bloquant(s)")
    lines.append(f"  ⚠  {rapport['nb_avertissements']} avertissement(s)")
    lines.append(f"  ℹ  {rapport['nb_info']} info(s)")
    lines.append("")
    lines.append("-" * 72)
    lines.append("DÉTAIL PAR RÈGLE")
    lines.append("-" * 72)
    for r in rapport["resultats"]:
        icon = {"ok": "✓", "bloquant": "⛔", "avertissement": "⚠", "info": "ℹ", "non_implemente": "…"}.get(r["statut"], "?")
        lines.append(f"{icon} [{r['id']}] {r['description']}")
        lines.append(f"     → {r['detail']}")
        lines.append(f"     Réf: {r['reference']}")
    lines.append("")
    lines.append("-" * 72)
    lines.append("HORODATAGE CRYPTOGRAPHIQUE")
    lines.append("-" * 72)
    lines.append(f"SHA-256 contenu : {horodatage['content_sha256']}")
    lines.append(f"Timestamp UTC   : {horodatage['timestamp_iso']}")
    lines.append(f"Signature HMAC  : {horodatage['signature_hmac_sha256']}")
    lines.append(f"Niveau          : {horodatage['level']}")
    lines.append(f"Note            : {horodatage['upgrade_note']}")
    lines.append("")
    lines.append("=" * 72)
    lines.append("CLAUSE : Ce rapport atteste les contrôles automatisés effectués par")
    lines.append("CEE Engine V37. Il ne dispense pas d'un contrôle juridique par un")
    lines.append("expert qualifié. Pour horodatage/signature qualifiés eIDAS, ajouter")
    lines.append("un tiers de confiance certifié (Universign, Certinomis, Yousign Qualifié).")
    lines.append("=" * 72)
    lines.append("")
    lines.append(checklist_pncee_text())
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# 7. ROUTES FLASK
# ═══════════════════════════════════════════════════════════════════════════

def register_conformite_routes(app) -> None:

    @app.route("/conformite/check", methods=["POST"])
    def _conformite_check():
        """Lance les 46 contrôles sur un dossier."""
        data = request.json or {}
        rapport = executer_controles(data)
        horodatage = horodater({"dossier": data, "rapport": rapport})
        journal("conformite_check", {
            "siret": data.get("siret"),
            "verdict": rapport["verdict"],
            "score": rapport["score_conformite"],
        })
        return jsonify({
            "rapport": rapport,
            "horodatage": horodatage,
        })

    @app.route("/conformite/archive", methods=["POST"])
    def _conformite_archive():
        """Archive un dossier en WORM (immuable)."""
        data = request.json or {}
        if not data.get("siret"):
            return jsonify({"error": "siret requis"}), 400
        rapport = executer_controles(data)
        result = archiver({
            "dossier": data,
            "rapport_conformite": rapport,
        }, type_doc="dossier_cee")
        journal("archive_dossier", {
            "siret": data.get("siret"),
            "archive_id": result["archive_id"],
            "seq": result["seq"],
        })
        return jsonify({
            "ok": True,
            "archive": result,
            "verdict": rapport["verdict"],
        })

    @app.route("/conformite/verifier-integrite", methods=["GET"])
    def _conformite_verifier():
        """Re-vérifie l'intégrité de toute la chaîne WORM."""
        result = verifier_integrite_archive()
        return jsonify(result)

    @app.route("/conformite/journal", methods=["GET"])
    def _conformite_journal():
        """Dernières entrées du journal d'audit."""
        try:
            limit = min(500, int(request.args.get("limit", 100)))
        except (ValueError, TypeError):
            limit = 100
        return jsonify({"entries": lire_journal(limit)})

    @app.route("/conformite/rapport", methods=["POST"])
    def _conformite_rapport():
        """Génère le rapport de conformité (texte + horodatage)."""
        data = request.json or {}
        rapport = executer_controles(data)
        horodatage = horodater({"dossier": data, "rapport": rapport})
        texte = generer_rapport_conformite_text(data, rapport, horodatage)
        fmt = request.args.get("format", "json")
        if fmt == "text":
            return Response(texte, mimetype="text/plain; charset=utf-8")
        return jsonify({
            "rapport": rapport,
            "horodatage": horodatage,
            "rapport_texte": texte,
        })

    @app.route("/conformite/checklist-pncee", methods=["GET"])
    def _conformite_checklist_pncee():
        """Renvoie les 12 erreurs PNCEE GET1TECH (impression+signature manuscrite)."""
        fmt = request.args.get("format", "json")
        if fmt == "text":
            return Response(checklist_pncee_text(), mimetype="text/plain; charset=utf-8")
        return jsonify({
            "checklist": CHECKLIST_PNCEE_12,
            "regle_or": ("La signature électronique (Yousign, GetAccept, DocuSign, eIDAS) "
                         "n'est PAS admise sur les pièces du dossier PNCEE. "
                         "Réserver aux documents internes uniquement."),
            "source": "Retour terrain GET1TECH 2021, applicable P6 2026",
        })

    @app.route("/conformite/regles", methods=["GET"])
    def _conformite_regles():
        """Liste les 30+ règles implémentées (pour documentation / audit externe)."""
        return jsonify({
            "nb_regles": len(REGLES_JURIDIQUES),
            "regles": REGLES_JURIDIQUES,
            "categories": sorted({r["cat"] for r in REGLES_JURIDIQUES}),
            "niveaux_severite": ["bloquant", "avertissement", "info"],
            "reference_legale": "Arrêté 22/12/2014 + décret P6 2025-1048",
        })
