// Rendu Remotion REEL (moteur graphique deja compile, lu seulement) du style Tech 3D cinematique avec l'ancien puis
// le nouveau detourage, a partir du bac a sable cree par test_detourage_rvm.py. Un petit serveur de fichiers local
// (127.0.0.1, port libre) sert UNIQUEMENT le bac, comme render.mjs le fait pour un export. Rien n'est ecrit hors du bac
// et du dossier de preuves. Lancer depuis remotion/ (Chrome deja present) :
//   node ../docs/qualite-2026-09-30/tests/rendu_detourage.mjs [bac] [images=24,39,100]
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';

const ICI = path.dirname(fileURLToPath(import.meta.url));
const VRAI = path.resolve(ICI, '../../..');
const BAC = path.resolve(process.argv[2] ?? path.join(VRAI, 'runtime/cache/tmp/detourage-rvm-test'));
const IMAGES = (process.argv[3] ?? '24,39,100').split(',').map(Number);
const PREUVES = path.join(ICI, 'detourage-preuves');
const req = createRequire(path.join(VRAI, 'remotion', 'package.json'));
const {selectComposition, renderStill} = await import(pathToFileURL(req.resolve('@remotion/renderer')).href);

// polices et textures lues dans le vrai dossier par jonction (lecture seule)
for (const d of ['fonts', 'overlays']) {
	const lien = path.join(BAC, 'assets', d);
	if (!fs.existsSync(lien) && fs.existsSync(path.join(VRAI, 'assets', d)))
		spawnSync('cmd', ['/c', 'mklink', '/J', lien, path.join(VRAI, 'assets', d)], {windowsHide: true});
}
const metas = fs.readdirSync(path.join(BAC, 'assets/detourage')).filter((f) => f.endsWith('.json'))
	.map((f) => JSON.parse(fs.readFileSync(path.join(BAC, 'assets/detourage', f), 'utf8'))).filter((d) => d.start === 5 && d.end === 9);
const variantes = {ancien: metas.find((d) => !d.engine), nouveau: metas.find((d) => d.engine)};
if (!variantes.ancien || !variantes.nouveau) throw new Error('Lancer d abord test_detourage_rvm.py (plage 5-9 s).');

const vrai = JSON.parse(fs.readFileSync(path.join(VRAI, 'projects/script1/reels/script.json'), 'utf8'));  // lecture seule
const c3 = vrai.clips.find((c) => c.id === 'c3');
const reelDe = (doc) => ({
	...vrai, clips: [{...c3, in: 5, out: 9, words: c3.words.filter((w) => w.start >= 5 && w.end <= 9)}],
	sources: {[c3.source]: vrai.sources[c3.source]}, broll: [], graphics: [], intro: {...(vrai.intro ?? {}), enabled: false},
	music: {...(vrai.music ?? {}), enabled: false}, banner: {...(vrai.banner ?? {}), enabled: false},
	design: {...(vrai.design ?? {}), mode: 'produit', cinematic: true, scenes: [], accent: vrai.design?.accent ?? '#6FE7FF'},
	cutouts: {c3: {...doc, source: c3.source, proxy: vrai.sources[c3.source].proxy}},
});

const MIME = {'.mp4': 'video/mp4', '.webp': 'image/webp', '.png': 'image/png', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.otf': 'font/otf', '.json': 'application/json'};
const serveur = await new Promise((resolve) => {
	const permis = [path.join(BAC, 'projects'), path.join(BAC, 'assets')];
	const s = http.createServer((q, r) => {
		const f = path.normalize(path.join(BAC, decodeURIComponent(new URL(q.url, 'http://x').pathname)));
		if (!permis.some((p) => f.startsWith(p)) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) return r.writeHead(404), r.end();
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
const cache = path.join(VRAI, 'runtime/cache');
const bundle = fs.readdirSync(cache).filter((f) => /^remotion-bundle-[0-9a-f]{12}$/.test(f) && fs.existsSync(path.join(cache, f, '.source-hash')))
	.map((f) => path.join(cache, f)).sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0];
if (!bundle) throw new Error('Aucun moteur graphique compile dans runtime/cache.');
console.log('moteur graphique', path.basename(bundle));
const sorties = [];
try {
	for (const [nom, doc] of Object.entries(variantes)) {
		const inputProps = {reel: reelDe(doc), audio: 'none', mediaBase: origine, assetBase: `${origine}/assets`};
		const composition = await selectComposition({serveUrl: bundle, id: 'Reel', inputProps});
		for (const i of IMAGES) {
			const out = path.join(PREUVES, `rendu-tech3d-${nom}-image${String(i).padStart(3, '0')}.png`);
			const t = Date.now();
			await renderStill({serveUrl: bundle, composition, inputProps, frame: i, output: out, chromiumOptions: {gl: 'angle'}});
			console.log(nom, 'image', i, `${Date.now() - t} ms`, out);
			sorties.push(out);
		}
	}
} finally {
	serveur.close();
}
// planches : ancien | nouveau, reduites de moitie
const ff = path.join(VRAI, 'tools/ffmpeg/bin/ffmpeg.exe');
for (const i of IMAGES) {
	const n = String(i).padStart(3, '0');
	const out = path.join(PREUVES, `rendu-tech3d-ancien-vs-nouveau-image${n}.png`);
	spawnSync(ff, ['-v', 'error', '-y', '-i', path.join(PREUVES, `rendu-tech3d-ancien-image${n}.png`), '-i', path.join(PREUVES, `rendu-tech3d-nouveau-image${n}.png`),
		'-filter_complex', '[0:v]pad=iw+12:ih:0:0:white[a];[a][1:v]hstack,scale=iw/2:-2', out], {stdio: 'inherit', windowsHide: true});
	console.log('planche', out);
}
