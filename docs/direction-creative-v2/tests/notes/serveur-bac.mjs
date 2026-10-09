// Bac isole pour le controle VISUEL des notes et dessins dans le vrai lecteur (navigateur), port 18805.
//   node docs/direction-creative-v2/tests/notes/serveur-bac.mjs      (Ctrl+C ou arret du processus : fin)
// Copies seulement (aucune jonction) : app/server.mjs, interface compilee, styles, moteur, projects/script1 (reel + projet),
// medias optimises des plans 1 et 2, polices, musique du style, textures. Rien n'est ecrit dans le vrai dossier.
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {bac, origine} from './outils.mjs';

const PORT = Number(process.env.BAC_PORT || 18805);
const box = bac('navigateur');
const D = (...p) => path.join(box, ...p);
const copy = (rel) => {
	fs.mkdirSync(path.dirname(D(rel)), {recursive: true});
	fs.cpSync(origine(rel), D(rel), {recursive: true});
};
for (const d of ['runtime/cache/tmp', 'media/entree']) fs.mkdirSync(D(d), {recursive: true});
['app/server.mjs', 'app/ui/index.html', 'app/ui/styles.css', 'app/dist/app.js', 'styles', 'engine/editeur', 'projects/script1/project.json',
	'projects/script1/reels/script.json', 'assets/fonts', 'assets/overlays', 'assets/music/tech.ogg'].forEach(copy);
const reel = JSON.parse(fs.readFileSync(D('projects/script1/reels/script.json'), 'utf8'));
for (const c of reel.clips.slice(0, 2)) copy(reel.sources[c.source].proxy);
const log = fs.openSync(D('serveur.log'), 'w');
const child = spawn(process.execPath, [D('app/server.mjs')], {env: {...process.env, EDITEUR_PORT: String(PORT)}, stdio: ['ignore', log, log], windowsHide: true});
console.log(`Bac : ${box}\nServeur isole : http://127.0.0.1:${PORT} (pid ${child.pid})`);
const stop = () => {
	child.kill();
	process.exit(0);
};
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
child.on('exit', (code) => {
	console.log(`serveur arrete (${code})`);
	process.exit(0);
});
