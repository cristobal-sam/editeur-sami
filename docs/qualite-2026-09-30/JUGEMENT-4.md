# Jugement indépendant n° 4 — Vidéo 1 « qualité » (2 octobre 2026)

Vidéo jugée : `livraisons\Lot 2026-09-30 10h51\Vidéo 1 - qualité - FINAL.mp4`, l'export de 6 h 58 (le plus récent) :
71,47 s, 2144 images, 1080 × 1920, 30 i/s, H.264 (9,5 Mb/s) + AAC 48 kHz (sha1 `3677eaf6…`).

Je l'ai comparée à :
- `… - FINAL (ancien 2026-10-02 04h52).mp4`, la version notée 7,6 par le juge n° 3 (sha1 `73114a05…`), aux mêmes images ;
- `docs\references\reference-montage-spectaculaire.mp4`, la référence (2 images/s) ;
- ta version à toi (`projects\script1\reels\script.json`, style Tech application) : je ne l'ai pas rendue à nouveau, elle n'a pas
  changé (sha1 `08b767e3…`, le même qu'au juge n° 3). Son jugement (≈ 6) tient toujours.

Je n'ai rien construit. Je n'ai modifié aucun fichier du projet, à part celui-ci. Je n'ai pas utilisé le vrai serveur ni le
plugin. Rien n'a été téléchargé. Mes fichiers de travail (scripts, images, mesures) sont dans
`runtime\cache\tmp\juge4-10020900\`.

## En bref (pour l'utilisateur)

- **Note : 7,9 / 10** (avant : 7,6). Le progrès est réel et sans recul : 6 des 9 défauts du juge n° 3 sont corrigés, les 3
  autres ont nettement progressé. Ce n'est pas encore tout à fait le 8, pour une raison que personne n'avait vue jusqu'ici.
- **Ce qui est vraiment réglé** :
  - plus aucun saut d'image sans coupe : la caméra ne change de cadre que sur une coupe ou sur l'image où une carte entre ;
  - les mots en couleur « frappent » sans toucher leur voisin (« concurrent le close », « au téléphone », « gratuitement dans ») ;
  - un seul bouton « En savoir plus → » de 0:59,8 jusqu'à la fin, avec « 1 SEMAINE GRATUITE » qui se pose au-dessus au bon mot ;
  - plus de sous-titre éclair : à 0:34,5, la page que la carte redit est cachée en entier, en fondu ;
  - les apostrophes sont toutes les mêmes (« ’ ») ;
  - la grande bande blanche le long de la joue a presque disparu.
- **Ce qui empêche le 8** :
  1. **La personne saccade (défaut ancien, jamais relevé).** Environ 1 image sur 5 de la personne est répétée, et la suivante
     est sautée. Sur les gestes, on dirait qu'elle bouge à 16–22 images par seconde alors que le décor et les cartes bougent
     à 30. C'est le plus visible de 0:16 à 0:21, quand elle compte sur ses doigts. La cause est une seule ligne de code (un
     arrondi), facile à corriger, mais il faudra réexporter.
  2. **L'incrustation reste visible à l'offre, en plus léger.** Il reste un voile gris-blanc sous l'oreille gauche, le long de la
     mâchoire et sous le menton (1:04,5–1:07,7, surtout 1:06,7–1:07,7). Les oreilles restent floues.
  3. **La fin est statique** : 8 s en plan moyen (0:59,8–1:07,7), sans relance, même quand l'offre arrive.
- **Mon conseil** : la version qualité reste nettement meilleure que ta version à toi. Si on corrige la saccade (une ligne) et
  qu'on réexporte, elle vaut environ **8,1**. Avec en plus le voile de la mâchoire et une relance sur l'offre : environ 8,3.

## Notes

| Vidéo | Note | Commentaire |
| --- | --- | --- |
| **Vidéo 1 - qualité - FINAL (6 h 58, jugée)** | **7,9** | Tous les défauts de montage du juge n° 3 sont réglés. Elle perd des points pour la personne qui saccade (≈ 20 % d'images répétées), le voile clair de la mâchoire à l'offre et la fin statique. |
| Vidéo 1 - qualité - FINAL (ancien 04h52) | 7,6 | Revue à côté aux mêmes instants : je confirme la note du juge n° 3. Elle a la même saccade (mesurée), que personne n'avait vue. |
| Ta version actuelle (Tech application) | ≈ 6 | Fichier inchangé depuis le juge n° 3 : je reprends sa note sans la refaire. |
| Référence (12 s de motion design pur) | — | Autre genre. Les pilules de verre lumineuses en reprennent bien la matière. |

Détail de la note (sur 10) :

| Partie | Juge n° 1 | Juge n° 2 | Juge n° 3 | **Juge n° 4** |
| --- | --- | --- | --- | --- |
| Intégration de l'image | 5,5 | 6,5 | 7 | **7,3** |
| Cartes et textes | 6 | 8 | 8,3 | **8,6** |
| Sous-titres | 6 | 8 | 8,2 | **8,5** |
| Montage et rythme | 6,5 | 7 | 7,2 | **7,5** |
| Son | 8 | 8 | 8,2 | **8,2** |
| Message et fin | 6,5 | 7,5 | 8 | **8,4** |

Comme le juge n° 3, je pèse l'intégration et le mouvement plus que le reste : c'est ce qui fait « amateur » en premier. Le
10/10 du contrôle automatique est trop haut (voir plus bas).

## Ce que j'ai regardé (méthode)

Tout est dans `runtime\cache\tmp\juge4-10020900\`.

- **1 image/s** au milieu de chaque seconde (images 15 + 30k) : `pl-final-00.png` à `pl-final-05.png` (12 images par planche).
- **Sauts et coupes** :
  - différence entre images voisines sur les 2144 images, et bandes aux 4 bords (`mesure.py` → `mesure-final.json`) ;
  - caméra du studio image par image, calculée avec le code actuel de `timeline.ts` en lecture seule, sur une copie du reel
    (`vue.mjs` → `vue.txt`, `vue.json`) ;
  - image d'avant / image d'après chaque coupe ou recadrage (`sauts\`, `coupes-a.png`, `coupe-6773.png`,
    `coupe-6773-old.png`) et recalage SIFT (`echelle.py`).
- **Images répétées de la personne** :
  - différence de la zone visage / buste image par image (`dup.py` → `dup-final.txt`), sur l'export, la prise optimisée
    (`projects\_cache\optimises\Hook (4)-eabf80b6.mp4`) et les images du détourage (`assets\detourage\c47796ced7c100e33201\*.webp`) ;
  - prédiction par la formule de `design.tsx` (`idx.mjs` → `predits.json`) ;
  - preuve à l'œil : `doublons-mains.png` (0:19,33–0:19,70, mains qui comptent), `m45.png` (0:45,4–0:45,6).
- **Ouverture** (images 0, 1, 6, 12, 27, 60, 86, 87, 100) : `ouverture.png`.
- **Mots en couleur** : `pop-concurrent.png` (images 85 à 99), `pop-autres.png` (« téléphone », « gratuitement »).
- **Sous-titre éclair et carte de 0:34,5** (une image sur trois, 34,2–35,7 s) : `flash-sheet.png`.
- **Bouton et fin** : `divers-sheet.png` (59,67–61,0 s et 68,9–69,6 s), `offre-new-full.png`, `fin-full.png`.
- **Bords du détourage** :
  - joue à l'offre, ancien / nouveau aux mêmes images : `joue-avant-apres.png`, `joue-x3.png` (× 2,6) ;
  - visage à 0:12,7 et 0:42,5, ancien / nouveau : `visage-1270.png` ;
  - cheveux et tempes à 0:09,5, 0:38,5, 1:05,5 : `cheveux.png` ;
  - vue de téléphone à ces trois moments : `hd-cles.png`.
- **Mains**, ancien / nouveau : `mains-overview.png`, `mains-1149.png` (0:38,3), `mains-1254.png` (0:41,8), `m16.png` (0:16,5).
- **Référence**, 2 images/s : `pl-ref-00.png`.
- **Son** : ebur128 sur l'export ; écart avec l'export de 4 h 52 par fenêtres de 50 ms ; niveau de la fin.
- **Temps des mots et des pages** : `infos.mjs` (PAGES=1) et `mots.mjs`, en lecture seule.

## Son (mesuré)

- **Niveaux** : −14,0 LUFS intégré, crête vraie −1,0 dBFS, LRA 3,1 LU. **Conforme**, identique à l'export de 4 h 52.
- **Mixage** : l'écart avec l'export de 4 h 52 est à −50 dB en tout. Seuls changements : de petits sons d'entrée (0:34,45, 0:35,8,
  0:43,9, 0:56,3, 1:04,4–1:04,65, 1:08,75), à −29 dB au plus sous une voix à −11 dB. Le reste du son n'a pas bougé : les
  mesures du juge n° 3 (aucun clic aux coupes, musique dans les pauses, fin en fondu jusqu'à −45 dB) restent vraies.
- **Limite** : je n'ai pas pu *écouter*. Je ne juge ni le timbre, ni le débruitage, ni le choix de la musique.

## Points forts

1. **Plus aucun saut d'image sans coupe.** Sur les 2144 images, les seuls changements brusques sont :
   - les 8 coupes (12,63 ; 21,00 ; 23,13 ; 28,70 ; 41,67 ; 45,03 ; 54,47 ; 67,73 s) ;
   - les 2 relances de l'accroche (× 1,20 sur « concurrent » à 2,90 s, × 0,83 à 6,30 s) ;
   - les 3 reculs à l'entrée d'une carte (16,97 ; 34,50 ; 59,83 s), chacun **sur l'image où la carte apparaît**.

   Les anciens sauts de 0:25,6, 0:36,6, 0:40,4 et 1:03,7 ont disparu (différence entre images normale, aucun décalage). Les
   coupes changent toutes de valeur de plan : d'au moins × 1,15 d'après la caméra calculée par le code, et à l'œil sur les
   images d'avant et d'après (`coupes-a.png`, `coupe-5447.png`, `coupe-6773-old.png`). Seule 0:28,70 reste plus proche
   (× 1,09 : changement de prise, cadre un peu plus serré et plus haut) ; elle se lit quand même comme une coupe.
2. **Les cartes poussent la personne.** À 0:34,50 et 0:59,83, la caméra recule sur l'image même où la carte commence à
   apparaître (`flash-sheet.png`, `divers-sheet.png`) : on lit « la carte prend sa place ». Ce n'est plus « elle rapetisse,
   puis une carte arrive ».
3. **Un seul bloc final.** « En savoir plus → » entre à 0:59,83, sur ses mots, et ne bouge plus jusqu'à la dernière image.
   « 1 SEMAINE GRATUITE » se pose au-dessus à 1:04,45, sur « gratuitement ». La fin finit sur un sourire, bouche fermée
   (`fin-full.png`).
4. **Les mots en couleur frappent proprement.** « concurrent » grossit très légèrement (≈ × 1,04) puis revient, sans rebond ;
   l'espace avec « le » reste constant d'image en image (`pop-concurrent.png`). Même chose pour « téléphone » et
   « gratuitement » (`pop-autres.png`).
5. **Les sous-titres** :
   - aucune page éclair : la page « pour répondre et qualifier » (0:34,48–0:35,48) est cachée en entier pendant que la carte
     « Répondre → Qualifier » la dit ; « vos leads rapidement » revient en fondu (`flash-sheet.png`) ;
   - les pages qu'un bouton redit (« « En savoir plus » ») sont cachées, sans trou visible ;
   - entrées et sorties en fondu court (3 images), plus de coupure sèche ;
   - apostrophes toutes courbes : « quelqu’un », « c’est qu’embaucher », « qu’un employé », « qu’on engage »,
     « l’expérimenter » ;
   - « on a un vrai intérêt » | « à bien qualifier » : la coupure faible du juge n° 3 est réglée.
6. **La joue est bien meilleure** (`joue-avant-apres.png`, `visage-1270.png`). La large bande blanche de la tempe à la mâchoire
   (0:12,7, 0:42,5, 1:04,5–1:07,7) a laissé place à la couleur de la peau ; l'anneau doré de la boucle d'oreille se lit de
   nouveau comme un anneau (1:05,07).
7. **Les cartes sont justes et sans faute** : « Réponse envoyée au lead », la liste Salaire → Journées de maladie, « Lead en
   attente depuis 3 h », « Répondre → Qualifier », « 5× MOINS CHER », « Formé par nos soins », « Qualifier → Transférer »,
   « 1 SEMAINE GRATUITE », « En savoir plus → ». Aucun texte interne, aucun texte illisible, aucune bande au bord (0 image
   touchée sur 2144).
8. **L'ouverture accroche** : 1re image serrée avec « Plus vous prenez » (bonne miniature), recul, relance sur « concurrent »
   (`ouverture.png`).
9. **À taille de téléphone**, la plupart des plans passent pour un studio virtuel soigné (`hd-cles.png`).

## Défauts (du plus grave au moins grave)

| # | Moment | Gravité | Problème | Piste de correction |
| --- | --- | --- | --- | --- |
| 1 | Toute la vidéo sauf 0:21,0–0:28,7 et 1:07,7–1:11,5 ; pire de **0:16 à 0:21** (14 images répétées par seconde ≈ 16 i/s, quand elle compte sur ses doigts), puis 0:04–0:12, 0:29–0:41, 0:55–1:04 (8 à 12 par seconde) | **Important (défaut ancien, jamais relevé)** | **La personne saccade.** 424 images sur 2144 (19,8 %) montrent la même image du détourage que l'image d'avant ; l'image suivante saute alors une image de la prise. Le décor, les cartes et les sous-titres restent à 30 i/s, mais la personne bouge par à-coups sur les gestes (`doublons-mains.png` : 0:19,53 = 0:19,57, 0:19,60 = 0:19,63, 0:19,67 = 0:19,70 ; `m45.png` : 0:45,50 = 0:45,53). La prise optimisée et les images du détourage n'ont, elles, aucune image répétée (vérifié). La formule de `design.tsx` (`idx.mjs`) prédit les **236 sur 236** images répétées mesurées pendant un mouvement. Même défaut dans l'export de 4 h 52 (même compte). | **Cause** : `remotion/src/design.tsx`, ligne 73 : `Math.floor((tSrc-mask.start)*(mask.fps??fps))`. Pour l'image 123, `(10,17 + 123/30 − 10,17) × 30` donne 122,99999…, et `floor` rend 122, donc l'image d'avant. **Correction** : `Math.round(…)` (l'image k du détourage est prise à `start + k/fps`), ou `Math.floor(x + 1e-6)`. **Vérification à ajouter** au contrôle et aux tests : aucune paire d'images voisines d'un même plan ne doit donner le même numéro d'image du détourage. Profite à tous les styles qui détourent (Tech 3D, collage, produit). Réexport nécessaire. |
| 2 | 1:04,45–1:07,73, surtout 1:06,7–1:07,7 (contour bosselé) ; plus léger aux tempes à 0:09,5, 0:38,5, 0:42,5 | **Moyen (net progrès)** | **Voile clair de la mâchoire à l'offre.** La bande blanche de la joue est presque partie, mais il reste une zone gris-blanc sous le lobe gauche, le long de la mâchoire jusqu'au menton, et une ligne claire sous le menton (`joue-x3.png`, 1:06,07 et 1:07,07). Le contour de la mâchoire fait encore des bosses. Les oreilles restent des taches floues. Aux tempes, la peau repeinte paraît un peu « plate » à 1:1 (`cheveux.png`), mais ça ne se voit presque pas sur un téléphone. | Étendre `_fond_clair` (`detourage_rvm.py`) au-dessous de la mâchoire et du lobe : là où le bord de l'alpha est plus clair que la peau voisine ET proche du mur, baisser l'alpha de 2 à 3 px plutôt que repeindre. Médiane de l'alpha sur ± 2 images autour des oreilles. Faire tourner la passe vidéo du contrôle (`bord-clair`) sur l'export : le contrôle enregistré dans le reel a `"video": null`. La vraie solution reste un fond sombre au tournage. |
| 3 | 0:59,83–1:07,73 | Moyen à mineur | **Fin statique.** 7,9 s en plan moyen, sans aucune relance, alors que c'est l'offre et l'appel. « 1 SEMAINE GRATUITE » arrive à 1:04,45 sans aucun accent de caméra. Le haut de l'image reste vide au-dessus du bouton de 0:59,8 à 1:04,45 (la place de l'offre est gardée). | Une relance ancrée sous le bloc final (le même mécanisme que la coupe de 1:07,73, plan serré, tête sous le bouton) sur « gratuitement » à 1:04,45, avec le son d'entrée de l'offre. Ou une coupe vers le plan serré dès 1:04,45. |
| 4 | 0:37,10–0:38,20 | Mineur | **Glissement avant le « 5× ».** La personne descend d'environ 75 px (3,9 % de la hauteur) en 1,1 s, avec un léger zoom (× 1,045 → × 1,06), et la carte n'entre qu'à 0:37,88 : la caméra bouge 0,8 s avant la raison du mouvement. C'est doux et adouci, beaucoup mieux qu'un saut, mais c'est le seul endroit où la caméra « anticipe ». | Même règle que les autres cartes : recul sur l'image d'entrée du « 5× », ou glissement ≤ 3 % qui commence avec la carte. |
| 5 | 0:38,30 ; 0:45,47–0:45,53 ; 0:41,80 | Mineur | **Mains sur les gestes rapides.** Les doigts sont plus opaques qu'avant (0:41,8 : plus de grille du décor à travers la main), mais l'index près du visage est encore déchiqueté et fondu à 0:38,3 (`mains-1149.png`), et le coude est haché à 0:45,5 (`m45.png`). C'est surtout le flou de la prise. | Garder le maximum de l'alpha sur ± 1 image sur les mains en mouvement rapide ; la correction du défaut 1 rendra déjà ces gestes plus fluides. |
| 6 | 0:41,79 ; 0:23,25 ; 0:11,70 et 0:14,23 | Mineur | **Coupures encore faibles** : « Puis là c’est pas » \| « juste des gens » (la négation est coupée de « juste ») ; « Et NON, le faire » \| « toi-même entre deux tâches » ; dans une page de 2 lignes, « quelqu’un à » \| « temps plein ». | Interdire la fin de page sur « pas » quand le mot suivant est « juste », « vraiment », « encore » ; ne pas séparer un verbe de « moi-même / toi-même » ; pour les lignes, couper avant « à », « de ». |
| 7 | 0:00–0:09,3 | Mineur (goût) | **9 s sans graphisme.** L'accroche repose sur le visage, les sous-titres et deux relances. C'est propre, mais loin de l'énergie de la référence, et la 1re carte n'arrive qu'à 0:09,3. | Facultatif : un petit élément sur « Plus vous prenez de temps » (icône horloge de la nouvelle banque, en verre, 1 s, en haut). Rien qui ne soit pas dit. |

Les effets (reflet sur les cartes, lueur chaude à gauche, horizon, grain) ont tous une raison et restent discrets.

## Suivi des 9 défauts du juge n° 3

| # juge 3 | Défaut | État | Ce que j'ai vu |
| --- | --- | --- | --- |
| 1 | Bande blanche sur la joue à l'offre, oreilles fondues | **Partiel (net progrès)** | La bande de la tempe et de la joue est presque partie (`joue-avant-apres.png`) ; boucle d'oreille de nouveau lisible. Restent le voile de la mâchoire et du menton, le contour bosselé à 1:06,7–1:07,7 et les oreilles floues (défaut 2). |
| 2 | 4 sauts sans coupe (0:25,6 ; 0:36,6 ; 0:40,4 ; 1:03,7) | **Corrigé** | Aucun saut à ces moments ni ailleurs. Reste un glissement doux 0:37,1–0:38,2 (défaut 4). |
| 3 | Mots en couleur qui touchent leur voisin | **Corrigé** | Espace constant, frappe sans rebond. |
| 4 | Bouton qui part et revient | **Corrigé** | Un seul bouton de 0:59,83 à la fin, l'offre au-dessus à 1:04,45. Le vide au-dessus du bouton reste jusqu'à 1:04,45 (défaut 3). |
| 5 | Sous-titre éclair à 0:34,5 | **Corrigé** | Page cachée en entier, retour en fondu. |
| 6 | Recul ≈ 1 s avant la liste et le bouton | **Corrigé** | Recul sur l'image d'entrée (16,97 et 59,83 s ; aussi 34,50 s). |
| 7 | Main transparente | **Partiel** | Plus opaque ; doigts encore fondus sur les gestes très rapides (défaut 5). |
| 8 | Apostrophes mélangées | **Corrigé** | « ’ » partout, sous-titres et cartes. |
| 9 | Coupures faibles | **Partiel** | « on a un vrai intérêt » \| « à bien qualifier » réglé ; restent « c’est pas » \| « juste », « le faire » \| « toi-même », « quelqu’un à » \| « temps plein » (défaut 6). |

**Défaut nouveau de ce cycle** : aucun. Le glissement du « 5× » est mineur.

**Défaut ancien que personne n'avait relevé** : la personne saccade (défaut 1). Il existait déjà dans l'export de 4 h 52 et,
d'après la formule, dans tous les exports détourés.

## Ce que le contrôle automatique n'a pas vu (10/10, 0 constat)

Il a raison sur ce qu'il mesure : zone sûre, bords, orthographe, son, sauts de cadre, pages éclair, bouton qui revient,
apostrophes. Mais :
- il ne voit pas les images répétées de la personne (défaut 1) ;
- le contrôle enregistré dans le reel (2 oct., 6 h 53) a `"video": null` : la passe vidéo, donc le repère `bord-clair`, n'apparaît
  pas pour cet export ;
- il ne juge pas le rythme de la fin (8 s sans relance).

Les deux premières vérifications sont simples à ajouter (la 1re se calcule sans vidéo, avec la formule des numéros d'image).

## Comparaison détaillée

- **Avec l'export de 4 h 52 (note 7,6)** :
  - **progrès** : plus de sauts, plus de mots qui se touchent, bloc final unique, plus de page éclair, apostrophes, joue
    beaucoup plus propre, mains un peu plus opaques, reculs sur l'image d'entrée des cartes ;
  - **recul** : aucun ;
  - **commun aux deux** : la saccade de la personne, les oreilles floues ;
  - **net progrès d'environ +0,3.**
- **Avec ta version actuelle (Tech application)** : la version qualité gagne sur l'orthographe (ta version garde « de la
  publicités » et « qualifier et éduqué »), le message (liste, parcours, 5×, badge, offre, bouton), la lisibilité et l'image
  de marque. Ta version garde le naturel d'un vrai lieu, sans bord de détourage. **Je conseille toujours de prendre la version
  qualité.**
- **Avec la référence** (`pl-ref-00.png`) : ce n'est pas le même genre. La référence, c'est 12 s de motion design pur : un
  changement toutes les 0,25 à 0,5 s, de grands éléments au centre, du flou de mouvement, un glitch. La vidéo jugée en reprend
  la matière (verre à liseré, lueurs, reflet) et un peu de la vie (compteur, coche, liste qui glisse). Ses éléments restent
  plus petits et en haut, pour laisser le visage libre, ce qui est logique pour une pub face caméra de 71 s. Ce qui la
  rapprocherait le plus de la référence : la fluidité (défaut 1) et un élément visuel dans les 3 premières secondes (défaut 7).

## Ordre de correction conseillé

1. **Saccade** (défaut 1) : une ligne dans `design.tsx`, une vérification dans le contrôle et un test, puis réexport.
   C'est le gain le plus grand pour le moins d'effort : ≈ 8,1.
2. **Relance sur l'offre** (défaut 3) et **recul du « 5× » sur son image d'entrée** (défaut 4) : règles de caméra dans
   `timeline.ts` (et dans les données si la chorégraphie lit ces temps).
3. **Voile de la mâchoire** (défaut 2) : détourage, plus long (plusieurs minutes de carte graphique par plan). Avec 1 et 2 :
   ≈ 8,3.
4. Le reste (défauts 5 à 7).

Toutes ces corrections sont générales : la 1re sert à tous les styles qui détourent la personne.

## Limites de ce jugement

- Je n'ai pas *écouté* la vidéo : le son est jugé sur des mesures seulement.
- La saccade est mesurée et prouvée image par image (et expliquée par le code). Sa gêne à l'œil dépend du geste : nette sur les
  mains qui comptent (0:16–0:21), à peine visible quand elle parle immobile.
- Les tailles aux coupes entre deux prises différentes sont moins sûres (peu de points communs) : je me suis appuyé sur les
  images autant que sur le chiffre.
- Ta version Tech application n'a pas été rendue à nouveau : son fichier n'a pas changé depuis le juge n° 3.
- Je n'ai relancé ni les tests ni le contrôle : aucun code n'a été modifié pendant ce jugement.
