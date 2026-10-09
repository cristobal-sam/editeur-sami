// Tests serveur (copie 18793, faux moteur + faux rendu « gel ») : corbeille avec restauration, partage, garde-fou
// proportionnel, nettoyage des fichiers temporaires, message de blocage garde apres « Annuler », item.style dans /template.
// COPIE DURABLE du script du bac a sable runtime\cache\tmp\interface-fable-85584\ (a lancer DEPUIS ce bac a sable, il attend
// son dossier rendu\ a cote de lui) : node setup-serveur.mjs ; cp render-gel.mjs rendu/remotion/render.mjs ; cd rendu ;
//   TEST_AUTO_S=3 TEST_AUTRE_S=0 EDITEUR_BLOCAGE_AUTRE_S=6 EDITEUR_BLOCAGE_PAR_MIN_S=2 EDITEUR_GRACE_STOP_S=4
//   EDITEUR_BLOCAGE_S=10 EDITEUR_BLOCAGE_MARGE_S=5 EDITEUR_PORT=18793 node app/server.mjs ; puis node test-corbeille.mjs.
// Resultat du 2026-09-30 : 73 verifications OK (resultat-test-corbeille.txt).
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const box = path.join(HERE, 'rendu');
const P = (...p) => path.join(box, ...p);
const BASE = 'http://127.0.0.1:18793';
let fails = 0;
const ok = (cond, msg) => {
	console.log(`${cond ? 'OK  ' : 'ECHEC'} ${msg}`);
	if (!cond) fails++;
};
const call = async (method, route, body, origin = BASE) => {
	const headers = {'content-type': 'application/json'};
	if (origin) headers.origin = origin;
	const r = await fetch(BASE + route, {method, headers, body: body ? JSON.stringify(body) : undefined});
	let data = null;
	try {
		data = await r.json();
	} catch {}
	return {status: r.status, data};
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ex = (...p) => fs.existsSync(P(...p));
const rel = (p) => path.relative(box, p).split(path.sep).join('/');
const appels = () => (fs.existsSync(P('runtime/cache/appels-moteur.log')) ? fs.readFileSync(P('runtime/cache/appels-moteur.log'), 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []);
const autoPour = (unit) => appels().filter((a) => a.argv[0] === 'auto' && a.argv[1].split(path.sep).join('/').endsWith(unit)).length;
const journal = () => (fs.existsSync(P('runtime/cache/erreurs-serveur.log')) ? fs.readFileSync(P('runtime/cache/erreurs-serveur.log'), 'utf8') : '');
const wait = async (job, max = 120000, onTick = null) => {
	const t0 = Date.now();
	for (;;) {
		const j = (await call('GET', `/api/jobs/${job}`)).data;
		if (onTick) await onTick(j);
		if (!['queued', 'running'].includes(j.status) || Date.now() - t0 > max) return {...j, waited: (Date.now() - t0) / 1000};
		await sleep(500);
	}
};

await sleep(6000); // le faux montage de G (3 s) est fini : G en erreur
let s = (await call('GET', '/api/revision')).data;
const find = (id) => s.items.find((i) => i.id === id);
ok(find('999999999991')?.status === 'erreur', `G montee par le faux moteur puis en erreur : ${find('999999999991')?.status}`);
const nAutoDebut = appels().filter((a) => a.argv[0] === 'auto').length;
ok(nAutoDebut === 1, `un seul appel « auto » du faux moteur au depart (G) : ${nAutoDebut}`);

// ---- 16. partage calcule par le serveur (meme regle que planSuppression)
ok(find('ddddddddddd1')?.partage?.unit === true && find('ddddddddddd1')?.partage?.project === false, `D1 : partage ${JSON.stringify(find('ddddddddddd1')?.partage)} (rushs partages avec D2)`);
ok(find('aaaaaaaaaaa1')?.partage?.unit === false && find('aaaaaaaaaaa1')?.partage?.project === false, `A : partage ${JSON.stringify(find('aaaaaaaaaaa1')?.partage)}`);
// une video RETIREE de la liste (cachee) compte aussi : D1 retiree, D2 partage toujours ses rushs
await call('POST', '/api/revision/ddddddddddd1/retirer', {});
s = (await call('GET', '/api/revision')).data;
ok(!find('ddddddddddd1') && find('ddddddddddd2')?.partage?.unit === true, `D1 retiree (cachee) : D2 partage ${JSON.stringify(find('ddddddddddd2')?.partage)}`);
ok(s.corbeilleN === 0, `corbeilleN au depart : ${s.corbeilleN}`);
let cb = await call('GET', '/api/revision/corbeille');
ok(cb.status === 200 && Array.isArray(cb.data.entrees) && cb.data.entrees.length === 0 && cb.data.corbeille === P('corbeille'), `GET corbeille vide : ${JSON.stringify(cb.data)}`);

// ---- origine
for (const o of [null, 'http://localhost:18793', 'http://127.0.0.1:18793.evil.com', 'http://127.0.0.1:8790']) {
	const r = await call('POST', '/api/revision/corbeille/restaurer', {dossier: 'x'}, o);
	ok(r.status === 403, `restaurer, origine ${o ?? '(aucune)'} refusee : ${r.status}`);
}

// ---- 15. suppression de A (prise, projet + videos brutes + livraison), manifeste enrichi
const ra = await call('POST', '/api/revision/aaaaaaaaaaa1/supprimer', {});
ok(ra.status === 200 && !ex('projects/faux-a') && !ex('media/entree/Lot T1/Vidéo A'), `A supprimee : ${ra.status}`);
const trashA = ra.data.supprime.corbeille;
const dossierA = path.basename(trashA);
let man = JSON.parse(fs.readFileSync(path.join(trashA, 'corbeille.json'), 'utf8'));
ok(man.lot && man.lot.complete === true && man.registre?.id === 'aaaaaaaaaaa1' && man.registre.status === 'pris', `manifeste : lot ${JSON.stringify(man.lot)}, registre ${man.registre?.id} (${man.registre?.status})`);
ok(/Restaurer/.test(man.pour_la_remettre) && /remontée/.test(man.pour_la_remettre), `note pour_la_remettre : ${man.pour_la_remettre.slice(0, 90)}…`);
ok(ra.data.corbeilleN === 1 && !ra.data.lots['Lot T1'], `corbeilleN=${ra.data.corbeilleN}, lot T1 retire`);
cb = await call('GET', '/api/revision/corbeille');
const eA = cb.data.entrees.find((e) => e.dossier === dossierA);
ok(cb.data.entrees.length === 1 && eA?.titre === 'Vidéo A' && eA.restaurable === true && eA.deplacements.length === 2, `GET corbeille : ${JSON.stringify(eA)}`);

// ---- refus : dossier invalide, place occupee, manifeste hors des dossiers permis
for (const d of ['..', '.', 'a/b', 'a\\b', '', null, 'inexistant 2020', '.cachee']) {
	const r = await call('POST', '/api/revision/corbeille/restaurer', {dossier: d});
	ok([400, 404].includes(r.status), `dossier ${JSON.stringify(d)} refuse (${r.status}) : ${r.data?.error}`);
}
fs.mkdirSync(P('projects/faux-a'), {recursive: true});
cb = await call('GET', '/api/revision/corbeille');
ok(cb.data.entrees[0].restaurable === false && /déjà occupé/.test(cb.data.entrees[0].raison), `place occupee vue par GET : ${cb.data.entrees[0].raison}`);
let r = await call('POST', '/api/revision/corbeille/restaurer', {dossier: dossierA});
ok(r.status === 409 && /déjà occupé/.test(r.data.error) && fs.existsSync(path.join(trashA, 'projects/faux-a/reels/script.json')) && fs.existsSync(path.join(trashA, 'media/entree/Lot T1/Vidéo A/prise1.mp4')),
	`restauration refusee, rien deplace (${r.status}) : ${r.data?.error}`);
fs.rmdirSync(P('projects/faux-a'));
// jonction posee sur la destination (projects/faux-a -> dehors-p) : refusee
fs.symlinkSync(P('dehors-p'), P('projects/faux-a'), 'junction');
r = await call('POST', '/api/revision/corbeille/restaurer', {dossier: dossierA});
ok(r.status !== 200 && fs.existsSync(path.join(trashA, 'projects/faux-a/reels/script.json')) && ex('dehors-p/NE-PAS-DEPLACER.txt') && !ex('dehors-p/reels'),
	`jonction sur la destination refusee (${r.status}) : ${r.data?.error}`);
fs.rmdirSync(P('projects/faux-a'));
// jonction sur le PARENT de la destination (media/entree/Lot T1 -> dehors-u) : refusee
fs.symlinkSync(P('dehors-u'), P('media/entree/Lot T1'), 'junction');
r = await call('POST', '/api/revision/corbeille/restaurer', {dossier: dossierA});
ok(r.status !== 200 && !ex('dehors-u/Vidéo A') && fs.existsSync(path.join(trashA, 'media/entree/Lot T1/Vidéo A/prise1.mp4')), `jonction sur le parent refusee (${r.status}) : ${r.data?.error}`);
fs.rmdirSync(P('media/entree/Lot T1'));
// Une jonction reste interdite meme si sa cible est a l'interieur du dossier autorise.
fs.mkdirSync(P('media/entree/Parent interne'), {recursive: true});
fs.symlinkSync(P('media/entree/Parent interne'), P('media/entree/Lot T1'), 'junction');
r = await call('POST', '/api/revision/corbeille/restaurer', {dossier: dossierA});
ok(r.status === 400 && !ex('media/entree/Parent interne/Vidéo A') && !ex('projects/faux-a'), 'jonction interne sur le parent refusee sans aucun deplacement');
fs.rmdirSync(P('media/entree/Lot T1'));
fs.rmdirSync(P('media/entree/Parent interne'));
// manifestes pieges : destination hors de projects / media/entree, source hors de la corbeille, nom de projet invalide
const piege = (name, deplacements, files = []) => {
	const dir = P('corbeille', name);
	fs.mkdirSync(dir, {recursive: true});
	for (const f of files) {
		fs.mkdirSync(path.dirname(path.join(dir, f)), {recursive: true});
		fs.writeFileSync(path.join(dir, f), 'piege');
	}
	fs.writeFileSync(path.join(dir, 'corbeille.json'), JSON.stringify({supprime: '2020-01-01T00:00:00.000Z', video: {titre: name}, deplacements, registre: {id: '123456789abc', unit: 'media/entree/X/y.mp4', lot: 'X', name: 'y.mp4', status: 'erreur'}}));
	return name;
};
const p1 = piege('2020-01-01 00h00 Piege app', [{avant: 'app/server.mjs', maintenant: `corbeille/2020-01-01 00h00 Piege app/app/server.mjs`}], ['app/server.mjs']);
const p2 = piege('2020-01-01 00h00 Piege dotdot', [{avant: 'projects/../app/x', maintenant: `corbeille/2020-01-01 00h00 Piege dotdot/projects/x`}], ['projects/x']);
const p3 = piege('2020-01-01 00h00 Piege source', [{avant: 'projects/nouveau-p', maintenant: 'app/ui'}]);
const p4 = piege('2020-01-01 00h00 Piege cache', [{avant: 'projects/_cache', maintenant: `corbeille/2020-01-01 00h00 Piege cache/projects/_cache`}], ['projects/_cache/x']);
const p5 = piege('2020-01-01 00h00 Piege media', [{avant: 'media/rushs/x.mp4', maintenant: `corbeille/2020-01-01 00h00 Piege media/media/rushs/x.mp4`}], ['media/rushs/x.mp4']);
const p6 = piege('2020-01-01 00h00 Piege absolu', [{avant: 'projects/abs', maintenant: P('dehors-p')}]);
cb = await call('GET', '/api/revision/corbeille');
for (const [name, motif] of [[p1, /hors de projects/], [p2, /invalide|refusé/], [p3, /corbeille|refusé/], [p4, /invalide/], [p5, /hors de projects/], [p6, /corbeille|refusé/]]) {
	const e = cb.data.entrees.find((x) => x.dossier === name);
	const rr = await call('POST', '/api/revision/corbeille/restaurer', {dossier: name});
	ok(e && e.restaurable === false && motif.test(e.raison) && rr.status === 400, `piege « ${name.slice(17)} » : GET non restaurable (${e?.raison}) ; POST ${rr.status}`);
}
const serverText = fs.readFileSync(P('app/server.mjs'), 'utf8');
ok(serverText.length > 10000 && ex('app/ui/index.html') && !ex('projects/nouveau-p') && !ex('projects/x') && !ex('media/rushs/x.mp4') && !ex('projects/abs') && ex('dehors-p/NE-PAS-DEPLACER.txt'), 'rien n\'a bouge avec les pieges (app, projects, media, dehors-p intacts)');
for (const name of [p1, p2, p3, p4, p5, p6]) fs.rmSync(P('corbeille', name), {recursive: true, force: true});

// ---- restauration de A : dossiers de retour, fiche de retour avec son statut, lot remis, AUCUN nouveau montage
const nAutoAvant = appels().filter((a) => a.argv[0] === 'auto').length;
r = await call('POST', '/api/revision/corbeille/restaurer', {dossier: dossierA});
ok(r.status === 200, `restauration de A : ${r.status} ${r.data?.error ?? ''}`);
const rs = r.data.restaure;
console.log('     reponse :', JSON.stringify(rs).slice(0, 300));
ok(rs?.titre === 'Vidéo A' && rs.remis.length === 2 && rs.remis.includes('projects/faux-a') && rs.remis.includes('media/entree/Lot T1/Vidéo A'), `remis : ${JSON.stringify(rs?.remis)}`);
ok(ex('projects/faux-a/reels/script.json') && ex('projects/faux-a/versions') && ex('media/entree/Lot T1/Vidéo A/prise1.mp4') && ex('media/entree/Lot T1/Vidéo A/script.docx'), 'A : projet et videos brutes de retour a leur place');
ok(rs.item?.id === 'aaaaaaaaaaa1' && rs.item.status === 'pris' && rs.item.project === 'faux-a' && rs.item.taken?.out, `fiche de retour : ${rs.item?.id} ${rs.item?.status} (projet ${rs.item?.project})`);
ok(r.data.items.some((i) => i.id === 'aaaaaaaaaaa1' && i.status === 'pris') && r.data.lots['Lot T1']?.complete === true && r.data.lots['Lot T1'].uploading === false, `liste et lot T1 remis : ${JSON.stringify(r.data.lots['Lot T1'])}`);
ok(r.data.corbeilleN === 0, `corbeilleN apres restauration : ${r.data.corbeilleN}`);
const disk = JSON.parse(fs.readFileSync(P('projects/_revision.json'), 'utf8'));
ok(disk.items.filter((i) => i.id === 'aaaaaaaaaaa1' || i.unit === 'media/entree/Lot T1/Vidéo A').length === 1 && disk.lots['Lot T1'], 'registre sur disque : une seule fiche pour A, lot present');
ok(!fs.existsSync(path.join(trashA, 'corbeille.json')) && fs.existsSync(path.join(trashA, 'restaure.json')) && !fs.existsSync(path.join(trashA, 'projects')) && !fs.existsSync(path.join(trashA, 'media')),
	`corbeille : manifeste renomme restaure.json, sous-dossiers vides retires (${fs.readdirSync(trashA).join(', ')})`);
cb = await call('GET', '/api/revision/corbeille');
ok(cb.data.entrees.length === 0, `GET corbeille apres restauration : ${cb.data.entrees.length} entree(s)`);
const again = await call('POST', '/api/revision/corbeille/restaurer', {dossier: dossierA});
ok(again.status === 404, `deuxieme restauration : ${again.status} (${again.data?.error})`);
ok(/video restauree « Vidéo A »/.test(journal()), 'journal : « video restauree »');
console.log('     attente de 12 s (deux passages du scanneur)…');
await sleep(12000);
s = (await call('GET', '/api/revision')).data;
const a = find('aaaaaaaaaaa1');
ok(a?.status === 'pris' && a.stage === 'Prête', `A apres 12 s : ${a?.status} / ${a?.stage} (pas de nouveau montage)`);
ok(s.items.filter((i) => i.unit === 'media/entree/Lot T1/Vidéo A').length === 1, 'une seule fiche pour l\'unite de A');
ok(appels().filter((x) => x.argv[0] === 'auto').length === nAutoAvant && autoPour('Lot T1/Vidéo A') === 0, `faux moteur : aucun appel « auto » pour A (total ${appels().filter((x) => x.argv[0] === 'auto').length})`);
ok(!s.busy, `montage au repos : busy=${s.busy}`);

// ---- jumelle : D2 supprimee (rushs gardes pour D1) puis restauree : fiche de retour malgre l'unite partagee
const rd2 = await call('POST', '/api/revision/ddddddddddd2/supprimer', {});
ok(rd2.status === 200 && rd2.data.supprime.gardes.length === 1 && ex('media/entree/Lot T3/Tournage/a.mp4') && !ex('projects/faux-d2'), `D2 supprimee, rushs gardes : ${rd2.data?.supprime?.gardes?.[0]}`);
const dossierD2 = path.basename(rd2.data.supprime.corbeille);
r = await call('POST', '/api/revision/corbeille/restaurer', {dossier: dossierD2});
const diskD = JSON.parse(fs.readFileSync(P('projects/_revision.json'), 'utf8'));
ok(r.status === 200 && r.data.restaure.item?.id === 'ddddddddddd2' && ex('projects/faux-d2/reels/script.json') && diskD.items.filter((i) => i.unit === 'media/entree/Lot T3/Tournage').length === 2,
	`D2 restauree : ${r.status} fiche ${r.data?.restaure?.item?.id} (${r.data?.restaure?.item?.status}), 2 fiches sur l'unite partagee (D1 cachee)`);

// ---- video en erreur sans projet (G) : supprimee puis restauree, statut « erreur » garde, aucun montage
const rg = await call('POST', '/api/revision/999999999991/supprimer', {});
ok(rg.status === 200 && !ex('media/entree/Lot T6/Vidéo G'), `G (erreur, sans projet) supprimee : ${rg.status}`);
r = await call('POST', '/api/revision/corbeille/restaurer', {dossier: path.basename(rg.data.supprime.corbeille)});
ok(r.status === 200 && r.data.restaure.item?.status === 'erreur' && ex('media/entree/Lot T6/Vidéo G/g.mp4') && r.data.lots['Lot T6'], `G restauree en « ${r.data?.restaure?.item?.status} », lot T6 remis`);
await sleep(6000);
ok(autoPour('Lot T6/Vidéo G') === 1, `faux moteur : toujours un seul appel « auto » pour G (${autoPour('Lot T6/Vidéo G')})`);

// ---- montage disparu de la corbeille : non restaurable ; puis fiche « pret » sans montage -> « attente » (remontee)
const rh = await call('POST', '/api/revision/888888888881/supprimer', {});
const trashH = rh.data.supprime.corbeille;
ok(rh.status === 200 && fs.existsSync(path.join(trashH, 'projects/court')), `H supprimee : ${rh.status}`);
fs.renameSync(path.join(trashH, 'projects/court'), P('court-a-part'));
cb = await call('GET', '/api/revision/corbeille');
ok(cb.data.entrees[0]?.restaurable === false && /n'est plus dans la corbeille/.test(cb.data.entrees[0]?.raison), `montage deplace a la main : ${cb.data.entrees[0]?.raison}`);
r = await call('POST', '/api/revision/corbeille/restaurer', {dossier: path.basename(trashH)});
ok(r.status === 400 && !ex('media/entree/Lot T7/Vidéo H'), `restauration refusee, rien deplace (${r.status})`);
// le manifeste ne parle plus que des videos brutes : la fiche « pret » revient en « attente » et un montage part (attendu)
man = JSON.parse(fs.readFileSync(path.join(trashH, 'corbeille.json'), 'utf8'));
man.deplacements = man.deplacements.filter((d) => d.avant !== 'projects/court');
fs.writeFileSync(path.join(trashH, 'corbeille.json'), JSON.stringify(man));
fs.rmSync(P('court-a-part'), {recursive: true, force: true});
r = await call('POST', '/api/revision/corbeille/restaurer', {dossier: path.basename(trashH)});
ok(r.status === 200 && ['attente', 'travail'].includes(r.data.restaure.item?.status) && /remontée/.test(r.data.restaure.note), `H sans montage : ${r.data?.restaure?.item?.status} — ${r.data?.restaure?.note}`);
await sleep(5000);
ok(autoPour('Lot T7/Vidéo H') === 1, `faux moteur : un montage relance pour H (${autoPour('Lot T7/Vidéo H')})`);

// ---- 20. /template de l'editeur met a jour item.style (faux moteur : la commande echoue, on verifie donc via /restore)
const before = JSON.parse(fs.readFileSync(P('projects/faux-a/reels/script.json'), 'utf8'));
before.template = 'reel-karaoke';
fs.mkdirSync(P('projects/faux-a/versions/script'), {recursive: true});
fs.writeFileSync(P('projects/faux-a/versions/script/2020-01-01T00-00-00 karaoke.json'), JSON.stringify(before));
const rv = await call('POST', '/api/reels/faux-a/script/restore', {file: '2020-01-01T00-00-00 karaoke.json'});
const diskV = JSON.parse(fs.readFileSync(P('projects/_revision.json'), 'utf8'));
ok(rv.status === 200 && rv.data.reel.template === 'reel-karaoke' && diskV.items.find((i) => i.id === 'aaaaaaaaaaa1')?.style === 'reel-karaoke', `/restore : item.style = ${diskV.items.find((i) => i.id === 'aaaaaaaaaaa1')?.style} dans le registre`);
const rt = await call('POST', '/api/reels/faux-a/script/template', {id: 'podcast-clip'});
ok(rt.status === 400 && /Faux moteur/.test(rt.data?.error ?? ''), `/template avec le faux moteur echoue avant la mise a jour (${rt.status}) : attendu`);

// ---- 17/18/19. garde-fou proportionnel, nettoyage, « Annuler » apres blocage (faux rendu « gel » : montage de la voix sans fin)
const gel = (name, secondes) => {
	const reel = JSON.parse(fs.readFileSync(P('reel-video1video1.json'), 'utf8'));
	const c = {...reel.clips[0], in: 0, out: secondes, words: []};
	Object.assign(reel, {project: name, id: 'script', variant: null, title: `Gel ${secondes} s`, clips: [c], broll: [], graphics: [], delivery: P('livraisons', 'gel')});
	fs.mkdirSync(P('projects', name, 'reels'), {recursive: true});
	fs.writeFileSync(P('projects', name, 'project.json'), JSON.stringify({name, label: name, timeline: [], variants: [], sources: reel.sources, script: {blocks: []}}));
	fs.writeFileSync(P('projects', name, 'reels', 'script.json'), JSON.stringify(reel));
	return P('livraisons', 'gel', `Gel ${secondes} s - FINAL.mp4`);
};
const out1 = gel('gel1', 60);
const out10 = gel('gel10', 600);
fs.mkdirSync(path.dirname(out1), {recursive: true});
fs.writeFileSync(out1, 'final existant');
const temps = (out) => ['.image.mp4', '.fx.raw', '.voix.wav', '.mix.wav', '.final.mp4'].map((e) => out + e);
let t0 = Date.now();
let rx = await call('POST', '/api/reels/gel1/script/export', {formats: ['9:16']});
ok(rx.status === 202 && !('dureeMontage' in rx.data), `export gel1 (1 min) lance : ${rx.status}`);
await sleep(1500);
ok(temps(out1).every((f) => fs.existsSync(f)), 'fichiers temporaires crees par le faux rendu');
let j1 = await wait(rx.data.id);
const s1 = (Date.now() - t0) / 1000;
ok(j1.status === 'failed' && /^L'export s'est bloqué à 0 % \(montage de la voix\)/.test(j1.error || ''), `gel1 arrete apres ${s1.toFixed(1)} s : ${j1.status} — ${j1.error}`);
await sleep(1000);
ok(temps(out1).every((f) => !fs.existsSync(f)), `fichiers temporaires de gel1 nettoyes (${temps(out1).filter((f) => fs.existsSync(f)).map((f) => path.basename(f)).join(', ') || 'aucun reste'})`);
ok(fs.readFileSync(out1, 'utf8') === 'final existant', 'FINAL.mp4 preexistant intact');
t0 = Date.now();
rx = await call('POST', '/api/reels/gel10/script/export', {formats: ['9:16']});
let cancelled = false;
const j10 = await wait(rx.data.id, 120000, async (j) => {
	// « Annuler » clique pendant le delai de grace qui suit le blocage : le message de blocage doit rester
	if (j.blocked && j.status === 'running' && !cancelled) {
		cancelled = true;
		const c = await call('POST', `/api/jobs/${rx.data.id}/cancel`);
		console.log(`     blocage detecte a ${((Date.now() - t0) / 1000).toFixed(1)} s, « Annuler » envoye : ${c.status}`);
	}
});
const s10 = (Date.now() - t0) / 1000;
ok(cancelled, 'annulation envoyee pendant le delai de grace');
ok(j10.status === 'failed' && /bloqué à 0 % \(montage de la voix\)/.test(j10.error || ''), `gel10 (10 min) arrete apres ${s10.toFixed(1)} s : ${j10.status} — ${(j10.error || '').slice(0, 80)}`);
ok(s10 - s1 >= 10, `limite plus longue pour 10 min que pour 1 min : ${s10.toFixed(1)} s contre ${s1.toFixed(1)} s`);
const lim = [...journal().matchAll(/export bloque .*limite (\d+) s, montage (\d+) s/g)].map((m) => [Number(m[1]), Number(m[2])]);
ok(lim.length >= 2 && lim.at(-2)[0] === 8 && lim.at(-2)[1] === 60 && lim.at(-1)[0] === 26 && lim.at(-1)[1] === 600, `journal : limites ${JSON.stringify(lim.slice(-2))} (attendu [8,60] puis [26,600])`);
await sleep(1000);
ok(temps(out10).every((f) => !fs.existsSync(f)) && !fs.existsSync(out10), 'fichiers temporaires de gel10 nettoyes, pas de FINAL');
const q = (await call('GET', '/api/queue')).data;
ok(Array.isArray(q) && q.every((x) => !['queued', 'running'].includes(x.status)) && q.every((x) => !('dureeMontage' in x) && !('stopFile' in x)), 'file d\'exports vide, champs internes absents');
console.log(fails ? `\n${fails} ECHEC(S)` : '\nTOUS LES TESTS OK');
