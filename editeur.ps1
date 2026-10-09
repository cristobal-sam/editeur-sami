# Lance l'editeur : double-clic sur « Editeur Sami.cmd » (ou .\editeur.ps1)  puis http://127.0.0.1:8790
# Relance propre : arrete l'ancien lanceur ET l'ancien serveur s'ils tournent encore, recompile l'interface, attend que le
# serveur reponde, puis ouvre le navigateur. Si le serveur s'arrete sur une erreur, il est relance.
#
# UN SEUL serveur par dossier (sinon : boite d'entree scannee deux fois = montages et exports en double) :
#  1. le lanceur prend le verrou runtime\cache\lanceur-<port>.json (pid + heure de demarrage) ;
#  2. il arrete les AUTRES boucles de lanceur plus anciennes (powershell dont la ligne de commande lance CE fichier, ou
#     parent du serveur en place) AVANT d'arreter le serveur : sinon l'ancienne boucle relancait aussitot un 2e serveur ;
#  3. il arrete le serveur du port et tout « node <ce dossier>\app\server.mjs » encore vivant, puis attend le port libre ;
#  4. il ne relance pas si le serveur sort avec le code 98 (port deja pris : un autre editeur tourne) ni si un lanceur
#     plus recent a pris le verrou (il s'arrete alors tout seul).
# Essais sur une copie : EDITEUR_PORT=<port> (meme variable que app\server.mjs), EDITEUR_SANS_NAVIGATEUR=1.
. "$PSScriptRoot\runtime\env.ps1"
$node = (Get-Command node -ErrorAction SilentlyContinue)
if (-not $node) { Write-Host 'Node.js est requis (https://nodejs.org).' -ForegroundColor Red; Read-Host 'Entree pour fermer'; exit 1 }

$port = 8790
if ($env:EDITEUR_PORT -match '^\d{2,5}$') { $port = [int]$env:EDITEUR_PORT }
$SORTIE_PORT_PRIS = 98   # code de sortie de app\server.mjs quand le port ne s'ouvre pas
$monDebut = (Get-Process -Id $PID).StartTime
$script = [IO.Path]::GetFullPath($PSCommandPath)
$serveurJs = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'app\server.mjs'))
$verrou = Join-Path $PSScriptRoot "runtime\cache\lanceur-$port.json"
New-Item -ItemType Directory -Force (Split-Path -Parent $verrou) | Out-Null
function Norm($s) { if ($s) { ([string]$s).Replace('/', '\').ToLowerInvariant() } else { '' } }

function Ecrire-Verrou {
    $tmp = "$verrou.$PID.tmp"
    @{pid = $PID; debut = [string]$monDebut.ToUniversalTime().Ticks; script = $script; port = $port; date = (Get-Date).ToString('s')} |
        ConvertTo-Json -Compress | Set-Content -Path $tmp -Encoding ASCII
    Move-Item -Force $tmp $verrou
}
function Lire-Verrou {
    for ($k = 0; $k -lt 3; $k++) {
        try { return (Get-Content -Raw -Path $verrou -ErrorAction Stop | ConvertFrom-Json) } catch { Start-Sleep -Milliseconds 100 }
    }
    return $null
}
# Ce lanceur est-il toujours le bon ? Non seulement si le verrou nomme un AUTRE lanceur vivant, demarre APRES lui
# (le plus recent gagne : deux doubles-clics rapproches ne s'arretent pas l'un l'autre). Verrou absent, illisible ou
# perime (processus mort, pid reutilise) : il le reprend.
function Test-Proprietaire {
    $v = Lire-Verrou
    if ($v -and [int]$v.pid -eq $PID) { return $true }
    if ($v -and $v.pid) {
        $p = Get-Process -Id ([int]$v.pid) -ErrorAction SilentlyContinue
        if ($p) {
            $memeProcessus = $false
            try { $memeProcessus = [math]::Abs($p.StartTime.ToUniversalTime().Ticks - [int64]$v.debut) -lt 20000000 } catch {}
            if ($memeProcessus -and $p.StartTime -gt $monDebut) { return $false }
        }
    }
    Ecrire-Verrou
    return $true
}
# Serveurs de CE dossier : celui qui ecoute sur le port, et tout « node <dossier>\app\server.mjs » (meme sans port).
function Serveurs-Du-Dossier($procs) {
    $ecoute = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object { [int]$_.OwningProcess })
    $cible = Norm $serveurJs
    return @($procs | Where-Object { ($ecoute -contains [int]$_.ProcessId) -or ($_.Name -eq 'node.exe' -and (Norm $_.CommandLine).Contains($cible)) })
}

Ecrire-Verrou

# ---- 1. les autres boucles de lanceur (AVANT le serveur, sinon elles le relancent aussitot) ----
$procs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
$ancetres = @{}
$cur = $procs | Where-Object { $_.ProcessId -eq $PID }
while ($cur -and -not $ancetres.ContainsKey([int]$cur.ProcessId)) {
    $ancetres[[int]$cur.ProcessId] = $true
    $parentId = $cur.ParentProcessId
    $cur = $procs | Where-Object { $_.ProcessId -eq $parentId }
}
$parents = @(Serveurs-Du-Dossier $procs | ForEach-Object { [int]$_.ParentProcessId })
$monScript = Norm $script
$lanceurs = @($procs | Where-Object {
    $id = [int]$_.ProcessId
    $cl = Norm $_.CommandLine
    ($_.Name -eq 'powershell.exe' -or $_.Name -eq 'pwsh.exe') -and $id -ne $PID -and -not $ancetres.ContainsKey($id) -and
    $_.CreationDate -lt $monDebut -and (
        $cl.Contains($monScript) -or
        # boucle lancee autrement (« .\editeur.ps1 » tape dans une console) : c'est le parent du serveur en place
        (($parents -contains $id) -and ($cl -match 'editeur\.ps1' -or $cl -notmatch '(^|\s)-(c|command|e|ec|encodedcommand)(\s|$)'))
    )
})
foreach ($l in $lanceurs) {
    Write-Host "Arret de l'ancien lanceur (pid $($l.ProcessId))..." -ForegroundColor Yellow
    Stop-Process -Id $l.ProcessId -Force -ErrorAction SilentlyContinue
}

# ---- 2. l'ancien serveur, puis le port libre (relu a chaque tour : un lanceur arrete a pu en lancer un juste avant) ----
$libre = $false
$annonce = $false
for ($i = 0; $i -lt 40; $i++) {
    $serveurs = @(Serveurs-Du-Dossier @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue))
    foreach ($s in $serveurs) {
        if (-not $annonce) { Write-Host "Arret de l'ancien editeur..." -ForegroundColor Yellow; $annonce = $true }
        Stop-Process -Id $s.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if (-not $serveurs.Count -and -not (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)) { $libre = $true; break }
    Start-Sleep -Milliseconds 250
}
if (-not $libre) {
    Write-Host "Le port $port reste occupe par un autre programme : l'editeur ne peut pas demarrer." -ForegroundColor Red
    Start-Sleep -Seconds 8
    exit 2
}

node "$PSScriptRoot\app\build.mjs" | Out-Null
Write-Host "Editeur Sami -> http://127.0.0.1:$port  (ferme cette fenetre pour l'arreter)" -ForegroundColor Green
$opened = ($env:EDITEUR_SANS_NAVIGATEUR -eq '1')
$rapides = 0
try {
    while ($true) {
        if (-not (Test-Proprietaire)) {
            Write-Host 'Un lanceur plus recent a pris la main : celui-ci s''arrete (pas de 2e serveur).' -ForegroundColor Yellow
            exit 0
        }
        $debut = Get-Date
        $srv = Start-Process node -ArgumentList "`"$serveurJs`"" -NoNewWindow -PassThru
        $null = $srv.Handle   # sans cela, ExitCode reste vide sous Windows PowerShell
        if (-not $opened) {
            for ($i = 0; $i -lt 40 -and -not $srv.HasExited; $i++) {
                try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 "http://127.0.0.1:$port/api/reels" | Out-Null; break } catch { Start-Sleep -Milliseconds 250 }
            }
            if (-not $srv.HasExited) { Start-Process "http://127.0.0.1:$port" }
            $opened = $true
        }
        $srv.WaitForExit()
        $code = $srv.ExitCode
        if ($code -eq $SORTIE_PORT_PRIS) {
            Write-Host "Le port $port est deja pris par un autre editeur : ce lanceur s'arrete sans relancer (pas de 2e serveur)." -ForegroundColor Red
            Start-Sleep -Seconds 8
            exit 2
        }
        if (-not (Test-Proprietaire)) {
            Write-Host 'Un lanceur plus recent a pris la main : celui-ci s''arrete (pas de 2e serveur).' -ForegroundColor Yellow
            exit 0
        }
        # arrets rapides a repetition (erreur au demarrage) : relances espacees
        if (((Get-Date) - $debut).TotalSeconds -lt 15) { $rapides++ } else { $rapides = 0 }
        $pause = if ($rapides -ge 3) { 15 } else { 2 }
        Write-Host "Le serveur s'est arrete (code $code) : relance dans $pause s..." -ForegroundColor Yellow
        Start-Sleep -Seconds $pause
    }
} finally {
    # verrou rendu seulement s'il est encore a ce lanceur (fermer la fenetre peut sauter cette etape : verrou perime, repris)
    $v = Lire-Verrou
    if ($v -and [int]$v.pid -eq $PID) { Remove-Item -Force $verrou -ErrorAction SilentlyContinue }
}
