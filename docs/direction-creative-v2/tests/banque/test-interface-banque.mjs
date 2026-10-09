// Onglet « Banque » dans un vrai navigateur (Chrome Headless Shell deja fourni avec Remotion, aucun telechargement), sur la
// COPIE ISOLEE lancee par test-serveur-banque.mjs --garder --medias --port 18832 (jamais le vrai serveur 8790).
//   node docs/direction-creative-v2/tests/banque/test-interface-banque.mjs <bac> [port]
// Ouvre l'editeur complet, Plus → Banque, cherche, filtre, ecoute, ajoute un vecteur, un modele et un son a l'instant choisi
// dans la timeline, verifie ce que la sauvegarde automatique a ecrit dans le reel DU BAC, puis passe a un reel avec
// habillage (Tech) : bruitages coupes signales, « Activer les bruitages », modele transforme en scene du style.
// Captures d'ecran (1600 x 1000) dans <bac>/interface/. Le reel script2 du bac est d'abord remis a la copie d'origine.
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../../..');
const FIX = path.join(REAL, 'docs/direction-creative-v2/tests/fixtures'); // donnees figees des tests (jamais projects/)
const [box, port = '18832'] = process.argv.slice(2);
if (!box || !fs.existsSync(path.join(box, 'app/server.mjs')) || !path.resolve(box).startsWith(path.join(REAL, 'runtime', 'cache', 'tmp'))) {
	throw new Error('Bac de test attendu (runtime/cache/tmp/dcv2-banque/serveur-…) en premier argument.');
}
const URL0 = `http://127.0.0.1:${port}/`;
const OUT = path.join(box, 'interface');
fs.mkdirSync(OUT, {recursive: true});
const reelBac = (p) => path.join(box, `projects/${p}/reels/script.json`);
fs.copyFileSync(path.join(FIX, 'projects/script2/reels/script.json'), reelBac('script2'));
fs.copyFileSync(path.join(FIX, 'projects/script1/reels/script.json'), reelBac('script1'));
const disque = (p) => JSON.parse(fs.readFileSync(reelBac(p), 'utf8'));

let fails = 0;
let count = 0;
const ok = (cond, msg) => {
	count++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${msg}`);
	if (!cond) fails++;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---- Chrome Headless Shell + protocole DevTools
const CHROME = path.join(REAL, 'remotion/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe');
const DBG = 9377;
const chrome = spawn(CHROME, [`--remote-debugging-port=${DBG}`, `--user-data-dir=${path.join(OUT, 'profil-chrome')}`, '--no-first-run',
	'--window-size=1600,1000', '--autoplay-policy=no-user-gesture-required', '--mute-audio', 'about:blank'], {stdio: 'ignore', windowsHide: true});
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
const shot = async (nom) => {
	const r = await send('Page.captureScreenshot', {format: 'png'});
	fs.writeFileSync(path.join(OUT, nom), Buffer.from(r.data, 'base64'));
	console.log(`      capture : ${path.join(OUT, nom)}`);
};
const attendre = async (expr, ms = 15000) => {
	for (const fin = Date.now() + ms; Date.now() < fin; await sleep(150)) if (await ev(expr)) return true;
	return false;
};
// helpers dans la page : bouton par texte, champ React (setter natif + evenement)
const JS = `
window.__b = (txt, root = document) => [...root.querySelectorAll('button')].find((b) => b.textContent.replace(/\\s+/g, ' ').trim().startsWith(txt));
window.__set = (el, v) => { const d = Object.getOwnPropertyDescriptor(el.constructor.prototype, 'value'); d.set.call(el, v);
	el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', {bubbles: true})); };
window.__cartes = () => [...document.querySelectorAll('.bq-card')].map((c) => ({nom: c.querySelector('.bq-name')?.textContent, meta: c.querySelector('.bq-meta')?.textContent,
	note: c.querySelector('.bq-note')?.textContent ?? '', bouton: c.querySelector('.bq-actions button')?.textContent, lic: c.querySelector('.bq-lic')?.title}));
window.__ajouter = (nom) => { const c = [...document.querySelectorAll('.bq-card')].find((x) => x.querySelector('.bq-name')?.textContent === nom);
	if (!c) return false; c.querySelector('.bq-actions button').click(); return true; };
`;
/** Tete de lecture a t (s) : vrai clic de souris dans la regle de la timeline. */
const seek = async (t) => {
	const p = await ev(`(() => { const sc = document.querySelector('.tl-scroll'); const spans = [...sc.querySelectorAll('.tl-ruler > span')];
		const zoom = parseFloat(spans[1].style.left) / 5; sc.scrollLeft = Math.max(0, ${t} * zoom - 200);
		const r = sc.querySelector('.tl-ruler').getBoundingClientRect(); const b = sc.getBoundingClientRect();
		return {x: b.left - sc.scrollLeft + ${t} * zoom, y: r.top + r.height / 2}; })()`);
	for (const type of ['mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', {type, x: p.x, y: p.y, button: 'left', clickCount: 1});
	await sleep(400);
};

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

	// 1. editeur complet, reel « Vidéo 2 » (Reel Impact, sans habillage)
	await ev(`__b('Éditeur complet').click()`);
	await attendre(`!!document.querySelector('header select')`);
	await ev(JS);
	const opt = await ev(`[...document.querySelector('header select').options].map((o) => [o.value, o.textContent])`);
	const v2 = opt.find(([, l]) => /Vidéo 2/.test(l))?.[0] ?? 'script2/script';
	await ev(`__set(document.querySelector('header select'), ${JSON.stringify(v2)})`);
	await attendre(`!!document.querySelector('.tl-scroll .tl-ruler > span:nth-child(2)')`, 30000);
	await sleep(1500);
	await ev(`[...document.querySelectorAll('.tabs:not(.more) > button')].find((b) => (b.title || '').startsWith('Réglages de monteur')).click()`);
	await ev(`__b('Banque', document.querySelector('.tabs.more')).click()`);
	ok(await attendre(`document.querySelectorAll('.bq-card').length > 0`, 20000), 'Plus → Banque : la grille se remplit');
	const entete = await ev(`document.querySelector('.panel .card h3')?.textContent`);
	const cartes = await ev('__cartes()');
	// 2026-10-02 (ronde 4, icônes) : « Tout » compte aussi les icônes (catalogue à part, 1 857 Lucide + importées) : 556 + icônes
	const surN = Number(/sur ([\d\s  ]+)/.exec(entete || '')?.[1]?.replace(/\D/g, '') || 0);
	ok(cartes.length === 48 && surN >= 556, `« ${entete} » ; ${cartes.length} cartes affichées (48 par page)`);
	ok(cartes.every((c) => c.lic && /Licence : .+\nProvenance : .+/.test(c.lic)), 'chaque carte porte licence et provenance (survol)');
	const types = await ev(`[...document.querySelectorAll('.bq-types button')].map((b) => b.textContent)`);
	// 2026-10-02 (ronde 4) : 6e filtre « Icônes » quand le bac a des icônes
	ok((types.length === 5 || (types.length === 6 && types.some((t) => t.startsWith('Icônes')))) && types[1].startsWith('Sons') && /490/.test(types[1]),
		`filtres de type : ${types.join(' | ')}`);
	await shot('banque-1-tout.png');

	// 2. recherche sans accent + apercus des vecteurs aux couleurs du style
	await ev(`__set(document.querySelector('.bq-search'), 'fleche')`);
	await sleep(400);
	let c2 = await ev('__cartes()');
	ok(c2.length >= 5 && c2.some((c) => c.nom === 'Flèche droite'), `« fleche » : ${c2.length} résultats (${c2.slice(0, 4).map((c) => c.nom).join(', ')}…)`);
	const svgs = await ev(`[...document.querySelectorAll('.bq-vec svg')].length`);
	const couleur = await ev(`getComputedStyle(document.querySelector('.bq-vec')).getPropertyValue('--v-principale').trim()`);
	ok(svgs > 0 && couleur.toUpperCase() === disque('script2').style.highlight.toUpperCase(), `vecteurs affichés en SVG (${svgs}), couleur principale ${couleur} = couleur du style`);
	await shot('banque-2-fleche.png');

	// 3. sons : filtre type + catégorie + intensité, écoute
	await ev(`__set(document.querySelector('.bq-search'), '')`);
	await ev(`__b('Sons', document.querySelector('.bq-types')).click()`);
	await sleep(200);
	await ev(`__set(document.querySelector('.panel select'), 'whoosh')`);
	await sleep(300);
	const c3 = await ev('__cartes()');
	ok(c3.length === 9 && c3.every((c) => /^Whoosh/.test(c.meta)), `Sons + « Whoosh » : ${c3.length} (${c3.map((c) => c.nom).join(', ')})`);
	await ev(`__set(document.querySelector('.panel select'), 'impact')`);
	await ev(`__b('●●●', document.querySelector('.panel')).click()`);
	await sleep(300);
	const c3b = await ev('__cartes()');
	ok(c3b.length > 0 && c3b.every((c) => /^Impact · ●●●/.test(c.meta)), `Sons + « Impact » + intensité forte : ${c3b.length} cartes, toutes ●●●`);
	await ev(`__set(document.querySelector('.panel select'), 'whoosh')`);
	await ev(`__b('Toutes', document.querySelector('.panel')).click()`);
	await sleep(200);
	await ev(`document.querySelector('.bq-play').click()`);
	const joue = await attendre(`document.querySelector('.bq-play')?.textContent === '■'`, 3000);
	ok(joue, 'écoute : le bouton passe à ■ pendant la lecture');
	await shot('banque-3-sons.png');

	// 4. ajouter a l'instant choisi dans la timeline : vecteur, modele, son
	await ev(`__set(document.querySelector('.panel select'), '')`);
	await ev(`__b('Tout', document.querySelector('.bq-types')).click()`);
	await seek(15.2);
	const instant = await ev(`document.querySelector('.panel .card h3 small')?.textContent`);
	ok(/0:15\.[12]/.test(instant), `tête de lecture posée dans la timeline : « ${instant} »`);
	await ev(`__set(document.querySelector('.bq-search'), 'flèche droite')`);
	await sleep(300);
	ok(await ev(`__ajouter('Flèche droite')`), '« + Ajouter » sur « Flèche droite »');
	await sleep(300);
	const fait = await ev(`document.querySelector('.bq-done h3')?.textContent`);
	ok(/Flèche droite.*ajouté à 0:15/.test(fait ?? ''), `confirmation : « ${fait} »`);
	await seek(16.6);
	await ev(`__set(document.querySelector('.bq-search'), 'liste cochée')`);
	await sleep(300);
	ok(await ev(`__ajouter('Liste cochée — 3 bénéfices')`), '« + Ajouter » sur « Liste cochée — 3 bénéfices »');
	await sleep(300);
	const champ = await ev(`[...document.querySelectorAll('.bq-done input[type=text]')].map((i) => i.value)`);
	ok(champ.includes('Inclus'), `retouche rapide proposée (titre « ${champ[0]} »)`);
	await ev(`__set(document.querySelector('.bq-done input[type=text]'), 'Ce qui est inclus')`);
	await seek(15.5);
	await ev(`__set(document.querySelector('.bq-search'), 'impact métal lourd')`);
	await sleep(300);
	const son = (await ev('__cartes()'))[0]?.nom;
	ok(await ev(`__ajouter(${JSON.stringify(son)})`), `« + Ajouter » sur le son « ${son} »`);
	await sleep(3000); // sauvegarde automatique
	const d = disque('script2');
	const vec = (d.vectors ?? []).find((v) => v.asset === 'banque/vecteurs/fleche.svg');
	const gr = (d.graphics ?? []).find((g) => g.props?.banque === 'template:liste-benefices');
	const sx = (d.sfx?.extra ?? []).find((x) => x.reason === `Banque : ${son}`);
	ok(vec && vec.manual && Math.abs(vec.at - 15.2) < 0.08 && vec.couleurs.principale === null && vec.y < 0.3,
		`sur le disque : vecteur à ${vec?.at} s, manual, couleurs de la charte, placé hors du visage (y ${vec?.y})`);
	ok(gr && gr.manual && gr.kind === 'coches' && gr.props.title === 'Ce qui est inclus' && Math.abs(gr.at - 16.6) < 0.08,
		`sur le disque : liste cochée à ${gr?.at} s, titre retouché « ${gr?.props?.title} »`);
	ok(sx && sx.manual && /^sfx\/kenney\//.test(sx.name) && sx.gain > 0 && Math.abs(sx.t - 15.5) < 0.08, `sur le disque : son ${sx?.name} à ${sx?.t} s, gain ${sx?.gain}`);
	// effets : s'appliquent a toute la video, « ✓ Actif · Retirer »
	await ev(`__set(document.querySelector('.bq-search'), '')`);
	await ev(`__b('Effets', document.querySelector('.bq-types')).click()`);
	await sleep(300);
	const fx = await ev('__cartes()');
	ok(fx.length === 12 && fx.filter((c) => c.bouton === 'Appliquer').length >= 10, `Effets : ${fx.length} cartes (${fx.map((c) => c.nom).slice(0, 5).join(', ')}…)`);
	await ev(`__ajouter('Look cinéma')`);
	await sleep(2800);
	const actif = (await ev('__cartes()')).find((c) => c.nom === 'Look cinéma')?.bouton;
	ok(disque('script2').effects?.grade === 'cinema' && /Actif/.test(actif ?? ''), `« Look cinéma » appliqué (étalonnage ${disque('script2').effects?.grade}) ; bouton « ${actif} »`);
	await shot('banque-4b-effets.png');
	await ev(`__ajouter('Look cinéma')`); // « ✓ Actif · Retirer »
	await sleep(2800);
	ok(disque('script2').effects?.grade === 'aucun', `« Retirer » : étalonnage ${disque('script2').effects?.grade}`);
	await ev(`__b('Tout', document.querySelector('.bq-types')).click()`);
	await seek(15.9);
	await sleep(1500);
	await shot('banque-4-apercu-fleche.png');
	await seek(17.3);
	await sleep(1500);
	await shot('banque-5-apercu-liste.png');

	// 5. reel avec habillage (Tech, bruitages coupes)
	const v1 = opt.find(([, l]) => /Vidéo 1 - Version script/.test(l))?.[0] ?? 'script1/script';
	await ev(`__set(document.querySelector('header select'), ${JSON.stringify(v1)})`);
	await sleep(3500);
	await ev(JS);
	if (!(await ev(`!!document.querySelector('.bq-card')`))) {
		await ev(`[...document.querySelectorAll('.tabs:not(.more) > button')].find((b) => (b.title || '').startsWith('Réglages de monteur')).click()`);
		await ev(`__b('Banque', document.querySelector('.tabs.more')).click()`);
	}
	await attendre(`document.querySelectorAll('.bq-card').length > 0`, 20000);
	const alerte = await ev(`document.querySelector('.panel .bq-warn')?.textContent ?? ''`);
	ok(/bruitages sont coupés/.test(alerte), `bruitages coupés signalés : « ${alerte.slice(0, 80)}… »`);
	await ev(`__set(document.querySelector('.bq-search'), 'chiffre qui défile')`);
	await sleep(300);
	const cc = await ev('__cartes()');
	ok(cc.length && cc.every((c) => /Dans ce style : « Chiffre encadré »/.test(c.note)), `modèle « chiffre » dans ce style : « ${cc[0]?.note} »`);
	await seek(16.2);
	ok(await ev(`__ajouter('Chiffre qui défile — prix')`), '« + Ajouter » sur « Chiffre qui défile — prix »');
	await ev(`__b('🔊 Activer les bruitages', document.querySelector('.panel')).click()`);
	await sleep(3000);
	const d1 = disque('script1');
	const sc = d1.styleScenes?.[0];
	ok(sc?.kind === 'metric' && sc.manual && sc.text === '2 400 $' && d1.sfx?.enabled === true,
		`sur le disque : scène ${sc?.kind} « ${sc?.text} » en tête, manual ; bruitages activés (${d1.sfx?.enabled})`);
	await seek(17.2);
	await sleep(1500);
	await shot('banque-6-tech.png');
	// attendu dans ce bac : modeles MediaPipe absents, medias de Vidéo 1 non copies (seuls ceux de Vidéo 2 le sont)
	const absent = (e) => {
		const m = /(\/projects\/[^\s:]+\.(mp4|webm))/.exec(String(e));
		return m && !fs.existsSync(path.join(box, decodeURIComponent(m[1])));
	};
	const utiles = erreurs.filter((e) => !/mediapipe|blaze_face|Fichier introuvable|Failed to load resource/i.test(String(e)) && !absent(e)
		&& !/^Error occurred in video MediaError$/.test(String(e).trim()));
	ok(utiles.length === 0, `console : ${erreurs.length} message(s) d'erreur, ${utiles.length} lié(s) au code (${utiles.slice(0, 3).join(' | ')})`);
} catch (e) {
	fails++;
	console.log('ECHEC', e?.stack ?? e);
} finally {
	console.log(`\n${count - fails}/${count} verifications dans le navigateur reussies`);
	try {
		ws?.close();
	} catch {}
	chrome.kill();
	process.exitCode = fails ? 1 : 0;
}
