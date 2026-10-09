# Résultat Fable 2 — reprise et vérification Codex, 30 septembre 2026

## État final

Les 22 points sont implémentés. Les changements des étapes 1, 2 et 4 ont été relus contre `docs/corrections-2026-09-30/avant2/`, puis testés de nouveau. L'étape 3 est terminée.

Le vrai serveur a été redémarré **après** les tests : ancien PID 43416, nouveau PID 28512, port 8790. Son lanceur `editeur.ps1` déjà actif a assuré la relance ; aucun second lanceur ni second serveur sur le vrai dossier n'a été démarré.

« Refaire » a été appelé successivement pour `a4296031c10d` (25 s), puis `0a92d5202af8` (20 s). Les deux vidéos sont **prêtes**, en Reel Impact, titre de livraison **Vidéo 1**. Aucun export des vrais projets. Contrôle final : `busy=false`, aucun export en cours, route de corbeille HTTP 200.

| Montage refait | Mots colorés | Expressions mises en avant / idées | Habillage visible | Plans de coupe |
|---|---:|---:|---|---:|
| script1 | 26/285 — 9,1 % | 18/19 | Un chiffre, hors accroche | 0 |
| video1video1 | 23/265 — 8,7 % | 16/18 | Une liste puis un chiffre, sans chevauchement | 0 |

Aucun petit mot coloré seul ; aucun habillage pendant l'accroche ; aucun bandeau tronqué. Les bandeaux des deux montages sont désactivés et vides après relecture.

## Points 1 à 22

Les références ci-dessous sont relatives à `D:\Tools\editeur_sami`.

| Point | État | Code principal | Preuve |
|---|---|---|---|
| 1. Boîte seulement sur les mots en couleur déjà dits | Fait | `remotion/src/Reel.tsx:191` | Export 2 s, six PNG regardés : « attend » simple, « trois » puis « heures » encadrés ; autres mots sans boîte. |
| 2. Compteur `from` et `count:false` | Fait | `remotion/src/graphics.tsx:27` | `tests/compteur.mjs` : 8 assertions sur le vrai composant TSX, dont départ positif/négatif, zéro par défaut et valeur fixe à quatre instants. |
| 3. Types des nouveaux champs | Fait | `remotion/src/types.ts:55`, `:111`, `:160` | TypeScript : zéro erreur. Ajout des marques `manual` / `edited` pour les scènes retouchées. |
| 4. Médias manquants et erreurs d'export | Fait | `remotion/render.mjs:230`, `:257` | 15 tests de `test-render-erreurs.mjs`, vrai export HTTP de 2 s terminé ; erreurs connues françaises, journal brut conservé. |
| 5. Bandeau toute la vidéo / accroche | Fait | `engine/editeur/sobriete.py:334` | Tests A1 et revue moteur : le bandeau ne bloque plus tous les éléments suivants. |
| 6. Appel à l'action partagé | Fait | `engine/editeur/sobriete.py:118` | Tests A2 : bloc explicite prioritaire, phrase au milieu exclue, repères également utilisés par broll/graphismes. |
| 7. Ajouts manuels conservés | Fait | `engine/editeur/sobriete.py:180`, `engine/editeur/galerie.py:395`, `app/ui/design-panel.tsx:12` | Tests A3, emoji manuel en Hormozi, graphique manuel dans les 8 changements CLI, scène retouchée conservée à travers trois styles. |
| 8. « Chez vos concurrents » | Fait | `engine/editeur/sobriete.py:34` | Test C : déterminants/possessifs exclus de la solution. |
| 9. Relecture au changement de style | Fait | `engine/editeur/reel.py:681` | 2 copies × 4 styles par vraie CLI ; rapport présent, accroche libre, absence de chevauchement ; test galerie du chemin `ensure(old, template)`. |
| 10. Immobilier / événement | Fait | `engine/editeur/auto.py:142`, `:202` | B1 et tests `_finish` : pas de reconstruction ; prises, adresse, kind, voix « aucun » et musique conservés. |
| 11. Bandeau masqué relu | Fait | `engine/editeur/auto.py:240` | Test avec bandeau désactivé : correcteur appelé et texte rejeté retiré. |
| 12. Titres conservés | Fait | `engine/editeur/galerie.py:402`, `engine/editeur/reel.py:939` | Titre utilisateur et `design.title` inchangés après les 8 changements ; titre conservé lors d'une reconstruction en mode suggestion. |
| 13. Suggestions de plans de coupe conservées | Fait | `engine/editeur/reel.py:850`, `:916` | Tests `refresh_ai` et `ensure` avec proposition existante. |
| 14. Durée d'accroche commune | Fait | `engine/editeur/galerie.py:36`, `engine/editeur/sobriete.py:89` | `HOOK_MAX` retiré ; calcul sur le montage réel ; égalité des repères dans les 8 essais CLI. |
| 15. Corbeille / restauration | Fait | `app/server.mjs:1070`, `:1125`, `:1410`, `app/ui/revision.tsx:203` | 74 contrôles : restauration sans nouveau montage, fiche/lot réinsérés, destination occupée refusée, chemins piégés et jonctions refusés, y compris jonction vers un autre dossier interne. |
| 16. Prises partagées / confirmation | Fait | `app/server.mjs:848`, `app/ui/revision.tsx:378` | Test de jumelle masquée : les prises restent et le partage est signalé. |
| 17. Garde-fou proportionnel | Fait | `app/server.mjs:269`, `:296` | Limites de test 8 s pour 1 min et 26 s pour 10 min ; arrêts observés ~14,6 et ~34,3 s, grâce incluse. Règle normale : 10 min + 1 min/minute ; rendu image 4 min + marge serveur. |
| 18. Nettoyage ciblé après échec | Fait | `app/server.mjs:314`, `:379` | Les 5 temporaires du faux export disparaissent ; FINAL préexistant intact ; pas de faux FINAL après échec. |
| 19. Annuler après blocage | Fait | `app/server.mjs:370` | Annulation pendant la grâce : statut failed et message de blocage conservés ; tests d'arrêt des processus enfants. |
| 20. Registre du style | Fait | `app/server.mjs:876`, `:1484`, `:1499` | `/restore` remet le style dans le registre ; branche `/template` relue, échec du faux moteur sans mise à jour. Changement moteur réussi vérifié séparément par CLI. |
| 21. Propositions conservées côté interface | Fait | `app/ui/panels.tsx:199` | Fusion relue ; TypeScript et construction réussis ; tests moteur de conservation associés. |
| 22. Propositions et résumé visibles | Fait | `app/ui/ajouter.tsx:243`, `:264`, `:342`, `app/ui/revision.tsx:526` | Liste, motif, insertion manuelle et retrait de la proposition relus ; construction et TypeScript réussis. À essayer visuellement dans l'outil. |

## Corrections supplémentaires trouvées pendant cette reprise

- Les anciens emojis masqués échappaient à la relecture automatique puis revenaient au passage en Karaoké/Hormozi. `sobriete.relire(tout=True)` les range désormais dans les propositions. Avec `tout=False`, un emoji manuel reste intact.
- Hormozi régénérait les emojis pendant un simple changement de style et effaçait les retouches. `galerie.apply` préserve les emojis existants ; la génération reste dans le montage automatique.
- Les scènes marquées manuelles/retouchées étaient régénérées avant même la relecture : elles sont maintenant préservées, et une retouche du panneau pose `edited:true`.
- La confirmation de restauration promettait « aucun nouveau montage » même si le montage avait été retiré à la main de la corbeille. Le texte prévient maintenant de cette exception ; le message final reprend la note réelle du serveur.
- Une jonction vers un dossier encore situé dans l'arbre autorisé passait le contrôle de destination. Les parents traversés sont maintenant vérifiés aussi.

## Tests et preuves

- Construction interface réussie ; `tsc -p tsconfig.verif.json` : zéro erreur ; vérifications syntaxiques serveur, plugin et rendu réussies.
- Python : `verification.py` 8/8 ; `test-galerie.py` 6/6 ; `test-sobriete.py` 18/18 ; `revue_moteur.py` « TOUT EST BON » ; `changement_style.py` 7/7 (dont les 8 cas CLI).
- JavaScript : temporels 6/6 ; erreurs de rendu 15/15 ; compteur 8/8.
- Copie HTTP : 43/43, export 2 s en 15 s. Copie blocage : 12/12. Copie corbeille : 74/74.
- Copies finales : `runtime/cache/tmp/fable2-http-pubm8p/`, `fable2-blocage-w1hjOh/`, `fable2-corbeille-LurPk3/`. Chaque dossier contient `resultat.txt` et `serveur.log`. Les serveurs de copie sont arrêtés, les faux moteurs terminés ; aucun processus Python/FFmpeg/Chrome de test ne restait au passage à l'étape 5.
- Export podcast : `runtime/cache/tmp/fable2-images-M4Ce4H/boite-2s.mp4`, durée mesurée **2,000 s**, images `image-01.png` à `image-06.png` toutes inspectées. Fixture : ancien reel copié, « trois heures » explicitement marqué pour isoler le test de boîte. Les anciens graphismes de cette fixture ne représentent pas les deux montages refaits.
- Le premier lancement du test d'image depuis le mauvais dossier a tenté la recherche automatique de Chrome ; l'accès réseau a échoué. Aucun téléchargement/install terminé. Test corrigé pour partir de `remotion/`, comme le vrai serveur, avec Chrome déjà présent.
- Les CRLF des cinq fichiers signalés dans la passation ont été vérifiés : zéro LF isolé.
- Contrôle final des deux reels réels : `etape5_verif.py` réussi. Le test compte les expressions contiguës, et non chaque mot de « En savoir plus » comme une idée ; la limite de 12 % reste calculée sur tous les mots.

## Fichiers modifiés et limites

Code de cette tâche, agents précédents inclus : `engine/editeur/{reel,galerie,auto,sobriete}.py`, `remotion/render.mjs`, `remotion/src/{Reel.tsx,graphics.tsx,types.ts}`, `app/server.mjs`, `app/ui/{revision.tsx,ajouter.tsx,panels.tsx,styles.css,design-panel.tsx}` et interface compilée `app/dist/app.js`.

Tests ajoutés/repris sous `docs/taches-fable/tests/` : `changement_style.py`, `isole.mjs`, `apercu-boite.mjs`, `compteur.mjs`, `test-corbeille.mjs`, `etape5.mjs`, `etape5_verif.py`. Les données réelles n'ont été changées qu'à l'étape 5 via les deux appels « Refaire » autorisés ; les versions d'avant montage sont conservées par le moteur. Aucun changement aux fichiers de styles demandés, aucun accès à `cles-api.env`, aucune IA vision lancée.

Restent : essai utilisateur des boutons dans le navigateur, appréciation du rythme et des placements sur les vidéos entières, puis un vrai export complet à sa demande. Les nouveaux budgets par style n'ont pas été ajoutés. Cette tâche ne termine pas les travaux de galerie restant décrits dans `docs/galerie-styles/RESULTATS.md`. Les anciennes scènes retouchées avant l'existence de `edited` ne peuvent pas être reconnues rétroactivement avec certitude.

**Ne pas supprimer récursivement les bacs à sable : ils contiennent des jonctions vers les ressources du vrai projet.**
