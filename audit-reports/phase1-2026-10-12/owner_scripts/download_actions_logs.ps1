# Run in YOUR OWN terminal with an authenticated GitHub CLI (gh auth login). READ-ONLY: it only downloads the log archives of the CI runs
# #1..#194 (the window 2026-09-19 -> 2026-10-10 when the test job used the repository secrets) so that the evidence survives the 90-day retention.
# Archives go OUTSIDE the repository (they can contain internal data). Runs whose logs have expired answer 404 and are listed, not retried.
# Usage:  .\download_actions_logs.ps1 [-Csv <path to ci_yml_runs_1-232.csv>] [-OutDir <folder>]
param(
    [string]$Csv = (Join-Path $PSScriptRoot '..\evidence\ci_yml_runs_1-232.csv'),
    [string]$OutDir = "$HOME\rag-secure-evidence\actions-logs",
    [string]$Repo = 'naomytcheums-dotcom/rag-saas-platform'
)
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Write-Error 'GitHub CLI (gh) not found.'; exit 1 }
gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error 'Run: gh auth login'; exit 1 }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$runs = Import-Csv $Csv | Where-Object { $_.used_repository_secrets_in_backend_tests -eq 'True' } | Sort-Object { [int]$_.run_number }
$missing = @()
foreach ($r in $runs) {
    $target = Join-Path $OutDir ("run{0:000}_{1}.zip" -f [int]$r.run_number, $r.run_id)
    if (Test-Path $target) { continue }
    gh api "repos/$Repo/actions/runs/$($r.run_id)/logs" > $target 2>$null
    if ($LASTEXITCODE -ne 0 -or (Get-Item $target).Length -lt 100) { Remove-Item $target -ErrorAction SilentlyContinue; $missing += $r.run_number }
    Start-Sleep -Milliseconds 400
}
Write-Host ("Downloaded: {0} of {1}. Not available (expired or failed): {2}" -f ((Get-ChildItem $OutDir -Filter *.zip).Count), $runs.Count, ($missing -join ', '))
Get-ChildItem $OutDir -Filter *.zip | Get-FileHash -Algorithm SHA256 | Select-Object Hash, @{n='File';e={Split-Path $_.Path -Leaf}} | Export-Csv (Join-Path $OutDir 'SHA256.csv') -NoTypeInformation
