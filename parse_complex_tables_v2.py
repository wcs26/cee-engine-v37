"""
PARSE_COMPLEX_TABLES_V2 — extracteur de table_cumac pour fiches CEE complexes.

Patterns ADEME identifiés :
  A) Lookup 1D    : Application/Type → Montant cumac (1 variable catégorielle)
  B) Lookup 2D    : Efficacité × Type → Montant cumac (2 variables catégorielles)
  C) Cas + fixe   : Cas 1/2/3 → Solution → Montant × Pf (puissance multiplier)
  D) Formule par tranche : "a × P + b" selon plage puissance
  E) Texte pur    : table inextractible, conditions dans paragraphes

Approche : pdfplumber.extract_tables() + classification heuristique + extraction
ciblée. Produit un rapport JSON détaillé pour review humaine assistée.

Usage :
  python3 parse_complex_tables_v2.py [--refs ALL|<csv>]
"""
import os, sys, json, glob, re, argparse
import pdfplumber

ROOT = os.path.dirname(os.path.abspath(__file__))
PDFS_DIR = os.path.join(ROOT, "pdfs")
REPORT_PATH = os.path.join(ROOT, "parse_complex_tables_report.json")

COMPLEXES_BROKEN = [
    'AGRI-TH-108','AGRI-TH-117','AGRI-UT-101','AGRI-UT-102','AGRI-UT-104',
    'BAT-EQ-117','BAT-EQ-130','BAT-EQ-131','BAT-TH-112','BAT-TH-115',
    'BAT-TH-122','BAT-TH-135','BAT-TH-153','BAT-TH-157','BAT-TH-161',
    'IND-BA-114','IND-UT-102','IND-UT-114','IND-UT-118','IND-UT-125',
    'IND-UT-131','IND-UT-132','IND-UT-133','IND-UT-137','IND-UT-138',
    'IND-UT-139','RES-CH-106','TRA-EQ-106','TRA-EQ-126','TRA-EQ-127',
]

# Mots-clés pour détecter le type de table
KW_CUMAC = ['montant', 'cumac', 'kwh cumac', 'kwhc']
KW_VARIABLE_HEADERS = {
    'puissance': ['puissance', 'p kw', 'kw', 'pf', 'pn'],
    'surface':   ['surface', 'm²', 'm2'],
    'efficacite': ['cop', 'rendement', 'ηs', 'efficacit', 'classe'],
    'type':      ['type', 'application', 'usage', 'opération', 'operation', 'cas'],
    'temperature': ['température', 'temperature', 'tempér', 't°'],
}


def find_local_pdf(ref):
    """Cherche le PDF local pour une ref."""
    for pat in [f'{PDFS_DIR}/{ref}.pdf', f'{PDFS_DIR}/{ref}*.pdf']:
        matches = [m for m in glob.glob(pat) if '_debug' not in m]
        if matches:
            return sorted(matches, key=os.path.getmtime, reverse=True)[0]
    return None


def normalize_cell(c):
    """Normalise une cellule : strip + collapse newlines + lowercase pour matching."""
    if c is None: return ''
    s = str(c).replace('\n', ' ').strip()
    return s


def parse_number(s):
    """Extrait un nombre depuis cellule (gère 'X kWh cumac', '1 500', '7,2', '4900 x P + 2600')."""
    if not s: return None
    s = str(s).strip()
    # Cas formule : retourner None (à traiter ailleurs)
    if 'x p' in s.lower() or 'x s' in s.lower() or '+' in s and 'p' in s.lower():
        return None
    # Nettoyer : enlever espaces dans nombres, virgules → points
    s2 = re.sub(r'(\d)\s+(\d)', r'\1\2', s).replace(',', '.').replace(' ', '')
    m = re.search(r'(\d+(?:\.\d+)?)', s2)
    if m:
        try: return float(m.group(1))
        except: return None
    return None


def classify_table(table):
    """Classifie une table : type (lookup_1d, lookup_2d, formula, header_only, other)."""
    if not table or len(table) < 2:
        return 'too_small'

    # Header : 1ère ligne
    header = [normalize_cell(c).lower() for c in table[0]]
    has_cumac_col = any(any(kw in h for kw in KW_CUMAC) for h in header)
    if not has_cumac_col:
        # Peut-être que les valeurs cumac sont dans une seule cellule sans header explicite
        # On checke les autres lignes
        any_kw = False
        for row in table[1:3]:
            for c in row:
                nc = normalize_cell(c).lower()
                if any(kw in nc for kw in KW_CUMAC):
                    any_kw = True
                    break
        if not any_kw:
            return 'no_cumac'

    # Détection formule
    for row in table[1:]:
        for c in row:
            if c and ('x P' in str(c) or 'x p' in str(c).lower() or '+' in str(c) and 'P' in str(c)):
                return 'formula'

    # Lookup 1D vs 2D
    n_cols = len(table[0])
    if n_cols == 2:
        return 'lookup_1d'
    elif n_cols >= 3:
        return 'lookup_2d_or_more'
    return 'other'


def extract_lookup_1d(table):
    """Extrait {clé: cumac} depuis table 2 colonnes."""
    result = {}
    for row in table[1:]:
        if len(row) < 2: continue
        key = normalize_cell(row[0])
        val = parse_number(row[1])
        if key and val is not None and val > 0:
            result[key] = val
    return result if result else None


def extract_lookup_2d(table):
    """Extrait {clé1: {clé2: cumac}} ou liste de dicts pour table 3+ colonnes."""
    if len(table) < 2: return None
    header = [normalize_cell(c) for c in table[0]]
    # Trouver la colonne cumac
    cumac_col = -1
    for i, h in enumerate(header):
        if any(kw in h.lower() for kw in KW_CUMAC):
            cumac_col = i
            break
    if cumac_col < 0:
        # Heuristique : c'est la dernière colonne
        cumac_col = len(header) - 1

    rows = []
    last_key1 = None
    for row in table[1:]:
        if len(row) <= cumac_col: continue
        key1 = normalize_cell(row[0]) or last_key1
        last_key1 = key1
        key2 = normalize_cell(row[1]) if len(row) > 2 else None
        val = parse_number(row[cumac_col])
        if val is not None and val > 0:
            rows.append({
                'cle1_header': header[0] if header else '',
                'cle1': key1,
                'cle2_header': header[1] if len(header) > 1 else '',
                'cle2': key2,
                'cumac': val,
            })
    return rows if rows else None


def extract_formula(table):
    """Extrait formules par tranche depuis table type 'a×P+b par plage'."""
    formulas = []
    for row in table:
        for c in row:
            if not c: continue
            s = str(c).strip()
            # Pattern "1 600 x P" ou "4 900 x P + 2 600"
            m = re.search(r'(\d[\d\s]*)\s*[x×]\s*P\s*(?:\+\s*(\d[\d\s]*))?', s)
            if m:
                a = int(m.group(1).replace(' ',''))
                b = int(m.group(2).replace(' ','')) if m.group(2) else 0
                formulas.append({'raw': s, 'a_coef': a, 'b_const': b, 'variable': 'P'})
    return formulas if formulas else None


def parse_pdf_for_complex(pdf_path):
    """Parse complet un PDF de fiche complexe — retourne dict structuré."""
    result = {
        'pdf': os.path.basename(pdf_path),
        'pages': 0,
        'tables_total': 0,
        'tables_classified': {},
        'extractions': [],
    }
    try:
        with pdfplumber.open(pdf_path) as pdf:
            result['pages'] = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                for ti, t in enumerate(tables):
                    result['tables_total'] += 1
                    klass = classify_table(t)
                    result['tables_classified'].setdefault(klass, 0)
                    result['tables_classified'][klass] += 1

                    extraction = None
                    if klass == 'lookup_1d':
                        extraction = {'type': '1d', 'data': extract_lookup_1d(t)}
                    elif klass == 'lookup_2d_or_more':
                        extraction = {'type': '2d', 'data': extract_lookup_2d(t)}
                    elif klass == 'formula':
                        extraction = {'type': 'formula', 'data': extract_formula(t)}

                    if extraction and extraction.get('data'):
                        # Garder seulement table dimensions + tronc en sample
                        sample = [[normalize_cell(c)[:30] for c in row[:4]] for row in t[:4]]
                        result['extractions'].append({
                            'page': page_num, 'table_idx': ti,
                            'class': klass,
                            'rows': len(t), 'cols': len(t[0]) if t else 0,
                            'sample': sample,
                            **extraction
                        })
    except Exception as e:
        result['error'] = f'{type(e).__name__}: {e}'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refs', default='ALL')
    args = parser.parse_args()

    cibles = COMPLEXES_BROKEN if args.refs == 'ALL' else args.refs.split(',')

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║   PARSE COMPLEX TABLES V2 — {len(cibles)} cibles                ║")
    print(f"╚══════════════════════════════════════════════════════╝\n")

    results = {}
    for ref in cibles:
        pdf = find_local_pdf(ref)
        if not pdf:
            print(f"  ❌ {ref:14s} PDF absent")
            results[ref] = {'error': 'pdf_absent'}
            continue
        r = parse_pdf_for_complex(pdf)
        results[ref] = r
        nb_extracts = len(r.get('extractions', []))
        types = '+'.join(set(e['type'] for e in r.get('extractions', [])))
        print(f"  {'✓' if nb_extracts else '⚠':2s} {ref:14s} {r['pages']}p, {r['tables_total']} tables, {nb_extracts} extractions ({types})")

    # Stats globales
    print()
    by_status = {'extracted': 0, 'no_extract': 0, 'no_pdf': 0}
    by_pattern = {}
    for ref, r in results.items():
        if r.get('error'):
            by_status['no_pdf'] += 1
        elif r.get('extractions'):
            by_status['extracted'] += 1
            for e in r['extractions']:
                by_pattern[e['type']] = by_pattern.get(e['type'], 0) + 1
        else:
            by_status['no_extract'] += 1
    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║   BILAN PARSE COMPLEX TABLES                          ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"  PDF avec extractions  : {by_status['extracted']}/{len(cibles)}")
    print(f"  PDF sans extraction   : {by_status['no_extract']}")
    print(f"  PDF absent            : {by_status['no_pdf']}")
    print(f"  Patterns détectés     : {by_pattern}")

    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  Rapport JSON → {REPORT_PATH}")


if __name__ == '__main__':
    main()
