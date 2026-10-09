// Identités de la galerie. Les instants et les ancres sont calculés exclusivement dans timeline.ts.
import React, {useMemo} from 'react';
import {AbsoluteFill, Img, OffthreadVideo, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {designScenes, pages, displayWord, framing, videoSegments, segLen, validCutout, colorGains, colorReference, cutoutFallbackMix,
	mixHex, segSrcTime, studioGrade, studioMode, studioPersonAt, studioView, visualClip, type PlacedScene} from './timeline';
import {STUDIO_UI_FONT, type ReelDoc, type StyleScene} from './types';
import {Choreo} from './choreo';

export const DesignBackground: React.FC<{reel: ReelDoc}> = ({reel}) => {
	if (reel.design?.enabled === false || reel.design?.mode !== 'collage') return null;
	return <AbsoluteFill style={{background: '#e7ddc7', backgroundImage: 'repeating-linear-gradient(3deg,#00000006 0px,#00000006 1px,transparent 1px,transparent 5px)'}}>
		<div style={{position:'absolute',left:'5%',top:'5%',width:'24%',height:'3%',background:'#c5aa74aa',transform:'rotate(-8deg)'}} />
		<div style={{position:'absolute',right:'5%',top:'8%',fontSize:130,color:reel.design.accent,transform:'rotate(14deg)'}}>✦</div>
	</AbsoluteFill>;
};

/** Personne détourée. Collage : contour blanc d'autocollant. Studio Tech 3D : étalonnée aux couleurs du décor (balance des
 * blancs froide d'après la vraie couleur du visage, légère désaturation, ombres bleutées, noirs denses), bord resserré,
 * occlusion de bord, liseré de lumière fin venant des deux lumières du studio, ombre portée, et caméra du studio
 * (studioView). Plage de repli du détourage (cutouts[clip].fallback) : la personne détourée s'efface au profit de la prise
 * d'origine. */
export const Foreground: React.FC<{reel: ReelDoc; t: number; assetBase: string}> = ({reel,t,assetBase}) => {
	const segs = useMemo(()=>videoSegments(reel),[reel]);
	const ref0 = useMemo(()=>colorReference(reel),[reel]);
	const {fps} = useVideoConfig();
	const studio = studioMode(reel);
	const u = Math.min(reel.width,reel.height);
	const accent = reel.design?.accent??'#6FE7FF', secondary = reel.design?.secondary??'#8B5CF6';
	const rim1 = mixHex(accent,'#ffffff',.5), rim2 = mixHex(secondary,'#ffffff',.35);
	return <>{segs.map((s,i)=>{
		// seul le plan affiché à cet instant est calculé (les autres Sequence ne montrent rien)
		if (t < s.out_start - .5/fps || t >= s.out_start + segLen(s) + .5/fps) return null;
		const mask = validCutout(reel,s);
		if (!mask) return null;
		const tSrc = segSrcTime(s,t);
		const mix = cutoutFallbackMix(mask,tSrc);
		const f=framing(reel,s.source,tSrc,s.src_in,s.src_out);
		const view = studio ? studioView(reel,s,t) : null;
		// plan tel qu'on le voit (angle multicaméra) : même couleur que la prise d'origine du repli (SegmentVideo)
		const raw = reel.clips.find(c=>c.id===s.clip);
		const clip = raw ? visualClip(reel,raw) : undefined;
		const id = `studio-personne-${i}`;
		const k = f.width/1080;
		const style:React.CSSProperties={position:'absolute',left:f.left,top:f.top,width:f.width,height:f.height,opacity:studio?1:1-mix,
			filter:reel.design?.mode==='collage'?'drop-shadow(6px 0 0 white) drop-shadow(-6px 0 0 white) drop-shadow(0 6px 0 white) drop-shadow(0 -6px 0 white) drop-shadow(8px 14px 10px #00000033)'
				:studio?`url(#${id}) drop-shadow(0 ${u*.022}px ${u*.035}px #000000b8)`
				:reel.design?.mode==='produit'?`drop-shadow(0 20px 34px #000c) drop-shadow(0 0 16px ${accent}26)`:undefined};
		// format large : la caméra recule et les côtés de la prise entrent dans l'image -> une main coupée par le bord de la
		// prise s'efface au lieu de montrer une coupe droite
		if (view?.wide) style.WebkitMaskImage = style.maskImage = 'linear-gradient(90deg,transparent,#000 7%,#000 93%,transparent)';
		const frame=Math.min((mask.count??1)-1,Math.max(0,Math.floor((tSrc-mask.start)*(mask.fps??fps))));
		const media = mask.frames?<Img src={`${assetBase}/${mask.frames.replace(/^assets\//,'')}/${String(frame).padStart(5,'0')}.webp`} style={style}/>:<OffthreadVideo src={`${assetBase}/${mask.file.replace(/^assets\//,'')}`} trimBefore={Math.max(0,Math.round((s.src_in-mask.start)*fps))}
			playbackRate={s.speed??1} transparent muted style={style} />;
		return <Sequence key={i} from={Math.round(s.out_start*fps)} durationInFrames={Math.max(1,Math.round(segLen(s)*fps))} layout="none">
			{studio && mix<1 && clip ? <>
				<svg style={{position:'absolute',width:0,height:0}} aria-hidden>
					<filter id={id} x="-4%" y="-4%" width="108%" height="108%" colorInterpolationFilters="sRGB">
						<feColorMatrix in="SourceGraphic" type="matrix" values={studioGrade(reel,s,colorGains(reel,clip,tSrc,ref0)).join(' ')} result="etal"/>
						{/* bord resserré d'un pixel puis adouci : retire le liseré clair laissé par le décor d'origine (mur, fenêtre) */}
						<feMorphology in="SourceAlpha" operator="erode" radius={Math.max(.5,k)} result="resserre"/>
						<feGaussianBlur in="resserre" stdDeviation={.7*k} result="alpha"/>
						<feComposite in="etal" in2="alpha" operator="in" result="net"/>
						{/* occlusion de bord : bande intérieure étroite assombrie vers le bleu nuit du studio (la personne est DANS le décor) */}
						<feGaussianBlur in="alpha" stdDeviation={5*k} result="flou"/>
						<feComposite in="alpha" in2="flou" operator="out" result="bord"/>
						<feFlood floodColor="#0a1426" floodOpacity={0.5}/>
						<feComposite in2="bord" operator="in" result="occlusion"/>
						<feComposite in="occlusion" in2="net" operator="over" result="integre"/>
						{/* lumière de contour FINE (pas de halo) : clé couleur d'accent en haut à gauche (la lueur du décor), contre-jour
						    secondaire plus faible à droite ; liseré de ~3 px collé au bord, à l'intérieur de la silhouette */}
						<feOffset in="alpha" dx={3.5*k} dy={3*k} result="decale1"/>
						<feComposite in="alpha" in2="decale1" operator="out" result="cote1"/>
						<feFlood floodColor={rim1} floodOpacity={0.52}/>
						<feComposite in2="cote1" operator="in" result="contour1"/>
						<feOffset in="alpha" dx={-3*k} dy={1.5*k} result="decale2"/>
						<feComposite in="alpha" in2="decale2" operator="out" result="cote2"/>
						<feFlood floodColor={rim2} floodOpacity={0.34}/>
						<feComposite in2="cote2" operator="in" result="contour2"/>
						<feMerge result="contours"><feMergeNode in="contour1"/><feMergeNode in="contour2"/></feMerge>
						<feGaussianBlur in="contours" stdDeviation={1.1*k} result="contoursDoux"/>
						<feComposite in="contoursDoux" in2="alpha" operator="in" result="contoursDedans"/>
						<feBlend in="contoursDedans" in2="integre" mode="screen"/>
					</filter>
				</svg>
				<AbsoluteFill style={view?{transform:`scale(${view.scale})`,transformOrigin:`${view.ox*100}% ${view.oy*100}%`}:undefined}>{media}</AbsoluteFill>
			</> : studio ? null : media}
		</Sequence>;
	})}</>;
};

/** Plage de repli du détourage : la prise d'origine (rendue sous le studio par Reel.tsx, même caméra, étalonnée comme la
 * personne détourée, décor flou et sombre, personne nette au centre) reçoit la teinte, le vignettage et le bas sombre du
 * studio. mix : 0 -> 1 (fondu enchaîné). */
const StudioFallback: React.FC<{reel: ReelDoc; mix: number; fx: number; fy: number}> = ({reel,mix,fx,fy}) => {
	const cx=`${(fx*100).toFixed(1)}%`, cy=`${((fy+.12)*100).toFixed(1)}%`;
	return <AbsoluteFill style={{pointerEvents:'none'}}>
		<AbsoluteFill style={{opacity:.24*mix,background:mixHex(reel.design?.accent??'#6FE7FF','#0a1a33',.72),mixBlendMode:'color'}}/>
		<AbsoluteFill style={{opacity:mix,background:`radial-gradient(ellipse 64% 56% at ${cx} ${cy}, transparent 34%, #03060dd6 100%)`}}/>
		<AbsoluteFill style={{opacity:mix,background:'linear-gradient(transparent 64%, #02040ae6)'}}/>
	</AbsoluteFill>;
};

/** Studio virtuel du style Tech 3D. Il n'invente aucun objet : il remplace seulement le décor quand le vrai
 * détourage de la personne est disponible. Sans détourage valide, la prise originale reste visible.
 * Aucun texte interne (titre du reel, minuteur) : seule la marque du client peut apparaître, discrète. La caméra
 * (studioView) pousse lentement sur les temps forts du récit ; le décor bouge moins que la personne (profondeur). */
export const ProductStage: React.FC<{reel: ReelDoc; t: number; assetBase: string}> = ({reel,t,assetBase}) => {
	const segs=useMemo(()=>videoSegments(reel),[reel]);
	const frame=useCurrentFrame();
	const active=segs.find(s=>t>=s.out_start&&t<s.out_start+segLen(s));
	const m=active?validCutout(reel,active):null;
	if(!studioMode(reel)||!active||!m)return null;
	const W=reel.width,H=reel.height,u=Math.min(W,H),accent=reel.design?.accent??'#6FE7FF',secondary=reel.design?.secondary??'#8B5CF6';
	const mix=cutoutFallbackMix(m,segSrcTime(active,t));
	const view=studioView(reel,active,t)!;
	const p=studioPersonAt(reel,segs,t);
	const fx=p?.fx??.5, fy=p?.fy??.42;
	const brand=reel.brand?.name&&!reel.brand.logo?reel.brand.name.trim().slice(0,32):'';
	const breathe=Math.sin(frame/150)*2;  // lumière qui respire lentement (aucun mouvement de caméra)
	return <>
		{mix<1?<AbsoluteFill style={{overflow:'hidden',background:'#03060d',opacity:1-mix}}>
			<AbsoluteFill style={{transform:`scale(${view.bg})`,transformOrigin:`${view.ox*100}% 50%`}}>
				<AbsoluteFill style={{background:`radial-gradient(circle at ${22+breathe}% 16%,${accent}38,transparent 38%),radial-gradient(circle at 86% ${74-breathe}%,${secondary}30,transparent 36%),linear-gradient(155deg,#060b16 0%,#070b17 48%,#02040a 100%)`}}/>
				{/* faisceaux doux venant du haut : le tiers haut est éclairé, pas vide */}
				<AbsoluteFill style={{opacity:.9,background:`linear-gradient(104deg,transparent 18%,${accent}10 30%,transparent 42%),linear-gradient(76deg,transparent 52%,${secondary}0d 64%,transparent 76%)`,maskImage:'linear-gradient(to bottom,black 0%,transparent 58%)',WebkitMaskImage:'linear-gradient(to bottom,black 0%,transparent 58%)'}}/>
				<AbsoluteFill style={{opacity:.13,backgroundImage:`linear-gradient(${accent}35 1px,transparent 1px),linear-gradient(90deg,${accent}35 1px,transparent 1px)`,backgroundSize:`${u*.11}px ${u*.11}px`,maskImage:'linear-gradient(to bottom,transparent 4%,black 34%,transparent 86%)',WebkitMaskImage:'linear-gradient(to bottom,transparent 4%,black 34%,transparent 86%)'}}/>
				{/* contre-jour derrière la personne : la détache du fond, sans halo néon */}
				<AbsoluteFill style={{background:`radial-gradient(ellipse ${u*.62}px ${u*.56}px at ${fx*100}% ${(fy-.02)*100}%,${accent}24,${accent}0a 45%,transparent 72%)`}}/>
			</AbsoluteFill>
			{/* ombre de la personne sur le fond du studio (lumière clé en haut à gauche) */}
			<AbsoluteFill style={{background:`radial-gradient(ellipse ${W*.46}px ${H*.34}px at ${(fx+.05)*100}% 92%,#000000b0,transparent 72%)`}}/>
			<Foreground reel={reel} t={t} assetBase={assetBase}/>
			{/* ombre de contact / occlusion en bas de l'image, là où la personne sort du cadre */}
			<div style={{position:'absolute',left:0,right:0,bottom:0,height:H*.3,background:'linear-gradient(transparent,#02040a8c 55%,#02040af0)'}}/>
			{brand?<div style={{position:'absolute',left:W*.06,top:H*.045,display:'flex',alignItems:'center',gap:u*.014,fontFamily:`'${STUDIO_UI_FONT}', sans-serif`,fontWeight:700,fontSize:u*.03,letterSpacing:1.5,color:'#dce8ff8c'}}>
				<span style={{width:u*.014,height:u*.014,borderRadius:'50%',background:accent,boxShadow:`0 0 ${u*.02}px ${accent}`}}/>{brand}
			</div>:null}
		</AbsoluteFill>:null}
		{mix>0?<StudioFallback reel={reel} mix={mix} fx={fx} fy={fy}/>:null}
	</>;
};

/** Typographie qui s'accumule, avec hiérarchie et espaces protégés autour du visage.
 * Le mot géant (derrière la personne) vient des scènes « keyword » choisies par le moteur (un bloc fort, rarement) ;
 * pendant qu'il est affiché, les mêmes mots restent simples dans la ligne de texte : jamais deux traitements
 * du même mot en même temps. Réglages de la scène (texte, couleur, taille, position, rotation) : le mot géant. */
export const Kinetic: React.FC<{reel: ReelDoc; t: number; behind?: boolean}> = ({reel,t,behind=false}) => {
	const all = useMemo(()=>pages(reel),[reel]);
	const keys = useMemo(()=>designScenes(reel).filter(s=>s.kind==='keyword'),[reel]);
	const segs = useMemo(()=>videoSegments(reel),[reel]);
	if (reel.design?.enabled===false) return null;
	const {width:W,height:H}= {width:reel.width,height:reel.height};
	const key=keys.find(s=>t>=s.at&&t<s.end);
	if (behind) {
		if (!key) return null;
		const text=displayWord(key.text,true);
		const local=t-key.at,len=key.end-key.at;
		// mot géant DERRIÈRE la personne : sans détourage fiable à cet instant (plage de repli), il passerait devant elle
		const seg=segs.find(s=>t>=s.out_start&&t<s.out_start+segLen(s));
		const cut=seg?validCutout(reel,seg):null;
		const behindOk=cut?1-cutoutFallbackMix(cut,segSrcTime(seg!,t)):1;
		const opacity=behindOk*interpolate(local,[0,.15,Math.max(.16,len-.2),len],[0,.94,.94,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
		return <div style={{position:'absolute',left:W*.02,top:H*.16,width:W*.96,textAlign:'center',color:key.color||reel.design?.accent,
			fontFamily:reel.style.font,fontWeight:900,fontSize:Math.min(W*.28,W*.96/Math.max(3,text.length*.49))*(key.scale??1),lineHeight:1,opacity,
			transform:`translate(${(key.x-.5)*W}px,${(key.y-.69)*H}px) rotate(${key.rotation??0}deg)`}}>{text}</div>;
	}
	const page=all.find(p=>t>=p.start&&t<p.end);
	if (!page) return null;
	const inKey=(w:{clip:string;index:number})=>!!key&&w.clip===key.clip&&w.index>=key.index&&w.index<key.index+(key.length??1);
	return <div style={{position:'absolute',left:W*.08,right:W*.08,top:H*reel.style.position,display:'flex',flexWrap:'wrap',alignItems:'baseline',gap:W*.015,
		fontFamily:reel.style.font,textShadow:'0 3px 18px #0008'}}>
		{page.words.map((w,i)=>{
			if (t<w.outStart) return null;
			const hl=w.hl&&!inKey(w);
			return <span key={i} style={{fontSize:Math.min(reel.style.size*W/1080*(hl?1.6:.75),W*.82/Math.max(3,w.w.length*.58)),fontWeight:hl?900:500,
			color:hl?(reel.design?.accent??reel.style.highlight):reel.style.color,transform:`rotate(${hl?-4:0}deg)`,lineHeight:1.13}}>{hl?'« ':''}{displayWord(w.w,hl)}{hl?' »':''}</span>;
		})}
	</div>;
};

/** Texte technique (ancien habillage) : jamais affiché à l'image. */
const TECH_LABEL=/exemple|illustration|interface|d[ée]mo\b|mockup|example|pas une mesure/i;
const shown=(s?:string)=>s&&!TECH_LABEL.test(s)?s:'';

export const DesignDecor: React.FC<{reel: ReelDoc; t: number}> = ({reel,t}) => {
	const frame=useCurrentFrame();
	const mode=reel.design?.enabled===false?null:reel.design?.mode;
	const W=reel.width,H=reel.height,u=Math.min(W,H);
	if(mode==='documentaire') {
		// titre discret : celui du style, sinon le titre du reel s'il n'est pas un nom de fichier (« Script 1 - 0 COMPLET… »)
		const title=reel.design?.title||(/COMPLET|Hook|Script\s*\d|FINAL|\(\d+x\d+\)/i.test(reel.title)?'':reel.title);
		return <>
		<div style={{position:'absolute',top:0,width:'100%',height:H*.08,background:'#080808'}} />
		<div style={{position:'absolute',bottom:0,width:'100%',height:H*.08,background:'#080808'}} />
		{t<4.5&&title?<div style={{position:'absolute',left:W*.07,bottom:H*.14,maxWidth:W*.8,fontFamily:reel.style.font,fontSize:u*.032,letterSpacing:3,color:'#ded7cb',borderLeft:'3px solid #ded7cb',paddingLeft:20}}>{title}</div>:null}
	</>;
	}
	if(mode==='luxe') return <>
		<div style={{position:'absolute',bottom:0,width:'100%',height:H*.4,background:'linear-gradient(transparent,#10100fd9)'}} />
		<div style={{position:'absolute',left:W*.1,bottom:H*.12,width:W*.8,height:1,background:reel.design?.accent,opacity:.6}} />
	</>;
	if(mode==='vhs') return <AbsoluteFill style={{pointerEvents:'none'}}>
		<AbsoluteFill style={{backgroundImage:'repeating-linear-gradient(transparent 0px,transparent 3px,#0003 4px)',opacity:.55}} />
		<div style={{position:'absolute',left:W*.07,top:H*.075,fontFamily:'monospace',fontSize:u*.045,color:'#eeeece',textShadow:'3px 0 #db657177'}}>PLAY ▷</div>
		<div style={{position:'absolute',left:W*.07,bottom:H*.09,fontFamily:'monospace',fontSize:u*.035,color:'#eeeece'}}>{reel.design?.date||(reel.brand?.name?`${reel.brand.name.toUpperCase()} · REC`:'REC')} · 00:{Math.floor(t).toString().padStart(2,'0')}:{(frame%reel.fps).toString().padStart(2,'0')}</div>
	</AbsoluteFill>;
	return null;
};

type Active=StyleScene&{at:number;end:number};
const STUDIO_CARDS=new Set(['metric','notification','dashboard','flow','cta']);
export const DesignScenes: React.FC<{reel:ReelDoc;t:number;assetBase:string}> = ({reel,t,assetBase}) => {
	const scenes=useMemo(()=>designScenes(reel),[reel]);
	const g=scenes.find(s=>t>=s.at&&t<s.end);
	if(!g || reel.design?.mode==='editorial') return null;
	const card=studioMode(reel)&&STUDIO_CARDS.has(g.kind);
	return <Choreo reel={reel} cible={{type:'design',id:g.id}} t={t} at={g.at} duration={g.end-g.at}>{card?<StudioCard reel={reel} g={g} t={t}/>:<Scene reel={reel} g={g} t={t} assetBase={assetBase}/>}</Choreo>;
};

// ---------- Interfaces du studio Tech 3D : verre sombre, liseré lumineux, grand texte lisible sur un téléphone ----------
// Tailles en part du petit côté u : texte principal >= 0,05 u, texte secondaire >= 0,04 u (lisible à 4,5 % de la largeur).
// Gabarits (largeur, hauteur) : studioCardSize() de timeline.ts, qui place la carte hors de la personne.
const studioFont=`'${STUDIO_UI_FONT}', sans-serif`;
/** Verre sombre + liseré clair et net tout autour (plus vif en haut à gauche, où il accroche la lumière), fine lueur
 * blanche serrée puis lueur d'accent large, comme les pilules de la référence. */
export const studioGlass=(u:number,accent:string,active=false):React.CSSProperties=>({
	background:active
		?`linear-gradient(140deg,${mixHex(accent,'#0b1220',.55)} 0%,${mixHex(accent,'#070b14',.82)} 100%) padding-box,linear-gradient(135deg,#ffffff 0%,${mixHex(accent,'#ffffff',.4)} 45%,${accent} 100%) border-box`
		:`linear-gradient(165deg,#232c3ef7 0%,#0e131ef8 58%,#080b12fa 100%) padding-box,linear-gradient(135deg,#ffffff 0%,#ffffffb3 22%,#ffffff66 52%,${mixHex(accent,'#ffffff',.35)}b3 80%,${accent} 100%) border-box`,
	border:`${Math.max(2,Math.round(u*.0034))}px solid transparent`,
	boxShadow:active
		?`0 0 ${u*.012}px #ffffff4d,0 0 ${u*.06}px ${accent}66,0 ${u*.03}px ${u*.08}px #000d,inset 0 1px 0 #ffffff66`
		:`0 0 ${u*.012}px #ffffff33,0 0 ${u*.055}px ${accent}2e,0 ${u*.03}px ${u*.08}px #000d,inset 0 1px 0 #ffffff40`,
});
const ease=(x:number)=>1-Math.pow(1-Math.min(1,Math.max(0,x)),3);
const Check:React.FC<{size:number;k:number;color:string}>=({size,k,color})=><svg viewBox="0 0 24 24" style={{width:size,height:size,flexShrink:0}}>
	<circle cx="12" cy="12" r="10.5" fill={k>0?color:'none'} fillOpacity={.18+.82*k} stroke={color} strokeWidth="1.6"/>
	<path d="M6.8 12.4l3.4 3.4 7-7.4" fill="none" stroke="#04101c" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="16" strokeDashoffset={16*(1-k)}/>
</svg>;

/** Chiffre réellement dit : grand nombre lumineux dans une pilule de verre, libellé dessous. Partagé avec graphics.tsx. */
export const StudioMetric:React.FC<{reel:ReelDoc;text:string;label?:string;local:number;len:number;accent:string}>=({reel,text,label,local,len,accent})=>{
	const u=Math.min(reel.width,reel.height);
	const e=ease(local/.4);
	const out=Math.min(1,Math.max(0,(len-local)/.25));
	return <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:u*.012,opacity:Math.min(1,local/.18)*out,transform:`translateY(${(1-e)*u*.035}px) scale(${.92+.08*e})`,fontFamily:studioFont}}>
		<div style={{...studioGlass(u,accent),borderRadius:999,padding:`${u*.035}px ${u*.085}px`,display:'flex',alignItems:'center',justifyContent:'center'}}>
			<span style={{fontSize:u*.15,fontWeight:800,lineHeight:1,letterSpacing:-u*.004,color:'#ffffff',textShadow:`0 0 ${u*.035}px ${accent}aa,0 0 ${u*.09}px ${accent}55`,whiteSpace:'nowrap'}}>{text}</span>
		</div>
		{label?<div style={{fontSize:u*.05,fontWeight:700,color:'#dbe6f7',letterSpacing:u*.0015,textShadow:'0 2px 12px #000c',whiteSpace:'nowrap',opacity:ease((local-.2)/.3)}}>{label}</div>:null}
	</div>;
};

const StudioCard:React.FC<{reel:ReelDoc;g:PlacedScene;t:number}>=({reel,g,t})=>{
	const W=reel.width,H=reel.height,u=Math.min(W,H),local=t-g.at,len=g.end-g.at;
	const accent=g.color||reel.design?.accent||'#6FE7FF',secondary=reel.design?.secondary||'#8B5CF6';
	const e=ease(local/.38);
	const out=Math.min(1,Math.max(0,(len-local)/.25));
	const wrap:React.CSSProperties={position:'absolute',left:W*g.x,top:H*g.y,transform:`translate(-50%,-50%) translateY(${(1-e)*u*.04}px) scale(${g.scale*(.94+.06*e)*(.97+.03*out)}) rotate(${g.rotation}deg)`,
		opacity:Math.min(1,local/.2)*out,fontFamily:studioFont,color:'#f4f8ff',boxSizing:'border-box'};
	if(g.kind==='metric') return <div style={wrap}><StudioMetric reel={reel} text={g.text} label={shown(g.secondary)} local={local} len={len} accent={accent}/></div>;
	if(g.kind==='flow'){
		const parts=[g.text,...(g.secondary||'').split('|')].map(x=>x.trim()).filter((x,i,a)=>x&&a.indexOf(x)===i).slice(0,3);
		const column=parts.length>2;
		const fs=column?u*.046:u*.056;
		return <div style={{...wrap,display:'flex',flexDirection:column?'column':'row',alignItems:'center',justifyContent:'center',gap:column?u*.012:u*.022,width:W*.92}}>
			{parts.map((p,i)=>{
				const k=ease((local-.08-i*.24)/.3), done=ease((local-.32-i*.24)/.25), last=i===parts.length-1;
				return <React.Fragment key={p}>
					{i>0?<div style={{color:accent,fontSize:column?u*.045:u*.062,fontWeight:800,lineHeight:1,opacity:ease((local-i*.24)/.2),textShadow:`0 0 ${u*.025}px ${accent}`,transform:column?'rotate(90deg)':undefined}}>→</div>:null}
					<div style={{...studioGlass(u,accent,last&&k>=.99),borderRadius:999,padding:`${u*.03}px ${u*.048}px`,display:'flex',alignItems:'center',gap:u*.02,opacity:k,transform:`translateX(${(1-k)*(column?0:-u*.03)}px) scale(${.9+.1*k})`,whiteSpace:'nowrap'}}>
						{!last?<Check size={fs*.95} k={done*(parts.length>1?1:0)} color={accent}/>:null}
						<span style={{fontSize:fs,fontWeight:800,letterSpacing:-u*.0008,lineHeight:1.15,textShadow:last?`0 0 ${u*.03}px ${accent}88`:undefined}}>{p}</span>
					</div>
				</React.Fragment>;
			})}
		</div>;
	}
	if(g.kind==='dashboard'){
		const items=(g.secondary||'').split('|').map(x=>x.trim()).filter(Boolean).slice(0,3);
		const rows=items.length?items:[g.text];
		const pulse=.55+.45*Math.abs(Math.sin(local*2.4));
		return <div style={{...wrap,width:u*.86,...studioGlass(u,accent),borderRadius:u*.055,padding:u*.042}}>
			<div style={{display:'flex',alignItems:'center',gap:u*.022,marginBottom:u*.028}}>
				<span style={{width:u*.07,height:u*.07,borderRadius:'50%',background:`linear-gradient(140deg,${accent},${secondary})`,color:'#04101c',display:'flex',alignItems:'center',justifyContent:'center',fontSize:u*.04,fontWeight:800,flexShrink:0,boxShadow:`0 0 ${u*.03}px ${accent}66`}}>{g.text.slice(0,1).toUpperCase()}</span>
				<span style={{fontSize:u*.062,fontWeight:800,letterSpacing:-u*.001}}>{g.text}</span>
				<span style={{marginLeft:'auto',width:u*.024,height:u*.024,borderRadius:'50%',background:accent,opacity:pulse,boxShadow:`0 0 ${u*.03}px ${accent}`}}/>
			</div>
			<div style={{display:'grid',gap:u*.016}}>{rows.map((it,i)=>{
				const k=ease((local-.15-i*.18)/.3), done=ease((local-.5-i*.3)/.3);
				return <div key={i} style={{display:'flex',alignItems:'center',gap:u*.024,borderRadius:u*.03,padding:`${u*.022}px ${u*.028}px`,background:'#ffffff0d',border:'1px solid #ffffff1c',opacity:k,transform:`translateY(${(1-k)*u*.02}px)`}}>
					<Check size={u*.058} k={done} color={i?secondary:accent}/>
					<span style={{fontSize:u*.054,fontWeight:750}}>{it}</span>
					<span style={{marginLeft:'auto',width:u*.12,height:u*.012,borderRadius:99,background:'#ffffff14',overflow:'hidden'}}><span style={{display:'block',height:'100%',width:`${100*done}%`,borderRadius:99,background:i?secondary:accent,boxShadow:`0 0 ${u*.02}px ${i?secondary:accent}`}}/></span>
				</div>;
			})}</div>
		</div>;
	}
	if(g.kind==='notification'){
		const app=shown(g.secondary)||reel.brand?.name||'Messages';
		return <div style={{...wrap,width:u*.84,...studioGlass(u,accent),borderRadius:u*.05,padding:`${u*.036}px ${u*.042}px`}}>
			<div style={{display:'flex',alignItems:'center',gap:u*.02,fontSize:u*.046,fontWeight:700,color:'#c6d3e6'}}>
				<span style={{width:u*.07,height:u*.07,borderRadius:u*.02,background:`linear-gradient(145deg,${accent},${secondary})`,color:'#04101c',display:'flex',alignItems:'center',justifyContent:'center',fontSize:u*.04,fontWeight:800,flexShrink:0,boxShadow:`0 0 ${u*.03}px ${accent}55`}}>{app.slice(0,1).toUpperCase()}</span>
				<span style={{whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{app}</span>
				<span style={{marginLeft:'auto',fontWeight:600,color:accent,whiteSpace:'nowrap'}}>{/^(new|reply|lead waiting|incoming)/i.test(g.text)?'now':'maintenant'}</span>
			</div>
			<div style={{fontSize:u*.058,fontWeight:800,marginTop:u*.02,lineHeight:1.14,letterSpacing:-u*.001}}>{g.text}</div>
		</div>;
	}
	// bouton d'appel à l'action : texte exact, pilule lumineuse, onde d'appui
	const tap=Math.max(0,local-.75), ring=Math.min(1,tap/.7);
	return <div style={{...wrap,display:'flex',flexDirection:'column',alignItems:'center',maxWidth:W*.9}}>
		{shown(g.secondary)?<div style={{fontSize:u*.046,fontWeight:700,letterSpacing:u*.005,textTransform:'uppercase',color:'#c9d6ea',marginBottom:u*.028,textShadow:'0 2px 10px #000c'}}>{shown(g.secondary)}</div>:null}
		<div style={{position:'relative',padding:`${u*.042}px ${u*.088}px`,borderRadius:999,background:`linear-gradient(105deg,${secondary},${accent}) padding-box,linear-gradient(135deg,#ffffff,#ffffff66 40%,${accent}) border-box`,border:`${Math.max(2,Math.round(u*.003))}px solid transparent`,
			color:'#04101c',fontSize:u*.064,fontWeight:800,letterSpacing:-u*.001,whiteSpace:'nowrap',boxShadow:`0 0 ${u*.09}px ${accent}70,0 ${u*.035}px ${u*.09}px #000b,inset 0 2px 0 #ffffff80`,transform:`scale(${1-.035*Math.sin(Math.min(1,tap/.25)*Math.PI)})`}}>
			{tap>0&&ring<1?<div style={{position:'absolute',inset:-u*.02*ring*2,borderRadius:999,border:`${Math.max(2,u*.004)}px solid ${accent}`,opacity:1-ring}}/>:null}
			{g.text}<span style={{marginLeft:u*.025}}>→</span>
		</div>
	</div>;
};
const Scene:React.FC<{reel:ReelDoc;g:Active;t:number;assetBase:string}>=({reel,g,t,assetBase})=>{
	const W=reel.width,H=reel.height,u=Math.min(W,H),local=t-g.at;
	const opacity=interpolate(local,[0,.18,g.end-g.at-.2,g.end-g.at],[0,1,1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
	const enter=interpolate(local,[0,.28],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
	const accent=g.color||reel.design?.accent||'#6FE7FF',secondary=reel.design?.secondary||'#8B5CF6';
	const base:React.CSSProperties={position:'absolute',left:W*g.x,top:H*g.y,width:W*.82,transform:`translate(-50%,calc(-50% + ${(1-enter)*u*.06}px)) scale(${g.scale*(.94+.06*enter)}) rotate(${g.rotation}deg)`,fontFamily:reel.style.font,color:'#fff',opacity,boxSizing:'border-box'};
	// chiffre dit dans la vidéo : aucune courbe ni tendance inventée, un simple trait qui se dessine
	if(g.kind==='metric') return <div style={{...base,width:'auto',minWidth:u*.48,maxWidth:u*.86,padding:`${u*.045}px ${u*.06}px`,borderRadius:u*.045,background:'linear-gradient(145deg,#101827f5,#070b14f2)',border:`1px solid ${accent}88`,boxShadow:`0 0 ${u*.08}px ${accent}25,0 ${u*.035}px ${u*.09}px #0009`,textAlign:'center',backdropFilter:'blur(18px)'}}>
		<div style={{position:'absolute',inset:u*.012,borderRadius:u*.035,border:'1px solid #ffffff12',pointerEvents:'none'}}/>
		<div style={{fontSize:u*.13,fontWeight:850,letterSpacing:-3,color:accent,lineHeight:1,textShadow:`0 0 ${u*.055}px ${accent}65`}}>{g.text}</div>
		{shown(g.secondary)?<div style={{fontSize:u*.04,marginTop:15}}>{shown(g.secondary)}</div>:null}
		<div style={{height:u*.008,marginTop:u*.03,borderRadius:u*.004,background:`linear-gradient(90deg,${accent},${secondary})`,boxShadow:`0 0 ${u*.025}px ${accent}`,width:`${100*Math.min(1,local/.65)}%`}}/>
	</div>;
	if(g.kind==='notification') {
		// notification de téléphone : nom de l'application, titre court ; placée par le moteur hors du visage
		const app=shown(g.secondary)||reel.brand?.name||'Messages';
		return <div style={{...base,width:u*.79,background:'linear-gradient(145deg,#121a2af5,#080d18f2)',borderRadius:u*.045,color:'#f6f9ff',padding:`${u*.034}px ${u*.04}px`,border:'1px solid #ffffff20',boxShadow:`0 ${u*.03}px ${u*.09}px #0009,0 0 ${u*.06}px ${accent}1e`,backdropFilter:'blur(18px)'}}>
			<div style={{display:'flex',gap:u*.02,alignItems:'center',fontSize:u*.026,fontWeight:650,color:'#a9b8ce'}}>
				<span style={{width:u*.058,height:u*.058,borderRadius:u*.018,background:`linear-gradient(145deg,${accent},${secondary})`,color:'#05101d',display:'flex',alignItems:'center',justifyContent:'center',fontSize:u*.032,fontWeight:900,flexShrink:0,boxShadow:`0 0 ${u*.035}px ${accent}55`}}>{app.slice(0,1).toUpperCase()}</span>
				<span style={{whiteSpace:'nowrap',overflow:'hidden'}}>{app}</span>
				<span style={{marginLeft:'auto',fontWeight:500,color:accent}}>{/^(new|reply|lead waiting|incoming)/i.test(g.text)?'now':'maintenant'}</span>
			</div>
			<div style={{fontSize:u*.05,fontWeight:780,marginTop:u*.022,lineHeight:1.14,letterSpacing:-1}}>{g.text}</div>
		</div>;
	}
	if(g.kind==='dashboard') {
		const items=(g.secondary||'').split('|').map(x=>x.trim()).filter(Boolean).slice(0,3);
		return <div style={{...base,width:W*.88,borderRadius:u*.05,padding:u*.042,background:'linear-gradient(150deg,#0e1625f7,#050914f5)',border:'1px solid #ffffff1f',boxShadow:`0 ${u*.04}px ${u*.12}px #000b,0 0 ${u*.09}px ${accent}1f`,backdropFilter:'blur(20px)'}}>
			<div style={{display:'flex',alignItems:'center',gap:u*.018,marginBottom:u*.035}}><span style={{width:u*.022,height:u*.022,borderRadius:'50%',background:accent,boxShadow:`0 0 ${u*.03}px ${accent}`}}/><span style={{fontSize:u*.046,fontWeight:800,letterSpacing:-1}}>{g.text}</span><span style={{marginLeft:'auto',fontSize:u*.022,color:'#ffffff66',letterSpacing:2}}>LIVE</span></div>
			<div style={{display:'grid',gap:u*.017}}>{(items.length?items:[g.text]).map((it,i)=><div key={i} style={{position:'relative',overflow:'hidden',display:'flex',alignItems:'center',gap:u*.022,borderRadius:u*.025,padding:`${u*.022}px ${u*.027}px`,background:'#ffffff09',border:'1px solid #ffffff0e'}}>
				<div style={{position:'absolute',left:0,top:0,bottom:0,width:`${Math.min(100,20+enter*80-i*12)}%`,background:`linear-gradient(90deg,${accent}17,transparent)`}}/>
				<span style={{width:u*.036,height:u*.036,borderRadius:'50%',border:`2px solid ${i?secondary:accent}`,boxShadow:`0 0 ${u*.024}px ${i?secondary:accent}`}}/><span style={{fontSize:u*.033,fontWeight:650,zIndex:1}}>{it}</span><span style={{marginLeft:'auto',width:u*.075,height:u*.008,borderRadius:99,background:i?secondary:accent,boxShadow:`0 0 ${u*.02}px ${i?secondary:accent}`}}/>
			</div>)}</div>
		</div>;
	}
	if(g.kind==='flow') {
		const parts=[g.text,...(g.secondary||'').split('|')].map(x=>x.trim()).filter((x,i,a)=>x&&a.indexOf(x)===i).slice(0,4);
		return <div style={{...base,width:W*.9,padding:`${u*.04}px ${u*.025}px`,borderRadius:u*.05,background:'#060b15ed',border:'1px solid #ffffff17',boxShadow:`0 ${u*.04}px ${u*.12}px #000a`,backdropFilter:'blur(18px)'}}>
			<div style={{display:'flex',alignItems:'stretch',justifyContent:'center',gap:u*.012}}>{parts.map((p,i)=><React.Fragment key={p}><div style={{flex:1,minWidth:0,padding:`${u*.032}px ${u*.014}px`,borderRadius:u*.027,background:i===parts.length-1?`linear-gradient(145deg,${accent}2e,${secondary}22)`:'#ffffff09',border:`1px solid ${i===parts.length-1?accent+'77':'#ffffff16'}`,textAlign:'center',fontSize:u*.027,fontWeight:720,display:'flex',alignItems:'center',justifyContent:'center',boxShadow:i===parts.length-1?`0 0 ${u*.05}px ${accent}22`:undefined}}>{p}</div>{i<parts.length-1?<div style={{display:'flex',alignItems:'center',color:accent,fontSize:u*.034,opacity:interpolate(local,[.18+i*.11,.38+i*.11],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}}>›</div>:null}</React.Fragment>)}</div>
		</div>;
	}
	if(g.kind==='cta') return <div style={{...base,width:'auto',maxWidth:W*.86,textAlign:'center'}}>
		{shown(g.secondary)?<div style={{fontSize:u*.025,letterSpacing:3,textTransform:'uppercase',color:'#c3cde0',marginBottom:u*.028}}>{shown(g.secondary)}</div>:null}
		<div style={{position:'relative',padding:`${u*.045}px ${u*.085}px`,borderRadius:u*.06,background:`linear-gradient(105deg,${secondary},${accent})`,color:'#04101a',fontSize:u*.055,fontWeight:900,letterSpacing:-1,boxShadow:`0 0 ${u*.09}px ${accent}66,0 ${u*.035}px ${u*.09}px #000a`}}>
			<div style={{position:'absolute',inset:u*.008,borderRadius:u*.052,border:'1px solid #ffffff70'}}/>{g.text}<span style={{marginLeft:u*.025}}>→</span>
		</div>
	</div>;
	if(g.kind==='comparison') return <div style={{...base,display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
		{[g.text,g.secondary].map((text,i)=><div key={i} style={{background:i?'#0f342bee':'#301b22ee',borderTop:`5px solid ${i?accent:'#d8a3a3'}`,padding:u*.03,minHeight:u*.22}}>
		<div style={{fontSize:u*.025,letterSpacing:2,color:i?accent:'#e4b8b8',marginBottom:14}}>{i?'APRÈS':'AVANT'}</div><div style={{fontSize:u*.044,lineHeight:1.2,fontWeight:800}}>{text}</div></div>)}
	</div>;
	if(g.kind==='paper') return <div style={{...base,width:'auto',maxWidth:W*.85,padding:`${u*.024}px ${u*.04}px`,background:'#fff9ec',color:'#151515',boxShadow:'5px 8px 0 #0003',borderBottom:`8px solid ${accent}`,fontWeight:900,fontSize:u*.09}}>
		<div style={{position:'absolute',width:'30%',height:25,left:'35%',top:-15,background:'#d8bc80bb',transform:'rotate(4deg)'}}/>{g.text} <span style={{color:accent}}>↗</span>
	</div>;
	if(g.kind==='product'){
		const video=reel.design?.productVideo;
		if(!video) return null;
		return <div style={{...base,height:H*.45,background:'#050506',borderRadius:20,overflow:'hidden'}}>
			<Sequence from={Math.round(g.at*reel.fps)} layout="none"><OffthreadVideo src={`${assetBase}/${video.replace(/^assets\//,'')}`} muted style={{width:'100%',height:'100%',objectFit:'contain'}} /></Sequence>
		</div>;
	}
	return null;
};

/** Les deux côtés montrent la vraie prise ; aucune expression ni résultat n'est fabriqué. */
export const ComparisonVideo:React.FC<{reel:ReelDoc;t:number;mediaBase:string}>=({reel,t,mediaBase})=>{
	const scenes=useMemo(()=>designScenes(reel),[reel]);
	const segs=useMemo(()=>videoSegments(reel),[reel]);
	const active=scenes.some(s=>s.kind==='comparison'&&t>=s.at&&t<s.end);
	const seg=segs.find(s=>t>=s.out_start&&t<s.out_start+segLen(s));
	if(!active||!seg)return null;
	const src=reel.sources[seg.source],W=reel.width,H=reel.height;
	const f=framing({...reel,width:W/2},seg.source,seg.src_in+(t-seg.out_start)*(seg.speed??1),seg.src_in,seg.src_out);
	return <AbsoluteFill style={{display:'flex',flexDirection:'row'}}>{[0,1].map(i=><div key={i} style={{position:'relative',width:'50%',height:'100%',overflow:'hidden',filter:i?'none':'grayscale(1) brightness(.75)',borderRight:i?undefined:`${W*.004}px solid #12191a`}}>
		<Sequence from={Math.round(seg.out_start*reel.fps)} durationInFrames={Math.max(1,Math.round(segLen(seg)*reel.fps))} layout="none">
			<OffthreadVideo src={`${mediaBase}/${src.proxy}`} trimBefore={Math.round(seg.src_in*reel.fps)} playbackRate={seg.speed??1} muted style={{position:'absolute',left:f.left,top:f.top,width:f.width,height:f.height}}/>
		</Sequence>
	</div>)}</AbsoluteFill>;
};
