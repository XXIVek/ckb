#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П4 узла V50: слой свойств общих реквизитов (стадия S4e).

Предмет проверки — не разбор файлов (его закрыл П2) и не писатели (П3), а слой и его
встраивание в конвейер:

  1. стадия зарегистрирована в `STAGES` между `s4d_roles` и `s4b_object_modules` (позиция
     2.5 нормативного списка), имеет свой ключ ответа `common_attributes` (правило C3) и свой
     закрытый контракт (C1); круг стадии S4 (`CHILD_TABLES`) не тронут, таблицы вида названы
     чужими стадиями (`FOREIGN_STAGE_TABLES`);
  2. отказ слоя называется состоянием контракта, а не исключением и не нулями (C1, C2):
     каталог не читается, uuid разошлись, строки заголовка нет, файл круга не разбирается;
     ни один отказ не меняет круг таблиц в базе;
  3. успех: строки двух таблиц записаны, числа ответа совпадают с тем, что легло в таблицы,
     состояния названы, каждая строка применения ссылается на CURRENT-ревизию своей строки
     реквизита (Q2, вариант A), сверка каталога с индексом состава соответствует независимому
     сравнению, статистика двух таблиц собрана (мера V46);
  4. повтор той же выгрузки идемпотентен: снятие названо двумя таблицами (M7 — снятие
     начинается с применения, иначе каскад FK снял бы его молча), дублей нет, `revision_no`
     не растёт (D8), метка загрузки меняется (новое событие);
  5. пустой круг KomMag (каталога вида нет — замер 2.9) НЕ является отказом: `files_found = 0`
     с наблюдением `directory_missing`, стадия проходит, нули названы (Q9);
  6. конвейер (`load_catalog`, `force=True`) вызывает стадию, карточка содержит раздел стадии
     с состояниями и границей круга, порядок разделов повторяет порядок стадий
     (S4c → S4d → S4e → S4b), соседние стадии S4d (V49) и S4b (V47) не сломаны, метки строк
     одной загрузки совпадают (M2), а `delete_configuration` снимает строки вида вместе с
     заголовком — сирот не остаётся;
  7. время стадии называется замером (критерий раздела 7 плана: без `ANALYZE` читатели
     витрин текущего состояния платят минутами, и прогон обязан назвать число).

Эталон — числа раздела 7 плана `docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md` (замеры 2.1,
2.4, 2.5, 2.6, 2.7, 2.9), а не память ассистента: расхождение с ними — провал прогона.

Проба работает с живой БД. Строки, записанные конвейером, остаются в базе намеренно: снимать
их после конвейера — значит оставить конфигурацию без только что записанного содержимого
(приём пробы П4 узлов V48 и V49). Разбор файлов и ограничения схемы проба не проверяет — их
закрыли П2 и П3; синтетическая фикстура заголовка снимается за собой.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v50_p4_loader_probe.py [MinCfg KomMag]   # базовая линия
    python _v50_p4_loader_probe.py BGU2              # отдельно, замер времени
    python _v50_p4_loader_probe.py BP3               # отдельно, замер времени

Код возврата 0 — расхождений нет. Прогоны, меняющие общее состояние БД, не параллелят.
"""
import sys
import time
import uuid as uuid_module
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_common_attributes as CA  # noqa: E402
import configuration_common_attributes_loader as CAL  # noqa: E402
# Карточка и конвейер — те же точки входа, что читает оператор: проба проверяет слой вместе
# с его встраиванием, а не только вызов функции.
from config_load_router import format_load_result, load_catalog  # noqa: E402
from configuration_load_contract import (  # noqa: E402
    CHILD_SECTION_HEADER,
    CHILD_TABLES,
    COMMON_ATTRIBUTES_BOUNDARY,
    COMMON_ATTRIBUTES_DIR,
    COMMON_ATTRIBUTES_SECTION_HEADER,
    COMMON_ATTRIBUTES_TABLES,
    COMMON_ATTRIBUTE_TABLE,
    COMMON_ATTRIBUTE_TARGETS_TABLE,
    FOREIGN_STAGE_TABLES,
    OBJECT_MODULES_SECTION_HEADER,
    ROLES_SECTION_HEADER,
    SESSION_PARAMETERS_SECTION_HEADER,
    STAGES,
    STAGE_COMMON_ATTRIBUTES,
    STAGE_OBJECT_MODULES,
    STAGE_ROLES,
    STAGE_SESSION_PARAMETERS,
    STATUS_ERROR,
    STATUS_NOT_RUN,
    STATUS_OK,
    common_attributes_defaults,
    format_common_attributes_lines,
    stages_after,
    stage_resume_hint,
)
from configuration_loader import delete_configuration, find_configuration  # noqa: E402
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from current_revision import (  # noqa: E402
    CHANGED_BY_LOAD, CONFIGURATION_VERSIONED_TABLES, FIRST_REVISION, current_view,
)
from external_db import connect  # noqa: E402
from external_table_writer import (  # noqa: E402
    CONFIGURATION_OBJECT_WRITERS, CONFIGURATION_UNVERSIONED_TABLES,
)

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DEFAULT_DUMPS = ("MinCfg", "KomMag")
UNLOADED_CANDIDATES = ("Config_NULL", "UNF3", "UT11", "ZUP10")
FIXTURE_DIR = ROOT / "_scratch" / "v50_p4_fixtures"
ATTRIBUTES_TABLE = COMMON_ATTRIBUTE_TABLE
TARGETS_TABLE = COMMON_ATTRIBUTE_TARGETS_TABLE

# Витрина текущего состояния есть только у версионируемой таблицы вида. У
# `common_attribute_targets` своей цепи ревизий нет (Q2, вариант A), поэтому её текущим
# кругом считается сама таблица: строки снимаются явным `DELETE` вместе со своим
# реквизитом. Разница названа здесь, а не спрятана: `current_view` на неверсионируемой
# таблице бросает исключение.
VIEW_BY_TABLE = {
    table: (current_view(table) if table in CONFIGURATION_VERSIONED_TABLES else table)
    for table in COMMON_ATTRIBUTES_TABLES
}


# Эталон раздела 7 плана (`docs/CONFIGURATION_COMMON_ATTRIBUTES_PLAN.md`) и замеры 2.1, 2.4,
# 2.5, 2.6, 2.7, 2.9: что обязан записать слой на каждой выгрузке. Числа держит проба, а не
# память ассистента: расхождение с ними — это провал прогона, а не расхождение двух
# пересчётов. `separation` — разборка по ОДНОМУ блоку (на строку их три), `types` — состояния
# блока `<Type>` по строкам реквизита, а не по записям значений.
BASELINE = {
    "MinCfg": {
        "attributes": 2, "targets": 3, "files": 2, "index_rows": 2,
        "content": {"with_content": 2}, "properties": {"all_known": 2},
        "use": {"used": 3}, "resolve": {"exact": 3}, "item_cond": {"empty_value": 3},
        "separation": {"empty_value": 2, "parsed": 0, "unknown_form": 0},
        "types": {"parsed": 2}, "multiplicity": {"single": 1, "composite": 1},
        "types_total": 4, "classes": {"primitive": 4},
        "distinct": 3, "max_per_file": 2,
        "kinds": {"Catalog": 1, "Document": 1, "InformationRegister": 1},
    },
    # KomMag: позиции вида нет ни файлами, ни строками индекса (замер 2.9). Пустой круг —
    # состояние выгрузки, а не отказ прогона (Q9): стадия обязана пройти с нулями и назвать
    # наблюдение `directory_missing`.
    "KomMag": {
        "attributes": 0, "targets": 0, "files": 0, "index_rows": 0,
        "content": {}, "properties": {}, "use": {}, "resolve": {}, "item_cond": {},
        "separation": {}, "types": {}, "multiplicity": {}, "types_total": 0, "classes": {},
        "distinct": 0, "max_per_file": 0, "kinds": {}, "directory_missing": True,
    },
    "BGU2": {
        "attributes": 7, "targets": 692, "files": 7, "index_rows": 7,
        "content": {"with_content": 7}, "properties": {"all_known": 7},
        "use": {"used": 127, "not_used": 565}, "resolve": {"exact": 692},
        "item_cond": {"empty_value": 692},
        "separation": {"empty_value": 5, "parsed": 2, "unknown_form": 0},
        "types": {"parsed": 7}, "multiplicity": {"single": 7},
        "types_total": 7, "classes": {"primitive": 7},
        "distinct": 584, "max_per_file": 565,
        "kinds": {"Catalog": 78, "ChartOfCharacteristicTypes": 5, "Constant": 188,
                  "ExchangePlan": 1, "InformationRegister": 262, "IntegrationService": 1,
                  "ScheduledJob": 157},
    },
    "BP3": {
        "attributes": 7, "targets": 817, "files": 7, "index_rows": 7,
        "content": {"with_content": 7}, "properties": {"all_known": 7},
        "use": {"used": 129, "not_used": 688}, "resolve": {"exact": 817},
        "item_cond": {"empty_value": 817},
        "separation": {"empty_value": 5, "parsed": 2, "unknown_form": 0},
        "types": {"parsed": 7}, "multiplicity": {"single": 7},
        "types_total": 7, "classes": {"primitive": 7},
        "distinct": 706, "max_per_file": 688,
        "kinds": {"Catalog": 121, "ChartOfCharacteristicTypes": 5, "Constant": 204,
                  "ExchangePlan": 1, "InformationRegister": 299, "IntegrationService": 1,
                  "ScheduledJob": 186},
    },
}
# Что эталон раздела 7 НЕ замерял: предопределённость (O2) и обратные отсылки из форм и
# функциональных опций (O5). Проба сверяет эти состояния с самой базой — отчёт обязан
# равняться строкам таблиц, — а не с числом, которого в замере нет.
UNMEASURED_STATES = ("counts_by_properties_state",)
SEPARATION_BLOCK_COLUMNS: tuple = tuple(CA.SEPARATION_BLOCKS)

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


def table_counts(cur, cfg_uuid):
    """Число строк каждой таблицы круга на эту конфигурацию (таблица, а не витрина)."""
    out = {}
    for table in COMMON_ATTRIBUTES_TABLES:
        cur.execute(f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
                    [str(cfg_uuid)])
        out[table] = int(cur.fetchone()[0])
    return out


def view_counts(cur, cfg_uuid):
    """Строки витрины текущего состояния: текущность читается витриной, а не таблицей."""
    out = {}
    for table in COMMON_ATTRIBUTES_TABLES:
        cur.execute(f"SELECT count(*) FROM {VIEW_BY_TABLE[table]} "
                    "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)])
        out[table] = int(cur.fetchone()[0])
    return out



def group_counts(cur, sql, params=None):
    cur.execute(sql, params or ())
    return {str(row[0]): int(row[1]) for row in cur.fetchall()}


def counts_now(cur, cfg_uuid):
    """Круг таблиц на момент вызова (для проверок, которым нужен свежий снимок)."""
    return table_counts(cur, cfg_uuid)


def versioned_tables_with_rows(counts):
    """Версионируемые таблицы вида, у которых ЕСТЬ строки этого круга.

    Пустая таблица (KomMag: ни одной строки — замер 2.9) даёт NULL по агрегатам
    `max(revision_no)` и `max(changed_at)`; сравнение NULL с ревизией или с меткой загрузки
    было бы провалом пробы, а не загрузки. Проверки цепи и метки применяются к непустым
    кругам, а пустой круг называется отдельной строкой — иначе «проверок не было» читается
    как «всё проверено».
    """
    return [table for table in (ATTRIBUTES_TABLE,)
            if table in CONFIGURATION_VERSIONED_TABLES and counts[table]]


def rows_by_configuration(cur, table):
    """Сколько строк таблицы относится к каждой конфигурации (снимок состояния базы).

    Глобальное «таблица пуста» пробой не было и не является: конвейер пишет реальный состав,
    и строки других конфигураций — штатное состояние базы. Сравнивается именно это: круг
    пробы меняется предсказуемо, чужие круги не меняются вовсе.
    """
    cur.execute(f"SELECT configuration_uuid, count(*) FROM {table} GROUP BY 1")
    return {str(row[0]).lower(): int(row[1]) for row in cur.fetchall()}


def index_ca_names(cur, configuration_id):
    """Индексные имена общих реквизитов из перечня (`CommonAttribute.<Имя>`).

    Независимый источник круга: тот же запрос к `configuration_objects`, но без колонок
    разбора — проба сверяет ответ слоя с перечнем, а не переиспользует его код. Берётся
    полное точечное имя (`name`), а не короткое (`object_name`): по короткому имени запись
    индекса не совпала бы с именем файла регистрации, и проба видела бы `index_only` +
    `file_only` там, где круг совпадает (урок `index_row_key` узла V48).
    """
    cur.execute(
        "SELECT name FROM configuration_objects WHERE configuration_id = %s "
        "AND object_type = %s", [int(configuration_id), CA.INDEX_OBJECT_TYPE])
    return {str(row[0]) for row in cur.fetchall()}


def disk_ca_names(dump_dir):
    """Индексные имена общих реквизитов файлами каталога — второй независимый источник.

    Имя файла регистрации переводится в индексное тем же правилом, которым его выводит
    разбор (замер 2.9: `<Имя>.xml` ↔ `CommonAttribute.<Имя>`); сравнивать стем файла с
    точечным именем перечня — значит увидеть расхождение там, где его нет.
    """
    files, _observations = CA.iter_registration_files(str(dump_dir))
    return {CA.index_object_name(Path(str(item["path"])).stem) for item in files}


def check_stage_registration():
    """Стадия в `STAGES` на позиции нормативного списка и со своим ключом ответа (C3).

    Порядок `STAGES` — то, что читает человек в подсказке об останове, и то, по чему
    конвейер решает, какую стадию не выполнять. Ошибка на один элемент перечня даёт либо
    пропущенное «свойства общих реквизитов не загружены», либо обещание стадии, которой нет.
    """
    print("\n=== регистрация стадии S4e в контракте конвейера ===")
    ids = [stage for stage, _title in STAGES]
    check("стадия S4e зарегистрирована", STAGE_COMMON_ATTRIBUTES in ids, str(ids))
    check("порядок стадий повторяет нормативный список: s4d → s4e → s4b (позиция 2.5)",
          ids.index(STAGE_SESSION_PARAMETERS) < ids.index(STAGE_ROLES)
          < ids.index(STAGE_COMMON_ATTRIBUTES) < ids.index(STAGE_OBJECT_MODULES), str(ids))
    check("после отказа s4e пропущенной остаётся только s4b_object_modules (критерий П8)",
          stages_after(STAGE_COMMON_ATTRIBUTES) == [STAGE_OBJECT_MODULES],
          str(stages_after(STAGE_COMMON_ATTRIBUTES)))
    check("после отказа s4d пропущенной остаётся s4e (стадия не пропущена молча)",
          STAGE_COMMON_ATTRIBUTES in stages_after(STAGE_ROLES),
          str(stages_after(STAGE_ROLES)))
    hint = stage_resume_hint(STAGE_COMMON_ATTRIBUTES)
    check("подсказка об останове называет отдельный вход группы (критерий П8)",
          "load_common_attributes_tool" in hint, hint[:160])
    defaults = common_attributes_defaults()
    check("ключ ответа стадии назван тем же адресом, что и в STAGES",
          defaults.get("stage") == STAGE_COMMON_ATTRIBUTES, str(defaults.get("stage")))
    check("контракт называет обе таблицы вида, а не одну",
          list(defaults.get("tables") or []) == list(COMMON_ATTRIBUTES_TABLES),
          str(defaults.get("tables")))
    check("состояние не выполненной стадии отличается от отказа (C2)",
          defaults.get("status") == STATUS_NOT_RUN, str(defaults.get("status")))
    check("круг стадии S4 (V46) не тронут: таблиц вида в нём нет",
          not set(COMMON_ATTRIBUTES_TABLES) & set(CHILD_TABLES),
          str(sorted(set(COMMON_ATTRIBUTES_TABLES) & set(CHILD_TABLES))))
    check("таблицы вида названы чужими стадиями (реестр версионности V19 их не затрагивает)",
          set(COMMON_ATTRIBUTES_TABLES) <= set(FOREIGN_STAGE_TABLES),
          str(FOREIGN_STAGE_TABLES))
    check("писатели обеих таблиц зарегистрированы общим реестром",
          all(table in CONFIGURATION_OBJECT_WRITERS for table in COMMON_ATTRIBUTES_TABLES))
    check("строка применения не версионируется своей цепью (Q2, вариант A)",
          TARGETS_TABLE in CONFIGURATION_UNVERSIONED_TABLES
          and ATTRIBUTES_TABLE not in CONFIGURATION_UNVERSIONED_TABLES,
          str(sorted(CONFIGURATION_UNVERSIONED_TABLES)))
    not_run = format_common_attributes_lines(defaults)
    check("текст не выполненной стадии называет это состоянием, а не нулями (C2)",
          any("Стадия не выполнена" in line for line in not_run), str(not_run[:2]))
    check("текст не выполненной стадии называет, чем продолжить",
          any("load_common_attributes_tool" in line for line in not_run))




def make_broken_fixture(dump_dir):
    """Фикстура «файл круга не разбирается» (каталог плоский — примитивность вида, замер 2.1).

    Фикстура нужна одному: отказ разбора файла круга обязан останавливать стадию ДО записи
    (приём V12/V46), а на настоящих выгрузках этого не проверить — там файлов круга нет с
    ошибками (замер 2.1). uuid фикстуры совпадает с uuid выгрузки-источника, поэтому
    заголовок находится, и отказ обязан быть про файл, а не про заголовок.
    """
    import shutil

    fixture = FIXTURE_DIR / "BrokenCommonAttributes"
    if fixture.exists():
        shutil.rmtree(fixture)
    (fixture / CA.DIR_NAME).mkdir(parents=True, exist_ok=True)
    shutil.copy(dump_dir / "Configuration.xml", fixture / "Configuration.xml")
    files, _observations = CA.iter_registration_files(str(dump_dir))
    if not files:
        return None
    shutil.copy(files[0]["path"], fixture / CA.DIR_NAME / files[0]["file_name"])
    (fixture / CA.DIR_NAME / "БитыйОбщийРеквизит.xml").write_text(
        "<CommonAttribute><Name", encoding="utf-8")
    return fixture


def check_refusals(cur, dump_dir, cfg_uuid):
    """Отказы слоя называются состоянием контракта и не меняют круг таблиц (C1, C2)."""
    print("\n=== отказы: каталог, расхождение uuid, отсутствие заголовка, битый файл ===")
    missing_dir = CAL.load_common_attributes(str(DUMP_ROOT / "_нет_такого_каталога"))
    check("каталог, которого нет, отклонён, а не сведён к нулям",
          missing_dir["status"] == STATUS_ERROR and missing_dir["success"] is False,
          str(missing_dir.get("error"))[:160])

    other_uuid = str(uuid_module.uuid4())
    mismatch = CAL.load_common_attributes(str(dump_dir), configuration_uuid=other_uuid)
    check("расхождение uuid каталога и переданного — отказ, а не выбор одного",
          mismatch["status"] == STATUS_ERROR and other_uuid in (mismatch.get("error") or ""),
          str(mismatch.get("error"))[:160])

    unloaded = None
    for name in UNLOADED_CANDIDATES:
        candidate = DUMP_ROOT / name
        if not candidate.is_dir():
            continue
        info = configuration_uuid_from_layout(str(candidate))
        if "uuid" in info and not find_configuration(str(info["uuid"])):
            unloaded = candidate
            break
    if unloaded is None:
        note("выгрузки без строки заголовка среди кандидатов нет — отказ «заголовка нет» "
             "этим прогоном не проверен; отсутствие проверки названо, а не снято молча")
    else:
        no_header = CAL.load_common_attributes(str(unloaded))
        check("без строки заголовка слой отказывает и называет точку входа",
              no_header["status"] == STATUS_ERROR
              and "load_1c_catalog_tool" in (no_header.get("error") or ""),
              str(no_header.get("error"))[:200])

    before = table_counts(cur, cfg_uuid)
    fixture = make_broken_fixture(dump_dir)
    if fixture is None:
        note("выгрузка без файлов вида — фикстура битого файла не построена; случай отказа "
             "разбора на этом прогоне не проверен")
        return before
    broken = CAL.load_common_attributes(str(fixture))
    check("битый файл круга останавливает стадию", broken["status"] == STATUS_ERROR,
          (broken.get("error") or "")[:200])
    check("отказ разбора называет файл и причину",
          "БитыйОбщийРеквизит.xml" in (broken.get("error") or ""),
          (broken.get("error") or "")[:200])
    after = table_counts(cur, cfg_uuid)
    check("ни одна строка круга не записана и прежние не сняты (приём V12/V46)",
          after == before, f"до {before}, после {after}")
    check("отказ называет, чем продолжить",
          any("load_common_attributes_tool" in w for w in broken.get("warnings") or []))
    check("отказ не привносит ключей сверх контракта (C1)",
          set(broken) == set(common_attributes_defaults()),
          "лишние: " + ", ".join(sorted(set(broken) - set(common_attributes_defaults())))
          + "; нет: " + ", ".join(sorted(set(common_attributes_defaults()) - set(broken))))
    return before


def expected_counts(baseline):
    """Ожидаемое число строк каждой таблицы по эталону плана (двумя таблицами, не одним)."""
    return {ATTRIBUTES_TABLE: baseline["attributes"], TARGETS_TABLE: baseline["targets"]}


def check_written(cur, cfg_uuid, cfg_id, dump_dir, report, baseline, label):
    """Числа ответа равны строкам таблиц, а строки таблиц равны эталону раздела 7.

    Сверяются три круга, а не один: отчёт ↔ таблицы ↔ эталон замера. Отчёт, равный самому
    себе, ничего не утверждает; таблицы без отчёта не читаются карточкой. Отдельно
    проверяется ссылка каждой строки применения на CURRENT-ревизию своей строки реквизита
    (Q2, вариант A): своей цепи ревизий у `common_attribute_targets` нет, и «цепочка есть у
    реквизита» без этой проверки означала бы висящие строки применения.
    """
    written = report.get("written_by_table") or {}
    expected = expected_counts(baseline)
    counts = table_counts(cur, cfg_uuid)
    for table in COMMON_ATTRIBUTES_TABLES:
        check(f"{label}: ответ назвал число строк {table}",
              int(written.get(table) or 0) == expected[table],
              f"отчёт {written.get(table)}, эталон {expected[table]}")
        check(f"{label}: строки {table} легли в таблицу тем же числом",
              counts[table] == expected[table],
              f"таблица {counts[table]}, эталон {expected[table]}")
    check(f"{label}: rows_written равен сумме двух таблиц, а не одному числу",
          int(report.get("rows_written") or 0) == sum(counts.values())
          and int(report.get("attributes_written") or 0) == counts[ATTRIBUTES_TABLE]
          and int(report.get("targets_written") or 0) == counts[TARGETS_TABLE],
          str(counts))
    check(f"{label}: реквизитов прочитано столько, сколько строк таблицы реквизитов",
          int(report.get("files_read") or 0) == counts[ATTRIBUTES_TABLE],
          f"отчёт {report.get('files_read')}, таблица {counts[ATTRIBUTES_TABLE]}")
    check(f"{label}: файлов регистрации названо по кругу выгрузки (замер 2.1)",
          int(report.get("files_found") or 0) == len(disk_ca_names(dump_dir)),
          f"отчёт {report.get('files_found')}")

    # ── витрины текущего состояния: одна ревизия, сирот нет ─────────────────────────────
    views = view_counts(cur, cfg_uuid)
    for table in COMMON_ATTRIBUTES_TABLES:
        check(f"{label}: витрина {VIEW_BY_TABLE[table]} отдаёт тот же круг, что таблица",
              views[table] == counts[table], f"витрина {views[table]}, таблица {counts[table]}")
    checked = versioned_tables_with_rows(counts)
    check(f"{label}: цепь ревизий не разрастается: max(revision_no) = 1 (D8)",
          all(one(cur, f"SELECT max(revision_no) FROM {table} "
                       "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) == FIRST_REVISION
              for table in checked))
    if not checked:
        note(f"{label}: таблица {ATTRIBUTES_TABLE} этого круга пуста (KomMag — замер 2.9) — "
             "цепь ревизий и метка загрузки по ней не проверяются; пустой круг назван, а не "
             "скрыт")
    check(f"{label}: каждая строка применения ссылается на CURRENT-ревизию своего реквизита "
          "(Q2)",
          one(cur, "SELECT count(*) FROM common_attribute_targets t "
                   "JOIN v_current_common_attributes ca ON ca.id = t.common_attribute_id "
                   "WHERE t.configuration_uuid = %s::uuid",
              [str(cfg_uuid)]) == counts[TARGETS_TABLE],
          f"применения {counts[TARGETS_TABLE]}")
    check(f"{label}: применений, висящих на не-текущей или чужой ревизии реквизита, нет",
          one(cur, "SELECT count(*) FROM common_attribute_targets t "
                   "LEFT JOIN v_current_common_attributes ca ON ca.id = t.common_attribute_id "
                   "WHERE t.configuration_uuid = %s::uuid AND ca.id IS NULL",
              [str(cfg_uuid)]) == 0)
    check(f"{label}: применения не перепутали конфигурации (configuration_uuid строки "
          "применения совпадает с конфигурацией реквизита)",
          one(cur, "SELECT count(*) FROM common_attribute_targets t "
                   "JOIN common_attributes ca ON ca.id = t.common_attribute_id "
                   "WHERE t.configuration_uuid IS DISTINCT FROM ca.configuration_uuid") == 0)
    check(f"{label}: uuid и индексное имя реквизита в строке применения совпадают с его "
          "строкой (цель держится индексным именем, а не коротким — модель раздела 4 плана)",
          one(cur, "SELECT count(*) FROM common_attribute_targets t "
                   "JOIN common_attributes ca ON ca.id = t.common_attribute_id "
                   "WHERE t.configuration_uuid = %s::uuid "
                   "AND (t.attribute_object_uuid IS DISTINCT FROM ca.object_uuid "
                   "OR t.attribute_full_name IS DISTINCT FROM %s || '.' || ca.object_name)",
              [str(cfg_uuid), CA.INDEX_OBJECT_TYPE]) == 0)
    return counts


def nonzero(mapping):
    """Эталон без нулевых позиций — в том виде, в котором их отдаёт `GROUP BY`.

    Нули в эталоне нужны человеку (словарь состояний замкнут), но `GROUP BY` нулевых групп
    не отдаёт; сравнивать словарь замера с группировкой напрямую — значит увидеть
    расхождение там, где его нет.
    """
    return {str(key): int(value) for key, value in (mapping or {}).items() if int(value)}


def check_states(cur, cfg_uuid, report, baseline, counts, label):
    """Состояния: отчёт = строки таблиц = эталон раздела 7.

    Каждое состояние проверяется двумя равенствами — отчёта таблице и таблицы эталону. Одно
    только равенство отчёта таблице ничего не утверждает про выгрузку, а одно равенство
    эталону не утверждает про то, что отчёт эти строки назвал.
    """
    by_use = group_counts(cur, "SELECT use_state, count(*) FROM common_attribute_targets "
                               "WHERE configuration_uuid = %s::uuid GROUP BY 1",
                          [str(cfg_uuid)])
    check(f"{label}: use_state в таблицах равен эталону (2.4: «не применяется» отдельно от "
          "«не перечислен»)", by_use == nonzero(baseline["use"]), f"база {by_use}")
    check(f"{label}: counts_by_use_state отчёта равен строкам таблицы",
          {k: v for k, v in (report.get("counts_by_use_state") or {}).items() if v} == by_use,
          f"отчёт {report.get('counts_by_use_state')}")

    by_resolve = group_counts(cur, "SELECT target_resolve_state, count(*) FROM "
                                   "common_attribute_targets WHERE configuration_uuid = "
                                   "%s::uuid GROUP BY 1", [str(cfg_uuid)])
    check(f"{label}: состояния разрешения целей равны эталону (2.6: 1 512 из 1 512 exact)",
          by_resolve == nonzero(baseline["resolve"]), f"база {by_resolve}")
    check(f"{label}: counts_by_target_resolve_state отчёта равен строкам таблицы",
          {k: v for k, v in (report.get("counts_by_target_resolve_state") or {}).items()
           if v} == by_resolve, f"отчёт {report.get('counts_by_target_resolve_state')}")
    check(f"{label}: у неразрешённой цели состояние не расходится с текстом отсылки",
          one(cur, "SELECT count(*) FROM common_attribute_targets WHERE "
                   "configuration_uuid = %s::uuid AND ((target_resolve_state = 'exact' AND "
                   "target_object_uuid IS NULL) OR (target_resolve_state <> 'exact' AND "
                   "target_object_uuid IS NOT NULL))", [str(cfg_uuid)]) == 0)
    check(f"{label}: вид цели строки применения равен верхнему сегменту её полного имени "
          "(2.5)",
          one(cur, "SELECT count(*) FROM common_attribute_targets WHERE "
                   "configuration_uuid = %s::uuid AND target_kind <> "
                   "split_part(target_full_name, '.', 1)", [str(cfg_uuid)]) == 0)
    by_kind = group_counts(cur, "SELECT target_kind, count(*) FROM common_attribute_targets "
                                "WHERE configuration_uuid = %s::uuid GROUP BY 1",
                           [str(cfg_uuid)])
    check(f"{label}: распределение целей по видам равно эталону (2.5)",
          by_kind == nonzero(baseline["kinds"]), f"база {by_kind}")
    check(f"{label}: targets_by_kind отчёта равен строкам таблицы",
          report.get("targets_by_kind") == by_kind, f"отчёт {report.get('targets_by_kind')}")

    by_cond = group_counts(cur, "SELECT conditional_separation_state, count(*) FROM "
                                "common_attribute_targets WHERE configuration_uuid = "
                                "%s::uuid GROUP BY 1", [str(cfg_uuid)])
    check(f"{label}: условие разделения позиции равно эталону (2.4: пустой тег во всех "
          "строках)", by_cond == nonzero(baseline["item_cond"]), f"база {by_cond}")
    check(f"{label}: counts_by_item_cond_state отчёта равен строкам таблицы",
          {k: v for k, v in (report.get("counts_by_item_cond_state") or {}).items() if v}
          == by_cond, f"отчёт {report.get('counts_by_item_cond_state')}")
    check(f"{label}: порядки применения не имеют разрывов внутри реквизита",
          one(cur, "SELECT count(*) FROM (SELECT common_attribute_id, count(*) AS c, "
                   "max(ordinal) AS m, min(ordinal) AS n FROM common_attribute_targets "
                   "WHERE configuration_uuid = %s::uuid GROUP BY 1) x WHERE x.c <> x.m - x.n "
                   "+ 1", [str(cfg_uuid)]) == 0)
    check(f"{label}: повторяющихся целей в перечне одного реквизита нет (2.10)",
          not (report.get("duplicate_targets") or []), str(report.get("duplicate_targets")))
    check(f"{label}: targets_total / targets_distinct / max_targets_per_file равны эталону "
          "(2.4: распределение называется)",
          int(report.get("targets_total") or 0) == baseline["targets"]
          and int(report.get("targets_distinct") or 0) == baseline["distinct"]
          and int(report.get("max_targets_per_file") or 0) == baseline["max_per_file"],
          f"отчёт {report.get('targets_total')}/{report.get('targets_distinct')}/"
          f"{report.get('max_targets_per_file')}")
    check(f"{label}: неразрешённых целей применения нет (2.6: лучший результат круга)",
          not (report.get("unresolved_targets") or [])
          and int(report.get("targets_total") or 0) == by_resolve.get("exact", 0),
          str(report.get("unresolved_targets"))[:160])

    by_content = group_counts(cur, "SELECT content_state, count(*) FROM common_attributes "
                                   "WHERE configuration_uuid = %s::uuid GROUP BY 1",
                              [str(cfg_uuid)])
    check(f"{label}: content_state равен эталону (2.4: перечень есть у всех файлов)",
          by_content == nonzero(baseline["content"]), f"база {by_content}")
    check(f"{label}: counts_by_content_state отчёта равен строкам таблицы",
          {k: v for k, v in (report.get("counts_by_content_state") or {}).items() if v}
          == by_content, f"отчёт {report.get('counts_by_content_state')}")
    check(f"{label}: счётчики применения строки реквизита равны её строкам применения "
          "(targets_count / used / not_used)",
          one(cur, "SELECT count(*) FROM common_attributes ca LEFT JOIN (SELECT "
                   "common_attribute_id, count(*) AS c, count(*) FILTER (WHERE use_state = "
                   "'used') AS u, count(*) FILTER (WHERE use_state = 'not_used') AS n FROM "
                   "common_attribute_targets GROUP BY 1) x ON x.common_attribute_id = ca.id "
                   "WHERE ca.configuration_uuid = %s::uuid AND (ca.targets_count IS "
                   "DISTINCT FROM COALESCE(x.c, 0) OR ca.targets_used_count IS DISTINCT FROM "
                   "COALESCE(x.u, 0) OR ca.targets_not_used_count IS DISTINCT FROM "
                   "COALESCE(x.n, 0))", [str(cfg_uuid)]) == 0)
    check(f"{label}: с состоянием with_content применение больше нуля, с empty_content — "
          "ровно ноль",
          one(cur, "SELECT count(*) FROM common_attributes WHERE configuration_uuid = "
                   "%s::uuid AND ((content_state = 'with_content' AND targets_count = 0) OR "
                   "(content_state = 'empty_content' AND targets_count > 0))",
              [str(cfg_uuid)]) == 0)

    by_props = group_counts(cur, "SELECT properties_state, count(*) FROM common_attributes "
                                 "WHERE configuration_uuid = %s::uuid GROUP BY 1",
                            [str(cfg_uuid)])
    check(f"{label}: состояния свойств равны эталону (2.2: 38 тегов, словарь замкнут)",
          by_props == nonzero(baseline["properties"]), f"база {by_props}")
    check(f"{label}: неизвестных значений словарных свойств нет (критерий раздела 7)",
          not any(report.get("unknown_value_properties") or {}),
          str(report.get("unknown_value_properties")))
    check(f"{label}: неизвестных тегов файла нет (2.2)",
          not any(report.get("unexpected_tags") or {}), str(report.get("unexpected_tags")))

    by_type = group_counts(cur, "SELECT type_parse_state, count(*) FROM common_attributes "
                                "WHERE configuration_uuid = %s::uuid GROUP BY 1",
                           [str(cfg_uuid)])
    check(f"{label}: состояния блока <Type> равны эталону (2.3: parsed по всем файлам)",
          by_type == nonzero(baseline["types"]), f"база {by_type}")
    by_mult = group_counts(cur, "SELECT type_multiplicity, count(*) FROM common_attributes "
                                "WHERE configuration_uuid = %s::uuid GROUP BY 1",
                           [str(cfg_uuid)])
    check(f"{label}: кратность типов равна эталону (2.3: composite — один файл MinCfg)",
          by_mult == nonzero(baseline["multiplicity"]), f"база {by_mult}")
    check(f"{label}: counts_by_type_state и types_multiplicity отчёта равны строкам таблицы",
          {k: v for k, v in (report.get("counts_by_type_state") or {}).items() if v}
          == by_type
          and {k: v for k, v in (report.get("types_multiplicity") or {}).items() if v}
          == by_mult, f"отчёт {report.get('counts_by_type_state')}")
    check(f"{label}: types_total равен числу записей jsonb, а не числу файлов (2.3)",
          int(report.get("types_total") or 0) == baseline["types_total"]
          and int(one(cur, "SELECT COALESCE(SUM(jsonb_array_length(types)), 0) FROM "
                           "common_attributes WHERE configuration_uuid = %s::uuid",
                      [str(cfg_uuid)])) == baseline["types_total"],
          f"отчёт {report.get('types_total')}")
    check(f"{label}: расхождения числа тегов <v8:Type> и разобраных записей нет (2.3)",
          not (report.get("value_tag_mismatch") or []),
          str(report.get("value_tag_mismatch")))
    check(f"{label}: types_by_class отчёта равна числу записей по классам (2.3)",
          {k: v for k, v in (report.get("types_by_class") or {}).items() if v}
          == baseline["classes"], f"отчёт {report.get('types_by_class')}")

    # ── разделение данных: три блока считаются раздельно (граница раздела 5 плана) ──────
    by_block = report.get("separation_by_block") or {}
    check(f"{label}: сводка разделения названа тремя блоками, а не агрегатом",
          set(by_block) == set(SEPARATION_BLOCK_COLUMNS), str(sorted(by_block)))
    for block in SEPARATION_BLOCK_COLUMNS:
        by_parse = group_counts(cur, f"SELECT {block}_parse_state, count(*) FROM "
                                     "common_attributes WHERE configuration_uuid = %s::uuid "
                                     "GROUP BY 1", [str(cfg_uuid)])
        check(f"{label}: состояния блока {block} равны эталону (2.7: пустой блок является "
              "состоянием строки)", by_parse == nonzero(baseline["separation"]), f"база {by_parse}")
        block_state = by_block.get(block) or {}
        check(f"{label}: сводка блока {block} отчёта равна строкам таблицы",
              {k: v for k, v in (block_state.get("by_parse_state") or {}).items() if v}
              == by_parse, f"отчёт {block_state.get('by_parse_state')}")
        by_block_resolve = group_counts(
            cur, f"SELECT {block}_resolve_state, count(*) FROM common_attributes WHERE "
                 "configuration_uuid = %s::uuid AND "
                 f"{block}_parse_state = 'parsed' GROUP BY 1", [str(cfg_uuid)])
        parsed_rows = int(baseline["separation"].get("parsed", 0))
        check(f"{label}: разрешение ссылок блока {block} равняется эталону (2.7: 12 из 12)",
              by_block_resolve == ({"exact": parsed_rows} if parsed_rows else {}),
              f"база {by_block_resolve}")
    check(f"{label}: суммарные состояния разделения равны трём блокам (48 блоков корпуса)",
          int(report.get("separation_parsed") or 0)
          == 3 * int(baseline["separation"].get("parsed", 0))
          and int(report.get("separation_empty") or 0)
          == 3 * int(baseline["separation"].get("empty_value", 0))
          and int(report.get("separation_unknown_form") or 0) == 0,
          f"отчёт parsed={report.get('separation_parsed')} "
          f"empty={report.get('separation_empty')}")
    check(f"{label}: неразрешённых ссылок разделения нет (2.7)",
          not (report.get("separation_unresolved") or [])
          and int(report.get("separation_unresolved_total") or 0) == 0,
          str(report.get("separation_unresolved"))[:160])
    check(f"{label}: текст называет пустые блоки числом, а не подразумеваемым нулём",
          int(report.get("separation_empty") or 0)
          == 3 * int(baseline["separation"].get("empty_value", 0)))
    check(f"{label}: статистика двух таблиц пересобрана загрузкой (мера V46)",
          int(report.get("statistics_refreshed") or 0) == len(COMMON_ATTRIBUTES_TABLES),
          f"обновлено {report.get('statistics_refreshed')}")


def check_reconciliation(cur, cfg_uuid, cfg_id, dump_dir, report, baseline, label):
    """Два источника круга против независимого сравнения каталога и перечня.

    Ответ стадии обязан называть `index_only`, `file_only` и `uuid_mismatch` теми же
    множествами, что получены прямым сравнением имён из `configuration_objects` и файлов на
    диске: замер 2.9 даёт пустые множества на всех четырёх выгрузках, и пустые множества
    обязаны быть названы числом, а не подразумеваться (раздел 5 плана).
    """
    index_names = index_ca_names(cur, cfg_id)
    disk_names = disk_ca_names(dump_dir)
    check(f"{label}: индекс состава этого заголовка доступен ответу стадии",
          report.get("index_available") is True)
    check(f"{label}: index_kind_records равно числу записей `CommonAttribute.<Имя>` (2.9)",
          int(report.get("index_kind_records") or 0) == len(index_names),
          f"перечень {len(index_names)}, отчёт {report.get('index_kind_records')}")
    check(f"{label}: file_only = файлы без записи перечня (независимое сравнение)",
          {CA.index_object_name(Path(str(path)).stem)
           for path in (report.get("file_only") or [])}
          == (disk_names - index_names),
          f"отчёт {sorted(report.get('file_only') or [])}")
    check(f"{label}: index_only = записи перечня без файла (независимое сравнение)",
          {str(name) for name in (report.get("index_only") or [])}
          == (index_names - disk_names),
          f"отчёт {sorted(report.get('index_only') or [])}")
    check(f"{label}: расхождений uuid файла и перечня на базовой линии нет (замер 2.9)",
          report.get("uuid_mismatch") == [], str(report.get("uuid_mismatch"))[:160])
    if index_names or disk_names:
        check(f"{label}: нули сверки названы ответом, а не подразумеваются (замер 2.9)",
              report.get("file_only") == [] and report.get("index_only") == [])
        check(f"{label}: предупреждения о разных кругах каталога и перечня нет при равных",
              not any("Записей `CommonAttribute.<Имя>` в индексе состава" in w
                      for w in report.get("warnings") or []))
    else:
        check(f"{label}: пустой круг назван наблюдением directory_missing, а не отказом (Q9)",
              any(obs[0] == "directory_missing" for obs in report.get("observations") or []),
              str(report.get("observations")))
        check(f"{label}: предупреждение об отсутствии каталога названо",
              any("CommonAttributes" in w and "отсутствует" in w
                  for w in report.get("warnings") or []),
              str([w[:80] for w in report.get("warnings") or []])[:240])
    check(f"{label}: предупреждение о повторе стадии отдельным входом названо",
          any("load_common_attributes_tool" in w for w in report.get("warnings") or []),
          str([w[:80] for w in report.get("warnings") or []])[:240])
    check(f"{label}: предупреждения о незнакомых префиксах пространства имён нет (2.1)",
          not any("префикс" in w.lower() for w in report.get("warnings") or []),
          str([w[:80] for w in report.get("warnings") or []])[:240])



# Граница времени стадии (критерий раздела 7 плана). Порог намеренно грубый: прогон обязан
# назвать ЧИСЛО и поймать квадратичную деградацию (например разрешение целей запросом на
# строку), а не доказать, что стадия быстрее соседней. Замер меньше порога — это число в
# заметке, а не обещание оптимизации.
TIME_LIMIT_S = 120.0

RENDER_MARKERS = (
    "Записано строк по таблицам:",
    "Файлов регистрации:",
    "Состояния свойств:",
    "Блок Type:",
    "Перечни применения:",
    "Применение:",
    "Цели применения по видам:",
    "Разделение, блок data_separation_value:",
    "Разделение, блок data_separation_use:",
    "Разделение, блок conditional_separation:",
    "Сверка с индексом состава:",
)
# Пустой круг KomMag печатает те же разделы нулями — «реквизитов нет» обязано быть
# названным числом, а не отсутствием раздела; единственная непечатаемая строка — перечень
# видов целей (`targets_by_kind` пуст, форматёр его опускает).
RENDER_MARKERS_EMPTY = (
    "Записано строк по таблицам:",
    "Файлов регистрации: 0",
    "Прежних строк этой конфигурации не снималось",
    "Состояния свойств:",
    "Блок Type:",
    "Перечни применения:",
    "Применение:",
    "Разделение, блок data_separation_value:",
    "Разделение всего:",
    "Сверка с индексом состава:",
)

# Ключи ответа, по которым повтор обязан совпасть с первым прогоном: совпадение чисел строк
# без совпадения состояний не доказывает, что повтор не изменил разбор.
STATE_KEYS = ("counts_by_content_state", "counts_by_use_state",
              "counts_by_target_resolve_state", "counts_by_item_cond_state",
              "counts_by_properties_state", "counts_by_type_state", "types_by_class",
              "types_multiplicity", "separation_by_block", "targets_by_kind",
              "types_total", "targets_total", "targets_distinct", "max_targets_per_file",
              "separation_parsed", "separation_empty", "separation_unknown_form",
              "separation_unresolved_total", "file_only", "index_only", "uuid_mismatch",
              "value_tag_mismatch", "unexpected_tags", "unknown_value_properties",
              "duplicate_targets", "unresolved_targets")


def check_text_render(report, baseline, label):
    """Текст стадии строится по закрытому контракту и называет записанное (C1, C3).

    Раздел читает человек, машинную часть читает вызывающий; если форматёр молчит о
    состояниях, человек получает «загружено» без ответа о том, что именно сохранено. Для
    пустого круга KomMag ожидается свой набор строк: «реквизитов нет» обязано быть названо
    нулём и границей, а не отсутствием раздела.
    """
    lines = format_common_attributes_lines(report, indent="   ")
    check(f"{label}: текст стадии непустой и состоит из строк",
          bool(lines) and all(isinstance(line, str) for line in lines), f"строк {len(lines)}")
    markers = RENDER_MARKERS if baseline["attributes"] else RENDER_MARKERS_EMPTY
    missing = [marker for marker in markers
               if not any(marker in line for line in lines)]
    check(f"{label}: текст называет каждый раздел стадии (числа без текста не читаются)",
          not missing, "нет разделов: " + ", ".join(missing))
    check(f"{label}: каждая строка текста начинается с отступа вызывающего",
          all(line.startswith("   ") for line in lines))
    total_line = next((line for line in lines
                       if "Записано строк по таблицам:" in line), "")
    check(f"{label}: итог в тексте равен числу rows_written ответа",
          f"всего {int(report.get('rows_written') or 0)}" in total_line, total_line[:200])
    for table in COMMON_ATTRIBUTES_TABLES:
        check(f"{label}: текст называет число строк каждой таблицы, а не одно общее",
              f"{table}=" in total_line, total_line[:200])
    check(f"{label}: граница круга названа в тексте успеха (успех ≠ «об общих реквизитах "
          "всё сохранено»)",
          any(COMMON_ATTRIBUTES_BOUNDARY in line for line in lines)
          or any(COMMON_ATTRIBUTES_DIR in line for line in lines),
          str(lines[-1])[:200] if lines else "")
    check(f"{label}: текст называет позиции словарей состояний нулями, а не пропуском",
          all(token in "".join(lines) for token in ("unknown_value=0", "prefix_only=0",
                                                    "unknown_form=0")),
          str(lines[:6])[:200])


def check_contract_shape(report, label):
    """Ответ слоя держит закрытый контракт: ключей нет ни больше, ни меньше (C1, C3).

    Лишний ключ — разрыв контракта для читающего карточку; недостающий читается нулём и
    маскируется под «данных нет». Оба варианта правкой не лечатся, поэтому провал здесь
    дороже, чем кажется.
    """
    defaults = common_attributes_defaults()
    extra = sorted(set(report) - set(defaults))
    missing = sorted(set(defaults) - set(report))
    check(f"{label}: ответ слоя не привносит ключей сверх контракта", not extra,
          "лишние: " + ", ".join(extra))
    check(f"{label}: каждый ключ контракта присутствует в ответе (C1)", not missing,
          "нет: " + ", ".join(missing))
    check(f"{label}: ключ стадии назван тем же адресом, что и в STAGES",
          report.get("stage") == STAGE_COMMON_ATTRIBUTES, str(report.get("stage")))
    check(f"{label}: таблицы ответа — две таблицы вида, порядок снятия сохранён",
          report.get("tables") == list(COMMON_ATTRIBUTES_TABLES), str(report.get("tables")))
    check(f"{label}: порядок снятия начинается с таблицы применения (M7)",
          list(CAL.REMOVE_ORDER) == [TARGETS_TABLE, ATTRIBUTES_TABLE],
          str(CAL.REMOVE_ORDER))



def attribute_uuids(cur, cfg_uuid):
    """`object_uuid` строк реквизитов этого круга — по ним читатель ссылается на строку.

    Повтор той же выгрузки обязан оставить те же значения: смена uuid при повторе означала
    бы потерю ссылок, которых в схеме нет осознанно (прецедент V20.1).
    """
    cur.execute(f"SELECT object_uuid FROM {ATTRIBUTES_TABLE} WHERE configuration_uuid = "
                "%s::uuid ORDER BY 1", [str(cfg_uuid)])
    return [str(row[0]).lower() for row in cur.fetchall()]


def table_columns(cur, table):
    """Колонки таблицы из `information_schema` — независимая проверка формы таблицы.

    Признак версионирования (`revision_no`, `changed_*`) ищется здесь, а не в ключах
    выборки: `rows_by_configuration` отдаёт круг по конфигурациям, а не состав колонок.
    """
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                [table])
    return [str(row[0]) for row in cur.fetchall()]


def check_idempotency(cur, dump_dir, cfg_uuid, baseline, label, first):
    """Повторный вызов той же выгрузки даёт тот же круг (критерий раздела 7).

    Снятое и записанное обязаны равняться эталону, строки — не удваиваться, `revision_no` —
    не расти (история состояний не заводится, D8), uuid строк — оставаться прежними: по ним
    читатель ссылается на строку, и смена uuid при повторе означала бы потерю ссылок.
    Формулировка «снимает прежние строки и пишет заново» проверяется числом снятых строк,
    а не только итогом.
    """
    before = table_counts(cur, cfg_uuid)
    uuids_before = attribute_uuids(cur, cfg_uuid)
    check(f"{label}: до повтора в таблицах ровно круг выгрузки",
          before == expected_counts(baseline), f"до {before}")
    started = time.monotonic()
    # Метка повторной загрузки называется вызывающим явно: строки одного события обязаны
    # нести одну метку (M2), и проверить это можно только сравнением с названным значением.
    # Сравнение часов двух прогонов было бы проверкой часов, а не загрузки: колонка хранит
    # секунды, и два вызова в пределах секунды дали бы равную метку — прогон падал бы на
    # скорости машины, а не на состоянии базы.
    moment = datetime.now().replace(microsecond=0) + timedelta(days=1)
    second = CAL.load_common_attributes(str(dump_dir), configuration_uuid=str(cfg_uuid),
                                       changed_at=moment)
    elapsed = time.monotonic() - started
    ok2 = check_text_render(second, baseline, f"{label} повтор")
    check(f"{label}: повторный вызов возвращает успех", second.get("success") is True
          and second.get("status") == STATUS_OK,
          str(second.get("error"))[:200])
    counts2 = check_written(cur, cfg_uuid, second["configuration_id"], dump_dir, second,
                           baseline, f"{label} повтор")
    check(f"{label}: повтор называет снятые строки прежним кругом (формулировка плана)",
          second.get("removed_by_table") == before, f"снято {second.get('removed_by_table')}")
    check(f"{label}: снятое и записанное на повторе равны кругу",
          int(second.get("removed_previous") or 0) == int(second.get("rows_written") or 0)
          == sum(expected_counts(baseline).values()),
          f"снято {second.get('removed_previous')}, записано {second.get('rows_written')}")
    check(f"{label}: строки не удваиваются", counts2 == before, f"после {counts2}")
    uuids_after = attribute_uuids(cur, cfg_uuid)
    check(f"{label}: uuid строк реквизитов не меняются при повторе (на них ссылается "
          "читатель)", uuids_after == uuids_before,
          f"было {len(uuids_before)}, стало {len(uuids_after)}")
    check(f"{label}: revision_no не растёт при повторе (история состояний не заводится, D8)",
          one(cur, f"SELECT count(*) FROM {ATTRIBUTES_TABLE} WHERE configuration_uuid = "
                   "%s::uuid AND revision_no <> 1", [str(cfg_uuid)]) == 0,
          str(one(cur, f"SELECT max(revision_no) FROM {ATTRIBUTES_TABLE} WHERE "
                       "configuration_uuid = %s::uuid", [str(cfg_uuid)])))
    check(f"{label}: метки строк повторной загрузки равны названной вызывающим метке (M2)",
          (not counts2[ATTRIBUTES_TABLE])
          or one(cur, f"SELECT count(*) FROM {ATTRIBUTES_TABLE} WHERE configuration_uuid "
                      "= %s::uuid AND changed_at IS DISTINCT FROM %s",
                 [str(cfg_uuid), moment]) == 0,
          f"названная метка {moment}")
    check(f"{label}: ответ называет момент загрузки строк той же меткой, что легла в строки",
          (not counts2[ATTRIBUTES_TABLE])
          or any("Момент загрузки строк реквизитов" in warning for warning
                 in second.get("warnings") or []),
          str([warning[:60] for warning in second.get("warnings") or []])[:200])
    unversioned = [column for column in table_columns(cur, TARGETS_TABLE)
                   if column.startswith(("revision", "changed_"))]
    check(f"{label}: таблица применения не имеет колонок версионирования (Q1, вариант A)",
          not unversioned, str(unversioned))
    check(f"{label}: таблица реквизитов своими колонками версионирования держит цепь",
          {"revision_no", "changed_at", "changed_by", "is_committed"}
          <= set(table_columns(cur, ATTRIBUTES_TABLE)))
    check(f"{label}: повтор не оставляет дублей по уникальным ключам",
          one(cur, "SELECT count(*) - count(DISTINCT (configuration_uuid, object_uuid)) "
                   "FROM common_attributes WHERE configuration_uuid = %s::uuid",
              [str(cfg_uuid)]) == 0
          and one(cur, "SELECT count(*) - count(DISTINCT (common_attribute_id, "
                       "target_full_name, ordinal)) FROM common_attribute_targets t JOIN "
                       "common_attributes ca ON ca.id = t.common_attribute_id WHERE "
                       "ca.configuration_uuid = %s::uuid", [str(cfg_uuid)]) == 0)
    check(f"{label}: состояния повтора равны состояниям первого прогона",
          {key: second.get(key) for key in STATE_KEYS}
          == {key: first.get(key) for key in STATE_KEYS},
          "состояния повтора отличаются: "
          + ", ".join(key for key in STATE_KEYS
                      if second.get(key) != first.get(key)))
    note(f"{label}: повтор стадии занял {elapsed:.2f} с")
    return second


def check_removal_with_header(cur):
    """Снятие заголовка снимает строки вида: сирот в схеме без FK быть не должно (V20.1).

    Фикстура — синтетический заголовок с собственным uuid и по одной строке каждой из двух
    таблиц: после `delete_configuration` не должно остаться ни строки заголовка, ни строк
    вида. Настоящие заголовки проба не снимает: их состав проверяют проверки других узлов.
    Фикстура с строкой применения нужна отдельно — на ней же проверяется, что каскад FK не
    подменяет явный `DELETE`: применение снимается вместе со своим реквизитом в любом случае,
    но назвать его числом обязан именно явный `DELETE` (M7).
    """
    print("\n=== снятие заголовка снимает строки вида (дефект сирот) ===")
    fixture_uuid = str(uuid_module.uuid4())
    cur.execute("INSERT INTO configurations (name, uuid) VALUES (%s, %s::uuid) RETURNING id",
                [f"_v50_p4_fixture_{fixture_uuid[:8]}", fixture_uuid])
    fixture_id = int(cur.fetchone()[0])
    cur.execute(
        f"INSERT INTO {ATTRIBUTES_TABLE} (configuration_uuid, object_uuid, object_name,"
        " full_name, data_separation_value_parse_state, data_separation_use_parse_state,"
        " conditional_separation_parse_state, type_multiplicity, type_parse_state, types,"
        " content_state, targets_count, targets_used_count, targets_not_used_count,"
        " properties_state, source_path, revision_no, changed_at, changed_by, is_committed)"
        " VALUES (%s::uuid, %s::uuid, %s, %s, 'empty_value', 'empty_value',"
        " 'empty_value', 'absent', 'absent', '[]'::jsonb, 'with_content', 1, 1, 0,"
        " 'all_known', %s, 1, now(), %s, TRUE) RETURNING id",
        [fixture_uuid, fixture_uuid, "Фикстура", "ОбщийРеквизит.Фикстура",
         "CommonAttributes/Фикстура.xml", CHANGED_BY_LOAD],
    )
    attribute_id = int(cur.fetchone()[0])
    cur.execute(
        f"INSERT INTO {TARGETS_TABLE} (common_attribute_id, configuration_uuid,"
        " attribute_object_uuid, attribute_full_name, ordinal, target_kind,"
        " target_full_name, target_resolve_state, target_unresolved_path, use_state,"
        " conditional_separation_state) VALUES (%s, %s::uuid, %s::uuid,"
        " 'ОбщийРеквизит.Фикстура', 0, 'Catalog', 'Справочник.Фикстура', 'unresolved',"
        " 'Справочник.Фикстура', 'used', 'empty_value')",
        [attribute_id, fixture_uuid, fixture_uuid],
    )
    cur.connection.commit()
    before = table_counts(cur, fixture_uuid)
    check("фикстура: строки обеих таблиц записаны",
          all(before[table] == 1 for table in COMMON_ATTRIBUTES_TABLES), str(before))
    removed = delete_configuration(cfg_id=fixture_id)
    deleted = removed.get("children_deleted") or {}
    for table in COMMON_ATTRIBUTES_TABLES:
        check(f"delete_configuration назвал снятие строк {table}",
              int(deleted.get(table) or 0) == 1, str(deleted)[:220])
    check("после снятия заголовка строк вида не осталось",
          not any(table_counts(cur, fixture_uuid).values()))
    for table in COMMON_ATTRIBUTES_TABLES:
        check(f"сирот нет: каждая строка {table} ссылается на строку заголовка",
              one(cur, f"SELECT count(*) FROM {table} t LEFT JOIN configurations c ON "
                       f"c.uuid = t.configuration_uuid WHERE c.id IS NULL") == 0)



def run_dump(cur, name):
    """Полный прогон слоя на одной выгрузке: загрузка → сверка → повтор → идемпотентность.

    Время стадии замеряется на каждом прогоне и называется числом (критерий раздела 7
    плана): без `ANALYZE` читатели витрин текущего состояния платят минутами, и прогон
    обязан назвать то, что он потратил сам.
    """
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
    baseline = BASELINE[name]

    print("--- загрузка №1 (одна транзакция на две таблицы круга) ---")
    started = time.time()
    report = CAL.load_common_attributes(str(dump_dir))
    first_seconds = time.time() - started
    check(f"{name}: загрузка №1 успешна",
          report["status"] == STATUS_OK and report["success"] is True, report.get("error"))
    if report.get("status") != STATUS_OK:
        return None
    check_contract_shape(report, f"{name}: загрузка №1")
    check_text_render(report, baseline, f"{name}: загрузка №1")
    check_written(cur, cfg_uuid, cfg_id, dump_dir, report, baseline, f"{name} загрузка №1")
    check_states(cur, cfg_uuid, report, baseline, table_counts(cur, cfg_uuid),
                 f"{name} загрузка №1")
    check_reconciliation(cur, cfg_uuid, cfg_id, dump_dir, report, baseline,
                        f"{name} загрузка №1")
    check(f"{name}: время стадии первой загрузки меньше границы замера (раздел 7 плана)",
          first_seconds < TIME_LIMIT_S, f"{first_seconds:.2f} с")
    note(f"{name}: время стадии S4e (загрузка №1) — {first_seconds:.2f} с на "
         f"{baseline['attributes']} реквизитов, {baseline['targets']} применений")

    again = check_idempotency(cur, dump_dir, cfg_uuid, baseline, f"{name} загрузка №2",
                              report)
    check_written(cur, cfg_uuid, cfg_id, dump_dir, again, baseline, f"{name} загрузка №2")
    check_states(cur, cfg_uuid, again, baseline, table_counts(cur, cfg_uuid),
                 f"{name} загрузка №2")
    return cfg_uuid


def rows_by_configuration_snapshot(cur):
    """Снимок «сколько строк какой конфигурации в каждой таблице вида» (состояние базы).

    Глобальное «таблица пуста» пробой не было и не является: строки других конфигураций —
    штатное состояние базы (их пишет конвейер и отдельный вход группы). Сравнивается
    именно это: круг пробы обязан стать пустым, чужие круги — не измениться.
    """
    return {table: rows_by_configuration(cur, table) for table in COMMON_ATTRIBUTES_TABLES}


def restore_baseline(cur, cfg_uuids, foreign_before):
    """Вернуть базовое состояние: проба не оставляет за собой строк после своих прогонов.

    Снятие фиксируется той же транзакцией, что и проверка нулей после него: без `commit`
    соединение пробы откатил бы очистку при закрытии, и база осталась бы с записанными
    строками. Порядок снятия — с `common_attribute_targets`: каскад FK снимал бы применение
    молча, и счётчик снятия был бы неправдой (M7).
    """
    print("\n=== очистка за пробой и возврат базового состояния ===")
    for cfg_uuid in cfg_uuids:
        removed = CAL.remove_common_attributes(cur, cfg_uuid)
        note(f"снято строк по {cfg_uuid[:8]}: {removed}")
    cur.connection.commit()
    for cfg_uuid in cfg_uuids:
        after = table_counts(cur, cfg_uuid)
        check(f"после очистки круг двух таблиц пуст ({cfg_uuid[:8]})",
              not any(after.values()), str(after))
    tested = {str(item).lower() for item in cfg_uuids}
    for table in COMMON_ATTRIBUTES_TABLES:
        after_by_cfg = rows_by_configuration(cur, table)
        foreign_after = {key: value for key, value in after_by_cfg.items()
                         if key not in tested}
        foreign_snapshot = {key: value for key, value in foreign_before[table].items()
                            if key not in tested}
        check(f"чужие конфигурации проба не тронула ({table})",
              foreign_after == foreign_snapshot,
              f"до: {foreign_snapshot}, после: {foreign_after}")
        check(f"сирот нет: каждая строка {table} ссылается на строку заголовка",
              one(cur, f"SELECT count(*) FROM {table} t LEFT JOIN configurations c ON "
                       f"c.uuid = t.configuration_uuid WHERE c.id IS NULL") == 0)



def check_pipeline(cur, cfg_uuid, dump_dir, baseline, label):
    """Конвейер целиком: стадию S4e вызывает `load_catalog` (force=True по уже загруженному).

    Отдельный слой и стадия — один и тот же код, поэтому проверяется и карточка: раздел
    стадии в тексте есть, порядок разделов повторяет порядок стадий (S4c → S4d → S4e → S4b),
    соседние стадии S4c (V48), S4d (V49), S4 (V46) и S4b (V47) не сломаны, метки строк одной
    загрузки совпадают (M2). Порядок разделов проверяется именно в тексте карточки: порядок
    стадий в `STAGES` ещё не значит, что карточка печатает разделы в этом порядке.
    """
    print(f"\n=== конвейер: стадия S4e внутри load_catalog ({label}) ===")
    started = time.time()
    result = load_catalog(str(dump_dir), force=True)
    pipeline_seconds = time.time() - started
    card = format_load_result(result)
    check("конвейер вернул успех", result.get("success") is True, result.get("error"))
    part = result.get("common_attributes") or {}
    check("конвейер вернул раздел S4e закрытым контрактом стадии (C3)",
          sorted(part) == sorted(common_attributes_defaults()),
          "лишнее: " + ", ".join(sorted(set(part) - set(common_attributes_defaults())))
          + "; нет: " + ", ".join(sorted(set(common_attributes_defaults()) - set(part))))
    check("стадия S4e конвейера успешна", part.get("status") == STATUS_OK, part.get("error"))
    check("числа конвейера равны эталону прямой загрузки",
          {table: int((part.get("written_by_table") or {}).get(table) or 0)
           for table in COMMON_ATTRIBUTES_TABLES} == expected_counts(baseline),
          str(part.get("written_by_table")))
    cfg_id = int(result.get("id") or 0)
    check_written(cur, cfg_uuid, cfg_id, dump_dir, part, baseline, f"конвейер {label}")
    check_states(cur, cfg_uuid, part, baseline, table_counts(cur, cfg_uuid),
                 f"конвейер {label}")
    check_reconciliation(cur, cfg_uuid, cfg_id, dump_dir, part, baseline, f"конвейер {label}")

    check("карточка загрузки содержит раздел стадии S4e",
          COMMON_ATTRIBUTES_SECTION_HEADER in card)
    check("карточка называет состояния свойств, типов, применения и разделения",
          "Состояния свойств:" in card and "Блок Type:" in card
          and "Перечни применения:" in card and "Разделение, блок data_separation_value:"
          in card)
    check("карточка называет границу круга узла V50", COMMON_ATTRIBUTES_BOUNDARY in card)
    check("карточка называет каталог вида позицией 2.5 нормативного списка",
          f"{COMMON_ATTRIBUTES_DIR}/" in card and "2.5" in card)
    order = [card.find(needle) for needle in
             (SESSION_PARAMETERS_SECTION_HEADER, ROLES_SECTION_HEADER,
              COMMON_ATTRIBUTES_SECTION_HEADER, OBJECT_MODULES_SECTION_HEADER)]
    check("порядок разделов карточки повторяет порядок стадий: S4c → S4d → S4e → S4b",
          all(index >= 0 for index in order) and order == sorted(order),
          f"позиции разделов: {order}")
    child = result.get("child_objects") or {}
    modules = result.get("object_modules") or {}
    session = result.get("session_parameters") or {}
    roles = result.get("roles") or {}
    check("стадия S4c (V48) после встраивания S4e работает",
          session.get("status") in (STATUS_OK, STATUS_NOT_RUN), session.get("error"))
    check("стадия S4d (V49) после встраивания S4e работает",
          roles.get("status") == STATUS_OK, roles.get("error"))
    check("стадия S4 (V46) после встраивания S4e работает",
          child.get("success") is True, child.get("error"))
    check("стадия S4b (V47) после встраивания S4e работает",
          modules.get("success") is True, modules.get("error"))
    check("разделы карточки соседних стадий на месте",
          CHILD_SECTION_HEADER in card and ROLES_SECTION_HEADER in card
          and SESSION_PARAMETERS_SECTION_HEADER in card
          and OBJECT_MODULES_SECTION_HEADER in card)
    counts = table_counts(cur, cfg_uuid)
    if counts[ATTRIBUTES_TABLE]:
        check("метки строк общих реквизитов и модулей одной загрузки совпадают (M2)",
              one(cur, f"SELECT max(changed_at) FROM {ATTRIBUTES_TABLE} WHERE "
                       "configuration_uuid = %s::uuid", [str(cfg_uuid)])
              == one(cur, "SELECT max(changed_at) FROM bsl_modules WHERE "
                          "configuration_uuid = %s::uuid AND parent_type = "
                          "'configuration_objects'", [str(cfg_uuid)]))
    else:
        note(f"{label}: строк вида у этой выгрузки нет (KomMag — замер 2.9), поэтому метка "
             "загрузки вида не сравнивается: сравнение NULL с NULL не было бы проверкой")
    check("конвейер не оставил применений вне CURRENT-ревизии реквизита (Q2)",
          one(cur, "SELECT count(*) FROM common_attribute_targets t LEFT JOIN "
                   "v_current_common_attributes ca ON ca.id = t.common_attribute_id "
                   "WHERE t.configuration_uuid = %s::uuid AND ca.id IS NULL",
              [str(cfg_uuid)]) == 0)
    note(f"{label}: время конвейера целиком — {pipeline_seconds:.2f} с; стадия S4e той же "
         "выгрузки измерена отдельно выше (сравнение называется, а не подразумевается)")



def main() -> int:
    chosen = tuple(arg for arg in sys.argv[1:] if arg in BASELINE) or DEFAULT_DUMPS
    skip_pipeline = "--no-pipeline" in sys.argv
    print("Проба V50 П4: слой свойств общих реквизитов (стадия S4e) — "
          + ", ".join(chosen))
    print("Загрузчик фиксирует свои транзакции; проба убирает за собой и возвращает "
          "базовое состояние: круг пробы пуст, чужие круги не тронуты (приём пробы П4 "
          "узлов V48 и V49). Раздел карточки и порядок стадий проверяются на тексте, "
          "который печатает оператор.")
    conn = connect()
    try:
        cur = conn.cursor()
        for table in COMMON_ATTRIBUTES_TABLES:
            note(f"базовое состояние {table}: строк по всей базе — "
                 f"{int(one(cur, f'SELECT count(*) FROM {table}') or 0)}")
        # Снимок по конфигурациям: проба обязана вернуть состояние чужих кругов, а не
        # «пустые таблицы» — строки других конфигураций в базе штатны.
        foreign_snapshot = rows_by_configuration_snapshot(cur)
        check_stage_registration()
        min_dir = DUMP_ROOT / "MinCfg"
        min_info = configuration_uuid_from_layout(str(min_dir))
        if "uuid" not in min_info:
            check("MinCfg доступен для отказов и фикстур", False, min_info.get("error"))
            return _summary()
        min_uuid = str(min_info["uuid"])
        check_refusals(cur, min_dir, min_uuid)
        check_removal_with_header(cur)
        tested = [cfg for cfg in (run_dump(cur, name) for name in chosen) if cfg]
        if not tested:
            check("хотя бы одна выгрузка проверена", False, "проверяемых выгрузок нет")
            return _summary()
        restore_baseline(cur, tested, foreign_snapshot)
        # Конвейер проверяется ПОСЛЕ очистки намеренно: он обязан записать строки сам, и
        # после него строки остаются (снять их — значит оставить конфигурацию без только
        # что записанного содержимого). Итог печатается последним всегда.
        if skip_pipeline:
            note("конвейер пропущен флагом --no-pipeline: раздел карточки и порядок "
                 "стадий этим прогоном не проверены — пропуск назван, а не снят молча")
        else:
            for name in chosen:
                info = configuration_uuid_from_layout(str(DUMP_ROOT / name))
                if "uuid" in info:
                    check_pipeline(cur, str(info["uuid"]), DUMP_ROOT / name, BASELINE[name],
                                   name)
        return _summary()
    finally:
        conn.close()


def _summary() -> int:
    """Итог пробы: число проваленных проверок, а не общее «успешно»."""
    print("\n" + "=" * 72)
    print(f"ИТОГ: пройдено {PASSED}, провалено {FAILED}, замечаний {len(NOTES)}")
    if FAILED:
        print("Проваленные проверки перечислены выше строками [FAIL].")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())


