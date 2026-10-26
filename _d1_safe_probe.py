# -*- coding: utf-8 -*-
r"""_d1_safe_probe.py — загружается ли .erf при включённом безопасном режиме сеанса.

Цепочка замеров:
  _d1_conn_probe  — файловая ИБ ibcmd открывается сеансом File="..." без аутентификации;
  _d1_ctx_probe   — загрузчик внешнего отчёта в 8.3.27 — ВнешниеОтчеты.Создать(файл);
  _d1_sig_probe / _d1_warn_probe — вызов читает файл (называет имя объекта), но обрывается
                    исключением 1001 «Предупреждение безопасности»; параметр 2 (bool) и
                    расположение файла диалог не снимают;
Зато в сеансе есть штатные методы глобального контекста БезопасныйРежим() и
УстановитьБезопасныйРежим(<Булево>). Проверяем их: если при безопасном режиме диалог не
нужен, замер D1 идёт на существующей ИБ без правок конфигурации и без новой базы.

После загрузки сразу смотрим, доступны ли объекты, нужные для слоёв D1 (макет СКД,
компоновщики настроек/макета). ИБ не меняется, сеанс закрывается в finally.
"""
import sys

import win32com.client

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

IB = r"C:\1C_LLM\ckb\_ibcmd_work\ib_bp3"
ERF = r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf"
TEMPLATE = "ОсновнаяСхемаКомпоновкиДанных"

# Что нужно слоям D1: L1 — компоновщик настроек, L2 — компоновщик макета.
MEMBERS = [
    ("Имя", None),
    ("Ссылка", None),
    ("ОсновнаяСхемаКомпоновкиДанных", None),
    ("ПолучитьМакет", (TEMPLATE,)),
    ("ПолучитьКомпоновщикНастроек", None),
    ("ПолучитьКомпоновщикМакета", None),
    ("ПолучитьПроцессорКомпоновкиДанных", None),
    ("УстановитьКомпоновщикНастроек", None),
]


def one_line(exc):
    return " ".join(str(exc).split())[:200]


def main():
    connector = win32com.client.Dispatch("V83.COMConnector")
    session = connector.Connect(f'File="{IB}";')
    try:
        print("=== безопасный режим сеанса ===")
        try:
            print(f"  до: БезопасныйРежим() = {session.БезопасныйРежим()}")
        except Exception as exc:
            print(f"  до: {one_line(exc)}")
        for flag in (True, False):
            try:
                session.УстановитьБезопасныйРежим(flag)
                print(f"  УстановитьБезопасныйРежим({flag}) принято, "
                      f"текущий = {session.БезопасныйРежим()}")
            except Exception as exc:
                print(f"  УстановитьБезопасныйРежим({flag}): {one_line(exc)}")

        for flag in (True, False):
            print()
            print(f"=== Создать() при безопасном режиме = {flag} ===")
            try:
                session.УстановитьБезопасныйРежим(flag)
            except Exception:
                pass
            try:
                report = session.ВнешниеОтчеты.Создать(ERF)
            except Exception as exc:
                print(f"  [не загрузился] {one_line(exc)}")
                continue
            print(f"  [OK] загружен: {report!r}")
            for name, args in MEMBERS:
                try:
                    value = (getattr(report, name)(*args) if args is not None
                             else getattr(report, name))
                    print(f"    [есть ] {name}: {value!r}"[:180])
                except Exception as exc:
                    print(f"    [нет  ] {name}: {one_line(exc)}")
            return 0
        return 1
    finally:
        try:
            session.Закрыть()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
