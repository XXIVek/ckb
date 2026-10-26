# _d1_direct_dot_probe.ps1 - приём из статьи записью через прямую точку.
#
# Почему снова проба: $session.('Отчеты').($name) (extended member syntax) для COM-объектов
# 1С работает ненадёжно - менеджер возвращается null, а «успешный» прогон _d1_bp3_dcs_probe.ps1
# оказался артефактом: Probe возвращал массив из строки лога и значения, дальше PowerShell
# применял вызовы к элементам массива. Прямая точка ($session.Отчеты.Имя) - то же, что в VBS
# из статьи, и PowerShell допускает кириллические имена членов.
#
# Если прямая точка даёт объект - читаем вариант настроек и параметры (Значение/Использование).

$ErrorActionPreference = 'Stop'
$ib = 'C:\1C_LLM\Bases_Test\BP3'

$connector = New-Object -ComObject V83.COMConnector
$session = $connector.Connect("File=`"$ib`";Usr=admin;Pwd=;")
Write-Output 'сеанс: открыт'

try {
    $manager = $session.Отчеты.АнализЖурналаРегистрации
    Write-Output ("менеджер: {0}" -f $manager.GetType().Name)

    $report = $manager.Создать()
    Write-Output ("объект отчёта: {0}" -f $report.GetType().Name)

    $schema = $report.ОсновнойМакет.СхемаКомпоновкиДанных
    Write-Output ("схема СКД: {0}" -f $schema.GetType().Name)
    Write-Output ("параметров схемы: {0}" -f $schema.Параметры.Количество())

    foreach ($variant in $schema.ВариантыНастроек) {
        Write-Output ("=== вариант: {0}" -f $variant.Имя)
        $count = 0
        foreach ($p in $variant.Настройки.Параметры) {
            $count++
            $value = $p.Значение
            $vtext = [string]$value
            if ($vtext.Length -gt 100) { $vtext = $vtext.Substring(0, 100) }
            $type = ''
            try { $type = $value.ТипЗначения().ПолноеИмя() } catch { }
            Write-Output ("    * {0}: Использование={1} Значение={2} тип={3}" -f `
                $p.Имя, $p.Использование, $vtext, $type)
        }
        Write-Output "    параметров: $count"
    }

    $composer = $report.КомпоновщикНастройки
    Write-Output '=== компоновщик настроек после применения варианта «Основной» ==='
    $variantMain = $null
    foreach ($variant in $schema.ВариантыНастроек) {
        if ($variant.Имя -eq 'Основной') { $variantMain = $variant; break }
    }
    if ($variantMain) {
        $composer.Настройки.Заполнить($variantMain.Настройки)
        Write-Output 'Заполнить(вариант.Настройки): выполнено'
        foreach ($p in $composer.Настройки.Параметры) {
            $value = $p.Значение
            $vtext = [string]$value
            if ($vtext.Length -gt 100) { $vtext = $vtext.Substring(0, 100) }
            Write-Output ("    * {0}: Использование={1} Значение={2}" -f `
                $p.Имя, $p.Использование, $vtext)
        }
    }
}
catch {
    Write-Output ("ОШИБКА: " + $_.Exception.Message)
}
finally {
    try { $session.Закрыть() } catch { Write-Output ('Закрыть: ' + $_.Exception.Message) }
    foreach ($obj in @($session, $connector)) {
        if ($obj) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($obj) }
    }
    [GC]::Collect() | Out-Null
    [GC]::WaitForPendingFinalizers()
    [GC]::Collect() | Out-Null
    Write-Output 'сеанс закрыт, COM освобождён'
}
