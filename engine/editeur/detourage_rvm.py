"""Detourage video RobustVideoMatting (RVM v1.0.0, GPL-3.0, modeles TorchScript locaux dans models/rvm).

La prise est traitee comme une VIDEO : les etats recurrents (r1..r4) passent d'une image a la suivante, ce qui
donne un alpha stable dans le temps. L'alpha sort en pleine resolution (raffineur guide interne de RVM), puis :
  1. on ne garde que les personnes (composantes connexes : celle qui contient le visage suivi, les morceaux
     proches, et toute autre personne entiere >= 8 % de son aire) ; morceaux de table / chaise detaches retires ;
  2. lissage temporel de l'alpha seulement la ou l'image ne bouge pas (pas de trainee sur les mains) ;
  3. filtre guide facultatif sur les bords avec l'image pleine resolution ;
  4. couleur des bords : premier plan estime par RVM (fgr) remplace par la couleur du corps voisin (deux echelles)
     + leger retrait de la teinte du decor ;
  4 bis. (2 oct. 2026, juge n° 3) doigts flous d'un geste rapide rendus plus opaques (_mains) ; bord pris sur un decor CLAIR
     recalcule par la couleur (_fond_clair : frange du mur retiree, mur ou peau brulee DANS la silhouette a la teinte de la
     peau voisine, or des boucles d'oreilles garde) ;
  5. score de qualite par image et plages de repli (le rendu peut montrer le decor d'origine assombri).

Rapport par prise : <dossier des images>/qualite.json (voir `rapport_qualite`).
Champ documente pour le rendu : cutouts[clip]['fallback'] = [[t0, t1], ...] en secondes DANS LA PRISE
(meme repere que src_in/src_out) ou le detourage est juge mauvais.
"""
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue

import numpy as np

from .media import ROOT, FFMPEG

MODELES = ROOT / 'models' / 'rvm'
PREROLL = 1.0          # secondes decodees avant le debut pour amorcer les etats recurrents
AMORCE_MIN = 15        # images d'amorce minimum (la 1re image est repetee si la prise commence trop tot)
SEUIL_REPLI = 0.5      # score sous lequel une image est marquee pour le repli
COTE_MAX = 1920        # plus grand cote traite (les medias optimises font 1080 px sur le petit cote)
COTE_MAX_PROCESSEUR = 1280  # sans carte graphique : 720x1280 (~0,6 s/image au lieu de ~1,4 s en 1080x1920)
AUTRE_PERSONNE = 0.08  # composante gardee meme loin de la principale si >= 8 % de son aire (2e personne) ;
                       # les morceaux de decor detaches font < 1 % de la personne sur les prises testees
QUALITE_WEBP = 90
REGLAGES = {
    'lissage': 0.4,     # poids max de l'image precedente la ou rien ne bouge (0 = aucun lissage)
    'guide': False,     # filtre guide supplementaire sur les bords (RVM raffine deja en pleine resolution)
    'despill': 0.6,     # force du retrait de la teinte du decor sur les bords
    'composantes': True,  # ne garder que la personne principale (morceaux de table, chaise detachee...)
    'voiles': True,     # attenuer les voiles faibles loin du corps (ombres, fumee grise)
    'plein': True,      # coeur du corps opaque, bords doux
    'extension': 1.0,   # part de la couleur du corps voisin sur les bords (anti-lisere)
    'couleur_avant_plein': True,  # bords rendus opaques par 'plein' : couleur du corps, pas celle du decor
    'fond_clair': 1.0,  # bord pris sur un decor CLAIR (mur blanc, fenetre) : alpha recalcule par la couleur (voir _fond_clair)
    'mains': 1.0,       # doigts flous d'un geste rapide : rendus plus opaques (voir _mains)
}


def ratio_reduction(w, h):
    """downsample_ratio conseille par la documentation RVM (buste / plan taille) selon la resolution."""
    cote = max(w, h)
    if cote <= 512:
        return 1.0
    if cote <= 1280:
        return 0.375
    if cote <= 1920:
        return 0.25
    return 0.125


def cuda_disponible():
    """Vraie carte graphique utilisable (CUDA_VISIBLE_DEVICES vide : is_available() dit oui, mais 0 appareil)."""
    import torch
    return torch.cuda.is_available() and torch.cuda.device_count() > 0


def _dimensions(path, cote_max=COTE_MAX):
    import cv2
    cap = cv2.VideoCapture(str(path))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if not w or not h:
        raise RuntimeError(f'Vidéo illisible pour le détourage : {Path(path).name}')
    k = min(1.0, cote_max / max(w, h))
    return w, h, int(round(w * k / 2) * 2), int(round(h * k / 2) * 2)


def _point_sujet(sujet, t):
    """Point du visage suivi le plus proche de t (coordonnees 0-1), ou None au-dela d'une seconde."""
    if not sujet:
        return None
    k = min(range(len(sujet)), key=lambda i: abs(sujet[i][0] - t))
    return (sujet[k][1], sujet[k][2]) if abs(sujet[k][0] - t) <= 1.0 else None


class Matteur:
    """Modele RVM charge une fois (resnet50 si la carte graphique a de la place, sinon mobilenetv3 ; processeur
    en dernier recours). Liberer avec close() : la carte graphique est partagee."""

    def __init__(self, modele=None, appareil=None):
        import torch
        self.torch = torch
        self.appareil = appareil or ('cuda' if cuda_disponible() else 'cpu')
        if modele is None:
            modele = 'mobilenetv3'
            if self.appareil == 'cuda':
                libre, _ = torch.cuda.mem_get_info()
                modele = 'resnet50' if libre > 1.5 * 2 ** 30 else 'mobilenetv3'
        chemin = MODELES / f'rvm_{modele}_fp32.torchscript'
        if not chemin.exists():
            raise FileNotFoundError(f'Modèle de détourage absent : {chemin.name}')
        self.modele = modele
        self.model = torch.jit.load(str(chemin), map_location=self.appareil).eval()

    def close(self):
        self.model = None
        if self.appareil == 'cuda':
            self.torch.cuda.empty_cache()

    # --- traitement d'une plage de prise -------------------------------------------------------------------
    def run(self, path, start, end, fps, dossier, sujet=None, reglages=None):
        """Ecrit dossier/00000.webp... (RGBA pleine resolution, image 0 = temps `start`) et qualite.json.
        Retourne le rapport de qualite (dict)."""
        import torch
        import torch.nn.functional as F
        opts = {**REGLAGES, **(reglages or {})}
        dossier = Path(dossier)
        dossier.mkdir(parents=True, exist_ok=True)
        sw, sh, w, h = _dimensions(path, COTE_MAX if self.appareil == 'cuda' else COTE_MAX_PROCESSEUR)
        ratio = opts.get('ratio') or ratio_reduction(w, h)
        s0 = max(0.0, start - PREROLL)
        saut = int(round((start - s0) * fps))
        vf = f'fps={fps}' + ('' if (w, h) == (sw, sh) else f',scale={w}:{h}')
        lecteur = subprocess.Popen([FFMPEG, '-v', 'error', '-ss', f'{s0:.4f}', '-t', f'{end - s0:.4f}', '-i', str(path),
                                    '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        taille = w * h * 3
        file = Queue(maxsize=6)

        def lire():  # decodage en parallele du modele, memoire bornee par la file
            try:
                while True:
                    raw = lecteur.stdout.read(taille)
                    if len(raw) != taille:
                        break
                    file.put(np.frombuffer(raw, np.uint8).reshape(h, w, 3))
            finally:
                file.put(None)
        fil = threading.Thread(target=lire, daemon=True)
        fil.start()

        from PIL import Image
        ecrivains = ThreadPoolExecutor(max_workers=10)
        places = threading.Semaphore(24)  # images en attente d'ecriture : memoire bornee

        def ecrire(i, rgba):
            try:
                Image.fromarray(rgba).save(dossier / f'{i:05d}.webp', 'WEBP', quality=QUALITE_WEBP, method=0)
            finally:
                places.release()

        dev = self.appareil
        luma = torch.tensor([0.299, 0.587, 0.114], device=dev).view(3, 1, 1)
        rec = [None] * 4
        prec = None        # (couleur reduite, alpha lisse) de l'image precedente
        mesures = []
        taches = []
        temps = {'modele': 0.0, 'post': 0.0, 'attente': 0.0, 'ecriture': 0.0}
        n_lues = 0
        index = 0
        t_debut = time.perf_counter()
        try:
            with torch.inference_mode():
                while True:
                    t0 = time.perf_counter()
                    rgb = file.get()
                    temps['attente'] += time.perf_counter() - t0
                    if rgb is None:
                        break
                    n_lues += 1
                    t0 = time.perf_counter()
                    x = torch.from_numpy(rgb).to(dev).permute(2, 0, 1)[None].float().div_(255)
                    if n_lues == 1 and saut < AMORCE_MIN:
                        # prise qui commence au debut du fichier : la 1re image repetee amorce les etats
                        for _ in range(AMORCE_MIN - saut):
                            _, _, *rec = self.model(x, *rec, ratio)
                    fgr, pha, *rec = self.model(x, *rec, ratio)
                    if dev == 'cuda':
                        torch.cuda.synchronize()
                    temps['modele'] += time.perf_counter() - t0
                    if n_lues <= saut:
                        continue  # image d'amorce avant le debut demande
                    t0 = time.perf_counter()
                    t = start + index / fps
                    rgba, m, prec = self._affiner(x, fgr, pha, prec, _point_sujet(sujet, t), opts, luma, F)
                    mesures.append(m)
                    temps['post'] += time.perf_counter() - t0
                    t0 = time.perf_counter()
                    places.acquire()
                    temps['ecriture'] += time.perf_counter() - t0
                    taches.append(ecrivains.submit(ecrire, index, rgba))
                    index += 1
            for tache in taches:
                tache.result()
        finally:
            ecrivains.shutdown(wait=True)
            if lecteur.poll() is None:
                lecteur.terminate()
            lecteur.wait()
            while fil.is_alive():  # arret en cours de route : vider la file pour liberer le fil de lecture
                while not file.empty():
                    file.get_nowait()
                fil.join(timeout=0.1)
        if not index:
            raise RuntimeError('Le détourage local n’a produit aucune image.')
        total = time.perf_counter() - t_debut
        vitesse = {'total': round(total * 1000 / index, 1), 'modele': round(temps['modele'] * 1000 / max(1, n_lues), 1),
                   'affinage': round(temps['post'] * 1000 / index, 1), 'attente_decodage': round(temps['attente'] * 1000 / max(1, n_lues), 1),
                   'attente_ecriture': round(temps['ecriture'] * 1000 / index, 1)}
        rapport = rapport_qualite(mesures, start, fps, {'moteur': f'rvm-{self.modele}', 'appareil': dev, 'ratio': ratio,
                                                        'width': w, 'height': h, 'vitesse_ms_image': vitesse,
                                                        'amorce_images': saut})
        (dossier / 'qualite.json').write_text(json.dumps(rapport, ensure_ascii=False), encoding='utf-8')
        return rapport

    # --- affinage d'une image ----------------------------------------------------------------------------------
    def _affiner(self, x, fgr, pha, prec, visage, opts, luma, F):
        import cv2
        import torch
        H, W = pha.shape[-2:]
        brut = pha[0, 0].clamp(0, 1)
        petit_h, petit_w = H // 4, W // 4
        petit = F.adaptive_avg_pool2d(brut[None, None], (petit_h, petit_w))[0, 0]
        b = (petit > 0.5).to(torch.uint8).cpu().numpy()
        n, lab, stats, _ = cv2.connectedComponentsWithStats(b, connectivity=8)
        aires = stats[1:, cv2.CC_STAT_AREA] if n > 1 else np.zeros(0)
        frag = int((aires >= 0.002 * petit_h * petit_w).sum())
        garde = None
        if opts['composantes'] and n > 1:
            principal = 0
            if visage:
                fx = min(petit_w - 1, max(0, int(visage[0] * petit_w)))
                fy = min(petit_h - 1, max(0, int(visage[1] * petit_h)))
                principal = int(lab[fy, fx])
                if not principal:  # visage hors masque : composante importante la plus proche du visage
                    cand = [k for k in range(1, n) if stats[k, cv2.CC_STAT_AREA] >= 0.1 * aires.max()]
                    principal = min(cand, key=lambda k: (max(0, stats[k, 0] - fx, fx - stats[k, 0] - stats[k, 2]) +
                                                         max(0, stats[k, 1] - fy, fy - stats[k, 1] - stats[k, 3])))
            if not principal:  # sans visage suivi : la plus grande, un peu favorisee au centre
                centre = [abs(stats[k, 0] + stats[k, 2] / 2 - petit_w / 2) / petit_w for k in range(1, n)]
                principal = 1 + int(np.argmax(aires * (1 - 0.5 * np.array(centre))))
            p = (lab == principal).astype(np.uint8)
            proche = cv2.dilate(p, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
            a_p = stats[principal, cv2.CC_STAT_AREA]
            # garde aussi une AUTRE personne entiere, meme loin (interview a deux, personne assise a cote) : la piste
            # visage suit l'intervenant qui parle, l'effacer ferait disparaitre l'autre a chaque changement de parole
            gardes = [principal] + [k for k in range(1, n) if k != principal and (
                stats[k, cv2.CC_STAT_AREA] >= max(AUTRE_PERSONNE * a_p, 0.002 * petit_h * petit_w) or
                (stats[k, cv2.CC_STAT_AREA] >= 0.02 * a_p and proche[lab == k].any()))]
            if len(gardes) < n - 1:
                g = np.isin(lab, gardes).astype(np.uint8)
                g = cv2.dilate(g, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
                g = cv2.GaussianBlur(g.astype(np.float32), (5, 5), 0)
                garde = torch.from_numpy(np.clip(g * 1.5, 0, 1)).to(brut.device)
                garde = F.interpolate(garde[None, None], size=(H, W), mode='bilinear', align_corners=False)[0, 0]
        alpha = brut if garde is None else brut * garde
        # lissage temporel : seulement la ou l'image (en couleur : peau et bois ont la meme luminance) et l'alpha
        # ne bougent pas ; sinon trainee sur les mains
        c_petit = F.adaptive_avg_pool2d(x, (petit_h, petit_w))
        # mouvement de l'image (quart de resolution) : doigts flous d'un geste rapide, lissage du bord sur decor clair
        mv = None if prec is None else F.max_pool2d((c_petit - prec[0]).abs().amax(1, keepdim=True), 5, 1, 2)
        if prec is not None and opts['lissage'] > 0:
            c_prec, a_prec = prec[0], prec[1]
            mvt = (c_petit - c_prec).abs().amax(1, keepdim=True)
            mvt = F.avg_pool2d(F.max_pool2d(mvt, 7, 1, 3), 5, 1, 2)
            mvt = F.interpolate(mvt, size=(H, W), mode='bilinear', align_corners=False)[0, 0]
            k = opts['lissage'] * (1 - (mvt / 0.02).clamp(0, 1)) * (1 - ((alpha - a_prec).abs() / 0.15).clamp(0, 1))
            alpha = alpha * (1 - k) + a_prec * k
        lisse = alpha
        # voiles (ombre sur la table, fumee grise) loin du corps : attenues au-dela de 20 px du coeur de la personne
        coeur = (F.adaptive_avg_pool2d(alpha[None, None], (petit_h, petit_w))[0, 0] > 0.5).to(torch.uint8).cpu().numpy()
        if coeur.any() and opts['voiles']:
            d = cv2.distanceTransform(1 - coeur, cv2.DIST_L2, 3) * (W / petit_w)
            f = torch.from_numpy(np.clip(1 - (d - 20) / 20, 0, 1).astype(np.float32)).to(alpha.device)
            f = F.interpolate(f[None, None], size=(H, W), mode='bilinear', align_corners=False)[0, 0]
            faible = ((0.45 - alpha) / 0.2).clamp(0, 1)
            alpha = alpha * (1 - faible * (1 - f))
        # coeur plein : l'interieur du corps (doigts rapides, peau sur bois) n'est jamais transparent,
        # les bords gardent la transition douce de RVM. La couleur suit l'alpha AVANT ce remplissage : un pixel de bord
        # rendu opaque garde la couleur du corps voisin, pas celle de l'image (fenetre en contre-jour = lisere blanc)
        a_couleur = alpha if opts.get('couleur_avant_plein', True) else None
        if opts['plein']:
            dur = (alpha > 0.5).float()[None, None]
            dur = 1 - F.max_pool2d(1 - dur, 7, 1, 3)
            dur = F.avg_pool2d(dur, 5, 1, 2)[0, 0]
            alpha = torch.maximum(alpha, dur)
        # doigts flous d'un geste rapide (hors du visage) : plus opaques ; puis bord pris sur un decor clair recalcule par
        # la couleur (bande blanche du mur le long de la joue, interieur des boucles d'oreilles). Juge n° 3 (2 oct. 2026).
        mains = None
        if opts.get('mains', 0) > 0 and mv is not None:
            alpha, mains = _mains(alpha, fgr, mv, visage, opts['mains'], F)
        pur = retrait = peint = None
        if opts.get('fond_clair', 0) > 0:
            alpha, retrait, pur, peint = _fond_clair(x, alpha, mains, mv, prec[2] if prec is not None and len(prec) > 2 else None,
                                                   opts['fond_clair'], F, visage)
        if opts['guide']:  # bords seulement : l'interieur et le fond ne bougent pas
            avant = alpha
            alpha = _filtre_guide((x[0] * luma).sum(0)[None, None], alpha[None, None], 6, 1e-3)[0, 0]
            bord = ((avant > 0.01) & (avant < 0.99)).float()[None, None]
            bord = F.max_pool2d(bord, 7, 1, 3)[0, 0]
            alpha = avant * (1 - bord) + alpha.clamp(0, 1) * bord
        alpha = torch.where(alpha < 0.02, torch.zeros_like(alpha), torch.where(alpha > 0.985, torch.ones_like(alpha), alpha))
        # couleur : image d'origine a l'interieur ; sur les bords, premier plan RVM melange a la couleur du corps
        # voisin (extension de bord) : pas de liseré clair du decor (fenetre, mur blanc) autour de la personne
        a_couleur = alpha if a_couleur is None else torch.minimum(a_couleur, alpha)
        interieur = ((a_couleur - 0.8) / 0.18).clamp(0, 1)
        if pur is not None:
            # pixel de bord dont la couleur est loin de celle du decor (or d'une boucle d'oreille, sourcil) : sa vraie couleur
            # est gardee, il n'est plus remplace par la peau voisine (boucles d'oreilles « fondues » en taches beiges)
            interieur = torch.maximum(interieur, pur * ((a_couleur - 0.55) / 0.25).clamp(0, 1))
        couleur = fgr[0].clamp(0, 1) * (1 - interieur) + x[0] * interieur
        if opts['extension'] > 0:
            # deux echelles : corps voisin a ~18 px (detail), sinon a ~70 px (voile clair entre boucle d'oreille et
            # joue, trou entre bras et corps) : tout pixel de bord recoit une couleur du corps, jamais celle du decor
            w_int = (a_couleur > 0.95).float()[None, None]
            ext, poids = None, None
            for f in (8, 2):
                taille = (H // f, W // f)
                num = F.avg_pool2d(F.interpolate(x * w_int, size=taille, mode='area'), 9, 1, 4)
                den = F.avg_pool2d(F.interpolate(w_int, size=taille, mode='area'), 9, 1, 4)
                num = F.interpolate(num, size=(H, W), mode='bilinear', align_corners=False)
                den = F.interpolate(den, size=(H, W), mode='bilinear', align_corners=False)
                e, m = num / den.clamp(min=1e-4), (den / 0.02).clamp(0, 1)
                ext = e if ext is None else ext * (1 - m) + e * m
                poids = m if poids is None else torch.maximum(poids, m)
            ext, poids = ext[0], poids[0] * opts['extension']
            couleur = couleur * (1 - (1 - interieur) * poids) + ext * (1 - interieur) * poids
        fond, corps = petit < 0.02, petit > 0.98
        if opts['despill'] > 0 and fond.float().mean() > 0.05 and bool(corps.any()):
            fond_rgb = c_petit[0][:, fond].mean(1)
            teinte = fond_rgb - fond_rgb.mean()
            peau = c_petit[0][:, corps].mean(1)
            peau = peau - peau.mean()
            # seulement si le decor a une teinte marquee ET differente de la personne (mur vert, bleu...) :
            # un mur chaud a la teinte de la peau, le retirer abimerait la peau
            if teinte.norm() > 0.03 and float((teinte * peau).sum()) < 0.3 * float(teinte.norm() * peau.norm()):
                u = (teinte / teinte.norm()).view(3, 1, 1)
                proj = ((couleur - couleur.mean(0, keepdim=True)) * u).sum(0, keepdim=True).clamp(min=0)
                couleur = couleur - opts['despill'] * (1 - interieur) * proj * u
        if peint is not None:
            # mur blanc ou peau brulee par la fenetre DANS la silhouette (entre l'oreille et la joue) : teinte de la peau voisine
            couleur = couleur * (1 - peint[1]) + peint[0] * peint[1]
        rgba = torch.cat([couleur.clamp(0, 1) * (alpha > 0), alpha[None]], 0)
        rgba = (rgba * 255 + 0.5).to(torch.uint8).permute(1, 2, 0).contiguous().cpu().numpy()
        # mesures pour le score (resolution reduite, bon marche)
        fin = F.adaptive_avg_pool2d(alpha[None, None], (petit_h, petit_w))[0, 0]
        masse_brute = float(petit.sum())
        incertain = float(((brut > 0.1) & (brut < 0.9)).sum()) / max(1.0, float((brut > 0.5).sum()))
        dedans = fin > 0.98
        m = {'couverture': float(fin.mean()), 'retire': 0.0 if masse_brute < 1 else max(0.0, 1 - float(fin.sum()) / masse_brute),
             'incertain': incertain, 'fragments': frag, 'visage': None,
             'rgb': c_petit[0][:, dedans].mean(1).tolist() if bool(dedans.any()) else None}
        if visage:
            fx = min(petit_w - 2, max(1, int(visage[0] * petit_w)))
            fy = min(petit_h - 2, max(1, int(visage[1] * petit_h)))
            m['visage'] = float(fin[fy - 1:fy + 2, fx - 1:fx + 2].mean())
        return rgba, m, (c_petit, lisse, retrait)


def _mains(alpha, fgr, mv, visage, force, F):
    """Doigts flous d'un geste rapide : l'alpha de RVM y est partiel (flou de bouger : doigt + mur), le decor du studio se
    voyait a travers les doigts (juge n° 3, 0:38,3). La ou le premier plan estime (fgr) a une couleur de peau ET ou l'image
    bouge vite (hors du visage : bord de la joue qui bouge avec la tete) ou la transition d'alpha est large (flou de bouger,
    20 a 40 px ; un bord net en fait 2 a 4 ; cheveux sombres jamais touches), l'alpha partiel est releve (1 - (1 - a)^3 :
    0,3 -> 0,66 ; 0,5 -> 0,88) ; les bords tres faibles (< 0,12) restent doux. -> (alpha, part relevee au quart de
    resolution, 0-1)."""
    import torch
    H, W = alpha.shape
    q = mv.shape[-2:]
    f4 = F.interpolate(fgr, size=q, mode='area')[0].clamp(0, 1)
    r, g, b = f4[0], f4[1], f4[2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    peau = (((r - b) - 0.05) / 0.06).clamp(0, 1) * ((r - g + 0.02) / 0.04).clamp(0, 1) * ((lum - 0.2) / 0.08).clamp(0, 1)
    vite = ((mv[0, 0] - 0.06) / 0.08).clamp(0, 1)
    # flou de bouger : transition d'alpha LARGE (un bord net fait 2 a 4 px, un doigt qui bouge 20 a 40 px)
    a4 = F.interpolate(alpha[None, None], size=q, mode='area')
    large = ((F.avg_pool2d(((a4 > 0.12) & (a4 < 0.88)).float(), 5, 1, 2)[0, 0] - 0.35) / 0.25).clamp(0, 1)
    if visage:
        # mouvement rapide : jamais sur le visage (bord de la joue qui bouge avec la tete) ; un flou large, lui, partout
        ys = torch.linspace(0, 1, q[0], device=alpha.device)[:, None]
        xs = torch.linspace(0, 1, q[1], device=alpha.device)[None, :]
        e = ((xs - visage[0]) / 0.11) ** 2 + ((ys - visage[1]) / 0.09) ** 2
        vite = vite * ((e - 1) / 0.4).clamp(0, 1)
    k = peau * torch.maximum(vite, large)
    k = F.avg_pool2d(k[None, None], 5, 1, 2) * force
    kk = F.interpolate(k, size=(H, W), mode='bilinear', align_corners=False)[0, 0].clamp(0, 1)
    semi = ((alpha - 0.12) / 0.18).clamp(0, 1)
    leve = 1 - (1 - alpha) ** 3
    return alpha + (leve - alpha) * kk * semi, k[0, 0]


def _fond_clair(x, alpha, mains, mv, retrait_prec, force, F, visage=None):
    """Bord de la personne pris sur un decor CLAIR (mur blanc, fenetre). RVM y garde souvent des pixels clairs et neutres :
    mur sous le lobe et dans les boucles d'oreilles, et surtout la peau BRULEE par la fenetre sur le cote du visage (blanc
    pur), qui devenait une bande blanc bleute collee le long de la joue dans le studio (juge n° 3 du 2 oct. 2026).
    Modele local a deux couleurs : B = couleur du decor tout pres (pixels sans personne, ~36 px, sinon ~100 px), G = couleur de
    la personne juste a l'interieur (coeur opaque a plus de 12 px du bord). Position d'un pixel entre B et G (projection de sa
    couleur sur le segment B -> G ; sur un decor neutre, aussi sa saturation : la peau eclairee reste chaude, le mur est neutre).
      - bande de 8 px qui touche le decor libre : l'alpha ne depasse plus cette position (frange du mur retiree) ;
      - jusqu'a 48 px : un pixel « couleur du mur » garde son alpha (la silhouette reste entiere : retirer le blanc entre
        l'oreille et la joue ouvrait une fente sombre) mais prend la teinte de la peau voisine, un peu eclaircie (reflet) ;
      - jamais dans le coeur du visage (yeux et dents, blancs et neutres eux aussi).
    Seulement si le decor est plus clair que la personne, si B et G sont bien distincts (chemise blanche sur mur blanc : rien),
    si le pixel est bien sur ce segment (or d'une boucle d'oreille : ni peau ni mur, inchange) et jamais sur des doigts flous
    releves par _mains. Retrait adouci (3 px) et lisse dans le temps la ou l'image ne bouge pas (contour non bossele).
    -> (alpha, retrait au quart de resolution pour l'image suivante, `pur` : pixel loin de la couleur du decor = vraie couleur
    a garder, (teinte de remplacement (3, H, W), poids (H, W)))."""
    import torch
    H, W = alpha.shape
    s = W / 1080
    q = (H // 4, W // 4)
    a4 = F.interpolate(alpha[None, None], size=q, mode='area')
    x4 = F.interpolate(x, size=q, mode='area')
    fond = (a4 < 0.03).float()
    e = max(1, round(3 * s))
    coeur = 1 - F.max_pool2d(1 - (a4 > 0.98).float(), 2 * e + 1, 1, e)

    def moyenne(m, k):
        num = F.avg_pool2d(x4 * m, k, 1, k // 2, count_include_pad=False)
        den = F.avg_pool2d(m, k, 1, k // 2, count_include_pad=False)
        return num / den.clamp(min=1e-4), (den / 0.03).clamp(0, 1)
    B1, m1 = moyenne(fond, 9)
    B2, m2 = moyenne(fond, 25)
    B = B1 * m1 + B2 * (1 - m1)
    # couleur de la personne : coeur opaque SANS les pixels couleur du mur (le mur pris dans la silhouette eclaircissait la
    # teinte de remplacement : bande pale au lieu de peau)
    coeur = coeur * ((x4 - B).norm(dim=1, keepdim=True) > 0.2).float()
    G1, n1 = moyenne(coeur, 9)
    G2, n2 = moyenne(coeur, 25)
    G = G1 * n1 + G2 * (1 - n1)
    connu = torch.maximum(m1, m2) * torch.maximum(n1, n2)

    def bande(px):  # pixels a moins de px (pleine resolution) du decor libre, bord doux
        r = max(1, round(px / 4 * s)) + 1
        return F.avg_pool2d(F.max_pool2d(fond, 2 * r + 1, 1, r), 3, 1, 1)
    poids = torch.tensor([0.299, 0.587, 0.114], device=x.device).view(1, 3, 1, 1)
    clair = ((((B - G) * poids).sum(1, keepdim=True) - 0.05) / 0.15).clamp(0, 1)
    sep = (((G - B).norm(dim=1, keepdim=True) - 0.12) / 0.12).clamp(0, 1)
    k4 = connu * clair * sep * force
    if mains is not None:
        k4 = k4 * (1 - mains[None, None])
    up = lambda v: F.interpolate(v, size=(H, W), mode='bilinear', align_corners=False)
    Bf, Gf, kf = up(B), up(G), up(k4)
    # coeur du visage (yeux, dents : blancs et neutres, jamais touches) exclu ; mur entre la machoire et le col : 48 px
    ka, kc = up(bande(8)), up(bande(48))
    if visage:
        ys = torch.linspace(0, 1, H, device=x.device)[:, None]
        xs = torch.linspace(0, 1, W, device=x.device)[None, :]
        e = ((xs - visage[0]) / 0.075) ** 2 + ((ys - visage[1]) / 0.065) ** 2
        hors = ((e - 1) / 0.3).clamp(0, 1)[None, None]
        ka, kc = ka * hors, kc * hors
    df = Gf - Bf
    ac = (((x - Bf) * df).sum(1, keepdim=True) / (df * df).sum(1, keepdim=True).clamp(min=1e-3)).clamp(0, 1)
    ecart = (x - (Bf + ac * df)).norm(dim=1, keepdim=True)
    modele = (1 - (ecart - 0.05) / 0.1).clamp(0, 1)
    sat = lambda v: (v.amax(1, keepdim=True) - v.amin(1, keepdim=True)) / v.amax(1, keepdim=True).clamp(min=0.05)
    neutre = ((0.15 - sat(Bf)) / 0.05).clamp(0, 1)
    ac = torch.maximum(ac, neutre * (sat(x) / sat(Gf).clamp(min=0.1)).clamp(0, 1))
    ac = ((ac - 0.15) / 0.7).clamp(0, 1)
    retrait = (alpha[None, None] - ac).clamp(min=0) * kf * ka * modele
    lisse = 2 * max(1, round(1.5 * s)) + 1
    retrait = F.avg_pool2d(retrait, lisse, 1, lisse // 2)
    retrait4 = F.interpolate(retrait, size=q, mode='area')
    if retrait_prec is not None and mv is not None:
        # contour stable : la ou rien ne bouge, moitie du retrait de l'image precedente (oreilles, joue)
        lent = 0.5 * (1 - (mv / 0.03).clamp(0, 1))
        lisse4 = retrait4 * (1 - lent) + retrait_prec * lent
        retrait = retrait + up(lisse4 - retrait4)
        retrait4 = lisse4
    out = (alpha[None, None] - retrait.clamp(min=0)).clamp(0, 1)[0, 0]
    # teinte de la peau voisine, eclaircie d'un quart vers le blanc (le cote du visage eclaire par la fenetre reste clair)
    w = F.avg_pool2d((1 - ac) * kf * kc * modele, lisse, 1, lisse // 2)[0, 0] * (out > 0.02)
    teinte = (Gf + (1 - Gf) * 0.12)[0]
    pur = (((x - Bf).norm(dim=1) - 0.22) / 0.15).clamp(0, 1)[0] * up(connu * clair)[0, 0]
    return out, retrait4, pur, (teinte, w)


def _filtre_guide(I, p, r, eps):
    """Filtre guide (He et al.) en torch, image guide I et alpha p de forme (1,1,H,W)."""
    import torch.nn.functional as F

    def boite(v):
        return F.avg_pool2d(v, 2 * r + 1, stride=1, padding=r, count_include_pad=False)
    mI, mp = boite(I), boite(p)
    a = (boite(I * p) - mI * mp) / (boite(I * I) - mI * mI + eps)
    b = mp - a * mI
    return boite(a) * I + boite(b)


def _tendance(cov, r=15):
    """Couverture attendue a chaque image : droite robuste (Theil-Sen) sur +-r images. Un mouvement regulier (la
    personne se penche, entre dans le cadre, debut ou fin de plage) suit la droite ; un saut bref du masque (chaise
    ou table attrapee quelques images, bras perdu) s'en ecarte. Avant : mediane simple, fausses alertes en bord de plage."""
    n = len(cov)
    ref = np.empty(n)
    for i in range(n):
        a, b = max(0, i - r), min(n, i + r + 1)
        y = cov[a:b]
        x = np.arange(a, b, dtype=np.float64) - i
        if len(y) < 3:
            ref[i] = float(np.median(y))
            continue
        dx = x[None, :] - x[:, None]
        pente = float(np.median((y[None, :] - y[:, None])[dx > 0] / dx[dx > 0]))
        ref[i] = float(np.median(y - pente * x))
    return ref


def rapport_qualite(mesures, start, fps, infos):
    """Score 0-1 par image et plages de repli.
    Penalites : alpha retire par le nettoyage (morceaux de decor), bords incertains, saut de couverture par rapport
    a la tendance des images voisines, fragmentation, visage hors du masque (si la piste visage est fiable pour la
    prise, voir visage_fiable), masque vide. Sous SEUIL_REPLI -> repli."""
    cov = np.array([m['couverture'] for m in mesures])
    ref = _tendance(cov)
    saut = np.abs(cov - ref) / np.maximum(ref, 0.03)
    # piste visage qui ne tombe presque jamais sur la personne detouree (plus d'1 s) : piste fausse pour cette prise
    # (analyse perimee, visage d'un passant ou d'une affiche) plutot que detourage rate -> ignoree pour le score
    avec = [m for m in mesures if m['visage'] is not None and m['couverture'] >= 0.01]
    hors = sum(1 for m in avec if m['visage'] < 0.5)
    visage_fiable = len(avec) < 30 or hors < 0.8 * len(avec)
    scores = []
    for m, j in zip(mesures, saut):
        p = (0.35 * np.clip((m['retire'] - 0.08) / 0.25, 0, 1) + 0.25 * np.clip((m['incertain'] - 0.30) / 0.40, 0, 1) +
             0.60 * np.clip((j - 0.10) / 0.25, 0, 1) + 0.20 * np.clip((m['fragments'] - 3) / 4, 0, 1))
        if visage_fiable and m['visage'] is not None and m['visage'] < 0.5:
            p += 0.7
        if m['couverture'] < 0.01:
            p += 1
        scores.append(float(np.clip(1 - p, 0, 1)))
    mauvais = [i for i, s in enumerate(scores) if s < SEUIL_REPLI]
    plages = []
    for i in mauvais:  # marge de 3 images, trous de moins de 6 images combles : pas de clignotement
        a, b = max(0, i - 3), min(len(scores), i + 4)
        if plages and a <= plages[-1][1] + 6:
            plages[-1][1] = max(plages[-1][1], b)
        else:
            plages.append([a, b])
    arr = lambda k, n=3: [None if m[k] is None else round(m[k], n) for m in mesures]
    teintes = [m['rgb'] for m in mesures if m.get('rgb')]
    return {'version': 2, **infos, 'start': start, 'fps': fps, 'count': len(scores), 'seuil': SEUIL_REPLI,
            'score_moyen': round(float(np.mean(scores)), 3), 'score_min': round(float(np.min(scores)), 3),
            'visage_fiable': visage_fiable,
            # couleur moyenne de la personne (0-255) : permet d'accorder la personne au decor du rendu
            'personne_rgb': [round(float(v) * 255, 1) for v in np.mean(teintes, 0)] if teintes else None,
            'repli': [[round(start + a / fps, 3), round(start + b / fps, 3)] for a, b in plages],
            'repli_images': plages,
            'scores': [round(s, 3) for s in scores],
            'mesures': {'couverture': arr('couverture', 4), 'retire': arr('retire'), 'incertain': arr('incertain'),
                        'fragments': [m['fragments'] for m in mesures], 'visage': arr('visage')},
            'aide': ('repli = plages [debut, fin] en secondes dans la prise (repere src_in/src_out) ou le detourage '
                     'est juge mauvais : y montrer la prise d origine (decor assombri/flou) au lieu de la personne '
                     'detouree. repli_images = memes plages en indices d images [debut, fin).')}


def journal(texte):
    print(texte, file=sys.stderr, flush=True)
