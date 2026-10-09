---
name: reference
description: Créer un style de montage à partir d'une vidéo déjà montée que l'utilisateur aime.
argument-hint: <vidéo de référence> [nom du style]
disable-model-invocation: true
---

L'utilisateur veut un style de montage comme cette vidéo : $ARGUMENTS

1. Repère le chemin de la vidéo de référence (fichier sur cet ordinateur) et le nom du style s'il en donne
   un (40 caractères au plus). S'il manque la vidéo, demande-la.
2. Appelle l'outil MCP `style_reference` une seule fois.
3. Explique que l'outil mesure le rythme, les sous-titres, les zooms, la musique et les couleurs (1 à
   3 minutes), puis appelle `suivre_export` avec l'identifiant de la tâche et `attendre` : 240.
4. Quand le style est créé, donne son nom et son identifiant, et propose de l'appliquer à une vidéo
   (`/editeur-sami:style`) ou d'en faire le style par défaut d'un sujet (`toujours_ce_style`) — sans le
   faire avant qu'il dise oui.
