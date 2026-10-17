#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Замер структуры `ConfigDumpInfo.xml` перед проектированием `configuration_objects` (узел V33).

Вопросы, которые нельзя решить «по аналогии»:

  1. какие элементы и атрибуты есть в файле;
  2. иерархия: вложенность `<Metadata>` внутри `<Metadata>` или плоский список;
  3. как устроено `name`: сколько сегментов через точку у записей разной глубины,
     совпадает ли XML-родитель с отсечённым хвостом имени (можно ли восстанавливать
     родителя обрезкой, или нужен именно XML-родитель);
  4. формат `id`: канонический v4, составной `<uuid>.<число>`, прочее;
  5. уникальны ли `name` и `id` в пределах файла;
  6. что в `configVersion`: длина, алфавит, доля записей без него;
  7. есть ли у `ConfigVersions` собственные атрибуты.

Скрипт только читает файл и печатает итоги; в БД не пишет.
"""
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

DEFAULT = r"C:\1C_LLM\LoadDoc\BGU2\ConfigDumpInfo.xml"
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
COMPOSITE_RE = re.compile(r"^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\.\d+$")


def local(tag):
    return tag.split('}', 1)[1] if '}' in tag else tag


def main(path):
    root = ET.parse(path).getroot()
    print(f"root={local(root.tag)} attrs={dict(root.attrib)}")

    tags = Counter()
    attrs = {}
    names, ids = [], []
    parents = {}
    depths = Counter()
    seg_counts = Counter()
    id_forms = Counter()
    id_len = Counter()
    cv_len = Counter()
    cv_alphabet = Counter()
    cv_missing = 0
    kinds_by_depth = {}

    def walk(element, depth, parent_name):
        nonlocal cv_missing
        for child in element:
            tag = local(child.tag)
            tags[tag] += 1
            for attr in child.attrib:
                attrs.setdefault(tag, Counter())[local(attr)] += 1
            if tag == "Metadata":
                name = child.attrib.get("name", "")
                ident = child.attrib.get("id", "")
                version = child.attrib.get("configVersion")
                names.append(name)
                ids.append(ident)
                parents[name] = parent_name
                depths[depth] += 1
                parts = name.split(".")
                seg_counts[len(parts)] += 1
                if UUID_RE.match(ident):
                    id_forms["uuid_v4"] += 1
                elif COMPOSITE_RE.match(ident):
                    id_forms["composite_uuid_num"] += 1
                elif not ident:
                    id_forms["empty"] += 1
                else:
                    id_forms["other"] += 1
                id_len[len(ident)] += 1
                if version:
                    cv_len[len(version)] += 1
                    cv_alphabet["hex_lower" if re.match(r"^[0-9a-f]+$", version) else "other"] += 1
                else:
                    cv_missing += 1
                kinds_by_depth.setdefault(depth, Counter())[len(parts)] += 1
                walk(child, depth + 1, name)
            else:
                walk(child, depth, parent_name)

    walk(root, 0, None)

    print(f"\ntags={dict(tags)}")
    for tag, counter in sorted(attrs.items()):
        print(f"attrs[{tag}]={dict(counter)}")
    print(f"\nMetadata_total={len(names)}")
    print(f"depths={dict(sorted(depths.items()))} max_depth={max(depths) if depths else 0}")
    print(f"segments_of_name={dict(sorted(seg_counts.items()))}")
    print(f"id_forms={dict(id_forms)} id_len={dict(sorted(id_len.items()))}")
    print(f"configVersion_len={dict(sorted(cv_len.items()))} missing={cv_missing} "
          f"alphabet={dict(cv_alphabet)}")

    dup_names = [n for n, c in Counter(names).items() if c > 1]
    dup_ids = [i for i, c in Counter(ids).items() if c > 1]
    print(f"\nduplicate_names={len(dup_names)} example={dup_names[:3]}")
    print(f"duplicate_ids={len(dup_ids)} example={dup_ids[:3]}")

    mismatch, examples = 0, []
    for name, parent in parents.items():
        if parent is None:
            continue
        cut = name.rsplit(".", 1)[0]
        if cut != parent:
            mismatch += 1
            if len(examples) < 5:
                examples.append((name, parent, cut))
    print(f"parent_vs_name_prefix_mismatch={mismatch}")
    for name, parent, cut in examples:
        print(f"  name={name}\n    xml_parent={parent}\n    name_prefix={cut}")

    for depth, counter in sorted(kinds_by_depth.items()):
        print(f"depth={depth} segment_counts={dict(sorted(counter.items()))}")

    seen = set()
    print("\nsamples:")
    for name in names:
        dots = name.count(".")
        if dots in seen:
            continue
        seen.add(dots)
        print(f"  dots={dots} parent={parents[name]!r}\n    name={name}")
        if len(seen) >= 6:
            break

    top = Counter(n.split(".")[0] for n, p in parents.items() if p is None)
    print(f"\ntop_level_kinds={len(top)}")
    for kind, count in top.most_common():
        print(f"  {kind}: {count}")

    child_kind = Counter()
    for name, parent in parents.items():
        if parent is None:
            continue
        parts = name.split(".")
        if len(parts) >= 4:
            child_kind[parts[-2]] += 1
    print(f"\nchild_kind_penultimate={len(child_kind)}")
    for kind, count in child_kind.most_common(25):
        print(f"  {kind}: {count}")


def parent_rules(names):
    """Проверить, каким правилом из имени восстанавливается существующая запись-родитель.

    Гипотезы:
      P1 - отсечь последний сегмент (`A.B.Form.C` -> `A.B.Form`);
      P2 - отсечь последние два сегмента, то есть пару `вид.имя`
           (`A.B.Attribute.C` -> `A.B`).
    Правильным считается то, чей результат существует в множестве имён индекса.
    """
    known = set(names)
    stats = Counter()
    examples = {}
    for name in names:
        parts = name.split(".")
        cut1 = ".".join(parts[:-1])
        cut2 = ".".join(parts[:-2]) if len(parts) >= 3 else ""
        hit1, hit2 = cut1 in known, cut2 in known
        if len(parts) <= 2:
            stats["top_level(no parent)"] += 1
            continue
        if hit1 and hit2:
            key = "both_hit"
        elif hit1:
            key = "only_P1_hit"
        elif hit2:
            key = "only_P2_hit"
        else:
            key = "no_hit"
        stats[f"{key}[segments={len(parts)}]"] += 1
        examples.setdefault(key, []).append(
            {"name": name, "P1": cut1, "P2": cut2,
             "P1_exists": hit1, "P2_exists": hit2})
    print(f"\nparent_rules={dict(sorted(stats.items()))}")
    for key, items in examples.items():
        print(f"  {key}:")
        for item in items[:3]:
            print(f"    name={item['name']}\n      P1={item['P1']} exists={item['P1_exists']}"
                  f"\n      P2={item['P2']} exists={item['P2_exists']}")


def other_ids(path):
    """Показать идентификаторы, не похожие ни на v4, ни на составной `<uuid>.<N>`."""
    root = ET.parse(path).getroot()
    seen = []
    for element in root.iter():
        if local(element.tag) != "Metadata":
            continue
        ident = element.attrib.get("id", "")
        if UUID_RE.match(ident) or COMPOSITE_RE.match(ident):
            continue
        if len(seen) < 12:
            seen.append((element.attrib.get("name", ""), ident))
    print(f"\nother_id_examples={len(seen)}")
    for name, ident in seen:
        print(f"  name={name}\n    id={ident}")


def structure_probe(path):
    """Второй слой замера: словарь имён, распределение configVersion, сопоставление с .bsl."""
    root = ET.parse(path).getroot()
    rows = []
    for element in root.iter():
        if local(element.tag) != "Metadata":
            continue
        rows.append((element.attrib.get("name", ""), element.attrib.get("id", ""),
                     bool(element.attrib.get("configVersion"))))

    cv_by_segments = Counter()
    terminal_odd = Counter()
    child_type_even = Counter()
    for name, _ident, has_cv in rows:
        parts = name.split(".")
        cv_by_segments[(len(parts), has_cv)] += 1
        if len(parts) >= 3 and len(parts) % 2 == 1:
            terminal_odd[parts[-1]] += 1
        if len(parts) >= 4 and len(parts) % 2 == 0:
            child_type_even[parts[-2]] += 1
    print("\ncv_by_segments={}")
    for key, count in sorted(cv_by_segments.items()):
        print(f"  segments={key[0]} has_configVersion={key[1]} -> {count}")
    print(f"\nterminal_segment_of_odd_names(kinds={len(terminal_odd)})")
    for kind, count in terminal_odd.most_common(30):
        print(f"  {kind}: {count}")
    print(f"\nchild_type_of_even_names(kinds={len(child_type_even)})")
    for kind, count in child_type_even.most_common(40):
        print(f"  {kind}: {count}")
    return rows


def bsl_probe(root_dir):
    """Объём и раскладка .bsl в каталоге выгрузки: сколько файлов, байт, какой вид модуля."""
    root = Path(root_dir)
    total_files, total_bytes = 0, 0
    kinds = Counter()
    sizes = []
    for path in root.rglob("*.bsl"):
        total_files += 1
        size = path.stat().st_size
        total_bytes += size
        sizes.append((size, str(path.relative_to(root))))
        parts = path.relative_to(root).parts
        # вид модуля: имя файла модуля или имя каталога Ext/Forms
        kinds[parts[-1]] += 1
    print(f"\nbsl_files={total_files} total_bytes={total_bytes} "
          f"avg={total_bytes // max(total_files, 1)}")
    sizes.sort(reverse=True)
    print(f"largest={[(s, p) for s, p in sizes[:5]]}")
    print(f"bsl_file_names(kinds={len(kinds)})={dict(kinds.most_common(12))}")
    # раскладка: CommonModules/<Имя>/Ext/Module.bsl и <Вид>/<Имя>/Ext/<Модуль>.bsl
    layout = Counter()
    for path in root.rglob("*.bsl"):
        parts = path.relative_to(root).parts
        layout[(len(parts), parts[0], parts[-2] if len(parts) >= 2 else "")] += 1
    print("bsl_layout(top)= ")
    for key, count in layout.most_common(20):
        print(f"  depth={key[0]} top={key[1]} before_name={key[2]} -> {count}")


def path_templates(root_dir):
    """Шаблоны путей .bsl: сегменты-имена сворачиваются в <...>, остаётся форма раскладки.

    Нужно, чтобы сопоставление файла модуля с именем записи индекса строилось по
    фактическим формам выгрузки, а не по памяти о ней.
    """
    root = Path(root_dir)
    service = {"Ext", "Forms", "Templates", "Pictures", "Rights", "Help", "Styles",
               "CommonModules", "CommonForms", "CommonTemplates", "Commands", "Layouts"}
    templates = {}
    for path in root.rglob("*.bsl"):
        parts = list(path.relative_to(root).parts)
        folded = [parts[0]]
        for part in parts[1:-1]:
            folded.append(part if part in service else "<name>")
        folded.append(parts[-1])
        key = "\\".join(folded)
        templates.setdefault(key, []).append(str(path.relative_to(root)))
    print(f"\nbsl_path_templates={len(templates)}")
    for key, items in sorted(templates.items(), key=lambda kv: -len(kv[1])):
        print(f"  [{len(items)}] {key}\n      example={items[0]}")


CONFIGURATION_ROOT = "Configuration"
CATALOG_TO_KIND = {
    "AccountingRegisters": "AccountingRegister",
    "AccumulationRegisters": "AccumulationRegister",
    "BusinessProcesses": "BusinessProcess",
    "Catalogs": "Catalog",
    "ChartsOfAccounts": "ChartOfAccounts",
    "ChartsOfCharacteristicTypes": "ChartOfCharacteristicTypes",
    "CommandGroups": "CommandGroup",
    "CommonAttributes": "CommonAttribute",
    "CommonCommands": "CommonCommand",
    "CommonForms": "CommonForm",
    "CommonModules": "CommonModule",
    "CommonPictures": "CommonPicture",
    "CommonTemplates": "CommonTemplate",
    "Constants": "Constant",
    "DataProcessors": "DataProcessor",
    "DefinedTypes": "DefinedType",
    "DocumentJournals": "DocumentJournal",
    "DocumentNumerators": "DocumentNumerator",
    "Documents": "Document",
    "Enums": "Enum",
    "EventSubscriptions": "EventSubscription",
    "ExchangePlans": "ExchangePlan",
    "FilterCriteria": "FilterCriterion",
    "FunctionalOptions": "FunctionalOption",
    "FunctionalOptionsParameters": "FunctionalOptionsParameter",
    "HTTPServices": "HTTPService",
    "InformationRegisters": "InformationRegister",
    # Единственный каталог, где голоса равны (по одному объекту на вид); выбор сделан
    # по виду метаданных, который присутствует в индексе (IntegrationService).
    "IntegrationServices": "IntegrationService",
    "Languages": "Language",
    "Reports": "Report",
    "Roles": "Role",
    "ScheduledJobs": "ScheduledJob",
    "Sequences": "Sequence",
    "SessionParameters": "SessionParameter",
    "SettingsStorages": "SettingsStorage",
    "StyleItems": "StyleItem",
    "Styles": "Style",
    "Subsystems": "Subsystem",
    "Tasks": "Task",
    "WSReferences": "WSReference",
    "WebServices": "WebService",
    "XDTOPackages": "XDTOPackage",
}
SERVICE_DIR_TO_CHILD_TYPE = {
    "Forms": "Form",
    "Commands": "Command",
    "Templates": "Template",
    "Pictures": "Picture",
    "Rights": "Rights",
    "Styles": "Style",
}
MODULE_FILE_TERMINALS = {
    "Module.bsl": "Module",
    "ObjectModule.bsl": "ObjectModule",
    "ManagerModule.bsl": "ManagerModule",
    "CommandModule.bsl": "CommandModule",
    "RecordSetModule.bsl": "RecordSetModule",
    "ValueManagerModule.bsl": "ValueManagerModule",
    "SessionModule.bsl": "SessionModule",
    "ManagedApplicationModule.bsl": "ManagedApplicationModule",
    "OrdinaryApplicationModule.bsl": "OrdinaryApplicationModule",
    "ExternalConnectionModule.bsl": "ExternalConnectionModule",
    "FormModule.bsl": "Form",
}


def candidate_index_name(rel_parts, configuration_name=None):
    """По относительному пути .bsl построить имя записи индекса (или None).

    Разбор идёт от сегмента `Ext`: у модулей форм файл лежит в `Ext/Form/Module.bsl`,
    поэтому проверять «перед файлом обязательно Ext» нельзя (замер 17.10.2026:
    `Tasks\\ЗадачаИсполнителя\\Forms\\ФормаСписка\\Ext\\Form\\Module.bsl`). Сам каталог
    `Ext` может быть и корневым (`Ext\\SessionModule.bsl` — модули уровня конфигурации),
    поэтому его ищут с нулевой позиции.

    Правила взяты из фактических шаблонов выгрузки (замер, 61 шаблон):
      `<Каталог вида>/<Имя>/Ext/<Модуль>.bsl`             -> `<Вид>.<Имя>.<Модуль>`
      `<Каталог>/<Имя>/Forms/<Ф>/Ext/Form/Module.bsl`     -> `<Вид>.<Имя>.Form.<Ф>.Form`
      `CommonForms/<Имя>/Ext/Form/Module.bsl`             -> `CommonForm.<Имя>.Form.<Имя>.Form`
      `<Каталог>/<Имя>/Commands/<К>/Ext/CommandModule.bsl`-> `<Вид>.<Имя>.Command.<К>.CommandModule`
      `Ext/<Модуль>.bsl`                                  -> `Configuration.<Имя конфиги>.<Модуль>`
    """
    parts = list(rel_parts)
    if len(parts) < 2:
        return None
    ext_index = None
    for position in range(len(parts)):
        if parts[position] == "Ext":
            ext_index = position
            break
    if ext_index is None or ext_index >= len(parts) - 1:
        return None
    head, tail, module_file = parts[:ext_index], parts[ext_index + 1:-1], parts[-1]
    if module_file not in MODULE_FILE_TERMINALS:
        return None
    if tail and tail != ["Form"]:
        return None

    catalog = head[0] if head else ""
    if not head:
        # модули уровня самой конфигурации: `Ext/SessionModule.bsl`
        if not configuration_name:
            return None
        segments = [CONFIGURATION_ROOT, configuration_name]
    else:
        kind = CATALOG_TO_KIND.get(catalog, catalog[:-1] if catalog.endswith("s") else catalog)
        segments = [kind, head[1]]
    position = 2
    while position < len(head):
        directory = head[position]
        if directory not in SERVICE_DIR_TO_CHILD_TYPE or position + 1 >= len(head):
            return None
        segments.append(SERVICE_DIR_TO_CHILD_TYPE[directory])
        segments.append(head[position + 1])
        position += 2

    if tail == ["Form"]:
        # модуль содержимого формы лежит в `Ext/Form/Module.bsl`; терминал записи — Form.
        # У общей формы (`CommonForms/<Имя>/Ext/Form/Module.bsl`) промежуточного имени
        # элемента нет: запись индекса называется `CommonForm.<Имя>.Form` (замер 17.10.2026).
        segments.append("Form")
    elif tail:
        return None
    else:
        segments.append(MODULE_FILE_TERMINALS[module_file])
    return ".".join(segments)


def index_names_with_terminals(index_names, terminals):
    """Показать, как в индексе называются записи с данными терминалами."""
    print("\nindex_names_by_terminal:")
    for terminal in terminals:
        hits = [name for name in index_names if name.split(".")[-1] == terminal]
        print(f"  {terminal}: {len(hits)} example={hits[:3]}")


def module_match_probe(root_dir, index_names, configuration_name=None):
    """Сколько .bsl сопоставляются с записью индекса по правилу, а сколько нет."""
    root = Path(root_dir)
    matched, unmatched = 0, []
    for path in root.rglob("*.bsl"):
        candidate = candidate_index_name(path.relative_to(root).parts, configuration_name)
        if candidate and candidate in index_names:
            matched += 1
        else:
            unmatched.append((str(path.relative_to(root)), candidate))
    total = matched + len(unmatched)
    print(f"\nmodule_match total={total} matched={matched} unmatched={len(unmatched)}")
    for path, candidate in unmatched[:15]:
        print(f"  UNMATCHED {path}\n      candidate={candidate}")


def catalog_kind_probe(root_dir, index_names):
    """Сопоставить каталоги верхнего уровня выгрузки с видами записей индекса.

    Правило «отбрось букву s» даёт неверные пары (`FilterCriteria` -> `FilterCriterion`),
    поэтому словарь строится замером, а не правилом.
    """
    root = Path(root_dir)
    catalogs = sorted(p.name for p in root.iterdir() if p.is_dir())
    kinds = sorted({name.split(".")[1 - 1] for name in index_names})
    kinds = sorted({name.split(".")[0] for name in index_names})
    print(f"\ndump_catalogs={len(catalogs)}")
    print(",".join(catalogs))
    print(f"\nindex_kinds={len(kinds)}")
    print(",".join(kinds))
    print("\ncommon_form_index_names:")
    for name in sorted(n for n in index_names if n.startswith("CommonForm."))[:6]:
        print(f"  {name}")
    print("\ncommon_template_index_names:")
    for name in sorted(n for n in index_names if n.startswith("CommonTemplate."))[:4]:
        print(f"  {name}")


def kind_dictionary(root_dir, index_names):
    """Вывести словарь «каталог выгрузки -> вид записей индекса» мажоритарным перебором.

    Для каждого каталога берутся ВСЕ имена объектов и считается, под каким видом они
    присутствуют в индексе. Первый объект и правило «отбрось s» ненадёжны: имена
    пересекаются между видами (`CommandGroups/ОбщийМодуль...` существует и как
    `CommonModule....`), а `ChartsOfAccounts` -> `ChartOfAccounts` даёт вовсе неверную пару.
    """
    root = Path(root_dir)
    by_name = {}
    for name in index_names:
        parts = name.split(".")
        if len(parts) == 2:
            by_name.setdefault(parts[1], set()).add(parts[0])
    print("\nCATALOG_TO_KIND = {")
    for directory in sorted(p.name for p in root.iterdir()
                            if p.is_dir() and p.name != "Ext"):
        votes = Counter()
        for path in (root / directory).glob("*.xml"):
            for kind in by_name.get(path.stem, set()):
                votes[kind] += 1
        if not votes:
            continue
        best, count = votes.most_common(1)[0]
        runner_up = votes.most_common(2)[1] if len(votes) > 1 else None
        note = ""
        if runner_up:
            note = f"  # голоса: {dict(votes)}"
        print(f'    "{directory}": "{best}",{note}')
    print("}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    root_dir = str(Path(path).parent)
    index_names = set()
    for element in ET.parse(path).getroot().iter():
        if local(element.tag) == "Metadata":
            index_names.add(element.attrib.get("name", ""))
    configuration_name = ""
    for name in index_names:
        parts = name.split(".")
        if len(parts) == 2 and parts[0] == CONFIGURATION_ROOT:
            configuration_name = parts[1]
            break
    if len(sys.argv) > 2 and sys.argv[2] == "dictionary":
        kind_dictionary(root_dir, index_names)
    else:
        module_match_probe(root_dir, index_names, configuration_name)
