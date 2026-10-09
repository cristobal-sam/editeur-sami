---
name: prendre
description: « Je la prends » — exporter la vidéo finale (MP4) d'une vidéo prête de l'Éditeur Sami.
argument-hint: <vidéo> [9:16 16:9 4:5 1:1]
disable-model-invocation: true
---

L'utilisateur prend cette vidéo : $ARGUMENTS

1. Identifie **une seule** vidéo (identifiant ou titre ; appelle `etat` si besoin) et les formats demandés
   (9:16 vertical, 16:9 horizontal, 4:5, 1:1 ; sans précision : le format du montage). Si plusieurs vidéos
   correspondent, demande laquelle.
2. Si `etat` montre un contrôle qualité avec un problème **bloquant**, dis-le d'abord simplement (appelle `controle`
   en mode `dernier` pour le détail) et demande s'il veut exporter quand même. Puis appelle l'outil MCP `prendre`
   pour cette vidéo et ces formats.
3. Dis que l'export passe dans la file (un à la fois, environ 2 à 3 minutes par format) et où sera le
   fichier (`livraisons\<dépôt>\`). Puis appelle `suivre_export` avec l'identifiant de la tâche et
   `attendre` : 240 pour annoncer la fin et le chemin du fichier (ou l'avancement si ce n'est pas fini).
4. Chaque vidéo exportée est ensuite contrôlée toute seule (≈ 1 minute, sans bloquer les autres exports) : sa note
   apparaît dans `etat` et `controle` (mode `dernier`).
