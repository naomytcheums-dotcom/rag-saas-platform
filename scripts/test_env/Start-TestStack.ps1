<#
 Starts (or reuses) the LOCAL, throw-away test stack: PostgreSQL 17 + pgvector, Redis 7, MinIO. Everything is bound to 127.0.0.1.
 It prepares three databases, applies the Alembic chain to them, creates the S3 buckets and writes scripts/test_env/.stack.env
 (git-ignored; random password generated here, never committed) for Run-IsolatedSuite.ps1.
 Nothing here can reach Supabase, Render or any hosted service: it only talks to docker and to 127.0.0.1.
#>
param(
    [int]$PgPort = 25432,
    [int]$RedisPort = 26379,
    [int]$MinioPort = 29000,
    [string]$Prefix = 'rag-test'
)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$stackFile = Join-Path $PSScriptRoot '.stack.env'
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

docker version --format '{{.Server.Version}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Docker is not running: start it, then run this script again (nothing was started).' }

if (Test-Path $stackFile) {
    $existing = Get-Content $stackFile -Raw | ConvertFrom-StringData
    $password = $existing.STACK_PASSWORD
} else {
    $password = -join ((48..57) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
}

function Ensure-Container($name, $runArgs) {
    $state = docker ps -a --filter "name=^/$name$" --format '{{.Status}}'
    if (-not $state) { docker run -d --name $name @runArgs | Out-Null }
    elseif ($state -notlike 'Up*') { docker start $name | Out-Null }
}

Ensure-Container "$Prefix-pg" @('-e', 'POSTGRES_USER=rag_test', '-e', "POSTGRES_PASSWORD=$password", '-p', "127.0.0.1:${PgPort}:5432", 'pgvector/pgvector:pg17')
Ensure-Container "$Prefix-redis" @('-p', "127.0.0.1:${RedisPort}:6379", 'redis:7-alpine')
Ensure-Container "$Prefix-minio" @('-e', 'MINIO_ROOT_USER=minioadmin', '-e', 'MINIO_ROOT_PASSWORD=minioadmin', '-p', "127.0.0.1:${MinioPort}:9000", 'bitnamilegacy/minio:2025.7.23-debian-12-r5')

for ($i = 0; $i -lt 60; $i++) {
    docker exec "$Prefix-pg" pg_isready -U rag_test 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep 1
}
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not become ready in 60 s' }
for ($i = 0; $i -lt 30; $i++) { if ((curl.exe -s -o NUL -w '%{http_code}' "http://127.0.0.1:$MinioPort/minio/health/live") -eq '200') { break }; Start-Sleep 1 }

$databases = @('rag_test_integration', 'rag_test_roundtrip_scratch', 'pytest_p0')
foreach ($db in $databases) {
    $exists = docker exec "$Prefix-pg" psql -U rag_test -d postgres -Atc "select 1 from pg_database where datname='$db'"
    if (-not $exists) { docker exec "$Prefix-pg" psql -U rag_test -d postgres -c "create database $db" | Out-Null }
}

$env:PYTHONDONTWRITEBYTECODE = '1'
# Alembic imports the application settings: give it the required ones (throw-away values) and never read a real .env file.
$migrationEnv = @{
    RAG_ENV_FILE = '.start-teststack.no-env-file'
    JWT_SECRET_KEY = -join ((48..57) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ })
    SESSION_MIDDLEWARE_SECRET = -join ((48..57) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ })
    AUDIT_LOG_HMAC_SECRET_KEY = -join ((48..57) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ })
    SUPPORT_EMAIL = 'support@test-stack.invalid'
}
foreach ($entry in $migrationEnv.GetEnumerator()) { Set-Item "Env:$($entry.Key)" $entry.Value }
foreach ($db in $databases) {
    $url = "postgresql+asyncpg://rag_test:${password}@127.0.0.1:${PgPort}/$db"
    $env:DATABASE_URL = $url; $env:DATABASE_URL_TRANSACTION = $url
    Push-Location $root
    & $python -m alembic upgrade head | Out-Null
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "alembic upgrade head failed on $db" }
    Pop-Location
}
Remove-Item Env:DATABASE_URL, Env:DATABASE_URL_TRANSACTION
foreach ($name in $migrationEnv.Keys) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }

$env:S3_ENDPOINT_URL = "http://127.0.0.1:$MinioPort"
& $python (Join-Path $root 'scripts\ci_create_buckets.py') 2>&1 | Out-Null  # an existing bucket is fine on a re-run

@(
    "STACK_PASSWORD=$password",
    "RAG_TEST_DATABASE_URL=postgresql+asyncpg://rag_test:${password}@127.0.0.1:${PgPort}/rag_test_integration",
    "RAG_TEST_PG_ROUNDTRIP_URL=postgresql+asyncpg://rag_test:${password}@127.0.0.1:${PgPort}/rag_test_roundtrip_scratch",
    "RAG_TEST_P0_PG_URL=postgresql+asyncpg://rag_test:${password}@127.0.0.1:${PgPort}/pytest_p0",
    "RAG_TEST_REDIS_URL=redis://127.0.0.1:$RedisPort",
    "RAG_TEST_S3_ENDPOINT=http://127.0.0.1:$MinioPort"
) | Set-Content $stackFile -Encoding ascii
Write-Host "Test stack ready (PostgreSQL :$PgPort, Redis :$RedisPort, MinIO :$MinioPort). Settings written to scripts/test_env/.stack.env (git-ignored)."
