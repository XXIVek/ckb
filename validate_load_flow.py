#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка контракта загрузки load_1c_catalog_tool на тестовых каталогах.

Норматив: docs/config-scenarios/FLOWCHART_1c-configurations-core.md (раздел 10).

Запуск:
    python validate_load_flow.py            - только определение варианта (в БД ничего не меняется)
    python validate_load_flow.py --with-load - плюс загрузка внешних отчётов Test1_Otchet и
      Test3_Otchet_Null с проверкой дочерних данных (attributes, tabular_sections, forms,
      form_ext, templates, bsl_modules); тестовые записи удаляются из БД после прогона.

Выход: 0 - поведение совпало с ожидаемым, 1 - есть расхождения.
"""
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC))

# Эмодзи исходов (✅ ♻️ ⚠️ ❌) не влазят в cp1251 консоль Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from config_load_router import detect_load_variant, load_catalog, format_load_result  # noqa: E402
from external_report_loader import (  # noqa: E402
    read_external_meta,
    delete_external_object,
    find_external_object,
)

BASE = r"C:\1C_LLM\LoadDoc"

# (каталог, ожидаемый вариант или "error")
DETECT_CASES = [
    ("Test1_Otchet", "external_report"),
    ("Test3_Otchet_Null", "external_report"),
    ("TSD_0", "external_processing"),
    ("TSD_R", "extension"),
    ("BGU2", "configuration"),
    ("__каталога_нет__", "error"),
]

failures = []


def check_detection():
    print("=" * 72)
    print("1. Определение варианта загрузки (узлы T1..T6, только корневой каталог)")
    print("=" * 72)
    for name, expected in DETECT_CASES:
        path = str(Path(BASE) / name)
        detection = detect_load_variant(path)
        got = detection.get("variant") if detection.get("success") else "error"
        ok = got == expected
        failures.extend([] if ok else [f"{name}: ожидался {expected}, получен {got}"])
        mark = "OK " if ok else "FAIL"
        if detection.get("success"):
            print(f"[{mark}] {name:24} -> {detection['variant']:20} xml={Path(detection['xml_path']).name}")
        else:
            print(f"[{mark}] {name:24} -> {detection['error']}")

    # Каталог, который не подходит ни одному загрузчику: XML с чужим корневым тегом.
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "Random.xml").write_text('<?xml version="1.0"?><Objects/>', encoding="utf-8")
        detection = detect_load_variant(tmp)
        ok = not detection.get("success")
        failures.extend([] if ok else ["временный каталог: ожидался отказ, получен вариант загрузки"])
        print(f"[{'OK ' if ok else 'FAIL'}] {'<временный каталог>':24} -> {detection.get('error')}")


def check_loading():
    print()
    print("=" * 72)
    print("2. Точка входа load_catalog: четыре исхода (вариант 3 - внешний отчёт)")
    print("=" * 72)
    # Тестовые объекты не должны остаться в БД от предыдущего прогона, иначе первая
    # проверка вместо "loaded" даст "duplicate".
    for name in ("Test1_Otchet", "Test3_Otchet_Null"):
        meta = read_external_meta(str(Path(BASE) / name))
        if meta.get("success") and meta.get("uuid"):
            removed = delete_external_object(uuid_val=meta["uuid"], obj_type="external_report")
            if removed.get("success"):
                print(f"⚗️ Подготовка теста {name}: удалена запись ID={removed.get('id')} "
                      f"(bsl_modules удалено: {removed.get('bsl_modules_deleted', 0)})")
            else:
                print(f"⚗️ Подготовка теста {name}: записи в БД нет")

    # Ожидаемые счётчики дочерних данных: (attributes, tabular_sections, forms, form_ext,
    # templates, bsl_modules). У Test3_Otchet_Null каталогов Forms/Templates/Ext нет.
    expected_children = {
        "Test1_Otchet": (36, 3, 1, 1, 1, 1),
        "Test3_Otchet_Null": (0, 0, 0, 0, 0, 0),
    }
    for name, force, expected_status in (
        ("Test1_Otchet", False, "loaded"),
        ("Test1_Otchet", False, "duplicate"),
        ("Test1_Otchet", True, "reloaded"),
        ("Test3_Otchet_Null", False, "loaded"),
        ("Test3_Otchet_Null", False, "duplicate"),
        ("TSD_0", False, "not_implemented"),
        ("TSD_R", False, "not_implemented"),
        ("BGU2", False, "not_implemented"),
    ):
        path = str(Path(BASE) / name)
        result = load_catalog(path, force=force)
        got = result.get("status")
        ok = got == expected_status
        failures.extend([] if ok else [f"{name} force={force}: ожидался {expected_status}, получен {got}"])
        print("-" * 72)
        print(f"[{'OK ' if ok else 'FAIL'}] load_catalog({name}, force={force}) -> {got}")
        print(format_load_result(result))

        # Узлы V12-V13: дочерние данные должны наполнять attributes/tabular_sections/forms/
        # form_ext/templates/bsl_modules, а карточка дубликата (find_external_object) -
        # показывать те же счётчики.
        if name in expected_children and result.get("uuid"):
            expected = expected_children[name]
            found = find_external_object(result["uuid"], "external_report") or {}
            got_children = (found.get("attributes_count", -1),
                            found.get("tabular_sections_count", -1),
                            found.get("forms_count", -1),
                            found.get("form_ext_count", -1),
                            found.get("templates_count", -1),
                            found.get("bsl_modules_count", -1))
            children_ok = got_children == expected
            if not children_ok:
                failures.append(f"{name}: дочерние данные {got_children}, ожидалось {expected}")
            print(f"[{'OK ' if children_ok else 'FAIL'}] дочерние данные {name}: "
                  f"attributes={got_children[0]}, tabular_sections={got_children[1]}, "
                  f"forms={got_children[2]}, form_ext={got_children[3]}, "
                  f"templates={got_children[4]}, bsl_modules={got_children[5]} "
                  f"(ожидалось {expected})")

    # Прогон не должен оставлять следов в БД: удаляем тестовые записи за собой.
    for name in ("Test1_Otchet", "Test3_Otchet_Null"):
        meta = read_external_meta(str(Path(BASE) / name))
        if meta.get("success") and meta.get("uuid"):
            delete_external_object(uuid_val=meta["uuid"], obj_type="external_report")
    print("-" * 72)
    print("🧹 Тестовые записи Test1_Otchet и Test3_Otchet_Null удалены из БД.")


def main():
    check_detection()
    if "--with-load" in sys.argv:
        check_loading()
    print()
    print("=" * 72)
    if failures:
        print(f"❌ РАСХОЖДЕНИЯ ({len(failures)}):")
        for f in failures:
            print("  -", f)
        return 1
    print("✅ Все проверки совпали с нормативом.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
