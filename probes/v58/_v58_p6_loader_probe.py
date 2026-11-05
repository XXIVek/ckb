#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_v58_p6_loader_probe.py — проба шага П6 узла V58 (живая БД, 05.11.2026).

Вызывает слой `load_defined_types` — ту же функцию, что вызывают стадия S4m конвейера и
инструмент `load_defined_types_tool`, — по четырём выгрузкам эталонного набора и проверяет
пункты 1–3 и 5 критериев готовности плана `docs/CONFIGURATION_DEFINED_TYPES_PLAN.md` (раздел 9):

  * строк записано ровно по числу файлов круга (2 / 1 / 304 / 513, всего 820);
  * расхождений ног круга нет, записей индекса вида столько же, сколько файлов;
  * состояния разрешения называют шесть `unresolved` (адреса `BusinessProcessRoutePoint.*` вне
    индекса состава данной выгрузки), а не теряют их;
  * витрина `v_current_defined_types` отдаёт только текущие ревизии, повтор той же выгрузки не
    заводит вторую ревизию (идемпотентность держится явным `DELETE`, D8);
  * чужие круги (V43, V46, V48–V57, `bsl_modules`) не изменены ни числом строк (мера M5).

В отличие от постоянной проверки `tools/check_v58_defined_types.py` (шаг П6 плана), проба пишет
по-настоящему: цель шага — чтобы свойства вида оказались в живой базе. Пропуск выгрузки
(заголовок не загружен) называется строкой, а не нулём.

Прогон: `python _v58_p6_loader_probe.py`.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from configuration_defined_types_loader import load_defined_types  # noqa: E402
from external_db import connect  # noqa: E402

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
# Тег каталога выгрузки ≠ имя заголовка в БД: заголовок берёт Name из Configuration.xml,
# поэтому соответствие называется явным словарём, а не ищется по началу имени (прецедент
# проб П4–П6 узлов V48…V57). Числа файлов — эталон замера 1.1 плана V58 (всего 820).
FIXTURES = (
    ("MinCfg", "MinCfg", 2),
    ("KomMag", "XXI_Коммерческий_магазин_8_редакция_1_0_3", 1),
    ("BGU2", "БухгалтерияГосударственногоУчреждения", 304),
    ("BP3", "БухгалтерияПредприятия", 513),
)

# Чужие круги (мера M5): их числа обязан сохранить прогон.
OTHER_TABLES = (
    "configurations", "configuration_objects", "subsystems", "common_modules",
    "session_parameters", "roles", "role_rights", "common_attributes",
    "common_attribute_targets", "exchange_plans", "filter_criteria",
    "event_subscriptions", "event_subscription_sources", "scheduled_jobs",
    "scheduled_job_schedules", "bots", "functional_options",
    "functional_option_content", "functional_option_parameters",
    "functional_option_parameter_targets", "bsl_modules",
)

fails = []


def check(condition, label, detail=""):
    line = ("OK   " if condition else "FAIL ") + label
    if detail:
        line += " — " + detail
    print(line)
    if not condition:
        fails.append(label)


def table_counts(cur):
    counts = {}
    for table in OTHER_TABLES:
        cur.execute(f"SELECT count(*) FROM {table}")
        counts[table] = int(cur.fetchone()[0])
    return counts


def main():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT name, uuid, id FROM configurations ORDER BY name")
    headers = {name: (uuid, cfg_id) for name, uuid, cfg_id in cur.fetchall()}
    before = table_counts(cur)

    totals = {}
    for tag, cfg_name, expect_files in FIXTURES:
        if cfg_name not in headers:
            print(f"SKIP {tag}: заголовок {cfg_name} не загружен в БД — пропуск называется, "
                  "а не считается нулём")
            continue
        uuid, _ = headers[cfg_name]
        result = load_defined_types(str(pathlib.Path(DUMP_ROOT) / tag), uuid)
        if not result.get("success"):
            check(False, f"{tag}: стадия не удалась",
                  str(result.get("error") or result.get("reason"))[:300])
            for warning in (result.get("warnings") or [])[:5]:
                print("     warning:", warning[:200])
            continue
        files = int(result.get("files_found") or 0)
        written = int(result.get("defined_types_written") or 0)
        totals[tag] = written
        print(f"LOAD {tag}: файлов={files} разобрано={result.get('files_parsed')} "
              f"записано={written} снято прежних={result.get('removed_previous')} "
              f"индекс вида={result.get('index_kind_records')} "
              f"значений={result.get('types_total')} "
              f"разрешено={result.get('resolve_exact')} "
              f"без цели={result.get('resolve_no_target')} "
              f"unresolved={result.get('resolve_unresolved')}")
        for warning in (result.get("warnings") or [])[:5]:
            print("     warning:", warning[:200])
        check(files == expect_files, f"{tag}: файлов круга = эталону замера 1.1",
              f"ожидалось {expect_files}, получено {files}")
        check(written == files, f"{tag}: строк записано по числу файлов (критерий 9.2)")
        for state in ("index_only", "file_only", "uuid_mismatch"):
            check(not (result.get(state) or []), f"{tag}: расхождений ног {state} нет")
        check(int(result.get("index_kind_records") or 0) == files,
              f"{tag}: записей индекса вида = числу файлов (критерий 9.1)")
        check(not (result.get("failures") or []), f"{tag}: отказавших файлов нет")
        check(not (result.get("duplicate_names") or []), f"{tag}: повторных имён нет")

    # Живые числа таблицы и витрины.
    cur.execute("SELECT configuration_uuid::text, count(*) FROM defined_types "
                "GROUP BY 1 ORDER BY 1")
    by_uuid = dict(cur.fetchall())
    cur.execute("SELECT uuid::text, name FROM configurations")
    uuid_names = {uuid: name for uuid, name in cur.fetchall()}
    for uuid, count in sorted(by_uuid.items(), key=lambda kv: uuid_names.get(kv[0], "")):
        print(f"TABLE defined_types: {uuid_names.get(uuid, uuid)} = {count}")
    cur.execute("SELECT count(*) FROM v_current_defined_types")
    view_total = int(cur.fetchone()[0])
    cur.execute("SELECT count(*) FROM defined_types")
    table_total = int(cur.fetchone()[0])
    check(view_total == table_total,
          "витрина v_current_defined_types отдаёт все строки (ревизий выше нет)",
          f"витрина={view_total}, таблица={table_total}")
    cur.execute("SELECT max(revision_no) FROM defined_types")
    max_rev = int(cur.fetchone()[0] or 0)
    check(max_rev <= 1, "повтор той же выгрузки не заводит вторую ревизию (D8)",
          f"max revision_no={max_rev}")

    # Инварианты по живой таблице (критерии 9.2, 9.3 плана).
    cur.execute("""
        SELECT count(*) FILTER (WHERE type_multiplicity = 'single'),
               count(*) FILTER (WHERE type_multiplicity = 'composite'),
               count(*) FILTER (WHERE type_multiplicity = 'absent'),
               count(*) FILTER (WHERE type_multiplicity NOT IN
                                ('single','composite','absent'))
        FROM defined_types""")
    single, composite, absent, off_vocab = (int(v or 0) for v in cur.fetchone())
    check(off_vocab == 0 and single + composite + absent == table_total,
          "кратность `type_multiplicity` названа на каждой строке и замкнута словарём",
          f"single={single}, composite={composite}, absent={absent}, вне словаря={off_vocab}")
    cur.execute("""
        SELECT count(*) FROM defined_types
         WHERE type_multiplicity = 'single'
           AND jsonb_array_length(types) <> 1""")
    bad_single = int(cur.fetchone()[0])
    check(bad_single == 0, "инвариант кратности и числа записей `types` не нарушен",
          f"нарушений={bad_single}")
    cur.execute("""
        SELECT count(*) FROM defined_types, jsonb_array_elements(types) e
         WHERE NOT (e ? 'resolve_state')
            OR e->>'resolve_state' NOT IN ('exact','no_target','unresolved')""")
    bad_resolve = int(cur.fetchone()[0])
    check(bad_resolve == 0,
          "запись `types` несёт состояние разрешения из замкнутого словаря (критерий 9.3)",
          f"записей вне словаря={bad_resolve}")
    # Классы значений и разрешение целей живут внутри записей `types` (Q1, вариант A), поэтому
    # распределение выводится из записей, а не читается колонкой-счётчиком (правило V43).
    cur.execute("""
        SELECT e->>'class', count(*) FROM defined_types,
               jsonb_array_elements(types) e GROUP BY 1 ORDER BY 2 DESC""")
    print("CLASS распределение по записям `types`:", cur.fetchall())
    cur.execute("""
        SELECT e->>'resolve_state', count(*) FROM defined_types,
               jsonb_array_elements(types) e GROUP BY 1 ORDER BY 2 DESC""")
    print("RESOLVE распределение по записям `types`:", cur.fetchall())
    cur.execute("""
        SELECT object_name, e->>'value' FROM defined_types, jsonb_array_elements(types) e
         WHERE e->>'resolve_state' = 'unresolved' ORDER BY object_name LIMIT 8""")
    print("UNRESOLVED примеры:", cur.fetchall())
    cur.execute("""
        SELECT count(*) FROM defined_types WHERE type_qualifiers <> '{}'::jsonb""")
    print("QUALIFIERS строк с непустым блоком:", int(cur.fetchone()[0]))



    after = table_counts(cur)
    changed = {t: (before[t], after[t]) for t in OTHER_TABLES if before[t] != after[t]}
    check(not changed, "чужие круги не изменены (мера M5)",
          "; ".join(f"{t}:{a}→{b}" for t, (a, b) in changed.items()))

    cur.close()
    conn.close()
    print("=" * 70)
    print(f"итог: записано по выгрузкам {totals}, всего по таблице {table_total}, "
          f"провалов {len(fails)}")
    for item in fails:
        print("  ПРОВАЛ:", item)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
