// Faux render.mjs (copie de test seulement) : reste a l'etape « Montage de la voix » SANS progression, cree les fichiers
// temporaires a cote de la sortie (comme le vrai), IGNORE le fichier .stop et ne finit jamais : pour verifier le garde-fou
// proportionnel a la duree du montage, le nettoyage des fichiers temporaires et le message garde apres « Annuler ».
import fs from 'node:fs';
const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
process.stdout.write(JSON.stringify({stage: 'Montage de la voix'}) + '\n');
for (const ext of ['.image.mp4', '.fx.raw', '.voix.wav', '.mix.wav', '.final.mp4']) fs.writeFileSync(job.out + ext, 'temporaire');
setInterval(() => {}, 1000);
