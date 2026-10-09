// Vecteurs V2 (SVG recolorables de la banque) — FICHIER DE L'AGENT « vecteurs » (voir docs/direction-creative-v2/SPEC.md §2.5, §9.3).
// Insere une fois par l'architecte dans Reel.tsx, au-dessus des graphismes et sous les scenes du style, le bandeau et les
// sous-titres. Les SVG sont dans assets/banque/vecteurs/ (servis a `${assetBase}/banque/vecteurs/...` dans l'apercu comme a
// l'export) et sont INSERES EN LIGNE (jamais en <img>) : les couleurs passent par les variables CSS --v-principale,
// --v-secondaire, --v-contour posees sur le conteneur, les formes du fichier ne sont jamais modifiees.
// Meme rendu apercu / export : texte du SVG charge une fois (delayRender : l'export attend qu'il soit la), nettoye
// (aucun script, aucun style global, aucune ressource externe), animation calculee uniquement a partir du temps t.
// Ronde 4 : ICONES (assets/banque/icones, assets/banque/import ; vecteur avec meta.icone) habillees en trait, plein ou
// verre par prepareIcon / IconView (section « icones ») ; un vecteur sans meta.icone garde exactement son rendu d'avant.
import React, {useEffect, useRef, useState} from 'react';
import {AbsoluteFill, Img, continueRender, delayRender, useVideoConfig} from 'remotion';
import type {Cue, ReelDoc, VectorItem} from './types';
import {Choreo, animateElement, cueFor, placeOf} from './choreo';

// ---------------------------------------------------------------- couleurs ----------------------------------------------------------------
export const SLOTS = ['principale', 'secondaire', 'contour'] as const;
export type Slot = (typeof SLOTS)[number];
export type VecColors = Record<Slot, string | null>;
export const SLOT_NAMES: Record<Slot, string> = {principale: 'Principale', secondaire: 'Secondaire', contour: 'Contour'};

/** Couleur CSS sure (hexadecimal, rgb(), hsl()) ou null : rien d'autre n'entre dans une variable CSS. */
export const safeColor = (c: unknown): string | null => {
	if (typeof c !== 'string') return null;
	const s = c.trim();
	return /^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(s) || /^(rgb|rgba|hsl|hsla)\([\d\s.,%/+-]+\)$/i.test(s) ? s : null;
};

/** Palette automatique (SPEC §9.3) : principale = accent de la charte, sinon accent du style de la galerie, sinon couleur des
 * mots en couleur ; secondaire = couleur secondaire du style, sinon fond du bandeau de la charte, sinon texte des sous-titres ;
 * contour = contour des sous-titres. Une valeur null laisse la couleur d'origine du dessin. */
export const vectorPalette = (reel: ReelDoc): VecColors => {
	const design = reel.design && reel.design.enabled !== false && reel.design.mode ? reel.design : null;
	return {
		principale: safeColor(reel.brand?.style?.highlight) ?? safeColor(design?.accent) ?? safeColor(reel.style?.highlight),
		secondaire: safeColor(design?.secondary) ?? safeColor(reel.brand?.bannerBg) ?? safeColor(reel.style?.color),
		contour: safeColor(reel.style?.stroke),
	};
};

/** Couleurs affichees d'un vecteur : une couleur choisie fait foi ; sinon la palette (charte / style), sauf si les couleurs
 * sont manuelles (la charte ne recolore plus : la couleur d'origine du dessin reste). */
export const vectorColors = (reel: ReelDoc, v: Pick<VectorItem, 'couleurs' | 'couleursManuelles'>): VecColors => {
	const pal = vectorPalette(reel);
	const out = {} as VecColors;
	for (const k of SLOTS) out[k] = safeColor(v.couleurs?.[k]) ?? (v.couleursManuelles ? null : pal[k]);
	return out;
};

/** Variables CSS a poser sur le conteneur du SVG. */
export const colorVars = (c: VecColors): Record<string, string> => {
	const vars: Record<string, string> = {};
	for (const k of SLOTS) if (c[k]) vars[`--v-${k}`] = c[k] as string;
	return vars;
};

// ---------------------------------------------------------------- SVG ----------------------------------------------------------------
/** Chemin sous assets/ d'un SVG de vecteur (jamais « .. », jamais absolu). */
export const safeAsset = (asset: unknown): string | null =>
	typeof asset === 'string' && /^[A-Za-z0-9][A-Za-z0-9/_.-]*\.svg$/i.test(asset) && !asset.split('/').includes('..') ? asset : null;
export const vectorUrl = (assetBase: string, asset: string) => `${assetBase}/${asset}`;
/** Nom court d'un vecteur (« banque/vecteurs/fleche-courbe.svg » -> « fleche-courbe »). */
export const vectorName = (asset: string) => asset.split('/').pop()?.replace(/\.svg$/i, '') || 'vecteur';

export type VecSvg = {
	/** SVG nettoye, pret a inserer (ids prefixes, traits relies aux variables --v-trace-N). */
	markup: string;
	viewBox: [number, number, number, number];
	/** hauteur / largeur du dessin */
	ratio: number;
	shapes: number;
	/** chemins a « tracer » (classe v-trait) et nombre d'etapes du trace (data-etape) */
	traits: number;
	stages: number;
	/** animation en boucle du dessin (data-boucle) et son point d'appui (data-origine) */
	boucle: string | null;
	origine: string;
};

const ELEMENTS = new Set(['svg', 'g', 'path', 'circle', 'ellipse', 'rect', 'line', 'polyline', 'polygon', 'defs', 'clipPath', 'mask',
	'linearGradient', 'radialGradient', 'stop', 'use', 'symbol']);
export const SHAPES = new Set(['path', 'circle', 'ellipse', 'rect', 'line', 'polyline', 'polygon']);
const ATTRS = new Set(['id', 'class', 'd', 'cx', 'cy', 'r', 'rx', 'ry', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'width', 'height', 'points',
	'viewBox', 'transform', 'style', 'pathLength', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray',
	'stroke-dashoffset', 'stroke-miterlimit', 'opacity', 'fill-opacity', 'stroke-opacity', 'fill-rule', 'clip-rule', 'clip-path', 'mask',
	'offset', 'stop-color', 'stop-opacity', 'gradientUnits', 'gradientTransform', 'spreadMethod', 'fx', 'fy', 'fr', 'href', 'xlink:href',
	'preserveAspectRatio', 'vector-effect', 'paint-order', 'display', 'visibility', 'maskUnits', 'maskContentUnits', 'clipPathUnits',
	'xmlns', 'xmlns:xlink', 'version', 'role']);
/** Geometrie d'une forme : ce qui ne doit jamais changer quand on recolore. */
export const GEOMETRY = ['d', 'cx', 'cy', 'r', 'rx', 'ry', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'width', 'height', 'points', 'transform', 'pathLength'];
const TOKEN = /<!--[\s\S]*?-->|<\?[\s\S]*?\?>|<!\[CDATA\[[\s\S]*?\]\]>|<![^>]*>|<\/\s*([A-Za-z][\w:.-]*)\s*>|<([A-Za-z][\w:.-]*)((?:\s+[^\s=>/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'))?)*)\s*(\/?)>|[^<]+/g;
const ATTR = /([^\s=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'))?/g;
const DANGER = /javascript:|vbscript:|expression\s*\(|@import|behavior\s*:|url\(\s*['"]?(?!#)/i;

type Tag = {name: string; attrs: [string, string][]; self: boolean; close: boolean};
/** Lit les balises d'un SVG (lecteur minimal, sans DOM : meme resultat dans le navigateur, l'export et les tests Node). */
export const svgTags = (text: string): Tag[] => {
	const out: Tag[] = [];
	for (const m of String(text).matchAll(TOKEN)) {
		if (m[1]) out.push({name: m[1], attrs: [], self: false, close: true});
		else if (m[2]) {
			const attrs: [string, string][] = [];
			for (const a of (m[3] ?? '').matchAll(ATTR)) attrs.push([a[1], a[2] ?? a[3] ?? '']);
			out.push({name: m[2], attrs, self: m[4] === '/', close: false});
		}
	}
	return out;
};

/** Formes d'un SVG (balise + geometrie), dans l'ordre : sert a verifier qu'une recoloration ne perd aucune forme. */
export const svgShapes = (text: string): string[] =>
	svgTags(text).filter((t) => !t.close && SHAPES.has(t.name))
		.map((t) => [t.name, ...GEOMETRY.filter((g) => g !== 'pathLength').map((g) => t.attrs.find(([k]) => k === g)?.[1] ?? '')].join('|'));

const esc = (v: string) => v.replace(/"/g, '&quot;').replace(/</g, '&lt;');
const numbers = (s: string | undefined) => (s ?? '').trim().split(/[\s,]+/).map(Number);

/** Nettoie et prepare un SVG pour l'insertion en ligne. prefix : rend les ids uniques (plusieurs vecteurs identiques a l'image).
 * Retire tout ce qui n'est pas du dessin (script, style, texte, image, lien, animation SMIL, attributs on*, url externes).
 * null si ce n'est pas un SVG exploitable (pas de viewBox ni de taille).
 * opts.tracerTout : chaque forme est un trait a « tracer » (icones au trait : Lucide n'a pas de classe v-trait). */
export const prepareSvg = (text: string, prefix = 'v', opts: {tracerTout?: boolean} = {}): VecSvg | null => {
	const pre = String(prefix).replace(/[^A-Za-z0-9_-]/g, '_');
	const ref = (v: string) => v.replace(/url\(\s*#([^)\s'"]+)\s*\)/g, (_, id) => `url(#${pre}-${id})`);
	const tags = svgTags(text);
	const out: string[] = [];
	const stack: string[] = [];
	let skip = 0;
	let root: VecSvg | null = null;
	let shapes = 0;
	let traits = 0;
	let stages = 0;
	for (const t of tags) {
		if (t.close) {
			if (skip) {
				skip--;
				continue;
			}
			const i = stack.lastIndexOf(t.name);
			if (i < 0) continue;
			while (stack.length > i) out.push(`</${stack.pop()}>`);
			continue;
		}
		if (skip || !ELEMENTS.has(t.name) || (!root && t.name !== 'svg')) {
			if (!t.self) skip++;
			continue;
		}
		const attrs: [string, string][] = [];
		let trait = false;
		let stage = 1;
		for (const [k0, v0] of t.attrs) {
			const k = k0;
			if (!(ATTRS.has(k) || /^data-[a-z0-9-]+$/.test(k) || /^aria-[a-z]+$/.test(k))) continue; // on*, xml:base, etc.
			if (DANGER.test(v0)) continue;
			if ((k === 'href' || k === 'xlink:href') && !/^#[\w:.-]+$/.test(v0)) continue;
			let v = ref(v0);
			if (k === 'id') v = `${pre}-${v0}`;
			if (k === 'href' || k === 'xlink:href') v = `#${pre}-${v0.slice(1)}`;
			if (k === 'class' && /(^|\s)v-trait(\s|$)/.test(v0)) trait = true;
			if (k === 'data-etape') stage = Math.max(1, Math.min(8, Math.round(Number(v0)) || 1));
			attrs.push([k, v]);
		}
		if (!root) {
			// racine : taille imposee par le conteneur, jamais rognee (les traits epais peuvent deborder du cadre du dessin)
			const get = (n: string) => attrs.find(([k]) => k === n)?.[1];
			let vb = numbers(get('viewBox'));
			if (vb.length !== 4 || !vb.every(Number.isFinite) || vb[2] <= 0 || vb[3] <= 0) {
				const w = Number.parseFloat(get('width') ?? '');
				const h = Number.parseFloat(get('height') ?? '');
				if (!(w > 0 && h > 0)) return null;
				vb = [0, 0, w, h];
			}
			const origine = (get('data-origine') ?? '').match(/^\s*(-?\d+(\.\d+)?%\s+-?\d+(\.\d+)?%)\s*$/)?.[1] ?? '50% 50%';
			root = {markup: '', viewBox: vb as VecSvg['viewBox'], ratio: vb[3] / vb[2], shapes: 0, traits: 0, stages: 0,
				boucle: (get('data-boucle') ?? '').match(/^[a-z-]{1,24}$/)?.[0] ?? null, origine};
			const keep = attrs.filter(([k]) => !['width', 'height', 'style', 'viewBox', 'preserveAspectRatio'].includes(k));
			out.push(`<svg${keep.map(([k, v]) => ` ${k}="${esc(v)}"`).join('')} viewBox="${vb.join(' ')}" preserveAspectRatio="xMidYMid meet"`
				+ ` aria-hidden="true" focusable="false" style="display:block;width:100%;height:100%;overflow:visible">`);
			stack.push('svg');
			continue;
		}
		if (SHAPES.has(t.name)) shapes++;
		if (opts.tracerTout && SHAPES.has(t.name)) trait = true;
		if (trait) {
			// trait a « tracer » : longueur ramenee a 1, pointilles 1 / 1,5 (0 = entierement dessine, 1 = invisible, sans point
			// residuel au bout) relies a la variable de son etape
			traits++;
			stages = Math.max(stages, stage);
			if (!attrs.some(([k]) => k === 'pathLength')) attrs.push(['pathLength', '1']);
			const i = attrs.findIndex(([k]) => k === 'style');
			const dash = `stroke-dasharray:1 1.5;stroke-dashoffset:var(--v-trace-${stage},0)`;
			if (i < 0) attrs.push(['style', dash]);
			else attrs[i] = ['style', `${attrs[i][1].replace(/;\s*$/, '')};${dash}`];
		}
		out.push(`<${t.name}${attrs.map(([k, v]) => ` ${k}="${esc(v)}"`).join('')}${t.self ? '/>' : '>'}`);
		if (!t.self) stack.push(t.name);
	}
	if (!root) return null;
	while (stack.length) out.push(`</${stack.pop()}>`);
	return {...root, markup: out.join(''), shapes, traits, stages};
};

// ---------------------------------------------------------------- animation ----------------------------------------------------------------
export type MoveType = 'fondu' | 'glisse' | 'zoom' | 'pop' | 'trace' | 'aucune';
export type Direction = 'gauche' | 'droite' | 'haut' | 'bas';
export type VecMove = {type: MoveType; direction: Direction};
const MOVES: MoveType[] = ['fondu', 'glisse', 'zoom', 'pop', 'trace', 'aucune'];
const DIRECTIONS: Direction[] = ['gauche', 'droite', 'haut', 'bas'];
/** Animations proposees dans l'interface (valeur enregistree dans v.anim.entree / v.anim.sortie). « glisse-gauche » :
 * arrive par la gauche (entree) / part vers la gauche (sortie) ; « glisse » seul = par le bas. */
export const ANIM_CHOICES: [string, string][] = [['pop', 'Pop (rebond)'], ['fondu', 'Fondu'], ['zoom', 'Zoom'], ['trace', 'Tracé (le trait se dessine)'],
	['glisse-gauche', 'Glisse par la gauche'], ['glisse-droite', 'Glisse par la droite'], ['glisse-haut', 'Glisse par le haut'],
	['glisse-bas', 'Glisse par le bas'], ['aucune', 'Aucune (apparaît net)']];

export const parseMove = (s: unknown, fallback: MoveType): VecMove => {
	const [type, direction] = String(s ?? '').toLowerCase().split('-') as [MoveType, Direction];
	return {type: MOVES.includes(type) ? type : fallback, direction: DIRECTIONS.includes(direction) ? direction : 'bas'};
};
/** Durees propres (s) de l'entree et de la sortie ; « trace » depend de la duree du vecteur. */
export const DUREES: Record<'entree' | 'sortie', Record<MoveType, number>> = {
	entree: {fondu: 0.35, glisse: 0.4, zoom: 0.4, pop: 0.45, trace: 0.8, aucune: 0},
	sortie: {fondu: 0.3, glisse: 0.35, zoom: 0.3, pop: 0.25, trace: 0.4, aucune: 0},
};

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const easeOut = (x: number) => 1 - (1 - x) ** 3;
const BACK = 1.70158;
const backOut = (x: number) => 1 + (BACK + 1) * (x - 1) ** 3 + BACK * (x - 1) ** 2;
const backIn = (x: number) => (BACK + 1) * x ** 3 - BACK * x ** 2;
/** Courbe d'un mouvement de la choregraphie appliquee au trace (sans depassement : un trait ne se dessine pas au-dela de 100 %). */
const curve = (courbe: string | undefined) => (p: number) =>
	courbe === 'lineaire' ? p : courbe === 'rapide' ? 1 - (1 - p) ** 5 : 1 - (1 - p) ** 3;

export type VecMotion = {opacity: number; tx: number; ty: number; scale: number; draw: number; dash: number[]; inType: MoveType; outType: MoveType};

/** Etat d'animation d'un vecteur a l'instant t (temps du montage) : pur, identique dans l'apercu et l'export.
 * frame = taille de l'image (px) ; size = taille du vecteur (px) ; stages = etapes du trace du dessin (0 : rien a tracer).
 * Un mouvement de la choregraphie de type « trace » sur ce vecteur est dessine ICI (le calque de la choregraphie ne
 * modifie que l'opacite et la position) ; ses autres types s'ajoutent par <Choreo>. */
export const vectorMotion = (v: Pick<VectorItem, 'at' | 'duration' | 'anim'>, t: number, frame: {w: number; h: number},
	size: {w: number; h: number}, stages: number, cue: Cue | null = null): VecMotion => {
	const D = Math.max(0.04, v.duration);
	const local = t - v.at;
	let inn = parseMove(v.anim?.entree, 'pop');
	let out = parseMove(v.anim?.sortie, 'fondu');
	let dIn = inn.type === 'trace' ? Math.max(0.45, Math.min(1, D * 0.4)) : DUREES.entree[inn.type];
	let dOut = DUREES.sortie[out.type];
	// courbe du trace : vitesse constante (geste de la main), sauf si la choregraphie en impose une
	let easeIn = (p: number) => p;
	let easeOutFn = (p: number) => p;
	// un « trace » de la choregraphie ne remplace l'animation propre que si le dessin a des traits : sinon (explosion,
	// etoile...) le vecteur garde sa propre entree / sortie au lieu de passer en fondu
	if (cue && !cue.desactive && stages > 0) {
		if (cue.entree?.type === 'trace') {
			[inn, dIn] = [{type: 'trace', direction: 'bas'}, cue.entree.duree > 0 ? cue.entree.duree : dIn];
			easeIn = curve(cue.entree.courbe);
		}
		if (cue.sortie?.type === 'trace') {
			[out, dOut] = [{type: 'trace', direction: 'bas'}, cue.sortie.duree > 0 ? cue.sortie.duree : DUREES.sortie.trace];
			easeOutFn = curve(cue.sortie.courbe);
		}
	}
	// rien a tracer dans ce dessin : fondu
	if (inn.type === 'trace' && !stages) [inn, dIn] = [{type: 'fondu', direction: 'bas'}, DUREES.entree.fondu];
	if (out.type === 'trace' && !stages) [out, dOut] = [{type: 'fondu', direction: 'bas'}, DUREES.sortie.fondu];
	// vecteur court : l'entree et la sortie se partagent au plus 90 % de sa duree
	const k = Math.min(1, (D * 0.9) / Math.max(1e-6, dIn + dOut));
	dIn *= k;
	dOut *= k;
	const m: VecMotion = {opacity: 1, tx: 0, ty: 0, scale: 1, draw: 1, dash: [], inType: inn.type, outType: out.type};
	const dist = Math.max(size.w, size.h, 0.12 * Math.min(frame.w, frame.h));
	const phase = (mv: VecMove, p: number, entering: boolean) => {
		// p : 0 = absent, 1 = entierement la
		if (p >= 1) return;
		const e = easeOut(p);
		switch (mv.type) {
			case 'fondu':
				m.opacity *= entering ? e : p;
				break;
			case 'glisse': {
				const d = dist * (1 - e);
				if (mv.direction === 'gauche') m.tx -= d;
				else if (mv.direction === 'droite') m.tx += d;
				else if (mv.direction === 'haut') m.ty -= d;
				else m.ty += d;
				m.opacity *= clamp01(p * 2.5);
				break;
			}
			case 'zoom':
				m.scale *= 0.35 + 0.65 * e;
				m.opacity *= clamp01(p * 2);
				break;
			case 'pop':
				m.scale *= entering ? Math.max(0, backOut(p)) : Math.max(0, 1 - backIn(1 - p));
				m.opacity *= clamp01(p * 4);
				break;
			case 'trace':
				m.draw = Math.min(m.draw, (entering ? easeIn : easeOutFn)(p));
				m.opacity *= clamp01(p * (entering ? 12 : 3));
				break;
			default:
				if (p <= 0) m.opacity = 0;
		}
	};
	phase(inn, dIn > 0 ? clamp01(local / dIn) : local >= 0 ? 1 : 0, true);
	phase(out, dOut > 0 ? clamp01((D - local) / dOut) : local < D ? 1 : 0, false);
	for (let s = 1; s <= stages; s++) m.dash.push(1 - clamp01(m.draw * stages - (s - 1)));
	return m;
};

/** Mouvement en boucle propre au dessin (data-boucle) pendant qu'il est a l'image. */
export const loopTransform = (boucle: string | null, local: number): string => {
	const tau = 2 * Math.PI;
	switch (boucle) {
		case 'rotation':
			return `rotate(${((local * 300) % 360).toFixed(2)}deg)`;
		case 'rotation-lente':
			return `rotate(${((local * 24) % 360).toFixed(2)}deg)`;
		case 'pulse': {
			const b = Math.max(0, Math.sin((local * tau) / 0.9));
			return `scale(${(1 + 0.07 * b ** 3).toFixed(4)})`;
		}
		case 'scintille':
			return `scale(${(1 + 0.08 * Math.sin((local * tau) / 0.8)).toFixed(4)}) rotate(${(6 * Math.sin((local * tau) / 1.6)).toFixed(2)}deg)`;
		case 'balance': {
			const q = local % 2.2;
			const a = q < 1.3 ? 12 * Math.sin((q * tau) / 0.45) * (1 - q / 1.3) : 0;
			return `rotate(${a.toFixed(2)}deg)`;
		}
		case 'flotte':
			return `translateY(${(-7 * Math.abs(Math.sin((local * Math.PI) / 0.7))).toFixed(2)}%)`;
		default:
			return '';
	}
};

// ---------------------------------------------------------------- chargement ----------------------------------------------------------------
const TEXTS = new Map<string, string | null>();
const LOADING = new Map<string, Promise<string | null>>();
/** Texte d'un SVG (charge une seule fois par page ; null si introuvable). */
export const loadVectorText = (url: string): Promise<string | null> => {
	let p = LOADING.get(url);
	if (!p) {
		p = fetch(url)
			.then((r) => (r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`))))
			.catch((e) => {
				console.warn(`Vecteur introuvable : ${url} (${e?.message ?? e})`);
				return null;
			})
			.then((txt) => {
				TEXTS.set(url, txt);
				return txt;
			});
		LOADING.set(url, p);
	}
	return p;
};
export const vectorText = (url: string) => TEXTS.get(url);
const PREPARED = new Map<string, VecSvg | null>();
/** SVG prepare (memorise par fichier et par vecteur : les ids restent uniques et stables d'une image a l'autre). */
export const preparedVector = (url: string, prefix: string): VecSvg | null => {
	const text = TEXTS.get(url);
	if (!text) return null;
	const key = `${url}\n${prefix}`;
	if (!PREPARED.has(key)) PREPARED.set(key, prepareSvg(text, prefix));
	return PREPARED.get(key) ?? null;
};

/** Charge les SVG du montage. A l'export, une attente (delayRender) garantit que la premiere image n'est prise qu'une fois
 * les dessins charges : pas de course entre le chargement et la capture. */
const useVectorTexts = (urls: string[]) => {
	const key = urls.join('\n');
	const [handle] = useState(() => (urls.some((u) => !TEXTS.has(u)) ? delayRender('Chargement des vecteurs SVG', {timeoutInMilliseconds: 30000}) : null));
	const released = useRef(false);
	const [, setTick] = useState(0);
	const ready = urls.every((u) => TEXTS.has(u));
	useEffect(() => {
		let alive = true;
		const todo = key ? key.split('\n').filter((u) => !TEXTS.has(u)) : [];
		if (todo.length) Promise.all(todo.map(loadVectorText)).then(() => alive && setTick((n) => n + 1));
		return () => {
			alive = false;
		};
	}, [key]);
	useEffect(() => {
		// libere l'export APRES le rendu qui contient les dessins
		if (ready && handle !== null && !released.current) {
			released.current = true;
			continueRender(handle);
		}
	}, [ready, handle]);
	useEffect(() => () => {
		if (handle !== null && !released.current) {
			released.current = true;
			continueRender(handle);
		}
	}, [handle]);
};

// ---------------------------------------------------------------- icones (ronde 4) ----------------------------------------------------------------
// Une icone de la banque (assets/banque/icones/<bibliotheque>/*.svg, Lucide ; ou assets/banque/import/** : SVG / PNG deposes
// par le monteur) est un VECTEUR ordinaire (reel.vectors : place, taille, moment, animation, verrou, choregraphie) dont
// meta.icone = {style, nom, banque} choisit l'habillage, calcule ICI pour n'importe quelle icone :
//  - « trait » : le trait de l'icone aux couleurs de la charte (principale), ombre douce (contour) pour rester lisible ;
//  - « plein » : pastille ronde pleine (degrade de la principale) et icone de la couleur la plus lisible dessus ;
//  - « verre » : tuile arrondie de verre givre (flou de l'image derriere, degrade translucide, reflet, liseré lumineux,
//    lueur douce) et icone en degrade vif (principale -> secondaire, ou une teinte voisine de la principale).
// Le fichier de l'icone n'est jamais modifie : ses formes sont inserees telles quelles (svgShapes identiques), seules la
// peinture (currentColor / couleur de la racine) et l'habillage changent ; les couleurs passent par des variables CSS
// (--ic-*) : meme balisage pour toutes les couleurs, meme rendu apercu / export. Vecteur sans meta.icone hors des dossiers
// d'icones : rendu d'avant, inchange.
export const ICON_STYLES = ['trait', 'plein', 'verre'] as const;
export type IconStyle = (typeof ICON_STYLES)[number];
export const ICON_STYLE_NAMES: Record<IconStyle, string> = {trait: 'Trait', plein: 'Plein', verre: 'Verre'};
export const ICON_STYLE_HINTS: Record<IconStyle, string> = {trait: 'Icône au trait, aux couleurs de la charte',
	plein: 'Pastille ronde pleine, icône contrastée dessus', verre: 'Tuile de verre givré, icône en dégradé lumineux'};
/** Couleurs reglables de chaque style (memes champs couleurs.principale / secondaire / contour que les vecteurs). */
export const ICON_SLOTS: Record<IconStyle, [Slot, string][]> = {
	trait: [['principale', 'Trait'], ['contour', 'Ombre']],
	plein: [['principale', 'Pastille'], ['secondaire', 'Icône']],
	verre: [['principale', 'Dégradé 1'], ['secondaire', 'Dégradé 2']],
};
const ICON_DIRS = ['banque/icones/', 'banque/import/', 'banque/apercus/import/'];
const ICON_ACCENT = '#FFD400';
/** Chemin sous assets/ d'une icone (SVG ou PNG des dossiers d'icones, ou SVG d'un vecteur habille en icone). */
export const iconAsset = (asset: unknown): string | null =>
	typeof asset === 'string' && /^[A-Za-z0-9][A-Za-z0-9/_.-]*\.(svg|png)$/i.test(asset) && !asset.split('/').includes('..')
		&& (/\.svg$/i.test(asset) || ICON_DIRS.some((d) => asset.startsWith(d))) ? asset : null;
export const isPngIcon = (asset: string) => /\.png$/i.test(asset);
export type IconMeta = {style?: string; nom?: string; banque?: string};
export const iconMeta = (v: {meta?: Record<string, unknown>}): IconMeta | null => {
	const m = v.meta?.icone;
	return m && typeof m === 'object' && !Array.isArray(m) ? (m as IconMeta) : null;
};
/** Style d'icone d'un vecteur, ou null (vecteur classique). meta.icone fait foi ; une ressource des dossiers d'icones posee
 * sans meta est rendue au trait. */
export const iconStyleOf = (v: {asset: string; meta?: Record<string, unknown>}): IconStyle | null => {
	const asset = iconAsset(v.asset);
	const m = iconMeta(v);
	if (!asset || (!m && !ICON_DIRS.some((d) => asset.startsWith(d)))) return null;
	return (ICON_STYLES as readonly string[]).includes(String(m?.style)) ? (m!.style as IconStyle) : 'trait';
};
/** Nom affiche d'une icone (nom francais garde dans meta.icone.nom, sinon le nom du fichier). */
export const iconName = (v: {asset: string; meta?: Record<string, unknown>}) => {
	const n = iconMeta(v)?.nom;
	return typeof n === 'string' && n.trim() ? n.trim().slice(0, 80) : vectorName(v.asset).replace(/\.png$/i, '');
};

// ---- couleurs derivees (pures) ----
type RGB = [number, number, number];
const hexRgb = (c: string | null | undefined): RGB | null => {
	const s = String(c ?? '').trim();
	const m = /^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.exec(s);
	if (!m) return null;
	const h = m[1].length <= 4 ? [...m[1].slice(0, 3)].map((x) => x + x).join('') : m[1].slice(0, 6);
	return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as RGB;
};
const rgbHex = (c: RGB) => `#${c.map((x) => Math.round(Math.max(0, Math.min(255, x))).toString(16).padStart(2, '0')).join('')}`.toUpperCase();
const rgbHsl = ([r0, g0, b0]: RGB): [number, number, number] => {
	const [r, g, b] = [r0 / 255, g0 / 255, b0 / 255];
	const mx = Math.max(r, g, b);
	const mn = Math.min(r, g, b);
	const l = (mx + mn) / 2;
	if (mx === mn) return [0, 0, l];
	const d = mx - mn;
	const s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
	const h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
	return [h * 60, s, l];
};
const hslRgb = (h: number, s: number, l: number): RGB => {
	const k = (n: number) => (n + h / 30) % 12;
	const a = s * Math.min(l, 1 - l);
	const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
	return [f(0) * 255, f(8) * 255, f(4) * 255];
};
const luminance = (c: RGB) => {
	const [r, g, b] = c.map((x) => {
		const v = x / 255;
		return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
	});
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
/** Contraste WCAG entre deux couleurs (1 a 21). */
export const contrastRatio = (a: string, b: string) => {
	const x = hexRgb(a);
	const y = hexRgb(b);
	if (!x || !y) return 1;
	const [l1, l2] = [luminance(x), luminance(y)].sort((p, q) => q - p);
	return (l1 + 0.05) / (l2 + 0.05);
};
const shade = (c: string, dl: number) => {
	const x = hexRgb(c);
	if (!x) return c;
	const [h, s, l] = rgbHsl(x);
	return rgbHex(hslRgb(h, s, Math.max(0, Math.min(1, l + dl))));
};
/** Deuxieme couleur vive du degrade « verre » : la secondaire si elle est vive et assez differente, sinon une teinte voisine
 * de la principale (35 degres plus loin sur le cercle des couleurs, saturee). */
export const iconSecondTone = (a: string, b: string | null) => {
	const x = hexRgb(a);
	if (!x) return b ?? a;
	const [h, s, l] = rgbHsl(x);
	const y = hexRgb(b);
	if (y) {
		const [h2, s2, l2] = rgbHsl(y);
		const dh = Math.min(Math.abs(h2 - h), 360 - Math.abs(h2 - h));
		if (s2 >= 0.45 && l2 >= 0.3 && l2 <= 0.75 && dh >= 25) return rgbHex(y);
	}
	if (s < 0.12) return rgbHex(hslRgb(0, 0, l > 0.5 ? Math.max(0.55, l - 0.3) : Math.min(0.85, l + 0.35))); // gris : plus clair / plus fonce
	return rgbHex(hslRgb((h - 35 + 360) % 360, Math.max(s, 0.85), Math.max(0.5, Math.min(0.62, l))));
};
/** Couleur de l'icone posee sur une pastille pleine : la premiere assez lisible (contraste >= 3), sinon la plus lisible. */
const lisible = (fond: string, choix: (string | null)[]) => {
	const ok = choix.filter((c): c is string => !!hexRgb(c));
	return ok.find((c) => contrastRatio(fond, c) >= 3) ?? ok.sort((p, q) => contrastRatio(fond, q) - contrastRatio(fond, p))[0] ?? '#FFFFFF';
};

/** Couleurs affichees d'une icone (variables CSS --ic-*) : une couleur choisie fait foi ; sinon la charte / le style
 * (vectorColors), puis des couleurs derivees de la principale. */
export const iconVars = (reel: ReelDoc, v: Pick<VectorItem, 'couleurs' | 'couleursManuelles'>, style: IconStyle): Record<string, string> => {
	const c = vectorColors(reel, v);
	const pal = vectorPalette(reel);
	const choisie = (k: Slot) => safeColor(v.couleurs?.[k]);
	const a = c.principale ?? pal.principale ?? ICON_ACCENT;
	if (style === 'plein') return {'--ic-a': a, '--ic-a1': shade(a, 0.1), '--ic-a2': shade(a, -0.12),
		'--ic-on': choisie('secondaire') ?? lisible(a, [c.secondaire, '#FFFFFF', '#0B0B0F'])};
	if (style === 'verre') return {'--ic-a': a, '--ic-al': shade(a, 0.12), '--ic-b': choisie('secondaire') ?? iconSecondTone(a, c.secondaire), '--ic-glow': a};
	return {'--ic-a': a, '--ic-sh': c.contour ?? '#000000'};
};
/** Couleurs a montrer dans les selecteurs (Trait/Ombre, Pastille/Icone, Degrade 1/2) : celles de l'image. */
export const iconShownColors = (reel: ReelDoc, v: Pick<VectorItem, 'couleurs' | 'couleursManuelles'>, style: IconStyle): VecColors => {
	const x = iconVars(reel, v, style);
	return {principale: x['--ic-a'] ?? null, secondaire: x['--ic-on'] ?? x['--ic-b'] ?? null, contour: x['--ic-sh'] ?? null};
};

const PRESENTATION = ['fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-miterlimit', 'fill-rule', 'clip-rule'];
const num = (x: number) => +x.toFixed(3);

/** Icones de packs achetes (Illustrator : <style>.cls-1{fill:#e94e1b}</style>) : les regles de CLASSE simples sont recopiees
 * dans l'attribut style de chaque element (prepareSvg retire les <style> : sans cela, les couleurs du dessin seraient
 * perdues). Le style ecrit sur l'element reste prioritaire. Les valeurs passent ensuite par les filtres de prepareSvg. */
export const inlineClassStyles = (text: string): string => {
	if (!/<style\b/i.test(text)) return text;
	const rules = new Map<string, string>();
	for (const m of text.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style\s*>/gi)) {
		const css = m[1].replace(/<!\[CDATA\[|\]\]>/g, '').replace(/\/\*[\s\S]*?\*\//g, '');
		for (const r of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
			const decl = r[2].trim().replace(/;+\s*$/, '');
			if (!decl) continue;
			for (const sel of r[1].split(',')) {
				const c = /^\s*\.([A-Za-z_][\w-]*)\s*$/.exec(sel);
				if (c) rules.set(c[1], [rules.get(c[1]), decl].filter(Boolean).join(';'));
			}
		}
	}
	if (!rules.size) return text;
	return text.replace(/<([A-Za-z][\w:.-]*)(\s[^<>]*?)?(\/?)>/g, (all, name: string, attrs: string | undefined, self: string) => {
		const a = attrs ?? '';
		const cm = /\sclass\s*=\s*(?:"([^"]*)"|'([^']*)')/.exec(a);
		if (!cm) return all;
		const decls = (cm[1] ?? cm[2] ?? '').split(/\s+/).map((k) => rules.get(k)).filter(Boolean).join(';');
		if (!decls) return all;
		const sm = /\sstyle\s*=\s*(?:"([^"]*)"|'([^']*)')/.exec(a);
		const style = (sm ? `${decls};${sm[1] ?? sm[2] ?? ''}` : decls).replace(/"/g, "'");
		return `<${name}${sm ? a.replace(sm[0], '') : a} style="${style}"${self}>`;
	});
};

const NEUTRES = new Set(['black', 'white', 'gray', 'grey', 'silver', 'dimgray', 'dimgrey', 'darkgray', 'darkgrey', 'lightgray', 'lightgrey', 'gainsboro']);
/** Couleur « sans couleur » (noir, gris, blanc) : celle d'un pack d'icones a recolorer. Une couleur vive (logo d'un
 * partenaire, pictogramme a sa couleur) ne l'est pas : elle reste. */
export const neutralPaint = (c: string): boolean => {
	const s = c.trim().toLowerCase();
	if (NEUTRES.has(s)) return true;
	const m = /^rgba?\(\s*([\d.]+)%?[\s,]+([\d.]+)%?[\s,]+([\d.]+)%?/.exec(s);
	const rgb = hexRgb(s) ?? (m ? ([m[1], m[2], m[3]].map(Number) as RGB) : null);
	return !!rgb && rgbHsl(rgb)[1] < 0.15;
};

/** Icone monochrome ecrite en dur (packs : fill="#1E1E1E" sur chaque forme) : sa couleur unique, si elle est neutre (noir,
 * gris, blanc), devient currentColor (l'icone suit alors la charte comme une icone Lucide). Une seule couleur vive (logo),
 * plusieurs couleurs, un degrade ou une couleur par url() : couleurs du fichier gardees. markup : interieur deja nettoye par
 * prepareSvg (attributs entre guillemets doubles) ; rootFill : la racine du fichier ecrit un remplissage (sinon une forme
 * sans remplissage prend la couleur de l'icone : une 2e couleur) ; rootPaints : couleurs ecrites sur la racine (logo rouge
 * a barres blanches : deux couleurs, gardees). */
export const monoToCurrent = (markup: string, rootFill = false, rootPaints: string[] = []): string => {
	if (/<(linearGradient|radialGradient)\b/.test(markup)) return markup;
	const PAINT = /(^|[\s;"])(fill|stroke)(="|\s*:\s*)([^";]*)/g;
	const libres = new Set(['none', 'currentcolor', 'transparent', 'inherit', '']);
	const couleurs = new Set<string>(rootPaints.map((c) => c.trim().toLowerCase()).filter((c) => !libres.has(c)));
	for (const m of markup.matchAll(PAINT)) {
		const c = m[4].trim().toLowerCase();
		if (c.startsWith('url(') || c.startsWith('var(')) return markup;
		if (!libres.has(c)) couleurs.add(c);
	}
	if (couleurs.size !== 1 || !neutralPaint([...couleurs][0])) return markup;
	// une forme peinte du noir par defaut (ni elle ni un groupe parent n'ecrit de remplissage) : deux couleurs, gardees
	const hasFill = (t: Tag) => t.attrs.some(([k, v]) => k === 'fill' || (k === 'style' && /(^|;)\s*fill\s*:/.test(v)));
	const stack: [string, boolean][] = [];
	for (const t of svgTags(markup)) {
		if (t.close) {
			const i = stack.map(([n]) => n).lastIndexOf(t.name);
			if (i >= 0) stack.length = i;
			continue;
		}
		const cache = ['defs', 'clipPath', 'mask', 'symbol'].includes(t.name);
		const herite = stack.length ? stack[stack.length - 1][1] : rootFill;
		const rempli = herite || hasFill(t) || cache;
		if (SHAPES.has(t.name) && !rempli) return markup;
		if (!t.self) stack.push([t.name, rempli]);
	}
	return markup.replace(PAINT, (all, p0: string, k: string, sep: string, v: string) => (couleurs.has(v.trim().toLowerCase()) ? `${p0}${k}${sep}currentColor` : all));
};

/** Habillage d'une icone (balisage SVG, boite 100 x 100, debordements visibles) : trait, pastille pleine ou tuile de verre.
 * text : le SVG de l'icone (null : icone PNG, l'image est posee par-dessus par IconView dans le carre iconBox(style)).
 * Le dessin garde toutes ses formes ; seule sa peinture (currentColor, couleur de la racine) suit les variables --ic-*. */
export const prepareIcon = (text: string | null, style: IconStyle, prefix = 'ic'): VecSvg | null => {
	const pre = String(prefix).replace(/[^A-Za-z0-9_-]/g, '_');
	let inner = '';
	let vb: VecSvg['viewBox'] = [0, 0, 24, 24];
	let stages = 0;
	let traits = 0;
	let shapes = 0;
	let gAttrs = '';
	const paint = style === 'verre' ? `url(#${pre}-ig)` : 'currentColor';
	if (text !== null) {
		// packs achetes : couleurs des classes <style> gardees, icone monochrome ecrite en dur recoloree comme Lucide
		const src = inlineClassStyles(text);
		const raw = svgTags(src).find((t) => !t.close && t.name === 'svg');
		const stroked = !!raw && raw.attrs.some(([k, v]) => k === 'stroke' && v.trim() !== 'none');
		const base = prepareSvg(src, pre, {tracerTout: stroked});
		if (!base) return null;
		vb = base.viewBox;
		[stages, traits, shapes] = [base.stages, base.traits, base.shapes];
		inner = monoToCurrent(base.markup.slice(base.markup.indexOf('>') + 1, base.markup.lastIndexOf('</svg>')),
			!!raw && raw.attrs.some(([k]) => k === 'fill'), (raw?.attrs ?? []).filter(([k]) => k === 'fill' || k === 'stroke').map(([, v]) => v));
		if (style === 'verre') inner = inner.replace(/currentColor/g, paint);
		// peinture de la racine (Lucide : fill="none" stroke="currentColor") reportee sur le groupe ; sans remplissage ecrit,
		// le noir par defaut d'un SVG devient la couleur de l'icone (packs d'icones pleines)
		const attrs = (raw?.attrs ?? []).filter(([k]) => PRESENTATION.includes(k));
		if (!attrs.some(([k]) => k === 'fill')) attrs.push(['fill', paint]);
		// (une couleur vive ecrite sur la racine — logo d'un partenaire — reste la sienne, comme dans monoToCurrent)
		gAttrs = attrs.map(([k, v]) => {
			// gardee seulement si c'est une simple couleur (jamais une url() ni autre chose venue du fichier)
			const recolore = /^currentcolor$/i.test(v.trim()) || neutralPaint(v) || !(safeColor(v) || /^\s*[a-z]{3,20}\s*$/i.test(v));
			const val = (k === 'fill' || k === 'stroke') && v.trim() !== 'none' && recolore ? paint : v;
			return ` ${k}="${esc(val)}"`;
		}).join('');
	}
	const [s, o] = style === 'trait' ? [88, 6] : style === 'plein' ? [50, 25] : [52, 24];
	const icon = text === null ? '' : `<svg x="${o}" y="${o}" width="${s}" height="${s}" viewBox="${vb.join(' ')}" preserveAspectRatio="xMidYMid meet" overflow="visible">`
		+ `<g${gAttrs}${style === 'verre' ? ` filter="url(#${pre}-igf)"` : ''} style="color:var(${style === 'plein' ? '--ic-on' : '--ic-a'})">${inner}</g></svg>`;
	const [x0, y0, w0, h0] = vb;
	let defs = '';
	let body = '';
	if (style === 'trait') {
		// lisible sur n'importe quelle image : liseré sombre fin (comme le contour des sous-titres) + ombre douce
		defs = `<filter id="${pre}-sh" filterUnits="userSpaceOnUse" x="-30" y="-30" width="160" height="160" color-interpolation-filters="sRGB">`
			+ `<feMorphology in="SourceAlpha" operator="dilate" radius="1.1" result="d"/><feGaussianBlur in="d" stdDeviation="0.5" result="db"/>`
			+ `<feFlood style="flood-color:var(--ic-sh)" flood-opacity="0.55"/><feComposite in2="db" operator="in" result="o"/>`
			+ `<feGaussianBlur in="SourceAlpha" stdDeviation="3" result="s"/><feOffset in="s" dy="1.6" result="so"/>`
			+ `<feFlood style="flood-color:var(--ic-sh)" flood-opacity="0.5"/><feComposite in2="so" operator="in" result="ss"/>`
			+ `<feMerge><feMergeNode in="ss"/><feMergeNode in="o"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
		body = `<g filter="url(#${pre}-sh)">${icon}</g>`;
	} else if (style === 'plein') {
		defs = `<linearGradient id="${pre}-pd" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--ic-a1)"/><stop offset="1" style="stop-color:var(--ic-a2)"/></linearGradient>`
			+ `<radialGradient id="${pre}-ph" cx="0.32" cy="0.16" r="0.78"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.42"/><stop offset="0.55" stop-color="#FFFFFF" stop-opacity="0.06"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>`
			+ `<filter id="${pre}-ps" filterUnits="userSpaceOnUse" x="-30" y="-30" width="160" height="170"><feDropShadow dx="0" dy="3" stdDeviation="3.4" flood-color="#000000" flood-opacity="0.4"/></filter>`;
		body = `<circle cx="50" cy="50" r="46" fill="url(#${pre}-pd)" filter="url(#${pre}-ps)"/><circle cx="50" cy="50" r="46" fill="url(#${pre}-ph)"/>`
			+ `<circle cx="50" cy="50" r="45.3" fill="none" stroke="#FFFFFF" stroke-opacity="0.3" stroke-width="1.4"/>${icon}`;
	} else {
		const g = Math.max(w0, h0) * 0.05;
		defs = `<linearGradient id="${pre}-ig" gradientUnits="userSpaceOnUse" x1="${num(x0)}" y1="${num(y0)}" x2="${num(x0 + w0)}" y2="${num(y0 + h0)}"><stop offset="0" style="stop-color:var(--ic-al)"/><stop offset="1" style="stop-color:var(--ic-b)"/></linearGradient>`
			+ `<linearGradient id="${pre}-gf" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.3"/><stop offset="0.5" stop-color="#FFFFFF" stop-opacity="0.07"/><stop offset="1" style="stop-color:var(--ic-b)" stop-opacity="0.16"/></linearGradient>`
			+ `<linearGradient id="${pre}-ge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.95"/><stop offset="0.32" stop-color="#FFFFFF" stop-opacity="0.32"/><stop offset="0.68" stop-color="#FFFFFF" stop-opacity="0.06"/><stop offset="1" style="stop-color:var(--ic-b)" stop-opacity="0.75"/></linearGradient>`
			+ `<linearGradient id="${pre}-gl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.55"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>`
			+ `<clipPath id="${pre}-gc"><rect x="6" y="6" width="88" height="88" rx="22"/></clipPath>`
			+ `<filter id="${pre}-gg" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="7"/></filter>`
			+ `<filter id="${pre}-igf" filterUnits="userSpaceOnUse" x="${num(x0 - w0 * 0.5)}" y="${num(y0 - h0 * 0.5)}" width="${num(w0 * 2)}" height="${num(h0 * 2)}" color-interpolation-filters="sRGB">`
			+ `<feGaussianBlur in="SourceAlpha" stdDeviation="${num(g)}" result="b"/><feFlood style="flood-color:var(--ic-glow)" flood-opacity="0.9"/>`
			+ `<feComposite in2="b" operator="in" result="l"/><feMerge><feMergeNode in="l"/><feMergeNode in="SourceGraphic"/></feMerge></filter>`;
		// ombre portee, lueur en anneau (autour et sur les bords, jamais au centre : l'icone reste lisible), verre fume puis givre
		body = `<rect x="10" y="16" width="80" height="80" rx="24" fill="#000000" opacity="0.3" filter="url(#${pre}-gg)"/>`
			+ `<rect x="6" y="6" width="88" height="88" rx="22" fill="none" style="stroke:var(--ic-glow)" stroke-width="7" opacity="0.6" filter="url(#${pre}-gg)"/>`
			+ `<rect x="6" y="6" width="88" height="88" rx="22" fill="#0B1022" opacity="0.3"/>`
			+ `<rect x="6" y="6" width="88" height="88" rx="22" fill="url(#${pre}-gf)"/>`
			+ `<g clip-path="url(#${pre}-gc)"><path d="M6 6H94V38C70 29 36 29 6 45Z" fill="url(#${pre}-gl)" opacity="0.6"/>`
			+ `<ellipse cx="74" cy="98" rx="42" ry="18" style="fill:var(--ic-b)" opacity="0.22" filter="url(#${pre}-gg)"/></g>`
			+ `<rect x="6.7" y="6.7" width="86.6" height="86.6" rx="21.3" fill="none" stroke="url(#${pre}-ge)" stroke-width="1.4"/>${icon}`;
	}
	const markup = `<svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false" style="display:block;width:100%;height:100%;overflow:visible">`
		+ `<defs>${defs}</defs>${body}</svg>`;
	return {markup, viewBox: [0, 0, 100, 100], ratio: 1, shapes, traits, stages, boucle: null, origine: '50% 50%'};
};
/** Carre de l'image d'une icone PNG dans la boite (en %), selon le style. */
export const iconBox = (style: IconStyle) => (style === 'trait' ? {x: 4, s: 92} : style === 'plein' ? {x: 25, s: 50} : {x: 24, s: 52});

const ICONS = new Map<string, VecSvg | null>();
/** Habillage memorise (par fichier, vecteur et style : ids stables d'une image a l'autre). */
export const preparedIcon = (url: string, prefix: string, style: IconStyle): VecSvg | null => {
	const png = isPngIcon(url);
	const text = png ? null : TEXTS.get(url);
	if (!png && !text) return null;
	const key = `${url}\n${prefix}\n${style}`;
	if (!ICONS.has(key)) ICONS.set(key, prepareIcon(png ? null : text!, style, prefix));
	return ICONS.get(key) ?? null;
};

/** Contenu d'une icone dans sa boite : verre givre (flou de l'arriere-plan, CSS), habillage SVG, image PNG eventuelle.
 * img : composant d'image (Img de Remotion dans la composition : l'export attend son chargement ; <img> dans l'interface).
 * size : cote de la boite en px (rayon du flou). */
export const IconView: React.FC<{svg: VecSvg; style: IconStyle; vars: Record<string, string>; size: number; png?: string | null;
	img?: React.ElementType; opacity?: number}> = ({svg, style, vars, size, png, img: ImgTag = 'img', opacity = 1}) => {
	const b = iconBox(style);
	// opacite posee sur chaque calque (pas sur un parent : un parent transparent couperait le flou du verre pendant un fondu)
	const op = opacity < 1 ? Math.max(0, opacity) : undefined;
	return (
		<div style={{position: 'relative', width: '100%', height: '100%', ...vars} as React.CSSProperties}>
			{style === 'verre' ? (
				<div style={{position: 'absolute', left: '6%', top: '6%', width: '88%', height: '88%', borderRadius: '25%', opacity: op,
					backdropFilter: `blur(${Math.max(2, size * 0.06).toFixed(1)}px) saturate(1.5) brightness(0.85)`,
					WebkitBackdropFilter: `blur(${Math.max(2, size * 0.06).toFixed(1)}px) saturate(1.5) brightness(0.85)`,
					background: 'rgba(255,255,255,0.04)'} as React.CSSProperties} />
			) : null}
			<div style={{position: 'absolute', inset: 0, opacity: op}} dangerouslySetInnerHTML={{__html: svg.markup}} />
			{png ? <ImgTag src={png} alt="" style={{position: 'absolute', left: `${b.x}%`, top: `${b.x}%`, width: `${b.s}%`, height: `${b.s}%`, objectFit: 'contain', opacity: op,
				filter: style === 'trait' ? `drop-shadow(0 ${(size * 0.012).toFixed(1)}px ${(size * 0.03).toFixed(1)}px rgba(0,0,0,0.55))` : undefined}} /> : null}
		</div>
	);
};

// ---------------------------------------------------------------- rendu ----------------------------------------------------------------
/** Style du conteneur d'un vecteur a l'instant t (position, taille, rotation, opacite, couleurs, trace). */
export const vectorBox = (reel: ReelDoc, v: VectorItem, svg: VecSvg, t: number, frame: {w: number; h: number}) => {
	// w = part du PETIT cote de l'image (comme les sous-titres et les graphismes) : meme taille apparente en 9:16 et en
	// 16:9 (identique a l'ancienne regle en 9:16, 4:5 et 1:1, ou le petit cote est la largeur)
	const w = Math.max(1, v.w * Math.min(frame.w, frame.h));
	const h = w * svg.ratio;
	const motion = vectorMotion(v, t, frame, {w, h}, svg.stages, cueFor(reel, {type: 'vector', id: v.id}));
	const icone = iconStyleOf(v);
	const vars: Record<string, string> = {...colorVars(vectorColors(reel, v)), ...(icone ? iconVars(reel, v, icone) : {})};
	motion.dash.forEach((d, i) => (vars[`--v-trace-${i + 1}`] = d.toFixed(4)));
	const outer = {
		position: 'absolute', left: v.x * frame.w - w / 2, top: v.y * frame.h - h / 2, width: w, height: h, pointerEvents: 'none',
		opacity: Math.max(0, Math.min(1, v.opacite ?? 1)) * motion.opacity,
		transform: `translate(${motion.tx.toFixed(2)}px, ${motion.ty.toFixed(2)}px) scale(${motion.scale.toFixed(4)}) rotate(${Number(v.rotation) || 0}deg)`,
		...vars,
	} as React.CSSProperties;
	const inner = {width: '100%', height: '100%', transform: loopTransform(svg.boucle, t - v.at) || undefined, transformOrigin: svg.origine} as React.CSSProperties;
	return {outer, inner, motion};
};

/** Calque des vecteurs : chaque vecteur visible (non propose) a l'instant t, dans <Choreo cible={{type: 'vector', id}}>.
 * Icones (meta.icone ou dossiers d'icones) : habillage trait / plein / verre (prepareIcon) ; PNG par <Img> (l'export attend
 * l'image). */
export const VectorLayer: React.FC<{reel: ReelDoc; t: number; total: number; assetBase: string}> = ({reel, t, assetBase}) => {
	const {width, height} = useVideoConfig();
	const list = (reel.vectors ?? []).filter((v) => !v.suggested && (safeAsset(v.asset) || iconStyleOf(v)));
	const urls = [...new Set(list.filter((v) => !isPngIcon(v.asset)).map((v) => vectorUrl(assetBase, v.asset)))];
	useVectorTexts(urls);
	const frame = {w: width, h: height};
	return (
		<>
			{list.filter((v) => t >= v.at && t < v.at + v.duration && (v.opacite ?? 1) > 0).map((v) => {
				const url = vectorUrl(assetBase, v.asset);
				const icone = iconStyleOf(v);
				const svg = icone ? preparedIcon(url, `v${v.id}`, icone) : preparedVector(url, `v${v.id}`);
				if (!svg) return null;
				const {outer, inner} = vectorBox(reel, v, svg, t, frame);
				// verre : l'opacite (entree, sortie, reglage) passe aux calques de l'icone, pas au conteneur (flou garde)
				const verre = icone === 'verre';
				const cible = {type: 'vector', id: v.id} as const;
				const corps = (fondu: number) => (
					<div style={verre ? {...outer, opacity: 1} : outer} data-vecteur={v.id}>
						{icone ? (
							<div style={inner}>
								<IconView svg={svg} style={icone} vars={{}} size={Number(outer.width) || 100} png={isPngIcon(v.asset) ? url : null} img={Img}
									opacity={verre ? Number(outer.opacity) * fondu : 1} />
							</div>
						) : <div style={inner} dangerouslySetInnerHTML={{__html: svg.markup}} />}
					</div>
				);
				// verre + mouvement de la choregraphie : meme enveloppe que <Choreo> (deplacement, zoom, rideau), mais son
				// opacite va elle aussi aux calques (un parent transparent couperait le flou du verre pendant le fondu)
				const cue = verre ? cueFor(reel, cible) : null;
				if (cue && !(cue.entree.type === 'aucune' && cue.sortie.type === 'aucune')) {
					const env = animateElement(cue, t, v.at, v.duration, placeOf(reel, cible));
					return (
						<AbsoluteFill key={v.id} style={{transform: env.transform || undefined, transformOrigin: env.transformOrigin, clipPath: env.clipPath,
							'--choreo-trace': env.trace ?? 1} as React.CSSProperties}>
							{corps(Math.max(0, Math.min(1, env.opacity)))}
						</AbsoluteFill>
					);
				}
				return (
					<Choreo key={v.id} reel={reel} cible={cible} t={t} at={v.at} duration={v.duration}>
						{corps(1)}
					</Choreo>
				);
			})}
		</>
	);
};
