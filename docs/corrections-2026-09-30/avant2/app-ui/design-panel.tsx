import React, {useState} from 'react';
import type {ReelDoc, StyleScene} from '../../remotion/src/types';
import {api, useJob} from './api';
type Props={reel:ReelDoc;update:(fn:(r:ReelDoc)=>ReelDoc)=>void;current:string};
export const DesignPanel:React.FC<Props>=({reel,update,current})=>{
	const [err,setErr]=useState('');
	const [job,setJob]=useJob(j=>update(r=>({...r,design:{...r.design,productVideo:j.result.file},styleScenes:j.result.reel.styleScenes})));
	const [cutJob,setCutJob]=useJob(j=>update(r=>({...r,cutouts:j.result.cutouts})));
	const design=reel.design;
	if(!design?.mode)return null;
	const set=(p:Partial<NonNullable<ReelDoc['design']>>)=>update(r=>({...r,design:{...r.design,...p}}));
	const scene=(id:string,p:Partial<StyleScene>)=>update(r=>({...r,styleScenes:(r.styleScenes??[]).map(s=>s.id===id?{...s,...p}:s)}));
	const pick=async(f:File|undefined,model:boolean)=>{
		if(!f)return;
		try{
			const data=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(new Error('Fichier illisible.'));reader.readAsDataURL(f);});
			const result=await api(model?'/api/product-assets':'/api/images','POST',{name:f.name,data});
			set(model?{productModel:result.path,productImage:undefined,productVideo:undefined}:{productImage:result.path,productModel:undefined,productVideo:undefined});
		}catch(e){setErr((e as Error).message);}
	};
	return <div className="card design-panel"><h3>Habillage du style</h3>
		<label className="inline"><input type="checkbox" checked={design.enabled!==false} onChange={e=>set({enabled:e.target.checked})}/> Afficher l’habillage</label>
		{['editorial','collage'].includes(design.mode)?<><p className="muted">Après avoir changé de prise ou élargi une coupe, actualise le détourage.</p><button disabled={cutJob?.status==='running'} onClick={async()=>{try{await api(`/api/reels/${current}`,'PUT',{clips:reel.clips});setCutJob(await api(`/api/reels/${current}/detourage`,'POST',{}));}catch(e){setErr((e as Error).message);}}}>{cutJob?.status==='running'?'Détourage en cours…':'Actualiser le détourage'}</button>{cutJob?.status==='failed'?<p className="err">{cutJob.error}</p>:null}</>:null}
		<div className="row"><label>Accent</label><input type="color" value={design.accent||reel.style.highlight} onChange={e=>{const color=e.target.value;update(r=>({...r,design:{...r.design,accent:color},styleScenes:(r.styleScenes??[]).map(s=>s.color===r.design?.accent?{...s,color}:s)}));}}/></div>
		{(reel.broll?.length||reel.graphics?.some(g=>!g.suggested))?<label className="inline"><input type="checkbox" checked={design.suppressExtras===false} onChange={e=>set({suppressExtras:!e.target.checked})}/> Afficher aussi mes anciens plans de coupe et graphismes (conservés)</label>:null}
		{design.mode==='documentaire'?<div className="row"><label>Titre discret</label><input className="grow" value={design.title??''} placeholder={reel.title} onChange={e=>set({title:e.target.value})}/></div>:null}
		{design.mode==='vhs'?<div className="row"><label>Texte cassette</label><input className="grow" value={design.date??'RYUCALLS · REC'} onChange={e=>set({date:e.target.value})}/></div>:null}
		{design.mode==='produit'?<>
			<p className="muted">Une photo devient une carte en relief. Un GLB utilise la forme réelle de ton produit. Sans fichier : carte de démonstration RyuCalls.</p>
			<div className="row"><label className="button-like small">Photo du produit<input type="file" hidden accept="image/png,image/jpeg,image/webp" onChange={e=>pick(e.target.files?.[0],false)}/></label>
			<label className="button-like small">Modèle GLB<input type="file" hidden accept=".glb" onChange={e=>pick(e.target.files?.[0],true)}/></label></div>
			<p className="muted">{design.productModel?'Modèle 3D choisi':design.productImage?'Photo choisie':'Carte démo'}{design.productVideo?' · Animation prête':''}</p>
			<button disabled={job?.status==='running'} onClick={async()=>{try{await api(`/api/reels/${current}`,'PUT',{design});setJob(await api(`/api/reels/${current}/produit`,'POST',{}));}catch(e){setErr((e as Error).message);}}}>{job?.status==='running'?'Blender prépare l’animation…':'Créer l’animation 3D'}</button>
			{job?.status==='failed'?<p className="err">{job.error}</p>:null}
		</>:null}
		{(reel.styleScenes??[]).map(s=><details key={s.id} className="design-scene"><summary>{s.text||'Produit'} · {{keyword:'Mot clé',paper:'Papier',notification:'Notification',comparison:'Comparatif',metric:'Chiffre',product:'Produit'}[s.kind]}</summary>
			<label className="inline"><input type="checkbox" checked={!s.hidden} onChange={e=>scene(s.id,{hidden:!e.target.checked})}/> Afficher cet élément</label>
			<div className="row"><label>Texte</label><input className="grow" value={s.text} onChange={e=>scene(s.id,{text:e.target.value})}/></div>
			<div className="row"><label>Deuxième texte</label><input className="grow" value={s.secondary||''} onChange={e=>scene(s.id,{secondary:e.target.value})}/></div>
			{(['x','y'] as const).map(k=><div className="row" key={k}><label>{k==='x'?'Position horizontale':'Hauteur'}</label><input type="range" min={.1} max={.9} step={.01} value={s[k]} onChange={e=>scene(s.id,{[k]:Number(e.target.value)})}/></div>)}
			<div className="row"><label>Taille</label><input type="range" min={.4} max={1.5} step={.05} value={s.scale} onChange={e=>scene(s.id,{scale:Number(e.target.value)})}/></div>
			<div className="row"><label>Rotation</label><input type="range" min={-20} max={20} value={s.rotation} onChange={e=>scene(s.id,{rotation:Number(e.target.value)})}/></div>
			<div className="row"><label>Durée (s)</label><input type="number" min={.3} max={8} step={.1} value={s.duration} onChange={e=>scene(s.id,{duration:Number(e.target.value)})}/><input type="color" value={s.color} onChange={e=>scene(s.id,{color:e.target.value})}/></div>
		</details>)}
		{err?<p className="err">{err}</p>:null}
	</div>;
};
