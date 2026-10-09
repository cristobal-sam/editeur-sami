"""Étape 5 (Fable, 2026-09-30) : contrôle des montages refaits (lecture seule des vrais reels).
Depuis engine\\ avec l'environnement chargé : python ..\\docs\\taches-fable\\tests\\etape5_verif.py script1 video1video1
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'engine'))
os.environ['EDITEUR_LLM'] = '0'
sys.stdout.reconfigure(encoding='utf-8')
from editeur import llm  # noqa: E402

llm.available = lambda: False
from editeur import montage, sobriete  # noqa: E402
from editeur import reel as R  # noqa: E402
from editeur.script import normalize  # noqa: E402

fails = []


def check(ok, msg):
    print(('OK    ' if ok else 'ECHEC ') + msg)
    if not ok:
        fails.append(msg)


for name in sys.argv[1:] or ['script1', 'video1video1']:
    f = ROOT / 'projects' / name / 'reels' / 'script.json'
    r = json.loads(f.read_text(encoding='utf-8'))
    print(f'\n=== {name} : « {r.get("title")} », style {r.get("template")}, {r.get("width")}x{r.get("height")} ===')
    total = sum(1 for c in r['clips'] for w in c['words'] if not (w.get('cut') or w.get('hide')))
    visible = [[w for w in c['words'] if not (w.get('cut') or w.get('hide'))] for c in r['clips']]
    on = [w['w'].strip(' ,.!?') for words in visible for w in words if w.get('hl')]
    # Une expression (« cinq fois moins cher », « En savoir plus ») est une seule mise en avant.
    # Le plafond de 12 % porte toujours sur TOUS ses mots, pas sur le nombre d'expressions.
    highlighted = sum(1 for words in visible for i, w in enumerate(words)
                      if w.get('hl') and (i == 0 or not words[i - 1].get('hl')))
    ideas = sum(len(R.idea_groups(c['words'])) for c in r['clips'])
    print(f'mots en couleur : {len(on)}/{total} ({100 * len(on) / max(1, total):.1f} %) pour {ideas} idées : {" | ".join(on)}')
    check(highlighted <= ideas + 2 and len(on) / max(1, total) <= 0.12,
          f'environ une expression en couleur par idée ({highlighted}/{ideas} ; mots ≤ 12 %)')
    alone = [w for c in r['clips'] for i, w in enumerate(c['words']) if w.get('hl')
             and normalize(w['w'].strip(' ,.!?')).split("'")[-1] in R.STOP
             and not (i and c['words'][i - 1].get('hl')) and not (i + 1 < len(c['words']) and c['words'][i + 1].get('hl'))]
    check(not alone, f'aucun petit mot coloré seul {[w["w"] for w in alone]}')
    seg = montage.compute(r)
    rep = sobriete.reperes(r, seg)
    els = sorted(sobriete._elements(r, seg), key=lambda e: e['at'])
    print('repères :', rep)
    print('éléments visibles :', [(e['type'], e['kind'], round(e['at'], 1), e.get('texte')) for e in els])
    check(not [e for e in els if e['at'] < rep['accroche']], "rien pendant l'accroche (sauf le bandeau)")
    check(all(b['at'] >= a['fin'] for a, b in zip(els, els[1:])), 'jamais deux éléments en même temps')
    check(not any(b.get('auto') for b in r.get('broll') or []) and not r.get('broll'), 'aucun plan de coupe ajouté tout seul')
    check(str(r.get('title', '')).startswith('Vidéo'), f'titre « {r.get("title")} »')
    banner = r.get('banner') or {}
    print('bandeau :', banner.get('enabled'), repr(banner.get('text')), '| relecture :', (r.get('sobriete') or {}).get('resume'))
    check(not (banner.get('enabled') and str(banner.get('text', '')).endswith(('…', '...'))), 'pas de bandeau coupé par « … »')
    sug = r.get('suggestions') or {}
    print('propositions : bandeaux', len(sug.get('banners') or []), '| graphismes proposés',
          len([g for g in r.get('graphics') or [] if g.get('suggested')]), '| posés', len([g for g in r.get('graphics') or [] if not g.get('suggested')]))

print('\n' + ('TOUT EST BON' if not fails else f'{len(fails)} ECHEC(S) :\n - ' + '\n - '.join(fails)))
sys.exit(1 if fails else 0)
