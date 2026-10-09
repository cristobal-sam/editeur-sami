// Test d'interaction de l'interface Claude dans la COPIE (port 18796, faux moteur, aucun appel reel) : Chrome sans ecran,
// clics dans la page (element.click / valeur + evenement input), verification sur le disque de la copie et dans le DOM.
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
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const reglages = () => JSON.parse(fs.readFileSync(path.join(BOX, 'styles/claude.json'), 'utf8'));
const reel = (p) => JSON.parse(fs.readFileSync(path.join(BOX, 'projects', p, 'reels/script.json'), 'utf8'));
let ok = 0;
let ko = 0;
const check = (nom, cond, detail = '') => {
	cond ? ok++ : ko++;
	console.log(`${cond ? 'OK  ' : 'ECHEC'} ${nom}${!cond && detail ? ` — ${detail}` : ''}`);
};
const OUTILS = `
window.__q = (sel, txt) => [...document.querySelectorAll(sel)].find((e) => !txt || e.textContent.includes(txt));
window.__clic = (sel, txt) => { const e = window.__q(sel, txt); if (!e) throw new Error('introuvable : ' + sel + ' ' + (txt || '')); e.click(); return true; };
window.__attendre = async (sel, txt, ms = 10000) => { const t = Date.now(); while (Date.now() - t < ms) { if (window.__q(sel, txt)) return true; await new Promise((r) => setTimeout(r, 100)); } throw new Error('attente : ' + sel + ' ' + (txt || '')); };
window.__pause = (ms = 400) => new Promise((r) => setTimeout(r, ms));
window.__saisir = (el, v) => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(el, v); el.dispatchEvent(new Event('input', {bubbles: true})); };
window.__stop = () => document.querySelector('.sr-tr-btn.plein[aria-label="Pause"]')?.click();
window.confirm = () => true; // les confirmations (cout annonce) sont acceptees dans ce test
`;
const srvLog = fs.openSync(path.join(WORK, `serveur-${PORT}-ui.log`), 'w');
const srv = spawn(process.execPath, [path.join(BOX, 'app/server.mjs')], {cwd: BOX, env: {...process.env, EDITEUR_PORT: String(PORT), EDITEUR_SANS_NAVIGATEUR: '1'},
	stdio: ['ignore', srvLog, srvLog], windowsHide: true});
for (let k = 0; k < 60; k++) {
	try {
		if ((await fetch(`${URL}api/reels`)).ok) break;
	} catch {}
	await wait(250);
}
const chrome = spawn(CHROME, ['--headless', '--disable-gpu', '--hide-scrollbars', '--mute-audio', `--remote-debugging-port=${CDP}`, `--user-data-dir=${path.join(WORK, 'chrome-cdp')}`,
	'--window-size=1440,900', 'about:blank'], {stdio: 'ignore', windowsHide: true, env: {...process.env, TEMP: path.join(WORK, 'tmp'), TMP: path.join(WORK, 'tmp')}});
let wsUrl;
for (let k = 0; k < 50 && !wsUrl; k++) {
	try {
		wsUrl = (await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json()).find((t) => t.type === 'page')?.webSocketDebuggerUrl;
	} catch {}
	if (!wsUrl) await wait(200);
}
const ws = new WebSocket(wsUrl);
await new Promise((r) => (ws.onopen = r));
let n = 0;
const pending = new Map();
const erreurs = [];
ws.onmessage = (m) => {
	const d = JSON.parse(m.data);
	if (d.id && pending.has(d.id)) {
		pending.get(d.id)(d);
		pending.delete(d.id);
	} else if (d.method === 'Runtime.exceptionThrown' || (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error')) erreurs.push(JSON.stringify(d.params).slice(0, 300));
};
const call = (method, params = {}) => new Promise((r) => {
	pending.set(++n, r);
	ws.send(JSON.stringify({id: n, method, params}));
});
const page = async (code) => {
	const r = await call('Runtime.evaluate', {expression: `(async () => { ${code} })()`, awaitPromise: true, returnByValue: true});
	if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description ?? r.result.exceptionDetails.text);
	return r.result?.result?.value;
};
try {
	await call('Page.enable');
	await call('Runtime.enable');
	await call('Emulation.setDeviceMetricsOverride', {width: 1440, height: 900, deviceScaleFactor: 1, mobile: false});
	await call('Page.navigate', {url: URL});
	await wait(4500);
	await page(OUTILS);
	// 1. modele : un clic = enregistre (styles/claude.json par le moteur)
	await page(`__stop(); __clic('.sa-rond'); await __attendre('.cl-modele'); __q('.cl-modele', 'Haiku').querySelector('input').click(); await __attendre('.sr-ok', 'Modèle');`);
	check('modele Haiku choisi -> enregistre', reglages().modele === 'claude-haiku-4-5');
	check('modele Haiku coche dans la page', (await page(`return document.querySelector('.cl-modele.on').textContent`)).includes('Haiku'));
	await page(`__q('.cl-modele', 'Sonnet').querySelector('input').click(); await __attendre('.sr-ok', 'Sonnet');`);
	// 2. plafonds (virgule acceptee)
	await page(`__clic('.cl-lien', 'Avancé'); await __attendre('.cl-plafonds input'); const i = document.querySelectorAll('.cl-plafonds input'); __saisir(i[0], '0,3'); await __pause();
		__clic('.sr-btn', 'Enregistrer les plafonds'); await __attendre('.sr-ok', 'Plafonds');`);
	check('plafond par video 0,3 -> 0.3', reglages().plafond_video === 0.3, JSON.stringify(reglages()));
	// 3. modele par tache
	await page(`const s = __q('.cl-select', 'Relecture').querySelector('select'); const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
		set.call(s, 'claude-opus-5-5'); s.dispatchEvent(new Event('change', {bubbles: true})); await __attendre('.sr-ok', 'tâche');`);
	check('modele par tache (critique = Opus)', reglages().modeles_taches.critique === 'claude-opus-5-5', JSON.stringify(reglages().modeles_taches));
	// 4. recharge : credit affiche + depenses d'aujourd'hui, date du jour
	await page(`__saisir(document.getElementById('cl-credit'), '10'); await __pause(); __clic('.cl-recharge .sr-btn', 'Enregistrer'); await __attendre('.sr-ok', 'crédit');`);
	const r = reglages();
	check('« J\'ai rechargé » : credit_depart = 10 + depense du jour, date du jour', Math.abs(r.credit_depart - 10.092) < 1e-6 && r.credit_date === new Date().toLocaleDateString('sv-SE'), JSON.stringify(r));
	check('credit restant affiche 10,00 $', (await page(`return document.querySelector('.cl-credit').textContent`)).includes('10,00 $'));
	// 5. espace de travail invalide : refus en francais (rien ecrit)
	await page(`const e = document.querySelector('[aria-label="Identifiant de l\\'espace de travail"]'); __saisir(e, 'abc'); await __pause(); e.parentElement.querySelector('.sr-btn').click(); await __attendre('.cl-reglages .sr-err', 'wrkspc_');`);
	check('espace de travail invalide refuse, rien ecrit', !reglages().espace_travail);
	// 6. eteindre : boutons Claude desactives avec la raison
	await page(`__clic('.cl-inter'); await __attendre('.sr-ok', 'éteint'); document.querySelector('.sa-rond').click(); await __pause(600);`);
	check('Claude eteint -> enregistre', reglages().actif === false);
	const eteint = await page(`await __attendre('.cl-raison', 'éteint'); return [...document.querySelectorAll('.cl-btn')].map((b) => b.disabled)`);
	check('Claude eteint -> boutons desactives + raison', eteint.every(Boolean), JSON.stringify(eteint));
	await page(`__clic('.sa-rond'); await __attendre('.cl-inter'); __clic('.cl-inter'); await __attendre('.sr-ok', 'allumé'); document.querySelector('.sa-rond').click(); await __pause(600);`);
	await fetch(`${URL}api/claude/reglages`, {method: 'PUT', headers: {'content-type': 'application/json', origin: `http://127.0.0.1:${PORT}`}, body: JSON.stringify({plafond_video: 0.25, modeles_taches: {critique: null}})});
	// 7. « 🧠 Refaire avec Claude » sur leads : confirmation, tache, resultat + Annuler
	const banniere = reel('leads').banner?.text;
	await page(`__clic('.sr-carte', 'leads'); await __attendre('.cl-btn'); await __pause(2500); __stop(); __clic('.cl-btn', 'Refaire'); await __attendre('.cl-fait', 'Idées', 15000);`);
	check('cerveau : le montage a change (faux moteur)', reel('leads').banner?.text === 'Texte proposé par Claude (faux)' && banniere !== reel('leads').banner?.text);
	check('cerveau : resultat affiche avec le cout', (await page(`return document.querySelector('.cl-fait').textContent`)).includes('0,03 $'));
	await page(`__clic('.cl-fait .sr-btn', 'Annuler'); await __attendre('.sr-message.ok', 'avant Claude');`);
	check('cerveau : « Annuler » remet le montage d\'avant', reel('leads').banner?.text === banniere, `${reel('leads').banner?.text}`);
	// revue 2026-10-02 : la critique juge la video livree -> sans export, bouton desactive avec la raison
	const sansExport = await page(`const b = __q('.cl-btn', 'Critique'); return {off: b.disabled, raison: document.querySelector('.cl-raison')?.textContent ?? ''}`);
	check('critique sans export : bouton desactive + « exporte d\'abord »', sansExport.off && /exporte d.abord/.test(sansExport.raison), JSON.stringify(sansExport));
	// 8. « 👁 Critique Claude » sur rappel (export fait) : avis dans la carte Controle qualite, moment cliquable
	await page(`__clic('.sr-carte', 'rappel'); await __attendre('.cl-btn'); await __pause(2500); __stop(); __clic('.cl-btn', 'Critique'); await __attendre('.cl-avis-note', '6,5', 15000);`);
	const avis = await page(`return document.querySelector('.cl-avis').textContent`);
	check('critique : avis 6,5/10 + probleme au bon moment', avis.includes('6,5/10') && avis.includes('0:00,8'), avis);
	const appels = fs.readFileSync(path.join(BOX, 'runtime/cache/appels-moteur.log'), 'utf8').trim().split('\n').map((l) => JSON.parse(l)).filter((a) => a.module === 'critique_claude');
	const argv = appels.at(-1)?.argv ?? [];
	check('critique : la video exportee est relue (ligne de commande du vrai module)', /Pourquoi on rappelle en 60 secondes - FINAL\.mp4$/.test(argv[0] ?? '') && argv.includes('--json'), JSON.stringify(argv));
	check('badge mis a jour pour rappel', (await page(`await __pause(3000); return __q('.sr-carte', 'rappel').textContent`)).includes('🧠'));
	check('console du navigateur propre', !erreurs.length, erreurs.join(' | '));
} catch (e) {
	ko++;
	console.log('ECHEC', e.message);
} finally {
	ws.close();
	chrome.kill();
	try {
		execFileSync(path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe'), ['/PID', String(srv.pid), '/T', '/F'], {stdio: 'ignore'});
	} catch {}
	fs.closeSync(srvLog);
}
console.log(`\n${ok}/${ok + ko} reussis`);
process.exit(ko ? 1 : 0);
