---
name: style
description: Remonter une vidéo de la Révision dans un autre style de montage.
argument-hint: <vidéo> <style>
disable-model-invocation: true
---

L'utilisateur veut changer le style de montage d'une vidéo : $ARGUMENTS

1. Identifie la vidéo (identifiant de 12 caractères ou titre ; appelle `etat` si besoin) et le style voulu
   (appelle `styles` pour trouver l'identifiant exact, ou `galerie` s'il cherche par genre : pub, UGC, cinéma, tech… ;
   si le style demandé n'existe pas, propose les plus proches).
   S'il manque la vidéo ou le style, demande-le.
2. Appelle l'outil MCP `changer_style` pour cette seule vidéo.
3. Dis-lui de la regarder dans l'interface (outil `ouvrir`) et demande s'il veut ce style **pour toutes
   les prochaines vidéos de ce sujet** : seulement s'il dit oui, appelle `toujours_ce_style`.
