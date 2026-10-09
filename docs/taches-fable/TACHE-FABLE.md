# Tâche pour Fable — Éditeur Sami (2026-09-30)

Lis ce fichier en entier, puis fais les deux tâches. Réponds en **français**, simplement : l'utilisateur est un
entrepreneur québécois, pas un monteur ni un programmeur.

## 1. Le projet en bref

`D:\Tools\editeur_sami` est un **monteur vidéo local et automatique** pour des pubs courtes (Reels/TikTok).
L'utilisateur dépose des vidéos brutes dans l'écran « Révision » (http://127.0.0.1:8790) ; l'outil les transcrit
(Whisper), les analyse (MediaPipe), choisit l'ordre des prises, détecte le sujet avec une IA locale (Qwen 9B via
llama.cpp), applique un style et monte tout seul. L'utilisateur prend la vidéo, la modifie ou change de style.

Documents de référence (lire seulement les parties utiles) :
- `CLAUDE.md` (règles), `REPRISE.md` (§4 dossiers, §5 fonctionnement, §6 modules, §11 pièges, §15 dernière session)
- `docs\passation-2026-09-30\PASSATION.md` (état de la veille) et `VERIFICATION-CODEX.md` (vérifications faites)

## 2. Règles à respecter absolument

- **Ne JAMAIS ouvrir, lire ni afficher** `D:\Tools\editeur_sami\cles-api.env` (vraie clé API).
- Ne rien modifier dans `D:\Y0U`. Rien écrire sur `C:`. Aucun téléchargement, aucune installation.
- **Mise à jour :** ChatGPT a FINI la galerie de 10 nouveaux styles (lire `docs\galerie-styles\RESULTATS.md` et
  `REPRISE.md` §17). Il a modifié `reel.py`, `auto.py`, `graphismes.py`, `broll.py`, `timeline.ts`, `Reel.tsx`,
  `server.mjs`… et ajouté une première « sobriété » (plus de plans de coupe ni de graphismes automatiques par
  défaut). **Ton diagnostic porte sur le code ACTUEL** : pour chaque défaut ci-dessous, dis d'abord s'il est déjà
  corrigé, en partie corrigé, ou toujours présent.
- Cette tâche reste en **lecture seule** pour `engine\`, `remotion\`, `app\`, `styles\` : tu ne modifies pas ces
  fichiers, tu proposes. Tu écris seulement dans `docs\taches-fable\` et, pour la tâche A, dans
  `plugins\editeur-sami\` et `.claude\settings.json` si une correction est vraiment nécessaire (le serveur a changé :
  vérifie que les routes utilisées par le plugin existent toujours dans `app\server.mjs`).
- Ne pas modifier les projets (`projects\*`), les rushs (`media\`), les livraisons (`livraisons\`).
- Ne lance aucun montage, aucun export, aucun « refaire ». **Ne démarre jamais un 2e serveur de l'éditeur**
  (il partagerait la vraie boîte d'entrée et lancerait de vrais montages). Le serveur tourne peut-être déjà sur le
  port 8790 : si oui, utilise-le ; sinon, dis-le et n'en démarre pas.
- Avant une commande Python : `source runtime/env.sh` (bash) ou `. .\runtime\env.ps1` (PowerShell).

## 3. Tâche A — Vérifier le plugin « Éditeur Sami » (connecteur MCP)

But : que l'utilisateur puisse piloter l'outil depuis Claude (« monte ce dossier », « donne-moi l'état »…).

Déjà fait (par d'autres) : `plugins\editeur-sami\` (`.claude-plugin\plugin.json`, `.mcp.json`, serveur MCP sans
dépendance `mcp\serveur.mjs`, compétences dans `skills\`), catalogue `.claude-plugin\marketplace.json`,
activation déclarée dans `.claude\settings.json`. Tests du protocole réussis. **Jamais vérifié dans Claude lui-même.**

À faire :
1. Regarder si les outils MCP `editeur` (etat, styles, erreurs…) sont disponibles dans ta session.
   - Si oui : appeler **seulement** `etat`, `styles` et `erreurs` (lecture seule) et montrer le résultat.
   - Si non : vérifier les fichiers du plugin avec la documentation officielle de Claude Code sur les plugins
     (https://code.claude.com/docs/en/plugins et plugins-reference), corriger ce qui est faux, et écrire à
     l'utilisateur les étapes exactes pour l'activer dans l'application Claude.
2. **Ne pas appeler** `monter`, `prendre`, `changer_style`, `refaire`, `retirer`, `style_reference` (ils lancent de vrais travaux).
3. Vérifier que le serveur MCP ne lit jamais `cles-api.env`.

## 4. Tâche B — Diagnostic (lecture seule) : pourquoi le montage automatique « en fait trop »

Vidéo test ratée : `livraisons\Lot 2026-09-30 10h51\Script 1 - 0 COMPLET - Hook original - FINAL.mp4` (71 s).
Son montage : `projects\script1\reels\script.json`. Registre de la Révision : `projects\_revision.json`.
Chaîne du montage automatique : `engine\editeur\auto.py` (`_finish`), `broll.py` (plans de coupe, `suggest`),
`graphismes.py` (graphismes), `reel.py` (`ensure`, mots en couleur `auto_highlights` / `_editorial`), `llm.py`
(`editorial`), styles `styles\montage\*.json`, `styles\types.json`, serveur `app\server.mjs` (route `/api/revision/:id/style`).

Défauts constatés — pour **chacun**, trouve la cause exacte dans le code (fichier + fonction + ligne) et propose une
correction précise (sans l'appliquer) :

1. **Plans de coupe hors sujet** : 7 plans en encadré sur des mots faibles (horloge sur « temps », visage d'un inconnu
   sur « RyuCalls », nuque sur « à temps plein », mains floues, courbe sur « ce qui est », homme au téléphone sur
   « transférez »). Pourquoi sont-ils ajoutés même quand la confiance est faible ? Quel seuil proposer ?
2. **Trop d'éléments au début** : bandeau + mot géant « TEMPS » + plan de coupe dans les 3 premières secondes.
   Aucune règle ne vérifie les chevauchements ?
3. **Graphismes faux** : liste « Pourquoi choisir RyuCalls » à 9,8 s (trop tôt, pendant le problème) ; compteur
   « 1 h → 3 h » avec l'étiquette « a déjà été » ; « ×4 → ×5 » avec « moins cher qu'un » coupé.
4. **Mots en couleur** : ~20 % des mots, dont des petits mots (« vous », « un », « avec », « que », « ça », « et »).
   Une correction existe dans `reel.py` : pourquoi ne s'applique-t-elle pas ici (chemin IA en mode automatique ?).
5. **Bandeau** = première phrase recopiée et coupée par « … ».
6. **Style incohérent** : le reel est en `podcast-clip` (sans musique) alors que la Révision indique `reel-impact`
   pour une pub ; titre « Script 1 » au lieu de « Vidéo 1 » (le script Word est
   `media\rushs\SAM SCRIPT ADS 2026-08-11.docx`).

7. **Nouveaux styles : mauvais choix de mots** (vu dans les exports de 5 s `docs\galerie-styles\tests\*.mp4`, phrase
   « un lead qui attend trois heures ») : l'Éditorial cinétique met « LEAD » en géant ET entre guillemets (doublon),
   Hormozi met « ATTEND » en jaune, le Collage met « deux » en autocollant, alors que le mot fort est « trois heures ».
   Trouve où ces mots sont choisis (`engine\editeur\galerie.py`, `reel.py`, `llm.py`…) et comment les faire
   choisir les chiffres / bénéfices / douleurs en priorité, une seule fois.
8. **Notification du style Tech** : elle recopie la phrase coupée (« qu'un lead qui attend trois »), affiche
   « EXEMPLE D'INTERFACE » et cache le corps de la personne. Proposer : un vrai texte court de notification
   (reformulé, ex. « Nouveau lead · réponse en 5 min »), sans mention technique, placé hors du visage et du corps.

Puis propose un plan global de **sobriété** (règle de monteur : chaque effet a une raison) :
seuil de confiance (en dessous : suggestion, pas ajout), budget d'effets par style (ex. un seul élément à la fois,
rien sur l'accroche sauf le bandeau), relecture finale qui retire chevauchements et éléments sans raison.

## 5. Ce que tu dois rendre

1. Un fichier `docs\taches-fable\RESULTAT-FABLE.md` avec :
   - **Tâche A** : ce qui marche, ce que tu as corrigé (fichiers), les étapes d'activation pour l'utilisateur.
   - **Tâche B** : un tableau « défaut → cause (fichier:ligne) → correction proposée → difficulté », puis le plan de sobriété.
2. Dans la conversation : un résumé **court** en français simple (5 à 10 lignes), sans jargon.
