# _d1_ib_state_probe.ps1 — есть ли в файловой ИБ конфигурация (и отчёты в ней).
#
# Повод: метка _ibcmd_work/ib_bp3/ckb_ibcmd_state.json говорит config_state="loaded",
# но config_source="inferred_from_layout" - это вывод из фактов разбора .erf, а не из
# успешного `config load` (правило R14: утверждает факт, а не файл). Факт проверяем здесь:
# имя конфигурации сеанса, число объектов отчётов и поиск конкретного отчёта.

$ErrorActionPreference = 'Continue'
$ib = 'C:\1C_LLM\ckb\_ibcmd_work\ib_bp3'

$connector = New-Object -ComObject V83.COMConnector
$session = $connector.Connect("File=`"$ib`";")
if (-not $session) { Write-Output 'connect: НЕ удалось'; exit 1 }
Write-Output 'connect: ок'

try {
    Write-Output ("  ИмяБазы = {0}" -f $session.('ИмяБазы'))
} catch {
    Write-Output ("  ИмяБазы: {0}" -f $_.Exception.Message)
}

$md = $session.('Метаданные')()
Write-Output ("Метаданные(): {0}" -f $md)

foreach ($prop in @('Имя', 'Name', 'Версия', 'Version')) {
    try { Write-Output ("  Метаданные().{0} = {1}" -f $prop, $md.($prop)) }
    catch { Write-Output ("  Метаданные().{0}: {1}" -f $prop, $_.Exception.Message) }
}

foreach ($call in @('Количество', 'Count')) {
    try { Write-Output ("  Метаданные().{0}() = {1}" -f $call, $md.($call)()) }
    catch { Write-Output ("  Метаданные().{0}(): {1}" -f $call, $_.Exception.Message) }
}

foreach ($full in @('Отчет.АнализЖурналаРегистрации', 'Report.АнализЖурналаРегистрации',
                    'Report.AnalysisOfEventLog')) {
    try { Write-Output ("  Метаданные().НайтиПоИмени({0}) -> {1}" -f $full, $md.('НайтиПоИмени')($full)) }
    catch { Write-Output ("  Метаданные().НайтиПоИмени({0}): {1}" -f $full, $_.Exception.Message) }
}

$reports = $md.('Отчеты')
foreach ($call in @('Количество', 'Count')) {
    try { Write-Output ("  Метаданные().Отчеты.{0}() = {1}" -f $call, $reports.($call)()) }
    catch { Write-Output ("  Метаданные().Отчеты.{0}(): {1}" -f $call, $_.Exception.Message) }
}
try { Write-Output ("  Метаданные().Отчеты.Count (свойство) = {0}" -f $reports.Count) }
catch { Write-Output ("  свойство Count: {0}" -f $_.Exception.Message) }

# отдельная проверка: доступна ли вообще хоть одна метаданная (число справочников)
$catalogs = $md.('Справочники')
foreach ($call in @('Количество', 'Count')) {
    try { Write-Output ("  Метаданные().Справочники.{0}() = {1}" -f $call, $catalogs.($call)()) }
    catch { Write-Output ("  Метаданные().Справочники.{0}(): {1}" -f $call, $_.Exception.Message) }
}

try { $session.('Закрыть')() } catch { }
Write-Output 'сеанс закрываем'
