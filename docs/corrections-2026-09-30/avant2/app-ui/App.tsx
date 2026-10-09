import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Player, type PlayerRef} from '@remotion/player';
import {Reel} from '../../remotion/src/Reel';
import {duration} from '../../remotion/src/timeline';
import {FORMATS, formatOf, type ReelDoc, type Source} from '../../remotion/src/types';
import {api, fmt, useJob} from './api';
import {clipPatch, moveClip, setTake, setWords, trim, type RawWord, type TakeOption} from './edit';
import {Compare, PlanPanel, SearchPanel, StylePanel, TextPanel, VersionsPanel} from './panels';
import {ConseilsPanel, ExportPanel, GraphicsPanel, type Alert, type Template} from './panels2';
import {AjouterPanel, useAddMedia} from './ajouter';
import {Revision} from './revision';
import {Timeline} from './Timeline';

type ReelItem = {project: string; rid: string; label: string; opened: boolean};
type Opened = {reel: ReelDoc; takes: Record<string, TakeOption[]>; blocks: Record<string, string>; mode: string};
type Tab = 'plan' | 'texte' | 'style' | 'ajouter' | 'graphismes' | 'rushs' | 'conseils' | 'versions' | 'export';
const TABS: Record<Tab, string> = {plan: 'Plan', texte: 'Texte', style: 'Style', ajouter: 'Ajouter', graphismes: 'Graphismes', rushs: 'Rushs', conseils: 'Conseils', versions: 'Versions', export: 'Export'};
// onglets du quotidien ; le reste (reglages de monteur) est range dans « Plus »
const MAIN_TABS: Tab[] = ['texte', 'style', 'ajouter'];
const MORE_TABS: Tab[] = ['plan', 'graphismes', 'rushs', 'conseils', 'versions', 'export'];
const EDITABLE = ['style', 'zoom', 'banner', 'flash', 'progress', 'effects', 'emoji', 'music', 'sfx', 'audio', 'intro', 'clips',
	'broll', 'graphics', 'brand', 'aiMode', 'suggestions', 'label', 'design', 'styleScenes'] as const;

const App: React.FC = () => {
	const [items, setItems] = useState<ReelItem[]>([]);
	const [current, setCurrent] = useState('');
	const [data, setData] = useState<Opened | null>(null);
	const [busy, setBusy] = useState('');
	const [error, setError] = useState('');
	const [tab, setTab] = useState<Tab>('texte');
	const [view, setView] = useState<'revision' | 'edition'>('revision');
	const [more, setMore] = useState(false);
	const [templates, setTemplates] = useState<Template[]>([]);
	const [frame, setFrame] = useState(0);
	const [selected, setSelected] = useState<string | null>(null);
	const [compare, setCompare] = useState(false);
	const [ab, setAb] = useState<{file: string; label: string; reel: ReelDoc; showB: boolean} | null>(null);
	const [alerts, setAlerts] = useState<Alert[] | null>(null);
	const [, force] = useState(0);
	const transcripts = useRef(new Map<string, RawWord[]>());
	const undo = useRef<ReelDoc[]>([]);
	const redo = useRef<ReelDoc[]>([]);
	const player = useRef<PlayerRef>(null);
	const saveTimer = useRef<number | undefined>(undefined);

	const refreshItems = useCallback(() => api('/api/reels').then((list: ReelItem[]) => {
		setItems(list);
		return list;
	}), []);
	/** Liste des styles de montage (les miens compris) : relue apres un ajout, un renommage ou une suppression. */
	const refreshTemplates = useCallback(() => api('/api/styles').then((s) => setTemplates(s.montage)).catch(() => undefined), []);
	useEffect(() => {
		refreshItems().then((list) => {
			const wanted = list.find((i) => i.rid === 'v1') ?? list[0];
			if (wanted) setCurrent((c) => c || `${wanted.project}/${wanted.rid}`);
		}).catch((e) => setError(e.message));
		refreshTemplates();
	}, [refreshItems, refreshTemplates]);

	const load = useCallback(async (key: string, action = 'open', body?: unknown, label = 'Ouverture du reel…') => {
		setBusy(label);
		setError('');
		try {
			const d: Opened = await api(`/api/reels/${key}/${action}`, action === 'open' && body === 'rapide' ? 'GET' : 'POST', body === 'rapide' ? undefined : body);
			setData(d);
			setSelected((s) => (s && d.reel.clips.some((c) => c.id === s) ? s : d.reel.clips[0]?.id ?? null));
			undo.current = [];
			redo.current = [];
			setAb(null);
			setAlerts(null);
		} catch (e) {
			setError((e as Error).message);
		} finally {
			setBusy('');
		}
	}, []);
	// l'editeur ne charge un reel que lorsqu'on l'ouvre (« Modifier ») : la Revision a son propre lecteur
	useEffect(() => {
		if (!current || view !== 'edition') return;
		const it = items.find((i) => `${i.project}/${i.rid}` === current);
		load(current, 'open', it?.opened === false ? undefined : 'rapide'); // reel jamais ouvert : le moteur le cree
	}, [current, load, view]);

	const reel = data?.reel;
	const fps = reel?.fps ?? 30;
	const t = frame / fps;
	const total = useMemo(() => (reel ? duration(reel) : 1), [reel]);

	const save = useCallback((next: ReelDoc) => {
		window.clearTimeout(saveTimer.current);
		saveTimer.current = window.setTimeout(() => {
			api(`/api/reels/${current}`, 'PUT', {...Object.fromEntries(EDITABLE.map((k) => [k, next[k]])), format: formatOf(next)}).catch((e) => setError(e.message));
		}, 350);
	}, [current]);

	/** Toute modification : historique (Ctrl+Z) + sauvegarde automatique. Instantane : aucun recalcul video. */
	const update = useCallback((fn: (r: ReelDoc) => ReelDoc) => {
		setData((d) => {
			if (!d) return d;
			undo.current.push(d.reel);
			if (undo.current.length > 200) undo.current.shift();
			redo.current = [];
			const next = fn(d.reel);
			save(next);
			return {...d, reel: next};
		});
	}, [save]);

	const history = useCallback((from: React.MutableRefObject<ReelDoc[]>, to: React.MutableRefObject<ReelDoc[]>) => {
		setData((d) => {
			const prev = from.current.pop();
			if (!d || !prev) return d;
			to.current.push(d.reel);
			// les sources (plans de coupe ajoutes par le moteur) ne font que s'ajouter : annuler ne les retire pas
			const merged = {...prev, sources: {...prev.sources, ...d.reel.sources}};
			save(merged);
			return {...d, reel: merged};
		});
	}, [save]);

	const transcript = useCallback(async (source: string) => {
		if (!transcripts.current.has(source) && reel) transcripts.current.set(source, await api(`/api/transcript/${reel.project}/${source}`));
		return transcripts.current.get(source);
	}, [reel]);
	useEffect(() => {
		reel?.clips.forEach((c) => transcript(c.source).catch(() => undefined));
	}, [reel?.id]);

	const seek = (s: number) => player.current?.seekTo(Math.max(0, Math.round(s * fps)));
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			const el = e.target as HTMLElement;
			if (el?.tagName === 'INPUT' || el?.tagName === 'TEXTAREA' || el?.tagName === 'SELECT') return;
			if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
				e.preventDefault();
				e.shiftKey ? history(redo, undo) : history(undo, redo);
				force((n) => n + 1);
			} else if (e.key === ' ') {
				e.preventDefault();
				player.current?.toggle();
			} else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
				e.preventDefault();
				const step = (e.shiftKey ? fps : 1) * (e.key === 'ArrowLeft' ? -1 : 1);
				player.current?.seekTo(Math.max(0, (player.current?.getCurrentFrame() ?? 0) + step));
			}
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	}, [history, fps]);

	useEffect(() => {
		const p = player.current;
		if (!p) return;
		const onFrame = (e: {detail: {frame: number}}) => setFrame(e.detail.frame);
		p.addEventListener('frameupdate', onFrame);
		return () => p.removeEventListener('frameupdate', onFrame);
	}, [reel?.id, data]);

	const shown = ab?.showB ? ab.reel : reel;
	const inputProps = useMemo(() => (shown ? {reel: shown, mediaBase: '', assetBase: '/assets', audio: 'preview' as const} : null), [shown]);
	const shownTotal = useMemo(() => (shown ? duration(shown) : 1), [shown]);
	const clip = reel?.clips.find((c) => c.id === selected) ?? null;
	const takes = (clip && data?.takes[clip.id]) || [];

	const doTrim = async (id: string, side: 'in' | 'out', d: number) => {
		const c = reel?.clips.find((k) => k.id === id);
		if (!c) return;
		const words = await transcript(c.source);
		update((r) => trim(r, id, side, d, words));
	};

	/** Relit le reel tel que le moteur l'a modifie (angles, plans de coupe...), sans relancer le moteur. */
	const reload = useCallback(() => load(current, 'open', 'rapide', 'Mise à jour du reel…'), [current, load]);
	const [anglesJob, setAnglesJob] = useJob(() => reload());
	/** Nouvelles sources ajoutees par le moteur (plans de coupe) : deja enregistrees dans le reel cote serveur. */
	const addSources = useCallback((s: Record<string, Source>) => setData((d) => (d ? {...d, reel: {...d.reel, sources: {...d.reel.sources, ...s}}} : d)), []);
	// taches suivies ici (toujours monte) : quitter l'onglet ou changer de video ne perd pas un resultat
	const adder = useAddMedia(current, addSources, update);
	const brollKey = useRef('');
	const currentRef = useRef(current);
	currentRef.current = current;
	const [brollJob, setBrollJob] = useJob(() => {
		if (brollKey.current === currentRef.current) reload();
	});
	const onAutoBroll = async (opts: {tout: boolean; banques: boolean}) => {
		brollKey.current = current;
		try {
			setBrollJob(await api(`/api/reels/${current}/broll`, 'POST', {...opts, auto: true}));
		} catch (e) {
			setError((e as Error).message);
		}
	};
	const openEditor = (key: string) => {
		setCurrent(key);
		setView('edition');
		refreshItems();
	};
	const openReel = async (rid: string) => {
		await refreshItems();
		setCurrent(`${reel?.project}/${rid}`);
	};
	const abReel = async (rid: string) => {
		const d: Opened = await api(`/api/reels/${reel?.project}/${rid}/open`);
		setAb({file: rid, label: d.reel.label ?? rid, reel: d.reel, showB: true});
	};
	const format = reel ? formatOf(reel) : '9:16';
	// une video glissee dans l'editeur ne fait jamais quitter la page : on passe a la Revision pour la deposer
	useEffect(() => {
		if (view !== 'edition') return;
		const over = (e: DragEvent) => e.dataTransfer?.types.includes('Files') && e.preventDefault();
		const drop = (e: DragEvent) => {
			if (!e.dataTransfer?.types.includes('Files')) return;
			e.preventDefault();
			setView('revision');
		};
		window.addEventListener('dragover', over);
		window.addEventListener('drop', drop);
		return () => {
			window.removeEventListener('dragover', over);
			window.removeEventListener('drop', drop);
		};
	}, [view]);

	if (view === 'revision') {
		return (
			<div className="app rv-app">
				<header>
					<h1>Éditeur <span>Sami</span></h1>
					<span className="muted">Dépose tes vidéos brutes : l'outil les monte seul. Tu regardes, tu prends ou tu modifies.</span>
					<div className="grow" />
					<button className="small" onClick={() => setView('edition')} title="Ouvrir l'éditeur complet sur le dernier montage">Éditeur complet</button>
				</header>
				<Revision onEdit={openEditor} templates={templates} onTemplates={refreshTemplates} />
			</div>
		);
	}

	return (
		<div className="app">
			<header>
				<button className="small" onClick={() => { setView('revision'); refreshItems(); refreshTemplates(); }} title="Retour à la liste des vidéos">← Révision</button>
				<h1>Éditeur <span>Sami</span></h1>
				<select value={current} onChange={(e) => setCurrent(e.target.value)}>
					{items.map((i) => <option key={`${i.project}/${i.rid}`} value={`${i.project}/${i.rid}`}>{i.label}</option>)}
				</select>
				{data?.mode && data.mode !== 'script' ? <span className="tag">{data.mode}</span> : null}
				{reel ? (
					<div className="formats" title="Format de l'image : aperçu instantané, le cadre suit la personne">
						{Object.entries(FORMATS).map(([f, [w, h]]) => (
							<button key={f} className={`small${format === f ? ' primary' : ''}`} onClick={() => update((r) => ({...r, width: w, height: h}))}>{f}</button>
						))}
					</div>
				) : null}
				<div className="grow" />
				{ab ? (
					<button className={`small${ab.showB ? ' primary' : ''}`} onClick={() => setAb({...ab, showB: !ab.showB})} title="Basculer entre le montage actuel (A) et la version choisie (B)">
						{ab.showB ? `B : ${ab.label}` : 'A : montage actuel'} ⇄
					</button>
				) : null}
				{ab ? <button className="small" onClick={() => setAb(null)} title="Fin de la comparaison">✕</button> : null}
				<button className="small" disabled={!undo.current.length} onClick={() => { history(undo, redo); force((n) => n + 1); }} title="Ctrl+Z">↶ Annuler</button>
				<button className="small" disabled={!redo.current.length} onClick={() => { history(redo, undo); force((n) => n + 1); }} title="Ctrl+Maj+Z">↷ Rétablir</button>
				<button className="primary" disabled={!reel || !!busy} onClick={() => setTab('export')}>Exporter</button>
			</header>
			<div className="main">
				<section className="stage">
					{busy ? <div className="busy"><div className="spinner" /><div>{busy}</div></div> : null}
					{shown && inputProps ? (
						<>
							<div className="player-wrap" style={{aspectRatio: `${shown.width} / ${shown.height}`}}>
								<Player ref={player} component={Reel} inputProps={inputProps} durationInFrames={Math.max(1, Math.round(shownTotal * fps))} fps={fps}
									compositionWidth={shown.width} compositionHeight={shown.height} style={{width: '100%', height: '100%'}}
									controls clickToPlay bufferStateDelayInMilliseconds={200} acknowledgeRemotionLicense />
							</div>
							<div className="transport">
								<button className="small" onClick={() => seek(t - 1)}>−1 s</button>
								<span>{fmt(t)} / {fmt(shownTotal)}</span>
								<button className="small" onClick={() => seek(t + 1)}>+1 s</button>
								<span className="muted"><kbd>Espace</kbd> lecture · <kbd>←→</kbd> image · <kbd>Ctrl+Z</kbd> annuler</span>
							</div>
						</>
					) : <div className="empty">{error || 'Chargement…'}</div>}
					{error && reel ? <div className="err">{error}</div> : null}
				</section>
				<aside>
					<div className="tabs">
						{MAIN_TABS.map((k) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => { setTab(k); setMore(false); }}>{TABS[k]}</button>)}
						<button className={MORE_TABS.includes(tab) ? 'on' : ''} onClick={() => setMore(!more)} title="Réglages de monteur">
							{MORE_TABS.includes(tab) ? `Plus : ${TABS[tab]}` : 'Plus'} ▾
						</button>
					</div>
					{more ? (
						<div className="tabs more">
							{MORE_TABS.map((k) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => { setTab(k); setMore(false); }}>{TABS[k]}</button>)}
						</div>
					) : null}
					<div className="panel">
						{reel && data && tab === 'plan' ? (
							<PlanPanel reel={reel} clip={clip} takes={takes} blocks={data.blocks} t={t} seek={seek}
								onTake={(i) => clip && update((r) => setTake(r, clip.id, takes[i], i))}
								onTrim={(side, d) => clip && doTrim(clip.id, side, d)}
								onPatch={(p) => clip && update((r) => clipPatch(r, clip.id, p))}
								onMove={(dir) => {
									const i = reel.clips.findIndex((c) => c.id === selected);
									if (i >= 0) update((r) => moveClip(r, i, i + dir));
								}}
								onCompare={() => setCompare(true)}
								anglesBusy={anglesJob?.status === 'running'}
								onAutoAngles={async () => setAnglesJob(await api(`/api/reels/${current}/angles`, 'POST', {}))} />
						) : null}
						{reel && data && tab === 'texte' ? <TextPanel reel={reel} blocks={data.blocks} t={t} seek={seek} update={update} current={current}
							onWords={(c, idx, p) => update((r) => setWords(r, c, idx, p))} /> : null}
						{reel && tab === 'style' ? <StylePanel reel={reel} update={update} t={t} total={total} busy={!!busy} current={current}
							onTemplate={(id) => load(current, 'template', {id}, 'Application du style de montage…')} onStylesChanged={refreshTemplates} /> : null}
						{reel && tab === 'ajouter' ? <AjouterPanel key={current} reel={reel} update={update} t={t} seek={seek} current={current} addSources={addSources}
							adder={adder} autoJob={brollKey.current === current ? brollJob : null} onAutoBroll={onAutoBroll} /> : null}
						{reel && tab === 'graphismes' ? <GraphicsPanel reel={reel} update={update} t={t} seek={seek} current={current} /> : null}
						{reel && tab === 'rushs' ? <SearchPanel key={current} reel={reel} update={update} t={t} seek={seek} current={current} addSources={addSources}
							onCreated={async (key) => { await refreshItems(); setCurrent(key); }} onReload={reload} /> : null}
						{reel && tab === 'conseils' ? <ConseilsPanel reel={reel} update={update} seek={seek} current={current} alerts={alerts} setAlerts={setAlerts} goto={setTab} /> : null}
						{reel && tab === 'versions' ? (
							<VersionsPanel reel={reel} current={current} abFile={ab?.file ?? null}
								onRestore={(file) => load(current, 'restore', {file}, 'Restauration de la version…')}
								onAB={async (file) => setAb(file ? {file, label: file.slice(20, -5), reel: await api(`/api/reels/${current}/version?file=${encodeURIComponent(file)}`), showB: true} : null)}
								onOpenReel={openReel} onABReel={abReel} />
						) : null}
						{reel && tab === 'export' ? <ExportPanel reel={reel} current={current} busy={!!busy} /> : null}
					</div>
				</aside>
			</div>
			{reel && data ? (
				<Timeline reel={reel} t={t} selected={selected} blocks={data.blocks} onSeek={seek}
					onSelect={(id) => { setSelected(id); if (tab !== 'plan' && tab !== 'texte') setTab('plan'); }}
					onMove={(from, to) => update((r) => moveClip(r, from, to))}
					onTrim={doTrim}
					onJL={(id, key, value) => update((r) => clipPatch(r, id, {[key]: value}))}
					onItemMove={(kind, id, at) => update((r) => (kind === 'broll'
						? {...r, broll: (r.broll ?? []).map((b) => (b.id === id ? {...b, at} : b))}
						: {...r, graphics: (r.graphics ?? []).map((g) => (g.id === id ? {...g, at} : g))}))}
					alerts={alerts} onAdvice={(s) => { seek(s); setTab('conseils'); }} />
			) : null}
			{compare && clip && reel ? (
				<Compare takes={takes} current={clip.choice ?? 0}
					proxy={(source) => `/${reel.sources[source]?.proxy}`}
					onChoose={(i) => { update((r) => setTake(r, clip.id, takes[i], i)); setCompare(false); }}
					onClose={() => setCompare(false)} />
			) : null}
		</div>
	);
};

createRoot(document.getElementById('root')!).render(<App />);
