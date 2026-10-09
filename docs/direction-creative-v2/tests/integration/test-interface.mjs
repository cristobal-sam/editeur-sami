// Controle de l'interface V2 de bout en bout, sans intervention : demarre le bac isole (bac-navigateur.mjs, port 18851),
// lance ui-integration.mjs (Chrome sans fenetre de Remotion), puis arrete le bac par son fichier « stop » (les jonctions
// sont retirees par bac-navigateur.mjs — le lien seulement) et efface les COPIES de medias du bac (captures gardees).
//   node docs/direction-creative-v2/tests/integration/test-interface.mjs
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const bac = spawn(process.execPath, [path.join(HERE, 'bac-navigateur.mjs')], {stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true});
let sortie = '';
bac.stdout.on('data', (d) => (sortie += d));
bac.stderr.on('data', (d) => (sortie += d));
const fini = new Promise((r) => bac.on('exit', r));
let box = null;
for (let k = 0; k < 240 && !box; k++) {
	box = /BAC=(.+)/.exec(sortie)?.[1]?.trim() ?? null;
	if (!box) await sleep(500);
}
if (!box) {
	console.log(`ECHEC bac non demarre :\n${sortie}`);
	process.exit(1);
}
console.log(`BAC=${box}`);
let code = 1;
try {
	for (let k = 0; k < 60; k++) {
		try {
			if ((await fetch('http://127.0.0.1:18851/api/v2')).ok) break;
		} catch {}
		await sleep(500);
	}
	const ui = spawn(process.execPath, [path.join(HERE, 'ui-integration.mjs'), box], {stdio: 'inherit', windowsHide: true});
	code = await new Promise((r) => ui.on('exit', r));
} finally {
	fs.writeFileSync(path.join(box, 'stop'), '');
	await Promise.race([fini, sleep(15000)]);
	process.stdout.write(sortie.split('\n').filter((l) => /arrete|Jonction/.test(l)).join('\n') + '\n');
	// plus aucune jonction dans le bac ? alors seulement, on efface les copies de medias (plusieurs centaines de Mo)
	const liens = ['runtime/venv', 'tools', 'assets/sfx'].filter((l) => {
		try {
			return fs.lstatSync(path.join(box, l)).isSymbolicLink();
		} catch {
			return false;
		}
	});
	if (liens.length) console.log(`Jonctions encore presentes (a retirer avec rmdir) : ${liens.join(', ')} — rien n'est efface`);
	else {
		fs.rmSync(path.join(box, 'projects', '_cache'), {recursive: true, force: true});
		console.log('copies de medias du bac effacees (captures gardees dans interface/)');
	}
}
process.exitCode = code;
