// Lecture seule contre la copie isolee de l'editeur deja lancee.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import readline from 'node:readline';
const child=spawn(process.execPath,['D:/Tools/editeur_sami/plugins/editeur-sami/mcp/serveur.mjs'],{env:{...process.env,EDITEUR_PORT:'18790',EDITEUR_MCP_SANS_DEMARRAGE:'1'},stdio:['pipe','pipe','pipe'],windowsHide:true});
let id=0;const pending=new Map();
readline.createInterface({input:child.stdout}).on('line',line=>{const r=JSON.parse(line);pending.get(r.id)?.(r);pending.delete(r.id)});
const req=(method,params)=>new Promise((resolve,reject)=>{
  const n=++id,t=setTimeout(()=>reject(Error('Delai MCP')),15000);
  pending.set(n,r=>{clearTimeout(t);resolve(r)});
  child.stdin.write(JSON.stringify({jsonrpc:'2.0',id:n,method,params})+'\n');
});
try {
  await req('initialize',{protocolVersion:'2025-06-18',capabilities:{},clientInfo:{name:'verification',version:'1'}});
  for(const name of ['etat','styles','erreurs']){
    const r=await req('tools/call',{name,arguments:name==='etat'?{filtre:'tout'}:{}});
    assert.ok(!r.error && !r.result.isError,name);
    console.log(`Lecture ${name} : OK`);
  }
} finally {child.stdin.end()}
