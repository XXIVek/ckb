#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П4 узла V48: слой загрузки свойств параметров сеанса (стадия S4c).

Предмет проверки — не разбор файла (его закрыл П2) и не писатель (П3), а слой и его
встраивание в конвейер:

  1. стадия зарегистрирована в `STAGES` между `s4_child_objects` и `s4b_object_modules`
     (решение Q5: порядок повторяет нормативный список, позиция 2.3), имеет свой ключ
     ответа (правило C3) и свой закрытый контракт (C1);
  2. отказ слоя называется состоянием контракта, а не исключением и не нулями (C1, C2):
     каталог не читается, uuid каталога и переданный разошлись, строки заголовка нет,
     файл круга не разбирается; ни один отказ не меняет круг таблиц в базе;
  3. успех: строки круга записаны, числа ответа совписаны с тем, что легло в таблицы,
     состояния разбора и кратность названы, сверка с индексом состава соответствует
     независимому сравнению каталога и перечня, статистика таблицы собрана;
  4. повтор той же выгрузки идемпотентен: снятие названо, дублей нет, `revision_no` не
     растёт (D8), метка загрузки меняется (новое событие);
  5. конвейер (`load_catalog`, `force=True`) вызывает стадию, карточка содержит раздел
     стадии с состояниями и границей круга, метки строк одной загрузки совпадают (M2),
     соседние стадии S4 и S4b не сломаны, а `delete_configuration` снимает строки вида
     вместе с заголовком — сирот не остаётся.

Проба работает с живой БД: загрузчик фиксирует свои транзакции сам, поэтому проба убирает
за собой и возвращает базовое состояние — круг пробы пуст, круги других конфигураций не
тронуты, сирот нет (приём `_v46_p5_loader_probe.py`, переформулированный узлом V48: конвейер
пишет реальный состав, и «пустая таблица» состоянием базы больше не является). Разбор файла и
ограничения схемы эта проба не проверяет — их закрыли П2 и П3.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v48_p4_loader_probe.py [MinCfg|KomMag]

Код возврата 0 — расхождений нет. Строки, записанные конвейером в последнем блоке,
остаются в базе намеренно: снимать их после конвейера — значит оставить конфигурацию без
только что записанного содержимого (тот же порядок, что у пробы П5 узла V46).
"""

import json
import sys
import time
import uuid as uuid_module
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
import configuration_session_parameters_loader as SPL  # noqa: E402
# Карточка и конвейер — те же точки входа, что читает оператор: проба проверяет слой
# вместе с его встраиванием, а не только вызов функции.
from config_load_router import format_load_result, load_catalog  # noqa: E402
from configuration_load_contract import (  # noqa: E402
    CHILD_SECTION_HEADER,
    CHILD_TABLES,
    OBJECT_MODULES_SECTION_HEADER,
    SESSION_PARAMETERS_BOUNDARY,
    SESSION_PARAMETERS_SECTION_HEADER,
    SESSION_PARAMETER_TABLE,
    STAGE_CHILD_OBJECTS,
    STAGE_OBJECT_MODULES,
    STAGE_SESSION_PARAMETERS,
    STAGES,
    STATUS_ERROR,
    STATUS_NOT_RUN,
    STATUS_OK,
    format_session_parameters_lines,
    session_parameters_defaults,
)
from configuration_loader import delete_configuration, find_configuration  # noqa: E402
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from current_revision import (  # noqa: E402
    CHANGED_BY_LOAD, CONFIGURATION_VERSIONED_TABLES, FIRST_REVISION, current_view,
)
from external_db import connect  # noqa: E402
from external_table_writer import CONFIGURATION_OBJECT_WRITERS  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag")
BASELINE_FILES = {"MinCfg": 2, "KomMag": 6}
# Выгрузки, которых нет в базе: нужны для отказа «строки заголовка нет». Список кандидатов
# перебирается, а не выбирается наугад: какой из них действительно не загружен, решает сама
# база — иначе проба проверяла бы совпадение со своим предположением.
UNLOADED_CANDIDATES = ("Config_NULL", "UNF3", "UT11", "ZUP31")
FIXTURE_DIR = ROOT / "_scratch" / "v48_p4_fixtures"

VIEW = current_view(SESSION_PARAMETER_TABLE)
TABLES = (SESSION_PARAMETER_TABLE,)

PASSED = 0
FAILED = 0
NOTES = []


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + ((" — " + str(detail)) if detail else ""))
    else:
        FAILED += 1
        print("  [FAIL] " + name + ((" — " + str(detail)) if detail else ""))


def note(text):
    NOTES.append(text)
    print("  [NOTE] " + text)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def table_counts(cur, cfg_uuid, tables=TABLES):
    """Счётчик таблиц слоя для этой конфигурации (базовое состояние и итог пробы)."""
    counts = {}
    for table in tables:
        cur.execute(f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
                    [str(cfg_uuid)])
        counts[table] = cur.fetchone()[0]
    return counts


def view_counts(cur, cfg_uuid):
    """Счётчик витрины текущего состояния — читатель видит ровно записанное (V19)."""
    cur.execute(f"SELECT count(*) FROM {VIEW} WHERE configuration_uuid = %s::uuid",
                [str(cfg_uuid)])
    return cur.fetchone()[0]


def index_kind_names(cur, configuration_id):
    """Независимая величина: имена вида из перечня состава этой конфигурации (замер 2.2)."""
    cur.execute(
        "SELECT object_name FROM configuration_objects WHERE configuration_id = %s "
        "AND object_type = %s",
        [int(configuration_id), SP.INDEX_OBJECT_TYPE],
    )
    return {row[0] for row in cur.fetchall()}


def physical_file_names(dump_dir):
    """Независимая величина: файлы круга на диске (обходом каталога, не разбором)."""
    root = Path(dump_dir) / SP.DIR_NAME
    if not root.is_dir():
        return set()
    return {path.stem for path in root.rglob("*.xml")}


def check_contract_shape(report, label):
    """Ответ стадии обязан быть ровно закрытым контрактом (C1, C3).

    Лишний ключ — обещание, которого карточка не давала; недостающий — читатель разрешит
    его `.get()`-ом по-своему, и два вызывающих разрешат по-разному.
    """
    expected = session_parameters_defaults()
    check(f"{label}: ответ содержит ровно ключи контракта стадии",
          sorted(report) == sorted(expected),
          "лишнее: " + ", ".join(sorted(set(report) - set(expected)))
          + "; нет: " + ", ".join(sorted(set(expected) - set(report))))
    check(f"{label}: словари состояний замкнуты (RECORD_STATES, MULTIPLICITY_VALUES, "
          "TYPE_CLASS_VALUES)",
          sorted(report.get("counts_by_state") or {}) == sorted(SP.RECORD_STATES)
          and sorted(report.get("types_multiplicity") or {}) == sorted(SP.MULTIPLICITY_VALUES)
          and sorted(report.get("types_by_class") or {}) == sorted(SP.TYPE_CLASS_VALUES),
          str({k: sorted(v) for k, v in (
              ("counts_by_state", report.get("counts_by_state") or {}),
              ("types_multiplicity", report.get("types_multiplicity") or {}),
              ("types_by_class", report.get("types_by_class") or {}))}))
    check(f"{label}: стадия названа адресом из STAGES",
          report.get("stage") == STAGE_SESSION_PARAMETERS, report.get("stage"))


def check_text_render(report, label):
    """Форматёр не падает и называет то, что обязан (C1): состояния, кратность, границу."""
    try:
        lines = format_session_parameters_lines(report, indent="   ")
    except Exception as exc:  # noqa: BLE001 — форматёр обязан называть причину сам
        check(f"{label}: форматёр не падает", False, str(exc))
        return ""
    check(f"{label}: форматёр дал непустой текст", bool(lines), f"{len(lines)} строк")
    text = "\n".join(lines)
    if report.get("success"):
        check(f"{label}: текст называет состояния разбора типа",
              "Состояния разбора типа:" in text)
        check(f"{label}: текст называет кратность значений типа",
              "Кратность значений типа:" in text)
        check(f"{label}: текст называет классы и неразрешённые ссылки",
              "Записей значений типа:" in text and "неразрешено" in text)
        check(f"{label}: текст называет сверку с индексом состава",
              "Сверка с индексом состава:" in text)
        check(f"{label}: текст называет границу круга узла",
              SESSION_PARAMETERS_BOUNDARY in text)
    else:
        prefix = ("Стадия не выполнена" if report.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        check(f"{label}: текст отказа называет причину ровно один раз",
              text.count(prefix) == 1 and (report.get("error") or "") in text, prefix)
        check(f"{label}: текст отказа называет, чем продолжить",
              "load_1c_catalog_tool" in text)
    return text


def check_stage_registration(cur):
    """Стадия, её ключ, писатель и порядок стоят одним местом (Q5, C1, C2, C3)."""
    print("\n=== регистрация стадии и закрытость её контракта ===")
    addresses = [address for address, _title in STAGES]
    check("стадия S4c входит в STAGES", STAGE_SESSION_PARAMETERS in addresses,
          " → ".join(addresses))
    check("порядок стадий повторяет нормативный список: S4 → S4c → S4b (пункт 2.9 плана)",
          addresses.index(STAGE_SESSION_PARAMETERS)
          == addresses.index(STAGE_CHILD_OBJECTS) + 1
          and addresses.index(STAGE_OBJECT_MODULES)
          == addresses.index(STAGE_SESSION_PARAMETERS) + 1,
          " → ".join(addresses))
    check("круг стадии S4 узла V46 этим узлом не тронут (CHILD_TABLES без session_parameters)",
          SESSION_PARAMETER_TABLE not in list(CHILD_TABLES), str(list(CHILD_TABLES)))
    defaults = session_parameters_defaults()
    check("нулевой контракт читается нулями и статусом not_run (C1, C2)",
          defaults["status"] == STATUS_NOT_RUN and defaults["success"] is False
          and defaults["rows_written"] == 0 and defaults["removed_previous"] == 0
          and defaults["tables"] == [SESSION_PARAMETER_TABLE])
    check("SUMMARY_KEYS слоя — подмножество ключей контракта: неперечисленный ключ "
          "читается нулём, а не исчезает (C1)",
          set(SPL.SUMMARY_KEYS) <= set(defaults),
          ", ".join(sorted(set(SPL.SUMMARY_KEYS) - set(defaults))))
    check("писатель строки зарегистрирован общим реестром писателей (правило п.6)",
          SESSION_PARAMETER_TABLE in CONFIGURATION_OBJECT_WRITERS)
    check("таблица входит в круг версионируемых таблиц конфигурации (узел П1)",
          SESSION_PARAMETER_TABLE in CONFIGURATION_VERSIONED_TABLES)
    check("витрина текущего состояния существует (узел П1)",
          one(cur, "SELECT count(*) FROM information_schema.views WHERE table_name = %s",
              [VIEW]) == 1, VIEW)
    check("форматёр нулевого контракта называет отказ, а не нули (C2)",
          any("Стадия не выполнена" in line
              for line in format_session_parameters_lines(defaults)))
    check("форматёр пустого ответа не печатает ничего",
          format_session_parameters_lines({}) == [])


def pick_unloaded_dump():
    """Первая выгрузка, заголовка которой нет в базе, — для отказа «заголовка нет».

    Список кандидатов перебирается, а не выбирается наугад: решение о том, что выгрузка
    не загружена, принимает база по uuid из `Configuration.xml`, а не предположение пробы.
    """
    for name in UNLOADED_CANDIDATES:
        dump_dir = DUMP_ROOT / name
        if not dump_dir.is_dir():
            continue
        info = configuration_uuid_from_layout(str(dump_dir))
        if "uuid" not in info:
            continue
        if not find_configuration(str(info["uuid"])):
            return dump_dir
    return None


def make_broken_fixture(min_cfg_dir):
    """Фикстура «круг разбирается не весь»: Configuration.xml MinCfg + битый файл вида.

    uuid фикстуры совпадает с uuid MinCfg — файл заголовка скопирован, поэтому проверка
    заголовка проходит и отказ обязан родиться именно из разбора круга. Это и есть
    проверяемое поведение: стадия останавливается ДО записи, и в базе не оказывается
    половины круга (приём V12/V46).
    """
    import shutil  # локальный импорт — фикстура нужна только этому блоку

    target = FIXTURE_DIR / "BrokenRound"
    shutil.rmtree(target, ignore_errors=True)
    (target / SP.DIR_NAME).mkdir(parents=True, exist_ok=True)
    files = sorted((Path(min_cfg_dir) / SP.DIR_NAME).rglob("*.xml"))
    if len(files) < 2:
        return None
    shutil.copy2(Path(min_cfg_dir) / "Configuration.xml", target / "Configuration.xml")
    broken = files[0]
    (target / SP.DIR_NAME / broken.name).write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject><Name>', encoding="utf-8")
    for other in files[1:]:
        shutil.copy2(other, target / SP.DIR_NAME / other.name)
    return target


def check_refusals(cur, baseline_total):
    """Отказы слоя — состояние закрытого контракта, а не исключение и не нули (C1, C2)."""
    print("\n=== отказы: каталог, расхождение uuid, отсутствие заголовка ===")

    missing_dir = SPL.load_session_parameters(str(DUMP_ROOT / "_нет_такого_каталога"))
    check("каталог, которого нет, отклонён, а не сведён к нулям",
          missing_dir["status"] == STATUS_ERROR and missing_dir["success"] is False,
          missing_dir["status"])
    check("причина отказа названа текстом", bool(missing_dir["error"]),
          (missing_dir["error"] or "")[:120])
    check_contract_shape(missing_dir, "отказ: каталога нет")
    check_text_render(missing_dir, "отказ: каталога нет")

    other_uuid = str(uuid_module.uuid4())
    mismatch = SPL.load_session_parameters(str(DUMP_ROOT / "MinCfg"),
                                          configuration_uuid=other_uuid)
    check("расхождение uuid каталога и переданного — отказ, а не выбор одного",
          mismatch["status"] == STATUS_ERROR, (mismatch["error"] or "")[:120])
    check("в отказе названы оба указателя",
          other_uuid in (mismatch["error"] or "") and "uuid=" in (mismatch["error"] or ""))
    check_contract_shape(mismatch, "отказ: расхождение uuid")
    check_text_render(mismatch, "отказ: расхождение uuid")

    unloaded = pick_unloaded_dump()
    if unloaded is None:
        note("все выгрузки-кандидаты уже загружены в базе — отказ «строки заголовка нет» "
             "не проверен; отсутствие проверки названо, а не снято молча")
    else:
        no_header = SPL.load_session_parameters(str(unloaded))
        check("без строки заголовка слой отказывает и называет точку входа",
              no_header["status"] == STATUS_ERROR
              and "load_1c_catalog_tool" in (no_header["error"] or ""),
              (no_header["error"] or "")[:120])
        check("отказ объясняет, почему заголовок обязателен (внешний ключ не ставился "
              "осознанно — V20.1)", "V20.1" in (no_header["error"] or ""))
        check_contract_shape(no_header, "отказ: заголовка нет")
        check_text_render(no_header, "отказ: заголовка нет")
        note(f"отказ проверен на выгрузке {unloaded.name}: её заголовка в базе нет")

    after = one(cur, f"SELECT count(*) FROM {SESSION_PARAMETER_TABLE}")
    check("ни один отказ не записал и не снял строк", after == baseline_total,
          f"{baseline_total} → {after}")


def check_partial_refusal(cur, cfg_uuid, counts_before, fixture):
    """Неразобранный файл круга останавливает стадию ДО записи (приём V12/V46).

    Проверка идёт после успешной загрузки: только на фоне уже записанного круга видно,
    что отказ не снял прежние строки и не дописал половину новой.
    """
    print("\n=== круг не записывается частями: битый файл круга ===")
    if fixture is None:
        note("фикстура не построена (в MinCfg меньше двух файлов вида) — проверка "
             "названа отсутствующей")
        return
    broken = SPL.load_session_parameters(str(fixture))
    check("битый файл круга останавливает стадию", broken["status"] == STATUS_ERROR,
          (broken["error"] or "")[:160])
    check("отказ называет число неразобранных файлов и путь",
          "не разобраны" in (broken["error"] or "")
          and f"{SP.DIR_NAME}/" in (broken["error"] or ""),
          (broken["error"] or "")[:160])
    check("отказ называет, что ни одной строки круга не записано",
          "Ни одной строки круга" in (broken["error"] or ""))
    check("прежние строки не сняты отказом (removed_previous = 0)",
          int(broken.get("removed_previous") or 0) == 0, broken.get("removed_previous"))
    check_contract_shape(broken, "отказ: битый файл круга")
    check_text_render(broken, "отказ: битый файл круга")
    after = table_counts(cur, cfg_uuid)
    check("круг в базе не изменился: ни частичной записи, ни снятия", after == counts_before,
          f"{counts_before} → {after}")


def check_written(cur, cfg_uuid, configuration_id, dump_dir, report, expected_files, label):
    """Что названо отчётом стадии, то и лежит в таблицах — и наоборот (M2, Q2, П1)."""
    counts = table_counts(cur, cfg_uuid)
    written = int(report.get("rows_written") or 0)
    check(f"{label}: строк в таблице ровно по отчёту",
          counts[SESSION_PARAMETER_TABLE] == written,
          f"база {counts[SESSION_PARAMETER_TABLE]}, отчёт {written}")
    check(f"{label}: круг совпадает с замером 2.1 ({expected_files})",
          written == expected_files, written)
    check(f"{label}: rows_written равна числу найденных и разобранных файлов",
          written == int(report.get("files_read") or 0) == int(report.get("files_found") or 0),
          f"found {report.get('files_found')}, read {report.get('files_read')}")
    check(f"{label}: строк без configuration_uuid в базе нет",
          one(cur, f"SELECT count(*) FROM {SESSION_PARAMETER_TABLE} "
                   "WHERE configuration_uuid IS NULL") == 0)
    check(f"{label}: витрина текущего состояния отдаёт записанное",
          view_counts(cur, cfg_uuid) == counts[SESSION_PARAMETER_TABLE])

    stamps = one(cur, f"SELECT count(DISTINCT changed_at) FROM {SESSION_PARAMETER_TABLE} "
                      "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)])
    check(f"{label}: одна метка changed_at на все строки одной загрузки (M2)", stamps == 1,
          stamps)
    check(f"{label}: строки загружены первой ревизией, changed_by = load, is_committed = true",
          one(cur, f"SELECT count(*) FROM {SESSION_PARAMETER_TABLE} WHERE "
                   "configuration_uuid = %s::uuid AND revision_no = %s "
                   "AND changed_by = %s AND is_committed = TRUE",
              [str(cfg_uuid), FIRST_REVISION, CHANGED_BY_LOAD]) == written)
    check(f"{label}: ключ (configuration_uuid, object_name) без дублей (решение Q2)",
          one(cur, f"SELECT count(*) FROM (SELECT object_name FROM {SESSION_PARAMETER_TABLE} "
                   "WHERE configuration_uuid = %s::uuid GROUP BY object_name HAVING "
                   "count(*) > 1) d", [str(cfg_uuid)]) == 0)

    cur.execute(f"SELECT object_name, object_uuid::text FROM {SESSION_PARAMETER_TABLE} "
                "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)])
    stored = {row[0]: row[1] for row in cur.fetchall()}
    check(f"{label}: имена строк = имена файлов круга (независимый обход каталога)",
          set(stored) == physical_file_names(dump_dir),
          "лишних: " + ", ".join(sorted(set(stored) - physical_file_names(dump_dir)))
          + "; нет: " + ", ".join(sorted(physical_file_names(dump_dir) - set(stored))))
    check(f"{label}: object_uuid каждой строки совпадает с uuid записи индекса",
          one(cur, f"SELECT count(*) FROM {SESSION_PARAMETER_TABLE} sp JOIN "
                   "configuration_objects co ON co.configuration_id = %s "
                   "AND co.object_type = %s AND co.object_name = sp.object_name "
                   "WHERE sp.configuration_uuid = %s::uuid AND co.uuid IS NOT NULL "
                   "AND co.uuid <> sp.object_uuid",
              [int(configuration_id), SP.INDEX_OBJECT_TYPE, str(cfg_uuid)]) == 0)

    cur.execute(f"SELECT type_parse_state, count(*) FROM {SESSION_PARAMETER_TABLE} "
                "WHERE configuration_uuid = %s::uuid GROUP BY 1", [str(cfg_uuid)])
    by_state = {row[0]: row[1] for row in cur.fetchall()}
    reported = {state: int(count or 0)
                for state, count in (report.get("counts_by_state") or {}).items()
                if int(count or 0)}
    check(f"{label}: состояния разбора в ответе равны состояниям строк в базе",
          by_state == reported, f"база {by_state}, отчёт {reported}")
    check(f"{label}: состояние parsed не встречается с пустым types (CHECK узла П1)",
          one(cur, f"SELECT count(*) FROM {SESSION_PARAMETER_TABLE} WHERE "
                   "configuration_uuid = %s::uuid AND type_parse_state = %s "
                   "AND types = '[]'::jsonb",
              [str(cfg_uuid), SP.STATE_PARSED]) == 0)

    cur.execute(f"SELECT types FROM {SESSION_PARAMETER_TABLE} "
                "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)])
    allowed = set(SP.TYPE_ENTRY_KEYS) | set(SP.TYPE_ENTRY_TARGET_KEYS)
    bad_entries = 0
    total_entries = 0
    for (entries,) in cur.fetchall():
        if isinstance(entries, str):
            entries = json.loads(entries)
        for entry in entries or []:
            total_entries += 1
            if not set(entry) <= allowed:
                bad_entries += 1
    check(f"{label}: словарь записей types закрыт (прецедент D3: ключи цели только у "
          "разрешённой ссылки)", bad_entries == 0, f"записей {total_entries}")
    check(f"{label}: types_total из ответа равен числу записей в jsonb",
          int(report.get("types_total") or 0) == total_entries,
          f"отчёт {report.get('types_total')}, база {total_entries}")

    check(f"{label}: статистика таблицы пересобрана загрузкой (мера V46)",
          int(report.get("statistics_refreshed") or 0) == 1
          and one(cur, "SELECT reltuples FROM pg_class WHERE relname = %s",
                  [SESSION_PARAMETER_TABLE]) >= 0,
          f"reltuples={one(cur, 'SELECT reltuples FROM pg_class WHERE relname = %s', [SESSION_PARAMETER_TABLE])}")


def check_reconciliation(cur, cfg_uuid, configuration_id, dump_dir, report, label):
    """Сверка двух источников круга против независимого сравнения каталога и перечня.

    Ответ стадии обязан называть `index_only` и `file_only` теми же множествами, что
    получены прямым сравнением имён из `configuration_objects` и имён файлов на диске:
    замер 2.2 даёт пустые множества, и пустые множества обязаны быть названы, а не
    подразумеваны (раздел 5 плана).
    """
    index_names = index_kind_names(cur, configuration_id)
    file_names = physical_file_names(dump_dir)
    check(f"{label}: индекс состава этого заголовка доступен ответу стадии",
          report.get("index_available") is True)
    check(f"{label}: index_records равно числу записей вида в перечне состава",
          int(report.get("index_records") or 0) == len(index_names),
          f"перечень {len(index_names)}, отчёт {report.get('index_records')}")
    check(f"{label}: file_only = файлы без записи перечня (независимое сравнение)",
          set(report.get("file_only") or [])
          == {SP.index_object_name(name) for name in (file_names - index_names)},
          f"отчёт {sorted(report.get('file_only') or [])}")
    check(f"{label}: index_only = записи перечня без файла (независимое сравнение)",
          set(report.get("index_only") or [])
          == {SP.index_object_name(name) for name in (index_names - file_names)},
          f"отчёт {sorted(report.get('index_only') or [])}")
    check(f"{label}: расхождений uuid файла и перечня на базовой линии нет (замер 2.2)",
          report.get("uuid_mismatch") == [], str(report.get("uuid_mismatch"))[:160])
    if index_names != file_names:
        note(f"{label}: круг каталога и перечня состава различаются — расхождение названо "
             f"ответом стадии (файлов {len(file_names)}, записей {len(index_names)})")
    else:
        check(f"{label}: нули сверки названы ответом, а не подразумеваются (замер 2.2)",
              report.get("file_only") == [] and report.get("index_only") == [])


def check_idempotency(cur, cfg_uuid, dump_dir, report, counts, first_moment):
    """Повтор той же выгрузки — снятие и запись заново, а не вторая ревизия (D8)."""
    print("\n=== загрузка №2: идемпотентность снятием, а не историей (D8) ===")
    # Пауза нужна не «ради паузы»: `changed_at` — TIMESTAMP без долей секунды, и две
    # загрузки внутри одной секунды получили бы одну метку. Без паузы проверка «повтор —
    # новое событие» проверяла бы точность часов, а не поведение слоя (приём пробы V46).
    time.sleep(1.1)
    again = SPL.load_session_parameters(str(dump_dir))
    check("загрузка №2 успешна", again["status"] == STATUS_OK and again["success"] is True,
          again.get("error"))
    check_contract_shape(again, "загрузка №2")
    check_text_render(again, "загрузка №2")
    check("снятые строки названы числом (removed_previous)",
          int(again.get("removed_previous") or 0) == int(report.get("rows_written") or 0),
          f"снято {again.get('removed_previous')}, было {report.get('rows_written')}")
    check("предупреждение о снятии прежних строк названо",
          any("Прежние строки" in w for w in again.get("warnings") or []))
    after = table_counts(cur, cfg_uuid)
    check("круг таблиц не вырос: повтор той же выгрузки не создаёт дублей", after == counts,
          f"{counts} → {after}")
    check("история состояний не заводится: revision_no остаётся 1",
          one(cur, f"SELECT max(revision_no) FROM {SESSION_PARAMETER_TABLE} "
                   "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) == FIRST_REVISION)
    second_moment = one(cur, f"SELECT max(changed_at) FROM {SESSION_PARAMETER_TABLE} "
                             "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)])
    check("повтор — новое событие загрузки (метка сменилась)", second_moment != first_moment,
          f"{first_moment} → {second_moment}")
    check("одна метка changed_at и на второй загрузке (M2)",
          one(cur, f"SELECT count(DISTINCT changed_at) FROM {SESSION_PARAMETER_TABLE} "
                   "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) == 1)
    return again


def check_removal_with_header(cur):
    """Снятие заголовка снимает и строки вида: сирот в схеме без FK быть не должно (V20.1).

    Фикстура — синтетический заголовок с собственным uuid и одна строка свойств: после
    `delete_configuration` не должно остаться ни строки заголовка, ни строки свойств.
    Настоящие заголовки проба не снимает: их состав проверяют проверки других узлов.
    """
    print("\n=== снятие заголовка снимает строки вида (дефект сирот) ===")
    fixture_uuid = str(uuid_module.uuid4())
    cur.execute("INSERT INTO configurations (name, uuid) VALUES (%s, %s::uuid) RETURNING id",
                [f"_v48_p4_fixture_{fixture_uuid[:8]}", fixture_uuid])
    fixture_id = int(cur.fetchone()[0])
    cur.execute(
        f"INSERT INTO {SESSION_PARAMETER_TABLE} (configuration_uuid, object_uuid, "
        "object_name, full_name, type_multiplicity, type_parse_state, source_path, "
        "changed_at, changed_by, is_committed) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, now(), %s, TRUE)",
        [fixture_uuid, fixture_uuid, "Фикстура", "Фикстура", SP.MULT_ABSENT,
         SP.STATE_ABSENT, "SessionParameters/Фикстура.xml", CHANGED_BY_LOAD],
    )
    cur.connection.commit()
    check("фикстура: строка свойств записана",
          table_counts(cur, fixture_uuid)[SESSION_PARAMETER_TABLE] == 1)
    removed = delete_configuration(cfg_id=fixture_id)
    check("delete_configuration назвала снятие строк вида",
          int((removed.get("children_deleted") or {}).get(SESSION_PARAMETER_TABLE) or 0) == 1,
          str(removed.get("children_deleted"))[:220])
    check("после снятия заголовка строк вида не осталось",
          table_counts(cur, fixture_uuid)[SESSION_PARAMETER_TABLE] == 0)
    check("сирот нет: каждая строка таблицы ссылается на строку заголовка",
          one(cur, f"SELECT count(*) FROM {SESSION_PARAMETER_TABLE} sp LEFT JOIN "
                   "configurations c ON c.uuid = sp.configuration_uuid WHERE c.id IS NULL") == 0)


def check_pipeline(cur, cfg_uuid, dump_dir, expected_files):
    """Конвейер целиком: стадию S4c вызывает `load_catalog` (force=True по уже загруженному).

    Отдельный слой и стадия — один и тот же код, поэтому проверка обязана подтвердить и
    карточку: раздел стадии в тексте есть, состояния и кратность названы, граница круга
    названа, а соседние стадии S4 (V46) и S4b (V47) не сломаны. Метки строк одной загрузки
    обязаны совпадать (M2).
    """
    print("\n=== конвейер: стадия S4c внутри load_catalog (V46 → V48 → V47) ===")
    result = load_catalog(str(dump_dir), force=True)
    card = format_load_result(result)
    check("конвейер вернул успех", result.get("success") is True, result.get("error"))
    part = result.get("session_parameters") or {}
    expected_keys = sorted(session_parameters_defaults())
    check("конвейер вернул раздел S4c закрытым контрактом стадии",
          sorted(part) == expected_keys,
          "лишнее: " + ", ".join(sorted(set(part) - set(expected_keys)))
          + "; нет: " + ", ".join(sorted(set(expected_keys) - set(part))))
    check("стадия S4c конвейера успешна", part.get("status") == STATUS_OK, part.get("error"))
    check("стадия записала весь круг (числа конвейера равны замеру 2.1)",
          int(part.get("rows_written") or 0) == expected_files, part.get("rows_written"))
    check_written(cur, cfg_uuid, int(result.get("id") or 0), dump_dir, part, expected_files,
                  "конвейер")
    check("карточка загрузки содержит раздел стадии S4c",
          SESSION_PARAMETERS_SECTION_HEADER in card)
    check("карточка называет состояния разбора и кратность значений",
          "Состояния разбора типа:" in card and "Кратность значений типа:" in card)
    check("карточка называет границу круга узла V48", SESSION_PARAMETERS_BOUNDARY in card)
    check("карточка называет SessionParameter среди видов с загруженным содержимым",
          "SessionParameter" in card and "узлы V46 и V48" in card)
    check("карточка не обещает незакрытой частью то, что закрыто узлом V48",
          "свойства параметров сеанса" in card and "позиция 2.3" in card)
    child = result.get("child_objects") or {}
    modules = result.get("object_modules") or {}
    check("стадия S4 (V46) после встраивания S4c работает", child.get("success") is True,
          child.get("error"))
    check("стадия S4b (V47) после встраивания S4c работает", modules.get("success") is True,
          modules.get("error"))
    check("разделы карточки соседних стадий на месте",
          CHILD_SECTION_HEADER in card and OBJECT_MODULES_SECTION_HEADER in card)
    check("метки строк свойств и модулей одной загрузки совпадают (M2)",
          one(cur, f"SELECT max(changed_at) FROM {SESSION_PARAMETER_TABLE} "
                   "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)])
          == one(cur, "SELECT max(changed_at) FROM bsl_modules WHERE "
                      "configuration_uuid = %s::uuid AND parent_type = "
                      "'configuration_objects'", [str(cfg_uuid)]))
    check("сирот после конвейера нет",
          one(cur, f"SELECT count(*) FROM {SESSION_PARAMETER_TABLE} sp LEFT JOIN "
                   "configurations c ON c.uuid = sp.configuration_uuid WHERE c.id IS NULL") == 0)
    note("строки стадии S4c остаются в базе: их записал конвейер, и снимать их после "
         "конвейера — значит оставить конфигурацию без только что записанного содержимого")


def run_dump(cur, name):
    """Полный прогон слоя на одной выгрузке: загрузка → сверка → повтор → идемпотентность."""
    dump_dir = DUMP_ROOT / name
    if not dump_dir.is_dir():
        check(f"{name}: каталог выгрузки существует", False, str(dump_dir))
        return None
    info = configuration_uuid_from_layout(str(dump_dir))
    if "uuid" not in info:
        check(f"{name}: uuid конфигурации прочитан из Configuration.xml", False,
              info.get("error"))
        return None
    cfg_uuid = str(info["uuid"])
    header = find_configuration(cfg_uuid)
    if not header:
        check(f"{name}: заголовок этой конфигурации загружен в базу", False, cfg_uuid)
        return None
    cfg_id = int(header["id"])
    print(f"\n=== выгрузка {name}: uuid={cfg_uuid}, configuration_id={cfg_id} ===")
    baseline = table_counts(cur, cfg_uuid)
    if any(baseline.values()):
        note(f"{name}: в таблице уже есть строки этой конфигурации ({baseline}) — "
             "идемпотентность проверяется повторным прогоном по ним же")

    print("--- загрузка №1 (текстов модулей у вида нет, флага просьбы нет) ---")
    report = SPL.load_session_parameters(str(dump_dir))
    check(f"{name}: загрузка №1 успешна",
          report["status"] == STATUS_OK and report["success"] is True, report.get("error"))
    check_contract_shape(report, f"{name}: загрузка №1")
    check_text_render(report, f"{name}: загрузка №1")
    check_written(cur, cfg_uuid, cfg_id, dump_dir, report, BASELINE_FILES[name],
                  f"{name} загрузка №1")
    check_reconciliation(cur, cfg_uuid, cfg_id, dump_dir, report, f"{name} загрузка №1")
    check(f"{name}: ответ называет, чем повторять стадию (отдельного MCP-инструмента пока "
          "нет — шаг П5)",
          any("load_1c_catalog_tool" in w for w in report.get("warnings") or []))
    unresolved_total = int(report.get("types_unresolved_total") or 0)
    check(f"{name}: число неразрешённых ссылок не меньше числа приведённых примеров",
          unresolved_total >= len(report.get("types_unresolved") or []),
          f"всего {unresolved_total}, примеров {len(report.get('types_unresolved') or [])}")
    if unresolved_total:
        note(f"{name}: неразрешённых ссылок {unresolved_total} — это данные или новое "
             "правило перехода (раздел 5 плана), молча NULL они не остаются")
    else:
        check(f"{name}: неразрешённых ссылок нет (замер 2.5: 24 из 24 разрешаются)",
              unresolved_total == 0)

    counts = table_counts(cur, cfg_uuid)
    first_moment = one(cur, f"SELECT max(changed_at) FROM {SESSION_PARAMETER_TABLE} "
                            "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)])
    if name == "MinCfg":
        check_partial_refusal(cur, cfg_uuid, counts, make_broken_fixture(dump_dir))
    again = check_idempotency(cur, cfg_uuid, dump_dir, report, counts, first_moment)
    check_written(cur, cfg_uuid, cfg_id, dump_dir, again, BASELINE_FILES[name],
                  f"{name} загрузка №2")
    return cfg_uuid


def rows_by_configuration(cur):
    """Сколько строк таблицы относится к каждой конфигурации (снимок состояния базы).

    Глобальное «таблица пуста» пробой не было и не является: конвейер пишет реальный состав
    стадий, и строки других конфигураций — штатное состояние базы (замер 29.10.2026: строки
    BP3 и BGU2, записанные отдельным входом группы). Сравнивается именно это: круг пробы
    обязан стать пустым, чужие круги — не измениться.
    """
    cur.execute(f"SELECT configuration_uuid, count(*) FROM {SESSION_PARAMETER_TABLE} "
                "GROUP BY 1")
    return {str(row[0]).lower(): int(row[1]) for row in cur.fetchall()}


def restore_baseline(cur, cfg_uuids, foreign_before):
    """Вернуть базовое состояние: проба не оставляет за собой строк после своих прогонов.

    Снятие фиксируется той же транзакцией, что и проверка нулей после него: без `commit`
    соединение пробы откатило бы очистку при закрытии, и база осталась бы с записанными
    строками — проба обязана возвращать базовое состояние, а не обещать его (приём П5 V46).
    Чужие круги при этом не тронуты: сравнение по конфигурациям, которых проба не касалась.
    """
    print("\n=== очистка за пробой и возврат базового состояния ===")
    for cfg_uuid in cfg_uuids:
        removed = SPL.remove_session_parameters(cur, cfg_uuid)
        note(f"снято строк по {cfg_uuid[:8]}: {removed}")
    cur.connection.commit()
    for cfg_uuid in cfg_uuids:
        after = table_counts(cur, cfg_uuid)
        check(f"после очистки круг таблиц пуст ({cfg_uuid[:8]})", not any(after.values()),
              str(after))
    tested = {str(item).lower() for item in cfg_uuids}
    after_by_cfg = rows_by_configuration(cur)
    foreign_after = {key: value for key, value in after_by_cfg.items() if key not in tested}
    foreign_snapshot = {key: value for key, value in foreign_before.items()
                        if key not in tested}
    check("чужие конфигурации проба не тронула (строки по конфигурациям совпали)",
          foreign_after == foreign_snapshot,
          f"до: {foreign_snapshot}, после: {foreign_after}")
    check("сирот нет: каждая строка таблицы ссылается на строку заголовка",
          one(cur, f"SELECT count(*) FROM {SESSION_PARAMETER_TABLE} sp LEFT JOIN "
                   "configurations c ON c.uuid = sp.configuration_uuid WHERE c.id IS NULL") == 0)
    note(f"состояние таблицы после пробы: строк по базе — {sum(after_by_cfg.values())}, "
         f"конфигураций — {len(after_by_cfg)} (строки других конфигураций — штатные)")


def main() -> int:
    chosen = tuple(arg for arg in sys.argv[1:] if arg in DUMPS) or DUMPS
    print("Проба V48 П4: слой свойств параметров сеанса (стадия S4c) — " + ", ".join(chosen))
    print("Загрузчик фиксирует свои транзакции; проба убирает за собой и возвращает "
          "базовое состояние: круг пробы пуст, чужие круги не тронуты (приём пробы П5 "
          "узла V46, переформулирован узлом V48).")
    conn = connect()
    try:
        cur = conn.cursor()
        baseline_total = one(cur, f"SELECT count(*) FROM {SESSION_PARAMETER_TABLE}")
        note(f"базовое состояние: строк по всей базе — {baseline_total}")
        # Снимок по конфигурациям: проба обязана вернуть состояние чужих кругов, а не
        # «пустую таблицу» — строки других конфигураций в базе штатны.
        foreign_snapshot = rows_by_configuration(cur)
        check_stage_registration(cur)
        check_refusals(cur, baseline_total)
        check_removal_with_header(cur)
        tested = [cfg for cfg in (run_dump(cur, name) for name in chosen) if cfg]
        if not tested:
            check("хотя бы одна выгрузка проверена", False, "проверяемых выгрузок нет")
            return _summary()
        restore_baseline(cur, tested, foreign_snapshot)
        # Конвейер проверяется ПОСЛЕ очистки намеренно: он обязан записать строки сам, и
        # после него строки остаются (снять их — значит оставить конфигурацию без только
        # что записанного содержимого). Итог печатается последним всегда.
        if "MinCfg" in chosen:
            info = configuration_uuid_from_layout(str(DUMP_ROOT / "MinCfg"))
            if "uuid" in info:
                check_pipeline(cur, str(info["uuid"]), DUMP_ROOT / "MinCfg",
                               BASELINE_FILES["MinCfg"])
        return _summary()
    finally:
        conn.close()


def _summary() -> int:
    """Итог пробы: число проваленных проверок, а не общее «успешно»."""
    print("\n" + "=" * 72)
    print(f"ИТОГ: пройдено {PASSED}, провалено {FAILED}, замечаний {len(NOTES)}")
    if FAILED:
        print("Проваленные проверки перечислены выше строками [FAIL]; причина называется "
              "там же — молчать про них итог не должен.")
    return FAILED


if __name__ == "__main__":
    sys.exit(main())



