# -*- coding: utf-8 -*-
r"""_d1_sig_probe.py — сигнатура ВнешниеОтчеты.Создать и загрузка без диалога безопасности.

_d1_ctx_probe.py установил факт: в 8.3.27.1859 загрузчик внешнего отчёта из файла —
`ВнешниеОтчеты.Создать(<путь к .erf>)`. Файл читается (платформа называет имя объекта —
"Сравнение УСН и 90"), но вызов заканчивается ошибкой кода 1001 «Предупреждение
безопасности»: в неинтерактивном COM-сеансе диалог некому ответить.

Здесь проверяем, подавляется ли диалог параметром. Способ — перебор арности: платформа на
неверное число параметров отвечает «Неверное количество параметров», на подходящий вызов —
или результатом, или другой ошибкой. Это и есть замер сигнатуры без документации.

Только чтение; сеанс закрывается в finally.
"""
import sys

import pythoncom
import win32com.client

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

IB = r"C:\1C_LLM\ckb\_ibcmd_work\ib_bp3"
ERF = r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf"
TEMPLATE = "ОсновнаяСхемаКомпоновкиДанных"

# Набор пробных вызовов: от пустого (арность) до вариантов с признаком безопасного режима.
ARG_SETS = [
    (),
    (ERF,),
    (ERF, True),
    (ERF, False),
    (ERF, True, True),
    (ERF, False, False),
    (ERF, False, False, False),
    (ERF, False, False, False, False),
]


def one_line(exc):
    return " ".join(str(exc).split())[:200]


def classify(exc):
    text = one_line(exc)
    if "Неверное количество параметров" in text:
        return "АРНОСТЬ НЕ ПОДХОДИТ"
    if "Предупреждение безопасности" in text:
        return "ЗАГРУЗИЛ, НО ДИАЛОГ БЕЗОПАСНОСТИ"
    if "unknown" in text:
        return "НЕТ ТАКОГО ИМЕНИ"
    return "ДРУГАЯ ОШИБКА"


def main():
    connector = win32com.client.Dispatch("V83.COMConnector")
    session = connector.Connect(f'File="{IB}";')
    try:
        holder = session.ВнешниеОтчеты
        loaded = None
        for method in ("Создать", "Подключить"):
            print(f"=== {method} ===")
            for args in ARG_SETS:
                shape = ", ".join("файл" if a == ERF else repr(a) for a in args)
                try:
                    value = getattr(holder, method)(*args)
                    print(f"  [OK   ] ({shape}) -> {value!r}")
                    if loaded is None:
                        loaded = value
                except Exception as exc:
                    print(f"  [{classify(exc)}] ({shape}): {one_line(exc)}")
        if loaded is None:
            print("\nзагрузка не удалась ни одним вариантом — D1 на этой ИБ недоступен")
            return 1

        print("\n=== что даёт загруженный объект (для слоёв D1) ===")
        for name in ("ОсновнаяСхемаКомпоновкиДанных", "ПолучитьМакет",
                     "УстановитьКомпоновщикНастроек", "ПолучитьКомпоновщикНастроек",
                     "ПолучитьКомпоновщикМакета", "ПолучитьПроцессорКомпоновкиДанных",
                     "Имя", "Ссылка"):
            try:
                if name == "ПолучитьМакет":
                    value = getattr(loaded, name)(TEMPLATE)
                else:
                    value = getattr(loaded, name)
                print(f"  [есть ] {name}: {value!r}"[:200])
            except Exception as exc:
                print(f"  [нет  ] {name}: {one_line(exc)}")
        return 0
    finally:
        try:
            session.Закрыть()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
