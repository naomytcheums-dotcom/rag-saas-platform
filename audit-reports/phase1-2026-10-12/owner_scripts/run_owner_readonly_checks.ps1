# Run in YOUR OWN terminal. Reads the production database in READ-ONLY mode and writes the answers to a file OUTSIDE the repository.
# Usage:
#   $env:PGURL = "postgresql://<user>:<password>@<host>:5432/postgres"   # never paste it in a chat; this script never prints it
#   .\run_owner_readonly_checks.ps1
# Uses a local psql if present, otherwise the postgres:17 Docker image. The session is forced read-only (default_transaction_read_only=on).
param([string]$OutDir = "$HOME\rag-secure-evidence")

if (-not $env:PGURL) { Write-Error "Set `$env:PGURL first (see the header of this file)."; exit 1 }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
$sql = Join-Path $PSScriptRoot 'owner_readonly_checks.sql'
$out = Join-Path $OutDir ("owner_readonly_checks_{0}.txt" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$env:PGOPTIONS = '-c default_transaction_read_only=on -c statement_timeout=30000'

if (Get-Command psql -ErrorAction SilentlyContinue) {
    psql $env:PGURL -X -v ON_ERROR_STOP=0 -f $sql 2>&1 | Tee-Object -FilePath $out
} else {
    docker run --rm -e PGURL -e PGOPTIONS -v "${PSScriptRoot}:/sql:ro" postgres:17 sh -c 'psql "$PGURL" -X -v ON_ERROR_STOP=0 -f /sql/owner_readonly_checks.sql' 2>&1 | Tee-Object -FilePath $out
}
Write-Host "Answers saved to: $out  (keep it outside the repository)"
Remove-Item Env:PGOPTIONS -ErrorAction SilentlyContinue
