// Vérification non destructive du paquet portable et des nouveaux outils MCP v2.
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import {spawn} from 'node:child_process';
const ROOT='D:\\Tools\\editeur_sami';
const PLUGIN=path.join(ROOT,'plugins','editeur-sami');
for(const f of ['plugin.json','mcp.json','.codex-plugin/plugin.json','.claude-plugin/plugin.json']) JSON.parse(fs.readFileSync(path.join(PLUGIN,f),'utf8'));
const manifest=JSON.parse(fs.readFileSync(path.join(PLUGIN,'plugin.json'),'utf8'));
if(manifest.version!=='2.1.0'||manifest.extensions['com.openai'].interface.shortDescription.length>30)throw Error('Manifeste invalide');
for(const p of ['assets/logo.svg','skills/controle/SKILL.md','skills/corbeille/SKILL.md','skills/declinaison/SKILL.md','skills/outils-locaux/SKILL.md'])if(!fs.existsSync(path.join(PLUGIN,p)))throw Error(`Manque ${p}`);
const child=spawn(process.execPath,[path.join(PLUGIN,'mcp','serveur.mjs')],{env:{...process.env,EDITEUR_MCP_SANS_DEMARRAGE:'1'},stdio:['pipe','pipe','pipe'],windowsHide:true});
const pending=new Map();let seq=0;
child.stderr.resume();
readline.createInterface({input:child.stdout}).on('line',line=>{const m=JSON.parse(line);if(m.id!==undefined){pending.get(m.id)?.(m);pending.delete(m.id);}});
const call=(method,params)=>new Promise(resolve=>{const id=++seq;pending.set(id,resolve);child.stdin.write(JSON.stringify({jsonrpc:'2.0',id,method,params})+'\n');});
const text=r=>r.result?.content?.map(x=>x.text).join('\n')||'';
const init=await call('initialize',{protocolVersion:'2025-06-18',capabilities:{},clientInfo:{name:'v2-test',version:'1'}});
if(init.result.serverInfo.version!=='2.1.0')throw Error('Version MCP incorrecte');
const listed=(await call('tools/list',{})).result.tools;
const required=['etat','monter','inspecter_montage','versions','restaurer_version','retour_style','declinaison','proposer','rechercher_rushs','outils_locaux','creer_titre_3d','animer_produit_3d','actualiser_detourage','generer_musique','ouvrir_resolve','exporter_montage_pro','annuler_tache','corbeille','mettre_corbeille','restaurer_corbeille'];
for(const name of required)if(!listed.some(t=>t.name===name))throw Error(`Outil manquant ${name}`);
if(!listed.find(t=>t.name==='mettre_corbeille').annotations.destructiveHint)throw Error('Garde-fou destructif absent');
const etat=await call('tools/call',{name:'etat',arguments:{filtre:'tout',limite:5}});
if(!text(etat).includes('Révision'))throw Error(`etat: ${text(etat)}`);
const videoId=text(etat).match(/\[([a-f0-9]{12})\]/i)?.[1];
if(videoId){
  for(const [name,needle] of [['inspecter_montage','Montage'],['versions','Version']]){
    const r=await call('tools/call',{name,arguments:{video:videoId}});
    if(!text(r).toLowerCase().includes(needle.toLowerCase()))throw Error(`${name}: ${text(r)}`);
  }
}
for(const [name,args,needle] of [
	['outils_locaux',{},'Outils locaux'],
  ['corbeille',{},'Corbeille'],
  ['mettre_corbeille',{video:'video-introuvable'},'introuvable'],
  ['restaurer_corbeille',{dossier:'../refuse'},'invalide'],
  ['annuler_tache',{tache:'pas-un-uuid'},'invalide'],
  ['declinaison',{video:'video-introuvable',duree:30},'introuvable'],
  ['proposer',{video:'video-introuvable',type:'ia'},'introuvable'],
	['creer_titre_3d',{video:'video-introuvable',texte:'Essai'},'introuvable'],
	['animer_produit_3d',{video:'video-introuvable'},'introuvable'],
	['actualiser_detourage',{video:'video-introuvable'},'introuvable'],
	['generer_musique',{video:'video-introuvable',ambiance:'luxe'},'introuvable'],
	['ouvrir_resolve',{confirmer:false},'confirme'],
]){
  const r=await call('tools/call',{name,arguments:args});
  if(!text(r).toLowerCase().includes(needle.toLowerCase()))throw Error(`${name}: ${text(r)}`);
}
child.stdin.end();
await new Promise(resolve=>child.on('exit',resolve));
console.log(`Plugin v2.1 OK : ${listed.length} outils, manifestes portables, appels en lecture et refus sûrs.`);
