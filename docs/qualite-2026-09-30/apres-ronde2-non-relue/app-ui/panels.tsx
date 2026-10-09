import React, {useEffect, useMemo, useRef, useState} from 'react';
import {timedWords, videoSegments} from '../../remotion/src/timeline';
import {FONT_FILES, type Clip, type ReelDoc, type Source, type Suggestions} from '../../remotion/src/types';
import {api, fmt, useJob, type Job} from './api';
import type {TakeOption} from './edit';
import {ClientCard, DeclinaisonsCard, ProjectTools, SaveStyleCard, TemplateGrid, type Template} from './panels2';
import {DesignPanel} from './design-panel';
import {LockToggle, withLock} from './lock';

type Update = (fn: (r: ReelDoc) => ReelDoc) => void;
const PARTS: Record<string, string> = {fidelite: 'Texte', fluidite: 'Fluidité', jeu: 'Jeu', image: 'Image', son: 'Son'};

const Bars: React.FC<{parts: Record<string, number>}> = ({parts}) => (
	<div className="bars">
		{Object.entries(PARTS).map(([k, label]) =>
			parts[k] !== undefined ? (
				<div key={k} title={`${label} : ${Math.round(parts[k] * 100)} %`}>
					<span>{label}</span>
					<i style={{width: `${Math.round(parts[k] * 100)}%`}} />
				</div>
			) : null,
		)}
	</div>
);

// ---------------- Plan selectionne ----------------
export const PlanPanel: React.FC<{
	reel: ReelDoc; clip: Clip | null; takes: TakeOption[]; blocks: Record<string, string>; t: number;
	seek: (s: number) => void; onTake: (i: number) => void; onTrim: (side: 'in' | 'out', d: number) => void;
	onPatch: (p: Partial<Clip>) => void; onMove: (dir: -1 | 1) => void; onCompare: () => void; onAutoAngles: () => void; anglesBusy: boolean;
}> = ({reel, clip, takes, blocks, seek, onTake, onTrim, onPatch, onMove, onCompare, onAutoAngles, anglesBusy}) => {
	if (!clip) return <p className="muted">Clique un plan dans la timeline pour le régler.</p>;
	const seg = videoSegments(reel).find((s) => s.clip === clip.id);
	const cur = takes[clip.choice ?? 0];
	const color = clip.color ?? {auto: true, exposure: 0, temperature: 0};
	const f = 1 / reel.fps;
	const group = reel.sources[clip.source]?.sync?.group;
	const angles = group ? Object.entries(reel.sources).filter(([, s]) => s.sync?.group === group) : [];
	const speed = clip.speed ?? 1;
	return (
		<>
			{angles.length > 1 ? (
				<div className="card">
					<h3>Angle <small>multicaméra — le son reste celui de la prise</small></h3>
					<div className="presets">
						{angles.map(([id, s]) => (
							<button key={id} className={`small${(clip.angle ?? clip.source) === id ? ' primary' : ''}`} onClick={() => onPatch({angle: id === clip.source ? null : id})}>{s.name}</button>
						))}
					</div>
					<button className="small" disabled={anglesBusy} onClick={onAutoAngles}>{anglesBusy ? 'Analyse…' : 'Angles automatiques (qui parle) pour tout le montage'}</button>
				</div>
			) : null}
			<div className="card">
				<h3>{blocks[clip.block] ?? clip.block}<small>{reel.sources[clip.source]?.name} · {clip.in.toFixed(2)} → {clip.out.toFixed(2)} s</small></h3>
				<div className="clip-text">{clip.words.filter((w) => !w.cut).map((w) => w.w).join(' ')}</div>
				<div className="row">
					<button className="small" onClick={() => seg && seek(seg.out_start)}>▶ Voir le plan</button>
					<button className="small" onClick={() => onMove(-1)}>← Avancer dans le montage</button>
					<button className="small" onClick={() => onMove(1)}>Reculer →</button>
				</div>
				{/* V2 : verrou du plan (Clip.locked) = ses mots en couleur et ses emojis ne sont plus changes par l'IA */}
				<div className="row">
					<LockToggle locked={clip.locked} label onChange={(v) => onPatch({locked: v || undefined})}
						title={clip.locked ? 'Mots en couleur et emojis de ce plan figés : l’IA et les changements de style n’y touchent plus. Clique pour déverrouiller.'
							: 'Figer les mots en couleur et les emojis de ce plan : l’IA et les changements de style n’y toucheront plus.'} />
					<span className="muted">{clip.locked ? 'Mots en couleur et emojis de ce plan figés.' : 'Mots en couleur et emojis de ce plan : choisis par l’IA.'}</span>
				</div>
			</div>
			<div className="card">
				<h3>Prise <small>{takes.length} disponible(s)</small></h3>
				<div className="row">
					<select className="grow" value={clip.choice ?? 0} onChange={(e) => onTake(Number(e.target.value))} disabled={takes.length < 2}>
						{takes.map((o, k) => <option key={k} value={k}>{o.name} — note {o.score.toFixed(2)}{k === 0 ? ' (choix auto)' : ''}</option>)}
					</select>
					<button className="small primary" disabled={takes.length < 2} onClick={onCompare}>Comparer</button>
				</div>
				{cur ? (
					<>
						<Bars parts={cur.parts} />
						{cur.notes.length ? <div className="flag">{cur.notes.join(' · ')}</div> : null}
					</>
				) : null}
			</div>
			<div className="card">
				<h3>Coupes</h3>
				<div className="row"><label>Début</label>
					<button className="small" onClick={() => onTrim('in', -0.25)}>−0,25 s</button>
					<button className="small" onClick={() => onTrim('in', -f)}>−1 image</button>
					<button className="small" onClick={() => onTrim('in', f)}>+1 image</button>
					<button className="small" onClick={() => onTrim('in', 0.25)}>+0,25 s</button></div>
				<div className="row"><label>Fin</label>
					<button className="small" onClick={() => onTrim('out', -0.25)}>−0,25 s</button>
					<button className="small" onClick={() => onTrim('out', -f)}>−1 image</button>
					<button className="small" onClick={() => onTrim('out', f)}>+1 image</button>
					<button className="small" onClick={() => onTrim('out', 0.25)}>+0,25 s</button></div>
				<div className="row"><label><input type="checkbox" checked={clip.tighten} onChange={(e) => onPatch({tighten: e.target.checked})} /> Resserrer les pauses</label></div>
				<div className="row"><label>Vitesse (×{speed.toFixed(2)})</label>
					{[0.5, 0.75, 1, 1.25, 1.5, 2].map((v) => <button key={v} className={`small${speed === v ? ' primary' : ''}`} onClick={() => onPatch({speed: v === 1 ? undefined : v})}>×{v}</button>)}</div>
				<div className="row"><label><input type="checkbox" checked={!!clip.mute} onChange={(e) => onPatch({mute: e.target.checked || undefined})} /> Plan muet (seule la musique joue)</label></div>
				{speed !== 1 && !clip.mute ? <p className="muted">Le son suit la vitesse (voix accélérée ou ralentie) : un plan muet est souvent préférable.</p> : null}
			</div>
			<div className="card">
				<h3>Son du raccord <small>J-cut / L-cut</small></h3>
				<div className="row"><label>J-cut ({(clip.audioLead ?? 0).toFixed(2)} s)</label>
					<input type="range" min={0} max={1.2} step={0.02} value={clip.audioLead ?? 0} onChange={(e) => onPatch({audioLead: Number(e.target.value)})} /></div>
				<p className="muted">Le son de ce plan commence avant son image (on entend la suite avant de la voir).</p>
				<div className="row"><label>L-cut ({(clip.audioTail ?? 0).toFixed(2)} s)</label>
					<input type="range" min={0} max={1.2} step={0.02} value={clip.audioTail ?? 0} onChange={(e) => onPatch({audioTail: Number(e.target.value)})} /></div>
				<p className="muted">Le son de ce plan continue sous l'image du plan suivant.</p>
			</div>
			<div className="card">
				<h3>Lumière et couleur</h3>
				<div className="row"><label><input type="checkbox" checked={color.auto} onChange={(e) => onPatch({color: {...color, auto: e.target.checked}})} /> Harmoniser avec les autres plans</label></div>
				<div className="row"><label>Exposition ({color.exposure > 0 ? '+' : ''}{color.exposure.toFixed(2)})</label>
					<input type="range" min={-1} max={1} step={0.05} value={color.exposure} onChange={(e) => onPatch({color: {...color, exposure: Number(e.target.value)}})} /></div>
				<div className="row"><label>Température ({color.temperature > 0 ? 'chaud' : color.temperature < 0 ? 'froid' : 'neutre'})</label>
					<input type="range" min={-1} max={1} step={0.05} value={color.temperature} onChange={(e) => onPatch({color: {...color, temperature: Number(e.target.value)}})} /></div>
			</div>
		</>
	);
};

// ---------------- Comparateur de prises ----------------
export const Compare: React.FC<{takes: TakeOption[]; current: number; proxy: (source: string) => string; onChoose: (i: number) => void; onClose: () => void}> = ({takes, current, proxy, onChoose, onClose}) => {
	const refs = useRef<(HTMLVideoElement | null)[]>([]);
	const [listen, setListen] = useState(current);
	const playAll = () =>
		takes.forEach((o, i) => {
			const v = refs.current[i];
			if (!v) return;
			v.currentTime = o.in;
			v.muted = i !== listen;
			v.play();
		});
	const stopAll = () => refs.current.forEach((v) => v?.pause());
	useEffect(() => {
		refs.current.forEach((v, i) => v && (v.muted = i !== listen));
	}, [listen]);
	return (
		<div className="modal" onClick={onClose}>
			<div className="modal-box" onClick={(e) => e.stopPropagation()}>
				<div className="row" style={{justifyContent: 'space-between'}}>
					<h3 style={{margin: 0}}>Comparer les prises — calées sur la même réplique</h3>
					<div className="row">
						<button className="primary" onClick={playAll}>▶ Lire toutes</button>
						<button onClick={stopAll}>■ Stop</button>
						<button onClick={onClose}>Fermer</button>
					</div>
				</div>
				<div className="compare">
					{takes.map((o, i) => (
						<div key={i} className={`cmp${i === current ? ' cur' : ''}`}>
							<video ref={(el) => { refs.current[i] = el; }} src={proxy(o.source)} preload="auto" muted playsInline
								onLoadedMetadata={(e) => ((e.target as HTMLVideoElement).currentTime = o.in)}
								onTimeUpdate={(e) => {
									const v = e.target as HTMLVideoElement;
									if (v.currentTime >= o.out) v.pause();
								}} />
							<b>{o.name}</b>
							<span className="muted">note {o.score.toFixed(2)}{i === current ? ' · prise actuelle' : ''}</span>
							<Bars parts={o.parts} />
							{o.notes.length ? <div className="flag">{o.notes.join(' · ')}</div> : null}
							<div className="row">
								<button className={`small${listen === i ? ' primary' : ''}`} onClick={() => setListen(i)}>🔊 Écouter</button>
								<button className="small primary" disabled={i === current} onClick={() => onChoose(i)}>Choisir</button>
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
};

// ---------------- Texte (montage par le texte) ----------------
const EMPTY_SUG: Suggestions = {banners: [], words: {}, emojis: {}};

/** Accepte (ou refuse) des propositions de l'IA : mots en couleur et emojis. */
const resolveSuggestions = (r: ReelDoc, accept: boolean, only?: {clip: string; index?: number}): ReelDoc => {
	const sug = r.suggestions ?? EMPTY_SUG;
	const words = {...sug.words};
	const emojis = {...sug.emojis};
	const clips = r.clips.map((c) => {
		if (only && only.clip !== c.id) return c;
		const pick = (words[c.id] ?? []).filter((i) => only?.index === undefined || i === only.index);
		const em = (emojis[c.id] ?? []).filter(([i]) => only?.index === undefined || i === only.index);
		words[c.id] = (words[c.id] ?? []).filter((i) => !pick.includes(i));
		emojis[c.id] = (emojis[c.id] ?? []).filter((e) => !em.includes(e));
		if (!accept) return c;
		return {...c, words: c.words.map((w, i) => (pick.includes(i) ? {...w, hl: true} : w)), emojis: [...(c.emojis ?? []), ...em]};
	});
	return {...r, clips, suggestions: {...sug, words, emojis}};
};

export const TextPanel: React.FC<{reel: ReelDoc; blocks: Record<string, string>; t: number; seek: (s: number) => void; update: Update; current: string;
	onWords: (clip: string, idx: number[], patch: {cut?: boolean; hl?: boolean; hide?: boolean; w?: string}) => void}> = ({reel, blocks, t, seek, onWords, update, current}) => {
	const [sel, setSel] = useState<{clip: string; a: number; b: number} | null>(null);
	const words = useMemo(() => timedWords(reel), [reel]);
	const pos = useMemo(() => new Map(words.map((w) => [`${w.clip}-${w.index}`, w])), [words]);
	const idx = sel ? Array.from({length: sel.b - sel.a + 1}, (_, k) => sel.a + k) : [];
	const selClip = sel ? reel.clips.find((c) => c.id === sel.clip) : null;
	const allCut = selClip ? idx.every((i) => selClip.words[i]?.cut) : false;
	const sug = reel.suggestions ?? EMPTY_SUG;
	const nWords = Object.values(sug.words).reduce((a, v) => a + v.length, 0);
	const nEmojis = Object.values(sug.emojis).reduce((a, v) => a + v.length, 0);
	const selSug = sel && idx.length === 1 && (sug.words[sel.clip] ?? []).includes(sel.a);
	// nouvelle passe de l'IA : mots, emojis et bandeaux remplaces ; les propositions de plans de coupe (suggestions.broll) restent
	const [aiJob, setAiJob] = useJob((j) => update((r) => ({...r, suggestions: {...(r.suggestions ?? EMPTY_SUG), ...j.result, banners: j.result.banners ?? []}})));
	const mode = reel.aiMode ?? 'auto';
	return (
		<>
			<div className="card">
				<h3>IA <small>mots en couleur, emojis, bandeaux</small></h3>
				<div className="row">
					<label>Choix de l'IA</label>
					<button className={`small${mode === 'suggestion' ? ' primary' : ''}`} onClick={() => update((r) => ({...r, aiMode: 'suggestion'}))}>Proposer (je valide)</button>
					<button className={`small${mode === 'auto' ? ' primary' : ''}`} onClick={() => update((r) => ({...r, aiMode: 'auto'}))}>Appliquer automatiquement</button>
				</div>
				<div className="row">
					{nWords || nEmojis ? <span className="muted grow">{nWords} mot(s) et {nEmojis} emoji(s) proposés, en pointillé ci-dessous</span> : <span className="muted grow">Aucune proposition en attente.</span>}
					<button className="small primary" disabled={!nWords && !nEmojis} onClick={() => update((r) => resolveSuggestions(r, true))}>Tout accepter</button>
					<button className="small" disabled={!nWords && !nEmojis} onClick={() => update((r) => resolveSuggestions(r, false))}>Tout refuser</button>
					<button className="small" disabled={aiJob?.status === 'running'} onClick={async () => setAiJob(await api(`/api/reels/${current}/ia`, 'POST'))}>{aiJob?.status === 'running' ? 'L’IA lit…' : '↻ Relancer l’IA'}</button>
				</div>
				{aiJob?.status === 'failed' ? <p className="err">{aiJob.error}</p> : null}
			</div>
			<div className="word-edit">
				{sel && selClip ? (
					<>
						<div className="muted">{idx.length} mot(s) : « {idx.map((i) => selClip.words[i]?.w).join(' ').slice(0, 80)} »</div>
						{selSug ? (
							<div className="row">
								<span className="muted">Proposition de l'IA :</span>
								<button className="small primary" onClick={() => update((r) => resolveSuggestions(r, true, {clip: sel.clip, index: sel.a}))}>Accepter</button>
								<button className="small" onClick={() => update((r) => resolveSuggestions(r, false, {clip: sel.clip, index: sel.a}))}>Refuser</button>
							</div>
						) : null}
						<div className="row">
							<button className="small primary" onClick={() => onWords(sel.clip, idx, {cut: !allCut})}>{allCut ? 'Rétablir dans le montage' : '✂ Couper du montage'}</button>
							<button className="small" onClick={() => onWords(sel.clip, idx, {hl: !selClip.words[sel.a]?.hl})}>Couleur</button>
							<button className="small" onClick={() => onWords(sel.clip, idx, {hide: !selClip.words[sel.a]?.hide})}>Masquer le sous-titre</button>
							<button className="small" onClick={() => setSel(null)}>Fermer</button>
						</div>
						{idx.length === 1 ? (
							<div className="row"><input type="text" className="grow" value={selClip.words[sel.a]?.w ?? ''} onChange={(e) => onWords(sel.clip, idx, {w: e.target.value})} /></div>
						) : null}
					</>
				) : (
					<span className="muted">Clique un mot (Maj + clic pour une phrase entière), puis « Couper du montage » : la vidéo suit. Les mots coupés restent visibles, barrés, pour les rétablir.</span>
				)}
			</div>
			{reel.clips.map((c) => (
				<div className="card" key={c.id}>
					<h3>{blocks[c.block] ?? c.block}</h3>
					<div className="words">
						{c.words.map((w, i) => {
							const tw = pos.get(`${c.id}-${i}`);
							const now = tw && t >= tw.outStart && t < tw.outEnd;
							const inSel = sel && sel.clip === c.id && i >= sel.a && i <= sel.b;
							const proposed = (sug.words[c.id] ?? []).includes(i);
							const emo = (sug.emojis[c.id] ?? []).find(([k]) => k === i);
							return (
								<React.Fragment key={i}>
									<span className={`w${w.hl ? ' hl' : ''}${w.hide ? ' hide' : ''}${w.cut ? ' cut' : ''}${now ? ' now' : ''}${inSel ? ' sel' : ''}${proposed ? ' sug' : ''}`}
										title={proposed ? "Proposé par l'IA : clique puis Accepter" : undefined}
										onClick={(e) => {
											if (e.shiftKey && sel && sel.clip === c.id) setSel({clip: c.id, a: Math.min(sel.a, i), b: Math.max(sel.b, i)});
											else setSel({clip: c.id, a: i, b: i});
											if (tw) seek(tw.outStart);
										}}>{w.w}</span>
									{emo ? <button className="emo-sug" title="Emoji proposé : cliquer pour l'accepter"
										onClick={() => update((r) => {
											const s = r.suggestions ?? EMPTY_SUG;
											return {...r, clips: r.clips.map((k) => (k.id === c.id ? {...k, emojis: [...(k.emojis ?? []), emo]} : k)),
												suggestions: {...s, emojis: {...s.emojis, [c.id]: (s.emojis[c.id] ?? []).filter((x) => x !== emo)}}};
										})}>+{emo[1]}</button> : null}
								</React.Fragment>
							);
						})}
					</div>
				</div>
			))}
		</>
	);
};

// ---------------- Style ----------------
type StylesInfo = {montage: Template[]; captions: {id: string; name: string; description: string; style: Partial<ReelDoc['style']>}[];
	music: {id: string; name: string; file: string}[]; generated: string[]; sfx: string[]};
const GRADES = {aucun: 'Aucun', chaud: 'Chaud', froid: 'Froid', contraste: 'Contrasté', cinema: 'Cinéma', noirblanc: 'Noir et blanc'};
const FLASHES = {blanc: 'Flash blanc', glitch: 'Glitch', lumiere: 'Fuite de lumière'};
const VOICES = {naturel: 'Naturel', radio: 'Radio (présence, compression)', podcast: 'Podcast (chaud)', aucun: 'Aucun traitement'};

export const StylePanel: React.FC<{reel: ReelDoc; update: Update; t: number; total: number; busy: boolean; current: string; onTemplate: (id: string) => void;
	onStylesChanged?: () => unknown; seek?: (s: number) => void}> = ({reel, update, t, total, busy, current, onTemplate, onStylesChanged, seek = () => undefined}) => {
	const [styles, setStyles] = useState<StylesInfo | null>(null);
	const load = () => api('/api/styles').then(setStyles).catch(() => undefined);
	/** Mes styles ajoutes, renommes ou supprimes : on relit la liste (ici et dans la Revision). */
	const stylesChanged = async () => {
		await load();
		await onStylesChanged?.();
	};
	useEffect(() => {
		load();
	}, []);
	const [musicJob, setMusicJob] = useJob((j) => {
		load();
		update((r) => ({...r, music: {...(r.music ?? {mood: null, volume: 0.2}), enabled: true, file: j.result.file}}));
	});
	const [introJob, setIntroJob] = useJob((j) => update((r) => ({...r, intro: {...(r.intro ?? {text: '', duration: 2.5}), enabled: true, file: j.result.fichier}})));
	const s = reel.style;
	const set = <K extends keyof ReelDoc['style']>(k: K, v: ReelDoc['style'][K]) => update((r) => ({...r, style: {...r.style, [k]: v}}));
	const music = reel.music ?? {enabled: false, mood: null, file: null, volume: 0.2};
	const sfx = reel.sfx ?? {enabled: false, transition: null, highlight: null, highlightGap: 4, cta: null, start: null, volume: 0.6};
	const fx = reel.effects ?? {grain: 0, vignette: 0, grade: 'aucun'};
	const audio = reel.audio ?? {voice: 'naturel' as const, roomTone: false, declip: false, denoise: true};
	const intro = reel.intro ?? {enabled: false, text: '', file: null, duration: 2.5};
	const setMusic = (p: Partial<typeof music>) => update((r) => ({...r, music: {...music, ...p}}));
	const setSfx = (p: Partial<typeof sfx>) => update((r) => ({...r, sfx: {...sfx, ...p}}));
	const setFx = (p: Partial<typeof fx>) => update((r) => ({...r, effects: {...fx, ...p}}));
	const setAudio = (p: Partial<typeof audio>) => update((r) => ({...r, audio: {...audio, ...p}}));
	const setIntro = (p: Partial<typeof intro>) => update((r) => ({...r, intro: {...intro, ...p}}));
	const sfxSelect = (value: string | null, onChange: (v: string | null) => void) => (
		<select className="grow" value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}>
			<option value="">Aucun</option>
			{(styles?.sfx ?? []).map((n) => <option key={n} value={n}>{n}</option>)}
		</select>
	);
	const moodId = styles?.music.find((m) => m.file === music.file)?.id ?? music.mood ?? 'energique';
	return (
		<>
			<div className="card">
				<h3>Style de montage <small>applique tout d'un coup</small></h3>
				<TemplateGrid className="templates" templates={styles?.montage ?? []} current={reel.template} disabled={busy} onApply={(tpl) => onTemplate(tpl.id)} onChanged={stylesChanged} />
				<p className="muted">Une version est sauvegardée avant chaque changement de style. Le montage (prises, coupes) est conservé.</p>
			</div>
			<SaveStyleCard reel={reel} reelKey={current} templates={styles?.montage ?? []} onSaved={async (tpl) => {
				// ce reel porte maintenant ce style (le serveur l'a note dans le reel)
				update((r) => ({...r, template: tpl.id}));
				await stylesChanged();
			}} />
			<ClientCard reel={reel} update={update} />
			<DesignPanel reel={reel} update={update} current={current} />
			<div className="card">
				<h3>Sous-titres</h3>
				<div className="presets">
					{(styles?.captions ?? []).map((p) => (
						<button key={p.id} className={`small${s.preset === p.id ? ' primary' : ''}`} title={p.description} onClick={() => update((r) => ({...r, style: {...r.style, ...p.style, preset: p.id}}))}>{p.name}</button>
					))}
				</div>
				<div className="row"><label>Police</label>
					<select className="grow" value={s.font} onChange={(e) => set('font', e.target.value)}>{Object.keys(FONT_FILES).map((f) => <option key={f}>{f}</option>)}</select></div>
				<div className="row"><label>Taille ({s.size})</label><input type="range" min={36} max={170} value={s.size} onChange={(e) => set('size', Number(e.target.value))} /></div>
				<div className="row"><label>Hauteur ({Math.round(s.position * 100)} %)</label><input type="range" min={0.3} max={0.9} step={0.01} value={s.position} onChange={(e) => set('position', Number(e.target.value))} /></div>
				<div className="row"><label>Mots par écran</label>{[1, 2, 3, 4, 5, 6].map((n) => <button key={n} className={`small${s.maxWords === n ? ' primary' : ''}`} onClick={() => set('maxWords', n)}>{n}</button>)}</div>
				<div className="row"><label>Couleurs</label>
					texte <input type="color" value={s.color} onChange={(e) => set('color', e.target.value)} />
					mots clés <input type="color" value={s.highlight} onChange={(e) => set('highlight', e.target.value)} />
					contour <input type="color" value={s.stroke} onChange={(e) => set('stroke', e.target.value)} /></div>
				<div className="row"><label>Contour ({s.strokeWidth})</label><input type="range" min={0} max={24} value={s.strokeWidth} onChange={(e) => set('strokeWidth', Number(e.target.value))} /></div>
				<div className="row"><label>Options</label>
					<label className="inline"><input type="checkbox" checked={s.uppercase} onChange={(e) => set('uppercase', e.target.checked)} /> Majuscules</label>
					<label className="inline"><input type="checkbox" checked={s.pop} onChange={(e) => set('pop', e.target.checked)} /> Mot actif qui ressort</label>
					<label className="inline"><input type="checkbox" checked={!!reel.emoji?.enabled} onChange={(e) => update((r) => ({...r, emoji: {enabled: e.target.checked}}))} /> Emojis</label></div>
			</div>
			<div className="card">
				<h3>Voix <small>appliqué à l'export</small></h3>
				<div className="row"><label>Traitement</label>
					<select className="grow" value={audio.voice} onChange={(e) => setAudio({voice: e.target.value as 'naturel'})}>{Object.entries(VOICES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
				<div className="row">
					<label className="inline" title="Enlève le bruit de fond (IA locale), à l'aperçu comme à l'export"><input type="checkbox" checked={audio.denoise !== false} onChange={(e) => setAudio({denoise: e.target.checked})} /> Voix débruitée</label>
					<label className="inline"><input type="checkbox" checked={audio.roomTone} onChange={(e) => setAudio({roomTone: e.target.checked})} /> Fond d'ambiance (sans musique seulement)</label>
					<label className="inline"><input type="checkbox" checked={audio.declip} onChange={(e) => setAudio({declip: e.target.checked})} /> Réparer la saturation</label></div>
			</div>
			<div className="card">
				<h3>Musique <small>baisse automatiquement quand on parle</small></h3>
				<div className="row"><label><input type="checkbox" checked={music.enabled} onChange={(e) => setMusic({enabled: e.target.checked})} /> Musique</label></div>
				<div className="row"><label>Morceau</label>
					<select className="grow" value={music.file ?? ''} onChange={(e) => setMusic({file: e.target.value || null, enabled: !!e.target.value, mood: styles?.music.find((m) => m.file === e.target.value)?.id ?? music.mood})}>
						<option value="">Aucun</option>
						<optgroup label="Bibliothèque">{(styles?.music ?? []).map((m) => <option key={m.id} value={m.file}>{m.name}</option>)}</optgroup>
						{styles?.generated.length ? <optgroup label="Créées sur mesure">{styles.generated.map((f) => <option key={f} value={f}>{f.split('/').pop()}</option>)}</optgroup> : null}
					</select></div>
				<div className="row"><label>Volume ({Math.round(music.volume * 100)} %)</label><input type="range" min={0} max={0.5} step={0.01} value={music.volume} onChange={(e) => setMusic({volume: Number(e.target.value)})} /></div>
				<div className="row">
					<button className="small" disabled={musicJob?.status === 'running'} onClick={async () => setMusicJob(await api(`/api/reels/${current}/music`, 'POST', {mood: moodId, duration: total}))}>
						🎵 Créer une musique unique ({styles?.music.find((m) => m.id === moodId)?.name ?? 'ambiance'})</button>
					{musicJob?.status === 'running' ? <span className="muted">{musicJob.stage}… (environ 1 min)</span> : null}
					{musicJob?.status === 'failed' ? <span className="err">{musicJob.error}</span> : null}
				</div>
			</div>
			<div className="card">
				<h3>Bruitages</h3>
				<div className="row"><label><input type="checkbox" checked={sfx.enabled} onChange={(e) => setSfx({enabled: e.target.checked})} /> Activés</label></div>
				<div className="row"><label>Entre les parties</label>{sfxSelect(sfx.transition, (v) => setSfx({transition: v}))}</div>
				<div className="row"><label>Sur les mots clés</label>{sfxSelect(sfx.highlight, (v) => setSfx({highlight: v}))}</div>
				<div className="row"><label>Avant l'appel à l'action</label>{sfxSelect(sfx.cta, (v) => setSfx({cta: v}))}</div>
				<div className="row"><label>Au début</label>{sfxSelect(sfx.start, (v) => setSfx({start: v}))}</div>
				<div className="row"><label>Volume ({Math.round(sfx.volume * 100)} %)</label><input type="range" min={0} max={1} step={0.05} value={sfx.volume} onChange={(e) => setSfx({volume: Number(e.target.value)})} /></div>
				{(sfx.extra ?? []).length ? (
					<details>
						<summary className="muted">Bruitages posés un par un ({(sfx.extra ?? []).length})</summary>
						{[...(sfx.extra ?? [])].map((e, i) => ({e, i})).sort((a, b) => a.e.t - b.e.t).map(({e, i}) => (
							<div className="row" key={`${i}-${e.t}-${e.name}`}>
								<span className="grow">{fmt(e.t)} · {e.name.split('/').pop()?.replace(/\.(wav|ogg|mp3)$/i, '')}
									{e.reason ? <small className="muted"> — {e.reason}</small> : e.creative ? <small className="muted"> — proposé par l’IA</small> : null}</span>
								<LockToggle locked={e.locked} onChange={(v) => update((r) => ({...r, sfx: {...sfx, ...r.sfx!, extra: (r.sfx?.extra ?? []).map((x, k) => (k === i ? withLock(x, v) : x))}}))} />
								<button className="small" onClick={() => seek(e.t)}>▶</button>
								<button className="small" title="Retirer ce bruitage" onClick={() => update((r) => ({...r, sfx: {...sfx, ...r.sfx!, extra: (r.sfx?.extra ?? []).filter((_, k) => k !== i)}}))}>✕</button>
							</div>
						))}
					</details>
				) : null}
			</div>
			<div className="card">
				<h3>Bandeau d'accroche</h3>
				<div className="row"><label><input type="checkbox" checked={reel.banner.enabled} onChange={(e) => update((r) => ({...r, banner: {...r.banner, enabled: e.target.checked}}))} /> Afficher</label>
					<LockToggle label locked={reel.banner.locked} title={reel.banner.locked ? 'Bandeau figé : un changement de style ne l’allume ni ne l’éteint plus. Clique pour le libérer.'
						: 'Figer le bandeau : un changement de style ne l’allumera ni ne l’éteindra plus.'} onChange={(v) => update((r) => ({...r, banner: withLock(r.banner, v)}))} /></div>
				<textarea rows={2} style={{width: '100%'}} value={reel.banner.text} onChange={(e) => update((r) => ({...r, banner: {...r.banner, text: e.target.value}}))} />
				{reel.suggestions?.banners?.length ? (
					<div className="row"><label>Propositions de l'IA</label>
						{reel.suggestions.banners.map((b) => (
							<button key={b} className={`small${reel.banner.text === b ? ' primary' : ''}`} onClick={() => update((r) => ({...r, banner: {...r.banner, enabled: true, text: b}}))}>{b}</button>
						))}</div>
				) : null}
				<div className="row"><label>Durée</label>
					<button className={`small${reel.banner.end === null ? ' primary' : ''}`} onClick={() => update((r) => ({...r, banner: {...r.banner, end: null}}))}>Toute la vidéo</button>
					<button className={`small${reel.banner.end !== null ? ' primary' : ''}`} onClick={() => update((r) => ({...r, banner: {...r.banner, end: Math.max(1, Math.round(t * 10) / 10)}}))}>Jusqu'à maintenant ({fmt(t)})</button></div>
			</div>
			<div className="card">
				<h3>Titre d'ouverture 3D <small>rendu par Blender</small></h3>
				<div className="row"><label><input type="checkbox" checked={intro.enabled && !!intro.file} disabled={!intro.file} onChange={(e) => setIntro({enabled: e.target.checked})} /> Afficher au début</label></div>
				<div className="row"><input type="text" className="grow" placeholder="Texte du titre" value={intro.text} onChange={(e) => setIntro({text: e.target.value})} /></div>
				<div className="row"><label>Durée ({intro.duration.toFixed(1)} s)</label><input type="range" min={1} max={4} step={0.5} value={intro.duration} onChange={(e) => setIntro({duration: Number(e.target.value)})} /></div>
				<div className="row">
					<button className="small" disabled={!intro.text.trim() || introJob?.status === 'running'}
						onClick={async () => setIntroJob(await api(`/api/reels/${current}/intro`, 'POST', {text: intro.text, color: s.highlight, seconds: intro.duration}))}>🧊 Créer le titre 3D</button>
					{introJob?.status === 'running' ? <span className="muted">Blender travaille… (environ 30 s)</span> : null}
					{introJob?.status === 'failed' ? <span className="err">{introJob.error}</span> : null}
				</div>
			</div>
			<div className="card">
				<h3>Image</h3>
				<div className="row"><label><input type="checkbox" checked={reel.zoom.auto} onChange={(e) => update((r) => ({...r, zoom: {...r.zoom, auto: e.target.checked}}))} /> {reel.design?.mode==='hormozi'?'Zooms sur les mots forts':'Zooms à chaque coupe'}</label></div>
				<div className="row"><label>Intensité ({Math.round((reel.zoom.strength - 1) * 100)} %)</label><input type="range" min={1} max={1.4} step={0.01} value={reel.zoom.strength} onChange={(e) => update((r) => ({...r, zoom: {...r.zoom, strength: Number(e.target.value)}}))} /></div>
				<div className="row"><label>Poussée lente ({Math.round(reel.zoom.push * 100)} %)</label><input type="range" min={0} max={0.1} step={0.005} value={reel.zoom.push} onChange={(e) => update((r) => ({...r, zoom: {...r.zoom, push: Number(e.target.value)}}))} /></div>
				<div className="row"><label>Étalonnage</label><select className="grow" value={fx.grade} onChange={(e) => setFx({grade: e.target.value})}>{Object.entries(GRADES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
				<div className="row"><label>Grain ({Math.round(fx.grain * 100)} %)</label><input type="range" min={0} max={1} step={0.05} value={fx.grain} onChange={(e) => setFx({grain: Number(e.target.value)})} /></div>
				<div className="row"><label>Vignettage ({Math.round(fx.vignette * 100)} %)</label><input type="range" min={0} max={1} step={0.05} value={fx.vignette} onChange={(e) => setFx({vignette: Number(e.target.value)})} /></div>
				<div className="row"><label>Transition</label>
					<input type="checkbox" checked={reel.flash.enabled} onChange={(e) => update((r) => ({...r, flash: {...r.flash, enabled: e.target.checked}}))} />
					<select className="grow" value={reel.flash.kind ?? 'blanc'} onChange={(e) => update((r) => ({...r, flash: {enabled: true, kind: e.target.value as 'blanc'}}))}>{Object.entries(FLASHES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
				<div className="row"><label><input type="checkbox" checked={reel.progress.enabled} onChange={(e) => update((r) => ({...r, progress: {enabled: e.target.checked}}))} /> Barre de progression</label></div>
			</div>
		</>
	);
};

// ---------------- Recherche dans les rushs ----------------
type Hit = {source: string; name: string; t: number; score: number; why: string; text: string; proxy: string};
export const SearchPanel: React.FC<{reel: ReelDoc; update: Update; t: number; seek: (s: number) => void; current: string;
	addSources: (s: Record<string, Source>) => void; onCreated: (key: string) => void; onReload: () => void}> = (props) => (
	<>
		<SearchCard {...props} />
		<p className="muted">Les plans de coupe (bibliothèque, banque libre, IA par phrase) sont dans l'onglet <b>Ajouter</b>.</p>
		<ProjectTools reel={props.reel} onCreated={props.onCreated} onReload={props.onReload} />
	</>
);

const SearchCard: React.FC<{reel: ReelDoc; update: Update; t: number}> = ({reel, update, t}) => {
	const project = reel.project;
	const [q, setQ] = useState('');
	const [hits, setHits] = useState<Hit[] | null>(null);
	const [preview, setPreview] = useState<Hit | null>(null);
	const [job, setJob] = useJob((j) => setHits(j.result));
	const WHY: Record<string, string> = {image: 'image', parole: 'dit dans la prise', description: 'description du plan'};
	return (
		<>
			<div className="card">
				<h3>Chercher dans les rushs <small>en phrase naturelle</small></h3>
				<div className="row">
					<input type="text" className="grow" placeholder="ex. quand elle parle du salaire, plan extérieur, main sur le téléphone…" value={q}
						onChange={(e) => setQ(e.target.value)} onKeyDown={async (e) => e.key === 'Enter' && q.trim() && setJob(await api('/api/search', 'POST', {project, q}))} />
					<button className="primary small" disabled={!q.trim() || job?.status === 'running'} onClick={async () => setJob(await api('/api/search', 'POST', {project, q}))}>Chercher</button>
				</div>
				{job?.status === 'running' ? <p className="muted">Recherche… (la première fois, l'IA regarde toutes les prises : quelques minutes)</p> : null}
				{job?.status === 'failed' ? <p className="err">{job.error}</p> : null}
			</div>
			<div className="hits">
				{(hits ?? []).map((h, i) => (
					<div key={i} className="hit" onClick={() => setPreview(h)}>
						<img src={`/api/thumb?proxy=${encodeURIComponent(h.proxy)}&t=${h.t}`} alt="" />
						<div>
							<b>{h.name}</b> <span className="muted">à {fmt(h.t)} · {WHY[h.why] ?? h.why} · {Math.round(Math.min(1, h.score) * 100)} %</span>
							{h.text ? <div className="clip-text">{h.text}</div> : null}
						</div>
					</div>
				))}
				{hits && !hits.length ? <p className="muted">Aucun résultat.</p> : null}
			</div>
			{preview ? (
				<div className="modal" onClick={() => setPreview(null)}>
					<div className="modal-box small" onClick={(e) => e.stopPropagation()}>
						<video src={`/${preview.proxy}#t=${preview.t}`} controls autoPlay style={{width: '100%', maxHeight: '70vh'}} />
						<div className="row"><b>{preview.name}</b><span className="muted">à {fmt(preview.t)}</span>
							<button className="small primary" disabled={!reel.sources[preview.source]} title={reel.sources[preview.source] ? '' : 'Prise absente de ce reel'}
								onClick={() => {
									update((r) => ({...r, broll: [...(r.broll ?? []), {id: `b${Date.now().toString(36)}`, source: preview.source, in: Math.max(0, preview.t - 0.3), at: +t.toFixed(2), duration: 1.8}]}));
									setPreview(null);
								}}>Insérer en plan de coupe à {fmt(t)}</button>
							<button className="small" onClick={() => setPreview(null)}>Fermer</button></div>
					</div>
				</div>
			) : null}
		</>
	);
};

// ---------------- Versions ----------------
type Version = {file: string; date: string; name: string};
export const VersionsPanel: React.FC<{reel: ReelDoc; current: string; abFile: string | null; onRestore: (file: string) => void; onAB: (file: string | null) => void;
	onOpenReel: (rid: string) => void; onABReel: (rid: string) => void}> = ({reel, current, abFile, onRestore, onAB, onOpenReel, onABReel}) => {
	const [list, setList] = useState<Version[]>([]);
	const [name, setName] = useState('');
	useEffect(() => {
		api(`/api/reels/${current}/versions`).then(setList).catch(() => undefined);
	}, [current]);
	return (
		<>
			<DeclinaisonsCard reel={reel} current={current} onOpen={onOpenReel} onAB={onABReel} />
			<div className="card">
				<h3>Enregistrer une version</h3>
				<div className="row">
					<input type="text" className="grow" placeholder="ex. V2 après retours client" value={name} onChange={(e) => setName(e.target.value)} />
					<button className="small primary" onClick={async () => {
						const r = await api(`/api/reels/${current}/versions`, 'POST', {name: name || 'version'});
						setList(r.versions);
						setName('');
					}}>Enregistrer</button>
				</div>
				<p className="muted">Une version est aussi gardée automatiquement avant chaque export, changement de style ou restauration.</p>
			</div>
			{list.map((v) => (
				<div className="card version" key={v.file}>
					<div><b>{v.name}</b><div className="muted">{v.date}</div></div>
					<div className="row">
						<button className={`small${abFile === v.file ? ' primary' : ''}`} onClick={() => onAB(abFile === v.file ? null : v.file)}>{abFile === v.file ? 'Fin A/B' : 'Comparer A/B'}</button>
						<button className="small" onClick={() => confirm(`Revenir à « ${v.name} » ? (l'état actuel est gardé en version)`) && onRestore(v.file)}>Restaurer</button>
					</div>
				</div>
			))}
			{!list.length ? <p className="muted">Aucune version pour l'instant.</p> : null}
		</>
	);
};

export type {Job};
