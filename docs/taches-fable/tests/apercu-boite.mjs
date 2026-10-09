// Export de preuve de 2 secondes ; copie en memoire, aucune ecriture dans projects/media/livraisons.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const box=fs.mkdtempSync(path.join(root,'runtime/cache/tmp/fable2-images-'));
const reel=JSON.parse(fs.readFileSync(path.join(root,'projects/script1/reels/script.json'),'utf8'));
if(reel.template!=='podcast-clip'||reel.style.preset!=='boite')throw Error('La fixture doit etre Clip podcast / boite');
// Fixture ciblee : les deux mots de la notion « trois heures » sont marques, les voisins restent simples.
for(const c of reel.clips)for(const w of c.words){
  if(c.id==='c2'&&w.start>=18&&w.start<=19.5)w.hl=['trois','heures'].includes(w.w.replace(/[.,!?…]/g,'').toLowerCase());
}
const job=path.join(box,'job.json'),out=path.join(box,'boite-2s.mp4');
fs.writeFileSync(job,JSON.stringify({reel,out,frameRange:[780,839]}));
console.log('COPIE='+box);
const child=spawn(process.execPath,[path.join(root,'remotion/render.mjs'),job],{cwd:path.join(root,'remotion'),env:process.env,windowsHide:true});
let log='';
for(const stream of [child.stdout,child.stderr])stream.on('data',b=>{log+=b;process.stdout.write(b);});
const code=await new Promise(r=>child.on('exit',r));
fs.writeFileSync(path.join(box,'rendu.log'),log);
if(code!==0||!fs.existsSync(out))process.exitCode=1;
