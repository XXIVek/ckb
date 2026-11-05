#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V49: форма файла метаданных роли — uuid, Comment, Synonym.

Зачем. Колонки `roles.object_uuid NOT NULL` и смысл пустого `Comment` выводятся не из
одного просмотренного файла, а из корпуса: `Roles/<Имя>.xml` держит uuid АТРИБУТОМ
элемента `<Role>`, а не свойством `<Properties>`. Нужно знать:

1. есть ли атрибут uuid в каждом файле (иначе NOT NULL невозможен);
2. совпадает ли он с именем файла (иначе имя файла не является ключом);
3. сколько файлов держат пустой `<Comment/>` / `<Comment></Comment>` против текста —
   пустой комментарий и отсутствующий комментарий различаются как состояние;
4. есть ли `Synonym` без `<v8:item>` (пустой синоним — тоже состояние);
5. бывает ли у роли `<ChildObjects>` (план мерил: 0 — подтверждаем своим прогоном).

Зонд ничего не пишет в БД.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
DIR_NAME = "Roles"

RE_ROLE_ATTRS = re.compile(r"<Role\b([^>]*)>")
RE_UUID_ATTR = re.compile(r'\buuid="([^"]*)"')
RE_NAME_PROP = re.compile(r"<Properties>.*?<Name>([^<]*)</Name>", re.S)
RE_COMMENT_SELF = re.compile(r"<Comment\s*/>")
RE_COMMENT_EMPTY = re.compile(r"<Comment>\s*</Comment>")
RE_COMMENT_ANY = re.compile(r"<Comment>(.*?)</Comment>", re.S)
RE_SYNONYM_SELF = re.compile(r"<Synonym\s*/>")
RE_SYNONYM_ITEM = re.compile(r"<Synonym>\s*<v8:item>", re.S)
RE_SYNONYM_ANY = re.compile(r"<Synonym>(.*?)</Synonym>", re.S)
RE_CHILD_OBJECTS = re.compile(r"<ChildObjects>")

if len(sys.argv) > 1:
    DUMPS = tuple(d for d in DUMPS if d in set(sys.argv[1:]))


def main() -> int:
    totals = {"files": 0, "uuid": 0, "uuid_empty": 0, "uuid_name_mismatch": 0,
              "comment_absent": 0, "comment_selfclosed": 0, "comment_empty": 0,
              "comment_text": 0, "synonym_absent": 0, "synonym_selfclosed": 0,
              "synonym_empty": 0, "synonym_items": 0,
              "child_objects": 0, "no_role_element": 0}
    for dump in DUMPS:
        directory = DUMP_ROOT / dump / DIR_NAME
        if not directory.exists():
            print(f"{dump}: каталога Roles нет")
            continue
        files = sorted(p for p in directory.glob("*.xml"))
        got = dict.fromkeys(totals, 0)
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            got["files"] += 1
            head = RE_ROLE_ATTRS.search(text)
            if not head:
                got["no_role_element"] += 1
            else:
                found = RE_UUID_ATTR.search(head.group(1))
                if found:
                    got["uuid"] += 1
                    if not found.group(1).strip():
                        got["uuid_empty"] += 1
                name = RE_NAME_PROP.search(text)
                if found and name and name.group(1).strip() != path.stem:
                    got["uuid_name_mismatch"] += 1
            if RE_COMMENT_SELF.search(text):
                got["comment_selfclosed"] += 1
            elif RE_COMMENT_ANY.search(text):
                if RE_COMMENT_EMPTY.search(text):
                    got["comment_empty"] += 1
                else:
                    got["comment_text"] += 1
            else:
                got["comment_absent"] += 1
            if RE_SYNONYM_SELF.search(text):
                got["synonym_selfclosed"] += 1
            elif RE_SYNONYM_ANY.search(text):
                if RE_SYNONYM_ITEM.search(text):
                    got["synonym_items"] += 1
                else:
                    got["synonym_empty"] += 1
            else:
                got["synonym_absent"] += 1
            if RE_CHILD_OBJECTS.search(text):
                got["child_objects"] += 1
        for key in totals:
            totals[key] += got[key]
        print(f"=== {dump} === файлов метаданных ролей: {len(files)}")
        print(f"  атрибут uuid: {got['uuid']} (пустой: {got['uuid_empty']}), "
              f"без элемента <Role>: {got['no_role_element']}, "
              f"имя файла ≠ Name: {got['uuid_name_mismatch']}")
        print(f"  Comment: текст {got['comment_text']}, пустой блок "
              f"{got['comment_empty']}, самозакрывающийся {got['comment_selfclosed']}, "
              f"нет элемента {got['comment_absent']}")
        print(f"  Synonym: с v8:item {got['synonym_items']}, самозакрывающийся "
              f"{got['synonym_selfclosed']}, пустой блок {got['synonym_empty']}, "
              f"нет элемента {got['synonym_absent']}")
        print(f"  ChildObjects: {got['child_objects']}")
        print()
    print("=== ИТОГ ПО КОРПУСУ ===")
    for key, value in totals.items():
        print(f"  {key}: {value:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
