# Résultat — cerveau créatif V2

## Ce qui change

Le projet n'a pas été recommencé. Une couche de direction créative est ajoutée entre la compréhension du sujet et
les moteurs existants. Elle lit d'abord tout le montage, puis produit un plan commun : accroche, tension, révélation,
preuve, démonstration et appel à l'action. Les styles, graphismes, bruitages et scènes existants exécutent ensuite
cette intention au lieu de prendre leurs décisions séparément.

Le plan reste déterministe et utilisable sans IA ni service en ligne. Chaque temps narratif conserve comme preuve la
phrase réellement dite. Les garde-fous interdisent les visuels sans rapport, les chiffres inventés, l'empilement de
messages et les effets automatiques sur l'accroche.

## Vidéo 1

Le plan V2 est attaché à `projects/script1/reels/script.json` : 7 temps narratifs, rythme nerveux, grammaire « studio
cinématique + interfaces motivées ». Les scènes du style sont reliées à un temps narratif et à une raison. Aucun
rush n'a été refait et aucun export complet n'a été lancé.

Dans l'éditeur, onglet **Ajouter**, une carte **Direction créative V2** présente le résumé et des boutons qui vont
directement à chaque moment : Accroche, Tension, Révélation et Passage à l'action.

Le storyboard exécutable est également intégré : type de plan, moteur, composition, ressource, justification, solution
de secours et état d'exécution. Sur Vidéo 1, les 7 plans sont prêts. Le moteur choisit volontairement la prise réelle
pour les moments humains, Remotion pour les interfaces et la preuve, et refuse Blender sans produit réel.

## Compatibilité et retour arrière

- Le moteur précédent reste en place ; le plan V2 est un champ supplémentaire du reel.
- Un plan marqué `locked` est préservé pour permettre une validation ou retouche humaine future.
- Un changement de style recalcule la grammaire visuelle à partir des mêmes phrases.
- Les scènes posées à la main et les bruitages manuels restent prioritaires.
- Copie de sécurité dans `docs/cerveau-creatif-v2-2026-09-30/avant/`.

## Fichiers

- `engine/editeur/creative.py` : analyse globale, arc narratif, direction, son et rattachement des scènes.
- `engine/editeur/auto.py` : exécution du plan avant l'habillage automatique.
- `engine/editeur/reel.py` : recalcul sûr lors d'un changement de style.
- `engine/editeur/galerie.py` : chaque scène reçoit sa fonction et sa raison créative.
- `remotion/src/types.ts` : document V2 typé, sans incidence sur les anciens reels.
- `app/ui/ajouter.tsx` : carte lisible et navigation vers les temps narratifs.
- `docs/cerveau-creatif-v2-2026-09-30/test-creative.py` : tests dédiés.

## Vérifications

- Test cerveau créatif : réussi.
- Vérification générale Python : 8/8.
- Galerie : 6/6.
- Calcul temporel : 6/6.
- Construction de l'interface : réussie.
- TypeScript : 0 erreur.
- Contrôle dans le vrai navigateur : carte V2 visible, 7 boutons aux bons temps.
- Storyboard visible et développé dans le vrai navigateur : 7 décisions de réalisation.
- Aperçu 14 s inspecté, puis aperçu correctif 5 s inspecté image par image.
- Défaut trouvé et corrigé : la preuve « ×5 MOINS CHER » est maintenant réellement visible dans le style immersif.
- Serveur unique 8790 resté au repos ; file vide avant l'application.
- Aucun export complet ni service en ligne ; seulement deux aperçus locaux temporaires.

## Limite honnête

C'est la fondation du directeur créatif, pas encore un « 10/10 automatique » garanti. Le storyboard fonctionne ; les
prochaines couches prioritaires sont la direction sonore structurée et le contrôleur qualité automatique. La
génération d'images et Blender ne seront utilisés que lorsqu'un storyboard futur les rend réellement nécessaires.
