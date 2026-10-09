// Tests de l'agent « notes » sans navigateur ni rendu : le VRAI app/ui/revue.tsx (compile pour Node) + timeline.ts.
//   node docs/direction-creative-v2/tests/notes/test-notes.mjs
// 1. timecodes mm:ss:ii ; 2. retour a l'image EXACTE (chaque image de 2 vrais reels et de 3 montages modifies) ;
// 3. note apres des coupes de mots avant elle, mot de la note coupe (« passage retiré ou modifié »), prise changee,
//    plan deplace, plan duplique ; 4. dessin aligne dans les 4 formats (meme pixel de la prise, calcul independant par la
//    transformation CSS de Reel.tsx) ; 5. fenetre d'affichage de 2 s a l'image pres ; 6. donnees acceptables par le serveur.
// Donnees : copies EN MEMOIRE des reels figes fixtures/projects/script1 et script2 (lecture seule, rien n'est ecrit).
import fsBase from 'node:fs';
import * as T from '../../../../remotion/src/timeline.ts';
import {bac, bilan, chargerRevue, lire, ok} from './outils.mjs';

const compile = bac('unitaires');
const R = await chargerRevue(compile);
// le module compile n'est qu'intermediaire (aucune jonction dans ce dossier) : retire a la fin
process.on('exit', () => fsBase.rmSync(compile, {recursive: true, force: true}));
const clone = (x) => structuredClone(x);
const script1 = lire('projects/script1/reels/script.json');
const script2 = lire('projects/script2/reels/script.json');
const SIZES = {'9:16': [1080, 1920], '16:9': [1920, 1080], '4:5': [1080, 1350], '1:1': [1080, 1080]};
const enFormat = (r, f) => ({...r, width: SIZES[f][0], height: SIZES[f][1]});
const fr = (r, t) => Math.round(t * r.fps);
const html = (el) => R.renderToStaticMarkup(el);
const props = (reel, t) => ({reel, t, format: '9:16', update: () => undefined, seek: () => undefined, pause: () => undefined, current: 'script1/script', reload: () => undefined});

// ---------- 1. timecodes ----------
ok(R.timecode(12.5, 30) === '00:12:15', `timecode 12,5 s a 30 i/s = ${R.timecode(12.5, 30)}`);
ok(R.timecode(0, 30) === '00:00:00' && R.timecode(61 + 29 / 30, 30) === '01:01:29' && R.timecode(59.999, 30) === '01:00:00', 'timecodes 00:00:00, 01:01:29, arrondi a l\'image 01:00:00');
ok(R.timecode(1, 25) === '00:01:00' && R.timecode(0.96, 25) === '00:00:24', 'timecodes a 25 i/s');

// ---------- 2. retour a l'image exacte : chaque image, 2 vrais reels + 3 montages modifies ----------
{
	const courts = clone(script1);
	// coupe de mots tres courts : les morceaux gardes se chevauchent dans la prise (piege pour un simple aller-retour)
	let coupes = 0;
	for (const c of courts.clips) {
		c.words.forEach((w, i) => {
			if (!w.cut && i > 0 && i < c.words.length - 1 && w.end - w.start < 0.2 && coupes < 6) {
				w.cut = true;
				coupes++;
			}
		});
	}
	const vite = clone(script1);
	vite.clips[2].speed = 1.25;
	vite.clips[0].tighten = !vite.clips[0].tighten;
	const deplace = clone(script2);
	deplace.clips.push(deplace.clips.shift());
	const cas = [['Video 1 (script1)', script1], ['script2', script2], [`Video 1, ${coupes} mots courts coupes`, courts], ['Video 1, plan accelere x1,25 + resserrage change', vite],
		['script2, plans deplaces', deplace]];
	for (const [nom, r] of cas) {
		const n = Math.round(T.duration(r) * r.fps);
		let bad = 0;
		let brut = 0;
		for (let f = 0; f < n; f++) {
			const note = R.newNote(r, f / r.fps, 'x', 'Sami', '9:16', new Date(0));
			// sauvegarde puis relecture : le JSON ne perd rien
			const relu = JSON.parse(JSON.stringify(note));
			const p = R.placeNote(r, relu);
			// App.seek : Math.round(s * fps)
			if (!p || Math.round(p.t * r.fps) !== f) bad++;
			const s = T.outputTimeOfAnchor(r, relu.anchor);
			if (s === null || Math.round(s * r.fps) !== f) brut++;
		}
		ok(bad === 0, `${nom} : ${n} notes (une par image) -> clic = retour a la meme image pour ${n - bad}/${n}${brut ? ` (ancre seule : ${brut} image(s) decalee(s) dans les chevauchements, corrigees par le temps verifie)` : ''}`);
	}
}

// ---------- 3. la note reste sur son passage quand le montage change ----------
{
	const r = clone(script1);
	const fps = r.fps;
	const c2 = r.clips[1];
	const k = c2.words.findIndex((w, i) => i >= 8 && !w.cut && w.start > c2.in + 1);
	const mot = (reel) => T.timedWords(reel).find((x) => x.clip === c2.id && x.index === k);
	const w0 = mot(r);
	const tNote = Math.round((w0.outStart + 3 / fps) * fps) / fps;
	const note = R.newNote(r, tNote, 'Coupe plus tôt ici 🎬, « vraiment »', 'Sami', '9:16');
	ok(note.anchor.clip === c2.id && note.anchor.source === c2.source && note.anchor.image === c2.source && note.contexte.format === '9:16'
		&& note.contexte.titre === r.title && note.contexte.style === r.template && note.statut === 'ouverte' && note.auteur === 'Sami',
	`note creee a ${R.timecode(tNote, fps)} : plan ${note.anchor.clip}, prise ${note.anchor.source}, contexte (titre, style ${note.contexte.style}, 9:16, ${note.contexte.duree} s), auteur Sami`);
	ok(typeof note.contexte?.phrase === 'string' && note.contexte.phrase.includes(w0.w) && !note.meta && R.phraseDe(note) === note.contexte.phrase, `souvenir du passage (contexte.phrase) : « ${note.contexte.phrase} »`);
	ok(R.phraseDe({...note, contexte: {...note.contexte, phrase: undefined}, meta: {phrase: 'ancienne note'}}) === 'ancienne note', 'ancienne note (meta.phrase) : souvenir du passage toujours lu');
	const decalage = tNote - w0.outStart;
	const verifie = (nom, reel, attendu) => {
		const p = R.placeNote(reel, note);
		const w = mot(reel);
		ok(!!p && !!w && Math.abs((p.t - w.outStart) - decalage) <= 1 / fps + 1e-9 && (attendu === undefined || Math.abs(p.t - attendu) <= 1 / fps + 1e-9),
			`${nom} : la note est a ${p ? R.timecode(p.t, fps) : 'null'}, toujours ${Math.round(decalage * fps)} images dans le mot « ${w?.w} »`);
		return p;
	};
	// 6 mots coupes dans le 1er plan (avant la note)
	const a = clone(r);
	a.clips[0].words.slice(2, 8).forEach((x) => (x.cut = true));
	const perdu = T.duration(r) - T.duration(a);
	ok(perdu > 0.3, `coupe de 6 mots dans le plan 1 : ${perdu.toFixed(3)} s retirees avant la note`);
	verifie('apres la coupe du plan 1', a, tNote - perdu);
	// 3 mots coupes dans le MEME plan, avant le mot de la note
	const b = clone(a);
	b.clips[1].words.slice(k - 6, k - 3).forEach((x) => (x.cut = true));
	const perdu2 = T.duration(a) - T.duration(b);
	ok(perdu2 > 0.1, `coupe de 3 mots du meme plan avant la note : ${perdu2.toFixed(3)} s de plus`);
	verifie('apres la coupe dans le meme plan', b, tNote - perdu - perdu2);
	// annuler les coupes : retour a l'image exacte d'origine
	const p0 = R.placeNote(clone(r), note);
	ok(p0 && fr(r, p0.t) === fr(r, tNote), `coupes annulees : la note revient a ${R.timecode(tNote, fps)} exactement`);
	// plan de la note deplace en tete
	const m = clone(r);
	m.clips.unshift(m.clips.splice(1, 1)[0]);
	verifie('plan de la note deplace en 1re position', m);
	// mot de la note coupe : orpheline, jamais deplacee en silence
	const g = clone(r);
	g.clips[1].words.slice(k - 1, k + 2).forEach((x) => (x.cut = true));
	ok(R.placeNote(g, note) === null, 'mot de la note coupe : note orpheline (null), pas de position de remplacement');
	const panel = html(R.createElement(R.NotesPanel, props({...g, notes: [note]}, 3)));
	ok(panel.includes('Passage retiré ou modifié') && panel.includes('Rattacher ici (00:03:00)'), 'panneau : « Passage retiré ou modifié » + bouton « Rattacher ici (00:03:00) »');
	const marks = html(R.createElement(R.NoteMarkers, {reel: {...g, notes: [note]}, x: (s) => s * 10, onSeek: () => undefined}));
	ok(!marks.includes('nt-mark '), 'timeline : aucun repere pour la note orpheline');
	const marks2 = html(R.createElement(R.NoteMarkers, {reel: {...a, notes: [note]}, x: (s) => s * 10, onSeek: () => undefined}));
	const left = Number(/left:([\d.]+)px/.exec(marks2)?.[1]);
	ok(Math.abs(left - R.placeNote(a, note).t * 10) < 1e-6, `timeline : repere a la nouvelle place (${left.toFixed(1)} px = ${R.timecode(R.placeNote(a, note).t, fps)})`);
	// autre prise pour ce plan : orpheline
	const pr = clone(r);
	pr.clips[1] = {...pr.clips[1], source: 'autre-prise', signature: 'autre-prise|0|9|true'};
	pr.sources['autre-prise'] = pr.sources[c2.source];
	ok(R.placeNote(pr, note) === null, 'prise du plan changee : note orpheline');
	// plan duplique puis original retire : retrouve ailleurs, signale
	const d = clone(r);
	d.clips.splice(1, 1, {...d.clips[1], id: 'c2-copie'});
	const pd = R.placeNote(d, note);
	ok(pd && !pd.exact, `plan remplace par une copie : note retrouvee dans l'autre plan (exact = false) a ${pd ? R.timecode(pd.t, fps) : '-'}`);
	ok(html(R.createElement(R.NotesPanel, props({...d, notes: [note]}, 0))).includes('Retrouvée dans un autre plan'), 'panneau : « Retrouvée dans un autre plan »');
	// panneau normal : timecode, statut, texte avec accents et emoji
	const normal = html(R.createElement(R.NotesPanel, props({...a, notes: [note]}, R.placeNote(a, note).t)));
	ok(normal.includes(`▶ ${R.timecode(R.placeNote(a, note).t, fps)}`) && normal.includes('Coupe plus tôt ici 🎬, « vraiment »') && normal.includes('Ouvertes (1)'),
		'panneau : timecode mis a jour, texte intact (accents, emoji), compteur « Ouvertes (1) »');
	ok(normal.includes('nt-card s-ouverte now'), 'panneau : la note sous la tete de lecture est mise en evidence');
	// temps en cache remis a jour a la prochaine modification des notes
	const [maj] = R.refreshTimes(a, [note]);
	ok(fr(a, maj.t) === fr(a, R.placeNote(a, note).t) && maj.anchor === note.anchor, 'refreshTimes : temps en cache recalcule, ancre inchangee');
	// note sur un passage (fin)
	const fin = {...note, end: tNote + 1, endAnchor: T.anchorAtTime(r, tNote + 1)};
	const pf = R.placeNote(a, fin);
	ok(pf && pf.end !== null && Math.abs(pf.end - pf.t - 1) <= 1 / fps + 1e-9, `note sur un passage : ${R.timecode(pf.t, fps)} -> ${R.timecode(pf.end, fps)} apres la coupe`);
}

// ---------- 4. dessin aligne dans les 4 formats ----------
{
	// variante avec zoom alterne (echelle != 1) pour eprouver aussi le zoom de l'image
	const zoome = clone(script1);
	delete zoome.design;
	zoome.zoom = {...zoome.zoom, auto: true, strength: 1.12, push: 0.05};
	for (const [nom, base] of [['Video 1 (style tech)', script1], ['Video 1 sans habillage, zoom 1,12 + poussee', zoome], ['script2', script2]]) {
		const segs = T.videoSegments(base);
		// plan impair de preference : zoom alterne x1,12 dans la variante sans habillage
		const seg = segs.find((s) => T.segLen(s) > 3 && s.index % 2 === 1) ?? segs.find((s) => T.segLen(s) > 3) ?? segs[0];
		const t = Math.round((seg.out_start + 1.4) * base.fps) / base.fps;
		// modele independant = SegmentVideo de Reel.tsx : image posee a framing(), puis scale(segmentZoom) autour de (cx, cy)
		const css = (r, [u, v]) => {
			const ss = T.videoSegments(r);
			const i = T.segmentAt(ss, t);
			const s = ss[i];
			const local = t - s.out_start;
			const tSrc = s.src_in + local * (s.speed ?? 1);
			const f = T.framing(r, s.source, tSrc, s.src_in, s.src_out);
			const k = T.segmentZoom(r, s, ss[i + 1], T.duration(r), local);
			const [ox, oy] = [f.cx * r.width, f.cy * r.height];
			return [ox + (f.left + u * f.width - ox) * k, oy + (f.top + v * f.height - oy) * k, k];
		};
		const s0 = segs[T.segmentAt(segs, t)];
		const face = T.subjectAt(base, s0.source, s0.src_in + (t - s0.out_start) * (s0.speed ?? 1), s0.src_in, s0.src_out);
		let pire = 0;
		let pireCercle = 0;
		let echelle = 1;
		for (const fd of Object.keys(SIZES)) {
			const rd = enFormat(base, fd);
			// cercle autour du visage + trait a main levee, dessines a l'ecran dans le format fd
			const [fx, fy] = css(rd, [face.cx, face.cy]);
			const c = [fx / rd.width, fy / rd.height];
			const cercle = R.newAnnotation(rd, t, {outil: 'cercle', couleur: '#FF00FF', epaisseur: 8, duree: 2}, [[c[0] - 0.08, c[1] - 0.05], [c[0] + 0.08, c[1] + 0.05]]);
			const trait = R.newAnnotation(rd, t, {outil: 'crayon', couleur: '#FFD400', epaisseur: 8, duree: 2},
				Array.from({length: 40}, (_, i) => [0.3 + i * 0.01, 0.6 + 0.05 * Math.sin(i / 4)]));
			for (const fs of Object.keys(SIZES)) {
				const rs = enFormat(base, fs);
				const [ex, ey, k] = css(rs, [face.cx, face.cy]);
				echelle = Math.max(echelle, k);
				const pc = T.annotationOutput(rs, cercle, t);
				const centre = [((pc[0][0] + pc[1][0]) / 2) * rs.width, ((pc[0][1] + pc[1][1]) / 2) * rs.height];
				pireCercle = Math.max(pireCercle, Math.hypot(centre[0] - ex, centre[1] - ey));
				// chaque point du trait : meme pixel de la prise que la transformation CSS de l'image
				const pt = T.annotationOutput(rs, trait, t, fs);
				trait.points.forEach((q, i) => {
					const [x, y] = css(rs, q);
					pire = Math.max(pire, Math.hypot(pt[i][0] * rs.width - x, pt[i][1] * rs.height - y));
				});
			}
		}
		ok(pireCercle < 0.5, `${nom} : cercle trace autour du visage dans chaque format -> centre sur le visage dans les 4 formats (16 cas, ecart max ${pireCercle.toFixed(4)} px)`);
		ok(pire < 0.5, `${nom} : trait a main levee, 40 points x 16 cas : meme pixel que l'image (ecart max ${pire.toFixed(4)} px, zoom jusqu'a x${echelle.toFixed(3)})`);
	}
	// meme dessin affiche apres un changement de format dans l'interface (width/height du reel) : points de la prise inchanges
	const r = clone(script1);
	const t = 20;
	const a = R.newAnnotation(r, t, {outil: 'fleche', couleur: '#0A84FF', epaisseur: 10, duree: 2}, [[0.2, 0.3], [0.5, 0.45]]);
	const allerRetour = Object.keys(SIZES).every((f) => {
		const rf = enFormat(r, f);
		const out = T.annotationOutput(rf, a, t);
		const rect = T.sourceRectAt(rf, t);
		return out.every((p, i) => Math.hypot(...T.outputToSource(rect, p).map((v, j) => v - a.points[i][j])) < 1e-9);
	});
	ok(allerRetour, 'fleche : ecran -> prise -> ecran exact dans les 4 formats');
	ok(a.points.every(([x, y]) => x === Math.round(x * 1e5) / 1e5 && y === Math.round(y * 1e5) / 1e5), 'points enregistres a 5 decimales (1/100 000 de la prise : < 0,02 px)');
}

// ---------- 5. fenetre d'affichage : 2 s a l'image pres, liee a sa prise ----------
{
	const r = clone(script1);
	const fps = r.fps;
	const segs = T.videoSegments(r);
	// dessin dans un plan APRES le 1er (la coupe du plan 1 doit le decaler)
	const seg = segs.find((s) => T.segLen(s) > 4 && s.clip !== r.clips[0].id);
	const f0 = Math.round((seg.out_start + 0.5) * fps);
	const a = R.newAnnotation(r, f0 / fps, {outil: 'crayon', couleur: '#FF00FF', epaisseur: 12, duree: R.DUREE_DESSIN}, [[0.4, 0.4], [0.45, 0.42], [0.5, 0.47]]);
	ok(a.duree === 2, 'duree par defaut d\'un dessin : 2 s');
	const vues = (reel, from, to) => {
		const spans = new Map([[a.id, R.annotationSpan(reel, a)]]);
		const out = [];
		for (let f = from; f <= to; f++) if (R.visibleDrawings(reel, [a], spans, f / fps).length) out.push(f);
		return out;
	};
	const v = vues(r, f0 - 10, f0 + 70);
	ok(v.length === 60 && v[0] === f0 && v[59] === f0 + 59, `visible exactement de ${R.timecode(f0 / fps, fps)} a ${R.timecode((f0 + 59) / fps, fps)} (60 images), cache avant et apres`);
	ok(!R.visibleDrawings(r, [{...a, masquee: true}], new Map([[a.id, R.annotationSpan(r, a)]]), f0 / fps).length, 'dessin masque : non affiche');
	// coupe avant : la fenetre suit (meme nombre d'images, decalee d'autant)
	const c = clone(r);
	c.clips[0].words.slice(2, 8).forEach((x) => (x.cut = true));
	const d = Math.round((T.duration(r) - T.duration(c)) * fps);
	const v2 = vues(c, f0 - d - 10, f0 - d + 70);
	ok(v2.length === 60 && Math.abs(v2[0] - (f0 - d)) <= 1, `apres une coupe de ${d} images avant : visible de ${R.timecode(v2[0] / fps, fps)} (60 images)`);
	// prise changee : jamais affiche de travers
	const p = clone(r);
	const cl = p.clips.find((x) => x.id === a.anchor.clip);
	cl.source = 'autre-prise';
	cl.signature = `autre-prise|${cl.in}|${cl.out}|true`;
	p.sources['autre-prise'] = p.sources[a.anchor.source];
	ok(vues(p, 0, Math.round(T.duration(p) * fps)).length === 0 && R.annotationSpan(p, a) === null, 'prise du plan changee : dessin jamais affiche (passage retire)');
	// lien avec une note : ajouter une note a cette image y joint les dessins libres (logique de NotesPanel.ajouter)
	const note = R.newNote(r, f0 / fps, 'Regarde ici', 'Sami', '9:16');
	ok(Math.round(R.annotationSpan(r, a)[0] * fps) === Math.round(R.placeNote(r, note).t * fps), 'le dessin et la note tombent sur la meme image (jointure automatique possible)');
}

// ---------- 6. donnees acceptables par le serveur (memes limites que validateV2) ----------
{
	const r = clone(script1);
	const beaucoup = Array.from({length: 5000}, (_, i) => [i / 5000, 0.5 + 0.2 * Math.sin(i / 50)]);
	const a = R.newAnnotation(r, 10, {outil: 'surligneur', couleur: 'pas une couleur', epaisseur: 999, duree: 0}, beaucoup);
	ok(a.points.length === 2000 && a.points[0][0] === 0 && a.points[1999][0] === 0.9998, `5000 points -> ${a.points.length} repartis regulierement (premier et dernier gardes)`);
	ok(a.couleur === '#FF3B30' && a.epaisseur === 200 && a.duree === 0.04, 'couleur invalide -> rouge ; epaisseur bornee a 200 ; duree >= 0,04 s');
	const loin = R.newAnnotation(r, 10, {outil: 'crayon', couleur: '#FFFFFF', epaisseur: 4, duree: 2}, [[-50, 80], [0.5, 0.5]]);
	ok(loin.points.flat().every((v) => v >= -2 && v <= 3), 'points hors image bornes a [-2, 3]');
	const longue = R.newNote(r, 5, 'é'.repeat(5000), '  ', '9:16');
	ok(longue.text.length === 2000 && longue.auteur === 'Sami' && /^[A-Za-z0-9_:.-]{1,120}$/.test(longue.id) && longue.cree.length <= 40, 'texte coupe a 2000, auteur vide -> « Sami », id et date valides');
	const ids = new Set(Array.from({length: 2000}, () => R.nouvelId('n')));
	ok(ids.size === 2000, '2000 identifiants tires a la suite : tous differents');
	const vide = {...r, clips: []};
	ok(R.newNote(vide, 0, 'x', 'Sami', '9:16') === null && R.newAnnotation(vide, 0, {outil: 'crayon', couleur: '#FFFFFF', epaisseur: 4, duree: 2}, [[0.5, 0.5]]) === null, 'montage vide : aucune note ni dessin cree');
	// ancien reel sans notes : panneau sans erreur, rien d'ajoute
	const ancien = clone(script2);
	delete ancien.notes;
	delete ancien.annotations;
	const p = html(R.createElement(R.NotesPanel, props(ancien, 0)));
	ok(p.includes('Aucune note pour l’instant') && !('notes' in ancien) && !('annotations' in ancien), 'ancien reel sans notes : panneau vide, reel inchange');
}

// ---------- 7. « Transformer en élément graphique » (fleche, cercle, surligneur -> vecteur de la banque) ----------
{
	const fs = await import('node:fs');
	const path = await import('node:path');
	const {ROOT} = await import('./outils.mjs');
	// la geometrie retenue correspond aux vrais SVG de l'agent vecteurs
	const svg = (n) => fs.readFileSync(path.join(ROOT, 'assets/banque/vecteurs', `${n}.svg`), 'utf8');
	const vb = (s) => s.match(/viewBox="([\d.\s]+)"/)[1].split(/\s+/).map(Number);
	const fl = svg('fleche');
	const xs = fl.match(/points="([^"]+)"/)[1].trim().split(/\s+/).map((p) => Number(p.split(',')[0]));
	const ce = svg('cercle');
	const su = svg('surligneur');
	const d = su.match(/d="M(\d+) [\d.]+ C[\d.\s]+ [\d.\s]+ (\d+) /);
	ok(vb(fl)[2] === R.VECTEURS_DESSIN.fleche.vb && Math.max(...xs) - Math.min(...xs) === R.VECTEURS_DESSIN.fleche.utile && vb(fl)[2] / 2 === (Math.max(...xs) + Math.min(...xs)) / 2
		&& vb(ce)[2] === R.VECTEURS_DESSIN.cercle.vb && / A98 98 /.test(ce) && R.VECTEURS_DESSIN.cercle.utile === 196
		&& vb(su)[2] === R.VECTEURS_DESSIN.surligneur.vb && d && Number(d[2]) - Number(d[1]) === R.VECTEURS_DESSIN.surligneur.utile,
	'geometrie de la conversion = vrais fichiers fleche.svg (queue 20 -> pointe 300 / 320), cercle.svg (rayon 98 / 240), surligneur.svg (22 -> 378 / 400)');
	for (const f of ['9:16', '16:9']) {
		const r = enFormat(clone(script1), f);
		const [W, H] = SIZES[f];
		const U = Math.min(W, H); // largeur des vecteurs : part du petit cote (vectors.tsx)
		const t = 20;
		const fleche = R.newAnnotation(r, t, {outil: 'fleche', couleur: '#0A84FF80', epaisseur: 10, duree: 3}, [[0.2, 0.7], [0.55, 0.35]]);
		const v = R.toVector(r, fleche, {entree: 'glisse-gauche', sortie: 'fondu'});
		// boite du vecteur comme vectors.tsx : largeur w*min(W, H), centre (x*W, y*H), rotation autour du centre
		const wpx = v.w * U;
		const rot = (v.rotation * Math.PI) / 180;
		const pt = (u) => [v.x * W + u * Math.cos(rot), v.y * H + u * Math.sin(rot)];
		const [queue, pointe] = [pt(((20 - 160) / 320) * wpx), pt(((300 - 160) / 320) * wpx)];
		const out = T.annotationOutput(r, fleche, t).map(([x, y]) => [x * W, y * H]);
		const e = Math.max(Math.hypot(queue[0] - out[0][0], queue[1] - out[0][1]), Math.hypot(pointe[0] - out[1][0], pointe[1] - out[1][1]));
		ok(e < 0.5 && v.asset === 'banque/vecteurs/fleche.svg' && v.couleurs.principale === '#0A84FF' && v.couleursManuelles && v.manual && Math.abs(v.at - t) < 1 / 30 && v.duration === 3
			&& v.anim.entree === 'glisse-gauche', `${f} : fleche -> vecteur ; queue et pointe du vecteur sur celles du dessin (ecart ${e.toFixed(3)} px), couleur, duree 3 s, manuel`);
		const cercle = R.newAnnotation(r, t, {outil: 'cercle', couleur: '#FF3B30', epaisseur: 8, duree: 2}, [[0.3, 0.3], [0.6, 0.5]]);
		const vc = R.toVector(r, cercle);
		const oc = T.annotationOutput(r, cercle, t).map(([x, y]) => [x * W, y * H]);
		const diam = (Math.abs(oc[1][0] - oc[0][0]) + Math.abs(oc[1][1] - oc[0][1])) / 2;
		ok(Math.abs((vc.w * U * 196) / 240 - diam) < 0.5 && Math.abs(vc.x * W - (oc[0][0] + oc[1][0]) / 2) < 0.5 && vc.rotation === 0,
			`${f} : cercle -> vecteur rond de meme centre et de meme diametre (${diam.toFixed(1)} px)`);
		const sur = R.newAnnotation(r, t, {outil: 'surligneur', couleur: '#FFD400', epaisseur: 36, duree: 2}, [[0.2, 0.62], [0.4, 0.6], [0.7, 0.61]]);
		const vs = R.toVector(r, sur);
		const os = T.annotationOutput(r, sur, t).map(([x, y]) => [x * W, y * H]);
		ok(Math.abs((vs.w * U * 356) / 400 - Math.hypot(os[2][0] - os[0][0], os[2][1] - os[0][1])) < 0.5, `${f} : surligneur -> vecteur de meme longueur`);
	}
	const r = clone(script1);
	const crayon = R.newAnnotation(r, 20, {outil: 'crayon', couleur: '#FF3B30', epaisseur: 8, duree: 2}, [[0.2, 0.2], [0.3, 0.3], [0.4, 0.2]]);
	ok(R.toVector(r, crayon) === null, 'crayon a main levee : pas de conversion (reste un dessin de revision)');
	const coupe = clone(r);
	const f = R.newAnnotation(r, 20, {outil: 'fleche', couleur: '#FF3B30', epaisseur: 8, duree: 2}, [[0.2, 0.2], [0.5, 0.5]]);
	coupe.clips.find((c) => c.id === f.anchor.clip).words.forEach((w) => (w.cut = true));
	ok(R.toVector(coupe, f) === null, 'dessin dont le passage est coupe : pas de conversion');
}

// ---------- 8. plafonds du serveur (relecture) : jamais un dessin de plus que validateV2 refuserait ----------
{
	const un = {points: Array.from({length: 2000}, () => [0.5, 0.5])};
	ok(R.dessinRefuse([], 2000) === '' && R.dessinRefuse(Array(99).fill(un), 2000) === '', 'plafonds : 100 dessins de 2000 points acceptes (200 000 points)');
	ok(/200|traits/.test(R.dessinRefuse(Array(100).fill(un), 1)), 'plafonds : 200 001 points refuses avec une phrase en francais (le serveur refuserait toute la sauvegarde)');
	ok(/500 dessins/.test(R.dessinRefuse(Array(500).fill({points: [[0, 0]]}), 1)), 'plafonds : 501e dessin refuse');
}

bilan('notes (unitaires)');
