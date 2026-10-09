# Prompt — nouvelle interface de l'Éditeur Sami

> À coller tel quel dans l'outil de design. Le résultat sert de maquette : il sera ensuite reproduit dans le vrai
> code de l'outil (React), donc il doit garder exactement les écrans et les boutons décrits ici.

---

Conçois l'interface complète d'une application de bureau appelée **« Éditeur Sami »** : un monteur vidéo
**automatique** pour un entrepreneur québécois (pas un monteur professionnel) qui doit livrer **environ 20 pubs
courtes par jour** (Reels, TikTok, YouTube Shorts). L'outil monte les vidéos tout seul ; l'utilisateur regarde,
accepte ou corrige. Toute l'interface est **en français (Québec)**, avec des mots simples, sans jargon technique.

## Direction visuelle
- Thème **sombre premium**, inspiré du « glassmorphism » : panneaux en verre givré légèrement transparents, reflets
  subtils, lueurs douces, coins arrondis (12-16 px), ombres profondes et douces. Ambiance « studio tech » haut de gamme
  (penser Linear, Raycast, Frame.io, CapCut Pro), jamais chargée.
- Couleur d'accent : **cyan lumineux (#38E1FF)** + un second accent **violet (#8B5CF6)** pour les éléments IA ;
  vert pour « prêt / bon », orange pour « à vérifier », rouge pour « bloquant ».
- Typographie moderne et lisible : **Manrope** (ou Inter) ; titres semi-gras, chiffres tabulaires pour les temps.
- Icônes au trait fines et cohérentes (style Lucide), quelques icônes en version « verre » pour les actions principales.
- Format principal : écran de bureau **1440 × 900** ; prévoir aussi la version **1920 × 1080**. Les vidéos sont
  surtout **verticales 9:16**.
- Animations sobres (survol, apparition des cartes) ; tout doit rester rapide et clair.

## Écran 1 — « Révision » (écran d'accueil, le plus important)
But : en un coup d'œil, voir les vidéos du jour et décider vite.
- **Colonne de gauche** :
  - Zone de dépôt « Ajouter des vidéos brutes » : glisser-déposer, boutons « Choisir des vidéos » et « Choisir un
    dossier », menu « Charte client » (ex. « Sans charte client »). Phrase d'aide courte : « Une vidéo = une vidéo à
    monter ; un dossier = plusieurs prises d'une même vidéo, avec son script. L'outil trouve le sujet et monte tout seul. »
  - Liste des vidéos en cartes : miniature verticale, titre (ex. « Répondez vite à vos leads »), sujet détecté
    (ex. « Marketing / pub »), état avec pastille de couleur (En file · En montage 45 % avec barre · Prête à regarder ·
    Prise · Erreur), **note qualité /10** (ex. « 8,2 »), petite icône 🗑️ au survol. Bouton « ☑ Choisir plusieurs ».
  - En bas : « Corbeille (3) » et « Ouvrir le dossier Entrée ».
- **Zone centrale** (la vidéo sélectionnée) :
  - Grand lecteur vertical avec timecode, lecture/pause, son.
  - Titre + une ligne « Sujet : Marketing / pub — style : Tech 3D cinématique — 1:08 — 5 plans ».
  - **Quatre gros boutons** : « ✅ Je la prends » (principal, jaune ou cyan plein), « ✏️ Modifier », « 🎨 Autre style »,
    « Suivante ▸ ».
  - Cases des formats d'export : 9:16 vertical (coché), 16:9 horizontal, 4:5 publication, 1:1 carré.
  - **Carte « Contrôle qualité »** : grande note « 8,2 / 10 », verdict en une phrase, liste des problèmes classés
    (bloquant / important / conseil), chacun avec son moment cliquable « ▶ 0:26 » et une suggestion
    (ex. « Image figée pendant 7 s → ajouter un zoom lent »). Bouton « Relancer le contrôle ».
  - Alertes du script (ex. « 2 phrases du script ne sont pas dans les prises »).
  - Suivi des exports : par format, barre de progression, puis « Ouvrir le fichier ».
- **Volet « Autre style »** (s'ouvre sous ou à côté du lecteur) : **galerie de styles** façon « Explore templates » :
  filtres (Tous, Pub, UGC, Témoignage, Tech, Produit, Cinéma, Motion), cartes verticales avec aperçu animé au survol
  (« Éditorial cinétique », « Hormozi », « Tech / application », « Infographie », « Documentaire », « Collage »,
  « Luxe / minimal », « Rétro VHS », « Comparatif », « Tech 3D cinématique », styles personnels marqués « mon style »
  avec Renommer / Supprimer), carte « + Style depuis une vidéo » (déposer un reel modèle), bouton « Revenir au style
  précédent », champ « Enregistrer comme mon style », bouton « 📌 Toujours ce style pour Marketing / pub ».

## Écran 2 — « Éditeur » (quand on clique « Modifier »)
- **En-tête** : « ← Révision », titre de la vidéo, choix de la version (ex. « script », « qualité », « 30 s »),
  sélecteur de format 9:16 / 16:9 / 4:5 / 1:1, comparaison A/B, annuler / rétablir, état « Enregistré ».
- **Centre** : lecteur vertical avec, au-dessus, une **barre d'outils de révision** façon Frame.io : « + Note à cette
  image », crayon, flèche, cercle, surligneur, couleur, épaisseur, annuler, masquer les dessins. Les dessins apparaissent
  par-dessus l'image (jamais dans l'export).
- **Panneau de droite à onglets** (simples d'abord) : **Texte** (les phrases, mots en couleur cliquables, couper un mot =
  couper la vidéo, propositions de l'IA en pointillé à accepter / refuser), **Style** (style de montage, charte client,
  sous-titres, musique, bruitages, voix débruitée), **Ajouter** (plans de coupe, banques d'images, « Direction créative »
  avec les moments du récit cliquables) et un menu **« Plus »** : Plan, Graphismes, **Notes**, **Banque**,
  **Chorégraphie**, Conseils, Versions, Export.
- **Onglet Notes** : liste des notes avec timecode (00:15:08), texte, auteur « Sami », date, statut
  (ouverte / traitée / résolue), filtre par statut, clic = retour à l'image exacte ; mention « passage retiré ou modifié »
  si le montage a changé.
- **Onglet Banque** : recherche + filtres (Effets, Sons, Vecteurs, Icônes, Templates ; catégorie ; intensité 1-3) ;
  grille d'aperçus (bouton lecture pour les sons, aperçu pour les vecteurs et icônes, carte animée pour les templates),
  bouton « Ajouter à l'instant courant », pastille de licence.
- **Réglages d'un vecteur ou d'une icône** : couleurs principale / secondaire / contour, bouton « Couleurs de la
  charte », style trait / plein / verre, opacité, taille, position, rotation, durée, animation d'entrée et de sortie,
  **cadenas 🔒 « Verrouiller »**.
- **Onglet Chorégraphie** : liste des mouvements (entrée / sortie, type, direction, durée, courbe, « raison » écrite par
  l'IA), boutons ralentir / accélérer / désactiver / verrouiller, bouton « Refaire la chorégraphie (garde ce qui est
  verrouillé) ».
- **Timeline en bas** (pleine largeur, pistes empilées, zoomable) : temps, rythme (💡 conseils), image (plans), plans
  de coupe, voix, musique, bruitages, graphismes et vecteurs, **chorégraphie**, **notes** (repères). Sélection d'une plage
  avec « Début ici » / « Fin ici » et bouton **« Refaire seulement ce passage »** (avec « Annuler »).
- Chaque élément de la timeline peut porter un petit cadenas 🔒 ; un élément retouché à la main est marqué d'un point.

## États à montrer
- Révision vide (premier lancement) avec un grand appel à déposer des vidéos.
- Une vidéo en montage (progression + étape en clair : « Écoute et analyse des prises »).
- Une vidéo prête avec une bonne note (8,6) et une avec un problème bloquant (rouge).
- Un export en cours en 2 formats.
- L'éditeur avec une note et un dessin au crayon visibles sur l'image.
- Messages d'erreur clairs et rassurants (ex. « Le fichier de la prise “3.MP4” est introuvable : clique Refaire »).

## Contraintes
- L'utilisateur n'est pas monteur : l'écran Révision doit se comprendre en 5 secondes ; les options avancées restent
  derrière « Modifier » et « Plus ».
- Lisibilité d'abord : contraste suffisant, textes ≥ 13 px, cibles cliquables ≥ 36 px, raccourcis clavier affichés au
  survol (Espace = lecture, I / O = début / fin du passage, N = note).
- Pas de faux logo de marque existante ; marque fictive pour les exemples : « RyuCalls ».
- Livrer : les maquettes des écrans 1 et 2 avec leurs états, une page « système de design » (couleurs, typographie,
  boutons, cartes, pastilles d'état, carte de style, carte de contrôle qualité, pistes de timeline, icônes trait / verre).
