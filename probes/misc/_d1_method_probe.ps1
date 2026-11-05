# _d1_method_probe.ps1 - замер: какие имена членов видит PowerShell на COM-сессии 1С.
#
# Зачем. tools/probe_d1_dcs.ps1 открыл сеанс, но $session.ВнешниеОтчёты вернул null, а
# $session.Закрыть дал «[System.__ComObject] не содержит метод». Тот же отказ, что и у
# pywin32 (session.ИмяБазы -> AttributeError). Нужно установить, видит хоть один транспорт
# русские имена BSL, или оба видят только английские - от этого зависит, чем вообще
# измерять D1, и это нельзя решать «на глаз» по одному сообщению об ошибке.
#
# Замер: одна и та же сессия, имя вызывается в двух записях (русской и английской).
# Результат печатается построчно: OK с типом/значением либо ERR с текстом.

$ErrorActionPreference = 'Continue'
$ib = 'C:\1C_LLM\ckb\_ibcmd_work\ib_bp3'

function Probe($obj, [string]$name) {
    if ($null -eq $obj) { Write-Output ("  SKIP {0} : объект null" -f $name); return }
    try {
        $value = $obj.($name)
        if ($null -eq $value) {
            Write-Output ("  NULL {0} : свойство не найдено либо значение null" -f $name)
            return
        }
        $type = ''
        try { $type = $value.GetType().FullName } catch { }
        Write-Output ("  OK   {0} : {1}" -f $name, $type)
    } catch {
        Write-Output ("  ERR  {0} : {1}" -f $name, $_.Exception.Message)
    }
}

$connector = New-Object -ComObject V83.COMConnector
Write-Output ("connector: {0}" -f $connector.GetType().FullName)
$session = $connector.Connect("File=`"$ib`";")
if ($null -eq $session) {
    Write-Output 'connect: ВЕРНУЛ null - сеанса нет'
    exit 2
}
Write-Output ("connect: объект {0}" -f $session.GetType().FullName)

foreach ($name in @('NameIBase', 'ИмяБазы', 'CommonAttributes', 'ОбщиеАтрибуты',
                    'Reports', 'Отчеты', 'ExternalReports', 'ВнешниеОтчеты',
                    'Close', 'Закрыть')) {
    Probe $session $name
}

# Reflection-путь: InvokeMember идёт через тот же IDispatch, но имя передаётся строкой
# явно - проверяем, не теряется ли кириллица до обращения к диспатчу.
foreach ($name in @('Close', 'Закрыть')) {
    try {
        $r = $session.GetType().InvokeMember($name, 'InvokeMethod', $null, $session, @())
        Write-Output ("  OK   InvokeMember {0} : {1}" -f $name, $r)
    } catch {
        Write-Output ("  ERR  InvokeMember {0} : {1}" -f $name, $_.Exception.Message)
    }
}
exit 0