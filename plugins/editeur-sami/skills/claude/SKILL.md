---
name: claude
description: Claude (IA en ligne d’Anthropic, en option et payante) dans l’Éditeur Sami : combien ça coûte, crédit restant, modèle, relecture des images par Claude, demande « Dis à l’IA ce que tu veux » sur un montage.
argument-hint: "[couts | critique <vidéo> | <vidéo> : <demande>]"
disable-model-invocation: true
---

# Claude dans l’Éditeur Sami

L’utilisateur parle de Claude, de l’IA en ligne ou de ce qu’il veut changer avec l’IA : $ARGUMENTS

Claude est **en option et payant** : chaque appel prend quelques centimes du crédit Anthropic de l’utilisateur
(il teste avec un petit crédit). Sans Claude, tout marche en local (IA locale ou règles simples).

1. **Toujours commencer par `claude_couts`** (lecture seule, gratuit) : allumé ou non, clé présente ou non (jamais la
   clé elle-même), modèle, dépensé aujourd’hui / ce mois, crédit restant estimé, plafonds, coût estimé d’une relecture.
   Avec une vidéo : ce qu’elle a déjà coûté.
2. **« Fais-la relire par Claude »** → `claude_critique` seulement si l’utilisateur le demande clairement, une fois,
   après avoir annoncé le coût estimé. Claude relit les images d’une vidéo **exportée** (la dernière par défaut) : sans
   export, proposer d’abord `prendre`. Un avis déjà payé pour la même vidéo revient gratuitement. Rien n’est changé dans
   le montage : note, verdict et problèmes avec leur moment (« à 0:28 »), aussi visibles dans la carte Contrôle qualité
   de la Révision. Suivre avec `suivre_export`.
3. **« Dis à l’IA de … »** (enlever le bandeau, mettre un mot en couleur, couper une pause à 0:12…) → `consigne` avec
   les mots de l’utilisateur ; `t` = le moment s’il en parle ; `simuler: true` s’il veut d’abord voir ce qui serait fait ;
   `moteur: "local"` s’il ne veut rien dépenser. Si l’éditeur pose une **question**, la transmettre telle quelle et
   attendre la réponse. Pour annuler : `restaurer_version` avec le fichier « avant » donné dans le résultat.
4. Réglages (allumer / éteindre, modèle Sonnet 5.5 recommandé, Haiku 4.5 très économique, Opus 5.5 meilleure qualité,
   plafonds, nouveau crédit après une recharge, critique automatique après export) : dans l’interface, roue ⚙️ →
   « Claude (IA en ligne) ». Les recharges se font sur platform.claude.com (Billing).
5. Message « Crédit Anthropic épuisé » ou « espace de travail » : le dire simplement ; l’outil continue en local.

Règles : jamais d’appel à Claude « pour tester » ni en boucle ; jamais lire `cles-api.env` ; un appel payant à la
fois, seulement sur demande explicite.
