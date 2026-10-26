# tools/probe_d1_dcs.ps1 - измерение D1 (СКД: DesignTimeValue -> фактическое значение)
# на COM против реальной информационной базы.
#
# Зачем. Профиль параметра СКД зафиксирован по XSD (xsd-docs/14-settings.md:341-343):
# использование по умолчанию = Истина, при Ложь значение НЕ передаётся в запрос. Но
# «не передаётся» означает «параметр запроса не инициализирован» или «подставляется
# DesignTimeValue» — в схеме компоновки это разные вещи, а на них держится пункт D1
# (EXTERNAL_OBJECT_EDIT_PLAN.md п. 28-29): если бы значение подставлялось, правка
# &Параметр в запросе макета не требовала бы правки значения в параметрах.
#
# Почему PowerShell, а не pywin32 (замер 19.10.2026): pywin32 резолвит у COM-объекта 1С
# только английские имена - session.ИмяБазы даёт AttributeError. BSL-интерфейс отчёта
# (ОсновнаяСхемаКомпоновкиДанных, КомпоновщикНастроек, ПараметрыДанных) по-русски, поэтому
# зонд идёт через pwsh 7 (он читает UTF-8 без BOM и допускает кириллические имена членов).
# Прежний прогон _d1_direct_dot_probe.ps1 в Windows PowerShell 5.1 был артефактом: 5.1
# читает файл как ANSI, кириллица в исходнике превращается в mojibake и скрипт не парсится.
#
# Площадка (решение 19.10.2026): не MinCfg, а BP3. MinCfg - фикстура формы и макета,
# она не загружена ни в одну живую ИБ; D1 измеряется только там, где СКД исполняется.
# ИБ - _ibcmd_work/ib_bp3 (в ней загружена конфигурация БП3, поэтому cfg:-типы разбора
# живые), объект - готовые .erf из C:\1C_LLM\LoadDoc\БП3. Строка подключения без
# пользователя: ИБ создавалась ibcmd под сеанс без аутентификации (замер: File="<иб>";
# даёт сеанс, Usr=/Pwd= с именем - отказ).
#
# Что меряет, по слоям (каждый включается отдельно, отказ одного не снимает вердикт по
# остальным):
#   L0  - запрос с &Параметр: инициализирован ли параметр запроса до исполнения;
#   L1  - параметры ВАР->НАСТ->ПАРАМ->СКД на живом объекте отчёта (то, что читает
#         DcsReader) плюс параметры схемы и параметры запроса;
#   L2  - КОМПО->ВЫПОЛН->ВЫРАЖ->ЗНАЧЕНИЕ: что в Параметрах макета после
#         CompositorLayout.Выполнить без применения варианта настроек;
#   L3 (--run) - полный цикл: ПараметрыДанных.Установить -> ПроцессорКомпоновки.Выполнить
#         -> число строк. Отвечает на вопрос «исполняется ли отчёт без правки».
#
# Формат вывода - маркерные строки (читаю их глазами, не парсером):
#   PARAM | имя | значение | Использование | тип | literal
#   LAYOUT_PARAM | имя | значение | Использование | тип | literal
#   QUERY_PARAM | имя
#   PARAM_VALUE | имя | literal
#   RESULT_ROWS | N
#   VERDICT D1=confirmed|refuted|undetermined - <причина>
#
# Запуск (только pwsh 7):
#   pwsh -NoProfile -ExecutionPolicy Bypass -File tools/probe_d1_dcs.ps1
#   pwsh -NoProfile -ExecutionPolicy Bypass -File tools/probe_d1_dcs.ps1 -Run
#   pwsh ... -IbPath <каталог ИБ> -Erf <путь к .erf>
# Выход: tools/_d1_dcs_probe_out.txt (UTF-8). Код возврата 0, если вердикт получен.

[CmdletBinding()]
param(
    [string]$IbPath = 'C:\1C_LLM\ckb\_ibcmd_work\ib_bp3',
    [string]$Erf = '',
    [string]$User = '',
    [string]$Password = '',
    [switch]$Run,
    [string]$OutFile = 'C:\1C_LLM\ckb\tools\_d1_dcs_probe_out.txt'
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$script:lines = [System.Collections.Generic.List[string]]::new()
function Say([string]$text) {
    Write-Output $text
    $script:lines.Add($text)
}
function ValueText($value) {
    if ($null -eq $value) { return '<null>' }
    $text = [string]$value
    if ($text.Length -gt 120) { return $text.Substring(0, 120) + '…' }
    return $text
}
function TypeFullName($value) {
    if ($null -eq $value) { return '' }
    try { return $value.ТипЗначения().ПолноеИмя() } catch { return '' }
}
function Describe-Parameters($parameters, [string]$marker) {
    # Обход коллекции параметров настроек (SettingsParameter): имя, значение,
    # Использование, тип значения и литерал внутри значения (Значение.Значение).
    $count = 0
    if ($null -eq $parameters) { Say "  $marker : коллекции нет"; return 0 }
    foreach ($p in $parameters) {
        $count++
        $name = ''
        try { $name = [string]$p.Имя } catch { }
        $value = $null
        try { $value = $p.Значение } catch { }
        $use = ''
        try { $use = [string]$p.Использование } catch { }
        $literal = ''
        try {
            $inner = $value.Значение
            if ($null -ne $inner) { $literal = ValueText $inner }
        } catch { }
        Say ("{0} | {1} | {2} | {3} | {4} | {5}" -f $marker, $name, (ValueText $value),
            $use, (TypeFullName $value), $literal)
    }
    Say "  $marker : всего $count"
    return $count
}

Say '=== ZONDE D1 (COM / PowerShell) ==='
if (-not (Test-Path -LiteralPath $IbPath)) {
    Say ("sqdb: каталог не найден: {0}" -f $IbPath)
    Set-Content -LiteralPath $OutFile -Value $script:lines -Encoding utf8
    exit 2
}

$targets = @()
if ($Erf) { $targets += $Erf }
else {
    $dir = 'C:\1C_LLM\LoadDoc\БП3'
    if (Test-Path -LiteralPath $dir) {
        foreach ($f in (Get-ChildItem -LiteralPath $dir -Filter '*.erf' | Select-Object -First 3)) {
            $targets += $f.FullName
        }
    }
}
if (-not $targets) {
    Say 'erf: ни одного .erf не найдено - D1 без объекта отчёта не измеряется'
    Set-Content -LiteralPath $OutFile -Value $script:lines -Encoding utf8
    exit 2
}

$connString = 'File="{0}";' -f $IbPath
if ($User) { $connString = 'File="{0}";Usr={1};Pwd={2};' -f $IbPath, $User, $Password }
$session = $null
try {
    $connector = New-Object -ComObject V83.COMConnector
    $session = $connector.Connect($connString)
    Say 'sqdb: сеанс открыт'
} catch {
    Say ("sqdb: ОТКАЗ подключения: {0}" -f $_.Exception.Message)
    Say 'VERDICT D1=undetermined - сеанс не открыт, измерять не на чём'
    Set-Content -LiteralPath $OutFile -Value $script:lines -Encoding utf8
    exit 1
}

try {
    foreach ($file in $targets) {
        Say ''
        Say ("=== OTCHET: {0} ===" -f $file)
        $report = $null
        try { $report = $session.ВнешниеОтчеты.Загрузить($file) } catch {
            Say ("L1: ОТКАЗ загрузки: {0}" -f $_.Exception.Message)
        }
        if ($null -eq $report) { Say 'L1: объект отчёта не получен'; continue }
        Say 'L1: объект отчёта загружен'

        $schema = $null
        try { $schema = $report.ОсновнаяСхемаКомпоновкиДанных } catch { }
        if ($null -eq $schema) {
            try { $schema = $report.ОсновнойМакет.СхемаКомпоновкиДанных } catch { }
        }
        if ($null -eq $schema) { Say 'L1: схема компоновки данных не получена'; continue }
        Say 'L1: схема компоновки данных получена'

        Say '--- L1a: параметры схемы ---'
        Describe-Parameters $schema.Параметры 'PARAM' | Out-Null

        Say '--- L1b: варианты настроек ---'
        $variantCount = 0
        foreach ($variant in $schema.ВариантыНастройки) {
            $variantCount++
            $vname = ''
            try { $vname = [string]$variant.Имя } catch { }
            Say ("variant: {0}" -f $vname)
            Describe-Parameters $variant.Настройки.Параметры 'PARAM' | Out-Null
        }
        Say ("variant: всего $variantCount")

        Say '--- L1c: параметры запроса отчёта ---'
        try {
            foreach ($p in $report.Запрос.Параметры) {
                $n = ''
                try { $n = [string]$p.Имя } catch { }
                Say ("QUERY_PARAM | {0}" -f $n)
            }
        } catch { Say ('QUERY_PARAM: параметров запроса нет: ' + $_.Exception.Message) }

        Say '--- L2: КомпоновщикМакета.Выполнить без применения настроек ---'
        try {
            $settings = $schema.ВариантыНастройки[0].Настройки
            $layout = $report.КомпоновщикМакета.Выполнить($schema, $settings)
            Describe-Parameters $layout.Параметры 'LAYOUT_PARAM' | Out-Null
        } catch { Say ('L2: ОТКАЗ: ' + $_.Exception.Message) }

        if ($Run) {
            Say '--- L3: Полный цикл (ПроцессорКомпоновки.Выполнить) ---'
            try {
                $sc = $report.КомпоновщикНастроек
                if ($schema.ВариантыНастройки.Count -gt 0) {
                    $sc.Настройки.Заполнить($schema.ВариантыНастройки[0].Настройки)
                }
                $result = $report.ПроцессорКомпоновки.Выполнить($sc.Настройки, $schema.ПараметрыДанных)
                $rows = 0
                try { $rows = $result.Выгрузить().Количество() } catch { }
                Say ("RESULT_ROWS | {0}" -f $rows)
            } catch { Say ('L3: ОТКАЗ: ' + $_.Exception.Message) }
        }
    }
} catch {
    Say ("ОШИБКА: {0}" -f $_.Exception.Message)
} finally {
    if ($session) { try { $session.Закрыть() } catch { Say ('Закрыть: ' + $_.Exception.Message) } }
    [GC]::Collect() | Out-Null
    [GC]::WaitForPendingFinalizers()
    Say 'sqdb: сеанс закрыт'
}

$marked = @($script:lines | Where-Object { $_ -like 'PARAM |*' -or $_ -like 'LAYOUT_PARAM |*' })
$withLiteral = @($marked | Where-Object { $_ -match '\| (0|Ложь|False) \|' -and $_ -notmatch '\|\s*$' })
$verdict = 'undetermined'
$reason = 'нет ни одного параметра с литералом значения при Использование=Ложь'
if ($withLiteral.Count -gt 0) {
    $verdict = 'confirmed'
    $reason = ('параметров с Использование=Ложь и заполненным значением: {0}' -f $withLiteral.Count)
} elseif ($marked.Count -eq 0) {
    $reason = 'ни одного параметра настроек не получено'
}
Say ("VERDICT D1={0} - {1}" -f $verdict, $reason)

Set-Content -LiteralPath $OutFile -Value $script:lines -Encoding utf8
Write-Output ("log: {0}" -f $OutFile)
if ($verdict -eq 'undetermined') { exit 1 }
exit 0