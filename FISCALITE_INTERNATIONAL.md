# Fiscalité internationale CEE Engine

> ⚠️ **Avertissement** : ce document expose des principes généraux de fiscalité
> internationale entre Bulgarie, Cambodge et pays clients (France, Italie,
> Espagne, Pologne, UK...). **Ne remplace PAS un avis juridique**.
> **Consultation obligatoire** d'un fiscaliste international (~300-500 €/h)
> avant toute action engageante.

## 🌍 Montage actuel Jimmy (à valider par fiscaliste)

| Acteur | Statut | Fiscalité |
|---|---|---|
| **Jimmy WILNER** (personne physique) | Résident fiscal **Cambodge** | Territorialité — Cambodge taxe uniquement les revenus de source cambodgienne. Dividendes WCS Bulgaria = revenus étrangers = **non taxés au Cambodge** (en principe) |
| **WCS Bulgaria EOOD** | Société droit bulgare | IS bulgare **10 %** flat sur bénéfices mondiaux |
| **Activité** | SaaS abonnement vendu B2B dans pays UE/UK avec dispositifs CEE | Pas d'activité physique localisée hors Bulgarie |
| **Hébergement** | Fly.io région UE (Paris-cdg) | Neutre fiscalement |

## 🇰🇭 Résidence fiscale Cambodge — points à vérifier

### Conditions à remplir
- Présence physique > **183 jours/an** au Cambodge (calendaire) **OU**
- Domicile principal au Cambodge (logement permanent disponible)
- Centre des intérêts économiques au Cambodge (banques, contrats, etc.)

### Vérifier ces preuves
- [ ] Bail / titre propriété logement Phnom Penh / Siem Reap / autre
- [ ] Relevés bancaires cambodgiens montrant activité régulière
- [ ] Visa long séjour (E-visa, retraite, business...) avec dates
- [ ] Tampons passeport prouvant > 183 j/an
- [ ] Adresse cambodgienne sur tous documents administratifs

### Pourquoi c'est critique
Si l'admin française te trouve résident fiscal France (séjours fréquents,
bien immobilier France, famille France...) elle peut **t'imposer sur tes
dividendes mondiaux**. La résidence fiscale n'est pas un choix déclaratif :
elle se prouve par les faits (présence, biens, intérêts).

## 🇧🇬 Société bulgare — risques de requalification

### Risque "société sans substance"
La Bulgarie applique le critère du **siège statutaire** (pas de la direction
effective) pour la résidence société. **Mais** :
- Si la société n'a **aucune activité réelle** en Bulgarie (pas de bureau,
  comptable, dépenses locales) → admin bulgare peut requalifier en
  "boîte aux lettres" → perte avantages fiscaux, voire dissolution forcée.
- Si tu télé-travailles depuis le Cambodge → admin bulgare peut estimer
  que la société "n'est pas vraiment là".

### Substance minimum recommandée
- [ ] Comptable bulgare local (~80-150 €/mois) — obligatoire
- [ ] Adresse réelle Sofia (au moins virtuelle avec courrier reçu) — déjà fait
- [ ] Compte bancaire bulgare actif (Postbank, UniCredit Bulbank, ProCredit)
- [ ] Au moins quelques dépenses bulgares par an (honoraires comptable,
      adresse, frais bancaires) — démontre activité réelle
- [ ] Assemblée générale annuelle documentée (procès-verbal en bulgare)

## 💰 Flux Bulgarie → Cambodge (dividendes Jimmy)

### Étape 1 : IS bulgare
- WCS Bulgaria EOOD réalise X € de bénéfice annuel
- IS bulgare 10 % → reste 0,9 X € distribuables

### Étape 2 : retenue à la source bulgare sur dividendes
- Bulgarie applique 5 % de retenue sur dividendes versés à non-résidents
  (sauf convention plus favorable)
- ⚠️ **Pas de convention fiscale Bulgarie-Cambodge** (à confirmer côté MFE)
  → retenue à la source bulgare 5 % s'applique en plein
- Jimmy reçoit 0,855 X € sur compte personnel

### Étape 3 : imposition Cambodge sur dividendes étrangers
- Cambodge système territorial → en principe **0 % sur dividendes étrangers**
- Vérifier : est-ce que Cambodge taxe les "rapatriements" ?
  → en pratique non, mais déclarer prudemment selon réglementation locale

### Total imposition combinée
≈ **14 %** (10 % IS + 5 % retenue dividendes) vs ≈ 50 % si même schéma société
française + résidence France.

## 🇫🇷 Vente SaaS aux clients français (B2B)

Tant que Jimmy n'a **aucune présence physique en France** (pas de bureau,
pas de personnel, pas de représentant habilité) :

### Pas d'établissement stable en France
- Article 5 OCDE : pas d'installation fixe d'affaires = pas d'ES
- Visites ponctuelles client (RDV commerciaux) = OK si ≤ quelques jours/an
- Pas d'IS français à payer

### TVA B2B France (auto-liquidation)
Mention obligatoire sur chaque facture :
> *« Reverse charge — VAT to be paid by the recipient (Article 44 of EU
> Directive 2006/112/EC) »*

→ WCS Bulgaria collecte **0 € de TVA française**. Le client français auto-liquide.

### B2C France ou autres particuliers
Si vente directe à des particuliers/TPE non assujetties UE > 10 000 €/an :
- Inscription **OSS bulgare** (One-Stop-Shop)
- Collecte TVA française 20 % et reversement trimestriel via portail BG → admin française
- Pas d'inscription TVA française nécessaire

## 🇮🇹 🇪🇸 🇵🇱 🇬🇧 — Multi-pays CEE (roadmap produit)

Pays avec dispositif équivalent aux CEE français :

| Pays | Dispositif | Statut produit | Effort intégration |
|---|---|---|---|
| 🇫🇷 France | CEE (depuis 2005) | ✅ 234 fiches catalogue | déjà fait |
| 🇮🇹 Italie | Certificati Bianchi (TEE) | ❌ Non intégré | ~2 semaines (catalogue + règles) |
| 🇪🇸 Espagne | CAE (depuis 2024) | ❌ Non intégré | ~2 semaines (système naissant) |
| 🇵🇱 Pologne | Białe Certyfikaty | ❌ Non intégré | ~2 semaines |
| 🇬🇧 UK (hors UE) | ECO + Boiler Upgrade Scheme | ❌ Non intégré | ~3 semaines (post-Brexit) |
| 🇩🇰 Danemark | Energiselskabernes spareforpligtelser | ❌ Non intégré | ~1 semaine |
| 🇧🇪 Belgique | Certificats Verts régionaux Wallonie/Flandre/Bruxelles | ❌ Non intégré | ~2 semaines (3 régions) |

### Implications fiscales multi-pays
- B2B chaque pays UE : auto-liquidation TVA art. 44 directive 2006/112/CE → OK
- B2C / OSS : déclaration unique par OSS bulgare pour TOUS les pays UE
- 🇬🇧 UK post-Brexit : régime spécifique — pas dans OSS UE, registration HMRC
  obligatoire si > seuil (à vérifier)

## ⚖️ Mentions légales et juridiction

Sur ton site web (`/legal/mentions`, `/legal/cgu`) :

### À garder
- ✅ Éditeur : **WCS Bulgaria EOOD** (Sofia 1540, EIK 207143227, gérant Jimmy WILNER)
- ✅ Hébergement Fly.io région cdg (Paris)
- ✅ Droit applicable : **droit bulgare**
- ✅ Juridiction : **tribunaux Sofia** (avec exception consommateur du domicile)

### À enlever ou modifier
- ❌ Toute mention "service en France" / "société française" / adresse France
- ❌ Mention "directeur de publication M. Jimmy WILNER" sans préciser Sofia
- ❌ Téléphone français +33 en mention principale → mettre en secondaire ou retirer

## 🚨 Signaux d'alerte à éviter absolument

1. **Bancarisation des revenus société sur compte personnel France** = preuve
   de résidence économique France → IR France garanti
2. **Bureau loué en France au nom de WCS Bulgaria** = établissement stable
3. **Adresse France sur signature email professionnelle** = indice fort
4. **Numéro SIRET français créé** (URSSAF, Centre de Formalités, etc.) = ES de plein droit
5. **Aucune trace Cambodge** sur documents (pas de visa, pas de bail, pas de
   compte bancaire local) → contestation résidence Cambodge facile
6. **Dépenses personnelles France sur carte société** = transfert imposable

## 📋 Checklist actions à faire (post-fiscaliste)

- [ ] Consulter fiscaliste international **Bulgarie-Cambodge-France** (~500 €
      pour 1 h, cabinet type Bird & Bird, KPMG International, ou expert Sofia)
- [ ] Documenter ta présence Cambodge (visa, bail, banque, dates) dans un dossier
- [ ] Activer numéro TVA intracommunautaire bulgare (BG suivi de 9-10 chiffres)
- [ ] Sécuriser substance Bulgarie (comptable local + au moins 1 AG/an documentée)
- [ ] Mettre à jour mentions légales site web (déjà fait dans `/legal/mentions`)
- [ ] Déposer marque EUIPO 850-1050 € au nom WCS Bulgaria EOOD avec adresse Sofia
- [ ] **NE PAS** créer SIRET français, **NE PAS** louer bureau France,
      **NE PAS** déclarer d'établissement secondaire France

## 🔄 Cas particulier : services rendus par Jimmy en personne

Si Jimmy se déplace ponctuellement en France pour faire un audit ou pitcher
un client gros compte (Carrefour, AHBFC, Engie...), c'est OK tant que :
- Durée totale en France < ~90 jours/an cumulé
- Aucune installation permanente (chaque déplacement est une mission)
- Facturation depuis WCS Bulgaria EOOD avec auto-liquidation TVA
- Documenter chaque déplacement avec billets d'avion + factures hôtels

Au-delà ou en cas de récurrence forte → risque ES "agent dépendant" → consulter
fiscaliste impérativement.

---

*Document V37.3.28 · Maintenu pour transparence · Ne remplace pas l'avis d'un
fiscaliste agréé international.*
