---
name: outils-locaux
description: Contrôler les moteurs locaux reliés à l’Éditeur Sami : Blender pour les titres et produits 3D, ACE-Step pour la musique, RobustVideoMatting (RVM) pour le détourage, le contrôle qualité, et DaVinci Resolve pour la finition.
---

# Outils locaux de l’Éditeur Sami

Utilise d’abord `outils_locaux` pour vérifier la disponibilité sans lancer de
logiciel ni de rendu.

## Correspondance

- titre d’ouverture Blender : `creer_titre_3d` ;
- produit Blender après choix d’une photo ou d’un GLB dans le style Produit 3D : `animer_produit_3d` ;
- détourage des styles Tech 3D cinématique, Éditorial cinétique ou Collage (RVM pleine résolution, repli sur la prise
  d’origine là où le contour est douteux) : `actualiser_detourage` ;
- contrôle qualité d’une vidéo livrée (images, détourage, son ; carte graphique ≈ 1 minute) : `controle` mode `export` ;
- musique originale locale : `generer_musique` ;
- fichiers pour la finition : `exporter_montage_pro` ;
- ouverture visible de Resolve : `ouvrir_resolve`.

Toutes ces actions exigent une demande explicite. Elles peuvent utiliser le GPU
et prendre du temps. Ne lance jamais deux tâches lourdes ensemble.

Pour Blender, n’utilise que `tools/blender/blender.exe`. Ne lis, ne copie et
n’exécute rien dans `D:\Y0U`. Si Blender autonome est absent, explique qu’il
faut d’abord l’installer ou le copier dans le dossier prévu avec l’accord de
l’utilisateur.

`ouvrir_resolve` doit rester séparé de `exporter_montage_pro` : préparer des
fichiers n’autorise pas à ouvrir un logiciel visible.
