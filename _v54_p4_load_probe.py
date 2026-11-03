#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V54, шаг П4: прогон загрузчика `load_scheduled_jobs` на выгрузках.

Запуск:  python _v54_p4_load_probe.py                 # MinCfg и KomMag (малый круг)
         python _v54_p4_load_probe.py BGU2            # одна выгрузка
         python _v54_p4_load_probe.py --big           # четыре, последовательно

Зонд меняет общее состояние БД, поэтому прогоны разных выгрузок НЕ параллелят (правило
слоя). Порядок: загрузка → сверка ответа с замерами плана (разделы 1.1, 2.2, 2.3) →
сверка с СОДЕРЖИМЫМ БД (числа читаются таблицами и витринами, а не ответом загрузчика) →
повторная загрузка той же выгрузки (идемпотентность: снятое равно записанному, новой
ревизии нет) → печать формата карточки `format_scheduled_jobs_lines`.

Ожидаемые числа — те же, что зафиксировали П0 и П3 (`_v54_p3_parse_probe.py`): MinCfg
2 задания / 5 записей расписания, KomMag 1 / 1, BGU2 157 / 143, BP3 186 / 164. Расхождение
ответа с БД является провалом зонда: ответ обязан описывать содержимое базы.

Граница живой базы названа планом (раздел 3): текстов общих модулей в БД ноль, поэтому
состояние объявления обработчика обязано быть `text_unavailable`, а не `declared` — это
граница слоя V46, а не свойство выгрузки (Q8, вариант A).
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from configuration_load_contract import (  # noqa: E402
    SCHEDULED_JOB_CIRCLE_DISCREPANCIES,
    SCHEDULED_JOB_CONTENT_DISCREPANCIES,
    format_scheduled_jobs_lines,
    scheduled_jobs_defaults,
)
from configuration_scheduled_jobs import CIRCLE_DISCREPANCIES, collect_scheduled_jobs  # noqa: E402
from configuration_scheduled_jobs_loader import (  # noqa: E402
    SUMMARY_KEYS,
    load_scheduled_jobs,
)
from external_db import transaction  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
SMALL_DUMPS = ("MinCfg", "KomMag")
BIG_DUMPS = ("BGU2", "BP3")

# Ожидаемые числа круга — план, разделы 1.1, 2.2, 2.3 (те же, что проверяет П3).
EXPECTED: Dict[str, Dict[str, object]] = {
    "MinCfg": {"files": 2, "read": 2, "jobs": 2, "with_schedule": 2, "without_schedule": 0,
               "index_kind": 2, "index_child": 2, "schedules": 5, "root": 2, "detailed": 3,
               "max_depth": 2, "files_with_detailed": 2, "methods_total": 2},
    "KomMag": {"files": 1, "read": 1, "jobs": 1, "with_schedule": 1, "without_schedule": 0,
               "index_kind": 1, "index_child": 1, "schedules": 1, "root": 1, "detailed": 0,
               "max_depth": 1, "files_with_detailed": 0, "methods_total": 1},
    "BGU2": {"files": 157, "read": 157, "jobs": 157, "with_schedule": 138,
             "without_schedule": 19, "index_kind": 157, "index_child": 138, "schedules": 143,
             "root": 138, "detailed": 5, "max_depth": 2, "files_with_detailed": 3,
             "methods_total": 157},
    "BP3": {"files": 186, "read": 186, "jobs": 186, "with_schedule": 162,
            "without_schedule": 24, "index_kind": 186, "index_child": 162, "schedules": 164,
            "root": 162, "detailed": 2, "max_depth": 2, "files_with_detailed": 1,
            "methods_total": 186},
}

FAILURES: List[str] = []


def check(name: str, got: object, want: object) -> None:
    """Сверка числа или флага: провал называется строкой, а не молчанием."""
    if isinstance(want, bool):
        ok = bool(got) == bool(want)
    else:
        try:
            ok = int(got or 0) == int(want or 0)
        except (TypeError, ValueError):
            ok = got == want
    if ok:
        print(f"  [ok]   {name} = {got}")
    else:
        FAILURES.append(f"{name}: получено {got!r}, ожидалось {want!r}")
        print(f"  [FAIL] {name}: получено {got!r}, ожидалось {want!r}")


def one_scalar(sql: str, params: Optional[list] = None):
    with transaction() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
    return row[0] if row else None


def show_nonzero(title: str, mapping: Dict) -> None:
    """Печатает только ненулевые позиции замкнутого словаря (нули названы контрактом)."""
    parts = [f"{key}={value}" for key, value in sorted((mapping or {}).items())
             if isinstance(value, int) and value]
    print(f"  {title}: " + (", ".join(parts) if parts else "все позиции нулевые"))


# Ключи, которые стадия обязана посчитать сама, а не скопировать с разбора: три ноги чтения
# (индекс состава, перечень общих модулей, тексты модулей) существуют только в БД, а `success`
# и `warnings` являются ответом стадии, а не разбора. Отсутствие этих ключей в `SUMMARY_KEYS`
# является состоянием, поэтому они перечислены здесь, а не молча пропущены.
STAGE_OWNED_KEYS = frozenset({
    "index_available", "index_kind_records", "index_child_records",
    "common_modules_available", "module_texts_available", "success", "warnings",
})


def check_key_alignment() -> None:
    """Статическая часть зонда: разбор ↔ `SUMMARY_KEYS` ↔ контракт стадии.

    Ответ собирается тремя множествами ключей: разбор даёт свои, стадия переносит только
    перечисленные (`SUMMARY_KEYS`), контракт задаёт замкнутый набор (C1, C3). Расхождение
    любого из них означает, что карточка обещает число, которого стадия не даёт, или теряет
    то, что разбор назвал; форматёр читает контракт, поэтому молча потерять ключ — значит
    напечатать ноль там, где знание есть.

    Разбор вызывается на несуществующем каталоге: нужен набор ключей, а не круг; пустой
    круг отдаёт тот же замкнутый словарь с наблюдением `directory_missing` (Q9), и это же
    проверяет ветку ответа о выгрузке.
    """
    print("сверка ключей ответа (статическая часть):")
    collected = collect_scheduled_jobs(str(DUMP_ROOT / "_нет_такого_каталога_"))
    parser_keys = set(collected)
    contract_keys = set(scheduled_jobs_defaults())
    summary_keys = set(SUMMARY_KEYS)
    check("ключей SUMMARY_KEYS вне контракта", len(summary_keys - contract_keys), 0)
    check("ключей SUMMARY_KEYS, которых не даёт разбор", len(summary_keys - parser_keys), 0)
    lost = (parser_keys & contract_keys) - summary_keys - STAGE_OWNED_KEYS
    check("ключей разбора, которые стадия теряет", len(lost), 0)
    if lost:
        print(f"    потерянные ключи: {', '.join(sorted(lost))}")
    # Замкнутые словари расхождений: ключи словаря контракта обязаны совпадать со
    # словарями разбора — второе перечисление состояний в проекте разъезжается с первым.
    defaults = scheduled_jobs_defaults()
    check("словарь counts_by_circle_discrepancy против CIRCLE_DISCREPANCIES",
          len(set(defaults["counts_by_circle_discrepancy"]) ^ set(CIRCLE_DISCREPANCIES)), 0)
    check("словарь counts_by_content_discrepancy против константы контракта",
          len(set(defaults["counts_by_content_discrepancy"])
              ^ set(SCHEDULED_JOB_CONTENT_DISCREPANCIES)), 0)
    check("константа контракта ноги вида против разбора",
          len(set(SCHEDULED_JOB_CIRCLE_DISCREPANCIES) ^ set(CIRCLE_DISCREPANCIES)), 0)
    print()


def db_state(configuration_uuid: str) -> Dict[str, object]:
    """Состояние круга глазами БД — таблицами и витринами, а не ответом загрузчика."""
    out: Dict[str, object] = {}
    with transaction() as cur:
        cur.execute(
            """
            SELECT count(*),
                   coalesce(min(revision_no), 0), coalesce(max(revision_no), 0),
                   count(*) FILTER (WHERE changed_at IS NULL),
                   count(*) FILTER (WHERE NOT is_committed),
                   count(*) FILTER (WHERE schedule_state = 'with_content'),
                   count(*) FILTER (WHERE schedule_state = 'absent')
              FROM v_current_scheduled_jobs
             WHERE configuration_uuid = %s
            """, [configuration_uuid])
        row = cur.fetchone()
        out["jobs_current"] = row[0]
        out["revision_min"] = row[1]
        out["revision_max"] = row[2]
        out["without_changed_at"] = row[3]
        out["uncommitted"] = row[4]
        out["state_with_content"] = row[5]
        out["state_absent"] = row[6]

        cur.execute(
            """
            SELECT count(*),
                   count(*) FILTER (WHERE kind = 'schedule'),
                   count(*) FILTER (WHERE kind = 'detailed_daily'),
                   coalesce(max(depth), 0),
                   count(*) FILTER (WHERE parent_id IS NULL),
                   count(*) FILTER (WHERE root_tag = 'JobSchedule')
              FROM v_current_scheduled_job_schedules
             WHERE configuration_uuid = %s
            """, [configuration_uuid])
        row = cur.fetchone()
        out["schedules_current"] = row[0]
        out["kind_root"] = row[1]
        out["kind_detailed"] = row[2]
        out["max_depth"] = row[3]
        out["roots"] = row[4]
        out["root_tag_ok"] = row[5]

    # После идемпотентной загрузки в таблицах не обязано оставаться ни одной строки
    # другого круга: витрина текущего состояния обязана отдавать весь круг.
    out["jobs_total"] = one_scalar(
        "SELECT count(*) FROM scheduled_jobs WHERE configuration_uuid = %s",
        [configuration_uuid])
    out["jobs_orphans"] = one_scalar(
        """SELECT count(*) FROM scheduled_jobs sj
            WHERE sj.configuration_uuid = %s
              AND NOT EXISTS (SELECT 1 FROM v_current_scheduled_jobs c
                               WHERE c.id = sj.id)""", [configuration_uuid])
    out["schedules_total"] = one_scalar(
        "SELECT count(*) FROM scheduled_job_schedules WHERE configuration_uuid = %s",
        [configuration_uuid])
    out["schedules_orphans"] = one_scalar(
        """SELECT count(*) FROM scheduled_job_schedules ss
            WHERE ss.configuration_uuid = %s
              AND NOT EXISTS (SELECT 1 FROM v_current_scheduled_job_schedules c
                               WHERE c.id = ss.id)""", [configuration_uuid])


    # Целостность самоссылки: родитель — запись того же задания и того же файла, глубина
    # на единицу больше (CHECK `scheduled_job_schedules_parent_same_job`).
    out["parent_violations"] = one_scalar(
        """SELECT count(*) FROM scheduled_job_schedules child
            JOIN scheduled_job_schedules parent ON parent.id = child.parent_id
            WHERE child.configuration_uuid = %s
              AND (parent.scheduled_job_id <> child.scheduled_job_id
                   OR parent.file_path <> child.file_path
                   OR parent.id = child.id
                   OR child.depth <> parent.depth + 1)""", [configuration_uuid])
    out["root_with_parent"] = one_scalar(
        """SELECT count(*) FROM scheduled_job_schedules
            WHERE configuration_uuid = %s AND kind = 'schedule'
              AND parent_id IS NOT NULL""", [configuration_uuid])
    out["detailed_without_parent"] = one_scalar(
        """SELECT count(*) FROM scheduled_job_schedules
            WHERE configuration_uuid = %s AND kind = 'detailed_daily'
              AND parent_id IS NULL""", [configuration_uuid])
    # Счётчик на строке задания против фактического числа записей: CHECK сверяет
    # состояние со счётчиком, а число строк круга сверяет обход выгрузки (П6).
    out["count_mismatches"] = one_scalar(
        """SELECT count(*) FROM v_current_scheduled_jobs sj
            WHERE sj.configuration_uuid = %s
              AND sj.schedule_record_count <> (SELECT count(*)
                                                FROM scheduled_job_schedules ss
                                                WHERE ss.scheduled_job_id = sj.id)""",
        [configuration_uuid])
    out["chain_duplicates"] = one_scalar(
        """SELECT count(*) FROM (SELECT object_name, revision_no
                                  FROM scheduled_jobs
                                 WHERE configuration_uuid = %s
                                 GROUP BY 1, 2 HAVING count(*) > 1) d""",
        [configuration_uuid])
    # Версионность держит ОДНА таблица пары: у записей расписания колонок ревизии быть
    # не должно (`CONFIGURATION_UNVERSIONED_TABLES`), иначе витрина связки врала бы.
    out["unversioned_columns"] = one_scalar(
        """SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'scheduled_job_schedules'
              AND column_name IN ('revision_no', 'changed_at', 'is_committed',
                                  'valid_from', 'valid_to')""")
    out["common_modules_rows"] = one_scalar(
        "SELECT count(*) FROM v_current_common_modules WHERE configuration_uuid = %s",
        [configuration_uuid])
    return out



def run_dump(name: str) -> None:
    layout = DUMP_ROOT / name
    if not layout.exists():
        FAILURES.append(f"{name}: каталог выгрузки {layout} не найден")
        print(f"== {name}: каталог {layout} не найден — пропуск ==")
        return
    expected = EXPECTED[name]
    print(f"== {name}: {layout} ==")

    result = load_scheduled_jobs(str(layout))
    if not result.get("success"):
        FAILURES.append(f"{name}: загрузка не удалась: {result.get('error')}")
        print(f"  [FAIL] status={result.get('status')} error={result.get('error')}")
        for text in result.get("warnings") or []:
            print(f"    warning: {text}")
        return

    print(f"  конфигурация id={result.get('configuration_id')} "
          f"uuid={result.get('configuration_uuid')} name={result.get('configuration_name')}")
    check("files_found", result.get("files_found"), expected["files"])
    check("files_read", result.get("files_read"), expected["read"])
    check("files_failed", len(result.get("files_failed") or []), 0)
    check("index_available", result.get("index_available"), True)
    check("index_kind_records", result.get("index_kind_records"), expected["index_kind"])
    check("index_child_records", result.get("index_child_records"), expected["index_child"])
    check("index_only", len(result.get("index_only") or []), 0)
    check("file_only", len(result.get("file_only") or []), 0)
    check("uuid_mismatch", len(result.get("uuid_mismatch") or []), 0)
    check("schedule_index_only", len(result.get("schedule_index_only") or []), 0)
    check("schedule_file_only", len(result.get("schedule_file_only") or []), 0)
    check("schedule_uuid_mismatch", len(result.get("schedule_uuid_mismatch") or []), 0)
    check("duplicate_names", len(result.get("duplicate_names") or []), 0)
    check("scheduled_jobs_written", result.get("scheduled_jobs_written"), expected["jobs"])
    check("schedule_records_written", result.get("schedule_records_written"),
          expected["schedules"])
    check("rows_written", result.get("rows_written"),
          int(expected["jobs"]) + int(expected["schedules"]))
    check("schedules_total", result.get("schedules_total"), expected["schedules"])
    check("root_records_total", result.get("root_records_total"), expected["root"])
    check("detailed_records_total", result.get("detailed_records_total"), expected["detailed"])
    check("max_depth_seen", result.get("max_depth_seen"), expected["max_depth"])
    check("files_with_schedule", result.get("files_with_schedule"), expected["with_schedule"])
    check("files_without_schedule", result.get("files_without_schedule"),
          expected["without_schedule"])
    check("files_with_detailed", result.get("files_with_detailed"),
          expected["files_with_detailed"])
    check("methods_total", result.get("methods_total"), expected["methods_total"])
    check("methods_unresolved_total", result.get("methods_unresolved_total"), 0)
    check("statistics_refreshed", result.get("statistics_refreshed"), 2)

    show_nonzero("counts_by_method_state", result.get("counts_by_method_state"))
    show_nonzero("counts_by_method_declared_state",
                 result.get("counts_by_method_declared_state"))
    show_nonzero("counts_by_schedule_state", result.get("counts_by_schedule_state"))
    show_nonzero("counts_by_schedule_file_state",
                 result.get("counts_by_schedule_file_state"))
    show_nonzero("counts_by_record_kind", result.get("counts_by_record_kind"))
    show_nonzero("counts_by_attribute_state", result.get("counts_by_attribute_state"))
    show_nonzero("counts_by_week_days_state", result.get("counts_by_week_days_state"))
    show_nonzero("counts_by_months_state", result.get("counts_by_months_state"))
    show_nonzero("counts_by_properties_state", result.get("counts_by_properties_state"))
    show_nonzero("counts_by_observation", result.get("counts_by_observation"))
    show_nonzero("counts_by_circle_discrepancy", result.get("counts_by_circle_discrepancy"))
    show_nonzero("counts_by_content_discrepancy", result.get("counts_by_content_discrepancy"))
    print(f"  methods_distinct={result.get('methods_distinct')} "
          f"method_modules_distinct={result.get('method_modules_distinct')} "
          f"schedule_jobs_distinct={result.get('schedule_jobs_distinct')}")
    print(f"  common_modules_available={result.get('common_modules_available')} "
          f"module_texts_available={result.get('module_texts_available')}")

    # ── глазами БД ─────────────────────────────────────────────────────────────────────
    state = db_state(str(result.get("configuration_uuid")))
    print("  состояние БД:")
    check("v_current_scheduled_jobs", state["jobs_current"], expected["jobs"])
    check("scheduled_jobs всего строк (сирот нет)", state["jobs_total"], expected["jobs"])
    check("сирот в scheduled_jobs", state["jobs_orphans"], 0)
    check("v_current_scheduled_job_schedules", state["schedules_current"],
          expected["schedules"])
    check("scheduled_job_schedules всего строк", state["schedules_total"],
          expected["schedules"])
    check("сирот в scheduled_job_schedules", state["schedules_orphans"], 0)
    check("kind=schedule", state["kind_root"], expected["root"])
    check("kind=detailed_daily", state["kind_detailed"], expected["detailed"])
    check("максимальная глубина в БД", state["max_depth"], expected["max_depth"])
    check("корневых записей (parent_id IS NULL)", state["roots"], expected["root"])
    check("нарушений самоссылки", state["parent_violations"], 0)
    check("корень с родителем", state["root_with_parent"], 0)
    check("вложенная без родителя", state["detailed_without_parent"], 0)
    check("несогласованных schedule_record_count", state["count_mismatches"], 0)
    check("дублей ключа цепи", state["chain_duplicates"], 0)
    check("ревизия min", state["revision_min"], 1)
    check("ревизия max", state["revision_max"], 1)
    check("строк без changed_at", state["without_changed_at"], 0)
    # Событие «загрузка» проставляет признак коммита само (решение D11/D12: значение
    # выводит точка доступа `commit_flag_for`, а не писатель), поэтому строк без него
    # быть не должно — это не про текущность (её держит максимум revision_no, A1).
    check("строк без признака коммита", state["uncommitted"], 0)
    check("колонок ревизии у расписания (их быть не должно)",
          state["unversioned_columns"], 0)
    check("состояний with_content в БД", state["state_with_content"],
          expected["with_schedule"])
    check("состояний absent в БД", state["state_absent"], expected["without_schedule"])
    print(f"  строк общих модулей этой конфигурации в БД: {state['common_modules_rows']}")

    # ── идемпотентность: повтор той же выгрузки ────────────────────────────────────────
    # Снятие обязано равняться записи, а новой ревизии — не появляться: история состояний
    # принадлежит узлу правки объекта, которого в схеме нет (D8).
    total_rows = int(expected["jobs"]) + int(expected["schedules"])
    repeat = load_scheduled_jobs(str(layout))
    if not repeat.get("success"):
        FAILURES.append(f"{name}: повторная загрузка не удалась: {repeat.get('error')}")
        print(f"  [FAIL] повтор: {repeat.get('error')}")
    else:
        print("  повтор той же выгрузки:")
        check("scheduled_jobs_written (повтор)", repeat.get("scheduled_jobs_written"),
              expected["jobs"])
        check("schedule_records_written (повтор)", repeat.get("schedule_records_written"),
              expected["schedules"])
        check("removed_previous (повтор) = записанное ранее",
              repeat.get("removed_previous"), total_rows)
        check("removed_by_table (повтор)",
              sum((repeat.get("removed_by_table") or {}).values()), total_rows)
        after = db_state(str(result.get("configuration_uuid")))
        check("строк вида после повтора", after["jobs_current"], expected["jobs"])
        check("записей расписания после повтора", after["schedules_current"],
              expected["schedules"])
        check("ревизия max после повтора", after["revision_max"], 1)
        check("сирот после повтора",
              int(after["jobs_orphans"]) + int(after["schedules_orphans"]), 0)

    print("  формат карточки стадии:")
    for line in format_scheduled_jobs_lines(result, indent="    "):
        print(line)
    print(f"  предупреждений в ответе: {len(result.get('warnings') or [])}")
    for text in (result.get("warnings") or [])[:6]:
        print(f"    - {text}")


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--big"]
    dumps = (SMALL_DUMPS + BIG_DUMPS) if "--big" in sys.argv[1:] else (tuple(args)
                                                                       or SMALL_DUMPS)
    check_key_alignment()
    for name in dumps:
        run_dump(name)
    print()
    if FAILURES:
        print(f"ПРОВАЛЫ ({len(FAILURES)}):")
        for text in FAILURES:
            print(f"  - {text}")
        return 1
    print(f"П4 ПРОЙДЕН: расхождений нет ({', '.join(dumps)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

