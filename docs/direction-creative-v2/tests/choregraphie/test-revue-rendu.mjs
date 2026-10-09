// Revue du groupe « rendu » (vecteurs + choregraphie) : regressions corrigees pendant la revue, sans navigateur.
//   node docs/direction-creative-v2/tests/choregraphie/test-revue-rendu.mjs
// 1. Piste Choregraphie : glisser une scene du style part du temps ACTUEL de la scene (celui que la piste affiche),
//    pas du cache cue.at (qui peut dater d'avant une coupe).
// 2. Vecteurs : un « trace » de la choregraphie sur un dessin SANS trait ne remplace pas l'entree propre du vecteur
//    (avant : l'explosion passait en fondu au lieu de son « pop »).
// Compile par esbuild (remotion/node_modules) dans runtime/cache/tmp/dcv2-choregraphie/. Lecture seule de la copie figee fixtures/projects/script1.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../../..');
const MODULES = path.join(ROOT, 'remotion', 'node_modules');
const esbuild = createRequire(path.join(MODULES, 'x.js'))('esbuild');
const box = path.join(ROOT, 'runtime/cache/tmp/dcv2-choregraphie');
fs.mkdirSync(box, {recursive: true});
const slash = (p) => JSON.stringify(p.replace(/\\/g, '/'));
const entry = path.join(box, `revue-entree-${process.pid}.tsx`);
fs.writeFileSync(entry, `export {moveTarget} from ${slash(path.join(ROOT, 'app/ui/choreo-lane.tsx'))};
export {vectorMotion} from ${slash(path.join(ROOT, 'remotion/src/vectors.tsx'))};
export {targetTimes} from ${slash(path.join(ROOT, 'remotion/src/choreo.tsx'))};
export {timedWords} from ${slash(path.join(ROOT, 'remotion/src/timeline.ts'))};
`);
const out = path.join(box, `revue-${process.pid}.cjs`);
try {
	await esbuild.build({entryPoints: [entry], bundle: true, outfile: out, format: 'cjs', platform: 'node', jsx: 'automatic', nodePaths: [MODULES],
		logLevel: 'error', define: {'process.env.NODE_ENV': '"production"'}});
} finally {
	fs.rmSync(entry, {force: true});
}
const M = createRequire(import.meta.url)(out);
fs.rmSync(out, {force: true});
const {moveTarget, vectorMotion, targetTimes, timedWords} = M;

let fails = 0;
let count = 0;
const ok = (cond, msg) => {
	count++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${msg}`);
	if (!cond) fails++;
};

// ---------- 1. glisser une scene : depuis son temps actuel ----------
const reel = JSON.parse(fs.readFileSync(path.join(HERE, '..', 'fixtures', 'projects/script1/reels/script.json'), 'utf8')); // copie figee
const times = targetTimes(reel);
const scene = (reel.styleScenes ?? []).find((s) => times.has(`design:${s.id}`));
if (!scene) ok(false, 'Video 1 : aucune scene du style affichee (essai sans objet)');
else {
	const now = times.get(`design:${scene.id}`).at;
	// cache du mouvement perime de 3 s (coupe faite plus tot dans la video, chorégraphie pas encore refaite)
	const cue = {id: 'cue-test', cible: {type: 'design', id: scene.id}, at: now + 3, duree: 2.4,
		entree: {type: 'glisse', direction: 'haut', duree: 0.4, courbe: 'douce'}, sortie: {type: 'fondu', direction: null, duree: 0.3, courbe: 'douce'},
		sync: {sur: 'temps', ref: null}, raison: 'essai', auto: true, locked: false};
	const r = {...reel, choreography: {version: 1, cues: [cue]}};
	const next = moveTarget(r, cue, 'move', 0.5);
	const moved = targetTimes(next).get(`design:${scene.id}`).at;
	const words = timedWords(r).filter((w) => !w.hide && w.w.trim()).map((w) => w.outStart);
	const nearest = words.reduce((b, x) => (Math.abs(x - (now + 0.5)) < Math.abs(b - (now + 0.5)) ? x : b), words[0]);
	ok(Math.abs(moved - nearest) < 1e-6, `scene glissee de +0,5 s depuis ${now.toFixed(2)} s : posee a ${moved.toFixed(2)} s (mot le plus proche ${nearest.toFixed(2)} s), pas a ~${(now + 3.5).toFixed(2)} s`);
	const c2 = next.choreography.cues[0];
	ok(Math.abs(c2.at - moved) < 1e-3, `cache du mouvement remis au temps de la scene (${c2.at})`);
	ok(next.styleScenes.find((s) => s.id === scene.id).manual === true, 'scene marquee retouchee (manual)');
	const ended = moveTarget(r, cue, 'end', 0.4);
	ok(Math.abs(ended.choreography.cues[0].at - now) < 1e-3, `raccourcir/allonger : cache « at » = temps actuel (${ended.choreography.cues[0].at})`);
}

// ---------- 2. trace de la choregraphie sur un dessin sans trait ----------
const v = {at: 10, duration: 2, anim: {entree: 'pop', sortie: 'fondu'}};
const traceCue = {id: 'c', cible: {type: 'vector', id: 'v'}, at: 10, duree: 2, entree: {type: 'trace', direction: 'gauche', duree: 0.5, courbe: 'douce'},
	sortie: {type: 'aucune', direction: null, duree: 0, courbe: 'lineaire'}, sync: {sur: 'temps', ref: null}, raison: 'x', auto: true, locked: false};
const frame = {w: 1080, h: 1920};
const size = {w: 378, h: 340};
const sans = vectorMotion(v, 10.1, frame, size, 0, traceCue);
const propre = vectorMotion(v, 10.1, frame, size, 0, null);
ok(sans.inType === 'pop' && Math.abs(sans.scale - propre.scale) < 1e-9 && Math.abs(sans.opacity - propre.opacity) < 1e-9,
	`dessin sans trait + « trace » de la choregraphie : garde son « pop » (entree ${sans.inType}, echelle ${sans.scale.toFixed(3)})`);
const avec = vectorMotion(v, 10.25, frame, size, 1, traceCue);
ok(avec.inType === 'trace' && avec.dash.length === 1 && avec.dash[0] > 0 && avec.dash[0] < 1,
	`dessin avec traits : le « trace » de la choregraphie le dessine (entree ${avec.inType}, reste ${avec.dash[0]?.toFixed(2)})`);

console.log(`\n${count - fails}/${count} verifications de la revue (rendu) reussies`);
process.exit(fails ? 1 : 0);
