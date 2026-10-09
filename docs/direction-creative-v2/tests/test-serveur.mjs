// Tests HTTP des champs V2 et des nouvelles routes, sur une COPIE ISOLEE du serveur (port 18797), jamais sur le vrai dossier.
//   node docs/direction-creative-v2/tests/test-serveur.mjs
// Bac : runtime/cache/tmp/dcv2-architecte/serveur-<hasard>/ (copies : app/server.mjs, styles, moteur, remotion/src + segments.mjs,
// projects/script1 ; IA locale coupee (EDITEUR_LLM=0) ;
// jonction EN LECTURE vers runtime/venv, retiree a la fin avec rmdir — le lien seulement, jamais sa cible).
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../..');
const FIX = path.join(REAL, 'docs/direction-creative-v2/tests/fixtures'); // donnees figees des tests (jamais projects/)
const origine = (rel) => path.join(/^projects\/(?!_)/.test(rel) ? FIX : REAL, rel); // projects/<video> : copie figee ; _cache, assets... : dossier reel
const PORT = 18797;
const BASE = `http://127.0.0.1:${PORT}`;
const box = fs.mkdtempSync(path.join(REAL, 'runtime/cache/tmp/dcv2-architecte/serveur-'));
const B = (...p) => path.join(box, ...p);
const copy = (rel, to = rel) => fs.cpSync(origine(rel), B(to), {recursive: true});
for (const d of ['app/ui', 'projects/script1/reels', 'runtime/cache/tmp', 'media/entree', 'assets/banque/apercus', 'engine', 'remotion']) fs.mkdirSync(B(d), {recursive: true});
copy('app/server.mjs');
copy('app/ui/index.html');
copy('app/ui/styles.css');
copy('styles');
copy('engine/editeur');
// calcul du montage (montage.compute -> node remotion/segments.mjs) : passage et choregraphie en ont besoin
copy('remotion/src');
copy('remotion/segments.mjs');
copy('projects/script1/project.json');
copy('projects/script1/reels/script.json');
fs.symlinkSync(path.join(REAL, 'runtime/venv'), B('runtime/venv'), 'junction');
copy('assets/overlays/grain.png', 'assets/banque/apercus/essai.png');
const REEL = B('projects/script1/reels/script.json');
const hash = () => crypto.createHash('sha1').update(fs.readFileSync(REEL)).digest('hex');
const disk = () => JSON.parse(fs.readFileSync(REEL, 'utf8'));

let fails = 0;
let count = 0;
const ok = (cond, msg) => {
	count++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${msg}`);
	if (!cond) fails++;
};
const call = async (method, route, body, origin = BASE) => {
	const headers = {'content-type': 'application/json'};
	if (origin) headers.origin = origin;
	const init = {method, headers, body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body)};
	let r;
	try {
		r = await fetch(BASE + route, init);
	} catch {
		// connexion fermee par le serveur apres un refus en plein envoi (413) : on reessaie sur une nouvelle connexion
		await sleep(200);
		r = await fetch(BASE + route, init);
	}
	let data = null;
	const type = r.headers.get('content-type') || '';
	try {
		data = type.includes('json') ? await r.json() : Buffer.from(await r.arrayBuffer());
	} catch {}
	return {status: r.status, data, type};
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const job = async (id) => {
	for (let k = 0; k < 120; k++) {
		const j = (await call('GET', `/api/jobs/${id}`)).data;
		if (j && j.status !== 'running' && j.status !== 'queued') return j;
		await sleep(500);
	}
	return null;
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
	const real = disk();
	const c0 = real.clips[0];
	const anchor = {clip: c0.id, src: c0.in + 1, sig: c0.signature, source: c0.source, image: c0.source};
	const note = (i, text = 'Couper la pause ici') => ({id: `n${i}`, t: 1, anchor, text, statut: 'ouverte', auteur: 'Sami', cree: '2026-09-30T20:00:00',
		modifie: '2026-09-30T20:00:00', contexte: {titre: 'Vidéo 1', style: real.template, format: '9:16', duree: 70}});
	const dessin = (i, n = 3) => ({id: `a${i}`, noteId: 'n0', outil: 'fleche', couleur: '#FF3355', epaisseur: 6,
		points: Array.from({length: n}, (_, k) => [0.3 + k / (n * 3), 0.4]), anchor, duree: 2});
	const vecteur = {id: 'v1', asset: 'banque/vecteurs/fleche.svg', at: 3, duration: 2, x: 0.5, y: 0.3, w: 0.3, rotation: 0, opacite: 1,
		couleurs: {principale: '#FFD400', secondaire: null, contour: '#000000'}, couleursManuelles: false, anim: {entree: 'pop', sortie: 'fondu'}, locked: true};
	const mouvement = {id: 'q1', cible: {type: 'vector', id: 'v1'}, at: 3, duree: 2, entree: {type: 'glisse', direction: 'gauche', duree: 0.3, courbe: 'douce'},
		sortie: {type: 'fondu', duree: 0.2, courbe: 'lineaire'}, sync: {sur: 'mot', ref: `${c0.id}:3`}, raison: 'entre avec le mot', auto: true, locked: false};
	const put = (body) => call('PUT', '/api/reels/script1/script', body);

	// 1. ancien appel (sans champ V2) : fonctionne et n'ajoute rien
	let r = await put({style: real.style, format: '9:16'});
	ok(r.status === 200, `PUT sans champ V2 : ${r.status}`);
	ok(!('notes' in disk()) && !('vectors' in disk()), 'aucun champ V2 ajoute a un ancien reel');

	// 2. champs V2 valides
	r = await put({notes: [note(0)], annotations: [dessin(0)], vectors: [vecteur], choreography: {version: 1, cues: [mouvement]},
		creativePlan: {...real.creativePlan, locked: true}, banner: {...real.banner, locked: true},
		sfx: {...real.sfx, extra: [{t: 4, name: 'sfx/kenney/impact-sounds/Audio/impactGeneric_light_000.ogg', gain: 0.8, locked: true, id: 's1'}]}});
	ok(r.status === 200, `PUT notes + dessins + vecteur + mouvement + verrous : ${r.status} ${r.data?.error ?? ''}`);
	let d = disk();
	ok(d.notes?.[0]?.text === 'Couper la pause ici' && d.annotations?.[0]?.points.length === 3 && d.vectors?.[0]?.locked === true
		&& d.choreography?.cues?.[0]?.id === 'q1' && d.creativePlan?.locked === true && d.banner?.locked === true, 'tout est enregistre sur le disque');
	const o = (await call('GET', '/api/reels/script1/script/open')).data;
	ok(o.reel.notes?.[0]?.id === 'n0' && o.reel.annotations?.length === 1, 'relecture (open) : notes et dessins revenus');
	r = await put({style: real.style});
	ok(r.status === 200 && disk().notes?.length === 1, 'un PUT sans « notes » ne les efface pas');

	// 3. UTF-8 : un gros envoi plein d'accents (caracteres coupes entre deux paquets) revient intact
	const accents = 'éàçôœ«»—'.repeat(240).slice(0, 1990);
	const beaucoup = Array.from({length: 400}, (_, i) => note(i, `${i} ${accents}`));
	r = await put({notes: beaucoup});
	ok(r.status === 200 && disk().notes.length === 400 && disk().notes.every((n, i) => n.text === `${i} ${accents}`),
		`400 notes accentuees (${Math.round(JSON.stringify(beaucoup).length / 1024)} Ko) : aucun caractere abime`);

	// 4. refus clairs, fichier inchange
	const before = hash();
	const bad = [
		[{notes: [{...note(1), couleur: 'rouge'}]}, 'champ inconnu', 'note : champ inconnu'],
		[{notes: [{...note(1), text: 'x'.repeat(2001)}]}, '2000', 'note de 2001 caracteres'],
		[{notes: Array.from({length: 501}, (_, i) => note(i))}, '500', '501 notes'],
		[{notes: [note(1), note(1)]}, 'double', 'deux notes avec le meme id'],
		[{notes: [{...note(1), statut: 'faite'}]}, 'inconnue', 'statut inconnu'],
		[{notes: [{...note(1), anchor: {clip: c0.id, sig: 'x'}}]}, 'src', 'ancre sans temps'],
		[{notes: [{...note(1), meta: {x: 'y'.repeat(3000)}}]}, 'meta', 'meta de plus de 2 Ko'],
		[{annotations: [dessin(1, 2001)]}, '2000', 'dessin de 2001 points'],
		[{annotations: [{...dessin(1), outil: 'pinceau'}]}, 'inconnue', 'outil inconnu'],
		[{annotations: [{...dessin(1), couleur: 'red'}]}, 'couleur', 'couleur invalide'],
		[{annotations: [{...dessin(1), points: [[0.5, 99]]}]}, 'point', 'point hors limites'],
		[{vectors: [{...vecteur, asset: 'banque/../../cles-api.env'}]}, 'ressource', 'vecteur hors de la banque'],
		[{vectors: [{...vecteur, opacite: 2}]}, 'opacité', 'opacite 2'],
		[{vectors: [{...vecteur, secret: 1}]}, 'champ inconnu', 'vecteur : champ inconnu'],
		[{choreography: {version: 1, cues: [{...mouvement, cible: {type: 'musique', id: 'x'}}]}}, 'inconnue', 'cible de mouvement inconnue'],
		[{choreography: {version: 1, cues: [{...mouvement, entree: {...mouvement.entree, courbe: 'folle'}}]}}, 'inconnue', 'courbe inconnue'],
		[{choreography: {cues: []}}, 'version', 'choregraphie sans version'],
		[{sfx: {...real.sfx, extra: [{t: 1, name: '../../cles-api.env'}]}}, 'fichier', 'bruitage hors de assets'],
		[{graphics: [{id: 'g', kind: 'logo', at: 1, duration: 1, props: {}, locked: 'oui'}]}, 'vrai/faux', 'verrou non booleen'],
		[{creativePlan: 'rien'}, 'Plan', 'plan creatif invalide'],
	];
	for (const [body, word, label] of bad) {
		r = await put(body);
		ok(r.status === 400 && String(r.data?.error).includes(word), `refus : ${label} -> ${r.status} « ${r.data?.error} »`);
	}
	try {
		r = await put('{"notes": [' + '"x",'.repeat(6_000_000) + '"x"]}');
		ok(r.status === 413 && /volumineux/.test(r.data?.error), `envoi de plus de 20 Mo : ${r.status} « ${r.data?.error} »`);
	} catch (e) {
		// le serveur peut couper la connexion avant la fin de l'envoi : c'est aussi un refus
		ok(true, `envoi de plus de 20 Mo : connexion coupee par le serveur (${e.cause?.code ?? e.message})`);
	}
	ok(hash() === before, 'apres tous les refus : le montage sur le disque est intact');

	// 5. origine exacte pour les POST (et PUT)
	for (const orig of [null, 'http://localhost:18797', 'http://127.0.0.1:8790', `${BASE}.evil.com`]) {
		const p1 = await call('POST', '/api/reels/script1/script/passage', {debut: 1, fin: 3}, orig);
		const p2 = await call('POST', '/api/reels/script1/script/choregraphie', {}, orig);
		const p3 = await call('PUT', '/api/reels/script1/script', {notes: []}, orig);
		ok(p1.status === 403 && p2.status === 403 && p3.status === 403, `origine ${orig ?? '(aucune)'} refusee : ${p1.status}/${p2.status}/${p3.status}`);
	}
	ok(hash() === before, 'apres les refus d\'origine : montage intact');

	// 6. routes V2 livrees : sonde, passage, choregraphie, banque
	r = await call('GET', '/api/v2');
	ok(r.status === 200 && r.data?.v2 === true, `sonde GET /api/v2 : ${r.status}`);
	r = await call('POST', '/api/reels/script1/script/passage', {debut: 5, fin: 4});
	ok(r.status === 400, `passage a l'envers : ${r.status} « ${r.data?.error} »`);
	const versions = () => (fs.existsSync(B('projects/script1/versions/script')) ? fs.readdirSync(B('projects/script1/versions/script')) : []);
	r = await call('POST', '/api/reels/script1/script/passage', {debut: 12, fin: 18.5});
	ok(r.status === 202 && r.data?.id, `passage : tache lancee (${r.status})`);
	let j = await job(r.data.id);
	ok(j?.status === 'done' && typeof j.result?.resume === 'string' && 'modifie' in j.result, `passage : tache terminee « ${j?.result?.resume ?? j?.error} »`);
	ok(versions().some((f) => f.includes('avant refaire le passage')), 'version « avant refaire le passage » gardee');
	r = await call('POST', '/api/reels/script1/script/passage', {debut: 500, fin: 510});
	j = await job(r.data.id);
	ok(j?.status === 'failed' && /après la fin de la vidéo/.test(j.error) && !/Erreur inattendue/.test(j.error), `passage hors de la video : phrase claire « ${j?.error} »`);
	r = await call('POST', '/api/reels/script1/script/choregraphie', {});
	j = await job(r.data.id);
	ok(r.status === 202 && j?.status === 'done' && j.result?.cues >= 0, `choregraphie : tache terminee (${j?.result?.cues ?? j?.error} mouvement(s))`);
	ok(versions().some((f) => f.includes('avant chorégraphie')), 'version « avant chorégraphie » gardee');
	r = await call('GET', '/api/banque?type=son&q=whoosh&format=9:16&intensite=2');
	ok(r.status === 200 && Array.isArray(r.data?.entrees) && r.data.entrees.every((e) => e.type === 'son' && e.intensite === 2), `GET /api/banque : ${r.status}, ${r.data?.total} resultat(s) (bac sans sons : liste vide permise)`);
	r = await call('GET', '/api/banque?type=musique');
	ok(r.status === 400 && /inconnue/.test(r.data?.error), `filtre invalide refuse : « ${r.data?.error} »`);
	r = await call('GET', '/api/banque/apercu/essai');
	ok(r.status === 404, `apercu absent du catalogue construit : ${r.status} « ${r.data?.error} »`);
	fs.writeFileSync(B('assets/banque/catalogue.json'), JSON.stringify({version: 1, entrees: [
		{id: 'essai', type: 'effet', apercu: 'banque/apercus/essai.png'}, {id: 'piege', type: 'effet', apercu: '../app/server.mjs'}]}));
	r = await call('GET', '/api/banque/apercu/essai');
	ok(r.status === 200 && r.type === 'image/png' && r.data.length === fs.statSync(B('assets/banque/apercus/essai.png')).size, `apercu servi depuis assets/ : ${r.status} ${r.type}`);
	r = await call('GET', '/api/banque/apercu/piege');
	ok(r.status === 404, `apercu hors de assets/ refuse : ${r.status}`);
	r = await call('GET', '/api/banque/apercu/inconnu');
	ok(r.status === 404, `apercu inconnu : ${r.status}`);
	fs.writeFileSync(B('assets/banque/catalogue.json'), JSON.stringify({version: 1, entrees: [{id: 'son:essai', type: 'son', apercu: 'banque/apercus/essai.png'}]}));
	r = await call('GET', '/api/banque/apercu/son%3Aessai');
	ok(r.status === 200 && r.type === 'image/png', `apercu avec un « : » encode (%3A) : ${r.status}`);
	r = await call('GET', '/api/banque/apercu/..%2F..%2Fapp%2Fserver.mjs');
	ok(r.status === 404, `apercu avec un chemin encode : ${r.status}`);
	ok(fs.readFileSync(B('app/server.mjs'), 'utf8').includes('validateV2'), 'la copie testee est bien le serveur V2');
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
console.log(`\n${count - fails}/${count} verifications serveur reussies (bac : ${box})`);
process.exit(fails ? 1 : 0);
