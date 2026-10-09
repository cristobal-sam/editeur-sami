// Tests du rendu (timeline.ts) pour les corrections du juge independant n° 1 (2 octobre 2026) :
//   node docs/qualite-2026-09-30/tests/test-juge1.mjs
// Donnee FIGEE : cas/juge1-p3d.json (Video 1 en Tech 3D cinematique, detourage RVM + analyse du decor ; jamais un projet vivant).
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const ICI = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(ICI, '../../..');
const T = await import(pathToFileURL(path.join(ROOT, 'remotion/src/timeline.ts')).href);
const base = JSON.parse(fs.readFileSync(path.join(ICI, 'cas/juge1-p3d.json'), 'utf8'));
const copie = () => JSON.parse(JSON.stringify(base));
let ok = 0, n = 0;
const verifier = (nom, cond, detail = '') => {
	n += 1;
	if (cond) ok += 1;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${nom}${detail ? ' — ' + detail : ''}`);
};
const pageDe = (reel, texte) => T.pages(reel).find((p) => p.words.map((w) => w.w).join(' ').toLowerCase().includes(texte.toLowerCase()));
const cache = (reel, p) => T.captionHidden(reel, (p.start + p.end) / 2);

// ---------- sous-titres pendant les interfaces ----------
{
	const r = copie();
	const scenes = T.designScenes(r);
	const notif = scenes.find((s) => s.kind === 'notification');
	const pn = T.pages(r).find((p) => p.start >= notif.at && p.end <= notif.end);
	verifier('sous-titres gardés pendant une notification (elle ne redit pas la phrase)', pn && !cache(r, pn), pn?.words.map((w) => w.w).join(' '));
	const liste = pageDe(r, 'des vacances');
	// 2 oct. 2026 (juge n° 2) : les pages coupent après la virgule (« pour régler ça, | ça veut dire ») et jamais sur un petit mot :
	// la phrase qui introduit la liste est maintenant la page « ça veut dire »
	const avant = pageDe(r, 'veut dire');
	verifier('page qui redit la liste masquée, la phrase qui l’introduit gardée', liste && cache(r, liste) && avant && !cache(r, avant));
	const cinq = pageDe(r, 'cinq fois moins cher');
	const payer = pageDe(r, 'que vous allez payer');
	verifier('« cinq fois moins cher » masqué sous le 5×, la page d’avant gardée', cinq && cache(r, cinq) && payer && !cache(r, payer));
	const bouton = T.pages(r).filter((p) => /savoir/i.test(p.words.map((w) => w.w).join(' ')));
	verifier('page « En savoir plus » masquée pendant le bouton', bouton.length && bouton.some((p) => cache(r, p)));
	const sans = copie();
	sans.design = {...sans.design, mode: undefined};
	verifier('style sans habillage : sous-titres jamais masqués', T.pages(sans).every((p) => !cache(sans, p)));
	let parole = 0, sansTexte = 0;
	for (const w of T.timedWords(r).filter((x) => !x.hide)) {
		parole += 1;
		if (T.pageAt(r, w.outStart + 0.02) && T.captionHidden(r, w.outStart + 0.02)) sansTexte += 1;
	}
	verifier('moins de 12 % des mots dits sans sous-titres', sansTexte / parole < 0.12, `${sansTexte}/${parole}`);
}

// ---------- zone du haut, place des cartes, fin de film ----------
{
	const r = copie();
	const u = Math.min(r.width, r.height);
	const hauts = T.designScenes(r).filter((s) => T.isStudioCard(r, s.kind)).map((s) => s.y - (T.studioCardSize(s.kind, s.text, s.secondary).h * u * s.scale) / r.height / 2);
	verifier('9:16 : haut de toute interface sous la barre du haut (>= 12 %)', hauts.every((h) => h >= 0.118), hauts.map((h) => h.toFixed(3)).join(' '));
	const cuts = T.videoSegments(r).slice(1).map((s) => s.out_start);
	const total = T.duration(r);
	const liste = T.designScenes(r).find((s) => s.kind === 'list');
	verifier('une interface qui finirait juste après une coupe sort sur la coupe', liste && cuts.some((c) => Math.abs(c - liste.end) < 1e-6), liste?.end.toFixed(2));
	const cta = T.designScenes(r).filter((s) => s.kind === 'cta').pop();
	verifier('dernier bouton : entre sur l’offre dite, le bouton sur son mot, tenu jusqu’à la fin', cta && cta.marks?.length === 1 && cta.marks[0] > cta.at + 2
		&& Math.abs(cta.end - total) < 0.05, cta ? `${cta.at.toFixed(2)} -> ${cta.marks?.[0]?.toFixed(2)} -> ${cta.end.toFixed(2)}` : '');
	const sfx = T.sfxEvents(r);
	verifier('studio : pas de whoosh sur une coupe sans mouvement ; clic quand le bouton rejoint l’offre',
		!sfx.some((e) => e.kind === 'transition') && sfx.some((e) => e.kind === 'bouton'));
	const sansStudio = copie();
	sansStudio.design = {...sansStudio.design, cinematic: false};
	verifier('hors studio : whoosh des coupes de parties gardé', T.sfxEvents(sansStudio).some((e) => e.kind === 'transition'));
	verifier('notification d’une ligne : gabarit de son contenu (0,234 u)', T.studioCardSize('notification', 'Réponse envoyée au lead').h === 0.234);
}

// ---------- caméra : coupes qui changent de plan, ouverture, bascule pour les interfaces ----------
{
	const r = copie();
	const segs = T.videoSegments(r);
	const taille = (t) => {
		const p = T.studioPersonAt(r, segs, t);
		return p ? p.fw : 0;
	};
	const ratios = segs.slice(1).map((s) => taille(s.out_start + 0.04) / Math.max(1, taille(s.out_start - 0.04)));
	const faibles = ratios.filter((x) => x > 1 / 1.12 && x < 1.12);
	verifier('chaque coupe change la taille de la personne à l’écran (x 1,12 au moins)', !faibles.length, ratios.map((x) => x.toFixed(2)).join(' '));
	const v0 = T.studioView(r, segs[0], 0), v1 = T.studioView(r, segs[0], 0.9);
	// 2 oct. 2026 (juge n° 2) : la poussée depuis le plan large ne se voyait pas ; la 1re image (la miniature) est SERRÉE et la
	// caméra recule vers le plan de l'accroche
	verifier('ouverture : 1re image serrée sur le visage, puis la caméra recule (mouvement visible)', v0 && v1 && v0.scale - v1.scale > 0.05, `${v0?.scale.toFixed(3)} -> ${v1?.scale.toFixed(3)}`);
	const cinq = (r.graphics ?? []).find((g) => g.kind === 'chiffre' && g.auto);
	const vc = cinq ? T.studioView(r, segs[T.segmentAt(segs, cinq.at + 1)], cinq.at + 1) : null;
	const spot = cinq ? T.studioGraphicSpot(r, cinq) : null;
	const p = cinq ? T.studioPersonAt(r, segs, cinq.at + 1) : null;
	const box = cinq ? T.studioMetricBox(...T.studioChiffreText(cinq)) : null;
	const bas = spot && box ? spot.y + (box.h * 1080 * spot.scale) / r.height / 2 : 1;
	verifier('5× : la caméra bascule (la personne descend) et la pilule tient au-dessus de la tête', vc && (vc.dy ?? 0) > 0 && p && bas <= p.head,
		`dy ${vc?.dy} bas ${bas.toFixed(3)} tête ${p?.head.toFixed(3)}`);
	// un dessin pose sur le visage (coordonnees de la prise) reste sur le visage a l'ecran pendant la bascule
	const t5 = cinq.at + 1;
	const sg = segs[T.segmentAt(segs, t5)];
	const f = T.framing(r, sg.source, T.segSrcTime(sg, t5), sg.src_in, sg.src_out);
	const rect = T.sourceRectAt(r, t5);
	const yEcran = rect ? T.sourceToOutput(rect, [0.5, (f.cy * r.height - f.top) / f.height])[1] : -1;
	verifier('dessins de révision : un point du visage reste sur le visage pendant la bascule', Math.abs(yEcran - p.fy) < 0.005, `${yEcran.toFixed(4)} / ${p.fy.toFixed(4)}`);
}

// ---------- chiffres, largeur des sous-titres ----------
{
	verifier('multiplicateur écrit après le nombre (5×)', T.studioChiffreText({props: {value: 5, prefix: '×', suffix: '', label: 'MOINS CHER'}})[0] === '5×'
		&& T.chiffreAffixes({props: {prefix: '$', suffix: ''}})[0] === '$');
	const r = copie();
	const larges = T.pages(r).map((p) => {
		const l = T.studioCaptionLayout(r, p);
		const em = p.words.reduce((s, w) => s + 0.2 + T.studioCaptionEm(T.displayWord(w.w, r.style.uppercase)), 0.2 * (p.words.length - 1));
		return l.lines > 1 ? 0 : (em * l.fontSize) / r.width;
	});
	verifier('sous-titres d’une ligne dans 80 % de la largeur (colonne de boutons à droite libre)', Math.max(...larges) <= 0.805, Math.max(...larges).toFixed(3));
	verifier('mots en couleur : sayTokens lit les chiffres dits', T.sayTokens('cinq fois moins cher').join(' ') === '5 x moin cher');
}

console.log(`\n${ok}/${n} vérifications réussies`);
process.exit(ok === n ? 0 : 1);
