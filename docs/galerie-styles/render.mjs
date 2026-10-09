// Génère les aperçus avec les composants réels ; exports courts séquentiels, sans serveur de l'outil.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const DIR=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(DIR,'../..');
const require=createRequire(path.join(ROOT,'remotion/package.json'));
const {bundle}=require('@remotion/bundler');
const {renderStill,selectComposition}=require('@remotion/renderer');
const browserExecutable=path.join(ROOT,'remotion/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe');
if(!fs.existsSync(browserExecutable))throw new Error('Navigateur local absent : aucun téléchargement automatique autorisé.');
const ids=['hormozi','documentaire','luxe-minimal','retro-vhs','comparatif','infographie','tech-application','collage','editorial-cinetique','produit-3d'];
const only=process.argv.find(a=>ids.includes(a));
const templates=ids.map(id=>JSON.parse(fs.readFileSync(path.join(ROOT,'styles/montage',id+'.json'),'utf8')));
const server=http.createServer((req,res)=>{
 const file=path.resolve(ROOT,'.'+decodeURIComponent(new URL(req.url,'http://local').pathname));
 if(!['assets','projects','docs/galerie-styles'].some(p=>file.startsWith(path.resolve(ROOT,p)+path.sep))||!fs.existsSync(file)){res.writeHead(404);res.end();return;}
 const size=fs.statSync(file).size;
 const mime={'.png':'image/png','.mp4':'video/mp4','.webm':'video/webm','.ttf':'font/ttf','.ogg':'audio/ogg','.wav':'audio/wav'}[path.extname(file)]||'application/octet-stream';
 const range=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range||'');
 const headers={'content-type':mime,'access-control-allow-origin':'*','accept-ranges':'bytes'};
 if(range){const a=+range[1],b=Math.min(size-1,range[2]?+range[2]:size-1);res.writeHead(206,{...headers,'content-range':`bytes ${a}-${b}/${size}`,'content-length':b-a+1});fs.createReadStream(file,{start:a,end:b}).pipe(res);}
 else {res.writeHead(200,{...headers,'content-length':size});fs.createReadStream(file).pipe(res);}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
try{
 if(!process.argv.includes('--videos')){
  const serveUrl=await bundle({entryPoint:path.join(ROOT,'remotion/galerie-entry.tsx'),outDir:fs.mkdtempSync(path.join(ROOT,'runtime/cache/tmp/galerie-bundle-'))});
  for(const tpl of templates.filter(t=>!only||t.id===only)){
   const reel=JSON.parse(fs.readFileSync(path.join(DIR,'tests',tpl.id+'-apercu.json'),'utf8'));
   const inputProps={reel,mediaBase:origin,assetBase:origin+'/assets',audio:'none'};
   const composition=await selectComposition({serveUrl,id:'Reel',inputProps,browserExecutable});
   const frame={'comparatif':120,'infographie':100,'editorial-cinetique':100,'tech-application':40,'collage':70,'produit-3d':50,'hormozi':85}[tpl.id]??85;
   const filename=path.basename(tpl.preview),output=path.join(DIR,'images',filename);
   await renderStill({serveUrl,composition,inputProps,frame,output,imageFormat:'png',browserExecutable,chromiumOptions:{gl:'angle'}});
   fs.copyFileSync(output,path.join(ROOT,'assets',tpl.preview));
   console.log('APERÇU',tpl.id);
  }
  if(templates.every(t=>fs.existsSync(path.join(ROOT,'assets',t.preview)))){
   const ordered=[...templates].sort((a,b)=>a.preview.localeCompare(b.preview));
   const inputProps={items:ordered.map(t=>({...t,name:t.name.replace(' / cinéma','').replace(' / écran partagé','').replace(' / papier découpé',''),description:{'editorial-cinetique':'Typographie rouge · Personne détourée','hormozi':'Mots forts · Accent jaune','tech-application':'Notifications · Interface illustrée','infographie':'Chiffres dits · Motion design','documentaire':'Cadre cinéma · Lumière chaude','collage':'Papier découpé · Contour blanc','luxe-minimal':'Empattements · Or discret','retro-vhs':'Cassette · Grain et balayage','comparatif':'Problème / solution · Deux panneaux','produit-3d':'Carte démo · Studio Blender'}[t.id]})),origin};
   const composition=await selectComposition({serveUrl,id:'Planche',inputProps,browserExecutable});
   await renderStill({serveUrl,composition,inputProps,frame:0,output:path.join(DIR,'planche.png'),imageFormat:'png',browserExecutable});
   console.log('PLANCHE PRÊTE');
  }
 }
 if(process.argv.includes('--videos')){
  for(const tpl of templates.filter(t=>!only||t.id===only)){
   const reel=JSON.parse(fs.readFileSync(path.join(DIR,'tests',tpl.id+'-essai.json'),'utf8'));
   const out=path.join(DIR,'tests',tpl.id+'.mp4');
   const job=path.join(DIR,'tests',tpl.id+'-export.json');
   fs.writeFileSync(job,JSON.stringify({reel,out}));
   console.log('EXPORT',tpl.id);
   const r=spawnSync(process.execPath,[path.join(ROOT,'remotion/render.mjs'),job],{cwd:path.join(ROOT,'remotion'),encoding:'utf8',env:{...process.env,EDITEUR_CONCURRENCE:'2'},maxBuffer:32*1024*1024,windowsHide:true});
   fs.writeFileSync(path.join(DIR,'tests',tpl.id+'-export.log'),r.stdout+'\n'+r.stderr);
   if(r.status!==0||!fs.existsSync(out))throw new Error(`${tpl.id}: ${r.stdout.slice(-2000)} ${r.stderr.slice(-1000)}`);
   console.log('VÉRIFIÉ',tpl.id,fs.statSync(out).size,'octets');
  }
 }
}finally{server.close();}
