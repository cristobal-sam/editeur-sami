# REPRISE DU PROJET — Éditeur Sami

> Document de passation. À lire en premier par toute nouvelle conversation (humaine ou IA)
> qui reprend le projet. Mis à jour le 2026-09-30 (après les 11 points restants : voir §12 et §13).
> **⚠️ Fin du 2026-09-30 : travail interrompu en cours de route → lire §15 et
> `docs/passation-2026-09-30/PASSATION.md` AVANT tout le reste.**
>
> **Reprise Codex : les six chantiers ont ensuite été corrigés et testés. Lire §16 et
> `docs/passation-2026-09-30/VERIFICATION-CODEX.md` pour l'état le plus récent et les limites restantes.**
>
> **Dernier état (30 septembre 2026, soir) : fonctions V2 de direction créative intégrées et testées — lire §22 et
> `docs/direction-creative-v2/RESULTAT.md`. Le vrai serveur 8790 doit être relancé une fois pour les activer.**
>
> **2 octobre 2026 : ronde 3 faite (Vidéo 1 en qualité pro, version « qualité ») — lire §24, puis §25 (corrections après le
> juge indépendant n° 1), §26 (corrections après le juge n° 2) et `docs/qualite-2026-09-30/COMPTE-RENDU.md`. File d'attente :
> `docs/qualite-2026-09-30/FILE-ATTENTE.md`.**
>
> **2 octobre 2026 (matin) : ronde 4 intégrée — nouvelle Révision d'après la maquette, icônes Lucide (trait / plein / verre),
> finition de Vidéo 1 après le juge n° 3. Lire §27 et `docs/qualite-2026-09-30/COMPTE-RENDU-RONDE4.md` (où cliquer).**
>
> **2 octobre 2026 (soir) : Claude (API Anthropic, en option, Sonnet 5.5 par défaut, plafonné), boîte « Dis à l'IA ce que tu
> veux » et sons de coupe variés (7 familles). Lire §29 et `docs/claude-api/RESULTAT.md`. ⚠️ La clé n'a pas d'espace de
> travail : aucun vrai appel n'a pu aboutir (0,00 $ dépensés) tant que l'utilisateur n'a pas collé son identifiant `wrkspc_…`.**

---

## 1. Le projet en une phrase

Un **monteur vidéo local et automatique** pour un entrepreneur qui reçoit des vidéos brutes de
clients et doit livrer des montages professionnels (reels publicitaires, face caméra, et plus tard
podcasts, conférences, immobilier). On choisit un **style de montage**, l'outil monte tout seul,
et **chaque détail reste modifiable instantanément** sans tout recommencer.

L'outil **ne remplace pas** DaVinci Resolve, Blender, etc. : il fait le travail mécanique
(dérushage, choix des prises, premier montage, habillage) et **s'appuie sur les logiciels locaux**
(Resolve pour la finition via l'export OTIO/XML, Blender pour les titres 3D).

---

## 1 bis. Rôle de l'assistant sur ce projet

L'assistant qui travaille sur l'éditeur tient **deux rôles à la fois** (demandé par l'utilisateur) :

1. **Monteur vidéo / cinéma professionnel de très haut niveau** : productions premium (action,
   science-fiction, drame, bandes-annonces, publicité cinématographique) et contenus courts (reels, pubs).
2. **Consultant produit** expert en logiciels de montage, flux de postproduction, IA créative et
   outils pour monteurs professionnels.

**Comment penser** : comme le monteur principal d'une grosse production qui utiliserait l'outil
tous les jours. Toujours se demander : « qu'est-ce qui me ferait gagner du temps, améliorerait mes
décisions ou la qualité du résultat ? ». Raisonner en narration, émotion, rythme, continuité,
lisibilité de l'action, jeu des acteurs, choix des prises, transitions motivées, conception sonore,
musique, tension, composition, synchronisation image/son, organisation, vitesse, contrôle créatif.
**Chaque coupe a une intention** : pourquoi à cet instant, motivée par un regard, un mouvement, un son
ou une émotion ; J-cut / L-cut ; plan redondant ; meilleure prise ; réaction à montrer.

**Comment évaluer l'outil** : ne jamais le supposer complet parce qu'il fonctionne. Le comparer
aux usages de Premiere, Resolve, Avid, Final Cut, After Effects / Fusion, sans les copier : chercher
ce qu'ils font mal ou trop lentement, ce qui reste manuel et pourrait être assisté par l'IA
**sans enlever le contrôle créatif au monteur**. Être critique et honnête, sans chercher à plaire.

**Comment proposer une fonction** : nom · problème actuel · exemple concret · fonctionnement ·
interface (où et comment) · apport de l'IA · contrôle du monteur · gain (temps, qualité, précision,
créativité, confort) · difficulté (facile / moyenne / difficile / très avancée) · priorité
(indispensable / très utile / intéressante / expérimentale). Pour une faiblesse : pourquoi elle gêne,
le flux professionnel idéal, une version simple puis une version avancée.

**Positionnement** : l'éditeur ne cherche pas à remplacer Avid ou Resolve ; il s'appuie sur les
logiciels locaux (Resolve/Fusion, Blender, Natron…) et vise à ce que le monteur passe moins de temps
sur les tâches mécaniques et plus sur les décisions créatives.

---

## 2. Règles de travail (demandées par l'utilisateur — à respecter)

1. **Ne jamais modifier quoi que ce soit dans `D:\Y0U`** (autre projet). On travaille uniquement
   dans `D:\Tools\editeur_sami`. Lire/exécuter depuis `D:\Y0U` est permis (ex. Blender).
2. **Tout reste dans `D:\Tools\editeur_sami`** : outils, modèles, caches, fichiers temporaires.
   Rien sur `C:`. Optimiser l'espace et garder une organisation propre.
3. **Aucune API payante ni service en ligne** : tout tourne en local (GPU RTX 5060 Ti 16 Go). Exception demandée par
   l'utilisateur le 2 oct. 2026 : Claude (sa clé Anthropic), en option, plafonné, avec repli local partout (§29).
4. **Un seul reel à la fois** : ne monter/exporter que la vidéo demandée, puis attendre.
   Ne jamais lancer de long montage ou toutes les versions sans demande explicite.
5. **Ne pas supprimer** les fichiers produits sans accord (l'utilisateur garde les extras).
6. Répondre en **français** (utilisateur au Québec).
7. Quand l'utilisateur dit « discutons » ou « ne modifie rien » : discuter, ne rien coder.
8. Tests : de préférence courts (quelques secondes d'export). L'utilisateur fera les tests finaux.

---

## 3. Démarrer

```powershell
cd D:\Tools\editeur_sami
.\editeur.ps1                         # interface : http://127.0.0.1:8790
.\derusher.ps1 -Styles                # liste des styles de montage
.\derusher.ps1 -Rushs "media\rushs" -Script "media\rushs\script.docx"   # avec script Word
.\derusher.ps1 -Rushs "media\rushs\tournage"                            # SANS script (transcription)
.\derusher.ps1 -Rushs ... [-Script ...] -Style reel-impact -Video video1 -Version v1
      # + monte et exporte UN reel stylisé (FINAL)
powershell -ExecutionPolicy Bypass -File installer.ps1    # réinstalle ce qui manque
remotion\node_modules\.bin\tsc -p tsconfig.verif.json    # vérification des types (interface + Remotion)
```

Dans un terminal, **toujours charger l'environnement d'abord** : `. .\runtime\env.ps1`
(PowerShell) ou `source runtime/env.sh` (bash). Il redirige tous les caches vers le dossier et
met Hugging Face hors ligne (`HF_HUB_OFFLINE=1`).

---

## 4. Organisation des dossiers (≈ 36 Go)

```
editeur_sami/
├─ REPRISE.md, README.md, editeur.ps1, derusher.ps1, installer.ps1
├─ app/                  ← serveur local + interface
│   ├─ server.mjs        ← serveur HTTP Node (port 8790), sans dépendance ; FILE D'EXPORTS
│   ├─ build.mjs         ← compile l'interface (esbuild) → app/dist/app.js
│   └─ ui/               ← App.tsx, Timeline.tsx, panels.tsx, panels2.tsx (graphismes, conseils,
│                          plans de coupe, charte, déclinaisons, visuel, multicam, export), conseils.ts,
│                          edit.ts, api.ts, styles.css
├─ engine/               ← moteur Python (paquet « editeur »)
│   ├─ pyproject.toml    ← dépendances (uv), PyTorch cu128
│   ├─ music_gen.py      ← musique ACE-Step (lancé par runtime/venvs/acestep)
│   ├─ blender_titre.py  ← script Blender du titre 3D
│   └─ editeur/          ← modules (voir §6)
├─ remotion/
│   ├─ src/timeline.ts   ← ★ LE CALCUL DU MONTAGE (plans, J/L-cuts, couleur, sous-titres, SRT,
│   │                      musique, bruitages, rythme). Seule implémentation : utilisée par
│   │                      l'aperçu (navigateur), l'export (Node) et Python (via segments.mjs).
│   │                      + vitesse, plans muets, angle multicaméra, recadrage (framing/subjectAt)
│   ├─ src/Reel.tsx      ← composition : plans (cadre qui suit le sujet, tous formats), plans de
│   │                      coupe V2, zooms, couleur, sous-titres, effets, graphismes, charte client,
│   │                      intro 3D, voix (aperçu), musique, bruitages
│   ├─ src/graphics.tsx  ← graphismes animés (chiffre, cases cochées, carte, mot géant, logo) + charte (logo, fin)
│   ├─ src/types.ts      ← format du document « reel » (+ FORMATS 9:16 / 16:9 / 4:5 / 1:1)
│   ├─ render.mjs        ← export final (voix FFmpeg + musique/bruitages calculés en Node + image Remotion + mixage)
│   └─ segments.mjs      ← calcul du montage en JSON pour Python (échange Resolve, SRT, mots minutés)
├─ tsconfig.verif.json   ← vérification des types (tsc), ne sert pas à la compilation
├─ styles/               ← styles MODIFIABLES : montage/*.json (9, dont immobilier, evenement ; clé « ia »),
│                          sous-titres.json (8), musiques.json (12), clients/<id>.json (chartes clients)
├─ assets/               ← fonts/ (17 OFL + emoji), music/ (12 .ogg + generes/), sfx/ (editeur/ + kenney/), overlays/,
│                          clients/<id>/logo.* (chartes), images/ (photos des cartes animées)
├─ media/rushs/          ← vidéos brutes à monter
├─ media/broll/          ← (à créer) plans d'illustration proposés comme plans de coupe
├─ projects/
│   ├─ _cache/           ← transcripts/, analysis/ (v3 + *.cadrage.json, *.bouche.json), optimises/
│   │                      (médias optimisés, cadre d'origine, *-stab.mp4 stabilisés), ambiances/,
│   │                      recherche/ (index CLIP), vignettes/, livraisons/
│   └─ video1/
│       ├─ project.json  ← résultat du dérushage (prises possibles par plan, variantes, groupes multicam)
│       ├─ rapport.md
│       ├─ reels/<script|v1|v2>.json  ← ★ le MONTAGE + le STYLE de chaque version (fait foi)
│       ├─ reels/<id>-<30-s|rapide…>.json ← déclinaisons (champ derivedFrom), listées dans l'interface
│       ├─ versions/<version>/*.json  ← instantanés (versions nommées + automatiques)
│       └─ intros/       ← titres 3D Blender (.webm transparents)
├─ livraisons/<script>/  ← montages bruts, parties, FINAL.mp4, dossiers « - pour Resolve »
├─ models/               ← huggingface/ (Whisper, CLIP), llm/ (Qwen3.5-9B + vision),
│                          acestep/ (musique), mediapipe/ (visage, repères, détourage), rnnoise/
├─ tools/                ← ffmpeg/, llama/ (llama.cpp CUDA 13), acestep/ (code source)
└─ runtime/              ← python/, venv/, venvs/acestep/, bin/uv.exe, cache/ (vidable)
```

---

## 5. Fonctionnement de bout en bout

```
rushs (+ script Word facultatif)
  │ derush.py (avec script) ou libre.py (sans script) :
  │   transcription Whisper (cache) + analyse v3 (visage, netteté, JEU : regard/expressions,
  │   énergie voix, couleur du visage, son) + médias optimisés (redressés 1080x1920, 30 i/s,
  │   image clé /0,5 s) + choix des meilleures prises
  ▼
projects/<video>/project.json   (plans, TOUTES les prises possibles avec notes et critères)
  │ reel.py : crée reels/<version>.json (plans, mots, style, sources, échantillons couleur,
  │           fond d'ambiance) + IA locale (mots clés, bandeau, emojis) + style de montage
  ▼
Interface (Remotion Player lit DIRECTEMENT les médias optimisés : aucune vidéo intermédiaire)
  │ toute retouche = modification du JSON du reel = INSTANTANÉE (prise, coupe, mots, J/L-cut,
  │ couleur, style) ; sauvegarde auto ; Ctrl+Z ; versions
  ▼
app/server.mjs : FILE D'EXPORTS (un à la fois, annulables, plusieurs formats par reel)
  ▼
remotion/render.mjs (export)
   1. voix : FFmpeg depuis les RUSHS D'ORIGINE (segments audio avec J/L-cuts, fondus, vitesse
      (atempo), fond d'ambiance, déclip, traitement Naturel/Radio/Podcast, loudnorm -14 LUFS) ;
      piste muette si tous les plans sont muets (immobilier)
   2. musique + bruitages : calculés en Node (PCM) avec musicVolume / sfxEvents de timeline.ts
      (avant : 2e passe Remotion qui rejouait toutes les images → ~45 % du temps d'export)
   3. image : Remotion (muet, concurrence 8-12) depuis les médias optimisés
   4. mixage FFmpeg (voix + effets + limiteur) → livraisons/<script>/<titre>[ (16x9)] - FINAL.mp4
   Annulation : le serveur crée <job>.json.stop (tuer le processus laisserait Chrome ouvert).
```

**Principes clés** : les rushs ne sont jamais modifiés ; le reel JSON fait foi pour le montage
d'une version ; `remotion/src/timeline.ts` est la seule source du calcul (aperçu = export).
Synchro vérifiée : voix exportée à ~7 ms du prévu.

---

## 6. Moteur Python (`engine/editeur/`)

| Module | Rôle |
|---|---|
| `media.py` | FFmpeg/ffprobe, audio, images, rotations, cache, **`optimized()`** (médias optimisés) |
| `transcribe.py` | faster-whisper large-v3-turbo (GPU), mots horodatés, cache |
| `analyze.py` | analyse v3 : rotation, visage, netteté, **jeu** (52 expressions MediaPipe : expressivité, regard relatif à l'habitude de la prise, clignements), **couleur du visage**, niveaux, écrêtages |
| `script.py` / `align.py` | lecture du .docx, alignement phrase ↔ prise |
| `derush.py` | note des prises (texte 40 %, fluidité 20 %, jeu 15 %, image 12 %, son 8 %, récence 5 %), choix optimal, variantes de hook, `project.json` avec prises + notes + critères |
| `libre.py` | **mode sans script** : phrases, bavardage/prises abandonnées écartés, phrase redite → dernière version gardée (les autres = prises alternatives) |
| `deliver.py` / `render.py` | livraison des montages bruts et des parties (FFmpeg) |
| `reel.py` | création/mise à jour du reel (sources, échantillons, ambiances, IA, styles) |
| `llm.py` | Qwen3.5-9B via llama-server (port 8791 texte, 8792 vision) |
| `search.py` | **recherche** : CLIP (images 1/s) + transcription + descriptions de scènes (vision Qwen, PySceneDetect) |
| `echange.py` | **export Resolve/Premiere/Final Cut** : .otio, .xml (FCP7), .fcpxml + .srt |
| `intro.py` | **titre 3D Blender** → .webm transparent |
| `export.py` | export final depuis Python (lance render.mjs) |
| `edit.py` | (ancien) retouches CLI sur project.json — l'interface modifie désormais le reel directement |
| `sfxgen.py` | synthèse des bruitages |
| `montage.py` | commun : lire/écrire un reel, calcul du montage via segments.mjs, phrases |
| `cadrage.py` | **recadrage** : piste de la personne qui parle (jusqu'à 4 visages, bouche + son, maintien 1,2 s) ; activité de parole (angles multicam) |
| `broll.py` | **plans de coupe** : bibliothèque media/broll (CLIP), emplacements (mots-concepts, coupes franches), 3 propositions |
| `graphismes.py` | **graphismes proposés** : chiffres dits (avec unité), bénéfices (Qwen) → cases cochées, mot choc, logo |
| `declinaison.py` | **déclinaisons** 60/30/15 s + intentions (Qwen note les phrases, coupe + remplissage) |
| `multicam.py` | **synchro multicaméra** par le son (FFT, 1 ms), groupes dans project.json, angles automatiques |
| `visuel.py` | **montages immobilier / événement** : vidstab, scènes, pièces (CLIP), coupes sur les temps (librosa), citations |
| `raccords.py` | **faux raccords** (expérimental) : mesures simples + vision Qwen contre-vérifiée (images inversées) |

Commandes (depuis `engine/`, environnement chargé) :
```
python -m editeur derush <rushs> [<script.docx>] [--style id --video video1 --version v1] [--sans-rendu]
python -m editeur reel ../projects/video1 --variante v1 [--style id] [--exporter]
python -m editeur echange ../projects/video1 --variante v1
python -m editeur intro ../projects/video1 "Texte du titre" [--couleur #FFD400 --duree 2.5]
python -m editeur recherche ../projects/video1 "quand elle parle du salaire"
python -m editeur render ../projects/video1      # refait la livraison brute
python -m editeur styles
python -m editeur ia|broll|graphismes|raccords|angles ../projects/video1 --reel v1   # propositions (JSON)
python -m editeur declinaison ../projects/video1 --reel v1 --duree 30 [--intention rapide|emotion]
python -m editeur multicam ../projects/video1 [--prises t01,t02]
python -m editeur visuel ../media/<dossier> --type immobilier|evenement --titre "12 rue X" --duree 30
```

---

## 7. Format du reel (`projects/<video>/reels/<version>.json`, voir `remotion/src/types.ts`)

`id, project, variant, title, delivery, template, width, height, fps,`
`sources: {tXX: {name, proxy (chemin relatif), path (rush d'origine), duration, width, height, samples [[t,cx,cy,luma,r,g,b]],
roomtone, track? [[t,cx,cy,w]] (qui parle), sync? {group, offset} (multicam), kind? 'broll'}}`,
`clips: [{id, block, signature, source, in, out, tighten, choice, words [{w,start,end,hl,hide,cut}],
emojis, audioLead (J-cut s), audioTail (L-cut s), color {auto, exposure, temperature}, speed?, mute?, angle?}]` (ORDRE = montage),
`ctaBlock, style{preset,font,…}, zoom, banner, flash{enabled,kind}, effects{grain,vignette,grade},
emoji, progress, music{enabled,mood,file,volume}, sfx{…, extra [{t,name}]}, audio{voice,roomTone,declip}, intro{enabled,text,file,duration}`,
`broll [{id, source, in, at, duration, word}]` (piste V2), `graphics [{id, kind, at, duration, props, suggested?}]`,
`brand {client, name, logo, logoPosition, logoSize, logoOpacity, bannerBg, bannerColor, style{font,color,highlight,stroke}, outro{enabled,text,duration}}`,
`aiMode 'auto'|'suggestion', suggestions {banners, words {clip: [i]}, emojis {clip: [[i,e]]}}`, `kind` (immobilier…),
`derivedFrom, label` (déclinaisons). Format = `width/height` (9:16, 16:9, 4:5, 1:1 : `FORMATS` dans types.ts).
Temps : `baseSegments` = segments dans la prise du SON ; `videoSegments` = avec l'angle multicam ; `segLen(s)` = durée
dans le montage (vitesse) — ne jamais utiliser `src_out - src_in` comme durée de sortie.

Les prises possibles de chaque plan sont dans `project.json` (`timeline[].takes`, `variants[].clip.takes`),
servies à l'interface par `/open`.

---

## 8. Interface (`app/`)

En-tête : choix du reel, **format 9:16 / 16:9 / 4:5 / 1:1** (aperçu instantané), A/B, annuler/rétablir.
Onglets : **Plan** (prise + notes + critères, **Comparer** les prises côte à côte, coupes à l'image
près, resserrage, **vitesse**, **plan muet**, **angle multicaméra** (+ automatique), **J-cut/L-cut**,
**lumière/couleur**, déplacer), **Texte** (IA : proposer / appliquer, propositions en pointillé à accepter
ou refuser, relancer l'IA ; couper des mots = couper la vidéo, rétablir, couleur, masquer, corriger),
**Style** (styles de montage, **charte client**, sous-titres, voix, musique, bruitages, bandeau (+ 3
bandeaux proposés), titre 3D, image), **Graphismes** (ajouter à l'instant courant, propositions de l'IA,
réglages), **Rushs** (recherche, **plans de coupe**, **multicaméra**, **nouveau montage visuel**),
**Conseils** (zones faibles du rythme → propositions en un clic ; **faux raccords**), **Versions**
(enregistrer, restaurer, A/B, **déclinaisons**), **Export** (formats cochés → **file d'exports** avec
progression et annulation ; export Resolve/Premiere).
**Timeline** en bas : temps, rythme (💡 conseils, ▲ faux raccords), image, **plans de coupe (V2)**,
voix (J/L-cut), musique, bruitages, **graphismes** (V2 et graphismes se déplacent à la souris).
Serveur : `/api/reels`, `/api/styles`, `/api/transcript/:p/:source`, `/api/thumb`, `/api/search`,
`/api/jobs/:id` (+ `/cancel`), `/api/queue`, `/api/reels/:p/:v/{open (GET = relecture rapide),template,versions,
restore,version,music,intro,echange,export,ia,broll,graphismes,raccords,angles,declinaison}`,
`/api/projects/:p/multicam`, `/api/visuel`, `/api/media-folders`, `/api/clients`, `/api/images`,
`PUT /api/reels/:p/:v` (champs EDITABLE + `format`), fichiers `/projects/*` et `/assets/*`.
Le serveur refuse les POST dont l'origine n'est pas exactement `http://127.0.0.1:<port>` (pas « localhost »).
Après modification de `app/ui/` : `node app/build.mjs` ; de `server.mjs` : redémarrer le serveur.

**Depuis la ronde 4 (2 oct. 2026)** : la page d'accueil est la **Révision** au design de la maquette Claude Design
(`app/ui/revision.tsx`, icônes `app/ui/icons.tsx`, bloc CSS `/* revision */`, classes `sr-*` / `sa-*`, police Manrope).
Barre du haut commune `TopBar` (onglets **Révision / Éditeur**, compteurs du jour, réglages) ; l'éditeur décrit ci-dessus
s'ouvre par « Modifier » (E) ou l'onglet Éditeur, ses outils d'en-tête sont dans cette barre, le reste garde l'ancien
thème. Raccourcis de la Révision : Entrée = Je la prends, E = Modifier, S = Autre style, → = Suivante, Espace, Échap.
Ceux de l'éditeur (Ctrl+Z, Espace, flèches) ne marchent que dans l'éditeur. Détails : §27.

---

## 9. Logiciels locaux (hors dossier — à INTÉGRER, pas à remplacer)

| Logiciel | Emplacement | Usage |
|---|---|---|
| DaVinci Resolve (gratuit) | `D:\Resolve.exe` | finition ; importer `montage.otio`/`.xml` ; page **Fusion** = alternative locale à After Effects |
| Blender 4.5 | `D:\Y0U\tools\portable\blender\...\blender.exe` | titres 3D (utilisé par `intro.py`) ; copier dans `tools/blender/` pour l'autonomie |
| Natron 2.5 | `D:\Y0U\tools\portable\natron\...` | compositing |
| Kdenlive 26.08 | `D:\Y0U\tools\portable\kdenlive-...exe` | montage libre |
| Unreal Engine 5.8 | `D:\Epic Games\UE_5.8\...` | décors/cinématiques 3D |

---

## 10. État actuel

- Rushs de test : `media/rushs/` (pubs RyuCalls, script « SAM SCRIPT ADS 2026-08-11.docx »).
- Reel de test : **Vidéo 1 – Hook alternatif 1** (`projects/video1`, version `v1`, style reel-impact).
  Converti au nouveau format ; son dernier FINAL a été exporté avant les points 1-10.
- Fichiers en plus à GARDER : `Vidéo 1 - 0 COMPLET - Hook original - FINAL.mp4`, reels `script` et `v2`.
- Points 1 à 10 puis les 11 points restants faits et testés brièvement (voir §12). L'utilisateur fera les tests complets.
- Les reels `v1` et `script` de video1 ont été rouverts pendant les tests : ils ont reçu les nouveaux champs
  (width/height des sources, aiMode, suggestions) ; format remis en 9:16, aucun graphisme ni plan de coupe ajouté.
- `runtime/cache/tmp` : les profils Chrome de Remotion de plus d'une heure sont vidés à la fin de chaque export.

---

## 11. Pièges connus (déjà résolus — ne pas les réintroduire)

- faster-whisper : décodeur PyAV cassé → décoder avec FFmpeg.
- DeepFilterNet absent pour Python 3.12 → `arnndn` + RNNoise.
- `uv` : `UV_PYTHON_BIN_DIR` sinon raccourcis sur C: ; `uv cache clean` après installation.
- Remotion : son ré-encodé en retard (~60 ms) → la voix est construite par FFmpeg depuis les rushs.
- Remotion : `renderMedia` garde les réglages de `selectComposition` → re-sélectionner par passe.
- Node 24 exécute `timeline.ts` directement (types retirés) : ce fichier ne doit importer QUE des types.
- Python dans un heredoc bash transforme `\b`, `\n` → écrire les correctifs avec l'outil de fichiers.
- Grain SVG trop lent → texture PNG déplacée.
- Regard caméra : comparer à l'habitude de la prise (caméra sous les yeux), pas à un seuil fixe.
- Recherche : retirer les mots de liaison (« quand elle parle du… ») ; CLIP attend de l'anglais (traduction par Qwen).
- Export « graphismes sur fond transparent + FFmpeg » MESURÉ : 2,5× PLUS LENT (captures PNG + ProRes 4444).
  Ne pas y revenir ; le gain vient de la suppression de la passe audio Remotion. Concurrence > 8 : aucun gain.
- Annuler un export sous Windows : ne pas tuer node (Chrome resterait ouvert) → fichier `<job>.json.stop`.
- Déclinaisons : ne protéger que la 1re phrase et la dernière phrase de l'appel à l'action (protéger des blocs
  entiers ne laissait rien à couper) ; remplissage après la coupe ; notation Qwen à température 0.
- Musique des montages visuels : librosa rate souvent l'intro sans pulsation → grille prolongée jusqu'à 0.
- Vision Qwen (raccords) : invente souvent (micro « disparu » alors qu'il est là) → alerte gardée seulement si
  confirmée images inversées et gravité ≥ 2 ; gestes et expressions explicitement ignorés.
- PowerShell `.Replace()` sur plusieurs lignes échoue sur les fichiers en CRLF (reel.py, echange.py…) :
  vérifier que le remplacement a eu lieu, sinon utiliser l'outil d'édition.
- Médias optimisés : une prise déjà en 9:16 garde sa clé `v1` (pas de ré-encodage) ; les autres passent en
  `v2-cadre` (cadre d'origine, recadrés à l'affichage).
- `derush` : chemins des rushs en ABSOLU (sinon l'export ne les trouve pas).
- Chemins relatifs (`proxy`, `roomtone`, `intro.file`) en « / », relatifs à la racine, servis par `/projects/…`.
- Titre Blender : caméra verticale → largeur visible ≈ 3,85 unités ; police épaisse (Anton).
- Vérifier la synchro d'un export : retranscrire et comparer les temps des mots.

---

## 12. Ce qui a été fait

Première série (points 1 à 10) :
1. Aperçu instantané sans recalcul (médias optimisés, lecture directe) ✅
2. Timeline multipiste avec J-cuts / L-cuts ✅
3. Montage par le texte + mode sans script ✅
4. Comparateur de prises côte à côte ✅
5. Analyse du jeu dans la note des prises ✅
6. Recherche en phrase naturelle dans les rushs ✅
7. Harmonisation lumière/couleur + lissage + réglages manuels ✅
8. Versions, restauration, comparaison A/B ✅
9. Échange Resolve/Premiere/Final Cut (OTIO, XML, FCPXML, SRT) + titre 3D Blender ✅
10. Traitement de la voix (3 préréglages) + fond d'ambiance ✅

Deuxième série (les 11 changements, 2026-09-30) — tous codés et testés brièvement :
1. **File d'exports** (un à la fois, annulation, progression, plusieurs formats) + **export ~1,8× plus rapide**
   (musique et bruitages calculés en Node : plus de 2e passe Remotion). ✅ (voir §13 : pas 2-3×)
2. **Multi-formats** 9:16 / 16:9 / 4:5 / 1:1 (aperçu instantané, export par format), médias optimisés au
   **cadre d'origine**, **recadrage qui suit le sujet** (lissé), **plusieurs intervenants** (cadrage.py :
   qui parle = bouche + son, maintien 1,2 s). ✅
3. **Plans de coupe** : piste V2 (aperçu, export, timeline, OTIO), propositions aux mots-concepts et aux
   coupes franches (CLIP, 3 vignettes, un clic), insertion depuis la recherche, dossier `media/broll`. ✅
4. **IA en mode suggestion** : `aiMode` par reel (clé `ia` par style), propositions en pointillé dans Texte
   (accepter / refuser / tout / relancer), 3 bandeaux proposés, emojis proposés. ✅
5. **Chartes clients** : `styles/clients`, logo en filigrane, couleurs/police des sous-titres, bandeau,
   carte de fin ; passe par-dessus le style de montage (aussi côté moteur). ✅
6. **Graphismes animés** : chiffre qui défile, cases cochées, carte (photo), mot géant lumineux, logo ;
   onglet Graphismes + piste ; propositions de l'IA (chiffres dits, bénéfices, mot choc). ✅
7. **Déclinaisons** 60/30/15 s + « rapide » / « émotion » : Qwen note les phrases, coupe + remplissage,
   nouvelle version listée, A/B avec l'original. ✅
8. **Multicaméra** : synchro par le son (FFT, 1 ms, confiance), angle par plan (son gardé), angles auto. ✅
9. **Montages visuels** : immobilier (vidstab, scènes, pièces par CLIP, ordre de visite, coupes sur les
   temps de la musique, titre-adresse) et événement (meilleurs moments + citations). Styles `immobilier`,
   `evenement`. Vitesse et plans muets par plan (utilisables partout). ✅
10. **Conseils de rythme** : zones faibles → resserrer, zoom de relance, bruitage, mot en couleur, couper
    un passage (jamais hook ni appel à l'action), ouvrir plans de coupe / graphismes. Marqueurs 💡. ✅
11. **Faux raccords** (expérimental) : vêtements (couleur du torse), cadre identique (coupe franche),
    lumière, + vision Qwen contre-vérifiée. Marqueurs ▲. ✅ (fiabilité faible, voir §13)

---

## 13. Ce qu'il manque encore après les 11 points (honnête)

1. **Export** : ~1,8× plus rapide seulement (≈150 s au lieu de ≈260 s pour 72 s). L'image plafonne à
   ~15 i/s (lecture vidéo dans Chrome). La piste « graphismes transparents + FFmpeg » a été mesurée
   2,5× plus lente : abandonnée. Piste restante : rendre dans Remotion à mi-résolution les segments sans
   graphisme… ou accepter. Pas d'encodage NVENC de l'image (Remotion encode en x264).
2. **Multi-formats** : jamais testé sur de vrais rushs HORIZONTAUX ni sur un vrai podcast à 2 (test
   synthétique côte à côte seulement : bascule correcte). Une prise verticale passée en 16:9 est agrandie
   ×1,78 (moins nette) : il faut filmer à l'horizontale pour du 16:9. Les prises horizontales seront
   ré-encodées une fois (nouveau cadre). L'export Resolve n'emporte pas le recadrage.
3. **Plans de coupe** : `media/broll` est vide → jamais testé avec de vrais plans d'illustration ; avec
   les rushs face caméra, les propositions sont forcément faibles (marquées « faible »). Pas de fondu
   réglable, pas de son du plan de coupe.
4. **IA suggestion** : qualité des bandeaux inégale (Qwen 9B). Les propositions d'un plan sont effacées si
   on change sa prise ou ses coupes (il faut relancer l'IA).
5. **Chartes** : pas de polices propres au client (seulement les 16 polices fournies) ; intro client =
   titre Blender existant aux couleurs ; pas d'outro vidéo (carte de fin seulement) ; pas de suppression
   de charte dans l'interface (supprimer le fichier `styles/clients/<id>.json`).
6. **Graphismes** : 5 éléments ; pas de placement à la souris dans l'image (hauteur par curseur) ; pas de
   bruitage automatique sur les graphismes ; non transférés vers Resolve.
7. **Déclinaisons** : le choix des phrases dépend de Qwen (bon sur le test : accroche → « 5 fois moins
   cher » → appel à l'action) ; la durée tombe à ±2 s de la cible (phrases entières) ; ne recoupe pas
   à l'intérieur d'une phrase.
8. **Multicam** : testé uniquement avec une copie décalée du même fichier (1,500 s exact) ; pas de vrai
   tournage multicam, dérive d'horloge entre caméras non gérée (longues captations), angle auto non évalué.
9. **Immobilier / événement** : aucune vraie vidéo de test (plomberie testée sur des extraits de rushs) ;
   pas d'accélérés/ralentis automatiques, pas de drone/hyperlapse, classement des pièces CLIP non évalué ;
   une citation peut reprendre un passage déjà vu ; musique seule à −18 LUFS (pas de normalisation à −14).
10. **Rythme** : règles simples (zones ≥ 3 s sous 0,45) ; pas de coupe « phrase faible » choisie par Qwen.
11. **Raccords** : Qwen vision invente encore (micro « disparu » alors qu'il est là) ; la contre-vérification
    élimine la plupart des erreurs mais peut aussi rater de vrais faux raccords. À considérer comme indice.
- **Types TS** : `tsc -p tsconfig.verif.json` marche ; restent 3 avertissements anciens (`react-dom` sans
  types, `premountFor` + `layout="none"`).
- **Tests complets** par l'utilisateur à faire (aperçu, exports longs, vrais tournages).

---

## 14. Limites connues et petites dettes à régler

- **Pas encore testé en conditions réelles par l'utilisateur** : il fera les tests complets à la fin.
- **FINAL du reel de test obsolète** : exporté avant les points 1-10 ; refaire l'export pour voir
  le nouveau moteur (non refait : un export complet ≈ 2 min 30, à lancer par l'utilisateur).
- **Traitement de voix et fond d'ambiance** : entendus seulement à l'export (l'aperçu joue le son brut).
- **`engine/editeur/edit.py`** (retouches CLI `reel --plan/--prise/--entree/--sortie`) agit encore sur
  `project.json`, alors que le reel fait foi : à brancher sur le reel ou à retirer.
- **`render.py` / `deliver.py`** (montages bruts de livraison) utilisent encore l'ancien calcul Python
  des plans (pas `timeline.ts`) : sans J/L-cuts, vitesse, angle ni couleur.
- **Export `.xml` (FCP7)** : les bruitages réutilisés sont écrits en références ; la relecture par
  OpenTimelineIO annonce 74,6 s au lieu de 72,6 s. Le `.otio` est exact (vitesse = LinearTimeWarp) et à
  privilégier dans Resolve.
- **Recherche** : la première recherche d'un projet indexe toutes les prises (≈ 3 min, vision comprise).
  Les descriptions de plans (Qwen) sont en français, CLIP en anglais (requête traduite par Qwen).
- **Blender** : utilisé depuis `D:\Y0U\tools\portable` (lecture/exécution). Le copier dans
  `tools/blender/` (≈ 900 Mo) pour rendre l'éditeur autonome — à demander à l'utilisateur.
- **Remotion** : licence gratuite jusqu'à 3 personnes ; au-delà, licence entreprise à acheter.
- **ACE-Step** : le modèle LM 1.7B (3,5 Go, `models/acestep/acestep-5Hz-lm-1.7B`) n'est pas utilisé
  (`thinking=False`) ; peut être supprimé pour gagner de la place, avec l'accord de l'utilisateur.
- **Score des prises** : le jeu compte pour 15 % ; poids réglables dans `derush.py` (`WEIGHTS`), pas
  encore dans l'interface.

---

## 15. Session du 2026-09-30 (après-midi) — nouvelle direction et travail interrompu

**Direction de l'utilisateur** : écran **Révision** d'abord (déposer N vidéos brutes → type détecté → montage automatique
dans le style associé → ✅ Je la prends / ✏️ Modifier / 🎨 Autre style), outil qui marche SANS l'assistant, **style par
référence** (déposer une vidéo modèle → nouveau style). Ensuite : plugin Claude « Éditeur Sami » (MCP local), puis
beaucoup de styles de montage différents (texte cinétique, faux écrans, galerie de styles, templates Blender).

**Ajouté et vérifié** (détails dans `docs/passation-2026-09-30/PASSATION.md` §2) : Révision (`app/ui/revision.tsx`,
`engine/editeur/auto.py`, `styles/types.json`, `media/entree/<lot>`, `projects/_revision.json`, `livraisons/<lot>`),
style par référence (`engine/editeur/style_ref.py`), banques d'images Pixabay (`engine/editeur/banques/`, clé dans
`cles-api.env` — NE JAMAIS LIRE CE FICHIER), chaîne son (RNNoise + expandeur, −14 LUFS, crête −1 dB, voix nettoyée dans
l'aperçu), robustesse (lanceur `Editeur Sami.cmd`, journaux `runtime/cache/erreurs*.log`, rotation par vote
`ROTATION_RULE = 2`, ordre accroche → corps → CTA sans script, correction Whisper par le script, anglais,
serveur IA partagé par compteur `runtime/cache/llama-<port>.json`).

**Interrompu à mi-chemin, NON revu** : déclinaisons (ré-ancrage des éléments), mots en couleur, « Je la prends »
multi-formats + enregistrer/supprimer un style ou une charte, lecteur PDF (`engine/editeur/pdftexte.py`, pas encore
branché), musique du style par référence (banc d'essai seulement), plugin `plugins/editeur-sami/`. Le code se charge et
compile, mais chaque chantier doit être terminé et vérifié : voir PASSATION.md §3. Copie du code d'avant :
`docs/passation-2026-09-30/avant/`.

**Pièges nouveaux** : `arnndn` plante ou donne NaN si l'entrée dépasse 0 dBFS → `volume=-4dB` avant, et `apad` avant +
`atrim` après (trame finale) ; musiques de `assets/music` en 48 kHz ; ne jamais lancer une 2e instance du serveur sur
le vrai dossier (même registre et même boîte d'entrée = vrais montages lancés) ; `derush.project_name()` évite de
réutiliser le dossier d'un autre projet.

---

## 16. Reprise Codex du 2026-09-30 — six chantiers revus

Compte rendu détaillé et limites : `docs/passation-2026-09-30/VERIFICATION-CODEX.md`.
La section 15 et la passation originale décrivent l'état AVANT cette reprise.

- **Mots en couleur** : sélection resserrée, limitation des groupes entièrement colorés consécutifs, y compris entre clips. Mesure vidéo1 : 41 mots, 31 groupes sur 63 ; tests règles et IA locale.
- **Déclinaisons** : ré-ancrage vérifié sur 60/30/15 secondes et intentions rapide/émotion ; correction du resserrement en émotion ; identifiants uniques pour ne pas écraser une version.
- **Révision/styles** : deux vrais exports d'une seconde (9:16 et 16:9) vérifiés dans le navigateur sur une copie isolée ; création/suppression de style, chartes et protections testées. Un export absent ou vide ne peut plus être déclaré réussi.
- **PDF** : lecteur branché au dépôt et au moteur ; les 13 blocs du scénario Bingo correspondent au TXT. Pas d'OCR pour les PDF scannés.
- **Musique de référence** : comparaison spectrale et rythmique avec la banque locale intégrée. Top 3 du banc d'essai : 65 % contre 57 % ; 9 voix seules correctement rejetées, mais 13 musiques faibles manquées sur 132. Ce n'est pas une reconnaissance garantie.
- **Plugin Claude** : appel multi-format corrigé, PDF accepté, protocole MCP testé ; activation déclarée dans `.claude/settings.json`. Affichage et activation effective dans Claude encore à confirmer, faute de client Claude disponible pour cette vérification.

Huit tests de régression Python, les 14 tests styles/Révision et les tests MCP passent ; construction de l'interface réussie. Quatre erreurs de typage préexistantes restent documentées dans le compte rendu.

Le vrai serveur n'a pas été démarré. La copie de test sur le port 18790 a été arrêtée après la fin des exports. Les dossiers de test sont conservés ; certains contiennent des jonctions vers des ressources originales : NE PAS les supprimer récursivement sans examiner ces jonctions.

Restent hors de cette validation : montage automatique complet depuis un nouveau dépôt, régénération du style RyuCalls, dettes antérieures et nouvelle gamme de styles (texte cinétique, faux écrans, galerie, Blender). Aucun montage long ni projet réel n'a été lancé pour ces vérifications.

## 17. Galerie de styles — première implémentation Codex du 2026-09-30

Lire `docs/galerie-styles/RESULTATS.md` pour l'état exact, les fichiers modifiés, les essais et les limites. Dix aperçus et une planche sont prêts ; dix styles sont branchés au moteur et ont un export court de cinq secondes. La partie B de `DEMANDE-IMAGES.md` reste partiellement réalisée : mise en page cinétique adaptative, variantes Tech, vraie police pixel, rythme/transitions spécifiques et produit utilisateur restent à approfondir ou valider.

Galerie avec filtres, application sans reconstruire les prises, retour au style précédent et panneau de retouche ajoutés. Détourage local pour Collage/Éditorial, Blender pour la carte produit démo. Qwen local + règles pour les scènes. Les éléments suivent les mots coupés ; anciens éléments manuels conservés, masqués par défaut.

Piège : un ancien cache de détourage de la copie avait de fausses couleurs. Version de cache `v3-alpha-frames`, régénération et séquence WebP alpha partagée lecteur/export ; contrôle visuel navigateur réussi. Actualiser le détourage après un changement de prise ou un élargissement de coupe.

Tests galerie 6 + temporels 6 + régression Python 8 réussis, appel Qwen réel testé, construction et TypeScript réussis (les erreurs de typage mentionnées au §16 sont corrigées). Browser sur copie : Tech → retour Hormozi, Collage, retouche persistée, actualisation. Ne pas confondre ces tests avec une validation exhaustive de chaque format ou d'un montage automatique complet. Le vrai serveur n'a pas été démarré.

## 18. Fable 2 — correctifs vérifiés et vrai serveur relancé (30 septembre 2026)

Lire `docs/taches-fable/RESULTAT-FABLE-2.md` : état des 22 points, preuves, limites et bacs de test. La passation `PASSATION-CHATGPT.md` décrit l'état AVANT cette reprise.

- Étape 3 terminée, étapes 1/2/4 relues indépendamment des changements des agents précédents. Relecture `sobriete.relire(..., tout=False)` branchée au changement de style ; accroche partagée ; titres et propositions de plans de coupe conservés ; immobilier/événement non reconstruits ; bandeau relu même masqué.
- A1–A3 corrigés : bandeau « toute la vidéo » ne bloque que l'accroche ; appel à l'action via bloc explicite ou dernier quart ; éléments manuels conservés. « Chez vos concurrents » n'est plus une solution. Les emojis masqués d'un montage automatique deviennent des propositions, les changements de style ne les recréent pas. Les nouvelles retouches de scènes portent `edited:true` et survivent au changement de style.
- B1–B4 corrigés : bandeau-adresse et son du montage visuel conservés ; vraie restauration ; médias manquants annoncés en français avant rendu ; délai sans progression proportionnel (10 min + 1 min par minute de montage). Rendu image : 4 min sans progrès, marge serveur et grâce avant arrêt forcé.
- Routes : `POST /api/revision/<id>/supprimer`, `POST /api/revision/supprimer`, `GET /api/revision/corbeille`, `POST /api/revision/corbeille/restaurer {dossier}`. Origine exacte obligatoire pour les POST. Déplacement récupérable seulement ; export terminé conservé. Restauration à destination libre sous `projects` ou `media/entree`, liens/parents jonctions refusés. Fiche et lot remis avant le scanneur : aucun remontage lorsque le montage est présent. Exception annoncée : montage absent → remontage.
- Échec/annulation d'export : nettoyage des cinq temporaires de CET export, jamais du FINAL existant ; annuler pendant la grâce garde le message de blocage. Registre du style synchronisé après `/template` et `/restore`.
- Preuves : Python 8 + 6 + 18 + 7 tests réussis, revue moteur sans échec ; temporels 6, erreurs export 15, compteur 8 ; HTTP 43, corbeille 74, blocage 12. Export podcast 2 s et six images regardées. Construction + TypeScript sans erreur. Tests sur copies uniquement, aucun export long.
- Étape 5 faite : serveur 8790 relancé via son lanceur existant (43416 → 28512). Refaire `a4296031c10d`, puis `0a92d5202af8`, terminé sans export. Deux vidéos prêtes en Reel Impact, titre de livraison « Vidéo 1 », 8,7 % et 9,1 % de mots colorés, aucun habillage sur l'accroche, zéro plan de coupe, aucun chevauchement. Bandeaux vides/désactivés après relecture. Au contrôle final : montage au repos, aucun export en cours.

Reste à l'utilisateur : regarder les deux vidéos, essayer trois autres styles, supprimer/restaurer une vidéo, puis « Je la prends » en 9:16. La validation visuelle complète des nouveaux boutons et des vidéos entières n'est pas revendiquée. Les budgets par style et les travaux de galerie restants sont hors de cette tâche. Aucun accès à `cles-api.env`, aucune IA vision, aucune installation.

Les bacs `runtime/cache/tmp/fable2-*` sont conservés avec leurs preuves ; certains contiennent des **jonctions**. Ne jamais les effacer récursivement sans examiner puis retirer les liens. Pour les exports directs, partir de `remotion/` afin d'utiliser Chrome déjà présent, pas de téléchargement automatique. Ne jamais lancer un deuxième serveur sur le vrai dossier ; le lanceur `editeur.ps1` déjà actif relance lui-même son enfant.

## 19. Plugin local 2.1 — Blender, Resolve et moteurs locaux (30 septembre 2026)

Le plugin `plugins/editeur-sami` expose maintenant 31 commandes. Six commandes ont été ajoutées : état des outils locaux, titre Blender 3D, animation Produit 3D, détourage MediaPipe, musique ACE-Step et ouverture explicite de DaVinci Resolve. L’export OTIO/XML/FCPXML/SRT vers Resolve/Premiere était déjà exposé.

Le titre 3D et la musique générée sont désormais rattachés au reel directement par `app/server.mjs`, même sans interface ouverte, avec une version « avant » gardée. Le plugin refuse Blender si la copie autonome `tools/blender/blender.exe` est absente et ne cherche jamais dans `D:\Y0U`. Resolve reste à `D:\Resolve.exe` et son ouverture exige une demande explicite distincte de l’export professionnel.

Syntaxe du serveur et du MCP vérifiée ; test non destructif : 31 outils découverts, appels en lecture et refus sûrs. Aucun rendu Blender, musique, détourage, logiciel visible, montage ou export lancé. Le vrai serveur doit être relancé de façon contrôlée pour charger les deux changements de rattachement dans `app/server.mjs` ; ne jamais en démarrer une seconde copie.

## 20. Tech 3D cinématique — refonte premium de Vidéo 1 (30 septembre 2026)

Le style `produit-3d` s'appelle maintenant **Tech 3D cinématique**. Il ne superpose plus une carte Blender générique :
la vraie personne détourée est placée dans un studio sombre animé (grille, halos, profondeur), avec des interfaces
ancrées aux mots réellement dits. Vidéo 1 contient quatre scènes visibles : tableau « Lead / Appelé », parcours
« Répondre → Qualifier », parcours « Qualifier → Transférez » et bouton exact « En savoir plus ». Une scène douteuse
sur l'accroche et le chiffre de la dernière phrase du CTA restent masqués par la relecture de sobriété.

Le générateur Blender refuse désormais toute animation produit sans vraie photo ou vrai modèle GLB. Un produit fourni
par le monteur reste possible et devient une scène manuelle ; l'ancien `productVideo` générique est retiré au prochain
changement de style s'il n'a ni `productImage` ni `productModel`. Le panneau explique ce comportement et son bouton est
désactivé tant qu'aucune vraie ressource n'est choisie. Le détourage peut être actualisé pour ce style.

Blender 4.5.10 LTS a été copié de façon autonome dans `tools/blender/` (copie vérifiée par nombre de fichiers, taille et
SHA-256 de l'exécutable). Les autres outils de `D:\Y0U\tools\portable` sont FFmpeg et Natron : non copiés, car FFmpeg
est déjà présent et Natron n'est pas nécessaire au nouveau rendu Remotion.

Vidéo 1 (`projects/script1/reels/script.json`) est enregistrée dans ce nouveau style ; ancienne version sauvegardée sous
`docs/amelioration-premium-2026-09-30/avant/`. Miniature remplacée par une vraie image du montage. Vidéo de référence
copiée dans `docs/references/reference-montage-spectaculaire.mp4` (SHA-256 identique à l'original fourni).

Preuves : build, TypeScript et vérifications Node réussis ; galerie 6/6, temporels 6/6, moteur 8/8, sobriété 18/18 ;
test premium dédié réussi. `revue_moteur.py` n'a pas pu finir parce que son projet fixture
`projects/video1video1/reels/script.json` n'existe plus (échec de donnée de test, pas une régression du style).
Deux exports courts H.264/AAC 1080×1920 ont été regardés, dont un de 15 s ; planches dans les dossiers
`runtime/cache/tmp/apercu-premium-*`. Le serveur est au repos, file vide. Aucun export final de 71 s : la tentative de
création d'une nouvelle livraison a été bloquée faute de confirmation explicite d'export complet.

## 21. Cerveau créatif V2 — première fondation intégrée (30 septembre 2026)

Lire `docs/cerveau-creatif-v2-2026-09-30/RESULTAT.md`. Le projet existant n'a pas été remplacé : le nouveau module
`engine/editeur/creative.py` s'insère avant `galerie.prepare` et produit un arc narratif commun à partir des phrases
réellement dites. Il distingue accroche, tension, solution, preuve, explication et appel à l'action ; il fixe aussi le
rythme, la grammaire visuelle, deux repères sonores au plus et quatre garde-fous anti-effets gratuits.

Le plan est recalculé au changement de style, sauf s'il porte `locked:true`. Les scènes automatiques reçoivent
`creativeBeat`, `creativeRole` et `creativeReason` ; les éléments manuels restent prioritaires. L'interface affiche
la carte « Direction créative V2 » dans l'onglet Ajouter avec accès direct aux moments du récit.

Vidéo 1 contient maintenant son plan : 7 temps narratifs et ses scènes sont reliées à une raison. Copie juste avant dans
`docs/cerveau-creatif-v2-2026-09-30/avant/script-video1.json`. Aucun rush refait, aucun export complet lancé. Tests : cerveau
créatif OK, moteur 8/8, galerie 6/6, temporels 6/6, build OK, TypeScript 0 erreur ; carte contrôlée dans le vrai
navigateur. Le serveur 8790 n'a pas été doublé ni relancé.

Complément : le storyboard exécutable est désormais dans `creativePlan.storyboard` avec moteur, composition,
ressource, justification, repli, état et références d'exécution. Les 7 plans de Vidéo 1 sont prêts ; Blender est
écarté sans produit réel. Un premier aperçu a montré que `design.suppressExtras` cachait la preuve pourtant planifiée.
`Reel.tsx` laisse maintenant passer uniquement un graphisme automatique rattaché à un plan
`remotion-graphisme`. Aperçu correctif 36–41 s inspecté : « ×5 MOINS CHER » visible au-dessus du visage, sans masquer
la personne. Preuves conservées dans `docs/cerveau-creatif-v2-2026-09-30/resultat/`.

Nouvelles demandes de Sami ajoutées à la passation Claude : notes timecodées et annotations au crayon façon Frame.io,
banque locale d'effets/swooshes/vecteurs/templates, SVG recolorables, chorégraphie complète gérée par l'IA mais
modifiable, verrouillage des retouches et « Refaire seulement ce passage ». La passation précise l'ordre recommandé
et les tests obligatoires. → **Elles sont maintenant implémentées et testées : voir §22.**

## 22. Fonctions V2 — direction créative (30 septembre 2026, intégrées et testées)

Compte rendu simple et liste de clics pour Sami : **`docs/direction-creative-v2/RESULTAT.md`**. Contrat technique (données,
fonctions, routes, règles) : **`docs/direction-creative-v2/SPEC.md`** (§13 = décisions de l'intégration). Copie du code
d'avant : `docs/direction-creative-v2/avant/`. Les fonctions demandées au §8 de `docs/PASSATION-CLAUDE-DIRECTION-CREATIVE-V2.md`
existent : **notes**, **crayon**, **banque**, **vecteurs recolorables**, **chorégraphie**, **verrous** et
**« Refaire seulement ce passage »**.

**⚠️ Le vrai serveur 8790 tourne encore avec l'ancien `server.mjs`.** L'interface (`app/dist/app.js`) est déjà la V2, mais
tant qu'il n'est pas relancé de façon contrôlée (par son lanceur, jamais une 2e copie) : notes, dessins, vecteurs et
chorégraphie ne sont PAS enregistrés (le panneau Notes l'annonce), et les routes banque / passage / chorégraphie
n'existent pas. Après la relance : `GET http://127.0.0.1:8790/api/v2` doit répondre 200.

**Ce qui existe (où cliquer)**
- **Notes** (onglet principal *Notes*, `app/ui/revue.tsx`) : note à l'image près (mm:ss:ii), statut ouverte / traitée /
  résolue, auteur, date, contexte du montage (titre, style, format, durée, phrase dite) ; repères dans la règle de la
  timeline ; clic = retour à l'image exacte ; la note suit les coupes et les déplacements de plans (ancre dans la prise) ;
  passage coupé ou prise changée → « ⚠ Passage retiré ou modifié » + « Rattacher ici » (jamais de pointage silencieux).
- **Crayon** (✏️ sur le lecteur) : crayon, flèche, cercle, surligneur, gomme, couleurs, épaisseur, annuler, effacer,
  masquer ; points en coordonnées de la PRISE (alignés en 9:16, 16:9, 4:5, 1:1) ; 2 s par défaut ; **jamais exportés**.
  « ⇢ Graphisme » transforme une flèche, un cercle ou un surligneur en vecteur exporté (choix explicite).
- **Banque** (*Plus → Banque*, `engine/editeur/banque.py` + `app/ui/banque.tsx`) : 556 ressources locales (490 sons :
  éditeur, 12 créés ici, 467 Kenney CC0 ; 18 modèles ; 12 effets ; 36 vecteurs), licence + provenance + aperçu pour
  chacune ; filtres type / catégorie / intensité / recherche ; « + Ajouter » à la tête de lecture, hors du visage,
  marqué `manual`. Catalogue `assets/banque/catalogue.json`, reconstruit tout seul si un dossier change.
- **Vecteurs** (*Plus → Graphismes → Vecteurs*, `remotion/src/vectors.tsx`, `assets/banque/vecteurs/` : 36 SVG écrits à
  la main + fiches) : couleurs principale / secondaire / contour par variables CSS (formes et animation intactes),
  ordre charte → style, ou couleur choisie ; « 🎨 Couleurs de la charte » ; taille (part du petit côté), position,
  rotation, opacité, entrée / sortie (pop, fondu, zoom, glisse, tracé).
- **Couleur des modèles** (*Plus → Graphismes*) : chiffre, cases cochées, carte, mot géant suivent la charte / le style,
  ou une couleur choisie (`props.color`) que la charte ne touche plus. Un graphisme posé ou verrouillé par le monteur
  reste visible dans un style avec habillage.
- **Chorégraphie** (*Plus → Chorégraphie* + piste *Chorégraphie*, `engine/editeur/choregraphie.py`,
  `remotion/src/choreo.tsx`, `app/ui/choreo-panel.tsx`, `app/ui/choreo-lane.tsx`) : l'IA (règles) choisit entrée, sortie,
  direction, durée, courbe et synchro (mot dit, temps de la musique) de chaque élément, avec une raison ; jamais deux
  entrées au même moment, rien sur l'accroche sauf le bandeau ; tout se règle, se désactive, se verrouille ; créée à la
  fin du montage automatique (`auto._finish`).
- **Verrous** (🔒 : graphismes, vecteurs, scènes, plans de coupe, bruitages, bandeau, plan créatif, mouvements,
  chorégraphie entière, et **plan** dans l'onglet Plan) : `engine/editeur/verrous.py` ; une retouche à la main = `manual`,
  même protection. Aucune passe automatique n'y touche (style, relecture, galerie, IA, cerveau créatif, chorégraphie,
  passage).
- **Refaire seulement ce passage** (barre de la timeline : « Début ici » / « Fin ici » ou touches I / O,
  `engine/editeur/passage.py`, `app/ui/passage.tsx`) : refait l'habillage automatique de la plage seulement ; rien ne
  change avant ni après ; bulle de compte rendu ; « Annuler ce passage ».

**Données** (`remotion/src/types.ts`, tout facultatif) : `notes`, `annotations`, `vectors`, `choreography` (+ `meta`),
`locked` / `manual` sur chaque élément, `banner.locked`, `creativePlan.locked`, `Clip.locked`, `sfx.extra[].gain` et chemins
de la banque. `REVIEW_KEYS` (notes, dessins) sont retirés des propriétés du lecteur ET de `render.mjs` : jamais exportés.

**Routes / ligne de commande** : `PUT /api/reels/:p/:v` (champs V2 validés, refus 400 en français, 20 Mo au plus),
`GET /api/v2`, `GET /api/banque?type=&categorie=&q=&format=&intensite=`, `GET /api/banque/apercu/<id>`,
`POST …/passage {debut, fin}`, `POST …/choregraphie {tout?}` (versions « avant » gardées). `python -m editeur banque
catalogue|construire|apercu`, `passage <projet> --reel v --debut a --fin b`, `choregraphie <projet> --reel v [--tout]`.

**Tests** — tout rejouer : `node docs/direction-creative-v2/tests/test-v2.mjs` (≈ 12 min : exports courts un à la fois +
interface ; `--rapide` ≈ 3 min sans exports). Il lance les suites de régression (build, tsc, node --check, moteur,
galerie, cerveau créatif, sobriété, timeline), les tests des agents (`tests/<agent>/`), l'intégration
(`tests/integration/` : un reel avec TOUTES les fonctions à la fois, nouvelle passe de l'IA, 4 styles, 2 chartes,
passage, montage automatique, 7 anciens reels, 4 exports de 2-4 s avec images, son et timecodes mesurés, interface dans
un Chrome sans fenêtre), puis affiche le tableau des 11 tests obligatoires du §9 de la passation. Planche d'images à
regarder : `runtime/cache/tmp/dcv2-integration/export-*/planche-integration.png` ; captures de l'interface :
`runtime/cache/tmp/dcv2-integration/navigateur-*/interface/`.

**Limites connues** : vecteurs à place fixe dans l'image (ne suivent pas la personne) ; dessins sur la piste principale
seulement (pas sur un plan de coupe ni sur l'écran partagé du Comparatif) ; crayon à main levée non convertible en
vecteur ; plans de coupe non recherchés à nouveau par « Refaire ce passage » ; Ctrl+Z n'annule pas un passage (bouton
« Annuler ce passage » ou Versions) ; scènes du style posées depuis la banque gardent la couleur de la charte du moment ;
effets de la banque = toute la vidéo ; emojis non verrouillables un par un (verrou du plan) ; « Refaire » de la Révision =
nouveau montage complet (verrous non reportés, version d'avant gardée) ; une retouche faite pendant une tâche du moteur
peut être écrasée à la fin de la tâche ; plans de coupe posés à la main toujours masqués dans un style avec habillage
(comme avant).

**Pièges (nouveaux)**
- Python dans un heredoc bash : `\b` devient un retour arrière (déjà au §11) — relire les expressions régulières écrites
  ainsi ; écrire plutôt le texte avec l'outil de fichiers.
- Sous Windows, tuer un processus Node (SIGTERM) n'exécute pas ses gestionnaires : un bac de test avec des jonctions
  s'arrête par un fichier `stop` (voir `tests/integration/bac-navigateur.mjs`), puis on vérifie qu'il ne reste aucune
  jonction AVANT d'effacer quoi que ce soit.
- Deux exports du MÊME reel ne sont pas identiques au pixel près (Chrome/GPU, écart moyen ≈ 1/255, aussi sans grain) :
  comparer des exports avec une tolérance, ou contre un 2e rendu de référence (`test-integration-export.py`).
- Le panneau navigateur de l'application fait 294 × 299 px : contrôler l'interface par le DOM, ou avec le Chrome sans
  fenêtre de Remotion (`remotion/node_modules/.remotion/chrome-headless-shell`, protocole DevTools).
- La crête d'un fichier AAC se mesure par canal : le repli en mono de FFmpeg (`-ac 1`) peut dépasser 1.

## 23. Pause du 2026-10-01 (vers 3 h 30) — montée en qualité en cours

L'utilisateur a demandé d'arrêter (PC allumé depuis plus de 24 h). **Lire `docs/qualite-2026-09-30/FILE-ATTENTE.md`
en premier** : état exact, ce qui est fait (V2, détourage RobustVideoMatting `models/rvm/` (GPL-3.0), contrôle qualité
`engine/editeur/controle.py`, ronde 2 construite mais relecture non terminée), Vidéo 2 retrouvée dans la corbeille
(supprimée volontairement par l'utilisateur le 2026-10-01 à 02 h 24 — ne pas restaurer ; rendre test-v2 indépendant des projets réels), et l'ordre de reprise (relectures ronde 2 → ronde 3 :
boucle d'auto-évaluation avec montages complets et juge indépendant). Copie du code avant la ronde 2 :
`docs/qualite-2026-09-30/avant-ronde2/`.

Piège nouveau : `TaskStop` sur un `editeur.ps1` lancé en arrière-plan laissait sa boucle de relance vivante ; un
2e `server.mjs` restait en vie après EADDRINUSE (le gestionnaire d'exceptions l'avalait). Corrigé en ronde 2
(sortie code 98 avant tout minuteur, le lanceur arrête d'abord l'ancien lanceur) — à confirmer par la relecture.

## 24. Ronde 3 — Vidéo 1 en qualité professionnelle (2 octobre 2026)

Compte rendu simple : **`docs/qualite-2026-09-30/COMPTE-RENDU.md`**.
- Vidéo finale : `livraisons/Lot 2026-09-30 10h51/Vidéo 1 - qualité - FINAL.mp4`. Le 1er export de la ronde est gardé
  sous `… - FINAL (ancien 2026-10-02 00h06).mp4`.
- Version : `projects/script1/reels/script-qualite.json` (`derivedFrom: script`, label « qualité », Tech 3D
  cinématique, détourage RVM recalculé ; les anciens détourages MediaPipe restent dans `assets/detourage`).
- Le reel de l'utilisateur (`script.json`, Tech application) n'a pas changé (sha1 08b767e3…).
- Notes :
  - contrôle de la vidéo 7,2 → 8,8 (0 important) ;
  - jugement du monteur ≈ 6,8 → 8/10.
- Le serveur n'a pas été relancé : `server.mjs` n'a pas changé ; le moteur Python et l'aperçu (`app/dist/app.js`)
  prennent le nouveau code d'eux-mêmes.

**Changements (généraux)**
- **`timeline.ts` — relances de cadre du studio** (`studioPunches`, `punchAt`, constantes `PUNCH*`) :
  - coupe franche = autre valeur de plan, sauf si un temps du récit y change déjà le cadre ;
  - entrée d'une interface = plan de base ;
  - « punch-in » sur un début de phrase, un mot en couleur ou, à défaut, un mot plein, au moins 2,6 s après la
    relance précédente ;
  - la sortie d'une interface compte 1 s plus tôt ;
  - jamais au-dessus de ×1,32, tête ≥ 5 % du haut ;
  - temps du storyboard en `prise-originale` = plan serré (`FACE_FRAME`) ;
  - les anciens reels sans plan créatif gardent un cadre fixe.
- **Scène `list`** (types `StyleScene.kind 'list'` + `items`) :
  - détectée par `galerie.enumerations()` (au moins 3 éléments introduits par un déterminant, après une virgule ou
    « et / ou ») ;
  - `studioListLayout` / `listParts` pour le gabarit commun ; `PlacedScene.marks` = instant de chaque élément ;
  - rendu `StudioCard` (repère « − » pendant le problème, coche ailleurs) ; repli simple dans `Scene`.
- **Bouton** : le 1er ET le dernier bouton d'appel à l'action sont montrés. Le dernier porte l'offre dite
  (`galerie.offre_dite` : une durée + gratuit/offert -> « 1 semaine gratuite »), plus grande dans `StudioCard`.
- **Sobriété** :
  - le bouton (scène `cta`) est permis sur la dernière phrase d'appel à l'action et passe avant les autres scènes
    (priorité `bouton`) ;
  - une autre scène qui déborde sur cette phrase est raccourcie (si elle garde au moins 1,4 s) au lieu d'être
    retirée.
- **Galerie** :
  - aucune interface créée pendant le temps « accroche » du plan créatif (`_hook_end`) ;
  - budget du mode produit : 1 écran / ~9 s ;
  - espacement par priorité (bouton > liste / parcours > tableau > chiffre / notification) ;
  - notification à deux indices (lead + réponse / appel) : confiance 2,5, que l'IA locale ne peut plus effacer.
- **Style `produit-3d.json`** : `budget {par_minute 7, ecart 3}`, musique 0,11 -> 0,19 (≈ 25 dB sous la voix).
- **Son** (`sfxEvents`, studio seulement) : whoosh à l'entrée de chaque interface, clic par élément de liste, son des
  mots forts sur la preuve du storyboard. Le pop d'un mot fort est retiré à 1,2 s d'une interface.
- **Sous-titres** : une ponctuation seule n'est jamais une page vide. Le signe ouvrant va au mot suivant, les autres
  au mot d'avant. Même règle dans `choregraphie.pages` et `passage._pages`.
- **Verre des cartes** du studio plus clair (`studioGlass`).
- **`graphismes.UNITS`** : + mois, day(s), week(s), month(s).
- **Contrôle (`controle.py`)** :
  - le pont fournit `studioCaptionLayout` (sous-titres), `studioMetricBox` (chiffre, graphismes et scènes) et
    `studioListLayout` (listes) : plus de copie du gabarit ;
  - `message-repete` ignoré quand chaque apparition est redite par la voix ;
  - `VERRE` à jour.
- **`design-panel.tsx`** : les curseurs montrent la place affichée (`designScenes`) et la première retouche la fige
  sans saut.

**Tests**
- Nouveaux : `docs/qualite-2026-09-30/tests/test-ronde3.mjs` (14) et `test_ronde3.py` (27, depuis `engine/`).
- Mis à jour avec un commentaire daté :
  - `test_controle.py` : l'ancien aperçu Tech 3D n'a plus de cadre figé ;
  - `test-timeline-v2.mjs` : les ponctuations seules sont masquées dans la copie donnée aux deux versions ; caméra et
    sons du studio exclus de la comparaison « identique à avant la V2 ».
- Généralité (même copie, code d'avant dans le bac `runtime/cache/tmp/ronde3-qualite/ancien`, qui contient des
  JONCTIONS) :
  - Tech application 7,4 -> 8,4 ;
  - Éditorial 5,7 = 5,7 ;
  - Hormozi 4,9 = 4,9 ;
  - Tech 3D 6,8 -> 8,5.

**Reste** :
- lumière chaude de la personne contre le studio froid ;
- gros plans agrandis (moins nets) ;
- pilules d'une liste de 4 un peu petites ;
- aucun plan de coupe (`media/broll` vide) ;
- le contrôle garde des conseils « carte terne » (mesure des pixels sur un verre sombre voulu).

**Pièges nouveaux**
- Un test « identique à l'ancien code » casse à chaque règle volontairement changée : neutraliser la règle dans
  l'ENTRÉE donnée aux deux versions (ici `hide` sur la ponctuation seule), jamais affaiblir la comparaison entière.
- Le bac `ancien/` a besoin de `runtime/cache/tmp`, `remotion/segments.mjs` et `projects/_cache` (jonction en
  lecture). Sans les médias, le contrôle annonce de faux « média manquant ».
- `grille.py` (tmp) trie mal les noms « …-12.00s.png » : un tiret est lu comme un signe moins. L'ordre des tuiles
  est donc inversé ; se fier aux étiquettes.

## 25. Ronde 3, cycle 2 — corrections générales après le juge indépendant n° 1 (2 octobre 2026)

Le juge (`docs/qualite-2026-09-30/JUGEMENT-1.md`) a noté l'export de 00 h 56 **6,5/10** (contrôle : 8,8). Compte rendu simple :
`docs/qualite-2026-09-30/COMPTE-RENDU.md`. Copie du code juste avant ce cycle : `docs/qualite-2026-09-30/avant-juge1/`.
- Vidéo finale : `livraisons/Lot 2026-09-30 10h51/Vidéo 1 - qualité - FINAL.mp4`. Les exports précédents sont gardés :
  `… FINAL (ancien 2026-10-02 00h06).mp4`, `(… 00h56)` (celui du juge), `(… 02h35)`, `(… 02h42)`.
- Version `script-qualite` corrigée par le vrai serveur (version « avant corrections du juge 1 (2 oct.) » gardée, puis PUT des
  mots relus, puis `POST …/template produit-3d`) ; le reel de l'utilisateur `script.json` est inchangé (sha1 08b767e3…).
- `server.mjs` n'a pas changé : pas de redémarrage.

**Rendu (`remotion/src`)**
- `timeline.ts` :
  - `overlayAt` (ce qui passe par-dessus l'image, même règle pour Reel.tsx et le contrôle), `pageAt`, `sayTokens` ;
  - `captionHidden` / `captionHiddenWhy` : les sous-titres RESTENT pendant une interface ; une page s'efface seulement si une
    scène la recouvre (même hauteur) ou si l'élément redit les mêmes mots (liste, bouton, parcours, chiffre, autocollant :
    au moins 2 mots porteurs et la moitié de la page). Styles sans habillage : inchangé (toujours affichés) ;
  - `studioTop` : haut libre 12 % en 9:16 (barre de TikTok / Reels), 6 % ailleurs ;
  - caméra : `StudioView.dy` (bascule : la personne descend jusqu'à 0,1 H quand une interface ne tient pas), `presence`
    (desserrage / retour SUR une coupe proche au lieu d'un glissement), relance × 1,2 avec plan de base qui cède
    (`PUNCH_MAX / 1,2`), relance sans coupe seulement si × 1,12 possible (`roomy`), choix du niveau à chaque coupe d'après la
    TAILLE À L'ÉCRAN (`onScreen`, autre prise et interface comprises), plan serré ancré sous la tête quand une coupe tombe
    pendant une interface, ouverture (`OPEN` 0,9 s) ;
  - scènes du studio : sortie sur une coupe qui arrive moins de 0,7 s avant leur fin ; bouton à deux temps (`lead` : l'offre
    entre quand elle est dite, `marks[0]` = le bouton) ;
  - `chiffreAffixes` : « 5× » (jamais « ×5 ») ; `studioCardSize('notification')` = hauteur du contenu ; bouton avec offre 0,3 u ;
  - sous-titres du studio sur 80 % de la largeur ; pas de whoosh de coupe dans le studio (clic quand le bouton rejoint l'offre).
- `design.tsx` : `StudioDesk` (bureau de verre noir au premier plan à la place exacte de la table du décor d'origine), liserés
  selon la lumière de la prise (froid du côté opposé, reflet chaud du côté de la lumière), lumière chaude motivée dans le studio,
  poussières lumineuses, grille qui glisse, balayage de lumière (+ ouverture), horizon, bas plus dense, `Sweep` (reflet à
  l'entrée des cartes), tableau / notification « problème » (teinte chaude, ✕, « ! »), bouton à deux temps avec badge d'offre,
  interface tenue jusqu'à la dernière image, bascule `dy` appliquée à la personne et au décor (parallaxe 0,3).
- `Reel.tsx` : `overlayAt` + `captionHidden` remplacent `designed` / `saysWords` ; repli du détourage avec la bascule ; entrée
  des sous-titres du studio en 0,08 s.
- `graphics.tsx` : multiplicateur compté 1× → 5× dans le studio.

**Moteur (`engine/editeur`)**
- `orthographe.py` (nouveau) : homophones é / er / ez (infinitif après une préposition ou un verbe comme pouvoir, infinitifs
  coordonnés, consigne à « vous »), accord après « sont », « Pi » → « Puis », majuscule en début de phrase ; texte d'origine dans
  `asr` ; jamais un plan verrouillé ; `infinitif()` pour les libellés ; `verifier()` pour le contrôle. Appelé par
  `reel.ensure` (mots NEUFS seulement) ; ligne de commande `python -m editeur orthographe <projet> --reel v [--appliquer]`.
- `galerie.py` : parcours à l'infinitif et en 2 étapes ; un fait dit avec son chiffre (« Lead en attente depuis 3 h ») passe avant
  un tableau générique ; teinte chaude (`CHAUD`) pour une notification / un tableau / un chiffre d'un problème vécu
  (`_negatif`) ; `offre_debut` (champ `lead` du dernier bouton).
- `detourage.py` : `scene()` (cache `scene.json`, `SCENE_VERSION` 4) = `lumiere()` (côté de la lumière sur le visage) +
  `occultant()` (table au premier plan : droite NETTE de la carte de présence, corps ≥ 0,85 d'un côté, ≤ 0,35 de l'autre, coin
  du bas) ; `_propager_occultants` (seulement si le décor est identique, caméra immobile).
- `controle.py` : pont `st` / `stWhy` / `dy`, `_parole_sans_texte`, `_orthographe`, `_coupes_meme_cadre`, zone du haut 12 %
  (important pour une carte sous 10 %), colonne de boutons à droite, « carte terne » ignorée pour le verre à liseré (passe
  vidéo), lumière chaude motivée, moment du bouton (`marque`) pour « message répété ».

**Tests** : `docs/qualite-2026-09-30/tests/test-juge1.mjs` (19) et `test_juge1.py` (20, depuis `engine/`), donnée figée
`tests/cas/juge1-p3d.json` ; `test_controle.py` 54 (le cas « propre » a deux vrais défauts nouveaux, vérifiés à part :
commentaire daté).

**Pièges nouveaux**
- `python -m editeur controle <reel.json>` SANS `--sortie` écrit dans `runtime/cache/controle/<projet>-<id>/` : un bac qui garde
  le même projet / id y laissait son rapport (déplacé dans `runtime/cache/tmp/ronde4q/controle-bac-egare/`). Toujours `--sortie`.
- Chercher la table dans l'IMAGE médiane de la prise (quand la présence ne la montre pas) trouvait le pied d'une chaise : essai
  abandonné. Les prises de Vidéo 1 n'ont pas la même caméra : la table d'une prise ne vaut pas pour une autre.
- `ffmpeg -vf fps=1` prend l'image du MILIEU de chaque seconde : une planche « 64 s » montre 64,5 s.
- Un long script Python dans un heredoc bash peut échouer (« unexpected EOF ») : l'écrire dans un fichier .py.

## 26. Ronde 3, cycle 3 — corrections générales après le juge indépendant n° 2 (2 octobre 2026)

Le juge n° 2 (`docs/qualite-2026-09-30/JUGEMENT-2.md`) a noté l'export de 3 h 01 **7,3/10** (contrôle : 9,4). Compte rendu simple :
`docs/qualite-2026-09-30/COMPTE-RENDU.md`. Copie du code juste avant ce cycle : `docs/qualite-2026-09-30/avant-juge2/`.
- Vidéo finale : `livraisons/Lot 2026-09-30 10h51/Vidéo 1 - qualité - FINAL.mp4` (export de 4 h 52, 71,47 s). Gardés à côté :
  `(ancien 2026-10-02 03h01)` (celui du juge n° 2), `(… 04h35)` et `(… 04h44)` (essais de ce cycle), et les plus anciens.
- Version `script-qualite` corrigée par le vrai serveur : version « avant corrections du juge 2 (2 oct.) » gardée, PUT des clips
  (orthographe relue + fin tenue), puis `POST …/template produit-3d` deux fois (détourage c5 recalculé sur la nouvelle plage,
  analyse du décor v6, grain du style). `script.json` de l'utilisateur inchangé (sha1 08b767e3…). `server.mjs` inchangé : pas de
  redémarrage.

**Rendu (`remotion/src`)**
- `timeline.ts` :
  - `studioDecorScale` : le décor du studio couvre toujours le haut pendant une bascule (bord haut = H/2·(1 − s) + 0,3·dy ≤ 0) ;
  - `cutoutHeadTop` / `trackValue` : haut RÉEL de la tête et largeur du visage lus dans `cutouts[clip].head` ; `rawPerson`, `headOf`
    et `studioPersonAt` s'en servent (avant : centre du visage − 1,1 largeur de visage, largeur 25 % par défaut : jusqu'à 5 % trop
    haut, la caméra reculait pour rien) ;
  - `occluderAt` : la table suit `occluderTrack` (caméra du téléphone qui dérive) ;
  - caméra pendant une interface (format vertical) : garde son plan de base et BASCULE (`StudioBusy.need/head`, `roomShift` calculé
    d'après l'échelle réelle, au plus `DY_ROOM` 0,12) ; changement de cadre à l'entrée / la sortie SUR une coupe à moins de
    `SNAP_UI` 1,5 s, sinon d'un coup sur un début de phrase (`tin` / `tout`), sinon glissement lent (`ROOM` 1,2 s) ;
  - coupe qui changerait trop peu le cadre : `StudioPunch.boost` (plan serré poussé jusqu'à × 1,15 de l'image d'avant, au plus
    `PUNCH_CUT_MAX` 1,4, seulement si c'est possible SUR la coupe) ; `onScreen` modélise le plan serré ancré sous une interface ;
  - ouverture : 1re image SERRÉE (× 1,2, tête à 5 % au moins du haut), puis recul en `OPEN` 0,9 s ;
  - `pages()` : 1) ponctuation seule collée, 2) coupures obligatoires (fin de phrase, pause, plan) et expressions figées `FIXED`,
    3) meilleur découpage par programmation dynamique (pages pleines, coupure après une virgule, jamais un petit mot `WEAK_END` en
    fin de page, pas de page éclair < 0,3 / 0,45 s, deux mots en couleur ou un nombre jamais séparés ; studio seulement : max + 1
    mots et pénalité des pages sur deux lignes) ; `remotion/segments.mjs` renvoie ces pages, que `choregraphie.pages` et
    `passage._pages` lisent telles quelles (plus de deuxième copie du découpage) ;
  - `saysSame` : une page dont TOUS les mots porteurs sont à l'écran s'efface aussi ; `studioCaptionLayout` : arrondi du nombre de
    lignes corrigé ;
  - `studioListLayout` : `widths` (rangée recentrée) ; badge seul (liste d'un élément) police 0,058 u.
- `design.tsx` : décor `studioDecorScale` ; personne : courbe `STUDIO_CURVE` (hautes lumières adoucies, noirs bleutés), bord
  décontaminé sur 5 px (couleur de l'intérieur par flou normalisé au lieu du mur blanc d'origine mêlé aux cheveux), liseré fin d'un
  seul côté (reflet chaud presque nul) ; lumière chaude aussi sur le mur derrière la personne (côté fenêtre) ; bas de l'image moins
  noir au centre ; table `occluderAt` ; rangée de liste recentrée au fil des mots.
- `Reel.tsx` : 1re page de sous-titres dès la 1re image (studio), virgule gardée à l'intérieur d'une page, mot en couleur qui
  « frappe » quand il est dit (× 1,1 ; × 1,2 sur l'accroche), halo sombre serré autour des mots en couleur.
- `styles/montage/produit-3d.json` : grain 0,04 → 0,1 (même texture pour la personne et le décor).

**Moteur (`engine/editeur`)**
- `orthographe.py` : `_accord_determinant` (singulier après « de la / la / le / l' / un / une / chaque / votre / notre / ce… », sauf
  après un sujet ou un pronom ; pluriel prudent après « vos / nos / mes / des / plusieurs / quelques ») ; mots invariables, nombres et
  fins invariables (‑ss, ‑us, ‑is, ‑ours…) jamais touchés. `verifier()` (contrôle) le voit aussi.
- `reel.py` : `fin_tenue` (la dernière prise continue `FIN_TENUE` 0,8 s après le dernier mot si la prise dure assez et que personne
  n'y parle — transcription en cache seulement, jamais Whisper ; jamais un plan verrouillé ou muet), appelée par `ensure` sur un plan
  neuf.
- `detourage.py` : `SCENE_VERSION` 6 ; `tete()` (haut réel de la tête dans l'alpha + largeur du visage de l'analyse, toutes les
  0,1 s) ; `coupes_droites` + `occultant_confirme` (la table d'une autre prise est reprise si la personne y est coupée net sur la
  même droite dans au moins 4 images, avec `occluderTrack`) dans `_propager_occultants`.
- `galerie.py` : `_claim_scenes` (badge de preuve dite, `_PREUVES` : « formé par nos soins », « sans engagement »…), priorité la plus
  basse, écart réduit à 4,5 s.
- `controle.py` : `bande_bord` + constat `bord-non-couvert` (passe vidéo) ; `_reculs_camera` + constat `recul-camera` (passe JSON) ;
  une fausse détection de visage loin du visage attendu (sur le pull) n'est plus comptée comme « visage couvert ».
- `choregraphie.py`, `passage.py` : pages lues dans `montage.compute` (`seg['pages']`), ancien découpage seulement en repli.

**Tests** : `docs/qualite-2026-09-30/tests/test-juge2.mjs` (18) et `test_juge2.py` (18, depuis `engine/`), donnée figée
`tests/cas/juge2-p3d.json`. Mis à jour avec un commentaire daté : `test-juge1.mjs` (ouverture serrée puis recul ; page « ça veut
dire »), `docs/direction-creative-v2/tests/test-timeline-v2.mjs` (pages et srt comparés avec une page = un mot, hors studio).

**Généralité** (copie figée, passe JSON ; code d'avant ce cycle dans le bac `runtime/cache/tmp/cycle3-10020500/avant`, qui contient
des JONCTIONS : ne jamais l'effacer récursivement) : Tech application 8,1 = 8,1 ; Éditorial 6,4 = 6,4 ; Hormozi 4,9 = 4,9 (visage
couvert par les sous-titres : 8,9 s → 5,1 s grâce au nouveau découpage).

**Reste** : bord de l'oreille et des boucles d'oreilles irrégulier (détourage) ; peau éclairée par une fenêtre ; doigts flous sur les
gestes rapides ; plan moyen pendant les 3 premières secondes de l'offre (place du bouton gardée au-dessus de la tête) ; coupe de
0:41,67 à × 1,13 (deux prises, tête déjà au bord du cadre) ; pas de plans de coupe.

**Pièges nouveaux**
- `sed -i` de Git Bash a réécrit `design.tsx` (CRLF) en LF : vérifier les fins de ligne après coup (compter les `\r\n` en
  Python). En CRLF : `design.tsx`, `graphics.tsx`, `controle.py`, `reel.py`.
- Un heredoc bash qui contient des barres obliques inverses ou certains guillemets peut échouer ou les modifier : écrire le script
  avec l'outil Write.
- `scene.json` des détourages est un cache PARTAGÉ : un bac du code d'avant le réécrit à sa version (prendre ses détourages ailleurs :
  `GEN_CUTOUTS_FROM`).
- Une page de sous-titres de 5 mots hors studio dépasse la zone sûre (taille fixe) : le « max + 1 » est réservé au studio.

## 27. Ronde 4 — nouvelle Révision, icônes, finition après le juge n° 3 (2 octobre 2026)

Compte rendu simple, avec où cliquer : **`docs/qualite-2026-09-30/COMPTE-RENDU-RONDE4.md`**. Copie du code juste avant :
`docs/qualite-2026-09-30/avant-ronde4/`. Trois groupes en parallèle (fichiers séparés), chacun relu par un relecteur
indépendant, puis une intégration (fin de cette section). (La demande parlait d'une « section 25 » : le numéro était pris.)

**Interface Révision (ronde 4a)** — `app/ui/revision.tsx`, `app/ui/icons.tsx`, bloc CSS `/* revision */` de `styles.css`,
en-tête de `App.tsx` ; d'après `docs/design/maquette/ANALYSE.md` et `captures/revision-1440.png`.
- Police Manrope (`@font-face` sur `/assets/fonts/Manrope.ttf`), icônes Lucide écrites en composants SVG (`icons.tsx`, note de
  licence ISC + MIT Feather en tête), classes `sr-*` (Révision) et `sa-*` (barre du haut). Anciennes règles `rv-*`, `.import`,
  `.dropzone`, `button.big` retirées ; blocs banque / vecteurs / revue / chorégraphie / passage identiques.
- `TopBar` (exportée par revision.tsx, utilisée aussi par l'éditeur) : onglets Révision / Éditeur (« complet » masqué par
  `.sa-cache` : les anciens tests cherchent « Éditeur complet »), compteurs du jour tirés de `/api/revision` (`created`
  d'aujourd'hui, statut `pret`, `taken.date` d'aujourd'hui), réglages (raccourcis, dossier Entrée, corbeille), pastille SA.
- Colonne gauche (348 px) : dépôt (fichiers, dossier, glisser-déposer, charte client), « Vidéos du jour », « Choisir plusieurs »
  → Toutes/Aucune, **Prendre** (export en lot des vidéos prêtes cochées, avec confirmation ; nouveau) et Supprimer ; Corbeille
  (Restaurer) ; dossier Entrée. Centre : lecteur Remotion, barre de lecture maison (`controls={false}`, piste ≥ 300 px), cadre
  du problème. Droite : 4 gros boutons, formats, carte Contrôle qualité (onglets Montage / Export, moments ▶ cliquables), phrases
  du script absentes, exports par format, carte d'erreur, montage en cours (5 étapes déduites des textes de progression d'auto.py).
- « Autre style » : panneau par-dessus la colonne de droite ; on choisit puis « Appliquer ce style » (double-clic = tout de
  suite). Galerie ouverte : seul « Style depuis une vidéo » accepte un dépôt (PUT `/api/references` + POST
  `/api/references/analyser`) ; ailleurs le dépôt est refusé (avant : la vidéo partait au montage automatique).
- Raccourcis : Entrée = Je la prends, E = Modifier, S = Autre style, → = Suivante, Espace, Échap. Souris / clavier distingués
  (après un clic souris, Entrée = Je la prends ; après Tab, Entrée active l'élément qui a le focus). E et S ignorés pendant une
  action. Ctrl+Z bloqué dans la Révision (écouteur en capture, message). Verrou contre deux exports ou deux envois à la fois.
- La vidéo choisie est gardée au retour de l'éditeur (variable de module `choixGarde`). `montrer(k, d)` : jamais le montage
  d'une autre vidéo sous le titre affiché.

**Icônes (ronde 4)** — `engine/editeur/banque.py`, `remotion/src/vectors.tsx`, `app/ui/banque.tsx`, `app/ui/vector-panel.tsx`.
- Lucide 1.49.0 (paquet npm `lucide-static`, registry.npmjs.org, archive 6,8 Mo, sha256 c8c9d5dc…ebba3 ; licence ISC, quelques
  dessins dérivés de Feather, MIT) : 1 857 SVG dans `assets/banque/icones/lucide/` (+ LICENSE, tags.json, SOURCE.txt).
- Index français `assets/banque/icones/dictionnaire-lucide-fr.json` : 558 icônes nommées et classées à la main, traduction mot à
  mot + règles de catégorie pour les autres (30 catégories), 112 mots anglais courants (aussi pour les imports). Recherche en
  français et en anglais, sans accents.
- Catalogue À PART `assets/banque/catalogue-icones.json` (type `icone`, `banque.construire_icones`, `CODE_ICONES` 2),
  reconstruit tout seul si `assets/banque/icones` ou `assets/banque/import` change (signature `os.scandir`). `catalogue.json`
  garde ses 4 types (556 entrées).
- `assets/banque/import/` (LISEZMOI.txt) : SVG / PNG achetés ; sous-dossier = catégorie ; licence « À vérifier (importé) » (un
  LICENSE du pack est signalé) ; SVG piégés refusés ; PNG ≤ 8 Mo ; nom accentué ou chemin > 150 caractères → copie sous un nom
  court dans `assets/banque/apercus/import/` (l'original n'est jamais touché).
- Rendu : une icône = `VectorItem` avec `meta.icone = {style, nom, banque}` (types.ts inchangé). `prepareIcon` : **trait**
  (liseré + ombre), **plein** (pastille ronde, icône à la couleur la plus lisible), **verre** (flou derrière, verre fumé,
  reflet, liseré, lueur en anneau, icône en dégradé). Couleurs par variables `--ic-*` (charte si `null`). Formes jamais
  modifiées. `inlineClassStyles` (règles `.classe` d'Illustrator recopiées en ligne), `monoToCurrent` (une seule couleur
  neutre → `currentColor` → charte ; logo coloré ou plusieurs couleurs gardés). PNG posés par `<Img>`. Verre + chorégraphie :
  `VectorLayer` applique lui-même `animateElement` (opacité sur les calques). Un vecteur sans `meta.icone` hors des dossiers
  d'icônes garde exactement son rendu.
- Interface : Plus → Banque → filtre **Icônes**, bascule Trait / Plein / Verre (localStorage), « + Ajouter » à la tête de
  lecture ; Graphismes → Vecteurs : style, couleurs par style, « Couleurs de la charte ».

**Finition après le juge n° 3 (ronde 3bis)** — `remotion/src/{timeline.ts, Reel.tsx, design.tsx, graphics.tsx, types.ts}`,
`engine/editeur/{detourage.py, detourage_rvm.py, galerie.py, controle.py}`.
- Vidéo : `livraisons/Lot 2026-09-30 10h51/Vidéo 1 - qualité - FINAL.mp4` (export de 6 h 58, 71,47 s, contrôle 10/10, 0 constat,
  −14,0 LUFS, crête −1,0 dBTP, LRA 3,1). Gardés : `(ancien 2026-10-02 04h52)` (celui du juge n° 3), `(… 06h22)`, `(… 06h39)`.
  Version « avant finition ronde 3bis 2 oct » gardée ; `script.json` de l'utilisateur inchangé (sha1 08b767e3…).
- `timeline.ts` : caméra du studio — plus jamais de bascule sur un simple début de phrase : coupe à ≤ 1,5 s (`SNAP_UI`), sinon
  coupe jusqu'à 3 s avant (`PRE_CUT`, champ `pre`), sinon sur l'image d'entrée de la carte (× 0,83) ou glissement adouci
  (`EASE_UI` 0,8 s, `span` ≤ 1,6 s) ; champs `ein / eout / pre / span` de `StudioBusy` ; pas de sortie pour une interface
  tenue jusqu'à la fin. Bouton unique : `StyleScene.offer / offerClip`, `marks = [entrée, offre]`, clic quand l'offre rejoint.
  `pageHides` / `PAGE_MIN_SHOWN` 0,6 s (+ fondu de 3 images dans Reel.tsx) ; `WEAK_END` étendu ; `typo()` = apostrophe « ’ »
  (sous-titres, cartes, graphismes, bandeau, titre Documentaire) ; frappe du mot en couleur plafonnée par sa chasse, sans rebond.
- `detourage_rvm.py` : `_fond_clair` (décor clair : frange du mur retirée, blanc intérieur repeint à la teinte de la peau voisine,
  yeux / dents / or des boucles gardés) et `_mains` ; `detourage.py` VERSION `v8-rvm-bords` (détourage refait au prochain style
  appliqué ou à la prochaine actualisation sur toute vidéo Tech 3D : plusieurs minutes de carte graphique par plan).
- `galerie.py` : `CTA_UNIQUE` 14 s (deux demandes proches = un seul bouton tenu jusqu'à la fin, `offer` = mot de l'offre ; jamais
  si un bouton est déjà retouché ou verrouillé : on garde alors les deux boutons d'avant) ; `_aligner_pages` (une carte qui redit
  la page en cours entre sur son 1er mot, sa fin ne bouge pas, jamais à moins de 0,5 s de la fin de la carte d'avant).
- `controle.py` : constats `saut-cadre`, `sous-titre-eclair`, `bouton-revient`, `apostrophes`, `bord-clair` (passe vidéo) ;
  `_fige` compte les marks comme relances. Aucune table de libellés par code dans l'interface ni le plugin : rien à ajouter.

**Intégration (2 oct., vers 8 h 30)**
- `app/server.mjs` : `GET /api/banque?type=icone` accepté (`?icones=1` = tout + icônes) ; `/api/banque/apercu/icone:…` lu dans
  `catalogue-icones.json` (cache par fichier). `engine/editeur/__main__.py` : `banque catalogue --type icone` et `--icones`.
  Plugin `banque_catalogue` : type `icone`. → **serveur relancé** (voir plus bas).
- `app/ui/App.tsx` : le gestionnaire clavier de l'éditeur (Ctrl+Z, Espace, flèches) ne s'exécute plus que dans l'éditeur
  (`view === 'edition'`). L'historique est déjà vidé à chaque ouverture d'un reel (`load`).
- `app/ui/Timeline.tsx` : piste des vecteurs → nom français des icônes (`iconName`), infobulle « Icône : … ».
- `engine/editeur/choregraphie.py` : `_icone_au_trait` — une icône des dossiers d'icônes dont la racine porte un trait peut être
  « tracée » (même règle que `prepareIcon`).
- `styles.css` (bloc controle) : le cadre du problème clignote du rouge `#F87171` au cyan `#38E1FF` de la maquette (avant : jaune).
- `docs/direction-creative-v2/tests/banque/test-interface-banque.mjs` (hors liste verte) : 6e filtre « Icônes » et « sur » ≥ 556
  acceptés (commentaire daté). Les 4 tests modifiés par la finition (test-ronde3.mjs, test_ronde3.py, test_juge1.py,
  test-timeline-v2.mjs) : relus, gardés.
- `revision.tsx` : espaces insécables dans « clique « Relancer le contrôle » » (le « « » restait seul en fin de ligne).
- **Vrai serveur relancé le 2 oct. à 8 h 41** par `editeur.ps1` (nouveau lanceur 51316 → serveur 26084 ; ancien lanceur 37860 et
  serveur 21328 arrêtés par lui), seulement après `/api/revision` `busy:false`, aucun export en file ni processus enfant ;
  `EDITEUR_SANS_NAVIGATEUR=1`, fenêtre réduite. Vérifié : un seul `server.mjs`, `GET /api/v2` = 200, `/api/banque?type=icone`
  et l'aperçu `icone:lucide:handshake` servis. Captures du vrai éditeur en lecture seule (écritures bloquées dans le Chrome de
  capture : `runtime/cache/tmp/integration-r4/capture-reel.mjs`), copiées dans `docs/qualite-2026-09-30/captures-ronde4/`.
- Le plugin MCP déjà chargé dans une session Claude garde l'ancienne liste (type `icone`) jusqu'à sa prochaine ouverture.

**Contrôles verts (liste à jour)** : ceux de la file d'attente + `node docs/qualite-2026-09-30/tests/test-juge3.mjs` (18),
depuis `engine/` : `python ..\docs\qualite-2026-09-30\tests\test_juge3.py` (24) et `python ..\docs\qualite-2026-09-30\icones\test_icones.py`
(5) ; `node docs/qualite-2026-09-30/icones/planche-icones.mjs` (22 329). Tests d'interface sur bac : `runtime/cache/tmp/interface-r4a/`
(`setup-bac.mjs`, puis serveur de la copie sur 18795, `test-ui.mjs` 39, `capture.mjs`) et `docs/qualite-2026-09-30/icones/ui-icones.mjs <bac> <port>`.

**Reste** : juge n° 4 sur l'export de 6 h 58 ; limite de la prise (mur blanc, fenêtre : peau très claire, oreille floue, doigts
flous) ; fin en plan moyen ≈ 8 s ; place vide au-dessus du bouton 0:59,8–1:04,45 ; frappe du mot plus discrète ; coupure de
ligne « quelqu’un à | temps plein » ; glissements de caméra possibles sur d'autres vidéos sans coupe proche (sous le seuil du
contrôle) ; une scène automatique qui chevauche une scène protégée d'un AUTRE type peut encore la cacher (`verrous.fusionner` met
les nouvelles avant les protégées ; corrigé seulement pour le bouton — à faire dans verrous.py + `anchoredScenes` + la copie
Python de `choregraphie`) ; le reste de l'éditeur garde l'ancien thème ; pas d'onglet « Système de design » ; l'onglet Éditeur
ouvre le dernier reel de l'éditeur (pas forcément la vidéo choisie dans la Révision : « Modifier » le fait) ; ≈ 1 300 icônes au nom
traduit mot à mot ; caches de détourage v6 / v7 (≈ 741 Mo dans `assets/detourage`) : à l'utilisateur de décider.

**Pièges nouveaux**
- Chrome sans écran ne livre pas le « drop » du protocole DevTools : tester avec un `DragEvent` + `DataTransfer` créé dans la page.
- Tester les raccourcis avec de VRAIS clics souris (`Input.dispatchMouseEvent`) : `element.click()` ne déplace pas le focus.
- Ne jamais mettre les icônes dans `catalogue.json` (le test serveur attend 4 catégories et 556 entrées).
- Chemin d'un vecteur : `[A-Za-z0-9/_.-]` seulement et ≤ 160 caractères (serveur) ; id d'icône importée
  `icone:import:<Dossier>-<nom>`, trop long ou en double → `-<ext><hash8>`.
- Imports : licence lue une fois par dossier (par fichier : 225 s pour 1 500 icônes, au lieu de 3 s).
- Dégradé de trait en `userSpaceOnUse` (en `objectBoundingBox`, un trait horizontal disparaît).
- Verre : jamais de filtre ni d'opacité CSS sur un parent (cela coupe `backdrop-filter`).
- Changer `VERSION` du détourage à chaque essai, sinon le cache est repris.
- Une règle de temps mise seulement dans `timeline.ts` casse la chorégraphie (qui lit les temps des mots) : la mettre dans les
  données (galerie).
- Un « \a » dans une chaîne Python non brute devient le caractère cloche.
- `runtime/cache/tmp` contient ≈ 148 JONCTIONS vers de vrais dossiers (assets, venv, tools, node_modules, models, projects/_cache),
  laissées par les bacs (interface-r4a, revue-interface-r4a, ronde4q, fable2-*…) : ne jamais vider ce dossier avec un outil qui
  suit les jonctions ; retirer d'abord les liens (`rmdir`).
- `python -m editeur banque catalogue` lancé à la main dans Git Bash avec une sortie redirigée (pipe) : `UnicodeEncodeError` (cp1252,
  « ✅ » dans un nom) et une ligne dans `runtime/cache/erreurs.log` ; mettre `PYTHONIOENCODING=utf-8` (le serveur le fait déjà).
  La ligne du 2 oct. vers 8 h 45 dans ce journal vient d'un essai de l'intégration, pas de l'utilisateur.
- La Révision peut changer le reel côté serveur (style appliqué) pendant que l'éditeur garde l'ancien en mémoire : l'éditeur relit
  le reel à chaque ouverture (`load`), ne pas garder son historique d'une ouverture à l'autre.

## 28. Juge n° 4 (2026-10-02) et correctif de la saccade du détourage

Juge n° 4 : **7,9/10** (JUGEMENT-4.md ; 6,5 → 7,3 → 7,6 → 7,9). Défaut ancien trouvé par le juge : la personne
détourée saccadait (≈ 1 image sur 5 répétée) à cause de `Math.floor((tSrc - start) * fps)` sans marge
(`remotion/src/design.tsx`, calcul de l'image de détourage) : les flottants donnent 4,9999… au lieu de 5.
Corrigé par le chef d'équipe avec une marge de 1/1000 d'image (`+ 1e-3`) ; simulation sur la version qualité :
316 images répétées → 0. Nouvel export complet lancé (l'ancien gardé : « (ancien 2026-10-02 06h58) »).
Piège : tout index d'image calculé depuis un temps doit avoir cette marge. Restes signalés par le juge : voile
gris-blanc le long de la mâchoire pendant l'offre, fin statique 8 s, léger glissement avant le « 5× », mains rapides.
Plugin : l'outil MCP `controle` accepte maintenant `version` (ex. `script-qualite`). Sans lui, l'export d'une autre
version que celle de la Révision était comparé au mauvais montage (faux « 6,2/10 » : durée et textes du reel
`script`). Contrôle de l'export final de 9 h 12 contre `script-qualite` : 10/10 « Prêt à livrer ». Passage 16-21 s :
paires d'images quasi identiques sur la personne 54 → 3 (saccade réglée). Recharger le plugin (nouvelle conversation).
Écran noir dans l'aperçu à partir de 0:19 (Vidéo 1 redéposée, 2026-10-02) : le Player Remotion plantait avec « Tried to
simultaneously mount 6 <Html5Audio /> tags … limited to 5 » (voix par plan avec J/L-cuts + musique + bruitages). Corrigé :
`numberOfSharedAudioTags={24}` sur les deux Player (`app/ui/App.tsx`, `app/ui/revision.tsx`). L'export n'était pas touché
(rendu sans balises audio partagées). Le contrôle qualité ne voit pas ce genre de plantage de l'aperçu (il ne joue pas
le Player) : à ajouter un jour (test navigateur qui lit tout le montage et relève les erreurs de console).
Petit défaut vu au passage : dans la Révision, la flèche → sert à la fois à « Suivante » et à avancer dans la barre de lecture.

## 29. Claude (API Anthropic), « Dis à l'IA ce que tu veux » et sons de coupe variés (2 octobre 2026, soir)

Demande de l'utilisateur : Opus obligatoire ? (non : **Sonnet 5.5 par défaut**) ; un endroit pour expliquer à l'IA ce qu'il veut
une fois le montage fait ; plusieurs sons de coupe (avant : toujours le même « whoosh-court », le « son de vent ») ; il n'a que
**2,00 $ US** de crédit, pour tester. **Exception à la règle 3 du §2 (tout local) demandée par l'utilisateur** : Claude est EN
OPTION, plafonné, et le chemin local reste le repli partout. Compte rendu simple : **`docs/claude-api/RESULTAT.md`**. Copie du
code d'avant : `docs/claude-api/avant/` (claude_api.py et la commande `claude` y ont été commencés après, par un essai
interrompu). Six groupes en parallèle (noyau, cerveau, critique, consigne, sons, interface), relus, puis une intégration.

**⚠️ Bloquant au 2 oct. 19 h : la clé de l'utilisateur est une clé d'organisation SANS espace de travail.** Anthropic répond 400
« This API key is not scoped to a workspace… anthropic-workspace-id » (non facturé). Deux vrais essais ont reçu ce refus (17 h 10
`claude test` Haiku, 19 h 05 cerveau Sonnet sur une copie) : **0,00 $ dépensés**. L'utilisateur doit copier l'identifiant
`wrkspc_…` (platform.claude.com → Settings → Workspaces) dans ⚙️ → Claude → Avancé → Espace de travail (réglage
`espace_travail`), ou l'écrire dans `cles-api.env` (`ANTHROPIC_WORKSPACE_ID=wrkspc_…`, lu par `banques._load_keys` depuis ce
soir), ou créer une clé dans un espace de travail. Vérifier : `python -m editeur claude test` (Haiku, < 0,001 $). Après ce refus,
`claude_api` met Claude en pause 10 min (`espace_manquant`) : aucun autre appel ne part.

**Fichiers**
- Moteur : `engine/editeur/claude_api.py` (noyau : réglages, modèles, budget, registre, journal, appel), `cerveau_claude.py`
  (idées du montage), `critique_claude.py` (avis sur les images d'un export), `consigne.py` (« Dis à l'IA »), `sfxgen.py`
  (sons de coupe + familles), `banque.py` (65 sons ajoutés à la banque, `CODE` 7) ; branchements dans `auto.py` (`_finish` :
  cerveau, bandeau, titre), `reel.py` (`rehighlight` / `auto_highlights` force, `refresh_ai`, `_apply_template` → famille de
  sons), `passage.py` (`_mots` : mots de Claude), `galerie.py`, `creative.py`, `graphismes.py`, `controle.py` (section « Avis de
  Claude », verdict combiné). `banques/__init__.py` lit aussi `ANTHROPIC_WORKSPACE_ID`.
- Données : réglages **`styles/claude.json`** ; registre des dépenses **`projects/_claude.json`** (jours, mois, vidéos, alertes
  « crédit épuisé » / « espace manquant ») ; journal **`runtime/cache/claude-appels.jsonl`** (une ligne par appel, jamais de texte
  envoyé ni de clé) ; avis déjà payés `runtime/cache/claude-critiques/` (les effacer = les repayer) ; verrous
  `runtime/cache/claude.lock` et `runtime/cache/claude-verrous/` (sans danger à effacer au repos) ; familles
  **`styles/sons-transitions.json`** ; sons `assets/sfx/editeur/*.wav` (+ `LICENCE.txt`).
- Interface : `app/ui/consigne.tsx` (boîte 💬), `app/ui/sons-transitions.tsx` (carte « Sons des coupes »), `revision.tsx`
  (⚙️ « Claude (IA en ligne) », boutons « 🧠 Refaire avec Claude » / « 👁 Critique Claude », coût par vidéo, ligne « Idées : … »,
  « Avis de Claude » dans le Contrôle qualité), blocs CSS `/* claude */` puis `/* consigne editeur */` de `styles.css`.
- Montage dans l'interface (intégration) : `<Consigne>` dans la Révision (bloc « Retouches par l'IA », colonne de droite, dès que
  la vidéo est prête) et dans l'éditeur (haut du panneau de droite, réductible, préférence `localStorage`
  `editeur-sami:ia-ouverte`) ; `<SonsTransitions>` dans `panels.tsx` (StylePanel, sous « Bruitages »).
- Plugin : `claude_couts` (lecture), `claude_critique` et `consigne` (payants, sur demande explicite) ; `proposer` type « ia »
  peut faire UN appel payant ; skill `plugins/editeur-sami/skills/claude/SKILL.md`.

**Réglages par défaut (`styles/claude.json`)** : `actif` true, `modele` claude-sonnet-5-5, `modeles_taches` {cerveau, critique,
consigne : null}, efforts medium / medium / low, plafonds 0,25 $ par vidéo, 0,75 $ par jour, 2,00 $ par mois, `credit_depart`
2,0 au `credit_date` 2026-10-02, `critique_auto` false, `images_critique` 16, `largeur_images` 540, `espace_travail` null.
Éteindre : ⚙️ → Claude → « Activer Claude », ou `python -m editeur claude reglages --json "{\"actif\": false}"` ; pour un
traitement : `EDITEUR_CLAUDE=0` (et `EDITEUR_LLM=0` coupe aussi Claude, sauf avec `EDITEUR_CLAUDE=1`).

**Requêtes (claude_api)** : Sonnet / Opus = `client.beta.messages.create` + `betas=["server-side-fallback-2026-07-01"]`,
`fallbacks="default"`, `output_config.effort` explicite ; Haiku = `client.messages.create` sans effort ni beta ; jamais
`thinking`, ni pré-remplissage, ni `tool_choice` ; sortie structurée `output_config.format` json_schema strict ; système en cache
(`cache_control` ephemeral) ; images JPEG ~540 px avant le texte. `stop_reason` vérifié d'abord (refus, coupé). Un 400 qui parle
d'effort / fallback / beta / thinking → un seul nouvel essai sans ce champ. Erreurs en français ; crédit épuisé → « Crédit
Anthropic épuisé : recharge sur platform.claude.com (Billing). L'outil continue en local. » + pause 10 min. `appeler()` ne lève
jamais ; avant chaque appel : actif, clé, SDK, pas d'alerte récente, puis crédit restant et plafonds contre une estimation
HAUTE. Coût = entrée × prix + écriture du cache × 1,25 + lecture du cache + sortie (réflexion comprise), noté même en cas
d'échec. `statut()` (≈ 0,2 s) donne aussi `modeles[].estimation` (coût typique par modèle).

**Cerveau** : UN appel par montage, gardé dans `reel.claude.cerveau` (signature = plans, sources, débuts des mots, mots coupés ;
ni texte ni style) : changer de style, rouvrir, « Relancer l'IA », refaire le même montage = 0 $ ; `--forcer` repaie. Tout passe
par des validateurs locaux (`ecartes` liste ce qui est retiré). Appel payé sans résultat → `reel.claude.cerveau_echec` (pas de
nouvel essai pour ce montage et ce modèle, sauf `--forcer`). Un verrou par reel empêche deux processus de payer deux fois.
Consommateurs : mots en couleur (force), `auto._finish` (bandeau, corrections, titre), galerie (titres des notifications,
bouton), creative (temps du récit, direction), graphismes (listes, mot géant), `refresh_ai` (propositions, dont
`suggestions.corrections`), « Refaire ce passage ». Chaque nouveau montage automatique fait un appel quand Claude est prêt
(≈ 0,03–0,06 $ avec Sonnet ; le plafond du jour arrête vers 15 vidéos, les suivantes sont montées en local).

**Critique** : `critique_claude.critique()` ; 16 images (réglage) choisies aux moments utiles, description du montage et
mesures du contrôle local ; résultat rangé à part dans le rapport du contrôle (section `claude`) ; un « bloquant » de Claude fait
passer « Prêt à livrer » à « À corriger avant de livrer » (`verdict_local` garde l'autre). Cache par sha1 de la vidéo + signature
du reel. Automatique après export seulement si `critique_auto` (dans `controle.main`, pas dans le serveur : un seul appel).

**Consigne** : 41 opérations fermées, schéma strict ; chaîne Claude → Qwen local (même schéma en grammaire) → règles simples ;
question si ambigu ; refus et notes pour le reste ; jamais un verrou levé sans « déverrouille » dans la demande ; sauvegarde sur
place avec `versions/<rid>/<stamp> avant IA ….json` (Annuler = restaurer) ; déclinaison = nouvelle version ; historique
`reel.consignes` (50 au plus), jamais exporté (`REVIEW_KEYS` de `types.ts`, `render.mjs`, serveur).

**Sons de coupe** : 52 sons créés ici + 13 Kenney CC0, même niveau K-pondéré (−11 LUFS sur 100 ms), `pic` = 90 % de l'enveloppe
centrée de 20 ms ; 7 familles (doux, punchy « Énergique », tech, cinema, retro, glitch, organique) × 6 rôles (transition,
interface, apparition, mot-fort, impact, cta) ; `styles` → famille pour les 20 styles. `timeline.ts` : `SFX_POOL_DEFAUT` +
`varySfx` (déterministe, jamais deux fois de suite, aucun des 3 derniers si ≥ 4 sons, pic sur la coupe, clics sur leur mot) ;
`sfx.varier === false` = exactement les sons d'avant ; `sfx.famille` / `sfx.pool` (32 au plus). `reel._apply_template` appelle
`sfxgen.appliquer_famille(reel, avant=…)` : famille choisie à la main gardée, sinon celle du nouveau style. « Enregistrer comme
mon style » garde `famille` et `varier: false`.

**Routes** : `GET /api/claude` (statut sans clé, coût par modèle), `PUT /api/claude/reglages`, `GET /api/claude/couts`,
`POST /api/reels/:p/:v/claude/cerveau`, `POST …/claude/critique {video?}` (vidéo EXPORTÉE), `POST …/consigne {texte, t?,
moteur?, simuler?}`, `GET /api/sons-transitions` ; le PUT du reel valide `sfx.varier/famille/pool`. Un seul travail Claude à la
fois par vidéo (409). Après une consigne : nouvelle note du contrôle seulement si le montage a changé (`r.modifie`) ; fiche de la
Révision mise au style du reel.

**Ligne de commande** (depuis `engine/`) : `python -m editeur claude statut | reglages [--json …] | couts [--video p/v] | test
[--modele id]` ; `cerveau <projet> --reel v [--forcer]` ; `critique <video.mp4> --reel <export.json | projet v> [--images 12]
[--refaire] [--estimer] [--json]` ; `consigne <projet> --reel v --texte "…" [--t s] [--moteur auto|claude|local] [--simuler]` ;
`sons <projet> --reel v --famille auto|doux|… [--varier oui|non]` (relayées telles quelles vers `editeur.<module>`).

**Coûts** (estimations, pas encore mesurés sur un vrai appel) : Sonnet 5.5 — cerveau 0,03–0,06 $, consigne 0,014–0,02 $, avis
16 images ≈ 0,054 $ (au pire 0,113 $) ; Haiku 4.5 — cerveau ≈ 0,008 $, consigne ≈ 0,009 $, avis ≈ 0,021 $ ; Opus 5.5 ≈ 2× Sonnet.
Recalibrer `claude_api.PROFILS` d'après le registre après les premiers vrais appels.

**Intégration (2 oct., 18 h 30 – 20 h)** : `__main__.py` (relais cerveau / critique / consigne / sons, clé masquée dans
`erreurs.log`), `passage._mots` (force), `reel._apply_template` (famille), `server.mjs` (fin de `lancerConsigne`,
`templateFromReel`), `types.ts` (`consignes` dans `REVIEW_KEYS`, champ `consignes`), `render.mjs`, `claude_api.statut()`
(`modeles[].estimation`), plugin `proposer`, montages `<Consigne>` / `<SonsTransitions>`, ligne « Idées : … » de la Révision,
corrections proposées par Claude dans la carte IA de l'onglet Texte (`panels.tsx` : Accepter / Refuser, ponctuation et majuscule
gardées, texte d'origine dans `asr` ; `Suggestions.corrections` dans `types.ts`).
**Vrai serveur relancé le 2 oct. à 19 h 06** par `editeur.ps1` (lanceur 51316 / serveur 26084 arrêtés par le nouveau lanceur
13712 → serveur 13512), après `/api/revision` busy false et aucun export en file ; vérifié : un seul `server.mjs`, `/api/v2` 200,
`/api/claude` 200 (`cle: true`, aucun texte de clé), `/api/sons-transitions` 200.

**Essais réels** (bac `runtime/cache/tmp/integ-claude-1002/`, rapport `reel/rapport-essai.json`) : cerveau → refus « espace de
travail » (0 $) ; critique et consigne par Claude non envoyées (pause) ; consigne locale : sous-titres #FFFFFF → #FFD400, musique
0,19 → 0,133 en 12,5 s. Sons sur Vidéo 1 Tech 3D : entrées d'écran whoosh-court ×7 → 5 sons différents sur 7 (famille Tech) ;
effets seuls −36,7 → −36,8 LUFS (même niveau), son final à −14 LUFS, crête −1,0 dBTP ; spectrogrammes `sons/effets-*-spectre.png`
regardés. `plafond_video` mis à 0,20 pendant l'essai puis remis à 0,25.

**Tests** (tous sans vrai appel ; faux client, `claude_api._client` / `_cle` remplacés, réglages / registre / journal en bac) :
depuis `engine/`, `python ..\docs\claude-api\tests\test_noyau.py` (139), `test_cerveau.py` (90), `test_critique.py` (135),
`test_consigne.py` (137), `test_sons.py` (45) ; `node docs/claude-api/tests/test_sons.mjs` (43) ; interface :
`node docs/claude-api/tests/interface/setup-bac.mjs` puis `test-http.mjs` (110), `test-ui.mjs` (17), `test-mcp.mjs` (16),
`test-contrat-moteur.mjs` (11 : vrais modules, Claude éteint) — refaire `setup-bac.mjs` avant chaque test.

**Pièges nouveaux**
- Clé d'organisation sans espace de travail : 400 non facturé, il faut l'en-tête `anthropic-workspace-id` (voir plus haut).
- Tout nouveau test qui appelle `auto._finish`, `auto.run`, `reel.refresh_ai`, `passage` ou `consigne` doit mettre
  `EDITEUR_LLM=0` (ou remplacer `claude_api._client` / `_cle` et les chemins), sinon il peut faire un VRAI appel payant.
- Ne pas changer `cerveau_claude.VERSION` à la légère : tous les résultats gardés deviennent caducs (nouveaux appels payés).
- `python -m editeur.sfxgen` SANS argument = `creer` (réécrit les sons) : passer par `python -m editeur sons …`.
- `test-timeline-v2.mjs` : sons variés neutralisés par `sfx.varier = false` dans la copie donnée aux deux versions.
- Le lot « Lot 2026-09-30 10h51 » (Vidéo 1) est parti à la corbeille (suppression par l'utilisateur à 16 h 13, puis Vidéo 1
  redéposée dans « Lot 2026-10-02 16h14 ») : `script-qualite.json` est dans `corbeille/2026-10-02 16h13 …` ; les cas figés de
  `test_controle.py` et `test_juge1.py` lisent les rushs absents dans la corbeille (`docs/qualite-2026-09-30/tests/rushs.py`,
  lecture seule) ; `test_juge2.py` « fin tenue » reste en échec (17/18) : la transcription en cache est rangée sous le CHEMIN du
  rush (`media.cache_name`).
- Deux serveurs de test sur le port 18797 (test-serveur de test-v2 et un bac d'interface) se gênent : un bac par port.
- Python lancé en sous-processus sous Windows : `PYTHONIOENCODING=utf-8` (accents du JSON) ; le relais de `__main__` et les
  modules Claude reconfigurent déjà leur sortie.
- Un long texte en français dans un heredoc bash peut faire échouer toute la commande (guillemets) : l'écrire avec l'outil Write.

**Reste** : le premier vrai appel (après l'espace de travail) ; mesurer les vrais coûts et recalibrer `PROFILS` ; comparer le
premier avis de Claude au juge n° 4 (7,9/10) ; écoute des familles par l'utilisateur ; les cartes « chiffre » de Claude ne sont
pas utilisées (règles) ; l'avis ne voit que des images fixes ; une retouche faite pendant un travail de Claude peut être écrasée
à la fin du travail (piège connu de toutes les tâches du moteur).

**Après l'intégration (2 octobre 2026, Claude Code)** : quand la pause de 10 minutes après le refus « espace de travail manquant »
est finie, `statut()` laissait `raison` ET `avertissement` vides, et le bandeau rouge de ⚙️ s'affichait vide. Maintenant `avertissement` =
`ESPACE_MANQUANT` ; l'interface affiche `raison || avertissement`, et la boîte 💬 indique « ⚠ Claude bloqué (espace de travail manquant) :
l'IA locale répondra » au lieu de « Claude prêt ». Le prochain appel réessaie quand même (un refus 400 n'est pas facturé). Vérifié sur la
vraie page : build, tsc, test_noyau 139/139, test-ui 17/17.
