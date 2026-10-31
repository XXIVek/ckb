#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V51, шаг П1: структура перечня `<Content>` плана обмена (колонки и домены).

Вопрос пробы — какие колонки обязана иметь таблица `exchange_plan_content` и какие
значения держит `AutoRecord`. Отвечает замером, а не предположением: домен значения в
этом проекте замыкается корпусом выгрузок (прецедент V48/V49/V50), а не справочником.

Считает по всем выгрузкам:
* число файлов `ExchangePlans/<Имя>/Ext/Content.xml` и число записей в них;
* теги цели (`xr:Metadata` и другие) и их детей;
* значения `AutoRecord` (в т.ч. отсутствие тега и пустой текст — три разных состояния);
* где именно лежит элемент `Content` (в Properties или отдельно).

Только читает. Числа идут в CHECK-словари DDL и в эталоны проверки П6.

Запуск:  python _v51_p1_content_probe.py
"""
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
VIEW_DIR = "ExchangePlans"


def local(tag):
    return tag.split("}")[-1]


def parent_map(root):
    return {child: parent for parent in root.iter() for child in parent}


def probe(name, totals):
    view = DUMP_ROOT / name / VIEW_DIR
    if not view.is_dir():
        print(f"{name}: каталога вида нет (состояние выгрузки)")
        return
    for path in sorted(view.rglob("*.xml")):
        # круг пробы: файл вида (`ExchangePlans/<Имя>.xml`) и слот `Ext/Content.xml` —
        # перечень мог лежать и там, и там; ответ даёт замер, а не предположение
        if path.name != "Content.xml" and path.parent != view:
            continue
        try:
            root = ET.parse(path).getroot()
        except Exception as exc:  # noqa: BLE001 - состояние выгрузки называется, а не теряется
            print(f"  [РАЗБОР НЕ ВЫПОЛНЕН] {name}/{path.name}: {exc}")
            continue
        owners = parent_map(root)
        contents = [e for e in root.iter()
                    if local(e.tag) in ("ExchangePlanContent", "Content")]
        if not contents:
            continue
        totals["files"] += 1
        totals["files_where"][("slot" if path.name == "Content.xml" else "view_file")] += 1
        for content in contents:
            owner = owners.get(content)
            totals["content_in"][f"{local(content.tag)} <- {local(owner.tag) if owner is not None else '<корень>'}"] += 1
            kids = list(content)
            if not kids:
                totals["empty_content"] += 1
            for entry in kids:
                totals["entries"] += 1
                totals["target_tag"][local(entry.tag)] += 1
                seen = set()
                for field in entry:
                    name_field = local(field.tag)
                    seen.add(name_field)
                    totals["entry_fields"][f"{local(entry.tag)}.{name_field}"] += 1
                    if name_field == "AutoRecord":
                        text = (field.text or "").strip()
                        totals["auto_record"][text if text else "<пустой текст>"] += 1
                    else:
                        text = (field.text or "").strip()
                        totals["field_values"][f"{name_field} = {text[:30] or '<пустой текст>'}"] += 1
                if not seen:
                    totals["entry_without_fields"] += 1
                if len(seen) > 1:
                    totals["entry_field_sets"]["+".join(sorted(seen))] += 1
        print(f"  {name}/{path.parent.name}{path.name}: перечней {len(contents)}, "
              f"записей {sum(1 for c in contents for _ in c)}")


def show(title, counter, limit=12):
    print(f"\n{title}:")
    if not counter:
        print("    (ничего не найдено)")
        return
    for key, count in counter.most_common(limit):
        print(f"    {key:52} {count}")


def main():
    print("=== П1: структура перечня <Content> плана обмена (только чтение) ===")
    totals = {
        "files": 0, "entries": 0, "empty_content": 0, "entry_without_fields": 0,
        "files_where": Counter(),
        "content_in": Counter(), "target_tag": Counter(), "entry_fields": Counter(),
        "auto_record": Counter(), "field_values": Counter(), "entry_field_sets": Counter(),
    }
    for dump in DUMPS:
        print(f"\n--- {dump} ---")
        probe(dump, totals)
    print(f"\nИТОГО: файлов {totals['files']}, записей {totals['entries']}, "
          f"пустых перечней {totals['empty_content']}, записей без полей {totals['entry_without_fields']}")
    show("где лежат перечни (слот Ext/Content.xml или файл вида)", totals["files_where"])
    show("где лежит Content", totals["content_in"])
    show("теги цели", totals["target_tag"])
    show("поля записи", totals["entry_fields"])
    show("значения AutoRecord", totals["auto_record"])
    show("наборы полей записи", totals["entry_field_sets"])
    show("значения прочих полей", totals["field_values"], limit=20)
    return 0


if __name__ == "__main__":
    sys.exit(main())
