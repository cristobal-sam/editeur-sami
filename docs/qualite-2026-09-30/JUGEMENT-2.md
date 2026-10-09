# Jugement indépendant n° 2 — Vidéo 1 « qualité » (2 octobre 2026)

Vidéo jugée : `livraisons\Lot 2026-09-30 10h51\Vidéo 1 - qualité - FINAL.mp4`. C'est l'export de 3 h 01 :
70,87 s, 1080 × 1920, 30 i/s, H.264 + AAC 48 kHz.

Je l'ai comparée à :
- `… - FINAL (ancien 2026-10-02 00h56).mp4`, la version notée 6,5 par le juge n° 1 ;
- `… - FINAL (ancien 2026-10-02 02h42).mp4` : seulement pour vérifier d'où vient un défaut nouveau ;
- `docs\references\reference-montage-spectaculaire.mp4`, la référence ;
- ta version actuelle (`projects\script1\reels\script.json`, style Tech application). Je l'ai rendue en images fixes
  avec le code actuel, en lecture seule. Le fichier n'a pas changé (sha1 `08b767e3…`).

Je n'ai rien construit et je n'ai modifié aucun fichier du projet, à part celui-ci. Mes fichiers de travail sont dans
`runtime\cache\tmp\juge2-10020330\`.

## En bref (pour l'utilisateur)

- **Note : 7,3 / 10** (avant : 6,5). Le progrès est net et réel. Ce n'est pas encore le 8 visé.
- **Ce qui est vraiment réglé** :
  - les sous-titres restent pendant les cartes : on suit enfin la phrase sans le son ;
  - la carte de 0:26 dit le bon message (« Lead en attente depuis 3 h », en couleur chaude) ;
  - « Transférer » est bien écrit ;
  - les cartes sont sous la barre du haut de TikTok et Reels ;
  - l'offre « 1 semaine gratuite » s'affiche quand elle est dite, et le bouton reste jusqu'à la fin ;
  - le chiffre compte de 1× à 5× pendant qu'elle montre ses 5 doigts : c'est la meilleure idée de la vidéo ;
  - le coin de table en bois a disparu.
- **Ce qui empêche le 8** :
  1. **Une bande noire en haut de l'image (défaut nouveau).** Elle apparaît quand la caméra « descend » pour faire de
     la place à une carte : 0:16,8–0:21, 0:37,3–0:40,6 et 1:04,2 jusqu'à la fin, donc aussi sur l'image finale du
     bouton. Elle fait de 9 à 27 pixels, avec un bord net. Elle n'existait pas dans la version notée 6,5. C'est un
     petit bug, facile à corriger.
  2. **On voit encore que la personne a été ajoutée sur le décor** :
     - son visage est éclairé par la fenêtre du bureau, très clair, alors que le studio est sombre ;
     - un contour clair régulier fait le tour des cheveux et des épaules, comme un autocollant.
     Le studio explique mieux la lumière qu'avant, mais pas encore assez.
  3. **Une faute dans les sous-titres** : « avec de la **publicités** » (0:06,7).
  4. **Une coupe sans changement de cadre** pendant l'appel final (1:07,7) : la tête saute de côté.
  5. **La caméra recule avant chaque carte**, et pendant l'appel final la personne est petite et loin.
- **Par rapport à ta version actuelle (Tech application)** :
  - celle-ci est plus « pub premium » ;
  - les cartes sont justes, avec un vrai bouton et l'offre ;
  - ta version garde le naturel du vrai bureau, mais contient une faute (« éduqué ») et le « 5× MOINS CHER » touche les
    cheveux.
  - **Je conseille de prendre la version qualité après 3 corrections rapides** : la bande noire, « publicités » et la
    coupe de 1:07,7. Elle vaudrait alors environ 7,7.

## Notes

| Vidéo | Note | Commentaire |
| --- | --- | --- |
| **Vidéo 1 - qualité - FINAL (3 h 01, jugée)** | **7,3** | Plafonnée par l'incrustation encore visible. Perd aussi des points pour la bande noire en haut (défaut nouveau), une faute à l'écran et une coupe au même cadre pendant l'appel final. |
| Vidéo 1 - qualité - FINAL (ancien 00h56) | 6,5 | Revue à côté : je confirme la note du juge n° 1. |
| Ta version actuelle (Tech application, images fixes) | ≈ 6 | Naturelle, mais bureau surexposé et encombré, faute « éduqué », « 5× » collé aux cheveux, pas de bouton. |
| Référence (12 s de motion design pur) | — | Autre genre. Les pilules de verre de la vidéo jugée en reprennent bien le langage. |

Détail de la note (sur 10) :

| Partie | Juge n° 1 | Juge n° 2 |
| --- | --- | --- |
| Intégration de l'image | 5,5 | **6,5** |
| Cartes et textes | 6 | **8** |
| Sous-titres | 6 | **8** |
| Montage et rythme | 6,5 | **7** |
| Son | 8 | **8** |
| Message et fin | 6,5 | **7,5** |

Le 7,8 que s'est donné le monteur est un peu généreux. Le 9,4/10 du contrôle automatique ne voit pas la bande noire ni
la faute « publicités » (voir plus bas).

## Ce que j'ai regardé (méthode)

Tout est dans `runtime\cache\tmp\juge2-10020330\`.

- **1 image/s** au milieu de chaque seconde (images exactes 15 + 30k, de 0,5 s à 70,5 s) :
  - vidéo jugée : `pl-final-00.png`, `pl-final-01.png`, `pl-final-02.png` ;
  - ancien export : `pl-old-00.png` à `pl-old-02.png`.
- **5 images/s, pour suivre les mouvements de caméra** : `mvt-0.png`, `mvt-1.png`, `mvt-2.png`.
- **Coupes** : 2 images avant et 3 après chacune des 8 coupes, dans `cuts-a.png` et `cuts-b.png`.
- **Mouvements de caméra, image par image** : `z16-sheet.png` (15,4–17 s), `z37-sheet.png` (36,8–38,8 s),
  `z59-sheet.png` (58,5–61,5 s).
- **Ouverture** : `ouverture.png` (0–1,6 s).
- **Pleine définition**, avec les sous-titres et les cartes : 20 images dans `hd\`, regroupées dans `hd-a.png` et `hd-b.png`.
- **Avant / après, aux mêmes instants** (00h56 contre 03h01) : `avant-apres.png`.
- **Bords du détourage** :
  - cheveux et épaule agrandis 1,5 et 3 fois : `zoom-1270.png`, `zoom3-1270.png` ;
  - mains à 1:1 : `mains.png`.
- **Table** :
  - à 0:12,6, nouvel export contre ancien : `c12-sheet.png` ;
  - à 0:41,6, image par image : `c41-sheet.png`.
- **Entrées des 8 cartes**, 7 images chacune : `entrees.png`.
- **Bande noire du haut** : `bande-haut.png`, éclaircie 2,2 fois à droite pour la rendre visible.
- **Ta version actuelle** :
  - 11 images rendues avec `stills.mjs`, en lecture seule : `planche-user.png` ;
  - 4 images en demi-définition : `user-zoom.png`.
- **Référence** : `runtime\cache\tmp\juge1-10020110\pl-ref-00.png` (4 images/s).
- **Mesures** :
  - son : ebur128 sur les deux exports ; RMS par 50 ms ; écart entre les deux mixages ; recherche de clics aux coupes
    (dérivée seconde à 48 kHz, fenêtres de 2 ms) ;
  - image :
    - haut des cartes et largeur des sous-titres, mesurés sur les pixels ;
    - hauteur de la bande noire, sur les 2126 images ;
    - zoom image par image, par recalage ECC sur la silhouette.
  - temps des pages et des cartes : `infos.mjs` (copie en lecture seule).

## Son (mesuré)

- **Niveaux** : −14,0 LUFS intégré, crête vraie −1,0 dBFS, LRA 3,1 LU. C'est **conforme**, et pareil que l'export
  00h56.
- **Musique et voix** :
  - la parole est à −12 dB RMS (médiane) ;
  - les 18 pauses de plus de 0,2 s sont entre −28 et −37 dB.
  - La musique est donc environ 20 à 25 dB sous la voix, dans la norme. On l'entend dans les pauses, pas sous les mots.
- **Bruitages** : l'écart entre les deux mixages confirme les changements annoncés.
  - Les « whoosh » des coupes franches sont retirés (0:12,6, 0:28,6, 0:41,6, 0:54,4).
  - Deux clics ont été ajoutés, à l'arrivée de l'offre (1:04,45) et du bouton (1:08,8). Ils restent dans l'enveloppe de
    la voix.
- **Coupes** : aucun clic mesuré.
  - À 0:54,47, un souffle d'environ 100 ms (fin de « transférer ») s'éteint en 16 ms sur la coupe. Ce n'est pas un clic,
    mais c'est à écouter.
  - À 0:41,15–0:42,05, il y a 0,9 s de silence sur le changement de prise.
- **Fin** : le dernier mot finit à 1:10,65 et la vidéo à 1:10,87. Il reste 0,2 s, la musique s'arrête net et rien ne
  tient la fin.
- **Limite** : je n'ai pas pu *écouter*. Je ne juge ni le timbre, ni le débruitage, ni le choix de la musique.

## Points forts

1. **Les sous-titres suivent toute la phrase.**
   - Ils restent pendant les notifications, le parcours et l'offre : vu à 0:09,5, 0:26,5, 0:35,5, 0:52,5 et 1:01,5.
   - Ils ne s'effacent que lorsque la carte dit les mêmes mots : la liste de 0:18,5 à 0:20,5, le « 5× » de 0:38 à 0:38,9,
     et « En savoir plus ».
   - Plus aucun bout de phrase orphelin.
2. **Les cartes disent ce que dit la voix**, au mot près :
   - 0:26 : « Lead en attente depuis 3 h », en teinte chaude avec un « ! » rouge ;
   - 0:34,7 : « Répondre → Qualifier » ; 0:51,7 : « Qualifier → Transférer ». La coche se pose sur l'étape 1 quand l'étape 2
     arrive, et la flèche se dessine.
3. **Le compteur 1× → 5×** (0:37,9–0:38,3) tombe exactement sur la main ouverte à 5 doigts. C'est un vrai moment de
   montage.
4. **La fin est construite** :
   - « 1 SEMAINE GRATUITE » arrive à 1:04,45, sur « gratuitement » ;
   - le bouton « En savoir plus → » le rejoint à 1:08,8, sur son mot ;
   - les deux restent jusqu'à la dernière image.
5. **Zone sûre respectée** : le haut des cartes est entre 11,4 et 15,9 % de la hauteur (en comptant la lueur). Les
   sous-titres font au plus 78 % de la largeur (de x = 11 % à 89 %), à 66–72 % de la hauteur.
6. **Coupes** : 7 des 8 coupes changent vraiment la taille du plan (0:12,6, 0:21, 0:23,1, 0:28,7, 0:41,7, 0:45, 0:54,5).
   Les relances sur « concurrent » (0:02,9) et le retour à 0:06,3 sont de vrais « punch ».
7. **Le bois de la table a disparu à 0:12,6.** Un bureau de verre sombre à liseré le remplace, et l'avant-bras passe
   derrière de façon crédible (`c12-sheet.png`).
8. **Le studio vit** : poussières, grille qui glisse, horizon, lueur chaude du côté de la fenêtre. Il n'est plus
   immobile comme avant.
9. **Entrées de cartes soignées** : fondu et léger agrandissement en 0,2 s, avec un reflet de lumière discret. C'est
   cohérent avec la référence.

## Défauts (du plus grave au moins grave)

| # | Moment | Gravité | Problème | Piste de correction |
| --- | --- | --- | --- | --- |
| 1 | 0:16,80–0:21,00 (9 px) ; 0:37,33–0:40,57 (jusqu'à 27 px) ; 1:04,17–1:10,87 (jusqu'à 24 px) | **Important** (défaut nouveau) | **Bande noire à bord net en haut de l'image** pendant 14,1 s, dernière image du bouton comprise. Luminance 6 contre 26–28 pour le fond (`bande-haut.png`). Elle n'existe pas dans l'export 00h56 ; elle est déjà dans celui de 02h42. **Cause** (`design.tsx`, ligne 194) : le calque du décor est décalé de `translateY(dy*.3)` avec `scale(view.bg)` centré à 50 %. Quand la caméra bascule (`view.dy`), son bord haut descend sous le haut de l'image, et le fond `#03060d` du conteneur apparaît. | Faire couvrir le décor quel que soit `dy` : agrandir le calque (`top: -|dy|·0,3`, hauteur H + \|dy\|), ou choisir `bg ≥ 1 + 0,6·\|dy\|/H`, ou limiter le décalage à la marge de `bg`. Ajouter au contrôle une vérification « bord non couvert » : ligne de bord presque noire avec une marche nette sur l'image voisine. |
| 2 | toute la vidéo (bien visible à 0:12,7, 0:50,5, 1:05) | **Important (plafonne la note)** | **L'incrustation se voit encore**, malgré de vrais progrès. Le visage, éclairé chaud par la fenêtre du bureau, est beaucoup plus clair que le studio. Un contour clair de 2–3 px, de même force partout, fait le tour des cheveux, de l'oreille et des épaules, des **deux** côtés : un effet d'autocollant (`zoom3-1270.png`). Les bras s'éteignent dans le noir en bas, sans contact ni ombre au sol. | Contour seulement du côté opposé à la lumière, plus fin (1–1,5 px), plus faible sur les cheveux, et dosé selon la douceur de l'alpha. Ajouter un vrai « light wrap » : le décor flouté qui déborde de 6 à 10 px sur le bord, à 15–25 %. Baisser un peu l'exposition de la peau (−0,2 à −0,3 IL) et teinter les noirs vers le bleu du studio. Ombre douce au sol. La vraie solution reste de filmer devant un fond sombre. |
| 3 | 0:06,70–0:07,94 | **Moyen** | **Faute à l'écran** : « leads avec de la » / « **publicités**, ça vous concerne ». Après « de la », il faut le singulier. La relecture d'orthographe et le contrôle ne l'ont pas vue. | Règle d'accord déterminant / nom (« de la », « la », « une » + nom au pluriel → singulier quand le nom est connu). Ajouter ce cas aux tests de `orthographe.py` et à la vérification d'orthographe du contrôle. |
| 4 | 1:07,73 | **Moyen** | **Coupe au même cadre pendant l'appel final** : la taille ne change presque pas (× ≈ 1,07 selon le contrôle). La tête saute de la gauche vers le centre (`cuts-b.png`, dernière ligne). C'est le seul vrai « saut » qui reste, et il tombe au moment le plus important. | Appliquer la règle × 1,2 même quand le badge d'offre est à l'image, avec le plan serré ancré sous le badge. Sinon, fondre la coupe dans une poussée de 0,3 s. |
| 5 | 0:16,0–0:16,9 ; 0:25,6–0:25,9 ; 0:58,8–0:59,6 ; 1:03,8–1:04,4 | **Moyen** | **La caméra recule avant chaque carte** : × 0,80 en 0,8 s à 0:16 (en plein « veut dire un salaire »), × 0,83 à 0:59. Le geste devient mécanique (« la personne rapetisse, une carte arrive »). Surtout, pendant l'appel final, la personne est petite et loin : à 1:05, le haut de la tête est à 38 % de la hauteur, avec une bande vide de 18 à 38 % sous le badge. La version 00h56 était plus proche à ce moment (`avant-apres.png`). | Faire le recadrage sur la coupe la plus proche si elle est à moins de 1,5 s ; sinon, recul limité à × 0,9 et plus lent (1,2 s). Pendant l'appel final, garder un plan moyen serré : le badge et le bouton tiennent dans 0,11–0,26 H, la tête peut commencer juste dessous. |
| 6 | 0:00–0:02,9 | **Moyen** | **Ouverture encore plate** : la première image (la miniature) est un plan moyen sans texte ni graphisme. La poussée d'ouverture (× 1,11 en 0,9 s) et le balayage de lumière se voient à peine (`ouverture.png`). La première carte n'arrive qu'à 0:09,3. | Mot clé dit (« concurrent ») en texte animé à 0:02,9. Ou ouvrir serré (× 1,3) puis reculer, avec un vrai son d'ouverture à 0:00. La première image doit arrêter le pouce. |
| 7 | 0:41,67–0:41,77 (4 images) | Mineur | **Avant-bras coupé en pointe** par une diagonale juste après la coupe (plan c4, où la table n'a pas été trouvée) (`c41-sheet.png`). | Si l'alpha montre un bord droit en bas à gauche sans table trouvée : fondre ce coin dans un dégradé sombre ; ou commencer le plan c4 plus serré pendant 0,3 s ; ou poser le bureau sur la droite mesurée dans l'alpha. |
| 8 | 0:41,87–0:41,93 ; 0:29,5 ; 0:32 | Mineur | **Doigts fantômes** sur les gestes rapides : main semi-transparente sur le pull. | Sur les mains en mouvement rapide, garder le maximum de l'alpha sur ± 1 image, ou reprendre la prise d'origine dans cette zone. |
| 9 | 0:15,07–0:16,23 ; 0:40,42–0:41,79 | Mineur | **Pages mal coupées** : la virgule disparaît dans « pour régler ça ça », qui ressemble à un bégaiement. « avoir à gérer quoi » / « que ce soit » coupe « quoi que ce soit » en deux. | Couper les pages sur la ponctuation (après « ça, ») et garder ensemble les expressions figées (« quoi que ce soit », « à temps plein »). |
| 10 | 0:26,39–0:27,33 | Mineur | **« trois heures »** en cyan sur le pull brun et les mains : contraste 2,3:1 (conseil du contrôle, confirmé). | Mot clé en blanc avec soulignement de couleur, ou teinte chaude assortie à la carte du problème, avec un contour plus sombre. |
| 11 | 0:41,7–0:51,7 | Mineur | **10 s sans aucune carte.** C'est voulu (« preuve humaine »), mais c'est long pour une pub, après un début déjà sans carte jusqu'à 0:09,3. | Un seul élément léger sur des mots dits, par exemple « Formé par nos soins ✓ » à 0:45,2. |
| 12 | 0:16,95–0:18,10 | Mineur | **« Salaire » seul en haut à gauche** pendant 1,1 s : la place finale est réservée, donc la première pilule est décentrée. Le texte des pilules est petit (≈ 36 px). | Centrer la rangée au fur et à mesure (glissement doux), ou empiler les éléments au centre. |
| 13 | 1:10,65–1:10,87 | Mineur | **Fin sèche** : 0,2 s après le dernier mot, la musique s'arrête net. Le bouton, lui, est bien gardé. | 0,6 à 1 s de tenue (musique et bouton), ou une fin qui boucle proprement. |

Je n'ai trouvé **aucun texte interne** (nom de fichier, identifiant, consigne), **aucun texte illisible** et **aucun
problème de niveau sonore**. Les effets (reflet sur les cartes, lueur chaude à gauche, horizon) ont tous une raison et
restent discrets.

## Suivi des 15 défauts du juge n° 1

| # juge 1 | Défaut | État | Ce que j'ai vu |
| --- | --- | --- | --- |
| 1 | Sous-titres retirés pendant les cartes | **Corrigé** | Seules les pages répétées par la carte sont masquées (liste, 5×, « En savoir plus »). |
| 2 | Carte à contresens à 0:26 | **Corrigé** | « Lead en attente depuis 3 h », teinte chaude, « ! ». |
| 3 | « Transférez » | **Corrigé** | « Qualifier → Transférer », sous-titre « le transférer ». |
| 4 | Cartes dans la zone cachée du haut | **Corrigé** | Haut des cartes à 11,4–15,9 % de la hauteur. |
| 5 | Incrustation visible | **Partiel** | Lumière chaude motivée, contour, décor animé. Mais contour en autocollant et peau trop claire pour le studio (défaut 2). |
| 6 | Table du bureau | **Partiel** | 0:12,6 corrigé (bureau de verre) ; 0:41,67 reste 4 images (défaut 7). |
| 7 | Textes faux recopiés de la transcription | **Corrigé** | Pour les mots cités (« appuyez », « Puis », « closés », « 5× »). Une faute nouvelle repérée : « publicités » (défaut 3). |
| 8 | Coupes au même cadre | **Partiel** | 0:21, 0:28,7 et 0:54,5 corrigés ; 1:07,7 reste (défaut 4). |
| 9 | Accroche plate | **Partiel** | Poussée de 0,9 s, peu visible (défaut 6). |
| 10 | Offre tardive | **Corrigé** | Badge à 1:04,45, sur « gratuitement ». |
| 11 | Fin sèche | **Partiel** | Bouton gardé jusqu'au bout, mais toujours 0,2 s de fin (défaut 13). |
| 12 | Sous-titres trop larges | **Corrigé** | 78 % au plus. |
| 13 | Animations simples | **Corrigé** | Compteur, coche et flèche du parcours, reflet. |
| 14 | Doigts fantômes | **Non corrigé** | Défaut 8. |
| 15 | Whoosh sur des coupes franches | **Corrigé** | Mesuré dans l'écart entre les mixages. |

**Défauts nouveaux de ce cycle** :
- la bande noire du haut (défaut 1), qui vient de la nouvelle bascule de caméra ;
- les reculs de caméra avant les cartes (défaut 5) ;
- la faute « publicités » : elle existait déjà, mais personne ne l'avait vue.

## Ce que le contrôle automatique n'a pas vu (9,4/10)

Ses deux conseils sont justes : le contraste de « trois heures » et la coupe de 1:07,7. En revanche, il **manque** :
- la bande noire en haut, pendant 14 s, dernière image comprise ;
- la faute « de la publicités » ;
- les reculs de caméra répétés et l'appel final en plan trop large ;
- le bras coupé en diagonale à 0:41,67 ;
- l'effet d'autocollant du contour, qu'il compte comme une lumière motivée.

Sans la bande noire et la faute, sa note de 9,4 serait proche de la vérité pour ce qu'il mesure. Mais il ne juge pas
l'intégration de l'image, qui est ce qui coûte le plus de points.

## Comparaison détaillée

- **Avec l'export 00h56 (note 6,5)** :
  - progrès sur tout ce qui se lit : sous-titres, cartes, orthographe, offre, bouton, zone sûre ;
  - progrès sur le décor (lumière, mouvement, table à 0:12,6) ;
  - recul sur deux points : la bande noire et l'appel final, filmé plus large qu'avant.
  - **Net progrès d'environ +0,8.**
- **Avec ta version actuelle (Tech application)** :
  - **la version qualité gagne** sur :
    - le message : la carte « 3 h » est la même, mais il y a en plus la liste, le parcours, le 5× qui compte, l'offre et
      le bouton ;
    - la lisibilité et l'image de marque ;
    - l'orthographe : ta version garde « éduqué » et « appuyer ».
  - **ta version gagne** sur le naturel : vrai lieu, aucun bord de détourage ;
  - **elle perd** sur :
    - l'exposition (fenêtre et mur brûlés) ;
    - le fouillis (chaises, table) ;
    - le « 5× MOINS CHER » posé sur les cheveux ;
    - l'appel final : un simple mot en couleur, sans bouton.
- **Avec la référence** : ce n'est pas le même genre (12 s de motion design pur, un changement toutes les
  0,25–0,5 s). La vidéo jugée reprend maintenant la *matière* de la référence (pilules de verre à liseré, lueurs) et une
  partie de sa *vie* (compteur, coche qui se pose, reflet). Elle n'en a pas la densité, ce qui est normal pour une pub
  face caméra de 71 s.

## Ordre de correction conseillé

1. **Bande noire du haut** (défaut 1) : une ligne dans `design.tsx` et une vérification de plus dans le contrôle.
   C'est le plus rapide et le plus visible pour un client.
2. **« publicités »** (défaut 3) : une règle d'accord et un test.
3. **Coupe de 1:07,7 et appel final trop large** (défauts 4 et 5) : garder la personne proche pendant l'offre et le
   bouton.
4. **Contour et « light wrap »** (défaut 2) : c'est ce qui sépare 7,5 de 8.
5. Le reste (défauts 6 à 13) : des finitions.

Après les points 1 à 3 : ≈ 7,7. Après le point 4 en plus : ≈ 8. Toutes ces corrections sont générales et profitent aux
autres vidéos du style Tech 3D.

## Limites de ce jugement

- Je n'ai pas *écouté* la vidéo : le son est jugé sur des mesures seulement.
- Ta version Tech application est jugée sur 11 images fixes, pas sur un export.
- Je n'ai relancé ni les tests ni le contrôle : aucun code n'a été modifié pendant ce jugement.
