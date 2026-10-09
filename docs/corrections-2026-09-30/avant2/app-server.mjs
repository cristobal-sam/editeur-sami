// Serveur local de l'editeur : interface, medias, montage, versions, recherche, exports.
// Seule connexion externe : les banques de medias libres (moteur Python, si une cle est dans cles-api.env).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const PROJECTS = path.join(ROOT, 'projects');
const PORT = Number(process.env.EDITEUR_PORT || 8790);
const HOST = '127.0.0.1';
const ORIGIN = `http://${HOST}:${PORT}`;

// Meme environnement que runtime/env.ps1 : tout reste dans le dossier de l'editeur.
const ENV = {
	...process.env,
	EDITEUR_ROOT: ROOT,
	HF_HOME: path.join(ROOT, 'models', 'huggingface'),
	TORCH_HOME: path.join(ROOT, 'models', 'torch'),
	ACESTEP_CHECKPOINTS_DIR: path.join(ROOT, 'models', 'acestep'),
	XDG_CACHE_HOME: path.join(ROOT, 'runtime', 'cache'),
	npm_config_cache: path.join(ROOT, 'runtime', 'cache', 'npm'),
	TEMP: path.join(ROOT, 'runtime', 'cache', 'tmp'),
	TMP: path.join(ROOT, 'runtime', 'cache', 'tmp'),
	PYTHONIOENCODING: 'utf-8',
	HF_HUB_DISABLE_SYMLINKS_WARNING: '1',
	HF_HUB_OFFLINE: '1',
	PATH: [path.join(ROOT, 'tools', 'ffmpeg', 'bin'), process.env.PATH].join(path.delimiter),
};
fs.mkdirSync(ENV.TEMP, {recursive: true});
const PYTHON = path.join(ROOT, 'runtime', 'venv', 'Scripts', 'python.exe');
const FFMPEG = path.join(ROOT, 'tools', 'ffmpeg', 'bin', 'ffmpeg.exe');

const MIME = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
	'.mp4': 'video/mp4', '.webm': 'video/webm', '.ttf': 'font/ttf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.json': 'application/json',
	'.svg': 'image/svg+xml', '.ogg': 'audio/ogg', '.wav': 'audio/wav', '.mp3': 'audio/mpeg'};

const json = (res, status, value) => {
	res.writeHead(status, {'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store'});
	res.end(JSON.stringify(value));
};

/** Ecriture sure : fichier temporaire puis remplacement (quelques essais si Windows verrouille le fichier). */
const writeAtomic = (file, text) => {
	const tmp = `${file}.${process.pid}.tmp`;
	fs.writeFileSync(tmp, text);
	for (let k = 0; ; k++) {
		try {
			return fs.renameSync(tmp, file);
		} catch (e) {
			if (k >= 4) throw e;
			const until = Date.now() + 150;
			while (Date.now() < until);
		}
	}
};

const readJson = async (req) => {
	let body = '';
	for await (const c of req) body += c;
	return body ? JSON.parse(body) : {};
};

const safeId = (s) => {
	if (!/^[a-z0-9_-]{1,60}$/i.test(String(s))) throw new Error('Identifiant invalide.');
	return String(s);
};

/** Banques de medias libres : arguments du moteur (la cle reste dans le moteur, jamais ici). */
const bankKind = (t) => (t === 'image' ? 'image' : 'video');
const bankId = (s) => {
	if (!/^[A-Za-z0-9_-]{1,40}$/.test(String(s))) throw new Error('Media invalide.');
	return String(s);
};
const bankSearchArgs = (b) => {
	const args = ['banques', 'chercher', '--type', bankKind(b.type), '--page', String(Math.min(20, Math.max(1, Number(b.page) || 1)))];
	if (['portrait', 'paysage', 'carre'].includes(b.orientation)) args.push('--orientation', b.orientation);
	const d = {courte: [0, 10], moyenne: [10, 30], longue: [30, 0]}[b.duree];
	if (d?.[0]) args.push('--duree-min', String(d[0]));
	if (d?.[1]) args.push('--duree-max', String(d[1]));
	if (['hd', '4k'].includes(b.qualite) && bankKind(b.type) === 'video') args.push('--qualite', b.qualite);
	// « -- » : une recherche qui commence par un tiret n'est pas lue comme une option
	return [...args, '--', String(b.q || '').trim().slice(0, 100)];
};

/** Fichier statique avec plages (lecture video fluide) et CORS (rendu Remotion). */
const sendFile = (req, res, file) => {
	if (!file || !fs.existsSync(file) || !fs.statSync(file).isFile()) return json(res, 404, {error: 'Introuvable.'});
	const size = fs.statSync(file).size;
	const headers = {'content-type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream',
		'accept-ranges': 'bytes', 'access-control-allow-origin': '*', 'cache-control': 'no-cache'};
	const m = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || '');
	if (m && (m[1] || m[2])) {
		const start = m[1] ? Number(m[1]) : Math.max(0, size - Number(m[2]));
		const end = m[1] && m[2] ? Math.min(Number(m[2]), size - 1) : size - 1;
		if (start > end || start >= size) {
			res.writeHead(416, {'content-range': `bytes */${size}`});
			return res.end();
		}
		res.writeHead(206, {...headers, 'content-length': end - start + 1, 'content-range': `bytes ${start}-${end}/${size}`});
		if (req.method === 'HEAD') return res.end();
		return fs.createReadStream(file, {start, end}).pipe(res);
	}
	res.writeHead(200, {...headers, 'content-length': size});
	if (req.method === 'HEAD') return res.end();
	fs.createReadStream(file).pipe(res);
};

/** Fichier sous un dossier autorise (jamais en dehors). */
const inside = (base, rel) => {
	const file = path.normalize(path.join(base, decodeURIComponent(rel)));
	return file.startsWith(base + path.sep) ? file : null;
};

const run = (exe, args, cwd, onLine = () => {}, onSpawn = () => {}) =>
	new Promise((resolve, reject) => {
		const child = spawn(exe, args, {cwd, env: ENV, windowsHide: true, shell: false});
		onSpawn(child);
		let out = '';
		let err = '';
		let pending = '';
		child.stdout.on('data', (b) => {
			out += b;
			pending += b;
			const lines = pending.split(/\r?\n/);
			pending = lines.pop();
			lines.forEach(onLine);
		});
		child.stderr.on('data', (b) => (err = (err + b).slice(-6000)));
		child.on('error', reject);
		child.on('exit', (code) => (code === 0 ? resolve(out) : reject(new Error(err.split('\n').map((l) => l.trimEnd()).filter((l) => l && !/warn|W0000|INFO:/i.test(l)).slice(-8).join('\n') || `Erreur ${code}`))));
	});
const python = (args) => run(PYTHON, ['-m', 'editeur', ...args], path.join(ROOT, 'engine'));
const lastJson = (out) => JSON.parse(out.trim().split(/\r?\n/).filter((l) => l.startsWith('{') || l.startsWith('[')).pop());

// Champs du reel modifiables par l'interface (le reste : sources, titre... vient du moteur)
const EDITABLE = ['style', 'zoom', 'banner', 'flash', 'progress', 'effects', 'emoji', 'music', 'sfx', 'audio', 'intro',
	'broll', 'graphics', 'brand', 'aiMode', 'suggestions', 'label', 'design', 'styleScenes'];
const reelFile = (project, rid) => path.join(PROJECTS, safeId(project), 'reels', `${safeId(rid)}.json`);
const readReel = (project, rid) => JSON.parse(fs.readFileSync(reelFile(project, rid), 'utf8'));
const readProject = (project) => JSON.parse(fs.readFileSync(path.join(PROJECTS, safeId(project), 'project.json'), 'utf8'));

/** Reel + prises possibles pour chaque plan (avec leurs mots, notes et criteres) pour changer de prise sans attendre. */
const opened = (reel) => {
	const project = readProject(reel.project);
	const clips = [...project.timeline, ...project.variants.map((v) => v.clip)];
	const takes = {};
	for (const c of clips) {
		takes[c.id] = (c.takes || []).map((t) => ({source: t.source, name: project.sources[t.source]?.name, score: t.score, notes: t.notes || [],
			parts: t.parts || {}, in: t.in, out: t.out, words: t.words, text: t.text}));
	}
	const blocks = Object.fromEntries(project.script.blocks.map((b) => [b.id, b.label]));
	return {reel, takes, blocks, mode: project.mode || 'script'};
};

const listReels = () => {
	const out = [];
	if (!fs.existsSync(PROJECTS)) return out;
	for (const name of fs.readdirSync(PROJECTS).sort()) {
		const pf = path.join(PROJECTS, name, 'project.json');
		if (!fs.existsSync(pf)) continue;
		let p;
		try {
			p = JSON.parse(fs.readFileSync(pf, 'utf8'));
		} catch {
			console.error(`Projet illisible ignore : ${pf}`);
			continue;
		}
		const label = p.label || p.name;
		const modes = {'sans-script': 'Montage', immobilier: 'Immobilier', evenement: 'Événement'};
		out.push({project: name, rid: 'script', label: `${label} - ${modes[p.mode] ?? 'Version script'}`});
		p.variants.forEach((v) => out.push({project: name, rid: v.id, label: `${label} - ${v.label}`}));
		// declinaisons (60/30/15 s, rapide, emotion...) creees depuis un reel
		const rdir = path.join(PROJECTS, name, 'reels');
		if (fs.existsSync(rdir)) {
			for (const f of fs.readdirSync(rdir).filter((x) => x.endsWith('.json')).sort()) {
				const rid = f.slice(0, -5);
				if (rid === 'script' || p.variants.some((v) => v.id === rid)) continue;
				try {
					const r = JSON.parse(fs.readFileSync(path.join(rdir, f), 'utf8'));
					if (r.derivedFrom) out.push({project: name, rid, label: `${label} - ${r.derivedFrom === 'script' ? 'script' : r.derivedFrom} › ${r.label}`});
				} catch {}
			}
		}
	}
	return out.map((r) => ({...r, opened: fs.existsSync(reelFile(r.project, r.rid))}));
};

// ---------- Versions (instantanes du reel) ----------
const versionsDir = (project, rid) => path.join(PROJECTS, safeId(project), 'versions', safeId(rid));
const snapshot = (project, rid, name) => {
	// montage absent (video supprimee ?) : on ne recree pas de dossier projet vide
	if (!fs.existsSync(reelFile(project, rid))) throw new Error('Montage introuvable (vidéo supprimée ?).');
	const dir = versionsDir(project, rid);
	fs.mkdirSync(dir, {recursive: true});
	const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
	const clean = String(name || 'sans nom').replace(/[^\p{L}\p{N} _-]/gu, '').slice(0, 60).trim() || 'sans nom';
	let file = `${stamp} ${clean}.json`;
	for (let n=2;fs.existsSync(path.join(dir,file));n++) file=`${stamp} ${clean} (${n}).json`;
	fs.copyFileSync(reelFile(project, rid), path.join(dir, file));
	return file;
};
const listVersions = (project, rid) => {
	const dir = versionsDir(project, rid);
	if (!fs.existsSync(dir)) return [];
	return fs.readdirSync(dir).filter((f) => f.endsWith('.json')).sort().reverse()
		.map((f) => ({file: f, date: `${f.slice(0, 10)} ${f.slice(11, 19).replace(/-/g, ':')}`, name: f.slice(20, -5)}));
};

// ---------- Travaux en cours par projet (une video en travail ne peut pas etre supprimee) ----------
const busyProjects = new Map();
const holdProject = async (project, fn) => {
	if (!project) return fn();
	busyProjects.set(project, (busyProjects.get(project) ?? 0) + 1);
	try {
		return await fn();
	} finally {
		const n = (busyProjects.get(project) ?? 1) - 1;
		if (n > 0) busyProjects.set(project, n);
		else busyProjects.delete(project);
	}
};

// ---------- Taches longues (export, musique, intro, recherche) ----------
const jobs = new Map();
const startJob = (stage, fn, project = null) => {
	const job = {id: crypto.randomUUID(), status: 'running', stage, progress: 0, started: Date.now(), ...(project ? {project} : {})};
	jobs.set(job.id, job);
	holdProject(project, () => fn(job))
		.then((result) => Object.assign(job, {status: 'done', progress: 1, result, seconds: Math.round((Date.now() - job.started) / 1000)}))
		.catch((e) => Object.assign(job, {status: 'failed', error: job.error || e.message}));
	return job;
};

/** Journal du serveur (lu par l'outil « erreurs » du plugin) : une ligne datee. */
const logServeur = (line) => {
	try {
		fs.appendFileSync(path.join(ROOT, 'runtime', 'cache', 'erreurs-serveur.log'), `${new Date().toISOString()} ${line}\n`);
	} catch {}
};
/** Arrete un processus ET tout ce qu'il a lance (Chrome, compositeur Remotion, FFmpeg). Sous Windows, tuer seulement
 * node laisserait Chrome ouvert : taskkill /T parcourt l'arbre tant que le processus parent existe encore. */
const killTree = (child) => {
	if (!child || child.exitCode !== null || child.signalCode !== null) return;
	if (process.platform !== 'win32') return child.kill('SIGKILL');
	const exe = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe');
	const k = spawn(exe, ['/PID', String(child.pid), '/T', '/F'], {windowsHide: true, stdio: 'ignore'});
	k.on('error', () => child.kill());
	k.on('exit', (code) => code !== 0 && child.exitCode === null && child.kill());
};

// ---------- File d'exports : un export a la fois, les autres attendent ; on continue a travailler ----------
const FORMATS = {'9:16': [1080, 1920], '16:9': [1920, 1080], '4:5': [1080, 1350], '1:1': [1080, 1080]};
const formatOf = (r) => Object.entries(FORMATS).find(([, [w, h]]) => w === r.width && h === r.height)?.[0] ?? '9:16';
const queue = [];
let exporting = false;
const procs = new Map(); // job.id -> processus render.mjs en cours (jamais envoye a l'interface)
// Export bloque : si la progression n'avance plus, on l'arrete (au lieu de rester des heures a « 3 % »).
// render.mjs s'arrete seul apres EDITEUR_BLOCAGE_S pendant le rendu de l'image ; le serveur verifie avec une marge,
// et plus largement pour les autres etapes (voix, mixage, preparation) qui n'envoient pas de progression.
const BLOCAGE_RENDU = (Number(process.env.EDITEUR_BLOCAGE_S) || 240) * 1000;
const BLOCAGE_MARGE = (Number(process.env.EDITEUR_BLOCAGE_MARGE_S) || 45) * 1000;
const BLOCAGE_AUTRE = (Number(process.env.EDITEUR_BLOCAGE_AUTRE_S) || 600) * 1000;
// apres le fichier .stop, render.mjs a ce delai pour s'arreter proprement ; sinon on arrete tout son arbre de processus
const GRACE_STOP = (Number(process.env.EDITEUR_GRACE_STOP_S) || 20) * 1000;

/** Demande l'arret d'un export en cours (annulation ou blocage) ; arret force si le .stop n'est pas respecte. */
const stopExport = (job) => {
	if (job.stopping) return;
	job.stopping = true;
	try {
		if (job.stopFile) fs.writeFileSync(job.stopFile, '1');
	} catch {}
	setTimeout(() => {
		const child = procs.get(job.id);
		if (job.status !== 'running' || !child || child.exitCode !== null || child.signalCode !== null) return;
		logServeur(`export ${job.id} « ${job.title} » : ne s'arrete pas apres ${GRACE_STOP / 1000} s, arret force (pid ${child.pid} et ses processus)`);
		killTree(child);
	}, GRACE_STOP).unref();
};

const etapeLisible = (stage) => {
	const s = String(stage || '').replace(/^Demarrage$/, 'Démarrage').replace(/^Preparation du moteur graphique$/, 'Préparation du moteur graphique') || 'Export';
	return s.charAt(0).toLowerCase() + s.slice(1);
};
setInterval(() => {
	for (const job of jobs.values()) {
		if (job.kind !== 'export' || job.status !== 'running' || job.stopping) continue;
		const rendu = /rendu de l'image/i.test(job.stage || '');
		const limit = rendu ? BLOCAGE_RENDU + BLOCAGE_MARGE : BLOCAGE_AUTRE;
		const idle = Date.now() - (job.lastAdvance ?? job.started);
		if (idle < limit) continue;
		const s = Math.round(idle / 1000);
		job.blocked = true;
		job.error = `L'export s'est bloqué à ${Math.round(100 * (job.progress || 0))} % (${etapeLisible(job.stage)}) : plus rien n'avançait depuis ${s < 90 ? `${s} s` : `${Math.round(s / 60)} min`}, il a été arrêté. `
			+ 'Relance « Je la prends ». Si ça recommence, ferme les logiciels lourds (IA, Blender, jeux) puis réessaie.';
		logServeur(`export bloque ${job.id} « ${job.title} » (${job.format}) : ${Math.round(100 * (job.progress || 0))} %, etape « ${job.stage} », rien depuis ${Math.round(idle / 1000)} s`);
		stopExport(job);
	}
}, 5000).unref();

const exportReel = (reel, format) => {
	const fmt = FORMATS[format] ? format : formatOf(reel);
	const doc = {...reel, width: FORMATS[fmt][0], height: FORMATS[fmt][1]};
	const suffix = fmt === '9:16' ? '' : ` (${fmt.replace(':', 'x')})`;
	const dir = reel.delivery || path.join(ROOT, 'livraisons');
	const job = {id: crypto.randomUUID(), kind: 'export', status: 'queued', stage: "En attente dans la file", progress: 0, created: Date.now(),
		title: `${reel.title}${suffix}`, format: fmt, project: reel.project, rid: reel.id, out: path.join(dir, `${reel.title}${suffix} - FINAL.mp4`)};
	jobs.set(job.id, job);
	queue.push({job, reel: doc});
	pump();
	return job;
};

const pump = async () => {
	if (exporting) return;
	const next = queue.find((q) => q.job.status === 'queued');
	if (!next) return;
	exporting = true;
	const {job, reel} = next;
	Object.assign(job, {status: 'running', stage: 'Demarrage', started: Date.now(), lastAdvance: Date.now(), maxProgress: 0});
	const jobFile = path.join(ENV.TEMP, `export-${job.id}.json`);
	job.stopFile = jobFile + '.stop';
	try {
		fs.mkdirSync(path.dirname(job.out), {recursive: true});
		fs.writeFileSync(jobFile, JSON.stringify({reel, out: job.out}));
		await run(process.execPath, [path.join(ROOT, 'remotion', 'render.mjs'), jobFile], path.join(ROOT, 'remotion'), (line) => {
			try {
				const e = JSON.parse(line);
				// « avance » = nouvelle etape ou progression plus haute (Remotion renvoie parfois la meme valeur en boucle)
				if (e.stage && e.stage !== job.stage) [job.stage, job.lastAdvance] = [e.stage, Date.now()];
				if (typeof e.progress === 'number') {
					job.progress = e.progress;
					if (e.progress > job.maxProgress + 1e-6) [job.maxProgress, job.lastAdvance] = [e.progress, Date.now()];
				}
				if (e.error && !job.blocked) job.error = e.error;
			} catch {}
		}, (child) => procs.set(job.id, child));
		if (job.error) throw new Error(job.error);
		if (!fs.existsSync(job.out) || fs.statSync(job.out).size === 0) throw new Error("L'export n'a produit aucun fichier vidéo.");
		Object.assign(job, {status: 'done', progress: 1, result: {out: job.out}});
	} catch (e) {
		Object.assign(job, {status: job.cancelled ? 'cancelled' : 'failed', error: job.cancelled ? 'Export annulé.' : job.error || e.message});
		if (!job.cancelled) logServeur(`export echoue ${job.id} « ${job.title} » (${job.format}) : ${String(job.error).slice(0, 400)}`);
	} finally {
		job.seconds = Math.round((Date.now() - job.started) / 1000);
		procs.delete(job.id);
		for (const f of [jobFile, job.stopFile]) fs.rmSync(f, {force: true});
		queue.splice(queue.indexOf(next), 1);
		exporting = false;
		pump();
	}
};

const cancelJob = (id) => {
	const job = jobs.get(id);
	if (!job || job.kind !== 'export') throw new Error('Tache inconnue.');
	job.cancelled = true;
	if (job.status === 'queued') {
		Object.assign(job, {status: 'cancelled', error: 'Export annulé.'});
		const i = queue.findIndex((q) => q.job === job);
		if (i >= 0) queue.splice(i, 1);
	} else if (job.status === 'running') stopExport(job); // .stop, puis arret force apres 20 s si besoin
	return job;
};

/** Tache telle qu'envoyee a l'interface (sans les champs internes). */
const publicJob = ({stopFile, lastAdvance, maxProgress, stopping, ...j}) => j;
const exportList = () => [...jobs.values()].filter((j) => j.kind === 'export').sort((a, b) => b.created - a.created).slice(0, 30).map(publicJob);

const readStyles = (f) => JSON.parse(fs.readFileSync(path.join(ROOT, 'styles', f), 'utf8'));
const styles = () => ({
	// « perso » : style cree par l'utilisateur (renommable, supprimable) ; le dossier _corbeille n'est pas lu
	montage: readTemplates().map((t) => ({...t, perso: isUserStyle(t.id)})),
	captions: readStyles('sous-titres.json'),
	music: readStyles('musiques.json').map((m) => ({...m, file: `music/${m.id}.ogg`})),
	generated: fs.existsSync(path.join(ROOT, 'assets', 'music', 'generes'))
		? fs.readdirSync(path.join(ROOT, 'assets', 'music', 'generes')).filter((f) => f.endsWith('.ogg')).map((f) => `music/generes/${f}`)
		: [],
	sfx: fs.readdirSync(path.join(ROOT, 'assets', 'sfx', 'editeur')).filter((f) => f.endsWith('.wav')).map((f) => f.replace(/\.wav$/, '')),
});

/** Musique originale sur mesure (ACE-Step, local). */
const makeMusic = (project, rid, mood, seed, duration) =>
	startJob('Composition de la musique', async (job) => {
		const info = readStyles('musiques.json').find((m) => m.id === mood);
		if (!info) throw new Error('Ambiance inconnue.');
		const dir = path.join(ROOT, 'assets', 'music', 'generes');
		fs.mkdirSync(dir, {recursive: true});
		const name = `${project}-${rid}-${mood}-${seed}`;
		const wav = path.join(ENV.TEMP, `${name}.wav`);
		const taskFile = path.join(ENV.TEMP, `music-${job.id}.json`);
		fs.writeFileSync(taskFile, JSON.stringify([{caption: info.caption, bpm: info.bpm, duration: Math.ceil(duration + 3), seed, out: wav}]));
		try {
			await run(path.join(ROOT, 'runtime', 'venvs', 'acestep', 'Scripts', 'python.exe'), [path.join(ROOT, 'engine', 'music_gen.py'), taskFile], path.join(ROOT, 'engine'), (line) => {
				try {
					const e = JSON.parse(line);
					if (e.stage) Object.assign(job, {stage: e.stage, progress: Math.min(0.8, job.progress + 0.3)});
					if (e.error) job.error = e.error;
				} catch {}
			});
			await run(FFMPEG, ['-v', 'error', '-y', '-i', wav, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000', '-c:a', 'libvorbis', '-q:a', '6', path.join(dir, `${name}.ogg`)], ROOT);
		} finally {
			fs.rmSync(taskFile, {force: true});
			fs.rmSync(wav, {force: true});
		}
		return {file: `music/generes/${name}.ogg`};
	});

// ---------- Chartes clients : styles/clients/<id>.json + assets/clients/<id>/ (logo) ----------
const CLIENTS = path.join(ROOT, 'styles', 'clients');
const listClients = () => (fs.existsSync(CLIENTS) ? fs.readdirSync(CLIENTS).filter((f) => f.endsWith('.json')).sort()
	.map((f) => JSON.parse(fs.readFileSync(path.join(CLIENTS, f), 'utf8'))) : []);
const saveClient = (body) => {
	const name = String(body.name || '').trim().slice(0, 60);
	if (!name) throw new Error('Nom du client requis.');
	const id = safeId(body.client || name.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'client');
	fs.mkdirSync(CLIENTS, {recursive: true});
	const file = path.join(CLIENTS, `${id}.json`);
	const old = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
	let logo = old.logo ?? null;
	const m = /^data:image\/(png|jpeg|webp|svg\+xml);base64,(.+)$/.exec(body.logoData || '');
	if (m) {
		const ext = {png: 'png', jpeg: 'jpg', webp: 'webp', 'svg+xml': 'svg'}[m[1]];
		const dir = path.join(ROOT, 'assets', 'clients', id);
		fs.mkdirSync(dir, {recursive: true});
		fs.writeFileSync(path.join(dir, `logo.${ext}`), Buffer.from(m[2], 'base64'));
		logo = `assets/clients/${id}/logo.${ext}`;
	}
	const hex = (v, d) => (/^#[0-9a-f]{6}$/i.test(v) ? v : d);
	const doc = {
		client: id, name, logo,
		logoPosition: ['haut-gauche', 'haut-droite', 'bas-gauche', 'bas-droite'].includes(body.logoPosition) ? body.logoPosition : 'haut-droite',
		logoSize: Math.min(0.4, Math.max(0.05, Number(body.logoSize) || 0.16)), logoOpacity: Math.min(1, Math.max(0.1, Number(body.logoOpacity) || 0.85)),
		bannerBg: hex(body.bannerBg, '#FFFFFF'), bannerColor: hex(body.bannerColor, '#0B0B0B'),
		style: {font: String(body.style?.font || '') || undefined, color: hex(body.style?.color, undefined), highlight: hex(body.style?.highlight, undefined), stroke: hex(body.style?.stroke, undefined)},
		outro: {enabled: !!body.outro?.enabled, text: String(body.outro?.text || '').slice(0, 80), duration: Math.min(5, Math.max(1, Number(body.outro?.duration) || 2.5))},
	};
	writeAtomic(file, JSON.stringify(doc, null, 1));
	return doc;
};

// >>> styles-utilisateur (fonctions sans etat serveur : testees a part en extrayant ce bloc)
// ---------- Styles de montage de l'utilisateur : enregistrer, renommer, supprimer (corbeille) ----------
const MONTAGE = path.join(ROOT, 'styles', 'montage');
const TYPES_FILE = path.join(ROOT, 'styles', 'types.json');
// styles fournis avec l'editeur : jamais remplaces ni supprimes
const BUILTIN_STYLES = new Set(['evenement', 'immobilier', 'minimal-propre', 'motivation-geant', 'podcast-clip', 'pub-premium', 'reel-impact', 'reel-karaoke', 'ugc-naturel']);
// sujet -> style d'origine (copie de styles/types.json) : un sujet dont le style est supprime y revient
const DEFAULT_TYPE_STYLES = {pub: 'reel-impact', temoignage: 'ugc-naturel', conseil: 'reel-karaoke', motivation: 'motivation-geant', podcast: 'podcast-clip',
	annonce: 'pub-premium', fiction: 'minimal-propre', immobilier: 'immobilier', evenement: 'evenement', autre: 'reel-impact'};
// champs d'un reel qui forment son style (le montage : prises, coupes, mots... n'en fait pas partie)
const TEMPLATE_FIELDS = ['template', 'style', 'zoom', 'banner', 'flash', 'effects', 'emoji', 'progress', 'music', 'sfx', 'aiMode', 'design'];

/** Style cree par l'utilisateur : « style par reference » (ref-*) ou « Enregistrer comme mon style » (mon-*). */
const isUserStyle = (id) => typeof id === 'string' && id.length <= 60 && !BUILTIN_STYLES.has(id) && /^(ref|mon)-[a-z0-9_-]+$/i.test(id);
const slugOf = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40).replace(/-+$/, '');
const cleanName = (s) => String(s ?? '').replace(/[\x00-\x1f<>]/g, '').replace(/\s+/g, ' ').trim().slice(0, 40).trim();
const sameName = (a, b) => String(a ?? '').trim().toLowerCase() === String(b ?? '').trim().toLowerCase();
const templatePath = (id) => path.join(MONTAGE, `${safeId(id)}.json`);
const readJsonFile = (file, fallback) => {
	try {
		return JSON.parse(fs.readFileSync(file, 'utf8'));
	} catch {
		return fallback;
	}
};
/** Styles de montage (styles/montage/*.json, sans les sous-dossiers comme _corbeille) ; un fichier illisible est ignore. */
const readTemplates = () => (fs.existsSync(MONTAGE) ? fs.readdirSync(MONTAGE, {withFileTypes: true}).filter((e) => e.isFile() && e.name.endsWith('.json'))
	.map((e) => e.name).sort().flatMap((f) => {
		const t = readJsonFile(path.join(MONTAGE, f), null);
		if (!t?.id) console.error(`Style illisible ignore : ${f}`);
		return t?.id ? [t] : [];
	}) : []);

/** Deplace un fichier dans <son dossier>/_corbeille (jamais efface : on peut le recuperer). */
const moveToTrash = (file, id) => {
	const dir = path.join(path.dirname(file), '_corbeille');
	fs.mkdirSync(dir, {recursive: true});
	const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
	let dest = path.join(dir, `${id} ${stamp}.json`);
	for (let n = 2; fs.existsSync(dest); n++) dest = path.join(dir, `${id} ${stamp} (${n}).json`);
	for (let k = 0; ; k++) {
		try {
			fs.renameSync(file, dest);
			return dest;
		} catch (e) {
			if (k >= 4) throw e;
			const until = Date.now() + 150;
			while (Date.now() < until);
		}
	}
};

const num = (v, lo, hi, d) => (v !== null && v !== '' && Number.isFinite(Number(v)) ? Math.min(hi, Math.max(lo, Number(v))) : d);
const hexOr = (v, d) => (/^#[0-9a-f]{6}$/i.test(String(v)) ? String(v) : d);
const idOr = (v, d) => (typeof v === 'string' && /^[a-z0-9_-]{1,40}$/i.test(v) ? v : d);

/** Style de montage (comme styles/montage/*.json) a partir des reglages d'un reel. base = style d'ou vient le reel. */
const templateFromReel = (reel, base, id, name) => {
	const s = reel.style ?? {};
	const z = reel.zoom ?? {};
	const fx = reel.effects ?? {};
	const mu = reel.music ?? {};
	const sx = reel.sfx ?? {};
	const captions = readJsonFile(path.join(ROOT, 'styles', 'sous-titres.json'), []);
	const moods = readJsonFile(path.join(ROOT, 'styles', 'musiques.json'), []);
	const preset = captions.find((c) => c.id === s.preset) ?? captions.find((c) => c.id === base?.captions) ?? captions[0];
	const mood = mu.enabled ? idOr(mu.mood, null) : null;
	const flashKind = ['blanc', 'glitch', 'lumiere'].includes(reel.flash?.kind) ? reel.flash.kind : 'blanc';
	const tpl = {
		id, name, description: '',
		captions: preset?.id ?? 'impact',
		// sous-titres tels qu'on les voit (par-dessus le preset)
		style: {font: typeof s.font === 'string' && s.font ? s.font.slice(0, 40) : undefined, weight: Math.round(num(s.weight, 100, 900, 900)), uppercase: !!s.uppercase,
			size: Math.round(num(s.size, 20, 200, 72)), color: hexOr(s.color, '#FFFFFF'), highlight: hexOr(s.highlight, '#FFD400'), stroke: hexOr(s.stroke, '#000000'),
			strokeWidth: Math.round(num(s.strokeWidth, 0, 30, 12)), position: num(s.position, 0.05, 0.95, 0.68), maxWords: Math.round(num(s.maxWords, 1, 8, 3)), pop: !!s.pop},
		zoom: {auto: !!z.auto, strength: num(z.strength, 1, 1.5, 1.1), push: num(z.push, 0, 0.2, 0.02)},
		banner: {enabled: !!reel.banner?.enabled},
		flash: {enabled: !!reel.flash?.enabled, kind: flashKind},
		effects: {grain: num(fx.grain, 0, 1, 0), vignette: num(fx.vignette, 0, 1, 0), grade: idOr(fx.grade, 'aucun')},
		emoji: !!reel.emoji?.enabled,
		progress: !!reel.progress?.enabled,
		music: {mood, volume: num(mu.volume, 0, 1, 0.2)},
		sfx: {enabled: sx.enabled !== false, transition: idOr(sx.transition, null), highlight: idOr(sx.highlight, null), highlightGap: num(sx.highlightGap, 1, 20, 4),
			cta: idOr(sx.cta, null), start: idOr(sx.start, null), volume: num(sx.volume, 0, 1, 0.6)},
		ia: reel.aiMode === 'suggestion' ? 'suggestion' : 'auto',
		graphismes: base?.graphismes === 'auto' ? 'auto' : 'suggestion',
		...(base?.broll ? {broll: base.broll} : {}),
		depuis: idOr(base?.id, null),
		...(reel.design?.mode ? {design: {...reel.design}, category: base?.category, preview: base?.preview} : {}),
	};
	const moodName = moods.find((m) => m.id === mood)?.name ?? mood;
	const flashName = {blanc: 'flash', glitch: 'glitch', lumiere: 'fuite de lumière'}[flashKind];
	tpl.description = `Mon style : ${[
		`sous-titres « ${preset?.name ?? tpl.captions} » (${tpl.style.maxWords} mot${tpl.style.maxWords > 1 ? 's' : ''}${tpl.style.uppercase ? ', majuscules' : ''})`,
		tpl.zoom.auto ? (tpl.zoom.strength >= 1.14 ? 'zooms marqués' : 'zooms légers') : 'sans zoom',
		tpl.flash.enabled ? `${flashName} entre les parties` : null,
		mood ? `musique ${moodName}` : 'sans musique',
		tpl.banner.enabled ? "bandeau d'accroche" : null,
		tpl.emoji ? 'emojis' : null,
	].filter(Boolean).join(', ')}.`;
	return tpl;
};

/** « Enregistrer comme mon style ». Renvoie le style enregistre, ou {conflict} si l'utilisateur a deja un style de ce nom
 * (on lui demande s'il veut le remplacer : replace = id). Un nom deja pris par un style fourni -> « Nom (2) ». */
const saveUserStyle = (reel, body) => {
	const templates = readTemplates();
	let name = cleanName(body.name);
	if (!name) throw new Error('Donne un nom à ton style.');
	let id;
	let old = null;
	if (body.replace) {
		id = String(body.replace);
		if (!isUserStyle(id) || !fs.existsSync(templatePath(id))) throw new Error("Seuls tes propres styles peuvent être remplacés (pas ceux fournis avec l'éditeur).");
		old = readJsonFile(templatePath(id), {});
		if (templates.some((t) => t.id !== id && sameName(t.name, name))) throw new Error('Un autre style porte déjà ce nom : choisis-en un autre.');
	} else {
		const base = `mon-${slugOf(name) || 'style'}`;
		const clash = templates.find((t) => t.id === base || sameName(t.name, name));
		if (clash && isUserStyle(clash.id) && !body.suffix) return {conflict: {id: clash.id, name: clash.name}};
		id = base;
		if (clash || fs.existsSync(templatePath(base))) {
			const root = name;
			for (let n = 2; ; n++) {
				[id, name] = [`${base}-${n}`, `${root} (${n})`];
				if (!fs.existsSync(templatePath(id)) && !templates.some((t) => sameName(t.name, name))) break;
			}
		}
	}
	if (BUILTIN_STYLES.has(id)) throw new Error("Les styles fournis avec l'éditeur ne peuvent pas être remplacés.");
	const base = old ?? templates.find((t) => t.id === reel.template) ?? {};
	const tpl = templateFromReel(reel, base, id, name);
	if (old?.reference) tpl.reference = old.reference; // mesures de la video de reference (style par reference)
	tpl.cree = old?.cree ?? new Date().toISOString().slice(0, 10);
	if (old) tpl.modifie = new Date().toISOString().slice(0, 10);
	fs.mkdirSync(MONTAGE, {recursive: true});
	writeAtomic(templatePath(id), JSON.stringify(tpl, null, 1));
	return tpl;
};

const renameUserStyle = (id, rawName) => {
	if (!isUserStyle(id)) throw new Error("Les styles fournis avec l'éditeur ne peuvent pas être renommés.");
	const file = templatePath(id);
	if (!fs.existsSync(file)) throw new Error('Style introuvable.');
	const name = cleanName(rawName);
	if (!name) throw new Error('Donne un nom à ton style.');
	if (readTemplates().some((t) => t.id !== id && sameName(t.name, name))) throw new Error('Un autre style porte déjà ce nom : choisis-en un autre.');
	const tpl = JSON.parse(fs.readFileSync(file, 'utf8'));
	tpl.name = name; // l'identifiant ne change pas : les videos et les sujets qui l'utilisent restent valides
	writeAtomic(file, JSON.stringify(tpl, null, 1));
	return tpl;
};

/** Supprime un style de l'utilisateur = le range dans styles/montage/_corbeille. Les sujets qui l'utilisaient
 * reviennent a leur style d'origine (liste renvoyee pour le dire a l'utilisateur). */
const trashUserStyle = (id) => {
	if (!isUserStyle(id)) throw new Error("Les styles fournis avec l'éditeur ne peuvent pas être supprimés.");
	const file = templatePath(id);
	if (!fs.existsSync(file)) throw new Error('Style introuvable (déjà supprimé ?).');
	const name = readJsonFile(file, {})?.name || id;
	const dest = moveToTrash(file, id);
	const sujets = [];
	const types = readJsonFile(TYPES_FILE, null);
	if (types) {
		const names = Object.fromEntries(readTemplates().map((t) => [t.id, t.name]));
		for (const [k, v] of Object.entries(types)) {
			if (v?.style !== id) continue;
			v.style = DEFAULT_TYPE_STYLES[k] && names[DEFAULT_TYPE_STYLES[k]] ? DEFAULT_TYPE_STYLES[k] : 'reel-impact';
			sujets.push({sujet: v.label ?? k, style: v.style, styleName: names[v.style] ?? v.style});
		}
		if (sujets.length) writeAtomic(TYPES_FILE, JSON.stringify(types, null, 1));
	}
	return {id, name, corbeille: path.relative(ROOT, dest), sujets};
};

/** Supprime une charte client = la range dans styles/clients/_corbeille (le logo reste dans assets/clients). */
const trashClient = (id) => {
	const file = path.join(CLIENTS, `${safeId(id)}.json`);
	if (!fs.existsSync(file)) throw new Error('Charte introuvable (déjà supprimée ?).');
	const name = readJsonFile(file, {})?.name || id;
	const dest = moveToTrash(file, id);
	return {client: id, name, corbeille: path.relative(ROOT, dest)};
};
// <<< styles-utilisateur

// ---------- Revision : videos deposees -> montees seules -> je la prends / modifier / autre style ----------
// Boite d'entree : media/entree/<lot>/. Dans un lot : chaque video seule = une video ; chaque sous-dossier = les prises
// d'une meme video (avec ou sans script) ; un script a la racine du lot (sans video du meme nom) = tout le lot suit ce script.
const ENTREE = path.join(ROOT, 'media', 'entree');
const REVISION = path.join(PROJECTS, '_revision.json');
const VIDEO_EXT = new Set(['.mp4', '.mov', '.m4v', '.mkv', '.avi', '.mts', '.webm']);
const SCRIPT_EXT = new Set(['.docx', '.txt', '.pdf']);
fs.mkdirSync(ENTREE, {recursive: true});
const revision = (() => {
	try {
		return JSON.parse(fs.readFileSync(REVISION, 'utf8'));
	} catch {
		return {items: [], lots: {}};
	}
})();
revision.items.filter((i) => i.status === 'travail').forEach((i) => Object.assign(i, {status: 'attente', stage: 'En attente'}));
const saveRevision = () => {
	try {
		fs.mkdirSync(PROJECTS, {recursive: true});
		writeAtomic(REVISION, JSON.stringify(revision, null, 1));
	} catch (e) {
		console.error(`Revision non enregistree : ${e.message}`);
	}
};
// « Je la prends » : un export par format coche (item.exports). Anciennes donnees : un seul export (item.export).
const FINAL = new Set(['done', 'failed', 'cancelled', 'interrompu']);
const formatFromOut = (out) => {
	const f = / \((\d+)x(\d+)\) - FINAL\.mp4$/.exec(String(out || ''));
	return f ? `${f[1]}:${f[2]}` : '9:16';
};
const itemExports = (i) => {
	if (!i.exports && i.export?.job) {
		i.exports = [{format: i.export.format ?? formatFromOut(i.export.out), job: i.export.job, out: i.export.out,
			status: i.status === 'pris' && i.taken?.out === i.export.out ? 'done' : i.export.status}];
	}
	delete i.export;
	return i.exports ?? [];
};
// apres un redemarrage, les exports en cours n'existent plus : revisionState les marque « interrompu » (au lieu de rester a « 0 % »)
revision.items.forEach(itemExports);
const relRoot = (p) => path.relative(ROOT, p).split(path.sep).join('/');
const itemId = (s) => crypto.createHash('sha1').update(s.toLowerCase()).digest('hex').slice(0, 12);
const visible = (n) => !n.startsWith('.') && !n.startsWith('~$');

/** Unites d'un lot (voir plus haut). */
const unitsOf = (lotDir) => {
	const entries = fs.readdirSync(lotDir, {withFileTypes: true}).filter((e) => visible(e.name));
	const ext = (e) => path.extname(e.name).toLowerCase();
	const videos = entries.filter((e) => e.isFile() && VIDEO_EXT.has(ext(e)));
	const stems = new Set(videos.map((e) => path.parse(e.name).name.toLowerCase()));
	const lotScript = entries.some((e) => e.isFile() && SCRIPT_EXT.has(ext(e)) && !stems.has(path.parse(e.name).name.toLowerCase()));
	if (lotScript && (videos.length || entries.some((e) => e.isDirectory()))) return [lotDir];
	return [...videos.map((e) => path.join(lotDir, e.name)), ...entries.filter((e) => e.isDirectory()).map((e) => path.join(lotDir, e.name))];
};
/** Empreinte (taille + date) : une video encore en cours de copie n'est pas traitee. */
const signature = (p) => {
	const st = fs.statSync(p);
	if (!st.isDirectory()) return `${st.size}-${Math.round(st.mtimeMs)}`;
	let n = 0;
	let t = 0;
	const walk = (d) => fs.readdirSync(d, {withFileTypes: true}).forEach((e) => {
		const f = path.join(d, e.name);
		if (e.isDirectory()) return walk(f);
		const s = fs.statSync(f);
		n += s.size;
		t = Math.max(t, s.mtimeMs);
	});
	walk(p);
	return `${n}-${Math.round(t)}`;
};
const seen = new Map();
const scanInbox = () => {
	try {
		scanInboxUnsafe();
	} catch (e) {
		console.error(`Boite d'entree : ${e.message}`);
	}
};
const scanInboxUnsafe = () => {
	if (!fs.existsSync(ENTREE)) return;
	let added = false;
	for (const lot of fs.readdirSync(ENTREE, {withFileTypes: true}).filter((e) => e.isDirectory() && visible(e.name))) {
		const lotDir = path.join(ENTREE, lot.name);
		const info = revision.lots[lot.name] ?? (revision.lots[lot.name] = {created: Date.now()});
		if (info.uploading && Date.now() - (info.lastPut ?? info.created) > 120000) {
			// envoi interrompu (page fermee) : on traite ce qui est arrive
			Object.assign(info, {uploading: false, complete: true, interrupted: true});
			added = true;
		}
		if (info.uploading) continue;
		let units = [];
		try {
			units = unitsOf(lotDir);
		} catch {
			continue;
		}
		for (const u of units) {
			const unit = relRoot(u);
			const id = itemId(unit);
			if (revision.items.some((i) => i.id === id || i.unit === unit)) continue;
			let sig = '';
			try {
				sig = signature(u);
			} catch {
				continue;
			}
			const prev = seen.get(id);
			if (!info.complete && (!prev || prev.sig !== sig || Date.now() - prev.t < 8000)) {
				if (!prev || prev.sig !== sig) seen.set(id, {sig, t: Date.now()});
				continue; // copie peut-etre en cours : on attend que rien ne change pendant 8 s
			}
			revision.items.push({id, unit, lot: lot.name, name: path.basename(u), status: 'attente', stage: 'En attente', progress: 0, created: Date.now()});
			added = true;
		}
	}
	if (added) {
		saveRevision();
		pumpAuto();
	}
};

let autoBusy = false;
const pumpAuto = async () => {
	if (autoBusy) return;
	const item = revision.items.find((i) => i.status === 'attente');
	if (!item) return;
	autoBusy = true;
	Object.assign(item, {status: 'travail', stage: 'Démarrage', progress: 0, error: null, started: Date.now()});
	saveRevision();
	const lot = revision.lots[item.lot] ?? {};
	const args = ['-m', 'editeur', 'auto', path.join(ROOT, item.unit), '--livraison', path.join(ROOT, 'livraisons', item.lot)];
	if (lot.client) args.push('--client', safeId(lot.client));
	if (item.forceStyle) args.push('--style', safeId(item.forceStyle));
	try {
		const out = await run(PYTHON, args, path.join(ROOT, 'engine'), (line) => {
			try {
				const e = JSON.parse(line);
				if (e.stage) item.stage = e.stage;
				if (typeof e.progress === 'number') item.progress = e.progress;
			} catch {}
		});
		const projets = lastJson(out).projets ?? [];
		if (!projets.length) throw new Error('Aucun montage produit.');
		projets.forEach((p, k) => {
			const fields = {status: 'pret', stage: 'Prête', progress: 1, project: p.project, rid: p.rid, type: p.type, typeLabel: p.typeLabel,
				title: p.titre, reason: p.raison, style: p.style, broll: p.plansDeCoupe ?? 0, alerts: p.alertes ?? [], ia: p.ia !== false,
				error: null, updated: Date.now()};
			if (k === 0) return Object.assign(item, fields);
			// autres videos trouvees dans la meme unite (un « Refaire » met a jour celles qui existent deja)
			const id = itemId(`${item.unit}#${p.project}`);
			const twin = revision.items.find((i) => i.id === id);
			if (twin) Object.assign(twin, fields);
			else revision.items.push({...item, ...fields, exports: [], taken: null, id, name: `${item.name} · ${p.titre}`});
		});
	} catch (e) {
		Object.assign(item, {status: 'erreur', stage: 'Erreur', error: e.message.slice(-600), updated: Date.now()});
	} finally {
		autoBusy = false;
		saveRevision();
		pumpAuto();
	}
};

/** Etat de la file pour l'interface : avancement de chaque export (un par format) ; tous finis et au moins un reussi -> « prise ». */
const revisionState = () => {
	let changed = false;
	for (const i of revision.items) {
		const list = itemExports(i);
		for (const e of list) {
			const j = jobs.get(e.job);
			if (j) {
				if (FINAL.has(j.status) && e.status !== j.status) changed = true;
				Object.assign(e, {status: j.status, progress: j.progress ?? 0, stage: j.stage ?? '', error: j.error ?? null, seconds: j.seconds ?? null});
			} else if (!FINAL.has(e.status)) {
				// l'editeur a redemarre pendant l'export : la tache n'existe plus
				Object.assign(e, {status: 'interrompu', stage: '', error: null});
				changed = true;
			}
		}
		const done = list.filter((e) => e.status === 'done');
		const batch = list[0]?.job;
		if (done.length && list.every((e) => FINAL.has(e.status)) && (i.status === 'pret' || i.status === 'pris') && i.taken?.batch !== batch) {
			Object.assign(i, {status: 'pris', taken: {out: done[0].out, outs: done.map((e) => e.out), formats: done.map((e) => e.format), date: Date.now(), batch}});
			changed = true;
		}
	}
	if (changed) saveRevision();
	// style affiche = celui du montage (reel.template) : il change aussi quand on choisit un style dans l'editeur ;
	// item.style (style du montage automatique) ne sert que si le montage est illisible
	const items = revision.items.filter((i) => i.status !== 'retire').map((i) => {
		const tpl = i.project && i.rid ? reelTemplate(i.project, i.rid) : null;
		return tpl && tpl !== i.style ? {...i, style: tpl} : i;
	});
	return {items, lots: revision.lots, entree: ENTREE, corbeille: CORBEILLE, busy: autoBusy};
};
/** reel.template lu sur le disque, relu seulement si le fichier a change (la liste est demandee toutes les 2,5 s). */
const templateCache = new Map();
const reelTemplate = (project, rid) => {
	let file;
	try {
		file = reelFile(project, rid);
		const {mtimeMs, size} = fs.statSync(file);
		const hit = templateCache.get(file);
		if (hit && hit.mtimeMs === mtimeMs && hit.size === size) return hit.template;
		const template = JSON.parse(fs.readFileSync(file, 'utf8')).template ?? null;
		templateCache.set(file, {mtimeMs, size, template});
		return template;
	} catch {
		if (file) templateCache.delete(file);
		return null;
	}
};
const exportRunning = (i) => itemExports(i).some((e) => ['queued', 'running'].includes(jobs.get(e.job)?.status));

// ---------- Supprimer une video de la Revision ----------
// Rien n'est efface : le dossier du montage (projects\<projet>) et les videos brutes deposees (media\entree\<lot>\<video>)
// sont DEPLACES dans corbeille\<date heure> <nom>\ (meme arborescence + corbeille.json pour les remettre a la main).
// Les videos exportees (livraisons\) restent ou elles sont. Refuse pendant un montage, un export ou un travail sur le projet.
const CORBEILLE = path.join(ROOT, 'corbeille');
const renameRetry = (src, dest) => {
	for (let k = 0; ; k++) {
		try {
			return fs.renameSync(src, dest);
		} catch (e) {
			if (k >= 4 || !['EPERM', 'EBUSY', 'EACCES'].includes(e.code)) throw e;
			const until = Date.now() + 200;
			while (Date.now() < until);
		}
	}
};
/** Chemin sur a deplacer : strictement sous base, sans « .. », pas un lien (jonction), et vraiment dans base une fois
 * resolu. null s'il n'existe pas (montage pas encore cree, video deja enlevee a la main). */
const cheminSur = (base, target) => {
	const resolved = path.resolve(target);
	const rel = path.relative(base, resolved);
	if (!rel || path.isAbsolute(rel) || rel.split(/[\\/]/).some((s) => !s || s === '.' || s === '..')) throw new Error('Chemin refusé : suppression annulée.');
	let st;
	try {
		st = fs.lstatSync(resolved);
	} catch {
		return null;
	}
	if (st.isSymbolicLink()) throw new Error(`Chemin refusé (lien vers un autre dossier) : ${relRoot(resolved)}. Rien n'a été déplacé.`);
	const real = fs.realpathSync.native(resolved).toLowerCase();
	if (!real.startsWith(fs.realpathSync.native(base).toLowerCase() + path.sep)) throw new Error('Chemin refusé : suppression annulée.');
	return resolved;
};
/** Ce qui sera deplace pour cette video (verifie avant de toucher a quoi que ce soit). */
const planSuppression = (item) => {
	const plan = [];
	const garde = [];
	if (item.project) {
		// jamais les dossiers internes (_cache, _revision.json) ni un nom bizarre
		if (!/^[a-z0-9][a-z0-9_-]{0,59}$/i.test(String(item.project))) throw new Error('Nom de projet invalide : suppression annulée.');
		const others = revision.items.filter((o) => o !== item && o.project === item.project);
		const dir = cheminSur(PROJECTS, path.join(PROJECTS, String(item.project)));
		if (dir && others.length) garde.push(`le montage (${relRoot(dir)}) : une autre vidéo de la liste l'utilise`);
		else if (dir) plan.push(dir);
	}
	if (item.unit) {
		const parts = String(item.unit).split('/');
		if (parts.length < 3 || parts.length > 4 || parts[0] !== 'media' || parts[1] !== 'entree' || parts[2] !== item.lot
			|| parts.slice(2).some((s) => !s || s === '.' || s === '..' || /[<>:"\\|?*\x00-\x1f]/.test(s))) throw new Error('Chemin de la vidéo brute invalide : suppression annulée.');
		const unit = cheminSur(ENTREE, path.join(ENTREE, ...parts.slice(2)));
		// les prises d'une meme unite peuvent donner plusieurs videos : on garde les rushs tant qu'une autre les utilise
		const others = revision.items.filter((o) => o !== item && o.unit === item.unit);
		if (unit && others.length) garde.push(`les vidéos brutes (${item.unit}) : une autre vidéo de la liste les utilise`);
		else if (unit) {
			plan.push(unit);
			// video seule : son script du meme nom (pub1.mp4 + pub1.docx) part avec elle
			if (fs.statSync(unit).isFile()) {
				const stem = path.parse(unit).name.toLowerCase();
				for (const f of fs.readdirSync(path.dirname(unit))) {
					const p = path.parse(f);
					if (p.name.toLowerCase() === stem && SCRIPT_EXT.has(p.ext.toLowerCase())) {
						const s = cheminSur(ENTREE, path.join(path.dirname(unit), f));
						if (s && fs.statSync(s).isFile()) plan.push(s);
					}
				}
			}
		}
	}
	return {plan, garde};
};
const nomCorbeille = (item) => {
	const stamp = new Date().toLocaleString('sv-SE').slice(0, 16).replace(':', 'h');
	const name = String(item.title || item.name || item.id).replace(/[<>:"/\\|?*\x00-\x1f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 60).replace(/[. ]+$/, '') || item.id;
	let dir = path.join(CORBEILLE, `${stamp} ${name}`);
	for (let n = 2; fs.existsSync(dir); n++) dir = path.join(CORBEILLE, `${stamp} ${name} (${n})`);
	return dir;
};
/** Retire les dossiers vides laisses derriere (jamais un dossier qui contient encore quelque chose). */
const removeEmptyDirs = (dir, stop) => {
	for (let d = dir; d.startsWith(stop + path.sep) && d !== stop; d = path.dirname(d)) {
		try {
			if (fs.readdirSync(d).length) return;
			fs.rmdirSync(d);
		} catch {
			return;
		}
	}
};
const supprimerVideo = (item) => {
	const titre = item.title || item.name;
	// (une video de la meme unite en montage recreerait celle-ci a la fin)
	if (item.status === 'travail' || (item.unit && revision.items.some((o) => o.unit === item.unit && o.status === 'travail'))) {
		throw Object.assign(new Error(`« ${titre} » est en cours de montage : attends la fin, puis supprime-la.`), {status: 409});
	}
	const exportEnCours = exportRunning(item) || queue.some((q) => q.job.project && q.job.project === item.project && ['queued', 'running'].includes(q.job.status));
	if (exportEnCours) throw Object.assign(new Error(`Un export de « ${titre} » est en cours : annule-le d'abord (bouton « Annuler »), puis supprime-la.`), {status: 409});
	if (item.project && busyProjects.get(item.project)) throw Object.assign(new Error(`L'éditeur travaille encore sur « ${titre} » (style, IA, détourage…) : attends la fin, puis réessaie.`), {status: 409});
	const {plan, garde} = planSuppression(item);
	const outs = [...new Set([...(item.taken?.outs ?? (item.taken?.out ? [item.taken.out] : [])), ...itemExports(item).filter((e) => e.status === 'done').map((e) => e.out)])]
		.filter((f) => f && fs.existsSync(f));
	let trash = null;
	const moved = [];
	if (plan.length) {
		trash = nomCorbeille(item);
		try {
			for (const src of plan) {
				const dest = path.join(trash, path.relative(ROOT, src));
				fs.mkdirSync(path.dirname(dest), {recursive: true});
				renameRetry(src, dest);
				moved.push({src, dest});
			}
		} catch (e) {
			const bad = plan[moved.length] ?? plan[0];
			// on remet en place ce qui a deja ete deplace : la video reste dans la liste, comme avant
			for (const m of [...moved].reverse()) {
				try {
					renameRetry(m.dest, m.src);
				} catch (e2) {
					logServeur(`suppression ${item.id} : impossible de remettre ${m.dest} -> ${m.src} : ${e2.message}`);
				}
			}
			for (const src of plan) removeEmptyDirs(path.dirname(path.join(trash, path.relative(ROOT, src))), CORBEILLE);
			logServeur(`suppression ${item.id} « ${titre} » annulee : ${relRoot(bad)} : ${e.code || e.message}`);
			throw Object.assign(new Error(`Suppression impossible : ${relRoot(bad)} est peut-être ouvert dans un autre logiciel (lecteur vidéo, explorateur…). Ferme-le puis réessaie. Rien n'a été supprimé.`), {status: 409});
		}
		const manifest = {
			supprime: new Date().toISOString(),
			video: {id: item.id, titre, nom: item.name, lot: item.lot, projet: item.project ?? null, version: item.rid ?? null, sujet: item.typeLabel ?? null, style: item.style ?? null, etat: item.status},
			deplacements: moved.map((m) => ({avant: relRoot(m.src), maintenant: relRoot(m.dest)})),
			gardes: [...garde, ...outs.map((f) => `vidéo exportée gardée : ${f}`)],
			registre: item,
			pour_la_remettre: "Déplace chaque dossier « maintenant » vers son chemin « avant » (l'éditeur peut rester ouvert) : "
				+ "les vidéos brutes seront remontées toutes seules. Pour retrouver aussi le montage sans le refaire, remets d'abord le dossier projects.",
		};
		writeAtomic(path.join(trash, 'corbeille.json'), JSON.stringify(manifest, null, 1));
	}
	// retire de la liste ; le lot disparait quand il n'a plus de video
	revision.items.splice(revision.items.indexOf(item), 1);
	seen.delete(item.id);
	const lotDir = path.join(ENTREE, String(item.lot));
	let lotGone = false;
	if (item.lot && !revision.items.some((o) => o.lot === item.lot)) {
		let rest = [];
		try {
			rest = fs.readdirSync(lotDir);
		} catch {}
		if (!rest.some(visible)) {
			delete revision.lots[item.lot];
			lotGone = true;
			if (!rest.length && cheminSur(ENTREE, lotDir)) {
				try {
					fs.rmdirSync(lotDir); // dossier vide seulement
				} catch {}
			}
		}
	}
	saveRevision();
	logServeur(`video supprimee ${item.id} « ${titre} » -> ${trash ? relRoot(trash) : '(rien a deplacer)'}`);
	return {id: item.id, titre, corbeille: trash, deplaces: moved.map((m) => relRoot(m.src)), gardes: garde, livraisons: outs, lotRetire: lotGone};
};
setInterval(scanInbox, 5000);
setTimeout(() => {
	scanInbox();
	pumpAuto().catch((e) => console.error(e));
}, 1500);

/** Chemin d'un fichier depose dans la boite d'entree (jamais en dehors ; noms simples). */
const entreePath = (lot, rel) => {
	const parts = [lot, ...String(rel).split('/')].map((s) => decodeURIComponent(s));
	if (parts.some((s) => !s || s === '.' || s === '..' || /[<>:"\\|?*\x00-\x1f]/.test(s) || s.length > 150)) throw new Error('Nom de fichier invalide.');
	const file = path.join(ENTREE, ...parts);
	if (!file.startsWith(ENTREE + path.sep)) throw new Error('Chemin refusé.');
	const e = path.extname(file).toLowerCase();
	if (!VIDEO_EXT.has(e) && !SCRIPT_EXT.has(e)) throw new Error('Seulement des vidéos et des scripts (.docx, .txt, .pdf).');
	return file;
};

/** Vignette d'une prise a un instant (cache). */
const thumb = async (proxyRel, t) => {
	const src = inside(ROOT, proxyRel);
	if (!src || !src.startsWith(PROJECTS)) throw new Error('Media invalide.');
	const dir = path.join(PROJECTS, '_cache', 'vignettes');
	fs.mkdirSync(dir, {recursive: true});
	const file = path.join(dir, `${crypto.createHash('sha1').update(`${proxyRel}|${t}`).digest('hex').slice(0, 16)}.jpg`);
	if (!fs.existsSync(file)) await run(FFMPEG, ['-v', 'error', '-y', '-ss', String(t), '-i', src, '-frames:v', '1', '-vf', 'scale=216:-2', '-q:v', '4', file], ROOT);
	return file;
};

const server = http.createServer(async (req, res) => {
	const url = new URL(req.url, ORIGIN);
	const p = url.pathname;
	try {
		if (req.method !== 'GET' && req.method !== 'HEAD' && req.headers.origin !== ORIGIN) return json(res, 403, {error: 'Origine non autorisee.'});
		if (p === '/' || p === '/index.html') return sendFile(req, res, path.join(HERE, 'ui', 'index.html'));
		if (p.startsWith('/dist/')) return sendFile(req, res, path.join(HERE, 'dist', path.basename(p)));
		if (p === '/styles.css') return sendFile(req, res, path.join(HERE, 'ui', 'styles.css'));
		if (p.startsWith('/assets/')) return sendFile(req, res, inside(path.join(ROOT, 'assets'), p.slice(8)));
		if (p.startsWith('/projects/')) return sendFile(req, res, inside(PROJECTS, p.slice(10)));

		if (p === '/api/reels' && req.method === 'GET') return json(res, 200, listReels());
		if (p === '/api/styles' && req.method === 'GET') return json(res, 200, styles());
		if (p === '/api/styles' && req.method === 'POST') {
			// « Enregistrer comme mon style » : reglages envoyes par l'interface (a jour meme avant la sauvegarde auto)
			const body = await readJson(req);
			const [project, rid] = [safeId(body.project), safeId(body.rid)];
			if (!fs.existsSync(reelFile(project, rid))) return json(res, 404, {error: 'Montage introuvable : ouvre la vidéo, puis réessaie.'});
			const reel = readReel(project, rid);
			for (const k of TEMPLATE_FIELDS) if (body.reel?.[k] !== undefined) reel[k] = body.reel[k];
			const tpl = saveUserStyle(reel, body);
			if (tpl.conflict) return json(res, 200, tpl);
			// le reel porte maintenant ce style (champ hors EDITABLE : la sauvegarde auto ne l'ecrase pas)
			const disk = readReel(project, rid);
			disk.template = tpl.id;
			writeAtomic(reelFile(project, rid), JSON.stringify(disk, null, 1));
			return json(res, 200, {...tpl, perso: true});
		}
		let m = /^\/api\/styles\/([^/]+)(\/renommer)?$/.exec(p);
		if (m && req.method === 'POST' && m[2]) {
			const {name} = await readJson(req);
			return json(res, 200, {...renameUserStyle(decodeURIComponent(m[1]), name), perso: true});
		}
		if (m && req.method === 'DELETE' && !m[2]) {
			const out = trashUserStyle(decodeURIComponent(m[1]));
			// « Refaire » avec ce style n'est plus possible : on reprend le style du sujet
			let touched = false;
			for (const i of revision.items) if (i.forceStyle === out.id) [i.forceStyle, touched] = [null, true];
			if (touched) saveRevision();
			return json(res, 200, out);
		}
		if (p === '/api/thumb' && req.method === 'GET') return sendFile(req, res, await thumb(url.searchParams.get('proxy') || '', Number(url.searchParams.get('t') || 0)));
		m = /^\/api\/transcript\/([^/]+)\/([^/]+)$/.exec(p);
		if (m) {
			const src = readProject(m[1]).sources[safeId(m[2])];
			if (!src) return json(res, 404, {error: 'Prise inconnue.'});
			return json(res, 200, JSON.parse(fs.readFileSync(src.transcript, 'utf8')).words);
		}
		if (p === '/api/search' && req.method === 'POST') {
			const {project, q} = await readJson(req);
			return json(res, 202, startJob('Recherche dans les rushs', async () => lastJson(await python(['recherche', path.join(PROJECTS, safeId(project)), String(q).slice(0, 200)])), safeId(project)));
		}
		m = /^\/api\/jobs\/([a-f0-9-]{36})(\/cancel)?$/.exec(p);
		if (m && m[2] && req.method === 'POST') return json(res, 200, publicJob(cancelJob(m[1])));
		if (m) {
			if (!jobs.has(m[1])) return json(res, 404, {error: 'Tache inconnue.'});
			return json(res, 200, publicJob(jobs.get(m[1])));
		}
		if (p === '/api/queue' && req.method === 'GET') return json(res, 200, exportList());
		// ---- Revision ----
		if (p === '/api/revision' && req.method === 'GET') {
			scanInbox();
			return json(res, 200, revisionState());
		}
		if (p === '/api/types' && req.method === 'GET') return json(res, 200, JSON.parse(fs.readFileSync(path.join(ROOT, 'styles', 'types.json'), 'utf8')));
		m = /^\/api\/types\/([a-z]+)$/.exec(p);
		if (m && req.method === 'POST') {
			// « Toujours ce style pour ce sujet » : les prochaines videos de ce sujet seront montees dans ce style
			const file = path.join(ROOT, 'styles', 'types.json');
			const types = JSON.parse(fs.readFileSync(file, 'utf8'));
			const {style} = await readJson(req);
			if (!types[m[1]]) return json(res, 404, {error: 'Sujet inconnu.'});
			if (!fs.existsSync(path.join(ROOT, 'styles', 'montage', `${safeId(style)}.json`))) return json(res, 404, {error: 'Style inconnu.'});
			types[m[1]].style = safeId(style);
			writeAtomic(file, JSON.stringify(types, null, 1));
			return json(res, 200, types);
		}
		if (p === '/api/entree/lot' && req.method === 'POST') {
			// nouveau lot (depot depuis la page) : les fichiers arrivent ensuite un par un (PUT), puis /fin
			const {client} = await readJson(req);
			const stamp = new Date().toLocaleString('sv-SE').slice(0, 16).replace(':', 'h');
			let lot = `Lot ${stamp}`;
			for (let n = 2; fs.existsSync(path.join(ENTREE, lot)); n++) lot = `Lot ${stamp} (${n})`;
			fs.mkdirSync(path.join(ENTREE, lot), {recursive: true});
			revision.lots[lot] = {created: Date.now(), client: client ? safeId(client) : null, uploading: true};
			saveRevision();
			return json(res, 200, {lot});
		}
		m = /^\/api\/entree\/([^/]+)\/fin$/.exec(p);
		if (m && req.method === 'POST') {
			const lot = decodeURIComponent(m[1]);
			if (!revision.lots[lot]) return json(res, 404, {error: 'Lot inconnu.'});
			Object.assign(revision.lots[lot], {uploading: false, complete: true});
			saveRevision();
			scanInbox();
			return json(res, 200, revisionState());
		}
		m = /^\/api\/entree\/([^/]+)\/(.+)$/.exec(p);
		if (m && req.method === 'PUT') {
			const lot = decodeURIComponent(m[1]);
			if (!revision.lots[lot]?.uploading) return json(res, 400, {error: 'Lot fermé ou inconnu.'});
			revision.lots[lot].lastPut = Date.now();
			const file = entreePath(lot, m[2]);
			fs.mkdirSync(path.dirname(file), {recursive: true});
			const tmp = file + '.part';
			await new Promise((resolve, reject) => {
				const out = fs.createWriteStream(tmp);
				req.pipe(out);
				out.on('finish', resolve);
				out.on('error', reject);
				req.on('error', reject);
			});
			fs.renameSync(tmp, file);
			revision.lots[lot].lastPut = Date.now();
			return json(res, 200, {ok: true});
		}
		m = /^\/api\/revision\/([a-f0-9]{12})\/([a-z]+)$/.exec(p);
		if (m && req.method === 'POST') {
			const item = revision.items.find((i) => i.id === m[1]);
			if (!item) return json(res, 404, {error: 'Vidéo inconnue.'});
			const body = await readJson(req);
			if (m[2] === 'prendre') {
				if (!item.project || !['pret', 'pris'].includes(item.status)) return json(res, 400, {error: 'La vidéo n\'est pas encore prête.'});
				if (exportRunning(item)) return json(res, 409, {error: 'Un export est déjà en cours pour cette vidéo : attends la fin (ou annule-le).'});
				const reel = readReel(item.project, item.rid);
				// un export par format coche (file d'exports : un a la fois) ; ancien appel : un seul format
				const asked = Array.isArray(body.formats) ? body.formats : body.format ? [body.format] : [];
				const list = Object.keys(FORMATS).filter((f) => asked.includes(f));
				snapshot(item.project, item.rid, 'prise');
				const queued = (list.length ? list : [formatOf(reel)]).map((f) => exportReel(reel, f));
				item.exports = queued.map((j) => ({format: j.format, job: j.id, out: j.out, status: j.status, progress: 0, stage: j.stage, error: null}));
				saveRevision();
				return json(res, 202, {exports: item.exports});
			}
			if (m[2] === 'style') {
				if (!item.project || !['pret', 'pris'].includes(item.status)) return json(res, 400, {error: 'La vidéo n\'est pas encore montée : attends qu\'elle soit prête.'});
				const id = safeId(body.style);
				if (!fs.existsSync(templatePath(id))) return json(res, 404, {error: 'Ce style n\'existe plus (supprimé ?). Choisis-en un autre.'});
				const before = snapshot(item.project, item.rid, `avant le style ${id}`);
				await holdProject(item.project, () => python(['reel', path.join(PROJECTS, safeId(item.project)), ...(item.rid==='script'?[]:['--variante',safeId(item.rid)]), '--style', id]));
				item.previousStyleVersion=before;
				Object.assign(item, {style: id, status: item.status === 'pris' ? 'pret' : item.status, updated: Date.now()});
				saveRevision();
				return json(res, 200, opened(readReel(item.project, item.rid)));
			}
			if (m[2] === 'retourstyle') {
				if (!item.project || !item.rid || !item.previousStyleVersion) return json(res,400,{error:'Aucun changement de style à annuler.'});
				const source=inside(versionsDir(item.project,item.rid),item.previousStyleVersion);
				if (!source || !fs.existsSync(source)) return json(res,404,{error:'La version précédente est introuvable.'});
				snapshot(item.project,item.rid,'avant retour au style précédent');
				fs.copyFileSync(source,reelFile(item.project,item.rid));
				const restored=readReel(item.project,item.rid);
				Object.assign(item,{style:restored.template,previousStyleVersion:null,status:'pret',updated:Date.now()});saveRevision();
				return json(res,200,opened(restored));
			}
			if (m[2] === 'refaire') {
				if (item.status === 'travail') return json(res, 409, {error: 'Le montage de cette vidéo est déjà en cours.'});
				if (body.style && !fs.existsSync(templatePath(body.style))) return json(res, 404, {error: 'Ce style n\'existe plus (supprimé ?).'});
				Object.assign(item, {status: 'attente', stage: 'En attente', progress: 0, error: null, forceStyle: body.style ? safeId(body.style) : item.forceStyle});
				saveRevision();
				pumpAuto();
				return json(res, 200, revisionState());
			}
			if (m[2] === 'retirer') {
				// une video en cours de montage finirait quand meme : on attend la fin
				if (item.status === 'travail') return json(res, 409, {error: 'Montage en cours : attends la fin pour la retirer.'});
				item.status = 'retire';
				saveRevision();
				return json(res, 200, revisionState());
			}
			if (m[2] === 'supprimer') {
				// montage + videos brutes -> corbeille (rien n'est efface) ; les videos exportees restent dans livraisons
				try {
					const supprime = supprimerVideo(item);
					return json(res, 200, {...revisionState(), supprime});
				} catch (e) {
					return json(res, e.status || 400, {error: e.message});
				}
			}
			return json(res, 404, {error: 'Action inconnue.'});
		}
		if (p === '/api/revision/supprimer' && req.method === 'POST') {
			// plusieurs videos d'un coup : chacune est verifiee ; celles qui sont occupees sont gardees (raison renvoyee)
			const {ids} = await readJson(req);
			if (!Array.isArray(ids) || !ids.length || ids.length > 200) return json(res, 400, {error: 'Choisis au moins une vidéo.'});
			const resultats = [];
			for (const id of new Set(ids.map(String))) {
				const item = /^[a-f0-9]{12}$/.test(id) ? revision.items.find((i) => i.id === id) : null;
				if (!item) {
					resultats.push({id, ok: false, error: 'Vidéo inconnue (déjà supprimée ?).'});
					continue;
				}
				try {
					resultats.push({id, ok: true, ...supprimerVideo(item)});
				} catch (e) {
					resultats.push({id, ok: false, titre: item.title || item.name, error: e.message});
				}
			}
			return json(res, 200, {...revisionState(), resultats});
		}
		// ---- Style par reference : une video deja montee -> nouveau style de montage ----
		m = /^\/api\/references\/([^/]+)$/.exec(p);
		if (m && req.method === 'PUT') {
			const name = decodeURIComponent(m[1]);
			if (!/^[^<>:"/\\|?*\x00-\x1f]{1,150}$/.test(name) || name.startsWith('.') || !VIDEO_EXT.has(path.extname(name).toLowerCase())) {
				return json(res, 400, {error: 'Une vidéo (mp4, mov, webm…) est attendue.'});
			}
			const dir = path.join(ROOT, 'media', 'references');
			fs.mkdirSync(dir, {recursive: true});
			const file = path.join(dir, name);
			await new Promise((resolve, reject) => {
				const out = fs.createWriteStream(file + '.part');
				req.pipe(out);
				out.on('finish', resolve);
				out.on('error', reject);
			});
			fs.renameSync(file + '.part', file);
			return json(res, 200, {fichier: name});
		}
		if (p === '/api/references/analyser' && req.method === 'POST') {
			const {fichier, nom} = await readJson(req);
			const file = inside(path.join(ROOT, 'media', 'references'), encodeURIComponent(String(fichier || '')));
			if (!file || !fs.existsSync(file)) return json(res, 404, {error: 'Vidéo de référence introuvable.'});
			const args = ['style-ref', file, ...(nom ? [`--nom=${String(nom).slice(0, 40)}`] : [])];
			return json(res, 202, startJob('Analyse du style de la vidéo de référence', async () => lastJson(await python(args))));
		}
		if (p === '/api/banques' && req.method === 'GET') return json(res, 200, lastJson(await python(['banques', 'statut'])));
		if (p === '/api/banques/recherche' && req.method === 'POST') {
			const body = await readJson(req);
			if (!String(body.q || '').trim()) return json(res, 400, {error: 'Écris ce que tu cherches.'});
			return json(res, 200, lastJson(await python(bankSearchArgs(body))));
		}

		m = /^\/api\/reels\/([^/]+)\/([^/]+)(\/[a-z]+)?$/.exec(p);
		if (m) {
			const [project, rid, action] = [safeId(m[1]), safeId(m[2]), m[3] || ''];
			const variant = rid === 'script' ? null : rid;
			const vArgs = variant ? ['--variante', variant] : [];
			if (req.method === 'GET' && action === '/open') return json(res, 200, opened(readReel(project, rid)));
			if (req.method === 'POST' && action === '/open') {
				await holdProject(project, () => python(['reel', path.join(PROJECTS, project), ...vArgs]));
				return json(res, 200, opened(readReel(project, rid)));
			}
			if (req.method === 'PUT' && !action) {
				const body = await readJson(req);
				const current = readReel(project, rid);
				for (const k of EDITABLE) if (body[k] !== undefined) current[k] = body[k];
				if (body.format && FORMATS[body.format]) [current.width, current.height] = FORMATS[body.format];
				if (Array.isArray(body.broll) && !body.broll.every((b) => current.sources[b.source])) return json(res, 400, {error: 'Plan de coupe invalide.'});
				if (Array.isArray(body.clips)) {
					// le montage (ordre, prises, coupes, J/L-cuts, couleur) est gere par l'interface : on valide les sources
					if (!body.clips.every((c) => current.sources[c.source] && typeof c.in === 'number' && typeof c.out === 'number' && c.out > c.in)) {
						return json(res, 400, {error: 'Montage invalide.'});
					}
					current.clips = body.clips;
				}
				writeAtomic(reelFile(project, rid), JSON.stringify(current, null, 1));
				return json(res, 200, {saved: true});
			}
			if (req.method === 'POST' && action === '/template') {
				const {id} = await readJson(req);
				snapshot(project, rid, `avant le style ${id}`);
				await holdProject(project, () => python(['reel', path.join(PROJECTS, project), ...vArgs, '--style', safeId(id)]));
				return json(res, 200, opened(readReel(project, rid)));
			}
			if (req.method === 'GET' && action === '/versions') return json(res, 200, listVersions(project, rid));
			if (req.method === 'POST' && action === '/versions') {
				const {name} = await readJson(req);
				return json(res, 200, {file: snapshot(project, rid, name), versions: listVersions(project, rid)});
			}
			if (req.method === 'POST' && action === '/restore') {
				const {file} = await readJson(req);
				const src = inside(versionsDir(project, rid), file);
				if (!src || !fs.existsSync(src)) return json(res, 404, {error: 'Version introuvable.'});
				snapshot(project, rid, 'avant restauration');
				fs.copyFileSync(src, reelFile(project, rid));
				return json(res, 200, opened(readReel(project, rid)));
			}
			if (req.method === 'GET' && action === '/version') {
				const src = inside(versionsDir(project, rid), url.searchParams.get('file') || '');
				if (!src || !fs.existsSync(src)) return json(res, 404, {error: 'Version introuvable.'});
				return json(res, 200, JSON.parse(fs.readFileSync(src, 'utf8')));
			}
			if (req.method === 'POST' && action === '/music') {
				const {mood, seed, duration} = await readJson(req);
				return json(res, 202, makeMusic(project, rid, safeId(mood), Number(seed) || Math.floor(Math.random() * 1e6), Number(duration) || 60));
			}
			if (req.method === 'POST' && action === '/intro') {
				const {text, color, seconds} = await readJson(req);
				return json(res, 202, startJob('Rendu du titre 3D (Blender)', async () =>
					lastJson(await python(['intro', path.join(PROJECTS, project), String(text).slice(0, 80), '--couleur', /^#[0-9a-f]{6}$/i.test(color) ? color : '#FFD400', '--duree', String(Number(seconds) || 2.5)])), project));
			}
			if (req.method === 'POST' && action === '/produit') {
				snapshot(project, rid, 'avant produit 3D');
				return json(res, 202, startJob('Animation du produit par Blender', async () => lastJson(await python(['produit', path.join(PROJECTS,project), '--reel',rid])), project));
			}
			if (req.method === 'POST' && action === '/detourage') {
				return json(res,202,startJob('Détourage de la personne',async()=>lastJson(await python(['detourage',path.join(PROJECTS,project),'--reel',rid])), project));
			}
			// Propositions du moteur (rien n'est applique sans le monteur) : resultat JSON de la commande
			const PROPOSALS = {'/ia': ['ia', 'Propositions de l\'IA'], '/broll': ['broll', 'Recherche de plans de coupe'],
				'/graphismes': ['graphismes', 'Propositions de graphismes'], '/raccords': ['raccords', 'Recherche des faux raccords'],
				'/angles': ['angles', 'Choix des angles (multicamera)']};
			if (req.method === 'POST' && PROPOSALS[action]) {
				const body = await readJson(req);
				const extra = [...(body.tout ? ['--tout'] : []), ...(body.vision === false ? ['--sans-vision'] : []), ...(body.large ? ['--large', String(Number(body.large) | 0)] : []),
					...(action === '/broll' && body.banques === false ? ['--sans-banques'] : []), ...(action === '/broll' && body.auto ? ['--auto'] : [])];
				const [cmd, label] = PROPOSALS[action];
				return json(res, 202, startJob(body.auto ? 'Plans de coupe automatiques' : label, async () => lastJson(await python([cmd, path.join(PROJECTS, project), '--reel', rid, ...extra])), project));
			}
			// Banques de medias libres : ajouter un media au reel (telecharge une seule fois) / trouver un plan pour une phrase
			if (req.method === 'POST' && action === '/banque') {
				const b = await readJson(req);
				const args = ['banques', 'ajouter', path.join(PROJECTS, project), '--reel', rid, '--fournisseur', safeId(b.fournisseur), '--id', bankId(b.id),
					'--type', bankKind(b.type), `--requete=${String(b.requete || '').slice(0, 100)}`];
				return json(res, 202, startJob('Téléchargement du plan de coupe', async () => lastJson(await python(args)), project));
			}
			if (req.method === 'POST' && action === '/phrase') {
				const {at} = await readJson(req);
				return json(res, 202, startJob('Recherche d\'un plan pour la phrase', async () =>
					lastJson(await python(['banques', 'phrase', path.join(PROJECTS, project), '--reel', rid, '--at', String(Math.max(0, Number(at) || 0))])), project));
			}
			if (req.method === 'POST' && action === '/declinaison') {
				const {duree, intention} = await readJson(req);
				const args = ['declinaison', path.join(PROJECTS, project), '--reel', rid];
				if (Number(duree) > 0) args.push('--duree', String(Number(duree)));
				if (['rapide', 'emotion'].includes(intention)) args.push('--intention', intention);
				return json(res, 202, startJob('Création de la déclinaison', async () => lastJson(await python(args)), project));
			}
			if (req.method === 'POST' && action === '/echange') {
				return json(res, 202, startJob('Export pour Resolve / Premiere', async () => lastJson(await python(['echange', path.join(PROJECTS, project), ...vArgs])), project));
			}
			if (req.method === 'POST' && action === '/export') {
				const {formats} = await readJson(req);
				snapshot(project, rid, 'export');
				const reel = readReel(project, rid);
				const list = Array.isArray(formats) && formats.length ? formats.filter((f) => FORMATS[f]) : [formatOf(reel)];
				const queued = list.map((f) => exportReel(reel, f));
				return json(res, 202, queued[0]);
			}
		}
		m = /^\/api\/projects\/([^/]+)\/multicam$/.exec(p);
		if (m && req.method === 'POST') {
			const {prises} = await readJson(req);
			const args = ['multicam', path.join(PROJECTS, safeId(m[1]))];
			if (Array.isArray(prises) && prises.length) args.push('--prises', prises.map(safeId).join(','));
			return json(res, 202, startJob('Synchronisation des caméras par le son', async () => lastJson(await python(args)), safeId(m[1])));
		}
		if (p === '/api/visuel' && req.method === 'POST') {
			const {dossier, type, titre, duree, musique} = await readJson(req);
			const folder = path.resolve(ROOT, String(dossier || ''));
			if (!folder.startsWith(path.join(ROOT, 'media')) || !fs.existsSync(folder)) return json(res, 400, {error: 'Le dossier doit être dans media\\.'});
			const args = ['visuel', folder, '--type', type === 'evenement' ? 'evenement' : 'immobilier', '--duree', String(Number(duree) || 30)];
			if (titre) args.push('--titre', String(titre).slice(0, 80));
			if (musique) args.push('--musique', safeId(musique));
			return json(res, 202, startJob('Montage visuel (préparation des vidéos)', async () => lastJson(await python(args))));
		}
		if (p === '/api/media-folders' && req.method === 'GET') {
			const base = path.join(ROOT, 'media');
			const out = [];
			const walk = (d, depth) => {
				for (const e of fs.readdirSync(d, {withFileTypes: true})) {
					if (!e.isDirectory()) continue;
					const full = path.join(d, e.name);
					out.push(path.relative(ROOT, full));
					if (depth < 2) walk(full, depth + 1);
				}
			};
			if (fs.existsSync(base)) walk(base, 0);
			return json(res, 200, out);
		}
		if (p === '/api/product-assets' && req.method === 'POST') {
			const {data, name} = await readJson(req);
			const mm = /^data:[^;]*;base64,(.+)$/.exec(data || '');
			if (!mm || path.extname(String(name)).toLowerCase() !== '.glb') return json(res,400,{error:'Fichier GLB attendu.'});
			const buf=Buffer.from(mm[1],'base64');
			if (buf.length > 64*1024*1024 || buf.subarray(0,4).toString() !== 'glTF') return json(res,400,{error:'GLB invalide ou trop volumineux (64 Mo maximum).'});
			const filename=`${crypto.createHash('sha1').update(buf).digest('hex').slice(0,16)}.glb`;
			fs.mkdirSync(path.join(ROOT,'assets','produits'),{recursive:true});
			fs.writeFileSync(path.join(ROOT,'assets','produits',filename),buf);
			return json(res,200,{path:`assets/produits/${filename}`});
		}
		if (p === '/api/images' && req.method === 'POST') {
			// photo d'une carte animee : gardee dans assets/images (nom = empreinte du contenu)
			const {data} = await readJson(req);
			const mm = /^data:image\/(png|jpeg|webp);base64,(.+)$/.exec(data || '');
			if (!mm) return json(res, 400, {error: 'Image PNG, JPEG ou WebP attendue.'});
			const buf = Buffer.from(mm[2], 'base64');
			const name = `${crypto.createHash('sha1').update(buf).digest('hex').slice(0, 16)}.${mm[1] === 'jpeg' ? 'jpg' : mm[1]}`;
			fs.mkdirSync(path.join(ROOT, 'assets', 'images'), {recursive: true});
			fs.writeFileSync(path.join(ROOT, 'assets', 'images', name), buf);
			return json(res, 200, {path: `assets/images/${name}`});
		}
		if (p === '/api/clients' && req.method === 'GET') return json(res, 200, listClients());
		if (p === '/api/clients' && req.method === 'POST') return json(res, 200, saveClient(await readJson(req)));
		m = /^\/api\/clients\/([^/]+)$/.exec(p);
		if (m && req.method === 'DELETE') return json(res, 200, trashClient(decodeURIComponent(m[1])));
		if (p === '/api/open-folder' && req.method === 'POST') {
			const {file} = await readJson(req);
			const target = path.resolve(file || '');
			if (!target.startsWith(ROOT)) return json(res, 400, {error: "Chemin hors de l'editeur."});
			const isDir = fs.existsSync(target) && fs.statSync(target).isDirectory();
			spawn('explorer.exe', isDir ? [target] : ['/select,', target], {detached: true}).unref();
			return json(res, 200, {ok: true});
		}
		if (p === '/api/open-resolve' && req.method === 'POST') {
			const exe = 'D:\\Resolve.exe';
			if (!fs.existsSync(exe)) return json(res, 404, {error: 'DaVinci Resolve introuvable.'});
			spawn(exe, [], {detached: true}).unref();
			return json(res, 200, {ok: true});
		}
		json(res, 404, {error: 'Introuvable.'});
	} catch (e) {
		json(res, 400, {error: e.message});
	}
});

const crashLog = (kind) => (e) => {
	const line = `${new Date().toISOString()} ${kind} ${e?.stack || e}\n`;
	console.error(line);
	try {
		fs.appendFileSync(path.join(ROOT, 'runtime', 'cache', 'erreurs-serveur.log'), line);
	} catch {}
};
process.on('uncaughtException', crashLog('uncaughtException'));
process.on('unhandledRejection', crashLog('unhandledRejection'));

server.listen(PORT, HOST, () => console.log(`Editeur Sami : ${ORIGIN}`));
