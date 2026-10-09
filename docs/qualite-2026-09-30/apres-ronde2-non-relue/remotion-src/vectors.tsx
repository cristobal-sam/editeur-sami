// Vecteurs V2 (SVG recolorables de la banque) — FICHIER DE L'AGENT « vecteurs » (voir docs/direction-creative-v2/SPEC.md §2.5, §9.3).
// Insere une fois par l'architecte dans Reel.tsx, au-dessus des graphismes et sous les scenes du style, le bandeau et les
// sous-titres. Les SVG sont dans assets/banque/vecteurs/ (servis a `${assetBase}/banque/vecteurs/...` dans l'apercu comme a
// l'export) et sont INSERES EN LIGNE (jamais en <img>) : les couleurs passent par les variables CSS --v-principale,
// --v-secondaire, --v-contour posees sur le conteneur, les formes du fichier ne sont jamais modifiees.
// Meme rendu apercu / export : texte du SVG charge une fois (delayRender : l'export attend qu'il soit la), nettoye
// (aucun script, aucun style global, aucune ressource externe), animation calculee uniquement a partir du temps t.
import React, {useEffect, useRef, useState} from 'react';
import {continueRender, delayRender, useVideoConfig} from 'remotion';
import type {Cue, ReelDoc, VectorItem} from './types';
import {Choreo, cueFor} from './choreo';

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
 * null si ce n'est pas un SVG exploitable (pas de viewBox ni de taille). */
export const prepareSvg = (text: string, prefix = 'v'): VecSvg | null => {
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

// ---------------------------------------------------------------- rendu ----------------------------------------------------------------
/** Style du conteneur d'un vecteur a l'instant t (position, taille, rotation, opacite, couleurs, trace). */
export const vectorBox = (reel: ReelDoc, v: VectorItem, svg: VecSvg, t: number, frame: {w: number; h: number}) => {
	// w = part du PETIT cote de l'image (comme les sous-titres et les graphismes) : meme taille apparente en 9:16 et en
	// 16:9 (identique a l'ancienne regle en 9:16, 4:5 et 1:1, ou le petit cote est la largeur)
	const w = Math.max(1, v.w * Math.min(frame.w, frame.h));
	const h = w * svg.ratio;
	const motion = vectorMotion(v, t, frame, {w, h}, svg.stages, cueFor(reel, {type: 'vector', id: v.id}));
	const vars: Record<string, string> = colorVars(vectorColors(reel, v));
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

/** Calque des vecteurs : chaque vecteur visible (non propose) a l'instant t, dans <Choreo cible={{type: 'vector', id}}>. */
export const VectorLayer: React.FC<{reel: ReelDoc; t: number; total: number; assetBase: string}> = ({reel, t, assetBase}) => {
	const {width, height} = useVideoConfig();
	const list = (reel.vectors ?? []).filter((v) => !v.suggested && safeAsset(v.asset));
	const urls = [...new Set(list.map((v) => vectorUrl(assetBase, v.asset)))];
	useVectorTexts(urls);
	const frame = {w: width, h: height};
	return (
		<>
			{list.filter((v) => t >= v.at && t < v.at + v.duration && (v.opacite ?? 1) > 0).map((v) => {
				const svg = preparedVector(vectorUrl(assetBase, v.asset), `v${v.id}`);
				if (!svg) return null;
				const {outer, inner} = vectorBox(reel, v, svg, t, frame);
				return (
					<Choreo key={v.id} reel={reel} cible={{type: 'vector', id: v.id}} t={t} at={v.at} duration={v.duration}>
						<div style={outer} data-vecteur={v.id}>
							<div style={inner} dangerouslySetInnerHTML={{__html: svg.markup}} />
						</div>
					</Choreo>
				);
			})}
		</>
	);
};
