# Jugement indépendant n° 3 — Vidéo 1 « qualité » (2 octobre 2026)

Vidéo jugée : `livraisons\Lot 2026-09-30 10h51\Vidéo 1 - qualité - FINAL.mp4`. C'est l'export de 4 h 52 :
71,47 s, 1080 × 1920, 30 i/s, H.264 + AAC 48 kHz (sha1 `73114a05…`).

Je l'ai comparée à :
- `… - FINAL (ancien 2026-10-02 03h01).mp4`, la version notée 7,3 par le juge n° 2 ;
- `docs\references\reference-montage-spectaculaire.mp4`, la référence ;
- ta version actuelle (`projects\script1\reels\script.json`, style Tech application). Je l'ai rendue en 8 images fixes avec
  le code actuel, en lecture seule. Le fichier n'a pas changé (sha1 `08b767e3…`).

Je n'ai rien construit. Je n'ai modifié aucun fichier du projet, à part celui-ci. Je n'ai pas utilisé le vrai serveur. Mes
fichiers de travail sont dans `runtime\cache\tmp\juge3-10020510\`.

## En bref (pour l'utilisateur)

- **Note : 7,6 / 10** (avant : 7,3). Le progrès est réel : presque tous les défauts du juge n° 2 sont corrigés. Ce n'est
  pas encore le 8. Le monteur s'était donné ≈ 7,9 : c'est un peu généreux, mais beaucoup plus proche que les fois d'avant.
- **Ce qui est vraiment réglé** :
  - la bande noire du haut a disparu : 0 image touchée sur 2144, mesuré sur les 4 bords ;
  - « avec de la publicité » est bien écrit ;
  - la coupe de 1:07,7 change enfin de plan ; pendant l'appel final, la personne est plus grande ;
  - la 1re image est serrée avec le premier sous-titre, puis la caméra recule ; elle relance ensuite sur « concurrent » ;
  - l'avant-bras de 0:41,7 passe derrière le bureau de verre : plus de bras coupé en pointe ;
  - les sous-titres sont mieux coupés (« pour régler ça, » | « ça veut dire », « quoi que ce soit ») ;
  - « trois heures » est lisible ;
  - le badge « Formé par nos soins » arrive sur ses mots ;
  - la liste se recentre à mesure que les pilules arrivent ;
  - la fin tient 0,8 s : elle sourit, et le bouton et la musique s'éteignent proprement.
- **Ce qui empêche le 8** :
  1. **L'incrustation se voit encore pendant l'offre (1:04,5–1:07,7).**
     - Une bande blanche longe la joue gauche et le dessous de la mâchoire. Elle n'existe pas dans la prise d'origine
       (vérifié sur ta version au même instant) : c'est le mur blanc du bureau qui reste collé au bord.
     - Les oreilles et les boucles d'oreilles sont « fondues ».
  2. **Quatre petits sauts d'image (défaut nouveau).** À 0:25,6, 0:36,6, 0:40,4 et 1:03,7, la personne descend (ou remonte)
     d'un coup de 50 à 150 pixels, sans coupe et sans changer de taille. On dirait une image qui saute. C'est l'effet de la
     nouvelle règle « jamais de glissement ».
  3. **Les mots en couleur qui « frappent » touchent leur voisin** pendant 2 ou 3 images : « concurrentle » à 0:02,9,
     « autéléphone » à 0:44,5, « gratuitementdans » à 1:04,5.
- **Petites finitions** :
  - un sous-titre éclair de 0,2 s à 0:34,5 ;
  - le bouton « En savoir plus » s'en va à 1:02,8 puis revient à 1:08,8 ;
  - les apostrophes sont mélangées (« c’est » courbe, « quelqu'un » droit) ;
  - la main est transparente sur les gestes rapides.
- **Par rapport à ta version actuelle (Tech application, ≈ 6)** : la version qualité est nettement meilleure.
  - Ta version garde « avec de la publicités » et « qualifier et éduqué ».
  - Son « 5× MOINS CHER » touche les cheveux, son bureau est surexposé et il n'y a pas de bouton.
  - **Je conseille de prendre la version qualité.** Avec les corrections rapides des points 2 et 3 et des finitions, elle
    vaudrait environ 7,9.

## Notes

| Vidéo | Note | Commentaire |
| --- | --- | --- |
| **Vidéo 1 - qualité - FINAL (4 h 52, jugée)** | **7,6** | Plafonnée par l'incrustation encore visible à l'offre (joue blanche, oreilles). Perd aussi des points pour 4 sauts d'image sans changement de plan (défaut nouveau) et pour les mots en couleur qui touchent leur voisin. |
| Vidéo 1 - qualité - FINAL (ancien 03h01) | 7,3 | Revue à côté aux mêmes instants : je confirme la note du juge n° 2. |
| Ta version actuelle (Tech application, images fixes) | ≈ 6 | Inchangée : bureau surexposé et encombré, « publicités », « éduqué », « 5× » collé aux cheveux, pas de bouton. Le nouveau découpage des sous-titres s'y applique déjà. |
| Référence (12 s de motion design pur) | — | Autre genre. Les pilules de verre lumineuses en reprennent bien la matière. |

Détail de la note (sur 10) :

| Partie | Juge n° 1 | Juge n° 2 | **Juge n° 3** |
| --- | --- | --- | --- |
| Intégration de l'image | 5,5 | 6,5 | **7** |
| Cartes et textes | 6 | 8 | **8,3** |
| Sous-titres | 6 | 8 | **8,2** |
| Montage et rythme | 6,5 | 7 | **7,2** |
| Son | 8 | 8 | **8,2** |
| Message et fin | 6,5 | 7,5 | **8** |

Le 10/10 du contrôle automatique est trop haut (voir « Ce que le contrôle automatique n'a pas vu »).

## Ce que j'ai regardé (méthode)

Tout est dans `runtime\cache\tmp\juge3-10020510\`.

- **1 image/s** au milieu de chaque seconde (images 15 + 30k, de 0,5 s à 70,5 s) :
  - vidéo jugée : `pl-final-00.png`, `pl-final-01.png`, `pl-final-02.png` ;
  - ancien export 03h01 : `pl-old-00.png`, `pl-old-02.png`.
- **Sauts de cadre** :
  - différence entre images voisines sur les 2144 images (`mesure.py`, résultat `mesure-final.json`) : 18 sauts trouvés,
    les 8 coupes et 10 changements dans une même prise ;
  - image d'avant et image d'après chaque saut : `sauts-a.png`, `sauts-b.png` ;
  - facteur de taille et décalage mesurés par recalage de points SIFT sur la personne, cartes exclues (`echelle.py`) ;
  - les 4 sauts sans changement de taille, avec des lignes repères : `micro-sauts.png`.
- **Bandes au bord** : profil de luminance des 40 premiers pixels des 4 bords, sur toutes les images (`mesure.py`).
- **Ouverture** (images 0, 1, 6, 12, 27) : `ouverture.png`, et taille mesurée entre la 1re image et les suivantes.
- **Pleine définition, moments clés** (12,7 ; 26,5 ; 29,8 ; 32 ; 38,3 ; 46,6 ; 50,5 ; 65 ; 68,3 ; 71,43 s) : `hd-cles.png`.
- **Mots en couleur qui « frappent »** : `pop-concurrent.png` (images 84 à 100), `pop-autres.png` (« téléphone »,
  « gratuitement »).
- **Bords du détourage** :
  - tête à 1:1 : `bords-tete.png` ;
  - avant / après aux mêmes instants : `avant-apres-1270.png`, `avant-apres-6500.png` ;
  - oreilles et joue agrandies : `oreilles-6500.png`, `joue-gauche-x15.png`, `joue-offre.png` (1:04,5–1:07,7 toutes les
    0,2 s), `joues.png` ;
  - prise d'origine au même instant (ta version) : `user-visage-6500.png`.
- **Table et mains** :
  - bureau de verre et main à 0:38,3 : `zoom-table-main.png` ;
  - avant-bras après la coupe de 0:41,67, image par image : `c41-sheet.png`.
- **Cartes** :
  - liste (16,8–20 s) : `liste-sheet.png` ;
  - badge, bouton, offre, bouton final : `cartes-sheet.png`.
- **Sous-titres** :
  - page éclair de 0:34,5 : `flash-3448.png`, et le même moment dans l'ancien export : `flash-ancien.png` ;
  - apostrophes : `apostrophes.png` ;
  - « trois heures », avant / après : `trois-heures.png`.
- **Fin tenue** (70,17–71,43 s) : `fin-sheet.png`.
- **Ta version actuelle** : 8 images rendues avec `stills.mjs`, copie de l'outil du juge n° 2, en lecture seule :
  `planche-user.png`.
- **Référence**, 2 images/s : `pl-ref-00.png`.
- **Mesures** :
  - son : ebur128, RMS par 50 ms, écart entre les deux mixages, enveloppe toutes les 5 ms autour de chaque coupe, spectre
    de la fin ;
  - temps des mots, des pages et des cartes : `infos.mjs`, `mots.mjs` et `captionHiddenWhy` de `timeline.ts`, en lecture
    seule.

## Son (mesuré)

- **Niveaux** : −14,0 LUFS intégré, crête vraie −1,0 dBFS, LRA 3,1 LU. C'est **conforme**, et identique à l'export
  03h01.
- **Mixage** : l'écart entre les deux mixages est à −51 dB en tout, donc presque nul. Seuls ajouts :
  - le whoosh du nouveau badge (0:45,8–0:46,0) ;
  - la fin tenue.

  Le reste du son n'a pas bougé.
- **Musique et voix** :
  - la parole est à −15 dB RMS (médiane, fenêtres de 50 ms) ;
  - les pauses avec seulement la musique sont entre −28 et −35 dB ;
  - on entend la musique dans les pauses, pas sous les mots.
- **Coupes** : aucun clic.
  - À 0:54,46, le souffle de fin de « transférer » s'éteint en 15 ms, comme dans la version 03h01. Ce n'est pas un clic,
    mais c'est à écouter.
  - À 0:28,70, le bruit de fond monte de −40 à −26 dB au changement de prise. C'est normal, ce n'est pas un clic.
- **Fin** : le dernier mot finit à 1:10,67 et la vidéo à 1:11,47.
  - De 1:10,7 à 1:11,0, le niveau est à −24/−28 dB : basses de la musique et son de la prise.
  - La musique s'éteint ensuite jusqu'à −45 dB sur la dernière image.
  - **La fin n'est plus sèche.**
- **Limite** : je n'ai pas pu *écouter*. Je ne juge ni le timbre, ni le débruitage, ni le choix de la musique.

## Points forts

1. **Plus aucune bande au bord.** Mesuré sur les 4 bords et les 2144 images : 0 image touchée (bande ≥ 2 px). Le
   rapport entre la ligne du bord et la ligne à 35 px ne descend jamais sous 0,88.
2. **Les sous-titres se lisent comme des phrases.**
   - Les pages sont coupées après la virgule : « pour régler ça, » | « ça veut dire » | « un salaire au complet, ».
   - Les expressions restent entières (« quoi que ce soit »).
   - Plus de « ça ça ».
   - « trois heures » a un halo sombre et se lit sur les mains (`trois-heures.png`).
3. **Les cartes disent ce que dit la voix**, au mot près, et ne contiennent aucune faute :
   - « Réponse envoyée au lead », « Lead en attente depuis 3 h » ;
   - « Répondre → Qualifier », le compteur jusqu'à « 5× MOINS CHER » ;
   - « Formé par nos soins », « Qualifier → Transférer » ;
   - « 1 SEMAINE GRATUITE », « En savoir plus → ».
4. **Le nouveau badge est juste.** « Formé par nos soins » apparaît sur « formé » (0:45,85), et la coche se pose en
   0,2 s. Le sous-titre qui dit la même chose s'efface pendant ce temps. Il remplit sans bavarder les 10 s qui étaient vides.
5. **La liste est propre.** « Salaire » arrive au centre, glisse quand « Avantages sociaux » arrive, puis la 2e rangée se
   centre à son tour (`liste-sheet.png`).
6. **L'ouverture accroche mieux.**
   - La 1re image est serrée sur le visage, avec « Plus vous prenez » déjà affiché (bonne miniature).
   - La caméra recule (× 0,83 en 0,4 s), puis relance (× 1,20) sur « concurrent » à 0:02,90.
7. **Les coupes changent vraiment de plan**, celle de 1:07,73 comprise : la tête grandit nettement sous l'offre
   (`sauts-b.png`, dernière paire). Les relances dans une même prise (0:02,9, 0:06,3, 0:16,0, 0:32,2, 0:58,9) changent la
   taille de × 1,2 ou × 0,83 : ce sont de vrais « punch ».
8. **Bras et table** :
   - à 0:41,67, l'avant-bras passe derrière le bureau de verre dès la 1re image (`c41-sheet.png`) ;
   - à 0:12,7, le bras disparaît derrière le liseré du bureau de façon crédible.
9. **La fin est construite** :
   - l'offre arrive sur « gratuitement » (1:04,45) ;
   - le bouton arrive sur « En savoir plus » (1:08,8) ;
   - elle finit sur un sourire, bouche fermée, avec le bouton et l'offre jusqu'à la dernière image (`fin-sheet.png`).
10. **L'incrustation a progressé** par rapport à 03h01 (`avant-apres-6500.png`, `avant-apres-1270.png`) :
    - le halo blanc régulier autour des cheveux a presque disparu ;
    - la peau est moins brûlée ;
    - le grain rapproche la texture de la personne et du décor.

    À taille de téléphone, la plupart des plans passent pour un studio virtuel soigné.

Je n'ai trouvé **aucun texte interne** (nom de fichier, identifiant, consigne), **aucun texte illisible** et **aucun
problème de niveau sonore**.

## Défauts (du plus grave au moins grave)

| # | Moment | Gravité | Problème | Piste de correction |
| --- | --- | --- | --- | --- |
| 1 | 1:04,45–1:07,73 (bien visible à 1:04,5, 1:04,9, 1:05,3, 1:05,7) ; contour bosselé 1:06,7–1:07,7 ; plus léger à 0:12,7 et 0:42,5 | **Important (plafonne la note)** | **Bande blanche le long de la joue gauche**, de la tempe à la mâchoire, plus une ligne claire sous le menton, pendant l'offre (`joue-gauche-x15.png`, `oreilles-6500.png`). Elle n'existe pas dans la prise d'origine : sur ta version au même instant, la joue est d'une seule couleur et l'anneau doré est net (`user-visage-6500.png`). C'est le mur blanc du bureau, visible sous le lobe dans la prise, qui reste dans le détourage. Les oreilles et les boucles d'oreilles sont « fondues » en taches beiges. De 1:06,7 à 1:07,7, le bord de la joue fait des bosses. C'est le moment le plus important de la pub (l'offre), en plan moyen. | Retirer le débordement du mur sur une bande plus large (10 à 15 px, pas 5) quand le fond de la prise est clair : là où la couleur est proche de celle du mur et plus claire que la peau voisine, la remplacer par la peau voisine, ou réduire l'alpha de 2 à 3 px de ce côté. Lisser le contour dans le temps sur les oreilles (médiane de l'alpha sur ± 2 images). Ajouter au contrôle un repère « bord clair » : pixels proches du blanc dans les 15 px intérieurs du bord de l'alpha. La vraie solution reste de filmer devant un fond sombre. |
| 2 | 0:25,63 ; 0:36,60 ; 0:40,43 ; 1:03,73 | **Moyen (défaut nouveau)** | **Sauts d'image sans changement de plan.** Dans une même prise, sans coupe, la personne descend d'un coup de 57 px (0:25,63, taille × 1,00), de 54 px (0:36,60, × 1,00), de 52 px (1:03,73, × 0,99), ou remonte de 151 px (0:40,43, × 1,04, en milieu de phrase sur « avoir »). Mesuré par recalage SIFT (`echelle.py`) et vu sur `micro-sauts.png`. Un recadrage de moins de 5 % sans coupe se lit comme une image qui saute, pas comme un changement de caméra. Ces sauts n'existaient pas dans l'export 03h01 (`flash-ancien.png`), où la caméra glissait. Cause : la bascule « faire de la place à une carte » (`DY_ROOM`) est appliquée d'un coup. | Un changement de cadre instantané doit changer la taille d'au moins × 1,15 (même règle que les coupes). Sinon, au choix : appliquer la bascule dès la coupe précédente et la garder ; ou la faire en glissement lent (≥ 0,8 s, adouci, ≤ 3 % de la hauteur), qui ne se voit pas ; ou la combiner avec un vrai punch. Ajouter au contrôle : « saut sans coupe, taille entre × 0,93 et × 1,07, décalage > 1,5 % de la hauteur en une image ». |
| 3 | 0:02,90–0:02,93 ; 0:44,50–0:44,57 ; 1:04,47–1:04,50 (tous les mots en couleur) | Mineur à moyen | **Les mots en couleur touchent leur voisin quand ils « frappent ».** On voit « concurrentle close » (agrandi × 1,2 pendant l'accroche), « autéléphone » et « gratuitementdans » pendant 2 à 3 images. Après « concurrent », l'espace devient trop large pendant 0,2 s (0:03,00–0:03,17) : le ressort repasse sous × 1 (`pop-concurrent.png`, `pop-autres.png`). Toute la ligne semble trembler. Cause : `Reel.tsx`, lignes 283–284. Le mot (inline-block, marge 0,1 em) est agrandi sans que sa place grandisse, avec un ressort peu amorti (damping 11). | Garder la place du mot : agrandir un span intérieur, ou augmenter sa marge au même rythme que l'agrandissement. Ou animer seulement la lueur, la luminosité et un léger `translateY`. Sinon, plafonner à × 1,06 avec un amortissement ≥ 18, sans rebond. |
| 4 | 1:02,83–1:08,80 | Mineur | **Le bouton s'en va, puis revient.** « En savoir plus → » (avec « RYUCALLS ») apparaît à 0:59,83, sort à 1:02,83 et revient à 1:08,80. Entre 1:02,87 et 1:04,45, le haut de l'image est vide pendant 1,6 s, avec la personne en plan moyen et le saut de 1:03,73. L'offre est ensuite posée seule, en plan moyen, jusqu'à 1:07,73. | Un seul bloc final : garder le bouton de 0:59,83 jusqu'à la fin et poser « 1 SEMAINE GRATUITE » au-dessus à 1:04,45. Cela supprime aussi le vide, le saut de 1:03,73 et le plan moyen du début de l'offre. |
| 5 | 0:34,50–0:34,67 | Mineur | **Sous-titre éclair** : « pour répondre et qualifier » reste 0,2 s (6 images), puis s'efface d'un coup, avant même que la carte n'apparaisse (0:34,77) (`flash-3448.png`). C'était déjà le cas dans l'export 03h01 (`flash-ancien.png`), mais le juge n° 2 ne l'a pas relevé. | Si une page doit s'effacer parce qu'une carte redit ses mots moins de 0,5 s après son début, la masquer dès son début, ou faire entrer la carte au début de la page. Toujours un fondu, jamais une coupure. Ajouter au contrôle : page visible moins de 0,3 s. |
| 6 | 0:16,03 → 0:16,95 ; 0:58,87 → 0:59,83 | Mineur | **« Elle rapetisse, puis une carte arrive. »** Le plan s'élargit franchement (× 0,83) environ 0,95 s avant la liste et avant le bouton. Pendant presque 1 s, le haut de l'image est vide, sans raison visible. C'est bien mieux que le glissement d'avant, mais le geste reste mécanique. | Faire l'élargissement sur l'image où la carte entre (même image, avec son whoosh) : la carte « pousse » alors la personne vers le bas. |
| 7 | 0:38,30 (main à 5 doigts, moment du 5×) ; 0:41,80–0:41,87 ; 0:29,5 ; 0:32 | Mineur | **Main transparente** sur les gestes rapides : la grille du décor se voit à travers les doigts (`zoom-table-main.png`, `c41-sheet.png`). Connu et annoncé, non corrigé. | Garder le maximum de l'alpha sur ± 1 à 2 images pour les mains en mouvement rapide (zone sous les épaules, fort flux optique). |
| 8 | 0:12,75–0:15,07 ; 0:25,63 ; 0:38,92 ; 0:43,05 ; 1:01,81 | Mineur | **Apostrophes mélangées** : courbes dans « c’est », « qu’embaucher », « qu’un », « l’expérimenter » ; droites dans « quelqu'un », « qu'on », « qu'un employé » (`apostrophes.png`). Un œil de graphiste le voit sur deux pages qui se suivent (0:12,75 puis 0:14,23). | Normaliser `'` en `’` dans `displayWord` (affichage) et dans les textes de cartes. |
| 9 | 0:41,79 ; 0:50,15–0:51,69 ; 0:11,70 et 0:14,23 | Mineur | **Quelques coupures encore faibles** : « Puis là c’est » \| « pas juste des gens » ; « on a un vrai » \| « intérêt à bien » \| « qualifier ». Dans une page de 2 lignes, la 1re ligne finit sur « à » (« quelqu'un à / temps plein »). | Interdire aussi la fin de page sur « c’est », sur un adjectif placé avant son nom (« un vrai ») et sur « bien » suivi d'un infinitif. Pour les lignes, couper avant les petits mots (« à », « de ») au lieu de laisser `text-wrap: balance` décider. |

Les effets (reflet sur les cartes, lueur chaude à gauche, horizon, grain) ont tous une raison et restent discrets. La
lueur brun-orangé du côté gauche du décor, pendant l'accroche, est un peu boueuse. C'est une affaire de goût, pas un
défaut.

## Suivi des 13 défauts du juge n° 2

| # juge 2 | Défaut | État | Ce que j'ai vu |
| --- | --- | --- | --- |
| 1 | Bande noire en haut (14 s) | **Corrigé** | 0 image sur 2144, aux 4 bords. |
| 2 | Incrustation visible | **Partiel** | Halo autour des cheveux presque disparu, peau moins brûlée, grain. Restent la bande blanche sur la joue pendant l'offre, les oreilles fondues et la main transparente (défauts 1 et 7). |
| 3 | « de la publicités » | **Corrigé** | « avec de la publicité, » (0:06,44). |
| 4 | Coupe au même cadre à 1:07,7 | **Corrigé** | La tête grandit nettement sous l'offre. |
| 5 | Caméra qui recule avant chaque carte, appel final loin | **Partiel** | Plus aucun glissement. La tête est à 0,33 H pendant l'offre (avant 0,38) et le plan est serré dès 1:07,73. Mais les glissements sont devenus 4 sauts sans changement de taille (défaut 2), et l'élargissement arrive encore 1 s avant la carte (défaut 6). |
| 6 | Ouverture plate | **Corrigé** | 1re image serrée avec sous-titre, recul, punch sur « concurrent ». Le mot qui frappe touche « le » (défaut 3). |
| 7 | Avant-bras coupé à 0:41,67 | **Corrigé** | Le bras passe derrière le bureau dès la 1re image. |
| 8 | Doigts fantômes | **Non corrigé** | Annoncé par le monteur (défaut 7). |
| 9 | Pages mal coupées | **Corrigé** | Les deux cas cités sont réglés. Il reste des coupures faibles ailleurs (défaut 9). |
| 10 | « trois heures » peu lisible | **Corrigé** | Halo sombre serré, lisible sur les mains. |
| 11 | 10 s sans carte | **Corrigé** | Badge « Formé par nos soins » à 0:45,85–0:48,45, sur ses mots. |
| 12 | « Salaire » seul dans un coin | **Corrigé** | Centré, puis glisse quand la 2e pilule arrive. |
| 13 | Fin sèche | **Corrigé** | 0,8 s de tenue, sourire, musique en fondu jusqu'à −45 dB. |

**Défauts nouveaux de ce cycle** :
- les 4 sauts sans changement de plan (défaut 2), effet direct de la règle « jamais de glissement » ;
- les mots qui touchent leur voisin (défaut 3), effet direct de la « frappe » ajoutée à l'ouverture et à tous les mots en
  couleur.

Défauts anciens que personne n'avait relevés : la bande blanche de la joue (défaut 1), le sous-titre éclair (défaut 5)
et les apostrophes mélangées (défaut 8).

## Ce que le contrôle automatique n'a pas vu (10/10, 0 constat)

Il a raison sur ce qu'il mesure : la zone sûre, les bords, l'orthographe, le son, les coupes entre prises. Mais il
**manque** :
- les 4 sauts d'image dans une même prise : sa vérification « coupe au même cadre » ne regarde que les vraies coupes ;
- les mots en couleur qui touchent leur voisin ;
- le sous-titre éclair de 0,2 s à 0:34,5 ;
- la bande blanche de la joue et les oreilles fondues (il ne juge pas l'intégration) ;
- le bouton qui s'en va et revient ;
- les apostrophes mélangées.

Un 10/10 donne une fausse assurance. Les trois vérifications proposées plus haut (saut sans coupe, page visible moins de
0,3 s, bord clair) sont simples à ajouter.

## Comparaison détaillée

- **Avec l'export 03h01 (note 7,3)** :
  - **progrès** :
    - plus de bande noire, plus de faute ;
    - coupe de 1:07,7 réglée, appel final plus proche, ouverture plus forte ;
    - avant-bras réglé, pages mieux coupées, « trois heures » lisible ;
    - un badge de plus, liste centrée, vraie fin ;
    - halo autour des cheveux beaucoup plus faible ;
  - **recul** : les 4 sauts d'image et les mots qui touchent leur voisin ;
  - **net progrès d'environ +0,3.** Les défauts restants se voient surtout à l'offre, qui est le moment qui compte.
- **Avec ta version actuelle (Tech application)** (`planche-user.png`) :
  - **la version qualité gagne** sur :
    - l'orthographe : ta version garde « avec de la publicités » à 0:06,9 et « qualifier et éduqué » à 0:52,5, parce que
      ses mots ne sont pas relus ;
    - le message : liste, parcours, 5× qui compte, badge, offre et bouton ;
    - la lisibilité : ta version a de petits sous-titres sur un fond clair ;
    - l'image de marque ;
  - **ta version gagne** sur le naturel : vrai lieu, aucun bord de détourage ;
  - **elle perd** sur :
    - la fenêtre et le mur brûlés, les chaises et la table ;
    - le « 5× MOINS CHER » posé sur les cheveux ;
    - l'appel final, sans bouton.
  - Le nouveau découpage des sous-titres s'y voit déjà (« Plus vous prenez », « pour régler ça »), sans que le fichier ait
    changé.
- **Avec la référence** (`pl-ref-00.png`) : ce n'est pas le même genre.
  - La référence, c'est 12 s de motion design pur : un changement toutes les 0,25 à 0,5 s, de grands éléments au centre,
    du flou de mouvement, un glitch chromatique.
  - La vidéo jugée en reprend la matière (pilules de verre à liseré, lueurs, reflet) et un peu de la vie (compteur, coche
    qui se pose, liste qui glisse).
  - Ses éléments sont plus petits et placés en haut, pour laisser le visage libre. C'est logique pour une pub face caméra
    de 71 s.

## Ordre de correction conseillé

1. **Sauts sans changement de plan** (défaut 2) : une règle dans la caméra du studio et une vérification dans le contrôle.
   C'est rapide, et c'est ce qui fait le plus « amateur » parmi les défauts neufs.
2. **Mots qui frappent** (défaut 3) : quelques lignes dans `Reel.tsx`.
3. **Bloc final unique** (défaut 4), **sous-titre éclair** (défaut 5) et **apostrophes** (défaut 8) : des finitions courtes.
4. **Bande blanche de la joue et oreilles** (défaut 1) : c'est le travail le plus long, et c'est ce qui sépare 7,9 de 8,2.
5. Le reste (défauts 6, 7 et 9).

Après les points 1 à 3 : ≈ 7,9. Après le point 4 en plus : ≈ 8,2. Toutes ces corrections sont générales et profitent aux
autres vidéos du style Tech 3D. Les points 3 et 8 servent à tous les styles.

## Limites de ce jugement

- Je n'ai pas *écouté* la vidéo : le son est jugé sur des mesures seulement.
- Ta version Tech application est jugée sur 8 images fixes rendues avec le code actuel, pas sur un export.
- Les tailles aux coupes entre deux prises différentes sont moins sûres : peu de points communs. Je me suis appuyé sur les
  images, pas seulement sur le chiffre.
- Je n'ai relancé ni les tests ni le contrôle : aucun code n'a été modifié pendant ce jugement.
