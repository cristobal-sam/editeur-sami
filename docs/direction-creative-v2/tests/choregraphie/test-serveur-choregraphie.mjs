// Chorégraphie de bout en bout sur une COPIE ISOLEE du serveur (port 18803), jamais sur le vrai dossier ni le port 8790.
//   node docs/direction-creative-v2/tests/choregraphie/test-serveur-choregraphie.mjs
// Bac : runtime/cache/tmp/dcv2-choregraphie/serveur-<hasard>/ (copies : app/server.mjs, styles, moteur, calcul du montage
// remotion/segments.mjs + src/timeline.ts + src/types.ts, projects/script1, assets/music/tech.ogg ; jonction EN LECTURE vers
// runtime/venv, retiree a la fin avec rmdir — le lien seulement, jamais sa cible).
// Verifie : la choregraphie produite par le moteur passe la validation du serveur (PUT) ; les retouches de l'interface
// (cadenas, desactiver, vitesse) aussi ; POST …/choregraphie lance la tache, garde la version « avant chorégraphie »,
// garde le mouvement verrouille et la retouche ; {tout: true} refait la retouche mais jamais le verrouille.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn, spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../../..');
const FIX = path.join(REAL, 'docs/direction-creative-v2/tests/fixtures'); // donnees figees des tests (jamais projects/)
const origine = (rel) => path.join(/^projects\/(?!_)/.test(rel) ? FIX : REAL, rel); // projects/<video> : copie figee ; _cache, assets... : dossier reel
const PORT = 18803;
const BASE = `http://127.0.0.1:${PORT}`;
fs.mkdirSync(path.join(REAL, 'runtime/cache/tmp/dcv2-choregraphie'), {recursive: true});
const box = fs.mkdtempSync(path.join(REAL, 'runtime/cache/tmp/dcv2-choregraphie/serveur-'));
const B = (...p) => path.join(box, ...p);
const copy = (rel, to = rel) => fs.cpSync(origine(rel), B(to), {recursive: true});
for (const d of ['app/ui', 'projects/script1/reels', 'runtime/cache/tmp', 'media/entree', 'engine', 'remotion/src', 'assets/music']) fs.mkdirSync(B(d), {recursive: true});
copy('app/server.mjs');
copy('app/ui/index.html');
copy('app/ui/styles.css');
copy('styles');
copy('engine/editeur');
copy('remotion/segments.mjs');
copy('remotion/src/timeline.ts');
copy('remotion/src/types.ts');
copy('assets/music/tech.ogg');
copy('projects/script1/project.json');
copy('projects/script1/reels/script.json');
fs.symlinkSync(path.join(REAL, 'runtime/venv'), B('runtime/venv'), 'junction');
const VRAI = path.join(FIX, 'projects/script1/reels/script.json');
const sha = (f) => crypto.createHash('sha1').update(fs.readFileSync(f)).digest('hex');
const vraiAvant = sha(VRAI);
const REEL = B('projects/script1/reels/script.json');
const disk = () => JSON.parse(fs.readFileSync(REEL, 'utf8'));

let fails = 0;
let count = 0;
const ok = (cond, msg) => {
	count++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${msg}`);
	if (!cond) fails++;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const call = async (method, route, body) => {
	const r = await fetch(BASE + route, {method, headers: {'content-type': 'application/json', origin: BASE}, body: body === undefined ? undefined : JSON.stringify(body)});
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
		await sleep(500);
	}
	return null;
};

// choregraphie calculee par le moteur de la COPIE (meme code que la tache), sur une copie du reel
const genere = () => {
	const tmp = B('runtime/cache/tmp/essai.json');
	fs.writeFileSync(tmp, JSON.stringify(disk()));
	const p = spawnSync(B('runtime/venv/Scripts/python.exe'), ['-c', `import json,sys
from editeur import choregraphie
r=json.load(open(sys.argv[1],encoding='utf-8')); choregraphie.actualiser(r, creer=True)
print(json.dumps(r['choreography'], ensure_ascii=False))`, tmp], {cwd: B('engine'), encoding: 'utf8',
		env: {...process.env, EDITEUR_ROOT: box, EDITEUR_LLM: '0', PYTHONIOENCODING: 'utf-8'}});
	if (p.status !== 0) throw new Error(p.stderr);
	return JSON.parse(p.stdout.trim().split('\n').pop());
};

const log = fs.openSync(B('serveur.log'), 'w');
const child = spawn(process.execPath, [B('app/server.mjs')], {env: {...process.env, EDITEUR_PORT: String(PORT), EDITEUR_LLM: '0'}, stdio: ['ignore', log, log], windowsHide: true});
try {
	for (let k = 0; k < 60; k++) {
		try {
			await fetch(`${BASE}/api/reels`);
			break;
		} catch {
			await sleep(250);
		}
	}
	// 1. la choregraphie du moteur passe la validation du serveur
	const ch = genere();
	ok(ch.cues.length > 0, `moteur (copie) : ${ch.cues.length} mouvements — ${ch.meta.resume}`);
	let r = await call('PUT', '/api/reels/script1/script', {choreography: ch});
	ok(r.status === 200, `PUT de la choregraphie du moteur accepte : ${r.status} ${r.data?.error ?? ''}`);
	ok(JSON.stringify(disk().choreography) === JSON.stringify(ch), 'choregraphie enregistree telle quelle (accents compris)');

	// 2. retouches faites par l'interface (memes transformations que choreo-lane.tsx) : acceptees
	const [a, b, c] = ch.cues;
	const retouche = {...ch, cues: ch.cues.map((x) => {
		if (x.id === a.id) return {...x, locked: true, entree: {type: 'trace', direction: 'droite', duree: 0.8, courbe: 'lineaire'}};
		if (x.id === b.id) return {...x, manual: true, desactive: true};
		if (x.id === c.id) return {...x, manual: true, sortie: {...x.sortie, duree: Math.round(x.sortie.duree * 1.33 * 100) / 100}};
		return x;
	})};
	r = await call('PUT', '/api/reels/script1/script', {choreography: retouche});
	ok(r.status === 200, `PUT des retouches (cadenas, desactiver, plus lent) : ${r.status} ${r.data?.error ?? ''}`);
	r = await call('PUT', '/api/reels/script1/script', {choreography: {...retouche, cues: [{...a, locked: undefined}]}});
	ok(r.status === 400, `mouvement sans « locked » refuse (l'interface le garde toujours) : ${r.status} « ${r.data?.error} »`);
	r = await call('PUT', '/api/reels/script1/script', {choreography: retouche});

	// 3. « Refaire la chorégraphie » : tache, version « avant », verrou et retouches gardes
	const versions = () => (fs.existsSync(B('projects/script1/versions/script')) ? fs.readdirSync(B('projects/script1/versions/script')) : []);
	r = await call('POST', '/api/reels/script1/script/choregraphie', {});
	ok(r.status === 202 && r.data?.id, `POST …/choregraphie : tache lancee (${r.status})`);
	let j = await job(r.data.id);
	ok(j?.status === 'done' && j.result?.cues > 0, `tache terminee : ${j?.status} — ${j?.result?.resume ?? j?.error}`);
	ok(versions().some((f) => f.includes('avant chorégraphie')), 'version « avant chorégraphie » gardee');
	let got = Object.fromEntries(disk().choreography.cues.map((x) => [x.id, x]));
	const want = Object.fromEntries(retouche.cues.map((x) => [x.id, x]));
	ok(JSON.stringify(got[a.id]) === JSON.stringify(want[a.id]), 'mouvement verrouille garde tel quel');
	ok(JSON.stringify(got[b.id]) === JSON.stringify(want[b.id]) && JSON.stringify(got[c.id]) === JSON.stringify(want[c.id]), 'retouches gardees telles quelles');

	// 4. {tout: true} : les retouches sont refaites, jamais le verrouille
	r = await call('POST', '/api/reels/script1/script/choregraphie', {tout: true});
	j = await job(r.data.id);
	got = Object.fromEntries(disk().choreography.cues.map((x) => [x.id, x]));
	ok(j?.status === 'done', `tache « tout refaire » : ${j?.status} — ${j?.result?.resume ?? j?.error}`);
	ok(JSON.stringify(got[a.id]) === JSON.stringify(want[a.id]), 'tout refaire : le verrouille reste identique');
	ok(!got[b.id]?.manual && !got[b.id]?.desactive && !got[c.id]?.manual, 'tout refaire : les retouches sont recalculees par l\'IA');

	// 5. choregraphie verrouillee : la tache ne change rien
	const verrou = {...disk().choreography, locked: true};
	await call('PUT', '/api/reels/script1/script', {choreography: verrou});
	r = await call('POST', '/api/reels/script1/script/choregraphie', {tout: true});
	j = await job(r.data.id);
	ok(j?.status === 'done' && /verrouillée/.test(j.result?.resume) && JSON.stringify(disk().choreography) === JSON.stringify(verrou),
		`choregraphie verrouillee : rien ne change (« ${j?.result?.resume} »)`);
} finally {
	child.kill();
	await sleep(400);
	try {
		fs.rmdirSync(B('runtime/venv')); // la jonction seulement
	} catch (e) {
		console.log(`Jonction a retirer a la main (rmdir) : ${B('runtime/venv')} (${e.message})`);
	}
	fs.closeSync(log);
}
ok(sha(VRAI) === vraiAvant, 'reel fige fixtures/projects/script1/reels/script.json inchange');
console.log(`\n${count - fails}/${count} verifications serveur (choregraphie) reussies (bac : ${box})`);
process.exit(fails ? 1 : 0);
