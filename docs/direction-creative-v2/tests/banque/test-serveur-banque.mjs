// Banque V2 par HTTP, sur une COPIE ISOLEE du serveur (port 18831 ; jamais le vrai dossier ni le port 8790).
//   node docs/direction-creative-v2/tests/banque/test-serveur-banque.mjs [--garder] [--medias] [--port 18832]
// Bac : runtime/cache/tmp/dcv2-banque/serveur-<hasard>/ : copies de app/server.mjs, de l'interface compilee, des styles, du
// moteur, des copies figees fixtures/projects/script1 et script2 (reels + project.json), de assets/banque (dates gardees : aucun recalcul) ;
// JONCTIONS EN LECTURE vers runtime/venv, tools, assets/sfx, assets/overlays, assets/fonts (retirees a la fin avec rmdir : le
// lien seulement, jamais sa cible). --medias : copie aussi les medias optimises de script2 (apercu reel dans le navigateur).
// --garder : laisse le serveur tourner apres les essais (controle dans le navigateur) ; l'arreter avec Ctrl+C.
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../../..');
const FIX = path.join(REAL, 'docs/direction-creative-v2/tests/fixtures'); // donnees figees des tests (jamais projects/)
const origine = (rel) => path.join(/^projects\/(?!_)/.test(rel) ? FIX : REAL, rel); // projects/<video> : copie figee ; _cache, assets... : dossier reel
const arg = (k) => process.argv.includes(k);
const PORT = Number(process.argv[process.argv.indexOf('--port') + 1]) > 0 && arg('--port') ? Number(process.argv[process.argv.indexOf('--port') + 1]) : 18831;
const BASE = `http://127.0.0.1:${PORT}`;
fs.mkdirSync(path.join(REAL, 'runtime/cache/tmp/dcv2-banque'), {recursive: true});
const box = fs.mkdtempSync(path.join(REAL, 'runtime/cache/tmp/dcv2-banque/serveur-'));
const B = (...p) => path.join(box, ...p);
const copy = (rel, to = rel) => fs.cpSync(origine(rel), B(to), {recursive: true, preserveTimestamps: true});
const liens = [];
const lien = (rel) => {
	fs.mkdirSync(path.dirname(B(rel)), {recursive: true});
	fs.symlinkSync(path.join(REAL, rel), B(rel), 'junction');
	liens.push(B(rel));
};
for (const d of ['app/ui', 'runtime/cache/tmp', 'media/entree', 'livraisons', 'engine', 'assets']) fs.mkdirSync(B(d), {recursive: true});
for (const f of ['app/server.mjs', 'app/ui/index.html', 'app/ui/styles.css', 'app/dist', 'styles', 'engine/editeur', 'assets/banque']) copy(f);
for (const p of ['script1', 'script2']) {
	copy(`projects/${p}/project.json`);
	copy(`projects/${p}/reels/script.json`);
}
for (const l of ['runtime/venv', 'tools', 'assets/sfx', 'assets/overlays', 'assets/fonts']) lien(l);
if (arg('--medias')) {
	const r = JSON.parse(fs.readFileSync(B('projects/script2/reels/script.json'), 'utf8'));
	for (const s of Object.values(r.sources)) for (const k of ['proxy', 'voice']) if (s[k] && fs.existsSync(path.join(REAL, s[k]))) copy(s[k]);
}
console.log(`BAC=${box}`);

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
	const type = r.headers.get('content-type') || '';
	const buf = Buffer.from(await r.arrayBuffer());
	let data = null;
	try {
		data = type.includes('json') ? JSON.parse(buf.toString('utf8')) : buf;
	} catch {}
	return {status: r.status, type, data, text: buf.toString('utf8')};
};

// regles de l'interface (app/ui/banque.tsx) : les elements envoyes sont exactement ceux que cree le bouton « Ajouter »
const MODULES = path.join(REAL, 'remotion', 'node_modules');
const esbuild = createRequire(path.join(MODULES, 'x.js'))('esbuild');
await esbuild.build({stdin: {contents: "export {elementPourReel, poser, visible} from './app/ui/banque.tsx';", resolveDir: REAL, loader: 'ts'},
	bundle: true, platform: 'node', format: 'esm', outfile: B('banque-regles.mjs'), nodePaths: [MODULES], jsx: 'automatic', target: 'node20',
	define: {'process.env.NODE_ENV': '"production"'}, logLevel: 'error',
	banner: {js: "import {createRequire as __cr} from 'node:module'; const require = __cr(import.meta.url);"}});
const regles = await import(pathToFileURL(B('banque-regles.mjs')).href);

const log = fs.openSync(B('serveur.log'), 'w');
const child = spawn(process.execPath, [B('app/server.mjs')], {env: {...process.env, EDITEUR_PORT: String(PORT), EDITEUR_LLM: '0'}, stdio: ['ignore', log, log], windowsHide: true});
const fin = () => {
	try {
		child.kill();
	} catch {}
	for (const l of liens) {
		try {
			fs.rmdirSync(l); // le lien seulement
		} catch {}
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
	const fichier = JSON.parse(fs.readFileSync(B('assets/banque/catalogue.json'), 'utf8'));
	const n = fichier.entrees.length;

	// 1. catalogue complet par le moteur
	let r = await call('GET', '/api/banque');
	ok(r.status === 200 && r.data?.total === n && r.data.entrees.length === n, `GET /api/banque : ${r.status}, ${r.data?.total} ressources (fichier : ${n})`);
	const casses = (r.text.match(/�/g) || []).length;
	const noms = new Map(fichier.entrees.map((e) => [e.id, e.nom]));
	const differents = (r.data?.entrees ?? []).filter((e) => noms.get(e.id) !== e.nom).length;
	ok(casses === 0 && differents === 0, `accents intacts dans la reponse (${Math.round(r.text.length / 1024)} Ko) : ${casses} caractere(s) abime(s), ${differents} nom(s) different(s)`);
	ok(Object.keys(r.data?.categories ?? {}).length === 4, `categories par type : ${Object.entries(r.data?.categories ?? {}).map(([t, c]) => `${t} ${c.length}`).join(', ')}`);

	// 2. filtres
	r = await call('GET', '/api/banque?type=son&categorie=whoosh');
	ok(r.status === 200 && r.data.total > 0 && r.data.entrees.every((e) => e.type === 'son' && e.categorie === 'whoosh'), `?type=son&categorie=whoosh : ${r.data?.total}`);
	r = await call('GET', `/api/banque?q=${encodeURIComponent('flèche')}`);
	ok(r.status === 200 && r.data.entrees.some((e) => e.id === 'vecteur:fleche'), `?q=flèche : ${r.data?.total} (dont vecteur:fleche)`);
	const sansAccent = await call('GET', '/api/banque?q=fleche');
	ok(sansAccent.data?.total === r.data?.total, `?q=fleche (sans accent) : ${sansAccent.data?.total}, meme resultat`);
	r = await call('GET', '/api/banque?intensite=3&type=template');
	ok(r.status === 200 && r.data.total > 0 && r.data.entrees.every((e) => e.intensite === 3 && e.type === 'template'), `?intensite=3&type=template : ${r.data?.total}`);
	r = await call('GET', `/api/banque?format=${encodeURIComponent('16:9')}&type=effet`);
	ok(r.status === 200 && r.data.total === fichier.compte.effet, `?format=16:9&type=effet : ${r.data?.total}`);
	for (const q of ['type=musique', 'intensite=5', `categorie=${encodeURIComponent('<b>')}`, `format=${encodeURIComponent('2:1')}`]) {
		r = await call('GET', `/api/banque?${q}`);
		ok(r.status === 400 && typeof r.data?.error === 'string', `?${decodeURIComponent(q)} refuse : ${r.status} « ${r.data?.error} »`);
	}

	// 3. apercus (toujours sous assets/)
	for (const [id, type] of [['son:banque:impact-cinema', 'image/png'], ['vecteur:fleche', 'image/svg+xml'], ['template:mot-geant', 'image/svg+xml'], ['effet:grain-leger', 'image/png']]) {
		r = await call('GET', `/api/banque/apercu/${id}`); // id brut (« : » permis dans un chemin)
		const png = r.data instanceof Buffer && r.data.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
		ok(r.status === 200 && r.type.startsWith(type) && (type !== 'image/png' || png) && (type !== 'image/svg+xml' || r.text.includes('<svg')), `apercu ${id} : ${r.status} ${r.type}`);
	}
	r = await call('GET', '/api/banque/apercu/son:rien');
	ok(r.status === 404, `apercu inconnu : ${r.status}`);
	r = await call('GET', '/api/banque/apercu/..%2F..%2Fpackage.json');
	ok(r.status === 404, `apercu hors de la banque : ${r.status}`);
	r = await call('GET', '/assets/banque/catalogue.json');
	ok(r.status === 200 && r.type.includes('json') && r.data?.entrees?.length === n, `catalogue lu directement par l'interface : ${r.status}, ${r.data?.entrees?.length}`);
	r = await call('GET', `/assets/${fichier.entrees.find((e) => e.source === 'kenney').fichier}`);
	ok(r.status === 200 && r.type === 'audio/ogg', `son Kenney servi pour l'ecoute : ${r.status} ${r.type}`);

	// 4. « Ajouter » (regles de l'interface) puis sauvegarde automatique (PUT) : validation stricte du serveur
	const byId = new Map(fichier.entrees.map((e) => [e.id, e]));
	const kenney = fichier.entrees.find((e) => e.id.startsWith('son:kenney:impact-sounds-impactMetal_heavy'));
	let reel = JSON.parse(fs.readFileSync(B('projects/script2/reels/script.json'), 'utf8'));
	const poses = [];
	for (const [id, at] of [[kenney.id, 15.5], ['son:editeur:whoosh-court', 20], ['son:banque:riser-long', 30], ['vecteur:fleche', 15.2], ['vecteur:coche', 21],
		['template:liste-benefices', 16.6], ['template:chiffre-prix', 24], ['template:mot-geant', 26], ['template:carte-droite', 28], ['effet:grain-leger', 0], ['effet:flash-glitch', 0]]) {
		const {champ, element} = regles.elementPourReel(byId.get(id), reel, at);
		reel = regles.poser(reel, champ, element);
		poses.push({id, champ, element});
	}
	const corps = {sfx: reel.sfx, vectors: reel.vectors, graphics: reel.graphics, effects: reel.effects, flash: reel.flash};
	r = await call('PUT', '/api/reels/script2/script', corps);
	ok(r.status === 200, `PUT des ${poses.length} ajouts (sons Kenney / editeur / crees ici, vecteurs, modeles, effets) : ${r.status} ${r.data?.error ?? ''}`);
	let disque = JSON.parse(fs.readFileSync(B('projects/script2/reels/script.json'), 'utf8'));
	const trouve = poses.every(({champ, element}) => {
		if (champ === 'sfx.extra') return disque.sfx.extra.some((x) => x.id === element.id && x.name === element.name && x.manual === true);
		if (champ === 'flash' || champ === 'effects') return JSON.stringify(disque[champ]) === JSON.stringify(element);
		return disque[champ].some((x) => x.id === element.id && x.manual === true);
	});
	ok(trouve, 'tout est sur le disque, marque manual (protege des passes automatiques)');
	// style avec habillage : scene du style + « Activer les bruitages »
	let s1 = JSON.parse(fs.readFileSync(B('projects/script1/reels/script.json'), 'utf8'));
	const vuAvant = regles.visible(byId.get('son:banque:impact-cinema'), s1);
	const scene = regles.elementPourReel(byId.get('template:notification'), s1, 16.2);
	const son = regles.elementPourReel(byId.get('son:banque:impact-cinema'), s1, 16.4);
	s1 = regles.poser(regles.poser(s1, scene.champ, scene.element), son.champ, son.element);
	s1 = {...s1, sfx: {...s1.sfx, enabled: true}};
	r = await call('PUT', '/api/reels/script1/script', {styleScenes: s1.styleScenes, sfx: s1.sfx});
	disque = JSON.parse(fs.readFileSync(B('projects/script1/reels/script.json'), 'utf8'));
	ok(r.status === 200 && scene.champ === 'styleScenes' && disque.styleScenes[0].id === scene.element.id && disque.sfx.enabled === true && !vuAvant.ok,
		`Tech : scene ${scene.element.kind} en tete, bruitages actives (avant : « ${vuAvant.pourquoi} ») : ${r.status}`);
	// un element mal forme (fabrique a la main) reste refuse : la banque ne contourne pas la validation
	r = await call('PUT', '/api/reels/script2/script', {vectors: [{...reel.vectors[0], asset: '../../cles.svg'}]});
	ok(r.status === 400, `vecteur avec « .. » refuse : ${r.status} « ${r.data?.error} »`);
	r = await call('PUT', '/api/reels/script2/script', {sfx: {...reel.sfx, extra: [{t: 1, name: 'sfx/../../x.wav'}]}});
	ok(r.status === 400, `bruitage avec « .. » refuse : ${r.status}`);
} catch (e) {
	fails++;
	console.log('ECHEC', e?.stack ?? e);
} finally {
	console.log(`\n${count - fails}/${count} verifications serveur (banque) reussies`);
	if (arg('--garder')) {
		console.log(`SERVEUR=${BASE} (Ctrl+C pour arreter ; jonctions retirees a l'arret)`);
		process.on('SIGINT', () => (fin(), process.exit(0)));
		process.on('SIGTERM', () => (fin(), process.exit(0)));
	} else {
		fin();
		process.exitCode = fails ? 1 : 0;
	}
}
