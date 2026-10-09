# Éditeur Sami — instructions pour l'assistant

**Avant toute chose, lire `REPRISE.md` en entier** (dans ce dossier). Il contient : le but du
projet, le rôle à tenir (monteur professionnel + consultant produit), les règles de travail,
l'architecture, le fonctionnement, les formats de données, l'état actuel, les pièges déjà résolus
et la liste de ce qu'il reste à faire.

Rappels essentiels (détaillés dans REPRISE.md) :
- Répondre en français (utilisateur au Québec).
- Ne JAMAIS modifier `D:\Y0U`. Tout reste dans `D:\Tools\editeur_sami` (rien sur C:).
- Aucune API payante ni service en ligne : tout est local, sauf Claude (API Anthropic) branché à la demande de l'utilisateur (clé à lui, plafonds bas, crédit de 2 $ : voir REPRISE.md §29) ; jamais d'appel réel en test.
- Un seul reel à la fois ; pas de long montage/export sans demande ; tests courts.
- Ne pas supprimer les fichiers de l'utilisateur sans accord.
- Charger l'environnement avant toute commande : `source runtime/env.sh` ou `. .\runtime\env.ps1`.
- Tenir REPRISE.md à jour à la fin de chaque grosse étape (état, reste à faire, pièges).
