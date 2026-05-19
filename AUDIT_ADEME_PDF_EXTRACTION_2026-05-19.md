# AUDIT_ADEME_PDF_EXTRACTION_2026-05-19.md

**Date** : 2026-05-19 08:33:09
**Cibles** : 50 fiches
**PDF disponibles** : 42
**Parses OK** : 42
**Sans PDF** : 8 → ['BAR-SE-109', 'BAR-TH-106', 'BAR-TH-107', 'BAR-TH-150', 'BAT-TH-140', 'BAT-TH-141', 'BAT-TH-146', 'IND-UT-121']

## 🟢 Extractions exploitables (cumac dict valide)

| Ref | Nom | Type | Cumac extrait | Variables | Notes |
|-----|-----|------|---------------|-----------|-------|
| **BAR-SE-107** | (nom non extrait) | unitaire | {'H1': 13, 'H2': 10, 'H3': 8} | ['debit'] | ✓ OK |
| **BAR-TH-110** | (nom non extrait) | unitaire | {'H1': 1700, 'H2': 1400, 'H3': 910} | [] | ✓ OK |
| **BAR-TH-116** | (nom non extrait) | surface | {'H1': 300, 'H2': 250, 'H3': 160} | ['surface'] | ✓ OK |
| **BAR-TH-117** | (nom non extrait) | unitaire | {'H3': 930} | [] | ✓ OK |
| **BAR-TH-122** | (nom non extrait) | unitaire | {'H1': 16, 'H2': 14, 'H3': 10} | ['puissance'] | ✓ OK |
| **BAR-TH-137** | (nom non extrait) | surface | {'H1': 48, 'H2': 40, 'H3': 29} | ['surface', 'nb_logements'] | ✓ OK |
| **AGRI-UT-104** | (nom non extrait) | unitaire | {'H2': 10, 'H3': 9} | ['puissance'] | ✓ OK |

## 🟡 Extractions suspectes (probable bruit OCR/regex)

| Ref | Cumac | Pourquoi suspect |
|-----|-------|------------------|
| BAR-EN-110 | {'H1': 7, 'H2': 6, 'H3': 4} | ⚠ valeurs très faibles, vérifier |
| BAR-TH-111 | {'H1': 2, 'H2': 1, 'H3': 1} | ⚠ valeurs très faibles, vérifier |

## 🔴 Sans cumac extrait (parser ne sait pas — lookup manuel requis)

Ces fiches ont des tables ADEME multi-paramètres (puissance × surface, etc.) que
le parser actuel ne gère pas. Lookup manuel sur https://atee.fr/cee/fiches requis.

- **BAR-TH-102** (unitaire) — variables=['surface']
- **BAR-TH-130** (unitaire) — variables=['surface']
- **BAR-TH-139** (unitaire) — variables=['puissance']
- **AGRI-TH-108** (🔧 COMPLEXE) — variables=['puissance', 'surface']
- **AGRI-TH-117** (🔧 COMPLEXE) — variables=['puissance', 'surface']
- **AGRI-UT-101** (🔧 COMPLEXE) — variables=['puissance']
- **AGRI-UT-102** (🔧 COMPLEXE) — variables=['puissance']
- **BAT-EQ-117** (🔧 COMPLEXE) — variables=['puissance']
- **BAT-EQ-130** (🔧 COMPLEXE) — variables=['puissance']
- **BAT-EQ-131** (🔧 COMPLEXE) — variables=[]
- **BAT-TH-112** (🔧 COMPLEXE) — variables=['puissance']
- **BAT-TH-115** (🔧 COMPLEXE) — variables=['puissance', 'surface']
- **BAT-TH-122** (🔧 COMPLEXE) — variables=['puissance', 'surface']
- **BAT-TH-135** (🔧 COMPLEXE) — variables=['puissance']
- **BAT-TH-153** (🔧 COMPLEXE) — variables=['puissance']
- **BAT-TH-157** (🔧 COMPLEXE) — variables=['puissance', 'surface', 'rendement']
- **BAT-TH-161** (🔧 COMPLEXE) — variables=['puissance']
- **IND-BA-114** (🔧 COMPLEXE) — variables=[]
- **IND-UT-102** (🔧 COMPLEXE) — variables=['puissance']
- **IND-UT-114** (🔧 COMPLEXE) — variables=['puissance']
- **IND-UT-118** (🔧 COMPLEXE) — variables=['puissance']
- **IND-UT-125** (🔧 COMPLEXE) — variables=['puissance']
- **IND-UT-131** (🔧 COMPLEXE) — variables=['surface']
- **IND-UT-132** (🔧 COMPLEXE) — variables=['puissance', 'rendement']
- **IND-UT-133** (🔧 COMPLEXE) — variables=['puissance', 'duree_fonctionnement']
- **IND-UT-137** (🔧 COMPLEXE) — variables=['puissance', 'debit', 'duree_fonctionnement']
- **IND-UT-138** (🔧 COMPLEXE) — variables=['puissance', 'rendement', 'duree_fonctionnement']
- **IND-UT-139** (🔧 COMPLEXE) — variables=['puissance', 'rendement']
- **RES-CH-106** (🔧 COMPLEXE) — variables=[]
- **TRA-EQ-106** (🔧 COMPLEXE) — variables=[]
- **TRA-EQ-126** (🔧 COMPLEXE) — variables=['puissance']
- **TRA-EQ-127** (🔧 COMPLEXE) — variables=['puissance']
- **IND-UT-115** (unitaire) — variables=['puissance']

## 📥 8 PDF introuvables dans l'index ADEME (peut-être abrogées ou autre source)

- BAR-SE-109
- BAR-TH-106
- BAR-TH-107
- BAR-TH-150
- BAT-TH-140
- BAT-TH-141
- BAT-TH-146
- IND-UT-121

## 🎯 Recommandations

1. **Valider manuellement les 9 extractions exploitables** ci-dessus contre ATEE/legifrance
2. **Lookup manuel** les 33 sans cumac + 8 sans PDF (chantier ~3-4h)
3. **Améliorer parse_pdf.py** : utiliser pdfplumber.extract_table() pour tables complexes
4. **Auto-apply** uniquement les extractions validées humainement