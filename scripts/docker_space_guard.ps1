<#
.SYNOPSIS
  Garde-fou d'espace disque pour Docker Desktop (WSL2) sous Windows.

.DESCRIPTION
  Probleme observe (2026-10-19) : le disque virtuel de Docker (docker_data.vhdx) ne rend JAMAIS d'espace a Windows tout seul. Il grossit a chaque build,
  pull ou test, atteint des dizaines de Go, et le moteur finit par tomber en erreur 500 quand C: est plein. Supprimer des images DANS Docker ne reduit pas
  le fichier sur C: : il faut le compacter.

  Ce script :
    1. mesure la taille du fichier docker_data.vhdx et l'espace libre sur C: ;
    2. (par defaut) nettoie ce qui est sans risque : cache de build de plus de 48 h et images orphelines. Il ne touche JAMAIS aux conteneurs ni aux volumes
       (les bases de test et les modeles Ollama y sont) ;
    3. avec -Compact (droits administrateur) : arrete Docker et WSL, compacte le fichier avec diskpart, relance Docker. C'est ce qui rend l'espace a Windows ;
    4. avec -Budget (Go, defaut 25) : dit clairement quand le fichier depasse le budget.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\docker_space_guard.ps1            # mesure + nettoyage sans risque
  powershell -ExecutionPolicy Bypass -File scripts\docker_space_guard.ps1 -Compact   # en administrateur : rend l'espace a Windows
  powershell -ExecutionPolicy Bypass -File scripts\docker_space_guard.ps1 -InstallWeeklyTask   # planifie le nettoyage sans risque chaque dimanche
#>
param(
    [switch]$Compact,
    [switch]$InstallWeeklyTask,
    [int]$Budget = 25,
    [int]$MinFreeGB = 15
)

$ErrorActionPreference = "Stop"
$vhdx = Join-Path $env:LOCALAPPDATA "Docker\wsl\disk\docker_data.vhdx"

function Get-FreeGB { [math]::Round((Get-PSDrive C).Free / 1GB, 1) }
function Get-VhdxGB { if (Test-Path $vhdx) { [math]::Round((Get-Item $vhdx).Length / 1GB, 1) } else { 0 } }
function Test-Docker { $null = docker info --format "{{.ServerVersion}}" 2>$null; return ($LASTEXITCODE -eq 0) }

if ($InstallWeeklyTask) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 10:00
    Register-ScheduledTask -TaskName "RagSaas-DockerSpaceGuard" -Action $action -Trigger $trigger -Description "Nettoyage sans risque du cache de build Docker (jamais de conteneur ni de volume)" -Force | Out-Null
    Write-Host "Tache planifiee 'RagSaas-DockerSpaceGuard' creee (dimanche 10:00, utilisateur courant, sans droits administrateur)."
    return
}

Write-Host ("Avant : C: libre {0} Go | docker_data.vhdx {1} Go (budget {2} Go)" -f (Get-FreeGB), (Get-VhdxGB), $Budget)

if (Test-Docker) {
    docker builder prune -f --filter "until=48h" | Select-Object -Last 1
    docker image prune -f | Select-Object -Last 1
} else {
    Write-Warning "Docker ne repond pas : nettoyage interne ignore."
}

if ($Compact) {
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) { throw "-Compact demande une fenetre PowerShell ouverte en administrateur." }
    Get-Process | Where-Object { $_.ProcessName -match "^(Docker Desktop|com\.docker|docker-agent)" } | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    wsl --shutdown
    Start-Sleep 8
    $script = Join-Path $env:TEMP "compact_docker_vhdx.txt"
    "select vdisk file=`"$vhdx`"`r`nattach vdisk readonly`r`ncompact vdisk`r`ndetach vdisk`r`nexit" | Set-Content -Path $script -Encoding ASCII
    diskpart /s $script
    Remove-Item $script -Force
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Host "Docker Desktop relance."
}

$vh = Get-VhdxGB; $free = Get-FreeGB
Write-Host ("Apres : C: libre {0} Go | docker_data.vhdx {1} Go" -f $free, $vh)
if ($vh -gt $Budget) { Write-Warning "docker_data.vhdx depasse le budget de $Budget Go : lancez ce script avec -Compact (en administrateur) apres avoir supprime les volumes inutiles." }
if ($free -lt $MinFreeGB) { Write-Warning "Moins de $MinFreeGB Go libres sur C: : ne lancez pas de build ni de suite de tests avant d'avoir libere de la place." }
