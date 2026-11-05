#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П3 узла V57: офлайн-проверка парсера круга `FunctionalOptionsParameters` (БД не трогает).

Зачем. П4 (писатель) и П5 (стадия) начинают писать код только когда разбор круга назван
числами и состояниями. Парсер проверяется на четырёх рядах доказательств.

1. Синтетические fixtures — случаи, которых в эталонных выгрузках нет (замеры 2.1…2.2
   плана дают один наблюдённый словарь: `<Use>` непустой у 14 файлов из 14, элемент только
   `<xr:Item xsi:type="xr:MDObjectRef">` в 34/34, цели только `exact`, формы только
   `dimension` 30 и `object` 4, 2 класса цели). Проверяются состояния, которых корпус не
   давал: пустой `<Use/>` и отсутствующий тег `Use` (M3 и `absent` с виновником), пустой
   текст элемента (`empty_value`, M6), `prefix_only`, `unresolved`, формы `attribute` /
   `register_resource` / `tabular_section` / `other`, элемент без `xsi:type` и с иным
   `xsi:type` (M6), элемент чужого тега (M7 — `item_tag` остаётся именем), повтор цели,
   тег свойства вне словаря (Q1, вариант A), значение свойства вне измеренной формы,
   пустой `Synonym` (пустой тег — НЕ виновник `absent`), битый XML, пустой `Name`,
   не-uuid, корень чужого вида, расхождения с индексом состава (`file_only`, `index_only`,
   `uuid_mismatch`), вид-сосед `FunctionalOption` в индексе (в круг не попадает — раздел
   1.2 плана), подкаталог и файл не-XML в каталоге вида (сторож примитивности, замер 1.2),
   отсутствие каталога вида и непереданный индекс состава.

2. Ожидания фикстур заданы ТАБЛИЦЕЙ (`fixture_specs()`), а не числами в проверках: из
   таблицы выводятся и ожидания по каждой строке (`check_fixture_row`), и агрегаты
   `counts_by_*` (`expected_fixture_counts`). Числа сводки, не совпавшие с суммой по
   таблице, — провал, а не расхождение, которое нужно «поправить в ожидании».

3. Инварианты строк — предикаты, которые кладёт схема (`functional_option_parameters_*`,
   `functional_option_parameter_targets_*`), прогоняются по строкам разбора ДО открытия
   базы (`check_row`). Сторож проверяется и на собственных ошибках: намеренно
   противоречивые строки обязаны быть названы, иначе «ноль нарушений» означал бы, что
   проверяющая функция ничего не проверяет. Плюс словарь ключей строк сверяется со списком
   колонок `functional_option_parameters` / `functional_option_parameter_targets` из текста
   `migrate_v57_functional_options_parameters.sql` (БД не открывается), а закрытые словари
   состояний модуля — со списками `IN (…)` тех же CHECK'ов.

4. Четыре эталонные выгрузки — ожидаемые числа берутся из П0 (`_v57_p0_probe.py`,
   разделы 1–2 плана): файлы 2/0/5/7 (всего 14), цели 2/0/6/26 (всего 34, максимум 20 на
   файл у параметра `Организация` в BP3), состояния `exact` 34/34, формы `dimension` 30 и
   `object` 4, классы цели `InformationRegister` 30 и `Catalog` 4, перечни непустые у 14
   файлов из 14, расхождений с индексом — ноль. У `KomMag` каталога вида нет ни файлом, ни
   строкой индекса — ответ обязан быть пустым кругом с наблюдением `directory_missing`, а
   не отказом. Расхождение с П0 — сигнал о том, что парсер или замер разошлись; цифру
   плана она не меняет, но обязана быть названа.

Ничего в БД зонд не пишет и ничего не чинит молча: провал — строка отчёта и ненулевой код
выхода.
"""
from __future__ import annotations

import re
import sys
import tempfile
import uuid as uuid_lib
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
# Тот же порядок, что у офлайн-зондов V49…V56: корень проекта и каталог `src`
# (модули слоя импортируются как верхние имена, а не как `src.`).
for _path in (str(ROOT), str(ROOT / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# Отчёт печатается кириллицей со стрелками состояний: консоль Windows по умолчанию
# cp1251, и печать падала бы на коде страницы, а не на разборе.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

import configuration_functional_options_parameters as fop  # noqa: E402
from config_dump_info_parser import find_config_dump_info, parse_config_dump_info  # noqa: E402
from configuration_functional_options_parameters import (  # noqa: E402
    ADDRESS_FORM_ATTRIBUTE, ADDRESS_FORM_DIMENSION, ADDRESS_FORM_EMPTY,
    ADDRESS_FORM_OBJECT, ADDRESS_FORM_OTHER, ADDRESS_FORM_REGISTER_RESOURCE,
    ADDRESS_FORM_TABULAR_SECTION, DIR_NAME, ITEM_TYPE_STATE_ABSENT, ITEM_TYPE_STATE_OTHER,
    ITEM_TYPE_STATE_REF, MAX_TARGETS_KEY, PARAMETER_LINK_KEY, PARAMETER_UUID_KEY,
    PROPS_ABSENT, PROPS_ALL_KNOWN, PROPS_UNKNOWN_TAG, PROPS_UNKNOWN_VALUE,
    TARGET_EMPTY_VALUE, TARGET_EXACT, TARGET_PREFIX_ONLY, TARGET_UNRESOLVED,
    USE_EMPTY, USE_WITH, check_row, collect_functional_options_parameters,
    read_registration_file, target_address_form, target_object_type,
)



# ─── ожидания по эталонным выгрузкам (замеры П0, разделы 1–2 плана) ────────────
# Нули по всем состояниям задаются шаблоном, а не подразумеваются: «состояния не было» и
# «состояние не считали» — разные ответы (правило C2).
_ZEROS_ROW = {"props_all_known": 0, "props_unknown_value": 0, "props_unknown_tag": 0,
              "props_absent": 0, "use_with": 0, "use_empty": 0}
_ZEROS_TARGET = {"exact": 0, "prefix_only": 0, "unresolved": 0, "empty_value": 0,
                 "form_object": 0, "form_dimension": 0, "form_register_resource": 0,
                 "form_attribute": 0, "form_tabular_section": 0, "form_other": 0,
                 "form_empty": 0, "item_md_object_ref": 0, "item_other_form": 0,
                 "item_absent": 0}


def expected(**overrides) -> Dict:
    """Ожидания выгрузки: нули по всем состояниям плюс названные значения."""
    base = {"files": 0, "targets": 0, "distinct": 0, "max_targets": 0, "kinds": {},
            "observations": [], "discrepancies": 0}
    base.update(_ZEROS_ROW)
    base.update(_ZEROS_TARGET)
    base.update(overrides)
    return base


EXPECTED = {
    # MinCfg — 2 файла, по одной цели у каждого (замеры 1.1, 2.1)
    "MinCfg": expected(files=2, targets=2, distinct=2, max_targets=1, props_all_known=2,
                       use_with=2, exact=2, form_object=1, form_dimension=1,
                       item_md_object_ref=2,
                       kinds={"Catalog": 1, "InformationRegister": 1}),
    # KomMag — каталога вида нет ни файлом, ни строкой индекса (замер 1.1): ответ обязан
    # быть пустым кругом с наблюдением `directory_missing`, а не отказом (Q9, вариант A).
    "KomMag": expected(observations=["directory_missing"]),
    "BGU2": expected(files=5, targets=6, distinct=6, max_targets=2, props_all_known=5,
                     use_with=5, exact=6, form_object=1, form_dimension=5,
                     item_md_object_ref=6,
                     kinds={"Catalog": 1, "InformationRegister": 5}),
    "BP3": expected(files=7, targets=26, distinct=26, max_targets=20, props_all_known=7,
                    use_with=7, exact=26, form_object=2, form_dimension=24,
                    item_md_object_ref=26,
                    kinds={"Catalog": 2, "InformationRegister": 24}),
}

# Итоги по корпусу (замеры 1.1, 2.1): 14 файлов, 34 цели, 30 срезов измерения и 4 цели на
# сам объект, 2 класса цели, максимум 20 целей на файл (параметр `Организация` в BP3).
# Сумма классов цели равна числу целей — это и есть проверка полноты словаря `kinds`.
# `max_targets` суммой не является (это максимум по выгрузке), поэтому проверяется отдельно.
CORPUS_TOTALS = {"files": 14, "targets": 34, "distinct": 34, "exact": 34,
                 "form_dimension": 30, "form_object": 4, "use_with": 14, "use_empty": 0,
                 "props_all_known": 14}
CORPUS_MAX_TARGETS = 20
CORPUS_KINDS = {"Catalog": 4, "InformationRegister": 30}

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DDL_FILE = ROOT / "migrate_v57_functional_options_parameters.sql"
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

FAILURES: list = []
REPORT: list = []
CHECKS_TOTAL = 0


def emit(text: str = "") -> None:
    REPORT.append(text)


def check(name: str, ok: bool, detail: str = "") -> bool:
    """Одна строка отчёта. Счётчик нужен итогу: «проверок N, отказов 0» — это мера того,
    что узел что-то проверял, а не прошёл молча."""
    global CHECKS_TOTAL
    CHECKS_TOTAL += 1
    emit(("  OK   " if ok else "  FAIL ") + name + ((" — " + detail) if detail else ""))
    if not ok:
        FAILURES.append((name, detail))
    return ok


def row_by(rows: List[Dict], name: str) -> Dict:
    for row in rows:
        if row["object_name"] == name:
            return row
    return {}


def targets_of(targets: List[Dict], parameter_index_name: str) -> List[Dict]:
    """Строки применения одного параметра — по ключу строки вида, а не по uuid.

    Ключом служит индексное имя `FunctionalOptionsParameter.<Имя>`: uuid и имена вида
    совпадают у BGU2 и BP3 (замер 1.3 — 5 общих uuid), поэтому связка по uuid давала бы
    смешение параметров разных выгрузок.
    """
    return [target for target in targets
            if target[PARAMETER_LINK_KEY] == parameter_index_name]


def failure_reason(files_failed: List[Dict], stem: str) -> str:
    """Причина отказа файла по имени файла без расширения (пустая строка — её нет)."""
    for item in files_failed:
        if Path(item["source_path"]).stem == stem:
            return item["reason"] or ""
    return ""


# ─── синтетические файлы круга ─────────────────────────────────────────────────
# Пространства имён — те же, что у файла выгрузки вида (замер: `MinCfg/
# FunctionalOptionsParameters/ПараметрФункциональныхОпций1.xml`): разбор снимает префиксы
# (`_local`), поэтому фикстура обязана давать именованные формы, а не «удобные» — иначе
# проверялся бы разбор своего текста.
HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
        'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
        'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xr="http://v8.1c.ru/8.3/xcf/readable">\n')


def fop_file(obj_uuid: str, body: str,
             root_tag: str = "FunctionalOptionsParameter") -> str:
    return (HEAD + f'<{root_tag} uuid="{obj_uuid}">\n'
            f"\t<Properties>\n{body}\t</Properties>\n"
            f"</{root_tag}>\n</MetaDataObject>\n")


def name_tag(name: str) -> str:
    return f"\t\t\t<Name>{name}</Name>\n"


def synonym_tag(text: str) -> str:
    return (f"\t\t\t<Synonym>\n\t\t\t\t<v8:item>\n\t\t\t\t\t<v8:lang>ru</v8:lang>\n"
            f"\t\t\t\t\t<v8:content>{text}</v8:content>\n\t\t\t\t</v8:item>\n"
            f"\t\t\t</Synonym>\n")


def comment_tag(text: str) -> str:
    return f"\t\t\t<Comment>{text}</Comment>\n"


def use_tag(items: str) -> str:
    """Блок `<Use>`: None — тега нет, "" — пустой блок, иначе — перечень элементов."""
    if items is None:
        return ""
    if not items:
        return "\t\t\t<Use/>\n"
    return f"\t\t\t<Use>\n{items}\t\t\t</Use>\n"


def item_tag(address: str, tag: str = "xr:Item",
             type_attr: str = 'xsi:type="xr:MDObjectRef"') -> str:
    attribute = " " + type_attr if type_attr else ""
    return f"\t\t\t\t<{tag}{attribute}>{address}</{tag}>\n"


# ─── адреса целей фикстур ──────────────────────────────────────────────────────
# Формы адресов берутся из реальной структуры записей индекса состава (замер по
# `ConfigDumpInfo.xml` BP3 даёт `AccountingRegister.Хозрасчетный.Resource.Сумма`,
# `BusinessProcess.X.TabularSection.Y`, `….TabularSection.Y.Attribute.Z`, `….Dimension.…`),
# а не выдумываются: иначе проверялся бы разбор удобного теста, а не разбора выгрузки.
CATALOG_TARGET = "Catalog.Товары"
REGISTER_PARENT = "InformationRegister.НастройкиУчетаНДС"
DIMENSION_TARGET = REGISTER_PARENT + ".Dimension.Организация"
PREFIX_PARENT = "InformationRegister.ПрочиеНастройки"
PREFIX_TARGET = PREFIX_PARENT + ".Dimension.Отсутствует"
ATTRIBUTE_TARGET = "Document.Реализация.Attribute.Контракт"
RESOURCE_TARGET = "AccountingRegister.Хозрасчетный.Resource.Сумма"
TABULAR_TARGET = "Catalog.Товары.TabularSection.Цены"
TS_ATTRIBUTE_TARGET = TABULAR_TARGET + ".Attribute.Цена"
UNRESOLVED_TARGET = "Catalog.ТакогоНет"
OTHER_PREFIX_TARGET = "Catalog.Товары.ЧтоТо"

ONE_ITEM = item_tag(CATALOG_TARGET)
TWO_ITEMS = item_tag(CATALOG_TARGET) + item_tag(DIMENSION_TARGET)


def full_body(name: str, comment: str = "", extra: str = "",
              use: str = ONE_ITEM, synonym: str = "") -> str:
    """Тело файла с полным словарём свойств (позиции 1–4 замера 2 плана).

    Порядок тегов — порядок файла выгрузки (`Name`, `Synonym`, `Comment`, `Use`): пропуск
    позиции в словаре свойств означал бы молчаливую потерю свойства. `use=None` — тега
    `Use` нет, `use=""` — пустой блок `<Use/>`, иначе — строки перечня (`item_tag`).
    Перечень элементов передаётся только параметром `use`: второй параметр с элементами в
    сигнатуре давал бы файл, который разбирается не так, как задумано в таблице ожиданий.
    """
    return (name_tag(name) + synonym_tag(synonym or name)
            + comment_tag(comment or name) + extra + use_tag(use))


def dump_index(entries) -> str:
    """Файл индекса состава фиктивной выгрузки (форма замера V33)."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<ConfigDumpInfo xmlns="http://v8.1c.ru/8.3/xcf/dumpinfo">', "\t<ConfigVersions>"]
    for name, obj_id in entries:
        # configVersion — не идентификатор объекта, а версия метаданий: форма замера V33 —
        # 40 шестнадцатеричных символов, иначе индекс читался бы выдумкой, а не замером.
        version = uuid_lib.uuid4().hex + uuid_lib.uuid4().hex[:8]
        lines.append(f'\t\t<Metadata name="{name}" id="{obj_id}" configVersion="{version}"/>')
    lines += ["\t</ConfigVersions>", "</ConfigDumpInfo>"]
    return "\n".join(lines) + "\n"


def load_index_rows(root: Path) -> List[Dict]:
    """Строки индекса состава фиктивной выгрузки (тот же разбор, что у стадии П5)."""
    path = find_config_dump_info(str(root))
    if path is None:
        raise SystemExit("фикстура: ConfigDumpInfo.xml не создан")
    parsed = parse_config_dump_info(str(path))
    if not parsed["success"]:
        raise SystemExit("фикстура: индекс состава не разобран: %s" % parsed["error"])
    return parsed["objects"]


# ─── круг фиктивных выгрузок: по одному файлу на состояние-исключение ──────────
# Ожидания задаются ТАБЛИЦЕЙ: из неё выводятся и проверки по каждой строке, и агрегаты
# `counts_by_*`. Правка ожидания тогда же правит и агрегат — расхождение сводки с суммой
# по таблице остаётся провалом, а не числом, которое «подгоняют».
FAIL = "fail"          # файл обязан быть назван отказом с причиной, а не строкой разбора


def t(address: str, form: str, state: str,
      type_state: str = ITEM_TYPE_STATE_REF) -> Tuple[str, str, str, str]:
    """Ожидаемая строка применения: адрес, форма, состояние, состояние `xsi:type`."""
    return (address, form, state, type_state)


def spec(name: str, xml: str, targets: List[Tuple[str, str, str, str]],
         props: str = PROPS_ALL_KNOWN, unknown: List[str] = None,
         use: str = USE_WITH, index: str = "matched", fail_reason: str = "") -> Dict:
    """Ожидание одного файла: строка вида, её применение и состояние сверки с индексом."""
    return {"name": name, "xml": xml, "targets": targets, "props": props,
            "unknown": unknown, "use": use, "index": index, "fail_reason": fail_reason}


def fixture_specs() -> Dict[str, Dict]:
    """Спецификации фиктур и их uuid.

    uuid нужен и для файла, и для записей индекса состава, поэтому он задаётся одним
    перечнем по порядку ключей: две независимые генерации дали бы файлам и индексу
    разные идентификаторы, и `uuid_mismatch` был бы фальсификацией.
    """
    uuids = {key: "a0000000-0000-0000-0000-%012d" % number
             for number, key in enumerate(
                 ["typical", "unknown_property", "comment_structure", "empty_synonym",
                  "no_use_tag", "use_empty_tag", "empty_item", "prefix_dimension",
                  "unresolved_object", "attribute_slice", "resource_slice",
                  "tabular_section", "ts_attribute", "other_prefix", "item_no_type",
                  "item_other_type", "foreign_item_tag", "duplicate_target",
                  "file_only", "uuid_mismatch", "broken_xml", "empty_name",
                  "bad_uuid", "foreign_root"], start=1)}

    def uid(key: str) -> str:
        return uuids[key]

    specs: Dict[str, Dict] = {}

    # 1. Полный файл словаря свойств: две цели перечня в порядке файла — цель самого
    #    объекта (`object`) и срез измерения (`dimension`); обе разрешаются индексом
    #    (наблюдённая форма 34 целей из 34).
    specs["typical"] = spec("Типичная",
                            fop_file(uid("typical"), full_body("Типичная",
                                                               use=TWO_ITEMS)),
                            [t(CATALOG_TARGET, ADDRESS_FORM_OBJECT, TARGET_EXACT),
                             t(DIMENSION_TARGET, ADDRESS_FORM_DIMENSION, TARGET_EXACT)])

    # 2. Тег свойства вне словаря (замер 2: ровно 4 тега в 14/14 файлов, XSD вида нет —
    #    замер 1.5): состояние `unknown_tag` с именем виновником (Q1, вариант A);
    #    разобранное значение при этом в строку не пишется.
    specs["unknown_property"] = spec(
        "НеизвестноеСвойство",
        fop_file(uid("unknown_property"), full_body(
            "НеизвестноеСвойство",
            extra="\t\t\t<UnknownProperty>текст</UnknownProperty>\n", use=TWO_ITEMS)),
        [t(CATALOG_TARGET, ADDRESS_FORM_OBJECT, TARGET_EXACT),
         t(DIMENSION_TARGET, ADDRESS_FORM_DIMENSION, TARGET_EXACT)],
        props=PROPS_UNKNOWN_TAG, unknown=["UnknownProperty"])

    # 3. Значение свойства формы, которой корпус не давал: `Comment` несёт языковой блок
    #    вместо текста (замер 2 плана даёт scalar в 2 файлах из 14 и пустой текст в 12) —
    #    состояние `unknown_value` с виновником, колонка `comment` остаётся NULL. Тело
    #    собирается явно, а не через `full_body` с `extra`: дублирующий тег `Comment`
    #    парсер пропускает как повтор, и состояние не возникло бы.
    comment_block = ("\t\t\t<Comment>\n\t\t\t\t<v8:item>\n"
                     "\t\t\t\t\t<v8:lang>ru</v8:lang>\n"
                     "\t\t\t\t\t<v8:content>текст</v8:content>\n"
                     "\t\t\t\t</v8:item>\n\t\t\t</Comment>\n")
    specs["comment_structure"] = spec(
        "СтруктураКомментария",
        fop_file(uid("comment_structure"),
                 name_tag("СтруктураКомментария")
                 + synonym_tag("СтруктураКомментария") + comment_block
                 + use_tag(ONE_ITEM)),
        [t(CATALOG_TARGET, ADDRESS_FORM_OBJECT, TARGET_EXACT)],
        props=PROPS_UNKNOWN_VALUE, unknown=["Comment"])


    # 4. Пустой тег `Synonym` — НЕ виновник `absent`: отсутствующий тег назвал бы себя
    #    состоянием, пустой таковым не является (CHECK требует перечня виновников только
    #    при absent/unknown_*). Состояние свойств остаётся `all_known`, колонка — NULL.
    specs["empty_synonym"] = spec(
        "ПустойСиноним",
        fop_file(uid("empty_synonym"),
                 name_tag("ПустойСиноним") + "\t\t\t<Synonym/>\n"
                 + comment_tag("ПустойСиноним") + use_tag(ONE_ITEM)),
        [t(CATALOG_TARGET, ADDRESS_FORM_OBJECT, TARGET_EXACT)])

    # 5. Тега `Use` в файле нет — `absent` с виновником `Use` (CHECK
    #    `..._properties_state_matches_unknown`) и `empty_content` перечня: «тега нет» и
    #    «перечень пуст» различаются диагностикой `use_declared`, но не состоянием
    #    перечня (M3).
    specs["no_use_tag"] = spec("БезUse", fop_file(uid("no_use_tag"),
                                                  full_body("БезUse", use=None)), [],
                               props=PROPS_ABSENT, unknown=["Use"], use=USE_EMPTY)

    # 6. Пустой блок `<Use/>` — состояние `empty_content` строки, а не пустая строка
    #    таблицы (M3); состояние свойств при этом `all_known`: все измеренные теги на месте.
    specs["use_empty_tag"] = spec("ПустойUse", fop_file(uid("use_empty_tag"),
                                                        full_body("ПустойUse", use="")),
                                  [], use=USE_EMPTY)

    # 7. Пустой ТЕКСТ элемента перечня — строка применения с состоянием `empty_value`
    #    (M6): строку ключит `ordinal`, CHECK `..._targets_name_matches_resolve_state`
    #    описывает это состояние; пустой адрес держится пустой формой и пустым видом цели.
    specs["empty_item"] = spec(
        "ПустойЭлемент",
        fop_file(uid("empty_item"), full_body("ПустойЭлемент", use=item_tag(""))),
        [t("", ADDRESS_FORM_EMPTY, TARGET_EMPTY_VALUE)])

    # 8. Срез измерения, записи которого в индексе нет, но есть запись регистра —
    #    `prefix_only`: остаток адреса называется, uuid цели отсутствует (строки индекса у
    #    самой цели нет), идентификатор берётся из строки-префикса.
    specs["prefix_dimension"] = spec(
        "ПрефиксИзмерения",
        fop_file(uid("prefix_dimension"),
                 full_body("ПрефиксИзмерения", use=item_tag(PREFIX_TARGET))),
        [t(PREFIX_TARGET, ADDRESS_FORM_DIMENSION, TARGET_PREFIX_ONLY)])

    # 9. Адреса нет ни у записи, ни у префикса — `unresolved` (достижимо и при незагруженном
    #    индексе, Q6); остатком называется весь адрес.
    specs["unresolved_object"] = spec(
        "НеразрешённаяЦель",
        fop_file(uid("unresolved_object"),
                 full_body("НеразрешённаяЦель", use=item_tag(UNRESOLVED_TARGET))),
        [t(UNRESOLVED_TARGET, ADDRESS_FORM_OBJECT, TARGET_UNRESOLVED)])

    # 10–13. Формы срезов, которых корпус не давал, но которые допускает модель 1С
    #     (замер 2.1 плана: `dimension` 30 и `object` 4 — весь наблюдённый словарь).
    #     Срез реквизита, разреза регистра, табличной части — разные носители значения
    #     параметра, и без колонки формы они стали бы одним свойством (M5, вариант C
    #     отклонён Q1).
    specs["attribute_slice"] = spec(
        "СрезРеквизита",
        fop_file(uid("attribute_slice"),
                 full_body("СрезРеквизита", use=item_tag(ATTRIBUTE_TARGET))),
        [t(ATTRIBUTE_TARGET, ADDRESS_FORM_ATTRIBUTE, TARGET_EXACT)])

    specs["resource_slice"] = spec(
        "СрезРесурса",
        fop_file(uid("resource_slice"),
                 full_body("СрезРесурса", use=item_tag(RESOURCE_TARGET))),
        [t(RESOURCE_TARGET, ADDRESS_FORM_REGISTER_RESOURCE, TARGET_EXACT)])

    specs["tabular_section"] = spec(
        "СрезТабличнойЧасти",
        fop_file(uid("tabular_section"),
                 full_body("СрезТабличнойЧасти", use=item_tag(TABULAR_TARGET))),
        [t(TABULAR_TARGET, ADDRESS_FORM_TABULAR_SECTION, TARGET_EXACT)])

    # 13. Адрес реквизита табличной части содержит оба маркера. Порядок проверок парсера
    #     (`.Dimension.`, `.Resource.`, `.Attribute.`, `.TabularSection.`) даёт форму среза
    #     реквизита; CHECK `..._targets_form_matches_name` веткой среза считает оба
    #     значения, поэтому выбор порядка — соглашение разбора, а не ограничение схемы.
    #     Соглашение называется здесь, потому что читатель карточки судит по нему.
    specs["ts_attribute"] = spec(
        "РеквизитТабличнойЧасти",
        fop_file(uid("ts_attribute"),
                 full_body("РеквизитТабличнойЧасти", use=item_tag(TS_ATTRIBUTE_TARGET))),
        [t(TS_ATTRIBUTE_TARGET, ADDRESS_FORM_ATTRIBUTE, TARGET_EXACT)])

    # 14. Прочий непустой адрес (не срез и не два сегмента) — форма `other`, граница
    #     разбора (корпус такой цели не давал); разрешается префиксом.
    specs["other_prefix"] = spec(
        "ПрочийАдрес",
        fop_file(uid("other_prefix"),
                 full_body("ПрочийАдрес", use=item_tag(OTHER_PREFIX_TARGET))),
        [t(OTHER_PREFIX_TARGET, ADDRESS_FORM_OTHER, TARGET_PREFIX_ONLY)])


    # 15–17. Форма элемента перечня (M6, M7). Корпус даёт `<xr:Item
    #      xsi:type="xr:MDObjectRef">` в 34/34; отсутствие атрибута, иное значение и чужой
    #      тег называются состояниями и именами, а не подстановкой измеренной формы:
    #      колонки `item_tag`/`item_type_attr` заведены ровно для того, чтобы незнакомая
    #      форма оставалась своей формой (Q7, вариант A).
    specs["item_no_type"] = spec(
        "ЭлементБезТипа",
        fop_file(uid("item_no_type"),
                 full_body("ЭлементБезТипа", use=item_tag(CATALOG_TARGET, type_attr=""))),
        [t(CATALOG_TARGET, ADDRESS_FORM_OBJECT, TARGET_EXACT, ITEM_TYPE_STATE_ABSENT)])

    specs["item_other_type"] = spec(
        "ЭлементЧужогоТипа",
        fop_file(uid("item_other_type"),
                 full_body("ЭлементЧужогоТипа",
                           use=item_tag(CATALOG_TARGET,
                                        type_attr='xsi:type="xr:OtherRef"'))),
        [t(CATALOG_TARGET, ADDRESS_FORM_OBJECT, TARGET_EXACT, ITEM_TYPE_STATE_OTHER)])

    specs["foreign_item_tag"] = spec(
        "ЭлементЧужогоТега",
        fop_file(uid("foreign_item_tag"),
                 full_body("ЭлементЧужогоТега",
                           use=item_tag(CATALOG_TARGET, tag="xr:Object"))),
        [t(CATALOG_TARGET, ADDRESS_FORM_OBJECT, TARGET_EXACT)])

    # 18. Повтор цели внутри перечня: дедупликации нет, строки остаются обе (порядок —
    #    `ordinal`), повтор называется диагностикой (замер 2.1 дублей не нашёл).
    specs["duplicate_target"] = spec(
        "ПовторЦели",
        fop_file(uid("duplicate_target"),
                 full_body("ПовторЦели", use=ONE_ITEM + ONE_ITEM)),
        [t(CATALOG_TARGET, ADDRESS_FORM_OBJECT, TARGET_EXACT),
         t(CATALOG_TARGET, ADDRESS_FORM_OBJECT, TARGET_EXACT)])

    # 19–20. Расхождения двух ног круга: файл без записи индекса и несовпадение uuid.
    #     Оба называются поимённо, а не числом (`CIRCLE_DISCREPANCIES` узла).
    specs["file_only"] = spec("ТолькоФайл", fop_file(uid("file_only"),
                                                     full_body("ТолькоФайл")),
                              [t(CATALOG_TARGET, ADDRESS_FORM_OBJECT, TARGET_EXACT)],
                              index="file_only")

    specs["uuid_mismatch"] = spec("НесовпадениеUUID",
                                  fop_file(uid("uuid_mismatch"),
                                           full_body("НесовпадениеUUID")),
                                  [t(CATALOG_TARGET, ADDRESS_FORM_OBJECT, TARGET_EXACT)],
                                  index="uuid_mismatch")

    # 21–24. Отказы файла — не состояние строки, а причина: битый XML, пустой `Name`
    #     (строку нечем ключить), не-uuid корня (правило R3), корень чужого вида. Файл при
    #     этом остаётся файлом круга: назвать его «записью индекса без файла» нельзя.
    specs["broken_xml"] = spec(
        "БитыйXML", HEAD + '<FunctionalOptionsParameter uuid="%s">\n' % uid("broken_xml"),
        [], props=FAIL, fail_reason="XML не разобран")

    specs["empty_name"] = spec(
        "ПустоеИмя",
        fop_file(uid("empty_name"),
                 "\t\t\t<Name/>\n" + synonym_tag("ПустоеИмя") + use_tag(ONE_ITEM)),
        [], props=FAIL, fail_reason="<Name>")

    specs["bad_uuid"] = spec(
        "КривойUUID", fop_file("не-uuid", full_body("КривойUUID")),
        [], props=FAIL, fail_reason="не является uuid")

    specs["foreign_root"] = spec(
        "ЧужойКорень", fop_file(uid("foreign_root"), full_body("ЧужойКорень"),
                                root_tag="FunctionalOption"),
        [], props=FAIL, fail_reason="нет элемента <FunctionalOptionsParameter>")

    for key, entry in specs.items():
        # uuid держится в спецификации отдельно: он нужен и тексту файла, и записи индекса
        # состава; две независимые генерации сделали бы `uuid_mismatch` фальсификацией.
        entry["uuid"] = uid(key)
    return specs



def build_fixtures(root: Path) -> Dict[str, Dict]:
    """Файлы фиктур в каталоге вида плюс артефакты, которых у вида быть не должно."""
    directory = root / DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    fixtures = fixture_specs()
    for entry in fixtures.values():
        # Имя файла без расширения равно `Name`: так устроен круг по замеру 1.1 (14
        # совпадений имени файла с записью индекса), и иначе сверка называла бы
        # `file_only` там, где её не проверяют.
        (directory / (entry["name"] + ".xml")).write_text(entry["xml"], encoding="utf-8")
    # Сторож примитивности круга (замер 1.2: плоский каталог без `Forms/`, `Templates/`,
    # `Ext/`, `.bsl`): подкаталог и файл не-XML обязаны назваться наблюдениями. Не-XML
    # кладётся и внутрь подкаталога — иначе он попал бы в круг как файл регистрации.
    (directory / "Forms").mkdir(exist_ok=True)
    (directory / "Forms" / "Заметка.txt").write_text("не XML\n", encoding="utf-8")
    (directory / "Модуль.bsl").write_text("// у вида модуля нет\n", encoding="utf-8")
    return fixtures


def fixture_index_rows(fixtures: Dict[str, Dict]) -> List[Tuple[str, str]]:
    """Записи индекса состава фиктивной выгрузки (вторая нога круга)."""
    index: List[Tuple[str, str]] = []
    for key, entry in fixtures.items():
        if key in ("file_only", "uuid_mismatch"):
            continue            # файл без записи индекса и запись с другим uuid — ниже
        index.append((fop.index_object_name(entry["name"]), entry["uuid"]))
    # запись индекса без файла:
    index.append(("FunctionalOptionsParameter.ИндексБезФайла",
                  "a0000000-0000-0000-0000-0000000000ee"))
    # uuid строки индекса другой, чем в файле:
    index.append(("FunctionalOptionsParameter.НесовпадениеUUID",
                  "a0000000-0000-0000-0000-0000000000ef"))
    # Вид-сосед позиции 2.11 (узел V56): в круг вида попасть не должен — сравнение ведётся
    # точным `object_type`, а не началом имени (раздел 1.2 плана).
    index.append(("FunctionalOption.ОпцияСоседа",
                  "b0000000-0000-0000-0000-0000000000f0"))
    # Цели перечня — объекты ДРУГИХ видов метаданных; псевдозапись среза `.Dimension.`
    # индекс содержит (замер 2.1: так разрешаются 30 целей из 34), а срезы `.Resource.` и
    # `.TabularSection.` — содержит как отдельные объекты вида.
    index += [(CATALOG_TARGET, "b0000000-0000-0000-0000-0000000000a1"),
              (REGISTER_PARENT, "b0000000-0000-0000-0000-0000000000a2"),
              (DIMENSION_TARGET, "b0000000-0000-0000-0000-0000000000a3"),
              (PREFIX_PARENT, "b0000000-0000-0000-0000-0000000000a4"),
              (ATTRIBUTE_TARGET, "b0000000-0000-0000-0000-0000000000a5"),
              (RESOURCE_TARGET, "b0000000-0000-0000-0000-0000000000a6"),
              (TABULAR_TARGET, "b0000000-0000-0000-0000-0000000000a7"),
              (TS_ATTRIBUTE_TARGET, "b0000000-0000-0000-0000-0000000000a8")]
    return index



# ─── проверка 1: фикстуры (состояния, которых корпус не даёт) ──────────────────
def expected_fixture_counts(fixtures: Dict[str, Dict]) -> Dict:
    """Агрегаты сводки, выведенные из таблицы ожиданий, а не заданные числами.

    Сводка `counts_by_*` обязана совпасть с суммой по таблице: иначе правка одного
    ожидания молча разъехалась бы с числом в ответе разбора.
    """
    props = {state: 0 for state in fop.PROPERTIES_STATES}
    use = {state: 0 for state in fop.USE_STATES}
    resolve = {state: 0 for state in fop.TARGET_RESOLVE_STATES}
    forms = {form: 0 for form in fop.ADDRESS_FORMS}
    item_types = {state: 0 for state in fop.ITEM_TYPE_STATES}
    kinds: Dict[str, int] = {}
    total = 0
    max_targets = 0
    distinct = set()
    for entry in fixtures.values():
        if entry["props"] == FAIL:
            continue
        props[entry["props"]] += 1
        use[entry["use"]] += 1
        max_targets = max(max_targets, len(entry["targets"]))
        for address, form, state, type_state in entry["targets"]:
            total += 1
            resolve[state] += 1
            forms[form] += 1
            item_types[type_state] += 1
            kind = target_object_type(address)
            kinds[kind] = kinds.get(kind, 0) + 1
            distinct.add(address)
    return {"counts_by_properties_state": props, "counts_by_use_state": use,
            "counts_by_target_resolve_state": resolve,
            "counts_by_target_address_form": forms,
            "counts_by_item_type_state": item_types, "targets_total": total,
            MAX_TARGETS_KEY: max_targets, "targets_distinct": len(distinct),
            "targets_by_kind": kinds}


def check_fixture_row(fixtures: Dict[str, Dict], result: Dict) -> None:
    """Ожидание по каждой фиктуре: строка вида, её применение, сверка с индексом."""
    rows = result["rows"]
    targets = result["targets"]
    for key, entry in fixtures.items():
        name = entry["name"]
        if entry["props"] == FAIL:
            reason = failure_reason(result["files_failed"], name)
            check("%s: файл назван отказом с причиной" % key,
                  bool(reason) and entry["fail_reason"] in reason, reason[:120])
            check("%s: отказа нет среди строк разбора" % key,
                  not row_by(rows, name), str(row_by(rows, name).get("object_name")))
            continue

        row = row_by(rows, name)
        if not check("%s: строка вида разобрана" % key, bool(row)):
            continue
        check("%s: properties_state=%s" % (key, entry["props"]),
              row["properties_state"] == entry["props"], str(row["properties_state"]))
        check("%s: перечень виновников %s" % (key, entry["unknown"]),
              (row["unknown_property_names"] or []) == (entry["unknown"] or []),
              str(row["unknown_property_names"]))
        check("%s: use_state=%s, targets_count=%d" % (key, entry["use"],
                                                      len(entry["targets"])),
              row["use_state"] == entry["use"]
              and row["targets_count"] == len(entry["targets"]),
              "use=%s count=%s" % (row["use_state"], row["targets_count"]))
        check("%s: full_name равна object_name (иерархии у вида нет — замер 1.2)" % key,
              row["full_name"] == row["object_name"] == name, str(row["full_name"]))
        check("%s: uuid строки взят из файла" % key,
              row["object_uuid"] == entry["uuid"], str(row["object_uuid"]))

        own = targets_of(targets, fop.index_object_name(name))
        got = [(target["target_full_name"], target["target_address_form"],
                target["target_resolve_state"], target["item_type_state"])
               for target in own]
        check("%s: перечень применения совпадает с ожиданием построчно и по порядку" % key,
              got == entry["targets"], "получено %s" % (got,))
        check("%s: ordinal — порядок записей файла" % key,
              [target["ordinal"] for target in own] == list(range(len(own))),
              str([target["ordinal"] for target in own]))
        expected_tag = "Object" if key == "foreign_item_tag" else "Item"
        check("%s: item_tag остаётся именем элемента из выгрузки (%s)" % (key, expected_tag),
              all(target["item_tag"] == expected_tag for target in own),
              str([target["item_tag"] for target in own]))
        attr = "xr:OtherRef" if key == "item_other_type" else None
        if entry["targets"]:
            check("%s: item_type_attr держит значение из выгрузки (%s)" % (key, attr),
                  all(target["item_type_attr"] == attr for target in own
                      if target["item_type_state"] != ITEM_TYPE_STATE_REF),
                  str([target["item_type_attr"] for target in own]))
        # ключ строки вида: писатель П4 заменит его на числовой id ревизии (M2)
        check("%s: строки применения ключуются индексным именем параметра и его uuid" % key,
              all(target[PARAMETER_LINK_KEY] == fop.index_object_name(name)
                  and target[PARAMETER_UUID_KEY] == entry["uuid"] for target in own),
              str([(target[PARAMETER_LINK_KEY], target[PARAMETER_UUID_KEY])
                   for target in own][:1]))



def target_by(result: Dict, name: str, index: int = 0) -> Dict:
    """Строка применения фиктуры по имени параметра и позиции перечня."""
    own = targets_of(result["targets"], fop.index_object_name(name))
    return own[index] if index < len(own) else {}


def check_fixture_details(result: Dict) -> None:
    """Содержание ссылок состояний: чем именно разрешён каждый адрес (Q3, вариант A)."""
    exact = target_by(result, "Типичная", 0)
    check("exact держит object_id и uuid строки индекса, остатка нет",
          exact.get("target_object_id") == "b0000000-0000-0000-0000-0000000000a1"
          and exact.get("target_object_uuid") == "b0000000-0000-0000-0000-0000000000a1"
          and exact.get("target_unresolved_path") is None,
          str((exact.get("target_object_id"), exact.get("target_object_uuid"),
               exact.get("target_unresolved_path"))))
    prefix = target_by(result, "ПрефиксИзмерения")
    check("prefix_only: идентификатор строки-префикса, uuid цели пуст, остаток назван",
          prefix.get("target_resolve_state") == TARGET_PREFIX_ONLY
          and prefix.get("target_object_id") == "b0000000-0000-0000-0000-0000000000a4"
          and prefix.get("target_object_uuid") is None
          and prefix.get("target_unresolved_path") == "Dimension.Отсутствует",
          str((prefix.get("target_object_id"), prefix.get("target_object_uuid"),
               prefix.get("target_unresolved_path"))))
    unresolved = target_by(result, "НеразрешённаяЦель")
    check("unresolved: ссылок нет, остатком назван весь адрес",
          unresolved.get("target_object_id") is None
          and unresolved.get("target_object_uuid") is None
          and unresolved.get("target_unresolved_path") == UNRESOLVED_TARGET,
          str((unresolved.get("target_object_id"),
               unresolved.get("target_unresolved_path"))))
    empty = target_by(result, "ПустойЭлемент")
    check("empty_value: адрес, вид цели, форма и ссылки пусты (M6)",
          empty.get("target_full_name") == "" and empty.get("target_object_type") == ""
          and empty.get("target_address_form") == ADDRESS_FORM_EMPTY
          and empty.get("target_object_id") is None
          and empty.get("target_object_uuid") is None
          and empty.get("target_unresolved_path") is None, str(empty))
    dimension = target_by(result, "Типичная", 1)
    check("псевдозапись среза `.Dimension.` разрешается и несёт uuid (замер 2.1: 30 из 34)",
          dimension.get("target_address_form") == ADDRESS_FORM_DIMENSION
          and dimension.get("target_object_uuid") == "b0000000-0000-0000-0000-0000000000a3",
          str(dimension))
    other = target_by(result, "ПрочийАдрес")
    check("прочий адрес остаётся формой `other` и разрешается префиксом",
          other.get("target_address_form") == ADDRESS_FORM_OTHER
          and other.get("target_unresolved_path") == "ЧтоТо", str(other))

    # Вид и форма цели выводятся из адреса, а не подставляются: тот же предикат, что
    # кладут CHECK `..._targets_type_matches_name` и `..._targets_form_matches_name`.
    check("вид цели = первый сегмент адреса, форма — его структурой (M5)",
          all(target["target_object_type"] == target_object_type(target["target_full_name"])
              and target["target_address_form"]
              == target_address_form(target["target_full_name"])
              for target in result["targets"]),
          str([(target["target_full_name"], target["target_object_type"],
                target["target_address_form"]) for target in result["targets"]][:3]))



def check_fixture_circle(fixtures: Dict[str, Dict], result: Dict) -> None:
    """Круг фиктур целиком: числа, расхождения двух ног, наблюдения, диагностика."""
    parsed = {key: entry for key, entry in fixtures.items() if entry["props"] != FAIL}
    check("спецификаций 24, из них 20 разбираются, 4 — отказ с причиной",
          len(fixtures) == 24 and len(parsed) == 20,
          "всего=%d разбираются=%d" % (len(fixtures), len(parsed)))
    check("круг: файлов найдено 24 (подкаталог и файл не-XML в круг не входят)",
          result["files_found"] == 24, str(result["files_found"]))
    check("круг: разобрано 20, пропущено 4 с причиной",
          result["files_read"] == 20 and len(result["files_failed"]) == 4,
          "read=%d failed=%s" % (result["files_read"],
                                 [(f["source_path"], f["reason"])
                                  for f in result["files_failed"]]))
    check("отказ каждого файла называется текстом причины",
          all(f["reason"] for f in result["files_failed"]),
          str([f["source_path"] for f in result["files_failed"]]))

    expected_counts = expected_fixture_counts(parsed)
    for key in fop.COUNT_KEYS:
        check("сводка %s равна сумме ожиданий по таблице фиктур" % key,
              result[key] == expected_counts[key],
              "получено %s, ожидалось %s" % (result[key], expected_counts[key]))
    for key in ("targets_total", MAX_TARGETS_KEY, "targets_distinct"):
        check("сводка %s равна ожиданию таблицы" % key,
              result[key] == expected_counts[key],
              "получено %s, ожидалось %s" % (result[key], expected_counts[key]))
    check("классы целей равны первым сегментам адресов",
          result["targets_by_kind"] == expected_counts["targets_by_kind"],
          str(result["targets_by_kind"]))
    check("словари состояний названы полным замкнутым перечнем, включая нули (C2)",
          all(set(result[key]) == set(fop.STATE_VOCABULARIES[column])
              for key, column in fop.COUNT_KEY_STATE_COLUMNS.items()),
          str({key: sorted(result[key]) for key in fop.COUNT_KEYS}))

    check("расхождение `file_only` названо файлом без записи индекса",
          result["file_only"] == ["FunctionalOptionsParameters/ТолькоФайл.xml"],
          str(result["file_only"]))
    check("расхождение `uuid_mismatch` названо парой uuid",
          len(result["uuid_mismatch"]) == 1
          and result["uuid_mismatch"][0]["file_uuid"]
          and result["uuid_mismatch"][0]["index_uuid"]
          and result["uuid_mismatch"][0]["file_uuid"]
          != result["uuid_mismatch"][0]["index_uuid"],
          str(result["uuid_mismatch"]))
    check("расхождение `index_only` названо записью индекса без файла",
          result["index_only"] == ["FunctionalOptionsParameter.ИндексБезФайла"],
          str(result["index_only"]))
    check("вид-сосед `FunctionalOption` в круг не попал (раздел 1.2 плана)",
          "FunctionalOption.ОпцияСоседа" not in result["index_only"]
          and not row_by(result["rows"], "ОпцияСоседа"),
          str(result["index_only"]))
    check("числа ноги индекса стадия не выдумывает: ключей `index_*` у разбора нет",
          not [key for key in result if key.startswith("index_")
               and key != "index_only"],
          str(sorted(key for key in result if key.startswith("index_"))))

    check("наблюдение о подкаталоге вида названо (сторож примитивности, замер 1.2)",
          ("unexpected_dir", "FunctionalOptionsParameters/Forms") in result["observations"],
          str(result["observations"]))
    check("наблюдения о файлах не-XML названы",
          ("unexpected_file", "FunctionalOptionsParameters/Forms/Заметка.txt")
          in result["observations"]
          and ("unexpected_file", "FunctionalOptionsParameters/Модуль.bsl")
          in result["observations"], str(result["observations"]))
    check("видов наблюдений вне замкнутого перечня нет",
          all(kind in fop.OBSERVATION_KINDS for kind, _ in result["observations"]),
          str(result["observations"]))

    check("тег свойства вне словаря назван именем и числом (Q1, вариант A)",
          result["unknown_properties"] == {"UnknownProperty": 1},
          str(result["unknown_properties"]))
    check("значение свойства вне измеренной формы названо именем (Q7, вариант A)",
          result["unknown_value_properties"] == {"Comment": 1},
          str(result["unknown_value_properties"]))
    check("чужой тег элемента перечня назван именем (M7)",
          result["unexpected_tags"] == {"Object": 1}, str(result["unexpected_tags"]))
    check("иное значение `xsi:type` названо значением из выгрузки (M6)",
          result["unexpected_item_types"] == {"xr:OtherRef": 1},
          str(result["unexpected_item_types"]))
    check("повтор цели назван адресом и файлом, дедупликации нет",
          len(result["duplicate_targets"]) == 1
          and result["duplicate_targets"][0]["target_full_name"] == CATALOG_TARGET,
          str(result["duplicate_targets"]))
    check("неразрешённые цели названы числом и примерами (не путать с «цели нет»)",
          result["unresolved_targets_total"] == 3,
          "total=%s примеры=%s" % (result["unresolved_targets_total"],
                                   result["unresolved_targets"]))
    check("инварианты строк разбора не нарушены (предикаты CHECK'ов П1)",
          result["invariant_violations_total"] == 0,
          str(result["invariant_violations"]))
    # Успех круга — не «всё разобралось»: круг фиктур намеренно содержит четыре файла,
    # которые обязаны быть названы отказом. Ответ называется неуспешным ровно по ним, а
    # не по нарушениям инвариантов (их число — ноль, проверка выше).
    check("круг с намеренно битыми файлами назван неуспешным по числу отказов, "
          "а не по инвариантам",
          result["success"] is False and len(result["files_failed"]) == 4
          and result["invariant_violations_total"] == 0,
          "success=%s failed=%d invariant=%d" % (result["success"],
                                                len(result["files_failed"]),
                                                result["invariant_violations_total"]))



def check_fixtures(root: Path) -> Dict:
    emit("=== фикстуры (состояния, которых эталонные выгрузки не дают)")
    fixtures = build_fixtures(root)
    (root / "ConfigDumpInfo.xml").write_text(
        dump_index(fixture_index_rows(fixtures)), encoding="utf-8")
    result = collect_functional_options_parameters(str(root),
                                                  index_rows=load_index_rows(root))
    check_fixture_row(fixtures, result)
    check_fixture_details(result)
    check_fixture_circle(fixtures, result)
    return result


def check_missing_directory() -> None:
    """Каталога вида нет — это состояние выгрузки, а не отказ (Q9, вариант A; KomMag)."""
    emit()
    emit("=== отсутствие каталога вида и непереданный индекс состава")
    with tempfile.TemporaryDirectory(prefix="v57_empty_") as name:
        empty = Path(name)
        result = collect_functional_options_parameters(str(empty), index_rows=[])
        check("каталог, которого нет, — ответ о выгрузке, а не отказ",
              result["success"] is True and result["files_found"] == 0
              and result["files_read"] == 0 and not result["files_failed"],
              str({key: result[key] for key in
                   ("success", "files_found", "files_read")}))
        check("причина названа наблюдением `directory_missing`",
              ("directory_missing", DIR_NAME) in result["observations"],
              str(result["observations"]))
        check("пустой круг назван нулями по всем словарям состояний, а не молчанием",
              all(sum(result[key].values()) == 0 for key in fop.COUNT_KEYS)
              and result["targets_total"] == 0 and result[MAX_TARGETS_KEY] == 0,
              str({key: result[key] for key in fop.COUNT_KEYS}))
        check("пустой ответ не притворяется ответом об индексе: `index_only` пуст",
              result["index_only"] == [] and result["file_only"] == []
              and result["uuid_mismatch"] == [],
              str({key: result[key] for key in fop.CIRCLE_DISCREPANCIES}))


def check_index_not_provided(root: Path) -> None:
    """Индекс не передавали — НЕ «целей нет»: разрешение остаётся `unresolved` (Q6, C2)."""
    result = collect_functional_options_parameters(str(root))
    resolve = result["counts_by_target_resolve_state"]
    check("индекс не передан — наблюдение `index_not_provided` называется",
          ("index_not_provided", "configuration_objects") in result["observations"],
          str(result["observations"]))
    check("цели при незагруженном индексе остаются `unresolved`, а не исчезают "
          "(пустой текст элемента — отдельное состояние `empty_value`, M6)",
          result["targets_total"] > 0
          and resolve[TARGET_UNRESOLVED]
          == result["targets_total"] - resolve[TARGET_EMPTY_VALUE],
          str(resolve))
    check("сверка ног при незагруженном индексе не считается: расхождений ноль",
          result["index_only"] == [] and result["file_only"] == [],
          str({key: result[key] for key in fop.CIRCLE_DISCREPANCIES}))
    check("«не разрешалось» отличается от «не разрешилось» строкой наблюдения",
          any(kind == "index_not_provided" for kind, _ in result["observations"])
          and result["unresolved_targets_total"]
          == result["targets_total"] - resolve[TARGET_EMPTY_VALUE],
          "unresolved=%s targets=%s" % (result["unresolved_targets_total"],
                                        result["targets_total"]))

    # Одиночный файл без индекса: сверка называется состоянием `not_checked`, а не
    # `file_only` (файл, которого не с чем сверять, — не расхождение круга).
    single = next((path for path in sorted((root / DIR_NAME).glob("*.xml"))
                   if path.stem == "Типичная"), None)
    if not check("одиночный файл фиктуры найден", single is not None, str(single)):
        return
    parsed = read_registration_file(single)
    check("без индекса сверка называется `not_checked`, а не выдуманным `file_only`",
          parsed["success"] and parsed["index_check"]["state"] == "not_checked",
          str(parsed["index_check"]))
    check("без индекса цели разрешаются состоянием `unresolved`",
          all(target["target_resolve_state"] == TARGET_UNRESOLVED
              for target in parsed["targets"]),
          str([target["target_resolve_state"] for target in parsed["targets"]]))



# ─── проверка 2: сторож инвариантов проверяется на собственных ошибках ─────────
# «Ноль нарушений» из `check_row` ничего не значит, если проверяющая функция не замечает
# противоречий. Здесь намеренно испорченные строки обязаны быть названы — иначе П4 падал
# бы на CHECK живой схемы на середине записанного круга.
ROW_UUID = "0a0a0a0a-0a0a-0a0a-0a0a-0a0a0a0a0a0a"
TARGET_UUID = "0b0b0b0b-0b0b-0b0b-0b0b-0b0b0b0b0b0b"


def base_row(**overrides) -> Dict:
    row = {"object_name": "Параметр", "full_name": "Параметр", "object_uuid": ROW_UUID,
           "synonym": {"ru": "Параметр"}, "comment": None, "use_state": USE_WITH,
           "targets_count": 1, "properties_state": PROPS_ALL_KNOWN,
           "unknown_property_names": None,
           "source_path": "FunctionalOptionsParameters/Параметр.xml"}
    row.update(overrides)
    return row


def base_target(**overrides) -> Dict:
    target = {"ordinal": 0, "item_tag": "Item", "item_type_attr": "xr:MDObjectRef",
              "item_type_state": ITEM_TYPE_STATE_REF,
              "target_full_name": CATALOG_TARGET, "target_object_type": "Catalog",
              "target_address_form": ADDRESS_FORM_OBJECT,
              "target_object_id": TARGET_UUID, "target_object_uuid": TARGET_UUID,
              "target_unresolved_path": None, "target_resolve_state": TARGET_EXACT,
              PARAMETER_LINK_KEY: "FunctionalOptionsParameter.Параметр",
              PARAMETER_UUID_KEY: ROW_UUID}
    target.update(overrides)
    return target


def check_invariant_guard() -> None:
    emit()
    emit("=== сторож инвариантов: целая строка проходит, испорченная — называется")
    ok_row, ok_target = base_row(), base_target()
    clean = check_row(ok_row, [ok_target])
    check("согласованная строка и её применение нарушений не дают", not clean, str(clean))
    empty_only = check_row(base_row(use_state=USE_EMPTY, targets_count=0), [])
    check("пустой перечень без строк применения проходит", not empty_only, str(empty_only))
    absent = check_row(base_row(use_state=USE_EMPTY, targets_count=0,
                                properties_state=PROPS_ABSENT,
                                unknown_property_names=["Use"]), [])
    check("отсутствующий тег `Use` с названным виновником проходит", not absent,
          str(absent))

    broken = {
        "with_content при нуле строк применения (CHECK ..._use_state_matches_targets)":
            (base_row(), [], 1),
        "empty_content при непустом перечне":
            (base_row(use_state=USE_EMPTY), [base_target()], 1),
        "targets_count не равен числу строк применения":
            (base_row(targets_count=2), [base_target()], 1),
        "absent без перечня виновников":
            (base_row(use_state=USE_EMPTY, targets_count=0,
                      properties_state=PROPS_ABSENT), [], 1),
        "all_known с непустым перечнем виновников":
            (base_row(unknown_property_names=["Use"]), [base_target()], 1),
        "пустой object_name (CHECK ..._names_not_blank)":
            (base_row(object_name=""), [base_target()], 2),
        "пустой full_name (CHECK ..._names_not_blank)":
            (base_row(full_name=""), [base_target()], 1),
        "full_name не равна object_name (иерархии у вида нет)":
            (base_row(full_name="Параметр.Вложенный"), [base_target()], 1),
        "object_uuid не является uuid":
            (base_row(object_uuid="не-uuid"), [base_target()], 1),
        "ordinal не равен позиции перечня":
            (base_row(targets_count=2), [base_target(), base_target(ordinal=5)], 1),
        "пустой item_tag": (base_row(), [base_target(item_tag="")], 1),
        "item_type_state=absent при непустом item_type_attr":
            (base_row(), [base_target(item_type_state=ITEM_TYPE_STATE_ABSENT)], 1),
        "item_type_state=md_object_ref при ином значении атрибута":
            (base_row(), [base_target(item_type_attr="xr:OtherRef")], 1),
        "item_type_state=other_form при значении `xr:MDObjectRef`":
            (base_row(), [base_target(item_type_state=ITEM_TYPE_STATE_OTHER)], 1),
        "item_type_state вне замкнутого словаря":
            (base_row(), [base_target(item_type_state="неизвестно")], 1),
        "exact без uuid цели (CHECK ..._resolve_matches_ref)":
            (base_row(), [base_target(target_object_uuid=None)], 1),
        "prefix_only с uuid цели":
            (base_row(), [base_target(target_resolve_state=TARGET_PREFIX_ONLY,
                                     target_unresolved_path="Dimension.Х")], 1),
        "unresolved без остатка адреса":
            (base_row(), [base_target(target_resolve_state=TARGET_UNRESOLVED,
                                     target_object_id=None)], 1),
        "empty_value с непустым адресом":
            (base_row(), [base_target(target_resolve_state=TARGET_EMPTY_VALUE)], 1),
        "пустой адрес с заполненным видом цели":
            (base_row(), [base_target(target_resolve_state=TARGET_EMPTY_VALUE,
                                     target_full_name="", target_object_uuid=None,
                                     target_object_id=None,
                                     target_address_form=ADDRESS_FORM_EMPTY)], 1),
        "target_object_type не равен первому сегменту адреса":
            (base_row(), [base_target(target_object_type="Document")], 1),
        "target_address_form вне замкнутого словаря":
            (base_row(), [base_target(target_address_form="срез")], 1),
    }
    for label, (row, targets, expected_problems) in broken.items():
        problems = check_row(row, targets)
        check("сторож называет: %s" % label, len(problems) >= expected_problems,
              "нарушений %d: %s" % (len(problems), problems[:2]))



# ─── проверка 3: словарь строк парсера против DDL ──────────────────────────────
# Колонки, которые заполняет писатель (П4), а не разбор: суррогатный ключ, ссылка на
# строку заголовка конфигурации, номер ревизии, служебные колонки витрин и связь строки
# применения со строкой вида (`functional_option_parameter_id` — id конкретной ревизии,
# которого разбор знать не может, Q2 вариант A). Разбор работает без живой базы и эти
# ключи не выдумывает.
WRITER_COLUMNS = {"id", "configuration_uuid", "created_at", "revision_no", "changed_at",
                  "changed_by", "is_committed", "functional_option_parameter_id"}


def ddl_table_body(table: str) -> str:
    """Тело `CREATE TABLE` таблицы из текста миграции V57 (БД не открывается)."""
    text = DDL_FILE.read_text(encoding="utf-8")
    match = re.search(r"CREATE TABLE(?: IF NOT EXISTS)?\s+" + table + r"\s*\((.*?)\n\);",
                      text, re.S)
    return match.group(1) if match else ""


def ddl_code_lines(body: str):
    """Строки тела без комментариев.

    `--` в теле — пояснение, а не элемент таблицы; в комментариях стоят и тексты значений
    (`target_resolve_state = 'exact'`), и имена состояний. Чтение их колонками или
    словарями дало бы ложные имена, поэтому комментарии снимаются ДО обоих разборов.
    """
    for line in body.splitlines():
        stripped = line.split("--")[0].strip()
        if stripped:
            yield stripped


def ddl_columns(table: str) -> set:
    """Колонки таблицы из текста миграции: строка формы `имя ТИП[...]`."""
    columns = set()
    for line in ddl_code_lines(ddl_table_body(table)):
        found = re.match(r"([a-z][a-z0-9_]*)\s+[A-Z]", line)
        if found:
            columns.add(found.group(1))
    return columns


def ddl_constraint_columns(table: str) -> set:
    """Колонки, которые называют ограничения таблицы (CHECK).

    Мера полноты чтения текста: пропущенная колонка всплывает здесь, а не в сравнении со
    строками разбора — там она выглядела бы как «колонка не заполняется разбором», и
    чинили бы разбор вместо чтения DDL.
    """
    names = set()
    for line in ddl_code_lines(ddl_table_body(table)):
        names.update(re.findall(
            r"([a-z_][a-z0-9_]*)\s*(?:>=|<=|<>|!=|=|IS\s+NOT\s+NULL|IS\s+NULL|IS\b|IN\s*\()",
            line))
    return names


def ddl_state_values(table: str, column: str) -> set:
    """Словарь значений колонки состояния из CHECK таблицы (замкнутый `IN (…)`).

    Берётся объединение всех предикатов по колонке: `IN (…)` даёт замкнутый словарь,
    сравнения `= '…'` — его подмножества. Расхождение с словарём модуля означает либо
    мёртвую ветку CHECK, либо состояние, которое схема отвергнет при загрузке круга.
    """
    body = " ".join(ddl_code_lines(ddl_table_body(table)))
    values = set()
    for group in re.findall(re.escape(column) + r"\s*IN\s*\(([^)]*)\)", body):
        values.update(re.findall(r"'([^']*)'", group))
    for group in re.findall(re.escape(column) + r"\s*=\s*'([^']*)'", body):
        values.add(group)
    return values



def check_ddl_layer(rows: List[Dict], targets: List[Dict]) -> None:
    emit()
    emit("=== словарь строк парсера и словари состояний против DDL (текст миграции)")
    for table, records in ((fop.TABLE_NAME, rows), (fop.TARGETS_TABLE_NAME, targets)):
        columns = ddl_columns(table)
        if not check("DDL: таблица %s найдена в тексте миграции" % table, bool(columns),
                     "колонок: %d" % len(columns)):
            continue
        not_seen = sorted(ddl_constraint_columns(table) - columns)
        check("%s: текст CREATE TABLE прочитан целиком — колонки из ограничений найдены"
              % table, not not_seen, "не извлечены: %s" % not_seen)
        if not records:
            continue
        keys = set()
        for record in records:
            keys.update(record.keys())
        extra = sorted(keys - columns)
        check("%s: каждому ключу строки разбора соответствует колонка" % table, not extra,
              "лишние ключи: %s" % extra)
        semantic = columns - WRITER_COLUMNS
        missing = sorted(semantic - keys)
        check("%s: каждая смысловая колонка DDL заполняется разбором (%d из %d, "
              "служебных колонок писателя %d)" % (table, len(semantic) - len(missing),
                                                 len(semantic), len(WRITER_COLUMNS)),
              not missing, "не заполняются: %s" % missing)

    declared_targets = set(fop.TARGET_ROW_KEYS)
    got_targets = set()
    for record in targets:
        got_targets.update(record.keys())
    check("модуль объявляет колонки применения ровно теми, что отдаёт разбор",
          declared_targets == got_targets,
          "нет в разборе: %s; нет в объявлении: %s"
          % (sorted(declared_targets - got_targets), sorted(got_targets - declared_targets)))
    check("ключ строки вида объявлен: писатель П4 меняет его на id ревизии (M2)",
          PARAMETER_LINK_KEY in declared_targets
          and PARAMETER_UUID_KEY in declared_targets, str(sorted(declared_targets)))

    for column, vocabulary in fop.STATE_VOCABULARIES.items():
        table = fop.STATE_VOCABULARY_TABLES[column]
        values = ddl_state_values(table, column)
        check("словарь состояний %s совпадает со словарём CHECK таблицы %s"
              % (column, table), values == set(vocabulary),
              "нет в модуле: %s; нет в DDL: %s"
              % (sorted(values - set(vocabulary)), sorted(set(vocabulary) - values)))
        check("колонка состояния %s есть в той таблице, где её ищет узел" % column,
              column in ddl_columns(table), table)
    check("словарей состояний ровно пять, и каждый отнесён к таблице узла",
          set(fop.STATE_VOCABULARIES) == set(fop.STATE_VOCABULARY_TABLES)
          and set(fop.COUNT_KEYS) == {"counts_by_" + column
                                      for column in fop.STATE_VOCABULARIES},
          str(sorted(fop.STATE_VOCABULARIES)))
    check("словарь свойств вида равен измеренному перечню тегов (замер 2 плана)",
          fop.XML_PROPERTY_NAMES == ("Name", "Synonym", "Comment", "Use")
          and fop.DECLARED_PROPERTIES == ("Synonym", "Comment", "Use"),
          str((fop.XML_PROPERTY_NAMES, fop.DECLARED_PROPERTIES)))



# ─── проверка 4: эталонные выгрузки ────────────────────────────────────────────
COUNT_KEYS_IN_EXPECTED = ("props_all_known", "props_unknown_value", "props_unknown_tag",
                         "props_absent", "use_with", "use_empty", "exact", "prefix_only",
                         "unresolved", "empty_value", "form_object", "form_dimension",
                         "form_attribute", "form_register_resource",
                         "form_tabular_section", "form_other", "form_empty",
                         "item_md_object_ref", "item_absent", "item_other_form")


def flatten(result: Dict) -> Dict[str, int]:
    """Сводка состояний одним словарём — в тех же ключах, что задаёт EXPECTED."""
    props = result["counts_by_properties_state"]
    use = result["counts_by_use_state"]
    resolve = result["counts_by_target_resolve_state"]
    forms = result["counts_by_target_address_form"]
    items = result["counts_by_item_type_state"]
    return {
        "props_all_known": props[PROPS_ALL_KNOWN],
        "props_unknown_value": props[PROPS_UNKNOWN_VALUE],
        "props_unknown_tag": props[PROPS_UNKNOWN_TAG],
        "props_absent": props[PROPS_ABSENT],
        "use_with": use[USE_WITH],
        "use_empty": use[USE_EMPTY],
        "exact": resolve[TARGET_EXACT],
        "prefix_only": resolve[TARGET_PREFIX_ONLY],
        "unresolved": resolve[TARGET_UNRESOLVED],
        "empty_value": resolve[TARGET_EMPTY_VALUE],
        "form_object": forms[ADDRESS_FORM_OBJECT],
        "form_dimension": forms[ADDRESS_FORM_DIMENSION],
        "form_attribute": forms[ADDRESS_FORM_ATTRIBUTE],
        "form_register_resource": forms[ADDRESS_FORM_REGISTER_RESOURCE],
        "form_tabular_section": forms[ADDRESS_FORM_TABULAR_SECTION],
        "form_other": forms[ADDRESS_FORM_OTHER],
        "form_empty": forms[ADDRESS_FORM_EMPTY],
        "item_md_object_ref": items[ITEM_TYPE_STATE_REF],
        "item_absent": items[ITEM_TYPE_STATE_ABSENT],
        "item_other_form": items[ITEM_TYPE_STATE_OTHER],
    }


def check_dump(name: str, root: Path) -> Dict[str, int]:
    emit()
    emit("--- %s: %s" % (name, root))
    if not check("выгрузка найдена", root.is_dir(), str(root)):
        return {}
    index_rows = load_index_rows(root)
    if not check("ConfigDumpInfo.xml найден и прочитан", bool(index_rows),
                 str(root / "ConfigDumpInfo.xml")):
        return {}
    result = collect_functional_options_parameters(str(root), index_rows=index_rows)
    expected = EXPECTED[name]
    check("разбор успешен: отказов круга нет",
          result["success"] is True and not result["files_failed"],
          str(result["files_failed"]))
    check("файлов круга и разобрано — по замеру 1.1",
          result["files_found"] == expected["files"]
          and result["files_read"] == expected["files"],
          "found=%s read=%s ожидалось=%s" % (result["files_found"],
                                             result["files_read"], expected["files"]))
    flat = flatten(result)
    flat["files"] = result["files_found"]
    flat["targets"] = result["targets_total"]
    flat["distinct"] = result["targets_distinct"]
    flat["max_targets"] = result[MAX_TARGETS_KEY]
    for key in COUNT_KEYS_IN_EXPECTED:
        check("состояние %s = %s (раздел 2 плана)" % (key, expected[key]),
              flat[key] == expected[key],
              "получено %s, ожидалось %s" % (flat[key], expected[key]))
    check("строк применения и их максимум — по замеру 2.1",
          result["targets_total"] == expected["targets"]
          and result[MAX_TARGETS_KEY] == expected["max_targets"],
          "total=%s max=%s ожидалось=%s/%s" % (result["targets_total"],
                                               result[MAX_TARGETS_KEY],
                                               expected["targets"],
                                               expected["max_targets"]))
    check("различающихся целей — по замеру 2.1 (дедупликации нет)",
          result["targets_distinct"] == expected["distinct"],
          "получено %s, ожидалось %s" % (result["targets_distinct"],
                                         expected["distinct"]))

    check("классов целей — по замеру 2.1", result["targets_by_kind"] == expected["kinds"],
          str(result["targets_by_kind"]))
    check("класса `FunctionalOption` среди целей нет (строка 179 плана)",
          "FunctionalOption" not in result["targets_by_kind"],
          str(sorted(result["targets_by_kind"])))
    check("круг полностью покрыт индексом: расхождений ног нет (числа 1.1 равны)",
          not result["index_only"] and not result["file_only"]
          and not result["uuid_mismatch"],
          str({key: result[key] for key in fop.CIRCLE_DISCREPANCIES}))
    check("тегов вне словаря, чужих тегов и чужих `xsi:type` корпус не даёт",
          not result["unknown_properties"] and not result["unexpected_tags"]
          and not result["unexpected_item_types"]
          and not result["unknown_value_properties"],
          str({key: result[key] for key in
               ("unknown_properties", "unexpected_tags", "unexpected_item_types",
                "unknown_value_properties")}))
    check("повторов цели в одном файле корпус не даёт (замер 2.1: dups=0)",
          not result["duplicate_targets"], str(result["duplicate_targets"]))
    check("классов цели у выгрузки ровно столько, сколько названо (замер 2.2)",
          result["target_kinds_total"] == len(expected["kinds"]),
          "получено %s, ожидалось %s" % (result["target_kinds_total"],
                                         len(expected["kinds"])))
    kinds = {kind for kind, _ in result["observations"]}
    check("наблюдения корпуса — только ожидаемые (пустой перечень остаётся состоянием)",
          kinds == set(expected["observations"]), str(result["observations"]))
    check("инварианты строк корпуса не нарушены",
          result["invariant_violations_total"] == 0, str(result["invariant_violations"]))

    # Целостность круга: каждая строка применения ссылается на строку вида той же
    # выгрузки именем из индекса — тем самым предикатом, которым П4 заменит его на id.
    names = {fop.index_object_name(str(row["object_name"])) for row in result["rows"]}
    orphan = sorted({str(target[PARAMETER_LINK_KEY]) for target in result["targets"]
                     if target[PARAMETER_LINK_KEY] not in names})
    check("каждая строка применения указывает на строку вида той же выгрузки",
          not orphan, str(orphan))
    mismatched = 0
    for row in result["rows"]:
        for target in targets_of(result["targets"],
                                fop.index_object_name(str(row["object_name"]))):
            if target[PARAMETER_UUID_KEY] != row["object_uuid"]:
                mismatched += 1
    check("uuid строки применения совпадает с uuid строки вида (пара для id из БД)",
          mismatched == 0, "несовпадений: %d" % mismatched)
    return flat


def check_corpora() -> None:
    emit()
    emit("=== эталонные выгрузки (числа разделов 1–2 плана)")
    totals: Dict[str, int] = {}
    kinds_total: Dict[str, int] = {}
    max_targets = 0
    for name in DUMPS:
        flat = check_dump(name, DUMP_ROOT / name)
        for key, value in flat.items():
            if key == "max_targets":
                max_targets = max(max_targets, value)
                continue
            totals[key] = totals.get(key, 0) + value
        for kind, count in EXPECTED[name]["kinds"].items():
            kinds_total[kind] = kinds_total.get(kind, 0) + count
    emit()
    emit("--- корпус целиком (строки 100–105, 179, 181, 183, 185 плана)")
    for key, value in sorted(CORPUS_TOTALS.items()):
        check("по корпусу %s = %s" % (key, value), totals.get(key) == value,
              "получено %s, ожидалось %s" % (totals.get(key), value))
    check("по корпусу максимум целей на файл — %d (замер 2.1, параметр `Организация` BP3)"
          % CORPUS_MAX_TARGETS, max_targets == CORPUS_MAX_TARGETS, str(max_targets))
    check("по корпусу классов цели — ровно %s (строка 179 плана)" % sorted(CORPUS_KINDS),
          kinds_total == CORPUS_KINDS, str(kinds_total))
    check("сумма классов цели равна числу целей — словарь классов полон",
          sum(kinds_total.values()) == totals.get("targets"),
          "классы=%s целей=%s" % (sum(kinds_total.values()), totals.get("targets")))
    check("по корпусу `exact` — все 34 цели, `prefix_only`/`unresolved`/`empty_value` — "
          "ноль (строки 158–159 плана: индекс содержит и псевдозаписи срезов)",
          totals.get("exact") == 34 and not any(totals.get(key)
                                               for key in ("prefix_only", "unresolved",
                                                         "empty_value")),
          str({key: totals.get(key) for key in ("exact", "prefix_only", "unresolved",
                                               "empty_value")}))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v57_p3_") as name:
        fixtures = Path(name)
        fixture_result = check_fixtures(fixtures)
        check_missing_directory()
        check_index_not_provided(fixtures)
    check_invariant_guard()
    check_ddl_layer(fixture_result["rows"], fixture_result["targets"])
    check_corpora()

    print("\n".join(REPORT))
    print()
    print("Проверок: %d, отказов: %d" % (CHECKS_TOTAL, len(FAILURES)))
    for name, detail in FAILURES:
        print("  FAIL: %s%s" % (name, (" — " + detail)[:300]))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())

