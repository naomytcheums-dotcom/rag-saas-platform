<#
 Runs pytest through scripts/run_isolated_tests.py against the stack started by Start-TestStack.ps1.
   .\scripts\test_env\Run-IsolatedSuite.ps1                       # whole suite, live Celery worker, strict skips
   .\scripts\test_env\Run-IsolatedSuite.ps1 -Network              # the network_flaky group (real GitHub public API, rate limited)
   .\scripts\test_env\Run-IsolatedSuite.ps1 -PytestArgs tests/test_billing.py,-q
 Optional tools: set RAG_TEST_EXTRA_PATH (tesseract / poppler directories) and RAG_TEST_TESSDATA (needs eng + fra) in the caller.
 Strict skips: a skip that is not a documented external dependency (tests/external_skip_allowlist.py) is reported as a failure.
#>
param(
    [switch]$Network,
    [string[]]$PytestArgs = @()
)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$stackFile = Join-Path $PSScriptRoot '.stack.env'
if (-not (Test-Path $stackFile)) { throw 'Run scripts/test_env/Start-TestStack.ps1 first.' }
foreach ($pair in (Get-Content $stackFile -Raw | ConvertFrom-StringData).GetEnumerator()) {
    if ($pair.Key -like 'RAG_TEST_*') { Set-Item "Env:$($pair.Key)" $pair.Value }
}
Remove-Item Env:DATABASE_URL, Env:DATABASE_URL_TRANSACTION -ErrorAction SilentlyContinue
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
Set-Location $root
if ($Network) {
    & $python scripts/run_isolated_tests.py --flush-redis -m network_flaky -o addopts= -v -rfEsx -p no:cacheprovider @PytestArgs
} else {
    & $python scripts/run_isolated_tests.py --flush-redis --with-worker -v -rfEsx -p no:cacheprovider @PytestArgs
}
exit $LASTEXITCODE
