#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v48_session_parameters.py — узел V48: свойства параметров сеанса.

Узел V48 (29.10.2026, позиция 2.3 нормативного списка «Структура конфигурации.txt»):
стадия `s4c_session_parameters` и отдельный вход `load_session_parameters_tool` пишут
свойства вида `SessionParameters/` в таблицу `session_parameters`. Норматив —
`docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md` (раздел 2 — замеры корпуса, раздел 4 —
модель схемы по решениям Q1–Q7, раздел 7 — критерии готовности узла).

Зачем узлу постоянная проверка. XSD вида нет (замер 2.6: 35 схем, `SessionParameter` не
встречается ни в одной), поэтому схемной верификации разбора быть не может — договорённость
узла держится эталоном по корпусу (числа раздела 2) плюс этой проверкой (решение Q6).
Второй класс того, что не выражается CHECK: словарь записи `types` и кратность по числу
`<v8:Type>` в файле. БД отклоняет любой CHECK по отдельной записи массива текстом
«cannot use subquery in check constraint», пропускает лишние ключи и дубликат второй записи
(замер 2.5) — значит словарь `TYPE_ENTRY_KEYS` и равенство «число записей = число тегов»
сторожит только проверка.

Проверка строится по образцу `tools/check_v47_configuration_object_modules.py`: каждый
контур считается по СВОЕМУ источнику, а не по следующему месту, и круг берётся не списком
имён в скрипте, а строками заголовков базы (правило одного источника).

Что проверяется и почему именно так:

  1. ГРАНИЦА КРУГА (контур 1): записи индекса состава вида одним агрегатным `COUNT` и
     построчным обходом того же условия — два числа обязаны совпасть; иначе условие круга
     разъезжается первым же новым видом (тот же класс дефекта, что «19 428 вместо 13 389»
     пробы П2 узла V47).
  2. РАВЕНСТВО МНОЖЕСТВ ИМЁН (контур 1, решение Q7 варианта A, ответ оператора
     29.10.2026): колонка `configurations.session_parameters[]` остаётся перечнем имён вида
     (контракт V43), таблица — содержимым; внешнего ключа в схеме нет осознанно (прецедент
     V20.1), поэтому инвариант «множество `object_name` таблицы = перечню заголовка =
     `object_name` индекса состава вида» кладётся сюда. Две копии одного знания без этого
     инварианта разъезжаются молча.
  3. ФАЙЛ ↔ СТРОКА БД (контур 2): каждая строка обязана существовать только там, где есть
     файл круга, и каждая колонка строки обязана совпадать со значением, которое отдаёт
     РАЗБОР этого файла (`read_registration_file`) — иначе писатель терял или подменял поле.
     Лишняя строка без файла называется именем, а не числом.
  4. МЕРЫ ФАЙЛА ↔ `types` (контур 3): число записей массива равняется числу тегов
     `<v8:Type>`, посчитанному по исходному тексту файла (`count_value_type_tags` — другой
     код, чем обход XML в `normalize_type_block`); `type_raw` равняется блоку исходным
     текстом; кратность равна `multiplicity_of(число тегов)`. Это ровно то, что не
     выражается CHECK (замер 2.5), и ровно то, что теряется при «прочитали первое значение»
     — прежний зонд `_v48_p0_ref_probe.py` считал файлы и давал «22 вместо 24».
  5. СЛОВАРЬ ЗАПИСИ `types` (контур 4): ключи записи — ровно `TYPE_ENTRY_KEYS`, ключи цели
     — только у разрешённого `object_ref` (прецедент D3: отсутствие ключа читается как
     «цели нет», `null` читался бы как «цель есть, но пустая»); классы и состояния — внутри
     замкнутых словарей разбора; дубликатов одного `value` в строке нет.
  6. РАЗРЕШЁННОСТЬ ССЫЛОК (контур 4): цель каждой разрешённой записи существует в индексе
     состава ТОЙ ЖЕ конфигурации, а её `target_object_uuid`/`target_object_type` равны
     колонкам этой записи индекса. Разрешение по всей таблице без границы конфигурации
     дало бы ложный успех на общей базе (замер 2.5: 24 из 24 целей — объекты других видов).
  7. ПРИМИТИВНОСТЬ ВИДА (контур 5): утверждение оператора от 29.10.2026 («группа
     примитивна») — замер, а не свойство платформы, поэтому круг таблиц берётся из живой
     схемы (`information_schema.columns`, колонка `parent_uuid`), а не из комментария к DDL:
     ни в одной из них не должно быть строки с `parent_uuid` = uuid параметра сеанса.
     Появление строки — не молчаливое расхождение, а сигнал пересмотреть границы узла
     (критерий 4а раздела 7). Тот же сторож со стороны выгрузки: каталог вида без
     подкаталогов и не-XML, детей вида в индексе состава нет.
  8. ВИТРИНА И КЛЮЧ ЦЕПОЧКИ (контур 6): определение уникального индекса живой схемы
     обязано называть `(configuration_uuid, object_name, revision_no)` — ключ по uuid
     метаданных не годится, потому что 82 из 125 uuid вида встречаются в двух и более
     конфигурациях (`_v48_q2_key_probe.py`); витрина отдаёт ровно по одной текущей строке на
     ключ и называется именем из реестра `current_view()`. Различение двух конфигураций
     доказывается фактом: имя, общее для двух конфигураций, остаётся в витрине двумя
     строками.
  9. ГРАНИЦА R5, СИРОТЫ, НЕПРИКОСНОВЕННОСТЬ (контуры 7–8): строки обязаны быть свежее
     файлов выгрузки, иначе сравнение было бы сравнением с прошлым состоянием (отдельный
     SKIP с причиной, а не успех); сирот по заголовку нет; чужие строки за прогон не
     меняются — проверка только читает.
 10. ИТОГ (контур 9): суммы по сравненным конфигурациям равны числам плана (раздел 2), а
     при полном круге — и корпусные числа: 207 строк, 213 записей `types`, 24 ссылки, 8
     различных целей, `single` 201 / `composite` 6, GIN-запрос по тяжёлой цели отдаёт 8
     параметров. Одиночный прогон называет, чего он не сравнивает: молчание читалось бы
     как «числа предместа сошлись».

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_v48_session_parameters.py [MinCfg|KomMag|BGU2|BP3|all]
По умолчанию — `all`: все строки заголовков, для которых находится каталог выгрузки.
Код возврата 0 — расхождений нет. Пропуск контуров называется причиной (нет строки
заголовка, нет выгрузки, строк узла не загружалось, выгрузка новее записей): ноль
проверок не читается как «всё хорошо».
"""

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица в консоли Windows (cp1251) - как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from configuration_load_contract import SESSION_PARAMETER_TABLE  # noqa: E402
from configuration_module_slots import resolve_dump_dir  # noqa: E402
from configuration_session_parameters import (  # noqa: E402
    CLASS_OBJECT_REF, DIR_NAME, INDEX_OBJECT_TYPE, MULTIPLICITY_VALUES, RECORD_STATES,
    TYPE_CLASS_VALUES, TYPE_ENTRY_KEYS, TYPE_ENTRY_TARGET_KEYS, count_value_type_tags,
    index_rows_by_name, iter_registration_files, kind_index_rows, multiplicity_of,
    raw_type_block, read_registration_file, read_text_file,
)
from configuration_session_parameters_loader import read_index_records  # noqa: E402
from current_revision import current_view  # noqa: E402
from external_db import transaction  # noqa: E402

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_SCOPE = "all"
# Сколько расхождений называется именами (дальше — только число).
MAX_NAMES = 10

# ── ожидания проверки (числа плана docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md) ───
# Раздел 2.1–2.5 и 2.7 (замеры 28–29.10.2026), воспроизводимые зондами `_v48_p0_probe.py`,
# `_v48_p0_index_probe.py`, `_v48_q4_ref_probe.py`. Числа названы по каталогу выгрузки, а
# не по имени строки заголовка: имя строки меняется вместе с выгрузкой, каталог — адрес,
# по которому проверка находит файлы.
PLAN_EXPECTATIONS = {
    "MinCfg": {"files": 2, "index": 2, "header": 2, "rows": 2,
               "single": 2, "composite": 0, "mult_absent": 0,
               "parsed": 2, "raw_filled": 2, "comments": 2,
               "entries": 2, "object_ref": 1, "resolved": 1, "unresolved": 0,
               "targets": 1, "defined_ref": 0, "unknown_cls": 0, "primitive_cls": 1,
               "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
               "observations": 0, "children": 0, "parent_refs": 0},
    "KomMag": {"files": 6, "index": 6, "header": 6, "rows": 6,
               "single": 6, "composite": 0, "mult_absent": 0,
               "parsed": 6, "raw_filled": 6, "comments": 0,
               "entries": 6, "object_ref": 0, "resolved": 0, "unresolved": 0,
               "targets": 0, "defined_ref": 0, "unknown_cls": 0, "primitive_cls": 6,
               "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
               "observations": 0, "children": 0, "parent_refs": 0},
    "BGU2": {"files": 101, "index": 101, "header": 101, "rows": 101,
             "single": 98, "composite": 3, "mult_absent": 0,
             "parsed": 101, "raw_filled": 101, "comments": 9,
             "entries": 104, "object_ref": 12, "resolved": 12, "unresolved": 0,
             "targets": 7, "defined_ref": 0, "unknown_cls": 0, "primitive_cls": 92,
             "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
             "observations": 0, "children": 0, "parent_refs": 0},
    "BP3": {"files": 98, "index": 98, "header": 98, "rows": 98,
            "single": 95, "composite": 3, "mult_absent": 0,
            "parsed": 98, "raw_filled": 98, "comments": 5,
            "entries": 101, "object_ref": 11, "resolved": 11, "unresolved": 0,
            "targets": 6, "defined_ref": 0, "unknown_cls": 0, "primitive_cls": 90,
            "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
            "observations": 0, "children": 0, "parent_refs": 0},
}
# Корпусные числа (сверяются только при полном круге из четырёх выгрузок): разделы 2.4.3,
# 2.5, 2.7 и замер `_v48_q2_key_probe.py` — те же 125/82/123/84, которыми обоснован ключ
# цепочки состояния в разделе 4 плана.
CORPUS_EXPECTATIONS = {
    "rows": 207, "entries": 213, "object_ref": 24, "resolved": 24, "targets": 8,
    "single": 201, "composite": 6, "mult_absent": 0, "comments": 16,
    "distinct_uuids": 125, "uuid_shared": 82, "distinct_names": 123,
    "names_shared": 84, "heaviest_links": 8,
}
# Тяжёлая цель ссылочного типа (замер 2.5: 8 ссылок) — ей проверяется запрос по GIN.
HEAVIEST_TARGET = "Catalog.НаборыГруппДоступа"
# Ключ цепочки состояния (решение Q2) и имя GIN-индекса по содержимому `types`.
KEY_INDEX = "session_parameters_configuration_object_revision_key"
KEY_COLUMNS = "(configuration_uuid, object_name, revision_no)"
GIN_INDEX = "idx_session_parameters_types_gin"

PASSED, FAILED, SKIPPED, INFO = [], [], [], []


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print(("PASS " if ok else "FAIL ") + name + (("\n      - " + str(detail)) if detail else ""))


def skip(name, reason):
    SKIPPED.append(name)
    print(f"SKIP {name} - {reason}")


def info(text):
    INFO.append(text)
    print("INFO " + text)


def section(title):
    print("\n" + title)
    print("-" * len(title))


def q(cur, sql, params=None):
    cur.execute(sql, params or ())
    if not cur.description:
        return []
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def one(cur, sql, params=None):
    rows = q(cur, sql, params)
    return rows[0] if rows else {}


def names(sample):
    """Сколько расхождений называется именами — дальше только число."""
    shown = list(sample)[:MAX_NAMES]
    tail = "" if len(sample) <= MAX_NAMES else f" … ещё {len(sample) - MAX_NAMES}"
    return ", ".join(str(item) for item in shown) + tail

# ── обход источников: строки БД, перечень заголовка, каталог выгрузки, разбор ───────
def read_db_rows(cur, configuration_uuid):
    """Строки узла этой конфигурации (граница та же, что у снятия писателя)."""
    return q(cur, f"""
        SELECT id, configuration_uuid::text AS configuration_uuid,
               object_uuid::text AS object_uuid, object_name, full_name, comment,
               synonym, type_raw, type_multiplicity, type_parse_state, types,
               type_qualifiers, source_path, revision_no, changed_at, changed_by,
               is_committed
          FROM {SESSION_PARAMETER_TABLE}
         WHERE configuration_uuid = %(configuration_uuid)s::uuid
         ORDER BY object_name, id
    """, {"configuration_uuid": str(configuration_uuid)})


def read_header_list(cur, configuration_uuid):
    """Перечень имён вида из строки заголовка (колонка V43, а не таблица узла).

    Иначе сравнение множеств сравнивало бы один набор с самим собой: инвариант Q7
    существует ровно потому, что источник здесь другой.
    """
    row = one(cur, "SELECT coalesce(session_parameters, '{}'::text[]) AS names "
                   "FROM configurations WHERE uuid = %(uuid)s::uuid",
              {"uuid": str(configuration_uuid)})
    return [str(item) for item in (row.get("names") or [])]


def read_disk_circle(dump_dir):
    """Файлы круга без чтения содержимого + наблюдения о составе каталога."""
    files, observations = iter_registration_files(dump_dir)
    by_stem = {}
    for item in files:
        by_stem.setdefault(Path(item["file_name"]).stem, item)
    return files, by_stem, observations


def parse_disk_rows(dump_dir, index_rows):
    """Разобрать круг ТЕМ ЖЕ модулем разбора, что и загрузка.

    Сравнение строки с файлом идёт по разбору, а не по второй реализации чтения XML:
    иначе проверка проверяла бы саму себя, а не то, донёс ли писатель строку.
    """
    by_name = index_rows_by_name(index_rows)
    parsed, failures = {}, []
    for item in iter_registration_files(dump_dir)[0]:
        result = read_registration_file(item["path"], source_path=item["rel_path"],
                                        index_by_name=by_name)
        if not result["success"]:
            failures.append({"source_path": item["rel_path"], "reason": result["reason"]})
            continue
        parsed[result["row"]["object_name"]] = result
    return parsed, failures


ROW_FIELDS = ("object_uuid", "object_name", "full_name", "comment", "synonym",
              "type_raw", "type_multiplicity", "type_parse_state", "types",
              "type_qualifiers", "source_path")


def _brief(value):
    text = repr(value)
    return text if len(text) <= 160 else text[:160] + "…"

# ── контур 1: граница круга и равенство множеств имён (Q7, вариант A) ───────────────
def check_circle_sources(cur, header, dump_dir, index_info, expect, tag):
    """Индекс состава ↔ каталог выгрузки ↔ перечень заголовка ↔ строки таблицы."""
    cfg_uuid = str(header["uuid"])
    aggregate = int(one(cur,
                       "SELECT count(*) AS c FROM configuration_objects "
                       "WHERE configuration_id = %s AND object_type = %s",
                       (int(header["id"]), INDEX_OBJECT_TYPE)).get("c") or 0)
    kind_rows = kind_index_rows(index_info["rows"])
    index_names = {str(row["object_name"]) for row in kind_rows if row.get("object_name")}
    files, by_stem, observations = read_disk_circle(dump_dir)
    header_names = read_header_list(cur, cfg_uuid)
    db_rows = read_db_rows(cur, cfg_uuid)
    table_names = {row["object_name"] for row in db_rows}

    check(f"{tag}: записи индекса состава вида агрегатом и построчным обходом дают одно число",
          aggregate == len(kind_rows), f"агрегат: {aggregate}, обход: {len(kind_rows)}")
    check(f"{tag}: записей индекса состава вида ровно {expect['index']}",
          len(kind_rows) == expect["index"], f"факт: {len(kind_rows)}")
    check(f"{tag}: файлов регистрации вида в каталоге ровно {expect['files']}",
          len(files) == expect["files"], f"факт: {len(files)}")
    check(f"{tag}: каталог вида без подкаталогов и файлов не-XML (сторож примитивности, 2.3)",
          len(observations) == expect["observations"], _brief(observations[:MAX_NAMES]))

    only_index = sorted(index_names - set(by_stem))
    only_files = sorted(set(by_stem) - index_names)
    check(f"{tag}: состояний `index_only` = {expect['index_only']} и `file_only` = "
          f"{expect['file_only']} (объявлен без файла / файл вне перечня)",
          len(only_index) == expect["index_only"] and len(only_files) == expect["file_only"],
          f"только в индексе: {names(only_index)}; только файлы: {names(only_files)}")
    check(f"{tag}: множество `object_name` таблицы равно перечню заголовка и `object_name` "
          f"индекса состава (Q7, вариант A оператора 29.10.2026)",
          table_names == set(header_names) == index_names,
          f"таблица: {len(table_names)}, заголовок: {len(header_names)}, "
          f"индекс: {len(index_names)}; расхождения: "
          f"таблица^заголовок={names(table_names ^ set(header_names))}; "
          f"таблица^индекс={names(table_names ^ index_names)}")
    check(f"{tag}: строк узла в таблице ровно {expect['rows']}, имён в перечне заголовка "
          f"ровно {expect['header']}",
          len(db_rows) == expect["rows"] and len(header_names) == expect["header"],
          f"строк: {len(db_rows)}, перечень: {len(header_names)}")
    return {"db_rows": db_rows, "kind_rows": kind_rows, "index_names": index_names,
            "files": files, "by_stem": by_stem, "observations": observations,
            "header_names": header_names, "only_index": only_index,
            "only_files": only_files}


# ── контур 2: файл ↔ строка БД ──────────────────────────────────────────────────────
def check_rows_against_files(parsed, failures, db_rows, expect, tag):
    """Каждая колонка строки обязана совпадать с разбором файла круга."""
    by_name = {row["object_name"]: row for row in db_rows}
    check(f"{tag}: отказов разбора файлов круга нет ({len(parsed)} файлов разобраны)",
          not failures, _brief(failures[:MAX_NAMES]))
    missing = sorted(set(parsed) - set(by_name))
    extra = sorted(set(by_name) - set(parsed))
    check(f"{tag}: файла без строки и строки без файла нет", not missing and not extra,
          f"файл без строки: {names(missing)}; строка без файла: {names(extra)}")

    diffs = {}
    for name, result in sorted(parsed.items()):
        row = by_name.get(name)
        if row is None:
            continue
        for field in ROW_FIELDS:
            if row.get(field) != result["row"].get(field):
                diffs.setdefault(field, []).append(
                    (name, _brief(row.get(field)), _brief(result["row"].get(field))))
    check(f"{tag}: все колонки строк совпадают с разбором файла (писатель не терял полей)",
          not diffs,
          "; ".join(f"{field}: {len(items)} — {_brief(items[0])}"
                    for field, items in sorted(diffs.items())) or "")

    mismatch = [item for item in parsed.values()
                if item["index_check"]["state"] == "uuid_mismatch"]
    file_only = [item for item in parsed.values()
                 if item["index_check"]["state"] == "file_only"]
    check(f"{tag}: расхождений uuid файла и записи индекса ровно {expect['uuid_mismatch']}",
          len(mismatch) == expect["uuid_mismatch"] and len(file_only) == expect["file_only"],
          _brief([(item["index_check"].get("index_name"), item["index_check"]["state"])
                  for item in (mismatch + file_only)][:MAX_NAMES]))
    return by_name


# ── контур 3: меры файла ↔ `types` (то, что не выражается CHECK) ────────────────────
def check_file_measures(dump_dir, db_rows, expect, tag):
    """Число записей jsonb = число тегов `<v8:Type>` в исходном тексте блока."""
    bad = {"tags": [], "raw": [], "multiplicity": [], "state": [], "unread": []}
    states = Counter()
    multiplicity = Counter()
    raw_filled = 0
    comments = 0
    for row in db_rows:
        text, error = read_text_file(Path(dump_dir) / str(row["source_path"]))
        if text is None:
            bad["unread"].append((row["object_name"], error))
            continue
        raw = raw_type_block(text)
        tags = count_value_type_tags(raw)
        entries = row["types"] or []
        if len(entries) != tags:
            bad["tags"].append((row["object_name"], tags, len(entries)))
        if (row["type_raw"] or "") != (raw or ""):
            bad["raw"].append((row["object_name"], _brief(raw), _brief(row["type_raw"])))
        if row["type_multiplicity"] != multiplicity_of(tags):
            bad["multiplicity"].append(
                (row["object_name"], multiplicity_of(tags), row["type_multiplicity"]))
        if bool(entries) != (row["type_parse_state"] != "absent"):
            bad["state"].append((row["object_name"], row["type_parse_state"], len(entries)))
        states[row["type_parse_state"]] += 1
        multiplicity[row["type_multiplicity"]] += 1
        if row["type_raw"]:
            raw_filled += 1
        if (row["comment"] or "").strip():
            comments += 1

    for key, label in (("unread", "файл строки не читается"),
                       ("tags", "число записей `types` не равно числу тегов `<v8:Type>`"),
                       ("raw", "`type_raw` не равен блоку `<Type>` исходным текстом"),
                       ("multiplicity", "`type_multiplicity` не равна формуле по числу тегов"),
                       ("state", "пустой массив `types` противоречит состоянию строки")):
        check(f"{tag}: {label} — расхождений нет", not bad[key], _brief(bad[key][:MAX_NAMES]))

    others = {state: count for state, count in states.items() if state != "parsed"}
    check(f"{tag}: состояний разбора — `{expect['parsed']}` строк `parsed`, других состояний "
          f"нет (`unknown_form` и `partial` назвали бы новую форму)",
          states.get("parsed", 0) == expect["parsed"] and not others,
          _brief(dict(states)))
    check(f"{tag}: кратность строк: `single` {expect['single']}, `composite` "
          f"{expect['composite']}, `absent` {expect['mult_absent']} (замер 2.4.3)",
          multiplicity.get("single", 0) == expect["single"]
          and multiplicity.get("composite", 0) == expect["composite"]
          and multiplicity.get("absent", 0) == expect["mult_absent"],
          _brief(dict(multiplicity)))
    check(f"{tag}: `type_raw` заполнен у всех {expect['raw_filled']} строк (полнота источника)",
          raw_filled == expect["raw_filled"], f"факт: {raw_filled}")
    check(f"{tag}: непустых `Comment` ровно {expect['comments']} (замер 2.7)",
          comments == expect["comments"], f"факт: {comments}")
    return states, multiplicity


# ── контур 4: словарь записи `types` и разрешённость ссылок ─────────────────────────
def check_types_dictionary(cur, header, db_rows, index_info, expect, tag):
    """Ключи записи, словари классов/состояний, дубликаты и цели ссылок."""
    required = set(TYPE_ENTRY_KEYS)
    target_keys = set(TYPE_ENTRY_TARGET_KEYS)
    bad_keys, bad_classes, bad_states, bad_target_keys, duplicates = [], [], [], [], []
    classes = Counter()
    entries_total = 0
    resolved = 0
    unresolved = 0
    targets = set()
    for row in db_rows:
        seen_values = set()
        for entry in row["types"] or []:
            entries_total += 1
            keys = set(entry.keys())
            extra = keys - required - target_keys
            if keys - target_keys != required or extra:
                bad_keys.append((row["object_name"], sorted(keys), sorted(extra)))
            cls = entry.get("class")
            classes[str(cls)] += 1
            if cls not in TYPE_CLASS_VALUES:
                bad_classes.append((row["object_name"], cls))
            if entry.get("state") not in RECORD_STATES:
                bad_states.append((row["object_name"], entry.get("state")))
            has_target = bool(target_keys & keys)
            if entry.get("resolved") is True:
                resolved += 1
                if not has_target or cls != CLASS_OBJECT_REF:
                    bad_target_keys.append((row["object_name"], cls, sorted(keys)))
                targets.add(str(entry.get("target_full_name")))
            else:
                if has_target:
                    bad_target_keys.append((row["object_name"], "ключи цели у неразрешённой",
                                            sorted(keys)))
                if cls == CLASS_OBJECT_REF:
                    unresolved += 1
            value = entry.get("value")
            if value in seen_values:
                duplicates.append((row["object_name"], value))
            seen_values.add(value)

    check(f"{tag}: ключи записей `types` — ровно `TYPE_ENTRY_KEYS` ({len(required)} ключей), "
          f"лишних ключей нет", not bad_keys, _brief(bad_keys[:MAX_NAMES]))
    check(f"{tag}: ключи цели есть только у разрешённого `object_ref` (прецедент D3)",
          not bad_target_keys, _brief(bad_target_keys[:MAX_NAMES]))
    check(f"{tag}: классы значений внутри замкнутого словаря разбора", not bad_classes,
          _brief(bad_classes[:MAX_NAMES]))
    check(f"{tag}: состояния записей внутри замкнутого словаря состояний", not bad_states,
          _brief(bad_states[:MAX_NAMES]))
    check(f"{tag}: дубликатов одного `value` в строке нет (этого не выражает CHECK, замер 2.5)",
          not duplicates, _brief(duplicates[:MAX_NAMES]))
    check(f"{tag}: записей `types` ровно {expect['entries']}, из них `object_ref` "
          f"{expect['object_ref']}",
          entries_total == expect["entries"]
          and classes.get("object_ref", 0) == expect["object_ref"],
          f"записей: {entries_total}, классы: {_brief(dict(classes))}")
    check(f"{tag}: классов `defined_type_ref` {expect['defined_ref']}, `unknown` "
          f"{expect['unknown_cls']}, `primitive` {expect['primitive_cls']} (замер 2.4)",
          classes.get("defined_type_ref", 0) == expect["defined_ref"]
          and classes.get("unknown", 0) == expect["unknown_cls"]
          and classes.get("primitive", 0) == expect["primitive_cls"],
          _brief(dict(classes)))
    check(f"{tag}: разрешено ссылок {expect['resolved']}, неразрешённых {expect['unresolved']}, "
          f"различных целей {expect['targets']} (замер 2.5)",
          resolved == expect["resolved"] and unresolved == expect["unresolved"]
          and len(targets) == expect["targets"],
          f"разрешено: {resolved}, неразрешённых: {unresolved}, целей: {len(targets)}")

    # Разрешённость цели — отдельным SQL-запросом, а не по строкам индекса Python:
    # два разных пути к одному факту (индекс той же конфигурации, а не вся таблица).
    broken = q(cur, f"""
        SELECT sp.object_name, e ->> 'target_full_name' AS target
          FROM {SESSION_PARAMETER_TABLE} sp
          JOIN configurations c ON c.uuid = sp.configuration_uuid
          JOIN jsonb_array_elements(sp.types) e ON (e ->> 'resolved') = 'true'
         WHERE sp.configuration_uuid = %(configuration_uuid)s::uuid
           AND NOT EXISTS (SELECT 1 FROM configuration_objects o
                            WHERE o.configuration_id = c.id
                              AND o.name = e ->> 'target_full_name')
         ORDER BY 1, 2
    """, {"configuration_uuid": str(header["uuid"])})
    check(f"{tag}: каждая разрешённая ссылка существует в индексе состава СВОЕЙ конфигурации "
          f"(SQL-путь)", not broken, _brief(broken[:MAX_NAMES]))

    index_by_name = index_rows_by_name(index_info["rows"])
    mismatched = []
    for row in db_rows:
        for entry in row["types"] or []:
            if entry.get("resolved") is not True:
                continue
            index_row = index_by_name.get(str(entry.get("target_full_name")))
            if not index_row:
                mismatched.append((row["object_name"], entry.get("target_full_name"),
                                   "нет записи индекса"))
                continue
            if str(index_row.get("uuid") or "").lower() != str(
                    entry.get("target_object_uuid") or "").lower():
                mismatched.append((row["object_name"], entry.get("target_full_name"),
                                   "uuid цели не совпадает"))
            if str(index_row.get("object_type") or "") != str(
                    entry.get("target_object_type") or ""):
                mismatched.append((row["object_name"], entry.get("target_full_name"),
                                   "object_type цели не совпадает"))
    check(f"{tag}: `target_object_uuid`/`target_object_type` равны колонкам записи индекса "
          f"(путь разбора)", not mismatched, _brief(mismatched[:MAX_NAMES]))
    return {"entries": entries_total, "object_ref": classes.get("object_ref", 0),
            "resolved": resolved, "unresolved": unresolved, "targets": len(targets),
            "targets_set": targets,
            "defined_ref": classes.get("defined_type_ref", 0),
            "unknown_cls": classes.get("unknown", 0),
            "primitive_cls": classes.get("primitive", 0)}


# ── контур 5: примитивность вида (критерий 4а раздела 7 плана) ──────────────────────
def parent_uuid_tables(cur):
    """Таблицы содержимого с колонкой `parent_uuid` — круг берёт живая схема.

    Перечень из комментария к DDL устарел бы молча: круг читается из
    `information_schema.columns`, и появление новой таблицы содержимого становится
    наблюдаемым фактом, а не слепой зоной проверки.
    """
    rows = q(cur, """
        SELECT table_name FROM information_schema.columns
         WHERE column_name = 'parent_uuid' AND table_schema = 'public'
           AND left(table_name, 2) <> 'v_'
         GROUP BY table_name ORDER BY table_name
    """)
    return [str(row["table_name"]) for row in rows
            if str(row["table_name"]) != SESSION_PARAMETER_TABLE]


def check_primitive_kind(cur, header, db_rows, circle, expect, tag, tables):
    """Ни одной строки содержимого с родителем-параметром сеанса, детей в индексе нет."""
    uuids = sorted({str(row["object_uuid"]) for row in db_rows})
    forms = sorted(set(uuids) | {item.replace("-", "") for item in uuids})
    hits = {}
    refs = 0
    for table in tables:
        count = int(one(cur, f'SELECT count(*) AS c FROM "{table}" '
                            f'WHERE parent_uuid IS NOT NULL '
                            f'AND lower(parent_uuid::text) = ANY(%s)',
                        (forms,)).get("c") or 0)
        if count:
            hits[table] = count
        refs += count
    check(f"{tag}: ни в одной таблице содержимого нет строки с `parent_uuid` = uuid "
          f"параметра сеанса (ожидалось {expect['parent_refs']})",
          refs == expect["parent_refs"],
          f"найдено {refs} в таблицах: {_brief(hits)}. Появление строки означает, что "
          f"примитивность вида перестала быть фактом замера — границы узла пересматриваются")
    children = int(one(cur,
                       "SELECT count(*) AS c FROM configuration_objects "
                       "WHERE configuration_id = %s AND parent_name = ANY(%s)",
                       (int(header["id"]),
                        sorted(circle["index_names"]))).get("c") or 0)
    check(f"{tag}: записей индекса состава с родителем-параметром сеанса "
          f"{expect['children']} (иерархии у вида нет, замер 2.2)",
          children == expect["children"], f"факт: {children}")
    return refs, children


# ── контур 6: ключ цепочки состояния и витрина текущего состояния ────────────────────
VIEW_NAME = current_view(SESSION_PARAMETER_TABLE)


def check_key_definition(cur):
    """Живые определения схемы: ключ цепочки и GIN по содержимому `types`.

    Ключ по uuid метаданных для этого вида невозможен: 82 из 125 uuid встречаются в двух и
    более конфигурациях (`_v48_q2_key_probe.py`), поэтому различает строку только пара
    (configuration_uuid, object_name). Контур читает определения БД, а не файл DDL — его
    сверяет `_cmp_ddl.py`.
    """
    index = str(one(cur, "SELECT indexdef AS def FROM pg_indexes WHERE indexname = %s",
                    (KEY_INDEX,)).get("def") or "")
    normalized = " ".join(index.split()).lower()
    check(f"ключ цепочки состояния `{KEY_INDEX}` называет `{KEY_COLUMNS}`",
          KEY_COLUMNS in normalized, f"живое определение: {index[:200]}")
    check("определение ключа цепочки не содержит мёртвого предиката WHERE",
          " where " not in normalized, f"живое определение: {index[:200]}")
    gin = str(one(cur, "SELECT indexdef AS def FROM pg_indexes WHERE indexname = %s",
                  (GIN_INDEX,)).get("def") or "")
    gin_normalized = " ".join(gin.split()).lower()
    check(f"GIN-индекс `{GIN_INDEX}` по колонке `types` существует (запрос по цели идёт по нему)",
          gin_normalized.startswith("create index") and " using gin " in gin_normalized
          and "types jsonb_path_ops" in gin_normalized,
          f"живое определение: {gin[:200] or 'индекса нет'}")


def check_view_rows(cur, cfg_uuid, db_rows, tag):
    """Витрина отдаёт ровно по одной текущей строке на ключ цепочки."""
    exists = int(one(cur, "SELECT count(*) AS c FROM information_schema.views "
                          "WHERE table_schema = 'public' AND table_name = %s",
                     (VIEW_NAME,)).get("c") or 0)
    check(f"витрина текущего состояния называется реестром `current_view()` ({VIEW_NAME}) "
          f"и существует в схеме", exists == 1, f"строк определения: {exists}")
    view_rows = int(one(cur, f"SELECT count(*) AS c FROM {VIEW_NAME} "
                             f"WHERE configuration_uuid = %(uuid)s::uuid",
                        {"uuid": str(cfg_uuid)}).get("c") or 0)
    keys = len({row["object_name"] for row in db_rows})
    check(f"{tag}: витрина отдаёт ровно по одной текущей строке на ключ цепочки "
          f"({len(db_rows)} строк таблицы, {keys} ключей)",
          view_rows == len(db_rows) == keys,
          f"витрина: {view_rows}, таблица: {len(db_rows)}, ключей: {keys}")
    duplicated = q(cur, f"SELECT object_name, count(*) AS c FROM {VIEW_NAME} "
                        f"WHERE configuration_uuid = %(uuid)s::uuid "
                        f"GROUP BY object_name HAVING count(*) > 1",
                   {"uuid": str(cfg_uuid)})
    check(f"{tag}: дубликатов текущих строк по одному ключу в витрине нет", not duplicated,
          _brief(duplicated[:MAX_NAMES]))


def check_cross_configuration_rows(cur):
    """Одно имя в двух конфигурациях остаётся в витрине двумя строками.

    Факт, а не рассуждение: именно ради него в ключ входит `configuration_uuid`. Если бы
    витрина схлопывала такую пару, вторая конфигурация потеряла бы состав вида молча.
    """
    shared = q(cur, f"""
        SELECT object_name, count(DISTINCT configuration_uuid) AS configs
          FROM {SESSION_PARAMETER_TABLE}
         GROUP BY object_name
        HAVING count(DISTINCT configuration_uuid) >= 2
    """)
    if not shared:
        skip("имена, общие для нескольких конфигураций, различаются витриной",
             "в таблице нет имени, встречающегося в двух конфигурациях: различение "
             "доказать нечем")
        return 0
    collapsed = q(cur, f"""
        SELECT s.object_name, s.configs, count(v.id) AS in_view
          FROM (SELECT object_name, count(DISTINCT configuration_uuid) AS configs
                  FROM {SESSION_PARAMETER_TABLE}
                 GROUP BY object_name
                HAVING count(DISTINCT configuration_uuid) >= 2) s
          LEFT JOIN {VIEW_NAME} v ON v.object_name = s.object_name
         GROUP BY s.object_name, s.configs
        HAVING count(v.id) <> s.configs
    """)
    check(f"{len(shared)} имён вида встречаются в двух и более конфигурациях — каждое "
          f"остаётся в витрине по строке на конфигурацию", not collapsed,
          _brief(collapsed[:MAX_NAMES]))
    return len(shared)


# ── контур 7: сироты и граница R5 ───────────────────────────────────────────────────
def check_orphans(cur):
    """Строк узла без строки заголовка нет — каскада в схеме нет осознанно (V20.1)."""
    orphans = int(one(cur, f"SELECT count(*) AS c FROM {SESSION_PARAMETER_TABLE} sp "
                          f"LEFT JOIN configurations c ON c.uuid = sp.configuration_uuid "
                          f"WHERE c.id IS NULL").get("c") or 0)
    check("сирот по заголовку в таблице узла нет (снятие держит `_remove_rows`, каскада нет)",
          orphans == 0, f"сирот: {orphans}")
    return orphans


def dump_newer_than_rows(dump_dir, db_rows):
    """True, если файлы круга новее строк узла (правило R5); None — если мерить нечем."""
    stamps = [row["changed_at"] for row in db_rows if row.get("changed_at")]
    if not stamps:
        return None
    directory = Path(dump_dir) / DIR_NAME
    if not directory.is_dir():
        return None
    newest = None
    for entry in directory.rglob("*"):
        if not entry.is_file():
            continue
        try:
            modified = datetime.fromtimestamp(entry.stat().st_mtime)
        except OSError:
            continue
        if newest is None or modified > newest:
            newest = modified
    if newest is None:
        return None
    return newest > min(stamps)


# ── контур 8: неприкосновенность чужого круга (проверка только читает) ──────────────
def foreign_state(cur):
    """Снимок того, что узел трогать не должен (сверяется до и после прогона)."""
    state = {}
    for table in ("configurations", "configuration_objects", "subsystems",
                  "subsystem_content", "common_modules", "common_module_sources",
                  "bsl_modules", "external_report", "config_aliases", "config_snippets",
                  "config_cross_references"):
        state[table] = int(one(cur, f"SELECT count(*) AS c FROM {table}").get("c") or 0)
    state["kind_index_records"] = int(one(cur,
                                          "SELECT count(*) AS c FROM configuration_objects "
                                          "WHERE object_type = %s",
                                          (INDEX_OBJECT_TYPE,)).get("c") or 0)
    state["kind_rows_total"] = int(one(cur, f"SELECT count(*) AS c FROM "
                                            f"{SESSION_PARAMETER_TABLE}").get("c") or 0)
    return state


def check_untouched(before, after):
    changed = {key: (before[key], after.get(key)) for key in before
               if before[key] != after.get(key)}
    check("чужие строки (заголовок, индекс состава, слои V44/V46/V47, внешние объекты, "
          "обогащение) за прогон не изменены", not changed, _brief(changed))
    info("снимок чужого круга: " + ", ".join(f"{key}={value}"
                                             for key, value in sorted(after.items())))


# ── контур 9: итог по узлу и корпусные числа (критерии 1–4 раздела 7 плана) ─────────
COMPARE_KEYS = ("files", "index", "header", "rows", "single", "composite", "mult_absent",
                "parsed", "raw_filled", "comments", "entries", "object_ref", "resolved",
                "unresolved", "targets", "defined_ref", "unknown_cls", "primitive_cls",
                "index_only", "file_only", "uuid_mismatch", "observations", "children",
                "parent_refs")


def check_aggregate(cur, totals, run_tags, skipped_tags=()):
    """Суммы по сравненным конфигурациям равны суммам ожиданий плана (раздел 2)."""
    if not run_tags:
        skip("итог по узлу", "ни одной конфигурации не проверялось")
        return
    expected = Counter()
    for tag in run_tags:
        expected.update(PLAN_EXPECTATIONS[tag])
    fact = {key: int(totals.get(key, 0)) for key in COMPARE_KEYS}
    wanted = {key: int(expected.get(key, 0)) for key in COMPARE_KEYS}
    diff = {key: (fact[key], wanted[key]) for key in COMPARE_KEYS if fact[key] != wanted[key]}
    named_skipped = f"; не сравнивались: {', '.join(skipped_tags)}" if skipped_tags else ""
    check(f"итог по {len(run_tags)} проверенным конфигурациям ({', '.join(run_tags)}) "
          f"равен суммам ожиданий плана{named_skipped}", fact == wanted, _brief(diff))
    states = {state: int(totals.get(f"state:{state}", 0)) for state in RECORD_STATES}
    multiplicities = {mult: int(totals.get(f"mult:{mult}", 0))
                      for mult in MULTIPLICITY_VALUES}
    info(f"итог по {len(run_tags)} конфигурациям: строк {fact['rows']}, записей `types` "
         f"{fact['entries']}, ссылок {fact['object_ref']}; состояния строк {states}; "
         f"кратность {multiplicities}")
    if len(run_tags) == len(PLAN_EXPECTATIONS) and not skipped_tags:
        check_corpus(cur)
    else:
        not_compared = sorted(set(PLAN_EXPECTATIONS) - set(run_tags))
        info(f"корпусные числа плана ({CORPUS_EXPECTATIONS['rows']} строк, "
             f"{CORPUS_EXPECTATIONS['entries']} записей `types`, "
             f"{CORPUS_EXPECTATIONS['object_ref']} ссылок, "
             f"{CORPUS_EXPECTATIONS['targets']} целей) сверяются только прогоном по всем "
             f"{len(PLAN_EXPECTATIONS)} выгрузкам плана; в этом прогоне сравнены "
             f"{len(run_tags)}; вне сравнения: "
             f"{', '.join(not_compared) if not_compared else 'нет'}"
             + (f"; пропущены: {', '.join(skipped_tags)}" if skipped_tags else ""))


def check_corpus(cur):
    """Корпус: 207 строк, 213 записей, 24 ссылки, 8 целей, GIN-запрос по тяжёлой цели."""
    table = one(cur, f"""
        SELECT count(*) AS rows_total,
               count(DISTINCT object_uuid) AS distinct_uuids,
               count(DISTINCT object_name) AS distinct_names,
               count(*) FILTER (WHERE type_multiplicity = 'single') AS single,
               count(*) FILTER (WHERE type_multiplicity = 'composite') AS composite,
               count(*) FILTER (WHERE type_multiplicity = 'absent') AS mult_absent,
               count(*) FILTER (WHERE coalesce(comment, '') <> '') AS comments
          FROM {SESSION_PARAMETER_TABLE}
    """)
    entries = one(cur, f"""
        SELECT count(*) AS entries_total,
               count(*) FILTER (WHERE e ->> 'class' = 'object_ref') AS object_ref,
               count(*) FILTER (WHERE (e ->> 'resolved') = 'true') AS resolved,
               count(DISTINCT e ->> 'target_full_name') AS targets
          FROM {SESSION_PARAMETER_TABLE} sp, jsonb_array_elements(sp.types) e
    """)
    shared_uuids = int(one(cur,
                           f"SELECT count(*) AS c FROM (SELECT object_uuid "
                           f"FROM {SESSION_PARAMETER_TABLE} GROUP BY object_uuid "
                           f"HAVING count(DISTINCT configuration_uuid) >= 2) s"
                           ).get("c") or 0)
    shared_names = int(one(cur,
                           f"SELECT count(*) AS c FROM (SELECT object_name "
                           f"FROM {SESSION_PARAMETER_TABLE} GROUP BY object_name "
                           f"HAVING count(DISTINCT configuration_uuid) >= 2) s"
                           ).get("c") or 0)
    hits = int(one(cur, f"SELECT count(*) AS c FROM {VIEW_NAME} "
                        f"WHERE types @> %(wanted)s::jsonb",
                   {"wanted": json.dumps([{"target_full_name": HEAVIEST_TARGET}])}
                   ).get("c") or 0)

    exp = CORPUS_EXPECTATIONS
    check(f"корпус: строк {exp['rows']}, `single` {exp['single']}, `composite` "
          f"{exp['composite']}, `absent` {exp['mult_absent']} — те же числа, что замер 2.4.3 "
          f"считает по файлам (критерий 1а)",
          int(table.get("rows_total") or 0) == exp["rows"]
          and int(table.get("single") or 0) == exp["single"]
          and int(table.get("composite") or 0) == exp["composite"]
          and int(table.get("mult_absent") or 0) == exp["mult_absent"], _brief(table))
    check(f"корпус: записей `types` {exp['entries']}, из них `object_ref` "
          f"{exp['object_ref']}, разрешено {exp['resolved']}, различных целей "
          f"{exp['targets']} (замер 2.5)",
          int(entries.get("entries_total") or 0) == exp["entries"]
          and int(entries.get("object_ref") or 0) == exp["object_ref"]
          and int(entries.get("resolved") or 0) == exp["resolved"]
          and int(entries.get("targets") or 0) == exp["targets"], _brief(entries))
    check(f"корпус: запрос по цели `{HEAVIEST_TARGET}` идёт по витрине и отдаёт "
          f"{exp['heaviest_links']} параметров (критерий 1б, GIN по `types`)",
          hits == exp["heaviest_links"], f"факт: {hits}")
    check(f"корпус: различных uuid {exp['distinct_uuids']}, из них в двух и более "
          f"конфигурациях {exp['uuid_shared']}; различных имён {exp['distinct_names']}, "
          f"общих имён {exp['names_shared']} — обоснование ключа Q2",
          int(table.get("distinct_uuids") or 0) == exp["distinct_uuids"]
          and shared_uuids == exp["uuid_shared"]
          and int(table.get("distinct_names") or 0) == exp["distinct_names"]
          and shared_names == exp["names_shared"],
          f"uuid: {table.get('distinct_uuids')}, общих uuid: {shared_uuids}, "
          f"имён: {table.get('distinct_names')}, общих имён: {shared_names}")
    check(f"корпус: непустых `Comment` {exp['comments']} (замер 2.7)",
          int(table.get("comments") or 0) == exp["comments"],
          f"факт: {table.get('comments')}")


# ── прогон ───────────────────────────────────────────────────────────────────────────
def run(cur, scope):
    headers = q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations "
                     "ORDER BY id")
    if not headers:
        print("FAIL строк заголовков конфигураций в базе нет — сравнивать не с чем")
        FAILED.append("нет строк заголовков")
        return
    before = foreign_state(cur)
    tables = parent_uuid_tables(cur)
    info(f"круг таблиц с колонкой `parent_uuid` взят из живой схемы: {len(tables)} — "
         f"{', '.join(tables)}")
    totals = Counter()
    run_tags, skipped_tags = [], []
    for header in headers:
        resolved = resolve_dump_dir(header["uuid"], DUMP_ROOT)
        dump_dir = resolved.get("path") or ""
        tag = Path(dump_dir).name if dump_dir else str(header["name"])
        if scope not in (DEFAULT_SCOPE, tag, str(header["name"])):
            continue
        section(f"Конфигурация {tag} (uuid {header['uuid']})")
        if not dump_dir:
            skipped_tags.append(tag)
            skip(f"{tag}: все контуры узла",
                 resolved.get("reason") or "каталог выгрузки не найден")
            continue
        expect = PLAN_EXPECTATIONS.get(tag)
        if expect is None:
            skipped_tags.append(tag)
            skip(f"{tag}: все контуры узла",
                 f"каталога `{tag}` нет в перечне ожиданий проверки — числа круга этой "
                 f"выгрузки надо переснять и записать в план прежде, чем сравнивать с ними")
            continue
        index_info = read_index_records(cur, int(header["id"]))
        if not index_info["available"]:
            skipped_tags.append(tag)
            skip(f"{tag}: контуры круга, ссылок и словаря `types`",
                 index_info.get("reason") or "индекс состава этой конфигурации не загружен: "
                                            "сверка файлов с перечнем и разрешение ссылок "
                                            "невыразимы")
            continue
        circle = check_circle_sources(cur, header, dump_dir, index_info, expect, tag)
        db_rows = circle["db_rows"]
        if not db_rows:
            skipped_tags.append(tag)
            skip(f"{tag}: контуры «файл ↔ строка», мер файла, словаря `types` и примитивности",
                 "строк узла в таблице нет — конфигурацию не перезагружали после узла V48 "
                 "(стадия `s4c_session_parameters` входит в загрузку каталога, отдельный "
                 "вход группы — `load_session_parameters_tool`)")
            continue
        if dump_newer_than_rows(dump_dir, db_rows):
            skipped_tags.append(tag)
            skip(f"{tag}: контуры «файл ↔ строка» и мер файла",
                 "файлы выгрузки новее строк узла (правило R5): сохранённые свойства "
                 "описывают прошлое состояние, сравнение с ним было бы сравнением с прошлым")
            continue
        parsed, failures = parse_disk_rows(dump_dir, index_info["rows"])
        check_rows_against_files(parsed, failures, db_rows, expect, tag)
        states, multiplicity = check_file_measures(dump_dir, db_rows, expect, tag)
        refs = check_types_dictionary(cur, header, db_rows, index_info, expect, tag)
        parent_refs, children = check_primitive_kind(cur, header, db_rows, circle, expect,
                                                     tag, tables)
        check_view_rows(cur, header["uuid"], db_rows, tag)

        totals["files"] += len(circle["files"])
        totals["index"] += len(circle["kind_rows"])
        totals["header"] += len(circle["header_names"])
        totals["rows"] += len(db_rows)
        totals["observations"] += len(circle["observations"])
        totals["index_only"] += len(circle["only_index"])
        totals["file_only"] += len(circle["only_files"])
        totals["uuid_mismatch"] += sum(
            1 for item in parsed.values()
            if item["index_check"]["state"] in ("uuid_mismatch", "file_only"))
        totals["parent_refs"] += parent_refs
        totals["children"] += children
        for state, count in states.items():
            totals[f"state:{state}"] += count
            if state == "parsed":
                totals["parsed"] += count
        for mult, count in multiplicity.items():
            totals[f"mult:{mult}"] += count
        totals["single"] += multiplicity.get("single", 0)
        totals["composite"] += multiplicity.get("composite", 0)
        totals["mult_absent"] += multiplicity.get("absent", 0)
        totals["raw_filled"] += sum(1 for row in db_rows if row["type_raw"])
        totals["comments"] += sum(1 for row in db_rows if (row["comment"] or "").strip())
        for key in ("entries", "object_ref", "resolved", "unresolved", "targets",
                    "defined_ref", "unknown_cls", "primitive_cls"):
            totals[key] += refs.get(key, 0)
        # В перечень сравнения конфигурация входит только после того, как её числа легли
        # в суммы: иначе итог сравнивал бы суммы по четырём строкам плана с фактом по
        # трём и проваливался бы на любой пропущенной выгрузке.
        run_tags.append(tag)

    after = foreign_state(cur)
    section("Итог узла V48")
    check_orphans(cur)
    check_key_definition(cur)
    check_cross_configuration_rows(cur)
    check_untouched(before, after)
    check_aggregate(cur, totals, run_tags, skipped_tags)


def main(argv):
    scope = str(argv[1]) if len(argv) > 1 else DEFAULT_SCOPE
    try:
        with transaction() as cur:
            run(cur, scope)
    except Exception as exc:  # отказ прогона обязан быть назван, а не оборвать вывод
        FAILED.append(f"прогон прерван исключением: {exc}")
        print(f"FAIL прогон прерван исключением: {type(exc).__name__}: {exc}")
    print("\n" + "=" * 72)
    print(f"ИТОГ: пройдено {len(PASSED)}, провалено {len(FAILED)}, "
          f"пропущено {len(SKIPPED)}, заметок {len(INFO)}")
    for name in FAILED:
        print("  ПРОВАЛ: " + name)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))









