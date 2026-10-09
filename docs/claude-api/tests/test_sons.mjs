// Sons de coupe varies (ronde « sons ») : sfxEvents de remotion/src/timeline.ts, sans navigateur ni rendu (rien n'est ecrit).
//   node docs/claude-api/tests/test_sons.mjs
// Donnees : copies FIGEES de Video 1 / Video 2 (docs/direction-creative-v2/tests/fixtures), jamais les projets de l'utilisateur.
// Comparaison « comme avant » : la copie du code juste avant ce travail (docs/claude-api/avant/remotion-src/timeline.ts).
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {isDeepStrictEqual} from 'node:util';

const ICI = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(ICI, '../../..');
const T = await import(pathToFileURL(path.join(ROOT, 'remotion/src/timeline.ts')).href);
const A = await import(pathToFileURL(path.join(ROOT, 'docs/claude-api/avant/remotion-src/timeline.ts')).href);
let ok = 0;
let ko = 0;
const verifier = (nom, cond, detail = '') => {
	cond ? ok++ : ko++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${nom}${detail && !cond ? ` — ${detail}` : ''}`);
};
const lire = (f) => JSON.parse(fs.readFileSync(path.join(ROOT, f), 'utf8'));
const clone = (r) => JSON.parse(JSON.stringify(r));
const FIX = 'docs/direction-creative-v2/tests/fixtures/projects';
const base1 = lire(`${FIX}/script1/reels/script.json`);
const base2 = lire(`${FIX}/script2/reels/script.json`);
const video1 = lire(`${FIX}/video1/reels/script.json`);
const CAT = lire('styles/sons-transitions.json');
const ROLES = ['transition', 'interface', 'apparition', 'mot-fort', 'impact', 'cta'];
/** Meme reserve que sfxgen.reserve() et reserveFamille() de l'interface. */
const reserve = (id) => ROLES.flatMap((role) => (CAT.familles.find((f) => f.id === id).sons[role] ?? []).map((s) => ({name: s.name, pic: s.pic, gain: s.gain, role})));
const picDe = (pool, name) => pool.find((p) => p.name === name)?.pic;
const fichier = (name) => fs.existsSync(path.join(ROOT, 'assets', T.sfxFile(name)));

/** Reel d'essai : les 5 plans de Vidéo 2 trois fois (15 parties -> 14 coupes), style Reel Impact (whoosh-court, pop, riser). */
const dixCoupes = (() => {
	const r = clone(base2);
	r.clips = [0, 1, 2].flatMap((k) => base2.clips.map((c) => ({...clone(c), id: k ? `${c.id}-${k}` : c.id, block: `${c.block}-${k}`})));
	r.ctaBlock = `${base2.ctaBlock}-2`;
	r.template = 'reel-impact';
	r.sfx = {enabled: true, transition: 'whoosh-court', highlight: 'pop', highlightGap: 3.5, cta: 'riser', start: null, volume: 0.6,
		extra: [{t: 4, name: 'ding'}]};
	return r;
})();
/** Studio Tech 3D (meme construction que docs/qualite-2026-09-30/tests/test-ronde3.mjs). */
const studio = (() => {
	const r = clone(base1);
	r.template = 'produit-3d';
	r.design = {mode: 'produit', enabled: true, accent: '#6FE7FF', secondary: '#8B5CF6', density: 5, cinematic: true, suppressExtras: true};
	r.zoom = {auto: true, strength: 1.06, push: 0.012, overrides: {}};
	r.sfx = {enabled: true, transition: 'whoosh-court', highlight: 'pop-grave', highlightGap: 8, cta: 'riser', start: 'impact', volume: 0.18, extra: []};
	r.cutouts = Object.fromEntries(r.clips.map((c) => [c.id, {file: 'x', start: c.in, end: c.out, width: 1080, height: 1920, source: c.source,
		proxy: r.sources[c.source].proxy, frames: 'x', fps: 30, count: 1}]));
	// + la liste enumeree de test-ronde3 (un clic par element suivant)
	r.styleScenes = [...(r.styleScenes ?? []), {id: 'style-c2-15-liste', kind: 'list', clip: 'c2', index: 15, length: 1, text: 'Salaire',
		secondary: 'Avantages sociaux|Vacances|Journées de maladie', items: [15, 19, 22, 25], duration: 4.5, x: 0.5, y: 0.2, scale: 1, rotation: 0,
		color: '#FF7A66', creativeRole: 'probleme'}];
	return r;
})();
/** Aucun son deux fois de suite ; aucun des 3 derniers si la reserve en a au moins 4. */
const suite = (noms, taille) => noms.every((n, i) => !noms.slice(Math.max(0, i - (taille >= 4 ? 3 : 1)), i).includes(n));

// ---------- 1. ancien reel (ni « varier » ni « pool ») : variation par defaut ----------
{
	const r = clone(dixCoupes);
	const ev = T.sfxEvents(r);
	const coupes = T.blockStarts(r).map((b) => b.t);
	const tr = ev.filter((e) => e.kind === 'transition');
	const noms = tr.map((e) => e.name);
	const defaut = T.SFX_POOL_DEFAUT['transition:whoosh-court'];
	verifier('ancien reel : calcule sans erreur, temps et volumes finis, aucun temps negatif', ev.length > 10
		&& ev.every((e) => Number.isFinite(e.t) && e.t >= 0 && Number.isFinite(e.volume) && e.volume > 0));
	verifier('ancien reel : chaque son joue existe dans assets/', ev.every((e) => fichier(e.name)), ev.filter((e) => !fichier(e.name)).map((e) => e.name).join(', '));
	verifier(`${tr.length} coupes : au moins 10`, tr.length >= 10 && tr.length === coupes.length);
	verifier('10 premieres coupes : au moins 4 sons differents', new Set(noms.slice(0, 10)).size >= 4, noms.slice(0, 10).join(' '));
	verifier('jamais deux fois de suite le meme son, ni un des 3 derniers (reserve de 6)', suite(noms, defaut.length), noms.join(' '));
	const pool = defaut.map(([name, pic, gain]) => ({name, pic, gain}));
	verifier('le maximum de chaque son tombe SUR la coupe (t + pic = coupe)', tr.every((e, i) => Math.abs(e.t + picDe(pool, e.name) - coupes[i]) < 1e-9),
		tr.map((e, i) => (e.t + picDe(pool, e.name) - coupes[i]).toFixed(3)).join(' '));
	verifier('le son du style fait partie de la reserve (le caractere du style reste)', defaut.some(([n]) => n === 'whoosh-court'));
	const again = T.sfxEvents(clone(r));
	verifier('meme tirage a chaque calcul (apercu = export)', isDeepStrictEqual(ev, again) && isDeepStrictEqual(ev, T.sfxEvents(JSON.parse(JSON.stringify(r)))));
	const off = T.sfxEvents({...r, sfx: {...r.sfx, varier: false}});
	const parType = (l) => Object.fromEntries([...new Set(l.map((e) => e.kind))].map((k) => [k, l.filter((e) => e.kind === k).length]));
	verifier('memes moments de son qu\'avant (meme nombre par type) : seuls le son, son depart et son volume changent', isDeepStrictEqual(parType(ev), parType(off)));
	verifier('bruitages poses a la main et son du debut jamais changes', isDeepStrictEqual(ev.filter((e) => e.kind === 'ajoute' || e.kind === 'debut'),
		off.filter((e) => e.kind === 'ajoute' || e.kind === 'debut')));
	const cta = ev.find((e) => e.kind === "appel a l'action");
	const ctaAvant = off.find((e) => e.kind === "appel a l'action");
	const pc = T.SFX_POOL_DEFAUT['cta:riser'].find(([n]) => n === cta.name);
	verifier('montee avant l\'appel a l\'action : maximum au meme instant que le riser d\'origine', Math.abs(cta.t + pc[1] - (ctaAvant.t + 1.54)) < 1e-9,
		`${cta.name} ${cta.t.toFixed(3)}`);
}

// ---------- 2. varier: false = exactement comme avant ----------
{
	const reels = {dixCoupes, base1, base2, video1, studio, studioAncien: {...studio, sfx: {...studio.sfx, transition: null}}};
	for (const f of fs.readdirSync(path.join(ROOT, 'docs/galerie-styles/tests')).filter((x) => x.endsWith('-apercu.json'))) {
		const r = lire(`docs/galerie-styles/tests/${f}`);
		reels[f] = {...r, sfx: {...(r.sfx ?? {}), enabled: true, transition: r.sfx?.transition ?? 'whoosh-court', highlight: 'pop', cta: 'riser', volume: 0.5}};
	}
	const diff = Object.entries(reels).filter(([, r]) => !isDeepStrictEqual(T.sfxEvents({...r, sfx: r.sfx && {...r.sfx, varier: false}}), A.sfxEvents(r)));
	verifier(`varier: false : sfxEvents identique au code d'avant (${Object.keys(reels).length} reels, studio compris)`, !diff.length, diff.map(([k]) => k).join(', '));
	const pool = reserve('retro');
	const r = {...dixCoupes, sfx: {...dixCoupes.sfx, varier: false, famille: 'retro', pool}};
	verifier('varier: false avec une famille choisie : la famille est ignoree, sons du style', isDeepStrictEqual(T.sfxEvents(r), A.sfxEvents(dixCoupes)));
	verifier('bruitages coupes : rien, comme avant', T.sfxEvents({...dixCoupes, sfx: {...dixCoupes.sfx, enabled: false, pool}}).length === 0);
	const sobre = {...dixCoupes, sfx: {...dixCoupes.sfx, transition: null, pool: reserve('punchy')}};
	verifier('style sobre (aucun son de coupe) : la famille n\'ajoute aucun son aux coupes', !T.sfxEvents(sobre).some((e) => e.kind === 'transition'));
}

// ---------- 3. famille choisie (sfx.pool) ----------
for (const fam of CAT.familles) {
	const pool = reserve(fam.id);
	const r = {...dixCoupes, sfx: {...dixCoupes.sfx, famille: fam.id, pool}};
	const ev = T.sfxEvents(r);
	const tr = ev.filter((e) => e.kind === 'transition');
	const permis = new Set(fam.sons.transition.map((s) => s.name));
	const noms = tr.map((e) => e.name);
	const coupes = T.blockStarts(r).map((b) => b.t);
	const g = (e) => fam.sons.transition.find((s) => s.name === e.name).gain;
	verifier(`famille « ${fam.nom} » : coupes tirees de ses sons, >= 4 differents sur 10, jamais deux fois de suite, pic sur la coupe, gain applique`,
		tr.length >= 10 && tr.every((e) => permis.has(e.name)) && new Set(noms.slice(0, 10)).size >= Math.min(4, permis.size)
		&& suite(noms, permis.size) && tr.every((e, i) => e.t === 0 || Math.abs(e.t + picDe(pool, e.name) - coupes[i]) < 1e-9)
		&& tr.every((e) => Math.abs(e.volume - 0.6 * g(e) * (T.SFX_GAIN[e.name] ?? 1)) < 1e-9), noms.join(' '));
	const mot = ev.filter((e) => e.kind === 'mot cle');
	verifier(`famille « ${fam.nom} » : mots forts tires de ses sons « mot-fort »`, mot.length > 0 && mot.every((e) => fam.sons['mot-fort'].some((s) => s.name === e.name)));
}

// ---------- 4. studio Tech 3D : chaque interface entre avec un son different ----------
{
	const ev = T.sfxEvents(studio);
	const off = T.sfxEvents({...studio, sfx: {...studio.sfx, varier: false}});
	const ui = ev.filter((e) => e.kind === 'interface');
	verifier(`studio : ${ui.length} entrees d'interface, plus le meme whoosh partout`, ui.length >= 3 && new Set(ui.map((e) => e.name)).size >= Math.min(3, ui.length)
		&& off.filter((e) => e.kind === 'interface').every((e) => e.name === 'whoosh-court'), ui.map((e) => e.name).join(' '));
	verifier('studio : jamais deux fois de suite le meme son d\'entree', suite(ui.map((e) => e.name), T.SFX_POOL_DEFAUT['interface:whoosh-court'].length));
	const pool = T.SFX_POOL_DEFAUT['interface:whoosh-court'].map(([name, pic]) => ({name, pic}));
	const scenes = T.designScenes(studio).filter((g) => g.kind !== 'keyword');
	verifier('studio : le maximum du son tombe juste apres le debut de l\'entree (+0,06 s, comme avant)',
		ui.length === scenes.length && ui.every((e) => e.t === 0 || scenes.some((g) => Math.abs(e.t + picDe(pool, e.name) - (g.at + 0.06)) < 1e-9)));
	const liste = ev.filter((e) => e.kind === 'liste');
	verifier('studio : les elements d\'une meme liste gardent le meme petit son', liste.length >= 2 && new Set(liste.map((e) => e.name)).size === 1,
		liste.map((e) => e.name).join(' '));
	const marques = scenes.filter((g) => g.kind === 'list').flatMap((g) => (g.marks ?? []).slice(1));
	verifier('studio : chaque petit clic de liste part SUR le mot de son element (comme avant)', liste.length === marques.length
		&& liste.every((e) => marques.some((m) => Math.abs(m - e.t) < 1e-9)));
	verifier('studio : pas de son de coupe (regle du studio gardee)', !ev.some((e) => e.kind === 'transition'));
	const tech = {...studio, sfx: {...studio.sfx, famille: 'tech', pool: reserve('tech')}};
	const ui2 = T.sfxEvents(tech).filter((e) => e.kind === 'interface');
	const permis = new Set(CAT.familles.find((f) => f.id === 'tech').sons.interface.map((s) => s.name));
	verifier('studio + famille Tech : entrees tirees des sons « interface » de la famille', ui2.length === ui.length && ui2.every((e) => permis.has(e.name)));
}

// ---------- 5. reserve abimee ou minuscule : jamais d'erreur ----------
{
	const junk = [null, 3, 'x', {name: ''}, {name: 'souffle-doux', pic: 'abc', gain: 99, role: 'transition'}, {name: 'souffle-leger', pic: -4, gain: -1, role: 'zzz'},
		{name: 'whoosh-tonal', pic: NaN}];
	let ev = null;
	try {
		ev = T.sfxEvents({...dixCoupes, sfx: {...dixCoupes.sfx, pool: junk}});
	} catch (e) {
		ev = String(e);
	}
	verifier('reserve abimee : aucune erreur, gains bornes a 4, pic borne a 0-3 s', Array.isArray(ev) && ev.filter((e) => e.kind === 'transition')
		.every((e) => ['souffle-doux', 'souffle-leger', 'whoosh-tonal'].includes(e.name) && e.volume <= 0.6 * 4 + 1e-9 && e.t >= 0), String(ev).slice(0, 200));
	const un = T.sfxEvents({...dixCoupes, sfx: {...dixCoupes.sfx, pool: [{name: 'souffle-doux', pic: 0.198, gain: 1, role: 'transition'}]}});
	verifier('reserve d\'un seul son : ce son a chaque coupe', un.filter((e) => e.kind === 'transition').every((e) => e.name === 'souffle-doux'));
	const deux = T.sfxEvents({...dixCoupes, sfx: {...dixCoupes.sfx, pool: [{name: 'souffle-doux', pic: 0.198}, {name: 'souffle-leger', pic: 0.122}]}})
		.filter((e) => e.kind === 'transition').map((e) => e.name);
	verifier('reserve de deux sons : ils alternent (jamais deux fois de suite)', suite(deux, 2) && new Set(deux).size === 2, deux.join(' '));
	verifier('reserve trop longue : 32 sons lus au plus', (() => {
		const long = Array.from({length: 40}, (_, i) => ({name: i < 32 ? 'souffle-doux' : 'whoosh-tonal', pic: 0.1}));
		return !T.sfxEvents({...dixCoupes, sfx: {...dixCoupes.sfx, pool: long}}).some((e) => e.name === 'whoosh-tonal');
	})());
	const vide = T.sfxEvents({...dixCoupes, sfx: {...dixCoupes.sfx, transition: 'sfx/kenney/impact-sounds/impactSoft_medium_000.ogg', pool: []}});
	verifier('son du style sans reserve connue (son de la banque) : garde tel quel', vide.filter((e) => e.kind === 'transition')
		.every((e) => e.name === 'sfx/kenney/impact-sounds/impactSoft_medium_000.ogg'));
}

// ---------- 6. reserves par defaut ----------
{
	const noms = Object.values(T.SFX_POOL_DEFAUT).flat().map(([n]) => n);
	verifier('reserves par defaut : chaque son existe dans assets/sfx/editeur', noms.every(fichier), noms.filter((n) => !fichier(n)).join(', '));
	const familles = new Map(CAT.familles.flatMap((f) => Object.values(f.sons).flat()).map((s) => [s.name, s.pic]));
	verifier('reserves par defaut : meme pic que styles/sons-transitions.json', Object.values(T.SFX_POOL_DEFAUT).flat()
		.every(([n, p]) => !familles.has(n) || Math.abs(familles.get(n) - p) < 1e-9));
}

console.log(`\n${ok}/${ok + ko} vérifications réussies`);
process.exit(ko ? 1 : 0);
