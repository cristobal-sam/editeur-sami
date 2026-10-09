# Galerie de styles — livraison du 30 septembre 2026

## État réel

Les dix images et la planche sont créées. Les dix styles ont une première implémentation dans le moteur et la galerie. **La demande B n'est pas entièrement terminée** : les limites ci-dessous ne sont pas couvertes par les essais courts.

Les aperçus sont des captures du véritable moteur Remotion sur une même photo de démonstration, pas des promesses de rendu dessinées indépendamment. La personne fictive a été créée avec l'outil de génération d'images ; son fichier a été déplacé dans ce dossier. La génération des habillages, détourage, IA éditoriale et Blender est locale.

![Planche](planche.png)

## Styles : acquis et limites

| Style | Ce qui fonctionne | Ce qui reste à faire ou à fournir |
|---|---|---|
| Éditorial cinétique | Accumulation des mots, tailles mélangées, rouge, diagonale, grand mot derrière le détourage. | Placement réellement adaptatif autour du visage, composition verticale et reproduction plus fidèle de CopyFi ; contrôle sur plusieurs cadrages. |
| Hormozi | Gros sous-titres jaunes, zoom motivé par un mot fort, émoji lié à une durée et espacé des zooms. | Valider la pertinence des mots forts sur plusieurs vidéos ; pas de garantie sémantique générale. |
| Tech / application | Carte de notification déclenchée par la transcription, texte éditable, sélection Qwen locale et règles. | Plusieurs variantes de bulle/tableau de bord ; téléphone en main uniquement si présent dans la vraie prise. |
| Infographie | Chiffres et unités prononcés, apparition animée, courbe explicitement illustrative. | Bibliothèque d'icônes et graphiques fondés sur de vraies données ; pas de statistiques inventées. |
| Documentaire | Bandes cinéma, étalonnage chaud, titre discret, sous-titres sobres. | Évaluer le rythme sur une séquence plus longue ; les prises et coupes existantes restent conservées. |
| Collage | Détourage réel, contour blanc, papier, ruban, étoile et mot avec flèche ; retouche vérifiée dans le navigateur. | Affiner les contours dans les décors difficiles ; le masque peut garder une partie de la table ou du fauteuil. |
| Luxe / minimal | Image en retrait, espace noir, empattements et or discret. | Transitions lentes et rythme spécifique plus poussés ; validation sur plusieurs cadrages. |
| Rétro VHS | Grain, balayage, teinte chaude, PLAY et horodatage cassette. | Véritable police pixel pour les sous-titres ; actuellement seuls les éléments cassette sont à chasse fixe. |
| Comparatif | Deux panneaux, vraie prise dupliquée, contraste avant/après, quantités explicites sans inversion. | Choisir deux vraies prises différentes problème/solution ; ne fabrique pas d'expressions stressée/souriante. |
| Produit 3D | Carte RyuCalls animée et rendue par Blender puis intégrée ; import photo/GLB branché, position modifiable. | Fournir le vrai produit et vérifier son import ; seule la carte démo est testée de bout en bout. Une photo produit une carte en relief, pas un modèle reconstruit. |

Les réglages exposés restent modifiables (texte, couleur, position, taille, rotation, durée, visibilité). Certaines décorations fixes et la mise en page cinétique globale ne disposent pas encore de contrôles indépendants.

## Vérifications effectuées

- Dix MP4 de **5 secondes**, 360 × 640, une piste vidéo et une piste audio chacun, dans `tests/`. Exports lancés successivement, jamais en parallèle.
- Six tests Python galerie : ressources, conservation des prises/coupes/textes, comparaison 3 heures / 5 minutes, rejet d'une négation ordinaire, unités numériques, application sans reconstruire le montage.
- Six vérifications temporelles : suivi des mots après coupe, fin bornée, retrait d'une ancre coupée, non-chevauchement, désactivation, rejet du détourage d'une autre prise.
- Huit tests Python des chantiers précédents : réussis. Le test DOCX a été adapté à son nouvel emplacement dans les sous-dossiers des rushs.
- Quatorze tests styles/Révision déjà repassés pendant ce chantier.
- Appel Qwen local réel : indices retournés, filtrage vers un mot admissible, scène ancrée à « leads » ; pas seulement un test de repli sans IA.
- Construction de l'interface et contrôle TypeScript : réussis, sans erreur de typage.
- Navigateur sur une copie isolée : filtre Tech, application Tech, retour Hormozi, application Collage, texte modifié, persistance après rechargement, actualisation du détourage, aucune erreur console au dernier contrôle.
- Cache de détourage ancien invalide observé dans la copie : invalidation de version et régénération. Ajout d'images WebP avec alpha pour un rendu partagé lecteur/export ; couleurs normales revérifiées visuellement.

![Retouche vérifiée dans la copie](tests/interface-collage.png)

Le passage réel de cinq secondes ne contient pas une comparaison à deux quantités : le style Comparatif n'y invente donc pas de scène. Son écran partagé est vérifié sur la phrase commune de démonstration, qui contient bien les deux quantités.

**Non vérifié :** montage complet depuis un nouveau dépôt, export long, totalité des dix styles dans tous les formats, import d'un GLB utilisateur, détourage sur tous les types de prise. Le placement « jamais sur le visage » n'est pas garanti dans tous les formats. L'IA propose encore parfois des mots discutables : retouche disponible.

## Sobriété et conservation

- Plus de plans de coupe automatiques par défaut sans activation explicite ; les propositions restent accessibles.
- Graphismes générés automatiquement retirés du chemin sobre, propositions conservées à valider ; chiffres littéraux et unités contrôlés.
- Pas de flash ni de bruitages par défaut dans les dix styles ; zoom Hormozi espacé et lié aux mots.
- Les anciens plans de coupe et graphismes manuels restent dans le document, masqués par défaut dans le nouvel habillage et réactivables.
- Application d'un style sur un reel existant sans refaire ses prises ni ses coupes ; sauvegarde préalable et bouton de retour en Révision.
- Bandeaux tronqués désactivés sur le chemin automatique, titre « Script N » normalisé vers « Vidéo N ».

## Comment essayer

1. Ouvrir l'outil comme d'habitude, une seule instance.
2. En Révision, ouvrir une vidéo puis **Autre style** ; filtrer la catégorie et cliquer une carte.
3. **Revenir au style précédent** restaure la version sauvegardée avant l'application.
4. **Modifier → Style → Habillage du style** : régler les éléments ; ouvrir la ligne d'un élément pour modifier son texte et sa position.
5. Après changement de prise ou élargissement d'une coupe dans Collage/Éditorial : **Actualiser le détourage**.
6. Produit 3D : choisir une photo ou un GLB, puis **Créer l'animation 3D**. Sans fichier, ce bouton construit la carte de démonstration.
7. Tester quelques secondes avant un export long. Les essais prêts à regarder sont dans `docs/galerie-styles/tests/<id>.mp4`.

## Fichiers créés ou modifiés

### Ressources et documentation créées

- `docs/galerie-styles/source-entrepreneur.png`, `planche.png`, `RESULTATS.md`.
- `docs/galerie-styles/images/01-editorial-cinetique.png`, `02-hormozi.png`, `03-tech-application.png`, `04-infographie.png`, `05-documentaire.png`, `06-collage.png`, `07-luxe-minimal.png`, `08-retro-vhs.png`, `09-comparatif.png`, `10-produit-3d.png`.
- Copies des aperçus et vidéo fixe commune dans `assets/galerie-styles/`.
- Dix fichiers `styles/montage/` : `hormozi.json`, `documentaire.json`, `luxe-minimal.json`, `retro-vhs.json`, `comparatif.json`, `infographie.json`, `tech-application.json`, `collage.json`, `editorial-cinetique.json`, `produit-3d.json`.
- `docs/galerie-styles/prepare.py`, `render.mjs`, `serve-test.mjs`, `test-galerie.py`, `test-timeline.mjs`, `test-ia.py` ; données, journaux, captures et exports dans `tests/`.
- Caches générés dans `assets/detourage/`, `assets/produits/`, `runtime/cache/produits/` et `runtime/cache/tmp/`.

### Code créé

- `engine/editeur/galerie.py`, `detourage.py`, `produit.py`, `engine/blender_produit.py`.
- `remotion/src/design.tsx`, `remotion/galerie-entry.tsx`.
- `app/ui/design-panel.tsx`, `app/ui/react-dom-client.d.ts`.

### Code modifié

- `engine/editeur/reel.py`, `auto.py`, `graphismes.py`, `broll.py`, `__main__.py`.
- `remotion/src/Reel.tsx`, `timeline.ts`, `types.ts`.
- `app/server.mjs`, `app/ui/App.tsx`, `panels.tsx`, `panels2.tsx`, `revision.tsx`, `styles.css`, interface compilée `app/dist/app.js`.
- `docs/passation-2026-09-30/tests/verification.py`, `REPRISE.md` §17.

## Précautions de reprise

Le vrai serveur 8790 n'a pas été lancé. Aucun projet réel, rush ou livraison n'a été modifié pour ces essais ; `cles-api.env` n'a pas été lu. Le SHA256 du reel original contrôlé est `AE530041B52265962A0982F4B1901DD071077E968F87E3C9CD8A5E4423CA9751`.

La copie navigateur se trouve dans `runtime/cache/tmp/galerie-interface-pQfXEU`. Elle contient des **jonctions vers les ressources originales** : ne pas supprimer récursivement sans examiner ces jonctions. Les données d'essai sont conservées.

La copie de serveur sur le port 18790 (PID 41204) et son onglet de test ont été arrêtés à la fin de cette livraison.
