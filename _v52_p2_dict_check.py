#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V52, шаг П2: самопроверка словарей `src/configuration_filter_criteria.py`.

Пять проверок, каждая отвечает на свой вопрос (образец `_v51_p2_dict_check.py`, круг шире):

1. Числа словарей совпадают с замером корпуса: 11 свойств, 0 доменов значений, 2 вида
   детей, 8 колонок состояний. Числа держатся здесь как ожидаемые, а не выводятся из
   модуля: иначе опечатка в словаре перестала бы быть ошибкой.
2. Порядок тегов словаря совпадает с порядком тегов в РЕАЛЬНЫХ файлах — проверяются ВСЕ
   15 файлов круга, а не один: порядок является частью контракта словаря, и «один файл
   подошёл» не означал бы, что словарь закрыт.
3. ФОРМЫ содержимого тегов совпадают с видом разбора словаря (скаляр ↔ text/reference,
   `bool` ↔ bool, языковой блок ↔ multilang, вложенный блок ↔ type_block/content_list,
   пустой тег разрешён везде, кроме `Name`): вид разбора задаёт форма значения, и проверка
   ловит случай, когда словарь обещает один вид, а файлы дают другой.
4. Колонки словаря существуют в живой схеме `ckb_1c_configurations` (П1 выполнен — эталон
   отсутствующих пуст), а словари состояний совпадают с перечнями CHECK'ов схемы: код и
   схема обязаны отвечать одинаково, иначе проверка П6 сверяла бы два разных знания.
5. Словарь записи `types` отличается от словаря V48/V50 РОВНО ключом `container` — тем,
   чем узел называет форму контейнера значения (Q6); остальные ключи обязаны совпадать,
   иначе два узла писали бы в одно поле разные записи.

Запуск: python _v52_p2_dict_check.py
"""
import re
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_common_attributes as ca  # noqa: E402
import configuration_exchange_plans as ep  # noqa: E402
import configuration_filter_criteria as fc  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

# Эталон замера `_v52_p2_property_probe.py` (15 файлов круга). Держится здесь, а не
# выводится из модуля: опечатка в словаре обязана оставаться ошибкой проверки.
EXPECTED_PROPERTY_COUNT = 11
EXPECTED_VALUE_DOMAINS = 0          # тегов с доменом значений вне true/false — 0
EXPECTED_CHILD_KINDS = ("Form", "Command")
EXPECTED_STATE_COLUMNS = 8

# Какое содержимое тега соответствует виду разбора словаря. `empty` разрешён всем тегам,
# кроме `Name` (имя ключуется колонкой `object_name` и обязано быть); `xsi_nil` корпусом
# вида не встречалась — она разрешена как граница словаря форм, но не как ожидаемое значение.
FORMS_BY_KIND = {
    fc.KIND_TEXT: {"scalar"},
    fc.KIND_MULTILANG: {"multilang"},
    fc.KIND_BOOL: {"bool"},
    fc.KIND_REFERENCE: {"scalar"},
    fc.KIND_TYPE: {"nested"},
    fc.KIND_CONTENT_LIST: {"nested"},
}
ALLOWED_EMPTY_TAGS = None            # None = пустой тег разрешён всем позициям словаря
NAME_TAG = "Name"

NIL_ATTR = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def loc(tag):
    return tag.rsplit("}", 1)[-1]


def find_child(node, name):
    for child in node:
        if loc(child.tag) == name:
            return child
    return None


def content_form(node):
    """Та же классификация формы, что в замере `_v52_p2_property_probe.py`."""
    if node.get(NIL_ATTR) == "true":
        return "xsi_nil"
    children = list(node)
    text = (node.text or "").strip()
    if not children:
        if not text:
            return "empty"
        if text in ("true", "false"):
            return "bool"
        return "scalar"
    names = [loc(c.tag) for c in children]
    if names and all(n in ("item", "lang", "content") for n in names):
        grand = [loc(g.tag) for c in children for g in c]
        if set(grand) <= {"lang", "content"}:
            return "multilang"
    return "nested"


def registration_files():
    """Все файлы регистрации вида по четырём выгрузкам (круг пробы П0)."""
    found = []
    for dump in DUMPS:
        view = DUMP_ROOT / dump / fc.DIR_NAME
        if not view.is_dir():
            continue
        for path in sorted(view.glob("*.xml")):
            found.append((dump, path))
    return found


def object_of(path):
    root = ET.parse(str(path)).getroot()
    obj = find_child(root, fc.OBJECT_KIND_TAG)
    if obj is None:
        raise AssertionError(f"{path}: узла вида {fc.OBJECT_KIND_TAG} нет")
    return obj


def check(label, ok, detail=""):
    print(f"  [{'OK ' if ok else 'ОШИБКА'}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def check_counts():
    bad = False
    records = fc.property_records()
    tags = [tag for tag, _column, _kind in records]
    bad |= not check("свойств вида в словаре ровно %d" % EXPECTED_PROPERTY_COUNT,
                     len(records) == EXPECTED_PROPERTY_COUNT,
                     "словарь даёт %d: %s" % (len(records), tags))
    bad |= not check("константа числа свойств равна длине словаря",
                     fc.FILTER_CRITERION_PROPERTY_COUNT == len(records),
                     str(fc.FILTER_CRITERION_PROPERTY_COUNT))
    domains = sorted(column for column, values in fc.PROPERTY_VALUE_DICTIONARY.items()
                     if any(value not in ("true", "false") for value in values))
    bad |= not check("доменов значений вне true/false в словаре %d"
                     % EXPECTED_VALUE_DOMAINS,
                     len(domains) == EXPECTED_VALUE_DOMAINS, str(domains))
    bad |= not check("словарь значений пуст, а не «забыт» (замер П2: 0 кандидатов в enum)",
                     fc.PROPERTY_VALUE_DICTIONARY == {},
                     "записей: %d" % len(fc.PROPERTY_VALUE_DICTIONARY))
    bad |= not check("bool-домен круга назван константой вида, а не словарём enum",
                     fc.BOOL_VALUES == ("true", "false"), str(fc.BOOL_VALUES))
    bad |= not check("видов детей ровно %d (замер 1.2)" % len(EXPECTED_CHILD_KINDS),
                     fc.CHILD_KINDS == EXPECTED_CHILD_KINDS, str(fc.CHILD_KINDS))
    bad |= not check("колонок состояния в словаре ровно %d и каждая указывает на словарь"
                     % EXPECTED_STATE_COLUMNS,
                     len(fc.STATE_VOCABULARIES) == EXPECTED_STATE_COLUMNS
                     and all(v for v in fc.STATE_VOCABULARIES.values()),
                     str(sorted(fc.STATE_VOCABULARIES)))
    bad |= not check("словарь состояний покрывает ровно те колонки, которые названы "
                     "в таблицах",
                     set(fc.STATE_VOCABULARIES) == set(fc.STATE_VOCABULARY_TABLES),
                     str(set(fc.STATE_VOCABULARIES) ^ set(fc.STATE_VOCABULARY_TABLES)))
    for kind in fc.CHILD_KINDS:
        table = fc.CHILD_TABLE_BY_KIND.get(kind)
        bad |= not check("ребёнок %s: таблица названа (%s)" % (kind, table), bool(table))
        column = fc.child_list_column(kind)
        bad |= not check("ребёнок %s: колонка перечня названа (%s)" % (kind, column),
                         column in (fc.CHILD_LIST_FORM_NAMES, fc.CHILD_LIST_COMMAND_UUIDS))
    try:
        fc.child_list_column("Attribute")
        bad |= not check("неизвестного вида детей нет: вызов обязан падать, а не молчать",
                         False, "KeyError не поднят")
    except KeyError:
        bad |= not check("неизвестного вида детей нет: вызов падает KeyError-ом", True)
    return not bad


def check_tag_order():
    """Порядок тегов словаря против ВСЕХ файлов круга (а не против одного файла)."""
    dict_tags = [tag for tag, _column, _kind in fc.property_records()]
    files = registration_files()
    if not files:
        print("  [ОШИБКА] файлов регистрации вида не найдено — проверка не выполнена")
        return False
    signatures = {}
    offenders = []
    for dump, path in files:
        props = find_child(object_of(path), "Properties")
        if props is None:
            offenders.append("%s/%s: блока Properties нет" % (dump, path.name))
            continue
        signatures.setdefault(tuple(loc(t.tag) for t in props), []).append(
            "%s/%s" % (dump, path.name))
    if not signatures:
        print("  [ОШИБКА] ни в одном файле блока Properties — проверка не выполнена")
        return False
    ok = True
    for signature, names in signatures.items():
        if list(signature) == dict_tags:
            continue
        ok = False
        extra = [t for t in signature if t not in dict_tags]
        missing = [t for t in dict_tags if t not in signature]
        print("  [ОШИБКА] %d файл(ов) (%s и др.) дают другой набор: лишние %s, "
              "не описаны %s" % (len(names), names[0], extra, missing))
        if not extra and not missing:
            print("           тот же набор, но порядок расходится: словарь %s, файл %s"
                  % (dict_tags, list(signature)))
    if ok:
        print("  [OK ] порядок %d тегов совпадает с файлом во всех %d файлах круга "
              "(различных порядков: %d)" % (len(dict_tags), len(files), len(signatures)))
    for offender in offenders:
        print("  [ОШИБКА] %s" % offender)
    return ok and not offenders


def check_forms_vs_kinds():
    """Вид разбора словаря против ФОРМ содержимого, которые дают файлы."""
    kind_by_tag = {tag: kind for tag, _column, kind in fc.property_records()}
    seen = {}
    for dump, path in registration_files():
        props = find_child(object_of(path), "Properties")
        for tag_node in ([] if props is None else list(props)):
            seen.setdefault(loc(tag_node.tag), Counter())[content_form(tag_node)] += 1
    ok = True
    for tag, kind in kind_by_tag.items():
        forms = seen.get(tag, Counter())
        if not forms:
            print("  [ОШИБКА] %s: содержимого тега в файлах не найдено" % tag)
            ok = False
            continue
        allowed = set(FORMS_BY_KIND.get(kind, set())) | {"xsi_nil"}
        if tag != NAME_TAG:
            allowed.add("empty")
        unexpected = sorted(set(forms) - allowed)
        if unexpected:
            print("  [ОШИБКА] %s: вид разбора %r не описывает формы %s (словарь допускает "
                  "%s)" % (tag, kind, unexpected, sorted(allowed)))
            ok = False
    if ok:
        detail = "; ".join("%s:%s" % (tag, dict(forms))
                           for tag, forms in sorted(seen.items()))
        print("  [OK ] формы содержимого файлов круга соответствуют видам словаря")
        print("        %s" % detail[:400])
    return ok


def schema_columns(table):
    import external_db
    with external_db.connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s", (table,))
        return {row[0] for row in cur.fetchall()}


def check_columns_against_schema():
    """Колонки словарей против живой схемы: П1 выполнен — отсутствующих быть не должно."""
    bad = False
    wanted = {
        fc.TABLE_NAME: (set(fc.property_columns()) | {fc.CONTENT_STATE_COLUMN,
                                                      fc.CONTENT_COUNT_COLUMN,
                                                      fc.CHILDREN_STATE_COLUMN,
                                                      fc.UNKNOWN_NAMES_COLUMN,
                                                      fc.FORM_NAMES_COLUMN,
                                                      fc.COMMAND_UUIDS_COLUMN,
                                                      fc.DEFAULT_FORM_STATE_COLUMN,
                                                      fc.AUXILIARY_FORM_STATE_COLUMN}),
        fc.CONTENT_TABLE_NAME: {fc.CONTENT_ORDINAL_COLUMN, fc.CONTENT_TARGET_TAG_COLUMN,
                                fc.CONTENT_TARGET_COLUMN, fc.CONTENT_TARGET_TYPE_COLUMN,
                                fc.CONTENT_TARGET_ID_COLUMN, fc.CONTENT_TARGET_UUID_COLUMN,
                                fc.CONTENT_RESOLVE_STATE_COLUMN,
                                fc.CONTENT_UNRESOLVED_PATH_COLUMN},
    }
    for table, columns in wanted.items():
        existing = schema_columns(table)
        if not existing:
            bad = True
            print("  [ОШИБКА] %s таблицы в схеме нет — её создаёт П1 (колонок ждали %d)"
                  % (table, len(columns)))
            continue
        missing = columns - existing
        if missing:
            bad = True
            print("  [ОШИБКА] %s нет в схеме: %s (П1 применён — эталон пуст)"
                  % (table, sorted(missing)))
        else:
            print("  [OK ] %s: колонок в словаре %d, все они есть в схеме"
                  % (table, len(columns)))
    return not bad


def check_constraints(table):
    import external_db
    with external_db.connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE connamespace='public'::regnamespace AND conrelid=%s::regclass "
            "AND contype='c'", (table,))
        return [(row[0], row[1]) for row in cur.fetchall()]


def constraint_values(constraints, column):
    """Закрытый перечень значений колонки из CHECK'ов схемы (оба вида записи)."""
    values = set()
    # pg_get_constraintdef пишет `col = ANY (ARRAY['a'::text, 'b'::text])` — массив
    # закрывается одним `]`, а не `]]`; вторая скобка относится к предикату.
    patterns = (re.escape(column) + r"\s*=\s*ANY\s*\(\s*ARRAY\[(.*?)\]",
                re.escape(column) + r"\s+IN\s*\((.*?)\)")
    for _name, definition in constraints:
        for pattern in patterns:
            for inner in re.findall(pattern, definition, flags=re.DOTALL):
                values.update(re.findall(r"'([^']*)'", inner))
    return values


def check_state_vocabularies():
    """Словари кода против перечней CHECK'ов схемы: два независимых источника."""
    bad = False
    by_table = {}
    for column in sorted(fc.STATE_VOCABULARIES):
        table = fc.state_vocabulary_table(column)
        if table not in by_table:
            by_table[table] = check_constraints(table)
        constraints = by_table[table]
        if not constraints:
            bad = True
            print("  [ОШИБКА] %s: CHECK'ов состояния в схеме нет — сравнивать не с чем"
                  % table)
            continue
        db_values = constraint_values(constraints, column)
        code_values = set(fc.state_vocabulary(column))
        if not db_values:
            bad = True
            print("  [ОШИБКА] %s.%s: CHECK замкнутого перечня не задаёт (словарь кода %d)"
                  % (table, column, len(code_values)))
        elif db_values != code_values:
            bad = True
            print("  [ОШИБКА] %s.%s: словарь кода и CHECK схемы расходятся: в коде %s, "
                  "в схеме %s" % (table, column, sorted(code_values), sorted(db_values)))
        else:
            print("  [OK ] %s.%s: словарь кода = CHECK схемы (%d значений)"
                  % (table, column, len(db_values)))
    return not bad


def props_tags(node):
    props = find_child(node, "Properties") if node is not None else None
    return [loc(t.tag) for t in props] if props is not None else []


def check_type_dictionaries_against_v50():
    """Словари блока `<Type>` против V50: отличие — РОВНО ключ `container` (Q6).

    Два узла пишут в одноимённые колонки (`type_parse_state`, `type_multiplicity`, `types`)
    — значит словари обязаны совпадать, иначе одна и та же форма значения в двух таблицах
    получила бы разные состояния. Отличие узла V52 названо планом и оно одно: запись вида
    говорит о форме контейнера значения (`Type`/`TypeSet`).
    """
    bad = False
    added = set(fc.TYPE_ENTRY_KEYS) - set(ca.TYPE_ENTRY_KEYS)
    dropped = set(ca.TYPE_ENTRY_KEYS) - set(fc.TYPE_ENTRY_KEYS)
    ok_entry = (added == {"container"}) and not dropped
    bad |= not check("словарь записи `types` = словарь V50 + ключ `container`", ok_entry,
                     "добавлено %s, утрачено %s" % (sorted(added), sorted(dropped)))
    pairs = (("TYPE_CLASS_VALUES", fc.TYPE_CLASS_VALUES, ca.TYPE_CLASS_VALUES),
             ("MULTIPLICITY_VALUES", fc.MULTIPLICITY_VALUES, ca.MULTIPLICITY_VALUES),
             ("состояния блока Type", fc.TYPE_BLOCK_STATES, ca.RECORD_STATES),
             ("TYPE_ENTRY_TARGET_KEYS", fc.TYPE_ENTRY_TARGET_KEYS,
              ca.TYPE_ENTRY_TARGET_KEYS),
             ("NS_XML_SCHEMA", (fc.NS_XML_SCHEMA,), (ca.NS_XML_SCHEMA,)),
             ("NS_V8_CORE", (fc.NS_V8_CORE,), (ca.NS_V8_CORE,)),
             ("NS_CURRENT_CONFIG", (fc.NS_CURRENT_CONFIG,), (ca.NS_CURRENT_CONFIG,)),
             ("PLATFORM_TYPE_LOCAL_NAMES", tuple(sorted(fc.PLATFORM_TYPE_LOCAL_NAMES)),
              tuple(sorted(ca.PLATFORM_TYPE_LOCAL_NAMES))),
             ("XS_TYPE_LOCAL_NAMES", tuple(sorted(fc.XS_TYPE_LOCAL_NAMES)),
              tuple(sorted(ca.XS_TYPE_LOCAL_NAMES))),
             ("QUALIFIER_TAGS", fc.QUALIFIER_TAGS, ca.QUALIFIER_TAGS),
             ("REFERENCE_SUFFIX", (fc.REFERENCE_SUFFIX,), (ca.REFERENCE_SUFFIX,)),
             ("DEFINED_TYPE_LOCAL_NAME", (fc.DEFINED_TYPE_LOCAL_NAME,),
              (ca.DEFINED_TYPE_LOCAL_NAME,)))
    for name, mine, theirs in pairs:
        same = tuple(mine) == tuple(theirs) or set(mine) == set(theirs)
        bad |= not check("%s совпадает со словарём V50" % name, same,
                         "в V52 %s, в V50 %s" % (list(mine)[:6], list(theirs)[:6])
                         if not same else "")
    bad |= not check("контейнеры значения названы обеими измеренными формами",
                     set(fc.TYPE_CONTAINERS) == {fc.CONTAINER_TYPE,
                                                fc.CONTAINER_TYPE_SET},
                     str(fc.TYPE_CONTAINERS))
    return not bad


def check_child_dictionaries_against_v51():
    """Словари детей вида — ТЕ ЖЕ словари, что у V51, и тот же порядок тегов в файлах.

    Узел не заводит новых колонок и новых словарей детей (Q3, вариант A), поэтому проверка
    обязана показать и обратное: словари V51 применимы к файлам этого вида без правок.
    """
    bad = False
    mincfg = DUMP_ROOT / "MinCfg" / fc.DIR_NAME
    targets = []
    command_node = None
    children = find_child(object_of(mincfg / "СвязанныеДокументы.xml"), "ChildObjects")
    if children is not None:
        for child in children:
            if loc(child.tag) == fc.CHILD_COMMAND:
                command_node = child
                break
    targets.append((fc.CHILD_COMMAND, ep.child_property_records(ep.CHILD_COMMAND),
                    props_tags(command_node), ("Help", "CommandInterface")))
    form_dir = mincfg / "СвязанныеДокументы" / "Forms"
    form_files = sorted(form_dir.glob("*.xml")) if form_dir.is_dir() else []
    if form_files:
        form_node = find_child(ET.parse(str(form_files[0])).getroot(), "Form")
        targets.append((fc.CHILD_FORM, ep.child_property_records(ep.CHILD_FORM),
                        props_tags(form_node), ()))
    else:
        bad = True
        print("  [ОШИБКА] файла формы вида %s нет — проверку словаря детей выполнить "
              "нечем" % form_dir)
    for kind, records, file_tags, expected_absent in targets:
        dict_tags = [tag for tag, _column, _k in records]
        if not file_tags:
            bad = True
            print("  [ОШИБКА] ребёнок %s: тегов в файле выгрузки нет — проверка не "
                  "выполнена" % kind)
            continue
        absent = [t for t in expected_absent if t not in file_tags]
        comparable = [t for t in dict_tags if t not in absent]
        if comparable == file_tags:
            print("  [OK ] ребёнок %s: словарь V51 (%d тегов) совпадает с файлом этого "
                  "вида%s" % (kind, len(file_tags),
                              " (в файле нет: %s)" % absent if absent else ""))
            continue
        bad = True
        extra = [t for t in comparable if t not in file_tags]
        missing = [t for t in file_tags if t not in comparable]
        print("  [ОШИБКА] ребёнок %s: словарь V51 даёт %d тегов, файл %d; лишние %s, "
              "не описаны %s" % (kind, len(comparable), len(file_tags), extra, missing))
    return not bad


def main():
    print("=== П2: самопроверка словарей узла V52 ===")
    ok_counts = check_counts()
    print("\n--- порядок тегов против ВСЕХ файлов круга ---")
    ok_order = check_tag_order()
    print("\n--- формы содержимого против видов разбора ---")
    ok_forms = check_forms_vs_kinds()
    print("\n--- колонки словарей против живой схемы ---")
    ok_columns = check_columns_against_schema()
    print("\n--- словари состояний против CHECK'ов схемы ---")
    ok_vocab = check_state_vocabularies()
    print("\n--- словари блока Type против V50 (отличие = container) ---")
    ok_type = check_type_dictionaries_against_v50()
    print("\n--- словари детей против V51 и против файлов вида ---")
    ok_children = check_child_dictionaries_against_v51()
    print("\n=== итог ===")
    flags = ("числа", "порядок тегов", "формы/виды", "колонки схемы", "словари vs CHECK",
             "Type vs V50", "дети vs V51")
    results = (ok_counts, ok_order, ok_forms, ok_columns, ok_vocab, ok_type, ok_children)
    print("; ".join("%s: %s" % (name, "OK" if ok else "ОШИБКА")
                    for name, ok in zip(flags, results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())





