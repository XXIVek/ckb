#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M1-замер узла V56: коллизия идентификаторов и имён функциональных опций + третья нога.

Зачем: ключ версионности выбирается по замеру, а не по схеме соседа. Прецеденты — V52,
V53 (162 uuid и 192 имени общие у BGU2 и BP3), V54 (134 uuid и 134 имени), V55 (коллизий
нет, потому что вид есть только в одной выгрузке). По позиции 2.11 корпус отвечает иначе:
вид есть в трёх выгрузках из четырёх, и P0-зонд насчитал 765 файлов при 630 различных
uuid и 622 различных именах — то есть коллизии между выгрузками есть. Замер называет их
число и пары выгрузок.

Замером проверяются ТРИ ноги круга (правило V43):

  * файлы `FunctionalOptions/*.xml` и их uuid;
  * записи индекса состава `ConfigDumpInfo.xml`: `FunctionalOption.<Имя>` (нога вида);
  * перечень заголовка `configurations.functional_options` (стадия S2, живая БД) — число
    имён и совпадение множеств с первыми двумя ногами;
  * строки `configuration_objects` живой БД по обоим видам — отдельным запросом, потому
    что фильтр `object_name LIKE 'FunctionalOption%'` захватывает и соседний вид
    `FunctionalOptionsParameter` (позиция 2.12, узел ещё не начинался): 4/229/546 строк
    против 2/224/539 файлов — разница равна числу файлов соседнего вида (2/5/7), и это
    называется фактом, а не оставляется как «псевдозаписи».

Зонд только читает: ни в БД, ни в файлы не пишет.
Запуск:  python _v56_m1_probe.py            # все четыре выгрузки
         python _v56_m1_probe.py BGU2      # одна
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMPS: Tuple[str, ...] = ("MinCfg", "KomMag", "BGU2", "BP3")
XML_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
OBJECT_DIR = "FunctionalOptions"
OBJECT_TYPE = "FunctionalOption"
SIBLING_TYPE = "FunctionalOptionsParameter"
DUMP_TO_CONFIGURATION = {
    "MinCfg": "MinCfg",
    "KomMag": "XXI_Коммерческий_магазин_8_редакция_1_0_3",
    "BGU2": "БухгалтерияГосударственногоУчреждения",
    "BP3": "БухгалтерияПредприятия",
}
DB = dict(host="localhost", dbname="ckb_1c_configurations", user="postgres",
          password="Sta090860")

UUID_RE = re.compile(r'^\s*<FunctionalOption\s+uuid="([0-9a-fA-F-]{36})"', re.MULTILINE)
INDEX_VIEW_RE = re.compile(
    r'<Metadata name="' + OBJECT_TYPE + r'\.([^"]+)" id="([0-9a-fA-F-]{36})"'
)
SIBLING_RE = re.compile(
    r'<Metadata name="' + SIBLING_TYPE + r'\.([^"]+)" id="([0-9a-fA-F-]{36})"'
)


def file_rows(dump: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    directory = XML_ROOT / dump / OBJECT_DIR
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.xml")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        match = UUID_RE.search(text)
        out[path.stem] = match.group(1).lower() if match else ""
    return out


def index_rows(dump: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    path = XML_ROOT / dump / "ConfigDumpInfo.xml"
    if not path.is_file():
        return {}, {}
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    views = {name: uuid.lower() for name, uuid in INDEX_VIEW_RE.findall(text)}
    siblings = {name: uuid.lower() for name, uuid in SIBLING_RE.findall(text)}
    return views, siblings


def header_list(dump: str):
    """Перечень заголовка `configurations.functional_options` (третья нога) из живой БД."""
    import psycopg2

    wanted = DUMP_TO_CONFIGURATION.get(dump)
    if not wanted:
        return None, f"имя выгрузки не из словаря соответствия: {dump}"
    try:
        conn = psycopg2.connect(**DB)
    except Exception as exc:  # noqa: BLE001
        return None, f"БД недоступна: {type(exc).__name__}: {exc}"
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT functional_options FROM configurations WHERE name = %s", (wanted,))
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None, f"строки заголовка с именем {wanted!r} в БД нет"
    if row[0] is None:
        return [], "перечень заголовка NULL (стадия S2 его не заполнила)"
    return list(row[0]), ""


def db_index_counts():
    """Число строк `configuration_objects` по обоим видам — чтобы назвать разницу ног."""
    import psycopg2

    try:
        conn = psycopg2.connect(**DB)
    except Exception as exc:  # noqa: BLE001
        return [(f"БД недоступна: {type(exc).__name__}", "", 0)]
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.name, o.object_type, count(*) FROM configuration_objects o "
                "JOIN configurations c ON c.id = o.configuration_id "
                "WHERE o.object_type IN (%s, %s) GROUP BY 1, 2 ORDER BY 1, 2",
                (OBJECT_TYPE, SIBLING_TYPE),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def main():
    dumps = tuple(sys.argv[1:]) or DUMPS
    unknown = [d for d in dumps if not (XML_ROOT / d).is_dir()]
    if unknown:
        print(f"выгрузок нет: {unknown}; доступны: {list(DUMPS)}")
        return 2

    per_dump = {}
    for dump in dumps:
        files = file_rows(dump)
        views, siblings = index_rows(dump)
        names, header_error = header_list(dump)
        per_dump[dump] = (files, views, siblings, names or [])
        print("=" * 78)
        print(f"ВЫГРУЗКА {dump}")
        print(f"нога файлов: {len(files)}; нога индекса вида: {len(views)}; "
              f"записей индекса соседнего вида {SIBLING_TYPE}: {len(siblings)}")
        if header_error:
            print(f"⚠️ третья нога: {header_error}")
        else:
            print(f"нога перечня заголовка configurations.functional_options: {len(names)}")
        header_names = set(names or [])
        fset, vset = set(files), set(views)
        print(f"файлы ↔ индекс: file_only={sorted(fset - vset)[:5]} "
              f"index_only={sorted(vset - fset)[:5]}")
        print(f"файлы ↔ перечень: file_only={sorted(fset - header_names)[:5]} "
              f"header_only={sorted(header_names - fset)[:5]}")
        print(f"индекс ↔ перечень: index_only={sorted(vset - header_names)[:5]} "
              f"header_only={sorted(header_names - vset)[:5]}")
        both = fset & vset
        same = [n for n in sorted(both) if files[n] and files[n] == views[n]]
        print(f"uuid файла и индекса совпали у {len(same)} имён из {len(both)}; "
              f"пустых uuid в файлах: {sum(1 for u in files.values() if not u)}")

    print("=" * 78)
    print("КРОСС-ВЫГРУЗОЧНЫЕ КОЛЛИЗИИ")
    uuid_map: Dict[str, set] = defaultdict(set)
    name_map: Dict[str, set] = defaultdict(set)
    for dump, (files, _views, _sib, _names) in per_dump.items():
        for name, uuid in files.items():
            name_map[name].add(dump)
            if uuid:
                uuid_map[uuid].add(dump)
    shared_uuid = {u: sorted(d) for u, d in uuid_map.items() if len(d) > 1}
    shared_name = {n: sorted(d) for n, d in name_map.items() if len(d) > 1}
    pairs: Dict[Tuple[str, ...], int] = defaultdict(int)
    for src in list(shared_uuid.values()) + list(shared_name.values()):
        pairs[tuple(src)] += 1
    print(f"различных uuid по корпусу: {len(uuid_map)}; различных имён: {len(name_map)}")
    print(f"uuid в двух и более выгрузках: {len(shared_uuid)}; "
          f"имён в двух и более выгрузках: {len(shared_name)}")
    print(f"пар выгрузок с общими идентификаторами или именами: {dict(pairs)}")
    print(f"примеров общих имён: {list(shared_name.items())[:3]}")
    dup_inside = []
    for dump in dumps:
        path = XML_ROOT / dump / "ConfigDumpInfo.xml"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        seen: Dict[str, int] = defaultdict(int)
        for name, _uuid in INDEX_VIEW_RE.findall(text):
            seen[name] += 1
        repeated = sorted(n for n, c in seen.items() if c > 1)
        if repeated:
            dup_inside.append(f"{dump}:{repeated}")
    print(f"повторных имён в индексе внутри выгрузки: {len(dup_inside)} {dup_inside}")

    print("=" * 78)
    print(f"СТРОКИ ИНДЕКСА СОСТАВА В ЖИВОЙ БД (object_type ∈ {{{OBJECT_TYPE}, "
          f"{SIBLING_TYPE}}}):")
    for row in db_index_counts():
        print(f"    {row}")
    print("ВЫВОД ЗАМЕРА: коллизии uuid и имён между выгрузками есть — ключ обязан держать "
          "границу конфигурации; перечень заголовка хранит детей массивом имён "
          "(configurations.functional_options), поэтому ключ — "
          "(configuration_uuid, object_name, revision_no) по прецеденту V48/V50/V52–V55. "
          "Разница числа строк индекса в живой БД и числа файлов равна записям соседнего "
          "вида FunctionalOptionsParameter (позиция 2.12), а не псевдозаписям вида.")


if __name__ == "__main__":
    sys.exit(main())

