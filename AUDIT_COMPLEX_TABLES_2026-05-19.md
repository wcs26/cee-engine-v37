# AUDIT_COMPLEX_TABLES_2026-05-19.md

**Parse de 30 fiches complexes désactivées V39.0.7 — extraction PDF V39.2.0**

- 22/30 PDFs ont des extractions exploitables
- 8/30 sans extraction (texte pur ou format inhabituel)
- Patterns détectés : 18 lookup_1d, 12 lookup_2d, 2 formules

## 🟢 Extractions à valider (table_cumac proposée)

Format attendu pour réactiver une fiche : injecter `table_cumac` (dict)
+ `mode_calcul: 'table'` + `variables: [...]`. Puis passer `actif: true`.

---

### AGRI-TH-108 — Chauffage infrarouge élevage
- PDF: `AGRI-TH-108 v A35-2 à compter du 01-10-2020.pdf` (3p, 5 tables)

**Extraction #1** — type=`2d` class=`lookup_2d_or_more` (table 5×3)
Headers : `Efficacité énergétique saisonnière (ηs)` × `Type de serre`
```
  "111% ≤ ηs < 126%" × "Maraîchère" = 800
  "111% ≤ ηs < 126%" × "Horticole" = 380
  "126% ≤ ηs" × "Maraîchère" = 970
  "126% ≤ ηs" × "Horticole" = 460
```

**Extraction #2** — type=`2d` class=`lookup_2d_or_more` (table 5×3)
Headers : `COP` × `Type de serre`
```
  "3,4 ≤ COP < 4" × "Maraîchère" = 780
  "3,4 ≤ COP < 4" × "Horticole" = 370
  "4 ≤ COP" × "Maraîchère" = 1040
  "4 ≤ COP" × "Horticole" = 490
```

### AGRI-UT-101 — Moto-variateur synchrone aimants
- PDF: `AGRI-UT-101 v A24-2 après le 01-04-2017.pdf` (3p, 4 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 7×2)
```python
"table_cumac": {
    "Pompage d’irrigation": 2100,
    "Ventilation de bâtiments d’élevage": 18300,
    "Ventilation en serre": 14900,
    "Pompe à vide d’une salle de traite": 2100,
    "Chaufferie d’une serre (pompe, ventilateur brûleur)": 6400,
    "Autres applications": 4500,
},
"mode_calcul": "table",
"variables": ["application"],
```

### AGRI-UT-102 — VEV moteur asynchrone
- PDF: `AGRI-UT-102 v A22-2.pdf` (3p, 4 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 7×2)
```python
"table_cumac": {
    "Pompe d’irrigation": 1600,
    "Ventilateur de bâtiments d’élevage": 19600,
    "Ventilation d’une serre": 11500,
    "Pompe à vide d’une salle de traite": 2800,
    "Chauffage d’une serre (pompe, ventilateur d’un brûleur)": 7700,
    "Autres applications": 2300,
},
"mode_calcul": "table",
"variables": ["application"],
```

### AGRI-UT-104 — Régulation haute pression flottante
- PDF: `AGRI-UT-104.pdf` (3p, 3 tables)

**Extraction #1** — type=`2d` class=`lookup_2d_or_more` (table 4×3)
Headers : `Zone climatique` × `Montant en kWh cumac par kW`
```
  "H1 ou H2" × "10 600" = 10600
  "H3" × "9 700" = 9700
```

### BAT-EQ-117 — Installation frigo CO2 sub/transcritique
- PDF: `BAT-EQ-117 vA40-2 à compter du 01-04-2022_0.pdf` (7p, 8 tables)

**Extraction #1** — type=`2d` class=`lookup_2d_or_more` (table 5×3)
Headers : `` × `Montants en kWh cumac / kW`
```
  "Option 0" × "8 500" = 8500
  "Option 1 ou 1 bis" × "10 300" = 10300
  "Option 2" × "12 700" = 12700
```

### BAT-EQ-130 — Condensation frigo haute efficacité
- PDF: `BAT-EQ-130.pdf` (6p, 7 tables)

**Extraction #1** — type=`2d` class=`lookup_2d_or_more` (table 5×4)
Headers : `D T en °C` × `Montant en kWh cumac par kW selon l’application`
```
  "8" × "500" = 500
  "7" × "770" = 770
  "6" × "1 100" = 1100
```

**Extraction #2** — type=`2d` class=`lookup_2d_or_more` (table 15×4)
Headers : `D T en °C` × `Montant en kWh cumac par kW selon l’application`
```
  "12" × "580" = 580
  "11" × "790" = 790
  "10" × "1 000" = 1000
  "9" × "1 200" = 1200
  "8" × "1 500" = 1500
  "7" × "1 700" = 1700
  "6" × "2 000" = 2000
  "5" × "2 300" = 2300
  "4" × "2 600" = 2600
  "3" × "2 900" = 2900
  "2" × "3 200" = 3200
  "1" × "3 600" = 3600
  "0" × "4 000" = 4000
```

**Extraction #3** — type=`2d` class=`lookup_2d_or_more` (table 15×4)
Headers : `D T en °C` × `Montant en kWh cumac par kW selon l’application`
```
  "22" × "580" = 580
  "21" × "790" = 790
  "20" × "1 000" = 1000
  "19" × "1 200" = 1200
  "18" × "1 500" = 1500
  "17" × "1 700" = 1700
  "16" × "2 000" = 2000
  "15" × "2 300" = 2300
  "14" × "2 600" = 2600
  "13" × "2 900" = 2900
  "12" × "3 200" = 3200
  "11" × "3 600" = 3600
  "10" × "4 000" = 4000
```

### BAT-TH-112 — VEV moteur asynchrone tertiaire
- PDF: `BAT-TH-112 v A22-2.pdf` (3p, 4 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 6×2)
```python
"table_cumac": {
    "Chauffage, pompage": 9600,
    "Ventilation, renouvellement d’air": 11400,
    "Réfrigération": 3900,
    "Climatisation": 990,
    "Autres applications": 990,
},
"mode_calcul": "table",
"variables": ["application"],
```

### BAT-TH-115 — Climatiseur performant DOM
- PDF: `BAT-TH-115 v A15-2.pdf` (3p, 4 tables)

**Extraction #1** — type=`2d` class=`lookup_2d_or_more` (table 9×5)
Headers : `` × `Montant en kWh cumac`
```
  "Bureaux" × "1 100" = 1100
  "Enseignement" × "900" = 900
  "Commerce" × "1 800" = 1800
  "Hôtellerie - restauration" × "1 300" = 1300
  "Santé" × "2 000" = 2000
  "Autres" × "900" = 900
```

### BAT-TH-122 — Programmateur intermittence clim DOM
- PDF: `BAT-TH-122.pdf` (3p, 3 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 7×2)
```python
"table_cumac": {
    "Bureaux": 560,
    "Commerce": 180,
    "Hôtellerie": 340,
    "Enseignement": 460,
    "Santé": 210,
    "Autres secteurs": 180,
},
"mode_calcul": "table",
"variables": ["application"],
```

### BAT-TH-135 — Régulation haute pression flottante froid DOM
- PDF: `BAT-TH-135.pdf` (3p, 3 tables)

**Extraction #1** — type=`2d` class=`lookup_2d_or_more` (table 3×3)
Headers : `Montant en kWh cumac par kW` × ``
```
  "2 700" × "2 500" = 2700
```

### BAT-TH-161 — Maintien T° groupes électrogènes PAC
- PDF: `BAT-TH-161 vA62-1 à compter du 31-08-2024_0.pdf` (5p, 2 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 3×2)
```python
"table_cumac": {
    "800 kW ≤ P ≤ 1 200 kW": 167800,
    "1 200 kW < P": 279600,
},
"mode_calcul": "table",
"variables": ["application"],
```

### IND-UT-102 — VEV moteur asynchrone industriel
- PDF: `IND-UT-102 v A19-2.pdf` (3p, 4 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 6×2)
```python
"table_cumac": {
    "Pompage": 12400,
    "Ventilation": 12200,
    "Compresseur d’air": 11900,
    "Compresseur frigorifique": 7100,
    "Autres applications": 5500,
},
"mode_calcul": "table",
"variables": ["application"],
```

### IND-UT-114 — Moto-variateur synchrone aimants
- PDF: `IND-UT-114 v A24-2 après le 01-04-2017.pdf` (3p, 4 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 6×2)
```python
"table_cumac": {
    "Pompage": 17800,
    "Ventilation": 17600,
    "Compresseur d’air": 9200,
    "Compresseur frigorifique": 14500,
    "Autre application": 11400,
},
"mode_calcul": "table",
"variables": ["application"],
```

### IND-UT-118 — Brûleur récup chaleur four industriel
- PDF: `IND-UT-118.pdf` (3p, 9 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 5×2)
```python
"table_cumac": {
    "600 ≤ T ≤ 750": 1600,
    "750 < T ≤ 1000": 2500,
    "1000 < T ≤ 1250": 4100,
    "1250 < T": 5800,
},
"mode_calcul": "table",
"variables": ["application"],
```

**Extraction #2** — type=`1d` class=`lookup_1d` (table 5×2)
```python
"table_cumac": {
    "600 ≤ T ≤ 750": 2300,
    "750 < T ≤ 1000": 3500,
    "1000 < T ≤ 1250": 5600,
    "1250 < T": 7800,
},
"mode_calcul": "table",
"variables": ["application"],
```

**Extraction #3** — type=`1d` class=`lookup_1d` (table 5×2)
```python
"table_cumac": {
    "1x8": 1000,
    "2x8": 2300,
    "3x8 avec arrêt le week-end": 3100,
    "3x8 sans arrêt le week-end": 4300,
},
"mode_calcul": "table",
"variables": ["application"],
```

### IND-UT-125 — Traitement eau chaudière vapeur
- PDF: `IND-UT-125.pdf` (3p, 3 tables)

**Extraction #1** — type=`2d` class=`lookup_2d_or_more` (table 6×5)
Headers : `Mode de fonctionnement du site` × `Montant en kWh cumac par kW selon la zone géographique d’installation de la chaudière`
```
  "1x8h" × "70" = 70
  "2x8h" × "160" = 160
  "3x8h avec arrêt le week-end" × "220" = 220
  "3x8h sans arrêt le week-end" × "300" = 300
```

### IND-UT-131 — Isolation parois planes/cylindriques
- PDF: `IND-UT-131 vA37-2 à compter du 01-04-2021.pdf` (5p, 7 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 6×2)
```python
"table_cumac": {
    "- 80°C < T ≤ -10°C": 300,
    "- 10°C < T ≤ 10°C": 180,
    "40°C < T ≤ 100°C": 1050,
    "100°C < T ≤ 300°C": 1900,
    "T > 300°C": 1850,
},
"mode_calcul": "table",
"variables": ["application"],
```

**Extraction #2** — type=`1d` class=`lookup_1d` (table 6×2)
```python
"table_cumac": {
    "- 80°C < T ≤ - 10°C": 450,
    "- 10°C < T ≤ 10°C": 400,
    "40°C < T ≤ 100°C": 1300,
    "100°C < T≤ 300°C": 2050,
    "T > 300°C": 1850,
},
"mode_calcul": "table",
"variables": ["application"],
```

### IND-UT-132 — Moteur asynchrone IE4
- PDF: `IND-UT-132.pdf` (2p, 2 tables)

**Extraction #1** — type=`formula` class=`formula` (table 3×3)
```python
  # tranche : 4900 × P + 2600
  # tranche : 700 × P + 12000
  # tranche : 1600 × P + 0
"mode_calcul": "formule",
"formule": "voir tranches ci-dessus selon P",
```

### IND-UT-133 — Système pilotage moteur récupération
- PDF: `IND-UT-133.pdf` (3p, 3 tables)

**Extraction #1** — type=`formula` class=`formula` (table 2×1)
```python
  # tranche : 25 × P + 0
"mode_calcul": "formule",
"formule": "voir tranches ci-dessus selon P",
```

### RES-CH-106 — Calorifugeage canalisations réseau
- PDF: `RES-CH-106 vA60-4 à compter du 01-03-2024.pdf` (8p, 10 tables)

**Extraction #1** — type=`2d` class=`lookup_2d_or_more` (table 17×4)
Headers : `Montant unitaire en kWh cumac selon le diamètre nominal DN (en mm) du réseau` × ``
```
  "32" × "3 300" = 32
  "40" × "3 800" = 40
  "50" × "4 500" = 50
  "60" × "5 000" = 60
  "65" × "5 300" = 65
  "80" × "6 000" = 80
  "100" × "6 800" = 100
  "125" × "7 600" = 125
  "150" × "8 400" = 150
  "175" × "9 100" = 175
  "200" × "9 800" = 200
  "250" × "11 100" = 250
  "300" × "12 300" = 300
  "350" × "13 400" = 350
  "≥ 400" × "14 600" = 400
```

**Extraction #2** — type=`2d` class=`lookup_2d_or_more` (table 17×4)
Headers : `Montant unitaire en kWh cumac selon le diamètre nominal DN (en mm) du réseau` × ``
```
  "32" × "3 800" = 32
  "40" × "4 400" = 40
  "50" × "4 900" = 50
  "60" × "5 400" = 60
  "65" × "5 700" = 65
  "80" × "6 500" = 80
  "100" × "7 500" = 100
  "125" × "8 300" = 125
  "150" × "9 100" = 150
  "175" × "10 100" = 175
  "200" × "11 000" = 200
  "250" × "12 900" = 250
  "300" × "14 300" = 300
  "350" × "16 200" = 350
  "≥ 400" × "17 800" = 400
```

### TRA-EQ-106 — Pneus basse résistance roulement
- PDF: `TRA-EQ-106 v A14-1.pdf` (3p, 4 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 4×2)
```python
"table_cumac": {
    "A": 0,
    "B": 0,
    "C": 0,
},
"mode_calcul": "table",
"variables": ["application"],
```

### TRA-EQ-126 — Remotorisation électrique/hybride bateau
- PDF: `TRA-EQ-126.pdf` (7p, 11 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 4×2)
```python
"table_cumac": {
    "Bateau de réception destiné à un usage principalement privatif * et bateau de travail": 147,
    "Petit bateau à passagers": 103,
    "Bateau restaurant, bateau promenades, automoteur, bateau de plaisance et péniche-hôtel": 71,
},
"mode_calcul": "table",
"variables": ["application"],
```

**Extraction #2** — type=`1d` class=`lookup_1d` (table 4×2)
```python
"table_cumac": {
    "Bateau de réception destiné à un usage principalement privatif * et bateau de travail": 54,
    "Petit bateau à passagers": 40,
    "Bateau restaurant, bateau promenades, automoteur, bateau de plaisance et péniche-hôtel": 29,
},
"mode_calcul": "table",
"variables": ["application"],
```

### TRA-EQ-127 — Bateau électrique/hybride eaux intérieures
- PDF: `TRA-EQ-127 vA54-1 à compter du 01-10-2023.pdf` (8p, 12 tables)

**Extraction #1** — type=`1d` class=`lookup_1d` (table 5×2)
```python
"table_cumac": {
    "Bateau de réception et bateau de travail": 121,
    "Petit bateau à passagers": 79,
    "Bateau restaurant, bateau promenade, automoteur, bateau de croisière fluviale avec hébergement et péniche-hôtel": 43,
    "Bateau de plaisance": 31,
},
"mode_calcul": "table",
"variables": ["application"],
```

**Extraction #2** — type=`1d` class=`lookup_1d` (table 5×2)
```python
"table_cumac": {
    "Bateau de réception et bateau de travail": 113,
    "Petit bateau à passagers": 70,
    "Bateau restaurant, bateau promenade, automoteur, bateau de croisière fluviale avec hébergement et péniche-hôtel": 35,
    "Bateau de plaisance": 23,
},
"mode_calcul": "table",
"variables": ["application"],
```

**Extraction #3** — type=`1d` class=`lookup_1d` (table 5×2)
```python
"table_cumac": {
    "Bateau de réception et bateau de travail": 59,
    "Petit bateau à passagers": 38,
    "Bateau restaurant, bateau promenade, automoteur, bateau de croisière fluviale avec hébergement et péniche-hôtel": 21,
    "Bateau de plaisance": 15,
},
"mode_calcul": "table",
"variables": ["application"],
```


## 🔴 Sans extraction (review manuelle requise)

Ces fiches sont en texte pur ou ont un format de table inhabituel.
Lookup manuel ATEE/ADEME ou amélioration parser nécessaire.

- **AGRI-TH-117** — Déshumidificateur thermodynamique serres (4p, 5 tables non classifiables)
- **BAT-EQ-131** — Conduits de lumière naturelle (3p, 5 tables non classifiables)
- **BAT-TH-153** — Confinement allées Data Center (3p, 4 tables non classifiables)
- **BAT-TH-157** — Chaudière biomasse collective tertiaire (5p, 2 tables non classifiables)
- **IND-BA-114** — Conduits de lumière naturelle (3p, 4 tables non classifiables)
- **IND-UT-137** — PAC rehausse T° chaleur fatale (8p, 4 tables non classifiables)
- **IND-UT-138** — Conversion chaleur fatale électricité/air (6p, 1 tables non classifiables)
- **IND-UT-139** — Stockage chaleur fatale (4p, 0 tables non classifiables)