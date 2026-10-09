import React from 'react';
import {registerRoot, Composition, AbsoluteFill, Img} from 'remotion';
import {Root} from './src/Root';
type Item={id:string;name:string;description:string;preview:string};
const Sheet:React.FC<{items:Item[];origin:string}>=({items,origin})=><AbsoluteFill style={{background:'#0e1015',color:'#f4f0e9',padding:44,fontFamily:'Arial,sans-serif'}}>
	<div style={{fontSize:38,fontWeight:750,letterSpacing:-1}}>RyuCalls <span style={{color:'#9198a6',fontWeight:400}}> / Galerie de montage</span></div>
	<div style={{fontSize:17,color:'#9299a6',marginTop:10,marginBottom:30}}>Dix identités · Une même personne · Aperçus issus du moteur vidéo</div>
	<div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:'28px 20px'}}>{items.map((item,i)=><div key={item.id}>
		<Img src={`${origin}/assets/${item.preview}`} style={{width:'100%',height:400,objectFit:'cover',borderRadius:12,border:'1px solid #ffffff18'}}/>
		<div style={{fontSize:18,fontWeight:700,marginTop:12}}><span style={{color:'#e76a4b',fontSize:13,marginRight:9}}>{String(i+1).padStart(2,'0')}</span>{item.name}</div>
		<div style={{fontSize:13,color:'#949ba7',marginTop:7,lineHeight:1.35}}>{item.description}</div>
	</div>)}</div>
	<div style={{position:'absolute',bottom:26,left:44,right:44,color:'#717987',fontSize:13}}>ÉDITEUR SAMI · Rendu local · Chaque élément reste modifiable</div>
</AbsoluteFill>;
registerRoot(()=> <><Root/><Composition id="Planche" component={Sheet} width={1360} height={1170} fps={30} durationInFrames={1} defaultProps={{items:[],origin:''}}/></>);
