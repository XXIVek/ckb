#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M1-замер узла V53: коллизия идентификаторов и имён подписок на события.

Зачем: ключ версионности выбирается по замеру, а не по схеме соседа (прецедент V52,
замер 1.3: 15 верхних строк вида дают 14 uuid, потому что `FilterCriterion.
СвязанныеДокументы` стоит в BGU2 и BP3). Ровно тот же вопрос к позиции 2.8: если
`EventSubscription.<Имя>` встречается в двух выгрузках с одним uuid, ключ по одному
`object_uuid` слил бы два круга в одну цепь ревизий; если имя повторяется внутри
выгрузки — ключ по имени внутри конфигурации не различал бы строки.

Что меряет (по файлам `EventSubscriptions/*.xml` и записям `ConfigDumpInfo.xml`):
  * число файлов и число РАЗЛИЧНЫХ uuid на выгрузку — расхождение называет коллизию
    внутри выгрузки;
  * пары `uuid -> [выгрузки]` с числом выгрузок больше одной — кросс-выгрузочная
    коллизия (граница конфигурации в ключе);
  * пары `имя -> [выгрузки]` и повторные имена внутри одной выгрузки;
  * совпадает ли круг файлов с записями индекса состава `EventSubscription.<Имя>`
    (ровность двух ног круга — тот же инвариант, что замер 1.1 у V52).

Ответ — текст в stdout; доказательством узлу он не записывается, цифра плана берётся
из файла `_v53_p0_out.txt` (П0). Ноль коллизий — тоже результат: он обязан быть
назван, а не подразумевать отсутствие проверки.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

DUMPS: Tuple[str, ...] = ("MinCfg", "KomMag", "BGU2", "BP3")
XML_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
OBJECT_DIR = "EventSubscriptions"
OBJECT_TYPE = "EventSubscription"
UUID_RE = re.compile(r'^\s*<EventSubscription\s+uuid="([0-9a-fA-F-]{36})"', re.MULTILINE)
INDEX_ENTRY_RE = re.compile(
    r'<Metadata name="' + OBJECT_TYPE + r'\.([^"]+)" id="([0-9a-fA-F-]{36})"'
)


def file_uuids(dump: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    directory = XML_ROOT / dump / OBJECT_DIR
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.xml")):
        match = UUID_RE.search(path.read_text(encoding="utf-8-sig", errors="replace"))
        out[path.stem] = match.group(1).lower() if match else ""
    return out


def index_rows(dump: str) -> Dict[str, str]:
    path = XML_ROOT / dump / "ConfigDumpInfo.xml"
    if not path.is_file():
        return {}
    return {name: uuid.lower()
            for name, uuid in INDEX_ENTRY_RE.findall(path.read_text(encoding="utf-8-sig", errors="replace"))}


def main() -> int:
    uuid_dumps: Dict[str, List[str]] = defaultdict(list)
    name_dumps: Dict[str, List[str]] = defaultdict(list)
    for dump in DUMPS:
        files = file_uuids(dump)
        index = index_rows(dump)
        distinct = {u for u in files.values() if u}
        dup_inside_uuid = sorted(u for u, c in
                                {u: list(files.values()).count(u) for u in distinct}.items() if c > 1)
        for uuid in distinct:
            uuid_dumps[uuid].append(dump)
        for name in files:
            name_dumps[name].append(dump)
        only_files = sorted(set(files) - set(index))
        only_index = sorted(set(index) - set(files))
        uuid_mismatch = sorted(n for n in set(files) & set(index) if files[n] != index[n])
        print(f"=== {dump} ===")
        print(f"  файлов: {len(files)}, различных uuid: {len(distinct)}, "
              f"коллизий uuid внутри выгрузки: {len(dup_inside_uuid)} {dup_inside_uuid[:3]}")
        print(f"  записей индекса {OBJECT_TYPE}.: {len(index)}, только файлами: {len(only_files)}, "
              f"только индексом: {len(only_index)}, uuid расходится: {len(uuid_mismatch)}")
        if only_files[:3]:
            print(f"    примеры только файлами: {only_files[:3]}")
        if only_index[:3]:
            print(f"    примеры только индексом: {only_index[:3]}")
    cross_uuid = {u: d for u, d in uuid_dumps.items() if len(d) > 1}
    cross_name = {n: d for n, d in name_dumps.items() if len(d) > 1}
    print("=== кросс-выгрузочные коллизии ===")
    print(f"  uuid в двух и более выгрузках: {len(cross_uuid)}")
    for uuid, dumps in sorted(cross_uuid.items())[:10]:
        print(f"    {uuid} -> {dumps}")
    print(f"  имён подписок в двух и более выгрузках: {len(cross_name)}")
    for name, dumps in sorted(cross_name.items())[:10]:
        print(f"    {name} -> {dumps}")
    print(f"  всего подписок по файлам: {sum(len(name_dumps[n]) for n in name_dumps)}, "
          f"различных имён: {len(name_dumps)}, различных uuid: {len(uuid_dumps)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
