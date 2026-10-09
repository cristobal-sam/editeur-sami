---
name: controle
description: Contrôler un montage de l’Éditeur Sami : note qualité sur 10 et problèmes à corriger (contrôle qualité), détails, versions, retour de style, propositions IA, refaire un passage ou la chorégraphie, recherche dans les rushs, export Resolve/Premiere.
argument-hint: <vidéo> [action]
disable-model-invocation: true
---

# Contrôle d’un montage

L’utilisateur veut contrôler un montage : $ARGUMENTS

1. Appelle `etat` si l’identifiant exact de la vidéo n’est pas connu.
2. Commence par `controle` (mode `dernier`, lecture seule) : note sur 10, verdict, problèmes classés
   **bloquant / important / conseil**, chacun avec son moment et une suggestion. Puis `inspecter_montage` si
   l’utilisateur veut le détail du montage.
   - Le rapport date d’avant ses retouches ? `controle` mode `montage` (quelques secondes, sans rendu).
   - Pour la vidéo déjà exportée : `controle` mode `export` (≈ 1 minute, images, détourage, son), puis `suivre_export`.
3. Explique en français simple, du plus grave au moins grave, avec le moment (« à 0:28 ») et quoi faire. L’outil ne
   corrige rien : dans la Révision, un clic sur le moment d’un problème amène l’aperçu à l’image exacte (et encadre
   l’endroit). Un problème **bloquant** = ne pas livrer en l’état.
4. Selon la demande explicite :
   - refaire l’habillage d’un seul passage : `refaire_passage` (début, fin en secondes du montage ; rien d’autre ne bouge) ;
   - refaire les entrées / sorties des éléments : `choregraphie` (`tout` pour les retouches aussi ; jamais les mouvements verrouillés) ;
   - historique : `versions`, puis `restaurer_version` seulement après choix d’un fichier exact ;
   - dernier style : `retour_style` ;
   - mots, plans de coupe, graphismes, raccords ou angles : `proposer` (vision désactivée par défaut, rien appliqué par défaut) ;
   - sons, effets, vecteurs disponibles : `banque_catalogue` (lecture seule) ;
   - retrouver une prise : `rechercher_rushs` ;
   - Resolve/Premiere : `exporter_montage_pro`.
5. Une action longue renvoie une tâche : utilise `suivre_export`. `annuler_tache` seulement si l’utilisateur demande l’arrêt.
6. Après une correction, propose de relancer `controle` (mode `montage`) pour voir la nouvelle note. Ne lance jamais une
   analyse, un passage ou un export uniquement « pour voir ».
