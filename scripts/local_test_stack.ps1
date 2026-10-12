<#
.SYNOPSIS
  Reproducible, disposable local stack for the backend tests (PostgreSQL+pgvector, Redis, MinIO, ClamAV), and the full suite with coverage.

.DESCRIPTION
  Nothing here touches a remote service or the real .env: the database is a local container, the password is generated at creation and never printed,
  and the test run goes through scripts/run_tests_local.sh (tests/_remote_guard.py refuses anything that is not local and disposable).

    pwsh scripts/local_test_stack.ps1 up        # create or start the containers (idempotent)
    pwsh scripts/local_test_stack.ps1 migrate   # alembic upgrade head on the test database
    pwsh scripts/local_test_stack.ps1 test      # full suite with coverage -> coverage.xml and a terminal summary
    pwsh scripts/local_test_stack.ps1 test tests/test_auth_api.py -q   # any pytest arguments instead of the full suite
    pwsh scripts/local_test_stack.ps1 down      # remove the containers (data included)

  Needs Docker, Git for Windows (sh) and a Python environment with requirements-api.txt installed (-Python to choose the interpreter).
#>
param(
  [Parameter(Position = 0)][ValidateSet('up', 'migrate', 'test', 'down')][string]$Action = 'up',
  [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$PytestArgs,
  [string]$Python = 'python',
  [string]$Database = 'pytest_p0'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Pg = 'rag-test-pg'; $PgPort = 25432
$RedisName = 'rag-test-redis'; $RedisPort = 26379
$Minio = 'rag-test-minio-9000'
$Clam = 'rag-test-clamav'

function Test-Container([string]$Name) { [bool](docker ps -a --filter "name=^$Name$" --format '{{.Names}}') }
function Test-Running([string]$Name) { [bool](docker ps --filter "name=^$Name$" --format '{{.Names}}') }

function Start-Or-Create([string]$Name, [scriptblock]$Create) {
  if (Test-Running $Name) { return }
  if (Test-Container $Name) { docker start $Name | Out-Null } else { & $Create | Out-Null }
}

function Get-TestPassword { (docker exec $Pg printenv POSTGRES_PASSWORD).Trim() }

function Initialize-TestEnvironment {
  $pw = Get-TestPassword
  $env:TEST_DATABASE_URL = "postgresql+asyncpg://rag_test:$pw@127.0.0.1:$PgPort/$Database"
  $env:TEST_REDIS_URL = "redis://127.0.0.1:$RedisPort"
  $env:RAG_ENV_FILE = '.no-env'
  $env:DATABASE_URL = $env:TEST_DATABASE_URL
  $env:DATABASE_URL_TRANSACTION = ''
  $env:JWT_SECRET_KEY = 'local-measure-only-0123456789abcdef0123456789'
  $env:SESSION_MIDDLEWARE_SECRET = 'local-measure-only-0123456789abcdef01234567'
  $env:SUPPORT_EMAIL = 'local@example.test'
  $env:AUDIT_LOG_HMAC_SECRET_KEY = 'local-measure-only-0123456789abcdef0123456789'
  $git = (Get-Command git -ErrorAction SilentlyContinue)
  if ($git) { $env:Path = (Split-Path (Split-Path $git.Source)) + '\bin;' + (Split-Path (Split-Path $git.Source)) + '\usr\bin;' + $env:Path }
  $pyCmd = Get-Command $Python -ErrorAction SilentlyContinue
  if ($pyCmd) { $env:Path = (Split-Path $pyCmd.Source) + ';' + $env:Path }
}

switch ($Action) {
  'up' {
    Start-Or-Create $Pg {
      $pw = -join ((48..57) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
      docker run -d --name $Pg -e POSTGRES_USER=rag_test -e "POSTGRES_PASSWORD=$pw" -e POSTGRES_DB=postgres -p "127.0.0.1:${PgPort}:5432" pgvector/pgvector:pg17
    }
    Start-Or-Create $RedisName { docker run -d --name $RedisName -p "127.0.0.1:${RedisPort}:6379" redis:7-alpine }
    Start-Or-Create $Minio {
      docker run -d --name $Minio -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin -p 127.0.0.1:9000:9000 bitnamilegacy/minio:2025.7.23-debian-12-r5
    }
    Start-Or-Create $Clam { docker run -d --name $Clam -p 127.0.0.1:3310:3310 clamav/clamav:stable }
    for ($i = 0; $i -lt 60; $i++) { docker exec $Pg pg_isready -U rag_test 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { break }; Start-Sleep 2 }
    $exists = docker exec $Pg psql -U rag_test -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$Database'"
    if (-not $exists) { docker exec $Pg psql -U rag_test -d postgres -c "CREATE DATABASE $Database" | Out-Null }
    docker exec $Pg psql -U rag_test -d $Database -c 'CREATE EXTENSION IF NOT EXISTS vector' | Out-Null
    Write-Host "stack up: postgres 127.0.0.1:$PgPort/$Database, redis 127.0.0.1:$RedisPort, minio 127.0.0.1:9000, clamav 127.0.0.1:3310 (ClamAV needs a few minutes to load its signatures)"
  }
  'migrate' {
    Initialize-TestEnvironment
    Push-Location $Root; try { & $Python -m alembic upgrade head; & $Python -m alembic current } finally { Pop-Location }
  }
  'test' {
    Initialize-TestEnvironment
    Push-Location $Root
    try {
      if (-not $PytestArgs) { $PytestArgs = @('tests', '-q', '-rfE', '--cov=api', '--cov-report=xml:coverage.xml', '--cov-report=term:skip-covered') }
      sh scripts/run_tests_local.sh @PytestArgs
      exit $LASTEXITCODE
    } finally { Pop-Location }
  }
  'down' {
    foreach ($n in $Pg, $RedisName, $Minio, $Clam) { if (Test-Container $n) { docker rm -f $n | Out-Null } }
    Write-Host 'stack removed'
  }
}
