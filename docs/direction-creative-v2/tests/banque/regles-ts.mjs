// Regles de l'interface (app/ui/banque.tsx), executees dans Node pour les comparer au moteur (engine/editeur/banque.py).
//   node regles-ts.mjs <catalogue.json> <cas.json> <sortie.json>
// cas = {filtres: [Filtres...], reels: {nom: ReelDoc}, ajouts: [{reel, id, at}], couleurs: [{reel, vecteur: VectorItem}]}
// Le bundle (esbuild, comme app/build.mjs) est ecrit a cote de <sortie.json> (bac de test), jamais dans le projet.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../../..');
const MODULES = path.join(ROOT, 'remotion', 'node_modules');
const esbuild = createRequire(path.join(MODULES, 'x.js'))('esbuild');
const [catFile, casFile, outFile] = process.argv.slice(2);
const bundle = path.join(path.dirname(outFile), 'banque-regles.mjs');
await esbuild.build({
	stdin: {contents: "export {filtrer, elementPourReel, formeTemplate, visible, poser} from './app/ui/banque.tsx';\n"
		+ "export {vectorColors} from './remotion/src/vectors.tsx';", resolveDir: ROOT, loader: 'ts'},
	bundle: true, platform: 'node', format: 'esm', outfile: bundle, nodePaths: [MODULES], jsx: 'automatic', target: 'node20',
	define: {'process.env.NODE_ENV': '"production"'}, logLevel: 'error',
	banner: {js: "import {createRequire as __cr} from 'node:module'; const require = __cr(import.meta.url);"},
});
const m = await import(pathToFileURL(bundle).href);
const cat = JSON.parse(fs.readFileSync(catFile, 'utf8'));
const cas = JSON.parse(fs.readFileSync(casFile, 'utf8'));
const byId = new Map(cat.entrees.map((e) => [e.id, e]));
const out = {
	filtres: (cas.filtres ?? []).map((f) => m.filtrer(cat.entrees, f).map((e) => e.id)),
	ajouts: (cas.ajouts ?? []).map(({reel, id, at}) => {
		const e = byId.get(id);
		const r = cas.reels[reel];
		try {
			const {champ, element} = m.elementPourReel(e, r, at);
			return {champ, element, forme: m.formeTemplate(e, r), visible: m.visible(e, r)};
		} catch (x) {
			return {erreur: String(x?.message ?? x)};
		}
	}),
	couleurs: (cas.couleurs ?? []).map(({reel, vecteur}) => m.vectorColors(cas.reels[reel], vecteur)),
};
fs.writeFileSync(outFile, JSON.stringify(out));
