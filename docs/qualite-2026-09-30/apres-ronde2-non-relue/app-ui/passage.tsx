// « Refaire seulement ce passage » — FICHIER DE L'AGENT « passage » (docs/direction-creative-v2/SPEC.md).
// Branche par l'architecte : RedoPassage est rendu dans la barre d'outils de la timeline ; la plage choisie (range) est
// dessinee sur la timeline par Timeline.tsx (bande .tl-range). Route : POST /api/reels/<cle>/passage {debut, fin} -> tache
// (engine/editeur/passage.py) ; a la fin, reload(). « Annuler » : POST /api/reels/<cle>/restore {file: version gardee}.
// La barre reste sur UNE ligne : le compte rendu s'ouvre dans une bulle au-dessus (.passage-pop).
// Raccourcis : I = debut ici, O = fin ici (hors champs de saisie).
// CSS : bloc /* passage */ ... /* fin passage */ de styles.css.
import React from 'react';
import {duration} from '../../remotion/src/timeline';
import {api, fmt, useJob} from './api';
import type {PassageRange, V2Props} from './v2';

/** Compte rendu du moteur (passage.refaire). */
type Resultat = {debut: number; fin: number; changes: string[]; resume: string; modifie: boolean; version: string | null;
	proteges?: number; aCheval?: number; ia?: boolean; remarques?: string[]};

const MIN = 0.3; // meme limite que le serveur et le moteur
const DEFAUT = 3; // longueur proposee quand on ne pose qu'une borne
const tc = (s: number) => fmt(Math.max(0, s)).replace('.', ',');
const sec = (s: number) => `${s.toFixed(1).replace('.', ',')} s`;

/** Ce qui empeche de lancer (phrase affichee), ou null. */
export const problemePlage = (r: PassageRange, total: number): string | null => {
	if (!r) return 'Choisis le passage : place la tête de lecture, « Début ici », avance, puis « Fin ici ».';
	if (!Number.isFinite(r.debut) || !Number.isFinite(r.fin)) return 'Passage invalide.';
	if (r.debut < 0) return 'Le début ne peut pas être avant 0 s.';
	if (r.fin <= r.debut) return 'Le début doit être avant la fin.';
	if (r.debut >= total) return `Le début est après la fin de la vidéo (${tc(total)}).`;
	if (Math.min(r.fin, total) - r.debut < MIN) return `Passage trop court : au moins ${sec(MIN)}.`;
	return null;
};

/** Message du moteur sans l'emballage technique ; ancien serveur (route absente) : dire quoi faire. */
const lisible = (msg: string) => {
	if (['Introuvable.', 'Action inconnue.'].includes(msg.trim())) return '« Refaire ce passage » arrive avec la mise à jour de l’éditeur : ferme puis rouvre « Editeur Sami », puis réessaie.';
	return msg.replace(/^Erreur inattendue : /, '').replace(/\s*\(d[ée]tails dans runtime\/cache\/erreurs\.log\)\s*$/, '').trim();
};

/** Elements verrouilles ou retouches qui touchent la plage (ils ne bougeront pas). */
const proteges = (reel: V2Props['reel'], r: PassageRange) => {
	if (!r) return 0;
	const touche = (at?: number, d?: number) => at !== undefined && at + (d ?? 0) > r.debut && at < r.fin;
	const lock = (e: {locked?: boolean; manual?: boolean; edited?: boolean}) => !!(e.locked || e.manual || e.edited);
	return [...(reel.graphics ?? []), ...(reel.broll ?? []), ...(reel.vectors ?? [])].filter((e) => lock(e) && touche(e.at, e.duration)).length;
};

export const RedoPassage: React.FC<V2Props & {range: PassageRange; setRange: (r: PassageRange) => void}> = ({reel, t, current, reload, seek, range, setRange}) => {
	const total = React.useMemo(() => duration(reel), [reel]);
	const [result, setResult] = React.useState<Resultat | null>(null);
	const [err, setErr] = React.useState('');
	const [open, setOpen] = React.useState(false);
	const [undoing, setUndoing] = React.useState(false);
	const [undone, setUndone] = React.useState(false);
	const [started, setStarted] = React.useState(0);
	const [now, setNow] = React.useState(0);
	const [job, setJob] = useJob((j) => {
		setResult(j.result as Resultat);
		setUndone(false);
		setOpen(true);
		reload();
	});
	const running = job?.status === 'running' || job?.status === 'queued';
	const failed = job?.status === 'failed' ? lisible(job.error || 'La tâche a échoué.') : '';
	const erreur = err || failed;
	const bloque = problemePlage(range, total);
	const n = proteges(reel, range);

	// une autre video : on oublie le compte rendu (la plage est effacee par App)
	React.useEffect(() => {
		setResult(null);
		setErr('');
		setOpen(false);
		setUndone(false);
		setJob(null);
	}, [current]);
	// chrono pendant le calcul
	React.useEffect(() => {
		if (!running) return;
		const id = window.setInterval(() => setNow(Date.now()), 500);
		return () => window.clearInterval(id);
	}, [running]);
	React.useEffect(() => {
		if (failed) setOpen(true);
	}, [failed]);

	const clamp = (s: number) => Math.max(0, Math.min(total, +s.toFixed(2)));
	const setDebut = React.useCallback((s: number) => {
		const d = Math.min(clamp(s), Math.max(0, total - MIN));
		setRange({debut: d, fin: range && range.fin - d >= MIN ? range.fin : Math.min(total, d + DEFAUT)});
	}, [range, total, setRange]);
	const setFin = React.useCallback((s: number) => {
		const f = Math.max(clamp(s), Math.min(total, MIN));
		setRange({debut: range && f - range.debut >= MIN ? range.debut : Math.max(0, f - DEFAUT), fin: f});
	}, [range, total, setRange]);

	// raccourcis I / O (comme dans les logiciels de montage), jamais pendant une saisie
	const keys = React.useRef({t, setDebut, setFin});
	keys.current = {t, setDebut, setFin};
	React.useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			const el = e.target as HTMLElement | null;
			if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
			if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)) return;
			const k = e.key.toLowerCase();
			if (k !== 'i' && k !== 'o') return;
			e.preventDefault();
			if (k === 'i') keys.current.setDebut(keys.current.t);
			else keys.current.setFin(keys.current.t);
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	}, []);

	const lancer = async () => {
		if (!range || bloque) return;
		setErr('');
		setResult(null);
		setUndone(false);
		setOpen(false);
		setStarted(Date.now());
		setNow(Date.now());
		try {
			setJob(await api(`/api/reels/${current}/passage`, 'POST', {debut: +Math.max(0, range.debut).toFixed(3), fin: +Math.min(total, range.fin).toFixed(3)}));
		} catch (e) {
			setErr(lisible((e as Error).message));
			setOpen(true);
		}
	};
	const annuler = async () => {
		if (!result?.version) return;
		setUndoing(true);
		setErr('');
		try {
			await api(`/api/reels/${current}/restore`, 'POST', {file: result.version});
			setUndone(true);
			reload();
		} catch (e) {
			setErr(lisible((e as Error).message));
		} finally {
			setUndoing(false);
		}
	};

	const secondes = running ? Math.max(0, Math.round((now - started) / 1000)) : 0;
	const titre = bloque ?? `Refait l’habillage automatique de ${tc(range!.debut)} à ${tc(Math.min(total, range!.fin))} seulement : `
		+ 'mots en couleur, éléments du style, graphismes proposés, mouvements, puis la relecture (un seul élément à la fois). '
		+ `Rien ne bouge avant ni après${n ? `, ni les ${n} élément(s) verrouillé(s) ou retouché(s) du passage` : ''}.`;

	return (
		<span className="passage row" style={{margin: 0}}>
			<button className="small" title="Début du passage = tête de lecture (touche I)" disabled={running} onClick={() => setDebut(t)}>Début ici</button>
			<button className="small" title="Fin du passage = tête de lecture (touche O)" disabled={running} onClick={() => setFin(t)}>Fin ici</button>
			{range ? (
				<button className="small ghost passage-plage" title="Aller au début du passage" onClick={() => seek(range.debut)}>
					{tc(range.debut)} → {tc(Math.min(total, range.fin))} <span className="muted">({sec(Math.max(0, Math.min(total, range.fin) - range.debut))})</span>
				</button>
			) : null}
			<button className="small primary" disabled={!!bloque || running || undoing} title={titre} onClick={lancer}>
				{running ? `En cours… ${secondes} s` : 'Refaire seulement ce passage'}
			</button>
			{range && !running ? <button className="small ghost" title="Oublier ce passage choisi (le montage ne change pas)" onClick={() => setRange(null)}>✕</button> : null}
			{(result || erreur) && !open ? (
				<button className={`small ghost ${erreur ? 'passage-alerte' : ''}`} title="Revoir le compte rendu du passage" onClick={() => setOpen(true)}>{erreur ? '⚠' : 'ℹ'}</button>
			) : null}
			{running ? <span className="passage-pop passage-mini" role="status">Le moteur refait ce passage… Ne retouche pas ce passage pendant le calcul.{secondes > 8 ? ' (L’IA locale peut prendre jusqu’à une minute pour démarrer.)' : ''}</span> : null}
			{open && (result || erreur) ? (
				<div className="passage-pop" role="dialog" aria-label="Compte rendu du passage">
					<div className="passage-tete">
						<b>Refaire seulement ce passage</b>
						<button className="small ghost" title="Fermer" onClick={() => setOpen(false)}>✕</button>
					</div>
					{erreur ? <p className="err">{erreur}</p> : null}
					{result && !undone ? (
						<>
							<p>{result.resume}</p>
							{result.changes.length ? (
								<ul>
									{result.changes.slice(0, 14).map((c, i) => <li key={i}>{c}</li>)}
									{result.changes.length > 14 ? <li className="muted">… et {result.changes.length - 14} autre(s).</li> : null}
								</ul>
							) : null}
							{(result.remarques ?? []).map((r, i) => <p key={i} className="muted">{r}</p>)}
						</>
					) : null}
					{undone ? <p className="ok">Passage annulé : le montage est revenu exactement comme avant.</p> : null}
					<div className="row">
						{result?.modifie && result.version && !undone ? (
							<button className="small" disabled={undoing} title="Remet le montage exactement comme avant ce passage (les retouches faites depuis seront perdues ; une version « avant restauration » est gardée)" onClick={annuler}>
								{undoing ? 'Annulation…' : 'Annuler ce passage'}
							</button>
						) : null}
						{result ? <button className="small ghost" onClick={() => seek(result.debut)}>Revoir le passage</button> : null}
						<button className="small ghost" onClick={() => setOpen(false)}>Fermer</button>
					</div>
				</div>
			) : null}
		</span>
	);
};
