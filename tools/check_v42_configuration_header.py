#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v42_configuration_header.py — узел V42: заголовок держит ВСЕ свойства корня.

Узел V42 (21.10.2026): из `configurations` сняты пять колонок (четыре id предопределённых
модулей и `mobile_functionality TEXT[]`), добавлены 33 — остальные свойства `<Properties>`.
Покрытие свойств корня становится 55/55, словарь `NOT_FILLED_COLUMNS` пустеет.

Основанием служит заполненная тестовыми значениями фикстура `MinCfg` (оператор заполнил все
свойства конфигурации и выгрузил её в `.cf` и в XML, 21.10.2026 18:41). Пока свойства были
пусты, проверка могла подтвердить только наличие колонки; непустое значение доказывает и
маршрут разбора, и форму сохранённого значения.

Что проверяется и почему именно так:
  1. СХЕМА: пять снятых колонок в живой схеме отсутствуют; 33 новых присутствуют, их типы
     совпадают с `migrate_v42_configuration_header_fields.sql` (тот же класс дефекта, что
     расхождение типов между шагами установки, которое ловит `_cmp_ddl.py`); число колонок
     равно арифметике 31 - 5 + 33 + 48 (с узла V43 в таблице ещё 48 колонок-перечней,
     их перечень берётся из `src/configuration_child_properties.py`, а не печатается числом); `NOT_FILLED_COLUMNS` пуст - состояния «колонка есть, но
     не заполняется осознанно» больше нет;
  2. РАЗБОР: каждое имя свойства из `<Properties>` (независимый обход XML, а не счётчик
     парсера) имеет колонку в `CONFIGURATION_FIELDS` - слепых зон по свойствам корня не
     осталось; обратная проверка: в словаре нет имени, которого фикстура не отдаёт (опечатка
     в ключе маппинга иначе осталась бы невидимой); форма значений - multilang -> словарь,
     bool -> True, ref -> имя БЕЗ префикса вида, qualified-имя -> с префиксом целиком;
  3. ЖИВАЯ СТРОКА <-> РАЗБОР: каждая колонка строки заголовка равна значению разбора того же
     XML; пустое значение фикстуры -> NULL, и это отличается от «колонки нет». Разбор и БД
     сверяются в обе стороны: поле парсера без колонки и колонка, которую никто не заполняет,
     - обе находки называются;
  4. СОДЕРЖИМОЕ jsonb (главный смысл V42): пары `functionality` + `use` сохранены поштучно
     (число записей = число групп выгрузки, значения `use` совпадают по каждой группе);
     поля `mime`/`uti`/`ext`/`processingVariant`/`isCustom` и `baseUrl`/`useAndroid`/
     `useIOS`/`useWindows` - на месте; скалярные дети перечней сохранены текстом;
  5. ГРАНИЦА: строка обязана быть свежее файлов фикстуры. Иначе сравнение было бы сравнением
     с прошлым состоянием - тот же отдельный статус «источник новее записи» и SKIP с причиной,
     что у `_v41_three_configs_check.py` (держит правило R5);
  6. СОСТОЯНИЕ ПРОЧИХ СТРОК: у колонок V42 состоянием является дата загрузки относительно
     файла миграции V42 - до узла этих колонок не было, и пустые колонки такой строки нельзя
     читать как «свойств нет в выгрузке». У перечней V43 даты-основания нет: их заполняет не
     `<Properties>`, а индекс состава, и бэкфилл миграции пишет те же значения в строки,
     загруженные до узла (проверка по дате назвала бы «до V43» строки, у которых значения на
     месте). Состоянием перечней назван проверяемый по БД факт: длина каждого перечня равна
     числу записей этого вида верхнего уровня в `configuration_objects` той же строки, а
     пустых массивов нет. NULL при виде, которого в индексе этой выгрузки нет, - корректное
     состояние границы K1/K2 («объектов этого вида нет»), а не потеря разбора;
  7. УБОРКА: скрипт читает всё - состав БД после прогона не меняется, эталонная пара
     внешних объектов не тронута.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_v42_configuration_header.py [имя_каталога]
Код возврата 0 - все проверки пройдены. Пустой прогон (нет строки или фикстуры) - не успех:
он называется отдельно, потому что ноль проверок выглядит как «всё хорошо».
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица в консоли Windows (cp1251) - как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from configuration_child_properties import (  # noqa: E402
    CHILD_COUNT, OBJECT_TYPE_BY_COLUMN, header_array_columns)
from configuration_meta_parser import (CONFIGURATION_FIELDS,  # noqa: E402
                                      NOT_FILLED_COLUMNS, parse_configuration_meta)
from external_db import transaction  # noqa: E402

XML_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
MIGRATION = ROOT / "sql" / "migrate_v42_configuration_header_fields.sql"
DEFAULT_CASE = "MinCfg"

PASSED, FAILED, SKIPPED, INFO = [], [], [], []


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print(("PASS " if ok else "FAIL ") + name + ((" - " + str(detail)) if detail else ""))


def skip(name, reason):
    SKIPPED.append(name)
    print(f"SKIP {name} - {reason}")


def info(text):
    INFO.append(text)
    print("INFO " + text)


def section(title):
    print("\n" + title)
    print("-" * len(title))


def q(sql, params=None):
    with transaction() as cur:
        cur.execute(sql, params if isinstance(params, dict) else tuple(params or ()))
        if not cur.description:
            return []
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def read_migration_columns():
    """Пары (колонка, тип) и список снимаемых колонок из файла миграции V42."""
    text = MIGRATION.read_text(encoding="utf-8")
    new_pairs = dict(re.findall(r"\['(\w+)',\s*'([A-Z]+(?:\(\d+\))?)'\]", text))
    dropped = re.findall(
        r"'(\w+)'", re.search(r"drop_columns TEXT\[\] := ARRAY\[(.*?)\];", text, re.S).group(1))
    return new_pairs, dropped


def xml_fixture_facts(xml_path):
    """Независимый обход XML: имена свойств <Properties> и состав перечней V42.

    Обход свой, а не из парсера: иначе проверка «парсер видит все свойства» сверяла бы
    парсер с самим собой и не заметила бы пропущенное имя свойства.

    Граница, на которой первый прогон дал ноль: элементом свойства является ОДИН элемент
    (`UsedMobileApplicationFunctionalities`), а группами перечня - его прямые дети. Приняв
    сам элемент за группу, обход насчитал бы одну группу с нулём полей - ровно тот же
    класс ошибки, из-за которого `text_of` на составном элементе возвращал пустоту до V39.
    """
    root = ET.parse(str(xml_path)).getroot()
    config = next(c for c in list(root) if _local(c.tag) == "Configuration")
    properties = next((c for c in list(config) if _local(c.tag) == "Properties"), None)
    names = ([_local(c.tag) for c in list(properties) if _local(c.tag)]
             if properties is not None else [])

    def prop_element(name):
        if properties is None:
            return None
        for child in list(properties):
            if _local(child.tag) == name:
                return child
        return None

    def children(element, name):
        if element is None:
            return []
        return [c for c in list(element) if _local(c.tag) == name]

    def text_of(element):
        return (element.text or "").strip() if element is not None else ""

    def field_names(prop):
        """Имена полей записей перечня: дети каждой группы, имеющей детей."""
        fields = set()
        if prop is None:
            return fields, False
        for entry in list(prop):
            if list(entry):
                fields |= {_local(c.tag) for c in list(entry)}
        return fields, bool(fields)

    mobile_groups = []
    mobile_prop = prop_element("UsedMobileApplicationFunctionalities")
    for entry in (list(mobile_prop) if mobile_prop is not None else []):
        functionality, use = children(entry, "functionality"), children(entry, "use")
        if not functionality or not use:
            continue
        mobile_groups.append((text_of(functionality[0]), text_of(use[0]).lower()))
    share_fields, share_is_records = field_names(prop_element("AllowedIncomingShareRequestTypes"))
    url_fields, url_is_records = field_names(prop_element("MobileApplicationURLs"))
    return {"names": names, "mobile_groups": mobile_groups,
            "share_fields": share_fields, "share_is_records": share_is_records,
            "url_fields": url_fields, "url_is_records": url_is_records}


def norm(value):
    """Сопоставимая форма значения: пустое (NULL, '', пустой список/словарь) -> None.

    Пустой список/словарь приравнивается к NULL намеренно: писатель `jsonb_nullable`
    кладёт NULL именно тогда, когда значения нет, - то есть «пустого перечня» в живой схеме
    не бывает, и сравнивать с ним значило бы сравнивать с невозможным состоянием.
    Различие «поля нет» и «поле пустое» внутри JSON при этом сохраняется (None остаётся None).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (list, tuple)):
        items = [norm(v) for v in value]
        return items or None
    if isinstance(value, dict):
        items = {k: norm(v) for k, v in value.items()}
        return items or None
    if isinstance(value, datetime):
        return str(value)
    return value
def check_schema(new_pairs, dropped):
    section("1. СХЕМА V42: пять колонок сняты, 33 добавлены, типы = миграции")
    rows = q("SELECT column_name, data_type, character_maximum_length "
             "FROM information_schema.columns WHERE table_name = 'configurations'")
    live = {r["column_name"]: r for r in rows}
    for col in dropped:
        check(f"колонка configurations.{col} снята (V42)", col not in live,
              live.get(col, {}).get("data_type"))
    missing = [c for c in new_pairs if c not in live]
    check(f"все {len(new_pairs)} новых колонок V42 присутствуют", not missing, missing)

    # Тип читаётся из объявления миграции: VARCHAR(n) -> character varying(n),
    # BOOLEAN -> boolean, JSONB -> jsonb. Расхождение типов миграции и бутстрапа ловит
    # _cmp_ddl.py (сверка идёт вместе с data_type); здесь тот же контроль по отношению
    # к файлу миграции, потому что именно миграция меняет живую БД.
    type_map = {"VARCHAR": "character varying", "BOOLEAN": "boolean",
                "JSONB": "jsonb", "TEXT": "text"}
    bad = []
    for col, decl in new_pairs.items():
        got = live.get(col)
        if not got:
            continue
        match = re.match(r"([A-Z]+)(?:\((\d+)\))?", decl)
        kind, length = match.group(1), match.group(2)
        if got["data_type"] != type_map.get(kind):
            bad.append(f"{col}: миграция={decl} в БД={got['data_type']}")
        elif length and got["character_maximum_length"] != int(length):
            bad.append(f"{col}: длина {got['character_maximum_length']} вместо {length}")
    check("типы и длины новых колонок совпадают с migrate_v42_*", not bad, bad[:6])
    # Арифметика называется полностью: V42 (снято 5, добавлено 33) плюс V43 — 48
    # колонок-перечней, перечень которых взят из контракта
    # src/configuration_child_properties.py, а не из числа, подогнанного под ответ.
    v43_columns = sorted(header_array_columns())
    check(f"арифметика колонок: было 31, снято {len(dropped)}, добавлено V42 {len(new_pairs)} "
          f"+ V43 {len(v43_columns)} -> {len(live)}",
          len(live) == 31 - len(dropped) + len(new_pairs) + len(v43_columns),
          f"в живой схеме {len(live)}")
    absent = [c for c in v43_columns if c not in live]
    check(f"все {len(v43_columns)} колонок-перечней V43 (L4={CHILD_COUNT}) описаны в схеме",
          not absent and len(v43_columns) == CHILD_COUNT,
          absent[:5] or f"L4={len(v43_columns)}")
    not_array = [f"{c}: {live[c]['data_type']}" for c in v43_columns
                 if c in live and live[c]["data_type"] != "ARRAY"]
    check("колонки-перечни V43 в живой схеме имеют тип массива", not not_array, not_array[:5])
    check("NOT_FILLED_COLUMNS пуст: «колонка есть, но не заполняется» больше нет",
          not NOT_FILLED_COLUMNS, NOT_FILLED_COLUMNS)


def check_parser(case_dir, facts):
    """Разбор заполненной фикстуры: покрытие свойств корня и ФОРМА значений."""
    xml_path = os.path.join(XML_ROOT, case_dir, "Configuration.xml")
    section(f"2. РАЗБОР заполненной фикстуры {case_dir}: покрытие свойств корня")
    if not os.path.exists(xml_path):
        skip("разбор фикстуры", f"нет файла {xml_path}")
        return None
    res = parse_configuration_meta(xml_path)
    check("Configuration.xml разобран", bool(res.get("success")), res.get("error"))
    if not res.get("success"):
        return None

    header, counts = res["configuration"], res.get("counts", {})
    names = facts["names"]
    check(f"свойств <Properties>: обход XML {len(names)} = счётчик разбора",
          len(names) == counts.get("properties_total"),
          f"XML={len(names)} разбор={counts.get('properties_total')}")
    unmapped = [n for n in names if n not in CONFIGURATION_FIELDS]
    check(f"каждое из {len(names)} свойств имеет колонку (слепых зон нет)", not unmapped, unmapped)
    phantom = [n for n in CONFIGURATION_FIELDS if n not in names]
    check("в словаре маппинга нет имени, которого фикстура не отдаёт (опечатка ключа)",
          not phantom, phantom)
    check("properties_unstored = 0 (свойств без колонки не осталось)",
          counts.get("properties_unstored") == 0, counts.get("properties_unstored"))
    blind = [w for w in (res.get("warnings") or []) if "колонки в configurations нет" in w]
    check("предупреждений о свойствах без колонки разбор не даёт", not blind, blind[:3])

    # Счётчики разбора по перечню сверяются с независимым обходом: счётчик, посчитанный
    # тем же кодом, который проверяется, ничего не подтверждает.
    groups = facts["mobile_groups"]
    check(f"групп functionality/use: обход XML {len(groups)} = счётчик разбора",
          counts.get("mobile_functionalities_total") == len(groups),
          f"XML={len(groups)} разбор={counts.get('mobile_functionalities_total')}")
    check("счётчик сохранённых записей совпадает с числом групп выгрузки",
          counts.get("mobile_functionalities_stored") == len(groups),
          counts.get("mobile_functionalities_stored"))
    xml_true = sorted(name for name, use in groups if use == "true")
    check(f"разбор называет функции с use=true поимённо ({xml_true})",
          sorted(counts.get("mobile_functionalities_use_true") or []) == xml_true,
          counts.get("mobile_functionalities_use_true"))

    # Форма значений - то, чем заполненная фикстура отличается от пустой: пока значения
    # пусты, колонку можно иметь, но маршрут и форму значения проверить нельзя.
    short_info = header.get("short_info")
    check("многоязычное значение (BriefInformation) пришло словарём {язык: текст}",
          isinstance(short_info, dict) and bool(short_info.get("ru")), short_info)
    check("флаг UseManagedFormInOrdinaryApplication пришёл булевым значением True",
          header.get("use_managed_form_in_ordinary_application") is True,
          header.get("use_managed_form_in_ordinary_application"))
    check("ref-значение DefaultLanguage -> имя БЕЗ префикса вида метаданных",
          header.get("default_language") == "Русский", header.get("default_language"))
    qualified = {"default_report_form": "CommonForm.", "default_style": "Style.",
                 "default_interface": "Interface.", "common_settings_storage": "SettingsStorage.",
                 "default_constants_form": "CommonForm."}
    bad = {col: header.get(col) for col, prefix in qualified.items()
           if not str(header.get(col) or "").startswith(prefix)}
    check("qualified-имена сохранены ЦЕЛИКОМ (префикс вида несёт смысл и не снимается)",
          not bad, bad)
    return res
def check_row(case_dir, res):
    """Живая строка заголовка против разбора того же XML (контур парсер <-> БД)."""
    xml_path = os.path.join(XML_ROOT, case_dir, "Configuration.xml")
    section("3. ЖИВАЯ СТРОКА <-> РАЗБОР: значение каждой колонки равно разбору того же XML")
    rows = q("SELECT * FROM configurations WHERE uuid = %s ORDER BY id", [res["uuid"]])
    if not rows:
        skip("сверка живой строки",
             f"заголовок uuid={res['uuid']} в БД не найден: загрузите фикстуру точкой входа")
        return None
    row = rows[-1]
    created = row.get("created_at")
    source_mtime = datetime.fromtimestamp(max(os.path.getmtime(xml_path),
                                              os.path.getmtime(os.path.dirname(xml_path))))
    if created is not None and created < source_mtime:
        skip("сверка живой строки",
             f"источник новее записи (id={row['id']} created_at={created}, "
             f"файлы фикстуры {source_mtime}) - перезагрузка force=True только после "
             f"подтверждения оператора (R5); сравнивать строку с этим XML нельзя")
        return None
    info(f"строка id={row['id']} name={row['name']} created_at={created}; "
         f"файлы фикстуры не новее записи - сравнение с текущим состоянием")

    live_cols = set(row) - {"id", "created_at", "updated_at"}
    parser_cols = set(res["configuration"])
    # Перечни V43 заполняет индекс состава, а не `<Properties>`, поэтому их отсутствие в
    # контракте разбора корня — состояние модели, а не слепая зона. Разрыв «схема минус
    # разбор» обязан быть ровно этим множеством: лишняя колонка иначе осталась бы невидимой.
    v43_columns = set(header_array_columns())
    only_parser = sorted(parser_cols - live_cols)
    only_db = sorted((live_cols - parser_cols) - v43_columns)
    gap = sorted((live_cols - parser_cols) & v43_columns)
    check("поля разбора без колонки в схеме нет", not only_parser, only_parser)
    check("колонки заголовка, которую загрузчик корня не описывает, нет "
          "(перечни V43 названы отдельно)", not only_db, only_db)
    check(f"разрыв «схема минус разбор корня» равен ровно {len(v43_columns)} перечням V43",
          gap == sorted(v43_columns), sorted(v43_columns - set(gap))[:5])

    common = sorted(live_cols & parser_cols)
    diffs = []
    for col in common:
        if norm(row[col]) != norm(res["configuration"][col]):
            diffs.append(f"{col}: в БД={row[col]!r} разбор={res['configuration'][col]!r}")
    check(f"значения всех {len(common)} колонок совпадают с разбором", not diffs, diffs[:8])

    # Счётчик непустых считается только по колонкам, источником которых является
    # `<Properties>`: сверять с разбором корня колонки, заполненные индексом состава,
    # значило бы сравнивать два разных источника и называть расхождение дефектом.
    stored_nonempty = sum(1 for col in common if norm(row[col]) is not None)
    parsed_nonempty = sum(1 for col in parser_cols if norm(res["configuration"][col]) is not None)
    check(f"непустых колонок корня {stored_nonempty} - ровно столько, сколько заполнено разбором",
          stored_nonempty == parsed_nonempty, f"разбор даёт {parsed_nonempty}")
    empty_by_design = sorted(col for col in common if norm(row[col]) is None)
    info(f"пустые свойства фикстуры сохранены как NULL ({len(empty_by_design)}): "
         + ", ".join(empty_by_design))
    v43_filled = [c for c in v43_columns if row.get(c)]
    v43_empty = [OBJECT_TYPE_BY_COLUMN[c] for c in v43_columns if not row.get(c)]
    info(f"перечней V43 заполнено индексом состава: {len(v43_filled)}/{len(v43_columns)}; "
         f"пустых массивов загрузчик не пишет: вида нет в индексе этой выгрузки — "
         f"колонка остаётся NULL (тот же контракт пустого состояния, что у V39/V42). "
         f"Пустых колонок {len(v43_empty)}: "
         + (", ".join(v43_empty) if v43_empty else "нет"))
    for col in ("content", "name_prefix", "update_url", "default_search_form",
                "required_mobile_application_permissions", "detailed_info"):
        if col in row:
            check(f"пустое свойство {col} -> NULL, а не пустая строка/список",
                  norm(row[col]) is None, row[col])
    return row


def check_jsonb_content(row, facts):
    """Главный смысл V42: перечень записей сохраняется парами, а не разъезжается."""
    section("4. СОДЕРЖИМОЕ jsonb (V42): пары перечней сохранены, а не разъехались")
    groups = facts["mobile_groups"]
    stored = row.get("mobile_application_functionalities") or []
    check(f"записей в mobile_application_functionalities = групп выгрузки ({len(groups)})",
          len(stored) == len(groups), f"в колонке {len(stored)}")
    pairs = [((rec.get("functionality") or ""), str(rec.get("use")).lower())
             for rec in stored if isinstance(rec, dict)]
    first_bad = next(((a, b) for a, b in zip(pairs, groups) if a != b), None)
    check("пары functionality/use сохранены поштучно и в порядке выгрузки",
          len(pairs) == len(groups) and pairs == groups, first_bad)
    lost_use = [rec for rec in stored if "use" not in (rec or {})]
    check("признак use есть у каждой записи (TEXT[] его терял)", not lost_use, lost_use[:2])
    check("значение use сохранено строкой выгрузки, а не выведено из текста",
          all(str(rec.get("use")).lower() in ("true", "false") for rec in stored),
          [rec.get("use") for rec in stored][:5])
    stored_true = sorted(rec.get("functionality") for rec in stored
                         if str(rec.get("use")).lower() == "true")
    xml_true = sorted(name for name, use in groups if use == "true")
    check(f"истинные значения use сохранены и не съехали ({xml_true})",
          stored_true == xml_true, f"в колонке {stored_true}")

    for column, fields_key, flag_key in (
            ("allowed_incoming_share_request_types", "share_fields", "share_is_records"),
            ("mobile_application_urls", "url_fields", "url_is_records")):
        records = row.get(column) or []
        want = facts[fields_key]
        if facts[flag_key]:
            missing = sorted(f for rec in records for f in want if f not in (rec or {}))
            check(f"поля записей перечня {column} сохранены ({sorted(want)})",
                  bool(records) and not missing, missing or records[:1])
        else:
            check(f"перечень {column}: форма детей выгрузкой не подтверждена, "
                  f"пустое значение -> NULL", not records, records[:1])
    for col in ("additional_full_text_search_dictionaries",
                "standalone_configuration_restriction_roles"):
        value = row.get(col) or []
        check(f"скалярные дети перечня {col} сохранены текстом (квалифицированное имя)",
              bool(value) and all(isinstance(v, str) and "." in v for v in value), value)
def check_other_rows(new_pairs):
    """Состояние каждой строки `configurations`: колонки V42 - по дате узла, перечни V43 - по индексу.

    Колонки V42: строка, загруженная до узла, физически не может держать 33 новых значения -
    колонок тогда не было. Это не провал и не данные о конфигурации, это состояние записи, и
    оно обязано быть названо, иначе пустые колонки читаются как «в конфигурации этих свойств
    нет». Граница здесь - mtime файла миграции V42: он и есть момент, когда колонки появились.

    Перечни V43 так же по дате не проверяются, и это не небрежность, а другое состояние модели:
    значения колонок берёт не `<Properties>`, а индекс состава, и бэкфилл миграции заполнил их
    из уже загруженного `configuration_objects`. Значит дата загрузки о перечнях не говорит
    ничего (первый вариант проверки по дате назвал бы «до V43» строки, у которых значения на
    месте - BGU2, BP3, KomMag). Состоянием считается единственный проверяемый по БД факт:
    длина каждого перечня равна числу записей этого вида верхнего уровня в индексе той же
    строки - то же выражение, которым `_v43_live_check.py` подтвердил нулевые расхождения.
    Расхождение и есть единственное основание сказать «требуется перезагрузка force=True» (по
    R5 - только после подтверждения оператора). Пустой массив - нарушение контракта V43: пустое
    состояние выражено NULL, поэтому отдельная проверка держит и это.
    """
    section("5. СОСТОЯНИЕ ПРОЧИХ ЗАГОЛОВКОВ: колонки V42 по дате узла, перечни V43 по индексу")
    boundary = datetime.fromtimestamp(MIGRATION.stat().st_mtime)
    v43_columns = list(header_array_columns())
    rows = q("SELECT id, name, created_at FROM configurations ORDER BY id")
    stale = []
    inconsistent = []
    empty_arrays = []
    for row in rows:
        # Сумма идёт по булевым выражениям, а не SUM(arg, arg, ...): агрегат так не
        # вызывается (первый прогон упал UndefinedFunction: function sum(integer, ...)).
        expr = " + ".join(f"({col} IS NOT NULL)::int" for col in sorted(new_pairs))
        filled = q(f"SELECT COALESCE(({expr}), 0) AS filled FROM configurations "
                   f"WHERE id = %s", [row["id"]])[0]["filled"]
        created = row["created_at"]
        state = "V42-текущая" if (created is None or created >= boundary) else "загружена до V42"
        info(f"id={row['id']} name={row['name']} created_at={created} "
             f"заполнено новых колонок: {filled}/{len(new_pairs)} - {state}")
        if state == "загружена до V42":
            stale.append(f"{row['name']} (id={row['id']})")
        # Перечни: число элементов каждой колонки против числа записей того же вида верхнего
        # уровня (depth = 0) в индексе этой же конфигурации. Пара «колонка - вид» берётся из
        # CHILD_PROPERTIES - своего перечня видов здесь быть не должно.
        idx = {rec["object_type"]: rec["n"] for rec in q(
            "SELECT object_type, count(*) AS n FROM configuration_objects "
            "WHERE configuration_id = %s AND depth = 0 GROUP BY object_type", [row["id"]])}
        got = q(f"SELECT {', '.join(v43_columns)} FROM configurations WHERE id = %s",
                [row["id"]])[0]
        mismatch, filled43, objects43, kinds_absent = [], 0, 0, []
        for column in v43_columns:
            value = got[column]
            want = idx.get(OBJECT_TYPE_BY_COLUMN[column], 0)
            have = 0 if value is None else len(value)
            if value is None:
                if want:
                    kinds_absent.append(f"{OBJECT_TYPE_BY_COLUMN[column]} (индекс ждёт {want})")
            else:
                filled43 += 1
                objects43 += have
                if have == 0:
                    empty_arrays.append(f"id={row['id']}.{column}")
            if have != want:
                mismatch.append(f"{column}: в колонке {have}, в индексе {want}")
        check(f"перечни V43 строки id={row['id']} согласованы с её индексом состава",
              not mismatch, mismatch[:6])
        info(f"    перечней V43: заполнено {filled43}/{len(v43_columns)}, "
             f"объектов в перечнях {objects43}; видов этих в индексе выгрузки нет: "
             + (", ".join(kinds_absent) if kinds_absent else "нет"))
        if mismatch:
            inconsistent.append(f"{row['name']} (id={row['id']})")
    if stale:
        info("требуют перезагрузки force=True (по R5 - только после подтверждения оператора): "
             + ", ".join(stale))
    else:
        info("заголовков, загруженных до V42, в БД нет")
    check("пустых массивов в колонках-перечнях V43 нет: пустое состояние выражено NULL",
          not empty_arrays, empty_arrays[:6])
    if inconsistent:
        info("перечни этих заголовков разошлись с их индексом состава - требуется "
             "перезагрузка force=True (по R5 - только после подтверждения оператора): "
             + ", ".join(inconsistent))
    else:
        info("строк, перечни которых разошлись с индексом состава, нет: бэкфилл миграции "
             "заполняет перечни из уже загруженного индекса, поэтому дата загрузки строки о "
             "перечнях V43 не говорит ничего")


def counts():
    return {table: q(f"SELECT count(*) AS c FROM {table}")[0]["c"]
            for table in ("configurations", "configuration_objects", "external_report")}


def main():
    case = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CASE
    new_pairs, dropped = read_migration_columns()
    xml_path = os.path.join(XML_ROOT, case, "Configuration.xml")
    if not os.path.exists(xml_path):
        print(f"❌ Фикстура не найдена: {xml_path}")
        return 1
    print(f"Основание: фикстура {case} ({xml_path}); "
          f"миграция {MIGRATION.name}: снято {len(dropped)}, добавлено {len(new_pairs)}")
    before = counts()
    facts = xml_fixture_facts(xml_path)
    info(f"свойств <Properties> в фикстуре: {len(facts['names'])}, "
         f"групп functionality/use: {len(facts['mobile_groups'])}")

    check_schema(new_pairs, dropped)
    res = check_parser(case, facts)
    if res and res.get("success"):
        row = check_row(case, res)
        if row is not None:
            check_jsonb_content(row, facts)
    check_other_rows(new_pairs)

    section("6. УБОРКА: скрипт только читает")
    after = counts()
    check("состав БД после прогона не изменился", before == after, f"до={before} после={after}")
    check("эталонная пара внешних объектов не тронута",
          before["external_report"] == after["external_report"], after["external_report"])

    total = len(PASSED) + len(FAILED)
    print(f"\nИТОГ: проверок {total}, провалено {len(FAILED)}, пропущено {len(SKIPPED)}, "
          f"справок {len(INFO)}")
    if FAILED:
        print("Провалено:")
        for name in FAILED:
            print("  -", name)
    if not PASSED:
        print("❌ ПУСТОЙ ПРОГОН: ни одной пройденной проверки - это не подтверждение узла")
        return 1
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())




