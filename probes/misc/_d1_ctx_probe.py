# -*- coding: utf-8 -*-
r"""_d1_ctx_probe.py — чем в этой платформе загружают внешний отчёт из файла.

Дано: _d1_erf_probe.py показал, что `session.ВнешниеОтчеты` существует (ошибка называет
несуществующий метод, а не имя свойства — "<unknown>.Загрузить" против
"Connect.ПолучениеВнешнегоОтчетаИзФайла"), но `Загрузить`/`ПолучитьИзФайла` у него нет.
Значит имя метода в этой версии другое. Определяем не гаданием, а замером:

1. ТипЗначения на разрешённое имя глобального контекста — какой тип у `ВнешниеОтчеты`;
2. перебор имён методов с классификацией ошибки: DISP_E_UNKNOWNNAME ("нет такого имени")
   отличается от ошибки вызова с неправильными аргументами — если аргументы не подходят,
   метод существует.

Только чтение; ИБ не меняется, сеанс закрывается в finally.
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

# Имена, которые стоит проверить у объекта-загрузчика внешних отчётов.
METHODS = [
    "Загрузить", "ЗагрузитьИзФайла", "ПолучитьИзФайла", "Поместить", "Получить",
    "Записать", "Установить", "Выбрать", "Подключить", "Открыть", "Создать",
    "ПолучитьВнешнийОтчет", "ЗагрузитьВнешнийОтчет",
]
# Имена глобального контекста, которые могут оказаться загрузчиком.
CONTEXT = [
    "ВнешниеОтчеты", "ВнешниеОбработки", "ВнешниеОтчетыМенеджер",
    "ВнешниеОбработкиМенеджер", "ОбщегоНазначения", "ОбщегоНазначенияКлиентСервер",
    "ПолучениеВнешнегоОтчетаИзФайла", "ПолучениеВнешнейОбработкиИзФайла",
    "СтандартныеПодсистемы", "Разное",
]


def one_line(exc):
    return " ".join(str(exc).split())[:240]


def type_name(session, value):
    try:
        description = session.ТипЗначения(value)
    except Exception as exc:
        return f"<ТипЗначения не сработал: {one_line(exc)}>"
    for attr in ("Имя", "Name"):
        try:
            return f"{getattr(description, attr)} (kind={getattr(description, 'Вид', getattr(description, 'Kind', '?'))})"
        except Exception:
            continue
    return "<тип без имени>"


def main():
    connector = win32com.client.Dispatch("V83.COMConnector")
    session = connector.Connect(f'File="{IB}";')
    try:
        print("=== имена глобального контекста ===")
        holders = []
        for name in CONTEXT:
            try:
                value = getattr(session, name)
            except Exception as exc:
                print(f"[нет ] {name}: {one_line(exc)}")
                continue
            print(f"[есть] {name}: тип = {type_name(session, value)}")
            holders.append((name, value))
        if not holders:
            print("ни одного загрузчика не найдено")
            return 1

        print()
        print("=== методы найденных объектов (кандидаты) ===")
        # Аргумент-приманка: если метод существует, но аргументы не подходят, платформа
        # ответит про параметры, а не про неизвестное имя — это и есть признак "метод есть".
        for name, value in holders:
            print(f"--- {name} ---")
            for method in METHODS:
                try:
                    callable_method = getattr(value, method)
                    callable_method(ERF)
                    print(f"  [ВЫЗОВ OK ] {method}(файл) — метод существует и принят")
                except pythoncom.com_error as exc:
                    text = one_line(exc)
                    kind = "НЕТ ИМЕНИ" if ("unknown" in text or "unknownname" in text.lower()) else "ЕСТЬ, ошибка аргументов"
                    print(f"  [{kind}] {method}: {text}")
                except Exception as exc:
                    print(f"  [ЕСТЬ, ошибка выполнения] {method}: {one_line(exc)}")
        return 0
    finally:
        try:
            session.Закрыть()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
