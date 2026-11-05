#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""УЗЕЛ V58, шаг П0 (проверка числа): формы значений блока `<Type>` — два счёта.

Зачем: главный замер узла — закрытый словарь ФОРМ значения типа. Он обязан быть назван
числами, которые совпадают с числом значений круга; расхождение в две записи уже является
ответом, а не погрешностью. Поэтому считаются двумя независимыми путями:
  1) обходом дерева (ElementTree, только прямые дети блока `Properties/Type`) — так же, как
     считает `_v58_p0_probe.py`;
  2) подстрокой по тексту файла (как это делает проб формы значений) — путь, который может
     посчитать лишний элемент, если форма записана вне блока.
Если счётцы расходятся, называется выгрузка, файл и само значение.

Границы: имена целей нормализуются (`<Вид>Ref.*`) — это словарь форм, а не перечень целей;
значений с точкой внутри имени цели такой срез назовёт отдельно (`odd_shapes`).
"""

import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
V8 = "{http://v8.1c.ru/8.1/data/core}"
FORM_RE = re.compile(r"^(?:[A-Za-z0-9]+:)?([A-Za-z0-9]+)\.([^.<]+)$")
SUFFIXES = ("Ref", "Object", "RecordSet", "ValueManager")


def shape_of(value):
    """Форма значения: `префикс:<Вид><Суффикс>.*` либо `xs:<тип>`; иначе — `odd`."""
    text = value.strip()
    if text.startswith("xs:"):
        return "xs:" + text[3:]
    m = FORM_RE.match(text)
    if not m:
        return "odd:" + text
    kind, name = m.group(1), m.group(2)
    for suf in SUFFIXES:
        if kind.endswith(suf):
            return f"{text.split(':', 1)[0]}:{kind[:-len(suf)]}.{suf}.*"
    return f"odd-kind:{kind}"


def localname(tag):
    """Локальное имя без префикса пространства имён (тот же приём, что `local()` в зонде)."""
    return tag.rpartition("}")[2]


def walk_values(path):
    """Значения блока `Properties/Type` обходом дерева (прямые дети `<v8:Type>`)."""
    try:
        root = ET.parse(str(path)).getroot()
    except Exception:  # noqa: BLE001
        return []
    out = []
    for props in root.iter():
        if localname(props.tag) != "Properties":
            continue
        for block in props:
            if localname(block.tag) != "Type":
                continue
            for node in block:
                if localname(node.tag) == "Type":
                    out.append((node.text or "").strip())
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    walk_total = text_total = 0
    shapes = Counter()
    diffs = []
    for dump in DUMPS:
        directory = DUMP_ROOT / dump / "DefinedTypes"
        for path in sorted(directory.glob("*.xml")):
            values = walk_values(path)
            walk_total += len(values)
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            found = re.findall(r"<v8:Type>([^<]*)</v8:Type>", text)
            text_total += len(found)
            if len(found) != len(values):
                diffs.append((dump, path.name, len(values), len(found),
                              sorted(set(found) ^ {v for v in values})[:3]))
            for v in values:
                shapes[shape_of(v)] += 1
    print(f"значений обходом дерева: {walk_total}; подстрокой по тексту: {text_total}; "
          f"расхождений файлов: {len(diffs)}")
    for row in diffs[:10]:
        print("   РАСХОЖДЕНИЕ:", row)
    print(f"форм значений (словарь замкнут корпусом): {len(shapes)}")
    for shape, count in shapes.most_common():
        print(f"   {count:>6} {shape}")
    by_class = Counter()
    for shape, count in shapes.items():
        if shape.startswith("xs:"):
            by_class["primitive"] += count
        elif shape.endswith(".Ref.*"):
            by_class["ref_value"] += count
        elif shape.endswith(".Object.*"):
            by_class["object_value"] += count
        elif shape.endswith(".RecordSet.*"):
            by_class["record_set"] += count
        elif shape.endswith(".ValueManager.*"):
            by_class["value_manager"] += count
        else:
            by_class["not_in_dictionary"] += count
    print(f"по классам: {dict(by_class)}; сумма {sum(by_class.values())}")


if __name__ == "__main__":
    main()
