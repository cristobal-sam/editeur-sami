import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
BOX=ROOT/'runtime/cache/tmp/musique-eval'
data=np.load(BOX/'spectres.npz')
cases=json.loads((BOX/'cas.json').read_text())
pos=[]
for c in cases:
    m=data[f"{c['id']}|mel"]
    level=m[3:45].sum(axis=0)
    keep=level<=np.quantile(level,.15)
    low=np.median(m[:,keep],axis=1)
    # fond vs voix, platitude spectrale du fond, concentration chromatique
    ratio=10*np.log10((low.sum()+1e-12)/(m.sum(axis=0).mean()+1e-12))
    flat=np.exp(np.mean(np.log(low+1e-12)))/(low.mean()+1e-12)
    ch=data[f"{c['id']}|chr"][:,keep].mean(axis=1)
    tone=ch.max()/ch.mean()
    row=(round(ratio,2),round(flat,3),round(tone,2))
    if not c['musique']: print(c['id'],row)
    elif c['voix']: pos.append(row)
print('music percentiles',np.percentile(pos,[0,10,25,50,90],axis=0))
