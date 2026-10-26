# -*- coding: utf-8 -*-
r"""_d1_erf_probe.py — загружается ли внешний отчёт в сеансе COM и что в нём видно.

Второй шаг после _d1_conn_probe.py (тот показал: файловая ИБ ibcmd открывается сеансом
File="..." без аутентификации, пользователей в ней нет). Здесь проверяется то, от чего
зависит весь замер D1:

1. каким из доступных в платформе способов загружается .erf (перебором — документация по
   этому API разошлась по поставкам, а вызов существует или нет, решает только прогон);
2. отдаёт ли загруженный объект содержимое, нужное для слоёв D1:
   L1 — КомпоновщикНастроек / Настройки.ПараметрыДанных,
   L2 — КомпоновщикМакета.Выполнить → МакетКомпоновки с источниками данных.

Скрипт только читает: в ИБ не пишет ничего, сеанс закрывает в finally.
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

# Кандидаты загрузки внешнего отчёта из файла: (объект контекста, метод).
# Перебор, а не один вызов: платформа оставляет имя несуществующего метода резолвиться
# динамически, поэтому проверка — именно вызов с разбором ошибки.
LOADERS = [
    ("ВнешниеОтчеты", "Загрузить"),
    ("ВнешниеОтчеты", "ПолучитьИзФайла"),
    ("ВнешниеОбработки", "Загрузить"),
    ("ПолучениеВнешнегоОтчетаИзФайла", "ПолучитьВнешнийОтчетИзФайла"),
]


def type_name(com, value):
    """Человеческое имя типа значения 1С через ТипЗначения (для отчёта, не для кода)."""
    for call in ("ТипЗначения", "Тип"):
        try:
            description = getattr(com, call)(value)
        except Exception:
            continue
        for attr in ("Name", "Имя"):
            try:
                return str(getattr(description, attr))
            except Exception:
                continue
        try:
            return str(description)
        except Exception:
            pass
    return f"<тип неизвестен, python: {type(value).__name__}>"


def main():
    connector = win32com.client.Dispatch("V83.COMConnector")
    session = connector.Connect(f'File="{IB}";')
    print(f"сеанс открыт: {session!r}")
    try:
        platform = "?"
        try:
            platform = session.Версия()
        except Exception:
            try:
                platform = session.ВерсияПлатформыПолная
            except Exception:
                pass
        print(f"платформа сеанса: {platform}")

        report = None
        for holder_name, method_name in LOADERS:
            try:
                holder = getattr(session, holder_name)
                report = getattr(holder, method_name)(ERF)
                print(f"[OK  ] {holder_name}.{method_name}({ERF})")
                break
            except Exception as exc:
                report = None
                print(f"[FAIL] {holder_name}.{method_name}: "
                      + " ".join(str(exc).split())[:220])
        if report is None:
            print("итог: ни один способ загрузки не сработал — замер D1 на этой ИБ невозможен")
            return 1

        print(f"загружен: {type_name(session, report)}")
        for attr in ("Имя", "Name", "Ссылка"):
            try:
                print(f"  {attr} = {getattr(report, attr)}")
            except Exception:
                continue

        # Что из нужного для D1 доступно у загруженного объекта.
        probes = [
            ("ОсновнаяСхемаКомпоновкиДанных", None),
            ("ПолучитьМакет", (TEMPLATE,)),
            ("ПолучитьКомпоновщикНастроек", None),
            ("ПолучитьКомпоновщикМакета", None),
            ("ПолучитьПроцессорКомпоновкиДанных", None),
            ("УстановитьКомпоновщикНастроек", None),
            ("ВыполнитьЗапрос", None),
        ]
        for name, args in probes:
            try:
                method = getattr(report, name)
                if args is None:
                    value = method  # свойство: обращение уже читает значение
                else:
                    value = method(*args)
                print(f"[OK  ] {name} -> {type_name(session, value)}")
            except Exception as exc:
                print(f"[FAIL] {name}: " + " ".join(str(exc).split())[:220])
        return 0
    finally:
        try:
            session.Закрыть()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
