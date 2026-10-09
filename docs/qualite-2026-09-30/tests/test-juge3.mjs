// Tests du rendu (timeline.ts) pour les finitions demandées par le juge indépendant n° 3 (2 octobre 2026) :
//   node docs/qualite-2026-09-30/tests/test-juge3.mjs
// Données FIGÉES (jamais un projet vivant) :
//  - cas/juge2-p3d.json : Vidéo 1 en Tech 3D telle que jugée par le juge n° 3 (deux boutons, scènes d'avant) ;
//  - cas/juge3-p3d.json : la même après cette finition (bouton unique avec l'offre, détourage v7).
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const ICI = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(ICI, '../../..');
const T = await import(pathToFileURL(path.join(ROOT, 'remotion/src/timeline.ts')).href);
const lire = (f) => JSON.parse(fs.readFileSync(path.join(ICI, 'cas', f), 'utf8'));
const CAS = {juge2: lire('juge2-p3d.json'), juge3: lire('juge3-p3d.json')};
const copie = (k) => JSON.parse(JSON.stringify(CAS[k]));
let ok = 0, n = 0;
const verifier = (nom, cond, detail = '') => {
	n += 1;
	if (cond) ok += 1;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${nom}${detail ? ' — ' + detail : ''}`);
};

/** Caméra image par image : changements dans un même plan (sans coupe). */
const camera = (r) => {
	const segs = T.videoSegments(r);
	const fps = r.fps || 30;
	const out = [];
	let prev = null;
	for (let f = 0; f < Math.round(T.duration(r) * fps); f++) {
		const t = f / fps;
		const k = T.segmentAt(segs, t);
		const v = T.studioView(r, segs[k], t);
		const fr = T.framing(r, segs[k].source, T.segSrcTime(segs[k], t), segs[k].src_in, segs[k].src_out);
		const cur = {t, k, v, cy: fr.cy};
		if (prev && v && prev.v && prev.k === k) {
			const y = (vv, cy) => vv.oy + (cy - vv.oy) * vv.scale + (vv.dy ?? 0);
			out.push({t, r: v.scale / prev.v.scale, dy: y(v, prev.cy) - y(prev.v, prev.cy)});
		}
		prev = cur;
	}
	return out;
};

// ---------- 1. sauts d'image sans coupe (0:25,6, 0:36,6, 0:40,4, 1:03,7 dans l'export jugé) ----------
for (const k of ['juge2', 'juge3']) {
	const r = copie(k);
	const sauts = camera(r).filter((c) => c.t >= 1 && c.r >= 0.93 && c.r <= 1.07 && Math.abs(c.dy) > 0.012);
	verifier(`${k} : aucun saut d'image sans coupe (taille × 0,93–1,07, déplacement > 1,2 % de la hauteur en une image)`, sauts.length === 0,
		sauts.map((s) => `${s.t.toFixed(2)} s ${(s.dy * r.height).toFixed(0)} px`).join(', ') || '0');
	// tout changement de cadre d'un coup sans coupe est un vrai changement de plan (au moins × 1,15) ou un glissement
	const brusques = camera(r).filter((c) => c.t >= 1 && Math.abs(Math.log(c.r)) > 0.02 && Math.abs(Math.log(c.r)) < Math.log(1.15) - 1e-3);
	verifier(`${k} : changement de taille d'un coup sans coupe = au moins × 1,15`, brusques.length === 0,
		brusques.map((s) => `${s.t.toFixed(2)} s × ${s.r.toFixed(3)}`).join(', ') || '0');
}

// ---------- 2. pas de recul « mécanique » 1 s avant une carte : le cadre change sur l'image où elle entre (ou sur une coupe) ----------
{
	const r = copie('juge3');
	const cam = camera(r);
	const avant = [];
	for (const s of T.designScenes(r)) {
		const pre = cam.filter((c) => c.t > s.at - 1.2 && c.t < s.at - 0.07 && Math.abs(Math.log(c.r)) > 0.05);
		if (pre.length) avant.push(`${s.text} ${pre[0].t.toFixed(2)} s`);
	}
	verifier('aucun changement de taille franc dans la seconde qui précède une carte', avant.length === 0, avant.join(', ') || '0');
	const liste = T.designScenes(r).find((s) => s.kind === 'list');
	const entree = cam.find((c) => Math.abs(c.t - liste.at) < 0.05 && Math.abs(Math.log(c.r)) > 0.1);
	verifier('la liste « pousse » la personne : le plan s\'élargit sur son image d\'entrée', !!entree, entree ? `× ${entree.r.toFixed(3)} à ${entree.t.toFixed(2)} s` : 'aucun');
}

// ---------- 3. bouton unique de la 1re demande à la fin, l'offre entre au-dessus quand elle est dite ----------
{
	const r = copie('juge3');
	const ctas = T.designScenes(r).filter((s) => s.kind === 'cta');
	const total = T.duration(r);
	const c = ctas[0];
	verifier('un seul bouton, tenu jusqu\'à la dernière image', ctas.length === 1 && c.end >= total - 0.05 && c.at < 60.5, ctas.map((s) => `${s.at.toFixed(2)}–${s.end.toFixed(2)}`).join(' '));
	verifier('l\'offre entre sur « gratuitement » (marks[1]) et le bouton dès l\'entrée (marks[0])', c.marks?.length === 2 && Math.abs(c.marks[0] - c.at) < 1e-6 && Math.abs(c.marks[1] - 64.45) < 0.1,
		JSON.stringify(c.marks?.map((m) => +m.toFixed(2))));
	const clics = T.sfxEvents(r).filter((e) => e.kind === 'bouton');
	verifier('un clic quand l\'offre rejoint le bouton, pas en double avec le whoosh d\'entrée', clics.length === 1 && Math.abs(clics[0].t - c.marks[1]) < 1e-6,
		clics.map((e) => e.t.toFixed(2)).join(' '));
	// ancien reel (deux boutons, champ lead) : rendu inchangé
	const vieux = T.designScenes(copie('juge2')).filter((s) => s.kind === 'cta');
	verifier('ancien reel à deux boutons : toujours lu (le 2e entre sur l\'offre, le bouton sur son mot)', vieux.length === 2 && vieux[1].marks?.length === 1 && vieux[1].marks[0] > vieux[1].at,
		vieux.map((s) => `${s.at.toFixed(2)}`).join(' '));
	// mot de l'offre coupé : le badge est affiché dès l'entrée (pas d'erreur)
	const coupe = copie('juge3');
	const sc = coupe.styleScenes.find((s) => s.kind === 'cta');
	coupe.clips.find((x) => x.id === sc.clip).words[sc.offer].hide = true;
	const c2 = T.designScenes(coupe).find((s) => s.kind === 'cta');
	verifier('mot de l\'offre masqué : offre affichée avec le bouton', c2 && c2.marks?.length === 1, JSON.stringify(c2?.marks));
}

// ---------- 4. sous-titres : jamais un bout de page de moins de 0,6 s ; la carte qui redit la page entre avec elle ----------
for (const k of ['juge2', 'juge3']) {
	const r = copie(k);
	const fps = r.fps || 30;
	const courts = [];
	for (const p of T.pages(r)) {
		let vis = 0, cache = 0;
		for (let f = Math.ceil(p.start * fps - 1e-6); f / fps < p.end - 1e-6; f++) T.captionHidden(r, f / fps) ? cache++ : vis++;
		if (cache && vis && vis / fps < 0.55) courts.push(`${p.start.toFixed(2)} ${(vis / fps).toFixed(2)} s`);
	}
	verifier(`${k} : aucune page à moitié masquée visible moins de 0,6 s (sous-titre éclair)`, courts.length === 0, courts.join(', ') || '0');
}
{
	// l'ancrage sur le 1er mot de la page est posé par le moteur (galerie._aligner_pages, test_juge3.py) : données d'après
	const r = copie('juge3');
	const flow = T.designScenes(r).find((s) => s.kind === 'flow');
	const page = T.pages(r).find((p) => p.words.some((w) => /^r[ée]pondre$/i.test(w.w)) && p.start < flow.at + 0.01 && p.end > flow.at);
	verifier('« pour répondre et qualifier » : le parcours entre avec la page qui le dit', page && Math.abs(flow.at - page.start) < 1e-6,
		`page ${page?.start.toFixed(2)} / carte ${flow.at.toFixed(2)}`);
}

// ---------- 5. une seule apostrophe à l'image ----------
{
	verifier('displayWord : apostrophe typographique', T.displayWord("quelqu'un", false) === 'quelqu’un' && T.displayWord('c’est', false) === 'c’est');
	const r = copie('juge2');
	const droites = T.pages(r).filter((p) => p.words.some((w) => T.displayWord(w.w, false).includes("'")));
	verifier('aucune apostrophe droite dans les sous-titres affichés', droites.length === 0, `${droites.length} page(s)`);
	verifier('typo : texte des cartes', T.typo("Lead d'un client") === 'Lead d’un client');
}

// ---------- 6. coupures de page plus fortes (« c’est | pas », « un vrai | intérêt », « chaque | lead », « qu'on | engage ») ----------
{
	const r = copie('juge2');
	const fins = [];
	for (const p of T.pages(r)) {
		const w = p.words[p.words.length - 1].w;
		const tok = w.toLowerCase().replace(/’/g, "'").replace(/[«»",.;:!?…]/g, '');
		if (["c'est", 'vrai', 'chaque', "qu'on", 'parce', 'bien'].includes(tok) && !/[.!?…]["»”)\]]*$/.test(w)) fins.push(`${p.start.toFixed(2)} « ${w} »`);
	}
	verifier('aucune page ne finit sur « c’est », « vrai », « chaque », « qu’on », « parce », « bien »', fins.length === 0, fins.join(', ') || '0');
}

console.log(`\n${ok}/${n} vérifications réussies`);
process.exit(ok === n ? 0 : 1);
