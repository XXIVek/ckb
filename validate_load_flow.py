#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка контракта загрузки load_1c_catalog_tool на тестовых каталогах.

Норматив: docs/config-scenarios/FLOWCHART_1c-configurations-core.md (раздел 10).

Запуск:
    python validate_load_flow.py            - только определение варианта + инвариант вида (в БД
                                              ничего не меняется)
    python validate_load_flow.py --with-load - плюс загрузка внешних отчётов Test1_Otchet и
      Test3_Otchet_Null и внешней обработки TSD_0 (узел V22) с проверкой дочерних данных
      (attributes, tabular_sections, forms, form_ext, templates, bsl_modules) и вида строки
      заголовка; тестовые записи удаляются из БД после прогона.
    Раздел 3 - инвариант вида: object_kind ↔ containedobject_classid, parent_type детей и
    целевые типы ссылок (ExternalReport / ExternalProcessing) обязаны совпадать.

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
    print("2. Точка входа load_catalog: четыре исхода (внешний отчёт и внешняя обработка)")
    print("=" * 72)
    # Тестовые объекты не должны остаться в БД от предыдущего прогона, иначе первая
    # проверка вместо "loaded" даст "duplicate". Вид строки берём из самого каталога (R1):
    # с узла V22 в прогон входит и внешняя обработка TSD_0.
    for name in ("Test1_Otchet", "Test3_Otchet_Null", "TSD_0"):
        meta = read_external_meta(str(Path(BASE) / name))
        if meta.get("success") and meta.get("uuid"):
            removed = delete_external_object(
                uuid_val=meta["uuid"], obj_type=meta.get("object_type") or "external_report")
            if removed.get("success"):
                print(f"⚗️ Подготовка теста {name}: удалена запись ID={removed.get('id')} "
                      f"(bsl_modules удалено: {removed.get('bsl_modules_deleted', 0)})")
            else:
                print(f"⚗️ Подготовка теста {name}: записи в БД нет")

    # Ожидаемые счётчики дочерних данных: (attributes, tabular_sections, forms, form_ext,
    # templates, bsl_modules). У Test3_Otchet_Null каталогов Forms/Templates/Ext нет.
    # TSD_0 — узел V22: реальная внешняя обработка; дочерние таблицы те же, что у отчёта,
    # отличается только вид строки заголовка (object_kind='external_processing').
    expected_children = {
        "Test1_Otchet": (36, 3, 1, 1, 1, 1),
        "Test3_Otchet_Null": (0, 0, 0, 0, 0, 0),
        "TSD_0": (35, 2, 6, 6, 3, 1),
    }
    for name, force, expected_status in (
        ("Test1_Otchet", False, "loaded"),
        ("Test1_Otchet", False, "duplicate"),
        ("Test1_Otchet", True, "reloaded"),
        ("Test3_Otchet_Null", False, "loaded"),
        ("Test3_Otchet_Null", False, "duplicate"),
        # Узел V22: внешняя обработка перестала быть заглушкой — TSD_0 загружается.
        ("TSD_0", False, "loaded"),
        ("TSD_0", False, "duplicate"),
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
            # вид строки берём из варианта, определённого точкой входа: для обработки
            # find_external_object читает object_kind и счётчики той же строки заголовка.
            found = find_external_object(
                result["uuid"], result.get("variant") or "external_report") or {}
            got_children = (found.get("attributes_count", -1),
                            found.get("tabular_sections_count", -1),
                            found.get("forms_count", -1),
                            found.get("form_ext_count", -1),
                            found.get("templates_count", -1),
                            found.get("bsl_modules_count", -1))
            children_ok = got_children == expected
            if not children_ok:
                failures.append(f"{name}: дочерние данные {got_children}, ожидалось {expected}")
            # Узел V22: строка заголовка обязана быть заявленного вида — иначе весь разбор
            # (обогащение, сводка, карточка) описывал бы обработку как отчёт.
            want_kind = result.get("variant") or "external_report"
            kind_ok = found.get("object_kind") == want_kind and not found.get("kind_mismatch")
            if not kind_ok:
                failures.append(f"{name}: object_kind={found.get('object_kind')!r} "
                                f"при ожидаемом {want_kind} (kind_mismatch="
                                f"{found.get('kind_mismatch')})")
            print(f"[{'OK ' if children_ok else 'FAIL'}] дочерние данные {name}: "
                  f"attributes={got_children[0]}, tabular_sections={got_children[1]}, "
                  f"forms={got_children[2]}, form_ext={got_children[3]}, "
                  f"templates={got_children[4]}, bsl_modules={got_children[5]} "
                  f"(ожидалось {expected})")
            print(f"[{'OK ' if kind_ok else 'FAIL'}] вид строки заголовка {name}: "
                  f"object_kind={found.get('object_kind')!r} (ожидался {want_kind})")

    # Узел V22: инвариант вида считается до уборки — пока тестовые строки (в том числе
    # внешняя обработка TSD_0) ещё в БД.
    check_kind_invariant()

    # Прогон не должен оставлять следов в БД: удаляем тестовые записи за собой.
    # Вид строки (отчёт/обработка) берём из каталога — с узла V22 это разные виды.
    for name in ("Test1_Otchet", "Test3_Otchet_Null", "TSD_0"):
        meta = read_external_meta(str(Path(BASE) / name))
        if meta.get("success") and meta.get("uuid"):
            delete_external_object(uuid_val=meta["uuid"],
                                   obj_type=meta.get("object_type") or "external_report")
    print("-" * 72)
    print("🧹 Тестовые записи Test1_Otchet, Test3_Otchet_Null и TSD_0 удалены из БД.")


def check_kind_invariant():
    """Узел V22: вид строки заголовка не может расходиться с ClassId и с parent_type детей.

    Проверяются три инварианта по всей БД, а не по одному каталогу:
      1. object_kind ↔ containedobject_classid (одна и та же выгрузка, два разных места
         разбора: корневой элемент XML и InternalInfo) — расхождение означает, что вид
         строки неверен и весь разбор (обогащение, сводка, карточка) описывает не тот объект;
      2. parent_type дочерних строк (forms, form_ext, templates, bsl_modules) обязан
         совпадать с object_kind родителя; у attributes/tabular_sections колонки parent_type
         нет - их вид определяется родителем через FK на external_report(uuid), а среди
         строк обогащения колонка есть у config_aliases и config_snippets
         (config_cross_references ссылается только на parent_uuid);
      3. целевой тип ссылок на сам объект: ExternalReport у обработки и ExternalProcessing
         у отчёта быть не может (config_aliases.active, config_cross_references).

    Пустой (NULL) containedobject_classid в инвариант 1 не попадает: колонка имеет тип uuid,
    пустое значение выгрузки пишется как NULL, вид в этом случае подтверждён только корневым
    элементом (R1), и загрузчик обязан предупредить, а не отказать (см. _check_object_kind).
    """
    print()
    print("=" * 72)
    print("3. Инвариант вида: object_kind ↔ ClassId ↔ parent_type ↔ target_type")
    print("=" * 72)
    from external_db import connect
    from external_meta_parser import OBJECT_CLASS_IDS

    cases = " ".join(
        f"WHEN '{kind}' THEN '{str(cls).lower()}'" for kind, cls in OBJECT_CLASS_IDS.items()
    )
    queries = [
        ("вид строки вне словаря (NULL или неизвестный)",
         """SELECT COUNT(*) FROM external_report
            WHERE object_kind IS NULL
               OR object_kind NOT IN ('external_report', 'external_processing')"""),
        ("object_kind противоречит containedobject_classid",
         f"""SELECT COUNT(*) FROM external_report
             WHERE COALESCE(lower(btrim(containedobject_classid::text)), '') <> ''
               AND lower(btrim(containedobject_classid::text)) <>
                   CASE COALESCE(object_kind, '') {cases}
                       ELSE lower(btrim(containedobject_classid::text)) END"""),
        ("дочерние строки с parent_type не вида родителя",
         """SELECT COUNT(*) FROM forms c JOIN external_report e ON e.uuid = c.parent_uuid
            WHERE c.parent_type IS DISTINCT FROM e.object_kind
            UNION ALL
            SELECT COUNT(*) FROM form_ext c JOIN external_report e ON e.uuid = c.parent_uuid
            WHERE c.parent_type IS DISTINCT FROM e.object_kind
            UNION ALL
            SELECT COUNT(*) FROM templates c JOIN external_report e ON e.uuid = c.parent_uuid
            WHERE c.parent_type IS DISTINCT FROM e.object_kind
            UNION ALL
            SELECT COUNT(*) FROM bsl_modules c JOIN external_report e ON e.uuid = c.parent_uuid
            WHERE c.parent_type IS DISTINCT FROM e.object_kind"""),
        ("строки обогащения с parent_type не вида родителя",
         """SELECT COUNT(*) FROM config_aliases c JOIN external_report e ON e.uuid = c.parent_uuid
            WHERE c.parent_type IS DISTINCT FROM e.object_kind
            UNION ALL
            SELECT COUNT(*) FROM config_snippets c JOIN external_report e ON e.uuid = c.parent_uuid
            WHERE c.parent_type IS DISTINCT FROM e.object_kind"""),
        ("целевой тип ссылок на сам объект не вида объекта",
         """SELECT COUNT(*) FROM config_aliases c JOIN external_report e ON e.uuid = c.parent_uuid
            WHERE c.active AND (
                  (e.object_kind = 'external_processing' AND c.target_type = 'ExternalReport')
               OR (e.object_kind = 'external_report' AND c.target_type = 'ExternalProcessing'))
            UNION ALL
            SELECT COUNT(*) FROM config_cross_references c
            JOIN external_report e ON e.uuid = c.parent_uuid
            WHERE (e.object_kind = 'external_processing' AND c.target_type = 'ExternalReport')
               OR (e.object_kind = 'external_report' AND c.target_type = 'ExternalProcessing')"""),
    ]
    conn = connect()
    cur = conn.cursor()
    try:
        for title, sql in queries:
            cur.execute(sql)
            bad = sum(int(row[0]) for row in cur.fetchall())
            ok = bad == 0
            if not ok:
                failures.append(f"инвариант вида: {title} — нарушений {bad}")
            print(f"[{'OK ' if ok else 'FAIL'}] {title}: нарушений {bad}")
        cur.execute("""SELECT object_kind, COUNT(*) FROM external_report
                       GROUP BY object_kind ORDER BY object_kind""")
        print("    заголовков в БД по видам:",
              ", ".join(f"{k or 'NULL'}={n}" for k, n in cur.fetchall()) or "записей нет")
    finally:
        conn.close()


def main():
    check_detection()
    if "--with-load" in sys.argv:
        # Инвариант вида считается внутри check_loading - пока тестовые строки ещё в БД.
        check_loading()
    else:
        check_kind_invariant()
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
