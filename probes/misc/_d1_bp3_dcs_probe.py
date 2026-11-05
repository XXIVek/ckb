# -*- coding: utf-8 -*-
r"""_d1_bp3_dcs_probe.py — вариант настроек встроенного отчёта на реальной базе БП3.

Площадка (дана оператором 19.10.2026): файловая ИБ C:\1C_LLM\Bases_Test\BP3, наполненная,
конфигурация снята с поддержки, пользователь admin без пароля. Прежняя рабочая ИБ
_ibcmd_work/ib_bp3 для этого не годилась: конфигурация в ней на поддержке без возможности
редактирования, а метаданные через COM не отдавались.

Приём взят из статьи «Как запустить встроенный отчет ... без изменения конфигурации»:
внешнее соединение даёт доступ к менеджерам метаданных (Connection.Reports.<Имя>.Create()),
внешний файл не участвует - диалога безопасности нет.

Предмет: Reports\АнализЖурналаРегистрации, макет ОсновнаяСхемаКомпоновкиДанных - в варианте
настроек найден параметр Пользователь со значением dcscor:DesignTimeValue
"Справочник.Пользователи.ПустаяСсылка" и <dcsset:use>false</dcsset:use>
(замер _d1_settings_items.py).

Вопрос: что платформа отдаёт на уровне объекта настроек - сохранено ли ЗНАЧЕНИЕ параметра,
если Использование = Ложь. Результат отчёта не формируется, данные не меняются.
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
VARIANT = "Основной"


def one_line(exc):
    return " ".join(str(exc).split())[:200]


def probe(label, call):
    try:
        value = call()
        print(f"  [OK  ] {label} -> {value!r}"[:300])
        return value
    except Exception as exc:
        print(f"  [FAIL] {label} -> {one_line(exc)}")
        return None


def dump_params(settings, title):
    print(f"  --- {title}")
    if settings is None:
        print("    объект настроек не получен")
        return
    items = probe("Настройки.Параметры", lambda: list(settings.Параметры))
    if items is None:
        return
    print(f"    параметров: {len(items)}")
    for item in items:
        name = getattr(item, "Имя", None) or "<без Имя>"
        try:
            use = repr(getattr(item, "Использование"))
        except Exception as exc:
            use = f"<ошибка: {one_line(exc)}>"
        try:
            value = getattr(item, "Значение")
            text = f"{value!r} | тип={value.ТипЗначения()!r}"[:220]
        except Exception as exc:
            text = f"<ошибка: {one_line(exc)}>"
        print(f"    * {name}: Использование={use} Значение={text}")


def main():
    connector = win32com.client.Dispatch("V83.COMConnector")
    session = connector.Connect(CONN)
    try:
        print("=== сеанс и конфигурация ===")
        probe("session.ИмяБазы", lambda: session.ИмяБазы)
        md = probe("session.Метаданные()", lambda: session.Метаданные())
        if md is None:
            return 1
        probe("Метаданные().Имя", lambda: md.Имя)
        probe("Метаданные().Версия", lambda: md.Версия)
        probe("Метаданные().Отчеты.Count()", lambda: md.Отчеты.Count())
        md_report = probe("Метаданные().НайтиПоИмени('Отчет.%s')" % REPORT,
                          lambda: md.НайтиПоИмени(f"Отчет.{REPORT}"))
        if md_report is not None:
            probe("метаданный.ОсновнойМакет.СхемаКомпоновкиДанных",
                  lambda: md_report.ОсновнойМакет.СхемаКомпоновкиДанных)

        print()
        print("=== объект отчёта через менеджер (приём из статьи) ===")
        manager = probe(f"session.Отчеты.{REPORT}", lambda: getattr(session.Отчеты, REPORT))
        if manager is None:
            return 1
        report = probe("менеджер.Создать()", lambda: manager.Создать())
        if report is None:
            return 1

        print()
        print("=== схема компоновки данных отчётного объекта ===")
        schema = probe("ОсновнойМакет.СхемаКомпоновкиДанных",
                       lambda: report.ОсновнойМакет.СхемаКомпоновкиДанных)
        if schema is None:
            return 1
        variants = probe("СхемаКомпоновкиДанных.ВариантыНастроек",
                         lambda: list(schema.ВариантыНастроек))
        if not variants:
            return 1
        print(f"    варианты: {[getattr(v, 'Имя', '?') for v in variants]}")

        target = None
        for variant in variants:
            if str(getattr(variant, "Имя", "")) == VARIANT:
                target = variant
                break
        if target is None:
            print(f"    вариант {VARIANT!r} не найден")
            return 1

        print()
        print(f"=== настройки варианта {VARIANT!r} (как их держит платформа) ===")
        variant_settings = probe("вариант.Настройки", lambda: target.Настройки)
        dump_params(variant_settings, "вариант.Настройки")
        probe("вариант.Настройки.Параметры.Получить('Пользователь').Использование",
              lambda: target.Настройки.Параметры.Получить("Пользователь").Использование)
        probe("вариант.Настройки.Параметры.Получить('Пользователь').Значение",
              lambda: target.Настройки.Параметры.Получить("Пользователь").Значение)

        print()
        print("=== компоновщик настроек отчётного объекта ===")
        composer = probe("report.КомпоновщикНастройки", lambda: report.КомпоновщикНастройки)
        if composer is None:
            return 0
        dump_params(probe("КомпоновщикНастройки.Настройки",
                          lambda: composer.Настройки), "до применения варианта")
        probe("Настройки.Заполнить(вариант.Настройки)",
              lambda: composer.Настройки.Заполнить(variant_settings))
        dump_params(probe("КомпоновщикНастройки.Настройки",
                          lambda: composer.Настройки), "после применения варианта")
        return 0
    finally:
        try:
            session.Закрыть()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())

