import sys
import time
from pathlib import Path

sys.path.insert(0, r'D:\Tools\editeur_sami\engine')
from editeur import declinaison, llm, montage  # noqa: E402

BOX = Path(r'D:\Tools\editeur_sami\runtime\cache\tmp\decl-reancrage\video1')
reel = montage.load(str(BOX), 'v1')
items = []
for c in reel['clips']:
    for i0, i1 in montage.sentences(c):
        ws = c['words'][i0:i1 + 1]
        items.append({'clip': c, 'i0': i0, 'i1': i1, 'words': ws, 'text': ' '.join(w['w'] for w in ws)})
print('llm.available', llm.available(), 'alive', llm._alive())
t = time.time()
real = llm.available
llm.available = lambda: False
rules = declinaison._importance(reel, items)
llm.available = real
t = time.time()
try:
    with llm.session():
        data = llm.ask_json(llm.EDITOR, 'Reponds {"ok": 1}', temperature=0.0)
    print('reponse directe', data, round(time.time() - t, 1), 's')
except Exception as e:
    print('ERREUR IA', type(e).__name__, e)
notes = declinaison._importance(reel, items)
print('regles', rules)
print('avec IA', [round(n, 2) for n in notes], round(time.time() - t, 1), 's')
