// Operations de montage (instantanees, sans recalcul) : changer de prise, couper, J/L-cuts, deplacer, couleur.
import {mergeFragments} from '../../remotion/src/timeline';
import type {Clip, ReelDoc, Word} from '../../remotion/src/types';

export type TakeOption = {source: string; name: string; score: number; notes: string[]; parts: Record<string, number>; in: number; out: number; words: {w: string; start: number; end: number}[]; text: string};
export type RawWord = {w: string; start: number; end: number};

export const norm = (w: string) => w.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9']/g, '');
const signature = (c: Clip) => `${c.source}|${c.in}|${c.out}|${c.tighten}`;

export const mapClip = (reel: ReelDoc, id: string, fn: (c: Clip) => Clip): ReelDoc => ({...reel, clips: reel.clips.map((c) => (c.id === id ? fn(c) : c))});

/** Les propositions de l'IA d'un plan visent des numeros de mots : on les oublie quand ses mots changent. */
const dropSuggestions = (reel: ReelDoc, id: string): ReelDoc => {
	const s = reel.suggestions;
	if (!s || (!s.words[id] && !s.emojis[id])) return reel;
	const {[id]: _w, ...words} = s.words;
	const {[id]: _e, ...emojis} = s.emojis;
	return {...reel, suggestions: {...s, words, emojis}};
};

/** Change la prise d'un plan ; les mots mis en couleur sont retrouves dans la nouvelle prise. */
export const setTake = (reel: ReelDoc, id: string, opt: TakeOption, choice: number): ReelDoc =>
	mapClip(dropSuggestions(reel, id), id, (c) => {
		const colored = new Set(c.words.filter((w) => w.hl).map((w) => norm(w.w)));
		const words: Word[] = mergeFragments(opt.words).map((w) => ({w: w.w, start: w.start, end: w.end, hl: colored.has(norm(w.w)), hide: false, cut: false}));
		const next = {...c, source: opt.source, in: opt.in, out: opt.out, choice, words, emojis: []};
		return {...next, signature: signature(next)};
	});

/** Deplace le debut ou la fin d'un plan ; les mots viennent de la transcription complete de la prise. */
export const trim = (reel: ReelDoc, id: string, side: 'in' | 'out', delta: number, transcript: RawWord[] | undefined): ReelDoc =>
	mapClip(transcript ? dropSuggestions(reel, id) : reel, id, (c) => {
		const dur = reel.sources[c.source]?.duration ?? c.out + 5;
		let a = c.in;
		let b = c.out;
		if (side === 'in') a = Math.min(Math.max(0, +(c.in + delta).toFixed(3)), b - 0.2);
		else b = Math.max(Math.min(dur, +(c.out + delta).toFixed(3)), a + 0.2);
		let words = c.words;
		if (transcript) {
			const old = new Map(c.words.map((w) => [Math.round(w.start * 50), w]));
			words = mergeFragments(transcript)
				.filter((w) => w.end > a + 0.02 && w.start < b - 0.02)
				.map((w) => {
					const o = old.get(Math.round(w.start * 50));
					return o ? {...o, start: w.start, end: w.end} : {w: w.w, start: w.start, end: w.end, hl: false, hide: false, cut: false};
				});
		}
		const next = {...c, in: a, out: b, words};
		return {...next, signature: signature(next)};
	});

export const moveClip = (reel: ReelDoc, from: number, to: number): ReelDoc => {
	const clips = [...reel.clips];
	const [c] = clips.splice(from, 1);
	clips.splice(Math.max(0, Math.min(clips.length, to)), 0, c);
	return {...reel, clips};
};

export const setWords = (reel: ReelDoc, id: string, indexes: number[], patch: Partial<Word>): ReelDoc =>
	mapClip(reel, id, (c) => ({...c, words: c.words.map((w, i) => (indexes.includes(i) ? {...w, ...patch} : w))}));

export const clipPatch = (reel: ReelDoc, id: string, patch: Partial<Clip>): ReelDoc => mapClip(reel, id, (c) => ({...c, ...patch}));
