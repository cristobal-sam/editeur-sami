// Protocole MCP reel, API factice : aucun montage ni export ne peut demarrer.
import assert from 'node:assert/strict';
import http from 'node:http';
import {spawn} from 'node:child_process';
import readline from 'node:readline';
const item={id:'abcdef123456',name:'Test',title:'Test',status:'pret',project:'test',rid:'script',lot:'test',exports:[]};
const writes=[];
const server=http.createServer(async(req,res)=>{
  let raw=''; for await(const c of req) raw+=c;
  const body=raw?JSON.parse(raw):{};
  res.setHeader('content-type','application/json');
  const out=(x)=>res.end(JSON.stringify(x));
  if(req.method!=='GET'){
    writes.push({url:req.url,body});
    assert.match(req.headers.origin,/^http:\/\/127\.0\.0\.1:/);
    if(req.url===`/api/revision/${item.id}/prendre`){
      item.exports=body.formats.map((format,k)=>({format,job:`00000000-0000-0000-0000-00000000000${k}`,status:'queued',out:`test-${k}.mp4`}));
      return out({exports:item.exports});
    }
    res.statusCode=400;return out({error:'Action inattendue dans le test'});
  }
  if(req.url==='/api/revision')return out({items:[item],entree:'test',busy:false});
  if(req.url==='/api/styles')return out({montage:[{id:'reel-impact',name:'Impact'}]});
  if(req.url==='/api/types')return out({pub:{label:'Pub',style:'reel-impact'}});
  if(['/api/clients','/api/queue','/api/reels'].includes(req.url))return out([]);
  res.statusCode=404;out({error:'Route absente'});
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const port=server.address().port;
const child=spawn(process.execPath,['D:/Tools/editeur_sami/plugins/editeur-sami/mcp/serveur.mjs'],{env:{...process.env,EDITEUR_PORT:String(port),EDITEUR_MCP_SANS_DEMARRAGE:'1'},stdio:['pipe','pipe','pipe'],windowsHide:true});
let id=0;const pending=new Map();
readline.createInterface({input:child.stdout}).on('line',line=>{const r=JSON.parse(line);pending.get(r.id)?.(r);pending.delete(r.id)});
const req=(method,params)=>new Promise((resolve,reject)=>{
  const n=++id;const timer=setTimeout(()=>reject(new Error(`Delai MCP ${method}`)),15000);
  pending.set(n,r=>{clearTimeout(timer);resolve(r)});
  child.stdin.write(JSON.stringify({jsonrpc:'2.0',id:n,method,params})+'\n');
});
const call=async(name,args={})=>(await req('tools/call',{name,arguments:args})).result;
try{
  assert.ok((await req('initialize',{protocolVersion:'2025-06-18',capabilities:{},clientInfo:{name:'test',version:'1'}})).result.serverInfo);
  child.stdin.write(JSON.stringify({jsonrpc:'2.0',method:'notifications/initialized'})+'\n');
  const tools=(await req('tools/list',{})).result.tools;
  assert.equal(tools.length,12);
  for(const name of ['etat','styles','erreurs']) assert.ok(!(await call(name)).isError,name);
  for(const [name,args] of [['monter',{}],['monter',{chemins:[]}],['prendre',{}],['prendre',{video:item.id,formats:['invalide']}],['changer_style',{video:'absente',style:'reel-impact'}],['style_reference',{video:'D:/absent.mp4'}],['suivre_export',{tache:'invalide'}]]) {
    assert.ok((await call(name,args)).isError, name);
  }
  assert.equal(writes.length,0);
  const taken=await call('prendre',{video:item.id,formats:['9:16','16:9']});
  assert.ok(!taken.isError,JSON.stringify(taken));
  assert.equal(writes.length,1);assert.deepEqual(writes[0].body.formats,['9:16','16:9']);
  const text=taken.content.map(x=>x.text).join('');
  for(const e of item.exports)assert.ok(text.includes(e.job));
  await call('prendre',{video:item.id,formats:['9:16']});assert.equal(writes.length,1,'pas de double export');
  const state=await call('etat');const stateText=state.content.map(x=>x.text).join('');
  for(const f of ['9:16','16:9']) assert.ok(stateText.includes(f));
  console.log('MCP OK : initialize, 12 outils, 3 lectures, 7 arguments invalides, 2 formats en une requete, aucun doublon.');
}finally{child.stdin.end();server.close();}
