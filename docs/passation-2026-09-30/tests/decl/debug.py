import json
import sys
from pathlib import Path

sys.path.insert(0, r'D:\Tools\editeur_sami\engine')
from editeur import declinaison, montage  # noqa: E402

BOX = Path(r'D:\Tools\editeur_sami\runtime\cache\tmp\decl-reancrage\video1')
base = montage.load(str(BOX), 'v1')
new = montage.load(str(BOX), sys.argv[1] if len(sys.argv) > 1 else 'v1-30-s')
m, n = montage.compute(base), montage.compute(new)
c = declinaison._Carte(m, n)
for t in [float(x) for x in sys.argv[2:]]:
    a = c.anchor(t)
    da = c.new(a)
    print('t', t, 'anchor', a, 'derived', da, 'exact', c.exact(t))
    print('   place', c.place(t, 0))
    s = declinaison._seg_at(c.bs, t)
    print('   base seg', s)
    print('   derived segs same clip', [d for d in c.ds if d['clip'] == s['clip']])
