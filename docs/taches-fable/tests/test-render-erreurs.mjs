// Verifications de remotion/render.mjs (correctif 4) : medias manquants detectes avant le rendu, erreurs Remotion
// traduites en francais. Aucun rendu lance. Depuis la racine : node docs/taches-fable/tests/test-render-erreurs.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const {mediaManquant, traduireErreur} = await import(path.join(ROOT, 'remotion', 'render.mjs').replace(/\\/g, '/').replace(/^([A-Za-z]):/, 'file:///$1:'));

let n = 0;
const ok = (cond, msg) => {
	assert.ok(cond, msg);
	n++;
	console.log('ok', msg);
};

// --- medias manquants ---
const reel = JSON.parse(fs.readFileSync(path.join(ROOT, 'projects', 'script1', 'reels', 'script.json'), 'utf8'));
ok(mediaManquant(reel) === null, 'montage complet : rien ne manque');

const copy = () => JSON.parse(JSON.stringify(reel));
let r = copy();
const first = r.clips[0].source;
r.sources[first].proxy = 'projects/_cache/optimises/inexistant-fable.mp4';
ok(mediaManquant(r) === `Le fichier de la prise « ${reel.sources[first].name} » est introuvable : clique « Refaire » dans la Révision.`, 'proxy manquant : message avec le nom de la prise');

r = copy();
r.sources[first].path = 'D:\\Tools\\editeur_sami\\media\\entree\\inexistant-fable.MP4';
ok(/^Le fichier de la prise « .+ » est introuvable/.test(mediaManquant(r)), 'rush d\'origine (path) manquant detecte');

r = copy();
r.sources[first].voice = 'projects/_cache/voix/inexistant-fable.m4a';
ok(/introuvable/.test(mediaManquant(r)), 'voix debruitee manquante detectee');

r = copy();
// une prise NON utilisee par le montage peut manquer sans bloquer l'export
const unused = Object.keys(r.sources).find((k) => !r.clips.some((c) => c.source === k) && !(r.broll ?? []).some((b) => b.source === k));
r.sources[unused].proxy = 'projects/_cache/optimises/inexistant-fable.mp4';
ok(mediaManquant(r) === null, `prise non utilisee (${unused}) manquante : ignoree`);

r = copy();
const bs = (r.broll ?? [])[0]?.source;
if (bs) {
	r.sources[bs].proxy = 'projects/_cache/optimises/inexistant-fable.mp4';
	ok(mediaManquant(r) === `Le fichier de la prise « ${reel.sources[bs].name} » est introuvable : clique « Refaire » dans la Révision.`, 'plan de coupe manquant detecte');
}

r = copy();
r.music = {enabled: true, mood: null, file: 'music/inexistante-fable.ogg', volume: 0.2};
ok(mediaManquant(r) === 'Le fichier de musique « music/inexistante-fable.ogg » est introuvable : clique « Refaire » dans la Révision.', 'musique manquante');
r.music.enabled = false;
ok(mediaManquant(r) === null, 'musique desactivee : non verifiee');

r = copy();
r.intro = {enabled: true, text: 'x', file: 'projects/script1/intros/inexistant-fable.webm', duration: 2.5};
ok(/titre d'ouverture « .+ » est introuvable/.test(mediaManquant(r)), 'intro manquante');

r = copy();
r.clips[0].angle = 'zz-inexistant';
ok(mediaManquant(r) === 'Le fichier de la prise « zz-inexistant » est introuvable : clique « Refaire » dans la Révision.', 'angle multicamera inconnu');

// --- traduction des erreurs Remotion ---
ok(traduireErreur('Timed out after 30000ms while setting up the headless browser. Something went wrong.') ===
	"Le moteur d'image n'a pas démarré à temps (ordinateur trop occupé ?) : relance « Je la prends ».", 'delai du navigateur traduit');
ok(traduireErreur('Error: Received a status code of 404 while downloading file http://127.0.0.1:5123/projects/_cache/optimises/HOOK%20(2)-e25af6a5.mp4. Does the file exist?') ===
	"Un fichier du montage est introuvable pendant l'export (HOOK (2)-e25af6a5.mp4) : clique « Refaire » dans la Révision.", '404 traduit avec le nom du fichier decode');
ok(traduireErreur('Export annule.') === 'Export annulé.', 'annulation avec accent');
const blocked = "L'export s'est bloqué à 3 % (rendu de l'image) : aucune image n'avançait depuis 240 s, il a été arrêté.";
ok(traduireErreur(blocked) === blocked, 'message de blocage garde tel quel');
ok(traduireErreur('ENOSPC: no space left on device') === 'ENOSPC: no space left on device', 'erreur inconnue gardee telle quelle');

console.log(`\n${n} verifications reussies`);
