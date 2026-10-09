// Contrat commun des composants V2 (notes, banque, vecteurs, choregraphie, passage) : App.tsx leur passe toujours ces
// proprietes. Fichier de l'architecte (docs/direction-creative-v2/SPEC.md) : les agents l'importent, ne le modifient pas.
import type {ReelDoc} from '../../remotion/src/types';

/** Toute modification du reel : historique (Ctrl+Z) + sauvegarde automatique (PUT, champs EDITABLE). */
export type Update = (fn: (r: ReelDoc) => ReelDoc) => void;

export type V2Props = {
	/** Montage courant (celui de l'editeur, jamais la version B d'une comparaison). */
	reel: ReelDoc;
	/** Instant de la tete de lecture (s, temps du montage). */
	t: number;
	/** Format affiche : '9:16' | '16:9' | '4:5' | '1:1' (ou `LxH`). */
	format: string;
	update: Update;
	/** Aller a l'instant s du montage. */
	seek: (s: number) => void;
	/** Mettre le lecteur en pause (avant de dessiner ou d'ecrire une note). */
	pause: () => void;
	/** Cle du reel « projet/version » pour les routes /api/reels/<cle>/... */
	current: string;
	/** Relire le reel tel que le moteur l'a enregistre (apres une tache : choregraphie, passage...). */
	reload: () => void;
};

/** Plage choisie pour « Refaire seulement ce passage » (temps du montage), partagee par App, la timeline et passage.tsx. */
export type PassageRange = {debut: number; fin: number} | null;
