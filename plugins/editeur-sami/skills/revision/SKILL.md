---
name: revision
description: Voir où en sont les vidéos de l'Éditeur Sami (liste Révision et file d'exports).
argument-hint: "[tout | pret | erreur | pris]"
disable-model-invocation: true
---

Montre l'état de la liste Révision de l'Éditeur Sami. Filtre demandé (facultatif) : $ARGUMENTS

1. Appelle l'outil MCP `etat` (filtre `a_faire` par défaut ; `tout`, `pret`, `erreur` ou `pris` si l'utilisateur
   l'a demandé).
2. Résume en français simple, sans jargon : combien de vidéos sont prêtes à regarder, en montage, en file,
   en erreur ; pour chaque vidéo prête, son titre, son sujet, son style et sa **note du contrôle qualité** (sur 10,
   avec le nombre de problèmes bloquants) ; les alertes du script ; les exports en cours avec leur avancement et la
   note de la vidéo livrée quand son contrôle est fini. Pour le détail des problèmes : `controle` (lecture seule).
3. Pour une vidéo en erreur, appelle aussi `erreurs` et explique le problème simplement.
4. Propose la suite sans rien lancer toi-même : regarder dans l'interface (`ouvrir`), `/editeur-sami:prendre`,
   `/editeur-sami:style`, ou `inspecter_montage`. Une vidéo ratée peut être rangée avec `mettre_corbeille`, mais
   seulement après une demande explicite ; l'opération est récupérable avec `corbeille` puis `restaurer_corbeille`.
