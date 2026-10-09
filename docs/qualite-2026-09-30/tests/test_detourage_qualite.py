"""Tests courts du detourage (bac a sable, jamais les vrais caches) :
  1. score de qualite et plages de repli (mesures synthetiques) ;
  2. affinage sur une image synthetique fond vert : tache detachee et voile retires, coeur opaque, bords sans vert ;
  3. prepare() sur un mini reel (1 s du plan c3 de Video 1) : champs du reel, cache reutilise, styles sans detourage ;
  4. plan sans personne : repli sur toute la plage ; repli automatique sur MediaPipe si le modele RVM manque ;
  5. memoire graphique rendue apres usage ; carte graphique pleine -> petit modele.
Usage (environnement charge, depuis engine/) : python ../docs/qualite-2026-09-30/tests/test_detourage_qualite.py
"""
import copy
import json
import os
import sys
import time
from pathlib import Path

VRAI = Path(__file__).resolve().parents[3]
BAC = VRAI / 'runtime/cache/tmp/detourage-rvm-test'
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_detourage_rvm as T  # noqa: E402  (meme bac a sable)

RESULTATS = []


def verifier(nom, ok, detail=''):
    RESULTATS.append((nom, bool(ok)))
    print(('OK   ' if ok else 'ECHEC') + f' {nom} {detail}')


def test_score(rvm):
    bon = {'couverture': 0.3, 'retire': 0.01, 'incertain': 0.06, 'fragments': 1, 'visage': 1.0, 'rgb': [0.5, 0.4, 0.3]}
    m = [dict(bon) for _ in range(90)]
    for i in range(20, 25):
        m[i]['visage'] = 0.1          # visage hors du masque : personne perdue
    m[50]['couverture'] = 0.6         # saut de couverture isole
    m[51]['couverture'] = 0.58
    for i in range(70, 73):
        m[i]['retire'] = 0.45         # gros morceau de decor retire
        m[i]['fragments'] = 9
    r = rvm.rapport_qualite(m, 10.0, 30, {'moteur': 'test'})
    verifier('score : images bonnes a 1', r['scores'][0] == 1.0 and r['scores'][89] == 1.0)
    verifier('score : visage perdu -> repli', r['repli_images'][0] == [17, 28], r['repli_images'])
    verifier('score : saut de couverture -> repli', any(a <= 50 < b for a, b in r['repli_images']), r['repli_images'])
    verifier('score : decor retire + fragments -> repli', any(a <= 71 < b for a, b in r['repli_images']))
    verifier('score : secondes dans la prise', r['repli'][0] == [round(10 + 17 / 30, 3), round(10 + 28 / 30, 3)], r['repli'][0])
    verifier('score : couleur de la personne', r['personne_rgb'] == [127.5, 102.0, 76.5])


def test_affinage(rvm):
    import torch
    import torch.nn.functional as F
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    H, W = 960, 544
    yy, xx = torch.meshgrid(torch.arange(H, device=dev).float(), torch.arange(W, device=dev).float(), indexing='ij')
    d = torch.sqrt(((xx - 272) / 170) ** 2 + ((yy - 560) / 330) ** 2)
    pha = ((1 - d) * 60).clamp(0, 1)                       # personne : ellipse, bord doux ~6 px
    pha[80:140, 30:90] = 1                                  # tache detachee (morceau de table)
    pha[880:940, 20:120] = torch.maximum(pha[880:940, 20:120], torch.tensor(0.2, device=dev))  # voile loin du corps
    peau = torch.tensor([0.85, 0.6, 0.45], device=dev).view(3, 1, 1)
    vert = torch.tensor([0.1, 0.85, 0.2], device=dev).view(3, 1, 1)
    x = (peau * pha + vert * (1 - pha))[None]
    fgr = x.clone()                                         # pire cas : premier plan contamine par le vert
    m = object.__new__(rvm.Matteur)
    m.torch, m.appareil = torch, dev
    luma = torch.tensor([0.299, 0.587, 0.114], device=dev).view(3, 1, 1)
    opts = dict(rvm.REGLAGES)
    rgba, mes, _ = m._affiner(x, fgr, pha[None, None], None, (0.5, 0.55), opts, luma, F)
    a = rgba[..., 3] / 255
    verifier('affinage : tache detachee retiree', a[80:140, 30:90].max() < 0.05, f"max {a[80:140, 30:90].max():.2f}")
    verifier('affinage : voile eloigne retire', a[880:940, 20:120].max() < 0.05, f"max {a[880:940, 20:120].max():.2f}")
    verifier('affinage : interieur opaque', a[500:620, 200:340].min() == 1.0)
    bord = (a > 0.1) & (a < 0.9)
    g = rgba[..., 1][bord].mean() / 255
    verifier('affinage : bords sans vert (despill + extension)', g < 0.65, f'vert moyen des bords {g:.2f} (peau 0.60, contamine ~0.72)')
    verifier('affinage : mesures presentes', mes['retire'] > 0 and mes['visage'] == 1.0, mes)


def test_prepare(detourage, reel_vrai):
    import torch
    reel = copy.deepcopy(reel_vrai)
    c3 = next(c for c in reel['clips'] if c['id'] == 'c3')
    reel['clips'] = [{**c3, 'in': 5.0, 'out': 6.0}]
    reel['sources'] = {c3['source']: reel['sources'][c3['source']]}
    reel['design'] = {**(reel.get('design') or {}), 'mode': 'produit', 'cinematic': True}
    import shutil
    cle = detourage._cle(detourage.ROOT / reel['sources'][c3['source']]['proxy'], 5.0, 6.0, reel['fps'], detourage.VERSION)
    for p in (detourage.ROOT / 'assets/detourage').glob(cle + '*'):  # sorties de ce test, dans le bac seulement
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    t = time.perf_counter()
    detourage.prepare(reel)
    t1 = time.perf_counter() - t
    cut = reel.get('cutouts', {}).get('c3') or {}
    champs = ['file', 'start', 'end', 'width', 'height', 'frames', 'fps', 'count', 'source', 'proxy', 'engine', 'score', 'quality', 'fallback']
    verifier('prepare : Tech 3D cinematique detoure', all(k in cut for k in champs), sorted(cut))
    verifier('prepare : 30 images pour 1 s', cut.get('count') == 30, cut.get('count'))
    verifier('prepare : fichiers presents', (detourage.ROOT / cut['frames'] / '00029.webp').exists() and
             (detourage.ROOT / cut['quality']).exists())
    verifier('prepare : source et proxy relies', cut['source'] == c3['source'] and cut['proxy'] == reel['sources'][c3['source']]['proxy'])
    verifier('prepare : memoire graphique rendue', not torch.cuda.is_available() or torch.cuda.memory_allocated() == 0,
             f'{torch.cuda.memory_allocated() if torch.cuda.is_available() else 0} octets')
    t = time.perf_counter()
    detourage.prepare(reel)
    t2 = time.perf_counter() - t
    verifier('prepare : cache reutilise', t2 < 1.0 and reel['cutouts']['c3'] == cut, f'{t1:.1f} s puis {t2:.2f} s')
    reel['design']['mode'] = 'editorial'
    detourage.prepare(reel)
    verifier('prepare : Editorial partage le meme cache', reel['cutouts']['c3']['frames'] == cut['frames'])
    autre = copy.deepcopy(reel)
    autre['design'] = {'mode': 'hormozi'}
    autre['cutouts'] = {'garde': 1}
    detourage.prepare(autre)
    verifier('prepare : style sans detourage inchange', autre['cutouts'] == {'garde': 1})
    produit_simple = copy.deepcopy(reel)
    produit_simple['design'] = {'mode': 'produit'}
    verifier('prepare : produit non cinematique sans detourage', not detourage.needs_cutout(produit_simple))


def test_sans_personne(detourage):
    """Plan de coupe sans personne (graphique pixabay 20833) : tout doit etre marque pour le repli."""
    import shutil
    nom = 'projects/_cache/optimises/pixabay-video-20833-dc0514bd.mp4'
    copie = BAC / nom
    if not copie.exists():
        shutil.copy2(VRAI / nom, copie)
    doc = detourage.cutout(copie, 2.0, 3.0, 30)
    verifier('sans personne : score nul et repli sur toute la plage', doc.get('score') == 0 and doc.get('fallback') == [[2.0, 3.0]],
             {k: doc.get(k) for k in ('score', 'fallback', 'width', 'height')})


def test_memoire_pleine(detourage, rvm, proxy):
    """Carte graphique pleine pendant le calcul (autre moteur) : nouvel essai avec le petit modele, sans MediaPipe."""
    import shutil
    cle = detourage._cle(proxy, 6.5, 7.0, 30, detourage.VERSION)
    for p in (detourage.ROOT / 'assets/detourage').glob(cle + '*'):
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    vrai_run = rvm.Matteur.run

    def run_plein(self, *a, **k):
        if self.modele == 'resnet50':
            raise RuntimeError('CUDA out of memory. Tried to allocate 2.00 GiB (simulation)')
        return vrai_run(self, *a, **k)
    rvm.Matteur.run = run_plein
    try:
        doc = detourage.cutout(proxy, 6.5, 7.0, 30)
    finally:
        rvm.Matteur.run = vrai_run
    verifier('memoire pleine : petit modele utilise', doc.get('engine') == 'rvm-mobilenetv3' and doc['count'] == 15,
             {k: doc.get(k) for k in ('engine', 'count')})


def test_repli(detourage, rvm, proxy):
    ancien = rvm.MODELES
    rvm.MODELES = Path(detourage.ROOT) / 'models' / 'absent'
    try:
        doc = detourage.cutout(proxy, 6.0, 6.5, 30)
    finally:
        rvm.MODELES = ancien
    verifier('repli : ancien detourage si RVM absent', doc['file'].endswith('.webm') and 'engine' not in doc and doc['count'] == 15, doc)


def main():
    reel = json.loads((VRAI / 'docs/direction-creative-v2/tests/fixtures/projects/script1/reels/script.json').read_text(encoding='utf-8'))  # copie figee (jamais projects/)
    src = reel['sources']['t02']
    os.environ['EDITEUR_ROOT'] = str(BAC)
    proxy = T.bac_a_sable(BAC, src['proxy'])
    sys.path.insert(0, str(VRAI / 'engine'))
    from editeur import detourage, detourage_rvm
    assert detourage.ROOT == BAC, 'le moteur doit ecrire dans le bac a sable'
    test_score(detourage_rvm)
    test_affinage(detourage_rvm)
    test_prepare(detourage, reel)
    test_sans_personne(detourage)
    test_memoire_pleine(detourage, detourage_rvm, proxy)
    test_repli(detourage, detourage_rvm, proxy)
    ok = sum(r for _, r in RESULTATS)
    print(f'{ok}/{len(RESULTATS)} verifications reussies')
    return 0 if ok == len(RESULTATS) else 1


if __name__ == '__main__':
    sys.exit(main())
