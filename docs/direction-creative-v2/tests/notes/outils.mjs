// Outils communs des tests de l'agent « notes » : compile le VRAI app/ui/revue.tsx pour Node (esbuild du projet), bacs de
// test sous runtime/cache/tmp/notes-agent/ (jamais sur C:, jamais dans projects/), petites verifications.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(HERE, '../../../..');
const MODULES = path.join(ROOT, 'remotion', 'node_modules');
const esbuild = createRequire(path.join(MODULES, 'x.js'))('esbuild');

/** Nouveau bac de test unique : runtime/cache/tmp/notes-agent/<nom>-XXXXXX. */
export const bac = (nom) => {
	const base = path.join(ROOT, 'runtime', 'cache', 'tmp', 'notes-agent');
	fs.mkdirSync(base, {recursive: true});
	return fs.mkdtempSync(path.join(base, `${nom}-`));
};

/** Module ESM compile depuis app/ui/revue.tsx (+ React et le rendu serveur de react-dom, meme instance de React). */
export const chargerRevue = async (dir) => {
	const entry = path.join(dir, 'entree-revue.tsx');
	const revue = path.join(ROOT, 'app', 'ui', 'revue.tsx').replace(/\\/g, '/');
	fs.writeFileSync(entry, `export * from '${revue}';\nexport {createElement} from 'react';\nexport {renderToStaticMarkup} from 'react-dom/server';\n`);
	const outfile = path.join(dir, 'revue.mjs');
	await esbuild.build({entryPoints: [entry], bundle: true, outfile, format: 'esm', platform: 'node', target: 'node20', jsx: 'automatic',
		nodePaths: [MODULES], define: {'process.env.NODE_ENV': '"production"'}, logLevel: 'silent',
		// react-dom/server (CommonJS) charge des modules de Node : require disponible dans le module ESM
		banner: {js: "import {createRequire as __cr} from 'node:module'; const require = __cr(import.meta.url);"}});
	return import(pathToFileURL(outfile).href);
};

/** Donnees figees des tests (fixtures/projects) : « projects/... » y est lu, jamais dans les projets vivants de l'utilisateur. */
export const FIX = path.join(ROOT, 'docs/direction-creative-v2/tests/fixtures');
export const origine = (rel) => path.join(/^projects\/(?!_)/.test(rel) ? FIX : ROOT, rel);
export const lire = (rel) => JSON.parse(fs.readFileSync(origine(rel), 'utf8'));

let n = 0;
let fails = 0;
export const ok = (cond, msg) => {
	n++;
	if (!cond) fails++;
	console.log(`${cond ? 'OK   ' : 'ECHEC'} ${msg}`);
	return cond;
};
export const bilan = (quoi) => {
	console.log(fails ? `\n${fails} ECHEC(S) sur ${n} verifications ${quoi}` : `\n${n} verifications ${quoi} reussies`);
	process.exitCode = fails ? 1 : 0;
};
