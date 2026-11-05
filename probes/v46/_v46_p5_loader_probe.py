#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба узла V46 П5: загрузчик свойств дочерних объектов (стадия S4).

Чем отличается от `_v46_p4_writer_probe.py`: та проба проверяла писателей на разборе из
памяти и записывала в транзакции с откатом. Здесь проверяется СЛОЙ: закрытость контракта,
отказ по незнакомому виду и по чужому uuid, круг снятых строк (идемпотентность через явный
`DELETE`, а не через новую ревизию — D8), одинаковый штамп одной загрузки (M2), связь
`subsystem_content.object_uuid` с индексом состава (граница модели: цепочка по uuid, а не по
`full_name`), и то, что тексты модулей без просьбы не пишутся, а `content_loaded` при этом
остаётся false (D6, D7).

Записи остаются в живой базе: загрузчик фиксирует транзакции сам (иначе стадия не была бы
стадией). Проба убирает за собой явно в конце и требует нулей до и после — состояние четырёх
таблиц до прогона снимается как базовое.

Запуск:

    python _v46_p5_loader_probe.py [MinCfg|BGU2|BP3] [texts]

По умолчанию MinCfg: полная выгрузка с 609 записями индекса. BGU2/BP3 — те же проверки на
полных конфигурациях (медленно, но это тот же путь кода); тексты модулей на них проверяются
только с явным `texts`, потому что это 188–294 МБ вставки (замер 2.6 плана).
"""
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from configuration_load_contract import (  # noqa: E402
    CHILD_NOT_IMPLEMENTED,
    CHILD_SECTION_HEADER,
    CHILD_KINDS,
    CHILD_NOT_IMPLEMENTED,
    CHILD_TABLES,
    STATUS_ERROR,
    STATUS_OK,
    child_module_content_defaults,
    child_object_kind_defaults,
    child_objects_defaults,
    format_child_object_lines,
)
from configuration_object_properties_loader import (  # noqa: E402
    COMMON_MODULE_OBJECT_TYPE,
    COMMON_MODULE_PARENT_TYPE,
    COMMON_MODULE_SLOT_TYPE,
    TABLES_BY_KIND,
    load_object_properties,
    normalize_kinds,
    remove_common_module_texts,
    remove_object_properties,
)
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
# Конвейер первого слоя: стадия S4 вызывается им же, поэтому проба проверяет и текст
# карточки (`format_load_result`), а не только машинную часть ответа стадии.
from config_load_router import format_load_result, load_catalog  # noqa: E402
from external_db import connect  # noqa: E402

DUMP_NAMES = ("MinCfg", "BGU2", "BP3")
DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMP_HINT = {
    "MinCfg": "Минимальная конфигурация",
    "BGU2": "Бухгалтерия для государственных учреждений",
    "BP3": "Бухгалтерия предприятия 3",
}

PASSED = 0
FAILED = 0
NOTES: List[str] = []


def check(name: str, ok: bool, detail: Any = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + (((" — " + str(detail)) if detail else "")))
    else:
        FAILED += 1
        print("  [FAIL] " + name + (((" — " + str(detail)) if detail else "")))


def note(text: str) -> None:
    NOTES.append(text)
    print("       " + text)


def one(cur, sql: str, params: Optional[List] = None):
    cur.execute(sql, params or [])
    row = cur.fetchone()
    return row[0] if row else None


def table_counts(cur, configuration_uuid: str, tables: tuple = CHILD_TABLES) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for table in tables:
        counts[table] = int(one(cur, f"SELECT count(*) FROM {table} "
                                   "WHERE configuration_uuid = %s::uuid",
                                [str(configuration_uuid)]) or 0)
    return counts


def module_text_counts(cur, configuration_uuid: str) -> Dict[str, int]:
    return {
        "rows": int(one(cur, "SELECT count(*) FROM bsl_modules WHERE configuration_uuid = "
                             "%s::uuid AND parent_type = %s",
                        [str(configuration_uuid), COMMON_MODULE_PARENT_TYPE]) or 0),
        "external": int(one(cur, "SELECT count(*) FROM bsl_modules WHERE parent_type = "
                                 "'external_report'") or 0),
    }


def physical_module_files(dump_dir: Path) -> int:
    """Сколько `.bsl` модулей лежит физически — независимая ожидаемая величина текстов."""
    return len(list((dump_dir / "CommonModules").rglob("Ext/Module.bsl"))) \
        if (dump_dir / "CommonModules").is_dir() else 0


# Каталог конфигурации, которой в базе нет (для отказа «заголовка нет»). Есть среди выгрузок
# и не загружен — подходит; если оператор его загрузит, проба скажет об этом прямо, а не
# пройдёт молча.
UNLOADED_DUMP = "UNF3"


def check_contract_shape(report: Dict[str, Any], label: str) -> None:
    """Закрытость контракта (C1): ключи ответа — ровно ключи словаря состояния стадии."""
    base = child_objects_defaults()
    check(f"{label}: ответ содержит ровно ключи контракта стадии",
          sorted(report) == sorted(base),
          "лишнее: " + ", ".join(sorted(set(report) - set(base))) +
          "; нет: " + ", ".join(sorted(set(base) - set(report))))
    for kind in CHILD_KINDS:
        part = report.get("kinds") or {}
        check(f"{label}: kinds содержит ровно два вида стадии S4",
              sorted(part) == sorted(CHILD_KINDS), ", ".join(sorted(part)))
        check(f"{label}: {kind}: ключи группы совпадают с child_object_kind_defaults",
              sorted(part.get(kind) or {}) == sorted(child_object_kind_defaults()),
              ", ".join(sorted(set((part.get(kind) or {})) - set(child_object_kind_defaults()))))
    check(f"{label}: module_content содержит ровно ключи контракта текстов",
          sorted(report.get("module_content") or {}) == sorted(child_module_content_defaults()),
          ", ".join(sorted(set((report.get("module_content") or {}))
                           - set(child_module_content_defaults()))))


def check_text_render(report: Dict[str, Any], label: str) -> None:
    """Форматёр стадии работает по закрытому контракту и называет границы (C3, раздел 8)."""
    try:
        lines = format_child_object_lines(report, indent="")
    except Exception as exc:  # noqa: BLE001 — текст отказа тоже обязан быть прочитан
        check(f"{label}: форматёр не падает", False, str(exc))
        return
    joined = "\n".join(lines)
    check(f"{label}: форматёр дал непустой текст", bool(lines), f"{len(lines)} строк")
    if not report.get("success"):
        # Отказ форматёр заканчивает причиной: других строк у несделанной стадии нет, и
        # требовать от неё описания состояний — значит выдумывать несуществующий состав.
        check(f"{label}: текст отказа называет причину один раз",
              any("Стадия не выполнена" in line or "Стадия не удалась" in line
                  for line in lines), lines[:1])
        return
    check(f"{label}: текст называет незакрытую часть содержимого дочерних объектов",
          CHILD_NOT_IMPLEMENTED in joined)
    if not (report.get("module_content") or {}).get("requested"):
        check(f"{label}: текст называет, что тексты модулей не запрашивались",
              "не запрашивались" in joined)
    else:
        check(f"{label}: текст называет запись текстов по parent_uuid общего модуля",
              "uuid самого общего модуля" in joined)


def check_refusals(cur, dump_dir: Path, configuration_uuid: str,
                   baseline: Dict[str, int], unloaded_dir: Optional[Path]) -> None:
    """Отказ слоя обязан называть причину и не менять базу (C2, C5)."""
    print("\n=== отказы и граница «вид не просили» ===")
    before = table_counts(cur, configuration_uuid)
    check("до отказов круг таблиц совпадает с базовым", before == baseline, str(before))

    bad = load_object_properties(str(dump_dir), kinds=["subsystem"])
    check("незнакомый вид отклонён, а не сведён к нулям",
          bad["status"] == STATUS_ERROR and not bad["success"], bad["status"])
    check("причина отказа названа текстом", bool(bad["error"]),
          (bad["error"] or "")[:150])
    check_contract_shape(bad, "отказ по виду")
    check_text_render(bad, "отказ по виду")

    empty = load_object_properties(str(dump_dir), kinds=[])
    check("пустой список видов отклонён", empty["status"] == STATUS_ERROR,
          (empty["error"] or "")[:120])

    kinds_tuple, reason = normalize_kinds(["common_modules", "subsystems"])
    check("normalize_kinds приводит к порядку CHILD_KINDS без дублей",
          kinds_tuple == CHILD_KINDS and reason is None, ",".join(kinds_tuple))

    other = "00000000-0000-4000-8000-000000000000"
    mismatch = load_object_properties(str(dump_dir), configuration_uuid=other)
    check("расхождение uuid каталога и переданного — отказ, а не выбор одного",
          mismatch["status"] == STATUS_ERROR and "uuid" in (mismatch["error"] or ""),
          (mismatch["error"] or "")[:150])

    if unloaded_dir and unloaded_dir.is_dir():
        info = configuration_uuid_from_layout(str(unloaded_dir))
        if "uuid" in info:
            if one(cur, "SELECT count(*) FROM configurations WHERE uuid = %s::uuid",
                   [str(info["uuid"])]):
                note(f"конфигурация {UNLOADED_DUMP} уже загружена — проверка «заголовка нет» "
                     "пропущена (состояние базы изменилось)")
            else:
                no_header = load_object_properties(str(unloaded_dir))
                check("без строки заголовка слой отказывает и называет точку входа",
                      no_header["status"] == STATUS_ERROR
                      and "load_1c_catalog_tool" in (no_header["error"] or ""),
                      (no_header["error"] or "")[:150])
    else:
        note(f"выгрузка {UNLOADED_DUMP} не найдена — проверка «заголовка нет» пропущена")

    after = table_counts(cur, configuration_uuid)
    check("ни один отказ не изменил круг таблиц", after == before, f"{before} → {after}")


def check_written(cur, cfg_uuid: str, report: Dict[str, Any],
                  external_baseline: Optional[int] = None) -> Dict[str, int]:
    """Состояние базы против отчёта стадии: числа, ссылки, штамп, границы состояний.

    Отчёт и база проверяются встречно: отчёт не обещает больше, чем легло, база не хранит
    больше, чем названо. Одиночный `changed_at` на четыре таблицы — требование M2;
    `revision_no = 1` — следствие того, что идемпотентность держится снятием, а не
    историей (D8).
    """
    print("\n--- состояние базы против отчёта ---")
    sub = (report["kinds"].get("subsystems") or {})
    cm = (report["kinds"].get("common_modules") or {})
    requested_kinds = report.get("kinds_requested") or []
    checked_tables = [table for kind in requested_kinds
                      for table in TABLES_BY_KIND.get(kind, ())]
    counts = table_counts(cur, cfg_uuid, tuple(checked_tables) or CHILD_TABLES)
    expected = {
        "subsystems": int(sub.get("written") or 0),
        "subsystem_content": int(sub.get("content_total") or 0),
        "common_modules": int(cm.get("written") or 0),
        "common_module_sources": int(cm.get("descriptor_rows") or 0),
    }
    for table in checked_tables:
        check(f"{table}: строк ровно по отчёту", counts[table] == expected[table],
              f"в базе {counts[table]}, отчёт {expected[table]}")
    check("objects_written равна сумме по таблицам запрошенных видов",
          int(report.get("objects_written") or 0) == sum(counts.values()),
          f"отчёт {report.get('objects_written')}, база {sum(counts.values())}")

    for table in CHILD_TABLES:
        others = int(one(cur, f"SELECT count(*) FROM {table} "
                              "WHERE configuration_uuid IS NULL") or 0)
        check(f"{table}: строк без configuration_uuid в базе нет", others == 0, others)
    for table in checked_tables:
        view_rows = int(one(cur, f"SELECT count(*) FROM v_current_{table} "
                                 "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0)
        check(f"{table}: витрина текущего состояния отдаёт записанное",
              view_rows == counts[table], f"витрина {view_rows}, таблицы {counts[table]}")

    # Статистика записанных таблиц (замер 28.10.2026): планировщик не видит строк своей же
    # загрузки, и без ANALYZE счётчик витрины на BGU2 (13 757 ссылок) выполняется 8 мин 25 с
    # вместо 7 мс. Проверка держится `reltuples` — числа, которое пишет именно ANALYZE, а не
    # автовакуум «когда посчитает нужным».
    for table in checked_tables:
        if counts[table] <= 0:
            continue
        reltuples = int(one(cur, "SELECT reltuples::bigint FROM pg_class "
                                 "WHERE relname = %s", [table]) or -1)
        check(f"{table}: загрузка собрала статистику таблицы (reltuples > 0)",
              reltuples > 0, f"reltuples {reltuples}, строк {counts[table]}")

    stamp_sql = "SELECT %s AS t, changed_at, changed_by, revision_no, is_committed FROM "
    stamps = []
    # Круг — таблицы запрошенных видов: частичная загрузка чужие строки не трогает, и их
    # прежняя метка не является второй меткой этой загрузки (проверено пробой: частичная
    # загрузка подсистем оставляет общие модули с меткой предыдущей загрузки — и правильно).
    for table in checked_tables:
        # Имя таблицы — из константы CHILD_TABLES, поэтому подставляется в текст запроса;
        # параметры значений идут через %s (иначе psycopg2 кавычит имя как литерал).
        cur.execute(stamp_sql + table + " WHERE configuration_uuid = %s::uuid",
                    (table, str(cfg_uuid)))
        stamps.extend(cur.fetchall())
    moments = {}
    for row in stamps:
        moments.setdefault(row[1], set()).add(row[0])
    check("одна метка changed_at на все строки одной загрузки (M2)", len(moments) <= 1,
          " | ".join(f"{label} → {', '.join(sorted(tables))}"
                     for label, tables in sorted(moments.items(),
                                                key=lambda pair: str(pair[0])))
          + f" — всего {len(stamps)} строк")
    check("штамп загрузки: changed_by = load, revision_no = 1, is_committed = true",
          all(row[2] == "load" and row[3] == 1 and row[4] is True for row in stamps),
          str(stamps[:1]))

    if "subsystems" in requested_kinds:
        check_subsystem_links(cur, cfg_uuid, sub)
    if "common_modules" in requested_kinds:
        check_descriptor_states(cur, cfg_uuid, report)

    texts = report.get("module_content") or {}
    module_rows = module_text_counts(cur, cfg_uuid)
    if not texts.get("requested"):
        check("без просьбы тексты модулей в bsl_modules не записаны (D6, D7)",
              module_rows["rows"] == 0, module_rows["rows"])
    if external_baseline is not None:
        check("строки модулей внешнего объекта загрузка свойств не трогает",
              module_rows["external"] == external_baseline,
              f"было {external_baseline}, стало {module_rows['external']}")
    return counts


def check_subsystem_links(cur, cfg_uuid: str, sub: Dict[str, Any]) -> None:
    """Ссылки подсистем: родитель строки, указание на запись индекса, судьба неразрешённых.

    Модель таблицы (П1): строка ссылки несёт `subsystem_object_uuid` (на кого ссылается
    подсистема-владелец) и `target_object_uuid` (на что указывает `Content`), плюс текстовые
    `subsystem_full_name`/`target_full_name` — цепочка по имени по D8. Отдельной колонки
    `parent_uuid` здесь нет, и проверка держится именно на фактических колонках.
    """
    broken_parent = int(one(
        cur, "SELECT count(*) FROM subsystem_content sc WHERE sc.configuration_uuid = "
             "%s::uuid AND NOT EXISTS (SELECT 1 FROM subsystems s WHERE "
             "s.configuration_uuid = sc.configuration_uuid AND s.object_uuid = "
             "sc.subsystem_object_uuid AND s.revision_no = sc.revision_no)",
        [str(cfg_uuid)]) or 0)
    check("subsystem_content.subsystem_object_uuid ссылается на строку этой загрузки",
          broken_parent == 0, broken_parent)

    # Граница модели: `target_object_uuid` — нормализованный id записи индекса. У вложенной
    # записи индекса отдельного uuid нет (`configuration_objects.uuid` заполнен только у
    # записей верхнего уровня), поэтому сравнение идёт по снятию суффикса — ровно так же,
    # как делает `norm_object_id` разбора. Это и есть открытая граница модели: ссылка на
    # вложенный объект даёт uuid его родителя, а не отдельный идентификатор.
    outside_index = int(one(
        cur, "SELECT count(*) FROM subsystem_content sc WHERE sc.configuration_uuid = "
             "%s::uuid AND sc.resolved AND NOT EXISTS (SELECT 1 FROM configuration_objects o "
             "WHERE o.configuration_id = (SELECT id FROM configurations WHERE uuid = %s::uuid) "
             "AND split_part(o.object_id, '.', 1) = sc.target_object_uuid::text)",
        [str(cfg_uuid), str(cfg_uuid)]) or 0)
    check("разрешённая ссылка указывает на запись индекса (после нормализации id)",
          outside_index == 0, outside_index)

    unresolved_rows = int(one(
        cur, "SELECT count(*) FROM subsystem_content WHERE configuration_uuid = %s::uuid "
             "AND NOT resolved", [str(cfg_uuid)]) or 0)
    check("неразрешённые ссылки остались строками с resolved=false и текстом ссылки",
          unresolved_rows == int(sub.get("content_unresolved") or 0),
          f"строк {unresolved_rows}, отчёт {sub.get('content_unresolved')}")

    unresolved_stored = int(one(
        cur, "SELECT coalesce(sum(jsonb_array_length(content_unresolved)), 0) FROM "
             "subsystems WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0)
    check("неразрешённые ссылки сохранены и в исходном jsonb объекта, а не брошены (D3)",
          unresolved_stored == int(sub.get("content_unresolved") or 0),
          f"в jsonb {unresolved_stored}, отчёт {sub.get('content_unresolved')}")


def check_descriptor_states(cur, cfg_uuid: str, report: Dict[str, Any]) -> None:
    """Дескрипторы модулей: пара «путь ↔ состояние» и признак загруженного текста."""
    bad_path_state = int(one(
        cur, "SELECT count(*) FROM common_module_sources WHERE configuration_uuid = "
             "%s::uuid AND file_path IS NULL AND content_state IN "
             "('file','file_not_in_index')", [str(cfg_uuid)]) or 0)
    check("дескрипторы: путь есть у состояний с текстом, и только у них (C-V46-1)",
          bad_path_state == 0, bad_path_state)
    texts = report.get("module_content") or {}
    loaded_true = int(one(cur, "SELECT count(*) FROM common_module_sources WHERE "
                               "configuration_uuid = %s::uuid AND content_loaded",
                          [str(cfg_uuid)]) or 0)
    want_loaded = int(texts.get("written") or 0) if texts.get("requested") else 0
    check("content_loaded = true ровно у тех дескрипторов, чей текст записан (D7)",
          loaded_true == want_loaded, f"true {loaded_true}, записано текстов {want_loaded}")


def check_module_text_rows(cur, cfg_uuid: str, report: Dict[str, Any]) -> None:
    """Строки текстов общих модулей: родитель — uuid самого общего модуля, цепочка — по пути файла.

    Уточнение оператора 28.10.2026: `parent_uuid` заполнен и равен uuid объекта общего модуля
    (`parent_type = 'common_modules'`); модель «`parent_uuid IS NULL` для текстов общих модулей»
    неверна — эта проверка сторожит именно её.
    """
    print("\n--- строки текстов модулей общих модулей ---")
    texts = report.get("module_content") or {}
    rows = int(one(cur, "SELECT count(*) FROM bsl_modules WHERE configuration_uuid = "
                        "%s::uuid AND parent_type = %s",
                   [str(cfg_uuid), COMMON_MODULE_PARENT_TYPE]) or 0)
    # Встречная проверка отчёта и таблицы: в П5 здесь и обнаружилось, что писатель
    # `bsl_modules` не объявлял колонку `configuration_uuid` — загрузчик называл три
    # записанных текста, а в таблице под фильтром конфигурации не было ни одной строки.
    check("bsl_modules: строк ровно столько, сколько названо отчётом",
          rows == int(texts.get("written") or 0),
          f"в таблице {rows}, отчёт {texts.get('written')}")
    orphan_cfg = int(one(cur, "SELECT count(*) FROM bsl_modules WHERE parent_type = %s "
                              "AND configuration_uuid IS NULL",
                         [COMMON_MODULE_PARENT_TYPE]) or 0)
    check("строки текстов общих модулей без configuration_uuid не образуются",
          orphan_cfg == 0, orphan_cfg)
    check("родитель каждой строки — uuid самого общего модуля, а не NULL",
          int(one(cur, "SELECT count(*) FROM bsl_modules WHERE configuration_uuid = "
                       "%s::uuid AND parent_type = %s AND parent_uuid IS NULL",
                  [str(cfg_uuid), COMMON_MODULE_PARENT_TYPE]) or 0) == 0, rows)
    check("parent_type называет таблицу-родителя, module_type — слот вида",
          int(one(cur, "SELECT count(*) FROM bsl_modules WHERE configuration_uuid = "
                       "%s::uuid AND parent_type = %s AND (module_type <> %s OR "
                       "object_type <> %s)",
                  [str(cfg_uuid), COMMON_MODULE_PARENT_TYPE, COMMON_MODULE_SLOT_TYPE,
                   COMMON_MODULE_OBJECT_TYPE]) or 0) == 0)
    orphans = int(one(cur, "SELECT count(*) FROM bsl_modules b WHERE b.configuration_uuid "
                           "= %s::uuid AND b.parent_type = %s AND NOT EXISTS (SELECT 1 FROM "
                           "common_module_sources s WHERE s.configuration_uuid = "
                           "b.configuration_uuid AND s.object_uuid = b.parent_uuid)",
                      [str(cfg_uuid), COMMON_MODULE_PARENT_TYPE]) or 0)
    check("parent_uuid совпадает с object_uuid дескриптора этого модуля", orphans == 0, orphans)
    duplicates = int(one(cur, "SELECT count(*) FROM (SELECT parent_uuid, file_path FROM "
                              "bsl_modules WHERE configuration_uuid = %s::uuid AND "
                              "parent_type = %s GROUP BY parent_uuid, file_path "
                              "HAVING count(*) > 1) d",
                         [str(cfg_uuid), COMMON_MODULE_PARENT_TYPE]) or 0)
    check("цепочка состояний текста — (parent_uuid, file_path, revision_no) без дублей",
          duplicates == 0, duplicates)
    note(f"строк текстов в bsl_modules: {rows}; усечено по отчёту: {texts.get('truncated')}")


def cleanup(cur, cfg_uuid: str) -> Dict[str, int]:
    """Убрать за пробой: четыре таблицы по uuid + тексты общих модулей из `bsl_modules`.

    Снятие фиксируется той же транзакцией, что и проверка нулей после него: без `commit`
    соединение пробы откатило бы очистку при закрытии, и база осталась бы с записанными
    строками — проба обязана возвращать базовое состояние, а не обещать его.
    """
    removed = remove_object_properties(cur, cfg_uuid)
    removed["bsl_modules"] = remove_common_module_texts(cur, cfg_uuid)
    cur.connection.commit()
    return removed


def main() -> int:
    chosen = next((arg for arg in sys.argv[1:] if arg in DUMP_NAMES), "MinCfg")
    dump_dir = DUMP_ROOT / chosen
    if not dump_dir.is_dir():
        print(f"Каталог выгрузки не найден: {dump_dir}")
        return 2
    info = configuration_uuid_from_layout(str(dump_dir))
    if "uuid" not in info:
        print(f"uuid конфигурации из каталога не получен: {info.get('error')}")
        return 2
    cfg_uuid = str(info["uuid"])
    print(f"Проба V46 П5: загрузчик свойств дочерних объектов — {chosen} "
          f"({DUMP_HINT.get(chosen, '')}), uuid={cfg_uuid}")
    print("Загрузчик фиксирует транзакции сам; проба убирает за собой в конце и требует "
          "нулей до и после.")

    conn = connect()
    try:
        cur = conn.cursor()
        baseline = table_counts(cur, cfg_uuid)
        external_baseline = module_text_counts(cur, cfg_uuid)["external"]
        note(f"базовое состояние: {baseline}; строк модулей внешнего объекта: "
             f"{external_baseline}")
        if any(baseline.values()):
            note("в таблицах уже есть строки этой конфигурации — проба идёт по ним же "
                 "(идемпотентность проверяется повторным прогоном)")

        check_refusals(cur, dump_dir, cfg_uuid, baseline, DUMP_ROOT / UNLOADED_DUMP)

        print("\n=== загрузка №1 (тексты модулей не запрошены — состояние по умолчанию) ===")
        report = load_object_properties(str(dump_dir))
        check("загрузка №1 успешна", report["status"] == STATUS_OK and report["success"],
              report.get("error") or report["status"])
        check_contract_shape(report, "загрузка №1")
        check_text_render(report, "загрузка №1")
        counts = check_written(cur, cfg_uuid, report, external_baseline=external_baseline)
        check("провенанс пути назван предупреждением (D-C, граница V31)",
              any("провенанс" in w for w in report["warnings"]))
        first_moment = one(cur, "SELECT max(changed_at) FROM subsystems WHERE "
                                "configuration_uuid = %s::uuid", [str(cfg_uuid)])

        print("\n=== загрузка №2: идемпотентность снятием, а не историей (D8) ===")
        # Пауза в секунду нужна не «ради паузы»: колонка `changed_at` — TIMESTAMP без долей
        # секунды, и две загрузки внутри одной секунды получили бы одну метку. Без паузы
        # проверка «повтор — новое событие» проверяла бы точность часов, а не поведение слоя.
        time.sleep(1.1)
        again = load_object_properties(str(dump_dir))
        check("загрузка №2 успешна", again["status"] == STATUS_OK, again.get("error"))
        removed = {kind: int((part or {}).get("removed_previous") or 0)
                   for kind, part in (again.get("kinds") or {}).items()}
        check("снятые строки названы по каждому виду",
              removed.get("subsystems") == counts["subsystems"] + counts["subsystem_content"]
              and removed.get("common_modules") == counts["common_modules"]
              + counts["common_module_sources"], str(removed))
        counts2 = table_counts(cur, cfg_uuid)
        check("круг таблиц не вырос: повтор той же выгрузки не создаёт дублей",
              counts2 == counts, f"{counts} → {counts2}")
        max_revision = one(cur, "SELECT max(revision_no) FROM subsystems WHERE "
                                "configuration_uuid = %s::uuid", [str(cfg_uuid)])
        check("история состояний не заводится: revision_no остаётся 1", max_revision == 1,
              max_revision)
        second_moment = one(cur, "SELECT max(changed_at) FROM subsystems WHERE "
                                 "configuration_uuid = %s::uuid", [str(cfg_uuid)])
        check("повтор — новое событие (метка сменилась)", second_moment != first_moment,
              f"{first_moment} → {second_moment}")
        check_written(cur, cfg_uuid, again, external_baseline=external_baseline)

        print("\n=== загрузка одного вида: круг снятия ограничен запрошенным ===")
        only_sub = load_object_properties(str(dump_dir), kinds=["subsystems"])
        check("загрузка только подсистем успешна", only_sub["status"] == STATUS_OK,
              only_sub.get("error"))
        after_sub = table_counts(cur, cfg_uuid)
        check("общие модули не уничтожены загрузкой чужого вида",
              after_sub["common_modules"] == counts["common_modules"]
              and after_sub["common_module_sources"] == counts["common_module_sources"],
              str(after_sub))
        cm_part = only_sub["kinds"]["common_modules"]
        check("незапрошенный вид помечен requested=false и даёт нули (C2)",
              not cm_part["requested"] and cm_part["written"] == 0
              and cm_part["removed_previous"] == 0, str(cm_part)[:120])
        check("подсистемы сняты и записаны заново — снятое названо",
              only_sub["kinds"]["subsystems"]["removed_previous"]
              == counts["subsystems"] + counts["subsystem_content"],
              only_sub["kinds"]["subsystems"]["removed_previous"])
        joined = "\n".join(format_child_object_lines(only_sub))
        check("текст называет, что вид не запрашивался", "вид не запрашивался" in joined)
        check_written(cur, cfg_uuid, only_sub, external_baseline=external_baseline)
        run_texts = chosen == "MinCfg" or "texts" in sys.argv[1:]
        if not run_texts:
            note("тексты модулей на этой выгрузке не проверяются (замер 2.6 плана: 188 МБ "
                 "BGU2, 294 МБ BP3); путь текстов проверяется на MinCfg или явным "
                 "аргументом `texts` — молча снимать проверку нельзя, поэтому она названа")
        return _finish(cur, cfg_uuid, dump_dir, counts, external_baseline, run_texts)
    finally:
        conn.close()


def physical_module_stats(dump_dir: Path, code_limit: Optional[int] = None):
    """Независимая величина: сколько файлов модулей лежит и сколько длиннее лимита."""
    root = dump_dir / "CommonModules"
    files = sorted(root.rglob("Ext/Module.bsl")) if root.is_dir() else []
    over = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if code_limit and len(text) > code_limit:
            over += 1
    return len(files), over


def _finish(cur, cfg_uuid: str, dump_dir: Path, counts: Dict[str, int],
            external_baseline: int, run_texts: bool) -> int:
    """Порядок финала пробы: тексты → возврат базового состояния → конвейер → итог.

    Конвейер проверяется ПОСЛЕ очистки намеренно: он обязан записать строки сам, и после
    него строки остаются (снять их — значит оставить конфигурацию без только что
    записанного содержимого). Итог печатается последним всегда, включая случай, когда
    проверка конвейера упала.
    """
    if run_texts:
        _check_texts(cur, cfg_uuid, dump_dir, counts, external_baseline)
    _restore_baseline(cur, cfg_uuid, external_baseline)
    check_pipeline(cur, cfg_uuid, dump_dir, external_baseline)
    return _summary()


def _check_texts(cur, cfg_uuid: str, dump_dir: Path, counts: Dict[str, int],
                 external_baseline: int) -> None:
    """Тексты модулей по просьбе (вторая транзакция D7) и усечение по лимиту (D-LIMIT)."""
    print("\n=== загрузка с текстами модулей (with_module_content=True, D7) ===")
    with_texts = load_object_properties(str(dump_dir), kinds=["common_modules"],
                                        with_module_content=True)
    check("загрузка с текстами успешна", with_texts["status"] == STATUS_OK,
          with_texts.get("error"))
    texts = with_texts["module_content"]
    check("тексты названы запрошенными", texts["requested"] is True)
    physical, _ = physical_module_stats(dump_dir)
    check("записано ровно столько текстов, сколько файлов модулей лежит (независимая величина)",
          texts["written"] == physical, f"файлов {physical}, записано {texts['written']}")
    content_counts = with_texts["kinds"]["common_modules"]["counts_by_content_state"]
    without_text = int(content_counts.get("bin_only") or 0) + \
        int(content_counts.get("indexed_no_file") or 0)
    check("пропущено ровно то, у чего текста нет физически (bin_only, indexed_no_file)",
          texts["skipped"] == without_text,
          f"пропущено {texts['skipped']}, без текста {without_text}")
    check("тексты модулей не породили строк свойств заново",
          table_counts(cur, cfg_uuid, ("common_modules", "common_module_sources"))
          == {table: counts[table] for table in ("common_modules", "common_module_sources")},
          str(table_counts(cur, cfg_uuid)))
    check_module_text_rows(cur, cfg_uuid, with_texts)
    check_written(cur, cfg_uuid, with_texts, external_baseline=external_baseline)
    check_text_render(with_texts, "загрузка с текстами")

    print("\n=== усечение: лимит задаёт вызывающий, D-LIMIT остаётся открытым ===")
    limit = 10
    limited = load_object_properties(str(dump_dir), kinds=["common_modules"],
                                    with_module_content=True, module_code_limit=limit)
    _, over_limit = physical_module_stats(dump_dir, limit)
    limited_texts = limited["module_content"]
    check("лимит назван в контракте", limited_texts["code_limit"] == limit,
          limited_texts["code_limit"])
    check("усечено ровно то число модулей, что длиннее лимита",
          limited_texts["truncated"] == over_limit,
          f"отчёт {limited_texts['truncated']}, файлов длиннее {limit} симв. {over_limit}")
    check("тексты записаны заново, а не добавлены к прежним (снятое названо)",
          limited_texts["removed_previous"] == texts["written"],
          f"снято {limited_texts['removed_previous']}, было {texts['written']}")


def check_pipeline(cur, cfg_uuid: str, dump_dir: Path, external_baseline: int) -> None:
    """Конвейер целиком: стадию S4 вызывает `load_catalog` (force=True по уже загруженному).

    Отдельный инструмент и стадия — один слой, поэтому проверка обязана подтвердить и
    карточку: раздел стадии в тексте есть, граница незакрытой части содержимого названа,
    тексты модулей стадия не читает (D-S4), и стадия S3 (V44) не сломана.
    """
    print("\n=== конвейер: стадия S4 внутри load_catalog (V45 → V46) ===")
    result = load_catalog(str(dump_dir), force=True)
    card = format_load_result(result)
    check("конвейер вернул успех", result.get("success") is True, result.get("error"))
    part = result.get("child_objects") or {}
    check("конвейер вернул раздел S4 закрытым контрактом стадии",
          sorted(part) == sorted(child_objects_defaults()),
          "лишнее: " + ", ".join(sorted(set(part) - set(child_objects_defaults())))
          + "; нет: " + ", ".join(sorted(set(child_objects_defaults()) - set(part))))
    check("стадия S4 конвейера успешна", part.get("status") == STATUS_OK, part.get("error"))
    check("стадия тексты модулей не читает (D-S4)",
          not (part.get("module_content") or {}).get("requested"))
    counts = table_counts(cur, cfg_uuid)
    sub = part.get("kinds", {}).get("subsystems") or {}
    cm = part.get("kinds", {}).get("common_modules") or {}
    check("числа стадии совпаны с тем, что легло в таблицы",
          counts["subsystems"] == int(sub.get("written") or 0)
          and counts["subsystem_content"] == int(sub.get("content_total") or 0)
          and counts["common_modules"] == int(cm.get("written") or 0)
          and counts["common_module_sources"] == int(cm.get("descriptor_rows") or 0),
          f"база {counts}, стадия {sub.get('written')}/{sub.get('content_total')}/"
          f"{cm.get('written')}/{cm.get('descriptor_rows')}")
    check("карточка загрузки содержит раздел стадии S4", CHILD_SECTION_HEADER in card)
    check("карточка называет границу незакрытой части содержимого дочерних объектов",
          CHILD_NOT_IMPLEMENTED in card)
    check("карточка называет, что тексты модулей не запрашивались",
          "не запрашивались" in card)
    root = result.get("root_modules") or {}
    check("стадия S3 (V44) после встраивания S4 работает", root.get("success") is True,
          root.get("error"))
    check("строки модулей внешнего объекта конвейер не трогает",
          module_text_counts(cur, cfg_uuid)["external"] == external_baseline,
          f"ожидалось {external_baseline}")
    note("строки стадии S4 остаются в базе: их записал конвейер, и снимать их после "
         "конвейера — значит оставить конфигурацию без только что записанного содержимого")


def _restore_baseline(cur, cfg_uuid: str, external_baseline: int) -> None:
    """Вернуть базовое состояние: проба не оставляет за собой строк после своих прогонов."""
    print("\n=== очистка за пробой и возврат базового состояния ===")
    removed = cleanup(cur, cfg_uuid)
    note(f"снято: {removed}")
    after = table_counts(cur, cfg_uuid)
    check("после очистки круг таблиц пуст", not any(after.values()), str(after))
    check("тексты общих модулей сняты полностью",
          module_text_counts(cur, cfg_uuid)["rows"] == 0)
    check("строки модулей внешнего объекта не тронуты очисткой",
          module_text_counts(cur, cfg_uuid)["external"] == external_baseline,
          f"ожидалось {external_baseline}")


def _summary() -> int:
    """Итог пробы: число проваленных проверок, а не общее «успешно»."""
    print("\n" + "=" * 72)
    print(f"ИТОГ: пройдено {PASSED}, провалено {FAILED}")
    if FAILED:
        print("Проваленные проверки перечислены выше строками [FAIL]; причина называется")
        print("там же — молчать про них итог не должен.")
    return FAILED


if __name__ == "__main__":
    sys.exit(main())



