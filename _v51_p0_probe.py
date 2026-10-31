#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V51, шаг П0: замеры круга позиции 2.6 «Планы обмена» (ExchangePlans).

Зонд только читает: ничего не пишет ни в БД, ни в файлы выгрузок. Отвечает на вопросы,
без которых модель записи детей выдумывалась бы:

1. круг вида по четырём выгрузкам — файлы регистрации и подкаталоги;
2. теги верхнего уровня файла вида и число детей по перечням (Attributes,
   TabularSections, Forms, Templates, Commands, Content, Help, AdditionalIndexes);
3. есть ли uuid у детей внутри XML (определяет, чем адресовать ребёнка — uuid или именем);
4. как устроены формы и макеты вида (пути, Ext/Form.xml, Ext/Template.xml, двоичные
   содержимые) и сколько весят (цена содержимого для решения о границах узла).

Запуск:  python _v51_p0_probe.py            # все четыре выгрузки
         python _v51_p0_probe.py MinCfg     # одна
"""

import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
VIEW_DIR = "ExchangePlans"

# Перечни детей внутри файла вида: тег-обёртка -> счёт по непосредственным элементам.
CHILD_TAGS = ("Attributes", "TabularSections", "Commands", "Forms", "Templates",
              "AdditionalIndexes", "PredefinedData", "Help", "Content")


def local(tag):
    return tag.split('}')[-1]


def probe_file(path):
    """Словарь свойств узла вида + перечни детей + наличие uuid у детей.

    Корень файла — `MetaDataObject`, внутри него ровно один узел вида (`ExchangePlan`).
    Перечни детей лежат внутри узла вида, а не в корне — первый срез этого не учитывал.
    """
    info = {"view_tag": "", "props": Counter(), "lists": Counter(), "list_items": Counter(),
            "child_uuid": Counter(), "child_names": Counter(), "error": ""}
    try:
        root = ET.parse(str(path)).getroot()
    except Exception as exc:                      # битый XML называется, а не пропускается
        info["error"] = f"{type(exc).__name__}: {exc}"
        return info
    view = None
    for node in root:
        if local(node.tag) not in ("MetaDataObject",):
            view = node
            break
    if view is None:                              # состояние файла называется, а не молчится
        info["error"] = f"узла вида нет, корень: {local(root.tag)}"
        return info
    info["view_tag"] = local(view.tag)
    # Узел вида делится на InternalInfo / Properties / ChildObjects — свойства и перечни
    # детей лежат внутри этих блоков, а не непосредственно в узле вида.
    nodes = []
    for node in view:
        if local(node.tag) in ("Properties", "ChildObjects"):
            nodes.extend(list(node))
        else:
            nodes.append(node)
    for node in nodes:
        name = local(node.tag)
        kids = list(node)
        if not kids and not (node.text or "").strip():
            info["props"][name + ":пусто"] += 1
            continue
        if not kids:
            info["props"][name + ":скаляр"] += 1
            continue
        if name in CHILD_TAGS or local(kids[0].tag) in ("Attribute", "TabularSection", "Form",
                                                        "Template", "Command", "Folder",
                                                        "AdditionalAttribute", "Total"):
            info["lists"][name] += len(kids)
            for kid in kids:
                kid_name, has_uuid = "", False
                for sub in kid:
                    sub_name = local(sub.tag)
                    if sub_name == "Name" and (sub.text or "").strip():
                        kid_name = sub.text.strip()
                    if sub_name in ("UUID", "Uuid", "Id") and (sub.text or "").strip():
                        has_uuid = True
                info["list_items"][f"{name}>{local(kid.tag)}"] += 1
                info["child_uuid"][f"{name}:{'uuid' if has_uuid else 'НЕТ'}"] += 1
                if kid_name:
                    info["child_names"][f"{name}.{kid_name}"] += 1
            continue
        info["props"][name + ":вложенный"] += 1
    return info


def probe_dump(name):
    root = DUMP_ROOT / name
    view = root / VIEW_DIR
    print(f"\n{'=' * 78}\n{name}: каталог {VIEW_DIR} — "
          f"{'есть' if view.is_dir() else 'НЕТ (состояние выгрузки, не отказ)'}")
    if not view.is_dir():
        return
    files = sorted(p for p in view.iterdir() if p.suffix.lower() == ".xml" and p.is_file())
    dirs = sorted(p for p in view.iterdir() if p.is_dir())
    print(f"файлов регистрации: {len(files)}, каталогов содержимого: {len(dirs)}")

    agg_lists = Counter()
    agg_items = Counter()
    agg_uuid = Counter()
    agg_props = Counter()
    prop_state = {}
    view_tags = Counter()
    for f in files:
        info = probe_file(f)
        if info["error"]:
            print(f"  ⚠️ {f.name}: {info['error']}")
            continue
        view_tags[info["view_tag"]] += 1
        agg_lists.update(info["lists"])
        agg_items.update(info["list_items"])
        agg_uuid.update(info["child_uuid"])
        for key, count in info["props"].items():
            tag, _, state = key.partition(":")
            agg_props[tag] += count
            prop_state.setdefault(tag, Counter())[state] += count
    print(f"узел вида: {dict(view_tags)}")
    print(f"словарь свойств узла вида — {len(agg_props)} имён тегов:")
    for tag, count in sorted(agg_props.items(), key=lambda kv: -kv[1])[:40]:
        states = ", ".join(f"{s}×{c}" for s, c in sorted(prop_state[tag].items()))
        print(f"    {tag:34} в {count:3} файлах ({states})")
    print("перечни детей внутри узла вида (суммарно по выгрузке):")
    for tag, count in sorted(agg_lists.items(), key=lambda kv: -kv[1]):
        print(f"    {tag:20} {count:5}  (элементы: {', '.join(f'{k}×{v}' for k, v in sorted(agg_items.items()))})"
              if tag == sorted(agg_lists.items(), key=lambda kv: -kv[1])[0][0]
              else f"    {tag:20} {count:5}")
    print("есть ли uuid у детей внутри XML:")
    for key, count in sorted(agg_uuid.items()):
        print(f"    {key:34} {count}")

    # Подкаталоги содержимого: Forms/Templates/Ext — пути и вес.
    kinds = Counter()
    sizes = Counter()
    samples = []
    for d in dirs:
        for sub in d.rglob("*"):
            rel = str(sub.relative_to(view))
            if sub.is_dir():
                kinds["каталог " + rel.split("\\")[0] if False else "каталог/" + (rel.split("\\")[1] if "\\" in rel else rel)] += 1
                continue
            head = rel.split("\\")[1] if "\\" in rel else rel.split(".")[0]
            kinds[head] += 1
            sizes[head] += sub.stat().st_size
            if len(samples) < 12 and ("Forms" in rel or "Templates" in rel or "Ext" in rel):
                samples.append(f"{rel} ({sub.stat().st_size} б)")
    print("содержимое подкаталогов вида (по типу):")
    for key, count in sorted(kinds.items(), key=lambda kv: -kv[1])[:12]:
        print(f"    {key:24} {count:5} шт, {sizes.get(key, 0):>12,} байт")
    print("примеры путей:")
    for s in samples:
        print("    ", s)


def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== П0 замеры круга ExchangePlans (только чтение) ===")
    for name in wanted:
        if name not in DUMPS:
            print(f"выгрузка не из списка замеров: {name}")
            continue
        probe_dump(name)
    print("\nисточник норматива позиции: C:\\1C_LLM\\Структура конфигурации.txt, 2.6 Планы обмена")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
