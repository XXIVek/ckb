#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П2 узла V50: офлайн-проверка парсера круга `CommonAttributes` (БД не трогает).

Зачем. П3 (писатель) и П4 (стадия) начинают писать код только когда разбор круга назван
числами и состояниями: парсер проверяется на двух рядах доказательств.

1. Синтетические fixtures — случаи, которых в эталонных выгрузках нет или мало: неизвестный
   тег свойства, неизвестное значение перечислимого свойства, `<Type>` только с
   `ValueStorage`, отсутствие блока `<Type>`, кратность (два `<v8:TypeValue>`),
   `<v8:TypeValue/>` с одними квалификаторами, элемент `<xr:Item>` без `<xr:Metadata>`,
   отсутствие `<Content>`, битый XML, дубль цели, ссылка разделения, расхождения с индексом
   состава (`index_only` / `file_only` / `uuid_mismatch`). В эталонных корпусах этих
   состояний нет (замер 2.3: неизвестных тегов и значений — 0), поэтому проверка состояний
   обязана быть своей, а не выведенной из корпусов.
2. Четыре эталонные выгрузки — ожидаемые числа берутся из П0 (`_v50_p0_probe.py`, раздел 2
   плана): файлы 3/0/15/16, цели 14/0/165/158, состояния блока `<Type>` (parsed 1/0/13/14,
   empty_value 2/0/2/2), разрешимость целей и ссылок по индексу состава, совпадение с
   индексом (uuid_match 3/15/16), нули по неизвестным свойствам и тегам. Расхождение с П0 —
   сигнал о том, что парсер или замер разошлись; цифру плана она не меняет, но обязана быть
   названа.

Третья проверка — соответствие словаря строк DDL: имена ключей строки парсера сверяются со
списком колонок `common_attributes` / `common_attribute_targets` из
`migrate_v50_common_attributes.sql` (файл читается текстом, БД не открывается). Иначе П3
упал бы на несуществующей колонке после записи половины строк.

Ничего в БД зонд не пишет и ничего не чинит молча: провал — строка отчёта и ненулевой код
выхода.
"""
from __future__ import annotations

import re
import sys
import tempfile
import uuid as uuid_lib
from pathlib import Path
from typing import Dict, Tuple

ROOT = Path(__file__).resolve().parents[2]
# Тот же порядок, что у офлайн-зондов V48/V49: корень проекта и каталог `src`
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

from config_dump_info_parser import find_config_dump_info, parse_config_dump_info  # noqa: E402
from configuration_common_attributes import (  # noqa: E402
    CLASS_OBJECT_REF, CLASS_PRIMITIVE, CONTENT_EMPTY, CONTENT_WITH, DIR_NAME,
    ENTRY_STATE_PARSED, ENTRY_STATE_UNKNOWN_FORM, MULT_COMPOSITE, MULT_SINGLE,
    PROPS_ALL_KNOWN, PROPS_UNKNOWN_TAG, PROPS_UNKNOWN_VALUE, SEP_EMPTY, SEP_PARSED,
    STATE_ABSENT, STATE_PARSED, STATE_PARTIAL,
    STATE_UNKNOWN_FORM, TARGET_EXACT, TARGET_PREFIX_ONLY, TARGET_UNRESOLVED, TYPE_ENTRY_KEYS,
    TYPE_ENTRY_REASON_KEY, TYPE_ENTRY_TARGET_KEYS, USE_NOT_USED, USE_USED,
    collect_common_attributes, read_registration_file,
)

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DDL_FILE = ROOT / "sql" / "migrate_v50_common_attributes.sql"

# Ожидаемые числа — раздел 2 плана docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md
# (`_v50_p0_probe.py`, `_v50_p0_index_probe.py`): файлы 2/0/7/7; цели применения
# 3/0/692/817 (Use 259, DontUse 1 253, различных целей 3/584/706, максимум на файл
# 2/565/688); значений `<v8:Type>` 18 (один файл составной — три значения); целей вне
# индекса 0; непустых ссылок разделения по 2 файла на выгрузку; расхождений с индексом
# состава 0. У KomMag позиции вида нет ни файлами, ни строками индекса, ни перечнем
# заголовка (замер 2.9) — ответ обязан быть пустым кругом с наблюдением directory_missing,
# а не отказом.
EXPECTED = {
    "MinCfg": {"files": 2, "targets": 3, "distinct": 3, "max_targets": 2,
               "used": 3, "not_used": 0, "types_total": 4, "single": 1, "composite": 1,
               "separation": 0},
    "KomMag": {"files": 0, "targets": 0, "distinct": 0, "max_targets": 0,
               "used": 0, "not_used": 0, "types_total": 0, "single": 0, "composite": 0,
               "separation": 0},
    "BGU2": {"files": 7, "targets": 692, "distinct": 584, "max_targets": 565,
             "used": 127, "not_used": 565, "types_total": 7, "single": 7, "composite": 0,
             "separation": 2},
    "BP3": {"files": 7, "targets": 817, "distinct": 706, "max_targets": 688,
            "used": 129, "not_used": 688, "types_total": 7, "single": 7, "composite": 0,
            "separation": 2},
}

FAILURES: list = []
REPORT: list = []


def emit(text: str = "") -> None:
    REPORT.append(text)


def check(name: str, ok: bool, detail: str = "") -> None:
    emit(("  OK   " if ok else "  FAIL ") + name + ((" — " + detail) if detail else ""))
    if not ok:
        FAILURES.append(name)


# ─── синтетические файлы круга ────────────────────────────────────────────────
HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
        'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
        'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xr="http://v8.1c.ru/8.4/xcf/xml-relation">\n')
TAIL = "</CommonAttribute>\n</MetaDataObject>\n"

# Значения `<xr:Use>` в файле — слова платформы (`Use`/`DontUse`, замер 2.4), а не
# состояния колонки (`used`/`not_used`). Писать в XML состояние колонки — значит
# проверить не разбор значения, а собственную ошибку фикстуры.
XML_USE = "Use"
XML_DONT_USE = "DontUse"

# Цель применения и ссылка разделения разрешаются по индексу состава, поэтому индекс
# обязан содержать эти строки других видов (замер 2.6: 1 512 целей BP3 разрешаются).
TARGETS = [("Catalog.Товары", "b0000000-0000-0000-0000-0000000000c1"),
           ("Document.Реализация", "b0000000-0000-0000-0000-0000000000d1"),
           ("Catalog.Контрагенты", "b0000000-0000-0000-0000-0000000000c2")]


def ca_file(obj_uuid: str, name: str, props: str = "", value_type: str = "",
            content: str = "", tail: str = "") -> str:
    """Файл регистрации вида целиком.

    Порядок вложенности задаёт замер 2.2: свойства вида лежат внутри `<Properties>`, в том
    числе `<Type>` (блок значений типа — одно из свойств, а не отдельный блок файла) и
    `<Content>`. Отдельного каталога содержимого у вида нет (замер 2.1).
    """
    inner = f"\t\t\t<Name>{name}</Name>\n{props}{value_type}{content}"
    return (HEAD + f'<CommonAttribute uuid="{obj_uuid}">\n'
            f"\t<Properties>\n{inner}\t</Properties>\n{tail}{TAIL}")


def item(metadata: str, use: str = XML_DONT_USE, cond_sep: str = "") -> str:
    body = f"<xr:Metadata>{metadata}</xr:Metadata><xr:Use>{use}</xr:Use>"
    if cond_sep:
        body += f"<xr:ConditionalSeparation>{cond_sep}</xr:ConditionalSeparation>"
    else:
        body += "<xr:ConditionalSeparation/>"
    return f"\t\t\t\t<xr:Item>{body}</xr:Item>\n"


def content_block(items: str) -> str:
    return f"\t\t\t<Content>\n{items}\t\t\t</Content>\n"


def value_type_block(values: str, qualifiers: str = "") -> str:
    """Свойство `<Type>`: значения типа и квалификаторы внутри одного свойства (замер 2.3)."""
    return f"\t\t\t<Type>\n\t\t\t\t<v8:Type>{values}</v8:Type>\n{qualifiers}\t\t\t</Type>\n"


def dump_index(entries) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<ConfigDumpInfo xmlns="http://v8.1c.ru/8.3/xcf/dumpinfo">', "\t<ConfigVersions>"]
    for name, obj_id in entries:
        # configVersion — не идентификатор объекта, а версия метаданий: форма замера V33 —
        # 40 шестнадцатеричных символов (CONFIG_VERSION_RE), иначе индекс читался бы
        # выдумкой, а не замером.
        version = uuid_lib.uuid4().hex + uuid_lib.uuid4().hex[:8]
        lines.append(f'\t\t<Metadata name="{name}" id="{obj_id}" configVersion="{version}"/>')
    lines += ["\t</ConfigVersions>", "</ConfigDumpInfo>"]
    return "\n".join(lines) + "\n"

def build_fixtures(root: Path) -> Dict[str, Tuple[str, str]]:
    """Круг фиктивных выгрузок: по одному файлу на состояние-исключение.

    Возвращает `{ключ: (имя файла, uuid)}` — имена нужны и для записи файлов, и для
    построения индекса состава (в нём задаются расхождения `index_only`, `file_only`,
    `uuid_mismatch`).
    """
    directory = root / DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)

    # 1. Типичный файл: одиночный тип, две цели (`Use` и `DontUse`), непустые блоки
    #    разделения текстом-ссылкой (замер 2.7: внутренних тегов у блоков нет).
    separators = ("\t\t\t<DataSeparationValue>SessionParameter.ОбластьДанныхЗначение"
                  "</DataSeparationValue>\n"
                  "\t\t\t<DataSeparationUse>SessionParameter.ОбластьДанныхИспользование"
                  "</DataSeparationUse>\n"
                  "\t\t\t<ConditionalSeparation>Constant.ИспользоватьРазделение"
                  "</ConditionalSeparation>\n")
    enums = ("\t\t\t<FillChecking>DontCheck</FillChecking>\n"
             "\t\t\t<AutoUse>DontUse</AutoUse>\n"
             "\t\t\t<DataSeparation>Separate</DataSeparation>\n"
             "\t\t\t<Indexing>IndexWithAdditionalOrder</Indexing>\n"
             "\t\t\t<FullTextSearch>Use</FullTextSearch>\n"
             "\t\t\t<PasswordMode>false</PasswordMode>\n")
    files: Dict[str, Tuple[str, str, str]] = {
        "full": ("ПометкаУдаления", "a0000000-0000-0000-0000-000000000001", ca_file(
            "a0000000-0000-0000-0000-000000000001", "ПометкаУдаления",
            enums + separators,
            value_type_block("xs:boolean"),
            content_block(item("Catalog.Товары", XML_USE)
                          + item("Document.Реализация")))),

        # 2. Неизвестный тег и неизвестное значение словарного свойства — виновник
        #    состояния называется, а не теряется (Q7, вариант A).
        "unknown": ("НеизвестноеСвойство", "a0000000-0000-0000-0000-000000000002", ca_file(
            "a0000000-0000-0000-0000-000000000002", "НеизвестноеСвойство",
            "\t\t\t<AutoUse>MaybeUse</AutoUse>\n"
            "\t\t\t<FuturePlatformTag>1</FuturePlatformTag>\n",
            value_type_block("xs:string",
                             "\t\t\t\t<v8:StringQualifiers><v8:Length>10</v8:Length>"
                             "</v8:StringQualifiers>\n"),
            content_block(item("Catalog.Контрагенты")))),

        # 3. Кратность: три значения — составной тип (замер 2.3 даёт такой файл в MinCfg).
        "composite": ("СоставнойТип", "a0000000-0000-0000-0000-000000000003", ca_file(
            "a0000000-0000-0000-0000-000000000003", "СоставнойТип", "",
            value_type_block("xs:decimal</v8:Type>\n\t\t\t\t<v8:Type>xs:dateTime"
                             "</v8:Type>\n\t\t\t\t<v8:Type>xs:string"),
            content_block(item("Catalog.Товары") + item("Catalog.Товары")))),

        # 4. Свойства `<Type>` нет вовсе — состояние `absent`, а не `unknown_form`;
        #    пустой массив types схемой связан именно с отсутствием блока (CHECK).
        "no_type": ("БезТипа", "a0000000-0000-0000-0000-000000000004", ca_file(
            "a0000000-0000-0000-0000-000000000004", "БезТипа", "", "",
            content_block(item("Catalog.Товары")))),

        # 5. Внутри `<Type>` только `<v8:ValueStorage>` — содержимое вне словаря V48 2.4.2:
        #    форма называется unknown_form, исходный блок сохраняется целиком.
        "value_storage": ("ТолькоValueStorage", "a0000000-0000-0000-0000-000000000005", ca_file(
            "a0000000-0000-0000-0000-000000000005", "ТолькоValueStorage", "",
            "\t\t\t<Type>\n\t\t\t\t<v8:ValueStorage>QUJDRA==</v8:ValueStorage>\n"
            "\t\t\t</Type>\n", content_block(item("Catalog.Товары")))),

        # 6. `<v8:Type/>` без текста, но с квалификаторами — значение пустое (замер 2.3
        #    даёт файлы с квалификаторами; пустое значение — граница модели).
        "empty_value": ("ПустойТип", "a0000000-0000-0000-0000-000000000006", ca_file(
            "a0000000-0000-0000-0000-000000000006", "ПустойТип", "",
            value_type_block("", "\t\t\t\t<v8:NumberQualifiers><v8:Precision>10"
                             "</v8:Precision><v8:Scale>2</v8:Scale></v8:NumberQualifiers>\n"),
            content_block(item("Catalog.Товары")))),

        # 7. Перечня `<Content>` нет — `empty_content`, а не отсутствующая строка
        #    (прецедент content_state узла V49; на корпусе пустых перечней 0).
        "no_content": ("БезЦелей", "a0000000-0000-0000-0000-000000000007", ca_file(
            "a0000000-0000-0000-0000-000000000007", "БезЦелей", "",
            value_type_block("xs:boolean"))),

        # 8. `<xr:Item>` без `<xr:Metadata>` — строку применения нечем ключить: файл
        #    обязан быть назван пропущенным с причиной, а не записан пустой строкой.
        "no_metadata": ("БезЦели", "a0000000-0000-0000-0000-000000000008", ca_file(
            "a0000000-0000-0000-0000-000000000008", "БезЦели", "",
            value_type_block("xs:boolean"),
            content_block("\t\t\t\t<xr:Item><xr:Use>DontUse</xr:Use>"
                          "<xr:ConditionalSeparation/></xr:Item>\n"))),

        # 9. Битый XML — та же граница отказа с текстом причины.
        "broken": ("Битый", "a0000000-0000-0000-0000-000000000009",
                   HEAD + '<CommonAttribute uuid="a0000000-0000-0000-0000-000000000009">\n'
                         "\t<Properties>\n"),

        # 10. `<Name>` пустой — строку реквизита нечем ключить (NOT BLANK по схеме).
        "no_name": ("БезИмени", "a0000000-0000-0000-0000-00000000000a",
                    HEAD + '<CommonAttribute uuid="a0000000-0000-0000-0000-00000000000a">\n'
                           "\t<Properties>\n\t\t\t<Name></Name>\n"
                           + value_type_block("xs:boolean")
                           + content_block(item("Catalog.Товары")) + TAIL),

        # 11. Файла нет в индексе состава — `file_only`; обратный случай (`index_only`)
        #     задаётся строкой индекса без файла ниже.
        "file_only": ("ВнеИндекса", "a0000000-0000-0000-0000-00000000000b", ca_file(
            "a0000000-0000-0000-0000-00000000000b", "ВнеИндекса", "",
            value_type_block("xs:boolean"), content_block(item("Catalog.Товары")))),

        # 12. uuid файла ≠ uuid строки индекса — `uuid_mismatch` называется, а не
        #     разрешается молча (замер 2.9 даёт совпадение 16/16, случай — граница).
        "uuid_mismatch": ("НесовпадениеUUID", "a0000000-0000-0000-0000-00000000000c", ca_file(
            "a0000000-0000-0000-0000-00000000000c", "НесовпадениеUUID", "",
            value_type_block("xs:boolean"), content_block(item("Catalog.Товары")))),
    }

    for file_name, _obj_uuid, text in files.values():
        (directory / f"{file_name}.xml").write_text(text, encoding="utf-8")

    # Индекс состава той же выгрузки: строки вида (с расхождениями) плюс цели применения и
    # ссылки разделения — они относятся к ДРУГИМ видам (замер 2.6: 1 512 целей BP3
    # разрешаются строками индекса целиком).
    index = [("CommonAttribute.ПометкаУдаления", "a0000000-0000-0000-0000-000000000001"),
             ("CommonAttribute.НеизвестноеСвойство", "a0000000-0000-0000-0000-000000000002"),
             ("CommonAttribute.СоставнойТип", "a0000000-0000-0000-0000-000000000003"),
             ("CommonAttribute.БезТипа", "a0000000-0000-0000-0000-000000000004"),
             ("CommonAttribute.ТолькоValueStorage", "a0000000-0000-0000-0000-000000000005"),
             ("CommonAttribute.ПустойТип", "a0000000-0000-0000-0000-000000000006"),
             ("CommonAttribute.БезЦелей", "a0000000-0000-0000-0000-000000000007"),
             ("CommonAttribute.БезЦели", "a0000000-0000-0000-0000-000000000008"),
             ("CommonAttribute.Битый", "a0000000-0000-0000-0000-000000000009"),
             ("CommonAttribute.БезИмени", "a0000000-0000-0000-0000-00000000000a"),
             # uuid строки индекса другой, чем в файле:
             ("CommonAttribute.НесовпадениеUUID", "a0000000-0000-0000-0000-0000000000ee"),
             # запись индекса без файла:
             ("CommonAttribute.ИндексБезФайла", "a0000000-0000-0000-0000-0000000000ff")]
    index += [("SessionParameter.ОбластьДанныхЗначение",
               "b0000000-0000-0000-0000-0000000000a1"),
              ("SessionParameter.ОбластьДанныхИспользование",
               "b0000000-0000-0000-0000-0000000000a2"),
              ("Constant.ИспользоватьРазделение", "b0000000-0000-0000-0000-0000000000a3")]
    index += TARGETS
    (root / "ConfigDumpInfo.xml").write_text(dump_index(index), encoding="utf-8")
    return {key: (file_name, obj_uuid)
            for key, (file_name, obj_uuid, _text) in files.items()}

# ─── проверка 1: фикстуры ─────────────────────────────────────────────────────
def load_index_rows(root: Path):
    """Строки индекса состава фиктивной выгрузки (тот же разбор, что у стадии П4)."""
    path = find_config_dump_info(root)
    if path is None:
        raise SystemExit("фикстура: ConfigDumpInfo.xml не создан")
    parsed = parse_config_dump_info(path)
    if not parsed["success"]:
        raise SystemExit("фикстура: индекс состава не разобран: %s" % parsed["error"])
    return parsed["objects"]


def row_by(rows, name):
    for row in rows:
        if row["object_name"] == name:
            return row
    return None


def check_fixtures(root: Path) -> Dict:
    emit("=== фикстуры (состояния, которых корпус не даёт)")
    fixtures = build_fixtures(root)
    index_rows = load_index_rows(root)
    result = collect_common_attributes(root, index_rows)
    rows = result["rows"]

    check("фиктур записано 12", len(fixtures) == 12, str(len(fixtures)))
    check("круг: файлов найдено 12", result["files_found"] == 12,
          "found=%d" % result["files_found"])
    check("круг: разобрано 9, пропущено 3 с причиной",
          result["files_read"] == 9 and len(result["files_failed"]) == 3,
          "read=%d failed=%s" % (result["files_read"],
                                 [(f["source_path"], f["reason"])
                                  for f in result["files_failed"]]))
    check("отказ называется текстом причины (битый XML, пустой Name, Item без Metadata)",
          all(f["reason"] for f in result["files_failed"])
          and any("XML не разобран" in (f["reason"] or "") for f in result["files_failed"])
          and any("нечем ключить" in (f["reason"] or "") for f in result["files_failed"]))
    check("наблюдений о составе каталога нет (круг плоский)",
          result["observations"] == [], str(result["observations"]))
    check("сводка success=False при пропущенных файлах", result["success"] is False)
    check("расхождения круга: index_only / file_only / uuid_mismatch названы поимённо",
          result["index_only"] == ["CommonAttribute.ИндексБезФайла"]
          and result["file_only"] == ["CommonAttributes/ВнеИндекса.xml"]
          and [item["source_path"] for item in result["uuid_mismatch"]]
          == ["CommonAttributes/НесовпадениеUUID.xml"],
          "index_only=%s file_only=%s uuid_mismatch=%s"
          % (result["index_only"], result["file_only"], result["uuid_mismatch"]))

    full = row_by(rows, "ПометкаУдаления")
    check("типичный файл разобран", full is not None)
    if full:
        check("uuid, полное имя и путь источника взяты из файла",
              full["object_uuid"] == "a0000000-0000-0000-0000-000000000001"
              and full["full_name"] == "ПометкаУдаления"
              and full["source_path"] == "CommonAttributes/ПометкаУдаления.xml")
        check("словарные свойства сохранены значениями корпуса (замер 2.7)",
              full["data_separation"] == "Separate"
              and full["indexing"] == "IndexWithAdditionalOrder"
              and full["full_text_search"] == "Use")
        check("логическое свойство читается логическим (false → False)",
              full["password_mode"] is False)
        check("одиночный тип распознан примитивом (xs:* по URI)",
              full["type_parse_state"] == STATE_PARSED
              and full["type_multiplicity"] == MULT_SINGLE
              and len(full["types"]) == 1
              and full["types"][0]["class"] == CLASS_PRIMITIVE
              and full["types"][0]["state"] == ENTRY_STATE_PARSED)
        check("ссылки разделения разрешены индексом целиком (замер 2.7: 12 из 12)",
              full["data_separation_value_parse_state"] == SEP_PARSED
              and full["data_separation_value_resolve_state"] == TARGET_EXACT
              and full["data_separation_value_object_uuid"]
              == "b0000000-0000-0000-0000-0000000000a1"
              and full["conditional_separation_parse_state"] == SEP_PARSED
              and full["conditional_separation_resolve_state"] == TARGET_EXACT)
        check("состояние свойств строки all_known, когда тегов и значений вне словаря нет",
              full["properties_state"] == PROPS_ALL_KNOWN
              and full["unknown_property_names"] is None)
        check("сверка с индексом состава: строка файла подтверждена (matched)",
              any(f["source_path"] == "CommonAttributes/ПометкаУдаления.xml"
                  for f in result["rows"])
              and full["type_raw"] is not None)
    targets = [t for t in result["targets"]
               if t["attribute_full_name"] == "CommonAttribute.ПометкаУдаления"]
    check("перечень применения: две цели в порядке файла с состояниями Use/DontUse",
          len(targets) == 2 and [t["ordinal"] for t in targets] == [0, 1]
          and targets[0]["use_state"] == USE_USED
          and targets[1]["use_state"] == USE_NOT_USED, str(targets))
    check("цель применения разрешена индексом целиком, kind по верхнему сегменту",
          bool(targets) and targets[0]["target_resolve_state"] == TARGET_EXACT
          and targets[0]["target_kind"] == "Catalog"
          and targets[0]["target_object_uuid"] == "b0000000-0000-0000-0000-0000000000c1")
    absent = row_by(rows, "БезТипа")
    check("пустые блоки разделения других файлов названы empty_value без ссылки",
          absent is not None
          and all(absent[column + "_parse_state"] == SEP_EMPTY
                  and absent[column + "_ref_text"] is None
                  and absent[column + "_resolve_state"] is None
                  for column in ("data_separation_value", "data_separation_use",
                                 "conditional_separation")))

    unknown = row_by(rows, "НеизвестноеСвойство")
    check("неизвестный тег свойства → unknown_tag со списком виновников (Q7, вариант A)",
          unknown is not None and unknown["properties_state"] == PROPS_UNKNOWN_TAG
          and unknown["unknown_property_names"] == ["AutoUse", "FuturePlatformTag"],
          str(unknown and unknown["unknown_property_names"]))
    check("unknown_tag важнее unknown_value; неизвестные значения считаются отдельно",
          unknown is not None
          and unknown["auto_use"] == "MaybeUse"
          and result["counts_by_properties_state"][PROPS_UNKNOWN_TAG] == 1
          and result["unknown_properties"] == {"FuturePlatformTag": 1}
          and result["unknown_value_properties"] == {"AutoUse": 1},
          "unknown=%s unknown_value=%s" % (result["unknown_properties"],
                                          result["unknown_value_properties"]))

    composite = row_by(rows, "СоставнойТип")
    check("кратность: три значения → composite, каждая запись разобрана (замер 2.3)",
          composite is not None and composite["type_multiplicity"] == MULT_COMPOSITE
          and len(composite["types"]) == 3
          and composite["type_parse_state"] == STATE_PARSED)
    check("повтор цели называется диагностикой, дедупликации нет (замер 2.4: повторов 0)",
          [d["target"] for d in result["duplicate_targets"]] == ["Catalog.Товары"]
          and composite is not None and composite["targets_count"] == 2)

    no_type = row_by(rows, "БезТипа")
    check("блока <Type> нет → absent + пустой массив + кратность absent (CHECK схемы)",
          no_type is not None and no_type["type_parse_state"] == STATE_ABSENT
          and no_type["type_multiplicity"] == "absent" and no_type["types"] == []
          and no_type["type_raw"] is None)

    storage = row_by(rows, "ТолькоValueStorage")
    check("содержимое <Type> вне словаря V48 2.4.2 → unknown_form, блок сохранён целиком",
          storage is not None and storage["type_parse_state"] == STATE_UNKNOWN_FORM
          and "<v8:ValueStorage>" in (storage["type_raw"] or "")
          and storage["types"][0]["class"] == "unknown"
          and result["unexpected_tags"] == {"ValueStorage": 1},
          str(storage and storage["types"]))
    check("расхождение числа тегов и числа записей называется (мера П6)",
          [m["source_path"] for m in result["value_tag_mismatch"]]
          == ["CommonAttributes/ТолькоValueStorage.xml"], str(result["value_tag_mismatch"]))

    # Закрытость словаря записи `types` — то, чего CHECK по элементу jsonb не выражает
    # (замер V48 2.5): ключи ровно TYPE_ENTRY_KEYS, ключи цели только у разрешённой
    # ссылки, `reason` ровно у записи unknown_form.
    entry_key_problems = []
    for row in rows:
        for position, entry in enumerate(row["types"]):
            allowed = set(TYPE_ENTRY_KEYS)
            if entry.get("class") == CLASS_OBJECT_REF and entry.get("resolved"):
                allowed |= set(TYPE_ENTRY_TARGET_KEYS)
            if entry.get("state") == ENTRY_STATE_UNKNOWN_FORM:
                allowed.add(TYPE_ENTRY_REASON_KEY)
            extra = sorted(set(entry) - allowed)
            missing = sorted(set(TYPE_ENTRY_KEYS) - set(entry))
            if entry.get("index") != position:
                entry_key_problems.append("%s: порядок записей потерян" % row["source_path"])
            if extra or missing:
                entry_key_problems.append("%s: запись %d extra=%s missing=%s"
                                          % (row["source_path"], position, extra, missing))
            if bool(entry.get(TYPE_ENTRY_REASON_KEY)) != (
                    entry.get("state") == ENTRY_STATE_UNKNOWN_FORM):
                entry_key_problems.append("%s: запись %d: reason не согласован с состоянием"
                                          % (row["source_path"], position))
    check("словарь записи types замкнут, reason согласован с состоянием записи",
          not entry_key_problems, str(entry_key_problems[:3]))

    empty_value = row_by(rows, "ПустойТип")
    check("пустое значение типа остаётся unknown_form, квалификаторы сохраняются",
          empty_value is not None
          and empty_value["types"][0]["value"] is None
          and empty_value["type_parse_state"] == STATE_UNKNOWN_FORM
          and "NumberQualifiers" in (empty_value["type_qualifiers"] or {}),
          str(empty_value and empty_value["type_qualifiers"]))

    no_content = row_by(rows, "БезЦелей")
    check("перечня нет → empty_content с нулевым счётчиком (прецедент content_state V49)",
          no_content is not None and no_content["content_state"] == CONTENT_EMPTY
          and no_content["targets_count"] == 0
          and result["counts_by_content_state"][CONTENT_EMPTY] == 1)
    check("непустой перечень во всех прочих разобранных строках → with_content",
          result["counts_by_content_state"][CONTENT_WITH] == 8,
          str(result["counts_by_content_state"]))

    check("счётчики состояний называются по замкнутому словарю, нули различимы",
          set(result["counts_by_type_state"]) == {STATE_PARSED, STATE_PARTIAL,
                                                 STATE_UNKNOWN_FORM, STATE_ABSENT}
          and result["counts_by_type_state"][STATE_PARTIAL] == 0
          and set(result["counts_by_target_resolve_state"]) == {TARGET_EXACT,
                                                              TARGET_PREFIX_ONLY,
                                                              TARGET_UNRESOLVED},
          str(result["counts_by_type_state"]))
    check("целей вне индекса в фикстурах не осталось: prefix_only и unresolved нулевые",
          result["counts_by_target_resolve_state"][TARGET_EXACT] == len(result["targets"])
          and result["unresolved_targets"] == [],
          str(result["counts_by_target_resolve_state"]))

    # Прямой вызов разбора одного файла: сверка с индексом состава и офлайн-граница
    # «индекс не передан» («не разрешалось» и «не разрешилось» различаются).
    single = read_registration_file(root / DIR_NAME / "ПометкаУдаления.xml",
                                   source_path="CommonAttributes/ПометкаУдаления.xml",
                                   index_by_name=None)
    check("без индекса состава сверка называется not_checked, а не matched",
          single["index_check"]["state"] == "not_checked")
    check("без индекса состава цели остаются unresolved (не «не разрешались»)",
          all(t["target_resolve_state"] == TARGET_UNRESOLVED for t in single["targets"])
          and len(single["targets"]) == 2, str(single["index_check"]))
    return result


# ─── проверка 2: словарь строк парсера против DDL ─────────────────────────────
# Колонки, которые заполняет писатель (П3), а не разбор: суррогатный ключ, ссылка на
# строку заголовка конфигурации, номер ревизии, служебные колонки витрин и связь строки
# применения со строкой реквизита (`common_attribute_id` — id конкретной ревизии, которого
# разбор знать не может). Разбор работает без живой базы и эти ключи не выдумывает.
WRITER_COLUMNS = {"id", "configuration_uuid", "created_at", "revision_no", "changed_at",
                  "changed_by", "is_committed", "common_attribute_id"}


def ddl_table_body(table: str) -> str:
    """Тело `CREATE TABLE` таблицы из текста миграции V50 (БД не открывается).

    Список колонок читается текстом, потому что П2 обязан работать без живой базы:
    несуществующая колонка всплывает у писателя на середине записи, а не до неё.
    """
    text = DDL_FILE.read_text(encoding="utf-8")
    match = re.search(r"CREATE TABLE(?: IF NOT EXISTS)?\s+" + table + r"\s*\((.*?)\n\);",
                      text, re.S)
    return match.group(1) if match else ""


def ddl_code_lines(body: str):
    """Строки тела без комментариев.

    `--` в теле — пояснение, а не элемент таблицы; в комментариях стоят и тексты
    значений (`xr:Use = DontUse`), и слова платформы. Чтение их колонками дало бы
    ложные имена, поэтому комментарии снимаются ДО обоих разборов — колонок и имён
    из ограничений.
    """
    for line in body.splitlines():
        stripped = line.split("--")[0].strip()
        if stripped:
            yield stripped


def ddl_columns(table: str) -> set:
    """Колонки таблицы из текста миграции.

    Колонку отличает форма строки — `имя ТИП[...]` (имя строчными, тип прописными);
    ограничения и их продолжения такой формы не имеют. Списка-«пропуска» здесь нет
    намеренно: имена колонок открыты, и префикс `OR` съедал колонку `ordinal`, а
    пропуск по целому слову — колонку `comment` (обе проверки падали на этом).
    """
    columns = set()
    for line in ddl_code_lines(ddl_table_body(table)):
        found = re.match(r"([a-z][a-z0-9_]*)\s+[A-Z]", line)
        if found:
            columns.add(found.group(1))
    return columns


def ddl_constraint_columns(table: str) -> set:
    """Колонки, которые называют ограничения таблицы (CHECK).

    Ограничение ссылается только на существующую колонку, поэтому перечень служит мерой
    полноты чтения текста: пропущенная колонка всплывает здесь, а не в сравнении со
    строками разбора — там она выглядела бы как «колонка не заполняется разбором», и
    чинили бы разбор вместо чтения DDL.
    """
    names = set()
    for line in ddl_code_lines(ddl_table_body(table)):
        names.update(re.findall(
            r"([a-z_][a-z0-9_]*)\s*(?:>=|<=|<>|!=|=|IS\s+NOT\s+NULL|IS\s+NULL|IS\b|IN\s*\()",
            line))
    return names


def check_ddl_columns(rows, targets) -> None:
    emit()
    emit("=== словарь строк парсера против DDL (миграция читается текстом)")
    for table, records in (("common_attributes", rows),
                          ("common_attribute_targets", targets)):
        columns = ddl_columns(table)
        check("DDL: таблицы %s в миграции не найдено" % table, bool(columns))
        if not columns:
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
        missing = sorted((columns - WRITER_COLUMNS) - keys)
        check("%s: каждая смысловая колонка DDL заполняется разбором" % table, not missing,
              "не заполняются: %s" % missing)


# ─── проверка 3: эталонные выгрузки ───────────────────────────────────────────
def check_corpora() -> None:
    emit()
    emit("=== эталонные выгрузки (числа раздела 2 плана)")
    for dump in ("MinCfg", "KomMag", "BGU2", "BP3"):
        expected = EXPECTED[dump]
        root = DUMP_ROOT / dump
        emit("-- %s" % dump)
        if not root.exists():
            check("%s: каталог выгрузки доступен" % dump, False, str(root))
            continue
        index_path = find_config_dump_info(root)
        if index_path is None:
            check("%s: индекс состава найден" % dump, False, str(root))
            continue
        parsed_index = parse_config_dump_info(index_path)
        if not parsed_index["success"]:
            check("%s: индекс состава разобран" % dump, False, parsed_index["error"])
            continue
        result = collect_common_attributes(root, parsed_index["objects"])
        check("разбор круга завершён без пропущенных файлов", result["success"],
              str(result["files_failed"]))
        check("файлов вида ровно столько, сколько измеряет план: %d" % expected["files"],
              result["files_found"] == expected["files"]
              and result["files_read"] == expected["files"],
              "found=%d read=%d" % (result["files_found"], result["files_read"]))
        if not expected["files"]:
            check("отсутствие каталога вида — наблюдение directory_missing, а не отказ (Q9)",
                  any(kind == "directory_missing" for kind, _ in result["observations"]),
                  str(result["observations"]))
            continue
        check("строк применения ровно столько, сколько измеряет план: %d"
              % expected["targets"], result["targets_total"] == expected["targets"],
              "targets=%d" % result["targets_total"])
        check("различных целей применения: %d (замер 2.4)" % expected["distinct"],
              result["targets_distinct"] == expected["distinct"],
              "distinct=%d" % result["targets_distinct"])
        check("наибольший перечень на файл: %d (замер 2.4)" % expected["max_targets"],
              result["max_targets_per_file"] == expected["max_targets"],
              "max=%d" % result["max_targets_per_file"])
        check("состояния xr:Use: Use %d, DontUse %d (замер 2.4)"
              % (expected["used"], expected["not_used"]),
              result["counts_by_use_state"][USE_USED] == expected["used"]
              and result["counts_by_use_state"][USE_NOT_USED] == expected["not_used"],
              str(result["counts_by_use_state"]))
        check("все цели разрешаются индексом целиком (замер 2.6: 1 512 из 1 512)",
              result["counts_by_target_resolve_state"][TARGET_EXACT]
              == result["targets_total"]
              and result["counts_by_target_resolve_state"][TARGET_PREFIX_ONLY] == 0
              and result["counts_by_target_resolve_state"][TARGET_UNRESOLVED] == 0,
              str(result["counts_by_target_resolve_state"]))
        check("значений <v8:Type> %d, все распознаны примитивами (замер 2.3)"
              % expected["types_total"],
              result["types_total"] == expected["types_total"]
              and result["types_parsed"] == expected["types_total"]
              and result["types_by_class"].get(CLASS_PRIMITIVE, 0) == expected["types_total"],
              "types=%d parsed=%d classes=%s" % (result["types_total"],
                                                 result["types_parsed"],
                                                 result["types_by_class"]))
        check("кратность: одиночных %d, составных %d (замер 2.3: составной один)"
              % (expected["single"], expected["composite"]),
              result["types_multiplicity"][MULT_SINGLE] == expected["single"]
              and result["types_multiplicity"][MULT_COMPOSITE] == expected["composite"],
              str(result["types_multiplicity"]))
        check("блок <Type> есть во всех файлах круга: unknown_form и absent нулевые",
              result["counts_by_type_state"][STATE_PARSED] == expected["files"]
              and result["counts_by_type_state"][STATE_UNKNOWN_FORM] == 0
              and result["counts_by_type_state"][STATE_ABSENT] == 0,
              str(result["counts_by_type_state"]))
        check("перечень применения есть во всех файлах (замер 2.4: 16/16)",
              result["counts_by_content_state"][CONTENT_WITH] == expected["files"],
              str(result["counts_by_content_state"]))
        check("свойств вида вне замкнутого словаря нет (замеры 2.2 и 2.3: ноль)",
              result["counts_by_properties_state"][PROPS_ALL_KNOWN] == expected["files"]
              and not result["unknown_properties"]
              and not result["unknown_value_properties"]
              and not result["unexpected_tags"]
              and not result["value_tag_mismatch"]
              and not result["duplicate_targets"],
              "unknown=%s values=%s tags=%s mismatch=%s dup=%s"
              % (result["unknown_properties"], result["unknown_value_properties"],
                 result["unexpected_tags"], result["value_tag_mismatch"],
                 result["duplicate_targets"]))
        check("круг сходится: расхождений с индексом состава нет (замер 2.9)",
              not result["index_only"] and not result["file_only"]
              and not result["uuid_mismatch"],
              "index_only=%s file_only=%s uuid=%s" % (result["index_only"],
                                                      result["file_only"],
                                                      result["uuid_mismatch"]))
        separated = expected.get("separation", 0)
        check("ссылок разделения непустых %d, пустых %d, неразрешённых нет (замер 2.7)"
              % (separated * 3, (expected["files"] - separated) * 3),
              result["separation_parsed"] == separated * 3
              and result["separation_empty"] == (expected["files"] - separated) * 3
              and result["separation_unknown_form"] == 0
              and not result["unresolved_refs"],
              "parsed=%d empty=%d unknown=%d refs=%s"
              % (result["separation_parsed"], result["separation_empty"],
                 result["separation_unknown_form"], result["unresolved_refs"]))
        check("предупреждений разбора нет: состояния круга замкнуты",
              not result["warnings"], "%d: %s" % (len(result["warnings"]),
                                                 result["warnings"][:3]))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v50_p2_") as tmp:
        fixture_result = check_fixtures(Path(tmp))
    check_ddl_columns(fixture_result["rows"], fixture_result["targets"])
    check_corpora()
    emit()
    emit("=== итог")
    if FAILURES:
        emit("ПРОВАЛЕНО ПРОВЕРОК: %d" % len(FAILURES))
        for name in FAILURES:
            emit("  - " + name)
    else:
        emit("все проверки пройдены")
    text = "\n".join(REPORT)
    print(text)
    out = ROOT / "_scratch" / "v50_p2_offline_probe.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())




