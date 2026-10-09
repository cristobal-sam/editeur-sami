import React, {useEffect, useMemo, useRef, useState} from 'react';
import {
	AbsoluteFill,
	Audio,
	Easing,
	Img,
	OffthreadVideo,
	Sequence,
	continueRender,
	delayRender,
	interpolate,
	random,
	spring,
	useCurrentFrame,
	useVideoConfig,
} from 'remotion';
import {
	audioSegments,
	blockStarts,
	colorGains,
	colorReference,
	displayWord,
	duration,
	brollMode,
	framing,
	insetBox,
	musicVolume,
	pages,
	segLen,
	sfxEvents,
	sfxFile,
	speech,
	timedWords,
	videoSegments,
	visualClip,
	designScenes,
	segmentZoom,
	validCutout,
	captionCueId,
	cutoutFallbackMix,
	studioGrade,
	studioMode,
	studioView,
} from './timeline';
import {BrandLayer, Graphics} from './graphics';
import {Choreo} from './choreo';
import {VectorLayer} from './vectors';
import {DesignBackground, DesignDecor, DesignScenes, Foreground, Kinetic, ComparisonVideo, ProductStage} from './design';
import {EMOJI_FONT, FONT_FILES, STUDIO_UI_FONT, type Broll, type ReelDoc, type ReelProps, type Segment} from './types';

const loaded = new Set<string>();
const loading = new Map<string, Promise<void>>();

/** Police chargee une seule fois (meme si deux elements la demandent) ; une police choisie apres l'ouverture (changement
 * de style dans l'apercu) est aussi chargee. Le rendu attend la police demandee a l'ouverture. */
const useFont = (family: string, file: string, assetBase: string) => {
	const [handle] = useState(() => (loaded.has(family) ? null : delayRender(`Police ${family}`)));
	const released = useRef(false);
	useEffect(() => {
		const release = () => {
			if (handle !== null && !released.current) {
				released.current = true;
				continueRender(handle);
			}
		};
		if (loaded.has(family)) return release();
		let p = loading.get(family);
		if (!p) {
			p = new FontFace(family, `url(${assetBase}/fonts/${file})`, {weight: '100 900'})
				.load()
				.then((f) => {
					document.fonts.add(f);
					loaded.add(family);
				})
				.catch(() => undefined);
			loading.set(family, p);
		}
		p.finally(release);
	}, [family, file, assetBase, handle]);
};

const GRADES: Record<string, string> = {
	aucun: '',
	chaud: 'sepia(0.14) saturate(1.12) contrast(1.03)',
	froid: 'hue-rotate(-8deg) saturate(0.95) contrast(1.06) brightness(1.02)',
	contraste: 'contrast(1.12) saturate(1.12)',
	cinema: 'contrast(1.08) saturate(0.88) sepia(0.08)',
	noirblanc: 'grayscale(1) contrast(1.15)',
};

/** Un plan (segment) : media optimise lu au bon endroit, zoom, couleur harmonisee. */
const SegmentVideo: React.FC<{reel: ReelDoc; seg: Segment; next: Segment | undefined; total: number; mediaBase: string; ref0: ReturnType<typeof colorReference>}> = ({
	reel,
	seg,
	next,
	total,
	mediaBase,
	ref0,
}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const clip = visualClip(reel, reel.clips.find((c) => c.id === seg.clip)!);
	const src = reel.sources[seg.source];
	const speed = seg.speed ?? 1;
	const tSrc = seg.src_in + (frame / fps) * speed;
	// Personne detouree (studio Tech 3D, Collage) : la prise d'origine n'est montree que dans les plages de repli du
	// detourage (cutouts[clip].fallback), en fondu ; ailleurs elle serait entierement cachee : on ne la decode pas.
	const mode = reel.design?.enabled === false ? null : reel.design?.mode;
	const studio = studioMode(reel);
	const cut = studio || mode === 'collage' ? validCutout(reel, seg) : null;
	const mix = cut ? cutoutFallbackMix(cut, tSrc) : 1;
	if (mix <= 0) return null;
	// meme calcul que le rectangle des dessins de revision (sourceRectAt) : les traits restent sur le bon pixel ;
	// studio : meme camera que la personne detouree (aucun saut au fondu)
	const view = studio ? studioView(reel, seg, seg.out_start + frame / fps) : null;
	const scale = view ? view.scale : segmentZoom(reel, seg, next, total, frame / fps);
	const f = framing(reel, seg.source, tSrc, seg.src_in, seg.src_out);
	const [r, g, b] = colorGains(reel, clip, tSrc, ref0);
	const id = `cc${seg.index}`;
	const grade = GRADES[reel.effects?.grade ?? 'aucun'];
	if (studio && cut) {
		// Repli du detourage dans le studio : la prise d'origine aux couleurs du studio (meme etalonnage que la personne
		// detouree), decor flou et sombre, personne nette au centre (ellipse autour du visage et du buste). Deux lectures de
		// la meme image, seulement pendant les plages de repli.
		const u = Math.min(reel.width, reel.height);
		const place = {position: 'absolute', left: f.left, top: f.top, width: f.width, height: f.height} as const;
		const media = src.still ? <Img src={`${mediaBase}/${src.proxy}`} style={place} />
			: <OffthreadVideo src={`${mediaBase}/${src.proxy}`} trimBefore={Math.round(seg.src_in * fps)} playbackRate={speed} muted style={place} />;
		const mask = `radial-gradient(ellipse 34% 40% at ${(f.cx * 100).toFixed(1)}% ${((f.cy + 0.08) * 100).toFixed(1)}%, #000 50%, transparent 100%)`;
		return (
			<AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: `${view!.ox * 100}% ${view!.oy * 100}%`}}>
				<svg style={{position: 'absolute', width: 0, height: 0}}>
					<filter id={id} colorInterpolationFilters="sRGB">
						<feColorMatrix type="matrix" values={studioGrade(reel, seg, [r, g, b]).join(' ')} />
					</filter>
				</svg>
				<AbsoluteFill style={{filter: `url(#${id}) blur(${(u * 0.016).toFixed(1)}px) brightness(0.42) saturate(0.55)`}}>{media}</AbsoluteFill>
				<AbsoluteFill style={{filter: `url(#${id}) brightness(0.92)`, WebkitMaskImage: mask, maskImage: mask}}>{media}</AbsoluteFill>
			</AbsoluteFill>
		);
	}
	return (
		<AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: view ? `${view.ox * 100}% ${view.oy * 100}%` : `${f.cx * 100}% ${f.cy * 100}%`,
			filter: `url(#${id})${grade ? ' ' + grade : ''}`, opacity: cut && !studio ? mix : undefined}}>
			<svg style={{position: 'absolute', width: 0, height: 0}}>
				<filter id={id} colorInterpolationFilters="sRGB">
					<feColorMatrix type="matrix" values={`${r} 0 0 0 0  0 ${g} 0 0 0  0 0 ${b} 0 0  0 0 0 1 0`} />
				</filter>
			</svg>
			{src.still ? <Img src={`${mediaBase}/${src.proxy}`} style={{position:'absolute',left:f.left,top:f.top,width:f.width,height:f.height}} />
				: <OffthreadVideo src={`${mediaBase}/${src.proxy}`} trimBefore={Math.round(seg.src_in * fps)} playbackRate={speed} muted
				style={{position: 'absolute', left: f.left, top: f.top, width: f.width, height: f.height}} />}
		</AbsoluteFill>
	);
};

/** Plan de coupe (piste V2) : remplit l'image au-dessus du plan principal, sans son. Image fixe : lent zoom avant. */
const BrollVideo: React.FC<{reel: ReelDoc; b: Broll; mediaBase: string}> = ({reel, b, mediaBase}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const src = reel.sources[b.source];
	if (!src) return null;
	const f = framing(reel, b.source, b.in + frame / fps, b.in, b.in + b.duration);
	const push = 1 + (src.still ? 0.09 : 0.04) * Math.min(1, frame / fps / Math.max(0.1, b.duration));
	const fade = interpolate(frame / fps, [0, 0.12, b.duration - 0.12, b.duration], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const grade = GRADES[reel.effects?.grade ?? 'aucun'];
	// plein ecran ou encadre : choix du monteur, sinon selon le format de CE rendu (export multi-formats)
	if ((b.mode ?? brollMode(reel, b.source)) === 'encadre') {
		// cadre a bord blanc sur la moitie droite (glisse depuis le bord), le media le remplit sans bande noire
		const box = insetBox(reel);
		const sw = src.width ?? 1920;
		const sh = src.height ?? 1080;
		const k = Math.max(box.width / sw, box.height / sh);
		const s = frame / fps;
		const slide = interpolate(s, [0, 0.22], [box.width * 0.35, 0], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)})
			+ interpolate(s, [b.duration - 0.18, b.duration], [0, box.width * 0.35], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.in(Easing.cubic)});
		const media = {position: 'absolute', left: (box.width - sw * k) / 2, top: (box.height - sh * k) / 2, width: sw * k, height: sh * k, transform: `scale(${push})`} as const;
		return (
			<AbsoluteFill>
				<div style={{position: 'absolute', left: box.left, top: box.top, width: box.width, height: box.height, overflow: 'hidden', boxSizing: 'border-box',
					border: `${Math.max(3, Math.round(reel.width / 216))}px solid #fff`, boxShadow: '0 14px 44px rgba(0,0,0,.5)',
					transform: `translateX(${slide}px)`, opacity: fade, filter: grade || undefined}}>
					{src.still ? <Img src={`${mediaBase}/${src.proxy}`} style={media} />
						: <OffthreadVideo src={`${mediaBase}/${src.proxy}`} trimBefore={Math.round(b.in * fps)} muted style={media} />}
				</div>
			</AbsoluteFill>
		);
	}
	const place = {position: 'absolute', left: f.left, top: f.top, width: f.width, height: f.height} as const;
	return (
		<AbsoluteFill style={{opacity: fade, transform: `scale(${push})`, filter: grade || undefined}}>
			{src.still ? <Img src={`${mediaBase}/${src.proxy}`} style={place} />
				: <OffthreadVideo src={`${mediaBase}/${src.proxy}`} trimBefore={Math.round(b.in * fps)} muted style={place} />}
		</AbsoluteFill>
	);
};

/** Largeur d'un mot en em pour une grotesque grasse (chasses de Manrope 800, espacement -0,012 em compris). */
const signsEm = (w: string) => [...w].reduce((n, c) => n - 0.012 + (/[ijlI|'’.,:;!]/.test(c) ? 0.31 : /[frt\-1]/.test(c) ? 0.43
	: /[mwMWœŒ%]/.test(c) ? 0.9 : /[A-Z0-9ÀÂÇÉÈÊËÎÏÔÙÛ]/.test(c) ? 0.68 : 0.6), 0);

const Captions: React.FC<{reel: ReelDoc; t: number}> = ({reel, t}) => {
	const {fps, width, height} = useVideoConfig();
	const frame = useCurrentFrame();
	const all = useMemo(() => pages(reel), [reel]);
	const page = all.find((p) => t >= p.start && t < p.end);
	if (!page) return null;
	const s = reel.style;
	const preset = s.preset;
	const soft = preset === 'minimal' || preset === 'elegant';
	const enter = spring({frame: frame - Math.round(page.start * fps), fps, config: {damping: preset === 'geant' ? 10 : 14, stiffness: 220}});
	const opacity = soft ? interpolate(enter, [0, 1], [0, 1]) : 1;
	const scaleIn = soft ? 1 : interpolate(enter, [0, 1], [preset === 'geant' ? 0.55 : 0.82, 1]);
	const glow = (c: string) => `0 0 8px ${c}, 0 0 22px ${c}, 0 0 42px ${c}`;
	const studio = studioMode(reel);
	const u = Math.min(width, height);
	// studio Tech 3D : une page tient sur UNE ligne si possible ; la police se resserre jusqu'a 80 % de sa taille (largeur
	// estimee avec les chasses d'une grotesque grasse - Manrope 800 -, marges et espaces des mots compris). Si deux lignes
	// restent necessaires, elles sont equilibrees (textWrap balance) : jamais un mot seul en 2e ligne.
	let fontSize = s.size * u / 1080;
	if (studio) {
		const em = page.words.reduce((n, w) => n + 0.2 + signsEm(displayWord(w.w, s.uppercase)), 0.2 * (page.words.length - 1));
		const est = em * fontSize;
		const room = width * 0.86;
		if (est > room) fontSize *= Math.max(0.8, room / est);
	}
	return (
		<Choreo reel={reel} cible={{type: 'caption', id: captionCueId(page.words[0])}} t={t} at={page.start} duration={page.end - page.start}>
		<div
			style={{
				position: 'absolute',
				left: width * 0.07,
				right: width * 0.07,
				top: height * s.position,
				transform: `translateY(-50%) scale(${scaleIn}) translateY(${(1 - opacity) * 18}px)`,
				opacity,
				textAlign: 'center',
				fontFamily: `'${s.font}', sans-serif`,
				fontWeight: s.weight,
				fontSize,
				lineHeight: preset === 'bulle' ? 1.5 : studio ? 1.14 : 1.1,
				letterSpacing: s.uppercase ? 0.5 : studio ? '-0.012em' : 0,
				textWrap: studio ? 'balance' : undefined,
			}}
		>
			<span style={preset === 'bulle' ? {background: '#FFFFFF', borderRadius: 14, padding: '4px 16px', boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone'} : undefined}>
				{page.words.map((w, i) => {
					const active = t >= w.outStart && t < w.outEnd + 0.02;
					let color = w.hl ? s.highlight : s.color;
					if (preset === 'karaoke') color = t >= w.outStart ? s.highlight : s.color;
					if (preset === 'boite') color = s.color; // texte lisible dans la boite (s.color sur fond s.highlight)
					// Boite : seuls les mots en couleur (hl) recoivent la boite, des qu'ils sont dits et tant que la page
					// est affichee ; les autres mots restent simples (texte s.color, sans boite). Avant, la boite suivait
					// chaque mot dit, ce qui mettait en valeur des mots quelconques.
					const boxed = preset === 'boite' && w.hl && t >= w.outStart;
					let transform = s.pop && active ? 'scale(1.07) translateY(-3px)' : 'scale(1)';
					if (boxed) {
						// petite entree de la boite au moment ou le mot est dit
						const pop = spring({frame: frame - Math.round(w.outStart * fps), fps, config: {damping: 12, stiffness: 260}});
						transform = `scale(${(s.pop && active ? 1.07 : 1) * interpolate(pop, [0, 1], [0.8, 1])}) translateY(${s.pop && active ? -3 : 0}px)`;
					}
					const style: React.CSSProperties = {
						display: 'inline-block',
						margin: '0 0.1em',
						color,
						textTransform: s.uppercase ? 'uppercase' : 'none',
						transform,
					};
					if (s.strokeWidth > 0) {
						style.WebkitTextStroke = `${s.strokeWidth * Math.min(width,height) / 1080}px ${s.stroke}`;
						style.paintOrder = 'stroke fill';
					}
					// studio Tech 3D : grotesque sans contour, ombre douce (lisible sur le studio sombre), mots forts a la couleur
					// d'accent avec une lueur legere
					if (studio) style.textShadow = w.hl ? `0 0 ${u * 0.026}px ${s.highlight}99, 0 2px 4px rgba(0,0,0,0.5), 0 6px 24px rgba(0,0,0,0.7)`
						: '0 2px 4px rgba(0,0,0,0.55), 0 6px 26px rgba(0,0,0,0.72)';
					else if (preset === 'neon') style.textShadow = glow(w.hl || active ? s.highlight : 'rgba(255,255,255,0.75)');
					else if (soft) style.textShadow = '0 3px 14px rgba(0,0,0,0.75)';
					else if (preset !== 'bulle') style.textShadow = '0 6px 18px rgba(0,0,0,0.45)';
					if (preset === 'elegant' && w.hl) style.fontStyle = 'italic';
					if (boxed) Object.assign(style, {background: s.highlight, borderRadius: 12, padding: '0 0.18em'});
					return (
						<React.Fragment key={`${w.clip}-${w.index}`}>
							{i > 0 ? ' ' : null}
							<span style={style}>{displayWord(w.w, s.uppercase)}</span>
						</React.Fragment>
					);
				})}
			</span>
		</div>
		</Choreo>
	);
};

const Banner: React.FC<{reel: ReelDoc; t: number; total: number}> = ({reel, t, total}) => {
	const {width, height, fps} = useVideoConfig();
	const frame = useCurrentFrame();
	const b = reel.banner;
	const end = b.end ?? total;
	const brand = reel.brand;
	if (!b.enabled || !b.text.trim() || t < b.start || t > end) return null;
	const enter = spring({frame: frame - Math.round(b.start * fps), fps, config: {damping: 16}});
	return (
		<Choreo reel={reel} cible={{type: 'banner', id: 'banner'}} t={t} at={b.start} duration={end - b.start}>
		<div style={{position: 'absolute', top: height * 0.1, left: 0, right: 0, display: 'flex', justifyContent: 'center'}}>
			<div
				style={{
					transform: `scale(${enter})`,
					maxWidth: width * 0.86,
					background: brand?.bannerBg || '#FFFFFF',
					color: brand?.bannerColor || '#0B0B0B',
					borderRadius: 18,
					padding: '18px 30px',
					textAlign: 'center',
					fontFamily: `'${reel.style.font}', sans-serif`,
					fontWeight: 900,
					fontSize: 46,
					lineHeight: 1.12,
					textTransform: 'uppercase',
					boxShadow: '0 10px 30px rgba(0,0,0,0.35)',
				}}
			>
				{b.text}
			</div>
		</div>
		</Choreo>
	);
};

/** Transition entre deux parties du script : flash blanc, glitch ou fuite de lumiere. */
const Transition: React.FC<{reel: ReelDoc; t: number; starts: {t: number}[]}> = ({reel, t, starts}) => {
	const {width, height} = useVideoConfig();
	const frame = useCurrentFrame();
	if (!reel.flash.enabled) return null;
	const kind = reel.flash.kind ?? 'blanc';
	const hit = starts.map((b) => t - b.t).find((d) => d >= -0.05 && d < (kind === 'lumiere' ? 0.7 : 0.25));
	if (hit === undefined) return null;
	if (kind === 'blanc') {
		return <AbsoluteFill style={{background: '#FFFFFF', opacity: interpolate(hit, [0, 0.2], [0.75, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}} />;
	}
	if (kind === 'lumiere') {
		const x = interpolate(hit, [-0.05, 0.7], [-0.3, 1.3]);
		const o = interpolate(hit, [-0.05, 0.15, 0.7], [0, 0.85, 0], {extrapolateRight: 'clamp'});
		return (
			<AbsoluteFill
				style={{mixBlendMode: 'screen', opacity: o,
					background: `radial-gradient(ellipse 60% 45% at ${x * 100}% 35%, rgba(255,170,90,0.95), rgba(255,80,120,0.5) 45%, transparent 75%)`}}
			/>
		);
	}
	const bars = Array.from({length: 7}, (_, i) => ({
		top: random(`y${frame}-${i}`) * height,
		h: 12 + random(`h${frame}-${i}`) * 90,
		dx: (random(`x${frame}-${i}`) - 0.5) * 120,
		c: ['rgba(0,255,255,0.35)', 'rgba(255,0,90,0.35)', 'rgba(255,255,255,0.25)'][i % 3],
	}));
	return (
		<AbsoluteFill>
			{bars.map((b, i) => (
				<div key={i} style={{position: 'absolute', left: b.dx, top: b.top, width: width + 120, height: b.h, background: b.c, mixBlendMode: 'screen'}} />
			))}
		</AbsoluteFill>
	);
};

/** Grain de film : texture precalculee deplacee a chaque image. */
const Grain: React.FC<{amount: number; assetBase: string}> = ({amount, assetBase}) => {
	const frame = useCurrentFrame();
	if (!amount) return null;
	return (
		<AbsoluteFill
			style={{opacity: amount * 0.4, mixBlendMode: 'overlay', pointerEvents: 'none', backgroundImage: `url(${assetBase}/overlays/grain.png)`,
				backgroundSize: '512px 512px', backgroundPosition: `${Math.floor(random(`gx${frame}`) * 512)}px ${Math.floor(random(`gy${frame}`) * 512)}px`}}
		/>
	);
};

const Emojis: React.FC<{reel: ReelDoc; t: number}> = ({reel, t}) => {
	const {fps, height, width} = useVideoConfig();
	const frame = useCurrentFrame();
	const items = useMemo(() => {
		const tw = timedWords(reel);
		return reel.clips
			.flatMap((c) => (c.emojis ?? []).map(([i, e]) => ({e, t: tw.find((w) => w.clip === c.id && w.index === i)?.outStart ?? -1})))
			.filter((x) => x.t >= 0);
	}, [reel]);
	if (!reel.emoji?.enabled) return null;
	const cur = items.find((x) => t >= x.t && t < x.t + 1.3);
	if (!cur) return null;
	const pop = spring({frame: frame - Math.round(cur.t * fps), fps, config: {damping: 9, stiffness: 180}});
	const out = interpolate(t - cur.t, [1.0, 1.3], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return (
		<div
			style={{position: 'absolute', left: 0, right: 0, top: height * (reel.style.position - 0.14), textAlign: 'center',
				fontFamily: "'Noto Color Emoji'", fontSize: 130*Math.min(width,height)/1080, transform: `scale(${pop}) rotate(${(1 - pop) * -20}deg)`, opacity: out}}
		>
			{cur.e}
		</div>
	);
};

export const Reel: React.FC<ReelProps> = ({reel, assetBase, mediaBase, audio = 'preview'}) => {
	const frame = useCurrentFrame();
	const {fps, width} = useVideoConfig();
	const t = frame / fps;
	useFont(reel.style.font, FONT_FILES[reel.style.font] ?? FONT_FILES.Montserrat, assetBase);
	useFont('Noto Color Emoji', EMOJI_FONT, assetBase);
	// interfaces du studio Tech 3D (cartes, bouton, chiffre) : police dediee, chargee seulement dans ce style
	const uiFont = studioMode(reel) ? STUDIO_UI_FONT : reel.style.font;
	useFont(uiFont, FONT_FILES[uiFont] ?? FONT_FILES.Montserrat, assetBase);
	const segs = useMemo(() => videoSegments(reel), [reel]);
	const voice = useMemo(() => audioSegments(reel), [reel]);
	const total = useMemo(() => duration(reel), [reel]);
	const starts = useMemo(() => blockStarts(reel, segs), [reel, segs]);
	const ref0 = useMemo(() => colorReference(reel), [reel]);
	const ranges = useMemo(() => speech(reel), [reel]);
	const events = useMemo(() => sfxEvents(reel), [reel]);
	const scenes = useMemo(() => designScenes(reel), [reel]);
	const fx = reel.effects ?? {grain: 0, vignette: 0, grade: 'aucun'};
	const intro = reel.intro;
	const url = (p: string) => (p.startsWith('assets/') ? `${assetBase}/${p.slice(7)}` : `${mediaBase}/${p}`);
	// carte de fin de la charte client : les sous-titres et le bandeau s'effacent
	const outro = !!reel.brand?.outro?.enabled && t >= total - reel.brand.outro.duration;
	const mode = reel.design?.enabled === false ? null : reel.design?.mode;
	const extras = !mode || reel.design?.suppressExtras === false;
	// Un style immersif masque les ajouts génériques, mais pas une preuve explicitement décidée par le storyboard.
	const plannedGraphic = (reel.graphics??[]).some(g=>!g.suggested&&g.auto&&t>=g.at&&t<g.at+g.duration)
		&& (reel.creativePlan?.storyboard??[]).some(s=>s.engine==='remotion-graphisme'&&t>=s.start-.3&&t<=s.end+.4);
	// V2 : un graphisme pose ou retouche a la main (manual) ou verrouille reste visible dans un style immersif (decision du
	// monteur, jamais effacee par un changement de style) ; il compte comme l'element par-dessus l'image a cet instant
	const userGraphic = !extras && !plannedGraphic && (reel.graphics??[]).some(g=>!g.suggested&&(g.manual||g.locked)&&t>=g.at&&t<g.at+g.duration);
	const manual = plannedGraphic || userGraphic || (extras && ((reel.graphics??[]).some(g=>!g.suggested&&t>=g.at&&t<g.at+g.duration) || (reel.broll??[]).some(b=>t>=b.at&&t<b.at+b.duration)));
	// studio Tech 3D : une seule information a la fois, le chiffre (ou le mot geant) affiche remplace aussi les sous-titres
	// qui le disent ; un logo, une liste ou une carte posee a la main laisse les sous-titres
	const saysWords = studioMode(reel) && (plannedGraphic || userGraphic) && (reel.graphics??[]).some(g=>!g.suggested
		&& (g.kind==='chiffre'||g.kind==='motgeant') && (plannedGraphic || !!(g.manual||g.locked)) && t>=g.at&&t<g.at+g.duration);
	const designed = (!manual && scenes.some(g=>t>=g.at&&t<g.end && g.kind!=='keyword' && (g.kind!=='product'||reel.design?.productVideo)))
		|| saysWords;
	return (
		<AbsoluteFill style={{background: '#000'}}>
			{mode==='collage' ? <DesignBackground reel={reel} /> : null}
			{/* plans detoures (Collage, studio Tech 3D) : SegmentVideo ne montre la prise que dans les plages de repli */}
			{segs.map((s, i) => (
				<Sequence key={`v${i}`} from={Math.round(s.out_start * fps)} durationInFrames={Math.max(1, Math.round(segLen(s) * fps))} layout="none">
					<SegmentVideo reel={reel} seg={s} next={segs[i + 1]} total={total} mediaBase={mediaBase} ref0={ref0} />
				</Sequence>
			))}
			{mode==='produit' ? <ProductStage reel={reel} t={t} assetBase={assetBase} /> : null}
			{/* mot geant derriere la personne ; pas pendant une preuve chiffree du storyboard (jamais deux traitements du meme mot) */}
			{mode==='editorial' && !plannedGraphic ? <Kinetic reel={reel} t={t} behind /> : null}
			{mode==='editorial'||mode==='collage' ? <Foreground reel={reel} t={t} assetBase={assetBase} /> : null}
			{mode==='comparatif'&&!manual ? <ComparisonVideo reel={reel} t={t} mediaBase={mediaBase} /> : null}
			{(extras ? reel.broll ?? [] : []).map((b) => (
				<Sequence key={b.id} from={Math.round(b.at * fps)} durationInFrames={Math.max(1, Math.round(b.duration * fps))} layout="none">
					<Choreo reel={reel} cible={{type: 'broll', id: b.id}} t={t} at={b.at} duration={b.duration}>
						<BrollVideo reel={reel} b={b} mediaBase={mediaBase} />
					</Choreo>
				</Sequence>
			))}
			{fx.vignette ? <AbsoluteFill style={{background: `radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,${0.75 * fx.vignette}) 100%)`}} /> : null}
			<Grain amount={fx.grain} assetBase={assetBase} />
			<DesignDecor reel={reel} t={t} />
			<Transition reel={reel} t={t} starts={starts} />
			{extras || plannedGraphic ? <Graphics reel={reel} t={t} url={url} />
				: userGraphic ? <Graphics reel={reel} t={t} url={url} only={(g) => !!(g.manual || g.locked)} /> : null}
			{/* V2 : vecteurs de la banque (au-dessus des graphismes, sous les scenes du style et les sous-titres) */}
			<VectorLayer reel={reel} t={t} total={total} assetBase={assetBase} />
			{/* Les notes et dessins de revision ne sont JAMAIS lus par la composition : absents de l'export (voir SPEC V2). */}
			{!outro && !manual ? <DesignScenes reel={reel} t={t} assetBase={assetBase} /> : null}
			{!outro ? <Banner reel={reel} t={t} total={total} /> : null}
			{!outro ? <Emojis reel={reel} t={t} /> : null}
			{!outro && !designed ? (mode==='editorial' ? <Kinetic reel={reel} t={t} /> : <Captions reel={reel} t={t} />) : null}
			<BrandLayer reel={reel} t={t} total={total} url={url} />
			{intro?.enabled && intro.file ? (
				<Sequence durationInFrames={Math.round(intro.duration * fps)}>
					<OffthreadVideo src={`${mediaBase}/${intro.file}`} transparent muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
				</Sequence>
			) : null}
			{reel.progress.enabled ? <div style={{position: 'absolute', left: 0, bottom: 0, height: 8, width: width * Math.min(1, t / total), background: reel.style.highlight}} /> : null}
			{audio === 'preview'
				? voice.map((s, i) => {
						const d = segLen(s);
						const df = Math.max(1, Math.round(d * fps));
						return (
							<Sequence key={`a${i}`} from={Math.round(s.out_start * fps)} durationInFrames={df} layout="none">
								<Audio
									src={`${mediaBase}/${reel.audio?.denoise !== false && reel.sources[s.source].voice ? reel.sources[s.source].voice : reel.sources[s.source].proxy}`}
									trimBefore={Math.round(s.src_in * fps)}
									playbackRate={s.speed ?? 1}
									volume={(f) => Math.min(1, (f / fps) / s.fadeIn, (d - f / fps) / s.fadeOut)}
								/>
							</Sequence>
						);
					})
				: null}
			{audio !== 'none' && reel.music?.enabled && reel.music.file ? (
				<Audio src={`${assetBase}/${reel.music.file}`} loop volume={(f) => musicVolume(reel, f / fps, ranges, total)} />
			) : null}
			{audio !== 'none'
				? events.map((e, i) => (
						<Sequence key={`s${i}`} from={Math.max(0, Math.round(e.t * fps))} durationInFrames={Math.round(3 * fps)} layout="none">
							<Audio src={`${assetBase}/${sfxFile(e.name)}`} volume={e.volume} />
						</Sequence>
					))
				: null}
		</AbsoluteFill>
	);
};
