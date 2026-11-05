#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""УЗЕЛ V58, шаг П0 (дополнение): востребованность определяемых типов корпусом.

Зачем: узел описывает вид, но ссылки на вид живут в ЧУЖИХ видах (реквизиты, измерения
регистров, константы). Ответ «сколько определяемых типов кем-то вызывается» нужен, чтобы
сказать, что даёт строка вида: без неё ссылка `cfg:DefinedType.<Имя>` остаётся текстом без
цели. Ссылка цели при этом НЕ утверждается: слои реквизитов (группа A модели) не загружены,
поэтому считается только текст ссылки и её совпадение с именем вида той же выгрузки.

Границы прогона:
  - сканируются каталоги видов, у которых бывает блок `<Type>` (перечислены в REF_DIRS), а не
    вся выгрузка — в BGU2 158 925 XML;
  - считается подстрока `cfg:DefinedType.` — форма ссылки на вид. Префиксы `d4p1:` и т. п.
    дают тот же URI (замер V48 2.4.4), поэтому здесь они не различаются: пропущенные ссылки
    называются числом `other_prefix`, а не молчат;
  - сравнение имён — по тексту имени после точки, регистр сохраняется как в выгрузке.
"""

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
REF_DIRS = ("Catalogs", "Documents", "InformationRegisters", "AccumulationRegisters",
            "ChartsOfCharacteristicTypes", "Constants", "BusinessProcesses", "Tasks",
            "ChartsOfAccounts", "ChartsOfCalculationTypes", "AccountingRegisters",
            "CumulationRegisters", "SessionParameters", "CommonAttributes", "FilterCriteria",
            "ExchangePlans")
# `cfg:` — URI текущей конфигурации; прочие префиксы того же URI (замер V48 2.4.4)
REF_RE = re.compile(r"<v8:(?:Type|TypeValue|TypeSet|ValueType)>([^<]*DefinedType\.[^<]*)</v8:")
NAME_RE = re.compile(r"DefinedType\.([A-Za-z0-9_\u0400-\u04FF]+)")


def defined_names(dump):
    directory = DUMP_ROOT / dump / "DefinedTypes"
    if not directory.is_dir():
        return set()
    return {p.stem for p in directory.glob("*.xml")}


def run(dumps):
    for dump in dumps:
        names = defined_names(dump)
        files = hits = other_prefix = 0
        referenced = Counter()
        per_dir = []
        for name in REF_DIRS:
            directory = DUMP_ROOT / dump / name
            if not directory.is_dir():
                continue
            d_files = d_hits = 0
            for path in directory.glob("*.xml"):
                try:
                    text = path.read_text(encoding="utf-8-sig", errors="replace")
                except Exception:  # noqa: BLE001
                    continue
                found = REF_RE.findall(text)
                if not found:
                    continue
                d_files += 1
                d_hits += len(found)
                for value in found:
                    m = NAME_RE.search(value)
                    if m:
                        referenced[m.group(1)] += 1
                    else:
                        other_prefix += 1
            if d_files:
                per_dir.append((name, d_files, d_hits))
            files += d_files
            hits += d_hits
        matched = {n for n in referenced if n in names}
        dangling = {n for n in referenced if n not in names}
        unused = names - set(referenced)
        print(f"=== {dump}: файлов вида {len(names)}; файлов чужих видов со ссылкой {files}; "
              f"вхождений {hits}; ссылок без разобранного имени {other_prefix}")
        for name, d_files, d_hits in per_dir:
            print(f"    {name}: файлов {d_files}, вхождений {d_hits}")
        print(f"    различных имён цели {len(referenced)}; из них определено той же "
              f"выгрузкой {len(matched)}; не определено {len(dangling)}")
        print(f"    определяемых типов, на которые никто не ссылается: {len(unused)}")
        if dangling:
            print(f"    висячих имён (топ 8): {list(dangling)[:8]}")
        if referenced:
            print(f"    самых частых целей (топ 8): {referenced.most_common(8)}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    only = tuple(a for a in sys.argv[1:] if a in DUMPS) or DUMPS
    run(only)


if __name__ == "__main__":
    main()
