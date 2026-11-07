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
   9. оглавление разделов модели равно выводу `tools/_make_model_toc.py` (узел V61,
      шаг П2) — второй генерируемый раздел того же файла. Генерируемый раздел, который
      не сверяется, отстаёт молча: так индекс журнала карточек называл 96 снимков при 97
      живых (нашёл прогон узла V61).

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
from _make_model_toc import (  # noqa: E402  (узел V61: оглавление разделов модели)
    DEFAULT_FILE as TOC_FILE, extract_block as toc_extract, render_block as toc_render,
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

    # 9. оглавление разделов модели = вывод генератора (узел V61, шаг П2).
    #    Раздел порождается прогон по заголовкам файла, поэтому сверяется его текст
    #    целиком: расхождение значит, что в документе появился раздел и оглавление не
    #    перегенерировали, а не что «перечень чуть устарел».
    try:
        toc_text = (ROOT / TOC_FILE).read_text(encoding="utf-8")
        toc_live, toc_want = toc_extract(toc_text), toc_render(toc_text)
        if toc_live is None:
            check("оглавление разделов вставлено в модель", False,
                  f"маркеров генератора нет в {TOC_FILE}")
        else:
            identical = toc_live == toc_want
            check("оглавление разделов модели = вывод `_make_model_toc.py`",
                  identical,
                  "" if identical else
                  f"в файле {len(toc_live)} симв., прогон даёт {len(toc_want)} — нужен "
                  "прогон python tools/_make_model_toc.py --write")
    except Exception as exc:  # noqa: BLE001 — отказ называется, а не роняет прогон
        note("FAIL", "генератор оглавления не выполнил свой прогон",
             f"{type(exc).__name__}: {exc}")

    # 10. контур остановки замкнут каждой стадией детей (узел V58, шаг П8).
    #     Десять стадий пакета вошли в `STAGES` узлом V59, но записей в двух словарях
    #     остановки у них не было: отсутствие ключа в `STAGE_FULL_RELOAD_ONLY` читается
    #     как «отдельный вход есть» (об этом говорит комментарий самого контракта),
    #     отсутствие записи в `STAGE_INCOMPLETE_GROUPS` — как «состава остановка не
    #     касается», а `stage_resume_hint` уходил в формулировку по умолчанию, минуя
    #     единый текст повтора. Дефект не поймала ни одна проверка узла V59 — его нашла
    #     стоп-проба чужого узла V48. Круг задаёт пакет, значит и проверка замкнутости
    #     словарей круга живёт здесь, а не в карточке и не в памяти ведущего.
    try:
        from configuration_load_contract import (
            STAGES as CONTRACT_STAGES, STAGE_FULL_RELOAD_ONLY,
            STAGE_INCOMPLETE_GROUPS, STAGE_REPEAT_HINT, stage_resume_hint,
        )
    except Exception as exc:  # noqa: BLE001 — отказ импорта называется, не роняет прогон
        note("FAIL", "реестр стадий контракта не прочитан", f"{type(exc).__name__}: {exc}")
    else:
        # Стадии заголовка (S1, S2) в контур не входят: их отказ — другой путь ответа
        # (разбор каталога и запись заголовка останавливают загрузку до детей).
        child_stages = [stage for stage, _title in CONTRACT_STAGES][2:]
        frame_stages = [spec["stage"] for spec in specs]
        check("стадий детей в реестре контракта", len(child_stages) >= len(frame_stages),
              f"детских: {len(child_stages)}, позиций пакета: {len(frame_stages)}")
        missing_reload = [s for s in child_stages if s not in STAGE_FULL_RELOAD_ONLY]
        missing_group = [s for s in child_stages if s not in STAGE_INCOMPLETE_GROUPS]
        check("словари контура остановки покрывают каждую стадию детей",
              not missing_reload and not missing_group,
              ("нет в `STAGE_FULL_RELOAD_ONLY`: " + ", ".join(missing_reload) if missing_reload
               else "")
              + ("; нет в `STAGE_INCOMPLETE_GROUPS`: " + ", ".join(missing_group)
                 if missing_group else "")
              or f"стадий: {len(child_stages)}, записей: "
                 f"{len(STAGE_FULL_RELOAD_ONLY)}/{len(STAGE_INCOMPLETE_GROUPS)}")
        check("полная перезагрузка заявлена обязательной для каждой стадии детей",
              all(STAGE_FULL_RELOAD_ONLY.get(s) for s in child_stages),
              "есть стадия без признака полной перезагрузки")
        check("подсказка повтора одна для всех стадий без отдельного входа "
              "(узел TOOL-DROP)",
              all(stage_resume_hint(s) == STAGE_REPEAT_HINT for s in frame_stages),
              ["подсказка расходится с `STAGE_REPEAT_HINT`: "
               + ", ".join(s for s in frame_stages
                           if stage_resume_hint(s) != STAGE_REPEAT_HINT)][:200])
        unnamed = [spec["position"] for spec in specs
                   if spec["position"] not in (STAGE_INCOMPLETE_GROUPS.get(
                       spec["stage"], "") or "")]
        check("незакрытая группа каждой позиции пакета называет её позицию списка",
              not unnamed,
              ", ".join(unnamed) if unnamed else "позиций: " + str(len(specs)))

    # 11. снятие `force=True` покрывает каждую таблицу пакета (узел V58, шаг П8).
    #     Внешнего ключа и каскада на `configurations` у таблиц пакета нет осознанно
    #     (прецеденты V20.1…V58), поэтому прежний состав снимает явный `DELETE` в контуре
    #     снятия заголовка. Его там не было: очистка стояла только внутри стадии, и при
    #     остановке конвейера на более ранней стадии база сохраняла прежний состав видов,
    #     а «стадия не выполнялась» читалось строками предыдущей загрузки (правило C2).
    #     Исходники читаются текстом, а не импортом модулей: импорт внутри `main()`
    #     сделал бы `inspect` локальным именем всей функции и сломал чужой контур
    #     писателей (замер первого применения — `UnboundLocalError: cannot access local
    #     variable 'inspect'`, 11 провалов). Круг задаёт пакет, второй копии круга нет.
    loader_path = ROOT / "src" / "configuration_loader.py"
    frame_loader_path = ROOT / "src" / "configuration_position_frame_loader.py"
    if not loader_path.is_file() or not frame_loader_path.is_file():
        note("FAIL", "исходники контура снятия не найдены",
             f"{loader_path} / {frame_loader_path}")
    else:
        loader_text = loader_path.read_text(encoding="utf-8")
        check("контур снятия заголовка вызывает снятие таблиц пакета",
              "remove_position_frames(cur, configuration_uuid)" in loader_text,
              "вызова `remove_position_frames` в `configuration_loader` нет — строки "
              "пакета переживут снятие заголовка сиротами прежнего состава")
        frame_text = frame_loader_path.read_text(encoding="utf-8")
        _start = frame_text.find("def remove_position_frames(")
        _next = frame_text.find("\ndef ", _start + 1)
        remove_text = frame_text[_start:_next] if _start >= 0 else ""
        check("круг снятия читается строками пакета, а не списком имён",
              "ordered_specs()" in remove_text and "stage_remove_order" in remove_text,
              "список таблиц, выписанный в функции снятия, разойдётся с пакетом незаметно")
        check("число снятых строк возвращается по каждой таблице (мера M7)",
              "removed[table] = int(cur.rowcount)" in remove_text
              and "return removed" in remove_text,
              "ответ снятия не называет число снятых строк по таблице")

    # 12. текст незакрытой части стадии S4 называет каждую позицию, закрытую стадиями
    #     конвейера (узел V58, шаг П8). Третий дефект того же прогона стоп-проб:
    #     `CHILD_NOT_IMPLEMENTED` перечислял закрытые позиции до 2.13 (узел V58) и модули
    #     `Ext/` (узел V47), а десяти позиций V59 — не называл. Ответ загрузки для общих
    #     макетов, картинок, XDTO-пакетов, WS-ссылок, сервисов интеграции, элементов
    #     стиля, стилей, языков, последовательностей и внешних источников данных
    #     утверждал «не закрыто», хотя стадии `s4n…s4w` их пишут (правило C2: ответ не
    #     отрицает сохранённое). Тот же класс дефекта повторялся узел за узлом: пробы
    #     V54→V55→V56→V57 сдвигали границу «2.NN not in CHILD_NOT_IMPLEMENTED» вручную,
    #     и узел V58 её не сдвинул. Поэтому проверяется не конкретная граница, а
    #     инвариант: каждая позиция, закрытая стадией из реестра, названа текстом.
    #     Позиции берутся словарём `STAGE_INCOMPLETE_GROUPS` и строками пакета — второй
    #     копии круга нет.
    try:
        from configuration_load_contract import (
            CHILD_NOT_IMPLEMENTED as boundary_text, STAGE_INCOMPLETE_GROUPS,
        )
    except Exception as exc:  # noqa: BLE001 — отказ импорта называется, не роняет прогон
        note("FAIL", "текст незакрытой части не прочитан", f"{type(exc).__name__}: {exc}")
    else:
        # Позицию закрытой стадии называет словарь `STAGE_INCOMPLETE_GROUPS`: он же держит
        # незакрытую часть каждой стадии и уже замкнут контуром 10. Замер первого
        # применения: ни записи `STAGES`, ни `stage_title` позиции не содержат — из них
        # извлекалось ровно десять позиций пакета, позиции V48…V58 пропадали.
        position_in_group = re.compile(r"позиц\w*\s+(\d+(?:\.\d+)?)")
        closed_positions: set[str] = set()
        for _stage, group in STAGE_INCOMPLETE_GROUPS.items():
            closed_positions.update(position_in_group.findall(group or ""))
        closed_positions.update(spec["position"] for spec in specs)
        missing_positions = sorted(p for p in closed_positions if p not in boundary_text)
        check("текст незакрытой части называет каждую позицию, закрытую стадиями детей",
              bool(closed_positions) and not missing_positions,
              ("в `CHILD_NOT_IMPLEMENTED` нет позиций: " + ", ".join(missing_positions)
               if missing_positions else f"закрытых позиций: {len(closed_positions)}"))
        missing_stage_names = [spec["stage"] for spec in specs
                               if spec["stage"] not in boundary_text]
        check("текст незакрытой части называет каждую стадию пакета",
              not missing_stage_names,
              "в `CHILD_NOT_IMPLEMENTED` нет стадий: "
              + (", ".join(missing_stage_names) if missing_stage_names
                 else f"нет — стадий: {len(specs)}"))

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


