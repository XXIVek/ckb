#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M1-замер узла V54: коллизия идентификаторов и имён регламентных заданий.

Зачем: ключ версионности выбирается по замеру, а не по схеме соседа. Прецеденты — V52
(15 верхних строк вида дают 14 uuid: `FilterCriterion.СвязанныеДокументы` стоит в BGU2 и
BP3) и V53 (162 uuid и 192 имени общие у BGU2 и BP3). К позиции 2.9 тот же вопрос: если
`ScheduledJob.<Имя>` встречается в двух выгрузках с одним uuid, ключ по одному
`object_uuid` слил бы два круга в одну цепь ревизий; если имя повторяется внутри
выгрузки — ключ по имени внутри конфигурации не различал бы строки.

Замером проверяются ТРИ ноги круга (правило V43: третья нога — перечень заголовка):

  * файлы `ScheduledJobs/*.xml` и их uuid;
  * записи индекса состава `ConfigDumpInfo.xml`: `ScheduledJob.<Имя>` (нога вида) и
    `ScheduledJob.<Имя>.Schedule` (нога содержимого);
  * перечень заголовка `configurations.scheduled_jobs` (стадия S2, живая БД) — число
    имён и совпадение множеств с первыми двумя ногами;
  * нога содержимого: файл `<Имя>/Ext/Schedule.xml` против строки индекса `.Schedule`
    (ровность ног — инвариант, который будет держать проверка П6).

Ноль коллизий — тоже результат: он обязан быть назван, а не подразумевать отсутствие
проверки. Зонд только читает: ни в БД, ни в файлы не пишет.

Запуск:  python _v54_m1_probe.py            # все четыре выгрузки
         python _v54_m1_probe.py MinCfg     # одна
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
OBJECT_DIR = "ScheduledJobs"
OBJECT_TYPE = "ScheduledJob"
# Имя папки выгрузки ≠ name строки заголовка БД (прецедент V52/V53): соответствие
# установлено замером П0 — число верхних строк индекса совпало с числом файлов
# регистрации (2↔MinCfg, 1↔KomMag, 157↔BGU2, 186↔BP3), а не предполагаемо по названию.
DUMP_TO_CONFIGURATION = {
    "MinCfg": "MinCfg",
    "KomMag": "XXI_Коммерческий_магазин_8_редакция_1_0_3",
    "BGU2": "БухгалтерияГосударственногоУчреждения",
    "BP3": "БухгалтерияПредприятия",
}
DB = dict(host="localhost", dbname="ckb_1c_configurations", user="postgres",
          password="Sta090860")

UUID_RE = re.compile(r'^\s*<ScheduledJob\s+uuid="([0-9a-fA-F-]{36})"', re.MULTILINE)
# Нога вида: id — ровно 36 символов (дочерняя запись оканчивается на `.0`, её этот
# шаблон не ловит — различение ног построено на форме id, а не на догадке).
INDEX_VIEW_RE = re.compile(
    r'<Metadata name="' + OBJECT_TYPE + r'\.([^".]+)" id="([0-9a-fA-F-]{36})"'
)
# Нога содержимого: id = `<uuid родителя>.<номер>`, имя = `<Имя>.<Вид содержимого>`.
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


def header_list(dump: str):
    """Перечень заголовка `configurations.scheduled_jobs` (третья нога) из живой БД."""
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
            cur.execute("SELECT scheduled_jobs FROM configurations WHERE name = %s", (wanted,))
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None, f"строки заголовка с именем {wanted!r} в БД нет"
    if row[0] is None:
        return [], "перечень заголовка NULL (стадия S2 его не заполнила)"
    return list(row[0]), ""


def duplicate_index_names(dump: str) -> List[str]:
    """Повторные имена вида в индексе состава (строки с одинаковым name)."""
    path = XML_ROOT / dump / "ConfigDumpInfo.xml"
    if not path.is_file():
        return []
    names = [name for name, _uuid in INDEX_VIEW_RE.findall(
        path.read_text(encoding="utf-8-sig", errors="replace"))]
    seen, dup = set(), set()
    for name in names:
        (dup if name in seen else seen).add(name)
    return sorted(dup)


def probe_dump(dump: str) -> Dict[str, object]:
    print(f"\n=== {dump}: {OBJECT_DIR} ===")
    files = file_rows(dump)
    views, children = index_rows(dump)
    header, header_error = header_list(dump)
    print(f"файлов: {len(files)}; строк индекса вида: {len(views)}; "
          f"строк индекса содержимого: {sum(len(v) for v in children.values())}; "
          f"имён в перечне заголовка: {'нет данных' if header is None else len(header)}")
    if header_error:
        print(f"  ⚠️ {header_error}")

    empty_uuid = sorted(n for n, u in files.items() if not u)
    distinct = {u for u in files.values() if u}
    with_uuid = len(files) - len(empty_uuid)
    print(f"файлов без uuid: {len(empty_uuid)} {empty_uuid[:3]}; различных uuid: {len(distinct)} "
          f"при файлах с uuid {with_uuid} → коллизий uuid внутри выгрузки: "
          f"{with_uuid - len(distinct)}")
    dup = duplicate_index_names(dump)
    print(f"повторных имён в индексе состава: {len(dup)} {dup[:3]}")

    only_file = sorted(set(files) - set(views))
    only_index = sorted(set(views) - set(files))
    uuid_diff = sorted(n for n in set(files) & set(views) if files[n] != views[n])
    print(f"только файлами: {len(only_file)} {only_file[:3]}; только индексом: "
          f"{len(only_index)} {only_index[:3]}; uuid расходится: {len(uuid_diff)} {uuid_diff[:3]}")
    if header is not None:
        head = set(header)
        print(f"перечень заголовка: вне файлов {len(head - set(files))} "
              f"{sorted(head - set(files))[:3]}; вне индекса {len(head - set(views))} "
              f"{sorted(head - set(views))[:3]}; имён вида вне перечня "
              f"{len(set(views) - head)} {sorted(set(views) - head)[:3]}")

    with_content = [n for n in files
                    if (XML_ROOT / dump / OBJECT_DIR / n / "Ext" / "Schedule.xml").is_file()]
    indexed = {n for n, kinds in children.items() if kinds}
    kinds_total = defaultdict(int)
    for vals in children.values():
        for k in vals:
            kinds_total[k] += 1
    print(f"файлов Ext/Schedule.xml: {len(with_content)}; имён со строкой .Schedule: "
          f"{len(indexed)}; видов содержимого в индексе: {dict(kinds_total)}")
    print(f"содержимое файлом без строки индекса: {len(set(with_content) - indexed)} "
          f"{sorted(set(with_content) - indexed)[:3]}; строка индекса без файла: "
          f"{len(indexed - set(with_content))} {sorted(indexed - set(with_content))[:3]}")
    print(f"заданий без содержимого (ни файлом, ни индексом): "
          f"{len(set(files) - set(with_content) - indexed)}")
    return {"files": files, "views": views}


def cross_dump(per_dump: Dict[str, Dict[str, object]]) -> None:
    print("\n=== кросс-выгрузочная коллизия (решающий замер ключа M1) ===")
    by_uuid = defaultdict(set)
    by_name = defaultdict(set)
    total_files = 0
    for dump, data in per_dump.items():
        files: Dict[str, str] = data["files"]  # type: ignore[assignment]
        total_files += len(files)
        for name, uuid in files.items():
            by_name[name].add(dump)
            if uuid:
                by_uuid[uuid].add(dump)
    shared_uuid = {u: sorted(d) for u, d in by_uuid.items() if len(d) > 1}
    shared_name = {n: sorted(d) for n, d in by_name.items() if len(d) > 1}
    print(f"файлов по корпусу: {total_files}; различных uuid: {len(by_uuid)}; "
          f"различных имён: {len(by_name)}")
    print(f"uuid в двух и более выгрузках: {len(shared_uuid)}; "
          f"имён в двух и более выгрузках: {len(shared_name)}")
    for uuid_value, dumps in sorted(shared_uuid.items())[:5]:
        names = sorted(n for d in dumps for n, u in per_dump[d]["files"].items()  # type: ignore[union-attr]
                       if u == uuid_value)
        print(f"    uuid {uuid_value} → {dumps} имена: {names[:3]}")
    for name, dumps in sorted(shared_name.items())[:5]:
        uuids = {per_dump[d]["files"].get(name, "") for d in dumps}  # type: ignore[union-attr]
        print(f"    имя {name} → {dumps} uuid совпадают: {len(uuids) == 1}")
    print("\nВывод: ключ обязан включать границу конфигурации, если общих uuid или общих "
          f"имён больше нуля (здесь: uuid {len(shared_uuid)}, имён {len(shared_name)}); "
          "ключ по одному object_uuid слил бы эти круги в одну цепь ревизий.")


def main(argv=None) -> int:
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== M1 замеры позиции 2.9 ScheduledJobs (только чтение) ===")
    per_dump: Dict[str, Dict[str, object]] = {}
    for dump in wanted:
        if dump not in DUMPS:
            print(f"выгрузка не из списка замеров: {dump}")
            continue
        per_dump[dump] = probe_dump(dump)
    if len(per_dump) > 1:
        cross_dump(per_dump)
    print("\nисточник норматива позиции: C:\\1C_LLM\\Структура конфигурации.txt, "
          "2.9 Регламентные задания")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
