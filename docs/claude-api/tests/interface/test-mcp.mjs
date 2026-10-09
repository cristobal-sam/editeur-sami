// Test du plugin MCP (plugins/editeur-sami/mcp/serveur.mjs, le vrai fichier) branche sur le serveur de la COPIE (port 18796,
// faux moteur) : nouveaux outils claude_couts (lecture seule), consigne, claude_critique ; jamais de cle dans les reponses.
// EDITEUR_MCP_SANS_DEMARRAGE=1 : le plugin ne demarre jamais d'editeur lui-meme.
import {spawn, execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import {fileURLToPath} from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../../..');
const WORK = path.join(path.resolve(HERE, '../../../..'), 'runtime', 'cache', 'tmp', 'claude-interface-1002'); // bac (jonctions), journaux, captures
const BOX = path.join(WORK, 'bac');
const PORT = 18796;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let ok = 0;
let ko = 0;
const check = (nom, cond, detail = '') => {
	cond ? ok++ : ko++;
	console.log(`${cond ? 'OK  ' : 'ECHEC'} ${nom}${!cond && detail ? ` — ${String(detail).slice(0, 400)}` : ''}`);
};
const srvLog = fs.openSync(path.join(WORK, `serveur-${PORT}-mcp.log`), 'w');
const srv = spawn(process.execPath, [path.join(BOX, 'app/server.mjs')], {cwd: BOX, env: {...process.env, EDITEUR_PORT: String(PORT), EDITEUR_SANS_NAVIGATEUR: '1'},
	stdio: ['ignore', srvLog, srvLog], windowsHide: true});
for (let k = 0; k < 60; k++) {
	try {
		if ((await fetch(`http://127.0.0.1:${PORT}/api/reels`)).ok) break;
	} catch {}
	await wait(250);
}
const mcp = spawn(process.execPath, [path.join(REAL, 'plugins/editeur-sami/mcp/serveur.mjs')], {env: {...process.env, EDITEUR_PORT: String(PORT), EDITEUR_MCP_SANS_DEMARRAGE: '1'},
	stdio: ['pipe', 'pipe', 'ignore'], windowsHide: true});
const rl = readline.createInterface({input: mcp.stdout});
const attente = new Map();
rl.on('line', (l) => {
	const m = JSON.parse(l);
	if (m.id !== undefined && attente.has(m.id)) {
		attente.get(m.id)(m);
		attente.delete(m.id);
	}
});
let n = 0;
const rpc = (method, params) => new Promise((r) => {
	attente.set(++n, r);
	mcp.stdin.write(JSON.stringify({jsonrpc: '2.0', id: n, method, params}) + '\n');
});
const outil = async (name, args) => {
	const r = await rpc('tools/call', {name, arguments: args});
	return {texte: r.result?.content?.map((c) => c.text).join('\n') ?? JSON.stringify(r.error), erreur: !!r.result?.isError};
};
const CLES = /sk-ant-|FAUSSECLE/;
try {
	const init = await rpc('initialize', {protocolVersion: '2025-06-18', capabilities: {}, clientInfo: {name: 'test', version: '1'}});
	check('initialize : consignes parlent de Claude payant', /PAYANT/.test(init.result?.instructions ?? ''));
	const list = (await rpc('tools/list', {})).result.tools;
	const t = Object.fromEntries(list.map((x) => [x.name, x]));
	check('3 nouveaux outils', !!t.claude_couts && !!t.claude_critique && !!t.consigne, Object.keys(t).join(','));
	check('claude_couts en lecture seule', t.claude_couts?.annotations?.readOnlyHint === true);
	check('claude_critique / consigne : pas en lecture seule, monde ouvert', t.claude_critique?.annotations?.readOnlyHint === false && t.consigne?.annotations?.openWorldHint === true);
	check('descriptions : seulement sur demande explicite', /SEULEMENT/.test(t.claude_critique?.description) && /SEULEMENT/.test(t.consigne?.description));
	let r = await outil('claude_couts', {});
	check('claude_couts : etat + depenses + derniers appels', /clé présente/.test(r.texte) && /Dépensé aujourd’hui/.test(r.texte) && /Derniers appels/.test(r.texte), r.texte);
	check('claude_couts : jamais de cle', !CLES.test(r.texte) && /\[clé masquée\]/.test(r.texte), r.texte);
	r = await outil('claude_couts', {video: 'leads', jours: 3});
	check('claude_couts d\'une video', /« Répondez vite à vos leads » : 0,09 \$ en 4 appel/.test(r.texte), r.texte);
	r = await outil('consigne', {video: 'leads', texte: ''});
	check('consigne vide refusee', r.erreur && /Écris/.test(r.texte), r.texte);
	r = await outil('consigne', {video: 'leads', texte: 'ambigu', simuler: true});
	check('consigne ambigue : question transmise', /demande une précision/.test(r.texte) && /Quel bandeau/.test(r.texte), r.texte);
	r = await outil('consigne', {video: 'leads', texte: 'enlève le bandeau du début', t: 3});
	check('consigne : changements + comment annuler', /Changements faits/.test(r.texte) && /0:03,0 — Bandeau du début retiré/.test(r.texte) && /restaurer_version/.test(r.texte), r.texte);
	r = await outil('claude_critique', {video: 'rappel'});
	const id = /tache ([a-f0-9-]{36})/.exec(r.texte)?.[1];
	check('claude_critique : tache lancee sur l\'export', !!id && /Pourquoi on rappelle en 60 secondes - FINAL\.mp4/.test(r.texte), r.texte);
	r = await outil('suivre_export', {tache: id, attendre: 30});
	check('suivre_export : avis de Claude lisible', /Avis de Claude : 6,5\/10/.test(r.texte) && /0:00,8 : Sous-titre collé au bord/.test(r.texte), r.texte);
	check('suivre_export : gravite du probleme (avis du vrai module : temps, gravite, probleme)', /\[important\] 0:00,8/.test(r.texte), r.texte);
	r = await outil('claude_critique', {video: 'leads'});
	check('claude_critique sans export : refus clair, rien lance', r.erreur && /pas encore été exportée/.test(r.texte), r.texte);
	r = await outil('claude_critique', {video: 'inconnue-xyz'});
	check('video inconnue : refus clair', r.erreur && /introuvable/.test(r.texte), r.texte);
} finally {
	mcp.stdin.end();
	mcp.kill();
	try {
		execFileSync(path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe'), ['/PID', String(srv.pid), '/T', '/F'], {stdio: 'ignore'});
	} catch {}
	fs.closeSync(srvLog);
}
console.log(`\n${ok}/${ok + ko} reussis`);
process.exit(ko ? 1 : 0);
