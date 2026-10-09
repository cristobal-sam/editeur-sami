"""Relecture Fable (2026-09-30) : essais du moteur sur des COPIES en memoire des montages (rien n'est ecrit dans
projects\\, aucune IA lancee). Lancer depuis engine\\ avec l'environnement charge :
    python ..\\docs\\taches-fable\\tests\\revue_moteur.py
"""
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'engine'))
os.environ['EDITEUR_LLM'] = '0'
sys.stdout.reconfigure(encoding='utf-8')

from editeur import llm  # noqa: E402

llm.available = lambda: False  # aucune IA locale pendant ces essais

from editeur import auto, derush, galerie, graphismes, montage, sobriete  # noqa: E402
from editeur import reel as R  # noqa: E402
from editeur.script import normalize  # noqa: E402

REELS = {'script1': ROOT / 'projects/script1/reels/script.json',
         'video1video1': ROOT / 'projects/video1video1/reels/script.json'}
ORIGINE = ROOT / 'runtime/cache/tmp/habillage-sobriete-7k2/script1-auto-origine.json'
fails = []


def check(ok, msg):
    print(('OK    ' if ok else 'ECHEC ') + msg)
    if not ok:
        fails.append(msg)


def load(name):
    return json.loads(REELS[name].read_text(encoding='utf-8'))


def hl_stats(reel):
    total = sum(1 for c in reel['clips'] for w in c['words'] if not (w.get('cut') or w.get('hide')))
    on = [w['w'].strip(' ,.!?') for c in reel['clips'] for w in c['words'] if w.get('hl')]
    return total, on


print('=== 1. Mots en couleur (rehighlight, regles seules) ===')
for name in REELS:
    r = load(name)
    total, before = hl_stats(r)
    R.rehighlight(r)
    total, after = hl_stats(r)
    print(f'{name} : {len(before)}/{total} -> {len(after)}/{total} ({100 * len(after) / total:.1f} %) : {" | ".join(after)}')
    check(len(after) / total <= 0.12, f'{name} : au plus 12 % de mots en couleur')
    small = [w for w in after if normalize(w).split("'")[-1] in R.STOP]
    # un petit mot peut faire partie d'un bloc (« En savoir plus ») ; seul, non
    alone = []
    for c in r['clips']:
        ws = c['words']
        for i, w in enumerate(ws):
            if w.get('hl') and normalize(w['w'].strip(' ,.!?')).split("'")[-1] in R.STOP \
                    and not (i and ws[i - 1].get('hl')) and not (i + 1 < len(ws) and ws[i + 1].get('hl')):
                alone.append(w['w'])
    check(not alone, f'{name} : aucun petit mot colore seul ({alone})')
    again = copy.deepcopy(r)
    R.rehighlight(again)
    check(hl_stats(again)[1] == after, f'{name} : deuxieme passage identique (stable)')
    # retouches a la main : un mot colore a la main reste, un mot decolore a la main ne revient pas
    c = next(c for c in r['clips'] if any(w.get('hl') for w in c['words']) and len(c['words']) > 8)
    off = next(i for i, w in enumerate(c['words']) if w.get('hl'))
    on = next(i for i, w in enumerate(c['words']) if not w.get('hl') and len(w['w']) > 5 and abs(i - off) > 6)
    c['words'][off]['hl'], c['words'][on]['hl'] = False, True
    R.rehighlight(r)
    check(c['words'][on]['hl'] and not c['words'][off]['hl'], f'{name} : retouches a la main gardees')

print('\n--- cas limites ---')
base = load('script1')
for label, clips in [
    ('aucun plan', []),
    ('plan sans mot', [{**base['clips'][0], 'words': []}]),
    ('un seul mot', [{**base['clips'][0], 'words': base['clips'][0]['words'][:1]}]),
    ('tous les mots masques', [{**base['clips'][0], 'words': [{**w, 'hide': True} for w in base['clips'][0]['words']]}]),
    ('mots sans champ hl', [{**base['clips'][0], 'words': [{k: v for k, v in w.items() if k != 'hl'} for w in base['clips'][0]['words']]}]),
]:
    r = {**copy.deepcopy(base), 'clips': copy.deepcopy(clips)}
    r.pop('hlAuto', None)
    try:
        R.rehighlight(r)
        R.key_blocks(r)
        check(True, f'rehighlight / key_blocks : {label}')
    except Exception as e:
        check(False, f'rehighlight / key_blocks : {label} -> {type(e).__name__}: {e}')
en = [{'w': x, 'start': i * 0.3, 'end': i * 0.3 + 0.25, 'hl': False} for i, x in enumerate(
    'Your competitor calls the lead back in three hours. We do it five times faster, for free. Click the button below.'.split())]
r = {**copy.deepcopy(base), 'clips': [{**base['clips'][0], 'words': en}]}
r.pop('hlAuto', None)
R.rehighlight(r)
print('anglais :', ' | '.join(w['w'] for w in r['clips'][0]['words'] if w.get('hl')), '| langue :', R.reel_language(r))
check(R.reel_language(r) == 'en', 'langue anglaise devinee')

print('\n=== 2. Styles de la galerie (apply_template, sans IA) + relecture (comme si le §3.2 etait branche) ===')
for tid in ['editorial-cinetique', 'hormozi', 'collage', 'tech-application', 'infographie', 'documentaire', 'reel-karaoke',
            'reel-impact', 'podcast-clip']:
    r = load('script1')
    try:
        R.apply_template(r, tid)
    except Exception as e:
        check(False, f'{tid} : apply_template -> {type(e).__name__}: {e}')
        continue
    times = galerie._times(r)
    scenes = r.get('styleScenes') or []
    txt = [f"{s['kind']}:{s['text']}@{times.get((s['clip'], s['index']), -1):.1f}{'(masque)' if s.get('hidden') else ''}" for s in scenes]
    _, on = hl_stats(r)
    print(f'{tid} : {len(on)} mots en couleur ; scenes : {txt}')
    check(not any(galerie.TECH_LABEL.search(str(s.get('text', '')) + str(s.get('secondary', ''))) for s in scenes), f'{tid} : aucune etiquette technique')
    check(not any('…' in str(s.get('text')) for s in scenes), f'{tid} : aucun texte coupe')
    texts = [normalize(s['text']) for s in scenes if not s.get('hidden') and s['kind'] in ('keyword', 'paper')]
    check(len(texts) == len(set(texts)), f'{tid} : pas deux fois le meme mot en habillage')
    if tid in ('editorial-cinetique', 'collage'):
        check(any(normalize(s['text']) == 'troisheures' for s in scenes), f'{tid} : « trois heures » choisi')
    if tid == 'hormozi':
        check('trois' in [normalize(x) for x in on] and 'attend' not in [normalize(x) for x in on], 'hormozi : « trois heures » en couleur, pas « attend »')
    try:
        rep = sobriete.relire(r, tid)
        print('   relecture :', rep['resume'], '|', ' / '.join(rep['retires'][:3]))
    except Exception as e:
        check(False, f'{tid} : relire -> {type(e).__name__}: {e}')

print('\n=== 3. Relecture du monteur (sobriete) ===')
orig = json.loads(ORIGINE.read_text(encoding='utf-8'))
r = copy.deepcopy(orig)
seg = montage.compute(r)
rep = sobriete.relire(r, 'reel-impact', seg=seg, tout=True)
print('reel d\'origine :', rep['resume'])
print('   reperes :', rep['reperes'])
for line in rep['retires'] + rep['deplaces'] + rep['corriges']:
    print('   -', line)
els = sobriete._elements(r, montage.compute(r))
check(not [e for e in els if e['at'] < rep['reperes']['accroche']], 'rien pendant l\'accroche')
els.sort(key=lambda e: e['at'])
check(all(b['at'] - a['fin'] >= 3.99 for a, b in zip(els, els[1:])), 'au moins 4 s entre deux elements')

# 3a. bandeau regle sur « Toute la video » (banner.end = null, bouton de l'onglet Style)
r = copy.deepcopy(orig)
r['banner'] = {'enabled': True, 'text': 'VOTRE CONCURRENT VOUS BAT', 'start': 0, 'end': None}
rep = sobriete.relire(r, 'reel-impact', seg=seg, tout=True)
print('bandeau « toute la video » :', rep['resume'])
check(rep['gardes'] > 0, 'bandeau toute la video : il reste des elements (sinon le bandeau bloque tout)')
r = copy.deepcopy(orig)
r['banner'] = {'enabled': True, 'text': 'VOTRE CONCURRENT VOUS BAT', 'start': 0, 'end': 4.5}
rep2 = sobriete.relire(r, 'reel-impact', seg=seg, tout=True)
print('meme bandeau jusqu\'a 4,5 s      :', rep2['resume'])

# 3b. un mot d'appel a l'action (« contacte ») dit au milieu de la video
words, t = [], 0.0
for k, sentence in enumerate([
        'Vos leads attendent trop longtemps.', 'Chaque minute perdue coûte un client.',
        'Chez nous un agent contacte vos leads en cinq minutes.', 'Vos ventes montent dès la première semaine.',
        'Votre équipe garde son temps pour vendre.', 'Vos clients sont rappelés le soir même.',
        'Essayez gratuitement dès aujourd\'hui.']):
    for x in sentence.split():
        words.append({'w': x, 'start': round(t, 2), 'end': round(t + 0.3, 2), 'clip': 'c1', 'index': len(words)})
        t += 0.35
    t += 1.0
fake_seg = {'duration': round(t, 2), 'words': words}
rep = sobriete.reperes({'clips': [{'id': 'c1', 'block': 'b1'}]}, fake_seg)
last = [w for w in words if w['w'] == 'Essayez'][0]['start']
print(f"appel a l'action au milieu : duree {fake_seg['duration']} s, reperes {rep} (derniere phrase a {last} s)")
check(rep['cta'] is None or rep['cta'] >= last - 0.01, 'la zone « appel a l\'action » ne commence pas au milieu de la video')

# 3c. emoji pose a la main, puis changement de style (tout=False)
r = load('script1')
R.apply_template(r, 'reel-karaoke')
for c in r['clips']:
    c['emojis'] = []
r['clips'][0]['emojis'] = [[1, '🔥']]  # pose a la main dans l'onglet Texte, sur l'accroche
rep = sobriete.relire(r, 'reel-karaoke')
print('emoji a la main :', rep['resume'], rep['retires'][:1])
check(r['clips'][0]['emojis'] == [[1, '🔥']], 'un emoji pose a la main n\'est pas retire par la relecture (tout=False)')

# 3d. montage sans parole (immobilier) : le bandeau = l'adresse
fake = {'banner': {'enabled': True, 'text': '12 RUE DES ÉRABLES', 'start': 0.3, 'end': 4.0}, 'suggestions': {'banners': []}, 'clips': []}
check(auto._banner_ok(fake), 'bandeau-adresse d\'un montage immobilier garde par le montage automatique')

print('\n=== 4. Bandeau, titres, graphismes ===')
first = ' '.join(w['w'] for w in load('script1')['clips'][0]['words'][:9])
for text, want in [('Plus vous prenez de temps à appeler un…', False), ('VOTRE CONCURRENT PRISE LE LEAD', False),
                   ('VOTRE CONCURRENT CLOSE VOS LEADS', None)]:
    r = load('script1')
    r['banner'] = {'enabled': True, 'text': text, 'start': 0, 'end': 4.5}
    r['suggestions'] = {**(r.get('suggestions') or {}), 'banners': [text]}
    got = auto._banner_ok(r)
    print(f'   bandeau « {text} » -> {got}')
    if want is not None:
        check(got == want, f'bandeau « {text} » refuse')
for title, folder, want in [('Script 1', ROOT / 'media/entree/Lot 2026-09-30 10h51/Vidéo 1', 'Vidéo 1'), ('SCRIPT 2', None, 'Vidéo 2'),
                            ('Script 3', Path('Lot 2026-09-30 10h45'), 'Vidéo 3'), ('Offre de Noël', Path('x'), 'Offre de Noël'),
                            ('', None, 'Vidéo'), ('Script 1', Path('pub1.mp4'), 'pub1')]:
    got = derush.nice_label(title, folder)
    check(got == want, f'titre « {title} » + dossier {folder.name if folder else None} -> « {got} »')
w = [{'w': x, 'start': i, 'end': i + 0.5} for i, x in enumerate("cinq fois moins cher qu'un employé".split())]
check(graphismes._label(w, 2) == 'MOINS CHER', f'libelle « {graphismes._label(w, 2)} »')
w = [{'w': x, 'start': i, 'end': i + 0.5} for i, x in enumerate('trois heures a déjà été'.split())]
check(graphismes._label(w, 2) == '', 'pas de libelle coupe (« a deja ete »)')

# graphismes proposes pour script1 (copie dans le bac a sable, aucune IA)
box = ROOT / 'runtime/cache/tmp/revue-fable/script1'
(box / 'reels').mkdir(parents=True, exist_ok=True)
r = load('script1')
R.apply_template(r, 'reel-impact')
r['graphics'], r['broll'] = [], []
(box / 'reels/script.json').write_text(json.dumps(r, ensure_ascii=False), encoding='utf-8')
found = graphismes.suggest(box, 'script')
for g in found:
    print('   graphisme :', g['kind'], g['at'], g['props'], g['confiance'], '|', g['raison'])
check(not any(g['at'] < 3 for g in found), 'aucun graphisme propose pendant l\'accroche')
check(not any('ÉTÉ' in str(g['props'].get('label', '')).upper() or "QU'" in str(g['props'].get('label', '')).upper() for g in found), 'aucun libelle coupe')

print('\n' + ('TOUT EST BON' if not fails else f'{len(fails)} ECHEC(S) :\n - ' + '\n - '.join(fails)))
