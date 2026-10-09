# Direction créative V2 — ce qui est fait (30 septembre 2026)

Pour Sami. Ce document dit, en mots simples, ce que l'éditeur sait faire de nouveau, comment l'essayer clic par clic,
ce qui a été vérifié et ce qui reste à savoir. Le détail technique est dans `SPEC.md` (même dossier) et dans
`REPRISE.md` §22.

## ⚠️ Avant d'essayer : relancer l'éditeur une fois

L'éditeur qui tourne en ce moment sur ton ordinateur date d'avant ces nouveautés. Ferme la fenêtre noire de
« Editeur Sami », puis relance **Editeur Sami.cmd**. Sans cette relance, tes notes, dessins, vecteurs et mouvements ne
seraient pas gardés (l'onglet Notes affiche alors un encadré jaune qui le dit).

## Ce qui est nouveau

1. **Notes de révision** (comme Frame.io) : tu écris une remarque sur l'image exacte. Un clic sur la note ramène à cette
   image. Chaque note a un statut (ouverte, traitée, résolue), ton nom, la date, et le contexte du montage. Si tu coupes
   le passage de la note, elle te le dit (« Passage retiré ou modifié ») au lieu de pointer ailleurs en silence.
2. **Crayon sur l'image** : crayon, flèche, cercle, surligneur, gomme, couleur, épaisseur, annuler. Le dessin reste sur
   la personne en 9:16, 16:9, 4:5 et 1:1. **Il n'apparaît jamais dans la vidéo exportée**, sauf si tu cliques
   « ⇢ Graphisme » pour en faire un vrai élément.
3. **Banque locale** : 556 ressources (490 sons, 18 modèles, 36 dessins vectoriels, 12 effets), toutes sur ton ordinateur,
   avec leur licence. Tu cherches, tu écoutes, tu cliques « + Ajouter » : l'élément se pose à la tête de lecture, sans
   cacher le visage.
4. **Dessins vectoriels recolorables** : ils prennent tout seuls les couleurs de ta charte client (ou du style). Tu peux
   choisir d'autres couleurs : un changement de charte ou de style ne les touche plus.
5. **Modèles aux couleurs de la charte** : chiffre, liste cochée, carte, mot géant suivent la charte ; une couleur choisie à
   la main est gardée.
6. **Chorégraphie** : l'IA décide comment chaque élément entre et sort (glisse, zoom, pop, fondu, tracé), sur le mot dit
   ou sur le temps de la musique, et dit pourquoi. Jamais deux entrées en même temps, rien sur l'accroche sauf le
   bandeau. Tu peux tout changer, ralentir, désactiver ou verrouiller. Les nouvelles vidéos montées automatiquement ont
   déjà leur chorégraphie.
7. **Cadenas 🔒** sur tout : ce que tu verrouilles (ou retouches) n'est plus changé par l'IA ni par un changement de style.
   Nouveau : le cadenas d'un **plan** (onglet Plan) fige ses mots en couleur et ses emojis.
8. **Refaire seulement ce passage** : tu choisis un passage dans la timeline, l'éditeur refait son habillage
   automatique sans toucher au reste de la vidéo.

## Essayer, clic par clic (après la relance)

**Ouvrir**
1. Double-clique **Editeur Sami.cmd**, puis ouvre http://127.0.0.1:8790 dans ton navigateur.
2. Clique **Éditeur complet**. Dans la liste en haut, choisis **Vidéo 2 - Version script**.

**Notes et crayon**
3. Clique l'onglet **Notes**. Il ne doit PAS y avoir d'encadré jaune « relancer ».
4. Arrête la vidéo (Espace) sur une image. Écris une remarque, puis **+ Ajouter la note** (ou Ctrl+Entrée). Une pastille
   apparaît dans la règle de la timeline et une bulle 💬 sur la vidéo.
5. Sur la note, clique **✏️ Dessiner**, trace une flèche sur la personne, puis **✓ Terminé**.
6. En haut, clique **16:9**, puis **4:5**, puis **1:1** : le dessin reste sur la personne. Reviens en **9:16**.
7. Clique ailleurs dans la timeline, puis **▶** sur la note : la vidéo revient exactement sur l'image de la note.
8. Ferme l'onglet du navigateur, rouvre http://127.0.0.1:8790 et la vidéo : la note et le dessin sont toujours là.

**Banque**
9. Clique **Plus ▾ → Banque**. Clique **Sons**, tape « whoosh », clique ▶ pour écouter.
10. Place la tête de lecture vers 0:15, puis **+ Ajouter** sur « Whoosh court ». Le son apparaît dans la piste Bruitages.
11. Clique **Modèles**, puis **+ Ajouter** sur « Liste cochée — 3 bénéfices ». Remplace les textes d'exemple par les tiens.
12. Clique **Vecteurs**, puis **+ Ajouter** sur « Étoile ».

**Couleurs et charte**
13. Onglet **Style** → **Charte client** : choisis (ou crée) une charte avec une couleur d'accent. L'étoile, le chiffre et
    les mots en couleur prennent cette couleur.
14. **Plus ▾ → Graphismes** : ouvre la liste cochée (**Modifier**), choisis une autre **Couleur**. Change encore de charte :
    la liste garde ta couleur, le reste suit la charte. **🎨 Couleur de la charte** la fait de nouveau suivre la charte.
15. Plus bas, carte **Vecteurs** : même chose pour l'étoile (couleur principale, secondaire, contour).

**Verrous**
16. Dans **Plus ▾ → Graphismes**, clique le cadenas 🔓 d'un élément : il devient 🔒 (aussi dans la piste Graphismes).
17. Onglet **Style** : change de style de montage, puis reviens. L'élément verrouillé n'a pas bougé.
18. **Plus ▾ → Plan** : clique **🔓 Verrouiller** sous le texte du plan : ses mots en couleur et emojis sont figés.

**Chorégraphie**
19. **Plus ▾ → Chorégraphie** → **Créer** (ou **Refaire**) **la chorégraphie**. Attends « ✓ Chorégraphie refaite ».
20. Dans la piste **Chorégraphie** en bas, clique un bloc : une petite fenêtre montre la raison de l'IA. Essaie
    **Plus lent**, change l'entrée, puis clique le cadenas.
21. Clique **Refaire la chorégraphie** : ton mouvement verrouillé reste tel quel.

**Refaire seulement ce passage**
22. Dans la timeline, place la tête de lecture au début d'un passage et appuie sur **I** (ou **Début ici**), avance, puis
    **O** (ou **Fin ici**). Une bande jaune montre le passage.
23. Clique **Refaire seulement ce passage**. La bulle dit ce qui a été refait et « Rien n'a bougé avant ni après ».
    **Annuler ce passage** remet tout exactement comme avant.

**Export**
24. Exporte comme d'habitude : ni les notes ni les dessins ne sont dans la vidéo ; les sons, vecteurs, modèles et
    mouvements y sont, comme dans l'aperçu.
25. Ctrl+Z annule n'importe quelle retouche (sauf un passage refait : utilise « Annuler ce passage » ou l'onglet Versions).

## Ce qui a été vérifié (sur des copies, jamais sur tes vraies vidéos)

Tous les tests sont rejoués par une seule commande : `node docs/direction-creative-v2/tests/test-v2.mjs`.
Les 11 tests obligatoires de la passation sont verts :

| Test obligatoire | Preuve |
|---|---|
| Une note revient à la bonne image après fermeture et réouverture | serveur arrêté puis relancé : mêmes images ; dans l'interface, clic sur la note → 0:15.3 (note à 15,2 s) |
| Un dessin reste aligné en 9:16, 16:9, 4:5 et 1:1 | écart mesuré < 0,02 px ; même point de la prise dans les 4 formats |
| Notes et dessins absents d'un export normal | 4 exports : 0 pixel magenta là où les dessins seraient (26 910 pixels dans l'aperçu) |
| Un dessin vectoriel multicolore se recolore sans perdre formes ni animation | 36 dessins, 1152 vérifications ; export mesuré |
| Une charte recolore un modèle, puis une retouche reste | export : chiffre et étoile roses (charte A) puis verts (charte B) ; liste et cœur retouchés restent bleus |
| La banque filtre effets, sons, vecteurs, modèles avec aperçu | 556 entrées, filtres, aperçus servis, parité moteur / interface |
| La chorégraphie ne place jamais deux éléments concurrents | vérifié sur un reel complet, après 4 styles, après « Refaire », sur 2 montages automatiques |
| Une retouche verrouillée survit à une passe de l'IA et à un changement de style | cerveau créatif, galerie, relecture, chorégraphie, IA, 5 styles, 2 chartes |
| « Refaire seulement ce passage » ne change rien hors de la plage | tout ce qui est hors de la plage identique ; dans la plage, un élément en conflit est bien relu |
| Les anciennes vidéos fonctionnent | 13 anciens reels : calculs identiques à avant ; 7 reels du projet : aucune donnée nouvelle ajoutée |
| Aperçu court regardé, son et timecodes | images regardées (planche), whoosh à 15,000 s dans le son, 120 images = 4,000 s, aucun écrêtage |

## À savoir (limites honnêtes)

- Les dessins vectoriels restent à leur place dans l'image : ils ne suivent pas la personne si elle bouge.
- Les dessins de révision ne marchent que sur la vidéo principale (pas sur un plan de coupe par-dessus).
- Le crayon à main levée ne se transforme pas en graphisme (flèche, cercle et surligneur oui).
- « Refaire seulement ce passage » ne cherche pas de nouveaux plans de coupe ; Ctrl+Z ne l'annule pas (bouton
  « Annuler ce passage »).
- Les effets de la banque (grain, look cinéma, flash) s'appliquent à toute la vidéo.
- Les scènes du style posées depuis la banque gardent la couleur de la charte du moment où tu les poses.
- « Refaire » dans l'écran Révision refait un montage complet : les verrous ne sont pas reportés (l'ancienne version est
  gardée dans Versions).
- La chorégraphie de l'IA suit des règles (rôle du passage, mots, musique) : elle est sobre exprès ; à toi de la rendre
  plus vive si tu veux.
