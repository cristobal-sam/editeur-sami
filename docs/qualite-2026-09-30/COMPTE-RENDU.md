# Compte rendu — ronde 3 : Vidéo 1 en qualité professionnelle (2 octobre 2026, mis à jour après le juge n° 3)

## En bref (dernier état, 2 octobre vers 7 h — finition après le juge n° 3)

- **La vidéo finale est ici** : `livraisons\Lot 2026-09-30 10h51\Vidéo 1 - qualité - FINAL.mp4`
  (export de 6 h 58 : 71,47 s, 1080 × 1920, son à −14 LUFS, crête −1 dB, écart de volume 3,1 LU).
- **Ta vidéo à toi n'a pas été touchée** (toujours « Tech application », fichier inchangé). Tout le travail est dans la version
  « Vidéo 1 - script › qualité ». Une copie a été gardée avant les changements (onglet Versions : « avant finition ronde 3bis 2 oct »).
- **Les anciens exports sont gardés** à côté : `(ancien 2026-10-02 04h52)` est celui qu'a noté le juge n° 3 (7,6/10) ;
  `(… 06h22)` et `(… 06h39)` sont mes essais de ce cycle (le 2e est presque identique au final).
- **Notes** :

| | Avant (export 4 h 52) | Après (export 6 h 58) |
| --- | --- | --- |
| Juge indépendant | **7,6 / 10** | pas encore rejugée |
| Mon jugement de monteur | ≈ 7,9 annoncé (le juge a dit 7,6) | **≈ 8 / 10** (prudent : voir « Ce qui reste ») |
| Contrôle automatique de la vidéo | 10 / 10 (mais il ratait 6 défauts) | **10 / 10**, avec 5 vérifications de plus qui auraient vu ces défauts |

### Les 8 défauts du juge n° 3 et ce que j'ai fait (tout est général : toutes tes vidéos en profitent)

1. **Bande blanche le long de la joue, oreilles « fondues »** (pendant l'offre). → Le détourage reconnaît maintenant un **décor clair**
   (mur blanc, fenêtre) : tout près du bord, il compare chaque pixel à la couleur du mur et à celle de la peau voisine.
   - le mur resté collé au bord est retiré (frange de quelques pixels) ;
   - le blanc pris **dans** la silhouette (entre l'oreille et la joue, sous la mâchoire, peau brûlée par la fenêtre) prend la teinte
     de la peau voisine au lieu de rester blanc-bleu (le retirer aurait ouvert une fente sombre) ;
   - l'or des boucles d'oreilles garde sa vraie couleur (avant : remplacé par la peau → taches beiges) ;
   - jamais les yeux ni les dents (blancs eux aussi) ; rien ne change sur un décor sombre.
   - Mesuré : la part de bord de tête « claire et neutre » passe de **1,5–3,7 %** (selon le plan) à **0,1–0,5 %**.
2. **Quatre sauts d'image sans coupe** (0:25,6, 0:36,6, 0:40,4, 1:03,7). → La caméra ne change plus de cadre sur un simple début de
   phrase. Pour laisser la place à une carte, elle bascule :
   - sur une coupe proche (jusqu'à 3 s avant la carte : invisible) ;
   - sinon sur l'image où la carte entre, avec son whoosh (la carte « pousse » la personne) ;
   - et si seule la hauteur change, en glissement lent et adouci (0,8 s pour 3 % de l'image).
   - Mesuré sur la vidéo : les 4 sauts ont disparu (seuls restent les 8 coupes et les vrais changements de plan × 1,2).
3. **Mots en couleur qui touchent leur voisin**. → Le mot « frappe » toujours, mais sans déborder : il grandit au plus de ce que permet
   sa longueur (jamais plus d'un tiers de l'espace avec son voisin), sans rebond (l'espace ne s'élargit plus), avec un léger saut vers
   le haut et une lueur plus forte. Vérifié image par image : « concurrent le », « au téléphone », « gratuitement dans » ne se touchent plus.
4. **Le bouton « En savoir plus » s'en allait puis revenait**. → **Un seul bouton**, de la 1re demande (0:59,8) jusqu'à la dernière image ;
   « 1 SEMAINE GRATUITE » se pose au-dessus quand elle est dite (1:04,45), avec un petit clic. Sa place est gardée dès le début : le
   bouton ne bouge pas. Le haut de l'image n'est plus jamais vide à la fin.
5. **Sous-titre éclair de 0,2 s** (0:34,5). → Une page n'est jamais montrée moins de 0,6 s en partie : soit entière, soit masquée.
   Et une carte qui redit la page entre **avec** elle (le parcours « Répondre → Qualifier » arrive maintenant sur « pour répondre »).
   Quand une page s'efface pour une carte, c'est un fondu de 3 images, jamais une coupure.
6. **« Elle rapetisse, puis une carte arrive »** (0:16,0 et 0:58,9). → L'élargissement se fait sur l'image même où la carte entre
   (0:16,97 et 0:59,83), et non plus 1 s avant.
7. **Doigts transparents sur les gestes rapides**. → Amélioré : là où les doigts sont flous de bouger (couleur de peau, bord très
   large), le détourage les rend plus opaques (environ 50 % → 80 %). Le flou lui-même vient de la prise (voir « Ce qui reste »).
8. **Apostrophes mélangées**. → Une seule apostrophe à l'image, la courbe « ’ », dans les sous-titres, les cartes, le bouton et les
   chiffres (le texte enregistré ne change pas).

En plus : les pages de sous-titres ne finissent plus sur « c’est », « un vrai », « bien », « chaque », « qu’on », « parce »
(« on a un vrai intérêt » | « à bien qualifier »).

### Le contrôle automatique voit maintenant ces défauts

Nouvelles vérifications : **saut d'image sans coupe**, **sous-titre éclair** (moins de 0,3 s), **bouton qui s'en va et revient**,
**apostrophes mélangées**, **bande claire au bord de la tête** (passe vidéo). Essayées sur l'ancienne version : elles trouvent les 4
sauts aux bons instants, l'éclair de 0:34,5, le bouton qui revient et les apostrophes. Sur la nouvelle : rien.

### Ce que j'ai regardé (preuves)

Tout est dans `runtime\cache\tmp\finition3bis-10020535\` :
- **export final (6 h 58), 1 image par seconde** : `final2\planche-00.png` (0–35 s), `final2\planche-01.png` (36–71 s) ; instants
  jugés (0:02,9, 0:16,97, 0:25,7, 0:34,5, 0:38,3, 0:40,5, 0:59,9, 1:03,75, 1:04,8, 1:06,7, 1:11,4) : `final2\cles.png` ; joue pendant
  l'offre : `final2\joue.png` ; apostrophes : `final2\apostrophes.png` ; les gros plans ci-dessous viennent de l'essai de 6 h 39
  (même rendu) ;
- **joue et oreilles pendant l'offre** (1:04,5 à 1:07,5) : `final\joue-offre.png` ; avant / après au même instant : `cmp-joue2.png` ;
  détourage seul, avant / après : `m-offre.png` (joue), `m-c1tete.png` (cheveux, rien d'abîmé) ;
- **bouton unique** (0:59,8 → 1:11,4) : `final\cta.png` ;
- **mots qui frappent** (0:02,9, 0:44,5, 1:04,5) : `final\pop.png` et `e1\pop.png` (image par image) ;
- **liste, sauts supprimés, sous-titre éclair** : `final\liste-flash.png`, `e1\flash.png` ;
- **main à 0:38,3, glissement 0:36,5–0:37,9, 0:40,4, 0:41,8, 0:12,7** : `final\divers.png`, `cmp-main.png` ;
- **sauts mesurés sur les deux vidéos** : `sauts.py` (ancienne : 4 sauts sans coupe ; nouvelle : aucun) ;
- rapport du contrôle : `runtime\cache\controle\script1-script-qualite\export-9x16\controle.txt`.

### Vérifié sur d'autres styles (aucune casse)

Copie figée de Vidéo 1, contrôle du montage avec le code d'**avant** puis d'**après** ce cycle (même procédure) :

| Style | Avant | Après |
| --- | --- | --- |
| Ta version telle quelle (Tech application) | 7,7 | 7,7 |
| Tech application (style réappliqué) | 7,5 | 7,5 |
| Éditorial cinétique | 4,8 | 4,8 |
| Hormozi | 4,9 | 4,9 |

Mêmes constats exactement. (Ces notes sont plus basses que celles des cycles d'avant parce que la copie figée garde son ancien
détourage et ses mots non relus : c'est la comparaison avant / après qui compte.) Ce qui change pour **tous** les styles sans que ton
fichier change : l'apostrophe courbe et un découpage des sous-titres un peu meilleur (par ex. « on a un vrai » | « intérêt à bien »
devient « un vrai intérêt » | « à bien qualifier »).

### Ce qui reste (honnêtement)

- **Limite de la prise** : la personne a été filmée devant un mur blanc, éclairée par une fenêtre. Le bord de la tête est maintenant
  propre, mais le côté du visage reste très clair (peau brûlée par la fenêtre) et le détail des oreilles est perdu dans la prise
  elle-même. Pour un rendu parfait : fond plus sombre, lumière douce de face.
- **Doigts** : plus opaques, mais toujours **flous** sur les gestes très rapides (0:38,3) : c'est le flou de bouger de la caméra
  (vitesse d'obturation), on ne peut pas inventer des doigts nets.
- **Fin** : de 0:59,8 à 1:07,7, plan moyen (la caméra garde la place du bouton et de l'offre) ; plan serré ensuite jusqu'à la fin.
- **0:34,5** : 0,2 s sans sous-titre juste avant que le parcours apparaisse (fondu) — beaucoup moins visible qu'un éclair.
- Le mot qui frappe est plus discret qu'avant (c'est le prix pour ne plus toucher le voisin).
- **Pas de plans de coupe** (`media\broll` vide) ; une seule caméra.

### Relecture après ce cycle (2 octobre, vers 8 h)

J'ai revu l'export de 6 h 58 image par image aux instants jugés, à côté de l'export de 4 h 52 : les 8 corrections se voient.
Trois petites règles ont été ajoutées pour les prochaines vidéos (la vidéo finale n'a pas besoin d'être refaite) :
- un bouton que tu as retouché (par exemple un autre texte) n'est jamais caché par le bouton unique posé au même moment ;
- une carte avancée pour arriver avec sa phrase garde son heure de fin, et elle n'est jamais avancée contre la carte d'avant ;
- l'apostrophe courbe « ’ » aussi dans le bandeau du haut, le titre du style Documentaire et les sous-titres des cartes.

---

# Cycle 3 : après le juge n° 2 (2 octobre, vers 5 h)

> Historique. La vidéo dont parle cette partie s'appelle maintenant `Vidéo 1 - qualité - FINAL (ancien 2026-10-02 04h52).mp4`
> (c'est celle qu'a notée le juge n° 3 : 7,6/10).

## En bref (état du cycle 3, 2 octobre vers 5 h)

- **La vidéo finale est ici** : `livraisons\Lot 2026-09-30 10h51\Vidéo 1 - qualité - FINAL.mp4`
  (export de 4 h 52 : 71,5 s, 1080 × 1920, son à −14 LUFS, crête −1 dB, écart de volume 3,1 LU).
- **Ta vidéo à toi n'a pas été touchée** (toujours « Tech application », fichier inchangé). Tout le travail est dans la version
  « Vidéo 1 - script › qualité ». Une copie a été gardée avant les changements (onglet Versions : « avant corrections du juge 2 »).
- **Les anciens exports sont gardés** à côté, avec la date dans le nom : `(ancien 2026-10-02 03h01)` est celui qu'a noté le juge
  n° 2 ; `(… 04h35)` et `(… 04h44)` sont mes essais de ce cycle.
- **Notes** :

| | Avant (export 3 h 01) | Après (export 4 h 52) |
| --- | --- | --- |
| Juge indépendant | **7,3 / 10** | pas encore rejugée |
| Mon jugement de monteur, comparé à la référence | 7,8 annoncé (le juge a dit 7,3) | **≈ 7,9 / 10** (je reste prudent) |
| Contrôle automatique de la vidéo | 9,4 / 10 (2 conseils) | **10 / 10** (aucun constat) |

  Le contrôle est encore plus sévère qu'avant (bande au bord, caméra qui recule, fautes d'accord) et ne trouve plus rien. Mais il
  ne juge pas « l'incrustation » (la personne posée sur le décor) : c'est ce qui me fait garder ≈ 7,9 et pas plus.

## Ce que le juge n° 2 a reproché (7,3/10) et ce que j'ai corrigé

Toutes les corrections sont **générales** (elles servent à toutes tes vidéos en style Tech 3D, et certaines à tous les styles).

1. **Bande noire en haut de l'image pendant 14 s** (quand la caméra « descend » pour laisser la place à une carte). → Le décor est
   maintenant toujours assez grand pour couvrir le cadre. Mesuré sur toutes les images de la vidéo : **0 s** de bande (avant :
   13,8 s, jusqu'à 28 px). Le contrôle automatique sait maintenant la repérer.
2. **On voyait que la personne était « collée » sur le décor** (contour clair tout autour, peau très claire). →
   - le contour lumineux est **fin et d'un seul côté** (celui opposé à la lumière), presque rien sur le haut des cheveux ;
   - le **bord est nettoyé** : la couleur du mur blanc du bureau, mêlée aux cheveux et au bord du visage, est remplacée par celle
     de la personne ;
   - la **peau éclairée par la fenêtre est adoucie** (environ −0,2 à −0,25 IL dans les parties claires) et les noirs prennent un peu
     du bleu du studio ;
   - la lumière chaude du studio éclaire aussi **le mur juste derrière elle**, du côté de la fenêtre : la joue claire ne se détache
     plus sur du noir ;
   - un **grain léger** sur toute l'image donne la même texture à la personne et au décor ;
   - le bas de l'image est moins noir : le buste ne « s'éteint » plus dans le noir.
3. **Faute « avec de la publicités »**. → Nouvelle règle : le nom s'accorde avec son déterminant (« de la publicité », « chaque
   lead », « vos leads »). Elle ne touche jamais un pronom (« tu la prends »), un mot invariable (« le temps ») ni un nombre. Le
   contrôle la vérifie aussi.
4. **Coupe au même cadre à 1:07,7** (pendant l'appel final). → Quand une coupe ne change pas assez la taille de la personne (elle
   a reculé dans la prise), le plan serré est poussé un peu plus : mesuré **× 1,15**, la tête reste juste sous l'offre.
5. **La caméra reculait avant chaque carte** (la personne rapetissait, puis une carte arrivait) et l'appel final était filmé
   loin. →
   - le changement de cadre se fait **d'un coup**, sur une coupe proche ou sur un début de phrase (comme une deuxième caméra),
     plus jamais en glissant ;
   - pendant une carte, la caméra **garde son plan** et la personne descend juste sous la carte, au lieu de reculer ;
   - le **haut de la tête est maintenant mesuré** dans le détourage (avant, il était estimé, jusqu'à 5 % trop haut) : pendant
     l'appel final, la tête est à 33 % de la hauteur au lieu de 38 %, et la personne est plus grande ; les 3,7 dernières secondes
     (avec le bouton) sont en plan serré.
6. **Ouverture plate**. → La **1re image** (la miniature) est **serrée sur le visage** et montre déjà le premier sous-titre ; la
   caméra recule ensuite en 0,9 s (un mouvement qui se voit) ; le mot fort (« concurrent ») « frappe » quand il est dit.
7. **Avant-bras coupé en pointe à 0:41,7**. → Le moteur reconnaît la table de cette prise (même bord que dans les autres prises,
   alors que la caméra du téléphone a bougé) et la suit image par image : le bureau de verre du studio y est posé.
8. **Sous-titres mal coupés** (« pour régler ça ça », « quoi | que ce soit »). → Nouveau découpage des pages : coupure après la
   virgule (« pour régler ça, » | « ça veut dire »), expressions gardées entières (« quoi que ce soit », « à temps plein »), jamais
   une page qui finit sur « de », « des », « à », « et », jamais une page qui ne dure qu'un éclair ; la virgule reste affichée au
   milieu d'une page.
9. **« trois heures » peu lisible** (bleu sur le pull brun). → Un halo sombre serré entoure les mots en couleur.
10. **10 s sans carte (0:41,7 à 0:51,7)**. → Un badge de preuve **« ✓ Formé par nos soins »** apparaît quand elle le dit (0:45,9 à
    0:48,5). Règle générale : seulement sur une promesse dite en quelques mots (« sans engagement », « formé par nos soins »…).
11. **« Salaire » seul dans un coin**. → La rangée de pilules se recentre à mesure qu'elles arrivent. Un badge seul est plus grand.
12. **Fin sèche** (la musique s'arrêtait 0,2 s après le dernier mot). → La dernière prise continue **0,8 s** après le dernier mot
    (si personne n'y parle) : elle sourit, le bouton et la musique tiennent.
13. **Le contrôle ne voyait pas tout**. → Nouvelles vérifications : bande sombre au bord de l'image, caméra qui recule en glissant
    plusieurs fois ; il ne compte plus un faux « visage » détecté sur le pull.

## Ce que j'ai regardé (preuves)

Tout est dans `runtime\cache\tmp\cycle3-10020500\` :
- **export final, 1 image par seconde** : `final3\planche-00.png`, `final3\planche-01.png`, `final3\planche-02.png` ;
- **images clés en pleine définition** (1re image, ouverture, liste, compteur 2× → 5×, badge, coupe de 1:07,7, bouton, dernière
  image) : `final3\hd-grille.png` ;
- **avant / après** sur les bords (cheveux à 0:12,7, joue et oreille à 1:05) : `final\avant-apres-bords.png`, `s5\oreille.png` ;
  avant-bras à 0:41,7 et « trois heures » : `final\details.png` ; lumière sur le mur et grain : `s7\mur.png`, `s7\grain.png` ;
- **aperçus courts à 5 images par seconde** (ouverture, liste, fin) : `apercu\A-ouverture-planche.png`,
  `apercu\B-liste-planche.png`, `apercu\C-fin-planche.png` ;
- **autres styles** avec le nouveau code : `generalite\grille.png` ;
- **mesures** : bande au bord sur toutes les images et niveau sonore (`mesures.py`) ; rapport du contrôle :
  `runtime\cache\controle\script1-script-qualite\export-9x16\controle.txt`.

## Vérifié sur d'autres styles (aucune casse)

Copie figée de Vidéo 1, contrôle du montage avec le code d'**avant** puis d'**après** ce cycle :

| Style | Avant | Après | Commentaire |
| --- | --- | --- | --- |
| Tech application (ton style) | 8,1 | 8,1 | identique ; images regardées : rendu normal |
| Éditorial cinétique | 6,4 | 6,4 | identique ; images regardées : rendu normal |
| Hormozi | 4,9 | 4,9 | visage couvert par les sous-titres moins longtemps (8,9 s → 5,1 s) grâce au nouveau découpage |

Ce qui change pour **tous** les styles (ton style Tech application compris, sans que ton fichier change) : le nouveau découpage des
sous-titres (virgules, expressions entières, pas de page qui finit sur « de » ou « à ») et la règle d'accord pour les nouveaux
montages. Le reste (caméra, détourage, grain, badge, fin tenue) ne concerne que le style Tech 3D ; la fin tenue sert aussi à tout
nouveau montage.

## Ce qui reste (honnêtement)

- **L'incrustation se voit encore un peu** : le bord de l'oreille et des boucles d'oreilles reste irrégulier (limite du
  détourage), et la peau est éclairée par une fenêtre alors que le studio est sombre. Pour un résultat parfait : filmer devant un
  fond sombre ou neutre, avec une lumière douce.
- **Doigts un peu flous / transparents** sur les gestes très rapides (flou de bouger de la prise).
- **Début de l'offre (1:04,5 à 1:07,7)** : plan moyen, parce que la place du bouton qui arrive ensuite est gardée au-dessus de la
  tête. Le plan devient serré à 1:07,7 jusqu'à la fin.
- **Coupe de 0:41,7** : la taille change de × 1,13 seulement (deux prises différentes ; la tête touche déjà le haut, impossible de
  serrer plus).
- **Pas de plans de coupe** (`media\broll` vide) ; une seule caméra. La référence est du pur motion design.
- Le **contrôle automatique** donne 10/10, mais il ne juge pas l'intégration de l'image : le juge indépendant doit encore la revoir.
- Ta version Tech application garde ses mots tels quels. Pour lui appliquer la relecture d'orthographe si tu veux (depuis
  `engine\`) : `python -m editeur orthographe ..\projects\script1 --reel script --appliquer`.

---

# Cycle 2 : après le juge n° 1 (2 octobre, vers 3 h)

> Historique. La vidéo dont parle cette partie s'appelle maintenant `Vidéo 1 - qualité - FINAL (ancien 2026-10-02 03h01).mp4`
> (c'est celle qu'a notée le juge n° 2 : 7,3/10 ; mon « ≈ 7,8 » ci-dessous était un peu généreux).

## En bref (état du cycle 2, 2 octobre vers 3 h)

- **La vidéo finale est ici** : `livraisons\Lot 2026-09-30 10h51\Vidéo 1 - qualité - FINAL.mp4`
  (export de 3 h 01 : 70,9 s, 1080 × 1920, son à −14 LUFS, crête −1 dB, écart de volume 3,1 LU).
- **Ta vidéo à toi n'a pas été touchée** (toujours « Tech application », fichier inchangé). Tout le travail est dans la version
  « Vidéo 1 - script › qualité » (`projects\script1\reels\script-qualite.json`). Une copie a été gardée avant chaque changement
  (onglet Versions : « avant corrections du juge 1 (2 oct.) », puis « avant le style produit-3d »).
- **Les anciens exports sont gardés** à côté, avec la date dans le nom : `… FINAL (ancien 2026-10-02 00h06).mp4`,
  `(… 00h56)` (celui qu'a noté le juge), `(… 02h35)` et `(… 02h42)` (mes essais de ce cycle).
- **Notes** :

| | Avant (export 00 h 56) | Après (export 3 h 01) |
| --- | --- | --- |
| Juge indépendant | **6,5 / 10** | pas encore rejugée |
| Mon jugement de monteur, comparé à la référence | 8 annoncé (trop généreux) | **≈ 7,8 / 10** |
| Contrôle automatique de la vidéo | 8,8 / 10 | **9,4 / 10** (0 bloquant, 0 important, 2 conseils) |

  Le contrôle est plus sévère qu'avant (5 vérifications en plus) et sa note monte quand même : les défauts qu'il ne voyait pas
  sont corrigés. Mon 7,8 reste en dessous : l'incrustation se voit encore pour un œil exercé (voir « Ce qui reste »).

## Ce que le juge a reproché (6,5/10) et ce que j'ai corrigé

Toutes les corrections sont **générales** (elles servent à toutes tes vidéos), pas des retouches à la main de Vidéo 1.

1. **Les sous-titres disparaissaient pendant chaque carte** (un tiers de la parole sans texte). → Ils **restent** maintenant :
   les cartes sont en haut, le texte en bas. Une page s'efface seulement si la carte **dit les mêmes mots** (la liste « salaire,
   avantages sociaux… », le bouton « En savoir plus », le « 5× moins cher »). Plus aucun bout de phrase perdu. Ton style Tech
   application en profite aussi (texte gardé pendant les notifications).
2. **Faute dans une carte** (« Qualifier → Transférez »). → Nouvelle **relecture d'orthographe** des mots transcrits, sans
   toucher à leur minutage : « transférer », « éduquer », « appuyez sur le bouton » (dit à « vous »), « vos leads sont
   closés », « Puis là » (au lieu de « Pi »), « Alors » en début de phrase. Les étapes d'un parcours sont toujours à
   l'infinitif. Elle passe sur chaque nouveau montage ; jamais sur un plan verrouillé ni sur tes retouches.
3. **Carte à contresens à 0:26** (« Lead / Appelé ✓ » en bleu pendant le problème). → La carte dit maintenant le fait dit
   dans la phrase : **« Lead en attente depuis 3 h »**, en **teinte chaude** avec un « ! ». Règle générale : un problème vécu
   n'a jamais une coche de succès.
4. **Cartes sous la barre du haut de TikTok / Reels** (98 à 150 px du bord). → Le haut de toute carte est à **12 % au moins**
   (230 px). Quand la place manque, la caméra « bascule » doucement (la personne descend un peu) au lieu de coller la carte
   au bord.
5. **Incrustation visible** (peau chaude de la fenêtre sur un studio froid et immobile, buste qui flotte). → Le studio
   **explique** maintenant la lumière : une lumière chaude du même côté que la fenêtre (mesurée sur le visage), un contour froid
   du côté opposé (cheveux, épaule), une ligne d'horizon derrière la personne, des poussières de lumière qui montent
   lentement, une grille qui glisse et un balayage de lumière (plus franc à l'ouverture).
6. **La table du bureau trahissait le détourage** (coin de bois sous la main à 0:12,6, bras coupé en diagonale). → Le moteur
   **repère la table** dans le détourage (le bras s'arrête toujours sur la même droite nette) et le studio y pose un **bureau
   de verre noir au premier plan** : le bras passe derrière, comme dans la vraie prise ; le bois a disparu. Trouvée sur 3 plans
   sur 5 (voir « Ce qui reste »).
7. **Textes faux recopiés de la transcription** (« appuyer », « Pi », « closé ») → corrigés (point 2). **« ×5 MOINS CHER »**
   se lisait « multiplié par 5 » → **« 5× MOINS CHER »**, et le chiffre **compte de 1× à 5×**.
8. **Coupes au même cadre** et relances trop faibles (× 1,10). → À **chaque coupe**, la taille de la personne à l'écran change
   d'au moins × 1,14 (mesuré : 1,14 à 1,31), même quand une carte est à l'image (le plan serré est alors « ancré » sous la
   tête pour ne pas toucher la carte). Une carte qui finirait juste après une coupe sort sur la coupe.
9. **Accroche visuelle plate**. → La caméra **arrive sur le visage dès la première image** (poussée de 0,9 s) avec un balayage
   de lumière d'ouverture, puis relance sur « concurrent ».
10. **L'offre arrivait tard**. → Le badge **« 1 SEMAINE GRATUITE »** apparaît **quand elle est dite** (« gratuitement »,
    1:04,5) ; le bouton « En savoir plus » le rejoint sur son mot (1:08,8), avec un petit clic.
11. **Fin sèche** (bouton à moitié effacé). → Le bouton et l'offre restent **jusqu'à la dernière image**.
12. **Sous-titres trop larges** (jusqu'à 92 % : la colonne de boutons des réseaux) → **80 %** au plus, 2 lignes si besoin ; ils
    apparaissent en 2-3 images (avant : un fondu qui laissait une page courte à moitié transparente).
13. **Animations simples** → chiffre qui compte, **reflet de lumière** qui traverse chaque carte à son entrée, bouton qui entre
    sur son mot.
14. **Whoosh sur des coupes où rien ne bouge** → retirés (les cartes gardent le leur).
15. **Le contrôle automatique ne voyait pas tout** → il vérifie maintenant : la parole sans sous-titres, l'orthographe des
    cartes et des sous-titres, la barre du haut (12 %), la colonne de boutons à droite, les coupes au même cadre. Ses fausses
    « cartes ternes » (verre à liseré lumineux) ont disparu.

## Ce que j'ai regardé (preuves)

Tout est dans `runtime\cache\tmp\ronde4q\` :
- **export final, 1 image par seconde** (prise au milieu de chaque seconde) : `final\planche-1.png`, `final\planche-2.png`,
  `final\planche-3.png` ; identique à l'essai de 2 h 42 (écart moyen 0,3/255), dont j'ai regardé `export2\planche-1.png` à
  `export2\planche-3.png` ;
- **gros plans** : `export1\bas-gauche.png` (table à 0:12,7 et 0:41,7), `export1\mains.png` (mains à 0:29,5 et 0:32),
  `export1\entrees.png` (entrée de chaque carte), `export2\deux.png` (lumière et contours), `export2\fondu.png` (entrée des
  sous-titres), `essai1\trois.png`, `essai1\grille.png`, `essai1\grille2.png` (essais avant l'export) ;
- **table détectée** : `presence\occultants.png` (carte de présence de chaque plan, droite trouvée en vert) ;
- **autres styles** avec le nouveau code : `generalite\grille.png` (Tech application et Collage) ;
- rapport du contrôle : `runtime\cache\controle\script1-script-qualite\export-9x16\controle.txt`.

## Vérifié sur d'autres styles (aucune casse)

Copie figée de Vidéo 1, même procédure, contrôle du montage avec le code d'**avant** puis d'**après** ce cycle :

| Style | Avant | Après | Pourquoi ça bouge |
| --- | --- | --- | --- |
| Tech application (ton style) | 8,4 | 8,1 | un conseil nouveau : « coupes au même cadre » (vrai : ce style ne change pas de plan aux coupes) |
| Éditorial cinétique | 6,7 | 6,4 | même conseil nouveau |
| Hormozi | 4,9 | 4,9 | inchangé |
| Collage | 8,0 | 7,1 | 3 conseils nouveaux et vrais : coupes au même cadre, sous-titres cachés par les autocollants (12 % de la parole), sous-titres jusqu'à 92 % de la largeur |

Les baisses viennent **seulement de vérifications nouvelles** (de vrais défauts qui existaient déjà dans ces styles), pas d'un
rendu abîmé. Images regardées : dans Tech application, le texte reste pendant les notifications et le chiffre s'écrit « 5× ».

## Ce qui reste (honnêtement)

- **L'incrustation se voit encore pour un œil exercé** : la lumière est maintenant expliquée, mais la personne a été filmée
  dans un bureau clair. Pour un rendu parfait : filmer devant un fond sombre ou neutre, lumière plus douce.
- **0:41,7** : pendant 5 images, l'avant-bras est encore coupé par le bord de la table (dans ce plan, la table ne se voit pas
  assez nettement dans le détourage pour être retrouvée ; le bas sombre de l'image l'atténue).
- **Doigts un peu flous** sur les gestes très rapides (0:29,5, 0:32) : flou de bouger de la prise.
- **0:41,7 à 0:51,7** : 10 s sans carte, seulement le visage, les relances de cadre et les sous-titres (voulu par le plan :
  « preuve humaine »), un peu long.
- **Coupe de 1:07,7** : la caméra change bien de plan (× 1,16) mais le visage bouge au même moment ; le contrôle la mesure à
  × 1,07 (simple conseil).
- **« trois heures » en bleu** sur le pull brun (0:26,7) : contraste un peu faible (conseil).
- **Autres styles** : les corrections de cadre aux coupes et la largeur des sous-titres ne valent que pour Tech 3D. Dans ton
  style Tech application, « MOINS CHER » touche encore le haut des cheveux (déjà signalé avant).
- **Pas de plans de coupe** (`media\broll` vide) ; la référence est du pur motion design : une pub face caméra de 71 s ne peut
  pas avoir son rythme.
- La relecture d'orthographe ne change que les mots **neufs** d'un montage (et cette version) : ta version Tech application
  garde ses mots tels quels (« appuyer », « Pi »…). Pour la corriger si tu veux (depuis `engine\`) :
  `python -m editeur orthographe ..\projects\script1 --reel script --appliquer`.

---

# Avant le juge : premier passage de la ronde 3 (2 octobre, vers 1 h)

> Historique. La vidéo dont parle cette partie s'appelle maintenant `Vidéo 1 - qualité - FINAL (ancien 2026-10-02 00h56).mp4`
> (c'est celle qu'a notée le juge). Le juge l'a notée 6,5/10 : mon « environ 8 » ci-dessous était trop généreux.

## En bref

- **La vidéo finale est ici** : `livraisons\Lot 2026-09-30 10h51\Vidéo 1 - qualité - FINAL.mp4`
  (71 s, 1080 × 1920, son à −14 LUFS, crête −1 dB).
- **Ta vidéo à toi n'a pas été touchée.** Elle est toujours en style « Tech application ». Tout le travail est
  dans une **nouvelle version**, « Vidéo 1 - script › qualité », visible dans l'éditeur (fichier
  `projects\script1\reels\script-qualite.json`). Une copie a été gardée avant chaque changement (onglet Versions).
- **Note** :
  - contrôle automatique de la vidéo : **7,2 → 8,8 / 10** (« Prêt à livrer », plus aucun problème important) ;
  - mon jugement de monteur, comparé à la vidéo de référence : **environ 6,8 → 8 / 10**.
- Le premier export de la ronde est gardé à côté, sous le nom
  `Vidéo 1 - qualité - FINAL (ancien 2026-10-02 00h06).mp4`, pour comparer.

## Quel style, et pourquoi

J'ai comparé ton style actuel (« Tech application ») et « Tech 3D cinématique » sur les mêmes passages
(accroche, preuve « ×5 », appel à l'action).

- **Tech 3D cinématique gagne nettement** pour cette pub :
  - c'est le langage de la vidéo de référence : fond sombre, pilules de verre lumineuses, interfaces qui
    s'animent ;
  - la personne est détourée proprement (nouveau moteur RVM : mains et bords nets, aucune zone douteuse sur la
    vidéo) ;
  - les cartes sont lisibles sur un téléphone.
- **Tech application garde des défauts** :
  - le bureau est surexposé et encombré (chaises, table, fenêtre brûlée) ;
  - le « ×5 MOINS CHER » colle aux cheveux, et le sous-titre répète la même chose.

## Ce qui n'allait pas dans le premier export (mon œil de monteur, ≈ 6,8/10)

1. **0:00 à 0:26 : 26 secondes sans rien** à part les sous-titres. Le cadre bouge à peine. C'est là que les gens
   décrochent.
2. **0:16 à 0:21** : elle compte sur ses doigts « salaire, avantages sociaux, vacances, journées de maladie ». Rien
   ne l'illustre.
3. **Coupes franches au même cadre** (0:12,6, 0:21, 0:23,1, 0:45) : on voit un saut de l'image.
4. **Fin faible** :
   - l'offre (« gratuitement… pendant une semaine ») n'était pas montrée ;
   - la dernière demande (« appuyez sur le bouton En savoir plus ») était sans bouton.
5. Un **sous-titre vide** d'un instant à 0:60,4 (un guillemet « » » transcrit seul).
6. **Musique presque inaudible** : environ 30 dB sous la voix, alors que la norme est de 18 à 25 dB.
7. Cartes en verre très sombre sur un studio très sombre : elles se détachaient mal.

## Ce que j'ai corrigé (améliorations générales, valables pour toutes tes vidéos)

1. **Relances de cadre comme un vrai monteur** (studio Tech 3D) :
   - à chaque coupe franche, la caméra change de valeur de plan (plan large ↔ plan serré) ;
   - dans un long passage, un « punch-in » se fait au début d'une phrase ou sur un mot fort (par ex. sur
     « concurrent » à 0:02,9, « gratuitement » à 1:04,5) ;
   - garde-fous : jamais pendant une carte, jamais la tête coupée, jamais plus de ×1,32 ;
   - les temps « visage seul » (accroche, tension, preuve humaine) sont filmés plus serrés.
   - Résultat : le plus long plan fixe passe de 9,1 s à 5,4 s.
2. **Nouvelle carte « liste »** :
   - quand une énumération est dite (« un salaire, des avantages sociaux, des vacances et des journées de
     maladie »), chaque élément apparaît en pilule **au moment exact où il est dit** ;
   - teinte chaude pendant le problème, couleur d'accent ailleurs ;
   - le texte est celui qui est dit : rien n'est inventé.
3. **Bouton final avec l'offre** :
   - le bouton revient sur la dernière demande ;
   - au-dessus, l'offre réellement dite : « 1 SEMAINE GRATUITE » ;
   - sans durée ni mot « gratuit » dans la phrase, la marque reste au-dessus.
4. **Rien sur l'accroche** : le moteur respecte le « visage et phrase seuls » du plan créatif. La place libérée
   sert à une notification utile juste après (« Réponse envoyée au lead », 0:09,3). Ton style actuel en profite
   aussi : plus de carte « Nouveau lead reçu » pendant l'accroche.
5. **Son des interfaces** : chaque carte entre avec un léger « whoosh », chaque élément de liste avec un petit
   clic, la preuve ×5 avec un son grave. **Musique remontée** à 25 dB sous la voix (style Tech 3D).
6. **Sous-titres** : un guillemet ou une ponctuation seule ne fait plus jamais un sous-titre vide (le « « » ouvrant
   va au mot suivant).
7. **Verre des cartes un peu plus clair** (fumé) : il se détache mieux du fond, comme les pilules de la référence.
8. **Contrôle qualité au même calcul que le rendu** :
   - taille et hauteur réelles des sous-titres (fin des faux « sous-titres 61 px » et du faux « visage couvert » en
     16:9) ;
   - taille réelle du ×5 ;
   - carte « liste » reconnue ;
   - un bouton redit en même temps que la voix n'est plus compté comme un « message répété ».
9. **Panneau de retouche** : les curseurs « Hauteur / Position / Taille » montrent la place réellement affichée. Le
   premier réglage ne fait plus sauter la carte.

## Vérifié sur d'autres styles (aucune casse)

Même copie de Vidéo 1, contrôle du montage avant / après mes changements :

| Style | Avant | Après | Commentaire |
| --- | --- | --- | --- |
| Tech application (ton style) | 7,4 | **8,4** | plus de carte sur l'accroche |
| Éditorial cinétique | 5,7 | 5,7 | inchangé (défauts propres à ce style) |
| Hormozi | 4,9 | 4,9 | inchangé (sous-titres géants sur le visage, voulu par ce style) |
| Tech 3D cinématique | 6,8 | **8,5** | |

Les images de Tech application et d'Hormozi ont été regardées : rendu normal.

## Ce qui reste (honnêtement)

- **Lumière** : la personne reste plus chaude (lumière de bureau) que le studio bleu froid. Un œil exercé voit le
  montage. Il faudrait une vraie « reprise de lumière » (refroidir la peau risque de la rendre grise).
- **Gros plans** : agrandis numériquement jusqu'à ×1,32, donc un peu moins nets. Pour des gros plans parfaits, il
  faudrait filmer en 4K.
- **Liste** : pilules un peu petites (≈ 49 px de texte) quand 4 éléments doivent tenir sur la largeur.
- **Rythme** : de 0:55 à 0:59,8 et de 1:02,8 à 1:04,5, seulement le visage et les sous-titres (moins de 6 s,
  acceptable).
- **Pas de plans de coupe** : le dossier `media\broll` est vide. Une seule caméra, un seul angle.
- **Par rapport à la référence** : c'est du pur motion design, très dense (un changement toutes les 0,5 s). Une pub
  face caméra de 71 s ne peut pas avoir ce rythme. Nos transitions de cartes sont aussi plus simples (fondu et
  glissé, pas de verre 3D ni de particules).
- **Contrôle automatique** : il garde 6 conseils (lumière, cartes « ternes » à la mesure des pixels, un sous-titre
  à 0:16,5). Aucun n'est bloquant.

## Où sont les preuves (images regardées)

Dans `runtime\cache\tmp\ronde3-qualite\` :
- `ref\planche-ref.png` (référence) ;
- `depart\grille-p3d.png` et `depart\grille-tech.png` (comparaison des deux styles) ;
- `export1\planche-a.png`, `export1\planche-b.png`, `export1\gros-plans-1.png`, `export1\gros-plans-2.png` (premier
  export) ;
- `essai1\grille.png`, `iter1\grille.png`, `verre\grille-avant-apres.png` (corrections) ;
- `apercu1\transitions.png` et `apercu2\planche.png` (aperçus vidéo 0–25 s et 54–71 s) ;
- `export2\planche-a.png`, `export2\planche-b.png`, `export2\gros-plans-a.png`, `export2\gros-plans-b.png` (export
  final) ;
- `generalite\grille-styles.png` (autres styles).

Les rapports du contrôle sont dans `runtime\cache\controle\script1-script-qualite\`.
