# Direction créative V2 — SPEC du socle (architecte)

Date : 30 septembre 2026 · Projet : `D:\Tools\editeur_sami` · Copie d'avant ce travail : `docs/direction-creative-v2/avant/`.

Ce document est le **contrat** entre l'architecte et les cinq agents qui construisent en parallèle les fonctions du §8
de `docs/PASSATION-CLAUDE-DIRECTION-CREATIVE-V2.md` : **notes**, **banque**, **vecteurs**, **chorégraphie**, **passage**.
Le socle décrit ici est **déjà codé et testé** (§10). Chaque agent n'écrit que dans ses fichiers (§8). Toute autre
modification passe par une demande au lead (§12).

---

## 1. Principes (valent pour tous)

1. **Chaque décision automatique a une raison** (`raison`, `reason`, `creativeReason`) et reste modifiable.
2. **Ce que le monteur a touché ou verrouillé n'est jamais écrasé** par une passe automatique : changement de style,
   relecture de sobriété, galerie, IA (`refresh_ai`), cerveau créatif, chorégraphie, « Refaire ce passage ».
   Règle unique : `engine/editeur/verrous.py` (§4).
3. **Les anciens reels sans les nouveaux champs fonctionnent à l'identique** (vérifié : 8 calculs de `timeline.ts`
   identiques à la copie d'avant sur 13 reels, §10).
4. **Sobriété** : un seul élément par-dessus l'image à la fois, rien sur l'accroche sauf le bandeau — s'applique à tout
   élément **automatique**, y compris les nouveaux (vecteurs, mouvements). Les éléments protégés comptent pour les
   chevauchements : les automatiques s'écartent d'eux.
5. **Notes et dessins de révision n'apparaissent JAMAIS dans l'export** : la composition Remotion ne les lit pas, et
   l'interface les retire des propriétés du lecteur (`REVIEW_KEYS`).
6. Tout le texte visible est **en français simple** (utilisateur : entrepreneur québécois, ~20 pubs/jour, pas monteur).
7. Local seulement : aucun téléchargement, aucune API en ligne. Tests courts, sur copies (§10).

---

## 2. Modèle de données (tout est facultatif, rétrocompatible) — `remotion/src/types.ts`

### 2.1 Verrou générique

```ts
type Lockable = {locked?: boolean; manual?: boolean};
```
- `locked: true` : **verrouillé** par le monteur (cadenas `LockToggle`).
- `manual: true` : **retouché ou posé à la main** (posé par l'interface à chaque retouche : `touched()` de `lock.tsx`).
  `edited: true` (scènes du style, ancien nom) vaut `manual`.
- **protégé = locked OU manual OU edited.** Porté par : `Graphic`, `Broll`, `StyleScene`, `VectorItem`, `SfxExtra`,
  `Cue`, et en bloc par `banner.locked`, `creativePlan.locked`, `choreography.locked`, `Clip.locked` (mots en couleur et
  emojis du plan figés).

### 2.2 Ancre (notes et dessins)

```ts
type Anchor = {clip: string; src: number; sig: string; source?: string; image?: string};
```
- `clip` : id du plan ; `src` : **secondes dans la prise du son du plan** (`clip.source`), pas dans le montage ;
  `sig` : `clip.signature` à la création ; `source` : `clip.source` (prise) ; `image` : prise affichée
  (angle multicam sinon la prise).
- Le temps du montage se **recalcule** toujours depuis l'ancre (`resolveAnchor`) : il suit les coupes, le déplacement
  des plans et les vitesses. Si le passage a été coupé, ou si la prise du plan a changé, le résultat est **null** :
  la note devient « orpheline » et l'interface le dit (jamais de pointage silencieux ailleurs).

### 2.3 Notes — `reel.notes?: Note[]` (≤ 500)

```ts
type Note = {id; t /* s du montage, cache */; anchor: Anchor; end?: number; endAnchor?: Anchor; text /* ≤ 2000 */;
  statut: 'ouverte' | 'traitee' | 'resolue'; auteur; cree; modifie /* ISO, ≤ 40 car. */;
  contexte: {titre; style; format; duree; phrase? /* mots dits à cet instant, ≤ 200 car. (lead) */} /* au moment de la note */;
  meta?: object /* ≤ 2 Ko */};
```
`t` est un cache : à la relecture, `resolveAnchor(reel, n.anchor)` fait foi (mettre `t` à jour si différent).
Souvenir du passage : `contexte.phrase` (les notes écrites avant l'intégration l'avaient dans `meta.phrase` : encore lu).

### 2.4 Dessins — `reel.annotations?: Annotation[]` (≤ 500 ; ≤ 2000 points chacun ; ≤ 200 000 en tout)

```ts
type Annotation = {id; noteId?; outil: 'crayon' | 'fleche' | 'cercle' | 'surligneur'; couleur /* #RRGGBB[AA] */;
  epaisseur /* px pour un petit côté de 1080 */; points: [x, y][] /* COORDONNÉES NORMALISÉES DE LA PRISE anchor.image */;
  anchor: Anchor; duree /* s */; masquee?: boolean; meta?};
```
Les points sont dans le repère **de la prise** (0..1 de l'image source), pas de l'écran : ils restent sur le même pixel
en 9:16, 16:9, 4:5 et 1:1, et suivent le cadrage qui accompagne le sujet (§3). Affichés **seulement** dans le calque de
l'application (`AnnotationOverlay`), jamais par Remotion. Un dessin ne devient un élément de l'export que si le
monteur le convertit explicitement (ex. en vecteur) — décision de l'agent notes, avec un bouton clair.

### 2.5 Vecteurs — `reel.vectors?: VectorItem[]` (≤ 200)

```ts
type VectorItem = Lockable & {id; asset /* chemin relatif à assets/ du SVG : 'banque/vecteurs/<nom>.svg' */;
  at; duration; x; y /* centre, 0..1 de l'image */; w /* largeur, part du PETIT CÔTÉ min(W, H) (lead) */; rotation /* ° */; opacite /* 0..1 */;
  couleurs: {principale; secondaire; contour} /* #hex ou null = couleurs de la charte / du style */;
  couleursManuelles: boolean /* true : la charte ne recolore plus */; anim: {entree; sortie} /* types de CueMove */;
  auto?; raison?; suggested? /* retiré par la sobriété : proposition non affichée */; sobriete?; meta?};
```

### 2.6 Chorégraphie — `reel.choreography?: Choreography` (≤ 1000 mouvements)

```ts
type Choreography = {version: number; cues: Cue[]; locked?: boolean; meta?: {resume?; rythme?; bpm?} /* ≤ 2 Ko */};
type Cue = {id; cible: {type: 'graphics' | 'design' | 'broll' | 'vector' | 'caption' | 'banner'; id};
  at; duree /* COPIE du temps de la cible, pour la piste */; entree: CueMove; sortie: CueMove;
  sync: {sur: 'mot' | 'temps' | 'battement'; ref: string | number | null}; raison; auto: boolean; locked: boolean;
  desactive?: boolean; manual?: boolean; meta?};
type CueMove = {type: 'fondu' | 'glisse' | 'zoom' | 'pop' | 'trace' | 'aucune'; direction?: 'gauche' | 'droite' | 'haut' | 'bas' | null;
  duree /* 0..10 s */; courbe: 'douce' | 'rapide' | 'rebond' | 'lineaire'};
```
- **Cibles** : `graphics`/`broll`/`vector` → id de l'élément ; `design` → id de la scène (`styleScenes`) ;
  `caption` → `captionCueId(1er mot de la page)` = `"<clip>:<index>"` ; `banner` → `"banner"`.
- **Le temps de la cible fait foi** (`at`/`duration` de l'élément ; scènes : mot d'ancrage). `cue.at/duree` sont un cache
  recalculé par `choregraphie.py`. Déplacer un mouvement dans la piste = déplacer l'élément (et le marquer `manual`).
- Le mouvement ne décide que **la manière** d'entrer/sortir (type, direction, durée, courbe) et sa synchro. Il
  s'ajoute à l'animation propre de l'élément ; `aucune` = animation d'origine seule.

### 2.7 Bruitages posés un par un — `reel.sfx.extra?: SfxExtra[]` (≤ 500)

```ts
type SfxExtra = Lockable & {t; name; reason?; creative?; id?; gain? /* 0..4 */; auto?};
```
`name` : nom court d'un fichier de `assets/sfx/editeur/` (sans extension, comme avant) **ou** chemin relatif à `assets/`
(`sfx/kenney/…/x.ogg`, `banque/sons/x.wav`). `sfxFile()` retire tout `..`. Les bruitages ne jouent que si
`sfx.enabled` est vrai (inchangé).

### 2.8 Autres champs touchés

`banner.locked`, `creativePlan.locked` (déjà lu par `creative.py` : plan ni recalculé ni audité), `Clip.locked`,
`StyleScene.locked`. Constante `REVIEW_KEYS = ['notes', 'annotations']` (retirées des props du lecteur).

---

## 3. Fonctions pures — `remotion/src/timeline.ts` (n'importe que des TYPES)

| Fonction | Rôle |
|---|---|
| `anchorAtTime(reel, t) → Anchor \| null` | ancre de l'instant t (plan sous la tête de lecture) ; null si montage vide |
| `resolveAnchor(reel, anchor, segs?) → {t, clip, exact} \| null` | où tombe l'ancre ; `exact=false` : même moment de la même prise trouvé dans un autre plan |
| `outputTimeOfAnchor(reel, anchor) → number \| null` | temps du montage, ou null (passage coupé, prise changée) |
| `sourceRectAt(reel, t, format?) → SourceRect \| null` | partie de la prise visible à t (`x, y, w, h` normalisés de la prise, `source`, `tSrc`, `scale`) avec le cadrage, les zooms et l'angle de l'aperçu/export ; `format` = `'9:16'…` ou `[w, h]` |
| `sourceToOutput(rect, [u, v])` / `outputToSource(rect, [x, y])` | point prise ↔ point de l'image (0..1) |
| `annotationWindow(reel, a) → [début, fin] \| null` | instants d'affichage d'un dessin |
| `annotationOutput(reel, a, t, format?) → points \| null` | points du dessin dans l'image ; null si l'image montre une autre prise que `anchor.image` |
| `segmentZoom(reel, seg, next, total, local)` | échelle d'un plan ; **seule implémentation**, utilisée par `SegmentVideo` (Reel.tsx) et `sourceRectAt` |
| `captionCueId({clip, index})` | id de chorégraphie d'une page de sous-titres |
| `sfxFile(name)` | nom court ou chemin sous `assets/` (jamais `..`) ; `sfxEvents` applique `gain` |

Limite : `sourceRectAt` décrit la piste principale (V1). Pendant un plan de coupe plein écran, un dessin reste lié à V1.
Mode Comparatif (écran partagé) non pris en compte.

---

## 4. Moteur — `engine/editeur/verrous.py`

```python
is_locked(e) · is_manual(e) · protege(e)          # protege = locked or manual or edited
modifiable(e, auto)                                 # une passe peut-elle y toucher ? (auto = règle propre à la passe)
partager(items) -> (proteges, libres)
cle(e)                                              # id, sinon « t|nom » (bruitage sans id)
fusionner(anciens, nouveaux)                        # liste recalculée : protégés gardés, nouveaux de même id écartés
garder_cues(anciens, nouveaux)                      # idem pour les mouvements, + même cible qu'un protégé = écarté
plan_verrouille(reel) · choregraphie_verrouillee(reel)
instantane(reel, plage=None, temps=None) · restaurer(reel, snap)
with sous_protection(reel, plage=None, temps=None): ...   # filet de sécurité
```
**Deux niveaux** : (1) chaque passe demande `protege()` avant de toucher un élément ; (2) `sous_protection` photographie
tout ce qui est protégé (listes `graphics`, `broll`, `styleScenes`, `vectors`, `sfx.extra`, `choreography.cues`, blocs
verrouillés `banner`/`creativePlan`/`choreography`, mots et emojis des plans verrouillés, et **toujours** `notes` et
`annotations`) puis le remet **à l'identique** après la passe, même si elle l'avait retiré ou changé.
Avec `plage=(début, fin)`, **tout ce qui est hors de la plage** est aussi remis à l'identique (éléments, bruitages,
mouvements, mots en couleur, emojis, `hlAuto` des plans entièrement hors plage). Un élément qui chevauche une borne
compte comme « dans la plage ».

**Branché dans** (déjà fait) :
- `sobriete.relire(reel, template, seg, tout, plage=None)` : un protégé n'est jamais retiré/déplacé, même `tout=True` ;
  vecteurs relus (retirés = `suggested`) ; bandeau verrouillé jamais éteint ; `plage` = seuls les automatiques qui
  touchent la plage bougent ; rapport `proteges` + phrase dans `resume`.
- `galerie.prepare(reel, use_ai, plage=None)` (scènes protégées gardées ; `plage` = seules les scènes libres ancrées dans
  la plage sont remplacées), `galerie.apply` (sous protection), `galerie.sober` (graphisme généré protégé gardé).
- `reel.apply_template` (sous protection ; bandeau verrouillé : le style ne l'allume ni ne l'éteint ; appelle ensuite
  `choregraphie.actualiser(reel, t)`), `reel.rehighlight` (plan verrouillé figé), `reel.refresh_ai` (aucune proposition
  sur un plan verrouillé ; bandeau verrouillé : propositions gardées), `reel.ensure` (instantané de l'ancien reel
  remis avant d'écrire).
- `creative.apply` (plan verrouillé intact ; sous protection ; bruitage créatif protégé gardé, sans doublon),
  `creative.direct_scenes` (aucun audit sur un plan verrouillé).

**Règle pour toute nouvelle passe automatique** (choregraphie.py, passage.py, banque automatique…) :
`with verrous.sous_protection(reel[, plage]):` autour de la passe + `protege()` avant chaque modification.

Hors socle : `auto._finish` (« Refaire » dans la Révision) repart d'un nouveau dérushage : l'ancien reel est gardé en
version, les verrous ne sont pas reportés (décision : nouveau montage complet).

---

## 5. Serveur — `app/server.mjs`

### 5.1 `PUT /api/reels/:p/:v`
`EDITABLE` += `notes`, `annotations`, `vectors`, `choreography`, `creativePlan`. Corps ≤ **20 Mo** (413 au-delà), lu
en UTF-8 d'un seul bloc (corrige les accents abîmés entre deux paquets). `validateV2(body)` **refuse (400, message en
français)** tout champ mal formé ou **inconnu** ; rien n'est écrit en cas de refus. Un champ absent du corps n'est pas
touché. Limites :

| Champ | Règles |
|---|---|
| `notes` | ≤ 500, ids uniques, texte ≤ 2000, statut ∈ {ouverte, traitee, resolue}, auteur ≤ 80, dates ≤ 40, contexte {titre ≤ 300, style ≤ 80, format ≤ 20, duree, phrase ≤ 200}, ancre complète |
| `annotations` | ≤ 500, 1..2000 points [x, y] ∈ [-2, 3], ≤ 200 000 points au total, outil ∈ 4, couleur #hex, épaisseur 0,5..200, durée 0,04..600 s |
| `vectors` | ≤ 200, `asset` = chemin sous assets sans `..`, x/y ∈ [-1, 2], w ∈ [0,01, 4], rotation ±360, opacité 0..1, couleurs #hex ou null |
| `choreography` | {version 1..100, cues ≤ 1000, locked?} ; cible ∈ 6 types ; entrée/sortie : type ∈ 6, courbe ∈ 4, direction ∈ 4 ou null, durée 0..10 |
| `creativePlan` | objet avec `version`, `locked` booléen, ≤ 512 Ko |
| `sfx.extra` | ≤ 500 ; `name` = nom court ou chemin sous assets sans `..` ; gain 0..4 |
| verrous | `locked`/`manual` booléens sur graphics, broll, styleScenes, banner |

Chaque note, dessin, vecteur, mouvement accepte `meta` (objet ≤ 2 Ko) pour un essai. **Un nouveau champ stable = une
demande au lead** (sinon 400 « champ inconnu »).

### 5.2 Routes V2 (toutes les requêtes non-GET exigent l'origine exacte `http://127.0.0.1:<port>`, sinon 403)

| Route | Effet |
|---|---|
| `GET /api/v2` | `{v2: true, champs, routes}` : sonde de l'interface (un serveur d'avant la V2 répond 404 → le panneau Notes demande de relancer) |
| `GET /api/banque?type=&categorie=&q=&format=&intensite=` | `python -m editeur banque catalogue …` → JSON de `banque.catalogue()` ; filtre invalide → 400 |
| `GET /api/banque/apercu/<id>` | lit `assets/banque/catalogue.json` (relu s'il change), envoie le fichier `apercu` de l'entrée **depuis assets/ seulement** ; 404 sinon |
| `POST /api/reels/:p/:v/passage` `{debut, fin}` | 0 ≤ début, fin − début ≥ 0,3 s ; version « avant refaire le passage » ; tâche `python -m editeur passage … --debut --fin` → `{id}` (202) |
| `POST /api/reels/:p/:v/choregraphie` `{tout?}` | version « avant chorégraphie » ; tâche `python -m editeur choregraphie …` (202) |

Les aperçus peuvent aussi être chargés directement : `/assets/<entree.apercu>` (déjà servi). Suivre une tâche :
`useJob` (`GET /api/jobs/<id>`), puis `reload()`.

---

## 6. Ligne de commande et modules bouchons — `engine/editeur/__main__.py`

```
python -m editeur banque catalogue [--type son --categorie x --q "mots" --format 9:16 --intensite 2] | construire | apercu <id>
python -m editeur passage <projet> --reel v1 --debut 12.0 --fin 18.5
python -m editeur choregraphie <projet> --reel v1 [--tout]
```
Sortie : une ligne JSON. Convention : une fonction pas encore livrée lève `NotImplementedError("… pas encore
disponible …")` → message clair, code 1, pas de trace. Signatures **définitives** (à remplir, ne pas renommer) :

- `banque.py` : `catalogue(filtres) -> {entrees, total, categories, filtres}` · `construire() -> {entrees, fichier}` ·
  `entree(id)` · `apercu(id) -> chemin relatif à assets/` · `element_pour_reel(entry, reel, at) -> (champ, element)`.
- `passage.py` : `refaire(project_dir, rid, debut, fin, options=None) -> {debut, fin, changes, resume}`.
- `choregraphie.py` : `actualiser(reel, template=None, plage=None)` (appelé par `apply_template` ; bouchon = ne fait
  rien) · `regenerer(project_dir, rid='script', libres=True) -> {cues, resume}`.

---

## 7. Points d'accroche déjà branchés

Contrat commun des composants d'interface : `app/ui/v2.ts` →
`V2Props = {reel, t, format, update, seek, pause, current, reload}` (+ `PassageRange`). `update(fn)` = historique
Ctrl+Z + sauvegarde automatique. Toujours le montage de l'éditeur, jamais la version B d'une comparaison.

| Point | Où c'est branché | Fichier (propriétaire) |
|---|---|---|
| `NotesPanel` | onglet principal **Notes** | `app/ui/revue.tsx` (notes) |
| `AnnotationOverlay` | div absolue **par-dessus le lecteur** (`.player-wrap` est `position: relative`), masquée en A/B | `app/ui/revue.tsx` (notes) |
| `NoteMarkers({reel, x, onSeek})` | règle de la timeline | `app/ui/revue.tsx` (notes) |
| `BanquePanel` | onglet **Plus → Banque** | `app/ui/banque.tsx` (banque) |
| `VectorPanel` | onglet **Plus → Graphismes**, sous les graphismes | `app/ui/vector-panel.tsx` (vecteurs) |
| `VectorLayer({reel, t, total, assetBase})` | `Reel.tsx`, au-dessus des graphismes, sous scènes/bandeau/sous-titres | `remotion/src/vectors.tsx` (vecteurs) |
| `ChoreoPanel` | onglet **Plus → Chorégraphie** | `app/ui/choreo-panel.tsx` (chorégraphie) |
| `ChoreoLane({reel, t, zoom, x, onSeek, update})` | ligne `.tl-row.tl-choreo` (24 px) de la timeline | `app/ui/choreo-lane.tsx` (chorégraphie) |
| `<Choreo reel cible t at duration>` + `cueFor`, `animateElement` | enveloppe DÉJÀ posée autour de chaque graphisme (`graphics.tsx`), scène (`design.tsx`), plan de coupe, bandeau et page de sous-titres (`Reel.tsx`) ; bouchon = rend les enfants tels quels | `remotion/src/choreo.tsx` (chorégraphie) |
| `RedoPassage({...V2Props, range, setRange})` | barre d'outils de la timeline ; la plage est dessinée (`.tl-range`) | `app/ui/passage.tsx` (passage) — version de départ fonctionnelle |
| `LockToggle`, `withLock`, `touched`, `isLocked` | **fonctionnel** : graphismes, scènes du style, plans de coupe, bruitages posés (Style → Bruitages), bandeau, plan créatif | `app/ui/lock.tsx` (architecte) |

Autres comportements du socle : glisser un graphisme, un plan de coupe ou un vecteur dans la timeline le marque
`manual` ; toute retouche d'un graphisme (panneau) ou d'un plan de coupe aussi ; les vecteurs apparaissent dans la
piste Graphismes (ocre) et se déplacent à la souris ; 🔒 devant un élément verrouillé.

Blocs CSS réservés dans `app/ui/styles.css` (écrire **uniquement entre ses deux marqueurs**) : `/* revue */ … /* fin revue */`,
`/* banque */ … /* fin banque */`, `/* vecteurs */ … /* fin vecteurs */`, `/* choregraphie */ … /* fin choregraphie */`,
`/* passage */ … /* fin passage */`.

---

## 8. Propriété des fichiers (après l'architecte)

| Agent | Fichiers (seul à les écrire) |
|---|---|
| **notes** | `app/ui/revue.tsx` ; CSS `/* revue */ … /* fin revue */` |
| **banque** | `engine/editeur/banque.py` ; `assets/banque/**` (nouveau) **sauf** `assets/banque/vecteurs/**` ; `app/ui/banque.tsx` ; CSS `/* banque */` |
| **vecteurs** | `remotion/src/vectors.tsx` ; `assets/banque/vecteurs/**` (SVG + fiches ; dossier partagé, seul cet agent y écrit) ; `app/ui/vector-panel.tsx` (nouveau) ; CSS `/* vecteurs */` |
| **chorégraphie** | `engine/editeur/choregraphie.py` ; `remotion/src/choreo.tsx` ; `app/ui/choreo-panel.tsx` ; `app/ui/choreo-lane.tsx` (Timeline.tsx ne fait que l'importer) ; CSS `/* choregraphie */` |
| **passage** | `engine/editeur/passage.py` ; `app/ui/passage.tsx` ; CSS `/* passage */` |

**Personne d'autre ne modifie** (demandes au lead) : `app/ui/App.tsx`, `app/ui/Timeline.tsx`, `remotion/src/Reel.tsx`,
`remotion/src/types.ts`, `remotion/src/timeline.ts`, `app/server.mjs`, `engine/editeur/__main__.py`, `reel.py`,
`galerie.py`, `sobriete.py`, `creative.py`, ni les fichiers du socle : `engine/editeur/verrous.py`, `app/ui/lock.tsx`,
`app/ui/v2.ts`, `remotion/src/graphics.tsx`, `remotion/src/design.tsx`, `app/ui/panels.tsx`, `panels2.tsx`,
`ajouter.tsx`, `design-panel.tsx`, le haut de `styles.css` (hors blocs réservés). Tests de chaque agent :
`docs/direction-creative-v2/tests/<agent>/` (nouveau dossier par agent). `REPRISE.md` : mis à jour par le lead.

---

## 9. Interfaces entre agents

### 9.1 Catalogue de la banque (`assets/banque/catalogue.json`, écrit par `banque.construire()`)

```json
{"version": 1, "entrees": [{
  "id": "son:whoosh-court",            // unique, [A-Za-z0-9_.:-]{1,120} (sert dans /api/banque/apercu/<id>)
  "type": "effet | son | vecteur | template",
  "nom": "Whoosh court", "categorie": "whoosh", "motsCles": ["transition", "rapide"], "intensite": 1,
  "formats": ["9:16", "16:9", "4:5", "1:1"],
  "apercu": "sfx/editeur/whoosh-court.wav",   // relatif à assets/ (image, son ou SVG) — jamais hors de assets/
  "fichier": "sfx/editeur/whoosh-court.wav",   // relatif à assets/, ou null (template)
  "licence": "CC0 1.0", "provenance": "Kenney.nl (assets/sfx/kenney/…/License.txt)" ,
  "params": {}                                  // selon le type, voir 9.2
}]}
```
Sources autorisées : `assets/sfx/editeur` (synthèse `sfxgen.py`, licence du fichier `LICENCE.txt`), `assets/sfx/kenney`
(CC0), `assets/music`, `assets/overlays`, polices, genres de graphismes (`chiffre`, `coches`, `carte`, `motgeant`,
`logo`) et de scènes existants, et ce qui est créé localement (SVG écrits à la main, sons de `sfxgen.py`).
**Licence et provenance obligatoires** pour chaque entrée. Les vecteurs sont lus par `banque.py` depuis
`assets/banque/vecteurs/<nom>.svg` + fiche `<nom>.json` écrite par l'agent vecteurs :
`{nom, categorie, motsCles, intensite, licence, provenance, couleurs: {principale, secondaire, contour}, anim: {entree, sortie}}`.

### 9.2 « Ajouter » depuis la banque (dans `banque.tsx`, par `update()` ; même règle dans `banque.element_pour_reel`)

| type | élément créé | détails |
|---|---|---|
| `son` | `reel.sfx.extra.push({id, t, name: fichier, gain: params.gain ?? 1, reason: 'Banque : <nom>', manual: true})` | si `sfx.enabled` est faux : le dire et proposer de l'activer d'un clic (ne pas changer les autres réglages) |
| `vecteur` | `reel.vectors.push({id, asset: fichier, at: t, duration: params.duree ?? 2, x: .5, y: .35, w: params.largeur ?? .35, rotation: 0, opacite: 1, couleurs: {principale: null, secondaire: null, contour: null}, couleursManuelles: false, anim: fiche.anim, manual: true, raison: 'Banque : <nom>'})` | `null` = couleurs de la charte / du style |
| `template` | `reel.graphics.push({id, kind: params.kind, at: t, duration: params.duree, props: {...params.props, banque: id}, manual: true})` | `params.cible: 'styleScenes'` seulement si `reel.design.mode` : scène ancrée au 1er mot dit à partir de t (`timedWords`), `manual: true` |
| `effet` | selon `params.cible` : `'flash'` → `reel.flash = {enabled: true, kind}` ; `'effects'` → `reel.effects` (grain, vignette, étalonnage) ; `'vector'` → comme un vecteur | pas d'effet de transition « à une coupe précise » dans ce socle (demande au lead si besoin) |

### 9.3 Vecteurs (contrat SVG, pour la banque et la composition)
SVG autonome (viewBox, aucune ressource externe, aucun script). Couleurs **uniquement** par les variables CSS
`var(--v-principale, #…)`, `var(--v-secondaire, #…)`, `var(--v-contour, #…)` (valeur par défaut = couleur d'origine),
pour recolorer sans perdre les formes ni l'animation. Chemins à « tracer » : `pathLength="1"` + classe `v-trait`.
Recoloration automatique (quand `couleursManuelles` est faux et qu'une couleur vaut null) : principale = accent de la
charte (`brand.style.highlight`) sinon `design.accent` sinon `style.highlight` ; secondaire = `design.secondary` sinon
`brand.bannerBg` ; contour = `style.stroke`. Rendu identique dans l'aperçu et l'export (`${assetBase}/banque/vecteurs/…`
est servi dans les deux). Chaque vecteur est rendu dans `<Choreo cible={{type: 'vector', id}} …>`. Ignorer `suggested`.

### 9.4 Chorégraphie
- `choregraphie.py` produit les mouvements à partir du storyboard (`creativePlan.storyboard`), des mots
  (`montage.compute(reel)['words']`) et des temps forts ; chaque mouvement a une `raison` ; `garder_cues()` pour ne
  jamais écraser un mouvement protégé ; rien si `choreography.locked`.
- **Jamais deux éléments concurrents au même moment** : ne pas créer d'élément ; si des éléments automatiques se
  chevauchent, laisser `sobriete.relire` trancher (les mouvements des éléments retirés sont supprimés).
- `choreo.tsx` : pur, même rendu aperçu/export ; enveloppe sur `[at, at + entree.duree]` et
  `[at + duration − sortie.duree, at + duration]` avec les `at/duration` **passés par l'appelant** ; ne pas ajouter de
  décalage de mise en page (une enveloppe `AbsoluteFill` avec opacité/transform est permise).

### 9.5 « Refaire seulement ce passage » (`passage.py`)
```python
def fn(reel):
    seg = montage.compute(reel); temps = {(w['clip'], w['index']): w['start'] for w in seg['words']}
    with verrous.sous_protection(reel, (debut, fin), temps):
        galerie.prepare(reel, plage=(debut, fin))                  # si design.mode
        # mots en couleur : reel.reel_highlights(clips, …, only={plans touchés}, keep={mots hors plage}) puis mark_auto
        # graphismes.suggest(…) : ne garder que ceux dont [at, at+duration] touche la plage
        choregraphie.actualiser(reel, template, plage=(debut, fin))
        sobriete.relire(reel, template, seg, tout=False, plage=(debut, fin))
montage.update(project_dir, rid, fn)   # relit le reel juste avant d'écrire
```
Ne modifie **pas** le montage (prises, coupes, vitesses) : cela décalerait tout ce qui suit. Test obligatoire : tout ce
qui est avant et après la plage est identique octet pour octet (hors `sobriete` et `creativePlan.storyboard[].status`).

### 9.6 Notes
Créer : `anchorAtTime(reel, t)` (+ `endAnchor`), `contexte = {titre: reel.title, style: reel.template, format, duree}`.
Afficher : `resolveAnchor` ; null → « passage coupé ou prise changée » + bouton « rattacher ici ». Dessins :
`outputToSource(sourceRectAt(reel, t), point)` à l'enregistrement, `annotationOutput(reel, a, t)` à l'affichage.
`pause()` avant de dessiner ; `pointer-events: none` hors du mode dessin.

---

## 10. Tests (tous verts à la fin du socle)

| Test | Contenu |
|---|---|
| `node docs/direction-creative-v2/tests/test-timeline-v2.mjs` | 71 : ancres après coupe / plan déplacé / prise changée / plan dupliqué ; rectangle de la prise en 4 formats (même pixel que la transformation CSS de l'image, aller-retour) ; `segmentZoom` = ancien calcul ; bruitages de la banque ; 13 reels : 8 calculs identiques à `avant/` ; aucun fichier de la composition ne lit notes/dessins |
| `python ../docs/direction-creative-v2/tests/test-verrous.py` (depuis `engine/`) | 10 : verrous après changement de style (4 styles × 2 reels + aller-retour), plan créatif verrouillé, sobriété `tout=True/False`, galerie, plan verrouillé, filet de plage, ancien reel, `refresh_ai` / `ensure` sur copie |
| `node docs/direction-creative-v2/tests/test-serveur.mjs` | 46 : copie isolée du serveur (port 18797) ; champs valides, UTF-8, 20 refus + 413, origine exacte, routes bouchons, aperçu confiné à assets/ |

Et toujours : `node app/build.mjs` ; `remotion\node_modules\.bin\tsc -p tsconfig.verif.json` ; `node --check app/server.mjs` ;
`node --check plugins/editeur-sami/mcp/serveur.mjs` ; depuis `engine/` : `verification.py`, `test-galerie.py`,
`test-creative.py`, `test-sobriete.py` ; `node docs/galerie-styles/test-timeline.mjs`.

Tests obligatoires restant aux agents (§9 de la passation) : note retrouvée après réouverture (notes) ; dessin aligné
en 4 formats dans le vrai lecteur (notes) ; notes/dessins absents d'un export court de 2 s (notes) ; SVG multicolore
recoloré sans perte (vecteurs) ; charte qui recolore un template puis retouche gardée (vecteurs + banque) ; filtres et
aperçus de la banque (banque) ; pas deux éléments concurrents (chorégraphie) ; retouche verrouillée après une passe de
l'IA et un changement de style (chorégraphie) ; rien ne change hors de la plage (passage).

---

## 11. Limites et décisions

- Les champs V2 du serveur ne sont actifs qu'après un **redémarrage contrôlé** du vrai serveur 8790 (à faire par le
  lead) ; l'interface compilée fonctionne avec l'ancien serveur (les nouveaux champs sont alors ignorés à la sauvegarde).
- Dessins : piste principale seulement (pas le plan de coupe par-dessus, pas l'écran partagé du Comparatif).
- Emojis : non verrouillables un par un (le verrou d'un plan les fige).
- « Refaire » (Révision) = nouveau montage complet : verrous non reportés (version d'avant gardée).
- Pendant une tâche du moteur (passage, chorégraphie), une retouche faite dans l'interface peut être écrasée par
  l'écriture de la tâche si elle arrive juste avant la fin : l'interface se recharge à la fin de la tâche.
- `test-creative.py` lisait le vrai `projects/script1`, remis par l'utilisateur en « tech-application » : il prend
  désormais la copie Tech 3D de Vidéo 1 quand le vrai reel est dans un autre style.

## 12. Demandes au lead

Un agent qui a besoin d'un changement hors de ses fichiers (nouveau champ, nouvelle route, nouvel import dans
App/Timeline/Reel) l'écrit dans son `requests_for_lead` avec : fichier, changement exact, raison, test. Le lead
l'applique et relance les tests du §10.

---

## 13. Intégration du lead (30 septembre 2026, après les 5 agents)

Les cinq fonctions sont livrées et revues ; le lead possède désormais tous les fichiers. Changements de contrat :

- **Vecteurs** : `w` = part du **petit côté** de l'image (`min(W, H)`), comme les sous-titres et les graphismes. Identique à
  l'ancienne règle en 9:16, 4:5 et 1:1 (données existantes inchangées) ; en 16:9 un cercle posé en 9:16 ne dépasse plus
  l'image. Appliqué dans `vectors.tsx` (`vectorBox`), `choreo.tsx` (`placeOf`), `revue.tsx` (`toVector`), `banque.tsx` et
  `banque.py` (`taille_element`), libellé du panneau « % du petit côté ».
- **Notes** : `contexte.phrase` (≤ 200) remplace `meta.phrase` (encore lu : `phraseDe`). **Chorégraphie** : `meta` typé.
- **Serveur** : `GET /api/v2` (sonde sans ligne rouge dans la console) ; sortie de Python décodée en UTF-8 d'un seul bloc
  (`run()`) ; `/api/banque/apercu/<id>` décode l'identifiant (`son%3Ax`) puis le vérifie.
- **Graphismes posés ou verrouillés par le monteur** (`manual` / `locked`) : visibles aussi dans un style avec habillage
  (`Reel.tsx`, `userGraphic`) ; ils comptent comme l'élément par-dessus l'image (scènes du style masquées à cet instant).
  Même règle dans `choregraphie.cibles`. La banque ne dit plus « ce style masque les graphismes ». Les anciens graphismes
  sans `manual` restent masqués comme avant (aucun reel réel n'en a).
- **Couleur des modèles** : `props.color` (choisie à la main) sinon l'accent du style / de la charte, pour chiffre, cases
  cochées, carte et mot géant (`graphics.tsx`, `tint`) ; réglage « Couleur » + « 🎨 Couleur de la charte » dans Plus →
  Graphismes. Scènes « papier » et « avant/après » : `g.color` vide → accent (plus de bordure invisible).
- **Plan verrouillé** : bouton cadenas dans l'onglet Plan (« Figer les mots en couleur et les emojis de ce plan »).
- **Montage automatique** (`auto._finish`) : crée la chorégraphie (`actualiser(creer=True)`) après la relecture.
- **Ligne de commande** : un refus de `passage` (plage, montage absent) sort en phrase claire (plus d'« Erreur inattendue »,
  rien dans `erreurs.log`) ; un échec de `node segments.mjs` n'est plus présenté comme un problème FFmpeg.
- **Export** : `render.mjs` retire `notes` et `annotations` des propriétés envoyées à Remotion.
- **Interface** : onglet du menu « Plus » ouvert = son nom seul (« Chorégraphie ▾ ») ; bouton jaune qui reste jaune au survol
  (règle globale) ; graphisme ajouté à la main = `manual`.
- **Tests** : `tests/test-v2.mjs` (tout, avec le tableau des 11 tests du §9 de la passation) ; `tests/integration/` (reel
  avec toutes les fonctions à la fois, 4 exports courts, interface dans un Chrome sans fenêtre). Voir `RESULTAT.md`.
