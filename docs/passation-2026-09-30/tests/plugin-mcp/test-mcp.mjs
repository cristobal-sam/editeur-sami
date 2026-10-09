// Essai du serveur MCP : initialize, tools/list, outils en lecture seule, et validation des arguments des outils d'action
// (chaque cas d'action echoue AVANT tout appel qui modifie quelque chose). Aucun demarrage d'editeur (EDITEUR_MCP_SANS_DEMARRAGE=1).
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import readline from 'node:readline';

const SERVEUR = 'D:\\Tools\\editeur_sami\\plugins\\editeur-sami\\mcp\\serveur.mjs';
const SCRATCH = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const port = Number(process.argv[2] || 8790);

const ouvert = () => new Promise((r) => {
	const s = net.connect({host: '127.0.0.1', port});
	s.setTimeout(4000, () => (s.destroy(), r(false)));
	s.once('connect', () => (s.destroy(), r(true)));
	s.once('error', () => r(false));
});

const client = () => {
	const child = spawn(process.execPath, [SERVEUR], {env: {...process.env, EDITEUR_PORT: String(port), EDITEUR_MCP_SANS_DEMARRAGE: '1'}, stdio: ['pipe', 'pipe', 'pipe']});
	const pending = new Map();
	const bad = [];
	const notes = [];
	let stderr = '';
	child.stderr.on('data', (d) => (stderr += d));
	readline.createInterface({input: child.stdout}).on('line', (line) => {
		let m;
		try {
			m = JSON.parse(line);
		} catch {
			bad.push(line);
			return;
		}
		if (m.method) return notes.push(m);
		pending.get(m.id)?.(m);
		pending.delete(m.id);
	});
	let n = 0;
	const req = (method, params) => new Promise((resolve) => {
		const id = ++n;
		pending.set(id, resolve);
		child.stdin.write(`${JSON.stringify({jsonrpc: '2.0', id, method, ...(params ? {params} : {})})}\n`);
	});
	const notif = (method, params) => child.stdin.write(`${JSON.stringify({jsonrpc: '2.0', method, ...(params ? {params} : {})})}\n`);
	const close = () => new Promise((r) => {
		child.on('exit', (code) => r(code));
		child.stdin.end();
	});
	return {req, notif, close, bad, notes, stderr: () => stderr};
};

const show = (title, obj, max = 2500) => {
	const t = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 1);
	console.log(`\n===== ${title} =====\n${t.length > max ? `${t.slice(0, max)}\n… (${t.length} caracteres)` : t}`);
};
const texte = (r) => r.result?.content?.map((c) => c.text).join('\n') ?? JSON.stringify(r.error ?? r);

if (port === 8790 && !(await ouvert())) {
	console.log('Editeur non lance sur 8790 : essais annules (on ne le demarre pas).');
	process.exit(2);
}

const c = client();
const init = await c.req('initialize', {protocolVersion: '2025-06-18', capabilities: {}, clientInfo: {name: 'essai', version: '0'}});
show('initialize (2025-06-18)', init.result);
c.notif('notifications/initialized');
show('ping', await c.req('ping'));
const list = await c.req('tools/list', {});
show('tools/list (noms + champs requis)', list.result.tools.map((t) => `${t.name} [${t.annotations?.readOnlyHint ? 'lecture' : 'action'}] requis=${JSON.stringify(t.inputSchema.required || [])} props=${Object.keys(t.inputSchema.properties).join(',')}`).join('\n'));

if (port !== 8790) {
	// editeur absent : l'outil le dit, sans rien demarrer
	const r = await c.req('tools/call', {name: 'etat', arguments: {}});
	show(`etat sur le port ${port} (aucun editeur)`, `isError=${r.result.isError}\n${texte(r)}`);
} else {
	for (const [name, args] of [['etat', {}], ['etat', {filtre: 'tout', limite: 5}], ['styles', {}], ['erreurs', {lignes: 8}], ['ouvrir', {}], ['suivre_export', {}]]) {
		const r = await c.req('tools/call', {name, arguments: args});
		show(`${name} ${JSON.stringify(args)}  isError=${!!r.result?.isError}`, texte(r), 4000);
	}
	// dossier d'essai hors de l'editeur (videos vides : jamais envoyees, la validation echoue avant)
	const dir = path.join(SCRATCH, 'lot-essai');
	fs.mkdirSync(path.join(dir, 'Tournage'), {recursive: true});
	for (const f of ['a.mp4', 'b.mov', 'Tournage/prise1.mp4', 'notes.pdf', 'script.pdf']) fs.writeFileSync(path.join(dir, f), '');
	const cas = [
		['monter', {}],
		['monter', {chemins: []}],
		['monter', {chemins: ['D:\\nexiste\\pas.mp4']}],
		['monter', {chemins: ['https://exemple.com/video.mp4']}],
		['monter', {chemins: ['\\\\serveur\\partage\\video.mp4']}],
		['monter', {chemins: ['D:\\Tools\\editeur_sami\\cles-api.env']}],
		['monter', {chemins: ['D:\\Tools\\editeur_sami\\projects']}],
		['monter', {chemins: ['D:\\Tools\\editeur_sami\\media\\entree']}],
		['monter', {chemins: ['D:\\']}],
		['monter', {chemins: [dir]}],
		['monter', {chemins: [dir], dossier: 'autre'}],
		['monter', {chemins: [path.join(dir, 'notes.pdf')]}],
		['prendre', {video: 'zzzzzzzzzzzz'}],
		['prendre', {}],
		['changer_style', {video: 'nexistepas', style: 'reel-impact'}],
		['refaire', {video: '000000000000'}],
		['retirer', {video: 'aucune-video'}],
		['toujours_ce_style', {sujet: 'inconnu', style: 'reel-impact'}],
		['toujours_ce_style', {sujet: 'pub', style: 'style-qui-nexiste-pas'}],
		['style_reference', {video: 'D:\\nexiste\\ref.mp4'}],
		['style_reference', {video: dir}],
		['style_reference', {video: path.join(dir, 'notes.pdf')}],
		['suivre_export', {tache: 'pas-un-id'}],
		['suivre_export', {tache: '00000000-0000-0000-0000-000000000000'}],
	];
	for (const [name, args] of cas) {
		const r = await c.req('tools/call', {name, arguments: args});
		show(`${name} ${JSON.stringify(args)}  isError=${!!r.result?.isError}`, texte(r), 900);
	}
	fs.rmSync(dir, {recursive: true, force: true});
}
show('outil inconnu', await c.req('tools/call', {name: 'nexiste', arguments: {}}));
show('methode inconnue', await c.req('resources/list', {}));
const c2 = await c.req('initialize', {protocolVersion: '1999-01-01', capabilities: {}, clientInfo: {name: 'essai', version: '0'}});
show('initialize (version inconnue -> la plus recente)', c2.result.protocolVersion);
const code = await c.close();
show('fin', `code de sortie ${code} ; lignes non JSON sur stdout : ${c.bad.length} ; notifications : ${c.notes.length}\nstderr :\n${c.stderr()}`);
