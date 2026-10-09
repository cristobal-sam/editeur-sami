// Planche de controle visuel de la bibliotheque (agent « vecteurs ») : chaque SVG, insere en ligne par le VRAI code de
// remotion/src/vectors.tsx, en 4 etats : couleurs d'origine · charte (rose / violet / noir) · couleurs manuelles
// (bleu / marine / blanc) · a mi-trace. Ecrit runtime/cache/tmp/dcv2-vecteurs/planche.html (autonome, aucun fichier externe).
//   node docs/direction-creative-v2/tests/vecteurs/planche.mjs
import fs from 'node:fs';
import path from 'node:path';
import {TMP, VDIR, chargerVecteurs, lireFiche, lireSvg} from './charger.mjs';

const V = await chargerVecteurs();
const noms = fs.readdirSync(VDIR).filter((f) => f.endsWith('.svg')).map((f) => f.slice(0, -4));
const ETATS = [
	['Origine', {}],
	['Charte', V.colorVars({principale: '#FF2D95', secondaire: '#7C3AED', contour: '#000000'})],
	['À la main', V.colorVars({principale: '#00C2FF', secondaire: '#0A2A66', contour: '#FFFFFF'})],
	['Mi-tracé', {'--v-trace-1': '0.5', '--v-trace-2': '1', '--v-trace-3': '1'}],
];
const style = (o) => Object.entries(o).map(([k, v]) => `${k}:${v}`).join(';');
const cells = noms.map((n) => {
	const svg = V.prepareSvg(lireSvg(n), `p-${n}`);
	const f = lireFiche(n);
	return `<figure><figcaption><b>${f.nom}</b> <small>${n} · ${f.categorie} · ${svg.shapes} formes${svg.traits ? ` · ${svg.traits} traits/${svg.stages} ét.` : ''}${svg.boucle ? ` · ${svg.boucle}` : ''}</small></figcaption>
		<div class="row">${ETATS.map(([label, vars]) => `<div class="cell"><div class="box" style="${style(vars)}">${svg.markup}</div><span>${label}</span></div>`).join('')}</div></figure>`;
});
const html = `<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Planche vecteurs</title><style>
body{margin:0;padding:16px;background:#1b1c20;color:#ddd;font:13px Segoe UI,sans-serif}
main{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
figure{margin:0;background:#26272c;border:1px solid #333;border-radius:8px;padding:8px}
figcaption small{color:#999}
.row{display:flex;gap:6px;margin-top:6px}
.cell{flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;font-size:10px;color:#aaa}
.box{width:100%;height:92px;display:flex;align-items:center;justify-content:center;border-radius:6px;padding:6px;box-sizing:border-box;
background:linear-gradient(135deg,#5d6b7a,#a9b3bc 50%,#3d4650)}
.box svg{max-height:80px}
</style></head><body><main>${cells.join('\n')}</main></body></html>`;
fs.mkdirSync(TMP, {recursive: true});
const out = path.join(TMP, 'planche.html');
fs.writeFileSync(out, html);
console.log(out);
