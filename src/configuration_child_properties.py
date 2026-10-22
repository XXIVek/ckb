#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Дочерние свойства конфигурации: массивы имён в строке заголовка (узел V43, 22.10.2026).

Основание — файл оператора `C:\\1C_LLM\\Дочерние свойства для конфигурации.txt` (21.10.2026):
48 дочерних свойств, каждое описано как «поле в конфигурации — всегда список значений, тип
строка макс 80 символов». Файл предлагает на каждое свойство отдельную таблицу; реализуется
первая часть того же контракта — поле-массив имён в `configurations`. Модель хранения
дочерних объектов (группы A–H, узел V38) этим узлом НЕ реализуется: только перечень имён.

Один словарь на три места (миграция, бутстрап шага 2, загрузчик) — по той же причине, по
которой фильтр карантина живёт в `src/quarantine.py`: 48 имён, переписанных в трёх файлах
порознь, обязательно разъедутся.

Ключ словаря — `object_type` индекса состава (`configuration_objects`, узел V33), а не имя
таблицы из файла. Замер 22.10.2026 (`_child_arrays_probe.sql`, живая БД: BGU2 + BP3 + KomMag
+ MinCfg, 274 141 строка индекса):

* K1. На `depth = 0` индекс отдаёт 49 `object_type` — ровно 48 видов файла плюс
  `Configuration` (сам корень, 4 строки). Дочерним свойством корень не является, поэтому в
  словарь не входит; граница названа здесь, а не молчит.
* Имена таблиц в файле местами опечатки (`ChartOfAccountss`, `ChartOfCharacteristicTypess`,
  `ChartOfCalculationTypess`, `BusinessProcesss`, `FilterCriterions`, `CalculationRegister`
  без `-s`) — источником они быть не могут. `object_type` — то, что отдаёт `ConfigDumpInfo.xml`.
* K3. `max(length(object_name)) = 80`, длиннее 80 — 0 строк (границы достигают `CommonModule`
  и `EventSubscription`); полные точечные имена — до 202. Значит в массив кладётся короткое
  `object_name`, а граница 80 — измеренная граница платформы (якорь
  `property-common-name-synonym-comment` слоя `xml-format`), а не наблюдение одной фикстуры.
* K4. Дублей `(configuration_id, object_type, object_name)` на `depth = 0` — 0: массив имён
  внутри вида в одной конфигурации однозначен.
* K5. `DocumentNumerator` (22) и `Sequence` (6) индекс моделирует ВЕРХНИМИ записями
  (`depth = 0`, `parent_name IS NULL`), хотя файл помечает их «только для документов».
  Родитель для них не нужен: индекс не прячет их внутрь документа — это и показывает замер.

Пустое состояние: вида в индексе нет → `None` (колонка остаётся `NULL`), а не `[]` — тот же
контракт, что у V39/V42 («пустая колонка читается как “в выгрузке этого нет”»). Различить
«вида нет» и «вид есть, но объектов ноль» индекс не может, поэтому выбран вариант, совпадающий
с остальной схемой.

Порядок имён — по полному точечному `name`, детерминированный и совпадающий с заполнением
миграции (`array_agg(object_name ORDER BY name COLLATE "C")`): порядок байт UTF-8 совпадает с
порядком кодовых точек, поэтому Python и PostgreSQL дают один список.
"""
from typing import Dict, Iterable, List, Tuple

# ── константы узла V43: один источник для модуля, загрузчика и зондов ─────────────
# Граница элемента массива: замер 22.10.2026 по 274 141 строке индекса — ровно 80, длиннее 0.
NAME_MAX_LEN = 80
# Верхний уровень индекса = объект метаданных; глубже — его содержимое (формы, реквизиты, …).
TOP_LEVEL_DEPTH = 0
# Корень конфигурации: индекс его перечисляет, дочерним свойством он не является (граница K1).
ROOT_OBJECT_TYPE = "Configuration"
# Сколько примеров называть текстом предупреждения (дальше — «ещё N»): предупреждение,
# перечисляющее 40 видов, оператор не прочитает.
MAX_EXAMPLES = 10

# (object_type индекса состава, колонка configurations, пункт файла оператора).
# Порядок повторяет нумерацию файла 1…48, чтобы маппинг читался против источника.
# Имена object_type подтверждены замером: все 48 присутствуют в configuration_objects на
# depth = 0 (_v43_types.txt, 22.10.2026); 49-е значение — Configuration, оно здесь лишним.
CHILD_PROPERTIES: Tuple[Tuple[str, str, int], ...] = (
    ("Subsystem", "subsystems", 1),
    ("CommonModule", "common_modules", 2),
    ("SessionParameter", "session_parameters", 3),
    ("Role", "roles", 4),
    ("CommonAttribute", "common_attributes", 5),
    ("ExchangePlan", "exchange_plans", 6),
    ("FilterCriterion", "filter_criteria", 7),
    ("EventSubscription", "event_subscriptions", 8),
    ("ScheduledJob", "scheduled_jobs", 9),
    ("Bot", "bots", 10),
    ("FunctionalOption", "functional_options", 11),
    ("FunctionalOptionsParameter", "functional_options_parameters", 12),
    ("DefinedType", "defined_types", 13),
    ("SettingsStorage", "settings_storages", 14),
    ("CommonCommand", "common_commands", 15),
    ("CommandGroup", "command_groups", 16),
    ("CommonForm", "common_forms", 17),
    ("Interface", "interfaces", 18),
    ("CommonTemplate", "common_templates", 19),
    ("CommonPicture", "common_pictures", 20),
    ("XDTOPackage", "xsdto_packages", 21),
    ("WebService", "web_services", 22),
    ("HTTPService", "http_services", 23),
    ("WSReference", "ws_references", 24),
    ("WebSocketClient", "web_socket_clients", 25),
    ("IntegrationService", "integration_services", 26),
    ("StyleItem", "style_items", 27),
    ("Style", "styles", 28),
    ("Language", "languages", 29),
    ("Constant", "constants", 30),
    ("Catalog", "catalogs", 31),
    ("Document", "documents", 32),
    ("DocumentNumerator", "document_numerators", 33),
    ("Sequence", "sequences", 34),
    ("DocumentJournal", "document_journals", 35),
    ("Enum", "enums", 36),
    ("Report", "reports", 37),
    ("DataProcessor", "data_processors", 38),
    ("ChartOfCharacteristicTypes", "charts_of_characteristic_types", 39),
    ("ChartOfAccounts", "charts_of_accounts", 40),
    ("ChartOfCalculationTypes", "charts_of_calculation_types", 41),
    ("InformationRegister", "information_registers", 42),
    ("AccumulationRegister", "accumulation_registers", 43),
    ("AccountingRegister", "accounting_registers", 44),
    ("CalculationRegister", "calculation_registers", 45),
    ("BusinessProcess", "business_processes", 46),
    ("Task", "tasks", 47),
    ("ExternalDataSource", "external_data_sources", 48),
)

CHILD_COUNT = len(CHILD_PROPERTIES)
CHILD_ARRAY_COLUMNS: Tuple[str, ...] = tuple(column for (_t, column, _n) in CHILD_PROPERTIES)
CHILD_OBJECT_TYPES: Tuple[str, ...] = tuple(object_type for (object_type, _c, _n) in CHILD_PROPERTIES)
COLUMN_BY_OBJECT_TYPE: Dict[str, str] = {
    object_type: column for (object_type, column, _n) in CHILD_PROPERTIES
}
OBJECT_TYPE_BY_COLUMN: Dict[str, str] = {
    column: object_type for (object_type, column, _n) in CHILD_PROPERTIES
}


def header_array_columns() -> Tuple[str, ...]:
    """Имена 48 колонок-перечней в порядке канонического контракта (узел V43).

    Единственный источник имён и порядка для трёх мест: блок DDL шага 2
    (`create_1c_configurations_db.sql`), бэкфилл миграции
    (`migrate_v43_configuration_child_arrays.sql`) — их генерирует `_v43_gen_sql.py`
    из этого словаря — и писатель `ConfigurationRowWriter`
    (`src/external_table_writer.py`) вместе с метриками загрузчика
    (`src/configuration_loader.py`). Писатель не имеет права придумывать свой перечень
    колонок — тот же принцип, что `REVISION_COLUMNS` у узла V19: иначе код и DDL
    разошлись бы при первом же добавленном виде метаданных.

    Порядок — канонический (правило K6), а не алфавитный по имени колонки: он
    совпадает с порядком генерации SQL и с `CHILD_ARRAY_COLUMNS`.
    """
    return CHILD_ARRAY_COLUMNS


# ── правило агрегации (узел V43) ───────────────────────────────────────────────
#
# Единственное место на Python, где правило записано; SQL-backfill
# `migrate_v43_configuration_child_arrays.sql` повторяет его дословно (те же K1, K5, K6).
# Согласованность двух контуров проверяется не комментарием, а сверкой на одной
# выгрузке: массив, собранный этим функцией из разбора `ConfigDumpInfo.xml`, против
# колонок БД, заполненных миграцией из `configuration_objects` (`_v43_loader_probe.py`).
# Если поправить одно выражение и не поправить второе, расхождения не покажет ни одна
# проверка по отдельному контуру — тот же класс дефекта, что собственный
# `max(revision_no)` в модуле-вызывателе до узла V19.


def collect_header_arrays(entries: Iterable[dict]) -> Dict[str, object]:
    """Собрать значения колонок-массивов по записям индекса состава (узел V43).

    `entries` — контракт `src/config_dump_info_parser.py` (`objects[]`): словари с полями
    `name`, `object_type`, `object_name`, `depth`. Правила — те, что названы в docstring
    модуля:

    * K1 — берутся только записи `depth == TOP_LEVEL_DEPTH` (объекты метаданных верхнего
      уровня); вложенное содержимое (`Catalog.Х.Форма.УстановкиОборотов`, реквизиты,
      командный интерфейс) в состав свойства не входит. Вид `ROOT_OBJECT_TYPE` не имеет
      колонки и в аномалии не попадает: это не вид метаданных, а сама конфигурация;
    * K2 — значение всегда список: у вида с одним объектом список из одного элемента;
    * K5 — элемент — ИМЯ объекта (`object_name`), а не полное точечное имя: вид задаёт
      сама колонка, повторять его в каждом элементе — описывать колонку, а не свойство;
    * K6 — порядок по полному имени (`name`) в побайтовом порядке: ключ сортировки —
      байты UTF-8, это тот же порядок, что `ORDER BY name COLLATE "C"` при
      `server_encoding = UTF8`. Порядок по локали базы (`datcollate` = Russian_Russia.1251
      по замеру) дал бы другой список, и Python с PostgreSQL разошлись бы.

    Возврат: `{values, counts, columns_total, columns_filled, top_level_entries,
    objects_total, unknown_types, overlong, empty_object_name, warnings}`. `values`
    содержит только непустые колонки — пустая колонка остаётся `NULL` («в выгрузке этого
    вида нет»), а не пустым списком (тот же контракт, что у V39/V42).

    Аномалии называются, а не сворачиваются в ноль: вид верхнего уровня без колонки
    (слепая зона словаря — знание неполное, а не свойство пустое), имя длиннее границы
    K3, пустое имя объекта. Молча пропущенная запись отличалась бы от «такого вида в
    конфигурации нет» — ровно тот класс расхождения, который узел V42 снял маркером
    `UNKNOWN_PROPERTY`.
    """
    groups: Dict[str, List[Tuple[bytes, str]]] = {}
    unknown_types: Dict[str, int] = {}
    overlong: List[Tuple[str, str, int]] = []
    empty_object_name = 0
    top_level_entries = 0

    for entry in entries or ():
        if entry.get("depth") != TOP_LEVEL_DEPTH:
            continue
        top_level_entries += 1
        object_type = str(entry.get("object_type") or "")
        column = COLUMN_BY_OBJECT_TYPE.get(object_type)
        if column is None:
            if object_type != ROOT_OBJECT_TYPE:
                unknown_types[object_type] = unknown_types.get(object_type, 0) + 1
            continue
        short = str(entry.get("object_name") or "")
        full = str(entry.get("name") or "")
        if not short:
            empty_object_name += 1
        if len(short) > NAME_MAX_LEN:
            overlong.append((object_type, short, len(short)))
        groups.setdefault(column, []).append((full.encode("utf-8"), short))

    values: Dict[str, List[str]] = {}
    counts: Dict[str, int] = {}
    for column in CHILD_ARRAY_COLUMNS:          # порядок словаря, а не порядок встречи
        items = groups.get(column)
        if not items:
            continue
        items.sort(key=lambda pair: pair[0])    # K6
        names = [name for _key, name in items]
        values[column] = names
        counts[column] = len(names)

    warnings: List[str] = []
    if unknown_types:
        shown = ", ".join(f"{name} ({count})"
                          for name, count in sorted(unknown_types.items())[:MAX_EXAMPLES])
        hidden = len(unknown_types) - MAX_EXAMPLES
        if hidden > 0:
            shown += f", … (ещё {hidden})"
        warnings.append(
            "узел V43: индекс состава отдаёт виды объектов верхнего уровня без колонки: "
            f"{shown}. Словарь `CHILD_PROPERTIES` их не покрывает — это неполнота нашего "
            "словаря, а не пустое свойство конкретной выгрузки."
        )
    if overlong:
        shown = ", ".join(f"{type_name}.{name} ({length})"
                          for type_name, name, length in overlong[:MAX_EXAMPLES])
        hidden = len(overlong) - MAX_EXAMPLES
        if hidden > 0:
            shown += f", … (ещё {hidden})"
        warnings.append(
            f"узел V43: {len(overlong)} имя(имён) длиннее границы K3 ({NAME_MAX_LEN} "
            f"символов): {shown}. Значение записано как есть: обрезать его — значит "
            "изменить состав перечня."
        )
    if empty_object_name:
        warnings.append(
            f"узел V43: {empty_object_name} запись(ей) верхнего уровня с пустым именем "
            "объекта; элемент оставлен пустой строкой, потому что молча убрать его — "
            "значит показать состав меньше, чем в выгрузке."
        )

    return {
        "values": values,
        "counts": counts,
        "columns_total": CHILD_COUNT,
        "columns_filled": len(counts),
        "top_level_entries": top_level_entries,
        "objects_total": sum(counts.values()),
        "unknown_types": unknown_types,
        "overlong": overlong,
        "empty_object_name": empty_object_name,
        "warnings": warnings,
    }
