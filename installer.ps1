# Installe ou repare l'editeur. Tout reste dans ce dossier ; rien n'est ecrit sur C:.
# Usage : powershell -ExecutionPolicy Bypass -File installer.ps1 [-SansMusique] [-SansIA]
# Ne retelecharge que ce qui manque. Prerequis : Node.js, pilote NVIDIA recent, FFmpeg dans tools\ffmpeg.
param([switch]$SansMusique, [switch]$SansIA)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\runtime\env.ps1"
$R = $env:EDITEUR_ROOT
$env:HF_HUB_OFFLINE = '0'   # l'installation doit pouvoir telecharger les modeles
function Get-File($url, $dest) {
    if (Test-Path $dest) { return }
    New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
    Write-Host "Telechargement : $(Split-Path $dest -Leaf)"
    Invoke-WebRequest $url -OutFile "$dest.part"; Move-Item "$dest.part" $dest
}
function Get-Zip($url, $destDir) {
    $zip = "$env:TEMP\$(Split-Path $destDir -Leaf).zip"
    Invoke-WebRequest $url -OutFile $zip; Expand-Archive $zip $destDir -Force; Remove-Item $zip
}

# 1. Python 3.12 local + moteur (Whisper, MediaPipe, CLIP, librosa, OpenTimelineIO...)
if (-not (Test-Path "$R\runtime\bin\uv.exe")) { Get-Zip 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' "$R\runtime\bin" }
if (-not (Test-Path "$R\tools\ffmpeg\bin\ffmpeg.exe")) { throw 'FFmpeg absent : copier le build complet dans tools\ffmpeg (bin\ffmpeg.exe).' }
uv python install 3.12
Push-Location "$R\engine"; uv sync; Pop-Location

# 2. Petits modeles
$mp = 'https://storage.googleapis.com/mediapipe-models'
Get-File "$mp/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite" "$R\models\mediapipe\blaze_face_short_range.tflite"
Get-File "$mp/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite" "$R\models\mediapipe\selfie_segmenter.tflite"
Get-File "$mp/face_landmarker/face_landmarker/float16/latest/face_landmarker.task" "$R\models\mediapipe\face_landmarker.task"
Get-File 'https://raw.githubusercontent.com/GregorR/rnnoise-models/master/somnolent-hogwash-2018-09-01/sh.rnnn' "$R\models\rnnoise\sh.rnnn"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
python -c "from faster_whisper import download_model; download_model('large-v3-turbo')"
python -c "import open_clip; open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')"

# 3. Polices libres (OFL / Apache) et bruitages
$gf = 'https://github.com/google/fonts/raw/main'
$fonts = @{ 'Montserrat.ttf'='ofl/montserrat/Montserrat%5Bwght%5D.ttf'; 'Anton.ttf'='ofl/anton/Anton-Regular.ttf'; 'BebasNeue.ttf'='ofl/bebasneue/BebasNeue-Regular.ttf';
    'Poppins-ExtraBold.ttf'='ofl/poppins/Poppins-ExtraBold.ttf'; 'Inter.ttf'='ofl/inter/Inter%5Bopsz,wght%5D.ttf'; 'Oswald.ttf'='ofl/oswald/Oswald%5Bwght%5D.ttf';
    'ArchivoBlack.ttf'='ofl/archivoblack/ArchivoBlack-Regular.ttf'; 'Bangers.ttf'='ofl/bangers/Bangers-Regular.ttf'; 'LuckiestGuy.ttf'='apache/luckiestguy/LuckiestGuy-Regular.ttf';
    'Rubik.ttf'='ofl/rubik/Rubik%5Bwght%5D.ttf'; 'BarlowCondensed-ExtraBold.ttf'='ofl/barlowcondensed/BarlowCondensed-ExtraBold.ttf';
    'PlayfairDisplay.ttf'='ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf'; 'DMSerifDisplay.ttf'='ofl/dmserifdisplay/DMSerifDisplay-Regular.ttf';
    'PermanentMarker.ttf'='apache/permanentmarker/PermanentMarker-Regular.ttf'; 'Kanit-ExtraBold.ttf'='ofl/kanit/Kanit-ExtraBold.ttf';
    'LeagueSpartan.ttf'='ofl/leaguespartan/LeagueSpartan%5Bwght%5D.ttf'; 'NotoColorEmoji.ttf'='ofl/notocoloremoji/NotoColorEmoji-Regular.ttf' }
foreach ($f in $fonts.GetEnumerator()) { Get-File "$gf/$($f.Value)" "$R\assets\fonts\$($f.Key)" }
if (-not (Test-Path "$R\assets\sfx\editeur\whoosh-court.wav")) { Push-Location "$R\engine"; python -m editeur.sfxgen; Pop-Location }
$kenney = @{ 'impact-sounds'='87b4ddecda-1677589768'; 'interface-sounds'='fa43c1dd4d-1677589452'; 'ui-audio'='490d233f68-1677590494';
    'digital-audio'='216eac4753-1677590265'; 'sci-fi-sounds'='6b296f9ecf-1677589334'; 'music-jingles'='f37e530b9e-1677590399' }
foreach ($k in $kenney.GetEnumerator()) {
    $dir = "$R\assets\sfx\kenney\$($k.Key)"
    if (Test-Path $dir) { continue }
    Get-Zip "https://kenney.nl/media/pages/assets/$($k.Key)/$($k.Value)/kenney_$($k.Key).zip" "$env:TEMP\kenney-$($k.Key)"
    New-Item -ItemType Directory -Force $dir | Out-Null
    Get-ChildItem "$env:TEMP\kenney-$($k.Key)" -Recurse -Include *.ogg,*.wav,*.mp3,License* | Copy-Item -Destination $dir
    Remove-Item -Recurse -Force "$env:TEMP\kenney-$($k.Key)"
}

# 4. IA de texte locale : llama.cpp (CUDA) + Qwen3.5-9B (Apache 2.0)
if (-not $SansIA) {
    if (-not (Test-Path "$R\tools\llama\llama-server.exe")) {
        $rel = Invoke-RestMethod 'https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=5' | Where-Object { $_.assets.Count } | Select-Object -First 1
        foreach ($pat in 'llama-*-bin-win-cuda-13.*-x64.zip', 'cudart-llama-bin-win-cuda-13.*-x64.zip') {
            $a = $rel.assets | Where-Object { $_.name -like $pat } | Select-Object -First 1
            Get-Zip $a.browser_download_url "$R\tools\llama"
        }
    }
    $hf = 'https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main'
    Get-File "$hf/Qwen3.5-9B-Q4_K_M.gguf" "$R\models\llm\Qwen3.5-9B-Q4_K_M.gguf"
    Get-File "$hf/mmproj-F16.gguf" "$R\models\llm\Qwen3.5-9B-mmproj-F16.gguf"
}

# 5. Musique originale locale : ACE-Step 1.5 (licence MIT), environnement separe
if (-not $SansMusique) {
    if (-not (Test-Path "$R\tools\acestep\pyproject.toml")) {
        Get-Zip 'https://codeload.github.com/ace-step/ACE-Step-1.5/zip/refs/heads/main' "$env:TEMP\acestep-src"
        Move-Item "$env:TEMP\acestep-src\ACE-Step-1.5-main" "$R\tools\acestep"; Remove-Item -Recurse -Force "$env:TEMP\acestep-src"
    }
    $env:UV_PROJECT_ENVIRONMENT = "$R\runtime\venvs\acestep"
    Push-Location "$R\tools\acestep"; uv sync; Pop-Location
    $env:UV_PROJECT_ENVIRONMENT = "$R\runtime\venv"
    if (-not (Test-Path "$R\models\acestep\acestep-v15-turbo")) {
        & "$R\runtime\venvs\acestep\Scripts\python.exe" -m acestep.model_downloader --model main --dir "$R\models\acestep"
    }
    if (-not (Test-Path "$R\assets\music\energique.ogg")) {
        Write-Host 'Composition de la bibliotheque musicale (environ 5 min)...'
        $tasks = Get-Content "$R\styles\musiques.json" -Raw -Encoding UTF8 | ConvertFrom-Json | ForEach-Object -Begin { $i = 0 } -Process {
            $i++; @{ caption = $_.caption; bpm = $_.bpm; duration = 92; seed = 100 + $i; out = "$env:TEMP\music\$($_.id).wav" } }
        $tasks | ConvertTo-Json | Set-Content "$env:TEMP\music.json" -Encoding UTF8
        & "$R\runtime\venvs\acestep\Scripts\python.exe" "$R\engine\music_gen.py" "$env:TEMP\music.json"
        Get-ChildItem "$env:TEMP\music\*.wav" | ForEach-Object {
            ffmpeg -v error -y -i $_.FullName -af 'silenceremove=stop_periods=1:stop_duration=1:stop_threshold=-55dB,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000' -c:a libvorbis -q:a 6 "$R\assets\music\$($_.BaseName).ogg"
        }
        Remove-Item -Recurse -Force "$env:TEMP\music", "$env:TEMP\music.json"
    }
}

# 6. Graphisme video (Remotion) et interface
Push-Location "$R\remotion"; npm ci --no-fund --no-audit; npx remotion browser ensure; Pop-Location
node "$R\app\build.mjs"
uv cache clean
Write-Host 'Installation terminee. Lancer .\editeur.ps1' -ForegroundColor Green
