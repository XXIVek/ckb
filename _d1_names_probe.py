# _d1_names_probe.py — замер (19.10.2026): какие имена отдаёт сеанс V83.COMConnector.
#
# Зачем: probe_d1_com.py не получил ВнешниеОтчеты/ExternalReports. Имя глобального свойства
# платформы пишется через «ё» (ВнешниеОтчёты), поэтому список кандидатов обязан включать обе
# записи. Замер отвечает на вопрос прямо, прежде чем править транспорт зонда.
#
# Запуск: python _d1_names_probe.py
import sys

import win32com.client as wc

IB = r"C:\1C_LLM\ckb\_ibcmd_work\ib_bp3"
ERF = r"C:\1C_LLM\LoadDoc\БП3\СравнениеУСНИ90_2.erf"
CANDIDATES = [
    "ВнешниеОтчёты", "ВнешниеОтчеты", "ExternalReports",
    "Отчёты", "Отчеты", "Reports",
    "Метаданные", "Metadata",
]


def main():
    try:
        connector = wc.Dispatch("V83.COMConnector")
    except Exception as exc:  # noqa: BLE001
        print("Dispatch: ОТКАЗ", type(exc).__name__, str(exc)[:200])
        return 2
    session = connector.Connect(f'File="{IB}";')
    print("session:", type(session).__name__)
    try:
        names = [n for n in dir(session) if not n.startswith("_")]
        print("dir():", len(names), names[:30])
    except Exception as exc:  # noqa: BLE001
        print("dir(): не отдаёт:", type(exc).__name__, str(exc)[:120])
    for name in CANDIDATES:
        try:
            value = getattr(session, name)
            print(f"  OK   {name} -> {type(value).__name__}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ERR  {name}: {type(exc).__name__}: {str(exc)[:140]}")
    # GetIDsOfNames — прямой вопрос IDispatch: знает ли сервер имя (список имён + lcid).
    for name in CANDIDATES:
        try:
            dpid = session._oleobj_.GetIDsOfNames([name], 0x409)
            print(f"  DISPID {name} -> {dpid}")
        except Exception as exc:  # noqa: BLE001
            print(f"  NODIS {name}: {type(exc).__name__}: {str(exc)[:100]}")

    print("\n--- методы менеджера внешних отчётов ---")
    manager = None
    for name in ("ВнешниеОтчеты", "ExternalReports"):
        try:
            manager = getattr(session, name)
            print(f"  OK   manager через {name}")
            break
        except Exception as exc:  # noqa: BLE001
            print(f"  ERR  {name}: {type(exc).__name__}: {str(exc)[:140]}")
    if manager is None:
        return 1
    for name in ("Загрузить", "Load", "Поместить", "Save"):
        try:
            member = getattr(manager, name)
            print(f"  OK   member {name} -> {type(member).__name__}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ERR  member {name}: {type(exc).__name__}: {str(exc)[:140]}")
    for name in ("Загрузить", "Load"):
        try:
            report = getattr(manager, name)(ERF)
            print(f"  CALL OK {name} -> {type(report).__name__}")
        except Exception as exc:  # noqa: BLE001
            print(f"  CALL ERR {name}: {type(exc).__name__}: {str(exc)[:400]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
