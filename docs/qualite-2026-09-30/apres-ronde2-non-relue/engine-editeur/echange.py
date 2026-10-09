"""Echange avec DaVinci Resolve / Premiere / Final Cut : le montage d'un reel en OTIO, XML (FCP7) et FCPXML,
avec pistes separees (image, voix avec J/L-cuts, musique, bruitages), marqueurs de parties et sous-titres SRT.
Le calcul des plans vient de remotion/segments.mjs (le meme que l'apercu et l'export)."""
import json
import subprocess
from pathlib import Path

import opentimelineio as otio

from .media import ROOT


def _segments(reel_file):
    out = subprocess.run(['node', str(ROOT / 'remotion/segments.mjs'), str(reel_file)], capture_output=True,
                         text=True, encoding='utf-8', check=True).stdout
    return json.loads(out)


def _ref(path, duration, rate):
    p = Path(path) if Path(path).is_absolute() else ROOT / path
    return otio.schema.ExternalReference(target_url=p.resolve().as_uri(),
                                         available_range=otio.opentime.TimeRange(otio.opentime.RationalTime(0, rate),
                                                                                 otio.opentime.RationalTime(round(duration * rate), rate)))


def _rt(seconds, rate):
    return otio.opentime.RationalTime(round(seconds * rate), rate)


def _seg_clip(name, path, dur_media, s, rate):
    """Plan d'un segment : duree = duree dans le montage ; un changement de vitesse devient un effet LinearTimeWarp."""
    speed = s.get('speed') or 1
    clip = otio.schema.Clip(name=name, media_reference=_ref(path, dur_media, rate),
                            source_range=otio.opentime.TimeRange(_rt(s['src_in'], rate), _rt((s['src_out'] - s['src_in']) / speed, rate)))
    if speed != 1:
        clip.effects.append(otio.schema.LinearTimeWarp(name=f'vitesse x{speed}', time_scalar=speed))
    return clip


def _place(track, items, rate):
    """Place des (debut, duree, clip) sur une piste en comblant les vides."""
    t = 0.0
    for start, dur, clip in sorted(items, key=lambda x: x[0]):
        if start - t > 1 / rate:
            track.append(otio.schema.Gap(source_range=otio.opentime.TimeRange(duration=_rt(start - t, rate))))
        track.append(clip)
        t = start + dur


def export_reel(project_dir, variant=None):
    project_dir = Path(project_dir)
    reel_file = project_dir / 'reels' / f"{variant or 'script'}.json"
    reel = json.loads(reel_file.read_text(encoding='utf-8'))
    seg = _segments(reel_file)
    rate = reel['fps']
    src = reel['sources']
    tl = otio.schema.Timeline(name=reel['title'], global_start_time=_rt(0, rate))

    video = otio.schema.Track(name='V1 Image', kind=otio.schema.TrackKind.Video)
    for s in seg['video']:
        video.append(_seg_clip(f"{s['clip']} {src[s['source']]['name']}", src[s['source']]['proxy'], src[s['source']]['duration'], s, rate))
    blocks = {b: f'{i + 1}' for i, b in enumerate(dict.fromkeys(c['block'] for c in reel['clips']))}
    last_block = None
    for s in seg['video']:
        block = next(c['block'] for c in reel['clips'] if c['id'] == s['clip'])
        if block != last_block:
            video.markers.append(otio.schema.Marker(name=f'Partie {blocks[block]}', marked_range=otio.opentime.TimeRange(_rt(s['out_start'], rate), _rt(0, rate))))
            last_block = block

    broll = reel.get('broll') or []
    v2 = None
    if broll:
        # plans de coupe au-dessus du montage (piste V2), sans son
        v2 = otio.schema.Track(name='V2 Plans de coupe', kind=otio.schema.TrackKind.Video)
        _place(v2, [(b['at'], b['duration'], otio.schema.Clip(
            name=f"plan de coupe {src[b['source']]['name']}", media_reference=_ref(src[b['source']]['proxy'], src[b['source']]['duration'], rate),
            source_range=otio.opentime.TimeRange(_rt(b['in'], rate), _rt(b['duration'], rate)))) for b in broll if b['source'] in src], rate)

    voice = otio.schema.Track(name='A1 Voix', kind=otio.schema.TrackKind.Audio)
    _place(voice, [(s['out_start'], (s['src_out'] - s['src_in']) / (s.get('speed') or 1),
                    _seg_clip(f"voix {s['clip']}", src[s['source']]['path'], src[s['source']]['duration'], s, rate))
                   for s in seg['audio']], rate)
    tracks = [video] + ([v2] if v2 else []) + [voice]

    music = reel.get('music') or {}
    if music.get('enabled') and music.get('file'):
        mt = otio.schema.Track(name='A2 Musique', kind=otio.schema.TrackKind.Audio)
        mfile = ROOT / 'assets' / music['file']
        mt.append(otio.schema.Clip(name=Path(music['file']).stem, media_reference=_ref(mfile, seg['duration'], rate),
                                   source_range=otio.opentime.TimeRange(_rt(0, rate), _rt(seg['duration'], rate))))
        tracks.append(mt)

    if seg['events']:
        lanes = []  # plusieurs pistes si des bruitages se chevauchent
        for e in seg['events']:
            f = ROOT / 'assets' / 'sfx' / 'editeur' / f"{e['name']}.wav"
            length = max(1 / rate, min(1.5, seg['duration'] - e['t']))  # jamais au-dela de la fin du montage
            clip = otio.schema.Clip(name=e['name'], media_reference=_ref(f, 3, rate),
                                    source_range=otio.opentime.TimeRange(_rt(0, rate), _rt(length, rate)))
            lane = next((l for l in lanes if l[-1][0] + l[-1][1] <= e['t']), None)
            if lane is None:
                lanes.append(lane := [])
            lane.append((e['t'], length, clip))
        for i, lane in enumerate(lanes):
            tr = otio.schema.Track(name=f'A{3 + i} Bruitages', kind=otio.schema.TrackKind.Audio)
            _place(tr, lane, rate)
            tracks.append(tr)
    tl.tracks.extend(tracks)

    out = Path(reel.get('delivery') or ROOT / 'livraisons') / f"{reel['title']} - pour Resolve"
    out.mkdir(parents=True, exist_ok=True)
    written, errors = [], []
    for ext, adapter in (('otio', 'otio_json'), ('xml', 'fcp_xml'), ('fcpxml', 'fcpx_xml')):
        target = out / f'montage.{ext}'
        try:
            otio.adapters.write_to_file(tl, str(target), adapter_name=adapter)
            written.append(target.name)
        except Exception as e:
            errors.append(f'{ext} : {e}')
    (out / 'sous-titres.srt').write_text(seg['srt'], encoding='utf-8')
    (out / 'LISEZ-MOI.txt').write_text(
        f"Montage « {reel['title']} » pour la finition dans DaVinci Resolve (ou Premiere / Final Cut).\n\n"
        "DaVinci Resolve : Fichier > Importer > Timeline > montage.otio (ou montage.xml).\n"
        "Premiere Pro : Fichier > Importer > montage.xml.   Final Cut Pro : montage.fcpxml.\n"
        "Sous-titres : importer sous-titres.srt sur une piste de sous-titres.\n\n"
        "Pistes : V1 image (medias optimises redresses, cadre d'origine), V2 plans de coupe, A1 voix (rushs d'origine,\n"
        "J/L-cuts compris), A2 musique, A3+ bruitages. Marqueurs = debut de chaque partie du script.\n"
        "Les sous-titres animes, zooms, recadrage, graphismes, charte client et changements de vitesse de l'editeur\n"
        "ne sont pas transferes : ils restent dans l'export FINAL.\n",
        encoding='utf-8')
    return out, written, errors
