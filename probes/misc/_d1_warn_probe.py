# -*- coding: utf-8 -*-
r"""_d1_warn_probe.py — подавляется ли «Предупреждение безопасности» при Создать().

Замер _d1_sig_probe.py: ВнешниеОтчеты.Создать(файл) читает .erf (называет имя объекта),
но обрывается исключением кода 1001 «Предупреждение безопасности». Параметр 2 (bool)
принимается и Истина, и Ложь — диалог не меняется; параметр 3 не bool.

Здесь проверяем остающиеся правдоподобные варианты:
1. параметр 3 другого типа (строка, число, None);
2. файл рядом с рабочим каталогом процесса и с относительным именем — вдруг проверка
   источника зависит от расположения;
3. существование свойств-переключателей сеанса.

Каждая проверка — отдельный вызов, ошибка не мешает следующим. ИБ не меняется.
"""
import os
import shutil
import sys

import win32com.client

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

IB = r"C:\1C_LLM\ckb\_ibcmd_work\ib_bp3"
ERF = r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf"
LOCAL_COPY = r"C:\1C_LLM\ckb\_d1_copy.erf"

SWITCHES = [
    "БезопасныйРежим", "UnsafeExternalDataProcessorMode", "Предупреждения",
    "УстановитьБезопасныйРежим",
]


def one_line(exc):
    return " ".join(str(exc).split())[:200]


def verdict(text):
    if "Предупреждение безопасности" in text:
        return "ДИАЛОГ НЕ ПОДАВЛЁН"
    if "Несоответствие типов" in text:
        return "тип параметра не тот"
    if "Неверное количество параметров" in text:
        return "арность не та"
    return "другое"


def try_call(session, label, args):
    try:
        value = getattr(session.ВнешниеОтчеты, "Создать")(*args)
        print(f"  [OK   ] {label} -> {value!r}")
        return value
    except Exception as exc:
        text = one_line(exc)
        print(f"  [{verdict(text)}] {label}: {text}")
        return None


def main():
    shutil.copyfile(ERF, LOCAL_COPY)
    connector = win32com.client.Dispatch("V83.COMConnector")
    session = connector.Connect(f'File="{IB}";')
    try:
        print("=== параметр 3 другого типа ===")
        for third in ("", " ", 0, None):
            try_call(session, f"Создать(файл, Ложь, {third!r})", (ERF, False, third))

        print()
        print("=== файл рядом с рабочим каталогом / относительное имя ===")
        try_call(session, f"Создать({LOCAL_COPY})", (LOCAL_COPY,))
        try_call(session, "Создать('_d1_copy.erf')", ("_d1_copy.erf",))
        try_call(session, "Создать('_d1_copy.erf', Ложь)", ("_d1_copy.erf", False))

        print()
        print("=== свойства-переключатели сеанса ===")
        for name in SWITCHES:
            try:
                value = getattr(session, name)
                print(f"  [есть] {name}: {value!r}")
            except Exception as exc:
                print(f"  [нет ] {name}: {one_line(exc)}")
        return 0
    finally:
        try:
            session.Закрыть()
        except Exception:
            pass
        try:
            os.remove(LOCAL_COPY)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
