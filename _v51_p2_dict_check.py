#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П2: самопроверка словарей `src/configuration_exchange_plans.py`.

Три проверки, каждая отвечает на свой вопрос:

1. Числа словарей совпадают с замером корпуса (40 / 28 / 26 / 7 / 12 / 6 / 4). Числа
   держатся здесь как ожидаемые, а не выводятся из модуля: иначе опечатка в словаре
   перестала бы быть ошибкой.
2. Порядок тегов словаря совпадает с порядком тегов в РЕАЛЬНОМ файле выгрузки (BGU2: файл
   вида, реквизит, табличная часть, колонка ТЧ, описание формы и макета; MinCfg: команда).
   Порядок — часть контракта: пропуск позиции означал бы потерю свойства.
3. Колонки словарей детей существуют в живой схеме `ckb_1c_configurations`. До П1 отсутствующие
   назывались списком и обязаны были быть ровно колонками, которые добавляет П1; после П1
   (выполнен 31.10.2026) эталон — пустой перечень, и любая отсутствующая колонка означает
   опечатку в словаре.

Запуск: python _v51_p2_dict_check.py
"""
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import configuration_exchange_plans as m  # noqa: E402

DUMP = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")

EXPECTED_COUNTS = {
    "вид (Properties)": 40,
    "Attribute (реквизит вида)": 28,
    "Attribute (колонка ТЧ)": 26,
    "TabularSection": 7,
    "Command": 12,
    "Form": 6,
    "Template": 4,
    "StandardAttribute": 0,
}

# Колонки словарей, которых в схеме нет. До П1 этот перечень называл то, что П1 обязан
# добавить (3 колонки в `attributes`, 1 в `tabular_sections`, таблица `commands` целиком).
# П1 выполнен 31.10.2026 и схема это содержит (замер information_schema: `attributes` 38
# колонок, `tabular_sections` 19, `commands` 24), поэтому эталон — пустые множества: любое
# отсутствующее сегодня колонка означает опечатку в словаре или незакоммиченную миграцию,
# а не план П1. Проверка при этом не становится слабее: она по-прежнему сверяет словарь с
# живой схемой и называет виновника по имени колонки.
EXPECTED_MISSING = {
    "attributes": set(),
    "tabular_sections": set(),
    "forms": set(),
    "templates": set(),
    "commands": set(),
}


def loc(tag):
    return tag.rsplit("}", 1)[-1]


def find_child(node, name):
    for child in node:
        if loc(child.tag) == name:
            return child
    return None


def props_tags(node):
    props = find_child(node, "Properties") if node is not None else None
    return [loc(t.tag) for t in props] if props is not None else []


def exchange_plan_root(dump, plan):
    path = DUMP / dump / "ExchangePlans" / f"{plan}.xml"
    return find_child(ET.parse(path).getroot(), "ExchangePlan")


def first_child_of(obj, kind, inside_ts=False):
    children = find_child(obj, "ChildObjects")
    if children is None:
        return None
    for child in children:
        if inside_ts and loc(child.tag) == "TabularSection":
            inner = find_child(child, "ChildObjects")
            if inner is None:
                continue
            for sub in inner:
                if loc(sub.tag) == kind:
                    return sub
        elif not inside_ts and loc(child.tag) == kind:
            return child
    return None


def description_root(dump, sub, root_tag):
    base = DUMP / dump / "ExchangePlans"
    for path in base.rglob("*.xml"):
        if path.parent.name != sub:
            continue
        return find_child(ET.parse(path).getroot(), root_tag)
    return None


def check_counts():
    actual = {
        "вид (Properties)": m.EXCHANGE_PLAN_PROPERTY_COUNT,
        "Attribute (реквизит вида)": m.ATTRIBUTE_COUNT_OBJECT,
        "Attribute (колонка ТЧ)": m.ATTRIBUTE_COUNT_TS_COLUMN,
        "TabularSection": len(m.child_property_records(m.CHILD_TABULAR_SECTION)),
        "Command": len(m.child_property_records(m.CHILD_COMMAND)),
        "Form": len(m.child_property_records(m.CHILD_FORM)),
        "Template": len(m.child_property_records(m.CHILD_TEMPLATE)),
        "StandardAttribute": len(m.child_property_records(m.CHILD_STANDARD_ATTRIBUTE)),
    }
    bad = False
    for name, expected in EXPECTED_COUNTS.items():
        got = actual[name]
        flag = "OK " if got == expected else "ОШИБКА"
        if got != expected:
            bad = True
        print(f"  [{flag}] {name:28} ожидаемо {expected:3} получено {got:3}")
    return not bad


def check_tag_order():
    """Порядок словаря против порядка тегов в файле выгрузки."""
    plan = exchange_plan_root("BGU2", "АвтономнаяРабота")
    mincfg = exchange_plan_root("MinCfg", "АвтономнаяРабота")
    targets = [
        ("вид", m.EXCHANGE_PLAN_PROPERTIES, props_tags(plan), ()),
        ("Attribute", m.child_property_records(m.CHILD_ATTRIBUTE),
         props_tags(first_child_of(plan, "Attribute")), ()),
        ("TabularSection", m.child_property_records(m.CHILD_TABULAR_SECTION),
         props_tags(first_child_of(plan, "TabularSection")), ()),
        # Колонка табличной части — тот же словарь, но двух тегов в файле нет (замер
        # `_v51_p2_shape_probe.py`): это ожидаемое состояние `absent`, а не ошибка словаря.
        ("Attribute внутри ТЧ", m.child_property_records(m.CHILD_ATTRIBUTE),
         props_tags(first_child_of(plan, "Attribute", inside_ts=True)),
         m.ATTRIBUTE_TS_ABSENT_TAGS),
        ("Command", m.child_property_records(m.CHILD_COMMAND),
         props_tags(first_child_of(mincfg, "Command")), ()),
        ("Form", m.child_property_records(m.CHILD_FORM),
         props_tags(description_root("BGU2", "Forms", "Form")), ()),
        ("Template", m.child_property_records(m.CHILD_TEMPLATE),
         props_tags(description_root("BGU2", "Templates", "Template")), ()),
    ]
    bad = False
    for name, records, file_tags, expected_absent in targets:
        dict_tags = [tag for tag, _column, _kind in records]
        if not file_tags:
            print(f"  [ОШИБКА] {name}: тегов в файле не найдено — проверка не выполнена")
            bad = True
            continue
        absent = [t for t in expected_absent if t not in file_tags]
        if len(absent) != len(expected_absent):
            print(f"  [ОШИБКА] {name}: ожидаемого отсутствия тегов нет: "
                  f"отсутствуют {absent}, ждали {list(expected_absent)}")
            bad = True
        comparable = [t for t in dict_tags if t not in absent]
        if comparable == file_tags:
            note = f" (за исключением {len(absent)} отсутствующих в файле)" if absent else ""
            print(f"  [OK ] {name:20} порядок {len(file_tags)} тегов совпадает с файлом{note}")
            continue
        bad = True
        extra = [t for t in comparable if t not in file_tags]
        missing = [t for t in file_tags if t not in comparable]
        print(f"  [ОШИБКА] {name}: словарём {len(comparable)} тегов, файлом {len(file_tags)}; "
              f"лишние {extra}, не описаны {missing}")
        if not extra and not missing:
            print(f"          тот же набор, но порядок расходится: словарь {comparable[:4]}…, "
                  f"файл {file_tags[:4]}…")
    return not bad


def schema_columns(table):
    import external_db
    with external_db.connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s", (table,))
        return {row[0] for row in cur.fetchall()}


def check_columns_against_schema():
    bad = False
    for kind in (m.CHILD_ATTRIBUTE, m.CHILD_TABULAR_SECTION, m.CHILD_FORM, m.CHILD_TEMPLATE,
                 m.CHILD_COMMAND):
        table = m.CHILD_TABLE_BY_KIND[kind]
        wanted = set(m.child_property_columns(kind))
        existing = schema_columns(table)
        if existing:
            missing = wanted - existing
            expected_missing = EXPECTED_MISSING[table]
            if missing == expected_missing:
                print(f"  [OK ] {table:18} колонок в словаре {len(wanted)}, "
                      f"отсутствующих в схеме: {len(missing)} {sorted(missing)}")
            else:
                bad = True
                print(f"  [ОШИБКА] {table:18} нет в схеме вне эталона: "
                      f"{sorted(missing - expected_missing)}; "
                      f"словарь не покрывает {sorted(expected_missing - missing)}")
        else:
            print(f"  [НЕТ ] {table:18} таблицы в схеме нет — её создаёт П1 "
                  f"(колонок в словаре {len(wanted)})")
    return not bad


def main():
    print("=== П2: самопроверка словарей узла V51 ===")
    ok_counts = check_counts()
    print("\n--- порядок тегов против файла выгрузки ---")
    ok_order = check_tag_order()
    print("\n--- колонки словарей против живой схемы ---")
    ok_columns = check_columns_against_schema()
    print("\n=== итог ===")
    print(f"числа: {'OK' if ok_counts else 'ОШИБКА'}; "
          f"порядок тегов: {'OK' if ok_order else 'ОШИБКА'}; "
          f"колонки схемы: {'OK' if ok_columns else 'ОШИБКА'}")
    return 0 if (ok_counts and ok_order and ok_columns) else 1


if __name__ == "__main__":
    sys.exit(main())