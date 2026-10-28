"""Закрытый контракт результата загрузки конфигурации (узел V45, 22.10.2026).

Конвейер первого слоя загрузки конфигурации: S1 разбор каталога → S2 заголовок (свойства V42 +
перечни имён состава V43 + индекс состава V33) → S3 модули предопределённых программ корня
(V44) → S4 содержимое дочерних объектов (с узла V46 — свойства подсистем, их ссылки `Content`,
свойства и дескрипторы общих модулей; по модели A–H узла V38 это часть групп B и E, а не
группа C — группой C в той модели названы модули предопределённых программ корня, закрытые V44;
тексты модулей — второй транзакцией по решению D7 и только по явной просьбе вызывающего).
Каждая стадия
возвращает состояние выполнения и текст ошибки. Отказ стадии S3 или S4 не отменяет уже
записанный заголовок и называется в ответе отдельно (решения V45 и V46): конвейер
останавливают только отказы разбора каталога и записи заголовка (C5).

Запланированная S5 (дополнение оператора 23.10.2026 — НЕ реализована, в `STAGES` её нет): анализ
загруженной конфигурации по уже сохранённым строкам БД, построение необходимых сниппетов по
объектам и при необходимости перекрёстных ссылок на документацию (`config_*`, контракт V17).
До согласования узла конвейер остаётся S1–S4; план зафиксирован разделом 16
`docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`.

Зачем отдельный модуль. Оператор (22.10.2026) сформулировал требование к ответу так: сводные
таблицы ему не нужны — нужен либо итог «конфигурация загружена», либо содержание ошибки, на
которой загрузка остановилась. При этом машинная часть ответа обязана остаться полной: её
читают `tools/check_v32_zero_configuration.py`, `tools/check_v42_configuration_header.py` и
будущий `tools/check_v44_configuration_root_modules.py`. Значит список ключей обязан быть
закрытым и объявленным ОДНИМ местом: карточка, которая придумывает свои ключи, утверждает то,
чего загрузчик не говорил (именно так сломался форматёр V44 — он держал `counts`, `rows`,
`forms`, `TABLE_MODULES`, которых у контракта загрузчика нет).

Правила контракта:

* C1. Незаполненный ключ читается нулём: `0`, `[]`, `{}`, `False`. Ключей «нет» в ответе быть
  не может — отсутствие ключа каждый вызывающий разрешает `.get()`-ом по-своему, и два
  вызывающих разрешат по-разному.
* C2. Стадия, которая не выполнялась, имеет статус `not_run`, а не нули. «Модулей нет» и
  «модули не загружались» — разные факты (тот же контракт, что «манифеста нет» / «манифест
  пуст» у V19 и `===EMPTY` у V39/V42); нули без статуса стадий слили бы их в одно.
* C3. Ответ каждой стадии вложен в свой ключ (`root_modules`, `child_objects`) без
  переименования: standalone-инструмент `load_configuration_root_modules_tool` отдаёт свой
  плоский контракт, и тот же dict не может быть одновременно и плоским, и вложенным.
* C4. Исходы `already_exists` / `name_conflict` / `kind_conflict` — не ошибка стадии, а точка
  остановки диалога (правило R5); их печатает прежний `format_load_result`, этот модуль их не
  трогает.
* C5. Граница «ошибка» (решение оператора 22.10.2026 — «нам нужна конфигурация без ошибок»):
  останавливают конвейер только отказы — нет каталога или `Configuration.xml`, пустой/кривой
  uuid (R3), ошибка записи в БД, файл модуля не раскодирован (`undecoded`), запись индекса
  вне словаря (`index_unmatched`). Состояния конкретной выгрузки (`absent`, `empty_file`,
  `indexed_no_file`) и файлы `Ext/` вне четырёх модулей (`stray_ext_bsl` — модули объектов,
  второй слой) ошибкой НЕ считаются: замер V40 даёт 6/6/7/7 файлов предопределённых модулей
  на восемь выгрузок, то есть у части конфигураций части этих модулей нет вовсе, и строгое
  правило «только file» не пропустило бы ни одну полную выгрузку.
"""
from typing import Any, Dict, List, Tuple

from configuration_object_properties import (
    CONTENT_STATES,
    DECLARATION_STATES,
    KIND_COMMON_MODULES,
    KIND_SUBSYSTEMS,
)
from configuration_root_modules import (
    KINDS,
    MODULE_BY_KIND,
    REPORT_STATES,
    ROOT_MODULE_COUNT,
    STATE_ABSENT,
    TABLES,
    TITLE_BY_KIND,
)
from current_revision import CONFIGURATION_VERSIONED_TABLES

# ── стадии конвейера: один перечень на контракт, карточку и проверку ───────────────
STAGE_LAYOUT = "s1_layout"
STAGE_HEADER = "s2_header"
STAGE_ROOT_MODULES = "s3_root_modules"
STAGE_CHILD_OBJECTS = "s4_child_objects"

STAGES: Tuple[Tuple[str, str], ...] = (
    (STAGE_LAYOUT, "Разбор каталога выгрузки (Configuration.xml)"),
    (STAGE_HEADER, "Запись заголовка: свойства, перечни состава, индекс состава"),
    (STAGE_ROOT_MODULES, "Модули предопределённых программ корня"),
    (STAGE_CHILD_OBJECTS, "Содержимое дочерних объектов конфигурации"),
)

STATUS_NOT_RUN = "not_run"
STATUS_OK = "ok"
STATUS_SKIPPED = "skipped"
STATUS_ERROR = "error"

# Что из содержимого дочерних объектов стадия S4 НЕ загружает (узлы V38 и V46). С узла V46
# стадия реализована частично: свойства подсистем, их ссылки `Content`, свойства
# и дескрипторы общих модулей. По модели A–H узла V38 это часть групп B (общие модули) и
# E (свойства подсистем без дочерней структуры); группой C в модели названы модули
# предопределённых программ корня, их закрыл узел V44 — прежняя формулировка «группа C закрыта
# для подсистем и общих модулей» была неверной именно поэтому. Остальное остаётся незакрытым,
# и текст стадии обязан это
# назвать: сказать «конфигурация загружена целиком», когда реквизитов и форм объектов нет,
# значило бы соврать (решение оператора 22.10.2026 о том, что заглушка не является ни
# ошибкой, ни успехом, сохраняется для неотзакрытой части).
CHILD_NOT_IMPLEMENTED = (
    "содержимое дочерних объектов загружено частично: закрыты свойства подсистем и общих "
    "модулей (узел V46, по модели V38 — часть групп B и E); не реализованы реквизиты и "
    "табличные части объектов "
    "конфигурации, формы, макеты, модули объектов, значения перечислений, роли и команды — "
    "остальные группы A–H "
    "модели V38, узел V18 остаётся открытым"
)

# Ключи `index_counts` — контракт разбора `ConfigDumpInfo.xml` (узел V33). Перечень держится
# здесь, потому что нулевой словарь по этому перечню обязан совпадать с настоящим ответом:
# карточка, которая заполняет «свои» семь ключей, через месяц теряет два из них.
INDEX_COUNT_KEYS: Tuple[str, ...] = (
    "entries_total", "root_entries", "child_entries", "max_depth",
    "config_versions", "config_versions_missing", "parent_unresolved",
)


def index_counts_defaults() -> Dict[str, int]:
    return {key: 0 for key in INDEX_COUNT_KEYS}


def header_array_anomalies_defaults() -> Dict[str, Any]:
    """Аномалии перечней V43: `unknown_types` — список видов, остальные — счётчики."""
    return {"unknown_types": [], "overlong": 0, "empty_object_name": 0,
            "top_level_entries": 0}


def root_modules_defaults() -> Dict[str, Any]:
    """Плоский контракт `load_root_modules` с нулями (C1, C3).

    `by_kind` остаётся пустым словарём, а не `{вид: absent}`: «вида нет в конфигурации» — это
    утверждение о выгрузке, которое делает только выполненный разбор. Для невыполненной стадии
    честный ответ — пустой словарь плюс `stages[].status = not_run` (C2).

    Ключ `error` входит в замкнутый перечень: его читает форматёр отказа
    («Стадия не выполнена: …») и кладёт конвейер при пропуске стадии. По C1 ключа
    «нет» в ответе быть не может — причина либо названа строкой, либо `None`.
    """
    return {
        "success": False,
        "error": None,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(TABLES),
        "written": 0,
        "written_by_table": {table: 0 for table in TABLES},
        "kinds_total": ROOT_MODULE_COUNT,
        "counts_by_state": {state: 0 for state in REPORT_STATES},
        "by_kind": {},
        "removed_previous": {table: 0 for table in TABLES},
        "index_available": False,
        "index_root_name": None,
        "index_rows": 0,
        "index_matched": 0,
        "index_unmatched": [],
        "stray_ext_bsl": [],
        "warnings": [],
    }


def child_objects_defaults() -> Dict[str, Any]:
    return {"status": STATUS_NOT_RUN, "reason": None, "objects_written": 0, "tables": []}


# ── текст стадии S3: один форматёр на карточку и на отдельный инструмент ────────────

# Заголовок раздела карточки `load_1c_catalog_tool` (вариант `configuration`) и ответа
# `load_configuration_root_modules_tool`. Один на два контура: карточка и инструмент
# описывают один и тот же слой, а заголовок и текст, переписанные порознь, разъезжаются
# при первой же правке контракта — по той же причине, по которой имена 48 перечней V43
# и фильтр карантина Q1 лежат в одном месте.
ROOT_MODULES_SECTION_HEADER = "КОД ПРЕДОПРЕДЕЛЁННЫХ ПРОГРАММ КОРНЯ (узел V44)"


def format_root_modules_lines(result: Dict[str, Any],
                              indent: str = "") -> List[str]:
    """Текст состояния стадии S3 по плоскому контракту `load_root_modules` (C1, C3).

    Формат один для двух контуров: карточки `load_1c_catalog_tool` и ответа
    `load_configuration_root_modules_tool` (решение V45). Отказ стадии форматёр
    называет сам («Стадия не выполнена: …») — вызывающий причину не повторяет: два
    текста об одном отказе разъезжаются (так же сломался прежний форматёр V44,
    державший `counts`, `rows`, `forms`, `TABLE_MODULES`, которых у контракта нет).
    Проблемные строки (несовпавшие записи индекса, файлы `Ext/` вне словаря, снятые
    прежние строки) кладёт в `warnings` сама стадия — форматёр их печатает, а не
    пересобирает по полям. Неперечисленные ключи читаются нулями (C1).
    """
    lines: List[str] = []
    if not result:
        return lines
    if not result.get("success"):
        lines.append(
            f"{indent}Стадия не выполнена: "
            f"{result.get('error') or 'загрузчик не назвал причину'}"
        )
        return lines

    counts_by_state = result.get("counts_by_state") or {}
    lines.append(
        f"{indent}Записано строк: {int(result.get('written') or 0)}; "
        f"ожидаемых видов: {int(result.get('kinds_total') or ROOT_MODULE_COUNT)}; "
        "состояния: "
        + ", ".join(
            f"{state}={int(counts_by_state.get(state) or 0)}"
            for state in REPORT_STATES
        )
    )
    by_kind = result.get("by_kind") or {}
    for kind in KINDS:
        lines.append(
            f"{indent}{MODULE_BY_KIND[kind]} ({TITLE_BY_KIND[kind]}): "
            f"{by_kind.get(kind) or STATE_ABSENT}"
        )
    if result.get("index_available"):
        lines.append(
            f"{indent}Индекс состава: строка корня "
            f"{result.get('index_root_name') or 'не названа'}, подтверждено слотов "
            f"{int(result.get('index_matched') or 0)} из {ROOT_MODULE_COUNT} "
            f"(записей вида: {int(result.get('index_rows') or 0)})"
        )
    else:
        lines.append(
            f"{indent}Индекс состава не читается — состояния называет только файл, "
            "и «модуля нет» от «пустого модуля» этим не отличить"
        )
    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    return lines


# ── стадия S4: содержимое дочерних объектов (узел V46, 28.10.2026) ────────────────────

# Круг таблиц стадии задаёт тот же перечень, что и круг версионных таблиц конфигурации
# (`src/current_revision.py`): отдельного списка здесь заводить нельзя — круг разъехался бы
# с кругом версионности, и ровно так появился D11 (круг задаёт признак версии, а не список).
CHILD_TABLES: Tuple[str, ...] = CONFIGURATION_VERSIONED_TABLES
CHILD_KINDS: Tuple[str, ...] = (KIND_SUBSYSTEMS, KIND_COMMON_MODULES)
CHILD_KIND_TITLES: Dict[str, str] = {
    KIND_SUBSYSTEMS: "Подсистемы",
    KIND_COMMON_MODULES: "Общие модули",
}

# Заголовок раздела карточки `load_1c_catalog_tool` (вариант `configuration`) и ответа
# `load_configuration_object_properties_tool` — один на два контура (решение V45: карточка и
# инструмент описывают один слой одинаково; переписанные порознь, они разъезжаются при первой
# же правке контракта).
CHILD_SECTION_HEADER = "СОДЕРЖИМОЕ ДОЧЕРНИХ ОБЪЕКТОВ: ПОДСИСТЕМЫ И ОБЩИЕ МОДУЛИ (узел V46)"


def child_object_kind_defaults() -> Dict[str, Any]:
    """Одна группа стадии S4 с нулями (C1).

    `requested` отделяет «вид не просили» от «таких объектов в конфигурации нет»: по нулям
    эти два ответа неразличимы (C2), поэтому состояние запрашивания — часть контракта, а не
    домысел вызывающего. Словари состояний заполняются нулями по словарям РАЗБОРА
    (`configuration_object_properties`), а не своим перечнем: два словаря состояний
    разъезжаются, и CHECK схемы (`common_module_sources_content_state_check`) тогда отстаёт
    от кода.
    """
    return {
        "requested": False,
        "written": 0,
        "counts_by_state": {state: 0 for state in DECLARATION_STATES},
        "by_depth": {},
        "content_total": 0,
        "content_resolved": 0,
        "content_unresolved": 0,
        "content_by_form": {},
        "content_by_target_type": {},
        "slots_by_state": {},
        "descriptor_rows": 0,
        "counts_by_content_state": {state: 0 for state in CONTENT_STATES},
        "modules_without_descriptor": 0,
        "index_available": False,
        "index_objects": 0,
        "index_slots": 0,
        "parse_errors": [],
        "layout_outliers": [],
        "removed_previous": 0,
    }


def child_module_content_defaults() -> Dict[str, Any]:
    """Тексты модулей общих модулей — вторая транзакция по D7 (C1).

    `requested` distinguishes «тексты не просили» (`with_module_content=False`, состояние
    по умолчанию замера 2.6: 188–294 МБ на выгрузку) from «просили, и их нет». `skipped`
    считает дескрипторы, у которых текста нет физически (`bin_only`, `indexed_no_file`) —
    их отсутствие в `bsl_modules` не является потерей, но обязано быть названо числом.
    """
    return {
        "requested": False,
        "written": 0,
        "truncated": 0,
        "skipped": 0,
        "code_limit": None,
        "counts_by_state": {state: 0 for state in CONTENT_STATES},
        "removed_previous": 0,
        "errors": [],
    }


def child_objects_defaults() -> Dict[str, Any]:
    """Закрытый контракт стадии S4 (C1, C3).

    Словарь плоский — тот же, что возвращает отдельный инструмент; конвейер вкладывает его
    в свой ключ `child_objects` без переименования (C3). `status` различает «стадия не
    выполнялась» (`not_run`, C2) и «выполнилась с отказом» (`error`): нули без статуса
    слили бы эти два факта в одно.
    """
    return {
        "status": STATUS_NOT_RUN,
        "success": False,
        "error": None,
        "reason": None,
        "configuration_id": None,
        "configuration_uuid": None,
        "configuration_name": None,
        "tables": list(CHILD_TABLES),
        "kinds_requested": [],
        "kinds": {kind: child_object_kind_defaults() for kind in CHILD_KINDS},
        "module_content": child_module_content_defaults(),
        "objects_written": 0,
        "warnings": [],
    }


def format_child_object_lines(result: Dict[str, Any],
                              indent: str = "") -> List[str]:
    """Текст стадии S4 по закрытому контракту `child_objects_defaults()` (C1, C3).

    Формат один для двух контуров: раздела карточки `load_1c_catalog_tool` и ответа
    `load_configuration_object_properties_tool` (решение V45). Отказ форматёр называет сам
    («Стадия не выполнена: …») — вызывающий причину не повторяет, иначе два текста об одном
    отказе разъезжаются. Неперечисленные ключи читаются нулями (C1).

    Строка о незакрытой части содержимого дочерних объектов печатается и при успехе: «свойства
    подсистем и общих
    модулей записаны» не равно «содержимое дочерних объектов загружено» — границы узла V46
    (план, раздел 8) читаются из ответа, а не из молчания.
    """
    lines: List[str] = []
    if not result:
        return lines
    if not result.get("success"):
        reason = result.get("error") or result.get("reason") or "загрузчик не назвал причину"
        prefix = ("Стадия не выполнена" if result.get("status") in (None, STATUS_NOT_RUN)
                  else "Стадия не удалась")
        lines.append(f"{indent}{prefix}: {reason}")
        return lines

    kinds = result.get("kinds") or {}
    removed_by_kind = {
        kind: int((kinds.get(kind) or {}).get("removed_previous") or 0)
        for kind in CHILD_KINDS
    }
    removed_total = sum(removed_by_kind.values())
    lines.append(
        f"{indent}Записано строк свойств: {int(result.get('objects_written') or 0)}; "
        f"таблицы: {', '.join(result.get('tables') or CHILD_TABLES)}"
        + (f"; снято прежних строк: {removed_total} ("
           + ", ".join(f"{kind} {count}" for kind, count in sorted(removed_by_kind.items())
                       if count) + ")"
           if removed_total else "; прежних строк не снималось")
    )

    for kind in CHILD_KINDS:
        title = CHILD_KIND_TITLES[kind]
        part = kinds.get(kind) or {}
        if not part.get("requested"):
            lines.append(
                f"{indent}{title}: вид не запрашивался — нули здесь не означают, что таких "
                "объектов в конфигурации нет"
            )
            continue
        counts_by_state = part.get("counts_by_state") or {}
        line = (
            f"{indent}{title}: строк {int(part.get('written') or 0)}; состояния объявления: "
            + ", ".join(f"{state}={int(counts_by_state.get(state) or 0)}"
                        for state in DECLARATION_STATES)
        )
        by_depth = part.get("by_depth") or {}
        if by_depth:
            try:
                order = sorted(by_depth, key=lambda depth: int(depth))
            except (TypeError, ValueError):
                order = sorted(str(depth) for depth in by_depth)
            line += "; глубина дерева: " + ", ".join(
                f"{depth}={int(by_depth[depth])}" for depth in order
            )
        lines.append(line)
        if not part.get("index_available"):
            lines.append(
                f"{indent}  Индекс состава не читается — состояния называются только по "
                "файлу, и «объекта нет» от «объект не подтверждён индексом» этим не отличить"
            )
        for outlier in part.get("layout_outliers") or []:
            lines.append(f"{indent}  ⚠️ раскладка: {outlier}")
        for failure in part.get("parse_errors") or []:
            lines.append(f"{indent}  ⚠️ файл регистрации: {failure}")

        if kind == KIND_SUBSYSTEMS:
            total = int(part.get("content_total") or 0)
            resolved = int(part.get("content_resolved") or 0)
            unresolved = int(part.get("content_unresolved") or 0)
            by_form = part.get("content_by_form") or {}
            lines.append(
                f"{indent}  Ссылки Content: всего {total}, разрешено {resolved}, "
                f"неразрешено {unresolved} (форма ссылок: "
                + ", ".join(f"{form}={int(count)}" for form, count in sorted(by_form.items()))
                + "); неразрешённые остаются строкой в `content_unresolved` самого объекта, "
                  "а не молчанием (D3)"
            )
            for slot, stats in sorted((part.get("slots_by_state") or {}).items()):
                stats = stats or {}
                lines.append(
                    f"{indent}  Слоты {slot}: записей индекса "
                    f"{int(stats.get('index_records') or 0)}, файлов "
                    f"{int(stats.get('files') or 0)}, объявлено индексом без файла "
                    f"{int(stats.get('indexed_no_file') or 0)}, файл вне индекса "
                    f"{int(stats.get('file_not_in_index') or 0)}; содержимое слота (xtui, "
                    "html) в схеме не хранится — граница узла V46"
                )
        else:
            content_counts = part.get("counts_by_content_state") or {}
            lines.append(
                f"{indent}  Дескрипторы модулей: {int(part.get('descriptor_rows') or 0)}; "
                "состояния текста: "
                + ", ".join(f"{state}={int(content_counts.get(state) or 0)}"
                            for state in CONTENT_STATES)
                + f"; модулей без дескриптора: "
                  f"{int(part.get('modules_without_descriptor') or 0)}"
            )

    module_content = result.get("module_content") or {}
    if not module_content.get("requested"):
        lines.append(
            f"{indent}Тексты модулей общих модулей: не запрашивались "
            "(with_module_content=False; замер 2.6: 188 МБ BGU2, 294 МБ BP3) — в bsl_modules "
            "строк общих модулей этой загрузкой не записано, а "
            "common_module_sources.content_loaded остался false (решения D6, D7)"
        )
    else:
        limit = module_content.get("code_limit")
        lines.append(
            f"{indent}Тексты модулей общих модулей (bsl_modules, вторая транзакция D7): "
            f"записано {int(module_content.get('written') or 0)}, усечено "
            f"{int(module_content.get('truncated') or 0)}, пропущено "
            f"{int(module_content.get('skipped') or 0)} (текста нет физически), снято прежних "
            f"{int(module_content.get('removed_previous') or 0)}; усечение: "
            + ("без лимита (code_limit не задан)" if not limit else f"до {int(limit)} симв.")
            + "; родителем строки выступает uuid самого общего модуля (parent_uuid, "
              "parent_type=common_modules), цепочка "
              "состояний — по пути файла, как у модулей внешнего объекта (M1, M3)"
        )
        for failure in module_content.get("errors") or []:
            lines.append(f"{indent}  ⚠️ текст модуля: {failure}")

    for warning in result.get("warnings") or []:
        lines.append(f"{indent}⚠️ {warning}")
    lines.append(f"{indent}Граница: {CHILD_NOT_IMPLEMENTED}")
    return lines


