# État à jour pour Fable — Éditeur Sami — 2026-09-30 (après-midi)

> Remplace la tâche B de `TACHE-FABLE.md` : le diagnostic a été fait ET corrigé entre-temps par 3 agents.
> Ta nouvelle mission est plus bas (§4). Réponds en français simple. Mêmes règles que `TACHE-FABLE.md` §2
> (ne jamais ouvrir `cles-api.env`, rien dans `D:\Y0U`, rien sur `C:`, aucune installation, ne pas toucher
> `projects\`, `media\`, `livraisons\`, ne jamais lancer un 2e serveur sur le vrai dossier).

## 1. Situation exacte

- Le vrai serveur de l'éditeur tourne sur **8790**, mais avec l'**ANCIEN** code serveur (lancé avant les corrections).
  L'interface compilée (`app/dist/app.js`) est déjà la nouvelle : tant que le serveur n'est pas relancé, le bouton
  🗑️ répond « Action inconnue ». Aucun export ni montage en cours.
- Un processus `node plugins/editeur-sami/mcp/serveur.mjs` tourne : c'est probablement **ton** plugin MCP chargé dans
  ta session (bon signe). Ne pas le tuer.
- Les 3 agents de correction ont **fini**. Les 3 relecteurs (vérification adverse) ont été **arrêtés en plein travail** :
  les corrections ne sont donc **pas encore relues**. Les relecteurs n'avaient pas fini d'appliquer de correctifs.
- Vérifié juste après l'arrêt : `node --check app/server.mjs` OK, `node --check plugins/editeur-sami/mcp/serveur.mjs` OK,
  `node app/build.mjs` OK, TypeScript **0 erreur**, `docs\passation-2026-09-30\tests\verification.py` (8) OK,
  `docs\galerie-styles\test-galerie.py` (6) OK, `docs\galerie-styles\test-timeline.mjs` (6) OK.
- Copie du code d'AVANT ces corrections : `docs\corrections-2026-09-30\avant\` (`engine-editeur\`, `app-ui\`,
  `app-server.mjs`, `remotion-src\`, `remotion-render.mjs`, `plugins\`). Faire `diff -ru` pour voir chaque changement.
- Rapports complets des 3 agents (causes, fichiers:lignes, mesures, demandes, étapes de test) :
  **`docs\corrections-2026-09-30\rapports-agents.json`** — à lire.

## 2. Ce qui a été corrigé (à relire)

Fichiers modifiés : `engine\editeur\` `reel.py`, `llm.py`, `galerie.py`, `auto.py`, `broll.py`, `graphismes.py`,
`derush.py` (titre), **nouveau `sobriete.py`** ; `remotion\src\design.tsx`, `remotion\render.mjs` ; `app\server.mjs`,
`app\ui\revision.tsx`, `app\ui\styles.css` ; `plugins\editeur-sami\mcp\serveur.mjs` + 3 `SKILL.md`.

| Défaut | Correction faite (selon les agents) |
|---|---|
| Mots en couleur trop nombreux (petits mots) | Sélection commune validée partout (`reel.auto_highlights` / rehighlight, champ `reel.hlAuto`) : script1 19 % → 9 % des mots, ~1 par idée, chiffres + unité d'abord |
| Nouveaux styles : mauvais mot (« LEAD », « ATTEND », « deux ») | Choix commun classé (chiffres+unités > bénéfice/douleur > marque) ; « trois heures » choisi ; pas de doublon géant + guillemets |
| Notification Tech (phrase coupée, « EXEMPLE D'INTERFACE ») | Titres courts reformulés (« Nouveau lead reçu », « Lead en attente depuis 3 h »), au-dessus de la tête, plus d'étiquette technique |
| Plans de coupe hors sujet | Plus aucun ajout automatique : ils deviennent des propositions (`reel.suggestions.broll`) |
| Trop d'éléments au début / chevauchements | `sobriete.relire(reel, template)` : 1 élément à la fois, rien sur l'accroche sauf le bandeau, écart minimal ; appelée à la fin de `auto._finish` |
| Graphismes faux (étiquettes, compteur 1 h→3 h) | Étiquettes vérifiées ou vides, props `from`/`count` ; liste des bénéfices seulement dans la partie solution |
| Bandeau = 1re phrase coupée | Vrai titre court validé, sinon pas de bandeau |
| Style « podcast-clip » ≠ Révision « reel-impact » | Cause : le style avait été changé ~10 fois (Autre style / éditeur) sans mise à jour du registre → la liste lit maintenant `reel.template` |
| Titre « Script 1 » | Titre = nom du dossier / titre du script (« Vidéo 1 ») |
| **Supprimer une vidéo** (demande de l'utilisateur) | 🗑️ sur chaque carte + dans le détail + « Choisir plusieurs » ; routes `POST /api/revision/:id/supprimer` et `POST /api/revision/supprimer {ids}` ; projet + dossier d'entrée DÉPLACÉS dans `corbeille\<date heure> <titre>\` avec `corbeille.json` ; exports gardés ; refusé pendant un montage/export |
| Export bloqué 1 h à 3 % | Cause exacte non reproduite. Garde-fou : arrêt après 4 min sans progrès avec message clair, annulation forcée en ≤ 20 s (`taskkill /T` sur l'arbre), moteur Remotion compilé rangé par version |
| Plugin | 17 routes vérifiées contre le nouveau serveur, outil `galerie` ajouté (version 1.1.0), pas d'outil de suppression |

## 3. Ce qui n'est PAS encore fait (demandes des agents, à faire après relecture)

1. **`remotion\src\Reel.tsx`** (préréglage de sous-titres `boite`, vers lignes 187 et 203) : la boîte de couleur suit
   CHAQUE mot prononcé (« OU », « QUI », « ÇA ») → ne la mettre que sur les mots `hl`. C'est le défaut le plus visible
   dans la vidéo de l'utilisateur (style Clip podcast).
2. **Brancher la relecture sur le changement de style** : `engine\editeur\reel.py` `apply_template`, juste après
   `galerie.apply(reel, t)` : appeler `sobriete.relire(reel, t)` (code exact dans `rapports-agents.json`, agent habillage,
   demande 1). Aujourd'hui elle ne tourne qu'au montage automatique.
3. `remotion\src\graphics.tsx` (Chiffre, lignes ~25-26) : respecter `props.from` et `props.count === false`.
4. `remotion\src\types.ts` : types des nouveaux champs (`suggestions.broll`, `Broll.auto`, `Graphic.auto/confiance/raison`,
   `sobriete`, `hlAuto`).
5. `app\ui\ajouter.tsx` : afficher `reel.suggestions.broll` avec leur « pourquoi », acceptables en un clic ;
   afficher `reel.sobriete.resume` ; `panels.tsx:199` garder `...sug` pour ne pas perdre `suggestions.broll`.
6. `server.mjs` : mettre à jour `item.style` aussi dans `/template` et `/restore` de l'éditeur.
7. `galerie.apply` : garder `design.title` (Documentaire affiche sinon le titre du reel) ; `reel.ensure` (reconstruction,
   ~ligne 731) : garder l'ancien titre.
8. Valeurs `budget` proposées par style (tableau dans le rapport habillage, demande 5) : **non écrites** dans
   `styles\montage\*.json` (à valider avec l'utilisateur).
9. Relancer le vrai serveur (Editeur Sami.cmd) quand rien ne tourne ; mettre `REPRISE.md` à jour (§4 corbeille, §6
   `sobriete.py`, §8 routes suppression, §11 pièges listés dans les rapports).
10. Bacs à sable à nettoyer plus tard — ATTENTION jonctions vers les vrais dossiers, retirer avec `rmdir` avant toute
    suppression : `runtime\cache\tmp\interface-fable-85584\` (jonctions `rendu\assets`, `rendu\models`,
    `rendu\tools\ffmpeg`, `rendu\remotion\node_modules`, `rendu\runtime\venv`, `rendu\media\entree\Lot T5\Lien`,
    `rendu\projects\lien-p`), `runtime\cache\tmp\galerie-interface-pQfXEU\`, `runtime\cache\tmp\interface-verification-C4V89t\`.
    Sans jonction : `runtime\cache\tmp\habillage-sobriete-7k2\`, `runtime\cache\tmp\mots-fix\`, `revue-mots-k7q2\`.

## 4. Ta mission (Fable)

1. **Tâche A de `TACHE-FABLE.md`** (plugin) si pas déjà faite : appeler seulement `etat`, `styles`, `erreurs`
   (+ `galerie` si présent). Attention : le serveur 8790 tourne encore l'ancien code, certaines routes nouvelles
   peuvent répondre « inconnue » — le signaler, ne pas relancer le serveur sans l'accord de l'utilisateur.
2. **Relire les corrections** (le travail des relecteurs arrêtés) : diff contre `docs\corrections-2026-09-30\avant\`,
   vérifier chaque ligne du tableau §2 (relancer au moins un test par défaut, sur des COPIES), chercher les vrais
   défauts (plantages sur cas limites, chemins avec accents/espaces comme « Vidéo 1 » ou « Lot 2026-09-30 10h45 »,
   suppression hors `projects\` / `media\entree\`, effacement définitif au lieu d'un déplacement, textes pas en
   français, sobriété encore violée). **Lecture seule** : proposer les correctifs, ne pas modifier le moteur,
   l'interface ni les styles (l'utilisateur décidera qui les applique).
3. Écrire `docs\taches-fable\RESULTAT-FABLE.md` : Tâche A ; tableau « défaut → vérifié oui/non → problème trouvé →
   correctif proposé (fichier:ligne) » ; avis sur les 9 points du §3 (ordre conseillé). Puis un résumé **court** en
   français simple dans la conversation.
