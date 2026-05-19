"""
VALIDATION FICHES CEE
Mode normal : vérifie le minimum pour le moteur
Mode strict : vérifie tout pour la production
"""

import json
import os
import sys
import re

FICHES_PATH = os.path.join(os.path.dirname(__file__), "fiches.json")

SECTEURS_VALIDES = ["BAT", "IND", "RES", "AGRI", "TRA", "BAR"]
TYPES_VALIDES = ["surface", "unitaire", "complexe", "forfaitaire"]
ZONES = ["H1", "H2", "H3"]
REF_PATTERN = re.compile(r"^(BAT|IND|RES|AGRI|TRA|BAR)-[A-Z]{2,3}-\d{2,3}(?:-[A-Z0-9]+)?$")


def load():
    with open(FICHES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_fiche(fiche, strict=False):
    erreurs = []
    warnings = []

    # === BASIQUE ===

    ref = fiche.get("ref", "")
    if not ref:
        erreurs.append("ref manquante")
    elif not REF_PATTERN.match(ref):
        erreurs.append(f"ref format invalide: {ref}")

    secteur = fiche.get("secteur", "")
    if secteur not in SECTEURS_VALIDES:
        erreurs.append(f"secteur '{secteur}' invalide")

    ftype = fiche.get("type", "")
    if ftype not in TYPES_VALIDES:
        erreurs.append(f"type '{ftype}' invalide")

    # Cumac
    cu = fiche.get("cumac_unitaire")
    if cu in ("A REMPLIR", "A VERIFIER") and fiche.get("actif") is False:
        warnings.append(f"cumac_unitaire={cu!r} (fiche inactive, lookup ADEME requis)")
        cu = None  # skip downstream cumac checks
    elif cu is None or cu in ("A REMPLIR", "A VERIFIER"):
        erreurs.append("cumac_unitaire manquant")
    elif cu == "COMPLEXE" and ftype == "complexe":
        pass  # sentinel valide : cumac calculé via table/formule
    elif isinstance(cu, dict):
        has_zone = any(z in cu for z in ZONES)
        has_dom = "DOM" in cu and isinstance(cu.get("DOM"), (int, float)) and cu["DOM"] > 0
        has_zone_energie = any("_" in k for k in cu)
        if not has_zone and not has_zone_energie and not has_dom:
            erreurs.append("cumac: aucune zone reconnue")
        if has_zone and not has_dom:
            for z in ZONES:
                if z in cu and (not isinstance(cu[z], (int, float)) or cu[z] <= 0):
                    erreurs.append(f"cumac {z} invalide: {cu[z]}")
    elif isinstance(cu, (int, float)):
        if cu <= 0:
            erreurs.append(f"cumac invalide: {cu}")
    else:
        erreurs.append(f"cumac format inconnu: {type(cu)}")

    if not fiche.get("params"):
        erreurs.append("params manquants")

    # === STRICT ===

    if strict:
        if not fiche.get("nom"):
            erreurs.append("nom manquant")

        if not fiche.get("duree_vie"):
            warnings.append("duree_vie manquante")
        elif not (1 <= fiche["duree_vie"] <= 50):
            erreurs.append(f"duree_vie aberrante: {fiche['duree_vie']}")
        elif fiche["duree_vie"] < 3:
            warnings.append(f"duree_vie courte: {fiche['duree_vie']} ans (vérifier vs ADEME)")

        if not fiche.get("unite"):
            warnings.append("unite manquante")

        # conditions_texte: tracé en stat globale, pas en warning par fiche
        # (110/234 fiches sans doc — bruit inutile en mode strict)

        # Doublons dans params
        params = fiche.get("params", [])
        if len(params) != len(set(params)):
            erreurs.append("params en doublon")

        # Fiche abrogée: tracé en stat globale, pas en warning par fiche

        # Cumac cohérence H1 >= H2 >= H3 (généralement vrai)
        if isinstance(cu, dict):
            vals = []
            for z in ZONES:
                if z in cu and isinstance(cu[z], (int, float)):
                    vals.append(cu[z])
            if len(vals) == 3 and not (vals[0] >= vals[1] >= vals[2]):
                warnings.append(f"cumac ordre inhabituel: H1={vals[0]} H2={vals[1]} H3={vals[2]}")

        # Cumac valeurs réalistes
        if isinstance(cu, dict):
            for k, v in cu.items():
                if isinstance(v, (int, float)):
                    if v > 500000:
                        warnings.append(f"cumac {k}={v} suspicieusement élevé")

        elif isinstance(cu, (int, float)):
            if cu > 500000:
                warnings.append(f"cumac={cu} suspicieusement élevé")

    return erreurs, warnings


def main(strict=False):
    fiches = load()
    mode = "STRICT" if strict else "NORMAL"
    print(f"\n===== VALIDATION {mode} — {len(fiches)} FICHES =====\n")

    ok = 0
    ko = 0
    warn_count = 0
    inactive_count = sum(1 for f in fiches if f.get("actif") is False)
    no_conditions = sum(1 for f in fiches if not f.get("conditions_texte"))

    for f in fiches:
        erreurs, warnings = validate_fiche(f, strict)
        ref = f.get("ref", "???")

        if erreurs:
            ko += 1
            print(f"  FAIL  {ref}")
            for e in erreurs:
                print(f"        x {e}")
        else:
            ok += 1
            print(f"  OK    {ref}")

        if warnings:
            warn_count += len(warnings)
            for w in warnings:
                print(f"        ? {w}")

    print(f"\n{'='*45}")
    print(f"  OK: {ok} | FAIL: {ko} | WARNINGS: {warn_count}")
    print(f"  TOTAL: {len(fiches)} fiches")
    if strict:
        print(f"  Stats: {inactive_count} inactives | {no_conditions} sans conditions_texte")
    print(f"{'='*45}\n")

    return ko == 0


if __name__ == "__main__":
    strict = "--strict" in sys.argv
    success = main(strict)
    sys.exit(0 if success else 1)
