#!/usr/bin/env python3
"""
MERGE ORACLE → CEE_ENGINE
Extrait les données d'Oracle V34 ULTIMATE et les fusionne dans le moteur CEE.
- Fiches: merge 224 Oracle + 162 Engine → fiches enrichies
- Cout travaux, deadlines, FOST factors → fichiers JSON séparés
"""

import json
import re
import os

HTML_PATH = os.path.expanduser("~/Downloads/WCS_ORACLE_V34_ULTIMATE.html")
ENGINE_DIR = os.path.dirname(__file__)
FICHES_PATH = os.path.join(ENGINE_DIR, "fiches.json")


def read_html():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


def extract_js_object(html, var_name):
    """Extrait un objet/array JS assigné à une variable."""
    # Cherche: const VAR = { ... }; ou const VAR = [ ... ];
    pattern = rf'(?:const|let|var)\s+{var_name}\s*=\s*'
    match = re.search(pattern, html)
    if not match:
        return None

    start = match.end()
    opener = html[start]
    closer = '}' if opener == '{' else ']'

    depth = 0
    i = start
    while i < len(html):
        c = html[i]
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                raw = html[start:i + 1]
                return raw
        elif c in ('"', "'", '`'):
            # Skip string
            quote = c
            i += 1
            while i < len(html) and html[i] != quote:
                if html[i] == '\\':
                    i += 1
                i += 1
        elif c == '/' and i + 1 < len(html):
            if html[i + 1] == '/':
                # Line comment
                while i < len(html) and html[i] != '\n':
                    i += 1
            elif html[i + 1] == '*':
                while i < len(html) - 1 and not (html[i] == '*' and html[i + 1] == '/'):
                    i += 1
                i += 1
        i += 1
    return None


def js_to_json(js_str):
    """Convertit un objet JS en JSON valide."""
    s = js_str

    # Supprimer les commentaires // ...
    s = re.sub(r'//[^\n]*', '', s)
    # Supprimer les commentaires /* ... */
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)

    # Clés sans quotes: word: → "word":
    s = re.sub(r'(?<=[{,\n])\s*(\w+)\s*:', r' "\1":', s)

    # Valeurs true/false
    s = s.replace(': true', ': true').replace(': false', ': false')

    # Trailing commas avant } ou ]
    s = re.sub(r',\s*([}\]])', r'\1', s)

    # Single quotes → double quotes (simple cas)
    # Attention: ne pas casser les apostrophes dans les labels FR
    # On ne touche que les clés/valeurs string entre single quotes
    s = re.sub(r"'([^']*)'", r'"\1"', s)

    return s


def parse_fiches_catalogue(html):
    """Parse FICHES_CATALOGUE depuis le HTML Oracle."""
    raw = extract_js_object(html, "FICHES_CATALOGUE")
    if not raw:
        print("ERREUR: FICHES_CATALOGUE non trouvé")
        return []

    json_str = js_to_json(raw)

    try:
        fiches = json.loads(json_str)
        print(f"  OK: {len(fiches)} fiches Oracle parsées")
        return fiches
    except json.JSONDecodeError as e:
        print(f"  ERREUR JSON parse: {e}")
        # Fallback: parse ligne par ligne
        return parse_fiches_fallback(raw)


def parse_fiches_fallback(raw):
    """Parse de secours pour les fiches, objet par objet."""
    fiches = []
    # Trouver chaque {ref:...}
    pattern = r'\{[^{}]*"?ref"?\s*:\s*"([^"]+)"[^{}]*\}'
    for m in re.finditer(pattern, raw):
        try:
            obj_str = js_to_json(m.group(0))
            obj = json.loads(obj_str)
            fiches.append(obj)
        except Exception:
            continue
    print(f"  FALLBACK: {len(fiches)} fiches parsées")
    return fiches


def parse_cout_travaux(html):
    """Parse COUT_TRAVAUX."""
    raw = extract_js_object(html, "COUT_TRAVAUX")
    if not raw:
        return {}
    json_str = js_to_json(raw)
    try:
        data = json.loads(json_str)
        print(f"  OK: {len(data)} entrées cout_travaux")
        return data
    except json.JSONDecodeError as e:
        print(f"  ERREUR cout_travaux: {e}")
        return {}


def parse_deadlines(html):
    """Parse FICHE_DEADLINES."""
    raw = extract_js_object(html, "FICHE_DEADLINES")
    if not raw:
        return {}
    json_str = js_to_json(raw)
    try:
        data = json.loads(json_str)
        print(f"  OK: {len(data)} deadlines")
        return data
    except json.JSONDecodeError as e:
        print(f"  ERREUR deadlines: {e}")
        return {}


def parse_activity_factors(html):
    """Parse ACTIVITY_FACTORS."""
    raw = extract_js_object(html, "ACTIVITY_FACTORS")
    if not raw:
        return {}
    json_str = js_to_json(raw)
    try:
        data = json.loads(json_str)
        print(f"  OK: {len(data)} activity factors")
        return data
    except json.JSONDecodeError as e:
        print(f"  ERREUR activity_factors: {e}")
        return {}


def oracle_to_engine_fiche(oracle_fiche):
    """Convertit une fiche Oracle (JS) → format Engine (Python)."""
    ref = oracle_fiche.get("ref", "")
    z = oracle_fiche.get("z", {})
    z_elec = oracle_fiche.get("z_elec")

    # Déterminer le type depuis unit
    unit = oracle_fiche.get("unit", "")
    ftype = "unitaire"
    if "m²" in unit or "m2" in unit:
        ftype = "surface"

    # Cumac unitaire
    cumac = {}
    for zone in ["H1", "H2", "H3", "DOM"]:
        if zone in z:
            cumac[zone] = z[zone]

    # Cumac elec
    cumac_elec = None
    if z_elec:
        cumac_elec = {}
        for zone in ["H1", "H2", "H3", "DOM"]:
            if zone in z_elec:
                cumac_elec[zone] = z_elec[zone]

    # Params
    params = []
    if ftype == "surface":
        params = ["surface"]
    elif "kW" in unit:
        params = ["puissance"]
    elif "logement" in unit:
        params = ["nb_logements"]
    elif "point" in unit:
        params = ["quantite"]
    elif "ml" in unit or "m" == unit:
        params = ["longueur"]
    else:
        params = ["quantite"]

    engine_fiche = {
        "ref": ref,
        "nom": oracle_fiche.get("label", oracle_fiche.get("nom", "")),
        "secteur": oracle_fiche.get("sector", ref[:3]),
        "sous_secteur": ref.split("-")[1] if "-" in ref else "",
        "type": ftype,
        "params": params,
        "cumac_unitaire": cumac,
        "unite": f"kWhc par {unit}",
        "duree_vie": 15,  # Default, à affiner par fiche
        "conditions": {
            "zone": [z for z in ["H1", "H2", "H3", "DOM"] if z in cumac]
        },
        "conditions_texte": [],
        "actif": oracle_fiche.get("active", True),
        # Données Oracle enrichies
        "unite_oracle": unit,
        "categorie": oracle_fiche.get("cat", ""),
        "gisements": oracle_fiche.get("gisements", []),
    }

    # FOST sectFactors
    if oracle_fiche.get("sectFactors"):
        engine_fiche["sect_factors"] = oracle_fiche["sectFactors"]

    # Coup de Pouce
    p6 = oracle_fiche.get("p6Bonus", 1)
    if p6 and p6 > 1:
        engine_fiche["p6_bonus"] = p6

    # zeroEuro
    if oracle_fiche.get("zeroEuro"):
        engine_fiche["zero_euro"] = True

    # COFRAC
    if oracle_fiche.get("cofrac"):
        engine_fiche["cofrac"] = True

    # Cumac elec
    if cumac_elec:
        engine_fiche["cumac_elec"] = cumac_elec

    return engine_fiche


def merge_fiches(oracle_fiches, engine_fiches):
    """Fusionne Oracle + Engine. Oracle = référence cumac, Engine = logique complexe."""
    # Index par ref
    engine_by_ref = {f["ref"]: f for f in engine_fiches}
    oracle_by_ref = {f["ref"]: f for f in oracle_fiches}

    merged = []
    seen = set()

    # 1) Pour chaque fiche Oracle → créer/enrichir
    for ref, of in oracle_by_ref.items():
        converted = oracle_to_engine_fiche(of)

        if ref in engine_by_ref:
            # Fiche existe dans Engine → merger
            ef = engine_by_ref[ref]

            # Garder la logique complexe d'Engine si elle existe
            if ef.get("type") == "complexe":
                converted["type"] = "complexe"
                converted["mode_calcul"] = ef.get("mode_calcul")
                converted["table_cumac"] = ef.get("table_cumac")
                converted["formule"] = ef.get("formule")
                converted["variables"] = ef.get("variables")

            # Garder les conditions texte d'Engine (plus détaillées)
            if ef.get("conditions_texte"):
                converted["conditions_texte"] = ef["conditions_texte"]

            # Garder les conditions seuils d'Engine
            if ef.get("conditions", {}).get("seuils_min"):
                converted["conditions"]["seuils_min"] = ef["conditions"]["seuils_min"]

            # Garder les conditions energie d'Engine
            if ef.get("conditions", {}).get("energie"):
                converted["conditions"]["energie"] = ef["conditions"]["energie"]

            # Garder la duree_vie d'Engine si spécifique
            if ef.get("duree_vie") and ef["duree_vie"] != 15:
                converted["duree_vie"] = ef["duree_vie"]

        merged.append(converted)
        seen.add(ref)

    # 2) Fiches Engine qui n'existent pas dans Oracle
    for ref, ef in engine_by_ref.items():
        if ref not in seen:
            # Garder la fiche Engine telle quelle, ajouter champs manquants
            ef.setdefault("gisements", [])
            ef.setdefault("actif", True)
            ef.setdefault("categorie", "")
            merged.append(ef)
            seen.add(ref)

    return sorted(merged, key=lambda f: f["ref"])


def main():
    print("\n" + "=" * 60)
    print("  FUSION ORACLE V34 → CEE ENGINE")
    print("=" * 60)

    # Lire HTML
    print(f"\n  Lecture: {HTML_PATH}")
    html = read_html()
    print(f"  Taille: {len(html):,} caractères")

    # Parser les données Oracle
    print("\n  --- EXTRACTION ORACLE ---")
    oracle_fiches = parse_fiches_catalogue(html)
    cout_travaux = parse_cout_travaux(html)
    deadlines = parse_deadlines(html)
    activity_factors = parse_activity_factors(html)

    # Charger fiches Engine existantes
    print("\n  --- CHARGEMENT ENGINE ---")
    with open(FICHES_PATH, "r", encoding="utf-8") as f:
        engine_fiches = json.load(f)
    print(f"  OK: {len(engine_fiches)} fiches Engine")

    # Merger
    print("\n  --- FUSION ---")
    merged = merge_fiches(oracle_fiches, engine_fiches)

    oracle_refs = set(f.get("ref") for f in oracle_fiches)
    engine_refs = set(f["ref"] for f in engine_fiches)
    print(f"  Oracle: {len(oracle_refs)} refs")
    print(f"  Engine: {len(engine_refs)} refs")
    print(f"  Communs: {len(oracle_refs & engine_refs)}")
    print(f"  Oracle uniquement: {len(oracle_refs - engine_refs)}")
    print(f"  Engine uniquement: {len(engine_refs - oracle_refs)}")
    print(f"  TOTAL FUSIONNÉ: {len(merged)}")

    # Sauvegarder
    print("\n  --- SAUVEGARDE ---")

    # Backup
    import shutil
    backup = FICHES_PATH + ".backup"
    shutil.copy2(FICHES_PATH, backup)
    print(f"  Backup: {backup}")

    # Fiches enrichies
    with open(FICHES_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"  fiches.json: {len(merged)} fiches")

    # Cout travaux
    ct_path = os.path.join(ENGINE_DIR, "cout_travaux.json")
    with open(ct_path, "w", encoding="utf-8") as f:
        json.dump(cout_travaux, f, ensure_ascii=False, indent=2)
    print(f"  cout_travaux.json: {len(cout_travaux)} entrées")

    # Deadlines
    dl_path = os.path.join(ENGINE_DIR, "deadlines.json")
    with open(dl_path, "w", encoding="utf-8") as f:
        json.dump(deadlines, f, ensure_ascii=False, indent=2)
    print(f"  deadlines.json: {len(deadlines)} entrées")

    # Activity factors
    af_path = os.path.join(ENGINE_DIR, "activity_factors.json")
    with open(af_path, "w", encoding="utf-8") as f:
        json.dump(activity_factors, f, ensure_ascii=False, indent=2)
    print(f"  activity_factors.json: {len(activity_factors)} entrées")

    print("\n" + "=" * 60)
    print("  FUSION TERMINÉE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
