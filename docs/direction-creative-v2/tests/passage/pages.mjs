// Pages de sous-titres d'un reel, calculees par remotion/src/timeline.ts (celles de l'apercu et de l'export) :
//   node pages.mjs <reel.json>  ->  [{start, end, words: [[plan, indice]]}]
// Sert de reference aux tests de « Refaire seulement ce passage » (test-passage.py).
import fs from 'node:fs';
import {pages} from '../../../../remotion/src/timeline.ts';

const reel = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
process.stdout.write(JSON.stringify(pages(reel).map((p) => ({start: p.start, end: p.end, words: p.words.map((w) => [w.clip, w.index])}))));
