// Copie isolee pour l'essai navigateur et les exports courts du vrai moteur.
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
const ROOT = 'D:/Tools/editeur_sami';
const box = fs.mkdtempSync(`${ROOT}/runtime/cache/tmp/interface-verification-`);
const mkdir = (p) => fs.mkdirSync(path.join(box,p),{recursive:true});
const copy = (p) => {mkdir(path.dirname(p)); fs.cpSync(path.join(ROOT,p),path.join(box,p),{recursive:true});};
for (const p of ['app/server.mjs','app/ui','app/dist','styles','engine/editeur','remotion/src','remotion/render.mjs','remotion/segments.mjs','remotion/package.json','remotion/tsconfig.json']) copy(p);
for (const p of ['assets','tools/ffmpeg','runtime/venv','remotion/node_modules']) {
  mkdir(path.dirname(p));
  fs.symlinkSync(path.join(ROOT,p),path.join(box,p),'junction');
}
mkdir('runtime/cache/tmp'); mkdir('projects/test/reels'); mkdir('media/entree'); mkdir('livraisons/test');
const r = JSON.parse(fs.readFileSync(`${ROOT}/projects/video1/reels/v1.json`,'utf8'));
const clip = r.clips[0];
clip.out = clip.in + 1;
clip.words = clip.words.filter(w=>w.start>=clip.in && w.end<=clip.out);
clip.audioLead=0; clip.audioTail=0; clip.tighten=false; clip.angle=null;
r.clips=[clip]; r.id='script'; r.project='test'; r.title='Verification courte';
r.delivery=path.join(box,'livraisons/test');
r.graphics=[]; r.broll=[]; r.intro.enabled=false; r.brand=null; r.sfx.extra=[];
r.music.enabled=false; r.sfx.enabled=false;
r.banner.enabled=false;
const source=r.sources[clip.source];
r.sources={[clip.source]:source};
const proxy=source.proxy;
mkdir(path.dirname(proxy)); fs.copyFileSync(path.join(ROOT,proxy),path.join(box,proxy));
source.roomtone=null; source.cleanAudio=null;
fs.writeFileSync(path.join(box,'projects/test/reels/script.json'),JSON.stringify(r));
fs.writeFileSync(path.join(box,'projects/test/project.json'),JSON.stringify({name:'test',label:'Verification courte',timeline:[],variants:[],sources:r.sources,script:{blocks:[]}}));
fs.writeFileSync(path.join(box,'projects/_revision.json'),JSON.stringify({lots:{},items:[{id:'abcdef123456',name:r.title,title:r.title,status:'pret',project:'test',rid:'script',style:r.template,lot:'test',type:'pub',typeLabel:'Publicite',updated:Date.now()}]}));
console.log(`FIXTURE=${box}`);
const child=spawn(process.execPath,[path.join(box,'app/server.mjs')],{cwd:box,env:{...process.env,EDITEUR_ROOT:box,EDITEUR_PORT:'18790',EDITEUR_LLM:'0',EDITEUR_CONCURRENCE:'2',TEMP:path.join(box,'runtime/cache/tmp'),TMP:path.join(box,'runtime/cache/tmp')},stdio:'inherit',windowsHide:true});
process.on('SIGINT',()=>child.kill());
process.on('SIGTERM',()=>child.kill());
child.on('exit',code=>process.exit(code||0));
