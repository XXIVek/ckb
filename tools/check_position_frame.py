#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_position_frame.py — постоянная проверка пакета позиций (узел V59).

Зачем. До этого узла каждая позиция приносила свою проверку `tools/check_vNN_*.py`
(13 файлов на V48–V58), и большая часть их текста повторялась: круг по выгрузкам,
наличие таблицы и витрины, словарь состояний, порядок стадии. Проверка ниже параметризована
спецификацией `src/configuration_position_spec.py`: один прогон отвечает по каждой
позиции пакета, и новая позиция получает свои проверки строкой контракта, а не файлом.

Что проверяется (числа берутся из спецификации и из прогона, а не из памяти):

  1. каждая позиция спецификации существует в нормативном списке оператора и порядок
     совпадает с порядком списка — выдуманной позиции быть не может;
  2. в живой базе `ckb_1c_configurations` есть таблица и витрина позиции, а колонки
     таблицы равны колонкам, выведенным спецификацией (ни лишней, ни недостающей);
  3. ключ цепочки состояния и словари состояний закреплены ограничениями — теми же
     именами, что генерирует спецификация;
  4. блок DDL в миграции `sql/migrate_v59_position_frame.sql` и в зеркале
     `sql/create_1c_configurations_db.sql` совпадает с текстом, который генерирует
     `tools/_make_position_frame.py` (расхождение = генератор не прогоняли);
  5. ожидаемые счётчики позиции по четырём выгрузкам совпадают с фактом прогона зонда
     `probes/v59/_v59_p0_frame_probe.py` — это round-trip круга до всякого кода загрузки;
  6. подключение стадии позиции к конвейеру — строка `OPEN`, пока движок пакета не
     подключён: разрыв называется, а не отмечается молчаливым PASS;
  7. контракт писателя позиции: класс таблицы есть в реестре
     `CONFIGURATION_OBJECT_WRITERS`, его спецификация колонок равна спецификации колонки
     позиции, а каждый вид приведения значения принимает словарь `TableRowWriter._adapt`.
     Имена видов приведения (`int`, `text`, `jsonb_nullable`) не совпадают с именами
     SQL-типов (`integer`), и подмена одного другим видна только на вставке — ни сверка
     живой схемы, ни сверка DDL её не замечают.
   8. раздел «Состояние позиций нормативного списка» в модели
      (`docs/config-scenarios/01_configuration.md`) равен тексту, который порождает
      `tools/_make_position_status.py` (узел V61, шаг П1) — тот же приём, что пункт 4 для
      DDL: расхождение значит, что генератор не прогоняли после правки контракта, а не что
      «текст в документе устарел». До этого узла состояние позиций держалось в модели прозой
      семью датированными перечнями, и каждый новый узел добавлял следующую копию.

Запуск: python tools/check_position_frame.py [--exports BP3,ZUP31,UT11,MinCfg]
"""
from __future__ import annotations

import argparse
import inspect
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "probes" / "v59"))
from db_env import subprocess_env  # noqa: E402  (узел V60: значения подключения из .env)

from configuration_position_spec import (  # noqa: E402
    EXPORTS, FRAME_NODE, MEASURE_DATE, ordered_specs, position_ddl, expected_total,
    column_names, position_sort_key, writer_columns,
)
from check_stage_order_against_normative_list import (  # noqa: E402
    NORMATIVE_LIST, read_normative,
)
from _v59_p0_frame_probe import registration_counts  # noqa: E402
from _make_position_status import (  # noqa: E402  (узел V61: реестр состояния позиций)
    MODEL as STATUS_MODEL, extract_block as status_extract, render_block as status_render,
)

PSQL = r"C:\Postgres\bin\psql.exe"
DATABASE = "ckb_1c_configurations"
MIGRATION = ROOT / "sql" / "migrate_v59_position_frame.sql"
MIRROR = ROOT / "sql" / "create_1c_configurations_db.sql"

_counters = {"PASS": 0, "FAIL": 0, "OPEN": 0, "INFO": 0}
_failures = []


def check(title: str, ok: bool, detail: str = "") -> bool:
    kind = "PASS" if ok else "FAIL"
    _counters[kind] += 1
    if not ok:
        _failures.append(title)
    print(f"{kind} {title}" + (f" — {detail}" if detail else ""))
    return ok


def note(kind: str, title: str, detail: str = "") -> None:
    _counters[kind] += 1
    print(f"{kind} {title}" + (f" — {detail}" if detail else ""))


def psql(query: str) -> list:
    """Строки ответа базы. Роль `postgres` названа явно: роли Windows-пользователя нет."""
    env = subprocess_env()
    result = subprocess.run(
        [PSQL, "-U", "postgres", "-h", "localhost", "-tA", "-P", "pager=off",
         "-P", "footer=off", "-d", DATABASE, "-c", query],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if result.returncode != 0:
        raise RuntimeError(f"psql rc={result.returncode}: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exports", default=",".join(EXPORTS))
    ap.add_argument("--skip-exports", action="store_true",
                    help="не переснимать круг по выгрузкам (быстрый прогон по схеме)")
    args = ap.parse_args()
    exports = [e.strip() for e in args.exports.split(",") if e.strip()]

    print(f"Проверка пакета позиций {FRAME_NODE} по спецификации "
          f"(круг измерен {MEASURE_DATE})")
    print("=" * 78)

    specs = ordered_specs()
    check(f"спецификация читается: позиций {len(specs)}", bool(specs),
          ", ".join(s["position"] for s in specs))
    if not specs:
        return 1

    # 1. позиции и порядок — по нормативному списку оператора
    if not NORMATIVE_LIST.exists():
        note("FAIL", "нормативный список не найден", str(NORMATIVE_LIST))
        return 2
    positions = read_normative(NORMATIVE_LIST)
    unknown = [s["position"] for s in specs if s["position"] not in positions]
    check("каждая позиция спецификации есть в нормативном списке", not unknown,
          ", ".join(unknown) if unknown else f"позиций в списке: {len(positions)}")
    order = {num: i for i, num in enumerate(sorted(positions, key=position_sort_key))}
    pairs = [s["position"] for s in specs]
    bad = [f"{prev} раньше, чем {cur}" for prev, cur in zip(pairs, pairs[1:])
           if order.get(cur, -1) < order.get(prev, -1)]
    check("порядок спецификации совпадает с порядком нормативного списка", not bad,
          "; ".join(bad) if bad else "порядок взят из списка")

    # 2–3. живая схема: таблицы, витрины, колонки, ограничения
    try:
        for spec in specs:
            table, view = spec["table"], spec["view"]
            kinds = psql("SELECT c.relkind FROM pg_class c "
                         "JOIN pg_namespace n ON n.oid=c.relnamespace "
                         "WHERE n.nspname='public' "
                         f"AND c.relname IN ('{table}','{view}')")
            check(f"{spec['position']}: таблица `{table}` и витрина `{view}` в живой базе",
                  "r" in kinds and "v" in kinds,
                  f"найдено: {sorted(set(kinds)) or 'ничего'}")

            live = psql("SELECT a.attname FROM pg_attribute a "
                        "JOIN pg_class c ON c.oid=a.attrelid "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE n.nspname='public' "
                        f"AND c.relname='{table}' AND c.relkind='r' "
                        "AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum")
            want = column_names(spec)
            check(f"{spec['position']}: колонки таблицы равны колонкам спецификации",
                  live == want,
                  (f"лишние: {sorted(set(live) - set(want)) or 'нет'}; "
                   f"нет: {sorted(set(want) - set(live)) or 'нет'}") if live != want
                  else f"колонок: {len(want)}")

            constraints = set(psql("SELECT conname FROM pg_constraint "
                                   f"WHERE conrelid='{table}'::regclass"))
            required = {f"{table}_configuration_object_revision_key",
                        f"{table}_properties_state_known",
                        f"{table}_content_state_known",
                        f"{table}_counters_match_content_state",
                        f"{table}_changed_pair_check",
                        f"{table}_revision_no_positive"}
            missing = sorted(required - constraints)
            check(f"{spec['position']}: ключ цепочки и словари состояний закреплены",
                  not missing,
                  ", ".join(missing) if missing else f"ограничений: {len(required)}")
    except RuntimeError as exc:
        note("FAIL", "живая база недоступна", str(exc))
        return 2

    # 4. DDL в миграции и в зеркале = тот текст, что генерирует спецификация
    migration_text = MIGRATION.read_text(encoding="utf-8") if MIGRATION.exists() else ""
    mirror_text = MIRROR.read_text(encoding="utf-8") if MIRROR.exists() else ""
    for spec in specs:
        ddl = position_ddl(spec)
        check(f"{spec['position']}: DDL позиции совпадает с генерируемым (миграция)",
              ddl in migration_text, MIGRATION.name if migration_text else "файла нет")
        check(f"{spec['position']}: DDL позиции совпадает с генерируемым (зеркало)",
              ddl in mirror_text, MIRROR.name if mirror_text else "файла нет")

    # 5. круг по выгрузкам: ожидаемые счётчики = факт прогона зонда
    if args.skip_exports:
        note("INFO", "круг по выгрузкам не переснимался (--skip-exports)",
             "ожидаемые числа называет спецификация: "
             + ", ".join(f"{s['position']}={expected_total(s)}" for s in specs))
    else:
        for spec in specs:
            fact = registration_counts(spec["container"], exports)
            want = {e: int(spec["expected"].get(e, 0)) for e in exports}
            diff = {e: (want[e], fact.get(e)) for e in exports
                    if (fact.get(e) or 0) != want[e]}
            check(f"{spec['position']}: круг `{spec['container']}` по выгрузкам совпадает",
                  not diff,
                  "; ".join(
                      f"{e}: ожидалось {a}, факт {b}" if b is not None
                      else f"{e}: ожидалось {a}, контейнера нет"
                      for e, (a, b) in diff.items()) if diff
                  else f"объектов: {sum(want.values())} по {len(exports)} выгрузкам")

    # 6. подключение стадии: разрыв называется строкой OPEN, а не молчанием
    try:
        from configuration_load_contract import STAGES
        stage_ids = {stage_id for stage_id, _title in STAGES}
    except Exception as exc:  # noqa: BLE001 — отказ импорта называется, а не роняет прогон
        note("FAIL", "реестр `STAGES` не прочитан", f"{type(exc).__name__}: {exc}")
        stage_ids = set()
    not_wired = [s["position"] for s in specs if s["stage"] not in stage_ids]
    if not_wired:
        note("OPEN", "стадии позиций ещё не подключены к конвейеру "
                     "(движок пакета — шаг П4/П6)",
             f"позиций без стадии: {len(not_wired)} — {', '.join(not_wired)}")
    else:
        check("стадии всех позиций внесены в реестр `STAGES`", True,
              f"стадий: {len(specs)}")

    # 7. писатель позиции: класс в реестре, колонки = колонки спецификации, а виды
    #    приведения значений — теми именами, которые принимает словарь
    #    `TableRowWriter._adapt`. Проверка появилась по замеру пробы П6 (06.11.2026):
    #    спецификация выдавала имя SQL-типа `integer` вместо имени вида `int`, и первая же
    #    вставка отказала «Неизвестный тип колонки: integer» — при корректной живой схеме и
    #    корректном DDL. Ни сверка схемы (п. 2), ни сверка DDL (п. 4) этого дефекта не
    #    видели: он рождается только на вставке, поэтому проверяется контракт писателя.
    try:
        from external_table_writer import (
            CONFIGURATION_OBJECT_WRITERS, TableRowWriter, versioned_columns,
        )
        adapter_kinds = set(re.findall(
            r'kind == "([a-z_]+)"', inspect.getsource(TableRowWriter._adapt)))
    except Exception as exc:  # noqa: BLE001 — отказ импорта называется, а не роняет прогон
        note("FAIL", "реестр писателей `CONFIGURATION_OBJECT_WRITERS` не прочитан",
             f"{type(exc).__name__}: {exc}")
        CONFIGURATION_OBJECT_WRITERS, adapter_kinds = {}, set()
    for spec in specs:
        writer = CONFIGURATION_OBJECT_WRITERS.get(spec["table"])
        check(f"{spec['position']}: писатель таблицы `{spec['table']}` в реестре",
              writer is not None and getattr(writer, "TABLE", "") == spec["table"],
              "" if writer else "класс писателя не найден")
        if writer is None:
            continue
        want = versioned_columns(writer_columns(spec))
        got = dict(getattr(writer, "COLUMNS", {}) or {})
        diff = sorted({name for name in set(got) ^ set(want)}
                      | {name for name, kind in got.items() if want.get(name) != kind})
        check(f"{spec['position']}: спецификация колонок писателя = колонки спецификации",
              not diff,
              ("расходятся: " + ", ".join(diff))[:200] if diff
              else f"колонок: {len(want)}")
        unknown = sorted({kind for kind in want.values()
                          if kind not in adapter_kinds})
        check(f"{spec['position']}: виды значений писателя принимает словарь `_adapt`",
            bool(adapter_kinds) and not unknown,
            ("неизвестные виды: " + ", ".join(unknown)) if unknown
            else f"видов в словаре `_adapt`: {len(adapter_kinds)}")

    # 8. раздел состояния позиций в модели = вывод генератора (узел V61, шаг П1).
    #    Раздел порождается прогоном, поэтому сверяется его текст целиком: расхождение
    #    означает, что генератор не запускали после правки `STAGES`, спецификации или схемы.
    try:
        want_block = status_render()
        live_block = status_extract(STATUS_MODEL.read_text(encoding="utf-8"))
        if live_block is None:
            check("раздел состояния позиций вставлен в модель", False,
                  f"маркеров генератора нет в {STATUS_MODEL}")
        else:
            identical = live_block == want_block
            check("раздел «Состояние позиций нормативного списка» модели = вывод "
                  "`_make_position_status.py`",
                  identical,
                  "" if identical else
                  f"в файле {len(live_block)} симв., генератор даёт {len(want_block)} — "
                  "нужен прогон python tools/_make_position_status.py --write")
    except Exception as exc:  # noqa: BLE001 — отказ называется, а не роняет прогон
        note("FAIL", "генератор состояния позиций не выполнил свой прогон",
             f"{type(exc).__name__}: {exc}")

    print("-" * 78)
    total = sum(_counters.values())
    print(f"ИТОГ: провер {total}, PASS {_counters['PASS']}, FAIL {_counters['FAIL']}, "
          f"OPEN {_counters['OPEN']}, INFO {_counters['INFO']}")
    if _failures:
        print("ПРОВАЛЕННЫЕ ПРОВЕРКИ:")
        for failure in _failures:
            print("  -", failure)
        return 1
    print("ПРОВАЛОВ НЕТ")
    return 0


if __name__ == "__main__":
    sys.exit(main())


