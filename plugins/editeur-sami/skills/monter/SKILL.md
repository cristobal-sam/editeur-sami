---
name: monter
description: Déposer des vidéos brutes (une vidéo ou un dossier) dans l'Éditeur Sami pour qu'il les monte tout seul.
argument-hint: <vidéo ou dossier> [script .docx/.txt/.pdf] [client]
disable-model-invocation: true
---

L'utilisateur veut faire monter par l'Éditeur Sami : $ARGUMENTS

1. Repère le ou les chemins (vidéos ou dossiers), le script éventuel (.docx, .txt ou .pdf) et la charte client
   éventuelle (vérifie son identifiant avec l'outil `styles` si besoin). Si rien n'est indiqué, demande quel
   dossier ou quelle vidéo déposer.
2. Pour un dossier, regarde ce qu'il contient et choisis `dossier` : `une_video` (les prises d'une même
   vidéo) ou `plusieurs_videos` (chaque vidéo montée à part). Si ce n'est pas évident, **demande-le**.
   Les PDF avec du texte sont lus. Pour un PDF scanné sans texte, demande une version .docx ou .txt.
3. Appelle l'outil MCP `monter` une seule fois avec ces choix.
4. Résume en français simple : nom du dépôt, nombre de vidéos à monter, identifiants. Explique que le
   montage se fait tout seul, une vidéo à la fois (plusieurs minutes chacune), et propose `/editeur-sami:revision`
   pour suivre.
