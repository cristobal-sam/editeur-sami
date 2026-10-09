// Sons de coupe varies (ronde « sons », 2026-10-02). Avant, chaque coupe et chaque entree d'interface jouait le meme
// « whoosh » (le « meme son de vent ») : ici « Varier les sons », « Famille de sons » (Auto selon le style ou une famille de
// styles/sons-transitions.json, lu par GET /api/sons-transitions), « ▶ Écouter » (les sons de la famille l'un apres l'autre,
// memes fichiers /assets/... que le lecteur) et le volume. Choisir une famille ecrit sa reserve (sfx.pool) dans le reel ;
// remotion/src/timeline.ts (sfxEvents) en tire un son different a chaque coupe. Le moteur fait la meme chose
// (engine/editeur/sfxgen.py : appliquer_famille, reserve).
import React, {useEffect, useRef, useState} from 'react';
import {SFX_GAIN, sfxFile} from '../../remotion/src/timeline';
import type {ReelDoc, Sfx} from '../../remotion/src/types';

type Son = {name: string; titre?: string; pic: number; gain: number; duree: number; licence: string};
type Famille = {id: string; nom: string; description: string; sons: Record<string, Son[]>};
export type SonsCatalogue = {version: number; roles: Record<string, string>; defaut: string; familles: Famille[];
	styles: Record<string, string>; sons: Record<string, string>};

const ROLES = ['transition', 'interface', 'apparition', 'mot-fort', 'impact', 'cta'];
const SFX_VIDE: Sfx = {enabled: false, transition: null, highlight: null, highlightGap: 4, cta: null, start: null, volume: 0.6};

/** Famille « auto » : celle du style du reel, sinon celle de son son de coupe, sinon la famille par defaut (comme le moteur). */
export const familleAuto = (cat: SonsCatalogue, reel: ReelDoc): string => {
	const ids = new Set(cat.familles.map((f) => f.id));
	const id = cat.styles[reel.template ?? ''] ?? cat.sons[reel.sfx?.transition ?? ''] ?? cat.defaut;
	return ids.has(id) ? id : cat.familles[0]?.id ?? '';
};

/** Reserve (« pool ») d'une famille : meme forme et meme ordre que sfxgen.reserve() (32 sons au plus). */
export const reserveFamille = (cat: SonsCatalogue, id: string): NonNullable<Sfx['pool']> => {
	const f = cat.familles.find((x) => x.id === id);
	return f ? ROLES.flatMap((role) => (f.sons[role] ?? []).map((s) => ({name: s.name, pic: s.pic, gain: s.gain, role}))).slice(0, 32) : [];
};

/** Ce que « Écouter » fait entendre : toutes les coupes, puis un son de chaque autre role. */
const aEcouter = (f: Famille): Son[] => [...(f.sons.transition ?? []), ...ROLES.slice(1).map((r) => f.sons[r]?.[0]).filter((s): s is Son => !!s)];

export const SonsTransitions: React.FC<{reel: ReelDoc; onChange: (sfx: Sfx) => void}> = ({reel, onChange}) => {
	const [cat, setCat] = useState<SonsCatalogue | null>(null);
	const [err, setErr] = useState('');
	const [joue, setJoue] = useState<Son | null>(null);
	const lecture = useRef<{id: number; audio: HTMLAudioElement | null}>({id: 0, audio: null});
	const arreter = () => {
		lecture.current.id++;
		lecture.current.audio?.pause();
		lecture.current.audio = null;
		setJoue(null);
	};
	useEffect(() => {
		let vivant = true;
		fetch('/api/sons-transitions')
			.then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
			.then((d: SonsCatalogue) => vivant && Array.isArray(d?.familles) && setCat(d))
			.catch(() => vivant && setErr('Familles de sons indisponibles pour le moment (relance l’éditeur si ça dure).'));
		return () => {
			vivant = false;
			lecture.current.id++;
			lecture.current.audio?.pause();
		};
	}, []);
	const sfx = reel.sfx ?? SFX_VIDE;
	const varier = sfx.varier !== false;
	const choix = sfx.famille && sfx.famille !== 'auto' && cat?.familles.some((f) => f.id === sfx.famille) ? sfx.famille : 'auto';
	const utilisee = cat ? (choix === 'auto' ? familleAuto(cat, reel) : choix) : '';
	const fam = cat?.familles.find((f) => f.id === utilisee);
	const set = (p: Partial<Sfx>) => onChange({...sfx, ...p});
	const choisir = (id: string) => {
		if (!cat) return;
		arreter();
		set({famille: id, pool: reserveFamille(cat, id === 'auto' ? familleAuto(cat, reel) : id)});
	};
	const ecouter = async () => {
		if (joue) return arreter();
		if (!fam) return;
		const id = ++lecture.current.id;
		for (const s of aEcouter(fam)) {
			if (lecture.current.id !== id) return;
			const a = new Audio(`/assets/${sfxFile(s.name)}`);
			a.volume = Math.max(0, Math.min(1, 0.6 * s.gain * (SFX_GAIN[s.name] ?? 1) * Math.max(0.3, sfx.volume / 0.6)));
			lecture.current.audio = a;
			setJoue(s);
			await new Promise<void>((done) => {
				a.onended = () => done();
				a.onerror = () => done();
				a.play().catch(() => done());
			});
			await new Promise((r) => setTimeout(r, 280));
		}
		if (lecture.current.id === id) {
			lecture.current.audio = null;
			setJoue(null);
		}
	};
	return (
		<div className="card">
			<h3>Sons des coupes <small>un son différent à chaque coupe</small></h3>
			<div className="row">
				<label className="inline" title="Chaque coupe, chaque écran qui entre et chaque mot fort prend un son différent de la famille. Décoché : toujours le même son, comme avant.">
					<input type="checkbox" checked={varier} onChange={(e) => set({varier: e.target.checked})} /> Varier les sons {varier ? '✓' : ''}</label>
			</div>
			<div className="row"><label>Famille de sons</label>
				<select className="grow" value={choix} disabled={!cat} onChange={(e) => choisir(e.target.value)}>
					<option value="auto">Auto selon le style{cat && choix === 'auto' && fam ? ` (${fam.nom})` : ''}</option>
					{(cat?.familles ?? []).map((f) => <option key={f.id} value={f.id}>{f.nom}</option>)}
				</select>
				<button className="small" disabled={!fam} title="Fait entendre les sons de cette famille, l’un après l’autre" onClick={ecouter}>
					{joue ? '■ Arrêter' : '▶ Écouter'}</button>
			</div>
			{fam ? <p className="muted">{joue ? `▶ ${joue.titre ?? joue.name}` : fam.description}</p> : null}
			{!sfx.transition && fam ? (
				<div className="row">
					<span className="muted grow">Ce style ne met pas de son aux coupes (montage sobre).</span>
					<button className="small" title="Ajoute un son à chaque coupe, tiré de cette famille"
						onClick={() => set({enabled: true, transition: fam.sons.transition?.[0]?.name ?? 'whoosh-court',
							...(sfx.pool?.length ? {} : {famille: choix, pool: reserveFamille(cat!, utilisee)})})}>Ajouter des sons aux coupes</button>
				</div>
			) : null}
			{!sfx.enabled ? <p className="muted">Les bruitages sont coupés pour cette vidéo : coche « Activés » pour les entendre.</p> : null}
			<div className="row"><label>Volume ({Math.round(sfx.volume * 100)} %)</label>
				<input type="range" min={0} max={1} step={0.05} value={sfx.volume} onChange={(e) => set({volume: Number(e.target.value)})} /></div>
			{err ? <p className="err">{err}</p> : null}
		</div>
	);
};
