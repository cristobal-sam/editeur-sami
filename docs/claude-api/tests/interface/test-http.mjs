// Tests HTTP du serveur de la COPIE (port 18796) avec le FAUX moteur : routes Claude (statut sans cle, reglages, couts),
// consigne (tache, validation, double clic), cerveau / critique (sur un clic, version « avant »), critique automatique apres
// export, reel.consignes jamais envoye a l'export, validation des nouveaux champs sfx, catalogue des sons de transition.
// AUCUN appel reel a Claude : le moteur de la copie est faux-moteur/. Usage : node test-http.mjs (lance et arrete le serveur).
import {spawn, execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const WORK = path.join(path.resolve(HERE, '../../../..'), 'runtime', 'cache', 'tmp', 'claude-interface-1002'); // bac (jonctions), journaux, captures
const BOX = path.join(WORK, 'bac');
const PORT = 18796;
const ORIGIN = `http://127.0.0.1:${PORT}`;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const B = (...p) => path.join(BOX, ...p);
let ok = 0;
let ko = 0;
const echecs = [];
const check = (nom, cond, detail = '') => {
	if (cond) ok++;
	else {
		ko++;
		echecs.push(`${nom}${detail ? ` : ${detail}` : ''}`);
	}
	console.log(`${cond ? 'OK  ' : 'ECHEC'} ${nom}${!cond && detail ? ` — ${detail}` : ''}`);
};
const req = async (method, route, body, origin = ORIGIN) => {
	const headers = {'content-type': 'application/json'};
	if (origin) headers.origin = origin;
	const r = await fetch(`${ORIGIN}${route}`, {method, headers, body: body === undefined ? undefined : JSON.stringify(body)});
	const text = await r.text();
	let data = text;
	try {
		data = JSON.parse(text);
	} catch {}
	return {status: r.status, data, text};
};
const job = async (id, ms = 20000) => {
	const fin = Date.now() + ms;
	for (;;) {
		const j = (await req('GET', `/api/jobs/${id}`)).data;
		if (!['running', 'queued'].includes(j.status) || Date.now() > fin) return j;
		await wait(250);
	}
};
const appelsMoteur = () => (fs.existsSync(B('runtime/cache/appels-moteur.log')) ? fs.readFileSync(B('runtime/cache/appels-moteur.log'), 'utf8').trim().split('\n').map((l) => JSON.parse(l)) : []);
const marque = (nom, on) => (on ? fs.writeFileSync(B('runtime/cache', `faux-${nom}`), '1') : fs.rmSync(B('runtime/cache', `faux-${nom}`), {force: true}));
const reel = (p) => JSON.parse(fs.readFileSync(B('projects', p, 'reels', 'script.json'), 'utf8'));
const CLES = /sk-ant-|FAUSSECLE/;

// ---- serveur de la copie (jamais 8790) ----
if (!BOX.startsWith(WORK) || !fs.existsSync(B('engine/editeur/_faux.py'))) throw new Error('copie absente : node setup-bac.mjs');
const log = fs.openSync(path.join(WORK, `serveur-${PORT}.log`), 'w');
const srv = spawn(process.execPath, [B('app/server.mjs')], {cwd: BOX, env: {...process.env, EDITEUR_PORT: String(PORT), EDITEUR_SANS_NAVIGATEUR: '1'}, stdio: ['ignore', log, log], windowsHide: true});
for (let k = 0; k < 60; k++) {
	try {
		if ((await fetch(`${ORIGIN}/api/reels`)).ok) break;
	} catch {}
	await wait(250);
}
try {
	// ===== GET /api/claude : statut, cle = vrai / faux seulement, estimations par modele =====
	let r = await req('GET', '/api/claude', undefined, null);
	check('statut 200', r.status === 200, r.text.slice(0, 200));
	check('statut : cle booleenne', r.data.cle === true);
	check('statut : estimation par modele ajoutee (estimation_video)', r.data.modeles?.every((m) => typeof m.estimation?.par_video === 'number'), JSON.stringify(r.data.modeles?.[1]));
	check('statut : Haiku ≈ 0,0257 $ / video', Math.abs((r.data.modeles?.find((m) => m.id === 'claude-haiku-4-5')?.estimation?.par_video ?? 0) - 0.0257) < 1e-6);
	marque('fuite', true);
	await wait(2100); // cache du statut : 2 s
	r = await req('GET', '/api/claude', undefined, null);
	check('fuite : aucune cle dans la reponse', !CLES.test(r.text), r.text.slice(0, 300));
	check('fuite : cle (texte) -> false', r.data.cle === false);
	check('fuite : texte masque', String(r.data.avertissement).includes('[clé masquée]'));
	marque('fuite', false);
	marque('statut-ko', true);
	await wait(2100);
	r = await req('GET', '/api/claude', undefined, null);
	check('moteur en panne : 200, pret faux, phrase en francais', r.status === 200 && r.data.pret === false && r.data.indisponible === true && /Claude indisponible/.test(r.data.raison), r.text);
	marque('statut-ko', false);

	// ===== PUT /api/claude/reglages : origine exacte, validation, transmis au moteur =====
	r = await req('PUT', '/api/claude/reglages', {modele: 'claude-haiku-4-5'}, null);
	check('reglages sans origine : 403', r.status === 403);
	r = await req('PUT', '/api/claude/reglages', {modele: 'claude-haiku-4-5'}, `http://localhost:${PORT}`);
	check('reglages origine localhost : 403', r.status === 403);
	r = await req('PUT', '/api/claude/reglages', {modele: 'claude-haiku-4-5'});
	check('reglages modele : 200 + statut frais', r.status === 200 && r.data.modele === 'claude-haiku-4-5', r.text.slice(0, 200));
	check('reglages : jamais de cle', !CLES.test(r.text));
	const mauvais = [[{modele: 'gpt-5'}, /Modèle de Claude/], [{plafond_jour: -1}, /plafond_jour/], [{plafond_mois: 'beaucoup'}, /nombre/], [{inconnu: 1}, /inconnu/],
		[{actif: 'oui'}, /vrai\/faux/], [{espace_travail: 'abc'}, /wrkspc_/], [{}, /rien à enregistrer/], [{modeles_taches: {montage: 'claude-haiku-4-5'}}, /champ inconnu/],
		[{modeles_taches: {critique: 'opus'}}, /Modèle pour « critique »/], [{images_critique: 2.5}, /entier/], [{credit_date: '2 octobre'}, /AAAA-MM-JJ/]];
	for (const [b, re] of mauvais) {
		r = await req('PUT', '/api/claude/reglages', b);
		check(`reglages refuse ${JSON.stringify(b)} (400, francais)`, r.status === 400 && re.test(r.data.error ?? ''), `${r.status} ${r.data.error}`);
	}
	r = await req('PUT', '/api/claude/reglages', {credit_date: '2026-13-45'});
	check('reglages : refus du MOTEUR transmis (400, sa phrase)', r.status === 400 && /credit_date/.test(r.data.error ?? '') && !/Traceback/.test(r.data.error ?? ''), `${r.status} ${r.data.error}`);
	r = await req('PUT', '/api/claude/reglages', {espace_travail: '  wrkspc_ABCDEFGH1234  ', modeles_taches: {critique: 'claude-haiku-4-5'}, plafond_video: 0.3});
	const disque = JSON.parse(fs.readFileSync(B('styles/claude.json'), 'utf8'));
	check('reglages : espace de travail nettoye + tache + plafond ecrits', r.status === 200 && disque.espace_travail === 'wrkspc_ABCDEFGH1234' && disque.modeles_taches.critique === 'claude-haiku-4-5' && disque.plafond_video === 0.3, JSON.stringify(disque));
	r = await req('PUT', '/api/claude/reglages', {espace_travail: null, modele: 'claude-sonnet-5-5', modeles_taches: {critique: null}, plafond_video: 0.25});
	check('reglages : retour aux valeurs de depart', r.status === 200 && r.data.modele === 'claude-sonnet-5-5');

	// ===== GET /api/claude/couts =====
	r = await req('GET', '/api/claude/couts?jours=7', undefined, null);
	check('couts 200 + 20 derniers appels', r.status === 200 && Array.isArray(r.data.derniers) && r.data.derniers.length === 5, r.text.slice(0, 200));
	check('couts : plus recent d\'abord', r.data.derniers?.[0]?.tache === 'test');
	check('couts : cle du journal masquee', !CLES.test(r.text) && r.data.derniers?.[0]?.erreur?.includes('[clé masquée]'), r.data.derniers?.[0]?.erreur);
	r = await req('GET', '/api/claude/couts?video=leads/script', undefined, null);
	check('couts d\'une video', r.status === 200 && r.data.video?.nb === 4);
	for (const q of ['video=../x', 'video=leads', 'jours=0', 'jours=401', 'jours=2.5']) {
		r = await req('GET', `/api/claude/couts?${q}`, undefined, null);
		check(`couts refuse ${q} (400)`, r.status === 400, `${r.status} ${r.text.slice(0, 100)}`);
	}

	// ===== GET /api/revision : depenses Claude par video (badge) =====
	r = await req('GET', '/api/revision', undefined, null);
	const leads = r.data.items.find((i) => i.project === 'leads');
	check('revision : resume Claude de « leads »', Math.abs((leads?.claude?.cout ?? 0) - 0.092) < 1e-9 && leads.claude.groupes.consigne?.n === 2 && leads.claude.groupes.cerveau?.ok === 1,
		JSON.stringify(leads?.claude));
	check('revision : rien pour une video sans Claude', !r.data.items.find((i) => i.project === 'erreurs').claude);
	check('revision : jamais de cle', !CLES.test(r.text));

	// ===== POST /consigne : contrat (job, resultat = ligne JSON du moteur), validation, double clic =====
	r = await req('POST', '/api/reels/leads/script/consigne', {texte: 'enlève le bandeau'}, null);
	check('consigne sans origine : 403', r.status === 403);
	for (const [b, re] of [[{texte: ''}, /Écris ta demande/], [{texte: '   \n '}, /Écris ta demande/], [{texte: 'x'.repeat(801)}, /800/], [{texte: 42}, /du texte/],
		[{texte: 'ok', t: -1}, /Moment/], [{texte: 'ok', t: 'midi'}, /Moment/], [{texte: 'ok', t: true}, /Moment/], [{texte: 'ok', moteur: 'gpt'}, /Moteur inconnu/], [{texte: 'ok', simuler: 'oui'}, /simuler/]]) {
		r = await req('POST', '/api/reels/leads/script/consigne', b);
		check(`consigne refuse ${JSON.stringify(b).slice(0, 50)} (400)`, r.status === 400 && re.test(r.data.error ?? ''), `${r.status} ${r.data.error}`);
	}
	r = await req('POST', '/api/reels/leads/../script/consigne', {texte: 'ok'});
	check('consigne : chemin bizarre refuse', r.status >= 400);
	r = await req('POST', '/api/reels/inconnu/script/consigne', {texte: 'ok'});
	check('consigne : montage inconnu 404', r.status === 404);
	const avantBandeau = reel('leads').banner?.enabled;
	r = await req('POST', '/api/reels/leads/script/consigne', {texte: 'lent : -- enlève le "bandeau" du début\nmerci', t: 12.5});
	check('consigne : 202 + tache', r.status === 202 && /^[a-f0-9-]{36}$/.test(r.data.id ?? ''), r.text.slice(0, 200));
	const id1 = r.data.id;
	r = await req('POST', '/api/reels/leads/script/consigne', {texte: 'autre chose'});
	check('consigne : double clic pendant la tache -> 409', r.status === 409 && /déjà/.test(r.data.error ?? ''), `${r.status} ${r.data.error}`);
	r = await req('POST', '/api/reels/leads/script/claude/cerveau', {});
	check('cerveau pendant une consigne -> 409', r.status === 409);
	r = await req('GET', '/api/revision', undefined, null);
	check('revision : tache de l\'IA en cours sur la fiche', !!r.data.items.find((i) => i.project === 'leads').iaEnCours);
	let j = await job(id1);
	check('consigne : tache terminee', j.status === 'done', JSON.stringify(j).slice(0, 300));
	check('consigne : resultat = contrat (version, avant, changements, refus, question, moteur, cout)',
		j.result?.version === 'script' && typeof j.result.avant === 'string' && Array.isArray(j.result.changements) && Array.isArray(j.result.refus) && 'question' in j.result
		&& j.result.moteur === 'claude' && typeof j.result.cout === 'number', JSON.stringify(j.result));
	const arg = appelsMoteur().filter((a) => a.module === 'consigne').at(-1)?.argv ?? [];
	check('consigne : texte passe tel quel (tirets, guillemets, retour a la ligne)', arg.includes('--texte=lent : -- enlève le "bandeau" du début\nmerci'), JSON.stringify(arg));
	check('consigne : --t=12.500 et --reel script', arg.includes('--t=12.500') && arg[arg.indexOf('--reel') + 1] === 'script', JSON.stringify(arg));
	check('consigne : montage change + historique', reel('leads').banner?.enabled === false && reel('leads').consignes?.length === 2, `${avantBandeau} ${reel('leads').consignes?.length}`);
	check('consigne : version « avant » dans versions/ (bouton Annuler)', fs.existsSync(B('projects/leads/versions/script', j.result.avant)));
	r = await req('POST', '/api/reels/leads/script/restore', {file: j.result.avant});
	check('annuler la consigne : restauration de « avant »', r.status === 200 && reel('leads').consignes?.length === 1, r.text.slice(0, 120));
	r = await req('POST', '/api/reels/leads/script/consigne', {texte: 'ambigu', simuler: true, moteur: 'local'});
	j = await job(r.data.id);
	const arg2 = appelsMoteur().filter((a) => a.module === 'consigne').at(-1)?.argv ?? [];
	check('consigne : question sans rien changer', j.result?.question?.includes('Quel bandeau') && reel('leads').consignes?.length === 1, JSON.stringify(j.result));
	check('consigne : --moteur=local --simuler transmis', arg2.includes('--moteur=local') && arg2.includes('--simuler'), JSON.stringify(arg2));

	// ===== POST /claude/cerveau et /claude/critique : sur un clic, version « avant », un a la fois =====
	r = await req('POST', '/api/reels/leads/script/claude/cerveau', {}, null);
	check('cerveau sans origine : 403', r.status === 403);
	const versionsAvant = fs.readdirSync(B('projects/leads/versions/script')).length;
	r = await req('POST', '/api/reels/leads/script/claude/cerveau', {});
	check('cerveau : 202', r.status === 202, r.text.slice(0, 200));
	r = await req('POST', '/api/reels/leads/script/claude/critique', {});
	check('critique pendant le cerveau -> 409', r.status === 409);
	j = await job((await req('GET', '/api/revision', undefined, null)).data.items.find((i) => i.project === 'leads').iaEnCours?.job ?? '');
	check('cerveau : termine, version « avant » gardee', j.status === 'done' && typeof j.result?.avantServeur === 'string'
		&& fs.existsSync(B('projects/leads/versions/script', j.result.avantServeur)) && fs.readdirSync(B('projects/leads/versions/script')).length === versionsAvant + 1, JSON.stringify(j).slice(0, 300));
	check('cerveau : resultat sans cle (masquee)', !CLES.test(JSON.stringify(j)) && JSON.stringify(j.result).includes('[clé masquée]'));
	r = await req('POST', '/api/reels/leads/script/claude/critique', {video: 'C:\\Windows\\win.ini'});
	check('critique : video hors de l\'editeur refusee (400)', r.status === 400, `${r.status} ${r.data.error}`);
	// revue 2026-10-02 : MEME ligne de commande que le vrai critique_claude.py (<video.mp4> --reel <...> --json) ; la critique
	// ne juge qu'une video EXPORTEE ; l'avis est range dans le rapport du controle de cette video -> fiche de la Revision
	const outRappel = B('livraisons/Lot test/Pourquoi on rappelle en 60 secondes - FINAL.mp4');
	r = await req('POST', '/api/reels/leads/script/claude/critique', {});
	check('critique sans export : refus clair (400)', r.status === 400 && /exporte d'abord/.test(r.data.error ?? ''), `${r.status} ${r.data.error}`);
	r = await req('POST', '/api/reels/rappel/script/controle', {video: outRappel});
	j = await job(r.data.id);
	check('controle de l\'export de rappel (rapport ou ranger l\'avis)', j.status === 'done', JSON.stringify(j).slice(0, 200));
	r = await req('POST', '/api/reels/rappel/script/claude/critique', {video: outRappel});
	j = await job(r.data.id);
	let argc = appelsMoteur().filter((a) => a.module === 'critique_claude').at(-1)?.argv ?? [];
	check('critique : ligne de commande du vrai module (video, --reel dossier id, --json)', j.status === 'done' && j.result?.ok === true && j.result?.note === 6.5
		&& argc[0] === outRappel && argc[1] === '--reel' && argc[2] === B('projects', 'rappel') && argc[3] === 'script' && argc.includes('--json') && !argc.includes('--video'), JSON.stringify(argc));
	let itRappel = (await req('GET', '/api/revision', undefined, null)).data.items.find((i) => i.project === 'rappel');
	check('critique : avis range dans le rapport de la video livree -> fiche de la Revision', itRappel.exports?.[0]?.controle?.claude?.note === 6.5, JSON.stringify(itRappel.exports?.[0]?.controle ?? null).slice(0, 300));
	r = await req('POST', '/api/reels/rappel/script/claude/critique', {});
	j = await job(r.data.id);
	argc = appelsMoteur().filter((a) => a.module === 'critique_claude').at(-1)?.argv ?? [];
	check('critique sans {video} : le dernier export de la video', j.status === 'done' && argc[0] === outRappel, JSON.stringify(argc));
	marque('critique-plafond', true);
	r = await req('POST', '/api/reels/rappel/script/claude/critique', {});
	j = await job(r.data.id);
	marque('critique-plafond', false);
	check('critique refusee (plafond) : ok = false + message, tache terminee', j.status === 'done' && j.result?.ok === false && /plafond/.test(j.result?.message ?? ''), JSON.stringify(j.result ?? j).slice(0, 300));
	fs.renameSync(B('engine/editeur/cerveau_claude.py'), B('engine/editeur/cerveau_claude.py.off'));
	r = await req('POST', '/api/reels/leads/script/claude/cerveau', {});
	check('module absent : phrase claire (400)', r.status === 400 && /pas encore installées/.test(r.data.error ?? ''), r.data.error);
	fs.renameSync(B('engine/editeur/cerveau_claude.py.off'), B('engine/editeur/cerveau_claude.py'));
	r = await req('GET', '/api/revision', undefined, null);
	check('revision : depense de « leads » mise a jour (cerveau 2 fois)', r.data.items.find((i) => i.project === 'leads').claude?.groupes?.cerveau?.n === 2);

	// ===== export : reel.consignes jamais envoye ; critique automatique seulement si cochee =====
	const nCritiques = () => appelsMoteur().filter((a) => a.module === 'critique_claude').length;
	const vus = () => (fs.existsSync(B('runtime/cache/jobs-vus')) ? fs.readdirSync(B('runtime/cache/jobs-vus')).sort() : []);
	let avantCrit = nCritiques();
	r = await req('POST', '/api/reels/leads/script/export', {formats: ['9:16']});
	check('export : 202', r.status === 202, r.text.slice(0, 200));
	let e = await job(r.data.id);
	await wait(1500);
	const recu = JSON.parse(fs.readFileSync(B('runtime/cache/jobs-vus', vus().at(-1)), 'utf8'));
	check('export : reel.consignes retire de ce que le rendu recoit', e.status === 'done' && recu.reel && !('consignes' in recu.reel) && Array.isArray(reel('leads').consignes), e.status);
	check('export : critique automatique eteinte -> aucune critique', nCritiques() === avantCrit);
	// critique automatique cochee : c'est le controle apres export (moteur, controle._avis_auto) qui demande l'avis ; le serveur
	// ne relance PAS une critique a part (un seul appel paye) ; l'avis arrive sur la fiche avec le resume du controle
	await req('PUT', '/api/claude/reglages', {critique_auto: true});
	avantCrit = nCritiques();
	const nAuto = () => appelsMoteur().filter((a) => a.module === 'controle-avis').length;
	const avantAuto = nAuto();
	r = await req('POST', '/api/reels/erreurs/script/export', {formats: ['9:16']});
	e = await job(r.data.id);
	for (let k = 0; k < 40 && nAuto() === avantAuto; k++) await wait(250);
	await wait(1500);
	const eCtl = (await req('GET', `/api/jobs/${e.id}`, undefined, null)).data; // export de l'editeur : resume du controle sur la tache
	check('export : critique automatique cochee -> un seul avis (dans le controle), pas de critique en double', nAuto() === avantAuto + 1 && nCritiques() === avantCrit,
		`controle-avis ${nAuto() - avantAuto}, critiques ${nCritiques() - avantCrit}`);
	check('export : avis automatique avec le resume du controle de cet export',eCtl.controle?.claude?.note === 7, JSON.stringify(eCtl.controle ?? null).slice(0, 300));
	// critique a la main de cet export : le reel EXACT de l'export (export.json garde par le controle apres export)
	r = await req('POST', '/api/reels/erreurs/script/claude/critique', {video: e.out});
	j = await job(r.data.id);
	argc = appelsMoteur().filter((a) => a.module === 'critique_claude').at(-1)?.argv ?? [];
	check('critique d\'un export : --reel export.json de cet export', j.status === 'done' && argc[0] === e.out && /export-9x16[\\/]export\.json$/.test(argc[2] ?? '') && argc.length === 4, JSON.stringify(argc));
	await req('PUT', '/api/claude/reglages', {critique_auto: false});
	for (let k = 0; k < 40; k++) {
		const it = (await req('GET', '/api/revision', undefined, null)).data.items.find((i) => i.project === 'erreurs');
		if (!it.iaEnCours) break;
		await wait(250);
	}

	// ===== PUT /api/reels/:p/:v : nouveaux champs sfx (contrat « sons ») =====
	const base = reel('erreurs').sfx ?? {enabled: true, transition: null, highlight: null, highlightGap: 4, cta: null, start: null, volume: 0.6};
	const pool = [{name: 'sfx/banque/transition/whoosh-doux.wav', pic: 0.18, gain: 1, role: 'transition'}, {name: 'whoosh-court'}];
	r = await req('PUT', '/api/reels/erreurs/script', {sfx: {...base, varier: true, famille: 'punchy', pool}});
	check('sfx valide : 200 et enregistre', r.status === 200 && reel('erreurs').sfx.famille === 'punchy' && reel('erreurs').sfx.pool.length === 2, r.text);
	for (const [nom, sfx, re] of [['famille auto', {famille: 'auto'}, null], ['famille nulle', {famille: null}, null], ['pool vide', {pool: []}, null], ['varier faux', {varier: false}, null]]) {
		r = await req('PUT', '/api/reels/erreurs/script', {sfx: {...base, ...sfx}});
		check(`sfx ${nom} : 200`, r.status === 200 && !re, r.text);
	}
	const trop = Array.from({length: 33}, (_, k) => ({name: `s${k}`}));
	for (const [nom, sfx, re] of [['varier texte', {varier: 'oui'}, /varier/], ['famille majuscules', {famille: 'Punchy!'}, /Famille/], ['famille longue', {famille: 'a'.repeat(41)}, /Famille/],
		['pool 33', {pool: trop}, /32/], ['pool objet', {pool: {name: 'x'}}, /32/], ['son ..', {pool: [{name: 'sfx/../../cles-api.env'}]}, /invalide/],
		['son chemin absolu', {pool: [{name: '/etc/passwd'}]}, /fichier/], ['son champ inconnu', {pool: [{name: 'x', licence: 'CC0'}]}, /champ inconnu/],
		['son sans nom', {pool: [{pic: 0.1}]}, /name/], ['gain 5', {pool: [{name: 'x', gain: 5}]}, /gain/], ['pic negatif', {pool: [{name: 'x', pic: -0.1}]}, /sommet/],
		['role bizarre', {pool: [{name: 'x', role: 'Mot Fort'}]}, /rôle/]]) {
		r = await req('PUT', '/api/reels/erreurs/script', {sfx: {...base, ...sfx}});
		check(`sfx refuse ${nom} (400 francais)`, r.status === 400 && re.test(r.data.error ?? ''), `${r.status} ${r.data.error}`);
	}
	check('sfx : un refus ne touche pas le reel', reel('erreurs').sfx.varier === false);

	// ===== GET /api/sons-transitions =====
	r = await req('GET', '/api/sons-transitions', undefined, null);
	check('sons-transitions absent : 404 en francais', r.status === 404 && /pas encore installé/.test(r.data.error ?? ''));
	fs.writeFileSync(B('styles/sons-transitions.json'), '\uFEFF' + JSON.stringify({version: 1, familles: {doux: {label: 'Doux'}}, styles: {'reel-impact': 'punchy'}}));
	r = await req('GET', '/api/sons-transitions', undefined, null);
	check('sons-transitions : fichier renvoye tel quel', r.status === 200 && r.data.familles?.doux?.label === 'Doux' && r.data.styles['reel-impact'] === 'punchy', r.text);
	fs.writeFileSync(B('styles/sons-transitions.json'), '{abime');
	r = await req('GET', '/api/sons-transitions', undefined, null);
	check('sons-transitions illisible : 500 en francais', r.status === 500 && /illisible/.test(r.data.error ?? ''));
	fs.rmSync(B('styles/sons-transitions.json'), {force: true});

	// ===== rien du faux moteur n'a parle a l'exterieur ; aucune route ne renvoie de cle =====
	const tout = appelsMoteur();
	check('faux moteur seulement (aucun module reel appele)', tout.every((a) => ['editeur', 'consigne', 'cerveau_claude', 'critique_claude', 'controle-avis'].includes(a.module)), JSON.stringify(tout.map((a) => a.module)));
	for (const route of ['/api/claude', '/api/claude/couts', '/api/revision', '/api/reels/leads/script/open', '/api/queue']) {
		r = await req('GET', route, undefined, null);
		check(`${route} : aucune cle`, !CLES.test(r.text));
	}
} finally {
	try {
		execFileSync(path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe'), ['/PID', String(srv.pid), '/T', '/F'], {stdio: 'ignore'});
	} catch {}
	fs.closeSync(log);
}
console.log(`\n${ok}/${ok + ko} reussis${ko ? `\nEchecs :\n- ${echecs.join('\n- ')}` : ''}`);
process.exit(ko ? 1 : 0);
