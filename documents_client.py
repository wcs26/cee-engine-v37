"""
Générateur unifié de documents CEE — header client réutilisé pour tous les docs.

Principe : 1 saisie du client (entreprise + représentant + SIRET + adresse + …)
→ génération auto de :
  • Rapport de gisement (format SIRAT)
  • Devis SIRAT (BAT-EN-103 ou autre)
  • Convention de mission diagnostic CEE 0€
  • Attestation sur l'honneur P6 2026 pré-remplie

Adaptable à TOUT client (pas que AHBFC). Header partagé via dataclass `ClientHeader`.

Endpoint principal :
  POST /documents/pack — retourne JSON {gisement, devis, convention, ah} avec HTML imprimables
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from flask import jsonify, request, Response

from gisement_sirat import (
    Site, calcul_gisement, COEFF_CUMAC, PRIX_TRAVAUX_HT_M2,
    PRIX_CUMAC_DEFAUT_EUR_MWHC, BAREME_SIRAT_APPORTEUR_TIERS,
    COMMISSION_PCT_MARGE_DEFAUT, TVA_DEFAUT, DELEGATAIRES_CONNUS,
)


# ─────────────────────────────────────────────────────────────────────
# HEADER CLIENT — utilisé en tête de TOUS les documents
# ─────────────────────────────────────────────────────────────────────

@dataclass
class ClientHeader:
    """Identité unique du bénéficiaire — réutilisée pour gisement, devis, convention, AH."""
    # Entreprise bénéficiaire
    raison_sociale: str = ""
    forme_juridique: str = ""        # SARL, SAS, Association, SCI, EHPAD…
    siret: str = ""                   # 14 chiffres établissement (le bon !)
    siren: str = ""                   # 9 chiffres
    rcs: str = ""                     # ex "RCS Paris"
    naf_ape: str = ""                 # code activité
    capital_social: str = ""

    # Adresse siège
    adresse: str = ""
    cp: str = ""
    ville: str = ""

    # Représentant légal (signataire)
    representant_civilite: str = ""   # M./Mme
    representant_prenom: str = ""
    representant_nom: str = ""
    representant_fonction: str = ""   # Gérant, Directeur, Président…

    # Référent terrain (peut différer du signataire)
    referent_nom: str = ""
    referent_tel: str = ""
    referent_email: str = ""

    # Contexte fiscal
    tva_intra: str = ""

    def lignes_identite(self) -> list[str]:
        """Lignes de présentation pour l'en-tête de doc."""
        out = [self.raison_sociale or "(raison sociale à renseigner)"]
        if self.forme_juridique:
            out[0] = f"{self.raison_sociale} ({self.forme_juridique})"
        if self.siret:
            out.append(f"SIRET : {self.siret}")
        elif self.siren:
            out.append(f"SIREN : {self.siren} ⚠️ SIRET établissement à compléter")
        if self.rcs:
            out.append(f"RCS : {self.rcs}")
        if self.naf_ape:
            out.append(f"Code NAF/APE : {self.naf_ape}")
        if self.tva_intra:
            out.append(f"TVA intra : {self.tva_intra}")
        if self.adresse:
            out.append(f"{self.adresse}, {self.cp} {self.ville}")
        if self.representant_nom:
            rep = f"Représentant : {self.representant_civilite} {self.representant_prenom} {self.representant_nom}".strip()
            if self.representant_fonction:
                rep += f" — {self.representant_fonction}"
            out.append(rep)
        if self.referent_nom:
            out.append(f"Référent terrain : {self.referent_nom}"
                      + (f" ({self.referent_tel})" if self.referent_tel else "")
                      + (f" {self.referent_email}" if self.referent_email else ""))
        return out


# ─────────────────────────────────────────────────────────────────────
# OPÉRATION — fiche CEE + surface + chantier
# ─────────────────────────────────────────────────────────────────────

@dataclass
class Operation:
    fiche: str = "BAT-EN-103"
    secteur: str = "sante"            # sante, tertiaire, industrie, residentiel
    zone: str = "H1"                  # H1, H2, H3
    surface_m2: float = 0
    nom_chantier: str = ""            # ex "MAGRITTE CEZANNE"
    adresse_chantier: str = ""
    cp_chantier: str = ""
    ville_chantier: str = ""
    isolant: str = "URSA RENOSOUDAL ALU 96mm R=3,00 m².K/W"
    hauteur_vs_m: float = 2.0
    # Override calcul (sinon utilise constantes calibrées)
    coeff_cumac_override: float | None = None        # MWhc/m² réel (si différent du défaut)
    prix_cumac_override: float | None = None         # €/MWhc négocié pour CE dossier
    prix_travaux_ht_m2_override: float | None = None # €/m² HT chantier (si négocié)


@dataclass
class DispositifCEE:
    """Acteurs du dispositif CEE — distinction juridique stricte.

    Chaîne réelle : POLLUEUR (obligé) → DÉLÉGATAIRE → MANDATAIRE/APPORTEUR → installateur RGE → bénéficiaire
    """
    # OBLIGÉ / POLLUEUR (vendeur d'énergie soumis à obligation : TotalEnergies, EDF, ENGIE…)
    obligé_nom: str = ""
    obligé_siret: str = ""

    # DÉLÉGATAIRE (collecte CEE pour le compte de l'obligé : Abokine, Économie d'Énergie SAS, Hellio…)
    delegataire_nom: str = ""
    delegataire_siret: str = ""
    delegataire_ref: str = ""

    # MANDATAIRE / APPORTEUR (intermédiaire commercial — toi via WCS Bulgarie)
    mandataire_nom: str = ""
    mandataire_siret_eik: str = ""

    # Mandat de cession des CEE (signé par bénéficiaire)
    mandat_num: str = ""
    mandat_date: str = ""             # YYYY-MM-DD
    emmy_dossier: str = ""            # n° dépôt registre national EMMY (post-validation PNCEE)


@dataclass
class Admin:
    """Champs administratifs nécessaires à la traçabilité du dossier."""
    dossier_num_interne: str = ""     # numérotation interne (ex DOSS-2026-001)
    bdc_num: str = ""                 # bon de commande client
    devis_num: str = ""               # numéro devis émetteur
    devis_date: str = ""              # YYYY-MM-DD signature devis = date d'engagement
    facture_num: str = ""
    facture_date: str = ""
    achevement_date: str = ""         # YYYY-MM-DD fin chantier
    depot_pncee_prevu: str = ""       # date prévisionnelle dépôt
    cofrac_organisme: str = ""        # bureau contrôle COFRAC missionné
    cofrac_rapport_num: str = ""

    # RGE installateur (obligatoire BAR/BAT)
    rge_qualification: str = ""       # Qualibat, Qualit'EnR, QualiPAC, RGE Travaux
    rge_numero: str = ""
    rge_validite_fin: str = ""        # YYYY-MM-DD

    # Assurance installateur
    assureur_police_num: str = ""
    assureur_decennale_num: str = ""

    # Charge d'affaire côté installateur
    charge_affaire_nom: str = ""
    charge_affaire_email: str = ""
    charge_affaire_tel: str = ""

    # ─── Financier interne (Mode vendeur uniquement, jamais en vue client) ───
    cout_reel_realisateur_eur: float | None = None  # coût réel SIRAT (matériaux + main d'œuvre + sous-traitance)
    commission_pct_marge: float | None = None       # % marge encaissée par Jimmy (50 % défaut)


# ─────────────────────────────────────────────────────────────────────
# Identité société émettrice (SIRAT par défaut, paramétrable)
# ─────────────────────────────────────────────────────────────────────

@dataclass
class Emetteur:
    """Société RÉALISATRICE des travaux (apparaît sur tous les docs).
    Pas la même chose que WCS qui est l'outil interne (jamais visible client)."""
    raison_sociale: str = "SIRAT"
    forme_juridique: str = "SARL"
    siret: str = "95117449900016"
    naf: str = "4329A"
    tva_intra: str = "FR13951174499"
    adresse: str = "1280 Avenue des Platanes"
    cp: str = "34970"
    ville: str = "LATTES"
    email: str = "direction@sirat-calo.com"
    tel: str = "07 83 52 73 25"
    site_web: str = "www.sirat-travaux.com"
    representant_nom: str = "Fouhad KHEMICI"
    representant_fonction: str = "Gérant"
    assureur: str = "MIC INSURANCE COMPANY"
    assureur_adresse: str = "Rue de l'Amiral Hamelin 75116 Paris (885 241 208 RCS Paris)"


def resolve_emetteur(d: dict) -> Emetteur:
    """Émetteur 100 % saisie manuelle — payload['emetteur'] = {raison_sociale, siret, ...}.
       Si rien → instance vide (champs à remplir)."""
    overrides = d.get("emetteur") or {}
    return Emetteur(**{k: v for k, v in overrides.items()
                       if k in Emetteur.__annotations__ and v is not None})


# ─────────────────────────────────────────────────────────────────────
# Helpers HTML
# ─────────────────────────────────────────────────────────────────────

def _e(s) -> str:
    return _html.escape(str(s) if s is not None else "")


_BASE_CSS = """
* { box-sizing:border-box; }
body { font-family:-apple-system,Helvetica,Arial,sans-serif; margin:24px; color:#222; }
h1 { color:#1f4068; border-bottom:3px solid #1f4068; padding-bottom:6px; margin:0 0 8px; }
h2 { color:#1f4068; margin:24px 0 8px; }
.header-strip { display:grid; grid-template-columns:2fr 1fr; gap:16px; padding:14px;
                background:#f4f7fb; border-left:5px solid #1f4068; border-radius:6px;
                margin-bottom:18px; font-size:13px; }
.header-strip .col h3 { margin:0 0 6px; color:#1f4068; font-size:14px; }
.header-strip ul { margin:0; padding-left:18px; }
.header-strip li { margin:2px 0; }
.warn-cell { background:#fff3cd; border-left:3px solid #f0ad4e; padding:6px 8px; margin:4px 0; }
table { border-collapse:collapse; width:100%; margin:8px 0; }
th,td { border:1px solid #ccc; padding:8px 12px; text-align:left; vertical-align:top; }
th { background:#1f4068; color:white; font-weight:600; }
.total { background:#fff8dc; font-weight:bold; }
.signe { margin-top:30px; display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.signe div { border:1px dashed #888; padding:14px; min-height:120px; }
.checklist { background:#f8f9fa; padding:10px; border-left:4px solid #1f4068; font-size:12px; margin-top:18px; }
.footer { margin-top:24px; padding-top:12px; border-top:1px solid #ccc; font-size:11px; color:#666; }
.badge { display:inline-block; background:#1f4068; color:white; padding:3px 8px; border-radius:3px; font-size:11px; }
"""


def _header_block(client: ClientHeader, emetteur: Emetteur, doc_type: str, doc_ref: str = "") -> str:
    """En-tête commun à tous les docs : émetteur (gauche) + bénéficiaire (droite) + type doc."""
    lignes = "".join(f"<li>{_e(l)}</li>" for l in client.lignes_identite())
    siret_warn = ""
    if not client.siret and client.siren:
        siret_warn = '<div class="warn-cell">⚠️ SIRET établissement (14 chiffres) absent — risque rejet PNCEE</div>'
    return f"""
<div class="header-strip">
  <div class="col">
    <h3>BÉNÉFICIAIRE</h3>
    <ul>{lignes}</ul>
    {siret_warn}
  </div>
  <div class="col">
    <h3>ÉMETTEUR</h3>
    <ul>
      <li><b>{_e(emetteur.raison_sociale)}</b> ({_e(emetteur.forme_juridique)})</li>
      <li>SIRET {_e(emetteur.siret)} · NAF {_e(emetteur.naf)}</li>
      <li>TVA {_e(emetteur.tva_intra)}</li>
      <li>{_e(emetteur.adresse)}, {_e(emetteur.cp)} {_e(emetteur.ville)}</li>
      <li>{_e(emetteur.tel)} · {_e(emetteur.email)}</li>
      <li>Représentant : {_e(emetteur.representant_nom)} ({_e(emetteur.representant_fonction)})</li>
    </ul>
    <div style="margin-top:6px;"><span class="badge">{_e(doc_type)}</span>
      {' · ' + _e(doc_ref) if doc_ref else ''}
      · {datetime.now().strftime("%d/%m/%Y")}</div>
  </div>
</div>
"""


def _checklist_pncee_html() -> str:
    return """
<div class="checklist">
  <b>Checklist PNCEE avant signature</b> — règles de fer (origine GET1TECH 2021) :<br>
  ✅ Imprimer COULEUR · feuille SIMPLE (pas recto-verso)<br>
  ✅ Date + « Bon pour accord » + signature : MANUSCRITS, encre BLEUE, MÊME stylo · année complète (2026, jamais 26)<br>
  ✅ AUCUNE mention « P/O » ou « au nom de » · signature électronique = NON pour PNCEE (sauf eIDAS Qualifié)<br>
  ✅ Tampon À CÔTÉ de la signature, ORIGINAL, lisible, UN SEUL, droit
</div>
"""


def _signature_block(client: ClientHeader, emetteur_label: str = "Pour l'entreprise réalisatrice") -> str:
    return f"""
<div class="signe">
  <div><b>Pour {_e(client.raison_sociale or "le bénéficiaire")}</b><br><br>
    Nom : {_e(client.representant_nom or "__________________")}<br>
    Fonction : {_e(client.representant_fonction or "__________________")}<br><br>
    Date : ____ / ____ / {datetime.now().year}<br><br>
    « Bon pour accord » + Signature manuscrite encre bleue + cachet :</div>
  <div><b>{_e(emetteur_label)}</b><br><br>
    Nom : __________________<br>
    Fonction : __________________<br><br>
    Date : ____ / ____ / {datetime.now().year}<br><br>
    Signature et cachet :</div>
</div>
"""


# ─────────────────────────────────────────────────────────────────────
# 1. RAPPORT DE GISEMENT
# ─────────────────────────────────────────────────────────────────────

def _bloc_dispositif(disp: DispositifCEE) -> str:
    if not any([disp.obligé_nom, disp.delegataire_nom, disp.mandataire_nom]):
        return ""
    rows = []
    if disp.obligé_nom:
        rows.append(f"<tr><th>Obligé / Pollueur</th><td>{_e(disp.obligé_nom)} {('SIRET '+_e(disp.obligé_siret)) if disp.obligé_siret else ''}</td></tr>")
    if disp.delegataire_nom:
        rows.append(f"<tr><th>Délégataire CEE</th><td>{_e(disp.delegataire_nom)} {('réf '+_e(disp.delegataire_ref)) if disp.delegataire_ref else ''} {('SIRET '+_e(disp.delegataire_siret)) if disp.delegataire_siret else ''}</td></tr>")
    if disp.mandataire_nom:
        rows.append(f"<tr><th>Mandataire / Apporteur</th><td>{_e(disp.mandataire_nom)} {('EIK/SIRET '+_e(disp.mandataire_siret_eik)) if disp.mandataire_siret_eik else ''}</td></tr>")
    if disp.mandat_num or disp.mandat_date:
        rows.append(f"<tr><th>Mandat de cession CEE</th><td>n° {_e(disp.mandat_num or '—')} signé le {_e(disp.mandat_date or '—')}</td></tr>")
    if disp.emmy_dossier:
        rows.append(f"<tr><th>Dossier EMMY</th><td>{_e(disp.emmy_dossier)}</td></tr>")
    return f"<h2>Dispositif CEE</h2><table>{''.join(rows)}</table>"


def _filter_calc_for_vue(calc: dict, vue: str) -> dict:
    """Vue client : masque les champs financiers internes (coût réel, marge, commission Jimmy).
    Vue interne : retourne tout."""
    if vue == "interne":
        return calc
    masked = {"cout_reel_realisateur_eur", "marge_nette_eur",
              "commission_jimmy_eur", "commission_pct_marge_applique",
              "commission_calculable", "reference_apporteur_tiers_eur"}
    return {k: v for k, v in calc.items() if k not in masked}


def _bloc_commission_interne(calc: dict, admin: Admin) -> str:
    """Bloc visible UNIQUEMENT en mode vendeur (vue=interne).
    Affiche prime obligé / coût réel / marge / commission Jimmy."""
    if calc.get('commission_calculable'):
        commission_str = f"<b>{calc['commission_jimmy_eur']:,.2f} €</b>"
        marge_str = f"{calc['marge_nette_eur']:,.2f} €"
        cout_str = f"{calc['cout_reel_realisateur_eur']:,.2f} €"
    else:
        commission_str = "<i>non calculable (saisir coût réel SIRAT)</i>"
        marge_str = "<i>—</i>"
        cout_str = "<i>non saisi</i>"
    ref = calc.get('reference_apporteur_tiers_eur', 0) or 0
    return f"""
<h2 style="color:#b00;">🔒 MODE VENDEUR — Compartiment financier interne</h2>
<table style="background:#fff8e1; border:2px solid #b00;">
  <tr><th>Prime encaissée par l'obligé</th><td>{calc['prime_obligé_eur']:,.2f} €</td></tr>
  <tr><th>Coût réel installateur (matériaux + MO + S/T)</th><td>{cout_str}</td></tr>
  <tr><th>Marge nette dispositif (prime − coût réel)</th><td><b>{marge_str}</b></td></tr>
  <tr><th>% de marge alloué à Jimmy / WCS</th><td>{calc.get('commission_pct_marge_applique', 50):.0f} %</td></tr>
  <tr style="background:#ffe082;"><th>💰 Commission Jimmy / WCS</th><td>{commission_str}</td></tr>
  <tr><td colspan="2" style="font-size:11px; color:#666;">
    Référence barème SIRAT apporteur tiers (BAT-EN-103/101 santé H1) : {ref:,.2f} € — pour comparaison uniquement.
  </td></tr>
</table>
<p style="font-size:11px; color:#b00;">⚠️ Ce bloc est masqué en vue client. Ne JAMAIS imprimer ce document si remis au bénéficiaire.</p>
"""


def _bloc_admin(admin: Admin) -> str:
    if not any(asdict(admin).values()):
        return ""
    rows = []
    if admin.dossier_num_interne: rows.append(f"<tr><th>N° dossier interne</th><td>{_e(admin.dossier_num_interne)}</td></tr>")
    if admin.bdc_num: rows.append(f"<tr><th>BDC</th><td>{_e(admin.bdc_num)}</td></tr>")
    if admin.devis_date: rows.append(f"<tr><th>Date d'engagement (devis signé)</th><td>{_e(admin.devis_date)}</td></tr>")
    if admin.achevement_date: rows.append(f"<tr><th>Date achèvement travaux</th><td>{_e(admin.achevement_date)}</td></tr>")
    if admin.depot_pncee_prevu: rows.append(f"<tr><th>Dépôt PNCEE prévu</th><td>{_e(admin.depot_pncee_prevu)}</td></tr>")
    if admin.facture_num: rows.append(f"<tr><th>Facture</th><td>n° {_e(admin.facture_num)} du {_e(admin.facture_date or '—')}</td></tr>")
    if admin.rge_numero: rows.append(f"<tr><th>RGE installateur</th><td>{_e(admin.rge_qualification)} n° {_e(admin.rge_numero)} (valide jusqu'au {_e(admin.rge_validite_fin or '—')})</td></tr>")
    if admin.cofrac_organisme: rows.append(f"<tr><th>Bureau contrôle COFRAC</th><td>{_e(admin.cofrac_organisme)} {('rapport '+_e(admin.cofrac_rapport_num)) if admin.cofrac_rapport_num else ''}</td></tr>")
    if admin.assureur_decennale_num: rows.append(f"<tr><th>Décennale</th><td>{_e(admin.assureur_decennale_num)}</td></tr>")
    if admin.charge_affaire_nom: rows.append(f"<tr><th>Chargé d'affaire</th><td>{_e(admin.charge_affaire_nom)} {_e(admin.charge_affaire_tel)} {_e(admin.charge_affaire_email)}</td></tr>")
    return f"<h2>Suivi administratif</h2><table>{''.join(rows)}</table>" if rows else ""


def doc_gisement(client: ClientHeader, op: Operation, em: Emetteur,
                 disp: DispositifCEE, admin: Admin, calc: dict, vue: str = "client") -> str:
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>Gisement CEE — {_e(op.nom_chantier)}</title><style>{_BASE_CSS}</style></head><body>

<h1>Rapport de Gisement CEE — {_e(op.nom_chantier)}</h1>
{_header_block(client, em, "RAPPORT DE GISEMENT")}

<h2>Site & opération</h2>
<table>
  <tr><th>Site</th><td>{_e(op.nom_chantier)}</td>
      <th>Adresse</th><td>{_e(op.adresse_chantier)}, {_e(op.cp_chantier)} {_e(op.ville_chantier)}</td></tr>
  <tr><th>Zone climatique</th><td>{_e(op.zone)}</td>
      <th>Secteur</th><td>{_e(op.secteur)}</td></tr>
  <tr><th>Fiche CEE</th><td>{_e(op.fiche)}</td>
      <th>Surface concernée</th><td>{op.surface_m2:,.0f} m²</td></tr>
</table>

<h2>Gisement chiffré</h2>
<table>
  <tr><th>Coefficient cumac</th><th>MWh cumac</th><th>GWh cumac</th><th>Prix obligé</th><th>Prime CEE</th><th>Reste à charge</th></tr>
  <tr><td>{calc['coeff_mwhc_m2']} MWhc/m² <small>({_e(calc.get('coeff_source',''))})</small></td>
      <td><b>{calc['mwhc']:,.1f}</b></td><td>{calc['gwhc']:.3f}</td>
      <td>{calc['prix_cumac_eur_mwhc']:.2f} €/MWhc</td>
      <td class="total">{calc['prime_obligé_eur']:,.2f} €</td>
      <td class="total">{calc['reste_a_charge_eur']:,.2f} €</td></tr>
</table>
{_bloc_dispositif(disp)}
{_bloc_admin(admin)}

<h2>Solution technique</h2>
<p><b>Isolant :</b> {_e(op.isolant)} · <b>Hauteur VS :</b> {op.hauteur_vs_m:.2f} m</p>
<p>Méthodologie : nettoyage support → tests d'arrachement → fixation mécanique →
  jonctions ALU TAPE → DOE → contrôle COFRAC. Durée 4-6 semaines.</p>

{_bloc_commission_interne(calc, admin) if vue == 'interne' else ''}

{_checklist_pncee_html()}
{_signature_block(client, f"Pour {em.raison_sociale}")}

<div class="footer">Coefficient {calc['coeff_mwhc_m2']} MWhc/m² · vue : <b>{vue}</b>.</div>

</body></html>"""


# ─────────────────────────────────────────────────────────────────────
# 2. DEVIS (format SIRAT)
# ─────────────────────────────────────────────────────────────────────

def doc_devis(client: ClientHeader, op: Operation, em: Emetteur,
              disp: DispositifCEE, admin: Admin, calc: dict, devis_num: str,
              vue: str = "client") -> str:
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>Devis {_e(devis_num)} — {_e(op.nom_chantier)}</title><style>{_BASE_CSS}</style></head><body>

<h1>Devis n° {_e(devis_num)}</h1>
{_header_block(client, em, "DEVIS", devis_num)}

<h2>Chantier</h2>
<table>
  <tr><th>Désignation</th><td>{_e(op.fiche)} — Mise en place d'isolant sous plancher bas vide sanitaire</td></tr>
  <tr><th>Adresse chantier</th><td>{_e(op.adresse_chantier)}, {_e(op.cp_chantier)} {_e(op.ville_chantier)}</td></tr>
  <tr><th>Zone</th><td>{_e(op.zone)} · <b>Secteur :</b> {_e(op.secteur)}</td></tr>
  <tr><th>Isolant</th><td>{_e(op.isolant)}</td></tr>
</table>

<h2>Détail prestation</h2>
<table>
  <tr><th>Référence</th><th>Désignation</th><th>Unité</th><th>Quantité</th><th>PU HT</th><th>Total HT</th><th>TVA</th></tr>
  <tr>
    <td>{_e(op.fiche)}</td>
    <td>Pose isolant en sous-face de plancher (fixation mécanique, jonctions ALU TAPE,
        DOE, contrôle COFRAC final)</td>
    <td>m²</td>
    <td>{op.surface_m2:,.0f}</td>
    <td>{calc['prix_travaux_ht_m2']:.2f} €</td>
    <td>{calc['ht_eur']:,.2f} €</td>
    <td>20 %</td>
  </tr>
</table>

<table style="margin-top:14px;">
  <tr><th colspan="2">Récapitulatif</th></tr>
  <tr><td>Total HT</td><td>{calc['ht_eur']:,.2f} €</td></tr>
  <tr><td>TVA 20 %</td><td>{calc['tva_eur']:,.2f} €</td></tr>
  <tr><td>Total TTC</td><td><b>{calc['ttc_eur']:,.2f} €</b></td></tr>
  <tr class="total"><td>Prime CEE versée par {_e(disp.delegataire_nom or '(délégataire à renseigner)')} {('réf '+_e(disp.delegataire_ref)) if disp.delegataire_ref else ''}</td>
      <td><b>− {calc['prime_obligé_eur']:,.2f} €</b></td></tr>
  <tr class="total"><td><b>Reste à payer</b></td><td><b>{calc['reste_a_charge_eur']:,.2f} €</b></td></tr>
</table>
{_bloc_dispositif(disp)}
{_bloc_admin(admin)}

<p style="margin-top:14px; font-size:12px;">
  Prime CEE {_e(disp.delegataire_nom)} {('- '+_e(disp.delegataire_ref)) if disp.delegataire_ref else ''}
  d'un montant de {calc['prime_obligé_eur']:,.2f} € — TVA non applicable.<br>
  Assurance RC + décennale : {_e(em.assureur)} — {_e(em.assureur_adresse)}.
</p>

{_bloc_commission_interne(calc, admin) if vue == 'interne' else ''}

{_checklist_pncee_html()}
{_signature_block(client, f"Pour {em.raison_sociale}")}

<div class="footer">{_e(em.raison_sociale)} · {_e(em.adresse)}, {_e(em.cp)} {_e(em.ville)} ·
  SIRET {_e(em.siret)} · NAF {_e(em.naf)} · TVA {_e(em.tva_intra)}</div>

</body></html>"""


# ─────────────────────────────────────────────────────────────────────
# 3. CONVENTION DE MISSION (visite technique 0€)
# ─────────────────────────────────────────────────────────────────────

def doc_convention(client: ClientHeader, op: Operation, em: Emetteur,
                   disp: DispositifCEE, admin: Admin) -> str:
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>Convention de mission — {_e(client.raison_sociale)}</title><style>{_BASE_CSS}</style></head><body>

<h1>Convention de mission — Diagnostic CEE 0€</h1>
{_header_block(client, em, "CONVENTION DE MISSION")}

<h2>Article 1 — Objet de la mission</h2>
<p>La présente convention encadre une mission de <b>diagnostic énergétique opérationnel</b>
  visant à identifier les gisements de financement CEE (Certificats d'Économies d'Énergie)
  valorisables à <b>0 € net</b> pour {_e(client.raison_sociale)}, et à éviter tout déplacement
  inutile.</p>
<ul>
  <li>✓ Mission prise en charge sous maîtrise d'ouvrage confiée</li>
  <li>✓ Aucun engagement sur travaux à ce stade</li>
  <li>✓ Durée : 6 mois à compter de la signature</li>
</ul>

<h2>Article 2 — Périmètre et livrables</h2>
<table>
  <tr><th>Site</th><td>{_e(op.nom_chantier)} — {_e(op.adresse_chantier)}, {_e(op.cp_chantier)} {_e(op.ville_chantier)}</td></tr>
  <tr><th>Surface concernée</th><td>{op.surface_m2:,.0f} m² (zone {_e(op.zone)}, secteur {_e(op.secteur)})</td></tr>
  <tr><th>Opérations visées</th><td>{_e(op.fiche)} et autres fiches éligibles détectées en visite</td></tr>
</table>
<p><b>Livrables remis au bénéficiaire :</b> rapport technique avec photos · tableau gisements
  0 € vs reste à charge · estimation primes (MWhc & €) · projection économies sur 3 ans ·
  préconisations priorisées · check-list de preuves dossier PNCEE.</p>

<h2>Article 3 — Engagements du bénéficiaire</h2>
<ul>
  <li>Accès complet aux locaux techniques, combles, vide sanitaire, chaufferie</li>
  <li>Mise à disposition factures énergies 2022-2025, plans, contrats maintenance</li>
  <li>Présence d'un interlocuteur habilité ({_e(client.referent_nom or "à désigner")}) une demi-journée</li>
  <li>Respect du calendrier convenu</li>
</ul>

<h2>Article 4 — Modalités financières</h2>
<p>Phase de diagnostic <b>intégralement prise en charge</b>. En cas de réalisation ultérieure
  des travaux : devis détaillé pour chaque poste, montants CEE déduits, reste à charge
  clairement indiqué. Le bénéficiaire conserve l'entière liberté de donner suite ou non.</p>

<h2>Article 5 — Calendrier</h2>
<table>
  <tr><th>J0</th><th>J+15</th><th>J+36</th><th>6 mois</th></tr>
  <tr><td>Signature</td><td>Visite technique</td><td>Remise livrables</td><td>Validité fin</td></tr>
</table>

{_signature_block(client, f"Pour {em.raison_sociale}")}

<div class="footer">Mission confiée à : {_e(em.raison_sociale)} — Convention 2 exemplaires originaux ·
  CEE régis par les articles L. 221-1 et suivants du Code de l'énergie · fiches en vigueur P6 2026.</div>

</body></html>"""


# ─────────────────────────────────────────────────────────────────────
# 4. ATTESTATION SUR L'HONNEUR (P6 2026)
# ─────────────────────────────────────────────────────────────────────

def doc_ah(client: ClientHeader, op: Operation, em: Emetteur,
           disp: DispositifCEE, admin: Admin, calc: dict, devis_num: str = "") -> str:
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<title>Attestation sur l'honneur — {_e(op.nom_chantier)}</title><style>{_BASE_CSS}</style></head><body>

<h1>Attestation sur l'honneur — Fiche {_e(op.fiche)}</h1>
{_header_block(client, em, "ATTESTATION SUR L'HONNEUR P6", devis_num)}

<h2>Partie A — Identification de l'opération</h2>
<table>
  <tr><th>Fiche d'opération standardisée</th><td><b>{_e(op.fiche)}</b></td></tr>
  <tr><th>Nature des travaux</th><td>Isolation d'un plancher bas (vide sanitaire / sous-sol non chauffé)</td></tr>
  <tr><th>Site des travaux</th><td>{_e(op.nom_chantier)} — {_e(op.adresse_chantier)}, {_e(op.cp_chantier)} {_e(op.ville_chantier)}</td></tr>
  <tr><th>Zone climatique</th><td>{_e(op.zone)}</td></tr>
  <tr><th>Secteur d'activité</th><td>{_e(op.secteur)}</td></tr>
  <tr><th>Surface concernée</th><td>{op.surface_m2:,.0f} m²</td></tr>
  <tr><th>Résistance thermique installée</th><td>R ≥ 3,0 m².K/W</td></tr>
  <tr><th>Date d'engagement (devis signé)</th><td>{_e(admin.devis_date) or '____ / ____ / 2026 (à compléter manuscrit encre bleue)'}</td></tr>
  <tr><th>Date d'achèvement des travaux</th><td>{_e(admin.achevement_date) or '____ / ____ / 2026 (à compléter manuscrit encre bleue)'}</td></tr>
  <tr><th>Cumac généré</th><td>{calc.get('mwhc',0):,.1f} MWhc</td></tr>
</table>
{_bloc_dispositif(disp)}
{_bloc_admin(admin)}

<h2>Partie B — Engagements du bénéficiaire</h2>
<p>Je soussigné(e), <b>{_e(client.representant_civilite)} {_e(client.representant_prenom)} {_e(client.representant_nom)}</b>,
  agissant en qualité de <b>{_e(client.representant_fonction)}</b> de
  <b>{_e(client.raison_sociale)}</b> (SIRET {_e(client.siret) or "⚠️ À COMPLÉTER 14 chiffres"}),
  atteste sur l'honneur :</p>
<ul>
  <li>être bénéficiaire des travaux réalisés à l'adresse mentionnée ci-dessus ;</li>
  <li>n'avoir signé aucune attestation similaire pour la même opération avec une autre
      personne morale, conformément à l'article L. 221-7 du Code de l'énergie et à
      l'article 441-7 du Code pénal (faux et usage de faux) ;</li>
  <li>autoriser {_e(disp.delegataire_nom or '(délégataire à renseigner)')} {('réf '+_e(disp.delegataire_ref)) if disp.delegataire_ref else ''} à valoriser les
      certificats d'économies d'énergie générés par cette opération au registre national EMMY
      pour le compte de {_e(disp.obligé_nom or '(obligé à renseigner)')} ;</li>
  <li>certifier l'exactitude des informations communiquées (surface, performance technique,
      dates) ;</li>
  <li>conserver pendant <b>9 ans</b> à compter de la délivrance des CEE
      (arrêté du 4 septembre 2014 art. 6, avis PNCEE) tous les documents
      justificatifs (devis, facture, DOE, photos avant/après).</li>
</ul>

<h2>Partie C — Engagements du professionnel</h2>
<p>{_e(em.raison_sociale)} (SIRET {_e(em.siret)}), représentée par {_e(em.representant_nom)}
  ({_e(em.representant_fonction)}), atteste avoir réalisé l'opération conformément à la
  fiche {_e(op.fiche)} en vigueur sur la période P6 du dispositif CEE (arrêté du
  21 décembre 2025), avoir transmis exclusivement les documents de monétisation à
  {_e(disp.delegataire_nom or '(délégataire)')}, et n'avoir signé aucune attestation
  similaire pour la même opération avec une autre entité.</p>

<h2>Mentions CNIL</h2>
<p style="font-size:12px;">Les informations recueillies font l'objet d'un traitement informatique
  destiné à l'instruction du dossier de demande de certificats d'économies d'énergie auprès
  du Pôle National des CEE (PNCEE). Conformément au RGPD et à la loi Informatique et Libertés,
  vous disposez d'un droit d'accès, de rectification et de suppression des données vous
  concernant.</p>

{_checklist_pncee_html()}
{_signature_block(client, f"Pour {em.raison_sociale}")}

<div class="footer">Attestation conforme arrêté 4/9/2014 modifié + arrêté 21/12/2025 (P6) ·
  Parties B et C saisies dactylographiquement avant signature manuscrite (encre bleue obligatoire).</div>

</body></html>"""


# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────

def _build_models(d: dict) -> tuple[ClientHeader, Operation, Emetteur, DispositifCEE, Admin]:
    cli = ClientHeader(**{k: v for k, v in (d.get("client") or {}).items()
                          if k in ClientHeader.__annotations__})
    op = Operation(**{k: v for k, v in (d.get("operation") or {}).items()
                      if k in Operation.__annotations__})
    em = resolve_emetteur(d)
    disp = DispositifCEE(**{k: v for k, v in (d.get("dispositif") or {}).items()
                            if k in DispositifCEE.__annotations__})
    admin = Admin(**{k: v for k, v in (d.get("admin") or {}).items()
                     if k in Admin.__annotations__})
    return cli, op, em, disp, admin


def register_documents_routes(app) -> None:

    # V37.3.40 — Gate JWT activé seulement si CEE_AUTH_REQUIRED=1.
    from functools import wraps as _wraps
    import os as _os

    def _gate(f):
        @_wraps(f)
        def _w(*a, **k):
            if _os.environ.get("CEE_AUTH_REQUIRED", "0") == "1":
                from auth import jwt_verify
                from flask import request as _req, jsonify as _jsn
                ah = _req.headers.get("Authorization", "")
                tok = ah[7:].strip() if ah.lower().startswith("bearer ") else ""
                if not tok or not jwt_verify(tok):
                    return _jsn({"error": "Unauthorized — JWT Bearer requis"}), 401
            return f(*a, **k)
        return _w


    @app.route("/documents/schema", methods=["GET"])
    @_gate
    def _doc_schema():
        """Renvoie le schéma JSON attendu pour générer un pack."""
        return jsonify({
            "client": list(ClientHeader.__annotations__.keys()),
            "operation": list(Operation.__annotations__.keys()),
            "emetteur": list(Emetteur.__annotations__.keys()),
            "dispositif": list(DispositifCEE.__annotations__.keys()),
            "admin": list(Admin.__annotations__.keys()),
            "exemple": {
                "client": asdict(ClientHeader(
                    raison_sociale="EHPAD Saint-Joseph",
                    forme_juridique="Association loi 1901",
                    siret="12345678901234",
                    siren="123456789",
                    naf_ape="8710A",
                    adresse="12 rue des Tilleuls",
                    cp="69001", ville="Lyon",
                    representant_civilite="M.",
                    representant_prenom="Pierre", representant_nom="Martin",
                    representant_fonction="Directeur",
                    referent_nom="Marie Durand", referent_tel="06 00 00 00 00",
                )),
                "operation": asdict(Operation(
                    fiche="BAT-EN-103", secteur="sante", zone="H1",
                    surface_m2=1850,
                    nom_chantier="EHPAD ST-JOSEPH BÂT A",
                    adresse_chantier="12 rue des Tilleuls",
                    cp_chantier="69001", ville_chantier="Lyon",
                )),
                "emetteur": "Optionnel — par défaut SIRAT",
            },
            "delegataires_connus": DELEGATAIRES_CONNUS,
        })

    @app.route("/documents/pack", methods=["POST"])
    @_gate
    def _doc_pack():
        """Génère les 4 documents (gisement, devis, convention, AH) en JSON HTML."""
        d = request.json or {}
        cli, op, em, disp, admin = _build_models(d)
        if op.surface_m2 <= 0:
            return jsonify({"error": "operation.surface_m2 > 0 requis"}), 400
        site = Site(nom=op.nom_chantier, adresse=op.adresse_chantier,
                    cp=op.cp_chantier, ville=op.ville_chantier,
                    zone=op.zone, secteur=op.secteur, surface_m2=op.surface_m2,
                    fiche=op.fiche, hauteur_vs_m=op.hauteur_vs_m, isolant=op.isolant,
                    delegataire=disp.delegataire_nom, delegataire_ref=disp.delegataire_ref,
                    referent_nom=cli.referent_nom, referent_tel=cli.referent_tel,
                    beneficiaire=cli.raison_sociale, siret_beneficiaire=cli.siret,
                    signataire_nom=f"{cli.representant_prenom} {cli.representant_nom}".strip(),
                    signataire_fonction=cli.representant_fonction)
        calc = calcul_gisement(
            site,
            coeff_override=op.coeff_cumac_override,
            prix_cumac_override=op.prix_cumac_override,
            prix_ht_m2_override=op.prix_travaux_ht_m2_override,
            cout_reel_realisateur_eur=admin.cout_reel_realisateur_eur,
            commission_pct_marge=admin.commission_pct_marge,
        )
        if "error" in calc:
            return jsonify({"error": calc["error"]}), 400
        devis_num = admin.devis_num or f"DE {datetime.now().strftime('%y%m')}{datetime.now().strftime('%H%M%S')[-3:]}"

        # Vue : "client" (par défaut, masque tout financier interne) ou "interne" (mode vendeur, tout visible)
        vue = (request.args.get("vue") or d.get("vue") or "client").lower()
        if vue not in ("client", "interne"):
            vue = "client"

        return jsonify({
            "vue": vue,
            "calcul": _filter_calc_for_vue(calc, vue),
            "documents": {
                "gisement_html":   doc_gisement(cli, op, em, disp, admin, calc, vue),
                "devis_html":      doc_devis(cli, op, em, disp, admin, calc, devis_num, vue),
                "convention_html": doc_convention(cli, op, em, disp, admin),
                "ah_html":         doc_ah(cli, op, em, disp, admin, calc, devis_num),
            },
            "devis_num": devis_num,
            "warnings": [w for w in [
                "Bénéficiaire : SIRET établissement vide — risque rejet PNCEE" if not cli.siret else None,
                "Bénéficiaire : représentant légal non renseigné" if not cli.representant_nom else None,
                "Chantier : adresse vide" if not op.adresse_chantier else None,
                "Émetteur : SIRET non renseigné" if not em.siret else None,
                "Dispositif : obligé/pollueur non renseigné" if not disp.obligé_nom else None,
                "Dispositif : délégataire non renseigné" if not disp.delegataire_nom else None,
                "Admin : RGE installateur non renseigné (bloquant BAR/BAT)" if not admin.rge_numero and op.fiche.startswith(("BAR","BAT")) else None,
                "Admin : date d'engagement (devis_date) absente" if not admin.devis_date else None,
                "Calcul : reste à charge non nul = " + f"{calc['reste_a_charge_eur']:.2f}€" if calc.get('reste_a_charge_eur',0) > 0 else None,
                "Mode vendeur : coût réel SIRAT non saisi → commission Jimmy non calculable" if vue == "interne" and not calc.get('commission_calculable') else None,
            ] if w],
        })

    @app.route("/documents/<doc_type>.html", methods=["POST"])
    @_gate
    def _doc_single(doc_type):
        """Génère 1 document HTML standalone : gisement | devis | convention | ah."""
        if doc_type not in {"gisement", "devis", "convention", "ah"}:
            return Response("type inconnu (gisement|devis|convention|ah)", status=400)
        d = request.json or {}
        cli, op, em, disp, admin = _build_models(d)
        if op.surface_m2 <= 0:
            return Response("operation.surface_m2 > 0 requis", status=400)
        site = Site(nom=op.nom_chantier, adresse=op.adresse_chantier,
                    cp=op.cp_chantier, ville=op.ville_chantier,
                    zone=op.zone, secteur=op.secteur, surface_m2=op.surface_m2,
                    fiche=op.fiche, hauteur_vs_m=op.hauteur_vs_m, isolant=op.isolant)
        calc = calcul_gisement(site,
                               coeff_override=op.coeff_cumac_override,
                               prix_cumac_override=op.prix_cumac_override,
                               prix_ht_m2_override=op.prix_travaux_ht_m2_override,
                               cout_reel_realisateur_eur=admin.cout_reel_realisateur_eur,
                               commission_pct_marge=admin.commission_pct_marge)
        if "error" in calc:
            return Response(calc["error"], status=400)
        devis_num = admin.devis_num or d.get("devis_num") or f"DE {datetime.now().strftime('%y%m')}001"
        vue = (request.args.get("vue") or d.get("vue") or "client").lower()
        if vue not in ("client", "interne"):
            vue = "client"
        gen = {
            "gisement":   lambda: doc_gisement(cli, op, em, disp, admin, calc, vue),
            "devis":      lambda: doc_devis(cli, op, em, disp, admin, calc, devis_num, vue),
            "convention": lambda: doc_convention(cli, op, em, disp, admin),
            "ah":         lambda: doc_ah(cli, op, em, disp, admin, calc, devis_num),
        }[doc_type]()
        return Response(gen, mimetype="text/html; charset=utf-8")

    @app.route("/documents/preremplir/<siret>", methods=["GET"])
    @_gate
    def _doc_preremplir(siret):
        """Pré-remplit un ClientHeader à partir d'un SIRET via le moteur /siret/search.
        Param `?cible=client|emetteur|obligé|delegataire` (sémantique uniquement)."""
        siret = (siret or "").strip().replace(" ", "")
        if not siret.isdigit() or len(siret) != 14:
            return jsonify({"error": "SIRET invalide (14 chiffres requis)"}), 400
        from urllib.request import urlopen, Request
        from urllib.error import URLError
        import json as _json
        try:
            host = request.host_url.rstrip("/")
            req = Request(f"{host}/siret/search?q={siret}", headers={"User-Agent": "CEE-Engine"})
            with urlopen(req, timeout=10) as r:
                data = _json.loads(r.read())
        except (URLError, Exception) as e:
            return jsonify({"error": f"recherche SIRET échouée : {e}"}), 502
        results = data.get("results") or []
        if not results:
            return jsonify({"error": f"SIRET {siret} introuvable"}), 404
        ent = results[0]
        match = None
        for et in (ent.get("matching_etablissements") or []):
            if et.get("siret") == siret:
                match = et; break
        if match is None:
            match = ent.get("siege") or {}
        client_filled = ClientHeader(
            raison_sociale=ent.get("nom_complet") or ent.get("nom_raison_sociale", ""),
            forme_juridique=ent.get("nature_juridique", ""),
            siret=match.get("siret") or siret,
            siren=ent.get("siren", ""),
            naf_ape=ent.get("activite_principale") or match.get("activite_principale", ""),
            capital_social=str(ent.get("capital_social") or ""),
            adresse=match.get("adresse") or match.get("geo_adresse", ""),
            cp=match.get("code_postal", ""),
            ville=match.get("libelle_commune") or match.get("commune", ""),
        )
        return jsonify({
            "cible": (request.args.get("cible") or "client").lower(),
            "siret": siret,
            "preremplissage": asdict(client_filled),
            "completude": sum(1 for v in asdict(client_filled).values() if v),
            "champs_a_completer_manuellement": [
                "representant_civilite", "representant_prenom", "representant_nom",
                "representant_fonction", "referent_nom", "referent_tel", "referent_email",
                "tva_intra", "rcs",
            ],
        })
