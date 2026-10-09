/** Un mot de la transcription. hl = en couleur ; hide = masque dans les sous-titres ; cut = retire du montage. */
export type Word = {w: string; start: number; end: number; hl: boolean; hide: boolean; cut?: boolean;
	/** Texte d'origine de la transcription quand la relecture d'orthographe (engine/editeur/orthographe.py) l'a corrige. */
	asr?: string};

/** Un plan du montage (temps en secondes dans la prise d'origine). */
export type Clip = {
	id: string;
	block: string;
	signature: string;
	source: string;
	in: number;
	out: number;
	tighten: boolean;
	choice?: number;
	words: Word[];
	emojis?: [number, string][];
	/** J-cut : le son du plan commence avant son image (s). */
	audioLead?: number;
	/** L-cut : le son du plan continue sous le plan suivant (s). */
	audioTail?: number;
	/** Couleur : harmonisation automatique + reglages manuels (exposition en diaphragmes, temperature -1..1). */
	color?: {auto: boolean; exposure: number; temperature: number};
	/** Vitesse de lecture (1 = normale, 0.5 = ralenti, 2 = accelere). Le son suit (plans muets conseilles). */
	speed?: number;
	/** Plan sans son (immobilier, evenementiel : seule la musique joue). */
	mute?: boolean;
	/** Multicamera : angle affiche (autre prise synchronisee) ; le son reste celui de `source`. */
	angle?: string | null;
	/** V2 : mots en couleur et emojis de ce plan figes (aucune proposition ni relecture automatique). */
	locked?: boolean;
};

// ---------- Direction creative V2 : verrous, notes, dessins, vecteurs, choregraphie (voir docs/direction-creative-v2/SPEC.md) ----------
/** Tout element peut etre verrouille (locked : aucune passe automatique n'y touche) ; manual = retouche a la main
 * (meme protection que locked, pose automatiquement par l'interface). */
export type Lockable = {locked?: boolean; manual?: boolean};
/** Ancre d'un instant du montage dans la PRISE : resiste aux coupes, au deplacement des plans et aux formats.
 * clip : id du plan ; src : secondes dans la prise du son du plan (clip.source) ; sig : clip.signature a la creation ;
 * source : clip.source a la creation (prise) ; image : prise affichee a la creation (angle multicamera sinon source). */
export type Anchor = {clip: string; src: number; sig: string; source?: string; image?: string};
export type NoteStatut = 'ouverte' | 'traitee' | 'resolue';
/** Note de revision rattachee a un instant (t = temps du montage, cache ; l'ancre fait foi). */
export type Note = {id: string; t: number; anchor: Anchor; end?: number; endAnchor?: Anchor; text: string; statut: NoteStatut;
	auteur: string; cree: string; modifie: string;
	/** Contexte du montage au moment de la note (phrase : quelques mots dits a cet instant, souvenir du passage, <= 200 car.). */
	contexte: {titre: string; style: string; format: string; duree: number; phrase?: string};
	/** Champs experimentaux (<= 2 Ko en JSON) : tout nouveau champ stable passe par le SPEC. */
	meta?: Record<string, unknown>};
export type AnnotationTool = 'crayon' | 'fleche' | 'cercle' | 'surligneur';
/** Dessin de revision : points en coordonnees NORMALISEES DE LA PRISE (anchor.image, 0..1) : reste aligne dans tous
 * les formats. Affiche seulement dans l'apercu de l'application, JAMAIS dans l'export Remotion. */
export type Annotation = {id: string; noteId?: string; outil: AnnotationTool; couleur: string;
	/** Epaisseur en px pour un petit cote de 1080 px. */
	epaisseur: number; points: [number, number][]; anchor: Anchor; duree: number; masquee?: boolean; meta?: Record<string, unknown>};
/** Vecteur de la banque (SVG recolorable) pose sur l'image. x, y : centre (part de la largeur / hauteur de l'image) ;
 * w : largeur, part du PETIT COTE de l'image (min(largeur, hauteur)) : meme taille apparente dans les 4 formats. */
export type VectorItem = Lockable & {id: string; asset: string; at: number; duration: number; x: number; y: number; w: number;
	rotation: number; opacite: number; couleurs: {principale: string | null; secondaire: string | null; contour: string | null};
	/** true : couleurs choisies a la main (la charte ne les recolore plus). */
	couleursManuelles: boolean; anim: {entree: string; sortie: string};
	auto?: boolean; raison?: string;
	/** Retire par la relecture du monteur : proposition non affichee (comme Graphic.suggested). */
	suggested?: boolean; sobriete?: string; meta?: Record<string, unknown>};
export type CueTargetType = 'graphics' | 'design' | 'broll' | 'vector' | 'caption' | 'banner';
/** Cible d'un mouvement : graphics/broll/vector -> id de l'element ; design -> id de la scene (styleScenes) ;
 * caption -> `${clip}:${index}` du 1er mot de la page ; banner -> 'banner'. */
export type CueTarget = {type: CueTargetType; id: string};
export type CueMove = {type: 'fondu' | 'glisse' | 'zoom' | 'pop' | 'trace' | 'aucune'; direction?: 'gauche' | 'droite' | 'haut' | 'bas' | null;
	duree: number; courbe: 'douce' | 'rapide' | 'rebond' | 'lineaire'};
/** Un mouvement de la choregraphie. at/duree : copie du temps de la cible (la cible fait foi), pour la piste. */
export type Cue = {id: string; cible: CueTarget; at: number; duree: number; entree: CueMove; sortie: CueMove;
	sync: {sur: 'mot' | 'temps' | 'battement'; ref: string | number | null}; raison: string; auto: boolean; locked: boolean;
	desactive?: boolean; manual?: boolean; meta?: Record<string, unknown>};
/** meta : resume du moteur (resume, rythme, bpm), <= 2 Ko. */
export type Choreography = {version: number; cues: Cue[]; locked?: boolean; meta?: {resume?: string; rythme?: string; bpm?: number | null} & Record<string, unknown>};
/** Bruitage pose a la main, par la banque ou par le cerveau creatif. name : bruitage de assets/sfx/editeur (sans extension)
 * ou chemin relatif a assets/ (« sfx/kenney/…/x.ogg », « banque/sons/x.wav »). gain : correction de volume (banque). */
export type SfxExtra = Lockable & {t: number; name: string; reason?: string; creative?: boolean; id?: string; gain?: number; auto?: boolean};

/** Une prise : media optimise (apercu + export), echantillons [t, cx, cy, luma visage, r, g, b]. */
export type Source = {
	name: string; proxy: string; path: string; duration: number; samples: number[][]; roomtone?: string | null;
	/** Taille du media optimise (cadre d'origine conserve). */
	width?: number; height?: number;
	/** Recadrage : position lissee de la personne qui parle [t, cx, cy, largeur du visage]. */
	track?: number[][];
	/** Multicamera : debut de la prise dans le temps commun du groupe (s). */
	sync?: {group: string; offset: number};
	/** 'rush' (defaut) ou 'broll' (plan de coupe d'un dossier media/broll). */
	kind?: 'rush' | 'broll';
	/** Image fixe (plan de coupe photo) : lent zoom avant a l'affichage. */
	still?: boolean;
	/** Voix debruitee (apercu) : meme traitement que l'export. */
	voice?: string;
	/** Media pris dans une banque libre : source, auteur, licence (fiche .json a cote du fichier). */
	credit?: {provider: string; author: string; url: string; license?: string};
};

export type Segment = {clip: string; source: string; src_in: number; src_out: number; out_start: number; index: number; speed?: number};

/** Plan de coupe (piste V2) : image d'une autre prise par-dessus le montage, sans son.
 * mode : 'plein' (plein ecran) ou 'encadre' (cadre a bord blanc sur la moitie droite, pour un media d'une autre orientation). */
export type Broll = Lockable & {id: string; source: string; in: number; at: number; duration: number; word?: string; mode?: 'plein' | 'encadre';
	/** Pose par le montage automatique (la relecture du monteur peut le retirer) ; motif et confiance de l'IA. */
	auto?: boolean; reason?: string; confidence?: string};

/** Un media candidat pour un emplacement de plan de coupe (bibliotheque locale). */
export type BrollCandidate = {source: string; name: string; t: number; score: number; confidence?: 'haute' | 'moyenne' | 'faible'; personne?: number};
/** Proposition de plan de coupe non inseree (broll.suggest en mode auto : at/duration/word/context/reason/pourquoi/candidates/externes ; sobriete._retirer : source/in/at/duration/word/id/raison). */
export type BrollSuggestion = {at: number; duration: number; word: string; context?: string; reason?: string; pourquoi?: string; raison?: string; candidates?: BrollCandidate[]; externes?: unknown[]; source?: string; in?: number; id?: string};

/** Element graphique anime (piste Graphismes). */
export type GraphicKind = 'chiffre' | 'coches' | 'carte' | 'motgeant' | 'logo';
export type Graphic = Lockable & {id: string; kind: GraphicKind; at: number; duration: number; props: Record<string, any>; suggested?: boolean;
	/** Pose par le montage automatique ; confiance et motif de l'IA ; note de la relecture du monteur (sobriete). */
	auto?: boolean; confiance?: 'haute' | 'moyenne'; raison?: string; sobriete?: string};

/** Charte d'un client : couleurs, police, logo, fin de video. */
export type Brand = {
	client: string; name: string; logo: string | null; logoPosition: 'haut-gauche' | 'haut-droite' | 'bas-gauche' | 'bas-droite'; logoSize: number; logoOpacity: number;
	bannerBg: string; bannerColor: string;
	/** Police et couleurs des sous-titres imposees par la charte. */
	style?: {font?: string; color?: string; highlight?: string; stroke?: string};
	outro: {enabled: boolean; text: string; duration: number};
};

/** Propositions de l'IA en attente de validation par le monteur. */
export type Suggestions = {banners: string[]; words: Record<string, number[]>; emojis: Record<string, [number, string][]>;
	/** Emplacements de plans de coupe proposes mais non inseres (avec leur « pourquoi »). */
	broll?: BrollSuggestion[];
	/** Corrections de transcription proposees par Claude (« Relancer l'IA », engine/editeur/cerveau_claude.py) : mot sans ponctuation. */
	corrections?: {clip: string; i: number; avant: string; apres: string; raison?: string}[]};

export type CaptionPreset = 'impact' | 'karaoke' | 'boite' | 'minimal' | 'neon' | 'geant' | 'elegant' | 'bulle';
export type Style = {
	preset: CaptionPreset | string;
	font: string;
	weight: number;
	uppercase: boolean;
	size: number;
	color: string;
	highlight: string;
	stroke: string;
	strokeWidth: number;
	position: number;
	maxWords: number;
	pop: boolean;
};
export type Sfx = {
	enabled: boolean;
	transition: string | null;
	highlight: string | null;
	highlightGap: number;
	cta: string | null;
	start: string | null;
	volume: number;
	/** Bruitages places a la main (conseils de rythme, graphismes, banque) ou par le cerveau creatif : temps du montage. */
	extra?: SfxExtra[];
	/** Sons de coupe varies (absent = oui) : chaque coupe, entree d'interface, mot fort, preuve prend un son different de la
	 * famille ; false = toujours les sons du style, exactement comme avant. */
	varier?: boolean;
	/** Famille de sons choisie (id de styles/sons-transitions.json) ; absente ou « auto » = celle du style. */
	famille?: string;
	/** Reserve de la famille (32 au plus) : name comme sfxFile ; pic = secondes entre le debut du fichier et son maximum (pose
	 * SUR la coupe) ; gain 0-4 ; role transition | interface | apparition | mot-fort | impact | cta (absent = transition).
	 * Absente : reserve par defaut voisine du son du style (SFX_POOL_DEFAUT de timeline.ts). */
	pool?: {name: string; pic?: number; gain?: number; role?: string}[];
};
export type CreativeBeat = {id: string; role: 'accroche' | 'probleme' | 'solution' | 'preuve' | 'explication' | 'cta'; label: string;
	start: number; end: number; clip: string; index: number; sentences: string[]; evidence: string; visualIntent: string; intensity: number};
export type StoryboardShot = {id: string; beat: string; role: CreativeBeat['role']; start: number; end: number; purpose: string; evidence: string;
	shot: string; engine: 'prise-originale' | 'remotion-ui' | 'remotion-typographie' | 'remotion-graphisme' | 'blender'; composition: string;
	asset: {kind: string; status: string; brief: string} | null; fallback: string; reason: string; status: 'planifié' | 'prêt' | 'rendu' | 'à revoir'};
/** locked : plan fige par le monteur (aucun recalcul au changement de style, ni audit du storyboard). */
export type CreativePlan = {version: number; enabled: boolean; locked?: boolean; source: string; summary: string;
	direction: {rhythm: string; wordsPerSecond: number; visualGrammar: string; density: number; accent?: string; objective: string; title: string};
	beats: CreativeBeat[]; storyboard: (StoryboardShot & {execution?: string[]})[]; assets: {shot: string; kind: string; status: string; brief: string; required: boolean}[];
	sound: {arc: string; music?: string | null; cues: {t: number; name: string; reason: string}[]};
	guardrails: string[]; quality: {confidence: number; coverage: number; hasHook: boolean; hasSolution: boolean; hasProof: boolean; hasCta: boolean}};
export type DesignMode = 'hormozi' | 'documentaire' | 'luxe' | 'vhs' | 'comparatif' | 'infographie' | 'tech' | 'collage' | 'editorial' | 'produit';
export type Design = {mode?: DesignMode; enabled?: boolean; accent?: string; secondary?: string; title?: string; density?: number;
 productImage?: string; productModel?: string; productVideo?: string; date?: string; suppressExtras?: boolean; cinematic?: boolean};
export type StyleScene = {id: string; kind: 'metric' | 'notification' | 'comparison' | 'keyword' | 'paper' | 'product' | 'dashboard' | 'flow' | 'cta' | 'list';
 clip: string; index: number; length?: number; text: string; secondary?: string; duration: number; x: number; y: number;
 /** Liste (kind 'list') : indice du mot (même plan) où chaque élément est dit, dans l'ordre text, secondary 1, 2... */
 items?: number[];
 /** Bouton (kind 'cta') : indice du mot (même plan) où l'offre est dite, avant le bouton. La carte entre sur l'offre
  * (badge seul), le bouton la rejoint sur son mot. */
 lead?: number;
 /** Bouton unique (kind 'cta') tenu de la 1re demande jusqu'à la fin : indice du mot où l'offre (secondary) est dite APRÈS
  * le bouton, dans le plan offerClip (par défaut le même plan). Le badge de l'offre entre au-dessus du bouton sur ce mot ;
  * sa place est gardée dès l'entrée (le bouton ne bouge pas). */
 offer?: number; offerClip?: string;
 scale: number; rotation: number; color: string; hidden?: boolean; manual?: boolean; edited?: boolean; locked?: boolean;
 /** Note de la relecture du monteur (sobriete) : pourquoi la scene a ete gardee, deplacee ou masquee. */
 sobriete?: string; creativeBeat?: string; creativeRole?: CreativeBeat['role']; creativeReason?: string; creativeShot?: string};
/** Personne detouree d'un plan (cache assets/detourage). Moteur RVM : engine, score moyen (0-1), quality (qualite.json)
 * et fallback = plages [debut, fin] en secondes DANS LA PRISE ou le masque est juge mauvais : le rendu y montre la prise
 * d'origine assombrie aux couleurs du studio au lieu de la personne detouree. */
export type Cutout = {file: string; start: number; end: number; width: number; height: number; source: string; proxy: string; frames?: string; fps?: number; count?: number;
	engine?: string; score?: number; quality?: string; fallback?: [number, number][];
	/** Lumière principale de la prise (mesurée sur le visage, detourage.py) : side -1 = vient de la gauche de l'image,
	 * 1 = de la droite ; k = écart de lumière entre les deux moitiés du visage (0 = face, 1 = très latérale). */
	light?: {side: number; k: number};
	/** Objet fixe du décor d'origine au premier plan (table) qui cachait la personne : polygone [[x, y], ...] (0-1, cadre de
	 * la prise). Le studio y pose un bureau sombre au premier plan (le bras passe derrière, comme dans la vraie prise). */
	occluder?: [number, number][]; occluderFrom?: string;
	/** Bord de la table image par image quand la caméra dérive (detourage.occultant_confirme) : [t de la prise, a, b], a et b =
	 * coordonnée libre (sur le bord de l'image) des deux sommets de `occluder` qui ne sont pas des coins de l'image. */
	occluderTrack?: [number, number, number][];
	/** Haut réel de la tête (cheveux compris) dans la prise, lu dans l'alpha : [t de la prise, y 0-1 du cadre de la prise,
	 * largeur du visage 0-1 de la largeur de la prise (facultative)]. */
	head?: number[][]};
export type ReelDoc = {
	id: string;
	project: string;
	variant: string | null;
	title: string;
	delivery?: string;
	template?: string;
	width: number;
	height: number;
	fps: number;
	sources: Record<string, Source>;
	clips: Clip[];
	ctaBlock?: string | null;
	style: Style;
	zoom: {auto: boolean; strength: number; push: number; overrides: Record<string, number>};
	/** locked : bandeau fige (un changement de style ou la relecture ne le rallume ni ne l'eteint). */
	banner: {enabled: boolean; text: string; start: number; end: number | null; locked?: boolean};
	flash: {enabled: boolean; kind?: 'blanc' | 'glitch' | 'lumiere'};
	progress: {enabled: boolean};
	effects?: {grain: number; vignette: number; grade: string};
	emoji?: {enabled: boolean};
	music?: {enabled: boolean; mood: string | null; file: string | null; volume: number};
	sfx?: Sfx;
	/** Traitement de la voix a l'export et fond d'ambiance sous les coupes. */
	audio?: {voice: 'naturel' | 'radio' | 'podcast' | 'aucun'; roomTone: boolean; declip: boolean; denoise?: boolean};
	/** Titre d'ouverture 3D rendu par Blender (video transparente). */
	intro?: {enabled: boolean; text: string; file: string | null; duration: number};
	/** Piste V2 : plans de coupe. */
	broll?: Broll[];
	/** Piste Graphismes. */
	graphics?: Graphic[];
	/** Charte du client appliquee par-dessus le style de montage. */
	brand?: Brand | null;
	/** IA : 'auto' = applique ses choix ; 'suggestion' = propose, le monteur valide. */
	aiMode?: 'auto' | 'suggestion';
	suggestions?: Suggestions;
	/** Type de montage : 'parole' (defaut), 'immobilier', 'evenement'. */
	kind?: string;
	/** Declinaison : reel d'origine et intention (60 s, rapide...). */
	derivedFrom?: string | null;
	label?: string;
	design?: Design;
	styleScenes?: StyleScene[];
	cutouts?: Record<string, Cutout>;
	/** Directeur créatif V2 : intention globale calculée avant les effets. */
	creativePlan?: CreativePlan;
	/** Relecture du monteur (sobriete.py) : ce qui a ete retire, deplace, corrige, garde, et un resume lisible. */
	sobriete?: {retires: string[]; deplaces: string[]; corriges: string[]; gardes: number; resume: string};
	/** Mots en couleur choisis automatiquement, par plan : signature du texte + index allumes / eteints
	 * (pour garder les retouches a la main quand la selection est refaite). */
	hlAuto?: Record<string, {sig: string; on: number[]; off: number[]}>;
	/** V2 — revision : notes timecodees et dessins (jamais dans l'export). */
	notes?: Note[];
	annotations?: Annotation[];
	/** V2 — vecteurs de la banque poses sur l'image. */
	vectors?: VectorItem[];
	/** V2 — choregraphie : entree/sortie/courbe/synchro de chaque element, proposee par l'IA, modifiable. */
	choreography?: Choreography;
	/** « Dis a l'IA ce que tu veux » (engine/editeur/consigne.py) : historique des demandes (50 au plus) ; jamais exporte. */
	consignes?: Record<string, unknown>[];
};
/** Champs de revision : lus par l'interface seulement, retires des props du lecteur Remotion (et de l'export). */
export const REVIEW_KEYS = ['notes', 'annotations', 'consignes'] as const;

export const FORMATS: Record<string, [number, number]> = {'9:16': [1080, 1920], '16:9': [1920, 1080], '4:5': [1080, 1350], '1:1': [1080, 1080]};
export const formatOf = (r: {width: number; height: number}) => Object.entries(FORMATS).find(([, [w, h]]) => w === r.width && h === r.height)?.[0] ?? `${r.width}x${r.height}`;
/** audio : 'preview' = voix + musique + bruitages ; 'fx' = musique + bruitages seuls (export) ; 'none'. */
export type ReelProps = {reel: ReelDoc; assetBase: string; mediaBase: string; audio?: 'preview' | 'fx' | 'none'};

export const FONT_FILES: Record<string, string> = {
	Montserrat: 'Montserrat.ttf',
	Anton: 'Anton.ttf',
	'Bebas Neue': 'BebasNeue.ttf',
	Poppins: 'Poppins-ExtraBold.ttf',
	Inter: 'Inter.ttf',
	Oswald: 'Oswald.ttf',
	'Archivo Black': 'ArchivoBlack.ttf',
	Bangers: 'Bangers.ttf',
	'Luckiest Guy': 'LuckiestGuy.ttf',
	Rubik: 'Rubik.ttf',
	'Barlow Condensed': 'BarlowCondensed-ExtraBold.ttf',
	'Playfair Display': 'PlayfairDisplay.ttf',
	'DM Serif Display': 'DMSerifDisplay.ttf',
	'Permanent Marker': 'PermanentMarker.ttf',
	Kanit: 'Kanit-ExtraBold.ttf',
	'League Spartan': 'LeagueSpartan.ttf',
	Manrope: 'Manrope.ttf',
};
/** Police des interfaces du studio Tech 3D (cartes, bouton, chiffre) : grotesque moderne, lisible en petit. */
export const STUDIO_UI_FONT = 'Manrope';
export const EMOJI_FONT = 'NotoColorEmoji.ttf';
