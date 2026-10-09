/** Un mot de la transcription. hl = en couleur ; hide = masque dans les sous-titres ; cut = retire du montage. */
export type Word = {w: string; start: number; end: number; hl: boolean; hide: boolean; cut?: boolean};

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
};

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
export type Broll = {id: string; source: string; in: number; at: number; duration: number; word?: string; mode?: 'plein' | 'encadre'};

/** Element graphique anime (piste Graphismes). */
export type GraphicKind = 'chiffre' | 'coches' | 'carte' | 'motgeant' | 'logo';
export type Graphic = {id: string; kind: GraphicKind; at: number; duration: number; props: Record<string, any>; suggested?: boolean};

/** Charte d'un client : couleurs, police, logo, fin de video. */
export type Brand = {
	client: string; name: string; logo: string | null; logoPosition: 'haut-gauche' | 'haut-droite' | 'bas-gauche' | 'bas-droite'; logoSize: number; logoOpacity: number;
	bannerBg: string; bannerColor: string;
	/** Police et couleurs des sous-titres imposees par la charte. */
	style?: {font?: string; color?: string; highlight?: string; stroke?: string};
	outro: {enabled: boolean; text: string; duration: number};
};

/** Propositions de l'IA en attente de validation par le monteur. */
export type Suggestions = {banners: string[]; words: Record<string, number[]>; emojis: Record<string, [number, string][]>};

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
	/** Bruitages places a la main (conseils de rythme, graphismes) : temps du montage. */
	extra?: {t: number; name: string}[];
};
export type DesignMode = 'hormozi' | 'documentaire' | 'luxe' | 'vhs' | 'comparatif' | 'infographie' | 'tech' | 'collage' | 'editorial' | 'produit';
export type Design = {mode?: DesignMode; enabled?: boolean; accent?: string; secondary?: string; title?: string; density?: number;
 productImage?: string; productModel?: string; productVideo?: string; date?: string; suppressExtras?: boolean};
export type StyleScene = {id: string; kind: 'metric' | 'notification' | 'comparison' | 'keyword' | 'paper' | 'product';
 clip: string; index: number; length?: number; text: string; secondary?: string; duration: number; x: number; y: number;
 scale: number; rotation: number; color: string; hidden?: boolean};
export type Cutout = {file: string; start: number; end: number; width: number; height: number; source: string; proxy: string; frames?: string; fps?: number; count?: number};
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
	banner: {enabled: boolean; text: string; start: number; end: number | null};
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
};

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
};
export const EMOJI_FONT = 'NotoColorEmoji.ttf';
