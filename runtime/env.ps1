# Garde tous les outils, caches et modeles dans D:\Tools\editeur_sami
$R = Split-Path -Parent $PSScriptRoot
$env:EDITEUR_ROOT = $R
$env:UV_CACHE_DIR = "$R\runtime\cache\uv"
$env:UV_PYTHON_INSTALL_DIR = "$R\runtime\python"
$env:UV_PROJECT_ENVIRONMENT = "$R\runtime\venv"
$env:UV_LINK_MODE = "copy"
$env:UV_PYTHON_BIN_DIR = "$R\runtime\bin"
$env:UV_TOOL_DIR = "$R\runtime\uv-tools"
$env:UV_TOOL_BIN_DIR = "$R\runtime\bin"
$env:UV_NO_MODIFY_PATH = "1"
$env:UV_PYTHON_PREFERENCE = "only-managed"
$env:PIP_CACHE_DIR = "$R\runtime\cache\pip"
$env:npm_config_cache = "$R\runtime\cache\npm"
$env:HF_HOME = "$R\models\huggingface"
$env:HF_HUB_OFFLINE = "1"   # modeles deja telecharges : aucune connexion (installer.ps1 le remet a 0)
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
$env:TORCH_HOME = "$R\models\torch"
$env:ACESTEP_CHECKPOINTS_DIR = "$R\models\acestep"
$env:XDG_CACHE_HOME = "$R\runtime\cache"
$env:TEMP = "$R\runtime\cache\tmp"; $env:TMP = $env:TEMP
$env:PATH = "$R\runtime\bin;$R\runtime\venv\Scripts;$R\tools\ffmpeg\bin;$env:PATH"
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
