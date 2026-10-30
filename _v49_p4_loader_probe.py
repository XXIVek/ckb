#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П4 узла V49: слой загрузки свойств ролей (стадия S4d).

Предмет проверки — не разбор файлов (его закрыл П2) и не писатель (П3), а слой и его
встраивание в конвейер:

  1. стадия зарегистрирована в `STAGES` между `s4c_session_parameters` и
     `s4b_object_modules` (позиция 2.4 нормативного списка), имеет свой ключ ответа
     `roles` (правило C3) и свой закрытый контракт (C1); круг стадии S4 (V46) не тронут;
  2. отказ слоя называется состоянием контракта, а не исключением и не нулями (C1, C2):
     каталог не читается, uuid разошлись, строки заголовка нет, файл круга не
     разбирается; ни один отказ не меняет круг таблиц в базе;
  3. успех: строки четырёх таблиц записаны, числа ответа совпадают с тем, что легло в
     таблицы, состояния названы, каждая строка права ссылается на CURRENT-ревизию своей
     роли (Q2, вариант A), сверка с индексом состава соответствует независимому сравнению
     каталога и перечня, статистика четырёх таблиц собрана (мера V46);
  4. повтор той же выгрузки идемпотентен: снятие названо четырьмя таблицами, дублей нет,
     `revision_no` не растёт (D8), метка загрузки меняется (новое событие);
  5. конвейер (`load_catalog`, `force=True`) вызывает стадию, карточка содержит раздел
     стадии с состояниями и границей круга, метки строк одной загрузки совпадают (M2),
     соседние стадии S4c и S4b не сломаны, а `delete_configuration` снимает строки вида
     вместе с заголовком — сирот не остаётся;
  6. время стадии называется замером (критерий раздела 7 плана: без `ANALYZE` читатели
     витрин текущего состояния платят минутами, и прогон обязан назвать число).

Проба работает с живой БД. Строки, записанные конвейером, остаются в базе намеренно:
снимать их после конвейера — значит оставить конфигурацию без только что записанного
содержимого (приём пробы П4 узла V48; здесь состав нужен ещё и проверке П6). Разбор
файлов и ограничения схемы проба не проверяет — их закрыли П2 и П3; синтетическая
фикстура заголовка снимается за собой.

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v49_p4_loader_probe.py [MinCfg KomMag]   # базовая линия
    python _v49_p4_loader_probe.py BGU2              # отдельно, замер времени
    python _v49_p4_loader_probe.py BP3               # отдельно, замер времени

Код возврата 0 — расхождений нет. Прогоны, меняющие общее состояние БД, не параллелят.
"""
import sys
import time
import uuid as uuid_module
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_roles as CR  # noqa: E402
import configuration_roles_loader as ROL  # noqa: E402
# Карточка и конвейер — те же точки входа, что читает оператор: проба проверяет слой
# вместе с его встраиванием, а не только вызов функции.
from config_load_router import format_load_result, load_catalog  # noqa: E402
from configuration_load_contract import (  # noqa: E402
    CHILD_SECTION_HEADER,
    CHILD_TABLES,
    OBJECT_MODULES_SECTION_HEADER,
    ROLE_DIR,
    ROLE_META_TAG,
    ROLES_BOUNDARY,
    ROLES_SECTION_HEADER,
    ROLE_RIGHTS_TABLE,
    ROLE_SOURCES_TABLE,
    ROLE_TABLE,
    ROLE_TABLES,
    ROLE_TEMPLATES_TABLE,
    SESSION_PARAMETERS_SECTION_HEADER,
    STAGES,
    STAGE_OBJECT_MODULES,
    STAGE_ROLES,
    STAGE_SESSION_PARAMETERS,
    STATUS_ERROR,
    STATUS_NOT_RUN,
    STATUS_OK,
    format_roles_lines,
    roles_defaults,
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
FIXTURE_DIR = ROOT / "_scratch" / "v49_p4_fixtures"
# Витрина текущего состояния есть только у версионируемых таблиц вида. У `role_rights` своей
# цепи ревизий нет (Q2, вариант A), поэтому её текущим кругом считается сама таблица: строки
# снимаются явным `DELETE` вместе со своей ролью. Разница названа здесь, а не спрятана:
# `current_view` на неверсионируемой таблице бросает исключение.
VIEW_BY_TABLE = {
    table: (current_view(table) if table in CONFIGURATION_VERSIONED_TABLES else table)
    for table in ROLE_TABLES
}

# Эталон П3 (`_v49_p3_rowcounts.txt`) и критерии раздела 7 плана: что обязан записать
# слой на каждой выгрузке. Числа держит проба, а не память ассистента: расхождение с
# ними — это провал прогона, а не расхождение двух пересчётов. `names`/`texts` — имена и
# различные тексты шаблонов: строк таблицы больше, чем текстов, когда один текст объявлен
# под двумя именами (O6), поэтому сравнение «тексты == строки» было бы неправдой.
BASELINE = {
    "MinCfg": {
        "roles": 2, "rights": 362, "templates": 1, "sources": 2,
        "content": {"with_rights": 2}, "resolve": {"exact": 67},
        "cond": {"no_condition": 362}, "decl": {"file_and_index": 2},
        "field": 0,
    },
    "KomMag": {
        "roles": 4, "rights": 2899, "templates": 0, "sources": 4,
        "content": {"with_rights": 4}, "resolve": {"exact": 773, "prefix_only": 353},
        "cond": {"no_condition": 2899}, "decl": {"file_and_index": 4},
        "field": 1,
    },
    "BGU2": {
        "roles": 514, "rights": 60565, "templates": 8, "sources": 514,
        "content": {"with_rights": 512, "empty_content": 2},
        "resolve": {"exact": 18193, "prefix_only": 1053},
        "cond": {"no_condition": 55821, "with_call": 4735, "no_call": 9},
        "decl": {"file_and_index": 514}, "field": 1,
    },
    "BP3": {
        "roles": 682, "rights": 76332, "templates": 9, "sources": 682,
        "content": {"with_rights": 673, "empty_content": 9},
        "resolve": {"exact": 28617, "prefix_only": 3666},
        "cond": {"no_condition": 72162, "with_call": 4152, "no_call": 18},
        "decl": {"file_and_index": 682}, "field": 1,
    },
}
# Что эталон П3 НЕ замерял: имена и значения прав (позиции O1, O5). Эти состояния проба
# сверяет с самой базой — отчёт обязан равняться строкам таблиц, — а не с числом, которого
# в замере нет. Приравнивать отчёт к собственному предположению значило бы проверить
# совпадение пробы с пробой.
UNMEASURED_STATES = ("counts_by_right_name_state", "counts_by_right_value_state")

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
    for table in ROLE_TABLES:
        cur.execute(f"SELECT count(*) FROM {table} WHERE configuration_uuid = %s::uuid",
                    [str(cfg_uuid)])
        out[table] = int(cur.fetchone()[0])
    return out


def view_counts(cur, cfg_uuid):
    """Строки витрины текущего состояния: текущность читается витриной, а не таблицей."""
    out = {}
    for table in ROLE_TABLES:
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

    Пустая таблица (KomMag: шаблонов ограничений 0 — замер 2.7) даёт NULL по агрегатам
    `max(revision_no)` и `max(changed_at)`; сравнение NULL с ревизией или с меткой загрузки
    было бы провалом пробы, а не загрузки. Проверки цепи и метки применяются к непустым
    кругам, а пустой круг называется отдельной строкой — иначе «проверок не было» читается
    как «всё проверено».
    """
    return [table for table in (ROLE_TABLE, ROLE_TEMPLATES_TABLE, ROLE_SOURCES_TABLE)
            if table in CONFIGURATION_VERSIONED_TABLES and counts[table]]


def rows_by_configuration(cur, table):
    """Сколько строк таблицы относится к каждой конфигурации (снимок состояния базы).

    Глобальное «таблица пуста» пробой не было и не является: конвейер пишет реальный
    состав, и строки других конфигураций — штатное состояние базы. Сравнивается именно
    это: круг пробы меняется предсказуемо, чужие круги не меняются вовсе.
    """
    cur.execute(f"SELECT configuration_uuid, count(*) FROM {table} GROUP BY 1")
    return {str(row[0]).lower(): int(row[1]) for row in cur.fetchall()}


def index_role_names(cur, configuration_id):
    """Имена ролей из индекса состава (`Role.<Имя>`) — независимый источник круга."""
    cur.execute(
        "SELECT object_name FROM configuration_objects WHERE configuration_id = %s "
        "AND object_type = %s", [int(configuration_id), CR.INDEX_OBJECT_TYPE])
    return {str(row[0]) for row in cur.fetchall()}


def index_rights_names(cur, configuration_id):
    """Имена записей содержимого (`Role.<Имя>.Rights`) — второй круг того же вида."""
    cur.execute(
        "SELECT object_name FROM configuration_objects WHERE configuration_id = %s "
        "AND child_type = %s", [int(configuration_id), CR.INDEX_RIGHTS_CHILD_TYPE])
    return {str(row[0]) for row in cur.fetchall()}


def disk_role_names(dump_dir):
    """Имена ролей, у которых на диске есть файл метаданных (независимый круг каталога)."""
    files_by_name, _observations = CR.iter_role_files(str(dump_dir))
    return {name for name, entry in files_by_name.items() if entry.get("metadata")}


def disk_rights_names(dump_dir):
    """Имена ролей, у которых на диске есть файл содержимого прав."""
    files_by_name, _observations = CR.iter_role_files(str(dump_dir))
    return {name for name, entry in files_by_name.items() if entry.get("rights")}


def check_stage_registration():
    """Стадия, её ключ, писатели и порядок стоят одним местом (C1, C2, C3, Q5-прецедент)."""
    print("\n=== регистрация стадии и закрытость её контракта ===")
    addresses = [address for address, _title in STAGES]
    check("стадия S4d входит в STAGES", STAGE_ROLES in addresses, " → ".join(addresses))
    check("порядок стадий повторяет нормативный список: S4c → S4d → S4b (2.3, 2.4)",
          addresses.index(STAGE_ROLES) == addresses.index(STAGE_SESSION_PARAMETERS) + 1
          and addresses.index(STAGE_OBJECT_MODULES)
          == addresses.index(STAGE_ROLES) + 1,
          " → ".join(addresses))
    check("круг стадии S4 узла V46 этим узлом не тронут (CHILD_TABLES без таблиц ролей)",
          not (set(CHILD_TABLES) & set(ROLE_TABLES)), str(list(CHILD_TABLES)))
    defaults = roles_defaults()
    check("нулевой контракт читается нулями и статусом not_run (C1, C2)",
          defaults["status"] == STATUS_NOT_RUN and defaults["success"] is False
          and defaults["rows_written"] == 0 and defaults["removed_previous"] == 0
          and defaults["tables"] == list(ROLE_TABLES)
          and defaults["stage"] == STAGE_ROLES)
    check("SUMMARY_KEYS слоя — подмножество ключей контракта: неперечисленный ключ "
          "читается нулём, а не исчезает (C1)",
          set(ROL.SUMMARY_KEYS) <= set(defaults),
          ", ".join(sorted(set(ROL.SUMMARY_KEYS) - set(defaults))))
    check("ключи разбора role_rows/right_rows/template_rows/source_rows в ответ не "
          "попадают (ответ называет числа, а не пересылает строки)",
          not ({"role_rows", "right_rows", "template_rows", "source_rows"} & set(defaults)))
    for table in ROLE_TABLES:
        check(f"писатель строки {table} зарегистрирован общим реестром (правило п.6)",
              table in CONFIGURATION_OBJECT_WRITERS)
    check("три таблицы версионируются своей цепочкой (П1), права — исключение без цепи (Q2)",
          all(table in CONFIGURATION_VERSIONED_TABLES
              for table in (ROLE_TABLE, ROLE_TEMPLATES_TABLE, ROLE_SOURCES_TABLE))
          and ROLE_RIGHTS_TABLE not in CONFIGURATION_VERSIONED_TABLES
          and ROLE_RIGHTS_TABLE in CONFIGURATION_UNVERSIONED_TABLES)
    check("порядок снятия круга начинается с role_rights (каскад не даёт точного счётчика)",
          ROL.REMOVE_ORDER[0] == ROLE_RIGHTS_TABLE
          and set(ROL.REMOVE_ORDER) == set(ROLE_TABLES), str(ROL.REMOVE_ORDER))
    refusal = format_roles_lines({"status": STATUS_ERROR, "success": False,
                                  "error": "проверка формата отказа"})
    check("форматёр отказа называет причину ровно один раз и не падает",
          any("Стадия не удалась" in line for line in refusal)
          and sum(1 for line in refusal if "Стадия не" in line) == 1, str(refusal)[:160])
    check("форматёр отказа называет, чем продолжить (отдельный вход П5 уже обещан)",
          any("load_roles_tool" in line or "load_1c_catalog_tool" in line
              for line in refusal), str(refusal)[:160])
    not_run = format_roles_lines(roles_defaults())
    check("not_run читается отдельно от отказа (C2)",
          any("Стадия не выполнена" in line for line in not_run)
          and not any("Стадия не удалась" in line for line in not_run))


def make_broken_fixture(dump_dir):
    """Копия `Configuration.xml` и файла метаданных роли + битый `Rights.xml`.

    Фикстура нужна одному: отказ разбора файла круга обязан останавливать стадию ДО записи
    (приём V12/V46), а на настоящих выгрузках этого не проверить — там файлов круга нет с
    ошибками (замер 2.1). uuid фикстуры совпадает с uuid выгрузки-источника, поэтому
    заголовок находится, и отказ обязан быть про файл, а не про заголовок.
    """
    import shutil

    fixture = FIXTURE_DIR / "BrokenRoles"
    if fixture.exists():
        shutil.rmtree(fixture)
    (fixture / CR.DIR_NAME).mkdir(parents=True, exist_ok=True)
    shutil.copy(dump_dir / "Configuration.xml", fixture / "Configuration.xml")
    files_by_name, _ = CR.iter_role_files(str(dump_dir))
    name = sorted(n for n, e in files_by_name.items() if e.get("rights"))[0]
    shutil.copy(files_by_name[name]["metadata"]["path"],
                fixture / CR.DIR_NAME / f"{name}.xml")
    content = fixture / CR.DIR_NAME / name / CR.RIGHTS_EXT_DIR
    content.mkdir(parents=True, exist_ok=True)
    (content / CR.RIGHTS_FILE_NAME).write_text("<Rights><object", encoding="utf-8")
    return fixture


def check_refusals(cur, dump_dir, cfg_uuid):
    """Отказы слоя называются состоянием контракта и не меняют круг таблиц (C1, C2)."""
    print("\n=== отказы: каталог, расхождение uuid, отсутствие заголовка, битый файл ===")
    missing_dir = ROL.load_roles(str(DUMP_ROOT / "_нет_такого_каталога"))
    check("каталог, которого нет, отклонён, а не сведён к нулям",
          missing_dir["status"] == STATUS_ERROR and missing_dir["success"] is False,
          str(missing_dir.get("error"))[:160])

    other_uuid = str(uuid_module.uuid4())
    mismatch = ROL.load_roles(str(dump_dir), configuration_uuid=other_uuid)
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
        no_header = ROL.load_roles(str(unloaded))
        check("без строки заголовка слой отказывает и называет точку входа",
              no_header["status"] == STATUS_ERROR
              and "load_1c_catalog_tool" in (no_header.get("error") or ""),
              str(no_header.get("error"))[:200])

    before = table_counts(cur, cfg_uuid)
    fixture = make_broken_fixture(dump_dir)
    broken = ROL.load_roles(str(fixture))
    check("битый файл круга останавливает стадию", broken["status"] == STATUS_ERROR,
          (broken.get("error") or "")[:200])
    check("отказ разбора называет файл и причину",
          CR.RIGHTS_FILE_NAME in (broken.get("error") or ""),
          (broken.get("error") or "")[:200])
    after = table_counts(cur, cfg_uuid)
    check("ни одна строка круга не записана и прежние не сняты (приём V12/V46)",
          after == before, f"до {before}, после {after}")
    check("отказ называет, чем продолжить",
          any("load_roles_tool" in w for w in broken.get("warnings") or []))
    return before


def check_written(cur, cfg_uuid, cfg_id, dump_dir, report, baseline, label):
    """Числа ответа равны строкам таблиц, а строки таблиц равны эталону П3.

    Сверяются три круга, а не один: отчёт ↔ таблицы ↔ эталон замера. Отчёт, равный самому
    себе, ничего не утверждает; таблицы без отчёта не читаются карточкой. Отдельно
    проверяется ссылка каждой строки права на CURRENT-ревизию своей роли (Q2, вариант A):
    своей цепи ревизий у `role_rights` нет, и «цепочка есть у роли» без этой проверки
    означала бы висящие права.
    """
    written = report.get("written_by_table") or {}
    expected = {"roles": baseline["roles"], "role_rights": baseline["rights"],
                "role_restriction_templates": baseline["templates"],
                "role_sources": baseline["sources"]}
    counts = table_counts(cur, cfg_uuid)
    for table in ROLE_TABLES:
        check(f"{label}: ответ назвал число строк {table}",
              int(written.get(table) or 0) == expected[table],
              f"отчёт {written.get(table)}, эталон {expected[table]}")
        check(f"{label}: строки {table} легли в таблицу тем же числом",
              counts[table] == expected[table],
              f"таблица {counts[table]}, эталон {expected[table]}")
    check(f"{label}: rows_written равен сумме четырёх таблиц, а не одному числу",
          int(report.get("rows_written") or 0) == sum(counts.values())
          and int(report.get("roles_written") or 0) == counts[ROLE_TABLE]
          and int(report.get("rights_written") or 0) == counts[ROLE_RIGHTS_TABLE]
          and int(report.get("templates_written") or 0) == counts[ROLE_TEMPLATES_TABLE]
          and int(report.get("sources_written") or 0) == counts[ROLE_SOURCES_TABLE],
          str(counts))
    check(f"{label}: ролей прочитано столько, сколько строк таблицы ролей",
          int(report.get("roles_read") or 0) == counts[ROLE_TABLE],
          f"отчёт {report.get('roles_read')}, таблица {counts[ROLE_TABLE]}")
    check(f"{label}: файлов метаданных и содержимого названо по кругу выгрузки",
          int(report.get("metadata_files_found") or 0) == len(disk_role_names(dump_dir))
          and int(report.get("rights_files_found") or 0) == len(disk_rights_names(dump_dir)),
          f"отчёт {report.get('metadata_files_found')}/{report.get('rights_files_found')}")

    # ── витрины текущего состояния: одна ревизия, сирот нет ─────────────────────────────
    views = view_counts(cur, cfg_uuid)
    for table in ROLE_TABLES:
        check(f"{label}: витрина {VIEW_BY_TABLE[table]} отдаёт тот же круг, что таблица",
              views[table] == counts[table], f"витрина {views[table]}, таблица {counts[table]}")
    checked = versioned_tables_with_rows(counts)
    check(f"{label}: цепь ревизий не разрастается: max(revision_no) = 1 (D8)",
          all(one(cur, f"SELECT max(revision_no) FROM {table} "
                       "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) == FIRST_REVISION
              for table in checked))
    for table in (ROLE_TABLE, ROLE_TEMPLATES_TABLE, ROLE_SOURCES_TABLE):
        if table not in checked:
            note(f"{label}: таблица {table} этого круга пуста — цепь ревизий и метка "
                 "загрузки по ней не проверяются (пустой круг назван, а не скрыт)")
    check(f"{label}: каждая строка права ссылается на CURRENT-ревизию своей роли (Q2)",
          one(cur, "SELECT count(*) FROM role_rights rr JOIN v_current_roles rc "
                   "ON rc.id = rr.role_id WHERE rr.configuration_uuid = %s::uuid",
              [str(cfg_uuid)]) == counts[ROLE_RIGHTS_TABLE],
          f"прав {counts[ROLE_RIGHTS_TABLE]}")
    check(f"{label}: прав, висящих на не-текущей или чужой ревизии роли, нет",
          one(cur, "SELECT count(*) FROM role_rights rr LEFT JOIN v_current_roles rc "
                   "ON rc.id = rr.role_id WHERE rr.configuration_uuid = %s::uuid "
                   "AND rc.id IS NULL", [str(cfg_uuid)]) == 0)
    check(f"{label}: права не перепутали конфигурации (configuration_uuid строки права "
          "совпадает с конфигурацией роли)",
          one(cur, "SELECT count(*) FROM role_rights rr JOIN roles r ON r.id = rr.role_id "
                   "WHERE rr.configuration_uuid IS DISTINCT FROM r.configuration_uuid") == 0)


def check_states(cur, cfg_uuid, report, baseline, counts, label):
    """Состояния: отчёт = строки таблиц = эталон замера П3.

    Каждое состояние проверяется двумя равенствами — отчёта таблице и таблицы эталону. Одно
    только равенство отчёта таблице ничего не утверждает про выгрузку, а одно равенство
    эталону не утверждает про то, что отчёт эти строки назвал.
    """
    by_state = group_counts(cur, f"SELECT content_state, count(*) FROM {ROLE_TABLE} "
                                 "WHERE configuration_uuid = %s::uuid GROUP BY 1",
                            [str(cfg_uuid)])
    check(f"{label}: content_state в таблицах равен эталону (Q6: «прав нет» отдельно от "
          "«файла нет»)", by_state == baseline["content"], f"база {by_state}")
    check(f"{label}: counts_by_content_state отчёта равен строкам таблицы",
          {k: v for k, v in (report.get("counts_by_content_state") or {}).items()
           if v} == by_state, f"отчёт {report.get('counts_by_content_state')}")
    check(f"{label}: rights_count строки роли равен числу её строк права, targets_count — "
          "числу её различных целей",
          one(cur, "SELECT count(*) FROM roles r LEFT JOIN (SELECT role_id, count(*) AS c, "
                   "count(DISTINCT target_full_name) AS t FROM role_rights GROUP BY 1) x "
                   "ON x.role_id = r.id WHERE r.configuration_uuid = %s::uuid AND "
                   "(r.rights_count IS DISTINCT FROM COALESCE(x.c, 0) OR r.targets_count "
                   "IS DISTINCT FROM COALESCE(x.t, 0))", [str(cfg_uuid)]) == 0)
    check(f"{label}: с состоянием with_rights прав больше нуля, с empty_content — ровно ноль",
          one(cur, "SELECT count(*) FROM roles r WHERE r.configuration_uuid = %s::uuid AND "
                   "((r.content_state = 'with_rights' AND r.rights_count = 0) OR "
                   "(r.content_state = 'empty_content' AND r.rights_count > 0))",
              [str(cfg_uuid)]) == 0)

    by_resolve = group_counts(cur, "SELECT target_resolve_state, count(*) FROM ("
                                   "SELECT DISTINCT rr.role_id, rr.target_full_name, "
                                   "rr.target_resolve_state FROM role_rights rr JOIN roles r "
                                   "ON r.id = rr.role_id WHERE r.configuration_uuid = "
                                   "%s::uuid) t GROUP BY 1", [str(cfg_uuid)])
    check(f"{label}: состояния разрешения целей равны эталону (Q3: prefix_only является "
          "ответом)", by_resolve == baseline["resolve"], f"база {by_resolve}")
    check(f"{label}: counts_by_target_resolve_state отчёта равен строкам таблицы",
          {k: v for k, v in (report.get("counts_by_target_resolve_state") or {}).items()
           if v} == by_resolve,
          f"отчёт {report.get('counts_by_target_resolve_state')}")
    check(f"{label}: у одной цели не два состояния разрешения",
          one(cur, "SELECT count(*) FROM (SELECT rr.role_id, rr.target_full_name FROM "
                   "role_rights rr JOIN roles r ON r.id = rr.role_id WHERE "
                   "r.configuration_uuid = %s::uuid GROUP BY 1,2 HAVING count(DISTINCT "
                   "rr.target_resolve_state) > 1) t", [str(cfg_uuid)]) == 0)
    check(f"{label}: targets_total отчёта равен числу различных целей в таблицах",
          int(report.get("targets_total") or 0) == sum(by_resolve.values()),
          f"отчёт {report.get('targets_total')}, база {sum(by_resolve.values())}")
    check(f"{label}: неразрешённая цель остаётся строкой с неполным путём (CHECK П1)",
          one(cur, "SELECT count(*) FROM role_rights rr JOIN roles r ON r.id = rr.role_id "
                   "WHERE r.configuration_uuid = %s::uuid AND rr.target_resolve_state <> "
                   "'exact' AND rr.target_unresolved_path IS NULL", [str(cfg_uuid)]) == 0)

    by_cond = group_counts(cur, "SELECT condition_state, count(*) FROM role_rights rr JOIN "
                                "roles r ON r.id = rr.role_id WHERE r.configuration_uuid = "
                                "%s::uuid GROUP BY 1", [str(cfg_uuid)])
    check(f"{label}: состояния ограничений равны эталону (замер 2.7)",
          by_cond == baseline["cond"], f"база {by_cond}")
    check(f"{label}: counts_by_condition_state отчёта равен строкам таблицы",
          {k: v for k, v in (report.get("counts_by_condition_state") or {}).items()
           if v} == by_cond, f"отчёт {report.get('counts_by_condition_state')}")
    check(f"{label}: с with_call непустой массив имён шаблонов, с no_condition — NULL "
          "(CHECK П1)",
          one(cur, "SELECT count(*) FROM role_rights rr JOIN roles r ON r.id = rr.role_id "
                   "WHERE r.configuration_uuid = %s::uuid AND ((rr.condition_state = "
                   "'with_call' AND COALESCE(array_length(rr.restriction_template_names, 1))"
                   " IS NULL) OR (rr.condition_state = 'no_condition' AND "
                   "rr.restriction_template_names IS NOT NULL))", [str(cfg_uuid)]) == 0)
    fields = int(one(cur, "SELECT count(*) FROM role_rights rr JOIN roles r ON r.id = "
                          "rr.role_id WHERE r.configuration_uuid = %s::uuid AND "
                          "rr.restriction_field_name IS NOT NULL", [str(cfg_uuid)]) or 0)
    check(f"{label}: число заполненных <field> равно эталону (замер 2.7)",
          fields == baseline["field"], f"база {fields}")
    check(f"{label}: отчёт называет то же число <field>",
          int(report.get("restrictions_with_field") or 0) == fields,
          f"отчёт {report.get('restrictions_with_field')}")
    if by_cond.get("with_call"):
        called_own = int(report.get("restrictions_called_own_role") or 0)
        called_other = int(report.get("restrictions_called_other_role") or 0)
        check(f"{label}: два круга вызовов шаблонов посчитаны раздельно и не превышают "
              "with_call (замер 2.7: круги деклараций разные)",
              called_own + called_other <= by_cond["with_call"],
              f"своей {called_own}, чужой {called_other}, всего {by_cond['with_call']}")
        note(f"{label}: вызовов шаблона своей роли {called_own}, чужой роли {called_other} — "
             "раздельный счёт обязателен, потому что круг их деклараций разный")

    by_decl = group_counts(cur, "SELECT declaration_state, count(*) FROM role_sources WHERE "
                                "configuration_uuid = %s::uuid GROUP BY 1", [str(cfg_uuid)])
    check(f"{label}: состояния дескрипторов файлов равны эталону (Q8: запись индекса без "
          "файла — отдельная строка)", by_decl == baseline["decl"], f"база {by_decl}")
    check(f"{label}: counts_by_declaration_state отчёта равен строкам таблицы",
          {k: v for k, v in (report.get("counts_by_declaration_state") or {}).items()
           if v} == by_decl, f"отчёт {report.get('counts_by_declaration_state')}")
    check(f"{label}: дескриптор описывает ровно те имена ролей, что есть в таблице ролей",
          one(cur, "SELECT count(*) FROM role_sources s FULL OUTER JOIN roles r ON "
                   "r.configuration_uuid = s.configuration_uuid AND r.object_name = "
                   "s.object_name WHERE s.configuration_uuid = %s::uuid AND (s.id IS NULL "
                   "OR r.id IS NULL)", [str(cfg_uuid)]) == 0)

    # ── состояния, которых эталон П3 не замерял (O1, O5): сверка только с базой ─────────
    by_name = group_counts(cur, "SELECT right_name_state, count(*) FROM role_rights rr "
                                "JOIN roles r ON r.id = rr.role_id WHERE r.configuration_uuid"
                                " = %s::uuid GROUP BY 1", [str(cfg_uuid)])
    by_value = group_counts(cur, "SELECT right_value_state, count(*) FROM role_rights rr "
                                 "JOIN roles r ON r.id = rr.role_id WHERE r.configuration_uuid"
                                 " = %s::uuid GROUP BY 1", [str(cfg_uuid)])
    for key, actual in zip(UNMEASURED_STATES, (by_name, by_value)):
        reported = {k: v for k, v in (report.get(key) or {}).items() if v}
        check(f"{label}: {key} отчёта равен строкам таблицы (эталон П3 этого не замерял)",
              reported == actual, f"отчёт {reported}, база {actual}")
        check(f"{label}: {key} покрывает все строки права",
              sum(reported.values()) == counts[ROLE_RIGHTS_TABLE],
              f"покрыто {sum(reported.values())} из {counts[ROLE_RIGHTS_TABLE]}")
    if by_value.get("denied"):
        note(f"{label}: DeniedValue=false читается состоянием denied — {by_value['denied']} "
             "строк (O1: отсутствие строки читалось бы как «права нет»)")
    if by_name.get("unknown_name"):
        note(f"{label}: имён прав вне словаря разбора {by_name['unknown_name']} — O5 "
             "(XSD вида отсутствует), имя сохранено текстом и состоянием")

    # ── шаблоны ограничений: строка держится парой (имя, отпечаток) ─────────────────────
    distinct_pairs = int(one(cur, "SELECT count(DISTINCT (name, digest)) FROM "
                                  "role_restriction_templates WHERE configuration_uuid = "
                                  "%s::uuid", [str(cfg_uuid)]) or 0)
    distinct_texts = int(one(cur, "SELECT count(DISTINCT digest) FROM "
                                  "role_restriction_templates WHERE configuration_uuid = "
                                  "%s::uuid", [str(cfg_uuid)]) or 0)
    check(f"{label}: строк таблицы шаблонов ровно столько, различных пар (имя, отпечаток)",
          counts[ROLE_TEMPLATES_TABLE] == distinct_pairs, f"пар {distinct_pairs}")
    check(f"{label}: различных текстов в таблице не больше названного отчётом числа "
          "(O6: один текст под двумя именами даёт две строки)",
          distinct_texts <= int(report.get("template_texts_distinct") or 0)
          and counts[ROLE_TEMPLATES_TABLE] >= distinct_texts,
          f"текстов в таблице {distinct_texts}, отчёт "
          f"{report.get('template_texts_distinct')}, строк {counts[ROLE_TEMPLATES_TABLE]}")
    check(f"{label}: вхождений шаблонов не меньше, чем объявляющих их строк",
          int(report.get("template_occurrences") or 0) >= counts[ROLE_TEMPLATES_TABLE],
          f"вхождений {report.get('template_occurrences')}, строк "
          f"{counts[ROLE_TEMPLATES_TABLE]}")
    check(f"{label}: holders_count каждого шаблона равен длине его списка ролей-носителей",
          one(cur, "SELECT count(*) FROM role_restriction_templates WHERE configuration_uuid"
                   " = %s::uuid AND holders_count <> COALESCE(array_length("
                   "holder_role_names, 1))", [str(cfg_uuid)]) == 0)
    check(f"{label}: condition_length каждого шаблона равен длине его текста",
          one(cur, "SELECT count(*) FROM role_restriction_templates WHERE configuration_uuid"
                   " = %s::uuid AND condition_length <> length(condition_text)",
              [str(cfg_uuid)]) == 0)

    check(f"{label}: статистика четырёх таблиц пересобрана загрузкой (мера V46)",
          int(report.get("statistics_refreshed") or 0) == len(ROLE_TABLES),
          f"обновлено {report.get('statistics_refreshed')}")


def check_reconciliation(cur, cfg_uuid, cfg_id, dump_dir, report, label):
    """Два источника круга против независимого сравнения каталога и перечня.

    Ответ стадии обязан называть `index_only`, `file_only` и `uuid_mismatch` теми же
    множествами, что получены прямым сравнением имён из `configuration_objects` и файлов на
    диске: замер 2.4 даёт пустые множества на всех четырёх выгрузках, и пустые множества
    обязаны быть названы числом, а не подразумеваться (раздел 5 плана).
    """
    index_roles = index_role_names(cur, cfg_id)
    index_rights = index_rights_names(cur, cfg_id)
    disk_roles = disk_role_names(dump_dir)
    disk_rights = disk_rights_names(dump_dir)
    check(f"{label}: индекс состава этого заголовка доступен ответу стадии",
          report.get("index_available") is True)
    check(f"{label}: index_role_records равно числу записей `Role.<Имя>` в перечне",
          int(report.get("index_role_records") or 0) == len(index_roles),
          f"перечень {len(index_roles)}, отчёт {report.get('index_role_records')}")
    check(f"{label}: index_rights_records равно числу записей `Role.<Имя>.Rights` "
          "(Q6: два круга одного вида считаются раздельно)",
          int(report.get("index_rights_records") or 0) == len(index_rights),
          f"перечень {len(index_rights)}, отчёт {report.get('index_rights_records')}")
    check(f"{label}: file_only = файлы без записи перечня (независимое сравнение)",
          set(report.get("file_only") or []) == (disk_roles - index_roles),
          f"отчёт {sorted(report.get('file_only') or [])}")
    check(f"{label}: index_only = записи перечня без файла (независимое сравнение)",
          set(report.get("index_only") or []) == (index_roles - disk_roles),
          f"отчёт {sorted(report.get('index_only') or [])}")
    check(f"{label}: расхождений uuid файла и перечня на базовой линии нет (замер 2.4)",
          report.get("uuid_mismatch") == [], str(report.get("uuid_mismatch"))[:160])
    check(f"{label}: дескрипторов файлов ровно на объединении записей перечня и файлов "
          "каталога (Q8: ни один из двух источников не теряется)",
          counts_now(cur, cfg_uuid)[ROLE_SOURCES_TABLE] == len(index_rights | disk_rights),
          f"объединение {len(index_rights | disk_rights)}, таблица "
          f"{counts_now(cur, cfg_uuid)[ROLE_SOURCES_TABLE]}")
    if index_roles != disk_roles:
        note(f"{label}: круг каталога и перечня различаются — расхождение названо ответом "
             f"стадии (файлов {len(disk_roles)}, записей {len(index_roles)})")
    else:
        check(f"{label}: нули сверки названы ответом, а не подразумеваются (замер 2.4)",
              report.get("file_only") == [] and report.get("index_only") == [])
    if len(index_roles) != len(index_rights):
        note(f"{label}: записей вида {len(index_roles)}, записей содержимого "
             f"{len(index_rights)} — круги различаются, и ответ называет это предупреждением")
    else:
        check(f"{label}: предупреждения о разных кругах индекса нет при равных кругах",
              not any("Role.<Имя>.Rights" in w for w in report.get("warnings") or []))
    check(f"{label}: предупреждение о повторе стадии отдельным входом названо",
          any("load_roles_tool" in w for w in report.get("warnings") or []),
          str([w[:80] for w in report.get("warnings") or []])[:240])


def check_idempotency(cur, cfg_uuid, dump_dir, baseline):
    """Повтор той же выгрузки: снятие названо четырьмя таблицами, дублей нет, D8.

    Идемпотентность держится явным `DELETE` по `configuration_uuid`, а не новой ревизией:
    история состояний принадлежит узлу правки объекта, которого в схеме ещё нет (D8).
    Поэтому повтор обязан назвать снятое ЧЕТЫРЬМИ числами — одно общее число скрыло бы
    момент, когда права перестали соответствовать ролям (M7).
    """
    print("\n=== повтор той же выгрузки: идемпотентность и отсутствие дублей ===")
    counts = table_counts(cur, cfg_uuid)
    checked = versioned_tables_with_rows(counts)
    first_moments = {
        table: one(cur, f"SELECT max(changed_at) FROM {table} WHERE configuration_uuid = "
                        "%s::uuid", [str(cfg_uuid)])
        for table in checked
    }
    first_ids = {table: int(one(cur, f"SELECT max(id) FROM {table} WHERE configuration_uuid "
                                     "= %s::uuid", [str(cfg_uuid)]) or 0)
                 for table in ROLE_TABLES}
    started = time.time()
    again = ROL.load_roles(str(dump_dir))
    elapsed = time.time() - started
    check("повтор успешен", again.get("status") == STATUS_OK, again.get("error"))
    removed = again.get("removed_by_table") or {}
    check("снятие названо четырьмя таблицами, а не одним числом (M7)",
          set(removed) == set(ROLE_TABLES)
          and int(again.get("removed_previous") or 0) == sum(counts.values()),
          str(removed))
    for table in ROLE_TABLES:
        check(f"снято {table} ровно предыдущий круг", int(removed.get(table) or 0) == counts[table],
              f"снято {removed.get(table)}, было {counts[table]}")
    check("предупреждение о снятии прежних строк названо",
          any("Прежние строки" in w for w in again.get("warnings") or []))
    after = table_counts(cur, cfg_uuid)
    check("круг таблиц не вырос: повтор той же выгрузки не создаёт дублей", after == counts,
          f"{counts} → {after}")
    check("история состояний не заводится: max(revision_no) остаётся 1 (D8)",
          all(one(cur, f"SELECT max(revision_no) FROM {table} WHERE configuration_uuid = "
                       "%s::uuid", [str(cfg_uuid)]) == FIRST_REVISION
              for table in checked))
    after_ids = {table: int(one(cur, f"SELECT max(id) FROM {table} WHERE configuration_uuid "
                                     "= %s::uuid", [str(cfg_uuid)]) or 0)
                 for table in ROLE_TABLES}
    check("повтор создаёт новые строки: max(id) каждой непустой таблицы вырос (снятие и "
          "запись, а не UPDATE по тем же строкам)",
          all(after_ids[table] > first_ids[table] for table in ROLE_TABLES if counts[table]),
          f"до {first_ids}, после {after_ids}")
    second_moments = {
        table: one(cur, f"SELECT max(changed_at) FROM {table} WHERE configuration_uuid = "
                        "%s::uuid", [str(cfg_uuid)])
        for table in checked
    }
    check("метка повтора не раньше прежней (точность колонки — секунда, поэтому равенство "
          "быстрых прогонов допустимо; новое событие называют новые id, а не метка)",
          all(second_moments[table] is not None
              and second_moments[table] >= first_moments[table]
              for table in checked),
          str({k: str(v) for k, v in second_moments.items()})[:200])
    check("одна метка changed_at на все версионируемые таблицы этого круга второй "
          "загрузки (M2)",
          bool(checked) and len({str(v) for v in second_moments.values()}) == 1)
    check("у строк права своей метки нет и быть не может: цепь ревизий у таблицы "
          "отсутствует (Q2)",
          one(cur, "SELECT count(*) FROM information_schema.columns WHERE table_name = "
                   "'role_rights' AND column_name IN ('revision_no','changed_at',"
                   "'changed_by')") == 0)
    check("числа второй загрузки равны эталону",
          {t: int((again.get("written_by_table") or {}).get(t) or 0) for t in ROLE_TABLES}
          == {"roles": baseline["roles"], "role_rights": baseline["rights"],
              "role_restriction_templates": baseline["templates"],
              "role_sources": baseline["sources"]},
          str(again.get("written_by_table")))
    note(f"время второй стадии слоя: {elapsed:.2f} с (замер критерия раздела 7 плана; "
         "первая загрузка того же круга замерена в блоке выгрузки)")
    return again


def check_removal_with_header(cur):
    """Снятие заголовка снимает строки вида: сирот в схеме без FK быть не должно (V20.1).

    Фикстура — синтетический заголовок с собственным uuid и по одной строке каждой из
    четырёх таблиц: после `delete_configuration` не должно остаться ни строки заголовка, ни
    строк вида. Настоящие заголовки проба не снимает: их состав проверяют проверки других
    узлов. Фикстура с правами нужна отдельно — на ней же проверяется, что каскад FK не
    подменяет явный `DELETE`: строка права снимается вместе со своей ролью в любом случае.
    """
    print("\n=== снятие заголовка снимает строки вида (дефект сирот) ===")
    fixture_uuid = str(uuid_module.uuid4())
    cur.execute("INSERT INTO configurations (name, uuid) VALUES (%s, %s::uuid) RETURNING id",
                [f"_v49_p4_fixture_{fixture_uuid[:8]}", fixture_uuid])
    fixture_id = int(cur.fetchone()[0])
    cur.execute(
        f"INSERT INTO {ROLE_TABLE} (configuration_uuid, object_uuid, object_name, full_name,"
        " content_state, source_path, revision_no, changed_at, changed_by, is_committed) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, 'empty_content', %s, 1, now(), %s, TRUE) "
        "RETURNING id",
        [fixture_uuid, fixture_uuid, "Фикстура", "Фикстура", "Roles/Фикстура.xml",
         CHANGED_BY_LOAD],
    )
    role_id = int(cur.fetchone()[0])
    cur.execute(
        f"INSERT INTO {ROLE_RIGHTS_TABLE} (role_id, configuration_uuid, target_kind, "
        "target_full_name, target_resolve_state, target_unresolved_path, right_name, "
        "right_name_state, right_value_state, condition_state, target_ordinal, "
        "right_ordinal) VALUES (%s, %s::uuid, 'Catalog', 'Справочник.Фикстура', "
        "'unresolved', 'Справочник.Фикстура', 'Просмотр', 'known', 'granted', "
        "'no_condition', 0, 0)",
        [role_id, fixture_uuid],
    )
    cur.execute(
        f"INSERT INTO {ROLE_TEMPLATES_TABLE} (configuration_uuid, name, name_signature, "
        "digest, condition_text, condition_length, holder_role_names, holders_count, "
        "revision_no, changed_at, changed_by, is_committed) VALUES (%s::uuid, 'Отбор', "
        "'Отбор', %s, 'Истина', 6, ARRAY[%s], 1, 1, now(), %s, TRUE)",
        [fixture_uuid, "0" * 40, "Фикстура", CHANGED_BY_LOAD],
    )
    cur.execute(
        f"INSERT INTO {ROLE_SOURCES_TABLE} (configuration_uuid, object_name, object_uuid, "
        "source_path, declaration_state, revision_no, changed_at, changed_by, is_committed) "
        "VALUES (%s::uuid, 'Фикстура', %s::uuid, 'Roles/Фикстура/Ext/Rights.xml', "
        "'file_not_in_index', 1, now(), %s, TRUE)",
        [fixture_uuid, fixture_uuid, CHANGED_BY_LOAD],
    )
    cur.connection.commit()
    before = table_counts(cur, fixture_uuid)
    check("фикстура: строки всех четырёх таблиц записаны",
          all(before[table] == 1 for table in ROLE_TABLES), str(before))
    removed = delete_configuration(cfg_id=fixture_id)
    deleted = removed.get("children_deleted") or {}
    for table in ROLE_TABLES:
        check(f"delete_configuration назвал снятие строк {table}",
              int(deleted.get(table) or 0) == 1, str(deleted)[:220])
    check("после снятия заголовка строк вида не осталось",
          not any(table_counts(cur, fixture_uuid).values()))
    for table in ROLE_TABLES:
        check(f"сирот нет: каждая строка {table} ссылается на строку заголовка",
              one(cur, f"SELECT count(*) FROM {table} t LEFT JOIN configurations c ON "
                       f"c.uuid = t.configuration_uuid WHERE c.id IS NULL") == 0)


# Граница времени стадии (критерий раздела 7 плана). Порог намеренно грубый: прогон обязан
# назвать ЧИСЛО и поймать квадратичную деградацию (например разрешение целей запросом на
# строку), а не доказать, что стадия быстрее соседней. Замер меньше порога — это число в
# заметке, а не обещание оптимизации.
TIME_LIMIT_S = 120.0

RENDER_MARKERS = (
    "Записано строк по таблицам:",
    "Файлов: метаданных",
    "Состояния содержимого ролей:",
    "состояния разрешения:",
    "Права ",
    "Ограничений ",
    "Шаблоны ограничений:",
    "Дескрипторы файлов содержимого:",
    "Сверка с индексом состава:",
)


def check_text_render(report, label):
    """Текст стадии строится по закрытому контракту и называет записанное (C1, C3).

    Раздел читает человек, машинную часть читает вызывающий; если форматёр молчит о
    состояниях, человек получает «загружено» без ответа о том, что именно сохранено. Отдельно
    проверяется, что текст не расходится с числами ответа: форматёр обязан печатать те же
    суммы, что посчитал слой.
    """
    lines = format_roles_lines(report, indent="   ")
    check(f"{label}: текст стадии непустой и состоит из строк",
          bool(lines) and all(isinstance(line, str) for line in lines), f"строк {len(lines)}")
    missing = [marker for marker in RENDER_MARKERS
               if not any(marker in line for line in lines)]
    check(f"{label}: текст называет каждый раздел стадии (числа без текста не читаются)",
          not missing, "нет разделов: " + ", ".join(missing))
    check(f"{label}: каждая строка текста начинается с отступа вызывающего",
          all(line.startswith("   ") for line in lines))
    total_line = next((line for line in lines
                       if "Записано строк по таблицам:" in line), "")
    check(f"{label}: итог в тексте равен числу rows_written ответа",
          f"всего {int(report.get('rows_written') or 0)}" in total_line, total_line[:200])
    for table in ROLE_TABLES:
        check(f"{label}: текст называет число строк каждой таблицы, а не одно общее",
              f"{table}=" in total_line, total_line[:200])
    check(f"{label}: граница круга названа в тексте успеха (успех ≠ «о ролях всё сохранено»)",
          any(ROLES_BOUNDARY in line for line in lines)
          or any(ROLE_DIR in line for line in lines),
          str(lines[-1])[:200] if lines else "")


def check_contract_shape(report, label):
    """Ответ слоя держит закрытый контракт: ключей нет ни больше, ни меньше (C1, C3).

    Лишний ключ — разрыв контракта для читающего карточку; недостающий читается нулём и
    маскируется под «данных нет». Оба варианта правкой не лечатся, поэтому провал здесь
    дороже, чем кажется.
    """
    defaults = roles_defaults()
    extra = sorted(set(report) - set(defaults))
    missing = sorted(set(defaults) - set(report))
    check(f"{label}: ответ слоя не привносит ключей сверх контракта", not extra,
          "лишние: " + ", ".join(extra))
    check(f"{label}: каждый ключ контракта присутствует в ответе (C1)", not missing,
          "нет: " + ", ".join(missing))
    check(f"{label}: ключ стадии назван тем же адресом, что и в STAGES",
          report.get("stage") == STAGE_ROLES, str(report.get("stage")))
    check(f"{label}: таблицы ответа — четыре таблицы вида, порядок снятия сохранён",
          report.get("tables") == list(ROLE_TABLES), str(report.get("tables")))


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

    print("--- загрузка №1 (единственный круг — права и их шаблоны) ---")
    started = time.time()
    report = ROL.load_roles(str(dump_dir))
    first_seconds = time.time() - started
    check(f"{name}: загрузка №1 успешна",
          report["status"] == STATUS_OK and report["success"] is True, report.get("error"))
    if report.get("status") != STATUS_OK:
        return None
    check_contract_shape(report, f"{name}: загрузка №1")
    check_text_render(report, f"{name}: загрузка №1")
    check_written(cur, cfg_uuid, cfg_id, dump_dir, report, baseline, f"{name} загрузка №1")
    check_states(cur, cfg_uuid, report, baseline, table_counts(cur, cfg_uuid),
                 f"{name} загрузка №1")
    check_reconciliation(cur, cfg_uuid, cfg_id, dump_dir, report, f"{name} загрузка №1")
    check(f"{name}: время стадии первой загрузки меньше границы замера (раздел 7 плана)",
          first_seconds < TIME_LIMIT_S, f"{first_seconds:.2f} с")
    note(f"{name}: время стадии S4d (загрузка №1) — {first_seconds:.2f} с на "
         f"{baseline['roles']} ролей, {baseline['rights']} прав")

    again = check_idempotency(cur, cfg_uuid, dump_dir, baseline)
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
    return {table: rows_by_configuration(cur, table) for table in ROLE_TABLES}


def restore_baseline(cur, cfg_uuids, foreign_before):
    """Вернуть базовое состояние: проба не оставляет за собой строк после своих прогонов.

    Снятие фиксируется той же транзакцией, что и проверка нулей после него: без `commit`
    соединение пробы откатил бы очистку при закрытии, и база осталась бы с записанными
    строками. Порядок снятия — с `role_rights`: каскад FK по рольной цепи снимал бы права
    молча, и счётчик снятия был бы неправдой (M7).
    """
    print("\n=== очистка за пробой и возврат базового состояния ===")
    for cfg_uuid in cfg_uuids:
        removed = ROL.remove_roles(cur, cfg_uuid)
        note(f"снято строк по {cfg_uuid[:8]}: {removed}")
    cur.connection.commit()
    for cfg_uuid in cfg_uuids:
        after = table_counts(cur, cfg_uuid)
        check(f"после очистки круг четырёх таблиц пуст ({cfg_uuid[:8]})",
              not any(after.values()), str(after))
    tested = {str(item).lower() for item in cfg_uuids}
    for table in ROLE_TABLES:
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
    """Конвейер целиком: стадию S4d вызывает `load_catalog` (force=True по уже загруженному).

    Отдельный слой и стадия — один и тот же код, поэтому проверяется и карточка: раздел
    стадии в тексте есть, порядок разделов повторяет порядок стадий (S4c → S4d → S4b),
    соседние стадии S4 (V46) и S4b (V47) не сломаны, метки строк одной загрузки совпадают
    (M2). Порядок разделов проверяется именно в тексте карточки: порядок стадий в `STAGES`
    ещё не значит, что карточка печатает разделы в этом порядке.
    """
    print(f"\n=== конвейер: стадия S4d внутри load_catalog ({label}) ===")
    started = time.time()
    result = load_catalog(str(dump_dir), force=True)
    pipeline_seconds = time.time() - started
    card = format_load_result(result)
    check("конвейер вернул успех", result.get("success") is True, result.get("error"))
    part = result.get("roles") or {}
    check("конвейер вернул раздел S4d закрытым контрактом стадии (C3)",
          sorted(part) == sorted(roles_defaults()),
          "лишнее: " + ", ".join(sorted(set(part) - set(roles_defaults())))
          + "; нет: " + ", ".join(sorted(set(roles_defaults()) - set(part))))
    check("стадия S4d конвейера успешна", part.get("status") == STATUS_OK, part.get("error"))
    check("числа конвейера равны эталону прямой загрузки",
          {table: int((part.get("written_by_table") or {}).get(table) or 0)
           for table in ROLE_TABLES}
          == {"roles": baseline["roles"], "role_rights": baseline["rights"],
              "role_restriction_templates": baseline["templates"],
              "role_sources": baseline["sources"]}, str(part.get("written_by_table")))
    cfg_id = int(result.get("id") or 0)
    check_written(cur, cfg_uuid, cfg_id, dump_dir, part, baseline, f"конвейер {label}")
    check_states(cur, cfg_uuid, part, baseline, table_counts(cur, cfg_uuid),
                 f"конвейер {label}")
    check_reconciliation(cur, cfg_uuid, cfg_id, dump_dir, part, f"конвейер {label}")

    check("карточка загрузки содержит раздел стадии S4d", ROLES_SECTION_HEADER in card)
    check("карточка называет состояния содержимого, разрешения и дескрипторов",
          "Состояния содержимого ролей:" in card and "состояния разрешения:" in card
          and "Дескрипторы файлов содержимого:" in card)
    check("карточка называет границу круга узла V49", ROLES_BOUNDARY in card)
    check("карточка называет Role среди видов с загруженным содержимым",
          ROLE_META_TAG in card and "V49" in card)
    order = [card.find(needle) for needle in
             (SESSION_PARAMETERS_SECTION_HEADER, ROLES_SECTION_HEADER,
              OBJECT_MODULES_SECTION_HEADER)]
    check("порядок разделов карточки повторяет порядок стадий: S4c → S4d → S4b",
          all(index >= 0 for index in order) and order == sorted(order),
          f"позиции разделов: {order}")
    child = result.get("child_objects") or {}
    modules = result.get("object_modules") or {}
    session = result.get("session_parameters") or {}
    check("стадия S4c (V48) после встраивания S4d работает",
          session.get("status") in (STATUS_OK, STATUS_NOT_RUN), session.get("error"))
    check("стадия S4 (V46) после встраивания S4d работает",
          child.get("success") is True, child.get("error"))
    check("стадия S4b (V47) после встраивания S4d работает",
          modules.get("success") is True, modules.get("error"))
    check("разделы карточки соседних стадий на месте",
          CHILD_SECTION_HEADER in card and OBJECT_MODULES_SECTION_HEADER in card)
    check("метки строк ролей и модулей одной загрузки совпадают (M2)",
          one(cur, f"SELECT max(changed_at) FROM {ROLE_TABLE} WHERE configuration_uuid "
                   "= %s::uuid", [str(cfg_uuid)])
          == one(cur, "SELECT max(changed_at) FROM bsl_modules WHERE configuration_uuid "
                      "= %s::uuid AND parent_type = 'configuration_objects'",
                 [str(cfg_uuid)]))
    check("конвейер не оставил прав вне CURRENT-ревизии роли (Q2)",
          one(cur, "SELECT count(*) FROM role_rights rr LEFT JOIN v_current_roles rc "
                   "ON rc.id = rr.role_id WHERE rr.configuration_uuid = %s::uuid "
                   "AND rc.id IS NULL", [str(cfg_uuid)]) == 0)
    note(f"{label}: время конвейера целиком — {pipeline_seconds:.2f} с; стадия S4d той же "
         "выгрузки измерена отдельно выше (сравнение называется, а не подразумевается)")


def main() -> int:
    chosen = tuple(arg for arg in sys.argv[1:] if arg in BASELINE) or DEFAULT_DUMPS
    skip_pipeline = "--no-pipeline" in sys.argv
    print("Проба V49 П4: слой свойств ролей (стадия S4d) — " + ", ".join(chosen))
    print("Загрузчик фиксирует свои транзакции; проба убирает за собой и возвращает "
          "базовое состояние: круг пробы пуст, чужие круги не тронуты (приём пробы П5 "
          "узла V46, переформулирован узлом V48). Раздел карточки и порядок стадий "
          "проверяются на тексте, который печатает оператор.")
    conn = connect()
    try:
        cur = conn.cursor()
        for table in ROLE_TABLES:
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