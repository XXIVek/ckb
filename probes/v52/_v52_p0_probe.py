#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V52, шаг П0: замеры круга позиции 2.7 «Критерии отбора» (FilterCriteria).

Зонд только читает: ничего не пишет ни в БД, ни в файлы выгрузок. Отвечает на вопросы,
без которых модель записи вида выдумывалась бы:

1. круг вида по четырём выгрузкам — файлы регистрации и подкаталоги содержимого;
2. словарь свойств узла вида (теги `Properties`) и ФОРМА каждого значения — пустое,
   скаляр, bool, мультыязык, блок, `xsi:nil` (форма задаёт вид разбора, а не имя тега);
3. перечни детей внутри `ChildObjects` по тегам, есть ли у детей uuid (чем адресовать
   ребёнка — uuid или именем), и точечные имена детей;
4. блок `ConditionItems` — «состав» вида (аналог `Content` у планов обмена): число
   элементов и словарь их внутренних тегов;
5. содержимое подкаталогов (пути и вес) — цена вторичного содержимого для решения о
   границах узла.

Отличия от зонда V51 названы в коде там, где круг ведёт себя иначе (у вида нет
реквизитов и табличных частей — это проверяется, а не предполагается).

Запуск:  python _v52_p0_probe.py            # все четыре выгрузки
         python _v52_p0_probe.py MinCfg     # одна
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
VIEW_DIR = "FilterCriteria"

# Теги, которые в файле вида являются перечнями детей (обёртки). Для плана обмена их
# задал замер V51; здесь перечень открыт — зонд обязан назвать то, что есть, а не искать
# заготовленное. Пустой ответ по группе «Attributes» — тоже знание (у вида реквизитов нет).
LIST_TAGS = ("Attributes", "TabularSections", "Commands", "Forms", "Templates", "Folders",
             "AdditionalAttributes", "Totals", "PredefinedData", "ConditionItems",
             "Content", "Help", "AdditionalIndexes")


def local(tag):
    return tag.split('}')[-1]


def shape_of(node):
    """Форма значения свойства: пустое / xsi:nil / скаляр / bool / мультыязык / блок."""
    if node.get("{http://www.w3.org/2001/XMLSchema-instance}nil"):
        return "xsi_nil"
    kids = [local(k.tag) for k in node]
    if not kids:
        text = (node.text or "").strip()
        if not text:
            return "empty"
        if text in ("true", "false", "1", "0"):
            return "bool"
        return "scalar"
    if set(kids) <= {"item"}:
        return "multilang"
    return "block"


def walk_names(node, prefix, names, depth=0):
    """Точечные имена элементов перечней (имя ребёнка в индексе состава — точечное)."""
    for kid in node:
        name = local(kid.tag)
        value = (kid.text or "").strip()
        if value and len(value) < 80:
            names[f"{prefix}.{name}.{value}"] += 1
        else:
            names[f"{prefix}.{name}"] += 1
        if depth < 2:
            walk_names(kid, f"{prefix}.{name}", names, depth + 1)


def probe_file(path):
    """Словарь свойств узла вида + перечни детей + форма значений + блок ConditionItems.

    Корень файла — `MetaDataObject`, внутри него ровно один узел вида (`FilterCriterion`).
    Свойства лежат в блоке `Properties`, дети — непосредственными элементами `ChildObjects`
    (обёрток-перечней у детей нет — тот же порядок, что у плана обмена, замер V51).
    """
    info = {"view_tag": "", "view_uuid": "", "props": Counter(), "shapes": Counter(),
            "lists": Counter(), "child_uuid": Counter(), "names": Counter(),
            "cond_items": 0, "cond_tags": Counter(), "error": ""}
    try:
        root = ET.parse(str(path)).getroot()
    except Exception as exc:                      # битый XML называется, а не пропускается
        info["error"] = f"{type(exc).__name__}: {exc}"
        return info
    view = None
    for node in root:
        if local(node.tag) != "MetaDataObject":
            view = node
            break
    if view is None:                              # состояние файла называется, а не молчится
        info["error"] = f"узла вида нет, корень: {local(root.tag)}"
        return info
    info["view_tag"] = local(view.tag)
    info["view_uuid"] = view.get("uuid", "")
    for block in view:
        tag = local(block.tag)
        if tag == "Properties":
            for prop in block:
                name = local(prop.tag)
                info["props"][name] += 1
                info["shapes"][f"{name}={shape_of(prop)}"] += 1
                if name == "ConditionItems":
                    for item in prop:
                        info["cond_items"] += 1
                        for inner in item:
                            info["cond_tags"][f"{local(item.tag)}.{local(inner.tag)}"] += 1
        elif tag == "ChildObjects":
            for child in block:
                name = local(child.tag)
                info["lists"][name] += 1
                if child.get("uuid"):
                    info["child_uuid"][f"{name}:uuid"] += 1
                else:
                    info["child_uuid"][f"{name}:без_uuid"] += 1
                walk_names(child, name, info["names"])
        elif tag == "InternalInfo":
            continue
        else:
            # верхний уровень узла вида, кроме Properties/ChildObjects: называется отдельным
            # ключом, чтобы не смешивать со свойствами (ошибка первой пробы V51)
            info["props"][f"#{tag}"] += 1
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

    agg_props = Counter()
    shapes = {}
    agg_lists = Counter()
    agg_uuid = Counter()
    agg_cond = Counter()
    agg_names = Counter()
    view_tags = Counter()
    sets = Counter()
    for f in files:
        info = probe_file(f)
        if info["error"]:
            print(f"  ⚠️ {f.name}: {info['error']}")
            continue
        view_tags[info["view_tag"]] += 1
        sets[tuple(sorted(info["props"]))] += 1
        agg_props.update(info["props"])
        for key, count in info["shapes"].items():
            tag, _, form = key.partition("=")
            shapes.setdefault(tag, Counter())[form] += count
        agg_lists.update(info["lists"])
        agg_uuid.update(info["child_uuid"])
        agg_names.update(info["names"])
        if info["cond_items"]:
            agg_cond["элементов ConditionItems"] += info["cond_items"]
            for tag, count in info["cond_tags"].items():
                agg_cond[f"тег {tag}"] += count
    print(f"узел вида: {dict(view_tags)}")
    print(f"словарь свойств узла вида — {len(agg_props)} имён тегов; различных наборов "
          f"по файлам: {len(sets)} ({', '.join(str(c) for c in sets.values())})")
    for tag, count in sorted(agg_props.items(), key=lambda kv: -kv[1]):
        forms = ", ".join(f"{s}×{c}" for s, c in sorted(shapes.get(tag, {}).items()))
        print(f"    {tag:34} в {count:3} файлах ({forms})")
    print("перечни детей непосредственно в ChildObjects (по тегу элемента):")
    for tag, count in sorted(agg_lists.items(), key=lambda kv: -kv[1]):
        print(f"    {tag:22} {count:5}")
    print("есть ли uuid у детей внутри XML:")
    for key, count in sorted(agg_uuid.items()):
        print(f"    {key:26} {count}")
    print("блок ConditionItems (состав вида):")
    for key, count in sorted(agg_cond.items(), key=lambda kv: -kv[1]):
        print(f"    {key:46} {count}")
    print("точечные имена детей (первые 12):")
    for key, count in sorted(agg_names.items())[:12]:
        print(f"    {key:70} {count}")

    kinds = Counter()
    sizes = Counter()
    samples = []
    for d in dirs:
        for sub in d.rglob("*"):
            rel = str(sub.relative_to(view))
            if sub.is_dir():
                continue
            head = rel.split("\\")[1] if "\\" in rel else rel.split(".")[0]
            kinds[head] += 1
            sizes[head] += sub.stat().st_size
            if len(samples) < 12:
                samples.append(f"{rel} ({sub.stat().st_size} б)")
    print("содержимое подкаталогов вида (по типу верхнего уровня):")
    for key, count in sorted(kinds.items(), key=lambda kv: -kv[1])[:12]:
        print(f"    {key:24} {count:5} шт, {sizes.get(key, 0):>12,} байт")
    print("примеры путей:")
    for s in samples:
        print("    ", s)


def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== П0 замеры круга FilterCriteria (только чтение) ===")
    for name in wanted:
        if name not in DUMPS:
            print(f"выгрузка не из списка замеров: {name}")
            continue
        probe_dump(name)
    print("\nисточник норматива позиции: C:\\1C_LLM\\Структура конфигурации.txt, "
          "2.7 Критерии отбора")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

