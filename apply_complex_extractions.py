"""
APPLY_COMPLEX_EXTRACTIONS — convertit les extractions parse_complex_tables_v2
au format attendu par moteur_cee_master.compute_complexe + active les fiches.

Logique de safety :
  - Pour chaque fiche, choisit la meilleure extraction (la plus riche)
  - Convertit au format selon type (1d→table_str, 2d→table_2d, formula→tranches)
  - Teste compute() avec params plausibles → doit retourner cumac > 0
  - Sanity check : valeurs cumac dans [10, 5_000_000]
  - Si OK → injecte dans fiches.json, passe actif=True
  - Sinon → skip avec raison

Usage:
  python3 apply_complex_extractions.py [--dry-run] [--refs ALL|<csv>]
"""
import os, sys, json, argparse, re

ROOT = os.path.dirname(os.path.abspath(__file__))
FICHES_PATH = os.path.join(ROOT, "fiches.json")
REPORT_PATH = os.path.join(ROOT, "parse_complex_tables_report.json")

# Min/max plausibles pour 1 unité (kWhc cumac)
CUMAC_MIN = 10
CUMAC_MAX = 5_000_000


def detect_variables_from_data(extraction, fiche_params):
    """Devine les noms de variables depuis headers + nom fiche + params existants."""
    typ = extraction['type']
    if typ == '1d':
        # 1ère cellule = clé. Heuristic sur nom application.
        return ['application']
    elif typ == '2d':
        data = extraction.get('data', [])
        if not data: return []
        h1 = (data[0].get('cle1_header') or '').lower()
        h2 = (data[0].get('cle2_header') or '').lower()
        def cat(h):
            if 'cop' in h or 'rendement' in h or 'efficac' in h or 'ηs' in h: return 'efficacite'
            if 'type' in h: return 'type'
            if 'puissance' in h: return 'puissance'
            if 'surface' in h: return 'surface'
            if 'classe' in h: return 'classe'
            if 'temperature' in h or 'tempér' in h: return 'temperature'
            if 'application' in h or 'usage' in h or 'opération' in h: return 'application'
            return h.split()[0] if h else 'cle'
        return [cat(h1), cat(h2)]
    elif typ == 'formula':
        return ['puissance']
    return []


def build_table_cumac(extraction, variables):
    """Convertit extraction au format dict attendu par compute_complexe."""
    typ = extraction['type']
    data = extraction.get('data', {})
    if typ == '1d':
        # Filtre valeurs hors plage
        return {k: int(v) for k, v in data.items()
                if CUMAC_MIN <= v <= CUMAC_MAX}, 'table_str'
    elif typ == '2d':
        # Nested dict {cle1: {cle2: cumac}}
        nested = {}
        for row in data:
            k1, k2, val = row['cle1'], row['cle2'], row['cumac']
            if not k1 or not (CUMAC_MIN <= val <= CUMAC_MAX): continue
            nested.setdefault(k1, {})[k2 or '_'] = int(val)
        return nested, 'table_2d'
    elif typ == 'formula':
        # Liste de tranches { min, max, a, b }
        tranches = []
        for f in data:
            tranches.append({
                'min': 0,  # à compléter manuellement si possible (parse plage)
                'max': float('inf'),
                'a': int(f['a_coef']),
                'b': int(f['b_const']),
            })
        return tranches, 'formule_tranches'
    return None, None


def parse_formula_ranges(extraction):
    """Pour formula : tente d'extraire les plages depuis sample (ex '0,12 ≤ P ≤ 0,75 kW')."""
    tranches = []
    sample = extraction.get('sample', [])
    formulas = extraction.get('data', [])
    # Sample contient ['0,12 kW ≤ P ≤ 0,75 k', '0,75 kW < P ≤ 375 kW', '375 kW < P ≤ 1000 kW']
    if sample and len(sample) >= 2:
        range_row = sample[1] if len(sample[1]) >= len(formulas) else sample[0]
        for i, cell in enumerate(range_row):
            if i >= len(formulas): break
            mn, mx = 0, float('inf')
            # Patterns: "0,12 kW ≤ P ≤ 0,75 k" / "375 kW < P ≤ 1000 kW"
            m1 = re.search(r'(\d[\d,\.]*)\s*kW?\s*[≤<]\s*P', cell)
            m2 = re.search(r'P\s*[≤<]\s*(\d[\d,\.]*)', cell)
            if m1: mn = float(m1.group(1).replace(',', '.'))
            if m2: mx = float(m2.group(1).replace(',', '.'))
            tranches.append({
                'min': mn, 'max': mx,
                'a': int(formulas[i]['a_coef']),
                'b': int(formulas[i]['b_const']),
            })
    return tranches if tranches else None


def smart_test_params(table_cumac, mode, variables):
    """Génère des params plausibles pour tester compute_complexe."""
    if mode == 'table_str':
        # Prendre la 1ère clé
        keys = list(table_cumac.keys())
        return {variables[0]: keys[0]} if keys else {}
    elif mode == 'table_2d':
        keys1 = list(table_cumac.keys())
        if not keys1: return {}
        keys2 = list(table_cumac[keys1[0]].keys()) if isinstance(table_cumac[keys1[0]], dict) else []
        return {variables[0]: keys1[0], variables[1]: keys2[0] if keys2 else ''}
    elif mode == 'formule_tranches':
        return {variables[0]: 10}  # 10 kW = valeur intermédiaire
    return {}


def apply_to_fiche(fiche, extraction):
    """Modifie fiche dict avec données extraites + activate. Retourne (success, msg)."""
    typ = extraction['type']
    variables = detect_variables_from_data(extraction, fiche.get('params', []))
    if not variables:
        return False, "variables introuvables"

    # Safety : skip variables ambiguës (headers non-sémantiques type 'cle'/'montant'/'d')
    AMBIGUOUS = {'cle', 'montant', 'd', '', 'application'}
    if typ == '2d' and any(v in AMBIGUOUS for v in variables[:2]):
        # Si AU MOINS UNE variable est ambiguë sur du 2D, c'est risqué d'activer
        if all(v in AMBIGUOUS for v in variables[:2]):
            return False, f"variables 2D ambiguës {variables} — review manuelle"

    # Build table_cumac
    if typ == 'formula':
        tranches = parse_formula_ranges(extraction)
        if not tranches:
            return False, "formula : plages non extractibles"
        fiche['table_cumac'] = {}  # signal "compute via tranches"
        fiche['tranches'] = tranches
        fiche['mode_calcul'] = 'formule_tranches'
        fiche['variables'] = variables
    else:
        table, mode = build_table_cumac(extraction, variables)
        if not table:
            return False, "table_cumac vide après filtres"
        if typ == '1d' and len(table) < 2:
            return False, f"1D avec seulement {len(table)} entrée — peu fiable"
        fiche['table_cumac'] = table
        fiche['mode_calcul'] = mode
        fiche['variables'] = variables

    # Test compute
    import importlib, moteur_cee_master
    importlib.reload(moteur_cee_master)
    test_params = smart_test_params(fiche.get('table_cumac', {}), fiche['mode_calcul'], variables)
    try:
        result = moteur_cee_master.compute_complexe(fiche, test_params)
    except Exception as e:
        return False, f"compute_complexe error: {e}"

    if not result or result <= 0:
        return False, f"compute test → {result} (params={test_params})"

    # Sanity check
    if result < CUMAC_MIN or result > CUMAC_MAX:
        return False, f"result {result} hors plage [{CUMAC_MIN},{CUMAC_MAX}]"

    fiche['actif'] = True
    audit = fiche.setdefault('audit', {})
    if isinstance(audit, dict):
        audit['reactivated_V39_2_1'] = {
            'method': 'apply_complex_extractions',
            'extraction_type': typ,
            'test_compute': result,
            'test_params': test_params,
        }
    return True, f"activée ({result} kWhc pour test {test_params})"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--refs', default='ALL')
    args = parser.parse_args()

    report = json.load(open(REPORT_PATH))
    fiches = json.load(open(FICHES_PATH))
    fiches_by_ref = {f['ref']: f for f in fiches}

    cibles = list(report.keys()) if args.refs == 'ALL' else args.refs.split(',')

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║   APPLY COMPLEX EXTRACTIONS — {len(cibles)} cibles           ║")
    print(f"║   {'DRY-RUN' if args.dry_run else 'WRITE MODE'}                                          ║")
    print(f"╚══════════════════════════════════════════════════════╝\n")

    activated = 0
    skipped = []
    for ref in cibles:
        r = report.get(ref, {})
        extractions = r.get('extractions', [])
        if not extractions:
            skipped.append((ref, 'sans extraction'))
            continue
        if ref not in fiches_by_ref:
            skipped.append((ref, 'ref inconnue dans fiches.json'))
            continue
        fiche = fiches_by_ref[ref]
        if fiche.get('actif'):
            skipped.append((ref, 'déjà active'))
            continue
        # Pick best extraction (the one with most data points)
        best = max(extractions, key=lambda e: len(e.get('data') or []) if isinstance(e.get('data'), (list, dict)) else 0)
        success, msg = apply_to_fiche(fiche, best)
        prefix = '✓' if success else '⚠'
        print(f"  {prefix} {ref:14s} {msg}")
        if success:
            activated += 1
        else:
            skipped.append((ref, msg))

    print(f"\n╔══════════════════════════════════════════════════════╗")
    print(f"║   BILAN                                               ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"  Activées : {activated}")
    print(f"  Skippées : {len(skipped)}")

    if not args.dry_run and activated > 0:
        with open(FICHES_PATH, 'w', encoding='utf-8') as f:
            json.dump(fiches, f, ensure_ascii=False, indent=2)
        print(f"\n  ✓ fiches.json sauvegardé ({activated} fiches activées)")


if __name__ == '__main__':
    main()
