"""Controle qualite automatique d'un reel, avant livraison. Tout est local, aucune IA en ligne.

Deux passes :
  a) passe RAPIDE sur le JSON du reel (aucun rendu) : chevauchements, habillage sur l'accroche, textes sur le visage,
     textes trop petits ou peu contrastes, textes internes affiches (titre du reel, timecodes, EXEMPLE, fichiers),
     tiers haut/bas vides, cadre fige trop longtemps, medias manquants, detourage, son (musique sous la voix) ;
  b) passe FACULTATIVE sur une video exportee ou un apercu court : images echantillonnees, restes de decor et bords
     du detourage (compares a un masque RVM de reference), visage masque (MediaPipe), lisibilite mesuree a l'image,
     images noires ou figees, loudness (ebur128 : -14 LUFS +-1, crete vraie <= -1 dBTP).

Sortie : {note /10, verdict, constats [{gravite, temps, fin, message, suggestion, preuve, code}], mesures}.
    python -m editeur.controle <reel.json | dossier_projet --reel id> [--video fichier.mp4] [--debut s]
                               [--pas 0.5] [--sortie dossier] [--json]

Les positions et tailles des elements a l'ecran reproduisent Reel.tsx, design.tsx et graphics.tsx (etat du
01/10/2026 : studio Tech 3D sans bandeau technique, interfaces de verre StudioCard, sous-titres sur une ligne) ; les
instants viennent de remotion/src/timeline.ts lui-meme (pont Node) : aucun calcul de temps duplique, et le studio
utilise les memes fonctions que le rendu (studioView = camera, cutoutFallbackMix = repli du detourage, studioCardSize /
designScenes / studioSpot = gabarits et places des interfaces, studioGrade = etalonnage de la personne).
Si l'habillage change dans ces fichiers, mettre a jour _scene / _carte_studio / _graphique / _hud / _decor / _sous_titres
/ visibles ci-dessous."""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from .media import FFMPEG, ROOT, probe

VERSION_RAPPORT = 2
GRAVITES = ('bloquant', 'important', 'conseil')
PENALITE = {'bloquant': 3.0, 'important': 1.0, 'conseil': 0.3}
PLAFOND = {'bloquant': 4.5, 'important': 2.0, 'conseil': 0.6}   # penalite max par type de constat
PAS = 0.1                                                          # pas d'analyse du montage (s)

# Seuils (taille rapportee a une image de 1080 px de petit cote)
TAILLE = {'sous-titre': (34, 50, 62), 'principal': (26, 36, 42), 'secondaire': (20, 26, 30)}  # bloquant, important, conseil
FIGE = 6.0            # cadre sans coupe, zoom ni habillage plus long que ca : conseil (x1,5 : important)
TIERS_VIDE = (8.0, 15.0)
LOUDNESS = (-14.0, 1.0, -1.0)   # cible LUFS, tolerance, crete vraie max (dBTP)

# Textes internes / de travail qui ne doivent jamais etre vus par le public
INTERNE_FORT = re.compile(r'^\W*(exemple|example|illustration|placeholder|lorem ipsum|mockup|maquette|todo|debug|sample|texte ici|text here)\W*$|'
                          r'\b(?-i:undefined|NaN|null|\[object Object\])\b|\blorem ipsum\b|\.(mp4|mov|m4v|webm|json|png|jpe?g|wav|ogg|docx?)\b', re.I)
INTERNE_MOT = re.compile(r'\b(exemple|example|illustration|placeholder|mockup|maquette)\b', re.I)
# etiquette de travail en tete (« EXEMPLE : tableau de bord », « Illustration - interface ») plutot qu'un mot d'une phrase
INTERNE_ETIQUETTE = re.compile(r'^\W*(exemple|example|illustration|placeholder|mockup|maquette)\b\s*[:\-–—|/]', re.I)
INTERNE_NOM = re.compile(r'^\s*(?:(?:vid[ée]o|video|reel|script|hook|prise|take|clip|version|rush)\s*[-_ #]?\d+|[tc]\d{1,2}|v\d)\s*$|'
                         r'\(\d+x\d+\)|-\s*\d+\s+COMPLET|COMPLET\s+-|- FINAL\b', re.I)
TIMECODE = re.compile(r'\b\d{1,2}:\d{2}(:\d{2})?\b')
HALLU = re.compile(r'sous-titrage|amara\.org|merci d.avoir regard[ée] cette vid[ée]o', re.I)  # ajouts connus de Whisper
# meme filtre que design.tsx (TECH_LABEL) : ces textes secondaires ne sont jamais affiches
TECH_LABEL = re.compile(r'exemple|illustration|interface|d[ée]mo\b|mockup|example|pas une mesure', re.I)
# nom des images de preuve ecrites par ce module (« <code>-<element>-034.0s.png ») : seules celles-ci sont remplacees
PREUVE_NOM = re.compile(r'^[a-z0-9-]+-\d{3,}\.\ds\.png$', re.I)


# ---------------------------------------------------------------------------------------------------------------
# Outils : couleurs, boites, textes
# ---------------------------------------------------------------------------------------------------------------
def couleur(c, defaut=(255, 255, 255, 1.0)):
    """'#RGB', '#RRGGBB', '#RRGGBBAA' ou 'rgba(r,g,b,a)' -> (r, g, b, alpha)."""
    if not c or not isinstance(c, str):
        return defaut
    c = c.strip()
    m = re.match(r'rgba?\(([^)]*)\)', c)
    if m:  # « rgba(r, g, b, a) » ou syntaxe CSS4 « rgb(r g b / 50%) » ; illisible -> defaut (jamais de plantage)
        try:
            v = [float(x[:-1]) / 100 if x.endswith('%') else float(x) for x in re.split(r'[\s,/]+', m.group(1).strip()) if x]
            return (v[0], v[1], v[2], v[3] if len(v) > 3 else 1.0)
        except (ValueError, IndexError):
            return defaut
    h = c.lstrip('#')
    if len(h) in (3, 4):
        h = ''.join(x * 2 for x in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(h[6:8], 16) / 255 if len(h) >= 8 else 1.0
        return (r, g, b, a)
    except (ValueError, IndexError):
        return defaut


def _lin(v):
    v = v / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = rgb[:3]
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contraste(l1, l2):
    a, b = max(l1, l2), min(l1, l2)
    return (a + 0.05) / (b + 0.05)


def melange(c, fond_rgb):
    """Couleur (avec alpha) posee sur un fond -> rgb."""
    r, g, b, a = c
    return tuple(a * x + (1 - a) * y for x, y in zip((r, g, b), fond_rgb[:3]))


def inter(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def aire(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def affiche(w, majuscules=False):
    """Meme regle que displayWord (timeline.ts)."""
    t = re.sub(r'[«»"“”]', '', w or '')
    t = re.sub(r'[,.;:…]+$', '', t).strip()
    return t.upper() if majuscules else t


def largeur(texte, px, majuscules=False, k=None):
    return len(texte) * px * (k or (0.64 if majuscules else 0.56))


def lignes(mots, px, maxw, majuscules=False, espace=0.28):
    """Retour a la ligne glouton : largeurs des lignes."""
    out, cur = [], 0.0
    for m in mots:
        w = largeur(m, px, majuscules)
        if cur and cur + espace * px + w > maxw:
            out.append(cur)
            cur = w
        else:
            cur = cur + (espace * px if cur else 0) + w
    if cur or not out:
        out.append(cur)
    return out


def hms(t):
    if t is None:
        return ''
    m, s = divmod(max(0.0, t), 60)
    return f'{int(m)}:{s:04.1f}'.replace('.', ',')


def plages(temps, pas=PAS):
    """Instants -> intervalles [debut, fin]."""
    out = []
    for t in sorted(temps):
        if out and t - out[-1][1] <= pas * 1.6:
            out[-1][1] = t
        else:
            out.append([t, t])
    return [[a, b + pas] for a, b in out]


def plages_texte(pl, n=4):
    s = ', '.join(f'{hms(a)}–{hms(b)}' for a, b in pl[:n])
    return s + (f' (+{len(pl) - n} autres)' if len(pl) > n else '')


def constat(gravite, code, message, suggestion, preuve, temps=None, fin=None, zone=None, element=None, plages_s=None):
    """zone = boite [x0, y0, x1, y1] en px de l'image finale (pour la dessiner sur le lecteur), facultative ;
    element = identifiant de l'element concerne (scene:<id>, graphique:<id>, sous-titres, bandeau, hud:marque...) ;
    plages_s = passages exacts [[debut, fin], ...] quand le constat en couvre plusieurs (facultatif)."""
    assert gravite in GRAVITES
    c = {'gravite': gravite, 'code': code, 'temps': None if temps is None else round(float(temps), 2),
         'fin': None if fin is None else round(float(fin), 2), 'message': message, 'suggestion': suggestion,
         'preuve': preuve}
    if zone is not None:
        c['zone'] = [int(round(v)) for v in zone]
    if element:
        c['element'] = element
    if plages_s:
        c['plages'] = [[round(float(a), 2), round(float(b), 2)] for a, b in plages_s]
    return c


# ---------------------------------------------------------------------------------------------------------------
# Montage : pont vers remotion/src/timeline.ts (seule source des instants)
# ---------------------------------------------------------------------------------------------------------------
_PONT = r"""
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const [tl, reelPath, pasTexte] = process.argv.slice(2);
const T = await import(pathToFileURL(tl).href);
const reel = JSON.parse(fs.readFileSync(reelPath, 'utf8'));
const has = (k) => typeof T[k] === 'function';
const total = T.duration(reel);
const video = T.videoSegments(reel);
const len = (s) => has('segLen') ? T.segLen(s) : (s.src_out - s.src_in) / (s.speed ?? 1);
const pas = Number(pasTexte) || 0.1;
// studio Tech 3D : camera du studio (studioView), plages de repli du detourage (cutoutFallbackMix), gabarits et places des
// interfaces (studioCardSize / studioSpot), etalonnage de la personne (studioGrade) : les MEMES fonctions que le rendu
const studio = has('studioMode') && T.studioMode(reel);
const cut = (s) => (has('validCutout') ? T.validCutout(reel, s) : null);
const frames = [];
for (let i = 0; i * pas < total; i++) {
  const t = i * pas;
  let k = -1;
  for (let j = 0; j < video.length; j++) if (video[j].out_start <= t + 1e-6) k = j;
  if (k < 0) { frames.push({t, seg: -1}); continue; }
  const s = video[k];
  const tSrc = s.src_in + Math.max(0, t - s.out_start) * (s.speed ?? 1);
  const f = has('framing') ? T.framing(reel, s.source, tSrc, s.src_in, s.src_out) : null;
  const scale = has('segmentZoom') ? T.segmentZoom(reel, s, video[k + 1], total, Math.max(0, t - s.out_start)) : null;
  const view = studio && has('studioView') ? T.studioView(reel, s, t) : null;
  const mix = has('cutoutFallbackMix') ? T.cutoutFallbackMix(cut(s), tSrc) : 0;
  frames.push({t, seg: k, tSrc, f, zoom: has('motivatedZoom') ? T.motivatedZoom(reel, t) : 1, scale, view, mix});
}
const scenes = has('designScenes') ? T.designScenes(reel) : [];
const spots = {};
if (studio && (has('studioGraphicSpot') || (has('studioSpot') && has('studioCardSize')))) {
  for (const g of reel.graphics ?? []) {
    if (g.kind !== 'chiffre' || g.manual || g.locked) continue;
    spots[g.id] = has('studioGraphicSpot') ? T.studioGraphicSpot(reel, g)
      : T.studioSpot(reel, 'chiffre', g.at, g.at + g.duration, {x: 0.5, y: g.props?.y ?? 0.3, scale: 1}, T.studioCardSize('chiffre'));
  }
}
const out = {
  total,
  video: video.map((s) => ({...s, len: len(s), cutout: !!cut(s), grade: studio && has('studioGrade') ? T.studioGrade(reel, s, [1, 1, 1]) : null})),
  words: T.timedWords(reel).map(({w, clip, index, outStart, outEnd, hl, hide}) => ({w, clip, index, start: outStart, end: outEnd, hl: !!hl, hide: !!hide})),
  pages: T.pages(reel).map((p) => ({start: p.start, end: p.end, words: p.words.map((w) => ({w: w.w, hl: !!w.hl, clip: w.clip, index: w.index, start: w.outStart, end: w.outEnd}))})),
  scenes: scenes.map((s) => (studio && has('studioCardSize') ? {...s, size: T.studioCardSize(s.kind, s.text, s.secondary)} : s)),
  spots,
  blocks: has('blockStarts') ? T.blockStarts(reel) : [],
  sfx: has('sfxEvents') ? T.sfxEvents(reel) : [],
  frames,
  rendu: {studio, camera: has('studioView'), repli: has('cutoutFallbackMix'), etalonnage: has('studioGrade'), places: has('studioSpot')},
};
process.stdout.write(JSON.stringify(out));
"""


def montage_calcule(reel, travail):
    script = travail / 'pont.mjs'
    script.write_text(_PONT, encoding='utf-8')
    fichier = travail / 'reel.json'
    fichier.write_text(json.dumps(reel, ensure_ascii=False), encoding='utf-8')
    r = subprocess.run(['node', str(script), str(ROOT / 'remotion/src/timeline.ts'), str(fichier), str(PAS)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=str(ROOT / 'remotion'))
    if r.returncode:
        raise RuntimeError('Calcul du montage impossible (timeline.ts) : ' + (r.stderr or '').strip()[-600:])
    return json.loads(r.stdout)


# ---------------------------------------------------------------------------------------------------------------
# Contexte : reel + montage calcule + visages + fonds d'image
# ---------------------------------------------------------------------------------------------------------------
class Contexte:
    def __init__(self, reel, tl):
        self.reel, self.tl = reel, tl
        self.W, self.H = reel['width'], reel['height']
        self.u = min(self.W, self.H)
        self.total = tl['total']
        d = reel.get('design') or {}
        self.mode = None if d.get('enabled') is False else d.get('mode')
        self.extras = not self.mode or d.get('suppressExtras') is False
        self.cinematique = self.mode == 'produit' and bool(d.get('cinematic'))
        self.decoupe = self.mode in ('editorial', 'collage') or self.cinematique
        self.story = (reel.get('creativePlan') or {}).get('storyboard') or []
        self.mots = {(w['clip'], w['index']): w for w in tl['words']}
        self._visages = {}
        self.accroche_source = 'première phrase'
        # ce que le rendu sait faire (fonctions exportees par timeline.ts) : camera du studio, repli du detourage...
        self.rendu = tl.get('rendu') or {}

    # -- instants
    def image(self, t):
        fr = self.tl['frames']
        return fr[max(0, min(len(fr) - 1, int(round(t / PAS))))] if fr else {'seg': -1}

    def segment(self, t):
        fr = self.image(t)
        return (self.tl['video'][fr['seg']] if fr.get('seg', -1) >= 0 else None), fr

    def cutout(self, seg):
        return (self.reel.get('cutouts') or {}).get(seg['clip']) if seg and seg.get('cutout') else None

    def studio(self, t):
        """Studio virtuel Tech 3D actif (ProductStage) : il recouvre la video (et ses zooms) ; sa camera (studioView)
        cadre la personne detouree ET la prise d'origine des plages de repli."""
        seg, _ = self.segment(t)
        return self.cinematique and bool(seg and seg.get('cutout'))

    def repli(self, t):
        """Part de la prise d'origine a l'instant t (0 : personne detouree ; 1 : prise d'origine, plage de repli du
        detourage). Toujours 0 si le rendu ne sait pas faire de repli."""
        return float(self.image(t).get('mix') or 0)

    def vue(self, t):
        """Camera du studio a l'instant t {scale, ox, oy, bg} (studioView de timeline.ts) ou None."""
        return self.image(t).get('view') if self.studio(t) else None

    def rect(self, t):
        """Rectangle a l'ecran (x, y, largeur, hauteur en px) de l'image de la prise (ou de la personne detouree) a
        l'instant t, camera du studio ou zoom du plan compris ; None hors des plans."""
        seg, fr = self.segment(t)
        f = fr.get('f') if seg else None
        if not f:
            return None
        v = self.vue(t)
        if v:
            s, ox, oy = v['scale'], v['ox'] * self.W, v['oy'] * self.H
        elif self.studio(t) or self.mode in ('editorial', 'collage'):
            s, ox, oy = 1.0, f['cx'] * self.W, f['cy'] * self.H
        else:
            s, ox, oy = self.echelle(t, seg, fr), f['cx'] * self.W, f['cy'] * self.H
        return (ox + (f['left'] - ox) * s, oy + (f['top'] - oy) * s, f['width'] * s, f['height'] * s)

    def outro(self, t):
        o = (self.reel.get('brand') or {}).get('outro') or {}
        return bool(o.get('enabled')) and t >= self.total - (o.get('duration') or 0)

    def accroche(self):
        self.accroche_source = 'plan créatif'
        for b in (self.reel.get('creativePlan') or {}).get('beats') or []:
            if b.get('role') == 'accroche':
                return max(0.5, min(float(b.get('end', 3)), 12.0))
        self.accroche_source = 'première phrase'
        clips = self.reel.get('clips') or []
        if clips:
            bloc = [c['id'] for c in clips if c.get('block') == clips[0].get('block')]
            fin = None
            for w in self.tl['words']:
                if w['clip'] in bloc and not w['hide']:
                    fin = w['end']
                    if re.search(r'[.!?…]$', w['w']) and fin > 1.5:
                        break
            if fin:
                return min(fin, 8.0)
        return min(3.0, self.total)

    # -- visage de la personne (analyse v3 : boite MediaPipe)
    def _analyse(self, sid):
        if sid not in self._visages:
            src = self.reel['sources'].get(sid) or {}
            pts = []
            proxy = src.get('proxy') or ''
            f = ROOT / 'projects/_cache/analysis' / (Path(proxy).stem + '.analysis.json')
            sw, sh = src.get('width') or 1080, src.get('height') or 1920
            piste = [p for p in src.get('track') or [] if len(p) > 3]
            if piste:
                # prise horizontale (plusieurs personnes possibles) : framing() suit la personne QUI PARLE (piste de
                # cadrage.py : t, cx, cy, largeur du visage) ; l'analyse ne garde que le plus grand visage, parfois l'autre
                pts = [(p[0], p[1], p[2], p[3], p[3] * sw / sh) for p in piste]
            elif f.exists():
                try:
                    for x in json.loads(f.read_text(encoding='utf-8')).get('frames') or []:
                        if x.get('face'):
                            v = x['face']
                            pts.append((x['t'], v['cx'], v['cy'], v.get('w', .24), v.get('h', .136)))
                except (OSError, ValueError, KeyError):
                    pts = []
            if not pts:  # echantillons du reel (sans taille) : taille typique d'un visage face camera
                for p in src.get('track') or src.get('samples') or []:
                    w = p[3] if src.get('track') and len(p) > 3 else .24
                    pts.append((p[0], p[1], p[2], w, w * (src.get('width') or 1080) / (src.get('height') or 1920)))
            if len(pts) >= 5:  # fausses detections isolees (main, objet) : taille anormale
                mw = float(np.median([p[3] for p in pts]))
                pts = [p for p in pts if .6 * mw <= p[3] <= 1.5 * mw]
            self._visages[sid] = sorted(pts)
        return self._visages[sid]

    def visage(self, t):
        """Boite du visage dans l'image finale (px) ou None."""
        seg, fr = self.segment(t)
        if not seg or not fr.get('f'):
            return None
        pts = self._analyse(seg['source'])
        if not pts:
            return None
        ts = fr['tSrc']
        proches = [x for x in pts if abs(x[0] - ts) <= .4]
        if not proches:
            return None
        p = [float(np.median([x[k] for x in proches])) for k in range(5)]  # mediane : robuste a une detection isolee
        L, T, RW, RH = self.rect(t)  # image de la prise a l'ecran (camera du studio ou zoom du plan compris)
        cx, cy = L + p[1] * RW, T + p[2] * RH
        w, h = p[3] * RW, p[4] * RH
        return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

    def comparaison(self, t):
        """Ecran partage du style Comparatif (ComparisonVideo) actif a l'instant t."""
        return self.mode == 'comparatif' and any(s.get('kind') == 'comparison' and s['at'] <= t < s['end'] for s in self.tl['scenes'])

    def visages(self, t):
        """Visages visibles (px) : un seul en general, deux pendant l'ecran partage du style Comparatif
        (meme prise dans chaque moitie, cadree par framing() sur une largeur W/2, sans zoom)."""
        vb = self.visage(t)
        if vb is None or not self.comparaison(t):
            return [vb] if vb else []
        seg, fr = self.segment(t)
        f, src = fr['f'], self.reel['sources'].get(seg['source']) or {}
        sw, sh = src.get('width') or 1080, src.get('height') or 1920
        scx, scy = (f['cx'] * self.W - f['left']) / f['width'], (f['cy'] * self.H - f['top']) / f['height']  # sujet (prise)
        k = max(self.W / 2 / sw, self.H / sh)
        dw, dh = sw * k, sh * k
        left = min(0.0, max(self.W / 2 - dw, self.W / 4 - scx * dw))
        top = min(0.0, max(self.H - dh, self.H * .42 - scy * dh))
        # visage dans la prise (fractions) retrouve a partir de la boite plein cadre (sans le zoom)
        s = self.echelle(t, seg, fr)
        ox, oy = f['cx'] * self.W, f['cy'] * self.H
        x0, y0, x1, y1 = [(v - o) / s + o for v, o in zip(vb, (ox, oy, ox, oy))]
        fx0, fx1 = (x0 - f['left']) / f['width'], (x1 - f['left']) / f['width']
        fy0, fy1 = (y0 - f['top']) / f['height'], (y1 - f['top']) / f['height']
        out = []
        for i in (0, 1):
            a, b = i * self.W / 2 + left + fx0 * dw, i * self.W / 2 + left + fx1 * dw
            a, b = max(a, i * self.W / 2), min(b, (i + 1) * self.W / 2)  # chaque moitie coupe ce qui deborde
            if b - a > 4:
                out.append((a, top + fy0 * dh, b, top + fy1 * dh))
        return out

    def echelle(self, t, seg, fr):
        if fr.get('scale') is not None:  # segmentZoom de timeline.ts (meme calcul que SegmentVideo)
            return fr['scale']
        z = self.reel.get('zoom') or {}
        s = 1.0
        ov = (z.get('overrides') or {}).get(str(seg['index']))
        if ov is not None:
            s = ov
        elif z.get('auto') and not self.mode:
            s = z.get('strength', 1) if seg['index'] % 2 == 1 else 1
        s *= fr.get('zoom') or 1
        s *= 1 + (z.get('push') or 0) * min(1, max(0, (t - seg['out_start']) / max(.001, seg['len'])))
        if self.mode == 'luxe':
            s *= .87
        return s


# ---------------------------------------------------------------------------------------------------------------
# Elements visibles a l'instant t (miroir de Reel.tsx / design.tsx / graphics.tsx)
# ---------------------------------------------------------------------------------------------------------------
def _txt(texte, px, coul, role, fond=None, contour=0.0, ombre=False, contour_coul='#000000', halo=None, cite=None):
    """halo = couleur d'une lueur epaisse autour des lettres (text-shadow en plusieurs couches) ;
    cite = texte a citer dans les messages (page entiere des sous-titres) si different du texte mesure."""
    return {'texte': texte, 'px': px, 'couleur': coul, 'role': role, 'fond': fond, 'contour': contour,
            'ombre': ombre, 'contour_coul': contour_coul, 'halo': halo, 'cite': cite}


def _el(ident, genre, box, textes=(), auto=True, carte=None, derriere=False, interne=False, occupe=True, voile=0.0, ponctuel=False, lisere=False):
    """voile = assombrissement de toute l'image pendant l'element (MotGeant : noir 35 %) ;
    ponctuel = effet bref de ponctuation voulu par le style (mot geant plein ecran) ;
    lisere = carte detachee du decor par un liseré clair et une lueur (verre du studio) : jamais « terne » par son fond."""
    return {'id': ident, 'genre': genre, 'box': tuple(float(x) for x in box), 'textes': list(textes), 'auto': auto,
            'carte': carte, 'derriere': derriere, 'interne': interne, 'occupe': occupe, 'voile': voile, 'ponctuel': ponctuel, 'lisere': lisere}


def _centre(cx, cy, w, h, s=1.0):
    return (cx - w * s / 2, cy - h * s / 2, cx + w * s / 2, cy + h * s / 2)


def _shown(s):
    return s if s and not TECH_LABEL.search(s) else ''


STUDIO_CARTES = ('metric', 'notification', 'dashboard', 'flow', 'cta')
VERRE = '#161c29'  # verre sombre des interfaces du studio (degrade #232c3e -> #080b12 de studioGlass, design.tsx)


def _gabarit_studio(kind, text='', secondary=''):
    """Copie de studioCardSize (timeline.ts) si le pont ne l'a pas fournie : (largeur, hauteur) en part du petit cote."""
    parts = len([x for x in [text, *str(secondary or '').split('|')] if str(x).strip()])
    if kind == 'flow':
        return .92, (.48 if parts > 2 else .15)
    if kind == 'dashboard':
        return .86, .17 + .11 * max(1, min(3, parts - 1))
    if kind == 'notification':
        return .84, .3
    if kind == 'cta':
        return .82, (.24 if secondary else .17)
    return .72, .33


def _carte_studio(ctx, g, ident, auto, accent, sec):
    """Interfaces du studio Tech 3D (StudioCard / StudioMetric de design.tsx, etat du 01/10/2026) : verre sombre a
    liseré clair et lueur d'accent, police Manrope grasse, grands textes ; place hors de la personne (designScenes)."""
    W, H, u = ctx.W, ctx.H, ctx.u
    kind, text = g.get('kind'), str(g.get('text') or '')
    size = g.get('size') or {}
    gw, gh = (size.get('w'), size.get('h')) if size.get('w') else _gabarit_studio(kind, text, g.get('secondary'))
    box = _centre(W * g.get('x', .5), H * g.get('y', .5), gw * u, gh * u, g.get('scale', 1) or 1)
    s2 = _shown(g.get('secondary'))
    if kind == 'metric':
        t = [_txt(text, u * .15, '#ffffff', 'principal', VERRE, halo=accent)] + ([_txt(s2, u * .05, '#dbe6f7', 'secondaire', None, ombre=True)] if s2 else [])
    elif kind == 'flow':
        parts = []
        for x in [text] + str(g.get('secondary') or '').split('|'):
            x = x.strip()
            if x and x not in parts:
                parts.append(x)
        parts = parts[:3]
        t = [_txt(p, u * (.046 if len(parts) > 2 else .056), '#ffffff', 'principal', VERRE) for p in parts]
    elif kind == 'dashboard':
        items = [x.strip() for x in str(g.get('secondary') or '').split('|') if x.strip()][:3] or [text]
        t = [_txt(text, u * .062, '#ffffff', 'principal', VERRE)] + [_txt(it, u * .054, '#ffffff', 'principal', '#1f2533') for it in items]
    elif kind == 'notification':
        app = s2 or (ctx.reel.get('brand') or {}).get('name') or 'Messages'
        quand = 'now' if re.match(r'(new|reply|lead waiting|incoming)', text, re.I) else 'maintenant'
        t = [_txt(app, u * .046, '#c6d3e6', 'secondaire', VERRE), _txt(quand, u * .046, accent, 'secondaire', VERRE),
             _txt(text, u * .058, '#f4f8ff', 'principal', VERRE)]
    else:  # cta : pilule degradee secondaire -> accent, texte sombre ; libelle au-dessus, sans fond
        a, b = couleur(accent), couleur(sec)
        bouton = '#%02x%02x%02x' % tuple(int((x + y) / 2) for x, y in zip(a[:3], b[:3]))
        t = [_txt(text, u * .064, '#04101c', 'principal', bouton)] + ([_txt(s2, u * .046, '#c9d6ea', 'secondaire', None, ombre=True)] if s2 else [])
        return _el(ident, 'carte', box, t, auto, carte=bouton, lisere=True)
    return _el(ident, 'carte', box, t, auto, carte=VERRE + 'f7', lisere=True)


def _scene(ctx, g):
    W, H, u = ctx.W, ctx.H, ctx.u
    d = ctx.reel.get('design') or {}
    accent = g.get('color') or d.get('accent') or '#6FE7FF'
    sec = d.get('secondary') or '#8B5CF6'
    cx, cy, sc = W * g.get('x', .5), H * g.get('y', .5), g.get('scale', 1) or 1
    kind, text = g.get('kind'), str(g.get('text') or '')
    auto = not g.get('edited') and not g.get('manual')
    ident = f"scene:{g.get('id')}"
    if ctx.cinematique and kind in STUDIO_CARTES:
        return _carte_studio(ctx, g, ident, auto, accent, sec)
    if kind == 'metric':
        px = u * .13
        w = min(max(largeur(text, px, k=.6) + 2 * u * .06, u * .48), u * .86)
        s2 = _shown(g.get('secondary'))
        h = 2 * u * .045 + px + (u * .04 + 15 if s2 else 0) + u * .038
        t = [_txt(text, px, accent, 'principal', '#0c1320')] + ([_txt(s2, u * .04, '#ffffff', 'secondaire', '#0c1320')] if s2 else [])
        return _el(ident, 'carte', _centre(cx, cy, w, h, sc), t, auto, carte='#0c1320f4')
    if kind == 'notification':
        app = _shown(g.get('secondary')) or (ctx.reel.get('brand') or {}).get('name') or 'Messages'
        w = u * .79
        nl = len(lignes(text.split(), u * .05, w - 2 * u * .04))
        h = 2 * u * .034 + u * .058 + u * .022 + nl * u * .05 * 1.14
        bg = '#0d1321'
        t = [_txt(app, u * .026, '#a9b8ce', 'secondaire', bg), _txt('maintenant', u * .026, accent, 'secondaire', bg),
             _txt(text, u * .05, '#f6f9ff', 'principal', bg)]
        return _el(ident, 'carte', _centre(cx, cy, w, h, sc), t, auto, carte=bg + 'f3')
    if kind == 'dashboard':
        items = [x.strip() for x in str(g.get('secondary') or '').split('|') if x.strip()][:3] or [text]
        w = W * .88
        h = 2 * u * .042 + u * .046 + u * .035 + len(items) * (2 * u * .022 + u * .036) + (len(items) - 1) * u * .017
        bg = '#0a101c'
        t = [_txt(text, u * .046, '#ffffff', 'principal', bg), _txt('LIVE', u * .022, '#ffffff66', 'secondaire', bg)]
        t += [_txt(it, u * .033, '#ffffff', 'principal', bg) for it in items]
        return _el(ident, 'carte', _centre(cx, cy, w, h, sc), t, auto, carte=bg + 'f6')
    if kind == 'flow':
        parts = []
        for x in [text] + str(g.get('secondary') or '').split('|'):
            x = x.strip()
            if x and x not in parts:
                parts.append(x)
        parts = parts[:4]
        w = W * .9
        h = 2 * u * .04 + 2 * u * .032 + u * .027 * 1.25
        bg = '#060b15'
        t = [_txt(p, u * .027, '#ffffff', 'principal', bg) for p in parts]
        return _el(ident, 'carte', _centre(cx, cy, w, h, sc), t, auto, carte=bg + 'ed')
    if kind == 'cta':
        s2 = _shown(g.get('secondary'))
        w = min(W * .86, largeur(text + ' →', u * .055, k=.6) + 2 * u * .085)
        h = 2 * u * .045 + u * .055 * 1.2 + ((u * .025 * 1.3 + u * .028) if s2 else 0)
        a, b = couleur(accent), couleur(sec)
        bouton = '#%02x%02x%02x' % tuple(int((x + y) / 2) for x, y in zip(a[:3], b[:3]))
        t = [_txt(text, u * .055, '#04101a', 'principal', bouton)]
        if s2:
            t.append(_txt(s2, u * .025, '#c3cde0', 'secondaire', None))
        return _el(ident, 'carte', _centre(cx, cy, w, h, sc), t, auto, carte=bouton)
    if kind == 'comparison':
        w = W * .82
        s2 = str(g.get('secondary') or '')
        nl = max(len(lignes(text.split(), u * .044, w / 2 - 2 * u * .03)), len(lignes(s2.split(), u * .044, w / 2 - 2 * u * .03)))
        h = max(u * .22, 2 * u * .03 + u * .025 + 14 + nl * u * .044 * 1.2)
        t = [_txt(text, u * .044, '#ffffff', 'principal', '#301b22'), _txt(s2, u * .044, '#ffffff', 'principal', '#0f342b'),
             _txt('AVANT', u * .025, '#e4b8b8', 'secondaire', '#301b22')]
        return _el(ident, 'carte', _centre(cx, cy, w, h, sc), t, auto, carte='#301b22ee')
    if kind == 'paper':
        px = u * .09
        w = min(W * .85, largeur(text + ' ↗', px, k=.62) + 2 * u * .04)
        h = px * 1.2 + 2 * u * .024 + 8
        return _el(ident, 'carte', _centre(cx, cy, w, h, sc), [_txt(text, px, '#151515', 'principal', '#fff9ec')], auto, carte='#fff9ec')
    if kind == 'product':
        if not d.get('productVideo'):
            return None
        return _el(ident, 'image', _centre(cx, cy, W * .82, H * .45, sc), [], auto, carte='#050506')
    return None


def _graphique(ctx, g):
    W, H, u = ctx.W, ctx.H, ctx.u
    st = ctx.reel.get('style') or {}
    p = g.get('props') or {}
    acc, stroke = st.get('highlight') or '#FFD400', st.get('stroke') or '#000000'
    ident, kind = f"graphique:{g.get('id')}", g.get('kind')
    auto = bool(g.get('auto')) or bool(g.get('suggested'))
    if kind == 'chiffre':
        px = u * .2
        v = p.get('value') or 0
        try:
            v = float(v)
            val = f'{v:,.0f}'.replace(',', ' ') if float(v).is_integer() else f'{v:.1f}'.replace('.', ',')
        except (TypeError, ValueError):
            val = str(v)
        text = f"{p.get('prefix') or ''}{val}{p.get('suffix') or ''}"
        lab = str(p.get('label') or '')
        if ctx.cinematique:
            # studio Tech 3D (graphics.tsx -> StudioMetric) : pilule de verre, grand chiffre blanc lumineux, libelle
            # dessous ; place dans l'espace libre au-dessus de la personne (studioSpot), sauf graphisme pose a la main
            spot = (ctx.tl.get('spots') or {}).get(g.get('id')) or {'x': .5, 'y': p.get('y') if p.get('y') is not None else .3, 'scale': 1}
            gw, gh = _gabarit_studio('chiffre')
            box = _centre(W * spot['x'], H * spot['y'], gw * u, gh * u, spot.get('scale') or 1)
            couleur_c = p.get('color') if isinstance(p.get('color'), str) and p.get('color') else acc  # tint() de graphics.tsx
            t = [_txt(text, u * .15, '#ffffff', 'principal', VERRE, halo=couleur_c)] + ([_txt(lab, u * .05, '#dbe6f7', 'secondaire', None, ombre=True)] if lab else [])
            return _el(ident, 'graphique', box, t, auto, carte=VERRE + 'f7', lisere=True)
        w = max(largeur(text, px, k=.62), largeur(lab, u * .055, True) if lab else 0)
        h = px + ((10 + u * .055 * 1.2) if lab else 0)
        cy = H * (p.get('y') if p.get('y') is not None else .3)
        t = [_txt(text, px, acc, 'principal', None, 8, True, stroke)] + ([_txt(lab.upper(), u * .055, '#FFFFFF', 'principal', None, 5, False, stroke)] if lab else [])
        return _el(ident, 'graphique', _centre(W / 2, cy, w, h), t, auto)
    if kind == 'coches':
        items = [x for x in (p.get('items') or []) if x][:5]
        top = H * (p.get('y') if p.get('y') is not None else .22)
        h = 2 * u * .04 + ((u * .05 + u * .02) if p.get('title') else 0) + len(items) * (u * .065 + 2 * u * .012)
        t = [_txt(str(x), u * .048, '#FFFFFF', 'principal', '#0a0a0c') for x in items]
        if p.get('title'):
            t.append(_txt(str(p['title']).upper(), u * .05, acc, 'principal', '#0a0a0c'))
        return _el(ident, 'carte', (W * .1, top, W * .9, top + h), t, auto, carte='rgba(10,10,12,0.82)')
    if kind == 'carte':
        w = u * .62
        right = p.get('side') != 'gauche'
        x0 = W - W * .06 - w if right else W * .06
        top = H * (p.get('y') if p.get('y') is not None else .16)
        h = (u * .4 if p.get('image') else u * .12) + 2 * u * .025 + u * .05 * 1.1 + ((u * .034 + 6) if p.get('subtitle') else 0)
        t = [_txt(str(p.get('title') or ''), u * .05, '#0B0B0B', 'principal', '#FFFFFF')]
        if p.get('subtitle'):
            t.append(_txt(str(p['subtitle']), u * .034, '#555555', 'secondaire', '#FFFFFF'))
        return _el(ident, 'carte', (x0, top, x0 + w, top + h), t, auto, carte='#FFFFFF')
    if kind == 'motgeant':
        # graphics.tsx MotGeant : voile noir 35 % sur toute l'image, texte blanc, contour 3 px et lueur de la couleur
        text = str(p.get('text') or '').upper()
        size = min(W * .9 / max(3, len(text) * .62), H * .2)
        c = p.get('color') or acc
        return _el(ident, 'graphique', _centre(W / 2, H / 2, largeur(text, size, k=.62), size),
                   [_txt(text, size, '#FFFFFF', 'principal', None, 3, True, c, halo=c)], auto, voile=.35, ponctuel=True)
    if kind == 'logo':
        s = u * (p.get('size') or .45)
        return _el(ident, 'image', _centre(W / 2, H / 2, s, s * .6), [], auto)
    return None


def _hud(ctx, t):
    """Haut du studio virtuel Tech 3D (ProductStage, design.tsx au 01/10/2026) : plus de titre interne ni de minuteur ;
    seulement le nom de la marque du client, discret en haut a gauche, quand la charte n'a pas de logo (le logo a sa
    propre couche). Rien du tout sinon."""
    W, H, u = ctx.W, ctx.H, ctx.u
    brand = ctx.reel.get('brand') or {}
    nom = '' if brand.get('logo') else str(brand.get('name') or '').strip()[:32]
    if not nom:
        return []
    px = u * .03
    x0, y0 = W * .06, H * .045
    x1 = x0 + 2 * u * .014 + largeur(nom, px) + 1.5 * len(nom)
    return [_el('hud:marque', 'hud', (x0, y0, x1, y0 + px * 1.3), [_txt(nom, px, '#dce8ff8c', 'secondaire', None)], auto=False, occupe=False)]


def _decor(ctx, t):
    W, H, u = ctx.W, ctx.H, ctx.u
    d = ctx.reel.get('design') or {}
    out = []
    if ctx.mode == 'documentaire':
        out.append(_el('decor:haut', 'decor', (0, 0, W, H * .08), occupe=True))
        out.append(_el('decor:bas', 'decor', (0, H * .92, W, H), occupe=True))
        title = d.get('title') or ('' if re.search(r'COMPLET|Hook|Script\s*\d|FINAL|\(\d+x\d+\)', ctx.reel.get('title') or '', re.I)
                                   else ctx.reel.get('title'))
        if t < 4.5 and title:
            px = u * .032
            out.append(_el('decor:titre', 'decor-texte', (W * .07, H * .86 - px * 1.3, W * .07 + min(W * .8, largeur(title, px) + 20), H * .86),
                           [_txt(title, px, '#ded7cb', 'secondaire', None)]))
    if ctx.mode == 'vhs':
        out.append(_el('decor:play', 'decor-texte', (W * .07, H * .075, W * .07 + largeur('PLAY ▷', u * .045, True), H * .075 + u * .045 * 1.2),
                       [_txt('PLAY ▷', u * .045, '#eeeece', 'secondaire', None)], occupe=False))
        brand = (ctx.reel.get('brand') or {}).get('name')
        rec = f"{d.get('date') or (brand.upper() + ' · REC' if brand else 'REC')} · 00:{int(t):02d}:{int(t * ctx.reel['fps']) % ctx.reel['fps']:02d}"
        px = u * .035
        out.append(_el('decor:rec', 'decor-texte', (W * .07, H * .91 - px * 1.2, W * .07 + largeur(rec, px, True), H * .91),
                       [_txt(rec, px, '#eeeece', 'secondaire', None)], occupe=False))
    return out


def _chasse_em(mot):
    """Largeur d'un mot en em pour une grotesque grasse (signsEm de Reel.tsx : chasses de Manrope 800, -0,012 em par signe)."""
    n = 0.0
    for c in mot:
        if re.match(r"[ijlI|'’.,:;!]", c):
            n += .31
        elif re.match(r'[frt\-1]', c):
            n += .43
        elif re.match(r'[mwMWœŒ%]', c):
            n += .9
        elif re.match(r'[A-Z0-9ÀÂÇÉÈÊËÎÏÔÙÛ]', c):
            n += .68
        else:
            n += .6
        n -= .012
    return n


def _sous_titres(ctx, page):
    W, H, u = ctx.W, ctx.H, ctx.u
    st = ctx.reel.get('style') or {}
    up = bool(st.get('uppercase'))
    mots = [affiche(w['w'], up) for w in page['words']]
    if ctx.mode == 'editorial':  # Kinetic : mots normaux a 75 %, mots forts a 160 %
        base = st.get('size', 60) * W / 1080
        norm = [min(base * .75, W * .82 / max(3, len(m) * .58)) for m, w in zip(mots, page['words']) if not w['hl']]
        fort = [min(base * 1.6, W * .82 / max(3, len(m) * .58)) for m, w in zip(mots, page['words']) if w['hl']]
        px = max(norm + fort) if (norm or fort) else base
        top = H * st.get('position', .72)
        lw = lignes(mots, px, W * .84)
        h = len(lw) * px * 1.13
        t = []
        if norm:
            t.append(_txt(' '.join(m for m, w in zip(mots, page['words']) if not w['hl']), min(norm), st.get('color', '#FFFFFF'), 'sous-titre', None, 0, True, cite=' '.join(mots)))
        if fort:
            t.append(_txt(' '.join(m for m, w in zip(mots, page['words']) if w['hl']), min(fort), (ctx.reel.get('design') or {}).get('accent') or st.get('highlight'),
                          'sous-titre', None, 0, True, cite=' '.join(mots)))
        return _el('sous-titres', 'sous-titres', (W * .08, top, W * .08 + max(lw), top + h), t, True)
    px = st.get('size', 60) * u / 1080
    interligne = 1.1
    if ctx.cinematique:
        # studio Tech 3D (Captions de Reel.tsx) : une page tient sur UNE ligne si possible, la police se resserre jusqu'a
        # 80 % de sa taille (chasses de Manrope 800 : signsEm) ; deux lignes equilibrees sinon ; sans contour, ombre douce
        em = sum(.2 + _chasse_em(m) for m in mots) + .2 * (len(mots) - 1)
        est, place = em * px, W * .86
        if est > place:
            px *= max(.8, place / est)
        interligne = 1.14
        if em * px <= place:
            lw = [em * px]
        else:  # textWrap: balance -> deux lignes de longueur voisine
            n = max(2, math.ceil(em * px / place))
            lw = [max(em * px / n, max(_chasse_em(m) for m in mots) * px)] * n
        h = len(lw) * px * interligne
        stroke = (st.get('strokeWidth') or 0) * u / 1080
        t = [_txt(' '.join(m for m, w in zip(mots, page['words']) if not w['hl']) or ' '.join(mots), px, st.get('color', '#FFFFFF'), 'sous-titre', None,
                  stroke, True, st.get('stroke') or '#000000', cite=' '.join(mots))]
        if any(w['hl'] for w in page['words']):
            t.append(_txt(' '.join(m for m, w in zip(mots, page['words']) if w['hl']), px, st.get('highlight', '#FFD400'), 'sous-titre', None,
                          stroke, True, st.get('stroke') or '#000000', cite=' '.join(mots)))
        return _el('sous-titres', 'sous-titres', _centre(W / 2, H * st.get('position', .72), max(lw), h), t, True)
    lw = lignes(mots, px, W * .86, up)
    h = len(lw) * px * interligne
    cy = H * st.get('position', .72)
    stroke = (st.get('strokeWidth') or 0) * u / 1080
    ombre = st.get('preset') in ('minimal', 'elegant', 'neon') or st.get('preset') != 'bulle'
    fond = '#FFFFFF' if st.get('preset') == 'bulle' else None
    t = [_txt(' '.join(m for m, w in zip(mots, page['words']) if not w['hl']) or ' '.join(mots), px, st.get('color', '#FFFFFF'), 'sous-titre', fond,
              stroke, ombre, st.get('stroke') or '#000000', cite=' '.join(mots))]
    if any(w['hl'] for w in page['words']) and st.get('preset') != 'boite':
        t.append(_txt(' '.join(m for m, w in zip(mots, page['words']) if w['hl']), px, st.get('highlight', '#FFD400'), 'sous-titre', fond,
                      stroke, ombre, st.get('stroke') or '#000000', cite=' '.join(mots)))
    return _el('sous-titres', 'sous-titres', _centre(W / 2, cy, max(lw), h), t, True)


def visibles(ctx, t):
    """Liste des elements visibles a l'instant t (avec leur boite en px)."""
    reel, W, H, u = ctx.reel, ctx.W, ctx.H, ctx.u
    out = []
    graphs = [g for g in reel.get('graphics') or [] if not g.get('suggested') and g['at'] <= t < g['at'] + g['duration']]
    brolls = [b for b in reel.get('broll') or [] if b['at'] <= t < b['at'] + b['duration']]
    planned = any(g.get('auto') for g in graphs) and any(s.get('engine') == 'remotion-graphisme' and s['start'] - .3 <= t <= s['end'] + .4
                                                         for s in ctx.story)
    # V2 (Reel.tsx) : un graphisme pose / retouche a la main ou verrouille reste visible dans un style immersif
    user = not ctx.extras and not planned and any(g.get('manual') or g.get('locked') for g in graphs)
    manual = planned or user or (ctx.extras and bool(graphs or brolls))
    scenes = [s for s in ctx.tl['scenes'] if s['at'] <= t < s['end']]
    # studio : une information a la fois ; le chiffre (ou le mot geant) affiche remplace les sous-titres qui le disent
    # (un logo, une liste ou une carte posee a la main les laisse)
    dit = ctx.cinematique and (planned or user) and any(g.get('kind') in ('chiffre', 'motgeant') and (planned or g.get('manual') or g.get('locked'))
                                                         for g in graphs)
    designed = (not manual and any(s.get('kind') != 'keyword' and (s.get('kind') != 'product' or (reel.get('design') or {}).get('productVideo'))
                                   for s in scenes)) or dit
    outro = ctx.outro(t)
    if ctx.extras:
        for b in brolls:
            src = reel['sources'].get(b['source']) or {}
            shape = lambda w, h: 'v' if h > w * 1.05 else ('h' if w > h * 1.05 else 'c')
            mode = b.get('mode') or ('encadre' if src.get('width') and shape(W, H) != 'c' and shape(src['width'], src['height']) != shape(W, H) else 'plein')
            box = (W * .49, H * .34, W, H * .86) if (mode == 'encadre' and H > W * 1.05) else ((W * .55, H * .1, W * .95, H * .9) if mode == 'encadre' else (0, 0, W, H))
            out.append(_quand(_el(f"broll:{b.get('id')}", 'broll-' + mode, box, [], auto=bool(b.get('suggested') or b.get('auto'))),
                              b['at'], b['at'] + b['duration']))
    if ctx.studio(t) and ctx.repli(t) < .5:  # le studio s'efface (fondu) pendant une plage de repli du detourage
        out += _hud(ctx, t)
    out += _decor(ctx, t)
    if ctx.extras or planned or user:
        for g in graphs:
            if user and not (g.get('manual') or g.get('locked')):
                continue
            e = _graphique(ctx, g)
            if e:
                out.append(_quand(e, g['at'], g['at'] + g['duration']))
    if not outro and not manual and ctx.mode != 'editorial' and scenes:
        e = _scene(ctx, scenes[0])
        if e:
            out.append(_quand(e, scenes[0]['at'], scenes[0]['end']))
    if ctx.mode == 'editorial':
        key = next((s for s in scenes if s.get('kind') == 'keyword'), None)
        if key:
            text = affiche(key.get('text', ''), True)
            size = min(W * .28, W * .96 / max(3, len(text) * .49)) * (key.get('scale') or 1)
            out.append(_quand(_el(f"scene:{key.get('id')}", 'mot-geant', (W * .02, H * .16, W * .98, H * .16 + size), [], derriere=True),
                              key['at'], key['end']))
    b = reel.get('banner') or {}
    if not outro and b.get('enabled') and (b.get('text') or '').strip() and b.get('start', 0) <= t <= (b.get('end') if b.get('end') is not None else ctx.total):
        text = b['text'].upper()
        lw = lignes(text.split(), 46, W * .86 - 60, True)
        w, h = min(W * .86, max(lw) + 60), len(lw) * 46 * 1.12 + 36
        brand = reel.get('brand') or {}
        out.append(_quand(_el('bandeau', 'bandeau', (W / 2 - w / 2, H * .1, W / 2 + w / 2, H * .1 + h),
                              [_txt(text, 46, brand.get('bannerColor') or '#0B0B0B', 'principal', brand.get('bannerBg') or '#FFFFFF')], auto=False,
                              carte=brand.get('bannerBg') or '#FFFFFF'), b.get('start', 0), b.get('end') if b.get('end') is not None else ctx.total))
    if not outro and (reel.get('emoji') or {}).get('enabled'):
        for c in reel.get('clips') or []:
            for i, e in c.get('emojis') or []:
                w = ctx.mots.get((c['id'], i))
                if w and w['start'] <= t < w['start'] + 1.3:
                    px = 130 * u / 1080
                    cy = H * ((reel.get('style') or {}).get('position', .72) - .14) + px * .6
                    out.append(_quand(_el(f"emoji:{c['id']}:{i}", 'emoji', _centre(W / 2, cy, px * 1.2, px * 1.2), [], auto=True),
                                      w['start'], w['start'] + 1.3))
                    break
    if not outro and not designed:
        page = next((p for p in ctx.tl['pages'] if p['start'] <= t < p['end']), None)
        if page:
            out.append(_quand(_sous_titres(ctx, page), page['start'], page['end']))
    brand = reel.get('brand') or {}
    if brand.get('logo') and not outro:
        s = u * (brand.get('logoSize') or .16)
        pos = brand.get('logoPosition') or 'haut-droite'
        x0 = W * .05 if 'gauche' in pos else W - W * .05 - s
        y0 = H * .045 if 'haut' in pos else H - H * .045 - s * .5
        out.append(_el('logo', 'logo', (x0, y0, x0 + s, y0 + s * .5), [], auto=False, occupe=False))
    if outro:
        out.append(_el('fin', 'fin', (0, 0, W, H), [], auto=False))
    intro = reel.get('intro') or {}
    if intro.get('enabled') and intro.get('file') and t < (intro.get('duration') or 0):
        out.append(_el('intro', 'intro', (0, 0, W, H), [], auto=False))
    for e in out:
        e.setdefault('debut', 0.0)
        e.setdefault('fin', ctx.total)
    return out


def _quand(e, debut, fin):
    """Instants d'apparition et de disparition d'un element (animations d'entree/sortie a eviter pour mesurer)."""
    e['debut'], e['fin'] = float(debut), float(fin)
    return e


# ---------------------------------------------------------------------------------------------------------------
# Fonds d'image (sans rendu) : prise d'origine cadree, ou personne detouree sur le studio / le collage
# ---------------------------------------------------------------------------------------------------------------
class Fonds:
    RED = 4        # image reduite 4x (1080x1920 -> 270x480)
    STUDIO = (6, 10, 20)
    COLLAGE = (231, 221, 199)

    def __init__(self, ctx):
        self.ctx = ctx
        self.w, self.h = ctx.W // self.RED, ctx.H // self.RED
        self._src = {}
        self._alpha = {}

    def _images(self, k):
        if k not in self._src:
            from .media import sample_frames
            seg = self.ctx.tl['video'][k]
            src = self.ctx.reel['sources'][seg['source']]
            path = ROOT / src['proxy']
            fr = self.ctx.image(seg['out_start'] + .01).get('f') or {'width': self.ctx.W}
            width = max(16, int(round(fr['width'] / self.RED / 2)) * 2)
            try:
                self._src[k] = sample_frames(path, fps=2, width=width, start=seg['src_in'], duration=seg['src_out'] - seg['src_in']) if path.exists() else []
            except Exception:
                self._src[k] = []
        return self._src[k]

    def _alpha_img(self, m, idx):
        key = (m.get('frames'), idx)
        if key not in self._alpha:
            import cv2
            p = ROOT / (m.get('frames') or '') / f'{idx:05d}.webp'
            im = cv2.imread(str(p), cv2.IMREAD_UNCHANGED) if p.exists() else None
            self._alpha[key] = im[:, :, 3].astype(np.float32) / 255 if im is not None and im.ndim == 3 and im.shape[2] == 4 else None
        return self._alpha[key]

    def image(self, t):
        """(rgb float HxWx3 de l'image finale reduite, masque personne ou None) ; None si inconnu."""
        import cv2
        ctx = self.ctx
        seg, fr = ctx.segment(t)
        if not seg or not fr.get('f'):
            return None
        ims = self._images(seg['index'] if seg['index'] < len(ctx.tl['video']) else 0)
        if not ims:
            return None
        ts = fr['tSrc']
        _, rgb = min(ims, key=lambda x: abs(x[0] - ts))
        f = fr['f']
        # image de la prise a l'ecran : camera du studio (studioView) pour la personne detouree comme pour le repli
        L, T, RW, RH = ctx.rect(t) if (ctx.studio(t) and ctx.vue(t)) else (f['left'], f['top'], f['width'], f['height'])
        dw, dh = max(2, int(round(RW / self.RED))), max(2, int(round(RH / self.RED)))
        src = cv2.resize(rgb, (dw, dh), interpolation=cv2.INTER_AREA).astype(np.float32)
        x0, y0 = int(round(L / self.RED)), int(round(T / self.RED))
        canvas = np.zeros((self.h, self.w, 3), np.float32)
        pers = None
        m = ctx.cutout(seg) if ctx.decoupe else None
        if m and ctx.studio(t) and ctx.repli(t) >= .5:
            # plage de repli : prise d'origine aux couleurs du studio, decor flou et sombre (brightness .42), personne nette
            # au centre ; aucun masque de personne fiable -> pas de mesure de « tiers vide » ici
            canvas = np.zeros((self.h, self.w, 3), np.float32)
            sx0, sy0, cx0, cy0 = max(0, -x0), max(0, -y0), max(0, x0), max(0, y0)
            cw, ch = min(self.w - cx0, dw - sx0), min(self.h - cy0, dh - sy0)
            if cw <= 0 or ch <= 0:
                return None
            canvas[cy0:cy0 + ch, cx0:cx0 + cw] = src[sy0:sy0 + ch, sx0:sx0 + cw] * .45
            return canvas, None
        a = None
        if m:
            idx = int(min((m.get('count') or 1) - 1, max(0, math.floor((ts - m['start']) * (m.get('fps') or ctx.reel['fps'])))))
            a = self._alpha_img(m, idx)
            if a is not None:
                a = cv2.resize(a, (dw, dh), interpolation=cv2.INTER_AREA)
        bg = self.STUDIO if ctx.cinematique else (self.COLLAGE if ctx.mode == 'collage' else None)
        if bg is not None and a is not None:
            canvas[:] = bg
        layer = np.zeros_like(canvas)
        alpha = np.zeros((self.h, self.w), np.float32)
        sx0, sy0 = max(0, -x0), max(0, -y0)
        cx0, cy0 = max(0, x0), max(0, y0)
        cw, ch = min(self.w - cx0, dw - sx0), min(self.h - cy0, dh - sy0)
        if cw <= 0 or ch <= 0:
            return None
        layer[cy0:cy0 + ch, cx0:cx0 + cw] = src[sy0:sy0 + ch, sx0:sx0 + cw]
        if bg is not None and a is not None:
            alpha[cy0:cy0 + ch, cx0:cx0 + cw] = a[sy0:sy0 + ch, sx0:sx0 + cw]
            canvas = canvas * (1 - alpha[..., None]) + layer * alpha[..., None]
            pers = alpha
        else:
            canvas = layer
            if a is not None:
                alpha[cy0:cy0 + ch, cx0:cx0 + cw] = a[sy0:sy0 + ch, sx0:sx0 + cw]
                pers = alpha
        if ctx.cinematique and a is not None:
            # ombre de contact du bas du studio (design.tsx : 30 % de la hauteur, #02040a 55 % a mi-hauteur puis 94 %)
            y = np.arange(self.h)[:, None] / self.h
            k = np.clip((y - .7) / .3, 0, 1)
            opac = np.where(k < .55, .55 * k / .55, .55 + (.94 - .55) * (k - .55) / .45)
            canvas = canvas * (1 - opac[..., None]) + np.array((2, 4, 10), np.float32) * opac[..., None]
        return canvas, pers

    def zone(self, t, box):
        """Statistiques de luminance relative dans une boite (px de l'image finale)."""
        r = self.image(t)
        if r is None:
            return None
        rgb, _ = r
        x0, y0 = int(max(0, box[0] // self.RED)), int(max(0, box[1] // self.RED))
        x1, y1 = int(min(self.w, math.ceil(box[2] / self.RED))), int(min(self.h, math.ceil(box[3] / self.RED)))
        if x1 <= x0 or y1 <= y0:
            return None
        return stats_zone(rgb[y0:y1, x0:x1])


def stats_zone(rgb):
    v = np.clip(rgb.astype(np.float32) / 255, 0, 1)
    lin = np.where(v <= .04045, v / 12.92, ((v + .055) / 1.055) ** 2.4)
    L = .2126 * lin[..., 0] + .7152 * lin[..., 1] + .0722 * lin[..., 2]
    y = .299 * rgb[..., 0] + .587 * rgb[..., 1] + .114 * rgb[..., 2]
    return {'L': float(L.mean()), 'L25': float(np.percentile(L, 25)), 'L75': float(np.percentile(L, 75)),
            'luma': float(y.mean()), 'ecart': float(y.std()), 'rgb': [float(x) for x in rgb.reshape(-1, 3).mean(0)]}


def contraste_texte(tx, fond_L, u=1080):
    """Contraste efficace d'un texte (remplissage + contour + ombre) sur un fond de luminance fond_L."""
    c = couleur(tx['couleur'])
    fond_rgb = None
    if tx.get('fond'):
        fond_rgb = couleur(tx['fond'])[:3]
        fond_L = luminance(fond_rgb)
    base = fond_rgb or (255 * fond_L ** (1 / 2.2),) * 3
    L = luminance(melange(c, base))
    cf = contraste(L, fond_L)
    eff = cf
    k = 1080 / u
    if tx.get('contour'):
        cs = contraste(L, luminance(couleur(tx.get('contour_coul'))))
        if tx['contour'] * k >= 2.5 and cs >= 4.5:
            eff = max(eff, 4.5)
        elif tx['contour'] * k >= 1.5 and cs >= 3:
            eff = max(eff, 3.0)
    if tx.get('ombre') and not fond_rgb:
        eff += .4
    if tx.get('halo') and not fond_rgb:  # lueur epaisse : la forme des lettres se lit sur le contraste lueur / fond
        eff = max(eff, contraste(luminance(couleur(tx['halo'])), fond_L))
    return cf, eff


def assombrir(L, voile):
    """Luminance relative d'un fond recouvert d'un voile noir d'opacite « voile » (melange CSS en sRGB)."""
    if not voile:
        return L
    g = 255 * max(0.0, L) ** (1 / 2.4) * (1 - voile)  # gris sRGB approche puis voile
    return luminance((g, g, g))


# ---------------------------------------------------------------------------------------------------------------
# Passe a : le JSON du reel
# ---------------------------------------------------------------------------------------------------------------
def _med(chemins, reel):
    """Fichiers medias utilises par le reel : (nom lisible, chemin, gravite si absent).
    Meme regle que remotion/render.mjs (verifierMedias) : seules les sources UTILISEES (plans, angle multicamera,
    plans de coupe) comptent, et l'export refuse de partir si proxy, rush, voix ou ambiance manque. Les prises
    inutilisees gardees dans reel.sources ne sont jamais signalees."""
    out = []
    sources = reel.get('sources') or {}
    utilisees = []
    for c in reel.get('clips') or []:
        utilisees += [c.get('source'), c.get('angle')]
    utilisees += [b.get('source') for b in reel.get('broll') or []]
    vus = set()
    for sid in utilisees:
        if not sid or sid in vus:
            continue
        vus.add(sid)
        s = sources.get(sid)
        nom = (s or {}).get('name') or sid
        if s is None:
            out.append((f"prise {sid} (absente de reel.sources)", ROOT / 'projects' / f'source-inconnue-{sid}', 'bloquant'))
            continue
        out.append((f"média optimisé de la prise {nom}", ROOT / (s.get('proxy') or f'proxy-absent-{sid}'), 'bloquant'))
        if s.get('path'):
            out.append((f"rush d'origine {nom} (son de l'export)", Path(s['path']) if Path(s['path']).is_absolute() else ROOT / s['path'], 'bloquant'))
        if s.get('voice'):
            out.append((f"voix nettoyée de {nom} (l'export refuse de partir sans elle)", ROOT / s['voice'], 'bloquant'))
        if s.get('roomtone'):
            out.append((f"ambiance de la pièce de {nom} (l'export refuse de partir sans elle)", ROOT / s['roomtone'], 'bloquant'))
    # un media absent fait echouer l'export (render.mjs refuse, ou Remotion echoue sur l'image introuvable) : bloquant.
    # Chemins : musique relative a assets/ ; images comme url() de Reel.tsx (« assets/... » ou relatif a la racine).
    m = reel.get('music') or {}
    if m.get('enabled') and m.get('file'):
        out.append(('musique', ROOT / 'assets' / m['file'], 'bloquant'))
    intro = reel.get('intro') or {}
    if intro.get('enabled') and intro.get('file'):
        out.append(('titre 3D', ROOT / intro['file'], 'bloquant'))
    brand = reel.get('brand') or {}
    if brand.get('logo'):
        out.append(('logo de la charte', ROOT / brand['logo'], 'bloquant'))
    for g in reel.get('graphics') or []:
        for k in ('image', 'file'):
            v = (g.get('props') or {}).get(k)
            if v and not g.get('suggested'):
                out.append((f"image du graphisme {g.get('id')}", ROOT / v, 'bloquant'))
    for e in chemins:
        out.append(e)
    return out


def passe_json(ctx, fonds):
    reel, W, H, u = ctx.reel, ctx.W, ctx.H, ctx.u
    out, mesures = [], {}
    n = len(ctx.tl['frames'])
    temps = [i * PAS for i in range(n)]
    accroche = ctx.accroche()
    mesures['accroche'] = round(accroche, 2)
    chev, sur_accroche, visage_c, visage_b, petits, internes = {}, {}, {}, {}, {}, {}
    entrees, prev = [], set()
    exemples = {}
    for t in temps:
        els = visibles(ctx, t)
        ids = {e['id'] for e in els}
        for e in els:
            if e['id'] not in exemples or (e['genre'] == 'sous-titres' and e['box'][3] > exemples[e['id']][1]['box'][3]):
                exemples[e['id']] = (t, e)
            if e['id'] not in prev and e['genre'] not in ('sous-titres', 'hud', 'logo', 'decor', 'decor-texte'):
                entrees.append(t)
        prev = ids
        # chevauchements
        actifs = [e for e in els if e['genre'] not in ('decor', 'fin', 'intro') and not e['derriere']]
        for i, a in enumerate(actifs):
            for b in actifs[i + 1:]:
                if a['genre'] == 'broll-plein' or b['genre'] == 'broll-plein':
                    if not (a['textes'] or b['textes']):
                        continue
                    if 'sous-titres' in (a['genre'], b['genre']):
                        continue  # sous-titres par-dessus un plan de coupe : normal
                ia = inter(a['box'], b['box'])
                if ia <= 0:
                    continue
                fr = ia / max(1.0, min(aire(a['box']), aire(b['box'])))
                if fr > .04:
                    k = tuple(sorted((a['id'], b['id'])))
                    chev.setdefault(k, []).append((t, fr, a, b))
        # habillage sur l'accroche
        if t < accroche:
            for e in els:
                if e['genre'] not in ('sous-titres', 'bandeau', 'hud', 'logo', 'decor', 'decor-texte', 'intro', 'fin'):
                    sur_accroche.setdefault(e['id'], []).append((t, e))
        # visage
        faces = [] if any(e['genre'] in ('broll-plein', 'fin', 'intro') for e in els) else ctx.visages(t)
        for e in els:
            if e['derriere'] or e['genre'] in ('hud', 'decor', 'logo'):
                continue
            if not (e['textes'] or e['carte'] or e['genre'] in ('broll-encadre', 'image', 'emoji')):
                continue
            meilleur_c, meilleur_b = None, None
            for vb in faces:  # deux visages pendant l'ecran partage du Comparatif : on garde le plus couvert
                fw, fh = vb[2] - vb[0], vb[3] - vb[1]
                coeur = (vb[0] + .15 * fw, vb[1] + .25 * fh, vb[2] - .15 * fw, vb[3] - .05 * fh)  # yeux -> bouche
                fc = inter(coeur, e['box']) / max(1.0, aire(coeur))
                fb = inter(vb, e['box']) / max(1.0, aire(vb))
                if fc > .02 and (meilleur_c is None or fc > meilleur_c[1]):
                    meilleur_c = (t, fc, e, vb)
                elif fb > .1 and (meilleur_b is None or fb > meilleur_b[1]):
                    meilleur_b = (t, fb, e, vb)
            if meilleur_c:
                visage_c.setdefault(e['id'], []).append(meilleur_c)
            elif meilleur_b:
                visage_b.setdefault(e['id'], []).append(meilleur_b)
        # textes
        for e in els:
            for tx in e['textes']:
                if not tx['texte'].strip():
                    continue
                norm = tx['px'] * 1080 / u
                seuils = TAILLE[tx['role']]
                g = 'bloquant' if norm < seuils[0] else ('important' if norm < seuils[1] else ('conseil' if norm < seuils[2] else None))
                if g and not e['interne'] and not e['genre'] == 'hud':
                    petits.setdefault((e['id'] if e['genre'] != 'sous-titres' else 'sous-titres', tx['role'], round(norm)), []).append((t, g, e, tx, norm))
                if e['genre'] != 'sous-titres':
                    txt = tx['texte'].strip()
                    titre = (reel.get('title') or '').strip()
                    raison = None
                    if INTERNE_FORT.search(txt):
                        raison, gr = 'mot de travail ou nom de fichier', 'bloquant'
                    elif INTERNE_MOT.search(txt) and (INTERNE_ETIQUETTE.search(txt) or (txt.isupper() and len(txt.split()) <= 3)):
                        raison, gr = 'étiquette de travail (exemple, illustration…)', 'important'
                    elif INTERNE_MOT.search(txt):
                        raison, gr = 'mot « exemple/illustration » dans une phrase : vérifier que ce n’est pas une étiquette de travail', 'conseil'
                    elif titre and txt.lower() == titre.lower() and not ((reel.get('brand') or {}).get('name') or '').lower() == txt.lower():
                        # « Vidéo 1 », « … COMPLET - Hook … » : nom de travail ; un vrai titre (Documentaire) peut etre voulu
                        if INTERNE_NOM.search(txt) or re.search(r'COMPLET|Hook|Script\s*\d|FINAL|\(\d+x\d+\)|^vid[ée]o\s*\d', txt, re.I):
                            raison, gr = 'titre interne du reel, champ reel.title', 'bloquant'
                        else:
                            raison, gr = 'titre du reel (reel.title) : vérifier que c’est un vrai titre pour le public', 'important'
                    elif INTERNE_NOM.search(txt):
                        raison, gr = 'nom interne (vidéo, prise, version)', 'bloquant'
                    elif TIMECODE.search(txt) and e['id'] in ('hud:temps',):
                        raison, gr = 'compteur de temps technique', 'important'
                    elif TIMECODE.search(txt) and e['genre'] == 'decor-texte':
                        raison, gr = 'compteur « REC » du style (volontaire ?)', 'conseil'
                    if raison:
                        internes.setdefault((e['id'], txt if e['id'] != 'hud:temps' else 'mm:ss'), []).append((t, gr, raison, e, tx))
    # -- constats : chevauchements
    for (a_id, b_id), v in chev.items():
        pl = plages([x[0] for x in v])
        fr = max(x[1] for x in v)
        a, b = v[0][2], v[0][3]
        textes = bool(a['textes']) and bool(b['textes'])
        g = 'important' if (fr > .25 or textes) else 'conseil'
        noms = f"{_nom(a)} et {_nom(b)}"
        out.append(constat(g, 'chevauchement', f"{noms[0].upper() + noms[1:]} se superposent ({plages_texte(pl)}).",
                           "Déplacer l'un des deux éléments ou décaler son apparition ; un seul message à la fois.",
                           f"recouvrement max {fr:.0%} de la plus petite boîte ; boîtes {_bx(a['box'])} / {_bx(b['box'])}", pl[0][0], pl[-1][1],
                           zone=(min(a['box'][0], b['box'][0]), min(a['box'][1], b['box'][1]), max(a['box'][2], b['box'][2]), max(a['box'][3], b['box'][3]))))
    # -- accroche
    for eid, v in sur_accroche.items():
        e = v[0][1]
        pl = plages([x[0] for x in v])
        g = 'important' if e['auto'] else 'conseil'
        if pl[0][0] < 3:
            quand = f"pendant les premiers mots ({plages_texte(pl)})"
        else:
            quand = f"pendant l'accroche ({ctx.accroche_source} : 0–{hms(accroche)}), de {hms(pl[0][0])} à {hms(pl[-1][1])}"
        out.append(constat(g, 'accroche-couverte', f"Accroche chargée : {_nom(e)} s'affiche {quand}, ce qui détourne l'attention.",
                           "Garder l'accroche nette (visage + sous-titres, éventuellement le bandeau) et faire entrer cet élément après.",
                           f"accroche = 0–{hms(accroche)} ({ctx.accroche_source}) ; élément « {_resume(e)} »", pl[0][0], pl[-1][1], zone=e['box'], element=e['id']))
    # -- visage
    for eid, v in visage_c.items():
        fc = max(x[1] for x in v)
        pl = plages([x[0] for x in v])
        e = v[0][2]
        g = 'bloquant' if fc > .3 else ('important' if fc > .08 else 'conseil')
        dur = sum(b - a for a, b in pl)
        if dur < 1.0:  # moins d'une seconde : genant, pas bloquant
            g = GRAVITES[min(2, GRAVITES.index(g) + 1)]
        sug = "Monter ou descendre l'élément pour dégager les yeux et la bouche."
        if e.get('ponctuel'):  # mot geant plein ecran : effet de ponctuation voulu par le style, bref
            g = 'conseil' if dur <= 1.5 else ('important' if g == 'bloquant' else g)
            sug = "Effet voulu (mot géant) : le garder court (1 s au plus), ou le placer sur un plan de coupe plutôt que sur le visage."
        tmax = max(v, key=lambda x: x[1])
        duree_txt = f'{dur:.1f}'.replace('.', ',')
        out.append(constat(g, 'visage-couvert', f"Visage en partie couvert par {_nom(e)} ({plages_texte(pl)} ; {duree_txt} s au total).", sug,
                           f"jusqu'à {fc:.0%} de la zone yeux-bouche couverte à {hms(tmax[0])} ; visage {_bx(tmax[3])}, élément {_bx(e['box'])}",
                           pl[0][0], pl[-1][1], zone=e['box'], element=e['id']))
    for eid, v in visage_b.items():
        if eid in visage_c:
            continue
        fb = max(x[1] for x in v)
        pl = plages([x[0] for x in v])
        e = v[0][2]
        out.append(constat('conseil', 'visage-frole', f"Bord du visage (front ou menton) touché par {_nom(e)} ({plages_texte(pl)}).",
                           "Laisser un peu d'air autour du visage.", f"{fb:.0%} de la boîte du visage touchée", pl[0][0], pl[-1][1], zone=e['box'], element=e['id']))
    # -- petits textes
    groupes = {}
    for (eid, role, norm), v in petits.items():
        groupes.setdefault((eid, role), []).append((norm, v))
    for (eid, role), lst in groupes.items():
        norm, v = min(lst, key=lambda x: x[0])
        allv = [x for _, vv in lst for x in vv]
        g = min((x[1] for x in allv), key=GRAVITES.index)
        e, tx = v[0][2], v[0][3]
        pl = plages([x[0] for x in allv])
        cible = TAILLE[role][2]
        if role == 'sous-titre':
            fmt = 'vertical' if H > W * 1.05 else ('horizontal' if W > H * 1.05 else 'carré')
            msg = f"Sous-titres petits pour un format {fmt} : {norm:.0f} px (lisibles sur téléphone à partir d'environ {cible} px)."
            sug = f"Passer la taille des sous-titres à {cible}–{cible + 12} px (onglet Style)."
        else:
            msg = f"Texte « {_court(tx['texte'])} » de {_nom(e)} trop petit : {norm:.0f} px ({plages_texte(pl, 2)})."
            sug = f"Agrandir ce texte à au moins {cible} px, ou raccourcir le texte pour pouvoir l'agrandir."
        out.append(constat(g, 'texte-petit', msg, sug, f"taille rendue {tx['px']:.1f} px sur {W}x{H} (= {norm:.0f} px pour 1080 px) ; rôle {role}",
                           pl[0][0], pl[-1][1], zone=e['box'], element=e['id']))
    # -- textes internes
    for (eid, txt), v in internes.items():
        t0, g, raison, e, tx = v[0]
        pl = plages([x[0] for x in v])
        dur = sum(b - a for a, b in pl)
        cite = f"« {tx['texte']} »" if eid != 'hud:temps' else f"« {tx['texte']} » → « {v[-1][4]['texte']} »"
        out.append(constat(g, 'texte-interne', f"Texte interne visible à l'écran : {cite} ({raison}), pendant {dur:.0f} s.",
                           "Retirer ce texte de l'habillage (ou le remplacer par le nom de la marque) : le public ne doit voir que le message.",
                           f"{_nom(e)} en {_bx(e['box'])}, {tx['px']:.0f} px ; visible {plages_texte(pl, 2)}", pl[0][0], pl[-1][1], zone=e['box'], element=e['id']))
    # -- sous-titres : hallucinations de transcription
    for p in ctx.tl['pages']:
        txt = ' '.join(w['w'] for w in p['words'])
        if HALLU.search(txt):
            out.append(constat('important', 'texte-interne', f"Sous-titre suspect « {_court(txt, 60)} » (texte ajouté par la transcription).",
                               "Supprimer ces mots dans l'onglet Texte.", 'motif de transcription automatique connu', p['start'], p['end']))
    # -- repetitions : mot begaye dans les sous-titres, meme message affiche deux fois
    out += _repetitions(ctx, exemples)
    # -- contraste (une mesure par page de sous-titres et par element)
    out += _contrastes(ctx, fonds, exemples, mesures)
    # -- cadre fige
    out += _fige(ctx, entrees, mesures)
    # -- tiers vides
    out += _tiers(ctx, fonds, mesures)
    # -- medias
    out += _medias(ctx)
    # -- detourage (JSON)
    out += _detourage_json(ctx, mesures)
    # -- son
    out += _son(ctx, mesures)
    # -- zones sures
    out += _zones_sures(ctx, exemples)
    return out, mesures


def _nom(e, majuscule=False):
    g = e['genre']
    noms = {'sous-titres': 'les sous-titres', 'bandeau': 'le bandeau', 'hud': "la marque en haut du studio", 'logo': 'le logo',
            'emoji': "l'emoji", 'broll-plein': 'le plan de coupe', 'broll-encadre': 'le plan de coupe encadré', 'mot-geant': 'le mot géant',
            'decor-texte': "le texte du décor", 'image': "l'image"}
    if g in noms:
        s = noms[g]
    elif g == 'carte':
        s = f"la carte « {_court(_resume(e))} »"
    elif g == 'graphique':
        s = f"le graphisme « {_court(_resume(e))} »"
    else:
        s = f"l'élément {e['id']}"
    return s[0].upper() + s[1:] if majuscule else s


def _resume(e):
    return ' / '.join(tx['texte'] for tx in e['textes'] if tx['role'] == 'principal')[:60] or e['id']


def _court(s, n=40):
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + '…'


def _bx(b):
    return f"[{b[0]:.0f},{b[1]:.0f} → {b[2]:.0f},{b[3]:.0f}]"


def _repetitions(ctx, exemples):
    out = []
    ws = [w for w in ctx.tl['words'] if not w['hide']]
    begaye = []
    for a, b in zip(ws, ws[1:]):
        na, nb = affiche(a['w']).lower(), affiche(b['w']).lower()
        if (na and na == nb and a['clip'] == b['clip'] and b['index'] == a['index'] + 1 and b['start'] - a['end'] < .6
                and not re.search(r'[,.;:!?…]$', a['w'].strip()) and len(na) > 1):
            begaye.append((a, b))
    for a, b in begaye[:6]:
        out.append(constat('conseil', 'mot-repete', f"Mot répété dans les sous-titres : « {affiche(a['w'])} {affiche(b['w'])} » (hésitation probable).",
                           "Couper l'un des deux mots dans l'onglet Texte (la vidéo est coupée avec).", f"plan {a['clip']}, mots {a['index']}-{b['index']}",
                           a['start'], b['end']))
    vus = {}
    for eid, (t, e) in exemples.items():
        if e['genre'] in ('carte', 'graphique') and e['textes']:
            vus.setdefault(_resume(e).lower(), []).append((e['debut'], e))
    for txt, v in vus.items():
        if len(v) >= 2 and txt:
            v.sort(key=lambda x: x[0])
            out.append(constat('conseil', 'message-repete', f"Le même message « {_court(_resume(v[0][1]))} » s'affiche {len(v)} fois.",
                               "Varier le message ou garder une seule apparition, au moment le plus fort.",
                               ', '.join(hms(x[0]) for x in v), v[0][0], v[-1][0] + 1))
    return out


def _contrastes(ctx, fonds, exemples, mesures):
    out = []
    faibles = {}
    cartes = {}
    vus = set()
    pages = ctx.tl['pages']
    points = []
    for p in pages:
        points.append((p['start'] + min(.3, (p['end'] - p['start']) / 2), None))
    for eid, (t, e) in exemples.items():
        if e['genre'] != 'sous-titres':
            points.append((min(e['debut'] + .45, (e['debut'] + e['fin']) / 2), eid))
    for t, eid in points:
        vis = visibles(ctx, t)
        voile = max([x.get('voile') or 0 for x in vis] or [0])  # voile plein ecran (mot geant) sous les textes
        for e in vis:
            if (eid and e['id'] != eid) or (not eid and e['genre'] != 'sous-titres'):
                continue
            z = fonds.zone(t, e['box']) if fonds else None
            for tx in e['textes']:
                if not tx['texte'].strip():
                    continue
                if tx.get('fond') is None and z is None:
                    continue
                clair = luminance(couleur(tx['couleur'])) > .4
                fl = assombrir((z['L75'] if clair else z['L25']) if z else .02, voile)
                cf, eff = contraste_texte(tx, fl, ctx.u)
                norm = tx['px'] * 1080 / ctx.u
                seuil = (1.7, 2.4) if norm >= 80 else (2.0, 3.0)
                if eff < seuil[1]:
                    k = e['id'] if e['genre'] != 'sous-titres' else 'sous-titres:' + tx['couleur']
                    faibles.setdefault(k, []).append((t, eff, cf, e, tx, z))
            # carte qui se confond avec le decor (une carte a liseré clair et lueur se detache par son bord : la mesure
            # sur l'image, passe video, reste faite)
            if e['carte'] and not e.get('lisere') and z is not None and e['id'] not in vus:
                vus.add(e['id'])
                x0, y0, x1, y1 = e['box']
                m = max(12, .06 * ctx.W)
                autour = [fonds.zone(t, bx) for bx in ((x0 - m, y0, x0, y1), (x1, y0, x1 + m, y1), (x0, y0 - m, x1, y0), (x0, y1, x1, y1 + m))]
                autour = [a for a in autour if a]
                if autour:
                    L_aut = float(np.mean([a['L'] for a in autour]))
                    rgb_aut = np.mean([a['rgb'] for a in autour], axis=0)
                    cc = couleur(e['carte'])
                    L_carte = luminance(melange(cc, rgb_aut))
                    r = contraste(L_carte, L_aut)
                    cartes[e['id']] = round(r, 2)
                    if r < 1.25:
                        teinte = 'carte claire sur fond clair' if L_carte > .35 else 'carte sombre sur décor sombre'
                        out.append(constat('conseil', 'carte-terne', f"{_nom(e, True)} se confond avec le fond ({teinte}) : l'ensemble paraît terne.",
                                           "Éclaircir le fond de la carte, ajouter un liseré de la couleur d'accent ou une ombre plus marquée.",
                                           f"contraste carte/fond {r:.2f}:1 (visible à partir d'environ 1,25:1)", e['debut'], e['fin'], zone=e['box'], element=e['id']))
    for k, v in faibles.items():
        pire = min(v, key=lambda x: x[1])
        t, eff, cf, e, tx, z = pire
        norm = tx['px'] * 1080 / ctx.u
        seuil = (1.7, 2.4) if norm >= 80 else (2.0, 3.0)
        g = 'important' if eff < seuil[0] else 'conseil'
        fondtxt = f"fond {tx['fond']}" if tx.get('fond') else (f"image dessous (luminance moyenne {z['luma']:.0f}/255)" if z else 'fond inconnu')
        pl = plages([x[0] for x in v], 1.0)
        quoi = f"Sous-titres « {_court(tx.get('cite') or tx['texte'], 50)} »" if e['genre'] == 'sous-titres' else f"Texte « {_court(tx['texte'])} »"
        out.append(constat(g, 'contraste-faible', f"{quoi} peu contrastés sur leur fond ({len(v)} passage(s))." if e['genre'] == 'sous-titres'
                           else f"{quoi} peu contrasté sur son fond ({len(v)} passage(s)).",
                           "Ajouter un contour ou une ombre plus forte, changer la couleur du texte ou poser le texte sur une carte.",
                           f"contraste {cf:.1f}:1 (efficace {eff:.1f}:1 avec contour/ombre) ; couleur {tx['couleur']} ; {fondtxt}", t, t + 1, zone=e['box'], element=e['id']))
    mesures['contraste_cartes'] = cartes
    return out


def _fige(ctx, entrees, mesures):
    reel = ctx.reel
    ev = set()
    for s in ctx.tl['video'][1:]:
        ev.add(round(s['out_start'], 2))
    z = reel.get('zoom') or {}
    prevz = 1.0
    invisibles = 0
    camera = 0
    dernier = -9.0
    fr_list = ctx.tl['frames']
    for i, fr in enumerate(fr_list):
        zz = fr.get('zoom') or 1
        studio = ctx.studio(fr['t'])
        if zz > 1.004 and prevz <= 1.004:
            if studio and not fr.get('view'):
                invisibles += 1  # ancien rendu : studio opaque sur la video zoomee, sans camera a lui
            elif not studio:
                ev.add(round(fr['t'], 2))
        prevz = zz
        # camera du studio (studioView) : une poussee ou un recadrage d'au moins 2,5 % en 1,5 s est une relance visible
        v = fr.get('view') if studio else None
        if v and fr['t'] - dernier > 2.5:
            j = max(0, i - int(round(1.5 / PAS)))
            v0 = fr_list[j].get('view') if ctx.studio(fr_list[j]['t']) else None
            if v0 and abs(v['scale'] - v0['scale']) >= .025 * v0['scale']:
                ev.add(round(fr['t'], 2))
                camera += 1
                dernier = fr['t']
    for t in entrees:
        ev.add(round(t, 2))
    mouvement = (z.get('push') or 0) >= .04 and not ctx.cinematique
    pts = sorted(x for x in ev if 0 < x < ctx.total)
    bornes = [0.0] + pts + [ctx.total]
    trous = [(a, b) for a, b in zip(bornes, bornes[1:]) if b - a > FIGE and not mouvement]
    mesures['relances'] = len(pts)
    mesures['plus_long_plan_fixe'] = round(max((b - a for a, b in zip(bornes, bornes[1:])), default=0), 2)
    mesures['zooms_invisibles'] = invisibles
    mesures['mouvements_camera_studio'] = camera
    out = []
    if trous:
        pire = max(b - a for a, b in trous)
        part = sum(b - a for a, b in trous) / max(1, ctx.total)
        g = 'important' if (pire > FIGE * 1.5 or part > .35) else 'conseil'
        plus_long = f'{pire:.1f}'.replace('.', ',')
        out.append(constat(g, 'cadre-fige', f"Image sans relance visuelle (coupe, zoom, graphisme) pendant plus de {FIGE:.0f} s à {len(trous)} endroit(s) ; le plus long : {plus_long} s.",
                           "Ajouter un zoom motivé sur un mot fort, un changement de cadre ou un plan de coupe au milieu de ces passages.",
                           f"passages : {plages_texte([[a, b] for a, b in trous], 5)} ; {part:.0%} de la vidéo ; {len(pts)} relances au total",
                           trous[0][0], trous[-1][1]))
    if invisibles:
        out.append(constat('important', 'zoom-invisible', f"{invisibles} zoom(s) automatique(s) ne se voient pas : le studio virtuel recouvre la vidéo zoomée.",
                           "Appliquer le zoom à la personne détourée du studio (à corriger dans le moteur de rendu) ou ajouter une autre relance.",
                           "mode Tech 3D cinématique : ProductStage (opaque) est dessiné au-dessus de SegmentVideo, seul élément zoomé", None))
    return out


def _tiers(ctx, fonds, mesures):
    if not fonds:
        return []
    W, H = ctx.W, ctx.H
    res = {'haut': [], 'bas': []}
    t = 0.25
    while t < ctx.total:
        r = fonds.image(t)
        # sans masque de la personne (prise d'origine plein cadre) on ne sait pas si le tiers est vide : une image
        # sombre ou un mur uni derriere la tete n'est pas un « tiers vide ». Le controle vise les decors refaits
        # (studio Tech 3D, collage, editorial) ou la personne detouree peut laisser un grand vide.
        if r is not None and r[1] is not None:
            rgb, pers = r
            synthetique = ctx.cinematique or ctx.mode == 'collage'
            els = [e for e in visibles(ctx, t) if e['occupe'] and not e['derriere']]
            for nom, (a, b) in (('haut', (0, H / 3)), ('bas', (2 * H / 3, H))):
                zone = (0, a, W, b)
                if any(inter(e['box'], zone) > .12 * aire(zone) or (e['textes'] and inter(e['box'], zone) > 0) for e in els):
                    continue
                y0, y1 = int(a / fonds.RED), int(b / fonds.RED)
                part = rgb[y0:y1]
                y = .299 * part[..., 0] + .587 * part[..., 1] + .114 * part[..., 2]
                cov = float(pers[y0:y1].mean())
                # decor refait (uni par construction) : seul le masque compte, pas la luminance (une personne tres
                # sombre sur le studio sombre reste une personne) ; decor reel derriere : il doit aussi etre uni
                if cov < .08 and (synthetique or y.std() < 6):
                    res[nom].append(t)
        t += .5
    out = []
    for nom, ts in res.items():
        pl = [p for p in plages(ts, .5) if p[1] - p[0] >= TIERS_VIDE[0]]
        mesures[f'tiers_{nom}_vide_s'] = round(sum(b - a for a, b in plages(ts, .5)), 1)
        if pl:
            pire = max(b - a for a, b in pl)
            g = 'important' if pire >= TIERS_VIDE[1] else 'conseil'
            regle = ('personne détourée < 8 % de la zone (décor refait)' if (ctx.cinematique or ctx.mode == 'collage')
                     else 'personne détourée < 8 % de la zone et décor uni (écart-type de luminance < 6/255)')
            zone = (0, 0, W, H / 3) if nom == 'haut' else (0, 2 * H / 3, W, H)
            out.append(constat(g, 'tiers-vide', f"Le tiers {nom} de l'image reste vide (décor uni, sans personne ni texte) pendant {pire:.0f} s d'affilée.",
                               "Rapprocher le cadre de la personne ou y placer une information utile (titre, carte, chiffre).",
                               f"passages : {plages_texte(pl, 3)} ; {regle}", pl[0][0], pl[-1][1], zone=zone, plages_s=pl))
    return out


def _medias(ctx):
    reel = ctx.reel
    out = []
    manquants = []
    for nom, p, g in _med([], reel):
        if not p.exists():
            manquants.append((nom, p, g))
    for nom, p, g in manquants:
        out.append(constat(g, 'media-manquant', f"Fichier manquant : {nom}.", "Remettre le fichier à sa place ou refaire la préparation du reel.", str(p)))
    m = reel.get('sfx') or {}
    if m.get('enabled'):
        for e in ctx.tl.get('sfx') or []:
            n = str(e['name'])  # meme regle que sfxFile (timeline.ts) : nom court ou chemin de banque relatif a assets/
            rel = '/'.join(x for x in n.replace('\\', '/').split('/') if x and x not in ('.', '..')) if '/' in n else f'sfx/editeur/{n}.wav'
            p = ROOT / 'assets' / rel
            if not p.exists():
                out.append(constat('conseil', 'media-manquant', f"Bruitage manquant : {e['name']}.", "Choisir un autre bruitage.", str(p), e['t']))
                break
    if ctx.decoupe:
        vus = set()
        for s in ctx.tl['video']:
            m = ctx.cutout(s)
            if not m or s['clip'] in vus:
                continue
            vus.add(s['clip'])
            dossier = ROOT / (m.get('frames') or '')
            if not m.get('frames') or not dossier.exists():
                out.append(constat('bloquant', 'media-manquant', f"Images du détourage absentes pour le plan {s['clip']}.",
                                   "Actualiser le détourage (onglet Style).", str(dossier), s['out_start']))
                continue
            besoin = max(math.floor((x['src_out'] - m['start']) * (m.get('fps') or reel['fps'])) for x in ctx.tl['video'] if x['clip'] == s['clip'])
            if besoin > (m.get('count') or 0):
                out.append(constat('important', 'detourage-court', f"Le détourage du plan {s['clip']} est plus court que le plan : la personne se fige à la fin.",
                                   "Actualiser le détourage après avoir élargi la coupe.", f"{m.get('count')} images pour {besoin} nécessaires", s['out_start']))
            else:
                derniere = dossier / f"{max(0, besoin - 1):05d}.webp"
                if not derniere.exists():
                    out.append(constat('bloquant', 'media-manquant', f"Images du détourage incomplètes pour le plan {s['clip']}.",
                                       "Actualiser le détourage.", str(derniere), s['out_start']))
    return out


def _detourage_json(ctx, mesures):
    if not ctx.decoupe:
        return []
    out = []
    vieux, notes, replis = [], [], []
    for s in ctx.tl['video']:
        m = ctx.cutout(s)
        if not m:
            continue
        eng = str(m.get('engine') or 'mediapipe')
        if 'mediapipe' in eng and s['clip'] not in [x[0] for x in vieux]:
            vieux.append((s['clip'], m.get('width'), m.get('height')))
        q = m.get('quality')
        if q and (ROOT / q).exists():
            try:
                rq = json.loads((ROOT / q).read_text(encoding='utf-8'))
                notes.append((s['clip'], rq.get('score_moyen'), rq.get('score_min')))
            except (OSError, ValueError):
                pass
        for a, b in m.get('fallback') or []:
            lo, hi = max(a, s['src_in']), min(b, s['src_out'])
            if hi > lo:
                replis.append((s['out_start'] + (lo - s['src_in']) / (s.get('speed') or 1), s['out_start'] + (hi - s['src_in']) / (s.get('speed') or 1)))
    sans = [s for s in ctx.tl['video'] if not s.get('cutout')]
    if ctx.cinematique and sans:
        out.append(constat('conseil', 'detourage-absent', f"{len(sans)} plan(s) sans détourage valide : le studio virtuel y est remplacé par la prise d'origine.",
                           "Actualiser le détourage pour garder un style homogène.", ', '.join(f"{s['clip']} à {hms(s['out_start'])}" for s in sans[:4]),
                           sans[0]['out_start']))
    mesures['detourage_moteur'] = 'mediapipe' if vieux else ('rvm' if notes else None)
    if vieux:
        w = vieux[0][1]
        out.append(constat('important', 'detourage-basse-resolution',
                           f"Détourage fait avec l'ancien moteur basse résolution (MediaPipe) sur {len(vieux)} plan(s) : bords en escalier et morceaux du décor probables.",
                           "Actualiser le détourage avec le moteur RVM (pleine résolution) avant de livrer.",
                           f"masque MediaPipe 256x256 agrandi vers {w} px puis {ctx.W} px ; plans {', '.join(x[0] for x in vieux)}", None))
    for clip, moy, mini in notes:
        if moy is not None and moy < .7:
            out.append(constat('important', 'detourage-note', f"Qualité du détourage faible sur le plan {clip} (note moyenne {moy:.2f}/1).",
                               "Vérifier ce plan ; garder la prise d'origine si les bords restent mauvais.", f"qualite.json : moyenne {moy}, minimum {mini}"))
    mesures['detourage_repli_s'] = round(sum(b - a for a, b in replis), 2)
    if replis and ctx.rendu.get('repli'):
        # rendu a jour (cutoutFallbackMix) : sur ces plages la prise d'origine remplace la personne detouree, en fondu
        # (studio : prise aux couleurs du studio, decor flou et sombre ; Collage : prise d'origine) -> simple information
        duree = f"{mesures['detourage_repli_s']:.1f}".replace('.', ',')
        out.append(constat('conseil', 'detourage-repli', f"{len(replis)} passage(s) ({duree} s) où le détourage est jugé douteux : le rendu y montre la prise d'origine (fondu).",
                           "Regarder ces passages : si le changement se voit trop, actualiser le détourage ou choisir une autre prise.",
                           f"qualite.json (plages de repli, cutouts[plan].fallback) : {plages_texte([list(r) for r in replis])}", replis[0][0], replis[-1][1],
                           plages_s=[list(r) for r in replis]))
    elif replis:
        # ancien rendu (sans cutoutFallbackMix) : ces images douteuses sont affichees telles quelles
        out.append(constat('important', 'detourage-repli', f"{len(replis)} passage(s) où le moteur de détourage juge son propre masque mauvais ; le rendu actuel l'affiche quand même.",
                           "Vérifier ces passages à l'image ; si les bords sont mauvais, garder la prise d'origine sur ce plan.",
                           f"qualite.json (plages de repli) : {plages_texte([list(r) for r in replis])}", replis[0][0], replis[-1][1]))
    if ctx.cinematique:
        chaud, avant = [], []
        vus = set()
        for s in ctx.tl['video']:
            if not s.get('cutout') or s['source'] in vus:
                continue
            vus.add(s['source'])
            sm = [p for p in (ctx.reel['sources'][s['source']].get('samples') or []) if len(p) >= 7]
            if not sm:
                continue
            rgb = np.array([float(np.median([p[k] for p in sm])) for k in (4, 5, 6)])
            avant.append(rgb[0] - rgb[2])
            M = s.get('grade')
            if M and len(M) >= 15:
                # etalonnage du studio applique par le rendu (studioGrade : matrice feColorMatrix 4x5, sRGB 0-1)
                c = rgb / 255
                rgb = np.array([sum(M[i * 5 + j] * c[j] for j in range(3)) + M[i * 5 + 4] for i in range(3)]) * 255
            chaud.append(float(rgb[0] - rgb[2]))
        if chaud and np.median(chaud) > 45 and ctx.rendu.get('etalonnage'):
            out.append(constat('conseil', 'integration-lumiere', "La personne reste plus chaude que le studio bleu froid, même après l'étalonnage automatique du rendu.",
                               "Refroidir un peu plus la prise (onglet Plan → lumière/couleur : température) ou choisir un accent plus chaud pour le studio.",
                               f"visage rouge−bleu médian {np.median(chaud):.0f}/255 après étalonnage (avant : {np.median(avant):.0f}) contre studio bleuté (6,10,20)"))
        elif chaud and np.median(chaud) > 45:
            out.append(constat('conseil', 'integration-lumiere', "La personne paraît « collée » : lumière chaude du bureau sur un studio bleu froid, sans ombre ni liseré.",
                               "Refroidir légèrement la personne, ajouter une lumière de contour de la couleur d'accent et une ombre douce au sol.",
                               f"visage rouge−bleu médian {np.median(chaud):.0f}/255 contre studio bleuté (6,10,20)"))
    return out


def loudness(path, debut=None, duree=None):
    """Mesure EBU R128 : {'I': LUFS, 'LRA': LU, 'TP': dBTP} ou None."""
    args = [FFMPEG, '-hide_banner', '-nostats']
    if debut is not None:
        args += ['-ss', f'{debut:.3f}']
    args += ['-i', str(path)]
    if duree is not None:
        args += ['-t', f'{duree:.3f}']
    args += ['-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-']
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    txt = r.stderr
    k = txt.rfind('Summary:')
    if k < 0:
        return None
    s = txt[k:]
    get = lambda pat: (lambda m: float(m.group(1)) if m else None)(re.search(pat, s, re.S))
    return {'I': get(r'I:\s+(-?[\d.]+|-inf) LUFS'), 'LRA': get(r'LRA:\s+(-?[\d.]+) LU'), 'TP': get(r'True peak:.*?Peak:\s+(-?[\d.]+|-inf) dBFS')}


def _son(ctx, mesures):
    reel = ctx.reel
    out = []
    m = reel.get('music') or {}
    if not ctx.tl['words']:
        return out
    if m.get('enabled') and m.get('file') and (ROOT / 'assets' / m['file']).exists():
        L = loudness(ROOT / 'assets' / m['file'], 0, 60)
        if L and L.get('I') is not None and L['I'] > -70:
            vol = m.get('volume') or 0
            if vol <= 0:
                return out
            sous = LOUDNESS[0] - (L['I'] + 20 * math.log10(vol * .45))   # musique baissee de 55 % pendant la parole
            mesures['musique_sous_voix_db'] = round(sous, 1)
            mesures['musique_lufs_fichier'] = L['I']
            if sous < 12:
                out.append(constat('important', 'musique-forte', f"Musique trop forte sous la voix : seulement {sous:.0f} dB en dessous (norme 18–25 dB).",
                                   "Baisser le volume de la musique (onglet Style).", f"fichier {L['I']:.1f} LUFS × volume {vol} × baisse 0,45 pendant la parole"))
            elif sous < 16:
                out.append(constat('conseil', 'musique-forte', f"Musique un peu présente sous la voix : {sous:.0f} dB en dessous (norme 18–25 dB).",
                                   "Baisser légèrement la musique.", f"fichier {L['I']:.1f} LUFS × volume {vol} × 0,45"))
            elif sous > 32:
                out.append(constat('conseil', 'musique-faible', f"Musique presque inaudible : {sous:.0f} dB sous la voix.",
                                   "Monter un peu la musique ou la couper.", f"fichier {L['I']:.1f} LUFS × volume {vol} × 0,45"))
    return out


def _zones_sures(ctx, exemples):
    """Zones couvertes par l'interface des applis (Reels, TikTok) : 14 % en haut, bas au-dela de 80 %."""
    if ctx.H <= ctx.W * 1.05:
        return []
    out = []
    for eid, (t, e) in exemples.items():
        if not e['textes'] or e['genre'] in ('hud', 'decor-texte'):
            continue
        x0, y0, x1, y1 = e['box']
        if y1 > ctx.H * .86:
            out.append(constat('important' if e['genre'] == 'sous-titres' else 'conseil', 'zone-sure',
                               f"Zone masquée par l'appli (légende, boutons) : {_nom(e)} y descend jusqu'à {y1 / ctx.H:.0%} de la hauteur.",
                               "Remonter l'élément au-dessus de 80 % de la hauteur.", f"bas de la boîte à {y1 / ctx.H:.0%} de la hauteur", t, zone=e['box'], element=e['id']))
        elif y0 < ctx.H * .06 - 4:  # 4 px de tolerance : le studio pose ses interfaces exactement a 6 % (STUDIO_TOP)
            out.append(constat('conseil', 'zone-sure', f"Zone masquée par l'appli (nom du compte) : {_nom(e)} commence à {y0 / ctx.H:.0%} de la hauteur.",
                               "Descendre l'élément sous 14 % de la hauteur.", f"haut de la boîte à {y0 / ctx.H:.0%} de la hauteur", t, zone=e['box'], element=e['id']))
    return out


# ---------------------------------------------------------------------------------------------------------------
# Passe b : video exportee ou apercu court
# ---------------------------------------------------------------------------------------------------------------
class Reference:
    """Masque de personne de reference (RobustVideoMatting, pleine resolution) ; libere la carte graphique."""

    def __init__(self):
        import torch
        self.torch = torch
        # is_available() peut repondre oui sans aucun appareil (CUDA_VISIBLE_DEVICES vide, pilote occupe) : on verifie
        # le nombre d'appareils, et au moindre echec sur la carte graphique on repasse sur le processeur (modele leger)
        essais = []
        try:
            if torch.cuda.is_available() and torch.cuda.device_count() > 0:
                essais.append(('cuda', 'rvm_resnet50_fp32.torchscript'))
        except Exception:
            pass
        essais.append(('cpu', 'rvm_mobilenetv3_fp32.torchscript'))
        erreur = None
        for dev, nom in essais:
            try:
                self.model = torch.jit.load(str(ROOT / 'models/rvm' / nom), map_location=torch.device(dev)).eval()
                self.dev, self.nom = dev, nom.split('_fp32')[0]
                return
            except Exception as e:  # modele absent ou carte graphique indisponible
                erreur = e
                if dev == 'cuda':
                    torch.cuda.empty_cache()
        raise RuntimeError(f'modèle RVM de référence indisponible ({erreur})')

    def masque(self, rgb):
        t = self.torch
        h, w = rgb.shape[:2]
        x = t.from_numpy(np.array(rgb, dtype=np.uint8, copy=True)).permute(2, 0, 1)[None].float().div(255).to(self.dev)
        rec = [None] * 4
        ratio = float(min(1.0, max(.1, 480 / max(h, w))))
        with t.no_grad():
            for _ in range(3):  # image isolee : quelques passes pour stabiliser la memoire du modele
                _, pha, *rec = self.model(x, *rec, ratio)
        return pha[0, 0].float().cpu().numpy()

    def close(self):
        self.model = None
        if self.dev == 'cuda':
            self.torch.cuda.empty_cache()


def _rendu_plus_recent(video):
    """Vrai si le moteur de rendu (remotion/src, meme empreinte que render.mjs : noms + dates des fichiers) a change apres
    la video : celle-ci a ete rendue avec une mise en page plus ancienne que celle que ce module reproduit."""
    try:
        src = max(p.stat().st_mtime for p in (ROOT / 'remotion/src').iterdir() if p.suffix in ('.ts', '.tsx'))
        return Path(video).stat().st_mtime < src - 60
    except (OSError, ValueError):
        return False


def _lire_images(video, pas, w, h):
    proc = subprocess.Popen([FFMPEG, '-v', 'error', '-i', str(video), '-vf', f'fps={1 / pas:.6f}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    i = 0
    try:
        while True:
            raw = proc.stdout.read(w * h * 3)
            if len(raw) < w * h * 3:
                break
            yield i * pas, np.frombuffer(raw, np.uint8).reshape(h, w, 3)
            i += 1
    finally:
        proc.stdout.close()
        proc.wait()


def _image_source(path, t):
    info = probe(path)
    w, h = info['width'], info['height']
    raw = subprocess.run([FFMPEG, '-v', 'error', '-ss', f'{max(0, t):.3f}', '-i', str(path), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3) if len(raw) >= w * h * 3 else None


def _filtres(video):
    """Images noires et figees (FFmpeg blackdetect + freezedetect)."""
    r = subprocess.run([FFMPEG, '-hide_banner', '-nostats', '-i', str(video), '-an', '-vf',
                        'blackdetect=d=0.2:pix_th=0.08,freezedetect=n=-60dB:d=1.0', '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    noirs = [(float(a), float(b)) for a, b in re.findall(r'black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)', r.stderr)]
    fs = [float(x) for x in re.findall(r'freeze_start:\s*([\d.]+)', r.stderr)]
    fe = [float(x) for x in re.findall(r'freeze_end:\s*([\d.]+)', r.stderr)]
    figes = list(zip(fs, fe + [None] * (len(fs) - len(fe))))
    return noirs, figes


def _mesure_detourage(A, P, echelle):
    """A = alpha du detourage utilise, P = masque de reference, meme taille. Mesures en px de l'image finale."""
    import cv2
    pers = float(((A > .5) & (P > .5)).sum()) or 1.0
    reste = ((A > .35) & (P < .15)).astype(np.uint8)
    reste = cv2.morphologyEx(reste, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(reste)
    mini = max(60, int(.0004 * A.size))
    blocs = [i for i in range(1, n) if st[i, 4] >= mini]
    masque_reste = np.isin(lab, blocs) if blocs else np.zeros_like(reste, bool)
    # morceaux detaches de la personne (sans reference)
    m = (A > .35).astype(np.uint8)
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(m)
    detaches = 0
    if n2 > 2:
        princ = 1 + int(np.argmax(st2[1:, 4]))
        detaches = int(sum(st2[i, 4] for i in range(1, n2) if i != princ and st2[i, 4] >= mini))
    voile = float(((A > .06) & (A < .6) & (P < .08)).sum())

    def rampe(a):
        cs, _ = cv2.findContours((a > .5).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        per = sum(cv2.arcLength(c, True) for c in cs if len(c) > 40)
        return float(((a > .1) & (a < .9)).sum()) / max(1.0, per)

    ra, rp = rampe(A) * echelle, rampe(P) * echelle
    # detail du masque : ce qu'il reste apres un passage par 256 px (masque basse resolution = presque rien)
    def detail(a, band):
        h, w = a.shape
        b = cv2.resize(cv2.resize(a, (256, max(8, round(256 * h / w))), interpolation=cv2.INTER_AREA), (w, h), interpolation=cv2.INTER_LINEAR)
        return float(np.abs(a - b)[band].mean()) if band.any() else 0.0
    band = cv2.dilate((((A > .03) & (A < .97)) | ((P > .03) & (P < .97))).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    da, dp = detail(A, band), detail(P, band)
    return {'restes': float(masque_reste.sum()) / pers, 'blocs': len(blocs), 'detaches': detaches / pers, 'voile': voile / pers,
            'rampe_px': round(ra, 1), 'rampe_ref_px': round(rp, 1), 'detail': round(da / max(1e-6, dp), 2), 'masque_restes': masque_reste}


def passe_video(ctx, video, debut, preuves, profond=True, pas=0.5, max_detourage=14):
    import cv2
    from . import analyze
    out, mes = [], {}
    info = probe(video)
    VW, VH = info['width'], info['height']
    W, H = ctx.W, ctx.H  # toutes les boites sont en px du reel : les images sont ramenees a cette taille
    duree = info['duration']
    meme_forme = abs(VW / max(1, VH) - W / H) < .01
    images_ok = meme_forme
    # video rendue AVANT la derniere modification du moteur de rendu (remotion/src) : les boites des elements (calculees
    # pour le rendu actuel) ne correspondent plus forcement a l'image -> pas de mesure a l'image par element (lisibilite,
    # cartes, visage masque) ; detourage, visage present, son, images noires/figees restent mesures sur la video
    ancien = images_ok and _rendu_plus_recent(video)
    mise_en_page = images_ok and not ancien
    mes['video'] = {'fichier': str(video), 'largeur': VW, 'hauteur': VH, 'duree': round(duree, 2), 'debut_dans_reel': round(debut, 2),
                    'images_controlees': images_ok, 'mise_en_page_controlee': mise_en_page}
    if ancien:
        out.append(constat('conseil', 'rendu-ancien', "Vidéo rendue avant la dernière mise à jour du moteur de rendu : la mise en page contrôlée est celle d'un export fait aujourd'hui.",
                           "Refaire l'export (ou un court aperçu) pour contrôler la mise en page à l'image ; le détourage, le son et les images noires/figées sont bien mesurés sur cette vidéo.",
                           "date du fichier vidéo antérieure à celle de remotion/src (cartes, lisibilité et visage masqué non mesurés à l'image)"))
    if (VW, VH) != (W, H):
        if meme_forme:
            out.append(constat('conseil', 'format', f"La vidéo fait {VW}x{VH}, plus petite que le reel ({W}x{H}) : contrôlée agrandie, à confirmer sur l'export final.",
                               "Contrôler aussi l'export en pleine résolution avant de livrer.", f"ffprobe : {VW}x{VH}"))
        else:
            out.append(constat('important', 'format', f"La vidéo fait {VW}x{VH} alors que le reel est en {W}x{H} : autre format, contrôle à l'image sauté.",
                               "Vérifier que c'est le bon fichier ; une déclinaison se contrôle avec son propre reel.", f"ffprobe : {VW}x{VH}"))
    if debut == 0 and abs(duree - ctx.total) > .3:
        out.append(constat('important', 'duree', f"Durée de la vidéo ({duree:.1f} s) différente du montage ({ctx.total:.1f} s).",
                           "Refaire l'export ; vérifier qu'il n'a pas été interrompu.", f"ffprobe {duree:.2f} s / montage {ctx.total:.2f} s"))
    # noirs / figes
    noirs, figes = _filtres(video)
    for a, b in noirs:
        out.append(constat('important' if b - a > .5 else 'conseil', 'image-noire', f"Image noire de {b - a:.1f} s.",
                           "Vérifier la coupe ou le média à cet endroit.", 'FFmpeg blackdetect (pix_th 0,08)', debut + a, debut + b))
    for a, b in figes:
        fin = b if b is not None else duree
        out.append(constat('important', 'image-figee', f"Image figée pendant {fin - a:.1f} s.",
                           "Vérifier le média (image manquante, détourage trop court).", 'FFmpeg freezedetect (-60 dB, 1 s)', debut + a, debut + fin))
    # loudness
    if not info.get('has_audio'):
        out.append(constat('bloquant', 'son-absent', "La vidéo n'a pas de son.", "Refaire l'export.", 'ffprobe : aucune piste audio'))
    else:
        L = loudness(video)
        mes['loudness'] = L
        court = duree < 20 or debut > 0
        if L and L.get('I') is not None:
            ecart = L['I'] - LOUDNESS[0]
            if abs(ecart) > LOUDNESS[1]:
                g = 'conseil' if court else ('bloquant' if abs(ecart) > 4 else 'important')
                sens = 'trop fort' if ecart > 0 else 'trop faible'
                out.append(constat(g, 'loudness', f"Niveau sonore {sens} : {L['I']:.1f} LUFS (cible −14 ± 1).",
                                   "Refaire le mixage (normalisation −14 LUFS) avant de livrer." + (" Mesure indicative : extrait court." if court else ''),
                                   f"ebur128 : I {L['I']} LUFS, LRA {L['LRA']} LU, crête vraie {L['TP']} dBTP"))
            if L.get('TP') is not None and L['TP'] > LOUDNESS[2]:
                g = 'bloquant' if L['TP'] > 0 else ('conseil' if court else 'important')
                out.append(constat(g, 'crete', f"Crête vraie trop haute : {L['TP']:.1f} dBTP (max −1).",
                                   "Ajouter un limiteur à −1 dBTP au mixage.", f"ebur128 crête vraie {L['TP']} dBTP"))
    # images
    ref = None
    lisib, caches, masques, cartes = {}, [], [], {}
    det = []
    n_det = 0
    cible_det = set()
    audit_impossible = None
    if ctx.decoupe and profond:
        # images ou la personne detouree est vraiment affichee (pas pendant une plage de repli : prise d'origine)
        ts_cut = [t for t in np.arange(0, duree, pas) if (lambda s: bool(s and s.get('cutout')))(ctx.segment(debut + t)[0]) and ctx.repli(debut + t) < .5]
        if ts_cut:
            k = max(1, int(math.ceil(len(ts_cut) / max_detourage)))
            cible_det = {round(t, 3) for t in ts_cut[::k]}
    try:
        for vt, R in (_lire_images(video, pas, VW, VH) if images_ok else ()):
            rt = debut + vt
            if rt >= ctx.total:
                break
            if (VW, VH) != (W, H):
                R = cv2.resize(R, (W, H), interpolation=cv2.INTER_LINEAR)
            els = visibles(ctx, rt)
            # visage
            vb = ctx.visage(rt)
            # ecran partage du Comparatif : deux visages, le detecteur n'en rend qu'un (non controle a l'image)
            if vb and not ctx.comparaison(rt) and not any(e['genre'] in ('broll-plein', 'fin', 'intro') for e in els):
                small = cv2.resize(R, (360, int(360 * H / W)))
                f = analyze.detect_face(small)
                if f is None:
                    caches.append(rt)
                else:
                    fb = ((f['cx'] - f['w'] / 2) * W, (f['cy'] - f['h'] / 2) * H, (f['cx'] + f['w'] / 2) * W, (f['cy'] + f['h'] / 2) * H)
                    for e in (els if mise_en_page else ()):
                        if e['textes'] and not e['derriere'] and e['genre'] not in ('hud', 'decor', 'logo'):
                            fr = inter(fb, e['box']) / max(1, aire(fb))
                            if fr > .15:
                                masques.append((rt, fr, e, fb))
            # lisibilite mesuree a l'image
            Y = (.299 * R[..., 0] + .587 * R[..., 1] + .114 * R[..., 2]).astype(np.float32)
            for e in (els if mise_en_page else ()):
                if not e['textes'] or e['genre'] in ('decor',):
                    continue
                if rt < e['debut'] + .45 or rt > e['fin'] - .3:
                    continue  # animation d'entree ou de sortie : texte encore transparent
                x0, y0, x1, y1 = [int(v) for v in e['box']]
                x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
                if x1 - x0 < 8 or y1 - y0 < 6:
                    continue
                zone = Y[y0:y1, x0:x1]
                seuil, _ = cv2.threshold(zone.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                hi, lo = zone[zone > seuil], zone[zone <= seuil]
                if hi.size < 20 or lo.size < 20:
                    continue
                Lh, Ll = luminance((hi.mean(),) * 3), luminance((lo.mean(),) * 3)
                c = contraste(Lh, Ll)
                lisib.setdefault(e['id'], []).append((rt, c, e))
                if e['carte']:
                    m = int(max(12, .05 * W))
                    ring = np.concatenate([Y[y0:y1, max(0, x0 - m):x0].ravel(), Y[y0:y1, x1:min(W, x1 + m)].ravel(),
                                           Y[max(0, y0 - m):y0, x0:x1].ravel(), Y[y1:min(H, y1 + m), x0:x1].ravel()])
                    if ring.size > 50:
                        cartes.setdefault(e['id'], []).append((rt, contraste(luminance((float(np.median(zone)),) * 3), luminance((float(np.median(ring)),) * 3)), e))
            # detourage : alpha utilise vs reference RVM sur l'image de la prise
            if round(vt, 3) in cible_det and not audit_impossible:
                seg, fr = ctx.segment(rt)
                m = ctx.cutout(seg)
                if m and fr.get('f') and m.get('frames'):
                    idx = int(min((m.get('count') or 1) - 1, max(0, math.floor((fr['tSrc'] - m['start']) * (m.get('fps') or ctx.reel['fps'])))))
                    im = cv2.imread(str(ROOT / m['frames'] / f'{idx:05d}.webp'), cv2.IMREAD_UNCHANGED)
                    S = _image_source(ROOT / ctx.reel['sources'][seg['source']]['proxy'], fr['tSrc'])
                    P = None
                    if im is not None and im.ndim == 3 and im.shape[2] == 4 and S is not None:
                        try:
                            if ref is None:
                                ref = Reference()
                            P = ref.masque(S)
                        except Exception as e:  # modele absent, memoire de la carte graphique pleine... : on continue sans
                            audit_impossible = str(e)[:200]
                    if P is not None:
                        A = im[:, :, 3].astype(np.float32) / 255
                        ah, aw = A.shape
                        P = cv2.resize(P, (aw, ah), interpolation=cv2.INTER_AREA)
                        # personne a l'ecran : camera du studio comprise (studioView) ; video plus ancienne que le rendu :
                        # cadre de la prise sans camera (le studio n'avait pas de camera avant le 01/10/2026)
                        f = fr['f']
                        L, T, RW, RH = ctx.rect(rt) if not ancien else (f['left'], f['top'], f['width'], f['height'])
                        f = {'left': L, 'top': T, 'width': RW, 'height': RH}
                        sc = f['width'] / aw
                        d = _mesure_detourage(A, P, sc)
                        # visibilite des restes dans l'image rendue
                        vis = 0.0
                        if d['masque_restes'].any():
                            mr = cv2.resize(d['masque_restes'].astype(np.uint8), (int(round(f['width'])), int(round(f['height']))), interpolation=cv2.INTER_NEAREST)
                            ao = cv2.resize(A, (int(round(f['width'])), int(round(f['height']))))
                            canvas_m = np.zeros((H, W), np.uint8)
                            canvas_a = np.zeros((H, W), np.float32)
                            x0, y0 = int(round(f['left'])), int(round(f['top']))
                            sx, sy, cx, cy = max(0, -x0), max(0, -y0), max(0, x0), max(0, y0)
                            cw, ch = min(W - cx, mr.shape[1] - sx), min(H - cy, mr.shape[0] - sy)
                            canvas_m[cy:cy + ch, cx:cx + cw] = mr[sy:sy + ch, sx:sx + cw]
                            canvas_a[cy:cy + ch, cx:cx + cw] = ao[sy:sy + ch, sx:sx + cw]
                            anneau = (cv2.dilate(canvas_m, np.ones((31, 31), np.uint8)) > 0) & (canvas_a < .02)
                            if canvas_m.any() and anneau.sum() > 50:
                                # ecart moyen pixel par pixel entre les restes et le studio qui les entoure
                                vis = float(np.abs(Y[canvas_m > 0] - np.median(Y[anneau])).mean())
                            d['masque_rendu'] = canvas_m
                        d['visible'] = round(vis, 1)
                        det.append((rt, d, R.copy() if d['restes'] > .004 else None))
                        n_det += 1
    finally:
        if ref is not None:
            ref.close()
    if audit_impossible:
        out.append(constat('conseil', 'detourage-non-controle', "Le détourage n'a pas pu être contrôlé à l'image (modèle de référence indisponible).",
                           "Relancer le contrôle plus tard (carte graphique occupée ?) ; les autres vérifications sont faites.", audit_impossible))
    # constats images
    if caches:
        pl = plages(caches, pas)
        if sum(b - a for a, b in pl) >= 1.0:
            out.append(constat('important', 'visage-non-detecte', f"Visage non détecté à l'image pendant {sum(b - a for a, b in pl):.1f} s alors que la personne parle.",
                               "Vérifier qu'aucun élément ne masque le visage à ces moments.", f"MediaPipe (blaze_face) sur l'image rendue ; {plages_texte(pl, 3)}",
                               pl[0][0], pl[-1][1]))
    par_el = {}
    for rt, fr, e, fb in masques:
        par_el.setdefault(e['id'], []).append((rt, fr, e, fb))
    for eid, v in par_el.items():
        rt, fr, e, fb = max(v, key=lambda x: x[1])
        g = 'important' if fr < .35 else 'bloquant'
        dur = len(v) * pas
        if dur < 1.0:
            g = GRAVITES[min(2, GRAVITES.index(g) + 1)]
        if e.get('ponctuel'):  # mot geant plein ecran, bref : effet voulu
            g = 'conseil' if dur <= 1.5 else 'important'
        p = _preuve_image(preuves, f'visage-{_slug(eid)}', ctx, video, debut, rt, [(fb, (0, 255, 0)), (e['box'], (255, 60, 60))])
        out.append(constat(g, 'visage-couvert-image', f"Visage recouvert à l'image par {_nom(e)} ({fr:.0%} de la boîte du visage).",
                           "Déplacer l'élément hors du visage.", f"visage détecté {_bx(fb)} ; image : {p}", rt, zone=e['box'], element=e['id']))
    for eid, v in lisib.items():
        rt, c, e = min(v, key=lambda x: x[1])
        if c < 2.0 and not e['carte']:
            p = _preuve_image(preuves, f'lisibilite-{_slug(eid)}', ctx, video, debut, rt, [(e['box'], (255, 200, 0))], recadre=e['box'])
            out.append(constat('important', 'lisibilite-image', f"Peu lisible à l'image : {_nom(e)} (contraste mesuré {c:.1f}:1).",
                               "Renforcer le contour/l'ombre du texte ou changer sa couleur.", f"séparation texte/fond (Otsu) {c:.2f}:1 ; image : {p}", rt, zone=e['box'], element=e['id']))
    for eid, v in cartes.items():
        rt, c, e = min(v, key=lambda x: x[1])
        if c < 1.3:
            p = _preuve_image(preuves, f'carte-{_slug(eid)}', ctx, video, debut, rt, [(e['box'], (255, 200, 0))], recadre=e['box'], marge=80)
            out.append(constat('conseil', 'carte-terne-image', f"Carte terne à l'image : {_nom(e)} se distingue mal du fond (contraste {c:.2f}:1).",
                               "Éclaircir la carte ou ajouter un liseré lumineux.", f"médiane carte / pourtour ; image : {p}", rt, zone=e['box'], element=e['id']))
    if det:
        mes['detourage'] = [{'t': round(rt, 2), **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items() if not k.startswith('masque')}}
                            for rt, d, _ in det]
        mes['detourage_reference'] = ref.nom if ref else 'rvm'
        touches = [x for x in det if x[1]['restes'] >= .004 and x[1]['visible'] >= 8]
        if touches:
            pire = max(touches, key=lambda x: x[1]['restes'] * min(1.0, x[1]['visible'] / 40))  # le plus visible
            part = len(touches) / len(det)
            rt, d, R = pire
            p = _preuve_restes(preuves, R, d, rt)
            g = 'bloquant' if (d['restes'] >= .03 and part >= .2) else ('important' if d['restes'] >= .01 else 'conseil')
            out.append(constat(g, 'detourage-restes', f"Morceaux du décor d'origine (chaise, table, mur) restent collés à la personne détourée sur {part:.0%} des images contrôlées.",
                               "Actualiser le détourage avec le moteur RVM ; sinon garder la prise d'origine sur ces passages.",
                               f"pire image {hms(rt)} : restes = {d['restes']:.1%} de la surface de la personne ({d['blocs']} morceaux), écart visible {d['visible']:.0f}/255 ; "
                               f"référence RVM ; image : {p}", min(x[0] for x in touches), max(x[0] for x in touches)))
        voiles = [x for x in det if x[1]['voile'] >= .03]
        if voiles:
            rt, d, _ = max(voiles, key=lambda x: x[1]['voile'])
            out.append(constat('important', 'detourage-voile', f"Traînées grises semi-transparentes autour de la personne (mains, bras) sur {len(voiles)}/{len(det)} images.",
                               "Détourage à refaire (RVM) ; le masque actuel laisse passer le décor en transparence.",
                               f"pire {hms(rt)} : voile = {d['voile']:.1%} de la surface de la personne (alpha 0,06–0,6 hors personne)", rt))
        flous = [x for x in det if x[1]['rampe_px'] >= 8 and x[1]['rampe_px'] >= 2 * max(1, x[1]['rampe_ref_px'])]
        if flous and len(flous) >= len(det) / 3:
            ra = float(np.median([x[1]['rampe_px'] for x in flous]))
            rr = float(np.median([x[1]['rampe_ref_px'] for x in flous]))
            dd = float(np.median([x[1]['detail'] for x in flous]))
            out.append(constat('important', 'detourage-bords', f"Bords du détourage flous et pixelisés (effet escalier) : transition de {ra:.0f} px à l'écran contre {rr:.0f} px pour un bon masque.",
                               "Utiliser un masque pleine résolution (RVM) et un léger affinage des bords.",
                               f"{len(flous)}/{len(det)} images ; finesse du masque {dd:.2f} × la référence (1 = aussi détaillé ; < 0,5 = masque basse résolution agrandi)",
                               flous[0][0], flous[-1][0]))
    return out, mes


def _slug(s):
    return re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-')[:40]


def _preuve_image(preuves, nom, ctx, video, debut, rt, boites, recadre=None, marge=60):
    """Image de preuve : image rendue avec boites (vert = visage, rouge/jaune = element)."""
    if not preuves:
        return '(non enregistrée)'
    import cv2
    R = _image_source(video, rt - debut)
    if R is None:
        return '(image illisible)'
    if R.shape[:2] != (ctx.H, ctx.W):  # boites en px du reel
        R = cv2.resize(R, (ctx.W, ctx.H), interpolation=cv2.INTER_LINEAR)
    im = cv2.cvtColor(R, cv2.COLOR_RGB2BGR)
    for b, c in boites:
        cv2.rectangle(im, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), c[::-1], 4)
    if recadre:
        x0, y0, x1, y1 = recadre
        im = im[int(max(0, y0 - marge)):int(min(im.shape[0], y1 + marge)), int(max(0, x0 - marge)):int(min(im.shape[1], x1 + marge))]
    else:
        im = cv2.resize(im, (im.shape[1] // 2, im.shape[0] // 2))
    preuves.mkdir(parents=True, exist_ok=True)
    p = preuves / f'{nom}-{rt:05.1f}s.png'
    cv2.imwrite(str(p), im)
    return str(p)


def _preuves_json(constats, ctx, video, debut, duree, preuves):
    """Pour les constats de la passe JSON situes dans la video : image recadree de l'element (preuve visuelle)."""
    if not preuves:
        return
    faits = set()
    for c in constats:
        cle = (c['code'], c.get('element') or tuple(c.get('zone') or ()))
        if 'zone' not in c or c['temps'] is None or cle in faits or len(faits) >= 10:
            continue
        fin = c['fin'] if c.get('fin') is not None else c['temps']
        a, b = max(c['temps'], debut), min(fin, debut + duree - .05)
        choix = None
        if not c.get('element'):  # constat sans element (tiers vide...) : une image d'un de ses passages dans la video
            for p0, p1 in c.get('plages') or [[c['temps'], fin]]:
                x0, x1 = max(p0, debut), min(p1, debut + duree - .05)
                if x1 - x0 >= .2:
                    choix = (min(x1, x0 + .5), c['zone'])
                    break
            a = b + 1
        t = a
        while t <= b and choix is None:  # un instant ou l'element est vraiment a l'ecran, hors animation d'entree/sortie
            for e in visibles(ctx, t):
                if e['id'] == c.get('element') and e['debut'] + .45 <= t <= e['fin'] - .3:
                    choix = (t, e['box'])
                    break
            t += .25
        if choix is None:
            continue
        t, box = choix
        quoi = c.get('element') or ('haut' if box[1] < ctx.H / 3 else 'bas')
        p = _preuve_image(preuves, f"{c['code']}-{_slug(quoi)}", ctx, video, debut, t, [(box, (255, 200, 0))], recadre=box, marge=90)
        if p.startswith('('):
            continue
        c['preuve'] += f' ; image : {p}'
        faits.add(cle)


def _preuve_restes(preuves, R, d, rt):
    if not preuves or R is None or 'masque_rendu' not in d:
        return '(non enregistrée)'
    import cv2
    m = d['masque_rendu']
    ys, xs = np.nonzero(m)
    if not len(xs):
        return '(aucun reste)'
    x0, x1 = max(0, xs.min() - 80), min(R.shape[1], xs.max() + 80)
    y0, y1 = max(0, ys.min() - 80), min(R.shape[0], ys.max() + 80)
    a = cv2.cvtColor(R[y0:y1, x0:x1], cv2.COLOR_RGB2BGR)
    b = a.copy()
    rouge = np.zeros_like(b)
    rouge[..., 2] = 255
    mm = m[y0:y1, x0:x1] > 0
    b[mm] = (.45 * b[mm] + .55 * rouge[mm]).astype(np.uint8)
    im = np.hstack([a, np.full((a.shape[0], 12, 3), 255, np.uint8), b])
    preuves.mkdir(parents=True, exist_ok=True)
    p = preuves / f'detourage-restes-{rt:05.1f}s.png'
    cv2.imwrite(str(p), im)
    return str(p)


# ---------------------------------------------------------------------------------------------------------------
# Note, rapport, commande
# ---------------------------------------------------------------------------------------------------------------
def noter(constats):
    total, par = 0.0, {}
    for c in constats:
        k = (c['code'], c['gravite'])
        deja = par.get(k, 0.0)
        p = PENALITE[c['gravite']] * (1 if deja == 0 else .5)
        p = min(p, PLAFOND[c['gravite']] - deja)
        if p > 0:
            par[k] = deja + p
            total += p
    note = max(0.0, 10 - total)
    if any(c['gravite'] == 'bloquant' for c in constats):
        note = min(note, 4.9)
    return round(note, 1)


def verdict(note, constats):
    if any(c['gravite'] == 'bloquant' for c in constats):
        return 'Pas livrable en l’état'
    if note >= 8:
        # « Prêt » seulement sans point important : sinon livrable, mais a ameliorer (message honnete pour Revision)
        return 'Livrable, à améliorer' if any(c['gravite'] == 'important' for c in constats) else 'Prêt à livrer'
    return 'À corriger avant de livrer'


def controler(reel, video=None, debut=None, sortie=None, profond=True, pas_video=0.5):
    """Controle complet. reel = document du reel (dict, jamais modifie). video = export ou apercu (facultatif) ;
    debut = instant du reel ou commence la video (0 pour un export complet) ; profond = audit du detourage a
    l'image avec le masque RVM de reference (carte graphique ; False = sans cet audit)."""
    t0 = time.time()
    if video and not Path(video).is_file():
        raise FileNotFoundError(f'Vidéo à contrôler introuvable : {video}')
    tmp_root = ROOT / 'runtime/cache/tmp'
    tmp_root.mkdir(parents=True, exist_ok=True)
    travail = Path(tempfile.mkdtemp(prefix='controle-', dir=str(tmp_root)))
    try:
        tl = montage_calcule(reel, travail)
        ctx = Contexte(reel, tl)
        fonds = Fonds(ctx)
        constats, mesures = passe_json(ctx, fonds)
        if video:
            preuves = Path(sortie) / 'preuves' if sortie else None
            if preuves and preuves.is_dir():  # preuves d'un controle precedent : on ne garde que celles de ce controle
                for ancienne in preuves.glob('*.png'):
                    if PREUVE_NOM.match(ancienne.name):
                        ancienne.unlink()
            cv, mv = passe_video(ctx, Path(video), float(debut or 0), preuves, profond=profond, pas=pas_video)
            # une mesure a l'image remplace l'estimation JSON du meme element
            paires = {'carte-terne-image': 'carte-terne', 'lisibilite-image': 'contraste-faible', 'visage-couvert-image': 'visage-couvert'}
            mesure = {(paires[c['code']], tuple(c['zone'])) for c in cv if c['code'] in paires and 'zone' in c}
            constats = [c for c in constats if (c['code'], tuple(c.get('zone') or ())) not in mesure]
            if mv.get('video', {}).get('mise_en_page_controlee'):
                _preuves_json(constats, ctx, Path(video), float(debut or 0), mv.get('video', {}).get('duree', 0), preuves)
            constats += cv
            mesures.update(mv)
    finally:
        shutil.rmtree(travail, ignore_errors=True)
    constats.sort(key=lambda c: (GRAVITES.index(c['gravite']), c['temps'] if c['temps'] is not None else -1))
    note = noter(constats)
    # version 2 : champ facultatif « plages » des constats, verdict « Livrable, à améliorer », medias = sources utilisees
    return {'version': VERSION_RAPPORT, 'reel': {'projet': reel.get('project'), 'id': reel.get('id'), 'titre': reel.get('title'),
                                   'style': reel.get('template'), 'format': f"{reel['width']}x{reel['height']}", 'duree': round(tl['total'], 2)},
            'video': str(video) if video else None, 'note': note, 'verdict': verdict(note, constats),
            'compte': {g: sum(1 for c in constats if c['gravite'] == g) for g in GRAVITES},
            'constats': constats, 'mesures': mesures, 'duree_controle_s': round(time.time() - t0, 1)}


def resume(r, n=20):
    """Resume compact a ranger dans le reel (champ « controle ») pour l'ecran Revision : note, verdict, constats."""
    garde = ('gravite', 'code', 'temps', 'fin', 'message', 'suggestion', 'zone', 'element', 'plages')
    # format : les boites « zone » sont en px de CE format (une declinaison 16:9 n'a pas les memes) ; total : nombre
    # de constats du rapport complet (le resume n'en garde que n, les plus graves d'abord)
    return {'version': r.get('version', VERSION_RAPPORT), 'date': time.strftime('%Y-%m-%d %H:%M'), 'note': r['note'], 'verdict': r['verdict'],
            'compte': r['compte'], 'video': r.get('video'), 'format': (r.get('reel') or {}).get('format'), 'total': len(r['constats']),
            'constats': [{k: c[k] for k in garde if k in c} for c in r['constats'][:n]]}


def dossier_rapport(projet, rid, sous='montage'):
    """Dossier des rapports d'un reel, meme regle que app/server.mjs (controleDir) : runtime/cache/controle/<projet>-<reel>/<sous>
    (sous = « montage » pour la passe JSON, « export-9x16 »… pour une video livree)."""
    return ROOT / 'runtime/cache/controle' / f'{projet}-{rid}' / sous


def ecrire_rapport(r, sortie):
    """controle.json (complet) + controle.txt (lisible) dans sortie."""
    sortie = Path(sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / 'controle.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    (sortie / 'controle.txt').write_text(texte_rapport(r), encoding='utf-8')


def texte_rapport(r):
    L = [f"Contrôle qualité — {r['reel'].get('titre') or r['reel'].get('id')} ({r['reel'].get('style')}, {r['reel']['format']}, {r['reel']['duree']:.1f} s)",
         f"Note : {str(r['note']).replace('.', ',')}/10 — {r['verdict']}",
         f"{r['compte']['bloquant']} bloquant(s), {r['compte']['important']} important(s), {r['compte']['conseil']} conseil(s)"
         + (f" ; vidéo contrôlée : {r['video']}" if r.get('video') else ' ; contrôle sans rendu (JSON seul)'), '']
    for c in r['constats']:
        quand = ''
        if c['temps'] is not None:
            quand = hms(c['temps']) + (f"–{hms(c['fin'])}" if c.get('fin') is not None and c['fin'] - c['temps'] > .15 else '')
        L.append(f"[{c['gravite'].upper()}] {quand + '  ' if quand else ''}{c['message']}")
        L.append(f"    → {c['suggestion']}")
        L.append(f"    preuve : {c['preuve']}")
    if not r['constats']:
        L.append('Aucun problème détecté.')
    return '\n'.join(L)


def charger(cible, reel_id=None):
    """Reel depuis un fichier .json (reel ou job d'export {reel, out, frameRange}) ou un dossier projet + id."""
    p = Path(cible)
    if p.is_dir():
        if not reel_id:
            raise SystemExit('Préciser --reel <id> avec un dossier de projet.')
        p = p / 'reels' / f'{reel_id}.json'
    if not p.is_file():
        raise SystemExit(f'Reel introuvable : {p}')
    doc = json.loads(p.read_text(encoding='utf-8'))
    job = None
    if 'clips' not in doc and isinstance(doc.get('reel'), dict):
        job = {k: v for k, v in doc.items() if k != 'reel'}
        doc = doc['reel']
    return doc, p, job


def _debut_auto(video, reel, job):
    """Instant de depart d'un apercu : job.json voisin (frameRange) sinon 0."""
    cands = [job] if job else []
    j = Path(video).parent / 'job.json'
    if j.exists():
        try:
            cands.append(json.loads(j.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            pass
    for c in cands:
        if c and c.get('frameRange') and (not c.get('out') or Path(c['out']).resolve() == Path(video).resolve()):
            return c['frameRange'][0] / (reel.get('fps') or 30)
    return 0.0


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m editeur.controle', description='Contrôle qualité automatique d’un reel.')
    ap.add_argument('cible', help='reel.json (ou job.json) ou dossier du projet')
    ap.add_argument('--reel', help='id du reel (avec un dossier de projet)')
    ap.add_argument('--video', help='vidéo exportée ou aperçu court à contrôler aussi')
    ap.add_argument('--debut', type=float, default=None, help="instant du reel où commence la vidéo (s) ; auto avec job.json")
    ap.add_argument('--pas', type=float, default=0.5, help='écart entre deux images contrôlées (s)')
    ap.add_argument('--sortie', help='dossier du rapport (défaut : runtime/cache/controle/<projet>-<reel>)')
    ap.add_argument('--json', action='store_true', help='écrire le rapport JSON sur la sortie standard')
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    reel, chemin, job = charger(a.cible, a.reel)
    if a.video and not Path(a.video).is_file():
        raise SystemExit(f'Vidéo à contrôler introuvable : {a.video}')
    sortie = Path(a.sortie) if a.sortie else ROOT / 'runtime/cache/controle' / _slug(f"{reel.get('project')}-{reel.get('id')}")
    sortie.mkdir(parents=True, exist_ok=True)
    debut = a.debut if a.debut is not None else (_debut_auto(a.video, reel, job) if a.video else 0.0)
    r = controler(reel, video=a.video, debut=debut, sortie=sortie, pas_video=a.pas)
    r['source'] = str(chemin)
    ecrire_rapport(r, sortie)
    txt = texte_rapport(r)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        print(txt)
        print(f"\nRapport : {sortie / 'controle.json'}")
    return r


if __name__ == '__main__':
    main()
