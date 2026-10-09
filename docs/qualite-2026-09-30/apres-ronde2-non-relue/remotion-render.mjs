// Export final d'un reel : node render.mjs <job.json>
// job.json = {reel, out, frameRange?, format?}. Progression ecrite en lignes JSON sur stdout.
// 1) voix : reconstruite par FFmpeg depuis les rushs d'origine (J/L-cuts, vitesse, traitement, fond d'ambiance)
// 2) musique + bruitages : calcules ici (meme volume que l'apercu : src/timeline.ts), sans passe Remotion
// 3) image : Remotion, a partir des medias optimises (meme calcul que l'apercu)   4) mixage FFmpeg -> FINAL.mp4
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {makeCancelSignal, renderMedia, selectComposition} from '@remotion/renderer';
import {audioSegments, duration, musicVolume, segLen, sfxEvents, sfxFile, speech} from './src/timeline.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const FFMPEG = path.join(ROOT, 'tools', 'ffmpeg', 'bin', 'ffmpeg.exe');
const say = (o) => {
	try {
		process.stdout.write(JSON.stringify(o) + '\n');
	} catch {} // serveur parti : on continue (et on s'arrete proprement)
};
// Blocage : pendant le rendu de l'image, si la progression n'avance plus pendant ce temps, on arrete l'export
// (sinon il peut rester des heures a « 3 % » sans erreur). Remotion renvoie parfois la meme valeur en boucle :
// seule une valeur PLUS HAUTE compte comme une avance.
const BLOCAGE_MS = (Number(process.env.EDITEUR_BLOCAGE_S) || 240) * 1000;
const MIME = {'.mp4': 'video/mp4', '.webm': 'video/webm', '.ttf': 'font/ttf', '.ogg': 'audio/ogg', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.png': 'image/png',
	'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'};

// Debruitage de la voix (IA locale RNNoise) AVANT l'egalisation et la compression (sinon le compresseur remonte le
// bruit de 4 a 6 dB), puis un expandeur doux qui baisse ce qui reste entre les mots. Filet si le modele manque.
const RNN = path.join(ROOT, 'models', 'rnnoise', 'sh.rnnn');
const DENOISE = fs.existsSync(RNN) ? `arnndn=m='${RNN.replace(/\\/g, '/').replace(':', '\\:')}':mix=0.9` : 'afftdn=nr=12:nf=-40';
const EXPANDER = 'agate=threshold=0.015:ratio=2:range=0.1:attack=5:release=300:knee=4';
const LUFS = -14; // niveau final (YouTube, Spotify ; TikTok et Instagram n'en publient pas) ; crete vraie <= -1 dBTP

// Traitements de voix (chaine appliquee apres le montage de la voix)
export const VOICE_CHAINS = {
	naturel: 'highpass=f=80,deesser=i=0.4,acompressor=threshold=-20dB:ratio=2:attack=10:release=120:makeup=2',
	radio: 'highpass=f=90,equalizer=f=300:t=q:w=1:g=-2.5,equalizer=f=3500:t=q:w=1.2:g=3,deesser=i=0.5,acompressor=threshold=-22dB:ratio=3.5:attack=5:release=80:makeup=3',
	podcast: 'highpass=f=70,equalizer=f=150:t=q:w=1:g=2,equalizer=f=4500:t=q:w=1:g=2,deesser=i=0.4,acompressor=threshold=-21dB:ratio=2.5:attack=8:release=100:makeup=2',
	aucun: 'highpass=f=60',
};

const sourceHash = () => {
	const h = crypto.createHash('sha1');
	for (const f of fs.readdirSync(path.join(HERE, 'src')).sort()) h.update(f + fs.statSync(path.join(HERE, 'src', f)).mtimeMs);
	return h.digest('hex').slice(0, 12);
};

// Moteur graphique compile : un dossier PAR version du code (remotion-bundle-<empreinte>). Avant, un seul dossier etait
// efface puis reconstruit des que remotion/src changeait, meme si un autre export s'en servait encore.
const getBundle = async () => {
	const cache = path.join(ROOT, 'runtime', 'cache');
	const hash = sourceHash();
	const dir = path.join(cache, `remotion-bundle-${hash}`);
	// date du dernier usage : une version encore utilisee n'est jamais retiree par un autre export
	const used = () => {
		try {
			fs.utimesSync(dir, new Date(), new Date());
		} catch {}
		return dir;
	};
	if (fs.existsSync(path.join(dir, '.source-hash'))) return used();
	say({stage: 'Preparation du moteur graphique'});
	const tmp = `${dir}.${process.pid}.tmp`;
	fs.rmSync(tmp, {recursive: true, force: true});
	await bundle({entryPoint: path.join(HERE, 'src', 'index.ts'), outDir: tmp});
	fs.writeFileSync(path.join(tmp, '.source-hash'), hash);
	try {
		fs.renameSync(tmp, dir);
	} catch (e) {
		// un autre export vient de construire la meme version : on garde la sienne
		fs.rmSync(tmp, {recursive: true, force: true});
		if (!fs.existsSync(path.join(dir, '.source-hash'))) throw e;
	}
	cleanOldBundles(cache, dir);
	return used();
};
/** Anciennes versions du moteur graphique : retirees 2 h apres leur dernier usage (un export ne dure jamais autant). */
const cleanOldBundles = (cache, keep) => {
	try {
		for (const f of fs.readdirSync(cache)) {
			const p = path.join(cache, f);
			if (p === keep || !/^remotion-bundle(-[0-9a-f]{12})?(\.\d+\.tmp)?$/.test(f)) continue;
			if (Date.now() - fs.statSync(p).mtimeMs > 2 * 3600e3) fs.rmSync(p, {recursive: true, force: true});
		}
	} catch {}
};

/** Mini-serveur de fichiers (projets + ressources) le temps du rendu : aucune dependance a l'interface. */
const serveFiles = () =>
	new Promise((resolve) => {
		const allowed = [path.join(ROOT, 'projects'), path.join(ROOT, 'assets')];
		const server = http.createServer((req, res) => {
			const file = path.normalize(path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname)));
			if (!allowed.some((a) => file.startsWith(a)) || !fs.existsSync(file)) {
				res.writeHead(404);
				return res.end();
			}
			const size = fs.statSync(file).size;
			const headers = {'content-type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream', 'accept-ranges': 'bytes', 'access-control-allow-origin': '*'};
			const m = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || '');
			if (m && (m[1] || m[2])) {
				const start = m[1] ? Number(m[1]) : Math.max(0, size - Number(m[2]));
				const end = m[1] && m[2] ? Math.min(Number(m[2]), size - 1) : size - 1;
				res.writeHead(206, {...headers, 'content-length': end - start + 1, 'content-range': `bytes ${start}-${end}/${size}`});
				return fs.createReadStream(file, {start, end}).pipe(res);
			}
			res.writeHead(200, {...headers, 'content-length': size});
			fs.createReadStream(file).pipe(res);
		});
		server.listen(0, '127.0.0.1', () => resolve(server));
	});

const ffmpeg = (args) => {
	const r = spawnSync(FFMPEG, ['-v', 'error', '-y', ...args], {maxBuffer: 1 << 26});
	if (r.status !== 0) throw new Error(String(r.stderr).slice(-1200));
};

/** Changement de vitesse du son (atempo accepte 0,5 a 2 : on enchaine au besoin). */
const atempo = (speed) => {
	const out = [];
	let s = speed;
	while (s > 2) (out.push('atempo=2'), (s /= 2));
	while (s < 0.5) (out.push('atempo=0.5'), (s /= 0.5));
	out.push(`atempo=${s.toFixed(4)}`);
	return out.join(',');
};

/** Voix du montage, depuis les rushs d'origine (meilleure qualite que les medias optimises). */
export const buildVoice = (reel, out) => {
	const segs = audioSegments(reel);
	const total = duration(reel);
	const audio = reel.audio ?? {voice: 'naturel', roomTone: true, declip: false};
	if (!segs.length) {
		// montage sans voix (immobilier...) : piste muette, la musique fait tout
		return ffmpeg(['-f', 'lavfi', '-t', total.toFixed(3), '-i', 'anullsrc=r=48000:cl=stereo', '-c:a', 'pcm_s16le', out]);
	}
	const args = [];
	const parts = [];
	segs.forEach((s, i) => {
		const d = s.src_out - s.src_in;
		const od = segLen(s);
		const tempo = s.speed && s.speed !== 1 ? `${atempo(s.speed)},` : '';
		args.push('-ss', s.src_in.toFixed(3), '-t', d.toFixed(3), '-i', reel.sources[s.source].path);
		parts.push(`[${i}:a]${tempo}aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=${s.fadeIn},afade=t=out:st=${Math.max(0, od - s.fadeOut).toFixed(3)}:d=${s.fadeOut},adelay=${Math.round(s.out_start * 1000)}:all=1[p${i}]`);
	});
	// un peu de silence en plus pendant le traitement, recoupe ensuite a la duree exacte : RNNoise rend une trame
	// invalide (NaN) sur la trame incomplete de la fin, qui casserait la normalisation
	let mix = `${segs.map((_, i) => `[p${i}]`).join('')}amix=inputs=${segs.length}:normalize=0:duration=longest,apad,atrim=0:${(total + 0.2).toFixed(3)}`;
	const clean = audio.denoise !== false && audio.voice !== 'aucun';
	// -4 dB avant RNNoise : des cretes au-dela du plein niveau (+3 dB dans certains rushs) le font deborder (plantage)
	const chain = [audio.declip ? 'adeclip' : '', clean ? `volume=-4dB,${DENOISE}` : '', VOICE_CHAINS[audio.voice] ?? VOICE_CHAINS.naturel, clean ? EXPANDER : '']
		.filter(Boolean).join(',');
	// voix a -16 LUFS : le niveau final (-14) est regle apres le mixage avec la musique et les bruitages
	const tone = audio.roomTone && !reel.music?.enabled && reel.sources[reel.clips[0]?.source]?.roomtone;
	if (tone) {
		// fond d'ambiance continu sous les coupes, seulement SANS musique (sinon il rajoute du bruit sous la musique) ;
		// mele apres le debruitage, tres bas
		args.push('-stream_loop', '-1', '-t', total.toFixed(3), '-i', path.join(ROOT, tone));
		parts.push(`${mix},${chain},atrim=0:${total.toFixed(3)},loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000[vx]`, `[${segs.length}:a]aresample=48000,aformat=channel_layouts=stereo,volume=0.25[rt]`,
			`[vx][rt]amix=inputs=2:normalize=0:duration=first[voice]`);
	} else {
		parts.push(`${mix},${chain},atrim=0:${total.toFixed(3)},loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000[voice]`);
	}
	ffmpeg([...args, '-filter_complex', parts.join(';'), '-map', '[voice]', '-c:a', 'pcm_s16le', out]);
};

/** Niveau integre (LUFS, EBU R128) d'un fichier son. */
export const loudness = (file) => {
	const r = spawnSync(FFMPEG, ['-hide_banner', '-nostats', '-i', file, '-af', 'ebur128', '-f', 'null', '-'], {encoding: 'utf8', maxBuffer: 1 << 26});
	const all = [...String(r.stderr).matchAll(/I:\s+(-?[\d.]+) LUFS/g)];
	const v = all.length ? Number(all[all.length - 1][1]) : NaN;
	return Number.isFinite(v) && v > -70 ? v : LUFS; // silence : pas de correction
};

const SR = 48000;
/** Son decode en PCM stereo 48 kHz (float). */
const decode = (file, seconds, loop = false, filter = '') => {
	const args = [FFMPEG, ...(loop ? ['-stream_loop', '-1'] : []), '-v', 'error', '-i', file, ...(seconds ? ['-t', seconds.toFixed(3)] : []),
		...(filter ? ['-af', filter] : []), '-ac', '2', '-ar', String(SR), '-f', 'f32le', '-'];
	const r = spawnSync(args[0], args.slice(1), {maxBuffer: 1 << 30});
	if (r.status !== 0) throw new Error(String(r.stderr).slice(-600));
	return new Float32Array(r.stdout.buffer, r.stdout.byteOffset, r.stdout.byteLength / 4);
};

/** Musique + bruitages, calcules directement (memes volumes que l'apercu : musicVolume, sfxEvents).
 *  Remplace l'ancienne passe audio de Remotion (qui rejouait toutes les images pour rien). */
export const buildFx = (reel, out) => {
	const total = duration(reel);
	const n = Math.ceil(total * SR);
	const mix = new Float32Array(n * 2);
	const fps = reel.fps;
	if (reel.music?.enabled && reel.music.file) {
		// creux vers 1,8 kHz : la musique laisse la place a la voix (intelligibilite) sans baisser encore son volume
		const music = decode(path.join(ROOT, 'assets', reel.music.file), total, true, 'equalizer=f=1800:t=q:w=1:g=-4');
		const ranges = speech(reel);
		const frames = Math.ceil(total * fps) + 1;
		const vol = Float32Array.from({length: frames + 1}, (_, f) => musicVolume(reel, f / fps, ranges, total));
		for (let i = 0; i < n && i * 2 + 1 < music.length; i++) {
			const x = (i / SR) * fps;
			const f = Math.floor(x);
			const v = vol[f] + (vol[Math.min(frames, f + 1)] - vol[f]) * (x - f);
			mix[i * 2] += music[i * 2] * v;
			mix[i * 2 + 1] += music[i * 2 + 1] * v;
		}
	}
	const cache = new Map();
	for (const e of sfxEvents(reel)) {
		const file = path.join(ROOT, 'assets', sfxFile(e.name));
		if (!fs.existsSync(file)) continue;
		if (!cache.has(file)) cache.set(file, decode(file, 3));
		const s = cache.get(file);
		const at = Math.max(0, Math.round(Math.round(e.t * fps) / fps * SR));
		for (let i = 0; i * 2 + 1 < s.length && at + i < n; i++) {
			mix[(at + i) * 2] += s[i * 2] * e.volume;
			mix[(at + i) * 2 + 1] += s[i * 2 + 1] * e.volume;
		}
	}
	fs.writeFileSync(out, Buffer.from(mix.buffer));
	return Boolean(reel.music?.enabled || (reel.sfx?.enabled && sfxEvents(reel).length));
};

const REFAIRE = 'clique « Refaire » dans la Révision.';
/** Avant le rendu : chaque media du montage doit exister. Sinon Remotion echoue en anglais (404 ou delai du navigateur),
 * longtemps apres avoir lance Chrome. Renvoie le message pour l'utilisateur, ou null si tout est la. */
export const mediaManquant = (reel) => {
	const exists = (p) => {
		try {
			return fs.existsSync(path.isAbsolute(p) ? p : path.join(ROOT, p));
		} catch {
			return false;
		}
	};
	const prise = (nom) => `Le fichier de la prise « ${nom} » est introuvable : ${REFAIRE}`;
	// sources utilisees : plans (et leur angle multicamera) + plans de coupe
	const used = new Set();
	for (const c of reel.clips ?? []) {
		used.add(c.source);
		if (c.angle) used.add(c.angle);
	}
	for (const b of reel.broll ?? []) used.add(b.source);
	for (const id of used) {
		const s = reel.sources?.[id];
		if (!s) return prise(id);
		for (const p of [s.proxy, s.path, s.voice, s.roomtone]) if (p && !exists(p)) return prise(s.name || id);
	}
	if (reel.music?.enabled && reel.music.file && !exists(path.join('assets', reel.music.file))) return `Le fichier de musique « ${reel.music.file} » est introuvable : ${REFAIRE}`;
	if (reel.intro?.enabled && reel.intro.file && !exists(reel.intro.file)) return `Le fichier du titre d'ouverture « ${reel.intro.file} » est introuvable : ${REFAIRE}`;
	return null;
};

/** Erreurs connues de Remotion, traduites pour l'utilisateur (le texte brut est garde dans le journal du serveur). */
export const traduireErreur = (raw) => {
	if (/Timed out after \d+ms while setting up the headless browser/.test(raw)) {
		return "Le moteur d'image n'a pas démarré à temps (ordinateur trop occupé ?) : relance « Je la prends ».";
	}
	const m = /status code of 404 while downloading file (\S+)/.exec(raw);
	if (m) {
		let nom = m[1].replace(/[.,;:!?)]+$/, '');
		try {
			nom = decodeURIComponent(new URL(nom).pathname);
		} catch {}
		return `Un fichier du montage est introuvable pendant l'export (${path.basename(nom)}) : ${REFAIRE}`;
	}
	if (raw === 'Export annule.') return 'Export annulé.';
	return raw;
};
/** Journal du serveur (runtime/cache/erreurs-serveur.log) : une ligne datee avec le texte brut de l'erreur. */
const journalBrut = (job, raw) => {
	try {
		const line = `${new Date().toISOString()} export ${path.basename(job.out)} : erreur brute : ${String(raw).replace(/\s+/g, ' ').slice(0, 1500)}\n`;
		fs.appendFileSync(path.join(ROOT, 'runtime', 'cache', 'erreurs-serveur.log'), line);
	} catch {}
};

const main = async () => {
	const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
	const reel = job.reel;
	// medias manquants : message en francais tout de suite, sans lancer Chrome ni creer de fichier temporaire
	const manque = mediaManquant(reel);
	if (manque) {
		say({error: manque});
		process.exitCode = 1;
		return;
	}
	const server = await serveFiles();
	const origin = `http://127.0.0.1:${server.address().port}`;
	// final : la video complete est ecrite ici puis renommee en job.out quand FFmpeg a fini (jamais de FINAL a moitie ecrit)
	const tmp = {video: job.out + '.image.mp4', fx: job.out + '.fx.raw', voice: job.out + '.voix.wav', mix: job.out + '.mix.wav', final: job.out + '.final.mp4'};
	// Annulation : le serveur cree <job>.stop (sous Windows, tuer le processus laisserait Chrome ouvert)
	let cancelled = false;
	let blocked = null; // message si l'export a ete arrete parce qu'il ne progressait plus
	let rendering = false;
	let best = 0;
	let lastAdvance = Date.now();
	const {cancelSignal, cancel} = makeCancelSignal();
	const watch = setInterval(() => {
		if (!cancelled && fs.existsSync(process.argv[2] + '.stop')) (cancelled = true), cancel();
		if (!cancelled && rendering && Date.now() - lastAdvance > BLOCAGE_MS) {
			const s = Math.round((Date.now() - lastAdvance) / 1000);
			blocked = `L'export s'est bloqué à ${Math.round(100 * (0.03 + best * 0.94))} % (rendu de l'image) : aucune image n'avançait depuis ${s < 90 ? `${s} s` : `${Math.round(s / 60)} min`}, `
				+ "il a été arrêté. Relance « Je la prends ». Si ça recommence, ferme les logiciels lourds (IA, Blender, jeux) puis réessaie.";
			cancelled = true;
			cancel();
		}
	}, 300);
	try {
		say({stage: 'Montage de la voix'});
		buildVoice(reel, tmp.voice);
		say({stage: 'Musique et bruitages', progress: 0.02});
		const withFx = buildFx(reel, tmp.fx);
		if (cancelled) throw new Error('annule');
		const serveUrl = await getBundle();
		// notes et dessins de revision : jamais lus par la composition (SPEC V2) ; retires ici pour ne pas envoyer jusqu'a
		// 200 000 points a chaque onglet Chrome de l'export
		const {notes: _notes, annotations: _annotations, ...image} = reel;
		const props = (audio) => ({reel: image, audio, mediaBase: origin, assetBase: `${origin}/assets`});
		const composition = await selectComposition({serveUrl, id: 'Reel', inputProps: props('none')});
		say({stage: "Rendu de l'image", frames: composition.durationInFrames});
		if (cancelled) throw new Error('annule');
		[rendering, lastAdvance] = [true, Date.now()];
		await renderMedia({
			serveUrl, composition, inputProps: props('none'), codec: 'h264', crf: 18, pixelFormat: 'yuv420p', muted: true,
			outputLocation: tmp.video, frameRange: job.frameRange ?? null, chromiumOptions: {gl: 'angle'},
			concurrency: Number(process.env.EDITEUR_CONCURRENCE) || Math.max(2, Math.min(12, os.cpus().length - 2)),
			onProgress: ({progress}) => {
				if (progress > best + 1e-6) [best, lastAdvance] = [progress, Date.now()];
				say({progress: 0.03 + progress * 0.94});
			},
			cancelSignal,
		});
		rendering = false;
		if (cancelled) throw new Error('annule');
		const start = job.frameRange ? job.frameRange[0] / composition.fps : 0;
		say({stage: 'Mixage final'});
		// 1. mixage voix + musique + bruitages ; 2. mesure du niveau (EBU R128) ; 3. gain vers -14 LUFS et limiteur
		// sur-echantillonne (crete vraie <= -1 dBTP) : meme niveau final quel que soit le style (et sans voix aussi)
		const ins = ['-ss', String(start), '-i', tmp.voice, ...(withFx ? ['-ss', String(start), '-f', 'f32le', '-ar', String(SR), '-ac', '2', '-i', tmp.fx] : [])];
		ffmpeg([...ins, '-filter_complex', withFx ? '[0:a][1:a]amix=inputs=2:normalize=0:duration=first[a]' : '[0:a]anull[a]',
			'-map', '[a]', '-c:a', 'pcm_f32le', tmp.mix]);
		const gain = Math.max(-20, Math.min(20, LUFS - loudness(tmp.mix)));
		ffmpeg(['-i', tmp.video, '-i', tmp.mix, '-filter_complex',
			`[1:a]volume=${gain.toFixed(2)}dB,aresample=192000,alimiter=limit=0.891:attack=1:release=60:level=false,aresample=48000[a]`,
			'-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', tmp.final]);
		// FFmpeg a fini : le fichier final prend sa place, en remplacant l'ancien (un FINAL present est toujours complet)
		fs.renameSync(tmp.final, job.out);
		say({done: true, out: job.out});
	} catch (e) {
		const raw = blocked ?? (cancelled ? 'Export annule.' : String(e?.message || e).slice(0, 2000));
		const message = traduireErreur(raw);
		if (message !== raw && !cancelled) journalBrut(job, raw);
		say({error: message, ...(blocked ? {blocked: true} : {})});
		process.exitCode = 1;
	} finally {
		rendering = false;
		clearInterval(watch);
		server.closeAllConnections?.();
		server.close();
		// .final.mp4 toujours retire (il n'existe encore que si l'export a echoue) ; GARDER_PISTES garde les pistes son
		for (const f of Object.values(tmp)) if (f === tmp.final || !(process.env.GARDER_PISTES && f !== tmp.video)) rmRetry(f);
		cleanChromeProfiles();
	}
	// Normalement le processus s'arrete tout seul ici. Si Chrome (ou le compositeur Remotion) ne se ferme pas, il le
	// garderait en vie indefiniment (export « bloque » qui ignore l'annulation) : on arrete nos processus enfants et on sort.
	setTimeout(() => {
		killChildren();
		process.exit(process.exitCode ?? 0);
	}, Number(process.env.EDITEUR_SORTIE_MS) || 8000).unref();
};

/** Suppression qui reessaie (Windows garde parfois le fichier verrouille quelques instants apres FFmpeg ou Chrome). */
const rmRetry = (f) => {
	for (let k = 0; k < 5; k++) {
		try {
			return fs.rmSync(f, {force: true});
		} catch {
			const until = Date.now() + 200;
			while (Date.now() < until);
		}
	}
};

/** Arrete les processus lances par cet export (Chrome, compositeur, FFmpeg) et leurs enfants (Windows : taskkill /T). */
const killChildren = () => {
	if (process.platform !== 'win32') return;
	try {
		const ps = `Get-CimInstance Win32_Process -Filter "ParentProcessId=${process.pid}" | ForEach-Object { $_.ProcessId }`;
		const r = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', ps], {encoding: 'utf8', timeout: 15000, windowsHide: true});
		const pids = String(r.stdout || '').split(/\s+/).map(Number).filter((n) => n > 0 && n !== r.pid);
		for (const pid of pids) spawnSync('taskkill.exe', ['/PID', String(pid), '/T', '/F'], {timeout: 15000, windowsHide: true});
		if (pids.length) process.stderr.write(`render.mjs : ${pids.length} processus enfant(s) arrete(s) de force\n`);
	} catch {}
};

/** Profils Chrome temporaires laisses par Remotion (runtime/cache/tmp) : on vide ceux de plus d'une heure. */
const cleanChromeProfiles = () => {
	const dir = path.join(ROOT, 'runtime', 'cache', 'tmp');
	try {
		for (const f of fs.readdirSync(dir)) {
			if (!/^(puppeteer_dev_chrome_profile|react-motion)/i.test(f)) continue;
			const p = path.join(dir, f);
			if (Date.now() - fs.statSync(p).mtimeMs > 3600e3) fs.rmSync(p, {recursive: true, force: true});
		}
	} catch {}
};

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
