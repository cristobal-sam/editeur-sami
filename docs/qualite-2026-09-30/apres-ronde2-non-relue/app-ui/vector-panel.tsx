// Edition des vecteurs poses (couleurs, recoloration par la charte, taille, position, rotation, opacite, moment, animation,
// verrou) — FICHIER DE L'AGENT « vecteurs » (docs/direction-creative-v2/SPEC.md). Branche par l'architecte dans l'onglet
// « Graphismes », sous les graphismes. Chaque vecteur a son cadenas (LockToggle de lock.tsx) ; toute retouche marque
// manual: true (touched) ; choisir une couleur marque couleursManuelles: true (la charte ne la recolore plus).
// CSS : bloc /* vecteurs */ ... /* fin vecteurs */ de styles.css.
import React, {useEffect, useMemo, useState} from 'react';
import type {VectorItem} from '../../remotion/src/types';
import {ANIM_CHOICES, SLOTS, SLOT_NAMES, colorVars, loadVectorText, parseMove, preparedVector, safeColor, vectorColors, vectorName,
	vectorPalette, vectorText, vectorUrl, type Slot, type VecColors} from '../../remotion/src/vectors';
import {fmt} from './api';
import {LockToggle, touched, withLock} from './lock';
import type {V2Props} from './v2';

/** Bibliotheque livree dans assets/banque/vecteurs (un SVG + sa fiche .json par nom ; test : tests/vecteurs). */
export const VECTOR_LIBRARY = ['fleche', 'fleche-courbe', 'fleche-main', 'fleche-bas', 'cercle', 'cercle-griffonne', 'soulignement',
	'surligneur', 'encadre', 'crochets', 'coins-cadre', 'explosion', 'eclair', 'bulle', 'attention', 'etoile', 'etincelles', 'confettis',
	'coeur', 'coche', 'croix', 'pouce', 'badge', 'note-autocollante', 'ruban-adhesif', 'etiquette-prix', 'cloche', 'telephone',
	'graphique-hausse', 'graphique-baisse', 'horloge', 'argent', 'cible', 'guillemets', 'chargement', 'curseur-clic'];
const CATEGORIES: Record<string, string> = {'flèches': 'Flèches', entourer: 'Entourer', impact: 'Impact', 'fête': 'Fête', validation: 'Oui / non',
	'étiquettes': 'Étiquettes', 'icônes': 'Icônes', graphiques: 'Graphiques'};
const ASSETS = '/assets';
const MAX = 200;
const NONE: VecColors = {principale: null, secondaire: null, contour: null};

type Fiche = {nom: string; categorie: string; motsCles: string[]; intensite: number; description?: string; couleurs: VecColors;
	anim: {entree: string; sortie: string}; duree?: number; largeur?: number; trace?: boolean; boucle?: string | null; garderCouleurs?: boolean};
const FICHES = new Map<string, Promise<Fiche | null>>();
const fiche = (nom: string) => {
	if (!FICHES.has(nom)) FICHES.set(nom, fetch(`${ASSETS}/banque/vecteurs/${encodeURIComponent(nom)}.json`).then((r) => (r.ok ? r.json() : null)).catch(() => null));
	return FICHES.get(nom)!;
};
/** Fiches des vecteurs demandes (chargees une fois). */
const useFiches = (noms: string[]) => {
	const [map, setMap] = useState<Record<string, Fiche | null>>({});
	const key = [...new Set(noms)].sort().join(',');
	useEffect(() => {
		let alive = true;
		const list = key ? key.split(',') : [];
		Promise.all(list.map(async (n) => [n, await fiche(n)] as const)).then((all) => alive && setMap(Object.fromEntries(all)));
		return () => {
			alive = false;
		};
	}, [key]);
	return map;
};

const uid = () => `vec${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
const pct = (x: number) => `${Math.round(x * 100)} %`;

/** Miniature : le vrai SVG insere en ligne, aux couleurs donnees (comme a l'image). */
export const VectorThumb: React.FC<{asset: string; colors: VecColors; size?: number; title?: string}> = ({asset, colors, size = 44, title}) => {
	const url = vectorUrl(ASSETS, asset);
	const [, setTick] = useState(0);
	useEffect(() => {
		if (vectorText(url) === undefined) loadVectorText(url).then(() => setTick((n) => n + 1));
	}, [url]);
	const svg = preparedVector(url, 'miniature');
	return <span className="vec-thumb" title={title} style={{width: size, height: size, ...colorVars(colors)} as React.CSSProperties}
		dangerouslySetInnerHTML={{__html: svg?.markup ?? ''}} />;
};

const Swatches: React.FC<{c: VecColors}> = ({c}) => (
	<span className="vec-swatches">{SLOTS.map((k) => (c[k] ? <i key={k} title={`${SLOT_NAMES[k]} : ${c[k]}`} style={{background: c[k] as string}} /> : null))}</span>
);

export const VectorPanel: React.FC<V2Props> = ({reel, t, update, seek}) => {
	const list = reel.vectors ?? [];
	const [open, setOpen] = useState<string | null>(null);
	const [adding, setAdding] = useState(false);
	const [cat, setCat] = useState('');
	const fiches = useFiches(adding ? [...VECTOR_LIBRARY, ...list.map((v) => vectorName(v.asset))] : list.map((v) => vectorName(v.asset)));
	const palette = useMemo(() => vectorPalette(reel), [reel.brand, reel.design, reel.style]);
	const source = reel.brand ? `la charte « ${reel.brand.name} »` : 'les couleurs du style';

	// toute retouche : manual (aucune passe automatique ne la deplace ni ne la retire plus)
	const set = (id: string, p: Partial<VectorItem>) => update((r) => ({...r, vectors: (r.vectors ?? []).map((v) => (v.id === id ? touched({...v, ...p}) : v))}));
	const lock = (id: string, on: boolean) => update((r) => ({...r, vectors: (r.vectors ?? []).map((v) => (v.id === id ? withLock(v, on) : v))}));
	const remove = (id: string) => update((r) => ({...r, vectors: (r.vectors ?? []).filter((v) => v.id !== id)}));
	const add = (nom: string) => {
		const f = fiches[nom];
		const keep = !!f?.garderCouleurs;
		const v: VectorItem = {id: uid(), asset: `banque/vecteurs/${nom}.svg`, at: +Math.max(0, t).toFixed(2), duration: f?.duree ?? 2,
			x: 0.5, y: 0.35, w: f?.largeur ?? 0.35, rotation: 0, opacite: 1,
			// vert / rouge d'une coche ou d'une croix : couleurs du dessin gardees ; sinon charte / style
			couleurs: keep && f ? {...NONE, ...f.couleurs} : {...NONE}, couleursManuelles: keep,
			anim: {entree: f?.anim?.entree ?? 'pop', sortie: f?.anim?.sortie ?? 'fondu'}, manual: true, raison: `Ajouté à la main : ${f?.nom ?? nom}`};
		update((r) => ({...r, vectors: [...(r.vectors ?? []), v]}));
		setOpen(v.id);
		setAdding(false);
	};
	/** Choisir une couleur : les deux autres sont figees telles qu'elles s'affichent (la charte ne recolore plus ce vecteur). */
	const setColor = (v: VectorItem, slot: Slot, hex: string) => {
		const shown = vectorColors(reel, v);
		const f = fiches[vectorName(v.asset)];
		const couleurs = {...NONE};
		for (const k of SLOTS) couleurs[k] = k === slot ? hex : f && f.couleurs[k] === null ? null : shown[k] ?? f?.couleurs[k] ?? null;
		set(v.id, {couleurs, couleursManuelles: true});
	};
	const sorted = [...list].sort((a, b) => a.at - b.at);
	const lib = VECTOR_LIBRARY.filter((n) => !cat || fiches[n]?.categorie === cat);

	return (
		<>
			<div className="card vec-panel">
				<h3>
					<span>Vecteurs <small>formes et icônes recolorables · à {fmt(t)}</small></span>
					<button className={`small${adding ? '' : ' primary'}`} disabled={list.length >= MAX} onClick={() => setAdding(!adding)}>{adding ? 'Fermer' : '+ Ajouter un vecteur'}</button>
				</h3>
				<p className="muted">Couleurs automatiques : {source} <Swatches c={palette} /> Un vecteur que tu recolores garde ses couleurs, même si tu changes de style.</p>
				{adding ? (
					<>
						<div className="presets">
							<button className={`small${!cat ? ' primary' : ''}`} onClick={() => setCat('')}>Tous</button>
							{Object.entries(CATEGORIES).map(([k, label]) => <button key={k} className={`small${cat === k ? ' primary' : ''}`} onClick={() => setCat(k)}>{label}</button>)}
						</div>
						<div className="vec-grid">
							{lib.map((n) => {
								const f = fiches[n];
								const colors = f?.garderCouleurs ? {...NONE, ...f.couleurs} : palette;
								return (
									<button key={n} type="button" title={`${f?.nom ?? n}${f?.description ? ` — ${f.description}` : ''} (ajouter à ${fmt(t)})`} onClick={() => add(n)}>
										<VectorThumb asset={`banque/vecteurs/${n}.svg`} colors={colors} size={48} />
										<span>{f?.nom ?? n}</span>
									</button>
								);
							})}
						</div>
						<p className="muted">Clique un vecteur pour le poser à {fmt(t)}. Il reste modifiable : couleurs, taille, place, animation.</p>
					</>
				) : null}
			</div>
			{sorted.map((v) => {
				const nom = vectorName(v.asset);
				const f = fiches[nom];
				const shown = vectorColors(reel, v);
				const auto = !v.couleursManuelles && SLOTS.every((k) => !safeColor(v.couleurs?.[k]));
				const slots = SLOTS.filter((k) => !f || f.couleurs[k] !== null);
				const on = t >= v.at && t < v.at + v.duration;
				const traceOk = f ? !!f.trace : true;
				const choices = ANIM_CHOICES.filter(([k]) => k !== 'trace' || traceOk);
				const entree = parseMove(v.anim?.entree, 'pop');
				const sortie = parseMove(v.anim?.sortie, 'fondu');
				const val = (s: string, m: ReturnType<typeof parseMove>) => (choices.some(([k]) => k === s) ? s : m.type === 'glisse' ? `glisse-${m.direction}` : m.type);
				return (
					<div key={v.id} className={`card vec${v.suggested ? ' suggested' : ''}${on ? ' on' : ''}`}>
						<h3>
							<span className="vec-title">
								<VectorThumb asset={v.asset} colors={shown} size={34} />
								<span>{f?.nom ?? nom} <small>{fmt(v.at)} · {v.duration.toFixed(1)} s</small></span>
							</span>
							<span className="row" style={{margin: 0}}>
								{v.suggested ? <button className="small primary" onClick={() => set(v.id, {suggested: false})}>Accepter</button>
									: <LockToggle locked={v.locked} onChange={(x) => lock(v.id, x)} />}
								<button className="small" title="Voir à l'image" onClick={() => seek(v.at + Math.min(0.6, v.duration / 2))}>▶</button>
								<button className="small" onClick={() => setOpen(open === v.id ? null : v.id)}>{open === v.id ? 'Fermer' : 'Modifier'}</button>
								<button className="small" onClick={() => remove(v.id)}>{v.suggested ? 'Refuser' : 'Supprimer'}</button>
							</span>
						</h3>
						{v.raison || v.sobriete ? <p className="muted">{[v.raison, v.sobriete].filter(Boolean).join(' · ')}</p> : null}
						{open === v.id ? (
							<>
								<div className="row vec-colors">
									<label>Couleurs</label>
									{slots.map((k) => (
										<label key={k} className="vec-color" title={auto ? `${SLOT_NAMES[k]} : couleur de ${source}` : SLOT_NAMES[k]}>
											<input type="color" value={toHex6(shown[k] ?? f?.couleurs[k] ?? '#FFFFFF')} onChange={(e) => setColor(v, k, e.target.value.toUpperCase())} />
											<span>{SLOT_NAMES[k]}</span>
										</label>
									))}
								</div>
								<div className="row">
									<label />
									<button className="small" disabled={auto} onClick={() => set(v.id, {couleurs: {...NONE}, couleursManuelles: false})}>🎨 Couleurs de la charte</button>
									{f ? <button className="small" onClick={() => set(v.id, {couleurs: {...NONE, ...f.couleurs}, couleursManuelles: true})}>Couleurs d’origine</button> : null}
									<span className="muted">{auto ? `Suit ${source}.` : 'Couleurs choisies : un changement de style ou de charte ne les touche plus.'}</span>
								</div>
								<div className="row"><label>Opacité ({pct(v.opacite)})</label>
									<input type="range" min={0.05} max={1} step={0.05} value={v.opacite} onChange={(e) => set(v.id, {opacite: Number(e.target.value)})} /></div>
								<div className="row"><label title="Même taille apparente dans tous les formats">Taille ({pct(v.w)} du petit côté)</label>
									<input type="range" min={0.05} max={1.2} step={0.01} value={v.w} onChange={(e) => set(v.id, {w: Number(e.target.value)})} /></div>
								<div className="row"><label>Position</label>
									<span className="vec-pos">
										{POS.map(([s, x, y]) => <button key={s} className={`small${Math.abs(v.x - x) < 0.01 && Math.abs(v.y - y) < 0.01 ? ' primary' : ''}`} title={`Placer ${s}`}
											onClick={() => set(v.id, {x, y})}>{s}</button>)}
									</span>
									<span className="vec-xy">
										<span>↔ <input type="range" min={-0.1} max={1.1} step={0.01} value={v.x} onChange={(e) => set(v.id, {x: Number(e.target.value)})} /></span>
										<span>↕ <input type="range" min={-0.1} max={1.1} step={0.01} value={v.y} onChange={(e) => set(v.id, {y: Number(e.target.value)})} /></span>
									</span>
								</div>
								<div className="row"><label>Rotation ({Math.round(v.rotation)}°)</label>
									<input type="range" min={-180} max={180} step={1} value={v.rotation} onChange={(e) => set(v.id, {rotation: Number(e.target.value)})} />
									<button className="small" disabled={!v.rotation} onClick={() => set(v.id, {rotation: 0})}>0°</button></div>
								<div className="row"><label>Début ({fmt(v.at)})</label>
									<button className="small" onClick={() => set(v.id, {at: +Math.max(0, t).toFixed(2)})}>Placer à {fmt(t)}</button>
									<button className="small" onClick={() => set(v.id, {at: Math.max(0, +(v.at - 0.1).toFixed(2))})}>−0,1 s</button>
									<button className="small" onClick={() => set(v.id, {at: +(v.at + 0.1).toFixed(2)})}>+0,1 s</button></div>
								<div className="row"><label>Durée ({v.duration.toFixed(1)} s)</label>
									<input type="range" min={0.3} max={8} step={0.1} value={v.duration} onChange={(e) => set(v.id, {duration: Number(e.target.value)})} /></div>
								<div className="row"><label>Animation</label>
									<span className="vec-anim">Entrée <select value={val(v.anim?.entree, entree)} onChange={(e) => set(v.id, {anim: {...v.anim, entree: e.target.value}})}>
										{choices.map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select></span>
									<span className="vec-anim">Sortie <select value={val(v.anim?.sortie, sortie)} onChange={(e) => set(v.id, {anim: {...v.anim, sortie: e.target.value}})}>
										{choices.map(([k, label]) => <option key={k} value={k}>{label.replace('par la', 'vers la').replace('par le', 'vers le').replace('le trait se dessine', 'le trait s’efface').replace('apparaît net', 'disparaît net')}</option>)}</select></span>
								</div>
							</>
						) : null}
					</div>
				);
			})}
			{!list.length ? <p className="muted">Aucun vecteur. Clique « + Ajouter un vecteur » (flèche, cercle, coche, explosion…) : il se pose à l’instant courant.</p> : null}
		</>
	);
};

const POS: [string, number, number][] = [['↖', 0.2, 0.2], ['↑', 0.5, 0.2], ['↗', 0.8, 0.2], ['←', 0.2, 0.5], ['•', 0.5, 0.5], ['→', 0.8, 0.5],
	['↙', 0.2, 0.8], ['↓', 0.5, 0.8], ['↘', 0.8, 0.8]];

/** <input type="color"> n'accepte que #rrggbb. */
const toHex6 = (c: string) => {
	const s = c.trim();
	if (/^#[0-9a-f]{6}$/i.test(s)) return s;
	if (/^#[0-9a-f]{8}$/i.test(s)) return s.slice(0, 7);
	if (/^#[0-9a-f]{3,4}$/i.test(s)) return `#${s[1]}${s[1]}${s[2]}${s[2]}${s[3]}${s[3]}`;
	return '#ffffff';
};
