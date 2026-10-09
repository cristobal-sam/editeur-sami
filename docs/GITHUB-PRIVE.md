# Sauvegarde GitHub privée de l'Éditeur Sami

Ce dépôt contient le code source, l'interface, les styles, les tests écrits et les petites banques nécessaires au fonctionnement de l'Éditeur Sami.

## Ce qui reste volontairement sur le PC

Pour protéger les données et éviter un dépôt gigantesque, GitHub ne reçoit pas :

- `cles-api.env` ni aucun fichier de clé ou de jeton ;
- les rushs, projets, livraisons et vidéos mises à la corbeille ;
- les détourages et produits générés à partir des vidéos ;
- les modèles d'IA, Blender, FFmpeg et les autres outils locaux installés ;
- les environnements Python, dépendances JavaScript, caches et fichiers compilés ;
- les captures, exports vidéo et anciennes copies volumineuses utilisées comme preuves de test ;
- les réglages personnels de Claude sur cette machine.

Ces exclusions sont définies dans `.gitignore`. Elles ne suppriment rien du PC : elles empêchent seulement Git de copier ces éléments vers GitHub.

## Pour réinstaller sur un autre PC

1. Cloner le dépôt privé.
2. Lancer `installer.ps1` pour préparer les outils et dépendances locales.
3. Recréer `cles-api.env` localement, sans jamais le publier.
4. Remettre les rushs dans `media/` et les éventuels projets locaux dans `projects/`.
5. Lancer l'éditeur avec `Editeur Sami.cmd`.

Le détail fonctionnel et l'historique du projet se trouvent dans `README.md`, `REPRISE.md` et les notes du dossier `docs/`.
