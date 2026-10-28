#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_v47_p2_probe.py — офлайн-проба словаря слотов и вывода путей (узел V47, шаг П2).

Проверка шага П2 плана `docs/CONFIGURATION_OBJECT_MODULES_PLAN.md`: словарь
`src/configuration_module_slots.py` обязан выводить путь файла модуля по записи индекса
состава для всего круга узла, называть каждую причину отказа и не оставлять ни одной
записи без состояния. В БД не пишется ни одной строки — проба только читает.

Контуры пробы:

  A. офлайн, без БД: индекс состава читается из `ConfigDumpInfo.xml` каждой выгрузки
     (штатным разборчиком V33), круг задаёт `scope_of`, путь выводит
     `derive_module_path`. Именно этот контур и есть «офлайн-проба путей по выгрузкам»;
  B. тот же круг из таблицы `configuration_objects` (`iter_index_records`,
     `iter_module_rows`) — числа офлайн- и табличного контуров обязаны совпасть:
     расхождение значит, что граница, записанная SQL, и граница, записанная словарём,
     разошлись;
  C. эквивалентность путей прежним замерам (`_v47_q2_examples.module_path`,
     `_v47x_kinds`): словарь обязан выводить те же файлы, что измерены шагами П0/Q2,
     иначе числа раздела 2 плана перестают относиться к коду;
  D. ловушка хвоста имени: сколько записей вне круга имеют хвост, похожий на слот
     (число, которым план обосновывает меру по `child_type`);
  E. ожидания числами раздела 2 плана: круг 13 389, файл 13 342, `indexed_no_file` 47,
     `empty_file` 0, рядом `.bin` 18 (открытая позиция O1 — названа отдельной строкой),
     отказов и дефектов словаря 0.

Запуск: python _v47_p2_probe.py
"""
from __future__ import annotations

import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for path in (str(ROOT), str(ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from config_dump_info_parser import find_config_dump_info, parse_config_dump_info  # noqa: E402
from external_db import connect  # noqa: E402

import configuration_module_slots as slots  # noqa: E402
import _v47_q2_examples as previous  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")

# Ожидания раздела 2 плана (замеры 28.10.2026, прогон `_v47_q2_examples.py`).
EXPECT = {
    "in_scope": 13389,
    slots.STATE_FILE: 13342,
    slots.STATE_INDEXED_NO_FILE: 47,
    slots.STATE_EMPTY_FILE: 0,
    "bin_side": 18,
}
# Круг по строкам заголовков (раздел 5 плана, «итого 13 389») и строки П6 (число
# раскодированных файлов). Ожидания по именам, потому что имена — то, что печатает
# карточка загрузки; uuid в тексте плана нет ни для одной строки.
EXPECT_PER_HEADER = {
    "БухгалтерияПредприятия": {"in_scope": 7758, slots.STATE_FILE: 7753},
    "БухгалтерияГосударственногоУчреждения": {"in_scope": 5403, slots.STATE_FILE: 5399},
    "XXI_Коммерческий_магазин_8_редакция_1_0_3": {"in_scope": 149, slots.STATE_FILE: 111},
    "MinCfg": {"in_scope": 79, slots.STATE_FILE: 79},
}

FAILURES = []


def check(title: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'OK' if ok else 'FAIL'}]   {title}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(title)
    return bool(ok)


def offline_index(dump_dir: Path):
    """Записи индекса выгрузки (пустой список, если индекса нет)."""
    index_path = find_config_dump_info(str(dump_dir))
    if not index_path:
        return []
    parsed = parse_config_dump_info(str(index_path))
    if not parsed.get("success"):
        print(f"  индекс не разобран: {index_path} — {parsed.get('error')}")
        return []
    return parsed.get("objects") or []


def scan_records(records, dump_dir: Path, cache: dict, counters: Counter,
                 by_slot: dict, samples: dict, sizes: list):
    """Прогнать словарь по записям и наполнить счётчики (файлы не читаются)."""
    for record in records:
        kind = str(record.get("object_type") or "")
        slot = str(record.get("child_type") or "")
        if slots.scope_of(kind, slot) != slots.SCOPE_V47:
            continue
        counters["in_scope"] += 1
        derived = slots.derive_module_path(record, str(dump_dir), cache)
        if not derived["ok"]:
            counters["refusal:" + str(derived["reason"])] += 1
            refusal_samples = samples.setdefault(str(derived["reason"]), [])
            if len(refusal_samples) < 2:
                refusal_samples.append(derived["name"])
            continue
        absolute = Path(derived["abs_path"])
        exists = absolute.is_file()
        if not exists:
            state = slots.STATE_INDEXED_NO_FILE
            size = 0
            if Path(derived["bin_path"]).is_file():
                counters["bin_side"] += 1
        else:
            size = absolute.stat().st_size
            state = slots.STATE_FILE if size else slots.STATE_EMPTY_FILE
        counters[state] += 1
        sizes.append((dump_dir.name, size))
        by_slot.setdefault(slot, Counter())[state] += 1
        state_samples = samples.setdefault(state, [])
        if len(state_samples) < 2:
            state_samples.append((derived["name"], derived["rel_path"], size))


def main() -> int:
    if not DUMP_ROOT.is_dir():
        print(f"Каталог выгрузок не найден: {DUMP_ROOT}")
        return 2

    # Строки заголовков читаются до офлайн-контура: офлайн-пробу интересуют все
    # выгрузки (словарь обязан работать и на незагруженных), но сверяться с числами
    # плана могут только те, что загружены в базу, — круга узла у остальных нет.
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT uuid::text AS uuid, name FROM configurations ORDER BY name")
        headers = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
    header_by_uuid = {str(h["uuid"]).lower(): h["name"] for h in headers}

    counters: Counter = Counter()
    by_slot: dict = defaultdict(Counter)
    samples: dict = defaultdict(list)
    per_dump: dict = defaultdict(Counter)
    sizes: list = []
    cache: dict = {}

    print("=== A. офлайн-контур: индекс из ConfigDumpInfo.xml, без БД ===")
    offline_uuid_to_dir = {}
    for entry in sorted(DUMP_ROOT.iterdir()):
        if not entry.is_dir():
            continue
        root_uuid = slots.configuration_root_uuid(entry)
        if not root_uuid:
            continue
        offline_uuid_to_dir[root_uuid] = entry
        loaded = root_uuid in header_by_uuid
        records = offline_index(entry)
        local = Counter()
        started = time.perf_counter()
        scan_records(records, entry, cache, local,
                     by_slot if loaded else {}, samples if loaded else {},
                     sizes if loaded else [])
        took = time.perf_counter() - started
        per_dump[entry.name] = local
        if loaded:
            counters.update(local)
        six_slot = sum(1 for r in records
                       if str(r.get("child_type") or "") in slots.SLOTS)
        print(f"  {entry.name:34} записей индекса {len(records):6} "
              f"шести слотов {six_slot:6} в круге {local['in_scope']:6} за {took:5.1f} с"
              + ("" if loaded else "   — строки заголовка в базе нет, вне сверки"))

    print("\n=== B. табличный контур: тот же круг из configuration_objects ===")
    db_counters: Counter = Counter()
    db_per_header: dict = defaultdict(Counter)
    with connect() as conn:
        cur = conn.cursor()

        db_cache: dict = {}
        for header in headers:
            resolved = slots.resolve_dump_dir(header["uuid"], DUMP_ROOT)
            dump_dir = resolved.get("path", "")
            expected_dir = str(offline_uuid_to_dir.get(header["uuid"].lower(), ""))
            check(f"{header['name']}: каталог выгрузки разрешён по uuid корня",
                  bool(dump_dir) and dump_dir == expected_dir,
                  f"получен {Path(dump_dir).name if dump_dir else resolved.get('reason')}")
            started = time.perf_counter()
            local = Counter()
            for item in slots.iter_module_rows(cur, header["uuid"], DUMP_ROOT, db_cache):
                local["in_scope"] += 1
                if item["refusal"]:
                    local["refusal:" + item["refusal"]] += 1
                    if len(samples[item["refusal"]]) < 2:
                        samples[item["refusal"]].append(item["name"])
                    continue
                local[item["state"]] += 1
                if item["bin_side"]:
                    local["bin_side"] += 1
                if item["state"] == slots.STATE_FILE:
                    row = item["row"]
                    if (not row["parent_uuid"] or not row["file_path"]
                            or row["parent_type"] != slots.PARENT_TYPE
                            or row["module_type"] != item["slot"]):
                        local["bad_row_spec"] += 1
            took = time.perf_counter() - started
            db_per_header[header["name"]] = local
            db_counters.update(local)
            refusals = sum(v for k, v in local.items() if k.startswith("refusal:"))
            print(f"  {header['name']:44} записей {local['in_scope']:6} "
                  f"(отказов {refusals}) за {took:5.1f} с")

        # C. эквивалентность путей прежним замерам (шаг П0, пробы Q2) на всём круге.
        path_diffs = []
        for header in headers:
            resolved = slots.resolve_dump_dir(header["uuid"], DUMP_ROOT)
            dump_dir = resolved.get("path", "")
            if not dump_dir:
                continue
            old_cache: dict = {}
            for record in slots.iter_index_records(cur, header["uuid"]):
                derived = slots.derive_module_path(record, dump_dir, {})
                if not derived["ok"]:
                    continue
                old_path, reason = previous.module_path(
                    dump_dir, str(record["name"]), str(record["child_type"]), old_cache)
                if reason or old_path is None:
                    path_diffs.append(f"{record['name']}: прежний зонд — {reason}")
                elif Path(old_path) != Path(derived["abs_path"]):
                    path_diffs.append(f"{record['name']}: {old_path} ≠ {derived['abs_path']}")
        print()
        check("пути словаря совпадают с путями прежних замеров (_v47_q2_examples)",
              not path_diffs, "; ".join(path_diffs[:3]) if path_diffs else "0 расхождений")

        # D. мера круга: чем именно `child_type` надёжнее хвоста имени.
        cur.execute(
            "SELECT count(*) FROM configuration_objects o "
            "WHERE o.child_type = ANY(%s) "
            "  AND split_part(o.name, '.', -1) IS DISTINCT FROM o.child_type",
            (list(slots.SLOTS),))
        tail_mismatch = int(cur.fetchone()[0] or 0)
        cur.execute(
            "SELECT count(*) FROM configuration_objects o "
            "WHERE o.child_type = ANY(%s) "
            "  AND array_length(string_to_array(o.name, '.'), 1) %% 2 = 0",
            (list(slots.SLOTS),))
        even_shape = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT count(*) FROM configuration_objects "
                    "WHERE child_type = 'Module' AND object_type = 'CommonModule'")
        v46_boundary = int(cur.fetchone()[0] or 0)

    print(f"\n  записей шести слотов, где хвост имени НЕ равен `child_type`: {tail_mismatch}")
    print(f"  записей шести слотов с чётным числом сегментов имени "
          f"(там хвост — имя объекта, а не слот): {even_shape}")
    print("  мера круга — `child_type`, а не хвост имени: расхождений на этих выгрузках "
          f"{tail_mismatch}, но проверка опирается на колонку, а не на совпадение хвоста")
    print(f"  записей `CommonModule.*.Module` (граница V46, вне предмета V47): {v46_boundary}")

    print("\n=== E. сверка с ожиданиями раздела 2 плана ===")
    db_total = db_counters["in_scope"]
    check(f"круг узла = {EXPECT['in_scope']}",
          counters["in_scope"] == EXPECT["in_scope"] and db_total == EXPECT["in_scope"],
          f"офлайн {counters['in_scope']}, по таблице {db_total}")
    for state in (slots.STATE_FILE, slots.STATE_INDEXED_NO_FILE, slots.STATE_EMPTY_FILE):
        check(f"состояние `{state}` = {EXPECT[state]} (оба контура)",
              counters[state] == EXPECT[state] and db_counters[state] == EXPECT[state],
              f"офлайн {counters[state]}, по таблице {db_counters[state]}")
    check(f"рядом `.bin` вместо `.bsl` = {EXPECT['bin_side']} (O1 названа)",
          counters["bin_side"] == EXPECT["bin_side"]
          and db_counters["bin_side"] == EXPECT["bin_side"],
          f"офлайн {counters['bin_side']}, по таблице {db_counters['bin_side']}")
    for reason in slots.REFUSALS + slots.DEFECTS:
        found = counters["refusal:" + reason] + db_counters["refusal:" + reason]
        check(f"причина `{reason}` не встречается", found == 0,
              f"{found}; примеры: {samples.get(reason, [])[:2]}" if found else "")
    check("спецификации строк полны (parent_uuid, file_path, parent_type, module_type)",
          db_counters["bad_row_spec"] == 0, str(db_counters["bad_row_spec"]))

    print("\n  по слотам (офлайн-контур):")
    for slot in sorted(by_slot):
        print(f"    {slot:20} " + "  ".join(f"{k}={v}" for k, v in sorted(by_slot[slot].items())))

    print("\n  по строкам заголовков и выгрузкам:")
    dir_of_header = {header_by_uuid[uuid]: Path(str(path)).name
                     for uuid, path in offline_uuid_to_dir.items() if uuid in header_by_uuid}
    for name in sorted(EXPECT_PER_HEADER):
        expected = EXPECT_PER_HEADER[name]
        found = db_per_header.get(name, Counter())
        dump_name = dir_of_header.get(name, "")
        got = per_dump.get(dump_name, Counter())
        ok = (found["in_scope"] == expected["in_scope"]
              and found[slots.STATE_FILE] == expected[slots.STATE_FILE]
              and got["in_scope"] == expected["in_scope"]
              and got[slots.STATE_FILE] == expected[slots.STATE_FILE])
        check(f"{name}: круг {expected['in_scope']}, строк {expected[slots.STATE_FILE]}",
              ok,
              f"по таблице круг {found['in_scope']}, файл {found[slots.STATE_FILE]}; "
              f"офлайн ({dump_name or 'выгрузка не сопоставлена'}) "
              f"круг {got['in_scope']}, файл {got[slots.STATE_FILE]}")

    print("\n=== F. примеры состояний (имя записи -> выведенный путь) ===")
    for state in (slots.STATE_FILE, slots.STATE_INDEXED_NO_FILE, slots.STATE_EMPTY_FILE):
        for name, rel_path, size in samples.get(state, []):
            print(f"  {state:16} {name}\n  {'':16} путь: {rel_path}  размер: {size}")
    total_bytes = sum(size for _dump, size in sizes)
    print(f"\n  байт файлов круга (офлайн-обход): {total_bytes} "
          f"({total_bytes / (1024 * 1024):.1f} МиБ)")

    print("\n=== ИТОГ: "
          + (f"провалено проверок: {len(FAILURES)}" if FAILURES else "все проверки пройдены")
          + " ===")
    for title in FAILURES:
        print(f"  FAIL: {title}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())


