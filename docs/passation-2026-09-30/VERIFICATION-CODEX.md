# Reprise des six chantiers — 30 septembre 2026

Le serveur principal n'a pas été lancé. Aucun vrai reel n'a été réécrit, aucun montage long n'a été lancé.
Les exports de contrôle portent sur une copie d'une seconde de video1. Les ressources originales ont seulement été lues.
Le fichier `cles-api.env` n'a jamais été ouvert. Aucun téléchargement ni installation de dépendance.

## Résultats

1. **Déclinaisons** : tests 60/30/15 s, rapide et émotion, sans IA puis avec Qwen local : réussis.
   Les tests contrôlent mots d'ancrage, limites, accroche, dernière phrase de CTA, bruitages et zooms.
   L'interface affiche désormais `elements_resume`. Correction du resserrage en mode émotion.
   Deux créations successives portent des identifiants différents, sans écraser une version précédente.
2. **Mots en couleur** : sélection plus stricte, suppression des expressions interrogatives trop longues,
   réduction des mots faibles et des articles, interdiction de deux groupes entièrement colorés consécutifs,
   y compris à la frontière de deux plans. Sur video1/v1 actuel (5 mots par groupe) : 41 mots, 31/63 groupes,
   en règles seules et lors de l'essai IA (la passation mesurait 56 mots et 43/63 groupes).
   Tests vide, mot unique, anglais, mots masqués, propositions IA invalides et styles 1/2/3/5/8 mots : réussis.
   Les choix restent éditoriaux et modifiables ; ce n'est pas une garantie de qualité sur tous les textes.
3. **Révision / styles / chartes** : 14 tests isolés réussis ; aller-retour reel → style → reel sans écart.
   Dans le navigateur : export 9:16 puis 16:9, chacun de 1 s, terminé (14 s puis 6 s de traitement).
   Enregistrement d'un style personnel, apparition dans « Autre style », suppression avec confirmation et
   présence dans la corbeille vérifiés. Création/suppression d'une charte de test vérifiées par l'API.
   Styles fournis protégés ; demandes sans origine ou avec localhost refusées (403), origine exacte acceptée.
   Compatibilité avec `item.export` et reprise d'états interrompus vérifiées dans le test isolé de l'état serveur.
   Le serveur et `export.py` refusent maintenant d'annoncer un succès sans fichier vidéo non vide.
4. **PDF** : branchés dans le lecteur de scripts, détection automatique, dépôt navigateur et plugin.
   Conversion des scénarios par les retraits : noms des personnages et répliques, sans action/didascalies.
   Les 13 blocs de Bingo sont identiques au TXT de référence, apostrophes comprises.
   Lettre et licence lisibles sans plantage ; sortie DOCX identique à `avant-docx.json`.
   Priorité DOCX puis TXT puis PDF ; recherche d'un script nommé dans les sous-dossiers (Paperwork).
   Limite : PDF avec texte ; pas d'OCR installé. Les mises en page de scénarios inhabituelles restent à éprouver.
5. **Musique de référence** : mesure du fond dans les trames peu dominées par la voix, spectres normalisés
   calculés de la même manière pour la bibliothèque, périodicité multibande, classement et confiance.
   Banc conservé de **141 cas** :

   | Mesure | Avant | Après |
   |---|---:|---:|
   | Musique présente détectée | 132/132 | 119/132 |
   | Voix seule correctement reconnue | 0/9 | 9/9 |
   | Ambiance top-1 | 33 % | 36 % |
   | Ambiance top-3 | 57 % | 65 % |
   | Top-3 sous la voix | 50 % | 58 % |
   | Top-3 musique seule | 88 % | 96 % |
   | Tempo à ±4 %, octave admise | 56 % | 68 % |

   C'est un compromis plus prudent : 13 fonds discrets ne sont pas détectés. La confiance est un indice
   heuristique (faible/moyenne/bonne), pas une probabilité. Résultats sur un banc de mélanges des 12 musiques
   locales, pas une validation sur toutes les musiques externes. Mesures détaillées :
   `runtime/cache/tmp/musique-eval/verification-avant.json` et `verification-apres.json`.
6. **Plugin Claude** : réponse multi-formats corrigée (une seule requête, pas de doublon), état de chaque
   format affiché, PDF acceptés, modes d'emploi actualisés. Catalogue enregistré et activation déclarée
   dans `.claude/settings.json`, selon la documentation officielle des paramètres Claude Code.
   Protocole réel : initialize, 12 outils, 3 lectures, 7 cas invalides, deux formats et refus du doublon : réussis.
   `etat`, `styles`, `erreurs` également testés contre la copie réelle de l'éditeur.
   **À confirmer dans Claude** : chargement du plugin en ouvrant ce projet et en acceptant la confiance du dossier.
   La commande `claude` n'est pas disponible dans ce terminal : pas de `claude plugin validate` exécuté,
   pas d'installation ajoutée. L'apparition exacte dans l'interface Claude n'a pas été observée.

## Vérification et reprise

- `tests/verification.py` : 8 tests de régression réussis.
- `node app/build.mjs`, `node --check app/server.mjs`, syntaxe du serveur MCP : réussis.
- Vérification TypeScript : **les quatre erreurs antérieures restent présentes**, aucune nouvelle :
  types `react-dom/client` absents et trois associations `premountFor` / `layout="none"` dans Reel.tsx.
- Serveur navigateur de test sur 18790 arrêté après ses deux exports ; serveur principal 8790 non lancé.
- Copie de test conservée : `runtime/cache/tmp/interface-verification-C4V89t/`.
  Les sous-dossiers assets, tools/ffmpeg, runtime/venv et remotion/node_modules sont des jonctions vers
  les ressources du projet : ne pas supprimer récursivement leur contenu lors d'un nettoyage.
- Capture : `tests/test-styles-ui/verification-navigateur.png`.
- Les nouveaux tests utilisent des dossiers uniques et conservent leurs résultats. Aucun ancien bac supprimé.
- La copie `avant/` n'a pas été modifiée. Le projet n'est pas un dépôt Git.

## Suite distincte

Restent le test complet du dépôt et montage automatique d'une vidéo, la réanalyse complète du style RyuCalls,
les autres dettes listées au §4 de PASSATION.md, puis les nouveaux styles cinétiques/faux écrans/galerie/Blender.
Le montage d'essai complet Bingo n'a pas été lancé.

Documentation consultée pour le plugin : https://code.claude.com/docs/en/settings-reference
