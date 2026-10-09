// Captures de l'interface de la COPIE (serveur lance ici sur le port 18796, faux moteur) avec le Chrome sans ecran de Remotion
// (lecture / execution seulement), pilote par le protocole DevTools. Usage : node capture.mjs [scenario...] ; images dans captures/.
import {spawn, execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../../..');
const WORK = path.join(path.resolve(HERE, '../../../..'), 'runtime', 'cache', 'tmp', 'claude-interface-1002'); // bac (jonctions), journaux, captures
const BOX = path.join(WORK, 'bac');
const CHROME = path.join(REAL, 'remotion/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe');
const PORT = 18796;
const URL = `http://127.0.0.1:${PORT}/`;
const CDP = 9338;
const OUT = path.join(WORK, 'captures');
fs.mkdirSync(OUT, {recursive: true});
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const marque = (nom, on) => (on ? fs.writeFileSync(path.join(BOX, 'runtime/cache', `faux-${nom}`), '1') : fs.rmSync(path.join(BOX, 'runtime/cache', `faux-${nom}`), {force: true}));

const OUTILS = `
window.__q = (sel, txt) => [...document.querySelectorAll(sel)].find((e) => !txt || e.textContent.includes(txt));
window.__clic = (sel, txt) => { const e = window.__q(sel, txt); if (!e) throw new Error('introuvable : ' + sel + ' ' + (txt || '')); e.click(); return true; };
window.__attendre = async (sel, txt, ms = 8000) => { const t = Date.now(); while (Date.now() - t < ms) { if (window.__q(sel, txt)) return true; await new Promise((r) => setTimeout(r, 100)); } throw new Error('attente : ' + sel + ' ' + (txt || '')); };
window.__pause = (ms = 300) => new Promise((r) => setTimeout(r, ms));
window.__stop = () => document.querySelector('.sr-tr-btn.plein[aria-label="Pause"]')?.click();
`;
const S = {
	// liste (badge « 🧠 »), fiche de « leads » : ligne Claude, retouches par l'IA, avis de Claude dans le controle qualite
	revision: `await __attendre('.cl-badge'); __clic('.sr-carte', 'leads'); await __attendre('.cl-ia'); await __pause(1500); __stop();
		document.querySelector('.sr-infos').scrollTop = document.querySelector('.cl-ia').offsetTop - 120;`,
	avis: `__clic('.sr-carte', 'leads'); await __attendre('.cl-avis'); await __pause(1500); __stop(); document.querySelector('.cl-avis').scrollIntoView({block: 'end'});`,
	// « 👁 Critique Claude » sur rappel (export fait) : avis de la forme du vrai module (temps, gravite, probleme)
	critique: `window.confirm = () => true; __clic('.sr-carte', 'rappel'); await __attendre('.cl-btn'); await __pause(2500); __stop(); __clic('.cl-btn', 'Critique');
		await __attendre('.cl-avis-note', '6,5', 15000); await __pause(500); document.querySelector('.cl-avis').scrollIntoView({block: 'end'});`,
	// avis demande mais refuse (plafond) apres le controle de l'export : la carte dit pourquoi (marqueur faux-critique-plafond)
	critiquenon: `window.confirm = () => true; const out = (await (await fetch('/api/revision')).json()).items.find((i) => i.project === 'rappel').exports[0].out;
		const j = await (await fetch('/api/reels/rappel/script/controle', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({video: out})})).json();
		for (let k = 0; k < 60; k++) { const s = await (await fetch('/api/jobs/' + j.id)).json(); if (s.status !== 'running' && s.status !== 'queued') break; await __pause(250); }
		__clic('.sr-carte', 'rappel'); await __attendre('.cl-btn'); await __pause(2500); __stop(); __clic('.cl-btn', 'Critique');
		await __attendre('.cl-avis-non', 'plafond', 15000); await __pause(500); document.querySelector('.cl-avis-non').scrollIntoView({block: 'end'});`,
	reglages: `__stop(); __clic('.sa-rond'); await __attendre('.cl-modele'); await __pause(500);`,
	avance: `__stop(); __clic('.sa-rond'); await __attendre('.cl-modele'); __clic('.cl-lien', 'Avancé'); await __pause(300); __clic('.cl-lien', 'Coûts Claude');
		await __attendre('.cl-appels'); await __pause(300); document.querySelector('.cl-pop').scrollTop = 9999;`,
	credit: `await __attendre('.cl-bandeau'); __clic('.sr-carte', 'leads'); await __pause(1500); __stop(); __clic('.sa-rond'); await __attendre('.cl-alerte');`,
	editeur: `__clic('.sa-onglets button', 'Éditeur'); await new Promise(r=>setTimeout(r,5000)); __clic('.sa-rond'); await __attendre('.cl-modele');`,
};

const srvLog = fs.openSync(path.join(WORK, `serveur-${PORT}-capture.log`), 'w');
const srv = spawn(process.execPath, [path.join(BOX, 'app/server.mjs')], {cwd: BOX, env: {...process.env, EDITEUR_PORT: String(PORT), EDITEUR_SANS_NAVIGATEUR: '1'},
	stdio: ['ignore', srvLog, srvLog], windowsHide: true});
const lancer = async () => {
	const child = spawn(CHROME, ['--headless', '--disable-gpu', '--hide-scrollbars', '--mute-audio', `--remote-debugging-port=${CDP}`, `--user-data-dir=${path.join(WORK, 'chrome-cdp')}`,
		'--window-size=1440,900', 'about:blank'], {stdio: 'ignore', windowsHide: true,
		env: {...process.env, TEMP: path.join(WORK, 'tmp'), TMP: path.join(WORK, 'tmp')}}); // rien sur C:
	for (let k = 0; k < 50; k++) {
		try {
			const list = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
			const page = list.find((t) => t.type === 'page');
			if (page) return {child, ws: page.webSocketDebuggerUrl};
		} catch {}
		await wait(200);
	}
	child.kill();
	throw new Error('Chrome ne repond pas');
};
const cdp = (url) => new Promise((resolve, reject) => {
	const ws = new WebSocket(url);
	let n = 0;
	const pending = new Map();
	const events = [];
	ws.onmessage = (m) => {
		const d = JSON.parse(m.data);
		if (d.id && pending.has(d.id)) {
			const [ok, ko] = pending.get(d.id);
			pending.delete(d.id);
			d.error ? ko(new Error(JSON.stringify(d.error))) : ok(d.result);
		} else if (d.method) events.push(d);
	};
	ws.onerror = reject;
	ws.onopen = () => resolve({
		call: (method, params = {}) => new Promise((ok, ko) => {
			const id = ++n;
			pending.set(id, [ok, ko]);
			ws.send(JSON.stringify({id, method, params}));
		}),
		events,
		close: () => ws.close(),
	});
});

for (let k = 0; k < 60; k++) {
	try {
		if ((await fetch(`${URL}api/reels`)).ok) break;
	} catch {}
	await wait(250);
}
const [W, H] = (process.env.TAILLE || '1440x900').split('x').map(Number);
const noms = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(S);
const {child, ws} = await lancer();
const c = await cdp(ws);
try {
	await c.call('Page.enable');
	await c.call('Runtime.enable');
	await c.call('Emulation.setDeviceMetricsOverride', {width: W, height: H, deviceScaleFactor: 1, mobile: false});
	for (const nom of noms) {
		marque('credit-epuise', nom === 'credit');
		marque('critique-plafond', nom === 'critiquenon');
		await c.call('Page.navigate', {url: URL});
		await wait(4500);
		await c.call('Runtime.evaluate', {expression: OUTILS});
		const r = await c.call('Runtime.evaluate', {expression: `(async () => { ${S[nom] ?? ''} })()`, awaitPromise: true, returnByValue: true});
		if (r.exceptionDetails) console.log(nom, 'ERREUR', r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
		await wait(900);
		const shot = await c.call('Page.captureScreenshot', {format: 'png'});
		const file = path.join(OUT, `${nom}-${W}x${H}.png`);
		fs.writeFileSync(file, Buffer.from(shot.data, 'base64'));
		// textes de controle (lus dans le DOM : ce que la capture doit montrer)
		const t = await c.call('Runtime.evaluate', {expression: `JSON.stringify({badge: [...document.querySelectorAll('.cl-badge')].map((e) => e.textContent),
			detail: document.querySelector('.cl-detail')?.textContent ?? null, boutons: [...document.querySelectorAll('.cl-btn')].map((b) => b.textContent + (b.disabled ? ' [désactivé]' : '')),
			raison: document.querySelector('.cl-raison')?.textContent ?? null, modeles: [...document.querySelectorAll('.cl-modele')].map((e) => e.textContent),
			avis: document.querySelector('.cl-avis-tete')?.textContent ?? null, bandeau: document.querySelector('.cl-bandeau')?.textContent ?? null,
			cle: document.querySelector('.cl-cle')?.textContent ?? null, credit: document.querySelector('.cl-credit')?.textContent ?? null})`, returnByValue: true});
		const errs = c.events.filter((e) => e.method === 'Runtime.exceptionThrown' || (e.method === 'Runtime.consoleAPICalled' && e.params.type === 'error'));
		console.log(file, errs.length ? `${errs.length} erreur(s) console : ${JSON.stringify(errs.map((e) => e.params.exceptionDetails?.exception?.description ?? e.params.args?.map((a) => a.value ?? a.description).join(' ')).slice(0, 3))}` : 'console propre');
		console.log('  ', t.result.value);
		c.events.length = 0;
	}
} finally {
	marque('credit-epuise', false);
	marque('critique-plafond', false);
	c.close();
	child.kill();
	try {
		execFileSync(path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe'), ['/PID', String(srv.pid), '/T', '/F'], {stdio: 'ignore'});
	} catch {}
	fs.closeSync(srvLog);
}
