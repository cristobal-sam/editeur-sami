// Planche de controle des icones (ronde 4) : vraies icones Lucide, 3 styles (trait, plein, verre), 4 palettes (style
// jaune, Tech bleu, charte rose, couleurs a la main), sur une vraie image de Video 1 — MEME code que l'image
// (remotion/src/vectors.tsx : prepareIcon, iconVars, IconView rendus en HTML statique). Verifie aussi, pour TOUTES les
// icones Lucide et les 3 styles, que l'habillage garde exactement les formes du fichier (svgShapes) et que le balisage ne
// depend pas des couleurs (variables CSS --ic-* seulement).
//   node docs/qualite-2026-09-30/icones/planche-icones.mjs     -> runtime/cache/tmp/icones-ronde4/visuel/planche.html
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../..');
const MODULES = path.join(ROOT, 'remotion', 'node_modules');
const OUT = path.join(ROOT, 'runtime', 'cache', 'tmp', 'icones-ronde4', 'visuel');
fs.mkdirSync(OUT, {recursive: true});
const esbuild = createRequire(path.join(MODULES, 'x.js'))('esbuild');
const bundle = path.join(OUT, `planche-${process.pid}.mjs`);
await esbuild.build({stdin: {contents: "export * from './remotion/src/vectors.tsx'; export {renderToStaticMarkup} from 'react-dom/server'; export {createElement} from 'react';",
	resolveDir: ROOT, loader: 'tsx'}, bundle: true, platform: 'node', format: 'esm', outfile: bundle, nodePaths: [MODULES], jsx: 'automatic',
	target: 'node20', logLevel: 'error', define: {'process.env.NODE_ENV': '"production"'},
	banner: {js: "import {createRequire as __cr} from 'node:module'; const require = __cr(import.meta.url);"}});
const V = await import(pathToFileURL(bundle).href);
fs.rmSync(bundle, {force: true});

let fails = 0;
let count = 0;
const ok = (c, m) => {
	count++;
	if (!c) {
		fails++;
		console.log(`ECHEC ${m}`);
	}
	return c;
};

// ---- 1. toutes les icones x 3 styles : formes gardees, balisage independant des couleurs
const LIB = path.join(ROOT, 'assets', 'banque', 'icones', 'lucide');
const noms = fs.readdirSync(LIB).filter((f) => f.endsWith('.svg')).map((f) => f.slice(0, -4));
let traces = 0;
for (const n of noms) {
	const txt = fs.readFileSync(path.join(LIB, `${n}.svg`), 'utf8');
	const ref = V.svgShapes(txt);
	for (const st of V.ICON_STYLES) {
		const ic = V.prepareIcon(txt, st, `t-${n}`);
		if (!ok(ic && ic.ratio === 1, `${n} (${st}) : habillage prepare`)) continue;
		// formes de l'icone dans l'habillage : memes balises et meme geometrie, dans le meme ordre (apres les formes du decor)
		const all = V.svgShapes(ic.markup);
		ok(JSON.stringify(all.slice(all.length - ref.length)) === JSON.stringify(ref), `${n} (${st}) : formes identiques au fichier`);
		// seuls les neutres du decor (blanc des reflets, noir des ombres, fumee du verre) sont ecrits en dur
		ok(!/#[0-9a-f]{6}/i.test(ic.markup.replace(/#FFFFFF|#000000|#0B1022/g, '')), `${n} (${st}) : aucune couleur de charte en dur (variables --ic-*)`);
		ok(!/<script|javascript:|href="http/i.test(ic.markup), `${n} (${st}) : rien d'executable ni d'externe`);
		if (st === 'trait' && ic.stages > 0) traces++;
	}
}
ok(traces === noms.length, `${traces}/${noms.length} icones au trait peuvent se « tracer » (animation Tracé)`);
console.log(`${noms.length} icones x 3 styles : formes gardees et balisage sans couleur en dur (${count - fails}/${count} verifications)`);

// ---- 2. couleurs : charte, style, a la main, derivees
const reelBase = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs/direction-creative-v2/tests/fixtures/projects/script2/reels/script.json'), 'utf8'));
const tech = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs/direction-creative-v2/tests/fixtures/projects/script1/reels/script.json'), 'utf8'));
const charte = {...structuredClone(reelBase), brand: {client: 'essai', name: 'Charte essai', logo: null, bannerBg: '#7C3AED', bannerColor: '#FFFFFF',
	style: {highlight: '#FF2D95'}, outro: {enabled: false, text: '', duration: 2}}};
const NUL = {principale: null, secondaire: null, contour: null};
const main = {couleurs: {principale: '#22C55E', secondaire: '#0EA5E9', contour: null}, couleursManuelles: true};
const vAuto = {couleurs: NUL, couleursManuelles: false};
ok(V.iconVars(reelBase, vAuto, 'trait')['--ic-a'] === '#FFD400', 'trait : couleur du style (jaune) sans charte');
ok(V.iconVars(charte, vAuto, 'verre')['--ic-a'] === '#FF2D95', 'verre : la charte recolore');
ok(V.iconVars(charte, vAuto, 'verre')['--ic-b'] === '#7C3AED', 'verre : 2e couleur du degrade = fond du bandeau de la charte (vive)');
ok(V.iconVars(reelBase, vAuto, 'verre')['--ic-b'] !== '#FFFFFF', 'verre sans couleur vive : teinte voisine (pas de degrade vers le blanc)');
ok(V.iconVars(charte, main, 'verre')['--ic-a'] === '#22C55E' && V.iconVars(charte, main, 'verre')['--ic-b'] === '#0EA5E9', 'couleurs a la main : gardees malgre la charte');
const on = V.iconVars(reelBase, vAuto, 'plein')['--ic-on'];
ok(V.contrastRatio(on, '#FFD400') >= 3, `plein : icone lisible sur la pastille jaune (${on}, contraste ${V.contrastRatio(on, '#FFD400').toFixed(1)})`);
ok(V.iconStyleOf({asset: 'banque/vecteurs/fleche.svg'}) === null, 'vecteur classique sans meta : rendu d’avant (pas une icone)');
ok(V.iconStyleOf({asset: 'banque/icones/lucide/phone.svg'}) === 'trait', 'icone posee sans meta : trait');
ok(V.iconStyleOf({asset: 'banque/icones/lucide/phone.svg', meta: {icone: {style: 'verre'}}}) === 'verre', 'meta.icone.style fait foi');
ok(V.iconStyleOf({asset: 'banque/vecteurs/argent.svg', meta: {icone: {style: 'plein'}}}) === 'plein', 'un vecteur peut etre habille en icone');
ok(V.iconStyleOf({asset: 'banque/import/../../x.png'}) === null && V.iconStyleOf({asset: 'banque/vecteurs/x.png'}) === null, 'chemins refuses');

// ---- 2b. icones de packs achetes (relecture ronde 4) : classes <style> d'Illustrator, monochrome ecrit en dur (Figma),
// multicolore et degrade gardes ; formes toujours identiques au fichier
const PACKS = {
	illustrator: '<svg id="Calque_1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><style>.cls-1{fill:#1d1d1b;}.cls-2{fill:none;stroke:#1d1d1b;stroke-width:3px;}</style></defs><path class="cls-1" d="M10 10h20v20H10z"/><circle class="cls-2" cx="44" cy="44" r="10"/></svg>',
	figma: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 12h16" stroke="#1E1E1E" stroke-width="2"/></svg>',
	multi: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><style>.a{fill:#e94e1b}.b{fill:#2a7de1}</style></defs><path class="a" d="M0 0h32v32H0z"/><path class="b" d="M32 32h32v32H32z"/></svg>',
	deuxTons: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0h12v12H0z"/><path fill="#ff0000" d="M12 12h12v12H12z"/></svg>',
	logo: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#E30613"><path d="M0 0h24v24H0z"/></svg>',
};
const LOGO2 = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#E30613"><path d="M0 0h24v24H0z"/><path fill="#ffffff" d="M8 9h8v2H8z"/></svg>';
for (const st of V.ICON_STYLES) {
	ok(/fill="#E30613"/.test(V.prepareIcon(PACKS.logo, st, 'pk').markup), `logo d'une couleur vive (${st}) : sa couleur reste`);
	const m = V.prepareIcon(LOGO2, st, 'pk').markup;
	ok(/fill="#E30613"/.test(m) && /fill="#ffffff"/.test(m), `logo rouge a barres blanches (${st}) : les deux couleurs restent`);
}
for (const st of V.ICON_STYLES) {
	for (const [k, txt] of Object.entries(PACKS)) {
		const m = V.prepareIcon(txt, st, `pk-${k}`).markup;
		const ref = V.svgShapes(txt);
		ok(JSON.stringify(V.svgShapes(m).slice(-ref.length)) === JSON.stringify(ref), `pack ${k} (${st}) : formes identiques au fichier`);
	}
	ok(!/1d1d1b/i.test(V.prepareIcon(PACKS.illustrator, st, 'pk').markup), `pack Illustrator monochrome (${st}) : recolore (classes lues)`);
	ok(!/1E1E1E/i.test(V.prepareIcon(PACKS.figma, st, 'pk').markup), `pack Figma monochrome (${st}) : recolore`);
	ok(/#e94e1b/i.test(V.prepareIcon(PACKS.multi, st, 'pk').markup) && /#2a7de1/i.test(V.prepareIcon(PACKS.multi, st, 'pk').markup), `pack multicolore (${st}) : couleurs gardees`);
	ok(/#ff0000/.test(V.prepareIcon(PACKS.deuxTons, st, 'pk').markup), `pack deux tons (${st}) : 2e couleur gardee`);
}

// ---- 3. planche HTML (regardee au navigateur)
const ICONES = ['handshake', 'banknote', 'piggy-bank', 'phone', 'smartphone', 'house', 'shield-check', 'trending-up', 'calendar-check', 'megaphone',
	'graduation-cap', 'heart-pulse', 'hand-coins', 'target', 'circle-check-big', 'rocket'];
const PALETTES = [['Style jaune (Vidéo 1)', reelBase, vAuto], ['Tech bleu', tech, vAuto], ['Charte rose', charte, vAuto], ['À la main (vert / bleu)', charte, main]];
const fond = path.join(OUT, 'fond.jpg');
if (!fs.existsSync(fond)) spawnSync(path.join(ROOT, 'tools/ffmpeg/bin/ffmpeg.exe'), ['-v', 'error', '-y', '-ss', '12', '-i',
	path.join(ROOT, 'projects/_cache/optimises/1-1aa57d0d.mp4'), '-frames:v', '1', '-vf', 'scale=540:-1', fond]);
const cell = (n, st, reel, v, size) => {
	const txt = fs.readFileSync(path.join(LIB, `${n}.svg`), 'utf8');
	const svg = V.prepareIcon(txt, st, `p-${n}-${st}-${size}-${Math.random().toString(36).slice(2, 7)}`);
	const html = V.renderToStaticMarkup(V.createElement(V.IconView, {svg, style: st, vars: V.iconVars(reel, v, st), size}));
	return `<div class="ic" style="width:${size}px;height:${size}px" title="${n} · ${st}">${html}</div>`;
};
let rows = '';
for (const [titre, reel, v] of PALETTES) {
	for (const st of V.ICON_STYLES) {
		rows += `<div class="row"><div class="lab">${titre}<br><b>${st}</b></div>${ICONES.slice(0, 8).map((n) => cell(n, st, reel, v, 96)).join('')}</div>`;
	}
}
const grand = V.ICON_STYLES.map((st) => cell('handshake', st, reelBase, vAuto, 220) + cell('banknote', st, charte, vAuto, 220)).join('');
fs.writeFileSync(path.join(OUT, 'planche.html'), `<!doctype html><meta charset="utf-8"><title>Planche icones</title><style>
body{margin:0;background:#111 url(fond.jpg) center/cover fixed;font:13px system-ui;color:#fff}
.row{display:flex;align-items:center;gap:14px;padding:8px 14px;background:linear-gradient(90deg,#0008,#0000)}
.lab{width:150px;flex:none;text-shadow:0 1px 3px #000}.ic{flex:none}.grand{display:flex;gap:40px;padding:30px;flex-wrap:wrap}
</style><div class="grand">${grand}</div>${rows}`);
console.log(`PLANCHE=${path.join(OUT, 'planche.html')}`);
console.log(`\n${count - fails}/${count} verifications reussies`);
process.exit(fails ? 1 : 0);
