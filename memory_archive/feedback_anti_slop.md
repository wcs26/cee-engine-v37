---
name: anti_slop
description: Filtre copywriter anti-AI-slop pour CEE Engine. Liste des adverbes/fillers/bombast à refuser + 5 exemples canon avant/après. À appliquer sur toute string visible utilisateur.
type: feedback
originSessionId: 77f696d7-e327-4ff8-9534-f54fec80bc4b
---
## Filtre à appliquer sur toute string user-facing

### Adverbes inutiles à supprimer (souvent)
véritablement · naturellement · facilement · simplement · évidemment · clairement · fondamentalement · essentiellement · particulièrement · généralement · principalement · notamment · automatiquement (sauf info technique réelle) · instantanément · rapidement · efficacement · totalement · entièrement · parfaitement · pleinement · directement · concrètement · effectivement · finalement · justement · précisément (sauf si vraiment de précision) · réellement · vraiment

### Fillers / throat clearing
Voici · Il s'agit de · Comme tu le sais · Comme on le voit · En somme · En bref (sauf vrai résumé) · En fin de compte · In fine · Tout d'abord · Pour commencer · En premier lieu · Dans un premier temps · Il convient de · Il est important de · Il faut noter que · Notez que · Sachez que · Par ailleurs · En outre

### Hedging mou
probablement · sans doute · il semble que · on peut dire que · on peut considérer que · une certaine · un certain · plutôt (sauf opposition) · assez · relativement · approximativement (sauf chiffre)

### Bombast / publicité
incroyable · fantastique · exceptionnel · fameux · célèbre · magique · révolutionnaire · ultime · puissant · transformateur · disruptif · innovant (sauf RGPD/loi) · optimal (sans chiffre) · idéal · parfait · maximum (sans chiffre)

### Verbes mous à remplacer
permettre de → directement le verbe d'action ("permet de calculer" → "calcule")
nous permet → coupe ("X nous permet de Y" → "X fait Y")
constituer → être
représenter → être
effectuer → faire / exécuter
réaliser → faire / livrer
mettre en place → installer / déployer
mettre en œuvre → appliquer / exécuter

## 5 exemples canon (ancrés CEE Engine)

### 1. Hero / promesse
❌ "Cette **incroyable** plateforme va **véritablement** transformer **complètement** ton workflow CEE"
✅ "Audit CEE en 30s depuis ton SIRET. 224 fiches scannées, sources visibles."

### 2. Description de fonctionnalité
❌ "**Naturellement**, l'Engine **vous permet de** détecter **automatiquement** **plusieurs** sources **par la suite**"
✅ "Détecte 7 sources : INSEE, IGN BD TOPO, DPE Géoportail, cadastre, ATEE, ADEME, OpenData."

### 3. Headline résultat
❌ "Vous avez **probablement** une prime **assez** élevée — **il s'agit de** ~8K€ **environ**"
✅ "Prime estimée : 8 200 € · source : moteur local + IGN BD TOPO 280 m²"

### 4. Référence dossier
❌ "**Voici** le **fameux** dossier AHBFC, **comme tu le sais**, **il s'agit du** trio SIRAt+H2D+WCS, qui est **véritablement** stratégique"
✅ "Dossier AHBFC : trio SIRAt+H2D+WCS, financeur Abokine 749843090, BAT-EN-103, 2 devis 0€ (Magritte 79K€ + Renoir 95K€)."

### 5. CTA / bouton
❌ "Cliquez **simplement** **ici** pour **éventuellement** **continuer**"
✅ "Continuer → voir mes 8 gisements"

## Règle additionnelle : verbe d'action en tête de string courte
Pour les boutons / labels / toasts :
- ❌ "L'option de sauvegarde est disponible" → ✅ "Sauvegarder"
- ❌ "Vous pouvez maintenant exporter" → ✅ "Exporter en PDF"
- ❌ "Une opportunité a été détectée" → ✅ "Gisement détecté : BAT-EN-103 ~3K€"

## Test rapide avant publication d'une string
1. Si je supprime cet adverbe, la phrase perd-elle de l'info ? Non → supprimer.
2. Si je remplace ce verbe mou par un verbe d'action, la phrase est-elle plus directe ? Oui → remplacer.
3. La phrase contient-elle un chiffre vérifiable ? Si non et possible → ajouter.
4. La phrase est-elle ≤ 18 mots ? Si non, couper.
5. Le verbe est-il en début de phrase ? Si CTA/bouton → oui obligatoire.
