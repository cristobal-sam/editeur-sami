// Ecran « Revision » (par defaut) : on depose des videos brutes, l'outil les monte seul (sujet -> style adapte),
// on regarde : « Je la prends » (export), « Modifier » (editeur complet) ou « Autre style ».
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Player} from '@remotion/player';
import {Reel} from '../../remotion/src/Reel';
import {duration} from '../../remotion/src/timeline';
import {FORMATS, formatOf, type ReelDoc} from '../../remotion/src/types';
import {api, fmt, useJob} from './api';
import {SaveStyleCard, TemplateGrid, type Template} from './panels2';

/** Un export par format coche dans « Je la prends ». interrompu = l'editeur a redemarre pendant l'export. */
export type ItemExport = {format: string; job: string; out: string; status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'interrompu';
	progress?: number; stage?: string; error?: string | null; seconds?: number | null};
export type Item = {
	id: string; unit: string; lot: string; name: string; status: 'attente' | 'travail' | 'pret' | 'pris' | 'erreur';
	stage: string; progress: number; project?: string; rid?: string; type?: string; typeLabel?: string; title?: string;
	reason?: string; style?: string; broll?: number; error?: string | null; exports?: ItemExport[];
	previousStyleVersion?: string | null;
	alerts?: string[]; ia?: boolean; updated?: number;
	taken?: {out: string; outs?: string[]; formats?: string[]; date: number} | null;
};
type State = {items: Item[]; lots: Record<string, {client?: string | null}>; entree: string; corbeille?: string; busy: boolean};
type Opened = {reel: ReelDoc};
/** Resultat d'une suppression (le serveur range le montage et les videos brutes dans la corbeille de l'editeur). */
type Deleted = {id: string; titre: string; corbeille: string | null; deplaces: string[]; gardes: string[]; livraisons: string[]};

const ALLOWED = /\.(mp4|mov|m4v|mkv|avi|mts|webm|docx|txt|pdf)$/i;
const STATUS: Record<Item['status'], string> = {attente: 'En file', travail: 'Montage…', pret: 'À regarder', pris: 'Prise ✓', erreur: 'Erreur'};
const FORMAT_NAMES: Record<string, string> = {'9:16': 'vertical (Reels, TikTok)', '16:9': 'horizontal (YouTube)', '4:5': 'publication (fil)', '1:1': 'carré'};
const EXPORT_STATUS: Record<ItemExport['status'], string> = {queued: 'en attente', running: 'en cours', done: 'terminé ✓', failed: 'échec', cancelled: 'annulé',
	interrompu: 'interrompu'};
const running = (e: ItemExport) => e.status === 'queued' || e.status === 'running';
/** Pourquoi une video ne peut pas etre supprimee maintenant ('' = possible). */
const deleteBlock = (i: Item) => (i.status === 'travail' ? 'Montage en cours : attends la fin pour la supprimer.'
	: (i.exports ?? []).some(running) ? 'Export en cours : annule-le d\'abord (bouton « Annuler »), puis supprime-la.' : '');
const winPath = (p: string) => p.replace(/\//g, '\\');

/** Formats coches la derniere fois (propres a ce navigateur ; 9:16 si rien n'est garde ou si le stockage est bloque). */
const FORMATS_KEY = 'revision.formats';
const loadFormats = (): string[] => {
	try {
		const v = JSON.parse(window.localStorage.getItem(FORMATS_KEY) || 'null');
		if (Array.isArray(v) && v.length && v.every((f) => typeof f === 'string' && FORMATS[f])) return v;
	} catch {}
	return ['9:16'];
};
const storeFormats = (list: string[]) => {
	try {
		window.localStorage.setItem(FORMATS_KEY, JSON.stringify(list));
	} catch {}
};

/** Fichiers deposes (y compris des dossiers entiers : on garde leur chemin relatif). */
const readDrop = async (dt: DataTransfer): Promise<{file: File; rel: string}[]> => {
	const out: {file: File; rel: string}[] = [];
	const walk = async (entry: any, prefix: string): Promise<void> => {
		if (entry.isFile) {
			const file: File = await new Promise((res, rej) => entry.file(res, rej));
			out.push({file, rel: prefix + file.name});
		} else if (entry.isDirectory) {
			const reader = entry.createReader();
			let batch: any[] = [];
			do {
				batch = await new Promise((res, rej) => reader.readEntries(res, rej));
				for (const e of batch) await walk(e, `${prefix}${entry.name}/`);
			} while (batch.length);
		}
	};
	const entries = [...dt.items].map((i) => (i as any).webkitGetAsEntry?.()).filter(Boolean);
	if (entries.length) for (const e of entries) await walk(e, '');
	else [...dt.files].forEach((file) => out.push({file, rel: file.name}));
	return out;
};

const Uploader: React.FC<{onDone: () => void}> = ({onDone}) => {
	const [clients, setClients] = useState<{client: string; name: string}[]>([]);
	const [client, setClient] = useState('');
	const [progress, setProgress] = useState<{done: number; total: number; skipped: number} | null>(null);
	const [err, setErr] = useState('');
	const [over, setOver] = useState(false);
	const files = useRef<HTMLInputElement>(null);
	const folder = useRef<HTMLInputElement>(null);
	useEffect(() => {
		api('/api/clients').then(setClients).catch(() => undefined);
	}, []);
	const send = useCallback(async (list: {file: File; rel: string}[]) => {
		const ok = list.filter((f) => ALLOWED.test(f.rel) && !f.rel.split('/').some((s) => s.startsWith('.')));
		if (!ok.length) return setErr('Aucune vidéo dans ce dépôt (formats acceptés : mp4, mov, mkv, avi, webm ; scripts .docx, .txt ou .pdf).');
		setErr('');
		setProgress({done: 0, total: ok.length, skipped: list.length - ok.length});
		try {
			const {lot} = await api('/api/entree/lot', 'POST', {client: client || null});
			for (let k = 0; k < ok.length; k++) {
				const rel = ok[k].rel.split('/').map(encodeURIComponent).join('/');
				const r = await fetch(`/api/entree/${encodeURIComponent(lot)}/${rel}`, {method: 'PUT', body: ok[k].file});
				if (!r.ok) throw new Error((await r.json()).error || `Erreur ${r.status}`);
				setProgress({done: k + 1, total: ok.length, skipped: list.length - ok.length});
			}
			await api(`/api/entree/${encodeURIComponent(lot)}/fin`, 'POST', {});
			onDone();
		} catch (e) {
			setErr((e as Error).message);
		} finally {
			setProgress(null);
		}
	}, [client, onDone]);
	useEffect(() => {
		const enter = (e: DragEvent) => {
			if (e.dataTransfer?.types.includes('Files')) {
				e.preventDefault();
				setOver(true);
			}
		};
		const drop = async (e: DragEvent) => {
			if (!e.dataTransfer?.types.includes('Files')) return;
			e.preventDefault();
			setOver(false);
			send(await readDrop(e.dataTransfer));
		};
		window.addEventListener('dragover', enter);
		window.addEventListener('drop', drop);
		return () => {
			window.removeEventListener('dragover', enter);
			window.removeEventListener('drop', drop);
		};
	}, [send]);
	const pick = (input: HTMLInputElement | null) => {
		const list = [...(input?.files ?? [])].map((file) => ({file, rel: (file as any).webkitRelativePath || file.name}));
		if (input) input.value = '';
		if (list.length) send(list);
	};
	return (
		<div className="import">
			<b>Ajouter des vidéos brutes</b>
			<p className="muted">Glisse tes vidéos ici (ou un dossier). Une vidéo seule = une vidéo à monter ; un dossier = plusieurs prises
				d'une même vidéo, avec son script si tu en as un. L'outil trouve le sujet et monte tout seul.</p>
			<div className="row">
				<button className="primary" disabled={!!progress} onClick={() => files.current?.click()}>Choisir des vidéos</button>
				<button disabled={!!progress} onClick={() => folder.current?.click()}>Choisir un dossier</button>
				<select value={client} onChange={(e) => setClient(e.target.value)} title="Charte du client (logo, couleurs) appliquée à ces vidéos">
					<option value="">Sans charte client</option>
					{clients.map((c) => <option key={c.client} value={c.client}>{c.name}</option>)}
				</select>
			</div>
			<input ref={files} type="file" multiple accept="video/*,.docx,.txt,.pdf" hidden onChange={(e) => pick(e.currentTarget)} />
			<input ref={folder} type="file" hidden onChange={(e) => pick(e.currentTarget)} {...{webkitdirectory: '', directory: ''}} />
			{progress ? (
				<div className="upload">
					Envoi {progress.done}/{progress.total}{progress.skipped ? ` (${progress.skipped} fichier(s) ignoré(s))` : ''}
					<div className="bar"><div style={{width: `${(100 * progress.done) / progress.total}%`}} /></div>
				</div>
			) : null}
			{err ? <p className="err">{err}</p> : null}
			{over ? <div className="dropzone" onDragLeave={() => setOver(false)}><div>Dépose tes vidéos ici</div></div> : null}
		</div>
	);
};

/** « Style depuis une video » : on depose un reel deja monte ; l'outil en mesure le style et le cree. */
const ReferenceCard: React.FC<{onCreated: (id: string) => void}> = ({onCreated}) => {
	const input = useRef<HTMLInputElement>(null);
	const [sending, setSending] = useState(false);
	const [err, setErr] = useState('');
	const [job, setJob] = useJob((j) => onCreated(j.result.id));
	const pick = async (file?: File) => {
		if (!file) return;
		setErr('');
		setSending(true);
		try {
			const r = await fetch(`/api/references/${encodeURIComponent(file.name)}`, {method: 'PUT', body: file});
			const d = await r.json();
			if (!r.ok) throw new Error(d.error || `Erreur ${r.status}`);
			setJob(await api('/api/references/analyser', 'POST', {fichier: d.fichier}));
		} catch (e) {
			setErr((e as Error).message);
		} finally {
			setSending(false);
		}
	};
	const running = sending || job?.status === 'running';
	return (
		<button className="tpl ref" disabled={running} onClick={() => input.current?.click()}>
			<b>＋ Style depuis une vidéo</b>
			<span>{running ? (sending ? 'Envoi de la vidéo…' : 'L\'outil mesure le style (rythme, sous-titres, zooms, musique, couleurs) : 1 à 3 min…')
				: 'Dépose un reel déjà monté que tu aimes : l\'outil crée le même style et l\'applique.'}</span>
			{job?.status === 'failed' ? <span className="err">{job.error}</span> : null}
			{err ? <span className="err">{err}</span> : null}
			<input ref={input} type="file" accept="video/*" hidden onChange={(e) => { pick(e.currentTarget.files?.[0]); e.currentTarget.value = ''; }} />
		</button>
	);
};

const Thumb: React.FC<{reel?: ReelDoc}> = ({reel}) => {
	const c = reel?.clips[0];
	const src = c && reel?.sources[c.source];
	return src ? <img src={`/api/thumb?proxy=${encodeURIComponent(src.proxy)}&t=${(c.in + 1).toFixed(1)}`} alt="" /> : <div className="ph" />;
};

export const Revision: React.FC<{onEdit: (key: string) => void; templates: Template[]; onTemplates: () => Promise<unknown>}> = ({onEdit, templates, onTemplates}) => {
	const [state, setState] = useState<State | null>(null);
	const [offline, setOffline] = useState(false);
	const [sel, setSel] = useState<string | null>(null);
	const [opened, setOpened] = useState<Opened | null>(null);
	const [reels, setReels] = useState<Record<string, ReelDoc>>({});
	const [styling, setStyling] = useState(false);
	const [busy, setBusy] = useState('');
	const [err, setErr] = useState('');
	const [notice, setNotice] = useState('');
	// « Choisir plusieurs » : cases a cocher dans la liste pour supprimer plusieurs videos d'un coup
	const [picking, setPicking] = useState(false);
	const [picked, setPicked] = useState<string[]>([]);
	const [formats, setFormats] = useState<string[]>(loadFormats);
	const refresh = useCallback(() => api('/api/revision').then((s: State) => {
		setState(s);
		setOffline(false);
		return s;
	}).catch(() => setOffline(true)), []);
	useEffect(() => {
		refresh();
		const t = window.setInterval(refresh, 2500);
		return () => window.clearInterval(t);
	}, [refresh]);
	const items = state?.items ?? [];
	const item = items.find((i) => i.id === sel) ?? null;
	// premiere video prete selectionnee d'office (et une autre si celle-ci a ete retiree)
	useEffect(() => {
		if (items.length && (!sel || !items.some((i) => i.id === sel))) setSel((items.find((i) => i.status === 'pret') ?? items[0]).id);
	}, [items, sel]);
	const ready = !!item?.project && !!item.rid && (item.status === 'pret' || item.status === 'pris');
	const key = ready ? `${item!.project}/${item!.rid}` : '';
	// montage affiche : relu quand on change de video ou quand le serveur l'a refait (nouveau style, « Refaire »)
	const shownKey = useRef('');
	useEffect(() => {
		if (shownKey.current !== key) {
			shownKey.current = key;
			setOpened(null);
			setStyling(false);
			setErr('');
		}
		if (!key) return;
		let live = true;
		api(`/api/reels/${key}/open`).then((d: Opened) => {
			if (!live) return;
			setOpened(d);
			setReels((r) => ({...r, [key]: d.reel}));
		}).catch((e) => live && setErr(`Impossible d'ouvrir ce montage : ${(e as Error).message}`));
		return () => {
			live = false;
		};
	}, [key, item?.updated]);
	// vignettes de la liste (un montage illisible ou deplace n'est pas redemande toutes les 2,5 s)
	const thumbAsked = useRef(new Map<string, number>());
	useEffect(() => {
		const now = Date.now();
		items.filter((i) => i.project && i.rid && !reels[`${i.project}/${i.rid}`] && now - (thumbAsked.current.get(`${i.project}/${i.rid}`) ?? 0) > 30000)
			.slice(0, 4).forEach((i) => {
				const k = `${i.project}/${i.rid}`;
				thumbAsked.current.set(k, now); // nouvel essai au plus toutes les 30 s si le montage ne s'ouvre pas
				api(`/api/reels/${k}/open`).then((d: Opened) => setReels((r) => ({...r, [k]: d.reel}))).catch(() => undefined);
			});
	}, [items]);

	const reel = opened?.reel;
	const total = useMemo(() => (reel ? duration(reel) : 1), [reel]);
	const inputProps = useMemo(() => (reel ? {reel, mediaBase: '', assetBase: '/assets', audio: 'preview' as const} : null), [reel]);
	const act = async (label: string, fn: () => Promise<unknown>) => {
		setBusy(label);
		setErr('');
		setNotice('');
		try {
			await fn();
		} catch (e) {
			setErr((e as Error).message);
		} finally {
			setBusy('');
		}
	};
	const next = () => {
		const list = items.filter((i) => i.status === 'pret');
		const k = list.findIndex((i) => i.id === sel);
		const n = list[(k + 1) % Math.max(1, list.length)];
		if (n) setSel(n.id);
	};
	const exportsList = item?.exports ?? [];
	const exporting = exportsList.some(running);
	const pct = exportsList.length ? Math.round((100 * exportsList.reduce((a, e) => a + (e.status === 'done' ? 1 : e.progress ?? 0), 0)) / exportsList.length) : 0;
	const toggleFormat = (f: string) => {
		const list = Object.keys(FORMATS).filter((k) => (k === f ? !formats.includes(k) : formats.includes(k)));
		setFormats(list);
		if (list.length) storeFormats(list);
	};
	const take = () => act(`Mise en file de l'export (${formats.join(', ')})…`, async () => {
		await api(`/api/revision/${item!.id}/prendre`, 'POST', {formats});
		await refresh();
	});
	const cancelExport = (e: ItemExport) => act('Annulation de l\'export…', async () => {
		await api(`/api/jobs/${e.job}/cancel`, 'POST');
		await refresh();
	});
	const openFolder = (file?: string) => file && api('/api/open-folder', 'POST', {file}).catch((e) => setErr((e as Error).message));
	const remove = (i: Item) => {
		if (!window.confirm(`Retirer « ${i.title || i.name} » de la liste ?\n\nAucun fichier n'est supprimé (vidéo brute, montage et exports restent sur le disque).\n`
			+ 'Pour t\'en débarrasser vraiment, utilise plutôt « 🗑️ Supprimer ».')) return;
		act('Retrait…', () => api(`/api/revision/${i.id}/retirer`, 'POST', {}).then(setState));
	};
	const trash = state?.corbeille ?? 'le dossier corbeille de l\'éditeur';
	/** Message apres suppression : ou sont les fichiers, ce qui est garde. */
	const deletedText = (d: Deleted) => [`« ${d.titre} » supprimée.`,
		d.corbeille ? `Montage et vidéos brutes rangés dans : ${d.corbeille}` : 'Il n\'y avait aucun fichier à ranger.',
		...d.gardes.map((g) => `Gardé : ${g}.`),
		d.livraisons.length ? `Vidéo(s) exportée(s) gardée(s) : ${d.livraisons.join(' ; ')}` : ''].filter(Boolean).join('\n');
	const supprimer = (i: Item) => {
		const why = deleteBlock(i);
		if (why) return setErr(why);
		const shared = items.some((o) => o.id !== i.id && o.unit === i.unit);
		const exported = !!i.taken || (i.exports ?? []).some((e) => e.status === 'done');
		const lines = [`Supprimer « ${i.title || i.name} » ?`, '', '• Elle disparaît de la liste.'];
		if (i.project) lines.push(`• Son montage (projects\\${i.project}) va dans la corbeille de l'éditeur.`);
		lines.push(shared ? '• Ses vidéos brutes sont gardées : une autre vidéo de la liste les utilise.'
			: `• Ses vidéos brutes (${winPath(i.unit)}) vont aussi dans la corbeille.`);
		lines.push(exported ? '• Les vidéos déjà exportées (dossier livraisons) sont GARDÉES.' : '• Les vidéos exportées (dossier livraisons) ne sont jamais touchées.');
		lines.push('', `Rien n'est effacé pour de bon : tout est rangé dans ${trash}, avec une note pour le remettre.`);
		if (!window.confirm(lines.join('\n'))) return;
		act('Suppression…', async () => {
			const d: State & {supprime: Deleted} = await api(`/api/revision/${i.id}/supprimer`, 'POST', {});
			setState(d);
			setPicked((p) => p.filter((x) => x !== i.id));
			setNotice(deletedText(d.supprime));
		});
	};
	const pickedItems = items.filter((i) => picked.includes(i.id));
	const supprimerPlusieurs = () => {
		if (!pickedItems.length) return;
		const blocked = pickedItems.filter((i) => deleteBlock(i));
		const lines = [`Supprimer ${pickedItems.length} vidéo(s) ?`, '', ...pickedItems.slice(0, 12).map((i) => `• ${i.title || i.name}`)];
		if (pickedItems.length > 12) lines.push(`• … et ${pickedItems.length - 12} autre(s)`);
		lines.push('', 'Leur montage et leurs vidéos brutes vont dans la corbeille de l\'éditeur (rien n\'est effacé pour de bon).',
			'Les vidéos déjà exportées (dossier livraisons) sont gardées.');
		if (blocked.length) lines.push(`${blocked.length} vidéo(s) en montage ou en export ne seront pas supprimées.`);
		lines.push('', `Corbeille : ${trash}`);
		if (!window.confirm(lines.join('\n'))) return;
		act('Suppression…', async () => {
			const d: State & {resultats: ({ok: boolean; id: string; titre?: string; error?: string} & Partial<Deleted>)[]} =
				await api('/api/revision/supprimer', 'POST', {ids: pickedItems.map((i) => i.id)});
			setState(d);
			const ok = d.resultats.filter((r) => r.ok);
			const ko = d.resultats.filter((r) => !r.ok);
			setPicked(ko.map((r) => r.id));
			if (!ko.length) setPicking(false);
			const where = [...new Set(ok.map((r) => r.corbeille).filter(Boolean))];
			setNotice([`${ok.length} vidéo(s) supprimée(s).`, where.length ? `Rangées dans : ${trash}` : ''].filter(Boolean).join('\n'));
			if (ko.length) setErr(`Pas supprimée(s) :\n${ko.map((r) => `• ${r.titre ?? r.id} : ${r.error}`).join('\n')}`);
		});
	};
	const togglePick = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
	const applyStyle = (t: Pick<Template, 'id' | 'name'>) => act(`Style « ${t.name} » en cours d'application…`, async () => {
		if (!item) throw new Error('Choisis d\'abord une vidéo.');
		const d: Opened = await api(`/api/revision/${item.id}/style`, 'POST', {style: t.id});
		setOpened(d);
		setReels((r) => ({...r, [key]: d.reel}));
		await refresh();
	});
	const speech = reel && reel.kind !== 'immobilier' && reel.kind !== 'evenement';
	const preview = reel ? formatOf(reel) : '9:16';
	const styleName = (id?: string) => templates.find((t) => t.id === id)?.name ?? id ?? 'aucun';

	return (
		<div className="revision">
			<aside className="rv-list">
				<Uploader onDone={refresh} />
				{offline ? <p className="err">L'éditeur ne répond pas (redémarrage en cours ?) : nouvel essai toutes les 2 secondes…</p> : null}
				{items.length > 1 ? (
					<div className="rv-pickbar">
						{picking ? (
							<>
								<span className="muted">{picked.length} choisie(s)</span>
								<button className="small" onClick={() => setPicked(picked.length === items.length ? [] : items.map((i) => i.id))}>
									{picked.length === items.length ? 'Aucune' : 'Toutes'}</button>
								<button className="small danger" disabled={!picked.length || !!busy} onClick={supprimerPlusieurs}>🗑️ Supprimer ({picked.length})</button>
								<button className="small ghost" onClick={() => { setPicking(false); setPicked([]); }}>Fini</button>
							</>
						) : <button className="small ghost" onClick={() => setPicking(true)} title="Cocher plusieurs vidéos pour les supprimer d'un coup">☑ Choisir plusieurs</button>}
					</div>
				) : null}
				<div className="rv-items">
					{state && !items.length ? <p className="muted">Aucune vidéo pour l'instant. Dépose tes vidéos brutes ci-dessus, ou copie-les dans
						<b> media\entree\</b>(un dossier par lot).</p> : null}
					{items.map((i) => {
						const why = deleteBlock(i);
						const label = i.title || i.name;
						return (
							<div key={i.id} className={`rv-row${picking ? ' picking' : ''}`}>
								{picking ? <input type="checkbox" className="rv-pick" checked={picked.includes(i.id)} onChange={() => togglePick(i.id)} aria-label={`Choisir « ${label} »`} /> : null}
								<button className={`rv-item${i.id === sel ? ' on' : ''} st-${i.status}${picking && picked.includes(i.id) ? ' picked' : ''}`}
									onClick={() => (picking ? togglePick(i.id) : setSel(i.id))} title={i.style ? `Style : ${styleName(i.style)}` : undefined}>
									<Thumb reel={i.project ? reels[`${i.project}/${i.rid}`] : undefined} />
									<div>
										<b>{label}</b>
										<span className="muted">{i.typeLabel ? `${i.typeLabel} · ` : ''}{(i.exports ?? []).some(running) ? 'Export en cours…' : STATUS[i.status]}
											{i.status === 'travail' ? ` · ${i.stage}` : ''}</span>
										{i.status === 'travail' || i.status === 'attente' ? <div className="bar"><div style={{width: `${Math.round(100 * (i.progress || 0))}%`}} /></div> : null}
									</div>
								</button>
								{!picking ? (
									<button className={`rv-del${why ? ' blocked' : ''}`} disabled={!!busy} onClick={() => supprimer(i)}
										title={why || 'Supprimer cette vidéo (elle va dans la corbeille de l\'éditeur)'} aria-label={`Supprimer « ${label} »`}>🗑️</button>
								) : null}
							</div>
						);
					})}
				</div>
				<button className="small" disabled={!state?.entree} onClick={() => openFolder(state?.entree)}>Ouvrir le dossier Entrée</button>
			</aside>
			<section className="rv-main">
				{!item ? <div className="empty">Dépose des vidéos à gauche pour commencer.</div> : null}
				{item && !ready ? (
					<div className="empty">
						{item.status === 'erreur' ? (
							<>
								<p className="err">{item.error || 'Le montage a échoué.'}</p>
								<div className="row">
									<button className="primary" disabled={!!busy} onClick={() => act('Relance…', () => api(`/api/revision/${item.id}/refaire`, 'POST', {}).then(setState))}>Refaire</button>
									<button className="ghost" disabled={!!busy} onClick={() => remove(item)}>Retirer de la liste</button>
									<button className="ghost danger" disabled={!!busy} onClick={() => supprimer(item)}>🗑️ Supprimer</button>
								</div>
							</>
						) : (
							<>
								<div className="spinner" />
								<p>{item.status === 'attente' ? 'En file : elle sera montée après les autres.' : item.stage}</p>
								<div className="bar wide"><div style={{width: `${Math.round(100 * (item.progress || 0))}%`}} /></div>
								{item.status === 'attente' ? (
									<div className="row">
										<button className="small ghost" disabled={!!busy} onClick={() => remove(item)}>Retirer de la liste</button>
										<button className="small ghost danger" disabled={!!busy} onClick={() => supprimer(item)}>🗑️ Supprimer</button>
									</div>
								) : null}
							</>
						)}
					</div>
				) : null}
				{ready && !reel && !err ? <div className="empty"><div className="spinner" /><p>Ouverture du montage…</p></div> : null}
				{ready && item && reel && inputProps ? (
					<>
						<div className="rv-player" style={{aspectRatio: `${reel.width} / ${reel.height}`}}>
							<Player component={Reel} inputProps={inputProps} durationInFrames={Math.max(1, Math.round(total * reel.fps))} fps={reel.fps}
								compositionWidth={reel.width} compositionHeight={reel.height} style={{width: '100%', height: '100%'}}
								controls clickToPlay autoPlay acknowledgeRemotionLicense />
						</div>
						<div className="rv-info">
							<b>{item.title || item.name}</b>
							<span className="muted">{item.typeLabel ? `Sujet : ${item.typeLabel}` : ''}{item.reason ? ` — ${item.reason}` : ''}
								{' · '}Style : {styleName(reel.template)} · {fmt(total)}
								{item.broll ? ` · ${item.broll} plan(s) de coupe` : ''}{item.ia === false ? ' · montée sans IA locale (règles simples)' : ''}</span>
							{item.alerts?.length ? (
								<details className="rv-alerts">
									<summary>⚠ {item.alerts.length} phrase(s) du script absente(s) des prises (ou script non lu)</summary>
									<ul>{item.alerts.map((a, k) => <li key={k}>{a}</li>)}</ul>
								</details>
							) : null}
						</div>
						<div className="rv-actions">
							<button className="big primary" disabled={!!busy || exporting || !formats.length} onClick={take}
								title={formats.length ? `Un fichier par format : ${formats.join(', ')}` : 'Coche au moins un format'}>
								{exporting ? `Export ${pct} %…` : item.status === 'pris' ? '✅ Reprendre (réexporter)' : '✅ Je la prends'}</button>
							<button className="big" disabled={!!busy} onClick={() => onEdit(key)}>✏️ Modifier</button>
							<button className={`big${styling ? ' on' : ''}`} disabled={!!busy} onClick={() => setStyling(!styling)}>🎨 Autre style</button>
							<button className="big ghost" onClick={next} title="Vidéo suivante à regarder">Suivante ▸</button>
						</div>
						<div className="rv-formats" title="Formats exportés quand tu prends la vidéo : un fichier par format coché">
							<span className="muted">Formats :</span>
							{Object.keys(FORMATS).map((f) => (
								<label key={f} className="inline fmt">
									<input type="checkbox" checked={formats.includes(f)} disabled={exporting || !!busy} onChange={() => toggleFormat(f)} /> {f} <small className="muted">{FORMAT_NAMES[f]}</small>
								</label>
							))}
						</div>
						{!formats.length ? <p className="flag">Coche au moins un format pour pouvoir prendre la vidéo.</p> : null}
						{formats.length && FORMATS[preview] && !formats.includes(preview) ? <p className="muted">L'aperçu est en {preview} : coche {preview} pour avoir exactement ce que tu vois.</p> : null}
						{exportsList.length ? (
							<div className="rv-exports">
								{exportsList.map((e) => (
									<div key={e.job} className="rv-export">
										<div className="row">
											<b>{e.format}</b>
											<span className={`st ${e.status}`}>{EXPORT_STATUS[e.status] ?? e.status}{e.status === 'running' ? ` — ${Math.round(100 * (e.progress ?? 0))} %` : ''}
												{e.status === 'done' && e.seconds ? ` (${e.seconds} s)` : ''}</span>
											<span className="grow" />
											{running(e) ? <button className="small" disabled={!!busy} onClick={() => cancelExport(e)}>Annuler</button> : null}
											{e.status === 'done' ? <button className="small" onClick={() => openFolder(e.out)}>Ouvrir le dossier</button> : null}
										</div>
										{e.status === 'running' ? <div className="bar"><div style={{width: `${Math.round(100 * (e.progress ?? 0))}%`}} /></div> : null}
										{e.status === 'running' && e.stage ? <div className="muted">{e.stage}</div> : null}
										<div className="muted rv-path" title={e.out}>{e.status === 'done' ? 'Enregistrée : ' : 'Fichier : '}{e.out}</div>
										{e.status === 'failed' ? <p className="err">{e.error || 'L\'export a échoué.'}</p> : null}
										{e.status === 'interrompu' ? <p className="flag">Export interrompu (l'éditeur a redémarré) : clique « {item.status === 'pris' ? 'Reprendre' : 'Je la prends'} » pour le relancer.</p> : null}
									</div>
								))}
							</div>
						) : null}
						{item.status === 'pris' && item.taken && !exportsList.length ? (
							<p className="ok">Enregistrée : {item.taken.out} <button className="small" onClick={() => openFolder(item.taken!.out)}>Ouvrir le dossier</button></p>
						) : null}
						{styling ? (
							<>
								<TemplateGrid className="rv-styles" templates={templates.filter((t) => (speech ? !['immobilier', 'evenement'].includes(t.id) : true))}
									current={reel.template} disabled={!!busy} onApply={applyStyle} onChanged={onTemplates}>
									<ReferenceCard onCreated={async (id) => {
										await onTemplates();
										applyStyle({id, name: 'nouveau style'});
									}} />
								</TemplateGrid>
								{reel.design?.mode==='produit'&&!reel.design.productVideo?<p className="muted">Pour animer ton produit : « Modifier » → « Style » → « Habillage du style », choisis sa photo ou son modèle GLB, puis « Créer l’animation 3D ».</p>:null}
								{item.previousStyleVersion ? <button disabled={!!busy} onClick={()=>act('Retour au style précédent…',async()=>{
									const d:Opened=await api(`/api/revision/${item.id}/retourstyle`,'POST',{});setOpened(d);setReels(r=>({...r,[key]:d.reel}));await refresh();
								})}>↶ Revenir au style précédent</button> : null}
								<SaveStyleCard className="card rv-save" reel={reel} reelKey={key} templates={templates} onSaved={async (t) => {
									await onTemplates();
									setOpened((o) => (o ? {...o, reel: {...o.reel, template: t.id}} : o));
								}} />
							</>
						) : null}
						{styling && item.type ? (
							<div className="row">
								<button className="small" disabled={!!busy || !reel.template} title="Les prochaines vidéos de ce sujet seront montées dans ce style"
									onClick={() => act('…', async () => {
										await api(`/api/types/${item.type}`, 'POST', {style: reel.template});
										setBusy('');
										alert(`C'est noté : les prochaines vidéos « ${item.typeLabel} » seront montées en « ${styleName(reel.template)} ».`);
									})}>
									📌 Toujours ce style pour « {item.typeLabel} »
								</button>
							</div>
						) : null}
						<div className="row rv-more">
							<button className="small ghost" disabled={!!busy || exporting} title={exporting ? 'Attends la fin de l\'export' : ''} onClick={() => remove(item)}>Retirer de la liste</button>
							<button className="small ghost danger" disabled={!!busy} title={deleteBlock(item) || 'Montage et vidéos brutes vers la corbeille ; les vidéos exportées sont gardées'}
								onClick={() => supprimer(item)}>🗑️ Supprimer</button>
						</div>
					</>
				) : null}
				{busy ? <p className="muted">{busy}</p> : null}
				{notice ? <p className="ok rv-notice">{notice}</p> : null}
				{err ? <p className="err">{err}</p> : null}
			</section>
		</div>
	);
};
