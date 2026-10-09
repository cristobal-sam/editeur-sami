// Banque locale d'effets, sons, vecteurs et modeles — FICHIER DE L'AGENT « banque » (docs/direction-creative-v2/SPEC.md §9).
// Branche par l'architecte : BanquePanel = onglet « Banque » (menu Plus).
// Catalogue : assets/banque/catalogue.json, construit par engine/editeur/banque.py. GET /api/banque sert d'abord a le
// garder a jour (le moteur le reconstruit si un dossier a change : nouveaux vecteurs...), puis le fichier est lu tel quel
// (/assets/banque/catalogue.json) et filtre ICI, sans attendre le moteur a chaque lettre tapee (memes regles que
// banque.filtrer). Apercus : /assets/<entree.apercu> (forme d'onde, SVG, maquette).
// « Ajouter » cree l'element DANS LE REEL par update() (Ctrl+Z, sauvegarde auto), marque manual:true, avec la meme regle
// que banque.element_pour_reel : son -> sfx.extra ; vecteur -> vectors (couleurs null = charte / style) ; modele ->
// graphics, ou styleScenes dans un style avec habillage (les graphismes y sont masques) ; effet -> flash / effects.
// CSS : bloc /* banque */ ... /* fin banque */ de styles.css.
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {GRAPHIC_NAMES} from '../../remotion/src/graphics';
import {SFX_GAIN, sourceRectAt, sourceToOutput, timedWords, type SourceRect} from '../../remotion/src/timeline';
import type {Graphic, ReelDoc, Sfx, SfxExtra, StyleScene, VectorItem} from '../../remotion/src/types';
import {colorVars, loadVectorText, prepareSvg, vectorColors, vectorPalette, vectorText} from '../../remotion/src/vectors';
import {api, fmt} from './api';
import type {V2Props} from './v2';

// ---------------------------------------------------------------- donnees (schema : SPEC §9.1)
export type BanqueType = 'effet' | 'son' | 'vecteur' | 'template';
export type BanqueEntree = {id: string; type: BanqueType; nom: string; categorie: string; motsCles: string[]; intensite: number;
	formats: string[]; apercu: string; fichier: string | null; licence: string; provenance: string; params: Record<string, any>;
	description?: string; duree?: number; source?: string};
type Catalogue = {version: number; construit?: string; compte?: Record<string, number>; entrees: BanqueEntree[]};
export type Filtres = {type?: string; categorie?: string; q?: string; format?: string; intensite?: number};

const TYPES: [string, string][] = [['', 'Tout'], ['son', 'Sons'], ['template', 'Modèles'], ['vecteur', 'Vecteurs'], ['effet', 'Effets']];
const CATEGORIES: Record<string, string> = {'montée': 'Montée (riser)', cta: 'Appel à l’action', clic: 'Clics', ding: 'Ding / notification',
	pas: 'Pas', 'étalonnage': 'Étalonnage', formes: 'Formes'};
const catLabel = (c: string) => CATEGORIES[c] ?? c.charAt(0).toUpperCase() + c.slice(1);
const INTENSITES: [number, string][] = [[0, 'Toutes'], [1, 'Douce'], [2, 'Moyenne'], [3, 'Forte']];
const SCENE_NAMES: Record<string, string> = {metric: 'Chiffre encadré', notification: 'Notification de téléphone', comparison: 'Avant / Après',
	keyword: 'Mot clé géant', paper: 'Étiquette papier', dashboard: 'Tableau de suivi', flow: 'Parcours en étapes', cta: 'Bouton d’appel à l’action'};
const EFFETS_DEFAUT = {grain: 0, vignette: 0, grade: 'aucun'};
const SFX_DEFAUT: Sfx = {enabled: false, transition: null, highlight: null, highlightGap: 4, cta: null, start: null, volume: 0.6};
const PAGE = 48;

const uid = (p: string) => `${p}${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
/** Minuscules sans accents (memes regles que banque._plat). */
export const plat = (s: unknown) => String(s ?? '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');
const jetons = (s: string) => plat(s).split(/[^a-z0-9]+/).filter(Boolean);

/** Filtres de la banque — memes regles que banque.filtrer (moteur) : type, categorie (sans accents), format, intensite
 * exacte, q = TOUS les mots presents (debut de mot) dans nom / categorie / mots-cles / description ; pertinence si q. */
export const filtrer = (entrees: BanqueEntree[], f: Filtres) => {
	const cat = plat(f.categorie);
	const mots = jetons(f.q ?? '');
	const out = entrees.filter((e) => {
		if (f.type && e.type !== f.type) return false;
		if (cat && plat(e.categorie) !== cat) return false;
		if (f.format && !(e.formats ?? []).includes(f.format)) return false;
		if (f.intensite && e.intensite !== f.intensite) return false;
		if (!mots.length) return true;
		const j = jetons([e.nom, e.categorie, (e.motsCles ?? []).join(' '), e.description ?? ''].join(' '));
		return mots.every((m) => j.some((x) => x.startsWith(m)));
	});
	if (!mots.length) return out;
	const score = (e: BanqueEntree) => {
		const nom = plat(e.nom);
		return mots.reduce((n, m) => n + (nom.startsWith(m) ? 3 : nom.includes(m) ? 2 : 1), 0);
	};
	return out.map((e, i) => ({e, i, s: score(e)})).sort((a, b) => b.s - a.s || a.i - b.i).map((x) => x.e);
};

// ---------------------------------------------------------------- « Ajouter » : meme regle que banque.element_pour_reel
const designActif = (reel: ReelDoc) => (reel.design?.mode && reel.design.enabled !== false ? reel.design.mode : null);
/** Un style avec habillage (galerie) masque les graphismes ajoutes, sauf si le monteur les a rallumes. */
const graphismesVisibles = (reel: ReelDoc) => !designActif(reel) || reel.design?.suppressExtras === false;

/** Forme d'un modele dans CE reel : graphisme (piste Graphismes) ou scene du style. */
export const formeTemplate = (e: BanqueEntree, reel: ReelDoc): {champ: 'graphics' | 'styleScenes' | null; kind: string | null} => {
	const p = e.params ?? {};
	const mode = designActif(reel);
	if (p.cible === 'graphics' && p.kind && graphismesVisibles(reel)) return {champ: 'graphics', kind: p.kind};
	if (mode && p.scene) {
		let k: string | null = p.scene.kind;
		if (mode === 'editorial') k = ['keyword', 'paper', 'cta'].includes(k!) ? 'keyword' : null; // ce style n'affiche que le mot geant
		else if (k === 'keyword') k = 'paper';
		if (k) return {champ: 'styleScenes', kind: k};
	}
	return p.kind ? {champ: 'graphics', kind: p.kind} : {champ: null, kind: null};
};

/** L'element ajoute sera-t-il vu (entendu) dans ce reel ? raison en francais sinon. */
export const visible = (e: BanqueEntree, reel: ReelDoc): {ok: boolean; pourquoi: string; cause?: 'sfx' | 'logo'} => {
	if (e.type === 'son') return reel.sfx?.enabled ? {ok: true, pourquoi: ''}
		: {ok: false, pourquoi: 'Les bruitages sont coupés pour cette vidéo : active-les pour entendre ce son.', cause: 'sfx'};
	if (e.type === 'template') {
		const f = formeTemplate(e, reel);
		if (!f.champ) return {ok: false, pourquoi: 'Ce modèle n’a pas de version pour ce style.'};
		if (e.params?.besoin === 'logo' && !reel.brand?.logo) return {ok: false, pourquoi: 'Il faut une charte client avec un logo (onglet Style).', cause: 'logo'};
		// un graphisme pose depuis la banque est « manual » : visible meme dans un style avec habillage (Reel.tsx)
	}
	return {ok: true, pourquoi: ''};
};

type Mot = {w: string; clip: string; index: number; start: number};
/** Mots du montage (temps du montage) sans les mots masques ni coupes. */
const motsDits = (reel: ReelDoc): Mot[] => timedWords(reel).filter((w) => !w.hide && w.w.trim()).map((w) => ({w: w.w, clip: w.clip, index: w.index, start: w.outStart}));
const motA = (mots: Mot[], t: number) => mots.find((w) => w.start >= t - 0.05) ?? mots[mots.length - 1] ?? null;
/** Texte pre-rempli : premier mot d'au moins 3 lettres dit dans [t, t + 1,5 s]. */
const motFort = (mots: Mot[], t: number) => {
	for (const w of mots) {
		if (w.start < t - 0.05) continue;
		if (w.start > t + 1.5) break;
		const m = w.w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '');
		if (m.length >= 3) return m;
	}
	return null;
};

// ---------------------------------------------------------------- placement hors du visage (meme regle que banque.placer)
const r3 = (v: number) => Math.round(v * 1000) / 1000;
const mediane = (xs: number[]) => {
	const s = [...xs].sort((a, b) => a - b);
	const n = s.length;
	return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
};
type Face = {x: number; y: number; w: number};
/** Visage dans l'image (0-1) pendant [t, t + duree] : piste de recadrage (qui parle) sinon echantillons de la prise affichee. */
export const visageDansCadre = (reel: ReelDoc, rect: SourceRect | null, duree: number): Face | null => {
	if (!rect) return null;
	const src = reel.sources[rect.source];
	const track = src?.track ?? [];
	const rows = track.length ? track : src?.samples ?? [];
	let pts = rows.filter((p) => p[0] >= rect.tSrc - 0.3 && p[0] <= rect.tSrc + duree);
	if (!pts.length && rows.length) pts = [rows.reduce((a, b) => (Math.abs(b[0] - rect.tSrc) < Math.abs(a[0] - rect.tSrc) ? b : a))];
	if (!pts.length) return null;
	const ws = track.length ? pts.map((p) => p[3]).filter((w) => w > 0) : [];
	const [x, y] = sourceToOutput(rect, [mediane(pts.map((p) => p[1])), mediane(pts.map((p) => p[2]))]);
	return {x, y, w: (ws.length ? mediane(ws) : 0.26) / rect.w};
};
type Taille = {w: number; h: number; cote?: boolean; centre: boolean; sousTitres?: boolean};
/** Centre d'un element hors du visage : au-dessus de la tete, sinon a cote (s'il peut se decaler), sinon entre le menton
 * et les sous-titres, sinon le plus haut possible. */
export const placeLibre = (reel: ReelDoc, face: Face | null, taille: Taille): {x: number; y: number} | null => {
	if (!face) return null;
	const W = reel.width;
	const H = reel.height;
	const marge = H > W ? 0.07 : 0.05;
	const demi = face.w / 2 + 0.03;
	const hautVisage = (face.w * W) / H;
	const tete = face.y - 0.75 * hautVisage;
	const menton = face.y + 0.6 * hautVisage;
	const {w, h} = taille;
	if (tete - marge >= h + 0.02) return {x: 0.5, y: r3(marge + (tete - marge) / 2)};
	if (taille.cote) {
		const gauche = face.x - demi;
		const droite = 1 - face.x - demi;
		if (Math.max(gauche, droite) >= w + 0.03) {
			const x = gauche >= droite ? face.x - demi - 0.015 - w / 2 : face.x + demi + 0.015 + w / 2;
			return {x: r3(x), y: r3(Math.min(1 - marge - h / 2, Math.max(marge + h / 2, face.y)))};
		}
	}
	const bas = taille.sousTitres === false ? 1 - marge : Number(reel.style?.position ?? 0.72) - 0.02;
	if (bas - menton >= h + 0.02) return {x: 0.5, y: r3(menton + (bas - menton) / 2)};
	return {x: 0.5, y: r3(marge + h / 2)};
};
const SCENES_TAILLE: Record<string, [number | null, number]> = {notification: [0.79, 0.2], metric: [0.6, 0.3], cta: [0.7, 0.2], flow: [null, 0.22],
	dashboard: [null, 0.45], comparison: [null, 0.3], paper: [0.6, 0.16]};
/** Encombrement approximatif d'un element (part de la largeur / hauteur de l'image) ; null = plein ecran. */
const tailleElement = (reel: ReelDoc, champ: string, kind: string | null, x: any): Taille | null => {
	const W = reel.width;
	const H = reel.height;
	const u = Math.min(W, H);
	// vecteur : x.w = part du petit cote de l'image (vectors.tsx)
	if (champ === 'vectors') return {w: (x.w * u) / W, h: (x.w * Number(x.ratio || 1) * u) / H, cote: true, centre: true};
	if (champ === 'graphics') {
		if (kind === 'chiffre') return {w: 0.9, h: (u * 0.28) / H, centre: true};
		if (kind === 'coches') {
			const n = Math.min(5, (x.items ?? []).filter(Boolean).length);
			return {w: 0.8, h: (u * (0.08 + (x.title ? 0.07 : 0) + n * 0.089)) / H, centre: false};
		}
		if (kind === 'carte') return {w: (u * 0.62) / W, h: (u * (x.image ? 0.52 : 0.25)) / H, centre: false};
		return null;
	}
	const s = kind ? SCENES_TAILLE[kind] : undefined;
	if (!s) return null;
	const w = s[0] ? (s[0] * u) / W : 0.9;
	return {w, h: (s[1] * u) / H, cote: w < 0.6, centre: true, sousTitres: false};
};
/** Position libre d'un element pose a t -> {x, y} (y = bord haut pour coches et carte) ou null. */
export const placer = (reel: ReelDoc, t: number, duree: number, champ: string, kind: string | null, x: any) => {
	const taille = tailleElement(reel, champ, kind, x);
	if (!taille) return null;
	const pos = placeLibre(reel, visageDansCadre(reel, sourceRectAt(reel, t), duree), taille);
	if (!pos) return null;
	return taille.centre ? pos : {x: pos.x, y: r3(pos.y - taille.h / 2)};
};

export type Champ = 'sfx.extra' | 'vectors' | 'graphics' | 'styleScenes' | 'flash' | 'effects';
/** Element a poser pour « Ajouter » a l'instant at (manual:true : aucune passe automatique n'y touchera). */
export const elementPourReel = (e: BanqueEntree, reel: ReelDoc, at: number): {champ: Champ; element: any} => {
	const p = e.params ?? {};
	const t = Math.round(Math.max(0, at) * 100) / 100;
	const raison = `Banque : ${e.nom}`;
	if (e.type === 'son') {
		const s: SfxExtra = {id: uid('s'), t, name: p.name || e.fichier!, gain: Number(p.gain ?? 1), reason: raison, manual: true};
		return {champ: 'sfx.extra', element: s};
	}
	if (e.type === 'vecteur' || (e.type === 'effet' && p.cible === 'vector')) {
		// null = couleurs de la charte / du style ; garderCouleurs (coche verte, croix rouge) : couleurs d'origine
		const aucune = {principale: null, secondaire: null, contour: null};
		const w = Number(p.largeur) || 0.35;
		const duree = Number(p.duree) || 2;
		const pos = 'x' in p || 'y' in p ? null : placer(reel, t, duree, 'vectors', null, {w, ratio: p.ratio});
		const v: VectorItem = {id: uid('v'), asset: e.fichier!, at: t, duration: duree, x: pos ? pos.x : p.x ?? 0.5, y: pos ? pos.y : p.y ?? 0.35,
			w, rotation: 0, opacite: 1, couleurs: p.garderCouleurs ? {...aucune, ...(p.couleurs ?? {})} : aucune,
			couleursManuelles: !!p.garderCouleurs, anim: {entree: p.anim?.entree || 'pop', sortie: p.anim?.sortie || 'fondu'}, manual: true, raison};
		return {champ: 'vectors', element: v};
	}
	if (e.type === 'effet') {
		if (p.cible === 'flash') return {champ: 'flash', element: {enabled: true, kind: p.kind || 'blanc'}};
		if (p.cible === 'effects') return {champ: 'effects', element: {...EFFETS_DEFAUT, ...(reel.effects ?? {}), ...(p.effects ?? {})}};
		throw new Error('Effet sans cible.');
	}
	const f = formeTemplate(e, reel);
	if (!f.champ) throw new Error('Ce modèle n’a pas de version pour ce style.');
	const mots = p.texteDit || f.champ === 'styleScenes' ? motsDits(reel) : [];
	const dit = p.texteDit ? motFort(mots, t) : null;
	if (f.champ === 'styleScenes') {
		const sc = p.scene;
		const w = motA(mots, t);
		if (!w) throw new Error('Aucun mot dit dans ce montage : impossible d’ancrer la scène.');
		const duree = Number(sc.duree) || 2.4;
		const pos = placer(reel, w.start, duree, 'styleScenes', f.kind, {});
		const s: StyleScene = {id: uid('bq'), kind: f.kind as StyleScene['kind'], clip: w.clip, index: w.index, length: 1, text: dit || sc.text,
			secondary: sc.secondary || '', duration: duree, x: pos ? pos.x : sc.x ?? 0.5, y: pos ? pos.y : sc.y ?? 0.5, scale: sc.scale ?? 1,
			rotation: sc.rotation ?? 0, color: vectorPalette(reel).principale ?? reel.style.highlight, manual: true};
		return {champ: 'styleScenes', element: s};
	}
	const props = {...structuredClone(p.props ?? {}), banque: e.id};
	if (dit && 'text' in props) props.text = dit;
	const duree = Number(p.duree) || 2;
	if (!('y' in props)) {
		const pos = placer(reel, t, duree, 'graphics', p.kind, props);
		if (pos) props.y = pos.y;
	}
	const g: Graphic = {id: uid('g'), kind: p.kind, at: t, duration: duree, props, manual: true, raison};
	return {champ: 'graphics', element: g};
};

/** Reel avec l'element pose (scene du style en tete : elle passe devant une scene automatique au meme moment). */
export const poser = (r: ReelDoc, champ: Champ, el: any): ReelDoc => {
	if (champ === 'sfx.extra') {
		const sfx = r.sfx ?? SFX_DEFAUT;
		return {...r, sfx: {...sfx, extra: [...(sfx.extra ?? []), el]}};
	}
	if (champ === 'vectors') return {...r, vectors: [...(r.vectors ?? []), el]};
	if (champ === 'graphics') return {...r, graphics: [...(r.graphics ?? []), el]};
	if (champ === 'styleScenes') return {...r, styleScenes: [el, ...(r.styleScenes ?? [])]};
	return {...r, [champ]: el};
};

/** Retire l'element pose (par son id). */
const retirer = (r: ReelDoc, champ: Champ, id: string): ReelDoc => {
	if (champ === 'sfx.extra') return {...r, sfx: {...r.sfx!, extra: (r.sfx?.extra ?? []).filter((x) => x.id !== id)}};
	if (champ === 'vectors' || champ === 'graphics' || champ === 'styleScenes') return {...r, [champ]: ((r as any)[champ] ?? []).filter((x: {id: string}) => x.id !== id)};
	return r;
};

/** Effet deja actif dans ce reel ? */
const effetActif = (e: BanqueEntree, reel: ReelDoc) => {
	const p = e.params ?? {};
	if (p.cible === 'flash') return !!reel.flash?.enabled && (reel.flash.kind ?? 'blanc') === p.kind;
	if (p.cible === 'effects') return Object.entries(p.effects ?? {}).every(([k, v]) => (reel.effects as any)?.[k] === v);
	return false;
};
const sansEffet = (e: BanqueEntree, r: ReelDoc): ReelDoc => {
	const p = e.params ?? {};
	if (p.cible === 'flash') return {...r, flash: {...r.flash, enabled: false}};
	const fx: any = {...EFFETS_DEFAUT, ...(r.effects ?? {})};
	for (const k of Object.keys(p.effects ?? {})) fx[k] = (EFFETS_DEFAUT as any)[k];
	return {...r, effects: fx};
};

const licenceCourte = (e: BanqueEntree) => {
	if (/CC0/i.test(e.licence)) return /kenney/i.test(e.provenance) ? 'CC0 · Kenney.nl' : 'CC0';
	if (/^Création originale/i.test(e.licence)) return 'Créé ici · libre';
	if (/éditeur/i.test(e.licence)) return 'Éditeur · libre';
	return e.licence;
};
const assetUrl = (rel: string) => `/assets/${rel.split('/').map(encodeURIComponent).join('/')}`;
const points = (n: number) => '●'.repeat(n) + '○'.repeat(Math.max(0, 3 - n));

// ---------------------------------------------------------------- apercus
/** Vecteur en ligne, aux couleurs de la charte / du style de CE reel (meme preparation que l'image : vectors.tsx). */
const VectorThumb: React.FC<{e: BanqueEntree; reel: ReelDoc}> = ({e, reel}) => {
	const url = assetUrl(e.fichier ?? e.apercu);
	const [, setTick] = useState(0);
	useEffect(() => {
		let alive = true;
		if (vectorText(url) === undefined) loadVectorText(url).then(() => alive && setTick((n) => n + 1));
		return () => {
			alive = false;
		};
	}, [url]);
	const text = vectorText(url);
	const svg = useMemo(() => (text ? prepareSvg(text, `bq-${e.id.replace(/[^A-Za-z0-9_-]/g, '_')}`) : null), [text, e.id]);
	const vars = colorVars(vectorColors(reel, {couleurs: {principale: null, secondaire: null, contour: null}, couleursManuelles: !!e.params?.garderCouleurs}));
	if (text === null) return <span className="muted">SVG introuvable</span>;
	if (!svg) return <span className="muted">…</span>;
	return <div className="bq-vec" style={vars as React.CSSProperties} dangerouslySetInnerHTML={{__html: svg.markup}} />;
};

type CardProps = {e: BanqueEntree; reel: ReelDoc; playing: boolean; onPlay: (e: BanqueEntree) => void; onAdd: (e: BanqueEntree) => void;
	onRemoveEffect: (e: BanqueEntree) => void};
const Card: React.FC<CardProps> = React.memo(({e, reel, playing, onPlay, onAdd, onRemoveEffect}) => {
	const vu = visible(e, reel);
	const f = e.type === 'template' ? formeTemplate(e, reel) : null;
	let note = '';
	if (f?.champ === 'styleScenes' && e.params.cible === 'graphics') note = `Dans ce style : « ${SCENE_NAMES[f.kind!] ?? f.kind} »`;
	else if (f?.champ === 'graphics' && e.params.cible === 'styleScenes') note = `Sans habillage : « ${GRAPHIC_NAMES[f.kind!] ?? f.kind} »`;
	if (!vu.ok && vu.cause !== 'sfx') note = vu.pourquoi;
	const actif = e.type === 'effet' && e.params?.cible !== 'vector' && effetActif(e, reel);
	const global = e.type === 'effet' && e.params?.cible !== 'vector';
	return (
		<div className={`bq-card bq-${e.type}${actif ? ' on' : ''}`}>
			<div className={`bq-prev bq-prev-${e.type}`} title={e.description || e.nom}>
				{e.type === 'vecteur' || (e.type === 'effet' && e.params?.cible === 'vector') ? <VectorThumb e={e} reel={reel} />
					: <img src={assetUrl(e.apercu)} alt="" loading="lazy" draggable={false} />}
				{e.type === 'son' ? <button className={`bq-play${playing ? ' on' : ''}`} title={playing ? 'Arrêter' : 'Écouter'} onClick={() => onPlay(e)}>{playing ? '■' : '▶'}</button> : null}
			</div>
			<div className="bq-name" title={e.description || e.nom}>{e.nom}</div>
			<div className="bq-meta">{catLabel(e.categorie)} · <span title={`Intensité ${e.intensite} sur 3`}>{points(e.intensite)}</span>{e.duree ? ` · ${e.duree.toFixed(1)} s` : ''}</div>
			{note ? <div className={`bq-note${vu.ok ? '' : ' warn'}`}>{note}</div> : null}
			<div className="bq-actions">
				{actif ? <button className="small" title="Retirer cet effet de la vidéo" onClick={() => onRemoveEffect(e)}>✓ Actif · Retirer</button>
					: <button className="small bq-add" title={global ? (e.description ?? '') : 'Ajouter à l’instant de la tête de lecture'} onClick={() => onAdd(e)}>
						{global ? 'Appliquer' : '+ Ajouter'}</button>}
			</div>
			<div className="bq-lic" title={`Licence : ${e.licence}\nProvenance : ${e.provenance}`}>{licenceCourte(e)}</div>
		</div>
	);
});

// ---------------------------------------------------------------- retouche rapide de l'element qui vient d'etre pose
type Pose = {e: BanqueEntree; champ: Champ; id: string; at: number};
const Retouche: React.FC<{pose: Pose; reel: ReelDoc; update: V2Props['update']; seek: (s: number) => void; onClose: () => void}> = ({pose, reel, update, seek, onClose}) => {
	const {e, champ, id, at} = pose;
	const vu = visible(e, reel);
	const setG = (patch: Record<string, any>) => update((r) => ({...r, graphics: (r.graphics ?? []).map((g) => (g.id === id ? {...g, props: {...g.props, ...patch}, manual: true} : g))}));
	const setS = (patch: Partial<StyleScene>) => update((r) => ({...r, styleScenes: (r.styleScenes ?? []).map((s) => (s.id === id ? {...s, ...patch, manual: true} : s))}));
	const setX = (gain: number) => update((r) => ({...r, sfx: {...r.sfx!, extra: (r.sfx?.extra ?? []).map((x) => (x.id === id ? {...x, gain, manual: true} : x))}}));
	const g = champ === 'graphics' ? (reel.graphics ?? []).find((x) => x.id === id) : undefined;
	const s = champ === 'styleScenes' ? (reel.styleScenes ?? []).find((x) => x.id === id) : undefined;
	const x = champ === 'sfx.extra' ? (reel.sfx?.extra ?? []).find((y) => y.id === id) : undefined;
	const global = champ === 'flash' || champ === 'effects';
	const gone = !global && !g && !s && !x && !(champ === 'vectors' && (reel.vectors ?? []).some((v) => v.id === id));
	if (gone) return null;
	const where = {graphics: 'piste Graphismes', styleScenes: 'habillage du style', 'sfx.extra': 'Style → Bruitages posés un par un',
		vectors: 'onglet Graphismes → Vecteurs', flash: 'toute la vidéo', effects: 'toute la vidéo'}[champ];
	return (
		<div className="card bq-done">
			<h3><span>✓ « {e.nom} » {global ? 'appliqué' : `ajouté à ${fmt(at)}`} <small>{where}</small></span>
				<span className="row" style={{margin: 0}}>
					{!global ? <button className="small" onClick={() => seek(Math.max(0, at - 0.5))}>▶ Voir</button> : null}
					{!global ? <button className="small" title="Retirer cet élément" onClick={() => { update((r) => retirer(r, champ, id)); onClose(); }}>Retirer</button> : null}
					<button className="small" title="Fermer" onClick={onClose}>✕</button>
				</span></h3>
			{!vu.ok ? (
				<div className="row bq-warn"><span className="grow">{vu.pourquoi}</span>
					{vu.cause === 'sfx' ? <button className="small primary" onClick={() => update((r) => ({...r, sfx: {...(r.sfx ?? SFX_DEFAUT), enabled: true}}))}>🔊 Activer les bruitages</button> : null}
				</div>
			) : null}
			{g?.kind === 'chiffre' ? (
				<div className="row"><label>Chiffre</label>
					<input type="text" style={{width: 44}} placeholder="avant" value={g.props.prefix ?? ''} onChange={(ev) => setG({prefix: ev.target.value})} />
					<input type="number" style={{width: 90}} value={g.props.value} onChange={(ev) => setG({value: Number(ev.target.value)})} />
					<input type="text" style={{width: 60}} placeholder="après" value={g.props.suffix ?? ''} onChange={(ev) => setG({suffix: ev.target.value})} />
					<input type="text" className="grow" placeholder="Texte sous le chiffre" value={g.props.label ?? ''} onChange={(ev) => setG({label: ev.target.value})} /></div>
			) : null}
			{g?.kind === 'coches' ? (
				<>
					<div className="row"><label>Titre</label><input type="text" className="grow" value={g.props.title ?? ''} onChange={(ev) => setG({title: ev.target.value})} /></div>
					<textarea rows={3} style={{width: '100%'}} value={(g.props.items ?? []).join('\n')} onChange={(ev) => setG({items: ev.target.value.split('\n')})} />
				</>
			) : null}
			{g?.kind === 'carte' ? (
				<>
					<div className="row"><label>Titre</label><input type="text" className="grow" value={g.props.title ?? ''} onChange={(ev) => setG({title: ev.target.value})} /></div>
					<div className="row"><label>Sous-titre</label><input type="text" className="grow" value={g.props.subtitle ?? ''} onChange={(ev) => setG({subtitle: ev.target.value})} /></div>
				</>
			) : null}
			{g?.kind === 'motgeant' ? (
				<div className="row"><label>Mot</label><input type="text" className="grow" value={g.props.text ?? ''} onChange={(ev) => setG({text: ev.target.value})} /></div>
			) : null}
			{s ? (
				<>
					<div className="row"><label>Texte</label><input type="text" className="grow" value={s.text} onChange={(ev) => setS({text: ev.target.value})} /></div>
					{s.kind !== 'keyword' && s.kind !== 'paper' ? (
						<div className="row"><label>{s.kind === 'comparison' ? 'Après' : 'Texte 2'}</label><input type="text" className="grow" value={s.secondary ?? ''}
							placeholder={['dashboard', 'flow'].includes(s.kind) ? 'Séparer les étapes par |' : ''} onChange={(ev) => setS({secondary: ev.target.value})} /></div>
					) : null}
					<p className="muted">Ancrée au mot dit à cet instant : elle suit le montage si tu coupes avant.</p>
				</>
			) : null}
			{x ? (
				<div className="row"><label>Volume ({Math.round((x.gain ?? 1) * 100)} %)</label>
					<input type="range" min={0} max={3} step={0.05} value={x.gain ?? 1} onChange={(ev) => setX(Number(ev.target.value))} /></div>
			) : null}
			{e.params?.aModifier && (g || s) ? <p className="muted">Remplace le texte d’exemple par le tien : rien n’est inventé à ta place.</p> : null}
			{champ === 'vectors' ? <p className="muted">Couleurs de ta charte appliquées automatiquement. Taille, position, couleurs : onglet Graphismes → Vecteurs.</p> : null}
			{global ? <p className="muted">{e.description}. Un changement de style peut le remplacer.</p> : null}
		</div>
	);
};

// ---------------------------------------------------------------- panneau
type Grid = {entrees: BanqueEntree[]; reel: ReelDoc; playing: string | null; onPlay: CardProps['onPlay']; onAdd: CardProps['onAdd']; onRemoveEffect: CardProps['onRemoveEffect']};
const GridView: React.FC<Grid> = React.memo(({entrees, reel, playing, onPlay, onAdd, onRemoveEffect}) => (
	<div className="bq-grid">
		{entrees.map((e) => <Card key={e.id} e={e} reel={reel} playing={playing === e.id} onPlay={onPlay} onAdd={onAdd} onRemoveEffect={onRemoveEffect} />)}
	</div>
));

export const BanquePanel: React.FC<V2Props> = ({reel, t, format, update, seek}) => {
	const [cat, setCat] = useState<Catalogue | null>(null);
	const [err, setErr] = useState('');
	const [loading, setLoading] = useState(false);
	const [q, setQ] = useState('');
	const [type, setType] = useState('');
	const [categorie, setCategorie] = useState('');
	const [intensite, setIntensite] = useState(0);
	const [limit, setLimit] = useState(PAGE);
	const [playing, setPlaying] = useState<string | null>(null);
	const [pose, setPose] = useState<Pose | null>(null);
	const [msg, setMsg] = useState('');
	const audio = useRef<HTMLAudioElement | null>(null);
	const tRef = useRef(t);
	tRef.current = t;
	const reelRef = useRef(reel);
	reelRef.current = reel;

	const charger = useCallback(async () => {
		setLoading(true);
		setErr('');
		// 1. le moteur remet le catalogue a jour s'il le faut (vecteurs ajoutes...) ; serveur pas encore relance : ignore
		let v = String(Date.now());
		try {
			const r = await api('/api/banque?type=vecteur');
			if (r?.construit) v = r.construit;
		} catch {}
		// 2. le catalogue complet, filtre ici
		try {
			const r = await fetch(`/assets/banque/catalogue.json?v=${encodeURIComponent(v)}`);
			if (!r.ok) throw new Error(String(r.status));
			const data: Catalogue = await r.json();
			if (!Array.isArray(data?.entrees)) throw new Error('catalogue invalide');
			setCat(data);
		} catch {
			setErr('La banque n’est pas encore prête (catalogue absent). Demande de la construire : « python -m editeur banque construire ».');
		}
		setLoading(false);
	}, []);
	useEffect(() => {
		charger();
	}, [charger]);
	useEffect(() => () => audio.current?.pause(), []);
	useEffect(() => setLimit(PAGE), [q, type, categorie, intensite]);

	const tous = cat?.entrees ?? [];
	const compte = useMemo(() => Object.fromEntries(TYPES.map(([k]) => [k, tous.filter((e) => (!k || e.type === k) && (e.formats ?? []).includes(format)).length])), [tous, format]);
	const categories = useMemo(() => [...new Set(tous.filter((e) => !type || e.type === type).map((e) => e.categorie))], [tous, type]);
	useEffect(() => {
		if (categorie && !categories.includes(categorie)) setCategorie('');
	}, [categories, categorie]);
	const choisis = useMemo(() => filtrer(tous, {type, categorie, q, intensite, format: format in {'9:16': 1, '16:9': 1, '4:5': 1, '1:1': 1} ? format : undefined}),
		[tous, type, categorie, q, intensite, format]);
	const vus = useMemo(() => choisis.slice(0, limit), [choisis, limit]);

	const onPlay = useCallback((e: BanqueEntree) => {
		const a0 = audio.current;
		a0?.pause();
		if (a0 && (a0 as any).bq === e.id) {
			audio.current = null;
			setPlaying(null);
			return;
		}
		const a = new Audio(assetUrl(e.fichier!));
		(a as any).bq = e.id;
		const name = e.params?.name as string | undefined;
		a.volume = Math.max(0, Math.min(1, 0.6 * Number(e.params?.gain ?? 1) * (name ? SFX_GAIN[name] ?? 1 : 1)));
		a.onended = () => audio.current === a && setPlaying(null);
		audio.current = a;
		setPlaying(e.id);
		a.play().catch(() => setPlaying(null));
	}, []);
	const onAdd = useCallback((e: BanqueEntree) => {
		const at = tRef.current;
		try {
			const {champ, element} = elementPourReel(e, reelRef.current, at);
			// plafonds du serveur (validateV2) : au-dela, il refuserait TOUTE la sauvegarde (montage compris)
			if (champ === 'vectors' && (reelRef.current.vectors?.length ?? 0) >= 200) throw new Error('Limite atteinte : 200 vecteurs au plus par vidéo. Retires-en un (Plus → Graphismes) pour en ajouter.');
			if (champ === 'sfx.extra' && (reelRef.current.sfx?.extra?.length ?? 0) >= 500) throw new Error('Limite atteinte : 500 bruitages posés au plus par vidéo.');
			update((r) => poser(r, champ, element));
			setPose({e, champ, id: element.id ?? champ, at: element.t ?? element.at ?? at});
			setMsg('');
		} catch (x) {
			setMsg(String((x as Error)?.message ?? x));
		}
	}, [update]);
	const onRemoveEffect = useCallback((e: BanqueEntree) => update((r) => sansEffet(e, r)), [update]);

	const sfxOff = !reel.sfx?.enabled && (!type || type === 'son');
	const styleSons = [reel.sfx?.transition, reel.sfx?.highlight, reel.sfx?.cta, reel.sfx?.start].filter(Boolean).length;
	return (
		<>
			<div className="card">
				<h3><span>Banque d’effets <small>{choisis.length} sur {compte[''] ?? 0} · à {fmt(t)}</small></span>
					<button className="small" title="Relire la banque (nouveaux vecteurs ou sons)" disabled={loading} onClick={charger}>{loading ? '…' : '↻'}</button></h3>
				<input type="search" className="bq-search" placeholder="Chercher : whoosh, impact, flèche, liste, notification…" value={q}
					onChange={(ev) => setQ(ev.target.value)} />
				<div className="row bq-types">
					<div className="seg">{TYPES.map(([k, label]) => (
						<button key={k} className={`small${type === k ? ' primary' : ''}`} onClick={() => setType(k)}>{label} <small>{compte[k] ?? 0}</small></button>
					))}</div>
				</div>
				<div className="row">
					<select value={categorie} onChange={(ev) => setCategorie(ev.target.value)} title="Catégorie">
						<option value="">Toutes les catégories</option>
						{categories.map((c) => <option key={c} value={c}>{catLabel(c)}</option>)}
					</select>
					<div className="seg" title="Intensité">{INTENSITES.map(([n, label]) => (
						<button key={n} className={`small${intensite === n ? ' primary' : ''}`} onClick={() => setIntensite(n)}>{n ? points(n) : label}</button>
					))}</div>
				</div>
				{sfxOff ? (
					<div className="row bq-warn"><span className="grow">🔇 Les bruitages sont coupés pour cette vidéo : un son ajouté ne s’entendra pas.
						{styleSons ? ' (Les bruitages du style se remettront aussi à jouer.)' : ''}</span>
						<button className="small" onClick={() => update((r) => ({...r, sfx: {...(r.sfx ?? SFX_DEFAUT), enabled: true}}))}>🔊 Activer les bruitages</button></div>
				) : null}
				{msg ? <p className="err">{msg}</p> : null}
				{err ? <p className="err">{err}</p> : null}
			</div>
			{pose ? <Retouche pose={pose} reel={reel} update={update} seek={seek} onClose={() => setPose(null)} /> : null}
			{cat && !choisis.length ? <p className="muted">Rien ne correspond. Essaie un autre mot (ex. « whoosh », « flèche », « liste ») ou « Tout ».</p> : null}
			<GridView entrees={vus} reel={reel} playing={playing} onPlay={onPlay} onAdd={onAdd} onRemoveEffect={onRemoveEffect} />
			{choisis.length > limit ? (
				<div className="row" style={{justifyContent: 'center'}}><button className="small" onClick={() => setLimit(limit + PAGE * 2)}>Afficher plus ({choisis.length - limit} autres)</button></div>
			) : null}
			{cat ? <p className="muted bq-foot">Tout est local : sons de l’éditeur et créés ici, sons Kenney.nl (CC0), vecteurs et modèles de l’éditeur. Survole la ligne du bas d’une carte pour voir sa licence et sa provenance.</p> : null}
		</>
	);
};
