# File d'attente — montée en qualité (mise à jour : 2026-10-02 vers 9 h, après l'intégration de la ronde 4 — voir la dernière section)

Autorisation de l'utilisateur pour ces étapes : tout est permis (téléchargements sur D: seulement, montages et
exports de test, auto-évaluation, itérations). Règles qui restent : ne jamais lire `cles-api.env`, rien dans
`D:\Y0U`, rien sur C:, ne rien supprimer de l'utilisateur (corbeille / copies datées), une seule équipe d'IA à la
fois sur le code, jamais deux serveurs.

## ⏸️ PAUSE (2026-10-01 vers 3 h 30) — l'utilisateur a demandé d'arrêter (PC allumé depuis plus de 24 h)

Tout est arrêté proprement : workflow arrêté, serveur de l'éditeur et son lanceur arrêtés, aucun processus de test
restant. Vérifié à l'arrêt : `node --check` serveur et MCP OK, `node app/build.mjs` OK, TypeScript 0 erreur.

### Fait
- ✅ Fonctions V2 (notes, crayon, banque, vecteurs, chorégraphie, verrous, « refaire ce passage ») : `docs/direction-creative-v2/RESULTAT.md`.
- ✅ Détourage RobustVideoMatting + contrôle qualité : `resultat-workflow-detourage-controle.json`.
- ✅ **Ronde 2 construite** (rapports : `rapports-ronde2.json`) mais **relecture adverse NON terminée** :
  - Rendu (Tech 3D cinématique) : HUD « VIDÉO 1 / 00:28 » retiré ; nouveau détourage + repli sur la vraie prise ;
    personne refroidie, contour lumineux, ombre ; cartes grandes, animées, au-dessus de la tête ; caméra motivée ;
    sous-titres Manrope (police OFL ajoutée dans `assets/fonts`). Auto-évaluation de l'agent : ~5,5 → ~7/10.
  - Contrôle / lanceur : un serveur lancé en double s'arrête seul (code 98) sans toucher la boîte d'entrée ;
    `editeur.ps1` arrête d'abord l'ancien lanceur ; note /10 + problèmes cliquables dans la Révision ; contrôle
    automatique après chaque export ; « Je la prends » demande confirmation s'il y a un problème bloquant ; plugin :
    outils `controle`, `refaire_passage`, `choregraphie`, `banque_catalogue`.
  - Le relecteur du rendu a fait quelques retouches (choreo.tsx) avant l'arrêt ; le relecteur contrôle venait de commencer.

### À savoir
- **Vidéo 2 est dans la corbeille** : supprimée avec le bouton 🗑️ le 2026-10-01 à 02 h 24 (journal
  `runtime/cache/erreurs-serveur.log`), dossier `corbeille/2026-10-01 02h24 Offre setter qualifié gratuit/`.
  **Confirmé par l'utilisateur : c'est lui qui l'a supprimée, volontairement → NE PAS la restaurer.**
  Conséquence : `docs/direction-creative-v2/tests/test-v2.mjs` échoue (18/32) parce qu'il lit le projet réel
  `projects/script2`. À corriger à la reprise : les tests doivent utiliser leur propre copie figée (fixture dans
  `docs/direction-creative-v2/tests/`, par ex. reprise depuis la corbeille en COPIE), jamais un projet vivant de
  l'utilisateur.

## ▶️ REPRISE LANCÉE le 2026-10-01 à 22 h 45 (l'utilisateur a dit « continue »)
- Éditeur relancé avec le nouveau lanceur (un seul serveur), le PC est gardé éveillé pendant le travail.
- Workflow `reprise-ronde2-ronde3` (`wf_ab4636d9-b9c`) : fin des 2 relectures de la ronde 2 + tests rendus
  indépendants des projets de l'utilisateur, puis ronde 3 sur Vidéo 1 (version « qualité »), puis juge indépendant.
- Copie de l'état juste avant cette reprise : `docs/qualite-2026-09-30/apres-ronde2-non-relue/`.

## ✅ Ronde 3 FAITE (2026-10-02, vers 1 h) — compte rendu : `COMPTE-RENDU.md`, REPRISE.md §24
- Relectures de la ronde 2 terminées (rendu + contrôle/lanceur), leurs correctifs intégrés ; tests indépendants des projets
  de l'utilisateur (fixtures figées).
- Nouvelle version **« Vidéo 1 - script › qualité »** (`projects/script1/reels/script-qualite.json`), Tech 3D cinématique,
  détourage RVM recalculé. Ton reel « script » (Tech application) est inchangé.
- Vidéo finale : `livraisons/Lot 2026-09-30 10h51/Vidéo 1 - qualité - FINAL.mp4`. Contrôle 7,2 -> **8,8/10**
  (0 important) ; jugement du monteur ≈ 6,8 -> 8/10.
- Améliorations générales :
  - relances de cadre (punch-in, coupe franche = autre valeur de plan) ;
  - carte « liste » synchronisée à la voix ;
  - bouton final avec l'offre dite ;
  - rien sur l'accroche du plan créatif ;
  - sons d'interface, musique à 25 dB sous la voix ;
  - plus de sous-titre vide ;
  - verre des cartes plus clair ;
  - contrôle au même calcul que le rendu ;
  - curseurs du panneau de retouche sans saut.
- Généralité vérifiée : Tech application 7,4 -> 8,4 ; Éditorial et Hormozi inchangés.
- Reste :
  - ~~juge indépendant~~ : fait (6,5/10), puis corrections — voir la section suivante ;
  - lumière chaude de la personne contre le studio froid ;
  - gros plans agrandis un peu moins nets ;
  - liste de 4 éléments un peu petite ;
  - aucun plan de coupe (`media/broll` vide) ;
  - défauts propres à Éditorial (sous-titres trop bas, contraste) et Hormozi (sous-titres sur le visage), non traités ici.

## ✅ Juge indépendant n° 1 FAIT, puis corrections générales (cycle 2, 2026-10-02 vers 3 h) — `JUGEMENT-1.md`, `COMPTE-RENDU.md`, REPRISE.md §25
- Juge : export de 00 h 56 noté **6,5/10** (contrôle 8,8). 15 défauts, dont 4 qui plafonnaient la note : sous-titres coupés pendant
  les cartes (33 % de la parole), faute « Transférez », carte « Lead / Appelé ✓ » à contresens, incrustation visible.
- Corrigé en code général (toutes les vidéos) : sous-titres gardés pendant les interfaces (sauf s'ils redisent les mêmes mots),
  relecture d'orthographe des mots transcrits, libellés à l'infinitif, carte du problème juste et chaude, zone du haut 12 %,
  chaque coupe change de valeur de plan, ouverture en mouvement, offre affichée quand elle est dite, fin tenue, « 5× » qui compte,
  reflets d'entrée, pas de whoosh sans mouvement, sous-titres sur 80 % de la largeur ; studio : lumière chaude motivée, liserés
  selon la lumière, bureau au premier plan à la place de la vraie table, décor qui vit ; contrôle : 5 nouvelles vérifications.
- Nouvel export : `livraisons/Lot 2026-09-30 10h51/Vidéo 1 - qualité - FINAL.mp4` (les précédents gardés « (ancien …) »).
  Contrôle 9,1/10 (0 important). Mon jugement : voir `COMPTE-RENDU.md`.
- Généralité (copies figées, passe JSON, code d'avant -> code d'après) : Tech application 8,4 -> 8,1, Éditorial 6,7 -> 6,4,
  Hormozi 4,9 = 4,9, Collage 8,0 -> 7,1 : seulement des CONSEILS nouveaux (coupes au même cadre, sous-titres masqués par les
  autocollants, largeur), aucun rendu cassé.
- Reste : voir « Ce qui reste » dans `COMPTE-RENDU.md` (table d'une prise non détectée à 0:41,7, doigts flous sur les gestes
  rapides, coupes au même cadre et sous-titres masqués dans les AUTRES styles, aucun plan de coupe, référence = motion design pur).

## ✅ Juge indépendant n° 2 FAIT, puis corrections générales (cycle 3, 2026-10-02 vers 5 h) — `JUGEMENT-2.md`, `COMPTE-RENDU.md`, REPRISE.md §26
- Juge : export de 3 h 01 noté **7,3/10** (contrôle 9,4). 13 défauts, dont 3 qui empêchaient le 8 : bande noire en haut (14 s, bascule de
  la caméra), incrustation visible (contour « autocollant », peau claire), faute « de la publicités » ; plus la coupe au même cadre de
  1:07,7 et la caméra qui reculait avant chaque carte.
- Corrigé en code général : décor qui couvre toujours le cadre ; haut de la tête mesuré dans le détourage ; caméra qui garde son plan et
  bascule pendant une carte, changement de cadre d'un coup sur une coupe ou un début de phrase ; coupe trop semblable poussée à × 1,15 ;
  1re image serrée avec sous-titre ; bord de la personne nettoyé, liseré d'un seul côté, peau adoucie, lumière sur le mur, grain ; accord
  déterminant + nom ; découpage des sous-titres (virgules, expressions, petits mots) ; badge de preuve dite ; liste recentrée ; fin tenue
  0,8 s ; table suivie quand la caméra dérive ; contrôle : bande au bord, recul de caméra, fausse détection de visage.
- Nouvel export : `livraisons/Lot 2026-09-30 10h51/Vidéo 1 - qualité - FINAL.mp4` (4 h 52 ; les précédents gardés « (ancien …) »).
  Contrôle 10/10 (0 constat). Mon jugement : ≈ 7,9/10 (prudent). Bande au bord mesurée : 0 s (avant 13,8 s).
- Généralité (copies figées, code d'avant -> code d'après) : Tech application 8,1 = 8,1, Éditorial 6,4 = 6,4, Hormozi 4,9 = 4,9.
- **À faire ensuite** : faire rejuger cette version par un juge indépendant (n° 3). Reste : bord de l'oreille / boucles d'oreilles
  (détourage), peau éclairée par une fenêtre, doigts flous sur les gestes rapides, plan moyen au début de l'offre, coupe de 0:41,7
  à × 1,13, aucun plan de coupe.

## ✅ Ronde 4a (demandée le 2026-10-02) — nouvelle interface « Révision » d'après la maquette Claude Design — FAITE (voir la dernière section)
À lancer après la ronde 3 et le juge, en parallèle de la ronde 4 (fichiers séparés : `app/ui/revision.tsx`,
`app/ui/styles.css`, en-tête de `app/ui/App.tsx`). Tout est décrit dans `docs/design/maquette/ANALYSE.md`
(capture de référence `docs/design/maquette/captures/revision-1440.png`). Garder toutes les fonctions existantes ;
vérifier au navigateur à 1440 et 1920 px en comparant à la capture.

## ✅ Ronde 4 (demandée par l'utilisateur le 2026-10-02) — icônes — FAITE (voir la dernière section)
Icônes comme ses exemples (verre « glassmorphism », icônes finance en verre, icônes au trait comme une poignée de main) :
1. Télécharger une grande bibliothèque d'icônes au trait LIBRE de droits (Lucide — licence ISC, ou Tabler — MIT ;
   annoncer nom, source, taille), sur D: seulement, dans `assets/banque/icones/` avec la licence.
2. Les indexer dans la banque (`engine/editeur/banque.py`) : mots-clés en français, catégories (finance, vente,
   communication, temps, téléphone…), recherche.
3. Traitement « verre » automatique pour n'importe quelle icône : tuile arrondie givrée, dégradé, reflet, lueur douce,
   couleurs de la charte ou choisies à la main (même système que les vecteurs actuels) ; versions « trait », « plein »,
   « verre » ; animation d'entrée par la chorégraphie. Rendu identique aperçu/export.
4. Dossier `assets/banque/import/` : l'utilisateur y dépose des icônes achetées (SVG/PNG) → indexées
   automatiquement avec une note de licence.
5. Tests : recoloration, 3 styles d'icône, export court regardé, banque filtrée.

## (plan initial de reprise)
1. Relancer l'éditeur avec `Editeur Sami.cmd` (nouveau lanceur). Vidéo 2 : supprimée volontairement, ne pas y toucher ;
   ronde 3 sur Vidéo 1 seulement (ou une autre vidéo si l'utilisateur en dépose une), et tests rendus indépendants
   des projets de l'utilisateur.
2. Relancer le workflow des rondes 2-3 en **reprise** : il doit d'abord finir les 2 relectures de la ronde 2 (diff contre
   `avant-ronde2/`), remettre tous les tests au vert, puis :
3. Ronde 3 — boucle d'auto-évaluation : nouvelles versions « qualité » de Vidéo 1 (et Vidéo 2 si restaurée), sans changer
   le style choisi par l'utilisateur ; export complet, contrôle, images regardées, corrections, jusqu'à 3 tours ; juge
   indépendant (correction en plus si < 8/10) ; `COMPTE-RENDU.md` ; `REPRISE.md`.
   Script du workflow (à réutiliser) :
   `C:\Users\crist\.claude\projects\D--Tools-editeur-sami\71087434-819e-4907-b372-abbc3df42b29\workflows\scripts\ronde2-ronde3-qualite-wf_c31ca459-715.js`
   (adapter le préambule « RESUMING » : ronde 2 construite, relectures à finir).
4. Questions ouvertes à l'utilisateur : « Frame » = Frame.io ? ; plans de coupe posés à la main visibles dans les styles
   avec habillage (comme les graphismes) ? ; éléments de la banque qui suivent une nouvelle charte ?

## ✅ Ronde 3 terminée (2026-10-02 vers 5 h) — ▶️ rondes 4a / 4 / 3bis lancées
- Juge indépendant : 6,5 → 7,3 → **7,6 / 10** (JUGEMENT-1 à 3) ; vidéo : `livraisons/Lot 2026-09-30 10h51/Vidéo 1 - qualité - FINAL.mp4`
  (anciens exports gardés « (ancien …) »). Limite principale : incrustation visible (tournage au bureau, lumière de fenêtre).
- Lancé à 5 h 35 : workflow `ronde4-interface-icones-finition` (`wf_d82e7e78-d6c`) = interface Révision d'après la maquette,
  icônes (Lucide + styles trait / plein / verre), finition des défauts de JUGEMENT-3, intégration (relance du serveur),
  juge n° 4. Copie d'avant : `docs/qualite-2026-09-30/avant-ronde4/`.

## ✅ Ronde 4 FAITE et intégrée (2026-10-02, vers 9 h) — `COMPTE-RENDU-RONDE4.md` (où cliquer), REPRISE.md §27
- **Interface Révision** d'après la maquette (Manrope, icônes Lucide, barre du haut commune, 4 gros boutons, carte Contrôle
  qualité, galerie « Autre style » avec « Appliquer », « Prendre » en lot, raccourcis Entrée / E / S / → / Espace / Échap).
  Relue : 10 défauts corrigés (raccourcis après un clic souris, dépôt dans la galerie, Ctrl+Z caché, vidéo gardée au retour…).
- **Icônes** : Lucide 1.49.0 (ISC, 6,8 Mo téléchargés depuis registry.npmjs.org, 1 857 icônes dans `assets/banque/icones/lucide`),
  index français (558 noms à la main, 30 catégories), styles trait / plein / verre aux couleurs de la charte, dossier
  `assets/banque/import` pour les icônes achetées. Relue : 12 défauts corrigés (gros packs, chemins longs, Illustrator / Figma…).
- **Finition de Vidéo 1** (8 défauts du juge n° 3) : nouvel export `livraisons/Lot 2026-09-30 10h51/Vidéo 1 - qualité - FINAL.mp4`
  (6 h 58, contrôle 10/10) ; anciens gardés « (ancien 2026-10-02 04h52) », « (… 06h22) », « (… 06h39) ». Relue : 6 corrections
  (bouton retouché protégé, carte avancée qui garde sa fin, apostrophes du bandeau / titre / sous-titres de carte).
- **Intégration** : type `icone` dans le serveur, la ligne de commande et le plugin ; raccourcis de l'éditeur limités à
  l'éditeur ; nom français des icônes dans la timeline ; icônes au trait « traçables » par la chorégraphie ; cadre du problème
  aux couleurs de la maquette ; test de la banque mis à jour. **Vrai serveur relancé à 8 h 41** par `editeur.ps1` (au repos,
  file vide) : un seul serveur, `/api/v2` = 200 ; vrai écran regardé à 1440 × 900 contre la maquette
  (`captures-ronde4/`).
- **Contrôles verts** (après intégration) : build, tsc 0 erreur, `node --check` serveur et MCP, **test-v2 32/32**, verification 8,
  galerie 6, cerveau créatif OK, sobriété 18, contrôle 54/54, détourage 23/23, juge1 20/20, juge2 18/18, juge3 24/24, ronde3 27/27,
  icônes OK, timeline 6, timeline-v2 71, test-juge3/2/1 18/18/19, ronde3 14/14, planche des icônes 22 329 ; Révision sur bac 39/39 +
  9/9 + 6/6 + Ctrl+Z. Nouveaux contrôles à garder dans la liste : `test-juge3.mjs`, `test_juge3.py`, `icones/test_icones.py`.

### Ce qui reste (prochaine étape)
1. **Faire rejuger Vidéo 1 (export de 6 h 58) par un juge indépendant n° 4** (jugement du monteur : ≈ 8/10).
2. Limites de la prise (mur blanc, fenêtre) : peau très claire, oreille gauche floue à 1:06,7, doigts flous sur les gestes rapides.
3. Fin en plan moyen ≈ 8 s ; place vide au-dessus du bouton 0:59,8–1:04,45 ; frappe du mot plus discrète ; coupure de ligne
   « quelqu’un à | temps plein ».
4. Une scène automatique qui chevauche une scène protégée d'un autre type peut la cacher (`verrous.fusionner` +
   `anchoredScenes` + copie Python de la chorégraphie) : corrigé pour le bouton seulement.
5. Éditeur au nouveau design (seule la barre du haut l'a) ; onglet « Système de design » absent de la maquette.
6. Questions à l'utilisateur : bouton par icône pour forcer / empêcher la recoloration d'une icône importée ? effacer les
   détourages d'essai v6 / v7 (≈ 741 Mo dans `assets/detourage`) ? (rien n'est effacé sans son accord)

## ✅ Rondes 4a / 4 / 3bis terminées (2026-10-02, 9 h 15)
- Nouvelle Révision (maquette) en place dans le vrai outil ; 1 857 icônes Lucide (trait / plein / verre) ; juge n° 4 : 7,9/10.
- Saccade du détourage corrigée par le chef d'équipe (`design.tsx`, marge 1e-3) ; export final 9 h 12 ;
  contrôle 10/10 sur la bonne version. Restes : voile le long de la mâchoire pendant l'offre, fin statique 8 s,
  incrustation (tournage au bureau). Rien d'autre en file d'attente.
