// Ronde 4 « icônes » : export court (3,5 s) par le VRAI export (remotion/render.mjs) avec 3 icônes Lucide, une par style
// (trait, plein, verre), aux couleurs d'une charte d'essai, + mesures sur les images.
//   node docs/qualite-2026-09-30/icones/export-icones.mjs        (environnement charge : runtime/env.sh)
// Reel : COPIE EN MEMOIRE du reel fige docs/direction-creative-v2/tests/fixtures/projects/script2 (rien n'est ecrit dans
// projects/, media/ ni livraisons/) + charte d'essai (rose #FF2D95, bandeau violet #7C3AED). Les icones sont des vecteurs
// avec meta.icone, exactement ce que pose « Ajouter » de la banque (banque.element_pour_reel).
// Sortie : runtime/cache/tmp/icones-ronde4/export-<hasard>/ (video, images PNG, planche, mesures.json).
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../..');
const TMP = path.join(ROOT, 'runtime', 'cache', 'tmp', 'icones-ronde4');
const FFMPEG = path.join(ROOT, 'tools', 'ffmpeg', 'bin', 'ffmpeg.exe');
const reel = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs/direction-creative-v2/tests/fixtures/projects/script2/reels/script.json'), 'utf8')); // copie figee
const DEBUT = 10;
const FIN = 13.5;
reel.brand = {client: 'essai', name: 'Charte essai', logo: null, logoPosition: 'haut-droite', logoSize: 0.16, logoOpacity: 0.85,
	bannerBg: '#7C3AED', bannerColor: '#FFFFFF', style: {highlight: '#FF2D95'}, outro: {enabled: false, text: '', duration: 2.5}};
reel.style = {...reel.style, highlight: '#FF2D95'};
const NUL = {principale: null, secondaire: null, contour: null};
const ic = (id, nom, style, fr, o) => ({id, asset: `banque/icones/lucide/${nom}.svg`, rotation: 0, opacite: 1, couleurs: {...NUL}, couleursManuelles: false,
	manual: true, raison: `Banque : ${fr}`, meta: {icone: {style, nom: fr, banque: `icone:lucide:${nom}`}}, ...o});
const W = reel.width;
const H = reel.height;
const BOX = 0.26;
reel.vectors = [
	ic('i-trait', 'handshake', 'trait', 'Poignée de main', {at: 10.0, duration: 3.3, x: 0.2, y: 0.2, w: BOX, anim: {entree: 'pop', sortie: 'fondu'}}),
	ic('i-plein', 'phone', 'plein', 'Téléphone', {at: 10.15, duration: 3.15, x: 0.5, y: 0.2, w: BOX, anim: {entree: 'zoom', sortie: 'fondu'}}),
	ic('i-verre', 'piggy-bank', 'verre', 'Tirelire', {at: 10.3, duration: 3.0, x: 0.8, y: 0.2, w: BOX, anim: {entree: 'pop', sortie: 'fondu'}}),
];
fs.mkdirSync(TMP, {recursive: true});
const box = fs.mkdtempSync(path.join(TMP, 'export-'));
const out = path.join(box, 'icones-3s.mp4');
const job = path.join(box, 'job.json');
fs.writeFileSync(job, JSON.stringify({reel, out, frameRange: [Math.round(DEBUT * reel.fps), Math.round(FIN * reel.fps) - 1]}));
console.log(`DOSSIER=${box}`);
const t0 = Date.now();
const run = spawnSync(process.execPath, [path.join(ROOT, 'remotion/render.mjs'), job], {cwd: path.join(ROOT, 'remotion'), env: process.env, encoding: 'utf8',
	windowsHide: true, maxBuffer: 1 << 26, timeout: 900000});
const lignes = (run.stdout || '').trim().split('\n').filter(Boolean);
console.log(`export : code ${run.status}, ${((Date.now() - t0) / 1000).toFixed(0)} s, derniere ligne : ${lignes.at(-1)}`);
if (run.status !== 0 || !fs.existsSync(out)) {
	console.log((run.stderr || '').slice(-2000));
	process.exit(1);
}

// ---- mesures ----
const raw = (t, x, y, w, h) => spawnSync(FFMPEG, ['-v', 'error', '-ss', String(t), '-i', out, '-frames:v', '1', '-vf', `crop=${w}:${h}:${x}:${y}`,
	'-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], {maxBuffer: 1 << 26}).stdout;
const hex = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const compte = (buf, refs, tol = 75) => {
	let n = 0;
	for (let i = 0; i < buf.length; i += 3) if (refs.some((ref) => dist([buf[i], buf[i + 1], buf[i + 2]], ref) < tol)) n++;
	return n;
};
const moyenne = (buf) => {
	const s = [0, 0, 0];
	for (let i = 0; i < buf.length; i += 3) for (let k = 0; k < 3; k++) s[k] += buf[i + k];
	return s.map((v) => Math.round(v / (buf.length / 3)));
};
const u = Math.min(W, H);
const side = Math.round(BOX * u);
const zone = (v) => ({x: Math.round(v.x * W - side / 2), y: Math.round(v.y * H - side / 2), w: side, h: side});
const [zt, zp, zv] = reel.vectors.map(zone);
const ROSE = hex('#FF2D95');
const VIOLET = hex('#7C3AED');
// 13,15 s : fondu de sortie EN COURS (les trois icones finissent a 13,3 s ; a 13,35 s elles seraient deja parties)
const instants = [10.05, 10.6, 11.6, 13.15];
const mesures = [];
let fails = 0;
const ok = (c, m) => {
	console.log(`${c ? 'OK   ' : 'ECHEC'} ${m}`);
	if (!c) fails++;
};
for (const t of instants) {
	const rel = +(t - DEBUT).toFixed(3);
	const png = path.join(box, `image-${t.toFixed(2)}s.png`);
	spawnSync(FFMPEG, ['-v', 'error', '-y', '-ss', String(rel), '-i', out, '-frames:v', '1', png]);
	const zoneTrait = raw(rel, zt.x, zt.y, zt.w, zt.h);
	const trait = compte(zoneTrait, [ROSE]);
	// rose meme a demi transparent (fondu) : rouge nettement au-dessus du vert
	let rosat = 0;
	for (let i = 0; i < zoneTrait.length; i += 3) if (zoneTrait[i] - zoneTrait[i + 1] > 70) rosat++;
	// pastille : bande sous l'icone (de 78 a 88 % de la boite), hors du dessin du telephone
	const disque = moyenne(raw(rel, zp.x + Math.round(side * 0.4), zp.y + Math.round(side * 0.8), Math.round(side * 0.2), Math.round(side * 0.06)));
	const verre = compte(raw(rel, zv.x, zv.y, zv.w, zv.h), [ROSE, VIOLET, hex('#FF5CB0'), hex('#A855F7')], 70);
	const m = {t, png, trait, rosat, disque, verre};
	mesures.push(m);
	console.log(`${t} s : trait ${trait} px roses (${rosat} rosés) · pastille ${disque} · verre ${verre} px roses / violets`);
}
const [a, b, c, d] = mesures;
ok(c.trait > 1500, `trait (charte) : la poignee de main est rose a ${c.t} s (${c.trait} px)`);
ok(a.trait < c.trait * 0.75, `trait : entree « pop » en cours a ${a.t} s (${a.trait} px < ${c.trait})`);
ok(dist(c.disque, ROSE) < 90, `plein : pastille rose de la charte (${c.disque} ~ ${ROSE})`);
ok(c.verre > 1500, `verre : icone en degrade rose -> violet + lueur (${c.verre} px)`);
ok(a.verre < 50, `verre : pas encore a l'image a ${a.t} s (entree a 10,3 s) : ${a.verre} px`);
ok(d.rosat > 1000 && d.trait < c.trait * 0.5 && d.verre < c.verre, `sortie en fondu EN COURS a ${d.t} s : trait encore visible a demi (${d.rosat} px rosés, ${d.trait} px roses francs < ${c.trait}), verre ${d.verre} < ${c.verre}`);
// planche des 4 images, regardee a la main
const planche = path.join(box, 'planche.png');
spawnSync(FFMPEG, ['-v', 'error', '-y', ...mesures.flatMap((m) => ['-i', m.png]), '-filter_complex',
	`${mesures.map((_, i) => `[${i}:v]scale=360:-1[v${i}]`).join(';')};${mesures.map((_, i) => `[v${i}]`).join('')}hstack=inputs=${mesures.length}`, planche]);
const haut = path.join(box, 'haut-11.6s.png');
spawnSync(FFMPEG, ['-v', 'error', '-y', '-i', c.png, '-vf', `crop=${W}:${Math.round(0.36 * H)}:0:0`, haut]);
fs.writeFileSync(path.join(box, 'mesures.json'), JSON.stringify({instants, mesures, zones: {zt, zp, zv}}, null, 1));
console.log(`VIDEO=${out}\nPLANCHE=${planche}\nHAUT=${haut}`);
console.log(`\n${6 - fails}/6 verifications reussies`);
process.exit(fails ? 1 : 0);
