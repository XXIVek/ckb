# _v52_p6_run_probes.ps1 — последовательный прогон проб остановки/продолжения (узел V52, шаг П5).
# Прогоны, меняющие общую БД, не параллелят (наблюдение П8 узла V50) — поэтому один цикл.
$env:PYTHONIOENCODING = 'utf-8'
Set-Location 'c:\1C_LLM\ckb'
foreach ($p in @('_v48_p8_stop_probe.py', '_v49_p8_stop_probe.py', '_v50_p8_stop_probe.py',
                 '_v51_p8_stop_probe.py', '_v51_p8_resume_probe.py')) {
    $base = $p -replace '\.py$', ''
    python $p MinCfg > "_out__v52_p6_$base.txt" 2> "_out__v52_p6_$base.err.txt"
    Set-Content -Path "_out__v52_p6_$base.rc.txt" -Value $LASTEXITCODE
}
Set-Content -Path '_out__v52_p6_all.done.txt' -Value 'done'
