// Compile remotion/src/vectors.tsx (et ce qu'il importe) en un module Node, pour tester ses fonctions pures.
// Le fichier compile va dans runtime/cache/tmp/dcv2-vecteurs/ (jamais sur C:).
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(HERE, '../../../..');
export const TMP = path.join(ROOT, 'runtime', 'cache', 'tmp', 'dcv2-vecteurs');
export const VDIR = path.join(ROOT, 'assets', 'banque', 'vecteurs');
const MODULES = path.join(ROOT, 'remotion', 'node_modules');

export const chargerVecteurs = async () => {
	const esbuild = createRequire(path.join(MODULES, 'x.js'))('esbuild');
	fs.mkdirSync(TMP, {recursive: true});
	const out = path.join(TMP, `vectors-${process.pid}.mjs`);
	await esbuild.build({entryPoints: [path.join(ROOT, 'remotion', 'src', 'vectors.tsx')], bundle: true, outfile: out, platform: 'node',
		format: 'esm', jsx: 'automatic', target: 'node20', nodePaths: [MODULES], logLevel: 'error',
		define: {'process.env.NODE_ENV': '"production"'}});
	try {
		return await import(pathToFileURL(out).href);
	} finally {
		fs.rmSync(out, {force: true});
	}
};

/** Noms de la bibliotheque declares dans app/ui/vector-panel.tsx (VECTOR_LIBRARY). */
export const bibliotheque = () => {
	const src = fs.readFileSync(path.join(ROOT, 'app', 'ui', 'vector-panel.tsx'), 'utf8');
	const m = /export const VECTOR_LIBRARY = \[([\s\S]*?)\];/.exec(src);
	return [...m[1].matchAll(/'([a-z0-9-]+)'/g)].map((x) => x[1]);
};

export const lireSvg = (nom) => fs.readFileSync(path.join(VDIR, `${nom}.svg`), 'utf8');
export const lireFiche = (nom) => JSON.parse(fs.readFileSync(path.join(VDIR, `${nom}.json`), 'utf8'));
