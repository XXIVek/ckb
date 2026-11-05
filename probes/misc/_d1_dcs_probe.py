# -*- coding: utf-8 -*-
r"""_d1_dcs_probe.py — откуда в сеансе взять объект СхемаКомпоновкиДанных.

Загрузка .erf через ВнешниеОтчеты.Создать обрывается диалогом безопасности
(_d1_warn_probe, _d1_safe_probe: УстановитьБезопасныйРежим() принимается, но
БезопасныйРежим() остаётся False). Значит нужен другой источник объекта СКД. Проверяем два:

1. метаданные конфигурации — Метаданные().Отчеты и стандартный менеджер отчёта
   (ПолучитьОбъект/ПолучитьМакет): объект макета СКД приходит из конфигурации,
   никакого диалога про «внешний объект из файла» нет;
2. можно ли создать схему прямо в коде — Тип("СхемаКомпоновкиДанных") и Новый по имени типа.
   Если да,Construct D1 воспроизводится на своей схеме с управляемыми параметрами и
   вариантом настроек, и внешний файл вообще не нужен.

Только чтение; сеанс закрывается в finally.
"""
import sys

import pythoncom
import win32com.client

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

IB = r"C:\1C_LLM\ckb\_ibcmd_work\ib_bp3"
DCS_TYPE_NAMES = ["СхемаКомпоновкиДанных", "DataCompositionSchema"]


def one_line(exc):
    return " ".join(str(exc).split())[:200]


def coll_sample(coll, limit=8):
    """Аккуратно вытащить первые элементы коллекции 1С через COM."""
    names = []
    try:
        count = None
        try:
            count = len(coll)
        except Exception:
            pass
        names.append(f"<len={count}>")
    except Exception as exc:
        names.append(f"<len: {one_line(exc)}>")
    try:
        for index, item in enumerate(coll):
            if index >= limit:
                break
            try:
                names.append(str(getattr(item, "Name")))
            except Exception:
                names.append(repr(item)[:80])
    except Exception as exc:
        names.append(f"<итерация: {one_line(exc)}>")
    return " ".join(names)


def main():
    connector = win32com.client.Dispatch("V83.COMConnector")
    session = connector.Connect(f'File="{IB}";')
    try:
        print("=== метаданные конфигурации ===")
        try:
            md = session.Метаданные()
            print(f"  Метаданные(): {md!r}")
            print(f"  Имя: {md.Имя} | Версия: {md.ВерсияИзменена}")
        except Exception as exc:
            md = None
            print(f"  Метаданные(): {one_line(exc)}")
        if md is not None:
            for prop in ("Отчеты", "Reports"):
                try:
                    reports = getattr(md, prop)
                    print(f"  Метаданные().{prop}: {coll_sample(reports)}")
                    break
                except Exception as exc:
                    print(f"  Метаданные().{prop}: {one_line(exc)}")

        print()
        print("=== стандартный менеджер отчётов ===")
        try:
            manager = session.Отчеты
            print(f"  session.Отчеты: {manager!r}")
        except Exception as exc:
            print(f"  session.Отчеты: {one_line(exc)}")

        print()
        print("=== создание схемы компоновки данных в коде ===")
        for type_name in DCS_TYPE_NAMES:
            try:
                t = session.Тип(type_name)
                print(f"  Тип({type_name!r}): {t!r}")
                try:
                    schema = session.Новый(type_name)
                    print(f"  Новый({type_name!r}): {schema!r}")
                except Exception as exc:
                    print(f"  Новый({type_name!r}): {one_line(exc)}")
            except Exception as exc:
                print(f"  Тип({type_name!r}): {one_line(exc)}")
        return 0
    finally:
        try:
            session.Закрыть()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
