// Verrou commun a tous les elements (graphismes, scenes du style, plans de coupe, bruitages, vecteurs, bandeau, plan
// creatif, mouvements de la choregraphie). Un element verrouille (locked) ou retouche a la main (manual / edited) n'est
// jamais modifie ni retire par une passe automatique : changement de style, relecture du monteur, IA, choregraphie,
// « Refaire ce passage » (moteur : engine/editeur/verrous.py).
import React from 'react';

/** Copie de l'element avec le verrou pose ou retire (le champ disparait quand il est retire). */
export const withLock = <T extends object>(item: T, locked: boolean): T => {
	const {locked: _old, ...rest} = item as T & {locked?: boolean};
	return (locked ? {...rest, locked: true} : rest) as T;
};

/** Copie de l'element marquee « retouche a la main » : protegee comme un verrou, sans cadenas visible. */
export const touched = <T extends object>(item: T): T => ({...item, manual: true});

export const isLocked = (item: {locked?: boolean} | null | undefined) => !!item?.locked;

/** Bouton cadenas : clic = verrouiller / deverrouiller. */
export const LockToggle: React.FC<{locked?: boolean; onChange: (locked: boolean) => void; label?: boolean; title?: string}> = ({locked, onChange, label, title}) => (
	<button type="button" className={`small lock${locked ? ' on' : ''}`} aria-pressed={!!locked}
		title={title ?? (locked ? 'Verrouillé : l’IA et les changements de style n’y touchent plus. Clique pour déverrouiller.'
			: 'Verrouiller : l’IA et les changements de style n’y toucheront plus.')}
		onClick={(e) => { e.stopPropagation(); onChange(!locked); }}>
		{locked ? '🔒' : '🔓'}{label ? (locked ? ' Verrouillé' : ' Verrouiller') : null}
	</button>
);
