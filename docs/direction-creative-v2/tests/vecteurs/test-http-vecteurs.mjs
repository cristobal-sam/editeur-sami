// Vecteurs par le serveur, sur une COPIE ISOLEE (port 18811), jamais sur le vrai dossier ni le vrai serveur 8790 :
// fichiers de la banque servis, sauvegarde (PUT), relecture apres actualisation (open), changement de style par le moteur
// (POST /template) : les couleurs choisies a la main restent, les couleurs « charte » suivent le nouveau style.
//   node docs/direction-creative-v2/tests/vecteurs/test-http-vecteurs.mjs [--garder]
//   --garder : laisse le serveur de test ouvert (http://127.0.0.1:18811) pour un essai a la main ; Ctrl+C l'arrete.
// Bac : runtime/cache/tmp/dcv2-vecteurs/serveur-<hasard>/ (copies ; jonction EN LECTURE vers runtime/venv, retiree a la fin
// avec rmdir — le lien seulement, jamais sa cible).
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {ROOT, TMP, chargerVecteurs} from './charger.mjs';

const V = await chargerVecteurs();
const PORT = 18811;
const BASE = `http://127.0.0.1:${PORT}`;
const GARDER = process.argv.includes('--garder');
fs.mkdirSync(TMP, {recursive: true});
const box = fs.mkdtempSync(path.join(TMP, 'serveur-'));
const B = (...p) => path.join(box, ...p);
// projects/<video> : copie figee des tests (fixtures/projects), jamais le projet vivant de l'utilisateur
const copy = (rel) => fs.cpSync(path.join(/^projects\/(?!_)/.test(rel) ? path.join(ROOT, 'docs/direction-creative-v2/tests/fixtures') : ROOT, rel), B(rel), {recursive: true});
for (const d of ['app/ui', 'projects/script2/reels', 'runtime/cache/tmp', 'media/entree', 'remotion/src', 'assets/banque']) fs.mkdirSync(B(d), {recursive: true});
for (const f of ['app/server.mjs', 'app/ui/index.html', 'app/ui/styles.css', 'app/dist', 'styles', 'engine/editeur', 'remotion/segments.mjs',
	'remotion/src/timeline.ts', 'remotion/src/types.ts', 'projects/script2/project.json', 'projects/script2/reels/script.json', 'assets/banque/vecteurs']) copy(f);
fs.symlinkSync(path.join(ROOT, 'runtime/venv'), B('runtime/venv'), 'junction');
const REEL = B('projects/script2/reels/script.json');
const disk = () => JSON.parse(fs.readFileSync(REEL, 'utf8'));

let fails = 0;
let count = 0;
const ok = (cond, msg) => {
	count++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${msg}`);
	if (!cond) fails++;
};
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const call = async (method, route, body) => {
	const r = await fetch(BASE + route, {method, headers: {'content-type': 'application/json', origin: BASE}, body: body === undefined ? undefined : JSON.stringify(body)});
	const type = r.headers.get('content-type') || '';
	const data = type.includes('json') ? await r.json().catch(() => null) : Buffer.from(await r.arrayBuffer());
	return {status: r.status, data, type};
};
const log = fs.openSync(B('serveur.log'), 'w');
const child = spawn(process.execPath, [B('app/server.mjs')], {env: {...process.env, EDITEUR_PORT: String(PORT), EDITEUR_LLM: '0'}, stdio: ['ignore', log, log], windowsHide: true});
const nettoyer = () => {
	child.kill();
	try {
		fs.rmdirSync(B('runtime/venv')); // la jonction seulement
	} catch (e) {
		console.log(`Jonction a retirer a la main (rmdir) : ${B('runtime/venv')} (${e.message})`);
	}
};
const MAIN = {principale: '#00C2FF', secondaire: '#0A2A66', contour: '#FFFFFF'};
const NUL = {principale: null, secondaire: null, contour: null};
const vec = (id, nom, at, o = {}) => ({id, asset: `banque/vecteurs/${nom}.svg`, at, duration: 2.5, x: 0.5, y: 0.35, w: 0.35, rotation: 0, opacite: 1,
	couleurs: {...NUL}, couleursManuelles: false, anim: {entree: 'pop', sortie: 'fondu'}, manual: true, ...o});
try {
	for (let k = 0; k < 80; k++) {
		try {
			await fetch(`${BASE}/api/reels`);
			break;
		} catch {
			await sleep(250);
		}
	}
	// 1. la banque est servie (apercu et export lisent le meme fichier)
	let r = await call('GET', '/assets/banque/vecteurs/coeur.svg');
	ok(r.status === 200 && r.type.startsWith('image/svg+xml') && r.data.equals(fs.readFileSync(path.join(ROOT, 'assets/banque/vecteurs/coeur.svg'))),
		`SVG servi : ${r.status} ${r.type}`);
	r = await call('GET', '/assets/banque/vecteurs/coeur.json');
	ok(r.status === 200 && r.data?.nom === 'Cœur' && r.data?.categorie === 'fête', `fiche servie, accents intacts : « ${r.data?.nom} » (${r.data?.categorie})`);

	// 2. sauvegarde puis relecture (= actualiser la page)
	const vecteurs = [
		vec('v-manuel', 'explosion', 20, {couleurs: {...MAIN}, couleursManuelles: true, rotation: -12, w: 0.42, raison: 'Ajouté à la main : Explosion de BD'}),
		vec('v-charte', 'etoile', 24, {raison: 'Ajouté à la main : Étoile'}),
		vec('v-verrou', 'fleche-courbe', 28, {locked: true, anim: {entree: 'trace', sortie: 'trace'}}),
	];
	r = await call('PUT', '/api/reels/script2/script', {vectors: vecteurs});
	ok(r.status === 200, `PUT de 3 vecteurs : ${r.status} ${r.data?.error ?? ''}`);
	ok(eq(disk().vectors, vecteurs), 'vecteurs enregistres sur le disque a l\'identique');
	r = await call('GET', '/api/reels/script2/script/open');
	ok(r.status === 200 && eq(r.data?.reel?.vectors, vecteurs), 'apres actualisation (open) : vecteurs identiques');
	ok(eq(V.vectorColors(r.data.reel, r.data.reel.vectors[0]), MAIN), 'apres actualisation : couleurs choisies a la main affichees');
	r = await call('PUT', '/api/reels/script2/script', {style: disk().style});
	ok(r.status === 200 && eq(disk().vectors, vecteurs), 'un PUT sans « vectors » ne les touche pas');

	// 3. changement de style par le moteur (comme un clic sur un style)
	const attendu = {'tech-application': '#86B7FF', 'reel-impact': '#FFD400', documentaire: '#E0D4BE'};
	for (const style of ['tech-application', 'documentaire', 'reel-impact']) {
		const t0 = Date.now();
		r = await call('POST', '/api/reels/script2/script/template', {id: style});
		const reel = r.data?.reel;
		ok(r.status === 200 && reel?.template === style, `style « ${style} » : ${r.status} en ${((Date.now() - t0) / 1000).toFixed(1)} s ${r.data?.error ?? ''}`);
		if (!reel) continue;
		ok(eq(reel.vectors, vecteurs) && eq(disk().vectors, vecteurs), `${style} : les 3 vecteurs retouches / verrouille sont intacts (disque et interface)`);
		ok(eq(V.vectorColors(reel, reel.vectors[0]), MAIN), `${style} : couleurs choisies a la main gardees`);
		const c = V.vectorColors(reel, reel.vectors[1]);
		ok(c.principale === attendu[style], `${style} : vecteur « couleurs de la charte » recolore par le style (${c.principale})`);
		ok(V.vectorColors(reel, reel.vectors[2]).principale === attendu[style], `${style} : vecteur verrouille (couleurs automatiques) recolore aussi`);
	}
	r = await call('GET', '/api/reels/script2/script/open');
	ok(eq(r.data?.reel?.vectors, vecteurs), 'relecture finale : rien n\'a bouge');

	// 4. refus clair d'une couleur invalide, fichier intact
	const avant = fs.readFileSync(REEL);
	r = await call('PUT', '/api/reels/script2/script', {vectors: [{...vecteurs[0], couleurs: {...MAIN, principale: 'rouge'}}]});
	ok(r.status === 400 && /couleur/.test(r.data?.error ?? ''), `couleur invalide refusee : ${r.status} « ${r.data?.error} »`);
	ok(fs.readFileSync(REEL).equals(avant), 'apres le refus : montage intact');
} finally {
	if (!GARDER) nettoyer();
}
console.log(`\n${count - fails}/${count} verifications serveur (vecteurs) reussies (bac : ${box})`);
if (GARDER) {
	console.log(`Serveur de test ouvert : ${BASE} (Ctrl+C pour l'arreter)`);
	const fin = () => {
		nettoyer();
		process.exit(0);
	};
	process.on('SIGINT', fin);
	process.on('SIGTERM', fin);
	setInterval(() => {
		if (fs.existsSync(B('ARRETER'))) fin();
	}, 1000);
} else process.exit(fails ? 1 : 0);
