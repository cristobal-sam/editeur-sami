# Passation pour Claude — Direction créative V2

Date : 30 septembre 2026  
Projet : `D:\Tools\editeur_sami`

## 1. Objectif de Sami

Sami veut conserver son éditeur vidéo automatique actuel et l'amener progressivement vers un niveau professionnel
de premier plan. Il ne veut **pas recommencer le projet**. Il veut que l'outil comprenne toute la vidéo avant de la
monter, construise une véritable direction créative, puis utilise intelligemment Remotion, Blender, les images
générées, la musique et les autres moteurs locaux.

L'objectif réaliste convenu est :

- résultat premium et cohérent sur la grande majorité des formats courts compatibles ;
- aucun objet, effet ou visuel générique sans rapport avec le contenu ;
- montage conçu comme une histoire complète, pas comme une accumulation d'effets ;
- contrôle qualité automatique avant livraison ;
- ancien moteur toujours disponible comme solution de repli.

## 2. Règles absolues

- Ne jamais lire ni afficher `cles-api.env`.
- Ne jamais démarrer une deuxième copie du serveur réel sur le port 8790.
- Ne pas modifier `D:\Y0U`. Les outils nécessaires doivent vivre dans le projet.
- Préserver les rushs originaux. Toute modification importante doit avoir une copie de sécurité récupérable.
- Ne pas lancer d'export complet sans demande explicite de Sami. Les aperçus courts de vérification sont permis.
- Ne jamais inventer de produit, de statistique, de résultat ou de preuve non présent dans les sources.
- Une image générée doit être signalée comme illustration conceptuelle et ne doit pas remplacer une vraie photo de
  produit lorsque l'identité exacte du produit compte.
- Blender ne doit être utilisé que lorsqu'une vraie ressource ou un storyboard le justifie.

## 3. Fondation existante à conserver

Le projet possède déjà :

- dérushage, transcription et sélection des prises ;
- montage Remotion, styles, sous-titres, graphismes, détourage et exports multiformats ;
- musique, bruitages et traitement de la voix ;
- Blender autonome dans `tools/blender` ;
- plugin local `plugins/editeur-sami` avec 31 commandes ;
- relecture de sobriété qui limite les chevauchements et protège l'accroche ;
- style `produit-3d`, renommé **Tech 3D cinématique** ;
- Vidéo 1 montée avec la vraie personne détourée dans un studio sombre et des interfaces liées aux paroles.

Le faux objet Blender sans rapport a été supprimé. Le moteur Blender refuse maintenant de fabriquer un produit sans
photo réelle ou modèle GLB.

## 4. Nouveau travail déjà réalisé

Le module `engine/editeur/creative.py` ajoute le **cerveau créatif V2** sans remplacer le moteur existant.

Il lit le montage entier avant les effets et produit :

- un arc narratif ;
- les rôles des passages : accroche, tension, révélation, preuve, explication, appel à l'action ;
- le rythme global ;
- la grammaire visuelle ;
- des intentions visuelles motivées ;
- un arc sonore ;
- des garde-fous et un score de confiance.

Intégrations :

- `auto.py` applique le plan avant l'habillage automatique ;
- `reel.py` le recalcule lors d'un changement de style ;
- `galerie.py` rattache chaque scène à un temps narratif et à une raison ;
- `types.ts` décrit le document ;
- `ajouter.tsx` affiche la carte **Direction créative V2** et ses moments cliquables.

Vidéo 1 possède actuellement 7 temps narratifs et ses 6 scènes sont reliées à des raisons créatives. Le plan est
visible dans **Modifier → Ajouter → Direction créative V2**.

Compte rendu et sauvegardes : `docs/cerveau-creatif-v2-2026-09-30/`.

## 5. Vérifications déjà réussies

- test dédié cerveau créatif : OK ;
- moteur Python : 8/8 ;
- galerie : 6/6 ;
- calcul temporel : 6/6 ;
- construction de l'interface : OK ;
- TypeScript : 0 erreur ;
- contrôle visuel dans le vrai navigateur : carte V2 et 7 moments visibles ;
- serveur réel au repos, file vide ;
- aucun export complet lancé.

## 6. Storyboard V2 maintenant intégré

Le **storyboard V2 exécutable** est maintenant intégré. Pour chaque temps narratif, il décide :

1. ce que le spectateur doit comprendre ou ressentir ;
2. quel type de plan sert cette intention ;
3. quelle composition employer ;
4. quel moteur exécute la scène ;
5. quels éléments sont nécessaires ;
6. pourquoi cette décision est liée aux mots réellement prononcés ;
7. quel plan de secours utiliser si la ressource manque.

Moteurs possibles, par ordre de sobriété :

- prise originale / recadrage / coupe ;
- typographie et interface Remotion ;
- plan de coupe réel disponible ;
- illustration conceptuelle générée ;
- Blender, uniquement si la 3D apporte une information ou un impact impossible autrement.

Le storyboard est stocké dans le reel et lisible dans **Modifier → Ajouter → Direction créative → Storyboard prévu**.
Il audite également l'exécution : plan prêt, ressource optionnelle ou ressource réellement manquante. Il ne déclenche
pas automatiquement un outil lourd au simple changement de style.

Sur Vidéo 1, les 7 plans sont prêts : prise originale pour l'accroche et la crédibilité humaine, interfaces Remotion
pour les mécanismes, graphisme pour la preuve « ×5 moins cher », CTA unique. Blender n'est pas sélectionné, car aucun
produit réel ne le justifie. Le seul plan de coupe externe est optionnel.

Un aperçu local de 5 secondes a révélé que le style cinématique masquait d'abord le graphisme de preuve. Le rendu a
été corrigé : une preuve explicitement décidée par le storyboard peut désormais traverser `suppressExtras`, sans
réactiver tous les graphismes génériques. La planche vérifiée et la vidéo sont dans
`docs/cerveau-creatif-v2-2026-09-30/resultat/`.

## 7. Ordre prévu après le storyboard

1. Direction sonore structurée : progression musicale, respirations, ponctuations motivées et mixage.
2. Contrôleur qualité automatique : lisibilité, visage, répétition, cohérence, chevauchement, audio et défauts visuels.
3. Génération ou sélection de ressources uniquement lorsqu'un futur storyboard marque une ressource obligatoire.
4. Exécution Blender seulement si un futur montage fournit une vraie photo ou un GLB.
5. Généralisation à plusieurs vidéos et plusieurs styles après validation du résultat étalon.

## 8. Nouvelles fonctions produit demandées par Sami

Ces fonctions font maintenant partie de la destination du projet. Ici, « comme dans Frame » est interprété comme une
expérience de révision visuelle de type **Frame.io** : commentaires rattachés à un instant précis et annotations
dessinées directement sur l'image. Confirmer cette interprétation avec Sami si une autre application appelée Frame
était visée.

> **État (30 septembre 2026, soir) : tout le §8 est implémenté et testé** (5 agents + intégration du lead). Résumé et
> liste de clics : `docs/direction-creative-v2/RESULTAT.md` ; contrat : `docs/direction-creative-v2/SPEC.md` ; tests :
> `node docs/direction-creative-v2/tests/test-v2.mjs`. **À faire avant usage réel : relancer une fois le vrai serveur
> 8790** (l'ancien serveur ignore les nouveaux champs et n'a pas les nouvelles routes).

### Notes et révision visuelle

- Ajouter des notes et commentaires rattachés à un timecode précis.
- Cliquer une note pour revenir exactement à l'image concernée.
- Pouvoir marquer une note comme ouverte, traitée ou résolue.
- Conserver l'auteur, la date, le texte et le contexte du montage au moment de la note.
- Éviter qu'une modification ultérieure du montage fasse silencieusement pointer la note vers le mauvais passage.

État : **fait** — onglet *Notes* (`app/ui/revue.tsx`). Note ancrée dans la prise (suit coupes, déplacements, vitesses) ;
passage coupé → « Passage retiré ou modifié » + « Rattacher ici ». Contexte : titre, style, format, durée, phrase dite.

### Annotation au crayon

- Pouvoir dessiner directement sur l'image de la vidéo : crayon, flèche, cercle et surligneur.
- Les traits sont liés au timecode ou à une courte plage, jamais incrustés définitivement dans les rushs.
- Permettre couleur, épaisseur, annulation, suppression et masquage des annotations.
- Utiliser ces annotations comme instructions de révision ; elles ne doivent apparaître dans l'export final que si
  l'utilisateur choisit explicitement d'en faire un élément graphique.

État : **fait** — calque ✏️ sur le lecteur (crayon, flèche, cercle, surligneur, gomme) ; points dans le repère de la prise
(alignés dans les 4 formats) ; jamais exportés (vérifié au pixel) ; « ⇢ Graphisme » convertit flèche / cercle / surligneur
en vecteur exporté. Limite : piste principale seulement, crayon à main levée non convertible.

### Banque d'effets, sons, vecteurs et templates

- Créer une banque locale consultable de transitions, swooshes/whooshes, impacts, bruitages, formes et vecteurs.
- Ajouter une banque de templates d'effets réutilisables : entrées, sorties, révélations, listes, comparaisons,
  notifications, CTA, cartes, titres et transitions.
- Chaque ressource doit avoir une miniature ou un aperçu, des mots-clés, une catégorie, une intensité et des formats
  compatibles.
- Les vecteurs doivent rester éditables : couleur principale, couleurs secondaires, contour, opacité, taille et
  animation. Ne pas convertir trop tôt les SVG en images figées.
- La charte du client et la palette du style doivent pouvoir recolorer automatiquement les vecteurs, avec retouche
  manuelle possible.
- Les licences et la provenance des ressources doivent être conservées.

État : **fait** — *Plus → Banque* (`engine/editeur/banque.py`, `app/ui/banque.tsx`) : 556 ressources locales (sons de
l'éditeur, 12 sons créés ici, 467 Kenney CC0, 18 modèles, 12 effets, 36 vecteurs SVG écrits à la main), chacune avec
licence, provenance, aperçu, mots-clés, catégorie, intensité, formats. Vecteurs recolorables (charte → style → couleur
choisie), modèles aussi (`props.color`). Limites : pas de musique ni de polices dans la banque ; effets = toute la vidéo.

### Chorégraphie gérée par l'IA, mais modifiable

« Chorégraphie » signifie ici la coordination temporelle de tous les éléments : mouvements, textes, vecteurs,
transitions, musique, bruitages, pauses et changements de plans.

- Le cerveau créatif doit proposer une chorégraphie complète à partir du storyboard.
- Chaque mouvement doit avoir une raison narrative et une relation avec la musique ou la parole.
- L'IA choisit les entrées, sorties, ordre, durée, direction, courbe d'animation et synchronisation.
- L'utilisateur doit pouvoir modifier chaque décision : déplacer, raccourcir, remplacer, recolorer, ralentir,
  désactiver ou verrouiller.
- Une modification manuelle ne doit pas être écrasée par une nouvelle passe automatique.
- Ajouter un mode « Refaire seulement ce passage » afin d'éviter de reconstruire toute la vidéo.
- La relecture de sobriété doit continuer à empêcher les accumulations et mouvements gratuits.

État : **fait** — *Plus → Chorégraphie* + piste *Chorégraphie* (`engine/editeur/choregraphie.py`, `remotion/src/choreo.tsx`) :
entrée, sortie, direction, durée, courbe, synchro sur les mots et les temps de la musique, une raison par mouvement ;
jamais deux entrées au même moment, rien sur l'accroche sauf le bandeau ; créée aussi à la fin du montage automatique.
Verrous partout (🔒, retouche = protégée) ; « Refaire seulement ce passage » dans la barre de la timeline (touches I / O),
rien ne change hors de la plage. Limites : la chorégraphie ne crée ni ne déplace d'élément (elle règle leur manière
d'entrer et sortir) ; emojis, bruitages et zooms hors chorégraphie ; Ctrl+Z n'annule pas un passage (« Annuler ce passage »).

### Ordre d'intégration recommandé

1. Modèle de données des notes, dessins et éléments verrouillés.
2. Interface de notes et crayon sur le lecteur, avec timecodes.
3. Catalogue local unifié pour effets, sons, SVG et templates.
4. Recoloration des SVG selon la charte et retouche manuelle.
5. Piste de chorégraphie produite par le cerveau créatif.
6. Éditeur manuel de cette piste et commande « Refaire seulement ce passage ».
7. Tests de persistance, changement de format, changement de style, annulation et export.

État : les 7 étapes sont faites (30 septembre 2026).

## 9. Tests obligatoires pour ces nouvelles fonctions

- Une note revient à la bonne image après fermeture et réouverture de l'outil.
- Une annotation au crayon reste alignée dans les formats 9:16, 16:9, 4:5 et 1:1.
- Notes et dessins de révision sont absents d'un export normal.
- Un SVG multicolore peut être recoloré sans perdre ses formes ni son animation.
- Une charte client recolore automatiquement un template, puis une retouche manuelle reste conservée.
- La banque filtre correctement effets, sons, vecteurs et templates, avec aperçu fonctionnel.
- La chorégraphie ne place pas deux éléments concurrents au même moment.
- Une retouche verrouillée survit à une nouvelle passe de l'IA et à un changement de style.
- « Refaire seulement ce passage » ne modifie rien avant ou après la plage choisie.
- Les anciens reels dépourvus de ces nouveaux champs continuent de fonctionner.
- Tester visuellement un aperçu court, puis vérifier le son, les timecodes et plusieurs images extraites.

État : **les 11 tests sont verts** (30 septembre 2026) — `node docs/direction-creative-v2/tests/test-v2.mjs` : 32/32 étapes
(suites de régression, tests des 5 agents, intégration d'un reel portant toutes les fonctions, 4 exports courts mesurés
et regardés, interface pilotée dans un Chrome sans fenêtre sur un bac isolé), puis le tableau de ces 11 tests. Détail et
preuves : `docs/direction-creative-v2/RESULTAT.md`.

## 10. Limite honnête

Le cerveau V2 est une fondation fonctionnelle, pas encore une garantie de montage 10/10. Le saut qualitatif dépendra
du storyboard, de l'exécution visuelle, de la conception sonore et de la boucle de contrôle/correction. Il faut
continuer par couches testables, conserver les sauvegardes et comparer les résultats à l'image.

## 11. Fichiers de référence

- `docs/cerveau-creatif-v2-2026-09-30/RESULTAT.md`
- `docs/amelioration-premium-2026-09-30/RESULTAT.md`
- `REPRISE.md`, sections 20 et 21
- `projects/script1/reels/script.json`
- `styles/montage/produit-3d.json`
- `engine/editeur/creative.py`
