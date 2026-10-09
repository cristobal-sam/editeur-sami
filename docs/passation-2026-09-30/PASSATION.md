# Passation — Éditeur Sami — 2026-09-30 (fin de journée)

> **Mise à jour après reprise Codex** : ce document conserve l'état initial de l'arrêt. Pour les corrections, tests et limites des six chantiers, lire `VERIFICATION-CODEX.md` et `REPRISE.md` §16.

> Pour la personne ou l'IA qui reprend le travail. Lire d'abord `CLAUDE.md` puis `REPRISE.md` (architecture,
> formats, pièges), puis ce document (état exact de ce qui était en cours quand tout a été arrêté).

## 0. Règles à respecter absolument

- Répondre en **français** (utilisateur au Québec, entrepreneur, pas monteur pro, ~20 vidéos/jour).
- Ne **jamais** modifier `D:\Y0U`. Tout reste dans `D:\Tools\editeur_sami` (rien sur C:).
- **Ne jamais lire, afficher ni envoyer** `D:\Tools\editeur_sami\cles-api.env` (vraie clé Pixabay de l'utilisateur).
- Aucune API payante, aucun service en ligne, sauf Pixabay (demandé : seuls des mots clés sont envoyés).
  Pas de Pexels sans clé, pas de « scraping ». Aucun téléchargement / installation sans permission explicite.
- Un seul reel à la fois ; pas de long montage ni d'export complet sans demande ; tests courts.
- Ne pas supprimer les fichiers de l'utilisateur sans accord.
- Charger l'environnement avant toute commande : `source runtime/env.sh` (bash) ou `. .\runtime\env.ps1`.
- Python écrit via heredoc bash = antislashs cassés : utiliser l'outil d'édition de fichiers.
- `remotion/src/timeline.ts` ne doit importer QUE des types.

## 1. État au moment de l'arrêt

- **Tout est arrêté** : serveur de l'éditeur (port 8790) arrêté, les 6 agents de travail arrêtés en plein milieu.
  Aucun processus llama/python/ffmpeg de l'outil ne tourne. (`runtime/cache/llama-8791.json` est un reste sans
  processus : le code le gère, PID mort = ignoré.)
- **Le code actuel se charge sans erreur** (vérifié après l'arrêt) :
  - `python -c "import editeur.declinaison, editeur.reel, editeur.llm, editeur.pdftexte, editeur.script, editeur.auto, editeur.style_ref"` → OK
  - `node --check app/server.mjs` → OK
  - `node app/build.mjs` → OK ; `tsc -p tsconfig.verif.json` → seulement les 4 erreurs anciennes connues
    (`react-dom/client` sans types + 3 × `premountFor`/`layout="none"` dans `remotion/src/Reel.tsx`, fichier non modifié).
- **Mais les changements des 6 chantiers sont à moitié finis et NON revus.** Copie du code d'AVANT ces chantiers :
  `docs/passation-2026-09-30/avant/` (`editeur/` = engine/editeur, `app/ui`, `app/server.mjs`, `remotion-src/`,
  `styles/`). Faire `diff -ru docs/passation-2026-09-30/avant/editeur engine/editeur` (etc.) pour voir tout ce qui a changé.
  Si un chantier pose problème, on peut remettre le fichier d'avant depuis ce dossier.
- Tests écrits par les agents : `docs/passation-2026-09-30/tests/` (decl, hl, pdf, plugin-mcp, test-styles-ui, musique).
  Ils peuvent contenir des chemins vers l'ancien dossier temporaire (`C:\Users\crist\AppData\Local\Temp\claude\...`) :
  les adapter vers `docs/passation-2026-09-30/...` avant de les relancer.
- Bacs à sable de test (peuvent être supprimés quand plus utiles) : `runtime/cache/tmp/decl-reancrage/` (copie de
  projects/video1), `runtime/cache/tmp/musique-eval/` (154 Mo de mélanges audio de test), `runtime/cache/tmp/ref-whatsapp/`.
- Pour relancer l'outil : double-clic sur `Editeur Sami.cmd` (ou `.\editeur.ps1`) → http://127.0.0.1:8790

## 2. Déjà fait et vérifié plus tôt aujourd'hui (avant les 6 chantiers)

- **Interface simplifiée « Révision »** (écran par défaut) : déposer des vidéos (glisser-déposer, fichiers ou dossiers) →
  chaque vidéo est analysée (type pub/témoignage/conseil/… par l'IA locale) et montée seule dans le style associé
  (`styles/types.json`) → boutons ✅ Je la prends / ✏️ Modifier (ouvre l'éditeur complet) / 🎨 Autre style / Suivante,
  📌 « Toujours ce style pour <type> », alertes (phrases du script absentes…). Moteur : `python -m editeur auto <unité>`
  (`engine/editeur/auto.py`), file côté serveur (`pumpAuto`, une vidéo à la fois), registre `projects/_revision.json`,
  entrée `media/entree/<lot>/`, livraison `livraisons/<lot>/`.
- **Style par référence** (`engine/editeur/style_ref.py`, commande `style-ref`, carte dans Révision) : mesure coupes,
  zooms, couleur, sous-titres (vision Qwen), musique → `styles/montage/ref-<nom>.json`.
- **Banques d'images** (`engine/editeur/banques/`) : Pixabay actif, Pexels inactif sans clé ; cache 24 h ; licences en
  `.json` à côté ; onglet « Ajouter » dans l'éditeur ; plans de coupe « plein écran » ou « encadré ».
- **Son** : débruitage RNNoise + expandeur ; écart voix/bruit mesuré sur `media/rushs/Vidéo 1/2.MP4` : 6,8 dB (ancienne
  chaîne) → **30,1 dB** ; export à −14 LUFS, crête vraie −1,3 dB ; l'aperçu joue la voix nettoyée.
- **Robustesse** : lanceur double-clic, erreurs en français (`runtime/cache/erreurs.log`, `erreurs-serveur.log`),
  vidéo sans son, rotation par vote image par image, ordre accroche → corps → appel à l'action en mode sans script,
  correction de Whisper par le script, bandeaux inventés refusés, écriture JSON atomique, partage du serveur IA entre
  processus (compteur d'utilisateurs), anglais pris en charge, noms de projets sans collision.
- Serveur redémarré avec ce code et `/api/revision` répondait (liste vide) — puis arrêté à la demande de l'utilisateur.

## 3. Les 6 chantiers interrompus : où ils en sont, ce qui manque, résultat attendu

### 3.1 Déclinaisons (versions 60/30/15 s) — `engine/editeur/declinaison.py` (≈ 400 lignes changées)

- **But** : quand on coupe des phrases pour faire une version courte, les éléments placés dans le temps (graphismes,
  plans de coupe V2, bruitages ajoutés `sfx.extra`, bandeau…) doivent suivre leurs mots ; ceux dont les mots sont coupés
  disparaissent ; rien ne dépasse la nouvelle fin ; le logo / la carte de fin / l'appel à l'action restent à la fin ;
  pas de plan de coupe sur la phrase d'accroche ni sur la dernière phrase de l'appel à l'action ; le bandeau reste
  dans l'accroche.
- **Fait** : nouvelles fonctions `_reanchor`, classe de correspondance ancien temps → nouveau temps (`_seg_at`, `exact`,
  `anchor`, `place`, `until`), `_fit`, `_carries` ; `create()` renvoie en plus `elements` = `{deplaces, raccourcis,
  retires}` et `elements_resume` (messages en français). L'agent a corrigé un bug de la notation par l'IA locale
  (`_importance`) et testait « 30 s avec l'IA » au moment de l'arrêt. Test : `tests/decl/test_reancrage.py`.
- **À vérifier** :
  1. Relire le diff complet ; relancer `test_reancrage.py` (sur une COPIE de projects/video1, jamais le vrai dossier)
     pour 60 / 30 / 15 s, « rapide », « émotion », avec et sans IA.
  2. Vérifier numériquement que chaque élément gardé commence sur le même mot qu'avant, que les retirés sont bien ceux
     des phrases coupées, que rien ne dépasse la durée.
  3. Vérifier que l'interface (onglet Versions → déclinaisons, `app/ui/panels2.tsx`) ne casse pas avec le nouveau champ
     de retour et, idéalement, affiche `elements_resume`.
- **Résultat attendu** : une déclinaison 30 s de video1 où graphismes et plans de coupe tombent sur les mêmes mots
  qu'avant, accroche et appel à l'action intacts, logo et carte de fin présents.

### 3.2 Mots surlignés (mots en couleur) — `engine/editeur/reel.py` (≈ 440 lignes), `engine/editeur/llm.py` (≈ 120)

- **But** : mieux choisir les mots en couleur (chiffres avec leur unité, bénéfice, douleur, marque, verbes forts),
  environ un par groupe de sous-titres, jamais de petits mots, pas deux collés, français et anglais.
- **Fait** : listes de mots (STOP_FR, STOP_EN, WEAK, NUMBERS, UNITS, STRONG, CTA_WORDS, EXPRESSIONS), `caption_groups`,
  `_units` (blocs « cinq fois moins cher », « trois heures », « En savoir plus »), nouveau `auto_highlights(words,
  max_words, language, context, picks)`, `reel_highlights`, `_theme`, `_brands` ; branché dans `_editorial`,
  `_clip_doc`, `suggestions_from`, `refresh_ai`, `ensure` ; côté IA : `editorial(clips, language, max_words)` + `_locate`.
  Mesures avant/après (règles seules) : `tests/hl/avant_regles.txt` → `tests/hl/nouveau4.txt` :
  video1 v1 = 24/63 groupes avec un mot en couleur → 43/63.
- **Points à juger** : il y a maintenant peut-être TROP de mots en couleur (56 mots sur ~300 pour v1) ; des blocs
  entiers sont colorés (« combien de temps », « En savoir plus » deux fois) et des mots faibles passent encore
  (« répondre », « question », « fortes », « commencer », « une semaine »). Le chemin avec l'IA n'avait pas encore été
  mesuré (`tests/hl/nouveau_ia.txt` est peut-être incomplet).
- **À vérifier** : relancer `tests/hl/mesure.py` (règles seules + IA sur 1-2 reels, en mémoire, sans écrire dans les vrais
  reels) ; vérifier les cas vides / un seul mot / anglais ; vérifier que les appelants de `auto_highlights` dans les autres
  modules (`grep -rn auto_highlights engine/`) utilisent la nouvelle signature ; que `suggestions.words` garde le même
  format `{clip: [indices]}`.
- **Résultat attendu** : ≈ 1 mot (ou bloc court) en couleur par groupe affiché, seulement des mots porteurs de sens,
  jamais deux groupes de suite colorés en entier.

### 3.3 Interface : « Je la prends » en plusieurs formats + gestion des styles et chartes
Fichiers : `app/server.mjs` (≈ 290 lignes), `app/ui/revision.tsx` (≈ 210), `panels2.tsx` (≈ 140), `panels.tsx`, `App.tsx`,
`styles.css`.

- **Fait (compilé, jamais essayé dans le navigateur, serveur jamais relancé avec)** :
  - « ✅ Je la prends » : cases 9:16 / 16:9 / 4:5 / 1:1 → un export par format (`item.exports`), état de chacun.
  - `POST /api/styles` = « Enregistrer comme mon style » (champs `TEMPLATE_FIELDS` du reel → `styles/montage/<id>.json`).
  - `/api/styles/<id>` (supprimer) et `/api/styles/<id>/renommer` : seulement les styles de l'utilisateur ; les styles
    fournis (`BUILTIN_STYLES`) sont protégés ; suppression = déplacement dans une corbeille ; si `types.json` pointait
    vers le style supprimé, retour au style par défaut (`DEFAULT_TYPE_STYLES`).
  - `/api/clients/<id>` : suppression d'une charte client (corbeille).
  - Tests isolés : `tests/test-styles-ui/test.mjs`, `roundtrip.mjs`.
- **À vérifier** :
  1. Relire le diff de `server.mjs` : protection par l'origine exacte `http://127.0.0.1:8790` sur les nouvelles routes
     POST/DELETE ; noms sûrs (`safeId`, pas de `..`) ; vérifier que le nom de la corbeille ne s'affiche pas comme un style
     (`reel.list_templates` et `styles()` du serveur ne doivent pas lister `_corbeille`) ; compatibilité avec l'ancien
     `item.export` (un seul format) dans `projects/_revision.json`.
  2. Relancer le serveur puis tester dans le navigateur : Révision → vidéo prête → cocher 9:16 + 16:9 → « Je la prends »
     → deux exports dans la file, chacun avec son état et son fichier dans `livraisons/<lot>/` ; relancer le serveur
     pendant un export → état « interrompu » ; Style → « Enregistrer comme mon style » → apparaît dans la liste et dans
     « Autre style » ; supprimer ce style (confirmation) → disparaît, fichier dans la corbeille ; essayer de supprimer un
     style fourni → refusé ; supprimer une charte client de test.
- **Résultat attendu** : tout marche en français, rien n'est supprimé pour de vrai (corbeille), aucun style fourni ne peut
  être effacé.

### 3.4 Scripts en PDF — `engine/editeur/pdftexte.py` (NOUVEAU, 1200 lignes, lecteur PDF sans bibliothèque)

- **Fait** : extraction du texte (`pdftexte.texte(chemin)`, aussi `lignes`, `paragraphes`, erreur `ErreurPdf`) :
  objets, flux compressés, encodages MacRoman/WinAnsi/Standard, ToUnicode, écarts TJ → espaces. Essayé après l'arrêt sur
  `media/rushs/test-pratique/EditStock Free Sample From Bingo Night/Paperwork/Bingo Night Script.pdf` : **le texte sort
  correctement** (noms des personnages, dialogues, didascalies ; une apostrophe « Ma’am » à vérifier).
- **Pas fait** :
  1. `engine/editeur/script.py` (ligne ~33) refuse encore les `.pdf` (SystemExit avec un message) → brancher `pdftexte`.
     `auto.py` (lignes ~190 et ~222) affiche aussi l'alerte « Script non lu (…) : enregistre-le en .docx ou .txt » : à adapter.
  2. Conversion **format scénario → dialogues** : retirer INT./EXT., didascalies, « (CONTINUED) », « CONTINUED: 14. »,
     numéros de page, didascalies entre parenthèses ; transformer « NOM » + réplique en « NOM: réplique » (format déjà
     accepté par le lecteur .txt). Comparer au fichier fait à la main
     `media/rushs/test-pratique/script-bingo-night.txt` (mêmes répliques attendues).
  3. `engine/editeur/auto.py` → `find_script` : accepter `.pdf`, préférer `.docx`/`.txt` quand les deux existent.
  4. Tester les 2 autres PDF du dossier (lettre, licence : pas des scripts, ne doivent pas planter) et la non-régression
     `.docx` (`tests/pdf/avant-docx.json`, `avant-ref.json` = sorties d'avant).
- **Résultat attendu** : déposer le dossier Bingo avec son PDF → le script est reconnu, les répliques sont alignées sur les
  prises comme avec le .txt.

### 3.5 Détection de la musique du « style par référence » — `engine/editeur/style_ref.py` (NON modifié)

- **Fait** : seulement un banc d'essai dans `runtime/cache/tmp/musique-eval/` (scripts copiés dans `tests/musique/`) :
  mélanges voix réelle + chacune des 12 musiques de `assets/music` à −16/−22 dB, versions décalées en tempo/hauteur, voix
  seule, musique seule. L'agent mesurait la référence de départ et explorait : estimation de la voix par RNNoise,
  bandes où la musique domine, variantes de calcul du tempo. Un piège trouvé : les pistes sont en 48 kHz
  (`asetrate` doit partir de 48000).
- **À faire** : relancer `evaluate.py` pour avoir les chiffres de départ (présence de musique, erreur de tempo, bonne
  ambiance top-1 / top-3) ; améliorer `_audio` / `_mood` (retirer la voix, plusieurs mesures normalisées comparées aux
  musiques de la bibliothèque analysées de la même façon, indice de confiance, repli sur tempo/énergie) ; donner les
  chiffres avant/après.
- **Résultat attendu** : la bonne ambiance musicale dans le top-3 la plupart du temps, « pas de musique » bien reconnu,
  confiance indiquée dans la description du style.

### 3.6 Plugin « Éditeur Sami » pour piloter l'outil depuis Claude

- **Fait** : `plugins/editeur-sami/` (`.claude-plugin/plugin.json`, `.mcp.json` → `node ${CLAUDE_PLUGIN_ROOT}/mcp/serveur.mjs`,
  serveur MCP sans dépendance de 47 Ko), compétences `skills/editeur-sami` (mode d'emploi) + `monter`, `revision`,
  `style`, `prendre`, `reference` ; catalogue local `.claude-plugin/marketplace.json` (nom `editeur-sami-local`).
  Outils MCP : `etat`, `monter`, `styles`, `changer_style`, `toujours_ce_style`, `refaire`, `retirer`, `prendre`,
  `suivre_export`, `style_reference`, `ouvrir`, `erreurs`. Il y a un interrupteur pour empêcher le démarrage auto du
  serveur pendant les tests. Test : `tests/plugin-mcp/test-mcp.mjs` (était en cours).
- **Pas fait** : `.claude/settings.json` du projet (pour que le catalogue et le plugin apparaissent « Dans ce projet ») ;
  validation (`claude plugin validate plugins/editeur-sami` si la commande existe) ; vérification que chaque route citée
  existe dans `server.mjs` (qui a lui-même changé au 3.3 : `prendre` accepte maintenant plusieurs formats) ; relecture
  du mode d'emploi.
- **À vérifier** : lancer le serveur MCP, envoyer `initialize`, `tools/list`, puis `tools/call` des outils en lecture seule
  (`etat`, `styles`, `erreurs`) contre l'éditeur lancé ; pour `monter`/`prendre`/… tester seulement les erreurs
  d'arguments (sinon de vrais montages/exports démarrent). Le serveur MCP ne doit jamais lire `cles-api.env`.
- **Résultat attendu** : dans l'appli Claude, fenêtre Plugins → « Les vôtres » → « Dans ce projet », le plugin
  Éditeur Sami apparaît et s'active (étapes exactes à confirmer dans la documentation officielle des plugins) ; « /monter <dossier> » lance les montages automatiques, « /revision » donne l'état.

## 4. Autres tâches restantes (déjà prévues)

1. Test complet de l'écran Révision dans le navigateur : déposer 1 vidéo courte → montage auto → lecture →
   « Je la prends » (court). Surveiller le GPU (Whisper + IA locale).
2. Refaire le style `styles/montage/ref-monmontageryucalls.json` avec le nouveau détecteur de coupes (il a été créé
   avec l'ancien : « 2 coupes/min » probablement faux) : `python -m editeur style-ref "livraisons/SAM SCRIPT ADS
   2026-08-11/Vidéo 1 - 0 COMPLET - Hook alternatif 1 (Est-ce que vous savez précisément) - FINAL.mp4" --nom="Mon montage RyuCalls"`
   (utilise l'IA vision, port 8792).
3. Mettre `REPRISE.md` à jour avec tout ce qui précède (fait en partie : voir son §15).
4. Petites dettes : `export.py` peut annoncer un succès sans fichier ; `edit.py` obsolète ; `derush --style` passe
   encore par l'ancien calcul de livraison ; deux onglets ouverts = conflit (409) ; espace disque ; Node non portable
   (installé dans C:\Program Files\nodejs) ; lot avec un script à la racine + vidéos sans rapport ; images Pixabay 1280 px
   max ; images de la bibliothèque b-roll pas proposées automatiquement ; export Resolve (OTIO) sans le mode encadré ni
   les images fixes.
5. Le dossier `projects/scriptbingonightvideo1` existe (reste d'un essai de dérushage de la scène Bingo) : ne pas le
   supprimer sans demander.
6. **Ensuite seulement** : le montage d'essai de la vidéo test Bingo Night (`media/rushs/test-pratique/`, en anglais,
   licence = pratique seulement), à faire à la demande de l'utilisateur, idéalement à travers le plugin.

## 5. Nouveau plan validé par l'utilisateur aujourd'hui (après les tâches ci-dessus)

L'utilisateur veut **beaucoup de styles de montage différents**, pas seulement « sous-titres + musique ». Vidéo modèle
analysée : `C:\Users\crist\Downloads\WhatsApp Video 2026-09-26 at 11.37.45 AM.mp4` (29 s, pub « CopyFi » générée par IA ;
planches d'images dans `runtime/cache/tmp/ref-whatsapp/`). Ce qui fait son style :
texte placé AUTOUR de la personne (petits mots de liaison + gros mots clés en gras + mot émotion en rouge, qui
s'accumulent), texte géant DERRIÈRE la personne (« LOOKED », « WHY »), texte en diagonale / à la verticale, mots entre
guillemets en rouge (« RULES », « FREE »), faux écrans d'application (notification, message privé, téléphone),
silhouette noire sur fond rouge, éclat BD, plan d'illustration toutes les 1-2 s, palette rouge / blanc / noir, fin avec la
marque (« Try it at COPYFI.AI »).

Ordre convenu :
1. **Moteur de texte cinétique** (Remotion) : placement du texte dans l'espace libre autour du visage (analyse visage déjà
   faite), hiérarchie de tailles/couleurs, accumulation au fil des mots, diagonales/verticales, guillemets, texte derrière
   la personne (détourage MediaPipe déjà installé dans `models/mediapipe` ; export plus lent). Difficulté moyenne à difficile.
2. **Faux écrans et silhouettes** : notification, message, écran de téléphone, silhouette sur couleur (comme les
   graphismes actuels de `remotion/src/graphics.tsx`).
3. **Galerie de styles** façon « Explore templates » : cartes avec aperçu de LA vidéo de l'utilisateur dans chaque style
   (aperçu Remotion instantané), filtres (Pub, UGC, Témoignage, Produit, Motion…), « Utiliser ce style » ; les styles
   « par référence » y apparaissent. Premiers styles complets : « Éditorial cinétique » (d'après la vidéo ci-dessus),
   Hormozi, Tech/application, Infographie, Documentaire, Collage, Luxe/minimal, Rétro VHS, Comparatif.
4. **Templates d'effets Blender** (Blender déjà utilisé par `intro.py`) : « Recréer avec mon produit » (photo/logo, ou
   modèle 3D du client) → produit 3D qui tourne (canette, bouteille, boîte, téléphone), logo 3D, texte derrière la
   personne, arrêt sur image + cercle, avant/après. Limite honnête : une vue éclatée type « montre en pièces » demande
   le modèle 3D du produit (Higgsfield l'invente avec une IA générative, ce qu'on ne fait pas). Unreal : plus tard.
   La génération d'images par IA (type Higgsfield) n'est PAS demandée.
5. Améliorer le « style par référence » pour reconnaître ce genre de mise en page.

L'utilisateur enverra d'autres vidéos d'exemple pour construire les styles.
