# Jugement indépendant n° 1 — Vidéo 1 « qualité » (2 octobre 2026)

Vidéo jugée : `livraisons\Lot 2026-09-30 10h51\Vidéo 1 - qualité - FINAL.mp4` (export du 2 oct. 00 h 56, 70,87 s,
1080 × 1920, 30 i/s, H.264 + AAC 48 kHz).
Comparée à :
- `docs\references\reference-montage-spectaculaire.mp4` (la référence) ;
- `… - FINAL (ancien 2026-10-02 00h06).mp4` (premier export de la ronde 3) ;
- la version actuelle de l'utilisateur (`projects\script1\reels\script.json`, style Tech application), regardée en
  images fixes rendues avec le code actuel, en lecture seule.

Je n'ai rien construit et je n'ai modifié aucun fichier du projet, à part celui-ci.

## En bref (pour l'utilisateur)

- **Note : 6,5 / 10.** C'est propre et moderne, mais pas encore « prêt à livrer » pour une pub payante.
- Le contrôle automatique dit 8,8 et le monteur qui l'a faite dit 8. Je suis plus sévère, pour quatre raisons
  qu'on voit tout de suite sur un téléphone :
  1. **Un tiers du texte disparaît.** Les sous-titres sont coupés chaque fois qu'une carte apparaît (environ 23 s
     sur 71 s). Sans le son, on lit des bouts de phrase sans suite.
  2. **Une faute dans une carte** : « Qualifier → **Transférez** » (0:52). Il faudrait « Transférer ».
  3. **Une carte dit le contraire de la phrase** (0:26–0:29). Elle dit qu'un lead qui attend 3 h a déjà été appelé
     par le concurrent ; la carte montre « Lead / Appelé ✓ » en bleu, comme un succès. Ta version actuelle avait la
     bonne carte : « Lead en attente depuis 3 h ».
  4. **On voit l'incrustation.** La personne, éclairée chaud par la fenêtre du bureau, est collée sur un fond bleu
     sombre qui ne bouge pas. À deux moments, on voit même un bout de la table du bureau (0:12,6) ou un bras
     coupé en diagonale par le bord de la table effacée (0:41,6).
- Ce qui est vraiment bien :
  - détourage du visage et des cheveux net ;
  - cartes en verre élégantes et lisibles ;
  - liste « salaire, avantages sociaux, vacances, journées de maladie » qui apparaît au mot près ;
  - bouton « En savoir plus » synchronisé avec la voix ;
  - son au bon niveau.
- **Par rapport au premier export : nettement mieux** (liste, boutons, offre, rythme, musique, plus de sous-titre
  vide).
- **Par rapport à ta version actuelle (Tech application)** :
  - plus « premium » et plus proche de la référence ;
  - mais moins naturelle, et la carte « 3 h » était meilleure chez toi.
  - Je ne conseille pas de la prendre telle quelle. Avec les 4 corrections ci-dessus (rapides), elle vaudrait environ
    7,5 ; avec une vraie intégration de la lumière, environ 8.

## Notes

| Vidéo | Note | Commentaire |
| --- | --- | --- |
| **Vidéo 1 - qualité - FINAL (jugée)** | **6,5** | plafonnée par l'incrustation visible, la faute à l'écran et les sous-titres coupés |
| Vidéo 1 - qualité - FINAL (ancien 00h06) | ≈ 5,8 | mêmes défauts, plus : pas de liste, pas de bouton final, sous-titre vide à 1:09, musique trop basse |
| Ta version actuelle (Tech application, images fixes seulement) | ≈ 6 (estimation) | naturelle, cartes justes (« Lead en attente depuis 3 h ») ; bureau surexposé et encombré, pas de bouton |
| Référence (motion design pur, 12 s) | — | autre genre : un changement toutes les 0,25–0,5 s, chiffres qui comptent, morphings, lueurs |

Détail de la note (sur 10) :
- intégration image : 5,5 ;
- cartes et textes : 6 ;
- sous-titres : 6 ;
- montage et rythme : 6,5 ;
- son : 8 ;
- message et fin : 6,5.

## Ce que j'ai regardé (méthode)

Tout est dans `runtime\cache\tmp\juge1-10020110\` :
- **1 image/s** de la vidéo jugée : `pl-final-00.png` à `pl-final-04.png`. Même chose pour l'ancien export :
  `pl-old-00.png` à `pl-old-04.png`.
- **Référence** à 4 images/s : `pl-ref-00.png`. J'ai aussi vu `runtime\cache\tmp\ronde3-qualite\ref\planche-ref.png`.
- **Coupes** :
  - avant/après chaque coupe : `coupes-avant-apres.png` ;
  - 6 premières images de chaque plan : `debuts-plans-a.png`, `debuts-plans-b.png` ;
  - image par image à 0:41,5 : `pl-c41-00.png` ; à 0:18,45 : `pl-c18-00.png`.
- **Bords du détourage** :
  - `zoom-bas-gauche.png`, `pl-bl1-00.png`, `pl-bl2-00.png` (mains, bas gauche) ;
  - `pl-bois-00.png` (table à 0:12,6) et `pl-diag-00.png` (diagonale à 0:41,6) ;
  - `tetes-hd.png`, `bords-zoom.png`, `bords-66.png` (cheveux, visage, bras à 1:1).
- **Cartes en pleine définition** : `cartes-hd-a.png`, `cartes-hd-b.png`. Leurs entrées : `entrees-cartes.png`.
- **Fin** : `pl-fin-00.png`. **Comparaison de rendu** : `look-compare.png`.
- **Ta version actuelle** : `planche-user.png`, 9 images rendues avec `stills.mjs`, en lecture seule. J'ai aussi vu
  `ronde3-qualite\depart\grille-tech.png` et `ronde3-qualite\generalite\grille-styles.png`.
- **Mesures** :
  - son : ebur128 sur les 3 exports ; RMS par 50 ms ; recherche de clics aux coupes (dérivée seconde à 48 kHz) ;
  - images : position verticale des cartes et largeur des sous-titres, mesurées sur les pixels ;
  - cadre : changement de valeur de plan aux coupes (taille de la silhouette) ;
  - temps des sous-titres, des scènes et des sons : `infos.mjs` (ronde 3) et `sons.mjs`, en lecture seule.

## Son (mesuré)

- **Niveaux** : −14,0 LUFS intégré, crête vraie −1,0 dBFS, LRA 3,1 LU. Pareil pour l'ancien export et pour l'export
  « Hook original ». **Conforme.**
- **Coupes** : aucun clic ni craquement mesuré aux 8 coupes. Le pic de dérivée seconde le plus fort est une sifflante
  à 0:29,2.
- **Musique / voix** : la musique (`tech.ogg`, −15,4 LUFS) est réglée à 0,19 et baissée à 45 % sous la parole. Elle
  est donc environ **21 dB sous la voix** pendant la parole (le rapport annonce 25 dB ; les deux sont dans la norme de
  18 à 25 dB). Dans la courte pause 0:36,2–0:36,6, le mélange tombe à −29 dB RMS contre −15,6 dB pour la parole : la
  musique s'entend.
- **Bruitages** : ils restent dans l'enveloppe de la voix (maximum −8 à −11 dB sur 50 ms) et aucun ne dépasse
  nettement.
  - Petite réserve : un « whoosh » est posé sur 4 coupes franches où rien ne bouge (0:12,4 / 0:28,5 / 0:41,5 /
    0:54,3). C'est un son sans raison à l'image, mais très discret (≈ −21 à −25 dB).
- **Fin** : le dernier mot (« bientôt ») finit à 70,67 s et la vidéo s'arrête à 70,87 s. Il reste 0,2 s, sans tenue
  de fin.
- **Limite** : je n'ai pas pu *écouter*. Le timbre de la voix et la qualité du débruitage ne sont pas jugés.

## Points forts

1. **Détourage du visage et des cheveux très propre** (RVM) : pas de halo à 1:1, pas de scintillement vu, bords
   stables (`tetes-hd.png`, `bords-zoom.png`).
2. **Langage visuel proche de la référence** : fond sombre, pilules de verre à liseré lumineux. Les textes (Manrope
   800) sont nets et lisibles sur téléphone (`cartes-hd-*.png`).
3. **Liste au mot près** : « Salaire » 0:16,95, « Avantages sociaux » 0:18,1, « Vacances » 0:19,25, « Journées de
   maladie » 0:19,8, avec un clic par élément. C'est la meilleure idée de montage de la vidéo.
4. **Boutons d'appel à l'action synchronisés** sur « En savoir plus » (0:59,8 et 1:08,8), avec l'offre réellement
   dite au-dessus du dernier bouton.
5. **Relances de cadre** sur des mots qui ont du sens : « concurrent » 0:02,9, 0:32,2, « gratuitement » 1:04,5.
   Coupes franches alternées serré/large à 0:12,6, 0:23,1, 0:41,7, 0:45,0 et 1:07,7.
6. **Sous-titres** bien placés (66–72 % de la hauteur), 4 mots par page, mot clé en couleur. Plus aucune page vide :
   le « « » seul de l'ancien export à 1:09 a disparu.
7. **Son de diffusion** conforme : −14 LUFS, −1 dBTP, musique audible et baissée sous la voix.

## Défauts (du plus grave au moins grave)

| # | Moment | Gravité | Problème | Piste de correction |
| --- | --- | --- | --- | --- |
| 1 | 0:09,3–0:11,7 ; 0:16,9–0:21,4 ; 0:25,9–0:29,0 ; 0:34,7–0:37,7 ; 0:37,9–0:40,1 ; 0:51,7–0:54,7 ; 0:59,8–1:02,8 ; 1:08,8–fin | **Important** | **Sous-titres retirés pendant chaque carte** : ≈ 23 s sur 70,5 s de parole (33 %). Sans le son, le message casse : « Parce que chaque lead » → [Réponse envoyée au lead] → « à temps plein » (perdu : « sans avoir embauché quelqu'un »). « c'est pas mieux, parce » → [Lead / Appelé] → « C'est pour ça que » (perdu : « un lead qui attend trois heures a déjà été appelé par ton concurrent »). « Et je vous garantis » et « qu'un employé habituel » sont cachés. Des pages orphelines suivent : « avoir à gérer quoi » 0:40,4, « puissiez l'expérimenter sans risque » 1:01,8 sans « Et pour que vous ». | Garder les sous-titres pendant les cartes : les cartes sont en haut (12–20 %) et les sous-titres à 69 %, donc ils ne se gênent pas. Ne les masquer que si la carte répète **les mêmes mots** (liste, bouton). Toujours reprendre sur un début de page complet. |
| 2 | 0:25,9–0:29,0 | **Important** | **Carte à contresens** : « Lead / Appelé ✓ » en cyan, avec barre de progression, se lit comme un succès du produit. Or la phrase décrit le *problème* (3 h d'attente, le concurrent appelle). « 3 h » et « concurrent » disparaissent. Le chiffre « 3 h » existe dans le reel (`g1-chiffre`, 26,29 s) mais n'est pas montré. Ta version Tech application avait la bonne carte (« Lead en attente depuis 3 h »). | Dans `galerie.py`, sur un temps « probleme » : carte en teinte chaude, état négatif (« En attente · 3 h » → « Appelé par un concurrent ✕ »), ou montrer le chiffre 3 h. Ne jamais mettre une coche ✓ cyan pendant le problème. |
| 3 | 0:51,7–0:54,7 | **Important** | **Faute dans une carte** : « Qualifier → Transférez ». Le mot est recopié de la transcription fautive « avant de vous le transférez » et mélange infinitif et impératif. Une faute dans un écran de marque ne se livre pas. | Mettre les libellés de parcours à l'infinitif (« Transférer ») avec une table é/er/ez, ou une relecture courte par l'IA locale limitée aux libellés. Ajouter au contrôle une vérification d'orthographe des textes de cartes. |
| 4 | 0:09,3 ; 0:17 ; 0:26 ; 0:37,9 ; 0:59,8 ; 1:08,8 | **Important** | **Cartes dans la zone cachée du haut** : le haut des cartes est à 98–150 px du bord (5–8 %) : tableau 98 px, « 1 SEMAINE GRATUITE » 112 px, ×5 113 px, liste 116 px, « RYUCALLS » 148 px, notification 150 px. TikTok et Reels y posent leur barre (onglets, recherche, titre « Reels »). L'offre, l'élément qui fait vendre, est la plus exposée. | Haut de toute carte ≥ 12–14 % de la hauteur (≈ 230–270 px en 9:16). Mettre l'offre **sous** le bouton, ou descendre le bouton vers 25–30 %. Ajouter au contrôle une règle « zone haute TikTok/Reels ». |
| 5 | toute la vidéo | **Important (plafonne la note)** | **Incrustation visible** : peau éclairée chaud par la fenêtre (côté gauche de l'écran), studio bleu froid sans lumière qui l'explique, aucun liseré ni « light wrap ». Le fond reste presque immobile (écart < 0,4/255 sur 3 s). Le buste flotte : pas de chaise, pas de sol, pas d'ombre. Le contrôle le dit aussi (rouge−bleu du visage 59 contre un studio à (6,10,20)). | Liseré cyan/violet de 2–4 px sur cheveux et épaules, côté opposé à la fenêtre. Assombrir un peu le côté éclairé. Lueur de sol ou ombre douce derrière le bas du corps. Fond animé lent (parallaxe, particules fines, balayage de lumière comme la référence). Autre piste : fond de bureau flouté et assombri plutôt que studio. |
| 6 | 0:12,63–0:12,95 ; 0:41,55–0:41,82 | Moyen | **La table du bureau trahit le détourage** : à 0:12,6, un coin de table en bois reste sous la main (début du plan c2). À 0:41,6, l'avant-bras et la main sont coupés net par une **diagonale** : le bord de la table effacée cachait le bras. Les deux arrivent sur une coupe, quand l'œil se recale (`pl-bois-00.png`, `pl-diag-00.png`). | Zone fixe « table » du plan (masque de la diagonale bas gauche). Aux moments où la main l'approche : recadrer plus serré pour l'exclure, ou fondre le coin bas gauche dans un dégradé sombre. Dans le détourage, retirer les zones immobiles non humaines. Ajouter au contrôle la détection d'un bord droit dans l'alpha. |
| 7 | 0:22,2 ; 0:37,9 ; 0:41,8 ; 0:58,9 ; 1:07,9 | Moyen | **Textes faux, recopiés de la transcription** : « appuyer sur le bouton » (×2, il faut « appuyez »), « Pi là c'est pas » (« Pis là » / « Puis là »), « closé ou non » (« closés »). Le « ×5 MOINS CHER » se lit « multiplié par 5 » : il faut écrire « 5× MOINS CHER » ou « 5 FOIS MOINS CHER ». | Passe d'homophones é/er/ez sur les sous-titres en gardant les temps des mots. Règle « ×N moins » → « N× moins ». Ne jamais modifier les mots verrouillés ou manuels. |
| 8 | 0:28,70 ; 0:54,47 (et 0:21,00) | Moyen | **Coupes au même cadre** malgré la règle annoncée. Le rapport de taille mesuré est ≈ 1,00 à 0:28,7 et ≈ 0,98 à 0:54,5 (deux prises différentes, carte qui chevauche la coupe), et à peine perceptible à 0:21,0. Les autres relances ne font que ×1,10 à ×1,14 : sur téléphone, c'est trop peu pour un nouveau plan voulu, ça ressemble à un saut. | Appliquer la bascule de plan aussi quand une carte chevauche la coupe. Écart minimum ×1,18–1,20 ; sinon une poussée douce de 0,3 s plutôt qu'un saut de 10 %. |
| 9 | 0:00–0:02,9 | Moyen | **Accroche visuelle plate** : plan moyen fixe sur dégradé sombre, sans titre, sans mouvement, sans élément qui arrête le pouce. La phrase est forte, l'image non. La référence ouvre sur un graphique 3D animé en 0,25 s. | Poussée lente dès l'image 0, ou relance à 0:00,8 sur « temps », mot « concurrent » en texte animé. Si le plan créatif impose « visage seul », au moins un mouvement de caméra et un vrai son d'ouverture. |
| 10 | 1:04,5–1:07,9 | Mineur | **L'offre arrive tard** : « gratuitement… pendant une semaine complète » n'a que les sous-titres. « 1 SEMAINE GRATUITE » n'apparaît qu'à 1:08,8, pendant 2 s, en haut. | Badge « 1 semaine gratuite » à 1:04,5, quand c'est dit, puis gardé sur le dernier bouton. |
| 11 | 1:10,6–1:10,87 | Mineur | **Fin sèche** : le bouton s'efface pendant les 0,2 dernières secondes, sans tenue de fin ni logo. La dernière image montre un bouton à moitié transparent. | Garder le bouton jusqu'à la dernière image et ajouter 0,5–1 s de tenue (musique seule). Ou une fin qui boucle proprement. |
| 12 | 0:07,3 ; 0:45,5 | Mineur | **Sous-titres trop larges** : certaines pages d'une ligne vont de 8 % à 92 % de la largeur (« publicités ça vous concerne », « Chaque setter est formé »). À 69 % de la hauteur, elles touchent la colonne de boutons à droite de TikTok/Reels (x > 88 %). | Largeur maximale 80–84 %, sinon passer sur 2 lignes. |
| 13 | toutes les cartes | Mineur | **Animations simples** : fondu + léger zoom en 0,3 s, puis carte immobile. La référence fait compter les chiffres (8x→9x→10x), enchaîne des morphings et des balayages de lueur. | Compter « ×1 → ×5 ». Faire passer « Répondre → Qualifier » à « Qualifier → Transférer » par un morphing. Balayage de lueur à l'entrée. |
| 14 | 0:29,5 ; 0:32,0 | Mineur | **Doigts fantômes** sur les gestes rapides : doigts semi-transparents, traînée sombre. | Affiner l'alpha dans le temps sur les mains, ou un réglage `downsample` plus fin sur ces passages. |
| 15 | 0:12,4 ; 0:28,5 ; 0:41,5 ; 0:54,3 | Mineur | **Whoosh sur des coupes franches** sans mouvement à l'image : un son sans raison visible, très bas. | Whoosh seulement sur un vrai mouvement (entrée de carte, relance). |

## Ce que le contrôle automatique n'a pas vu (8,8/10)

Il n'a signalé que des conseils (lumière, cartes « ternes », un contraste). Il **manque** :
- la faute « Transférez » ;
- la carte à contresens (0:26) ;
- les 33 % de parole sans sous-titres et les pages orphelines ;
- la zone cachée du haut ;
- la table et la diagonale dans le détourage ;
- les coupes au même cadre.

Ses « cartes ternes » (contraste 1,03–1,16:1) sont en revanche de **faux problèmes** : à 1:1, les cartes se
détachent bien grâce à leur liseré.

## Comparaison détaillée

- **Avec l'ancien export (00h06)** :
  - ajouts réels : liste animée, notification 0:09,3, bouton final avec l'offre, relances 0:02,9 / 0:06,3 / 0:32,2 /
    1:04,5, musique +4,8 dB ;
  - réparé : le sous-titre vide « plus  et on » à 1:09 ;
  - inchangé : « Transférez », « Lead / Appelé », la zone du haut et l'incrustation.
  - Progrès net, mais les défauts de fond restent.
- **Avec ta version actuelle (Tech application)** :
  - **Tech 3D gagne** sur l'élégance, la cohérence avec la référence et la lisibilité des cartes (verre, lueurs) ;
  - **Tech application gagne** sur le naturel (vrai bureau, aucun bord) et sur la justesse de la carte à 0:27
    (« Lead en attente depuis 3 h ») ; elle garde aussi le sous-titre pendant le ×5 ;
  - elle perd sur l'exposition (fenêtre et mur brûlés), le fouillis (chaises, table) et l'absence de bouton et de
    liste.
- **Avec la référence** : pas le même genre (motion design pur, 12 s, un changement toutes les 0,25–0,5 s). La
  vidéo jugée reprend la *matière* (pilules de verre, fond sombre) mais pas la *vie* : rien ne compte, rien ne
  se transforme, et le fond ne bouge pas.

## Ordre de correction conseillé

1. Sous-titres pendant les cartes (défaut 1) : le plus gros gain pour une pub regardée sans le son.
2. Orthographe des cartes et des sous-titres (défauts 3 et 7) : rapide.
3. Carte « problème » juste à 0:26 (défaut 2).
4. Marge haute de 12–14 % pour toutes les cartes (défaut 4).
5. Coin bas gauche (table) et intégration de la lumière (défauts 5 et 6) : plus long.

Les défauts 1 à 4 se corrigent dans le code général et profitent à toutes les vidéos et à tous les styles.
