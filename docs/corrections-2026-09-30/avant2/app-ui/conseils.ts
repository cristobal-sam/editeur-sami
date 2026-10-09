// Conseils de rythme : les zones faibles de la bande « Rythme » deviennent des propositions concretes.
// Chaque proposition est une modification du reel que le monteur accepte d'un clic (Ctrl+Z pour revenir).
import {baseSegments, duration, pacing, segLen, timedWords} from '../../remotion/src/timeline';
import type {ReelDoc} from '../../remotion/src/types';

export type Advice = {id: string; label: string; detail: string; apply?: (r: ReelDoc) => ReelDoc; action?: 'broll' | 'graphic'};
export type Zone = {start: number; end: number; score: number; advice: Advice[]};

const WEAK = 0.45; // seconde « molle »
const ZONE_MEAN = 0.4; // une zone faible : au moins 3 s molles d'affilee, en moyenne sous ce niveau
const ZONE_MIN = 3;

/** Zones ou le rythme retombe (au moins 3 s molles d'affilee), hors premiere seconde. */
export const weakZones = (reel: ReelDoc): Zone[] => {
	const pace = pacing(reel);
	const zones: Zone[] = [];
	let cur: {start: number; end: number; sum: number; n: number} | null = null;
	for (const p of pace) {
		if (p.score < WEAK && p.t >= 1) {
			if (!cur) cur = {start: p.t, end: p.t + 1, sum: 0, n: 0};
			cur.end = p.t + 1;
			cur.sum += p.score;
			cur.n++;
		} else if (cur) {
			if (cur.end - cur.start >= ZONE_MIN && cur.sum / cur.n < ZONE_MEAN) zones.push({start: cur.start, end: cur.end, score: cur.sum / cur.n, advice: []});
			cur = null;
		}
	}
	if (cur && cur.end - cur.start >= ZONE_MIN && cur.sum / cur.n < ZONE_MEAN) zones.push({start: cur.start, end: Math.min(cur.end, duration(reel)), score: cur.sum / cur.n, advice: []});
	for (const z of zones) z.advice = adviceFor(reel, z);
	return zones;
};

const adviceFor = (reel: ReelDoc, z: Zone): Advice[] => {
	const out: Advice[] = [];
	const segs = baseSegments(reel).filter((s) => s.out_start < z.end && s.out_start + segLen(s) > z.start);
	const clipIds = [...new Set(segs.map((s) => s.clip))];
	const words = timedWords(reel).filter((w) => w.outStart >= z.start - 0.2 && w.outStart < z.end);
	const key = `${z.start}`;
	// 1. resserrer les pauses des plans concernes
	const loose = reel.clips.filter((c) => clipIds.includes(c.id) && !c.tighten);
	if (loose.length) {
		out.push({id: `${key}-tight`, label: 'Resserrer les pauses', detail: `${loose.length} plan(s) non resserré(s) dans cette zone`,
			apply: (r) => ({...r, clips: r.clips.map((c) => (loose.some((l) => l.id === c.id) ? {...c, tighten: true} : c))})});
	}
	// 2. zoom de relance sur le segment qui commence dans la zone
	const seg = segs.find((s) => s.out_start >= z.start - 0.1) ?? segs[0];
	if (seg && reel.zoom.overrides[String(seg.index)] === undefined) {
		const target = +(Math.max(reel.zoom.strength, 1.1) + 0.06).toFixed(2);
		out.push({id: `${key}-zoom`, label: `Zoom de relance (${Math.round((target - 1) * 100)} %)`, detail: seg.out_start >= z.start - 0.1 ? `sur le plan qui commence à ${seg.out_start.toFixed(1)} s` : `sur le plan en cours (depuis ${seg.out_start.toFixed(1)} s)`,
			apply: (r) => ({...r, zoom: {...r.zoom, overrides: {...r.zoom.overrides, [String(seg.index)]: target}}})});
	}
	// 3. bruitage d'accent au debut de la zone
	const at = +(z.start + 0.3).toFixed(2);
	out.push({id: `${key}-sfx`, label: 'Bruitage d’accent (whoosh)', detail: `à ${at.toFixed(1)} s`,
		apply: (r) => ({...r, sfx: {...(r.sfx ?? {enabled: true, transition: null, highlight: null, highlightGap: 4, cta: null, start: null, volume: 0.6}),
			enabled: true, extra: [...(r.sfx?.extra ?? []), {t: at, name: 'whoosh-court'}]}})});
	// 4. mot cle : aucun mot en couleur dans la zone -> colorer le mot le plus long
	if (!words.some((w) => w.hl)) {
		const best = [...words].sort((a, b) => b.w.length - a.w.length)[0];
		if (best && best.w.length >= 5) {
			out.push({id: `${key}-hl`, label: `Mettre « ${best.w.replace(/[,.!?]/g, '')} » en couleur`, detail: 'donne un point d’accroche au regard',
				apply: (r) => ({...r, clips: r.clips.map((c) => (c.id === best.clip ? {...c, words: c.words.map((w, i) => (i === best.index ? {...w, hl: true} : w))} : c))})});
		}
	}
	// 5. couper la phrase la plus faible (jamais le hook ni l'appel a l'action)
	const lastBlock = reel.clips[reel.clips.length - 1]?.block;
	const protectedBlocks = new Set<string | undefined>([reel.clips[0]?.block, reel.ctaBlock ?? lastBlock]);
	const candidates = clipIds.filter((id) => !protectedBlocks.has(reel.clips.find((c) => c.id === id)?.block));
	if (candidates.length && words.length >= 4) {
		const inZone = words.filter((w) => candidates.includes(w.clip));
		if (inZone.length >= 4) {
			const clip = inZone[0].clip;
			const idx = inZone.filter((w) => w.clip === clip).map((w) => w.index);
			out.push({id: `${key}-cut`, label: 'Couper ce passage', detail: `« ${inZone.filter((w) => w.clip === clip).map((w) => w.w).join(' ').slice(0, 70)}… » (rétablissable dans Texte)`,
				apply: (r) => ({...r, clips: r.clips.map((c) => (c.id === clip ? {...c, words: c.words.map((w, i) => (idx.includes(i) ? {...w, cut: true} : w))} : c))})});
		}
	}
	// 6. plan de coupe et graphisme : ouvrent l'outil correspondant
	out.push({id: `${key}-broll`, label: 'Plan de coupe', detail: 'chercher une image pour relancer', action: 'broll'});
	if (words.some((w) => /\d/.test(w.w))) out.push({id: `${key}-gfx`, label: 'Chiffre animé', detail: 'un nombre est dit dans cette zone', action: 'graphic'});
	return out;
};
