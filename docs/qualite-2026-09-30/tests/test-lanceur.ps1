# JAMAIS DEUX SERVEURS : essai du lanceur editeur.ps1 + sortie 98 de app/server.mjs sur des COPIES (ports 18793 / 18794),
# jamais le vrai dossier ni le vrai serveur 8790 (verifie a la fin : pid du port 8790 et lanceur du verrou inchanges).
#   powershell -NoProfile -ExecutionPolicy Bypass -File docs\qualite-2026-09-30\tests\test-lanceur.ps1     (environ 2 min)
# Bacs : runtime\cache\tmp\test-lanceur-<date>\ (aucune jonction). Cas : ancien lanceur de l'incident (cas\editeur-ancien.ps1),
# doublon code 98 (meme dossier / autre dossier), zombie de l'ancien code serveur (avant-ronde2), 3 lancements rapproches,
# plantage, serveur lance a la main pendant la pause de relance (plugin), serveur qui sort toujours avec 98.
$ErrorActionPreference = 'Stop'
$REAL = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$W = Join-Path $REAL ("runtime\cache\tmp\test-lanceur-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force $W | Out-Null
$A = Join-Path $W 'bacA'      # copie principale (port 18793)
$B2 = Join-Path $W 'bacB2'    # 2e dossier : serveur en double sur le meme port
$C = Join-Path $W 'bacC'      # serveur factice qui sort toujours avec le code 98 (port 18794)
$PORT = 18793
$fails = 0
$vraiServeur = @(Get-NetTCPConnection -LocalPort 8790 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { [int]$_.OwningProcess })
$vraiLanceur = (Get-Content "$REAL\runtime\cache\lanceur-8790.json" -Raw | ConvertFrom-Json).pid
function Ok($cond, $msg) { if ($cond) { Write-Host "OK    $msg" } else { Write-Host "ECHEC $msg"; $script:fails++ } }
function Bac($dir) {
    foreach ($d in 'app\ui', 'runtime\cache\tmp', 'projects', 'media\entree\lot1') { New-Item -ItemType Directory -Force (Join-Path $dir $d) | Out-Null }
    Copy-Item "$REAL\app\server.mjs" "$dir\app\server.mjs"
    Copy-Item "$REAL\app\ui\index.html" "$dir\app\ui\index.html"
    Copy-Item "$REAL\runtime\env.ps1" "$dir\runtime\env.ps1"
    Set-Content "$dir\app\build.mjs" '// build factice (essai du lanceur)'
    [IO.File]::WriteAllBytes("$dir\media\entree\lot1\essai.mp4", [byte[]](1..64))
}
function Srv($root) { @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains("$root\app\server.mjs".ToLower()) }) }
function Lanceurs($root) { @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe' or Name='pwsh.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains("$root\editeur.ps1".ToLower()) }) }
function Ecoute($port) { @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object { [int]$_.OwningProcess }) }
function Attendre($cond, $sec = 20) { $t = (Get-Date).AddSeconds($sec); while ((Get-Date) -lt $t) { if (& $cond) { return $true }; Start-Sleep -Milliseconds 250 }; return $false }
function Lancer($root, $port, $exe = 'powershell') {
    $env:EDITEUR_PORT = "$port"; $env:EDITEUR_SANS_NAVIGATEUR = '1'
    $p = Start-Process $exe -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\editeur.ps1" -WindowStyle Hidden -PassThru
    $null = $p.Handle
    return $p
}
function Direct($root, $port, $nom) {
    $env:EDITEUR_PORT = "$port"
    $p = Start-Process node -ArgumentList "`"$root\app\server.mjs`"" -WindowStyle Hidden -PassThru -RedirectStandardError "$W\$nom-err.txt" -RedirectStandardOutput "$W\$nom-out.txt"
    $null = $p.Handle
    return $p
}

Bac $A; Bac $B2; Bac $C
$ancien = (Get-Content "$PSScriptRoot\cas\editeur-ancien.ps1" -Raw).Replace('8790', "$PORT").Replace("Start-Process 'http://127.0.0.1:$PORT'", '# (pas de navigateur)')
Set-Content "$A\editeur.ps1" $ancien -Encoding UTF8

Write-Host '--- 1. ancien lanceur (incident) : il relance un serveur des qu''on tue le sien'
$L1 = Lancer $A $PORT
Ok (Attendre { @(Ecoute $PORT).Count -gt 0 }) 'ancien lanceur : serveur demarre'
$S1 = (Ecoute $PORT)[0]
Ok (Attendre { Test-Path "$A\projects\_revision.json" } 15) 'le serveur du port scanne sa boite d''entree (_revision.json cree)'
Stop-Process -Id $S1 -Force
Ok (Attendre { $e = Ecoute $PORT; $e.Count -gt 0 -and $e[0] -ne $S1 } 10) 'ancienne boucle : relance aussitot (cause de l''incident)'

Write-Host '--- 2. doublon (nouveau code) dans le MEME dossier : code 98, _revision.json intact'
Start-Sleep -Seconds 6
$rev = Get-Item "$A\projects\_revision.json"
$h0 = (Get-FileHash $rev.FullName).Hash
$t0 = Get-Date
$dup = Direct $A $PORT 'dup-meme'
$fini = $dup.WaitForExit(10000)
Ok ($fini -and $dup.ExitCode -eq 98) "doublon du meme dossier : sortie $($dup.ExitCode) en $([math]::Round(((Get-Date) - $t0).TotalSeconds, 2)) s"
$dup2 = Direct $B2 $PORT 'dup-autre'
Ok ($dup2.WaitForExit(10000) -and $dup2.ExitCode -eq 98) "doublon d'un autre dossier : sortie $($dup2.ExitCode)"
Start-Sleep -Seconds 7   # plus que le 1er scan (1,5 s) et un tour du scanneur (5 s)
Ok (-not (Test-Path "$B2\projects\_revision.json")) 'doublon : aucune boite d''entree scannee'
Ok ((Get-Content "$A\runtime\cache\erreurs-serveur.log" -Raw) -match 'demarrage refuse : port 18793') 'raison ecrite dans erreurs-serveur.log'

Write-Host '--- 3. zombie de l''ANCIEN code (survit a EADDRINUSE) dans le meme dossier, puis nouveau lanceur'
Copy-Item "$REAL\docs\qualite-2026-09-30\avant-ronde2\app-server.mjs" "$A\app\server.mjs" -Force
$z = Direct $A $PORT 'zombie'
Start-Sleep -Seconds 4
Ok (-not $z.HasExited) "ancien code : le doublon reste vivant sans port (zombie pid $($z.Id))"
Copy-Item "$REAL\app\server.mjs" "$A\app\server.mjs" -Force
Copy-Item "$REAL\editeur.ps1" "$A\editeur.ps1" -Force
$avant = (Ecoute $PORT)[0]
$L2 = Lancer $A $PORT
Ok (Attendre { $L1.HasExited } 15) "ancienne boucle $($L1.Id) arretee"
Ok (Attendre { $z.HasExited } 15) 'zombie arrete par le nouveau lanceur'
Ok (Attendre { $e = Ecoute $PORT; $e.Count -gt 0 -and $e[0] -ne $avant } 20) 'nouveau serveur a l''ecoute'
Start-Sleep -Seconds 6
$S2 = (Ecoute $PORT)[0]
Ok (@(Srv $A).Count -eq 1) "un seul serveur de la copie (trouves : $(@(Srv $A).Count))"
Ok ((Get-CimInstance Win32_Process -Filter "ProcessId=$S2").ParentProcessId -eq $L2.Id) "serveur $S2 enfant du nouveau lanceur $($L2.Id)"
Ok (@(Lanceurs $A).Count -eq 1) "un seul lanceur (trouves : $(@(Lanceurs $A).Count))"
$v = Get-Content "$A\runtime\cache\lanceur-$PORT.json" -Raw | ConvertFrom-Json
Ok ($v.pid -eq $L2.Id) "verrou au nouveau lanceur ($($v.pid))"

Write-Host '--- 4. doublon lance a la main pendant que le nouveau lanceur tourne'
$dup3 = Direct $A $PORT 'dup-3'
Ok ($dup3.WaitForExit(10000) -and $dup3.ExitCode -eq 98) "doublon : sortie $($dup3.ExitCode)"
Start-Sleep -Seconds 3
Ok (@(Srv $A).Count -eq 1 -and (Ecoute $PORT)[0] -eq $S2 -and -not $L2.HasExited) 'le serveur du lanceur continue, toujours un seul'

Write-Host '--- 5. trois lancements rapproches (0,15 s) : le plus recent gagne'
$L3 = Lancer $A $PORT
Start-Sleep -Milliseconds 150
$L4 = Lancer $A $PORT
Start-Sleep -Milliseconds 150
$L5 = Lancer $A $PORT
Ok (Attendre { $L2.HasExited -and $L3.HasExited -and $L4.HasExited } 30) 'lanceurs plus anciens arretes'
Ok (Attendre { @(Ecoute $PORT).Count -gt 0 } 20) 'serveur a l''ecoute'
Start-Sleep -Seconds 8
Ok (@(Srv $A).Count -eq 1 -and @(Lanceurs $A).Count -eq 1 -and -not $L5.HasExited) "un serveur, un lanceur, le dernier (serveurs $(@(Srv $A).Count), lanceurs $(@(Lanceurs $A).Count))"

Write-Host '--- 6. plantage : relance par le lanceur'
$S5 = (Ecoute $PORT)[0]
Stop-Process -Id $S5 -Force
Ok (Attendre { $e = Ecoute $PORT; $e.Count -gt 0 -and $e[0] -ne $S5 } 15) 'serveur relance'
Start-Sleep -Seconds 3
Ok (@(Srv $A).Count -eq 1) 'toujours un seul serveur'

Write-Host '--- 7. plantage + serveur lance a la main pendant les 2 s de pause (plugin) : le lanceur ne double pas'
$S6 = (Ecoute $PORT)[0]
Stop-Process -Id $S6 -Force
Start-Sleep -Milliseconds 400
$direct = Direct $A $PORT 'direct'
Ok ($L5.WaitForExit(30000)) 'lanceur arrete tout seul (port pris par l''autre serveur)'
Ok ($L5.ExitCode -eq 2) "code du lanceur 2 (obtenu $($L5.ExitCode))"
Start-Sleep -Seconds 2
Ok (@(Srv $A).Count -eq 1 -and (Ecoute $PORT)[0] -eq $direct.Id) "un seul serveur : celui lance a la main (serveurs $(@(Srv $A).Count))"

Write-Host '--- 8. serveur qui sort avec 98 : pas de relance'
Copy-Item "$REAL\editeur.ps1" "$C\editeur.ps1" -Force
Set-Content "$C\app\server.mjs" "import fs from 'node:fs'; fs.appendFileSync(new URL('./demarrages.txt', import.meta.url), 'x'); process.exit(98);"
$L6 = Lancer $C 18794
Ok ($L6.WaitForExit(30000)) 'lanceur arrete tout seul'
Ok ($L6.ExitCode -eq 2) "code du lanceur 2 (obtenu $($L6.ExitCode))"
Ok ((Get-Content "$C\app\demarrages.txt" -Raw).Length -eq 1) "serveur demarre une seule fois ($((Get-Content "$C\app\demarrages.txt" -Raw).Length))"

Write-Host '--- fin : arret de la copie ; le vrai serveur 8790 et son lanceur n''ont pas bouge'
foreach ($l in Lanceurs $A) { Stop-Process -Id $l.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 500
foreach ($s in Srv $A) { Stop-Process -Id $s.ProcessId -Force -ErrorAction SilentlyContinue }
foreach ($s in Srv $B2) { Stop-Process -Id $s.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 3
Ok (@(Srv $A).Count -eq 0 -and @(Lanceurs $A).Count -eq 0 -and @(Ecoute $PORT).Count -eq 0) 'copie arretee : plus rien ne tourne'
$vraiApres = @(Get-NetTCPConnection -LocalPort 8790 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { [int]$_.OwningProcess })
Ok (($vraiServeur -join ',') -eq ($vraiApres -join ',') -and (Get-Process -Id $vraiLanceur -ErrorAction SilentlyContinue)) "vrai serveur 8790 inchange (pid $($vraiApres -join ',')), vrai lanceur $vraiLanceur vivant"
Write-Host "RESULTAT : $(if ($fails) { "$fails ECHEC(S)" } else { 'tout reussi' })"
