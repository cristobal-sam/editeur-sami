"""Generation de musique instrumentale originale avec ACE-Step 1.5 (licence MIT, usage commercial autorise).
S'execute avec l'environnement runtime/venvs/acestep :
  python music_gen.py <taches.json>
taches.json = [{"caption": "...", "duration": 60, "bpm": 110, "out": "chemin.wav", "seed": 42}, ...]
Une ligne JSON de progression par morceau sur stdout."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('ACESTEP_CHECKPOINTS_DIR', str(ROOT / 'models' / 'acestep'))
sys.path.insert(0, str(ROOT / 'tools' / 'acestep'))


def say(**kw):
    print(json.dumps(kw, ensure_ascii=False), flush=True)


def main(task_file):
    tasks = json.loads(Path(task_file).read_text(encoding='utf-8'))
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    say(stage='Chargement du modele de musique')
    dit = AceStepHandler()
    dit.initialize_service(project_root=str(ROOT / 'tools' / 'acestep'), config_path='acestep-v15-turbo', device='cuda')
    for i, t in enumerate(tasks, 1):
        say(stage=f'Musique {i}/{len(tasks)}', caption=t['caption'])
        params = GenerationParams(caption=t['caption'], lyrics='[Instrumental]', instrumental=True,
                                  duration=float(t.get('duration', 60)), bpm=t.get('bpm'),
                                  inference_steps=int(t.get('steps', 8)), seed=int(t.get('seed', -1)),
                                  thinking=False, fade_out_duration=2.0)
        with tempfile.TemporaryDirectory(dir=os.environ.get('TEMP')) as tmp:
            result = generate_music(dit, None, params, GenerationConfig(batch_size=1, audio_format='wav'), save_dir=tmp)
            if not result.success or not result.audios:
                say(error=str(result.error), out=t['out'])
                continue
            out = Path(t['out'])
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(result.audios[0]['path'], out)
            say(done=str(out))


if __name__ == '__main__':
    main(sys.argv[1])
