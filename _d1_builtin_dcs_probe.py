# -*- coding: utf-8 -*-
r"""_d1_builtin_dcs_probe.py — встроенный отчёт BP3 через COM вместо внешнего .erf.

Основание (статья «Как запустить встроенный отчет или обработку 1С из командной строки
без изменения конфигурации»): внешнее соединение даёт доступ к менеджерам метаданных
встроенных объектов - Connection.Reports.<Имя>.Create(). Внешний файл не участвует,
поэтому диалог «Предупреждение безопасности» (_d1_warn_probe, _d1_safe_probe) не
возникает вообще.

Предмет - отчёт, у которого в макете найден проверяемый паттерн (замер
_d1_settings_items.py): Reports\АнализЖурналаРегистрации, параметр Пользователь со
значением dcscor:DesignTimeValue "Справочник.Пользователи.ПустаяСсылка" и
<dcsset:use>false</dcsset:use> в варианте настроек.

Вопрос пробы:
  1. доступен ли встроенный отчёт и его СхемаКомпоновкиДанных через COM;
  2. сохранено ли DesignTimeValue-ЗНАЧЕНИЕ параметра, если Использование = Ложь.

Только чтение; сеанс закрывается в finally. Результат отчёта не формируется.
"""
import sys

import win32com.client

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

IB = r"C:\1C_LLM\ckb\_ibcmd_work\ib_bp3"
REPORT = "АнализЖурналаРегистрации"


def one_line(exc):
    return " ".join(str(exc).split())[:240]


def dump_settings(settings, title):
    print(f"  --- {title}")
    try:
        items = list(settings.Параметры)
    except Exception as exc:
        print(f"    Параметры: {one_line(exc)}")
        return
    print(f"    параметров в объекте настроек: {len(items)}")
    for item in items:
        name = getattr(item, "Имя", None) or "<без Имя>"
        try:
            use = repr(getattr(item, "Использование"))
        except Exception as exc:
            use = f"<Использование: {one_line(exc)}>"
        try:
            value = getattr(item, "Значение")
            vtext = repr(value)
            try:
                vtext += f" | тип={value.ТипЗначения()!r}"[:150]
            except Exception:
                pass
        except Exception as exc:
            vtext = f"<Значение: {one_line(exc)}>"
        print(f"    * {name}: Использование={use} Значение={vtext[:200]}")


def get_report_object(session):
    """Несколько способов получить объект встроенного отчёта.

    pywin32 не разрешает динамическое имя метаданного через GetIDsOfNames
    (<unknown>.АнализЖурналаРегистрации), поэтому пробуем поисковые методы.
    """
    tried = []
    manager = None
    for label, call in (
        ("getattr(Отчеты, Имя)", lambda: getattr(session.Отчеты, REPORT)),
        ("Отчеты.НайтиПоИмени", lambda: session.Отчеты.НайтиПоИмени(REPORT)),
        ("Отчеты.ПолучитьМенеджер", lambda: session.Отчеты.ПолучитьМенеджер(REPORT)),
    ):
        try:
            manager = call()
            print(f"  менеджер получен через {label}: {manager!r}")
            break
        except Exception as exc:
            tried.append(f"{label}: {one_line(exc)}")
    if manager is None:
        print("  менеджер отчёта НЕ получен:\n    " + "\n    ".join(tried))
        return None
    for label, call in (("Создать", lambda: manager.Создать()),
                        ("ПолучитьОбъект", lambda: manager.ПолучитьОбъект())):
        try:
            obj = call()
            print(f"  объект отчёта через {label}(): {obj!r}")
            return obj
        except Exception as exc:
            tried.append(f"{label}: {one_line(exc)}")
    print("  объект отчёта НЕ получен:\n    " + "\n    ".join(tried))
    return None


def get_schema_from_metadata(session):
    """Второй путь: СхемаКомпоновкиДанных из метаданных макета отчёта."""
    tried = []
    for label, call in (
        ("Метаданные().Отчеты.НайтиПоИмени(...).ОсновнойМакет.СхемаКомпоновкиДанных",
         lambda: session.Метаданные().Отчеты.НайтиПоИмени(REPORT).ОсновнойМакет
                 .СхемаКомпоновкиДанных),
        ("...Макеты[0].СхемаКомпоновкиДанных",
         lambda: session.Метаданные().Отчеты.НайтиПоИмени(REPORT).Макеты[0]
                 .СхемаКомпоновкиДанных),
    ):
        try:
            schema = call()
            print(f"  схема получена через {label}: {schema!r}")
            return schema
        except Exception as exc:
            tried.append(f"{label}: {one_line(exc)}")
    print("  схема из метаданных НЕ получена:\n    " + "\n    ".join(tried))
    return None


def get_variants(schema):
    for label in ("ВариантыНастроек", "Variants"):
        try:
            variants = list(getattr(schema, label))
            print(f"  {label}: {len(variants)} -> "
                  f"{[getattr(v, 'Имя', repr(v)[:40]) for v in variants]}")
            return variants
        except Exception as exc:
            print(f"  {label}: {one_line(exc)}")
    return []



def main():
    connector = win32com.client.Dispatch("V83.COMConnector")
    session = connector.Connect(f'File="{IB}";')
    try:
        print("=== объект встроенного отчёта (путь из статьи) ===")
        report = get_report_object(session)
        schema = None
        if report is not None:
            for label, call in (
                ("ОсновнойМакет.СхемаКомпоновкиДанных",
                 lambda: report.ОсновнойМакет.СхемаКомпоновкиДанных),
                ("СхемаКомпоновкиДанных", lambda: report.СхемаКомпоновкиДанных),
            ):
                try:
                    schema = call()
                    print(f"  {label}: {schema!r}")
                    break
                except Exception as exc:
                    print(f"  {label}: {one_line(exc)}")
        if schema is None:
            print()
            print("=== схема из метаданных конфигурации (без объекта отчёта) ===")
            schema = get_schema_from_metadata(session)
        if schema is None:
            return 1

        print()
        print("=== варианты настроек схемы ===")
        target = None
        for variant in get_variants(schema):
            if str(getattr(variant, "Имя", "")) in ("Основной", "Main"):
                target = variant
                break
        if target is None:
            print("  вариант «Основной» не найден - дальше не идём")
            return 0

        print()
        print("=== настройки варианта «Основной» (как их держит платформа) ===")
        try:
            dump_settings(target.Настройки, "вариант.Настройки (из макета)")
        except Exception as exc:
            print(f"    вариант.Настройки: {one_line(exc)}")

        print()
        print("=== компоновщик настроек отчётного объекта ===")
        try:
            composer = report.КомпоновщикНастроек
            print(f"  КомпоновщикНастроек: {composer!r}")
            dump_settings(composer.Настройки, "до применения варианта")
            try:
                composer.Настройки.Заполнить(target.Настройки)
                print("  Настройки.Заполнить(вариант.Настройки): выполнено")
            except Exception as exc:
                print(f"  Настройки.Заполнить(): {one_line(exc)}")
                try:
                    composer.Установить(target)
                    print("  КомпоновщикНастроек.Установить(вариант): выполнено")
                except Exception as exc2:
                    print(f"  КомпоновщикНастроек.Установить(): {one_line(exc2)}")
            dump_settings(composer.Настройки, "после применения варианта")
        except Exception as exc:
            print(f"  КомпоновщикНастроек: {one_line(exc)}")
        return 0
    finally:
        try:
            session.Закрыть()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())

