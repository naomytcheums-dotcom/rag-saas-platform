<#
 Removes the throw-away test stack (containers and their data). Only containers named <prefix>-pg / -redis / -minio are touched.
#>
param([string]$Prefix = 'rag-test')
foreach ($suffix in 'pg', 'redis', 'minio') {
    $name = "$Prefix-$suffix"
    if (docker ps -a --filter "name=^/$name$" --format '{{.Names}}') { docker rm -f $name | Out-Null; Write-Host "removed $name" }
}
Remove-Item (Join-Path $PSScriptRoot '.stack.env') -ErrorAction SilentlyContinue
