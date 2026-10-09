// Essai de l'interface dans un vrai navigateur (Chrome sans fenetre de remotion/node_modules, pilote par CDP), sur la
// COPIE ISOLEE preparee par bac-interface.mjs et servie sur le port 18804 (jamais le vrai dossier ni le port 8790).
//   node docs/direction-creative-v2/tests/choregraphie/bac-interface.mjs
//   (serveur du bac lance a part : EDITEUR_PORT=18804 node <bac>/app/server.mjs)
//   node docs/direction-creative-v2/tests/choregraphie/test-interface.mjs
// Vrais clics souris et touches clavier : piste Chorégraphie, fenetre de reglage, « Plus lent », glisser un mouvement,
// Ctrl+Z, onglet Plus → Chorégraphie, « Refaire la chorégraphie ». Captures d'ecran dans le bac (captures/).
// Profil du navigateur et fichiers temporaires : dans le bac (rien sur C:).
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../../..');
const box = path.join(REAL, 'runtime/cache/tmp/dcv2-choregraphie/interface');
const URL0 = 'http://127.0.0.1:18804/';
const CHROME = path.join(REAL, 'remotion/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe');
const shots = path.join(box, 'captures');
fs.mkdirSync(shots, {recursive: true});
const profil = path.join(box, 'profil-chrome');
fs.mkdirSync(profil, {recursive: true});
const REEL = path.join(box, 'projects/script1/reels/script.json');
const disk = () => JSON.parse(fs.readFileSync(REEL, 'utf8'));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let fails = 0;
let count = 0;
const ok = (cond, msg) => {
	count++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${msg}`);
	if (!cond) fails++;
};

const PORT = 9347;
const chrome = spawn(CHROME, [`--remote-debugging-port=${PORT}`, `--user-data-dir=${profil}`, '--no-first-run', '--no-default-browser-check',
	'--autoplay-policy=no-user-gesture-required', '--window-size=1440,900', 'about:blank'],
{stdio: 'ignore', windowsHide: true, env: {...process.env, TEMP: path.join(box, 'runtime/cache/tmp'), TMP: path.join(box, 'runtime/cache/tmp')}});
let ws;
const erreurs = [];
try {
	let target;
	for (let k = 0; k < 60 && !target; k++) {
		await sleep(250);
		try {
			target = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find((t) => t.type === 'page');
		} catch {}
	}
	ws = new WebSocket(target.webSocketDebuggerUrl);
	await new Promise((r) => (ws.onopen = r));
	let id = 0;
	const pending = new Map();
	ws.onmessage = (m) => {
		const d = JSON.parse(m.data);
		if (d.id && pending.has(d.id)) {
			pending.get(d.id)(d);
			pending.delete(d.id);
		} else if (d.method === 'Runtime.exceptionThrown') erreurs.push(d.params.exceptionDetails?.exception?.description ?? d.params.exceptionDetails?.text);
		else if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') erreurs.push(d.params.args.map((a) => a.value ?? a.description).join(' '));
	};
	const send = (method, params = {}) => new Promise((res) => {
		const i = ++id;
		pending.set(i, res);
		ws.send(JSON.stringify({id: i, method, params}));
	});
	const js = async (expression) => {
		const r = await send('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
		if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description ?? 'erreur JS');
		return r.result?.result?.value;
	};
	const shot = async (name) => {
		const r = await send('Page.captureScreenshot', {format: 'png'});
		fs.writeFileSync(path.join(shots, name), Buffer.from(r.result.data, 'base64'));
		return path.join(shots, name);
	};
	const mouse = (type, x, y, extra = {}) => send('Input.dispatchMouseEvent', {type, x, y, button: 'left', buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1, ...extra});
	const click = async (x, y) => {
		await mouse('mouseMoved', x, y, {buttons: 0});
		await mouse('mousePressed', x, y);
		await mouse('mouseReleased', x, y);
	};
	const key = async (k, code, vk, modifiers = 0) => {
		await send('Input.dispatchKeyEvent', {type: 'keyDown', key: k, code, windowsVirtualKeyCode: vk, modifiers});
		await send('Input.dispatchKeyEvent', {type: 'keyUp', key: k, code, windowsVirtualKeyCode: vk, modifiers});
	};
	const rect = (sel, text) => js(`(() => { const e = [...document.querySelectorAll(${JSON.stringify(sel)})].find((x) => ${text ? `x.textContent.includes(${JSON.stringify(text)})` : 'true'});
		if (!e) return null; e.scrollIntoView({block: 'nearest', inline: 'nearest'}); const b = e.getBoundingClientRect(); return {x: b.left + b.width / 2, y: b.top + b.height / 2, w: b.width, l: b.left}; })()`);
	const until = async (expr, ms = 15000) => {
		for (let t = 0; t < ms; t += 250) {
			if (await js(expr)) return true;
			await sleep(250);
		}
		return false;
	};
	await send('Runtime.enable');
	await send('Page.enable');
	await send('Emulation.setDeviceMetricsOverride', {width: 1440, height: 900, deviceScaleFactor: 1, mobile: false});
	await send('Page.navigate', {url: URL0});
	await until(`!!document.querySelector('button[title*="diteur complet"]')`);
	await js(`document.querySelector('button[title*="diteur complet"]').click()`);
	await until(`!!document.querySelector('header select')`);
	await js(`(() => { const s = document.querySelector('header select'); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(s, 'script1/script');
		s.dispatchEvent(new Event('change', {bubbles: true})); })()`);
	ok(await until(`document.querySelectorAll('.ch-cue').length === 5`), 'piste Chorégraphie : 5 mouvements affiches');
	await sleep(1500);
	console.log('capture', await shot('1-timeline.png'));

	// 1. clic sur la preuve « x5 » : fenetre de reglage + tete de lecture sur son entree
	let r = await rect('.ch-cue', 'Pop');
	await click(r.x, r.y);
	ok(await until(`!!document.querySelector('.ch-pop')`, 3000), 'clic sur un mouvement : fenetre de reglage ouverte');
	const pop = await js(`document.querySelector('.ch-pop')?.innerText ?? ''`);
	ok(/Chiffre qui défile/.test(pop) && /cinq/.test(pop) && /Preuve/.test(pop), `la fenetre montre l'element, le role et la raison (« ${pop.split('\n').slice(0, 3).join(' | ')} »)`);
	for (let k = 0; k < 4; k++) await key('ArrowRight', 'ArrowRight', 39);
	await sleep(1500);
	console.log('capture', await shot('2-fenetre-et-mi-entree.png'));

	// 2. « Plus lent » sur l'entree : enregistre, marque retouche
	const avantLent = disk().choreography.cues.find((c) => c.cible.id === 'g2-chiffre');
	r = await rect('.ch-pop .ch-move .ch-speed button', 'Plus lent'); // le premier = l'entree
	await click(r.x, r.y);
	await sleep(1200);
	const lent = disk().choreography.cues.find((c) => c.cible.id === 'g2-chiffre');
	ok(lent.entree.duree > avantLent.entree.duree && lent.manual === true && lent.locked === false,
		`« Plus lent » : ${avantLent.entree.duree} s -> ${lent.entree.duree} s, retouche enregistree (manual)`);
	// cadenas
	r = await rect('.ch-pop button.lock');
	await click(r.x, r.y);
	await sleep(1200);
	ok(disk().choreography.cues.find((c) => c.cible.id === 'g2-chiffre').locked === true, 'cadenas : mouvement verrouille sur le disque');
	r = await rect('.ch-pop button', '✕');
	await click(r.x, r.y);
	ok(await until(`!document.querySelector('.ch-pop')`, 2000), 'fenetre fermee');

	// 3. glisser la notification de 2 s vers la droite = deplacer l'element (scene ancree au mot le plus proche)
	const scene0 = disk().styleScenes.find((s) => s.id === 'style-c2-52');
	const zoomPx = 14;
	r = await rect('.ch-cue', 'Glisse');
	await mouse('mouseMoved', r.x, r.y, {buttons: 0});
	await mouse('mousePressed', r.x, r.y);
	for (let k = 1; k <= 7; k++) await mouse('mouseMoved', r.x + k * 4, r.y);
	await mouse('mouseReleased', r.x + 2 * zoomPx, r.y);
	await sleep(1200);
	const scene1 = disk().styleScenes.find((s) => s.id === 'style-c2-52');
	const cue1 = disk().choreography.cues.find((c) => c.cible.id === 'style-c2-52');
	ok(scene1.manual === true && (scene1.clip !== scene0.clip || scene1.index !== scene0.index) && cue1.at > 25.95 + 1.5,
		`glisser : scene ancree de ${scene0.clip}/${scene0.index} a ${scene1.clip}/${scene1.index}, mouvement a ${cue1.at.toFixed(2)} s, marquee retouchee`);
	await key('z', 'KeyZ', 90, 2);
	await sleep(1200);
	const scene2 = disk().styleScenes.find((s) => s.id === 'style-c2-52');
	ok(scene2.clip === scene0.clip && scene2.index === scene0.index && !scene2.manual, 'Ctrl+Z : la scene revient a son mot d\'origine');

	// 4. onglet Plus → Chorégraphie
	await js(`[...document.querySelectorAll('.tabs:not(.more) > button')].find((b) => (b.title || '').startsWith('Réglages de monteur'))?.click()`);
	await sleep(300);
	await js(`[...document.querySelectorAll('.tabs.more button')].find((b) => b.textContent.includes('Chorégraphie'))?.click()`);
	ok(await until(`!!document.querySelector('.card.choreo')`, 3000), 'onglet Plus → Chorégraphie ouvert');
	const panel = await js(`document.querySelector('.card.choreo').innerText`);
	ok(/Refaire la chorégraphie/.test(panel) && (await js(`document.querySelectorAll('.ch-item').length`)) === 5 && /5 mouvements/.test(panel),
		'panneau : resume, bouton « Refaire la chorégraphie » et les 5 mouvements');
	r = await rect('.ch-row', 'Notification');
	await click(r.x, r.y);
	await sleep(800);
	ok(await js(`!!document.querySelector('.ch-item.sel .ch-editor')`), 'clic sur une ligne : reglages du mouvement ouverts dans le panneau');
	console.log('capture', await shot('3-panneau.png'));

	// 5. « Refaire la chorégraphie » : le mouvement verrouille (x5, plus lent) est garde
	const garde = JSON.stringify(disk().choreography.cues.find((c) => c.cible.id === 'g2-chiffre'));
	r = await rect('.card.choreo button.primary', 'Refaire');
	await click(r.x, r.y);
	ok(await until(`/mouvement/.test(document.querySelector('.card.choreo .ok')?.textContent ?? '')`, 60000), 'Refaire : tache terminee, resume affiche');
	await sleep(1500);
	ok(JSON.stringify(disk().choreography.cues.find((c) => c.cible.id === 'g2-chiffre')) === garde, 'Refaire : le mouvement verrouille est garde tel quel');
	console.log('capture', await shot('4-apres-refaire.png'));
	const propres = erreurs.filter((e) => !/Failed to load resource|404|media|MEDIA_ERR|NotAllowedError|play\(\)/i.test(String(e)));
	ok(!propres.length, `console : aucune erreur du code (${propres.slice(0, 3).join(' | ') || 'aucune'})`);
} finally {
	try {
		ws?.close();
	} catch {}
	chrome.kill();
}
console.log(`\n${count - fails}/${count} verifications de l'interface reussies ; captures dans ${shots}`);
process.exit(fails ? 1 : 0);
