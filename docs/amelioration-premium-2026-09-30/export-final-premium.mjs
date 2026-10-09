// Export final non destructif de Vidéo 1 : garde toute ancienne livraison et choisit un nouveau nom.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const reel=JSON.parse(fs.readFileSync(path.join(root,'projects/script1/reels/script.json'),'utf8'));
const delivery=reel.delivery&&path.isAbsolute(reel.delivery)?reel.delivery:path.join(root,'livraisons','Premium');
fs.mkdirSync(delivery,{recursive:true});
let out=path.join(delivery,'Vidéo 1 - Tech 3D cinématique - FINAL.mp4');
for(let n=2;fs.existsSync(out);n++)out=path.join(delivery,`Vidéo 1 - Tech 3D cinématique - v${n} - FINAL.mp4`);
const box=fs.mkdtempSync(path.join(root,'runtime/cache/tmp/export-premium-'));
const job=path.join(box,'job.json');
fs.writeFileSync(job,JSON.stringify({reel,out}));
console.log(`SORTIE=${out}`);
const run=spawnSync(process.execPath,[path.join(root,'remotion/render.mjs'),job],{cwd:path.join(root,'remotion'),env:process.env,stdio:'inherit',windowsHide:true});
if(run.status!==0||!fs.existsSync(out))process.exit(run.status||1);
const result=path.join(root,'docs/amelioration-premium-2026-09-30/resultat');
fs.mkdirSync(result,{recursive:true});
const sheet=path.join(result,'planche-finale.jpg');
const ffmpeg=path.join(root,'tools/ffmpeg/bin/ffmpeg.exe');
const shot=spawnSync(ffmpeg,['-hide_banner','-loglevel','error','-i',out,'-vf','fps=1/5,scale=360:-1,tile=4x4:padding=8:margin=8:color=0x111318','-frames:v','1',sheet],{stdio:'inherit',windowsHide:true});
if(shot.status!==0||!fs.existsSync(sheet))process.exit(shot.status||1);
console.log(`FINAL=${out}`);
console.log(`PLANCHE=${sheet}`);
