// Notes et dessins ABSENTS de l'export : deux exports COURTS (2 s, images 0 a 59) du meme reel (copie de Video 1),
// l'un sans rien, l'autre avec 3 notes et 6 grands dessins magenta visibles pendant ces 2 s ; puis comparaison des images.
//   node docs/direction-creative-v2/tests/notes/test-export.mjs
// Meme chemin que la file d'exports du serveur : node remotion/render.mjs <job.json> avec {reel, out} (+ frameRange),
// lance depuis remotion/ (Chrome deja present). Sorties : runtime/cache/tmp/notes-agent/export-XXXXXX/ (rien dans
// livraisons/, rien dans projects/). Un export a la fois.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn, spawnSync} from 'node:child_process';
import * as T from '../../../../remotion/src/timeline.ts';
import {ROOT, bac, bilan, chargerRevue, lire, ok} from './outils.mjs';

const box = bac('export');
const R = await chargerRevue(box);
const FFMPEG = path.join(ROOT, 'tools', 'ffmpeg', 'bin', 'ffmpeg.exe');
const SRC = path.join(ROOT, 'remotion', 'src');
const ENV = {...process.env, EDITEUR_ROOT: ROOT, TEMP: path.join(ROOT, 'runtime', 'cache', 'tmp'), TMP: path.join(ROOT, 'runtime', 'cache', 'tmp'),
	XDG_CACHE_HOME: path.join(ROOT, 'runtime', 'cache'), PATH: [path.join(ROOT, 'tools', 'ffmpeg', 'bin'), process.env.PATH].join(path.delimiter)};
// meme empreinte que render.mjs (sourceHash) : les deux exports doivent utiliser le MEME moteur graphique
const empreinte = () => {
	const h = crypto.createHash('sha1');
	for (const f of fs.readdirSync(SRC).sort()) h.update(f + fs.statSync(path.join(SRC, f)).mtimeMs);
	return h.digest('hex').slice(0, 12);
};

const base = lire('projects/script1/reels/script.json');
delete base.notes;
delete base.annotations;
const FIN = 59;
const fps = base.fps;

// reel B : 3 notes + 6 dessins (4 outils) couvrant les images 0 a 59, en magenta pur, tres epais
const MAGENTA = '#FF00FF';
const zigzag = Array.from({length: 60}, (_, i) => [0.08 + (i / 59) * 0.84, i % 2 ? 0.25 : 0.75]);
const dessins = [
	R.newAnnotation(base, 0, {outil: 'crayon', couleur: MAGENTA, epaisseur: 60, duree: 2}, zigzag),
	R.newAnnotation(base, 0.5, {outil: 'surligneur', couleur: MAGENTA, epaisseur: 120, duree: 2}, [[0.1, 0.5], [0.5, 0.52], [0.9, 0.5]]),
	R.newAnnotation(base, 0, {outil: 'cercle', couleur: MAGENTA, epaisseur: 40, duree: 2}, [[0.2, 0.3], [0.8, 0.6]]),
	R.newAnnotation(base, 1, {outil: 'fleche', couleur: MAGENTA, epaisseur: 40, duree: 2}, [[0.1, 0.9], [0.7, 0.4]]),
	R.newAnnotation(base, 1.5, {outil: 'crayon', couleur: MAGENTA, epaisseur: 80, duree: 2}, [[0.5, 0.1], [0.5, 0.9]]),
	R.newAnnotation(base, 0.04, {outil: 'crayon', couleur: MAGENTA, epaisseur: 200, duree: 2}, [[0.3, 0.45]]),
];
const notes = [R.newNote(base, 0, 'Accroche : trop lent ?', 'Sami', '9:16'), R.newNote(base, 1, 'Le logo doit apparaître ici', 'Sami', '9:16'),
	{...R.newNote(base, 1.9, 'OK validé ✅', 'Sami', '9:16'), statut: 'resolue'}];
dessins[0].noteId = notes[0].id;
const avec = {...base, notes, annotations: dessins};
ok(dessins.every(Boolean) && notes.every(Boolean), `reel d'essai : ${notes.length} notes et ${dessins.length} dessins magenta (4 outils) sur les 2 premieres secondes`);

const exporter = (nom, reel) => new Promise((resolve) => {
	const out = path.join(box, `${nom} - FINAL.mp4`);
	const job = path.join(box, `${nom}.json`);
	fs.writeFileSync(job, JSON.stringify({reel, out, frameRange: [0, FIN]}));
	const t0 = Date.now();
	const p = spawn(process.execPath, [path.join(ROOT, 'remotion', 'render.mjs'), job], {cwd: path.join(ROOT, 'remotion'), env: ENV, windowsHide: true});
	let last = '';
	p.stdout.on('data', (d) => (last = String(d).trim().split(/\r?\n/).pop() || last));
	p.stderr.on('data', (d) => fs.appendFileSync(path.join(box, `${nom}.err.log`), d));
	p.on('exit', (code) => resolve({code, out, last, s: ((Date.now() - t0) / 1000).toFixed(1)}));
});
const hashes = (file) => spawnSync(FFMPEG, ['-v', 'error', '-i', file, '-map', '0:v:0', '-f', 'framemd5', '-'], {encoding: 'utf8', maxBuffer: 64 << 20}).stdout
	.split(/\r?\n/).filter((l) => l && !l.startsWith('#')).map((l) => l.split(',').pop().trim());
const image = (file, f) => spawnSync(FFMPEG, ['-v', 'error', '-i', file, '-map', '0:v:0', '-vf', `select=eq(n\\,${f})`, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
	{maxBuffer: 64 << 20}).stdout;
const magenta = (buf) => {
	let n = 0;
	for (let i = 0; i < buf.length; i += 3) if (buf[i] > 200 && buf[i + 1] < 90 && buf[i + 2] > 200) n++;
	return n;
};

const h0 = empreinte();
const A = await exporter('sans-notes', base);
ok(A.code === 0 && fs.existsSync(A.out), `export 1 (sans notes ni dessins) : code ${A.code}, ${A.s} s — ${A.last.slice(0, 120)}`);
const B = await exporter('avec-notes', avec);
ok(B.code === 0 && fs.existsSync(B.out), `export 2 (avec 3 notes + 6 dessins) : code ${B.code}, ${B.s} s — ${B.last.slice(0, 120)}`);
const h1 = empreinte();
ok(h0 === h1, `meme moteur graphique pour les deux exports (empreinte ${h0}${h0 === h1 ? '' : ` -> ${h1} : remotion/src a change pendant le test, relancer`})`);

if (A.code === 0 && B.code === 0) {
	const ha = hashes(A.out);
	const hb = hashes(B.out);
	ok(ha.length === FIN + 1 && hb.length === FIN + 1, `${ha.length} et ${hb.length} images decodees (2 s a ${fps} i/s)`);
	const diff = ha.filter((h, i) => h !== hb[i]).length;
	ok(diff === 0, `images identiques au pixel pres (empreinte MD5 de chaque image decodee) : ${ha.length - diff}/${ha.length}`);
	// temoin : ce qu'un export AVEC dessins aurait montre (dessins de l'apercu peints dans l'image 1), puis controle de B
	const W = base.width;
	const H = base.height;
	let totalTemoin = 0;
	let totalB = 0;
	let totalA = 0;
	for (const f of [0, 15, 30, 45, 59]) {
		const t = f / fps;
		const a = image(A.out, f);
		const b = image(B.out, f);
		const spans = new Map(dessins.map((d) => [d.id, R.annotationSpan(avec, d)]));
		const vus = R.visibleDrawings(avec, dessins, spans, t);
		const temoin = Buffer.from(a);
		for (const v of vus) {
			const r = Math.max(2, (v.a.epaisseur * Math.min(W, H)) / 2160);
			const P = v.pts.map(([x, y]) => [x * W, y * H]);
			const seg = v.a.outil === 'cercle' ? [P[0], P[1]] : P;
			for (let i = 0; i < seg.length; i++) {
				const [p, q] = [seg[i], seg[Math.min(seg.length - 1, i + 1)]];
				const pas = Math.max(1, Math.ceil(Math.hypot(q[0] - p[0], q[1] - p[1]) / 2));
				for (let s = 0; s <= pas; s++) {
					const [cx, cy] = [p[0] + ((q[0] - p[0]) * s) / pas, p[1] + ((q[1] - p[1]) * s) / pas];
					for (let y = Math.max(0, Math.floor(cy - r)); y < Math.min(H, cy + r); y++) {
						for (let x = Math.max(0, Math.floor(cx - r)); x < Math.min(W, cx + r); x++) {
							if ((x - cx) ** 2 + (y - cy) ** 2 <= r * r) temoin.set([255, 0, 255], (y * W + x) * 3);
						}
					}
				}
			}
		}
		totalTemoin += magenta(temoin);
		totalB += magenta(b);
		totalA += magenta(a);
		console.log(`     image ${f} : ${vus.length} dessin(s) affiches dans l'apercu ; pixels magenta : temoin ${magenta(temoin)}, export avec notes ${magenta(b)}, export sans ${magenta(a)} ; identiques : ${a.equals(b)}`);
	}
	ok(totalTemoin > 100000 && totalB === totalA, `les dessins de l'apercu auraient colore ${totalTemoin} pixels magenta ; l'export avec notes en a ${totalB} (autant que sans : ${totalA})`);
	// piste son : identique aussi (les notes ne touchent ni la musique ni les bruitages)
	const son = (file) => crypto.createHash('md5').update(spawnSync(FFMPEG, ['-v', 'error', '-i', file, '-map', '0:a:0', '-f', 's16le', '-'], {maxBuffer: 64 << 20}).stdout).digest('hex');
	ok(son(A.out) === son(B.out), 'piste son identique');
}
// « Transformer en élément graphique » : la fleche, le cercle et le surligneur deviennent des vecteurs -> CETTE fois exportes
{
	const vecs = dessins.map((d) => R.toVector(base, d, {entree: 'fondu', sortie: 'fondu'})).filter(Boolean);
	ok(vecs.length === 3, `3 dessins convertibles (fleche, cercle, surligneur) -> ${vecs.length} vecteurs magenta ; le crayon reste un dessin de revision`);
	const C = await exporter('dessins-transformes', {...base, notes, vectors: vecs, annotations: dessins.filter((d) => !R.VECTEURS_DESSIN[d.outil])});
	ok(C.code === 0 && fs.existsSync(C.out), `export 3 (dessins transformes en elements graphiques) : code ${C.code}, ${C.s} s`);
	if (C.code === 0 && A.code === 0) {
		const ha = hashes(A.out);
		const hc = hashes(C.out);
		const diff = ha.filter((h, i) => h !== hc[i]).length;
		const mag = [30, 45, 59].map((f) => magenta(image(C.out, f)));
		ok(diff > 0 && mag.every((m) => m > 2000), `elements graphiques presents dans l'export : ${diff}/${ha.length} images changees, pixels magenta aux images 30/45/59 : ${mag.join(' / ')}`);
		spawnSync(FFMPEG, ['-v', 'error', '-y', '-i', C.out, '-vf', 'select=eq(n\\,45),scale=360:-1', '-frames:v', '1', path.join(box, 'transformes-image45.png')]);
	}
}
console.log(`Bac conserve : ${box}`);
bilan('notes (export 2 s sans notes ni dessins)');
