// Calcul du montage : UNE seule implementation, utilisee par l'apercu (navigateur) et par l'export (Node).
// Ce fichier ne doit importer que des types (Node l'execute directement en retirant les types).
import type {Clip, ReelDoc, Segment, Word, StyleScene} from './types';

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
	for (const e of s.extra ?? []) ev.push({t: e.t, name: e.name, volume: s.volume * 0.8, kind: 'ajoute'});
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

export const sfxFile = (name: string) => `sfx/editeur/${name}.wav`;

/** Scènes ancrées à un mot : une coupe de texte déplace ou retire automatiquement l'habillage. */
export const designScenes = (reel: ReelDoc): (StyleScene & {at: number; end: number})[] => {
	if (reel.design?.enabled === false || !reel.design?.mode) return [];
	const words = timedWords(reel);
	const total = duration(reel);
	const result: (StyleScene & {at: number; end: number})[] = [];
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

export const validCutout = (reel: ReelDoc, s: Segment) => {
	const m=reel.cutouts?.[s.clip];
	return m && m.source===s.source && m.proxy===reel.sources[s.source]?.proxy && m.start<=s.src_in+.02 && m.end>=s.src_out-.02 ? m : null;
};

/** Zoom seulement sur un mot fort, jamais systématiquement à chaque coupe. */
export const motivatedZoom = (reel: ReelDoc, t: number) => {
	if (reel.design?.mode !== 'hormozi' || reel.design.enabled === false || !reel.zoom.auto) return 1;
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
