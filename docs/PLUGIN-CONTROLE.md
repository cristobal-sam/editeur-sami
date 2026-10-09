# Plugin de contrôle de l'Éditeur Sami

Date : 30 septembre 2026

## Décision d'architecture

Un seul plugin local, `editeur-sami`, contrôle l'outil. Plusieurs plugins
séparés se partageraient le même serveur, les mêmes vidéos et les mêmes tâches ;
ils augmenteraient donc le risque d'actions concurrentes sans offrir de
capacité supplémentaire. Les domaines sont séparés par des compétences dans le
plugin, pas par plusieurs processus.

## Ce que le plugin contrôle

| Domaine | Commandes principales |
| --- | --- |
| Diagnostic | `etat`, `erreurs`, `ouvrir` |
| Montage | `monter`, `inspecter_montage`, `refaire`, `retirer` |
| Révision | `prendre`, `retour_style` |
| Styles | `styles`, `galerie`, `changer_style`, `toujours_ce_style`, `style_reference` |
| Historique | `versions`, `restaurer_version` |
| Création | `declinaison`, `proposer`, `rechercher_rushs` |
| Export | `suivre_export`, `exporter_montage_pro` |
| Outils locaux | `outils_locaux`, `creer_titre_3d`, `animer_produit_3d`, `actualiser_detourage`, `generer_musique`, `ouvrir_resolve` |
| Tâches | `annuler_tache` |
| Récupération | `corbeille`, `mettre_corbeille`, `restaurer_corbeille` |

Le serveur MCP expose 31 commandes au total. Le plugin contient dix
compétences qui apprennent à l'assistant quand utiliser chaque commande et
quelles confirmations respecter.

## Protections conservées

- ne jamais lire `cles-api.env` ;
- ne rien lire ni modifier dans `D:\Y0U` ;
- ne jamais démarrer une seconde copie du serveur de l'outil ;
- ne lancer un montage, une déclinaison, une proposition, une recherche, un
  export ou une restauration que sur demande explicite ;
- ne jamais vider la corbeille ;
- valider les chemins locaux et masquer les secrets dans les diagnostics.

## Fonctions volontairement laissées dans l'interface

Les réglages image par image, le dessin des zones de flou, les recadrages
manuels et les ajustements fins de timeline restent dans l'interface visuelle.
Ils dépendent d'un jugement visuel précis et seraient moins sûrs sous forme de
commande textuelle générique. Le plugin peut inspecter le résultat et piloter
les opérations structurées autour de ces réglages.

## Fichiers du plugin

- `plugins/editeur-sami/plugin.json` : manifeste portable ;
- `plugins/editeur-sami/mcp.json` : serveur local ;
- `plugins/editeur-sami/mcp/serveur.mjs` : commandes et protections ;
- `plugins/editeur-sami/skills/` : consignes par tâche ;
- `plugins/editeur-sami/assets/logo.svg` : identité visuelle ;
- `.claude-plugin/marketplace.json` : marché local compatible avec les hôtes de plugins.

## Validation effectuée

- syntaxe du serveur vérifiée ;
- manifestes JSON vérifiés ;
- démarrage MCP et inventaire des 31 commandes vérifiés ;
- appels en lecture testés contre le serveur déjà actif ;
- refus des demandes invalides vérifié ;
- anciens tests du plugin repassés avec succès.

Aucun montage, export, changement de style, déplacement ou restauration de
vidéo n'a été déclenché pendant cette validation.

## Installation Codex

Le marché local `editeur-sami-local` a été enregistré dans Codex et le plugin
`editeur-sami` version 2.1.0 contient aussi les connexions Blender, ACE-Step,
MediaPipe et Resolve. Son manifeste installé doit être relu après chaque mise à jour
et correspond au paquet source. Une nouvelle conversation Codex est nécessaire
pour charger ses 25 commandes, car les outils d'une conversation déjà ouverte
ne sont pas remplacés en cours de route.
