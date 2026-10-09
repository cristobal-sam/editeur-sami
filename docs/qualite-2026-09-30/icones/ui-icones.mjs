// Ronde 4 « icônes » : onglet Banque → Icônes et panneau Vecteurs dans un vrai navigateur (Chrome Headless Shell de
// Remotion), sur la COPIE ISOLEE lancee par test-serveur-banque.mjs --garder --medias --port <port> (jamais le vrai
// serveur 8790).
//   node docs/qualite-2026-09-30/icones/ui-icones.mjs <bac> [port]
// Verifie : filtre « Icônes », recherche « poignée de main », bascule trait / plein / verre de l'apercu, « + Ajouter » a la
// tete de lecture (vecteur + meta.icone ecrit sur le disque DU BAC), style et couleurs dans Graphismes → Vecteurs,
// « Couleurs de la charte ». Captures dans <bac>/interface-icones/.
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../..');
const FIX = path.join(REAL, 'docs/direction-creative-v2/tests/fixtures');
const [box, port = '18841'] = process.argv.slice(2);
if (!box || !fs.existsSync(path.join(box, 'app/server.mjs')) || !path.resolve(box).startsWith(path.join(REAL, 'runtime', 'cache', 'tmp'))) {
	throw new Error('Bac de test attendu (runtime/cache/tmp/dcv2-banque/serveur-…) en premier argument.');
}
const URL0 = `http://127.0.0.1:${port}/`;
const OUT = path.join(box, 'interface-icones');
fs.mkdirSync(OUT, {recursive: true});
const reelBac = (p) => path.join(box, `projects/${p}/reels/script.json`);
fs.copyFileSync(path.join(FIX, 'projects/script2/reels/script.json'), reelBac('script2'));
const disque = (p) => JSON.parse(fs.readFileSync(reelBac(p), 'utf8'));

let fails = 0;
let count = 0;
const ok = (cond, msg) => {
	count++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${msg}`);
	if (!cond) fails++;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const CHROME = path.join(REAL, 'remotion/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe');
const DBG = 9391;
const chrome = spawn(CHROME, [`--remote-debugging-port=${DBG}`, `--user-data-dir=${path.join(OUT, 'profil-chrome')}`, '--no-first-run',
	'--window-size=1600,1000', '--mute-audio', 'about:blank'], {stdio: 'ignore', windowsHide: true});
let ws;
const pending = new Map();
const erreurs = [];
let seq = 0;
const send = (method, params = {}) => new Promise((res, rej) => {
	const id = ++seq;
	pending.set(id, (d) => (d.error ? rej(new Error(`${method} : ${JSON.stringify(d.error)}`)) : res(d.result)));
	ws.send(JSON.stringify({id, method, params}));
});
const ev = async (expression) => {
	const r = await send('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true, userGesture: true});
	if (r.exceptionDetails) throw new Error(`${expression.slice(0, 80)}… : ${r.exceptionDetails.exception?.description ?? r.exceptionDetails.text}`);
	return r.result.value;
};
const shot = async (nom, clip) => {
	const r = await send('Page.captureScreenshot', {format: 'png', ...(clip ? {clip: {...clip, scale: 1}} : {})});
	fs.writeFileSync(path.join(OUT, nom), Buffer.from(r.data, 'base64'));
	console.log(`      capture : ${path.join(OUT, nom)}`);
};
const attendre = async (expr, ms = 15000) => {
	for (const fin = Date.now() + ms; Date.now() < fin; await sleep(150)) if (await ev(expr)) return true;
	return false;
};
const JS = `
window.__b = (txt, root = document) => [...root.querySelectorAll('button')].find((b) => b.textContent.replace(/\\s+/g, ' ').trim().startsWith(txt));
window.__set = (el, v) => { const d = Object.getOwnPropertyDescriptor(el.constructor.prototype, 'value'); d.set.call(el, v);
	el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', {bubbles: true})); };
window.__cartes = () => [...document.querySelectorAll('.bq-card')].map((c) => ({nom: c.querySelector('.bq-name')?.textContent, meta: c.querySelector('.bq-meta')?.textContent,
	lic: c.querySelector('.bq-lic')?.textContent, svg: c.querySelectorAll('.bq-prev svg').length, givre: [...c.querySelectorAll('.bq-prev div')].some((d) => d.style.backdropFilter)}));
window.__ajouter = (nom) => { const c = [...document.querySelectorAll('.bq-card')].find((x) => x.querySelector('.bq-name')?.textContent === nom);
	if (!c) return false; c.querySelector('.bq-actions button').click(); return true; };
window.__panneau = () => document.querySelector('.panel');
`;
const seek = async (t) => {
	const p = await ev(`(() => { const sc = document.querySelector('.tl-scroll'); const spans = [...sc.querySelectorAll('.tl-ruler > span')];
		const zoom = parseFloat(spans[1].style.left) / 5; sc.scrollLeft = Math.max(0, ${t} * zoom - 200);
		const r = sc.querySelector('.tl-ruler').getBoundingClientRect(); const b = sc.getBoundingClientRect();
		return {x: b.left - sc.scrollLeft + ${t} * zoom, y: r.top + r.height / 2}; })()`);
	for (const type of ['mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', {type, x: p.x, y: p.y, button: 'left', clickCount: 1});
	await sleep(400);
};
const zonePanneau = async () => ev(`(() => { const r = document.querySelector('.panel').getBoundingClientRect(); return {x: r.left, y: r.top, width: r.width, height: Math.min(r.height, 1000 - r.top)}; })()`);

try {
	let list;
	for (let k = 0; k < 60 && !list; k++) {
		try {
			list = (await (await fetch(`http://127.0.0.1:${DBG}/json/list`)).json()).find((x) => x.type === 'page');
		} catch {
			await sleep(250);
		}
	}
	ws = new WebSocket(list.webSocketDebuggerUrl);
	await new Promise((r) => (ws.onopen = r));
	ws.onmessage = (m) => {
		const d = JSON.parse(m.data);
		if (d.id && pending.has(d.id)) {
			pending.get(d.id)(d);
			pending.delete(d.id);
		} else if (d.method === 'Runtime.exceptionThrown') erreurs.push(d.params.exceptionDetails?.exception?.description ?? d.params.exceptionDetails?.text);
		else if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') erreurs.push(d.params.args.map((a) => a.value ?? a.description).join(' '));
	};
	await send('Runtime.enable');
	await send('Page.enable');
	await send('Emulation.setDeviceMetricsOverride', {width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false});
	await send('Page.navigate', {url: URL0});
	await attendre(`document.readyState === 'complete' && !!document.querySelector('button')`);
	await ev(JS);
	// editeur : bouton « Éditeur complet » (ancienne interface) ou onglet « Éditeur » de la barre du haut (maquette, ronde 4a)
	await ev(`(__b('Éditeur complet') ?? [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Éditeur'))?.click()`);
	const SEL = `[...document.querySelectorAll('select')].find((s) => [...s.options].some((o) => /^script\\d\\//.test(o.value)))`;
	await attendre(`!!${SEL}`, 20000);
	await ev(JS);
	const opt = await ev(`[...${SEL}.options].map((o) => [o.value, o.textContent])`);
	const v2 = opt.find(([v]) => /^script2\//.test(v))?.[0] ?? opt[0][0];
	await ev(`__set(${SEL}, ${JSON.stringify(v2)})`);
	await attendre(`!!document.querySelector('.tl-scroll .tl-ruler > span:nth-child(2)')`, 30000);
	await sleep(1500);
	await ev(`[...document.querySelectorAll('.tabs:not(.more) > button')].find((b) => (b.title || '').startsWith('Réglages de monteur'))?.click()`);
	await ev(`__b('Banque', document.querySelector('.tabs.more')).click()`);
	ok(await attendre(`document.querySelectorAll('.bq-card').length > 0`, 30000), 'Plus → Banque : la grille se remplit');

	// 1. filtre « Icônes » + recherche en francais
	const types = await ev(`[...document.querySelectorAll('.bq-types button')].map((b) => b.textContent)`);
	ok(types.some((t) => /^Icônes\s*\d{4}/.test(t)), `filtre de type « Icônes » avec son nombre : ${types.join(' | ')}`);
	await ev(`__b('Icônes', document.querySelector('.bq-types')).click()`);
	await sleep(600);
	const c1 = await ev('__cartes()');
	ok(c1.length === 48 && c1.every((c) => /Lucide|vérifier/.test(c.lic)), `Icônes : ${c1.length} cartes, licence affichée (« ${c1[0]?.lic} »)`);
	ok(await ev(`!!__b('Verre') && !!__b('Plein') && !!__b('Trait')`), 'bascule « Style des icônes » trait / plein / verre');
	await ev(`__set(document.querySelector('.bq-search'), 'poignée de main')`);
	await attendre(`document.querySelectorAll('.bq-card .bq-prev svg').length >= 2`, 8000);
	await sleep(500);
	const c2 = await ev('__cartes()');
	ok(c2[0]?.nom === 'Poignée de main' && c2[1]?.nom === 'Poignée de main et cœur', `« poignée de main » : ${c2.map((c) => c.nom).join(', ')}`);
	for (const st of ['Trait', 'Plein', 'Verre']) {
		await ev(`__b(${JSON.stringify(st)}).click()`);
		await sleep(400);
		const c = (await ev('__cartes()'))[0];
		ok(c.svg >= 2 && (st === 'Verre') === c.givre, `apercu « ${st} » : icône dessinée (${c.svg} svg)${st === 'Verre' ? ', verre givré (flou de l’arrière-plan)' : ''}`);
		await shot(`icones-${st.toLowerCase()}.png`, await zonePanneau());
	}
	await ev(`__set(document.querySelector('.bq-search'), 'argent')`);
	await sleep(700);
	const c3 = await ev('__cartes()');
	ok(['Billet de banque', 'Pièces de monnaie', 'Tirelire'].every((n) => c3.slice(0, 12).some((c) => c.nom === n)), `« argent » : ${c3.slice(0, 6).map((c) => c.nom).join(', ')}…`);
	await shot('icones-argent-verre.png', await zonePanneau());

	// 2. ajouter a la tete de lecture, au style choisi (verre)
	await seek(15.2);
	await ev(`__set(document.querySelector('.bq-search'), 'tirelire')`);
	await sleep(500);
	ok(await ev(`__ajouter('Tirelire')`), '« + Ajouter » sur « Tirelire » (style verre)');
	await sleep(400);
	const fait = await ev(`document.querySelector('.bq-done h3')?.textContent`);
	ok(/Tirelire.*ajouté à 0:15/.test(fait ?? ''), `confirmation : « ${fait} »`);
	ok(await ev(`!!__b('Plein', document.querySelector('.bq-done'))`), 'retouche rapide : style de l’icône proposé');
	await ev(`__b('Plein', document.querySelector('.bq-done')).click()`);
	await sleep(3000); // sauvegarde automatique
	let v = (disque('script2').vectors ?? []).find((x) => x.meta?.icone?.banque === 'icone:lucide:piggy-bank');
	ok(v && v.asset === 'banque/icones/lucide/piggy-bank.svg' && v.manual && Math.abs(v.at - 15.2) < 0.08 && v.couleurs.principale === null && v.meta.icone.style === 'plein',
		`sur le disque : vecteur ${v?.asset} à ${v?.at} s, style ${v?.meta?.icone?.style}, couleurs de la charte`);
	await seek(15.9);
	await sleep(1500);
	await shot('apercu-tirelire-plein.png');
	ok(await ev(`!!document.querySelector('[data-vecteur] svg')`), 'aperçu (lecteur) : l’icône est à l’image');

	// 3. Graphismes → Vecteurs : style, couleurs, « Couleurs de la charte »
	if (!(await ev(`!!document.querySelector('.tabs.more')`))) {
		await ev(`[...document.querySelectorAll('.tabs:not(.more) > button')].find((b) => (b.title || '').startsWith('Réglages de monteur'))?.click()`);
		await attendre(`!!document.querySelector('.tabs.more')`, 3000);
	}
	await ev(`__b('Graphismes', document.querySelector('.tabs.more')).click()`);
	await sleep(800);
	await ev(JS);
	const titre = await ev(`[...document.querySelectorAll('.card.vec h3')].map((h) => h.textContent).find((x) => /Tirelire/.test(x)) ?? ''`);
	ok(/Tirelire.*icône · plein/.test(titre), `panneau Vecteurs : « ${titre} »`);
	await ev(`(() => { const c = [...document.querySelectorAll('.card.vec')].find((x) => /Tirelire/.test(x.querySelector('h3').textContent)); __b('Modifier', c).click(); })()`);
	await sleep(400);
	const labels = await ev(`[...document.querySelectorAll('.card.vec .vec-color span')].map((s) => s.textContent)`);
	ok(labels.join(',') === 'Pastille,Icône', `couleurs du style plein : ${labels.join(', ')}`);
	await ev(`__b('Verre', [...document.querySelectorAll('.card.vec')].find((x) => /Tirelire/.test(x.querySelector('h3').textContent))).click()`);
	await sleep(500);
	const labels2 = await ev(`[...document.querySelectorAll('.card.vec .vec-color span')].map((s) => s.textContent)`);
	ok(labels2.join(',') === 'Dégradé 1,Dégradé 2', `style verre choisi : couleurs ${labels2.join(', ')}`);
	await ev(`(() => { const i = document.querySelector('.card.vec .vec-color input[type=color]'); const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
		d.set.call(i, '#00c2ff'); i.dispatchEvent(new Event('input', {bubbles: true})); i.dispatchEvent(new Event('change', {bubbles: true})); })()`);
	await sleep(3000);
	v = (disque('script2').vectors ?? []).find((x) => x.meta?.icone?.banque === 'icone:lucide:piggy-bank');
	ok(v?.meta?.icone?.style === 'verre' && v.couleursManuelles && v.couleurs.principale === '#00C2FF', `sur le disque : verre, couleur choisie ${v?.couleurs?.principale}`);
	await ev(`[...document.querySelectorAll('.card.vec')].find((x) => /Tirelire/.test(x.querySelector('h3').textContent)).scrollIntoView({block: 'start'})`);
	await sleep(300);
	await shot('vecteurs-tirelire-verre.png', await zonePanneau());
	await ev(`__b('🎨 Couleurs de la charte').click()`);
	await sleep(3000);
	v = (disque('script2').vectors ?? []).find((x) => x.meta?.icone?.banque === 'icone:lucide:piggy-bank');
	ok(v && !v.couleursManuelles && v.couleurs.principale === null && v.meta.icone.style === 'verre', '« Couleurs de la charte » : la charte recolore à nouveau, style gardé');
	ok(!erreurs.length, `aucune erreur dans la page${erreurs.length ? ` : ${erreurs.slice(0, 3).join(' | ')}` : ''}`);
} catch (e) {
	fails++;
	console.log('ECHEC', e?.stack ?? e);
} finally {
	try {
		ws?.close();
	} catch {}
	chrome.kill();
	console.log(`\n${count - fails}/${count} verifications interface (icones) reussies`);
	process.exitCode = fails ? 1 : 0;
}
