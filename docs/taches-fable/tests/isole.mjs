// Tests reproductibles sur un bac NEUF, jamais sur les donnees de l'utilisateur.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn,spawnSync} from 'node:child_process';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const old=path.join(ROOT,'runtime/cache/tmp/interface-fable-85584');
const mode=process.argv[2];
if(!['corbeille','http','blocage'].includes(mode)) throw Error('Mode invalide');
try {await fetch('http://127.0.0.1:18793/api/revision'); throw Error('Port de test deja occupe');}
catch(e){if(e.message==='Port de test deja occupe')throw e;}
const base=fs.mkdtempSync(path.join(ROOT,`runtime/cache/tmp/fable2-${mode}-`));
const box=path.join(base,'rendu');
console.log('COPIE='+base);
const cp=(src,dest)=>{fs.mkdirSync(path.dirname(dest),{recursive:true});fs.cpSync(src,dest,{recursive:true});};
for(const f of ['setup-rendu.mjs','setup-serveur.mjs']){
  cp(path.join(old,f),path.join(base,f));
  const r=spawnSync(process.execPath,[path.join(base,f)],{cwd:base,stdio:'inherit',windowsHide:true});
  if(r.status!==0)throw Error(f);
}
cp(path.join(old,'rendu/engine'),path.join(box,'engine'));
// Les sources utilisees par le vrai export court doivent toutes etre presentes.
const real=JSON.parse(fs.readFileSync(path.join(box,'reel-video1video1.json'),'utf8'));
const used=new Set([real.clips[0].source,real.clips[0].angle].filter(Boolean));
if(mode==='http') for(const id of used)for(const k of ['path','voice','proxy','roomtone']){
  const rel=real.sources[id]?.[k];
  if(!rel)continue;
  const local=path.isAbsolute(rel)?path.relative(ROOT,rel):rel;
  if(local.startsWith('..')||path.isAbsolute(local))throw Error('Source hors du projet');
  const dest=path.join(box,path.isAbsolute(rel)?`projects/_cache/originaux/${id}-${path.basename(rel)}`:local);
  if(!fs.existsSync(dest))cp(path.isAbsolute(rel)?rel:path.join(ROOT,rel),dest);
  if(path.isAbsolute(rel))for(const name of ['faux-a','faux-d1','faux-d2','court','faux-f']){
    const file=path.join(box,'projects',name,'reels/script.json');
    const r=JSON.parse(fs.readFileSync(file,'utf8'));
    r.sources[id][k]=dest;
    fs.writeFileSync(file,JSON.stringify(r));
  }
}
const test=`test-${mode}.mjs`;
cp(path.join(mode==='corbeille'?path.join(ROOT,'docs/taches-fable/tests'):old,test),path.join(base,test));
if(mode!=='http')cp(path.join(mode==='corbeille'?path.join(ROOT,'docs/taches-fable/tests'):old,mode==='corbeille'?'render-gel.mjs':'render-stub.mjs'),path.join(box,'remotion/render.mjs'));
const env={...process.env,EDITEUR_ROOT:box,EDITEUR_PORT:'18793',TEST_AUTO_S:mode==='http'?'90':'3',TEST_AUTRE_S:mode==='blocage'?'10':'0',
  EDITEUR_BLOCAGE_AUTRE_S:'6',EDITEUR_BLOCAGE_PAR_MIN_S:'2',EDITEUR_GRACE_STOP_S:'4',EDITEUR_BLOCAGE_S:'10',EDITEUR_BLOCAGE_MARGE_S:'5',
  TEMP:path.join(box,'runtime/cache/tmp'),TMP:path.join(box,'runtime/cache/tmp')};
// Vrai export : delais normaux ; les seuils courts ne servent qu'aux rendus factices.
if(mode==='http')for(const k of Object.keys(env))if(k.startsWith('EDITEUR_BLOCAGE_'))delete env[k];
const log=fs.openSync(path.join(base,'serveur.log'),'w');
const server=spawn(process.execPath,['app/server.mjs'],{cwd:box,env,stdio:['ignore',log,log],windowsHide:true});
fs.writeFileSync(path.join(base,'serveur.pid'),String(server.pid));
console.log('SERVEUR_TEST_PID='+server.pid);
try{
  let ready=false;
  for(let i=0;i<100;i++){try{await fetch('http://127.0.0.1:18793/api/revision');ready=true;break;}catch{}await new Promise(r=>setTimeout(r,200));}
  if(!ready)throw Error('Serveur de copie indisponible');
  const child=spawn(process.execPath,[test],{cwd:base,env,windowsHide:true});
  let output='';
  for(const stream of [child.stdout,child.stderr])stream.on('data',b=>{output+=b;process.stdout.write(b);});
  const code=await new Promise(r=>child.on('exit',r));
  fs.writeFileSync(path.join(base,'resultat.txt'),output);
  if(code!==0||!output.includes('TOUS LES TESTS OK')||output.includes('ECHEC'))process.exitCode=1;
}finally{
  // Laisser le faux moteur finir avant d'arreter son serveur (aucun orphelin).
  for(let i=0;i<110;i++){
    const state=await fetch('http://127.0.0.1:18793/api/revision').then(r=>r.json());
    if(!state.busy)break;
    await new Promise(r=>setTimeout(r,1000));
  }
  // Uniquement le PID que CE script vient de creer, et ses enfants de test.
  const stopped=spawnSync('taskkill',['/PID',String(server.pid),'/T','/F'],{windowsHide:true,encoding:'utf8'});
  console.log('ARRET_ARBRE='+stopped.status+' '+stopped.stdout.trim()+' '+stopped.stderr.trim());
  if(stopped.status!==0)server.kill();
  await new Promise(r=>server.exitCode!==null?r():server.once('exit',r));
  console.log('SERVEUR_COPIE_ARRETE');
  fs.closeSync(log);
}
