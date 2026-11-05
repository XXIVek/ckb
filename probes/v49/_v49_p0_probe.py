#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V49: замер круга `Roles` по эталонным выгрузкам.

Зачем. Позиция 2.4 нормативного списка — роли — в модели A–H отнесена к группе F
(«специфичная структура вида»: `Roles/Роль1/Ext/Rights.xml`), и модель прямо говорит, что
прятать права в `properties` нельзя: «их нужно уметь собрать обратно». Прежде чем выбирать
модель хранения, нужны четыре числа:

1. раскладка — что реально лежит в каталоге `Roles/` (роль — это два файла: метаданные роли
   и содержимое прав), и есть ли третий вид содержимого;
2. масштаб — сколько объектов `<object>` и элементов `<right>` даёт корпус: от этого зависит,
   кладём ли права строчками в таблицу или содержимым файла;
3. словарь прав — закрыт ли набор имён прав (как словарь `<Type>` у V48) и какие формы
   принимает `<value>`;
4. адресация цели права — `<name>` внутри `<object>` это имя объекта метаданных; у V48 ссылки
   разрешались индексом состава, здесь нужно знать глубину имён (`HTTPService.x.URLTemplate.y.
   Method.post`) и какие виды целей вообще встречаются.

Отдельно меряется содержательная часть прав — ограничения (RLS): `<restrictionTemplate>`
с условием. Без числа ограничений нельзя решить, нужна ли под них отдельная таблица.

Ничего в БД этот зонд не пишет: он только читает файлы и печатает измеренное.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
DIR_NAME = "Roles"

# Аргументы командной строки сужают круг (BGU2 и BP3 — по 100 МБ текста, прогон
# разделяют; без аргументов меряются все четыре выгрузки плана).
if len(sys.argv) > 1:
    DUMPS = tuple(d for d in DUMPS if d in set(sys.argv[1:]))

# --- метаданные роли (Roles/<Имя>.xml) -------------------------------------
RE_ROLE_ROOT = re.compile(r'<Role\s+uuid="([0-9a-fA-F-]{36})"')
RE_PROPS = re.compile(r"<Properties>(.*?)</Properties>", re.S)
RE_TAG = re.compile(r"<([A-Za-z][A-Za-z0-9]*)[ >/]")
RE_CHILD_OBJECTS = re.compile(r"<ChildObjects>")

# --- содержимое прав (Roles/<Имя>/Ext/Rights.xml) --------------------------
RE_FLAGS = re.compile(
    r"<(setForNewObjects|setForAttributesByDefault|independentRightsOfChildObjects)>(.*?)</\1>",
    re.S,
)
RE_OBJECT_BLOCK = re.compile(r"<object>(.*?)</object>", re.S)
RE_FIRST_NAME = re.compile(r"<name>([^<]*)</name>")
RE_RIGHT_BLOCK = re.compile(r"<right>(.*?)</right>", re.S)
RE_VALUE = re.compile(r"<value>(.*?)</value>", re.S)
RE_VALUE_EMPTY = re.compile(r"<value/>")
RE_RESTRICTION_TEMPLATE = re.compile(r"<restrictionTemplate[ >/]")
RE_RESTRICTION = re.compile(r"<restriction[ >/]")
RE_CONDITION = re.compile(r"<condition>(.*?)</condition>", re.S)


def value_form(block: str) -> str:
    """Форма значения права: true / false / пустое / прочее (замер, а не допущение)."""
    if RE_VALUE_EMPTY.search(block):
        return "пустое <value/>"
    match = RE_VALUE.search(block)
    if not match:
        return "<value> отсутствует"
    raw = match.group(1).strip()
    if raw in ("true", "false"):
        return raw
    return f"прочее: {raw[:24]}"


def main() -> int:
    role_files = 0
    role_uuids = 0
    role_props: collections.Counter = collections.Counter()
    role_child_objects = 0
    rights_files = 0
    rights_bytes = 0
    other_files: collections.Counter = collections.Counter()
    flags: collections.Counter = collections.Counter()
    objects_total = 0
    rights_total = 0
    right_names: collections.Counter = collections.Counter()
    value_forms: collections.Counter = collections.Counter()
    target_kinds: collections.Counter = collections.Counter()
    target_depth: collections.Counter = collections.Counter()
    restriction_templates = 0
    restriction_refs = 0
    condition_lengths: list[int] = []
    per_dump: dict[str, object] = {}

    for dump in DUMPS:
        directory = DUMP_ROOT / dump / DIR_NAME
        if not directory.exists():
            per_dump[dump] = "каталога Roles нет"
            continue

        d_role_files = 0
        d_rights_files = 0
        d_objects = 0
        d_rights = 0
        d_bytes = 0
        role_names: set[str] = set()
        rights_names: set[str] = set()

        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(directory).as_posix()
            if path.parent == directory and path.suffix == ".xml":
                role_files += 1
                d_role_files += 1
                role_names.add(path.stem)
                text = path.read_text(encoding="utf-8", errors="replace")
                if RE_ROLE_ROOT.search(text):
                    role_uuids += 1
                if RE_CHILD_OBJECTS.search(text):
                    role_child_objects += 1
                block = RE_PROPS.search(text)
                if block:
                    for tag in RE_TAG.findall(block.group(1)):
                        role_props[tag] += 1
                continue
            if path.name == "Rights.xml" and path.parent.name == "Ext":
                rights_files += 1
                d_rights_files += 1
                rights_names.add(path.parent.parent.name)
                text = path.read_text(encoding="utf-8", errors="replace")
                size = len(text.encode("utf-8", errors="replace"))
                d_bytes += size
                rights_bytes += size
                for name, value in RE_FLAGS.findall(text):
                    flags[f"{name}={value.strip()}"] += 1
                restriction_templates += len(RE_RESTRICTION_TEMPLATE.findall(text))
                restriction_refs += len(RE_RESTRICTION.findall(text))
                for cond in RE_CONDITION.findall(text):
                    condition_lengths.append(len(cond.strip()))
                for obj_block in RE_OBJECT_BLOCK.findall(text):
                    d_objects += 1
                    name_match = RE_FIRST_NAME.search(obj_block)
                    target = name_match.group(1) if name_match else "<имени нет>"
                    target_kinds[target.split(".", 1)[0] or "<пустое>"] += 1
                    target_depth[target.count(".")] += 1
                    for right_block in RE_RIGHT_BLOCK.findall(obj_block):
                        d_rights += 1
                        right_name = RE_FIRST_NAME.search(right_block)
                        right_names[right_name.group(1) if right_name else "<имени нет>"] += 1
                        value_forms[value_form(right_block)] += 1
                continue
            other_files[rel if path.suffix != ".xml" else "<файл xml не метаданных>/Ext"] += 1

        per_dump[dump] = {
            "ролей": d_role_files,
            "rights.xml": d_rights_files,
            "байт": d_bytes,
            "объектов": d_objects,
            "прав": d_rights,
            "прав на роль": round(d_rights / d_rights_files, 1) if d_rights_files else 0,
            "ролей без Rights.xml": len(role_names - rights_names),
            "Rights.xml без роли": len(rights_names - role_names),
        }
        objects_total += d_objects
        rights_total += d_rights

    print(f"РОЛИ: файлов метаданных {role_files} (uuid корня {role_uuids}, <ChildObjects> {role_child_objects})")
    print(f"RIGHTS: файлов {rights_files}, байт {rights_bytes}")
    for dump, values in per_dump.items():
        print(f"  {dump}: {values}")
    if other_files:
        print(f"\nПРОЧИЕ ФАЙЛЫ в Roles/: {sum(other_files.values())}")
        for name, value in other_files.most_common(20):
            print(f"  {name:44} {value}")
    print(f"\nСВОЙСТВА РОЛИ (встречаемость на файл из {role_files}):")
    for name, value in role_props.most_common():
        print(f"  {name:28} {value}")
    print("\nФЛАГИ Rights.xml:")
    for name, value in flags.most_common():
        print(f"  {name:52} {value}")
    print(f"\nМАСШТАБ: объектов {objects_total}, прав {rights_total}")
    print(f"ИМЕНА ПРАВ (разных {len(right_names)}):")
    for name, value in right_names.most_common(60):
        print(f"  {name:44} {value}")
    print("\nФОРМЫ <value>:")
    for name, value in value_forms.most_common():
        print(f"  {name:32} {value}")
    print(f"\nВИДЫ ЦЕЛЕЙ ПРАВА (разных {len(target_kinds)}):")
    for name, value in target_kinds.most_common(60):
        print(f"  {name:34} {value}")
    print("\nГЛУБИНА ИМЕНИ ЦЕЛИ (число точек):")
    for depth in sorted(target_depth):
        print(f"  {depth:3} {target_depth[depth]}")
    print(f"\nОГРАНИЧЕНИЯ (RLS): шаблонов {restriction_templates}, ссылок <restriction> {restriction_refs}")
    if condition_lengths:
        condition_lengths.sort()
        mid = condition_lengths[len(condition_lengths) // 2]
        print(f"  условий: {len(condition_lengths)}, длина (мин {condition_lengths[0]} / медиана {mid} / макс {condition_lengths[-1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

