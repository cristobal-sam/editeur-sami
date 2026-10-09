# Claude dans l'éditeur, « Dis à l'IA » et les nouveaux sons de coupe — ce qui est fait (2 octobre 2026)

Pour Sami. Ce document dit, en mots simples, ce que l'éditeur fait de nouveau avec ta clé Claude, combien ça coûte, où
cliquer, et ce qui a été vérifié. Le détail technique est dans `REPRISE.md` §29.

## ⚠️ Une chose à faire avant que Claude puisse travailler

Ta clé Claude est bien là, mais Anthropic la refuse pour l'instant : elle n'est liée à **aucun « espace de travail »**
(workspace). Le seul vrai essai fait ce soir a reçu ce refus. **Il n'a rien coûté (0,00 $)** : tes 2,00 $ sont intacts.
Tant que ce n'est pas réglé, tout marche quand même, mais en local (l'IA de ton ordinateur), comme avant.

Deux façons de régler ça (au choix, une seule suffit) :

1. **La plus simple** : va sur **platform.claude.com** → **Settings** → **Workspaces**, copie l'identifiant qui commence
   par `wrkspc_`, puis dans l'éditeur : roue **⚙️** (en haut à droite) → **Claude (IA en ligne)** → **▸ Avancé** →
   **Espace de travail Anthropic** → colle-le → **Enregistrer**.
   (Tu peux aussi l'écrire dans `cles-api.env`, sur une ligne à part : `ANTHROPIC_WORKSPACE_ID=wrkspc_...` ; l'éditeur la
   lit maintenant.)
2. Ou crée sur platform.claude.com une **nouvelle clé à l'intérieur d'un espace de travail** (API keys), et remplace
   l'ancienne dans `cles-api.env`.

Ensuite, pour vérifier (moins d'un dixième de cent) : dans une fenêtre PowerShell, depuis `D:\Tools\editeur_sami\engine` :
`..\runtime\venv\Scripts\python.exe -m editeur claude test` → la réponse doit dire `"ok": true`.

## Est-ce obligatoire de prendre Opus ? Non.

L'éditeur utilise **Claude Sonnet 5.5 par défaut**. Il est très bon pour ce travail (choisir les mots, écrire des textes
courts, regarder des images) et coûte environ **deux fois moins cher qu'Opus**. Tu peux changer quand tu veux :
⚙️ → Claude → **Modèle**.

| Modèle | Pour qui | Prix typique par vidéo (idées + une demande) | Avis sur les images (16 images) |
|---|---|---|---|
| **Sonnet 5.5** (par défaut) | le bon équilibre | environ 0,07 $ | environ 0,05 $ |
| **Haiku 4.5** | le moins cher, un peu moins fin | environ 0,03 $ | environ 0,02 $ |
| **Opus 5.5** | le meilleur, le plus cher | environ 0,15 $ | environ 0,11 $ |

Ce sont des **estimations** : les vrais montants se verront aux premiers vrais appels (après l'espace de travail).
Dans ⚙️ → Claude → Avancé, tu peux aussi choisir un modèle différent pour chaque tâche (par exemple Haiku pour « Dis à
l'IA » et Sonnet pour les idées).

## Ce que Claude fait (là où l'IA locale était faible)

1. **Les idées du montage** (« cerveau ») : une seule fois par montage, Claude lit ce qui est dit et choisit les mots en
   couleur (environ un par idée), les parties de l'histoire (accroche, problème, solution, preuve, appel à l'action), le
   texte des cartes et des notifications, le bouton de la fin, le bandeau du début, un titre court, et corrige les fautes
   de transcription (« Pi » → « Puis », « transférez » → « transférer »…).
   **Tout est revérifié par l'outil** avant d'être utilisé : jamais un petit mot comme « vous » en couleur, jamais un
   chiffre qui n'est pas dit, jamais une correction qui change le sens (« deux » → « dix », « moins » → « plus », un nom
   de marque), rien par-dessus l'accroche sauf le bandeau. Ce qui ne passe pas est simplement retiré.
   Ça se fait tout seul à chaque nouveau montage, et sur un clic : Révision → **🧠 Refaire avec Claude** (le montage
   d'avant est gardé, bouton **Annuler**). Dans l'éditeur, onglet **Texte** → **↻ Relancer l'IA** : ce sont seulement des
   propositions ; les corrections de transcription s'affichent (« Pi » → « Puis ») avec **Accepter** / **Refuser**.
2. **L'avis sur la vidéo exportée** (« critique ») : sur un clic, Révision → **👁 Critique Claude**. Claude regarde des
   images de la vidéo livrée prises aux bons moments (début, après les coupes, quand une carte entre, le bouton de la fin)
   et te rend une note sur 10, ses problèmes avec le moment exact, les points forts et la chose à corriger en premier. Il
   s'ajoute à la carte « Contrôle qualité », à part de la note de l'outil. **Redemander le même avis est gratuit**
   (la réponse est gardée). L'avis automatique après chaque export est **éteint** au départ.
3. **« Dis à l'IA ce que tu veux »** : voir plus bas.

Ce qui reste local et gratuit : le choix des prises, le montage, le détourage, la musique, le contrôle qualité, les
sous-titres. Si Claude n'est pas disponible (éteint, pas de clé, plafond atteint, crédit épuisé, pas d'Internet, refus),
l'outil fait exactement comme avant, en local, et il te dit pourquoi.

## Tes 2 $ sont protégés

- **Plafonds** (⚙️ → Claude → Avancé) : 0,25 $ par vidéo, 0,75 $ par jour, 2,00 $ par mois. Avant chaque appel, l'outil
  calcule le pire coût possible et **refuse** s'il dépasserait un plafond ou ce qui reste de ton crédit.
- **Un seul appel par montage** : changer de style, rouvrir la vidéo, « Relancer l'IA », refaire le montage avec les mêmes
  mots = 0 $ (l'outil relit ce que Claude a déjà dit). Un double clic ne paie jamais deux fois.
- **Crédit épuisé** chez Anthropic : l'outil le dit clairement (point rouge sur la roue ⚙️ + bandeau), arrête d'appeler
  pendant 10 minutes et continue en local.
- **Ta clé n'est jamais affichée ni écrite nulle part** (seulement « Clé présente ✓ »).
- ⚠️ À savoir : avec Claude allumé, **chaque nouvelle vidéo montée automatiquement fait un appel** (environ 3 à 6 cents
  avec Sonnet). Avec le plafond de 0,75 $ par jour, ça fait environ 15 vidéos par jour avec Claude ; les suivantes sont
  montées en local. Monte le plafond, ou passe à Haiku, si tu veux plus.

**Où voir ce que tu as dépensé et ce qui reste** : ⚙️ → **Claude (IA en ligne)** : dépensé aujourd'hui et ce mois-ci,
« Crédit restant estimé », et **▸ Coûts Claude** (les 20 derniers appels). Chaque vidéo de la Révision affiche aussi ce
qu'elle a coûté (par exemple « 🧠 0,09 $ ») et qui a fait ses idées (« Idées : Claude Sonnet 5.5 (0,04 $) » ou
« Idées : IA locale — <raison> »). Après une recharge sur platform.claude.com : ⚙️ → Claude → **J'ai rechargé :
nouveau crédit** → tape le montant.

**Éteindre Claude** : ⚙️ → Claude → décoche **Activer Claude**. Tout continue en local, gratuitement. (En ligne de
commande : `python -m editeur claude reglages --json "{\"actif\": false}"` depuis `engine`.)

## « Dis à l'IA ce que tu veux » (la boîte 💬)

**Où** : dans la **Révision**, colonne de droite, bloc « Retouches par l'IA » (dès que la vidéo est montée) ; et dans
l'**éditeur** (« Modifier »), en haut du panneau de droite (bouton « ▴ Réduire » pour lui laisser moins de place).

**Comment** : tu écris ce que tu veux, avec tes mots, puis **Envoyer** (ou Ctrl+Entrée). La case « à partir d'ici »
veut dire « à l'endroit où est la lecture ». Exemples :
- « mets les sous-titres en jaune pis la musique un peu moins forte »
- « enlève la carte ici » · « change le texte du bouton pour Réserve ton appel »
- « coupe le bout où je bégaie à 0:31 » · « mets le style Hormozi » · « fais-en une version de 30 secondes »
- « des sons plus doux quand ça coupe » · « varie les sons »

**Ce que tu vois** : ce qui a été changé, ce qui n'a pas pu l'être (avec la raison), le coût, et **↶ Annuler ce
changement** qui remet la vidéo exactement comme avant. Si ta demande n'est pas claire, l'IA te pose une question au lieu
de deviner. Ce qu'elle ne sait pas faire (ajouter une photo, par exemple) devient une note dans l'onglet Notes. Elle ne
touche jamais à ce que tu as verrouillé 🔒. « Version de 30 s » crée une nouvelle version ; l'originale ne change pas.

**Qui répond** : Claude s'il est prêt (environ 1 à 2 cents par demande avec Sonnet, moins d'un cent avec Haiku) ; sinon
l'IA locale (gratuite, 15 à 20 secondes) ; sinon des règles simples pour les demandes courantes.

## Les nouveaux sons de coupe (fini le même son de vent)

Avant, chaque coupe et chaque écran qui entre jouait le même « whoosh » (le son de vent). Maintenant il y a **65 nouveaux
sons** (52 créés ici, sans droits à payer, et 13 sons gratuits de Kenney), rangés en **7 familles** : **Doux**,
**Énergique**, **Tech / écran**, **Cinéma**, **Rétro**, **Glitch / numérique**, **Organique** (papier, bois, tissu).
Chaque coupe prend un son différent de la famille ; le même ne revient jamais deux fois de suite. Tous ont le même volume
perçu que l'ancien whoosh, et le moment le plus fort de chaque son tombe pile sur la coupe.

**Où** : éditeur → onglet **Style** → carte **Sons des coupes** (sous « Bruitages ») :
- **Varier les sons ✓** (décoché : tu retrouves exactement les sons d'avant) ;
- **Famille de sons** : « Auto selon le style » ou la famille de ton choix (gardée quand tu changes de style) ;
- **▶ Écouter** : les sons de la famille, l'un après l'autre ; et le volume.

Ou par la boîte 💬 : « des sons plus doux », « varie les sons », « toujours le même son ».
Si tu ne veux plus aucun son de vent : prends **Tech**, **Rétro**, **Organique** ou **Doux** (Énergique et Cinéma
gardent surtout des souffles).

## Ce qui a été essayé pour de vrai ce soir

**Claude (l'argent)** : un seul vrai appel a été tenté (les idées de Vidéo 1, sur une COPIE, avec Sonnet). Anthropic l'a
refusé à cause de l'espace de travail : **0,00 $**. Les autres essais prévus (l'avis sur « Vidéo 1 - qualité - FINAL » et
une demande « Dis à l'IA » par Claude) n'ont donc pas été envoyés : l'outil a dit clairement pourquoi et a continué en
local. **Total dépensé : 0,00 $ ; crédit restant estimé : 2,00 $.** Ton vrai montage n'a pas été touché.

**« Dis à l'IA » avec l'IA locale (gratuit)**, sur une copie de Vidéo 1 :
« mets les sous-titres en jaune pis la musique un peu moins forte » → en 12 secondes :
- sous-titres : blanc (#FFFFFF) → **jaune (#FFD400)** ;
- musique : volume 0,19 → **0,133** (un peu moins forte) ;
- une copie « avant » gardée (Annuler = retour exact).

**Les sons, avant / après, sur Vidéo 1 (Tech 3D)** — calculés par le même code que l'aperçu et l'export :

| Moment | Avant | Maintenant (famille Tech / écran) |
|---|---|---|
| 7 entrées d'écran | whoosh-court ×7 (le son de vent) | glisse tonale, sélection, balayage numérique, glisse, souffle léger, glisse tonale, sélection (5 sons différents) |
| 7 mots forts | pop grave ×7 | bulle, verre, bulle, pop doux, verre, pop doux, verre |
| montée avant l'appel à l'action | riser | riser numérique |
| même montage en style Reel Impact (famille Énergique) : 4 coupes | whoosh-court ×4 | whoosh avec chute, coupe sèche, passage éclair, whoosh court |

Son mesuré sur 11 secondes (8,6 s à 19,9 s, deux entrées d'écran et une liste) : les effets seuls sont au même niveau
qu'avant (−36,8 LUFS contre −36,7), et le son final reste à −14 LUFS sur la vidéo, crête −1,0 dB : rien ne sature. Sur le
spectrogramme, le souffle large de l'ancien whoosh (de 1 à 20 kHz) est remplacé par une glisse tonale et un petit « bip »
d'interface. **Je ne peux pas écouter** : c'est à toi de juger à l'oreille (« ▶ Écouter », puis un court export).

**Exemple des idées de Claude (fait avec un FAUX Claude dans les tests, pas encore avec le vrai)** : « Pi » → « Puis »,
« transférez » → « transférer », « appuyer » → « appuyez » ; notification « Lead qui attend depuis 3 h » ; mot géant
POURCENTAGE ; bouton « Réservez votre appel ». Une proposition inventée comme « Gagnez 10 clients » (chiffre jamais dit)
est retirée par l'outil.

## Pour les tests de la fin (après l'espace de travail)

1. ⚙️ → Claude : le bandeau rouge doit disparaître et dire « Claude prêt ».
2. Révision → Vidéo 1 → **🧠 Refaire avec Claude** (environ 3 à 6 cents) : regarde les mots en couleur, les cartes, le
   bandeau ; **Annuler** remet le montage d'avant.
3. Écris dans la boîte 💬 : « mets les sous-titres en jaune » (environ 1 à 2 cents), puis **↶ Annuler ce changement**.
4. Après un export : **👁 Critique Claude** (environ 5 cents) : compare sa note avec celle du juge n° 4 (7,9/10,
   `docs/qualite-2026-09-30/JUGEMENT-4.md`).
5. Style → Sons des coupes → ▶ Écouter les familles, puis un court export.

Total de ces essais : environ 0,10 à 0,15 $ avec Sonnet.

## Ce qui a été vérifié (sans dépenser)

Tout a été testé avec un **faux Claude** (aucun vrai appel) : 139 vérifications du moteur Claude, 90 des idées, 135 de
l'avis sur les images, 137 de « Dis à l'IA », 45 + 43 des sons, 110 du serveur, 17 de clics dans l'interface, 16 du plugin,
11 avec les vrais modules du moteur. Les anciens tests de l'éditeur passent aussi (contrôle qualité 54/54, juges, timeline,
galerie, cerveau créatif, sobriété), sauf un cas du juge n° 2 (« fin tenue ») qui a besoin de la transcription des rushs de
l'ancienne Vidéo 1, partis à la corbeille quand tu l'as supprimée : ce n'est pas un défaut de l'éditeur. L'éditeur a été relancé une fois (19 h 06) pour activer les nouvelles routes.

## À savoir

- Les montages déjà faits gardent leurs idées ; Claude ne relit un montage existant que sur un clic : « 🧠 Refaire avec
  Claude », « Relancer l'IA » (onglet Texte, propositions seulement) ou « Refaire » dans la Révision (nouveau montage).
- Tes anciennes vidéos varient déjà leurs sons de coupe (seuls les sons changent, pas le montage). « Varier les sons »
  décoché = exactement comme avant.
- Le crédit restant est une **estimation** faite par l'éditeur (ce qu'il a lui-même dépensé) ; le vrai solde est sur
  platform.claude.com (Billing).
- L'avis de Claude ne voit que des images fixes : il ne juge pas le mouvement ni le son (il écrit « à vérifier » quand il
  n'est pas sûr).
