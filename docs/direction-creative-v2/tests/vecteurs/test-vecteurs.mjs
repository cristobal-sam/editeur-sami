// Tests des vecteurs V2 (agent « vecteurs ») : bibliotheque SVG, recoloration SANS perte de formes, palette charte / style,
// couleurs manuelles, animation, nettoyage des SVG, et couleurs affichees apres les passes du moteur (style, sobriete,
// ensure, refresh_ai : test-vecteurs-moteur.py sur des copies).
//   node docs/direction-creative-v2/tests/vecteurs/test-vecteurs.mjs        (environnement charge : runtime/env.sh)
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {ROOT, TMP, VDIR, bibliotheque, chargerVecteurs, lireFiche, lireSvg} from './charger.mjs';

const V = await chargerVecteurs();
let fails = 0;
let count = 0;
const ok = (cond, msg) => {
	count++;
	if (!cond) {
		fails++;
		console.log(`ECHEC ${msg}`);
	} else if (process.env.VERBOSE) console.log(`OK    ${msg}`);
	return cond;
};
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const reel2 = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs/direction-creative-v2/tests/fixtures/projects/script2/reels/script.json'), 'utf8')); // copie figee
const base = (extra = {}) => ({...structuredClone(reel2), ...extra});
const PAINT = /^(none|var\(--v-(principale|secondaire|contour),\s*#[0-9A-F]{6}\))$/;
const VAR = /var\(--v-(principale|secondaire|contour),\s*(#[0-9A-Fa-f]{3,8})\)/g;

// ---------------------------------------------------------------- A. bibliotheque ----------------------------------------------------------------
const noms = fs.readdirSync(VDIR).filter((f) => f.endsWith('.svg')).map((f) => f.slice(0, -4)).sort();
const jsons = fs.readdirSync(VDIR).filter((f) => f.endsWith('.json')).map((f) => f.slice(0, -5)).sort();
ok(noms.length >= 30, `bibliotheque : ${noms.length} vecteurs (>= 30)`);
ok(eq(noms, jsons), 'chaque SVG a sa fiche .json et chaque fiche son SVG (aucun autre .json dans le dossier)');
ok(eq([...bibliotheque()].sort(), noms), 'VECTOR_LIBRARY (vector-panel.tsx) = fichiers du dossier');
ok(fs.existsSync(path.join(VDIR, 'LISEZMOI.txt')), 'LISEZMOI.txt (licence, provenance, format) present');
const categories = new Set();
let multicolores = 0;
for (const nom of noms) {
	const raw = lireSvg(nom);
	const f = lireFiche(nom);
	const w = `${nom}.svg`;
	ok(raw.length < 8192, `${w} : ${raw.length} octets (< 8 Ko)`);
	ok(!/<(script|style|image|foreignObject|text|a|iframe|animate|set)\b/i.test(raw) && !/\son\w+\s*=/i.test(raw) && !/href|url\(/i.test(raw),
		`${w} : aucun script, style global, texte, image, lien ni ressource externe`);
	ok(!/\sid=/.test(raw), `${w} : aucun id (plusieurs copies a l'image sans conflit)`);
	const svg = V.prepareSvg(raw, 'test');
	if (!ok(svg && svg.viewBox.length === 4 && svg.shapes > 0 && svg.ratio > 0, `${w} : SVG lisible (viewBox, ${svg?.shapes} formes)`)) continue;
	// toute la peinture passe par les variables : rien de code en dur, donc rien que la charte ne puisse recolorer
	const paints = [];
	const walk = [];
	for (const t of V.svgTags(raw)) {
		if (t.close) {
			walk.pop();
			continue;
		}
		const style = Object.fromEntries((t.attrs.find(([k]) => k === 'style')?.[1] ?? '').split(';').filter((s) => s.includes(':'))
			.map((s) => [s.slice(0, s.indexOf(':')).trim(), s.slice(s.indexOf(':') + 1).trim()]));
		for (const [k, v] of t.attrs) if (['fill', 'stroke', 'stop-color', 'color'].includes(k)) paints.push(v);
		for (const k of ['fill', 'stroke', 'stop-color', 'color']) if (style[k]) paints.push(style[k]);
		const eff = {fill: style.fill ?? walk.at(-1)?.fill, stroke: style.stroke ?? walk.at(-1)?.stroke};
		if (V.SHAPES.has(t.name)) {
			ok((eff.fill && eff.fill !== 'none') || (eff.stroke && eff.stroke !== 'none'), `${w} : <${t.name}> peint (remplissage ou trait)`);
			if (/\bv-trait\b/.test(t.attrs.find(([k]) => k === 'class')?.[1] ?? '')) {
				ok(t.attrs.some(([k, v]) => k === 'pathLength' && v === '1') && eff.fill === 'none' && eff.stroke?.startsWith('var('),
					`${w} : trait a tracer (pathLength="1", sans remplissage, trait par variable)`);
			}
		}
		if (!t.self) walk.push(eff);
	}
	ok(paints.length && paints.every((p) => PAINT.test(p)), `${w} : couleurs uniquement par var(--v-…, #RRGGBB) ou none (${paints.filter((p) => !PAINT.test(p)).join(', ')})`);
	const used = new Set([...raw.matchAll(VAR)].map((m) => m[1]));
	if (used.size >= 2) multicolores++;
	// fiche (SPEC 9.1) : champs obligatoires, coherente avec le dessin
	categories.add(f.categorie);
	ok(typeof f.nom === 'string' && f.nom.length > 1 && typeof f.categorie === 'string' && /^[\p{L}\p{N} _-]+$/u.test(f.categorie)
		&& Array.isArray(f.motsCles) && f.motsCles.length >= 3 && [1, 2, 3].includes(f.intensite) && f.licence && f.provenance
		&& eq(f.formats, ['9:16', '16:9', '4:5', '1:1']), `${nom}.json : nom, categorie, mots-cles, intensite, licence, provenance, formats`);
	for (const k of V.SLOTS) {
		const def = new RegExp(`var\\(--v-${k},\\s*(#[0-9A-Fa-f]{6})\\)`).exec(raw)?.[1]?.toUpperCase() ?? null;
		ok(f.couleurs[k] === def, `${nom}.json : couleur ${k} d'origine = dessin (${f.couleurs[k]} / ${def})`);
		ok(!raw.includes(`--v-${k},`) || [...raw.matchAll(new RegExp(`var\\(--v-${k},\\s*(#[0-9A-Fa-f]{6})\\)`, 'g'))].every((m) => m[1].toUpperCase() === def),
			`${w} : une seule couleur d'origine par emplacement (${k})`);
	}
	ok(f.trace === svg.traits > 0, `${nom}.json : « trace » = le dessin a des traits a tracer (${svg.traits})`);
	ok(f.boucle === svg.boucle, `${nom}.json : boucle = data-boucle (${f.boucle})`);
	for (const s of ['entree', 'sortie']) {
		const m = V.parseMove(f.anim?.[s], 'aucune');
		ok(V.ANIM_CHOICES.some(([k]) => k === f.anim[s]) && (m.type !== 'trace' || svg.traits > 0), `${nom}.json : animation ${s} « ${f.anim?.[s]} » valide`);
	}
	ok(f.duree >= 0.5 && f.duree <= 8 && f.largeur >= 0.05 && f.largeur <= 1.2, `${nom}.json : duree ${f.duree} s et largeur ${f.largeur} raisonnables`);
}
ok(categories.size >= 6, `${categories.size} categories (${[...categories].join(', ')})`);
ok(multicolores >= 20, `${multicolores} vecteurs multicolores (>= 2 couleurs recolorables)`);

// ---------------------------------------------------------------- B. recoloration sans perte ----------------------------------------------------------------
const charte = {client: 'essai', name: 'Charte essai', logo: null, logoPosition: 'haut-droite', logoSize: 0.16, logoOpacity: 0.85,
	bannerBg: '#7C3AED', bannerColor: '#FFFFFF', style: {highlight: '#FF2D95'}, outro: {enabled: false, text: '', duration: 2.5}};
const rCharte = base({brand: charte, style: {...reel2.style, highlight: '#FF2D95'}});
const MAIN = {principale: '#00C2FF', secondaire: '#0A2A66', contour: '#FFFFFF'};
/** Ce que fait le navigateur : chaque var(--v-x, defaut) prend la valeur posee sur le conteneur, sinon son defaut. */
const resoudre = (markup, vars) => markup.replace(VAR, (_, k, d) => vars[`--v-${k}`] ?? d);
const peintures = (markup) => new Set([...markup.matchAll(/(?:fill|stroke):(#[0-9A-Fa-f]{3,8}|none)/g)].map((m) => m[1].toUpperCase()).filter((c) => c !== 'NONE'));
let recolores = 0;
for (const nom of noms) {
	const raw = lireSvg(nom);
	const used = [...new Set([...raw.matchAll(VAR)].map((m) => m[1]))];
	if (used.length < 2) continue;
	recolores++;
	const avant = V.svgShapes(raw);
	const v = {id: `r-${nom}`, asset: `banque/vecteurs/${nom}.svg`, at: 0, duration: 2, x: 0.5, y: 0.5, w: 0.3, rotation: 0, opacite: 1,
		couleurs: {principale: null, secondaire: null, contour: null}, couleursManuelles: false, anim: {entree: 'pop', sortie: 'fondu'}};
	const svg = V.prepareSvg(raw, v.id);
	const apres = V.svgShapes(svg.markup);
	ok(eq(avant, apres) && apres.length === svg.shapes, `${nom} : ${avant.length} formes identiques apres preparation (balises + geometrie)`);
	// 1) la charte recolore (couleurs nulles)
	const cCharte = V.vectorColors(rCharte, v);
	ok(eq(cCharte, {principale: '#FF2D95', secondaire: '#7C3AED', contour: '#000000'}), `${nom} : charte -> ${JSON.stringify(cCharte)}`);
	const p1 = peintures(resoudre(svg.markup, V.colorVars(cCharte)));
	const attendu1 = new Set(used.map((k) => cCharte[k].toUpperCase()));
	ok(eq([...p1].sort(), [...attendu1].sort()), `${nom} : a l'image, seules les couleurs de la charte (${[...p1].join(' ')})`);
	// 2) retouche a la main : ses couleurs, meme avec la charte
	const vm = {...v, couleurs: {...MAIN}, couleursManuelles: true};
	const cMain = V.vectorColors(rCharte, vm);
	ok(eq(cMain, MAIN), `${nom} : couleurs manuelles gardees malgre la charte`);
	const p2 = peintures(resoudre(svg.markup, V.colorVars(cMain)));
	ok(eq([...p2].sort(), [...new Set(used.map((k) => MAIN[k]))].sort()), `${nom} : a l'image, seules les couleurs choisies (${[...p2].join(' ')})`);
	// le dessin prepare ne depend PAS des couleurs : recolorer ne peut rien perdre (formes, traits, animation)
	ok(V.prepareSvg(raw, v.id).markup === svg.markup, `${nom} : dessin identique quelle que soit la couleur`);
	ok(V.vectorMotion(v, 0.3, {w: 1080, h: 1920}, {w: 324, h: 324}, svg.stages).opacity === V.vectorMotion(vm, 0.3, {w: 1080, h: 1920}, {w: 324, h: 324}, svg.stages).opacity,
		`${nom} : animation identique apres recoloration`);
}
ok(recolores >= 20, `${recolores} SVG multicolores recolores (charte puis main) sans perte`);

// ---------------------------------------------------------------- C. regles de palette ----------------------------------------------------------------
const nul = {couleurs: {principale: null, secondaire: null, contour: null}, couleursManuelles: false};
ok(eq(V.vectorColors(base(), nul), {principale: '#FFD400', secondaire: '#FFFFFF', contour: '#000000'}), 'sans charte ni galerie : couleurs du style (mots en couleur, texte, contour)');
const tech = base({design: {mode: 'tech', enabled: true, accent: '#86B7FF', secondary: '#E0E0FF'}});
ok(eq(V.vectorColors(tech, nul), {principale: '#86B7FF', secondaire: '#E0E0FF', contour: '#000000'}), 'style de la galerie : accent et couleur secondaire du style');
ok(eq(V.vectorColors({...tech, brand: charte}, nul), {principale: '#FF2D95', secondaire: '#E0E0FF', contour: '#000000'}), 'charte + galerie : accent de la charte d\'abord');
ok(V.vectorColors({...tech, design: {...tech.design, enabled: false}}, nul).principale === '#FFD400', 'galerie desactivee : son accent ne compte plus');
ok(eq(V.vectorColors(tech, {couleurs: {principale: '#123456', secondaire: null, contour: null}, couleursManuelles: true}), {principale: '#123456', secondaire: null, contour: null}),
	'couleurs manuelles : un emplacement vide garde la couleur d\'origine du dessin (pas la charte)');
ok(eq(V.vectorColors(tech, {couleurs: {principale: '#22C55E', secondaire: null, contour: null}, couleursManuelles: false}), {principale: '#22C55E', secondaire: '#E0E0FF', contour: '#000000'}),
	'couleur fixee sans verrou des couleurs : elle fait foi, les autres suivent la palette');
ok(V.vectorColors(tech, {couleurs: {principale: 'red;background:url(http://x)', secondaire: 'url(#a)', contour: 'expression(1)'}, couleursManuelles: false}).principale === '#86B7FF'
	&& V.safeColor('red;background:url(http://x)') === null && V.safeColor('#abc') === '#abc' && V.safeColor('rgba(1, 2, 3, .5)') === 'rgba(1, 2, 3, .5)',
	'couleur piegee refusee (rien d\'autre qu\'une couleur n\'entre dans une variable CSS)');
ok(V.vectorColors(base({style: {...reel2.style, highlight: 'rouge'}}), nul).principale === null, 'palette invalide : couleur d\'origine du dessin');

// ---------------------------------------------------------------- D. animation ----------------------------------------------------------------
const F = {w: 1080, h: 1920};
const S = {w: 378, h: 280};
const mk = (entree, sortie, duration = 2) => ({at: 10, duration, anim: {entree, sortie}});
for (const e of ['pop', 'fondu', 'zoom', 'glisse-gauche', 'glisse-bas', 'trace']) {
	const a = V.vectorMotion(mk(e, 'fondu'), 10, F, S, 2);
	const b = V.vectorMotion(mk(e, 'fondu'), 11, F, S, 2);
	ok(a.opacity < 0.05 || a.scale < 0.05 || a.draw === 0, `entree ${e} : invisible au premier instant (opacite ${a.opacity.toFixed(2)}, echelle ${a.scale.toFixed(2)})`);
	ok(b.opacity === 1 && Math.abs(b.scale - 1) < 1e-9 && b.tx === 0 && b.ty === 0 && b.dash.every((d) => d === 0), `entree ${e} : entierement la au milieu`);
}
{
	const g = V.vectorMotion(mk('glisse-gauche', 'glisse-droite'), 10.1, F, S, 0);
	ok(g.tx < 0 && g.ty === 0, `glisse-gauche : arrive par la gauche (${g.tx.toFixed(0)} px)`);
	const o = V.vectorMotion(mk('glisse-gauche', 'glisse-droite'), 11.9, F, S, 0);
	ok(o.tx > 0, `glisse-droite en sortie : part vers la droite (${o.tx.toFixed(0)} px)`);
	const h = V.vectorMotion(mk('glisse-haut', 'fondu'), 10.1, F, S, 0);
	ok(h.ty < 0, 'glisse-haut : arrive par le haut');
	const p = [10.05, 10.15, 10.25, 10.35, 10.44].map((t) => V.vectorMotion(mk('pop', 'fondu'), t, F, S, 0).scale);
	ok(Math.max(...p) > 1.02 && p[0] < p[1], `pop : rebond (${p.map((x) => x.toFixed(2)).join(' ')})`);
	const f = [11.72, 11.8, 11.9, 11.98].map((t) => V.vectorMotion(mk('pop', 'fondu'), t, F, S, 0).opacity);
	ok(f.every((x, i) => i === 0 || x < f[i - 1]) && f[0] <= 1, `sortie fondu : opacite qui baisse (${f.map((x) => x.toFixed(2)).join(' ')})`);
	// trace en 2 etapes : la 1re se dessine entierement avant la 2e
	// duree 2,2 s -> entree tracee en 0,88 s (40 %)
	const tr = [0.1, 0.3, 0.45, 0.6, 0.87].map((d) => V.vectorMotion(mk('trace', 'trace', 2.2), 10 + d, F, S, 2).dash);
	ok(tr[0][0] > 0 && tr[0][0] < 1 && tr[0][1] === 1, `trace : etape 1 en cours, etape 2 pas commencee (${tr[0].map((x) => x.toFixed(2))})`);
	ok(tr.every((d, i) => i === 0 || (d[0] <= tr[i - 1][0] && d[1] <= tr[i - 1][1])) && tr[4][1] < 0.1, `trace : progresse sans revenir (${tr.map((d) => d.map((x) => x.toFixed(2)).join('/')).join(' ')})`);
	const ef = [12.0, 12.1, 12.19].map((t) => V.vectorMotion(mk('trace', 'trace', 2.2), t, F, S, 2).dash);
	ok(ef[0][1] > 0 && ef.every((d, i) => i === 0 || d[1] >= ef[i - 1][1]), `sortie trace : le trait s'efface (${ef.map((d) => d.map((x) => x.toFixed(2)).join('/')).join(' ')})`);
	const nd = V.vectorMotion(mk('trace', 'fondu'), 10.1, F, S, 0);
	ok(nd.inType === 'fondu', 'trace demande sur un dessin sans trait : fondu');
	const cue = {id: 'q', cible: {type: 'vector', id: 'x'}, at: 10, duree: 2, entree: {type: 'trace', duree: 1.2, courbe: 'lineaire'}, sortie: {type: 'aucune', duree: 0, courbe: 'lineaire'},
		sync: {sur: 'mot', ref: null}, raison: 'essai', auto: true, locked: false};
	const c = V.vectorMotion(mk('pop', 'fondu'), 10.6, F, S, 1, cue);
	ok(c.inType === 'trace' && Math.abs(c.dash[0] - 0.5) < 0.01, `mouvement « trace » de la choregraphie : dessine ici, sur sa duree (${c.dash[0].toFixed(2)})`);
	const cd = V.vectorMotion(mk('pop', 'fondu'), 10.6, F, S, 1, {...cue, entree: {...cue.entree, courbe: 'douce'}});
	ok(Math.abs(cd.dash[0] - 0.125) < 0.01, `… avec sa courbe (douce : 87,5 % dessine a mi-duree, ${cd.dash[0].toFixed(3)})`);
	ok(V.vectorMotion(mk('pop', 'fondu'), 10.6, F, S, 1, {...cue, desactive: true}).inType === 'pop', 'mouvement desactive : animation propre du vecteur');
	const court = V.vectorMotion(mk('pop', 'fondu', 0.4), 10.2, F, S, 0);
	ok(court.opacity > 0.9, `vecteur tres court (0,4 s) : bien visible au milieu (${court.opacity.toFixed(2)})`);
	ok(V.vectorMotion(mk('aucune', 'aucune'), 10, F, S, 0).opacity === 1 && V.vectorMotion(mk('aucune', 'aucune'), 11.99, F, S, 0).opacity === 1, 'aucune : net du debut a la fin');
	ok(V.loopTransform('rotation', 0.5).startsWith('rotate(') && V.loopTransform(null, 1) === '' && V.loopTransform('flotte', 0.35).includes('translateY'), 'mouvements en boucle (rotation, flotte)');
	const again = V.vectorMotion(mk('zoom', 'pop'), 10.2, F, S, 0);
	ok(eq(again, V.vectorMotion(mk('zoom', 'pop'), 10.2, F, S, 0)), 'animation pure : meme instant = meme image (apercu = export)');
}

// ---------------------------------------------------------------- E. nettoyage d'un SVG piege ----------------------------------------------------------------
{
	const piege = `<?xml version="1.0"?><!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" onload="alert(1)">
	<style>body{display:none}</style><script>alert(2)</script><title>x</title>
	<defs><linearGradient id="g"><stop offset="0" style="stop-color:var(--v-principale,#FF0000)"/></linearGradient></defs>
	<rect id="r" x="1" y="2" width="3" height="4" style="fill:url(#g)" onclick="alert(3)"/>
	<use href="#r"/><use href="http://mal.com/x.svg#a"/><image href="http://mal.com/a.png"/>
	<foreignObject><div>html</div></foreignObject><a href="javascript:alert(4)"><circle r="3"/></a>
	<path d="M0 0" style="fill:url(http://mal.com/p)" class="v-trait"/><animate attributeName="x"/></svg>`;
	const s = V.prepareSvg(piege, 'z9');
	ok(s && eq(s.viewBox, [0, 0, 100, 50]), 'SVG sans viewBox : taille reprise de width/height');
	ok(!/script|<style|onload|onclick|foreignObject|<image|<a\b|javascript|mal\.com|<animate|<title/i.test(s.markup), `SVG piege nettoye : ${s.markup.slice(0, 400)}`);
	ok(/id="z9-g"/.test(s.markup) && /url\(#z9-g\)/.test(s.markup) && /href="#z9-r"/.test(s.markup), 'ids prefixes et references suivies (plusieurs copies a l\'image)');
	ok(/stroke-dashoffset:var\(--v-trace-1,0\)/.test(s.markup) && /pathLength="1"/.test(s.markup), 'trait sans pathLength : ajoute, relie a --v-trace-1');
	ok(s.markup.includes('overflow:visible') && !/width="100"/.test(s.markup), 'racine : jamais rognee, taille du conteneur');
	ok(V.prepareSvg('<div>pas un svg</div>') === null && V.prepareSvg('<svg><rect/></svg>') === null, 'fichier qui n\'est pas un SVG exploitable : ignore');
	ok(V.safeAsset('banque/vecteurs/fleche.svg') && !V.safeAsset('banque/../../cles-api.env') && !V.safeAsset('/etc/x.svg') && !V.safeAsset('banque/x.png')
		&& !V.safeAsset('http://x/y.svg'), 'chemin de vecteur confine a assets/ (.svg, jamais « .. »)');
	const deux = [V.prepareSvg(piege, 'a1').markup, V.prepareSvg(piege, 'b2').markup];
	ok(deux[0] !== deux[1] && deux[0].includes('a1-g') && deux[1].includes('b2-g'), 'deux vecteurs identiques a l\'image : ids distincts');
}

// ---------------------------------------------------------------- F. apres les passes du moteur (copies) ----------------------------------------------------------------
{
	fs.mkdirSync(TMP, {recursive: true});
	const sortie = path.join(TMP, `moteur-${process.pid}.json`);
	const py = path.join(ROOT, 'runtime', 'venv', 'Scripts', 'python.exe');
	const run = spawnSync(py, [path.join(ROOT, 'docs/direction-creative-v2/tests/vecteurs/test-vecteurs-moteur.py')],
		{cwd: path.join(ROOT, 'engine'), env: {...process.env, VEC_SORTIE: sortie, EDITEUR_LLM: '0', PYTHONIOENCODING: 'utf-8'}, encoding: 'utf8', windowsHide: true, timeout: 600000});
	const fin = (run.stderr || '').trim().split('\n').slice(-3).join(' | ');
	ok(run.status === 0, `moteur (style x5 x2 reels, sobriete, creatif, galerie, charte, ensure, refresh_ai) : ${fin}`);
	const res = fs.existsSync(sortie) ? JSON.parse(fs.readFileSync(sortie, 'utf8')) : {};
	fs.rmSync(sortie, {force: true});
	const attendu = {'tech-application': '#86B7FF', 'reel-impact': '#FFD400', documentaire: '#E0D4BE', hormozi: '#FFE34D', 'luxe-minimal': '#D8BC79'};
	let vus = 0;
	for (const [cas, r] of Object.entries(res)) {
		const v = Object.fromEntries(r.vectors.map((x) => [x.id, x]));
		const style = cas.split(':')[1];
		const cm = V.vectorColors(r, v['v-manuel']);
		ok(eq(cm, MAIN), `${cas} : vecteur recolore a la main -> ${JSON.stringify(cm)}`);
		const cc = V.vectorColors(r, v['v-charte']);
		const want = cas.includes('charte') ? '#FF2D95' : attendu[style.replace('ensure-', '')];
		ok(cc.principale === want, `${cas} : vecteur « couleurs de la charte » suit la nouvelle palette (${cc.principale} / ${want})`);
		ok(V.vectorColors(r, v['v-verrou']).principale === want, `${cas} : vecteur verrouille, couleurs automatiques -> ${want}`);
		vus++;
	}
	ok(vus >= 13, `${vus} etats du moteur verifies`);
	ok(res['script2:charte'] && eq(V.vectorColors(res['script2:charte'], {couleurs: {principale: null, secondaire: null, contour: null}, couleursManuelles: false}),
		{principale: '#FF2D95', secondaire: '#7C3AED', contour: '#000000'}), 'charte du client (bandeau violet) : secondaire = fond du bandeau');
}

console.log(`\n${count - fails}/${count} verifications vecteurs reussies (${noms.length} SVG, ${recolores} multicolores recolores)`);
process.exit(fails ? 1 : 0);
