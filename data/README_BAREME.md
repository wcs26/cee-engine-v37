# Import barème coûts travaux officiel

## Pour fiabiliser les % de couverture et marges V44.0

Le système utilise actuellement la table `COUT_TRAVAUX` interne (244 entrées,
fourchettes marché 2026 indicatives, ±20-30% vs réalité).

Pour précision absolue, dépose un fichier CSV avec :

### Format attendu (V44.1)

```csv
ref_CEE,cout_min,cout_max,cout_moy,unite,source
BAT-EN-101,18,32,24,m²,CAPEB 2026
BAT-TH-158,110,165,140,m²,CAPEB 2026
...
```

Colonnes :
- `ref_CEE` : référence fiche (BAR-EN-101, BAT-TH-158, IND-UT-114, ...)
- `cout_min` / `cout_max` / `cout_moy` : prix en € HT
- `unite` : m², kW, point, logement, installation, etc.
- `source` : libellé source (CAPEB 2026, Batiprix Q1, devis interne, ...)

### Chemin de dépôt

```
~/CEE_ENGINE/data/capeb_bareme.csv
```

ou

```
~/CEE_ENGINE/data/bareme_couts.csv  (nom générique)
```

### Comportement après import

- Au démarrage de l'app, si le fichier existe :
  - Les coûts uploadés ÉCRASENT la table COUT_TRAVAUX
  - Chaque ligne du classement V44.0 affiche le badge 🏛 source
  - Les % de couverture deviennent référencés officiellement
- Si le fichier est absent : fallback table interne avec tag 📊 estimation marché

## Sources possibles

| Source | Coût | Couverture fiches CEE |
|--------|------|------------------------|
| CAPEB | ~200€/an adhésion | 100% poste résidentiel/tertiaire |
| FFB Batiprix | ~250€/an | 100% tous postes |
| Bordereau Le Moniteur | ~300€/an | 100% tous postes |
| ATEE FOST | gratuit | Indicatif partiel |
| Devis fournisseur propre | gratuit | Limité aux opérations contractées |
