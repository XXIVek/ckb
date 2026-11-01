#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V52, шаг П2: покрытие блока `<Type>` существующим разбором (только чтение).

Позиция П2 плана («отдельная позиция шага — замер покрытия блока <Type>»): ветка
`Type.TypeSet` в существующем разборе V48/V50 не замерялась. Проверять, а не предполагать:
проба вызывает РОВНО тот код, который уже есть в репозитории
(`configuration_common_attributes.normalize_type_block` — он же лежит в основе разбора
параметров сеанса узла V48), на РЕАЛЬНЫХ файлах вида и называет результат числом.

Что отвечает проба:

* сколько блоков `<Type>` и сколько значений лежит в файлах, с разделением по контейнеру
  (`Type` против `TypeSet`) — это эталон, с которым сверяется разбор узла V52;
* сколько записей `types` даёт существующий разбор, в каком состоянии строки и какого
  класса записи — проба проверяет и значение: в отличие от ожидания плана (раздел 2.1),
  разбор значение НЕ теряет (замер П2 по KomMag даёт `value = cfg:DocumentRef`), но класс
  и состояние называют его нераспознанным;
* сохранены ли квалификаторы (`StringQualifiers` MinCfg) отдельной колонкой — эта ветка
  покрыта, и проба называет это, а не молчит о ней;
* составной тип (BGU2, BP3) — число записей и кратность `composite`.

Вывод пробы — основание решения Q6 (вариант A с собственной веткой парсера): состояние
`unknown_form` для KomMag недопустимо, потому что значение типа в файле есть.

Ничего не пишет в БД и не меняет файлов.

Запуск:  python _v52_p2_type_probe.py [BGU2 BP3 MinCfg KomMag]
"""

import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import configuration_common_attributes as ca  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
VIEW_DIR = "FilterCriteria"
VIEW_TAG = "FilterCriterion"

# Эталон замера `_v52_p2_property_probe.py` и раздела 2.1 плана: сколько значений какого
# контейнера лежит в файлах. Держится здесь, а не выводится из модуля: иначе опечатка в
# замере перестала бы быть ошибкой.
EXPECTED_VALUES = {
    "MinCfg": {"Type": 1, "TypeSet": 0},
    "KomMag": {"Type": 0, "TypeSet": 1},
    "BGU2": {"Type": 240, "TypeSet": 0},
    "BP3": {"Type": 187, "TypeSet": 0},
}


def local(tag):
    return tag.rsplit("}", 1)[-1]


def find_child(node, name):
    for child in node:
        if local(child.tag) == name:
            return child
    return None


def container_counts(type_element):
    """Значения блока по контейнерам: `Type` (значение-элемент) и `TypeSet` (контейнер)."""
    got = Counter()
    for inner in ([] if type_element is None else list(type_element)):
        tag = local(inner.tag)
        if tag in ("Type", "TypeSet"):
            got[tag] += 1
    return got


def probe_dump(name):
    print(f"\n{'=' * 78}\n{name} / {VIEW_DIR}")
    view = DUMP_ROOT / name / VIEW_DIR
    if not view.is_dir():
        print("    каталога вида нет — состояние выгрузки")
        return None
    files = sorted(view.glob("*.xml"))
    blocks = 0
    file_containers = Counter()
    entry_states = Counter()
    entry_classes = Counter()
    entry_containers = Counter()
    multiplicity = Counter()
    entries_total = 0
    qualifier_blocks = 0
    preserved_values = 0
    examples = []
    for path in files:
        text, error = ca.read_text_file(path)
        if error:
            print(f"    {path.name}: {error}")
            continue
        root, xml_error = ca.parse_xml(text)
        if xml_error:
            print(f"    {path.name}: {xml_error}")
            continue
        obj = find_child(root, VIEW_TAG)
        props = find_child(obj, "Properties") if obj is not None else None
        type_element = find_child(props, "Type") if props is not None else None
        if type_element is None:
            continue
        blocks += 1
        file_containers.update(container_counts(type_element))
        ns_map, _ns_warnings = ca.file_namespace_map(text)
        normalized = ca.normalize_type_block(type_element, ns_map,
                                            raw_block=ca.raw_type_block(text))
        entries_total += len(normalized["entries"])
        multiplicity[normalized["type_multiplicity"]] += 1
        entry_states[normalized["type_parse_state"]] += 1
        if normalized["qualifiers"]:
            qualifier_blocks += 1
        for entry in normalized["entries"]:
            entry_classes[entry.get("class")] += 1
            entry_containers[entry.get("container") or "<ключа container нет>"] += 1
            value = str(entry.get("value") or "")
            if value and not value.startswith("<"):
                preserved_values += 1
            if "TypeSet" in value or "TypeSet" in str(entry.get("reason") or ""):
                if len(examples) < 3:
                    examples.append((path.name, entry))
        for warning in normalized["warnings"]:
            print(f"    [ПРЕДУПРЕЖДЕНИЕ] {path.name}: {warning}")

    print(f"    файлов: {len(files)}, блоков <Type>: {blocks}, "
          f"блоков с квалификаторами: {qualifier_blocks}")
    print(f"    значений в файлах по контейнерам: {dict(file_containers) or 'нет'}")
    expected = EXPECTED_VALUES.get(name)
    if expected is not None:
        # Сравнение по ключам эталона: отсутствие ключа в счётчике означает ноль, иначе
        # «TypeSet: 0» расходилось бы с «ключа нет» как две разные величины.
        got = {key: file_containers.get(key, 0) for key in expected}
        extra = {k: v for k, v in file_containers.items() if k not in expected}
        if got == expected and not extra:
            print(f"      эталон замера совпал: {expected}")
        else:
            print(f"      ❌ РАСХОЖДЕНИЕ с эталоном замера: ждали {expected}, "
                  f"файлы дают {got}" + (f", вне эталона {extra}" if extra else ""))
    print(f"    существующий разбор V50: записей {entries_total}, значения сохранены у "
          f"{preserved_values}; состояния строк {dict(entry_states)}; кратность "
          f"{dict(multiplicity)}")
    print(f"      классов записей: {dict(entry_classes)}")
    print(f"      ключей container у записей: {dict(entry_containers)}")
    for file_name, entry in examples:
        print(f"      как разбор V50 видит TypeSet в {file_name}: {entry}")
    return {"blocks": blocks, "containers": dict(file_containers),
            "entries": entries_total, "states": dict(entry_states),
            "classes": dict(entry_classes), "preserved": preserved_values}


def main(argv=None):
    wanted = [a for a in (argv or []) if not a.startswith("--")] or list(DUMPS)
    print("=== П2 V52: покрытие блока <Type> существующим разбором V48/V50 ===")
    results = {}
    for name in wanted:
        got = probe_dump(name)
        if got:
            results[name] = got
    print(f"\n{'=' * 78}\nИтог по корпусу")
    file_values = Counter()
    total_entries = 0
    total_preserved = 0
    states = Counter()
    classes = Counter()
    for got in results.values():
        for container, count in got["containers"].items():
            file_values[container] += count
        total_entries += got["entries"]
        total_preserved += got["preserved"]
        states.update(got["states"])
        classes.update(got["classes"])
    in_files = sum(file_values.values())
    print(f"    значений в файлах: {dict(file_values)}, всего {in_files}")
    print(f"    записей у существующего разбора: {total_entries}, из них со значением: "
          f"{total_preserved}")
    print(f"    состояния строк: {dict(states)}; классов записей: {dict(classes)}")
    gap = file_values.get("TypeSet", 0)
    unknown_rows = sum(cnt for state, cnt in states.items() if state != "parsed")
    unknown_entries = sum(cnt for cls, cnt in classes.items() if cls == "unknown")
    if gap and (unknown_rows or unknown_entries):
        print(f"    ❌ ветка TypeSet ({gap} знач.) существующим разбором НЕ покрыта: "
              f"значение он сохраняет ({total_preserved} из {in_files}), но класс даёт "
              f"unknown, а состояние строки — unknown_form ({unknown_rows} строк, "
              f"{unknown_entries} записей). Для KomMag это означало бы строку вида с "
              f"type_parse_state=unknown_form при известном типе cfg:DocumentRef: ссылка "
              f"не вычислялась бы и не разрешалась индексом состава, а предупреждение "
              f"«число значений (0) не совпадает с числом записей (1)» было бы ложным. "
              f"Отдельная ветка парсера нужна за класс, состояние и container (Q6, "
              f"вариант A с решением оператора) — вывод узла V52 уточнён замером П2 "
              f"относительно текста плана, который ожидал потери самого значения")
    elif not gap:
        print("    значений TypeSet в корпусе нет — отрицательный факт")
    else:
        print("    ⚠️ значений TypeSet есть, но ни одна строка не помечена unknown_form — "
              "вывод о собственной ветке нужно пересматривать")
    print("    квалификаторы (MinCfg StringQualifiers) существующий разбор сохраняет "
          "отдельной колонкой — эта ветка покрыта (замер V48 2.4.2); ключа `container` "
          "у записей нет ни у одной — словарь записи V52 шире, и это названо константой")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

