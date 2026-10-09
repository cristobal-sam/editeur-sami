"""Test du reancrage des declinaisons (bac a sable, jamais dans projects/)."""
import json
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, r'D:\Tools\editeur_sami\engine')
from editeur import declinaison, llm, montage  # noqa: E402

SRC = Path(r'D:\Tools\editeur_sami\projects\video1\reels\v1.json')
BOX = Path(tempfile.mkdtemp(prefix='decl-verification-', dir=r'D:\Tools\editeur_sami\runtime\cache\tmp')) / 'video1'
use_llm = '--llm' in sys.argv
secs = next((float(a.split('=')[1]) for a in sys.argv if a.startswith('--duree=')), 30.0)
intent = next((a.split('=')[1] for a in sys.argv if a.startswith('--intention=')), None)
if not use_llm:
    llm.available = lambda: False

(BOX / 'reels').mkdir(parents=True)
reel = json.loads(SRC.read_text(encoding='utf-8'))
m = montage.compute(reel)
words = sorted(m['words'], key=lambda w: w['start'])
total = m['duration']
key = {(w['clip'], w['index']): w for w in words}

# phrases (comme declinaison.create)
sents = []
for c in reel['clips']:
    for i0, i1 in montage.sentences(c):
        ws = [key[(c['id'], i)] for i in range(i0, i1 + 1) if (c['id'], i) in key]
        if ws:
            sents.append({'clip': c['id'], 'block': c['block'], 'words': ws})
print('phrases', len(sents), 'duree', round(total, 2))

def mid(s):
    return s['words'][len(s['words']) // 2]

g, b, x = list(reel.get('graphics') or []), [], []
LONG = '--long' in sys.argv
for k, s in enumerate(sents):
    w = mid(s)
    if LONG:
        g.append({'id': f't-L{k}', 'kind': 'coches', 'at': round(s['words'][-3]['start'], 2), 'duration': 4.4, 'props': {'title': f'L{k}'}})
        continue
    g.append({'id': f't-g{k}', 'kind': 'motgeant', 'at': round(w['start'] - 0.1, 2), 'duration': 0.9, 'props': {'text': w['w'].upper()}})
    b.append({'id': f't-b{k}', 'source': reel['clips'][0]['source'], 'in': 1.0, 'at': round(s['words'][1]['start'] - 0.15, 2), 'duration': 1.8,
              'word': s['words'][1]['w']})
    x.append({'t': round(s['words'][-2]['start'], 2), 'name': 'pop'})
# graphisme long a cheval sur deux phrases (fin de la phrase 3 -> phrase 4)
s3 = sents[3]['words']
g.append({'id': 't-long', 'kind': 'coches', 'at': round(s3[-3]['start'], 2), 'duration': 4.4, 'props': {'items': ['a', 'b'], 'title': 'Long'}})
# logo de fin, graphisme dans l'appel a l'action (1re phrase du bloc)
g.append({'id': 't-logo', 'kind': 'logo', 'at': round(total - 2.0, 2), 'duration': 2.0, 'props': {}})
cta = [s for s in sents if s['block'] == reel['ctaBlock']]
g.append({'id': 't-cta', 'kind': 'carte', 'at': round(cta[0]['words'][2]['start'], 2), 'duration': 2.0, 'props': {'title': 'Appel'}})
reel['graphics'] = g
reel['broll'] = b
reel['sfx']['extra'] = x
reel['banner'] = {**reel['banner'], 'enabled': True, 'start': 0, 'end': 4.5}
reel['zoom']['overrides'] = {str(s['index']): 1.3 for s in m['video']}
(BOX / 'reels' / 'v1.json').write_text(json.dumps(reel, ensure_ascii=False), encoding='utf-8')

res = declinaison.create(str(BOX), 'v1', seconds=secs or None, intention=intent)
print(json.dumps({k: v for k, v in res.items() if k != 'elements'}, ensure_ascii=False, indent=1))
new = montage.load(str(BOX), res['rid'])
n = montage.compute(new)
ntotal = n['duration']
bc = declinaison._Carte(m, m)
dc = declinaison._Carte(n, n)
cut_keys = {k for k in key if k not in {(w['clip'], w['index']) for w in n['words']}}
errors = []
reported = {e['element'] + '@' + str(e['avant']): e for part in ('retires', 'raccourcis', 'deplaces') for e in res['elements'][part]}

def check(track, olds, news, at='at', dur='duration', name=lambda o: o['id']):
    byid = {o['id']: o for o in news} if track != 'sfx' else None
    for k, o in enumerate(olds):
        nw = byid.get(o['id']) if byid is not None else None
        a = bc.anchor(o[at])
        if nw is None and byid is not None:
            why = 'coupe' if (a['clip'], a['index']) in cut_keys else 'AUTRE'
            print(f'  {track} {name(o)} retire ({why})')
            continue
        if nw is None:
            continue
        if nw[at] + nw.get(dur, 0) > ntotal + 1e-3:
            errors.append(f'{track} {name(o)} depasse la fin {nw[at]} + {nw.get(dur)} > {ntotal}')
        endtie = o[at] + o.get(dur, 0) >= total - 0.25
        if (a['clip'], a['index']) in cut_keys and not endtie:
            # mot coupe mais element garde : seulement le logo et les graphismes de l'appel a l'action
            ok = o.get('kind') == 'logo' or o[at] >= cta[0]['words'][0]['start'] - 0.3
            print(f'  {track} {name(o)} {o[at]:.2f}->{nw[at]:.2f} dur {o.get(dur, 0):.2f}->{nw.get(dur, 0):.2f} garde (appel a l action / logo)', 'OK' if ok else 'ERREUR')
            if not ok:
                errors.append(f'{track} {name(o)} garde alors que son mot est coupe')
            continue
        if track != 'sfx' and nw.get(dur) and not endtie:
            inv = {(w['clip'], w['index']): w for w in words}
            extra = [w for w in n['words'] if nw[at] + 0.02 <= w['start'] < nw[at] + nw[dur] - 0.05
                     and not (o[at] - 0.6 <= inv[(w['clip'], w['index'])]['start'] <= o[at] + o[dur] + 0.1)]
            if extra:
                held = nw[dur] <= declinaison.MIN_HOLD.get(o.get('kind', 'broll'), 1.2) + 1e-6
                msg = f'{track} {name(o)} recouvre {len(extra)} mot(s) d une autre phrase ({extra[0]["w"]})'
                if held:
                    print('    (maintien minimal)', msg)
                else:
                    errors.append(msg)
        da = dc.anchor(nw[at])
        same = (a['clip'], a['index']) == (da['clip'], da['index'])
        tag = 'meme mot' if same else f"AUTRE MOT {a['w']}->{da['w']}"
        print(f'  {track} {name(o)} {o[at]:.2f}->{nw[at]:.2f} dur {o.get(dur, 0):.2f}->{nw.get(dur, 0):.2f} {tag}')
        if not same and not endtie and track != 'broll':
            errors.append(f'{track} {name(o)} ne commence plus sur le meme mot')

print('graphismes :')
check('graphics', g, new.get('graphics') or [])
print('plans de coupe :')
check('broll', b, new.get('broll') or [])
print('bruitages :')
nx = new['sfx']['extra']
kept_sfx = 0
for e in x:
    a = bc.anchor(e['t'])
    cutw = (a['clip'], a['index']) in cut_keys
    if not cutw:
        want = dc.dw[(a['clip'], a['index'])]
        hits = [y for y in nx if (lambda d: (d['clip'], d['index']) == (a['clip'], a['index']))(dc.anchor(y['t']))]
        if not hits:
            errors.append(f'bruitage {e} perdu alors que son mot est garde')
        else:
            kept_sfx += 1
print('  gardes', len(nx), 'sur', len(x), '; verifies sur le meme mot', kept_sfx, '; mots coupes', sum(1 for e in x if (bc.anchor(e['t'])['clip'], bc.anchor(e['t'])['index']) in cut_keys))
print('bandeau', new['banner'])
print('zooms', len(reel['zoom']['overrides']), '->', len(new['zoom']['overrides']), 'segments', len(m['video']), '->', len(n['video']))
for k2 in new['zoom']['overrides']:
    if int(k2) >= len(n['video']):
        errors.append(f'zoom sur un segment inexistant {k2}')
# plans de coupe hors accroche / dernier appel
hook = [(w['clip'], w['index']) for w in sents[0]['words']]
last = [(w['clip'], w['index']) for w in cta[-1]['words']]
for z, nm in ((hook, 'accroche'), (last, 'appel')):
    ws = [dc.dw[k] for k in z if k in dc.dw]
    z0, z1 = min(w['start'] for w in ws), max(w['end'] for w in ws)
    for bb in new.get('broll') or []:
        if bb['at'] < z1 and bb['at'] + bb['duration'] > z0:
            errors.append(f'plan de coupe {bb["id"]} sur {nm} {bb["at"]}-{bb["at"] + bb["duration"]} / {z0:.2f}-{z1:.2f}')
for nm, z in (('accroche', hook), ("derniere phrase de l'appel", last)):
    lost = [k for k in z if k not in dc.dw]
    print(f'{nm} : {len(z) - len(lost)}/{len(z)} mots gardes')
    if lost:
        errors.append(f'{nm} : {len(lost)} mots perdus')
print('fin', round(ntotal, 2), '(visee', secs, ')')
if secs and ntotal > secs + 1e-6:
    errors.append('duree au-dessus de la cible')
print('messages :')
for s in res['elements_resume']:
    print('  -', s)
print('ERREURS :' if errors else 'AUCUNE ERREUR', *errors, sep='\n  ')
sys.exit(1 if errors else 0)
