// Ecrit les fiches assets/banque/vecteurs/<nom>.json a partir de la table ci-dessous (agent « vecteurs »).
//   node docs/direction-creative-v2/tests/vecteurs/ecrire-fiches.mjs
// Les couleurs d'origine, la presence de traits a dessiner (« trace ») et l'animation en boucle sont LUES dans le SVG :
// la fiche ne peut pas contredire le dessin. Format de la fiche : SPEC §9.1 (+ champs facultatifs documentes dans
// assets/banque/vecteurs/LISEZMOI.txt).
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DIR = path.resolve(HERE, '../../../../assets/banque/vecteurs');
const LICENCE = "Création originale de l'Éditeur Sami — usage libre, y compris commercial";
const PROVENANCE = "Dessin vectoriel écrit à la main pour ce projet (assets/banque/vecteurs), 30 septembre 2026 ; aucune ressource externe, aucun téléchargement.";

// nom de fichier : [titre, categorie, mots-cles, intensite 1-3, entree, sortie, duree (s), largeur (part de l'image), description, options]
const TABLE = {
	'fleche': ['Flèche droite', 'flèches', ['flèche', 'pointer', 'montrer', 'direction', 'droite', 'regarder'], 2, 'glisse-gauche', 'fondu', 2, 0.35, 'Flèche pleine qui pointe vers la droite.'],
	'fleche-courbe': ['Flèche courbe', 'flèches', ['flèche', 'courbe', 'pointer', 'montrer', 'regarde ici'], 2, 'trace', 'fondu', 2.2, 0.4, 'Flèche en arc qui se dessine pour désigner un détail.'],
	'fleche-main': ['Flèche dessinée à la main', 'flèches', ['flèche', 'main', 'croquis', 'boucle', 'pointer', 'regarde'], 2, 'trace', 'fondu', 2.4, 0.45, 'Flèche au crayon avec une boucle, qui se dessine.'],
	'fleche-bas': ['Flèche vers le bas', 'flèches', ['flèche', 'bas', 'lien', 'cliquer', 'description', 'en dessous'], 2, 'glisse-haut', 'fondu', 2.5, 0.2, 'Flèche qui rebondit vers le bas (« lien en description »).'],
	'cercle': ['Cercle', 'entourer', ['entourer', 'cercle', 'attention', 'détail', 'rond'], 1, 'trace', 'fondu', 2, 0.45, 'Cercle net qui se dessine autour d’un détail.'],
	'cercle-griffonne': ['Cercle griffonné', 'entourer', ['entourer', 'griffonné', 'main', 'croquis', 'important'], 2, 'trace', 'fondu', 2.2, 0.55, 'Cercle au crayon, fait vite à la main.'],
	'soulignement': ['Soulignement', 'entourer', ['souligner', 'trait', 'important', 'mot', 'phrase'], 1, 'trace', 'fondu', 2, 0.6, 'Double trait de soulignement qui se dessine.'],
	'surligneur': ['Trait de surligneur', 'entourer', ['surligner', 'surligneur', 'marqueur', 'mot clé', 'fluo'], 1, 'trace', 'fondu', 2, 0.6, 'Bande de surligneur transparente, à poser sur un mot.'],
	'encadre': ['Encadré', 'entourer', ['encadrer', 'cadre', 'boîte', 'prix', 'important', 'offre'], 1, 'trace', 'fondu', 2.2, 0.7, 'Rectangle arrondi qui se dessine autour d’un prix ou d’une offre.'],
	'crochets': ['Crochets', 'entourer', ['crochets', 'cadrer', 'mettre en valeur', 'citation'], 1, 'trace', 'fondu', 2, 0.6, 'Deux crochets qui encadrent un élément.'],
	'coins-cadre': ['Coins de cadre', 'entourer', ['cadre', 'viseur', 'coins', 'mise au point', 'focus'], 1, 'zoom', 'fondu', 2, 0.7, 'Quatre coins de viseur pour faire le point sur un détail.'],
	'explosion': ['Explosion de BD', 'impact', ['explosion', 'bd', 'bam', 'impact', 'choc', 'wow'], 3, 'pop', 'zoom', 1.2, 0.5, 'Explosion de bande dessinée pour un moment choc.'],
	'eclair': ['Éclair', 'impact', ['éclair', 'énergie', 'rapide', 'puissance', 'choc'], 3, 'pop', 'fondu', 1.2, 0.25, 'Éclair plein : énergie, vitesse.'],
	'bulle': ['Bulle de parole', 'impact', ['bulle', 'parole', 'dialogue', 'message', 'commentaire'], 2, 'pop', 'pop', 2, 0.4, 'Bulle de BD avec trois points (quelqu’un écrit).'],
	'attention': ['Panneau attention', 'impact', ['attention', 'danger', 'erreur', 'alerte', 'prudence'], 3, 'pop', 'fondu', 1.6, 0.3, 'Triangle d’avertissement.'],
	'etoile': ['Étoile', 'fête', ['étoile', 'note', 'avis', 'qualité', '5 étoiles'], 2, 'pop', 'pop', 1.6, 0.25, 'Étoile pleine (avis, qualité).'],
	'etincelles': ['Étincelles', 'fête', ['étincelles', 'brillant', 'magie', 'nouveau', 'propre'], 2, 'zoom', 'fondu', 1.8, 0.3, 'Trois étincelles qui scintillent.'],
	'confettis': ['Confettis', 'fête', ['confettis', 'fête', 'bravo', 'succès', 'célébrer'], 3, 'pop', 'fondu', 2, 0.6, 'Confettis pour célébrer un résultat.'],
	'coeur': ['Cœur', 'fête', ['cœur', 'amour', 'j’aime', 'like', 'favori'], 2, 'pop', 'pop', 1.6, 0.25, 'Cœur qui bat doucement.'],
	'coche': ['Case cochée', 'validation', ['coche', 'validé', 'oui', 'inclus', 'correct', 'vert'], 2, 'trace', 'fondu', 1.6, 0.22, 'Case verte dont la coche se dessine (✅).', {garderCouleurs: true}],
	'croix': ['Croix', 'validation', ['croix', 'non', 'faux', 'erreur', 'à éviter', 'rouge'], 2, 'trace', 'fondu', 1.6, 0.22, 'Rond rouge dont la croix se dessine (❌).', {garderCouleurs: true}],
	'pouce': ['Pouce levé', 'validation', ['pouce', 'like', 'approuvé', 'bien', 'super'], 2, 'pop', 'pop', 1.6, 0.25, 'Pouce levé : approuvé.'],
	'badge': ['Badge sceau', 'étiquettes', ['badge', 'sceau', 'garanti', 'certifié', 'qualité', 'nouveau'], 2, 'zoom', 'fondu', 2, 0.3, 'Sceau dentelé qui tourne lentement.'],
	'note-autocollante': ['Note autocollante', 'étiquettes', ['note', 'post-it', 'rappel', 'mémo', 'autocollant'], 1, 'pop', 'fondu', 2, 0.35, 'Petite note collée avec un bout de ruban.'],
	'ruban-adhesif': ['Ruban adhésif', 'étiquettes', ['ruban', 'scotch', 'collé', 'photo', 'coller'], 1, 'pop', 'fondu', 2, 0.35, 'Bout de ruban adhésif déchiré.'],
	'etiquette-prix': ['Étiquette de prix', 'étiquettes', ['prix', 'étiquette', 'promo', 'solde', 'rabais', 'coût'], 2, 'glisse-droite', 'fondu', 2, 0.4, 'Étiquette de prix avec sa ficelle.'],
	'cloche': ['Cloche de notification', 'icônes', ['cloche', 'notification', 'alerte', 'abonne-toi', 'rappel'], 2, 'pop', 'fondu', 2, 0.25, 'Cloche qui sonne, avec sa pastille de notification.'],
	'telephone': ['Cadre de téléphone', 'icônes', ['téléphone', 'cellulaire', 'application', 'écran', 'mobile'], 1, 'zoom', 'fondu', 3, 0.5, 'Contour de téléphone : l’écran reste transparent.'],
	'graphique-hausse': ['Graphique en hausse', 'graphiques', ['graphique', 'hausse', 'croissance', 'ventes', 'résultats', 'plus'], 2, 'trace', 'fondu', 2.4, 0.45, 'Barres et flèche qui monte en se dessinant.'],
	'graphique-baisse': ['Graphique en baisse', 'graphiques', ['graphique', 'baisse', 'perte', 'chute', 'moins', 'coûts'], 2, 'trace', 'fondu', 2.4, 0.45, 'Barres et flèche qui descend en se dessinant.'],
	'horloge': ['Horloge', 'icônes', ['horloge', 'temps', 'heure', 'rapide', 'délai', 'attente'], 1, 'pop', 'fondu', 2, 0.25, 'Horloge ronde (temps, délai).'],
	'argent': ['Argent', 'icônes', ['argent', 'billet', 'dollar', 'prix', 'économies', 'payer'], 2, 'pop', 'fondu', 2, 0.35, 'Billet et pièce de monnaie.'],
	'cible': ['Cible', 'icônes', ['cible', 'objectif', 'précision', 'client idéal', 'but'], 2, 'zoom', 'fondu', 2, 0.3, 'Cible avec une fléchette au centre.'],
	'guillemets': ['Guillemets de citation', 'icônes', ['citation', 'guillemets', 'témoignage', 'avis client'], 1, 'fondu', 'fondu', 2.5, 0.25, 'Grands guillemets pour un témoignage.'],
	'chargement': ['Chargement', 'icônes', ['chargement', 'attente', 'patience', 'en cours'], 1, 'fondu', 'fondu', 2, 0.18, 'Roue de chargement qui tourne.'],
	'curseur-clic': ['Curseur qui clique', 'icônes', ['curseur', 'clic', 'cliquer', 'souris', 'lien', 'bouton'], 2, 'glisse-bas', 'fondu', 2, 0.22, 'Flèche de souris avec l’éclat du clic.'],
};

const defaut = (svg, slot) => new RegExp(`var\\(--v-${slot},\\s*(#[0-9A-Fa-f]{3,8})\\)`).exec(svg)?.[1]?.toUpperCase() ?? null;
const svgs = fs.readdirSync(DIR).filter((f) => f.endsWith('.svg')).map((f) => f.slice(0, -4)).sort();
const manque = svgs.filter((n) => !TABLE[n]);
const orphelines = Object.keys(TABLE).filter((n) => !svgs.includes(n));
if (manque.length || orphelines.length) throw new Error(`Table et SVG differents : sans fiche ${manque} ; sans SVG ${orphelines}`);
for (const nom of svgs) {
	const svg = fs.readFileSync(path.join(DIR, `${nom}.svg`), 'utf8');
	const [titre, categorie, motsCles, intensite, entree, sortie, duree, largeur, description, opts = {}] = TABLE[nom];
	const fiche = {
		nom: titre, categorie, motsCles, intensite, description,
		licence: LICENCE, provenance: PROVENANCE,
		couleurs: {principale: defaut(svg, 'principale'), secondaire: defaut(svg, 'secondaire'), contour: defaut(svg, 'contour')},
		anim: {entree, sortie},
		duree, largeur,
		formats: ['9:16', '16:9', '4:5', '1:1'],
		trace: /class="[^"]*\bv-trait\b/.test(svg),
		boucle: /data-boucle="([a-z-]+)"/.exec(svg)?.[1] ?? null,
		garderCouleurs: !!opts.garderCouleurs,
	};
	fs.writeFileSync(path.join(DIR, `${nom}.json`), JSON.stringify(fiche, null, 1) + '\n');
}
console.log(`${svgs.length} fiches ecrites dans ${DIR}`);
