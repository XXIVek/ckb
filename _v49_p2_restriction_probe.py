# -*- coding: utf-8 -*-
"""П2 узла V49: словарь детей `<restrictionByCondition>` — чего не снимал П0.

П0 (`_v49_p0_element_probe.py`) перечислил детей `<right>` и остановился на них:
`<restrictionByCondition>` попал в словарь как ЭЛЕМЕНТ права, а его собственные дети не
измерялись. Разбор П2 нашёл в KomMag `<restrictionByCondition><field>Товары</field>
<condition/></restrictionByCondition>` — то есть (а) у элемента ограничения бывает `<field>`
(поле объекта, к которому относится право), (б) `<condition/>` бывает пустым.

Числа этого прогона и есть базовая линия по условию права; прежняя строка плана «других
элементов у restrictionByCondition нет» замером не подтверждена и заменяется измеренным.
"""
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
DIR_NAME = "Roles"
NS_ROLE = "{http://v8.1c.ru/8.2/roles}"


def local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def main() -> int:
    if len(sys.argv) > 1:
        dumps = tuple(d for d in DUMPS if d in set(sys.argv[1:]))
    else:
        dumps = DUMPS
    merged_restriction_children = Counter()
    merged_restriction_of = Counter()
    merged_condition_forms = Counter()
    merged = Counter()
    field_samples = []
    for dump in dumps:
        directory = DUMP_ROOT / dump / DIR_NAME
        got_restriction_children = Counter()
        got_restriction_of = Counter()
        got_condition_forms = Counter()
        got = Counter()
        for path in sorted(directory.rglob("Rights.xml")):
            root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
            for object_el in root.iter(NS_ROLE + "object"):
                target_el = object_el.find(NS_ROLE + "name")
                target = (target_el.text or "").strip() if target_el is not None else ""
                for right_el in object_el.findall(NS_ROLE + "right"):
                    got["rights"] += 1
                    right_name_el = right_el.find(NS_ROLE + "name")
                    right_name = ((right_name_el.text or "").strip()
                                  if right_name_el is not None else "")
                    for restriction_el in right_el.findall(
                            NS_ROLE + "restrictionByCondition"):
                        got["restriction_elements"] += 1
                        got_restriction_children.update(
                            local_name(child.tag) for child in restriction_el)
                        got_restriction_of[local_name(restriction_el.tag)] += 1
                        field_el = restriction_el.find(NS_ROLE + "field")
                        if field_el is not None:
                            field_samples.append(
                                (dump, path.relative_to(DUMP_ROOT).as_posix(), target,
                                 right_name, (field_el.text or "").strip(),
                                 ET.tostring(restriction_el, encoding="unicode")))
                        condition_el = restriction_el.find(NS_ROLE + "condition")
                        if condition_el is None:
                            got_condition_forms["нет condition"] += 1
                            continue
                        text = (condition_el.text or "").strip()
                        got_condition_forms["пустой condition" if not text else "непустой"] += 1
                        if text:
                            got["condition_texts"] += 1
        merged_restriction_children.update(got_restriction_children)
        merged_restriction_of.update(got_restriction_of)
        merged_condition_forms.update(got_condition_forms)
        merged.update(got)
        print(f"=== {dump} ===")
        print(f"  прав {got['rights']}, элементов ограничения {got['restriction_elements']}, "
              f"непустых условий {got['condition_texts']}")
        print(f"  дети restrictionByCondition: {dict(got_restriction_children.most_common())}")
        print(f"  формы condition: {dict(got_condition_forms.most_common())}")
    print("=== ИТОГ ===")
    print(f"прав {merged['rights']}, элементов ограничения "
          f"{merged['restriction_elements']}, непустых условий {merged['condition_texts']}")
    print(f"дети restrictionByCondition: {dict(merged_restriction_children.most_common())}")
    print(f"формы condition: {dict(merged_condition_forms.most_common())}")
    print("=== СЛУЧАИ <field> ВНУТРИ ОГРАНИЧЕНИЯ ===")
    for dump, rel, target, right_name, field, raw in field_samples:
        print(f"{dump} {rel}\n  цель {target} право {right_name} field {field!r}")
        print("  " + " ".join(raw.split())[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
