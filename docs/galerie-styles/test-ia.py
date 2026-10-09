"""Un appel Qwen local réel, sur la copie synthétique ; erreurs non masquées."""
import json
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'engine'))
os.environ['EDITEUR_LLM']='1'
from editeur import galerie,llm
r=json.loads((ROOT/'docs/galerie-styles/tests/tech-application-apercu.json').read_text(encoding='utf-8'))
original=llm.ask_json
calls=[]
def tracked(*args,**kwargs):
    response=original(*args,**kwargs)
    calls.append(response)
    return response
llm.ask_json=tracked
galerie.prepare(r)
assert calls, 'Aucune réponse Qwen reçue : ne pas confondre repli et test IA réussi.'
assert isinstance(calls[0].get('indices'),list),calls
assert r['styleScenes'], 'Aucune scène pertinente retenue.'
for s in r['styleScenes']:
    c=next(c for c in r['clips'] if c['id']==s['clip'])
    assert 0<=s['index']<len(c['words'])
print(json.dumps({'reponseQwen':calls,'scenes':r['styleScenes']},ensure_ascii=False))
