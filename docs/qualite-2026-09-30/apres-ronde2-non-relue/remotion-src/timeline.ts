// Calcul du montage : UNE seule implementation, utilisee par l'apercu (navigateur) et par l'export (Node).
// Ce fichier ne doit importer que des types (Node l'execute directement en retirant les types).
import type {Anchor, Annotation, Clip, CreativeBeat, Cutout, Graphic, ReelDoc, Segment, Word, StyleScene} from './types';

export type TimedWord = Word & {clip: string; index: number; outStart: number; outEnd: number};
export type Page = {words: TimedWord[]; start: number; end: number};
export type SfxEvent = {t: number; name: string; volume: number; kind: string};
export type AudioSegment = Segment & {fadeIn: number; fadeOut: number};

const TIGHT_GAP = 0.45;
const KEEP_BEFORE = 0.12;
const KEEP_AFTER = 0.15;
const CUT_PAD_BEFORE = 0.08;
const CUT_PAD_AFTER = 0.1;

const round = (t: number, fps: number) => Math.round(t * fps) / fps;

/** Recolle les morceaux que Whisper separe : « Est -ce » -> « Est-ce ». */
export const mergeFragments = <T extends {w: string; start: number; end: number}>(words: T[]): T[] => {
	const out: T[] = [];
	for (const w of words) {
		const text = w.w.trim();
		const last = out[out.length - 1];
		if (last && ("'’-".includes(text[0] ?? '') || /['’-]$/.test(last.w))) out[out.length - 1] = {...last, w: last.w + text, end: w.end};
		else out.push({...w, w: text});
	}
	return out;
};

/** Portions d'une prise gardees dans un plan : on retire les mots coupes et, si demande, les pauses. */
const clipRanges = (clip: Clip): [number, number][] => {
	const words = clip.words;
	if (!words.length) return [[clip.in, clip.out]];
	const runs: {words: Word[]; cutBefore: boolean; cutAfter: boolean}[] = [];
	let cur: Word[] = [];
	let cutBefore = false;
	words.forEach((w) => {
		if (w.cut) {
			if (cur.length) runs.push({words: cur, cutBefore, cutAfter: true});
			cur = [];
			cutBefore = true;
		} else cur.push(w);
	});
	if (cur.length) runs.push({words: cur, cutBefore, cutAfter: false});
	const ranges: [number, number][] = [];
	for (const run of runs) {
		const start = run.cutBefore ? run.words[0].start - CUT_PAD_BEFORE : clip.in;
		const end = run.cutAfter ? run.words[run.words.length - 1].end + CUT_PAD_AFTER : clip.out;
		let a = Math.max(clip.in, start);
		if (clip.tighten) {
			for (let i = 1; i < run.words.length; i++) {
				const prev = run.words[i - 1];
				const next = run.words[i];
				if (next.start - prev.end > TIGHT_GAP) {
					ranges.push([a, prev.end + KEEP_AFTER]);
					a = next.start - KEEP_BEFORE;
				}
			}
		}
		ranges.push([a, Math.min(clip.out, end)]);
	}
	return ranges.filter(([a, b]) => b - a > 0.05);
};

/** Duree d'un segment dans la video montee (tient compte de la vitesse). */
export const segLen = (s: Segment) => (s.src_out - s.src_in) / (s.speed ?? 1);

/** Segments du montage dans la prise du plan (celle du son), duree en images entieres : aucune derive. */
export const baseSegments = (reel: ReelDoc): Segment[] => {
	const out: Segment[] = [];
	let t = 0;
	for (const clip of reel.clips) {
		const speed = clip.speed && clip.speed > 0 ? clip.speed : 1;
		for (const [a, b] of clipRanges(clip)) {
			const d = Math.max(1, Math.round(((b - a) / speed) * reel.fps)) / reel.fps;
			const seg: Segment = {clip: clip.id, source: clip.source, src_in: a, src_out: a + d * speed, out_start: round(t, reel.fps), index: out.length};
			if (speed !== 1) seg.speed = speed;
			out.push(seg);
			t += d;
		}
	}
	return out;
};

/** Multicamera : decalage entre la prise du son et l'angle affiche (meme groupe synchronise), sinon null. */
export const angleShift = (reel: ReelDoc, clip: Clip): number | null => {
	if (!clip.angle || clip.angle === clip.source) return null;
	const a = reel.sources[clip.source]?.sync;
	const b = reel.sources[clip.angle]?.sync;
	if (!a || !b || a.group !== b.group) return null;
	return a.offset - b.offset;
};

/** Le plan tel qu'on le voit (angle multicamera applique) : pour le cadrage et la couleur. */
export const visualClip = (reel: ReelDoc, clip: Clip): Clip => {
	const shift = angleShift(reel, clip);
	return shift === null ? clip : {...clip, source: clip.angle!, in: clip.in + shift, out: clip.out + shift};
};

/** Segments d'image : ceux du montage, avec l'angle choisi pour les plans multicamera. */
export const videoSegments = (reel: ReelDoc): Segment[] => {
	const byClip = new Map(reel.clips.map((c) => [c.id, c]));
	return baseSegments(reel).map((s) => {
		const c = byClip.get(s.clip)!;
		const shift = angleShift(reel, c);
		return shift === null ? s : {...s, source: c.angle!, src_in: s.src_in + shift, src_out: s.src_out + shift};
	});
};

export const duration = (reel: ReelDoc) => {
	const s = baseSegments(reel);
	const last = s[s.length - 1];
	return last ? last.out_start + segLen(last) : 1;
};

/** Segments de son : identiques a l'image, sauf aux J-cuts / L-cuts entre deux plans ; plans muets retires. */
export const audioSegments = (reel: ReelDoc): AudioSegment[] => {
	const segs: AudioSegment[] = baseSegments(reel).map((s) => ({...s, fadeIn: 0.015, fadeOut: 0.015}));
	const byClip = new Map(reel.clips.map((c) => [c.id, c]));
	for (let i = 1; i < segs.length; i++) {
		const a = segs[i - 1];
		const b = segs[i];
		if (a.clip === b.clip || a.speed || b.speed) continue;
		const ca = byClip.get(a.clip)!;
		const cb = byClip.get(b.clip)!;
		if (ca.mute || cb.mute) continue;
		const srcB = reel.sources[cb.source];
		const srcA = reel.sources[ca.source];
		// J-cut : le son de B arrive avant son image (remplace la fin du son de A)
		const lead = Math.min(cb.audioLead ?? 0, a.src_out - a.src_in - 0.1, b.src_in);
		if (lead > 0.01) {
			a.src_out -= lead;
			b.src_in -= lead;
			b.out_start -= lead;
			a.fadeOut = b.fadeIn = 0.04;
		}
		// L-cut : le son de A continue sous l'image de B
		const tail = Math.min(ca.audioTail ?? 0, b.src_out - b.src_in - 0.1, (srcA?.duration ?? 1e9) - a.src_out);
		if (tail > 0.01) {
			a.src_out += tail;
			b.src_in += tail;
			b.out_start += tail;
			a.fadeOut = b.fadeIn = 0.04;
		}
		void srcB;
	}
	return segs.filter((s) => !byClip.get(s.clip)?.mute);
};

/** Temps de la prise d'origine (prise du son) -> temps dans la video montee. */
export const toOut = (segments: Segment[], clip: string, t: number): number | null => {
	for (const s of segments) {
		if (s.clip === clip && t >= s.src_in - 0.03 && t <= s.src_out + 0.03) return s.out_start + (Math.min(Math.max(t, s.src_in), s.src_out) - s.src_in) / (s.speed ?? 1);
	}
	return null;
};

export const timedWords = (reel: ReelDoc, segments = baseSegments(reel)): TimedWord[] => {
	const out: TimedWord[] = [];
	for (const clip of reel.clips) {
		clip.words.forEach((w, index) => {
			if (w.cut) return;
			const s = toOut(segments, clip.id, w.start);
			const e = toOut(segments, clip.id, w.end);
			if (s === null || e === null) return;
			out.push({...w, clip: clip.id, index, outStart: s, outEnd: Math.max(e, s + 0.05)});
		});
	}
	return out.sort((a, b) => a.outStart - b.outStart);
};

/** Groupes de mots affiches ensemble (coupe sur la ponctuation, les pauses et le nombre de mots). */
export const pages = (reel: ReelDoc): Page[] => {
	const words = timedWords(reel).filter((w) => !w.hide && w.w.trim());
	const result: Page[] = [];
	let cur: TimedWord[] = [];
	const flush = () => {
		if (cur.length) result.push({words: cur, start: cur[0].outStart, end: cur[cur.length - 1].outEnd});
		cur = [];
	};
	for (const w of words) {
		const prev = cur[cur.length - 1];
		if (prev && (cur.length >= reel.style.maxWords || /[.!?…]$/.test(prev.w) || w.outStart - prev.outEnd > 0.35 || prev.clip !== w.clip)) flush();
		cur.push(w);
	}
	flush();
	result.forEach((p, i) => {
		const next = result[i + 1];
		p.end = next ? Math.min(next.start, p.end + 0.6) : p.end + 0.4;
	});
	return result;
};

export const displayWord = (w: string, uppercase: boolean) => {
	const t = w.replace(/[«»"“”]/g, '').replace(/[,.;:…]+$/g, '').trim();
	return uppercase ? t.toLocaleUpperCase('fr-CA') : t;
};

/** Sous-titres au format SRT (pour Resolve, Premiere, YouTube...). */
export const srt = (reel: ReelDoc) => {
	const ts = (t: number) => {
		const ms = Math.max(0, Math.round(t * 1000));
		const p = (n: number, l = 2) => String(n).padStart(l, '0');
		return `${p(Math.floor(ms / 3600000))}:${p(Math.floor(ms / 60000) % 60)}:${p(Math.floor(ms / 1000) % 60)},${p(ms % 1000, 3)}`;
	};
	return pages(reel)
		.map((p, i) => `${i + 1}\n${ts(p.start)} --> ${ts(p.end)}\n${p.words.map((w) => displayWord(w.w, false)).join(' ')}\n`)
		.join('\n');
};

export const segmentAt = (segments: Segment[], t: number) => {
	let idx = 0;
	for (let i = 0; i < segments.length; i++) if (segments[i].out_start <= t + 1e-6) idx = i;
	return idx;
};

/** Debut de chaque nouvelle partie du script (flash, transition sonore). */
export const blockStarts = (reel: ReelDoc, segments = baseSegments(reel)): {t: number; block: string}[] => {
	const blockOf = new Map(reel.clips.map((c) => [c.id, c.block]));
	const out: {t: number; block: string}[] = [];
	segments.forEach((s, i) => {
		const b = blockOf.get(s.clip) ?? '';
		if (i > 0 && blockOf.get(segments[i - 1].clip) !== b) out.push({t: s.out_start, block: b});
	});
	return out;
};

/** Centre du visage dans un segment (pour les zooms). */
export const faceAt = (reel: ReelDoc, seg: Segment) => {
	const s = reel.sources[seg.source]?.samples ?? [];
	const inside = s.filter((x) => x[0] >= seg.src_in && x[0] <= seg.src_out);
	if (!inside.length) return {cx: 0.5, cy: 0.4};
	const med = (k: number) => inside.map((x) => x[k]).sort((a, b) => a - b)[Math.floor(inside.length / 2)];
	return {cx: med(1), cy: med(2)};
};

// ---------- Couleur : harmonisation des prises ----------
const median = (v: number[]) => (v.length ? [...v].sort((a, b) => a - b)[Math.floor(v.length / 2)] : 0);
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

type ClipStats = {luma: number; r: number; g: number; b: number};
const clipStats = (reel: ReelDoc, clip: Clip): ClipStats | null => {
	const s = (reel.sources[clip.source]?.samples ?? []).filter((x) => x[0] >= clip.in && x[0] <= clip.out && x[3] > 0);
	if (s.length < 2) return null;
	return {luma: median(s.map((x) => x[3])), r: median(s.map((x) => x[4])), g: median(s.map((x) => x[5])), b: median(s.map((x) => x[6]))};
};

/** Reference = mediane des plans du montage ; chaque plan y est ramene (exposition + balance des blancs). */
export const colorReference = (reel: ReelDoc): ClipStats | null => {
	const all = reel.clips.map((c) => clipStats(reel, visualClip(reel, c))).filter(Boolean) as ClipStats[];
	if (!all.length) return null;
	return {luma: median(all.map((x) => x.luma)), r: median(all.map((x) => x.r / x.luma)), g: median(all.map((x) => x.g / x.luma)), b: median(all.map((x) => x.b / x.luma))};
};

/** Multiplicateurs R, G, B a l'instant t (temps de la prise) pour un plan. */
export const colorGains = (reel: ReelDoc, clip: Clip, t: number, ref: ClipStats | null): [number, number, number] => {
	const c = clip.color ?? {auto: true, exposure: 0, temperature: 0};
	let gr = 1;
	let gg = 1;
	let gb = 1;
	const st = c.auto && ref ? clipStats(reel, clip) : null;
	if (st && ref) {
		const gain = clamp(ref.luma / st.luma, 0.75, 1.35);
		gr = gain * clamp(ref.r / (st.r / st.luma), 0.85, 1.15);
		gg = gain * clamp(ref.g / (st.g / st.luma), 0.85, 1.15);
		gb = gain * clamp(ref.b / (st.b / st.luma), 0.85, 1.15);
		// Lissage des variations dans la prise (exposition automatique du telephone, nuages...)
		const near = (reel.sources[clip.source]?.samples ?? []).filter((x) => Math.abs(x[0] - t) <= 0.75 && x[3] > 0);
		if (near.length >= 2) {
			const local = near.reduce((a, x) => a + x[3], 0) / near.length;
			const g = 1 + 0.7 * (clamp(st.luma / local, 0.85, 1.18) - 1);
			gr *= g;
			gg *= g;
			gb *= g;
		}
	}
	const exp = Math.pow(2, c.exposure || 0);
	const temp = c.temperature || 0;
	return [gr * exp * (1 + 0.08 * temp), gg * exp, gb * exp * (1 - 0.08 * temp)];
};

// ---------- Son : musique et bruitages ----------
/** Intervalles ou quelqu'un parle (pour baisser la musique). */
export const speech = (reel: ReelDoc): [number, number][] => {
	const out: [number, number][] = [];
	for (const w of timedWords(reel, audioSegments(reel))) {
		const last = out[out.length - 1];
		if (last && w.outStart - last[1] < 0.35) last[1] = Math.max(last[1], w.outEnd);
		else out.push([w.outStart, w.outEnd]);
	}
	return out;
};

/** Volume de la musique : baisse pendant la parole, remonte dans les silences, fondu final. */
export const musicVolume = (reel: ReelDoc, t: number, ranges: [number, number][], total: number) => {
	const m = reel.music;
	if (!m?.enabled) return 0;
	let duck = 1;
	for (const [a, b] of ranges) {
		if (t >= a - 0.25 && t <= b + 0.35) {
			const inRamp = Math.min(1, (t - (a - 0.25)) / 0.25);
			const outRamp = Math.min(1, (b + 0.35 - t) / 0.35);
			duck = Math.min(duck, 1 - 0.55 * Math.min(inRamp, outRamp));
		}
	}
	// fin : fondu court (0,8 s) pour ne pas eteindre la musique pendant la derniere phrase
	return m.volume * duck * Math.min(1, Math.max(0, (total - t) / 0.8)) * Math.min(1, t / 0.4);
};

/** Gain par bruitage (mesure RMS des fichiers : tous ramenes vers -20 dB ; le « glitch » etait 16 dB trop fort). */
export const SFX_GAIN: Record<string, number> = {
	click: 2.2, 'declencheur-photo': 1.5, ding: 1.0, glitch: 0.15, impact: 0.34, 'pop-grave': 0.6, pop: 0.6,
	riser: 1.6, 'whoosh-court': 1.25, 'whoosh-descendant': 1.07, 'whoosh-long': 1.2,
};

/** Bruitages places automatiquement selon le style de montage. */
export const sfxEvents = (reel: ReelDoc): SfxEvent[] => {
	const s = reel.sfx;
	if (!s?.enabled) return [];
	const ev: SfxEvent[] = [];
	if (s.start) ev.push({t: 0, name: s.start, volume: s.volume, kind: 'debut'});
	const starts = blockStarts(reel);
	if (s.transition) for (const b of starts) ev.push({t: Math.max(0, b.t - (s.transition.startsWith('whoosh') ? 0.2 : 0)), name: s.transition, volume: s.volume, kind: 'transition'});
	if (s.cta && reel.ctaBlock) {
		const cta = starts.find((b) => b.block === reel.ctaBlock);
		if (cta && cta.t > 2) ev.push({t: cta.t - 1.6, name: s.cta, volume: s.volume * 0.8, kind: "appel a l'action"});
	}
	if (s.highlight) {
		let last = -99;
		for (const w of timedWords(reel)) {
			if (!w.hl || w.hide || w.outStart - last < s.highlightGap) continue;
			if (starts.some((b) => Math.abs(b.t - w.outStart) < 0.6)) continue;
			ev.push({t: w.outStart, name: s.highlight, volume: s.volume * 0.7, kind: 'mot cle'});
			last = w.outStart;
		}
	}
	for (const e of s.extra ?? []) ev.push({t: e.t, name: e.name, volume: s.volume * 0.8 * (e.gain ?? 1), kind: 'ajoute'});
	return ev.map((e) => ({...e, volume: e.volume * (SFX_GAIN[e.name] ?? 1)})).sort((a, b) => a.t - b.t);
};

// ---------- Recadrage (tous formats) ----------
/** Position lissee du sujet a l'instant t de la prise : piste de recadrage (qui parle) sinon visage principal. */
export const subjectAt = (reel: ReelDoc, source: string, t: number, from: number, to: number): {cx: number; cy: number} => {
	const src = reel.sources[source];
	const pts = (src?.track?.length ? src.track : src?.samples ?? []).filter((x) => x[0] >= from - 1 && x[0] <= to + 1);
	if (!pts.length) return {cx: 0.5, cy: 0.4};
	// moyenne ponderee (gaussienne ~0,6 s) : suit la personne sans trembler
	let sw = 0;
	let sx = 0;
	let sy = 0;
	for (const p of pts) {
		const w = Math.exp(-(((p[0] - t) / 0.6) ** 2));
		sw += w;
		sx += w * p[1];
		sy += w * p[2];
	}
	if (sw < 1e-3) return faceAt(reel, {clip: '', source, src_in: from, src_out: to, out_start: 0, index: 0});
	return {cx: sx / sw, cy: sy / sw};
};

/** Cadre du media dans l'image finale : taille et position (px) pour remplir le format en gardant le sujet. */
export const framing = (reel: ReelDoc, source: string, t: number, from: number, to: number) => {
	const src = reel.sources[source];
	const sw = src?.width ?? 1080;
	const sh = src?.height ?? 1920;
	const W = reel.width;
	const H = reel.height;
	const k = Math.max(W / sw, H / sh);
	const dw = sw * k;
	const dh = sh * k;
	const s = subjectAt(reel, source, t, from, to);
	// sujet centre horizontalement, yeux vers 40 % de la hauteur ; jamais de bord noir
	const left = clamp(W / 2 - s.cx * dw, W - dw, 0);
	const top = clamp(H * 0.42 - s.cy * dh, H - dh, 0);
	return {left, top, width: dw, height: dh, cx: (s.cx * dw + left) / W, cy: (s.cy * dh + top) / H};
};

/** Plan de coupe d'une autre orientation que le montage (video horizontale dans un reel vertical) : encadre, net,
 * plutot qu'un plein ecran tres recadre et agrandi. Meme regle dans le moteur (broll.py). */
export const brollMode = (reel: ReelDoc, source: string): 'plein' | 'encadre' => {
	const s = reel.sources[source];
	if (!s?.width || !s?.height) return 'plein';
	const shape = (w: number, h: number) => (h > w * 1.05 ? 'v' : w > h * 1.05 ? 'h' : 'c');
	const r = shape(reel.width, reel.height);
	return r !== 'c' && shape(s.width, s.height) !== r ? 'encadre' : 'plein';
};

/** Cadre du plan de coupe encadre (px) : moitie droite qui deborde du bord (reel vertical), carte a droite sinon. */
export const insetBox = (reel: ReelDoc) => {
	const {width: W, height: H} = reel;
	return H > W * 1.05 ? {left: W * 0.49, top: H * 0.34, width: W * 0.56, height: H * 0.52}
		: {left: W * 0.55, top: H * 0.1, width: W * 0.4, height: H * 0.8};
};

/** Fichier d'un bruitage, relatif a assets/ : nom court (« whoosh-court ») = assets/sfx/editeur/<nom>.wav ; sinon chemin
 * relatif a assets/ (banque : « sfx/kenney/…/x.ogg », « banque/sons/x.wav »), sans jamais remonter (« .. » retire). */
export const sfxFile = (name: string) => (name.includes('/')
	? name.replace(/\\/g, '/').split('/').filter((p) => p && p !== '.' && p !== '..').join('/')
	: `sfx/editeur/${name}.wav`);

export type PlacedScene = StyleScene & {at: number; end: number};
/** Scènes ancrées à un mot (temps seulement, place enregistrée). */
const anchoredScenes = (reel: ReelDoc): PlacedScene[] => {
	if (reel.design?.enabled === false || !reel.design?.mode) return [];
	const words = timedWords(reel);
	const total = duration(reel);
	const result: PlacedScene[] = [];
	for (const scene of reel.styleScenes ?? []) {
		if (scene.hidden) continue;
		const word = words.find((w) => w.clip === scene.clip && w.index === scene.index && !w.hide);
		if (!word) continue;
		const at = Math.max(0, word.outStart);
		const end = Math.min(total, at + Math.max(.2, scene.duration));
		if (result.some((s) => at < s.end + .5 && end > s.at)) continue;
		result.push({...scene, at, end});
	}
	return result;
};
/** Empreinte rapide (FNV-1a) des champs dont dépendent les calculs gardés en mémoire : plans, mots (coupe, masque,
 * temps), format, scènes, habillage, zoom, graphismes, détourage, temps du récit. Un reel modifié EN PLACE (moteur,
 * tests, retouche qui garde le même objet) est donc recalculé ; les pistes d'analyse (sources) ne changent jamais en place. */
const fingerprint = (r: ReelDoc) => {
	let h = 2166136261;
	const num = (x: unknown) => {
		h = Math.imul(h ^ (typeof x === 'number' ? Math.round(x * 1000) | 0 : x ? 1 : x === undefined ? 2 : 0), 16777619);
	};
	const str = (x: string | null | undefined) => {
		if (x) for (let i = 0; i < x.length; i++) h = Math.imul(h ^ x.charCodeAt(i), 16777619);
		num(-1);
	};
	num(r.fps);
	num(r.width);
	num(r.height);
	for (const c of r.clips) {
		str(c.id);
		str(c.source);
		str(c.angle);
		num(c.in);
		num(c.out);
		num(c.speed);
		num(c.tighten);
		num(c.mute);
		for (const w of c.words) {
			num(w.start);
			num(w.end);
			num(w.cut);
			num(w.hide);
		}
	}
	const plan = r.creativePlan;
	str(JSON.stringify([r.styleScenes, r.design, r.zoom, r.graphics, r.cutouts, plan?.enabled, plan?.beats?.map((b) => [b.role, b.start, b.end, b.intensity]),
		plan?.storyboard?.map((s) => [s.engine, s.start, s.end])]));
	return h;
};
/** Calculs par reel gardés en mémoire, recalculés si le reel a changé (même objet modifié en place, voir fingerprint). */
const memo = <T>(cache: WeakMap<ReelDoc, {key: number; v: T}>, reel: ReelDoc, make: () => T): T => {
	const key = fingerprint(reel);
	const hit = cache.get(reel);
	if (hit && hit.key === key) return hit.v;
	const v = make();
	cache.set(reel, {key, v});
	return v;
};
const SCENES = new WeakMap<ReelDoc, {key: number; v: PlacedScene[]}>();
/** Scènes ancrées à un mot : une coupe de texte déplace ou retire automatiquement l'habillage. Studio Tech 3D : une
 * interface automatique est posée dans l'espace libre au-dessus (ou à côté) de la personne, jamais sur elle ; une scène
 * retouchée, posée à la main ou verrouillée garde exactement sa place. */
export const designScenes = (reel: ReelDoc): PlacedScene[] => memo(SCENES, reel, () => {
	const scenes = anchoredScenes(reel);
	if (!studioMode(reel)) return scenes;
	return scenes.map((s) => (s.manual || s.edited || s.locked || !STUDIO_KINDS.has(s.kind) ? s
		: {...s, ...studioSpot(reel, s.kind, s.at, s.end, {x: s.x, y: s.y, scale: s.scale}, studioCardSize(s.kind, s.text, s.secondary))}));
});

export const validCutout = (reel: ReelDoc, s: Segment) => {
	const m=reel.cutouts?.[s.clip];
	return m && m.source===s.source && m.proxy===reel.sources[s.source]?.proxy && m.start<=s.src_in+.02 && m.end>=s.src_out-.02 ? m : null;
};

/** Temps dans la prise (celle de l'image) d'un segment à l'instant t du montage. */
export const segSrcTime = (s: Segment, t: number) => s.src_in + Math.max(0, t - s.out_start) * (s.speed ?? 1);

/** Détourage jugé mauvais à cet instant de la prise (cutouts[clip].fallback, secondes dans la prise). */
export const cutoutFallback = (m: Cutout | null | undefined, srcT: number) => !!m?.fallback?.some(([a, b]) => srcT >= a && srcT < b);
const FALLBACK_RAMP = 0.12;
/** Part de la prise d'origine (0 : personne détourée ; 1 : prise d'origine) : fondu enchaîné de 0,12 s aux bords d'une
 * plage de repli, pour ne jamais sauter d'un rendu à l'autre. */
export const cutoutFallbackMix = (m: Cutout | null | undefined, srcT: number) => {
	let mix = 0;
	for (const [a, b] of m?.fallback ?? []) {
		if (srcT < a - FALLBACK_RAMP || srcT >= b + FALLBACK_RAMP) continue;
		mix = Math.max(mix, clamp(Math.min((srcT - (a - FALLBACK_RAMP)) / FALLBACK_RAMP, (b + FALLBACK_RAMP - srcT) / FALLBACK_RAMP), 0, 1));
	}
	return mix;
};

// ---------- Studio Tech 3D : personne détourée dans le décor virtuel ----------
/** Style Tech 3D cinématique : la vraie personne détourée est posée dans le studio virtuel (si le détourage existe). */
export const studioMode = (reel: ReelDoc) => reel.design?.enabled !== false && reel.design?.mode === 'produit' && !!reel.design?.cinematic;
const STUDIO_KINDS = new Set(['metric', 'notification', 'dashboard', 'flow', 'cta']);
const smooth = (x: number) => {
	const p = clamp(x, 0, 1);
	return p * p * (3 - 2 * p);
};
/** Valeur de plan de chaque temps du récit (agrandissement - 1, [début, fin] : poussée lente pendant le temps) pour le style
 * de référence (zoom.strength 1,06) : gros plan sur l'accroche (le tiers haut se remplit), plan large quand une interface
 * s'explique (place pour elle), poussée franche sur la preuve et l'appel à l'action. */
const BEAT_FRAME: Record<CreativeBeat['role'], [number, number]> = {
	accroche: [0.19, 0.24], probleme: [0.06, 0.1], solution: [0, 0.03], explication: [0.04, 0.07], preuve: [0.08, 0.13], cta: [0.06, 0.11],
};
const REFRAME = 1.6; // s : recadrage doux d'un temps du récit au suivant quand aucune coupe n'est proche
const SNAP = 1.2; // s : une coupe à moins de 1,2 s du début d'un temps porte le changement de plan (invisible)
const ROOM = 1.0; // s : la caméra se desserre avant l'entrée d'une interface et revient après sa sortie
const DRIFT_RATE = 0.0022; // poussée lente dans un plan (par seconde), reprise à chaque coupe
const DRIFT_MAX = 0.018;
type StudioBeat = CreativeBeat & {from: number; snap: boolean};
/** Interface affichée pendant [a, b] : agrandissement maximal de la caméra pour qu'elle tienne au-dessus de la tête. */
type StudioBusy = {a: number; b: number; smax: number};
type StudioPlan = {beats: StudioBeat[]; gain: number; busy: StudioBusy[]};
const STUDIO_OY = 0.94; // centre vertical de la caméra du studio (part de la hauteur), sous la personne : une poussée remonte le visage
const STUDIO_HEAD = 1.1; // haut de la tête (cheveux compris) au-dessus du centre du visage, en largeurs de visage (boîte MediaPipe)
const PLANS = new WeakMap<ReelDoc, {key: number; v: StudioPlan}>();
/** Graphisme réellement affiché dans un style avec habillage (même règle que Reel.tsx) : posé ou retouché à la main,
 * verrouillé, ou preuve automatique décidée par le storyboard. */
const studioGraphicShown = (reel: ReelDoc, g: Graphic) => !g.suggested && (reel.design?.suppressExtras === false || !!g.manual || !!g.locked
	|| (!!g.auto && (reel.creativePlan?.storyboard ?? []).some((s) => s.engine === 'remotion-graphisme' && g.at >= s.start - 0.3 && g.at <= s.end + 0.4)));
/** Mouvements de caméra du studio, calculés une fois par reel : temps du récit (plan créatif), amplitude du style et
 * moments où une interface occupe l'image (la caméra lui laisse la place). Sans plan créatif ou zoom auto coupé : cadre fixe
 * (anciens reels inchangés). */
const studioPlan = (reel: ReelDoc): StudioPlan => memo(PLANS, reel, () => {
	const plan = reel.creativePlan;
	const sorted = plan && plan.enabled !== false && reel.zoom?.auto ? [...(plan.beats ?? [])].sort((a, b) => a.start - b.start) : [];
	const cuts = videoSegments(reel).slice(1).map((s) => s.out_start);
	const beats = sorted.map((b, i) => {
		const cut = i ? cuts.filter((c) => Math.abs(c - b.start) <= SNAP).sort((x, y) => Math.abs(x - b.start) - Math.abs(y - b.start))[0] : undefined;
		return {...b, from: cut ?? b.start, snap: cut !== undefined};
	});
	// interfaces : la caméra ne se desserre que si l'interface ne tiendrait ni au-dessus de la tête ni à côté du visage
	// (pas de va-et-vient) ; 9:16 : jamais sous 1 (studioMinScale)
	const segs = videoSegments(reel);
	const u = Math.min(reel.width, reel.height);
	const room = (a: number, b: number, size: {w: number; h: number}): StudioBusy => {
		let head = 1;
		let side = 1;
		let fw = 0;
		let minS = 1;
		for (let x = a; x <= Math.max(a, b - 0.05) + 1e-6; x += 0.4) {
			const p = rawPerson(reel, segs, x);
			if (!p) continue;
			head = Math.min(head, p.f.cy - (STUDIO_HEAD * p.fw) / reel.height);
			side = Math.min(side, Math.max(p.f.cx, 1 - p.f.cx));
			fw = Math.max(fw, p.fw);
			minS = Math.min(minS, studioMinScale(reel, p.f));
		}
		const need = STUDIO_TOP + STUDIO_GAP + (size.h * u) / reel.height;
		const above = head < STUDIO_OY ? (STUDIO_OY - need) / (STUDIO_OY - head) : 1;
		// à côté du visage : la carte réduite à 60 % tient entre l'épaule (1,5 largeur de visage) et le bord
		const beside = fw > 0 ? ((side - 0.02 - (0.6 * size.w * u) / reel.width) * reel.width) / (1.5 * fw) : 0;
		return {a, b, smax: Math.max(minS, above, beside)};
	};
	const busy = anchoredScenes(reel).filter((s) => s.kind !== 'keyword').map((s) => room(s.at, s.end, studioCardSize(s.kind, s.text, s.secondary)));
	for (const g of reel.graphics ?? []) if (studioGraphicShown(reel, g)) busy.push(room(g.at, g.at + g.duration, studioCardSize(g.kind === 'chiffre' ? 'chiffre' : 'dashboard')));
	// amplitude réglée par le style (zoom.strength) ; formats larges : une prise verticale y est déjà très agrandie
	const gain = clamp(((reel.zoom?.strength ?? 1) - 1) / 0.06, 0, 2) * (reel.height > reel.width ? 1 : 0.5);
	return {beats, gain, busy};
});
/** Personne à l'instant t SANS la caméra du studio : segment, cadre (framing) et largeur du visage (px). */
const rawPerson = (reel: ReelDoc, segs: Segment[], t: number) => {
	if (!segs.length) return null;
	const seg = segs[segmentAt(segs, t)];
	const tSrc = segSrcTime(seg, t);
	const f = framing(reel, seg.source, tSrc, seg.src_in, seg.src_out);
	const near = (reel.sources[seg.source]?.track ?? []).filter((p) => Math.abs(p[0] - tSrc) <= 0.6 && p[3] > 0);
	return {seg, f, fw: (near.length ? median(near.map((p) => p[3])) : 0.25) * f.width};
};
/** Valeur de plan (agrandissement - 1) du temps du récit en cours : changement sur une coupe proche, sinon recadrage doux. */
const beatFrame = (beats: StudioBeat[], t: number) => {
	const at = (b: StudioBeat, x: number) => {
		const [a, z] = BEAT_FRAME[b.role] ?? [0.04, 0.07];
		const k = 0.8 + 0.2 * clamp(b.intensity ?? 0.5, 0, 1);
		return a + (z * k - a) * smooth((clamp(x, b.start, b.end) - b.start) / Math.max(0.5, b.end - b.start));
	};
	let i = -1;
	for (let j = 0; j < beats.length; j++) if (beats[j].from <= t) i = j;
	if (i < 0) return at(beats[0], beats[0].start);
	const v = at(beats[i], t);
	if (i === 0 || beats[i].snap || t - beats[i].from >= REFRAME) return v;
	const prev = at(beats[i - 1], beats[i - 1].end);
	return prev + (v - prev) * smooth((t - beats[i].from) / REFRAME);
};
/** Agrandissement limité pendant une interface qui manquerait de place : desserrage doux avant son entrée, retour après. */
const roomCap = (busy: StudioBusy[], t: number, s: number) => busy.reduce((out, k) => {
	if (s <= k.smax) return out;
	const pres = Math.min(smooth((t - (k.a - ROOM)) / ROOM), smooth((k.b + ROOM - t) / ROOM));
	return pres > 0 ? Math.min(out, s - (s - k.smax) * pres) : out;
}, s);

/** Plus petite échelle de la caméra du studio. 9:16 (prise aussi haute que l'image) : 1, le bas du détourage n'est jamais
 * découvert. Format plus large qu'une prise verticale (16:9, 1:1, 4:5 : la prise y est très agrandie) : la caméra peut
 * reculer jusqu'à 0,55 pour laisser une place à une interface ; le bas de la prise reste couvert (centre recalculé dans
 * studioView) et ses côtés sont fondus (design.tsx). */
export const studioMinScale = (reel: ReelDoc, f: {height: number}) => (f.height > reel.height * 1.05 ? clamp((1.1 * reel.height) / f.height, 0.55, 1) : 1);

/** Caméra du studio pour un segment à l'instant t du montage : échelle et centre (part de l'image) du plan de la personne,
 * échelle du décor (parallaxe : le fond bouge moins que la personne). null hors du studio. Le centre est bas (sous la
 * personne) : une poussée resserre ET remonte légèrement la personne dans le tiers haut, sans jamais découvrir le bas du
 * détourage. Même calcul pour la personne détourée, la prise d'origine (repli) et les dessins de révision.
 * wide : la caméra peut reculer sous 1 (format large), les côtés de la prise sont alors fondus. */
export type StudioView = {scale: number; ox: number; oy: number; bg: number; wide?: boolean};
export const studioView = (reel: ReelDoc, seg: Segment, t: number): StudioView | null => {
	if (!studioMode(reel) || !validCutout(reel, seg)) return null;
	const f = framing(reel, seg.source, segSrcTime(seg, t), seg.src_in, seg.src_out);
	const p = studioPlan(reel);
	const planned = p.beats.length > 0 && p.gain > 0; // sans plan créatif (ancien reel) : cadre fixe d'origine
	// plan de base : 9:16 = la prise entière ; format large = plan un peu plus large et constant (les interfaces n'imposent
	// alors qu'un petit recul, pas un va-et-vient)
	const minS = planned ? studioMinScale(reel, f) : 1;
	const base = minS < 1 ? (1 + minS) / 2 : 1;
	const override = reel.zoom?.overrides?.[String(seg.index)];
	let scale = base;
	if (override !== undefined) scale = Math.max(minS, base * override); // zoom du plan réglé à la main : cadre fixe
	else if (planned) {
		const drift = Math.min(DRIFT_MAX, DRIFT_RATE * Math.max(0, t - seg.out_start));
		scale = Math.max(minS, roomCap(p.busy, t, base * (1 + p.gain * (beatFrame(p.beats, t) + drift))));
	}
	// recul (échelle < 1) : le centre descend juste assez pour que le bas de la prise couvre toujours le bas de l'image
	const bottom = (f.top + f.height) / reel.height;
	const oy = scale < 1 ? clamp((1 - bottom * scale) / (1 - scale), STUDIO_OY, 1) : STUDIO_OY;
	return {scale, ox: f.cx, oy, bg: 1 + Math.max(0, scale - 1) * 0.3, wide: minS < 1};
};

/** Personne à l'instant t (part de l'image, caméra du studio comprise) : centre du visage, haut de la tête, demi-largeur
 * des épaules. Visage : piste de recadrage sinon échantillons d'analyse ; largeur du visage par défaut 25 % de la prise. */
export const studioPersonAt = (reel: ReelDoc, segs: Segment[], t: number) => {
	const r = rawPerson(reel, segs, t);
	if (!r) return null;
	const {seg, f} = r;
	const v = studioView(reel, seg, t) ?? {scale: 1, ox: f.cx, oy: f.cy, bg: 1};
	const fx = v.ox + (f.cx - v.ox) * v.scale;
	const fy = v.oy + (f.cy - v.oy) * v.scale;
	const fw = r.fw * v.scale; // px
	return {fx, fy, fw, head: fy - (STUDIO_HEAD * fw) / reel.height, half: (1.5 * fw) / reel.width};
};

/** Gabarit des interfaces du studio (échelle 1), en part du petit côté u : largeur, hauteur. MÊMES valeurs que les
 * cartes de design.tsx (StudioCard) et le chiffre de graphics.tsx : sert à les poser hors de la personne. */
export const studioCardSize = (kind: string, text = '', secondary = ''): {w: number; h: number} => {
	const parts = [text, ...String(secondary || '').split('|')].map((x) => x.trim()).filter(Boolean).length;
	if (kind === 'flow') return {w: 0.92, h: parts > 2 ? 0.48 : 0.15};
	if (kind === 'dashboard') return {w: 0.86, h: 0.17 + 0.11 * Math.max(1, Math.min(3, parts - 1))};
	if (kind === 'notification') return {w: 0.84, h: 0.3};
	if (kind === 'cta') return {w: 0.82, h: secondary ? 0.24 : 0.17};
	return {w: 0.72, h: 0.33}; // metric, chiffre
};
const STUDIO_TOP = 0.06; // haut de l'image laissé libre (interface des réseaux)
const STUDIO_GAP = 0.02; // écart minimal entre une interface et la tête
/** Place (centre x, y en part de l'image, échelle) d'une interface du studio pendant [at, end] : dans l'espace libre
 * au-dessus de la tête si elle y tient (même réduite à 80 %), sinon à côté du visage (formats larges), sinon la place
 * enregistrée. Calculée avec la caméra du studio sur toute la durée (haut de la tête le plus haut). */
export const studioSpot = (reel: ReelDoc, kind: string, at: number, end: number, stored: {x: number; y: number; scale: number}, size = studioCardSize(kind)) => {
	const segs = videoSegments(reel);
	const u = Math.min(reel.width, reel.height);
	let head = 1;
	let fx = 0;
	let half = 0;
	let n = 0;
	for (let x = at; x <= Math.max(at, end - 0.05) + 1e-6; x += 0.4) {
		const p = studioPersonAt(reel, segs, x);
		if (!p) continue;
		head = Math.min(head, p.head);
		fx += p.fx;
		half = Math.max(half, p.half);
		n += 1;
	}
	if (!n) return stored;
	fx /= n;
	const ch = (size.h * u) / reel.height;
	const cw = (size.w * u) / reel.width;
	const room = head - STUDIO_GAP - STUDIO_TOP;
	if (room >= ch * 0.8) {
		const scale = Math.min(1, room / ch);
		const h = ch * scale;
		// dans l'espace libre, un peu plus près de la tête que du bord : le regard va du visage à l'interface
		return {x: 0.5, y: +Math.max(STUDIO_TOP + h / 2, head - STUDIO_GAP - h / 2 - (room - h) * 0.35).toFixed(4), scale: +scale.toFixed(3)};
	}
	const left = fx - half - 0.02;
	const right = 1 - fx - half - 0.02;
	const side = Math.max(left, right);
	if (side >= cw * 0.6) {
		const scale = Math.min(1, side / cw);
		const w = cw * scale;
		return {x: +(left >= right ? left - w / 2 + 0.01 : 1 - right + w / 2 - 0.01).toFixed(4), y: +clamp(head + ch * scale * 0.6, STUDIO_TOP + ch / 2, 0.6).toFixed(4), scale: +scale.toFixed(3)};
	}
	return stored;
};

const GSPOTS = new WeakMap<ReelDoc, {key: number; v: Map<string, {x: number; y: number; scale: number}>}>();
/** Place d'un chiffre de la piste Graphismes dans le studio Tech 3D (studioSpot, gardée en mémoire par reel) : MÊME
 * calcul pour l'image (graphics.tsx) et la chorégraphie (origine du « pop », découpe du tracé). Hors studio, ou chiffre
 * posé à la main / verrouillé : sa place enregistrée. */
export const studioGraphicSpot = (reel: ReelDoc, g: Graphic) => {
	const stored = {x: 0.5, y: typeof g.props?.y === 'number' ? g.props.y : 0.3, scale: 1};
	if (!studioMode(reel) || g.kind !== 'chiffre' || g.manual || g.locked) return stored;
	const all = memo(GSPOTS, reel, () => new Map<string, {x: number; y: number; scale: number}>());
	const key = `${g.id}|${g.at}|${g.duration}`;
	let spot = all.get(key);
	if (!spot) {
		spot = studioSpot(reel, 'chiffre', g.at, g.at + g.duration, stored, studioCardSize('chiffre'));
		all.set(key, spot);
	}
	return spot;
};
/** Interfaces du studio Tech 3D dessinées en cartes de verre (StudioCard de design.tsx) et posées par studioSpot. */
export const isStudioCard = (reel: ReelDoc, kind: string) => studioMode(reel) && STUDIO_KINDS.has(kind);

const hexRgb =(hex: string): [number, number, number] => {
	const h = /^#?([0-9a-f]{6})/i.exec(hex)?.[1] ?? '6fe7ff';
	return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
};
/** Mélange de deux couleurs #rrggbb (k = part de b). */
export const mixHex = (a: string, b: string, k: number) => '#' + hexRgb(a).map((v, i) => Math.round(v + (hexRgb(b)[i] - v) * k).toString(16).padStart(2, '0')).join('');

/** Étalonnage de la personne détourée pour le studio : couleur du plan (harmonisation + réglages du monteur), balance
 * des blancs refroidie d'après la couleur réelle du visage (lumière chaude de bureau -> studio froid), légère
 * désaturation, noirs plus denses (fond très sombre) et ombres légèrement bleutées (même nuit que le décor ; la peau, dans
 * les tons moyens, reste naturelle). Les pixels semi-transparents du bord (cheveux, flou de bouge d'une main) gardent
 * souvent la couleur claire du décor d'origine : ils sont assombris en proportion de leur transparence (EDGE_DARK, sans
 * effet sur l'intérieur opaque). Matrice feColorMatrix 4 x 5 (sRGB, couleurs non prémultipliées). */
const SHADOW_TINT = [-0.004, 0, 0.016];
const EDGE_DARK = 0.3;
export const studioGrade = (reel: ReelDoc, seg: Segment, gains: [number, number, number]) => {
	const s = (reel.sources[seg.source]?.samples ?? []).filter((x) => x[0] >= seg.src_in - 0.5 && x[0] <= seg.src_out + 0.5 && x[3] > 0);
	const r = s.length ? median(s.map((x) => x[4])) * gains[0] : 1;
	const b = s.length ? median(s.map((x) => x[6])) * gains[2] : 0.6;
	const gb = clamp(0.6 / Math.max(0.05, b / Math.max(1e-3, r)), 1, 1.12);
	const gr = clamp(1 - 0.5 * (gb - 1), 0.94, 1);
	const gg = 1 + 0.15 * (gb - 1);
	const G = [gains[0] * gr, gains[1] * gg, gains[2] * gb];
	const sat = 0.86;
	const L = [0.2126, 0.7152, 0.0722];
	const contrast = 1.07;
	const bright = 0.94;
	const slope = contrast * bright;
	const offset = (0.5 - 0.5 * contrast) * bright;
	const rows: number[] = [];
	for (let i = 0; i < 3; i++) {
		for (let j = 0; j < 3; j++) rows.push(+(slope * ((i === j ? L[j] + (1 - L[j]) * sat : L[j] * (1 - sat)) * G[j])).toFixed(4));
		rows.push(EDGE_DARK, +(offset + SHADOW_TINT[i] - EDGE_DARK).toFixed(4));
	}
	return [...rows, 0, 0, 0, 1, 0];
};

/** Zoom seulement sur un mot fort, jamais systématiquement à chaque coupe. */
export const motivatedZoom = (reel: ReelDoc, t: number) => {
	if (!['hormozi','produit'].includes(reel.design?.mode??'') || reel.design?.enabled === false || !reel.zoom.auto) return 1;
	const all = timedWords(reel);
	const emojis = reel.emoji?.enabled ? all.filter(w=>reel.clips.find(c=>c.id===w.clip)?.emojis?.some(([i])=>i===w.index)) : [];
	const words = all.filter((w) => w.hl && !w.hide && !emojis.some(e=>w.outStart<e.outStart+1.3 && w.outStart+1.2>e.outStart));
	const chosen: TimedWord[] = [];
	for (const w of words) if (!chosen.length || w.outStart - chosen[chosen.length-1].outStart > 4) chosen.push(w);
	const hit = chosen.find((w) => t >= w.outStart && t < w.outStart+1.2);
	if (!hit) return 1;
	const d = t-hit.outStart;
	return 1 + (reel.zoom.strength-1) * Math.min(1, d/.12, (1.2-d)/.2);
};

/** Echelle de l'image d'un plan (zooms du style, zoom motive, poussee lente, luxe), local = secondes depuis le debut du
 * segment. UNE seule implementation : l'image (SegmentVideo de Reel.tsx) et le rectangle des dessins (sourceRectAt). */
export const segmentZoom = (reel: ReelDoc, seg: Segment, next: Segment | undefined, total: number, local: number) => {
	const len = (next ? next.out_start : total) - seg.out_start;
	const progress = Math.min(1, Math.max(0, local / Math.max(0.001, len)));
	let scale = 1;
	const override = reel.zoom.overrides?.[String(seg.index)];
	if (override !== undefined) scale = override;
	else if (reel.zoom.auto && !reel.design?.mode) scale = seg.index % 2 === 1 ? reel.zoom.strength : 1;
	scale *= motivatedZoom(reel, seg.out_start + local);
	scale *= 1 + reel.zoom.push * progress;
	if (reel.design?.mode === 'luxe' && reel.design.enabled !== false) scale *= .87;
	return scale;
};

// ---------- V2 : ancres (notes, dessins), rectangle de la prise visible (dessins alignes dans tous les formats) ----------
/** Tailles des formats : meme table que FORMATS de types.ts (ce fichier n'importe que des types). */
const FORMAT_SIZES: Record<string, [number, number]> = {'9:16': [1080, 1920], '16:9': [1920, 1080], '4:5': [1080, 1350], '1:1': [1080, 1080]};

/** Identifiant de choregraphie d'une page de sous-titres : 1er mot de la page. */
export const captionCueId = (w: {clip: string; index: number}) => `${w.clip}:${w.index}`;

/** Prise d'une ancre (champ source, sinon debut de la signature « source|in|out|tighten »). */
const anchorTake = (a: Anchor) => a.source ?? (a.sig ? a.sig.split('|')[0] : undefined);

/** Ancre de l'instant t du montage : plan sous la tete de lecture, temps dans sa prise. null : montage vide. */
export const anchorAtTime = (reel: ReelDoc, t: number): Anchor | null => {
	const segs = baseSegments(reel);
	if (!segs.length) return null;
	const s = segs[segmentAt(segs, t)];
	const clip = reel.clips.find((c) => c.id === s.clip)!;
	const local = Math.min(Math.max(0, t - s.out_start), segLen(s));
	return {clip: clip.id, src: +(s.src_in + local * (s.speed ?? 1)).toFixed(4), sig: clip.signature, source: clip.source, image: visualClip(reel, clip).source};
};

export type AnchorPlace = {t: number; clip: string; exact: boolean};
/** Ou tombe une ancre dans le montage actuel. exact : dans son plan d'origine ; sinon le meme moment de la meme prise
 * retrouve dans un autre plan. null : passage coupe, prise du plan changee (la note ne pointe JAMAIS en silence ailleurs). */
export const resolveAnchor = (reel: ReelDoc, anchor: Anchor, segs: Segment[] = baseSegments(reel)): AnchorPlace | null => {
	const take = anchorTake(anchor);
	const own = reel.clips.find((c) => c.id === anchor.clip);
	if (own && (!take || own.source === take)) {
		const t = toOut(segs, own.id, anchor.src);
		if (t !== null) return {t, clip: own.id, exact: true};
	}
	if (!take) return null;
	for (const c of reel.clips) {
		if (c.id === anchor.clip || c.source !== take) continue;
		const t = toOut(segs, c.id, anchor.src);
		if (t !== null) return {t, clip: c.id, exact: false};
	}
	return null;
};

/** Temps du montage (s) d'une ancre, ou null si le passage a ete coupe ou retire. */
export const outputTimeOfAnchor = (reel: ReelDoc, anchor: Anchor): number | null => resolveAnchor(reel, anchor)?.t ?? null;

/** Partie de la prise visible dans l'image : x, y, w, h en coordonnees normalisees de la prise (0..1 ; hors 0..1 si
 * l'image est plus petite que le cadre). source : prise affichee (angle compris) ; tSrc : temps dans cette prise. */
export type SourceRect = {clip: string; source: string; tSrc: number; x: number; y: number; w: number; h: number; scale: number};

/** Rectangle de la prise visible a l'instant t, avec le cadrage (sujet suivi), les zooms et l'angle de l'apercu et de
 * l'export. format : '9:16' | '16:9' | '4:5' | '1:1' | [largeur, hauteur] (defaut : celui du reel). Piste principale
 * seulement (un plan de coupe par-dessus n'est pas pris en compte). null : montage vide. */
export const sourceRectAt = (reel: ReelDoc, t: number, format?: string | [number, number]): SourceRect | null => {
	const size = Array.isArray(format) ? format : format ? FORMAT_SIZES[format] : null;
	const r = size ? {...reel, width: size[0], height: size[1]} : reel;
	const segs = videoSegments(r);
	if (!segs.length) return null;
	const i = segmentAt(segs, t);
	const seg = segs[i];
	const local = Math.min(Math.max(0, t - seg.out_start), segLen(seg));
	const tSrc = seg.src_in + local * (seg.speed ?? 1);
	const f = framing(r, seg.source, tSrc, seg.src_in, seg.src_out);
	// personne detouree : Collage sans zoom ; studio Tech 3D avec sa camera (studioView, meme calcul que design.tsx)
	const mode = r.design?.enabled === false ? null : r.design?.mode;
	const view = studioView(r, seg, t);
	const cutout = mode === 'collage' && !!validCutout(r, seg);
	const scale = view ? view.scale : cutout ? 1 : segmentZoom(r, seg, segs[i + 1], duration(r), local);
	const ox = (view ? view.ox : f.cx) * r.width;
	const oy = (view ? view.oy : f.cy) * r.height;
	// le zoom agrandit autour de (ox, oy) : le coin (0, 0) de l'image montre le point o - o / scale du cadre
	return {clip: seg.clip, source: seg.source, tSrc, scale,
		x: (ox - ox / scale - f.left) / f.width, y: (oy - oy / scale - f.top) / f.height, w: r.width / scale / f.width, h: r.height / scale / f.height};
};

/** Point de la prise (0..1) -> point de l'image (0..1) ; et l'inverse. */
export const sourceToOutput = (rect: SourceRect, [u, v]: [number, number]): [number, number] => [(u - rect.x) / rect.w, (v - rect.y) / rect.h];
export const outputToSource = (rect: SourceRect, [x, y]: [number, number]): [number, number] => [rect.x + x * rect.w, rect.y + y * rect.h];

/** Instants d'affichage d'un dessin : [debut, fin] du montage, ou null si son passage a ete coupe. */
export const annotationWindow = (reel: ReelDoc, a: Annotation): [number, number] | null => {
	const t = outputTimeOfAnchor(reel, a.anchor);
	return t === null ? null : [t, t + Math.max(0.04, a.duree)];
};

/** Points d'un dessin dans l'image (0..1) a l'instant t et dans ce format ; null si l'image montre une autre prise que
 * celle du dessin (prise ou angle change) : on ne l'affiche pas de travers. */
export const annotationOutput = (reel: ReelDoc, a: Annotation, t: number, format?: string | [number, number]): [number, number][] | null => {
	const rect = sourceRectAt(reel, t, format);
	if (!rect) return null;
	const image = a.anchor.image ?? anchorTake(a.anchor);
	if (image && rect.source !== image) return null;
	return a.points.map((p) => sourceToOutput(rect, p));
};

// ---------- Rythme ----------
/** Energie du montage par tranche d'une seconde (0..1) : coupes, debit de parole, mots cles. */
export const pacing = (reel: ReelDoc) => {
	const total = duration(reel);
	const segs = baseSegments(reel);
	const words = timedWords(reel);
	const n = Math.max(1, Math.ceil(total));
	return Array.from({length: n}, (_, i) => {
		const cuts = segs.filter((s) => s.out_start >= i - 1.5 && s.out_start < i + 1.5).length / 3;
		const wps = words.filter((w) => w.outStart >= i && w.outStart < i + 1).length;
		const hl = words.some((w) => w.hl && w.outStart >= i - 1 && w.outStart < i + 2) ? 1 : 0;
		const silence = wps === 0 ? 1 : 0;
		const score = clamp(0.35 * Math.min(1, cuts / 0.6) + 0.4 * Math.min(1, wps / 3.2) + 0.25 * hl - 0.3 * silence, 0, 1);
		return {t: i, score};
	});
};
