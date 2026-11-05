#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V49: связь «условие права -> шаблон ограничения» и позиция O6.

Зачем. `_v49_p0_element_probe.py` показал закрытый словарь: в `<right>` лежат только
`name`, `value`, `restrictionByCondition` - ЯВНОЙ ссылки права на `<restrictionTemplate>`
выгрузка не содержит. Значит «ссылка строки права на шаблон» может быть только выводом
из текста условия (вызов вида `#ДляОбъекта("")`). Прежде чем класть такую ссылку в
схему, нужны четыре числа:

1. сколько условий права вызывают шаблон, объявленный в ЭТОЙ роли (иначе вывод нечем
   строить);
2. сколько вызывают имя, которого нет ни в одной роли конфигурации (висячий вызов -
   состояние, а не ссылка); отдельно печатается словарь таких токенов: среди них
   заведомо есть ключевые слова предпроцессора (`#Если`, `#ИначеЕсли`), и путать их с
   висячими вызовами нельзя;
3. уникально ли имя шаблона внутри одной роли (повторного объявления быть не должно -
   иначе имя не является ключом);
4. позиция O6: «то же имя, другой текст» и обратный случай «один текст под двумя
   именами» - по конфигу и по корпусу.

Зонд ничего не пишет в БД.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
DIR_NAME = "Roles"
NS = "{http://v8.1c.ru/8.2/roles}"

# вызов в тексте условия: #Имя( ... ) - имя до первой скобки
RE_CALL = re.compile(r"#([A-Za-zА-Яа-яЁё_][\wА-Яа-яЁё]*)\s*\(")
# имя шаблона по тексту файла (дешёвый проход 1): только объявление, без тела
RE_TEMPLATE_NAME = re.compile(
    r"<restrictionTemplate>\s*<name>([^<]*)</name>", re.S)

if len(sys.argv) > 1:
    DUMPS = tuple(d for d in DUMPS if d in set(sys.argv[1:]))


def text_of(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def role_templates(root):
    """Имя шаблона -> множество отпечатков его текста в одном файле роли."""
    names: dict[str, set[int]] = defaultdict(set)
    for tpl in root.findall(NS + "restrictionTemplate"):
        names[text_of(tpl.find(NS + "name"))].add(
            hash(text_of(tpl.find(NS + "condition"))))
    return dict(names)


def main() -> int:
    merged = {"conditions": 0, "declared": 0, "out_file": 0, "out_config": 0,
              "dup_in_file": 0}
    merged_unknown: Counter[str] = Counter()
    merged_name_digests: dict[str, set[int]] = defaultdict(set)
    merged_digest_names: dict[int, set[str]] = defaultdict(set)

    for dump in DUMPS:
        directory = DUMP_ROOT / dump / DIR_NAME
        if not directory.exists():
            print(f"{dump}: каталога Roles нет")
            continue
        files = sorted(directory.rglob("Rights.xml"))
        # проход 1 — только имена шаблонов по файлам (дешёвый разбор текста): нужен,
        # чтобы отличить «вызов имени чужой роли» от «вызова, которого нет в базе».
        per_file_names: dict[str, set[str]] = {}
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            per_file_names[str(path)] = set(RE_TEMPLATE_NAME.findall(text))
        config_names: set[str] = set()
        for names in per_file_names.values():
            config_names |= names
        # сопоставление вызова с объявлением — по полному имени И по сигнатуре до `(`
        config_full = set(config_names)
        config_prefix = {n.split("(", 1)[0] for n in config_names}

        conditions = declared = out_file = out_config = dup_in_file = 0
        unknown_tokens: Counter[str] = Counter()
        name_digests: dict[str, set[int]] = defaultdict(set)
        digest_names: dict[int, set[str]] = defaultdict(set)
        # проход 2 — настоящий разбор: права, условия, отпечатки текстов шаблонов.
        for path in files:
            root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
            names = role_templates(root)
            for name, digests in names.items():
                name_digests[name] |= digests
                for digest in digests:
                    digest_names[digest].add(name)
            if any(len(d) > 1 for d in names.values()):
                dup_in_file += 1
            # имя шаблона несёт сигнатуру параметров (`ДляОбъекта(ПолеОбъекта)`),
            # а вызов в тексте пишется как `#ДляОбъекта("")`. Сопоставление возможно
            # только по сигнатуре до `(` — сравнение полными именами даёт ложный
            # «необъявленный вызов» (замер: 4 735 из 4 744 условий BGU2).
            own_full = set(names)
            own_prefix = {n.split("(", 1)[0] for n in names}
            for obj in root.findall(NS + "object"):
                for right in obj.findall(NS + "right"):
                    cond = right.find(NS + "restrictionByCondition/" + NS + "condition")
                    if cond is None:
                        continue
                    conditions += 1
                    tokens = set(RE_CALL.findall(text_of(cond)))
                    hit_own = {t for t in tokens if t in own_full or t in own_prefix}
                    if hit_own:
                        declared += 1
                    if tokens - own_full - own_prefix:
                        out_file += 1
                    if tokens - config_full - config_prefix:
                        out_config += 1
                        unknown_tokens.update(
                            t for t in tokens - config_full - config_prefix)

        merged["conditions"] += conditions
        merged["declared"] += declared
        merged["out_file"] += out_file
        merged["out_config"] += out_config
        merged["dup_in_file"] += dup_in_file
        merged_unknown.update(unknown_tokens)
        for name, digests in name_digests.items():
            merged_name_digests[name] |= digests
        for digest, names_for in digest_names.items():
            merged_digest_names[digest] |= names_for

        print(f"=== {dump} === файлов Rights.xml: {len(files)}")
        print(f"  условий права: {conditions}")
        print(f"  вызывают шаблон СВОЕЙ роли: {declared}")
        print(f"  вызывают имя чужой роли этой конфигурации: {out_file - out_config}")
        print(f"  вызывают имя, которого нет в конфигурации: {out_config}")
        print(f"  файлов с повторным объявлением одного имени: {dup_in_file}")
        print(f"  имён шаблонов в конфигурации: {len(name_digests)}; "
              f"различных текстов: {len(digest_names)}")
        print(f"  имя с несколькими текстами: "
              f"{[n for n, d in name_digests.items() if len(d) > 1] or 'нет'}")
        print(f"  текст под несколькими именами: "
              f"{[sorted(ns) for ns in digest_names.values() if len(ns) > 1] or 'нет'}")
        print(f"  необъявленные токены (top): {dict(unknown_tokens.most_common(12))}")
        print()

    print("=== ИТОГ ПО КОРПУСУ ===")
    print(f"условий права: {merged['conditions']}")
    print(f"  вызывают шаблон своей роли: {merged['declared']}")
    print(f"  вызывают имя чужой роли этой конфигурации: "
          f"{merged['out_file'] - merged['out_config']}")
    print(f"  вызывают имя, которого нет в конфигурации: {merged['out_config']}")
    print(f"файлов с повторным объявлением одного имени: {merged['dup_in_file']}")
    print(f"имён шаблонов по корпусу: {len(merged_name_digests)}; "
          f"различных текстов: {len(merged_digest_names)}")
    print(f"имя с несколькими текстами по корпусу: "
          f"{[n for n, d in merged_name_digests.items() if len(d) > 1] or 'нет'}")
    print(f"текст под несколькими именами по корпусу: "
          f"{[sorted(ns) for ns in merged_digest_names.values() if len(ns) > 1] or 'нет'}")
    print(f"словарь необъявленных токенов ({len(merged_unknown)}): "
          f"{dict(merged_unknown.most_common(40))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
