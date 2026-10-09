// Contrat serveur <-> VRAI moteur (revue 2026-10-02) : les routes Claude du serveur lancent les VRAIS modules
// (claude_api via « python -m editeur claude », cerveau_claude, critique_claude, consigne) avec leurs vraies lignes de
// commande, et lisent leurs vraies sorties. ZERO appel a Claude : copie isolee SANS cles-api.env, ANTHROPIC_API_KEY retire
// de l'environnement, Claude ETEINT dans styles/claude.json de la copie (actif = false), IA locale coupee (EDITEUR_LLM=0).
// Usage (depuis la racine) : node docs/claude-api/tests/interface/setup-bac.mjs && node docs/claude-api/tests/interface/test-contrat-moteur.mjs
// (port 18795 ; remplace le faux moteur de la copie par une copie du vrai engine/editeur ; refaire setup-bac.mjs ensuite).
import {spawn, execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../../..');
const WORK = path.join(REAL, 'runtime', 'cache', 'tmp', 'claude-interface-1002');
const BOX = path.join(WORK, 'bac');
const B = (...p) => path.join(BOX, ...p);
const PORT = 18795;
const ORIGIN = `http://127.0.0.1:${PORT}`;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let ok = 0;
let ko = 0;
const check = (nom, cond, detail = '') => {
	cond ? ok++ : ko++;
	console.log(`${cond ? 'OK  ' : 'ECHEC'} ${nom}${!cond && detail ? ` — ${detail}` : ''}`);
};
const req = async (method, route, body, origin = ORIGIN) => {
	const r = await fetch(`${ORIGIN}${route}`, {method, headers: {'content-type': 'application/json', ...(origin ? {origin} : {})}, body: body === undefined ? undefined : JSON.stringify(body)});
	const text = await r.text();
	let data = text;
	try {
		data = JSON.parse(text);
	} catch {}
	return {status: r.status, data, text};
};
const job = async (id, ms = 120000) => {
	const fin = Date.now() + ms;
	for (;;) {
		const j = (await req('GET', `/api/jobs/${id}`)).data;
		if (!['running', 'queued'].includes(j.status) || Date.now() > fin) return j;
		await wait(400);
	}
};

// ---- garde-fous : jamais la vraie cle, jamais Claude allume, jamais le dossier reel ----
if (!fs.existsSync(B('app/server.mjs')) || !BOX.startsWith(WORK)) throw new Error('copie absente : node setup-bac.mjs');
if (fs.existsSync(B('cles-api.env'))) throw new Error('la copie ne doit pas contenir cles-api.env');
fs.rmSync(B('engine/editeur'), {recursive: true, force: true});
fs.cpSync(path.join(REAL, 'engine/editeur'), B('engine/editeur'), {recursive: true, filter: (s) => !s.includes('__pycache__')});
// calcul du montage (montage.compute -> node remotion/segments.mjs -> src/timeline.ts, types seulement) : COPIE, pas de jonction
fs.rmSync(B('remotion/src'), {recursive: true, force: true});
fs.cpSync(path.join(REAL, 'remotion/src'), B('remotion/src'), {recursive: true});
fs.copyFileSync(path.join(REAL, 'remotion/segments.mjs'), B('remotion/segments.mjs'));
const reglages = JSON.parse(fs.readFileSync(B('styles/claude.json'), 'utf8'));
fs.writeFileSync(B('styles/claude.json'), JSON.stringify({...reglages, actif: false}, null, 1));
const env = {...process.env, EDITEUR_PORT: String(PORT), EDITEUR_SANS_NAVIGATEUR: '1', EDITEUR_LLM: '0'};
delete env.ANTHROPIC_API_KEY;
delete env.ANTHROPIC_WORKSPACE_ID;
const log = fs.openSync(path.join(WORK, `serveur-${PORT}.log`), 'w');
const srv = spawn(process.execPath, [B('app/server.mjs')], {cwd: BOX, env, stdio: ['ignore', log, log], windowsHide: true});
for (let k = 0; k < 60; k++) {
	try {
		if ((await fetch(`${ORIGIN}/api/reels`)).ok) break;
	} catch {}
	await wait(250);
}
try {
	// statut reel : jamais la cle (aucune dans la copie), Claude eteint, estimations par modele (estimation_video)
	let r = await req('GET', '/api/claude', undefined, null);
	check('statut (vrai claude_api) : cle = false, eteint, pas pret', r.status === 200 && r.data.cle === false && r.data.actif === false && r.data.pret === false && /éteint/.test(r.data.raison), r.text.slice(0, 300));
	check('statut : estimation par modele ajoutee (estimation_video)', r.data.modeles?.length === 3 && r.data.modeles.every((m) => typeof m.estimation?.critique === 'number' && typeof m.estimation?.cerveau === 'number'), JSON.stringify(r.data.modeles).slice(0, 300));
	r = await req('PUT', '/api/claude/reglages', {plafond_jour: 0.5, modeles_taches: {critique: 'claude-haiku-4-5'}});
	const disque = JSON.parse(fs.readFileSync(B('styles/claude.json'), 'utf8'));
	check('reglages (vrai ecrire_reglages) : ecrits, Claude reste eteint', r.status === 200 && disque.plafond_jour === 0.5 && disque.modeles_taches.critique === 'claude-haiku-4-5' && disque.actif === false, r.text.slice(0, 200));
	r = await req('PUT', '/api/claude/reglages', {credit_date: '2026-02-30'});
	check('reglages : date impossible refusee par le moteur (400, sa phrase)', r.status === 400 && /AAAA-MM-JJ/.test(r.data.error ?? ''), `${r.status} ${r.data.error}`);
	r = await req('GET', '/api/claude/couts?jours=3&video=leads/script', undefined, null);
	check('couts (vrai couts()) : 3 jours, la video, derniers appels', r.status === 200 && r.data.jours?.length === 3 && r.data.video?.video === 'leads/script' && Array.isArray(r.data.derniers), r.text.slice(0, 300));
	// cerveau : vraie ligne de commande ; Claude eteint -> ok = false + raison, montage inchange
	const avantLeads = fs.readFileSync(B('projects/leads/reels/script.json'), 'utf8');
	r = await req('POST', '/api/reels/leads/script/claude/cerveau', {});
	let j = await job(r.data.id);
	check('cerveau (vrai module) : termine, ok = false + raison (Claude eteint)', j.status === 'done' && j.result?.ok === false && /éteint|prêt|coupé/.test(j.result?.raison ?? ''), JSON.stringify(j).slice(0, 400));
	check('cerveau eteint : montage inchange', fs.readFileSync(B('projects/leads/reels/script.json'), 'utf8') === avantLeads);
	// critique : vraie ligne de commande (<video> --reel <dossier> <id> --json) ; Claude eteint -> statut « eteint », rien range
	const outRappel = B('livraisons/Lot test/Pourquoi on rappelle en 60 secondes - FINAL.mp4');
	r = await req('POST', '/api/reels/rappel/script/claude/critique', {video: outRappel});
	j = await job(r.data.id);
	check('critique (vrai module) : arguments acceptes, JSON lu, statut eteint', j.status === 'done' && j.result?.ok === false && j.result?.statut === 'eteint', JSON.stringify(j).slice(0, 400));
	// consigne : vraie ligne de commande, IA locale coupee et Claude eteint -> regles simples ; essai (rien ecrit)
	const avantConsigne = fs.readFileSync(B('projects/leads/reels/script.json'), 'utf8');
	r = await req('POST', '/api/reels/leads/script/consigne', {texte: 'mets la musique moins forte', t: 2, simuler: true});
	j = await job(r.data.id);
	check('consigne (vrai module) : termine, contrat (changements, refus, question, moteur)', j.status === 'done' && Array.isArray(j.result?.changements) && Array.isArray(j.result?.refus)
		&& 'question' in (j.result ?? {}) && ['regles', 'local', 'claude'].includes(j.result?.moteur), JSON.stringify(j).slice(0, 400));
	check('consigne --simuler : montage inchange', fs.readFileSync(B('projects/leads/reels/script.json'), 'utf8') === avantConsigne);
	check('aucune cle dans les reponses', ![JSON.stringify(j)].some((t) => /sk-ant-/.test(t)));
} catch (e) {
	ko++;
	console.log('ECHEC', e.stack || e.message);
} finally {
	try {
		execFileSync(path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe'), ['/PID', String(srv.pid), '/T', '/F'], {stdio: 'ignore'});
	} catch {}
	fs.closeSync(log);
}
console.log(`\n${ok}/${ok + ko} reussis`);
process.exit(ko ? 1 : 0);
