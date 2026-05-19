"""
SCRAPE-ADEME PDF V2 — module batch d'extraction PDF officiels ADEME.

Mission : combler les trous data du catalogue CEE Engine.
- Liste les refs cibles (placeholders + complexes désactivés + cumac à vérifier)
- Download les PDF manquants depuis ecologie.gouv.fr
- Parse via parse_pdf.py (extract_text, parse_cumac_table, parse_duree_vie, ...)
- Génère rapport diff JSON
- NE MODIFIE PAS fiches.json — review user obligatoire

Usage : python3 scrape_ademe_pdf_v2.py [--refs ALL|placeholders|complexes|<ref1,ref2,...>]
"""
import os, sys, json, glob, re, time, argparse
import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.abspath(__file__))
FICHES_PATH = os.path.join(ROOT, "fiches.json")
PDFS_DIR = os.path.join(ROOT, "pdfs")
REPORT_PATH = os.path.join(ROOT, "scrape_ademe_pdf_report.json")
INDEX_URL = "https://www.ecologie.gouv.fr/operations-standardisees-deconomies-denergie"

# === Cibles par défaut ===
PLACEHOLDERS_V39_0_9 = [
    'BAR-EN-110','BAR-SE-107','BAR-SE-109','BAR-TH-102','BAR-TH-106',
    'BAR-TH-107','BAR-TH-110','BAR-TH-111','BAR-TH-116','BAR-TH-117',
    'BAR-TH-122','BAR-TH-130','BAR-TH-137','BAR-TH-139','BAR-TH-150',
    'BAT-TH-140','BAT-TH-141','BAT-TH-146','IND-UT-121',
]
COMPLEXES_BROKEN_V39_0_7 = [
    'AGRI-TH-108','AGRI-TH-117','AGRI-UT-101','AGRI-UT-102','AGRI-UT-104',
    'BAT-EQ-117','BAT-EQ-130','BAT-EQ-131','BAT-TH-112','BAT-TH-115',
    'BAT-TH-122','BAT-TH-135','BAT-TH-153','BAT-TH-157','BAT-TH-161',
    'IND-BA-114','IND-UT-102','IND-UT-114','IND-UT-118','IND-UT-125',
    'IND-UT-131','IND-UT-132','IND-UT-133','IND-UT-137','IND-UT-138',
    'IND-UT-139','RES-CH-106','TRA-EQ-106','TRA-EQ-126','TRA-EQ-127',
]
CUMAC_INCONNU = ['IND-UT-115']


def find_pdf_url_for_ref(ref, soup):
    """Trouve l'URL du PDF officiel pour une ref donnée dans l'index ADEME."""
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href.lower().endswith('.pdf'):
            continue
        # Match strict : ref doit apparaître dans URL ou texte ancre
        if ref in href.replace('%20', ' ') or ref in a.get_text(strip=True):
            return href if href.startswith('http') else 'https://www.ecologie.gouv.fr' + href
    return None


def download_pdf(url, ref, retries=2):
    """Download un PDF dans pdfs/ avec retry. Retourne le path local ou None."""
    os.makedirs(PDFS_DIR, exist_ok=True)
    # Nom de fichier propre
    filename = f"{ref}.pdf"
    path = os.path.join(PDFS_DIR, filename)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path  # déjà là
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=30, allow_redirects=True)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(path, 'wb') as f:
                    f.write(r.content)
                return path
        except Exception as e:
            print(f"    ⚠ download retry {attempt+1}: {e}")
            time.sleep(1)
    return None


def find_local_pdf(ref):
    """Cherche un PDF déjà téléchargé pour ref (handle naming variations)."""
    patterns = [f'{PDFS_DIR}/{ref}.pdf', f'{PDFS_DIR}/{ref}*.pdf',
                f'{PDFS_DIR}/{ref.replace("-","_")}*.pdf']
    for pat in patterns:
        matches = [m for m in glob.glob(pat) if '_debug' not in m]
        if matches:
            return sorted(matches, key=os.path.getmtime, reverse=True)[0]
    return None


def parse_pdf_to_fiche_data(pdf_path):
    """Extrait fiche data depuis un PDF via parse_pdf.py existant."""
    import parse_pdf
    try:
        text = parse_pdf.extract_text(pdf_path)
        if not text or len(text) < 200:
            return {'error': 'PDF trop court ou vide', 'text_len': len(text or '')}
        ref = parse_pdf.parse_ref(text)
        if not ref:
            return {'error': 'ref introuvable', 'text_sample': text[:300]}
        return {
            'ref': ref,
            'nom': parse_pdf.parse_nom(text, ref),
            'type': parse_pdf.parse_type(text),
            'cumac_unitaire': parse_pdf.parse_cumac_table(text),
            'duree_vie': parse_pdf.parse_duree_vie(text),
            'variables': parse_pdf.extract_variables(text),
            'is_complex': parse_pdf.detect_complex(text),
            'is_expired': parse_pdf.detect_expired(text),
            'text_len': len(text),
        }
    except Exception as e:
        return {'error': f'{type(e).__name__}: {e}'}


def compare_with_local(ref, extracted, local_fiches_by_ref):
    """Diff entre extraction PDF et fiche locale. Retourne dict de diffs."""
    local = local_fiches_by_ref.get(ref)
    diff = {'ref': ref, 'has_local': local is not None, 'extracted': extracted}
    if local:
        diff['local_actif'] = local.get('actif')
        diff['local_nom'] = local.get('nom')
        diff['local_cumac'] = local.get('cumac_unitaire')
        diff['local_duree_vie'] = local.get('duree_vie')
        diff['local_type'] = local.get('type')
        # Conflicts
        conflicts = []
        if extracted.get('nom') and local.get('nom') and \
           extracted['nom'].lower()[:30] != local['nom'].lower()[:30]:
            conflicts.append(f"nom: '{local['nom'][:40]}' vs '{extracted['nom'][:40]}'")
        if extracted.get('cumac_unitaire') and isinstance(local.get('cumac_unitaire'), dict) \
           and isinstance(extracted['cumac_unitaire'], dict):
            for z in ['H1','H2','H3','DOM']:
                lv = local['cumac_unitaire'].get(z)
                ev = extracted['cumac_unitaire'].get(z)
                if lv and ev and abs(lv - ev) / max(lv, 1) > 0.10:
                    conflicts.append(f"cumac {z}: {lv} vs {ev}")
        diff['conflicts'] = conflicts
    return diff


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refs', default='ALL',
        help='ALL | placeholders | complexes | cumac_inconnu | <ref1,ref2,...>')
    parser.add_argument('--skip-download', action='store_true',
        help='N\'essaie pas de télécharger, parse uniquement les PDF déjà locaux')
    args = parser.parse_args()

    # Resolve targets
    if args.refs == 'ALL':
        cibles = PLACEHOLDERS_V39_0_9 + COMPLEXES_BROKEN_V39_0_7 + CUMAC_INCONNU
    elif args.refs == 'placeholders':
        cibles = PLACEHOLDERS_V39_0_9
    elif args.refs == 'complexes':
        cibles = COMPLEXES_BROKEN_V39_0_7
    elif args.refs == 'cumac_inconnu':
        cibles = CUMAC_INCONNU
    else:
        cibles = [r.strip() for r in args.refs.split(',')]

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║   SCRAPE-ADEME PDF V2 — {len(cibles)} refs cibles         ║")
    print(f"╚══════════════════════════════════════════════════════╝\n")

    # Charger catalogue local
    with open(FICHES_PATH) as f:
        local_fiches = json.load(f)
    local_by_ref = {f['ref']: f for f in local_fiches}

    # Step 1: identifier PDF locaux + URLs à télécharger
    needs_download = []
    local_pdfs = {}
    for ref in cibles:
        local = find_local_pdf(ref)
        if local:
            local_pdfs[ref] = local
        else:
            needs_download.append(ref)

    print(f"📁 PDF en cache local : {len(local_pdfs)}/{len(cibles)}")
    print(f"⬇️  À télécharger     : {len(needs_download)}\n")

    # Step 2: télécharger les manquants
    if needs_download and not args.skip_download:
        print(f"=== Récupération URLs depuis index ADEME ===")
        try:
            r = requests.get(INDEX_URL, timeout=30, allow_redirects=True)
            soup = BeautifulSoup(r.text, 'html.parser')
            print(f"  Index : HTTP {r.status_code}, {len(r.content)} bytes")
        except Exception as e:
            print(f"  ❌ erreur index : {e}")
            soup = None

        if soup:
            print(f"\n=== Download {len(needs_download)} PDF ===")
            for i, ref in enumerate(needs_download, 1):
                url = find_pdf_url_for_ref(ref, soup)
                if not url:
                    print(f"  [{i:2d}/{len(needs_download)}] ❌ {ref} : URL introuvable dans index")
                    continue
                path = download_pdf(url, ref)
                if path:
                    local_pdfs[ref] = path
                    print(f"  [{i:2d}/{len(needs_download)}] ✓ {ref} ({os.path.getsize(path)//1024} KB)")
                else:
                    print(f"  [{i:2d}/{len(needs_download)}] ❌ {ref} : download failed")
                time.sleep(0.3)  # politesse

    # Step 3: parser chaque PDF
    print(f"\n=== Parse {len(local_pdfs)} PDF ===")
    results = []
    for i, (ref, path) in enumerate(local_pdfs.items(), 1):
        data = parse_pdf_to_fiche_data(path)
        diff = compare_with_local(ref, data, local_by_ref)
        diff['pdf_path'] = os.path.basename(path)
        results.append(diff)
        status = '✓' if 'error' not in data else '⚠'
        cumac_str = ''
        if isinstance(data.get('cumac_unitaire'), dict):
            cumac_str = ' | cumac=' + ','.join(f"{k}:{v}" for k,v in data['cumac_unitaire'].items())
        print(f"  [{i:2d}/{len(local_pdfs)}] {status} {ref:14s} {data.get('error','OK')[:40]:40s}{cumac_str[:60]}")

    # Step 4: rapport
    report = {
        'date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'cibles': cibles,
        'pdf_locaux': len(local_pdfs),
        'parses_ok': sum(1 for r in results if 'error' not in r.get('extracted', {})),
        'parses_ko': sum(1 for r in results if 'error' in r.get('extracted', {})),
        'sans_pdf': [r for r in cibles if r not in local_pdfs],
        'avec_conflits': sum(1 for r in results if r.get('conflicts')),
        'results': results,
    }
    with open(REPORT_PATH, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n╔══════════════════════════════════════════════════════╗")
    print(f"║   RAPPORT FINAL                                       ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"  Cibles            : {len(cibles)}")
    print(f"  PDF disponibles   : {len(local_pdfs)}")
    print(f"  Parse OK          : {report['parses_ok']}")
    print(f"  Parse KO          : {report['parses_ko']}")
    print(f"  Sans PDF          : {len(report['sans_pdf'])}")
    print(f"  Avec conflits     : {report['avec_conflits']}")
    print(f"\n  Rapport JSON  → {REPORT_PATH}")
    print(f"  ⚠ fiches.json NON modifié — review requise avant apply\n")


if __name__ == '__main__':
    main()
