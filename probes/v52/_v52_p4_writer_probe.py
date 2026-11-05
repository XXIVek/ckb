#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Шаг П4 узла V52: прогон писателей круга `filter_criteria` в живую схему.

Предмет — путь ЗАПИСИ. Офлайн-разбор П3 (`_v52_p3_parse_probe.py`) отвечал на вопрос
«что мы знаем о выгрузке»; этот отвечает на «знаемое доходит до двух таблиц вида без потерь
и без домыслов». Проверяются обе таблицы узла сразу, потому что круг узла — именно круг
(Q1, вариант A): строка критерия без строк перечня `<Content>` не отвечает на «по каким
полям можно отбирать этот вид метаданных», а строка условия без строки критерия ниоткуда не
берётся — её ключ начинается с числового id конкретной ревизии строки вида (Q2, вариант A).

Отдельные проверки, которых нет в `tools/check_v19_revisions.py`:

  * спецификация каждого из двух писателей совпадает с живой схемой: объявленная колонка
    существует, а каждая NOT NULL-колонка без DEFAULT объявлена писателем (иначе вставка
    упала бы на NULL, и виновата была бы не выгрузка);
  * круг писателей = круг версионных таблиц ПЛЮС именованное исключение
    `CONFIGURATION_UNVERSIONED_TABLES` (`filter_criterion_content`: своей цепи ревизий у неё
    нет — Q2, вариант A). Список исключения общий для узлов V49, V50 и V52, поэтому
    сравнение идёт с ним целиком: лишняя таблица означала бы, что чья-то версионность
    снята молча;
  * круг стадии S4 не тронут регистрацией вида: `FILTER_CRITERIA_TABLES` вычтены из
    `CHILD_TABLES` контракта и названы в `FOREIGN_STAGE_TABLES` (без этой константы
    `_v46_p4_writer_probe.py` падает на `KeyError: 'filter_criteria'`);
  * дети вида пишутся ПИСАТЕЛЯМИ УЗЛА V51 (`ExchangePlanFormsRowWriter`, `FormExtRowWriter`,
    `CommandsRowWriter`) — переиспользование, а не второй писатель той же таблицы (Q3,
    вариант A); проба проверяет, что `TABLE_WRITERS` слоя указывает ровно на эти классы и
    второго описания строки детей в проекте нет;
  * замкнутые словари состояний вида (`STATE_VOCABULARIES` разбора) сверяются с CHECK живой
    схемы по имени колонки — в обеих формах предиката (`col IN (...)` и
    `col = ANY (ARRAY[...])`), потому что домены `*_resolve_state` живут внутри парных
    ограничений, а не отдельным предикатом;
  * словарных доменов у СВОЙСТВ вида (`use_standard_commands`, `type_raw`,
    `list_presentation`, …) в схеме НЕТ — это решение Q7 (вариант A), и его отсутствие
    проверяется как свойство, а не предполагается;
  * каждое состояние из словаря записывается ЧЕРЕЗ ПИСАТЕЛЯ и принимается схемой —
    «словарь совпадает» и «словарь достижим» суть разные факта;
  * каждое нарушение называется ограничением по имени (`filter_criteria_content_count_matches_state`,
    `filter_criteria_unknown_names_match_state`, `filter_criteria_form_ref_value_matches_state`,
    `filter_criteria_type_multiplicity_matches_types`, `filter_criteria_types_is_array`,
    `filter_criteria_configuration_object_revision_key`,
    `filter_criterion_content_resolve_matches_reference`,
    `filter_criterion_content_criterion_ordinal_key`,
    `filter_criterion_content_names_not_blank`, `filter_criteria_names_not_blank`);
  * round-trip: значения возвращаются из таблицы ровно теми, что отдал разбор, по ВСЕМ
    колонкам обеих таблиц и для ВСЕХ строк круга — сравнение идёт по типам спецификации
    писателя, потому что иначе «значение дошло» проверялось бы только для колонок, которые
    кто-то вспомнил;
  * цепочка состояния: ключ строки вида включает конфигурацию — ОДНО И ТО ЖЕ имя вида
    в ДВУХ конфигурациях является двумя строками (замер 1.3: 15 верхних записей индекса
    дают 14 различных uuid, общий `FilterCriterion.СвязанныеДокументы` стоит в BGU2 и BP3,
    а имя `СвязанныеДокументы` встречается в четырёх конфигурациях), повторная ревизия
    того же имени в ТОЙ ЖЕ конфигурации продолжает цепочку и становится текущей, а витрина
    строк условия перестаёт отдавать условия прежней ревизии — при том что сами строки
    остаются в таблице (Q2, вариант A).

Транзакция в конце ОТКАТЫВАЕТСЯ намеренно. Инвариант — тот же, что у проб П3 узлов V48–V50:
пустота таблиц инвариантом не является, поэтому базовое состояние читается ДО записи, а
после отката новым соединением сверяется равенство числа строк — всего и строк этой
конфигурации — по обеим таблицам.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v52_p4_writer_probe.py [MinCfg|KomMag|BGU2|BP3]
Код возврата 0 — расхождений нет. Прогоны, меняющие состояние БД, не параллелятся.
"""

import re
import sys
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

import psycopg2  # noqa: E402

import configuration_filter_criteria as FC  # noqa: E402
from configuration_exchange_plans import (  # noqa: E402
    COMMANDS_TABLE_NAME as EP_COMMANDS_TABLE,
    PARENT_TYPE_CONFIGURATION,
)
from configuration_exchange_plans_loader import (  # noqa: E402
    FORMS_TABLE as EP_FORMS_TABLE,
    FORM_EXT_TABLE as EP_FORM_EXT_TABLE,
)
from configuration_filter_criteria_loader import (  # noqa: E402
    CHILD_TABLES as FC_CHILD_TABLES,
    REMOVE_ORDER as FC_REMOVE_ORDER,
    TABLE_WRITERS as FC_TABLE_WRITERS,
    read_index_records,
)
from configuration_load_contract import (  # noqa: E402
    CHILD_TABLES as S4_CHILD_TABLES,
    FILTER_CRITERIA_TABLES,
    FOREIGN_STAGE_TABLES,
    STAGE_FILTER_CRITERIA,
    STAGES as CONTRACT_STAGES,
)
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from current_revision import (  # noqa: E402
    CHANGED_BY_EDIT, CHANGED_BY_LOAD, CHANGED_BY_RESTORE,
    CONFIGURATION_VERSIONED_TABLES, FIRST_REVISION, REVISION_COLUMNS, current_view,
    stamp_revision_rows,
)
from external_db import connect  # noqa: E402
from external_table_writer import (  # noqa: E402
    CommandsRowWriter, CONFIGURATION_OBJECT_WRITERS,
    CONFIGURATION_UNVERSIONED_TABLES, ExchangePlanFormsRowWriter, FormExtRowWriter,
)

TABLE = FC.TABLE_NAME
CONTENT_TABLE = FC.CONTENT_TABLE_NAME
TABLES = (TABLE, CONTENT_TABLE)
# Круг узла по версионности: свою цепь ведёт строка критерия, у строк перечня своей цепи нет
# (Q2, вариант A) — ключ начинается с `filter_criterion_id`.
NODE_VERSIONED = (TABLE,)
NODE_UNVERSIONED = (CONTENT_TABLE,)
# Полный круг таблиц без своей цепи, каким его задают узлы V49, V50 и V52: строки права
# (V49), строки применения (V50), строки перечня `<Content>` критерия отбора (V52). Список
# общий для всех писателей, поэтому сравнение прогона идёт с ним целиком: лишняя таблица в
# списке означала бы, что чью-то версионность сняли молча, а отсутствие строки условия —
# что её версионность кто-то добавил, не назвав причин.
EXPECTED_UNVERSIONED = ("role_rights", "common_attribute_targets", CONTENT_TABLE)
VIEWS = dict((table, current_view(table)) for table in NODE_VERSIONED)
# Имя витрины строк условия названо явно, а не спросом у `current_view`: своей цепи у таблицы
# нет, и точка доступа отвечает отказом (прецедент `TARGETS_VIEW` узла V50). Текущность
# читается связкой по `filter_criterion_id` (Q2, вариант A).
CONTENT_VIEW = "v_current_" + CONTENT_TABLE

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
ONLY = tuple(arg for arg in sys.argv[1:] if arg in DUMPS) or ("MinCfg", "BGU2")

# Базовая линия круга — числа плана (docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md, разделы 1.1
# и 1.4: 1/1/7/6 объектов вида и 1 219 целей условия, из них 727 в BGU2 и 492 в BP3; в
# MinCfg и KomMag блок `<Content>` пуст). Проба сверяет с ними то, что отдал разбор, и то,
# что легло в таблицу и в витрину: расхождение видно по имени таблицы.
BASELINE_ROWS = {
    "MinCfg": {TABLE: 1, CONTENT_TABLE: 0},
    "KomMag": {TABLE: 1, CONTENT_TABLE: 0},
    "BGU2": {TABLE: 7, CONTENT_TABLE: 727},
    "BP3": {TABLE: 6, CONTENT_TABLE: 492},
}

# Колонки, которых в контракте разбора нет по замыслу: их подставляет вызывающий слой.
LOADER_SUPPLIED = {
    TABLE: set(["configuration_uuid"]),
    CONTENT_TABLE: set(["configuration_uuid", "filter_criterion_id"]),
}

# Связь разбора остаётся колонкой ОСОЗНАННО: `criterion_object_uuid` и `criterion_full_name`
# — указатель на критерий в форме индекса состава, он читается и тогда, когда строка вида
# снята перезагрузкой (прецедент `attribute_full_name` узла V50).
LINK_COLUMNS_OF = {CONTENT_TABLE: ("criterion_object_uuid", "criterion_full_name")}

# Домены состояний, принадлежащие ЦЕПИ СОСТОЯНИЯ, а не виду: их словарь задаёт точка
# доступа `src/current_revision.py`, и сверять его со словарём разбора — значит искать не
# там. Проверка всё равно выполняется: схема обязана разрешать ровно те события, которые
# умеет называть точка доступа.
REVISION_STATE_VALUES = (CHANGED_BY_LOAD, CHANGED_BY_EDIT, CHANGED_BY_RESTORE)

# Две формы домена состояний в CHECK. `col = ANY (ARRAY[...])` — форма миграций V46–V51;
# `col IN (...)` — форма, которой написан DDL узла V52 (замер П1), и внутри неё домены
# `*_resolve_state` лежат в составе парных ограничений, а не отдельным предикатом.
DOMAIN_RES = (
    re.compile(r"([a-z_][a-z0-9_]*)\s*=\s*ANY\s*\(\s*ARRAY\[(.*?)\]\s*\)", re.S),
    re.compile(r"([a-z_][a-z0-9_]*)\s+IN\s*\(([^)]*)\)", re.S),
)
VALUE_RE = re.compile(r"'((?:[^']|'')*)'(?:::[A-Za-z_ ]+)?")

PASSED = 0
FAILED = 0
NOTES = []


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + (((" — " + str(detail)) if detail else "")))
    else:
        FAILED += 1
        print("  [FAIL] " + name + (((" — " + str(detail)) if detail else "")))


def note(text):
    NOTES.append(text)
    print("  [NOTE] " + text)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def fetch_dicts(cur, sql, params=None):
    cur.execute(sql, params or ())
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


# ── статическая часть: круг писателей и переиспользование детей ───────────────────────
def check_registry():
    print("\n=== писатели узла, круг версионности и переиспользование детей ===")
    expected = sorted(set(CONFIGURATION_VERSIONED_TABLES)
                      | set(CONFIGURATION_UNVERSIONED_TABLES))
    check("словарь писателей покрывает круг версионных таблиц плюс именованное исключение",
          sorted(CONFIGURATION_OBJECT_WRITERS) == expected,
          ", ".join(sorted(CONFIGURATION_OBJECT_WRITERS)))
    check("исключение названо и совпадает с полным кругом таблиц без своей цепи "
          "(V49+V50+V52)",
          sorted(CONFIGURATION_UNVERSIONED_TABLES) == sorted(EXPECTED_UNVERSIONED),
          ", ".join(CONFIGURATION_UNVERSIONED_TABLES))
    check("строки перечня `<Content>` узла названы в этом списке, а не обходятся молча "
          "(Q2, A)", CONTENT_TABLE in CONFIGURATION_UNVERSIONED_TABLES,
          ", ".join(CONFIGURATION_UNVERSIONED_TABLES))
    check("строка вида узла стоит в круге версионности (своя цепь ревизий, Q1 A)",
          TABLE in CONFIGURATION_VERSIONED_TABLES, ", ".join(CONFIGURATION_VERSIONED_TABLES))
    for table in TABLES:
        writer = CONFIGURATION_OBJECT_WRITERS.get(table)
        if writer is None:
            check("%s: писатель объявлен" % table, False, "в словаре нет класса")
            continue
        check("%s: TABLE писателя совпадает с ключом словаря" % table,
              writer.TABLE == table, writer.TABLE)
    # Круг стадии S4 не тронут регистрацией вида (прецедент KeyError узла V46).
    check("круг стадии S4 (`CHILD_TABLES`) не включает таблиц вида (правило C3)",
          not (set(FILTER_CRITERIA_TABLES) & set(S4_CHILD_TABLES)),
          ", ".join(S4_CHILD_TABLES))
    check("таблицы вида названы чужим кругом стадии (`FOREIGN_STAGE_TABLES`), а круг S4 "
          "не называет их своим",
          all(table in FOREIGN_STAGE_TABLES for table in FILTER_CRITERIA_TABLES)
          and not (set(FOREIGN_STAGE_TABLES) & set(S4_CHILD_TABLES)),
          "чужих: " + ", ".join(FOREIGN_STAGE_TABLES))
    # Стадия названа контрактом отдельным ключом (правило C3), но в `STAGES` она вносится
    # шагом П5 — это названо комментарием контракта (позиция 2.7 идёт между S4f и S4b).
    # Проверяемое свойство — идентификатор не занимает чужую позицию перечня. Формулировка пробы
    # П4 («стадии нет в `STAGES`») описывала состояние слоя ДО шага П5, поэтому после внесения
    # стадии читалась бы вечным провалом: коллизией называлось собственное внесение узла.
    # Замечено 02.11.2026 при регрессе правки контракта (к самой правке отношения не имеет —
    # `STAGES` правка не трогает), исправлено этим же прогоном: проверяется то, что держится и
    # до внесения, и после — чужим идентификатор не занят, а строк своей стадии не больше одной.
    stage_ids = tuple(stage_id for stage_id, _ in CONTRACT_STAGES)
    foreign_ids = [stage_id for stage_id in stage_ids if stage_id != STAGE_FILTER_CRITERIA]
    check("идентификатор стадии не занят чужой стадией перечня, а строк своей стадии — не больше "
          "одной (до шага П5 стадия отсутствует, после — ровно одна)",
          STAGE_FILTER_CRITERIA not in foreign_ids
          and stage_ids.count(STAGE_FILTER_CRITERIA) <= 1, ", ".join(stage_ids))
    note("стадия `%s` в `STAGES` %s — внесение является шагом П5 того же узла"
         % (STAGE_FILTER_CRITERIA,
            "уже есть" if STAGE_FILTER_CRITERIA in stage_ids else "ЕЩЁ НЕ внесена"))
    # Дети вида — переиспользование писателей V51 (Q3, вариант A): второго описания той же
    # строки в проекте быть не должно.
    check("формы вида пишет писатель узла V51 (второго писателя таблицы нет)",
          FC_TABLE_WRITERS[EP_FORMS_TABLE] is ExchangePlanFormsRowWriter)
    check("описания форм пишет общий `FormExtRowWriter` (своей таблицы у описаний нет)",
          FC_TABLE_WRITERS[EP_FORM_EXT_TABLE] is FormExtRowWriter)
    check("команды вида пишет общий `CommandsRowWriter`",
          FC_TABLE_WRITERS[EP_COMMANDS_TABLE] is CommandsRowWriter)
    check("круг снятия стадии начинается с `form_ext` и заканчивается строками вида (M7)",
          FC_REMOVE_ORDER[0] == EP_FORM_EXT_TABLE and FC_REMOVE_ORDER[-1] == TABLE,
          ", ".join(FC_REMOVE_ORDER))
    check("детьми вида названы формы и команды — реквизитов и макетов у вида нет (замер 1.2)",
          set(FC_CHILD_TABLES) == {EP_FORMS_TABLE, EP_COMMANDS_TABLE},
          ", ".join(FC_CHILD_TABLES))


def schema_columns(cur, table):
    """Колонки живой таблицы: {имя: (тип, is_nullable, default)} — источник для сравнения."""
    cur.execute(
        "SELECT column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position",
        (table,))
    return {row[0]: (row[1], row[2], row[3]) for row in cur.fetchall()}


def check_writer_specs(cur):
    """Спецификация писателя против живой схемы: объявленное существует, обязательное объявлено.

    Обратная половина проверки важнее прямой: NOT NULL-колонка без DEFAULT, которой нет в
    спецификации, даёт отказ вставки с текстом про NULL, и виноватой выглядела бы выгрузка,
    хотя колонку не описал писатель (прецедент проб П3 узлов V48–V51).
    """
    print("\n=== спецификации писателей против живой схемы ===")
    for table in TABLES:
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        schema = schema_columns(cur, table)
        if not schema:
            check("%s: таблица существует в живой схеме" % table, False, "колонок нет")
            continue
        check("%s: таблица существует" % table, True, "колонок: %d" % len(schema))
        unknown = sorted(name for name in writer.COLUMNS if name not in schema)
        check("%s: каждая объявленная колонка существует в схеме" % table, not unknown,
              ", ".join(unknown) if unknown else "колонок писателя: %d" % len(writer.COLUMNS))
        required = sorted(name for name, (_t, nullable, default) in schema.items()
                          if nullable == "NO" and default is None)
        undeclared = sorted(name for name in required if name not in writer.COLUMNS)
        check("%s: каждая NOT NULL-колонка без DEFAULT объявлена писателем" % table,
              not undeclared, ", ".join(undeclared) if undeclared else
              "обязательных колонок: %d" % len(required))
        outside = sorted(name for name in schema
                         if name not in writer.COLUMNS and name != "id")
        note("%s: обязательных без DEFAULT — %d; вне спецификации (их даёт DEFAULT или "
             "последовательность) — %s"
             % (table, len(required), ", ".join(outside) if outside else "нет"))
    # Витрины: текущая ревизия строки вида и текущие строки условия (связка по id, Q2 A).
    cur.execute("SELECT table_name FROM information_schema.views WHERE table_schema = "
                "current_schema() AND table_name = ANY(%s)",
                (list(VIEWS.values()) + [CONTENT_VIEW],))
    got = set(row[0] for row in cur.fetchall())
    for table in NODE_VERSIONED:
        check("%s: витрина текущего состояния существует" % VIEWS[table],
              VIEWS[table] in got)
    check("%s: витрина строк условия существует, хотя имя её не даёт current_view "
          "(связка Q2 A)" % CONTENT_VIEW, CONTENT_VIEW in got)
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                (CONTENT_VIEW,))
    view_columns = set(row[0] for row in cur.fetchall())
    missing = sorted(set(CONFIGURATION_OBJECT_WRITERS[CONTENT_TABLE].COLUMNS) - view_columns)
    check("%s отдаёт все колонки строки условия, включая указатель критерия и порядок"
          % CONTENT_VIEW, not missing,
          ", ".join(missing) if missing else "колонок: %d" % len(view_columns))
    # Колонок ревизии у таблицы условия нет — это и есть исключение (Q2, вариант A).
    content_columns = set(schema_columns(cur, CONTENT_TABLE))
    check("%s: колонок ревизии (`revision_no`, `changed_*`) у таблицы условия нет"
          % CONTENT_TABLE,
          not (set(REVISION_COLUMNS) & content_columns),
          ", ".join(sorted(set(REVISION_COLUMNS) & content_columns)))


def schema_state_domains(cur):
    """Домены состояний из CHECK живой схемы: {таблица: {колонка: [(имя, значения)]}}.

    Значения по одной колонке объединяются из всех ограничений, где она названа: в DDL узла
    V52 домен `*_resolve_state` назван и полным списком (в ветви `parsed` парного
    ограничения), и укороченным (в проверке «ссылка есть только у разрешённого») — сравнение
    по объединению даёт полный домен колонки, а имена ограничений называются ответом, чтобы
    было видно, ГДЕ именно он лежит.
    """
    result = {}
    for table in TABLES:
        cur.execute("SELECT con.conname, pg_get_constraintdef(con.oid) FROM pg_constraint con "
                    "JOIN pg_class cls ON cls.oid = con.conrelid "
                    "WHERE cls.relname = %s AND con.contype = 'c' ORDER BY con.conname",
                    (table,))
        domains = {}
        for conname, definition in cur.fetchall():
            for pattern in DOMAIN_RES:
                for column, body in pattern.findall(definition or ""):
                    values = set(match.group(1).replace("''", "'")
                                 for match in VALUE_RE.finditer(body))
                    if values:
                        domains.setdefault(column, []).append((conname, values))
        result[table] = domains
    return result


def check_state_vocabularies(cur):
    """Словари состояний вида против CHECK схемы — по имени колонки (шаг П4).

    Две стороны одного расхождения: состояние в CHECK, которого разбор не отдаёт никогда, —
    мёртвая ветка ограничения; состояние в словаре разбора, которого нет в CHECK, — отказ
    загрузки круга. Поэтому сравниваются МНОЖЕСТВА значений, а не наличие слова в тексте.
    """
    print("\n=== словари состояний вида против CHECK живой схемы ===")
    domains = schema_state_domains(cur)
    for column, states in sorted(FC.STATE_VOCABULARIES.items()):
        table = FC.STATE_VOCABULARY_TABLES[column]
        found = domains.get(table, {}).get(column, [])
        if not found:
            check("%s.%s: в схеме есть домен состояний этого столбца" % (table, column),
                  False, "предикатов не найдено")
            continue
        values = set()
        for _conname, part in found:
            values |= part
        names = ", ".join(sorted(set(conname for conname, _ in found)))
        check("%s.%s: словарь разбора и домен CHECK совпадают" % (table, column),
              values == set(states),
              "CHECK: %s; словарь: %s; ограничения: %s"
              % (sorted(values)[:8], sorted(states)[:8], names))
    # Домен события цепи — у схемы, а не у разбора: точка доступа называет три значения.
    for table in NODE_VERSIONED:
        found = domains.get(table, {}).get("changed_by", [])
        values = set()
        for _conname, part in found:
            values |= part
        check("%s: домен `changed_by` схемы совпадает со словарём точки доступа" % table,
              values == set(REVISION_STATE_VALUES), "CHECK: %s" % sorted(values))
    # Словарей значений СВОЙСТВ вида в схеме нет — это решение Q7 (вариант A): незнакомое
    # значение остаётся значением с состоянием `unknown_value` и виновником, а не отказом.
    property_columns = sorted(set(FC.property_columns()) - set(FC.STATE_VOCABULARIES))
    enforced = sorted(column for column in property_columns if column in domains.get(TABLE, {}))
    check("%s: у свойств вида нет словарных доменов CHECK (Q7, вариант A)" % TABLE,
          not enforced, "домены у колонок: %s" % ", ".join(enforced)
          if enforced else "свойств без доменов: %d" % len(property_columns))
    return domains




def index_rows_of(cur, configuration_id):
    """Записи индекса состава из `configuration_objects` — тем же слоем, что и загрузка.

    Источник — строки БД, а не повторный разбор `ConfigDumpInfo.xml` (приём `read_index_records`
    узлов V46, V48–V51): разрешение целей перечня `<Content>` идёт по индексному `object_id` и
    `uuid`, и проба обязана проверять тот же путь, которым идёт стадия. Без индекса цели
    остались бы записями `unresolved` — проба молча сравнивала бы не то состояние.
    """
    info = read_index_records(cur, configuration_id)
    return list(info.get("rows") or []), info


def table_baseline(cur, cfg_uuid):
    """Базовое состояние двух таблиц: {таблица: (всего строк, строк этой конфигурации)}."""
    state = {}
    for table in TABLES:
        state[table] = (int(one(cur, "SELECT count(*) FROM " + table) or 0),
                        int(one(cur, "SELECT count(*) FROM " + table
                                   + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0))
    return state


def check_contract_matches_writer(collected):
    """Контракт разбора и спецификация писателя совпадают в обе стороны.

    Ключ разбора, которого нет в писателе, — потерянный факт: разбор его отдал, а в таблицу он
    не пойдёт, и карточка конфигурации не узнает о нём никогда. Колонка писателя, которой нет у
    разбора, — выдуманное значение: колонка осталась бы NULL, и читатель отличал бы «значения
    нет» от «слоя не спрашивали» только по имени колонки. Поэтому сравниваются МНОЖЕСТВА.
    """
    print("\n=== контракт разбора против спецификации писателя (обе стороны) ===")
    for table, key in ((TABLE, "rows"), (CONTENT_TABLE, "content")):
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        declared = set(writer.COLUMNS) - set(REVISION_COLUMNS) - LOADER_SUPPLIED[table]
        rows = collected.get(key) or []
        if not rows:
            note("%s: строк разбора нет — сравнение контракта с писателем даёт выгрузка, "
                 "где круг есть (MinCfg, BGU2, BP3)" % table)
            continue
        given = set()
        for row in rows:
            given |= {name for name in row if name != "configuration_uuid"}
        dropped = sorted(given - declared)
        check("%s: ни один ключ разбора не теряется перед записью" % table, not dropped,
              ", ".join(dropped) if dropped else "ключей разбора: %d" % len(given))
        invented = sorted(declared - given)
        check("%s: писатель не объявляет колонок, о которых разбор молчит" % table,
              not invented, ", ".join(invented) if invented
              else "колонок спецификации: %d" % len(declared))



def write_all(cur, cfg_uuid, collected):
    """Записать круг той же очерёдностью, что стадия, и вернуть связи для проверок.

    Порядок держится иерархией данных, а не удобством (Q1, вариант A): строка условия ссылается
    на ЧИСЛОВОЙ id конкретной ревизии строки вида, поэтому сначала идут критерии
    (`insert_ids` с `RETURNING id`), затем условия; формы — до описаний, потому что
    `form_ext.form_id` NOT NULL и берётся из `insert_ids` строк форм. Снятие круга предшествует
    вставкам и идёт по `REMOVE_ORDER` (M7): каскад `form_ext_form_id_fkey` не должен снять
    описания молча.
    """
    criterion_rows = list(collected.get("rows") or [])
    content_rows = list(collected.get("content") or [])
    form_rows = list(collected.get("forms") or [])
    form_ext_rows = list(collected.get("form_ext") or [])
    command_rows = list(collected.get("commands") or [])
    for rows in (criterion_rows, content_rows, form_rows, command_rows):
        for row in rows:
            row["configuration_uuid"] = cfg_uuid

    # Один штамп на всё событие (M2): версионируемые таблицы одной загрузки несут одну метку.
    # Строки условия метки не получают — колонок ревизии у них нет (Q2, вариант A).
    moment = None
    for rows in (criterion_rows, form_rows, command_rows):
        moment = stamp_revision_rows(rows, revision_no=FIRST_REVISION,
                                     changed_by=CHANGED_BY_LOAD, changed_at=moment)
    if form_ext_rows:
        moment = stamp_revision_rows(form_ext_rows, revision_no=FIRST_REVISION,
                                     changed_by=CHANGED_BY_LOAD, changed_at=moment)

    parents = sorted({str(row.get("object_uuid")) for row in criterion_rows
                      if row.get("object_uuid")})
    removed = {}
    for table in FC_REMOVE_ORDER:
        if table in (TABLE, CONTENT_TABLE):
            cur.execute("DELETE FROM " + table + " WHERE configuration_uuid = %s",
                        (cfg_uuid,))
        elif table == EP_FORM_EXT_TABLE:
            cur.execute("DELETE FROM " + table + " WHERE parent_type = %s "
                        "AND parent_uuid = ANY(%s::uuid[])",
                        (PARENT_TYPE_CONFIGURATION, parents))
        else:
            cur.execute("DELETE FROM " + table + " WHERE configuration_uuid = %s "
                        "AND parent_type = %s AND parent_uuid = ANY(%s::uuid[])",
                        (cfg_uuid, PARENT_TYPE_CONFIGURATION, parents))
        removed[table] = cur.rowcount

    written = {table: 0 for table in FC_REMOVE_ORDER}
    criterion_ids = (FC_TABLE_WRITERS[TABLE].insert_ids(cur, criterion_rows)
                     if criterion_rows else [])
    written[TABLE] = len(criterion_ids)
    ids_by_key = dict(zip([str(row.get("full_name") or "") for row in criterion_rows],
                          criterion_ids))
    for row in content_rows:
        row["filter_criterion_id"] = ids_by_key[str(row.get("criterion_full_name"))]
    written[CONTENT_TABLE] = (FC_TABLE_WRITERS[CONTENT_TABLE]
                              .insert_many(cur, content_rows) if content_rows else 0)
    form_ids_by_uuid = {}
    if form_rows:
        # Та же граница, что у стадии: `form_ext.form_id` NOT NULL, ссылка держится uuid
        # формы, а не порядком списка; описания вставляются только вместе со строками форм.
        form_ids = FC_TABLE_WRITERS[EP_FORMS_TABLE].insert_ids(cur, form_rows)
        form_ids_by_uuid = {str(row.get("uuid")): record_id
                            for row, record_id in zip(form_rows, form_ids) if record_id}
        without_id = [str(row.get("name") or row.get("form_uuid"))
                      for row in form_ext_rows
                      if form_ids_by_uuid.get(str(row.get("form_uuid"))) is None]
        if without_id:
            raise ValueError("описания форм остались без строки формы: "
                             + ", ".join(without_id[:10]))
        for row in form_ext_rows:
            row["form_id"] = form_ids_by_uuid.get(str(row.get("form_uuid")))
        written[EP_FORMS_TABLE] = len(form_ids_by_uuid)
        written[EP_FORM_EXT_TABLE] = (FC_TABLE_WRITERS[EP_FORM_EXT_TABLE]
                                      .insert_many(cur, form_ext_rows)
                                      if form_ext_rows else 0)
    written[EP_COMMANDS_TABLE] = (FC_TABLE_WRITERS[EP_COMMANDS_TABLE]
                                  .insert_many(cur, command_rows) if command_rows else 0)
    return written, removed, moment, ids_by_key, form_ids_by_uuid



def check_written(cur, cfg_uuid, name, collected, written, moment):
    """Сколько строк дошло до таблиц и витрин (шаг П4): писатель, таблица, витрина — три числа."""
    print("\n--- что записано: писатель, таблица, витрина ---")
    expected = BASELINE_ROWS[name]
    parse_counts = {
        TABLE: len(collected.get("rows") or []),
        CONTENT_TABLE: len(collected.get("content") or []),
        EP_FORMS_TABLE: len(collected.get("forms") or []),
        EP_FORM_EXT_TABLE: len(collected.get("form_ext") or []),
        EP_COMMANDS_TABLE: len(collected.get("commands") or []),
    }
    for table in FC_REMOVE_ORDER:
        check("%s: писатель записал столько же строк, сколько отдал разбор" % table,
              written.get(table) == parse_counts[table],
              "писатель: %s, разбор: %d" % (written.get(table), parse_counts[table]))
    for table in (TABLE, CONTENT_TABLE):
        check("%s: базовая линия плана соблюдена" % table,
              parse_counts[table] == expected[table],
              "разбор: %d, план: %d" % (parse_counts[table], expected[table]))
    views_of = dict((table, VIEWS.get(table, CONTENT_VIEW)) for table in TABLES)
    for table in TABLES:
        stored = int(one(cur, "SELECT count(*) FROM " + table
                            + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
        current = int(one(cur, "SELECT count(*) FROM " + views_of[table]
                             + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
        check("%s: таблица содержит строки этого круга" % table,
              stored == parse_counts[table],
              "в таблице %d, разбора %d" % (stored, parse_counts[table]))
        check("%s: витрина текущего состояния отдаёт весь круг (первая ревизия — текущая)"
              % views_of[table], current == parse_counts[table],
              "в витрине %d, круга %d" % (current, parse_counts[table]))
    for table in (EP_FORMS_TABLE, EP_FORM_EXT_TABLE, EP_COMMANDS_TABLE):
        children = int(one(cur, "SELECT count(*) FROM " + table + " WHERE parent_type = %s "
                           "AND parent_uuid IN (SELECT object_uuid FROM " + TABLE
                           + " WHERE configuration_uuid = %s)",
                           (PARENT_TYPE_CONFIGURATION, cfg_uuid)) or 0)
        check("%s: строки детей этого круга лежат в общей таблице" % table,
              children == parse_counts[table],
              "в таблице %d, разбора %d" % (children, parse_counts[table]))
    check("метка события названа (M2)", bool(moment), str(moment))
    distinct = int(one(cur, "SELECT count(DISTINCT changed_at) FROM " + TABLE
                      + " WHERE configuration_uuid = %s", (cfg_uuid,)) or 0)
    check("все строки вида этой загрузки несут одну метку (M2)", distinct == 1,
          "различных меток: %d" % distinct)
    note("записано: вид %d, условия %d, формы %d, описания %d, команды %d"
         % (written[TABLE], written[CONTENT_TABLE], written[EP_FORMS_TABLE],
            written[EP_FORM_EXT_TABLE], written[EP_COMMANDS_TABLE]))



def check_link_integrity(cur, cfg_uuid, collected):
    """Связи круга: состояние строки вида согласовано с её собственными строками.

    Проверки идут по таблице, а не по списку разбора: именно так виден расход между тем, что
    утверждает строка вида (`content_count`, `form_names`, `command_uuids`, `children_state`), и
    тем, что действительно лежит в таблицах детей. Расход называет себя числом строк, а не
    молчанием: CHECK его не ловит, потому что второй таблицы он не видит.
    """
    print("\n--- связи круга: состояние строки вида против её строк условия и детей ---")
    orphans = int(one(cur, "SELECT count(*) FROM " + CONTENT_TABLE + " cc LEFT JOIN "
                        + TABLE + " fc ON fc.id = cc.filter_criterion_id "
                        "WHERE cc.configuration_uuid = %s AND fc.id IS NULL",
                        (cfg_uuid,)) or 0)
    check("каждая строка условия указывает на строку вида этой конфигурации (Q1, вариант A)",
          orphans == 0, "сирот: %d" % orphans)
    mismatched = int(one(cur, "SELECT count(*) FROM " + CONTENT_TABLE + " cc JOIN " + TABLE
                        + " fc ON fc.id = cc.filter_criterion_id "
                        "WHERE cc.configuration_uuid = %s AND (cc.criterion_object_uuid <> "
                        "fc.object_uuid OR cc.criterion_full_name <> fc.full_name)",
                        (cfg_uuid,)) or 0)
    check("указатель критерия в строке условия совпадает со строкой вида (прецедент V50)",
          mismatched == 0, "расхождений: %d" % mismatched)
    counts_sql = ("(SELECT filter_criterion_id, count(*) AS n FROM " + CONTENT_TABLE
                  + " GROUP BY 1) cnt ON cnt.filter_criterion_id = fc.id")
    bad_count = int(one(cur, "SELECT count(*) FROM " + VIEWS[TABLE] + " fc LEFT JOIN "
                        + counts_sql + " WHERE fc.configuration_uuid = %s AND "
                        "COALESCE(cnt.n, 0) <> fc.content_count", (cfg_uuid,)) or 0)
    check("счётчик `content_count` строки вида равен числу её строк условия (M4)",
          bad_count == 0, "строк с расходимостью: %d" % bad_count)
    bad_state = int(one(cur, "SELECT count(*) FROM " + VIEWS[TABLE] + " fc LEFT JOIN "
                        + counts_sql + " WHERE fc.configuration_uuid = %s AND "
                        "((fc.content_state = 'with_content' AND COALESCE(cnt.n, 0) = 0) OR "
                        "(fc.content_state = 'empty_content' AND COALESCE(cnt.n, 0) > 0))",
                        (cfg_uuid,)) or 0)
    check("состояние `<Content>` согласно собственным строкам условия (M5: пустой блок — "
          "состояние, а не ноль)", bad_state == 0, "расхождений: %d" % bad_state)
    # %s-параметры держатся в тексте запроса, а не подставляются оператором %: значение
    # `PARENT_TYPE_CONFIGURATION` является строкой (`configuration_objects`), и подстановка
    # в текст SQL без кавычек дала бы отказ «column "configuration_objects" does not exist».
    child_join = ("LEFT JOIN forms f ON f.parent_type = %s AND f.parent_uuid = "
                  "fc.object_uuid LEFT JOIN commands c ON c.parent_type = %s AND "
                  "c.parent_uuid = fc.object_uuid")
    child_params = (PARENT_TYPE_CONFIGURATION, PARENT_TYPE_CONFIGURATION, cfg_uuid)
    bad_forms = int(one(cur, "SELECT count(*) FROM (SELECT fc.id, fc.form_names, "
                       "count(f.id) AS nf FROM " + VIEWS[TABLE] + " fc " + child_join
                       + " WHERE fc.configuration_uuid = %s GROUP BY fc.id, fc.form_names) t "
                       "WHERE COALESCE(cardinality(t.form_names), 0) <> t.nf",
                       child_params) or 0)
    check("перечень `form_names` строки вида равен её строкам форм (замер 1.2)",
          bad_forms == 0, "строк с расходимостью: %d" % bad_forms)
    bad_commands = int(one(cur, "SELECT count(*) FROM (SELECT fc.id, fc.command_uuids, "
                           "count(c.id) AS nc FROM " + VIEWS[TABLE] + " fc " + child_join
                           + " WHERE fc.configuration_uuid = %s GROUP BY fc.id, "
                           "fc.command_uuids) t WHERE COALESCE(cardinality(t.command_uuids), "
                           "0) <> t.nc", child_params) or 0)
    check("перечень `command_uuids` строки вида равен её строкам команд",
          bad_commands == 0, "строк с расходимостью: %d" % bad_commands)
    bad_children = int(one(cur, "SELECT count(*) FROM (SELECT fc.id, fc.children_state, "
                           "count(f.id) + count(c.id) AS kids FROM " + VIEWS[TABLE] + " fc "
                           + child_join + " WHERE fc.configuration_uuid = %s "
                           "GROUP BY fc.id, fc.children_state) t WHERE ((t.children_state = "
                           "'with_children' AND t.kids = 0) OR (t.children_state = "
                           "'empty_content' AND t.kids > 0))", child_params) or 0)
    check("состояние детей согласно строкам форм и команд (словарь V51 переиспользуется)",
          bad_children == 0, "расхождений: %d" % bad_children)
    ext_orphans = int(one(cur, "SELECT count(*) FROM " + EP_FORM_EXT_TABLE + " fe LEFT JOIN "
                         "forms f ON f.id = fe.form_id WHERE fe.parent_type = %s AND "
                         "fe.parent_uuid IN (SELECT object_uuid FROM " + TABLE
                         + " WHERE configuration_uuid = %s) AND f.id IS NULL",
                         (PARENT_TYPE_CONFIGURATION, cfg_uuid)) or 0)
    check("описание формы не остаётся без строки формы (`form_ext.form_id` NOT NULL)",
          ext_orphans == 0, "сирот: %d" % ext_orphans)



def expected_value(kind, value):
    """Что должно лежать в таблице по виду спецификации — своей независимой реализацией.

    Сверять себя с `_adapt` писателя бессмысленно: проверка сравнивает контракт разбора с
    содержимым таблицы, а не две копии одного кода. Пустые значения при этом ведут себя как в
    писателе: пустой перечень остаётся NULL (границы K1–K6 узла V43), пустой jsonb — NULL
    (V31), пустая строка — NULL.
    """
    if kind in ("text", "uuid"):
        if value is None:
            return None
        return (str(value).strip() or None)
    if kind == "bool":
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("true", "1"):
            return True
        if text in ("false", "0"):
            return False
        return None
    if kind == "jsonb_array":
        return list(value) if isinstance(value, list) else []
    if kind == "jsonb_object":
        return dict(value) if isinstance(value, dict) else {}
    if kind == "jsonb_nullable":
        if not value:
            return None
        return value if isinstance(value, (dict, list)) else None
    if kind == "int":
        if value is None or value == "":
            return None
        return int(value)
    if kind == "text_array_nullable":
        if value is None or value == "" or value == []:
            return None
        items = [str(item) for item in value if str(item).strip()]
        return items or None
    if kind == "uuid_array_nullable":
        if value is None or value == "" or value == []:
            return None
        items = [str(item).strip().lower() for item in value if str(item).strip()]
        return items or None
    return value


def pg_array_items(value):
    """Элементы массива Postgres из того, что вернуло соединение.

    `text[]` psycopg отдаёт списком, а `uuid[]` — строкой с литералом массива: typecaster'а
    для массива uuid в psycopg2 нет (он есть только для скалярного `uuid`). Сравнение без
    разбора литерала сравнивало бы символы строки, а не элементы перечня, и круговая проверка
    давала бы ложный отказ на колонке `command_uuids` — при том что значение в таблице
    правильное. Разбор делается здесь, а не в писателе: писатель пишет перечень, а читает его
    проба, и именно проба обязана понимать, в каком виде значение дошло.
    """
    if isinstance(value, (list, tuple)):
        return [str(item).strip().strip('"') for item in value]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("{") and text.endswith("}"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"') for item in inner.split(",")]
    return [text]


def stored_value(kind, value):
    """Как то же значение вернёт таблица: `uuid` psycopg отдаёт объектом, сравнение идёт
    строкой в нижнем регистре (прецедент V49); то же касается элементов `uuid[]`, которые
    приходят литералом массива (см. `pg_array_items`)."""
    if kind == "uuid" and value is not None:
        return str(value).lower()
    if kind == "uuid_array_nullable" and value is not None:
        return [item.lower() for item in pg_array_items(value)]
    if kind == "text_array_nullable" and value is not None:
        return pg_array_items(value)
    return value


def row_key(table, row):
    """Ключ, по которому строку разбора ищут в таблице: имя позиции вида для строк вида,
    пара (указатель критерия, порядковый номер) для строк условия — у критерия их несколько, и
    по одному имени они слились бы в одну (прецеденты V49/V50/V51)."""
    if table == TABLE:
        return row["object_name"]
    return (row["criterion_full_name"], row["ordinal"])


def expected_loader_value(column, cfg_uuid, parser_row, criterion_ids):
    """Что подставляет загрузчик, а не разбор: uuid конфигурации и id строки вида."""
    if column == "configuration_uuid":
        return str(cfg_uuid).lower()
    if column == "filter_criterion_id":
        return criterion_ids.get(parser_row["criterion_full_name"])
    raise KeyError("загрузчик подставляет только эти две колонки: %s" % column)


def check_round_trip(cur, cfg_uuid, collected, criterion_ids):
    """Круговая проверка содержимого обеих таблиц: каждая колонка писателя сравнивается с
    контрактом разбора.

    Сравнение идёт по колонкам спецификации, а не по ключам строк: именно так видна колонка,
    которую писатель читает, а разбор не отдаёт (она осталась бы NULL и не участвовала бы в
    сравнении по ключам строк).
    """
    print("\n--- круговая проверка содержимого (обе таблицы, все колонки) ---")
    compared = 0
    problems = []
    views_of = {TABLE: TABLE, CONTENT_TABLE: CONTENT_TABLE}
    for table, key in ((TABLE, "rows"), (CONTENT_TABLE, "content")):
        writer = CONFIGURATION_OBJECT_WRITERS[table]
        columns = sorted(set(writer.COLUMNS) - set(REVISION_COLUMNS))
        stored = {}
        for row in fetch_dicts(cur, "SELECT %s FROM %s WHERE configuration_uuid = %%s"
                                  % (", ".join(columns), views_of[table]), (cfg_uuid,)):
            stored[row_key(table, row)] = row
        for parser_row in collected.get(key) or []:
            got = stored.get(row_key(table, parser_row))
            if got is None:
                problems.append("%s: строки %s нет в таблице"
                                % (table, row_key(table, parser_row)))
                continue
            for column in columns:
                kind = writer.COLUMNS[column]
                if column in LOADER_SUPPLIED[table]:
                    want = expected_loader_value(column, cfg_uuid, parser_row, criterion_ids)
                else:
                    want = expected_value(kind, parser_row.get(column))
                have = stored_value(kind, got[column])
                if have != want:
                    problems.append("%s.%s колонка %s: ожидалось %r, в таблице %r"
                                    % (table, row_key(table, parser_row), column, want, have))
                compared += 1

    check("содержимое круга совпадает с контрактом разбора по всем колонкам писателя",
          not problems, "сравнено значений %d, расхождений %d: %s"
          % (compared, len(problems), "; ".join(problems[:10])))
    print("  сравнение: %s колонок вида, %s колонок условия, значений %d"
          % (len(set(CONFIGURATION_OBJECT_WRITERS[TABLE].COLUMNS) - set(REVISION_COLUMNS)),
             len(set(CONFIGURATION_OBJECT_WRITERS[CONTENT_TABLE].COLUMNS)), compared))



# ── случаи отказа: нарушение называется ограничением по имени ─────────────────────────
def probe_uuid(tag):
    """Устойчивый uuid пробной строки (один и тот же на повторных прогонах)."""
    return str(uuid_module.uuid5(uuid_module.UUID(int=0), "v52-p4-" + tag))


def probe_criterion_row(base, cfg_uuid, tag, **overrides):
    """Пробная строка вида: копия реальной с новой личностью и заданными полями.

    Копия, а не составленная с нуля строка: только так видно, что отклоняет ИМЕННО проверяемое
    сочетание полей, а не отсутствие чего-то, о чём прогон забыл подумать.
    """
    name = "_Проба_V52_" + tag
    row = dict(base)
    row.update({
        "configuration_uuid": cfg_uuid,
        "object_name": name,
        "full_name": FC.INDEX_OBJECT_TYPE + FC.INDEX_NAME_SEPARATOR + name,
        "object_uuid": probe_uuid(tag),
        "source_path": "%s/_Проба_V52_%s.xml" % (FC.DIR_NAME, tag),
    })
    row.update(overrides)
    stamp_revision_rows([row], revision_no=FIRST_REVISION, changed_by=CHANGED_BY_LOAD)
    return row


def probe_content_row(base, cfg_uuid, criterion_ids, tag, ordinal=9000, **overrides):
    """Пробная строка условия: копия реальной с другим порядковым номером.

    Номер меняется на заведомо свободный: копия строки условия с её же `ordinal` нарушила бы
    ключ `(filter_criterion_id, ordinal)` раньше проверяемого ограничения, и прогон отчитался бы
    не о том отказе.
    """
    row = dict(base)
    row.update({
        "configuration_uuid": cfg_uuid,
        "filter_criterion_id": criterion_ids.get(row["criterion_full_name"]),
        "ordinal": ordinal,
    })
    row.update(overrides)
    return row


def expect_violation(cur, label, table, row, constraints):
    """Нарушение читается именованным ограничением, а не текстом ошибки (приём V49).

    Имя ограничения psycopg2 отдаёт в `diag`, поэтому сравнивается именно оно: иначе прогон
    принимал бы любой отказ. `constraints` — имя или набор имён: пара значений может нарушать
    два ограничения согласованности, и какой из них отчитывается решает порядок проверки
    ограничений, а не замысел узла.
    """
    allowed = set([constraints]) if isinstance(constraints, str) else set(constraints)
    cur.execute("SAVEPOINT v52_p4_case")
    try:
        CONFIGURATION_OBJECT_WRITERS[table].insert(cur, row)
        check(label, False, "строка принята — ограничение не сработало")
    except psycopg2.Error as exc:
        name = getattr(getattr(exc, "diag", None), "constraint_name", None) \
            or getattr(exc, "constraint_name", None)
        check(label + " — имя из ожидаемого набора", name in allowed,
              "нарушено: " + (name or str(exc).splitlines()[0][:200])
              + "; ожидалось одно из " + ", ".join(sorted(allowed)))
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v52_p4_case")


def expect_not_null(cur, label, table, row, column):
    """Отказ по обязательности колонки читается классом ошибки и именем колонки.

    Имени ограничения у такого отказа нет: `NOT NULL` в DDL живёт атрибутом колонки, а не
    строкой `pg_constraint` (замеры узлов V49/V50). Требовать имени значило бы выдумывать то,
    чего схема не даёт; при этом колонка в сообщении называется, и именно она является
    предметом отказа.
    """
    cur.execute("SAVEPOINT v52_p4_not_null")
    try:
        CONFIGURATION_OBJECT_WRITERS[table].insert(cur, row)
        check(label, False, "строка принята — обязательность колонки не сработала")
    except psycopg2.Error as exc:
        text = str(exc).splitlines()[0]
        ok = isinstance(exc, psycopg2.errors.NotNullViolation) and ('"%s"' % column) in text
        check(label + " — отказ назван колонкой", ok,
              "%s: %s" % (type(exc).__name__, text[:200]))
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v52_p4_not_null")


def expect_update_violation(cur, label, sql, params, constraints):
    """Ограничение схемы проверяется правкой уже записанной строки.

    Часть предикатов писатель не выражает: `text` из пустой строки даёт NULL, а `jsonb_array`
    из не-списка даёт `[]`, и предикаты `*_names_not_blank`, `types_is_array` до таблицы не
    доходят. Тогда ограничение проверяется прямой правкой — но правкой строки круга, а не
    отдельной вставкой, чтобы не собирать заново остальные предикаты строки.
    """
    allowed = set([constraints]) if isinstance(constraints, str) else set(constraints)
    cur.execute("SAVEPOINT v52_p4_update")
    try:
        cur.execute(sql, params)
        check(label, False, "правка принята — ограничение не сработало")
    except psycopg2.Error as exc:
        name = getattr(getattr(exc, "diag", None), "constraint_name", None) \
            or getattr(exc, "constraint_name", None)
        check(label + " — имя из ожидаемого набора", name in allowed,
              "нарушено: " + (name or str(exc).splitlines()[0][:200])
              + "; ожидалось одно из " + ", ".join(sorted(allowed)))
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v52_p4_update")



def check_named_constraints(cur, cfg_uuid, name, collected, criterion_ids):
    """Что отклоняет схема и как она это называет (шаг П4, узел V52)."""
    print("\n--- что отклоняет схема: нарушение называется ограничением ---")
    rows = collected.get("rows") or []
    content_rows = collected.get("content") or []
    if not rows:
        note("%s: строк вида в этой выгрузке нет — случаи отказа строятся на выгрузках, "
             "где круг есть (MinCfg, BGU2, BP3)" % name)
        return
    base = rows[0]
    entry = dict((base.get("types") or [{}])[0])
    second_entry = dict(entry, index=1)

    # Содержимое `<Content>`: состояние и счётчик названы вместе (CHECK согласует их).
    expect_violation(cur, "состояние `with_content` без строк условия отклоняется",
                     TABLE, probe_criterion_row(base, cfg_uuid, "cc_state",
                                               content_state=FC.CONTENT_WITH_CONTENT,
                                               content_count=0),
                     "filter_criteria_content_count_matches_state")
    # Виновник свойств: «всё известно» не держит списка, «неизвестное» называет его.
    expect_violation(cur, "`all_known` со списком неизвестных свойств отклоняется",
                     TABLE, probe_criterion_row(base, cfg_uuid, "un_all",
                                               properties_state=FC.PROPS_ALL_KNOWN,
                                               unknown_property_names=["UnknownTag"]),
                     "filter_criteria_unknown_names_match_state")
    expect_violation(cur, "`unknown_value` без виновника отклоняется",
                     TABLE, probe_criterion_row(base, cfg_uuid, "un_none",
                                               properties_state=FC.PROPS_UNKNOWN_VALUE,
                                               unknown_property_names=None),
                     "filter_criteria_unknown_names_match_state")
    # Ссылка на форму: состояние и значение согласованы (M5).
    expect_violation(cur, "`with_reference` без текста ссылки на форму отклоняется",
                     TABLE, probe_criterion_row(base, cfg_uuid, "form_ref",
                                               default_form_state=FC.FORM_REF_WITH_REFERENCE,
                                               default_form=None),
                     "filter_criteria_form_ref_value_matches_state")
    # Блок `<Type>`: кратность согласно содержимому. Пара значений нарушает два ограничения
    # согласованности сразу — какое из них отчитывается, решает порядок проверки, поэтому
    # ожидается любой из набора (приём V49/V50).
    pair = {"filter_criteria_types_absent_matches_no_block",
            "filter_criteria_type_multiplicity_matches_types"}
    expect_violation(cur, "`single` при пустом перечне типов отклоняется",
                     TABLE, probe_criterion_row(base, cfg_uuid, "tm_empty",
                                               types=[], type_parse_state=FC.TYPE_PARSED,
                                               type_multiplicity=FC.MULT_SINGLE),
                     pair)
    expect_violation(cur, "`absent` при непустом перечне типов отклоняется",
                     TABLE, probe_criterion_row(base, cfg_uuid, "tm_absent",
                                               types=[entry], type_parse_state=FC.TYPE_PARSED,
                                               type_multiplicity=FC.MULT_ABSENT),
                     pair)
    expect_violation(cur, "`single` при двух типах отклоняется",
                     TABLE, probe_criterion_row(base, cfg_uuid, "tm_two",
                                               types=[entry, second_entry],
                                               type_parse_state=FC.TYPE_PARSED,
                                               type_multiplicity=FC.MULT_SINGLE),
                     "filter_criteria_type_multiplicity_matches_types")

    # Что писатель выразить не может: пустая строка для него — NULL, не-список для jsonb — [].
    # Такие предикаты проверяются правкой записанной строки круга (приём V50).
    stored_id = one(cur, "SELECT id FROM " + TABLE + " WHERE configuration_uuid = %s "
                    "ORDER BY id LIMIT 1", (cfg_uuid,))
    if stored_id:
        expect_update_violation(
            cur, "пустое имя позиции вида отклоняется",
            "UPDATE " + TABLE + " SET object_name = '' WHERE id = %s", (stored_id,),
            "filter_criteria_names_not_blank")
        expect_update_violation(
            cur, "нулевой номер ревизии отклоняется",
            "UPDATE " + TABLE + " SET revision_no = 0 WHERE id = %s", (stored_id,),
            "filter_criteria_revision_no_positive")
        expect_update_violation(
            cur, "метка события без события отклоняется",
            "UPDATE " + TABLE + " SET changed_by = NULL WHERE id = %s", (stored_id,),
            "filter_criteria_changed_pair_check")
        expect_update_violation(
            cur, "не-массив в `types` отклоняется",
            "UPDATE " + TABLE + " SET types = %s::jsonb WHERE id = %s",
            ('"xs:string"', stored_id), "filter_criteria_types_is_array")

    if not content_rows:
        note("%s: строк условия в этой выгрузке нет — случаи отказа таблицы условия строятся "
             "на BGU2/BP3 (замер 1.4: пустой блок `<Content/>` дают MinCfg и KomMag)" % name)
        return
    content_base = content_rows[0]
    expect_violation(cur, "`exact` без ссылки на строку индекса отклоняется",
                     CONTENT_TABLE,
                     probe_content_row(content_base, cfg_uuid, criterion_ids, "exact_none",
                                       target_resolve_state=FC.TARGET_EXACT,
                                       target_object_id=None),
                     "filter_criterion_content_resolve_matches_reference")
    expect_violation(cur, "`unresolved` с разрешённой ссылкой отклоняется",
                     CONTENT_TABLE,
                     probe_content_row(content_base, cfg_uuid, criterion_ids, "unres_ref",
                                       target_resolve_state=FC.TARGET_UNRESOLVED,
                                       target_object_id=content_base.get("target_object_id")
                                       or "Document.Проба"),
                     "filter_criterion_content_resolve_matches_reference")
    expect_violation(cur, "повтор позиции перечня внутри одной ревизии вида отклоняется "
                          "уникальным ключом (Q2, вариант A)",
                     CONTENT_TABLE,
                     probe_content_row(content_base, cfg_uuid, criterion_ids, "dup",
                                       ordinal=content_base["ordinal"]),
                     "filter_criterion_content_criterion_ordinal_key")
    expect_not_null(cur, "строка условия без id строки вида отклоняется (Q1, вариант A)",
                    CONTENT_TABLE,
                    probe_content_row(content_base, cfg_uuid, criterion_ids, "noid",
                                      ordinal=9100, filter_criterion_id=None),
                    "filter_criterion_id")
    stored_content_id = one(cur, "SELECT id FROM " + CONTENT_TABLE
                            + " WHERE configuration_uuid = %s ORDER BY id LIMIT 1", (cfg_uuid,))
    if stored_content_id:
        expect_update_violation(
            cur, "пустое имя критерия в строке условия отклоняется",
            "UPDATE " + CONTENT_TABLE + " SET criterion_full_name = '' WHERE id = %s",
            (stored_content_id,), "filter_criterion_content_names_not_blank")
        expect_update_violation(
            cur, "отрицательная позиция перечня отклоняется",
            "UPDATE " + CONTENT_TABLE + " SET ordinal = -1 WHERE id = %s",
            (stored_content_id,), "filter_criterion_content_ordinal_non_negative")



def check_state_reachability(cur, cfg_uuid, name, collected, criterion_ids):
    """Каждое состояние словаря вида записывается ЧЕРЕЗ ПИСАТЕЛЯ и принимается схемой.

    Сверка словарей с CHECK отвечает на «значения совпадают»; эта проверка отвечает на
    «значения достижимы»: состояние записывается строкой, которую собрал писатель, а не
    литералом из миграции. Иначе «словарь есть в двух местах» не отличалось бы от «словари
    расходятся при загрузке круга». Парные состояния (счётчик содержимого, виновник свойств,
    текст ссылки на форму, содержимое `<Type>`, ссылка цели) задаются вместе с проверяемым —
    иначе отказ приписался бы проверяемому значению, а не отсутствию его пары.
    """
    print("\n--- каждое состояние словаря записывается через писателя ---")
    rows = collected.get("rows") or []
    content_rows = collected.get("content") or []
    if not rows:
        note("%s: круга вида в этой выгрузке нет — состояния таблицы вида через писателя "
             "записываются там, где круг есть (замер 1.1 даёт 1/1/7/6 файлов вида)" % name)
        return
    base = rows[0]
    entry = dict((base.get("types") or [{}])[0])
    second_entry = dict(entry, index=1)
    variants = []

    # Свойства: состояние и перечень виновников названы вместе (CHECK их согласует).
    for state in FC.STATE_VOCABULARIES["properties_state"]:
        variants.append((TABLE, "properties_state=" + state,
                         probe_criterion_row(base, cfg_uuid, "ps_" + state,
                                             properties_state=state,
                                             unknown_property_names=(
                                                 None if state == FC.PROPS_ALL_KNOWN
                                                 else ["Comment"]))))
    # Содержимое `<Content>`: состояние и счётчик (M4, M5).
    for state in FC.STATE_VOCABULARIES["content_state"]:
        variants.append((TABLE, "content_state=" + state,
                         probe_criterion_row(base, cfg_uuid, "cs_" + state,
                                             content_state=state,
                                             content_count=(1 if state == FC.CONTENT_WITH_CONTENT
                                                            else 0))))
    # Дети: состояния различают «детей нет» и «круг снят» — парных колонок у них нет.
    for state in FC.STATE_VOCABULARIES["children_state"]:
        variants.append((TABLE, "children_state=" + state,
                         probe_criterion_row(base, cfg_uuid, "ch_" + state,
                                             children_state=state)))

    # Ссылки на форму: текст держат `with_reference` и `unknown_form`, пустоту — остальные
    # (CHECK `filter_criteria_form_ref_value_matches_state`).
    for column in (FC.DEFAULT_FORM_STATE_COLUMN, FC.AUXILIARY_FORM_STATE_COLUMN):
        for state in FC.STATE_VOCABULARIES[column]:
            holds = state in (FC.FORM_REF_WITH_REFERENCE, FC.FORM_REF_UNKNOWN_FORM)
            variants.append((TABLE, "%s=%s" % (column, state),
                             probe_criterion_row(base, cfg_uuid,
                                                 "%s_%s" % (column, state),
                                                 **{column: state,
                                                    column.replace("_state", ""):
                                                        ("FilterCriterion.Проба.Form.Форма"
                                                         if holds else None)})))
    # Блок `<Type>`: состояние разбора и содержимое `types` — парные (CHECK
    # `types_absent_matches_no_block`, `type_multiplicity_matches_types`).
    for state in FC.STATE_VOCABULARIES["type_parse_state"]:
        absent = state == FC.TYPE_ABSENT
        variants.append((TABLE, "type_parse_state=" + state,
                         probe_criterion_row(base, cfg_uuid, "tps_" + state,
                                             type_parse_state=state,
                                             type_multiplicity=(FC.MULT_ABSENT if absent
                                                                else FC.MULT_SINGLE),
                                             types=[] if absent else [entry],
                                             type_qualifiers=None)))
    for multiplicity in FC.STATE_VOCABULARIES["type_multiplicity"]:
        count = {FC.MULT_ABSENT: 0, FC.MULT_SINGLE: 1}.get(multiplicity, 2)
        variants.append((TABLE, "type_multiplicity=" + multiplicity,
                         probe_criterion_row(base, cfg_uuid, "tm_" + multiplicity,
                                             type_multiplicity=multiplicity,
                                             type_parse_state=(FC.TYPE_ABSENT if not count
                                                               else FC.TYPE_PARSED),
                                             types=[] if not count
                                             else [entry, second_entry][:count],
                                             type_qualifiers=None)))
    # Строки условия: состояние цели согласно её собственной ссылке и остатку пути. Основой
    # берётся разрешённая цель — иначе копия для `exact` осталась бы без ссылки. Порядковые
    # номера берутся из заведомо свободного диапазона, чтобы копия не нарушила ключ вида.
    # Пустой `<Content/>` — состояние выгрузки, а не отсутствие узла: состояния таблицы вида
    # записаны выше и остаются проверенными и на такой выгрузке (замер 1.4).
    if not content_rows:
        note("%s: строк условия в этой выгрузке нет — состояния таблицы условия через "
             "писателя записываются на BGU2/BP3 (пустой блок `<Content/>` дают MinCfg и "
             "KomMag); состояния таблицы вида записаны выше" % name)
    else:
        exact_rows = [row for row in content_rows
                      if row.get("target_resolve_state") == FC.TARGET_EXACT]
        if not exact_rows:
            note("%s: ни одна цель перечня не разрешена индексом состава — состояния `exact` "
                 "и `prefix_only` через писателя записываются на выгрузке с загруженным "
                 "индексом" % name)
        else:
            for offset, resolve in enumerate(FC.STATE_VOCABULARIES["target_resolve_state"]):
                over = {"target_resolve_state": resolve}
                if resolve == FC.TARGET_EXACT:
                    over["target_unresolved_path"] = None
                elif resolve == FC.TARGET_PREFIX_ONLY:
                    over["target_unresolved_path"] = "Attribute.Проба"
                else:
                    over["target_object_id"] = None
                    over["target_object_uuid"] = None
                    over["target_unresolved_path"] = exact_rows[0].get("target_full_name")
                variants.append((CONTENT_TABLE, "target_resolve_state=" + resolve,
                                 probe_content_row(exact_rows[0], cfg_uuid, criterion_ids,
                                                   "trs_" + resolve, ordinal=9200 + offset,
                                                   **over)))

    for table, label, row in variants:
        cur.execute("SAVEPOINT v52_p4_state")
        try:
            CONFIGURATION_OBJECT_WRITERS[table].insert(cur, row)
            check("состояние %s записано писателем и принято схемой" % label, True)
        except psycopg2.Error as exc:
            check("состояние %s записано писателем и принято схемой" % label, False,
                  str(exc).splitlines()[0][:200])
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT v52_p4_state")



def check_chain(cur, cfg_uuid, name, collected, criterion_ids):
    """Цепочка состояния строки вида и граница её ключа; текущность строк условия следует за ней.

    Все вставки группы идут в SAVEPOINT и откатываются: проба не оставляет в транзакции вторых
    ревизий, из-за которых последующие проверки круга считали бы не тот состав.

    Граница ключа названа замером 1.3: имя `СвязанныеДокументы` встречается в четырёх
    конфигурациях, а `FilterCriterion.СвязанныеДокументы` — в BGU2 и BP3 одним и тем же uuid.
    Ключ без границы по конфигурации принял бы их одной строкой, и вопрос «как этот общий
    критерий устроен в другой конфигурации» остался бы без ответа (M1).
    """
    print("\n--- цепочка состояния и граница ключа (Q1, Q2 вариант A) ---")
    rows = collected.get("rows") or []
    content_rows = collected.get("content") or []
    if not rows:
        note("%s: строк вида в этой выгрузке нет — цепочка состояния и граница её ключа "
             "проверяются на выгрузках, где круг есть (MinCfg, BGU2, BP3)" % name)
        return
    cur.execute("SAVEPOINT v52_p4_chain")
    try:
        first = dict(rows[0])
        object_name = first["object_name"]
        criterion_id = criterion_ids[first["full_name"]]

        duplicate = dict(first, object_uuid=probe_uuid("дубль"))
        stamp_revision_rows([duplicate], revision_no=FIRST_REVISION,
                            changed_by=CHANGED_BY_LOAD)
        expect_violation(cur, "повтор той же ревизии отклоняется уникальным индексом "
                              "цепочки", TABLE, duplicate,
                              "filter_criteria_configuration_object_revision_key")

        other_cfg = str(uuid_module.uuid4())
        # То же имя вида в ДРУГОЙ конфигурации — принимается: границей ключа является
        # конфигурация, а не имя и не uuid позиции (замер 1.3).
        other = dict(first, configuration_uuid=other_cfg)
        stamp_revision_rows([other], revision_no=FIRST_REVISION, changed_by=CHANGED_BY_LOAD)
        cur.execute("SAVEPOINT v52_p4_other")
        try:
            other_ids = CONFIGURATION_OBJECT_WRITERS[TABLE].insert_ids(cur, [other])
            other_id = other_ids[0]
            hit = int(one(cur, "SELECT count(*) FROM " + TABLE
                          + " WHERE configuration_uuid = %s AND object_name = %s",
                          (other_cfg, object_name)) or 0)
            check("то же имя позиции вида в ДРУГОЙ конфигурации принимается (граница ключа, "
                  "замер 1.3)", hit == 1 and other_id is not None,
                  "строк другой конфигурации: %d" % hit)
            if other_id and content_rows:
                sample = dict(content_rows[0], configuration_uuid=other_cfg,
                              filter_criterion_id=other_id)
                CONFIGURATION_OBJECT_WRITERS[CONTENT_TABLE].insert(cur, sample)
                cur.execute("DELETE FROM " + TABLE + " WHERE id = %s", (other_id,))
                left = int(one(cur, "SELECT count(*) FROM " + CONTENT_TABLE
                               + " WHERE filter_criterion_id = %s", (other_id,)) or 0)
                check("снятие строки вида снимает её строки условия каскадом (ON DELETE "
                      "CASCADE), своей цепи у них нет (Q2, вариант A)",
                      left == 0, "строк условия осталось: %d" % left)
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT v52_p4_other")

        # Вторая ревизия той же конфигурации продолжает цепочку и становится текущей.
        second = dict(first, object_uuid=probe_uuid("ревизия-2"))
        stamp_revision_rows([second], revision_no=FIRST_REVISION + 1,
                            changed_by=CHANGED_BY_EDIT)
        second_id = CONFIGURATION_OBJECT_WRITERS[TABLE].insert_ids(cur, [second])[0]
        if content_rows:
            second_content = [dict(row, configuration_uuid=cfg_uuid,
                                   filter_criterion_id=second_id,
                                   ordinal=row["ordinal"] + 9300)
                              for row in content_rows[:3]]
            CONFIGURATION_OBJECT_WRITERS[CONTENT_TABLE].insert_many(cur, second_content)
        cur.execute("SELECT revision_no, object_uuid FROM " + VIEWS[TABLE]
                    + " WHERE configuration_uuid = %s AND object_name = %s",
                    (cfg_uuid, object_name))
        got = cur.fetchall()
        check("витрина текущего состояния отдаёт одну строку — вторую ревизию",
              len(got) == 1 and got[0][0] == FIRST_REVISION + 1
              and str(got[0][1]).lower() == str(second["object_uuid"]).lower(), str(got))
        history = int(one(cur, "SELECT count(*) FROM " + TABLE
                            + " WHERE configuration_uuid = %s AND object_name = %s",
                            (cfg_uuid, object_name)) or 0)
        check("прежняя ревизия остаётся в таблице историей", history == 2,
              "строк в таблице: %d" % history)
        if content_rows:
            current_content = int(one(cur, "SELECT count(*) FROM " + CONTENT_VIEW
                                     + " WHERE filter_criterion_id = %s",
                                     (criterion_id,)) or 0)
            old_content = int(one(cur, "SELECT count(*) FROM " + CONTENT_TABLE
                                  + " WHERE filter_criterion_id = %s",
                                  (criterion_id,)) or 0)
            check("витрина строк условия перестаёт отдавать условия прежней ревизии (связка по "
                  "id текущей ревизии, Q2 вариант A)", current_content == 0,
                  "строк в витрине: %d" % current_content)
            check("сами строки условия прежней ревизии остаются в таблице: своей цепи у них "
                  "нет, они снимаются вместе со своей ревизией", old_content > 0,
                  "строк в таблице: %d" % old_content)
        else:
            note("%s: строк условия в этой выгрузке нет — витрина условий и сохранение строк "
                 "прежней ревизии проверяются там, где круг есть (BGU2, BP3; замер 1.4)"
                 % name)
            old_content = 0

        cur.execute("SAVEPOINT v52_p4_undo")
        try:
            cur.execute("DELETE FROM " + TABLE + " WHERE configuration_uuid = %s AND "
                        "object_name = %s AND revision_no = %s",
                        (cfg_uuid, object_name, FIRST_REVISION + 1))
            back = int(one(cur, "SELECT count(*) FROM " + CONTENT_VIEW
                           + " WHERE filter_criterion_id = %s", (criterion_id,)) or 0)
            check("снятие второй ревизии возвращает витрину к первой и её условиям",
                  back == old_content, "строк в витрине: %d, в таблице: %d"
                  % (back, old_content))
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT v52_p4_undo")
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v52_p4_chain")



def run_dump(name):
    dump_dir = DUMP_ROOT / name
    print("\n" + "=" * 78)
    print("ПРЕДМЕТ: " + str(dump_dir))
    print("=" * 78)
    if not dump_dir.is_dir():
        check("%s: каталог выгрузки существует" % name, False, str(dump_dir))
        return
    uuid_info = configuration_uuid_from_layout(str(dump_dir))
    if "uuid" not in uuid_info:
        check("%s: uuid конфигурации прочитан из Configuration.xml" % name, False,
              uuid_info.get("error"))
        return
    cfg_uuid = uuid_info["uuid"]
    check("%s: uuid конфигурации прочитан из Configuration.xml" % name, True, cfg_uuid)

    before = None
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM configurations WHERE uuid = %s", (cfg_uuid,))
        header_row = cur.fetchone()
        if not header_row:
            check("%s: заголовок конфигурации загружен (порог слоя V52)" % name, False,
                  "строки заголовка в `configurations` нет — свойства круга остались бы ни "
                  "на что не указывающими (узел V20.1)")
            return
        configuration_id = int(header_row[0])
        check("%s: заголовок конфигурации загружен" % name, True,
              "id=%d name=%s" % (configuration_id, header_row[1]))
        # Индекс состава читается тем же слоем, что и стадия: разрешение целей `<Content>`
        # идёт по строкам `configuration_objects`, а не по повторному разбору XML.
        index_rows, index_info = index_rows_of(cur, configuration_id)
        check("%s: индекс состава читается из `configuration_objects`" % name,
              bool(index_rows), index_info.get("reason")
              or ("записей %d, вида %d" % (len(index_rows), index_info.get("kind_count", 0))))
        collected = FC.collect_filter_criteria(str(dump_dir), index_rows=index_rows)
        check("%s: файлы вида разбираются без отказов" % name, collected["success"],
              collected["files_failed"][:2] if collected["files_failed"] else 0)
        expected = BASELINE_ROWS[name]
        check("%s: круг вида совпадает с базовой линией плана (%d + %d)"
              % (name, expected[TABLE], expected[CONTENT_TABLE]),
              len(collected.get("rows") or []) == expected[TABLE]
              and len(collected.get("content") or []) == expected[CONTENT_TABLE],
              "критериев %d, условий %d" % (len(collected.get("rows") or []),
                                            len(collected.get("content") or [])))
        check("%s: файлы вида и записи индекса состава совпадают" % name,
              not collected["file_only"] and not collected["index_only"]
              and not collected["uuid_mismatch"],
              "file_only %d, index_only %d, uuid_mismatch %d"
              % (len(collected["file_only"]), len(collected["index_only"]),
                 len(collected["uuid_mismatch"])))
        note("контракт разбора: файлов %d, прочитано %d, критериев %d, условий %d "
             "(различных целей %d, максимум на файл %d), неразрешённых %d, детей %d/%d, "
             "псевдозаписей индекса %d"
             % (collected["files_found"], collected["files_read"],
                len(collected["rows"]), collected.get("targets_total", 0),
                collected.get("targets_distinct", 0), collected.get("max_targets_per_file", 0),
                len(collected.get("unresolved_targets") or []),
                len(collected.get("forms") or []), len(collected.get("commands") or []),
                len(collected.get("index_pseudo_entries") or [])))
        check_contract_matches_writer(collected)

        # Инвариант тот же, что у проб П3 узлов V48–V50: таблицы не пустуют — стадии
        # конвейера и проба П6 пишут реальный состав. Проверяемое свойство не изменилось:
        # проба ничего не меняет в базе. Базовое состояние читается ДО записи, снятие идёт по
        # кругу этой конфигурации, откат обязан вернуть ровно прочитанное до состояние.
        before = table_baseline(cur, cfg_uuid)
        for table in TABLES:
            if before[table][1]:
                note("%s: в таблице уже есть %d строк этой конфигурации — они сняты внутри "
                     "транзакции пробы и вернутся после отката" % (table, before[table][1]))
        written, removed, moment, criterion_ids, _form_ids = write_all(cur, cfg_uuid, collected)
        for table in TABLES:
            check("%s: прежние строки этой конфигурации сняты внутри транзакции" % table,
                  removed.get(table) == before[table][1],
                  "снято %d, ожидалось %d" % (removed.get(table, 0), before[table][1]))
        check_written(cur, cfg_uuid, name, collected, written, moment)
        check_link_integrity(cur, cfg_uuid, collected)
        check_round_trip(cur, cfg_uuid, collected, criterion_ids)
        check_named_constraints(cur, cfg_uuid, name, collected, criterion_ids)
        check_state_reachability(cur, cfg_uuid, name, collected, criterion_ids)
        check_chain(cur, cfg_uuid, name, collected, criterion_ids)
        conn.rollback()
        check("транзакция откатана", True, "строк в базу не попало")
    except psycopg2.Error as exc:
        conn.rollback()
        # Отказ называется запросом, а не только сообщением: без текста SQL проба
        # осталась бы описанием ошибки, а не местом, где она возникла.
        query_text = ""
        if getattr(exc, "query", None):
            query_text = str(exc.query).replace("\n", " ")[:400]
        check("запись круга прошла без ошибки схемы", False,
              str(exc).splitlines()[0][:300] + (" | SQL: " + query_text if query_text else ""))
    finally:
        conn.close()

    if before is None:
        return
    conn_after = connect()
    try:
        after = table_baseline(conn_after.cursor(), cfg_uuid)
        bad = [table for table in TABLES if after[table] != before[table]]
        check("после отката обе таблицы вернулись к базовому состоянию", not bad,
              "; ".join("%s: всего %d (было %d), этой конфигурации %d (было %d)"
                        % (table, after[table][0], before[table][0], after[table][1],
                           before[table][1]) for table in bad) or "состояние совпадает")
    finally:
        conn_after.close()


def main():
    print("ПРОГОН V52 (П4): писатели содержимого критериев отбора")
    print("писатели: FilterCriteriaRowWriter, FilterCriterionContentRowWriter "
          "(src/external_table_writer.py); разбор: src/configuration_filter_criteria.py; "
          "слой записи: src/configuration_filter_criteria_loader.py")
    wanted = ONLY or DUMPS
    check_registry()
    conn = connect()
    try:
        cursor = conn.cursor()
        check_writer_specs(cursor)
        check_state_vocabularies(cursor)
    finally:
        conn.close()
    for name in wanted:
        run_dump(name)
    print("\nИТОГ: пройдено " + str(PASSED) + ", провалено " + str(FAILED)
          + ", заметок " + str(len(NOTES)))
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
