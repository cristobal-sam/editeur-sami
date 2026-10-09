# Lance l'editeur : double-clic sur « Editeur Sami.cmd » (ou .\editeur.ps1)  puis http://127.0.0.1:8790
# Relance propre : arrete l'ancien serveur s'il tourne encore, recompile l'interface, attend que le serveur reponde,
# puis ouvre le navigateur. Si le serveur s'arrete sur une erreur, il est relance.
. "$PSScriptRoot\runtime\env.ps1"
$node = (Get-Command node -ErrorAction SilentlyContinue)
if (-not $node) { Write-Host 'Node.js est requis (https://nodejs.org).' -ForegroundColor Red; Read-Host 'Entree pour fermer'; exit 1 }
$old = Get-NetTCPConnection -LocalPort 8790 -State Listen -ErrorAction SilentlyContinue
if ($old) {
    Write-Host 'Arret de l''ancien editeur...' -ForegroundColor Yellow
    $old | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 800
}
node "$PSScriptRoot\app\build.mjs" | Out-Null
Write-Host 'Editeur Sami -> http://127.0.0.1:8790  (ferme cette fenetre pour l''arreter)' -ForegroundColor Green
$opened = $false
while ($true) {
    $srv = Start-Process node -ArgumentList "`"$PSScriptRoot\app\server.mjs`"" -NoNewWindow -PassThru
    if (-not $opened) {
        for ($i = 0; $i -lt 40; $i++) {
            try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 'http://127.0.0.1:8790/api/reels' | Out-Null; break } catch { Start-Sleep -Milliseconds 250 }
        }
        Start-Process 'http://127.0.0.1:8790'
        $opened = $true
    }
    $srv.WaitForExit()
    Write-Host "Le serveur s'est arrete (code $($srv.ExitCode)) : relance dans 2 s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
}
