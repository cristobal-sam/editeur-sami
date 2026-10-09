// Controle de l'interface V2 COMPLETE dans un Chrome sans fenetre (celui de Remotion, aucune installation), sur le bac
// isole de bac-navigateur.mjs (port 18851). Pilote par le protocole DevTools, vrais clics et vraies touches, captures
// 1600 x 1000 a REGARDER. Rien n'est ecrit hors du bac.
//   node docs/direction-creative-v2/tests/integration/bac-navigateur.mjs      (dans un autre terminal : BAC=…)
//   node docs/direction-creative-v2/tests/integration/ui-integration.mjs <BAC> [port]
// Verifie : onglets (ordre, noms en francais), Notes (liste, retour a l'image, pas d'avertissement « relancer »), Plan
// (cadenas du plan -> disque), Banque, Graphismes (vecteurs + couleur des modeles), Choregraphie (panneau + piste),
// barre « Refaire seulement ce passage » (touches I/O, tache, bulle), aucune erreur de console venant du code.
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../../..');
const [BOX, port = '18851'] = process.argv.slice(2);
if (!BOX || !fs.existsSync(path.join(BOX, 'projects/script2/reels/script.json'))) throw new Error('Donne le dossier du bac (BAC=… de bac-navigateur.mjs).');
const BASE = `http://127.0.0.1:${port}`;
const REEL = path.join(BOX, 'projects/script2/reels/script.json');
const disk = () => JSON.parse(fs.readFileSync(REEL, 'utf8'));
const OUT = path.join(BOX, 'interface');
fs.mkdirSync(OUT, {recursive: true});
const CHROME = path.join(ROOT, 'remotion/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe');
const CDP = 9361;
const chrome = spawn(CHROME, ['--headless', '--no-sandbox', '--disable-gpu', `--remote-debugging-port=${CDP}`, `--user-data-dir=${path.join(OUT, 'profil')}`,
	'--hide-scrollbars', '--autoplay-policy=no-user-gesture-required', '--window-size=1600,1000', 'about:blank'], {stdio: 'ignore', windowsHide: true});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let fails = 0;
let count = 0;
const ok = (c, m) => {
	count++;
	console.log(`${c ? 'OK   ' : 'ECHEC'} ${m}`);
	if (!c) fails++;
	return c;
};
const erreurs = [];
try {
	let target;
	for (let k = 0; k < 60 && !target; k++) {
		try {
			target = (await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json()).find((t) => t.type === 'page');
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
	const shot = async (name) => {
		const r = await cdp('Page.captureScreenshot', {format: 'png'});
		const f = path.join(OUT, `${name}.png`);
		fs.writeFileSync(f, Buffer.from(r.result.data, 'base64'));
		console.log(`CAPTURE ${f}`);
	};
	// vrai clic souris au centre de l'element (comme un utilisateur)
	const clic = async (txt, sel = 'button', exact = false) => {
		const box = await js(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(sel)})].find((b) => ${exact
			? `b.textContent.trim() === ${JSON.stringify(txt)}` : `b.textContent.trim() === ${JSON.stringify(txt)} || b.textContent.includes(${JSON.stringify(txt)}) || (b.title || '').includes(${JSON.stringify(txt)})`});
			if (!el) return null; el.scrollIntoView({block: 'center'}); const r = el.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2}; })()`);
		if (!box) return false;
		for (const type of ['mousePressed', 'mouseReleased']) await cdp('Input.dispatchMouseEvent', {type, x: box.x, y: box.y, button: 'left', clickCount: 1});
		await sleep(250);
		return true;
	};
	const touche = async (key, code) => {
		for (const type of ['keyDown', 'keyUp']) await cdp('Input.dispatchKeyEvent', {type, key, code, text: type === 'keyDown' ? key : undefined});
		await sleep(150);
	};
	const texte = () => js('document.body.innerText');
	await cdp('Runtime.enable');
	await cdp('Log.enable');
	await cdp('Page.enable');
	await cdp('Emulation.setDeviceMetricsOverride', {width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false});
	await cdp('Page.navigate', {url: BASE});
	ok(await until(`!![...document.querySelectorAll('button')].find((b) => b.textContent.includes('Éditeur complet'))`), 'page d\'accueil (Revision) chargee');
	await clic('Éditeur complet');
	ok(await until(`document.querySelectorAll('.tl-clip').length > 0`, 25000), 'editeur ouvert, timeline affichee');
	await sleep(1500);

	// 1. onglets : ordre et noms en francais, sans doublon
	const principaux = await js(`[...document.querySelectorAll('.tabs:not(.more) > button')].map((b) => b.textContent.trim())`);
	ok(JSON.stringify(principaux) === JSON.stringify(['Texte', 'Style', 'Ajouter', 'Notes', 'Plus ▾']), `onglets principaux : ${principaux.join(' | ')}`);
	await clic('Réglages de monteur', '.tabs:not(.more) > button');
	const plus = await js(`[...document.querySelectorAll('.tabs.more > button')].map((b) => b.textContent.trim())`);
	ok(JSON.stringify(plus) === JSON.stringify(['Plan', 'Graphismes', 'Banque', 'Chorégraphie', 'Rushs', 'Conseils', 'Versions', 'Export']), `menu Plus : ${plus.join(' | ')}`);
	await clic('Réglages de monteur', '.tabs:not(.more) > button');
	const pistes = await js(`[...document.querySelectorAll('.tl-heads > div')].map((d) => d.textContent.trim())`);
	ok(pistes.length === 9 && pistes.includes('Chorégraphie') && new Set(pistes).size === pistes.length, `pistes de la timeline : ${pistes.join(' | ')}`);
	const barre = await js(`[...document.querySelectorAll('.tl-tools button')].map((b) => b.textContent.trim())`);
	ok(barre.filter((b) => b === 'Refaire seulement ce passage').length === 1 && barre.includes('Début ici') && barre.includes('Fin ici'), `barre de la timeline : ${barre.join(' | ')}`);
	await shot('1-editeur');

	// 2. Notes : les 4 notes du reel, pas d'avertissement (serveur V2), clic -> image exacte
	await clic('Notes', '.tabs > button', true);
	ok(await until(`document.querySelectorAll('.nt-card').length === 4`), 'onglet Notes : 4 notes');
	const t = await texte();
	ok(!/doit être relancé/.test(t), 'aucun avertissement « relancer l\'éditeur » (le serveur du bac est V2 : GET /api/v2 = 200)');
	const repere = await js(`document.querySelectorAll('.tl-ruler .nt-mark, .tl-ruler .nt-mark-d').length`);
	ok(repere >= 3, `reperes des notes dans la regle de la timeline : ${repere}`);
	const n1 = disk().notes.find((n) => n.id === 'n1');
	// bouton « ▶ timecode » de la carte qui porte le texte de la note
	const pos = await js(`(() => { const c = [...document.querySelectorAll('.nt-card')].find((x) => x.innerText.includes('Garder ce whoosh'));
		const b = c && c.querySelector('button.nt-tc'); if (!b) return null; b.scrollIntoView({block: 'center'}); const r = b.getBoundingClientRect();
		return {x: r.x + r.width / 2, y: r.y + r.height / 2, tc: b.textContent.trim()}; })()`);
	ok(!!pos, `carte de la note : bouton ${pos?.tc}`);
	if (pos) for (const type of ['mousePressed', 'mouseReleased']) await cdp('Input.dispatchMouseEvent', {type, x: pos.x, y: pos.y, button: 'left', clickCount: 1});
	await sleep(800);
	const lecture = await js(`document.querySelector('.transport span')?.textContent`);
	ok(/0:15/.test(lecture ?? ''), `clic sur la note « Garder ce whoosh » : tete de lecture ${lecture} (note a ${n1.t} s)`);
	await shot('2-notes');

	// 3. Plan : cadenas du plan (mots en couleur et emojis figes) -> enregistre sur le disque
	await clic('Réglages de monteur', '.tabs:not(.more) > button');
	await clic('Plan', '.tabs.more > button', true);
	await sleep(400);
	const avantPlan = disk().clips.map((c) => !!c.locked);
	const lockBtn = await js(`!![...document.querySelectorAll('button.lock')].find((b) => (b.title || '').includes('emojis de ce plan'))`);
	ok(lockBtn, 'onglet Plan : cadenas « Figer les mots en couleur et les emojis de ce plan »');
	await clic('emojis de ce plan', 'button.lock');
	await sleep(1200);
	const apresPlan = disk().clips.map((c) => !!c.locked);
	ok(JSON.stringify(apresPlan) !== JSON.stringify(avantPlan), `cadenas du plan (clic = verrouiller / deverrouiller) enregistre sur le disque (${avantPlan.filter(Boolean).length} -> ${apresPlan.filter(Boolean).length} plan(s) fige(s))`);
	await shot('3-plan');

	// 4. Banque : grille, filtres, licence
	await clic('Réglages de monteur', '.tabs:not(.more) > button');
	await clic('Banque', '.tabs.more > button', true);
	ok(await until(`document.querySelectorAll('.bq-card').length > 10`, 20000), 'Banque : grille des ressources');
	const types = await js(`[...document.querySelectorAll('.bq-types button')].map((b) => b.textContent.trim())`);
	ok(types.length >= 5, `Banque : filtres ${types.join(' | ')}`);
	await shot('4-banque');

	// 5. Graphismes : vecteurs (carte), couleur des modeles (charte / choisie)
	await clic('Réglages de monteur', '.tabs:not(.more) > button');
	await clic('Graphismes', '.tabs.more > button', true);
	await sleep(500);
	const g = await texte();
	ok(/Vecteurs/.test(g) && /Ajouter un vecteur/.test(g), 'Graphismes : carte Vecteurs presente');
	await clic('Modifier', '.card:has(.lock) button');
	await sleep(300);
	ok(/Couleur de la charte/.test(await texte()), 'Graphismes : réglage « Couleur » d\'un modèle avec « Couleur de la charte »');
	await shot('5-graphismes');

	// 6. Choregraphie : panneau, liste, refaire (tache), piste
	await clic('Réglages de monteur', '.tabs:not(.more) > button');
	await clic('Chorégraphie', '.tabs.more > button', true);
	ok(await until(`document.querySelectorAll('.ch-item').length > 0`), 'Chorégraphie : liste des mouvements');
	const nCues = disk().choreography.cues.length;
	ok((await js(`document.querySelectorAll('.tl-choreo *').length`)) > 0, 'piste Chorégraphie : mouvements dessines');
	await clic('Refaire la chorégraphie');
	ok(await until(`/Chorégraphie refaite/.test(document.body.innerText)`, 40000), 'Refaire la chorégraphie : tache terminee (« ✓ Chorégraphie refaite »)');
	const verrouille = disk().choreography.cues.filter((c) => c.locked).length;
	ok(verrouille >= 1, `mouvement verrouille garde apres « Refaire » (${verrouille} ; ${nCues} -> ${disk().choreography.cues.length} mouvements)`);
	await shot('6-choregraphie');

	// 7. Refaire seulement ce passage : touches I/O, tache, bulle, annuler
	await cdp('Runtime.evaluate', {expression: 'document.activeElement && document.activeElement.blur()'});
	await clic('+1 s');
	for (let k = 0; k < 4; k++) await clic('+1 s');
	await touche('i', 'KeyI');
	for (let k = 0; k < 8; k++) await clic('+1 s');
	await touche('o', 'KeyO');
	const plage = await js(`document.querySelector('.passage-plage')?.textContent`);
	ok(!!plage && (await js(`!!document.querySelector('.tl-range')`)), `plage choisie au clavier (I / O) : ${plage}`);
	await clic('Refaire seulement ce passage');
	ok(await until(`!!document.querySelector('.passage-pop[role="dialog"]')`, 40000), 'compte rendu du passage dans la bulle');
	const bulle = await js(`document.querySelector('.passage-pop[role="dialog"]')?.innerText`);
	ok(/Rien n.a bougé avant ni après|rien à changer/.test(bulle ?? ''), `bulle : ${String(bulle).split('\n').slice(0, 2).join(' / ')}`);
	ok((await js(`document.querySelector('.tl-tools').getBoundingClientRect().height`)) <= 40, 'la barre de la timeline reste sur une ligne');
	await shot('7-passage');

	// 8. console : aucune erreur venant du code (medias absents du bac exceptes)
	const vraies = erreurs.filter((e) => !/Failed to load resource|404|media|\.mp4|\.webm|NotSupportedError|play\(\)|AbortError/i.test(String(e)));
	ok(!vraies.length, `console : ${vraies.length} erreur(s) du code${vraies.length ? ` : ${vraies.slice(0, 3).join(' | ')}` : ''} (${erreurs.length} message(s) en tout)`);
} catch (e) {
	fails++;
	console.log('ECHEC', e?.stack ?? e);
} finally {
	try {
		chrome.kill();
	} catch {}
	// profil Chrome du test (≈ 30 Mo) : inutile apres l'essai ; les captures restent
	await sleep(1000);
	try {
		fs.rmSync(path.join(OUT, 'profil'), {recursive: true, force: true, maxRetries: 5, retryDelay: 300});
	} catch {}
}
console.log(`\n${count - fails}/${count} verifications interface (integration V2) reussies — captures dans ${OUT}`);
process.exitCode = fails ? 1 : 0;
