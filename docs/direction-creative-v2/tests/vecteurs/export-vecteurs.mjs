// Export court de controle (3 s) avec 3 vecteurs, par le VRAI export (remotion/render.mjs), puis mesures sur les images.
//   node docs/direction-creative-v2/tests/vecteurs/export-vecteurs.mjs        (environnement charge : runtime/env.sh)
// Reel : COPIE EN MEMOIRE du reel fige fixtures/projects/script2 (rien n'est ecrit dans projects/, media/ ni livraisons/) + une charte d'essai
// (rose #FF2D95, bandeau violet). Vecteurs : etoile (couleurs de la charte, pop), coeur (couleurs choisies a la main :
// bleu / marine / blanc, zoom + battement), fleche courbe (charte, se dessine puis s'efface).
// Sortie : runtime/cache/tmp/dcv2-vecteurs/export-<hasard>/ (video, 3 images PNG, mesures.json).
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {ROOT, TMP} from './charger.mjs';

const FFMPEG = path.join(ROOT, 'tools', 'ffmpeg', 'bin', 'ffmpeg.exe');
const reel = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs/direction-creative-v2/tests/fixtures/projects/script2/reels/script.json'), 'utf8')); // copie figee
const DEBUT = 10;
const FIN = 13;
reel.brand = {client: 'essai', name: 'Charte essai', logo: null, logoPosition: 'haut-droite', logoSize: 0.16, logoOpacity: 0.85,
	bannerBg: '#7C3AED', bannerColor: '#FFFFFF', style: {highlight: '#FF2D95'}, outro: {enabled: false, text: '', duration: 2.5}};
reel.style = {...reel.style, highlight: '#FF2D95'};
const NUL = {principale: null, secondaire: null, contour: null};
const vec = (id, nom, o) => ({id, asset: `banque/vecteurs/${nom}.svg`, rotation: 0, opacite: 1, couleurs: {...NUL}, couleursManuelles: false, manual: true, ...o});
reel.vectors = [
	vec('v-etoile', 'etoile', {at: 10.0, duration: 3.0, x: 0.25, y: 0.28, w: 0.32, anim: {entree: 'pop', sortie: 'fondu'}, raison: 'essai : charte'}),
	vec('v-coeur', 'coeur', {at: 10.2, duration: 2.6, x: 0.75, y: 0.28, w: 0.32, anim: {entree: 'zoom', sortie: 'fondu'},
		couleurs: {principale: '#00C2FF', secondaire: '#0A2A66', contour: '#FFFFFF'}, couleursManuelles: true, raison: 'essai : couleurs a la main'}),
	vec('v-fleche', 'fleche-courbe', {at: 10.3, duration: 2.5, x: 0.5, y: 0.5, w: 0.55, rotation: -8, anim: {entree: 'trace', sortie: 'trace'}, raison: 'essai : trace'}),
];
fs.mkdirSync(TMP, {recursive: true});
const box = fs.mkdtempSync(path.join(TMP, 'export-'));
const out = path.join(box, 'vecteurs-3s.mp4');
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

// ---- mesures : couleur au centre de l'etoile et du coeur, pixels de la fleche (trait rose) a 3 instants ----
const W = reel.width;
const H = reel.height;
const raw = (t, x, y, w, h) => {
	const r = spawnSync(FFMPEG, ['-v', 'error', '-ss', String(t), '-i', out, '-frames:v', '1', '-vf', `crop=${w}:${h}:${x}:${y}`, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
		{maxBuffer: 1 << 26});
	return r.stdout;
};
const moyenne = (buf) => {
	const n = buf.length / 3;
	const s = [0, 0, 0];
	for (let i = 0; i < buf.length; i += 3) for (let k = 0; k < 3; k++) s[k] += buf[i + k];
	return s.map((v) => Math.round(v / n));
};
const hex = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const compte = (buf, ref, tol = 70) => {
	let n = 0;
	for (let i = 0; i < buf.length; i += 3) if (dist([buf[i], buf[i + 1], buf[i + 2]], ref) < tol) n++;
	return n;
};
// centres (px) : x*W, y*H ; l'etoile a son centre de remplissage un peu sous le milieu de la boite
const etoile = {x: Math.round(0.25 * W), y: Math.round(0.28 * H + 0.32 * W * (3 / 230))};
const coeur = {x: Math.round(0.75 * W), y: Math.round(0.28 * H)};
const fleche = {x: Math.round(0.5 * W - 0.55 * W * 0.6), y: Math.round(0.5 * H - 0.55 * W * (220 / 300) * 0.62), w: Math.round(0.55 * W * 1.2)};
fleche.h = Math.min(Math.round(0.55 * W * (220 / 300) * 1.24), Math.round(0.63 * H) - fleche.y); // au-dessus des sous-titres
const ROSE = hex('#FF2D95');
const BLEU = hex('#00C2FF');
const instants = [10.45, 11.5, 12.62];
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
	const ce = moyenne(raw(rel, etoile.x - 6, etoile.y - 6, 12, 12));
	const cc = moyenne(raw(rel, coeur.x - 6, coeur.y - 6, 12, 12));
	const zone = raw(rel, fleche.x, fleche.y, fleche.w, fleche.h);
	const m = {t, png, etoile: ce, coeur: cc, flecheRose: compte(zone, ROSE)};
	mesures.push(m);
	console.log(`${t} s : etoile ${ce} · coeur ${cc} · pixels roses de la fleche ${m.flecheRose}`);
}
const [a, b, c] = mesures;
ok(dist(b.etoile, ROSE) < 60, `etoile (charte) : rose de la charte au centre (${b.etoile} ~ ${ROSE})`);
ok(dist(b.coeur, BLEU) < 60, `coeur (couleurs a la main) : bleu choisi au centre malgre la charte (${b.coeur} ~ ${BLEU})`);
ok(dist(a.coeur, BLEU) < 90, `coeur en cours de zoom a ${a.t} s : deja bleu au centre (${a.coeur})`);
ok(a.flecheRose > 200 && a.flecheRose < b.flecheRose * 0.7, `fleche : le trait se dessine (${a.flecheRose} px a ${a.t} s < ${b.flecheRose} px a ${b.t} s)`);
ok(c.flecheRose > 100 && c.flecheRose < b.flecheRose * 0.85, `fleche : le trait s'efface en sortie (${c.flecheRose} px a ${c.t} s)`);
fs.writeFileSync(path.join(box, 'mesures.json'), JSON.stringify({instants, mesures, zones: {etoile, coeur, fleche}}, null, 1));
console.log(`VIDEO=${out}`);
process.exit(fails ? 1 : 0);
