# -*- coding: utf-8 -*-
r"""_d1_com_names_en.py - какие имена members отдаёт COM-сеанс (pywin32, обе записи).

Серия замеров 19.10.2026 дала противоречия, которые нужно снять одним замером:
  * pywin32: session.Отчеты как свойство возвращается, но getattr(..., "АнализЖурнала...")
    и session.Метаданные() -> DISP_E_MEMBERNOTFOUND;
  * PowerShell extended syntax $session.('Отчеты') -> null, $session.('Метаданные')() -> объект;
  * PowerShell прямая точка $session.Отчеты -> null; метод Закрыть не найден;
  * VBScript: кириллические идентификаторы не принимает лексер.
Гипотеза: в IDispatch сеанса имена зарегистрированы в английской записи (LCID 1033),
русские имена действуют только внутри встроенного языка.

Здесь перебираются обе записи для session и для менеджера отчётов. Только чтение.
"""
import sys

import win32com.client

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

IB = r"C:\1C_LLM\Bases_Test\BP3"
CONN = f'File="{IB}";Usr=admin;Pwd=;'
REPORT = "АнализЖурналаРегистрации"


def probe(label, call):
    try:
        value = call()
        print(f"  [OK  ] {label} -> {type(value).__name__} {value!r}"[:200])
        return value
    except Exception as exc:
        reason = " ".join(str(exc).split())[:120]
        print(f"  [FAIL] {label} -> {reason}")
        return None


def main():
    connector = win32com.client.Dispatch("V83.COMConnector")
    session = connector.Connect(CONN)
    try:
        print("=== имена уровня сеанса ===")
        names = {}
        for name in ("Reports", "Metadata", "Close", "NewObject", "NewValue",
                     "Отчеты", "Метаданные", "Закрыть", "ПолучитьИмяБазы"):
            names[name] = probe(f"session.{name}", lambda name=name: getattr(session, name))

        for key in ("Reports", "Отчеты"):
            manager = names.get(key)
            if manager is None:
                continue
            print()
            print(f"=== члены {key} ===")
            probe(f"{key}.{REPORT}", lambda manager=manager: getattr(manager, REPORT))
            for method in ("Item", "FindByName", "НайтиПоИмени", "Count", "Количество"):
                probe(f"{key}.{method}()",
                      lambda manager=manager, method=method: getattr(manager, method)())
            break
        return 0
    finally:
        for closer in ("Close", "Закрыть"):
            try:
                getattr(session, closer)()
                print(f"\nсеанс закрыт через {closer}")
                break
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
