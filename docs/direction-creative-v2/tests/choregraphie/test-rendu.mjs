// Rendu Remotion REEL de la choregraphie, sur des COPIES en memoire de Video 1 (copie figee fixtures/projects/script1, lecture seule).
//   node docs/direction-creative-v2/tests/choregraphie/test-rendu.mjs [--sans-export]
// 1. Deux moteurs graphiques compiles dans le bac : remotion/src avec le BOUCHON de choreo.tsx (avant) et avec le
//    nouveau choreo.tsx (apres). Un ancien reel SANS choregraphie donne des images identiques pixel pour pixel.
// 2. Avec la choregraphie du moteur : images prises au milieu de chaque entree (differentes de l'image sans mouvement)
//    + planches cote a cote (sans | avec) a regarder.
// 3. Export court de 4 s (render.mjs, frameRange) avec la choregraphie, puis images extraites au milieu des entrees.
// Bac : runtime/cache/tmp/dcv2-choregraphie/rendu-<hasard>/ ; un petit serveur de fichiers local (127.0.0.1, port libre)
// sert projects/ et assets/ en LECTURE, comme render.mjs le fait pour un export. Rien n'est ecrit ailleurs.
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../../..');
const REMOTION = path.join(ROOT, 'remotion');
const req = createRequire(path.join(REMOTION, 'package.json'));
const {bundle} = req('@remotion/bundler');
const {renderStill, selectComposition} = req('@remotion/renderer');
const browserExecutable = path.join(REMOTION, 'node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe');
if (!fs.existsSync(browserExecutable)) throw new Error('Navigateur local absent : aucun telechargement automatique autorise.');
const FFMPEG = path.join(ROOT, 'tools/ffmpeg/bin/ffmpeg.exe');
fs.mkdirSync(path.join(ROOT, 'runtime/cache/tmp/dcv2-choregraphie'), {recursive: true});
const box = fs.mkdtempSync(path.join(ROOT, 'runtime/cache/tmp/dcv2-choregraphie/rendu-'));
const B = (...p) => path.join(box, ...p);
console.log('bac', box);

let fails = 0;
let count = 0;
const ok = (cond, msg) => {
	count++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${msg}`);
	if (!cond) fails++;
};
const sha = (f) => crypto.createHash('sha1').update(fs.readFileSync(f)).digest('hex');

// ---------- donnees : copie de Video 1, choregraphie calculee par le moteur (sur la copie) ----------
const VRAI = path.join(HERE, '..', 'fixtures', 'projects/script1/reels/script.json'); // copie figee (jamais projects/)
const avantHash = sha(VRAI);
const vrai = JSON.parse(fs.readFileSync(VRAI, 'utf8'));
const sans = {...vrai};
delete sans.choreography;
fs.writeFileSync(B('reel-sans.json'), JSON.stringify(sans));
const py = spawnSync(path.join(ROOT, 'runtime/venv/Scripts/python.exe'), ['-c', `import json,sys
from editeur import choregraphie
r=json.load(open(sys.argv[1],encoding='utf-8')); choregraphie.actualiser(r, creer=True)
json.dump(r, open(sys.argv[2],'w',encoding='utf-8'), ensure_ascii=False)`, B('reel-sans.json'), B('reel-avec.json')],
{cwd: path.join(ROOT, 'engine'), encoding: 'utf8', env: {...process.env, EDITEUR_LLM: '0', PYTHONIOENCODING: 'utf-8'}});
if (py.status !== 0) throw new Error(py.stderr);
const avec = JSON.parse(fs.readFileSync(B('reel-avec.json'), 'utf8'));
const cues = avec.choreography.cues;
ok(cues.length > 0, `choregraphie du moteur : ${cues.length} mouvements`);

// ---------- deux moteurs graphiques : bouchon (avant) / nouveau (apres) ----------
const BOUCHON = `import React from 'react';
import type {Cue, CueTarget, ReelDoc} from './types';
export type Envelope = {opacity: number; transform: string};
export const IDENTITY: Envelope = {opacity: 1, transform: ''};
export const cueFor = (reel: ReelDoc, cible: CueTarget): Cue | null =>
	reel.choreography?.cues?.find((c) => !c.desactive && c.cible.type === cible.type && c.cible.id === cible.id) ?? null;
export const animateElement = (_cue: Cue | null, _t: number, _at: number, _duration: number): Envelope => IDENTITY;
export const Choreo: React.FC<{reel: ReelDoc; cible: CueTarget; t: number; at: number; duration: number; children?: React.ReactNode}> = ({children}) => (
	<>{children}</>
);
`;
const moteur = async (nom, bouchon) => {
	const src = B(`src-${nom}`);
	fs.cpSync(path.join(REMOTION, 'src'), src, {recursive: true});
	if (bouchon) fs.writeFileSync(path.join(src, 'choreo.tsx'), BOUCHON);
	return bundle({entryPoint: path.join(src, 'index.ts'), outDir: B(`moteur-${nom}`),
		webpackOverride: (c) => ({...c, resolve: {...c.resolve, modules: [path.join(REMOTION, 'node_modules'), 'node_modules']}})});
};
const t0 = Date.now();
const avant = await moteur('avant', true);
const apres = await moteur('apres', false);
console.log(`moteurs compiles en ${((Date.now() - t0) / 1000).toFixed(0)} s`);

// ---------- serveur de fichiers en lecture (projects/, assets/) ----------
const MIME = {'.mp4': 'video/mp4', '.webm': 'video/webm', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.ttf': 'font/ttf',
	'.otf': 'font/otf', '.woff2': 'font/woff2', '.json': 'application/json', '.ogg': 'audio/ogg', '.wav': 'audio/wav', '.svg': 'image/svg+xml'};
const serveur = await new Promise((resolve) => {
	const permis = [path.join(ROOT, 'projects'), path.join(ROOT, 'assets')];
	const s = http.createServer((q, r) => {
		const f = path.normalize(path.join(ROOT, decodeURIComponent(new URL(q.url, 'http://x').pathname)));
		if (!permis.some((p) => f.startsWith(p + path.sep)) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) return r.writeHead(404), r.end();
		const size = fs.statSync(f).size;
		const h = {'content-type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream', 'accept-ranges': 'bytes', 'access-control-allow-origin': '*'};
		const m = /^bytes=(\d*)-(\d*)$/.exec(q.headers.range || '');
		if (m && (m[1] || m[2])) {
			const a = m[1] ? Number(m[1]) : Math.max(0, size - Number(m[2]));
			const b = m[1] && m[2] ? Math.min(Number(m[2]), size - 1) : size - 1;
			r.writeHead(206, {...h, 'content-length': b - a + 1, 'content-range': `bytes ${a}-${b}/${size}`});
			return fs.createReadStream(f, {start: a, end: b}).pipe(r);
		}
		r.writeHead(200, {...h, 'content-length': size});
		fs.createReadStream(f).pipe(r);
	});
	s.listen(0, '127.0.0.1', () => resolve(s));
});
const origine = `http://127.0.0.1:${serveur.address().port}`;
const image = async (serveUrl, reel, frame, out) => {
	const inputProps = {reel, audio: 'none', mediaBase: origine, assetBase: `${origine}/assets`};
	// d'autres rendus peuvent tourner en meme temps (port local du moteur deja pris) : on reessaie
	for (let essai = 1; ; essai++) {
		try {
			const composition = await selectComposition({serveUrl, id: 'Reel', inputProps, browserExecutable});
			await renderStill({serveUrl, composition, inputProps, frame, output: out, imageFormat: 'png', browserExecutable, chromiumOptions: {gl: 'angle'}});
			return out;
		} catch (e) {
			if (essai >= 4) throw e;
			console.log(`      (rendu de l'image ${frame} repris : ${String(e.message).slice(0, 90)})`);
			await new Promise((r) => setTimeout(r, 1500 * essai));
		}
	}
};
/** Ecart entre deux images : {max: plus grand ecart d'une composante (0..255), n: pixels ecartes de plus de 16}.
 * Le decodage d'une video peut varier d'un niveau (1/255) d'un rendu a l'autre : « identique » = max <= 2. */
const rgb = (f) => spawnSync(FFMPEG, ['-loglevel', 'error', '-i', f, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], {maxBuffer: 64 * 1024 * 1024, windowsHide: true}).stdout;
const ecart = (a, b) => {
	const x = rgb(a);
	const y = rgb(b);
	if (x.length !== y.length) return {max: 255, n: Infinity};
	let max = 0;
	let n = 0;
	for (let i = 0; i < x.length; i += 3) {
		const d = Math.max(Math.abs(x[i] - y[i]), Math.abs(x[i + 1] - y[i + 1]), Math.abs(x[i + 2] - y[i + 2]));
		if (d > max) max = d;
		if (d > 16) n++;
	}
	return {max, n, part: n / (x.length / 3)};
};
const pareil = (a, b) => sha(a) === sha(b) || ecart(a, b).max <= 2;
const cote = (a, b, out) => spawnSync(FFMPEG, ['-y', '-loglevel', 'error', '-i', a, '-i', b, '-filter_complex',
	'[0]scale=540:-1[a];[1]scale=540:-1[b];[a][b]hstack', out], {windowsHide: true}).status === 0;

try {
	// 1. ancien reel sans choregraphie : avant / apres identiques pixel pour pixel
	const fps = vrai.fps || 30;
	const instants = [3.0, 26.1, 29.85, 34.85, 38.0, 48.2];
	for (const s of instants) {
		const f = Math.round(s * fps);
		const a = await image(avant, sans, f, B(`sans-avant-${f}.png`));
		const b = await image(apres, sans, f, B(`sans-apres-${f}.png`));
		const c = await image(apres, {...sans, choreography: {version: 1, cues: []}}, f, B(`vide-apres-${f}.png`));
		const e = ecart(a, b);
		ok(pareil(a, b) && pareil(b, c), `ancien reel, image ${f} (${s} s) : identique avant/apres et avec une choregraphie vide `
			+ `(${sha(a) === sha(b) ? 'octet pour octet' : `ecart max ${e.max}/255 : bruit du decodage video`})`);
	}
	// bruit du decodage : la meme image, le meme moteur, rendue deux fois
	const f38 = Math.round(38 * fps);
	const r1 = await image(avant, sans, f38, B(`bruit-1-${f38}.png`));
	const r2 = await image(avant, sans, f38, B(`bruit-2-${f38}.png`));
	console.log(`      (meme image rendue deux fois par le meme moteur : ecart max ${ecart(r1, r2).max}/255)`);
	// 2. au milieu de chaque entree : le mouvement est la (image differente), planche sans | avec
	for (const cue of cues) {
		if (cue.entree.type === 'aucune' || cue.desactive) continue;
		const f = Math.round((cue.at + Math.min(cue.entree.duree, cue.duree * 0.4) * 0.35) * fps);
		const a = await image(apres, sans, f, B(`mi-sans-${cue.id.replace(/[:]/g, '_')}-${f}.png`));
		const b = await image(apres, avec, f, B(`mi-avec-${cue.id.replace(/[:]/g, '_')}-${f}.png`));
		const fin = Math.round((cue.at + cue.entree.duree + 0.25) * fps);
		const c = await image(apres, sans, fin, B(`fin-sans-${f}.png`));
		const d = await image(apres, avec, fin, B(`fin-avec-${f}.png`));
		const m = ecart(a, b);
		ok(m.max > 40 && m.n > 500, `${cue.id} : ${cue.entree.type} visible a mi-entree (image ${f} : ${m.n} pixels changent, ${(m.part * 100).toFixed(2)} %)`);
		ok(pareil(c, d), `${cue.id} : entree finie (image ${fin}) = image sans mouvement (ecart max ${ecart(c, d).max}/255)`);
		cote(a, b, B(`planche-${cue.id.replace(/[:]/g, '_')}-${f}.png`));
	}
	// 3. export court de 4 s avec la choregraphie (preuve « x5 » et notification)
	if (!process.argv.includes('--sans-export')) {
		const debut = 34.4;
		const job = B('export.json');
		const out = B('export-4s-avec-choregraphie.mp4');
		fs.writeFileSync(job, JSON.stringify({reel: avec, out, frameRange: [Math.round(debut * fps), Math.round((debut + 4) * fps) - 1]}));
		const t1 = Date.now();
		const r = spawnSync(process.execPath, [path.join(REMOTION, 'render.mjs'), job], {cwd: REMOTION, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024,
			windowsHide: true, env: {...process.env, EDITEUR_CONCURRENCE: '4'}});
		fs.writeFileSync(B('export.log'), `${r.stdout}\n${r.stderr}`);
		ok(r.status === 0 && fs.existsSync(out), `export 4 s termine en ${((Date.now() - t1) / 1000).toFixed(0)} s (${out})`);
		if (fs.existsSync(out)) {
			const probe = spawnSync(path.join(ROOT, 'tools/ffmpeg/bin/ffprobe.exe'), ['-v', 'error', '-show_entries', 'format=duration:stream=codec_name,width,height',
				'-of', 'json', out], {encoding: 'utf8'});
			const info = JSON.parse(probe.stdout);
			const dur = Number(info.format.duration);
			ok(Math.abs(dur - 4) < 0.15 && info.streams.some((s) => s.codec_name === 'h264') && info.streams.some((s) => s.codec_name === 'aac'),
				`export : ${dur.toFixed(2)} s, ${info.streams.map((s) => s.codec_name + (s.width ? ` ${s.width}x${s.height}` : '')).join(' + ')}`);
			for (const cue of cues.filter((c) => c.at >= debut && c.at < debut + 4 && c.entree.type !== 'aucune')) {
				const local = cue.at - debut + cue.entree.duree * 0.35;
				const png = B(`export-mi-entree-${cue.id.replace(/[:]/g, '_')}.png`);
				spawnSync(FFMPEG, ['-y', '-loglevel', 'error', '-ss', local.toFixed(3), '-i', out, '-frames:v', '1', png], {windowsHide: true});
				ok(fs.existsSync(png), `image extraite de l'export a mi-entree de ${cue.id} (${local.toFixed(2)} s) : ${png}`);
			}
		}
	}
} finally {
	serveur.close();
}
ok(sha(VRAI) === avantHash, 'reel fige fixtures/projects/script1/reels/script.json inchange');
console.log(`\n${count - fails}/${count} verifications de rendu reussies ; images dans ${box}`);
process.exit(fails ? 1 : 0);
