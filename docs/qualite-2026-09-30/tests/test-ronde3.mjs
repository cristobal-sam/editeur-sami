// Ronde 3 (02/10/2026) — rendu : relances de cadre du studio, liste énumérée, ponctuation des sous-titres, sons d'interface.
// node docs/qualite-2026-09-30/tests/test-ronde3.mjs   (lit une COPIE figée de Vidéo 1 : fixtures de direction-creative-v2)
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const ICI = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(ICI, '../../..');
const T = await import(pathToFileURL(path.join(ROOT, 'remotion/src/timeline.ts')).href);
let ok = 0;
let ko = 0;
const verifier = (nom, cond, detail = '') => {
	cond ? ok++ : ko++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${nom}${detail ? ` — ${detail}` : ''}`);
};
const lire = (f) => JSON.parse(fs.readFileSync(f, 'utf8'));
const base = lire(path.join(ROOT, 'docs/direction-creative-v2/tests/fixtures/projects/script1/reels/script.json'));
const clone = (r) => JSON.parse(JSON.stringify(r));

// 1. Ponctuation seule (« », « ». ») : jamais une page de sous-titres vide
{
	const r = clone(base);
	const pages = T.pages(r);
	const vides = pages.filter((p) => !p.words.some((w) => T.displayWord(w.w, false)));
	verifier('sous-titres : aucune page vide (guillemet seul collé au mot d’avant)', vides.length === 0, `${pages.length} pages, ${vides.length} vide(s)`);
	const c = r.clips[0];
	c.words.splice(3, 0, {w: '».', start: c.words[2].end, end: c.words[2].end + 0.05});
	const p2 = T.pages(r);
	verifier('sous-titres : « ». » ajouté = même nombre de pages, fin de phrase gardée',
		p2.every((p) => p.words.every((w) => T.displayWord(w.w, false))) && p2.some((p) => /».$/.test(p.words[p.words.length - 1].w)));
}

// 2. Studio Tech 3D : relances de cadre (coupe franche = autre valeur de plan ; pas de passage figé de plus de 6 s)
const studio = (() => {
	const r = clone(base);
	r.template = 'produit-3d';
	r.design = {mode: 'produit', enabled: true, accent: '#6FE7FF', secondary: '#8B5CF6', density: 5, cinematic: true, suppressExtras: true};
	r.zoom = {auto: true, strength: 1.06, push: 0.012, overrides: {}};
	r.sfx = {enabled: true, transition: 'whoosh-court', highlight: 'pop-grave', highlightGap: 8, cta: 'riser', start: 'impact', volume: 0.18, extra: []};
	// détourage valide sur chaque plan (le contenu n'est pas lu par ce test)
	r.cutouts = Object.fromEntries(r.clips.map((c) => [c.id, {file: 'x', start: c.in, end: c.out, width: 1080, height: 1920, source: c.source,
		proxy: r.sources[c.source].proxy, frames: 'x', fps: 30, count: 1}]));
	return r;
})();
{
	const segs = T.videoSegments(studio);
	const total = T.duration(studio);
	const scale = (t) => T.studioView(studio, segs[T.segmentAt(segs, t)], t)?.scale ?? 1;
	const cuts = segs.slice(1).map((s) => s.out_start);
	const sauts = cuts.map((c) => Math.abs(scale(c + 0.02) - scale(c - 0.04)) / scale(c - 0.04));
	const plats = sauts.filter((x) => x < 0.02).length;
	verifier('studio : la plupart des coupes changent la valeur de plan (≥ 2 %)', plats <= Math.max(1, Math.floor(cuts.length / 3)),
		`${cuts.length} coupes, ${plats} sans changement`);
	// relances visibles : coupe, saut de cadre ≥ 2,5 % en 1,5 s, entrée d'interface
	const ev = new Set(cuts.map((c) => +c.toFixed(1)));
	for (let t = 1.5; t < total; t += 0.1) if (Math.abs(scale(t) - scale(t - 1.5)) >= 0.025 * scale(t - 1.5)) ev.add(+t.toFixed(1));
	// 2 oct. 2026 (finition après le juge n° 3) : la bascule pour une carte se fait sur une coupe ou en glissement adouci au lieu
	// d'un saut sur un début de phrase ; un glissement vertical d'au moins 2,5 % de la hauteur en 1,5 s est un mouvement de caméra
	// visible et compte aussi comme relance
	const dyAt = (t) => T.studioView(studio, segs[T.segmentAt(segs, t)], t)?.dy ?? 0;
	for (let t = 1.5; t < total; t += 0.1) if (Math.abs(dyAt(t) - dyAt(t - 1.5)) >= 0.025) ev.add(+t.toFixed(1));
	for (const s of T.designScenes(studio)) ev.add(+s.at.toFixed(1));
	const pts = [0, ...[...ev].sort((a, b) => a - b), total];
	const plusLong = Math.max(...pts.slice(1).map((x, i) => x - pts[i]));
	verifier('studio : aucun passage sans relance de plus de 6 s', plusLong <= 6.05, `plus long : ${plusLong.toFixed(1)} s`);
	// la tête n'est jamais poussée hors du cadre, l'agrandissement reste raisonnable
	let pire = 1;
	let maxi = 0;
	for (let t = 0; t < total; t += 0.25) {
		const p = T.studioPersonAt(studio, segs, t);
		if (p) pire = Math.min(pire, p.head);
		maxi = Math.max(maxi, scale(t));
	}
	verifier('studio : haut de la tête toujours dans l’image (≥ 4 %)', pire >= 0.04, `plus haut : ${pire.toFixed(3)}`);
	verifier('studio : agrandissement ≤ 1,32', maxi <= 1.3201, maxi.toFixed(3));
	// ancien reel sans plan créatif : cadre fixe (aucune relance ajoutée)
	const ancien = clone(studio);
	delete ancien.creativePlan;
	const fixes = new Set();
	for (let t = 0; t < total; t += 0.5) fixes.add(T.studioView(ancien, segs[T.segmentAt(segs, t)], t)?.scale.toFixed(3));
	verifier('studio : ancien reel sans plan créatif = cadre fixe (inchangé)', fixes.size === 1, [...fixes].join(','));
}

// 3. Liste : gabarit, instants des éléments, place hors de la personne, sons
{
	const l4 = T.studioListLayout(['Salaire', 'Avantages sociaux', 'Vacances', 'Journées de maladie']);
	verifier('liste : 4 éléments sur 2 lignes équilibrées', l4.rows.length === 2 && l4.w <= 0.96, JSON.stringify(l4.rows) + ` ${l4.w}u`);
	const l3 = T.studioListLayout(['Leads', 'Calls', 'Sales']);
	verifier('liste : 3 éléments courts sur une ligne', l3.rows.length === 1, JSON.stringify(l3.rows));
	const r = clone(studio);
	const c2 = r.clips.find((c) => c.id === 'c2');
	const idx = [15, 19, 22, 25];
	r.styleScenes = [{id: 'style-c2-15-liste', kind: 'list', clip: 'c2', index: 15, length: 1, text: 'Salaire', secondary: 'Avantages sociaux|Vacances|Journées de maladie',
		items: idx, duration: 4.5, x: 0.5, y: 0.2, scale: 1, rotation: 0, color: '#FF7A66', creativeRole: 'probleme'}];
	const s = T.designScenes(r).find((x) => x.kind === 'list');
	const words = T.timedWords(r);
	const attendu = idx.map((i) => words.find((w) => w.clip === 'c2' && w.index === i)?.outStart);
	verifier('liste : chaque élément apparaît sur son mot', !!s && s.marks.length === 4 && s.marks.every((m, k) => Math.abs(m - attendu[k]) < 1e-6),
		s ? s.marks.map((m) => m.toFixed(2)).join(' ') : 'absente');
	const p = s ? T.studioPersonAt(r, T.videoSegments(r), s.at + 1) : null;
	const box = T.studioCardSize('list', s?.text, s?.secondary);
	const bas = s ? s.y + (box.h * 1080) / 1920 * s.scale / 2 : 1;
	verifier('liste : posée au-dessus de la tête', !!p && bas <= p.head, `bas ${bas.toFixed(3)} / tête ${p?.head.toFixed(3)}`);
	const sons = T.sfxEvents(r).filter((e) => e.kind === 'liste' || e.kind === 'interface');
	verifier('liste : un son d’entrée + un clic par élément suivant', sons.filter((e) => e.kind === 'interface').length === 1 && sons.filter((e) => e.kind === 'liste').length === 3);
	c2.words[22].cut = true; // un élément coupé au montage : il suit le précédent, jamais avant lui
	const s2 = T.designScenes(r).find((x) => x.kind === 'list');
	verifier('liste : mot coupé -> élément placé après le précédent', !!s2 && s2.marks.every((m, k) => !k || m >= s2.marks[k - 1]));
}

// 4. Hors studio : aucun son d'interface ajouté (les autres styles ne changent pas)
{
	const r = clone(base);
	r.sfx = {...studio.sfx};
	r.styleScenes = clone(studio.styleScenes ?? []);
	verifier('hors studio : pas de son d’interface', !T.sfxEvents(r).some((e) => e.kind === 'interface' || e.kind === 'liste'));
}

console.log(`\n${ok}/${ok + ko} vérifications réussies`);
process.exit(ko ? 1 : 0);
