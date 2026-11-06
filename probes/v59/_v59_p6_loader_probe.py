#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П6 (узел V59): загрузка десяти позиций пакета на живой БД.

Отвечает на вопросы, которых не показывает разбор вне БД (`_v59_p6_parse_probe.py`):

  1. проходит ли строка позиции CHECK'ы живой схемы (свойства ↔ неизвестные имена,
     счётчики ↔ состояние содержимого, `revision_no`, пара `changed_at`/`changed_by`) —
     нарушение CHECK является исключением, а не нулём, и увидеть его нужно до коммита;
  2. читается ли записанное витриной текущего состояния `v_current_<table>`: число строк
     витрины обязано равняться числу записанных строк, иначе цепь ревизий сломана;
  3. идемпотентность по `configuration_uuid`: повторный вызов той же выгрузки снимает
     прежнее число строк и пишет то же число, история не растёт (явный `DELETE`, потому что
     внешнего ключа и каскада в схеме нет осознанно — V20.1);
  4. сверка с индексом состава той же конфигурации: записи вида в индексе есть, поэтому
     состояние `matched` достижимо настоящим прогоном, а не фикстурой (в отличие от
     `_v59_p6_parse_probe.py`, где индекс не передаётся и всё остаётся `not_checked`);
  5. отсутствующий каталог вида — фикстура (несуществующий путь), а не прогон: у MinCfg
     каталоги есть у всех десяти позиций, поэтому `directory_missing` достигается здесь
     только фикстурой, и проба называет это прямо, а не выдаёт фикстуру за прогон.

За собой проба снимает строки всех десяти таблиц по `configuration_uuid` — база остаётся в
том состоянии, в котором была до пробы.

Запуск: `python probes/v59/_v59_p6_loader_probe.py [MinCfg]`.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from configuration_position_frame_loader import load_position_frame  # noqa: E402
from configuration_position_spec import (  # noqa: E402
    EXPORTS_ROOT, ordered_specs,
)
from external_db import transaction  # noqa: E402


def header_row(cur, name: str):
    cur.execute("SELECT id, uuid::text, name FROM configurations WHERE name = %s", [name])
    row = cur.fetchone()
    if row is None:
        return None
    return {"id": int(row[0]), "uuid": row[1], "name": row[2]}


def table_state(cur, table: str) -> dict:
    """Состояние таблицы позиции — своим запросом, а не ответом стадии."""
    cur.execute(
        f"SELECT count(*), coalesce(max(revision_no), 0), "
        f"count(DISTINCT changed_at), count(*) FILTER (WHERE changed_by = 'load') "
        f"FROM {table}")
    total, max_revision, distinct_moments, load_marked = cur.fetchone()
    cur.execute(f"SELECT count(*) FROM v_current_{table}")
    current_rows = int(cur.fetchone()[0])
    return {"rows": int(total), "max_revision": int(max_revision),
            "distinct_moments": int(distinct_moments), "load_marked": int(load_marked),
            "current_view": current_rows}


def main() -> int:
    export = sys.argv[1] if len(sys.argv) > 1 else "MinCfg"
    source = Path(EXPORTS_ROOT) / export
    problems = 0

    with transaction() as cur:
        header = header_row(cur, export)
    if header is None:
        print(f"❌ Конфигурация {export} в базе не найдена — проба не запускается: сначала "
              "загрузите каталог точкой входа load_1c_catalog_tool(source_path=…), иначе "
              "свойства позиции не указывали бы ни на какой заголовок")
        return 1
    print(f"=== {export} id={header['id']} uuid={header['uuid']}")

    written: dict = {}
    for spec in ordered_specs():
        started = time.perf_counter()
        result = load_position_frame(spec, str(source),
                                    configuration_uuid=header["uuid"])
        took = time.perf_counter() - started
        table = spec["table"]
        written[table] = int(result.get("rows_written") or 0)
        states = {state: count for state, count in
                  (result.get("counts_by_registration_state") or {}).items() if count}
        content = {state: count for state, count in
                   (result.get("counts_by_content_state") or {}).items() if count}
        observations = {kind: count for kind, count in
                        (result.get("counts_by_observation") or {}).items() if count}
        flag = "OK" if result.get("success") else "ОТКАЗ"
        print(f"{spec['position']:5} {table:24} {flag:5} строк={written[table]:5} "
              f"снято={int(result.get('removed_previous') or 0):5} "
              f"файлов={int(result.get('registration_files') or 0):5} "
              f"индекс={int(result.get('index_kind_records') or 0):5} "
              f"стат={int(result.get('statistics_refreshed') or 0)} {took:7.2f}с")
        print(f"      сверка={states or '-'} содержимое={content or '-'} "
              f"наблюдения={observations or '-'}")
        if not result.get("success"):
            problems += 1
            print(f"      ОТКАЗ: {result.get('error') or result.get('reason')}")
            for failure in (result.get("failures") or [])[:5]:
                print(f"      ⚠️ {failure}")

    # Сверка с БД — отдельным запросом: ответ стадии не является доказательством записи.
    print("--- сверка с живой схемой (CHECK пройден, если таблица читается)")
    with transaction() as cur:
        for spec in ordered_specs():
            table = spec["table"]
            state = table_state(cur, table)
            want = written.get(table, 0)
            ok = (state["rows"] == want and state["current_view"] == want
                  and state["max_revision"] in (0, 1)
                  and state["load_marked"] == want)
            if not ok:
                problems += 1
            print(f"{spec['position']:5} {table:24} "
                  f"{'OK' if ok else 'РАСХОЖДЕНИЕ'} таблица={state['rows']} "
                  f"витрина={state['current_view']} ждали={want} "
                  f"ревизия={state['max_revision']} моментов={state['distinct_moments']} "
                  f"changed_by=load:{state['load_marked']}")

    # Повтор той же выгрузки: идемпотентность по uuid, а не вторая ревизия (V20.1).
    print("--- повтор (идемпотентность по configuration_uuid)")
    spec = ordered_specs()[0]
    again = load_position_frame(spec, str(source), configuration_uuid=header["uuid"])
    with transaction() as cur:
        state = table_state(cur, spec["table"])
    ok = (int(again.get("removed_previous") or 0) == written.get(spec["table"], 0)
          and int(again.get("rows_written") or 0) == written.get(spec["table"], 0)
          and state["rows"] == written.get(spec["table"], 0)
          and state["max_revision"] == 1)
    if not ok:
        problems += 1
    print(f"{spec['position']:5} {spec['table']:24} {'OK' if ok else 'РАСХОЖДЕНИЕ'} "
          f"снято={int(again.get('removed_previous') or 0)} "
          f"записано={int(again.get('rows_written') or 0)} таблица={state['rows']} "
          f"ревизия={state['max_revision']} — второй ревизии нет, потому что повтор "
          "снимает прежнее тем же `DELETE`")

    # Фикстура отсутствующего каталога: у MinCfg каталоги есть у всех десяти позиций,
    # поэтому случай `directory_missing` здесь достижим только выдуманным путём — проба
    # называет это фикстурой (на настоящем корпусе он достигается 2.27, 5.2, 19).
    print("--- фикстура отсутствующего каталога (не прогон)")
    fixture = load_position_frame(spec, str(ROOT / "probes" / "v59" / "_нет_такого_каталога"),
                                  configuration_uuid=header["uuid"])
    observations = fixture.get("counts_by_observation") or {}
    ok = bool(observations.get("directory_missing")) and fixture.get("success")
    if not ok:
        problems += 1
    print(f"{spec['position']:5} {spec['table']:24} {'OK' if ok else 'РАСХОЖДЕНИЕ'} "
          f"строк={int(fixture.get('rows_written') or 0)} "
          f"directory_missing={int(observations.get('directory_missing') or 0)} "
          f"success={fixture.get('success')} — нули являются ответом о выгрузке, а не "
          "отказом стадии; строки позиции при этом сняты (идемпотентность по uuid), "
          "поэтому очистка за собой покажет по этой таблице ноль")

    # За собой: снять строки всех десяти таблиц этой конфигурации (внешнего ключа и каскада
    # в схеме нет, поэтому снятие явное — тот же приём, что у загрузчика).
    print("--- очистка за собой")
    with transaction() as cur:
        removed = {}
        for spec in ordered_specs():
            cur.execute(f"DELETE FROM {spec['table']} WHERE configuration_uuid = %s::uuid",
                        [header["uuid"]])
            removed[spec["table"]] = int(cur.rowcount)
    print("снято за собой: " + ", ".join(f"{t}={n}" for t, n in removed.items()))
    print(f"ИТОГ пробы: расхождений {problems}")
    return problems


if __name__ == "__main__":
    sys.exit(1 if main() else 0)

