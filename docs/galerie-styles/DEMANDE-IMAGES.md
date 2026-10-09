# Demande : galerie de styles qui MARCHENT pour de vrai — Éditeur Sami

## But

Je construis un outil de montage vidéo automatique pour mes pubs courtes (Reels, TikTok, YouTube).
Je veux une **galerie de styles de montage**, comme la page « Explore templates » de Higgsfield :

1. je vois une **image d'aperçu** par style (je comprends le style sans lire de texte) ;
2. **je clique sur le style que je veux → ma vidéo est remontée dans ce style, pour de vrai**, dans l'outil,
   avec ma vraie personne et mes vraies prises. Pas seulement une image : un style qui fonctionne.

Deux parties : **A. les images d'aperçu**, **B. la construction des styles dans l'outil.**

## Où sont les choses (pour ne pas avoir à tout parcourir)

| Quoi | Où |
|---|---|
| Projet | `D:\Tools\editeur_sami` |
| À lire en premier | `CLAUDE.md`, `REPRISE.md` (§4 à §8, §11 pièges, §15), `docs\passation-2026-09-30\PASSATION.md` (§5 = ce plan) |
| Vidéo modèle du style « Éditorial cinétique » | `C:\Users\crist\Downloads\WhatsApp Video 2026-09-26 at 11.37.45 AM.mp4` |
| Planches d'images de cette vidéo | `runtime\cache\tmp\ref-whatsapp\planche1.png` et `planche2.png` |
| Styles actuels (1 fichier = 1 style) | `styles\montage\*.json` (ex. `reel-impact.json`) ; sous-titres : `styles\sous-titres.json` ; musiques : `styles\musiques.json` |
| Application d'un style à un reel | `engine\editeur\reel.py` → `apply_template()` ; liste : `list_templates()` |
| Type de vidéo → style par défaut | `styles\types.json` ; choix du type : `engine\editeur\auto.py` → `classify()` |
| Calcul du montage (seule source, aperçu = export) | `remotion\src\timeline.ts` (n'importer QUE des types) |
| Rendu image (sous-titres, zooms, effets, plans de coupe) | `remotion\src\Reel.tsx` |
| Graphismes animés existants (chiffre, cases, carte, mot géant, logo) | `remotion\src\graphics.tsx` ; propositions : `engine\editeur\graphismes.py` |
| Format du document « reel » | `remotion\src\types.ts` |
| Position du visage / de la personne qui parle | `engine\editeur\cadrage.py`, `engine\editeur\analyze.py` |
| Détourage de la personne (déjà installé) | `models\mediapipe\selfie_segmenter.tflite` |
| Titres 3D Blender (déjà utilisé) | `engine\editeur\intro.py`, `engine\blender_titre.py` |
| Export final | `remotion\render.mjs` |
| Écran Révision (liste des styles cliquables) | `app\ui\revision.tsx` ; serveur : `app\server.mjs` (`/api/styles`, `/api/revision/:id/style`) |
| Vidéo test déjà montée (exemple de ce qu'il ne faut PAS faire, voir « Sobriété ») | `livraisons\Lot 2026-09-30 10h51\Script 1 - 0 COMPLET - Hook original - FINAL.mp4` |
| Dossier des images d'aperçu | `docs\galerie-styles\images\` |

## Règles

- Ne jamais ouvrir `D:\Tools\editeur_sami\cles-api.env`. Ne rien écrire dans `D:\Y0U`. Rien sur `C:`.
- Aucun service en ligne, aucune API payante, aucun téléchargement ni installation sans ma permission.
- Ne pas modifier mes projets (`projects\*`), mes rushs (`media\`) ni mes livraisons : tester sur des **copies**.
- Tests courts (quelques secondes d'export). Un seul style à la fois. Ne jamais lancer un 2e serveur sur le vrai dossier.
- Charger l'environnement avant toute commande : `. .\runtime\env.ps1` ou `source runtime/env.sh`.
- Textes de l'interface en français. Aucune vraie marque : marque fictive **RyuCalls**.

## Sobriété (très important)

Le montage automatique actuel ajoute des effets **inutiles** (voir la vidéo test ci-dessus). Chaque style doit suivre
cette règle de monteur professionnel : **chaque effet a une raison** (un mot important, un changement d'idée, un
chiffre, l'appel à l'action). Pas d'effet « pour faire de l'effet », pas deux effets en même temps, pas d'effet sur
chaque coupe. Un style = une **identité** cohérente (typographie, couleurs, rythme, éléments graphiques), pas un
empilement d'effets.

Ce qui ne va pas dans la vidéo test (reel `projects\script1\reels\script.json`, 71 s) — à corriger dans le moteur :
- **Plans de coupe hors sujet** (7, en encadré) posés sur des mots faibles : horloge-spirale sur « temps »,
  **visage d'un inconnu sur « RyuCalls »**, nuque d'une personne sur « à temps plein », mains floues, courbe sur
  « ce qui est », homme au téléphone plein écran sur « transférez ». Un plan de coupe doit illustrer une idée,
  jamais montrer une autre personne comme si c'était la marque ; si aucun plan pertinent (confiance faible), ne rien mettre.
- **Trop de choses en même temps au début** : bandeau + mot géant « TEMPS » + plan de coupe horloge dans les 3 premières
  secondes, par-dessus l'accroche.
- **Graphismes mal placés ou faux** : liste « Pourquoi choisir RyuCalls » pendant qu'elle parle encore du problème ;
  compteur « 1 h → 3 h » avec l'étiquette « a déjà été » ; compteur « ×4 → ×5 » avec « moins cher qu'un » coupé.
- **Mots en couleur** : ~20 % des mots, presque chaque groupe de 3 mots, dont des petits mots (« VOUS », « UN »,
  « AVEC », « QUE », « ÇA », « SOIT », « NOS », « UNE », « ET »). La correction faite dans `reel.py` ne semble pas
  s'appliquer sur ce chemin (montage automatique avec l'IA) : à vérifier.
- **Bandeau** = simple copie de la première phrase, coupée par « … ».
- **Style incohérent** : le reel est en « Clip podcast » (pas de musique) pour une pub, alors que la Révision indique
  « reel-impact » ; titre « Script 1 » au lieu de « Vidéo 1 ».

---

## A. Images d'aperçu

1. **Une image par style** (liste plus bas), format **vertical 9:16**, comme une capture d'un Reel monté dans ce style.
   Même personne partout (entrepreneur ~30 ans, t-shirt noir, face caméra, bureau moderne), même message :
   « Répondez à vos leads en 5 minutes, pas en 3 heures ». Rendu professionnel, crédible comme une vraie pub.
2. **Une planche récapitulative** : grille propre, fond sombre, style galerie haut de gamme ; sous chaque image,
   le nom du style et une seule ligne de description.
3. Fichiers : `docs\galerie-styles\images\<fichier>` (noms dans le tableau) et `docs\galerie-styles\planche.png`.

## B. Construire les styles pour qu'ils marchent vraiment

Pour chaque style :

1. **Un fichier** `styles\montage\<id>.json` (même format que les styles actuels, + les nouveaux réglages nécessaires),
   avec son image d'aperçu (`docs\galerie-styles\images\...`, à copier dans `assets\` si l'interface doit l'afficher).
2. **Le rendu réel** dans `remotion\src\` (nouveaux composants si besoin : texte cinétique, faux écrans, écran partagé,
   VHS, collage…), calculé par `timeline.ts` pour que **l'aperçu et l'export soient identiques**.
3. **Les décisions automatiques** côté moteur (`engine\editeur\`) : quels mots mettre en gros, où placer le texte (autour
   du visage, jamais dessus), quand montrer un faux écran ou un chiffre — avec l'IA locale (Qwen) + des règles.
4. **La galerie dans l'écran Révision** (`app\ui\revision.tsx`) : cartes avec l'image d'aperçu, filtres (Pub, UGC,
   Tech, Cinéma…), **un clic = la vidéo est remontée dans ce style** (route existante `/api/revision/:id/style`),
   sans rien perdre (retour possible au style précédent).
5. **Tout reste modifiable** ensuite dans l'éditeur (« ✏️ Modifier ») : textes, positions, couleurs, éléments.
6. **Vérifier** : faire un export court (≈ 5 s) de ma vidéo test dans le style, comparer avec l'image d'aperçu,
   vérifier la sobriété, noter ce qui marche et ce qui ne marche pas.

**Ordre conseillé** (du plus simple au plus gros) : Hormozi, Documentaire, Luxe, Rétro VHS, Comparatif,
Infographie, Tech/application, Collage, Éditorial cinétique (le plus gros : moteur de texte autour et derrière la
personne), Produit 3D (Blender : demande une photo ou le modèle 3D du produit).

## Les styles

| # | Fichier d'aperçu | Style | À montrer / à construire |
|---|---|---|---|
| 1 | `01-editorial-cinetique.png` | Éditorial cinétique | Mots placés autour de la personne, tailles mélangées (petits mots de liaison, gros mots clés en gras, un mot en rouge), qui s'accumulent au fil de la phrase ; un mot géant *derrière* la personne (détourage) ; texte en diagonale ou vertical ; mots clés entre guillemets en rouge ; palette rouge / blanc / noir. Voir la vidéo modèle. |
| 2 | `02-hormozi.png` | Hormozi | Gros mots en majuscules au centre, un mot surligné en jaune, zoom serré sur le visage aux moments forts, un émoji de temps en temps. |
| 3 | `03-tech-application.png` | Tech / application | La personne tient un téléphone ; fausse notification « Nouveau lead reçu ✅ », bulle de message, petit tableau de bord qui apparaissent quand on en parle. |
| 4 | `04-infographie.png` | Infographie | Grand chiffre animé (« 5 min ») quand un chiffre est dit, graphique qui monte, icônes simples à côté de la personne ; couleurs propres, motion design. |
| 5 | `05-documentaire.png` | Documentaire / cinéma | Bandes noires en haut et en bas, étalonnage cinéma chaud et contrasté, petit titre discret en bas à gauche, rythme posé, peu d'effets. |
| 6 | `06-collage.png` | Collage / papier découpé | Personne détourée avec contour blanc (autocollant), fond de papier texturé, flèches, étoiles, ruban adhésif découpés. |
| 7 | `07-luxe-minimal.png` | Luxe / minimal | Beaucoup d'espace vide, typographie fine à empattements, or discret, lumière douce, fondus lents. |
| 8 | `08-retro-vhs.png` | Rétro VHS | Grain, lignes de balayage, couleurs délavées, date/heure de cassette dans le coin, texte pixelisé. |
| 9 | `09-comparatif.png` | Comparatif / écran partagé | Écran coupé en deux : « AVANT » (stressé, téléphone qui sonne, « 3 h d'attente ») / « APRÈS » (souriant, « Réponse en 5 min ✅ »), utilisé quand la vidéo compare un problème et sa solution. |
| 10 | `10-produit-3d.png` | Produit 3D (effet Blender) | Objet de marque fictive (carte ou téléphone) qui tourne en 3D sur fond noir, lumière de studio, reflet au sol ; rendu par Blender puis inséré dans le montage. |

## Présentation de la réponse

Propre et professionnelle : d'abord la planche récapitulative, puis, pour chaque style, l'image en grand, son nom,
**ce qui marche déjà dans l'outil** et **ce qui reste à faire**. Une ligne par point, pas de longs paragraphes.
À la fin : la liste des fichiers créés ou modifiés, et comment tester (quoi cliquer).
