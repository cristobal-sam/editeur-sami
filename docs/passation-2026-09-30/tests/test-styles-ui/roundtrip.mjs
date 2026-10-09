// Aller-retour : reglages d'un reel -> style enregistre (code du serveur) -> apply_template (moteur Python) -> memes reglages.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {execFileSync} from 'node:child_process';

const SRC = fs.readFileSync('D:/Tools/editeur_sami/app/server.mjs', 'utf8');
const SANDBOX = fs.mkdtempSync('D:/Tools/editeur_sami/runtime/cache/tmp/test-styles-roundtrip-');
fs.mkdirSync(SANDBOX, {recursive: true});
fs.cpSync('D:/Tools/editeur_sami/styles', path.join(SANDBOX, 'styles'), {recursive: true});
const block = SRC.slice(SRC.indexOf('// >>> styles-utilisateur'), SRC.indexOf('// <<< styles-utilisateur'));
const ctx = vm.createContext({fs, path, console, ROOT: SANDBOX, safeId: (s) => String(s), writeAtomic: (f, t) => fs.writeFileSync(f, t), CLIENTS: '', Date, JSON});
const {saveUserStyle} = vm.runInContext(`${block}\n;({saveUserStyle})`, ctx);

const reel = JSON.parse(fs.readFileSync('D:/Tools/editeur_sami/projects/video1/reels/v1.json', 'utf8'));
// reglages retouches « a la main » dans l'interface
reel.style = {...reel.style, maxWords: 5, size: 90, color: '#FF00AA', uppercase: true, position: 0.6};
reel.zoom = {...reel.zoom, auto: true, strength: 1.2, push: 0.04};
reel.music = {enabled: true, mood: 'electro', file: 'music/electro.ogg', volume: 0.33};
reel.sfx = {...reel.sfx, enabled: true, transition: 'glitch', highlight: 'pop', volume: 0.5};
reel.flash = {enabled: true, kind: 'glitch'};
reel.effects = {grain: 0.2, vignette: 0.3, grade: 'froid'};
reel.emoji = {enabled: true};
reel.progress = {enabled: true};
reel.banner = {...reel.banner, enabled: false};
const tpl = saveUserStyle(reel, {name: 'Aller retour'});
fs.writeFileSync(path.join(SANDBOX, 'reel.json'), JSON.stringify(reel));

const py = `
import json, os, sys
from editeur import reel as R
src = json.load(open(os.path.join(os.environ['EDITEUR_ROOT'], 'reel.json'), encoding='utf-8'))
out = R.apply_template(json.loads(json.dumps(src)), '${tpl.id}')
bad = []
for k in ('font', 'size', 'color', 'highlight', 'stroke', 'strokeWidth', 'position', 'maxWords', 'uppercase', 'pop', 'weight', 'preset'):
    if src['style'].get(k) != out['style'].get(k) and not (src.get('brand') and k in ('font', 'color', 'highlight', 'stroke')):
        bad.append(('style.' + k, src['style'].get(k), out['style'].get(k)))
for k in ('auto', 'strength', 'push'):
    if src['zoom'][k] != out['zoom'][k]: bad.append(('zoom.' + k, src['zoom'][k], out['zoom'][k]))
for k in ('flash', 'effects', 'emoji', 'progress'):
    if src[k] != out[k]: bad.append((k, src[k], out[k]))
if out['banner']['enabled'] != src['banner']['enabled']: bad.append(('banner', src['banner'], out['banner']))
for k in ('enabled', 'mood', 'volume', 'file'):
    if src['music'][k] != out['music'][k]: bad.append(('music.' + k, src['music'][k], out['music'][k]))
for k in ('enabled', 'transition', 'highlight', 'highlightGap', 'cta', 'start', 'volume'):
    if src['sfx'].get(k) != out['sfx'].get(k): bad.append(('sfx.' + k, src['sfx'].get(k), out['sfx'].get(k)))
print(json.dumps({'template': out['template'], 'ecarts': bad}, ensure_ascii=False))
print('listes :', [t['id'] for t in R.list_templates()][-3:])
`;
try {
	const out = execFileSync('D:/Tools/editeur_sami/runtime/venv/Scripts/python.exe', ['-c', py], {cwd: 'D:/Tools/editeur_sami/engine',
		env: {...process.env, EDITEUR_ROOT: SANDBOX, PYTHONIOENCODING: 'utf-8', HF_HUB_OFFLINE: '1'}, encoding: 'utf8'});
	console.log(out);
} finally {
	console.log('bac a sable conserve :', SANDBOX);
}
