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
/** Expressions figées qu'une page ne coupe jamais (« quoi | que ce soit » se lisait mal, juge n° 2). Mots en minuscules,
 * sans accents ni ponctuation. */
const FIXED = ['quoi que ce soit', 'qui que ce soit', 'a temps plein', 'a temps partiel', 'peu importe', 'en savoir plus', 'tout le monde',
	'tout de suite', 'de plus en plus', 'de moins en moins', 'au lieu de', 'par exemple', 'parce que', 'est-ce que', 'il y a',
	"n'importe quoi", 'en fait', 'au moins', 'pas du tout', 'a chaque fois', 'une fois', 'plus que', 'moins cher', 'fois moins cher',
	'fois plus', 'sans risque', 'du coup', 'en ce moment', 'tout le temps', 'de la publicite', 'no matter', 'right now', 'as soon as',
	'find out more', 'learn more', 'full time', 'part time'].map((e) => e.split(' '));
const WEAK_END = new Set(("le la les l' un une des du de d' a au aux et ou en pour par sur dans avec sans ce ces cette mon ma mes ton ta tes "
	+ "son sa ses notre votre nos vos leur leurs que qu' qui se ne plus moins si quand comme mais donc tres the a an of to and or for with in on at "
	// « Puis là c’est | pas juste », « on a un vrai | intérêt », « à bien | qualifier » (juge n° 3) : la suite est attendue
	+ "c'est vrai vraie vrais vraies bien bon bonne petit petite grand grande "
	// déterminants et élisions qui annoncent un nom (« et éduquer chaque | lead », « des gens qu'on | engage », « parce | qu'un »)
	+ "chaque parce qu'on qu'il qu'elle qu'ils qu'un qu'une d'un d'une aucun aucune tout toute tous toutes cet quel quelle quelques plusieurs")
		.split(' '));
const pageToken = (w: string) => w.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[«»"“”,.;:!?…()\[\]]/g, '').replace(/’/g, "'").trim();
export const pages = (reel: ReelDoc): Page[] => {
	const raw = timedWords(reel).filter((w) => !w.hide && w.w.trim());
	// 1. ponctuation seule (« », « ». », « ! ») transcrite comme un mot : jamais une page vide (un sous-titre blanc d'un
	// instant). Un signe ouvrant (« “ ( [) se colle au mot suivant, les autres au mot d'avant (fin de phrase comptée).
	const words: TimedWord[] = [];
	let open = '';
	for (let w of raw) {
		const prev = words[words.length - 1];
		if (!displayWord(w.w, false)) {
			if (/^[«“(\[¿¡]/.test(w.w.trim())) {
				open += w.w.trim();
				continue;
			}
			if (prev && prev.clip === w.clip) {
				words[words.length - 1] = {...prev, w: prev.w + w.w.trim(), outEnd: Math.max(prev.outEnd, w.outEnd)};
				continue;
			}
		}
		if (open) {
			w = {...w, w: open + w.w};
			open = '';
		}
		words.push(w);
	}
	// 2. coupure de page possible avant chaque mot : fin de phrase, pause, changement de plan (obligatoire) ; jamais au
	// milieu d'une expression figée (elle passe entière à la page suivante si elle n'y tient pas)
	const hard = words.map((w, i) => i > 0 && (/[.!?…]["»”)\]]*$/.test(words[i - 1].w) || w.outStart - words[i - 1].outEnd > 0.35 || words[i - 1].clip !== w.clip));
	const glued = words.map(() => false);
	const toks = words.map((w) => pageToken(w.w));
	for (let i = 0; i < words.length; i++) {
		for (const e of FIXED) {
			if (i + e.length > words.length || !e.every((x, k) => toks[i + k] === x)) continue;
			if (e.some((_, k) => k > 0 && hard[i + k])) continue;
			for (let k = 1; k < e.length; k++) glued[i + k] = true;
		}
	}
	// 3. dans chaque phrase (entre deux coupures obligatoires), le meilleur découpage en pages (programmation dynamique) :
	// pages de 2 à max mots (max + 1 au plus), coupe de préférence après une virgule, jamais sur un petit mot qui annonce la
	// suite (« de », « des », « à »), jamais une page éclair (< 0,45 s), jamais au milieu d'une expression figée
	const max = Math.max(1, reel.style.maxWords);
	// une page de max + 1 mots seulement dans le studio (sa mise en page passe sur deux lignes dans 80 % de la largeur) ;
	// ailleurs, la taille des sous-titres est fixe : jamais plus de max mots (zone sûre des réseaux)
	const extra = studioMode(reel) ? 1 : 0;
	const uMin = Math.min(reel.width, reel.height);
	const oneLine = (reel.style.size * uMin) / 1080; // taille de base des sous-titres (px)
	const result: Page[] = [];
	const comma = (w: TimedWord) => /[,;:]["»”)\]]*$/.test(w.w.trim());
	let a = 0;
	while (a < words.length) {
		let z = a + 1;
		while (z < words.length && !hard[z]) z++;
		const run = words.slice(a, z);
		const m = run.length;
		const cost = (i: number, j: number) => {
			const n = j - i + 1;
			let c = n > max ? 1.6 : n === 1 && m > 1 ? 2.6 : n === 2 && max > 2 ? 0.5 : 0;
			c += Math.max(0, max - n) * 0.35; // pages pleines de préférence (moins de changements de page)
			const last = run[j];
			if (j < m - 1 && WEAK_END.has(pageToken(last.w)) && !comma(last) && !glued[a + j]) c += 3; // fin d'expression : permise
			// deux mots en couleur qui se suivent (« trois heures ») ou un nombre et ce qu'il compte : jamais séparés
			if (j < m - 1 && ((last.hl && run[j + 1].hl) || /^\d+$|^(deux|trois|quatre|cinq|six|sept|huit|neuf|dix|vingt|cent|mille)$/.test(pageToken(last.w)))) c += 2;
			for (let k = i; k < j; k++) if (comma(run[k])) c += 0.9;
			if (j < m - 1 && comma(last)) c -= 0.3;
			const d = run[j].outEnd - run[i].outStart;
			if (d < 0.3) c += 3;
			else if (d < 0.45) c += 1.4;
			// temps à l'écran (jusqu'à la page suivante) sous 0,5 s : à peine lisible (léger : une bonne coupure passe avant)
			const shown = (j < m - 1 ? run[j + 1].outStart : run[j].outEnd + 0.3) - run[i].outStart;
			if (shown < 0.5) c += 0.5 * (0.5 - shown) / 0.1;
			// studio : une page qui ne tient pas sur une ligne passe sur deux, en plus petit (studioCaptionLayout)
			if (extra && n > 1) {
				const em = run.slice(i, j + 1).reduce((x, w) => x + 0.2 + studioCaptionEm(displayWord(w.w, reel.style.uppercase)), 0.2 * (n - 1));
				if (em * Math.max(oneLine * 0.8, Math.min(oneLine, uMin * 0.06)) > reel.width * 0.8) c += 0.6;
			}
			return c + 0.15; // chaque page coûte un peu : pas de pages inutilement courtes
		};
		const solve = (glue: boolean) => {
			const best = new Array<number>(m + 1).fill(Infinity);
			const from = new Array<number>(m + 1).fill(-1);
			best[0] = 0;
			for (let j = 1; j <= m; j++) {
				if (glue && j < m && glued[a + j]) continue; // la page suivante commencerait au milieu d'une expression
				for (let i = Math.max(0, j - (max + extra)); i < j; i++) {
					if (best[i] === Infinity) continue;
					const v = best[i] + cost(i, j - 1);
					if (v < best[j]) [best[j], from[j]] = [v, i];
				}
			}
			if (best[m] === Infinity) return null;
			const out: number[] = [];
			for (let j = m; j > 0; j = from[j]) out.unshift(from[j]);
			return out;
		};
		// une expression plus longue qu'une page (style à 2-3 mots par page) : coupée comme un autre groupe de mots
		const cuts = solve(true) ?? solve(false) ?? [0];
		cuts.forEach((i, k) => {
			const ws = run.slice(i, k + 1 < cuts.length ? cuts[k + 1] : m);
			result.push({words: ws, start: ws[0].outStart, end: ws[ws.length - 1].outEnd});
		});
		a = z;
	}
	result.forEach((p, i) => {
		const next = result[i + 1];
		p.end = next ? Math.min(next.start, p.end + 0.6) : p.end + 0.4;
	});
	return result;
};

/** Typographie des textes à l'image (sous-titres, cartes, bouton) : une seule apostrophe, la courbe « ’ ». La transcription
 * et les retouches mêlaient « c’est » et « quelqu'un » sur deux pages qui se suivent (juge n° 3, 2 oct. 2026). Le texte
 * enregistré ne change pas. */
export const typo = (s: string) => String(s ?? '').replace(/'/g, '’');
export const displayWord = (w: string, uppercase: boolean) => {
	const t = typo(w.replace(/[«»"“”]/g, '').replace(/[,.;:…]+$/g, '').trim());
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

/** Gain par bruitage (mesure RMS des fichiers : tous ramenes vers -20 dB ; le « glitch » etait 16 dB trop fort).
 * Sons de coupe varies (engine/editeur/sfxgen.py) : ramenes a la meme sonie ; seuls ceux qui ne peuvent pas l'atteindre sans
 * ecreter (clics tres brefs) ont un gain ici. */
export const SFX_GAIN: Record<string, number> = {
	click: 2.2, 'declencheur-photo': 1.5, ding: 1.0, glitch: 0.15, impact: 0.34, 'pop-grave': 0.6, pop: 0.6,
	riser: 1.6, 'whoosh-court': 1.25, 'whoosh-descendant': 1.07, 'whoosh-long': 1.2,
	'coupe-seche': 1.46, 'arret-bande': 1.13, 'arret-bande-court': 1.18, 'ui-tic': 2.47, 'ui-tic-double': 1.77, 'ui-clic-doux': 1.42,
	obturateur: 1.18, 'pop-bouchon': 1.31, 'tap-bois': 1.21, 'kenney-interrupteur': 1.1, 'kenney-survol': 2.45, 'kenney-verre': 1.14,
	'kenney-depot': 1.11, 'kenney-phaser': 1.06, 'kenney-impact-doux': 1.1, 'kenney-impact-bois': 1.23,
};

type SfxPoolSound = NonNullable<NonNullable<ReelDoc['sfx']>['pool']>[number];
type SfxSound = {name: string; pic: number; gain: number; role: string};
/** Role d'un son de coupe et instant (montage) ou son maximum doit tomber : la coupe, l'entree de l'interface, le mot. */
type SfxSlot = SfxEvent & {role?: string; at?: number; scene?: number};

/** Reserves par defaut (reel sans « pool », ancien reel compris) : voisins du son choisi par le style, memes pic et gains que
 * styles/sons-transitions.json. Cle « role:son du style » (sinon « …:son du style »). [nom, pic (s), gain]. */
export const SFX_POOL_DEFAUT: Record<string, [string, number, number][]> = {
	'transition:whoosh-court': [['whoosh-court', 0.182, 1], ['whoosh-aerien-court', 0.18, 1], ['passage-eclair', 0.168, 1],
		['whoosh-chute-court', 0.182, 1], ['coupe-seche', 0.09, 1], ['souffle-leger', 0.122, 1]],
	'transition:whoosh-long': [['whoosh-long', 0.372, 1], ['whoosh-aerien-long', 0.557, 1], ['passage-gauche-droite', 0.318, 1],
		['passage-droite-gauche', 0.278, 1], ['aspiration-longue', 1.135, 1], ['whoosh-chute', 0.297, 1]],
	'transition:whoosh-descendant': [['whoosh-descendant', 0.24, 1], ['passage-droite-gauche', 0.278, 1], ['whoosh-sourd', 0.253, 1],
		['whoosh-chute', 0.297, 1], ['souffle-ample', 0.323, 1]],
	'transition:glitch': [['glitch', 0.013, 1], ['glitch-saccade', 0.195, 0.8], ['glitch-roulement', 0.32, 0.8], ['glitch-bits', 0.01, 0.8],
		['balayage-numerique', 0.15, 1]],
	// studio Tech 3D : chaque interface entre avec un son d'ecran different (avant : toujours le meme whoosh)
	'interface:whoosh-court': [['ui-glisse', 0.16, 1], ['ui-glisse-tonale', 0.12, 1], ['balayage-numerique', 0.15, 1],
		['kenney-selection', 0.01, 1], ['souffle-leger', 0.122, 1], ['whoosh-court', 0.182, 1]],
	'apparition:click': [['click', 0, 1], ['ui-tic', 0, 0.6], ['ui-tic-double', 0.037, 0.6], ['kenney-bascule', 0.007, 0.6]],
	'mot-fort:pop': [['pop', 0.005, 1], ['pop-bouchon', 0.005, 0.6], ['pop-bulle', 0.005, 0.6], ['pop-doux', 0.005, 0.6]],
	'mot-fort:pop-grave': [['pop-grave', 0.005, 1], ['pop-doux', 0.005, 0.6], ['ui-bulle', 0.005, 0.6], ['pop-goutte', 0.005, 0.6]],
	'mot-fort:click': [['click', 0, 1], ['ui-tic-double', 0.037, 0.6], ['kenney-bascule', 0.007, 0.6], ['ui-tic', 0, 0.6]],
	'mot-fort:impact': [['impact', 0.007, 1], ['impact-leger', 0.007, 0.8], ['impact-coup-sec', 0.01, 0.8], ['impact-mat', 0.01, 0.8]],
	'impact:pop-grave': [['pop-grave', 0.005, 1], ['impact-leger', 0.007, 0.8], ['ding-cristal', 0.01, 0.8], ['ui-bulle', 0.005, 0.6]],
	'cta:riser': [['riser', 1.54, 1], ['riser-numerique', 0.92, 1.8], ['riser-souffle', 1.087, 1.8], ['riser-doux', 0.725, 1.8]],
};
/** Sons qui se suivent a l'oreille (meme historique : jamais deux fois de suite le meme). */
const SFX_GROUP: Record<string, string> = {transition: 'passage', interface: 'passage', apparition: 'apparition', 'mot-fort': 'accent', impact: 'accent', cta: 'cta'};
const SFX_ROLES = new Set(Object.keys(SFX_GROUP));

/** Reserve du reel, nettoyee (32 au plus, pic 0-3 s, gain 0-4) : un reel abime ne casse jamais le calcul. */
const sfxPool = (pool: unknown): SfxSound[] => (Array.isArray(pool) ? pool : []).slice(0, 32)
	.filter((p): p is SfxPoolSound => !!p && typeof p === 'object' && typeof (p as SfxPoolSound).name === 'string' && !!(p as SfxPoolSound).name)
	.map((p) => ({name: p.name, pic: clamp(Number.isFinite(p.pic) ? Number(p.pic) : 0, 0, 3), gain: clamp(Number.isFinite(p.gain) ? Number(p.gain) : 1, 0, 4),
		role: typeof p.role === 'string' && SFX_ROLES.has(p.role) ? p.role : 'transition'}));

/** Sons possibles pour un role : ceux de la famille du reel (interface sans son propre = ceux des coupes ; preuve <-> mot fort),
 * sinon la reserve par defaut du son du style, sinon rien (le son du style, comme avant). */
const sfxChoices = (pool: SfxSound[], role: string, styleSound: string): SfxSound[] => {
	const of = (r: string) => pool.filter((p) => p.role === r);
	const own = of(role).length ? of(role) : role === 'interface' ? of('transition') : role === 'impact' ? of('mot-fort') : role === 'mot-fort' ? of('impact') : [];
	if (own.length) return own;
	const d = SFX_POOL_DEFAUT[`${role}:${styleSound}`] ?? Object.entries(SFX_POOL_DEFAUT).find(([k]) => k.endsWith(`:${styleSound}`))?.[1];
	return d ? d.map(([name, pic, gain]) => ({name, pic, gain, role})) : [];
};

/** Empreinte stable (index de l'evenement + temps au millieme) : meme tirage a l'apercu et a l'export. */
const sfxHash = (i: number, t: number) => {
	let h = 2166136261;
	for (const c of `${i}:${Math.round(t * 1000)}`) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
	h ^= h >>> 13;
	h = Math.imul(h, 0x5bd1e995);
	return (h ^ (h >>> 15)) >>> 0;
};

/** Varie les sons de coupe : chaque evenement prend un son de la reserve de son role (dans l'ordre du temps), jamais le meme
 * que le precedent du meme groupe, ni un des 3 derniers quand la reserve en a au moins 4 ; son maximum (pic) tombe sur
 * l'instant voulu ; une liste (ou un bouton) garde le meme son pour tous ses elements, qui part SUR le mot (petit clic). */
const varySfx = (pool: SfxSound[], ev: SfxSlot[]): SfxSlot[] => {
	const out = [...ev];
	const order = ev.map((e, k) => ({e, k})).filter(({e}) => e.role && e.at !== undefined).sort((a, b) => a.e.at! - b.e.at! || a.k - b.k);
	const history: Record<string, string[]> = {};
	const count: Record<string, number> = {};
	const scenes = new Map<string, SfxSound>();
	for (const {e, k} of order) {
		const choices = sfxChoices(pool, e.role!, e.name);
		if (!choices.length) continue;
		const group = SFX_GROUP[e.role!];
		const key = e.scene !== undefined ? `${group}:${e.scene}` : '';
		let pick = key ? scenes.get(key) : undefined;
		if (!pick) {
			const h = (history[group] ??= []);
			const distinct = new Set(choices.map((c) => c.name)).size;
			const avoid = h.slice(distinct >= 4 ? -3 : distinct >= 2 ? -1 : h.length);
			const free = choices.filter((c) => !avoid.includes(c.name));
			const i = (count[group] = (count[group] ?? -1) + 1);
			pick = free[sfxHash(i, e.at!) % free.length];
			h.push(pick.name);
			if (key) scenes.set(key, pick);
		}
		out[k] = {...e, name: pick.name, t: Math.max(0, e.at! - (e.role === 'apparition' ? 0 : pick.pic)), volume: e.volume * pick.gain};
	}
	return out;
};

/** Bruitages places automatiquement selon le style de montage. Sons de coupe varies (sfx.varier absent ou vrai) : chaque
 * coupe, entree d'interface, mot fort, preuve et montee avant l'appel a l'action prend un son de la famille (sfx.pool) ou de
 * la reserve par defaut ; sfx.varier === false : exactement les sons du style, comme avant. */
export const sfxEvents = (reel: ReelDoc): SfxEvent[] => {
	const s = reel.sfx;
	if (!s?.enabled) return [];
	const ev: SfxSlot[] = [];
	if (s.start) ev.push({t: 0, name: s.start, volume: s.volume, kind: 'debut'});
	const starts = blockStarts(reel);
	// studio Tech 3D : pas de whoosh sur une coupe franche où rien ne bouge (un son sans raison à l'image) ; il accompagne
	// l'entrée de chaque interface (plus bas)
	if (s.transition && !studioMode(reel)) for (const b of starts) ev.push({t: Math.max(0, b.t - (s.transition.startsWith('whoosh') ? 0.2 : 0)), name: s.transition, volume: s.volume, kind: 'transition', role: 'transition', at: b.t});
	if (s.cta && reel.ctaBlock) {
		const cta = starts.find((b) => b.block === reel.ctaBlock);
		// le maximum de la montee tombe juste avant la partie de l'appel a l'action (comme le « riser » d'origine)
		if (cta && cta.t > 2) ev.push({t: cta.t - 1.6, name: s.cta, volume: s.volume * 0.8, kind: "appel a l'action", role: 'cta', at: cta.t - 0.06});
	}
	// studio Tech 3D : chaque interface entre avec le son de transition du style (léger, juste avant), chaque élément d'une
	// liste avec un petit clic, la preuve chiffrée du storyboard avec le son des mots forts (comme un habillage de motion
	// design : rien n'apparaît en silence)
	const ui: number[] = [];
	if (studioMode(reel)) {
		const whoosh = s.transition || 'whoosh-court';
		designScenes(reel).forEach((g, k) => {
			if (g.kind === 'keyword') return;
			ev.push({t: Math.max(0, g.at - 0.12), name: whoosh, volume: s.volume * 0.55, kind: 'interface', role: 'interface', at: g.at + 0.06});
			ui.push(g.at);
			if (g.kind === 'list') for (const m of (g.marks ?? []).slice(1)) ev.push({t: m, name: 'click', volume: s.volume * 0.4, kind: 'liste', role: 'apparition', at: m, scene: k});
			// bouton qui rejoint l'offre déjà affichée, ou offre qui rejoint le bouton tenu : petit clic sur son mot (rien en double
			// avec le whoosh de l'entrée)
			if (g.kind === 'cta') for (const m of g.marks ?? []) if (m > g.at + 0.05) ev.push({t: m, name: 'click', volume: s.volume * 0.45, kind: 'bouton', role: 'apparition', at: m, scene: k});
		});
		for (const g of reel.graphics ?? []) {
			if (!studioGraphicShown(reel, g)) continue;
			ev.push({t: g.at, name: s.highlight || 'pop-grave', volume: s.volume * 0.85, kind: 'preuve', role: 'impact', at: g.at});
			ui.push(g.at);
		}
	}
	if (s.highlight) {
		let last = -99;
		for (const w of timedWords(reel)) {
			if (!w.hl || w.hide || w.outStart - last < s.highlightGap) continue;
			if (starts.some((b) => Math.abs(b.t - w.outStart) < 0.6)) continue;
			if (ui.some((t) => Math.abs(t - w.outStart) < 1.2)) continue; // l'interface a déjà son son
			ev.push({t: w.outStart, name: s.highlight, volume: s.volume * 0.7, kind: 'mot cle', role: 'mot-fort', at: w.outStart});
			last = w.outStart;
		}
	}
	for (const e of s.extra ?? []) ev.push({t: e.t, name: e.name, volume: s.volume * 0.8 * (e.gain ?? 1), kind: 'ajoute'});
	const placed = s.varier === false ? ev : varySfx(sfxPool(s.pool), ev);
	return placed.map(({t, name, volume, kind}) => ({t, name, volume: volume * (SFX_GAIN[name] ?? 1), kind})).sort((a, b) => a.t - b.t);
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

/** marks : liste (kind 'list') = instant (montage) où chaque élément est dit. */
export type PlacedScene = StyleScene & {at: number; end: number; marks?: number[]};
/** Scènes ancrées à un mot (temps seulement, place enregistrée). */
const anchoredScenes = (reel: ReelDoc): PlacedScene[] => {
	if (reel.design?.enabled === false || !reel.design?.mode) return [];
	const words = timedWords(reel);
	const total = duration(reel);
	const result: PlacedScene[] = [];
	// studio Tech 3D : une interface qui finirait juste après une coupe (moins de 0,7 s) sort SUR la coupe : la coupe porte
	// alors le changement de valeur de plan (une carte qui chevauche une coupe la figeait au même cadre)
	const cuts = studioMode(reel) ? videoSegments(reel).slice(1).map((s) => s.out_start) : [];
	for (const scene of reel.styleScenes ?? []) {
		if (scene.hidden) continue;
		const word = words.find((w) => w.clip === scene.clip && w.index === scene.index && !w.hide);
		if (!word) continue;
		// (une interface qui redit la page en cours est ancrée sur le 1er mot de la page par le moteur : galerie._aligner_pages)
		const at = Math.max(0, word.outStart);
		let end = Math.min(total, at + Math.max(.2, scene.duration));
		const snap = cuts.find((c) => c > at + 1.4 && c < end && end - c <= 0.7);
		if (snap !== undefined && end < total - 0.05) end = snap;
		// bouton précédé de l'offre dite (« gratuitement… une semaine ») : la carte entre sur l'offre (badge seul, au moment où
		// elle est dite), le bouton la rejoint sur son mot (marks[0])
		if (scene.kind === 'cta' && typeof scene.lead === 'number' && scene.lead < scene.index) {
			const lead = words.find((w) => w.clip === scene.clip && w.index === scene.lead && !w.hide);
			if (lead && lead.outStart < at - 0.6 && at - lead.outStart <= 8 && !result.some((s) => lead.outStart < s.end + .5 && end > s.at)) {
				result.push({...scene, at: Math.max(0, lead.outStart), end, marks: [at]});
				continue;
			}
		}
		if (result.some((s) => at < s.end + .5 && end > s.at)) continue;
		// bouton unique tenu jusqu'à la fin : marks = [bouton (= entrée), offre dite] ; offre au mot coupé : affichée dès l'entrée
		if (scene.kind === 'cta' && typeof scene.offer === 'number') {
			const w = words.find((x) => x.clip === (scene.offerClip ?? scene.clip) && x.index === scene.offer && !x.hide);
			result.push({...scene, at, end, marks: w && w.outStart > at + 0.3 && w.outStart < end - 0.5 ? [at, w.outStart] : [at]});
			continue;
		}
		if (scene.kind === 'list') {
			// chaque élément apparaît sur son mot ; un élément sans mot (texte retouché, mot coupé) suit le précédent
			const n = listParts(scene).length;
			const marks: number[] = [];
			for (let k = 0; k < n; k++) {
				const idx = scene.items?.[k];
				const w = idx === undefined ? undefined : words.find((x) => x.clip === scene.clip && x.index === idx && !x.hide);
				const prev = marks.length ? marks[marks.length - 1] : at;
				marks.push(clamp(w ? w.outStart : k ? prev + 0.45 : at, prev, Math.max(prev, end - 0.4)));
			}
			result.push({...scene, at, end, marks});
			continue;
		}
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
			str(w.w); // texte : sous-titres redits par une interface (captionHidden)
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
// plages lues telles quelles dans le cache du détourage : une entrée mal formée (null, nombre seul) est ignorée, jamais fatale
const fallbackRanges = (m: Cutout | null | undefined): [number, number][] => (Array.isArray(m?.fallback) ? m.fallback : [])
	.filter((r): r is [number, number] => Array.isArray(r) && typeof r[0] === 'number' && typeof r[1] === 'number');
export const cutoutFallback = (m: Cutout | null | undefined, srcT: number) => fallbackRanges(m).some(([a, b]) => srcT >= a && srcT < b);
const FALLBACK_RAMP = 0.12;
/** Part de la prise d'origine (0 : personne détourée ; 1 : prise d'origine) : fondu enchaîné de 0,12 s aux bords d'une
 * plage de repli, pour ne jamais sauter d'un rendu à l'autre. */
export const cutoutFallbackMix = (m: Cutout | null | undefined, srcT: number) => {
	let mix = 0;
	for (const [a, b] of fallbackRanges(m)) {
		if (srcT < a - FALLBACK_RAMP || srcT >= b + FALLBACK_RAMP) continue;
		mix = Math.max(mix, clamp(Math.min((srcT - (a - FALLBACK_RAMP)) / FALLBACK_RAMP, (b + FALLBACK_RAMP - srcT) / FALLBACK_RAMP), 0, 1));
	}
	return mix;
};

/** Valeur k d'une piste [[t, v1, v2...], ...] triée par t, à l'instant t (interpolation linéaire, tenue aux deux bouts). */
const trackValue = (track: number[][], t: number, k: number): number | null => {
	const ok = track.filter((p) => Array.isArray(p) && typeof p[0] === 'number' && typeof p[k] === 'number');
	if (!ok.length) return null;
	if (t <= ok[0][0]) return ok[0][k];
	for (let i = 1; i < ok.length; i++) {
		if (t <= ok[i][0]) {
			const [a, b] = [ok[i - 1], ok[i]];
			return a[k] + (b[k] - a[k]) * ((t - a[0]) / Math.max(1e-6, b[0] - a[0]));
		}
	}
	return ok[ok.length - 1][k];
};
/** Haut réel de la tête (cheveux compris, part de la hauteur de la PRISE) à l'instant tSrc, lu dans l'alpha du détourage
 * (cutouts[clip].head, detourage.tete) ; null sans mesure (l'estimation par le visage sert alors). */
export const cutoutHeadTop = (m: Cutout | null | undefined, tSrc: number) => (Array.isArray(m?.head) && m!.head.length ? trackValue(m!.head, tSrc, 1) : null);
/** Table du décor d'origine (polygone 0-1 du cadre de la prise) à l'instant tSrc : `occluder`, dont les deux sommets qui ne
 * sont pas des coins de l'image suivent `occluderTrack` quand la caméra de la prise dérive. */
export const occluderAt = (m: Cutout | null | undefined, tSrc: number): [number, number][] | null => {
	const pts = m?.occluder;
	if (!Array.isArray(pts) || pts.length < 3) return null;
	const track = m!.occluderTrack;
	if (!Array.isArray(track) || !track.length) return pts;
	const a = trackValue(track, tSrc, 1);
	const b = trackValue(track, tSrc, 2);
	if (a === null || b === null) return pts;
	let n = 0;
	return pts.map(([x, y]) => {
		const corner = (x <= 0.002 || x >= 0.998) && (y <= 0.002 || y >= 0.998);
		if (corner) return [x, y] as [number, number];
		const v = n++ === 0 ? a : b;
		// sommet sur un bord vertical : y libre ; sur le bas / le haut : x libre
		return (x <= 0.002 || x >= 0.998 ? [x, v] : [v, y]) as [number, number];
	});
};

// ---------- Studio Tech 3D : personne détourée dans le décor virtuel ----------
/** Style Tech 3D cinématique : la vraie personne détourée est posée dans le studio virtuel (si le détourage existe). */
export const studioMode = (reel: ReelDoc) => reel.design?.enabled !== false && reel.design?.mode === 'produit' && !!reel.design?.cinematic;
const STUDIO_KINDS = new Set(['metric', 'notification', 'dashboard', 'flow', 'cta', 'list']);
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
const ROOM = 1.2; // s : glissement lent de la caméra avant l'entrée d'une interface et après sa sortie (sans coupe ni début de phrase proche)
const SNAP_UI = 1.5; // s : une coupe à moins de 1,5 s de l'entrée / la sortie porte le changement de cadre
const PRE_CUT = 3; // s : sinon une coupe jusqu'à 3 s avant l'entrée (ou après la sortie) porte la bascule, gardée jusqu'à la carte
const EASE_UI = 0.8; // s : sinon bascule seule (sans changement de taille) en glissement adouci autour de l'entrée / la sortie
const DY_ROOM = 0.12; // bascule maximale (part de la hauteur) qui garde le plan de base pendant une interface (format vertical)
const DRIFT_RATE = 0.0022; // poussée lente dans un plan (par seconde), reprise à chaque coupe
const DRIFT_MAX = 0.018;
// Relances de cadre (« punch-in » de monteur) : dans un long passage sans coupe, sans changement de temps du récit et
// sans interface, la caméra change de valeur de plan d'un coup (comme une 2e caméra) au début d'une phrase ou sur un mot
// fort, en alternant plan serré / plan de base. Jamais pendant une interface, jamais juste avant une coupe.
// Écart de valeur de plan d'une relance : x 1,2 (9:16) ; formats larges (prise déjà très agrandie) : x 1,12. En dessous
// de x 1,15, un saut d'image ne se lit pas comme un nouveau plan voulu sur un téléphone mais comme un défaut : le plan de
// base cède alors (au plus PUNCH_MAX / 1,2) pour que le plan serré reste nettement plus serré.
const PUNCH = 0.2;
const PUNCH_MIN = 1.12; // écart minimal d'une relance sans coupe (sinon elle n'a pas lieu)
const PUNCH_GAP = 2.6; // s sans autre relance visible avant une relance de cadre
const PUNCH_AFTER = 1.4; // s : pas de relance si une coupe ou un changement de temps du récit arrive avant
const PUNCH_BEFORE_UI = 2.4; // s : ni juste avant une interface (la caméra lui laisse la place 1 s avant)
const PUNCH_MAX = 1.32; // agrandissement total maximal (au-delà, la prise perd en netteté)
const PUNCH_CUT_MAX = 1.4; // seulement sur une coupe qui, sinon, garderait le même cadre (la personne a reculé dans la prise)
const HEAD_MIN = 0.05; // une relance ne pousse jamais le haut de la tête au-dessus de 5 % de l'image
const OPEN = 0.9; // s : ouverture du film, la caméra arrive sur le visage (poussée franche depuis le plan de base)
const DY_MAX = 0.1; // bascule maximale de la caméra (part de la hauteur) : la personne descend pour laisser la place à une interface
/** faceOnly : le storyboard ne prévoit aucune interface pour ce temps (prise d'origine : accroche, tension, preuve
 * humaine) ; la caméra y tient un plan plus serré, le visage porte le passage. */
type StudioBeat = CreativeBeat & {from: number; snap: boolean; faceOnly?: boolean};
const FACE_FRAME: [number, number] = [0.06, 0.12];
/** Interface affichée pendant [a, b] : agrandissement maximal de la caméra pour qu'elle tienne au-dessus de la tête ;
 * dy : bascule de la caméra (la personne descend, part de la hauteur) quand même le plan de base ne lui laisse pas la place. */
type StudioBusy = {a: number; b: number; smax: number; dy: number;
	/** format vertical : besoin (haut de l'interface + écart, part de la hauteur) et tête la plus haute (sans caméra) : la
	 * caméra bascule d'après son échelle réelle (studioView) */
	need?: number; head?: number;
	/** instants du changement de cadre à l'entrée / à la sortie (coupe proche, sinon l'image où la carte entre / sort) ;
	 * absent : glissement ROOM (ancien calcul) */
	tin?: number; tout?: number;
	/** ein / eout : changement SANS coupe et sans changement de taille (bascule seule) : glissement adouci EASE_UI autour de
	 * tin / tout, jamais un saut d'image (juge n° 3, 2 oct. 2026). pre : tin est une coupe d'avant l'entrée (bascule gardée
	 * jusqu'à la carte ; le plan de base est repris à l'entrée de la carte). */
	ein?: boolean; eout?: boolean; pre?: boolean;
	/** durée du glissement adouci (EASE_UI, plus long pour une bascule de plus de 3 % de la hauteur) */
	span?: number};
/** Valeur de la relance de cadre à partir de t (0 : plan de base, 1 : plan serré) ; une coupe remet 0. */
type StudioPunch = {t: number; level: number;
	/** coupe : plan serré poussé un peu plus (au plus x 1,15) quand aucun des deux niveaux ne change assez la taille à l'écran */
	boost?: number};
type StudioPlan = {beats: StudioBeat[]; gain: number; busy: StudioBusy[]; punches: StudioPunch[]; cuts: number[]};
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
		const shot = (plan?.storyboard ?? []).find((s) => s.beat === b.id);
		return {...b, from: cut ?? b.start, snap: cut !== undefined, faceOnly: shot?.engine === 'prise-originale'};
	});
	// amplitude réglée par le style (zoom.strength) ; formats larges : une prise verticale y est déjà très agrandie
	const gain = clamp(((reel.zoom?.strength ?? 1) - 1) / 0.06, 0, 2) * (reel.height > reel.width ? 1 : 0.5);
	const P = punchGain(reel, gain);
	// interfaces : la caméra ne se desserre que si l'interface ne tiendrait ni au-dessus de la tête ni à côté du visage
	// (pas de va-et-vient) ; 9:16 : jamais sous 1 (studioMinScale)
	const segs = videoSegments(reel);
	const u = Math.min(reel.width, reel.height);
	const portrait = reel.height > reel.width * 1.2;
	const room = (a: number, b: number, size: {w: number; h: number}): StudioBusy => {
		let head = 1;
		let side = 1;
		let fw = 0;
		let minS = 1;
		for (let x = a; x <= Math.max(a, b - 0.05) + 1e-6; x += 0.2) {
			const p = rawPerson(reel, segs, x);
			if (!p) continue;
			head = Math.min(head, p.head);
			side = Math.min(side, Math.max(p.f.cx, 1 - p.f.cx));
			fw = Math.max(fw, p.fw);
			minS = Math.min(minS, studioMinScale(reel, p.f));
		}
		const need = studioTop(reel) + STUDIO_GAP + (size.h * u) / reel.height;
		const above = head < STUDIO_OY ? (STUDIO_OY - need) / (STUDIO_OY - head) : 1;
		if (portrait && beats.length && gain > 0 && head < STUDIO_OY) {
			// format vertical : la caméra garde son plan de base (jamais un recul franc avant chaque carte, juge n° 2) et
			// BASCULE : la personne descend juste sous l'interface (bascule calculée dans studioView d'après l'échelle réelle,
			// au plus DY_ROOM) ; elle ne recule que si la bascule ne suffit pas
			const sb = Math.max(minS, Math.min((minS < 1 ? (1 + minS) / 2 : 1) * (1 + gain * beatFrame(beats, a)), PUNCH_MAX / (1 + P)));
			const tilt = (STUDIO_OY - need + DY_ROOM) / (STUDIO_OY - head);
			// durée d'un glissement de bascule sans coupe : 0,8 s jusqu'à 3 % de la hauteur (invisible), plus long au-delà (au plus
			// 1,6 s : un mouvement de caméra lent et adouci, jamais un saut)
			const shift = clamp(need - (STUDIO_OY - (STUDIO_OY - head) * Math.max(minS, above, Math.min(sb, tilt))), 0, DY_ROOM);
			return {a, b, smax: Math.max(minS, above, Math.min(sb, tilt)), dy: 0, need, head, span: +clamp(EASE_UI * shift / 0.03, EASE_UI, 2 * EASE_UI).toFixed(3)};
		}
		// à côté du visage : la carte réduite à 60 % tient entre l'épaule (1,5 largeur de visage) et le bord
		const beside = fw > 0 ? ((side - 0.02 - (0.6 * size.w * u) / reel.width) * reel.width) / (1.5 * fw) : 0;
		const smax = Math.max(minS, above, beside);
		// ni au-dessus ni à côté, même au plan le plus large permis (9:16 : la caméra ne recule pas sous 1) : la caméra bascule,
		// la personne descend juste assez (au plus DY_MAX) pour que l'interface tienne sous la barre du haut des réseaux
		const dy = head < 1 && above < minS && beside < minS ? clamp(need - (STUDIO_OY + (head - STUDIO_OY) * minS), 0, DY_MAX) : 0;
		return {a, b, smax, dy: +dy.toFixed(4)};
	};
	const busy = anchoredScenes(reel).filter((s) => s.kind !== 'keyword').map((s) => room(s.at, s.end, studioCardSize(s.kind, s.text, s.secondary)));
	for (const g of reel.graphics ?? []) if (studioGraphicShown(reel, g)) busy.push(room(g.at, g.at + g.duration, g.kind === 'chiffre' ? studioCardSize('chiffre', ...studioChiffreText(g)) : studioCardSize('dashboard')));
	// Changement de cadre d'une interface (juge n° 3, 2 oct. 2026 : un recadrage de moins de 5 % sans coupe se lit comme une
	// image qui saute ; un élargissement 1 s avant la carte, comme un geste mécanique) :
	// - SUR une coupe proche (moins de SNAP_UI s avant l'entrée / après la sortie) ;
	// - sinon sur une coupe un peu plus éloignée (PRE_CUT s) si aucune autre interface n'est à l'image entre les deux : la
	//   bascule y est prise et gardée (invisible), le plan de base est repris à l'entrée de la carte ;
	// - sinon SUR l'image où la carte entre (avec son whoosh : la carte « pousse » la personne) ; une bascule seule, sans
	//   changement de taille, y glisse en EASE_UI s adoucies (≤ DY_ROOM) — décidé par studioPunches (ein / eout).
	// Plus jamais sur un simple début de phrase.
	if (beats.length && gain > 0) {
		const total = duration(reel);
		for (const k of busy) {
			const prevEnd = Math.max(-Infinity, ...busy.filter((o) => o !== k && o.b <= k.a + 1e-3).map((o) => o.b));
			const nextStart = Math.min(Infinity, ...busy.filter((o) => o !== k && o.a >= k.b - 1e-3).map((o) => o.a));
			const near = cuts.filter((c) => c >= k.a - SNAP_UI - 1e-3 && c <= k.a + 1e-3);
			const early = cuts.filter((c) => c >= Math.max(k.a - PRE_CUT, prevEnd + 0.3) - 1e-3 && c < k.a - SNAP_UI - 1e-3);
			k.tin = near.length ? near[near.length - 1] : early.length ? early[early.length - 1] : k.a;
			k.pre = !near.length && early.length > 0;
			const nearOut = cuts.filter((c) => c >= k.b - 1e-3 && c <= k.b + SNAP_UI + 1e-3);
			const late = cuts.filter((c) => c > k.b + SNAP_UI + 1e-3 && c <= Math.min(k.b + PRE_CUT, nextStart - 0.3) + 1e-3);
			k.tout = nearOut.length ? nearOut[0] : late.length ? late[0] : k.b;
			// sortie sans coupe : la personne remonte en glissant (la carte s'efface dans le même temps) ; une interface tenue
			// jusqu'à la dernière image ne sort pas (aucun mouvement sur les dernières images)
			k.eout = !nearOut.length && !late.length;
			if (k.b >= total - 0.05) [k.tout, k.eout] = [Infinity, false];
		}
	}
	return {beats, gain, busy, cuts, punches: beats.length && gain > 0 ? studioPunches(reel, cuts, beats, busy, gain) : []};
});
/** Relances de cadre d'un reel (voir PUNCH). Règles de monteur :
 * - coupe franche (même prise resserrée ou autre prise au même cadre) : la valeur de plan CHANGE (plan de base <-> plan
 *   serré), sinon la coupe ressemble à un saut d'image ; sauf si un temps du récit y change déjà le cadre (une interface
 *   à l'image garde sa place : roomCap limite alors l'agrandissement) ;
 * - entrée d'une interface : retour au plan de base (la caméra lui laisse la place) ;
 * - dans un long passage sans relance : début de phrase ou mot en couleur (préféré dans la seconde qui suit), à défaut un
 *   mot plein (5 lettres et plus) ; au moins PUNCH_GAP s après la dernière relance visible, PUNCH_AFTER s avant une coupe ;
 *   la sortie d'une interface relance moins qu'une entrée (comptée 1 s plus tôt). */
const studioPunches = (reel: ReelDoc, cuts: number[], beats: StudioBeat[], busy: StudioBusy[], gain: number): StudioPunch[] => {
	const total = duration(reel);
	// relance sans coupe : seulement si le plan serré peut l'être nettement (tête assez basse dans l'image)
	const segs = videoSegments(reel);
	const P = punchGain(reel, gain);
	const roomy = (t: number) => {
		const r = rawPerson(reel, segs, t);
		if (!r) return false;
		const head = r.head;
		const tight = head < STUDIO_OY - 0.01 ? Math.min(PUNCH_MAX, (STUDIO_OY - HEAD_MIN) / (STUDIO_OY - head)) : PUNCH_MAX;
		const base = Math.max(studioMinScale(reel, r.f), Math.min(1 + gain * beatFrame(beats, t), PUNCH_MAX / (1 + P)));
		return tight / base >= PUNCH_MIN;
	};
	const words = timedWords(reel).filter((w) => !w.hide && displayWord(w.w, false));
	const cands: {t: number; strong: boolean; weak: boolean}[] = [];
	words.forEach((w, i) => {
		const prev = words[i - 1];
		const start = !prev || w.outStart - prev.outEnd >= 0.14 || /[,.;:!?…]["»”)\]]*$/.test(prev.w.trim());
		const full = displayWord(w.w, false).replace(/[^A-Za-zÀ-ÿ]/g, '').length >= 5;
		if (start || w.hl || full) cands.push({t: w.outStart, strong: !!w.hl, weak: !start && !w.hl});
	});
	// changement de temps du récit visible seulement si la valeur de plan change (deux « solution » de suite : non)
	const frameOf = (b: StudioBeat) => (b.faceOnly ? FACE_FRAME : BEAT_FRAME[b.role] ?? [0.04, 0.07]).join(',');
	const reframes = beats.filter((b, i) => i > 0 && frameOf(b) !== frameOf(beats[i - 1])).map((b) => b.from);
	const inBusy = (t: number) => busy.some((k) => t > Math.min(k.a - PUNCH_BEFORE_UI, k.tin ?? k.a) && t < k.b + 0.3);
	const ok = (t: number, last: number, weak = false) => t - last >= PUNCH_GAP + (weak ? 0.6 : 0) && t < total - 1.5 && !inBusy(t)
		&& ![...cuts, ...reframes].some((e) => e > t + 1e-3 && e < t + PUNCH_AFTER) && roomy(t);
	// points fixes dans l'ordre du temps : coupes (bascule), entrées d'interface (plan de base), sorties (relance partielle)
	type Point = {t: number; kind: 'cut' | 'in' | 'out' | 'reframe'; k?: StudioBusy};
	// entrée : plan de base SUR la coupe proche, sinon sur l'image où la carte entre (bascule prise plus tôt sur une coupe : pre)
	const points: Point[] = [...cuts.map((t) => ({t, kind: 'cut' as const})), ...busy.map((k) => ({t: k.pre ? k.a : k.tin ?? k.a, kind: 'in' as const, k})),
		...busy.map((k) => ({t: Math.max(k.a, k.b - 1), kind: 'out' as const})), ...reframes.map((t) => ({t, kind: 'reframe' as const}))]
		.sort((a, b) => a.t - b.t);
	const out: StudioPunch[] = [];
	let last = 0; // dernière relance visible (coupe, temps du récit, interface ou relance de cadre)
	let level = 0;
	let p = 0;
	// taille de la personne à l'écran (largeur du visage x échelle approchée de la caméra, sans interface) pour un niveau
	const onScreen = (t: number, lvl: number) => {
		const r = rawPerson(reel, segs, t);
		if (!r) return 0;
		const minS = studioMinScale(reel, r.f);
		const sb = (minS < 1 ? (1 + minS) / 2 : 1) * (1 + gain * beatFrame(beats, t));
		const room = r.head < STUDIO_OY - 0.01 ? (STUDIO_OY - HEAD_MIN) / (STUDIO_OY - r.head) : PUNCH_MAX;
		const sc = lvl ? Math.max(sb, Math.min(sb * (1 + P), room, PUNCH_MAX)) : Math.max(minS, Math.min(sb, PUNCH_MAX / (1 + P)));
		// une interface à l'image limite le plan (studioView) ; une coupe pendant l'interface y garde un plan serré ANCRÉ sous elle
		const capped = Math.max(minS, roomCap(busy, t, sc));
		const anchored = lvl && capped < sc - 1e-3 && busy.some((k) => t >= k.a - 1e-3 && t < k.b);
		return r.fw * (anchored ? Math.min(capped * (1 + Math.min(P, 0.16)), PUNCH_MAX) : capped);
	};
	const advance = (t: number) => {
		for (; p < points.length && points[p].t <= t + 1e-6; p++) {
			const x = points[p];
			last = Math.max(last, x.t);
			if (x.kind === 'in') {
				// entrée sans coupe, déjà au plan de base : seule la bascule change -> glissement adouci (jamais un saut d'image) ;
				// au plan serré : retour au plan de base d'un coup, sur l'image où la carte entre (× 1,2 : un vrai changement de plan)
				if (x.k && !x.k.pre && x.k.tin === x.k.a && !cuts.some((c) => Math.abs(c - x.t) < 1e-3)) x.k.ein = level === 0;
				level = 0;
				out.push({t: x.t, level});
			} else if (x.kind === 'cut') {
				const reframe = reframes.some((r) => Math.abs(r - x.t) < 0.05);
				// la coupe doit changer franchement la taille de la personne à l'écran (x 1,15 au moins, autre prise comprise) :
				// d'abord le choix habituel (temps du récit : plan de base ; sinon bascule), l'autre s'il change seul assez le cadre
				const first = reframe || x.t > total - 1 ? 0 : 1 - level;
				const before = onScreen(x.t - 0.04, level);
				const gap = (lvl: number) => (before > 0 ? Math.abs(Math.log(onScreen(x.t + 0.04, lvl) / before)) : 1);
				level = x.t > total - 1 || gap(first) >= Math.log(1.15) || gap(1 - first) <= gap(first) ? first : 1 - first;
				// aucun des deux niveaux ne change assez le cadre (la caméra était entre les deux, par ex. pendant une carte) :
				// plan serré poussé jusqu'à x 1,15 de l'image d'avant, si la prise le permet (PUNCH_MAX)
				let boost: number | undefined;
				const r = rawPerson(reel, segs, x.t + 0.04);
				if (x.t <= total - 1 && before > 0 && r && gap(level) < Math.log(1.15)) {
					const tight = onScreen(x.t + 0.04, 1);
					const want = clamp((before * 1.15) / Math.max(1, tight), 1, 1.15);
					// possible SUR la coupe : ni au-delà de PUNCH_CUT_MAX, ni la tête poussée hors de l'image (sinon rien : un
					// agrandissement qui n'arriverait que plus tard dans le plan ne servirait pas la coupe)
					const roomAt = r.head < STUDIO_OY - 0.01 ? (STUDIO_OY - HEAD_MIN) / (STUDIO_OY - r.head) : PUNCH_MAX;
					const anchored = busy.some((k) => x.t >= k.a - 1e-3 && x.t < k.b);
					if (tight > before && (tight / r.fw) * want <= Math.min(PUNCH_CUT_MAX, anchored ? PUNCH_CUT_MAX : roomAt) + 1e-6) [level, boost] = [1, +want.toFixed(4)];
				}
				out.push(boost ? {t: x.t, level, boost} : {t: x.t, level});
			}
		}
	};
	for (let i = 0; i < cands.length; i++) {
		const t = cands[i].t;
		advance(t);
		if (!ok(t, last, cands[i].weak)) continue;
		// un mot fort dans la seconde qui suit porte mieux la relance qu'un début de phrase (ou un simple mot plein)
		const strong = cands.slice(i + 1).find((c) => c.strong && c.t <= t + 1.2 && ok(c.t, last));
		const better = !cands[i].strong && !strong && cands[i].weak
			? cands.slice(i + 1).find((c) => !c.weak && c.t <= t + 1.2 && ok(c.t, last)) : undefined;
		const at = !cands[i].strong && strong ? strong.t : better ? better.t : t;
		advance(at);
		level = 1 - level;
		out.push({t: at, level});
		last = at;
		while (i + 1 < cands.length && cands[i + 1].t <= at) i++;
	}
	advance(total);
	return out.sort((a, b) => a.t - b.t);
};
/** Relance de cadre en cours à l'instant t (0 ou 1) : la dernière avant t, remise à 0 par chaque coupe. */
const punchAt = (punches: StudioPunch[], t: number) => punchNow(punches, t)?.level ?? 0;
/** Relance de cadre en cours à l'instant t (la dernière avant t). */
const punchNow = (punches: StudioPunch[], t: number) => {
	let cur: StudioPunch | undefined;
	for (const p of punches) {
		if (p.t > t + 1e-6) break;
		cur = p;
	}
	return cur;
};
/** Personne à l'instant t SANS la caméra du studio : segment, cadre (framing), largeur du visage (px) et haut de la tête
 * (part de l'image) : mesuré dans l'alpha du détourage si possible (cheveux compris), sinon estimé par le visage. */
const rawPerson = (reel: ReelDoc, segs: Segment[], t: number) => {
	if (!segs.length) return null;
	const seg = segs[segmentAt(segs, t)];
	const tSrc = segSrcTime(seg, t);
	const f = framing(reel, seg.source, tSrc, seg.src_in, seg.src_out);
	const near = (reel.sources[seg.source]?.track ?? []).filter((p) => Math.abs(p[0] - tSrc) <= 0.6 && p[3] > 0);
	const m = validCutout(reel, seg);
	// largeur du visage : piste de recadrage, sinon celle mesurée avec la tête dans le détourage, sinon 25 % de la prise
	const mw = !near.length && Array.isArray(m?.head) ? trackValue(m!.head, tSrc, 2) : null;
	const fw = (near.length ? median(near.map((p) => p[3])) : mw && mw > 0.05 ? mw : 0.25) * f.width;
	const top = cutoutHeadTop(m, tSrc);
	return {seg, f, fw, head: top !== null ? (f.top + top * f.height) / reel.height : f.cy - (STUDIO_HEAD * fw) / reel.height};
};
/** Valeur de plan (agrandissement - 1) du temps du récit en cours : changement sur une coupe proche, sinon recadrage doux. */
const beatFrame = (beats: StudioBeat[], t: number) => {
	const at = (b: StudioBeat, x: number) => {
		let [a, z] = BEAT_FRAME[b.role] ?? [0.04, 0.07];
		if (b.faceOnly) [a, z] = [Math.max(a, FACE_FRAME[0]), Math.max(z, FACE_FRAME[1])];
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
/** Présence (0..1) d'une interface pour la caméra : mouvement doux pendant ROOM s avant son entrée et après sa sortie ; une
 * coupe dans ces fenêtres porte le changement (la caméra change de cadre SUR la coupe, comme un vrai monteur, au lieu de
 * glisser autour). */
const presence = (k: StudioBusy, t: number) => {
	// glissement adouci : 3/4 avant l'instant (la tête est presque sous la carte quand elle apparaît), 1/4 après
	const e = k.span ?? EASE_UI;
	const pin = k.tin === undefined ? smooth((t - (k.a - ROOM)) / ROOM) : k.ein ? smooth((t - (k.tin - e * 0.75)) / e)
		: t >= k.tin - 1e-6 ? 1 : 0;
	const pout = k.tout === undefined ? smooth((k.b + ROOM - t) / ROOM) : k.eout ? smooth((k.tout + e * 0.75 - t) / e)
		: t < k.tout - 1e-6 ? 1 : 0;
	return Math.min(pin, pout);
};
/** Agrandissement limité pendant une interface qui manquerait de place : desserrage avant son entrée, retour après. */
const roomCap = (busy: StudioBusy[], t: number, s: number) => busy.reduce((out, k) => {
	if (s <= k.smax) return out;
	const pres = presence(k, t);
	return pres > 0 ? Math.min(out, s - (s - k.smax) * pres) : out;
}, s);
/** Bascule de la caméra (part de la hauteur, la personne descend) pendant les interfaces qui en ont besoin. Format vertical :
 * juste assez, pour l'échelle réelle de la caméra, pour que la tête la plus haute passe sous l'interface (au plus DY_ROOM). */
const roomShift = (busy: StudioBusy[], t: number, scale: number) => busy.reduce((out, k) => {
	const d = k.need !== undefined && k.head !== undefined ? clamp(k.need - (STUDIO_OY - (STUDIO_OY - k.head) * scale), 0, DY_ROOM) : k.dy;
	return d > 0 ? Math.max(out, d * presence(k, t)) : out;
}, 0);
/** Écart d'une relance de cadre (1 + P) : amplitude du style, moindre dans les formats larges. */
const punchGain = (reel: ReelDoc, gain: number) => PUNCH * Math.min(1, gain) * (reel.height > reel.width ? 1 : 0.6);

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
export type StudioView = {scale: number; ox: number; oy: number; bg: number; wide?: boolean;
	/** bascule de la caméra : la personne (et le studio, moins) descend de dy (part de la hauteur) ; translateY avant scale. */
	dy?: number};
/** Haut de la tête (part de l'image, sans la caméra du studio) d'un segment à l'instant t : mesuré dans le détourage, sinon
 * estimé par le visage (même règle que rawPerson). */
const headOf = (reel: ReelDoc, seg: Segment, f: {top: number; height: number; width: number; cy: number}, t: number) => {
	const tSrc = segSrcTime(seg, t);
	const top = cutoutHeadTop(validCutout(reel, seg), tSrc);
	if (top !== null) return (f.top + top * f.height) / reel.height;
	const fw = (reel.sources[seg.source]?.track ?? []).filter((q) => Math.abs(q[0] - tSrc) <= 0.6 && q[3] > 0);
	return f.cy - (STUDIO_HEAD * (fw.length ? median(fw.map((q) => q[3])) : 0.25) * f.width) / reel.height;
};
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
	let dy = 0;
	if (override !== undefined) scale = Math.max(minS, base * override); // zoom du plan réglé à la main : cadre fixe
	else if (planned) {
		const drift = Math.min(DRIFT_MAX, DRIFT_RATE * Math.max(0, t - seg.out_start));
		let s = base * (1 + p.gain * (beatFrame(p.beats, t) + drift));
		// amplitude suivant le zoom du style (gain 1 = style de référence) ; formats larges : moindre
		const P = punchGain(reel, p.gain);
		if (p.punches.length && P > 0) {
			const now = punchNow(p.punches, t);
			if (now?.level) {
				// relance de cadre : plan plus serré, sans pousser le haut de la tête hors de l'image ni trop agrandir la prise
				const head = headOf(reel, seg, f, t);
				const room = head < STUDIO_OY - 0.01 ? (STUDIO_OY - HEAD_MIN) / (STUDIO_OY - head) : PUNCH_MAX;
				s = Math.max(s, Math.min(s * (1 + P) * (now.boost ?? 1), room, now.boost ? PUNCH_CUT_MAX : PUNCH_MAX));
			} else s = Math.max(minS, Math.min(s, PUNCH_MAX / (1 + P))); // le plan de base cède : la relance reste nettement plus serrée
		}
		// ouverture : la 1re image (la miniature) est SERRÉE sur le visage, puis la caméra recule en OPEN s vers le plan de
		// l'accroche (un mouvement qui se voit) ; avant, une poussée de x 1,11 depuis le plan large ne se lisait pas (juge n° 2)
		if (seg.out_start < 1e-6 && t < OPEN) {
			const head = headOf(reel, seg, f, t);
			const room = head < STUDIO_OY - 0.01 ? (STUDIO_OY - HEAD_MIN) / (STUDIO_OY - head) : PUNCH_MAX;
			const tight = Math.max(s, Math.min(s * (1 + Math.max(P, 0.12)), room, PUNCH_MAX));
			s = tight + (s - tight) * (1 - Math.pow(1 - clamp(t / OPEN, 0, 1), 3));
		}
		scale = Math.max(minS, roomCap(p.busy, t, s));
		dy = roomShift(p.busy, t, scale);
		// relance posée par une coupe PENDANT l'interface (pas pendant le desserrage qui la précède)
		let lp: StudioPunch | undefined;
		for (const q of p.punches) if (q.t <= t + 1e-6) lp = q;
		const inside = !!lp && lp.level === 1 && p.busy.some((k) => lp!.t >= k.a - 1e-3 && lp!.t < k.b && t < k.b);
		if (inside && scale < s - 1e-3 && P > 0) {
			// une interface empêche le plan serré (une coupe y bascule pourtant de valeur de plan) : plan serré ANCRÉ sous le haut
			// de la tête — la personne grandit vers le bas, la tête reste sous l'interface (la caméra descend d'autant)
			const head = headOf(reel, seg, f, t);
			const tight = Math.min(scale * (1 + Math.min(P, 0.16)) * (lp!.boost ?? 1), lp!.boost ? PUNCH_CUT_MAX : PUNCH_MAX);
			if (head < STUDIO_OY && tight > scale) {
				dy = Math.min(dy + (STUDIO_OY - head) * (tight - scale), DY_MAX * 2);
				scale = tight;
			}
		}
	}
	// recul (échelle < 1) : le centre descend juste assez pour que le bas de la prise couvre toujours le bas de l'image
	const bottom = (f.top + f.height) / reel.height;
	const oy = scale < 1 ? clamp((1 - bottom * scale) / (1 - scale), STUDIO_OY, 1) : STUDIO_OY;
	return {scale, ox: f.cx, oy, bg: 1 + Math.max(0, scale - 1) * 0.3, wide: minS < 1, ...(dy > 1e-4 ? {dy: +dy.toFixed(4)} : {})};
};

/** Échelle du DÉCOR du studio (design.tsx) : parallaxe de la caméra (bg) et, pendant une bascule, assez grande pour que le
 * décor décalé de 0,3·dy couvre toujours le haut de l'image (centre à mi-hauteur : bord haut = H/2·(1 − s) + 0,3·dy).
 * Sans cela, la bascule laissait voir le fond du conteneur en haut (bande noire à bord net, juge n° 2, 2 oct. 2026). */
export const studioDecorScale = (reel: ReelDoc, v: StudioView) => Math.max(v.bg, v.dy ? 1 + v.dy * 0.6 + 4 / reel.height : 1);

/** Personne à l'instant t (part de l'image, caméra du studio comprise) : centre du visage, haut de la tête, demi-largeur
 * des épaules. Visage : piste de recadrage sinon échantillons d'analyse ; largeur du visage par défaut 25 % de la prise. */
export const studioPersonAt = (reel: ReelDoc, segs: Segment[], t: number) => {
	const r = rawPerson(reel, segs, t);
	if (!r) return null;
	const {seg, f} = r;
	const v = studioView(reel, seg, t) ?? {scale: 1, ox: f.cx, oy: f.cy, bg: 1};
	const fx = v.ox + (f.cx - v.ox) * v.scale;
	const fy = v.oy + (f.cy - v.oy) * v.scale + (v.dy ?? 0);
	const fw = r.fw * v.scale; // px
	// haut de la tête : mesuré dans le détourage (rawPerson), passé par la même caméra que le visage
	return {fx, fy, fw, head: v.oy + (r.head - v.oy) * v.scale + (v.dy ?? 0), half: (1.5 * fw) / reel.width};
};

/** Gabarit des interfaces du studio (échelle 1), en part du petit côté u : largeur, hauteur. MÊMES valeurs que les
 * cartes de design.tsx (StudioCard) et le chiffre de graphics.tsx : sert à les poser hors de la personne. */
export const studioCardSize = (kind: string, text = '', secondary = ''): {w: number; h: number} => {
	if ((kind === 'metric' || kind === 'chiffre') && String(text || '').trim()) {
		const b = studioMetricBox(String(text), String(secondary || ''));
		return {w: b.w, h: b.h};
	}
	if (kind === 'list') {
		const l = studioListLayout(listParts({text, secondary}));
		return {w: l.w, h: l.h};
	}
	const parts = [text, ...String(secondary || '').split('|')].map((x) => x.trim()).filter(Boolean).length;
	if (kind === 'flow') return {w: 0.92, h: parts > 2 ? 0.48 : 0.15};
	if (kind === 'dashboard') return {w: 0.86, h: 0.17 + 0.11 * Math.max(1, Math.min(3, parts - 1))};
	// notification : hauteur de son CONTENU (StudioCard : marges 2 x 0,036 u, ligne de l'appli 0,07 u, écart 0,02 u, titre
	// 0,058 u x 1,14 par ligne, sur 0,756 u de large)
	if (kind === 'notification') return {w: 0.84, h: +(0.168 + 0.0661 * (studioTextEm(String(text || '')) * 0.058 > 0.756 ? 2 : 1)).toFixed(3)};
	// bouton : l'offre dite (un chiffre : « 1 semaine gratuite ») est un badge de verre au-dessus ; sinon la marque, discrète
	if (kind === 'cta') return {w: 0.82, h: /\d/.test(String(secondary || '')) ? 0.3 : secondary ? 0.24 : 0.17};
	return {w: 0.72, h: 0.33}; // metric, chiffre sans texte connu
};
/** Chasse (em) d'un texte en Manrope 800, chasses mesurées sur assets/fonts/Manrope.ttf (chiffres 0,45-0,67, espace 0,2). */
export const studioTextEm = (s: string) => [...s].reduce((n, c) => n + (/\s/.test(c) ? 0.2 : /[ijlI|'’.,:;!]/.test(c) ? 0.3
	: /[1frt\-]/.test(c) ? 0.45 : /[mwMWœŒ%]/.test(c) ? 0.9 : /[A-Z0-9ÀÂÇÉÈÊËÎÏÔÙÛ$€£]/.test(c) ? 0.66 : 0.6), 0);
/** Chiffre du studio Tech 3D (pilule de verre + libellé dessous), en part du petit côté u : taille du nombre, marges de la
 * pilule, gabarit total. Un nombre court (« ×5 », « 3 h ») est grand (0,21 u) : la preuve domine l'image, comme la pilule
 * « 8x » de la référence ; un texte plus long se resserre pour que la pilule tienne dans environ 0,8 u. MÊMES valeurs pour
 * StudioMetric (design.tsx) et le placement hors de la personne (studioCardSize -> studioSpot). */
export const studioMetricBox = (text: string, label = '') => {
	const em = Math.max(0.5, studioTextEm(text));
	const font = clamp(0.62 / em, 0.1, 0.21);
	const padY = 0.2 * font;
	const padX = 0.42 * font;
	const labelFont = 0.054;
	const pillW = em * font + 2 * padX + 0.008;
	const pillH = font + 2 * padY + 0.008;
	const labelW = label ? studioTextEm(label) * labelFont + label.length * 0.0015 : 0;
	return {font, padX, padY, labelFont, w: +Math.max(pillW, labelW).toFixed(3), h: +(pillH + (label ? 0.012 + labelFont * 1.25 : 0)).toFixed(3)};
};
/** Éléments d'une liste (text puis secondary séparé par « | »), sans doublon, 5 au plus. */
export const listParts = (s: {text?: string; secondary?: string}) => [s.text ?? '', ...String(s.secondary ?? '').split('|')]
	.map((x) => x.trim()).filter((x, i, a) => x && a.indexOf(x) === i).slice(0, 5);
/** Liste du studio Tech 3D : pilules de verre (repère + texte) rangées en lignes dans l'ordre où elles sont dites, le moins
 * de lignes possible (largeur 0,96 u au plus), lignes équilibrées. Tailles en part du petit côté u. MÊMES valeurs pour
 * StudioCard (design.tsx), le placement hors de la personne (studioCardSize) et le contrôle qualité. */
export const studioListLayout = (parts: string[]) => {
	const font = parts.length === 1 ? 0.058 : parts.length <= 3 ? 0.052 : 0.045; // un badge seul (preuve dite) : plus lisible
	const padY = 0.02;
	const padX = 0.03;
	const marker = font * 0.92;
	const markerGap = 0.014;
	const gap = 0.016;
	const maxW = 0.96;
	const pillH = font * 1.18 + 2 * padY + 0.008;
	const widths = parts.map((p) => studioTextEm(p) * font + marker + markerGap + 2 * padX + 0.008);
	const rowW = (r: number[]) => r.reduce((n, i) => n + widths[i], 0) + gap * Math.max(0, r.length - 1);
	// toutes les coupes en lignes qui gardent l'ordre (5 éléments au plus : 16 essais) : le moins de lignes qui tiennent
	// dans 0,96 u, puis la ligne la plus large la plus courte (lignes équilibrées)
	let rows: number[][] = parts.map((_, i) => [i]);
	let best = [Infinity, Infinity];
	for (let mask = 0; mask < 1 << Math.max(0, parts.length - 1); mask++) {
		const tryRows: number[][] = [[0]];
		for (let i = 1; i < parts.length; i++) {
			if (mask & (1 << (i - 1))) tryRows.push([i]);
			else tryRows[tryRows.length - 1].push(i);
		}
		const widest = Math.max(...tryRows.map(rowW));
		if (widest > maxW && tryRows.length < parts.length) continue;
		if (tryRows.length < best[0] || (tryRows.length === best[0] && widest < best[1])) {
			best = [tryRows.length, widest];
			rows = tryRows;
		}
	}
	const w = Math.min(0.96, Math.max(...rows.map(rowW), 0.2));
	return {font, padX, padY, marker, markerGap, gap, pillH, rows, widths: widths.map((x) => +x.toFixed(4)), w: +w.toFixed(3),
		h: +(rows.length * pillH + (rows.length - 1) * gap).toFixed(3)};
};
/** Texte final et libellé d'un chiffre de la piste Graphismes (même format que graphics.tsx) : sert au gabarit du studio,
 * calculé sur la valeur FINALE (la pilule ne change pas de taille pendant le défilement). */
export const studioChiffreText = (g: Graphic): [string, string] => {
	const p = g.props ?? {};
	const value = Number(p.value) || 0;
	const decimals = Number.isInteger(value) ? 0 : 1;
	const shown = value.toLocaleString('fr-CA', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
	const [prefix, suffix] = chiffreAffixes(g);
	return [`${prefix}${shown}${suffix}`, p.label ? String(p.label) : ''];
};
/** Préfixe et suffixe affichés d'un chiffre : un multiplicateur s'écrit APRÈS le nombre (« 5× moins cher » : « ×5 » se lit
 * « multiplié par 5 », le contraire de ce qui est dit). */
export const chiffreAffixes = (g: Graphic): [string, string] => {
	const p = g.props ?? {};
	const pre = String(p.prefix ?? '');
	const suf = String(p.suffix ?? '');
	return /^\s*[×x]\s*$/.test(pre) && !suf.trim() ? ['', '×'] : [pre, suf];
};

/** Largeur d'un mot de sous-titre en em pour une grotesque grasse (chasses de Manrope 800, espacement -0,012 em compris). */
export const studioCaptionEm = (w: string) => [...w].reduce((n, c) => n - 0.012 + (/[ijlI|'’.,:;!]/.test(c) ? 0.31 : /[frt\-1]/.test(c) ? 0.43
	: /[mwMWœŒ%]/.test(c) ? 0.9 : /[A-Z0-9ÀÂÇÉÈÊËÎÏÔÙÛ]/.test(c) ? 0.68 : 0.6), 0);
const CAPTIONS = new WeakMap<ReelDoc, {key: number; v: Map<string, {fontSize: number; top: number; lines: number}>}>();
/** Sous-titres du studio Tech 3D : taille (px) et hauteur du centre (part de l'image) d'une page. MÊME calcul pour l'image
 * (Captions de Reel.tsx) et le contrôle qualité. Une page tient sur UNE ligne si possible : la police se resserre jusqu'à
 * 80 % de la taille du style, jamais sous 0,06 u (≈ 65 px pour 1080 px, lisible sur un téléphone) ; au-delà, deux lignes
 * équilibrées. Hauteur : celle du style, descendue juste sous la bouche si la personne la couvrirait (formats larges, où la
 * prise verticale est très agrandie ; poussée de la caméra), sans entrer dans la bande du bas des réseaux. */
export const studioCaptionLayout = (reel: ReelDoc, page: Page) => {
	const s = reel.style;
	const all = memo(CAPTIONS, reel, () => new Map<string, {fontSize: number; top: number; lines: number}>());
	const key = `${page.start}|${page.end}|${s.size}|${s.position}|${s.uppercase}|${s.font}`;
	const hit = all.get(key);
	if (hit) return hit;
	const W = reel.width;
	const H = reel.height;
	const u = Math.min(W, H);
	const base = (s.size * u) / 1080;
	const em = page.words.reduce((n, w) => n + 0.2 + studioCaptionEm(displayWord(w.w, s.uppercase)), 0.2 * (page.words.length - 1));
	// largeur utile 80 % : la colonne de boutons des réseaux (à droite, x > 88 %) n'est jamais touchée
	const room = W * 0.8;
	let fontSize = base;
	if (em * base > room) fontSize = Math.max(base * Math.max(0.8, room / (em * base)), Math.min(base, u * 0.06));
	// police resserrée juste à la largeur utile : l'arrondi ne doit pas compter une 2e ligne
	const lines = em * fontSize > room * 1.005 ? Math.ceil((em * fontSize) / (room * 1.005)) : 1;
	const half = (fontSize * 1.14 * lines) / 2;
	let top = s.position;
	if (studioMode(reel)) {
		// bas de la bouche : centre du visage + 0,62 largeur de visage (boîte MediaPipe), caméra du studio comprise
		const segs = videoSegments(reel);
		let mouth = 0;
		for (let x = page.start; x <= Math.max(page.start, page.end - 0.04) + 1e-6; x += 0.25) {
			const p = studioPersonAt(reel, segs, x);
			if (p) mouth = Math.max(mouth, p.fy * H + 0.62 * p.fw);
		}
		const need = (mouth + 0.012 * H + half) / H;
		const floor = (H * (H > W ? 0.8 : 0.9) - half) / H; // 9:16 : interface des réseaux en bas ; formats larges : 10 %
		if (need > top) top = Math.max(top, Math.min(need, floor));
	}
	const v = {fontSize, top: +top.toFixed(4), lines};
	all.set(key, v);
	return v;
};
/** Haut de l'image laissé libre au-dessus d'une interface du studio. 9:16 : barre du haut de TikTok, Reels et Shorts (onglets,
 * recherche, titre « Reels ») ≈ 12 % de la hauteur ; formats plus larges : 6 %. */
const studioTop = (reel: ReelDoc) => (reel.height >= reel.width * 1.5 ? 0.12 : 0.06);
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
	const top = studioTop(reel);
	const room = head - STUDIO_GAP - top;
	if (room >= ch * 0.8) {
		const scale = Math.min(1, room / ch);
		const h = ch * scale;
		// dans l'espace libre, un peu plus près de la tête que du bord : le regard va du visage à l'interface
		return {x: 0.5, y: +Math.max(top + h / 2, head - STUDIO_GAP - h / 2 - (room - h) * 0.35).toFixed(4), scale: +scale.toFixed(3)};
	}
	const left = fx - half - 0.02;
	const right = 1 - fx - half - 0.02;
	const side = Math.max(left, right);
	if (side >= cw * 0.6) {
		const scale = Math.min(1, side / cw);
		const w = cw * scale;
		return {x: +(left >= right ? left - w / 2 + 0.01 : 1 - right + w / 2 - 0.01).toFixed(4), y: +clamp(head + ch * scale * 0.6, top + ch / 2, 0.6).toFixed(4), scale: +scale.toFixed(3)};
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
		spot = studioSpot(reel, 'chiffre', g.at, g.at + g.duration, stored, studioCardSize('chiffre', ...studioChiffreText(g)));
		all.set(key, spot);
	}
	return spot;
};
/** Interfaces du studio Tech 3D dessinées en cartes de verre (StudioCard de design.tsx) et posées par studioSpot. */
export const isStudioCard = (reel: ReelDoc, kind: string) => studioMode(reel) && STUDIO_KINDS.has(kind);

// ---------- Ce qui passe par-dessus l'image, et les sous-titres pendant une interface ----------
/** Éléments par-dessus l'image à l'instant t (MÊME règle que Reel.tsx, lue aussi par le contrôle qualité) :
 * - extras : le style n'a pas d'habillage (graphismes et plans de coupe affichés tels quels) ;
 * - planned : preuve automatique décidée par le storyboard (graphisme auto pendant un plan « remotion-graphisme ») ;
 * - user : graphisme posé / retouché à la main ou verrouillé, dans un style avec habillage ;
 * - manual : un graphisme ou un plan de coupe occupe l'image (les scènes du style s'effacent) ;
 * - scene : scène du style affichée (aucune pendant manual ni dans Éditorial, dont les mots géants sont dans le texte). */
export type Overlay = {extras: boolean; planned: boolean; user: boolean; manual: boolean; scene: PlacedScene | null; graphics: Graphic[]};
export const overlayAt = (reel: ReelDoc, t: number): Overlay => {
	const mode = reel.design?.enabled === false ? null : reel.design?.mode;
	const extras = !mode || reel.design?.suppressExtras === false;
	const gs = (reel.graphics ?? []).filter((g) => !g.suggested && t >= g.at && t < g.at + g.duration);
	const planned = gs.some((g) => g.auto) && (reel.creativePlan?.storyboard ?? []).some((s) => s.engine === 'remotion-graphisme' && t >= s.start - 0.3 && t <= s.end + 0.4);
	const user = !extras && !planned && gs.some((g) => g.manual || g.locked);
	const manual = planned || user || (extras && (gs.length > 0 || (reel.broll ?? []).some((b) => t >= b.at && t < b.at + b.duration)));
	const scene = !manual && mode && mode !== 'editorial' ? designScenes(reel).find((g) => t >= g.at && t < g.end) ?? null : null;
	return {extras, planned, user, manual, scene, graphics: extras || planned ? gs : user ? gs.filter((g) => g.manual || g.locked) : []};
};
const PAGE_CACHE = new WeakMap<ReelDoc, {key: number; v: Page[]}>();
/** Page de sous-titres affichée à l'instant t (pages() gardées en mémoire par reel). */
export const pageAt = (reel: ReelDoc, t: number): Page | null => memo(PAGE_CACHE, reel, () => pages(reel)).find((p) => t >= p.start && t < p.end) ?? null;
// mots vides (articles, pronoms, liaisons) : ils ne comptent pas pour savoir si une interface « dit » la même chose
const SAY_STOP = new Set(('le la les l un une des du de d a au aux et ou en y ne n pas que qu qui ce c ca se s sa son ses ma mon mes ta ton tes '
	+ 'nos notre vos votre leur leurs je j tu il elle on nous vous ils elles me m te t lui est sont pour par avec sans dans sur chez si '
	+ 'the an of to and or in on at for is are it you we').split(' '));
// chiffres dits en lettres, « fois » = ×, unités de temps : « cinq fois moins cher » = « 5× moins cher »
const SAY_NUM: Record<string, string> = {deux: '2', trois: '3', quatre: '4', cinq: '5', six: '6', sept: '7', huit: '8', neuf: '9', dix: '10',
	onze: '11', douze: '12', quinze: '15', vingt: '20', trente: '30', cent: '100', mille: '1000', two: '2', three: '3', four: '4', five: '5',
	ten: '10', fois: 'x', times: 'x', heure: 'h', heures: 'h', hour: 'h', hours: 'h', minute: 'min', minutes: 'min'};
/** Mots porteurs d'un texte (minuscules, sans accents, pluriel simple retiré, chiffres en lettres -> chiffres). */
export const sayTokens = (text: string) => text.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/×/g, ' x ')
	.split(/[^a-z0-9]+/).filter(Boolean).map((w) => SAY_NUM[w] ?? (w.length > 3 && w.endsWith('s') ? w.slice(0, -1) : w)).filter((w) => !SAY_STOP.has(w));
/** La page redit ce que l'interface affiche : au moins 2 de ses mots porteurs ET au moins la moitié d'entre eux, ou tous. */
const saysSame = (page: Page, shown: string[]) => {
	const words = page.words.flatMap((w) => sayTokens(w.w));
	if (!words.length) return false;
	const set = new Set(shown.flatMap(sayTokens));
	const hit = words.filter((w) => set.has(w)).length;
	// ou une page courte dont TOUS les mots porteurs sont à l'écran (« des vacances » sous la pilule « Vacances »)
	return (hit >= 2 && hit >= 0.5 * words.length) || (hit >= 1 && hit === words.length);
};
// interfaces dont le texte EST la parole (liste dite, bouton, parcours, chiffre, autocollant) : la page qui le redit s'efface ;
// une notification ou un tableau résument l'idée sans la répéter, les sous-titres restent
const SAID_KINDS = new Set(['list', 'cta', 'flow', 'metric', 'paper']);
// hauteur approximative des scènes hors studio (part du petit côté), comme Scene de design.tsx
const SCENE_H: Record<string, number> = {notification: 0.21, metric: 0.3, dashboard: 0.36, flow: 0.17, cta: 0.22, comparison: 0.26, paper: 0.17, list: 0.3};
/** Bande verticale [haut, bas] (part de la hauteur) d'une scène affichée. */
const sceneBand = (reel: ReelDoc, g: PlacedScene): [number, number] => {
	const u = Math.min(reel.width, reel.height);
	const h = (g.kind === 'product' ? 0.45 * reel.height : (isStudioCard(reel, g.kind) ? studioCardSize(g.kind, g.text, g.secondary).h : SCENE_H[g.kind] ?? 0.25) * u)
		* (g.scale || 1) / reel.height;
	return [g.y - h / 2, g.y + h / 2];
};
/** Bande verticale [haut, bas] (part de la hauteur) d'une page de sous-titres (deux lignes au plus hors studio). */
const captionBand = (reel: ReelDoc, page: Page): [number, number] => {
	if (studioMode(reel)) {
		const l = studioCaptionLayout(reel, page);
		const half = (l.fontSize * 1.14 * l.lines) / 2 / reel.height;
		return [l.top - half, l.top + half];
	}
	const half = ((reel.style.size * Math.min(reel.width, reel.height)) / 1080) * 1.1 / reel.height;
	return [reel.style.position - half, reel.style.position + half];
};
/** Sous-titres masqués à l'instant t. Règle de monteur : on n'enlève JAMAIS le texte de la parole juste parce qu'une interface
 * est à l'image (sans le son, un tiers du message disparaissait) ; la page s'efface seulement si :
 * - une scène du style la recouvrirait (même hauteur dans l'image), ou
 * - l'élément affiché redit les mêmes mots (liste dite, bouton, parcours, chiffre : jamais deux fois le même mot à l'écran).
 * Styles sans habillage : inchangé (les sous-titres restent toujours). Décision par page entière : jamais un bout de page. */
export const captionHidden = (reel: ReelDoc, t: number): boolean => captionHiddenWhy(reel, t) !== '';
/** Une page masquée en partie n'est jamais montrée moins de 0,6 s : un bout visible plus court est masqué aussi (sous-titre
 * éclair de 0,2 s avant une carte qui le redit, juge n° 3 du 2 oct. 2026). */
const PAGE_MIN_SHOWN = 0.6;
type Hide = [number, number, 'recouvert' | 'redit'];
const HIDES = new WeakMap<ReelDoc, {key: number; v: Map<Page, Hide[]>}>();
const pageHides = (reel: ReelDoc) => memo(HIDES, reel, () => {
	const out = new Map<Page, Hide[]>();
	const step = 1 / (reel.fps || 30);
	for (const p of memo(PAGE_CACHE, reel, () => pages(reel))) {
		const runs: {a: number; b: number; why: '' | 'recouvert' | 'redit'}[] = [];
		for (let k = 0; p.start + k * step < p.end - 1e-6; k++) {
			const t = p.start + k * step;
			const why = pageHiddenWhy(reel, t, p);
			const last = runs[runs.length - 1];
			if (last && last.why === why) last.b = t + step;
			else runs.push({a: t, b: t + step, why});
		}
		if (runs.every((r) => !r.why)) continue;
		for (let i = 0; i < runs.length; i++) {
			const r = runs[i];
			if (r.why || r.b - r.a >= PAGE_MIN_SHOWN - 1e-6) continue;
			r.why = runs[i - 1]?.why || runs[i + 1]?.why || '';
		}
		out.set(p, runs.filter((r) => r.why).map((r) => [r.a, Math.min(p.end, r.b), r.why as 'recouvert' | 'redit']));
	}
	return out;
});
/** Raison du masquage (contrôle qualité) : 'recouvert' (une scène est à la hauteur des sous-titres), 'redit' (l'élément affiche
 * les mêmes mots : le message reste à l'écran) ou '' (sous-titres affichés). */
export const captionHiddenWhy = (reel: ReelDoc, t: number): '' | 'recouvert' | 'redit' => {
	const mode = reel.design?.enabled === false ? null : reel.design?.mode;
	if (!mode) return '';
	const page = pageAt(reel, t);
	if (!page) return '';
	const h = pageHides(reel).get(page);
	return h?.find(([a, b]) => t >= a - 1e-6 && t < b - 1e-6)?.[2] ?? '';
};
/** Masquage brut d'une page à l'instant t (avant la règle de durée minimale PAGE_MIN_SHOWN). */
const pageHiddenWhy = (reel: ReelDoc, t: number, page: Page): '' | 'recouvert' | 'redit' => {
	const o = overlayAt(reel, t);
	const g = o.scene && o.scene.kind !== 'keyword' && (o.scene.kind !== 'product' || reel.design?.productVideo) ? o.scene : null;
	if (g) {
		const [a, b] = sceneBand(reel, g);
		const [c, d] = captionBand(reel, page);
		if (a < d && c < b) return 'recouvert';
		if (SAID_KINDS.has(g.kind) && saysSame(page, [g.text, ...String(g.secondary ?? '').split('|')])) return 'redit';
	}
	for (const x of o.graphics) {
		if (x.kind === 'chiffre' && saysSame(page, studioChiffreText(x))) return 'redit';
		if (x.kind === 'motgeant' && saysSame(page, [String(x.props?.text ?? '')])) return 'redit';
	}
	return '';
};

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
	const dy = (view?.dy ?? 0) * r.height; // bascule de la caméra du studio (translateY avant le zoom)
	// le zoom agrandit autour de (ox, oy) : le coin (0, 0) de l'image montre le point o - (o + dy) / scale du cadre
	return {clip: seg.clip, source: seg.source, tSrc, scale,
		x: (ox - ox / scale - f.left) / f.width, y: (oy - (oy + dy) / scale - f.top) / f.height, w: r.width / scale / f.width, h: r.height / scale / f.height};
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
