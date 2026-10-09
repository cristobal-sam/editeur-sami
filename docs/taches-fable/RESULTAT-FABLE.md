# Résultat Fable — Éditeur Sami — 2026-09-30

Mission : `ETAT-POUR-FABLE.md` §4 (plugin, relecture des corrections, avis sur la suite).
Lecture seule : je n'ai modifié ni le moteur, ni l'interface, ni les styles, ni `projects\`, `media\`, `livraisons\`.

## En bref

- **Le plugin marche** dans Claude : les 4 outils de lecture répondent.
- **Les 12 corrections font ce qui est annoncé** sur les cas testés. Tous les tests existants passent.
- **J'ai trouvé 3 vrais défauts dans la nouvelle « relecture du monteur »** (`sobriete.py`). Ils ne gênent presque pas
  aujourd'hui, mais ils feraient des dégâts dès qu'on branche la relecture sur le changement de style (point 2 du §3).
  À corriger **avant** ce branchement.
- 4 autres problèmes moyens (immobilier, corbeille, messages d'export en anglais, longues vidéos) et quelques petits.
- Le vrai serveur (8790) tourne toujours avec l'ancien code. Rien n'est en cours : il peut être relancé dès que
  l'utilisateur est d'accord.
- Les 2 vidéos déjà dans la Révision ont été montées avec l'ancien code : il faudra cliquer « Refaire » pour les nettoyer.

---

## 1. Tâche A — plugin « Éditeur Sami »

| Outil | Résultat |
|---|---|
| `etat` | OK. 2 vidéos « à regarder », montage au repos, file d'exports vide. |
| `styles` | OK. 20 styles, 10 sujets → style, aucune charte client. |
| `erreurs` | OK. Aucun journal d'erreurs, aucune vidéo en erreur. |
| `galerie` | OK. 20 styles dans 7 catégories, avec le chemin des aperçus (donc version 1.1.0 chargée). |

- Rien à corriger dans le plugin. `.claude\settings.json` l'active bien (les outils sont apparus seuls dans ma session).
- Aucun outil de suppression. Le plugin ne lit jamais `cles-api.env` (seulement des refus explicites, `serveur.mjs:203` et `:245`).
- **Signe que le serveur tourne l'ancien code** : `etat` affiche encore « Reel Impact » pour la vidéo `0a92d5202af8`
  (projet `script1`), alors que son montage est en « Clip podcast ». Ce sera juste après le redémarrage.
- Je n'ai appelé ni `monter`, ni `prendre`, ni `changer_style`, ni `refaire`, ni `retirer`, ni `style_reference`.

---

## 2. Relecture des corrections

« Vérifié » = j'ai relu le code **et** relancé au moins un essai sur une copie.

| # | Défaut | Vérifié | Ce que j'ai mesuré | Problème trouvé | Correctif proposé |
|---|---|---|---|---|---|
| 1 | Mots en couleur trop nombreux | **Oui** | script1 : 54 → 26 mots sur 285 (9,1 %). video1video1 : 51 → 24 sur 265 (9,1 %). Aucun petit mot seul. Deux passages = même résultat. Retouches à la main gardées. Cas limites sans plantage (aucun plan, plan vide, un mot, tout masqué). | Ce que l'utilisateur **voit** ne change pas tant que la boîte du style Clip podcast suit chaque mot (§3 point 1). Sur un ancien montage, un mot coloré à la main peut tomber au premier changement de style. En anglais, « five times faster » ne colore que « five times ». | Faire le point 1 du §3. Le reste est acceptable. |
| 2 | Nouveaux styles : mauvais mot | **Oui** (données, pas à l'image) | Éditorial : 6 mots géants en 71 s dont « trois heures ». Collage : 4 autocollants dont « trois heures ». Hormozi : « trois heures » en couleur, plus « attend ». Aucun doublon. | Aucun. | — |
| 3 | Notification Tech | **Oui** (sans IA) | 3 notifications visibles (« Nouveau lead reçu » 6,3 s, « Lead en attente depuis 3 h » 26,4 s, « Réponse envoyée au lead » 35,1 s) et 3 masquées. Aucune étiquette technique, aucun texte coupé. | « RyuCalls » est écrit en dur comme marque par défaut (`galerie.py:16`). Sans gravité : utilisé seulement si le mot est dit. | Plus tard : lire la marque dans la charte client. |
| 4 | Plans de coupe hors sujet | **Oui** (sans IA ni recherche d'images) | Aucun style ne demande de plans automatiques. Les 9 emplacements proposés sont hors accroche et hors appel à l'action, jamais sur « RyuCalls », « deux », « des ». Sans avis de l'IA, rien n'est inséré. | Dans le montage automatique normal, les propositions ne sont **pas calculées** (seulement si le style le demande) : `suggestions.broll` reste vide. Touché aussi par le problème A2 ci-dessous. | Voir A2. Le point 5 du §3 devient peu urgent. |
| 5 | Trop d'éléments au début | **Oui** pour le montage automatique | Ancien montage raté relu : 8 retirés, 1 déplacé, 2 corrigés, 4 gardés. Rien pendant l'accroche, au moins 4 s entre deux éléments. | **Trois défauts : A1, A2, A3 ci-dessous.** Et la relecture ne tourne pas au changement de style : en Karaoké l'emoji 📞 reste à 1,5 s, en Infographie « 1 semaine » reste à 66 s sur l'appel à l'action. | Corriger A1-A3, puis point 2 du §3. |
| 6 | Graphismes faux | **Oui** (sans IA) | « ×5 MOINS CHER » à 37,9 s (confiance haute). « 3 h » à 26,3 s sans libellé. Plus de « A DÉJÀ ÉTÉ » ni « MOINS CHER QU'UN ». Rien pendant l'accroche. | Le compteur défile encore de 0 à la valeur tant que `graphics.tsx` n'est pas corrigé (§3 point 3). Le mot géant de repli est « ENTREPRISE » : faible, mais c'est seulement une proposition. | Point 3 du §3. |
| 7 | Bandeau = phrase coupée | **Oui** (sans la relecture par l'IA) | Phrase coupée refusée, « VOTRE CONCURRENT PRISE LE LEAD » refusé, vrai titre accepté. | B1 ci-dessous (immobilier). Un bandeau valide n'est relu par l'IA que si le style l'affiche (`auto.py:227`) : il peut apparaître non relu après un changement de style. Beaucoup de vidéos n'auront **aucun** bandeau : à valider, car le bandeau fait partie du style Reel Impact. | Relire le bandeau même masqué. Décision de l'utilisateur sur « pas de bandeau ». |
| 8 | Style affiché ≠ vrai style | **Oui** | Sur la copie : « style lu dans le montage : podcast-clip (registre : reel-impact) ». | Aucun. Visible seulement après le redémarrage du serveur. | — |
| 9 | Titre « Script 1 » | **Oui** | 6 cas : « Script 1 » + dossier « Vidéo 1 » → « Vidéo 1 » ; « SCRIPT 2 » → « Vidéo 2 » ; vrai titre gardé ; « pub1.mp4 » → « pub1 ». | Le style Documentaire affiche « Vidéo 1 » à l'image après un changement de style (§3 point 7). | Point 7 du §3. |
| 10 | Supprimer une vidéo | **Oui** | 41 vérifications réussies sur la copie : origine refusée (4 cas), 6 chemins piégés refusés, jonctions jamais suivies, refus pendant montage / export / travail du moteur, dossiers avec accents et espaces (« Lot T1\Vidéo A »), vidéos exportées gardées, registre à jour. **Rien n'est effacé : tout est déplacé** (`fs.rename`). | B2 ci-dessous (note de la corbeille fausse). Le texte de confirmation peut dire « les vidéos brutes vont dans la corbeille » alors que le serveur les garde pour une vidéo jumelle cachée (`revision.tsx:315`). Un projet dont le nom dépasse 60 caractères ne peut pas être supprimé (`server.mjs:884`) — limite qui existait déjà partout. | Voir B2. |
| 11 | Export bloqué | **Oui** | Faux export bloqué à 3 % : arrêté en 19 s avec le message en français, processus enfant arrêté. Annulation ignorée : forcée en 6 s. 4 vrais exports de 2 s réussis (16 s en direct, 8 s par la file). | B3 et B4 ci-dessous. Après un arrêt forcé, les fichiers temporaires (`… - FINAL.mp4.image.mp4`, `.voix.wav`, `.mix.wav`, `.fx.raw`) peuvent rester dans `livraisons\` (lu dans le code, pas testé). | Voir B3, B4. Nettoyer ces 4 fichiers côté serveur après un arrêt forcé (`server.mjs`, bloc `finally` de `pump`, ligne 348). |
| 12 | Plugin | **Oui** | Voir tâche A. | Aucun. | — |

Tests relancés, tous réussis : `verification.py` 8/8, `test-galerie.py` 6/6, `test-timeline.mjs` 6/6,
`test-sobriete.py` 8/8, `test-blocage.mjs` 12/12, `test-http.mjs` 41/44. Les 3 échecs de `test-http.mjs` viennent du bac à
sable, pas du code : les copies de vidéos y avaient été retirées, donc l'export court ne trouvait plus ses images.
Avec les médias remis (liens), l'export passe.

Mon script : `docs\taches-fable\tests\revue_moteur.py` (62 vérifications, 4 échecs = A1, A2, A3, B1).

---

## 3. Problèmes trouvés

### A. À corriger avant de brancher la relecture sur le changement de style

**A1. Un bandeau réglé sur « Toute la vidéo » fait retirer tous les autres éléments.**
- Où : `engine\editeur\sobriete.py:298-301`. Le bandeau compte comme un élément fixe du début à la fin ; la règle
  « un seul élément à la fois » rejette alors tout le reste.
- Mesuré : même montage, même bandeau. Jusqu'à 4,5 s : 4 éléments gardés. « Toute la vidéo » : **0 gardé, 11 retirés**.
- Ce réglage existe dans l'interface (`app\ui\panels.tsx:403`, bouton « Toute la vidéo »).
- Correctif : ne compter le bandeau que pendant l'accroche. Ligne 301 :
  `fixed.append({'at': start, 'fin': min(end, rep['accroche'])})`.

**A2. L'appel à l'action est mal repéré quand un mot comme « contacte », « lien » ou « appelez » est dit au milieu.**
- Où : `sobriete.py:102-106` (la dernière phrase qui contient un de ces mots, où qu'elle soit), puis `sobriete.py:343`
  (tout ce qui finit après ce point est retiré). Même repère dans `broll.py:126` et `graphismes.py:91, 124, 132`.
- Mesuré : vidéo de 23 s, « un agent contacte vos leads » dit à 5,9 s, vraie dernière phrase à 20,7 s.
  Repère trouvé : **5,85 s**. Tout plan de coupe, mot géant, emoji ou scène de style après 6 s serait retiré, et plus
  aucun emplacement ne serait proposé. Pour un service qui « contacte » ou « appelle » des leads, c'est probable.
- Correctif : utiliser d'abord le bloc d'appel à l'action du script (`reel['ctaBlock']`, déjà lu lignes 107-110) ;
  n'accepter une phrase repérée par ses mots que si elle commence dans le dernier quart de la vidéo ; sinon `cta = None`.

**A3. Un emoji posé à la main est traité comme automatique.**
- Où : `sobriete.py:160` (`'auto'` vaut vrai dès que le montage est en mode IA automatique).
- Mesuré : emoji 🔥 ajouté à la main sur l'accroche, puis relecture comme lors d'un changement de style : **retiré**.
  La règle promise est « les éléments posés à la main ne sont jamais touchés ».
- Correctif : ligne 160, `'auto': False`. Les emojis ne sont alors nettoyés qu'au montage automatique (`tout=True`),
  ce qui suffit : ils ne sont pas régénérés à chaque style.

Effet lié, à dire à l'utilisateur : sur un montage fait **avant** ces corrections, les anciens éléments n'ont pas de
marque « automatique ». La relecture les garde tous (7 plans de coupe hors sujet compris) et ils remplissent le budget.
Mesuré sur `script1` en Karaoké : 11 anciens éléments gardés, les 5 emojis retirés. Seul « Refaire » nettoie ces vidéos.

### B. Moyens

**B1. Montage automatique d'une vidéo sans parole (immobilier, événement) : le titre-adresse disparaît.**
- `auto.py:225-229` : le nouveau contrôle du bandeau refuse tout texte qui n'est pas un titre validé par l'IA.
  Vérifié sur un faux montage : bandeau « 12 RUE DES ÉRABLES » → refusé.
- Déjà là avant les corrections, lu dans le code, **pas testé sur une vraie vidéo** : `auto.py:197-205` supprime le
  montage que `visuel.py:227-233` vient d'écrire et le refait, ce qui perd aussi le type (`kind`) et le réglage « pas de voix ».
- Correctif : dans `_finish`, ne pas refaire le montage et ne pas toucher au bandeau quand `info['type']` est
  `immobilier` ou `evenement`.

**B2. La note de la corbeille promet ce que l'outil ne fait pas.**
- `server.mjs:976` dit : remets le dossier `projects` d'abord « pour retrouver le montage sans le refaire ».
- En réalité (lu dans le code, pas testé) : la vidéo remise est vue comme nouvelle (`server.mjs:742`), un montage
  automatique démarre, et `auto.py:197-204` range le montage restauré dans les versions puis le refait.
- Correctif simple : corriger le texte (« la vidéo sera remontée ; ton ancien montage sera dans l'onglet Versions »).
  Correctif complet : un bouton « Restaurer » qui remet les dossiers et réinsère la fiche gardée dans `corbeille.json`
  (champ `registre`) avant le passage du scanneur.

**B3. Quand un média manque, l'erreur d'export est en anglais.**
- Vu deux fois dans le bac à sable : « Timed out after 30000ms while setting up the headless browser… » (34 s) et
  « Received a status code of 404 while downloading file … » (10 s). C'est rapide, mais incompréhensible.
- Où : `remotion\render.mjs:287` renvoie le message brut.
- Correctif : avant le rendu, vérifier que chaque média optimisé et chaque vidéo brute du montage existe, sinon
  « Le fichier de la prise « X » est introuvable : clique Refaire. » ; traduire aussi le délai dépassé du navigateur.

**B4. Garde-fou de 10 minutes sur les étapes sans progression : risque pour les longues vidéos.**
- `server.mjs:266` : « Montage de la voix » et « Mixage final » n'envoient aucune progression. Pour un reel de 70 s
  c'est quelques secondes. Pour un podcast d'une heure, je ne l'ai **pas mesuré** : l'étape pourrait dépasser 10 min et
  l'export serait arrêté à tort.
- Correctif : limite proportionnelle à la durée du montage (par exemple 10 min + 1 min par minute de vidéo).

### C. Petits

- `reel.py:844` : « Relancer l'IA » efface `suggestions.broll` côté moteur (en plus de `panels.tsx:199`, déjà connu).
  Même chose en mode suggestion, `reel.py:910`. Correctif : garder la clé `broll` de l'ancien `suggestions`.
- `sobriete.py:34` : « chez vos concurrents » est pris pour le début de la solution (seuls « chez vous / nous / toi… »
  sont exclus). Ajouter `vos|votre|les|le|la|un|une|mon|ma|mes|son|sa|ses|leur|leurs|ce|cette|ces`.
- `server.mjs:346` : si l'utilisateur clique « Annuler » pendant les 20 s qui suivent un blocage, le message de blocage
  est remplacé par « Export annulé. ». Sans gravité.
- Deux définitions de l'accroche : `galerie.py:17` (4,5 s au plus) et `sobriete.py` (3 à 6 s). La relecture est la plus
  stricte, donc pas de danger, mais un seul réglage serait plus clair.

---

## 4. Avis sur les 9 points du §3 — ordre conseillé

| Ordre | Point | Avis |
|---|---|---|
| 1 | **9a. Relancer le vrai serveur** | À faire en premier, avec l'accord de l'utilisateur. Rien ne tourne. Sans ça, la 🗑️ répond « Action inconnue », le style affiché est faux et le garde-fou d'export n'existe pas. |
| 2 | **1. Boîte du style Clip podcast** (`Reel.tsx:187` et `:203`) | Le défaut le plus visible, petit changement. Je conseille : boîte seulement sur les mots en couleur (`w.hl`), affichée dès que le mot est dit. À savoir : avec 9 % de mots en couleur, la boîte deviendra rare ; c'est voulu. |
| 3 | **3. Compteur** (`graphics.tsx:26`) + **4. Types** (`types.ts`) | Ensemble : petit et sans risque. Sans le point 3, « 3 h » s'affiche encore comme « 1 h → 3 h ». |
| 4 | **Corriger A1, A2, A3** (nouveau) | Avant le point suivant. Trois petites modifications dans `sobriete.py`. |
| 5 | **2. Relecture au changement de style** (`reel.py`, après la ligne 680) | Oui, avec le `try / except` proposé par l'agent. Seulement après l'étape 4. |
| 6 | **7. Titre Documentaire et ancien titre** | Utile. La partie « reconstruction » est rare : l'éditeur rouvre un montage existant sans le reconstruire (`App.tsx:82`). |
| 7 | **5. Propositions de plans de coupe** | D'abord ne plus les perdre (`panels.tsx:199` et `reel.py:844`). L'affichage peut attendre : dans le montage normal, rien ne remplit encore cette liste. |
| 8 | **6. `item.style` dans `/template` et `/restore`** | Faible priorité : la liste lit déjà le vrai style. À faire pour la propreté du registre. |
| 9 | **8. Budgets par style** | Attendre. Les valeurs par défaut suffisent. À régler après essai sur 3 ou 4 vraies vidéos. Attention au Karaoké : les emojis comptent dans le budget ; 3 par minute lui enlèverait son caractère. |
| 10 | **9b. REPRISE.md** | À la fin, une fois les correctifs appliqués. Ajouter aussi les problèmes A1-A3 et B1-B4 s'ils ne sont pas corrigés. |

Le point 10 (nettoyage des bacs à sable) peut attendre. Rappel : retirer les jonctions avec `rmdir` d'abord.

---

## 5. Ce que j'ai lancé, et ce que je n'ai pas vérifié

Lancé :
- Les 4 outils de lecture du plugin contre le vrai serveur (aucune écriture).
- Les tests Python et Node cités, sur des copies en mémoire ou dans `runtime\cache\tmp\`.
- Deux fois une **copie isolée** du serveur sur le port 18793 (bac à sable `runtime\cache\tmp\interface-fable-85584\`,
  faux moteur), arrêtée à chaque fois. Le vrai serveur 8790 n'a jamais été touché et tourne toujours.
- 4 exports de **2 secondes** dans cette copie seulement, pour vérifier l'export. Pour cela j'ai mis 9 liens vers les
  médias optimisés dans la copie, puis je les ai retirés ; les originaux sont intacts.
- Aucune IA locale, aucun montage, aucun export dans le vrai dossier.

Fichiers ajoutés : `docs\taches-fable\RESULTAT-FABLE.md`, `docs\taches-fable\tests\revue_moteur.py`,
`runtime\cache\tmp\revue-fable\` (une copie de montage), et dans le bac à sable `interface-fable-85584\` :
`essai-export-fable.mjs`, `serveur-18793-fable.log`, `serveur-18793-fable-b.log`, `rendu\out\stderr-fable.txt`.

Pas vérifié :
- Tout ce qui passe par l'IA locale : titres de notification reformulés, relecture du bandeau, liste de bénéfices,
  mot choc, jugement « concret » des plans de coupe.
- Le rendu à l'image des nouveaux styles (position de la notification, mot géant) : je n'ai regardé aucune image.
- Les boutons de suppression dans le navigateur (l'agent l'avait fait ; j'ai testé les routes).
- B1 et B2 sur un vrai cas, B4 sur une longue vidéo, les fichiers temporaires après un arrêt forcé.
