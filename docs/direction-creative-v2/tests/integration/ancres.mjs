// Aide du test d'integration (test-integration.py) : calculs de remotion/src/timeline.ts LUI-MEME (Node l'execute directement).
//   node ancres.mjs <reel-avant.json> <reel-apres.json>
// -> une ligne JSON : {notes: [{id, avant, relu, apres}] (image de chaque note : dans le reel, apres relecture du fichier,
//    apres les passes automatiques), alignement: {format: ecart max} (dessins : prise -> image -> prise, 4 formats),
//    pixel: {format: [x, y]} (ou tombe dans l'image le 1er point du 1er dessin)}.
//   node ancres.mjs --points <reel.json> <t>   -> {id: points de l'image 0..1} des dessins visibles a t (temoin de l'export)
import fs from 'node:fs';
import {annotationOutput, annotationWindow, outputToSource, resolveAnchor, sourceRectAt} from '../../../../remotion/src/timeline.ts';

if (process.argv[2] === '--points') {
	const reel = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
	const t = Number(process.argv[4]);
	const out = {};
	for (const a of reel.annotations ?? []) {
		const w = annotationWindow(reel, a);
		if (w && t >= w[0] && t < w[1]) out[a.id] = {outil: a.outil, epaisseur: a.epaisseur, points: annotationOutput(reel, a, t)};
	}
	console.log(JSON.stringify(out));
	process.exit(0);
}
const [fa, fb] = process.argv.slice(2);
const avant = JSON.parse(fs.readFileSync(fa, 'utf8'));
// « fermeture et reouverture » : le reel est ecrit sur le disque puis relu, comme le serveur le sert a l'interface
fs.writeFileSync(`${fa}.relu.json`, JSON.stringify(avant, null, 1));
const relu = JSON.parse(fs.readFileSync(`${fa}.relu.json`, 'utf8'));
const apres = JSON.parse(fs.readFileSync(fb, 'utf8'));
const image = (reel, n) => {
	const p = resolveAnchor(reel, n.anchor);
	return p ? Math.round(p.t * reel.fps) : null;
};
const notes = (avant.notes ?? []).map((n) => ({id: n.id, avant: image(avant, n), relu: image(relu, relu.notes.find((x) => x.id === n.id)),
	apres: image(apres, (apres.notes ?? []).find((x) => x.id === n.id) ?? n)}));
const FORMATS = {'9:16': [1080, 1920], '16:9': [1920, 1080], '4:5': [1080, 1350], '1:1': [1080, 1080]};
const alignement = {};
const pixel = {};
for (const [f, [w, h]] of Object.entries(FORMATS)) {
	const r = {...apres, width: w, height: h};
	let e = 0;
	for (const a of r.annotations ?? []) {
		const win = annotationWindow(r, a);
		if (!win) continue;
		for (const t of [win[0], (win[0] + win[1]) / 2]) {
			const pts = annotationOutput(r, a, t);
			const rect = sourceRectAt(r, t);
			if (!pts || !rect) continue;
			pts.forEach((p, i) => {
				const [u, v] = outputToSource(rect, p);
				e = Math.max(e, Math.abs(u - a.points[i][0]), Math.abs(v - a.points[i][1]));
			});
			if (a === r.annotations[0] && t === win[0]) pixel[f] = pts[0].map((x, k) => Math.round(x * (k ? h : w)));
		}
	}
	alignement[f] = e;
}
console.log(JSON.stringify({notes, alignement, pixel}));
