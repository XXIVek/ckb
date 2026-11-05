#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Шаг П2 узла V48: офлайн-проверка разбора `src/configuration_session_parameters.py`.

Офлайн — то есть без живой БД и без записи (приём `_v46_p3_offline_probe.py`): разбор
проверяется на корпусе и на фикстурах, а разрешение ссылок — на переданных строках
индекса, а не на таблице. Живой индекс состава проверяется шагом П4, когда появляется
стадия.

Что проверяется и почему именно это:

1. круг и числа базовой линии (2.1, 2.4, 2.4.3, 2.5): 207 файлов, 213 значений,
   24 ссылочных, 6 файлов с составным типом, распределение по выгрузкам 2/6/101/98.
   Разбор, давший другое число, либо потерял знание, либо придумал его;
2. закрытость словарей: каждая запись `types` содержит ровно ключи `TYPE_ENTRY_KEYS`
   (+ ключи цели только у разрешённой ссылки), кратность совпадает с числом записей,
   состояние строки согласовано с состояниями записей, `index` — 0..n-1 по порядку файла.
   Именно это CHECK схемы не выражает (замер 2.5), поэтому оно существует здесь;
3. `type_raw` полон: число тегов значений в исходном блоке равно числу записей (этот же
   guard нашёл дефект первой версии выражения внешнего блока — см. комментарий
   `TYPE_BLOCK_RE` в модуле);
4. неизвестное называется, а не проглатывается: элемент вне словаря содержимого (2.4.2),
   префикс без объявления в файле (2.4.4), свойство вне словаря вида (2.3), пустой блок
   `<Type>`, блок только с квалификаторами, отсутствующий `<Name>`, кривой uuid,
   смесь распознанного и нераспознанного значений (`partial`) — каждый случай даёт
   названное состояние или причину;
5. правило перехода и разрешение индексом (2.5): форма `<Вид>Ref.<Имя>` → индексное имя,
   ключи цели только у разрешённого значения; сверка с индексом различает `matched`,
   `uuid_mismatch`, `file_only`, `index_only`.

Запуск: `python _v48_p2_offline_probe.py` (ничего не пишет в БД; фикстуры — в `_scratch/`).
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_session_parameters as SP  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
FIXTURE_DIR = ROOT / "_scratch" / "v48_p2_fixtures"

# базовая линия раздела 2 (повторный прогон обязан совпасть; числа снимает сам прогон)
BASELINE_FILES = {"MinCfg": 2, "KomMag": 6, "BGU2": 101, "BP3": 98}
BASELINE_TOTAL_FILES = 207
BASELINE_TOTAL_VALUES = 213
BASELINE_REF_VALUES = 24
BASELINE_COMPOSITE_FILES = 6
BASELINE_OBSERVATIONS = 0

RESULTS = []


def check(label, condition, detail=""):
    RESULTS.append((bool(condition), label, detail))
    print(("[OK  ] " if condition else "[FAIL] ") + label + ((" — " + str(detail)) if detail else ""))


def note(label, detail=""):
    print("[NOTE] " + label + ((" — " + str(detail)) if detail else ""))


def check_row_invariants(rows):
    """Закрытость словарей и согласованность колонок (то, чего не выражает CHECK)."""
    problems = []
    for row in rows:
        who = row["source_path"]
        entries = row["types"]
        # 1. кратность = число записей (та же формула, что и CHECK схемы)
        expected_mult = SP.multiplicity_of(len(entries))
        if row["type_multiplicity"] != expected_mult:
            problems.append("%s: кратность %r ≠ выведенной %r"
                            % (who, row["type_multiplicity"], expected_mult))
        # 2. состояние строки согласно состояниям записей
        if row["type_parse_state"] != SP.type_row_state(entries):
            problems.append("%s: состояние строки не согласовано с записями" % who)
        # 3. пустой массив обязан соответствовать отсутствию блока
        if (not entries) != (row["type_parse_state"] == SP.STATE_ABSENT):
            problems.append("%s: пустые types и состояние %r не соответствуют друг другу"
                            % (who, row["type_parse_state"]))
        # 4. ключи записи замкнуты
        for position, entry in enumerate(entries):
            if entry.get("index") != position:
                problems.append("%s: запись %d имеет index=%r (порядок файла потерян)"
                                % (who, position, entry.get("index")))
            allowed = set(SP.TYPE_ENTRY_KEYS)
            if entry.get("class") == SP.CLASS_OBJECT_REF:
                allowed |= set(SP.TYPE_ENTRY_TARGET_KEYS)
            allowed |= {"reason"}
            extra = set(entry) - allowed
            missing = set(SP.TYPE_ENTRY_KEYS) - set(entry)
            if extra:
                problems.append("%s: запись %d содержит ключи вне словаря: %s"
                                % (who, position, ", ".join(sorted(extra))))
            if missing:
                problems.append("%s: записи %d не хватает ключей: %s"
                                % (who, position, ", ".join(sorted(missing))))
            if entry.get("resolved") is True:
                absent = set(SP.TYPE_ENTRY_TARGET_KEYS) - set(entry)
                if absent:
                    problems.append("%s: разрешённая ссылка без ключей цели: %s"
                                    % (who, ", ".join(sorted(absent))))
            elif entry.get("class") == SP.CLASS_OBJECT_REF:
                wrong = (set(SP.TYPE_ENTRY_TARGET_KEYS) - {"resolved"}) & set(entry)
                if wrong:
                    problems.append("%s: неразрешённая ссылка содержит ключи цели: %s"
                                    % (who, ", ".join(sorted(wrong))))
        # 5. type_raw полон: тегов значений в исходном блоке столько же, сколько записей
        tags = SP.count_value_type_tags(row["type_raw"])
        if row["type_raw"] is not None and tags != len(entries):
            problems.append("%s: в исходном блоке %d тегов значений, записей %d"
                            % (who, tags, len(entries)))
        if row["type_raw"] is None and entries:
            problems.append("%s: записи типа есть, а исходного блока нет" % who)
    return problems


def check_corpus():
    """Числа базовой линии раздела 2 по четырём выгрузкам (2.1, 2.4, 2.4.3, 2.5)."""
    totals = {"files": 0, "values": 0, "refs": 0, "composite": 0, "observations": 0}
    per_dump = {}
    all_rows = []
    for dump in DUMPS:
        directory = DUMP_ROOT / dump
        if not directory.exists():
            check("выгрузка %s доступна" % dump, False, "каталога нет")
            continue
        report = SP.collect_session_parameters(directory)
        per_dump[dump] = report
        all_rows.extend(report["rows"])
        totals["files"] += report["files_found"]
        totals["values"] += report["types_total"]
        totals["refs"] += report["types_by_class"][SP.CLASS_OBJECT_REF]
        totals["composite"] += report["types_multiplicity"][SP.MULT_COMPOSITE]
        totals["observations"] += len(report["observations"])
        check("круг %s: файлов %d (замер 2.1)" % (dump, report["files_found"]),
              report["files_found"] == BASELINE_FILES[dump],
              "ожидалось %s, получено %d" % (BASELINE_FILES[dump], report["files_found"]))
        check("разбор %s: отказов нет" % dump, not report["files_failed"],
              report["files_failed"][:2])
        check("содержимое каталога %s: только xml, подкаталогов нет (2.3)" % dump,
              not report["observations"], report["observations"][:3])
        check("несловарного содержимого блока <Type> в %s нет (2.4.2)" % dump,
              not report["unexpected_tags"], report["unexpected_tags"])
        check("свойств вне словаря вида в %s нет (2.3)" % dump,
              not report["unknown_properties"], report["unknown_properties"])
        check("число тегов значений = число записей в %s" % dump,
              not report["value_tag_mismatch"], report["value_tag_mismatch"][:3])
        check("офлайн-режим %s: ни одна ссылка не считается разрешённой" % dump,
              report["types_resolved"] == 0,
              "resolved=%d" % report["types_resolved"])
    check("суммарный круг: %d файлов (замер 2.1)" % totals["files"],
          totals["files"] == BASELINE_TOTAL_FILES, totals)
    check("суммарное число значений типа: %d (замер 2.4)" % totals["values"],
          totals["values"] == BASELINE_TOTAL_VALUES, totals["values"])
    check("ссылочных значений: %d (замер 2.5)" % totals["refs"],
          totals["refs"] == BASELINE_REF_VALUES, totals["refs"])
    check("файлов с составным типом: %d (замер 2.4.3)" % totals["composite"],
          totals["composite"] == BASELINE_COMPOSITE_FILES, totals["composite"])
    check("наблюдений о составе каталогов нет (%d) — примитивность вида подтверждена"
          % totals["observations"], totals["observations"] == BASELINE_OBSERVATIONS)

    problems = check_row_invariants(all_rows)
    check("инварианты строк (закрытость словарей, порядок, полнота type_raw)",
          not problems, problems[:5])

    # классы значений по корпусу: определяемых типов в параметрах сеанса нет (2.4.4)
    defined = sum(per_dump[d]["types_by_class"][SP.CLASS_DEFINED_TYPE_REF] for d in per_dump)
    check("определяемых типов внутри <Type> в корпусе нет (замер 2.4.4)", defined == 0, defined)
    unknown = sum(per_dump[d]["types_by_class"][SP.CLASS_UNKNOWN] for d in per_dump)
    check("значений неизвестного класса в корпусе нет (словарь закрыт замером)",
          unknown == 0, unknown)
    ns_seen = set()
    for dump in per_dump:
        ns_seen.update(per_dump[dump]["namespace_prefixes"])
    check("префиксы пространств имён собираются (2.4.4: признак по URI)",
          "cfg" in ns_seen and "v8" in ns_seen and "xs" in ns_seen, sorted(ns_seen)[:8])
    note("префиксы по корпусу", sorted(ns_seen))

    # составной тип: значения идут порядком файла, оба сохранены в type_raw
    composite_rows = [row for row in all_rows
                      if row["type_multiplicity"] == SP.MULT_COMPOSITE]
    check("каждый составный тип сохраняет оба значения в порядке файла",
          len(composite_rows) == BASELINE_COMPOSITE_FILES and
          all(len(row["types"]) >= 2 for row in composite_rows),
          [(row["object_name"], len(row["types"])) for row in composite_rows])
    check("исходный блок составного типа содержит оба тега значений",
          all(SP.count_value_type_tags(row["type_raw"]) == len(row["types"])
              for row in composite_rows))
    return all_rows


FIXED_UUID = "11111111-2222-3333-4444-555555555555"
OTHER_UUID = "66666666-7777-8888-9999-000000000000"
HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
    'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" '
    'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
    'xmlns:xs="http://www.w3.org/2001/XMLSchema">\n'
)


def fixture(name, body):
    """Записать фикстуру в `_scratch` и вернуть путь к ней."""
    directory = FIXTURE_DIR / SP.DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name + ".xml")
    path.write_text(HEADER + body + "</MetaDataObject>\n", encoding="utf-8")
    return path


def props(name, uuid=FIXED_UUID, extra="", type_block="", comment=""):
    """Тело фикстуры: обёртка Properties с четырьмя свойствами вида."""
    return ('<%s uuid="%s"><Properties>'
            "<Name>%s</Name>"
            "<Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>%s</v8:content></v8:item>"
            "</Synonym><Comment>%s</Comment>%s%s"
            "</Properties></SessionParameter>"
            % (SP.OBJECT_KIND_TAG, uuid, name, name, comment, type_block, extra))


def check_fixtures():
    """Отрицательные и граничные случаи на фикстурах: состояние называется, а не молчит."""
    if FIXTURE_DIR.exists():  # фикстуры прошлого прогона не должны попадать в круг
        shutil.rmtree(FIXTURE_DIR)
    cases = {
        # блок <Type> есть, значений в нём нет → «типа не было» (Q3, вариант A)
        "ПустойБлок": props("ПустойБлок", type_block="<Type/>"),
        # квалификаторы без значений: состояние absent, предупреждение названо
        "ТолькоКвалификаторы": props(
            "ТолькоКвалификаторы",
            type_block=("<Type><v8:StringQualifiers><v8:Length>10</v8:Length>"
                        "<v8:AllowedLength>Variable</v8:AllowedLength>"
                        "</v8:StringQualifiers></Type>")),
        # содержимое вне словаря 2.4.2: unknown_form, а не пустой массив
        "НеизвестныйЭлемент": props(
            "НеизвестныйЭлемент",
            type_block=("<Type><v8:TypeSet><v8:Type>cfg:DefinedType.Сумма</v8:Type>"
                        "</v8:TypeSet></Type>")),
        # префикс не объявлен в файле: класс не выводится (2.4.4)
        "НеобъявленныйПрефикс": ('<SessionParameter uuid="%s"><Properties>'
                                 "<Name>НеобъявленныйПрефикс</Name><Synonym/><Comment/>"
                                 "<Type><v8:Type>zz:CatalogRef.Организации</v8:Type></Type>"
                                 "</Properties></SessionParameter>" % FIXED_UUID),
        # смесь распознанного и нераспознанного → partial (Q4: тип бывает составным)
        "СмешанныйТип": props(
            "СмешанныйТип",
            type_block=("<Type><v8:Type>xs:string</v8:Type>"
                        "<v8:StringQualifiers><v8:Length>0</v8:Length>"
                        "</v8:StringQualifiers>"
                        "<v8:Type>v8:NotInList</v8:Type></Type>")),
        # свойство вне словаря 2.3: называется, колонку не получает
        "ЧужоеСвойство": props("ЧужоеСвойство",
                               type_block="<Type><v8:Type>xs:boolean</v8:Type></Type>",
                               extra="<ObjectBelonging>Application</ObjectBelonging>"),
        # пустой <Name>: строку нечем ключить → отказ с причиной
        "БезИмени": ('<SessionParameter uuid="%s"><Properties><Name/><Synonym/><Comment/>'
                     "<Type><v8:Type>xs:boolean</v8:Type></Type></Properties>"
                     "</SessionParameter>" % FIXED_UUID),
        # uuid не по правилу R3 → отказ
        "КривойUuid": props("КривойUuid", uuid="не-uuid",
                            type_block="<Type><v8:Type>xs:boolean</v8:Type></Type>"),
        # xs-имя вне перечня: unknown_form, а не «примитив по умолчанию»
        "ВнеПеречняТипов": props("ВнеПеречняТипов",
                                 type_block="<Type><v8:Type>xs:base64Binary</v8:Type></Type>"),
        # определяемый тип: форма распознана, индексом не разрешается (2.4.4)
        "ОпределяемыйТип": props("ОпределяемыйТип",
                                 type_block="<Type><v8:Type>cfg:DefinedType.Сумма</v8:Type></Type>"),
        # чужое пространство имён: unknown с названным URI
        "ЧужойURI": ('<SessionParameter uuid="%s"><Properties><Name>ЧужойURI</Name>'
                     "<Synonym/><Comment/>"
                     '<Type><foo:Type xmlns:foo="http://example.com/other">'
                     "foo:Something</foo:Type></Type></Properties></SessionParameter>"
                     % FIXED_UUID),
        # дубликат свойства: берётся первое, факт назван предупреждением
        "ДубликатСвойства": ('<SessionParameter uuid="%s"><Properties>'
                             "<Name>ДубликатСвойства</Name><Name>ВтороеИмя</Name>"
                             "<Synonym/><Comment/>"
                             "<Type><v8:Type>xs:boolean</v8:Type></Type>"
                             "</Properties></SessionParameter>" % FIXED_UUID),
    }
    for name, body in cases.items():
        fixture(name, body)

    report = SP.collect_session_parameters(FIXTURE_DIR)
    rows = {row["object_name"]: row for row in report["rows"]}
    failures = {Path(item["source_path"]).name.split(".")[0]: item["reason"]
                for item in report["files_failed"]}

    check("из фикстур отказывают только названные (пустой Name, кривой uuid)",
          set(failures) == {"БезИмени", "КривойUuid"}, failures)
    check("пустой <Name> назван причиной отказа", "Name" in failures.get("БезИмени", ""),
          failures.get("БезИмени"))
    check("кривой uuid назван причиной отказа (правило R3)",
          "uuid" in failures.get("КривойUuid", ""), failures.get("КривойUuid"))

    check("пустой блок <Type> читается состоянием absent (Q3)",
          rows["ПустойБлок"]["type_parse_state"] == SP.STATE_ABSENT and
          rows["ПустойБлок"]["type_multiplicity"] == SP.MULT_ABSENT and
          rows["ПустойБлок"]["types"] == [],
          rows.get("ПустойБлок", {}).get("type_parse_state"))
    qrow = rows["ТолькоКвалификаторы"]
    check("квалификаторы без значений: absent плюс названное предупреждение",
          qrow["type_parse_state"] == SP.STATE_ABSENT and qrow["type_qualifiers"] and
          any("квалификатор" in w for w in report["warnings"]),
          qrow["type_qualifiers"])
    urow = rows["НеизвестныйЭлемент"]
    check("содержимое вне словаря (2.4.2) даёт unknown_form, а не пустой массив",
          urow["type_parse_state"] == SP.STATE_UNKNOWN_FORM and len(urow["types"]) == 1 and
          urow["types"][0]["class"] == SP.CLASS_UNKNOWN and
          urow["types"][0]["state"] == SP.ENTRY_STATE_UNKNOWN_FORM and
          "<v8:TypeSet>" in (urow["type_raw"] or ""),
          urow["types"])
    prow = rows["НеобъявленныйПрефикс"]
    check("префикс без объявления в файле: unknown_form с причиной (2.4.4)",
          prow["types"][0]["class"] == SP.CLASS_UNKNOWN and
          prow["types"][0]["ns_uri"] is None and
          "не объявлен" in (prow["types"][0].get("reason") or ""),
          prow["types"][0])
    mrow = rows["СмешанныйТип"]
    check("смесь значений даёт partial; квалификаторы — отдельной колонкой",
          mrow["type_parse_state"] == SP.STATE_PARTIAL and
          mrow["type_multiplicity"] == SP.MULT_COMPOSITE and len(mrow["types"]) == 2 and
          mrow["types"][0]["class"] == SP.CLASS_PRIMITIVE and
          mrow["types"][1]["class"] == SP.CLASS_UNKNOWN and
          "StringQualifiers" in (mrow["type_qualifiers"] or {}),
          mrow["types"])
    check("свойство вне словаря вида (2.3) называется и не попадает в строку",
          rows["ЧужоеСвойство"]["types"][0]["class"] == SP.CLASS_PRIMITIVE and
          report["unknown_properties"].get("ObjectBelonging") == 1 and
          "ObjectBelonging" not in json.dumps(rows["ЧужоеСвойство"], ensure_ascii=False),
          report["unknown_properties"])
    check("xs-имя вне перечня не считается примитивом",
          rows["ВнеПеречняТипов"]["types"][0]["class"] == SP.CLASS_UNKNOWN,
          rows["ВнеПеречняТипов"]["types"][0])
    drow = rows["ОпределяемыйТип"]
    check("определяемый тип: класс defined_type_ref, цель не ставится (2.4.4)",
          drow["types"][0]["class"] == SP.CLASS_DEFINED_TYPE_REF and
          drow["types"][0]["state"] == SP.ENTRY_STATE_PARSED and
          "target_object_uuid" not in drow["types"][0],
          drow["types"][0])
    check("чужое пространство имён — unknown с названным URI",
          rows["ЧужойURI"]["types"][0]["class"] == SP.CLASS_UNKNOWN and
          rows["ЧужойURI"]["types"][0]["ns_uri"] == "http://example.com/other",
          rows["ЧужойURI"]["types"][0])
    check("дубликат свойства: берётся первое, факт назван предупреждением",
          rows["ДубликатСвойства"]["object_name"] == "ДубликатСвойства" and
          any("встречается в файле 2-й раз" in w for w in report["warnings"]),
          [w for w in report["warnings"] if "встречается" in w][:1])
    check("сводка называет весь словарь состояний и кратностей нулями (правило C2)",
          set(report["counts_by_state"]) ==
          {SP.STATE_PARSED, SP.STATE_PARTIAL, SP.STATE_UNKNOWN_FORM, SP.STATE_ABSENT} and
          set(report["types_multiplicity"]) ==
          {SP.MULT_ABSENT, SP.MULT_SINGLE, SP.MULT_COMPOSITE},
          report["counts_by_state"])
    problems = check_row_invariants(report["rows"])
    check("инварианты строк выполняются и на фикстурах", not problems, problems[:5])
    return report


def check_reference_rule():
    """Правило перехода и классификация — чистые функции (замер 2.5)."""
    check("правило перехода: CatalogRef.Организации → Catalog.Организации",
          SP.index_name_for_reference("CatalogRef.Организации") ==
          ("Catalog", "Catalog.Организации"))
    check("правило перехода не зависит от вида ссылки (DocumentRef — та же форма)",
          SP.index_name_for_reference("DocumentRef.Заказ") == ("Document", "Document.Заказ"))
    check("форма без суффикса Ref не считается ссылкой",
          SP.index_name_for_reference("Catalog.Организации") is None)
    check("форма Ref без имени не считается ссылкой",
          SP.index_name_for_reference("CatalogRef.") is None)
    check("пустое значение разбирается как unknown",
          SP.split_qname("")[0] is None and SP.split_qname(None)[1] is None)

    ns_map = {"cfg": SP.NS_CURRENT_CONFIG, "v8": SP.NS_V8_CORE, "xs": SP.NS_XML_SCHEMA,
              "d4p1": SP.NS_CURRENT_CONFIG}
    check("один и тот же URI под разными префиксами даёт один класс (2.4.4)",
          SP.classify_type_value("cfg:CatalogRef.Организации", ns_map)["class"] ==
          SP.classify_type_value("d4p1:CatalogRef.Организации", ns_map)["class"] ==
          SP.CLASS_OBJECT_REF)
    check("префикс без объявления даёт unknown_form, а не object_ref",
          SP.classify_type_value("zz:CatalogRef.Организации", ns_map)["class"] ==
          SP.CLASS_UNKNOWN)
    check("тип платформы вне перечня — unknown, а не primitive",
          SP.classify_type_value("v8:ValueTree", ns_map)["class"] == SP.CLASS_PRIMITIVE and
          SP.classify_type_value("v8:ЧтоТоНовое", ns_map)["class"] == SP.CLASS_UNKNOWN)
    check("класс определяется URI, а не именем префикса (чужой URI)",
          SP.classify_type_value("cfg:CatalogRef.Организации",
                                 {"cfg": "http://example.com"})["class"] == SP.CLASS_UNKNOWN)
    check("кратность выводится из числа записей (Q4)",
          [SP.multiplicity_of(n) for n in (0, 1, 2, 3)] ==
          [SP.MULT_ABSENT, SP.MULT_SINGLE, SP.MULT_COMPOSITE, SP.MULT_COMPOSITE])
    check("состояние строки: mixed ≠ unknown_form ≠ absent (Q3)",
          SP.type_row_state([]) == SP.STATE_ABSENT and
          SP.type_row_state([{"state": SP.ENTRY_STATE_PARSED}]) == SP.STATE_PARSED and
          SP.type_row_state([{"state": SP.ENTRY_STATE_UNKNOWN_FORM}]) == SP.STATE_UNKNOWN_FORM and
          SP.type_row_state([{"state": SP.ENTRY_STATE_PARSED},
                             {"state": SP.ENTRY_STATE_UNKNOWN_FORM}]) == SP.STATE_PARTIAL)


def check_index_resolution():
    """Разрешение ссылок строками индекса состава (офлайн: без таблицы)."""
    fixture("СсылкаЕсть", props("СсылкаЕсть",
                               type_block="<Type><v8:Type>cfg:CatalogRef.Организации"
                                          "</v8:Type></Type>"))
    fixture("СсылкиНет", props("СсылкиНет",
                              type_block="<Type><v8:Type>cfg:CatalogRef.ТакойНет"
                                         "</v8:Type></Type>"))
    fixture("ИндексаНет", props("ИндексаНет",
                               type_block="<Type><v8:Type>xs:boolean</v8:Type></Type>"))
    index_rows = [
        {"object_type": SP.INDEX_OBJECT_TYPE, "object_name": "SessionParameter.СсылкаЕсть",
         "uuid": FIXED_UUID, "depth": "0", "parent_name": ""},
        {"object_type": SP.INDEX_OBJECT_TYPE, "object_name": "SessionParameter.ТолькоИндекс",
         "uuid": OTHER_UUID, "depth": "0", "parent_name": ""},
        {"object_type": SP.INDEX_OBJECT_TYPE, "object_name": "SessionParameter.СсылкиНет",
         "uuid": FIXED_UUID, "depth": "0", "parent_name": ""},
        {"object_type": "Catalog", "object_name": "Catalog.Организации",
         "uuid": "aaaaaaaa-0000-0000-0000-000000000000", "depth": "0", "parent_name": ""},
    ]
    report = SP.collect_session_parameters(FIXTURE_DIR, index_rows=index_rows)
    rows = {row["object_name"]: row for row in report["rows"]}

    entry = rows["СсылкаЕсть"]["types"][0]
    check("разрешённая ссылка получает ключи цели из индекса (2.5)",
          entry["resolved"] is True and
          entry["target_object_uuid"] == "aaaaaaaa-0000-0000-0000-000000000000" and
          entry["target_full_name"] == "Catalog.Организации" and
          entry["target_object_type"] == "Catalog",
          entry)
    missing = rows["СсылкиНет"]["types"][0]
    check("неразрешённая ссылка остаётся без ключей цели (прецедент D3)",
          missing["resolved"] is False and "target_object_uuid" not in missing and
          "target_full_name" not in missing,
          missing)
    check("разрешённых ссылок ровно столько, сколько найдено целей",
          report["types_resolved"] == 1, report["types_resolved"])
    check("файл без записи индекса называется file_only",
          any("ИндексаНет" in item for item in report["file_only"]), report["file_only"])
    check("запись индекса без файла называется index_only поимённо",
          report["index_only"] == ["SessionParameter.ТолькоИндекс"], report["index_only"])

    single = SP.read_registration_file(
        FIXTURE_DIR / SP.DIR_NAME / "СсылкаЕсть.xml",
        index_by_name=SP.index_rows_by_name(index_rows))
    check("сверка файла с индексом называется matched",
          single["index_check"]["state"] == "matched", single["index_check"])
    other_rows = [dict(row, uuid="cccccccc-2222-2222-2222-222222222222")
                  for row in index_rows]
    mismatch = SP.read_registration_file(
        FIXTURE_DIR / SP.DIR_NAME / "СсылкаЕсть.xml",
        index_by_name=SP.index_rows_by_name(other_rows))
    check("расхождение uuid файла и индекса называется uuid_mismatch, а не замалчивается",
          mismatch["index_check"]["state"] == "uuid_mismatch" and
          any("не совпадает" in w for w in mismatch["warnings"]),
          mismatch["index_check"])
    check("цель ссылки ищется по всем строкам индекса, а сверка вида — по своим",
          len(SP.index_rows_by_name(index_rows)) == 4 and
          len(SP.kind_index_rows(index_rows)) == 3,
          (len(SP.index_rows_by_name(index_rows)), len(SP.kind_index_rows(index_rows))))
    problems = check_row_invariants(report["rows"])
    check("инварианты строк выполняются после разрешения ссылок", not problems, problems[:5])


def main():
    print("=== шаг П2 узла V48: офлайн-проверка разбора параметров сеанса ===")
    print("модуль: src/configuration_session_parameters.py; выгрузки: %s" % ", ".join(DUMPS))
    print("словарь свойств вида замкнут: %d (%s)"
          % (SP.SESSION_PARAMETER_PROPERTY_COUNT, ", ".join(SP.XML_PROPERTY_NAMES)))
    print("словарь записи types: %s (+ %s — только у разрешённой ссылки)"
          % (", ".join(SP.TYPE_ENTRY_KEYS), ", ".join(SP.TYPE_ENTRY_TARGET_KEYS)))
    print()
    check_corpus()
    print()
    check_fixtures()
    print()
    check_reference_rule()
    print()
    check_index_resolution()
    print()
    failed = [label for ok, label, _ in RESULTS if not ok]
    print("=" * 72)
    print("ПРОВЕРЕНО: %d, ПРОВАЛЕНО: %d" % (len(RESULTS), len(failed)))
    for label in failed:
        print("  провалено: " + label)
    print("РЕЗУЛЬТАТ:", "расхождений нет" if not failed else "есть расхождения")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
