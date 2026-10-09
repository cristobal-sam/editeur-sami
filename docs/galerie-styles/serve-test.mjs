// Copie indépendante pour tester les clics de la galerie ; aucune entrée réelle ni livraison réelle.
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const DIR=path.dirname(fileURLToPath(import.meta.url)),ROOT=path.resolve(DIR,'../..');
const box=fs.mkdtempSync(path.join(ROOT,'runtime/cache/tmp/galerie-interface-'));
const mkdir=p=>fs.mkdirSync(path.join(box,p),{recursive:true});
for(const p of ['app/server.mjs','app/ui','app/dist','styles','engine/editeur','engine/blender_produit.py','remotion/src','remotion/render.mjs','remotion/segments.mjs','remotion/package.json','remotion/tsconfig.json']){
 mkdir(path.dirname(p));fs.cpSync(path.join(ROOT,p),path.join(box,p),{recursive:true});
}
for(const p of ['assets','models','tools/ffmpeg','runtime/venv','remotion/node_modules']){
 mkdir(path.dirname(p));fs.symlinkSync(path.join(ROOT,p),path.join(box,p),'junction');
}
mkdir('runtime/cache/tmp');mkdir('projects/test/reels');mkdir('media/entree');mkdir('livraisons/test');
const reel=JSON.parse(fs.readFileSync(path.join(DIR,'tests/hormozi-essai.json'),'utf8'));
reel.project='test';reel.id='script';reel.variant=null;reel.title='Vérification des styles (copie)';
reel.delivery=path.join(box,'livraisons/test');
for(const s of Object.values(reel.sources)){
 delete s.voice;delete s.roomtone;
 if(s.proxy.startsWith('projects/')){mkdir(path.dirname(s.proxy));fs.copyFileSync(path.join(ROOT,s.proxy),path.join(box,s.proxy));}
}
fs.writeFileSync(path.join(box,'projects/test/reels/script.json'),JSON.stringify(reel));
fs.writeFileSync(path.join(box,'projects/test/project.json'),JSON.stringify({name:'test',label:reel.title,timeline:[],variants:[],sources:reel.sources,script:{blocks:[]}}));
fs.writeFileSync(path.join(box,'projects/_revision.json'),JSON.stringify({lots:{},items:[{id:'abcdef123456',name:reel.title,title:reel.title,status:'pret',project:'test',rid:'script',style:reel.template,lot:'test',type:'pub',typeLabel:'Publicité',updated:Date.now()}]}));
fs.writeFileSync(path.join(DIR,'tests/interface.json'),JSON.stringify({box,port:18790}));
console.log('COPIE='+box);
const child=spawn(process.execPath,[path.join(box,'app/server.mjs')],{cwd:box,env:{...process.env,EDITEUR_ROOT:box,EDITEUR_PORT:'18790',EDITEUR_LLM:'0'},windowsHide:true,stdio:'inherit'});
console.log('PID_SERVEUR='+child.pid);
process.on('SIGINT',()=>child.kill());process.on('SIGTERM',()=>child.kill());child.on('exit',c=>process.exit(c||0));
