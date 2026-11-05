# _d1_bp3_dcs_probe.ps1 - вариант настроек встроенного отчёта на реальной базе БП3.
#
# Площадка (дана оператором 19.10.2026): файловая ИБ C:\1C_LLM\Bases_Test\BP3, наполненная,
# конфигурация снята с поддержки, пользователь admin без пароля.
#
# Язык стенда - PowerShell. Причина выбора измерена 19.10.2026:
#   * pywin32 резолвит у COM-объекта 1С только английские имена: session.Метаданные() даёт
#     DISP_E_MEMBERNOTFOUND и на наполненной базе (_d1_bp3_dcs_probe.py);
#   * VBScript не принимает кириллические идентификаторы лексером («Недопустимый знак»);
#   * PowerShell обращается к члену по имени из строки ($o.('Имя')) и русские имена видит.
#
# Приём - из статьи «Как запустить встроенный отчет ... без изменения конфигурации»:
# внешнее соединение даёт доступ к менеджерам метаданных, внешнего файла нет, значит диалога
# безопасности нет.
#
# Предмет: Отчет.АнализЖурналаРегистрации, вариант «Основной» - в макете найден параметр
# Пользователь со значением dcscor:DesignTimeValue и <dcsset:use>false</dcsset:use>.
# Вопрос: сохраняет ли платформа ЗНАЧЕНИЕ параметра при использовании = ложь.

$ErrorActionPreference = 'Continue'
$ib = 'C:\1C_LLM\Bases_Test\BP3'
$reportName = 'АнализЖурналаРегистрации'
$variantName = 'Основной'

function Probe($label, [scriptblock]$body) {
    try {
        $value = & $body
        $text = Out-String -InputObject $value
        if ($text) { $text = $text.Trim() }
        if ($text.Length -gt 200) { $text = $text.Substring(0, 200) }
        Write-Output ("  [OK  ] {0} -> {1}" -f $label, $text)
        return $value
    }
    catch {
        Write-Output ("  [FAIL] {0} -> {1}" -f $label, $_.Exception.Message)
        return $null
    }
}

function DumpParams($settings, $title) {
    Write-Output "  --- $title"
    if (-not $settings) { Write-Output '    объект настроек не получен'; return }
    $params = Probe 'Настройки.Параметры' { $settings.('Параметры') }
    if (-not $params) { return }
    $count = 0
    foreach ($p in $params) {
        $count++
        $name = $p.('Имя')
        $use = try { $p.('Использование') } catch { '<ошибка>' }
        $value = try { $p.('Значение') } catch { '<ошибка>' }
        $type = try { $p.('Значение').('ТипЗначения')() } catch { '' }
        $vtext = [string]$value
        if ($vtext.Length -gt 120) { $vtext = $vtext.Substring(0, 120) }
        Write-Output ("    * {0}: Использование={1} Значение={2} тип={3}" -f $name, $use, $vtext, $type)
    }
    Write-Output "    параметров: $count"
}

$connector = New-Object -ComObject V83.COMConnector
$session = $connector.Connect("File=`"$ib`";Usr=admin;Pwd=;")
if (-not $session) { Write-Output 'connect: НЕ удалось'; exit 1 }
Write-Output '=== сеанс и конфигурация ==='
Probe 'session.ИмяБазы' { $session.('ИмяБазы') } | Out-Null
$md = Probe 'session.Метаданные()' { $session.('Метаданные')() }
if (-not $md) { exit 1 }
Probe 'Метаданные().Имя' { $md.('Имя') } | Out-Null
Probe 'Метаданные().Версия' { $md.('Версия') } | Out-Null
Probe 'Метаданные().Отчеты.Count' { $md.('Отчеты').Count } | Out-Null
Probe ("Метаданные().НайтиПоИмени('Отчет.{0}')" -f $reportName) {
    $md.('НайтиПоИмени')(("Отчет.{0}" -f $reportName))
} | Out-Null

Write-Output ''
Write-Output '=== объект отчёта через менеджер (приём из статьи) ==='
$manager = Probe ("session.Отчеты.{0}" -f $reportName) { $session.('Отчеты').($reportName) }
if (-not $manager) { $session.('Закрыть')(); exit 1 }
$report = Probe 'менеджер.Создать()' { $manager.('Создать')() }
if (-not $report) { $session.('Закрыть')(); exit 1 }

Write-Output ''
Write-Output '=== схема и варианты настроек ==='
$schema = Probe 'ОсновнойМакет.СхемаКомпоновкиДанных' { $report.('ОсновнойМакет').('СхемаКомпоновкиДанных') }
if (-not $schema) { $session.('Закрыть')(); exit 1 }
$variants = Probe 'СхемаКомпоновкиДанных.ВариантыНастроек' { $schema.('ВариантыНастроек') }
if (-not $variants) { $session.('Закрыть')(); exit 1 }
foreach ($v in $variants) { Write-Output ("    вариант: {0}" -f $v.('Имя')) }

$target = $null
foreach ($v in $variants) { if ($v.('Имя') -eq $variantName) { $target = $v; break } }
if (-not $target) { Write-Output "    вариант $($variantName) не найден"; $session.('Закрыть')(); exit 1 }

Write-Output ''
Write-Output ("=== настройки варианта {0} (как их держит платформа) ===" -f $variantName)
DumpParams (Probe 'вариант.Настройки' { $target.('Настройки') }) 'вариант.Настройки'

Write-Output ''
Write-Output '=== компоновщик настроек отчётного объекта ==='
$composer = Probe 'report.КомпоновщикНастройки' { $report.('КомпоновщикНастройки') }
if ($composer) {
    DumpParams (Probe 'КомпоновщикНастройки.Настройки' { $composer.('Настройки') }) 'до применения варианта'
    Probe 'Настройки.Заполнить(вариант.Настройки)' { $composer.('Настройки').('Заполнить')($target.('Настройки')) } | Out-Null
    DumpParams (Probe 'КомпоновщикНастройки.Настройки' { $composer.('Настройки') }) 'после применения варианта'
}

try { $session.('Закрыть')() } catch { }
Write-Output ''
Write-Output 'сеанс закрыт'
