# Recherche montage — 30 septembre 2026

Deux recherches web faites pour orienter la suite de l'éditeur (styles, son, vidéos de test) :
1. **Tendances, données de rétention et normes** : recherche complète, sources à la fin de la section 2.
2. **Vidéos libres pour tester et banques de plans de coupe** : la recherche a été arrêtée avant la fin.
   Voici ce qu'elle avait déjà vérifié sur les pages officielles.

Rien n'a été téléchargé. Les licences ont été lues le 2026-09-30. Il faut les revérifier avant de publier quoi que ce soit.

---

## 1. Ce que ça change pour l'éditeur

- **Un style = une recette de briques + un budget de densité** (curseur de sobre à dense). Aucune brique n'est posée « à chaque coupe ».
  - **Relance visuelle** (punch-in, plan de coupe ou graphisme). Valeurs de départ à calibrer :
    - toutes les ~6 s en sobre ;
    - toutes les 2-3 s en standard ;
    - toutes les 1-1,5 s en dense ;
    - plus dense au début.
  - **Garde-fous** :
    - 2 couches d'effets simultanées au plus ;
    - zones sûres respectées ;
    - lisibilité vérifiée.
- **Style MrBeast** : MrBeast lui-même a ralenti (38 coupes/min en 2023, 23 en 2024). Notre préréglage sera donc « dense mais lisible », pas du chaos.
- **Accroche automatique (0-3 s)** :
  - la phrase la plus forte en premier ;
  - un texte de 2-6 mots dès la 1re image ;
  - un changement visuel avant 1,5 s ;
  - 3 accroches au choix (bouton « Autre accroche »).
- **Sous-titres** : toujours présents, mot à mot avec le mot-clé surligné.
  - Ils sont placés dans la zone sûre des applis : garder libres 14 % en haut, 35 % en bas et 6 % sur les côtés.
  - Variante sobre : phrase entière, 42 caractères par ligne, 2 lignes.
- **Son, normes pro** :
  - **Niveaux** : −14 LUFS intégré, crête vraie −1 dBTP.
  - **Voix** : coupe des graves sous 80 Hz, débruitage modéré, de-esser (≤ 4 dB), compression légère (≤ 6 dB).
  - **Musique sous la voix** :
    - 18-25 dB sous la voix, et elle remonte dans les silences ;
    - ducking 2:1, attaque 15-20 ms, relâche 600-700 ms ;
    - creux d'égalisation entre 800 Hz et 3 kHz.
  - **Placement de la musique** :
    - elle entre après l'accroche ;
    - sa fin est calée à rebours sur son dernier accent, avec une coupe sur la mesure plutôt qu'un fondu ;
    - au-dessus de 120 BPM, les pubs TikTok sont mieux regardées.
- **Durées** :
  - pub : 21-34 s (TikTok) ou 15 s et moins (Meta) ;
  - organique : Reels de 45-60 s.
  - Les déclinaisons 60/30/15 s existent déjà. Il faudra une durée par défaut selon le type.
- **Fin** : appel à l'action écrit à l'écran (+152 % de conversions selon TikTok) et fin sèche ou en boucle.
- **Galerie de styles possibles** :
  - Hormozi ;
  - MrBeast (dense) ;
  - Podcast ;
  - Pub UGC ;
  - Premium cinématique (Iman Gadzhi) ;
  - Doux (Ali Abdaal) ;
  - Documentaire collage (Johnny Harris) ;
  - Sobre (MKBHD).
- **Concurrents** : Submagic, OpusClip, CapCut et Captions font déjà émojis et mots-clés, suppression des silences, recadrage et plans de coupe. Notre différence :
  - tout est local ;
  - prises multiples ;
  - charte client ;
  - 20 vidéos par jour sans manipulation.

---

## 2. Tendances, données et normes (rapport complet)

Légende : **[F]** fait chiffré sourcé · **[P]** pratique courante ou avis, non démontré.

### 2.1 Styles types
- **MrBeast** : son document interne [1] donne des consignes, pas des données.
  - La 1re minute est décisive.
  - Il faut montrer plutôt qu'annoncer et tenir la promesse du titre.
  - Relances vers 3 et 6 min, aucun temps mort, fin abrupte.
  - [F] 38 coupes par minute en 2023, 23 en 2024 (échantillons d'une minute). Il dit avoir « ralenti » [2]. L'hyper-densité est donc datée.
- **Hormozi** [4] [P] :
  - plans de 1-3 s, coupes sèches entre plan moyen et plan serré, punch-in de 10-20 % ;
  - sous-titres en MAJUSCULES grasses (Anton, proche de Montserrat Black), blancs à contour noir, mot prononcé en jaune, 2-4 mots visibles, apparition « pop » ;
  - fond sombre et contrasté ;
  - les sources ne s'accordent pas sur les bruitages et les images.
- **Ali Abdaal** [5] [P] :
  - rythme modéré ;
  - typographie fine (Inter, TT Fors) animée lettre par lettre ;
  - transitions « papier déchiré » avec bruits de papier ;
  - image claire et chaude, musique lo-fi.
- **Iman Gadzhi** [6] [P] :
  - plans de coupe « art de vivre » cinématiques, étalonnage par LUT ;
  - ralentis et rampes de vitesse, transitions fluides avec whoosh ;
  - typographie sobre, musique cinématique qui monte.
- **Podcast** [8] [P] :
  - plein cadre sur la personne qui parle ;
  - écran partagé empilé seulement pendant les échanges ;
  - départ sur la phrase la plus forte, environ 45 s.
- **Pub UGC** :
  - [F] image lo-fi, regard caméra, structure accroche → corps → appel à l'action, texte à l'écran, plusieurs scènes [11–13] ;
  - [P] tester 3-5 accroches, jamais de logo en ouverture [9].
- **Faceless** [P] : voix off (souvent IA), illustrations de banque ou générées qui changent souvent, sous-titres synchronisés, musique [32].
- **Documentaire (Johnny Harris)** [7] [P] :
  - cartes animées ;
  - collage texturé animé à 12 i/s : détourages à liseré blanc, photos « punaisées », flèches dessinées ;
  - punch-ins marqués, peu de fondus ;
  - bruits de papier et d'obturateur.
- **Retention editing** [10] [P] : relances (plan de coupe, zoom, graphisme, bruitage) toutes les 20-40 s en format long.
- **Repère sobre mesuré** [F] : MKBHD (3 vidéos), 7,4 coupes/min, plan médian d'environ 6 s, plus dense au début [3].

### 2.2 Ce que disent les données

**Accroche**
- [F] TikTok :
  - plus de 63 % des pubs au meilleur taux de clic livrent le message en 3 s [11] ;
  - 90 % de l'effet sur la mémorisation se joue en 6 s [12] ;
  - une accroche à suspense donne +16 % de temps vu [12].
- [F] Facebook/Nielsen : jusqu'à 47 % de la valeur d'une campagne vient de vues de moins de 3 s, et 74 % de vues de moins de 10 s [18].
- [F] Buffer (1,1 million de TikTok) : le temps médian vu est de 6,9 s pour une vidéo de 30-60 s [24].
- [F] Mesure de l'abandon :
  - Instagram mesure l'abandon avant 3 s depuis août 2025 [21] ;
  - YouTube Shorts affiche « regardé / balayé » [23].

**Son coupé et sous-titres**
- [F] Verizon/Publicis 2019 (5 616 adultes américains) [20] :
  - 69 % regardent sans son en public, 25 % en privé ;
  - ils sont 80 % plus enclins à finir une vidéo sous-titrée ;
  - 80 % des usagers des sous-titres entendent bien.
- [F] Meta :
  - les sous-titres donnent +12 % de durée vue [15] ;
  - en 2016, 85 % des vues Facebook se faisaient sans son [19].
- [F] Mais TikTok et Reels se regardent « son activé » : 88-90 % des utilisateurs TikTok jugent le son essentiel [12, 14, 17]. Il faut donc un montage lisible sans son, et meilleur avec.
- [F] Texte à l'écran :
  - 40 % des pubs TikTok au meilleur visionnage ont du texte superposé [11] ;
  - un appel à l'action écrit donne +152 % de conversions [13].

**Rythme**
- [F] Études en laboratoire :
  - plus de coupes dans une même scène augmente l'attention et la mémoire, sans surcharge [26] ;
  - rythme rapide et contenu très excitant ensemble : surcharge, et moins de mémorisation [27] ;
  - un effet sonore réoriente l'attention et aide à retenir l'information qui suit [28].
- [F] TikTok :
  - pubs e-commerce à plusieurs scènes : +38 % de conversions [13] ;
  - musique au-dessus de 120 BPM : meilleur visionnage [11].
- [P] Aucune donnée publique fiable ne donne la fréquence idéale des relances.

**Durée**
- [F] Pubs :
  - pub TikTok de 21-34 s : +280 % de conversions [13] ;
  - Meta suggère 15 s ou moins pour ses pubs [16].
- [F] Contenu organique :
  - Reels de 45-60 s : meilleur engagement et meilleures vues (6 millions de Reels, 2026) [25] ;
  - TikTok de plus de 60 s : plus de portée [24] ;
  - Shorts jusqu'à 3 min [23].
- [F] Instagram classe d'abord sur le temps vu (en % et en secondes), puis les j'aime et les partages rapportés à la portée [22].

### 2.3 Sous-titres : tendances et outils
- [P] **Style dominant** :
  - 1-4 mots, affichés mot par mot, mot prononcé surligné (jaune, vert) ;
  - contour ou ombre, apparition « pop », émojis ponctuels ;
  - placés dans le tiers inférieur-médian, hors de l'interface.
  - Meta demande de libérer 14 % en haut, 35 % en bas et 6 % sur les côtés [39].
- **Style sobre** :
  - [P] phrase entière en casse normale ;
  - [F] repère Netflix fr-CA : 42 caractères par ligne, 2 lignes, 17 caractères par seconde au plus [38].
- **Outils** [29–32] :
  - **Submagic** : émojis et mots-clés automatiques, modèles « Hormozi », zooms, plans de coupe, bruitages, suppression des silences ;
  - **OpusClip** : découpage, recadrage qui suit le sujet, plans de coupe IA, score de viralité, suppression des hésitations ;
  - **CapCut** : mots-clés surlignés, mots parasites, recadrage ;
  - **Captions** : AI Edit (coupes et plans de coupe), débruitage, pauses, regard caméra, musique générée.

### 2.4 Audio
- [F] YouTube et Spotify normalisent à −14 LUFS [33].
- [F] La norme AES TD1008 fixe parole −18, musique −16 et contenu mixte −17 LUFS, avec une crête vraie ≤ −1 dBTP [34].
- [P] TikTok et Instagram ne publient aucune cible. Viser −14 LUFS intégré et −1 dBTP.
- [P] Voix : passe-haut à 80 Hz, débruitage modéré, de-esser ≤ 4 dB, compression ≤ 6 dB [35].
- [P] Musique sous la voix [36] :
  - 18-25 dB sous la voix, remontée quand personne ne parle ;
  - transitions de 0,5-1 s ;
  - creux d'égalisation entre 800 Hz et 3 kHz.
- [P] Ducking : ratio 2:1, attaque 15-20 ms, relâche 600-700 ms [37].
- [P] Placement de la musique :
  - elle entre après l'accroche [12] ;
  - sa fin se cale à rebours sur son dernier accent, avec un raccord sur une mesure plutôt qu'un fondu [40].

### 2.5 Dix briques prioritaires (impact décroissant)
Plusieurs existent déjà dans l'éditeur. L'enjeu est un « budget de densité » par style qui les pilote ensemble.
1. **Accroche 0-3 s** [11, 12, 24] :
   - la phrase la plus forte d'abord ;
   - un texte de 2-6 mots dès la 1re image ;
   - un changement visuel avant 1,5 s ;
   - 3 variantes.
2. **Sous-titres animés** mot à mot, mots-clés surlignés, zone sûre, préréglages du sobre au dense [15, 20].
3. **Resserrage** : suppression des silences, hésitations et faux départs, avec une pause résiduelle réglable par style.
4. **Horloge de relance** : un changement visuel toutes les N s, par punch-in, plan de coupe ou graphisme, plus dense au début [2, 3, 26].
   - Valeurs de départ à calibrer : 6 s en sobre, 2-3 s en standard, 1-1,5 s en dense.
5. **Plans de coupe et cartes sur les mots-concepts** [13] :
   - plein écran, encadré ou écran partagé ;
   - cartes ✅ pour les listes, compteurs pour les chiffres.
6. **Bruitages liés aux événements** (whoosh, pop, impact), placés juste avant l'information clé [28].
7. **Musique** : choix par énergie et BPM, entrée après l'accroche, ducking, fin calée [11, 12].
8. **Structure et fin** : accroche → corps → appel à l'action écrit ; fin sèche ou en boucle [1, 13].
9. **Voix et loudness** : chaîne de traitement de la voix, −14 LUFS et −1 dBTP homogènes.
10. **Garde-fous de densité** [27] :
    - 2 couches simultanées au plus ;
    - pas de bruitage à chaque coupe ;
    - respect des zones sûres ;
    - lisibilité vérifiée.

**Chiffres écartés** parce que leur méthode n'est pas vérifiable :
- « 1,7 s pour décider » ;
- « 70-80 % des Reels regardés avec le son » ;
- les références de rétention de Retensis (aucune méthode publiée) ;
- « une relance toutes les 4 s donne 58 % de rétention » (OpusClip, 500 vidéos) ;
- « 30 coupes par minute idéales ».

La plupart des sources [P] sont des blogs d'outils commerciaux.

**Sources**
1. Mémo MrBeast : https://www.alexanderjarvis.com/memo-how-to-succeed-in-mrbeast-production/ ; https://www.danielscrivner.com/how-to-succeed-in-mrbeast-production-summary/
2. Tubefilter 2024 : https://www.tubefilter.com/2024/03/04/mrbeast-editing-style-number-of-cuts-per-video/
3. WritePanda (mesure MKBHD) : https://www.writepanda.ai/blog/mkbhd-editing-style-measured/
4. Hormozi : https://www.submagic.co/blog/how-to-make-alex-hormozi-captions ; https://www.choppity.com/tools/recreate-video-editing-style/alex-hormozi/ ; https://riverside.com/blog/hormozi-style-videos
5. Ali Abdaal : https://sendshort.ai/guides/ali-abdaal-style/ ; https://www.submagic.co/blog/make-shorts-like-ali-abdaal
6. Iman Gadzhi : https://sendshort.ai/guides/iman-gadzhi-style/
7. Johnny Harris : https://fcpxfullaccess.com/blogs/blog/vox-johnny-harris-documentary-style-final-cut-pro ; https://www.premiumbeat.com/blog/making-maps-for-johnny-harris/
8. Podcast : https://www.heyeddie.ai/blog/how-to-make-vertical-clips-from-a-podcast-or-interview
9. UGC : https://reloop.so/blog/article/ugc-advertising/
10. Retention editing : https://etwell.studio/blog/what-is-retention-editing-and-why-does-it-matter-for-youtube
11. TikTok, « 9 Creative Tips » : https://ads.tiktok.com/business/library/Auction_Ads_Creative_Tips.pdf
12. TikTok, « Creative Codes » (2023 ; études Kantar, Lumen, Neuro-Insight) : https://ads.tiktok.com/business/library/Creative_Codes_One_Pager_CA.pdf
13. TikTok, conversions (déc. 2021) : https://ads.tiktok.com/business/en-US/blog/creative-that-drives-conversions
14. TikTok, bonnes pratiques (Ipsos 2022) : https://ads.tiktok.com/business/en/blog/creative-best-practices-top-performing-ads
15. Meta, sous-titres +12 % : https://www.facebook.com/business/news/updated-features-for-video-ads
16. Meta, vidéo mobile : https://www.facebook.com/business/news/want-to-better-video-ads-for-mobile-well-show-you-how
17. Meta, pubs Reels : https://www.facebook.com/business/ads/facebook-instagram-reels-ads
18. Facebook/Nielsen (173 études, 2015) : https://martech.org/even-brief-video-views-drive-brand-lift-facebook-nielsen-study-finds/
19. Digiday 2016 : https://digiday.com/media/silent-world-facebook-video/
20. Verizon Media/Publicis 2019 : https://www.nexttv.com/news/mobile-videos-often-watched-without-audio-study-finds ; https://www.streamingmedia.com/Articles/ReadArticle.aspx?ArticleID=131860
21. Instagram, taux d'abandon (août 2025) : https://www.socialmediatoday.com/news/instagram-adds-retention-insights-reels/758464/
22. Mosseri (janv. et févr. 2025) : https://www.socialmediatoday.com/news/instagram-shares-algorithm-insights-2025/738034/ ; https://www.socialmediatoday.com/news/instagram-longer-video-watch-time-versus-completion-rate/740916/
23. YouTube Shorts : https://support.google.com/youtube/community-video/273390203/new-youtube-shorts-metric-viewed-vs-swiped-away?hl=en-EN ; https://blog.youtube/news-and-events/tall-updates-coming-to-shorts/
24. Buffer (mars 2025) : https://buffer.com/resources/longer-tiktoks-get-more-views-data/
25. Socialinsider (juill. 2026) : https://www.socialinsider.io/blog/instagram-reels-length/
26. Lang et al. 2000 : https://www.tandfonline.com/doi/abs/10.1207/s15506878jobem4401_7
27. Lang et al. 1999 : https://www.tandfonline.com/doi/abs/10.1080/08838159909364504
28. Potter, Lang et Bolls 2008 : https://econtent.hogrefe.com/doi/10.1027/1864-1105.20.4.168
29. Submagic : https://www.submagic.co/ ; https://www.submagic.co/blog/reasons-to-use-submagic-for-ai-captions
30. OpusClip : https://www.opus.pro/ ; https://www.opus.pro/blog/opusclip-clip-different
31. CapCut : https://www.capcut.com/tools/filler-words ; https://www.capcut.com/tools/video-keywords ; https://www.capcut.com/tools/long-video-to-shorts
32. Captions : https://www.captions.ai/ ; https://captions.ai/use-cases/faceless-video-ai-voiceover
33. Production Advice (2021) : https://productionadvice.co.uk/td1008/
34. Radio World (AES TD1008) : https://www.radioworld.com/tech-and-gear/tech-tips/streaming-audio-loudness-guidelines-explained
35. Sage Audio : https://www.sageaudio.com/articles/mastering-voice-over-dialogue-for-video
36. VidPros : https://vidpros.com/fix-background-music-too-loud-video/
37. Sound On Sound : https://www.soundonsound.com/techniques/duck-tales
38. Netflix fr-CA : https://partnerhelp.netflixstudios.com/hc/en-us/articles/42738240066835-French-Canada-Timed-Text-Style-Guide
39. AdNabu (zones sûres Meta) : https://blog.adnabu.com/meta-ads/meta-safe-zones/
40. Frame.io : https://blog.frame.io/2017/11/08/make-music-fit-your-video/

---

## 3. Vidéos libres pour tester l'éditeur (licences vérifiées)

Ces vidéos sont destinées aux tests internes seulement.
- Si on publie un résultat, il faut créditer l'auteur.
- Avec une licence « SA », il faut en plus partager le résultat sous la même licence.
- De toute façon, on ne met pas ces personnes dans une pub.

**Parole face caméra / entrevues, en français :**

| Vidéo | Contenu | Durée | Qualité | Taille | Licence | Où |
|---|---|---|---|---|---|---|
| WIKITONGUES – Maxime speaking Québécois French | monologue face caméra, accent québécois | 5 min 56 | 1280×720 | ≈ 71 Mo (.webm) | CC BY-SA 4.0 | Wikimedia Commons ; .mp4 sur wikitongues.org |
| WIKITONGUES – Jacques and Yvette speaking Chiac | 2 personnes (acadien) | ? | ? | ? | CC BY-SA 4.0 | wikitongues.org / Commons |
| Interview de Tristan Nitot (version courte), MOOC CHATONS #1 | entrevue assise | 6 min 38 | 1080p | 174 Mo (720p : 81 Mo) | CC BY-SA | framatube.org (Framasoft) ; version longue de 37 min : 976 Mo |
| Entrevue de l'expédition Tapiskwan sipi 2019 – 04 (Louis-Jean Petiquay) | entrevue, Manawan (Québec) | 8 min 47 | 1920×1080 | 311 Mo | CC BY-SA 4.0 (Benoit Rochon) | Wikimedia Commons (11 autres fichiers de la série) |
| La Boîte à Médailles (Sport en France), par ex. Jordan Sepho | entrevues d'athlètes olympiques | 6-12 min | 1080p | ? | CC BY 3.0 (vérifiée par Commons) | Wikimedia Commons |
| TVA Nouvelles – « Paris2024 - Virginie Chénier » | entrevue d'une archère de Laval | 5 min 31 | 720p | ? | CC BY (YouTube, vérifiée par Commons) | Wikimedia Commons |
| Conférences JdLL 2025-2026 | conférences d'environ 1 h (test « longue vidéo → clips ») | ~58 min | 720p | ~190 Mo | CC BY-SA | videos-libr.es (PeerTube) |
| NASA SVS – Artemis II, entrevues « soundbites » séparées par des claps | réponses brutes, en anglais | 8 min 26 / 8 min 37 | 1080p | ? | domaine public (pas de pub avec ces personnes) | svs.gsfc.nasa.gov/14934 |

**Immobilier (mode visuel) — Pexels :**
- **Kindel Media, « Video of a House Interior »** (7578540) et plans voisins (7578541 à 7578552) :
  - intérieurs + extérieur ;
  - même créateur et numéros qui se suivent, donc probablement le même tournage ;
  - 4K, environ 16 s chacun.
- **MART PRODUCTION, « A Family and a Female Real Estate Agent Visiting a House »** (7347877) et série : courtière + famille, vertical 2160×3840, 18 s.
- **Curtis Adams, « Empty Living Room with Hardwood Floors and a Fireplace »** (19228172) : 4K, 21 s.

**Limite honnête** : la recherche n'a trouvé aucun « rush de pub » brut en français avec plusieurs prises, comme ceux de l'utilisateur.
- Les plus proches : Maxime (monologue brut) et les entrevues Tapiskwan et Framasoft.
- Pour tester le dérushage, les vrais rushs de l'utilisateur restent le meilleur test.

---

## 4. Banques de plans de coupe utilisables dans des pubs

| Banque | Pub permise | Crédit obligatoire | Compte requis | Attention |
|---|---|---|---|---|
| **Pexels** | oui | non | non | pas de personne reconnaissable sous un mauvais jour ; ne pas laisser croire qu'une personne ou une marque recommande le produit ; pas de revente telle quelle |
| **Coverr** | oui | non | non | pas de revente ; interdit pour entraîner une IA |
| **Pixabay** | oui | non | oui, pour la pleine qualité | personnes reconnaissables, marques |
| **Mixkit** | selon le clip | non | non | deux licences : « Free » (pub permise) ou « Restricted » (usage personnel seulement ; c'est le cas du clip « A lot of cash over a rotating background ») |

**Sources écartées pour les pubs :**
- **ESA** : usage commercial interdit.
- **Videvo** : redirige vers Freepik, licence illisible.
- **Service audiovisuel de l'UE** : réservé à l'information et à l'éducation ; les personnes privées demandent une autorisation.
- **NASA et DVIDS** : domaine public, mais pas de pub avec des astronautes ou militaires reconnaissables ; DVIDS demande un compte.
- **EditStock** : pratique seulement, aucune production diffusée.
- **RawFootage Lab** : liens YouTube, pratique seulement.
- **YouTube** : on ne télécharge pas depuis YouTube ; pour une vidéo CC BY, prendre la copie de Wikimedia Commons.

Non vérifié (recherche arrêtée) :
- le filtre « Creative Commons » de YouTube en français ;
- archive.org (le moteur de recherche renvoyait une erreur) ;
- les vidéos d'événements.
