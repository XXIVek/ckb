#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V49: разрешимость целей прав индексом состава + круг индекса.

Зачем. У V48 ссылочные значения разрешались индексом состава (`ConfigDumpInfo.xml`), и это
был единственный способ назвать цель ссылкой, а не текстом. У прав роли цель — имя объекта
метаданных внутри `<object><name>`, и глубина этого имени больше глубины индекса: встречается
`Catalog.X.TabularSection.Y.Attribute.Z`, `HTTPService.x.URLTemplate.y.Method.post`,
`InformationRegister.X.StandardAttribute.Active`. Вопрос, который решает зонд:

1. сколько целей разрешается индексом ЦЕЛИКОМ (имя есть в индексе), сколько — только
   ПРЕФИКСОМ (объект разрешается, а уровень атрибута/формы/метода индексом не моделируется),
   и сколько не разрешается ничем;
2. какой глубины префикс удаётся сопоставить — это и есть возможная колонка `target_*`;
3. равняется ли множество имён ролей из каталога `Roles/` множеству строк индекса `Role.*`
   (тот же инвариант, что Q7 у V48: круг не должен записываться частями);
4. какой словарь имён прав даёт объединение четырёх выгрузок (закрыт ли словарь).

Ничего в БД зонд не пишет.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
DIR_NAME = "Roles"

RE_INDEX_ROW = re.compile(r'<Metadata name="([^"]*)" id="([^"]*)"')
RE_OBJECT_BLOCK = re.compile(r"<object>(.*?)</object>", re.S)
RE_FIRST_NAME = re.compile(r"<name>([^<]*)</name>")
RE_RIGHT_BLOCK = re.compile(r"<right>(.*?)</right>", re.S)

if len(sys.argv) > 1:
    DUMPS = tuple(d for d in DUMPS if d in set(sys.argv[1:]))


def index_rows(dump: str) -> dict[str, str]:
    """Имена и идентификаторы строк индекса состава выгрузки."""
    text = (DUMP_ROOT / dump / "ConfigDumpInfo.xml").read_text(encoding="utf-8", errors="replace")
    return {name: obj_id for name, obj_id in RE_INDEX_ROW.findall(text)}


def main() -> int:
    all_right_names: set[str] = set()
    per_dump_right_names: dict[str, set[str]] = {}

    for dump in DUMPS:
        directory = DUMP_ROOT / dump / DIR_NAME
        if not directory.exists():
            print(f"{dump}: каталога Roles нет")
            continue
        rows = index_rows(dump)
        index_role = {n for n in rows if n.startswith("Role.")}
        index_role_children = {n for n in index_role if n.count(".") > 1}
        index_role_names = {n.split(".", 1)[1] for n in index_role if n.count(".") == 1}
        file_roles = {p.stem for p in directory.glob("*.xml")}

        resolved_exact = 0
        resolved_prefix = 0
        unresolved = 0
        distinct_targets: set[str] = set()
        unresolvable_samples: list[str] = []
        prefix_depth: collections.Counter = collections.Counter()
        leaf_segment: collections.Counter = collections.Counter()
        target_kinds: collections.Counter = collections.Counter()
        right_names: set[str] = set()
        role_targets = 0

        for path in sorted(directory.rglob("Rights.xml")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for obj_block in RE_OBJECT_BLOCK.findall(text):
                name_match = RE_FIRST_NAME.search(obj_block)
                target = name_match.group(1) if name_match else ""
                if not target:
                    continue
                distinct_targets.add(target)
                target_kinds[target.split(".", 1)[0]] += 1
                if target.startswith("Role."):
                    role_targets += 1
                for right_block in RE_RIGHT_BLOCK.findall(obj_block):
                    right_name = RE_FIRST_NAME.search(right_block)
                    if right_name:
                        right_names.add(right_name.group(1))
                if target in rows:
                    resolved_exact += 1
                    continue
                segments = target.split(".")
                deepest = 0
                for i in range(1, len(segments)):
                    if ".".join(segments[:i]) in rows:
                        deepest = i
                if deepest:
                    resolved_prefix += 1
                    prefix_depth[(len(segments), deepest)] += 1
                    leaf_segment[".".join(segments[deepest:-1]) or "<лист без сегментов>"] += 1
                else:
                    unresolved += 1
                    if len(unresolvable_samples) < 8:
                        unresolvable_samples.append(target)
                for right_block in RE_RIGHT_BLOCK.findall(obj_block):
                    right_name = RE_FIRST_NAME.search(right_block)
                    if right_name:
                        right_names.add(right_name.group(1))

        all_right_names |= right_names
        per_dump_right_names[dump] = right_names
        print(f"=== {dump} ===")
        print(f"  индекс состава: строк {len(rows)}, строк Role.* {len(index_role)} (из них .Rights {len(index_role_children)})")
        print(f"  файлов ролей в каталоге: {len(file_roles)}")
        print(f"  имена каталога вне индекса: {sorted(file_roles - index_role_names)[:5]}")
        print(f"  имена индекса без файла: {sorted(index_role_names - file_roles)[:5]}")
        print(f"  целей права: разных {len(distinct_targets)}, разрешено целиком {resolved_exact}, только префиксом {resolved_prefix}, ничем {unresolved}")
        print(f"  целей вида Role.*: {role_targets}")
        print(f"  словарь прав выгрузки: {len(right_names)}")
        if unresolvable_samples:
            print("  примеры неразрешённых:")
            for sample in unresolvable_samples:
                print(f"    {sample}")
        print(f"  глубина цели / глубина разрешённого префикса (комбинаций: {len(prefix_depth)}):")
        for (total, deepest), value in sorted(prefix_depth.items(), key=lambda kv: -kv[1])[:12]:
            print(f"    сегментов {total}, префикс {deepest}: {value}")
        print("  сегменты после границы разрешения (первые 12):")
        for name, value in leaf_segment.most_common(12):
            print(f"    {name[:60]:60} {value}")
        print("  виды целей:", ", ".join(f"{k}={v}" for k, v in target_kinds.most_common(8)))
        print()

    for dump in DUMPS:
        if dump in per_dump_right_names:
            print(f"  {dump}: словарь {len(per_dump_right_names[dump])}")
    print(f"ОБЪЕДИНЁННЫЙ СЛОВАРЬ ПРАВ: {len(all_right_names)}")
    for dump in per_dump_right_names:
        only = per_dump_right_names[dump] - set().union(
            *(v for k, v in per_dump_right_names.items() if k != dump)
        )
        if only:
            print(f"  только в {dump}: {sorted(only)}")
    print("словарь целиком:", ", ".join(sorted(all_right_names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
