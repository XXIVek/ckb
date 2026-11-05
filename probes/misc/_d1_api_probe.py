# -*- coding: utf-8 -*-
"""_d1_api_probe.py — что именно отдаёт объект сеанса V83.COMConnector (замер имён).

Зачем. Замер `_d1_min_call_probe.py` (19.10.2026) показал, что позднее связывание
pywin32 на объекте 1С работает: часть имён разрешается (`Метаданные`, `ВнешниеОтчеты`
отдаются как CDispatch), часть — нет (`Вычислить`, `ПолучитьМакет`,
`ПолучитьВнешнююОбработку`, экспортированная функция общего модуля `Умножение`).
Прежние провалы были двух разных видов, которые надо разделить:

  * `session.Метаданные()` падало с DISP_E_MEMBERNOTFOUND — потому что `Метаданные`
    это СВОЙСТВО, а не метод: вызов пытается выполнить метод по умолчанию (DISPID 0);
  * `getattr` по имени, которого сеанс не отдаёт, даёт AttributeError — это и есть
    настоящий признак отсутствия имени.

Скрипт измеряет один раз (одно подключение) и печатает:
  [1] список имён сеанса: разрешается / нет (глобальный контекст платформы против
      фиксированного набора внешнего соединения);
  [2] навигация по Метаданные (свойство): отдаются ли коллекции видов, работает ли Найти;
  [3] менеджер внешних отчётов: каким именем загружается .erf;
  [4] почему у фикстуры MinCfg не виден её собственный общий модуль: флаги
      CommonModules/МинМодуль.xml читаются только чтобы объяснить результат.

Площадка — наша ИБ `_ibcmd_work\\ib_mincfg` (заполнена MinCfg_1Cv8.cf, п. 13.8),
резерв — `_ibcmd_work\\ib_bp3`. Только чтение, ничего не записывает.

Запуск: python _d1_api_probe.py --log _d1_api_probe.txt
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:\1C_LLM\ckb")
from win32com.client import Dispatch  # noqa: E402

TARGETS = [
    ("наша ИБ MinCfg", r'File="C:\1C_LLM\ckb\_ibcmd_work\ib_mincfg";'),
    ("наша ИБ БП3", r'File="C:\1C_LLM\ckb\_ibcmd_work\ib_bp3";'),
]

# имена, которые теоретически могут быть у сеанса внешнего соединения
SESSION_NAMES = [
    # фиксированный набор внешнего соединения
    "Метаданные", "Metadata", "ВнешниеОтчеты", "ExternalReports",
    "ВнешниеОбработки", "ExternalDataProcessors", "ВнешниеРасширения",
    "ПолучитьСоединение", "АргументыКоманднойСтроки",
    "ПолучитьОбновлениеИнформационнойБазы",
    # глобальные функции платформы — проверяем, отдаёт ли их сеанс
    "Вычислить", "Eval", "ПолучитьВнешнийОтчет", "ПолучитьВнешнююОбработку",
    "ПолучитьВнешнееРасширение", "ПолучитьМакет", "ОткрытьФорму", "ПолучитьФорму",
    "Новый", "Запрос", "Записать", "Найти", "ПолучитьЖурналРегистрации",
    "НачатьТранзакцию", "УстановитьПривилегированныйРежим",
    # свои функции конфигурации (у MinCfg общий модуль НЕ открыт для внешнего соединения)
    "Умножение", "СложениеАиБ",
]

# навигация по Метаданные
META_NAMES = ["Найти", "Find", "ThisObject", "ЭтотОбъект", "CommonModules",
              "ОбщиеМодули", "DataProcessors"]

# менеджер внешних отчётов
ER_METHODS = ["Загрузить", "Load", "ЗагрузитьВнешнийОтчет", "Create", "Создать",
              "Get", "Получить"]

MODULE_XML = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg"
                  r"\CommonModules\МинМодуль.xml")

_log = []


def say(s=""):
    print(s, flush=True)
    _log.append(str(s))


def short(e):
    return str(e).replace("\n", " ").strip()[:180]


def probe_owner(owner, label, names):
    say(f"\n[{label}]")
    found = []
    for name in names:
        try:
            value = getattr(owner, name)
            found.append(name)
            say(f"  OK     {name}: {type(value).__name__}")
        except Exception as exc:                      # noqa: BLE001
            say(f"  absent {name}: {type(exc).__name__}: {short(exc)}")
    return found


def main():
    connector = Dispatch("V83.COMConnector")
    session = None
    for title, conn_str in TARGETS:
        say(f"[connect] {title}: {conn_str}")
        try:
            session = connector.Connect(conn_str)
            say("  ОК")
            break
        except Exception as exc:                      # noqa: BLE001
            say(f"  ОТКАЗ: {short(exc)}")
    if session is None:
        say("\nНет доступной ИБ — замер не состоялся")
        return 2

    session_found = probe_owner(session, "1. ИМЕНА СЕАНСА", SESSION_NAMES)

    if "Метаданные" in session_found:
        meta = session.Метаданные
        say(f"\n[2. НАВИГАЦИЯ ПО Метаданные] тип: {type(meta).__name__}")
        probe_owner(meta, "метаданные", META_NAMES)
        for candidate in ("DataProcessor.МинОбработка", "CommonModule.МинМодуль",
                          "Report.МинОтчёт"):
            try:
                found = meta.Найти(candidate)
                say(f"  Найти({candidate!r}) -> {found!r}")
            except Exception as exc:                  # noqa: BLE001
                say(f"  Найти({candidate!r}) отказ: {short(exc)}")

    if "ВнешниеОтчеты" in session_found:
        er = session.ВнешниеОтчеты
        say(f"\n[3. МЕНЕДЖЕР ВНЕШНИХ ОТЧЁТОВ] тип: {type(er).__name__}")
        probe_owner(er, "менеджер", ER_METHODS)

    say("\n[4. ПОЧЕМУ СВОЙ ОБЩИЙ МОДУЛЬ НЕ ВИДЕН]")
    if MODULE_XML.exists():
        text = MODULE_XML.read_text(encoding="utf-8-sig", errors="replace")
        flags = {}
        for flag in ("ExternalConnection", "Global", "Server", "ServerCall",
                     "ClientManagedApplication"):
            match = re.search(rf"<{flag}>(.*?)</{flag}>", text)
            flags[flag] = match.group(1) if match else "?"
        say("  флаги МинМодуль.xml: " + ", ".join(f"{k}={v}" for k, v in flags.items()))
        say("  вывод: при ExternalConnection=false общий модуль в сеансе внешнего")
        say("  соединения не участвует — чтобы вызвать свою BSL-функцию, нужен true.")
    else:
        say(f"  {MODULE_XML} не найден — сравнение пропущено")

    say("\n[ИТОГ]")
    say(f"  разрешённых имён сеанса: {len(session_found)} из {len(SESSION_NAMES)}")
    say("  список разрешённых: " + ", ".join(session_found))
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

