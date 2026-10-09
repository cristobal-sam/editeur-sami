// Tests du rendu (timeline.ts) pour les corrections du juge independant n° 2 (2 octobre 2026) :
//   node docs/qualite-2026-09-30/tests/test-juge2.mjs
// Donnee FIGEE : cas/juge2-p3d.json (Video 1 en Tech 3D cinematique apres ce cycle : detourage RVM, analyse du decor v6 avec
// le haut reel de la tete, table reprise sur la prise c4, fin tenue ; jamais un projet vivant).
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const ICI = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(ICI, '../../..');
const T = await import(pathToFileURL(path.join(ROOT, 'remotion/src/timeline.ts')).href);
const base = JSON.parse(fs.readFileSync(path.join(ICI, 'cas/juge2-p3d.json'), 'utf8'));
const copie = () => JSON.parse(JSON.stringify(base));
let ok = 0, n = 0;
const verifier = (nom, cond, detail = '') => {
	n += 1;
	if (cond) ok += 1;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${nom}${detail ? ' — ' + detail : ''}`);
};
const texte = (p) => p.words.map((w) => w.w).join(' ');

// ---------- bande noire du haut : le décor couvre toujours le cadre pendant la bascule ----------
{
	const r = copie();
	const segs = T.videoSegments(r);
	let pire = -1e9, vues = 0, avec = 0;
	for (let t = 0; t < T.duration(r); t += 1 / 30) {
		const v = T.studioView(r, segs[T.segmentAt(segs, t)], t);
		if (!v) continue;
		vues += 1;
		if (v.dy) avec += 1;
		const s = T.studioDecorScale(r, v);
		// bord haut du décor (px) : centre à mi-hauteur, échelle s, puis décalé de 0,3·dy
		pire = Math.max(pire, (r.height / 2) * (1 - s) + 0.3 * (v.dy ?? 0) * r.height);
	}
	verifier('bascule : le décor couvre le haut de l’image à chaque image (bord haut <= 0 px)', vues > 0 && avec > 0 && pire <= 0,
		`${avec} images basculées, bord ${pire.toFixed(1)} px`);
	// cas de contrôle (export jugé : bascule sans agrandissement) : parallaxe seule = bande de 58 px ; avec la correction, couvert
	const v = {scale: 1, ox: 0.5, oy: 0.94, bg: 1, dy: 0.1};
	verifier('bascule sans agrandissement : bande de l’ancien calcul, couverte par le nouveau', 0.3 * v.dy * r.height > 50
		&& (r.height / 2) * (1 - T.studioDecorScale(r, v)) + 0.3 * v.dy * r.height <= 0);
}

// ---------- caméra : haut réel de la tête, pas de recul mécanique, coupes qui changent de plan, appel final ----------
{
	const r = copie();
	const segs = T.videoSegments(r);
	const c5 = r.cutouts.c5;
	verifier('haut de la tête mesuré dans le détourage (piste head)', Array.isArray(c5.head) && c5.head.length > 50
		&& Math.abs(T.cutoutHeadTop(c5, c5.head[3][0]) - c5.head[3][1]) < 1e-9);
	const sans = copie();
	for (const m of Object.values(sans.cutouts)) delete m.head;
	const a = T.studioPersonAt(r, segs, 65), b = T.studioPersonAt(sans, T.videoSegments(sans), 65);
	verifier('appel final : la tête juste sous le badge (haut réel de la tête)', a.head >= 0.28 && a.head <= 0.36,
		`tête ${a.head.toFixed(3)} (estimation par le visage : ${b.head.toFixed(3)}), taille × ${(a.fw / b.fw).toFixed(2)}`);
	// recul en glissant de plus de 12 % en moins de 1,6 s sans coupe (même mesure que le contrôle)
	const cuts = segs.slice(1).map((s) => s.out_start);
	const vs = [];
	for (let x = 0; x < T.duration(r); x += 0.1) vs.push([x, T.studioView(r, segs[T.segmentAt(segs, x)], x)?.scale ?? 1]);
	const reculs = [];
	for (let i = 0; i < vs.length - 1;) {
		let j = i;
		while (j + 1 < vs.length && vs[j + 1][1] < vs[j][1] - 1e-4 && (vs[j][1] - vs[j + 1][1]) / vs[j][1] < 0.05) j++;
		if (j > i) {
			const rr = vs[j][1] / vs[i][1];
			if (rr <= 0.88 && vs[i][0] >= 1 && vs[j][0] - vs[i][0] <= 1.6 && !cuts.some((c) => c >= vs[i][0] - 1e-3 && c <= vs[j][0] + 1e-3)) reculs.push(vs[i][0].toFixed(1));
			i = j;
		} else i++;
	}
	verifier('aucun recul de caméra en glissant avant une carte (hors ouverture ; changement d’un coup sur une coupe ou un début de phrase)', !reculs.length, reculs.join(' '));
	const ratio = (c) => T.studioPersonAt(r, segs, c + 0.04).fw / T.studioPersonAt(r, segs, c - 0.04).fw;
	const cta = T.designScenes(r).filter((s) => s.kind === 'cta').pop();
	const dansCta = cuts.filter((c) => c > cta.at && c < cta.end);
	verifier('coupe pendant l’appel final : la taille change d’au moins x 1,15 (plan serré ancré sous le badge)',
		dansCta.length > 0 && dansCta.every((c) => ratio(c) >= 1.149 || ratio(c) <= 1 / 1.149), dansCta.map((c) => ratio(c).toFixed(3)).join(' '));
	verifier('chaque coupe change la taille à l’écran (x 1,12 au moins)', cuts.every((c) => ratio(c) >= 1.12 || ratio(c) <= 1 / 1.12),
		cuts.map((c) => ratio(c).toFixed(2)).join(' '));
	const tete = dansCta.map((c) => [T.studioPersonAt(r, segs, c - 0.04).head, T.studioPersonAt(r, segs, c + 0.04).head]);
	verifier('le plan serré de l’appel final garde la tête sous l’interface (même hauteur à 2 % près)', tete.every(([x, y]) => Math.abs(x - y) < 0.02),
		tete.map(([x, y]) => `${x.toFixed(3)}→${y.toFixed(3)}`).join(' '));
	const v0 = T.studioView(r, segs[0], 0), v1 = T.studioView(r, segs[0], 0.9);
	verifier('ouverture : 1re image serrée puis recul visible', v0.scale - v1.scale > 0.1, `${v0.scale.toFixed(3)} -> ${v1.scale.toFixed(3)}`);
}

// ---------- table de la prise c4 (caméra qui dérive) ----------
{
	const r = copie();
	const m = r.cutouts.c4;
	const debut = T.occluderAt(m, m.start), fin = T.occluderAt(m, m.end - 0.1);
	verifier('table reprise sur la prise c4 et suivie image par image (la caméra dérive)', !!m.occluder && m.occluderTrack?.length > 20 && !!debut && !!fin
		&& Math.abs(debut[0][0] - fin[0][0]) > 0.05, debut && fin ? `${JSON.stringify(debut[0])} -> ${JSON.stringify(fin[0])}` : '');
	verifier('sans piste : le polygone fixe', JSON.stringify(T.occluderAt({...m, occluderTrack: undefined}, m.start)) === JSON.stringify(m.occluder));
}

// ---------- sous-titres : pages coupées sur la ponctuation, expressions entières ----------
{
	const r = copie();
	const pg = T.pages(r).map(texte);
	verifier('« quoi que ce soit » jamais coupé', pg.some((p) => /quoi que ce soit/.test(p)) && !pg.some((p) => /quoi$/.test(p)));
	verifier('« pour régler ça, | ça veut dire » : coupure après la virgule', pg.some((p) => /ça,$/.test(p.trim())) && pg.some((p) => /^ça veut/.test(p)));
	const faibles = T.pages(r).filter((p, i, all) => {
		const last = p.words[p.words.length - 1];
		const next = all[i + 1];
		return next && next.words[0].clip === last.clip && !/[.!?…,;:]["»”)\]]*$/.test(last.w)
			&& /^(de|des|du|à|au|aux|et|ou|le|la|les|un|une|pour|par|sur|que|qui)$/i.test(last.w);
	}).map(texte);
	verifier('aucune page ne finit sur un petit mot qui annonce la suite', !faibles.length, faibles.join(' | '));
	const courtes = T.pages(r).filter((p) => p.words[p.words.length - 1].outEnd - p.words[0].outStart < 0.3).map(texte);
	verifier('aucune page éclair (< 0,3 s de parole)', !courtes.length, courtes.join(' | '));
}

// ---------- fin tenue, badge de preuve, liste centrée ----------
{
	const r = copie();
	const words = T.timedWords(r).filter((w) => !w.hide);
	const fin = T.duration(r) - words[words.length - 1].outEnd;
	verifier('fin tenue : au moins 0,6 s après le dernier mot', fin >= 0.6, `${fin.toFixed(2)} s`);
	const badge = T.designScenes(r).find((s) => s.kind === 'list' && T.listParts(s).length === 1);
	verifier('badge de preuve dit (« Formé par nos soins ») dans le long passage sans carte', !!badge && /form/i.test(badge.text) && badge.at > 41.7 && badge.end < 51.7,
		badge ? `${badge.text} ${badge.at.toFixed(2)}–${badge.end.toFixed(2)}` : '');
	const l = T.studioListLayout(['Salaire', 'Avantages sociaux', 'Vacances', 'Journées de maladie']);
	verifier('liste : largeur de chaque pilule fournie (rangée recentrée au fil des mots)', l.widths?.length === 4 && l.widths.every((x) => x > 0.1));
}

console.log(`\n${ok}/${n} vérifications réussies`);
process.exit(ok === n ? 0 : 1);
