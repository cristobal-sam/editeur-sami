"""Tests des finitions demandees par le juge independant n° 3 (2 octobre 2026), depuis engine/ :
    python ..\\docs\\qualite-2026-09-30\\tests\\test_juge3.py

Donnees FIGEES ou SYNTHETIQUES seulement (jamais un projet vivant de l'utilisateur) :
- docs/qualite-2026-09-30/tests/cas/juge2-p3d.json (Video 1 en Tech 3D telle que jugee : deux boutons) ;
- images synthetiques (tenseurs) pour le detourage : rien n'est ecrit sur le disque.

Couvre : bouton unique avec l'offre (galerie), bord pris sur un decor clair et doigts flous (detourage_rvm), controle :
saut d'image sans coupe, sous-titre eclair, bouton qui revient, apostrophes melangees, bande claire au bord de la tete."""
import copy
import json
import os
import sys
from pathlib import Path

os.environ['EDITEUR_LLM'] = '0'  # regles seules : resultat reproductible
ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[2]
sys.path.insert(0, str(ROOT / 'engine'))

import numpy as np  # noqa: E402

from editeur import controle, detourage_rvm, galerie  # noqa: E402

P3D = ICI / 'cas/juge2-p3d.json'
resultats = []


def verifier(nom, ok, detail=''):
    resultats.append(bool(ok))
    print(('OK    ' if ok else 'ECHEC ') + nom + (f' — {detail}' if detail else ''))


def cas_bouton_unique():
    base = json.loads(P3D.read_text(encoding='utf-8'))
    r = copy.deepcopy(base)
    galerie._prepare(r, use_ai=False)
    ctas = [s for s in r['styleScenes'] if s['kind'] == 'cta']
    times = galerie._times(r)
    c = ctas[0] if ctas else {}
    t0 = times.get((c.get('clip'), c.get('index')), 0)
    fin = t0 + float(c.get('duration') or 0)
    total = max(times.values())
    verifier('deux demandes du bouton a 9 s d\'ecart : UN seul bouton', len(ctas) == 1, f"{len(ctas)} bouton(s)")
    verifier('bouton tenu de la 1re demande jusqu\'a la fin', ctas and fin >= total - 0.5, f"{t0:.2f} -> {fin:.2f} (dernier mot {total:.2f})")
    verifier('offre dite gardee au-dessus (« 1 semaine gratuite ») et son mot (offer)', ctas and c.get('secondary') == '1 semaine gratuite'
             and isinstance(c.get('offer'), int) and 'lead' not in c, f"{c.get('secondary')} / offer {c.get('offer')}")
    # le parcours « Répondre -> Qualifier » redit la page « pour répondre et qualifier » : il entre avec elle (1er mot « pour »)
    flow = next((s for s in r['styleScenes'] if s['kind'] == 'flow' and s['text'] == 'Répondre'), {})
    mots_flow = next((c['words'] for c in r['clips'] if c['id'] == flow.get('clip')), [])
    verifier("parcours ancre sur le 1er mot de la page qu'il redit", mots_flow and str(mots_flow[flow['index']]['w']).lower() == 'pour',
             f"index {flow.get('index')} : {mots_flow[flow['index']]['w'] if mots_flow else '?'}")
    autres = [s for s in r['styleScenes'] if s['kind'] != 'cta' and t0 <= times.get((s['clip'], s['index']), -1) <= fin]
    verifier('aucune autre scene posee pendant le bouton tenu', not autres, ', '.join(s['text'] for s in autres) or 'aucune')
    # revue du 2 oct. 2026 : le parcours avance garde sa fin (duree allongee d'autant : pas de vide de plus avant le chiffre) ;
    # jamais avance contre la fin de la scene d'avant (timeline.ts l'ecarterait : carte perdue)
    verifier('parcours avance : sa fin ne bouge pas (duree allongee)', abs(float(flow.get('duration') or 0) - 3.2) < 0.06, str(flow.get('duration')))
    notif = [s for s in r['styleScenes'] if s['kind'] == 'notification'][-1]
    garde = copy.deepcopy(r['styleScenes'])
    f2 = next(s for s in garde if s['id'] == flow['id'])
    f2.update({'index': flow['index'] + 1, 'duration': 3})
    from editeur import montage
    exact = {(w['clip'], w['index']): w['start'] for p in montage.compute(r)['pages'] for w in p['words']}
    t_flow = exact[(flow['clip'], flow['index'])]  # 1er mot de la page (« pour »)
    # la notification d'avant finit 0,3 s avant ce mot : l'avancer la ferait ecarter par timeline.ts
    next(s for s in garde if s['id'] == notif['id'])['duration'] = round(t_flow - 0.3 - exact[(notif['clip'], notif['index'])], 2)
    galerie._aligner_pages(r, garde)
    verifier("parcours jamais avance contre la fin de la scene d'avant", f2['index'] == flow['index'] + 1 and f2['duration'] == 3,
             f"index {f2['index']}, duree {f2['duration']}")
    # revue du 2 oct. 2026 : un 1er bouton retouche par le monteur (texte change) n'est jamais cache par le bouton unique pose au
    # meme instant sous un autre identifiant ; le bouton unique retouche, lui, reste seul
    r4 = copy.deepcopy(base)
    galerie._prepare(r4, use_ai=False)
    r5 = copy.deepcopy(r4)
    c4 = next(s for s in r4['styleScenes'] if s['kind'] == 'cta')
    premier = {**c4, 'id': c4['id'][:-len('-final')], 'text': 'Réserver un appel', 'edited': True, 'duration': 3.0}
    for s in ('offer', 'offerClip', 'secondary'):
        premier.pop(s, None)
    r4['styleScenes'] = [premier]
    galerie.prepare(r4, use_ai=False)
    ctas4 = [s for s in r4['styleScenes'] if s['kind'] == 'cta']
    debut = {s['id']: times.get((s['clip'], s['index'])) for s in ctas4}
    verifier('bouton retouche par le monteur : jamais cache par un bouton unique au meme instant',
             any(s.get('edited') and s['text'] == 'Réserver un appel' for s in ctas4)
             and not any(not s.get('edited') and debut[s['id']] is not None and abs(debut[s['id']] - debut[premier['id']]) < 0.5 for s in ctas4),
             str([(s['id'], s['text'], s.get('edited')) for s in ctas4]))
    c5 = next(s for s in r5['styleScenes'] if s['kind'] == 'cta')
    r5['styleScenes'] = [{**c5, 'text': 'Réserver un appel', 'edited': True}]
    galerie.prepare(r5, use_ai=False)
    ctas5 = [s for s in r5['styleScenes'] if s['kind'] == 'cta']
    verifier('bouton unique retouche : il reste seul (le protege gagne)', len(ctas5) == 1 and ctas5[0]['text'] == 'Réserver un appel',
             str([(s['id'], s['text']) for s in ctas5]))
    # demandes eloignees : comportement d'avant (premier bouton, puis le dernier avec l'offre qui entre avant lui)
    ancien = galerie.CTA_UNIQUE
    try:
        galerie.CTA_UNIQUE = 5.0
        r2 = copy.deepcopy(base)
        galerie._prepare(r2, use_ai=False)
    finally:
        galerie.CTA_UNIQUE = ancien
    ctas2 = [s for s in r2['styleScenes'] if s['kind'] == 'cta']
    verifier('demandes eloignees : deux boutons comme avant (le 2e avec lead)', len(ctas2) == 2 and isinstance(ctas2[1].get('lead'), int),
             str([(s['index'], s.get('lead')) for s in ctas2]))


def _image_test():
    """Personne synthetique sur un mur blanc : visage couleur peau (disque) dont le bord gauche garde une bande blanche
    (mur vu entre l'oreille et la joue) que RVM a mise dans la personne (alpha 1) ; dents blanches au centre du visage."""
    import torch
    H, W = 960, 540  # demi-resolution d'une prise verticale (les bandes du module sont en px de 1080 de large)
    ys, xs = torch.meshgrid(torch.arange(H, dtype=torch.float32), torch.arange(W, dtype=torch.float32), indexing='ij')
    mur = torch.tensor([0.97, 0.97, 0.98]).view(3, 1, 1)
    peau = torch.tensor([0.78, 0.5, 0.38]).view(3, 1, 1)
    d = ((xs - 270) ** 2 + (ys - 400) ** 2).sqrt()
    alpha = (d < 180).float()
    x = mur.expand(3, H, W).clone()
    x = torch.where(alpha.bool()[None], peau.expand(3, H, W), x)
    bande = (d >= 160) & (d < 180) & (xs < 140)  # mur blanc dans la silhouette, cote gauche
    x[:, bande] = mur.view(3, 1).expand(3, int(bande.sum()))
    dents = ((xs - 270).abs() < 36) & ((ys - 450).abs() < 12)
    x[:, dents] = torch.tensor([0.96, 0.95, 0.93]).view(3, 1)
    return x[None], alpha, bande, dents


def cas_fond_clair():
    import torch
    import torch.nn.functional as F
    x, alpha, bande, dents = _image_test()
    out, retrait4, pur, (teinte, w) = detourage_rvm._fond_clair(x, alpha, None, None, None, 1.0, F, visage=(270 / 540, 400 / 960))
    H, W = alpha.shape
    coul = x[0] * (1 - w) + teinte * w
    peau = torch.tensor([0.78, 0.5, 0.38]).view(3, 1)
    avant = float((x[0][:, bande] - peau).norm(dim=0).mean())
    apres = float((coul[:, bande] - peau).norm(dim=0).mean())
    verifier('decor clair : la bande blanche dans la silhouette prend la teinte de la peau', apres < 0.5 * avant, f"ecart a la peau {avant:.2f} -> {apres:.2f}")
    # au-dela des 8 px (16 px a pleine resolution) qui touchent le decor libre, la bande garde son alpha : pas de fente sombre
    ys, xs = torch.meshgrid(torch.arange(H, dtype=torch.float32), torch.arange(W, dtype=torch.float32), indexing='ij')
    dedans = bande & (((xs - 270) ** 2 + (ys - 400) ** 2).sqrt() < 170)
    verifier("decor clair : la silhouette reste entiere (alpha garde a l'interieur de la bande)", float(out[dedans].mean()) > 0.85,
             f"alpha moyen {float(out[dedans].mean()):.2f} (toute la bande {float(out[bande].mean()):.2f})")
    verifier('decor clair : les dents (blanches, au coeur du visage) ne bougent pas', float(w[dents].max()) < 0.05 and float((out[dents] - 1).abs().max()) < 1e-3,
             f"poids max {float(w[dents].max()):.3f}")
    # bord exterieur : frange du mur (pixel tres clair au bord exact de la silhouette) -> alpha retire
    x2, alpha2 = x.clone(), alpha.clone()
    ys, xs = torch.meshgrid(torch.arange(H, dtype=torch.float32), torch.arange(W, dtype=torch.float32), indexing='ij')
    d = ((xs - 270) ** 2 + (ys - 400) ** 2).sqrt()
    frange = (d >= 180) & (d < 184)
    alpha2[frange] = 1.0  # RVM a pris 4 px de mur
    out2, *_ = detourage_rvm._fond_clair(x2, alpha2, None, None, None, 1.0, F)
    verifier('decor clair : frange du mur au bord exterieur retiree', float(out2[frange].mean()) < 0.4, f"alpha {float(out2[frange].mean()):.2f}")
    # decor SOMBRE : rien ne change
    x3 = x.clone()
    x3[0][:, alpha == 0] = 0.08
    out3, _, _, (_, w3) = detourage_rvm._fond_clair(x3, alpha, None, None, None, 1.0, F)
    verifier('decor sombre : alpha et couleurs inchanges', float((out3 - alpha).abs().max()) < 1e-4 and float(w3.max()) < 1e-3)


def cas_mains():
    import torch
    import torch.nn.functional as F
    H, W = 480, 270
    ys, xs = torch.meshgrid(torch.arange(H, dtype=torch.float32), torch.arange(W, dtype=torch.float32), indexing='ij')
    # doigt flou de bouger : transition d'alpha large (30 px) couleur peau, loin du visage
    a = (1 - ((xs - 200).abs() - 10) / 30).clamp(0, 1) * ((ys > 300) & (ys < 420)).float()
    fgr = torch.tensor([0.8, 0.55, 0.42]).view(1, 3, 1, 1).expand(1, 3, H, W).clone()
    mv = torch.zeros(1, 1, H // 4, W // 4)
    out, k = detourage_rvm._mains(a, fgr, mv, (0.5, 0.3), 1.0, F)
    semi = (a > 0.3) & (a < 0.7)
    verifier('doigt flou (transition large, peau) : alpha releve', float(out[semi].mean()) > float(a[semi].mean()) + 0.15,
             f"{float(a[semi].mean()):.2f} -> {float(out[semi].mean()):.2f}")
    # cheveux sombres au bord flou : rien ne change
    fgr2 = torch.tensor([0.12, 0.09, 0.07]).view(1, 3, 1, 1).expand(1, 3, H, W).clone()
    out2, _ = detourage_rvm._mains(a, fgr2, mv, (0.5, 0.3), 1.0, F)
    verifier('bord flou sombre (cheveux) : alpha inchange', float((out2 - a).abs().max()) < 1e-4)
    # bord net de peau (bras) : presque rien
    a3 = (xs < 150).float()
    out3, _ = detourage_rvm._mains(a3, fgr, mv, (0.5, 0.3), 1.0, F)
    verifier('bord net (bras) : inchange', float((out3 - a3).abs().max()) < 1e-3)


class _Ctx:
    def __init__(self, tl, H=1920):
        self.tl, self.H, self.W = tl, H, 1080
        self.reel = {'brand': {}}

    def outro(self, t):
        return False


def cas_controle():
    # saut d'image sans coupe : la camera descend la personne de 3 % d'un coup (meme plan, meme taille) ; glissement : non
    def frames(dys):
        return [{'t': i * .1, 'seg': 0, 'f': {'cy': .42}, 'view': {'scale': 1.1, 'oy': .94, 'dy': dy}} for i, dy in enumerate(dys)]
    saut = controle._sauts_cadre(_Ctx({'frames': frames([0] * 30 + [.03] * 20)}))
    glisse = controle._sauts_cadre(_Ctx({'frames': frames([0] * 30 + [.03 * min(1, k / 8) for k in range(1, 21)])}))
    coupe = controle._sauts_cadre(_Ctx({'frames': frames([0] * 30)[:30] + [dict(f, seg=1) for f in frames([.03] * 50)[30:]]}))
    verifier('controle : saut d\'image sans coupe repere', len(saut) == 1 and saut[0]['code'] == 'saut-cadre', saut[0]['message'] if saut else 'rien')
    verifier('controle : glissement adouci et coupe non comptes', not glisse and not coupe)
    # sous-titre eclair
    pages = [{'start': 34.48, 'end': 35.48, 'vis': .2, 'cache': .8, 'words': [{'w': 'pour'}, {'w': 'répondre'}]},
             {'start': 35.48, 'end': 36.5, 'vis': 1.02, 'cache': 0, 'words': [{'w': 'vos'}, {'w': 'leads'}]}]
    ec = controle._pages_eclair(_Ctx({'pages': pages}))
    verifier('controle : sous-titre eclair de 0,2 s repere', len(ec) == 1 and ec[0]['gravite'] == 'important', ec[0]['message'] if ec else 'rien')
    # bouton qui s'en va et revient
    sc = [{'kind': 'cta', 'text': 'En savoir plus', 'at': 59.83, 'end': 62.83}, {'kind': 'cta', 'text': 'En savoir plus', 'at': 64.45, 'end': 71.47}]
    br = controle._bouton_revient(_Ctx({'scenes': sc, 'pages': []}))
    un = controle._bouton_revient(_Ctx({'scenes': [dict(sc[0], end=71.47)], 'pages': []}))
    verifier('controle : bouton qui revient repere, bouton unique non', len(br) == 1 and not un)
    # apostrophes melangees (textes affiches)
    ap = controle._apostrophes(_Ctx({'pages': [{'start': 1, 'shown': "quelqu'un à", 'words': []}, {'start': 2, 'shown': 'c’est', 'words': []}], 'scenes': []}))
    ap2 = controle._apostrophes(_Ctx({'pages': [{'start': 1, 'shown': 'quelqu’un à', 'words': []}, {'start': 2, 'shown': 'c’est', 'words': []}], 'scenes': []}))
    verifier('controle : apostrophes melangees reperees, homogenes non', len(ap) == 1 and not ap2)
    # bande claire au bord de la tete (image BGRA) : tete avec une bande blanche le long du bord / sans
    import cv2
    im = np.zeros((480, 270, 4), np.uint8)
    cv2.circle(im, (135, 120), 70, (90, 130, 200, 255), -1)
    propre = controle.bord_clair(im)
    cv2.circle(im, (135, 120), 70, (250, 250, 250, 255), 8)
    blanc = controle.bord_clair(im)
    verifier('controle : bande claire au bord de la tete mesuree', blanc > .1 and propre < .001, f"{propre:.3f} -> {blanc:.3f}")


def main():
    cas_bouton_unique()
    cas_fond_clair()
    cas_mains()
    cas_controle()
    print(f'\n{sum(resultats)}/{len(resultats)} verifications reussies')
    return 0 if all(resultats) else 1


if __name__ == '__main__':
    sys.exit(main())
