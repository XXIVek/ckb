#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V52, шаг П0: замеры содержимого свойств вида `FilterCriterion` — блоков `Type`
и `Content` («условия отбора» = состав вида), а также ссылок на формы.

Зонд только читает. Отвечает на вопросы, без которых нельзя решить модель записи:

1. блок `Type` — тот же ли это `v8:TypeDescription`, что у параметров сеанса (V48) и общих
   реквизитов (V50): переиспользуемые закрытые словари или нужен свой разбор;
2. блок `Content` — из чего состоит условие отбора: теги элемента, их число, есть ли у
   элемента uuid (чем адресовать), на что он ссылается (`Metadata`/`Field`/…);
3. `DefaultForm`/`AuxiliaryForm` — ссылкой какого вида заданы (имя формы вида или внешний
   объект), то есть чем разрешать цель;
4. вес и форма значений свойств, не вошедших в первый срез (маскирование длинных текстов).

Запуск:  python _v52_p0_content_probe.py            # все четыре выгрузки
         python _v52_p0_content_probe.py BP3        # одна
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
BLOCKS = ("Type", "Content")
MAX_SAMPLES = 3
MAX_VALUE = 70


def local(tag):
    return tag.split('}')[-1]


def mask(text):
    value = " ".join((text or "").split())
    if len(value) > MAX_VALUE:
        return value[:MAX_VALUE] + "…"
    return value


def walk_block(node, path, tags, samples, depth=0):
    """Дерево тегов блока: путь -> число встреч + примеры значений (маскированные)."""
    for kid in node:
        name = local(kid.tag)
        key = f"{path}.{name}"
        tags[key] += 1
        text = mask(kid.text)
        if text and len(samples.setdefault(key, [])) < MAX_SAMPLES:
            samples[key].append(text)
        attrs = {k.split('}')[-1]: v for k, v in kid.attrib.items()}
        if attrs and len(samples.setdefault(key + "@attr", [])) < MAX_SAMPLES:
            samples[key + "@attr"].append(", ".join(f"{k}={v}" for k, v in attrs.items()))
        if depth < 5:
            walk_block(kid, key, tags, samples, depth + 1)


def probe_file(path, agg):
    root = ET.parse(str(path)).getroot()
    view = None
    for node in root:
        if local(node.tag) != "MetaDataObject":
            view = node
            break
    if view is None:
        return
    props = None
    children = Counter()
    for node in view:
        if local(node.tag) == "Properties":
            props = node
        elif local(node.tag) == "ChildObjects":
            for child in node:
                children[local(child.tag)] += 1
    if props is None:
        return
    for prop in props:
        name = local(prop.tag)
        if name in BLOCKS:
            walk_block(prop, name, agg[f"{name}.tags"], agg[f"{name}.samples"])
        elif name in ("DefaultForm", "AuxiliaryForm"):
            key = f"ссылка {name}"
            text = mask(prop.text)
            agg[key + ".tags"][name] += 1
            if text and len(agg[key + ".samples"].setdefault(name, [])) < MAX_SAMPLES:
                agg[key + ".samples"][name].append(text)
    if children:
        agg["дети ChildObjects.tags"][";".join(f"{k}×{v}" for k, v in sorted(children.items()))] += 1


def probe_dump(name):
    view = DUMP_ROOT / name / VIEW_DIR
    print(f"\n{'=' * 78}\n{name}: каталог {VIEW_DIR} — "
          f"{'есть' if view.is_dir() else 'НЕТ (состояние выгрузки, не отказ)'}")
    if not view.is_dir():
        return
    files = sorted(p for p in view.iterdir() if p.suffix.lower() == ".xml" and p.is_file())
    print(f"файлов регистрации: {len(files)}")
    agg = {}
    for key in ("Type.tags", "Type.samples", "Content.tags", "Content.samples",
                "ссылка DefaultForm.tags", "ссылка DefaultForm.samples",
                "ссылка AuxiliaryForm.tags", "ссылка AuxiliaryForm.samples",
                "дети ChildObjects.tags", "дети ChildObjects.samples"):
        agg[key] = Counter() if key.endswith(".tags") else {}
    for f in files:
        try:
            probe_file(f, agg)
        except Exception as exc:
            print(f"  ⚠️ {f.name}: {type(exc).__name__}: {exc}")
    for block in ("Type", "Content", "ссылка DefaultForm", "ссылка AuxiliaryForm",
                  "дети ChildObjects"):
        tags = agg[f"{block}.tags"]
        samples = agg[f"{block}.samples"]
        print(f"блок {block}: {'пуст' if not tags else str(len(tags)) + ' путей тегов'}")
        for key, count in sorted(tags.items(), key=lambda kv: -kv[1])[:45]:
            print(f"    {key:52} {count:5}")
            for sample in samples.get(key, []):
                print(f"        пример: {sample}")


def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== П0 замеры блоков Type/Content файла FilterCriteria (только чтение) ===")
    for name in wanted:
        if name not in DUMPS:
            print(f"выгрузка не из списка замеров: {name}")
            continue
        probe_dump(name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
