# Passation à ChatGPT — Tâche 2 de Fable (2026-09-30, ~14 h) — arrêtée en cours de route

> Lis d'abord `CLAUDE.md`, puis `docs\taches-fable\TACHE-FABLE-2.md` (la tâche, les 22 correctifs, les règles) et
> `docs\taches-fable\RESULTAT-FABLE.md` (le rapport de relecture qui a motivé ces correctifs). Ce fichier dit où
> le travail en est. Répondre en français simple à l'utilisateur (entrepreneur, pas programmeur).

## 1. Règles (rappel, à respecter absolument)

- Jamais ouvrir `cles-api.env`. Rien dans `D:\Y0U`, rien sur `C:` (temporaires dans `runtime\cache\tmp\<ton-dossier>`).
  Aucune installation, aucun téléchargement.
- Ne pas modifier `projects\*` (dont `_revision.json`), `media\*`, `livraisons\*`, `styles\montage\*.json`,
  `styles\types.json` pendant les tests : tout sur des **copies**.
- **Le vrai serveur tourne encore sur le port 8790 avec l'ANCIEN code** (PID 43416 au moment de l'arrêt). Ne le
  relancer qu'à l'étape 5, quand tout est vérifié et que rien ne tourne. Jamais un 2e serveur sur le vrai dossier :
  copie isolée sur un autre port (18793) dans `runtime\cache\tmp\interface-fable-85584\` (voir `setup-serveur.mjs`,
  `render-stub.mjs`, `test-http.mjs`, `test-blocage.mjs`). Jonctions dans ce bac à sable : `rmdir` avant toute
  suppression récursive.
- Tests courts (exports 2-5 s, un à la fois). Pas d'IA vision. IA texte seulement pour quelques appels courts.
- Fichiers en **CRLF** à garder en CRLF : `engine\editeur\broll.py`, `reel.py`, `auto.py`, `llm.py`, `app\ui\styles.css`
  (vérifier avec `file`). Écrire le code avec un outil d'édition, pas de heredoc bash. `remotion\src\timeline.ts`
  n'importe que des types.
- Copie du code d'AVANT la tâche 2 : `docs\corrections-2026-09-30\avant2\` (pour `diff -u` et pour revenir en arrière).
- Environnement : `source runtime/env.sh` (bash) ou `. .\runtime\env.ps1`, commandes Python depuis `engine\`.

## 2. Ce qui a été fait (par des agents, en parallèle, puis arrêt brutal à la demande de l'utilisateur)

Vérifié après l'arrêt : `node --check app/server.mjs` OK, `node --check remotion/render.mjs` OK, `sobriete.py` compile,
`tsc -p tsconfig.verif.json` **0 erreur**, CRLF intacts. Tests : `verification.py` 8/8, `test-galerie.py` 6/6,
`docs\corrections-2026-09-30\tests\test-sobriete.py` **18/18** (copié et enrichi), `revue_moteur.py` : **1 seul échec
restant** (B1 « bandeau-adresse immobilier », étape 3 non faite).

**Ces changements n'ont PAS été relus par un vérificateur indépendant** (la phase de vérification a été arrêtée avant de
commencer). Les agents ont testé eux-mêmes ; à contrôler.

### Étape 1 — Rendu : FAIT (agent « rendu »)
Fichiers : `remotion\src\Reel.tsx` (+13), `remotion\src\graphics.tsx` (+3), `remotion\src\types.ts` (+22),
`remotion\render.mjs` (+71).
1. Boîte du préréglage `boite` : seulement sur les mots `w.hl`, dès `t >= w.outStart`, petite animation d'entrée ;
   les autres mots restent simples. **À vérifier à l'image** (§3 de la tâche : export 2 s d'une copie de
   `projects\script1\reels\script.json`, frameRange [780, 839] = « trois heures », puis `ffmpeg -vf fps=3` → PNG et regarder).
2. `Chiffre` respecte `props.from` et `props.count === false`.
3. Types ajoutés : `BrollCandidate`, `BrollSuggestion`, `Suggestions.broll`, `Broll.auto/reason/confidence`,
   `Graphic.auto/confiance/raison/sobriete`, `StyleScene.sobriete`, `ReelDoc.sobriete`, `ReelDoc.hlAuto`.
4. `render.mjs` : `mediaManquant(reel)` vérifie proxys / rushs / voix / ambiance / musique / intro / plans de coupe avant le
   rendu → message français « Le fichier de la prise « X » est introuvable : clique « Refaire » dans la Révision. » ;
   erreurs Remotion connues traduites (délai du navigateur, 404) avec le texte brut écrit dans
   `runtime\cache\erreurs-serveur.log` ; la vidéo finale est écrite dans `<out>.final.mp4` puis renommée.
   Tests de l'agent : `docs\taches-fable\tests\test-render-erreurs.mjs`, `render-gel.mjs` (à relire ; images dans
   `runtime\cache\tmp\rendu-fable\` s'il y en a).

### Étape 2 — Relecture du monteur : FAIT (agent « sobriété »)
Fichier : `engine\editeur\sobriete.py` (+49 -24). `broll.py` et `graphismes.py` **non modifiés** (ils lisent déjà
`reperes()`, donc profitent de la correction).
5. A1 : le bandeau ne compte comme élément fixe que jusqu'à la fin de l'accroche (`fin = min(end, rep['accroche'])`).
6. A2 : `reperes()` : d'abord `reel['ctaBlock']`, sinon une phrase avec un mot d'action seulement si elle commence dans
   le dernier quart (`s[0] >= total * 0.75`), sinon aucun.
7. A3 : emojis jamais « automatiques » (`'auto': False`) ; scènes de style automatiques sauf `manual` / `edited`.
8. C : « chez vos/votre/les/… » exclus de la détection de la solution.
9. Nouvelle fonction publique `sobriete.accroche_fin(words, total, b=None)` (même valeur que `rep['accroche']`), prévue
   pour remplacer `HOOK_MAX` dans `galerie.py` (point 14, pas fait).
Tests : `docs\corrections-2026-09-30\tests\test-sobriete.py` (+ `script1-auto-origine.json`, `video1-auto-origine.json`),
18/18 OK.

### Étape 4 — Serveur et interface : FAIT selon l'agent, à relire (agent « serveur/interface »)
Fichiers : `app\server.mjs` (+202), `app\ui\revision.tsx` (+77), `app\ui\ajouter.tsx` (+60), `app\ui\panels.tsx` (+2),
`app\ui\styles.css` (+10).
15. Corbeille : `GET /api/revision/corbeille` (liste), `POST /api/revision/corbeille/restaurer {dossier}` (origine
    exacte, destination libre et strictement sous `projects\` ou `media\entree\`, jonctions refusées, retour en arrière
    si échec, fiche `registre` et lot remis dans le registre sans `await` avant `saveRevision()`, manifeste renommé
    `restaure.json`) ; `corbeille.json` contient maintenant aussi `lot` ; note `pour_la_remettre` corrigée. Interface :
    bouton « Corbeille (N) » sous la liste, « Restaurer » par entrée, message vert.
16. `revisionState()` renvoie `partage: {unit, project}` ; texte de confirmation exact dans `revision.tsx`.
17. Garde-fou proportionnel : `dureeMontage` calculée dans `exportReel`, limite = `BLOCAGE_AUTRE + BLOCAGE_PAR_MIN × minutes`
    pour les étapes sans progression ; 240 s + marge gardés pour « Rendu de l'image ».
18. `exportTemps(out)` : après un export non terminé, suppression des seuls `.image.mp4`, `.fx.raw`, `.voix.wav`,
    `.mix.wav`, `.final.mp4` (jamais `job.out`).
19. « Annuler » après un blocage garde le message et le statut `failed` (`annule = job.cancelled && !job.blocked`).
20. `syncItemStyle(project, rid, template)` appelé dans `/template` et `/restore` de l'éditeur.
21. `panels.tsx` : `suggestions.broll` gardé lors d'une nouvelle passe de l'IA.
22. `ajouter.tsx` : liste « Plans de coupe proposés » (avec le pourquoi, insertion en un clic) ; `reel.sobriete.resume` affiché.
Tests de l'agent sur la copie 18793 : `docs\taches-fable\tests\test-corbeille.mjs` → `resultat-test-corbeille.txt`
(« TOUS LES TESTS OK », dont restauration sans nouveau montage, garde-fou 10 min > 1 min, nettoyage). À relancer
soi-même après `node setup-serveur.mjs`.

### Étape 3 — Moteur : **PAS COMMENCÉE** (points 9 à 14)
Fichiers à modifier : `engine\editeur\reel.py` (CRLF), `galerie.py`, `auto.py` (CRLF). Rien n'y a été touché.
Détails dans `TACHE-FABLE-2.md` §2 étape 3 et `RESULTAT-FABLE.md` §3-B1. En résumé :
9. `reel.py` `apply_template` (juste après `galerie.apply(reel, t)`, ~l. 680) : appeler `sobriete.relire(reel, t)`
   dans un `try/except`, garder `retires/deplaces/corriges/gardes/resume` dans `reel['sobriete']` (tout=False).
10. B1 : `auto._finish` (~l. 197-205) ne refait pas le montage des vidéos `immobilier` / `evenement` (garde `kind`,
    bandeau-adresse, `audio.voice = 'aucun'`, musique calée) ; `_banner_ok()` renvoie True si `r.get('kind')` est
    immobilier/evenement ou si aucun mot n'est dit → c'est le dernier échec de `revue_moteur.py`.
11. Bandeau relu par `_banner_correct` même si le style ne l'affiche pas (`auto.py` ~l. 227).
12. `galerie.apply` garde `design.title` ; `reel.ensure` (~l. 932) garde l'ancien `title`.
13. `reel.py` ~l. 844 (`refresh_ai`) et ~l. 908-911 (mode suggestion) : garder la clé `broll` de `suggestions`.
14. `galerie._hook_end` → `sobriete.accroche_fin(...)` (fonction déjà disponible), supprimer `HOOK_MAX`.
Puis écrire `docs\taches-fable\tests\changement_style.py` (copies de `script1` et `video1video1`, 4 styles via
`python -m editeur reel <copie> --style <id>` : rien sur l'accroche, un seul élément à la fois, éléments posés à la
main gardés, `reel['sobriete']['resume']` présent).

## 3. Reste à faire, dans l'ordre

1. Étape 3 ci-dessus.
2. **Vérifications obligatoires** de `TACHE-FABLE-2.md` §3, toutes : build, tsc 0 erreur, `node --check` (server,
   plugin, render), tests Python (verification 8/8, test-galerie 6/6, `revue_moteur.py` 0 échec, test-sobriete 18/18,
   changement_style), `test-timeline.mjs`, tests HTTP sur la copie isolée (`setup-serveur.mjs` puis serveur de copie
   avec `EDITEUR_PORT=18793`, stub pour les blocages ; arrêter la copie à la fin), export 2 s « Clip podcast » et
   **regarder les images**, changement de style sur copies avec 4 styles. Relire aussi les diffs des étapes 1, 2, 4
   contre `avant2\` (personne ne l'a fait).
3. Étape 5 (`TACHE-FABLE-2.md` §4) : vérifier `/api/revision` → `busy:false` et `/api/queue` vide, relancer le vrai
   serveur (`Editeur Sami.cmd` arrête l'ancien, recompile l'interface, relance et ouvre le navigateur), puis « Refaire »
   sur les 2 vidéos `a4296031c10d` (video1video1) et `0a92d5202af8` (script1), une à la fois, **sans export**, puis
   contrôle des reels, puis `REPRISE.md`. Scripts prêts : `docs\taches-fable\tests\etape5.mjs`
   (`node docs/taches-fable/tests/etape5.mjs verifier` ; `... refaire a4296031c10d 0a92d5202af8`) et
   `etape5_verif.py` (depuis `engine\` : `python ..\docs\taches-fable\tests\etape5_verif.py script1 video1video1`).
4. Rendre `docs\taches-fable\RESULTAT-FABLE-2.md` (point par point 1-22 : fait / pas fait, fichier:ligne, preuve) et un
   court message à l'utilisateur avec la liste de test (ouvrir http://127.0.0.1:8790, regarder les 2 vidéos refaites,
   « Autre style » ×3, supprimer puis restaurer depuis la Corbeille, « Je la prends » en 9:16).

## 4. État de la machine au moment de l'arrêt

- Vrai serveur 8790 : ancien code, au repos (aucun montage, file vide). Aucune copie de serveur en écoute (18793/18794).
  Vérifier quand même `tasklist` (chrome, python, node orphelins) avant de commencer.
- Bacs à sable créés aujourd'hui (à garder tant qu'utiles) : `runtime\cache\tmp\interface-fable-85584\` (JONCTIONS :
  `rendu\assets`, `rendu\models`, `rendu\tools\ffmpeg`, `rendu\remotion\node_modules`, `rendu\runtime\venv`,
  `rendu\media\entree\Lot T5\Lien`, `rendu\projects\lien-p`), `runtime\cache\tmp\rendu-fable\`,
  `runtime\cache\tmp\sobriete-fable\`, `runtime\cache\tmp\revue-fable\` (sans jonction).
- Fichiers ajoutés par la tâche 2 : `docs\corrections-2026-09-30\tests\` (test-sobriete + 2 json),
  `docs\taches-fable\tests\` (`revue_moteur.py`, `test-corbeille.mjs`, `resultat-test-corbeille.txt`,
  `render-gel.mjs`, `test-render-erreurs.mjs`, `etape5.mjs`, `etape5_verif.py`).
- `REPRISE.md` n'est pas à jour pour la corbeille, `sobriete.py`, les routes de suppression/restauration et le
  garde-fou des exports (à faire à l'étape 5).
