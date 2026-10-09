# Compte rendu — ronde 4 (2 octobre 2026) : nouvelle Révision, icônes, finition de Vidéo 1

Trois chantiers ont été faits en même temps, chacun vérifié par un relecteur indépendant, puis assemblés et testés
ensemble. Détails techniques pour une prochaine conversation : `REPRISE.md` §27.

## En bref

- **Nouvel écran Révision**, d'après la maquette Claude Design : mêmes couleurs, police Manrope, icônes propres, même
  disposition (liste à gauche, vidéo au centre, actions à droite). Toutes les fonctions d'avant sont gardées.
- **Icônes** : 1 857 icônes gratuites (Lucide), cherchables en français, à poser en **trait**, **pastille pleine** ou
  **verre givré**, aux couleurs de ta charte. Tu peux aussi ajouter tes icônes achetées.
- **Vidéo 1 « qualité »** : les 8 défauts relevés par le juge n° 3 (note 7,6/10) sont corrigés par des règles générales.
  Nouvelle vidéo : `livraisons\Lot 2026-09-30 10h51\Vidéo 1 - qualité - FINAL.mp4` (export de 6 h 58). Contrôle
  automatique : 10/10. Le juge n° 4 ne l'a pas encore revue.
- **Ta vidéo à toi n'a pas changé** (Vidéo 1, style « Tech application »). Rien n'a été effacé : les anciens exports sont
  gardés sous « (ancien …) ».
- **L'éditeur a été relancé** le 2 octobre à 8 h 41, par son lanceur habituel, quand il était au repos (aucun montage ni
  export en cours). Une seule copie tourne. La fenêtre du lanceur est réduite dans la barre des tâches : la fermer arrête
  l'éditeur. Il suffit de recharger la page (http://127.0.0.1:8790).

## Ce que tu peux essayer (où cliquer)

### 1. La Révision (page d'accueil)

1. Ouvre l'éditeur (double-clic sur « Editeur Sami.cmd », ou http://127.0.0.1:8790 dans ton navigateur).
2. **En haut** : les onglets « Révision » et « Éditeur », puis les compteurs du jour (vidéos déposées, prêtes, prises).
   La roue dentée montre les raccourcis clavier et ouvre le dossier Entrée ou la corbeille.
3. **À gauche** :
   - dépose tes vidéos dans la carte en pointillés (ou glisse-les n'importe où dans la page) ; choisis la charte client
     juste en dessous ;
   - chaque vidéo du jour montre sa miniature, son sujet, son état (prête, en montage avec %, en file, prise, erreur) et
     sa note sur 10 en couleur ;
   - **nouveau** : « Choisir plusieurs » → coche des vidéos prêtes → **Prendre** les exporte toutes d'un coup (aux formats
     cochés, avec confirmation) ;
   - en bas : « Corbeille » (avec Restaurer) et « Ouvrir le dossier Entrée ».
4. **Au centre** : la vidéo en grand, avec une barre de lecture simple (clique ou glisse sur la barre ; flèches = ± 1 s).
5. **À droite** :
   - les 4 gros boutons : **Je la prends**, **Modifier**, **Autre style**, **Suivante** (passe la souris dessus : le
     raccourci s'affiche) ;
   - les formats d'export à cocher ;
   - la carte **Contrôle qualité** : grosse note, problèmes avec leur moment (clique « ▶ 0:26 » : la vidéo y va et un
     cadre clignote à l'endroit du problème), et la solution proposée après « → ».
6. **Autre style** (ou touche S) : filtres, aperçus, « mon style », « Revenir au style précédent ».
   - Clique un style puis **Appliquer ce style** (un double-clic applique tout de suite).
   - « Enregistrer comme mon style » et « Toujours ce style pour … » sont en bas.
   - Pour créer un style depuis une vidéo modèle, **glisse-la sur la carte « Style depuis une vidéo »**. Quand cette
     galerie est ouverte, une vidéo lâchée ailleurs n'est plus envoyée au montage par erreur.
7. **Raccourcis** : Entrée = je la prends · E = modifier · S = autre style · → = suivante · Espace = lecture · Échap = fermer.
   Ctrl+Z ne fait rien dans la Révision (un message explique pourquoi) : il ne sert que dans l'éditeur.
8. Après « Modifier », quand tu reviens sur l'onglet Révision, tu retombes sur la même vidéo.

### 2. Les icônes

Conseil : essaie-les sur une copie (dans l'éditeur, onglet **Versions** → enregistrer une version), ou annule avec Ctrl+Z.

1. Choisis une vidéo → **Modifier** → **Plus → Banque** → filtre **Icônes**.
2. Cherche en français : « argent » (billet, pièces, tirelire, portefeuille), « poignée de main », « téléphone »,
   « croissance », « maison », « sécurité »…
3. Choisis le style avec la bascule **Trait / Plein / Verre** (l'aperçu change), place la tête de lecture, puis **+ Ajouter**.
4. Pour la changer après coup : **Graphismes → Vecteurs** → style, couleurs, taille, place, animation ;
   « 🎨 Couleurs de la charte » remet les couleurs automatiques. Dans la timeline, la piste montre le nom français de l'icône.
5. **Tes icônes achetées** : dépose les fichiers SVG ou PNG dans `assets\banque\import` (un sous-dossier = une catégorie),
   puis clique ↻ dans la banque. Elles apparaissent en premier, avec la mention « licence à vérifier ».
   - Une icône SVG noire, grise ou blanche prend les couleurs de ta charte ; une icône en couleur (logo d'un partenaire,
     plusieurs couleurs) garde ses couleurs. Un PNG garde toujours ses couleurs.

### 3. Vidéo 1 « qualité »

Regarde `livraisons\Lot 2026-09-30 10h51\Vidéo 1 - qualité - FINAL.mp4` (ou, dans l'éditeur, la version
« Vidéo 1 - script › qualité »). Ce qui a changé par rapport à celle du juge n° 3 :

1. **Bande blanche le long de la joue** : le mur blanc collé au visage est retiré ; le blanc pris dans la silhouette prend la
   couleur de la peau voisine. Les boucles d'oreilles gardent leur or ; yeux, dents et cheveux ne sont pas touchés.
2. **Sauts d'image sans coupe** : les 4 ont disparu. La caméra change de cadre sur une coupe, sur l'image où la carte arrive,
   ou par un glissement lent.
3. **Mots en couleur qui touchaient leur voisin** : ils « frappent » toujours, sans déborder ni rebondir.
4. **Bouton qui partait puis revenait** : un seul « En savoir plus » jusqu'à la fin ; « 1 SEMAINE GRATUITE » se pose au-dessus
   au moment où elle le dit.
5. **Sous-titre éclair** : une page n'est plus jamais montrée moins de 0,6 s.
6. **Recul avant chaque carte** : la caméra recule au moment exact où la carte entre.
7. **Doigts transparents** : plus opaques (encore flous sur les gestes rapides : c'est le flou de la caméra).
8. **Apostrophes** : la même partout (« ’ »), sous-titres, cartes, bandeau et titres.

## Ce qui a été téléchargé (sur D: seulement)

| Quoi | Source | Taille | Licence |
| --- | --- | --- | --- |
| Lucide 1.49.0 (1 857 icônes au trait) | registry.npmjs.org, paquet « lucide-static » | archive 6,8 Mo (2,8 Mo gardés dans `assets\banque\icones\lucide`) | ISC (usage commercial permis) ; quelques dessins dérivés de Feather, MIT |
| 45 icônes Lucide pour l'écran Révision | unpkg.com (lucide-static 1.49.0) | 22 Ko (seuls les tracés sont recopiés dans `app\ui\icons.tsx`) | ISC + MIT (Feather), note de licence dans le fichier |

Rien d'autre n'a été téléchargé. Aucun service en ligne n'est utilisé par l'éditeur.

## Ce qui reste (honnêtement)

- **Juge n° 4** : la nouvelle Vidéo 1 n'a pas encore été rejugée par un juge indépendant (mon estimation : ≈ 8/10).
- **Limite de la prise** (mur blanc, lumière de fenêtre) : côté du visage très clair, oreille gauche un peu floue à 1:06,7,
  doigts flous sur les gestes rapides. Pour la prochaine fois : fond plus sombre, lumière douce de face.
- Fin en plan moyen pendant ≈ 8 s avec le bouton, puis plan serré ; la place gardée pour l'offre est vide au-dessus du bouton
  entre 0:59,8 et 1:04,45 ; le mot en couleur « frappe » plus discrètement ; la coupure de ligne « quelqu’un à | temps plein ».
- **Éditeur** : seule sa barre du haut a le nouveau look ; le reste garde l'ancien thème jaune. Pas d'onglet « Système de
  design » (la maquette ne le fournit pas).
- **Icônes** : environ 1 300 icônes ont un nom traduit mot à mot (ex. « Aligner centre vertical ») ; le verre paraît un peu
  gris sur une image très claire (voulu, pour que l'icône reste lisible).
- **Question pour toi** : veux-tu un bouton, icône par icône, pour forcer ou empêcher la recoloration d'une icône importée ?
  Aujourd'hui c'est automatique (noir / gris / blanc → charte ; couleurs → gardées).
- **À décider par toi** : les détourages intermédiaires des essais (versions v6 et v7, environ 741 Mo dans
  `assets\detourage`) ne servent plus qu'aux anciennes versions de « qualité ». Ils ne sont pas effacés sans ton accord.

## Vérifications faites

Tout a été relancé après l'assemblage des trois chantiers, sur des copies de test (jamais sur tes vidéos) :
- construction de l'interface, vérification des types (0 erreur), serveur et plugin : OK ;
- grande série de tests de l'éditeur : **32 étapes sur 32 vertes**, dont les 11 tests obligatoires et l'interface (26/26) ;
- moteur : 8 + 6 + 18 tests, cerveau créatif OK, contrôle qualité 54/54, détourage 23/23, tests des juges 20/20, 18/18 et 24/24,
  ronde 3 27/27, icônes OK ;
- calcul du montage : 6, 71, 18, 18, 19 et 14 vérifications ; les 1 857 icônes dans les 3 styles : 22 329 vérifications ;
- écran Révision sur une copie à part : **39/39** (avec un vrai export de 2 s), raccourcis avec de vrais clics de souris 9/9,
  dépôt dans la galerie 6/6, Ctrl+Z sans effet dans la Révision ;
- vrai éditeur après la relance : une seule copie du serveur, il répond, les icônes sont servies (« poignée de main » trouve
  les 2 bonnes icônes ; 2 413 ressources en tout dans la banque).

## Ce que j'ai regardé

Captures du **vrai éditeur** (en lecture seule : tout envoi qui écrit était bloqué dans le navigateur de capture), comparées à
la maquette `docs\design\maquette\captures\revision-1440.png`. Copies dans `docs\qualite-2026-09-30\captures-ronde4\` :
- `reel-base-1440x900.png` et `reel-base-1920x1080.png` : même disposition, mêmes couleurs, même police, même taille de lecteur
  et de boutons que la maquette. Les différences viennent de tes vraies données : une seule vidéo dans la liste (le bouton
  « Choisir plusieurs » n'apparaît qu'à partir de 2), pas encore de note de contrôle sur ce montage (« – / 10 » et un bouton pour
  le lancer), « 0 vidéo aujourd'hui » (elle a été déposée avant aujourd'hui).
- `reel-galerie-1440x900.png` : galerie « Autre style » (filtres, aperçus, « Style depuis une vidéo », Appliquer grisé tant
  qu'aucun style n'est choisi).
- `reel-reglages-1440x900.png` : panneau des raccourcis et des dossiers.
- `reel-banque-1440x900.png` : éditeur → Banque → Icônes, recherche « argent » en style Verre (61 résultats : main qui donne de
  l'argent, billet, pièces, tirelire, portefeuille, carte).
- Défaut vu et corrigé pendant cette vérification : dans « clique « Relancer le contrôle » », le « « » restait seul en fin de
  ligne (espaces insécables ajoutées).
