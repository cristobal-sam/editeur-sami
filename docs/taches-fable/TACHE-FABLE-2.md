# Tâche 2 pour Fable — appliquer les correctifs et rendre l'outil prêt à tester

> Cette fois, tu **modifies le code** : tu appliques les correctifs de ton propre rapport
> (`docs\taches-fable\RESULTAT-FABLE.md`), puis tu relances l'outil pour que l'utilisateur puisse le tester.
> Réponds en français simple : l'utilisateur est un entrepreneur, pas un programmeur.

## 1. Règles (inchangées, à respecter absolument)

- **Ne jamais ouvrir, lire ni afficher** `D:\Tools\editeur_sami\cles-api.env`.
- Rien dans `D:\Y0U`, rien sur `C:` (fichiers temporaires dans `runtime\cache\tmp\<ton-dossier>`). Aucune installation,
  aucun téléchargement, aucun service en ligne.
- Ne pas modifier les données de l'utilisateur pendant les tests : `projects\*` (dont `projects\_revision.json`),
  `media\*`, `livraisons\*`. Pas de modification de `styles\montage\*.json` ni `styles\types.json` dans cette tâche.
  Tester sur des **copies** (le moteur accepte `EDITEUR_ROOT` et un dossier de projet quelconque).
- Le vrai serveur tourne sur 8790 avec l'ancien code : **ne le relance qu'à l'étape 5**, quand tout est fini et que
  rien ne tourne. Jamais de 2e serveur sur le vrai dossier ; pour les tests HTTP, une copie isolée sur un autre port
  (comme tu l'as fait dans `runtime\cache\tmp\interface-fable-85584\`). **Jonctions** dans ces bacs à sable :
  les retirer avec `rmdir` avant toute suppression récursive.
- Tests courts (exports de 2 à 5 s, un à la fois). Pas d'IA vision (port 8792). L'IA texte seulement pour quelques
  appels courts si nécessaire.
- Code : garder le style du code autour ; textes de l'interface en français ; `remotion\src\timeline.ts` n'importe que
  des types ; écrire les fichiers avec l'outil d'édition (pas de heredoc bash pour du code) ; attention aux fichiers CRLF.
- Copie du code AVANT cette tâche : `docs\corrections-2026-09-30\avant2\` (pour les diff et pour revenir en arrière).

## 2. Correctifs à appliquer, dans cet ordre

### Étape 1 — Rendu (petit, sans risque)
1. `remotion\src\Reel.tsx` (préréglage de sous-titres `boite`, vers les lignes 187 et 203) : la boîte de couleur ne
   va **que sur les mots en couleur** (`w.hl`), dès que le mot est dit ; les autres mots restent simples. Vérifier que
   les autres préréglages n'ont pas le même défaut.
2. `remotion\src\graphics.tsx` (Chiffre, ~l. 25-26) : respecter `props.from` (valeur de départ, 0 par défaut) et
   `props.count === false` (afficher la valeur directement).
3. `remotion\src\types.ts` : types des nouveaux champs (liste dans `docs\corrections-2026-09-30\rapports-agents.json`,
   agent habillage demande 3, agent mots demande 5 : `suggestions.broll`, `Broll.auto/reason/confidence`,
   `Graphic.auto/confiance/raison/sobriete`, `StyleScene.sobriete`, `ReelDoc.sobriete`, `ReelDoc.hlAuto`).
4. `remotion\render.mjs` (ton B3) : avant le rendu, vérifier que chaque média du montage existe ; sinon message en
   français (« Le fichier de la prise « X » est introuvable : clique « Refaire » dans la Révision. ») ; traduire les
   erreurs connues (délai du navigateur, 404 d'un fichier) en gardant le texte brut dans le journal.

### Étape 2 — Relecture du monteur (`engine\editeur\sobriete.py`, `broll.py`, `graphismes.py`)
5. A1 : le bandeau « Toute la vidéo » ne compte que pendant l'accroche.
6. A2 : repérage de l'appel à l'action : d'abord `reel['ctaBlock']` ; une phrase repérée par ses mots seulement si elle
   commence dans le dernier quart ; sinon aucun. **Une seule fonction partagée** utilisée par `sobriete.py`, `broll.py`
   (~l. 126) et `graphismes.py` (~l. 91, 124, 132).
7. A3 : un élément posé à la main n'est jamais « automatique » (emojis compris) : seule la création automatique pose la
   marque `auto`.
8. C : « chez vos concurrents » n'est pas le début de la solution (exclure déterminants et possessifs).

### Étape 3 — Moteur (`reel.py`, `galerie.py`, `auto.py`)
9. Brancher la relecture sur le changement de style : `reel.py` `apply_template`, juste après `galerie.apply(reel, t)`
   (code proposé dans `rapports-agents.json`, agent habillage demande 1, avec `try/except`, `tout=False`). Vérifier :
   Révision → Autre style, éditeur → Style, `ensure(old, template)`. Les éléments posés à la main restent ; rien sur
   l'accroche (cas de l'emoji 📞 à 1,5 s en Karaoké et de « 1 semaine » sur l'appel à l'action en Infographie).
10. B1 : `auto._finish` ne refait pas le montage des vidéos `immobilier` / `evenement` et garde leur bandeau-adresse,
    leur `kind` et le réglage « pas de voix ».
11. Bandeau (ton #7) : relu (ou retiré) même s'il est masqué par le style, pour qu'un changement de style ne montre
    jamais un bandeau non relu.
12. Point 7 : `galerie.apply` garde `design.title` (Documentaire) ; la reconstruction de `reel.ensure` (~l. 731)
    garde l'ancien titre.
13. « Relancer l'IA » ne doit pas effacer `suggestions.broll` (`reel.py` ~l. 844 et ~l. 910).
14. (Si simple) une seule définition de la durée de l'accroche pour `galerie.py` et `sobriete.py`.

### Étape 4 — Serveur et interface (`app\server.mjs`, `app\ui\revision.tsx`, `panels.tsx`, `ajouter.tsx`, `styles.css`)
15. B2 corbeille : un vrai bouton **« Restaurer »** et une petite liste « Corbeille » dans la Révision : remettre les
    dossiers à leur place d'origine (seulement si elle est libre et dans `projects\` ou `media\entree\`) et remettre la
    fiche du registre (gardée dans `corbeille.json`) **avant** que le scanneur ne voie la vidéo comme nouvelle — aucun
    nouveau montage ne doit démarrer. Route protégée par l'origine exacte. Si c'est trop risqué, au minimum corriger le
    texte pour qu'il dise la vérité. Jamais d'effacement définitif, pas de « vider la corbeille ».
16. `revision.tsx` ~l. 315 : texte de confirmation exact quand les vidéos brutes sont gardées pour une vidéo jumelle.
17. B4 : pour les étapes sans progression (« Montage de la voix », « Mixage final »), limite proportionnelle à la durée
    du montage (ex. 10 min + 1 min par minute de vidéo) ; garder la règle des 4 min pour les étapes qui progressent.
18. Après un arrêt forcé, supprimer seulement les fichiers temporaires de CET export (`…FINAL.mp4.image.mp4`,
    `.voix.wav`, `.mix.wav`, `.fx.raw`) dans le `finally` de `pump` (~l. 348) ; jamais un FINAL terminé.
19. « Annuler » pendant les 20 s après un blocage garde le message de blocage.
20. Point 6 : mettre à jour `item.style` des vidéos de la Révision dans `/template` et `/restore` de l'éditeur.
21. `panels.tsx` ~l. 199 : garder `suggestions.broll` lors d'une nouvelle passe de l'IA.
22. (Facultatif) `ajouter.tsx` : afficher `reel.suggestions.broll` avec leur « pourquoi », acceptables en un clic ;
    afficher discrètement `reel.sobriete.resume`.

**Ne pas faire** : les « budgets » par style (on attend des essais sur de vraies vidéos).

## 3. Vérifications obligatoires avant de relancer

Tout doit passer :
- `node app/build.mjs` ; `remotion\node_modules\.bin\tsc -p tsconfig.verif.json` = **0 erreur** ; `node --check app/server.mjs` ;
  `node --check plugins/editeur-sami/mcp/serveur.mjs`.
- Depuis `engine\` : `docs\passation-2026-09-30\tests\verification.py`, `docs\galerie-styles\test-galerie.py`,
  `docs\taches-fable\tests\revue_moteur.py` (**les 4 échecs A1, A2, A3, B1 doivent passer**),
  `runtime\cache\tmp\habillage-sobriete-7k2\test-sobriete.py` (le copier avec son fichier de données dans
  `docs\corrections-2026-09-30\tests\` et corriger ses chemins) ; `node docs\galerie-styles\test-timeline.mjs`.
- Tes tests HTTP sur copie isolée (suppression → corbeille → restauration sans nouveau montage ; refus hors dossiers
  permis ; garde-fou proportionnel ; nettoyage des fichiers temporaires ; message après blocage).
- Un export de 2 s en style « Clip podcast » d'une copie de `projects\script1\reels\script.json` : **regarde les images**
  (ffmpeg → PNG) pour confirmer que la boîte n'est que sur les mots en couleur.
- Changement de style sur des copies de `script1` et `video1video1` avec 4 styles (reel-karaoke, hormozi,
  editorial-cinetique, infographie) : rien sur l'accroche, un seul élément à la fois, éléments posés à la main gardés.

## 4. Étape 5 — Rendre l'outil prêt à tester

1. Vérifier que rien ne tourne (`/api/revision` → `busy:false`, `/api/queue` vide), puis **relancer le vrai serveur** :
   arrêter le processus qui écoute sur 8790, puis lancer `Editeur Sami.cmd` (ou `powershell -ExecutionPolicy Bypass
   -File editeur.ps1`). Vérifier que `/api/revision` répond et que la route de suppression existe.
2. Dans la Révision, cliquer **« Refaire »** (route `POST /api/revision/<id>/refaire`, avec l'en-tête
   `Origin: http://127.0.0.1:8790`) sur les 2 vidéos existantes (`a4296031c10d` et `0a92d5202af8`), pour qu'elles soient
   remontées avec le nouveau code. La file les fait **une à la fois**. **Aucun export.** Attendre qu'elles soient
   « prêtes » et vérifier sur le montage obtenu (JSON du reel) : ~1 mot en couleur par idée, rien sur l'accroche, aucun
   plan de coupe ajouté tout seul, titre « Vidéo 1 ».
3. Mettre `REPRISE.md` à jour (nouvelle section : corbeille + restauration, `sobriete.py`, routes de suppression /
   restauration, garde-fou des exports, pièges A1-A3 / B1-B4 et ce qui reste).

## 5. Ce que tu rends

- `docs\taches-fable\RESULTAT-FABLE-2.md` : pour chaque point 1 à 22 : fait / pas fait, fichier:ligne, preuve de test ;
  ce qui reste ; les fichiers modifiés.
- Dans la conversation, un message **court** pour l'utilisateur : ce qui est prêt, puis une **liste de test simple**
  (quoi cliquer et quoi regarder) : ouvrir http://127.0.0.1:8790, regarder les 2 vidéos refaites, essayer « Autre
  style » (3 styles), supprimer une vidéo puis la restaurer depuis la Corbeille, faire « Je la prends » sur une vidéo en
  9:16 (un export complet de ~1 min 10 prend quelques minutes).
