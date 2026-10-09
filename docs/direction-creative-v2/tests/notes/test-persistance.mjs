// Persistance des notes et dessins par le VRAI serveur, sur une COPIE ISOLEE (port 18803), jamais sur le vrai dossier.
//   node docs/direction-creative-v2/tests/notes/test-persistance.mjs
// Bac : runtime/cache/tmp/notes-agent/persistance-XXXXXX/ (copies : app/server.mjs, styles, moteur, projects/script1 ;
// aucune jonction). Notes et dessins crees par le VRAI revue.tsx, enregistres comme l'interface (PUT de tous les champs
// EDITABLE), relus, serveur arrete puis relance (fermeture/reouverture de l'outil), changement de format, coupe de mots.
// Controle : le serveur d'AVANT la V2 (docs/direction-creative-v2/avant/app-server.mjs, port 18804) perd les notes et
// repond 404 a la sonde (GET /api/v2) : c'est ce que detecte l'avertissement du panneau Notes.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
import {isDeepStrictEqual} from 'node:util';
import * as T from '../../../../remotion/src/timeline.ts';
import {ROOT, bac, bilan, chargerRevue, ok, origine} from './outils.mjs';

const box = bac('persistance');
const R = await chargerRevue(box);
const B = (...p) => path.join(box, ...p);
const REAL_REEL = origine('projects/script1/reels/script.json'); // copie figee (fixtures/projects)
const sha = (f) => crypto.createHash('sha1').update(fs.readFileSync(f)).digest('hex');
const avantReel = sha(REAL_REEL);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const monter = (dir, serveur) => {
	const D = (...p) => path.join(dir, ...p);
	for (const d of ['app/ui', 'app/dist', 'projects/script1/reels', 'runtime/cache/tmp', 'media/entree', 'engine']) fs.mkdirSync(D(d), {recursive: true});
	fs.copyFileSync(serveur, D('app/server.mjs'));
	for (const f of ['app/ui/index.html', 'app/ui/styles.css', 'app/dist/app.js', 'projects/script1/project.json', 'projects/script1/reels/script.json']) fs.copyFileSync(origine(f), D(f));
	fs.cpSync(path.join(ROOT, 'styles'), D('styles'), {recursive: true});
	fs.cpSync(path.join(ROOT, 'engine/editeur'), D('engine/editeur'), {recursive: true});
};
monter(box, path.join(ROOT, 'app/server.mjs'));
const VIEUX = B('ancien-serveur');
monter(VIEUX, path.join(ROOT, 'docs/direction-creative-v2/avant/app-server.mjs'));

const demarrer = async (dir, port) => {
	const log = fs.openSync(path.join(dir, `serveur-${Date.now()}.log`), 'w');
	const child = spawn(process.execPath, [path.join(dir, 'app/server.mjs')], {env: {...process.env, EDITEUR_PORT: String(port)}, stdio: ['ignore', log, log], windowsHide: true});
	for (let k = 0; k < 80; k++) {
		try {
			await fetch(`http://127.0.0.1:${port}/api/reels`);
			return child;
		} catch {
			await sleep(250);
		}
	}
	throw new Error(`serveur de test ${port} injoignable`);
};
const arreter = async (child) => {
	if (!child || child.exitCode !== null) return;
	const fin = new Promise((r) => child.once('exit', r));
	child.kill();
	await Promise.race([fin, sleep(5000)]);
};
const client = (port) => async (method, route, body) => {
	const r = await fetch(`http://127.0.0.1:${port}${route}`, {method, headers: {'content-type': 'application/json', origin: `http://127.0.0.1:${port}`},
		body: body === undefined ? undefined : JSON.stringify(body)});
	let data = null;
	try {
		data = await r.json();
	} catch {}
	return {status: r.status, data};
};
// memes champs que la sauvegarde automatique de App.tsx
const EDITABLE = ['style', 'zoom', 'banner', 'flash', 'progress', 'effects', 'emoji', 'music', 'sfx', 'audio', 'intro', 'clips', 'broll', 'graphics', 'brand', 'aiMode',
	'suggestions', 'label', 'design', 'styleScenes', 'notes', 'annotations', 'vectors', 'choreography', 'creativePlan'];
const corps = (reel) => ({...Object.fromEntries(EDITABLE.map((k) => [k, reel[k]])), format: `${reel.width === 1920 ? '16:9' : reel.height === 1350 ? '4:5' : reel.width === reel.height ? '1:1' : '9:16'}`});

let serveur = null;
let ancien = null;
try {
	const PORT = 18803;
	const api = client(PORT);
	serveur = await demarrer(box, PORT);
	const ouvrir = async () => (await api('GET', '/api/reels/script1/script/open')).data.reel;
	const r0 = await ouvrir();
	ok(!r0.notes && !r0.annotations, 'copie du reel ouverte : aucune note ni dessin au depart');
	const fps = r0.fps;

	// notes et dessins crees par le vrai code de l'interface
	const n1 = R.newNote(r0, 5, 'Coupe plus tôt ici — « bof » ; ça traîne', 'Sami', '9:16');
	const n2 = {...R.newNote(r0, 15.5, 'Logo trop petit 🎯 : mets-le à droite', 'Sami', '9:16'), statut: 'traitee', end: 17, endAnchor: T.anchorAtTime(r0, 17)};
	const n3 = {...R.newNote(r0, 40, 'Élément à revoir, déjà validé par le client. '.repeat(60).slice(0, 2000), 'Équipe Québec', '9:16'), statut: 'resolue'};
	const trait = (t, outil, n, extra = {}) => ({...R.newAnnotation(r0, t, {outil, couleur: '#FF3B30', epaisseur: 8, duree: 2, noteId: n?.id},
		Array.from({length: n === undefined ? 2000 : 300}, (_, i) => [0.2 + (i % 300) / 600, 0.3 + 0.1 * Math.sin(i / 20)])), ...extra});
	const a1 = trait(5, 'crayon', n1);
	const a2 = {...R.newAnnotation(r0, 15.5, {outil: 'fleche', couleur: '#0A84FF', epaisseur: 10, duree: 3, noteId: n2.id}, [[0.2, 0.2], [0.5, 0.4]])};
	const a3 = {...R.newAnnotation(r0, 40, {outil: 'cercle', couleur: '#34C759CC', epaisseur: 6, duree: 2}, [[0.3, 0.2], [0.7, 0.45]])};
	const a4 = trait(41, 'surligneur', undefined, {masquee: true});
	const notes = [n1, n2, n3];
	const annotations = [a1, a2, a3, a4];
	ok(a4.points.length === 2000 && n3.text.length === 2000, 'jeu d\'essai : 3 notes (accents, emoji, 2000 caracteres, 3 statuts, une plage), 4 dessins (4 outils, 2000 points, un masque)');
	const put = await api('PUT', '/api/reels/script1/script', corps({...r0, notes, annotations}));
	ok(put.status === 200, `sauvegarde comme l'interface (PUT de tous les champs) : ${put.status} ${JSON.stringify(put.data)}`);

	const r1 = await ouvrir();
	ok(isDeepStrictEqual(r1.notes, notes) && isDeepStrictEqual(r1.annotations, annotations), 'relecture : notes et dessins identiques (texte, accents, emoji, points, liens, masque)');
	ok(isDeepStrictEqual(r1.clips, r0.clips) && r1.width === 1080, 'relecture : montage et format inchanges');
	const images = (r) => notes.map((n) => {
		const p = R.placeNote(r, r.notes.find((x) => x.id === n.id));
		return p ? Math.round(p.t * fps) : null;
	});
	const attendu = notes.map((n) => Math.round(n.t * fps));
	ok(isDeepStrictEqual(images(r1), attendu), `retour a l'image exacte apres relecture : images ${images(r1).join(', ')}`);

	// fermeture et reouverture de l'outil : serveur arrete puis relance
	await arreter(serveur);
	serveur = await demarrer(box, PORT);
	const r2 = await ouvrir();
	ok(isDeepStrictEqual(r2.notes, notes) && isDeepStrictEqual(r2.annotations, annotations), 'serveur arrete puis relance : notes et dessins toujours la, identiques');
	ok(isDeepStrictEqual(images(r2), attendu), `apres reouverture, chaque note revient a la meme image (${notes.map((n) => R.timecode(n.t, fps)).join(', ')})`);
	const spans = new Map(r2.annotations.map((a) => [a.id, R.annotationSpan(r2, a)]));
	const outils = (t) => R.visibleDrawings(r2, r2.annotations, spans, t).map((v) => v.a.outil).join('+') || 'rien';
	ok(outils(5) === 'crayon' && outils(41) === 'cercle' && outils(43) === 'rien',
		`apres reouverture : 00:05:00 -> ${outils(5)} ; 00:41:00 -> ${outils(41)} (surligneur masque absent) ; 00:43:00 -> ${outils(43)}`);

	// changement de format (bouton 16:9 de l'interface) : points de la prise inchanges, dessin toujours affiche
	ok((await api('PUT', '/api/reels/script1/script', corps({...r2, width: 1920, height: 1080}))).status === 200, 'passage en 16:9 enregistre');
	const r3 = await ouvrir();
	const s3 = new Map(r3.annotations.map((a) => [a.id, R.annotationSpan(r3, a)]));
	ok(r3.width === 1920 && isDeepStrictEqual(r3.annotations, annotations) && R.visibleDrawings(r3, r3.annotations, s3, 15.5).length === 1,
		'16:9 relu : memes points de la prise, la fleche est affichee a 00:15:15');

	// coupe de mots avant les notes (comme la retouche du texte) : chaque note suit son mot ou devient orpheline
	const coupe = structuredClone(r3);
	coupe.clips[0].words.slice(2, 8).forEach((w) => (w.cut = true));
	ok((await api('PUT', '/api/reels/script1/script', corps({...coupe, width: 1080, height: 1920}))).status === 200, 'coupe de 6 mots du 1er plan enregistree (retour en 9:16)');
	const r4 = await ouvrir();
	const mots = T.timedWords(r0);
	const suit = notes.every((n) => {
		const w = [...mots].reverse().find((x) => x.outStart <= n.t + 1e-9);
		const p = R.placeNote(r4, r4.notes.find((x) => x.id === n.id));
		const w2 = T.timedWords(r4).find((x) => x.clip === w.clip && x.index === w.index);
		console.log(`     note ${R.timecode(n.t, fps)} -> ${p ? R.timecode(p.t, fps) : 'orpheline'} (mot « ${w.w} »${w2 ? '' : ', coupe'})`);
		return w2 ? p && Math.abs((p.t - w2.outStart) - (n.t - w.outStart)) <= 1 / fps + 1e-9 : p === null;
	});
	ok(suit, 'apres la coupe relue : chaque note est toujours sur son mot (ou « passage retiré » si son mot est coupe)');

	// « Transformer en élément graphique » : le vecteur produit est accepte par la validation stricte du serveur
	const vecs = [R.toVector(r4, r4.annotations.find((a) => a.outil === 'fleche'), {entree: 'glisse-gauche', sortie: 'fondu'}), R.toVector(r4, r4.annotations.find((a) => a.outil === 'cercle'))];
	const putV = await api('PUT', '/api/reels/script1/script', corps({...r4, vectors: vecs, annotations: r4.annotations.filter((a) => !['fleche', 'cercle'].includes(a.outil))}));
	const r5 = await ouvrir();
	ok(putV.status === 200 && isDeepStrictEqual(r5.vectors, vecs) && r5.annotations.length === 2,
		`fleche et cercle transformes en elements graphiques : PUT ${putV.status}${putV.status === 200 ? '' : ` ${JSON.stringify(putV.data)}`}, 2 vecteurs relus a l'identique, dessins retires`);

	// sonde du panneau (GET /api/v2) : serveur V2 -> 200 (pas d'avertissement)
	const sonde = await fetch(`http://127.0.0.1:${PORT}/api/v2`);
	ok(sonde.status === 200 && (await sonde.json()).v2 === true, `sonde du panneau sur le serveur V2 : ${sonde.status} (les notes sont enregistrees, pas d'avertissement)`);
	ok((await api('PUT', '/api/reels/script1/script', {notes: [], annotations: [], vectors: []})).status === 200 && !(await ouvrir()).notes?.length, 'tout supprimer : listes vides enregistrees');

	// controle : serveur d'avant la V2 -> les notes sont perdues, la sonde repond 404 (avertissement affiche)
	const P2 = 18804;
	const api2 = client(P2);
	ancien = await demarrer(VIEUX, P2);
	const avant = (await api2('GET', '/api/reels/script1/script/open')).data.reel;
	const put2 = await api2('PUT', '/api/reels/script1/script', corps({...avant, notes, annotations}));
	const relu2 = (await api2('GET', '/api/reels/script1/script/open')).data.reel;
	const sonde2 = await fetch(`http://127.0.0.1:${P2}/api/v2`);
	ok(put2.status === 200 && !relu2.notes && sonde2.status === 404, `serveur d'avant la V2 : PUT ${put2.status} mais notes perdues a la relecture, sonde ${sonde2.status} -> le panneau affiche l'avertissement`);
} finally {
	await arreter(serveur);
	await arreter(ancien);
}
ok(sha(REAL_REEL) === avantReel, 'reel fige fixtures/projects/script1/reels/script.json inchange');
console.log(`Bac conserve : ${box}`);
bilan('notes (persistance, serveur isole)');
