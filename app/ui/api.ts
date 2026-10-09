import {useEffect, useRef, useState} from 'react';

export type Job = {id: string; status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled'; stage: string; progress: number; out?: string; result?: any; error?: string;
	seconds?: number; title?: string; format?: string};

export const api = async (url: string, method = 'GET', body?: unknown) => {
	const r = await fetch(url, {method, headers: {'content-type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
	const data = await r.json();
	if (!r.ok) throw new Error(data.error || `Erreur ${r.status}`);
	return data;
};

export const fmt = (t: number) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`;
/** Duree courte « 1:08 » (secondes entieres) : lecteur et fiches de la Revision. */
export const mmss = (t: number) => {
	const s = Math.max(0, Math.floor(Number.isFinite(t) ? t : 0));
	return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

/** Suit une tache longue du serveur (export, musique, recherche...) jusqu'a la fin. */
export const useJob = (onDone?: (job: Job) => void) => {
	const [job, setJob] = useState<Job | null>(null);
	const done = useRef(onDone);
	done.current = onDone;
	useEffect(() => {
		if (!job || (job.status !== 'running' && job.status !== 'queued')) return;
		const id = window.setInterval(async () => {
			try {
				const r = await fetch(`/api/jobs/${job.id}`);
				if (r.status === 404) {
					// l'editeur a redemarre : la tache n'existe plus, on le dit au lieu de tourner sans fin
					setJob({...job, status: 'failed', error: "Tâche interrompue (l'éditeur a redémarré) : relance-la."});
					return;
				}
				const j: Job = await r.json();
				setJob(j);
				if (j.status === 'done') done.current?.(j);
			} catch {}
		}, 1000);
		return () => window.clearInterval(id);
	}, [job]);
	return [job, setJob] as const;
};
