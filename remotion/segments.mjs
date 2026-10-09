// Calcul du montage d'un reel en JSON (meme code que l'apercu et l'export) :
//   node segments.mjs <reel.json>  ->  {duration, video, audio, srt, pacing, events, words, pages}
import fs from 'node:fs';
import {audioSegments, duration, pacing, pages, sfxEvents, srt, timedWords, videoSegments} from './src/timeline.ts';

const reel = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const light = process.argv.includes('--duree');
process.stdout.write(JSON.stringify(light ? {duration: duration(reel)} : {
	duration: duration(reel),
	video: videoSegments(reel),
	audio: audioSegments(reel),
	srt: srt(reel),
	pacing: pacing(reel),
	events: sfxEvents(reel),
	words: timedWords(reel).map(({w, clip, index, outStart, outEnd, hl}) => ({w, clip, index, start: outStart, end: outEnd, hl})),
	// pages de sous-titres de l'aperçu et de l'export : le moteur Python (choregraphie, passage) les lit telles quelles
	pages: pages(reel).map((p) => ({start: p.start, end: p.end, words: p.words.map(({w, clip, index, outStart, outEnd, hl}) => ({w, clip, index, start: outStart, end: outEnd, hl}))})),
}));
