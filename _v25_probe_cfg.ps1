$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$ibcmd = 'C:\Program Files\1cv8\8.3.27.1859\bin\ibcmd.exe'
$ib1 = 'C:\1C_LLM\ckb\_ibcmd_work\ib1'
$ibp = 'C:\1C_LLM\ckb\_ibcmd_work\ib_bp3'

Write-Output '=== config load отсутствующего .cf (ib1) ==='
& $ibcmd config --db-path $ib1 load 'C:\1C_LLM\LoadDoc\БП3\нет_такого.cf' 2>&1 | Select-Object -First 8
Write-Output "rc=$LASTEXITCODE"

Write-Output '=== generation-id ib1 (без конфигурации) ==='
& $ibcmd config --db-path $ib1 generation-id 2>&1 | Select-Object -First 5
Write-Output "rc=$LASTEXITCODE"

Write-Output '=== generation-id ib_bp3 (с конфигурацией) ==='
& $ibcmd config --db-path $ibp generation-id 2>&1 | Select-Object -First 5
Write-Output "rc=$LASTEXITCODE"

Write-Output '=== help config (синтаксис load) ==='
& $ibcmd help config 2>&1 | Select-Object -First 40
Write-Output "rc=$LASTEXITCODE"
