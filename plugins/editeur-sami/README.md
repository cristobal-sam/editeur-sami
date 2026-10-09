# Éditeur Sami — plugin local

Ce plugin permet à Codex ou Claude de piloter l'Éditeur Sami local par des
commandes encadrées. Il réutilise l'unique serveur de l'outil sur le port 8790
et refuse d'en lancer une deuxième copie.

## Couverture

- état de l'outil et erreurs récentes ;
- lancement et suivi d'un montage ;
- inspection de la timeline et de ses médias ;
- Révision, styles, galerie et style de référence ;
- versions et restauration ;
- déclinaisons et propositions assistées ;
- recherche de rushs ;
- exports finaux et professionnels ;
- Blender local pour les titres et produits 3D ;
- ACE-Step pour la musique et RobustVideoMatting (RVM) pour le détourage ;
- contrôle qualité (note /10 et problèmes datés), refaire un passage, chorégraphie, banque locale ;
- ouverture explicite de DaVinci Resolve ;
- annulation d'une tâche ;
- corbeille récupérable et restauration.

Le plugin expose 35 outils MCP et dix compétences conversationnelles. Les
actions longues ou modificatrices ne sont exécutées qu'après une demande
explicite. La corbeille n'est jamais vidée par le plugin.

## Compatibilité

- Agent Plugins v1 : `plugin.json` et `mcp.json` ;
- Codex : `.codex-plugin/plugin.json` ;
- Claude : `.claude-plugin/plugin.json` et `.mcp.json`.

## Vérification sûre

Depuis la racine du projet :

```powershell
node --check plugins\editeur-sami\mcp\serveur.mjs
node docs\passation-2026-09-30\tests\plugin-mcp\test-plugin-v2.mjs
```

Ces contrôles ne lancent ni export ni montage réel.
