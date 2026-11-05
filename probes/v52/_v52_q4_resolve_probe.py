#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V52, развилка Q4: разрешает ли индекс состава цели блока `Content` вида FilterCriteria.

Зонд только читает. Отвечает на вопрос, без которого Q4 решался бы текстом плана:

1. сколько целей даёт блок `Content/Item` по файлам регистрации вида (эталон П0 — 727 BGU2
   + 492 BP3, у MinCfg и KomMag блок пуст);
2. разрешается ли каждая цель записью индекса состава целиком (`exact`) — тем же алгоритмом,
   которым пользуются узлы V49/V50/V51 (`index_row_key` = полное точечное имя, затем срез
   префикса от длинного к короткому);
3. если целиком не разрешается — находится ли префикс (`prefix_only`) или ничем (`unresolved`),
   и какие имена при этом виновники.

Цель берётся из файла выгрузки, индекс — из таблицы `configuration_objects` (повторный разбор
`ConfigDumpInfo.xml` вторым источником быть не может, правило V43).

Запуск:  python _v52_q4_resolve_probe.py            # все четыре выгрузки
         python _v52_q4_resolve_probe.py BGU2 BP3   # выборочно
"""

import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import psycopg2  # noqa: E402

from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
VIEW_DIR = "FilterCriteria"
INDEX_NAME_SEPARATOR = "."
MAX_EXAMPLES = 6
DB = dict(host="localhost", dbname="ckb_1c_configurations", user="postgres",
          password="Sta090860")


def local(tag):
    return tag.split("}")[-1]


def view_files(dump_dir):
    """Файлы регистрации вида: `FilterCriteria/*.xml` (подкаталоги вида здесь не читаются)."""
    kind_dir = Path(dump_dir) / VIEW_DIR
    if not kind_dir.is_dir():
        return []
    return sorted(p for p in kind_dir.glob("*.xml") if p.is_file())


def content_targets(path):
    """Цели блока `Content/Item` одного файла регистрации — тексты элементов по порядку.

    Корнем файла является `MetaDataObject`, объектом вида — его первый дочерний элемент
    (`FilterCriterion`); ошибка уровня здесь дала бы ноль целей вместо 727 по BGU2.
    """
    root = ET.parse(str(path)).getroot()
    view = None
    for node in root:
        if local(node.tag) != "MetaDataObject":
            view = node
            break
    if view is None:
        return []
    for props in view:
        if local(props.tag) != "Properties":
            continue
        for block in props:
            if local(block.tag) != "Content":
                continue
            return [" ".join((item.text or "").split())
                    for item in block if local(item.tag) == "Item"]
    return []


def index_rows(cur, configuration_uuid):
    """Строки индекса состава конфигурации — ключом служит полное точечное имя `name`."""
    cur.execute(
        """SELECT co.id, co.uuid::text, co.name, co.object_type, co.child_type, co.depth
             FROM configuration_objects co
             JOIN configurations c ON c.id = co.configuration_id
            WHERE c.uuid = %s::uuid""",
        (configuration_uuid,),
    )
    columns = [d[0] for d in cur.description]
    rows = [dict(zip(columns, r)) for r in cur.fetchall()]
    return {str(r["name"]): r for r in rows}, len(rows)


def resolve(target, index_by_name):
    """Те же три состояния, что у `resolve_target` узлов V49/V50/V51 (Q3 варианта A ряда)."""
    name = (target or "").strip()
    if not name:
        return "empty", None
    row = index_by_name.get(name)
    if row is not None:
        return "exact", row
    segments = name.split(INDEX_NAME_SEPARATOR)
    for cut in range(len(segments) - 1, 0, -1):
        key = INDEX_NAME_SEPARATOR.join(segments[:cut])
        row = index_by_name.get(key)
        if row is not None:
            return "prefix_only", row
    return "unresolved", None


def probe(cur, dump):
    dump_dir = DUMP_ROOT / dump
    info = configuration_uuid_from_layout(dump_dir)
    if not info.get("uuid"):
        print(f"{dump}: конфигурация не опознана: {info.get('error')}")
        return None
    uuid_value = info["uuid"]
    index_by_name, index_total = index_rows(cur, uuid_value)
    files = view_files(dump_dir)

    states = Counter()
    kinds = Counter()
    examples = {}
    per_file = []
    total = 0
    for path in files:
        targets = content_targets(path)
        per_file.append((path.name, len(targets)))
        for target in targets:
            total += 1
            state, row = resolve(target, index_by_name)
            states[state] += 1
            kinds[target.split(".")[0] if target else "<пусто>"] += 1
            bucket = examples.setdefault(state, [])
            if len(bucket) < MAX_EXAMPLES:
                owner = str(row["name"]) if row else "<нет>"
                bucket.append(f"{target}  ->  {owner}")

    print(f"\n=== {dump}: конфигурация {uuid_value}, строк индекса {index_total}, "
          f"файлов регистрации {len(files)}")
    for name, count in per_file:
        print(f"  файл {name}: целей {count}")
    print("  целей всего " + str(total) + "; состояний: "
          + ", ".join(f"{k} {v}" for k, v in sorted(states.items())))
    print("  верхние сегменты целей: "
          + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())[:12]))
    for state in ("unresolved", "prefix_only", "empty"):
        for line in examples.get(state, []):
            print(f"  пример {state}: {line}")
    return total, states


def main():
    dumps = sys.argv[1:] or list(DUMPS)
    conn = psycopg2.connect(**DB)
    try:
        with conn.cursor() as cur:
            grand = 0
            grand_states = Counter()
            for dump in dumps:
                got = probe(cur, dump)
                if got:
                    grand += got[0]
                    grand_states.update(got[1])
            print("\n=== корпус: целей " + str(grand) + "; состояний: "
                  + ", ".join(f"{k} {v}" for k, v in sorted(grand_states.items())))
    finally:
        conn.close()


if __name__ == "__main__":
    main()

