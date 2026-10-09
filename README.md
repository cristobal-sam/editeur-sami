# Editeur Sami

> Nouvelle conversation ? Lire d'abord **REPRISE.md** (infrastructure, état, règles, reste à faire).

Monteur video local et automatique. Tout tourne sur ce poste (GPU RTX 5060 Ti) ; seule exception,
facultative : la recherche de plans de coupe dans des banques libres (Pixabay), qui n'envoie que des mots-cles. Les rushs ne sont jamais modifies ; chaque montage est un fichier
projet que l'on peut retoucher et reexporter a volonte.

## Utilisation

**Montage entierement automatique** (derushage + montage stylise + export) :
```powershell
.\derusher.ps1 -Rushs "media\rushs\tournage" -Script "media\rushs\tournage\script.docx" -Style reel-impact
.\derusher.ps1 -Styles          # liste des styles de montage
```
Avec `-Style`, un seul reel est monte : la premiere video, version script. Choisir avec `-Video video1 -Version v1`.
Sans `-Script` : montage a partir de la transcription seule. Script : Word (.docx) ou texte (.txt), pas de PDF.
Sans `-Style` : seulement le derushage et les montages bruts (sans sous-titres ni effets).
`-Langue en` (ou `auto`) pour des rushs dans une autre langue que le francais ; `-Format 16:9` (ou 4:5, 1:1) pour
partir d'un autre format que 9:16. Un nouveau derushage n'ecrase jamais un projet venu d'un autre script.

**Banques d'images et de videos libres (plans de coupe)** : colle ta cle gratuite dans `cles-api.env` (a la racine,
les explications sont dedans ; Pixabay actif, Pexels pret si une cle redevient disponible). La cle reste dans le moteur.
Sans cle, tout le reste marche ; les plans deposes dans `media\broll` (par ex. telecharges a la main sur pexels.com)
sont proposes automatiquement.

**Retouches dans l'editeur** : `.\editeur.ps1` puis http://127.0.0.1:8790
- **En haut** : format de l'image 9:16 / 16:9 / 4:5 / 1:1 (le cadre suit la personne qui parle).
- **Timeline** (en bas) : glisser un plan pour le deplacer, ses bords pour le couper ; poignees du son = J-cut / L-cut ;
  pistes plans de coupe et graphismes (glisser pour deplacer) ; 💡 conseils de rythme, ▲ faux raccords.
- **Plan** : prise (+ comparateur cote a cote), coupes a l'image pres, vitesse, plan muet, angle multicamera,
  J/L-cut, lumiere et couleur.
- **Texte** : couper des mots = couper la video ; couleur, masquer, corriger ; l'IA propose (pointille) ou applique.
- **Style** : style de montage, charte client (logo, couleurs, police, carte de fin), sous-titres, voix, musique
  (bibliotheque ou sur mesure), bruitages, bandeau (+ propositions de l'IA), titre 3D, image.
- **Ajouter** (plans de coupe) : « Trouver automatiquement » pour la phrase en cours (l'IA lit la phrase, cherche,
  compare, propose 3 plans), recherche externe (videos/photos, orientation, duree, qualite, apercu au survol),
  propositions sur toute la video (bibliotheque `media\broll` puis banque libre) et « Mettre les plans surs
  automatiquement ». Un plan d'une autre orientation que le montage est **encadre** (moitie droite, bord blanc).
  Seul le media retenu est telecharge (une fois) dans `media\broll\banques\` avec sa fiche de licence (.json).
- **Graphismes** : chiffre qui defile, cases cochees, carte animee, mot geant lumineux, logo ; l'IA propose des emplacements.
- **Rushs** : recherche en phrase naturelle, synchronisation multicamera, nouveau montage visuel (immobilier, evenement).
- **Conseils** : zones faibles du rythme (propositions en un clic), faux raccords (experimental).
- **Versions** : enregistrer, restaurer, comparer A/B, declinaisons 60/30/15 s et « rapide » / « emotion ».
- **Export** : cocher les formats → file d'exports (un a la fois, annulable, on continue a travailler) ;
  export pour DaVinci Resolve / Premiere (OTIO, XML, FCPXML, SRT ; plans de coupe en V2).
Apercu identique a l'export. `Ctrl+Z` / `Ctrl+Maj+Z`. Sauvegarde automatique.

**Montage visuel sans parole** (immobilier, evenement), en ligne de commande :
```powershell
. .\runtime\env.ps1; cd engine
python -m editeur visuel "..\media\maison-rue-x" --type immobilier --titre "1234 rue X, Laval" --duree 30
```

## Resultats

`livraisons/<nom du script>/` :
- `Vidéo 1 - 0 COMPLET ... - FINAL.mp4` : montage stylise final (une version par hook)
- `Vidéo 1 - 0 COMPLET ....mp4` : montage brut ; `Vidéo 1 - 1 HOOK ...`, `- 2 ...` : parties
- `LISEZ-MOI.txt` : ce qu'est chaque video, sa duree, les prises d'origine

## Dossiers

| Dossier | Contenu |
|---|---|
| `app/` | Serveur local et interface de retouche (`ui/` source, `dist/` compile) |
| `engine/` | Moteur Python : derushage, transcription, analyse, IA, rendu, export |
| `remotion/` | Graphisme video (sous-titres, zooms, effets, musique) |
| `styles/` | **Styles modifiables** : `montage/*.json`, `sous-titres.json`, `musiques.json`, `clients/*.json` (chartes) |
| `assets/` | Ressources libres de droits : `fonts/`, `music/`, `sfx/`, `overlays/` ; logos clients, images des cartes |
| `media/rushs/` | Videos brutes a monter |
| `media/broll/` | Plans d'illustration proposes comme plans de coupe ; `banques/` = medias pris dans les banques libres (+ fiche .json) |
| `cles-api.env` | Cles des banques libres (Pixabay, Pexels) — ne jamais le partager |
| `projects/` | Un dossier par video : `project.json`, `rapport.md`, `reels/` (styles et videos de base) |
| `livraisons/` | Videos finales |
| `models/` | Modeles IA (telecharges une fois) |
| `tools/` | FFmpeg, llama.cpp (IA de texte), ACE-Step (musique) |
| `runtime/` | Python, environnements, caches (regenerables avec `installer.ps1`) |

Pour creer un nouveau style de montage : copier un fichier de `styles/montage/`, changer
`id` et `name`, ajuster les valeurs. Il apparait aussitot dans l'editeur et dans `-Styles`.

## Outils et modeles (tous locaux, usage commercial autorise)

| Outil | Role | Licence |
|---|---|---|
| FFmpeg 9 (NVENC) | coupes, son, export | LGPL/GPL |
| faster-whisper large-v3-turbo | transcription mot par mot | MIT |
| MediaPipe (visage, detourage, reperes) | orientation, cadrage, zooms | Apache 2.0 |
| CLIP ViT-B-32 (open_clip) | retrouver des plans par description | MIT |
| PySceneDetect, librosa | changements de plan, rythme musical | BSD / ISC |
| OpenTimelineIO | export vers DaVinci / Premiere | Apache 2.0 |
| Qwen3.5-9B via llama.cpp | mots cles, bandeau, emojis (et vision) | Apache 2.0 / MIT |
| ACE-Step 1.5 | musique originale sur mesure | MIT |
| Remotion 4 | graphisme video | gratuit jusqu'a 3 personnes |

Ressources : polices Google Fonts (OFL/Apache), bruitages Kenney (CC0) + bruitages
synthetises par l'editeur, 12 musiques originales generees par ACE-Step.

## Installation / reparation

`powershell -ExecutionPolicy Bypass -File installer.ps1` (ne retelecharge que ce qui manque).
Environnement dans un terminal : `. .\runtime\env.ps1` (PowerShell) ou `source runtime/env.sh`.
Tous les caches sont rediriges dans ce dossier. `runtime/cache/tmp` peut etre vide sans risque.
Apres une modification de `app/ui/` : `node app/build.mjs`.
