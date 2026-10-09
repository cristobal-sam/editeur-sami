// Essai de l'interface (onglet Graphismes -> Vecteurs) dans un Chrome sans fenetre, sur le SERVEUR DE TEST isole
// (test-http-vecteurs.mjs --garder, port 18811). Pilote par le protocole DevTools (aucune dependance), captures pleine taille.
//   node docs/direction-creative-v2/tests/vecteurs/ui-vecteurs.mjs <dossier du bac serveur-XXXX>
// Verifie : liste des vecteurs, ajout depuis la grille, recoloration a la main (couleursManuelles), « Couleurs de la charte »,
// cadenas, taille, animation, sauvegarde sur le disque du bac, rendu dans le lecteur, aucune erreur dans la console.
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {ROOT, TMP} from './charger.mjs';

const BOX = process.argv[2];
if (!BOX || !fs.existsSync(path.join(BOX, 'projects/script2/reels/script.json'))) throw new Error('Donne le dossier du bac serveur (serveur-XXXX).');
const BASE = 'http://127.0.0.1:18811';
const REEL = path.join(BOX, 'projects/script2/reels/script.json');
const disk = () => JSON.parse(fs.readFileSync(REEL, 'utf8'));
const OUT = fs.mkdtempSync(path.join(TMP, 'ui-'));
const CHROME = path.join(ROOT, 'remotion/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe');
const PORT = 9337;
const chrome = spawn(CHROME, ['--headless', '--no-sandbox', '--disable-gpu', `--remote-debugging-port=${PORT}`, `--user-data-dir=${path.join(OUT, 'profil')}`,
	'--hide-scrollbars', '--window-size=1500,1000', 'about:blank'], {stdio: 'ignore', windowsHide: true});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let fails = 0;
let count = 0;
const ok = (c, m) => {
	count++;
	console.log(`${c ? 'OK   ' : 'ECHEC'} ${m}`);
	if (!c) fails++;
};
const erreurs = [];
try {
	let target;
	for (let k = 0; k < 60 && !target; k++) {
		try {
			target = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find((t) => t.type === 'page');
		} catch {
			await sleep(250);
		}
	}
	const ws = new WebSocket(target.webSocketDebuggerUrl);
	await new Promise((r) => ws.addEventListener('open', r, {once: true}));
	let id = 0;
	const wait = new Map();
	ws.addEventListener('message', (e) => {
		const m = JSON.parse(e.data);
		if (m.id && wait.has(m.id)) {
			wait.get(m.id)(m);
			wait.delete(m.id);
		}
		if (m.method === 'Runtime.exceptionThrown') erreurs.push(m.params.exceptionDetails?.exception?.description ?? m.params.exceptionDetails?.text);
		if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') erreurs.push(m.params.args.map((a) => a.value ?? a.description).join(' '));
		if (m.method === 'Log.entryAdded' && m.params.entry.level === 'error') erreurs.push(`${m.params.entry.text} ${m.params.entry.url ?? ''}`);
	});
	const cdp = (method, params = {}) => new Promise((r) => {
		const n = ++id;
		wait.set(n, r);
		ws.send(JSON.stringify({id: n, method, params}));
	});
	const js = async (expr) => (await cdp('Runtime.evaluate', {expression: expr, awaitPromise: true, returnByValue: true})).result?.result?.value;
	const until = async (expr, ms = 15000) => {
		for (let t = 0; t < ms; t += 200) {
			if (await js(expr)) return true;
			await sleep(200);
		}
		return false;
	};
	const shot = async (name, clip) => {
		const r = await cdp('Page.captureScreenshot', {format: 'png', ...(clip ? {clip: {...clip, scale: 1}} : {})});
		const f = path.join(OUT, `${name}.png`);
		fs.writeFileSync(f, Buffer.from(r.result.data, 'base64'));
		console.log(`CAPTURE ${f}`);
	};
	await cdp('Runtime.enable');
	await cdp('Log.enable');
	await cdp('Page.enable');
	await cdp('Emulation.setDeviceMetricsOverride', {width: 1500, height: 1000, deviceScaleFactor: 1, mobile: false});
	await cdp('Page.navigate', {url: BASE});
	const clic = (txt, sel = 'button') => js(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(sel)})].find((b) => b.textContent.trim() === ${JSON.stringify(txt)} || b.textContent.includes(${JSON.stringify(txt)}) || (b.title || '').includes(${JSON.stringify(txt)})); if (!el) return false; el.scrollIntoView({block: 'center'}); el.click(); return true; })()`);
	ok(await until(`!![...document.querySelectorAll('button')].find((b) => (b.title||'').includes('éditeur complet'))`), 'page d\'accueil chargee');
	await clic('éditeur complet');
	ok(await until(`!![...document.querySelectorAll('button')].find((b) => b.textContent.includes('Réglages de monteur') || (b.title||'').includes('Réglages'))`), 'editeur ouvert');
	await clic('Réglages de monteur');
	await sleep(300);
	ok(await clic('Graphismes', 'button, [role=menuitem], .more-menu *'), 'Plus -> Graphismes');
	ok(await until(`!!document.querySelector('.vec-panel')`), 'carte « Vecteurs » affichee sous les graphismes');
	const cartes = await js(`[...document.querySelectorAll('.card.vec')].map((c) => c.querySelector('h3').textContent)`);
	ok(cartes?.length === 3, `3 vecteurs listes : ${JSON.stringify(cartes)}`);
	ok(await js(`document.querySelectorAll('.card.vec .vec-thumb svg').length === 3`), 'miniatures : le vrai SVG insere en ligne');
	await js(`document.querySelector('.vec-panel').scrollIntoView({block: 'start'})`);
	await shot('1-liste');

	// ajout depuis la grille
	await clic('+ Ajouter un vecteur');
	ok(await until(`document.querySelectorAll('.vec-grid button').length >= 30`), 'grille de la bibliotheque (>= 30 vecteurs)');
	await sleep(600);
	await shot('2-grille');
	await clic('Oui / non', '.vec-panel .presets button');
	await sleep(200);
	const filtres = await js(`[...document.querySelectorAll('.vec-grid button span:last-child')].map((s) => s.textContent)`);
	ok(filtres?.length === 3 && filtres.includes('Case cochée'), `filtre « Oui / non » : ${JSON.stringify(filtres)}`);
	await clic('Tous', '.vec-panel .presets button');
	await sleep(200);
	ok(await clic('Cercle griffonné', '.vec-grid button'), 'clic sur « Cercle griffonné »');
	ok(await until(`document.querySelectorAll('.card.vec').length === 4`), 'vecteur ajoute (4 cartes)');
	await sleep(800);
	let r = disk();
	const neuf = r.vectors?.find((v) => v.asset === 'banque/vecteurs/cercle-griffonne.svg');
	ok(neuf && neuf.manual === true && neuf.couleursManuelles === false && neuf.anim.entree === 'trace' && neuf.w === 0.55 && neuf.duration === 2.2,
		`enregistre sur le disque : ${JSON.stringify(neuf && {manual: neuf.manual, couleursManuelles: neuf.couleursManuelles, anim: neuf.anim, w: neuf.w, d: neuf.duration})}`);
	await shot('3-ajoute-edition');

	// recolorer a la main : couleursManuelles + les deux autres figees
	const setColor = (i, hex) => js(`(() => { const inp = document.querySelectorAll('.card.vec.on .vec-colors input[type=color], .card.vec:not(.x) .vec-colors input[type=color]')[${i}];
		if (!inp) return false; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(inp, ${JSON.stringify(hex)});
		inp.dispatchEvent(new Event('input', {bubbles: true})); return true; })()`);
	ok(await setColor(0, '#00c2ff'), 'couleur principale choisie : #00C2FF');
	await sleep(800);
	r = disk();
	let v = r.vectors.find((x) => x.id === neuf.id);
	ok(v.couleursManuelles === true && v.couleurs.principale === '#00C2FF' && v.couleurs.contour === '#000000',
		`couleurs manuelles enregistrees, contour fige a la couleur affichee : ${JSON.stringify(v.couleurs)}`);
	ok(await js(`[...document.querySelectorAll('.card.vec')].some((c) => c.textContent.includes('Couleurs choisies'))`), 'message « Couleurs choisies : un changement de style… »');
	await shot('4-recolore');
	// retour a la charte
	ok(await clic('Couleurs de la charte'), 'clic « 🎨 Couleurs de la charte »');
	await sleep(800);
	v = disk().vectors.find((x) => x.id === neuf.id);
	ok(v.couleursManuelles === false && Object.values(v.couleurs).every((c) => c === null), `retour a la charte : ${JSON.stringify(v.couleurs)}`);
	// taille, animation, cadenas
	await js(`(() => { const inp = [...document.querySelectorAll('.card.vec input[type=range]')].find((i) => i.closest('.row').textContent.includes('Taille'));
		const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(inp, '0.3'); inp.dispatchEvent(new Event('input', {bubbles: true})); })()`);
	await js(`(() => { const s = [...document.querySelectorAll('.card.vec .vec-anim select')][0]; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
		set.call(s, 'glisse-gauche'); s.dispatchEvent(new Event('change', {bubbles: true})); })()`);
	await sleep(800);
	v = disk().vectors.find((x) => x.id === neuf.id);
	ok(v.w === 0.3 && v.anim.entree === 'glisse-gauche', `taille 30 % et entree « glisse par la gauche » : w=${v.w} ${v.anim.entree}`);
	await js(`(() => { const c = [...document.querySelectorAll('.card.vec')].find((c) => c.textContent.includes('Cercle griffonné')); c.querySelector('button.lock').click(); })()`);
	await sleep(800);
	v = disk().vectors.find((x) => x.id === neuf.id);
	ok(v.locked === true, 'cadenas : verrouille sur le disque');
	ok(await js(`[...document.querySelectorAll('.tl-gfx .vec')].some((d) => d.textContent.includes('🔒') && d.textContent.includes('cercle-griffonne'))`), 'piste Graphismes : 🔒 cercle-griffonne');

	// rendu dans le lecteur : aller a 20,5 s (explosion recoloree a la main, sans media : fond noir)
	await js(`(() => { const c = [...document.querySelectorAll('.card.vec')].find((c) => c.textContent.includes('Explosion')); c.querySelector('button[title="Voir à l\\'image"]').click(); })()`);
	await sleep(1500);
	const rendu = await js(`(() => { const d = document.querySelector('[data-vecteur="v-manuel"]'); if (!d) return null; const s = getComputedStyle(d);
		const p = d.querySelector('polygon'); return {principale: s.getPropertyValue('--v-principale'), fill: p && getComputedStyle(p).fill, w: d.getBoundingClientRect().width}; })()`);
	ok(rendu && rendu.principale.trim() === '#00C2FF' && rendu.fill === 'rgb(0, 194, 255)', `lecteur : explosion aux couleurs choisies (${JSON.stringify(rendu)})`);
	const lecteur = await js(`(() => { const r = document.querySelector('.player-wrap').getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; })()`);
	await shot('5-lecteur', lecteur);
	const vraies = erreurs.filter((e) => !/Failed to load resource|404|media|NotSupportedError|no supported source|Police|fonts\//i.test(e));
	ok(vraies.length === 0, `console : aucune erreur hors medias absents du bac (${vraies.slice(0, 3).join(' | ')})`);
	ws.close();
} finally {
	chrome.kill();
}
console.log(`\n${count - fails}/${count} verifications interface (vecteurs) reussies (captures : ${OUT})`);
process.exit(fails ? 1 : 0);
