# AUDIT_TODO_FINAL — 13 fiches complexes à activer manuellement

Pour chaque fiche : section 5 du PDF officiel ADEME + bloc JSON suggéré.
Coller le bloc dans `fiches.json` puis passer `actif: true` pour activer.

---

## BAT-EQ-130 — Condensation frigo haute efficacité

**Fiche actuelle** : `actif=False` `type=complexe` `params=['puissance']`

**Section 5 du PDF (Montant cumac)** :
```
Mise en place d’un système de condensation à eau seul (sur nappe ou cours d’eau) permettant un D T, différence
entre la température de condensation du fluide frigorigène et celle de l’eau en entrée du condenseur, inférieure ou
égale à 8°C :
Montant en kWh cumac par kW
Puissance électrique
selon l’application
D T nominale totale du
Réfrigération ou
en °C Climatisation de confort Climatisation groupe de production
conditionnement
hors datacenter en datacenter de froid en kW
d’ambiance hors confort
8 500 1 900 1 300
7 770 3 000 2 000 X P
6 1 100 4 100 2 700
Mise en place d’un condenseur à air sec (adiabatique ou non) ou d’un condenseur à eau et d’un aéroréfrigérant à air
sec (adiabatique ou non) permettant une différence D T entre la température de condensation du fluide frigorigène et
celle 
```

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## BAT-TH-115 — Climatiseur performant DOM

**Fiche actuelle** : `actif=False` `type=complexe` `params=['quantite']`

**Section 5 du PDF (Montant cumac)** :
```
Facteur
Montant en kWh cumac
correctif
Classe d'efficacité énergétique de l'appareil
Branche d’activité
A A+ A++ A+++
Bureaux 1 100 2 000 2 700 5 100
Enseignement 900 1 600 2 200 4 100
X F
Commerce 1 800 3 200 4 400 8 200
Hôtellerie - restauration 1 300 2 300 3 200 5 900
Santé 2 000 3 700 5 100 9 500
Autres 900 1 600 2 200 4 100
Le facteur correctif F est fonction de la puissance du climatiseur.
Puissance frigorifique
de l’appareil Facteur correctif
en kW (ou BTU/h)
2,05 (7 000) 0,58
2,64 (9 000) 0,75
3,52 (12 000) 1
4,40 (15 000) 1,25
5,28 (18 000) 1,5
6,16 (21 000) 1,75
7,03 (24 000) 2
8,21 (28 000) 2,33
*SEER : Seasonal Energy Efficiency Ratio ou coefficient d’efficacité énergétique saisonnier
```

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## BAT-TH-135 — Régulation haute pression flottante froid DOM

**Fiche actuelle** : `actif=False` `type=complexe` `params=['puissance']`

**Section 5 du PDF (Montant cumac)** :
```
Montant en kWh cumac par kW
Puissance électrique nominale
totale du groupe de production
Climatisation hors Climatisation
Réfrigération de froid en kW
datacenter datacenter
2 700 2 500 4 700 X P
Dans chaque cas, la puissance électrique nominale à retenir est celle figurant sur la plaque signalétique du groupe de
production de froid (mono-compresseur ou multi-compresseurs). A défaut, la puissance à retenir est la puissance
électrique absorbée mentionnée sur un document issu du fabricant du groupe mono-compresseur ou multi-
compresseurs. La puissance du ou des compresseurs de secours n’est pas comptabilisée.
```

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## RES-CH-106 — Calorifugeage canalisations réseau

**Fiche actuelle** : `actif=False` `type=complexe` `params=['longueur']`

**Section 5 du PDF (Montant cumac)** :
```
Le montant de certificats est calculé pour chaque élément de canalisation de diamètre nominal DN de la tuyauterie
concernée et de longueur L, et selon la durée annuelle d’utilisation du réseau :
Pour les canalisations respectant les exigences relatives à la classe d’isolation thermique 4 définie par la norme
NF EN 12828 :
Durée Facteur correctif Montant unitaire en kWh cumac selon le
annuelle tenant compte de diamètre nominal DN (en mm) du réseau
Longueur d'utilisation l’utilisation du
Eau Eau
(en m) du réseau réseau DN Vapeur
chaude surchauffée
L X 12 mois 1,00 X 32 3 300 5 000 8 700
11 mois 0,92 40 3 800 5 900 10 800
10 mois 0,83 50 4 500 6 800 13 000
9 mois 0,75 60 5 000 7 700 -
8 mois 0,67 65 5 300 8 100 13 600
7 mois 0,58 80 6 000 9 100 15 900
6 mois 0,50 100 6 800 10 400 19 700
125 7
```

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## TRA-EQ-106 — Pneus basse résistance roulement

**Fiche actuelle** : `actif=False` `type=complexe` `params=['quantite']`

**Section 5 du PDF (Montant cumac)** :
```
Classe d’efficacité en Kilométrage annuel
Montant en Nombre de
carburant des pneumatiques moyen parcouru par
kWh cumac pneumatiques
montés les véhicules
A 0,011 N
A
B 0,008 X N X Y
B
C 0,006 N
C
N est le nombre de pneumatiques de classe d’efficacité en carburant A
A
N est le nombre de pneumatiques de classe d’efficacité en carburant B
B
N est le nombre de pneumatiques de classe d’efficacité en carburant C
C
```

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## AGRI-TH-117 — Déshumidificateur thermodynamique serres

**Fiche actuelle** : `actif=False` `type=complexe` `params=['puissance']`

**Section 5 du PDF (Montant cumac)** :
```
Montant du gain en Surface de serre
kWh cumac par m² équipée (m²)
710 X S
```

**Coefficients détectés** :
- `710.0 × S`

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## BAT-EQ-131 — Conduits de lumière naturelle

**Fiche actuelle** : `actif=False` `type=complexe` `params=['surface']`

**Section 5 du PDF (Montant cumac)** :
```
Montant en kWh Secteur d’application Section totale S
Zone climatique
cumac par m2 tertiaire en m²
Commerce 1
France
1
métropolitaine
28 500 X Bureaux 0,75 X X S
Autres France
0,6 1,5
Secteurs d’outre-mer
S est la somme des sections de la totalité des tubes des conduits de lumière naturelle installés, en m².
```

**Coefficients détectés** :
- `28500.0 × Bureaux`
- `0.75 × X`

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## BAT-TH-153 — Confinement allées Data Center

**Fiche actuelle** : `actif=False` `type=complexe` `params=['puissance']`

**Section 5 du PDF (Montant cumac)** :
```
Puissance électrique
Montant en
Gain sur les températures de nominale du groupe de
kWh par
cumac consigne (°C) production de froid (ou
(kW.°C)
batteries froides*) (kW)
1 500 X ∆T X P
La puissance électrique à prendre en compte est celle figurant sur la plaque signalétique du ou des compresseur(s)
ou à défaut celle indiquée sur un document issu du fabricant.
*Dans le cas où le groupe de production de froid n’alimente pas uniquement le Data Center, la puissance nominale
électrique à prendre en compte est celle de la ou des batterie(s) froide(s) installée(s).
NB : D T représente soit l’augmentation moyenne en °C de la température de consigne de la production d’eau
glacée alimentant la boucle d’eau des unités de conditionnement d’air (CRAC), soit l’augmentation moyenne en
°C de la température 
```

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## BAT-TH-157 — Chaudière biomasse collective tertiaire

**Fiche actuelle** : `actif=False` `type=complexe` `params=['puissance']`

**Section 5 du PDF (Montant cumac)** :
```
Le montant de certificats d’économies d’énergie est déterminé par l’application de la formule ci-après :
Pour une chaudière de puissance Pour une chaudière de puissance
inférieure ou égale à 500 kW supérieure à 500 kW
Q x 4,8 Q x 3,4
Q est la chaleur nette utile produite par la chaudière biomasse installée en kWh/an. Elle est déterminée à partir de
l’étude de dimensionnement préalable à la mise en place de la chaudière biomasse.
```

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## IND-BA-114 — Conduits de lumière naturelle

**Fiche actuelle** : `actif=False` `type=complexe` `params=['surface']`

**Section 5 du PDF (Montant cumac)** :
```
Montant en kWh Section totale S
Zone climatique
cumac par m2 en m²
France
X 1 X
métropolitaine
17 100 S
France d’outre-
1,5
mer
S est la somme des sections de la totalité des tubes des conduits de lumière naturelle installés, en m².
```

**Coefficients détectés** :
- `1.0 × m`

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## IND-UT-137 — PAC rehausse T° chaleur fatale

**Fiche actuelle** : `actif=False` `type=complexe` `params=['puissance']`

**Section 5 du PDF (Montant cumac)** :
```
Le volume de certificats d’économies d’énergie est déterminé comme suit :
10,986 x (Q – E )
élec
Q (en kWh/an) est l’énergie thermique annuelle fournie sous forme de chaleur en sortie du système, calculée au
d du II.3 ci-dessus de l’étude de dimensionnement.
E (en kWh/an) est l’énergie électrique annuelle absorbée par le système, qui est la somme des énergies
élec
électriques absorbées par le ou les compresseur(s) et les auxiliaires, calculée au e du II.3 ci-dessus de l’étude de
dimensionnement.
```

**Coefficients détectés** :
- `10.986 × (Q`

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## IND-UT-138 — Conversion chaleur fatale électricité/air

**Fiche actuelle** : `actif=False` `type=complexe` `params=['puissance']`

**Section 5 du PDF (Montant cumac)** :
```
Le volume de certificats d’économies d’énergie est déterminé comme suit :
14,134 x D x (P x η – P )
récup conso
D, P , η et P sont des paramètres dont les valeurs sont indiquées dans l’étude de dimensionnement :
récup conso
- D est la durée annuelle de fonctionnement (en heures) ;
- P est la puissance thermique apportée par le fluide caloporteur à la machine thermodynamique (en kW
récup
thermique) ;
- η est le rendement brut estimé de la machine thermodynamique (en %) ;
- P est la puissance électrique absorbée par les auxiliaires (en kW électrique).
conso
```

**Coefficients détectés** :
- `14.134 × D`

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---

## IND-UT-139 — Stockage chaleur fatale

**Fiche actuelle** : `actif=False` `type=complexe` `params=['puissance']`

**Section 5 du PDF (Montant cumac)** :
```
Le volume de certificats d’économies d’énergie est déterminé comme suit :
14,134 x η x C x Nc
η, C et Nc sont des paramètres dont les valeurs sont indiquées dans l’étude de dimensionnement :
- η est le rendement du système de stockage (en %) ;
- C est la capacité maximale de stockage de chaleur du système (en kWh) ;
- Nc est le nombre annuel de cycles équivalents à 100 % de la capacité maximale du système de stockage,
effectués sur une année représentative.
```

**Bloc JSON à coller dans `fiches.json`** (à adapter selon section 5) :
```json
"table_cumac": {},
"mode_calcul": "formule_tranches",
"tranches": [
  {"min": 0, "max": 1e9, "a": COEFFICIENT_ICI, "b": 0}
],
"variables": ["surface"],  // ou puissance/quantite/Q selon formule
"actif": true
```

---
