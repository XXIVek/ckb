# _d1_com_names_probe.ps1 — какие имена реально отдаёт COM-сеанс внешней базы.
#
# Основание: приём из статьи («Connection.Reports.<Имя>», «ReportObject.СкомпоноватьРезультат»)
# не воспроизводится ни в pywin32 (DISP_E_MEMBERNOTFOUND на session.Отчеты.<Имя>),
# ни в VBScript (лексер VBScript не принимает кириллические идентификаторы - «Недопустимый
# знак» на mgr.Создать()). PowerShell обращается к члену по имени из строки ($o.('Имя')),
# поэтому здесь можно замерить, какие имена доступны: русские, английские или оба.
#
# Только чтение; сеанс закрывается.

$ErrorActionPreference = 'Continue'
$ib = 'C:\1C_LLM\ckb\_ibcmd_work\ib_bp3'

$connector = New-Object -ComObject V83.COMConnector
$session = $connector.Connect("File=`"$ib`";")
if (-not $session) { Write-Output 'connect: НЕ удалось'; exit 1 }
Write-Output 'connect: ок'

$names = @('Метаданные', 'Metadata', 'Отчеты', 'Reports', 'ИмяБазы', 'NameIBase',
           'ПолучитьИмяБазы', 'УстановитьБезопасныйРежим', 'Закрыть', 'Close')

Write-Output '--- обращение к члену по имени (без явного вызова)'
foreach ($name in $names) {
    try {
        $value = $session.($name)
        $text = Out-String -InputObject $value
        if ($text) { $text = $text.Trim() }
        if ($text.Length -gt 160) { $text = $text.Substring(0, 160) }
        Write-Output ("  [OK  ] {0} -> {1}" -f $name, $text)
    }
    catch {
        Write-Output ("  [FAIL] {0} -> {1}" -f $name, $_.Exception.Message)
    }
}

Write-Output '--- вызов по имени как метода (Метаданные/Metadata)'
foreach ($name in @('Метаданные', 'Metadata')) {
    try {
        $md = $session.($name)()
        Write-Output ("  [OK  ] {0}() -> {1}" -f $name, $md)
        foreach ($prop in @('Отчеты', 'Reports')) {
            try {
                $reports = $md.($prop)
                Write-Output ("        {0}.{1}: получено, Count={2}" -f $name, $prop, $reports.Count)
                $found = $reports.('НайтиПоИмени')('АнализЖурналаРегистрации')
                Write-Output ("        НайтиПоИмени(АнализЖурналаРегистрации) -> {0}" -f $found)
            }
            catch {
                Write-Output ("        {0}.{1}: {2}" -f $name, $prop, $_.Exception.Message)
            }
        }
    }
    catch {
        Write-Output ("  [FAIL] {0}() -> {1}" -f $name, $_.Exception.Message)
    }
}

try { $session.('Закрыть')() } catch { }
try { $session.('Close')() } catch { }
Write-Output 'сеанс закрываем'
