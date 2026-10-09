// Elements graphiques animes (piste Graphismes) : chiffre qui defile, cases cochees, carte, mot geant, logo.
import React, {useMemo} from 'react';
import {AbsoluteFill, Img, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Graphic, ReelDoc} from './types';
import {Choreo} from './choreo';
import {StudioMetric} from './design';
import {studioGraphicSpot, studioMode} from './timeline';

type P = {g: Graphic; reel: ReelDoc; t: number; url: (p: string) => string};

/** Entree (0 -> 1) et sortie (1 -> 0) communes a tous les elements. */
const useLife = (g: Graphic, t: number) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const local = t - g.at;
	const enter = spring({frame: frame - Math.round(g.at * fps), fps, config: {damping: 13, stiffness: 190}});
	const exit = interpolate(local, [g.duration - 0.3, g.duration], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return {local, enter, exit, frame, fps};
};

const font = (reel: ReelDoc) => `'${reel.style.font}', sans-serif`;
const accent = (reel: ReelDoc) => reel.style.highlight;
/** Couleur d'un element : choisie a la main (props.color) sinon l'accent du style / de la charte (recolore automatiquement). */
const tint = (g: Graphic, reel: ReelDoc) => (typeof g.props?.color === 'string' && g.props.color) || accent(reel);

/** Chiffre qui defile jusqu'a sa valeur : « 5 FOIS PLUS », « 2 400 $ »... */
const Chiffre: React.FC<P> = ({g, reel, t}) => {
	const {width, height} = useVideoConfig();
	const {local, enter, exit} = useLife(g, t);
	const value = Number(g.props.value) || 0;
	// from = valeur de depart du defilement (0 par defaut) ; count === false = la valeur s'affiche directement, sans defiler
	const from = Number(g.props.from) || 0;
	const count = g.props.count === false ? value : interpolate(local, [0, Math.min(1.1, g.duration * 0.5)], [from, value], {extrapolateRight: 'clamp', easing: (x) => 1 - (1 - x) ** 3});
	const decimals = Number.isInteger(value) ? 0 : 1;
	const shown = count.toLocaleString('fr-CA', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
	// studio Tech 3D : pilule de verre lumineuse dans l'espace libre au-dessus de la personne (place a la main : gardee)
	const studio = studioMode(reel);
	// meme place que l'origine de la choregraphie (choreo.tsx) : studioGraphicSpot
	const spot = useMemo(() => studioGraphicSpot(reel, g), [reel, g]);
	if (studio) {
		return (
			<div style={{position: 'absolute', left: width * spot.x, top: height * spot.y, transform: `translate(-50%,-50%) scale(${spot.scale})`}}>
				<StudioMetric reel={reel} text={`${g.props.prefix ?? ''}${shown}${g.props.suffix ?? ''}`} label={g.props.label ? String(g.props.label) : ''}
					local={local} len={g.duration} accent={tint(g, reel)} />
			</div>
		);
	}
	return (
		<div style={{position: 'absolute', left: 0, right: 0, top: height * (g.props.y ?? 0.3), textAlign: 'center', opacity: exit,
			transform: `translateY(-50%) scale(${interpolate(enter, [0, 1], [0.6, 1])})`, fontFamily: font(reel)}}>
			<div style={{fontSize: Math.min(width, height) * 0.2, fontWeight: 900, color: tint(g, reel), lineHeight: 1,
				WebkitTextStroke: `8px ${reel.style.stroke}`, paintOrder: 'stroke fill', textShadow: '0 10px 40px rgba(0,0,0,0.5)'}}>
				{g.props.prefix ?? ''}{shown}{g.props.suffix ?? ''}
			</div>
			{g.props.label ? (
				<div style={{marginTop: 10, fontSize: Math.min(width, height) * 0.055, fontWeight: 800, color: '#FFFFFF', textTransform: 'uppercase',
					WebkitTextStroke: `5px ${reel.style.stroke}`, paintOrder: 'stroke fill'}}>{g.props.label}</div>
			) : null}
		</div>
	);
};

/** Liste de benefices qui se cochent un par un. */
const Coches: React.FC<P> = ({g, reel, t}) => {
	const {width, height} = useVideoConfig();
	const {local, enter, exit, frame, fps} = useLife(g, t);
	const items: string[] = (g.props.items ?? []).filter(Boolean).slice(0, 5);
	const step = Math.max(0.35, Math.min(0.8, (g.duration - 0.6) / Math.max(1, items.length)));
	const u = Math.min(width, height);
	const c = tint(g, reel);
	return (
		<div style={{position: 'absolute', left: width * 0.1, right: width * 0.1, top: height * (g.props.y ?? 0.22), opacity: exit,
			transform: `translateY(${(1 - enter) * 40}px)`, background: 'rgba(10,10,12,0.82)', borderRadius: 28, padding: u * 0.04,
			boxShadow: '0 20px 60px rgba(0,0,0,0.45)', fontFamily: font(reel)}}>
			{g.props.title ? <div style={{color: c, fontWeight: 900, fontSize: u * 0.05, marginBottom: u * 0.02, textTransform: 'uppercase'}}>{g.props.title}</div> : null}
			{items.map((it, i) => {
				const at = 0.2 + i * step;
				const pop = spring({frame: frame - Math.round((g.at + at) * fps), fps, config: {damping: 11, stiffness: 220}});
				const on = local >= at;
				return (
					<div key={i} style={{display: 'flex', alignItems: 'center', gap: u * 0.025, margin: `${u * 0.012}px 0`, opacity: on ? 1 : 0.25}}>
						<div style={{width: u * 0.065, height: u * 0.065, borderRadius: 12, flex: 'none', border: `5px solid ${c}`,
							background: on ? c : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
							<svg viewBox="0 0 24 24" style={{width: '75%', transform: `scale(${on ? pop : 0})`}}>
								<path d="M4 12.5l5 5L20 6.5" fill="none" stroke="#0B0B0B" strokeWidth={3.4} strokeLinecap="round" strokeLinejoin="round" />
							</svg>
						</div>
						<div style={{color: '#FFFFFF', fontWeight: 800, fontSize: u * 0.048, lineHeight: 1.15}}>{it}</div>
					</div>
				);
			})}
		</div>
	);
};

/** Carte animee : photo (ou pastille de couleur) + libelle, qui glisse depuis le cote. */
const Carte: React.FC<P> = ({g, reel, t, url}) => {
	const {width, height} = useVideoConfig();
	const {enter, exit} = useLife(g, t);
	const u = Math.min(width, height);
	const fromRight = g.props.side !== 'gauche';
	const x = interpolate(enter, [0, 1], [fromRight ? width : -width, 0]);
	return (
		<div style={{position: 'absolute', [fromRight ? 'right' : 'left']: width * 0.06, top: height * (g.props.y ?? 0.16), width: u * 0.62, opacity: exit,
			transform: `translateX(${x}px) rotate(${(1 - enter) * (fromRight ? 8 : -8)}deg)`, background: '#FFFFFF', borderRadius: 26, overflow: 'hidden',
			boxShadow: '0 24px 60px rgba(0,0,0,0.45)', fontFamily: font(reel)}}>
			{g.props.image ? <Img src={url(g.props.image)} style={{width: '100%', height: u * 0.4, objectFit: 'cover', display: 'block'}} />
				: <div style={{height: u * 0.12, background: tint(g, reel)}} />}
			<div style={{padding: `${u * 0.025}px ${u * 0.035}px`}}>
				<div style={{fontWeight: 900, fontSize: u * 0.05, color: '#0B0B0B', lineHeight: 1.1}}>{g.props.title ?? ''}</div>
				{g.props.subtitle ? <div style={{fontWeight: 600, fontSize: u * 0.034, color: '#555', marginTop: 6}}>{g.props.subtitle}</div> : null}
			</div>
		</div>
	);
};

/** Mot geant lumineux en flash. */
const MotGeant: React.FC<P> = ({g, reel, t}) => {
	const {width, height} = useVideoConfig();
	const {local, exit} = useLife(g, t);
	const c = tint(g, reel);
	const s = interpolate(local, [0, 0.18, g.duration], [1.5, 1, 0.94], {extrapolateRight: 'clamp'});
	const o = interpolate(local, [0, 0.08], [0, 1], {extrapolateRight: 'clamp'}) * exit;
	const text = String(g.props.text ?? '').toLocaleUpperCase('fr-CA');
	const size = Math.min(width * 0.9 / Math.max(3, text.length * 0.62), height * 0.2);
	return (
		<AbsoluteFill style={{background: `rgba(0,0,0,${0.35 * o})`, alignItems: 'center', justifyContent: 'center'}}>
			<div style={{fontFamily: font(reel), fontWeight: 900, fontSize: size, color: '#FFFFFF', opacity: o, transform: `scale(${s})`, textAlign: 'center',
				textShadow: `0 0 12px ${c}, 0 0 34px ${c}, 0 0 70px ${c}, 0 0 120px ${c}`, WebkitTextStroke: `3px ${c}`, lineHeight: 1}}>{text}</div>
		</AbsoluteFill>
	);
};

/** Logo anime (celui de la charte client, ou un fichier choisi). */
const Logo: React.FC<P> = ({g, reel, t, url}) => {
	const {width, height} = useVideoConfig();
	const {enter, exit} = useLife(g, t);
	const file = g.props.file || reel.brand?.logo;
	if (!file) return null;
	const u = Math.min(width, height);
	return (
		<AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: exit}}>
			<Img src={url(file)} style={{width: u * (g.props.size ?? 0.45), transform: `scale(${enter}) rotate(${(1 - enter) * -25}deg)`,
				filter: 'drop-shadow(0 18px 40px rgba(0,0,0,0.5))'}} />
		</AbsoluteFill>
	);
};

const KINDS = {chiffre: Chiffre, coches: Coches, carte: Carte, motgeant: MotGeant, logo: Logo};
export const GRAPHIC_NAMES: Record<string, string> = {chiffre: 'Chiffre qui défile', coches: 'Cases cochées', carte: 'Carte animée', motgeant: 'Mot géant lumineux', logo: 'Logo animé'};

/** only : ne rendre que certains graphismes (style immersif : ceux poses ou verrouilles par le monteur). */
export const Graphics: React.FC<{reel: ReelDoc; t: number; url: (p: string) => string; only?: (g: Graphic) => boolean}> = ({reel, t, url, only}) => (
	<>
		{(reel.graphics ?? []).filter((g) => !g.suggested && t >= g.at && t < g.at + g.duration && (!only || only(g))).map((g) => {
			const C = KINDS[g.kind];
			// V2 : la choregraphie (choreo.tsx) peut envelopper l'entree/sortie ; sans mouvement, rendu identique
			return C ? (
				<Choreo key={g.id} reel={reel} cible={{type: 'graphics', id: g.id}} t={t} at={g.at} duration={g.duration}>
					<C g={g} reel={reel} t={t} url={url} />
				</Choreo>
			) : null;
		})}
	</>
);

/** Charte client : logo en filigrane + carte de fin. */
export const BrandLayer: React.FC<{reel: ReelDoc; t: number; total: number; url: (p: string) => string}> = ({reel, t, total, url}) => {
	const {width, height, fps} = useVideoConfig();
	const frame = useCurrentFrame();
	const b = reel.brand;
	if (!b) return null;
	const u = Math.min(width, height);
	const out = b.outro;
	const outroStart = total - (out?.duration ?? 0);
	const inOutro = out?.enabled && t >= outroStart;
	const pos = b.logoPosition ?? 'haut-droite';
	const logo = b.logo && !inOutro ? (
		<Img src={url(b.logo)} style={{position: 'absolute', width: u * (b.logoSize ?? 0.16), opacity: b.logoOpacity ?? 0.85,
			[pos.includes('haut') ? 'top' : 'bottom']: height * 0.045, [pos.includes('gauche') ? 'left' : 'right']: width * 0.05}} />
	) : null;
	if (!inOutro) return logo;
	const e = spring({frame: frame - Math.round(outroStart * fps), fps, config: {damping: 14}});
	return (
		<AbsoluteFill style={{background: `rgba(8,8,10,${0.82 * e})`, alignItems: 'center', justifyContent: 'center', gap: u * 0.05, flexDirection: 'column'}}>
			{b.logo ? <Img src={url(b.logo)} style={{width: u * 0.42, transform: `scale(${e})`}} /> : null}
			{out.text ? (
				<div style={{fontFamily: `'${reel.style.font}', sans-serif`, fontWeight: 900, fontSize: u * 0.065, color: b.bannerBg || reel.style.highlight,
					textAlign: 'center', padding: `0 ${width * 0.08}px`, opacity: e, textTransform: 'uppercase', lineHeight: 1.15}}>{out.text}</div>
			) : null}
		</AbsoluteFill>
	);
};
