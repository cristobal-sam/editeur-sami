// Tests des fonctions pures V2 de remotion/src/timeline.ts (sans navigateur, sans rendu, rien n'est ecrit).
//   node docs/direction-creative-v2/tests/test-timeline-v2.mjs
// Donnees : copies FIGEES de Video 1 et Video 2 dans fixtures/projects/ (jamais les projets vivants de l'utilisateur).
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import * as T from '../../../remotion/src/timeline.ts';
import * as AVANT from '../avant/remotion-src/timeline.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../..');
// « projects/... » = donnees figees des tests (fixtures/projects), le reste est lu dans le dossier de l'editeur
const FIX = path.join(HERE, 'fixtures');
const load = (rel) => JSON.parse(fs.readFileSync(path.join(rel.startsWith('projects/') ? FIX : ROOT, rel), 'utf8'));
const SIZES = {'9:16': [1080, 1920], '16:9': [1920, 1080], '4:5': [1080, 1350], '1:1': [1080, 1080]};
let n = 0;
const ok = (cond, msg) => {
	assert.ok(cond, msg);
	n++;
	console.log(`OK   ${msg}`);
};
const near = (a, b, eps, msg) => ok(Math.abs(a - b) <= eps, `${msg} (${a.toFixed(4)} ~ ${b.toFixed(4)})`);

const base = load('projects/script1/reels/script.json');
const script2 = load('projects/script2/reels/script.json');

// ---------- 1. ancres : aller-retour, coupe, prise changee, plans deplaces ----------
{
	const r = structuredClone(base);
	for (const t of [0.5, 7.3, 20.02, 41.9, T.duration(r) - 0.2]) {
		const a = T.anchorAtTime(r, t);
		near(T.outputTimeOfAnchor(r, a), t, 1 / r.fps, `ancre a ${t} s : revient a la meme image`);
	}
	// ancre sur un mot du 2e plan, puis on coupe des mots du 1er plan : la note recule d'autant
	const c2 = r.clips[1];
	const w = c2.words.find((x) => !x.cut && x.start > c2.in + 1);
	const tw = T.timedWords(r).find((x) => x.clip === c2.id && x.w === w.w && Math.abs(x.outStart - T.timedWords(r).find((y) => y.clip === c2.id && y.index === c2.words.indexOf(w)).outStart) < 1e-9);
	const a = T.anchorAtTime(r, tw.outStart + 0.01);
	ok(a.clip === c2.id && a.source === c2.source && a.sig === c2.signature && a.image === c2.source, 'ancre : plan, prise, signature et image notees');
	const before = T.outputTimeOfAnchor(r, a);
	const cut = structuredClone(r);
	cut.clips[0].words.slice(2, 8).forEach((x) => (x.cut = true));
	const lost = T.duration(r) - T.duration(cut);
	ok(lost > 0.3, `coupe de 6 mots dans le 1er plan : ${lost.toFixed(2)} s retirees`);
	near(T.outputTimeOfAnchor(cut, a), before - lost, 1.5 / r.fps, 'apres la coupe, la note pointe toujours sur le meme mot');
	const place = T.resolveAnchor(cut, a);
	ok(place.exact && place.clip === c2.id, 'meme plan retrouve (exact)');
	// le mot de la note est coupe : null (jamais un autre passage en silence)
	const gone = structuredClone(r);
	const k = c2.words.indexOf(w);
	gone.clips[1].words.slice(Math.max(0, k - 1), k + 2).forEach((x) => (x.cut = true));
	ok(T.outputTimeOfAnchor(gone, a) === null, 'passage de la note coupe : null');
	// autre prise pour ce plan : null
	const take = structuredClone(r);
	take.clips[1] = {...take.clips[1], source: 'autre-prise', signature: 'autre-prise|0|9|true'};
	take.sources['autre-prise'] = take.sources[c2.source];
	ok(T.outputTimeOfAnchor(take, a) === null, 'prise changee : null');
	// plans deplaces : la note suit son plan
	const moved = structuredClone(r);
	const [first] = moved.clips.splice(0, 1);
	moved.clips.splice(3, 0, first);
	const segs = T.baseSegments(moved);
	const expect = T.toOut(segs, c2.id, a.src);
	near(T.outputTimeOfAnchor(moved, a), expect, 1e-9, 'plan deplace dans le montage : la note le suit');
	ok(Math.abs(expect - before) > 1, `la note a bien change de temps (${before.toFixed(2)} -> ${expect.toFixed(2)} s)`);
	// meme moment de la meme prise dans un AUTRE plan (plan duplique puis l'original supprime) : retrouve, exact=false
	const dup = structuredClone(r);
	dup.clips[1] = {...dup.clips[1], id: 'copie'};
	const p2 = T.resolveAnchor(dup, a);
	ok(p2 && !p2.exact && p2.clip === 'copie', 'plan d\'origine disparu, meme prise ailleurs : retrouve (exact = faux)');
	ok(T.anchorAtTime({...r, clips: []}, 3) === null, 'montage vide : pas d\'ancre');
}

// ---------- 2. rectangle de la prise visible : 4 formats ----------
{
	const r = structuredClone(base);
	const t = 12.4;
	const segs = T.videoSegments(r);
	const i = T.segmentAt(segs, t);
	const seg = segs[i];
	const local = t - seg.out_start;
	const tSrc = seg.src_in + local * (seg.speed ?? 1);
	const face = T.subjectAt(r, seg.source, tSrc, seg.src_in, seg.src_out); // point dessine sur le visage (prise)
	const pt = [face.cx, face.cy];
	const rects = {};
	for (const [f, [W, H]] of Object.entries(SIZES)) {
		const rect = T.sourceRectAt(r, t, f);
		rects[f] = rect;
		ok(rect.source === seg.source && rect.clip === seg.clip, `${f} : meme plan et meme prise que l'image`);
		// calcul independant : transformation CSS de SegmentVideo (Reel.tsx) sur le cadrage framing()
		const rf = {...r, width: W, height: H};
		const fr = T.framing(rf, seg.source, tSrc, seg.src_in, seg.src_out);
		const s = T.segmentZoom(rf, seg, segs[i + 1], T.duration(rf), local);
		const ox = fr.cx * W;
		const oy = fr.cy * H;
		const px = ox + s * (fr.left + pt[0] * fr.width - ox);
		const py = oy + s * (fr.top + pt[1] * fr.height - oy);
		const [x, y] = T.sourceToOutput(rect, pt);
		near(x * W, px, 0.5, `${f} : le point du visage tombe au meme pixel que l'image (x)`);
		near(y * H, py, 0.5, `${f} : le point du visage tombe au meme pixel que l'image (y)`);
		ok(x > 0 && x < 1 && y > 0 && y < 1, `${f} : le trait sur le visage reste dans l'image (${x.toFixed(2)}, ${y.toFixed(2)})`);
		const back = T.outputToSource(rect, [x, y]);
		near(back[0], pt[0], 1e-9, `${f} : aller-retour image -> prise (x)`);
		near(back[1], pt[1], 1e-9, `${f} : aller-retour image -> prise (y)`);
	}
	// une prise verticale en 16:9 montre toute la largeur mais une bande de la hauteur ; en 9:16, tout le cadre
	const src = r.sources[seg.source];
	ok(src.height > src.width, 'prise de test verticale');
	near(rects['9:16'].w * rects['9:16'].scale, 1, 1e-6, '9:16 : toute la largeur de la prise');
	near(rects['16:9'].h * rects['16:9'].scale, (1080 / 1920) / (1920 / 1080) * (src.width / src.height) * (1920 / 1080), 0.02, '16:9 : bande horizontale de la prise');
	ok(rects['1:1'].h < rects['4:5'].h && rects['4:5'].h < rects['9:16'].h, '1:1 < 4:5 < 9:16 en hauteur visible');
	// dessin : points de la prise -> image, et refus d'une autre prise
	const a = {id: 'a1', outil: 'cercle', couleur: '#FF0000', epaisseur: 6, points: [pt, [pt[0] + 0.05, pt[1]]], anchor: T.anchorAtTime(r, t), duree: 2};
	for (const f of Object.keys(SIZES)) {
		const pts = T.annotationOutput(r, a, t, f);
		near(pts[0][0], T.sourceToOutput(rects[f], pt)[0], 1e-9, `${f} : annotationOutput = sourceToOutput`);
	}
	const win = T.annotationWindow(r, a);
	near(win[0], t, 1 / r.fps, 'fenetre du dessin : commence a son ancre');
	near(win[1] - win[0], 2, 1e-9, 'fenetre du dessin : duree 2 s');
	ok(T.annotationOutput(r, {...a, anchor: {...a.anchor, image: 'autre-prise'}}, t) === null, 'dessin d\'une autre prise : pas affiche de travers');
	// zoom partage : identique a l'ancien calcul en ligne de SegmentVideo (Reel.tsx avant la V2)
	const old = (reel, sg, next, total, loc) => {
		const len = (next ? next.out_start : total) - sg.out_start;
		const progress = Math.min(1, Math.max(0, loc / Math.max(0.001, len)));
		let scale = 1;
		if (reel.zoom.overrides[String(sg.index)] !== undefined) scale = reel.zoom.overrides[String(sg.index)];
		else if (reel.zoom.auto && !reel.design?.mode) scale = sg.index % 2 === 1 ? reel.zoom.strength : 1;
		scale *= T.motivatedZoom(reel, sg.out_start + loc);
		scale *= 1 + reel.zoom.push * progress;
		if (reel.design?.mode === 'luxe' && reel.design.enabled !== false) scale *= .87;
		return scale;
	};
	for (const reel of [base, script2, {...script2, design: {mode: 'luxe'}}, {...script2, zoom: {...script2.zoom, overrides: {1: 1.3}}}]) {
		const ss = T.videoSegments(reel);
		const total = T.duration(reel);
		const same = ss.every((sg, j) => [0, 0.4, 1.3].every((loc) => old(reel, sg, ss[j + 1], total, loc) === T.segmentZoom(reel, sg, ss[j + 1], total, loc)));
		ok(same, `segmentZoom identique a l'ancien calcul (${reel.template}${reel.design?.mode ? ' / ' + reel.design.mode : ''})`);
	}
}

// ---------- 3. bruitages de la banque ----------
ok(T.sfxFile('whoosh-court') === 'sfx/editeur/whoosh-court.wav', 'bruitage court : assets/sfx/editeur');
ok(T.sfxFile('sfx/kenney/impact-sounds/a.ogg') === 'sfx/kenney/impact-sounds/a.ogg', 'bruitage de la banque : chemin garde');
ok(T.sfxFile('../../cles-api.env') === 'cles-api.env' && !T.sfxFile('a/../../b.wav').includes('..'), 'jamais de « .. » dans un chemin de bruitage');
{
	const r = structuredClone(script2);
	r.sfx.extra = [{t: 3, name: 'whoosh-court'}, {t: 5, name: 'sfx/kenney/x.ogg', gain: 0.5}];
	const ev = T.sfxEvents(r).filter((e) => e.kind === 'ajoute');
	near(ev[1].volume, r.sfx.volume * 0.8 * 0.5, 1e-9, 'gain d\'un bruitage de la banque applique');
}

// ---------- 4. anciens reels : calculs identiques a la version d'avant (docs/direction-creative-v2/avant) ----------
{
	const fixtures = ['projects/script1/reels/script.json', 'projects/script2/reels/script.json',
		...fs.readdirSync(path.join(ROOT, 'docs/galerie-styles/tests')).filter((f) => f.endsWith('-apercu.json')).map((f) => `docs/galerie-styles/tests/${f}`)];
	// Ronde 3 (02/10/2026), changements VOULUS, testes dans docs/qualite-2026-09-30/tests/test-ronde3.mjs :
	// - une ponctuation seule transcrite comme un mot (« « », « ». ») ne fait plus une page de sous-titres vide : pour comparer
	//   le reste, elle est masquee (hide) dans la copie donnee aux DEUX versions (indices des mots inchanges) ;
	// - studio Tech 3D : relances de cadre, sons d'interface et listes (la camera place autrement les interfaces) : sfxEvents et
	//   designScenes ne sont compares que hors du studio.
	// Juge n° 3 (02/10/2026), changement VOULU, teste dans docs/qualite-2026-09-30/tests/test-juge3.mjs : une seule apostrophe à
	// l'image (displayWord écrit « ’ ») ; la copie donnée aux DEUX versions a déjà l'apostrophe courbe (srt comparable).
	const prep = (r) => {
		for (const c of r.clips) for (const w of c.words) {
			if (!T.displayWord(w.w, false)) w.hide = true;
			w.w = String(w.w).replace(/'/g, '’');
		}
		// Sons (02/10/2026), changement VOULU, teste dans docs/claude-api/tests/test_sons.mjs : les sons de coupe varient (sfx.varier
		// absent = oui) ; « varier: false » redonne exactement les sons d'avant : la copie donnee aux DEUX versions l'a.
		if (r.sfx) r.sfx = {...r.sfx, varier: false};
		return r;
	};
	// Juge n° 2 (02/10/2026), changement VOULU, teste dans docs/qualite-2026-09-30/tests/test-juge2.mjs : le decoupage des pages
	// de sous-titres cherche le meilleur decoupage de chaque phrase (virgules, petits mots, expressions figees, pages eclair).
	// pages et srt sont donc compares avec une page = un mot (maxWords 1, hors studio) dans la copie donnee aux DEUX versions :
	// coupures obligatoires (fin de phrase, pause, plan), ponctuation seule et temps restent compares mot a mot.
	const unMot = (r) => ({...r, style: {...r.style, maxWords: 1}, design: r.design ? {...r.design, cinematic: false} : r.design});
	for (const f of fixtures) {
		const r = prep(load(f));
		const studio = T.studioMode(r);
		const fns = ['duration', 'videoSegments', 'audioSegments', 'pages', 'pacing', 'srt', ...(studio ? [] : ['sfxEvents', 'designScenes'])];
		for (const fn of fns) {
			const x = fn === 'pages' || fn === 'srt' ? unMot(r) : r;
			assert.deepEqual(T[fn](x), AVANT[fn](x), `${f} : ${fn} a change`);
		}
		n++;
		console.log(`OK   ${f} : ${fns.length} calculs identiques a avant la V2${studio ? ' (studio : camera et sons de la ronde 3 exclus)' : ''}`);
	}
}

// ---------- 5. notes et dessins jamais lus par la composition (absents de l'export) ----------
{
	const files = fs.readdirSync(path.join(ROOT, 'remotion/src')).map((f) => path.join(ROOT, 'remotion/src', f)).concat(path.join(ROOT, 'remotion/render.mjs'));
	const bad = files.filter((f) => !/timeline\.ts$|types\.ts$/.test(f)).filter((f) => /\.(notes|annotations)\b|annotationOutput|annotationWindow/.test(fs.readFileSync(f, 'utf8')));
	ok(!bad.length, `aucun fichier de la composition ne lit les notes ou les dessins (${bad.join(', ') || 'aucun'})`);
}

console.log(`\n${n} verifications V2 (timeline) reussies`);
