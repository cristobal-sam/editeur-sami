// Identités de la galerie. Les instants et les ancres sont calculés exclusivement dans timeline.ts.
import React, {useMemo} from 'react';
import {AbsoluteFill, Img, OffthreadVideo, Sequence, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {designScenes, pages, displayWord, framing, videoSegments, segLen, validCutout} from './timeline';
import type {ReelDoc, StyleScene} from './types';

export const DesignBackground: React.FC<{reel: ReelDoc}> = ({reel}) => {
	if (reel.design?.enabled === false || reel.design?.mode !== 'collage') return null;
	return <AbsoluteFill style={{background: '#e7ddc7', backgroundImage: 'repeating-linear-gradient(3deg,#00000006 0px,#00000006 1px,transparent 1px,transparent 5px)'}}>
		<div style={{position:'absolute',left:'5%',top:'5%',width:'24%',height:'3%',background:'#c5aa74aa',transform:'rotate(-8deg)'}} />
		<div style={{position:'absolute',right:'5%',top:'8%',fontSize:130,color:reel.design.accent,transform:'rotate(14deg)'}}>✦</div>
	</AbsoluteFill>;
};

export const Foreground: React.FC<{reel: ReelDoc; t: number; assetBase: string}> = ({reel,t,assetBase}) => {
	const segs = useMemo(()=>videoSegments(reel),[reel]);
	const {fps} = useVideoConfig();
	return <>{segs.map((s,i)=>{
		const mask = validCutout(reel,s);
		if (!mask) return null;
		const f=framing(reel,s.source,s.src_in + Math.max(0,t-s.out_start)*(s.speed??1),s.src_in,s.src_out);
		const style:React.CSSProperties={position:'absolute',left:f.left,top:f.top,width:f.width,height:f.height,
			filter:reel.design?.mode==='collage'?'drop-shadow(6px 0 0 white) drop-shadow(-6px 0 0 white) drop-shadow(0 6px 0 white) drop-shadow(0 -6px 0 white)':undefined};
		const frame=Math.min((mask.count??1)-1,Math.max(0,Math.floor((s.src_in-mask.start+Math.max(0,t-s.out_start)*(s.speed??1))*(mask.fps??fps))));
		return <Sequence key={i} from={Math.round(s.out_start*fps)} durationInFrames={Math.max(1,Math.round(segLen(s)*fps))} layout="none">
			{mask.frames?<Img src={`${assetBase}/${mask.frames.replace(/^assets\//,'')}/${String(frame).padStart(5,'0')}.webp`} style={style}/>:<OffthreadVideo src={`${assetBase}/${mask.file.replace(/^assets\//,'')}`} trimBefore={Math.max(0,Math.round((s.src_in-mask.start)*fps))}
				playbackRate={s.speed??1} transparent muted style={style} />}
		</Sequence>;
	})}</>;
};

/** Typographie qui s'accumule, avec hiérarchie et espaces protégés autour du visage.
 * Le mot géant (derrière la personne) vient des scènes « keyword » choisies par le moteur (un bloc fort, rarement) ;
 * pendant qu'il est affiché, les mêmes mots restent simples dans la ligne de texte : jamais deux traitements
 * du même mot en même temps. Réglages de la scène (texte, couleur, taille, position, rotation) : le mot géant. */
export const Kinetic: React.FC<{reel: ReelDoc; t: number; behind?: boolean}> = ({reel,t,behind=false}) => {
	const all = useMemo(()=>pages(reel),[reel]);
	const keys = useMemo(()=>designScenes(reel).filter(s=>s.kind==='keyword'),[reel]);
	if (reel.design?.enabled===false) return null;
	const {width:W,height:H}= {width:reel.width,height:reel.height};
	const key=keys.find(s=>t>=s.at&&t<s.end);
	if (behind) {
		if (!key) return null;
		const text=displayWord(key.text,true);
		const local=t-key.at,len=key.end-key.at;
		const opacity=interpolate(local,[0,.15,Math.max(.16,len-.2),len],[0,.94,.94,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
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
export const DesignScenes: React.FC<{reel:ReelDoc;t:number;assetBase:string}> = ({reel,t,assetBase}) => {
	const scenes=useMemo(()=>designScenes(reel),[reel]);
	const g=scenes.find(s=>t>=s.at&&t<s.end);
	if(!g || reel.design?.mode==='editorial') return null;
	return <Scene reel={reel} g={g} t={t} assetBase={assetBase}/>;
};
const Scene:React.FC<{reel:ReelDoc;g:Active;t:number;assetBase:string}>=({reel,g,t,assetBase})=>{
	const W=reel.width,H=reel.height,u=Math.min(W,H),local=t-g.at;
	const opacity=interpolate(local,[0,.18,g.end-g.at-.2,g.end-g.at],[0,1,1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
	const base:React.CSSProperties={position:'absolute',left:W*g.x,top:H*g.y,width:W*.82,transform:`translate(-50%,-50%) scale(${g.scale}) rotate(${g.rotation}deg)`,fontFamily:reel.style.font,color:'#fff',opacity};
	// chiffre dit dans la vidéo : aucune courbe ni tendance inventée, un simple trait qui se dessine
	if(g.kind==='metric') return <div style={{...base,width:'auto',minWidth:u*.4,maxWidth:u*.82,padding:`${u*.035}px ${u*.05}px`,borderRadius:u*.03,background:'#111b29ed',border:`2px solid ${g.color}`,textAlign:'center'}}>
		<div style={{fontSize:u*.12,fontWeight:900,color:g.color,lineHeight:1}}>{g.text}</div>
		{shown(g.secondary)?<div style={{fontSize:u*.04,marginTop:15}}>{shown(g.secondary)}</div>:null}
		<div style={{height:u*.008,marginTop:u*.025,borderRadius:u*.004,background:g.color,width:`${100*Math.min(1,local/.6)}%`}}/>
	</div>;
	if(g.kind==='notification') {
		// notification de téléphone : nom de l'application, titre court ; placée par le moteur hors du visage
		const app=shown(g.secondary)||reel.brand?.name||'Messages';
		return <div style={{...base,width:u*.78,background:'#f5f7f9f2',borderRadius:u*.035,color:'#1a2432',padding:`${u*.026}px ${u*.032}px`,boxShadow:'0 14px 40px #0006'}}>
			<div style={{display:'flex',gap:u*.018,alignItems:'center',fontSize:u*.026,fontWeight:700,color:'#627280'}}>
				<span style={{width:u*.052,height:u*.052,borderRadius:u*.013,background:g.color,color:'#081824',display:'flex',alignItems:'center',justifyContent:'center',fontSize:u*.03,flexShrink:0}}>{app.slice(0,1).toUpperCase()}</span>
				<span style={{whiteSpace:'nowrap',overflow:'hidden'}}>{app}</span>
				<span style={{marginLeft:'auto',fontWeight:500}}>{/^(new|reply|lead waiting|incoming)/i.test(g.text)?'now':'maintenant'}</span>
			</div>
			<div style={{fontSize:u*.046,fontWeight:750,marginTop:u*.014,lineHeight:1.2}}>{g.text}</div>
		</div>;
	}
	if(g.kind==='comparison') return <div style={{...base,display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
		{[g.text,g.secondary].map((text,i)=><div key={i} style={{background:i?'#0f342bee':'#301b22ee',borderTop:`5px solid ${i?g.color:'#d8a3a3'}`,padding:u*.03,minHeight:u*.22}}>
		<div style={{fontSize:u*.025,letterSpacing:2,color:i?g.color:'#e4b8b8',marginBottom:14}}>{i?'APRÈS':'AVANT'}</div><div style={{fontSize:u*.044,lineHeight:1.2,fontWeight:800}}>{text}</div></div>)}
	</div>;
	if(g.kind==='paper') return <div style={{...base,width:'auto',maxWidth:W*.85,padding:`${u*.024}px ${u*.04}px`,background:'#fff9ec',color:'#151515',boxShadow:'5px 8px 0 #0003',borderBottom:`8px solid ${g.color}`,fontWeight:900,fontSize:u*.09}}>
		<div style={{position:'absolute',width:'30%',height:25,left:'35%',top:-15,background:'#d8bc80bb',transform:'rotate(4deg)'}}/>{g.text} <span style={{color:g.color}}>↗</span>
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
