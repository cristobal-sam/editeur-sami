// Test isole des fonctions ajoutees a app/server.mjs (styles de l'utilisateur + exports multi-formats de la Revision).
// Le code est EXTRAIT du fichier serveur et execute dans un bac a sable (vm) : aucun serveur lance, aucun fichier reel touche.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const SRC = fs.readFileSync('D:/Tools/editeur_sami/app/server.mjs', 'utf8');
const SANDBOX = fs.mkdtempSync('D:/Tools/editeur_sami/runtime/cache/tmp/test-styles-ui-');
fs.mkdirSync(SANDBOX, {recursive: true});
fs.cpSync('D:/Tools/editeur_sami/styles', path.join(SANDBOX, 'styles'), {recursive: true});
const ROOT = path.resolve(SANDBOX);

const between = (a, b) => {
	const i = SRC.indexOf(a);
	const j = SRC.indexOf(b, i);
	assert.ok(i >= 0 && j > i, `bloc introuvable : ${a}`);
	return SRC.slice(i, j + b.length);
};
const pick = (re) => {
	const m = re.exec(SRC);
	assert.ok(m, `extrait introuvable : ${re}`);
	return m[0];
};
const writeAtomic = new Function('fs', `return ${pick(/\(file, text\) => \{[\s\S]*?\n\};/).slice(0, -1)}`)(fs);
const safeId = new Function(`return ${pick(/\(s\) => \{\n\tif \(!\/\^\[a-z0-9_-\]\{1,60\}\$\/i[\s\S]*?\n\};/).slice(0, -1)}`)();

const ctx = vm.createContext({fs, path, console, ROOT, safeId, writeAtomic, CLIENTS: path.join(ROOT, 'styles', 'clients'), Date, JSON, Object, Math, Number, String, Set, Array, Error});
const styleApi = vm.runInContext(`${between('// >>> styles-utilisateur', '// <<< styles-utilisateur')}
;({isUserStyle, slugOf, cleanName, readTemplates, templateFromReel, saveUserStyle, renameUserStyle, trashUserStyle, trashClient, MONTAGE, TYPES_FILE})`, ctx);

let ok = 0;
const plain = (x) => (x === undefined ? undefined : JSON.parse(JSON.stringify(x)));
const t = (name, fn) => {
	fn();
	ok++;
	console.log(`ok - ${name}`);
};

// ---------- styles ----------
const reel = JSON.parse(fs.readFileSync('D:/Tools/editeur_sami/projects/video1/reels/v1.json', 'utf8'));
const TEMPLATE_KEYS = ['id', 'name', 'captions', 'zoom', 'banner', 'flash', 'effects', 'emoji', 'progress', 'music', 'sfx'];

t('isUserStyle : fournis refuses, ref-/mon- acceptes, traversee refusee', () => {
	for (const id of ['reel-impact', 'ugc-naturel', 'immobilier', '../x', 'ref-../../a', 'mon-', 'x'.repeat(70), '', null, 'ref-a/b']) assert.equal(styleApi.isUserStyle(id), false, String(id));
	for (const id of ['ref-monmontageryucalls', 'mon-mes-pubs', 'mon-a_b-2']) assert.equal(styleApi.isUserStyle(id), true, id);
});
t('slugOf / cleanName', () => {
	assert.equal(styleApi.slugOf('Mes pubs « Été » RyuCalls !'), 'mes-pubs-ete-ryucalls');
	assert.equal(styleApi.slugOf('../../..'), '');
	assert.equal(styleApi.cleanName('  a\u0000<b>   c  '), 'ab c');
});
t('readTemplates ignore _corbeille et les fichiers illisibles', () => {
	fs.mkdirSync(path.join(styleApi.MONTAGE, '_corbeille'), {recursive: true});
	fs.writeFileSync(path.join(styleApi.MONTAGE, '_corbeille', 'ref-x 2026.json'), '{"id":"ref-x","name":"X"}');
	fs.writeFileSync(path.join(styleApi.MONTAGE, 'casse.json'), '{pas du json');
	const ids = styleApi.readTemplates().map((x) => x.id);
	const files = fs.readdirSync(styleApi.MONTAGE).filter((f) => f.endsWith('.json') && f !== 'casse.json');
	assert.ok(!ids.includes('ref-x') && ids.includes('reel-impact') && ids.length === files.length, ids.join(','));
	fs.rmSync(path.join(styleApi.MONTAGE, 'casse.json'));
});
t('templateFromReel : memes champs que les styles fournis, valeurs du reel', () => {
	const base = JSON.parse(fs.readFileSync(path.join(styleApi.MONTAGE, 'reel-impact.json'), 'utf8'));
	const tpl = styleApi.templateFromReel({...reel, style: {...reel.style, maxWords: 6, color: 'rouge'}, music: {enabled: false, mood: 'electro', volume: 3}}, base, 'mon-test', 'Test');
	for (const k of TEMPLATE_KEYS) assert.ok(k in tpl, k);
	for (const k of Object.keys(base.sfx)) assert.ok(k in tpl.sfx, `sfx.${k}`);
	assert.equal(tpl.style.maxWords, 6);
	assert.equal(tpl.style.color, '#FFFFFF'); // couleur invalide -> defaut
	assert.equal(tpl.music.mood, null); // musique coupee
	assert.equal(tpl.music.volume, 1); // borne
	assert.equal(tpl.graphismes, 'auto'); // repris du style d'origine
	assert.equal(tpl.captions, reel.style.preset);
	assert.match(tpl.description, /^Mon style : sous-titres « .+ » \(6 mots/);
	console.log('   description :', tpl.description);
});
let saved;
t('saveUserStyle : nouveau style mon-<nom>', () => {
	saved = styleApi.saveUserStyle(reel, {name: 'Mes pubs Été'});
	assert.equal(saved.id, 'mon-mes-pubs-ete');
	assert.ok(fs.existsSync(path.join(styleApi.MONTAGE, 'mon-mes-pubs-ete.json')));
	assert.ok(styleApi.readTemplates().some((x) => x.id === 'mon-mes-pubs-ete'));
});
t('saveUserStyle : meme nom -> conflit (on demande), puis remplacer ou suffixer', () => {
	const c = styleApi.saveUserStyle(reel, {name: 'mes pubs été'});
	assert.deepEqual(plain(c.conflict), {id: 'mon-mes-pubs-ete', name: 'Mes pubs Été'});
	const r = styleApi.saveUserStyle({...reel, style: {...reel.style, maxWords: 2}}, {name: 'Mes pubs Été', replace: 'mon-mes-pubs-ete'});
	assert.equal(r.id, 'mon-mes-pubs-ete');
	assert.equal(r.style.maxWords, 2);
	assert.ok(r.modifie && r.cree);
	const s = styleApi.saveUserStyle(reel, {name: 'Mes pubs Été', suffix: true});
	assert.equal(s.id, 'mon-mes-pubs-ete-2');
	assert.equal(s.name, 'Mes pubs Été (2)');
});
t('saveUserStyle : nom d\'un style fourni -> suffixe, jamais ecrase', () => {
	const before = fs.readFileSync(path.join(styleApi.MONTAGE, 'reel-impact.json'), 'utf8');
	const s = styleApi.saveUserStyle(reel, {name: 'Reel Impact'});
	assert.equal(s.name, 'Reel Impact (2)');
	assert.ok(s.id.startsWith('mon-'));
	assert.equal(fs.readFileSync(path.join(styleApi.MONTAGE, 'reel-impact.json'), 'utf8'), before);
	assert.throws(() => styleApi.saveUserStyle(reel, {name: 'x', replace: 'reel-impact'}), /Seuls tes propres styles/);
	assert.throws(() => styleApi.saveUserStyle(reel, {name: 'x', replace: '../../package'}), /Seuls tes propres styles/);
	assert.throws(() => styleApi.saveUserStyle(reel, {name: '   '}), /Donne un nom/);
});
t('saveUserStyle : remplacer un style par reference garde ses mesures', () => {
	const r = styleApi.saveUserStyle(reel, {name: 'Mon montage RyuCalls', replace: 'ref-monmontageryucalls'});
	assert.ok(r.reference && r.reference.duree === 72.6);
});
t('renameUserStyle', () => {
	const r = styleApi.renameUserStyle('mon-mes-pubs-ete-2', 'Pubs rapides');
	assert.equal(r.name, 'Pubs rapides');
	assert.equal(r.id, 'mon-mes-pubs-ete-2');
	assert.throws(() => styleApi.renameUserStyle('mon-mes-pubs-ete', 'pubs RAPIDES'), /déjà ce nom/);
	assert.throws(() => styleApi.renameUserStyle('reel-impact', 'X'), /ne peuvent pas être renommés/);
	assert.throws(() => styleApi.renameUserStyle('mon-inexistant', 'X'), /introuvable/);
});
t('trashUserStyle : corbeille + sujet remis a son style d\'origine', () => {
	const types = JSON.parse(fs.readFileSync(styleApi.TYPES_FILE, 'utf8'));
	types.temoignage.style = 'mon-mes-pubs-ete';
	types.pub.style = 'mon-mes-pubs-ete';
	fs.writeFileSync(styleApi.TYPES_FILE, JSON.stringify(types, null, 1));
	const out = styleApi.trashUserStyle('mon-mes-pubs-ete');
	assert.equal(out.name, 'Mes pubs Été');
	assert.ok(!fs.existsSync(path.join(styleApi.MONTAGE, 'mon-mes-pubs-ete.json')));
	assert.ok(fs.existsSync(path.join(ROOT, out.corbeille)), out.corbeille);
	assert.deepEqual(plain(out.sujets.map((s) => [s.sujet, s.style, s.styleName])), [['Marketing / pub', 'reel-impact', 'Reel Impact'], ['Témoignage', 'ugc-naturel', 'UGC naturel']]);
	const after = JSON.parse(fs.readFileSync(styleApi.TYPES_FILE, 'utf8'));
	assert.equal(after.pub.style, 'reel-impact');
	assert.equal(after.temoignage.style, 'ugc-naturel');
	assert.ok(!styleApi.readTemplates().some((x) => x.id === 'mon-mes-pubs-ete'));
	assert.throws(() => styleApi.trashUserStyle('mon-mes-pubs-ete'), /introuvable/);
	assert.throws(() => styleApi.trashUserStyle('reel-impact'), /ne peuvent pas être supprimés/);
	assert.ok(fs.existsSync(path.join(styleApi.MONTAGE, 'reel-impact.json')));
	// deux suppressions du meme id la meme seconde : deux fichiers distincts dans la corbeille
	styleApi.saveUserStyle(reel, {name: 'Jetable'});
	const a = styleApi.trashUserStyle('mon-jetable');
	styleApi.saveUserStyle(reel, {name: 'Jetable'});
	const b = styleApi.trashUserStyle('mon-jetable');
	assert.notEqual(a.corbeille, b.corbeille);
});
t('trashClient : corbeille, identifiant valide', () => {
	fs.mkdirSync(path.join(ROOT, 'styles', 'clients'), {recursive: true});
	fs.writeFileSync(path.join(ROOT, 'styles', 'clients', 'acme.json'), JSON.stringify({client: 'acme', name: 'ACME'}));
	const out = styleApi.trashClient('acme');
	assert.equal(out.name, 'ACME');
	assert.ok(fs.existsSync(path.join(ROOT, out.corbeille)));
	assert.ok(!fs.existsSync(path.join(ROOT, 'styles', 'clients', 'acme.json')));
	assert.throws(() => styleApi.trashClient('../types'), /Identifiant invalide/);
	assert.throws(() => styleApi.trashClient('acme'), /introuvable/);
});

// ---------- Revision : exports multi-formats ----------
const revCode = [
	between('const FINAL = ', '\nrevision.items.forEach(itemExports);'),
	between("/** Etat de la file pour l'interface : avancement", 'const exportRunning = (i) => itemExports(i).some((e) => [\'queued\', \'running\'].includes(jobs.get(e.job)?.status));'),
].join('\n');
const makeRev = (items, jobs) => {
	const saves = {n: 0};
	const c = vm.createContext({revision: {items, lots: {}}, jobs: new Map(Object.entries(jobs)), saveRevision: () => saves.n++, ENTREE: 'E', autoBusy: false, Date, Set, Object, String});
	const api = vm.runInContext(`${revCode}\n;({itemExports, revisionState, exportRunning, formatFromOut})`, c);
	return {api, c, saves};
};
t('ancien item.export relu (compatibilite) : format deduit, « pris » garde son export', () => {
	const items = [
		{id: 'a', status: 'pris', export: {job: 'j1', out: 'D:/l/T (16x9) - FINAL.mp4', status: 'queued'}, taken: {out: 'D:/l/T (16x9) - FINAL.mp4', date: 1}},
		{id: 'b', status: 'pret', export: {job: 'j2', out: 'D:/l/T - FINAL.mp4', status: 'running'}},
		{id: 'c', status: 'pret', export: null},
	];
	const {api} = makeRev(items, {});
	api.revisionState();
	assert.deepEqual(plain(items[0].exports.map((e) => [e.format, e.status])), [['16:9', 'done']]);
	assert.deepEqual(plain(items[1].exports.map((e) => [e.format, e.status])), [['9:16', 'interrompu']]);
	assert.deepEqual(plain(items[2].exports), undefined);
	assert.ok(!('export' in items[0]) && !('export' in items[2]));
	assert.equal(items[1].status, 'pret'); // interrompu : pas « prise »
});
t('plusieurs formats : progression par format, « prise » quand tout est fini', () => {
	const items = [{id: 'a', status: 'pret', exports: [{format: '9:16', job: 'j1', out: 'o1', status: 'queued'}, {format: '1:1', job: 'j2', out: 'o2', status: 'queued'}]}];
	const jobs = {j1: {status: 'running', progress: 0.4, stage: 'Image'}, j2: {status: 'queued', progress: 0, stage: 'En attente dans la file'}};
	const {api, c, saves} = makeRev(items, jobs);
	let s = api.revisionState();
	assert.equal(s.items[0].exports[0].progress, 0.4);
	assert.equal(items[0].status, 'pret');
	assert.equal(api.exportRunning(items[0]), true);
	c.jobs.get('j1').status = 'done';
	c.jobs.get('j2').status = 'running';
	api.revisionState();
	assert.equal(items[0].status, 'pret');
	c.jobs.get('j2').status = 'failed';
	c.jobs.get('j2').error = 'Erreur de rendu';
	api.revisionState();
	assert.equal(items[0].status, 'pris');
	assert.deepEqual(plain(items[0].taken.outs), ['o1']);
	assert.equal(items[0].exports[1].error, 'Erreur de rendu');
	assert.equal(api.exportRunning(items[0]), false);
	const n = saves.n;
	api.revisionState();
	assert.equal(saves.n, n); // rien de neuf : pas de sauvegarde
	// changement de style -> « pret » ; les exports deja finis ne la remettent pas « prise »
	items[0].status = 'pret';
	api.revisionState();
	assert.equal(items[0].status, 'pret');
	// apres redemarrage (taches disparues) : les exports finis gardent leur etat
	c.jobs.clear();
	api.revisionState();
	assert.deepEqual(plain(items[0].exports.map((e) => e.status)), ['done', 'failed']);
});
t('video en cours de montage : un export qui finit ne la marque pas « prise »', () => {
	const items = [{id: 'a', status: 'travail', exports: [{format: '9:16', job: 'j1', out: 'o1', status: 'running'}]}];
	const {api} = makeRev(items, {j1: {status: 'done', progress: 1}});
	api.revisionState();
	assert.equal(items[0].status, 'travail');
});

console.log(`\n${ok} tests reussis ; bac a sable conserve : ${SANDBOX}`);
