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

SECTEURS_VALIDES = ["BAT", "IND", "RES", "AGR", "TRA"]
TYPES_VALIDES = ["surface", "unitaire"]
ZONES = ["H1", "H2", "H3"]
REF_PATTERN = re.compile(r"^(BAT|IND|RES|AGR|TRA)-[A-Z]{2}-\d{2,3}$")


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
    if cu is None or cu in ("A REMPLIR", "A VERIFIER"):
        erreurs.append("cumac_unitaire manquant")
    elif isinstance(cu, dict):
        has_zone = any(z in cu for z in ZONES)
        has_zone_energie = any("_" in k for k in cu)
        if not has_zone and not has_zone_energie:
            erreurs.append("cumac: aucune zone reconnue")
        if has_zone:
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
        elif not (5 <= fiche["duree_vie"] <= 50):
            erreurs.append(f"duree_vie aberrante: {fiche['duree_vie']}")

        if not fiche.get("unite"):
            warnings.append("unite manquante")

        if not fiche.get("conditions_texte"):
            warnings.append("conditions_texte manquantes")

        # Doublons dans params
        params = fiche.get("params", [])
        if len(params) != len(set(params)):
            erreurs.append("params en doublon")

        # Fiche abrogée
        if fiche.get("actif") is False:
            warnings.append("fiche marquee INACTIVE/ABROGEE")

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
    print(f"{'='*45}\n")

    return ko == 0


if __name__ == "__main__":
    strict = "--strict" in sys.argv
    success = main(strict)
    sys.exit(0 if success else 1)
