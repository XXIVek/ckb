#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Единая точка доступа к текущему состоянию содержимого выгрузки (узел V19, S1-S5).

Зачем. С узла V19 строки семи таблиц внешнего объекта версионированы: на один `uuid`
приходится цепочка строк с `revision_no` (M1). M5 требует, чтобы «текущее состояние»
обеспечивали сами инструменты, а не договорённость вызывающего. Замер цены узла
(`tools/_v19_read_sites.py`, 18.10.2026) даёт 52 SQL-обращения в семи модулях; править
их по одному — значит оставить 52 шанса пропустить фильтр, а одна пропущенная строка
даёт смешанные ревизии в одном ответе (тот самый дефект, из-за которого отклонён
вариант В-3). Поэтому определение «текущего» живёт в одном месте:

  * в схеме — витрины `v_current_*` (их текст создаёт `src/generate_ddl.py`, шаг 1; для уже
    созданных БД — `migrate_v19_revisions.sql` с тем же текстом, иначе `_cmp_ddl.py`
    зафиксирует расхождение — инвариант 9 норматива);
  * в коде — этот модуль: он отдаёт имена витрин и SQL-фрагменты разрешения детей через
    манифест (S4).

Правило для вызывающего (то же, что у `src/quarantine.py` про фильтр карантина): писать
свой `max(revision_no)` в модуле-вызывателе нельзя. Сторожит `tools/_v19_read_sites.py`:
после реализации V19 `max(...revision_no)` встречается только здесь и в определениях
`v_current_*` из DDL-источника.

Два разных вопроса, которые нельзя смешивать (инвариант 2 норматива):

  1. «какая строка цепочки является текущей для своего uuid» — отвечает `v_current_*`
     (максимальный `revision_no` в пределах `uuid`);
  2. «какие дети относятся к текущему состоянию объекта» — отвечает ТОЛЬКО манифест
     текущей ревизии родителя, `external_report.children_manifest` (M3, M4, A1). Строка
     ребёнка, у которой своя цепочка в порядке, но её нет в манифесте, — историческая
     строка, а не сирота; отдельного признака состояния на строке ребёнка нет и не будет
     (решение A1).

Манифест — jsonb на строке заголовка: uuid реквизитов объекта, табличных частей, форм,
макетов и пути модулей `Ext/` (у модулей uuid в выгрузке нет, граница — `file_path`).
Уже существующие манифесты (M3) — `tabular_sections.column_uuids` (колонки ТЧ) и jsonb
`form_ext.items/events/commands` (состав формы) — дублировать не стали: дети ТЧ
разрешаются через `column_uuids` текущей ревизии ТЧ, состав формы читают по её jsonb.

Канон формата манифеста — SQL-витрина `v_current_object_manifest` (`src/generate_ddl.py`,
зеркало — `migrate_v19_revisions.sql`): она читает ключи `attribute_uuids`,
`tabular_section_uuids`, `form_uuids`, `template_uuids`, `module_paths` и разворачивает их
в колонки с теми же именами. Python обязан выдавать ровно те же ключи и ровно те же
значения: манифест, собранный этим модулем, и манифест, который витрина посчитала бы по
фактическим строкам детей, обязаны совпадать, — иначе «состав текущего состояния» зависит
от того, каким из двух способов его спросили (раскрытие узла — `tools/check_v19_revisions.py`).

Ключа `form_ext` в манифеста нет осознанно: у описания формы нет своей цепи ревизий —
`uq_form_ext_form_id_revision` привязывает его к ревизии строки формы, поэтому текущность
`form_ext` следует из `form_uuids`, а не из отдельного списка. Витрина этот ключ не читает.

Элемент `module_paths` — пара `parent_type|file_path`: у модуля нет своего uuid в выгрузке,
поэтому границей его идентичности служит путь файла (тот же ключ, что у частичного
`uq_bsl_modules_parent_file_revision`). Формат задаёт `MODULE_KEY_SEPARATOR` и шаблон
`MODULE_KEY_EXPR_TPL` (готовое выражение для алиаса — `MODULE_KEY_EXPR` / `module_key_sql()`):
Python (`_module_path`) и SQL собирают один и тот же ключ из этих констант, потому что
манифест сравнивается со строками детей, и расхождение в одном символе читалось бы как
«модуля нет в составе» при исправном манифесте.
"""

from datetime import datetime

VERSIONED_TABLES = (
    "external_report", "attributes", "tabular_sections",
    "forms", "form_ext", "templates", "bsl_modules",
)

# Имя витрины текущего состояния для версионируемой таблицы. Единственный способ получить
# это имя — current_view(); придумывать строку в вызывающем коде нельзя: опечатка в имени
# читается как «нет такой таблицы», а не как пропущенный фильтр ревизий.
CURRENT_VIEWS = {table: "v_current_" + table for table in VERSIONED_TABLES}

# Витрина, разворачивающая манифест текущей ревизии заголовка в строки (объект, вид цели,
# ключ члена). Она же отвечает на вопрос «строк детей, не попавших ни в один манифест
# текущего состояния, = 0» в SQL-сверках.
MANIFEST_VIEW = "v_current_object_manifest"
MANIFEST_COLUMN = "children_manifest"

# Витрина текущего состояния заголовка — единственная точка, с которой начинают счёт дети.
CURRENT_HEADER = "v_current_external_report"

# Колонки элемента манифеста, которые читает `v_current_object_manifest` (канон — SQL, см.
# шапку модуля). Колонки ТЧ здесь нет намеренно: их перечень — `column_uuids` ТЧ (M3).
VIEW_MEMBER_COLUMNS = {
    "Attribute": ("attribute_uuids", "attributes"),
    "TabularSection": ("tabular_section_uuids", "tabular_sections"),
    "Form": ("form_uuids", "forms"),
    "Template": ("template_uuids", "templates"),
    "Module": ("module_paths", "bsl_modules"),
}

# Таблицы, чей состав детей описан манифестом: «сиротой» считается строка этих таблиц,
# отсутствующая в манифесте текущего состояния. У form_ext своей цепи нет — она проверяется
# через форму (см. `_MEMBERSHIP`).
CURRENT_CHILD_TABLES = ("attributes", "tabular_sections", "forms", "templates", "bsl_modules")

# Ключи манифеста — имена, которые читает `v_current_object_manifest` (канон — SQL, см.
# шапку модуля). Словарь видов цели при этом остаётся словарём целей обогащения
# (config_aliases.target_type): разрешение цели (узел E, решение A2) не заводит второго
# словаря. Колонки ТЧ здесь нет намеренно: их перечень — column_uuids ТЧ.
MANIFEST_KEYS = (
    "attribute_uuids", "tabular_section_uuids", "form_uuids",
    "template_uuids", "module_paths",
)

# Ключ манифеста -> (таблица-источник, колонки элемента). У модуля своей цепи по uuid нет
# (uq_bsl_modules_parent_file_revision), поэтому элемент — пара parent_type|file_path,
# ровно как его собирает ARRAY(...) в витрине: parent_type || '|' || file_path.
MANIFEST_MEMBERS = {
    "attribute_uuids": ("attributes", ("uuid",)),
    "tabular_section_uuids": ("tabular_sections", ("uuid",)),
    "form_uuids": ("forms", ("uuid",)),
    "template_uuids": ("templates", ("uuid",)),
    "module_paths": ("bsl_modules", ("parent_type", "file_path")),
}

MEMBER_KINDS = {
    "attribute_uuids": "Attribute",
    "tabular_section_uuids": "TabularSection",
    "form_uuids": "Form",
    "template_uuids": "Template",
    "module_paths": "Module",
}

# Разделитель элемента `module_paths`. Он один на два контура: Python (`_module_path`) и SQL
# (`MODULE_KEY_EXPR_TPL`). Разных разделителей быть не может: манифест сравнивается со
# строками детей, и расхождение в одном символе дало бы «модуля нет в составе» при верном
# пути. Витрина `v_current_object_manifest` элемент не вычисляет — она разворачивает
# сохранённый jsonb, поэтому формат держат эти два места (п. 0.3 migrate_v19_revisions.sql).
MODULE_KEY_SEPARATOR = "|"

# SQL-выражение элемента `module_paths` для строки модуля: ровно тот же алгоритм, что
# `_module_path()` на Python, — пустая часть (parent_type или путь) означает «это не
# элемент», а не пустую строку в перечне. Путь берётся из file_path, module_name — только
# резерв для строк, загруженных до узла V13 (тот же порядок, что в Python).
# Нормализация регистра и обрамляющих пробелов обязательна: манифест пишет Python, а
# `_key_list()` приводит каждый ключ к `strip().lower()` (uuid в БД и так читаются
# строчными). Сохранённый jsonb поэтому строчный; SQL без `LOWER(BTRIM(...))` сравнил бы
# `external_processing|...Ext/ObjectModule.bsl` со строчным элементом манифеста и потерял бы
# модуль из состава при исправном манифесте (замер 18.10.2026: строгий счёт bsl_modules = 0
# при члене манифеста = 1; регрессия — tools/check_v19_revisions.py, группа 3).
_MODULE_PATH_SQL_PART = ("COALESCE(NULLIF({alias}.file_path::text, ''), "
                        "NULLIF({alias}.module_name::text, ''))")
MODULE_KEY_EXPR_TPL = (
    "(CASE WHEN COALESCE({alias}.parent_type::text, '') = '' "
    "OR COALESCE(" + _MODULE_PATH_SQL_PART + ", '') = '' THEN NULL "
    "ELSE LOWER(BTRIM({alias}.parent_type::text || '" + MODULE_KEY_SEPARATOR + "' || "
    + _MODULE_PATH_SQL_PART + ")) END)"
)


def module_key_sql(alias="c"):
    """SQL-выражение идентичности модуля (`parent_type|file_path`) для алиаса запроса.

    Единственный способ собрать это выражение: вызывающий, который пишет
    `m.parent_type || '/' || m.file_path`, получит ключ, которого в манифесте нет, и
    модуль «исчезнет из состава» при исправном манифесте. Та же причина — в регистре:
    ключи манифеста Python сохраняет строчными, поэтому выражение обязано нормализовать
    `LOWER(BTRIM(...))`, а не сопоставлять путь как он лежит в `file_path`. Готовое
    значение для алиаса `c`, которым пользуется `current_child_count_sql`, —
    `MODULE_KEY_EXPR` ниже; оно выведено из этого же шаблона, а не переписано.
    """
    return MODULE_KEY_EXPR_TPL.format(alias=str(alias))


# Выражение для алиаса `c` — его читает `_MEMBERSHIP` (единственный потребитель).
MODULE_KEY_EXPR = module_key_sql()

# Ключ элемента формы в составе описания формы (`form_ext.items`). Его осознанно нет в
# манифесте заголовка (M3: состав формы принадлежит описанию самой формы), но он нужен как
# цель алиасов и зависимостей — формат тот же, что у `config_aliases.target_uuid`
# (`form_item:<uuid формы>:<имя элемента>`, `.clinerules/1c-configurations-enrichment_Rule.md`).
FORM_ITEM_KEY_SEPARATOR = ":"
FORM_ITEM_KEY_TPL = "form_item" + FORM_ITEM_KEY_SEPARATOR + "{form_uuid}" + FORM_ITEM_KEY_SEPARATOR + "{name}"


def form_item_key_sql(form_uuid_alias="c.parent_uuid", name_alias="item ->> 'name'"):
    """SQL-выражение ключа элемента формы для разбора `form_ext.items` (jsonb-массив)."""
    return ("'form_item' || '" + FORM_ITEM_KEY_SEPARATOR + "' || " + str(form_uuid_alias) +
            " || '" + FORM_ITEM_KEY_SEPARATOR + "' || " + str(name_alias))


# Словарь changed_by (M1). Первая загрузка каталога — ревизия FIRST_REVISION, changed_by
# 'load'; 'edit' — правка состояния строками БД (рабочий путь правки), 'restore' — возврат
# состояния из цепочки. NULL означает «событие не записано»: так остаются строки,
# загруженные до V19 (миграция не ставит им время — этого события не было).
CHANGED_BY_LOAD = "load"
CHANGED_BY_EDIT = "edit"
CHANGED_BY_RESTORE = "restore"
CHANGED_BY_VALUES = (CHANGED_BY_LOAD, CHANGED_BY_EDIT, CHANGED_BY_RESTORE)
FIRST_REVISION = 1

# Колонки ревизии, общие для всех версионируемых таблиц. Писатели берут их из своей
# спецификации колонок; отсутствие колонки в спецификации означает «таблица не
# версионируется» (config_*, configurations, configuration_objects — M8 и граница узла).
REVISION_COLUMNS = ("revision_no", "changed_at", "changed_by")


def current_view(table):
    """Имя витрины текущего состояния для версионируемой таблицы.

    Отказ вместо молчаливой подстановки: вызывающий, который просит «текущее» для
    неверсионируемой таблицы, ошибается в модели, а не в имени — и должен увидеть это в
    момент вызова, а не получить пустой запрос.
    """
    name = str(table).strip().lower()
    if name not in CURRENT_VIEWS:
        raise ValueError(
            "Таблица '%s' не версионируется узлом V19; версионируемые таблицы: %s"
            % (table, ", ".join(VERSIONED_TABLES))
        )
    return CURRENT_VIEWS[name]


def revision_defaults(row, changed_at=None):
    """Значения колонок ревизии для строки, где их не заполнили (загрузка = ревизия 1).

    Явно переданное значение сохраняет силу: правка состояния (путь 'edit') обязана
    проставить следующий номер, и молча подменить его единицей — значит потерять ревизию.

    changed_at и changed_by проставляются парой и одним и тем же моментом: CHECK
    `<таблица>_changed_pair_check` отклоняет половину штампа, а у колонки changed_at нет
    DEFAULT в схеме (проверено по src/ddl_external_report.sql: `changed_at TIMESTAMP`),
    поэтому момент события задаёт код. Один datetime на всю загрузку нужен и потому, что
    строка заголовка и все её дети одной ревизии обязаны нести ОДНО время: разные
    метки в родителе и ребёнке читались бы как два разных события об одном составе.
    NULL остаются только там, где события не было — строки, загруженные до V19.
    """
    out = dict(row or {})
    if out.get("revision_no") in (None, ""):
        out["revision_no"] = FIRST_REVISION
    if not out.get("changed_by"):
        out["changed_by"] = CHANGED_BY_LOAD
    if not out.get("changed_at"):
        out["changed_at"] = changed_at or datetime.now()
    return out


def stamp_revision_rows(rows, revision_no=FIRST_REVISION, changed_by=CHANGED_BY_LOAD,
                        changed_at=None):
    """Проставить ревизию и штамп списка строк контракта; вернуть общий момент.

    Нужен загрузчику: заголовок и все его дети одной ревизии пишутся одной транзакцией,
    поэтому штамп у них один. Возвращает использованный changed_at, чтобы вызывающий
    проставил его и строкам, которые создаёт позже (form_ext после forms), тем же
    значением. Пустой список — допустимый исход: состав может быть пустым (Test3).
    """
    moment = changed_at or datetime.now()
    for row in rows or ():
        if row is None:
            continue
        row["revision_no"] = int(revision_no)
        row["changed_by"] = changed_by
        row["changed_at"] = moment
    return moment


def _key_list(values):
    """Отфильтрованный список ключей манифеста (строки, без пустых, порядок — по значению).

    Порядок фиксирован намеренно: манифест попадает в jsonb и в сравнение составов двух
    ревизий (M4 — отличия считаются по присутствию/отсутствию uuid). Один и тот же состав,
    записанный в разном порядке, читался бы как различие, а отличие порядка от различия
    состава из данных не разрешается.
    """
    out = []
    for value in values or ():
        text = str(value or "").strip().lower()
        if text and text not in out:
            out.append(text)
    return sorted(out)


def _row_uuid(row):
    return str((row or {}).get("uuid") or "").strip().lower()


def _tabular_section_column_uuids(ts_row):
    """uuid колонок табличной части из её собственного манифеста (column_uuids)."""
    return {str(item or "").strip().lower()
            for item in ((ts_row or {}).get("column_uuids") or [])
            if str(item or "").strip()}


def _module_path(row):
    """Элемент `module_paths` — формат, зафиксированный контрактом (шапка V19).

    `v_current_object_manifest` разворачивает сохранённый jsonb и не вычисляет пути, поэтому
    формат элемента задаёт договорённость, записанная в `migrate_v19_revisions.sql`
    (п. 0.3): `parent_type|file_path`. Причина ровно та же, что и у цепочки модулей: своей
    цепи по uuid у модуля нет, граница идентичности — `(parent_uuid, file_path, revision_no)`.
    Вид родителя обязателен: один и тот же `Ext/objectmodule.bsl` у отчёта и обработки —
    разные модули, а таблица-заголовок у них общая (узел V22). Путь берётся из file_path,
    module_name — только резерв для строк, загруженных до V13. Пустая часть — не элемент:
    молчаливый `'|'` в перечне читался бы как модуль с неизвестным именем.
    """
    row = row or {}
    parent_type = str(row.get("parent_type") or "").strip()
    path = str(row.get("file_path") or row.get("module_name") or "").strip()
    if not parent_type or not path:
        return ""
    return parent_type + "|" + path


def build_children_manifest(attribute_rows=(), tabular_section_rows=(),
                           form_rows=(), template_rows=(), bsl_rows=()):
    """Собрать манифест состава детей для строки заголовка (M3).

    Ключи и значения — канон `v_current_object_manifest` (MANIFEST_KEYS/MANIFEST_MEMBERS):
    `attribute_uuids`, `tabular_section_uuids`, `form_uuids`, `template_uuids`,
    `module_paths`. Имена отличаются от имён колонок детей намеренно — их задаёт витрина,
    и расхождение Python с ней сделало бы «состав текущего состояния» разным в двух местах.

    Источник — контракты разбора ДО транзакции, а не запрос к БД после вставки: загрузчик
    знает полный состав до первой вставки, и ровно тот же состав он вставит (одна
    транзакция, иначе полный откат). Считать манифест запросом после вставки означало бы
    описать состояние тем, что в него попало, и не заметить молча не вставшую строку.
    Совпадение манифеста и фактических строк проверяет tools/check_v19_revisions.py —
    сравнение с тем, что посчитала бы витрина по уже вставленным детям.

    Реквизиты объекта отличаются от колонок табличных частей: колонки перечислены в
    column_uuids своей ТЧ (это уже манифест, M3), поэтому в перечень родителя попадают
    только те строки attributes, которые ни одна ТЧ своей колонкой не называет.
    """
    column_uuids = set()
    for ts_row in tabular_section_rows or ():
        column_uuids |= _tabular_section_column_uuids(ts_row)

    object_attributes = [
        _row_uuid(row) for row in attribute_rows or ()
        if _row_uuid(row) and _row_uuid(row) not in column_uuids
    ]

    return {
        "attribute_uuids": _key_list(object_attributes),
        "tabular_section_uuids": _key_list(_row_uuid(row) for row in tabular_section_rows or ()),
        "form_uuids": _key_list(_row_uuid(row) for row in form_rows or ()),
        "template_uuids": _key_list(_row_uuid(row) for row in template_rows or ()),
        "module_paths": _key_list(_module_path(row) for row in bsl_rows or ()),
    }


def uuid_literal(value):
    """uuid как SQL-литерал для запросов, идущих через psql без параметров psycopg2.

    Экранирование — одно место на весь код: строковый uuid в SQL без удвоенной кавычки
    читается ошибкой, а повторное replace("'", "''") в каждом вызывающем модуле — это те
    самые «52 решения», против которых направлены S1-S2.
    """
    text = str(value or "").strip()
    if not text:
        return "NULL::uuid"
    return "'" + text.replace("'", "''") + "'::uuid"


def manifest_array_sql(kind, uuid_expr):
    """Скалярное SQL-выражение массива ключей состава ТЕКУЩЕЙ ревизии родителя (M5, S4).

        (SELECT m.attribute_uuids FROM v_current_object_manifest
          WHERE m.object_uuid = <uuid_expr>)

    Форма — массив, а не набор строк, потому что такой же формы элемент отдаёт витрина
    `v_current_object_manifest` (`src/generate_ddl.py`, раздел 7.1; зеркало —
    `migrate_v19_revisions.sql`): она разворачивает jsonb в колонки `attribute_uuids`,
    `tabular_section_uuids`, `form_uuids`, `template_uuids` (uuid[]) и `module_paths`
    (text[]). Придумывать у витрины колонки `member_key`/`member_kind` нельзя: запрос
    падал бы «нет такой колонки» там, где дефект в другом месте.

    uuid_expr — SQL-выражение, дающее uuid ('<uuid>'::uuid из uuid_literal() или
    %(cur_uuid)s::uuid для psycopg2): стиль параметров выбирает запрос вызывающего, а
    смешать %s и %(name)s в одном SQL нельзя (то же правило, что у sql_* фрагментов
    src/quarantine.py).

    Манифеста нет (строки, загруженные до V19) — подзапрос отдаёт NULL-массив, и сравнение
    с ним не подтверждает ни одного ребёнка. Это не «состав пуст», поэтому различает
    `manifest_missing_sql`; вызывать её обязан тот, кто печатает число.
    """
    column = str(kind)
    if column not in MANIFEST_KEYS:
        raise ValueError(
            "Неизвестный вид состава манифеста: %s; допустимы: %s"
            % (kind, ", ".join(MANIFEST_KEYS))
        )
    return ("(SELECT m." + column + " FROM " + MANIFEST_VIEW +
            " m WHERE m.object_uuid = " + uuid_expr + ")")


def manifest_member_set_sql(kind, uuid_expr):
    """Множество ключей состава ТЕКУЩЕЙ ревизии родителя как подзапрос строк (M5, S4).

        (SELECT unnest(<manifest_array_sql(kind, uuid_expr)>))

    Зачем отдельная функция, а не `= ANY(` + manifest_array_sql(...) + `)`. Построенное
    сравнение `key = ANY((SELECT m.attribute_uuids FROM ...))` Postgres читает НЕ как
    «ключ входит в массив», а как форму подзапроса `= ANY (SELECT ...)`: скаляр сравнивают
    со строкой подзапроса, а ею оказывается весь массив (`uuid[]`/`text[]`). Замер
    18.10.2026 (`C:/TMP/_v19_sqlform_probe.py`, живой SQL) даёт ровно два исхода:
    `ANY((SELECT m.module_paths ...))` — ошибка types text[] и text, `ANY(m.module_paths)`
    и `= ANY(ARRAY(SELECT m.module_paths ...))` — работают. Ошибка же не локальна месту
    сравнения: в составном выражении падает вся команда, поэтому `find_external_object`
    возвращал None вместо карточки — по нему судили об отсутствии объекта, а не о дефекте
    запроса (правило S3: канал один, и он обязан работать).

    `unnest` разворачивает массив в строки ровно там, где сравнение требует набор строк;
    отсутствующий манифест (NULL) `unnest` разворачивает в пустой набор — ни один ребёнок
    не подтверждается, что и есть смысл «состава нет» (различает `manifest_missing_sql`).
    Подзапрос обязан давать не более одной строки манифеста: витрина отдаёт по одной строке
    на uuid объекта (максимальная ревизия), на этом держится и `manifest_array_sql`.
    """
    return "(SELECT unnest(" + manifest_array_sql(kind, uuid_expr) + "))"


def manifest_missing_sql(uuid_expr):
    """Истина, если у текущей ревизии объекта манифест НЕ записан (строки до V19).

    Витрина различает «манифеста нет» (NULL — снимок до V19) и «манифест пуст» (состав снят
    целиком) — `manifest_missing`. Читать их одинаково значит соврать: у первого состав
    неизвестен, у второго — пуст по заявлению. Поэтому число детей без манифеста считается
    только по витрине текущей ревизии (`include_without_manifest`), и карточка обязана это
    назвать, а не выдавать 0 как факт о составе.
    """
    return ("(SELECT COALESCE(m.manifest_missing, TRUE) FROM " + MANIFEST_VIEW +
            " m WHERE m.object_uuid = " + uuid_expr + ")")


def manifest_member_count_sql(uuid_expr):
    """Скаляр: сколько членов заявляет манифест ТЕКУЩЕЙ ревизии объекта (M3, M4).

    Нужен карточке и сверкам: «манифест записан» и «манифест пуст» — разные утверждения, и
    число членов — то, по чему видно, что состав действительно описан. Считается по витрине,
    а не по jsonb напрямую: каналом «что заявлено в составе» остаётся `v_current_object_manifest`,
    иначе карточка и SQL-сверка считали бы состав разными способами (S3).
    """
    parts = " + ".join(
        "COALESCE(array_length(m." + key + ", 1), 0)" for key in MANIFEST_KEYS
    )
    return ("(SELECT " + parts + " FROM " + MANIFEST_VIEW +
            " m WHERE m.object_uuid = " + uuid_expr + ")")


# Чем подтверждается membership детей каждой таблицы (M5, S4): имя состава из манифеста и
# выражение строки ребёнка, ключ которого с ним сравнивается. Разные таблицы — разные
# выражения: uuid ребёнка это ключ его строки в цепочке состояний, а модуль не имеет uuid и
# опознаётся парой parent_type|file_path (M2). Для form_ext состав — uuid формы: описание
# формы относится к её ревизии (uq_form_ext_form_id_revision), собственной uuid-цепочки у
# него нет, поэтому сравнивается колонка form_uuid, а не id.
_MEMBERSHIP = {
    "attributes": ("attribute_uuids", "c.uuid"),
    "tabular_sections": ("tabular_section_uuids", "c.uuid"),
    "forms": ("form_uuids", "c.uuid"),
    "form_ext": ("form_uuids", "c.form_uuid"),
    "templates": ("template_uuids", "c.uuid"),
    "bsl_modules": ("module_paths", MODULE_KEY_EXPR),
}


def current_child_count_sql(table, uuid_expr, include_without_manifest=False):
    """Скалярный подзапрос: число детей ТЕКУЩЕГО состояния объекта (M5, S4).

    Чем это отличается от «SELECT COUNT(*) FROM <таблица> WHERE parent_uuid = …», которым
    пользовались до V19: с историей такой подсчёт считает все ревизии и уже снятых детей,
    то есть приписывает объекту содержимое, которого у него нет. Считает по витрине
    текущей ревизии ребёнка и только те строки, которые называет манифест текущей ревизии
    родителя (A1). Колонки табличных частей — отдельное правило с основанием: их перечень
    принадлежит самой ТЧ (column_uuids, M3), поэтому колонка считается текущей, если она
    названа column_uuids ТЧ, которая сама входит в состав объекта.

    include_without_manifest=True — оговорка для снимков до V19: если у объекта манифест не
    записан (`manifest_missing`), считаются все строки текущей ревизии по parent_uuid. Это
    не «текущий состав по M5», а «состав, которого мы не заявляли»; вызывающий обязан
    назвать число именно так, иначе 0 от строгого подсчёта прочитался бы как «детей нет».
    """
    view = current_view(table)
    member, key_expr = _MEMBERSHIP.get(str(table).strip().lower(), (None, None))
    if not member:
        raise ValueError("Для таблицы '%s' состав детей манифестом не описывается" % table)
    members = manifest_member_set_sql(member, uuid_expr)

    if table == "attributes":
        # Колонки ТЧ не входят в манифест объекта: их перечень принадлежит самой ТЧ
        # (column_uuids, M3), поэтому колонка текущая, если она названа column_uuids ТЧ,
        # которая сама входит в состав объекта.
        ts_members = manifest_member_set_sql("tabular_section_uuids", uuid_expr)
        condition = ("((" + key_expr + ") = ANY(" + members + ") OR EXISTS "
                     "(SELECT 1 FROM " + CURRENT_VIEWS["tabular_sections"] + " ts "
                     "WHERE ts.parent_uuid = " + uuid_expr +
                     " AND ts.uuid = ANY(" + ts_members + ")"
                     " AND ts.column_uuids @> jsonb_build_array(c.uuid::text)))")
    else:
        condition = "(" + key_expr + ") = ANY(" + members + ")"
    if include_without_manifest:
        condition = "(" + manifest_missing_sql(uuid_expr) + " OR " + condition + ")"
    return ("(SELECT COUNT(*) FROM " + view + " c WHERE c.parent_uuid = " + uuid_expr +
            " AND " + condition + ")")


def current_children_counts_sql(uuid_expr, tables=("attributes", "tabular_sections", "forms",
                                                   "form_ext", "templates", "bsl_modules")):
    """Пары (таблица, скалярный подзапрос текущего состава) — для карточек инструментов.

    Возвращает список, а не словарь: порядок нужен вызывающему, который собирает список
    колонок SELECT и соответствующий ему список ключей результата (словарь в Python 3.7+
    порядок сохраняет, но порядок колонок и порядок ключей — две разные вещи, которые
    легко перепутать).
    """
    return [(table, current_child_count_sql(table, uuid_expr)) for table in tables]
