// Étape 5 (Fable, 2026-09-30) : après le redémarrage du vrai serveur, relancer « Refaire » sur les vidéos de la
// Révision (une à la fois par la file du serveur, AUCUN export) et attendre qu'elles soient prêtes.
//   node docs/taches-fable/tests/etape5.mjs verifier            -> état du serveur, route de suppression, rien en cours
//   node docs/taches-fable/tests/etape5.mjs refaire <id> [<id>] -> clique « Refaire » puis attend « Prête »
const BASE = 'http://127.0.0.1:8790';
const call = async (method, route, body) => {
	const r = await fetch(BASE + route, {method, headers: {'content-type': 'application/json', origin: BASE}, body: body ? JSON.stringify(body) : undefined});
	return {status: r.status, data: await r.json().catch(() => null)};
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const [mode, ...ids] = process.argv.slice(2);

const etat = async () => {
	const rev = (await call('GET', '/api/revision')).data;
	const queue = (await call('GET', '/api/queue')).data;
	const enCours = (queue || []).filter((j) => ['queued', 'running'].includes(j.status));
	return {rev, enCours};
};

if (mode === 'verifier') {
	const {rev, enCours} = await etat();
	console.log(`busy=${rev.busy} · exports en cours=${enCours.length} · corbeille annoncée=${rev.corbeille ?? '(absente : ancien code)'}`);
	for (const i of rev.items) console.log(`  [${i.id}] ${i.title || i.name} — ${i.status} — style ${i.style} — projet ${i.project}`);
	const corb = await call('GET', '/api/revision/corbeille');
	console.log(`GET /api/revision/corbeille -> ${corb.status} ${corb.status === 200 ? '(nouveau code)' : '(route absente : ancien code)'}`);
	process.exitCode = rev.busy || enCours.length ? 2 : 0;
}

if (mode === 'refaire') {
	if (!ids.length) throw new Error('identifiants manquants');
	for (const id of ids) {
		const r = await call('POST', `/api/revision/${id}/refaire`, {});
		console.log(`refaire ${id} -> ${r.status}${r.data?.error ? ` ${r.data.error}` : ''}`);
		if (r.status >= 400) throw new Error(r.data?.error || `Refaire refuse : ${r.status}`);
	}
	const t0 = Date.now();
	let last = '';
	for (;;) {
		await sleep(5000);
		const {rev} = await etat();
		const mine = rev.items.filter((i) => ids.includes(i.id));
		const line = mine.map((i) => `${i.id.slice(0, 4)}:${i.status}${i.status === 'travail' ? ` ${Math.round(100 * (i.progress || 0))} % ${i.stage}` : ''}`).join(' | ');
		if (line !== last) {
			console.log(`${Math.round((Date.now() - t0) / 1000)} s  ${line}`);
			last = line;
		}
		if (mine.length === ids.length && mine.every((i) => ['pret', 'pris', 'erreur'].includes(i.status)) && !rev.busy) {
			for (const i of mine) console.log(`\n[${i.id}] ${i.title || i.name} — ${i.status} — style ${i.style} — plans de coupe ${i.broll} — projet ${i.project}${i.error ? `\n  ERREUR : ${i.error}` : ''}${i.alerts?.length ? `\n  alertes : ${i.alerts.join(' / ')}` : ''}${i.sobriete ? `\n  relecture : ${i.sobriete}` : ''}`);
			if (mine.some((i) => i.status === 'erreur')) process.exitCode = 1;
			break;
		}
		if (Date.now() - t0 > 45 * 60000) {
			console.log('Délai dépassé (45 min).');
			process.exitCode = 3;
			break;
		}
	}
}
