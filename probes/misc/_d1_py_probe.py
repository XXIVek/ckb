# _d1_py_probe.py - замер: что возвращает V83.COMConnector.Connect и какие члены у объекта.
#
# Зачем (19.10.2026): PowerShell открыл «сеанс», но ни одно имя члена не резолвится -
# и русское (Закрыть), и английское (Close) дают DISP_E_UNKNOWNNAME. Значит объект,
# который вернул Connect, - не COMSession. pywin32 даёт текст ошибки самого коннектора,
# поэтому замер идёт здесь, а не в PowerShell.
#
# Запуск: python _d1_py_probe.py

import sys

import pythoncom
import win32com.client as wc

VARIANTS = [
    r'File="C:\1C_LLM\Bases_Test\BP3";',
    r'File="C:\1C_LLM\Bases_Test\BP3";Usr=admin;Pwd=;',
    r'File="C:\1C_LLM\ckb\_ibcmd_work\ib_mincfg";',
    r'File="C:\1C_LLM\ckb\_ibcmd_work\ib_bp3";',
]


def describe(obj, label):
    print(f"  {label}: type={type(obj).__name__}")
    try:
        names = [n for n in dir(obj) if not n.startswith('_')]
        print(f"  {label}: dir() -> {len(names)} имён: {names[:20]}")
    except Exception as exc:  # noqa: BLE001
        print(f"  {label}: dir() не отдаёт: {type(exc).__name__}: {exc}")
    for name in ("Close", "Закрыть", "Reports", "Отчеты"):
        try:
            getattr(obj, name)
            print(f"  {label}: OK {name}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {label}: ERR {name}: {type(exc).__name__}: {str(exc)[:120]}")


def main():
    print("python:", sys.version.split()[0])
    try:
        connector = wc.Dispatch("V83.COMConnector")
    except Exception as exc:  # noqa: BLE001
        print("Dispatch V83.COMConnector: ОТКАЗ", type(exc).__name__, str(exc)[:200])
        return 2
    describe(connector, "connector")
    for conn_string in VARIANTS:
        print("\nconnect:", conn_string)
        try:
            session = connector.Connect(conn_string)
        except Exception as exc:  # noqa: BLE001
            print("  ОТКАЗ:", type(exc).__name__, str(exc)[:300])
            continue
        describe(session, "session")
    return 0


if __name__ == "__main__":
    sys.exit(main())
