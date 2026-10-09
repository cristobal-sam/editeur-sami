# Maquette « Révision » (Claude Design) — à reproduire dans l'outil

Source : `C:\Users\crist\Downloads\Révision vidéo.html` (export « bundled » de Claude Design, 3,6 Mo, tout est dedans),
copiée ici : `Révision vidéo.html` et `revision-maquette.html` (même fichier, nom sans accent).
Capture de référence 1440 × 900 : `captures/revision-1440.png` (faite avec le Chrome sans écran de Remotion :
`remotion/node_modules/.remotion/chrome-headless-shell/.../chrome-headless-shell.exe --headless --window-size=1440,900
--virtual-time-budget=8000 --screenshot=... http://127.0.0.1:8899/revision-maquette.html`, en servant le dossier avec
`python -m http.server 8899 --bind 127.0.0.1 --directory docs/design/maquette`).

Seul l'écran **Révision** est dans l'export. Les liens « Éditeur » et « Système de design » pointent vers d'autres
fichiers (`Éditeur.dc.html`…) qui ne sont pas fournis ; « Autre style » n'ouvre rien dans la maquette.

## Jetons de design relevés
- Police : **Manrope** (déjà dans `assets/fonts/Manrope.ttf`), icônes **Lucide** (police d'icônes dans la maquette ;
  dans l'outil, utiliser des SVG Lucide — licence ISC — ou les icônes existantes).
- Fond `#090B0F` / `#0A0C10`, panneaux `#0A0F1A`, texte `#E8ECF2`, texte secondaire `#9AA3B2` / `#7D8696` / `#C9D0DB`,
  accent **cyan `#38E1FF`** (texte sur cyan `#04121A`), violet `#8B5CF6` / `#A78BFA` / `#C4B5FD` (IA, « Autre style »),
  vert `#34D399` (prêt, bonne note), orange `#FB923C` (important), rouge `#F87171` (bloquant / mauvaise note).

## Disposition (1440 × 900)
- **Barre du haut** : logo « S » + « Éditeur Sami » ; onglets Révision (actif) · Éditeur · Système de design ;
  à droite « Aujourd'hui · 7 vidéos », « ● 3 prêtes », « ● 1 prises », bouton réglages, pastille « SA ».
- **Colonne gauche (~345 px)** : carte en pointillés « Ajouter des vidéos brutes / Glisse tes fichiers ici » avec
  « Choisir des vidéos », « Choisir un dossier », menu « Charte client : Sans charte client », phrase d'aide ;
  « VIDÉOS DU JOUR » + « Choisir plusieurs » ; cartes vidéo (miniature verticale, titre, sujet, état avec pastille :
  « Prête à regarder » vert, « En montage 45 % » violet + barre, « En file » gris ; **note /10 en badge** vert ou rouge) ;
  carte sélectionnée encadrée cyan ; en bas « Corbeille (3) » et « Ouvrir le dossier Entrée ».
- **Centre** : lecteur vertical arrondi « Aperçu vidéo · 9:16 », bouton lecture rond au centre, barre de lecture
  (0:12 / 1:08, volume) sous le lecteur.
- **Droite** : titre (gros, gras), ligne « Sujet : … — style : … — 1:08 — 5 plans » ; **4 gros boutons** :
  « ✓ Je la prends » (cyan plein, raccourci Entrée), « ✏ Modifier » (E), « 🎨 Autre style » (violet, S),
  « Suivante › » (→) ; raccourcis affichés au survol ; « Formats d'export » en pastilles cochables (9:16 vertical,
  16:9 horizontal, 4:5 publication, 1:1 carré) ; **carte Contrôle qualité** : grande note « 8,6 / 10 » verte,
  « CONTRÔLE QUALITÉ », verdict, bouton « Relancer le contrôle », lignes de problèmes : étiquette (« ⚠ Important »
  orange, « 💡 Conseil » gris), temps cliquable « ▶ 0:26 » (cyan), texte + suggestion après « → ».

## À reproduire dans le vrai code
`app/ui/revision.tsx` + `app/ui/styles.css` (+ l'en-tête dans `app/ui/App.tsx`), en gardant TOUTES les fonctions
existantes (dépôt, charte, liste, sélection multiple, suppression 🗑️, corbeille + restaurer, galerie « Autre style »
avec filtres et styles personnels, « Toujours ce style », « Enregistrer comme mon style », formats, exports par format,
contrôle qualité et problèmes cliquables, alertes du script, erreurs). Les compteurs de la barre du haut viennent de
`/api/revision`. Vérifier au navigateur (capture 1440 × 900 comparée à `captures/revision-1440.png`) et à la
largeur 1920.
