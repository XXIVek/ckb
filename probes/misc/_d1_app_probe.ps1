# _d1_app_probe.ps1 - проверка Automation-сервера V83.Application и CodeEvaluation.
#
# Зачем: через IDispatch имена 1С разрешаются непоследовательно (pywin32 видит только
# английские, PowerShell - русские свойства, но не методы: «Закрыть» не найден, имена
# вариантов настроек пустые). Automation-сервер даёт метод CodeEvaluation(Код), то есть
# измерение пишется на встроенном языке целиком, и резолвить имена метаданных в COM не нужно.
#
# Проверяем по шагам: регистрация класса -> Connect -> Visible -> CodeEvaluation("1+1")
# (семантика возврата) -> короткий отчёт о конфигурации и о варианте настроек отчёта.

$ErrorActionPreference = 'Continue'
$ib = 'C:\1C_LLM\Bases_Test\BP3'

Write-Output '--- регистрация V83.Application'
$reg = Get-ItemProperty 'HKLM:\SOFTWARE\Classes\V83.Application\CLSID' -ErrorAction SilentlyContinue
if (-not $reg) { $reg = Get-ItemProperty 'HKCU:\SOFTWARE\Classes\V83.Application\CLSID' -ErrorAction SilentlyContinue }
if (-not $reg) { Write-Output '  V83.Application НЕ зарегистрирован'; exit 1 }
$clsid = $reg.'(default)'
Write-Output "  CLSID = $clsid"
$inproc = Get-ItemProperty "HKLM:\SOFTWARE\Classes\CLSID\$clsid\LocalServer32" -ErrorAction SilentlyContinue
if (-not $inproc) { $inproc = Get-ItemProperty "HKLM:\SOFTWARE\Classes\CLSID\$clsid\InprocServer32" -ErrorAction SilentlyContinue }
Write-Output ("  сервер = " + $inproc.'(default)')

Write-Output '--- создание и подключение'
$app = New-Object -ComObject V83.Application
if (-not $app) { Write-Output '  не создан'; exit 1 }
try {
    $app.Connect("File=`"$ib`";Usr=admin;Pwd=;")
    Write-Output '  Connect: ок'
} catch {
    Write-Output ("  Connect: " + $_.Exception.Message); exit 1
}
try { $app.Visible = $false; Write-Output '  Visible=false: ок' }
catch { Write-Output ('  Visible: ' + $_.Exception.Message) }

Write-Output '--- поиск доступного способа выполнить код на встроенном языке'
$evalMethod = $null
foreach ($name in @('Eval', 'CodeEvaluation', 'ExecCode', 'RunCode', 'Evaluate')) {
    try {
        $result = $app.($name)('1+1')
        Write-Output ("  [OK  ] {0}('1+1') -> {1}" -f $name, $result)
        $evalMethod = $name
        break
    }
    catch {
        Write-Output ("  [FAIL] {0}: {1}" -f $name, $_.Exception.Message)
    }
}
if (-not $evalMethod) {
    try { $app.Quit() } catch { }
    exit 1
}

Write-Output '--- отчёт о конфигурации и варианте настроек (код на BSL)'
$code = @'
Отчет = Новый Массив;
Мета = Метаданные();
Отчет.Добавить("Метаданные=" + ?(Мета = Неопределено, "нет", Мета.Имя));
Отчет.Добавить("Отчетов=" + Строка(Мета.Отчеты.Количество()));
Отчет.Добавить("ИщемОтчет=" + ?(Мета.Найти("Отчет.АнализЖурналаРегистрации") = Неопределено, "нет", "есть"));
Отчет.Добавить("ТипСКД=" + ?(Тип("СхемаКомпоновкиДанных") = Неопределено, "нет", "есть"));
Рез = "";
Для Каждого СтрокаОтчета Из Отчет Цикл
    Рез = Рез + СтрокаОтчета + " | ";
КонецЦикла;
Рез;
'@
try { Write-Output ("  [{0}] -> {1}" -f $evalMethod, $app.($evalMethod)($code)) }
catch { Write-Output ("  {0}(отчёт): {1}" -f $evalMethod, $_.Exception.Message) }

try { $app.Quit() } catch { }
Write-Output '  Quit выполнен'
