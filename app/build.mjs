// Compile l'interface (React + lecteur Remotion) en un seul fichier : node app/build.mjs [--watch]
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MODULES = path.join(HERE, '..', 'remotion', 'node_modules');
const esbuild = createRequire(path.join(MODULES, 'x.js'))('esbuild');

const options = {
	entryPoints: [path.join(HERE, 'ui', 'App.tsx')],
	bundle: true,
	outfile: path.join(HERE, 'dist', 'app.js'),
	nodePaths: [MODULES],
	format: 'iife',
	jsx: 'automatic',
	target: 'es2022',
	minify: true,
	sourcemap: false,
	define: {'process.env.NODE_ENV': '"production"'},
	logLevel: 'info',
};
if (process.argv.includes('--watch')) await (await esbuild.context(options)).watch();
else await esbuild.build(options);
