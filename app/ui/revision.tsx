// Ecran « Revision » (par defaut) : on depose des videos brutes, l'outil les monte seul (sujet -> style adapte),
// on regarde : « Je la prends » (export), « Modifier » (editeur complet) ou « Autre style ».
// Mise en page et jetons de design : maquette Claude Design (docs/design/maquette/ANALYSE.md, captures/revision-1440.png).
// Raccourcis : Entree = Je la prends, E = Modifier, S = Autre style, fleche droite = Suivante, Espace = lecture, Echap = fermer.
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Player, type PlayerRef} from '@remotion/player';
import {Reel} from '../../remotion/src/Reel';
import {duration} from '../../remotion/src/timeline';
import {FORMATS, formatOf, type ReelDoc} from '../../remotion/src/types';
import {api, fmt, mmss, useJob} from './api';
import {SaveStyleCard, type Template} from './panels2';
import {Consigne} from './consigne';
import * as I from './icons';

/** Controle qualite (engine/editeur/controle.py, resume) : note /10, verdict, constats classes du plus grave au moins grave.
 * temps = secondes du montage ; zone = boite [x0, y0, x1, y1] en px du format « format » (ex. 1080x1920). */
export type Constat = {gravite: 'bloquant' | 'important' | 'conseil'; code: string; temps: number | null; fin: number | null; message: string;
	suggestion: string; zone?: [number, number, number, number]; element?: string; plages?: [number, number][]};
export type Controle = {version: number; date: string; note: number; verdict: string; compte: {bloquant: number; important: number; conseil: number};
	video?: string | null; format?: string | null; total?: number; constats: Constat[]};
/** Resultat range sur un export : le resume, ou l'erreur du controle (jamais bloquant pour la livraison). */
type ControleExport = Controle | {erreur: string; date?: string};
const aNote = (c?: ControleExport | null): c is Controle => !!c && typeof (c as Controle).note === 'number';

// ---------- Claude (IA en ligne, en option et payant) : etat partage par les reglages ⚙️ et la Revision ----------
// Le serveur (GET /api/claude) ne donne jamais la cle : seulement « cle » = vrai / faux. Rien ne part vers Claude sans un clic.
/** Cout typique d'un appel (estimation_video du moteur, pas un plafond). */
export type ClaudeEstimation = {modele: string; nom: string; cerveau: number; consigne: number; critique: number; par_video: number; videos_avec_credit: number; texte: string};
export type ClaudeStatut = {indisponible?: boolean; cle: boolean; actif: boolean; pret: boolean; raison: string; avertissement?: string; modele?: string; nom_modele?: string;
	modeles_taches?: Partial<Record<'cerveau' | 'critique' | 'consigne', string | null>>; plafonds?: {video: number; jour: number; mois: number};
	depense_jour?: number; depense_mois?: number; credit_depart?: number; credit_date?: string; credit_restant_estime?: number; appels_jour?: number;
	dernier_appel?: {date: string; tache: string; cout: number; modele: string} | null; credit_epuise?: boolean; critique_auto?: boolean;
	espace_travail?: boolean; espace_manquant?: boolean; modeles?: {id: string; nom: string; conseil: string; estimation?: ClaudeEstimation}[]; estimation?: ClaudeEstimation};
/** Depenses Claude d'une video (registre du moteur), par tache. */
export type ClaudeGroupe = {n: number; ok: number; cout: number; dernier: string | null};
export type ClaudeVideo = {cout: number; nb: number; dernier: string | null; groupes: Partial<Record<'cerveau' | 'critique' | 'consigne' | 'autre', ClaudeGroupe>>};
type ClaudeAppel = {date: string; tache: string; video: string | null; modele: string | null; cout: number; ok: boolean; erreur: string | null; secondes: number};
type ClaudeCouts = {mois: {cout: number; appels: number}; credit: {restant_estime: number}; jours: {date: string; cout: number; appels: number}[]; derniers?: ClaudeAppel[]};
type ClaudeEtat = {statut: ClaudeStatut | null; absent: boolean};
/** 0,04 $ (« < 0,01 $ » pour un tout petit montant). */
export const argent = (x?: number | null) => {
	const v = Number(x) || 0;
	return v > 0 && v < 0.005 ? '< 0,01 $' : `${v.toFixed(2).replace('.', ',')} $`;
};
const MODELES_CLAUDE: Record<string, {nom: string; mot: string}> = {'claude-sonnet-5-5': {nom: 'Sonnet 5.5', mot: 'recommandé'},
	'claude-haiku-4-5': {nom: 'Haiku 4.5', mot: 'très économique'}, 'claude-opus-5-5': {nom: 'Opus 5.5', mot: 'meilleure qualité'}};
const nomModele = (id?: string | null) => (id ? MODELES_CLAUDE[id]?.nom ?? id.replace(/^claude-/, '') : '');
const TACHES_CLAUDE: Record<string, string> = {cerveau: 'idées du montage', critique: 'relecture des images', consigne: 'demande « Dis à l’IA »', test: 'essai de connexion'};
const tacheFr = (t: string) => TACHES_CLAUDE[Object.keys(TACHES_CLAUDE).find((k) => t.startsWith(k)) ?? ''] ?? t;
const aujourdhui = () => new Date().toLocaleDateString('sv-SE'); // AAAA-MM-JJ, heure locale
/** « 09:40 » aujourd'hui, « 01/10 09:40 » un autre jour (liste des derniers appels). */
const heureCourte = (date: string) => {
	const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})/.exec(date || '');
	if (!m) return date;
	return `${m[1]}-${m[2]}-${m[3]}` === aujourdhui() ? m[4] : `${m[3]}/${m[2]} ${m[4]}`;
};
/** Cout typique d'une tache avec le modele qui la fera (modele par tache, sinon le modele general). */
const estimationClaude = (s: ClaudeStatut | null, tache: 'cerveau' | 'critique' | 'consigne') => {
	if (!s) return null;
	const m = s.modeles_taches?.[tache] || s.modele;
	const e = s.modeles?.find((x) => x.id === m)?.estimation ?? (s.estimation?.modele === m ? s.estimation : null);
	return typeof e?.[tache] === 'number' ? e[tache] : null;
};
// une seule lecture de GET /api/claude pour toute la page (barre du haut + Revision) ; relue toutes les 60 s et apres un appel
let claudeMemo: ClaudeEtat = {statut: null, absent: false};
let claudeLu = 0;
let claudeEnCours: Promise<void> | null = null;
const claudeAbonnes = new Set<(e: ClaudeEtat) => void>();
const publierClaude = (e: ClaudeEtat) => {
	claudeMemo = e;
	claudeAbonnes.forEach((f) => f(e));
};
/** Nouvel etat recu (reponse de PUT /api/claude/reglages). */
const majClaude = (s: ClaudeStatut) => {
	claudeLu = Date.now();
	publierClaude({statut: s, absent: false});
};
export const relireClaude = (force = false): Promise<void> => {
	if (claudeEnCours) return claudeEnCours;
	if (!force && Date.now() - claudeLu < 15000 && (claudeMemo.statut || claudeMemo.absent)) return Promise.resolve();
	claudeEnCours = api('/api/claude').then((s: ClaudeStatut) => majClaude(s)).catch((e) => {
		claudeLu = Date.now();
		// serveur lance avant cette version : la route n'existe pas (on le dit au lieu de « Introuvable. »)
		if ((e as Error).message === 'Introuvable.') publierClaude({statut: null, absent: true});
	}).finally(() => {
		claudeEnCours = null;
	});
	return claudeEnCours;
};
const useClaude = () => {
	const [etat, setEtat] = useState<ClaudeEtat>(claudeMemo);
	useEffect(() => {
		claudeAbonnes.add(setEtat);
		relireClaude();
		const t = window.setInterval(() => relireClaude(true), 60000);
		return () => {
			claudeAbonnes.delete(setEtat);
			window.clearInterval(t);
		};
	}, []);
	return etat;
};
/** « Claude : cerveau ✓ (0,03 $) · critique ✓ (0,02 $) · consignes 2 (0,03 $) » ('' si Claude n'a pas servi). */
const ligneClaude = (c?: ClaudeVideo | null) => {
	if (!c || (!c.nb && !c.cout)) return '';
	const g = c.groupes ?? {};
	const parts = [g.cerveau ? `cerveau ${g.cerveau.ok ? '✓' : '✗'} (${argent(g.cerveau.cout)})` : '', g.critique ? `critique ${g.critique.ok ? '✓' : '✗'} (${argent(g.critique.cout)})` : '',
		g.consigne ? `consignes ${g.consigne.n} (${argent(g.consigne.cout)})` : '', g.autre ? `autres ${g.autre.n} (${argent(g.autre.cout)})` : ''].filter(Boolean);
	return `Claude : ${parts.length ? parts.join(' · ') : argent(c.cout)}`;
};
/** « Idées : Claude Sonnet 5.5 (0,04 $) » ou « Idées : IA locale — <raison> » : cerveau du montage automatique (reel.auto.cerveau,
 * ecrit par auto._finish) ; '' pour un montage fait avant le cerveau Claude. */
type CerveauAuto = {ok?: boolean; source?: string; modele?: string; cout?: number; raison?: string};
const ligneCerveau = (reel?: ReelDoc | null) => {
	const c = (reel as (ReelDoc & {auto?: {cerveau?: CerveauAuto}}) | null)?.auto?.cerveau;
	if (!c || typeof c !== 'object') return '';
	if (c.ok) return `Idées : Claude ${nomModele(c.modele) || ''}${c.source === 'garde' ? ' (déjà payé)' : typeof c.cout === 'number' ? ` (${argent(c.cout)})` : ''}`.replace('  ', ' ');
	const r = String(c.raison ?? '').replace(/\s*L'outil continue en local\.?$/, '');
	return `Idées : IA locale${r ? ` — ${r.length > 150 ? `${r.slice(0, 149)}…` : r}` : ''}`;
};
/** Avis de Claude sur les images (critique) : rangé dans le reel par le moteur, ou resultat de la tache. Formes acceptees :
 * {note, verdict, problemes: [{t|temps, fin?, texte|message, suggestion?, gravite?}]} (ou dans « avis »). */
type AvisProbleme = {t: number | null; fin: number | null; texte: string; suggestion: string; gravite: string};
type Avis = {note: number | null; verdict: string; problemes: AvisProbleme[]; date: string; cout: number | null; modele: string};
const avisDe = (x: unknown): Avis | null => {
	if (!x || typeof x !== 'object') return null;
	const o = x as Record<string, any>;
	const a = (o.avis && typeof o.avis === 'object' ? o.avis : o) as Record<string, any>;
	// avis non obtenu (Claude eteint, plafond, credit, erreur : critique_claude.py rend ok = false et « message ») : pas d'avis
	// a montrer (jamais « aucun probleme » a tort) ; « resume » du resultat = le resume du rapport du controle, pas une phrase
	if (o.ok === false || a.ok === false) return null;
	const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
	const liste: any[] = [a.problemes, a.problems, a.constats].find(Array.isArray) ?? [];
	const problemes = liste.filter((p) => p && typeof p === 'object').map((p) => ({t: num(p.t ?? p.temps ?? p.debut), fin: num(p.fin), texte: String(p.texte ?? p.message ?? p.probleme ?? ''),
		suggestion: String(p.suggestion ?? p.conseil ?? ''), gravite: String(p.gravite ?? '')})).filter((p) => p.texte);
	const note = num(a.note);
	const verdict = [a.verdict, a.resume].find((v) => typeof v === 'string') ?? '';
	if (note === null && !verdict && !problemes.length) return null;
	// cout_avis = prix de l'avis (cout = paye par CET appel : 0 quand l'avis etait deja paye)
	return {note, verdict, problemes, date: String(a.date ?? o.date ?? ''), cout: num(a.cout_avis ?? o.cout_avis ?? o.cout ?? a.cout), modele: String(o.modele ?? a.modele ?? '')};
};
const avisDuReel = (reel?: ReelDoc | null) => {
	const r = reel as (ReelDoc & Record<string, any>) | null | undefined;
	return r ? avisDe(r.claude?.critique) ?? avisDe(r.critiqueClaude) ?? avisDe(r.critique_claude) ?? avisDe(r.controle?.claude) : null;
};

/** Un export par format coche dans « Je la prends ». interrompu = l'editeur a redemarre pendant l'export.
 * controle = controle qualite de la video livree (lance tout seul apres l'export) ; controleEtat = en attente / en cours. */
export type ItemExport = {format: string; job: string; out: string; status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'interrompu';
	progress?: number; stage?: string; error?: string | null; seconds?: number | null; controle?: ControleExport | null;
	controleEtat?: 'queued' | 'running' | null};
export type Item = {
	id: string; unit: string; lot: string; name: string; status: 'attente' | 'travail' | 'pret' | 'pris' | 'erreur';
	stage: string; progress: number; project?: string; rid?: string; type?: string; typeLabel?: string; title?: string;
	reason?: string; style?: string; broll?: number; error?: string | null; exports?: ItemExport[];
	previousStyleVersion?: string | null;
	alerts?: string[]; ia?: boolean; updated?: number; created?: number;
	/** Note du controle qualite du montage (resume ; les constats sont dans reel.controle). */
	controle?: (Pick<Controle, 'note' | 'verdict' | 'compte' | 'date'> & {stamp?: number}) | null;
	taken?: {out: string; outs?: string[]; formats?: string[]; date: number} | null;
	/** Ce qu'une suppression garderait : une autre video (meme retiree de la liste) utilise les memes videos brutes / le meme montage. */
	partage?: {unit: boolean; project: boolean};
	/** Depenses Claude de cette video (badge « 🧠 0,04 $ ») ; tache de l'IA en cours sur elle (un appel a la fois). */
	claude?: ClaudeVideo | null;
	iaEnCours?: {job: string; stage: string} | null;
};
type State = {items: Item[]; lots: Record<string, {client?: string | null}>; entree: string; corbeille?: string; corbeilleN?: number; busy: boolean};
type Opened = {reel: ReelDoc};
/** Resultat d'une suppression (le serveur range le montage et les videos brutes dans la corbeille de l'editeur). */
type Deleted = {id: string; titre: string; corbeille: string | null; deplaces: string[]; gardes: string[]; livraisons: string[]};
/** Une entree de la corbeille (dossier corbeille\<date> <titre>\ avec son corbeille.json). */
type TrashEntry = {dossier: string; titre: string; supprime: string | null; deplacements: {avant: string; maintenant: string}[]; gardes: string[]; restaurable: boolean; raison: string};
type Restored = {titre: string; remis: string[]; item: Item | null; note: string};
/** Compteurs de la barre du haut (« Aujourd'hui · 7 vidéos · 3 prêtes · 1 prises »), tires de /api/revision. */
export type RevisionCompte = {jour: number; total: number; pretes: number; prises: number; entree?: string; corbeille?: string};
const dateFr = (iso: string | null) => {
	const d = iso ? new Date(iso) : null;
	return d && !Number.isNaN(d.getTime()) ? d.toLocaleString('fr-CA', {dateStyle: 'short', timeStyle: 'short'}) : '';
};
/** « aujourd'hui à 05 h 57 » / « le 01/10 à 05 h 57 » (corbeille). */
const dateCourte = (iso: string) => {
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return '';
	const h = `${String(d.getHours()).padStart(2, '0')} h ${String(d.getMinutes()).padStart(2, '0')}`;
	return memeJour(d.getTime()) ? `aujourd'hui à ${h}` : `le ${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')} à ${h}`;
};
const memeJour = (ms?: number | null) => {
	if (!ms) return false;
	const d = new Date(ms);
	const n = new Date();
	return d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate();
};
/** vidéos = deposees aujourd'hui ; prêtes = a regarder (tous jours) ; prises = exportees aujourd'hui. */
const compter = (s: State): RevisionCompte => ({jour: s.items.filter((i) => memeJour(i.created)).length, total: s.items.length,
	pretes: s.items.filter((i) => i.status === 'pret').length, prises: s.items.filter((i) => i.status === 'pris' && memeJour(i.taken?.date)).length,
	entree: s.entree, corbeille: s.corbeille});

const ALLOWED = /\.(mp4|mov|m4v|mkv|avi|mts|webm|docx|txt|pdf)$/i;
const FORMAT_LABEL: Record<string, string> = {'9:16': '9:16 vertical', '16:9': '16:9 horizontal', '4:5': '4:5 publication', '1:1': '1:1 carré'};
const FORMAT_NAMES: Record<string, string> = {'9:16': 'vertical (Reels, TikTok, Shorts)', '16:9': 'horizontal (YouTube)', '4:5': 'publication (fil Instagram, Facebook)', '1:1': 'carré'};
/** Petit cadre dessine dans la pastille de format (largeur, hauteur en px). */
const FORMAT_CADRE: Record<string, [number, number]> = {'9:16': [8, 13], '16:9': [14, 8], '4:5': [10, 12], '1:1': [11, 11]};
const running = (e: ItemExport) => e.status === 'queued' || e.status === 'running';
/** Pourquoi une video ne peut pas etre supprimee maintenant ('' = possible). */
const deleteBlock = (i: Item) => (i.status === 'travail' ? 'Montage en cours : attends la fin pour la supprimer.'
	: (i.exports ?? []).some(running) ? 'Export en cours : annule-le d\'abord (bouton « Annuler »), puis supprime-la.' : '');
const winPath = (p: string) => p.replace(/\//g, '\\');
const pctExports = (list: ItemExport[]) => (list.length ? Math.round((100 * list.reduce((a, e) => a + (e.status === 'done' ? 1 : e.progress ?? 0), 0)) / list.length) : 0);
/** Fond des vignettes sans image (videos pas encore montees) : couleurs de la maquette, choisies par la video. */
const FONDS = ['linear-gradient(165deg,#24425A 0%,#101A26 55%,#2B2150 100%)', 'linear-gradient(165deg,#4A2B2B 0%,#1A1214 55%,#2A1F33 100%)',
	'linear-gradient(165deg,#3B3424 0%,#15130E 60%,#1F2630 100%)', 'linear-gradient(165deg,#1F2A2A 0%,#0F1414 100%)',
	'linear-gradient(165deg,#1E3B3A 0%,#0F1717 55%,#25304A 100%)', 'linear-gradient(165deg,#1C2E4A 0%,#0D1420 55%,#13303A 100%)',
	'linear-gradient(165deg,#2A2A30 0%,#121216 100%)'];
const FONDS_STYLE = ['linear-gradient(135deg,#3A1F2B,#141018,#4A2A1E,#141018)', 'linear-gradient(135deg,#2E2E12,#121208,#3A2A10,#121208)',
	'linear-gradient(135deg,#132A44,#0A111C,#1A3A4A,#0A111C)', 'linear-gradient(135deg,#123A33,#08130F,#1A2E44,#08130F)',
	'linear-gradient(135deg,#2E2A22,#11100D,#232A2E,#11100D)', 'linear-gradient(135deg,#3A2440,#140E16,#40301E,#140E16)',
	'linear-gradient(135deg,#1F2C44,#0C1018,#44281F,#0C1018)', 'linear-gradient(135deg,#1A3550,#0A0F1A,#2E2050,#0A0F1A)'];
const hash = (s: string) => [...s].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
const fondDe = (s: string, list = FONDS) => list[hash(s) % list.length];
const PLAYER_STYLE: React.CSSProperties = {width: '100%', height: '100%'};

/** Formats coches la derniere fois (propres a ce navigateur ; 9:16 si rien n'est garde ou si le stockage est bloque). */
const FORMATS_KEY = 'revision.formats';
const loadFormats = (): string[] => {
	try {
		const v = JSON.parse(window.localStorage.getItem(FORMATS_KEY) || 'null');
		if (Array.isArray(v) && v.length && v.every((f) => typeof f === 'string' && FORMATS[f])) return v;
	} catch {}
	return ['9:16'];
};
const storeFormats = (list: string[]) => {
	try {
		window.localStorage.setItem(FORMATS_KEY, JSON.stringify(list));
	} catch {}
};

/** Fichiers deposes (y compris des dossiers entiers : on garde leur chemin relatif). */
const readDrop = async (dt: DataTransfer): Promise<{file: File; rel: string}[]> => {
	const out: {file: File; rel: string}[] = [];
	const walk = async (entry: any, prefix: string): Promise<void> => {
		if (entry.isFile) {
			const file: File = await new Promise((res, rej) => entry.file(res, rej));
			out.push({file, rel: prefix + file.name});
		} else if (entry.isDirectory) {
			const reader = entry.createReader();
			let batch: any[] = [];
			do {
				batch = await new Promise((res, rej) => reader.readEntries(res, rej));
				for (const e of batch) await walk(e, `${prefix}${entry.name}/`);
			} while (batch.length);
		}
	};
	const entries = [...dt.items].map((i) => (i as any).webkitGetAsEntry?.()).filter(Boolean);
	if (entries.length) for (const e of entries) await walk(e, '');
	else [...dt.files].forEach((file) => out.push({file, rel: file.name}));
	return out;
};

/** Depot de videos brutes (glisser-deposer n'importe ou dans la page, fichiers ou dossier) : partage par la carte de gauche
 * et par le grand cadre de l'ecran vide. */
const useDepot = (onDone: () => void, galerie = false) => {
	// galerie « Autre style » ouverte : une video lachee dans la page n'est PAS envoyee au montage (on voulait sans doute la
	// deposer sur « Style depuis une video ») ; seule cette carte accepte alors un depot
	const galerieOuverte = useRef(galerie);
	galerieOuverte.current = galerie;
	const [clients, setClients] = useState<{client: string; name: string}[]>([]);
	const [client, setClient] = useState('');
	const [progress, setProgress] = useState<{done: number; total: number; skipped: number} | null>(null);
	const [err, setErr] = useState('');
	const [over, setOver] = useState(false);
	const files = useRef<HTMLInputElement>(null);
	const folder = useRef<HTMLInputElement>(null);
	useEffect(() => {
		api('/api/clients').then(setClients).catch(() => undefined);
	}, []);
	const envoi = useRef(false); // un seul envoi a la fois (un 2e glisser-deposer pendant l'envoi melangerait les compteurs)
	const send = useCallback(async (list: {file: File; rel: string}[]) => {
		if (envoi.current) return setErr('Un envoi est déjà en cours : attends qu\'il soit fini, puis dépose les autres vidéos.');
		const ok = list.filter((f) => ALLOWED.test(f.rel) && !f.rel.split('/').some((s) => s.startsWith('.')));
		if (!ok.length) return setErr('Aucune vidéo dans ce dépôt (formats acceptés : mp4, mov, mkv, avi, webm ; scripts .docx, .txt ou .pdf).');
		envoi.current = true;
		setErr('');
		setProgress({done: 0, total: ok.length, skipped: list.length - ok.length});
		try {
			const {lot} = await api('/api/entree/lot', 'POST', {client: client || null});
			for (let k = 0; k < ok.length; k++) {
				const rel = ok[k].rel.split('/').map(encodeURIComponent).join('/');
				const r = await fetch(`/api/entree/${encodeURIComponent(lot)}/${rel}`, {method: 'PUT', body: ok[k].file});
				if (!r.ok) throw new Error((await r.json()).error || `Erreur ${r.status}`);
				setProgress({done: k + 1, total: ok.length, skipped: list.length - ok.length});
			}
			await api(`/api/entree/${encodeURIComponent(lot)}/fin`, 'POST', {});
			onDone();
		} catch (e) {
			setErr((e as Error).message);
		} finally {
			envoi.current = false;
			setProgress(null);
		}
	}, [client, onDone]);
	useEffect(() => {
		const enter = (e: DragEvent) => {
			if (e.dataTransfer?.types.includes('Files')) {
				e.preventDefault();
				if (galerieOuverte.current) e.dataTransfer.dropEffect = 'none';
				else setOver(true);
			}
		};
		const drop = async (e: DragEvent) => {
			if (!e.dataTransfer?.types.includes('Files')) return;
			e.preventDefault();
			setOver(false);
			if (galerieOuverte.current) {
				setErr('La galerie de styles est ouverte : rien n\'a été envoyé au montage. Dépose ton reel modèle sur « Style depuis une vidéo », '
					+ 'ou ferme la galerie pour déposer des vidéos à monter.');
				return;
			}
			send(await readDrop(e.dataTransfer));
		};
		window.addEventListener('dragover', enter);
		window.addEventListener('drop', drop);
		return () => {
			window.removeEventListener('dragover', enter);
			window.removeEventListener('drop', drop);
		};
	}, [send]);
	const pick = (input: HTMLInputElement | null) => {
		const list = [...(input?.files ?? [])].map((file) => ({file, rel: (file as any).webkitRelativePath || file.name}));
		if (input) input.value = '';
		if (list.length) send(list);
	};
	const inputs = (
		<>
			<input ref={files} type="file" multiple accept="video/*,.docx,.txt,.pdf" hidden onChange={(e) => pick(e.currentTarget)} />
			<input ref={folder} type="file" hidden onChange={(e) => pick(e.currentTarget)} {...{webkitdirectory: '', directory: ''}} />
		</>
	);
	return {clients, client, setClient, progress, err, over, setOver, inputs,
		choisirVideos: () => files.current?.click(), choisirDossier: () => folder.current?.click()};
};
type Depot = ReturnType<typeof useDepot>;

/** Carte de depot (colonne de gauche). */
const DepotCarte: React.FC<{depot: Depot}> = ({depot}) => (
	<div className="sr-depot">
		<div className="sr-depot-tete">
			<div className="sr-depot-ic"><I.Upload size={17} /></div>
			<div>
				<b>Ajouter des vidéos brutes</b>
				<span>Glisse tes fichiers ici</span>
			</div>
		</div>
		<button className="sr-btn" disabled={!!depot.progress} onClick={depot.choisirVideos}><I.FileVideo size={15} />Choisir des vidéos</button>
		<button className="sr-btn" disabled={!!depot.progress} onClick={depot.choisirDossier}><I.Folder size={15} />Choisir un dossier</button>
		<label className="sr-charte" title="Charte du client (logo, couleurs) appliquée à ces vidéos">
			<span>Charte client</span>
			<select value={depot.client} onChange={(e) => depot.setClient(e.target.value)}>
				<option value="">Sans charte client</option>
				{depot.clients.map((c) => <option key={c.client} value={c.client}>{c.name}</option>)}
			</select>
			<I.ChevronDown size={15} />
		</label>
		<p className="sr-aide">Une vidéo = une vidéo à monter ; un dossier = plusieurs prises d'une même vidéo, avec son script. L'outil trouve le sujet et monte tout seul.</p>
		{depot.progress ? (
			<div className="sr-envoi">
				<span>Envoi {depot.progress.done}/{depot.progress.total}{depot.progress.skipped ? ` (${depot.progress.skipped} fichier(s) ignoré(s))` : ''}</span>
				<div className="sr-barre"><div style={{width: `${(100 * depot.progress.done) / depot.progress.total}%`}} /></div>
			</div>
		) : null}
		{depot.err ? <p className="sr-err">{depot.err}</p> : null}
	</div>
);

/** « Style depuis une video » : on depose un reel deja monte ; l'outil en mesure le style et le cree. */
const ReferenceCard: React.FC<{onCreated: (id: string) => void}> = ({onCreated}) => {
	const input = useRef<HTMLInputElement>(null);
	const [sending, setSending] = useState(false);
	const [err, setErr] = useState('');
	const [job, setJob] = useJob((j) => onCreated(j.result.id));
	const pick = async (file?: File) => {
		if (!file) return;
		setErr('');
		setSending(true);
		try {
			const r = await fetch(`/api/references/${encodeURIComponent(file.name)}`, {method: 'PUT', body: file});
			const d = await r.json();
			if (!r.ok) throw new Error(d.error || `Erreur ${r.status}`);
			setJob(await api('/api/references/analyser', 'POST', {fichier: d.fichier}));
		} catch (e) {
			setErr((e as Error).message);
		} finally {
			setSending(false);
		}
	};
	const busy = sending || job?.status === 'running' || job?.status === 'queued';
	// la carte accepte aussi une video glissee (« Dépose un reel modèle ») ; elle ne part jamais au montage automatique
	const [survol, setSurvol] = useState(false);
	const glisse = (e: React.DragEvent) => {
		if (!e.dataTransfer.types.includes('Files')) return;
		e.preventDefault();
		e.stopPropagation();
		e.dataTransfer.dropEffect = busy ? 'none' : 'copy';
		setSurvol(!busy);
	};
	const lache = (e: React.DragEvent) => {
		if (!e.dataTransfer.types.includes('Files')) return;
		e.preventDefault();
		e.stopPropagation();
		setSurvol(false);
		if (busy) return;
		const file = [...e.dataTransfer.files].find((f) => f.type.startsWith('video/') || /\.(mp4|mov|m4v|mkv|webm|avi)$/i.test(f.name));
		if (!file) return setErr('Dépose une vidéo (mp4, mov, mkv, webm…) : le reel dont tu veux copier le style.');
		pick(file);
	};
	return (
		<div className={`sr-style${survol ? ' survol' : ''}`} onDragOver={glisse} onDragLeave={() => setSurvol(false)} onDrop={lache}>
			<button className="sr-style-ref" disabled={busy} onClick={() => input.current?.click()}
				title="Dépose un reel déjà monté que tu aimes : l'outil crée le même style (rythme, sous-titres, zooms, musique, couleurs) et l'applique.">
				<span className="sr-style-ref-ic">{busy ? <I.Loader size={18} className="tourne" /> : <I.Plus size={18} />}</span>
				<b>Style depuis une vidéo</b>
				<span>{busy ? (sending ? 'Envoi de la vidéo…' : 'Mesure du style : 1 à 3 min…') : 'Dépose un reel modèle'}</span>
				{job?.status === 'failed' ? <span className="sr-err">{job.error}</span> : null}
				{err ? <span className="sr-err">{err}</span> : null}
			</button>
			<input ref={input} type="file" accept="video/*" hidden onChange={(e) => { pick(e.currentTarget.files?.[0]); e.currentTarget.value = ''; }} />
		</div>
	);
};

/** Corbeille de la Revision : les videos supprimees, avec un vrai bouton « Restaurer » (rien n'est jamais efface pour de bon). */
const TrashPanel: React.FC<{count: number; folder?: string; busy: boolean; onClose: () => void; onRestored: (r: Restored) => void; onError: (e: string) => void}> = ({count, folder,
	busy, onClose, onRestored, onError}) => {
	const [entries, setEntries] = useState<TrashEntry[] | null>(null);
	const [working, setWorking] = useState('');
	const load = useCallback(() => api('/api/revision/corbeille').then((d: {entrees: TrashEntry[]}) => setEntries(d.entrees)).catch((e) => onError((e as Error).message)), [onError]);
	// liste relue a l'ouverture et quand le nombre change (suppression, restauration, dossier deplace a la main)
	useEffect(() => {
		load();
	}, [count, load]);
	const restore = async (e: TrashEntry) => {
		if (!window.confirm(`Restaurer « ${e.titre} » ?\n\n${e.deplacements.map((d) => `• ${winPath(d.avant)} revient à sa place`).join('\n')}\n\nSon montage sera conservé s'il est présent. S'il manque, la vidéo sera remontée.`)) return;
		setWorking(e.dossier);
		onError('');
		try {
			const d: State & {restaure: Restored} = await api('/api/revision/corbeille/restaurer', 'POST', {dossier: e.dossier});
			onRestored(d.restaure);
			load();
		} catch (err) {
			onError((err as Error).message);
			load();
		} finally {
			setWorking('');
		}
	};
	return (
		<div className="sr-corbeille" role="dialog" aria-label="Corbeille">
			<div className="sr-corbeille-tete">
				<I.Trash size={16} />
				<b>Corbeille</b>
				<span className="grow" />
				{folder ? <button className="sr-btn petit" onClick={() => api('/api/open-folder', 'POST', {file: folder}).catch((e) => onError((e as Error).message))}>
					<I.FolderOpen size={14} />Ouvrir le dossier</button> : null}
				<button className="sr-icone" onClick={onClose} aria-label="Fermer la corbeille"><I.X size={15} /></button>
			</div>
			<div className="sr-corbeille-liste">
				{entries === null ? <p className="sr-muet">Lecture de la corbeille…</p> : null}
				{entries && !entries.length ? <p className="sr-muet">La corbeille est vide. Rien n'est jamais effacé pour de bon : une vidéo supprimée apparaît ici.</p> : null}
				{(entries ?? []).map((e) => (
					<div key={e.dossier} className="sr-corbeille-item">
						<div>
							<b>{e.titre}</b>
							<span className="sr-muet" title={`${e.dossier}${e.deplacements.length ? `\n${e.deplacements.map((d) => winPath(d.avant)).join('\n')}` : ''}`}>
								{e.supprime && dateFr(e.supprime) ? `Supprimée ${dateCourte(e.supprime)}` : e.dossier}</span>
							{!e.restaurable ? <span className="sr-err">{e.raison || 'Pas restaurable pour l\'instant.'}</span> : null}
						</div>
						<button className="sr-btn petit" disabled={!e.restaurable || busy || !!working} onClick={() => restore(e)}
							title={e.restaurable ? 'Remettre le montage et les vidéos brutes à leur place, et la vidéo dans la liste' : e.raison}>
							<I.RotateCcw size={14} />{working === e.dossier ? 'Restauration…' : 'Restaurer'}</button>
					</div>
				))}
			</div>
			<p className="sr-muet sr-corbeille-pied">Montage et vidéos brutes sont rangés dans la corbeille de l'éditeur ; les vidéos exportées restent dans « livraisons ».</p>
		</div>
	);
};

const GRAVITE: Record<Constat['gravite'], string> = {bloquant: 'Bloquant', important: 'Important', conseil: 'Conseil'};
const GRAVITE_ICONE: Record<Constat['gravite'], React.ReactNode> = {bloquant: <I.OctagonAlert size={13} />, important: <I.TriangleAlert size={13} />,
	conseil: <I.Lightbulb size={13} />};
const virgule = (n: number) => String(Math.round(n * 10) / 10).replace('.', ',');
/** Moment d'un probleme a la francaise : 0:28,5 (0:26 quand il tombe pile sur la seconde). */
const tcv = (t: number) => fmt(t).replace(/\.0$/, '').replace('.', ',');
const noteClasse = (c: Pick<Controle, 'note' | 'compte'>) => (c.compte.bloquant ? 'mauvais' : c.note >= 8 ? 'bon' : c.note >= 6 ? 'moyen' : 'mauvais');
/** « 2 bloquants · 3 importants · 1 conseil » (les zeros sont omis). */
const compteTexte = (c: Controle['compte']) => {
	const parts = (['bloquant', 'important', 'conseil'] as const).filter((g) => c[g]).map((g) => `${c[g]} ${g}${c[g] > 1 ? 's' : ''}`);
	return parts.length ? parts.join(' · ') : 'aucun problème';
};
/** « 2026-10-02 09:41 » -> « aujourd'hui 09:41 » / « le 01/10 09:41 » (date du controle, courte). */
const quand = (date: string) => {
	const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})/.exec(date || '');
	if (!m) return date;
	const n = new Date();
	const jour = +m[1] === n.getFullYear() && +m[2] === n.getMonth() + 1 && +m[3] === n.getDate();
	return jour ? `aujourd'hui ${m[4]}` : `le ${m[3]}/${m[2]} ${m[4]}`;
};
/** Une source de rapport affichee dans le panneau : le montage (reel.controle) ou une video livree (export). */
type Rapport = {cle: string; titre: string; controle?: ControleExport | null; etat?: 'queued' | 'running' | null; video?: string};

/** Controle qualite dans la Revision : note /10, verdict, problemes (gravite, moment cliquable = aller a l'image, suggestion). */
const ControlePanel: React.FC<{rapports: Rapport[]; choisi: string; onChoisir: (cle: string) => void; reel: ReelDoc; relance: boolean; relanceErreur: string;
	busy: boolean; onRelancer: () => void; onVoir: (t: number, zone: Constat['zone'] | null) => void; avis?: Avis | null}> = ({rapports, choisi, onChoisir, reel, relance,
	relanceErreur, busy, onRelancer, onVoir, avis: avisTache}) => {
	const r = rapports.find((x) => x.cle === choisi) ?? rapports[0];
	const c = r && aNote(r.controle) ? r.controle : null;
	// avis de Claude range dans CE rapport (critique de la video livree : section « claude » du controle), sinon celui de la
	// tache qui vient de finir ou du reel
	const claudeRapport = c ? ((c as Controle & {claude?: {ok?: boolean; message?: string}}).claude ?? null) : null;
	const avis = avisDe(claudeRapport) ?? avisTache;
	// avis demande mais pas obtenu (plafond, credit, erreur) : on dit pourquoi au lieu de ne rien montrer
	const avisNon = !avis && claudeRapport?.ok === false && claudeRapport.message ? String(claudeRapport.message) : '';
	// une boite n'est dessinee que si le rapport est au format du lecteur (un export 16:9 n'a pas les memes px qu'un 9:16)
	const memeFormat = !c?.format || c.format === `${reel.width}x${reel.height}`;
	const erreur = r && !c && !r.etat && r.controle && 'erreur' in r.controle ? r.controle.erreur : '';
	const attente = r?.etat ? (r.etat === 'running' ? 'Contrôle de la vidéo livrée en cours (images, détourage, son) : environ 1 minute…' : 'Contrôle de la vidéo livrée en attente…') : '';
	const vide = !c && !attente && !erreur ? (r?.cle === 'montage' ? 'Pas encore de contrôle pour ce montage : clique « Relancer le contrôle ».' : 'Pas encore de contrôle pour cette vidéo.') : '';
	return (
		<section className="sr-qc" aria-label="Contrôle qualité">
			<div className="sr-qc-tete">
				<div className={`sr-qc-note ${c ? noteClasse(c) : 'vide'}`}>
					<span>{c ? virgule(c.note) : '–'}</span><small>/ 10</small>
				</div>
				<div className="sr-qc-verdict">
					<div className="sr-qc-label">Contrôle qualité</div>
					<div className="sr-qc-texte">{c ? c.verdict : attente || (erreur ? `Contrôle impossible : ${erreur}` : vide)}</div>
					{c ? <div className="sr-qc-detail" title={`Contrôlé le ${c.date}${r.cle === 'montage' ? ' : montage, sans rendu' : ' : vidéo livrée (images, détourage, son)'}`}>
						{compteTexte(c.compte)} · {quand(c.date)}</div> : null}
				</div>
				<button className="sr-btn" disabled={busy || relance} onClick={onRelancer}
					title="Relit le montage actuel (quelques secondes, sans rendu) : à refaire après des retouches">
					<I.RefreshCw size={14} className={relance ? 'tourne' : ''} />{relance ? 'Contrôle en cours…' : 'Relancer le contrôle'}</button>
			</div>
			{rapports.length > 1 ? (
				<div className="sr-qc-onglets" role="tablist" aria-label="Rapport affiché">
					{rapports.map((x) => (
						<button key={x.cle} role="tab" aria-selected={x.cle === r?.cle} className={x.cle === r?.cle ? 'on' : ''} onClick={() => onChoisir(x.cle)}
							title={x.video ? `Vidéo contrôlée : ${x.video}` : 'Contrôle du montage (sans rendu)'}>
							{x.titre}{aNote(x.controle) ? ` · ${virgule(x.controle.note)}/10` : x.etat ? ' · en cours…' : ''}
						</button>
					))}
				</div>
			) : null}
			{relanceErreur ? <p className="sr-err sr-qc-msgerr">Contrôle qualité impossible : {relanceErreur}</p> : null}
			{c && c.constats.length ? (
				<ul className="sr-qc-liste">
					{c.constats.map((k, n) => (
						<li key={`${k.code}-${n}`} className={`sr-qc-ligne ${k.gravite}`}>
							<span className={`sr-grav ${k.gravite}`}>{GRAVITE_ICONE[k.gravite]}{GRAVITE[k.gravite]}</span>
							{k.temps !== null && k.temps !== undefined ? (
								<button className="sr-tc" onClick={() => onVoir(k.temps as number, memeFormat ? k.zone ?? null : null)}
									title={memeFormat && k.zone ? 'Aller à ce moment et montrer l\'endroit' : 'Aller à ce moment'}>
									<I.Play size={11} />{tcv(k.temps)}{k.fin !== null && k.fin !== undefined && k.fin - k.temps > 0.15 ? `–${tcv(k.fin)}` : ''}
								</button>
							) : <span className="sr-tc vide">toute la vidéo</span>}
							<div className="sr-qc-msg"><b>{k.message}</b> <span>→ {k.suggestion}</span></div>
						</li>
					))}
				</ul>
			) : null}
			{c && !c.constats.length ? <p className="sr-qc-ok"><I.CircleCheck size={15} />Aucun problème détecté.</p> : null}
			{c && (c.total ?? 0) > c.constats.length ? <p className="sr-muet sr-qc-plus" title="Rapport complet : dossier runtime\cache\controle de l'éditeur">
				+ {(c.total ?? 0) - c.constats.length} point(s) moins grave(s) dans le rapport complet.</p> : null}
			{avis ? (
				// relecture des images par Claude (bouton « 👁 Critique Claude ») : un avis de plus, a cote du controle automatique
				<div className="cl-avis" aria-label="Avis de Claude">
					<div className="cl-avis-tete">
						<span className="cl-avis-titre">👁 Avis de Claude</span>
						{avis.note !== null ? <b className={`cl-avis-note ${avis.note >= 8 ? 'bon' : avis.note >= 6 ? 'moyen' : 'mauvais'}`}>{virgule(avis.note)}/10</b> : null}
						<span className="grow" />
						{avis.date || avis.cout !== null ? <small>{[avis.date ? quand(avis.date) : '', avis.cout !== null ? argent(avis.cout) : '', nomModele(avis.modele)].filter(Boolean).join(' · ')}</small> : null}
					</div>
					{avis.verdict ? <p className="cl-avis-verdict">{avis.verdict}</p> : null}
					{avis.problemes.length ? (
						<ul className="sr-qc-liste">
							{avis.problemes.map((k, n) => (
								<li key={n} className={`sr-qc-ligne ${k.gravite}`}>
									{k.gravite in GRAVITE ? <span className={`sr-grav ${k.gravite}`}>{GRAVITE_ICONE[k.gravite as Constat['gravite']]}{GRAVITE[k.gravite as Constat['gravite']]}</span> : null}
									{k.t !== null ? (
										<button className="sr-tc" onClick={() => onVoir(k.t as number, null)} title="Aller à ce moment">
											<I.Play size={11} />{tcv(k.t)}{k.fin !== null && k.fin - k.t > 0.15 ? `–${tcv(k.fin)}` : ''}
										</button>
									) : <span className="sr-tc vide">toute la vidéo</span>}
									<div className="sr-qc-msg"><b>{k.texte}</b>{k.suggestion ? <span> → {k.suggestion}</span> : null}</div>
								</li>
							))}
						</ul>
					) : <p className="sr-qc-ok"><I.CircleCheck size={15} />Claude ne voit pas de problème dans les images.</p>}
				</div>
			) : avisNon ? <p className="sr-muet cl-avis-non">{avisNon}</p> : null}
		</section>
	);
};

/** Vignette d'une carte : premiere image du montage, sinon un fond de couleur (video pas encore montee). */
const Vignette: React.FC<{reel?: ReelDoc; id: string}> = ({reel, id}) => {
	const c = reel?.clips[0];
	const src = c && reel?.sources[c.source];
	return (
		<div className="sr-vignette" style={src ? undefined : {background: fondDe(id)}}>
			{src ? <img src={`/api/thumb?proxy=${encodeURIComponent(src.proxy)}&t=${(c.in + 1).toFixed(1)}`} alt="" loading="lazy" /> : <><i /><i /></>}
		</div>
	);
};

/** Etat d'une video dans la liste : texte, couleur (classe), avancement. */
const etatDe = (i: Item): {label: string; cls: string; pct?: number} => {
	const ex = i.exports ?? [];
	if (ex.some(running)) {
		const p = pctExports(ex);
		return {label: `Export en cours ${p} %`, cls: 'export', pct: p};
	}
	if (i.status === 'attente') return {label: 'En file', cls: 'file'};
	if (i.status === 'travail') {
		const p = Math.round(100 * (i.progress || 0));
		return {label: `En montage ${p} %`, cls: 'montage', pct: p};
	}
	if (i.status === 'pret') return {label: 'Prête à regarder', cls: 'prete'};
	if (i.status === 'pris') return {label: 'Prise', cls: 'prise'};
	return {label: 'Erreur', cls: 'erreur'};
};

/** Barre de lecture sous l'apercu (lecture, temps, position cliquable, son, plein ecran) : suit le lecteur image par image
 * sans faire redessiner le reste de la page. */
const Transport: React.FC<{player: React.RefObject<PlayerRef | null>; fps: number; frames: number}> = ({player, fps, frames}) => {
	const [frame, setFrame] = useState(0);
	const [playing, setPlaying] = useState(false);
	const [muted, setMuted] = useState(false);
	const drag = useRef(false);
	useEffect(() => {
		const p = player.current;
		if (!p) return;
		const onFrame = (e: {detail: {frame: number}}) => setFrame(e.detail.frame);
		const onPlay = () => setPlaying(true);
		const onPause = () => setPlaying(false);
		const onMute = (e: {detail: {isMuted: boolean}}) => setMuted(e.detail.isMuted);
		p.addEventListener('frameupdate', onFrame);
		p.addEventListener('play', onPlay);
		p.addEventListener('pause', onPause);
		p.addEventListener('ended', onPause);
		p.addEventListener('mutechange', onMute);
		setPlaying(p.isPlaying());
		setMuted(p.isMuted());
		setFrame(p.getCurrentFrame());
		return () => {
			p.removeEventListener('frameupdate', onFrame);
			p.removeEventListener('play', onPlay);
			p.removeEventListener('pause', onPause);
			p.removeEventListener('ended', onPause);
			p.removeEventListener('mutechange', onMute);
		};
	}, [player]);
	const last = Math.max(1, frames - 1);
	const seek = (f: number) => player.current?.seekTo(Math.max(0, Math.min(last, Math.round(f))));
	const at = (e: React.PointerEvent<HTMLDivElement>) => {
		const r = e.currentTarget.getBoundingClientRect();
		seek(((e.clientX - r.left) / Math.max(1, r.width)) * last);
	};
	const pct = `${Math.min(100, (100 * frame) / last)}%`;
	return (
		<div className="sr-transport">
			<button className="sr-tr-btn plein" onClick={(e) => player.current?.toggle(e)} title="Lecture / pause (Espace)" aria-label={playing ? 'Pause' : 'Lecture'}>
				{playing ? <I.Pause size={16} /> : <I.Play size={16} />}</button>
			<span className="sr-tr-t">{mmss(frame / fps)}</span>
			<div className="sr-tr-piste" role="slider" tabIndex={0} aria-label="Position dans la vidéo" aria-valuemin={0} aria-valuemax={Math.round(frames / fps)}
				aria-valuenow={Math.round(frame / fps)} aria-valuetext={mmss(frame / fps)}
				onPointerDown={(e) => { drag.current = true; e.currentTarget.setPointerCapture(e.pointerId); at(e); }}
				onPointerMove={(e) => drag.current && at(e)}
				onPointerUp={() => { drag.current = false; }}
				// glisser interrompu (fenetre quittee, geste annule) : survoler ensuite la piste ne doit plus deplacer la lecture
				onLostPointerCapture={() => { drag.current = false; }}
				onKeyDown={(e) => {
					if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
					e.preventDefault();
					e.stopPropagation(); // la fleche droite seule passe a la video suivante : ici elle avance d'une seconde
					seek(frame + (e.key === 'ArrowLeft' ? -1 : 1) * fps);
				}}>
				<div className="sr-tr-plein" style={{width: pct}} />
				<div className="sr-tr-tete" style={{left: pct}} />
			</div>
			<span className="sr-tr-d">{mmss(frames / fps)}</span>
			<button className="sr-tr-btn" onClick={() => (muted ? player.current?.unmute() : player.current?.mute())} title={muted ? 'Remettre le son' : 'Couper le son'}
				aria-label={muted ? 'Remettre le son' : 'Couper le son'}>{muted ? <I.VolumeX size={16} /> : <I.Volume size={16} />}</button>
			<button className="sr-tr-btn" onClick={() => player.current?.requestFullscreen()} title="Plein écran" aria-label="Plein écran"><I.Maximize size={15} /></button>
		</div>
	);
};

/** Gros bouton de lecture au centre de l'apercu, visible a l'arret (le clic passe au lecteur : clic = lecture / pause). */
const PlayOverlay: React.FC<{player: React.RefObject<PlayerRef | null>}> = ({player}) => {
	const [playing, setPlaying] = useState(true);
	useEffect(() => {
		const p = player.current;
		if (!p) return;
		const on = () => setPlaying(true);
		const off = () => setPlaying(false);
		p.addEventListener('play', on);
		p.addEventListener('pause', off);
		p.addEventListener('ended', off);
		setPlaying(p.isPlaying());
		return () => {
			p.removeEventListener('play', on);
			p.removeEventListener('pause', off);
			p.removeEventListener('ended', off);
		};
	}, [player]);
	return <div className={`sr-lecture${playing ? '' : ' visible'}`} aria-hidden><I.Play size={26} /></div>;
};

/** Etapes du montage automatique (textes envoyes par engine/editeur/auto.py : « Écoute et analyse des prises »…). */
const ETAPES: {label: string; re: RegExp; min: number}[] = [
	{label: 'Lecture des prises', re: /démarrage|attente/i, min: 0},
	{label: 'Écoute et analyse des prises', re: /écoute|analyse|transcri/i, min: 0.03},
	{label: 'Compréhension du sujet', re: /compréhension|sujet/i, min: 0.3},
	{label: 'Montage et sous-titres', re: /montage/i, min: 0.45},
	{label: 'Contrôle qualité', re: /contrôle/i, min: 0.97},
];
const etapeDe = (i: Item) => {
	const byText = ETAPES.map((e, k) => (e.re.test(i.stage || '') ? k : -1)).reduce((a, b) => Math.max(a, b), -1);
	const byProgress = ETAPES.reduce((a, e, k) => ((i.progress || 0) >= e.min ? k : a), 0);
	return byText >= 0 ? Math.max(byText, i.status === 'attente' ? 0 : byProgress) : byProgress;
};

type Types = Record<string, {label: string; style?: string; description?: string}>;
/** « Autre style » : galerie par-dessus la colonne de droite. On choisit une carte, puis « Appliquer ce style » (double-clic = appliquer). */
const Galerie: React.FC<{templates: Template[]; current?: string; item: Item; reel: ReelDoc; reelKey: string; busy: boolean; types: Types | null;
	onApply: (t: Pick<Template, 'id' | 'name'>) => Promise<boolean>; onRetour: () => void; onPin: () => void; onClose: () => void; onTemplates: () => Promise<unknown>;
	onSaved: (t: Template) => unknown}> = ({templates, current, item, reel, reelKey, busy, types, onApply, onRetour, onPin, onClose, onTemplates, onSaved}) => {
	const [categorie, setCategorie] = useState('Tous');
	const [choisi, setChoisi] = useState('');
	const [working, setWorking] = useState(false);
	const [msg, setMsg] = useState('');
	const [err, setErr] = useState('');
	const categories = ['Tous', ...new Set(templates.map((t) => t.category || 'Classiques'))];
	const shown = templates.filter((t) => categorie === 'Tous' || (t.category || 'Classiques') === categorie);
	const tChoisi = templates.find((t) => t.id === choisi);
	const run = async (fn: () => Promise<string>) => {
		setWorking(true);
		setErr('');
		setMsg('');
		try {
			setMsg(await fn());
			await onTemplates();
		} catch (e) {
			setErr((e as Error).message);
		} finally {
			setWorking(false);
		}
	};
	const rename = (t: Template) => {
		const name = window.prompt(`Nouveau nom pour ton style « ${t.name} » :`, t.name);
		if (!name || !name.trim() || name.trim() === t.name) return;
		run(async () => {
			const r: Template = await api(`/api/styles/${encodeURIComponent(t.id)}/renommer`, 'POST', {name});
			return `Style renommé : « ${r.name} ».`;
		});
	};
	const remove = (t: Template) => {
		if (!window.confirm(`Supprimer ton style « ${t.name} » ?\n\nIl sera rangé dans la corbeille (dossier styles\\montage\\_corbeille) : on peut le récupérer.\n`
			+ 'Les vidéos déjà montées avec ce style gardent leur apparence.')) return;
		if (choisi === t.id) setChoisi('');
		run(async () => {
			const r: {name: string; sujets: {sujet: string; styleName: string}[]} = await api(`/api/styles/${encodeURIComponent(t.id)}`, 'DELETE');
			return `Style « ${r.name} » mis à la corbeille.${r.sujets.map((s) => ` Les prochaines vidéos « ${s.sujet} » seront montées en « ${s.styleName} ».`).join('')}`;
		});
	};
	const appliquer = async (t?: Template) => {
		if (!t || t.id === current || busy || working) return;
		if (await onApply(t)) onClose();
	};
	const pinned = !!item.type && !!types && types[item.type]?.style === reel.template;
	const nomActuel = templates.find((t) => t.id === reel.template)?.name ?? reel.template ?? 'aucun';
	return (
		<div className="sr-galerie" role="dialog" aria-label="Autre style">
			<div className="sr-gal-tete">
				<I.Palette size={19} className="violet" />
				<h3>Autre style</h3>
				<span className="sr-muet">Actuel : {nomActuel}</span>
				<span className="grow" />
				<button className="sr-btn" disabled={busy || !item.previousStyleVersion} onClick={onRetour}
					title={item.previousStyleVersion ? 'Remettre le montage tel qu\'il était avant le dernier changement de style' : 'Aucun changement de style à annuler'}>
					<I.Undo size={14} />Revenir au style précédent</button>
				<button className="sr-icone" onClick={onClose} aria-label="Fermer la galerie (Échap)" title="Fermer (Échap)"><I.X size={16} /></button>
			</div>
			<div className="sr-gal-filtres" aria-label="Catégories de styles">
				{categories.map((c) => <button key={c} className={c === categorie ? 'on' : ''} aria-pressed={c === categorie} onClick={() => setCategorie(c)}>{c}</button>)}
			</div>
			<div className="sr-gal-grille">
				<ReferenceCard onCreated={async (id) => {
					await onTemplates();
					if (await onApply({id, name: 'nouveau style'})) onClose();
				}} />
				{shown.map((t) => (
					<div key={t.id} className={`sr-style${choisi === t.id ? ' choisi' : ''}${current === t.id ? ' actuel' : ''}`}>
						<button className="sr-style-image" disabled={working} onClick={() => setChoisi(choisi === t.id ? '' : t.id)} onDoubleClick={() => appliquer(t)}
							aria-pressed={choisi === t.id} title={`${t.description}${current === t.id ? '' : '\n(double-clic : appliquer tout de suite)'}`}>
							{t.preview ? <img src={`/assets/${t.preview}`} alt={`Aperçu du style ${t.name}`} loading="lazy" /> : <span className="sr-style-fond" style={{background: fondDe(t.id, FONDS_STYLE)}}>{t.name}</span>}
							{t.perso ? <span className="sr-badge perso">mon style</span> : null}
							{current === t.id ? <span className="sr-badge actuel"><I.Check size={12} />Actuel</span> : null}
						</button>
						<div className="sr-style-nom">{t.name}</div>
						{t.perso ? (
							<div className="sr-style-outils">
								<button disabled={working} onClick={() => rename(t)}>Renommer</button>
								<button className="suppr" disabled={working} onClick={() => remove(t)}>Supprimer</button>
							</div>
						) : null}
					</div>
				))}
			</div>
			{msg || err || (reel.design?.mode === 'produit' && !reel.design.productVideo) ? (
				<div className="sr-gal-msgs">
					{msg ? <p className="sr-ok">{msg}</p> : null}
					{err ? <p className="sr-err">{err}</p> : null}
					{reel.design?.mode === 'produit' && !reel.design.productVideo ? <p className="sr-muet">Pour animer ton produit : « Modifier » → « Style » → « Habillage du style », choisis sa photo ou son modèle GLB, puis « Créer l’animation 3D ».</p> : null}
				</div>
			) : null}
			<div className="sr-gal-pied">
				<SaveStyleCard className="sr-gal-save" reel={reel} reelKey={reelKey} templates={templates} onSaved={onSaved} />
				<span className="sr-gal-pied-ligne" />
				{item.type ? (
					<button className={`sr-btn pin${pinned ? ' on' : ''}`} disabled={busy || !reel.template} onClick={onPin}
						title={`Les prochaines vidéos « ${item.typeLabel ?? item.type} » seront montées en « ${nomActuel} » (le style actuel de cette vidéo)`}>
						<I.Pin size={14} className="violet" />Toujours ce style pour « {item.typeLabel ?? item.type} »{pinned ? ' ✓' : ''}</button>
				) : null}
				<span className="grow" />
				<button className="sr-btn appliquer" disabled={!tChoisi || tChoisi.id === current || busy || working} onClick={() => appliquer(tChoisi)}
					title={tChoisi ? (tChoisi.id === current ? 'C\'est déjà le style de cette vidéo' : `Remonter la vidéo en « ${tChoisi.name} »`) : 'Choisis d\'abord un style'}>
					{busy ? 'Application…' : 'Appliquer ce style'}</button>
			</div>
		</div>
	);
};

/** Barre du haut (Revision et Editeur) : logo, onglets, compteurs du jour, reglages, initiales. */
export const TopBar: React.FC<{vue: 'revision' | 'edition'; onVue: (v: 'revision' | 'edition') => void; compte?: RevisionCompte | null; children?: React.ReactNode}> = ({vue,
	onVue, compte, children}) => (
	<header className="sa-top">
		<div className="sa-marque">
			<div className="sa-logo" aria-hidden>S</div>
			<b>Éditeur Sami</b>
		</div>
		<nav className="sa-onglets" aria-label="Écrans">
			<button className={vue === 'revision' ? 'on' : ''} aria-current={vue === 'revision' ? 'page' : undefined} onClick={() => onVue('revision')}
				title="Les vidéos déposées : regarder, prendre, changer de style">Révision</button>
			<button className={vue === 'edition' ? 'on' : ''} aria-current={vue === 'edition' ? 'page' : undefined} onClick={() => onVue('edition')}
				title="L'éditeur complet (texte, style, plans, timeline)">Éditeur<span className="sa-cache"> complet</span></button>
		</nav>
		<div className="sa-top-outils">{children}</div>
		{compte && vue === 'revision' ? (
			<div className="sa-compteurs">
				<span title={`Vidéos déposées aujourd'hui (${compte.total} dans la liste en tout)`}>Aujourd'hui · <b>{compte.jour} vidéo{compte.jour > 1 ? 's' : ''}</b></span>
				<span title="Vidéos montées, prêtes à regarder"><i className="pastille vert" />{compte.pretes} prête{compte.pretes > 1 ? 's' : ''}</span>
				<span title="Vidéos prises (exportées) aujourd'hui"><i className="pastille cyan" />{compte.prises} prise{compte.prises > 1 ? 's' : ''}</span>
			</div>
		) : null}
		<Reglages compte={compte} />
		<div className="sa-avatar" title="Sami">SA</div>
	</header>
);

const RACCOURCIS: [string, string][] = [['Entrée', 'Je la prends'], ['E', 'Modifier'], ['S', 'Autre style'], ['→', 'Vidéo suivante'], ['Espace', 'Lecture / pause'],
	['Échap', 'Fermer la galerie']];
/** Petit panneau des reglages : raccourcis clavier et dossiers de l'editeur. */
const Reglages: React.FC<{compte?: RevisionCompte | null}> = ({compte}) => {
	const [open, setOpen] = useState(false);
	const [err, setErr] = useState('');
	const box = useRef<HTMLDivElement>(null);
	useEffect(() => {
		if (!open) return;
		const out = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
		const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
		window.addEventListener('mousedown', out);
		window.addEventListener('keydown', esc);
		return () => {
			window.removeEventListener('mousedown', out);
			window.removeEventListener('keydown', esc);
		};
	}, [open]);
	const ouvrir = (file?: string) => file && api('/api/open-folder', 'POST', {file}).then(() => setErr('')).catch((e) => setErr((e as Error).message));
	// pastille rouge sur la roue : credit Anthropic epuise ou espace de travail manquant (Claude repasse en local)
	const {statut} = useClaude();
	const alerte = !!statut?.actif && (!!statut.credit_epuise || !!statut.espace_manquant);
	return (
		<div className="sa-reglages" ref={box}>
			<button className={`sa-rond${open ? ' on' : ''}`} onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Paramètres"
				title={alerte ? `Claude : ${statut?.raison || statut?.avertissement}` : 'Raccourcis clavier, dossiers et Claude (IA en ligne)'}>
				<I.Settings size={17} />{alerte ? <i className="cl-point" aria-hidden /> : null}</button>
			{open ? (
				<div className="sa-pop cl-pop" role="dialog" aria-label="Paramètres">
					<div className="sa-pop-titre"><I.Keyboard size={15} />Raccourcis de la Révision</div>
					<ul className="sa-raccourcis">{RACCOURCIS.map(([k, t]) => <li key={k}><kbd>{k}</kbd><span>{t}</span></li>)}</ul>
					<div className="sa-pop-titre"><I.Folder size={15} />Dossiers</div>
					<button className="sr-btn" disabled={!compte?.entree} onClick={() => ouvrir(compte?.entree)}><I.FolderOpen size={14} />Dossier Entrée (vidéos brutes)</button>
					<button className="sr-btn" disabled={!compte?.corbeille} onClick={() => ouvrir(compte?.corbeille)}><I.Trash size={14} />Corbeille de l'éditeur</button>
					{err ? <p className="sr-err">{err}</p> : null}
					<ClaudeReglages />
				</div>
			) : null}
		</div>
	);
};

/** Section « Claude (IA en ligne) » des reglages ⚙️ : allumer / eteindre, modele, plafonds, credit, couts. Chaque changement est
 * enregistre tout de suite (styles/claude.json, par le moteur). Jamais la cle : seulement « Clé présente ✓ ». */
const ClaudeReglages: React.FC = () => {
	const {statut: s, absent} = useClaude();
	const [err, setErr] = useState('');
	const [ok, setOk] = useState('');
	const [working, setWorking] = useState(false);
	const [avance, setAvance] = useState(false);
	const [plafonds, setPlafonds] = useState<{video: string; jour: string; mois: string} | null>(null);
	const [credit, setCredit] = useState('');
	const [espace, setEspace] = useState('');
	const [couts, setCouts] = useState<ClaudeCouts | null>(null);
	const [voirCouts, setVoirCouts] = useState(false);
	useEffect(() => {
		relireClaude(true);
	}, []);
	useEffect(() => {
		const fr = (v: number) => String(v).replace('.', ',');
		if (avance && s?.plafonds && !plafonds) setPlafonds({video: fr(s.plafonds.video), jour: fr(s.plafonds.jour), mois: fr(s.plafonds.mois)});
	}, [avance, s, plafonds]);
	useEffect(() => {
		if (!voirCouts) return;
		api('/api/claude/couts?jours=7').then(setCouts).catch((e) => setErr((e as Error).message));
	}, [voirCouts, s?.depense_jour, s?.appels_jour]);
	const enregistrer = async (patch: Record<string, unknown>, message: string) => {
		setWorking(true);
		setErr('');
		setOk('');
		try {
			majClaude(await api('/api/claude/reglages', 'PUT', patch));
			setOk(message);
			return true;
		} catch (e) {
			setErr((e as Error).message);
			return false;
		} finally {
			setWorking(false);
		}
	};
	const nombre = (v: string) => Number(String(v).trim().replace(',', '.'));
	const titre = <div className="sa-pop-titre cl-titre"><I.Sparkles size={15} />Claude (IA en ligne)</div>;
	if (absent) return <>{titre}<p className="sr-flag">Claude n'est pas encore actif dans l'éditeur lancé : relance-le (« Editeur Sami.cmd »).</p></>;
	if (!s) return <>{titre}<p className="sr-muet">Lecture de l'état de Claude…</p></>;
	if (s.indisponible) return <>{titre}<p className="sr-flag">{s.raison}</p></>;
	const estimations = Object.keys(MODELES_CLAUDE).map((id) => ({id, e: s.modeles?.find((m) => m.id === id)?.estimation ?? (s.estimation?.modele === id ? s.estimation : undefined)}));
	const libelle = (id: string, e?: ClaudeEstimation) => {
		const m = MODELES_CLAUDE[id];
		const prix = e ? ` (≈ ${argent(e.par_video)}${id === 'claude-sonnet-5-5' ? ' / vidéo' : ''})` : '';
		return `${m.nom} — ${m.mot}${prix}`;
	};
	const alerte = s.actif && (s.credit_epuise || s.espace_manquant);
	const enregistrerPlafonds = () => {
		if (!plafonds) return;
		const p = {plafond_video: nombre(plafonds.video), plafond_jour: nombre(plafonds.jour), plafond_mois: nombre(plafonds.mois)};
		if (Object.values(p).some((v) => !Number.isFinite(v) || v < 0 || v > 1000)) return setErr('Plafonds : des montants en $ entre 0 et 1000 (par exemple 0,25).');
		enregistrer(p, 'Plafonds enregistrés.');
	};
	const recharger = () => {
		const v = nombre(credit);
		if (!credit.trim() || !Number.isFinite(v) || v < 0 || v > 1000) return setErr('Indique le crédit affiché sur platform.claude.com (Billing), en $ : par exemple 10.');
		// le credit affiche par Anthropic compte deja les depenses d'aujourd'hui : on les rajoute au depart (elles sont deduites ensuite)
		enregistrer({credit_depart: Math.min(1000, Math.round((v + (s.depense_jour ?? 0)) * 10000) / 10000), credit_date: aujourdhui()}, `Nouveau crédit noté : ${argent(v)}.`)
			.then((fait) => fait && setCredit(''));
	};
	return (
		<>
			{titre}
			<div className="cl-reglages">
				<div className="cl-ligne">
					<button className={`cl-inter${s.actif ? ' on' : ''}`} role="switch" aria-checked={s.actif} disabled={working}
						onClick={() => enregistrer({actif: !s.actif}, s.actif ? 'Claude éteint : tout se fait en local.' : 'Claude allumé.')}>
						<span className="cl-inter-rond" /></button>
					<b>Activer Claude</b>
					<span className="grow" />
					<span className={s.cle ? 'cl-cle ok' : 'cl-cle'}>{s.cle ? 'Clé présente ✓' : 'Aucune clé dans cles-api.env'}</span>
				</div>
				<p className="sr-muet cl-aide">Claude rend les idées, les textes et les relectures meilleurs que l'IA locale. Chaque appel coûte un peu de ton crédit Anthropic ;
					sans Claude, tout marche quand même en local.</p>
				{alerte ? <p className="cl-alerte"><I.TriangleAlert size={14} />{s.raison || s.avertissement}</p> : null}
				{!alerte && s.actif && !s.pret && s.raison ? <p className="sr-flag">{s.raison}</p> : null}
				{!alerte && s.avertissement ? <p className="sr-flag">{s.avertissement}</p> : null}
				<div className="cl-sous">Modèle</div>
				<div className="cl-modeles" role="radiogroup" aria-label="Modèle de Claude">
					{estimations.map(({id, e}) => (
						<label key={id} className={`cl-modele${s.modele === id ? ' on' : ''}`} title={s.modeles?.find((m) => m.id === id)?.conseil ?? ''}>
							<input type="radio" name="claude-modele" checked={s.modele === id} disabled={working}
								onChange={() => enregistrer({modele: id}, `Modèle : ${MODELES_CLAUDE[id].nom}.`)} />
							<span>{libelle(id, e)}</span>
						</label>
					))}
				</div>
				<div className="cl-chiffres">
					<span>Aujourd'hui : <b>{argent(s.depense_jour)}</b>{s.appels_jour ? ` (${s.appels_jour} appel${s.appels_jour > 1 ? 's' : ''})` : ''}</span>
					<span>Ce mois : <b>{argent(s.depense_mois)}</b></span>
				</div>
				<div className="cl-credit">
					<span>Crédit restant estimé : <b>{argent(s.credit_restant_estime)}</b></span>
					<span className="sr-muet" title="Calculé par l'éditeur d'après ses propres appels (les autres logiciels qui utilisent la même clé ne sont pas comptés)">
						depuis le {s.credit_date} (départ {argent(s.credit_depart)})</span>
				</div>
				<div className="cl-ligne cl-recharge">
					<label htmlFor="cl-credit">J'ai rechargé : nouveau crédit</label>
					<input id="cl-credit" type="text" inputMode="decimal" value={credit} placeholder="10" disabled={working} onChange={(e) => setCredit(e.target.value)}
						onKeyDown={(e) => e.key === 'Enter' && recharger()} />
					<span>$</span>
					<button className="sr-btn petit" disabled={working || !credit.trim()} onClick={recharger}>Enregistrer</button>
				</div>
				<label className="cl-coche">
					<input type="checkbox" checked={!!s.critique_auto} disabled={working}
						onChange={(e) => enregistrer({critique_auto: e.target.checked}, e.target.checked ? 'Chaque export sera relu par Claude.' : 'Critique automatique éteinte.')} />
					<span>Critique automatique après export<small>Éteinte par défaut : chaque relecture coûte{estimationClaude(s, 'critique') !== null ? ` environ ${argent(estimationClaude(s, 'critique'))}` : ' un peu'}.</small></span>
				</label>
				<button className="cl-lien" aria-expanded={avance} onClick={() => setAvance(!avance)}>{avance ? '▾' : '▸'} Avancé</button>
				{avance ? (
					<div className="cl-avance">
						<div className="cl-sous">Modèle par tâche</div>
						{(['cerveau', 'critique', 'consigne'] as const).map((t) => (
							<label key={t} className="cl-select">
								<span>{t === 'cerveau' ? 'Idées du montage (cerveau)' : t === 'critique' ? 'Relecture des images (critique)' : 'Demandes « Dis à l’IA » (consigne)'}</span>
								<select value={s.modeles_taches?.[t] ?? ''} disabled={working}
									onChange={(e) => enregistrer({modeles_taches: {[t]: e.target.value || null}}, 'Modèle de la tâche enregistré.')}>
									<option value="">Modèle général ({nomModele(s.modele)})</option>
									{Object.entries(MODELES_CLAUDE).map(([id, m]) => <option key={id} value={id}>{m.nom}</option>)}
								</select>
							</label>
						))}
						<div className="cl-sous">Plafonds de dépense</div>
						<div className="cl-plafonds">
							{(['video', 'jour', 'mois'] as const).map((k) => (
								<label key={k}>
									<span>{k === 'video' ? 'Par vidéo' : k === 'jour' ? 'Par jour' : 'Par mois'}</span>
									<input type="text" inputMode="decimal" value={plafonds?.[k] ?? ''} disabled={working || !plafonds}
										onChange={(e) => plafonds && setPlafonds({...plafonds, [k]: e.target.value})} />
									<span>$</span>
								</label>
							))}
						</div>
						<button className="sr-btn petit" disabled={working || !plafonds} onClick={enregistrerPlafonds}>Enregistrer les plafonds</button>
						<div className="cl-sous">Espace de travail Anthropic</div>
						<p className="sr-muet cl-aide">Seulement si Anthropic le demande (clé d'organisation) : platform.claude.com → Settings → Workspaces, l'identifiant commence par wrkspc_.
							{s.espace_travail ? ' Un espace de travail est déjà indiqué ✓.' : ''}</p>
						<div className="cl-ligne">
							<input type="text" value={espace} placeholder="wrkspc_…" disabled={working} onChange={(e) => setEspace(e.target.value)} aria-label="Identifiant de l'espace de travail" />
							<button className="sr-btn petit" disabled={working || !espace.trim()} onClick={() => enregistrer({espace_travail: espace.trim()}, 'Espace de travail enregistré.').then((f) => f && setEspace(''))}>
								Enregistrer</button>
							{s.espace_travail ? <button className="sr-btn petit" disabled={working} onClick={() => enregistrer({espace_travail: null}, 'Espace de travail retiré.')}>Retirer</button> : null}
						</div>
					</div>
				) : null}
				<button className="cl-lien" aria-expanded={voirCouts} onClick={() => setVoirCouts(!voirCouts)}>{voirCouts ? '▾' : '▸'} Coûts Claude</button>
				{voirCouts ? (
					<div className="cl-couts" aria-label="Coûts Claude">
						{!couts ? <p className="sr-muet">Lecture des coûts…</p> : (
							<>
								<div className="cl-chiffres">
									<span>Aujourd'hui : <b>{argent(couts.jours?.[0]?.cout)}</b></span>
									<span>Ce mois : <b>{argent(couts.mois?.cout)}</b></span>
									<span>Crédit restant : <b>{argent(couts.credit?.restant_estime)}</b></span>
								</div>
								{couts.derniers?.length ? (
									<ul className="cl-appels">
										{couts.derniers.map((a, n) => (
											<li key={n} title={a.erreur ?? (a.video ? `Vidéo : ${a.video}` : '')}>
												<span className="cl-appel-date">{heureCourte(a.date)}</span>
												<span className="cl-appel-tache">{tacheFr(a.tache)}{a.video ? <small> · {a.video.split('/')[0]}</small> : null}</span>
												<span className="cl-appel-modele">{nomModele(a.modele)}</span>
												<span className={`cl-appel-cout${a.ok ? '' : ' ko'}`}>{argent(a.cout)} {a.ok ? '✓' : '✗'}</span>
											</li>
										))}
									</ul>
								) : <p className="sr-muet">Aucun appel à Claude pour l'instant.</p>}
							</>
						)}
					</div>
				) : null}
				<p className="sr-muet cl-console">Console Anthropic : platform.claude.com</p>
				{ok ? <p className="sr-ok">{ok}</p> : null}
				{err ? <p className="sr-err">{err}</p> : null}
			</div>
		</>
	);
};

/** Video choisie, gardee quand on passe a l'Editeur (« Modifier ») puis qu'on revient : on retombe sur la video retouchee. */
let choixGarde: string | null = null;
export const Revision: React.FC<{onEdit: (key: string) => void; templates: Template[]; onTemplates: () => Promise<unknown>;
	onCompte?: (c: RevisionCompte) => void}> = ({onEdit, templates, onTemplates, onCompte}) => {
	const [state, setState] = useState<State | null>(null);
	const [offline, setOffline] = useState(false);
	const [sel, setSel] = useState<string | null>(() => choixGarde);
	useEffect(() => {
		choixGarde = sel;
	}, [sel]);
	const [opened, setOpened] = useState<Opened | null>(null);
	const [reels, setReels] = useState<Record<string, ReelDoc>>({});
	const [galerie, setGalerie] = useState(false);
	const [corbeille, setCorbeille] = useState(false);
	const [busy, setBusy] = useState('');
	const [err, setErr] = useState('');
	const [notice, setNotice] = useState('');
	// « Choisir plusieurs » : cases a cocher dans la liste pour prendre ou supprimer plusieurs videos d'un coup
	const [picking, setPicking] = useState(false);
	const [picked, setPicked] = useState<string[]>([]);
	const [formats, setFormats] = useState<string[]>(loadFormats);
	const [types, setTypes] = useState<Types | null>(null);
	const compteRef = useRef(onCompte);
	compteRef.current = onCompte;
	const refresh = useCallback(() => api('/api/revision').then((s: State) => {
		setState(s);
		setOffline(false);
		compteRef.current?.(compter(s));
		return s;
	}).catch(() => setOffline(true)), []);
	useEffect(() => {
		refresh();
		const t = window.setInterval(refresh, 2500);
		return () => window.clearInterval(t);
	}, [refresh]);
	const depot = useDepot(refresh, galerie);
	const items = state?.items ?? [];
	const item = items.find((i) => i.id === sel) ?? null;
	// premiere video prete selectionnee d'office (et une autre si celle-ci a ete retiree)
	useEffect(() => {
		if (items.length && (!sel || !items.some((i) => i.id === sel))) setSel((items.find((i) => i.status === 'pret') ?? items[0]).id);
	}, [items, sel]);
	const ready = !!item?.project && !!item.rid && (item.status === 'pret' || item.status === 'pris');
	const key = ready ? `${item!.project}/${item!.rid}` : '';
	// montage affiche : relu quand on change de video ou quand le serveur l'a refait (nouveau style, « Refaire »)
	const shownKey = useRef('');
	useEffect(() => {
		if (shownKey.current !== key) {
			shownKey.current = key;
			setOpened(null);
			setGalerie(false);
			setErr('');
		}
		if (!key) return;
		let live = true;
		api(`/api/reels/${key}/open`).then((d: Opened) => {
			if (!live) return;
			setOpened(d);
			setReels((r) => ({...r, [key]: d.reel}));
		}).catch((e) => live && setErr(`Impossible d'ouvrir ce montage : ${(e as Error).message}`));
		return () => {
			live = false;
		};
		// item.controle.date : nouvelle note du controle qualite (apres un changement de style) -> constats relus
	}, [key, item?.updated, item?.controle?.stamp ?? item?.controle?.date]);
	// vignettes de la liste (un montage illisible ou deplace n'est pas redemande toutes les 2,5 s)
	const thumbAsked = useRef(new Map<string, number>());
	useEffect(() => {
		const now = Date.now();
		items.filter((i) => i.project && i.rid && !reels[`${i.project}/${i.rid}`] && now - (thumbAsked.current.get(`${i.project}/${i.rid}`) ?? 0) > 30000)
			.slice(0, 4).forEach((i) => {
				const k = `${i.project}/${i.rid}`;
				thumbAsked.current.set(k, now); // nouvel essai au plus toutes les 30 s si le montage ne s'ouvre pas
				api(`/api/reels/${k}/open`).then((d: Opened) => setReels((r) => ({...r, [k]: d.reel}))).catch(() => undefined);
			});
	}, [items]);
	// sujets (« Toujours ce style pour … ») : lus a l'ouverture de la galerie
	useEffect(() => {
		if (galerie) api('/api/types').then(setTypes).catch(() => undefined);
	}, [galerie]);

	const reel = opened?.reel;
	const total = useMemo(() => (reel ? duration(reel) : 1), [reel]);
	// le lecteur ne recoit jamais l'historique des demandes « Dis a l'IA » (reel.consignes : interface seulement, jamais exporte)
	const inputProps = useMemo(() => {
		if (!reel) return null;
		const {consignes: _consignes, ...image} = reel as ReelDoc & {consignes?: unknown};
		return {reel: image as ReelDoc, mediaBase: '', assetBase: '/assets', audio: 'preview' as const};
	}, [reel]);
	// ---- controle qualite : aller au moment d'un probleme (et montrer l'endroit), relancer le controle du montage ----
	const player = useRef<PlayerRef>(null);
	const lecteur = useRef<HTMLDivElement>(null);
	const [zone, setZone] = useState<{box: [number, number, number, number]; n: number} | null>(null);
	const [onglet, setOnglet] = useState('');
	const [relance, setRelance] = useJob(() => {
		if (!key) return;
		api(`/api/reels/${key}/open`).then((d: Opened) => {
			setOpened(d);
			setReels((r) => ({...r, [key]: d.reel}));
		}).catch(() => undefined);
		refresh();
	});
	useEffect(() => {
		setZone(null);
		setOnglet('');
		// « Contrôle en cours… » / erreur d'une relance concernaient la video precedente : pas celle-ci (la tache continue
		// cote serveur, sa note arrive sur sa fiche)
		setRelance(null);
	}, [key]);
	useEffect(() => {
		if (!zone) return;
		const t = window.setTimeout(() => setZone(null), 4500);
		return () => window.clearTimeout(t);
	}, [zone]);
	const voir = (t: number, box: Constat['zone'] | null) => {
		if (!reel) return;
		player.current?.pause();
		player.current?.seekTo(Math.max(0, Math.min(Math.round(total * reel.fps) - 1, Math.round(t * reel.fps))));
		setZone(box ? {box, n: Date.now()} : null);
		// ecran etroit : le panneau est SOUS le lecteur ; on remonte jusqu'a l'image si elle n'est plus visible
		lecteur.current?.scrollIntoView({block: 'nearest', behavior: 'smooth'});
	};
	// temps du lecteur (s) pour la boite « Dis a l'IA » (« à 0:12, enlève… ») : a la pause, a chaque saut, et une fois par seconde
	// pendant la lecture (jamais a chaque image : la page entiere serait redessinee)
	const [tempsLecteur, setTempsLecteur] = useState(0);
	useEffect(() => {
		const p = player.current;
		setTempsLecteur(0);
		if (!p || !reel) return;
		let dernier = 0;
		const maj = () => setTempsLecteur(Math.round((100 * p.getCurrentFrame()) / reel.fps) / 100);
		const image = () => {
			if (Date.now() - dernier < 1000) return;
			dernier = Date.now();
			maj();
		};
		p.addEventListener('pause', maj);
		p.addEventListener('seeked', maj);
		p.addEventListener('frameupdate', image);
		return () => {
			p.removeEventListener('pause', maj);
			p.removeEventListener('seeked', maj);
			p.removeEventListener('frameupdate', image);
		};
	}, [key, !!reel, reel?.fps]);
	const controleMontage = (reel as (ReelDoc & {controle?: Controle}) | undefined)?.controle ?? null;
	const rapports: Rapport[] = useMemo(() => {
		const list: Rapport[] = [{cle: 'montage', titre: 'Montage', controle: controleMontage}];
		for (const e of item?.exports ?? []) {
			if (e.status === 'done' || e.controle || e.controleEtat) list.push({cle: `export:${e.job}`, titre: `Export ${e.format}`, controle: e.controle, etat: e.controleEtat, video: e.out});
		}
		return list;
	}, [controleMontage, item?.exports]);
	// onglet par defaut : la video livree la plus recente qui a un controle (plus complet : images, son), sinon le montage
	const ongletDefaut = [...rapports].reverse().find((x) => x.cle !== 'montage' && (aNote(x.controle) || x.etat))?.cle ?? 'montage';
	// un serveur lance avant cette version ne connait pas la route : on le dit clairement (au lieu de « Introuvable. »)
	const routeControle = async (body: object) => {
		try {
			return await api(`/api/reels/${key}/controle`, 'POST', body);
		} catch (e) {
			if ((e as Error).message === 'Introuvable.') throw new Error('Le contrôle qualité n\'est pas encore actif : relance l\'éditeur (« Editeur Sami.cmd »), puis réessaie.');
			throw e;
		}
	};
	const act = async (label: string, fn: () => Promise<unknown>) => {
		setBusy(label);
		setErr('');
		setNotice('');
		try {
			await fn();
			return true;
		} catch (e) {
			setErr((e as Error).message);
			return false;
		} finally {
			setBusy('');
		}
	};
	const relancer = () => act('Contrôle qualité du montage…', async () => {
		setRelance(await routeControle({}));
		setOnglet('montage');
	});
	const controlerExport = (e: ItemExport) => act(`Contrôle de l'export ${e.format}…`, async () => {
		await routeControle({video: e.out, format: e.format});
		setOnglet(`export:${e.job}`);
		await refresh();
	});
	/** Suivante : la prochaine video prete a regarder (apres celle-ci dans la liste), sinon simplement la video d'apres. */
	const next = () => {
		if (!items.length) return;
		const k = Math.max(0, items.findIndex((i) => i.id === sel));
		const ordre = [...items.slice(k + 1), ...items.slice(0, k)];
		const n = ordre.find((i) => i.status === 'pret') ?? ordre[0];
		if (n) setSel(n.id);
	};
	const exportsList = item?.exports ?? [];
	const exporting = exportsList.some(running);
	const pct = pctExports(exportsList);
	const toggleFormat = (f: string) => {
		const list = Object.keys(FORMATS).filter((k) => (k === f ? !formats.includes(k) : formats.includes(k)));
		setFormats(list);
		if (list.length) storeFormats(list);
	};
	const peutPrendre = ready && !!reel && !busy && !exporting && !!formats.length;
	const enPrise = useRef(false); // double clic / Entree repetee : une seule mise en file
	const take = () => {
		if (!item || !peutPrendre || enPrise.current) return;
		// probleme bloquant trouve par le controle qualite : on previent avant d'exporter (le choix reste au monteur)
		const bloquants = (controleMontage?.constats ?? []).filter((k) => k.gravite === 'bloquant');
		if (controleMontage?.compte.bloquant && !window.confirm([`Le contrôle qualité (${controleMontage.date}) a trouvé ${controleMontage.compte.bloquant} problème(s) bloquant(s) :`, '',
			...bloquants.slice(0, 5).map((k) => `• ${k.temps !== null ? `${tcv(k.temps)} — ` : ''}${k.message}`), '',
			'Exporter quand même ? (« Annuler » pour corriger d\'abord : clique un problème pour aller au bon moment.)'].join('\n'))) return;
		enPrise.current = true;
		act(`Mise en file de l'export (${formats.join(', ')})…`, async () => {
			await api(`/api/revision/${item.id}/prendre`, 'POST', {formats});
			await refresh();
		}).finally(() => {
			enPrise.current = false;
		});
	};
	const cancelExport = (e: ItemExport) => act('Annulation de l\'export…', async () => {
		await api(`/api/jobs/${e.job}/cancel`, 'POST');
		await refresh();
	});
	const openFolder = (file?: string) => file && api('/api/open-folder', 'POST', {file}).catch((e) => setErr((e as Error).message));
	/** Dossier des videos brutes d'une video (item.unit est relatif a la racine de l'editeur, ENTREE = <racine>\media\entree). */
	const unitPath = (i: Item) => {
		const racine = (state?.entree ?? '').replace(/[\\/]media[\\/]entree[\\/]?$/i, '');
		return racine ? `${racine}\\${winPath(i.unit)}` : '';
	};
	const remove = (i: Item) => {
		if (!window.confirm(`Retirer « ${i.title || i.name} » de la liste ?\n\nAucun fichier n'est supprimé (vidéo brute, montage et exports restent sur le disque).\n`
			+ 'Pour t\'en débarrasser vraiment, utilise plutôt « Supprimer ».')) return;
		act('Retrait…', () => api(`/api/revision/${i.id}/retirer`, 'POST', {}).then(setState));
	};
	const trash = state?.corbeille ?? 'le dossier corbeille de l\'éditeur';
	/** Message apres suppression : ou sont les fichiers, ce qui est garde. */
	const deletedText = (d: Deleted) => [`« ${d.titre} » supprimée.`,
		d.corbeille ? `Montage et vidéos brutes rangés dans : ${d.corbeille}` : 'Il n\'y avait aucun fichier à ranger.',
		...d.gardes.map((g) => `Gardé : ${g}.`),
		d.livraisons.length ? `Vidéo(s) exportée(s) gardée(s) : ${d.livraisons.join(' ; ')}` : ''].filter(Boolean).join('\n');
	const supprimer = (i: Item) => {
		const why = deleteBlock(i);
		if (why) return setErr(why);
		// meme regle que le serveur (planSuppression) : une autre video, meme retiree de la liste, garde ce qu'elle partage
		const shared = i.partage?.unit ?? items.some((o) => o.id !== i.id && o.unit === i.unit);
		const sharedProject = i.partage?.project ?? items.some((o) => o.id !== i.id && !!i.project && o.project === i.project);
		const exported = !!i.taken || (i.exports ?? []).some((e) => e.status === 'done');
		const lines = [`Supprimer « ${i.title || i.name} » ?`, '', '• Elle disparaît de la liste.'];
		if (i.project) lines.push(sharedProject ? `• Son montage (projects\\${i.project}) est GARDÉ : une autre vidéo (peut-être retirée de la liste) l'utilise.`
			: `• Son montage (projects\\${i.project}) va dans la corbeille de l'éditeur.`);
		lines.push(shared ? `• Ses vidéos brutes (${winPath(i.unit)}) sont GARDÉES : une autre vidéo (peut-être retirée de la liste) les utilise.`
			: `• Ses vidéos brutes (${winPath(i.unit)}) vont aussi dans la corbeille.`);
		lines.push(exported ? '• Les vidéos déjà exportées (dossier livraisons) sont GARDÉES.' : '• Les vidéos exportées (dossier livraisons) ne sont jamais touchées.');
		lines.push('', `Rien n'est effacé pour de bon : tout est rangé dans ${trash}. Bouton « Restaurer » dans la Corbeille (en bas de la liste) pour la remettre.`);
		if (!window.confirm(lines.join('\n'))) return;
		act('Suppression…', async () => {
			const d: State & {supprime: Deleted} = await api(`/api/revision/${i.id}/supprimer`, 'POST', {});
			setState(d);
			compteRef.current?.(compter(d));
			setPicked((p) => p.filter((x) => x !== i.id));
			setNotice(deletedText(d.supprime));
		});
	};
	const pickedItems = items.filter((i) => picked.includes(i.id));
	const supprimerPlusieurs = () => {
		if (!pickedItems.length) return;
		const blocked = pickedItems.filter((i) => deleteBlock(i));
		const lines = [`Supprimer ${pickedItems.length} vidéo(s) ?`, '', ...pickedItems.slice(0, 12).map((i) => `• ${i.title || i.name}`)];
		if (pickedItems.length > 12) lines.push(`• … et ${pickedItems.length - 12} autre(s)`);
		lines.push('', 'Leur montage et leurs vidéos brutes vont dans la corbeille de l\'éditeur (rien n\'est effacé pour de bon).',
			'Les vidéos déjà exportées (dossier livraisons) sont gardées.');
		if (blocked.length) lines.push(`${blocked.length} vidéo(s) en montage ou en export ne seront pas supprimées.`);
		lines.push('', `Corbeille : ${trash}`);
		if (!window.confirm(lines.join('\n'))) return;
		act('Suppression…', async () => {
			const d: State & {resultats: ({ok: boolean; id: string; titre?: string; error?: string} & Partial<Deleted>)[]} =
				await api('/api/revision/supprimer', 'POST', {ids: pickedItems.map((i) => i.id)});
			setState(d);
			compteRef.current?.(compter(d));
			const ok = d.resultats.filter((r) => r.ok);
			const ko = d.resultats.filter((r) => !r.ok);
			setPicked(ko.map((r) => r.id));
			if (!ko.length) setPicking(false);
			const where = [...new Set(ok.map((r) => r.corbeille).filter(Boolean))];
			setNotice([`${ok.length} vidéo(s) supprimée(s).`, where.length ? `Rangées dans : ${trash}` : ''].filter(Boolean).join('\n'));
			if (ko.length) setErr(`Pas supprimée(s) :\n${ko.map((r) => `• ${r.titre ?? r.id} : ${r.error}`).join('\n')}`);
		});
	};
	/** « Prendre » plusieurs videos d'un coup : chaque video prete part dans la file d'exports, aux formats coches. */
	const prendrePlusieurs = () => {
		const prets = pickedItems.filter((i) => i.status === 'pret' && !!i.project && !(i.exports ?? []).some(running));
		if (!prets.length) return setErr('Aucune des vidéos choisies n\'est prête à prendre (seules les vidéos « Prête à regarder » partent à l\'export).');
		if (!formats.length) return setErr('Coche au moins un format d\'export (sous les gros boutons) avant de prendre des vidéos.');
		const bloq = prets.filter((i) => i.controle?.compte?.bloquant);
		const lines = [`Prendre ${prets.length} vidéo(s) ? Un fichier par format : ${formats.join(', ')}.`, '', ...prets.slice(0, 12).map((i) => `• ${i.title || i.name}`)];
		if (prets.length > 12) lines.push(`• … et ${prets.length - 12} autre(s)`);
		if (pickedItems.length > prets.length) lines.push('', `${pickedItems.length - prets.length} vidéo(s) choisie(s) ne sont pas prêtes : elles sont laissées de côté.`);
		if (bloq.length) lines.push('', `⚠ Le contrôle qualité a trouvé un problème bloquant dans : ${bloq.map((i) => `« ${i.title || i.name} »`).join(', ')}.`);
		lines.push('', 'Les exports partent un par un dans la file ; tu peux continuer à regarder les autres vidéos.');
		if (!window.confirm(lines.join('\n'))) return;
		act(`Mise en file de ${prets.length} vidéo(s)…`, async () => {
			const ko: string[] = [];
			for (const i of prets) {
				try {
					await api(`/api/revision/${i.id}/prendre`, 'POST', {formats});
				} catch (e) {
					ko.push(`• ${i.title || i.name} : ${(e as Error).message}`);
				}
			}
			await refresh();
			setPicked([]);
			setPicking(false);
			setNotice(`${prets.length - ko.length} vidéo(s) envoyée(s) à l'export (${formats.join(', ')}).`);
			if (ko.length) setErr(`Pas envoyée(s) :\n${ko.join('\n')}`);
		});
	};
	const togglePick = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
	// « Suivante » pendant l'application d'un style : le montage recu n'est affiche que si sa video est encore a l'ecran
	const montrer = (k: string, d: Opened) => {
		if (shownKey.current === k) setOpened(d);
		setReels((r) => ({...r, [k]: d.reel}));
	};
	const applyStyle = (t: Pick<Template, 'id' | 'name'>) => act(`Style « ${t.name} » en cours d'application…`, async () => {
		if (!item) throw new Error('Choisis d\'abord une vidéo.');
		const k = key;
		const d: Opened = await api(`/api/revision/${item.id}/style`, 'POST', {style: t.id});
		montrer(k, d);
		await refresh();
		setNotice(`Style « ${templates.find((x) => x.id === t.id)?.name ?? t.name} » appliqué. Pour revenir en arrière : « Autre style » → « Revenir au style précédent ».`);
	});
	const retourStyle = () => item && act('Retour au style précédent…', async () => {
		const k = key;
		const d: Opened = await api(`/api/revision/${item.id}/retourstyle`, 'POST', {});
		montrer(k, d);
		await refresh();
		setGalerie(false);
		setNotice(`Style précédent remis : « ${styleName(d.reel.template)} ».`);
	});
	// un message de reussite s'efface tout seul (les erreurs restent jusqu'a ce qu'on les ferme)
	useEffect(() => {
		if (!notice) return;
		const t = window.setTimeout(() => setNotice(''), 12000);
		return () => window.clearTimeout(t);
	}, [notice]);
	const styleName = (id?: string) => templates.find((t) => t.id === id)?.name ?? id ?? 'aucun';
	const pinStyle = () => item?.type && reel?.template && act('Enregistrement du style du sujet…', async () => {
		setTypes(await api(`/api/types/${item.type}`, 'POST', {style: reel.template}));
		setNotice(`C'est noté : les prochaines vidéos « ${item.typeLabel ?? item.type} » seront montées en « ${styleName(reel.template)} ».`);
	});
	// ---- Claude (IA en ligne, payant) : « 🧠 Refaire avec Claude » (idees du montage) et « 👁 Critique Claude » (relecture des
	// images) ; seulement sur un clic confirme, un appel a la fois par video ; cout estime affiche avant ----
	const claude = useClaude();
	const iaQuoi = useRef<{quoi: 'cerveau' | 'critique'; key: string} | null>(null);
	const [iaResultat, setIaResultat] = useState<{quoi: 'cerveau' | 'critique'; key: string; result: any} | null>(null);
	const [iaJob, setIaJob] = useJob((j) => {
		const q = iaQuoi.current;
		if (!q) return;
		setIaResultat({...q, result: j.result ?? {}});
		relireClaude(true);
		refresh();
		api(`/api/reels/${q.key}/open`).then((d: Opened) => montrer(q.key, d)).catch(() => undefined);
	});
	const iaTourne = !!iaJob && (iaJob.status === 'running' || iaJob.status === 'queued') && iaQuoi.current?.key === key;
	/** Pourquoi un bouton Claude est desactive ('' = possible). */
	const raisonIa = (quoi: 'cerveau' | 'critique') => {
		if (claude.absent) return 'Claude n\'est pas encore actif dans l\'éditeur lancé : relance-le (« Editeur Sami.cmd »).';
		const s = claude.statut;
		if (!s) return 'Lecture de l\'état de Claude…';
		if (!s.pret) return s.raison || 'Claude n\'est pas prêt (réglages ⚙️).';
		if (item?.iaEnCours || iaTourne) return `L'IA travaille déjà sur cette vidéo (${(item?.iaEnCours?.stage ?? iaJob?.stage ?? '').toLowerCase()}) : attends la fin.`;
		if (busy) return 'Attends la fin de l\'action en cours.';
		// la critique juge la video LIVREE (images de l'export) : rien a relire avant le premier export
		if (quoi === 'critique' && !(item?.exports ?? []).some((e) => e.status === 'done')) return 'Critique Claude : exporte d\'abord la vidéo (« Je la prends ») ; Claude relit les images de la vidéo livrée.';
		const est = estimationClaude(s, quoi) ?? 0;
		const dv = item?.claude?.cout ?? 0;
		if (s.plafonds && dv + est > s.plafonds.video) return `Plafond par vidéo presque atteint : ${argent(dv)} déjà dépensés sur ${argent(s.plafonds.video)} (réglages ⚙️ → Claude → Avancé).`;
		if (s.plafonds && (s.depense_jour ?? 0) + est > s.plafonds.jour) return `Plafond du jour presque atteint : ${argent(s.depense_jour)} sur ${argent(s.plafonds.jour)} (réglages ⚙️ → Claude → Avancé).`;
		if (s.plafonds && (s.depense_mois ?? 0) + est > s.plafonds.mois) return `Plafond du mois presque atteint : ${argent(s.depense_mois)} sur ${argent(s.plafonds.mois)} (réglages ⚙️ → Claude → Avancé).`;
		if (typeof s.credit_restant_estime === 'number' && s.credit_restant_estime < est) return `Crédit Claude presque épuisé (il reste environ ${argent(s.credit_restant_estime)}) : recharge sur platform.claude.com, puis indique le nouveau crédit dans les réglages ⚙️.`;
		return '';
	};
	const lancerIa = (quoi: 'cerveau' | 'critique') => {
		if (!item?.project || !item.rid || !reel) return;
		const why = raisonIa(quoi);
		if (why) return setErr(why);
		const est = estimationClaude(claude.statut, quoi);
		const reste = claude.statut?.credit_restant_estime;
		const exportFait = [...(item.exports ?? [])].reverse().find((e) => e.status === 'done');
		const cout = `Coût estimé : environ ${est !== null ? argent(est) : 'quelques centimes'}${typeof reste === 'number' ? ` (crédit restant estimé : ${argent(reste)})` : ''}.`;
		const lignes = quoi === 'cerveau'
			? ['Refaire les idées du montage avec Claude ?', '', 'Claude relit ce qui est dit et refait les mots forts, les textes des cartes, le bandeau et le découpage.', cout,
				'', 'Le montage actuel est gardé dans les versions : tu pourras revenir en arrière.']
			: ['Faire relire les images par Claude ?', '', `Claude regarde des images de la vidéo livrée${exportFait ? ` (export ${exportFait.format})` : ''} et donne son avis : note, problèmes avec leur moment.`,
				cout, '', 'Rien n\'est changé dans le montage. Un avis déjà payé pour cette même vidéo revient gratuitement.'];
		if (!window.confirm(lignes.join('\n'))) return;
		const k = key;
		act(quoi === 'cerveau' ? 'Claude : idées du montage…' : 'Claude : relecture des images…', async () => {
			const j = await api(`/api/reels/${k}/claude/${quoi}`, 'POST', quoi === 'critique' && exportFait ? {video: exportFait.out} : {});
			iaQuoi.current = {quoi, key: k};
			setIaResultat(null);
			setIaJob(j);
			await refresh();
		});
	};
	/** Annuler les idees de Claude : la version « avant » gardee par le serveur revient (l'etat avec Claude reste dans les versions). */
	const annulerIa = (file: string) => act('Retour au montage d\'avant Claude…', async () => {
		const k = key;
		const d: Opened = await api(`/api/reels/${k}/restore`, 'POST', {file});
		montrer(k, d);
		setIaResultat(null);
		await refresh();
		setNotice('Montage d\'avant Claude remis. La version faite avec Claude reste dans « Modifier » → Versions.');
	});
	/** Une demande « Dis a l'IA » appliquee (composant Consigne) : liste et montage relus ; autre version -> on la montre si c'est la meme video. */
	const consigneAppliquee = (version: string) => {
		relireClaude(true);
		refresh();
		if (!item?.project) return;
		const k = `${item.project}/${version || item.rid}`;
		api(`/api/reels/${k}/open`).then((d: Opened) => montrer(k, d)).catch(() => undefined);
	};
	const avis = useMemo(() => (iaResultat?.quoi === 'critique' && iaResultat.key === key ? avisDe(iaResultat.result) : null) ?? avisDuReel(reel), [iaResultat, key, reel]);
	const speech = reel && reel.kind !== 'immobilier' && reel.kind !== 'evenement';
	const preview = reel ? formatOf(reel) : '9:16';

	// ---- raccourcis clavier (Entree, E, S, fleche droite, Espace, Echap) : jamais pendant une saisie ----
	// Souris ou clavier ? Une carte ou un bouton cliques a la souris gardent le focus : Entree / Espace restent alors les
	// raccourcis (Je la prends, lecture). Apres Tab (navigation au clavier), Entree active l'element qui a le focus.
	const souris = useRef(true);
	useEffect(() => {
		const pointe = () => {
			souris.current = true;
		};
		const tab = (e: KeyboardEvent) => {
			if (e.key === 'Tab') souris.current = false;
		};
		window.addEventListener('pointerdown', pointe, true);
		window.addEventListener('keydown', tab, true);
		return () => {
			window.removeEventListener('pointerdown', pointe, true);
			window.removeEventListener('keydown', tab, true);
		};
	}, []);
	// Ctrl+Z dans la Revision : l'historique d'annulation est celui de l'Editeur (dernier montage ouvert) ; l'appliquer ici
	// changerait ce montage et l'enregistrerait sans rien montrer. Arrete avant l'editeur (phase de capture) ; champ de texte :
	// annulation normale du texte.
	useEffect(() => {
		const bloque = (e: KeyboardEvent) => {
			if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'z') return;
			const el = e.target as HTMLElement | null;
			if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return;
			e.stopPropagation();
			e.preventDefault();
			setNotice('Ctrl+Z ne sert que dans l\'Éditeur. Ici, pour annuler un changement de style : « Autre style » → « Revenir au style précédent ».');
		};
		window.addEventListener('keydown', bloque, true);
		return () => window.removeEventListener('keydown', bloque, true);
	}, []);
	const clavier = useRef<(e: KeyboardEvent) => void>(() => undefined);
	clavier.current = (e: KeyboardEvent) => {
		if (e.ctrlKey || e.metaKey || e.altKey) return;
		// touche maintenue : seule la fleche (videos suivantes) se repete ; jamais deux exports d'un coup
		if (e.repeat && e.key !== 'ArrowRight') return;
		const el = e.target as HTMLElement | null;
		if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)) return;
		if (document.querySelector('.sa-pop')) return; // panneau des reglages ouvert (Echap le ferme)
		const surBouton = !souris.current && !!el?.closest?.('button, a, summary, [role="button"], [role="tab"], [role="slider"]');
		if (e.key === 'Escape') {
			if (galerie) setGalerie(false);
			else if (corbeille) setCorbeille(false);
			return;
		}
		if (e.key === 'Enter') {
			// Entree sur un bouton atteint au clavier = ce bouton (comportement normal) ; galerie ouverte : pas d'export par erreur
			if (surBouton || galerie) return;
			e.preventDefault(); // un bouton clique a la souris (« Suivante », un moment…) n'est pas relance par Entree
			take();
		} else if (e.key === 'e' || e.key === 'E') {
			if (!ready || busy) return; // comme le bouton « Modifier » (desactive pendant une action)
			e.preventDefault();
			onEdit(key);
		} else if (e.key === 's' || e.key === 'S') {
			if (!ready || !reel || (busy && !galerie)) return; // comme le bouton « Autre style »
			e.preventDefault();
			setGalerie((g) => !g);
		} else if (e.key === 'ArrowRight') {
			e.preventDefault();
			next();
		} else if (e.key === ' ') {
			if (!reel) return;
			e.preventDefault();
			player.current?.toggle();
		}
	};
	useEffect(() => {
		const h = (e: KeyboardEvent) => clavier.current(e);
		window.addEventListener('keydown', h);
		return () => window.removeEventListener('keydown', h);
	}, []);

	const ar = reel ? reel.width / reel.height : 9 / 16;
	const frames = reel ? Math.max(1, Math.round(total * reel.fps)) : 1;
	const label = item ? item.title || item.name : '';
	const etape = item && (item.status === 'attente' || item.status === 'travail') ? etapeDe(item) : 0;
	const enCours = item?.status === 'travail' || item?.status === 'attente';
	const metaPrete = item && reel ? [`Sujet : ${item.typeLabel ?? '—'}`, `style : ${styleName(reel.template)}`, mmss(total), `${reel.clips.length} plan${reel.clips.length > 1 ? 's' : ''}`,
		...(item.broll ? [`${item.broll} plan(s) de coupe`] : []), ...(item.ia === false ? ['montée sans IA locale (règles simples)'] : [])].join(' — ') : '';

	return (
		<div className="sr">
			{depot.inputs}
			{depot.over ? <div className="sr-depose" onDragLeave={() => depot.setOver(false)}><div><I.Upload size={34} />Dépose tes vidéos ici</div></div> : null}
			<aside className="sr-gauche">
				<div className="sr-gauche-haut">
					<DepotCarte depot={depot} />
					{offline ? <p className="sr-err sr-horsligne">L'éditeur ne répond pas (redémarrage en cours ?) : nouvel essai toutes les 2 secondes…</p> : null}
				</div>
				<div className="sr-liste-tete">
					<h2>Vidéos du jour</h2>
					<span className="grow" />
					{picking ? <button className="sr-lien sr-toutes" onClick={() => setPicked(picked.length === items.length ? [] : items.map((i) => i.id))}>
						{picked.length === items.length ? 'Aucune' : 'Toutes'}</button> : null}
					{items.length > 1 ? (
						<button className={`sr-btn petit${picking ? ' on' : ''}`} onClick={() => { setPicking(!picking); setPicked([]); }}
							title="Cocher plusieurs vidéos pour les prendre ou les supprimer d'un coup"><I.SquareCheck size={15} />{picking ? 'Fini' : 'Choisir plusieurs'}</button>
					) : null}
				</div>
				{picking ? (
					<div className="sr-multi">
						<span>{picked.length} choisie{picked.length > 1 ? 's' : ''}</span>
						<span className="grow" />
						<button className="sr-btn petit cyan" disabled={!picked.length || !!busy} onClick={prendrePlusieurs} title={`Exporter les vidéos prêtes choisies (${formats.join(', ') || 'aucun format coché'})`}>Prendre</button>
						<button className="sr-btn petit danger" disabled={!picked.length || !!busy} onClick={supprimerPlusieurs} title="Mettre les vidéos choisies à la corbeille (récupérables)">Supprimer</button>
					</div>
				) : null}
				<div className="sr-liste">
					{state && !items.length ? <p className="sr-liste-vide">Aucune vidéo pour l'instant.<br />Dépose tes vidéos brutes ci-dessus,<br />ou copie-les dans <b>media\entree\</b> (un dossier par lot).</p> : null}
					{items.map((i) => {
						const why = deleteBlock(i);
						const nom = i.title || i.name;
						const st = etatDe(i);
						const choisi = picked.includes(i.id);
						const reelI = i.project ? reels[`${i.project}/${i.rid}`] : undefined;
						const choisir = () => (picking ? togglePick(i.id) : setSel(i.id));
						return (
							<div key={i.id} className={`sr-carte${i.id === sel ? ' on' : ''}${picking ? ' picking' : ''}${choisi ? ' picked' : ''}`} role="button" tabIndex={0}
								aria-pressed={picking ? choisi : i.id === sel} onClick={choisir}
								// Entree / Espace sur la carte atteinte au clavier (Tab) = la choisir ; apres un clic souris ce sont les raccourcis
								// (Je la prends, lecture) ; sur sa corbeille, Entree = la corbeille
								onKeyDown={(e) => {
									if (e.target !== e.currentTarget || souris.current || (e.key !== 'Enter' && e.key !== ' ')) return;
									e.preventDefault();
									e.stopPropagation();
									choisir();
								}}
								title={i.style ? `Style : ${styleName(i.style)}` : undefined}>
								{picking ? <span className={`sr-case${choisi ? ' on' : ''}`} aria-hidden><I.Check size={13} strokeWidth={3} /></span> : null}
								<Vignette reel={reelI} id={i.id} />
								<div className="sr-carte-corps">
									<b>{nom}</b>
									<span className="cl-carte-ligne">
										<span className="sr-carte-sujet">{i.typeLabel || i.lot}</span>
										{/* Claude a servi pour cette video : combien elle a coute (detail au survol) */}
										{i.claude && (i.claude.cout > 0 || Object.values(i.claude.groupes ?? {}).some((g) => g && g.ok)) ? (
											<span className="cl-badge" title={`${ligneClaude(i.claude)}\n(dépensé avec Claude pour cette vidéo)`}>🧠 {argent(i.claude.cout)}</span>
										) : null}
									</span>
									<span className="grow" />
									<span className={`sr-etat ${st.cls}`}><i />{st.label}</span>
									{st.pct !== undefined ? <div className={`sr-barre fine ${st.cls}`}><div style={{width: `${st.pct}%`}} /></div> : null}
								</div>
								{i.controle && (i.status === 'pret' || i.status === 'pris') ? (
									<span className={`sr-note ${noteClasse(i.controle)}`} title={`Contrôle qualité du ${i.controle.date} : ${i.controle.verdict} (${compteTexte(i.controle.compte)})`}>
										{virgule(i.controle.note)}</span>
								) : null}
								{!picking ? (
									<button className={`sr-carte-suppr${why ? ' bloque' : ''}`} disabled={!!busy} onClick={(e) => { e.stopPropagation(); supprimer(i); }}
										title={why || 'Supprimer cette vidéo (elle va dans la corbeille de l\'éditeur)'} aria-label={`Supprimer « ${nom} »`}><I.Trash size={15} /></button>
								) : null}
							</div>
						);
					})}
				</div>
				{corbeille ? (
					<TrashPanel count={state?.corbeilleN ?? 0} folder={state?.corbeille} busy={!!busy} onError={setErr} onClose={() => setCorbeille(false)} onRestored={(r) => {
						setNotice([`« ${r.titre} » restaurée.`, ...r.remis.map((d) => `Remis : ${winPath(d)}`), r.item ? 'Elle est de retour dans la liste.' : '', r.note].filter(Boolean).join('\n'));
						// la liste d'abord (sinon la selection retomberait sur la premiere video prete), puis la video restauree
						refresh().then(() => r.item && setSel(r.item.id));
					}} />
				) : null}
				<div className="sr-gauche-pied">
					<button className={`sr-pied-btn${corbeille ? ' on' : ''}`} onClick={() => setCorbeille(!corbeille)} aria-expanded={corbeille}
						title="Vidéos supprimées : montage et vidéos brutes rangés dans la corbeille de l'éditeur (bouton « Restaurer »)">
						<I.Trash size={15} />Corbeille ({state?.corbeilleN ?? 0})</button>
					<button className="sr-pied-btn large" disabled={!state?.entree} onClick={() => openFolder(state?.entree)} title="Le dossier où arrivent les vidéos brutes (un dossier par lot)">
						<I.FolderOpen size={15} />Ouvrir le dossier Entrée</button>
				</div>
			</aside>
			<main className="sr-centre">
				{state && !items.length ? (
					<div className="sr-vide">
						<div className="sr-vide-cadre">
							<div className="sr-vide-ic"><I.Upload size={30} /></div>
							<h2>Dépose tes vidéos brutes ici</h2>
							<p>L'outil trouve le sujet, choisit les meilleurs passages et monte tout seul. Tu n'as qu'à regarder et accepter.</p>
							<div className="sr-vide-btns">
								<button className="sr-btn grand cyan" disabled={!!depot.progress} onClick={depot.choisirVideos}><I.FileVideo size={17} />Choisir des vidéos</button>
								<button className="sr-btn grand" disabled={!!depot.progress} onClick={depot.choisirDossier}><I.Folder size={17} />Choisir un dossier</button>
							</div>
							<span className="sr-muet">MP4, MOV · une vidéo par fichier, ou un dossier de prises + script</span>
						</div>
					</div>
				) : null}
				{!state && !offline ? <div className="sr-vide"><I.Loader size={28} className="tourne" /></div> : null}
				{item ? (
					<div className="sr-scene">
						<div className="sr-col-lecteur">
							{ready && reel && inputProps ? (
								<>
									<div className="sr-ecran" ref={lecteur} style={{'--ar': String(ar)} as React.CSSProperties}>
										<Player key={key} ref={player} component={Reel} inputProps={inputProps} durationInFrames={frames} fps={reel.fps}
											compositionWidth={reel.width} compositionHeight={reel.height} style={PLAYER_STYLE}
											controls={false} clickToPlay doubleClickToFullscreen spaceKeyToPlayOrPause={false} autoPlay
											// voix par plan (J/L-cuts) + musique + bruitages : plus de 5 sons peuvent jouer ensemble ; au-delà de la limite (5 par
											// défaut), le lecteur plantait et l'image devenait noire (vu à 0:19 sur Vidéo 1)
											numberOfSharedAudioTags={24} acknowledgeRemotionLicense />
										<PlayOverlay key={`o-${key}`} player={player} />
										{zone ? (
											// le cadre se place dans le rectangle de l'IMAGE (.rvc-image) : une video 16:9 dans un ecran etroit a des bandes
											<div className="rvc-cadre" aria-hidden style={{'--rvc-ar': String(reel.width / reel.height)} as React.CSSProperties}>
												<div className="rvc-image">
													<div key={zone.n} className="rvc-zone" style={{left: `${(100 * zone.box[0]) / reel.width}%`, top: `${(100 * zone.box[1]) / reel.height}%`,
														width: `${(100 * (zone.box[2] - zone.box[0])) / reel.width}%`, height: `${(100 * (zone.box[3] - zone.box[1])) / reel.height}%`}} />
												</div>
											</div>
										) : null}
									</div>
									<Transport key={`t-${key}`} player={player} fps={reel.fps} frames={frames} />
								</>
							) : (
								<div className="sr-ecran vide" style={{'--ar': String(9 / 16), background: fondDe(item.id)} as React.CSSProperties}>
									<span className="sr-ecran-label">Aperçu vidéo · 9:16</span>
									{item.status === 'erreur' ? <div className="sr-ecran-voile erreur"><I.FileX size={40} /></div> : null}
									{enCours ? (
										<div className="sr-ecran-voile">
											<div className="sr-ecran-ic"><I.Sparkles size={24} /></div>
											<b>{item.status === 'attente' ? 'En file d’attente' : 'Montage en cours…'}</b>
										</div>
									) : null}
									{ready && !reel ? <div className="sr-ecran-voile">{err ? <b className="sr-err">{err}</b> : <><I.Loader size={26} className="tourne" /><b>Ouverture du montage…</b></>}</div> : null}
								</div>
							)}
						</div>
						<div className="sr-col-infos">
							<div className="sr-infos">
								{claude.statut?.actif && (claude.statut.credit_epuise || claude.statut.espace_manquant) ? (
									// credit Anthropic epuise / cle sans espace de travail : Claude ne repond plus, tout continue en local
									<div className="cl-bandeau" role="alert"><I.TriangleAlert size={16} /><span>{claude.statut.raison || claude.statut.avertissement || 'Claude est en pause : l\'outil continue en local.'}</span></div>
								) : null}
								<div className="sr-tete">
									<h1>{label}</h1>
									<div className="sr-meta" title={item.reason ? `Pourquoi ce sujet : ${item.reason}` : undefined}>
										{ready && reel ? metaPrete : `Sujet : ${item.typeLabel ?? 'trouvé pendant le montage'} — ${item.lot}`}</div>
									{reel?.sobriete?.resume ? <div className="sr-meta petit" title="Relecture du monteur : un seul élément à la fois, rien sur l'accroche ; les éléments retirés restent en proposition dans « Modifier »">{reel.sobriete.resume}</div> : null}
									{ready && ligneClaude(item.claude) ? <div className="sr-meta petit cl-detail" title="Dépensé avec Claude pour cette vidéo (registre de l'éditeur)">{ligneClaude(item.claude)}</div> : null}
									{ready && ligneCerveau(reel) ? <div className="sr-meta petit cl-detail" title="Qui a choisi les mots forts, les cartes, le bandeau et le découpage de ce montage">{ligneCerveau(reel)}</div> : null}
								</div>
								{ready && reel ? (
									<>
										<div className="sr-actions">
											<button className={`sr-gros prendre${item.status === 'pris' ? ' prise' : ''}`} disabled={!peutPrendre} onClick={take}
												title={formats.length ? (item.status === 'pris' ? `Déjà prise : réexporter (${formats.join(', ')})` : `Un fichier par format : ${formats.join(', ')}`) : 'Coche au moins un format'}>
												{item.status === 'pris' && !exporting ? <I.CircleCheck size={18} /> : <I.Check size={18} strokeWidth={2.5} />}
												{exporting ? `Export ${pct} %…` : item.status === 'pris' ? 'Reprendre' : 'Je la prends'}<kbd className="sr-kbd">Entrée</kbd></button>
											<button className="sr-gros" disabled={!!busy} onClick={() => onEdit(key)} title="Ouvrir l'éditeur complet sur ce montage">
												<I.Pencil size={17} />Modifier<kbd className="sr-kbd">E</kbd></button>
											<button className={`sr-gros style${galerie ? ' on' : ''}`} disabled={!!busy && !galerie} onClick={() => setGalerie(!galerie)} aria-expanded={galerie}
												title="Choisir un autre style de montage"><I.Palette size={17} className="violet" />Autre style<kbd className="sr-kbd">S</kbd></button>
											<button className="sr-gros" onClick={next} title="Vidéo suivante à regarder">Suivante<I.ChevronRight size={17} /><kbd className="sr-kbd">→</kbd></button>
										</div>
										<div className="sr-formats" title="Formats exportés quand tu prends la vidéo : un fichier par format coché">
											<span className="sr-formats-titre">Formats d’export</span>
											{Object.keys(FORMATS).map((f) => {
												const on = formats.includes(f);
												const [w, h] = FORMAT_CADRE[f] ?? [10, 10];
												return (
													<button key={f} className={`sr-format${on ? ' on' : ''}`} aria-pressed={on} disabled={exporting || !!busy} onClick={() => toggleFormat(f)}
														title={`${f} : ${FORMAT_NAMES[f] ?? ''}`}>
														<span className="sr-coche">{on ? <I.Check size={11} strokeWidth={3} /> : null}</span>
														<span className="sr-cadre" style={{width: w, height: h}} />
														{FORMAT_LABEL[f] ?? f}
													</button>
												);
											})}
										</div>
										{!formats.length ? <p className="sr-flag">Coche au moins un format pour pouvoir prendre la vidéo.</p> : null}
										{formats.length && FORMATS[preview] && !formats.includes(preview) ? <p className="sr-muet">L'aperçu est en {preview} : coche {preview} pour avoir exactement ce que tu vois.</p> : null}
										{(() => {
											// ---- retouches par l'IA : demande libre (composant Consigne, monte par l'integrateur), Claude sur un clic ----
											const rCerveau = raisonIa('cerveau');
											const rCritique = raisonIa('critique');
											const eCerveau = estimationClaude(claude.statut, 'cerveau');
											const eCritique = estimationClaude(claude.statut, 'critique');
											const raisons = [...new Set([rCerveau, rCritique].filter(Boolean))];
											const r = iaResultat?.key === key ? iaResultat : null;
											const res = r?.result ?? {};
											return (
												<section className="sr-bloc cl-ia" aria-label="Retouches par l'IA">
													<div className="cl-ia-tete"><span className="sr-bloc-titre">Retouches par l'IA</span></div>
													{/* « Dis à l'IA ce que tu veux » (contrat « consigne ») : tempsLecteur = « ici » (temps du lecteur en s) ;
													    consigneAppliquee relit la liste et le montage (autre version créée -> montrée). */}
													{item.project && item.rid ? <Consigne project={item.project} version={item.rid} currentTime={tempsLecteur} onApplied={consigneAppliquee} /> : null}
													<div className="cl-ia-btns">
														<button className="sr-btn cl-btn" disabled={!!rCerveau} onClick={() => lancerIa('cerveau')}
															title={rCerveau || 'Claude refait les mots forts, les textes des cartes, le bandeau et le découpage (le montage actuel est gardé dans les versions)'}>
															🧠 Refaire avec Claude{eCerveau !== null ? <small>≈ {argent(eCerveau)}</small> : null}</button>
														<button className="sr-btn cl-btn" disabled={!!rCritique} onClick={() => lancerIa('critique')}
															title={rCritique || 'Claude regarde des images de la vidéo et donne son avis (note, problèmes avec leur moment) ; rien n\'est changé'}>
															👁 Critique Claude{eCritique !== null ? <small>≈ {argent(eCritique)}</small> : null}</button>
													</div>
													{raisons.length && !iaTourne ? <p className="sr-muet cl-raison">{raisons.join(' ')}</p> : null}
													{iaTourne ? <p className="cl-cours"><I.Loader size={14} className="tourne" />{iaJob?.stage}… (Claude répond en 10 à 60 s)</p> : null}
													{iaJob?.status === 'failed' && iaQuoi.current?.key === key ? <p className="sr-err">Claude : {iaJob.error}</p> : null}
													{/* cerveau : « raison » ; critique : « message » (vide quand Claude est eteint : la raison est dans « detail ») */}
													{r && res.ok === false ? <p className="sr-flag">Claude n'a pas servi : {String(res.message || res.raison || res.detail || 'raison inconnue')}</p> : null}
													{r && res.ok !== false ? (
														<div className="cl-fait">
															<I.CircleCheck size={15} />
															<span>{r.quoi === 'cerveau' ? 'Idées du montage refaites par Claude' : 'Avis de Claude ajouté au contrôle qualité'}
																{res.cache || res.source === 'garde' ? ' (déjà payé : gratuit cette fois)' : typeof res.cout === 'number' ? ` (${argent(res.cout)})` : ''}.
																{typeof res.resume === 'string' && res.resume ? ` ${res.resume}` : ''}</span>
															{r.quoi === 'cerveau' && typeof res.avantServeur === 'string' ? (
																<button className="sr-btn petit" disabled={!!busy} onClick={() => annulerIa(res.avantServeur)} title="Remettre le montage tel qu'il était avant Claude">
																	<I.Undo size={14} />Annuler</button>
															) : null}
														</div>
													) : null}
												</section>
											);
										})()}
										<ControlePanel rapports={rapports} choisi={onglet || ongletDefaut} onChoisir={setOnglet} reel={reel} busy={!!busy}
											relance={relance?.status === 'running' || relance?.status === 'queued'} relanceErreur={relance?.status === 'failed' ? relance.error || 'erreur inconnue' : ''}
											onRelancer={relancer} onVoir={voir} avis={avis} />
										{item.alerts?.length ? (
											<details className="sr-alerte">
												<summary>
													<I.FileText size={17} />
													<span>{item.alerts.length} phrase{item.alerts.length > 1 ? 's' : ''} du script {item.alerts.length > 1 ? 'ne sont' : 'n’est'} pas dans les prises (ou script non lu)</span>
													<button className="sr-lien orange" onClick={(e) => { e.preventDefault(); onEdit(key); }}>Voir dans le texte</button>
												</summary>
												<ul>{item.alerts.map((a, k) => <li key={k}>{a}</li>)}</ul>
											</details>
										) : null}
										{exportsList.length ? (
											<section className="sr-bloc sr-exports" aria-label="Exports">
												<div className="sr-bloc-titre">Exports</div>
												{exportsList.map((e) => (
													<div key={e.job} className={`sr-export ${e.status}`}>
														<div className="sr-export-ligne">
															<b className="sr-export-format" title={e.format}>{FORMAT_LABEL[e.format] ?? e.format}</b>
															{e.status === 'running' ? (
																<div className="sr-export-prog">
																	<div className="sr-barre"><div style={{width: `${Math.round(100 * (e.progress ?? 0))}%`}} /></div>
																	<span>{Math.round(100 * (e.progress ?? 0))} %</span>
																</div>
															) : null}
															{e.status === 'queued' ? <span className="sr-muet grow">En attente dans la file…</span> : null}
															{e.status === 'done' ? <span className="sr-export-ok grow"><I.CircleCheck size={15} />Terminé{e.seconds ? ` (${e.seconds} s)` : ''}</span> : null}
															{e.status === 'failed' ? <span className="sr-export-ko grow"><I.CircleX size={15} />Échec</span> : null}
															{e.status === 'cancelled' ? <span className="sr-export-ko jaune grow"><I.Ban size={15} />Annulé</span> : null}
															{e.status === 'interrompu' ? <span className="sr-export-ko jaune grow"><I.TriangleAlert size={15} />Interrompu</span> : null}
															{running(e) ? <button className="sr-btn petit" disabled={!!busy} onClick={() => cancelExport(e)}><I.Ban size={14} />Annuler</button> : null}
															{e.status === 'done' ? <button className="sr-btn petit" onClick={() => openFolder(e.out)}><I.ExternalLink size={14} />Ouvrir le dossier</button> : null}
															{e.status === 'done' ? (
																<button className="sr-btn petit" disabled={!!busy || !!e.controleEtat} onClick={() => controlerExport(e)}
																	title="Contrôle qualité de la vidéo livrée : images, détourage, lisibilité, son (environ 1 minute)">
																	<I.Search size={14} />{e.controleEtat ? 'Contrôle en cours…' : 'Contrôler l\'export'}</button>
															) : null}
														</div>
														{e.status === 'running' && e.stage ? <div className="sr-muet">{e.stage}</div> : null}
														{e.status === 'done' && (aNote(e.controle) || e.controleEtat) ? (
															<button className={`sr-export-qc ${aNote(e.controle) ? noteClasse(e.controle) : ''}`} onClick={() => setOnglet(`export:${e.job}`)}
																title="Voir les problèmes trouvés dans cette vidéo (carte Contrôle qualité)">
																{aNote(e.controle) ? <>Contrôle : <b>{virgule(e.controle.note)}/10</b> — {e.controle.verdict} ({compteTexte(e.controle.compte)})</>
																	: e.controleEtat === 'running' ? 'Contrôle qualité de la vidéo en cours…' : 'Contrôle qualité de la vidéo en attente…'}
															</button>
														) : null}
														{e.status === 'done' && e.controle && !aNote(e.controle) && !e.controleEtat ? <p className="sr-flag">Contrôle de la vidéo impossible : {e.controle.erreur}</p> : null}
														<div className="sr-chemin" title={e.out}>{e.status === 'done' ? 'Enregistrée : ' : 'Fichier : '}{e.out}</div>
														{e.status === 'failed' ? <p className="sr-err">{e.error || 'L\'export a échoué.'}</p> : null}
														{e.status === 'interrompu' ? <p className="sr-flag">Export interrompu (l'éditeur a redémarré) : clique « {item.status === 'pris' ? 'Reprendre' : 'Je la prends'} » pour le relancer.</p> : null}
													</div>
												))}
											</section>
										) : null}
										{item.status === 'pris' && item.taken && !exportsList.length ? (
											<section className="sr-bloc sr-exports">
												<div className="sr-export-ligne">
													<span className="sr-export-ok grow"><I.CircleCheck size={15} />Enregistrée : <span className="sr-chemin">{item.taken.out}</span></span>
													<button className="sr-btn petit" onClick={() => openFolder(item.taken!.out)}><I.ExternalLink size={14} />Ouvrir le dossier</button>
												</div>
											</section>
										) : null}
										<div className="sr-plus">
											<button className="sr-lien" disabled={!!busy || exporting} title={exporting ? 'Attends la fin de l\'export' : 'Enlever de la liste sans rien supprimer'} onClick={() => remove(item)}>
												<I.ListX size={14} />Retirer de la liste</button>
											<button className="sr-lien danger" disabled={!!busy} title={deleteBlock(item) || 'Montage et vidéos brutes vers la corbeille ; les vidéos exportées sont gardées'}
												onClick={() => supprimer(item)}><I.Trash size={14} />Supprimer</button>
										</div>
									</>
								) : null}
								{item.status === 'erreur' ? (
									<section className="sr-bloc sr-erreur">
										<div className="sr-erreur-ic"><I.FileX size={19} /></div>
										<div className="sr-erreur-corps">
											<b>Le montage s’est arrêté</b>
											<p>{item.error || 'Le montage a échoué.'}</p>
											<span className="sr-muet">Rien n’est perdu : tes vidéos brutes et ton script sont toujours là.</span>
											<div className="sr-erreur-btns">
												<button className="sr-btn moyen cyan" disabled={!!busy} onClick={() => act('Relance…', () => api(`/api/revision/${item.id}/refaire`, 'POST', {}).then(setState))}>
													<I.RotateCw size={15} />Refaire</button>
												<button className="sr-btn moyen" disabled={!unitPath(item)} onClick={() => openFolder(unitPath(item))} title="Le dossier des vidéos brutes de cette vidéo">
													<I.FolderOpen size={15} />Ouvrir le dossier</button>
											</div>
											<div className="sr-plus">
												<button className="sr-lien" disabled={!!busy} onClick={() => remove(item)} title="Enlever de la liste sans rien supprimer"><I.ListX size={14} />Retirer de la liste</button>
												<button className="sr-lien danger" disabled={!!busy} onClick={() => supprimer(item)} title="Vidéos brutes vers la corbeille (récupérables)"><I.Trash size={14} />Supprimer</button>
											</div>
										</div>
									</section>
								) : null}
								{enCours ? (
									<section className="sr-bloc sr-travail">
										<div className="sr-travail-tete">
											<span className="sr-travail-pct">{item.status === 'attente' ? '—' : `${Math.round(100 * (item.progress || 0))} %`}</span>
											<b>{item.status === 'attente' ? 'En file : commence dès que la vidéo précédente est finie' : item.stage || 'Montage en cours'}</b>
										</div>
										<div className="sr-barre epaisse"><div style={{width: `${Math.round(100 * (item.status === 'attente' ? 0 : item.progress || 0))}%`}} /></div>
										<ol className="sr-etapes">
											{ETAPES.map((s, k) => {
												const fait = item.status === 'travail' && k < etape;
												const cur = item.status === 'travail' && k === etape;
												return (
													<li key={s.label} className={fait ? 'fait' : cur ? 'cur' : ''}>
														<span className="sr-etape-rond">{fait ? <I.Check size={12} strokeWidth={3} /> : cur ? <I.Loader size={12} className="tourne" /> : null}</span>{s.label}
													</li>
												);
											})}
										</ol>
										<span className="sr-muet">Tu peux continuer à réviser les autres vidéos pendant ce temps.</span>
										{item.status === 'attente' ? (
											<div className="sr-plus">
												<button className="sr-lien" disabled={!!busy} onClick={() => remove(item)}><I.ListX size={14} />Retirer de la liste</button>
												<button className="sr-lien danger" disabled={!!busy} onClick={() => supprimer(item)}><I.Trash size={14} />Supprimer</button>
											</div>
										) : null}
									</section>
								) : null}
							</div>
							{galerie && ready && reel ? (
								<Galerie templates={templates.filter((t) => (speech ? !['immobilier', 'evenement'].includes(t.id) : true))} current={reel.template} item={item} reel={reel}
									reelKey={key} busy={!!busy} types={types} onApply={applyStyle} onRetour={retourStyle} onPin={pinStyle} onClose={() => setGalerie(false)}
									onTemplates={onTemplates} onSaved={async (t) => {
										await onTemplates();
										setOpened((o) => (o ? {...o, reel: {...o.reel, template: t.id}} : o));
									}} />
							) : null}
						</div>
					</div>
				) : null}
				<div className="sr-messages" aria-live="polite">
					{busy ? <div className="sr-message busy"><I.Loader size={16} className="tourne" /><div>{busy}</div></div> : null}
					{notice ? <div className="sr-message ok"><I.CircleCheck size={16} /><div>{notice}</div><button className="sr-icone" onClick={() => setNotice('')} aria-label="Fermer"><I.X size={14} /></button></div> : null}
					{err ? <div className="sr-message err"><I.CircleX size={16} /><div>{err}</div><button className="sr-icone" onClick={() => setErr('')} aria-label="Fermer"><I.X size={14} /></button></div> : null}
				</div>
			</main>
		</div>
	);
};
