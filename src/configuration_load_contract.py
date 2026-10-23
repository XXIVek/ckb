"""Закрытый контракт результата загрузки конфигурации (узел V45, 22.10.2026).

Конвейер первого слоя загрузки конфигурации: S1 разбор каталога → S2 заголовок (свойства V42 +
перечни имён состава V43 + индекс состава V33) → S3 модули предопределённых программ корня
(V44) → S4 содержимое дочерних объектов (V38, заглушка). Каждая стадия возвращает состояние
выполнения и текст ошибки; первая ошибка останавливает конвейер.

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

from configuration_root_modules import (
    KINDS,
    MODULE_BY_KIND,
    REPORT_STATES,
    ROOT_MODULE_COUNT,
    STATE_ABSENT,
    TABLES,
    TITLE_BY_KIND,
)

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

# Шаг 4 существует как заглушка намеренно (решение оператора 22.10.2026): класс есть, он
# возвращает «сценарий не реализован». Это НЕ ошибка конвейера — иначе ни одна загрузка
# конфигурации не была бы успешной, — и НЕ успех: сказать «конфигурация загружена целиком»,
# когда содержимого объектов нет, значило бы соврать.
CHILD_NOT_IMPLEMENTED = (
    "сценарий не реализован (узел V38): содержимое дочерних объектов конфигурации "
    "(реквизиты, формы, макеты, модули объектов). Модель групп A–H принята, загрузчика нет"
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
