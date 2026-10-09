// Bac ISOLE pour le controle de l'interface V2 dans un navigateur (port 18851 ; jamais le vrai dossier ni le port 8790).
//   node docs/direction-creative-v2/tests/integration/bac-navigateur.mjs        -> affiche BAC=… et SERVEUR=…, puis attend
//   (arret : creer le fichier <bac>/stop ; le serveur s'arrete et les jonctions sont retirees — le lien seulement)
// Bac : runtime/cache/tmp/dcv2-integration/navigateur-<hasard>/ : COPIES de app/server.mjs, de l'interface compilee, des
// styles, du moteur, de remotion/src + segments.mjs, de assets/banque (dates gardees : aucun recalcul), polices, textures,
// musiques, projects/script2 (project.json + medias optimises) ; le reel est le « reel complet » de l'integration (notes,
// dessins, banque, vecteurs, charte, choregraphie, verrous). JONCTIONS EN LECTURE : runtime/venv, tools, assets/sfx.
import fs from 'node:fs';
import path from 'node:path';
import {spawn, spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../../..');
const FIX = path.join(REAL, 'docs/direction-creative-v2/tests/fixtures'); // donnees figees des tests (jamais projects/)
const origine = (rel) => path.join(/^projects\/(?!_)/.test(rel) ? FIX : REAL, rel); // projects/<video> : copie figee ; _cache, assets... : dossier reel
const PORT = Number(process.env.BAC_PORT || 18851);
fs.mkdirSync(path.join(REAL, 'runtime/cache/tmp/dcv2-integration'), {recursive: true});
const box = fs.mkdtempSync(path.join(REAL, 'runtime/cache/tmp/dcv2-integration/navigateur-'));
const B = (...p) => path.join(box, ...p);
const copy = (rel) => {
	fs.mkdirSync(path.dirname(B(rel)), {recursive: true});
	fs.cpSync(origine(rel), B(rel), {recursive: true, preserveTimestamps: true});
};
const liens = [];
const lien = (rel) => {
	fs.mkdirSync(path.dirname(B(rel)), {recursive: true});
	fs.symlinkSync(path.join(REAL, rel), B(rel), 'junction');
	liens.push(B(rel));
};
const retirerLiens = () => {
	for (const l of liens) {
		try {
			fs.rmdirSync(l); // la jonction seulement, jamais sa cible
		} catch (e) {
			console.log(`Jonction a retirer a la main (rmdir) : ${l} (${e.message})`);
		}
	}
};
for (const d of ['runtime/cache/tmp', 'media/entree', 'livraisons', 'projects/script2/reels']) fs.mkdirSync(B(d), {recursive: true});
['app/server.mjs', 'app/ui/index.html', 'app/ui/styles.css', 'app/dist', 'styles', 'engine/editeur', 'remotion/src', 'remotion/segments.mjs',
	'assets/banque', 'assets/fonts', 'assets/overlays', 'assets/music/corporate.ogg', 'assets/music/tech.ogg', 'projects/script2/project.json'].forEach(copy);
for (const l of ['runtime/venv', 'tools', 'assets/sfx']) lien(l);
// le reel complet (meme construction que test-integration.py), ecrit DANS le bac
const py = spawnSync(path.join(REAL, 'runtime/venv/Scripts/python.exe'), ['-c', [
	'import json, sys',
	`sys.path.insert(0, ${JSON.stringify(HERE)})`,
	'from commun import complet, lire',
	"r, _ = complet(lire('projects/script2/reels/script.json'))",
	`open(${JSON.stringify(B('projects/script2/reels/script.json'))}, 'w', encoding='utf-8').write(json.dumps(r, ensure_ascii=False, indent=1))`,
].join('\n')], {cwd: path.join(REAL, 'engine'), encoding: 'utf8', env: {...process.env, EDITEUR_LLM: '0', PYTHONIOENCODING: 'utf-8'}});
if (py.status !== 0) {
	retirerLiens();
	throw new Error(`reel complet : ${py.stderr}`);
}
const reel = JSON.parse(fs.readFileSync(B('projects/script2/reels/script.json'), 'utf8'));
for (const s of Object.values(reel.sources)) for (const k of ['proxy', 'voice']) if (s[k] && fs.existsSync(path.join(REAL, s[k]))) copy(s[k]);
const log = fs.openSync(B('serveur.log'), 'w');
const child = spawn(process.execPath, [B('app/server.mjs')], {env: {...process.env, EDITEUR_PORT: String(PORT), EDITEUR_LLM: '0'},
	stdio: ['ignore', log, log], windowsHide: true});
console.log(`BAC=${box}\nSERVEUR=http://127.0.0.1:${PORT} (pid ${child.pid}) — arret : creer ${B('stop')}`);
const fin = (code = 0) => {
	try {
		child.kill();
	} catch {}
	setTimeout(() => {
		retirerLiens();
		console.log('serveur du bac arrete, jonctions retirees');
		process.exit(code);
	}, 600);
};
const veille = setInterval(() => {
	if (fs.existsSync(B('stop'))) {
		clearInterval(veille);
		fin(0);
	}
}, 500);
child.on('exit', (code) => {
	clearInterval(veille);
	console.log(`serveur du bac sorti (${code})`);
	fin(code ?? 0);
});
