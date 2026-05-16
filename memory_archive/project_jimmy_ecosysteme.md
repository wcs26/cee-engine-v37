---
name: Écosystème complet Jimmy — au-delà du CEE
description: Cartographie réelle découverte par scan ordi (16/04/2026) — Jimmy n'est pas que CEE. Il pilote un écosystème JARVIS multi-projets avec équipe commerciale.
type: project
originSessionId: 2df11f34-7c9e-449e-84cf-ffec1837e5ed
---
## Activités métier de Jimmy (au-delà du CEE)

| Domaine | Indicateurs trouvés | Implication CEE Engine |
|---|---|---|
| **CEE pur** (cœur) | Cotations, audits énergétiques, AHBFC client réf | CEE Engine V37 = outil principal |
| **Photovoltaïque** | Cotations PV (Dupas, Delquie, Linlaud, etc.), Datasheet AESOLAR, Budget PV 2025 | Étendre à module PV (cotation + contrat maintenance) |
| **Bornes recharge IRVE** | Contrat Maintenance PV+PointBornes 3R Industries | Module IRVE possible |
| **Maintenance ENR** | Contrats de maintenance V2 ENR | Module SAV/maintenance |
| **Agriculture** | Serres (AGRI-TH-117 cité dans gisements), Cotations agri | Confirmer AGRI dans CEE Engine ✅ |
| **Vélos cargo électriques** | Contrats SAV vélos cargo, rapport projet 19/10/25 | Pas en scope CEE Engine |
| **Formation interne équipe** | 8+ modules formation (QCM, technique vente, montage dossier, optiwise, monday, getaccept, porte-à-porte) | Module formation IA dans CEE Engine = GIS-08 |

## Équipe commerciale

- **Nicolas, Anthony, Aurelien** : commerciaux (stats hebdo W01-W04, recap mensuel)
- Stats trackées : leads fournis/traités, signatures, CA
- Manager (Jimmy) suit Monday + reporting hebdo

## Stack outils existants

| Outil | Usage |
|---|---|
| **Monday.com** | CRM principal — leads, pipeline, équipe |
| **Likewatt / Optiwise** | Calcul PV (à concurrencer ou intégrer) |
| **GetAccept** | Signature électronique probable |
| **WCS Oracle** | Autre projet IA (ancêtre ou parallèle de CEE Engine) |
| **JARVIS** | Hub IA multi-projets (jarvis-hub, jarvis_gateway) |
| **WhatsApp Bot** | Communication client (whatsapp-jarvis, AI-Jarvis-WhatsApp-Bot) |

## Roadmap IA déjà cartographiée (gisements_priorites.csv)

12 gisements priorisés Tier 1/2/3 — extraits clés :

| ID | Gisement | Tier | ROI documenté |
|---|---|:-:|---|
| GIS-01 | Agent Qualification Leads Auto | 1 | +15% taux contact, gain 2h/jour |
| GIS-02 | Générateur Devis/Étude PV Auto | 1 | Gain 1h30/devis × 5/sem = 7.5h/sem |
| GIS-03 | **Assistant Closing R2 temps réel** | 1 | **+10% closing = +2 signatures/mois = 40K€ CA/an** |
| GIS-04 | Rapport Hebdo Monday→Claude→PDF | 1 | Gain 3h/sem manager |
| GIS-05 | Scoring CEE AHBFC + Serres | 1 | Déblocage 19 879 € PAC + serres AGRI-TH-117 |
| GIS-06 | Chatbot WhatsApp B2B | 2 | +20% leads qualifiés 24/7 |
| GIS-07 | Détecteur Anomalies Pipeline | 2 | Détection fraude/négligence |
| GIS-08 | Formation Vendeur IA Simulateur R1/R2 | 2 | +15% skill closing sans mobiliser manager |
| GIS-09 | Prospection CEE Auto (Serres+Industrie) | 2 | x10 volume prospection |
| GIS-10 | JARVIS CEO Dashboard | 3 | Décision CEO 30s vs 30min |
| GIS-11 | Multi-Agent JARVIS Orchestration | 3 | Auto 70% tâches répétitives, ~1.5 ETP |
| GIS-12 | API Courtage Énergie + IA | 3 | Nouveau service à valeur ajoutée |

## Méthode commerciale Jimmy

- **R1 / R2** : structure Rendez-vous 1 (découverte) → Rendez-vous 2 (closing)
- **Argumentaires** : SCRIPT ARGUMENTAIRE FICHIER CLIENT COURTAGE
- **Synthèse techniques de vente / management** : doc Desktop référence
- **Méthode** : porte-à-porte + courtage + closing R1/R2

## Audit forensique en cours

`AUDIT_RESULTS/` contient un audit forensique Monday — détection d'activités suspectes (enrichissement puis suppression, KO bursts). Suggère un soupçon de fraude / négligence dans l'équipe commerciale → besoin de **GIS-07 Détecteur Anomalies** activé.

## Implications stratégiques pour CEE Engine

1. **Connecter Monday CRM** (webhook bi-directionnel) → priorité car CRM principal Jimmy
2. **Module Assistant Closing R2 live** → ROI direct documenté 40K€/an
3. **Module Formation IA simulateur** → pour Anthony/Aurelien/Nicolas
4. **Module PV cotation** → étendre scope au-delà du CEE pur
5. **Module Détecteur Anomalies** → réponse au besoin AUDIT_RESULTS actuel
6. **Intégration GetAccept** plutôt que Yousign stub (Jimmy a déjà GetAccept)
7. **Simulateur R1/R2 dans drawer outils** → former l'équipe sans mobiliser Jimmy
