<#
 Runs the WHOLE suite through scripts/run_isolated_tests.py in memory-bounded batches (one pytest process at a time) and keeps one
 JUnit XML + one text log per batch, so that every test gets an identifier and a status. Nothing is excluded: the batches are built
 from every test file found on disk, plus a catch-all batch for any file the named batches did not match, plus the 7 files that CI
 ignores. Run Start-TestStack.ps1 first.

   .\scripts\test_env\Run-IsolatedBatches.ps1 -OutDir C:\Users\me\rag-test-evidence\run1
   .\scripts\test_env\Run-IsolatedBatches.ps1 -OutDir ... -Only B3,B5        # re-run some batches

 Optional tools (set in the caller): RAG_TEST_EXTRA_PATH (tesseract / poppler directories), RAG_TEST_TESSDATA (eng + fra).
 -Coverage: measures api/ with pytest-cov (--cov=api, the repo's [tool.coverage.run] from pyproject.toml, NO threshold) and keeps one data file per
 batch, <OutDir>\.coverage.<batch>, so that batches can be combined (`coverage combine`) in any subset. A batch whose data file is missing is
 reported in progress.txt as COVERAGE FILE MISSING.
 Output: <OutDir>\<batch>.xml / .txt / .files.txt and <OutDir>\progress.txt (exit code, duration and free memory per batch).
 A batch is never retried automatically: the first result is the result.
#>
param(
    [Parameter(Mandatory = $true)][string]$OutDir,
    [string[]]$Only = @(),
    [int]$MinFreeMB = 300,
    [switch]$Coverage
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root
New-Item -ItemType Directory -Force $OutDir | Out-Null
$tmp = Join-Path $env:LOCALAPPDATA 'Temp\rag-tests'
New-Item -ItemType Directory -Force $tmp | Out-Null
$env:TEMP = $tmp; $env:TMP = $tmp

$files = @()
foreach ($base in 'tests', 'tests_pipeline', 'sdks/python/tests') {
    if (Test-Path $base) { $files += Get-ChildItem $base -Recurse -File -Include 'test_*.py', '*_test.py' | ForEach-Object { $_.FullName.Substring($root.Length + 1).Replace('\', '/') } }
}
$files = $files | Sort-Object -Unique
$ciIgnored = @('sdks/python/tests/test_client.py', 'tests/test_agent.py', 'tests/test_injection_test_set.py', 'tests/test_integrations.py', 'tests/test_regression.py', 'tests/test_voice.py', 'tests_pipeline/test_retrieval.py')
$rules = [ordered]@{
    'B1' = { param($f) $f -like 'tests/backend/*' -or $f -like 'tests/docs/*' }
    'B2' = { param($f) $f -match '^tests/test_[a-c]' }
    'B3' = { param($f) $f -match '^tests/test_[d-i]' }
    'B4' = { param($f) $f -match '^tests/test_[j-o]' }
    'B5' = { param($f) $f -match '^tests/test_[p-r]' }
    'B6' = { param($f) $f -match '^tests/test_[s-z]' }
}
$assigned = @{}
$batches = [ordered]@{}
foreach ($name in $rules.Keys) {
    $batches[$name] = @($files | Where-Object { -not $assigned.ContainsKey($_) -and (& $rules[$name] $_) -and ($ciIgnored -notcontains $_) })
    foreach ($f in $batches[$name]) { $assigned[$f] = $name }
}
$batches['B7'] = @($files | Where-Object { -not $assigned.ContainsKey($_) -and ($ciIgnored -notcontains $_) })   # catch-all: nothing can be left out
foreach ($f in $batches['B7']) { $assigned[$f] = 'B7' }
$batches['B8'] = @($ciIgnored | Where-Object { $files -contains $_ })                                             # the files CI excludes with --ignore
$total = ($batches.Values | ForEach-Object { $_.Count } | Measure-Object -Sum).Sum
"files found: $($files.Count); in batches: $total" | Set-Content (Join-Path $OutDir 'batches.txt')
foreach ($name in $batches.Keys) { "$name : $($batches[$name].Count) files" | Add-Content (Join-Path $OutDir 'batches.txt'); $batches[$name] | Set-Content (Join-Path $OutDir "$name.files.txt") }
if ($total -ne $files.Count) { throw "batch construction lost or duplicated files ($total vs $($files.Count))" }

$progress = Join-Path $OutDir 'progress.txt'
foreach ($name in $batches.Keys) {
    if ($Only.Count -gt 0 -and $Only -notcontains $name) { continue }
    if ($batches[$name].Count -eq 0) { "$name skipped: no file" | Add-Content $progress; continue }
    for ($i = 0; $i -lt 20; $i++) {
        $free = [int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024)
        if ($free -ge $MinFreeMB) { break }
        "$name waiting: free memory $free MB < $MinFreeMB MB" | Add-Content $progress
        Start-Sleep 30
    }
    $started = Get-Date
    "$name start $($started.ToString('o')) files=$($batches[$name].Count) freeMB=$([int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024))" | Add-Content $progress
    $batchArgs = $batches[$name] + @('-p', 'no:cacheprovider', "--basetemp=$tmp\bt-$name", "--junitxml=$OutDir\$name.xml")
    if ($Coverage) {
        Remove-Item (Join-Path $root '.coverage') -ErrorAction SilentlyContinue   # a stale file would be mistaken for this batch's data
        $batchArgs += @('--cov=api', '--cov-report=')
    }
    & (Join-Path $PSScriptRoot 'Run-IsolatedSuite.ps1') -PytestArgs $batchArgs *>&1 | Out-File -Encoding utf8 (Join-Path $OutDir "$name.txt")
    $code = $LASTEXITCODE
    $secs = [int]((Get-Date) - $started).TotalSeconds
    "$name end exit=$code seconds=$secs freeMB=$([int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024))" | Add-Content $progress
    if ($Coverage) {
        $data = Join-Path $root '.coverage'
        if (Test-Path $data) { Move-Item $data (Join-Path $OutDir ".coverage.$name") -Force; "$name coverage data kept: .coverage.$name" | Add-Content $progress }
        else { "$name COVERAGE FILE MISSING" | Add-Content $progress }
    }
}
"all requested batches finished $((Get-Date).ToString('o'))" | Add-Content $progress
