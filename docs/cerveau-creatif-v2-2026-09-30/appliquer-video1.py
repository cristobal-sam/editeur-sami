"""Attache le plan V2 au montage de référence sans refaire ni exporter la vidéo."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'engine'))

from editeur import creative, galerie, montage, reel
from editeur import sobriete

project = ROOT / 'projects/script1'
doc = montage.load(project, 'script')
template = next(t for t in reel.list_templates() if t['id'] == doc.get('template'))
creative.apply(doc, doc.get('auto'), template)
galerie.prepare(doc, use_ai=False)
report = sobriete.relire(doc, template, tout=False)
doc['sobriete'] = {k: report[k] for k in ('retires', 'deplaces', 'corriges', 'gardes', 'resume')}
creative.direct_scenes(doc, doc.get('styleScenes') or [], galerie._times(doc))
montage.save(project, 'script', doc)
print(doc['creativePlan']['summary'])
print(f"{len(doc['creativePlan']['beats'])} temps narratifs attachés ; aucun export lancé.")
