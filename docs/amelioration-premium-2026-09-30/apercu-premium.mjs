// Rendu court de contrôle du style Tech 3D. N'écrit jamais dans projects, media ou livraisons.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const start=Number(process.argv[2]??24);
const end=Number(process.argv[3]??39);
if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start||end-start>20)throw new Error('Plage attendue : 0 à 20 secondes.');
const reel=JSON.parse(fs.readFileSync(path.join(root,'projects/script1/reels/script.json'),'utf8'));
const box=fs.mkdtempSync(path.join(root,'runtime/cache/tmp/apercu-premium-'));
const job=path.join(box,'job.json');
const out=path.join(box,`premium-${start}-${end}.mp4`);
fs.writeFileSync(job,JSON.stringify({reel,out,frameRange:[Math.round(start*reel.fps),Math.round(end*reel.fps)-1]}));
console.log(`DOSSIER=${box}`);
const run=spawnSync(process.execPath,[path.join(root,'remotion/render.mjs'),job],{cwd:path.join(root,'remotion'),env:process.env,stdio:'inherit',windowsHide:true});
if(run.status!==0||!fs.existsSync(out))process.exit(run.status||1);
const ffmpeg=path.join(root,'tools/ffmpeg/bin/ffmpeg.exe');
const sheet=path.join(box,'planche.jpg');
const shot=spawnSync(ffmpeg,['-hide_banner','-loglevel','error','-i',out,'-vf','fps=1,scale=360:-1,tile=4x4:padding=8:margin=8:color=0x111318','-frames:v','1',sheet],{stdio:'inherit',windowsHide:true});
if(shot.status!==0||!fs.existsSync(sheet))process.exit(shot.status||1);
console.log(`VIDEO=${out}`);
console.log(`PLANCHE=${sheet}`);
