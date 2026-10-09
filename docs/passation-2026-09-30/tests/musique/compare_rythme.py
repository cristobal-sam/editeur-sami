import json
from pathlib import Path
import numpy as np
from scipy.ndimage import uniform_filter1d
ROOT = Path(__file__).resolve().parents[4]
BOX = ROOT / 'runtime/cache/tmp/musique-eval'
data = np.load(BOX / 'spectres.npz')
cases = json.loads((BOX / 'cas.json').read_text(encoding='utf-8'))
moods = json.loads((ROOT / 'styles/musiques.json').read_text(encoding='utf-8'))
fps = 22050/512

def rhythm(m):
    log = 10*np.log10(np.maximum(m,1e-10))
    spread = np.percentile(log,90,axis=1)-np.percentile(log,10,axis=1)
    weight = np.exp(-spread/12)
    weight *= np.r_[np.ones(3)*2, np.ones(48)*.3, np.ones(13)*2]
    env = np.average(np.maximum(np.diff(log),0),axis=0,weights=weight)
    env = np.maximum(env-uniform_filter1d(env,17),0)
    fft = np.abs(np.fft.rfft((env-env.mean())*np.hanning(len(env)),n=16384))
    freq = np.fft.rfftfreq(16384,1/fps)
    grid = np.arange(55,201,.2)
    sal = sum(w*np.interp(grid*k/60,freq,fft) for k,w in ((1,1),(2,.5),(4,.25)))
    sal *= np.exp(-.5*(np.log2(grid/105)/.9)**2)
    i=sal.argmax()
    return grid[i], sal[i]/(np.median(sal)+1e-9)

rows=[]
for c in cases:
    tempo, clarity = rhythm(data[f"{c['id']}|mel"])
    rows.append({**c,'est':tempo,'clarity':clarity})
pos=[r for r in rows if r['musique']]
neg=[r for r in rows if not r['musique']]
for kind in ('sami1','sami2','bingo',None):
    sel=[r for r in pos if r['voix']==kind]
    good=sum(min(abs(r['est']*k-r['tempo'])/r['tempo'] for k in (.5,1,2))<.04 for r in sel)
    print(kind,good,len(sel), 'clarity', np.percentile([r['clarity'] for r in sel],[0,10,50,90]))
print('neg',[(r['id'],round(r['clarity'],2),round(r['est'])) for r in neg])
for r in rows: r.pop('words')
(BOX/'rythme-verification.json').write_text(json.dumps(rows),encoding='utf-8')
