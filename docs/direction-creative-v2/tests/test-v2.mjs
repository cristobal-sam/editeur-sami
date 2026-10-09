// Tests OBLIGATOIRES des fonctions V2 (§9 de docs/PASSATION-CLAUDE-DIRECTION-CREATIVE-V2.md) + suites de regression,
// de bout en bout, toujours sur des COPIES (bacs runtime/cache/tmp/...) : jamais le vrai serveur 8790, jamais projects/.
//
//   node docs/direction-creative-v2/tests/test-v2.mjs              tout (≈ 12 min : exports courts un a la fois + interface)
//   node docs/direction-creative-v2/tests/test-v2.mjs --rapide     sans les exports ni l'interface (≈ 3 min)
//   node docs/direction-creative-v2/tests/test-v2.mjs --seulement=base,notes   (groupes : base, notes, banque, vecteurs,
//                                                                               choregraphie, passage, integration)
//
// Chaque etape lance un test existant (sa sortie reelle est gardee dans le bac) ; le tableau final dit, pour chacun des
// 11 tests obligatoires du §9, quelles etapes le prouvent et s'ils sont tous verts. Resultat aussi ecrit dans
// <bac>/resultats-v2.json. L'etape « interface » demarre un bac isole (port 18851) et un Chrome sans fenetre.
// IA locale coupee (EDITEUR_LLM=0) : aucun appel a Qwen, aucun telechargement.
// Donnees : copies FIGEES de Video 1, Video 2 et des anciens reels dans fixtures/projects/ (origine et empreintes :
// fixtures/provenance.json). Aucun test ne lit les projets vivants de l'utilisateur (projects/<video>) : il peut les
// retoucher, les changer de style ou les supprimer sans casser la suite. Les medias restent ceux, partages, de projects/_cache.
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../..');
const PY = path.join(ROOT, 'runtime', 'venv', 'Scripts', 'python.exe');
const TSC = path.join(ROOT, 'remotion', 'node_modules', 'typescript', 'bin', 'tsc');
const ENGINE = path.join(ROOT, 'engine');
const T = (...p) => path.join('docs', 'direction-creative-v2', 'tests', ...p);
const arg = (k) => process.argv.find((a) => a === k || a.startsWith(`${k}=`));
const RAPIDE = !!arg('--rapide');
const SEUL = arg('--seulement')?.split('=')[1]?.split(',').filter(Boolean) ?? null;

// meme environnement que runtime/env.sh : caches et temporaires dans le dossier du projet, IA locale coupee
const ENV = {...process.env, EDITEUR_ROOT: ROOT, EDITEUR_LLM: '0', PYTHONIOENCODING: 'utf-8', HF_HUB_OFFLINE: '1',
	TEMP: path.join(ROOT, 'runtime', 'cache', 'tmp'), TMP: path.join(ROOT, 'runtime', 'cache', 'tmp'),
	XDG_CACHE_HOME: path.join(ROOT, 'runtime', 'cache'), HF_HOME: path.join(ROOT, 'models', 'huggingface'),
	PATH: [path.join(ROOT, 'tools', 'ffmpeg', 'bin'), path.join(ROOT, 'runtime', 'venv', 'Scripts'), process.env.PATH].join(path.delimiter)};

const base = path.join(ROOT, 'runtime', 'cache', 'tmp', 'dcv2-integration');
fs.mkdirSync(base, {recursive: true});
const box = fs.mkdtempSync(path.join(base, 'test-v2-'));

// ---------------------------------------------------------------- etapes ----------------------------------------------------------------
// [id, groupe, titre, commande, arguments, dossier, lourd (export), motif de succes dans la sortie]
const node = (f, ...a) => [process.execPath, [f, ...a]];
const py = (f) => [PY, [path.join('..', f)]];
const ETAPES = [
	['build', 'base', 'Construction de l’interface (node app/build.mjs)', ...node('app/build.mjs'), ROOT, false, /Done/],
	['tsc', 'base', 'Types : tsc -p tsconfig.verif.json = 0 erreur', ...node(TSC, '-p', 'tsconfig.verif.json'), ROOT, false, null],
	['check-serveur', 'base', 'node --check app/server.mjs', ...node('--check', 'app/server.mjs'), ROOT, false, null],
	['check-mcp', 'base', 'node --check plugins/editeur-sami/mcp/serveur.mjs', ...node('--check', 'plugins/editeur-sami/mcp/serveur.mjs'), ROOT, false, null],
	['verification', 'base', 'Moteur : verification.py', ...py('docs/passation-2026-09-30/tests/verification.py'), ENGINE, false, /\bOK\b/],
	['galerie', 'base', 'Galerie : test-galerie.py', ...py('docs/galerie-styles/test-galerie.py'), ENGINE, false, /\bOK\b/],
	['creative', 'base', 'Cerveau créatif : test-creative.py', ...py('docs/cerveau-creatif-v2-2026-09-30/test-creative.py'), ENGINE, false, /CERVEAU CREATIF V2: OK/],
	['sobriete', 'base', 'Sobriété : test-sobriete.py', ...py('docs/corrections-2026-09-30/tests/test-sobriete.py'), ENGINE, false, /\bOK\b/],
	['timeline', 'base', 'Calcul du montage : test-timeline.mjs', ...node('docs/galerie-styles/test-timeline.mjs'), ROOT, false, /réussies|reussies/],
	['timeline-v2', 'base', 'Socle V2 : ancres, rectangle de la prise, 13 anciens reels (test-timeline-v2.mjs)', ...node(T('test-timeline-v2.mjs')), ROOT, false, /reussies/],
	['verrous', 'base', 'Socle V2 : verrous (test-verrous.py)', ...py(T('test-verrous.py')), ENGINE, false, /\bOK\b/],
	['serveur', 'base', 'Socle V2 : serveur isolé, champs, refus, routes (test-serveur.mjs)', ...node(T('test-serveur.mjs')), ROOT, false, /reussies/],
	['notes', 'notes', 'Notes : image exacte, ancres, 4 formats, plafonds (test-notes.mjs)', ...node(T('notes', 'test-notes.mjs')), ROOT, false, /reussies/],
	['notes-persistance', 'notes', 'Notes : serveur arrêté puis relancé (test-persistance.mjs)', ...node(T('notes', 'test-persistance.mjs')), ROOT, false, /reussies/],
	['notes-export', 'notes', 'Notes : absentes de 3 exports de 2 s (test-export.mjs)', ...node(T('notes', 'test-export.mjs')), ROOT, true, /reussies/],
	['banque', 'banque', 'Banque : catalogue, filtres, aperçus, parité moteur/interface (test-banque.py)', ...py(T('banque', 'test-banque.py')), ENGINE, false, /\bOK\b/],
	['banque-serveur', 'banque', 'Banque : routes et aperçus servis (test-serveur-banque.mjs)', ...node(T('banque', 'test-serveur-banque.mjs')), ROOT, false, /reussies/],
	['banque-export', 'banque', 'Banque : son, vecteur et modèle dans 4 exports de 3 s (test-export-banque.py)', ...py(T('banque', 'test-export-banque.py')), ENGINE, true, /\bOK\b/],
	['vecteurs', 'vecteurs', 'Vecteurs : 36 SVG, recoloration sans perte, animation (test-vecteurs.mjs)', ...node(T('vecteurs', 'test-vecteurs.mjs')), ROOT, false, /reussies/],
	['vecteurs-moteur', 'vecteurs', 'Vecteurs : passes automatiques et chartes (test-vecteurs-moteur.py)', ...py(T('vecteurs', 'test-vecteurs-moteur.py')), ENGINE, false, /\bOK\b/],
	['vecteurs-http', 'vecteurs', 'Vecteurs : serveur isolé, changement de style (test-http-vecteurs.mjs)', ...node(T('vecteurs', 'test-http-vecteurs.mjs')), ROOT, false, /reussies/],
	['vecteurs-export', 'vecteurs', 'Vecteurs : export de 3 s, couleurs mesurées (export-vecteurs.mjs)', ...node(T('vecteurs', 'export-vecteurs.mjs')), ROOT, true, /OK/],
	['choregraphie', 'choregraphie', 'Chorégraphie : moteur, verrous, sobriété (test-choregraphie.py)', ...py(T('choregraphie', 'test-choregraphie.py')), ENGINE, false, /\bOK\b/],
	['choreo', 'choregraphie', 'Chorégraphie : enveloppe de l’image (test-choreo.mjs)', ...node(T('choregraphie', 'test-choreo.mjs')), ROOT, false, /réussies|reussies/],
	['choreo-revue', 'choregraphie', 'Chorégraphie : correctifs de la revue (test-revue-rendu.mjs)', ...node(T('choregraphie', 'test-revue-rendu.mjs')), ROOT, false, /réussies|reussies|\d+\/\d+/],
	['choreo-serveur', 'choregraphie', 'Chorégraphie : route et versions (test-serveur-choregraphie.mjs)', ...node(T('choregraphie', 'test-serveur-choregraphie.mjs')), ROOT, false, /\d+\/\d+/],
	['choreo-rendu', 'choregraphie', 'Chorégraphie : images comparées + export de 4 s (test-rendu.mjs)', ...node(T('choregraphie', 'test-rendu.mjs')), ROOT, true, /réussies|reussies/],
	['passage', 'passage', 'Refaire ce passage : rien hors de la plage (test-passage.py)', ...py(T('passage', 'test-passage.py')), ENGINE, false, /\bOK\b/],
	['passage-http', 'passage', 'Refaire ce passage : de bout en bout par HTTP (test-http-passage.mjs)', ...node(T('passage', 'test-http-passage.mjs')), ROOT, false, /réussies|reussies/],
	['integration', 'integration', 'Intégration : un reel avec TOUTES les fonctions V2 (test-integration.py)', ...py(T('integration', 'test-integration.py')), ENGINE, false, /\bOK\b/],
	['integration-export', 'integration', 'Intégration : 4 exports courts, images, son, timecodes, planche (test-integration-export.py)', ...py(T('integration', 'test-integration-export.py')), ENGINE, true, /\bOK\b/],
	['interface', 'integration', 'Interface : bac isolé + Chrome sans fenêtre, vrais clics (test-interface.mjs)', ...node(T('integration', 'test-interface.mjs')), ROOT, true, /reussies/],
];

// ------------------------------------------------- les 11 tests obligatoires (§9) et leurs preuves -------------------------------------------------
const S9 = [
	['Une note revient à la bonne image après fermeture et réouverture de l’outil', ['notes', 'notes-persistance', 'integration', 'interface']],
	['Un dessin au crayon reste aligné en 9:16, 16:9, 4:5 et 1:1', ['notes', 'timeline-v2', 'integration']],
	['Notes et dessins absents d’un export normal', ['notes-export', 'integration-export']],
	['Un SVG multicolore se recolore sans perdre ses formes ni son animation', ['vecteurs', 'vecteurs-export', 'integration-export']],
	['Une charte recolore un modèle, puis une retouche manuelle reste', ['vecteurs-moteur', 'vecteurs-http', 'integration', 'integration-export']],
	['La banque filtre effets, sons, vecteurs et modèles, avec aperçu', ['banque', 'banque-serveur', 'banque-export', 'interface']],
	['La chorégraphie ne place jamais deux éléments concurrents au même moment', ['choregraphie', 'choreo', 'integration']],
	['Une retouche verrouillée survit à une passe de l’IA et à un changement de style', ['verrous', 'choregraphie', 'vecteurs-moteur', 'integration']],
	['« Refaire seulement ce passage » ne change rien avant ni après la plage', ['passage', 'passage-http', 'integration', 'interface']],
	['Les anciens reels sans les nouveaux champs fonctionnent', ['timeline-v2', 'verrous', 'serveur', 'integration']],
	['Aperçu court : images extraites regardées, son et timecodes vérifiés', ['integration-export', 'choreo-rendu', 'banque-export']],
];

// ---------------------------------------------------------------- execution ----------------------------------------------------------------
const lancer = ([id, , titre, exe, args, cwd, , motif]) => new Promise((resolve) => {
	const t0 = Date.now();
	const log = path.join(box, `${id}.log`);
	const out = fs.openSync(log, 'w');
	const p = spawn(exe, args, {cwd, env: ENV, windowsHide: true, stdio: ['ignore', out, out]});
	const limite = setTimeout(() => p.kill(), 30 * 60 * 1000); // filet : 30 min au plus par etape
	p.on('exit', (code) => {
		clearTimeout(limite);
		fs.closeSync(out);
		const texte = fs.readFileSync(log, 'utf8');
		const lignes = texte.trim().split(/\r?\n/).filter((l) => l.trim());
		// ligne la plus parlante : un bilan (« 57 verifications… », « Ran 9 tests », « OK »), sinon la derniere
		const bilan = [...lignes].reverse().find((l) => /reussies|réussies|verifications|vérifications|^Ran \d+|^OK|FAILED|ECHEC|Done|CERVEAU/.test(l)) ?? lignes.pop() ?? '';
		const echecs = (texte.match(/^ECHEC/gm) ?? []).length + (/^FAILED/m.test(texte) ? 1 : 0);
		const vert = code === 0 && echecs === 0 && (!motif || motif.test(texte));
		resolve({id, titre, code, vert, s: Math.round((Date.now() - t0) / 1000), bilan: bilan.trim().slice(0, 160), log});
	});
});

const choisies = ETAPES.filter((e) => (!SEUL || SEUL.includes(e[1]) || SEUL.includes(e[0])) && !(RAPIDE && e[6]));
console.log(`Tests V2 : ${choisies.length} etape(s)${RAPIDE ? ' (--rapide : sans exports)' : ''} — journaux dans ${box}\n`);
const res = new Map();
for (const e of choisies) {
	process.stdout.write(`… ${e[2]}\n`);
	const r = await lancer(e);
	res.set(r.id, r);
	console.log(`${r.vert ? 'OK   ' : 'ECHEC'} [${r.id}] ${r.s} s — ${r.bilan}${r.vert ? '' : ` (code ${r.code}, journal : ${r.log})`}`);
}

console.log('\n================ Tests obligatoires du §9 ================');
const s9 = S9.map(([quoi, preuves], i) => {
	const faites = preuves.filter((p) => res.has(p));
	const etat = !faites.length ? 'NON LANCE' : faites.every((p) => res.get(p).vert) ? (faites.length === preuves.length ? 'OK' : 'OK (partiel)') : 'ECHEC';
	console.log(`${String(i + 1).padStart(2)}. ${etat.padEnd(12)} ${quoi}  [${preuves.map((p) => (res.has(p) ? `${p}${res.get(p).vert ? '' : ' ✗'}` : `(${p})`)).join(', ')}]`);
	return {test: quoi, etat, preuves: faites.map((p) => ({etape: p, vert: res.get(p).vert, bilan: res.get(p).bilan}))};
});
const rouges = [...res.values()].filter((r) => !r.vert);
console.log(`\n${res.size - rouges.length}/${res.size} etapes vertes${rouges.length ? ` — en echec : ${rouges.map((r) => r.id).join(', ')}` : ''}`);
fs.writeFileSync(path.join(box, 'resultats-v2.json'), JSON.stringify({date: new Date().toISOString(), rapide: RAPIDE, etapes: [...res.values()], s9}, null, 1));
console.log(`Resultats : ${path.join(box, 'resultats-v2.json')}`);
process.exitCode = rouges.length ? 1 : 0;
