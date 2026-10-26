# -*- coding: utf-8 -*-
r"""_d1_vbs_probe.py — проба способа из статьи штатным средством: cscript + VBScript.

Причина: в pywin32 динамическое имя метаданного через IDispatch не разрешается
(DISP_E_MEMBERNOTFOUND на session.Отчеты.<Имя> и на НайтиПоИмени), а в статье приём
описан на VBScript, где обращение Connection.Reports.<Имя> работает за счёт позднего
связывания. Значит проверять надо тем же языком, каким написан эталонный пример.

VBS пишется в cp1251: cscript читает .vbs в кодовой странице системы (ru), UTF-8 без
BOM дал бы битые кириллические идентификаторы.

Предмет - отчёт АнализЖурналаРегистрации: в его макете найден параметр Пользователь со
значением dcscor:DesignTimeValue и use=false (замер _d1_settings_items.py).
"""
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

VBS_PATH = r"C:\1C_LLM\ckb\_d1_builtin_probe.vbs"
IB = r"C:\1C_LLM\ckb\_ibcmd_work\ib_bp3"

VBS = r'''
Option Explicit
Dim conn, mgr, rep, lay, sk, vs, v, pr, name
Set conn = CreateObject("V83.COMConnector").Connect("File=""%IB%"";")
If Err.Number <> 0 Then
    WScript.Echo "Connect: " & Err.Description
    WScript.Quit 1
End If
WScript.Echo "сеанс: ок"
On Error Resume Next
Execute "Set mgr = conn.Отчеты.АнализЖурналаРегистрации"
If Err.Number <> 0 Then
    WScript.Echo "Отчеты.АнализЖурналаРегистрации: " & Err.Description
    Err.Clear
Else
    WScript.Echo "менеджер отчета: ок"
    Set rep = mgr.Создать()
    If Err.Number <> 0 Then WScript.Echo "Создать: " & Err.Description
    Err.Clear
    Set lay = rep.ОсновнойМакет
    If Err.Number <> 0 Then WScript.Echo "ОсновнойМакет: " & Err.Description
    Err.Clear
    Set sk = lay.СхемаКомпоновкиДанных
    If Err.Number <> 0 Then WScript.Echo "СхемаКомпоновкиДанных: " & Err.Description
    Err.Clear
End If
If Not (sk Is Nothing) Then
    WScript.Echo "схема получена из объекта отчета"
Else
    Execute "Set sk = conn.Метаданные().Отчеты.НайтиПоИмени(""АнализЖурналаРегистрации"").ОсновнойМакет.СхемаКомпоновкиДанных"
    If Err.Number <> 0 Then
        WScript.Echo "схема из метаданных: " & Err.Description
        conn.Закрыть()
        WScript.Quit 1
    End If
    WScript.Echo "схема получена из метаданных"
End If
Set vs = sk.ВариантыНастроек
If Err.Number <> 0 Then
    WScript.Echo "ВариантыНастроек: " & Err.Description
    conn.Закрыть()
    WScript.Quit 1
End If
For Each v In vs
    WScript.Echo "=== вариант: " & v.Имя
    For Each pr In v.Настройки.Параметры
        If Err.Number <> 0 Then
            WScript.Echo "  Настройки.Параметры: " & Err.Description
            Err.Clear
            Exit For
        End If
        name = pr.Значение
        WScript.Echo "  * " & pr.Имя & " | Использование=" & pr.Использование _
            & " | Значение=" & name & " | тип=" & pr.Значение.ТипЗначения()
        Err.Clear
    Next
Next
conn.Закрыть()
WScript.Echo "сеанс закрыт"
'''.replace("%IB%", IB)


def main():
    with open(VBS_PATH, "w", encoding="utf-16", newline="\r\n") as handle:
        handle.write(VBS)
    print(f"записан {VBS_PATH} ({len(VBS)} симв, utf-16)")
    proc = subprocess.run(
        ["cscript.exe", "//nologo", VBS_PATH],
        capture_output=True, text=True, encoding="cp866", errors="replace", timeout=600,
    )
    print(f"--- cscript rc={proc.returncode}")
    for line in (proc.stdout or "").splitlines():
        print("  " + line.strip())
    if (proc.stderr or "").strip():
        print("--- stderr:")
        for line in proc.stderr.splitlines():
            print("  " + line.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
