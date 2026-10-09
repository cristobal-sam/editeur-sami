# Equivalent bash de env.ps1
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -W 2>/dev/null || pwd)"
export EDITEUR_ROOT="$R" UV_CACHE_DIR="$R/runtime/cache/uv" UV_PYTHON_INSTALL_DIR="$R/runtime/python" UV_PROJECT_ENVIRONMENT="$R/runtime/venv" UV_LINK_MODE=copy UV_PYTHON_BIN_DIR="$R/runtime/bin" UV_TOOL_DIR="$R/runtime/uv-tools" UV_TOOL_BIN_DIR="$R/runtime/bin" UV_NO_MODIFY_PATH=1 UV_PYTHON_PREFERENCE=only-managed
export PIP_CACHE_DIR="$R/runtime/cache/pip" npm_config_cache="$R/runtime/cache/npm" HF_HOME="$R/models/huggingface" HF_HUB_OFFLINE=1 HF_HUB_DISABLE_SYMLINKS_WARNING=1 TORCH_HOME="$R/models/torch" ACESTEP_CHECKPOINTS_DIR="$R/models/acestep" XDG_CACHE_HOME="$R/runtime/cache"
export TEMP="$R/runtime/cache/tmp" TMP="$R/runtime/cache/tmp"
export PATH="$(cygpath -u "$R")/runtime/bin:$(cygpath -u "$R")/runtime/venv/Scripts:$(cygpath -u "$R")/tools/ffmpeg/bin:$PATH"
mkdir -p "$TEMP"
