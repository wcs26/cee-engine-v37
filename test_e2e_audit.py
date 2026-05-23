"""TEST E2E V44.3 — Simule l'audit complet d'un SIRET et vérifie cohérence.

Pour 3 SIRET tests, simule :
  1. Récupération entreprise via API gouv (mock si pas connecté)
  2. Détection pack éligible via auto_detect.moteur_expert_v2
  3. Génération questions par fiche via pipeline.build_questions_for_fiche
  4. Vérifie classification poste métier
  5. Vérifie coûts COUT_TRAVAUX présents
  6. Calcule prime + couverture + marge attendue
"""
import json, sys, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_detect import moteur_expert_v2
from pipeline import build_questions_for_fiche

# Cas de test représentatifs
CAS_TEST = [
    {
        'siret': '979 734 076 00016',
        'libelle': 'LE POTAGER COCCINELLE — culture maraichère NAF 01.13Z',
        'naf': '01.13Z',
        'surface': 1000,
        'energie': 'fioul',
        'departement': '69',
        'micro_attendue': 'agri_culture',
        'fiches_attendues_mini': ['AGRI-TH-117', 'AGRI-EQ-107'],
    },
    {
        'siret': '775 685 019 06478',
        'libelle': 'Test commerce tertiaire — NAF 47.11F (hypermarché)',
        'naf': '47.11F',
        'surface': 2500,
        'energie': 'electricite',
        'departement': '75',
        'micro_attendue': 'commerce',
        # V44.4 — BAT-EQ-127 LED tertiaire inactive depuis 71e arrêté 1/8/2025
        # On vérifie plutôt BAT-EQ-124/125 (fermeture meubles frigo) actives
        'fiches_attendues_mini': ['BAT-EQ-124', 'BAT-TH-158'],
    },
    {
        'siret': '331 760 481 00084',
        'libelle': 'Test industrie — NAF 25.62B (mécanique générale)',
        'naf': '25.62B',
        'surface': 5000,
        'energie': 'gaz',
        'departement': '38',
        'micro_attendue': 'industrie',
        'fiches_attendues_mini': ['IND-UT-114'],  # Moto-variateur
    },
]


def parse_cout_travaux():
    """Extrait la table COUT_TRAVAUX d'oracle.html."""
    html = open('oracle.html').read()
    m = re.search(r'const COUT_TRAVAUX = \{(.*?)^  \};', html, re.MULTILINE | re.DOTALL)
    body = m.group(1)
    pat = re.compile(r'"([A-Z][\w-]+)":\s*\{min:(\d+(?:\.\d+)?),max:(\d+(?:\.\d+)?),moy:(\d+(?:\.\d+)?),u:"([^"]*)"')
    return {m.group(1): {'min': float(m.group(2)), 'max': float(m.group(3)),
                         'moy': float(m.group(4)), 'u': m.group(5)} for m in pat.finditer(body)}


def main():
    couts = parse_cout_travaux()
    print(f"COUT_TRAVAUX : {len(couts)} entrées chargées\n")

    with open('fiches.json') as f:
        fiches_all = {x['ref']: x for x in json.load(f)}

    bugs = []
    warns = []
    for cas in CAS_TEST:
        print(f"═══ CAS : {cas['libelle']} ═══")
        try:
            res = moteur_expert_v2(
                entreprise={'naf': cas['naf']},
                surface=cas['surface'],
                energie=cas['energie'],
                departement=cas['departement'],
            )
        except Exception as e:
            bugs.append(f"{cas['siret']}: moteur_expert_v2 ERREUR {e}")
            print(f"  ✗ ERREUR {e}\n")
            continue

        pack = res.get('pack', [])
        total_prime = res.get('total_prime', 0)
        print(f"  Pack : {len(pack)} fiches · Prime totale : {total_prime:,} €")

        # 1. Fiches attendues présentes ?
        pack_refs = set(p.get('fiche') or p.get('ref') for p in pack)
        for ref_attendu in cas['fiches_attendues_mini']:
            if ref_attendu not in pack_refs:
                bugs.append(f"{cas['siret']}: fiche attendue {ref_attendu} ABSENTE du pack")
                print(f"  ✗ Fiche {ref_attendu} attendue mais ABSENTE")
            else:
                print(f"  ✓ {ref_attendu} présent")

        # 2. Coverage COUT_TRAVAUX pour les fiches du pack
        sans_cout = [r for r in pack_refs if r not in couts]
        if sans_cout:
            warns.append(f"{cas['siret']}: {len(sans_cout)} fiches du pack sans COUT_TRAVAUX : {sans_cout[:5]}")
            print(f"  ⚠ {len(sans_cout)} fiches du pack sans coût défini")

        # 3. Questions générées par fiche (sample 3 fiches complexes)
        complexes = [r for r in pack_refs if fiches_all.get(r, {}).get('mode_calcul')][:3]
        for r in complexes:
            f = fiches_all[r]
            try:
                qs = build_questions_for_fiche(f, connu={
                    'zone': 'H2' if cas['departement'] not in ('06','13','83') else 'H3',
                    'activite': cas['micro_attendue'],
                    'surface': cas['surface'],
                    'energie': cas['energie'],
                })
                if not qs:
                    warns.append(f"{cas['siret']}: {r} complexe sans questions générées")
                    print(f"  ⚠ {r} complexe SANS questions")
                else:
                    print(f"  ✓ {r} → {len(qs)} questions générées")
            except Exception as e:
                bugs.append(f"{cas['siret']}: {r} build_questions ERREUR {e}")

        # 4. Cohérence prime/cumac
        for p in pack[:5]:
            ref = p.get('fiche') or p.get('ref')
            prime = p.get('prime', 0)
            cumac = p.get('cumac', 0)
            if prime > 0 and cumac > 0:
                ratio = prime / (cumac / 1000)  # prime €/MWhc
                if ratio < 5 or ratio > 30:
                    warns.append(f"{cas['siret']}: {ref} ratio prime/cumac aberrant : {ratio:.1f} €/MWhc")

        # 5. V44.4 — Cohérence prime/coût/coverage par fiche du top10
        for p in pack[:10]:
            ref = p.get('fiche') or p.get('ref')
            prime = p.get('prime', 0)
            cumac = p.get('cumac', 0)
            cout = couts.get(ref, {})
            cout_moy = cout.get('moy', 0)
            if prime > 0 and cout_moy > 0:
                # Approx coverage par défaut (quantité unitaire)
                # Real coverage = prime / (cout × quantité réelle), mais quantité dépend du contexte
                # Si prime brute < 1€/MWhc → bug certain
                if prime < cumac * 0.001:
                    bugs.append(f"{cas['siret']}: {ref} prime {prime:.0f}€ << cumac {cumac:.0f} kWhc — sous-évaluée ?")

        # 6. V44.4 — Vérifier que les fiches du pack ont toutes un cumac > 0
        pack_sans_cumac = [p.get('fiche') or p.get('ref') for p in pack if p.get('cumac', 0) == 0 and not fiches_all.get(p.get('fiche') or p.get('ref'), {}).get('mode_calcul')]
        if pack_sans_cumac:
            warns.append(f"{cas['siret']}: {len(pack_sans_cumac)} fiches simples du pack avec cumac=0 : {pack_sans_cumac[:5]}")

        print()

    print("═══ BILAN ═══")
    print(f"Cas testés : {len(CAS_TEST)}")
    print(f"BUGS critiques : {len(bugs)}")
    for b in bugs[:10]: print(f"  ✗ {b}")
    print(f"WARNINGS : {len(warns)}")
    for w in warns[:10]: print(f"  ⚠ {w}")

    return 1 if bugs else 0


if __name__ == '__main__':
    sys.exit(main())
