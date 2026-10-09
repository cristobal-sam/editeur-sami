---
name: editeur-sami
description: Mode d'emploi de l'Éditeur Sami, le monteur vidéo local et automatique de l'utilisateur (reels, pubs, témoignages, podcasts, immobilier). À utiliser dès que l'utilisateur parle de ses vidéos brutes à monter, de la liste Révision, d'un style de montage, d'un export (« je la prends »), d'un style copié d'une vidéo de référence, ou d'une erreur de l'éditeur.
---

# Éditeur Sami — mode d'emploi pour Claude

L'Éditeur Sami (dossier `D:\Tools\editeur_sami`) monte des vidéos **tout seul et en local** (seule option en
ligne : **Claude**, l'IA d'Anthropic, payante, voir plus bas) : on dépose des vidéos brutes, il détecte le sujet (pub, témoignage, conseil…), choisit le style
adapté, fait le montage complet (meilleures prises, sous-titres, zooms, musique, plans de coupe) et range
la vidéo dans la liste **Révision**. L'utilisateur regarde, puis : **Je la prends** (export MP4),
**Modifier** (éditeur complet dans l'interface) ou **Autre style**.

L'utilisateur est un entrepreneur (pas monteur) qui fait ~20 vidéos par jour. Parle-lui **en français
simple** (Québec), sans jargon technique.

## Le flux de tous les jours

1. **Déposer** → outil `monter` (vidéos ou dossiers ; script .docx/.txt/.pdf et charte client facultatifs).
2. **Montage automatique** : une vidéo à la fois, plusieurs minutes chacune → suivre avec `etat`.
3. **Révision** : l'utilisateur regarde dans l'interface (`ouvrir` → http://127.0.0.1:8790).
4. Selon sa décision : `prendre` (export) · `changer_style` · `refaire` · retouches fines dans l'interface
   (bouton « Modifier » : prises, coupes, texte, graphismes…).

## Quel outil pour quelle demande

| L'utilisateur dit… | Outil |
|---|---|
| « où en sont mes vidéos ? », « c'est prêt ? » | `etat` (d'abord, pour avoir les identifiants) |
| « monte ces vidéos », « voici le dossier de lundi » | `monter` |
| « quels styles j'ai ? », « quelles chartes clients ? » | `styles` |
| « montre-moi la galerie », « quels styles pour une pub / du UGC ? » | `galerie` (par catégorie, avec l'image d'aperçu ; lecture seule) |
| « mets-la dans le style X » | `changer_style` |
| « toujours ce style pour les pubs » | `toujours_ce_style` (sujet → style, pour les prochaines vidéos) |
| « recommence cette vidéo » (après une erreur, ou avec un style imposé) | `refaire` |
| « enlève-la de la liste » | `retirer` (aucun fichier supprimé) |
| « inspecte ce montage », « qu’y a-t-il dedans ? » | `inspecter_montage` |
| « reviens avant », « quelles versions ? » | `versions`, puis `restaurer_version` ou `retour_style` |
| « fais une version 30 s / rapide / émotion » | `declinaison`, puis `suivre_export` |
| « propose des graphismes / plans / mots » | `proposer` (rien appliqué par défaut, vision désactivée par défaut) |
| « retrouve ce passage dans les rushs » | `rechercher_rushs` |
| « supprime-la », « je n'en veux pas » | `mettre_corbeille` seulement sur demande explicite ; `retirer` s'il veut seulement la cacher |
| « montre/restaure la corbeille » | `corbeille`, puis `restaurer_corbeille` avec le dossier exact |
| « je la prends », « exporte-la en 9:16 et 16:9 » | `prendre`, puis `suivre_export` |
| « annule cet export / cette analyse » | `annuler_tache` |
| « prépare pour Resolve / Premiere » | `exporter_montage_pro`, puis `suivre_export` |
| « quels outils locaux sont prêts ? » | `outils_locaux` (lecture seule) |
| « crée un titre 3D » | `creer_titre_3d`, puis `suivre_export` |
| « anime mon produit en 3D » | `animer_produit_3d`, puis `suivre_export` |
| « refais le détourage » (Tech 3D cinématique, Éditorial, Collage) | `actualiser_detourage`, puis `suivre_export` |
| « elle est bien ? », « quelle note ? », « qu'est-ce qui cloche ? » | `controle` (mode `dernier`, lecture seule) ; `controle` mode `montage` pour relire le montage actuel (quelques secondes) |
| « contrôle la vidéo exportée » | `controle` mode `export` (vidéo livrée : images, détourage, son ; ≈ 1 min), puis `suivre_export` |
| « refais seulement de 12 à 18 s » | `refaire_passage` (début, fin en secondes du montage), puis `suivre_export` |
| « refais les animations / entrées des éléments » | `choregraphie` (`tout` = retouches comprises, jamais les verrouillés), puis `suivre_export` |
| « quels sons / effets / flèches j'ai ? » | `banque_catalogue` (banque locale, lecture seule) |
| « quelles icônes j'ai ? » (argent, poignée de main, téléphone…) | `banque_catalogue` type `icone` + `q` en français (1 857 icônes Lucide + icônes importées ; posées dans l'interface en trait, plein ou verre) |
| « compose une musique » | `generer_musique`, puis `suivre_export` |
| « ouvre Resolve » | `ouvrir_resolve` seulement après demande explicite |
| « fais un style comme cette vidéo » | `style_reference`, puis `suivre_export`, puis `changer_style` |
| « ouvre l'éditeur » | `ouvrir` |
| « ça ne marche pas », « pourquoi erreur ? » | `erreurs`, puis `etat` |
| « combien Claude m'a coûté ? », « il me reste combien ? », « Claude est allumé ? » | `claude_couts` (lecture seule, gratuit) |
| « fais-la relire par Claude » | `claude_critique` (PAYANT : seulement sur demande, coût annoncé), puis `suivre_export` |
| « dis à l'IA d'enlever le bandeau », « mets GRATUIT en jaune », « à 0:12 coupe la pause » | `consigne` (demande libre ; `simuler` pour voir avant ; `moteur` `local` = gratuit) |

Précisions :
- `monter` avec un **dossier** demande `dossier` : `une_video` = ce sont les prises d'**une** même vidéo
  (avec son script éventuel) ; `plusieurs_videos` = chaque vidéo est montée à part (chaque sous-dossier =
  les prises d'une vidéo ; un script seul à la racine = tout le dossier suit ce script). En cas de doute,
  regarde le contenu du dossier et **demande** à l'utilisateur. Un script du même nom qu'une vidéo
  (`pub1.mp4` + `pub1.docx`) est le sien. Les PDF avec du texte sont lus ; les scénarios sont convertis en répliques.
  Un PDF scanné sans texte nécessite une version .docx/.txt. À contenu équivalent, .docx puis .txt sont prioritaires.
- Une vidéo se désigne par son identifiant de 12 caractères (donné par `etat`) ou par son titre.
- Les formats d'export : `9:16` (vertical, défaut), `16:9`, `4:5`, `1:1`. Les exports passent un à la fois
  dans la file (≈ 2 à 3 min par format). `suivre_export` peut attendre la fin (`attendre` en secondes).
- Les outils démarrent l'éditeur tout seuls s'il n'est pas lancé.
- **Contrôle qualité** : chaque montage automatique reçoit une note sur 10 et une liste de problèmes (bloquant, important,
  conseil), chacun avec son moment et une suggestion ; chaque export est ensuite contrôlé tout seul (vidéo livrée).
  `controle` les lit. Explique les problèmes simplement, du plus grave au moins grave, avec le moment (« à 0:28 ») ;
  l'outil ne corrige rien : l'utilisateur clique le problème dans la Révision pour aller au bon moment, corrige, puis relance.
  Un problème **bloquant** = ne pas livrer en l'état (le dire clairement avant un `prendre`).

- **Claude (IA en ligne d'Anthropic, en option et PAYANTE)** : il rend meilleurs les idées du montage, les textes des
  cartes, la relecture des images et les demandes « Dis à l'IA ce que tu veux ». Chaque appel prend quelques centimes du
  crédit de l'utilisateur (petit crédit de test) ; des plafonds par vidéo, par jour et par mois le protègent, et tout
  marche en local sans Claude. `claude_couts` dit l'état et les dépenses (jamais la clé). Réglages : roue ⚙️ de
  l'interface → « Claude (IA en ligne) » (modèle Sonnet 5.5 recommandé, Haiku 4.5 très économique, Opus 5.5 meilleure
  qualité). « Crédit épuisé » : recharge sur platform.claude.com, puis « J'ai rechargé » dans les réglages.

## Règles strictes

- **Claude coûte de l'argent** : `claude_critique` et `consigne` seulement sur demande explicite de l'utilisateur, une
  fois, en annonçant le coût estimé (`claude_couts`) ; jamais « pour tester » ni en boucle.

- **Un seul reel à la fois** : lancer `monter`, `refaire`, `prendre`, `declinaison`, `proposer`, `exporter_montage_pro`, `creer_titre_3d`, `animer_produit_3d`, `actualiser_detourage`, `generer_musique`, `refaire_passage`, `choregraphie`, `controle` (modes `montage` / `export`) ou `style_reference` **seulement quand
  l'utilisateur le demande**, et pour ce qu'il a demandé. Jamais de long montage ni d'export « pour tester ».
- **Ne jamais lire, afficher ni ouvrir `cles-api.env`** (clés privées des banques de médias et de Claude).
- **Ne jamais lire, modifier ni exécuter quoi que ce soit dans `D:\Y0U`**. Blender doit être autonome dans `tools\blender\blender.exe`. Tout reste dans `D:\Tools\editeur_sami`.
- **Ne pas supprimer** sans demande explicite. `mettre_corbeille` est récupérable et garde les exports ; ne jamais vider ni effacer définitivement la corbeille.
- Ne pas modifier à la main `projects\_revision.json` ni les reels pendant que l'éditeur tourne : passer par les outils.
- Ne jamais lancer un second serveur (`node app\server.mjs`) si l'éditeur répond déjà : deux serveurs
  traiteraient la même boîte d'entrée.

## Où sont les choses

| Dossier | Contenu |
|---|---|
| `media\entree\<dépôt>\` | boîte d'entrée : une copie des vidéos déposées (un dossier par dépôt) |
| `livraisons\<dépôt>\` | vidéos finales : `<titre> - FINAL.mp4` (et `<titre> (16x9) - FINAL.mp4`…) |
| `corbeille\<date heure> <titre>\` | vidéos supprimées depuis la Révision (🗑️) : montage + vidéos brutes, et `corbeille.json` pour les remettre à la main |
| `projects\<projet>\reels\script.json` | le montage d'une vidéo (fait foi) ; `versions\` = versions gardées |
| `projects\_revision.json` | la liste Révision (tenue par le serveur) |
| `styles\montage\*.json` | styles de montage (`ref-*.json` = créés depuis une vidéo de référence) |
| `styles\types.json` | sujet détecté → style utilisé automatiquement |
| `styles\clients\<id>.json` | chartes clients (logo, couleurs) |
| `media\references\` | vidéos de référence copiées par `style_reference` |
| `media\broll\` | bibliothèque de plans de coupe (`media\broll\banques\` = téléchargés des banques libres) |
| `media\rushs\` | anciens rushs de test |
| `runtime\cache\erreurs.log`, `erreurs-serveur.log`, `serveur-mcp.log` | journaux (lus par `erreurs`) |

## En secours : la ligne de commande

Préférer les outils : la ligne de commande **ne met pas** la vidéo dans la liste Révision.
Toujours charger l'environnement d'abord, depuis `D:\Tools\editeur_sami` :

```powershell
. .\runtime\env.ps1 ; cd engine
python -m editeur styles                                   # liste des styles
python -m editeur auto "<vidéo ou dossier>" [--style id] [--client id] [--livraison "<dossier>"]
python -m editeur style-ref "<vidéo de référence>" [--nom "Nom du style"]
python -m editeur reel ..\projects\<projet> --style <id>    # changer le style d'un montage
python -m editeur derush "<dossier des rushs>" ["<script.docx>"] [--style id --video video1 --version v1]
python -m editeur banques statut                           # banques de médias libres (sans jamais montrer la clé)
```

En bash : `source runtime/env.sh && cd engine && python -m editeur …`.
Interface : double-clic sur `Editeur Sami.cmd` (ou `.\editeur.ps1`) : arrête l'ancien lanceur PUIS l'ancien serveur,
recompile l'interface et relance l'éditeur s'il s'arrête. Un seul serveur à la fois : un serveur lancé en double
s'arrête tout seul (port déjà pris, code 98) sans rien monter ni exporter, et son lanceur ne le relance pas.

## Dépannage

- **« L'éditeur n'est pas lancé »** : les outils le démarrent tout seuls ; sinon double-clic sur
  `Editeur Sami.cmd`. Détails du démarrage : `runtime\cache\serveur-mcp.log`.
- **Vidéo en erreur** : `erreurs` (le message dit quoi faire : fichier illisible, mémoire de la carte
  graphique pleine → fermer les logiciels lourds…), puis `refaire` si l'utilisateur le veut.
- **« Tâche inconnue » / export « interrompu »** : l'éditeur a redémarré ; relancer `prendre`.
- **« L'export s'est bloqué à X % »** : l'éditeur a arrêté tout seul un export qui n'avançait plus (4 min sans
  progrès). Proposer de relancer `prendre` ; si ça recommence, fermer les logiciels lourds (IA, Blender, jeux).
- **Phrases du script absentes** (alertes dans `etat`) : le script ne correspond pas aux prises, ou il
  manque une prise ; le dire simplement à l'utilisateur.
- **L'interface n'a pas les derniers changements** : relancer avec `Editeur Sami.cmd` (recompile tout).
- **« Le port 8790 est déjà pris par un autre éditeur »** (fenêtre du lanceur, ou `erreurs-serveur.log` : « démarrage
  refusé ») : un éditeur tourne déjà ; ce serveur en double s'est arrêté sans rien faire. Utiliser celui qui tourne, ou
  relancer avec `Editeur Sami.cmd` (il arrête d'abord l'ancien lanceur et l'ancien serveur).
- **Note du contrôle qualité ancienne** : elle date d'avant les retouches ; `controle` mode `montage` pour la refaire.
