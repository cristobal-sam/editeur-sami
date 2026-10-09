// « Dis à l'IA ce que tu veux changer » — FICHIER DU GROUPE « consigne » (contrat « consigne »).
// L'integrateur le monte dans la Revision et dans l'editeur : <Consigne project version currentTime onApplied />.
// Route : POST /api/reels/<p>/<v>/consigne {texte, t?} -> tache (useJob) ; resultat = la ligne JSON du moteur
// (engine/editeur/consigne.py : version, avant, changements, refus, question, moteur, cout, note_ajoutee).
// Historique : reel.consignes, relu par GET /api/reels/<p>/<v>/open (jamais envoye au lecteur ni a l'export).
// « Annuler ce changement » : POST /api/reels/<p>/<version>/restore {file: avant} (copie exacte d'avant la demande) ;
// declinaison (nouvelle version) : avant = id de l'originale -> onApplied(avant), l'originale n'a pas change.
// Etat de Claude (pret, modele, cout estime) : GET /api/claude (jamais la cle). Styles : bloc CSS de ce fichier (cg-*),
// couleurs de la Revision (--sr-*) avec repli sur celles de l'editeur (--panel, --accent...). Raccourci : Ctrl+Entree.
import React from 'react';
import {api, fmt, useJob} from './api';

type Changement = {quoi: string; detail: string; t?: number};
type Refus = {demande: string; raison: string};
/** Ligne JSON du moteur (contrat « consigne »). */
type Resultat = {ok: boolean; version: string; avant: string | null; changements: Changement[]; refus: Refus[]; question: string | null;
	moteur: 'claude' | 'local' | 'regles' | null; cout: number; note_ajoutee: boolean; reponse?: string; remarques?: string[];
	modifie?: boolean; simule?: boolean; erreur?: string};
/** Une demande de l'historique (reel.consignes). */
type Entree = {date: string; texte: string; t: number | null; moteur: string; cout: number; reponse?: string; changements: Changement[];
	refus: Refus[]; question: string | null; avant?: string | null; version?: string; note_ajoutee?: boolean};
type Statut = {pret?: boolean; raison?: string; modele?: string; nom_modele?: string; estimation?: {consigne?: number};
	espace_manquant?: boolean; credit_epuise?: boolean;
	modeles_taches?: {consigne?: string | null}; modeles?: {id: string; nom: string}[]};

export type ConsigneProps = {
	/** Projet (dossier de projects/). */
	project: string;
	/** Version du reel (script, v1, v1-30-s...). */
	version: string;
	/** Instant de la tete de lecture (s, temps du montage) : « ici ». */
	currentTime: number;
	/** Le moteur a enregistre un changement : relire ce reel (ou ouvrir la nouvelle version d'une declinaison). */
	onApplied: (newVersion: string) => void;
};

const EXEMPLES = ['Mets les sous-titres en jaune', 'La musique est trop forte', 'Moins de bruitages', 'Enlève la carte ici'];
const AIDE = 'Ex. : « mets les sous-titres en jaune », « enlève la carte à 0:12 », « la musique est trop forte », '
	+ '« coupe le bout où je bégaie ici », « change le texte du bandeau pour … », « fais-en une version de 30 secondes »';
const MAX = 800; // meme limite que le serveur et le moteur
const tc = (s: number) => fmt(Math.max(0, s)).replace('.', ',');
const argent = (x: number) => (!x ? 'gratuit' : x < 0.01 ? 'moins de 0,01 $' : `${x.toFixed(2).replace('.', ',')} $`);
// Claude essaye puis abandonne (reponse coupee, illisible...) : ce qu'il a coute est dit, meme si l'IA locale a fini le travail
const badge = (moteur: string | null | undefined, cout: number) => moteur === 'claude' ? `🧠 Claude · ${argent(cout)}`
	: moteur === 'local' || moteur === 'regles' ? `${moteur === 'local' ? '💻 Local' : '📏 Règles simples'} · ${cout > 0 ? `gratuit (Claude essayé : ${argent(cout)})` : 'gratuit'}` : '';
/** Message du serveur ou du moteur sans l'emballage technique ; ancien serveur (route absente) : dire quoi faire. */
const lisible = (msg: string) => {
	if (['Introuvable.', 'Action inconnue.'].includes(msg.trim())) return 'La boîte « Dis à l’IA » arrive avec la mise à jour de l’éditeur : ferme puis rouvre « Editeur Sami », puis réessaie.';
	return msg.replace(/^Erreur inattendue : /, '').replace(/\s*\(d[ée]tails dans runtime\/cache\/erreurs\.log\)\s*$/, '').trim() || 'La demande a échoué.';
};
/** « avant » d'une declinaison = id de l'originale (pas un fichier de versions/). */
const estFichier = (avant: string) => avant.endsWith('.json');

const CSS = `
.cg { --cg-texte: var(--sr-texte, var(--text, #e9e9ea)); --cg-muet: var(--sr-muet, var(--muted, #9a9ca3)); --cg-ligne: var(--sr-ligne2, var(--line, #2a2c31));
  --cg-fond: var(--sr-fond-carte, var(--panel, #17181b)); --cg-accent: var(--sr-cyan, var(--accent, #ffd400)); --cg-encre: var(--sr-encre, var(--accent-ink, #111));
  display: flex; flex-direction: column; gap: 10px; color: var(--cg-texte); font-size: 13px; min-height: 0; }
.cg-tete { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.cg-tete b { font-size: 14px; }
.cg-etat { color: var(--cg-muet); font-size: 12px; }
.cg-fil { display: flex; flex-direction: column; gap: 8px; max-height: 340px; overflow-y: auto; padding-right: 2px; }
.cg-moi { align-self: flex-end; max-width: 88%; background: rgba(255,255,255,0.07); border: 1px solid var(--cg-ligne); border-radius: 12px 12px 3px 12px;
  padding: 7px 10px; white-space: pre-wrap; overflow-wrap: anywhere; }
.cg-moi small { display: block; color: var(--cg-muet); font-size: 11px; margin-top: 2px; }
.cg-ia { align-self: flex-start; max-width: 94%; background: rgba(56,225,255,0.06); border: 1px solid rgba(56,225,255,0.18); border-radius: 12px 12px 12px 3px;
  padding: 8px 10px; display: flex; flex-direction: column; gap: 5px; }
.cg-ia ul { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 2px; }
.cg-ia li { line-height: 1.35; }
.cg-question { color: #FDE68A; font-weight: 600; }
.cg-refus { color: #FDBA74; }
.cg-err { color: #FCA5A5; white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; }
.cg-ok { color: #6EE7B7; margin: 0; }
.cg-badge { align-self: flex-start; font-size: 11px; color: var(--cg-muet); border: 1px solid var(--cg-ligne); border-radius: 999px; padding: 1px 8px; }
.cg-pied { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cg textarea { width: 100%; min-height: 64px; resize: vertical; background: rgba(255,255,255,0.04); color: var(--cg-texte); border: 1px solid var(--cg-ligne);
  border-radius: 10px; padding: 8px 10px; font: inherit; line-height: 1.4; }
.cg textarea:focus { outline: none; border-color: var(--cg-accent); }
.cg-puces { display: flex; gap: 6px; flex-wrap: wrap; }
.cg-puce { font-size: 12px; padding: 3px 9px; border-radius: 999px; border: 1px solid var(--cg-ligne); background: rgba(255,255,255,0.04); color: var(--cg-texte); cursor: pointer; }
.cg-puce:hover:not(:disabled) { border-color: var(--cg-accent); background: rgba(255,255,255,0.08); }
.cg-ici { display: inline-flex; align-items: center; gap: 5px; color: var(--cg-muet); font-size: 12px; cursor: pointer; }
.cg-envoyer, .cg-envoyer:hover:not(:disabled) { background: var(--cg-accent); color: var(--cg-encre); border: none; border-radius: 9px; padding: 6px 14px; font-weight: 700; cursor: pointer; }
.cg-envoyer:disabled { opacity: .45; cursor: default; }
.cg-annuler { align-self: flex-start; font-size: 12px; padding: 2px 9px; border-radius: 8px; border: 1px solid var(--cg-ligne); background: transparent; color: var(--cg-texte); cursor: pointer; }
.cg-annuler:hover:not(:disabled) { border-color: rgba(248,113,113,0.5); background: rgba(248,113,113,0.08); }
.cg-travail { color: var(--cg-muet); display: flex; align-items: center; gap: 6px; }
.cg-travail::before { content: ''; width: 10px; height: 10px; border-radius: 50%; border: 2px solid var(--cg-accent); border-right-color: transparent; animation: cg-tourne 0.9s linear infinite; }
@keyframes cg-tourne { to { transform: rotate(360deg); } }
`;

/** Reponse de l'IA : ce qui a ete fait, ce qui ne l'a pas ete (avec la raison), la question, le moteur et le cout. */
const Reponse: React.FC<{e: Pick<Entree, 'reponse' | 'changements' | 'refus' | 'question' | 'moteur' | 'cout'> & {note?: boolean; remarques?: string[]};
	annuler?: () => void; annulable?: string; occupe: boolean}> = ({e, annuler, annulable, occupe}) => (
	<div className="cg-ia">
		{e.question ? <div className="cg-question">❓ {e.question}</div> : null}
		{e.reponse && !e.question ? <div>{e.reponse}</div> : null}
		{e.changements?.length ? (
			<ul>
				{e.changements.slice(0, 12).map((c, i) => <li key={i}>{c.t !== undefined ? <span className="cg-etat">{tc(c.t)} · </span> : null}{c.detail}</li>)}
				{e.changements.length > 12 ? <li className="cg-etat">… et {e.changements.length - 12} autre(s).</li> : null}
			</ul>
		) : !e.question && !e.refus?.length ? <div className="cg-etat">Rien à changer.</div> : null}
		{e.refus?.length ? (
			<ul className="cg-refus">
				{e.refus.map((r, i) => <li key={i}>Pas fait : {r.demande}{r.raison ? ` — ${r.raison}` : ''}</li>)}
			</ul>
		) : null}
		{e.note ? <div className="cg-etat">📝 Une note est laissée dans l’onglet Notes pour ce qui n’a pas été fait.</div> : null}
		{(e.remarques ?? []).filter((r) => !/^Temps du lecteur/.test(r)).slice(0, 2).map((r, i) => <div key={i} className="cg-etat">{r}</div>)}
		<span className="cg-badge">{badge(e.moteur, e.cout)}</span>
		{annuler ? (
			<button className="cg-annuler" disabled={occupe} title={annulable} onClick={annuler}>↶ Annuler ce changement</button>
		) : null}
	</div>
);

export const Consigne: React.FC<ConsigneProps> = ({project, version, currentTime, onApplied}) => {
	const cle = `${encodeURIComponent(project)}/${encodeURIComponent(version)}`;
	const [historique, setHistorique] = React.useState<Entree[]>([]);
	const [texte, setTexte] = React.useState('');
	const [ici, setIci] = React.useState(true);
	const [err, setErr] = React.useState('');
	const [info, setInfo] = React.useState('');
	const [dernier, setDernier] = React.useState<Resultat | null>(null);
	// demande envoyee (gardee jusqu'a ce que l'historique relu la contienne), longueur de l'historique et date de sa
	// derniere entree a l'envoi (historique plein, 50 demandes : la longueur ne bouge plus, la date si)
	const [envoye, setEnvoye] = React.useState<{texte: string; t: number | null; n: number; date?: string} | null>(null);
	const [statut, setStatut] = React.useState<Statut | null>(null);
	const [annulation, setAnnulation] = React.useState(false);
	const [debut, setDebut] = React.useState(0);
	const [now, setNow] = React.useState(0);
	const fil = React.useRef<HTMLDivElement>(null);
	const applied = React.useRef(onApplied);
	applied.current = onApplied;

	const relire = React.useCallback(async () => {
		try {
			const d = await api(`/api/reels/${cle}/open`);
			const h = d?.reel?.consignes;
			setHistorique(Array.isArray(h) ? h.filter((x: unknown) => x && typeof x === 'object') : []);
		} catch {
			setHistorique([]);
		}
	}, [cle]);
	const [job, setJob] = useJob((j) => {
		const r = j.result as Resultat;
		setDernier(r);
		void relire();
		if (r?.ok && (r.modifie || r.version !== version)) applied.current(r.version || version);
	});
	const enCours = job?.status === 'running' || job?.status === 'queued';
	const echec = job?.status === 'failed' ? lisible(job.error || 'La demande a échoué.') : '';
	// la reponse arrivee est deja dans l'historique relu (meme reel) : elle n'est pas montree une 2e fois
	const derniere = historique[historique.length - 1];
	const dansHistorique = !!envoye && !enCours && derniere?.texte === envoye.texte && (historique.length > envoye.n || derniere.date !== envoye.date);

	// une autre video : historique relu, le reste oublie
	React.useEffect(() => {
		setDernier(null);
		setErr('');
		setInfo('');
		setEnvoye(null);
		setJob(null);
		void relire();
	}, [cle]);
	// etat de Claude (pret ? modele, cout estime) : une fois ; jamais bloquant
	React.useEffect(() => {
		let vivant = true;
		fetch('/api/claude').then((r) => (r.ok ? r.json() : null)).then((s) => vivant && setStatut(s)).catch(() => {});
		return () => {
			vivant = false;
		};
	}, []);
	React.useEffect(() => {
		if (!enCours) return;
		const id = window.setInterval(() => setNow(Date.now()), 500);
		return () => window.clearInterval(id);
	}, [enCours]);
	React.useEffect(() => {
		fil.current?.scrollTo({top: fil.current.scrollHeight});
	}, [historique.length, enCours, dernier, echec, info]);

	const t = Number.isFinite(currentTime) ? Math.max(0, currentTime) : 0;
	const propre = texte.trim();
	const trop = propre.length > MAX;

	const envoyer = async (demande = propre) => {
		const d = demande.trim();
		if (!d || d.length > MAX || enCours || annulation) return;
		setErr('');
		setInfo('');
		setDernier(null);
		setDebut(Date.now());
		setNow(Date.now());
		const quand = ici ? +t.toFixed(3) : null;
		setEnvoye({texte: d, t: quand, n: historique.length, date: historique[historique.length - 1]?.date});
		try {
			setJob(await api(`/api/reels/${cle}/consigne`, 'POST', quand === null ? {texte: d} : {texte: d, t: quand}));
			setTexte('');
		} catch (e) {
			setEnvoye(null);
			setErr(lisible((e as Error).message));
		}
	};

	const annuler = async (e: {avant?: string | null; version?: string; texte: string}, plusRecent: boolean) => {
		if (!e.avant || annulation || enCours) return;
		if (!plusRecent && !window.confirm('Annuler ce changement remet le montage comme avant cette demande : les changements demandés après seront aussi annulés. Continuer ?')) return;
		setErr('');
		setInfo('');
		if (!estFichier(e.avant)) {
			// declinaison : l'originale n'a jamais change ; on y retourne (la nouvelle version reste dans la liste)
			applied.current(e.avant);
			setInfo(`Retour à la version d’origine (« ${e.avant} ») ; la version créée reste disponible dans la liste.`);
			return;
		}
		setAnnulation(true);
		try {
			await api(`/api/reels/${encodeURIComponent(project)}/${encodeURIComponent(e.version || version)}/restore`, 'POST', {file: e.avant});
			setDernier(null);
			setEnvoye(null);
			setInfo(`Changement annulé : le montage est revenu exactement comme avant « ${e.texte.slice(0, 60)}${e.texte.length > 60 ? '…' : ''} ».`);
			await relire();
			applied.current(e.version || version);
		} catch (x) {
			setErr(lisible((x as Error).message));
		} finally {
			setAnnulation(false);
		}
	};

	const secondes = enCours ? Math.max(0, Math.round((now - debut) / 1000)) : 0;
	const derniereAnnulable = [...historique].reverse().find((h) => h.avant)?.avant;
	// modele de cette tache (reglage modeles_taches.consigne, sinon le modele general) ; l'estimation vaut pour le modele general
	const propreModele = statut?.modeles_taches?.consigne && statut.modeles_taches.consigne !== statut.modele ? statut.modeles_taches.consigne : null;
	const nomModele = propreModele ? statut?.modeles?.find((m) => m.id === propreModele)?.nom ?? propreModele : statut?.nom_modele;
	const estimation = propreModele ? 0 : statut?.estimation?.consigne ?? 0;
	// cle refusee au dernier appel (espace de travail manquant, credit epuise) : ne pas afficher « prêt » ; l'IA locale prendra le relais
	const etatClaude = statut ? (statut.pret && (statut.espace_manquant || statut.credit_epuise)
		? `⚠ Claude bloqué (${statut.espace_manquant ? 'espace de travail manquant, voir ⚙️' : 'crédit épuisé'}) : l'IA locale répondra, gratuitement`
		: statut.pret ? `🧠 Claude prêt${nomModele ? ` (${nomModele})` : ''}${estimation ? ` · environ ${argent(estimation)} par demande` : ''}`
		: `💻 En local (gratuit)${statut.raison ? ` : ${statut.raison.replace(/\s*L'outil continue en local\.?$/, '')}` : ''}`) : '';

	return (
		<div className="cg">
			<style>{CSS}</style>
			<div className="cg-tete">
				<b>💬 Dis à l’IA ce que tu veux changer</b>
				{etatClaude ? <span className="cg-etat" title={statut?.raison || ''}>{etatClaude}</span> : null}
			</div>
			{historique.length || enCours || envoye || dernier || echec || err || info ? (
				<div className="cg-fil" ref={fil} aria-live="polite">
					{historique.map((h, i) => (
						<React.Fragment key={`${h.date}-${i}`}>
							<div className="cg-moi">{h.texte}{typeof h.t === 'number' ? <small>à {tc(h.t)}</small> : null}</div>
							<Reponse e={{...h, note: !!h.note_ajoutee}} occupe={enCours || annulation}
								annuler={h.avant ? () => annuler(h, h.avant === derniereAnnulable) : undefined}
								annulable={h.avant && estFichier(h.avant) ? 'Remet le montage exactement comme avant cette demande (une version « avant restauration » est gardée).'
									: 'Retourne à la version d’origine (elle n’a pas changé).'} />
						</React.Fragment>
					))}
					{envoye && !dansHistorique ? <div className="cg-moi">{envoye.texte}{envoye.t !== null ? <small>à {tc(envoye.t)}</small> : null}</div> : null}
					{enCours ? (
						<div className="cg-travail" role="status">L’IA travaille… {secondes} s{secondes > 10 ? ' (l’IA locale peut prendre jusqu’à une minute pour démarrer ; un changement de style ou une version courte prend plus longtemps)' : ''}</div>
					) : null}
					{dernier && !enCours && !dansHistorique ? (
						<Reponse e={{...dernier, moteur: dernier.moteur ?? '', note: dernier.note_ajoutee}} occupe={enCours || annulation}
							annuler={dernier.avant ? () => annuler({avant: dernier.avant, version: dernier.version, texte: envoye?.texte || 'ta demande'}, true) : undefined} />
					) : null}
					{echec || err ? <p className="cg-err">{echec || err}</p> : null}
					{info ? <p className="cg-ok">{info}</p> : null}
				</div>
			) : null}
			<textarea value={texte} maxLength={MAX + 200} placeholder={AIDE} disabled={enCours} aria-label="Ta demande à l’IA"
				onChange={(e) => setTexte(e.target.value)}
				onKeyDown={(e) => {
					if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
						e.preventDefault();
						e.stopPropagation();
						void envoyer();
					} else e.stopPropagation(); // les raccourcis de la Revision / de l'editeur (E, S, Espace...) ne partent pas pendant la saisie
				}} />
			<div className="cg-puces">
				{EXEMPLES.map((x) => (
					<button key={x} className="cg-puce" disabled={enCours} title="Écrire cet exemple (tu peux le modifier avant d’envoyer)" onClick={() => setTexte(x)}>{x}</button>
				))}
			</div>
			<div className="cg-pied">
				<label className="cg-ici" title="« ici », « là », « ce bout-là » = l’endroit où est la lecture">
					<input type="checkbox" checked={ici} onChange={(e) => setIci(e.target.checked)} /> à partir d’ici ({tc(t)})
				</label>
				<span style={{flex: 1}} />
				{trop ? <span className="cg-err">{propre.length} / {MAX} caractères</span> : null}
				<button className="cg-envoyer" disabled={!propre || trop || enCours || annulation} title="Envoyer (Ctrl+Entrée)" onClick={() => void envoyer()}>
					{enCours ? 'L’IA travaille…' : 'Envoyer'}
				</button>
			</div>
		</div>
	);
};

export default Consigne;
