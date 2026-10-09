---
name: declinaison
description: Créer une version 15, 30 ou 60 secondes, rapide ou émotion, à partir d’un montage prêt dans l’Éditeur Sami.
argument-hint: <vidéo> [15|30|60] [rapide|emotion]
disable-model-invocation: true
---

# Déclinaison d’une vidéo

L’utilisateur veut une déclinaison : $ARGUMENTS

1. Identifie une seule vidéo prête avec `etat`.
2. Confirme la durée cible (15, 30 ou 60 secondes) et/ou l’intention (`rapide` ou `emotion`) à partir de sa demande ; s’il n’en donne aucune, demande laquelle.
3. Appelle `declinaison` une seule fois.
4. Suis la tâche avec `suivre_export` et rapporte le résultat. Aucune déclinaison ne doit être créée sans demande explicite.
