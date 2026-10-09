// Choregraphie (edition des mouvements) — FICHIER DE L'AGENT « choregraphie » (docs/direction-creative-v2/SPEC.md).
// ChoreoPanel = onglet « Chorégraphie » (menu Plus). L'IA (engine/editeur/choregraphie.py) propose l'entree et la sortie
// de chaque element avec une raison ; chaque mouvement se regle ici (type, direction, vitesse, courbe, desactiver,
// cadenas). « Refaire la chorégraphie » : POST /api/reels/<cle>/choregraphie {tout?} -> tache (useJob), puis reload().
// Ce qui est verrouille ou retouche a la main est garde par la nouvelle proposition.
// CSS : bloc /* choregraphie */ ... /* fin choregraphie */ de styles.css.
import React, {useMemo, useState} from 'react';
import {targetKey, targetTimes} from '../../remotion/src/choreo';
import {duration as reelDuration} from '../../remotion/src/timeline';
import type {ReelDoc} from '../../remotion/src/types';
import {api, useJob} from './api';
import {CueEditor, ROLE_LABELS, clock, moveSummary, selectCue, targetLabel, useCueSelection} from './choreo-lane';
import {LockToggle, withLock} from './lock';
import type {V2Props} from './v2';

export const ChoreoPanel: React.FC<V2Props> = ({reel, t, update, seek, current, reload}) => {
	const sel = useCueSelection();
	const [tout, setTout] = useState(false);
	const [err, setErr] = useState('');
	const [now, setNow] = useState(false);
	const [job, setJob] = useJob(() => reload());
	const running = job?.status === 'running' || job?.status === 'queued';
	const ch = reel.choreography;
	// resume ecrit par le moteur dans choreography.meta (types.ts : Choreography.meta)
	const resume = ch?.meta?.resume;
	const total = useMemo(() => reelDuration(reel), [reel]);
	const times = useMemo(() => targetTimes(reel, total), [reel, total]);
	const rows = useMemo(() => (ch?.cues ?? []).map((cue) => ({cue, place: times.get(targetKey(cue.cible)) ?? null}))
		.sort((a, b) => (a.place?.at ?? a.cue.at) - (b.place?.at ?? b.cue.at)), [ch, times]);
	const shown = now ? rows.filter((r) => r.place && t >= r.place.at - 0.5 && t < r.place.at + r.place.duration + 0.5) : rows;
	const counts = {
		total: rows.length,
		locked: rows.filter((r) => r.cue.locked).length,
		manual: rows.filter((r) => r.cue.manual && !r.cue.locked).length,
		off: rows.filter((r) => r.cue.desactive).length,
		orphan: rows.filter((r) => !r.place).length,
	};

	const refaire = async () => {
		setErr('');
		// laisser partir la derniere sauvegarde automatique (350 ms) : le moteur relit le reel sur le disque
		await new Promise((r) => setTimeout(r, 700));
		try {
			setJob(await api(`/api/reels/${current}/choregraphie`, 'POST', tout ? {tout: true} : {}));
		} catch (e) {
			const m = (e as Error).message;
			setErr(/404|introuvable|not found|JSON/i.test(m)
				? 'Cette fonction n’est pas encore active dans l’éditeur ouvert : il faut le redémarrer une fois.'
				: `Impossible de lancer la chorégraphie : ${m}`);
		}
	};
	const remove = (id: string) => update((r: ReelDoc) => (r.choreography
		? {...r, choreography: {...r.choreography, cues: r.choreography.cues.filter((c) => c.id !== id)}} : r));

	return (
		<div className="card choreo">
			<h3>Chorégraphie</h3>
			<p className="muted">
				L’IA décide comment chaque élément entre et sort de l’image — au rythme de la voix et de la musique, selon le moment du récit
				(accroche, tension, révélation, preuve, appel à l’action) — et dit pourquoi. Tout se règle ici ou dans la piste
				« Chorégraphie » de la timeline. Ce que tu retouches ou verrouilles n’est plus changé par l’IA.
			</p>
			{typeof resume === 'string' ? <p className="ch-resume">{resume}</p> : null}
			<div className="row ch-actions">
				<button className="primary" disabled={running || !!ch?.locked} onClick={refaire}
					title={ch?.locked ? 'Chorégraphie verrouillée : déverrouille-la pour la refaire' : 'L’IA recalcule les mouvements ; ce qui est verrouillé ou retouché est gardé'}>
					{running ? 'En cours…' : ch ? 'Refaire la chorégraphie' : 'Créer la chorégraphie'}
				</button>
				{ch ? (
					<LockToggle locked={ch.locked} label onChange={(v) => update((r) => (r.choreography ? {...r, choreography: withLock(r.choreography, v)} : r))}
						title={ch.locked ? 'Chorégraphie verrouillée : l’IA et les changements de style n’y touchent plus. Clique pour déverrouiller.'
							: 'Verrouiller toute la chorégraphie : l’IA et les changements de style n’y toucheront plus.'} />
				) : null}
			</div>
			{ch ? (
				<label className="ch-tout" title="Sinon, seuls les mouvements proposés par l’IA sont refaits">
					<input type="checkbox" checked={tout} onChange={(e) => setTout(e.target.checked)} /> Refaire aussi ce que j’ai retouché (jamais ce qui est verrouillé)
				</label>
			) : null}
			{running ? <p className="muted">{job?.stage || 'Calcul des mouvements…'}</p> : null}
			{job?.status === 'failed' ? <p className="err">{job.error}</p> : null}
			{job?.status === 'done' && job.result ? (
				<p className="ok">✓ Chorégraphie refaite : {job.result.cues} mouvement{job.result.cues > 1 ? 's' : ''} (détail ci-dessus).</p>
			) : null}
			{err ? <p className="err">{err}</p> : null}

			{!ch ? (
				<p className="muted">Pas encore de chorégraphie pour cette vidéo : sans elle, chaque élément garde son animation d’origine.</p>
			) : (
				<>
					<div className="row ch-filter">
						<span className="muted">
							{counts.total} mouvement{counts.total > 1 ? 's' : ''}
							{counts.locked ? ` · ${counts.locked} 🔒` : ''}{counts.manual ? ` · ${counts.manual} retouché${counts.manual > 1 ? 's' : ''}` : ''}
							{counts.off ? ` · ${counts.off} désactivé${counts.off > 1 ? 's' : ''}` : ''}
						</span>
						<label><input type="checkbox" checked={now} onChange={(e) => setNow(e.target.checked)} /> Seulement autour de la tête de lecture</label>
					</div>
					{!rows.length ? <p className="muted">Aucun mouvement : aucun élément n’est posé par-dessus l’image après l’accroche.</p> : null}
					<div className="ch-list">
						{shown.map(({cue, place}) => {
							const role = typeof cue.meta?.role === 'string' ? ROLE_LABELS[cue.meta.role] : null;
							const open = sel === cue.id;
							return (
								<div key={cue.id} className={`ch-item${open ? ' sel' : ''}${cue.desactive ? ' off' : ''}${place ? '' : ' orphan'}`}>
									<button type="button" className="ch-row" onClick={() => {
										selectCue(open ? null : cue.id);
										if (place && !open) seek(place.at);
									}}>
										<span className="ch-time">{clock(place?.at ?? cue.at)}</span>
										<span className="ch-name">{cue.locked ? '🔒 ' : cue.manual ? '✎ ' : ''}{targetLabel(reel, cue.cible)}</span>
										{role ? <span className="ch-role">{role}</span> : null}
										<span className="ch-how">{cue.desactive ? 'désactivé' : moveSummary(cue.entree)}</span>
									</button>
									{!place ? (
										<div className="ch-orphan">
											<span className="muted">Élément absent ou masqué dans ce style : ce mouvement ne s’applique pas.</span>
											<button type="button" className="small" onClick={() => remove(cue.id)}>Retirer</button>
										</div>
									) : null}
									{open && place ? <CueEditor reel={reel} cue={cue} update={update} seek={seek} at={place.at} titre={false} /> : null}
								</div>
							);
						})}
					</div>
					{counts.orphan ? (
						<p className="muted">{counts.orphan} mouvement{counts.orphan > 1 ? 's visent' : ' vise'} un élément absent (retiré ou masqué par le style).</p>
					) : null}
				</>
			)}
		</div>
	);
};
