// Copie isolee de l'editeur pour tester l'interface Claude (groupe « interface ») : port 18796, AUCUNE donnee vivante de
// l'utilisateur, AUCUN appel reel a Claude (moteur factice : faux-moteur/). Montages = copies des fixtures figees
// (docs/direction-creative-v2/tests/fixtures). Jonctions en LECTURE : assets, runtime/venv (interpreteur seulement : le
// paquet « editeur » lu est le faux moteur de la copie), projects/_cache/{optimises,ambiances,transcripts,voix}.
// Usage : node setup-bac.mjs [--code]   (--code : recopie seulement le code du serveur, de l'interface et du faux moteur)
// Puis, depuis la racine (apres node app/build.mjs) : node docs/claude-api/tests/interface/test-http.mjs (110), test-ui.mjs (17),
// test-mcp.mjs (16), test-contrat-moteur.mjs (11 : VRAIS modules du moteur, Claude eteint, aucune cle ; port 18795),
// capture.mjs [revision avis critique reglages avance credit editeur] (images dans runtime/cache/tmp/claude-interface-1002/captures).
// Refaire setup-bac.mjs avant chaque test (les tests changent les donnees de la copie). La copie contient des JONCTIONS :
// ne jamais l'effacer recursivement sans retirer d'abord les liens (rmdir).
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../../..');
const WORK = path.join(path.resolve(HERE, '../../../..'), 'runtime', 'cache', 'tmp', 'claude-interface-1002'); // bac (jonctions), journaux, captures
const box = path.join(WORK, 'bac');
const P = (...p) => path.join(box, ...p);
const mk = (...p) => fs.mkdirSync(P(...p), {recursive: true});
const put = (rel, text = 'x') => {
	mk(path.dirname(rel));
	fs.writeFileSync(P(rel), text);
};
const junction = (rel, target) => {
	if (fs.existsSync(P(rel))) return;
	mk(path.dirname(rel));
	fs.symlinkSync(target, P(rel), 'junction');
};
// code a tester (copie fraiche a chaque fois) ; app/dist = l'interface compilee par node app/build.mjs
for (const p of ['app/server.mjs', 'app/ui', 'app/dist']) {
	fs.rmSync(P(p), {recursive: true, force: true});
	mk(path.dirname(p));
	fs.cpSync(path.join(REAL, p), P(p), {recursive: true});
}
fs.rmSync(P('engine/editeur'), {recursive: true, force: true});
mk('engine/editeur');
for (const f of fs.readdirSync(path.join(HERE, 'faux-moteur'))) fs.copyFileSync(path.join(HERE, 'faux-moteur', f), P('engine/editeur', f));
mk('remotion');
fs.copyFileSync(path.join(HERE, 'faux-rendu.mjs'), P('remotion/render.mjs'));
if (process.argv.includes('--code')) {
	console.log('CODE RECOPIE');
	process.exit(0);
}
for (const j of ['assets', 'runtime/venv']) junction(j, path.join(REAL, j));
for (const j of ['optimises', 'ambiances', 'transcripts', 'voix']) junction(`projects/_cache/${j}`, path.join(REAL, 'projects/_cache', j));
mk('projects/_cache/vignettes');
mk('runtime/cache/tmp');
// donnees de la copie (remises a zero)
for (const d of ['media/entree', 'livraisons', 'corbeille', 'styles']) fs.rmSync(P(d), {recursive: true, force: true});
fs.cpSync(path.join(REAL, 'styles'), P('styles'), {recursive: true});
fs.rmSync(P('styles/sons-transitions.json'), {force: true}); // catalogue du groupe « sons » : absent au depart (test 404)
fs.writeFileSync(P('styles/claude.json'), JSON.stringify({actif: true, modele: 'claude-sonnet-5-5', modeles_taches: {cerveau: null, critique: null, consigne: null},
	effort_cerveau: 'medium', effort_critique: 'medium', effort_consigne: 'low', plafond_video: 0.25, plafond_jour: 0.75, plafond_mois: 2.0,
	credit_depart: 2.0, credit_date: new Date().toLocaleDateString('sv-SE'), critique_auto: false, images_critique: 16, largeur_images: 540, espace_travail: null}, null, 1));
for (const d of fs.readdirSync(P('projects'))) if (!d.startsWith('_')) fs.rmSync(P('projects', d), {recursive: true, force: true});
for (const f of ['projects/_revision.json', 'projects/_claude.json', 'runtime/cache/claude-appels.jsonl', 'runtime/cache/appels-moteur.log']) fs.rmSync(P(f), {force: true});
for (const f of fs.readdirSync(P('runtime/cache'))) if (f.startsWith('faux-')) fs.rmSync(P('runtime/cache', f), {force: true});
fs.rmSync(P('runtime/cache/jobs-vus'), {recursive: true, force: true});
fs.rmSync(P('runtime/cache/controle'), {recursive: true, force: true});

const FIX = path.join(REAL, 'docs/direction-creative-v2/tests/fixtures/projects');
const lire = (rel) => JSON.parse(fs.readFileSync(path.join(FIX, rel), 'utf8'));
const now = Date.now();
const projet = (name, src, extra = {}, couper = 0) => {
	const r = lire(src);
	if (couper) {
		const c = r.clips[0];
		c.out = +(c.in + couper).toFixed(2);
		c.words = (c.words ?? []).filter((w) => w.end <= c.out);
		r.clips = [c];
		r.broll = [];
		r.graphics = [];
		r.vectors = [];
	}
	Object.assign(r, {project: name, id: 'script', variant: null, delivery: P('livraisons', extra.lot ?? 'Lot test'), ...extra.reel});
	const cache = path.join(REAL, 'projects', '_cache') + path.sep;
	for (const s of Object.values(r.sources)) if (typeof s.path === 'string' && s.path.startsWith(cache)) s.path = P('projects', '_cache', s.path.slice(cache.length));
	delete r.controle;
	mk('projects', name, 'reels');
	mk('projects', name, 'versions', 'script');
	fs.writeFileSync(P('projects', name, 'project.json'), JSON.stringify({name, label: r.title, timeline: [], variants: [], sources: r.sources, script: {blocks: []}}));
	fs.writeFileSync(P('projects', name, 'reels', 'script.json'), JSON.stringify(r, null, 1));
	return r;
};
const jour = new Date().toLocaleDateString('sv-SE');
const iso = (h) => `${jour}T${h}`;
projet('leads', 'video1/reels/script.json', {lot: 'Lot test', reel: {title: 'Répondez vite à vos leads', template: 'pub-premium',
	// avis de Claude deja range par la critique (forme acceptee par l'interface : reel.claude.critique)
	claude: {critique: {date: `${jour} 09:12`, cout: 0.052, modele: 'claude-sonnet-5-5', note: 7.5, verdict: 'Bonne pub, mais le bouton final arrive trop tard.',
		problemes: [{t: 3.2, texte: 'Le texte de la carte cache le visage', suggestion: 'remonter la carte'}, {t: 41.5, fin: 44, texte: 'Le bouton « En savoir plus » apparaît trop tard', suggestion: 'le montrer dès « appelez »'}]}},
	consignes: [{date: iso('09:30:00'), texte: 'enlève le bandeau du début', t: 1.2, moteur: 'claude', cout: 0.004, changements: [{quoi: 'Bandeau retiré'}], refus: [], question: null}]}});
projet('erreurs', 'script2/reels/script.json', {lot: 'Lot test', reel: {title: '3 erreurs qui coûtent des clients', template: 'editorial-cinetique'}});
projet('rappel', 'script1/reels/script.json', {lot: 'Lot test', reel: {title: 'Pourquoi on rappelle en 60 secondes', template: 'hormozi'}}, 2);
const unites = {leads: 'media/entree/Lot test/leads.mp4', erreurs: 'media/entree/Lot test/erreurs.mp4', rappel: 'media/entree/Lot test/rappel.mp4'};
for (const [k, u] of Object.entries(unites)) put(u, `fausse video ${k}`);
put('livraisons/Lot test/Pourquoi on rappelle en 60 secondes - FINAL.mp4', 'faux export 9:16');
const outRappel = P('livraisons/Lot test/Pourquoi on rappelle en 60 secondes - FINAL.mp4');
const id = (n) => (n + '000000000000').slice(0, 12);
const resume = (note, verdict, compte) => ({note, verdict, compte, date: `${jour} 09:41`, stamp: now});
const it = (key, extra) => ({id: extra.id, unit: unites[key], lot: 'Lot test', name: path.posix.basename(unites[key]), status: 'pret', stage: 'Prête',
	progress: 1, created: now - 3600e3, updated: now, rid: 'script', exports: [], taken: null, project: key, ...extra});
const items = [
	it('leads', {id: id('c1'), title: 'Répondez vite à vos leads', type: 'pub', typeLabel: 'Marketing / pub', style: 'pub-premium', ia: true,
		controle: resume(8.6, 'Prête à publier. Deux petits ajustements possibles.', {bloquant: 0, important: 1, conseil: 1})}),
	it('erreurs', {id: id('c2'), title: '3 erreurs qui coûtent des clients', type: 'conseil', typeLabel: 'Conseils / éducation', style: 'editorial-cinetique', ia: true,
		controle: resume(6.4, 'Correcte : un passage lent au milieu.', {bloquant: 0, important: 1, conseil: 0})}),
	it('rappel', {id: id('c3'), title: 'Pourquoi on rappelle en 60 secondes', type: 'pub', typeLabel: 'Marketing / pub', style: 'hormozi', status: 'pris',
		exports: [{format: '9:16', job: '33333333-3333-4333-8333-333333333333', out: outRappel, status: 'done', progress: 1, seconds: 12}],
		taken: {out: outRappel, outs: [outRappel], formats: ['9:16'], date: now - 600e3, batch: '33333333-3333-4333-8333-333333333333'}}),
];
fs.writeFileSync(P('projects/_revision.json'), JSON.stringify({items, lots: {'Lot test': {created: now, client: null, uploading: false, complete: true}}}, null, 1));
// registre des depenses Claude (forme de engine/editeur/claude_api.py) : « leads » a deja servi (cerveau + critique + 2 consignes)
const appel = (h, tache, cout, ok = true, erreur = null) => ({date: iso(h), tache, modele: 'claude-sonnet-5-5', jetons: {entree: 3000, sortie: 900}, cout, request_id: 'req_test', ok, erreur});
const appelsLeads = [appel('09:05:00', 'cerveau', 0.031), appel('09:12:00', 'critique', 0.052), appel('09:30:00', 'consigne', 0.004), appel('09:31:00', 'consigne', 0.005)];
const total = appelsLeads.reduce((a, x) => a + x.cout, 0);
fs.writeFileSync(P('projects/_claude.json'), JSON.stringify({version: 1, jours: {[jour]: {cout: total, appels: 5}}, mois: {[jour.slice(0, 7)]: {cout: total, appels: 5}},
	videos: {'leads/script': {cout: total, nb: 4, dernier: iso('09:31:00'), appels: appelsLeads}}, dernier: null, credit_epuise: null, espace_manquant: null, journal_octets: 0}, null, 1));
// journal : une ligne par appel ; la derniere a une fausse cle dans son erreur (le serveur doit la masquer)
const lignes = [...appelsLeads.map((a) => ({...a, video: 'leads/script', secondes: 8.2})),
	{date: iso('09:40:00'), tache: 'test', video: null, modele: 'claude-haiku-4-5', cout: 0, ok: false, erreur: 'refus 401 cle sk-ant-api03-FAUSSECLEJOURNAL0123456789abcdef', secondes: 1.1}];
mk('runtime/cache');
fs.writeFileSync(P('runtime/cache/claude-appels.jsonl'), lignes.map((l) => JSON.stringify(l)).join('\n') + '\n');
console.log('COPIE=' + box);
