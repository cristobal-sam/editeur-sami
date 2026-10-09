// Choregraphie V2 (cote image) — FICHIER DE L'AGENT « choregraphie » (voir docs/direction-creative-v2/SPEC.md).
// Chaque element (graphismes, scenes du style, plans de coupe, bandeau, sous-titres ; les vecteurs via vectors.tsx) est
// rendu DANS <Choreo>. Sans mouvement (cue) pour cet element, <Choreo> rend ses enfants tels quels : image identique a
// avant la V2 (anciens reels inchanges).
// Contrat : pur (aucun etat, aucun effet), meme resultat dans l'apercu et l'export ; le temps de la cible fait foi
// (at/duration passes par l'appelant), le cue ne donne que la maniere d'entrer/sortir (type, direction, duree, courbe).
// Le mouvement s'AJOUTE a l'animation propre de l'element : enveloppe AbsoluteFill (opacite, translation, echelle,
// decoupe pour le trace), sans aucun decalage de mise en page.
import React from 'react';
import {AbsoluteFill} from 'remotion';
import {brollMode, designScenes, insetBox, isStudioCard, pages, studioCardSize, studioGraphicSpot, studioMode} from './timeline';
import type {Cue, CueMove, CueTarget, ReelDoc} from './types';

/** Enveloppe d'animation appliquee par-dessus l'animation propre de l'element.
 * trace : progression du trace (0 -> 1), aussi exposee en variable CSS --choreo-trace (traits SVG .v-trait). */
export type Envelope = {opacity: number; transform: string; transformOrigin?: string; clipPath?: string; trace?: number};
export const IDENTITY: Envelope = {opacity: 1, transform: ''};

/** Place approximative de l'element dans l'image (0..1) : centre (x, y), demi-largeur/hauteur (hw, hh).
 * plein : l'element couvre toute l'image (plan de coupe plein ecran) ; texte : sous-titres (mouvements plus discrets). */
export type Place = {x: number; y: number; hw: number; hh: number; plein?: boolean; texte?: boolean;
	/** l'element dessine lui-meme son trace (vecteurs : vectors.tsx trace les traits) : pas de decoupe ici. */
	traceNatif?: boolean};
const CENTRE: Place = {x: 0.5, y: 0.5, hw: 0.42, hh: 0.12};

/** Cle d'une cible (« type:id »), commune a la piste, au panneau et au moteur. */
export const targetKey = (c: CueTarget) => `${c.type}:${c.id}`;

/** Le mouvement actif (non desactive) qui vise cet element, ou null. */
export const cueFor = (reel: ReelDoc, cible: CueTarget): Cue | null =>
	reel.choreography?.cues?.find((c) => !c.desactive && c.cible.type === cible.type && c.cible.id === cible.id) ?? null;

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));

/** Courbes : douce = arrivee en douceur ; rapide = depart vif, arrivee nette ; rebond = depasse un peu puis se pose ;
 * lineaire = vitesse constante. x : progression 0..1 -> 0..1 (rebond depasse 1 un instant). */
export const ease = (courbe: CueMove['courbe'], x: number) => {
	const p = clamp01(x);
	if (courbe === 'lineaire') return p;
	if (courbe === 'rapide') return 1 - Math.pow(1 - p, 5);
	if (courbe === 'rebond') {
		const c1 = 1.4;
		const c3 = c1 + 1;
		return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2);
	}
	return 1 - Math.pow(1 - p, 3);
};

/** Durees effectives [entree, sortie] (s) : reduites ensemble si l'element est trop court pour les deux. */
export const cueDurations = (cue: Cue, duration: number): [number, number] => {
	let din = cue.entree.type === 'aucune' ? 0 : Math.max(0, cue.entree.duree || 0);
	let dout = cue.sortie.type === 'aucune' ? 0 : Math.max(0, cue.sortie.duree || 0);
	const room = Math.max(0.001, duration) * 0.9;
	if (din + dout > room) {
		const k = room / (din + dout);
		din *= k;
		dout *= k;
	}
	return [din, dout];
};

/** Place de l'element vise (pour l'origine du zoom/pop et le trace). */
export const placeOf = (reel: ReelDoc, cible: CueTarget): Place => {
	switch (cible.type) {
		case 'caption':
			return {x: 0.5, y: reel.style?.position ?? 0.7, hw: 0.43, hh: 0.06, texte: true};
		case 'banner':
			return {x: 0.5, y: 0.14, hw: 0.43, hh: 0.05};
		case 'design': {
			// place affichee (studio Tech 3D : posee hors de la personne par designScenes), sinon celle enregistree
			const s = designScenes(reel).find((x) => x.id === cible.id) ?? reel.styleScenes?.find((x) => x.id === cible.id);
			if (s && isStudioCard(reel, s.kind)) {
				// carte du studio : son vrai gabarit (le trace la revele en entier, sans saut du bord a la fin)
				const size = studioCardSize(s.kind, s.text, s.secondary);
				const u = Math.min(reel.width, reel.height);
				return {x: s.x ?? 0.5, y: s.y ?? 0.5, hw: Math.min(0.5, (size.w * u * (s.scale || 1)) / reel.width / 2 + 0.01),
					hh: Math.min(0.5, (size.h * u * (s.scale || 1)) / reel.height / 2 + 0.01)};
			}
			return s ? {x: s.x ?? 0.5, y: s.y ?? 0.5, hw: Math.min(0.5, 0.41 * (s.scale || 1)), hh: 0.12} : CENTRE;
		}
		case 'vector': {
			const v = reel.vectors?.find((x) => x.id === cible.id);
			if (!v) return CENTRE;
			// v.w = part du petit cote de l'image (vectors.tsx) -> demi-largeur en part de la largeur
			const hw = Math.max(0.02, ((v.w ?? 0.3) * Math.min(reel.width, reel.height)) / Math.max(1, reel.width) / 2);
			return {x: v.x ?? 0.5, y: v.y ?? 0.5, hw, hh: hw * (reel.width / Math.max(1, reel.height)), traceNatif: true};
		}
		case 'broll': {
			const b = reel.broll?.find((x) => x.id === cible.id);
			if (b && (b.mode ?? brollMode(reel, b.source)) === 'encadre') {
				const box = insetBox(reel);
				return {x: (box.left + box.width / 2) / reel.width, y: (box.top + box.height / 2) / reel.height,
					hw: box.width / 2 / reel.width, hh: box.height / 2 / reel.height};
			}
			return {x: 0.5, y: 0.5, hw: 0.5, hh: 0.5, plein: true};
		}
		case 'graphics': {
			const g = reel.graphics?.find((x) => x.id === cible.id);
			if (!g) return CENTRE;
			const y = typeof g.props?.y === 'number' ? g.props.y : null;
			if (g.kind === 'chiffre') {
				// studio Tech 3D : place calculee hors de la personne (meme calcul que graphics.tsx), sinon la place enregistree
				const p = studioGraphicSpot(reel, g);
				if (!studioMode(reel)) return {x: p.x, y: p.y, hw: 0.4, hh: 0.09};
				const size = studioCardSize('chiffre');
				const u = Math.min(reel.width, reel.height);
				return {x: p.x, y: p.y, hw: Math.min(0.5, (size.w * u * p.scale) / reel.width / 2), hh: Math.min(0.5, (size.h * u * p.scale) / reel.height / 2)};
			}
			if (g.kind === 'coches') return {x: 0.5, y: (y ?? 0.22) + 0.1, hw: 0.4, hh: 0.12};
			if (g.kind === 'carte') return {x: g.props?.side === 'gauche' ? 0.37 : 0.63, y: (y ?? 0.16) + 0.14, hw: 0.31, hh: 0.15};
			return {x: 0.5, y: 0.5, hw: 0.45, hh: 0.12};
		}
	}
	return CENTRE;
};

type Acc = {opacity: number; tx: number; ty: number; scale: number; clip: [number, number, number, number] | null; trace: number};

/** Applique un mouvement a la progression k (0 = hors de l'image, 1 = en place). direction : d'ou il vient (entree) ou
 * ou il va (sortie). Translations en % de l'image (l'enveloppe couvre toute l'image). */
const applyMove = (m: CueMove, k: number, place: Place, acc: Acc) => {
	const vis = clamp01(k);
	const soft = place.texte ? 0.55 : 1;
	switch (m.type) {
		case 'fondu':
			acc.opacity *= vis;
			break;
		case 'glisse': {
			const d = 1 - k;
			const dir = m.direction ?? 'bas';
			if (dir === 'gauche') acc.tx -= 14 * soft * d;
			else if (dir === 'droite') acc.tx += 14 * soft * d;
			else if (dir === 'haut') acc.ty -= 8 * soft * d;
			else acc.ty += 8 * soft * d;
			acc.opacity *= clamp01(vis * 1.6);
			break;
		}
		case 'zoom': {
			const s0 = place.plein ? 1.1 : place.texte ? 0.9 : 0.86;
			acc.scale *= s0 + (1 - s0) * k;
			acc.opacity *= clamp01(vis * 1.4);
			break;
		}
		case 'pop': {
			const s0 = place.texte ? 0.8 : place.plein ? 0.92 : 0.5;
			acc.scale *= Math.max(0.01, s0 + (1 - s0) * k);
			acc.opacity *= clamp01(vis * 3);
			break;
		}
		case 'trace': {
			// l'element se revele (decoupe) dans le sens du trace, sur sa propre largeur ; un vecteur trace lui-meme ses traits
			// (vectors.tsx lit le mouvement) : seule la progression est donnee (--choreo-trace)
			acc.trace = Math.min(acc.trace, vis);
			if (place.traceNatif) break;
			const dir = m.direction ?? 'gauche';
			const left = (place.x - place.hw) * 100;
			const right = (place.x + place.hw) * 100;
			const top = (place.y - place.hh) * 100;
			const bottom = (place.y + place.hh) * 100;
			const c: [number, number, number, number] = [0, 0, 0, 0]; // haut, droite, bas, gauche (inset en %)
			if (dir === 'gauche') c[1] = Math.max(0, 100 - (left + (right - left) * vis));
			else if (dir === 'droite') c[3] = Math.max(0, right - (right - left) * vis);
			else if (dir === 'haut') c[2] = Math.max(0, 100 - (top + (bottom - top) * vis));
			else c[0] = Math.max(0, bottom - (bottom - top) * vis);
			acc.clip = acc.clip ? acc.clip.map((v, i) => Math.max(v, c[i])) as [number, number, number, number] : c;
			break;
		}
		default:
			break;
	}
};

/** Enveloppe d'un element a l'instant t (temps du montage) ; at/duration = temps de l'element (fait foi). */
export const animateElement = (cue: Cue | null, t: number, at: number, duration: number, place: Place = CENTRE): Envelope => {
	if (!cue || cue.desactive) return IDENTITY;
	const [din, dout] = cueDurations(cue, duration);
	if (!din && !dout) return IDENTITY;
	const local = t - at;
	const acc: Acc = {opacity: 1, tx: 0, ty: 0, scale: 1, clip: null, trace: 1};
	let moving = false;
	if (din > 0 && local < din) {
		applyMove(cue.entree, ease(cue.entree.courbe, local / din), place, acc);
		moving = true;
	}
	const rest = duration - local;
	if (dout > 0 && rest < dout) {
		applyMove(cue.sortie, ease(cue.sortie.courbe, rest / dout), place, acc);
		moving = true;
	}
	if (!moving) return IDENTITY;
	const parts: string[] = [];
	if (acc.tx || acc.ty) parts.push(`translate(${acc.tx.toFixed(3)}%, ${acc.ty.toFixed(3)}%)`);
	if (acc.scale !== 1) parts.push(`scale(${acc.scale.toFixed(4)})`);
	const env: Envelope = {opacity: clamp01(acc.opacity), transform: parts.join(' ')};
	if (acc.scale !== 1) env.transformOrigin = `${(place.x * 100).toFixed(2)}% ${(place.y * 100).toFixed(2)}%`;
	if (acc.clip) env.clipPath = `inset(${acc.clip.map((v) => `${v.toFixed(2)}%`).join(' ')})`;
	if (acc.trace < 1) env.trace = acc.trace;
	return env;
};

/** Temps de chaque cible dans le montage (cle « type:id » -> {at, duration}) : pour la piste de la timeline. Meme
 * calcul que l'image (designScenes, pages de sous-titres) ; les cibles absentes ou masquees n'y sont pas. */
export const targetTimes = (reel: ReelDoc, total?: number): Map<string, {at: number; duration: number}> => {
	const m = new Map<string, {at: number; duration: number}>();
	for (const g of reel.graphics ?? []) if (!g.suggested) m.set(`graphics:${g.id}`, {at: g.at, duration: g.duration});
	for (const b of reel.broll ?? []) m.set(`broll:${b.id}`, {at: b.at, duration: b.duration});
	for (const v of reel.vectors ?? []) if (!v.suggested) m.set(`vector:${v.id}`, {at: v.at, duration: v.duration});
	for (const s of designScenes(reel)) m.set(`design:${s.id}`, {at: s.at, duration: s.end - s.at});
	if (reel.choreography?.cues?.some((c) => c.cible.type === 'caption')) {
		for (const p of pages(reel)) m.set(`caption:${p.words[0].clip}:${p.words[0].index}`, {at: p.start, duration: p.end - p.start});
	}
	const b = reel.banner;
	const end = b?.end ?? total;
	if (b?.enabled && b.text?.trim() && end !== undefined && end > b.start) m.set('banner:banner', {at: b.start, duration: end - b.start});
	return m;
};

/** Enveloppe un element. Sans mouvement actif : rend les enfants tels quels (aucune div ajoutee, aucun decalage). */
export const Choreo: React.FC<{reel: ReelDoc; cible: CueTarget; t: number; at: number; duration: number; children?: React.ReactNode}> = ({reel, cible, t, at, duration, children}) => {
	const cue = cueFor(reel, cible);
	if (!cue || (cue.entree.type === 'aucune' && cue.sortie.type === 'aucune')) return <>{children}</>;
	const env = animateElement(cue, t, at, duration, placeOf(reel, cible));
	const style: React.CSSProperties & Record<'--choreo-trace', number> = {
		opacity: env.opacity,
		transform: env.transform || undefined,
		transformOrigin: env.transformOrigin,
		clipPath: env.clipPath,
		'--choreo-trace': env.trace ?? 1,
	};
	return <AbsoluteFill style={style}>{children}</AbsoluteFill>;
};
