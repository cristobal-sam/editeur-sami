// Timeline multipiste : rythme (+ conseils), image (plans), plans de coupe (V2), voix (J/L-cuts), musique, bruitages,
// graphismes (+ vecteurs), choregraphie (piste de choreo-lane.tsx), reperes des notes (revue.tsx), plage « Refaire ce passage ».
import React, {useMemo, useRef, useState} from 'react';
import {GRAPHIC_NAMES} from '../../remotion/src/graphics';
import {audioSegments, duration, pacing, segLen, sfxEvents, videoSegments} from '../../remotion/src/timeline';
import type {ReelDoc} from '../../remotion/src/types';
import {iconName, iconStyleOf} from '../../remotion/src/vectors';
import {weakZones} from './conseils';
import {ChoreoLane} from './choreo-lane';
import {NoteMarkers} from './revue';
import type {PassageRange, Update} from './v2';

type Drag = {kind: 'move' | 'in' | 'out' | 'lead' | 'tail' | 'broll' | 'gfx' | 'vec'; clip: string; index: number; x0: number; dx: number};
export type Marker = {t: number; gravite: number; notes: string[]};
const vecName = (asset: string) => asset.split('/').pop()?.replace(/\.svg$/i, '') || 'Vecteur';
/** Nom d'un element de la piste des vecteurs : nom francais pour une icone de la banque (ronde 4), nom du fichier sinon. */
const vecLabel = (v: {asset: string; meta?: Record<string, unknown>}) => (iconStyleOf(v) ? iconName(v) : vecName(v.asset));

const hue = (s: string) => [...s].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);
const fmt = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;

export const Timeline: React.FC<{
	reel: ReelDoc; t: number; selected: string | null; blocks: Record<string, string>;
	onSeek: (t: number) => void; onSelect: (id: string) => void; onMove: (from: number, to: number) => void;
	onTrim: (id: string, side: 'in' | 'out', delta: number) => void; onJL: (id: string, key: 'audioLead' | 'audioTail', value: number) => void;
	onItemMove: (kind: 'broll' | 'gfx' | 'vector', id: string, at: number) => void; alerts: Marker[] | null; onAdvice: (t: number) => void;
	/** V2 : modification du reel (piste choregraphie), plage « Refaire ce passage », outils dans la barre (passage.tsx). */
	update?: Update; range?: PassageRange; tools?: React.ReactNode;
}> = ({reel, t, selected, blocks, onSeek, onSelect, onMove, onTrim, onJL, onItemMove, alerts, onAdvice, update, range, tools}) => {
	const [zoom, setZoom] = useState(14);
	const [drag, setDrag] = useState<Drag | null>(null);
	const box = useRef<HTMLDivElement>(null);
	const segs = useMemo(() => videoSegments(reel), [reel]);
	const aud = useMemo(() => audioSegments(reel), [reel]);
	const total = useMemo(() => duration(reel), [reel]);
	const events = useMemo(() => sfxEvents(reel), [reel]);
	const pace = useMemo(() => pacing(reel), [reel]);
	const zones = useMemo(() => weakZones(reel), [reel]);
	const W = Math.max(600, total * zoom);
	const x = (s: number) => s * zoom;

	// plans = segments regroupes par plan
	const clips = reel.clips.map((c, index) => {
		const own = segs.filter((s) => s.clip === c.id);
		const a = own[0]?.out_start ?? 0;
		const last = own[own.length - 1];
		const b = last ? last.out_start + segLen(last) : a;
		return {c, index, a, b};
	});

	const pointer = (e: React.PointerEvent) => (e.clientX - (box.current?.getBoundingClientRect().left ?? 0) + (box.current?.scrollLeft ?? 0)) / zoom;
	const start = (e: React.PointerEvent, kind: Drag['kind'], clip: string, index: number) => {
		e.stopPropagation();
		try {
			(e.target as HTMLElement).setPointerCapture(e.pointerId);
		} catch {}
		if (kind !== 'broll' && kind !== 'gfx' && kind !== 'vec') onSelect(clip);
		setDrag({kind, clip, index, x0: e.clientX, dx: 0});
	};
	const moveP = (e: React.PointerEvent) => drag && setDrag({...drag, dx: e.clientX - drag.x0});
	const end = (e: React.PointerEvent) => {
		if (!drag) return;
		const d = drag.dx / zoom;
		if (Math.abs(drag.dx) > 3) {
			if (drag.kind === 'move') {
				const at = pointer(e);
				const to = clips.findIndex((k) => at < (k.a + k.b) / 2);
				onMove(drag.index, to === -1 ? clips.length - 1 : to > drag.index ? to - 1 : to);
			} else if (drag.kind === 'broll' || drag.kind === 'gfx' || drag.kind === 'vec') {
				const item = drag.kind === 'broll' ? reel.broll?.find((b) => b.id === drag.clip)
					: drag.kind === 'vec' ? reel.vectors?.find((v) => v.id === drag.clip) : reel.graphics?.find((g) => g.id === drag.clip);
				if (item) onItemMove(drag.kind === 'vec' ? 'vector' : drag.kind, drag.clip, Math.max(0, +(item.at + d).toFixed(2)));
			} else if (drag.kind === 'in' || drag.kind === 'out') onTrim(drag.clip, drag.kind, +d.toFixed(3));
			else {
				const c = reel.clips.find((k) => k.id === drag.clip)!;
				if (drag.kind === 'lead') onJL(drag.clip, 'audioLead', Math.max(0, Math.min(1.5, +((c.audioLead ?? 0) - d).toFixed(2))));
				else onJL(drag.clip, 'audioTail', Math.max(0, Math.min(1.5, +((c.audioTail ?? 0) + d).toFixed(2))));
			}
		}
		setDrag(null);
	};

	return (
		<div className="timeline">
			<div className="tl-tools">
				<span className="muted">Timeline — glisser un plan pour le déplacer, ses bords pour le couper ; bords du son = J-cut / L-cut</span>
				{tools}
				<label className="muted">Zoom <input type="range" min={6} max={60} value={zoom} onChange={(e) => setZoom(Number(e.target.value))} /></label>
			</div>
			<div className="tl-body">
				<div className="tl-heads">
					<div>Temps</div><div>Rythme</div><div>Image</div><div>Plans coupe</div><div>Voix</div><div>Musique</div><div>Bruitages</div><div>Graphismes</div><div>Chorégraphie</div>
				</div>
				<div className="tl-scroll" ref={box} onPointerMove={moveP} onPointerUp={end}>
					<div style={{width: W, position: 'relative'}} onPointerDown={(e) => !drag && onSeek(Math.max(0, pointer(e)))}>
						{range && range.fin > range.debut ? (
							<div className="tl-range" style={{left: x(Math.max(0, range.debut)), width: x(range.fin - Math.max(0, range.debut))}} title="Passage à refaire" />
						) : null}
						<div className="tl-row tl-ruler">
							{Array.from({length: Math.ceil(total / 5) + 1}, (_, i) => (
								<span key={i} style={{left: x(i * 5)}}>{fmt(i * 5)}</span>
							))}
							<NoteMarkers reel={reel} x={x} onSeek={onSeek} />
						</div>
						<div className="tl-row tl-pace" title="Rythme : vert = soutenu, rouge = zone a surveiller">
							{pace.map((p) => (
								<i key={p.t} style={{left: x(p.t), width: zoom, background: `hsl(${Math.round(p.score * 120)} 70% 42%)`}} />
							))}
							{zones.map((z) => (
								<b key={z.start} className="tl-advice" style={{left: x(z.start)}} title={`Rythme faible : ${z.advice.length} conseil(s) (onglet Conseils)`}
									onPointerDown={(e) => { e.stopPropagation(); onAdvice(z.start); }}>💡</b>
							))}
							{(alerts ?? []).map((a, i) => (
								<b key={`r${i}`} className={`tl-alert g${a.gravite}`} style={{left: x(a.t)}} title={a.notes.join('\n')}
									onPointerDown={(e) => { e.stopPropagation(); onSeek(Math.max(0, a.t - 1)); }}>▲</b>
							))}
						</div>
						<div className="tl-row tl-video">
							{clips.map(({c, index, a, b}) => {
								const dx = drag && drag.clip === c.id ? drag.dx : 0;
								const moving = drag?.kind === 'move' && drag.clip === c.id;
								const left = x(a) + (drag?.clip === c.id && drag.kind === 'in' ? dx : 0) + (moving ? dx : 0);
								const width = x(b - a) + (drag?.clip === c.id ? (drag.kind === 'out' ? dx : drag.kind === 'in' ? -dx : 0) : 0);
								return (
									<div key={c.id} className={`tl-clip${selected === c.id ? ' sel' : ''}${moving ? ' moving' : ''}`}
										style={{left, width: Math.max(8, width), background: `hsl(${hue(c.block)} 45% 32%)`}}
										onPointerDown={(e) => start(e, 'move', c.id, index)}>
										<b>{index + 1}. {blocks[c.block] ?? c.block}</b>
										<span>{c.words.filter((w) => !w.cut).slice(0, 6).map((w) => w.w).join(' ')}</span>
										{selected === c.id ? (
											<>
												<em className="h hl" onPointerDown={(e) => start(e, 'in', c.id, index)} title="Debut du plan" />
												<em className="h hr" onPointerDown={(e) => start(e, 'out', c.id, index)} title="Fin du plan" />
											</>
										) : null}
									</div>
								);
							})}
						</div>
						<div className="tl-row tl-broll">
							{(reel.broll ?? []).map((b) => {
								const dx = drag?.kind === 'broll' && drag.clip === b.id ? drag.dx : 0;
								return (
									<div key={b.id} style={{left: x(b.at) + dx, width: Math.max(6, x(b.duration))}} title={reel.sources[b.source]?.name}
										onPointerDown={(e) => start(e, 'broll', b.id, 0)}>{b.locked ? '🔒 ' : ''}{reel.sources[b.source]?.name ?? b.source}</div>
								);
							})}
						</div>
						<div className="tl-row tl-audio">
							{aud.map((s, i) => (
								<div key={i} className={`tl-a${s.clip === selected ? ' sel' : ''}`} style={{left: x(s.out_start), width: Math.max(2, x(segLen(s)))}} />
							))}
							{selected
								? (() => {
										const own = aud.filter((s) => s.clip === selected);
										if (!own.length) return null;
										const first = own[0];
										const last = own[own.length - 1];
										const c = reel.clips.find((k) => k.id === selected)!;
										const i = reel.clips.indexOf(c);
										return (
											<>
												<em className="jl" style={{left: x(first.out_start) - 5}} title={`J-cut : ${(c.audioLead ?? 0).toFixed(2)} s`} onPointerDown={(e) => start(e, 'lead', c.id, i)} />
												<em className="jl" style={{left: x(last.out_start + segLen(last)) - 5}} title={`L-cut : ${(c.audioTail ?? 0).toFixed(2)} s`} onPointerDown={(e) => start(e, 'tail', c.id, i)} />
											</>
										);
									})()
								: null}
						</div>
						<div className="tl-row tl-music">{reel.music?.enabled && reel.music.file ? <div style={{left: 0, width: x(total)}}>{reel.music.file.split('/').pop()}</div> : null}</div>
						<div className="tl-row tl-sfx">
							{events.map((ev, i) => (
								<i key={i} style={{left: x(ev.t)}} title={`${ev.name} (${ev.kind})`}>◆</i>
							))}
						</div>
						<div className="tl-row tl-gfx">
							{(reel.graphics ?? []).map((g) => {
								const dx = drag?.kind === 'gfx' && drag.clip === g.id ? drag.dx : 0;
								return (
									<div key={g.id} className={`${g.suggested ? 'sug' : ''}${g.locked ? ' locked' : ''}`} style={{left: x(g.at) + dx, width: Math.max(6, x(g.duration))}} title={GRAPHIC_NAMES[g.kind]}
										onPointerDown={(e) => start(e, 'gfx', g.id, 0)}>{g.locked ? '🔒 ' : ''}{GRAPHIC_NAMES[g.kind]}</div>
								);
							})}
							{(reel.vectors ?? []).map((v) => {
								const dx = drag?.kind === 'vec' && drag.clip === v.id ? drag.dx : 0;
								return (
									<div key={v.id} className={`vec${v.suggested ? ' sug' : ''}${v.locked ? ' locked' : ''}`} style={{left: x(v.at) + dx, width: Math.max(6, x(v.duration))}}
										title={`${iconStyleOf(v) ? 'Icône' : 'Vecteur'} : ${vecLabel(v)}`} onPointerDown={(e) => start(e, 'vec', v.id, 0)}>{v.locked ? '🔒 ' : ''}{vecLabel(v)}</div>
								);
							})}
						</div>
						<div className="tl-row tl-choreo">
							<ChoreoLane reel={reel} t={t} zoom={zoom} x={x} onSeek={onSeek} update={update} />
						</div>
						<div className="tl-playhead" style={{left: x(t)}} />
					</div>
				</div>
			</div>
		</div>
	);
};
