// Prepare une COPIE ISOLEE de l'editeur pour regarder la choregraphie dans le vrai navigateur (jamais le vrai dossier).
//   node docs/direction-creative-v2/tests/choregraphie/bac-interface.mjs            -> cree / rafraichit le bac
//   node docs/direction-creative-v2/tests/choregraphie/bac-interface.mjs --nettoyer -> retire les jonctions (rmdir) et les medias copies
// Puis : node <bac>/app/server.mjs avec EDITEUR_PORT=18804, et ouvrir http://127.0.0.1:18804.
// Bac : runtime/cache/tmp/dcv2-choregraphie/interface/ — copies : serveur, interface compilee, styles, moteur, calcul du
// montage, Video 1 (projects/script1, reel avec la choregraphie du moteur) et SES medias optimises (copies, ~280 Mo).
// Jonctions EN LECTURE : runtime/venv (interpreteur), assets (polices, musiques). Nettoyage : rmdir des liens seulement.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = path.resolve(HERE, '../../../..');
const FIX = path.join(REAL, 'docs/direction-creative-v2/tests/fixtures'); // donnees figees des tests (jamais projects/)
const origine = (rel) => path.join(/^projects\/(?!_)/.test(rel) ? FIX : REAL, rel); // projects/<video> : copie figee ; _cache, assets... : dossier reel
const box = path.join(REAL, 'runtime/cache/tmp/dcv2-choregraphie/interface');
const B = (...p) => path.join(box, ...p);
const JONCTIONS = ['runtime/venv', 'assets'];

if (process.argv.includes('--nettoyer')) {
	for (const j of JONCTIONS) {
		try {
			fs.rmdirSync(B(j)); // le lien seulement, jamais sa cible
			console.log('jonction retiree', j);
		} catch (e) {
			console.log('jonction', j, ':', e.code);
		}
	}
	fs.rmSync(B('projects/_cache'), {recursive: true, force: true}); // copies des medias (vrais fichiers, pas des liens)
	console.log('medias copies retires');
	process.exit(0);
}

for (const d of ['app/ui', 'runtime/cache/tmp', 'media/entree', 'engine', 'remotion/src', 'projects/script1/reels', 'projects/_cache/optimises', 'projects/_cache/voix']) {
	fs.mkdirSync(B(d), {recursive: true});
}
const copy = (rel) => {
	fs.rmSync(B(rel), {recursive: true, force: true});
	fs.cpSync(origine(rel), B(rel), {recursive: true});
};
for (const rel of ['app/server.mjs', 'app/ui/index.html', 'app/ui/styles.css', 'app/dist', 'styles', 'engine/editeur', 'remotion/segments.mjs',
	'remotion/src/timeline.ts', 'remotion/src/types.ts', 'projects/script1/project.json']) copy(rel);
for (const j of JONCTIONS) if (!fs.existsSync(B(j))) fs.symlinkSync(path.join(REAL, j), B(j), 'junction');

const reel = JSON.parse(fs.readFileSync(path.join(FIX, 'projects/script1/reels/script.json'), 'utf8')); // lecture seule (copie figee)
for (const s of Object.values(reel.sources)) {
	for (const rel of [s.proxy, s.voice]) {
		if (rel && !fs.existsSync(B(rel))) fs.copyFileSync(path.join(REAL, rel), B(rel));
	}
}
const file = B('projects/script1/reels/script.json');
fs.writeFileSync(file, JSON.stringify(reel, null, 1));
// choregraphie produite par le moteur de la COPIE (comme « Créer la chorégraphie »)
const p = spawnSync(B('runtime/venv/Scripts/python.exe'), ['-m', 'editeur', 'choregraphie', B('projects/script1'), '--reel', 'script'],
	{cwd: B('engine'), encoding: 'utf8', env: {...process.env, EDITEUR_ROOT: box, EDITEUR_LLM: '0', PYTHONIOENCODING: 'utf-8'}});
console.log(p.status === 0 ? p.stdout.trim() : p.stderr);
console.log(`bac pret : ${box}\nserveur : EDITEUR_PORT=18804 node "${B('app/server.mjs')}"  puis http://127.0.0.1:18804`);
