// Serveur MCP de l'Editeur Sami (stdio, sans dependance) : piloter l'editeur depuis Claude
// (application Claude, onglet Code, ou Claude Code en ligne de commande).
// Protocole : JSON-RPC 2.0, un message JSON par ligne sur stdin / stdout. Rien d'autre n'est ecrit sur stdout
// (le journal va sur stderr). Il parle a l'API locale de l'editeur (app/server.mjs, http://127.0.0.1:8790) et la
// demarre si elle ne repond pas. Il ne lit jamais cles-api.env et n'ecrit rien lui-meme hors du dossier de l'editeur :
// les videos sont envoyees au serveur (les fichiers d'origine sont seulement lus).
import fs from 'node:fs';
import http from 'node:http';
import net from 'node:net';
import path from 'node:path';
import readline from 'node:readline';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const VERSION = '2.1.0';
const PROTOCOLES = ['2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05'];
const HERE = path.dirname(fileURLToPath(import.meta.url));
const isRoot = (d) => !!d && fs.existsSync(path.join(d, 'app', 'server.mjs')) && fs.existsSync(path.join(d, 'engine', 'editeur'));
// plugin charge sur place (plugins/editeur-sami/mcp) ; sinon l'editeur indique par l'environnement, ou son dossier habituel
const ROOT = path.resolve([path.join(HERE, '..', '..', '..'), process.env.EDITEUR_ROOT, process.env.CLAUDE_PROJECT_DIR, 'D:\\Tools\\editeur_sami'].find(isRoot)
	|| path.join(HERE, '..', '..', '..'));
const HOST = '127.0.0.1';
const PORT = Number(process.env.EDITEUR_PORT || 8790);
const ORIGIN = `http://${HOST}:${PORT}`;
const CACHE = path.join(ROOT, 'runtime', 'cache');
const VIDEO_EXT = new Set(['.mp4', '.mov', '.m4v', '.mkv', '.avi', '.mts', '.webm']);
const SCRIPT_EXT = new Set(['.docx', '.txt', '.pdf']);
const FORMATS = ['9:16', '16:9', '4:5', '1:1'];

const log = (...a) => process.stderr.write(`[editeur-sami] ${a.join(' ')}\n`);
console.log = log; // stdout est reserve au protocole
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const extOf = (f) => path.extname(f).toLowerCase();
const pct = (p) => `${Math.round(100 * (Number(p) || 0))} %`;
const mo = (b) => `${(b / 1048576).toFixed(b >= 1073741824 ? 0 : 1)} Mo`;

/** Refus ou probleme a montrer tel quel (phrase claire en francais). */
class Refus extends Error {}
class ErreurHttp extends Error {
	constructor(message, status) {
		super(message);
		this.status = status;
	}
}

// ---------- Environnement de l'editeur (meme que runtime/env.ps1 : tout reste dans son dossier) ----------
const envEditeur = () => {
	const env = {...process.env};
	const old = Object.keys(env).filter((k) => k.toUpperCase() === 'PATH').map((k) => env[k]).find(Boolean) || '';
	for (const k of Object.keys(env)) if (k.toUpperCase() === 'PATH') delete env[k];
	const r = (...p) => path.join(ROOT, ...p);
	return Object.assign(env, {
		EDITEUR_ROOT: ROOT, UV_CACHE_DIR: r('runtime', 'cache', 'uv'), UV_PYTHON_INSTALL_DIR: r('runtime', 'python'), UV_PROJECT_ENVIRONMENT: r('runtime', 'venv'),
		UV_LINK_MODE: 'copy', UV_PYTHON_BIN_DIR: r('runtime', 'bin'), UV_TOOL_DIR: r('runtime', 'uv-tools'), UV_TOOL_BIN_DIR: r('runtime', 'bin'), UV_NO_MODIFY_PATH: '1',
		UV_PYTHON_PREFERENCE: 'only-managed', PIP_CACHE_DIR: r('runtime', 'cache', 'pip'), npm_config_cache: r('runtime', 'cache', 'npm'),
		HF_HOME: r('models', 'huggingface'), HF_HUB_OFFLINE: '1', HF_HUB_DISABLE_SYMLINKS_WARNING: '1', TORCH_HOME: r('models', 'torch'),
		ACESTEP_CHECKPOINTS_DIR: r('models', 'acestep'), XDG_CACHE_HOME: r('runtime', 'cache'), TEMP: r('runtime', 'cache', 'tmp'), TMP: r('runtime', 'cache', 'tmp'),
		PATH: [r('runtime', 'bin'), r('runtime', 'venv', 'Scripts'), r('tools', 'ffmpeg', 'bin'), old].join(path.delimiter),
	});
};

// ---------- API HTTP de l'editeur ----------
const appel = (method, route, {body, file, timeout = 60000, onBytes} = {}) => new Promise((resolve, reject) => {
	// le serveur refuse les POST/PUT dont l'origine n'est pas exactement la sienne
	const headers = {origin: ORIGIN, accept: 'application/json'};
	let payload;
	if (body !== undefined) {
		payload = Buffer.from(JSON.stringify(body));
		Object.assign(headers, {'content-type': 'application/json', 'content-length': payload.length});
	}
	if (file) headers['content-length'] = fs.statSync(file).size;
	const req = http.request({host: HOST, port: PORT, method, path: route, headers, timeout}, (res) => {
		const chunks = [];
		res.on('data', (c) => chunks.push(c));
		res.on('error', reject);
		res.on('end', () => {
			const text = Buffer.concat(chunks).toString('utf8');
			let data = text;
			try {
				data = text ? JSON.parse(text) : null;
			} catch {}
			if (res.statusCode >= 400) reject(new ErreurHttp(data?.error || `Erreur ${res.statusCode}`, res.statusCode));
			else resolve(data);
		});
	});
	req.on('timeout', () => req.destroy(Object.assign(new Error('délai dépassé'), {code: 'ETIMEDOUT'})));
	req.on('error', reject);
	if (!file) return req.end(payload);
	const rs = fs.createReadStream(file);
	rs.on('data', (c) => onBytes?.(c.length));
	rs.on('error', (e) => req.destroy(e));
	rs.pipe(req);
});

/** Appel a l'editeur ; s'il n'est pas lance, on le demarre puis on reessaie une fois. */
const api = async (method, route, opts = {}) => {
	try {
		return await appel(method, route, opts);
	} catch (e) {
		if (e.code !== 'ECONNREFUSED' || opts.file) throw e;
		await demarrer();
		return appel(method, route, opts);
	}
};

// Un serveur deja a l'ecoute (meme lent) ne doit JAMAIS etre double : deux serveurs traiteraient la meme boite d'entree.
const portOuvert = () => new Promise((resolve) => {
	const s = net.connect({host: HOST, port: PORT});
	const fin = (v) => {
		s.destroy();
		resolve(v);
	};
	s.setTimeout(4000, () => fin(false));
	s.once('connect', () => fin(true));
	s.once('error', () => fin(false));
});
const repond = async () => {
	try {
		await appel('GET', '/api/reels', {timeout: 10000});
		return true;
	} catch (e) {
		return e instanceof ErreurHttp;
	}
};

const lancerServeur = async () => {
	fs.mkdirSync(CACHE, {recursive: true});
	// deux sessions Claude (application + terminal) peuvent demarrer l'editeur en meme temps : une seule le lance
	const lock = path.join(CACHE, 'demarrage-editeur.lock');
	try {
		fs.closeSync(fs.openSync(lock, 'wx'));
	} catch {
		const age = Date.now() - (fs.statSync(lock, {throwIfNoEntry: false})?.mtimeMs ?? 0);
		if (age < 60000) return log('demarrage deja en cours ailleurs : attente');
		fs.writeFileSync(lock, String(process.pid));
	}
	let out;
	try {
		log(`demarrage de l'editeur (${ROOT})`);
		const env = envEditeur();
		fs.mkdirSync(env.TEMP, {recursive: true});
		out = fs.openSync(path.join(CACHE, 'serveur-mcp.log'), 'a');
		fs.writeSync(out, `\n${new Date().toISOString()} demarrage par le plugin Claude\n`);
		// interface a jour, comme editeur.ps1 (sans ouvrir de navigateur)
		await new Promise((resolve) => {
			const b = spawn(process.execPath, [path.join(ROOT, 'app', 'build.mjs')], {cwd: ROOT, env, stdio: ['ignore', out, out], windowsHide: true});
			const t = setTimeout(() => b.kill(), 120000);
			b.on('error', resolve);
			b.on('exit', () => {
				clearTimeout(t);
				resolve();
			});
		});
		if (await portOuvert()) return; // lance entre-temps par quelqu'un d'autre
		spawn(process.execPath, [path.join(ROOT, 'app', 'server.mjs')], {cwd: ROOT, env, detached: true, stdio: ['ignore', out, out], windowsHide: true}).unref();
	} finally {
		if (out !== undefined) fs.closeSync(out);
		setTimeout(() => fs.rmSync(lock, {force: true}), 15000).unref();
	}
};

// EDITEUR_MCP_SANS_DEMARRAGE=1 : ne jamais lancer l'editeur (essais, ou si on prefere le lancer soi-meme)
const SANS_DEMARRAGE = process.env.EDITEUR_MCP_SANS_DEMARRAGE === '1';
let demarrage = null;
const demarrer = () => (demarrage ??= (async () => {
	try {
		if (!(await portOuvert())) {
			if (SANS_DEMARRAGE) throw new Refus("L'éditeur n'est pas lancé (démarrage automatique désactivé) : double-clique « Editeur Sami.cmd ».");
			await lancerServeur();
		}
		const limite = Date.now() + 60000;
		while (Date.now() < limite) {
			if (await repond()) return;
			await sleep(500);
		}
		throw new Refus(`L'éditeur ne démarre pas. Détails dans ${path.join(CACHE, 'serveur-mcp.log')} (ou double-clique « Editeur Sami.cmd »).`);
	} finally {
		demarrage = null;
	}
})());

const messageErreur = (e) => {
	if (e instanceof Refus) return e.message;
	if (e instanceof ErreurHttp) return `L'éditeur a répondu : ${e.message}`;
	if (e.code === 'ECONNREFUSED') return "L'éditeur n'est pas lancé et n'a pas pu démarrer (double-clique « Editeur Sami.cmd »).";
	if (e.code === 'ETIMEDOUT') return "L'éditeur ne répond pas (délai dépassé). Réessaie dans un instant ; sinon relance-le (« Editeur Sami.cmd »).";
	if (e.code === 'ECONNRESET' || e.code === 'EPIPE') return "La connexion avec l'éditeur a été coupée (redémarrage ?). Réessaie dans un instant.";
	return `Erreur inattendue : ${e.message}`;
};

// ---------- Verifications ----------
const dans = (base, p) => {
	const rel = path.relative(base, p);
	return rel === '' || (!!rel && !rel.startsWith('..') && !path.isAbsolute(rel));
};

/** Fichier ou dossier de cet ordinateur (lecture seule), hors des dossiers internes de l'editeur. */
const cheminLocal = (brut, quoi) => {
	let p = String(brut ?? '').trim().replace(/^["']+|["']+$/g, '');
	if (!p) throw new Refus(`Chemin manquant (${quoi}).`);
	if (/^[a-z][a-z0-9+.-]*:\/\//i.test(p) || /^(\\\\|\/\/)/.test(p)) throw new Refus(`Seulement des fichiers de cet ordinateur (pas de lien internet ni de dossier réseau) : ${p}`);
	p = path.resolve(ROOT, p);
	if (path.basename(p).toLowerCase() === 'cles-api.env') throw new Refus('Ce fichier est privé : les outils de l\'éditeur ne le lisent jamais.');
	let st;
	try {
		st = fs.statSync(p);
	} catch {
		throw new Refus(`Introuvable : ${p}`);
	}
	const media = path.join(ROOT, 'media');
	if (dans(path.join(media, 'entree'), p)) throw new Refus(`Déjà dans la boîte d'entrée (${p}) : l'éditeur la monte tout seul, rien à envoyer.`);
	if (dans(ROOT, p) && !(dans(media, p) && p !== media) && !dans(path.join(ROOT, 'livraisons'), p)) {
		throw new Refus(`Ce dossier fait partie de l'éditeur (programmes, projets, caches) : ${p}. Choisis des vidéos brutes (ex. media\\rushs, ou n'importe quel dossier hors de l'éditeur).`);
	}
	if (st.isDirectory() && (path.dirname(p) === p || dans(p, ROOT))) throw new Refus(`Dossier trop large (disque entier ou dossier de l'éditeur) : ${p}. Choisis le dossier des vidéos.`);
	if (!st.isDirectory() && !st.isFile()) throw new Refus(`Pas un fichier : ${p}`);
	return {path: p, dir: st.isDirectory(), size: st.isFile() ? st.size : 0};
};

/** Video produite par l'editeur (export de livraisons\, ou apercu de runtime\cache\tmp\) a controler : lecture seule. */
const cheminVideoEditeur = (brut) => {
	let p = String(brut ?? '').trim().replace(/^["']+|["']+$/g, '');
	if (!p) throw new Refus('Chemin du fichier à contrôler manquant.');
	if (/^[a-z][a-z0-9+.-]*:\/\//i.test(p) || /^(\\\\|\/\/)/.test(p)) throw new Refus(`Seulement un fichier de cet ordinateur : ${p}`);
	p = path.resolve(ROOT, p);
	if (!dans(path.join(ROOT, 'livraisons'), p) && !dans(path.join(ROOT, 'runtime', 'cache', 'tmp'), p)) {
		throw new Refus(`Le contrôle lit seulement les vidéos de l'éditeur (livraisons\\… ou un aperçu de runtime\\cache\\tmp) : ${p}`);
	}
	if (!VIDEO_EXT.has(extOf(p))) throw new Refus(`Pas une vidéo : ${p}`);
	if (!fs.statSync(p, {throwIfNoEntry: false})?.isFile()) throw new Refus(`Introuvable : ${p}`);
	return p;
};

/** Nom accepte par la boite d'entree (caracteres interdits sous Windows, longueur). */
const propre = (s) => {
	let n = String(s).replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').trim().replace(/[. ]+$/, '');
	if (n.length > 140) {
		const e = path.extname(n);
		n = n.slice(0, 140 - e.length) + e;
	}
	return n && !n.startsWith('.') ? n : `_${n}`;
};

/** Videos et scripts d'un dossier (sous-dossiers compris) ; les autres fichiers sont ignores. */
const lister = (dir, notes, max = 400) => {
	const out = [];
	const walk = (d, rel, depth) => {
		for (const e of fs.readdirSync(d, {withFileTypes: true}).sort((a, b) => a.name.localeCompare(b.name))) {
			if (e.name.startsWith('.') || e.name.startsWith('~$')) continue;
			const f = path.join(d, e.name);
			const r = rel ? `${rel}/${e.name}` : e.name;
			if (e.isDirectory()) {
				if (depth < 4) walk(f, r, depth + 1);
				continue;
			}
			if (!e.isFile()) continue;
			const x = extOf(e.name);
			if (['.doc', '.pages', '.rtf'].includes(x)) notes.push(`Script ignoré (enregistre-le en .docx, .txt ou PDF avec texte) : ${r}`);
			if (!VIDEO_EXT.has(x) && !SCRIPT_EXT.has(x) || e.name.toLowerCase() === 'cles-api.env') continue;
			out.push({src: f, rel: r, size: fs.statSync(f).size});
			if (out.length > max) throw new Refus(`Plus de ${max} fichiers dans ${dir} : dépose moins de vidéos à la fois.`);
		}
	};
	walk(dir, '', 0);
	return out;
};

const resume = (dir) => {
	const entries = fs.readdirSync(dir, {withFileTypes: true}).filter((e) => !e.name.startsWith('.') && !e.name.startsWith('~$'));
	const videos = entries.filter((e) => e.isFile() && VIDEO_EXT.has(extOf(e.name))).length;
	const scripts = entries.filter((e) => e.isFile() && SCRIPT_EXT.has(extOf(e.name))).map((e) => e.name);
	const sous = entries.filter((e) => e.isDirectory()).length;
	return `${dir} : ${videos} vidéo(s), ${sous} sous-dossier(s)${scripts.length ? `, script(s) : ${scripts.join(', ')}` : ', aucun script'}`;
};

// ---------- Aides communes ----------
const STATUT = {attente: 'En file (montée après les autres)', travail: 'Montage en cours', pret: 'Prête : à regarder', pris: 'Prise ✓ (exportée)', erreur: 'Erreur', retire: 'Retirée'};
const TACHE = {queued: 'en attente dans la file', running: 'en cours', done: 'terminé', failed: 'échec', cancelled: 'annulé', interrompu: 'interrompu (éditeur redémarré : relance « prendre »)'};
const PRETE = (i) => !!i.project && (i.status === 'pret' || i.status === 'pris');

const revision = () => api('GET', '/api/revision');
const listeStyles = async () => (await api('GET', '/api/styles')).montage;

/** Video de la liste Revision : par identifiant (12 caracteres) ou par son titre / nom de fichier. */
const trouverVideo = async (v) => {
	const q = String(v ?? '').trim();
	if (!q) throw new Refus('Indique la vidéo (identifiant donné par l\'outil etat, ou son titre).');
	const {items} = await revision();
	const exact = items.find((i) => i.id === q);
	if (exact) return exact;
	const low = q.toLowerCase();
	let found = items.filter((i) => [i.title, i.name].some((t) => String(t || '').toLowerCase() === low));
	if (!found.length) found = items.filter((i) => [i.title, i.name].some((t) => String(t || '').toLowerCase().includes(low)));
	if (found.length === 1) return found[0];
	if (!found.length) throw new Refus(`Vidéo introuvable : « ${q} ». Appelle etat pour voir les identifiants.`);
	throw new Refus(`Plusieurs vidéos correspondent à « ${q} » : ${found.slice(0, 8).map((i) => `[${i.id}] ${i.title || i.name}`).join(' ; ')}. Donne l'identifiant.`);
};

const verifierStyle = async (id) => {
	const s = String(id ?? '').trim();
	const all = await listeStyles();
	const found = all.find((t) => t.id === s) || all.find((t) => t.name.toLowerCase() === s.toLowerCase());
	if (!found) throw new Refus(`Style inconnu « ${s} ». Styles : ${all.map((t) => `${t.id} (${t.name})`).join(', ')}.`);
	return found;
};

// ---------- Controle qualite (rapport du moteur engine/editeur/controle.py, ou son resume) ----------
const GRAVITE = {bloquant: 'BLOQUANT', important: 'IMPORTANT', conseil: 'conseil'};
const tc = (t) => {
	const m = Math.floor(Math.max(0, t) / 60);
	return `${m}:${(Math.max(0, t) - 60 * m).toFixed(1).padStart(4, '0').replace('.', ',')}`;
};
const virgule = (n) => String(Math.round(Number(n) * 10) / 10).replace('.', ',');
const compteTexte = (c = {}) => ['bloquant', 'important', 'conseil'].map((g) => `${c[g] ?? 0} ${g}${(c[g] ?? 0) > 1 ? 's' : ''}`).join(', ');
/** Rapport lisible : note, verdict, puis les problemes du plus grave au moins grave (moment, message, suggestion). */
const texteControle = (r, n = 12) => {
	if (!r || typeof r.note !== 'number') return 'Aucun rapport de contrôle qualité.';
	const constats = Array.isArray(r.constats) ? r.constats : [];
	const out = [`Note : ${virgule(r.note)}/10 — ${r.verdict} (${compteTexte(r.compte)})${r.date ? ` ; contrôlé le ${r.date}` : ''}`
		+ `${r.video ? ` ; vidéo contrôlée : ${r.video}` : ' ; contrôle du montage (sans rendu)'}.`];
	for (const c of constats.slice(0, n)) {
		const quand = c.temps === null || c.temps === undefined ? 'toute la vidéo' : tc(c.temps) + (c.fin !== null && c.fin !== undefined && c.fin - c.temps > 0.15 ? `–${tc(c.fin)}` : '');
		out.push(`• [${GRAVITE[c.gravite] || c.gravite}] ${quand} : ${c.message}`, `  → ${c.suggestion}`);
		const image = /image : (\S.*?\.png)/.exec(String(c.preuve || ''))?.[1];
		if (image) out.push(`  Image de preuve : ${image}`);
	}
	const total = r.total ?? constats.length;
	if (total > Math.min(n, constats.length)) out.push(`(+ ${total - Math.min(n, constats.length)} point(s) moins grave(s) dans le rapport complet)`);
	if (!constats.length) out.push('Aucun problème détecté.');
	return out.join('\n');
};

// ---------- Claude (IA en ligne d'Anthropic, en option et PAYANTE : credit de l'utilisateur) ----------
// Le serveur ne donne jamais la cle (seulement « presente » / « absente ») ; les appels payants partent seulement par
// claude_critique et consigne, sur demande explicite de l'utilisateur.
const argent = (x) => {
	const v = Number(x) || 0;
	return v > 0 && v < 0.005 ? '< 0,01 $' : `${v.toFixed(2).replace('.', ',')} $`;
};
const NOMS_CLAUDE = {'claude-sonnet-5-5': 'Sonnet 5.5', 'claude-haiku-4-5': 'Haiku 4.5', 'claude-opus-5-5': 'Opus 5.5'};
const nomClaude = (m) => NOMS_CLAUDE[m] || String(m || '?').replace(/^claude-/, '');
/** Un editeur lance avant cette version n'a pas les routes de Claude : phrase claire au lieu de « Introuvable. ». */
const routeClaude = async (method, route, opts) => {
	try {
		return await api(method, route, opts);
	} catch (e) {
		if (e instanceof ErreurHttp && e.status === 404 && /Introuvable\.$/.test(e.message)) throw new Refus('Claude n’est pas encore actif dans l’éditeur lancé : relance-le (« Editeur Sami.cmd »).');
		throw e;
	}
};
const estimationTache = (s, tache) => {
	const m = s?.modeles_taches?.[tache] || s?.modele;
	const e = (s?.modeles || []).find((x) => x.id === m)?.estimation || (s?.estimation?.modele === m ? s.estimation : null);
	return typeof e?.[tache] === 'number' ? e[tache] : null;
};
const texteStatutClaude = (s) => {
	if (s.indisponible) return `Claude : indisponible (${s.raison}).`;
	const out = [`Claude (IA en ligne, en option et payante) : ${s.actif ? 'allumé' : 'éteint'} · clé ${s.cle ? 'présente' : 'absente (cles-api.env)'} · modèle ${nomClaude(s.modele)}`
		+ `${s.pret ? ' · prêt' : ''}.`];
	if (!s.pret && s.raison) out.push(`Pas prêt : ${s.raison}`);
	if (s.avertissement) out.push(`Attention : ${s.avertissement}`);
	const taches = Object.entries(s.modeles_taches || {}).filter(([, m]) => m).map(([t, m]) => `${t} → ${nomClaude(m)}`);
	if (taches.length) out.push(`Modèle par tâche : ${taches.join(', ')}.`);
	out.push(`Dépensé aujourd’hui : ${argent(s.depense_jour)} (${s.appels_jour || 0} appel(s)) · ce mois : ${argent(s.depense_mois)} · crédit restant estimé : ${argent(s.credit_restant_estime)}`
		+ ` (départ ${argent(s.credit_depart)} le ${s.credit_date}).`);
	if (s.plafonds) out.push(`Plafonds : ${argent(s.plafonds.video)} par vidéo, ${argent(s.plafonds.jour)} par jour, ${argent(s.plafonds.mois)} par mois.`);
	if (s.estimation?.texte) out.push(`Estimation : ${s.estimation.texte}`);
	const e = estimationTache(s, 'critique');
	if (e !== null) out.push(`Une critique d’images coûte environ ${argent(e)} ; critique automatique après export : ${s.critique_auto ? 'oui' : 'non'}.`);
	return out.join('\n');
};
/** Resultat de « Dis a l'IA » (python -m editeur.consigne) : changements, refus, question, moteur, cout, version « avant ». */
const texteConsigne = (r, simuler = false) => {
	if (!r || typeof r !== 'object') return 'Résultat illisible.';
	const out = [];
	if (r.question) out.push(`L’éditeur demande une précision (rien n’a été changé) : ${r.question}`);
	const ch = Array.isArray(r.changements) ? r.changements : [];
	if (ch.length) {
		out.push(simuler ? 'Ce qui serait fait (essai : rien n’est changé) :' : 'Changements faits :');
		for (const c of ch) out.push(`• ${typeof c.t === 'number' ? `${tc(c.t)} — ` : ''}${c.quoi ?? ''}${c.detail ? ` : ${c.detail}` : ''}`);
	} else if (!r.question) out.push(r.ok === false ? 'Rien n’a été changé.' : 'Aucun changement.');
	const refus = Array.isArray(r.refus) ? r.refus : [];
	if (refus.length) out.push('Pas fait :', ...refus.map((x) => `• ${x.demande ?? ''}${x.raison ? ` → ${x.raison}` : ''}`));
	if (r.raison && r.ok === false) out.push(`Raison : ${r.raison}`);
	const moteur = {claude: 'Claude', local: 'IA locale', regles: 'règles simples'}[r.moteur] || r.moteur;
	if (moteur) out.push(`Fait par : ${moteur}${typeof r.cout === 'number' ? ` · coût ${argent(r.cout)}` : ''}${r.note_ajoutee ? ' · une note a été ajoutée au montage' : ''}.`);
	if (!simuler && r.avant && ch.length) out.push(`Pour annuler : restaurer_version avec le fichier « ${r.avant} » (version gardée avant la demande).`);
	return out.join('\n');
};
/** Avis de Claude sur les images (python -m editeur.critique_claude) : note, verdict, problemes avec leur moment. */
const GRAVITES_AVIS = {bloquant: 'BLOQUANT', important: 'important', conseil: 'conseil'};
const texteAvis = (r) => {
	const a = r?.avis && typeof r.avis === 'object' ? r.avis : r;
	// avis non obtenu (Claude eteint, plafond, credit, erreur) : critique_claude.py rend ok = false et « message » (ou « detail »)
	if (r?.ok === false || a?.ok === false) return `Avis de Claude non obtenu : ${a?.message || a?.raison || a?.detail || r?.message || 'raison inconnue'}`;
	const liste = [a?.problemes, a?.problems, a?.constats].find(Array.isArray) || [];
	const prix = a?.cache ? ' (déjà payé : gratuit cette fois)' : typeof r?.cout === 'number' ? ` (coût ${argent(r.cout)})` : '';
	const out = [`Avis de Claude${typeof a?.note === 'number' ? ` : ${virgule(a.note)}/10` : ''}${a?.verdict ? ` — ${a.verdict}` : ''}${prix}.`];
	for (const p of liste.slice(0, 20)) {
		const t = p?.t ?? p?.temps ?? p?.debut;
		const g = GRAVITES_AVIS[p?.gravite] ? `[${GRAVITES_AVIS[p.gravite]}] ` : '';
		out.push(`• ${g}${typeof t === 'number' ? tc(t) : 'toute la vidéo'} : ${p?.texte ?? p?.probleme ?? p?.message ?? ''}${p?.suggestion ? ` → ${p.suggestion}` : ''}`);
	}
	if (a?.prochaine_amelioration) out.push(`À faire en premier : ${a.prochaine_amelioration}`);
	if (!liste.length) out.push('Aucun problème signalé dans les images.');
	return out.join('\n');
};

const ligneTache = (j) => {
	const quoi = j.kind === 'export' ? `Export « ${j.title} »` : j.stage || 'Tâche';
	const etat = TACHE[j.status] || j.status;
	const parts = [`[${j.id}] ${quoi} : ${etat}`];
	if (j.status === 'running' || j.status === 'queued') parts.push(`${j.stage || ''} ${pct(j.progress)}`.trim());
	if (j.status === 'done' && j.seconds !== undefined) parts.push(`en ${j.seconds} s`);
	let t = parts.join(' · ');
	if (j.out || j.result?.out) t += `\n  Fichier : ${j.out || j.result.out}`;
	if (j.error && j.status !== 'done') t += `\n  Problème : ${j.error}`;
	if (j.kind === 'export' && j.controle) {
		const c = j.controle;
		t += c.etat === 'done' ? `\n  Contrôle qualité de la vidéo : ${virgule(c.note)}/10 — ${c.verdict} (${compteTexte(c.compte)})`
			: c.etat === 'failed' ? `\n  Contrôle qualité de la vidéo impossible : ${c.erreur}` : `\n  Contrôle qualité de la vidéo : ${c.etat === 'running' ? 'en cours' : 'en attente'}`;
	}
	if (j.kind !== 'export' && j.status === 'done' && j.result) {
		const indent = (s) => s.split('\n').map((l) => `  ${l}`).join('\n');
		const pasServi = j.result.message || j.result.raison || j.result.detail; // critique : « message » ; cerveau : « raison »
		if (j.claude && j.result.ok === false && pasServi && !Array.isArray(j.result.changements)) t += `\n  Claude n’a pas servi : ${pasServi}`;
		else if (Array.isArray(j.result.changements) || (j.result.question !== undefined && 'refus' in j.result)) t += `\n${indent(texteConsigne(j.result))}`;
		else if (j.claude && (j.result.avis || Array.isArray(j.result.problemes) || Array.isArray(j.result.problems))) t += `\n${indent(texteAvis(j.result))}`;
		else if (j.result.id && j.result.name) t += `\n  Nouveau style créé : « ${j.result.name} » (id ${j.result.id}).${j.result.description ? ` ${j.result.description}` : ''}`;
		else if (typeof j.result.note === 'number' && Array.isArray(j.result.constats)) {
			t += `\n${texteControle(j.result).split('\n').map((l) => `  ${l}`).join('\n')}`;
			if (j.result.reelUtilise) t += `\n  (reel comparé : ${j.result.reelUtilise})`;
		} else if (typeof j.result.resume === 'string') t += `\n  Résultat : ${j.result.resume.slice(0, 1500)}`;
		else t += `\n  Résultat : ${JSON.stringify(j.result).slice(0, 1500)}`;
	}
	return t;
};

const ligneVideo = (i, noms) => {
	const lignes = [`• [${i.id}] ${i.title || i.name} — ${STATUT[i.status] || i.status}${i.status === 'travail' ? ` · ${i.stage} (${pct(i.progress)})` : ''}`];
	const info = [`Dépôt : ${i.lot} / ${i.name}`];
	if (i.typeLabel) info.push(`Sujet : ${i.typeLabel} (${i.type})`);
	if (i.style) info.push(`Style : ${noms[i.style] ? `${noms[i.style]} (${i.style})` : i.style}`);
	if (i.forceStyle && i.status === 'attente') info.push(`style imposé : ${i.forceStyle}`);
	lignes.push(`  ${info.join(' · ')}`);
	if (i.reason) lignes.push(`  Pourquoi ce sujet : ${i.reason}`);
	if (i.broll) lignes.push(`  Plans de coupe ajoutés : ${i.broll}`);
	if (i.ia === false) lignes.push('  Montée sans IA locale (règles simples).');
	if (i.alerts?.length) lignes.push(`  ⚠ ${i.alerts.length} phrase(s) du script absente(s) des prises : ${i.alerts.slice(0, 3).join(' ; ')}${i.alerts.length > 3 ? ' ; …' : ''}`);
	if (i.error) lignes.push(`  Problème : ${i.error}`);
	if (i.controle && typeof i.controle.note === 'number') lignes.push(`  Contrôle qualité du montage : ${virgule(i.controle.note)}/10 — ${i.controle.verdict} (${compteTexte(i.controle.compte)}) ; ${i.controle.date} (détails : controle)`);
	if (i.claude && (i.claude.cout > 0 || i.claude.nb)) {
		const g = i.claude.groupes || {};
		const parts = [['cerveau', 'idées'], ['critique', 'relecture'], ['consigne', 'demandes']].filter(([k]) => g[k]).map(([k, nom]) => `${nom} ${g[k].n} (${argent(g[k].cout)})`);
		lignes.push(`  Claude : ${argent(i.claude.cout)} dépensés pour cette vidéo${parts.length ? ` — ${parts.join(', ')}` : ''} (détails : claude_couts)`);
	}
	if (i.iaEnCours) lignes.push(`  L’IA travaille sur cette vidéo : ${i.iaEnCours.stage} (tâche ${i.iaEnCours.job}).`);
	for (const e of i.exports || (i.export ? [i.export] : [])) {
		const c = e.controle && typeof e.controle.note === 'number' ? ` · contrôle ${virgule(e.controle.note)}/10 (${e.controle.verdict})`
			: e.controleEtat ? ` · contrôle ${e.controleEtat === 'running' ? 'en cours' : 'en attente'}` : e.controle?.erreur ? ` · contrôle impossible : ${e.controle.erreur}` : '';
		lignes.push(`  Export ${e.format || ''} : ${TACHE[e.status] || e.status} (tâche ${e.job}) → ${e.out}${e.error ? ` · ${e.error}` : ''}${c}`);
	}
	for (const out of i.taken?.outs || (i.taken?.out ? [i.taken.out] : [])) lignes.push(`  Vidéo finale : ${out}`);
	if (i.project) lignes.push(`  Projet : projects\\${i.project} (version ${i.rid})`);
	return lignes.join('\n');
};

// ---------- Outils ----------
const S = (description, extra = {}) => ({type: 'string', description, ...extra});
const VIDEO = S('Identifiant de la vidéo (12 caractères, donné par l\'outil etat) ou son titre / nom de fichier.');

/** Montage réellement ouvert par une fiche de la Révision. */
const montageDe = async (video) => {
	const item = await trouverVideo(video);
	if (!item.project || !item.rid) throw new Refus(`« ${item.title || item.name} » n'a pas encore de montage à inspecter.`);
	const opened = await api('GET', `/api/reels/${encodeURIComponent(item.project)}/${encodeURIComponent(item.rid)}/open`);
	return {item, reel: opened.reel};
};

const dureeReel = (r) => (r.clips || []).reduce((n, c) => n + Math.max(0, Number(c.out) - Number(c.in)) / (Number(c.speed) || 1), 0);
const resumerReel = (item, r) => {
	const words = (r.clips || []).flatMap((c) => c.words || []).filter((w) => !w.cut && !w.hide);
	const hl = words.filter((w) => w.hl);
	const visibles = (r.graphics || []).filter((g) => !g.suggested).length;
	const proposes = (r.graphics || []).filter((g) => g.suggested).length;
	return [
		`Montage « ${r.title || item.title || item.name} » — ${dureeReel(r).toFixed(1).replace('.', ',')} s — ${r.width}×${r.height}`,
		`Vidéo : [${item.id}] ${item.title || item.name} · projet ${item.project} · reel ${item.rid}`,
		`Style : ${r.template || item.style || '?'} · sous-titres ${r.style?.preset || '?'} · ${r.clips?.length || 0} plan(s)`,
		`Texte : ${words.length} mot(s) visibles, ${hl.length} en couleur (${words.length ? Math.round(1000 * hl.length / words.length) / 10 : 0} %).`,
		`Habillage : ${(r.broll || []).length} plan(s) de coupe, ${visibles} graphisme(s) posé(s), ${proposes} proposé(s), ${(r.styleScenes || []).filter((s) => !s.hidden).length} scène(s) de style.`,
		`Bandeau : ${r.banner?.enabled && r.banner?.text ? `« ${r.banner.text} »` : 'aucun'} · musique : ${r.music?.enabled ? r.music.mood || r.music.file || 'active' : 'aucune'} · voix : ${r.audio?.voice || 'défaut'}.`,
		r.sobriete?.resume ? `Relecture : ${r.sobriete.resume}` : 'Relecture : aucun rapport enregistré.',
		(r.suggestions?.broll || []).length ? `Plans de coupe proposés : ${r.suggestions.broll.length}.` : 'Plans de coupe proposés : aucun.',
	].join('\n');
};

const OUTILS = [
	{
		name: 'etat',
		title: 'État de la Révision',
		description: 'Liste « Révision » de l\'Éditeur Sami : chaque vidéo déposée (identifiant, sujet détecté, style, état du montage automatique et progression, '
			+ 'alertes du script, erreurs, export, vidéo finale) et la file d\'exports. À appeler d\'abord pour connaître les identifiants des vidéos.',
		inputSchema: {type: 'object', properties: {
			filtre: S('a_faire (défaut : en file, en montage, prêtes, en erreur) · tout · pret · erreur · pris (déjà exportées)', {enum: ['a_faire', 'tout', 'pret', 'erreur', 'pris']}),
			limite: {type: 'integer', minimum: 1, maximum: 200, description: 'Nombre maximum de vidéos affichées (les plus récentes), défaut 40.'},
		}, additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async ({filtre = 'a_faire', limite = 40}) => {
			const [rev, file, styles] = await Promise.all([revision(), api('GET', '/api/queue'), listeStyles().catch(() => [])]);
			const noms = Object.fromEntries(styles.map((s) => [s.id, s.name]));
			const garde = {a_faire: ['attente', 'travail', 'pret', 'erreur'], tout: null, pret: ['pret'], erreur: ['erreur'], pris: ['pris']}[filtre];
			if (garde === undefined) throw new Refus('filtre : a_faire, tout, pret, erreur ou pris.');
			const n = Math.min(200, Math.max(1, Number(limite) || 40));
			const compte = (s) => rev.items.filter((i) => i.status === s).length;
			const out = [`Éditeur Sami — Révision (interface : ${ORIGIN})`,
				`${rev.items.length} vidéo(s) : ${compte('pret')} à regarder, ${compte('travail')} en montage, ${compte('attente')} en file, ${compte('erreur')} en erreur, `
				+ `${compte('pris')} prise(s). Montage automatique ${rev.busy ? 'en cours' : 'au repos'}.`, `Boîte d'entrée : ${rev.entree}`];
			const items = rev.items.filter((i) => !garde || garde.includes(i.status)).slice(-n);
			out.push('', items.length ? `Vidéos (${filtre}) :` : `Aucune vidéo (${filtre}).`, ...items.map((i) => ligneVideo(i, noms)));
			const actives = file.filter((j) => j.status === 'queued' || j.status === 'running');
			const recentes = file.filter((j) => !actives.includes(j)).slice(0, 5);
			out.push('', actives.length ? 'File d\'exports (en cours / en attente) :' : 'File d\'exports : vide.', ...actives.map((j) => `• ${ligneTache(j)}`));
			if (recentes.length) out.push('Derniers exports :', ...recentes.map((j) => `• ${ligneTache(j)}`));
			return out.join('\n');
		},
	},
	{
		name: 'monter',
		title: 'Déposer des vidéos à monter',
		description: 'Dépose des vidéos brutes dans l\'Éditeur Sami pour qu\'il les monte tout seul (sujet détecté → style adapté → montage complet), '
			+ 'une à la fois, dans la liste Révision. Travail long (carte graphique) : seulement quand l\'utilisateur le demande. Les fichiers d\'origine '
			+ 'sont seulement lus (une copie va dans media\\entree\\<dépôt>). Ensuite : etat pour suivre.',
		inputSchema: {type: 'object', properties: {
			chemins: {type: 'array', minItems: 1, maxItems: 100, items: {type: 'string'},
				description: 'Chemins complets de vidéos (mp4, mov, m4v, mkv, avi, mts, webm) et/ou de dossiers sur cet ordinateur. Un script .docx/.txt/.pdf peut aussi être donné ici.'},
			dossier: S('Obligatoire si un chemin est un dossier. une_video : le dossier contient les prises d\'UNE même vidéo (avec son script éventuel). '
				+ 'plusieurs_videos : chaque vidéo du dossier est montée à part (chaque sous-dossier = les prises d\'une vidéo ; un script seul à la racine = tout le dossier suit ce script).',
			{enum: ['une_video', 'plusieurs_videos']}),
			script: S('Script Word (.docx), texte (.txt) ou PDF avec texte (.pdf), facultatif. Avec une seule vidéo ou un seul dossier : c\'est son script. Avec plusieurs : tout le dépôt suit ce script (une vidéo par partie du script).'),
			client: S('Identifiant de la charte client (logo, couleurs), voir l\'outil styles. Facultatif.'),
		}, required: ['chemins'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({chemins, dossier, script, client}, ctx) => {
			if (!Array.isArray(chemins) || !chemins.length) throw new Refus('Donne au moins une vidéo ou un dossier (chemins).');
			if (chemins.length > 100) throw new Refus('100 chemins au maximum à la fois.');
			if (dossier !== undefined && !['une_video', 'plusieurs_videos'].includes(dossier)) throw new Refus('dossier : une_video ou plusieurs_videos.');
			const entrees = chemins.map((c) => cheminLocal(c, 'vidéo ou dossier'));
			const dossiers = entrees.filter((e) => e.dir);
			if (dossiers.length && !dossier) {
				throw new Refus(`Précise « dossier » : une_video (les fichiers sont des prises d'une même vidéo) ou plusieurs_videos (chaque vidéo est montée à part).\n${dossiers.map((d) => resume(d.path)).join('\n')}`);
			}
			const notes = [];
			const fichiers = [];
			// noms deja pris a la racine du depot : un second « pub.mp4 » (ou dossier « Tournage ») devient « pub (2).mp4 »
			const racine = new Set();
			const libre = (name, dir) => {
				const p = dir ? {name, ext: ''} : path.posix.parse(name);
				let n = name;
				for (let k = 2; racine.has(n.toLowerCase()); k++) n = `${p.name} (${k})${p.ext}`;
				racine.add(n.toLowerCase());
				return n;
			};
			for (const e of entrees) {
				if (!e.dir) {
					if (!VIDEO_EXT.has(extOf(e.path)) && !SCRIPT_EXT.has(extOf(e.path))) {
						throw new Refus(`Pas une vidéo ni un script : ${e.path} (vidéos : mp4, mov, mkv, avi, webm ; scripts : .docx, .txt ou .pdf).`);
					}
					fichiers.push({src: e.path, rel: libre(propre(path.basename(e.path)), false), size: e.size});
					continue;
				}
				const liste = lister(e.path, notes);
				if (!liste.some((f) => VIDEO_EXT.has(extOf(f.rel)))) throw new Refus(`Aucune vidéo dans ${e.path}.`);
				if (dossier === 'une_video') {
					const prefixe = libre(propre(path.basename(e.path)), true);
					for (const f of liste) fichiers.push({...f, rel: [prefixe, ...f.rel.split('/').map(propre)].join('/')});
					continue;
				}
				const sous = new Map();
				for (const f of liste) {
					const segs = f.rel.split('/').map(propre);
					if (segs.length === 1) segs[0] = libre(segs[0], false);
					else {
						if (!sous.has(segs[0])) sous.set(segs[0], libre(segs[0], true));
						segs[0] = sous.get(segs[0]);
					}
					fichiers.push({...f, rel: segs.join('/')});
				}
			}
			if (!fichiers.some((f) => VIDEO_EXT.has(extOf(f.rel)))) throw new Refus('Aucune vidéo à monter (seulement des scripts).');
			if (script) {
				const s = cheminLocal(script, 'script');
				const x = extOf(s.path);
				if (s.dir) throw new Refus(`Le script doit être un fichier : ${s.path}`);
				if (!SCRIPT_EXT.has(x)) throw new Refus(`Script : Word (.docx), texte (.txt) ou PDF (.pdf) seulement (${s.path}).`);
				let rel;
				if (entrees.length === 1 && !entrees[0].dir) rel = propre(`${path.parse(fichiers[0].rel).name}${x}`); // meme nom que la video : c'est son script
				else if (entrees.length === 1 && dossier === 'une_video') {
					const pre = fichiers[0].rel.split('/')[0];
					if (fichiers.some((f) => SCRIPT_EXT.has(extOf(f.rel)) && f.rel.split('/').length === 2)) throw new Refus(`Le dossier ${entrees[0].path} contient déjà un script : enlève l'option script (ou l'autre script).`);
					rel = `${pre}/${propre(path.basename(s.path))}`;
				} else {
					rel = libre(propre(path.basename(s.path)), false);
					notes.push(`Tout le dépôt suit le script ${path.basename(s.path)} (une vidéo par partie du script).`);
				}
				fichiers.push({src: s.path, rel, size: s.size});
			}
			if (client) {
				const clients = await api('GET', '/api/clients');
				if (!clients.some((c) => c.client === client)) {
					throw new Refus(`Charte client inconnue « ${client} ». Chartes : ${clients.map((c) => `${c.client} (${c.name})`).join(', ') || 'aucune (à créer dans l\'interface, onglet Style)'}.`);
				}
			}
			const total = fichiers.reduce((a, f) => a + f.size, 0);
			const {lot} = await api('POST', '/api/entree/lot', {body: {client: client || null}});
			let envoye = 0;
			let dernier = 0;
			for (const [k, f] of fichiers.entries()) {
				const msg = `Envoi ${k + 1}/${fichiers.length} : ${f.rel}`;
				ctx.progress(envoye, total, msg);
				try {
					await appel('PUT', `/api/entree/${encodeURIComponent(lot)}/${f.rel.split('/').map(encodeURIComponent).join('/')}`, {file: f.src, timeout: 120000, onBytes: (b) => {
						envoye += b;
						if (envoye - dernier > total / 50) {
							dernier = envoye;
							ctx.progress(envoye, total, msg);
						}
					}});
				} catch (e) {
					throw new Refus(`Envoi interrompu sur ${f.rel} : ${messageErreur(e)}\nDépôt « ${lot} » : les ${k} fichier(s) déjà reçus seront montés dans environ 2 minutes ; retire-les de la Révision (outil retirer) si tu n'en veux pas.`);
				}
			}
			const rev = await api('POST', `/api/entree/${encodeURIComponent(lot)}/fin`, {body: {}});
			const items = rev.items.filter((i) => i.lot === lot);
			return [`Dépôt « ${lot} » : ${fichiers.length} fichier(s) envoyé(s) (${mo(total)})${client ? `, charte ${client}` : ''}.`,
				items.length ? `${items.length} vidéo(s) à monter (une à la fois, tout seul) :` : 'Les vidéos apparaîtront dans la Révision dans quelques secondes.',
				...items.map((i) => `• [${i.id}] ${i.name} — ${STATUT[i.status] || i.status}`), ...notes,
				'Suis l\'avancement avec etat ; chaque vidéo prête se regarde dans l\'interface (ouvrir).'].join('\n');
		},
	},
	{
		name: 'styles',
		title: 'Styles de montage',
		description: 'Styles de montage disponibles (dont ceux créés depuis une vidéo de référence), le style choisi automatiquement pour chaque sujet '
			+ '(styles\\types.json) et les chartes clients (option client de monter).',
		inputSchema: {type: 'object', properties: {}, additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async () => {
			const [styles, types, clients] = await Promise.all([listeStyles(), api('GET', '/api/types'), api('GET', '/api/clients')]);
			const noms = Object.fromEntries(styles.map((s) => [s.id, s.name]));
			const court = (t) => (String(t || '').length > 220 ? `${String(t).slice(0, 217)}…` : String(t || ''));
			return ['Styles de montage (id — nom ; l\'outil galerie les range par catégorie, avec leur aperçu) :',
				...styles.map((s) => `• ${s.id} — ${s.name}${s.category ? ` [${s.category}]` : ''}${s.perso ? ' [mon style]' : ''}${s.reference || s.id.startsWith('ref-') ? ' [créé depuis une vidéo de référence]' : ''}${['immobilier', 'evenement'].includes(s.id) ? ' [vidéos sans parole]' : ''} : ${court(s.description)}`),
				'', 'Style choisi automatiquement selon le sujet détecté (sujet → style) :',
				...Object.entries(types).map(([k, t]) => `• ${k} — ${t.label} → ${t.style} (${noms[t.style] || 'style introuvable'})`),
				'', clients.length ? 'Chartes clients :' : 'Chartes clients : aucune (à créer dans l\'interface, onglet Style).', ...clients.map((c) => `• ${c.client} — ${c.name}`)].join('\n');
		},
	},
	{
		name: 'galerie',
		title: 'Galerie de styles',
		description: 'Galerie des styles de montage telle que dans l\'écran « Autre style » : styles rangés par catégorie (Classiques, Pub, UGC, Cinéma, '
			+ 'Motion, Tech, Produit…), avec leur description et le chemin de leur image d\'aperçu. Lecture seule : pour appliquer un style, changer_style.',
		inputSchema: {type: 'object', properties: {
			categorie: S('Seulement cette catégorie (nom affiché, ex. « Classiques ») ; sans valeur : toutes.'),
		}, additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async ({categorie}) => {
			const styles = await listeStyles();
			const cat = (s) => s.category || 'Classiques';
			const groupes = new Map();
			for (const s of styles) groupes.set(cat(s), [...(groupes.get(cat(s)) ?? []), s]);
			const voulu = String(categorie ?? '').trim().toLowerCase();
			const noms = [...groupes.keys()];
			const choisis = voulu ? noms.filter((n) => n.toLowerCase() === voulu || n.toLowerCase().includes(voulu)) : noms;
			if (!choisis.length) throw new Refus(`Catégorie inconnue « ${categorie} ». Catégories : ${noms.join(', ')}.`);
			const court = (t) => (String(t || '').length > 200 ? `${String(t).slice(0, 197)}…` : String(t || ''));
			const out = [`Galerie de styles (${styles.length} styles, ${noms.length} catégorie(s) : ${noms.join(', ')}).`];
			for (const n of choisis) {
				out.push('', `${n} :`);
				for (const s of groupes.get(n)) {
					out.push(`• ${s.id} — ${s.name}${s.perso ? ' [mon style]' : ''} : ${court(s.description)}`);
					if (s.preview) out.push(`  Aperçu : ${path.join(ROOT, 'assets', ...String(s.preview).split('/'))}`);
				}
			}
			out.push('', 'Pour l\'appliquer à une vidéo prête : changer_style (une version « avant le style » est gardée ; « Revenir au style précédent » dans l\'interface).');
			return out.join('\n');
		},
	},
	{
		name: 'changer_style',
		title: 'Autre style',
		description: 'Remonte une vidéo prête dans un autre style de montage (comme « Autre style » dans la Révision). Une version « avant le style » est gardée. '
			+ 'Quelques secondes à une minute.',
		inputSchema: {type: 'object', properties: {video: VIDEO, style: S('Identifiant du style (voir l\'outil styles).')}, required: ['video', 'style'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false},
		run: async ({video, style}) => {
			const item = await trouverVideo(video);
			const s = await verifierStyle(style);
			if (!PRETE(item)) throw new Refus(`La vidéo « ${item.title || item.name} » n'est pas encore prête (${STATUT[item.status] || item.status}).`);
			const visuel = ['immobilier', 'evenement'];
			if (visuel.includes(s.id) && !visuel.includes(item.type)) throw new Refus(`Le style ${s.name} est réservé aux vidéos sans parole (immobilier, événement).`);
			const avant = item.style;
			const d = await api('POST', `/api/revision/${item.id}/style`, {body: {style: s.id}, timeout: 600000});
			return `Style changé pour « ${item.title || item.name} » : ${avant || '?'} → ${s.name} (${d?.reel?.template || s.id}).\nRegarde-la dans l'interface (${ORIGIN}, écran Révision). `
				+ (item.type ? `Pour garder ce style pour tous les prochains « ${item.typeLabel} » : toujours_ce_style (sujet ${item.type}).` : '');
		},
	},
	{
		name: 'toujours_ce_style',
		title: 'Toujours ce style pour ce sujet',
		description: 'Choisit le style utilisé automatiquement pour les PROCHAINES vidéos d\'un sujet (ex. pub → Reel Impact). Ne change pas les vidéos déjà montées.',
		inputSchema: {type: 'object', properties: {sujet: S('Sujet : pub, temoignage, conseil, motivation, podcast, annonce, fiction, immobilier, evenement, autre (ou son nom affiché).'),
			style: S('Identifiant du style (voir l\'outil styles).')}, required: ['sujet', 'style'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false},
		run: async ({sujet, style}) => {
			const types = await api('GET', '/api/types');
			const q = String(sujet ?? '').trim().toLowerCase();
			const key = Object.keys(types).find((k) => k === q) || Object.keys(types).find((k) => types[k].label.toLowerCase() === q);
			if (!key) throw new Refus(`Sujet inconnu « ${sujet} ». Sujets : ${Object.entries(types).map(([k, t]) => `${k} (${t.label})`).join(', ')}.`);
			const s = await verifierStyle(style);
			await api('POST', `/api/types/${key}`, {body: {style: s.id}});
			return `C'est noté : les prochaines vidéos « ${types[key].label} » seront montées en « ${s.name} » (${s.id}). Les vidéos déjà montées ne changent pas.`;
		},
	},
	{
		name: 'refaire',
		title: 'Refaire le montage',
		description: 'Refait tout le montage automatique d\'une vidéo (après une erreur, ou avec un style imposé). Long (plusieurs minutes, carte graphique) : '
			+ 'seulement quand l\'utilisateur le demande.',
		inputSchema: {type: 'object', properties: {video: VIDEO, style: S('Style imposé (facultatif ; sinon choisi selon le sujet).')}, required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video, style}) => {
			const item = await trouverVideo(video);
			if (item.status === 'attente' || item.status === 'travail') throw new Refus(`La vidéo « ${item.title || item.name} » est déjà ${item.status === 'travail' ? 'en montage' : 'en file'}.`);
			const s = style ? await verifierStyle(style) : null;
			const rev = await api('POST', `/api/revision/${item.id}/refaire`, {body: s ? {style: s.id} : {}});
			const now = rev.items.find((i) => i.id === item.id);
			return `Montage relancé pour « ${item.title || item.name} »${s ? ` (style ${s.name})` : ''} : ${STATUT[now?.status] || now?.status || 'en file'}. Suis l'avancement avec etat.`;
		},
	},
	{
		name: 'retirer',
		title: 'Retirer de la Révision',
		description: 'Retire une vidéo de la liste Révision. Aucun fichier n\'est supprimé (rushs, projet et vidéo finale restent). '
			+ 'Pour vraiment s\'en débarrasser, l\'utilisateur clique « 🗑️ Supprimer » dans l\'interface (montage et vidéos brutes vont dans la corbeille de '
			+ 'l\'éditeur) : ce plugin ne supprime jamais rien.',
		inputSchema: {type: 'object', properties: {video: VIDEO}, required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false},
		run: async ({video}) => {
			const item = await trouverVideo(video);
			await api('POST', `/api/revision/${item.id}/retirer`, {body: {}});
			return `« ${item.title || item.name} » est retirée de la liste Révision (aucun fichier supprimé).`;
		},
	},
	{
		name: 'inspecter_montage',
		title: 'Inspecter un montage',
		description: 'Résumé technique lisible d’une vidéo prête : durée, format, style, plans, mots en couleur, habillage, bandeau, musique, voix, propositions et rapport de relecture. Lecture seule.',
		inputSchema: {type: 'object', properties: {video: VIDEO}, required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async ({video}) => {
			const {item, reel} = await montageDe(video);
			return resumerReel(item, reel);
		},
	},
	{
		name: 'versions',
		title: 'Versions d’un montage',
		description: 'Liste les sauvegardes d’une vidéo, sans rien modifier. Donne le nom exact à utiliser avec restaurer_version.',
		inputSchema: {type: 'object', properties: {video: VIDEO}, required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async ({video}) => {
			const {item} = await montageDe(video);
			const list = await api('GET', `/api/reels/${item.project}/${item.rid}/versions`);
			return list.length ? [`Versions de « ${item.title || item.name} » :`, ...list.map((v) => `• ${typeof v === 'string' ? v : v.file || v.name || JSON.stringify(v)}`)].join('\n') : 'Aucune version enregistrée.';
		},
	},
	{
		name: 'restaurer_version',
		title: 'Restaurer une version',
		description: 'Restaure une sauvegarde précise du montage. Le montage actuel est sauvegardé automatiquement avant la restauration. Seulement sur demande explicite.',
		inputSchema: {type: 'object', properties: {video: VIDEO, fichier: S('Nom exact renvoyé par versions.')}, required: ['video', 'fichier'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video, fichier}) => {
			const {item} = await montageDe(video);
			const r = await api('POST', `/api/reels/${item.project}/${item.rid}/restore`, {body: {file: String(fichier)}});
			return `Version restaurée pour « ${item.title || item.name} » : ${fichier}. Style actuel : ${r.reel?.template || r.template || '?'}. Une copie de l’état précédent a été gardée.`;
		},
	},
	{
		name: 'retour_style',
		title: 'Revenir au style précédent',
		description: 'Annule le dernier changement de style d’une vidéo. Une sauvegarde de l’état actuel est gardée.',
		inputSchema: {type: 'object', properties: {video: VIDEO}, required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video}) => {
			const item = await trouverVideo(video);
			const r = await api('POST', `/api/revision/${item.id}/retourstyle`, {body: {}});
			return `« ${item.title || item.name} » est revenue au style ${r.reel?.template || r.template || '?'}.`;
		},
	},
	{
		name: 'declinaison',
		title: 'Créer une déclinaison',
		description: 'Crée une autre version courte (15, 30 ou 60 s) et/ou avec une intention rapide ou émotion. Travail local potentiellement long, uniquement sur demande explicite.',
		inputSchema: {type: 'object', properties: {video: VIDEO,
			duree: {type: 'integer', enum: [15, 30, 60], description: 'Durée cible en secondes (facultatif).'},
			intention: S('Rythme de la déclinaison (facultatif).', {enum: ['rapide', 'emotion']})}, required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video, duree, intention}) => {
			if (!duree && !intention) throw new Refus('Choisis une durée (15, 30 ou 60 s), une intention (rapide ou emotion), ou les deux.');
			const {item} = await montageDe(video);
			const job = await api('POST', `/api/reels/${item.project}/${item.rid}/declinaison`, {body: {duree, intention}});
			return `Déclinaison lancée pour « ${item.title || item.name} » : ${ligneTache(job)}\nSuis-la avec suivre_export (tache ${job.id}).`;
		},
	},
	{
		name: 'proposer',
		title: 'Analyser et proposer des retouches',
		description: 'Lance une analyse pour proposer des mots/emoji/bandeau, plans de coupe, graphismes, faux raccords ou angles. Par défaut, rien n’est appliqué et la vision est désactivée. Type « ia » : si Claude est activé et n’a jamais lu ce montage (mots changés depuis), UN appel payant à Claude (≈ 0,04 $ avec Sonnet, réponse gardée ensuite : gratuit) ; sinon IA locale gratuite. À lancer seulement sur demande explicite.',
		inputSchema: {type: 'object', properties: {video: VIDEO,
			type: S('Type d’analyse.', {enum: ['ia', 'broll', 'graphismes', 'raccords', 'angles']}),
			tout: {type: 'boolean', description: 'Analyser tout le montage plutôt que la zone courante.'},
			vision: {type: 'boolean', description: 'Autoriser l’IA vision locale (défaut false).'},
			automatique: {type: 'boolean', description: 'Plans de coupe seulement : poser automatiquement les propositions sûres. Défaut false.'}},
			required: ['video', 'type'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video, type, tout = false, vision = false, automatique = false}) => {
			const {item} = await montageDe(video);
			if (automatique && type !== 'broll') throw new Refus('automatique est disponible seulement pour les plans de coupe (type broll).');
			const route = {ia: 'ia', broll: 'broll', graphismes: 'graphismes', raccords: 'raccords', angles: 'angles'}[type];
			if (!route) throw new Refus('type : ia, broll, graphismes, raccords ou angles.');
			const job = await api('POST', `/api/reels/${item.project}/${item.rid}/${route}`, {body: {tout: !!tout, vision: !!vision, ...(type === 'broll' ? {auto: !!automatique} : {})}});
			return `Analyse lancée pour « ${item.title || item.name} » : ${ligneTache(job)}\nSuis-la avec suivre_export (tache ${job.id}).`;
		},
	},
	{
		name: 'rechercher_rushs',
		title: 'Rechercher dans les rushs',
		description: 'Recherche une phrase naturelle dans les prises d’un projet. Analyse locale en lecture seule des rushs.',
		inputSchema: {type: 'object', properties: {video: VIDEO, requete: S('Ce qu’il faut retrouver dans les rushs (200 caractères maximum).', {maxLength: 200})}, required: ['video', 'requete'], additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async ({video, requete}) => {
			const {item} = await montageDe(video);
			const q = String(requete || '').trim();
			if (!q) throw new Refus('Écris ce qu’il faut retrouver dans les rushs.');
			const job = await api('POST', '/api/search', {body: {project: item.project, q}});
			return `Recherche lancée : ${ligneTache(job)}\nSuis-la avec suivre_export (tache ${job.id}).`;
		},
	},
	{
		name: 'controle',
		title: 'Contrôle qualité',
		description: 'Contrôle qualité automatique d’une vidéo : note sur 10, verdict et problèmes classés (bloquant, important, conseil), chacun avec le moment exact '
			+ 'et une suggestion. mode « dernier » (défaut, lecture seule) : derniers rapports enregistrés. « montage » : relit le montage actuel (quelques secondes, '
			+ 'sans rendu ; la note s’affiche dans la Révision). « export » : contrôle la vidéo livrée (images, détourage, lisibilité, son ; environ 1 minute, carte '
			+ 'graphique) — par défaut le dernier export de la vidéo. Rien n’est corrigé : l’outil signale, l’utilisateur décide. Ensuite : suivre_export.',
		inputSchema: {type: 'object', properties: {video: VIDEO,
			mode: S('dernier (défaut, lecture seule) · montage · export', {enum: ['dernier', 'montage', 'export']}),
			fichier: S('mode export : chemin du MP4 à contrôler, dans le dossier de l’éditeur (livraisons\\… ou un aperçu). Défaut : le dernier export de la vidéo.'),
			format: S('mode export : format de ce fichier (défaut : déduit du nom « (16x9) », sinon 9:16).', {enum: FORMATS}),
			debut: {type: 'number', minimum: 0, maximum: 86400, description: 'mode export : instant du montage où commence le fichier (aperçu partiel) ; défaut 0 ou job.json voisin.'},
			details: {type: 'integer', minimum: 1, maximum: 40, description: 'Nombre de problèmes affichés (défaut 12).'},
				version: S('Version du montage à contrôler, par ex. « script-qualite » (une déclinaison ou une version « qualité ») ; défaut : la version de la vidéo dans la Révision. Indispensable pour contrôler l’export d’une autre version, sinon la vidéo est comparée au mauvais montage.')},
		required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false},
		run: async ({video, mode = 'dernier', fichier, format, debut, details = 12, version}) => {
			if (!['dernier', 'montage', 'export'].includes(mode)) throw new Refus('mode : dernier, montage ou export.');
			const {item, reel} = await montageDe(video);
			if (version !== undefined && !/^[A-Za-z0-9_-]{1,80}$/.test(String(version))) throw new Refus('version : lettres, chiffres, « - » ou « _ » seulement (ex. script-qualite).');
			const rid = version ? String(version) : item.rid;
			const route = `/api/reels/${encodeURIComponent(item.project)}/${encodeURIComponent(rid)}/controle`;
			const n = Math.min(40, Math.max(1, Number(details) || 12));
			if (mode === 'dernier') {
				let d;
				try {
					d = await api('GET', route);
				} catch (e) {
					if (e instanceof ErreurHttp && e.status === 404 && /Introuvable\.$/.test(e.message)) throw new Refus('Le contrôle qualité n’est pas encore actif dans l’éditeur lancé : relance-le (« Editeur Sami.cmd »).');
					throw e;
				}
				// le plus recent des deux : resume range dans le reel (montage automatique, changement de style) ou rapport complet du fichier
				const quand = (r) => (r?.modifie ?? (r?.date ? new Date(String(r.date).replace(' ', 'T')).getTime() : 0)) || 0;
				const montage = d.montage && quand(d.montage) >= quand(d.resume) - 60000 ? d.montage : d.resume ?? d.montage;
				const out = [`Contrôle qualité de « ${item.title || item.name} » (${reel.width}×${reel.height}, style ${reel.template || '?'}) :`, '', 'Montage :',
					texteControle(montage, n)];
				for (const e of d.exports || []) out.push('', `Vidéo livrée ${e.format} (${e.rapport.video || '?'}) :`, texteControle(e.rapport, n));
				if (!d.resume && !d.montage) out.push('', 'Pour un premier contrôle du montage : controle avec mode « montage ».');
				return out.join('\n');
			}
			let body = {};
			if (mode === 'export') {
				const faits = (item.exports || []).filter((e) => e.status === 'done');
				const cible = fichier ? cheminVideoEditeur(fichier) : faits.at(-1)?.out || item.taken?.out;
				if (!cible) throw new Refus(`« ${item.title || item.name} » n’a pas encore d’export : prendre d’abord (sur demande), ou donne le fichier à contrôler.`);
				const e = faits.find((x) => path.resolve(x.out).toLowerCase() === path.resolve(cible).toLowerCase());
				body = {video: cible, ...(format || e?.format ? {format: format || e.format} : {}), ...(debut !== undefined ? {debut: Number(debut)} : {})};
			}
			let job;
			try {
				job = await api('POST', route, {body});
			} catch (e) {
				if (e instanceof ErreurHttp && e.status === 404 && /Introuvable\.$/.test(e.message)) throw new Refus('Le contrôle qualité n’est pas encore actif dans l’éditeur lancé : relance-le (« Editeur Sami.cmd »).');
				throw e;
			}
			return `Contrôle qualité lancé (${mode === 'export' ? `vidéo ${body.video}, environ 1 minute` : 'montage, quelques secondes'}) : ${ligneTache(job)}\n`
				+ `Suis-le avec suivre_export (tache ${job.id}, attendre ${mode === 'export' ? 120 : 30}).`;
		},
	},
	{
		name: 'claude_couts',
		title: 'Claude : état et coûts',
		description: 'État de Claude (IA en ligne d’Anthropic, en option et PAYANTE) dans l’Éditeur Sami : allumé ou non, clé présente ou non (jamais la clé), modèle, '
			+ 'dépenses du jour et du mois, crédit restant estimé, plafonds, coût estimé d’une critique, derniers appels ; avec video : ce que cette vidéo a coûté. '
			+ 'Lecture seule : aucun appel à Claude, rien ne coûte.',
		inputSchema: {type: 'object', properties: {
			video: S('Facultatif : identifiant de la vidéo (12 caractères, donné par etat) ou son titre, pour son détail.'),
			jours: {type: 'integer', minimum: 1, maximum: 90, description: 'Nombre de jours de dépenses affichés (défaut 7).'}},
		additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async ({video, jours = 7}) => {
			const n = Math.min(90, Math.max(1, Number(jours) || 7));
			let item = null;
			if (video !== undefined && String(video).trim()) {
				item = await trouverVideo(video);
				if (!item.project || !item.rid) throw new Refus(`« ${item.title || item.name} » n’a pas encore de montage.`);
			}
			const s = await routeClaude('GET', '/api/claude');
			const q = `/api/claude/couts?jours=${n}${item ? `&video=${encodeURIComponent(`${item.project}/${item.rid}`)}` : ''}`;
			const c = await routeClaude('GET', q);
			const out = [texteStatutClaude(s), ''];
			const jrs = (c.jours || []).filter((d) => d.appels || d.cout);
			out.push(`Sur ${n} jour(s) : ${argent(c.total)}${jrs.length ? ` (${jrs.map((d) => `${d.date} ${argent(d.cout)}, ${d.appels} appel(s)`).join(' ; ')})` : ' (aucun appel)'}.`);
			if (item) {
				const v = c.video || {};
				out.push('', `« ${item.title || item.name} » : ${argent(v.cout)} en ${v.nb || 0} appel(s) à Claude.`);
				for (const a of (v.appels || []).slice(-10)) out.push(`• ${String(a.date || '').replace('T', ' ').slice(0, 16)} ${a.tache} (${nomClaude(a.modele)}) : ${argent(a.cout)}${a.ok ? '' : ` — échec : ${masquer(a.erreur || '?')}`}`);
			} else if ((c.videos || []).length) out.push('Vidéos récentes :', ...c.videos.slice(0, 10).map((v) => `• ${v.video} : ${argent(v.cout)} (${v.nb} appel(s))`));
			const d = (c.derniers || []).slice(0, 10);
			if (d.length) out.push('', 'Derniers appels :', ...d.map((a) => `• ${a.date.replace('T', ' ').slice(0, 16)} ${a.tache}${a.video ? ` · ${a.video}` : ''} (${nomClaude(a.modele)}) : ${argent(a.cout)}${a.ok ? ' ✓' : ` ✗ ${masquer(a.erreur || '')}`}`));
			out.push('', 'Console Anthropic (crédit réel, recharges) : platform.claude.com. Réglages : interface → roue ⚙️ → Claude.');
			return out.join('\n');
		},
	},
	{
		name: 'claude_critique',
		title: 'Critique par Claude (payant)',
		description: 'Fait relire des images de la vidéo par Claude (IA en ligne, PAYANTE : quelques centimes du crédit Anthropic de l’utilisateur ; coût estimé par claude_couts) : '
			+ 'note, verdict et problèmes avec leur moment. Rien n’est changé dans le montage ; l’avis s’affiche aussi dans la carte Contrôle qualité de la Révision. '
			+ 'SEULEMENT si l’utilisateur le demande explicitement, une fois. Claude relit une vidéo EXPORTÉE (par défaut la dernière) : sans export, demande d’abord prendre. '
			+ 'Un avis déjà payé pour la même vidéo revient gratuitement. Ensuite : suivre_export (attendre 120).',
		inputSchema: {type: 'object', properties: {video: VIDEO,
			fichier: S('Facultatif : MP4 livré à relire, dans le dossier de l’éditeur (livraisons\\…). Défaut : le dernier export de la vidéo.')},
		required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true},
		run: async ({video, fichier}) => {
			const item = await trouverVideo(video);
			if (!PRETE(item)) throw new Refus(`« ${item.title || item.name} » n’est pas encore prête : attends la fin du montage.`);
			const s = await routeClaude('GET', '/api/claude');
			if (!s.pret) throw new Refus(`Claude n’est pas prêt : ${s.raison || 'voir claude_couts'}`);
			const faits = (item.exports || []).filter((e) => e.status === 'done');
			const cible = fichier ? cheminVideoEditeur(fichier) : faits.at(-1)?.out || item.taken?.out || null;
			// la critique juge les images d'une video livree (python -m editeur.critique_claude <video.mp4>) : rien avant le premier export
			if (!cible) throw new Refus(`« ${item.title || item.name} » n’a pas encore été exportée : Claude relit les images de la vidéo livrée. Exporte-la d’abord (prendre), puis relance la critique.`);
			const job = await routeClaude('POST', `/api/reels/${encodeURIComponent(item.project)}/${encodeURIComponent(item.rid)}/claude/critique`, {body: {video: cible}});
			const e = estimationTache(s, 'critique');
			return `Relecture par Claude lancée pour « ${item.title || item.name} » (vidéo ${cible}${e !== null ? `, environ ${argent(e)}` : ''}) : ${ligneTache(job)}\n`
				+ `Suis-la avec suivre_export (tache ${job.id}, attendre 120).`;
		},
	},
	{
		name: 'consigne',
		title: 'Dis à l’IA ce que tu veux',
		description: 'Applique une demande en français sur le montage d’une vidéo prête, comme la boîte « Dis à l’IA ce que tu veux » de l’interface (« enlève le bandeau du début », '
			+ '« mets GRATUIT en jaune », « à 0:12, coupe la pause »). Peut utiliser Claude (PAYANT, quelques centimes) ou l’IA locale (moteur : auto, claude, local). '
			+ 'Si la demande est ambiguë, l’éditeur pose une question au lieu d’agir. Une version « avant » est gardée (annulable avec restaurer_version). '
			+ 'SEULEMENT sur demande explicite de l’utilisateur, avec ses mots ; simuler=true montre ce qui serait fait sans rien changer.',
		inputSchema: {type: 'object', properties: {video: VIDEO,
			texte: S('La demande de l’utilisateur, en français (800 caractères au plus).', {maxLength: 800}),
			t: {type: 'number', minimum: 0, maximum: 86400, description: 'Facultatif : moment du montage visé (secondes), par ex. 12 pour « à 0:12 ».'},
			moteur: S('auto (défaut : Claude si prêt, sinon local) · claude · local (gratuit).', {enum: ['auto', 'claude', 'local']}),
			simuler: {type: 'boolean', description: 'Seulement montrer ce qui serait fait, sans rien changer (défaut false).'},
			attendre: {type: 'integer', minimum: 0, maximum: 300, description: 'Attendre le résultat au plus ce nombre de secondes (défaut 120).'}},
		required: ['video', 'texte'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true},
		run: async ({video, texte, t, moteur, simuler = false, attendre = 120}, ctx) => {
			const demande = String(texte ?? '').trim();
			if (!demande) throw new Refus('Écris la demande de l’utilisateur (texte).');
			if (demande.length > 800) throw new Refus('Demande trop longue : 800 caractères au plus.');
			if (moteur !== undefined && !['auto', 'claude', 'local'].includes(moteur)) throw new Refus('moteur : auto, claude ou local.');
			const item = await trouverVideo(video);
			if (!PRETE(item)) throw new Refus(`« ${item.title || item.name} » n’est pas encore prête : attends la fin du montage.`);
			const body = {texte: demande, ...(t !== undefined && t !== null ? {t: Number(t)} : {}), ...(moteur ? {moteur} : {}), ...(simuler ? {simuler: true} : {})};
			let job = await routeClaude('POST', `/api/reels/${encodeURIComponent(item.project)}/${encodeURIComponent(item.rid)}/consigne`, {body});
			const fin = Date.now() + 1000 * Math.min(300, Math.max(0, Number(attendre) || 0));
			while ((job.status === 'running' || job.status === 'queued') && Date.now() < fin && !ctx.annule()) {
				await sleep(2000);
				job = await api('GET', `/api/jobs/${job.id}`);
				ctx.progress(0.5, 1, job.stage || 'Demande en cours');
			}
			if (job.status === 'done') return `Demande « ${demande.slice(0, 120)} » pour « ${item.title || item.name} » :\n${texteConsigne(job.result, simuler)}`;
			if (job.status === 'failed') throw new Refus(`La demande n’a pas abouti : ${job.error || 'erreur inconnue'}`);
			return `Demande en cours pour « ${item.title || item.name} » : ${ligneTache(job)}\nSuis-la avec suivre_export (tache ${job.id}, attendre 120).`;
		},
	},
	{
		name: 'refaire_passage',
		title: 'Refaire seulement ce passage',
		description: 'Refait seulement l’habillage automatique d’un passage du montage (début et fin en secondes du montage) : rien ne change avant ni après, '
			+ 'rien de verrouillé ni de retouché à la main. Une version « avant refaire le passage » est gardée (outil versions). Seulement sur demande explicite.',
		inputSchema: {type: 'object', properties: {video: VIDEO,
			debut: {type: 'number', minimum: 0, maximum: 86400, description: 'Début du passage (secondes du montage).'},
			fin: {type: 'number', minimum: 0.3, maximum: 86400, description: 'Fin du passage (secondes du montage), au moins 0,3 s après le début.'}},
		required: ['video', 'debut', 'fin'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video, debut, fin}) => {
			const [a, b] = [Number(debut), Number(fin)];
			if (!Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b - a < 0.3) throw new Refus('Passage invalide : un début et une fin en secondes, la fin au moins 0,3 s après le début.');
			const {item, reel} = await montageDe(video);
			const total = dureeReel(reel) + (reel.intro?.enabled ? Number(reel.intro.duration) || 0 : 0);
			if (total && a >= total) throw new Refus(`Le montage dure ${virgule(total)} s : le début (${virgule(a)} s) est après la fin.`);
			const job = await api('POST', `/api/reels/${encodeURIComponent(item.project)}/${encodeURIComponent(item.rid)}/passage`, {body: {debut: a, fin: b}});
			return `Passage ${tc(a)}–${tc(b)} en cours de refonte pour « ${item.title || item.name} » : ${ligneTache(job)}\n`
				+ 'Une version « avant refaire le passage » est gardée. Suis-le avec suivre_export (tache ' + job.id + ', attendre 120).';
		},
	},
	{
		name: 'choregraphie',
		title: 'Refaire la chorégraphie',
		description: 'Recalcule la chorégraphie du montage : comment chaque élément (graphisme, scène, plan de coupe, vecteur, bandeau) entre et sort, synchronisé '
			+ 'sur les mots et la musique. Les mouvements verrouillés ne changent jamais ; tout=true refait aussi ceux retouchés à la main. Une version « avant chorégraphie » '
			+ 'est gardée. Seulement sur demande explicite.',
		inputSchema: {type: 'object', properties: {video: VIDEO,
			tout: {type: 'boolean', description: 'Refaire aussi les mouvements retouchés à la main (jamais les verrouillés). Défaut false.'}},
		required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video, tout = false}) => {
			if (typeof tout !== 'boolean') throw new Refus('tout : vrai ou faux.');
			const {item} = await montageDe(video);
			const job = await api('POST', `/api/reels/${encodeURIComponent(item.project)}/${encodeURIComponent(item.rid)}/choregraphie`, {body: {tout}});
			return `Chorégraphie relancée pour « ${item.title || item.name} »${tout ? ' (retouches comprises, jamais les mouvements verrouillés)' : ''} : ${ligneTache(job)}\n`
				+ `Suis-la avec suivre_export (tache ${job.id}, attendre 60).`;
		},
	},
	{
		name: 'banque_catalogue',
		title: 'Banque locale (effets, sons, vecteurs, templates, icônes)',
		description: 'Catalogue de la banque LOCALE de l’éditeur (rien d’internet) : sons (whoosh, impact…), effets, vecteurs SVG recolorables, templates et '
			+ 'icônes (1 857 icônes Lucide au trait + icônes importées, recherche en français), avec catégorie, intensité, licence et provenance. '
			+ 'Lecture seule : pour poser un élément, l’utilisateur clique « + Ajouter » dans l’interface (Plus → Banque).',
		inputSchema: {type: 'object', properties: {
			type: S('effet · son · vecteur · template · icone (icônes Lucide posées en trait / plein / verre) ; défaut : tout sauf les icônes.',
				{enum: ['effet', 'son', 'vecteur', 'template', 'icone']}),
			categorie: S('Catégorie exacte (ex. whoosh, flèches, transitions) ; la liste est donnée dans la réponse.', {maxLength: 40}),
			q: S('Mots-clés (ex. « impact », « flèche »).', {maxLength: 100}),
			format: S('Seulement les ressources adaptées à ce format.', {enum: FORMATS}),
			intensite: {type: 'integer', enum: [1, 2, 3], description: '1 discret · 2 moyen · 3 fort.'},
			limite: {type: 'integer', minimum: 1, maximum: 100, description: 'Nombre de ressources affichées (défaut 25).'}},
		additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async ({type, categorie, q, format, intensite, limite = 25}) => {
			const params = new URLSearchParams();
			for (const [k, v] of Object.entries({type, categorie, q, format, intensite})) if (v !== undefined && v !== null && String(v).trim()) params.set(k, String(v).trim());
			let d;
			try {
				d = await api('GET', `/api/banque${[...params].length ? `?${params}` : ''}`, {timeout: 120000});
			} catch (e) {
				if (e instanceof ErreurHttp && e.status === 404) throw new Refus('La banque locale n’est pas disponible dans l’éditeur lancé : relance-le (« Editeur Sami.cmd »).');
				throw e;
			}
			const n = Math.min(100, Math.max(1, Number(limite) || 25));
			const entrees = d.entrees || [];
			const cats = Object.entries(d.categories || {}).filter(([t]) => !type || t === type).map(([t, l]) => `${t} : ${l.join(', ')}`);
			return [`Banque locale : ${d.total ?? entrees.length} ressource(s) trouvée(s)${[...params].length ? ` (filtres : ${[...params].map(([k, v]) => `${k}=${v}`).join(', ')})` : ''} `
				+ `sur ${Object.values(d.compte || {}).reduce((a, b) => a + b, 0)} (${Object.entries(d.compte || {}).map(([k, v]) => `${v} ${k}s`).join(', ')}).`,
				...entrees.slice(0, n).map((e) => `• ${e.id} — ${e.nom} [${e.type} / ${e.categorie}${e.intensite ? `, intensité ${e.intensite}` : ''}]${e.description ? ` : ${e.description}` : ''}`
					+ `\n  Fichier : assets\\${String(e.fichier || e.apercu || '').split('/').join('\\')} · Licence : ${e.licence || '?'}`),
				entrees.length > n ? `… et ${entrees.length - n} autre(s) (limite ${n}).` : '',
				'', 'Catégories :', ...cats.map((c) => `• ${c}`)].filter((l) => l !== '').join('\n');
		},
	},
	{
		name: 'outils_locaux',
		title: 'État des outils locaux',
		description: 'Vérifie sans rien lancer quels moteurs locaux de l’Éditeur Sami sont disponibles : Blender autonome, Resolve, FFmpeg, llama/Qwen, ACE-Step, Whisper, MediaPipe, détourage RVM et RNNoise.',
		inputSchema: {type: 'object', properties: {}, additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async () => {
			const checks = [
				['DaVinci Resolve', 'D:\\Resolve.exe'],
				['Blender autonome', path.join(ROOT, 'tools', 'blender', 'blender.exe')],
				['FFmpeg', path.join(ROOT, 'tools', 'ffmpeg')],
				['llama.cpp / Qwen', path.join(ROOT, 'tools', 'llama')],
				['ACE-Step', path.join(ROOT, 'tools', 'acestep')],
				['Whisper', path.join(ROOT, 'models', 'huggingface')],
				['MediaPipe (visages)', path.join(ROOT, 'models', 'mediapipe')],
				['Détourage RVM (personne, contrôle qualité)', path.join(ROOT, 'models', 'rvm')],
				['RNNoise', path.join(ROOT, 'models', 'rnnoise')],
			];
			return ['Outils locaux (aucun logiciel lancé) :', ...checks.map(([nom, cible]) => `• ${fs.existsSync(cible) ? 'prêt' : 'absent'} — ${nom} — ${cible}`),
				'', 'Le plugin ne cherche jamais Blender dans D:\\Y0U. Pour la 3D, une copie autonome est attendue dans tools\\blender\\blender.exe.'].join('\n');
		},
	},
	{
		name: 'creer_titre_3d',
		title: 'Créer un titre 3D avec Blender',
		description: 'Rend localement un titre d’ouverture 3D avec Blender et l’attache au montage. Travail long : seulement sur demande explicite.',
		inputSchema: {type: 'object', properties: {video: VIDEO, texte: S('Texte du titre, 80 caractères maximum.', {maxLength: 80}),
			couleur: S('Couleur hexadécimale, par exemple #FFD400.'), duree: {type: 'number', minimum: 1, maximum: 4, description: 'Durée en secondes (défaut 2,5).'}},
			required: ['video', 'texte'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video, texte, couleur = '#FFD400', duree = 2.5}) => {
			const {item} = await montageDe(video);
			const blender = path.join(ROOT, 'tools', 'blender', 'blender.exe');
			if (!fs.existsSync(blender)) throw new Refus('Blender autonome est absent : tools\\blender\\blender.exe. Le plugin ne va pas le chercher dans D:\\Y0U.');
			const text = String(texte || '').trim().slice(0, 80);
			if (!text) throw new Refus('Écris le texte du titre 3D.');
			if (!/^#[0-9a-f]{6}$/i.test(couleur)) throw new Refus('Couleur attendue au format #RRGGBB.');
			const seconds = Math.min(4, Math.max(1, Number(duree) || 2.5));
			const job = await api('POST', `/api/reels/${item.project}/${item.rid}/intro`, {body: {text, color: couleur, seconds}});
			return `Titre 3D lancé pour « ${item.title || item.name} » : ${ligneTache(job)}\nSuis-le avec suivre_export (tache ${job.id}).`;
		},
	},
	{
		name: 'animer_produit_3d',
		title: 'Animer un produit avec Blender',
		description: 'Crée l’animation Blender du style Produit 3D à partir de la photo ou du modèle GLB déjà choisi dans le montage. Travail long : seulement sur demande explicite.',
		inputSchema: {type: 'object', properties: {video: VIDEO}, required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video}) => {
			const {item, reel} = await montageDe(video);
			if (!fs.existsSync(path.join(ROOT, 'tools', 'blender', 'blender.exe'))) throw new Refus('Blender autonome est absent : tools\\blender\\blender.exe.');
			if (reel.design?.mode !== 'produit') throw new Refus('Choisis d’abord le style Produit 3D pour cette vidéo.');
			const job = await api('POST', `/api/reels/${item.project}/${item.rid}/produit`, {body: {}});
			return `Animation Produit 3D lancée : ${ligneTache(job)}\nSuis-la avec suivre_export (tache ${job.id}).`;
		},
	},
	{
		name: 'actualiser_detourage',
		title: 'Actualiser le détourage local',
		description: 'Recalcule localement le détourage de la personne (RobustVideoMatting, pleine résolution, avec repli sur la prise d’origine là où le contour '
			+ 'est douteux) pour les styles Tech 3D cinématique, Éditorial cinétique et Collage. Carte graphique, 1 à 2 minutes : seulement sur demande explicite.',
		inputSchema: {type: 'object', properties: {video: VIDEO}, required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video}) => {
			const {item, reel} = await montageDe(video);
			const d = reel.design || {};
			if (!(['editorial', 'collage'].includes(d.mode) || (d.mode === 'produit' && d.cinematic))) { // meme regle que detourage.needs_cutout
				throw new Refus('Le détourage est prévu pour les styles Tech 3D cinématique, Éditorial cinétique et Collage.');
			}
			const job = await api('POST', `/api/reels/${item.project}/${item.rid}/detourage`, {body: {}});
			return `Détourage lancé : ${ligneTache(job)}\nSuis-le avec suivre_export (tache ${job.id}).`;
		},
	},
	{
		name: 'generer_musique',
		title: 'Composer une musique locale',
		description: 'Compose une musique originale avec ACE-Step en local et l’attache au montage. Travail GPU long : seulement sur demande explicite.',
		inputSchema: {type: 'object', properties: {video: VIDEO, ambiance: S('Identifiant d’ambiance musicale disponible dans l’éditeur.'),
			duree: {type: 'number', minimum: 5, maximum: 600, description: 'Durée en secondes (défaut : durée du montage).'},
			seed: {type: 'integer', minimum: 1, maximum: 999999999, description: 'Graine facultative pour reproduire une composition.'}},
			required: ['video', 'ambiance'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video, ambiance, duree, seed}) => {
			const {item, reel} = await montageDe(video);
			const assets = await api('GET', '/api/assets');
			const moods = (assets.music || []).map((m) => m.id);
			if (!moods.includes(ambiance)) throw new Refus(`Ambiance inconnue « ${ambiance} ». Disponibles : ${moods.join(', ') || 'aucune'}.`);
			const body = {mood: ambiance, duration: Math.min(600, Math.max(5, Number(duree) || dureeReel(reel) || 60))};
			if (Number.isInteger(seed)) body.seed = seed;
			const job = await api('POST', `/api/reels/${item.project}/${item.rid}/music`, {body});
			return `Composition locale lancée : ${ligneTache(job)}\nSuis-la avec suivre_export (tache ${job.id}).`;
		},
	},
	{
		name: 'ouvrir_resolve',
		title: 'Ouvrir DaVinci Resolve',
		description: 'Ouvre DaVinci Resolve installé sur ce PC. Ne prépare ni n’importe automatiquement une timeline. Seulement si l’utilisateur demande explicitement d’ouvrir Resolve.',
		inputSchema: {type: 'object', properties: {confirmer: {type: 'boolean', description: 'Doit être true : confirme l’ouverture visible du logiciel.'}}, required: ['confirmer'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({confirmer}) => {
			if (confirmer !== true) throw new Refus('Confirme explicitement l’ouverture de DaVinci Resolve.');
			if (!fs.existsSync('D:\\Resolve.exe')) throw new Refus('DaVinci Resolve est introuvable dans D:\\Resolve.exe.');
			await api('POST', '/api/open-resolve', {body: {}});
			return 'DaVinci Resolve a été ouvert. Pour préparer la timeline, utilise exporter_montage_pro séparément.';
		},
	},
	{
		name: 'exporter_montage_pro',
		title: 'Exporter vers Resolve / Premiere',
		description: 'Prépare les fichiers de montage professionnels (OTIO, XML, FCPXML, SRT) pour DaVinci Resolve ou Premiere. Ne crée pas le MP4 final.',
		inputSchema: {type: 'object', properties: {video: VIDEO}, required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video}) => {
			const {item} = await montageDe(video);
			const job = await api('POST', `/api/reels/${item.project}/${item.rid}/echange`, {body: {}});
			return `Export professionnel lancé : ${ligneTache(job)}\nSuis-le avec suivre_export (tache ${job.id}).`;
		},
	},
	{
		name: 'annuler_tache',
		title: 'Annuler une tâche',
		description: 'Annule un export ou une analyse en cours à partir de son identifiant. À utiliser seulement quand l’utilisateur demande l’arrêt.',
		inputSchema: {type: 'object', properties: {tache: S('Identifiant UUID de la tâche.')}, required: ['tache'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: true, idempotentHint: true, openWorldHint: false},
		run: async ({tache}) => {
			const id = String(tache || '').trim();
			if (!/^[a-f0-9-]{36}$/.test(id)) throw new Refus('Identifiant de tâche invalide.');
			const j = await api('POST', `/api/jobs/${id}/cancel`, {body: {}});
			return `Arrêt demandé : ${ligneTache(j)}`;
		},
	},
	{
		name: 'corbeille',
		title: 'Voir la corbeille',
		description: 'Liste les vidéos rangées dans la corbeille récupérable de l’éditeur et indique lesquelles peuvent être restaurées. Lecture seule.',
		inputSchema: {type: 'object', properties: {}, additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async () => {
			const r = await api('GET', '/api/revision/corbeille');
			return r.entrees.length ? [`Corbeille : ${r.corbeille}`, ...r.entrees.map((e) => `• ${e.dossier} — ${e.titre} — ${e.restaurable ? 'restaurable' : `non restaurable : ${e.raison}`}`)].join('\n') : `Corbeille vide : ${r.corbeille}`;
		},
	},
	{
		name: 'mettre_corbeille',
		title: 'Mettre une vidéo à la corbeille',
		description: 'Range le montage et, s’ils ne sont pas partagés, les rushs d’une vidéo dans la corbeille récupérable. Les exports terminés restent dans livraisons. Action destructive mais réversible : seulement sur demande explicite.',
		inputSchema: {type: 'object', properties: {video: VIDEO}, required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false},
		run: async ({video}) => {
			const item = await trouverVideo(video);
			const r = await api('POST', `/api/revision/${item.id}/supprimer`, {body: {}});
			return [`« ${item.title || item.name} » a été rangée dans la corbeille.`, `Dossier : ${r.supprime.corbeille}`,
				...(r.supprime.deplaces || []).map((p) => `• Déplacé : ${p}`), ...(r.supprime.gardes || []).map((p) => `• Gardé : ${p}`),
				'Récupération : outil restaurer_corbeille avec le nom exact du dossier.'].join('\n');
		},
	},
	{
		name: 'restaurer_corbeille',
		title: 'Restaurer depuis la corbeille',
		description: 'Remet une entrée de la corbeille à son emplacement d’origine si la place est libre. Le montage existant est conservé ; s’il manque, la vidéo pourra être remontée.',
		inputSchema: {type: 'object', properties: {dossier: S('Nom exact du dossier renvoyé par corbeille.')}, required: ['dossier'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({dossier}) => {
			const r = await api('POST', '/api/revision/corbeille/restaurer', {body: {dossier: String(dossier)}});
			return [`« ${r.restaure.titre} » restaurée.`, ...(r.restaure.remis || []).map((p) => `• Remis : ${p}`), r.restaure.note].filter(Boolean).join('\n');
		},
	},
	{
		name: 'prendre',
		title: 'Je la prends (exporter)',
		description: '« Je la prends » : exporte la vidéo finale (MP4) dans livraisons\\<dépôt>\\. Les exports passent un à la fois dans la file (environ 2 à 3 minutes '
			+ 'par format). Seulement quand l\'utilisateur le demande, une vidéo à la fois. Ensuite : suivre_export.',
		inputSchema: {type: 'object', properties: {video: VIDEO,
			formats: {type: 'array', minItems: 1, maxItems: 4, uniqueItems: true, items: {type: 'string', enum: FORMATS},
				description: 'Formats à sortir : 9:16 (vertical), 16:9 (horizontal), 4:5, 1:1. Défaut : le format du montage.'}},
		required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video, formats}) => {
			if (formats !== undefined && (!Array.isArray(formats) || !formats.length || formats.length > 4)) throw new Refus('Formats : une liste de 1 à 4 formats est attendue.');
			const item = await trouverVideo(video);
			if (!PRETE(item)) throw new Refus(`La vidéo « ${item.title || item.name} » n'est pas encore prête (${STATUT[item.status] || item.status}).`);
			const list = [...new Set(Array.isArray(formats) ? formats : [])];
			if (list.some((f) => !FORMATS.includes(f))) throw new Refus(`Formats possibles : ${FORMATS.join(', ')}.`);
			const busy = (item.exports || (item.export ? [item.export] : [])).find((e) => ['queued', 'running'].includes(e.status));
			if (busy) return `« ${item.title || item.name} » est déjà en export (tâche ${busy.job}, ${TACHE[busy.status]}). Suis-le avec suivre_export.`;
			const response = await api('POST', `/api/revision/${item.id}/prendre`, {body: list.length ? {formats: list} : {}});
			const jobs = (response.exports || [response]).map((e) => ({...e, id: e.job || e.id, kind: 'export', title: item.title || item.name}));
			return [`Export lancé pour « ${item.title || item.name} » (un export à la fois, environ 2 à 3 minutes par format) :`,
				...jobs.map((j) => `• ${ligneTache(j)}`), 'Suis-le avec suivre_export (tache = identifiant ci-dessus, attendre = secondes).'].join('\n');
		},
	},
	{
		name: 'suivre_export',
		title: 'Suivre un export ou une analyse',
		description: 'Avancement d\'une tâche : export lancé par prendre, ou analyse de style_reference. Sans identifiant : toute la file d\'exports. '
			+ 'Peut attendre la fin (attendre, en secondes).',
		inputSchema: {type: 'object', properties: {tache: S('Identifiant de la tâche (donné par prendre ou style_reference).'),
			attendre: {type: 'integer', minimum: 0, maximum: 600, description: 'Attendre jusqu\'à la fin de la tâche, au plus ce nombre de secondes (défaut 0 : état actuel).'}},
		additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async ({tache, attendre = 0}, ctx) => {
			if (!tache) {
				const file = await api('GET', '/api/queue');
				return file.length ? ['File d\'exports (les plus récents d\'abord) :', ...file.map((j) => `• ${ligneTache(j)}`)].join('\n') : 'File d\'exports vide.';
			}
			const id = String(tache).trim();
			if (!/^[a-f0-9-]{36}$/.test(id)) throw new Refus('Identifiant de tâche invalide (36 caractères, donné par prendre ou style_reference).');
			const fin = Date.now() + 1000 * Math.min(600, Math.max(0, Number(attendre) || 0));
			for (;;) {
				let j;
				try {
					j = await api('GET', `/api/jobs/${id}`);
				} catch (e) {
					if (e instanceof ErreurHttp && e.status === 404) throw new Refus('Tâche inconnue : l\'éditeur a redémarré depuis (les tâches en cours sont perdues). Relance-la (prendre ou style_reference).');
					throw e;
				}
				const encours = j.status === 'running' || j.status === 'queued';
				if (!encours || Date.now() >= fin || ctx.annule()) return `${ligneTache(j)}${encours ? '\n(toujours en cours)' : ''}`;
				ctx.progress(Number(j.progress) || 0, 1, `${j.stage || ''} ${pct(j.progress)}`.trim());
				await sleep(3000);
			}
		},
	},
	{
		name: 'style_reference',
		title: 'Style depuis une vidéo',
		description: 'Crée un nouveau style de montage en analysant une vidéo déjà montée que l\'utilisateur aime (rythme, sous-titres, zooms, musique, couleurs). '
			+ 'La vidéo est copiée dans media\\references. Analyse de 1 à 3 minutes (IA locale) : suivre avec suivre_export, puis changer_style pour l\'appliquer.',
		inputSchema: {type: 'object', properties: {video: S('Chemin complet de la vidéo de référence (mp4, mov, m4v, mkv, avi, mts, webm).'),
			nom: S('Nom du nouveau style (facultatif, 40 caractères au plus).', {maxLength: 40})}, required: ['video'], additionalProperties: false},
		annotations: {readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false},
		run: async ({video, nom}) => {
			const v = cheminLocal(video, 'vidéo de référence');
			if (v.dir || !VIDEO_EXT.has(extOf(v.path))) throw new Refus(`Une vidéo est attendue (mp4, mov, m4v, mkv, avi, mts, webm) : ${v.path}`);
			const refs = path.join(ROOT, 'media', 'references');
			let fichier = propre(path.basename(v.path));
			if (dans(refs, v.path)) fichier = path.relative(refs, v.path).split(path.sep).join('/');
			else {
				// meme nom deja present : la meme video est reutilisee, une autre video prend « nom (2) » (rien n'est ecrase)
				const p = path.parse(fichier);
				for (let k = 2; ; k++) {
					const st = fs.statSync(path.join(refs, fichier), {throwIfNoEntry: false});
					if (!st || st.size === v.size) break;
					fichier = `${p.name} (${k})${p.ext}`;
				}
				if (!fs.existsSync(path.join(refs, fichier))) {
					await api('GET', '/api/reels'); // demarre l'editeur au besoin avant l'envoi
					await appel('PUT', `/api/references/${encodeURIComponent(fichier)}`, {file: v.path, timeout: 120000});
				}
			}
			const n = String(nom ?? '').trim().slice(0, 40);
			const job = await api('POST', '/api/references/analyser', {body: {fichier, ...(n ? {nom: n} : {})}});
			return `Analyse du style lancée (1 à 3 minutes) : ${fichier}\n• ${ligneTache(job)}\nSuis-la avec suivre_export (tache ${job.id}, attendre 180) ; ensuite applique le style avec changer_style.`;
		},
	},
	{
		name: 'ouvrir',
		title: 'Ouvrir l\'interface',
		description: `Adresse de l'interface de l'éditeur (${ORIGIN}) pour regarder les vidéos et les retoucher ; démarre l'éditeur au besoin. navigateur=true l'ouvre dans le navigateur par défaut.`,
		inputSchema: {type: 'object', properties: {navigateur: {type: 'boolean', description: 'Ouvrir aussi l\'interface dans le navigateur par défaut (défaut : non).'}}, additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async ({navigateur}) => {
			await api('GET', '/api/reels');
			if (navigateur) {
				const [cmd, args] = process.platform === 'win32' ? ['explorer.exe', [ORIGIN]] : [process.platform === 'darwin' ? 'open' : 'xdg-open', [ORIGIN]];
				spawn(cmd, args, {detached: true, stdio: 'ignore'}).on('error', () => {}).unref();
			}
			return `Interface de l'Éditeur Sami : ${ORIGIN}\nÉcran Révision : les vidéos montées toutes seules → « Je la prends », « Modifier » ou « Autre style ».`;
		},
	},
	{
		name: 'erreurs',
		title: 'Journaux d\'erreurs',
		description: 'Dernières lignes des journaux d\'erreurs de l\'éditeur (runtime\\cache\\erreurs.log du moteur, erreurs-serveur.log du serveur, serveur-mcp.log) '
			+ 'et vidéos en erreur. Pour comprendre un problème.',
		inputSchema: {type: 'object', properties: {lignes: {type: 'integer', minimum: 1, maximum: 300, description: 'Nombre de lignes par journal (défaut 40).'}}, additionalProperties: false},
		annotations: {readOnlyHint: true, openWorldHint: false},
		run: async ({lignes = 40}) => {
			const n = Math.min(300, Math.max(1, Number(lignes) || 40));
			const out = [];
			for (const [nom, quoi] of [['erreurs.log', 'moteur (montage, analyse, export Python)'], ['erreurs-serveur.log', 'serveur (plantages)'], ['serveur-mcp.log', 'démarrages par Claude']]) {
				const f = path.join(CACHE, nom);
				const t = queue(f, n);
				out.push(t === null ? `— ${nom} (${quoi}) : aucun journal.` : `— ${nom} (${quoi}), ${n} dernières lignes :\n${masquer(t) || '(vide)'}`);
			}
			if (await portOuvert()) {
				try {
					const {items} = await appel('GET', '/api/revision', {timeout: 10000});
					const ko = items.filter((i) => i.status === 'erreur');
					out.push(ko.length ? `— Vidéos en erreur :\n${ko.map((i) => `• [${i.id}] ${i.title || i.name} : ${masquer(i.error || '')}`).join('\n')}` : '— Aucune vidéo en erreur.');
				} catch (e) {
					out.push(`— Liste Révision illisible : ${messageErreur(e)}`);
				}
			} else out.push("— L'éditeur n'est pas lancé (les outils le démarrent au besoin).");
			return out.join('\n\n');
		},
	},
];

/** Fin d'un journal (lecture des derniers 256 Ko seulement). */
const queue = (file, n) => {
	let fd;
	try {
		fd = fs.openSync(file, 'r');
	} catch {
		return null;
	}
	try {
		const size = fs.fstatSync(fd).size;
		const len = Math.min(size, 262144);
		const buf = Buffer.alloc(len);
		fs.readSync(fd, buf, 0, len, size - len);
		return buf.toString('utf8').split(/\r?\n/).slice(len < size ? 1 : 0).filter((l, k, a) => l || k < a.length - 1).slice(-n).join('\n').trimEnd();
	} finally {
		fs.closeSync(fd);
	}
};

/** Jamais de cle dans une reponse : valeurs apres key/token/secret... et longues suites qui ressemblent a une cle. */
const masquer = (t) => String(t)
	.replace(/sk-ant-[A-Za-z0-9_-]{4,}/g, '[clé masquée]')
	.replace(/((?:api[_-]?key|apikey|key|token|secret|password|authorization)["']?\s*[:=]\s*["']?(?:bearer\s+)?)[^\s"'&,;]+/gi, '$1[masqué]')
	.replace(/\b\d{6,}-[0-9a-f]{32}\b/gi, '[masqué]')
	.replace(/\b[A-Za-z0-9]{40,}\b/g, '[masqué]');

// ---------- Protocole MCP (JSON-RPC 2.0 par lignes) ----------
const INSTRUCTIONS = `Outils de l'Éditeur Sami (monteur vidéo local et automatique ; interface ${ORIGIN}). Réponds en français simple, sans jargon. `
	+ 'Commence par etat pour connaître les vidéos et leurs identifiants. Lance monter, refaire, prendre ou style_reference seulement quand '
	+ 'l\'utilisateur le demande, une vidéo à la fois pour les exports. Ne lis jamais cles-api.env et n\'écris jamais dans D:\\Y0U. '
	+ 'Les outils longs, Blender, ACE-Step, le détourage, refaire_passage, choregraphie et l’ouverture de Resolve ne sont lancés que sur demande explicite. '
	+ 'controle (mode dernier) et banque_catalogue sont en lecture seule ; controle signale les problèmes avec leur moment, il ne corrige rien. '
	+ 'Pour Blender, utilise seulement tools\\blender\\blender.exe et ne cherche jamais dans D:\\Y0U. mettre_corbeille est récupérable et garde les exports ; '
	+ 'ne vide ni n’efface jamais définitivement la corbeille. Claude (IA en ligne d’Anthropic) est en option et PAYANT (petit crédit de l’utilisateur) : '
	+ 'claude_couts est en lecture seule ; claude_critique et consigne ne sont lancés que sur demande explicite, une fois, en annonçant le coût estimé.';

const envoyer = (msg) => process.stdout.write(`${JSON.stringify(msg)}\n`);
const annules = new Set();

const traiter = async (msg) => {
	if (!msg || typeof msg !== 'object' || Array.isArray(msg)) return envoyer({jsonrpc: '2.0', id: null, error: {code: -32600, message: 'Invalid Request'}});
	const {id, method, params} = msg;
	if (typeof method !== 'string') return; // reponse a une requete du serveur (il n'en envoie pas)
	const avecId = id !== undefined && id !== null;
	const repondre = (result) => avecId && !annules.has(id) && envoyer({jsonrpc: '2.0', id, result});
	const erreur = (code, message) => avecId && envoyer({jsonrpc: '2.0', id, error: {code, message}});
	switch (method) {
		case 'initialize':
			return repondre({
				protocolVersion: PROTOCOLES.includes(params?.protocolVersion) ? params.protocolVersion : PROTOCOLES[0],
				capabilities: {tools: {listChanged: false}},
				serverInfo: {name: 'editeur-sami', title: 'Éditeur Sami', version: VERSION},
				instructions: INSTRUCTIONS,
			});
		case 'ping':
			return repondre({});
		case 'tools/list':
			return repondre({tools: OUTILS.map(({name, title, description, inputSchema, annotations}) => ({name, title, description, inputSchema, annotations: {title, ...annotations}}))});
		case 'tools/call': {
			const outil = OUTILS.find((o) => o.name === params?.name);
			if (!outil) return erreur(-32602, `Unknown tool: ${params?.name}`);
			const token = params?._meta?.progressToken;
			let dernier = -1;
			const ctx = {
				progress: (progress, total, message) => {
					if (token === undefined || !(progress > dernier)) return;
					dernier = progress;
					envoyer({jsonrpc: '2.0', method: 'notifications/progress', params: {progressToken: token, progress, ...(total ? {total} : {}), ...(message ? {message} : {})}});
				},
				annule: () => annules.has(id),
			};
			const args = params.arguments && typeof params.arguments === 'object' ? params.arguments : {};
			try {
				return repondre({content: [{type: 'text', text: await outil.run(args, ctx)}]});
			} catch (e) {
				if (!(e instanceof Refus)) log(`${outil.name} : ${e.stack || e}`);
				return repondre({content: [{type: 'text', text: messageErreur(e)}], isError: true});
			} finally {
				annules.delete(id);
			}
		}
		case 'notifications/cancelled':
			if (params?.requestId !== undefined) annules.add(params.requestId);
			return;
		default:
			if (method.startsWith('notifications/')) return;
			return erreur(-32601, `Method not found: ${method}`);
	}
};

const rl = readline.createInterface({input: process.stdin, crlfDelay: Infinity});
rl.on('line', (line) => {
	if (!line.trim()) return;
	let msg;
	try {
		msg = JSON.parse(line);
	} catch {
		return envoyer({jsonrpc: '2.0', id: null, error: {code: -32700, message: 'Parse error'}});
	}
	for (const m of Array.isArray(msg) ? msg : [msg]) traiter(m).catch((e) => log(e.stack || e));
});
// le client est parti : on laisse le temps d'ecrire les dernieres reponses puis on s'arrete
rl.on('close', () => setTimeout(() => process.exit(0), 1500));
process.on('uncaughtException', (e) => log(`erreur : ${e.stack || e}`));
process.on('unhandledRejection', (e) => log(`erreur : ${e?.stack || e}`));
log(`pret (editeur : ${ROOT}, ${ORIGIN})`);
