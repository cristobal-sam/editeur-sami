import sys, time, traceback
from pathlib import Path
sys.path.insert(0, r'D:\Tools\editeur_sami\engine')
from editeur import declinaison, llm, montage
BOX = Path(r'D:\Tools\editeur_sami\runtime\cache\tmp\decl-reancrage\video1')
reel = montage.load(str(BOX), 'v1')
items = []
for c in reel['clips']:
    for i0, i1 in montage.sentences(c):
        ws = c['words'][i0:i1 + 1]
        items.append({'text': ' '.join(w['w'] for w in ws)})
numbered = '\n'.join(f'{k}. {it["text"]}' for k, it in enumerate(items))
t = time.time()
try:
    with llm.session():
        data = llm.ask_json(llm.EDITOR,
                            f'Voici les phrases d\'une publicite video, dans l\'ordre :\n{numbered}\n\n'
                            'Note l\'importance de chaque phrase pour convaincre (10 = indispensable : promesse, preuve, '
                            'chiffre, benefice principal ; 1 = accessoire, repetition, transition). '
                            'Reponds {"notes": [n0, n1, ...]} avec une note par phrase, dans l\'ordre.', temperature=0.0)
    print('data', data, round(time.time() - t, 1))
except Exception:
    traceback.print_exc()
