// FAUX remotion/render.mjs (copie de test) : garde une copie du reel recu (pour verifier ce que l'export recoit), ecrit
// une fausse video, aucune image rendue.
import fs from 'node:fs';
import path from 'node:path';
const job = process.argv[2];
const data = JSON.parse(fs.readFileSync(job, 'utf8'));
const vus = path.resolve(path.dirname(job), '..', 'jobs-vus');
fs.mkdirSync(vus, {recursive: true});
fs.writeFileSync(path.join(vus, `${Date.now()}.json`), JSON.stringify(data));
console.log(JSON.stringify({stage: "Rendu de l'image", progress: 0.5}));
fs.mkdirSync(path.dirname(data.out), {recursive: true});
fs.writeFileSync(data.out, 'fausse video exportee');
console.log(JSON.stringify({stage: 'Fini', progress: 1}));
