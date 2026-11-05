# _d1_names_enum.ps1 - карта имён IDispatch для варианта настроек СКД.
#
# Что уже измерено: $schema.('ВариантыНастройки') возвращает коллекцию (3 варианта), но
# $v.('Имя') даёт пусто, а $session.('Закрыть')() - «не содержит метод». Значит часть имён
# доступна в английской записи. Здесь для одного объекта перебираем обе записи и печатаем,
# что реально резолвится - это карта для рабочего замера.

$ErrorActionPreference = 'Continue'
$ib = 'C:\1C_LLM\Bases_Test\BP3'
$reportName = 'АнализЖурналаРегистрации'

function TryMember($obj, $name) {
    try {
        $value = $obj.($name)
        $text = [string]$value
        if ($text.Length -gt 120) { $text = $text.Substring(0, 120) }
        Write-Output ("    [OK  ] {0} -> {1} ({2})" -f $name, $text, $value.GetType().Name)
        return $value
    }
    catch {
        Write-Output ("    [FAIL] {0}: {1}" -f $name, $_.Exception.Message)
        return $null
    }
}

$connector = New-Object -ComObject V83.COMConnector
$session = $connector.Connect("File=`"$ib`";Usr=admin;Pwd=;")

# Метаданные() через внешнее соединение содержимого не даёт (имя пустое, Reports.Count=0),
# зато прямое обращение к менеджеру работает - ровно так, как написано в статье.
$manager = $session.('Отчеты').($reportName)
if (-not $manager) { $manager = $session.('Reports').($reportName) }
if (-not $manager) { Write-Output 'менеджер отчёта не получен'; exit 1 }
Write-Output 'менеджер отчёта: получен'

$report = $manager.('Create')()
if (-not $report) { $report = $manager.('Создать')() }
if (-not $report) { Write-Output 'объект отчёта не получен'; exit 1 }
Write-Output 'объект отчёта: получен'

$schema = $report.('MainLayout').('DataCompositionSchema')
if (-not $schema) { $schema = $report.('ОсновнойМакет').('СхемаКомпоновкиДанных') }
if (-not $schema) { Write-Output 'схема не получена'; exit 1 }
Write-Output 'схема СКД: получена'

$variants = $schema.('SettingsSets')
if (-not $variants) { $variants = $schema.('ВариантыНастройки') }
Write-Output ("вариантов: {0}" -f @($variants).Count)

$index = 0
foreach ($v in $variants) {
    $index++
    Write-Output ""
    Write-Output ("=== вариант #{0}: карта имён" -f $index)
    foreach ($name in @('Имя', 'Name', 'Представление', 'Description', 'Настройки', 'Settings')) {
        TryMember $v $name | Out-Null
    }
    $settings = $null
    foreach ($sn in @('Настройки', 'Settings')) {
        try { $settings = $v.($sn) } catch { continue }
        if ($settings) { Write-Output "    настройки получены через $sn"; break }
    }
    if (-not $settings) { break }
    $params = $null
    foreach ($pn in @('Параметры', 'Parameters')) {
        try { $params = $settings.($pn) } catch { continue }
        if ($params) { Write-Output "    параметры получены через $pn"; break }
    }
    if (-not $params) { break }
    foreach ($p in $params) {
        Write-Output "    --- карта имён первого параметра"
        foreach ($name in @('Имя', 'Name', 'Значение', 'Value', 'Использование', 'Use',
                            'Представление', 'Presentation')) {
            TryMember $p $name | Out-Null
        }
        break
    }
    break
}

foreach ($name in @('Close', 'Закрыть')) {
    try { $session.($name)(); Write-Output "  сеанс закрыт через $name"; break }
    catch { Write-Output ("  {0}: {1}" -f $name, $_.Exception.Message) }
}
# Освобождение COM обязательно: без ReleaseComObject процесс 1cv8 -Embedding остаётся
# висеть и держит файловую ИБ - следующие сеансы ведут себя непредсказуемо (замер
# 19.10.2026: два осиротевших процесса по ~1 ГБ после прогонов без освобождения).
foreach ($obj in @($manager, $report, $schema, $variants, $session, $connector)) {
    if ($obj) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($obj) }
}
[GC]::Collect() | Out-Null
[GC]::WaitForPendingFinalizers()
[GC]::Collect() | Out-Null
Write-Output 'COM освобождён'
