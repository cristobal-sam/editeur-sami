// Panneau « Ajouter » : plans de coupe (bibliotheque media/broll, banques de medias libres, IA par phrase).
// L'interface ne connait pas les banques : elle parle au serveur (/api/banques...), qui passe par le moteur.
import React, {useEffect, useMemo, useRef, useState} from 'react';
import {brollMode, timedWords} from '../../remotion/src/timeline';
import {formatOf, type Broll, type ReelDoc, type Source} from '../../remotion/src/types';
import {api, fmt, useJob, type Job} from './api';

type Update = (fn: (r: ReelDoc) => ReelDoc) => void;
const uid = () => `b${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;

/** Media externe au format commun (banques/base.py), avec le classement de l'IA s'il y en a un. */
export type Media = {
	provider: string; providerName: string; id: string; type: 'video' | 'image'; width: number; height: number; duration: number | null;
	orientation: 'portrait' | 'paysage' | 'carre'; quality: string; preview: string; previewVideo: string | null;
	author: string; authorUrl: string; pageUrl: string; tags: string[]; query?: string;
	score?: number; relevance?: number; confidence?: 'haute' | 'moyenne' | 'faible'; reasons?: string[]; auto?: boolean; start?: number;
};
type Status = {fournisseurs: {id: string; nom: string; actif: boolean}[]; actif: boolean; fichierCles: string; bibliotheque: number};
type Props = {reel: ReelDoc; update: Update; t: number; seek: (s: number) => void; current: string; addSources: (s: Record<string, Source>) => void;
	adder: Adder; autoJob: Job | null; onAutoBroll: (opts: {tout: boolean; banques: boolean}) => void};

const ORIENTS: Record<string, string> = {'': 'Toutes', portrait: 'Vertical', paysage: 'Horizontal', carre: 'Carré'};
const DUREES: Record<string, string> = {'': 'Toutes durées', courte: 'Moins de 10 s', moyenne: '10 à 30 s', longue: 'Plus de 30 s'};
const QUALITES: Record<string, string> = {'': 'Toutes qualités', hd: 'HD et plus', '4k': '4K'};
const CONF: Record<string, string> = {haute: 'sûr', moyenne: 'possible', faible: 'faible'};
const keyOf = (m: Media) => `${m.provider}:${m.type}:${m.id}`;

/** Ajouter un media de banque au montage : le serveur le telecharge (une fois), puis on l'insere sur la piste V2.
 * Appele dans App (toujours monte) : quitter l'onglet pendant le telechargement ne perd rien ; si on a change de
 * video entre-temps, rien n'est insere dans la mauvaise. Un seul ajout a la fois. */
export const useAddMedia = (current: string, addSources: Props['addSources'], update: Update) => {
	const cur = useRef(current);
	cur.current = current;
	const pending = useRef<(Omit<Broll, 'id' | 'source'> & {key: string}) | null>(null);
	const [busy, setBusy] = useState<string | null>(null);
	const [note, setNote] = useState('');
	const [job, setJob] = useJob((j) => {
		const r = j.result as {source: string; sources: Record<string, Source>};
		const p = pending.current;
		pending.current = null;
		setBusy(null);
		if (!p) return;
		if (p.key !== cur.current) {
			setNote("Plan téléchargé, mais tu as changé de vidéo entre-temps : rien n'a été inséré (ajoute-le à nouveau, sans nouveau téléchargement).");
			return;
		}
		const {key, ...b} = p;
		addSources(r.sources);
		update((reel) => ({...reel, broll: [...(reel.broll ?? []), {...b, id: uid(), source: r.source}].sort((x, y) => x.at - y.at)}));
	});
	useEffect(() => {
		if (job?.status === 'failed') setBusy(null);
	}, [job]);
	const add = async (m: Media, at: number, duration: number, start: number) => {
		if (pending.current) return;
		setNote('');
		pending.current = {key: current, at: +at.toFixed(2), duration: +duration.toFixed(2), in: Math.max(0, start), word: m.query ?? m.tags[0] ?? ''};
		setBusy(keyOf(m));
		try {
			setJob(await api(`/api/reels/${current}/banque`, 'POST', {fournisseur: m.provider, id: m.id, type: m.type, requete: m.query ?? ''}));
		} catch (e) {
			pending.current = null;
			setBusy(null);
			setNote((e as Error).message);
		}
	};
	return {add, busy, error: job?.status === 'failed' ? job.error ?? '' : note};
};
export type Adder = ReturnType<typeof useAddMedia>;

/** Duree et point d'entree par defaut d'un plan de coupe ajoute a la main. */
const defaults = (m: Media) => {
	const d = m.duration ?? 0;
	const duration = m.type === 'video' ? Math.min(2.5, Math.max(1, d - 0.6)) : 2.5;
	return {duration, start: m.type === 'video' ? Math.max(0, Math.min(0.5, d - duration - 0.1)) : 0};
};

/** Vignette d'un media externe : survol = apercu video ; credit obligatoire (auteur + banque, lien vers la page). */
export const MediaCard: React.FC<{m: Media; busy: boolean; disabled?: boolean; label: string; onAdd: () => void; why?: boolean}> = ({m, busy, disabled, label, onAdd, why}) => {
	const [hover, setHover] = useState(false);
	const shape = {portrait: 'vertical', paysage: 'horizontal', carre: 'carré'}[m.orientation];
	return (
		<div className={`media${m.confidence === 'faible' ? ' weak' : ''}`} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
			<div className="media-img">
				{hover && m.previewVideo ? <video src={m.previewVideo} muted autoPlay loop playsInline /> : <img src={m.preview} alt="" loading="lazy" />}
				<span className="media-tags">{m.type === 'video' && m.duration != null ? `${m.duration} s · ` : 'photo · '}{m.quality} · {shape}</span>
				{m.confidence ? <span className={`media-conf ${m.confidence}`}>{CONF[m.confidence]}</span> : null}
			</div>
			{why && m.reasons ? <div className="media-why">{m.reasons.join(' · ')}</div> : null}
			<a className="media-credit" href={m.pageUrl} target="_blank" rel="noreferrer noopener" title="Voir le média à sa source">
				{m.author || 'Auteur'} · {m.providerName}
			</a>
			<button className="small primary" disabled={busy || disabled} onClick={onAdd}>{busy ? 'Téléchargement…' : label}</button>
		</div>
	);
};

/** Phrase du montage a l'instant t (meme regle que le moteur : ponctuation ou pause > 0,6 s). */
const usePhrase = (reel: ReelDoc, t: number) => {
	const words = useMemo(() => timedWords(reel), [reel]);
	return useMemo(() => {
		const groups: typeof words[] = [];
		let cur: typeof words = [];
		words.forEach((w, k) => {
			cur.push(w);
			const next = words[k + 1];
			if (/[.!?…]$/.test(w.w.trim()) || !next || next.outStart - w.outEnd > 0.6) {
				groups.push(cur);
				cur = [];
			}
		});
		const g = groups.find((x) => t >= x[0].outStart - 0.3 && t <= x[x.length - 1].outEnd + 0.3);
		return g ? {text: g.map((w) => w.w).join(' '), start: g[0].outStart, end: g[g.length - 1].outEnd} : null;
	}, [words, t]);
};

type PhraseResult = {phrase: {text: string; start: number; end: number}; requetes: string[]; duree: number; candidats: Media[]; message: string; ia: boolean};

const PhraseCard: React.FC<Props & {adder: Adder; status: Status | null}> = ({reel, t, seek, current, adder, status}) => {
	const phrase = usePhrase(reel, t);
	const [res, setRes] = useState<PhraseResult | null>(null);
	const [job, setJob] = useJob((j) => setRes(j.result));
	const running = job?.status === 'running';
	return (
		<div className="card">
			<h3>Plan de coupe pour cette phrase <small>l'IA cherche pour toi</small></h3>
			<p className="clip-text">{phrase ? `« ${phrase.text} »` : 'Place la tête de lecture sur une phrase.'}</p>
			<div className="row">
				<button className="primary small" disabled={!phrase || running || !status?.actif} onClick={async () => {
					setRes(null);
					setJob(await api(`/api/reels/${current}/phrase`, 'POST', {at: t}));
				}}>Trouver automatiquement</button>
				{running ? <span className="muted">L'IA lit la phrase, cherche et compare les plans (20 à 60 s)…</span> : null}
			</div>
			{job?.status === 'failed' ? <p className="err">{job.error}</p> : null}
			{res ? (
				<>
					<p className="muted">
						<button className="small" onClick={() => seek(res.phrase.start)}>▶ {fmt(res.phrase.start)}</button> Recherches : {res.requetes.join(' · ')}
						{res.ia ? '' : ' (sans IA locale : mots de la phrase)'}
					</p>
					{res.message ? <p className="flag">{res.message}</p> : null}
					<div className="medias">
						{res.candidats.map((m) => (
							<MediaCard key={keyOf(m)} m={m} why busy={adder.busy === keyOf(m)} disabled={!!adder.busy} label={`Ajouter à ${fmt(res.phrase.start)}`}
								onAdd={() => adder.add(m, res.phrase.start, res.duree, m.start ?? 0)} />
						))}
					</div>
				</>
			) : null}
		</div>
	);
};

const ExternalSearch: React.FC<Props & {adder: Adder}> = ({reel, t, adder}) => {
	const f = formatOf(reel);
	const [q, setQ] = useState('');
	const [type, setType] = useState<'video' | 'image'>('video');
	// toutes orientations par defaut : les banques ont surtout des videos horizontales, encadrees dans un reel vertical
	const [orientation, setOrientation] = useState(f === '16:9' ? 'paysage' : '');
	const [duree, setDuree] = useState('');
	const [qualite, setQualite] = useState('hd');
	const [results, setResults] = useState<Media[] | null>(null);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [err, setErr] = useState('');
	const [asked, setAsked] = useState('');
	const seq = useRef(0);
	const run = async (p = 1) => {
		if (!q.trim()) return;
		const my = ++seq.current; // une reponse ancienne n'ecrase jamais la derniere recherche
		const query = q.trim();
		setLoading(true);
		setErr('');
		try {
			const r = await api('/api/banques/recherche', 'POST', {q: query, type, orientation, duree: type === 'video' ? duree : '', qualite: type === 'video' ? qualite : '', page: p});
			if (my !== seq.current) return;
			setResults((old) => (p > 1 && old ? [...old, ...r.resultats.filter((m: Media) => !old.some((o) => keyOf(o) === keyOf(m)))] : r.resultats));
			setAsked(query);
			setPage(p);
			if (r.erreurs?.length) setErr(r.erreurs.join(' ; '));
		} catch (e) {
			if (my === seq.current) setErr((e as Error).message);
		} finally {
			if (my === seq.current) setLoading(false);
		}
	};
	useEffect(() => {
		if (results) run(1);
	}, [type, orientation, duree, qualite]);
	return (
		<div className="card">
			<h3>Recherche externe <small>images et vidéos libres de droits</small></h3>
			<div className="row">
				<input type="text" className="grow" placeholder="ex. argent, téléphone, bureau, voyage… (en anglais : plus de résultats)" value={q}
					onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && !loading && run(1)} />
				<button className="primary small" disabled={!q.trim() || loading} onClick={() => run(1)}>{loading ? '…' : 'Chercher'}</button>
			</div>
			<div className="row">
				<div className="seg">
					<button className={`small${type === 'video' ? ' primary' : ''}`} onClick={() => setType('video')}>Vidéos</button>
					<button className={`small${type === 'image' ? ' primary' : ''}`} onClick={() => setType('image')}>Photos</button>
				</div>
				<select value={orientation} onChange={(e) => setOrientation(e.target.value)}>
					{Object.entries(ORIENTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
				</select>
				{type === 'video' ? (
					<select value={duree} onChange={(e) => setDuree(e.target.value)}>
						{Object.entries(DUREES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
					</select>
				) : null}
				{type === 'video' ? (
					<select value={qualite} onChange={(e) => setQualite(e.target.value)}>
						{Object.entries(QUALITES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
					</select>
				) : null}
			</div>
			{err ? <p className="err">{err}</p> : null}
			{adder.error ? <p className="err">{adder.error}</p> : null}
			{results ? (
				<>
					<div className="medias">
						{results.map((m) => {
							const d = defaults(m);
							return <MediaCard key={keyOf(m)} m={{...m, query: asked}} busy={adder.busy === keyOf(m)} disabled={!!adder.busy} label={`Ajouter à ${fmt(t)}`}
								onAdd={() => adder.add({...m, query: asked}, t, d.duration, d.start)} />;
						})}
					</div>
					{!results.length ? <p className="muted">Aucun résultat : essaie un autre mot (souvent mieux en anglais), ou une autre orientation.</p> : null}
					{results.length ? <div className="row"><button className="small" disabled={loading} onClick={() => run(page + 1)}>Plus de résultats</button></div> : null}
				</>
			) : null}
		</div>
	);
};

// ---------------- Plans de coupe proposes sur tout le montage (bibliotheque + banques) ----------------
type Local = {source: string; name: string; t: number; score: number; proxy: string};
type Slot = {at: number; duration: number; word: string; reason: string; candidates: Local[]; externes?: Media[]; requetes?: string[]};

const BrollCard: React.FC<Props & {adder: Adder; status: Status | null}> = ({reel, update, t, seek, current, addSources, adder, status, autoJob, onAutoBroll}) => {
	const [slots, setSlots] = useState<Slot[] | null>(null);
	const [msg, setMsg] = useState('');
	const [all, setAll] = useState(false);
	const [banks, setBanks] = useState(true);
	const [job, setJob] = useJob((j) => {
		addSources(j.result.sources ?? {});
		setSlots(j.result.slots);
		setMsg(j.result.message ?? '');
	});
	const list = reel.broll ?? [];
	// pas de mode fige a l'insertion : plein ecran ou encadre selon le format (brollMode), sauf choix manuel
	const insert = (b: Omit<Broll, 'id'>) => update((r) => ({...r, broll: [...(r.broll ?? []), {...b, id: uid()}].sort((a, c) => a.at - c.at)}));
	const setB = (id: string, p: Partial<Broll>) => update((r) => ({...r, broll: (r.broll ?? []).map((b) => (b.id === id ? {...b, ...p} : b))}));
	const running = job?.status === 'running' || autoJob?.status === 'running';
	const launch = async () => {
		setMsg('');
		setJob(await api(`/api/reels/${current}/broll`, 'POST', {tout: all, banques: banks && !!status?.actif}));
	};
	const autoMsg = autoJob?.status === 'done' && autoJob.result
		? [autoJob.result.inseres ? `${autoJob.result.inseres} plan(s) de coupe inséré(s) automatiquement (seulement ceux dont l'IA est sûre).`
			: 'Aucun plan assez sûr pour être inséré seul : utilise « Proposer des plans de coupe ».', autoJob.result.message].filter(Boolean).join(' ')
		: '';
	return (
		<>
			<div className="card">
				<h3>Plans de coupe sur toute la vidéo <small>piste V2, au-dessus du montage</small></h3>
				<p className="muted">L'IA trouve les bons moments (mots importants, coupes à cacher) et propose 3 plans à chaque fois : un clic pour insérer.
					Elle cherche d'abord dans <b>media\broll</b> (tes plans + ceux déjà pris), puis dans la banque libre.</p>
				<div className="row">
					<label className="inline"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> Aussi les prises non utilisées</label>
					<label className="inline" title={status?.actif ? '' : 'Ajoute une clé dans cles-api.env'}>
						<input type="checkbox" checked={banks && !!status?.actif} disabled={!status?.actif} onChange={(e) => setBanks(e.target.checked)} /> Aussi la banque libre
					</label>
				</div>
				<div className="row">
					<button className="small primary" disabled={running} onClick={launch}>Proposer des plans de coupe</button>
					<button className="small" disabled={running} onClick={() => onAutoBroll({tout: all, banques: banks && !!status?.actif})} title="N'insère que les plans dont l'IA est sûre ; les autres restent des propositions">Mettre les plans sûrs automatiquement</button>
				</div>
				{running ? <p className="muted">{(job?.status === 'running' ? job : autoJob)?.stage} (la première fois : 1 à 2 min)…</p> : null}
				{job?.status === 'failed' ? <p className="err">{job.error}</p> : null}
				{autoJob?.status === 'failed' ? <p className="err">{autoJob.error}</p> : null}
				{msg ? <p className="flag">{msg}</p> : null}
				{autoMsg ? <p className="flag">{autoMsg}</p> : null}
			</div>
			{(slots ?? []).map((s, i) => (
				<div className="card" key={i}>
					<h3><span>{fmt(s.at)} <small>{s.reason}</small></span><button className="small" onClick={() => seek(s.at)}>▶</button></h3>
					{(s.candidates ?? []).length ? (
						<div className="thumbs">
							{s.candidates.map((c, k) => (
								<button key={k} className={`thumb${c.score < 0.23 ? ' weak' : ''}`} title={`${c.name} à ${fmt(c.t)} — correspondance ${c.score < 0.23 ? 'faible' : 'bonne'} (${Math.round(c.score * 100)})`}
									onClick={() => insert({source: c.source, in: c.t, at: s.at, duration: s.duration, word: s.word})}>
									<img src={`/api/thumb?proxy=${encodeURIComponent(c.proxy)}&t=${c.t + 0.5}`} alt="" />
									<span>{c.name}</span>
								</button>
							))}
						</div>
					) : null}
					{s.externes?.length ? (
						<>
							<p className="muted">Banque libre{s.requetes?.length ? ` (${s.requetes.join(' · ')})` : ''} :</p>
							<div className="medias">
								{s.externes.map((m) => (
									<MediaCard key={keyOf(m)} m={m} why busy={adder.busy === keyOf(m)} disabled={!!adder.busy} label={`Ajouter à ${fmt(s.at)}`}
										onAdd={() => adder.add(m, s.at, s.duration, m.start ?? 0)} />
								))}
							</div>
						</>
					) : null}
					{!(s.candidates ?? []).length && !s.externes?.length ? <span className="muted">Aucun plan trouvé.</span> : null}
				</div>
			))}
			{list.length ? (
				<div className="card">
					<h3>Dans le montage <small>{list.length}</small></h3>
					{list.map((b) => {
						const src = reel.sources[b.source];
						return (
							<div className="row" key={b.id}>
								<span className="grow">{fmt(b.at)} · {src?.still ? '🖼 ' : ''}{src?.name ?? b.source}{b.word ? ` · « ${b.word} »` : ''}
									{src?.credit ? <small className="muted"> — {src.credit.author} · {src.credit.provider}</small> : null}</span>
								<select value={b.mode ?? ''} onChange={(e) => setB(b.id, {mode: (e.target.value || undefined) as Broll['mode']})} title="Affichage du plan de coupe">
									<option value="">Auto ({brollMode(reel, b.source) === 'encadre' ? 'encadré' : 'plein écran'})</option>
									<option value="plein">Plein écran</option><option value="encadre">Encadré</option>
								</select>
								<input type="range" min={0.5} max={5} step={0.1} value={b.duration} style={{width: 90}} title={`Durée ${b.duration.toFixed(1)} s`} onChange={(e) => setB(b.id, {duration: Number(e.target.value)})} />
								<button className="small" onClick={() => setB(b.id, {at: +t.toFixed(2)})} title="Placer à l'instant courant">⇤ {fmt(t)}</button>
								<button className="small" onClick={() => seek(b.at)}>▶</button>
								<button className="small" onClick={() => update((r) => ({...r, broll: (r.broll ?? []).filter((x) => x.id !== b.id)}))}>✕</button>
							</div>
						);
					})}
				</div>
			) : null}
		</>
	);
};

export const AjouterPanel: React.FC<Props> = (props) => {
	const [status, setStatus] = useState<Status | null>(null);
	const adder = props.adder;
	useEffect(() => {
		api('/api/banques').then(setStatus).catch(() => setStatus(null));
	}, []);
	return (
		<>
			{status && !status.actif ? (
				<div className="card">
					<h3>Banque d'images et de vidéos libres <small>non configurée</small></h3>
					<p className="muted">Pour chercher des plans de coupe sur Internet, colle ta clé gratuite dans le fichier <b>{status.fichierCles}</b> (à la racine
						de l'éditeur ; les explications sont dedans), puis reviens ici. Tes plans du dossier <b>media\broll</b> marchent déjà sans clé.</p>
					<button className="small" onClick={() => api('/api/banques').then(setStatus)}>J'ai mis la clé</button>
				</div>
			) : null}
			<PhraseCard {...props} adder={adder} status={status} />
			{status?.actif ? <ExternalSearch {...props} adder={adder} /> : null}
			<BrollCard {...props} adder={adder} status={status} />
			{status?.actif ? <p className="muted credit-line">Images et vidéos des banques libres : {status.fournisseurs.filter((f) => f.actif).map((f) => f.nom).join(', ')}.</p> : null}
		</>
	);
};
