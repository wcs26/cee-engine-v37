/**
 * CEE Engine V37 PRO — Module exports/PDFs (self-contained)
 * Fonctions : générer mandat de cession, attestation sur l'honneur,
 *             backup JSON complet, import JSON merge.
 *
 * Dépend des globales suivantes (définies dans oracle.html) :
 *   STATE, CONFIG, CRM_STORAGE_KEY, CRM_MAX
 *   getFullCalc(), getClientsHistory(), renderClientsHistory()
 *   window.jspdf.jsPDF (librairie externe)
 *
 * Chargé via <script src="js/cee-pdfs.js"> APRÈS le script principal.
 */

function generateMandatCEE() {
    if (!window.jspdf || !window.jspdf.jsPDF) { alert('Librairie jsPDF non chargée'); return; }
    var doc = new window.jspdf.jsPDF();
    var d = STATE.diagnostic || {};
    var today = new Date().toLocaleDateString('fr-FR', {day:'2-digit',month:'long',year:'numeric'});
    var y = 20;
    doc.setFontSize(14); doc.setFont('helvetica','bold');
    doc.text('MANDAT DE CESSION DES CERTIFICATS D\'ÉCONOMIES D\'ÉNERGIE', 105, y, {align:'center'}); y += 10;
    doc.setFontSize(10); doc.setFont('helvetica','normal');
    doc.text('Dispositif CEE — Arrêté du 22 décembre 2014 modifié — Période P6 (2026-2030)', 105, y, {align:'center'}); y += 12;

    doc.setFont('helvetica','bold'); doc.text('LE MANDANT (bénéficiaire de la prime) :', 14, y); y += 6;
    doc.setFont('helvetica','normal');
    doc.text('Raison sociale : ' + (d.raisonSociale || '_______________________________'), 14, y); y += 6;
    doc.text('SIRET : ' + (d.siret || '_______________________________'), 14, y); y += 6;
    doc.text('Adresse : ' + (d.adresse || '___________________'), 14, y); y += 6;
    doc.text('Code postal / Ville : ' + (d.cp || '_____') + ' ' + (d.ville || '___________________'), 14, y); y += 6;
    doc.text('Représenté par : __________________________  Qualité : __________________________', 14, y); y += 10;

    doc.setFont('helvetica','bold'); doc.text('LE MANDATAIRE :', 14, y); y += 6;
    doc.setFont('helvetica','normal');
    doc.text('Raison sociale : __________________________________________________________', 14, y); y += 6;
    doc.text('SIRET : _____________________  Représenté par : __________________________', 14, y); y += 10;

    doc.setFont('helvetica','bold'); doc.text('OBJET DU MANDAT', 14, y); y += 6;
    doc.setFont('helvetica','normal');
    var objet = 'Le Mandant confie au Mandataire le soin de valoriser pour son compte les Certificats d\'Économies d\'Énergie (CEE) générés par les opérations de rénovation énergétique décrites en annexe, dans le cadre du dispositif CEE (L. 221-1 et suivants du code de l\'énergie).';
    var split = doc.splitTextToSize(objet, 180); doc.text(split, 14, y); y += split.length * 5 + 4;

    doc.setFont('helvetica','bold'); doc.text('OPÉRATIONS CONCERNÉES', 14, y); y += 6;
    doc.setFont('helvetica','normal');
    var ops = (STATE.selectedFiches && STATE.selectedFiches.size) ? Array.from(STATE.selectedFiches.keys()) : [];
    if (ops.length) {
      ops.slice(0,12).forEach(function(ref) { doc.text('• ' + ref, 18, y); y += 5; });
      if (ops.length > 12) { doc.text('… et ' + (ops.length-12) + ' autres opérations (voir rapport de diagnostic).', 18, y); y += 6; }
    } else {
      doc.text('Voir annexe : rapport de diagnostic CEE Engine.', 18, y); y += 6;
    }
    y += 4;

    doc.setFont('helvetica','bold'); doc.text('PRIME CEE ESTIMÉE', 14, y); y += 6;
    doc.setFont('helvetica','normal');
    var gc = (typeof getFullCalc === 'function') ? getFullCalc() : {};
    if (gc.totalPrimeBrute) {
      doc.text('Volume CEE estimé : ' + Math.round((gc.totalKwhc||0)/1000).toLocaleString('fr-FR') + ' MWhc', 14, y); y += 6;
      doc.text('Prime brute estimée : ' + Math.round(gc.totalPrimeBrute).toLocaleString('fr-FR') + ' € (prix de rachat ' + (CONFIG.PRIX_MWH) + ' €/MWh)', 14, y); y += 6;
    } else {
      doc.text('Montant estimatif : voir rapport de diagnostic.', 14, y); y += 6;
    }
    y += 4;

    doc.setFont('helvetica','bold'); doc.text('DURÉE ET SIGNATURES', 14, y); y += 6;
    doc.setFont('helvetica','normal');
    doc.text('Le présent mandat prend effet à la date de signature et expire à la clôture définitive', 14, y); y += 5;
    doc.text('du/des dossier(s) CEE, y compris les contrôles post-versement.', 14, y); y += 10;
    doc.text('Fait à _______________, le ' + today, 14, y); y += 12;
    doc.text('Le Mandant (signature + cachet)                    Le Mandataire (signature + cachet)', 14, y); y += 24;
    doc.setFontSize(8); doc.setTextColor(120);
    doc.text('Document généré par CEE Engine V37 — Horodatage : ' + new Date().toISOString(), 105, 287, {align:'center'});

    doc.save('Mandat_CEE_' + (d.siret||'entreprise') + '_' + new Date().toISOString().split('T')[0] + '.pdf');
  }

function generateAttestationHonneur() {
    if (!window.jspdf || !window.jspdf.jsPDF) { alert('Librairie jsPDF non chargée'); return; }
    var doc = new window.jspdf.jsPDF();
    var d = STATE.diagnostic || {};
    var today = new Date().toLocaleDateString('fr-FR', {day:'2-digit',month:'long',year:'numeric'});
    var y = 20;
    doc.setFontSize(14); doc.setFont('helvetica','bold');
    doc.text('ATTESTATION SUR L\'HONNEUR', 105, y, {align:'center'}); y += 7;
    doc.setFontSize(11);
    doc.text('(Dispositif des Certificats d\'Économies d\'Énergie)', 105, y, {align:'center'}); y += 14;
    doc.setFontSize(10); doc.setFont('helvetica','normal');
    doc.text('Je soussigné(e) _________________________________________________________,', 14, y); y += 7;
    doc.text('agissant en qualité de ________________________________________________,', 14, y); y += 7;
    doc.text('représentant légal de :', 14, y); y += 7;
    doc.setFont('helvetica','bold');
    doc.text((d.raisonSociale || '________________________________'), 14, y); y += 6;
    doc.setFont('helvetica','normal');
    doc.text('SIRET : ' + (d.siret || '____________________'), 14, y); y += 6;
    doc.text('Adresse : ' + (d.adresse || '_______________________________') + ' ' + (d.cp || '_____') + ' ' + (d.ville || '__________'), 14, y); y += 10;
    doc.setFont('helvetica','bold'); doc.text('Atteste sur l\'honneur :', 14, y); y += 8;
    doc.setFont('helvetica','normal');
    var para1 = '1. Que les opérations de rénovation énergétique décrites dans le dossier CEE ont été réalisées par des entreprises titulaires d\'un signe de qualité RGE en cours de validité à la date de signature du devis, conformément à l\'article 2 de l\'arrêté du 22 décembre 2014.';
    var para2 = '2. Que les équipements et matériaux installés respectent les caractéristiques techniques minimales requises par la (les) fiche(s) d\'opération(s) standardisée(s) applicable(s).';
    var para3 = '3. Ne pas avoir sollicité, ou s\'engager à ne pas solliciter, le bénéfice des Certificats d\'Économies d\'Énergie pour ces mêmes opérations auprès d\'un autre demandeur que celui désigné dans le mandat de cession.';
    var para4 = '4. Avoir pris connaissance que les opérations sont susceptibles d\'être contrôlées par un organisme d\'inspection accrédité COFRAC, et m\'engager à faciliter ces contrôles.';
    var para5 = '5. Que toute fausse déclaration m\'expose aux sanctions prévues par l\'article 441-7 du Code pénal et par l\'article L. 222-10 du code de l\'énergie (annulation des CEE, remboursement, sanctions administratives).';
    [para1,para2,para3,para4,para5].forEach(function(p) { var s=doc.splitTextToSize(p,180); doc.text(s,14,y); y += s.length*5 + 4; });
    y += 6;
    doc.text('Fait à _______________, le ' + today, 14, y); y += 14;
    doc.text('Signature du représentant légal + cachet :', 14, y);
    doc.setFontSize(8); doc.setTextColor(120);
    doc.text('Document généré par CEE Engine V37 — Horodatage : ' + new Date().toISOString(), 105, 287, {align:'center'});
    doc.save('Attestation_Honneur_CEE_' + (d.siret||'entreprise') + '_' + new Date().toISOString().split('T')[0] + '.pdf');
  }

function exportAllCEEJSON() {
    var payload = {
      _meta: {
        version: 'V37-FUSED',
        exported_at: new Date().toISOString(),
        user_agent: navigator.userAgent.substring(0, 100),
      },
      clients: getClientsHistory(),
      suivi_dossiers: {},
      preferences: {
        prix_mwh: CONFIG.PRIX_MWH,
        commission_rate: CONFIG.COMMISSION_RATE,
      },
    };
    // Récupérer tous les suivis dossiers (une entrée par SIRET)
    for (var i = 0; i < localStorage.length; i++) {
      var key = localStorage.key(i);
      if (key && key.indexOf('cee_suivi_') === 0) {
        try { payload.suivi_dossiers[key.substring(10)] = JSON.parse(localStorage.getItem(key)); } catch(_) {}
      }
    }
    var blob = new Blob([JSON.stringify(payload, null, 2)], {type:'application/json;charset=utf-8'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'CEE_Engine_Backup_' + new Date().toISOString().split('T')[0] + '.json';
    a.click();
    URL.revokeObjectURL(url);
  }

function importAllCEEJSON() {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json,.json';
    input.onchange = function(e) {
      var file = e.target.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function(ev) {
        try {
          var data = JSON.parse(ev.target.result);
          if (!data._meta) throw new Error('Fichier non reconnu (pas de _meta)');

          var nImported = 0, nMerged = 0;
          // Merger clients — dédup par SIRET, garde le plus récent
          if (data.clients && Array.isArray(data.clients)) {
            var existing = getClientsHistory();
            var bySiret = {};
            existing.forEach(function(c) { bySiret[c.siret] = c; });
            data.clients.forEach(function(c) {
              if (!c.siret) return;
              if (!bySiret[c.siret]) { bySiret[c.siret] = c; nImported++; }
              else {
                var oldDate = new Date(bySiret[c.siret].date || 0);
                var newDate = new Date(c.date || 0);
                if (newDate > oldDate) { bySiret[c.siret] = c; nMerged++; }
              }
            });
            var merged = Object.values(bySiret).sort(function(a,b) {
              return new Date(b.date||0) - new Date(a.date||0);
            }).slice(0, CRM_MAX);
            localStorage.setItem(CRM_STORAGE_KEY, JSON.stringify(merged));
          }
          // Merger suivi dossiers
          var nSuivi = 0;
          if (data.suivi_dossiers) {
            Object.keys(data.suivi_dossiers).forEach(function(siret) {
              var key = 'cee_suivi_' + siret;
              if (!localStorage.getItem(key)) {
                localStorage.setItem(key, JSON.stringify(data.suivi_dossiers[siret]));
                nSuivi++;
              }
            });
          }
          renderClientsHistory();
          alert('✅ Import réussi :\n- ' + nImported + ' nouveau(x) client(s)\n- ' + nMerged + ' client(s) mis à jour\n- ' + nSuivi + ' suivi(s) dossier ajouté(s)');
        } catch (err) {
          alert('❌ Erreur import : ' + err.message);
        }
      };
      reader.readAsText(file);
    };
    input.click();
  }
