---
name: GET1TECH — template historique CEE de Jimmy (2020-2022)
description: Bureau d'ingénierie CEE prédécesseur d'OXEO. Modèle "0€ reste à charge" + parrainage asso/tertiaire. CRM, scripts, conformité PNCEE, montage juridique LSF Energie/G1T.
type: reference
originSessionId: 2df11f34-7c9e-449e-84cf-ffec1837e5ed
---
## Identité juridique
- **GET1TECH** SARL — RCS Paris 797 552 858 — capital 15 000€ — siège 12 rue Blaise Pascal 92200 Neuilly-sur-Seine
- Gérant : **Michael WEITZ**
- Bureau d'études partenaire : **LSF ENERGIE** SASU — RCS Paris 838 170 421 — capital 100 000€ — 59 av La Grande Armée 75116 Paris — Gérant **Jonathan LUMBROSO**
- Montage : LSF = BE / GET1TECH = maître d'œuvre / Entreprise Adhérente = bénéficiaire
- Tagline : "Au service de la rénovation énergétique" / "Agir pour l'avenir"

## Modèle économique (template "0€ reste à charge")
- Adhésion **gratuite** à l'offre LSF/G1T → accès valorisation CEE
- **Devis 0€ NET** (sans reste à charge) signé avant chantier
- Accompagnement gratuit pour entreprise adhérente, financé par entreprises partenaires + valorisation CEE
- Cible : copropriétés, collectivités, bailleurs, **entreprises Personnes Morales uniquement**
- Annexe 1 : liste filiales/établissements concernés (multi-sites)
- Annonce client : "subventions rénovation montant **390K€/bâtiment éligible**"

## Pipeline commercial (trame ENOPTEA→GET1TECH 16 étapes)
1. Prise contact (rappel 1ère opération, satisfaction)
2. But : FUSION ENOPTEA + GET1TECH, clients "FAVORISÉS" car déjà clients
3. Que fait G1T : EN CHARGE DE LA DISTRIBUTION DES SUBVENTIONS
4. Pourquoi : décret tertiaire CO2 (-30% 2030, -40% 2040, -50% 2050)
5. Profitable : 100% subventionné, sans dépense, sans avance
6. Montant : 390K€/bâtiment éligible
7. Avantages : économies 15-25% facture, éco-responsable
8. Éligibilité : conditions UNIQUEMENT TECHNIQUES
9. Coordinateur : 8 questions techniques + 3 sondages, durée **4 minutes** appel
10. Calendrier : RDV 24-48h pour réponse éligibilité
11. Coordonnées + mail récap
13. 2 options : non éligible (vous aurez essayé) / éligible (1ère sub déplacement métreur, postes 0€, économie estimée, **bonus réversion chèque environnement CEE/m²**, signature convention en ligne)
14. Clôture : récap + **"bouquet de fleurs"** (signature de gratitude) + prise de congé
15-16. Interne : mail récap + CRM (Insee + Geoportail)

## CRM GET1TECH (template UI vu en pdf 2021)
- Champs client : Statut / Statut gestionnaire / Raison sociale / Civilité-Prénom-Nom-Fonction / SIRET / SIREN / RCS / TVA intra / Forme juridique / Capital / **Code NAF (APE)** / Adresse / **Parcelle cadastrale** / Tél / Email / **Téléopérateur** / Source / Campagne / Date création/modif
- Onglets : Établissements / Contacts / Conventions / **Chantiers** / Commentaires / **Localisation** / Documents
- Multi-établissements par client (ex: Fédération Audoise des Œuvres Laïques + résidence jeunesse)
- Chaque établissement : SIREN/SIRET/Adresse/CP/Ville/**Zone (H1/H2/H3)**/Catégorie/Secteur

→ **Ce CRM 2021 est exactement le modèle de données que CEE Engine doit reproduire et augmenter.**

## Les 12 erreurs à NE PAS commettre (signature dossiers PNCEE)
**Critique opérationnel — règle de fer pour tout doc CEE final :**
1. Imprimer en **COULEUR** (PNCEE refuse N&B)
2. **PAS de recto-verso** — feuille simple toujours
3. Date **manuscrite** au stylo **encre BLEUE**
4. Année **complète** (2026, jamais 26)
5. "Bon pour accord" manuscrit encre bleue
6. Signature manuscrite encre bleue
7. **AUCUNE mention** ajoutée ("au nom de", "P/O", fonction)
8. **PAS de signature électronique** (formellement interdit pour CEE)
9. **Même écriture, même stylo** pour : date + bon pour accord + signature
10. Tampon **à côté** de la signature (pas dessus) — tous deux lisibles
11. Tampon **original**, complet, lisible (scannés refusés)
12. **Un seul tampon**, pas double, pas à l'envers

## Cibles historiques GET1TECH (parrainage)
- Associations (UNAPEI, ADAPEI, fédération CAPEB)
- Logement social
- Médical
- Tertiaire pré-1986 chauffé combustible
- Postes éligibles types : **BAT-TH-101, BAT-TH-103, BAT-TH-146**
- Réversion via "chèque environnement CEE/m²" + partenariat **Mon Compte CO2**

## How to apply (pour CEE Engine)
1. **Module conformité documents** : checklist 12 erreurs G1T → bloc auto au générateur PDF (rappel "Imprimer couleur, sign manuscrite encre bleue, pas P/O")
2. **Modèle données client** : reprendre champs CRM G1T (parcelle cadastrale, NAF, téléopérateur, multi-établissements avec zone climatique)
3. **Convention LSF/G1T** = template juridique réutilisable (4 pages, articles 1-8, annexe 1 filiales) — adapter en `convention_oxeo.html`
4. **Trame appel 4 min** : peut alimenter chatbot WhatsApp B2B (GIS-06) avec questions filtrantes G1T
5. **"Bonus réversion CEE/m²"** = mécanisme de fidélisation à intégrer dans simulateur ROI
6. **Cible PROPRIÉTAIRE PERSONNE MORALE uniquement** (cohérent avec règle Jimmy : pas particuliers)
