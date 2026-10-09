// « Refaire seulement ce passage » de bout en bout par HTTP, sur une COPIE ISOLEE du serveur (port 18823), jamais sur le
// vrai dossier ni le vrai serveur 8790.
//   node docs/direction-creative-v2/tests/passage/test-http-passage.mjs [--garder]
// Bac : runtime/cache/tmp/dcv2-passage/serveur-<hasard>/ (copies : app/server.mjs, app/ui, app/dist, styles, moteur,
// remotion/src + segments.mjs, projects/script1 ; jonction EN LECTURE vers runtime/venv, retiree a la fin avec rmdir — le
// lien seulement, jamais sa cible). --garder : le serveur du bac reste ouvert (controle dans le navigateur) jusqu'a ce que
// le fichier <bac>/stop existe ; il s'arrete alors et retire la jonction.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../../..');
const FIX = path.join(REAL, 'docs/direction-creative-v2/tests/fixtures'); // donnees figees des tests (jamais projects/)
const origine = (rel) => path.join(/^projects\/(?!_)/.test(rel) ? FIX : REAL, rel); // projects/<video> : copie figee ; _cache, assets... : dossier reel
const PORT = 18823;
const BASE = `http://127.0.0.1:${PORT}`;
const keep = process.argv.includes('--garder');
fs.mkdirSync(path.join(REAL, 'runtime/cache/tmp/dcv2-passage'), {recursive: true});
const box = fs.mkdtempSync(path.join(REAL, 'runtime/cache/tmp/dcv2-passage/serveur-'));
const B = (...p) => path.join(box, ...p);
const copy = (rel, to = rel) => fs.cpSync(origine(rel), B(to), {recursive: true});
for (const d of ['app/ui', 'projects/script1/reels', 'runtime/cache/tmp', 'media/entree', 'engine', 'remotion']) fs.mkdirSync(B(d), {recursive: true});
copy('app/server.mjs');
copy('app/ui/index.html');
copy('app/ui/styles.css');
copy('app/dist');
copy('styles');
copy('engine/editeur');
copy('remotion/src');
copy('remotion/segments.mjs');
copy('projects/script1/project.json');
copy('projects/script1/reels/script.json');
fs.symlinkSync(path.join(REAL, 'runtime/venv'), B('runtime/venv'), 'junction');
const REEL = B('projects/script1/reels/script.json');
const hash = (f = REEL) => crypto.createHash('sha1').update(fs.readFileSync(f)).digest('hex');

let fails = 0;
let count = 0;
const ok = (cond, msg) => {
	count++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${msg}`);
	if (!cond) fails++;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const call = async (method, route, body, origin = BASE) => {
	const headers = {'content-type': 'application/json'};
	if (origin) headers.origin = origin;
	const r = await fetch(BASE + route, {method, headers, body: body === undefined ? undefined : JSON.stringify(body)});
	let data = null;
	try {
		data = await r.json();
	} catch {}
	return {status: r.status, data};
};
const job = async (id) => {
	for (let k = 0; k < 240; k++) {
		const j = (await call('GET', `/api/jobs/${id}`)).data;
		if (j && j.status !== 'running' && j.status !== 'queued') return j;
		await sleep(250);
	}
	return null;
};
const passage = (body, origin) => call('POST', '/api/reels/script1/script/passage', body, origin);
const versions = async () => (await call('GET', '/api/reels/script1/script/versions')).data ?? [];

const log = fs.openSync(B('serveur.log'), 'w');
const child = spawn(process.execPath, [B('app/server.mjs')], {env: {...process.env, EDITEUR_PORT: String(PORT), EDITEUR_LLM: '0'},
	stdio: ['ignore', log, log], windowsHide: true});
const cleanup = () => {
	try {
		child.kill();
	} catch {}
	try {
		fs.rmdirSync(B('runtime/venv')); // la jonction seulement
	} catch (e) {
		console.log(`Jonction a retirer a la main (rmdir) : ${B('runtime/venv')} (${e.message})`);
	}
};
try {
	for (let k = 0; k < 80; k++) {
		try {
			await fetch(`${BASE}/api/reels`);
			break;
		} catch {
			await sleep(250);
		}
	}
	console.log(`Bac : ${box}`);
	const h0 = hash();

	// 1. refus immediats (serveur) : plage a l'envers, trop courte, origine absente ou fausse
	let r = await passage({debut: 40, fin: 30});
	ok(r.status === 400 && /début avant la fin/.test(r.data?.error ?? ''), `plage a l'envers -> ${r.status} « ${r.data?.error} »`);
	r = await passage({debut: 10, fin: 10.1});
	ok(r.status === 400, `plage de 0,1 s -> ${r.status}`);
	r = await passage({debut: 'abc', fin: 3});
	ok(r.status === 400, `debut non numerique -> ${r.status}`);
	r = await passage({debut: 30, fin: 40}, null);
	ok(r.status === 403, `sans origine -> ${r.status}`);
	r = await passage({debut: 30, fin: 40}, 'http://localhost:18823');
	ok(r.status === 403, `origine « localhost » -> ${r.status}`);
	ok(hash() === h0, 'refus : reel inchange');

	// 2. passage 30-40 s : tache, compte rendu en francais, une seule version « avant refaire le passage »
	r = await passage({debut: 30, fin: 40});
	ok(r.status === 202 && r.data?.id, `POST passage 30-40 s -> ${r.status}`);
	let j = await job(r.data.id);
	ok(j?.status === 'done', `tache terminee (${j?.status} ${j?.error ?? ''})`);
	const res = j?.result ?? {};
	console.log(`      ${res.resume}`);
	for (const c of res.changes ?? []) console.log(`        - ${c}`);
	ok(res.modifie === true && typeof res.version === 'string' && /Passage 0:30,0 → 0:40,0/.test(res.resume), 'compte rendu : modifie, version, resume');
	const vs = await versions();
	const miennes = vs.filter((v) => v.name === 'avant refaire le passage');
	ok(miennes.length === 1 && miennes[0].file === res.version, `une seule version « avant refaire le passage » (${miennes.length}) = celle du compte rendu`);
	ok(hash(B('projects/script1/versions/script', res.version)) === h0, 'la version gardee est le reel d\'avant, a l\'octet pres');
	ok(hash() !== h0, 'le reel a change');
	const opened = (await call('GET', '/api/reels/script1/script/open')).data;
	ok(opened?.reel?.sobriete?.resume === res.resume, 'relecture (open) : le compte rendu est dans le reel');

	// 3. « Annuler » = restaurer la version : le reel revient exactement
	r = await call('POST', '/api/reels/script1/script/restore', {file: res.version});
	ok(r.status === 200, `POST restore -> ${r.status}`);
	ok(hash() === h0, 'Annuler : reel revenu a l\'octet pres');

	// 4. deux fois de suite : la 2e ne change rien (fichier non reecrit)
	j = await job((await passage({debut: 30, fin: 40})).data.id);
	const h1 = hash();
	j = await job((await passage({debut: 30, fin: 40})).data.id);
	ok(j?.status === 'done' && j.result.modifie === false && j.result.version === null && hash() === h1,
		`2e fois : ${j?.result?.resume}`);

	// 5. plage apres la fin de la video : la tache echoue avec une phrase claire, rien n'est ecrit
	r = await passage({debut: 500, fin: 510});
	j = await job(r.data.id);
	ok(j?.status === 'failed' && /après la fin de la vidéo/.test(j.error ?? '') && hash() === h1, `apres la fin -> ${j?.status} « ${j?.error} »`);
	ok(!/Traceback/.test(j?.error ?? ''), 'aucune trace technique dans le message');
	fs.copyFileSync(B('projects/script1/versions/script', res.version), REEL); // bac remis comme au depart (controle visuel)
} catch (e) {
	fails++;
	console.log(`ECHEC inattendu : ${e.stack || e}`);
} finally {
	console.log(`\n${count - fails}/${count} verifications HTTP « passage » reussies`);
	if (keep && !fails) {
		console.log(`Serveur du bac ouvert : ${BASE} (creer ${B('stop')} pour l'arreter)`);
		while (!fs.existsSync(B('stop'))) await sleep(500);
	}
	cleanup();
}
process.exit(fails ? 1 : 0);
