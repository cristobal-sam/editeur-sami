// Piste « Chorégraphie » de la timeline — FICHIER DE L'AGENT « choregraphie » (docs/direction-creative-v2/SPEC.md).
// Timeline.tsx (architecte) rend <ChoreoLane> DANS la ligne .tl-row.tl-choreo (24 px de haut, position relative).
// Chaque mouvement est dessine au temps de SON ELEMENT (le temps de l'element fait foi) : entree en clair a gauche,
// sortie a droite. Glisser = deplacer l'element ; glisser un bord = le raccourcir / l'allonger ; clic = choisir le
// mouvement (petite fenetre de reglage ici, et le meme dans Plus → Chorégraphie). Toute retouche marque le mouvement ou
// l'element « retouche a la main » (manual) : aucune passe automatique n'y touchera plus.
// Ce fichier contient aussi ce que partagent la piste et le panneau (libelles, editeur d'un mouvement, selection).
import React, {useMemo, useState, useSyncExternalStore} from 'react';
import {GRAPHIC_NAMES} from '../../remotion/src/graphics';
import {cueDurations, targetKey, targetTimes} from '../../remotion/src/choreo';
import {duration as reelDuration, pages, timedWords} from '../../remotion/src/timeline';
import type {Cue, CueMove, CueTarget, ReelDoc} from '../../remotion/src/types';
import {LockToggle, touched} from './lock';
import type {Update} from './v2';

// ---------- libelles (francais simple) ----------
export const MOVE_LABELS: Record<CueMove['type'], string> = {
	fondu: 'Fondu', glisse: 'Glisse', zoom: 'Zoom', pop: 'Pop', trace: 'Tracé', aucune: 'Aucun (animation d’origine)',
};
export const MOVE_ICONS: Record<CueMove['type'], string> = {fondu: '◐', glisse: '➜', zoom: '⊕', pop: '✦', trace: '✎', aucune: '·'};
export const CURVE_LABELS: Record<CueMove['courbe'], string> = {douce: 'Douce', rapide: 'Vive', rebond: 'Rebond', lineaire: 'Régulière'};
const DIRS = ['gauche', 'droite', 'haut', 'bas'] as const;
const DIR_ICONS: Record<(typeof DIRS)[number], string> = {gauche: '←', droite: '→', haut: '↑', bas: '↓'};
const DIR_FROM: Record<(typeof DIRS)[number], string> = {gauche: 'depuis la gauche', droite: 'depuis la droite', haut: 'depuis le haut', bas: 'depuis le bas'};
const DIR_TO: Record<(typeof DIRS)[number], string> = {gauche: 'vers la gauche', droite: 'vers la droite', haut: 'vers le haut', bas: 'vers le bas'};
export const ROLE_LABELS: Record<string, string> = {
	accroche: 'Accroche', probleme: 'Tension', solution: 'Révélation', preuve: 'Preuve', explication: 'Démonstration', cta: 'Appel à l’action',
};
const SCENE_NAMES: Record<string, string> = {
	metric: 'Chiffre', notification: 'Notification', comparison: 'Comparaison', keyword: 'Mot-clé', paper: 'Papier',
	product: 'Produit', dashboard: 'Tableau', flow: 'Parcours', cta: 'Bouton',
};
const TARGET_TYPES: Record<CueTarget['type'], string> = {
	graphics: 'Graphisme', design: 'Élément du style', broll: 'Plan de coupe', vector: 'Vecteur', caption: 'Sous-titre', banner: 'Bandeau',
};
const short = (s: string, n = 34) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
export const secs = (s: number) => `${s.toFixed(2).replace('.', ',')} s`;
export const clock = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`;

/** Nom lisible de l'element vise par un mouvement. */
export const targetLabel = (reel: ReelDoc, cible: CueTarget): string => {
	switch (cible.type) {
		case 'graphics': {
			const g = reel.graphics?.find((x) => x.id === cible.id);
			if (!g) return 'Graphisme (retiré)';
			const p = g.props ?? {};
			const txt = p.value !== undefined ? `${p.prefix ?? ''}${p.value}${p.suffix ?? ''}${p.label ? ` ${p.label}` : ''}`
				: String(p.text ?? p.title ?? (Array.isArray(p.items) ? p.items.join(', ') : ''));
			return `${GRAPHIC_NAMES[g.kind] ?? 'Graphisme'}${txt.trim() ? ` « ${short(txt.trim())} »` : ''}`;
		}
		case 'design': {
			const s = reel.styleScenes?.find((x) => x.id === cible.id);
			if (!s) return 'Élément du style (retiré)';
			return `${SCENE_NAMES[s.kind] ?? 'Élément du style'}${s.text ? ` « ${short(s.text)} »` : ''}`;
		}
		case 'broll': {
			const b = reel.broll?.find((x) => x.id === cible.id);
			return b ? `Plan de coupe « ${short(reel.sources[b.source]?.name ?? b.source)} »` : 'Plan de coupe (retiré)';
		}
		case 'vector': {
			const v = reel.vectors?.find((x) => x.id === cible.id);
			return v ? `Vecteur « ${v.asset.split('/').pop()?.replace(/\.svg$/i, '') ?? 'vecteur'} »` : 'Vecteur (retiré)';
		}
		case 'caption': {
			const p = pages(reel).find((x) => `${x.words[0].clip}:${x.words[0].index}` === cible.id);
			return p ? `Sous-titre « ${short(p.words.map((w) => w.w).join(' '))} »` : 'Sous-titre (texte changé)';
		}
		case 'banner':
			return reel.banner?.text?.trim() ? `Bandeau « ${short(reel.banner.text.trim())} »` : 'Bandeau';
	}
	return 'Élément';
};

/** Resume court d'une entree ou d'une sortie : « Glisse ↑ · 0,40 s ». */
export const moveSummary = (m: CueMove) => (m.type === 'aucune' ? 'aucun'
	: `${MOVE_LABELS[m.type]}${m.direction ? ` ${DIR_ICONS[m.direction]}` : ''} · ${secs(m.duree)}`);

// ---------- selection partagee piste <-> panneau ----------
let selection: string | null = null;
const listeners = new Set<() => void>();
export const selectCue = (id: string | null) => {
	selection = id;
	listeners.forEach((f) => f());
};
const subscribe = (f: () => void) => {
	listeners.add(f);
	return () => listeners.delete(f);
};
export const useCueSelection = () => useSyncExternalStore(subscribe, () => selection, () => selection);

// ---------- modifications ----------
/** Remplace un mouvement (retouche : marque manual, sauf `keep`). Le mouvement garde toujours ses champs obligatoires. */
export const patchCue = (update: Update, id: string, fn: (c: Cue) => Cue, keep = false) => update((r) => {
	const ch = r.choreography;
	if (!ch) return r;
	return {...r, choreography: {...ch, cues: ch.cues.map((c) => (c.id === id ? (keep ? fn(c) : touched(fn(c))) : c))}};
});

const DEFAULT_DUREE: Record<CueMove['type'], number> = {fondu: 0.3, glisse: 0.4, zoom: 0.35, pop: 0.3, trace: 0.55, aucune: 0};
const clampDur = (d: number) => Math.round(Math.max(0.08, Math.min(3, d)) * 100) / 100;

/** Reglage d'une entree ou d'une sortie : type, direction, vitesse, courbe. */
const MoveEditor: React.FC<{label: string; move: CueMove; sortie?: boolean; onChange: (m: CueMove) => void}> = ({label, move, sortie, onChange}) => {
	const dirs = move.type === 'glisse' || move.type === 'trace';
	const setType = (type: CueMove['type']) => onChange({
		type, courbe: move.courbe, duree: type === 'aucune' ? move.duree : move.duree > 0 ? move.duree : DEFAULT_DUREE[type],
		direction: type === 'glisse' || type === 'trace' ? move.direction ?? (type === 'trace' ? 'gauche' : 'bas') : null,
	});
	return (
		<div className="ch-move">
			<div className="ch-move-head">
				<b>{label}</b>
				<select value={move.type} onChange={(e) => setType(e.target.value as CueMove['type'])} title={`Type de ${label.toLowerCase()}`}>
					{(Object.keys(MOVE_LABELS) as CueMove['type'][]).map((k) => <option key={k} value={k}>{MOVE_LABELS[k]}</option>)}
				</select>
			</div>
			{move.type !== 'aucune' ? (
				<div className="ch-move-body">
					{dirs ? (
						<span className="ch-dirs" title={sortie ? 'Direction de la sortie' : 'D’où il arrive'}>
							{DIRS.map((d) => (
								<button key={d} type="button" className={`small${move.direction === d ? ' on' : ''}`} title={sortie ? DIR_TO[d] : DIR_FROM[d]}
									onClick={() => onChange({...move, direction: d})}>{DIR_ICONS[d]}</button>
							))}
						</span>
					) : null}
					<span className="ch-speed">
						<button type="button" className="small" title="Plus rapide (durée plus courte)" onClick={() => onChange({...move, duree: clampDur(move.duree / 1.33)})}>Plus rapide</button>
						<span className="ch-dur">{secs(move.duree)}</span>
						<button type="button" className="small" title="Plus lent (durée plus longue)" onClick={() => onChange({...move, duree: clampDur(move.duree * 1.33)})}>Plus lent</button>
					</span>
					<select value={move.courbe} onChange={(e) => onChange({...move, courbe: e.target.value as CueMove['courbe']})} title="Courbe : la façon d’accélérer">
						{(Object.keys(CURVE_LABELS) as CueMove['courbe'][]).map((k) => <option key={k} value={k}>{CURVE_LABELS[k]}</option>)}
					</select>
				</div>
			) : null}
		</div>
	);
};

/** Editeur complet d'un mouvement (piste et panneau). */
export const CueEditor: React.FC<{reel: ReelDoc; cue: Cue; update: Update; seek?: (s: number) => void; onClose?: () => void; at?: number;
	/** false : sans le nom de l'element (deja ecrit sur la ligne du panneau). */
	titre?: boolean}> = ({reel, cue, update, seek, onClose, at, titre = true}) => {
	const set = (fn: (c: Cue) => Cue) => patchCue(update, cue.id, fn);
	const role = typeof cue.meta?.role === 'string' ? ROLE_LABELS[cue.meta.role] : null;
	const giveBack = () => patchCue(update, cue.id, (c) => {
		const {manual: _m, desactive: _d, ...rest} = c;
		return {...rest, locked: false};
	}, true);
	const origin = cue.locked ? 'Verrouillé : l’IA n’y touche plus.' : cue.manual ? 'Retouché à la main : l’IA n’y touche plus.' : 'Choix de l’IA.';
	return (
		<div className="ch-editor" onPointerDown={(e) => e.stopPropagation()}>
			<div className="ch-editor-head">
				{titre ? <b title={TARGET_TYPES[cue.cible.type]}>{targetLabel(reel, cue.cible)}</b> : <span className="muted">Réglages du mouvement</span>}
				{role && titre ? <span className="ch-role">{role}</span> : null}
				<span className="grow" />
				<LockToggle locked={cue.locked} onChange={(v) => patchCue(update, cue.id, (c) => ({...c, locked: v}), true)} />
				{onClose ? <button type="button" className="small ghost" title="Fermer" onClick={onClose}>✕</button> : null}
			</div>
			<p className="ch-raison"><b>{origin}</b> {cue.raison}</p>
			<MoveEditor label="Entrée" move={cue.entree} onChange={(m) => set((c) => ({...c, entree: m}))} />
			<MoveEditor label="Sortie" move={cue.sortie} sortie onChange={(m) => set((c) => ({...c, sortie: m}))} />
			<div className="ch-editor-foot">
				<label title="Le mouvement ne s’applique plus : l’élément garde son animation d’origine">
					<input type="checkbox" checked={!!cue.desactive} onChange={(e) => set((c) => ({...c, desactive: e.target.checked}))} /> Désactiver
				</label>
				{seek ? <button type="button" className="small" title="Aller juste avant l’entrée" onClick={() => seek(Math.max(0, (at ?? cue.at) - 0.4))}>▶ Revoir</button> : null}
				{cue.manual || cue.locked || cue.desactive ? (
					<button type="button" className="small ghost" title="L’IA pourra de nouveau le recalculer (« Refaire la chorégraphie »)" onClick={giveBack}>Rendre à l’IA</button>
				) : null}
			</div>
		</div>
	);
};

// ---------- deplacer / raccourcir l'element vise ----------
type Mode = 'move' | 'start' | 'end';
const MIN_LEN = 0.3;
/** Deplacements possibles selon l'element : les sous-titres suivent la voix (aucun) ; une scene suit son mot. */
const canDrag = (c: CueTarget, mode: Mode) => c.type !== 'caption' && !(c.type === 'design' && mode === 'start');

/** Deplace (d secondes) ou raccourcit l'element vise ; l'element est marque retouche (manual), le cache du mouvement suit. */
export const moveTarget = (r: ReelDoc, cue: Cue, mode: Mode, d: number): ReelDoc => {
	const c = cue.cible;
	const total = reelDuration(r);
	// temps ACTUEL de l'element (celui que la piste affiche) : cue.at n'est qu'un cache, qui peut dater d'avant une coupe
	const now = targetTimes(r, total).get(targetKey(c));
	let at = now?.at ?? cue.at;
	let len = now?.duration ?? cue.duree;
	const shift = (a: number, l: number): [number, number] => {
		if (mode === 'move') return [Math.max(0, Math.min(total - 0.1, a + d)), l];
		if (mode === 'start') {
			const na = Math.max(0, Math.min(a + l - MIN_LEN, a + d));
			return [na, a + l - na];
		}
		return [a, Math.max(MIN_LEN, Math.min(total - a, l + d))];
	};
	let next = r;
	if (c.type === 'graphics' || c.type === 'broll' || c.type === 'vector') {
		const key = c.type === 'graphics' ? 'graphics' : c.type === 'broll' ? 'broll' : 'vectors';
		const list = (r[key] ?? []) as {id: string; at: number; duration: number}[];
		const item = list.find((x) => x.id === c.id);
		if (!item) return r;
		[at, len] = shift(item.at, item.duration);
		at = +at.toFixed(2);
		len = +len.toFixed(2);
		next = {...r, [key]: list.map((x) => (x.id === c.id ? touched({...x, at, duration: len}) : x))};
	} else if (c.type === 'design') {
		const s = r.styleScenes?.find((x) => x.id === c.id);
		if (!s) return r;
		if (mode === 'end') {
			len = +Math.max(MIN_LEN, s.duration + d).toFixed(2);
			next = {...r, styleScenes: r.styleScenes!.map((x) => (x.id === c.id ? touched({...x, duration: len}) : x))};
		} else {
			// une scene est ancree a un mot : elle va au mot dit le plus proche du nouvel instant
			const words = timedWords(r).filter((w) => !w.hide && w.w.trim());
			const want = at + d;
			const w = words.reduce<(typeof words)[number] | null>((best, x) => (!best || Math.abs(x.outStart - want) < Math.abs(best.outStart - want) ? x : best), null);
			if (!w) return r;
			at = w.outStart;
			next = {...r, styleScenes: r.styleScenes!.map((x) => (x.id === c.id ? touched({...x, clip: w.clip, index: w.index}) : x))};
		}
	} else if (c.type === 'banner') {
		const b = r.banner;
		[at, len] = shift(b.start, (b.end ?? total) - b.start);
		at = +at.toFixed(2);
		len = +len.toFixed(2);
		// bandeau « jusqu'a la fin » : il le reste tant qu'on ne tire pas sa fin
		const end = b.end === null && mode !== 'end' ? null : +(at + len).toFixed(2);
		if (end === null) len = total - at;
		next = {...r, banner: {...b, start: at, end, manual: true} as ReelDoc['banner']};
	} else return r;
	const ch = next.choreography;
	return ch ? {...next, choreography: {...ch, cues: ch.cues.map((x) => (x.id === cue.id ? {...x, at: +at.toFixed(3), duree: +len.toFixed(3)} : x))}} : next;
};

export type ChoreoLaneProps = {reel: ReelDoc; t: number; zoom: number; x: (s: number) => number; onSeek: (s: number) => void; update?: Update};
type Drag = {id: string; mode: Mode; x0: number; dx: number; moved: boolean};

export const ChoreoLane: React.FC<ChoreoLaneProps> = ({reel, zoom, x, onSeek, update}) => {
	const sel = useCueSelection();
	const [drag, setDrag] = useState<Drag | null>(null);
	const [pop, setPop] = useState<{id: string; left: number; bottom: number} | null>(null);
	const total = useMemo(() => reelDuration(reel), [reel]);
	const times = useMemo(() => targetTimes(reel, total), [reel, total]);
	const cues = reel.choreography?.cues ?? [];
	// deux mouvements qui se chevauchent : le second passe sur une demi-ligne
	const placed = useMemo(() => {
		const out: {cue: Cue; at: number; len: number; low: boolean}[] = [];
		let end = -1;
		for (const cue of [...cues].sort((a, b) => (times.get(targetKey(a.cible))?.at ?? a.at) - (times.get(targetKey(b.cible))?.at ?? b.at))) {
			const tt = times.get(targetKey(cue.cible));
			if (!tt) continue;
			const low = tt.at < end;
			out.push({cue, at: tt.at, len: tt.duration, low});
			if (!low) end = tt.at + tt.duration;
		}
		return out;
	}, [cues, times]);
	if (!cues.length) return <span className="ch-empty">Aucun mouvement — Plus → Chorégraphie pour que l’IA les propose</span>;
	const locked = !!reel.choreography?.locked;

	const start = (e: React.PointerEvent, cue: Cue, mode: Mode) => {
		e.stopPropagation();
		try {
			(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
		} catch {}
		setDrag({id: cue.id, mode, x0: e.clientX, dx: 0, moved: false});
	};
	const move = (e: React.PointerEvent) => {
		if (!drag) return;
		const dx = e.clientX - drag.x0;
		setDrag({...drag, dx, moved: drag.moved || Math.abs(dx) > 3});
	};
	const end = (e: React.PointerEvent, cue: Cue, at: number) => {
		e.stopPropagation();
		const d = drag;
		setDrag(null);
		if (!d || d.id !== cue.id) return;
		if (!d.moved) {
			// clic : choisir ce mouvement (fenetre de reglage au-dessus de la piste) et aller a son entree
			selectCue(cue.id);
			const box = (e.currentTarget as HTMLElement).closest('.ch-cue')?.getBoundingClientRect();
			if (box) setPop({id: cue.id, left: Math.max(8, Math.min(window.innerWidth - 348, box.left)), bottom: Math.max(8, window.innerHeight - box.top + 6)});
			onSeek(at);
			return;
		}
		if (!update || !canDrag(cue.cible, d.mode)) return;
		update((r) => moveTarget(r, cue, d.mode, d.dx / zoom));
	};

	const current = pop ? cues.find((c) => c.id === pop.id) : null;
	return (
		<>
			{placed.map(({cue, at, len, low}) => {
				const [din, dout] = cueDurations(cue, len);
				// un sous-titre ne se deplace pas (il suit la voix) : il ne bouge pas non plus pendant le glisser
				const dx = drag?.id === cue.id && drag.moved && canDrag(cue.cible, drag.mode) ? drag.dx : 0;
				const mode = drag?.id === cue.id ? drag.mode : null;
				const left = x(at) + (mode === 'move' || mode === 'start' ? dx : 0);
				const width = Math.max(6, x(len) + (mode === 'end' ? dx : mode === 'start' ? -dx : 0));
				const cls = ['ch-cue', low ? 'low' : '', sel === cue.id ? 'sel' : '', cue.locked ? 'locked' : '', cue.manual ? 'manual' : '',
					cue.desactive ? 'off' : '', cue.cible.type === 'caption' ? 'cap' : ''].filter(Boolean).join(' ');
				const how = cue.desactive ? 'désactivé' : `entrée ${moveSummary(cue.entree)} · sortie ${moveSummary(cue.sortie)}`;
				return (
					<div key={cue.id} className={cls} style={{left, width}}
						title={`${targetLabel(reel, cue.cible)} — ${how}\n${cue.raison}\n\nClic : régler · glisser : déplacer l’élément · bords : raccourcir${cue.cible.type === 'caption' ? ' (les sous-titres suivent la voix : ils ne se déplacent pas)' : ''}`}
						onPointerDown={(e) => start(e, cue, 'move')} onPointerMove={move} onPointerUp={(e) => end(e, cue, at)}>
						{din > 0 && !cue.desactive ? <i className="ch-in" style={{width: Math.min(width, x(din))}} /> : null}
						{dout > 0 && !cue.desactive ? <i className="ch-out" style={{width: Math.min(width, x(dout))}} /> : null}
						<span>{cue.locked ? '🔒 ' : cue.manual ? '✎ ' : ''}{MOVE_ICONS[cue.desactive ? 'aucune' : cue.entree.type]} {MOVE_LABELS[cue.entree.type].split(' ')[0]}</span>
						{canDrag(cue.cible, 'start') ? <em className="ch-h l" title="Début de l’élément" onPointerDown={(e) => start(e, cue, 'start')} onPointerMove={move} onPointerUp={(e) => end(e, cue, at)} /> : null}
						{canDrag(cue.cible, 'end') ? <em className="ch-h r" title="Fin de l’élément" onPointerDown={(e) => start(e, cue, 'end')} onPointerMove={move} onPointerUp={(e) => end(e, cue, at)} /> : null}
					</div>
				);
			})}
			{pop && current && update ? (
				<div className="ch-pop" style={{left: pop.left, bottom: pop.bottom}} onPointerDown={(e) => e.stopPropagation()} onPointerUp={(e) => e.stopPropagation()}
					onKeyDown={(e) => e.key === 'Escape' && setPop(null)}>
					{locked ? <p className="muted ch-note">Chorégraphie verrouillée : l’IA ne la refait plus, tes réglages restent possibles.</p> : null}
					<CueEditor reel={reel} cue={current} update={update} at={times.get(targetKey(current.cible))?.at}
						seek={onSeek} onClose={() => setPop(null)} />
					<p className="muted ch-note">Tous les mouvements : Plus → Chorégraphie.</p>
				</div>
			) : null}
		</>
	);
};
