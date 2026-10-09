// Panneaux ajoutes : graphismes, conseils (rythme + raccords), plans de coupe, chartes clients,
// declinaisons, montages visuels, multicamera, file d'exports.
import React, {useEffect, useMemo, useState} from 'react';
import {GRAPHIC_NAMES} from '../../remotion/src/graphics';
import {duration} from '../../remotion/src/timeline';
import {FONT_FILES, FORMATS, formatOf, type Brand, type Broll, type Graphic, type GraphicKind, type ReelDoc, type Source} from '../../remotion/src/types';
import {api, fmt, useJob, type Job} from './api';
import {weakZones, type Zone} from './conseils';

type Update = (fn: (r: ReelDoc) => ReelDoc) => void;
const uid = (p: string) => `${p}${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;

// ---------------- Graphismes (point 6) ----------------
const DEFAULTS: Record<GraphicKind, {duration: number; props: Record<string, any>}> = {
	chiffre: {duration: 2.2, props: {value: 100, prefix: '', suffix: ' %', label: 'DE CLIENTS SATISFAITS'}},
	coches: {duration: 3.5, props: {title: 'Inclus', items: ['Premier bénéfice', 'Deuxième bénéfice', 'Troisième bénéfice']}},
	carte: {duration: 2.5, props: {title: 'Titre de la carte', subtitle: 'Sous-titre', image: '', side: 'droite'}},
	motgeant: {duration: 0.9, props: {text: 'WOW'}},
	logo: {duration: 2, props: {}},
};

export const GraphicsPanel: React.FC<{reel: ReelDoc; update: Update; t: number; seek: (s: number) => void; current: string}> = ({reel, update, t, seek, current}) => {
	const list = reel.graphics ?? [];
	const [open, setOpen] = useState<string | null>(null);
	const [job, setJob] = useJob((j) => update((r) => ({...r, graphics: [...(r.graphics ?? []).filter((g) => !g.suggested), ...(j.result as Graphic[])]})));
	const set = (id: string, p: Partial<Graphic>) => update((r) => ({...r, graphics: (r.graphics ?? []).map((g) => (g.id === id ? {...g, ...p} : g))}));
	const setProp = (g: Graphic, k: string, v: any) => set(g.id, {props: {...g.props, [k]: v}});
	const remove = (id: string) => update((r) => ({...r, graphics: (r.graphics ?? []).filter((g) => g.id !== id)}));
	const add = (kind: GraphicKind) => {
		const g: Graphic = {id: uid('g'), kind, at: +t.toFixed(2), ...structuredClone(DEFAULTS[kind])};
		update((r) => ({...r, graphics: [...(r.graphics ?? []), g]}));
		setOpen(g.id);
	};
	const suggested = list.filter((g) => g.suggested);
	return (
		<>
			<div className="card">
				<h3>Ajouter un élément <small>à {fmt(t)}</small></h3>
				<div className="presets">{(Object.keys(GRAPHIC_NAMES) as GraphicKind[]).map((k) => <button key={k} className="small" onClick={() => add(k)}>+ {GRAPHIC_NAMES[k]}</button>)}</div>
				<div className="row">
					<button className="small primary" disabled={job?.status === 'running'} onClick={async () => setJob(await api(`/api/reels/${current}/graphismes`, 'POST'))}>✨ Proposer des emplacements (IA)</button>
					{job?.status === 'running' ? <span className="muted">Lecture du texte… (chiffres, bénéfices, mot choc)</span> : null}
					{job?.status === 'failed' ? <span className="err">{job.error}</span> : null}
				</div>
				{suggested.length ? (
					<div className="row">
						<span className="muted">{suggested.length} proposition(s) en pointillé</span>
						<button className="small" onClick={() => update((r) => ({...r, graphics: (r.graphics ?? []).map((g) => ({...g, suggested: false}))}))}>Tout accepter</button>
						<button className="small" onClick={() => update((r) => ({...r, graphics: (r.graphics ?? []).filter((g) => !g.suggested)}))}>Tout refuser</button>
					</div>
				) : null}
			</div>
			{[...list].sort((a, b) => a.at - b.at).map((g) => (
				<div key={g.id} className={`card${g.suggested ? ' suggested' : ''}`}>
					<h3>
						<span>{GRAPHIC_NAMES[g.kind]} <small>{fmt(g.at)} · {g.duration.toFixed(1)} s</small></span>
						<span className="row" style={{margin: 0}}>
							{g.suggested ? <button className="small primary" onClick={() => set(g.id, {suggested: false})}>Accepter</button> : null}
							<button className="small" onClick={() => seek(g.at)}>▶</button>
							<button className="small" onClick={() => setOpen(open === g.id ? null : g.id)}>{open === g.id ? 'Fermer' : 'Modifier'}</button>
							<button className="small" onClick={() => remove(g.id)}>{g.suggested ? 'Refuser' : 'Supprimer'}</button>
						</span>
					</h3>
					{open === g.id ? (
						<>
							<div className="row"><label>Début</label><button className="small" onClick={() => set(g.id, {at: +t.toFixed(2)})}>Placer à {fmt(t)}</button>
								<button className="small" onClick={() => set(g.id, {at: Math.max(0, +(g.at - 0.1).toFixed(2))})}>−0,1 s</button>
								<button className="small" onClick={() => set(g.id, {at: +(g.at + 0.1).toFixed(2)})}>+0,1 s</button></div>
							<div className="row"><label>Durée ({g.duration.toFixed(1)} s)</label><input type="range" min={0.5} max={6} step={0.1} value={g.duration} onChange={(e) => set(g.id, {duration: Number(e.target.value)})} /></div>
							{g.kind === 'chiffre' ? (
								<>
									<div className="row"><label>Valeur</label><input type="number" value={g.props.value} onChange={(e) => setProp(g, 'value', Number(e.target.value))} />
										<input type="text" placeholder="avant" style={{width: 60}} value={g.props.prefix ?? ''} onChange={(e) => setProp(g, 'prefix', e.target.value)} />
										<input type="text" placeholder="après" style={{width: 80}} value={g.props.suffix ?? ''} onChange={(e) => setProp(g, 'suffix', e.target.value)} /></div>
									<div className="row"><label>Libellé</label><input type="text" className="grow" value={g.props.label ?? ''} onChange={(e) => setProp(g, 'label', e.target.value)} /></div>
								</>
							) : null}
							{g.kind === 'coches' ? (
								<>
									<div className="row"><label>Titre</label><input type="text" className="grow" value={g.props.title ?? ''} onChange={(e) => setProp(g, 'title', e.target.value)} /></div>
									<textarea rows={4} style={{width: '100%'}} value={(g.props.items ?? []).join('\n')} onChange={(e) => setProp(g, 'items', e.target.value.split('\n'))} />
									<p className="muted">Une ligne par case (5 au plus).</p>
								</>
							) : null}
							{g.kind === 'carte' ? (
								<>
									<div className="row"><label>Titre</label><input type="text" className="grow" value={g.props.title ?? ''} onChange={(e) => setProp(g, 'title', e.target.value)} /></div>
									<div className="row"><label>Sous-titre</label><input type="text" className="grow" value={g.props.subtitle ?? ''} onChange={(e) => setProp(g, 'subtitle', e.target.value)} /></div>
									<div className="row"><label>Photo</label>
										<button className="small" onClick={() => setProp(g, 'image', reel.brand?.logo ?? '')} disabled={!reel.brand?.logo}>Logo du client</button>
										<button className="small" onClick={() => setProp(g, 'image', '')}>Aucune</button>
										<ImagePick onPick={(p) => setProp(g, 'image', p)} /></div>
									<div className="row"><label>Côté</label>{['gauche', 'droite'].map((s) => <button key={s} className={`small${(g.props.side ?? 'droite') === s ? ' primary' : ''}`} onClick={() => setProp(g, 'side', s)}>{s}</button>)}</div>
								</>
							) : null}
							{g.kind === 'motgeant' ? (
								<div className="row"><label>Mot</label><input type="text" className="grow" value={g.props.text ?? ''} onChange={(e) => setProp(g, 'text', e.target.value)} />
									<input type="color" value={g.props.color || reel.style.highlight} onChange={(e) => setProp(g, 'color', e.target.value)} /></div>
							) : null}
							{g.kind === 'logo' && !reel.brand?.logo ? <p className="muted">Choisis une charte client avec un logo (onglet Style).</p> : null}
							{['chiffre', 'coches', 'carte'].includes(g.kind) ? (
								<div className="row"><label>Hauteur ({Math.round((g.props.y ?? (g.kind === 'chiffre' ? 0.3 : g.kind === 'coches' ? 0.22 : 0.16)) * 100)} %)</label>
									<input type="range" min={0.05} max={0.8} step={0.01} value={g.props.y ?? (g.kind === 'chiffre' ? 0.3 : g.kind === 'coches' ? 0.22 : 0.16)} onChange={(e) => setProp(g, 'y', Number(e.target.value))} /></div>
							) : null}
						</>
					) : null}
				</div>
			))}
			{!list.length ? <p className="muted">Aucun graphisme. Ajoute un élément à l'instant courant, ou laisse l'IA proposer des emplacements.</p> : null}
		</>
	);
};

/** Image d'un fichier local (photo pour une carte) : envoyee au serveur dans assets/images. */
const ImagePick: React.FC<{onPick: (path: string) => void}> = ({onPick}) => (
	<label className="small button-like">Fichier…
		<input type="file" accept="image/png,image/jpeg,image/webp" style={{display: 'none'}} onChange={async (e) => {
			const f = e.target.files?.[0];
			if (!f) return;
			const data = await new Promise<string>((ok) => {
				const r = new FileReader();
				r.onload = () => ok(String(r.result));
				r.readAsDataURL(f);
			});
			const res = await api('/api/images', 'POST', {name: f.name, data});
			onPick(res.path);
		}} />
	</label>
);

// ---------------- Conseils : rythme (point 10) + faux raccords (point 11) ----------------
export type Alert = {t: number; clipA: string; clipB: string; gravite: number; notes: string[]};
export const ConseilsPanel: React.FC<{reel: ReelDoc; update: Update; seek: (s: number) => void; current: string; alerts: Alert[] | null;
	setAlerts: (a: Alert[] | null) => void; goto: (tab: 'ajouter' | 'graphismes') => void}> = ({reel, update, seek, current, alerts, setAlerts, goto}) => {
	const zones = useMemo(() => weakZones(reel), [reel]);
	const [done, setDone] = useState<Set<string>>(new Set());
	const [vision, setVision] = useState(true);
	const [job, setJob] = useJob((j) => setAlerts(j.result));
	const GRAV = ['info', 'à vérifier', 'probable', 'évident'];
	return (
		<>
			<div className="card">
				<h3>Rythme <small>{zones.length ? `${zones.length} zone(s) faible(s)` : 'aucune zone faible'}</small></h3>
				<p className="muted">Zones rouges de la bande « Rythme » : propositions à accepter d'un clic (Ctrl+Z pour revenir).</p>
			</div>
			{zones.map((z: Zone) => (
				<div className="card" key={z.start}>
					<h3><span>{fmt(z.start)} → {fmt(z.end)} <small>énergie {Math.round(z.score * 100)} %</small></span>
						<button className="small" onClick={() => seek(z.start)}>▶ Voir</button></h3>
					{z.advice.map((a) => (
						<div className="row advice" key={a.id}>
							<div className="grow"><b>{a.label}</b> <span className="muted">{a.detail}</span></div>
							{a.apply ? (
								<button className="small primary" disabled={done.has(a.id)} onClick={() => { update(a.apply!); setDone(new Set(done).add(a.id)); }}>{done.has(a.id) ? 'Fait' : 'Appliquer'}</button>
							) : (
								<button className="small" onClick={() => { seek(z.start); goto(a.action === 'broll' ? 'ajouter' : 'graphismes'); }}>Ouvrir</button>
							)}
						</div>
					))}
				</div>
			))}
			<div className="card">
				<h3>Faux raccords <small>expérimental</small></h3>
				<p className="muted">À chaque coupe : vêtements, accessoires, lumière, cadre identique (coupe franche). L'IA de vision se trompe encore souvent : ce sont des alertes à vérifier.</p>
				<div className="row">
					<label className="inline"><input type="checkbox" checked={vision} onChange={(e) => setVision(e.target.checked)} /> Vision de l'IA (plus lent, ~1 min)</label>
					<button className="small primary" disabled={job?.status === 'running'} onClick={async () => setJob(await api(`/api/reels/${current}/raccords`, 'POST', {vision}))}>Chercher</button>
					{alerts ? <button className="small" onClick={() => setAlerts(null)}>Effacer</button> : null}
				</div>
				{job?.status === 'running' ? <p className="muted">Comparaison des images de part et d'autre de chaque coupe…</p> : null}
				{job?.status === 'failed' ? <p className="err">{job.error}</p> : null}
			</div>
			{(alerts ?? []).map((a, i) => (
				<div className={`card alert g${a.gravite}`} key={i}>
					<h3><span>Coupe à {fmt(a.t)} <small>{GRAV[a.gravite] ?? ''}</small></span><button className="small" onClick={() => seek(Math.max(0, a.t - 1))}>▶ Voir</button></h3>
					<ul>{a.notes.map((n, k) => <li key={k} className="muted">{n}</li>)}</ul>
				</div>
			))}
			{alerts && !alerts.length ? <p className="ok">Aucun faux raccord détecté.</p> : null}
		</>
	);
};

// Plans de coupe : voir ajouter.tsx (onglet Ajouter : bibliotheque, banques libres, IA par phrase).

// ---------------- Styles de montage : grille (renommer / supprimer mes styles) + « Enregistrer comme mon style » ----------------
/** perso : style cree par l'utilisateur (style par reference ou enregistre depuis une video) : renommable et supprimable. */
export type Template = {id: string; name: string; description: string; perso?: boolean; preview?: string; category?: string};
// champs du reel qui forment son style (envoyes tels qu'affiches : a jour meme avant la sauvegarde automatique)
const STYLE_FIELDS = ['template', 'style', 'zoom', 'banner', 'flash', 'effects', 'emoji', 'progress', 'music', 'sfx', 'aiMode', 'design'] as const;

export const TemplateGrid: React.FC<{templates: Template[]; current?: string; disabled: boolean; className: string; onApply: (t: Template) => void;
	onChanged: () => unknown; children?: React.ReactNode}> = ({templates, current, disabled, className, onApply, onChanged, children}) => {
	const [working, setWorking] = useState(false);
	const [msg, setMsg] = useState('');
	const [err, setErr] = useState('');
	const [category, setCategory] = useState('Tous');
	const categories = ['Tous', ...new Set(templates.map(t=>t.category||'Classiques'))];
	const run = async (fn: () => Promise<string>) => {
		setWorking(true);
		setErr('');
		setMsg('');
		try {
			setMsg(await fn());
			await onChanged();
		} catch (e) {
			setErr((e as Error).message);
		} finally {
			setWorking(false);
		}
	};
	const rename = (t: Template) => {
		const name = window.prompt(`Nouveau nom pour ton style « ${t.name} » :`, t.name);
		if (!name || !name.trim() || name.trim() === t.name) return;
		run(async () => {
			const r: Template = await api(`/api/styles/${encodeURIComponent(t.id)}/renommer`, 'POST', {name});
			return `Style renommé : « ${r.name} ».`;
		});
	};
	const remove = (t: Template) => {
		if (!window.confirm(`Supprimer ton style « ${t.name} » ?\n\nIl sera rangé dans la corbeille (dossier styles\\montage\\_corbeille) : on peut le récupérer.\n`
			+ 'Les vidéos déjà montées avec ce style gardent leur apparence.')) return;
		run(async () => {
			const r: {name: string; sujets: {sujet: string; styleName: string}[]} = await api(`/api/styles/${encodeURIComponent(t.id)}`, 'DELETE');
			return `Style « ${r.name} » mis à la corbeille.${r.sujets.map((s) => ` Les prochaines vidéos « ${s.sujet} » seront montées en « ${s.styleName} ».`).join('')}`;
		});
	};
	return (
		<>
			<div className="gallery-filters" aria-label="Catégories de styles">{categories.map(c=><button key={c} className={`small${c===category?' primary':''}`} onClick={()=>setCategory(c)}>{c}</button>)}</div>
			<div className={className}>
				{templates.filter(t=>category==='Tous'||(t.category||'Classiques')===category).map((t) => (
					<div key={t.id} className="tpl-box">
						<button className={`tpl${current === t.id ? ' on' : ''}`} disabled={disabled || working} onClick={() => onApply(t)} title={t.description}>
							{t.preview ? <img className="tpl-preview" src={`/assets/${t.preview}`} alt={`Aperçu du style ${t.name}`} loading="lazy" /> : null}
							<b>{t.name}{t.perso ? <em className="tag-perso">mon style</em> : null}</b><span>{t.description}</span>
						</button>
						{t.perso ? (
							<div className="tpl-tools">
								<button className="small ghost" disabled={working} onClick={() => rename(t)}>Renommer</button>
								<button className="small ghost" disabled={working} onClick={() => remove(t)}>Supprimer</button>
							</div>
						) : null}
					</div>
				))}
				{children}
			</div>
			{msg ? <p className="ok">{msg}</p> : null}
			{err ? <p className="err">{err}</p> : null}
		</>
	);
};

/** « Enregistrer comme mon style » : les reglages de style de ce reel deviennent un style reutilisable (styles/montage/mon-*.json). */
export const SaveStyleCard: React.FC<{reel: ReelDoc; reelKey: string; templates: Template[]; className?: string; onSaved: (t: Template) => unknown}> = ({reel, reelKey, templates, className, onSaved}) => {
	const [name, setName] = useState('');
	const [busy, setBusy] = useState(false);
	const [msg, setMsg] = useState('');
	const [err, setErr] = useState('');
	const mine = templates.find((t) => t.id === reel.template && t.perso);
	const [project, rid] = reelKey.split('/');
	const save = async (label: string, extra: Record<string, unknown> = {}) => {
		setBusy(true);
		setErr('');
		setMsg('');
		try {
			const body = {project, rid, name: label, reel: Object.fromEntries(STYLE_FIELDS.map((k) => [k, reel[k]])), ...extra};
			let r = await api('/api/styles', 'POST', body);
			if (r.conflict) {
				if (!window.confirm(`Tu as déjà un style « ${r.conflict.name} ».\n\nLe remplacer par les réglages de cette vidéo ?`)) {
					setErr('Rien n\'a été enregistré : choisis un autre nom.');
					return;
				}
				r = await api('/api/styles', 'POST', {...body, replace: r.conflict.id});
			}
			setMsg(`Style « ${r.name} » enregistré. Il est dans la liste des styles ; tu peux le choisir pour un sujet avec 📌.`);
			setName('');
			await onSaved(r);
		} catch (e) {
			setErr((e as Error).message);
		} finally {
			setBusy(false);
		}
	};
	return (
		<div className={className ?? 'card'}>
			<h3>Mon style <small>garder ces réglages pour les prochaines vidéos</small></h3>
			<div className="row">
				<input type="text" className="grow" maxLength={40} placeholder="Nom du style (ex. Mes pubs RyuCalls)" value={name} disabled={busy}
					onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && name.trim() && !busy && save(name)} />
				<button className="small primary" disabled={!name.trim() || busy} onClick={() => save(name)}>{busy ? 'Enregistrement…' : '💾 Enregistrer comme mon style'}</button>
			</div>
			{mine ? (
				<div className="row">
					<button className="small" disabled={busy} onClick={() => save(mine.name, {replace: mine.id})}>Mettre à jour « {mine.name} » avec ces réglages</button>
				</div>
			) : null}
			<p className="muted">Sont gardés : sous-titres, zooms, bandeau, transitions, image, musique, bruitages et mode de l'IA. Pas le montage (prises, coupes).
				{reel.brand ? ` Les couleurs de la charte « ${reel.brand.name} » seront incluses.` : ''}</p>
			{msg ? <p className="ok">{msg}</p> : null}
			{err ? <p className="err">{err}</p> : null}
		</div>
	);
};

// ---------------- Charte client (point 5) ----------------
type ClientDoc = Brand & {style?: {font?: string; color?: string; highlight?: string; stroke?: string}};
export const ClientCard: React.FC<{reel: ReelDoc; update: Update}> = ({reel, update}) => {
	const [clients, setClients] = useState<ClientDoc[]>([]);
	const [edit, setEdit] = useState<(Partial<ClientDoc> & {logoData?: string}) | null>(null);
	const [err, setErr] = useState('');
	const load = () => api('/api/clients').then(setClients).catch(() => undefined);
	useEffect(() => {
		load();
	}, []);
	const apply = (c: ClientDoc | null) =>
		update((r) => {
			if (!c) return {...r, brand: null};
			const {style, ...brand} = c;
			return {...r, brand: {...brand, style}, style: {...r.style, ...Object.fromEntries(Object.entries(style ?? {}).filter(([, v]) => v))}};
		});
	const cur = reel.brand;
	const [msg, setMsg] = useState('');
	const [removing, setRemoving] = useState(false);
	const saved = cur ? clients.find((c) => c.client === cur.client) : undefined;
	/** Supprimer = ranger dans styles/clients/_corbeille (recuperable) ; les videos deja montees gardent leur charte. */
	const remove = async (c: ClientDoc) => {
		if (!window.confirm(`Supprimer la charte « ${c.name} » ?\n\nElle sera rangée dans la corbeille (dossier styles\\clients\\_corbeille) : on peut la récupérer. `
			+ 'Son logo reste dans assets\\clients.\nCette vidéo et celles déjà montées gardent leur logo et leurs couleurs (choisis « Aucune charte » pour l\'enlever d\'ici).')) return;
		setRemoving(true);
		setErr('');
		try {
			const r: {name: string} = await api(`/api/clients/${encodeURIComponent(c.client)}`, 'DELETE');
			await load();
			setEdit(null);
			setMsg(`Charte « ${r.name} » mise à la corbeille : elle n'est plus proposée pour les prochaines vidéos.`);
		} catch (e) {
			setErr((e as Error).message);
		} finally {
			setRemoving(false);
		}
	};
	return (
		<div className="card">
			<h3>Charte client <small>logo, couleurs, police, fin de vidéo</small></h3>
			<div className="row">
				<select className="grow" value={cur?.client ?? ''} onChange={(e) => { setMsg(''); apply(clients.find((c) => c.client === e.target.value) ?? null); }}>
					<option value="">Aucune charte</option>
					{clients.map((c) => <option key={c.client} value={c.client}>{c.name}</option>)}
					{cur && !saved ? <option value={cur.client}>{cur.name} (supprimée)</option> : null}
				</select>
				<button className="small" onClick={() => setEdit(cur ? {...cur} : {name: '', bannerBg: '#FFFFFF', bannerColor: '#0B0B0B', logoPosition: 'haut-droite', logoSize: 0.16, logoOpacity: 0.85,
					style: {font: reel.style.font, color: reel.style.color, highlight: reel.style.highlight, stroke: reel.style.stroke}, outro: {enabled: true, text: '', duration: 2.5}})}>
					{cur ? 'Modifier' : 'Nouvelle charte'}</button>
				{saved ? <button className="small ghost" disabled={removing} onClick={() => remove(saved)} title="Ranger cette charte dans la corbeille">Supprimer</button> : null}
			</div>
			{msg ? <p className="ok">{msg}</p> : null}
			{!edit && err ? <p className="err">{err}</p> : null}
			{cur ? (
				<div className="row">
					<label className="inline"><input type="checkbox" checked={!!cur.outro?.enabled} onChange={(e) => update((r) => ({...r, brand: r.brand && {...r.brand, outro: {...r.brand.outro, enabled: e.target.checked}}}))} /> Carte de fin ({cur.outro?.duration ?? 2.5} s)</label>
					<span className="muted">La charte passe par-dessus le style de montage.</span>
				</div>
			) : null}
			{edit ? (
				<div className="subform">
					<div className="row"><label>Nom du client</label><input type="text" className="grow" value={edit.name ?? ''} onChange={(e) => setEdit({...edit, name: e.target.value})} /></div>
					<div className="row"><label>Logo (PNG, SVG)</label>
						<input type="file" accept="image/png,image/svg+xml,image/webp,image/jpeg" onChange={async (e) => {
							const f = e.target.files?.[0];
							if (!f) return;
							const data = await new Promise<string>((ok) => { const r = new FileReader(); r.onload = () => ok(String(r.result)); r.readAsDataURL(f); });
							setEdit({...edit, logoData: data});
						}} />
						{edit.logoData || edit.logo ? <img className="logo-prev" src={edit.logoData || `/${edit.logo}`} alt="" /> : null}</div>
					<div className="row"><label>Position du logo</label>
						<select value={edit.logoPosition} onChange={(e) => setEdit({...edit, logoPosition: e.target.value as Brand['logoPosition']})}>
							{['haut-gauche', 'haut-droite', 'bas-gauche', 'bas-droite'].map((p) => <option key={p}>{p}</option>)}</select>
						taille <input type="range" min={0.06} max={0.35} step={0.01} style={{width: 90}} value={edit.logoSize ?? 0.16} onChange={(e) => setEdit({...edit, logoSize: Number(e.target.value)})} />
						opacité <input type="range" min={0.2} max={1} step={0.05} style={{width: 90}} value={edit.logoOpacity ?? 0.85} onChange={(e) => setEdit({...edit, logoOpacity: Number(e.target.value)})} /></div>
					<div className="row"><label>Police</label>
						<select className="grow" value={edit.style?.font ?? ''} onChange={(e) => setEdit({...edit, style: {...edit.style, font: e.target.value}})}>{Object.keys(FONT_FILES).map((f) => <option key={f}>{f}</option>)}</select></div>
					<div className="row"><label>Couleurs</label>
						texte <input type="color" value={edit.style?.color ?? '#FFFFFF'} onChange={(e) => setEdit({...edit, style: {...edit.style, color: e.target.value}})} />
						accent <input type="color" value={edit.style?.highlight ?? '#FFD400'} onChange={(e) => setEdit({...edit, style: {...edit.style, highlight: e.target.value}})} />
						contour <input type="color" value={edit.style?.stroke ?? '#000000'} onChange={(e) => setEdit({...edit, style: {...edit.style, stroke: e.target.value}})} /></div>
					<div className="row"><label>Bandeau</label>
						fond <input type="color" value={edit.bannerBg ?? '#FFFFFF'} onChange={(e) => setEdit({...edit, bannerBg: e.target.value})} />
						texte <input type="color" value={edit.bannerColor ?? '#0B0B0B'} onChange={(e) => setEdit({...edit, bannerColor: e.target.value})} /></div>
					<div className="row"><label>Fin de vidéo</label>
						<input type="checkbox" checked={!!edit.outro?.enabled} onChange={(e) => setEdit({...edit, outro: {...(edit.outro ?? {text: '', duration: 2.5}), enabled: e.target.checked}})} />
						<input type="text" className="grow" placeholder="ex. APPELEZ-NOUS AUJOURD'HUI" value={edit.outro?.text ?? ''} onChange={(e) => setEdit({...edit, outro: {...(edit.outro ?? {enabled: true, duration: 2.5}), text: e.target.value}})} /></div>
					<div className="row">
						<button className="small primary" onClick={async () => {
							try {
								const saved: ClientDoc = await api('/api/clients', 'POST', edit);
								await load();
								apply(saved);
								setEdit(null);
								setErr('');
							} catch (e) {
								setErr((e as Error).message);
							}
						}}>Enregistrer et appliquer</button>
						<button className="small" onClick={() => setEdit(null)}>Annuler</button>
						{err ? <span className="err">{err}</span> : null}
					</div>
				</div>
			) : null}
		</div>
	);
};

// ---------------- Declinaisons (point 7) ----------------
export const DeclinaisonsCard: React.FC<{reel: ReelDoc; current: string; onOpen: (rid: string) => void; onAB: (rid: string) => void}> = ({reel, current, onOpen, onAB}) => {
	const [dur, setDur] = useState<number | null>(30);
	const [intent, setIntent] = useState<string | null>(null);
	const [job, setJob] = useJob();
	const total = duration(reel);
	return (
		<div className="card">
			<h3>Déclinaisons <small>nouvelle version à partir de celle-ci</small></h3>
			<div className="row"><label>Durée (actuelle {Math.round(total)} s)</label>
				{[60, 30, 15].map((d) => <button key={d} className={`small${dur === d ? ' primary' : ''}`} disabled={d >= total} onClick={() => setDur(d)}>{d} s</button>)}
				<button className={`small${dur === null ? ' primary' : ''}`} onClick={() => setDur(null)}>garder</button></div>
			<div className="row"><label>Intention</label>
				{[[null, 'aucune'], ['rapide', 'rapide'], ['emotion', 'émotion']].map(([k, l]) => <button key={l} className={`small${intent === k ? ' primary' : ''}`} onClick={() => setIntent(k)}>{l}</button>)}</div>
			<div className="row">
				<button className="small primary" disabled={job?.status === 'running' || (!dur && !intent)} onClick={async () => setJob(await api(`/api/reels/${current}/declinaison`, 'POST', {duree: dur, intention: intent}))}>Créer la déclinaison</button>
				{job?.status === 'running' ? <span className="muted">L'IA classe les phrases par importance…</span> : null}
			</div>
			{job?.status === 'failed' ? <p className="err">{job.error}</p> : null}
			{job?.status === 'done' ? (
				<>
					<p className="ok">« {job.result.label} » créée : {job.result.duree} s{job.result.phrases_coupees.length ? `, ${job.result.phrases_coupees.length} phrase(s) coupée(s)` : ''}.</p>
					{job.result.phrases_coupees.length ? <ul>{job.result.phrases_coupees.map((p: string, i: number) => <li key={i} className="muted">{p}</li>)}</ul> : null}
					{job.result.elements_resume?.length ? <details><summary>Éléments ajustés au nouveau montage</summary><ul>{job.result.elements_resume.map((message: string, i: number) => <li key={i} className="muted">{message}</li>)}</ul></details> : null}
					<div className="row">
						<button className="small primary" onClick={() => onOpen(job.result.rid)}>Ouvrir</button>
						<button className="small" onClick={() => onAB(job.result.rid)}>Comparer A/B</button>
					</div>
					<p className="muted">Les phrases coupées restent barrées dans l'onglet Texte : un clic pour les rétablir.</p>
				</>
			) : null}
		</div>
	);
};

// ---------------- Projets : montage visuel (point 9) + multicamera (point 8) ----------------
export const ProjectTools: React.FC<{reel: ReelDoc; onCreated: (key: string) => void; onReload: () => void}> = ({reel, onCreated, onReload}) => {
	const [folders, setFolders] = useState<string[]>([]);
	const [form, setForm] = useState({dossier: '', type: 'immobilier', titre: '', duree: 30, musique: ''});
	const [job, setJob] = useJob((j) => {
		const name = String(j.result.projet).split(/[\\/]/).pop();
		onCreated(`${name}/script`);
	});
	const [sync, setSync] = useJob(() => onReload());
	useEffect(() => {
		api('/api/media-folders').then((f: string[]) => {
			setFolders(f);
			setForm((x) => ({...x, dossier: x.dossier || f[0] || ''}));
		}).catch(() => undefined);
	}, []);
	const groups = new Set(Object.values(reel.sources).map((s) => s.sync?.group).filter(Boolean));
	return (
		<>
			<div className="card">
				<h3>Multicaméra <small>podcast, conférence</small></h3>
				<p className="muted">Aligne par le son les prises filmées en même temps par plusieurs caméras. Ensuite, dans l'onglet Plan : choix de l'angle de chaque plan (ou automatique selon qui parle).</p>
				<div className="row">
					<button className="small primary" disabled={sync?.status === 'running'} onClick={async () => setSync(await api(`/api/projects/${reel.project}/multicam`, 'POST', {}))}>Synchroniser les caméras</button>
					{groups.size ? <span className="ok">{groups.size} groupe(s) synchronisé(s)</span> : null}
					{sync?.status === 'running' ? <span className="muted">Comparaison des sons…</span> : null}
					{sync?.status === 'done' ? <span className="muted">{sync.result.groupes.length ? `${sync.result.groupes.length} groupe(s) trouvé(s).` : 'Aucune prise filmée en même temps.'}</span> : null}
					{sync?.status === 'failed' ? <span className="err">{sync.error}</span> : null}
				</div>
			</div>
			<div className="card">
				<h3>Nouveau montage visuel <small>sans parole, calé sur la musique</small></h3>
				<div className="row"><label>Dossier de vidéos</label>
					<select className="grow" value={form.dossier} onChange={(e) => setForm({...form, dossier: e.target.value})}>{folders.map((f) => <option key={f}>{f}</option>)}</select></div>
				<div className="row"><label>Type</label>
					{[['immobilier', 'Immobilier'], ['evenement', 'Événement']].map(([k, l]) => <button key={k} className={`small${form.type === k ? ' primary' : ''}`} onClick={() => setForm({...form, type: k})}>{l}</button>)}</div>
				<div className="row"><label>Titre / adresse</label><input type="text" className="grow" value={form.titre} placeholder="ex. 1234 rue des Érables, Laval" onChange={(e) => setForm({...form, titre: e.target.value})} /></div>
				<div className="row"><label>Durée</label>{[15, 30, 45, 60].map((d) => <button key={d} className={`small${form.duree === d ? ' primary' : ''}`} onClick={() => setForm({...form, duree: d})}>{d} s</button>)}</div>
				<div className="row">
					<button className="small primary" disabled={!form.dossier || job?.status === 'running'} onClick={async () => setJob(await api('/api/visuel', 'POST', form))}>Monter</button>
					{job?.status === 'running' ? <span className="muted">{job.stage}… (stabilisation et analyse : quelques minutes)</span> : null}
					{job?.status === 'failed' ? <span className="err">{job.error}</span> : null}
				</div>
				<p className="muted">Immobilier : stabilisation, pièces reconnues et mises dans l'ordre d'une visite, coupes sur les temps de la musique. Événement : meilleurs moments + citations de l'orateur.</p>
			</div>
		</>
	);
};

// ---------------- Export : formats + file d'attente (points 1 et 2) ----------------
export const ExportPanel: React.FC<{reel: ReelDoc; current: string; busy: boolean}> = ({reel, current, busy}) => {
	const [formats, setFormats] = useState<string[]>([formatOf(reel)]);
	const [queue, setQueue] = useState<Job[]>([]);
	const [ex, setEx] = useJob();
	const [err, setErr] = useState('');
	const refresh = () => api('/api/queue').then(setQueue).catch(() => undefined);
	useEffect(() => {
		refresh();
		const id = window.setInterval(refresh, 1500);
		return () => window.clearInterval(id);
	}, []);
	const toggle = (f: string) => setFormats(formats.includes(f) ? formats.filter((x) => x !== f) : [...formats, f]);
	const STATUS: Record<string, string> = {queued: 'en attente', running: 'en cours', done: 'terminé', failed: 'échec', cancelled: 'annulé'};
	return (
		<>
			<div className="card export-box">
				<h3 style={{justifyContent: 'center'}}>{reel.title} - FINAL.mp4</h3>
				<p className="muted">Sous-titres, zooms, couleur harmonisée, voix traitée, musique, bruitages, plans de coupe, graphismes. Le cadre suit la personne dans chaque format.</p>
				<div className="row" style={{justifyContent: 'center'}}>
					{Object.keys(FORMATS).map((f) => <label key={f} className="inline fmt"><input type="checkbox" checked={formats.includes(f)} onChange={() => toggle(f)} /> {f}</label>)}
				</div>
				<button className="primary" disabled={busy || !formats.length} onClick={async () => {
					try {
						await api(`/api/reels/${current}/export`, 'POST', {formats});
						setErr('');
						refresh();
					} catch (e) {
						setErr((e as Error).message);
					}
				}}>Ajouter à la file d'export ({formats.length})</button>
				<p className="muted">Les exports passent un par un ; tu peux continuer à travailler (et changer de reel) pendant ce temps.</p>
				{err ? <p className="err">{err}</p> : null}
			</div>
			<div className="card">
				<h3>File d'export <small>{queue.filter((j) => j.status === 'queued' || j.status === 'running').length} en cours / en attente</small></h3>
				{queue.map((j) => (
					<div key={j.id} className="qjob">
						<div className="row" style={{margin: 0}}>
							<b className="grow">{j.title}</b>
							<span className={`st ${j.status}`}>{STATUS[j.status] ?? j.status}{j.status === 'done' ? ` (${j.seconds} s)` : ''}</span>
							{j.status === 'queued' || j.status === 'running' ? <button className="small" onClick={() => api(`/api/jobs/${j.id}/cancel`, 'POST').then(refresh)}>Annuler</button> : null}
							{j.status === 'done' ? <button className="small" onClick={() => api('/api/open-folder', 'POST', {file: j.result.out})}>Dossier</button> : null}
						</div>
						{j.status === 'running' ? <><div className="bar"><div style={{width: `${Math.round(j.progress * 100)}%`}} /></div><div className="muted">{j.stage} — {Math.round(j.progress * 100)} %</div></> : null}
						{j.status === 'failed' ? <p className="err">{j.error}</p> : null}
					</div>
				))}
				{!queue.length ? <p className="muted">Aucun export pour l'instant.</p> : null}
			</div>
			<div className="card export-box">
				<h3 style={{justifyContent: 'center'}}>Finir dans DaVinci Resolve / Premiere</h3>
				<p className="muted">Montage (pistes image, voix avec J/L-cuts, musique, bruitages, marqueurs) en .otio, .xml et .fcpxml + sous-titres .srt.</p>
				<div className="row" style={{justifyContent: 'center'}}>
					<button className="primary" disabled={ex?.status === 'running'} onClick={async () => setEx(await api(`/api/reels/${current}/echange`, 'POST'))}>Exporter pour Resolve</button>
					<button onClick={() => api('/api/open-resolve', 'POST')}>Ouvrir DaVinci Resolve</button>
				</div>
				{ex?.status === 'running' ? <p className="muted">{ex.stage}…</p> : null}
				{ex?.status === 'done' ? (
					<>
						<p className="ok">{ex.result.fichiers.join(', ')} + sous-titres.srt</p>
						<p className="muted">Dans Resolve : Fichier › Importer › Timeline › montage.otio</p>
						<button onClick={() => api('/api/open-folder', 'POST', {file: ex.result.dossier})}>Ouvrir le dossier</button>
					</>
				) : null}
				{ex?.status === 'failed' ? <p className="err">{ex.error}</p> : null}
			</div>
		</>
	);
};
