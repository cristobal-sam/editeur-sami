# Montage automatique : analyse les prises, garde les meilleures selon le script, monte les videos.
# Exemples :
#   .\derusher.ps1 -Rushs "media\rushs\tournage" -Script "media\rushs\tournage\script.docx"
#   .\derusher.ps1 -Rushs "media\rushs\tournage" -Script "...\script.docx" -Style reel-impact
#       -> monte UN seul reel : la premiere video, version script
#   ... -Style reel-impact -Video video1 -Version v1     (hook alternatif 1 de la video 1)
#   .\derusher.ps1 -Styles        (liste des styles de montage)
param(
    [string]$Rushs,
    [string]$Script,
    [string]$Style,
    [string]$Video,
    [string]$Version = 'script',
    [switch]$SansRendu,
    [switch]$Styles,
    [string]$Langue,    # fr (defaut), en... ou auto
    [string]$Format     # 9:16 (defaut), 16:9, 4:5, 1:1
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\runtime\env.ps1"
$env:PYTHONIOENCODING = 'utf-8'
# Chemins resolus depuis le dossier ou la commande est lancee, avant d'entrer dans engine\
if (-not $Styles) {
    if (-not $Rushs) { throw 'Indiquer -Rushs (et -Script si un script existe), ou -Styles pour la liste des styles.' }
    $Rushs = (Resolve-Path $Rushs).Path
    if ($Script) { $Script = (Resolve-Path $Script).Path }
}
Push-Location "$PSScriptRoot\engine"
try {
    if ($Styles) { python -m editeur styles; return }
    $cmd = @('-m', 'editeur', 'derush', $Rushs)
    if ($Script) { $cmd += $Script }   # sans script : montage a partir de la transcription
    if ($Style) { $cmd += @('--style', $Style, '--version', $Version) }
    if ($Video) { $cmd += @('--video', $Video) }
    if ($SansRendu) { $cmd += '--sans-rendu' }
    if ($Langue) { $cmd += @('--langue', $Langue) }
    if ($Format) { $cmd += @('--format', $Format) }
    python @cmd 2>&1 | Where-Object { $_ -notmatch 'WARNING|^W0000|^INFO:|feedback' }
} finally { Pop-Location }
