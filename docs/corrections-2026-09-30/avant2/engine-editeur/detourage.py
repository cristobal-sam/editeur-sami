"""Détourage local MediaPipe, mis en cache pour aperçu ET export ; aucune installation."""
import hashlib
import json
import subprocess
from pathlib import Path

from .media import ROOT, FFMPEG


def preview_frames(doc, fps):
    """Images alpha identiques dans le lecteur et le rendu, sans décodage VP9 matériel."""
    out=ROOT/doc['file']
    folder=out.with_suffix('')
    marker=folder/'complete.json'
    if not marker.exists():
        folder.mkdir(parents=True,exist_ok=True)
        subprocess.run([str(FFMPEG),'-v','error','-y','-c:v','libvpx-vp9','-i',str(out),
                        '-c:v','libwebp','-quality','90','-start_number','0',str(folder/'%05d.webp')],check=True)
        count=len(list(folder.glob('*.webp')))
        if not count:raise RuntimeError('Images détourées absentes.')
        marker.write_text(json.dumps({'count':count}),encoding='utf-8')
    return {**doc,'frames':folder.relative_to(ROOT).as_posix(),'fps':fps,
            'count':json.loads(marker.read_text(encoding='utf-8'))['count']}


def cutout(path, start, end, fps=30):
    import cv2
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import ImageSegmenter, ImageSegmenterOptions
    path = Path(path)
    key = hashlib.sha1(json.dumps([str(path), path.stat().st_mtime_ns, start, end, fps, 'v3-alpha-frames']).encode()).hexdigest()[:20]
    out = ROOT / 'assets' / 'detourage' / f'{key}.webm'
    meta = out.with_suffix('.json')
    if out.exists() and meta.exists():
        return preview_frames(json.loads(meta.read_text(encoding='utf-8')),fps)
    out.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(path))
    sw, sh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    width = min(720, sw) // 2 * 2
    height = round(sh * width / sw / 2) * 2
    options = ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=str(ROOT / 'models/mediapipe/selfie_segmenter.tflite')),
                                   output_category_mask=False, output_confidence_masks=True)
    reader = subprocess.Popen([str(FFMPEG), '-v', 'error', '-ss', str(start), '-t', str(end-start), '-i', str(path),
                               '-vf', f'scale={width}:{height},fps={fps}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    temp = out.with_name(out.stem + '.part.webm')
    writer = subprocess.Popen([str(FFMPEG), '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{width}x{height}',
                               '-r', str(fps), '-i', '-', '-an', '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-auto-alt-ref', '0',
                               '-b:v', '0', '-crf', '30', '-deadline', 'realtime', '-cpu-used', '6', str(temp)], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        count = 0
        with ImageSegmenter.create_from_options(options) as model:
            while True:
                raw = reader.stdout.read(width*height*3)
                if len(raw) != width*height*3:
                    break
                rgb = np.frombuffer(raw, np.uint8).reshape(height, width, 3)
                result = model.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb.copy()))
                mask = result.confidence_masks[0].numpy_view().copy()
                mask = cv2.GaussianBlur(cv2.resize(mask, (width, height)), (5, 5), 0)
                alpha = np.clip((mask - .15) / .7, 0, 1)
                writer.stdin.write(np.dstack([rgb, (alpha*255).astype(np.uint8)]).tobytes())
                count += 1
        writer.stdin.close()
        if reader.wait() or writer.wait() or not count:
            raise RuntimeError('Le détourage local n’a pas produit de vidéo.')
        temp.replace(out)
        doc = {'file': out.relative_to(ROOT).as_posix(), 'start': start, 'end': end, 'width': width, 'height': height}
        meta.write_text(json.dumps(doc), encoding='utf-8')
        return preview_frames(doc,fps)
    finally:
        if reader.poll() is None:
            reader.terminate()
        if writer.poll() is None:
            writer.terminate()


def prepare(reel):
    if (reel.get('design') or {}).get('mode') not in ('editorial', 'collage'):
        return
    from . import montage
    reel['cutouts'] = {}
    for c in reel['clips']:
        if c.get('angle') and c['angle'] != c['source']:
            raise ValueError('Détourage : utilise la prise principale ou prépare cet angle séparément.')
        path = montage.proxy_path(reel['sources'][c['source']])
        reel['cutouts'][c['id']] = {**cutout(path, c['in'], c['out'], reel['fps']),
                                   'source': c['source'], 'proxy': reel['sources'][c['source']]['proxy']}
