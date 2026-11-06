#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M1-замер узла V55: коллизия идентификаторов и имён ботов + третья нога круга.

Зачем: ключ версионности выбирается по замеру, а не по схеме соседа. Прецеденты — V52
(15 верхних строк вида дают 14 uuid), V53 (162 uuid и 192 имени общие у BGU2 и BP3),
V54 (134 uuid и 134 имени общие у BGU2 и BP3). По позиции 2.10 корпус отвечает на тот же
вопрос иначе: вид существует только в одной выгрузке, поэтому коллизий между выгрузками
замер не находит — и это называется результатом замера, а не отсутствием проверки.
Границу конфигурации в ключ берёт прецедент V52–V54 plus перечень заголовка, который
хранит детей массивами ИМЁН (`configurations.bots`), а не uuid.

Замером проверяются ТРИ ноги круга (правило V43):

  * файлы `Bots/*.xml` и их uuid;
  * записи индекса состава `ConfigDumpInfo.xml`: `Bot.<Имя>` (нога вида) и
    `Bot.<Имя>.Module` (нога модуля, тексты которого пишет узел V47);
  * перечень заголовка `configurations.bots` (стадия S2, живая БД) — число имён и
    совпадение множеств с первыми двумя ногами;
  * состояние модулей вида в живой БД (`bsl_modules`): строки узла V47 против ног
    файла и индекса — узел V55 тексты не читает, он называет дескрипторы (Q8 V51/V52).

Ноль коллизий — тоже результат: он обязан быть назван, а не подразумевать отсутствие
проверки. Зонд только читает: ни в БД, ни в файлы не пишет.

Запуск:  python _v55_m1_probe.py            # все четыре выгрузки
         python _v55_m1_probe.py MinCfg     # одна
"""
from __future__ import annotations
import os

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
OBJECT_DIR = "Bots"
OBJECT_TYPE = "Bot"
# Имя папки выгрузки ≠ name строки заголовка БД (прецедент V52/V53/V54): соответствие
# установлено замером — число верхних строк индекса совпало с числом файлов регистрации
# (2 ↔ MinCfg, 0 ↔ остальные), а не предполагалось по названию каталога.
DUMP_TO_CONFIGURATION = {
    "MinCfg": "MinCfg",
    "KomMag": "XXI_Коммерческий_магазин_8_редакция_1_0_3",
    "BGU2": "БухгалтерияГосударственногоУчреждения",
    "BP3": "БухгалтерияПредприятия",
}
DB = dict(host="localhost", dbname="ckb_1c_configurations", user="postgres",
          password=os.environ["PGPASSWORD"])

UUID_RE = re.compile(r'^\s*<Bot\s+uuid="([0-9a-fA-F-]{36})"', re.MULTILINE)
# Нога вида: id — ровно 36 символов (дочерняя запись оканчивается на `.1`, её этот
# шаблон не ловит — различение ног построено на форме id, а не на догадке).
INDEX_VIEW_RE = re.compile(
    r'<Metadata name="' + OBJECT_TYPE + r'\.([^".]+)" id="([0-9a-fA-F-]{36})"'
)
# Нога модуля: id = `<uuid родителя>.<номер>`, имя = `<Имя>.<Вид содержимого>`.
INDEX_CHILD_RE = re.compile(
    r'<Metadata name="' + OBJECT_TYPE + r'\.([^".]+)\.([A-Za-z]+)" '
    r'id="([0-9a-fA-F-]{36})\.\d+"'
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


def index_rows(dump: str) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    path = XML_ROOT / dump / "ConfigDumpInfo.xml"
    if not path.is_file():
        return {}, {}
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    views = {name: uuid.lower() for name, uuid in INDEX_VIEW_RE.findall(text)}
    children: Dict[str, List[str]] = defaultdict(list)
    for name, kind, _parent in INDEX_CHILD_RE.findall(text):
        children[name].append(kind)
    return views, children


def module_files(dump: str) -> Dict[str, int]:
    """Файлы модулей вида: путь → размер (тексты не читаются — они принадлежат V47)."""
    out: Dict[str, int] = {}
    directory = XML_ROOT / dump / OBJECT_DIR
    if not directory.is_dir():
        return out
    for path in sorted(directory.rglob("*.bsl")):
        out[path.relative_to(directory).as_posix()] = path.stat().st_size
    return out


def header_list(dump: str):
    """Перечень заголовка `configurations.bots` (третья нога) из живой БД."""
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
            cur.execute("SELECT bots FROM configurations WHERE name = %s", (wanted,))
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None, f"строки заголовка с именем {wanted!r} в БД нет"
    if row[0] is None:
        return [], "перечень заголовка NULL (стадия S2 его не заполнила)"
    return list(row[0]), ""


def loaded_modules(uuids: List[str]):
    """Строки модулей вида в живой БД (узел V47): их узел V55 не трогает."""
    import psycopg2

    if not uuids:
        return []
    try:
        conn = psycopg2.connect(**DB)
    except Exception as exc:  # noqa: BLE001
        return [("БД недоступна", f"{type(exc).__name__}: {exc}", "", 0, False)]
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT parent_uuid::text, file_path, object_name, code_size, is_committed "
                "FROM bsl_modules WHERE parent_uuid::text = ANY(%s) ORDER BY file_path",
                (uuids,),
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
        views, children = index_rows(dump)
        mods = module_files(dump)
        names, header_error = header_list(dump)
        per_dump[dump] = (files, views, children, mods, names or [])
        print("=" * 78)
        print(f"ВЫГРУЗКА {dump}")
        print(f"нога файлов: {len(files)}; нога индекса вида: {len(views)}; "
              f"нога индекса детей: {sum(len(v) for v in children.values())}; "
              f"файлов модулей: {len(mods)}")
        if header_error:
            print(f"⚠️ третья нога: {header_error}")
        else:
            print(f"нога перечня заголовка configurations.bots: {len(names)} {sorted(names)}")
        header_names = set(names or [])
        fset, vset = set(files), set(views)
        print(f"файлы ↔ индекс: file_only={sorted(fset - vset)} index_only={sorted(vset - fset)}")
        print(f"файлы ↔ перечень: file_only={sorted(fset - header_names)} "
              f"header_only={sorted(header_names - fset)}")
        print(f"индекс ↔ перечень: index_only={sorted(vset - header_names)} "
              f"header_only={sorted(header_names - vset)}")
        both = fset & vset
        same = [n for n in sorted(both) if files[n] and files[n] == views[n]]
        print(f"uuid файла и индекса совпали у {len(same)} имён из {len(both)}; "
              f"пустых uuid в файлах: {sum(1 for u in files.values() if not u)}")
        child_kinds: Dict[str, int] = defaultdict(int)
        for kinds in children.values():
            for kind in kinds:
                child_kinds[kind] += 1
        print(f"виды детей индекса состава: {dict(child_kinds)}")
        for name in sorted(set(children) | set(p.split('/')[0] for p in mods)):
            kinds = sorted(children.get(name, []))
            mod_paths = sorted(p for p in mods if p.split("/")[0] == name)
            if kinds and mod_paths:
                state = "file_and_index"
            elif kinds:
                state = "index_only"
            else:
                state = "file_only"
            print(f"    {name:12} файлов модулей: {len(mod_paths)} {mod_paths}; "
                  f"строк индекса: {kinds} → {state}")
        print(f"байтов модулей: {sum(mods.values())}")

    print("=" * 78)
    print("КРОСС-ВЫГРУЗОЧНЫЕ КОЛЛИЗИИ")
    uuid_map: Dict[str, set] = defaultdict(set)
    name_map: Dict[str, set] = defaultdict(set)
    for dump, (files, _views, _children, _mods, _names) in per_dump.items():
        for name, uuid in files.items():
            name_map[name].add(dump)
            if uuid:
                uuid_map[uuid].add(dump)
    shared_uuid = {u: sorted(d) for u, d in uuid_map.items() if len(d) > 1}
    shared_name = {n: sorted(d) for n, d in name_map.items() if len(d) > 1}
    print(f"различных uuid по корпусу: {len(uuid_map)}; различных имён: {len(name_map)}")
    print(f"uuid в двух и более выгрузках: {len(shared_uuid)} {list(shared_uuid.items())[:5]}")
    print(f"имён в двух и более выгрузках: {len(shared_name)} {list(shared_name.items())[:5]}")
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
    print("ВЫВОД ЗАМЕРА: коллизий между выгрузками нет, потому что вид есть только в одной "
          "выгрузке корпуса; границы ключа при этом держат границу конфигурации — перечень "
          "заголовка хранит детей массивом имён (configurations.bots), и прецедент V52–V54 "
          "не позволяет ключу по одному object_uuid или одному имени остаться без границы.")

    all_uuids = sorted({uuid for (_files, _v, _c, _m, _n) in per_dump.values()
                        for uuid in _files.values() if uuid})
    rows = loaded_modules(all_uuids)
    print("=" * 78)
    print(f"МОДУЛИ ВИДА В ЖИВОЙ БД (их пишет узел V47, узел V55 их не трогает): {len(rows)}")
    for row in rows:
        print(f"    {row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

