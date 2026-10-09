// Notes timecodees et dessins de revision (facon Frame.io) — FICHIER DE L'AGENT « notes » (docs/direction-creative-v2/SPEC.md).
// Branche par l'architecte :
//  - NotesPanel : onglet « Notes » (ecrire, filtrer, modifier, supprimer ; clic = retour a l'image exacte) ;
//  - AnnotationOverlay : calque PAR-DESSUS le lecteur (crayon, fleche, cercle, surligneur, gomme) ; pointer-events: none
//    hors du mode dessin pour ne pas bloquer les commandes du lecteur ;
//  - NoteMarkers : reperes des notes dans la regle de la timeline (x(s) = position en px d'un instant).
// Donnees : reel.notes / reel.annotations (types.ts). Ancres : anchorAtTime / resolveAnchor (timeline.ts) : une note suit
// son passage quand le montage change ; passage coupe ou prise changee = « passage retire ou modifie » (jamais deplacee en
// silence). Dessins : points en coordonnees de la PRISE (outputToSource / sourceRectAt a l'enregistrement,
// annotationOutput a l'affichage) : alignes en 9:16, 16:9, 4:5 et 1:1. Jamais lus par la composition Remotion : absents
// de l'export (App retire REVIEW_KEYS des props du lecteur).
// CSS : bloc /* revue */ ... /* fin revue */ de styles.css (classes « nt- »).
import React, {useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore} from 'react';
import {anchorAtTime, annotationOutput, baseSegments, duration, outputToSource, resolveAnchor, segLen, segmentAt, sourceRectAt, timedWords} from '../../remotion/src/timeline';
import type {Anchor, Annotation, AnnotationTool, Note, NoteStatut, ReelDoc, Segment, VectorItem} from '../../remotion/src/types';
import type {V2Props} from './v2';

// ---------- Reglages et libelles ----------
export const STATUTS: {id: NoteStatut; nom: string; aide: string}[] = [
	{id: 'ouverte', nom: 'Ouverte', aide: 'À faire'},
	{id: 'traitee', nom: 'Traitée', aide: 'Corrigée, à revoir'},
	{id: 'resolue', nom: 'Résolue', aide: 'Validée, terminée'},
];
export const OUTILS: {id: AnnotationTool; nom: string; icone: string; epaisseur: number}[] = [
	{id: 'crayon', nom: 'Crayon', icone: '✏️', epaisseur: 8},
	{id: 'fleche', nom: 'Flèche', icone: '➜', epaisseur: 10},
	{id: 'cercle', nom: 'Cercle', icone: '◯', epaisseur: 8},
	{id: 'surligneur', nom: 'Surligneur', icone: '🖍', epaisseur: 36},
];
export const COULEURS = ['#FF3B30', '#FFD400', '#34C759', '#0A84FF', '#FFFFFF', '#111111'];
/** Duree d'affichage d'un nouveau dessin (s). */
export const DUREE_DESSIN = 2;
const DUREES = [0.5, 1, 2, 3, 5, 10];
/** Memes regles que le serveur (validateV2) : un champ refuse bloquerait TOUTE la sauvegarde. */
const SAFE_ID = /^[A-Za-z0-9_:.-]{1,120}$/;
const HEX = /^#[0-9a-f]{6}([0-9a-f]{2})?$/i;
const MAX_POINTS = 2000;
const MAX_TEXTE = 2000;
/** Plafonds du serveur (validateV2) : au-dela, il refuserait TOUTE la sauvegarde (montage compris). */
const MAX_NOTES = 500;
const MAX_DESSINS = 500;
const MAX_POINTS_TOTAL = 200000;
const MAX_VECTEURS = 200;
/** Dessin de plus refuse par le serveur ? -> phrase pour le monteur, sinon ''. */
export const dessinRefuse = (list: Annotation[], points: number) => {
	if (list.length >= MAX_DESSINS) return `Limite : ${MAX_DESSINS} dessins par vidéo. Supprimes-en pour continuer.`;
	if (list.reduce((n, a) => n + a.points.length, points) > MAX_POINTS_TOTAL) return 'Limite : trop de traits dans cette vidéo. Supprime des dessins pour continuer.';
	return '';
};

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const round5 = (v: number) => Math.round(v * 1e5) / 1e5;
/** Identifiant unique (lettres, chiffres, tirets : accepte par le serveur), jamais deja pris dans `pris`. */
export const nouvelId = (p: string, pris: {id: string}[] = []) => {
	for (;;) {
		const id = `${p}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
		if (!pris.some((x) => x.id === id)) return id;
	}
};

// ---------- Temps : image exacte, timecode mm:ss:ii ----------
export const frameOf = (t: number, fps: number) => Math.max(0, Math.round(t * fps));
const snap = (t: number, fps: number) => frameOf(t, fps) / fps;
/** Timecode « minutes:secondes:images » (00:12:15 = 12 s et 15 images). */
export const timecode = (t: number, fps: number) => {
	const f = frameOf(t, fps);
	const s = Math.floor((f + 1e-6) / fps);
	const p = (n: number) => String(n).padStart(2, '0');
	return `${p(Math.floor(s / 60))}:${p(s % 60)}:${p(f - Math.round(s * fps))}`;
};

// ---------- Ancres ----------
/** Ancre acceptee par le serveur : plan et prises en identifiants simples (sinon champ facultatif retire). */
const ancreSure = (a: Anchor | null): Anchor | null => {
	if (!a || !SAFE_ID.test(a.clip) || typeof a.sig !== 'string' || a.sig.length > 400 || !(a.src >= 0 && a.src <= 86400)) return null;
	const out: Anchor = {clip: a.clip, src: a.src, sig: a.sig};
	if (a.source && SAFE_ID.test(a.source)) out.source = a.source;
	if (a.image && SAFE_ID.test(a.image)) out.image = a.image;
	return out;
};
const priseDe = (a: Anchor) => a.source ?? a.sig.split('|')[0];
/** Le temps t du montage montre-t-il encore le moment de l'ancre (meme plan, meme prise, meme image) ? */
const memeMoment = (reel: ReelDoc, segs: Segment[], t: number, a: Anchor) => {
	if (!(t >= 0) || !segs.length) return false;
	const s = segs[segmentAt(segs, t)];
	const clip = reel.clips.find((c) => c.id === s.clip);
	if (!clip || s.clip !== a.clip || clip.source !== priseDe(a)) return false;
	const speed = s.speed ?? 1;
	const src = s.src_in + Math.min(Math.max(0, t - s.out_start), segLen(s)) * speed;
	return Math.abs(src - a.src) <= (0.5 / reel.fps) * speed + 1e-4;
};

export type Place = {t: number; exact: boolean; end: number | null};
/** Ou tombe la note dans le montage actuel, a l'image pres ; null = passage coupe ou prise changee (note « orpheline »).
 * Le temps enregistre (cache) n'est garde que s'il montre encore le meme instant de la meme prise : sinon l'ancre fait
 * foi (resolveAnchor). exact = false : meme moment de la meme prise retrouve dans un autre plan. */
export const placeNote = (reel: ReelDoc, n: Note, segs: Segment[] = baseSegments(reel)): Place | null => {
	let t: number;
	let exact = true;
	if (memeMoment(reel, segs, n.t, n.anchor)) t = snap(n.t, reel.fps);
	else {
		const p = resolveAnchor(reel, n.anchor, segs);
		if (!p) return null;
		t = snap(p.t, reel.fps);
		exact = p.exact;
	}
	let end: number | null = null;
	if (n.endAnchor) {
		const e = n.end !== undefined && memeMoment(reel, segs, n.end, n.endAnchor) ? {t: n.end} : resolveAnchor(reel, n.endAnchor, segs);
		if (e && e.t > t) end = snap(e.t, reel.fps);
	}
	return {t, exact, end};
};

/** Quelques mots dits a l'instant t (souvenir du passage, affiche si la note devient orpheline). */
export const phraseAt = (reel: ReelDoc, t: number) => {
	const words = timedWords(reel);
	if (!words.length) return '';
	let i = words.findIndex((w) => w.outEnd > t);
	if (i < 0) i = words.length - 1;
	return words.slice(Math.max(0, i - 3), i + 5).map((w) => w.w).join(' ').slice(0, 200);
};

/** Nouvelle note a l'image de t (auteur, date, contexte du montage a cet instant). null : montage vide. */
export const newNote = (reel: ReelDoc, t: number, text: string, auteur: string, format: string, now = new Date()): Note | null => {
	const tf = snap(t, reel.fps);
	const anchor = ancreSure(anchorAtTime(reel, tf));
	if (!anchor) return null;
	const iso = now.toISOString();
	const phrase = phraseAt(reel, tf);
	return {id: nouvelId('n', reel.notes), t: tf, anchor, text: text.slice(0, MAX_TEXTE), statut: 'ouverte', auteur: (auteur.trim() || 'Sami').slice(0, 80),
		cree: iso, modifie: iso,
		contexte: {titre: String(reel.title ?? '').slice(0, 300), style: String(reel.template ?? '').slice(0, 80), format: format.slice(0, 20), duree: +duration(reel).toFixed(2),
			...(phrase ? {phrase} : {})}};
};

/** Souvenir du passage d'une note : contexte.phrase (V2), ou meta.phrase (notes ecrites avant que le champ soit stable). */
export const phraseDe = (n: Note) => (typeof n.contexte?.phrase === 'string' ? n.contexte.phrase : typeof n.meta?.phrase === 'string' ? n.meta.phrase : '');

/** Temps en cache des notes remis a jour (notes orphelines : inchange). */
export const refreshTimes = (reel: ReelDoc, notes: Note[]) => {
	const segs = baseSegments(reel);
	return notes.map((n) => {
		const p = placeNote(reel, n, segs);
		if (!p) return n;
		const next: Note = {...n, t: p.t};
		if (p.end !== null) next.end = p.end;
		return p.t === n.t && (p.end === null || p.end === n.end) ? n : next;
	});
};

// ---------- Dessins ----------
/** Points prets pour le serveur : bornes [-2, 3], 5 decimales, 2000 points au plus. */
export const cleanPoints = (pts: [number, number][]): [number, number][] => {
	const out = pts.filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1])).map(([x, y]) => [round5(clamp(x, -2, 3)), round5(clamp(y, -2, 3))] as [number, number]);
	const n = out.length;
	// trait tres long : 2000 points repartis regulierement (le premier et le dernier gardes)
	return n <= MAX_POINTS ? out : Array.from({length: MAX_POINTS}, (_, i) => out[Math.round((i * (n - 1)) / (MAX_POINTS - 1))]);
};

export type Trait = {outil: AnnotationTool; couleur: string; epaisseur: number; duree: number; noteId?: string | null};
/** Dessin fait a l'image de t : points de l'ecran (0..1 de l'image affichee) convertis en points de la PRISE. */
export const newAnnotation = (reel: ReelDoc, t: number, o: Trait, ecran: [number, number][]): Annotation | null => {
	const tf = snap(t, reel.fps);
	const rect = sourceRectAt(reel, tf);
	const anchor = ancreSure(anchorAtTime(reel, tf));
	const points = rect ? cleanPoints(ecran.map((p) => outputToSource(rect, p))) : [];
	if (!rect || !anchor || !points.length) return null;
	const a: Annotation = {id: nouvelId('d', reel.annotations), outil: o.outil, couleur: HEX.test(o.couleur) ? o.couleur : COULEURS[0],
		epaisseur: +clamp(o.epaisseur, 0.5, 200).toFixed(1), points, anchor, duree: +clamp(o.duree, 0.04, 600).toFixed(2)};
	if (o.noteId && SAFE_ID.test(o.noteId)) a.noteId = o.noteId;
	return a;
};

/** Instants d'affichage d'un dessin, a l'image pres ([debut, fin[) ; null si son passage a ete coupe. */
export const annotationSpan = (reel: ReelDoc, a: Annotation, segs: Segment[] = baseSegments(reel)): [number, number] | null => {
	const p = resolveAnchor(reel, a.anchor, segs);
	if (!p) return null;
	const t0 = snap(p.t, reel.fps);
	return [t0, t0 + Math.max(0.04, a.duree)];
};

// ---------- « Transformer en élément graphique » : fleche, cercle, surligneur -> vecteur de la banque (EXPORTE) ----------
/** SVG de la banque (agent vecteurs, assets/banque/vecteurs) et leur geometrie : largeur du viewBox et longueur utile
 * du dessin dans ce viewBox (fleche : queue x=20 -> pointe x=300 ; cercle : diametre 196 ; surligneur : x=22 -> 378).
 * Le crayon a main levee n'a pas d'equivalent : il reste un dessin de revision. */
export const VECTEURS_DESSIN: Partial<Record<AnnotationTool, {asset: string; vb: number; utile: number}>> = {
	fleche: {asset: 'banque/vecteurs/fleche.svg', vb: 320, utile: 280},
	cercle: {asset: 'banque/vecteurs/cercle.svg', vb: 240, utile: 196},
	surligneur: {asset: 'banque/vecteurs/surligneur.svg', vb: 400, utile: 356},
};
/** Vecteur (reel.vectors) qui reproduit le dessin a son image de depart, dans le format actuel : centre, largeur et
 * rotation calcules pour que la fleche aille de la queue a la pointe dessinees, que le cercle ait le meme diametre et
 * le surligneur la meme longueur. Position FIXE dans l'image (comme tout vecteur). null : crayon, passage retire, autre prise. */
export const toVector = (reel: ReelDoc, a: Annotation, anim: {entree: string; sortie: string} = {entree: 'fondu', sortie: 'fondu'}): VectorItem | null => {
	const g = VECTEURS_DESSIN[a.outil];
	const span = annotationSpan(reel, a);
	if (!g || !span) return null;
	const pts = annotationOutput(reel, a, span[0]);
	if (!pts?.length) return null;
	const W = reel.width;
	const H = reel.height;
	const P = pts.map(([x, y]) => [x * W, y * H]);
	const [p0, p1] = [P[0], P[P.length - 1]];
	let centre = [(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2];
	let taille = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]);
	let rotation = (Math.atan2(p1[1] - p0[1], p1[0] - p0[0]) * 180) / Math.PI;
	if (a.outil === 'cercle') {
		taille = (Math.abs(p1[0] - p0[0]) + Math.abs(p1[1] - p0[1])) / 2;
		rotation = 0;
	}
	if (taille < 4) return null;
	const principale = a.couleur.slice(0, 7).toUpperCase();
	return {id: nouvelId('v', reel.vectors), asset: g.asset, at: +span[0].toFixed(3), duration: +clamp(a.duree, 0.04, 600).toFixed(2),
		// w : part du petit cote de l'image (regle des vecteurs, vectors.tsx)
		x: +clamp(centre[0] / W, -1, 2).toFixed(4), y: +clamp(centre[1] / H, -1, 2).toFixed(4), w: +clamp((taille * g.vb) / g.utile / Math.min(W, H), 0.01, 4).toFixed(4),
		rotation: +clamp(rotation, -360, 360).toFixed(2), opacite: 1, couleurs: {principale, secondaire: null, contour: null}, couleursManuelles: true,
		anim: {entree: String(anim.entree).slice(0, 40), sortie: String(anim.sortie).slice(0, 40)}, manual: true,
		raison: 'Dessin de révision transformé en élément graphique par le monteur.'};
};

export type Visible = {a: Annotation; pts: [number, number][]};
/** Dessins visibles a l'instant t (points de l'image 0..1) ; ni masques, ni sur une autre prise que la leur. */
export const visibleDrawings = (reel: ReelDoc, list: Annotation[], spans: Map<string, [number, number] | null>, t: number): Visible[] => {
	const f = frameOf(t, reel.fps);
	const out: Visible[] = [];
	for (const a of list) {
		const w = spans.get(a.id);
		if (!w || a.masquee || f < frameOf(w[0], reel.fps) || f >= frameOf(w[1], reel.fps)) continue;
		const pts = annotationOutput(reel, a, t);
		if (pts) out.push({a, pts});
	}
	return out;
};

// ---------- Etat partage (panneau, calque du lecteur, timeline) : reglages memorises sur cet ordinateur ----------
type Filtre = 'toutes' | NoteStatut;
type Etat = {cle: string; dessin: boolean; outil: AnnotationTool | 'gomme'; couleur: string; epaisseurs: Record<AnnotationTool, number>; duree: number;
	noteId: string | null; filtre: Filtre; visibles: boolean; auteur: string; pile: string[]; focus: string | null};
const PREFS = 'editeur-sami.revue';
const defaut: Etat = {cle: '', dessin: false, outil: 'crayon', couleur: COULEURS[0], duree: DUREE_DESSIN, noteId: null, filtre: 'toutes', visibles: true,
	auteur: 'Sami', pile: [], focus: null, epaisseurs: Object.fromEntries(OUTILS.map((o) => [o.id, o.epaisseur])) as Record<AnnotationTool, number>};
const lirePrefs = (): Etat => {
	const e = {...defaut, epaisseurs: {...defaut.epaisseurs}};
	try {
		const p = JSON.parse(localStorage.getItem(PREFS) || '{}');
		if ([...OUTILS.map((o) => o.id), 'gomme'].includes(p.outil)) e.outil = p.outil;
		if (typeof p.couleur === 'string' && HEX.test(p.couleur)) e.couleur = p.couleur;
		if (DUREES.includes(p.duree)) e.duree = p.duree;
		if (['toutes', ...STATUTS.map((s) => s.id)].includes(p.filtre)) e.filtre = p.filtre;
		if (typeof p.visibles === 'boolean') e.visibles = p.visibles;
		if (typeof p.auteur === 'string' && p.auteur.trim()) e.auteur = p.auteur.slice(0, 80);
		for (const o of OUTILS) if (typeof p.epaisseurs?.[o.id] === 'number') e.epaisseurs[o.id] = clamp(p.epaisseurs[o.id], 1, 80);
	} catch {}
	return e;
};
let etat: Etat = typeof window === 'undefined' ? defaut : lirePrefs();
const abonnes = new Set<() => void>();
const abonner = (f: () => void) => {
	abonnes.add(f);
	return () => {
		abonnes.delete(f);
	};
};
const changer = (p: Partial<Etat>) => {
	etat = {...etat, ...p};
	try {
		const {outil, couleur, duree, filtre, visibles, auteur, epaisseurs} = etat;
		localStorage.setItem(PREFS, JSON.stringify({outil, couleur, duree, filtre, visibles, auteur, epaisseurs}));
	} catch {}
	abonnes.forEach((f) => f());
};
const useEtat = () => useSyncExternalStore(abonner, () => etat, () => etat);
/** Autre video : on sort du mode dessin (un dessin ne passe jamais d'une video a l'autre). */
const useVideo = (reel: ReelDoc) => {
	const cle = `${reel.project}/${reel.id}`;
	useEffect(() => {
		if (etat.cle !== cle) changer({cle, dessin: false, noteId: null, pile: [], focus: null});
	}, [cle]);
};

/** Le serveur enregistre-t-il les notes ? (un serveur d'avant la V2 les ignorerait : elles seraient perdues). */
let sonde: Promise<boolean> | null = null;
const useServeurV2 = () => {
	const [ok, setOk] = useState(true);
	useEffect(() => {
		let on = true;
		sonde ??= fetch('/api/v2').then((r) => r.status !== 404).catch(() => true);
		sonde.then((v) => on && setOk(v));
		return () => {
			on = false;
		};
	}, []);
	return ok;
};

const nomStatut = (s: NoteStatut) => STATUTS.find((x) => x.id === s)?.nom ?? s;
const date = (iso: string) => {
	const d = new Date(iso);
	return Number.isNaN(d.getTime()) ? '' : d.toLocaleString('fr-CA', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
};
const court = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

// ---------- Rendu d'un dessin (SVG, unites = pixels de l'image du montage) ----------
const lisse = (P: number[][]) => {
	const f = (v: number) => v.toFixed(1);
	if (P.length < 3) return `M ${P.map((p) => `${f(p[0])} ${f(p[1])}`).join(' L ')}`;
	let d = `M ${f(P[0][0])} ${f(P[0][1])}`;
	for (let i = 1; i < P.length - 1; i++) d += ` Q ${f(P[i][0])} ${f(P[i][1])} ${f((P[i][0] + P[i + 1][0]) / 2)} ${f((P[i][1] + P[i + 1][1]) / 2)}`;
	const l = P[P.length - 1];
	return `${d} L ${f(l[0])} ${f(l[1])}`;
};
const pointe = (p0: number[], p1: number[], sw: number, unit: number) => {
	const dx = p1[0] - p0[0];
	const dy = p1[1] - p0[1];
	const len = Math.hypot(dx, dy) || 1;
	const L = Math.min(Math.max(sw * 3.2, 22 * unit), len * 0.6);
	const [ux, uy] = [dx / len, dy / len];
	const base = [p1[0] - ux * L, p1[1] - uy * L];
	const hw = L * 0.55;
	return {base, d: `M ${p1[0]} ${p1[1]} L ${base[0] - uy * hw} ${base[1] + ux * hw} L ${base[0] + uy * hw} ${base[1] - ux * hw} Z`};
};
const Forme: React.FC<{outil: AnnotationTool; couleur: string; epaisseur: number; pts: [number, number][]; W: number; H: number}> = ({outil, couleur, epaisseur, pts, W, H}) => {
	const unit = Math.min(W, H) / 1080;
	const sw = Math.max(0.5, epaisseur * unit);
	const P = pts.map(([x, y]) => [x * W, y * H]);
	if (!P.length) return null;
	const [p0, p1 = P[0]] = P;
	if (outil === 'cercle') {
		return <ellipse className="nt-trait" cx={(p0[0] + p1[0]) / 2} cy={(p0[1] + p1[1]) / 2} rx={Math.abs(p1[0] - p0[0]) / 2} ry={Math.abs(p1[1] - p0[1]) / 2}
			fill="none" stroke={couleur} strokeWidth={sw} />;
	}
	if (outil === 'fleche') {
		const {base, d} = pointe(p0, p1, sw, unit);
		return (
			<g className="nt-trait">
				<line x1={p0[0]} y1={p0[1]} x2={base[0]} y2={base[1]} stroke={couleur} strokeWidth={sw} strokeLinecap="round" />
				<path d={d} fill={couleur} stroke={couleur} strokeWidth={sw * 0.4} strokeLinejoin="round" />
			</g>
		);
	}
	const surligne = outil === 'surligneur';
	if (P.length === 1) return <circle className={surligne ? 'nt-surligne' : 'nt-trait'} cx={p0[0]} cy={p0[1]} r={sw / 2} fill={couleur} opacity={surligne ? 0.45 : 1} />;
	return <path className={surligne ? 'nt-surligne' : 'nt-trait'} d={lisse(P)} fill="none" stroke={couleur} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round"
		strokeOpacity={surligne ? 0.45 : 1} />;
};

/** Distance (px de l'image) entre un point et un dessin : pour la gomme. */
const distance = (v: Visible, q: number[], W: number, H: number) => {
	let P = v.pts.map(([x, y]) => [x * W, y * H]);
	if (v.a.outil === 'cercle' && P.length) {
		const [p0, p1 = P[0]] = P;
		const [cx, cy, rx, ry] = [(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, Math.abs(p1[0] - p0[0]) / 2, Math.abs(p1[1] - p0[1]) / 2];
		P = Array.from({length: 49}, (_, i) => [cx + rx * Math.cos((i / 48) * 2 * Math.PI), cy + ry * Math.sin((i / 48) * 2 * Math.PI)]);
	}
	if (P.length === 1) return Math.hypot(q[0] - P[0][0], q[1] - P[0][1]);
	let best = Infinity;
	for (let i = 1; i < P.length; i++) {
		const [a, b] = [P[i - 1], P[i]];
		const [dx, dy] = [b[0] - a[0], b[1] - a[1]];
		const k = clamp(((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / (dx * dx + dy * dy || 1), 0, 1);
		best = Math.min(best, Math.hypot(q[0] - a[0] - k * dx, q[1] - a[1] - k * dy));
	}
	return best;
};

/** Note a cette image exacte (pour y joindre les dessins). */
const noteIci = (reel: ReelDoc, segs: Segment[], t: number) => {
	const f = frameOf(t, reel.fps);
	return (reel.notes ?? []).find((n) => {
		const p = placeNote(reel, n, segs);
		return p && frameOf(p.t, reel.fps) === f;
	}) ?? null;
};

// ---------- Calque du lecteur : dessins visibles + mode dessin ----------
export const AnnotationOverlay: React.FC<V2Props> = ({reel, t, update, pause}) => {
	const e = useEtat();
	useVideo(reel);
	const box = useRef<HTMLDivElement>(null);
	const surface = useRef<HTMLDivElement>(null);
	const [taille, setTaille] = useState<[number, number]>([0, 0]);
	useLayoutEffect(() => {
		const el = box.current;
		if (!el) return;
		const mesure = () => setTaille([el.clientWidth, el.clientHeight]);
		mesure();
		const ro = new ResizeObserver(mesure);
		ro.observe(el);
		return () => ro.disconnect();
	}, []);
	// le lecteur garde les proportions de l'image : on se cale exactement sur elle (bandes noires eventuelles exclues)
	const W = reel.width;
	const H = reel.height;
	const k = taille[0] && taille[1] ? Math.min(taille[0] / W, taille[1] / H) : 0;
	const vue = {left: (taille[0] - W * k) / 2, top: (taille[1] - H * k) / 2, width: W * k, height: H * k};
	const segs = useMemo(() => baseSegments(reel), [reel]);
	const list = reel.annotations ?? [];
	const spans = useMemo(() => new Map(list.map((a) => [a.id, annotationSpan(reel, a, segs)])), [reel, segs]);
	const visibles = e.visibles || e.dessin ? visibleDrawings(reel, list, spans, t) : [];
	const bulles = useMemo(() => (reel.notes ?? []).map((n) => ({n, p: placeNote(reel, n, segs)})), [reel, segs]);
	const f = frameOf(t, reel.fps);
	const ici = e.visibles && !e.dessin ? bulles.filter(({n, p}) => p && n.statut !== 'resolue' && f >= frameOf(p.t, reel.fps)
		&& f < frameOf(Math.max(p.end ?? 0, p.t + 2), reel.fps)).slice(0, 2) : [];
	const lien = e.noteId && (reel.notes ?? []).some((n) => n.id === e.noteId) ? (reel.notes ?? []).find((n) => n.id === e.noteId)! : noteIci(reel, segs, t);

	// trait en cours (points de l'ecran 0..1) ; gomme : dessins touches
	const trait = useRef<[number, number][] | null>(null);
	const gomme = useRef(new Set<string>());
	const [, redessiner] = useState(0);
	const [refus, setRefus] = useState('');
	const pos = (ev: React.PointerEvent): [number, number] => {
		const r = surface.current!.getBoundingClientRect();
		return [(ev.clientX - r.left) / r.width, (ev.clientY - r.top) / r.height];
	};
	const gommer = (p: [number, number]) => {
		for (const v of visibles) if (distance(v, [p[0] * W, p[1] * H], W, H) <= (v.a.epaisseur * Math.min(W, H)) / 2160 + 10 / (k || 1)) gomme.current.add(v.a.id);
	};
	const down = (ev: React.PointerEvent) => {
		if (ev.button !== 0) return;
		ev.preventDefault();
		pause();
		try {
			(ev.target as HTMLElement).setPointerCapture(ev.pointerId);
		} catch {}
		const p = pos(ev);
		trait.current = [p];
		gomme.current = new Set();
		if (e.outil === 'gomme') gommer(p);
		redessiner((n) => n + 1);
	};
	const move = (ev: React.PointerEvent) => {
		const pts = trait.current;
		if (!pts) return;
		const p = pos(ev);
		if (e.outil === 'gomme') gommer(p);
		else if (e.outil === 'fleche' || e.outil === 'cercle') trait.current = [pts[0], p];
		else {
			const l = pts[pts.length - 1];
			if (Math.hypot((p[0] - l[0]) * vue.width, (p[1] - l[1]) * vue.height) < 2) return;
			pts.push(p);
		}
		redessiner((n) => n + 1);
	};
	const up = () => {
		const pts = trait.current;
		trait.current = null;
		redessiner((n) => n + 1);
		if (!pts) return;
		if (e.outil === 'gomme') {
			const ids = gomme.current;
			if (ids.size) {
				setRefus('');
				update((r) => ({...r, annotations: (r.annotations ?? []).filter((a) => !ids.has(a.id))}));
			}
			return;
		}
		const outil = e.outil;
		// fleche ou cercle trop petits : un simple clic ne dessine rien
		if ((outil === 'fleche' || outil === 'cercle') && (pts.length < 2 || Math.hypot((pts[1][0] - pts[0][0]) * vue.width, (pts[1][1] - pts[0][1]) * vue.height) < 6)) return;
		const a = newAnnotation(reel, t, {outil, couleur: e.couleur, epaisseur: e.epaisseurs[outil], duree: e.duree, noteId: lien?.id}, pts);
		if (!a) return;
		const non = dessinRefuse(list, a.points.length);
		setRefus(non);
		if (non) return;
		update((r) => ({...r, annotations: [...(r.annotations ?? []).filter((x) => x.id !== a.id), a]}));
		changer({pile: [...etat.pile, a.id]});
	};
	const annulerTrait = () => {
		const ids = new Set(list.map((a) => a.id));
		const pile = etat.pile.filter((id) => ids.has(id));
		const id = pile.pop();
		changer({pile});
		if (id) update((r) => ({...r, annotations: (r.annotations ?? []).filter((a) => a.id !== id)}));
	};
	const effacerImage = () => {
		const ids = new Set(visibles.map((v) => v.a.id));
		if (ids.size) update((r) => ({...r, annotations: (r.annotations ?? []).filter((a) => !ids.has(a.id))}));
	};
	useEffect(() => {
		if (!e.dessin) return;
		const key = (ev: KeyboardEvent) => ev.key === 'Escape' && changer({dessin: false, noteId: null});
		window.addEventListener('keydown', key);
		return () => window.removeEventListener('keydown', key);
	}, [e.dessin]);

	const enCours = trait.current && e.outil !== 'gomme' ? trait.current : null;
	const outilTrait = e.outil === 'gomme' ? 'crayon' : e.outil;
	const pile = e.pile.filter((id) => list.some((a) => a.id === id));
	return (
		<div className={`nt-overlay${e.dessin ? ' on' : ''}`} ref={box}>
			{k ? (
				<svg className="nt-svg" style={vue} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
					{visibles.map((v) => (
						<g key={v.a.id} opacity={gomme.current.has(v.a.id) && trait.current ? 0.25 : 1}>
							<Forme outil={v.a.outil} couleur={v.a.couleur} epaisseur={v.a.epaisseur} pts={v.pts} W={W} H={H} />
						</g>
					))}
					{enCours ? <Forme outil={outilTrait} couleur={e.couleur} epaisseur={e.epaisseurs[outilTrait]} pts={enCours} W={W} H={H} /> : null}
				</svg>
			) : null}
			{ici.length ? (
				<div className="nt-bulles">
					{ici.map(({n}) => <div key={n.id} className={`nt-bulle s-${n.statut}`}><b>💬 {n.auteur}</b> {court(n.text, 140)}</div>)}
				</div>
			) : null}
			{e.dessin ? (
				<>
					<div ref={surface} className={`nt-surface${e.outil === 'gomme' ? ' gomme' : ''}`} style={vue}
						onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} />
					<div className="nt-tools" onPointerDown={(ev) => ev.stopPropagation()}>
						{OUTILS.map((o) => (
							<button key={o.id} className={`small${e.outil === o.id ? ' primary' : ''}`} title={o.nom} onClick={() => changer({outil: o.id})}>{o.icone}</button>
						))}
						<button className={`small${e.outil === 'gomme' ? ' primary' : ''}`} title="Gomme : passe sur un dessin pour l'effacer" onClick={() => changer({outil: 'gomme'})}>🧽</button>
						<span className="nt-sep" />
						{COULEURS.map((c) => (
							<button key={c} className={`nt-coul${e.couleur.toUpperCase() === c ? ' on' : ''}`} style={{background: c}} title="Couleur" onClick={() => changer({couleur: c})} />
						))}
						<input type="color" value={e.couleur.slice(0, 7)} title="Autre couleur" onChange={(ev) => changer({couleur: ev.target.value.toUpperCase()})} />
						{e.outil !== 'gomme' ? (
							<label className="nt-ep" title={`Épaisseur : ${e.epaisseurs[e.outil]} px`}>
								<input type="range" min={2} max={e.outil === 'surligneur' ? 80 : 40} value={e.epaisseurs[e.outil]}
									onChange={(ev) => changer({epaisseurs: {...etat.epaisseurs, [outilTrait]: Number(ev.target.value)}})} />
							</label>
						) : null}
						<span className="nt-sep" />
						<button className="small" disabled={!pile.length} title="Annuler le dernier trait" onClick={annulerTrait}>↶</button>
						<button className="small" disabled={!visibles.length} title="Effacer les dessins de cette image" onClick={effacerImage}>🗑</button>
						<button className="small primary" title="Terminer (Échap)" onClick={() => changer({dessin: false, noteId: null})}>✓ Terminé</button>
					</div>
					<div className="nt-aide">
						{refus ? `⚠ ${refus}` : <>
							{timecode(t, reel.fps)} · visible {String(e.duree).replace('.', ',')} s{lien ? ` · joint à la note « ${court(lien.text, 40)} »` : ' · sans note (elle sera jointe à la note écrite ici)'}
						</>}
					</div>
				</>
			) : (
				<button className="small nt-quick" title="Dessiner sur l'image (révision : jamais dans l'export)" onClick={() => { pause(); changer({dessin: true, noteId: null}); }}>✏️</button>
			)}
		</div>
	);
};

// ---------- Panneau des notes ----------
type Actions = {
	seek: (n: Note, p: Place) => void; statut: (id: string, s: NoteStatut) => void; texte: (id: string, text: string) => void;
	supprimer: (id: string) => void; dessiner: (n: Note, p: Place) => void; rattacher: (id: string) => void; fin: (id: string, on: boolean) => void;
};
/** Carte d'une note. Memoisee (la tete de lecture bouge 30 fois par seconde) : proprietes simples seulement, et les
 * actions sont lues AU CLIC dans actions.current (jamais une version perimee : temps, montage). */
const NoteCard: React.FC<{n: Note; p: Place | null; fps: number; now: boolean; focus: boolean; dessins: number; ici: string;
	style: string; format: string; duree: number; actions: React.MutableRefObject<Actions>}> = React.memo(({n, p, fps, now, focus, dessins, ici, style, format, duree, actions}) => {
	const [edit, setEdit] = useState<string | null>(null);
	const card = useRef<HTMLDivElement>(null);
	useEffect(() => {
		if (focus) card.current?.scrollIntoView({block: 'nearest', behavior: 'smooth'});
	}, [focus]);
	const a = {
		seek: (x: Note, y: Place) => actions.current.seek(x, y), statut: (id: string, s: NoteStatut) => actions.current.statut(id, s),
		texte: (id: string, s: string) => actions.current.texte(id, s), supprimer: (id: string) => actions.current.supprimer(id),
		dessiner: (x: Note, y: Place) => actions.current.dessiner(x, y), rattacher: (id: string) => actions.current.rattacher(id),
		fin: (id: string, on: boolean) => actions.current.fin(id, on),
	};
	const phrase = phraseDe(n);
	const change: string[] = [];
	if (n.contexte.format && n.contexte.format !== format) change.push(`écrite en ${n.contexte.format}`);
	if (n.contexte.style && n.contexte.style !== style) change.push(`style ${n.contexte.style}`);
	if (Math.abs(n.contexte.duree - duree) > 0.05) change.push(`montage de ${n.contexte.duree.toFixed(1).replace('.', ',')} s (maintenant ${duree.toFixed(1).replace('.', ',')} s)`);
	return (
		<div ref={card} className={`card nt-card s-${n.statut}${now ? ' now' : ''}${focus ? ' focus' : ''}${p ? '' : ' orpheline'}`}>
			<div className="nt-head">
				{p ? (
					<button className="small nt-tc" title="Revenir à cette image" onClick={() => a.seek(n, p)}>
						▶ {timecode(p.t, fps)}{p.end !== null ? ` → ${timecode(p.end, fps)}` : ''}
					</button>
				) : <span className="nt-tc off" title="Temps de la note quand elle a été écrite">{timecode(n.t, fps)}</span>}
				<span className="nt-statuts">
					{STATUTS.map((s) => (
						<button key={s.id} className={`small${n.statut === s.id ? ' on' : ''}`} title={s.aide} onClick={() => a.statut(n.id, s.id)}>{s.nom}</button>
					))}
				</span>
			</div>
			{!p ? (
				<div className="nt-orph">
					⚠ Passage retiré ou modifié : la note n’est plus rattachée à une image du montage.
					<button className="small" onClick={() => a.rattacher(n.id)} title="Rattacher la note à l'image de la tête de lecture">Rattacher ici ({ici})</button>
				</div>
			) : !p.exact ? <div className="muted">Retrouvée dans un autre plan (même moment de la même prise).</div> : null}
			{edit !== null ? (
				<>
					<textarea className="nt-text" rows={3} maxLength={MAX_TEXTE} value={edit} autoFocus onChange={(ev) => setEdit(ev.target.value)}
						onKeyDown={(ev) => {
							if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey) && edit.trim()) (a.texte(n.id, edit.trim()), setEdit(null));
							if (ev.key === 'Escape') setEdit(null);
						}} />
					<div className="row">
						<button className="small primary" disabled={!edit.trim()} onClick={() => { a.texte(n.id, edit.trim()); setEdit(null); }}>Enregistrer</button>
						<button className="small" onClick={() => setEdit(null)}>Annuler</button>
					</div>
				</>
			) : <div className="nt-body" onDoubleClick={() => setEdit(n.text)}>{n.text}</div>}
			{phrase ? <div className="muted nt-phrase">« {phrase} »</div> : null}
			<div className="muted nt-meta">
				{n.auteur} · {date(n.cree)}{n.modifie !== n.cree ? ` · modifiée ${date(n.modifie)}` : ''}{dessins ? ` · ${dessins} dessin${dessins > 1 ? 's' : ''}` : ''}
				{change.length ? <div>Contexte : {change.join(' · ')}</div> : null}
			</div>
			<div className="row nt-actions">
				{edit === null ? <button className="small" onClick={() => setEdit(n.text)}>Modifier</button> : null}
				{p ? <button className="small" title="Dessiner sur cette image ; les traits sont joints à la note" onClick={() => a.dessiner(n, p)}>✏️ Dessiner</button> : null}
				{p ? <button className="small" title={n.endAnchor ? 'La note ne couvre plus qu’une image' : 'La note couvre le passage jusqu’à la tête de lecture'}
					onClick={() => a.fin(n.id, !n.endAnchor)}>{n.endAnchor ? 'Retirer la fin' : 'Fin ici'}</button> : null}
				<button className="small" title={dessins ? 'Supprimer la note et ses dessins (Ctrl+Z pour annuler)' : 'Supprimer la note (Ctrl+Z pour annuler)'} onClick={() => a.supprimer(n.id)}>Supprimer</button>
			</div>
		</div>
	);
});

export const NotesPanel: React.FC<V2Props> = ({reel, t, format, update, seek, pause}) => {
	const e = useEtat();
	useVideo(reel);
	const serveurOk = useServeurV2();
	const fps = reel.fps;
	const segs = useMemo(() => baseSegments(reel), [reel]);
	const total = useMemo(() => duration(reel), [reel]);
	const notes = reel.notes ?? [];
	const dessins = reel.annotations ?? [];
	const places = useMemo(() => new Map(notes.map((n) => [n.id, placeNote(reel, n, segs)])), [reel, segs]);
	const spans = useMemo(() => new Map(dessins.map((a) => [a.id, annotationSpan(reel, a, segs)])), [reel, segs]);
	const [texte, setTexte] = useState('');
	const [erreur, setErreur] = useState('');
	const f = frameOf(t, fps);
	const ici = timecode(t, fps);
	const orphelinsDessins = dessins.filter((a) => !spans.get(a.id)).length;
	const libresIci = dessins.filter((a) => !a.noteId && spans.get(a.id) && frameOf(spans.get(a.id)![0], fps) === f).length;

	/** Toute modification des notes : temps en cache remis a jour (ancres) ; Ctrl+Z annule. */
	const setNotes = (fn: (list: Note[], r: ReelDoc) => Note[]) => update((r) => ({...r, notes: refreshTimes(r, fn(r.notes ?? [], r))}));
	const maintenant = () => new Date().toISOString();
	const ajouter = () => {
		const txt = texte.trim();
		if (!txt) return;
		pause();
		if (notes.length >= MAX_NOTES) return setErreur(`Limite atteinte : ${MAX_NOTES} notes au plus par vidéo. Supprime des notes résolues pour en ajouter.`);
		const n = newNote(reel, t, txt, e.auteur, format);
		if (!n) return setErreur('Impossible : le montage est vide.');
		setErreur('');
		const fn = frameOf(n.t, fps);
		update((r) => {
			const next: ReelDoc = {...r, notes: refreshTimes(r, [...(r.notes ?? []).filter((x) => x.id !== n.id), n])};
			// dessins de cette image encore sans note : joints a la nouvelle note (dessiner, puis ecrire) ; un dessin dont le
			// passage a ete coupe n'est sur aucune image (jamais joint, meme a une note sur la toute premiere image)
			const s = baseSegments(r);
			const libreIci = (a: Annotation) => {
				const w = !a.noteId && annotationSpan(r, a, s);
				return !!w && frameOf(w[0], fps) === fn;
			};
			if (r.annotations?.some(libreIci)) next.annotations = r.annotations.map((a) => (libreIci(a) ? {...a, noteId: n.id} : a));
			return next;
		});
		setTexte('');
		changer({focus: n.id});
	};
	const actions = useRef<Actions>(null as unknown as Actions);
	actions.current = {
		seek: (n, p) => {
			pause();
			seek(p.t);
			changer({focus: n.id});
		},
		statut: (id, s) => setNotes((list) => list.map((n) => (n.id === id ? {...n, statut: s, modifie: maintenant()} : n))),
		texte: (id, text) => setNotes((list) => list.map((n) => (n.id === id ? {...n, text: text.slice(0, MAX_TEXTE), modifie: maintenant()} : n))),
		supprimer: (id) => update((r) => {
			const next: ReelDoc = {...r, notes: (r.notes ?? []).filter((n) => n.id !== id)};
			if (r.annotations?.some((a) => a.noteId === id)) next.annotations = r.annotations.filter((a) => a.noteId !== id);
			return next;
		}),
		dessiner: (n, p) => {
			pause();
			seek(p.t);
			changer({dessin: true, noteId: n.id, focus: n.id});
		},
		rattacher: (id) => {
			const tf = snap(t, fps);
			const anchor = ancreSure(anchorAtTime(reel, tf));
			if (!anchor) return;
			const img = anchor.image ?? priseDe(anchor);
			update((r) => {
				const s = baseSegments(r);
				const next: ReelDoc = {...r, notes: (r.notes ?? []).map((n) => {
					if (n.id !== id) return n;
					const {end: _e, endAnchor: _a, meta: oldMeta, ...rest} = n;
					// souvenir du passage dans contexte.phrase (l'ancien emplacement meta.phrase est retire)
					const {phrase: _p, ...meta} = (oldMeta ?? {}) as Record<string, unknown>;
					const phrase = phraseAt(r, tf);
					return {...rest, anchor, t: tf, modifie: maintenant(), contexte: {...rest.contexte, ...(phrase ? {phrase} : {})},
						...(Object.keys(meta).length ? {meta} : {})} as Note;
				})};
				// ses dessins orphelins suivent, s'ils ont ete faits sur la meme prise (sinon ils seraient de travers)
				if (r.annotations?.some((a) => a.noteId === id && !annotationSpan(r, a, s))) {
					next.annotations = r.annotations.map((a) => (a.noteId === id && !annotationSpan(r, a, s) && (a.anchor.image ?? priseDe(a.anchor)) === img ? {...a, anchor} : a));
				}
				return next;
			});
			changer({focus: id});
		},
		fin: (id, on) => {
			const tf = snap(t, fps);
			const endAnchor = on ? ancreSure(anchorAtTime(reel, tf)) : null;
			const p = places.get(id);
			if (on && (!endAnchor || !p || frameOf(tf, fps) <= frameOf(p.t, fps))) {
				setErreur('Pour « Fin ici » : place d’abord la tête de lecture APRÈS le début de la note.');
				return;
			}
			setErreur('');
			setNotes((list) => list.map((n) => {
				if (n.id !== id) return n;
				const {end: _e, endAnchor: _a, ...rest} = n;
				return on && endAnchor ? {...rest, end: tf, endAnchor, modifie: maintenant()} : {...rest, modifie: maintenant()};
			}));
		},
	};

	const compte = (s: NoteStatut) => notes.filter((n) => n.statut === s).length;
	const tri = [...notes].sort((a, b) => {
		const [pa, pb] = [places.get(a.id), places.get(b.id)];
		if (!pa !== !pb) return pa ? -1 : 1;
		return (pa?.t ?? a.t) - (pb?.t ?? b.t) || a.cree.localeCompare(b.cree);
	});
	const shown = tri.filter((n) => e.filtre === 'toutes' || n.statut === e.filtre);
	const nomNote = (id?: string) => {
		const n = notes.find((x) => x.id === id);
		const p = n ? places.get(n.id) : null;
		return n ? `${p ? timecode(p.t, fps) : '⚠'} · ${court(n.text, 28)}` : '';
	};
	const setDessin = (id: string, p: Partial<Annotation>) => update((r) => ({...r, annotations: (r.annotations ?? []).map((a) => {
		if (a.id !== id) return a;
		const next = {...a, ...p};
		if (!next.noteId) delete next.noteId;
		if (!next.masquee) delete next.masquee;
		return next;
	})}));
	const triDessins = [...dessins].sort((a, b) => (spans.get(a.id)?.[0] ?? Infinity) - (spans.get(b.id)?.[0] ?? Infinity));
	// « Transformer en élément graphique » : confirmation sur place, puis vecteur de la banque (exporte) a la place du dessin
	const [conv, setConv] = useState<string | null>(null);
	const [msgDessin, setMsgDessin] = useState<{ok: boolean; text: string} | null>(null);
	const transformer = async (a: Annotation) => {
		setConv(null);
		const g = VECTEURS_DESSIN[a.outil];
		if (!g) return;
		if ((reel.vectors?.length ?? 0) >= MAX_VECTEURS) {
			setMsgDessin({ok: false, text: `Limite atteinte : ${MAX_VECTEURS} éléments graphiques (vecteurs) au plus par vidéo.`});
			return;
		}
		let anim = {entree: 'fondu', sortie: 'fondu'};
		try {
			const r = await fetch(`/assets/${g.asset.replace(/\.svg$/, '.json')}`);
			if (!r.ok) throw new Error(String(r.status));
			const fiche = await r.json();
			if (typeof fiche?.anim?.entree === 'string') anim = {entree: fiche.anim.entree, sortie: typeof fiche.anim.sortie === 'string' ? fiche.anim.sortie : 'fondu'};
		} catch {
			setMsgDessin({ok: false, text: 'Impossible pour l’instant : cet élément n’est pas encore dans la banque de vecteurs.'});
			return;
		}
		const v = toVector(reel, a, anim);
		if (!v) {
			setMsgDessin({ok: false, text: 'Ce dessin ne peut pas devenir un élément graphique (passage retiré, autre prise ou dessin trop petit).'});
			return;
		}
		update((r) => {
			const vec = (r.vectors ?? []).some((x) => x.id === v.id) ? {...v, id: nouvelId('v', r.vectors)} : v;
			return {...r, vectors: [...(r.vectors ?? []), vec], annotations: (r.annotations ?? []).filter((x) => x.id !== a.id)};
		});
		setMsgDessin({ok: true, text: 'Transformé en élément graphique : il sera dans la vidéo exportée. Réglages : Plus → Graphismes (Ctrl+Z pour annuler).'});
	};

	return (
		<>
			{!serveurOk ? (
				<div className="card nt-warn">
					⚠ L’éditeur doit être relancé une fois pour enregistrer les notes et les dessins : pour l’instant, ils seraient perdus en fermant la vidéo.
				</div>
			) : null}
			<div className="card">
				<h3>
					<span>Nouvelle note <small>à {ici}</small></span>
					<label className="nt-auteur" title="Nom affiché sur tes notes (mémorisé sur cet ordinateur)">
						<small>Auteur</small>
						<input type="text" maxLength={80} value={e.auteur} onChange={(ev) => changer({auteur: ev.target.value})} onBlur={() => !etat.auteur.trim() && changer({auteur: 'Sami'})} />
					</label>
				</h3>
				<textarea className="nt-text" rows={3} maxLength={MAX_TEXTE} value={texte} placeholder="Ta remarque sur cette image… (ex. : coupe plus tôt, change ce mot, logo trop petit)"
					onFocus={pause} onChange={(ev) => setTexte(ev.target.value)}
					onKeyDown={(ev) => ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey) && (ev.preventDefault(), ajouter())} />
				<div className="row">
					<button className="small primary" disabled={!texte.trim()} onClick={ajouter} title="Ctrl+Entrée">+ Ajouter la note à {ici}</button>
					<button className={`small${e.dessin ? ' on' : ''}`} onClick={() => { pause(); changer({dessin: !e.dessin, noteId: null}); }}
						title="Crayon, flèche, cercle, surligneur sur l'image (jamais dans l'export)">{e.dessin ? '✓ Terminer le dessin' : '✏️ Dessiner sur l’image'}</button>
				</div>
				{libresIci ? <p className="muted">{libresIci} dessin{libresIci > 1 ? 's' : ''} de cette image {libresIci > 1 ? 'seront joints' : 'sera joint'} à la note.</p> : null}
				<p className="muted">Les notes et les dessins servent à la révision : ils ne sont <b>jamais</b> dans la vidéo exportée. Une note reste sur son passage si tu coupes ou déplaces des plans.</p>
			</div>

			{erreur ? <div className="err nt-err">{erreur}</div> : null}
			<div className="row nt-filtres">
				<button className={`small${e.filtre === 'toutes' ? ' primary' : ''}`} onClick={() => changer({filtre: 'toutes'})}>Toutes ({notes.length})</button>
				{STATUTS.map((s) => (
					<button key={s.id} className={`small${e.filtre === s.id ? ' primary' : ''}`} onClick={() => changer({filtre: s.id})}>{s.nom}s ({compte(s.id)})</button>
				))}
				<span className="grow" />
				<button className="small" onClick={() => changer({visibles: !e.visibles})} title="Afficher ou masquer notes et dessins par-dessus l'image (aperçu seulement)">
					{e.visibles ? '👁 Sur l’image' : '🙈 Masqués'}
				</button>
			</div>
			{!notes.length ? <p className="muted">Aucune note pour l’instant. Mets la vidéo en pause sur l’image à corriger, écris ta remarque, puis « Ajouter ».</p> : null}
			{notes.length && !shown.length ? <p className="muted">Aucune note « {e.filtre === 'toutes' ? '' : nomStatut(e.filtre)} ».</p> : null}
			{shown.map((n) => {
				const p = places.get(n.id) ?? null;
				const now = !!p && f >= frameOf(p.t, fps) && f < (p.end !== null ? frameOf(p.end, fps) : frameOf(p.t, fps) + 1);
				// le timecode de la tete de lecture ne sert qu'aux notes orphelines (« Rattacher ici ») : les autres cartes ne
				// se redessinent pas a chaque image
				return <NoteCard key={n.id} n={n} p={p} fps={fps} now={now} focus={e.focus === n.id} dessins={dessins.filter((a) => a.noteId === n.id).length}
					ici={p ? '' : ici} style={String(reel.template ?? '')} format={format} duree={+total.toFixed(2)} actions={actions} />;
			})}

			<div className="card nt-dessins">
				<h3>
					<span>Dessins <small>{dessins.length ? `${dessins.length}` : 'aucun'}{orphelinsDessins ? ` · ${orphelinsDessins} sans passage` : ''}</small></span>
					<label className="nt-auteur" title="Durée d'affichage des prochains dessins">
						<small>Visibles</small>
						<select value={e.duree} onChange={(ev) => changer({duree: Number(ev.target.value)})}>
							{DUREES.map((d) => <option key={d} value={d}>{String(d).replace('.', ',')} s</option>)}
						</select>
					</label>
				</h3>
				{!dessins.length ? <p className="muted">Clique « ✏️ Dessiner sur l’image » (ou le crayon en haut à droite du lecteur), puis trace sur la vidéo. Un dessin reste sur le bon endroit de l’image dans les 4 formats.</p> : null}
				{triDessins.map((a) => {
					const s = spans.get(a.id) ?? null;
					const o = OUTILS.find((x) => x.id === a.outil);
					return (
						<div key={a.id} className={`nt-dessin${s ? '' : ' orpheline'}${s && f >= frameOf(s[0], fps) && f < frameOf(s[1], fps) ? ' now' : ''}`}>
							<span className="nt-pastille" style={{background: a.couleur}} title={o?.nom}>{o?.icone}</span>
							{s ? <button className="small nt-tc" title="Revenir à cette image" onClick={() => { pause(); seek(s[0]); }}>▶ {timecode(s[0], fps)}</button>
								: <span className="nt-tc off" title="Passage retiré ou modifié : le dessin n'est plus affiché">⚠ retiré</span>}
							<select value={a.noteId ?? ''} title="Note jointe" onChange={(ev) => setDessin(a.id, {noteId: ev.target.value || undefined})}>
								<option value="">Sans note</option>
								{tri.map((n) => <option key={n.id} value={n.id}>{nomNote(n.id)}</option>)}
							</select>
							<select value={DUREES.includes(a.duree) ? a.duree : ''} title="Durée d'affichage" onChange={(ev) => setDessin(a.id, {duree: Number(ev.target.value)})}>
								{!DUREES.includes(a.duree) ? <option value="">{String(a.duree).replace('.', ',')} s</option> : null}
								{DUREES.map((d) => <option key={d} value={d}>{String(d).replace('.', ',')} s</option>)}
							</select>
							<button className="small" title={a.masquee ? 'Afficher ce dessin' : 'Masquer ce dessin'} onClick={() => setDessin(a.id, {masquee: !a.masquee})}>{a.masquee ? '🙈' : '👁'}</button>
							{VECTEURS_DESSIN[a.outil] && s ? (
								<button className={`small${conv === a.id ? ' on' : ''}`} title="Transformer en élément graphique : il apparaîtra dans la vidéo exportée"
									onClick={() => { setMsgDessin(null); setConv(conv === a.id ? null : a.id); }}>⇢ Graphisme</button>
							) : null}
							<button className="small" title="Supprimer ce dessin (Ctrl+Z pour annuler)" onClick={() => update((r) => ({...r, annotations: (r.annotations ?? []).filter((x) => x.id !== a.id)}))}>🗑</button>
							{conv === a.id ? (
								<div className="nt-conv">
									<span>Ce dessin deviendra un <b>élément graphique visible dans l’export</b> (place fixe dans l’image de ce format, réglable dans Plus → Graphismes).</span>
									<span className="row">
										<button className="small primary" onClick={() => transformer(a)}>Transformer en élément graphique</button>
										<button className="small" onClick={() => setConv(null)}>Annuler</button>
									</span>
								</div>
							) : null}
						</div>
					);
				})}
				{msgDessin ? <div className={msgDessin.ok ? 'ok nt-msg' : 'err nt-msg'}>{msgDessin.text}</div> : null}
				{dessins.length ? (
					<p className="muted">Un dessin s’affiche pendant sa durée à partir de son image. Il n’apparaît jamais dans l’export : c’est une consigne de révision.
						Une flèche, un cercle ou un surligneur peut devenir un élément graphique de la vidéo (bouton « ⇢ Graphisme »).</p>
				) : null}
			</div>
		</>
	);
};

// ---------- Reperes des notes dans la regle de la timeline ----------
export const NoteMarkers: React.FC<{reel: ReelDoc; x: (s: number) => number; onSeek: (s: number) => void}> = ({reel, x, onSeek}) => {
	const e = useEtat();
	const segs = useMemo(() => baseSegments(reel), [reel]);
	const marks = useMemo(() => (reel.notes ?? []).map((n) => ({n, p: placeNote(reel, n, segs)})), [reel, segs]);
	const libres = useMemo(() => (reel.annotations ?? []).filter((a) => !a.noteId).map((a) => ({a, s: annotationSpan(reel, a, segs)})), [reel, segs]);
	return (
		<>
			{libres.map(({a, s}) => (s ? (
				<b key={a.id} className="nt-mark-d" style={{left: x(s[0])}} title={`${timecode(s[0], reel.fps)} · dessin sans note`}
					onPointerDown={(ev) => { ev.stopPropagation(); onSeek(s[0]); }}>✎</b>
			) : null))}
			{marks.filter(({n}) => e.filtre === 'toutes' || n.statut === e.filtre).map(({n, p}) => (p ? (
				<b key={n.id} className={`nt-mark s-${n.statut}`} style={{left: x(p.t)}} title={`${timecode(p.t, reel.fps)} · ${nomStatut(n.statut)} · ${court(n.text, 120)}`}
					onPointerDown={(ev) => {
						ev.stopPropagation();
						onSeek(p.t);
						changer({focus: n.id});
					}}>
					{p.end !== null ? <i className="nt-plage" style={{width: Math.max(2, x(p.end) - x(p.t))}} /> : null}
					<i className="nt-pin" />
				</b>
			) : null))}
		</>
	);
};
