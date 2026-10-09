// Tests de remotion/src/choreo.tsx (enveloppe des mouvements) et de la piste (temps des cibles), sans navigateur.
//   node docs/direction-creative-v2/tests/choregraphie/test-choreo.mjs
// choreo.tsx est compile par esbuild (celui de remotion/node_modules) dans runtime/cache/tmp/dcv2-choregraphie/ puis
// importe ; React rend le composant <Choreo> en HTML (react-dom/server) pour verifier qu'un element SANS mouvement est
// rendu EXACTEMENT comme avant (aucune div ajoutee). Lecture seule de la copie figee fixtures/projects/script1 (en memoire).
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../../..');
const MODULES = path.join(ROOT, 'remotion', 'node_modules');
const req = createRequire(path.join(MODULES, 'x.js'));
const esbuild = req('esbuild');
const box = path.join(ROOT, 'runtime/cache/tmp/dcv2-choregraphie');
fs.mkdirSync(box, {recursive: true});
const entry = path.join(box, 'choreo-essai-entree.tsx');
fs.writeFileSync(entry, `export * from ${JSON.stringify(path.join(ROOT, 'remotion/src/choreo.tsx').replace(/\\/g, '/'))};
export {pages, designScenes} from ${JSON.stringify(path.join(ROOT, 'remotion/src/timeline.ts').replace(/\\/g, '/'))};
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
export {React, renderToStaticMarkup};
`);
const out = path.join(box, `choreo-essai-${process.pid}.cjs`);
await esbuild.build({entryPoints: [entry], bundle: true, outfile: out, format: 'cjs', platform: 'node', jsx: 'automatic', nodePaths: [MODULES],
	logLevel: 'error', define: {'process.env.NODE_ENV': '"production"'}});
const M = createRequire(import.meta.url)(out);
fs.rmSync(out, {force: true});
fs.rmSync(entry, {force: true});
const {React, renderToStaticMarkup, Choreo, animateElement, cueFor, cueDurations, ease, placeOf, targetTimes, IDENTITY} = M;

let fails = 0;
let count = 0;
const ok = (cond, msg) => {
	count++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${msg}`);
	if (!cond) fails++;
};
const near = (a, b, e = 1e-6) => Math.abs(a - b) <= e;

const vrai = JSON.parse(fs.readFileSync(path.join(HERE, '..', 'fixtures', 'projects/script1/reels/script.json'), 'utf8')); // copie figee
const sans = {...vrai};
delete sans.choreography;
const cue = (over = {}) => ({id: 'cue-graphics-g2-chiffre', cible: {type: 'graphics', id: 'g2-chiffre'}, at: 37.88, duree: 2.2,
	entree: {type: 'pop', direction: null, duree: 0.4, courbe: 'rebond'}, sortie: {type: 'fondu', direction: null, duree: 0.3, courbe: 'douce'},
	sync: {sur: 'mot', ref: 'c3:35'}, raison: 'essai', auto: true, locked: false, ...over});
const avec = (...cues) => ({...vrai, choreography: {version: 1, cues}});
const g2 = {type: 'graphics', id: 'g2-chiffre'};

// 1. sans mouvement : rendu identique (aucune enveloppe)
const enfant = React.createElement('div', {id: 'x', style: {position: 'absolute', top: 10}}, 'X');
const nu = renderToStaticMarkup(enfant);
const rendu = (reel, t) => renderToStaticMarkup(React.createElement(Choreo, {reel, cible: g2, t, at: 37.88, duration: 2.2}, enfant));
ok(rendu(sans, 38) === nu, 'ancien reel (sans choregraphie) : enfant rendu tel quel, aucune div ajoutee');
ok(rendu({...vrai, choreography: {version: 1, cues: []}}, 38) === nu, 'choregraphie vide : rendu identique');
ok(rendu(avec(cue({cible: {type: 'graphics', id: 'autre'}})), 38) === nu, 'mouvement d\'un autre element : rendu identique');
ok(rendu(avec(cue({desactive: true})), 38) === nu, 'mouvement desactive : rendu identique');
ok(rendu(avec(cue({entree: {type: 'aucune', duree: 0, courbe: 'lineaire'}, sortie: {type: 'aucune', duree: 0, courbe: 'lineaire'}})), 38) === nu,
	'entree et sortie « aucune » : rendu identique');
ok(cueFor(sans, g2) === null && cueFor(avec(cue()), g2)?.id === 'cue-graphics-g2-chiffre', 'cueFor');
const mi = rendu(avec(cue()), 37.88 + 0.12);
ok(mi !== nu && mi.includes('scale(') && mi.includes('id="x"') && /opacity:\s*0?\.\d|opacity:1/.test(mi), `au milieu de l'entree : enveloppe posee (${mi.slice(0, 160)}…)`);
const apres = rendu(avec(cue()), 38.9);
ok(apres.includes('id="x"') && !apres.includes('scale(') && !apres.includes('translate('), 'entree finie : enveloppe neutre (aucune transformation)');

// 2. courbes
for (const c of ['douce', 'rapide', 'rebond', 'lineaire']) ok(near(ease(c, 0), 0) && near(ease(c, 1), 1), `courbe ${c} : 0 -> 0, 1 -> 1`);
ok([...Array(20).keys()].some((i) => ease('rebond', i / 20) > 1.01), 'rebond : depasse un peu puis se pose');
ok(ease('rapide', 0.2) > ease('douce', 0.2) && ease('douce', 0.2) > ease('lineaire', 0.2), 'rapide part plus vite que douce, douce plus vite que lineaire');

// 3. enveloppes
const P = placeOf(vrai, g2);
ok(P.x === 0.5 && P.y > 0.2 && P.y < 0.4, `place du chiffre (${P.x}, ${P.y})`);
const env = (c, t, at = 10, d = 3) => animateElement(c, t, at, d, P);
ok(env(null, 10.1) === IDENTITY, 'sans mouvement : identite');
const fondu = cue({entree: {type: 'fondu', duree: 0.4, courbe: 'lineaire'}});
ok(near(env(fondu, 10).opacity, 0) && near(env(fondu, 10.2).opacity, 0.5) && env(fondu, 10.4) === IDENTITY, 'fondu lineaire : 0 -> 0,5 -> identite');
ok(env(fondu, 11.5) === IDENTITY, 'milieu de l\'element : identite');
const so = env(fondu, 12.85);
ok(so.opacity > 0 && so.opacity < 1 && env(fondu, 13).opacity === 0, 'sortie en fondu : s\'efface jusqu\'a 0 a la fin');
const gl = (d) => env(cue({entree: {type: 'glisse', direction: d, duree: 0.4, courbe: 'douce'}}), 10.05).transform;
ok(/translate\(-\d/.test(gl('gauche')) && /translate\(\d/.test(gl('droite')) && /translate\(0\.000%, -\d/.test(gl('haut')) && /translate\(0\.000%, \d/.test(gl('bas')),
	`glisse : directions (${gl('gauche')} | ${gl('haut')})`);
const pop = env(cue({entree: {type: 'pop', duree: 0.4, courbe: 'rebond'}}), 10.1);
ok(/scale\(0\.\d+\)/.test(pop.transform) && pop.transformOrigin?.startsWith('50.00%'), `pop : echelle autour de l'element (${pop.transform}, origine ${pop.transformOrigin})`);
const tr = env(cue({entree: {type: 'trace', direction: 'gauche', duree: 0.5, courbe: 'lineaire'}}), 10.25);
ok(tr.clipPath?.startsWith('inset(') && near(tr.trace, 0.5), `trace : decoupe dans le sens du trace (${tr.clipPath}, trace ${tr.trace})`);
const vec = {...vrai, vectors: [{id: 'v1', asset: 'banque/vecteurs/fleche.svg', at: 10, duration: 3, x: 0.5, y: 0.4, w: 0.3, rotation: 0, opacite: 1,
	couleurs: {principale: null, secondaire: null, contour: null}, couleursManuelles: false, anim: {entree: 'trace', sortie: 'fondu'}}]};
const trv = animateElement(cue({cible: {type: 'vector', id: 'v1'}, entree: {type: 'trace', direction: 'gauche', duree: 0.5, courbe: 'lineaire'}}), 10.25, 10, 3,
	placeOf(vec, {type: 'vector', id: 'v1'}));
ok(!trv.clipPath && near(trv.trace, 0.5) && !trv.transform, 'vecteur : le trace est dessine par vectors.tsx (aucune decoupe ici, progression donnee)');
const court = cue({entree: {type: 'zoom', duree: 2, courbe: 'douce'}, sortie: {type: 'fondu', duree: 2, courbe: 'douce'}});
const [din, dout] = cueDurations(court, 1);
ok(near(din + dout, 0.9) && near(din, dout), `element trop court : entree + sortie ramenees a 90 % (${din.toFixed(2)} + ${dout.toFixed(2)})`);
const plein = placeOf({...vrai, broll: [{id: 'b1', source: vrai.clips[0].source, in: 0, at: 5, duration: 2}]}, {type: 'broll', id: 'b1'});
const z = animateElement(cue({cible: {type: 'broll', id: 'b1'}, entree: {type: 'zoom', duree: 0.4, courbe: 'lineaire'}}), 5.0, 5, 2, plein);
ok(plein.plein && /scale\(1\.1/.test(z.transform), 'plan de coupe plein ecran : zoom de 1,1 vers 1 (jamais de bord noir)');

// 4. piste : temps des cibles = temps de l'image (sur une choregraphie produite par le moteur, sur une copie)
const tmp = path.join(box, `essai-piste-${process.pid}.json`);
fs.writeFileSync(tmp, JSON.stringify(vrai));
const py = spawnSync(path.join(ROOT, 'runtime/venv/Scripts/python.exe'), ['-c', `import json,sys
from editeur import choregraphie
r=json.load(open(sys.argv[1],encoding='utf-8')); choregraphie.actualiser(r, creer=True)
print(json.dumps(r['choreography'], ensure_ascii=False))`, tmp], {cwd: path.join(ROOT, 'engine'), encoding: 'utf8', env: {...process.env, EDITEUR_LLM: '0', PYTHONIOENCODING: 'utf-8'}});
fs.rmSync(tmp, {force: true});
ok(py.status === 0, `moteur : choregraphie produite (${py.stderr.slice(-300)})`);
const ch = JSON.parse(py.stdout.trim().split('\n').pop());
const reel = {...vrai, choreography: ch};
const times = targetTimes(reel, 71.6);
const manquants = ch.cues.filter((c) => !times.has(`${c.cible.type}:${c.cible.id}`));
ok(ch.cues.length > 0 && !manquants.length, `piste : les ${ch.cues.length} mouvements sont places (${manquants.map((c) => c.id).join(', ') || 'aucun manquant'})`);
const ecarts = ch.cues.map((c) => Math.abs(times.get(`${c.cible.type}:${c.cible.id}`).at - c.at));
ok(Math.max(...ecarts) < 2e-3, `piste : temps de l'element = cache du moteur (ecart max ${Math.max(...ecarts).toFixed(4)} s)`);
// au milieu de chaque entree, l'enveloppe bouge vraiment ; a la fin de l'entree elle est neutre
for (const c of ch.cues) {
	const tt = times.get(`${c.cible.type}:${c.cible.id}`);
	const [a] = cueDurations(c, tt.duration);
	if (!a) continue;
	const m = animateElement(c, tt.at + a / 2, tt.at, tt.duration, placeOf(reel, c.cible));
	const f = animateElement(c, tt.at + a + 0.01, tt.at, tt.duration, placeOf(reel, c.cible));
	ok(m !== IDENTITY && (m.opacity < 1 || m.transform || m.clipPath) && f === IDENTITY, `${c.id} : ${c.entree.type} visible a mi-entree (${m.transform || m.clipPath || `opacite ${m.opacity.toFixed(2)}`}), neutre ensuite`);
}

console.log(`\n${count - fails}/${count} verifications choregraphie (image) reussies`);
process.exit(fails ? 1 : 0);
