#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V51, шаг П0: цена вторичного содержимого плана обмена (Q3/Q4).

Вопрос, на который отвечает проба: что именно получает загрузка вида, если цикл решено
закрывать полностью. Считает по каждой выгрузке число и вес:

* описаний форм (`Forms/<Имя>.xml`) и их содержимого (`Forms/<Имя>/Ext/Form.xml`
  или `Form.bin` — бинарная форма называется отдельно, это другой контракт V13);
* модулей форм (`Forms/<Имя>/Ext/Form/Module.bsl`);
* описаний макетов (`Templates/<Имя>.xml`) и их содержимого (`Ext/Template.xml|.txt|.bin`);
* слотов вида `Ext/Content.xml`, `Ext/Help.xml`, `Ext/AdditionalIndexes.xml`;
* каталогов команд и их модулей (`Commands/<Имя>/Ext/CommandModule.bsl`).

Только читает. Числа идут в эталоны проверки П6 и в оценку цены П1/П3.

Запуск:  python _v51_p0_content_probe.py [MinCfg BGU2 BP3 KomMag]
"""

import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
VIEW_DIR = "ExchangePlans"

# Категория -> предикат относительно пути внутри каталога вида.
BUCKETS = (
    ("form_desc", lambda p: p.startswith("Forms\\") and p.endswith(".xml") and p.count("\\") == 1),
    ("form_ext_xml", lambda p: "\\Ext\\Form.xml" in p),
    ("form_ext_bin", lambda p: "\\Ext\\Form.bin" in p),
    ("form_module", lambda p: "\\Ext\\Form\\Module.bsl" in p),
    ("tpl_desc", lambda p: p.startswith("Templates\\") and p.endswith(".xml") and p.count("\\") == 1),
    ("tpl_xml", lambda p: "\\Ext\\Template.xml" in p),
    ("tpl_txt", lambda p: "\\Ext\\Template.txt" in p),
    ("tpl_bin", lambda p: "\\Ext\\Template.bin" in p),
    ("slot_content", lambda p: p.endswith("\\Ext\\Content.xml")),
    ("slot_help", lambda p: p.endswith("\\Ext\\Help.xml")),
    ("slot_addidx", lambda p: p.endswith("\\Ext\\AdditionalIndexes.xml")),
    ("cmd_dir", lambda p: p.startswith("Commands\\")),
    ("cmd_module", lambda p: "\\Ext\\CommandModule.bsl" in p),
    ("obj_module", lambda p: p.endswith("\\Ext\\ObjectModule.bsl")),
    ("mgr_module", lambda p: p.endswith("\\Ext\\ManagerModule.bsl")),
)


def human(n):
    return f"{n:>12,} б"


def probe(name):
    view = DUMP_ROOT / name / VIEW_DIR
    print(f"\n{'=' * 74}\n{name}: " + ("есть" if view.is_dir() else "НЕТ каталога вида (состояние выгрузки)"))
    if not view.is_dir():
        return Counter(), Counter()
    counts, sizes = Counter(), Counter()
    for path in view.rglob("*"):
        if path.is_dir():
            continue
        rel = str(path.relative_to(view))
        for bucket, match in BUCKETS:
            if match(rel):
                counts[bucket] += 1
                sizes[bucket] += path.stat().st_size
    for bucket, _ in BUCKETS:
        if counts[bucket]:
            print(f"    {bucket:14} {counts[bucket]:5} шт {human(sizes[bucket])}")
    return counts, sizes


def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== П0: цена вторичного содержимого плана обмена (только чтение) ===")
    total_c, total_s = Counter(), Counter()
    per_dump = {}
    for name in wanted:
        c, s = probe(name)
        per_dump[name] = (c, s)
        total_c.update(c)
        total_s.update(s)
    print(f"\n{'=' * 74}\nИТОГО по запрошенным выгрузкам:")
    for bucket, _ in BUCKETS:
        if total_c[bucket]:
            print(f"    {bucket:14} {total_c[bucket]:5} шт {human(total_s[bucket])}")
    print("\nФормы считаются как сущность по числу `form_desc`; содержимое формы — это")
    print("form_ext_xml или form_ext_bin (бинарная форма — отдельный контракт V13).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
