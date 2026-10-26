# -*- coding: utf-8 -*-
"""_d1_min_call_probe.py — разрешаются ли через COM имена методов КОНФИГУРАЦИИ.

Зачем. Предыдущие зонды (`_d1_names_probe.py`, `_d1_eval_probe.py`) показали: getattr
по всем именам глобального контекста платформы на сессии `V83.COMConnector` даёт
DISP_E_MEMBERNOTFOUND («Член группы не найден»), а `GetIDsOfNames` у pywin32 не
принимает нашу раскладку аргументов. Остаётся два разных объяснения, и их надо
различить:

  A) pywin32/позднее связанное связывание не умеет разрешать имена на объекте 1С;
  B) сессия внешнего соединения действительно не отдаёт имена глобального контекста
     платформы, но отдаёт экспортированные методы общих модулей конфигурации.

Разрешает спор фикстура MinCfg: её общий модуль `МинМодуль`
(XML_files\\MinCfg\\CommonModules\\МинМодуль\\Ext\\Module.bsl) содержит экспортированную
функцию `Умножение(ТекА, ТекБ)`. Если `session.Умножение(6, 7)` вернёт 42 — верно B:
имена конфигурации разрешаются, а платформенных глобальных функций через COM нет.
Если падает так же — верно A, и тогда нужен другой транспорт (PowerShell/VBScript).

Площадка: наша ИБ `_ibcmd_work\\ib_mincfg` (создана и заполнена `config load
MinCfg_1Cv8.cf` — замер 13.8). Резерв — ИБ оператора `C:\\1C_LLM\\Bases_Test\\MinCfg`
только на чтение (вызов функции ничего в базе не меняет).

Запуск (обязательно с логом):
  python _d1_min_call_probe.py --log _d1_min_call_probe.txt
"""
import sys
import traceback

sys.path.insert(0, r"C:\1C_LLM\ckb")
from win32com.client import Dispatch, CDispatch  # noqa: E402
from win32com.client.dynamic import CDispatch as DynamicCDispatch  # noqa: E402

TARGETS = [
    ("наша ИБ MinCfg", r'File="C:\1C_LLM\ckb\_ibcmd_work\ib_mincfg";'),
    ("ИБ оператора MinCfg", r'File="C:\1C_LLM\Bases_Test\MinCfg";'),
]

# имена конфигурации (ожидаем успех) и имена платформы (ожидаем отказ) — сравнение
CONFIG_NAMES = ["Умножение", "СложениеАиБ"]
PLATFORM_NAMES = ["Метаданные", "Вычислить", "ПолучитьМакет", "ВнешниеОтчеты",
                  "ПолучитьВнешнююОбработку"]

_log = []


def say(s=""):
    print(s, flush=True)
    _log.append(str(s))


def short(e):
    text = str(e).replace("\n", " ").strip()
    return text[:200]


def main():
    say(f"pywin32 CDispatch: {CDispatch} / dynamic: {DynamicCDispatch}")
    connector = Dispatch("V83.COMConnector")
    session = None
    for title, conn_str in TARGETS:
        say(f"\n[connect] {title}: {conn_str}")
        try:
            session = connector.Connect(conn_str)
            say("  ОК")
            break
        except Exception as exc:                      # noqa: BLE001
            say(f"  ОТКАЗ: {short(exc)}")
    if session is None:
        say("\nНи одна ИБ MinCfg не доступна — сравнение не состоялось.")
        return 2

    say("\n[имена конфигурации — ожидаем разрешение]")
    works = 0
    for name in CONFIG_NAMES:
        try:
            value = getattr(session, name)(6, 7)
            works += 1
            say(f"  OK   {name}(6, 7) = {value!r} [{type(value).__name__}]")
        except Exception as exc:                      # noqa: BLE001
            say(f"  FAIL {name}: {type(exc).__name__}: {short(exc)}")

    say("\n[имена платформы — ожидаем DISP_E_MEMBERNOTFOUND]")
    platform_ok = 0
    for name in PLATFORM_NAMES:
        try:
            value = getattr(session, name)
            platform_ok += 1
            say(f"  RESOLVED {name}: {type(value).__name__}")
        except Exception as exc:                      # noqa: BLE001
            say(f"  absent   {name}: {short(exc)}")

    say("\n[вывод]")
    say(f"  имена конфигурации разрешаются: {works} из {len(CONFIG_NAMES)}")
    say(f"  имена платформы разрешаются:    {platform_ok} из {len(PLATFORM_NAMES)}")
    if works and not platform_ok:
        say("  → B: транспорт рабочий, но только для своих BSL-функций конфигурации;")
        say("    платформенных глобальных функций (Метаданные/Вычислить) через COM нет.")
    elif works and platform_ok:
        say("  → A/B частично: часть имён платформы всё-таки отдаётся, список выше.")
    else:
        say("  → A: позднее связывание pywin32 на объекте 1С не работает —")
        say("    нужен другой транспорт (PowerShell/VBS) или другой способ вызова.")

    try:
        connector.Disconnect()
    except Exception:                                 # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    code = main()
    if "--log" in sys.argv:
        path = sys.argv[sys.argv.index("--log") + 1]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(_log) + "\n")
    sys.exit(code)
