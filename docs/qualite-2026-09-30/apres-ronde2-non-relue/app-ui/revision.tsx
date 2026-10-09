// Ecran « Revision » (par defaut) : on depose des videos brutes, l'outil les monte seul (sujet -> style adapte),
// on regarde : « Je la prends » (export), « Modifier » (editeur complet) ou « Autre style ».
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Player, type PlayerRef} from '@remotion/player';
import {Reel} from '../../remotion/src/Reel';
import {duration} from '../../remotion/src/timeline';
import {FORMATS, formatOf, type ReelDoc} from '../../remotion/src/types';
import {api, fmt, useJob} from './api';
import {SaveStyleCard, TemplateGrid, type Template} from './panels2';

/** Controle qualite (engine/editeur/controle.py, resume) : note /10, verdict, constats classes du plus grave au moins grave.
 * temps = secondes du montage ; zone = boite [x0, y0, x1, y1] en px du format « format » (ex. 1080x1920). */
export type Constat = {gravite: 'bloquant' | 'important' | 'conseil'; code: string; temps: number | null; fin: number | null; message: string;
	suggestion: string; zone?: [number, number, number, number]; element?: string; plages?: [number, number][]};
export type Controle = {version: number; date: string; note: number; verdict: string; compte: {bloquant: number; important: number; conseil: number};
	video?: string | null; format?: string | null; total?: number; constats: Constat[]};
/** Resultat range sur un export : le resume, ou l'erreur du controle (jamais bloquant pour la livraison). */
type ControleExport = Controle | {erreur: string; date?: string};
const aNote = (c?: ControleExport | null): c is Controle => !!c && typeof (c as Controle).note === 'number';

/** Un export par format coche dans « Je la prends ». interrompu = l'editeur a redemarre pendant l'export.
 * controle = controle qualite de la video livree (lance tout seul apres l'export) ; controleEtat = en attente / en cours. */
export type ItemExport = {format: string; job: string; out: string; status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'interrompu';
	progress?: number; stage?: string; error?: string | null; seconds?: number | null; controle?: ControleExport | null;
	controleEtat?: 'queued' | 'running' | null};
export type Item = {
	id: string; unit: string; lot: string; name: string; status: 'attente' | 'travail' | 'pret' | 'pris' | 'erreur';
	stage: string; progress: number; project?: string; rid?: string; type?: string; typeLabel?: string; title?: string;
	reason?: string; style?: string; broll?: number; error?: string | null; exports?: ItemExport[];
	previousStyleVersion?: string | null;
	alerts?: string[]; ia?: boolean; updated?: number;
	/** Note du controle qualite du montage (resume ; les constats sont dans reel.controle). */
	controle?: (Pick<Controle, 'note' | 'verdict' | 'compte' | 'date'> & {stamp?: number}) | null;
	taken?: {out: string; outs?: string[]; formats?: string[]; date: number} | null;
	/** Ce qu'une suppression garderait : une autre video (meme retiree de la liste) utilise les memes videos brutes / le meme montage. */
	partage?: {unit: boolean; project: boolean};
};
type State = {items: Item[]; lots: Record<string, {client?: string | null}>; entree: string; corbeille?: string; corbeilleN?: number; busy: boolean};
type Opened = {reel: ReelDoc};
/** Resultat d'une suppression (le serveur range le montage et les videos brutes dans la corbeille de l'editeur). */
type Deleted = {id: string; titre: string; corbeille: string | null; deplaces: string[]; gardes: string[]; livraisons: string[]};
/** Une entree de la corbeille (dossier corbeille\<date> <titre>\ avec son corbeille.json). */
type TrashEntry = {dossier: string; titre: string; supprime: string | null; deplacements: {avant: string; maintenant: string}[]; gardes: string[]; restaurable: boolean; raison: string};
type Restored = {titre: string; remis: string[]; item: Item | null; note: string};
const dateFr = (iso: string | null) => {
	const d = iso ? new Date(iso) : null;
	return d && !Number.isNaN(d.getTime()) ? d.toLocaleString('fr-CA', {dateStyle: 'short', timeStyle: 'short'}) : '';
};

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

/** Corbeille de la Revision : les videos supprimees, avec un vrai bouton « Restaurer » (rien n'est jamais efface pour de bon). */
const TrashList: React.FC<{count: number; folder?: string; busy: boolean; onRestored: (r: Restored) => void; onError: (e: string) => void}> = ({count, folder, busy, onRestored, onError}) => {
	const [open, setOpen] = useState(false);
	const [entries, setEntries] = useState<TrashEntry[] | null>(null);
	const [working, setWorking] = useState('');
	const load = useCallback(() => api('/api/revision/corbeille').then((d: {entrees: TrashEntry[]}) => setEntries(d.entrees)).catch((e) => onError((e as Error).message)), [onError]);
	// liste relue a l'ouverture et quand le nombre change (suppression, restauration, dossier deplace a la main)
	useEffect(() => {
		if (open) load();
	}, [open, count, load]);
	const restore = async (e: TrashEntry) => {
		if (!window.confirm(`Restaurer « ${e.titre} » ?\n\n${e.deplacements.map((d) => `• ${winPath(d.avant)} revient à sa place`).join('\n')}\n\nSon montage sera conservé s'il est présent. S'il manque, la vidéo sera remontée.`)) return;
		setWorking(e.dossier);
		onError('');
		try {
			const d: State & {restaure: Restored} = await api('/api/revision/corbeille/restaurer', 'POST', {dossier: e.dossier});
			onRestored(d.restaure);
			load();
		} catch (err) {
			onError((err as Error).message);
			load();
		} finally {
			setWorking('');
		}
	};
	return (
		<div className="rv-trash">
			<div className="row">
				<button className="small ghost" onClick={() => setOpen(!open)} title="Vidéos supprimées : montage et vidéos brutes rangés dans la corbeille de l'éditeur">
					{open ? '▾' : '▸'} 🗑️ Corbeille ({count})</button>
				{open && folder ? <button className="small ghost" onClick={() => api('/api/open-folder', 'POST', {file: folder}).catch((e) => onError((e as Error).message))}>Ouvrir le dossier</button> : null}
			</div>
			{open ? (
				<div className="rv-trash-list">
					{entries === null ? <p className="muted">Lecture de la corbeille…</p> : null}
					{entries && !entries.length ? <p className="muted">La corbeille est vide. Rien n'est jamais effacé pour de bon : une vidéo supprimée apparaît ici.</p> : null}
					{(entries ?? []).map((e) => (
						<div key={e.dossier} className="rv-trash-item">
							<div>
								<b>{e.titre}</b>
								<span className="muted">{dateFr(e.supprime) ? `Supprimée le ${dateFr(e.supprime)}` : e.dossier}{e.deplacements.length ? ` · ${e.deplacements.length} dossier(s)` : ''}</span>
								{!e.restaurable ? <span className="err">{e.raison || 'Pas restaurable pour l\'instant.'}</span> : null}
							</div>
							<button className="small" disabled={!e.restaurable || busy || !!working} onClick={() => restore(e)}
								title={e.restaurable ? 'Remettre le montage et les vidéos brutes à leur place, et la vidéo dans la liste' : e.raison}>
								{working === e.dossier ? 'Restauration…' : '↶ Restaurer'}</button>
						</div>
					))}
				</div>
			) : null}
		</div>
	);
};

const GRAVITE: Record<Constat['gravite'], string> = {bloquant: 'Bloquant', important: 'Important', conseil: 'Conseil'};
const virgule = (n: number) => String(Math.round(n * 10) / 10).replace('.', ',');
/** Moment d'un probleme a la francaise : 0:28,5. */
const tcv = (t: number) => fmt(t).replace('.', ',');
const noteClasse = (c: Pick<Controle, 'note' | 'compte'>) => (c.compte.bloquant ? 'mauvais' : c.note >= 8 ? 'bon' : c.note >= 6 ? 'moyen' : 'mauvais');
/** « 2 bloquants · 3 importants · 1 conseil » (les zeros sont omis). */
const compteTexte = (c: Controle['compte']) => {
	const parts = (['bloquant', 'important', 'conseil'] as const).filter((g) => c[g]).map((g) => `${c[g]} ${g}${c[g] > 1 ? 's' : ''}`);
	return parts.length ? parts.join(' · ') : 'aucun problème';
};
/** Une source de rapport affichee dans le panneau : le montage (reel.controle) ou une video livree (export). */
type Rapport = {cle: string; titre: string; controle?: ControleExport | null; etat?: 'queued' | 'running' | null; video?: string};

/** Controle qualite dans la Revision : note /10, verdict, problemes (gravite, moment cliquable = aller a l'image, suggestion). */
const ControlePanel: React.FC<{rapports: Rapport[]; choisi: string; onChoisir: (cle: string) => void; reel: ReelDoc; relance: boolean; relanceErreur: string;
	busy: boolean; onRelancer: () => void; onVoir: (t: number, zone: Constat['zone'] | null) => void}> = ({rapports, choisi, onChoisir, reel, relance, relanceErreur, busy,
	onRelancer, onVoir}) => {
	const r = rapports.find((x) => x.cle === choisi) ?? rapports[0];
	const c = r && aNote(r.controle) ? r.controle : null;
	// une boite n'est dessinee que si le rapport est au format du lecteur (un export 16:9 n'a pas les memes px qu'un 9:16)
	const memeFormat = !c?.format || c.format === `${reel.width}x${reel.height}`;
	return (
		<div className="rv-controle">
			<div className="rvc-tete">
				<b>Contrôle qualité</b>
				{rapports.length > 1 ? (
					<div className="rvc-onglets" role="tablist">
						{rapports.map((x) => (
							<button key={x.cle} role="tab" aria-selected={x.cle === r?.cle} className={`small${x.cle === r?.cle ? ' on' : ''}`} onClick={() => onChoisir(x.cle)}
								title={x.video ? `Vidéo contrôlée : ${x.video}` : 'Contrôle du montage (sans rendu)'}>
								{x.titre}{aNote(x.controle) ? ` · ${virgule(x.controle.note)}/10` : x.etat ? ' · en cours…' : ''}
							</button>
						))}
					</div>
				) : null}
				<span className="grow" />
				<button className="small" disabled={busy || relance} onClick={onRelancer}
					title="Relit le montage actuel (quelques secondes, sans rendu) : à refaire après des retouches">{relance ? 'Contrôle en cours…' : '↻ Relancer le contrôle'}</button>
			</div>
			{relanceErreur ? <p className="err">Contrôle qualité impossible : {relanceErreur}</p> : null}
			{r?.etat ? <p className="muted">{r.etat === 'running' ? 'Contrôle de la vidéo livrée en cours (images, détourage, son) : environ 1 minute…' : 'Contrôle de la vidéo livrée en attente…'}</p> : null}
			{r && !c && !r.etat && r.controle && 'erreur' in r.controle ? <p className="err">Contrôle impossible : {r.controle.erreur}</p> : null}
			{!c && !r?.etat && !(r?.controle && 'erreur' in r.controle) ? (
				<p className="muted">{r?.cle === 'montage' ? 'Pas encore de contrôle pour ce montage : clique « Relancer le contrôle ».' : 'Pas encore de contrôle pour cette vidéo.'}</p>
			) : null}
			{c ? (
				<>
					<div className={`rvc-note ${noteClasse(c)}`}>
						<span className="rvc-score">{virgule(c.note)}<small>/10</small></span>
						<div>
							<b>{c.verdict}</b>
							<span className="muted">{compteTexte(c.compte)} — contrôlé le {c.date}{r.cle === 'montage' ? ' (montage, sans rendu)' : ' (vidéo livrée)'}</span>
						</div>
					</div>
					{c.constats.length ? (
						<ul className="rvc-liste">
							{c.constats.map((k, n) => (
								<li key={`${k.code}-${n}`} className={`rvc-c ${k.gravite}`}>
									<span className={`rvc-badge ${k.gravite}`}>{GRAVITE[k.gravite]}</span>
									{k.temps !== null && k.temps !== undefined ? (
										<button className="rvc-temps small" onClick={() => onVoir(k.temps as number, memeFormat ? k.zone ?? null : null)}
											title={memeFormat && k.zone ? 'Aller à ce moment et montrer l\'endroit' : 'Aller à ce moment'}>
											▶ {tcv(k.temps)}{k.fin !== null && k.fin !== undefined && k.fin - k.temps > 0.15 ? `–${tcv(k.fin)}` : ''}
										</button>
									) : <span className="rvc-temps muted">toute la vidéo</span>}
									<div className="rvc-texte">
										<div>{k.message}</div>
										<div className="muted">→ {k.suggestion}</div>
									</div>
								</li>
							))}
						</ul>
					) : <p className="ok">Aucun problème détecté.</p>}
					{(c.total ?? 0) > c.constats.length ? <p className="muted">+ {(c.total ?? 0) - c.constats.length} point(s) moins grave(s) dans le rapport complet (dossier runtime\cache\controle).</p> : null}
				</>
			) : null}
		</div>
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
		// item.controle.date : nouvelle note du controle qualite (apres un changement de style) -> constats relus
	}, [key, item?.updated, item?.controle?.stamp ?? item?.controle?.date]);
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
	// ---- controle qualite : aller au moment d'un probleme (et montrer l'endroit), relancer le controle du montage ----
	const player = useRef<PlayerRef>(null);
	const [zone, setZone] = useState<{box: [number, number, number, number]; n: number} | null>(null);
	const [onglet, setOnglet] = useState('');
	const [relance, setRelance] = useJob(() => {
		if (!key) return;
		api(`/api/reels/${key}/open`).then((d: Opened) => {
			setOpened(d);
			setReels((r) => ({...r, [key]: d.reel}));
		}).catch(() => undefined);
		refresh();
	});
	useEffect(() => {
		setZone(null);
		setOnglet('');
	}, [key]);
	useEffect(() => {
		if (!zone) return;
		const t = window.setTimeout(() => setZone(null), 4500);
		return () => window.clearTimeout(t);
	}, [zone]);
	const voir = (t: number, box: Constat['zone'] | null) => {
		if (!reel) return;
		player.current?.pause();
		player.current?.seekTo(Math.max(0, Math.min(Math.round(total * reel.fps) - 1, Math.round(t * reel.fps))));
		setZone(box ? {box, n: Date.now()} : null);
	};
	const controleMontage = (reel as (ReelDoc & {controle?: Controle}) | undefined)?.controle ?? null;
	const rapports: Rapport[] = useMemo(() => {
		const list: Rapport[] = [{cle: 'montage', titre: 'Montage', controle: controleMontage}];
		for (const e of item?.exports ?? []) {
			if (e.status === 'done' || e.controle || e.controleEtat) list.push({cle: `export:${e.job}`, titre: `Export ${e.format}`, controle: e.controle, etat: e.controleEtat, video: e.out});
		}
		return list;
	}, [controleMontage, item?.exports]);
	// onglet par defaut : la video livree la plus recente qui a un controle (plus complet : images, son), sinon le montage
	const ongletDefaut = [...rapports].reverse().find((x) => x.cle !== 'montage' && (aNote(x.controle) || x.etat))?.cle ?? 'montage';
	// un serveur lance avant cette version ne connait pas la route : on le dit clairement (au lieu de « Introuvable. »)
	const routeControle = async (body: object) => {
		try {
			return await api(`/api/reels/${key}/controle`, 'POST', body);
		} catch (e) {
			if ((e as Error).message === 'Introuvable.') throw new Error('Le contrôle qualité n\'est pas encore actif : relance l\'éditeur (« Editeur Sami.cmd »), puis réessaie.');
			throw e;
		}
	};
	const relancer = () => act('Contrôle qualité du montage…', async () => {
		setRelance(await routeControle({}));
		setOnglet('montage');
	});
	const controlerExport = (e: ItemExport) => act(`Contrôle de l'export ${e.format}…`, async () => {
		await routeControle({video: e.out, format: e.format});
		setOnglet(`export:${e.job}`);
		await refresh();
	});
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
	const take = () => {
		// probleme bloquant trouve par le controle qualite : on previent avant d'exporter (le choix reste au monteur)
		const bloquants = (controleMontage?.constats ?? []).filter((k) => k.gravite === 'bloquant');
		if (controleMontage?.compte.bloquant && !window.confirm([`Le contrôle qualité (${controleMontage.date}) a trouvé ${controleMontage.compte.bloquant} problème(s) bloquant(s) :`, '',
			...bloquants.slice(0, 5).map((k) => `• ${k.temps !== null ? `${tcv(k.temps)} — ` : ''}${k.message}`), '',
			'Exporter quand même ? (« Annuler » pour corriger d\'abord : clique un problème pour aller au bon moment.)'].join('\n'))) return;
		act(`Mise en file de l'export (${formats.join(', ')})…`, async () => {
			await api(`/api/revision/${item!.id}/prendre`, 'POST', {formats});
			await refresh();
		});
	};
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
		// meme regle que le serveur (planSuppression) : une autre video, meme retiree de la liste, garde ce qu'elle partage
		const shared = i.partage?.unit ?? items.some((o) => o.id !== i.id && o.unit === i.unit);
		const sharedProject = i.partage?.project ?? items.some((o) => o.id !== i.id && !!i.project && o.project === i.project);
		const exported = !!i.taken || (i.exports ?? []).some((e) => e.status === 'done');
		const lines = [`Supprimer « ${i.title || i.name} » ?`, '', '• Elle disparaît de la liste.'];
		if (i.project) lines.push(sharedProject ? `• Son montage (projects\\${i.project}) est GARDÉ : une autre vidéo (peut-être retirée de la liste) l'utilise.`
			: `• Son montage (projects\\${i.project}) va dans la corbeille de l'éditeur.`);
		lines.push(shared ? `• Ses vidéos brutes (${winPath(i.unit)}) sont GARDÉES : une autre vidéo (peut-être retirée de la liste) les utilise.`
			: `• Ses vidéos brutes (${winPath(i.unit)}) vont aussi dans la corbeille.`);
		lines.push(exported ? '• Les vidéos déjà exportées (dossier livraisons) sont GARDÉES.' : '• Les vidéos exportées (dossier livraisons) ne sont jamais touchées.');
		lines.push('', `Rien n'est effacé pour de bon : tout est rangé dans ${trash}. Bouton « Restaurer » dans la Corbeille (sous la liste) pour la remettre.`);
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
										{i.controle && (i.status === 'pret' || i.status === 'pris') ? (
											<span className={`rv-note ${noteClasse(i.controle)}`} title={`Contrôle qualité du ${i.controle.date} : ${i.controle.verdict} (${compteTexte(i.controle.compte)})`}>
												{virgule(i.controle.note)}/10</span>
										) : null}
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
				<TrashList count={state?.corbeilleN ?? 0} folder={state?.corbeille} busy={!!busy} onError={setErr} onRestored={(r) => {
					setNotice([`« ${r.titre} » restaurée.`, ...r.remis.map((d) => `Remis : ${winPath(d)}`), r.item ? 'Elle est de retour dans la liste.' : '', r.note].filter(Boolean).join('\n'));
					// la liste d'abord (sinon la selection retomberait sur la premiere video prete), puis la video restauree
					refresh().then(() => r.item && setSel(r.item.id));
				}} />
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
						{/* apercu + controle qualite cote a cote (en dessous si l'ecran est etroit) : la note et les problemes se lisent
						    en regardant la video, sans faire defiler ni ecraser le lecteur */}
						<div className="rv-stage">
							<div className="rv-player" style={{aspectRatio: `${reel.width} / ${reel.height}`}}>
								<Player ref={player} component={Reel} inputProps={inputProps} durationInFrames={Math.max(1, Math.round(total * reel.fps))} fps={reel.fps}
									compositionWidth={reel.width} compositionHeight={reel.height} style={{width: '100%', height: '100%'}}
									controls clickToPlay autoPlay acknowledgeRemotionLicense />
								{zone ? (
									<div key={zone.n} className="rvc-zone" aria-hidden style={{left: `${(100 * zone.box[0]) / reel.width}%`, top: `${(100 * zone.box[1]) / reel.height}%`,
										width: `${(100 * (zone.box[2] - zone.box[0])) / reel.width}%`, height: `${(100 * (zone.box[3] - zone.box[1])) / reel.height}%`}} />
								) : null}
							</div>
							<ControlePanel rapports={rapports} choisi={onglet || ongletDefaut} onChoisir={setOnglet} reel={reel} busy={!!busy}
								relance={relance?.status === 'running' || relance?.status === 'queued'} relanceErreur={relance?.status === 'failed' ? relance.error || 'erreur inconnue' : ''}
								onRelancer={relancer} onVoir={voir} />
						</div>
						<div className="rv-info">
							<b>{item.title || item.name}</b>
							<span className="muted">{item.typeLabel ? `Sujet : ${item.typeLabel}` : ''}{item.reason ? ` — ${item.reason}` : ''}
								{' · '}Style : {styleName(reel.template)} · {fmt(total)}
								{item.broll ? ` · ${item.broll} plan(s) de coupe` : ''}{item.ia === false ? ' · montée sans IA locale (règles simples)' : ''}</span>
							{reel.sobriete?.resume ? <span className="muted" title="Relecture du monteur : un seul élément à la fois, rien sur l'accroche ; les éléments retirés restent en proposition dans « Modifier »">{reel.sobriete.resume}</span> : null}
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
											{e.status === 'done' ? (
												<button className="small" disabled={!!busy || !!e.controleEtat} onClick={() => controlerExport(e)}
													title="Contrôle qualité de la vidéo livrée : images, détourage, lisibilité, son (environ 1 minute)">
													{e.controleEtat ? 'Contrôle en cours…' : '🔎 Contrôler l\'export'}</button>
											) : null}
										</div>
										{e.status === 'done' && (aNote(e.controle) || e.controleEtat) ? (
											<button className={`rvc-ligne ${aNote(e.controle) ? noteClasse(e.controle) : ''}`} onClick={() => setOnglet(`export:${e.job}`)}
												title="Voir les problèmes trouvés dans cette vidéo (panneau Contrôle qualité)">
												{aNote(e.controle) ? <>Contrôle : <b>{virgule(e.controle.note)}/10</b> — {e.controle.verdict} ({compteTexte(e.controle.compte)})</>
													: e.controleEtat === 'running' ? 'Contrôle qualité de la vidéo en cours…' : 'Contrôle qualité de la vidéo en attente…'}
											</button>
										) : null}
										{e.status === 'done' && e.controle && !aNote(e.controle) && !e.controleEtat ? <p className="flag">Contrôle de la vidéo impossible : {e.controle.erreur}</p> : null}
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
