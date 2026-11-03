#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик свойств регламентных заданий (узел V54, шаг П4, 03.11.2026).

Стадия S4i конвейера первого слоя: файлы вида `ScheduledJobs` (позиция 2.9 нормативного
списка плана `docs/CONFIGURATION_SCHEDULED_JOBS_PLAN.md`) в две таблицы — `scheduled_jobs`
(строка задания, версионируемая цепью) и `scheduled_job_schedules` (записи расписания из
`Ext/Schedule.xml`). Норматив — тот же план (решения Q1–Q8, наблюдения M1–M6); разбор
файлов вида — отдельный модуль `src/configuration_scheduled_jobs.py` (шаг П3), писатели
строк двух таблиц добавлены этим же шагом П4 в реестр `CONFIGURATION_OBJECT_WRITERS`.

Почему стадия отдельная, а не девятый вид S4 (прецеденты Q5 узлов V48–V53): правило C3
требует своего ключа ответа `scheduled_jobs`; порядок `STAGES` повторяет порядок
нормативного списка (2.9 идёт сразу за 2.8), поэтому S4i стоит между S4h и S4b. Круг стадии
(`SCHEDULED_JOBS_TABLES`) отделён от круга версионности этим же шагом: регистрация таблицы
вида в `CONFIGURATION_VERSIONED_TABLES` молча добавила бы её к чужой стадии — тот дефект,
который закрывали записи V49…V53.

Групп запроса (`kinds`) у вида нет — как у V50, V52 и V53 — и это решение, а не упущение
(Q5, вариант A): запись расписания существует только через id строки вида (Q2, вариант A),
поэтому состояния «записать задание без расписания» в модели нет; порога цены, при котором
круг стоило бы резать, замер 1.1/2.2 не дал (346 файлов регистрации и 313 записей
расписания на весь круг, максимум 3 записи в одном файле). Отдельный вход дозагружает весь
круг сразу.

Идемпотентность держится явным `DELETE` по `configuration_uuid` (внешнего ключа на
`configurations` и каскада по нему в схеме нет осознанно — прецеденты V20.1, V44, V46, V48,
V49, V50, V51, V52, V53), а не новой ревизией: повтор той же выгрузки не создаёт истории,
снятые строки названы в ответе. Ключом цепочки строки вида является (`configuration_uuid`,
`object_name`, `revision_no`) — замер M1 плана: имена заданий стоят одновременно в BGU2 и
BP3, и без границы конфигурации две выгрузки слились бы в одну строку.

Круг пишется одной транзакцией, и отказ разбора любого файла круга останавливает стадию ДО
записи: в базе не остаётся половины строк (приём V12/V46/V48/V49/V50/V51/V52/V53). Молча
записать то, что разобралось, означало бы назвать неполный круг полным.

После фиксации загрузчик пересобирает статистику двух таблиц (`refresh_table_statistics` —
мера V46): без статистики счётчики по витринам текущего состояния на большой выгрузке
выполняются минутами (замер V46 на BGU2: 8 мин 25 с против 7 мс). Отказ статистики отказом
загрузки не является — строки зафиксированы, и это предупреждение.

Прогон шага: `python _v54_p4_load_probe.py MinCfg KomMag`, затем отдельно BGU2 и BP3
(прогоны, меняющие общее состояние БД, не параллелят). Проверка узла —
`python tools/check_v54_scheduled_jobs.py` (шаг П6).
"""
from typing import Any, Dict, List, Optional, Tuple

from configuration_load_contract import (
    SCHEDULED_JOB_CONTENT_DISCREPANCIES,
    SCHEDULED_JOBS_REMOVE_ORDER,
    SCHEDULED_JOBS_REPEAT_HINT,
    SCHEDULED_JOBS_TABLES,
    STATUS_ERROR,
    STATUS_OK,
    scheduled_jobs_defaults,
)
from configuration_object_properties_loader import refresh_table_statistics
from configuration_root_module_loader import configuration_uuid_from_layout
from configuration_scheduled_jobs import (
    CIRCLE_DISCREPANCIES,
    SCHEDULE_CHILD_KIND,
    SCHEDULE_FILE_NAME,
    SCHEDULES_TABLE_NAME,
    TABLE_NAME,
    collect_scheduled_jobs,
    kind_child_index_rows,
    kind_root_index_rows,
    module_method_names,
)
from current_revision import (
    CHANGED_BY_LOAD,
    CURRENT_VIEWS,
    FIRST_REVISION,
    stamp_revision_rows,
)
from external_db import transaction
from external_table_writer import CONFIGURATION_OBJECT_WRITERS


OBJECTS_TABLE = "configuration_objects"
JOBS_TABLE = TABLE_NAME
SCHEDULES_TABLE = SCHEDULES_TABLE_NAME
# Перечень общих модулей и тексты их модулей берутся из витрин текущего состояния (имена
# даёт реестр `CURRENT_VIEWS`, а не строка в этом коде: опечатка в имени читалась бы как
# «нет такой таблицы», а не как пропущенный фильтр ревизий). Строки общих модулей пишет
# узел V46, тексты — тот же узел второй транзакцией при `with_module_content=True`
# (решение D-S4), поэтому в живой базе текстов ноль (замер 03.11.2026), а состояние
# объявления метода остаётся `text_unavailable` — границей базы, а не свойством выгрузки
# (Q8, вариант A).
COMMON_MODULES_TABLE = "common_modules"
COMMON_MODULES_VIEW = CURRENT_VIEWS[COMMON_MODULES_TABLE]
BSL_MODULES_TABLE = "bsl_modules"
BSL_MODULES_VIEW = CURRENT_VIEWS[BSL_MODULES_TABLE]
COMMON_MODULE_PARENT_TYPE = "common_modules"

# Писатели двух таблиц берутся общим реестром, а не импортом классов (правило п.6 слоя):
# ошибка выбора превращается в запись не в ту таблицу, а реестр уже знает, какая таблица
# версионируется своей цепочкой, а какая — нет (`CONFIGURATION_UNVERSIONED_TABLES`).
SJ_WRITERS = {table: CONFIGURATION_OBJECT_WRITERS[table] for table in SCHEDULED_JOBS_TABLES}

# Порядок снятия круга — не порядок `SCHEDULED_JOBS_TABLES`: записи расписания снимаются ДО
# строк вида, потому что их собственный FK `scheduled_job_schedules_scheduled_job_id_fkey`
# объявлен с `ON DELETE CASCADE` — каскад снял бы их молча, и число в ответе было бы
# неправдой (M7). Тот же приём, что `REMOVE_ORDER` узлов V49/V50/V52/V53. Порядок берётся из
# контракта одним местом, чтобы стадия и описание узла не разъехались.
REMOVE_ORDER: Tuple[str, ...] = SCHEDULED_JOBS_REMOVE_ORDER

# Колонки индекса состава, которые нужны разбору вида: `name`/`object_name` — ключ сверки
# (`ScheduledJob.<Имя>` и `ScheduledJob.<Имя>.Schedule`), `uuid` — сверка uuid файла с
# записью перечня, `child_type` — различение ноги содержимого, `depth`/`parent_name` —
# состояние «запись индекса имеет глубину» (иерархии раскладки у вида нет, замер 1.2).
# Своего вида здесь нет намеренно: отбор круга делает разбор (`kind_root_index_rows`,
# `kind_child_index_rows`). Тот же приём, что `INDEX_ROW_COLUMNS`/`read_index_records`
# узлов V46, V48, V49, V50, V52, V53: источник — строки БД, а не повторный разбор
# `ConfigDumpInfo.xml`.
INDEX_ROW_COLUMNS: Tuple[str, ...] = (
    "name", "object_id", "object_type", "object_name", "child_type", "parent_name", "depth",
    "uuid",
)

# Ключи сводки разбора, совпадающие с ключами контракта по имени (один словарь на разбор и
# на ответ): копируются только они — неперечисленный ключ контракта читается нулём (C1), а
# незнакомый ключ разбора не попадает в ответ, которого карточка не обещала (прецедент
# `SUMMARY_KEYS` узлов V46/V48/V49/V50/V52/V53). Ключей `rows` и `schedule_rows` здесь нет:
# строки записи идут в писатели, а не в ответ стадии; `success` и `errors` разбора —
# внутренние признаки круга, стадия отвечает своими `success`, `status` и `errors`. Ключей
# `index_available`, `index_kind_records`, `index_child_records`, `common_modules_available`,
# `module_texts_available` здесь тоже нет: их берёт ЧТЕНИЕ БД стадией, а не разбор — разбор
# видел только переданные ему строки, а ответ обязан описывать, чем именно его разрешили.
# Агрегаты, которых разбор не даёт (`methods_total`, `methods_distinct`,
# `method_modules_distinct`, `schedule_jobs_distinct`, `counts_by_observation`,
# `counts_by_circle_discrepancy`, `counts_by_content_discrepancy`), считает стадия по
# ЗАПИСАННЫМ строкам: ответ обязан описывать содержимое базы, а не круг выгрузки (тот же
# приём, что `separation_summary` узла V50).
SUMMARY_KEYS: Tuple[str, ...] = (
    "directory", "files_found", "files_read", "files_failed", "observations",
    "index_only", "file_only", "uuid_mismatch", "index_child_unexpected", "duplicate_names",
    "schedule_index_only", "schedule_file_only", "schedule_uuid_mismatch",
    "counts_by_properties_state", "counts_by_property_presence", "counts_by_value_form",
    "unknown_properties",
    "counts_by_method_state", "counts_by_method_declared_state",
    "methods_unresolved_total", "methods_unresolved",
    "methods_not_declared_total", "methods_not_declared",
    "counts_by_schedule_state", "counts_by_schedule_file_state",
    "schedules_total", "root_records_total", "detailed_records_total",
    "files_with_schedule", "files_without_schedule", "files_with_detailed",
    "max_detailed_per_record", "max_depth_seen", "day_times_total",
    "counts_by_record_kind", "counts_by_attribute_state", "attribute_states_by_name",
    "counts_by_week_days_state", "counts_by_months_state",
)


def read_index_records(cur, configuration_id: int) -> Dict[str, Any]:
    """Записи индекса состава этой конфигурации из `configuration_objects` (Н6).

    Пустой ответ означает «индекс недоступен», а не «объектов нет»: при недоступном индексе
    сверка файлов регистрации и файлов содержимого с перечнем невыразима, и вызывающий обязан
    назвать это состоянием загрузки, а не нулями (тот же контракт, что у слоёв V46, V47, V48,
    V49, V50, V52, V53).

    Своего вида считаются ДВА числа: `kind_count` — записи вида (`ScheduledJob.<Имя>`) и
    `child_count` — записи содержимого (`ScheduledJob.<Имя>.Schedule`). У вида есть
    содержимое (303 файла `Ext/Schedule.xml` из 346, замер 1.2), и вторая нога сверяется
    отдельно: расхождение `schedule_file_only` (файл есть, записи индекса нет) дают 43
    задания без расписания (замер 1.3) — одна цифра скрыла бы, что ноги расходятся.
    """
    info: Dict[str, Any] = {"available": False, "row_count": 0, "kind_count": 0,
                            "child_count": 0, "reason": None}
    columns = ", ".join(INDEX_ROW_COLUMNS)
    try:
        cur.execute(
            f"SELECT {columns} FROM {OBJECTS_TABLE} WHERE configuration_id = %s",
            [int(configuration_id)],
        )
    except Exception as exc:  # noqa: BLE001 — слой обязан назвать причину, а не ноль
        info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"
        return {"rows": [], **info}
    records = [dict(zip(INDEX_ROW_COLUMNS, row)) for row in cur.fetchall()]
    if not records:
        info["reason"] = (
            f"в {OBJECTS_TABLE} нет записей для configuration_id={configuration_id}: индекс "
            "состава этого заголовка не загружен, поэтому сверка файлов регистрации и файлов "
            "содержимого с перечнем невозможна"
        )
        return {"rows": [], **info}
    info.update({
        "available": True,
        "row_count": len(records),
        "kind_count": len(kind_root_index_rows(records)),
        "child_count": len(kind_child_index_rows(records)),
    })
    return {"rows": records, **info}


def read_common_module_names(cur, configuration_uuid: str) -> Dict[str, Any]:
    """Имена общих модулей ТЕКУЩЕЙ ревизии этой конфигурации (Q3 — разрешение обработчика).

    Источник — витрина `v_current_common_modules` (её строки пишет узел V46): разрешать по
    всей таблице `common_modules` нельзя, потому что в ней лежат и снятые ревизии, и
    обработчик получил бы `exact` по модулю, которого в текущем состоянии нет.

    Пустой ответ означает «перечень недоступен» (свойства общих модулей этой конфигурации не
    загружены), а не «общих модулей нет»: при недоступном перечне все обработчики остаются
    `unresolved`, и стадия обязана назвать причину предупреждением — «модуля нет» и «нечем
    разрешить» являются разными ответами (правило C2). Внешнего ключа на `common_modules` в
    схеме нет (Q3, вариант A), поэтому согласование держится этим чтением, а не ссылкой в
    структуре схемы.
    """
    info: Dict[str, Any] = {"available": False, "count": 0, "reason": None}
    try:
        cur.execute(
            f"SELECT object_name FROM {COMMON_MODULES_VIEW} "
            "WHERE configuration_uuid = %s::uuid",
            [str(configuration_uuid)],
        )
    except Exception as exc:  # noqa: BLE001 — перечень читается до записи, отказ называется
        info["reason"] = f"чтение {COMMON_MODULES_VIEW} не удалось: {exc}"
        return {"names": set(), **info}
    names = {str(row[0]).strip() for row in cur.fetchall() if row[0]}
    if not names:
        info["reason"] = (
            f"в {COMMON_MODULES_VIEW} нет общих модулей для configuration_uuid="
            f"{configuration_uuid}: свойства общих модулей этой конфигурации не загружены "
            "точкой входа load_configuration_object_properties_tool, поэтому разрешить "
            "обработчик нечем"
        )
        return {"names": set(), **info}
    info.update({"available": True, "count": len(names)})
    return {"names": names, **info}


def read_common_module_methods(cur, configuration_uuid: str) -> Dict[str, Any]:
    """Методы общих модулей ТЕКУЩЕЙ ревизии (Q8 — состояние объявления метода).

    Источник — витрина `v_current_bsl_modules` с `parent_type = 'common_modules'` (родителем
    строки текста является uuid самого общего модуля, решение D6/D-S4 узла V46). Имена методов
    выделяет РАЗБОР (`module_method_names`), а не этот слой: синтаксис объявления принадлежит
    разбору языка, и второе его написание в стадии разъехалось бы с первым.

    Три состояния различаются и называются, а не читаются нулями (правило C2):

    * строк модуля нет вовсе — «текстов общих модулей в базе не загружали» (живая база даёт
      именно это: замер 03.11.2026 — строк `bsl_modules` с этим `parent_type` ноль);
    * строка модуля есть, но `code` пуст (`bin_only`, `indexed_no_file`) — модуль в перечень
      методов НЕ попадает: сказать «метода нет» по незагруженному тексту было бы неправдой, и
      состояние объявления остаётся `text_unavailable` (Q8, вариант A);
    * текст есть — методы считаются, и отсутствие имени в перечне legitimately называется
      `not_declared`.

    Число модулей без текста возвращается отдельно (`without_text`): «текстов нет ни у чего» и
    «текстов нет у части модулей» — разные ответы, и предупреждение стадии обязано это
    различать.
    """
    info: Dict[str, Any] = {"available": False, "count": 0, "without_text": 0, "reason": None}
    try:
        cur.execute(
            f"SELECT module_name, code FROM {BSL_MODULES_VIEW} "
            "WHERE configuration_uuid = %s::uuid AND parent_type = %s",
            [str(configuration_uuid), COMMON_MODULE_PARENT_TYPE],
        )
    except Exception as exc:  # noqa: BLE001 — перечень читается до записи, тем же порядком
        info["reason"] = f"чтение {BSL_MODULES_VIEW} не удалось: {exc}"
        return {"methods": {}, **info}
    methods: Dict[str, set] = {}
    for module_name, code in cur.fetchall():
        name = str(module_name or "").strip()
        if not name:
            continue
        if not code:
            info["without_text"] += 1
            continue
        methods.setdefault(name, set()).update(module_method_names(str(code)))
    if not methods:
        info["reason"] = (
            f"в {BSL_MODULES_VIEW} нет текстов общих модулей для configuration_uuid="
            f"{configuration_uuid} (parent_type='{COMMON_MODULE_PARENT_TYPE}', строк без "
            f"текста: {info['without_text']}): тексты модулей узлом V46 не загружались "
            "(решение D-S4), поэтому объявить или опровергнуть метод нечем"
        )
        return {"methods": {}, **info}
    info.update({"available": True, "count": len(methods)})
    return {"methods": methods, **info}


def prepare_scheduled_jobs_rows(
        collected: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Строки `scheduled_jobs` из разбора — без колонок версионности (их добавляет писатель).

    Отличие от V53 названо прямо: переименовывать здесь нечего. Разбор даёт ключи строки
    теми же именами, что колонки таблицы (`method_name` несёт полный текст обработчика,
    `method_module`/`method_method` — разложение, `schedule_record_count` — посчитанное число
    записей), потому что словарь состояний и CHECK'и колонки задаёт схема, а разбор ей следует
    (Q3, Q4). Единственная правка — снять строку без идентификатора: `object_uuid` обязана
    быть NOT NULL, и писатель поднял бы `ValueError` внутри транзакции, где уже снят круг;
    стадия называет пропуск ответом, а не потерянной строкой.

    Порядок строк — порядок обхода разбора (по именам файлов регистрации): позиционного ключа
    у строки вида нет (одна строка на файл), а порядок нужен для предсказуемой выдачи
    `insert_ids` и, значит, для воспроизводимого ключа последующих ревизий.
    """
    rows: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for item in collected:
        row = dict(item)
        if not row.get("object_uuid"):
            skipped.append(
                f"{row.get('source_path') or row.get('object_name') or '<без имени>'}: в "
                "файле регистрации нет `<uuid>` — строка вида без идентификатора невозможна "
                "(NOT NULL), строки расписания к ней не привязать"
            )
            continue
        rows.append(row)
    return rows, skipped


def schedule_batches(
        schedules: List[Dict[str, Any]],
        job_ids: Dict[str, int],
) -> Tuple[List[List[Dict[str, Any]]], List[str]]:
    """Пакеты записей `scheduled_job_schedules` по возрастанию глубины — с `scheduled_job_id`.

    Возвращаются ПАКЕТЫ, а не один список, потому что числовой `parent_id` вложенной записи
    известен только после вставки родительской: вложенные записи вставляются вторым пакетом,
    после того как `insert_ids` вернул id корневых (прецедент двухфазной вставки `form_ext`
    узла V13 и детей узлов V51/V52). Внутри пакета порядок — порядок разбора, в котором
    родитель всегда идёт раньше потомка.

    `job_ids` — соответствие `object_name` → числовой id вставленной ревизии строки вида
    (Q2, вариант A: своей цепи ревизий у записи расписания нет). Ключом подстановки служит
    индексное имя задания — его несёт строка расписания в колонке `job_full_name` (тот же
    приём, что `subscription_full_name` V53, `criterion_full_name` V52,
    `attribute_full_name` V50). Отсутствующий id — отказ стадии ДО записи, а не строка с
    NULL: колонка `scheduled_job_id` объявлена NOT NULL, а запись расписания без задания
    описывает расписание, которого в выгрузке нет.

    Родителя вложенной записи (`ent:DetailedDailySchedules`) разбор адресует парой
    `parent_kind`/`parent_ordinal` внутри того же файла — uuid у записей расписания нет
    (замер 2.2), а композитная ссылка `scheduled_job_schedules_parent_same_job` держит
    связность парой (id записи, id строки задания), а не uuid. Числовой `parent_id` вызывающий
    подставляет перед вставкой пакета по уже вставленным записям предыдущих пакетов; здесь
    пакеты выстроены по возрастанию глубины: сначала корневые записи (глубина 1), затем
    вложенные (глубина 2 — глубже в четырёх выгрузках не бывает, замер 2.3). Порядок пакетов
    задаёт поле `depth`, а не порядок файлов: обратный порядок оставил бы родителя неизвестным
    в момент вставки.

    Ключ пакета и ключ родителя включают `file_path`, а не только имя задания: одна строка
    вида имеет не более одного файла содержимого, но ключ обязан различать случаи, когда
    файлов несколько (наблюдение `unexpected_schedule_file`) — иначе запись из чужого файла
    получила бы родителя из этого.
    """
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for record in schedules:
        groups.setdefault((str(record.get("job_full_name") or ""),
                           str(record.get("file_path") or "")), []).append(record)
    batches: List[List[Dict[str, Any]]] = []
    failures: List[str] = []
    for job_name, file_path in sorted(groups):
        job_id = job_ids.get(job_name)
        if job_id is None:
            failures.append(
                f"задание {job_name!r}: строка вида не была вставлена, поэтому её "
                f"расписаниям ({len(groups[(job_name, file_path)])} шт.) нечем заполнить "
                "`scheduled_job_id` — колонка объявлена NOT NULL, и запись половины круга "
                "невозможна"
            )
            continue
        by_depth: Dict[int, List[Dict[str, Any]]] = {}
        for record in groups[(job_name, file_path)]:
            by_depth.setdefault(int(record["depth"]), []).append(record)
        for depth in sorted(by_depth):
            batch: List[Dict[str, Any]] = []
            for record in by_depth[depth]:
                row = dict(record)
                row["scheduled_job_id"] = job_id
                batch.append(row)
            batches.append(batch)
    return batches, failures


def remove_scheduled_jobs(cur, configuration_uuid: str,
                         tables: Tuple[str, ...] = REMOVE_ORDER) -> Dict[str, int]:
    """Снять строки регламентных заданий этой конфигурации (внутри текущей транзакции).

    Очистка обязана быть явной: внешнего ключа на `configurations` и каскада по нему в схеме
    нет осознанно (прецеденты V20.1, V44, V46, V48, V49, V50, V51, V52, V53), иначе строки
    пережили бы снятие заголовка и стали бы сиротами, которые нельзя ни показать в карточке
    конфигурации, ни отличить от строк другой конфигурации. Этим же фильтром
    (`configuration_uuid`) держится снятие в `_remove_rows` конвейера — иначе `force=True`
    оставил бы в базе прежний состав вида (для BP3 это 24 строки задания и 164 записи
    расписания — замер 1.1).

    Порядок задаёт `REMOVE_ORDER`, а не `SCHEDULED_JOBS_TABLES`: записи расписания снимаются
    ДО строк вида, потому что их FK `scheduled_job_schedules_scheduled_job_id_fkey` объявлен с
    `ON DELETE CASCADE` — каскад по строке задания снял бы их молча, и число в ответе было бы
    неправдой (мера M7 узла V53). Запись расписания несёт `configuration_uuid` именно поэтому,
    чтобы снятие шло по одной ноге с таблицей вида, а не через связку с ней (тот же порядок,
    что `role_rights` V49, `common_attribute_targets` V50, `filter_criterion_content` V52,
    `event_subscription_sources` V53).
    """
    removed: Dict[str, int] = {}
    for table in tables:
        cur.execute(f"DELETE FROM {table} WHERE configuration_uuid = %s::uuid",
                    [str(configuration_uuid)])
        removed[table] = cur.rowcount
    return removed


def _require_header(configuration_uuid: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Найти строку заголовка по uuid; вернуть карточку или причину отказа.

    Заголовок обязателен: свойства вида — второй шаг того же первого слоя, и строки без
    заголовка нельзя ни показать в карточке конфигурации, ни снять вместе с ней (внешний ключ
    в схеме не поставлен осознанно — V20.1). Ленивый импорт — тот же обход цикла, что у слоёв
    V44/V46/V48/V49/V50/V52/V53.
    """
    from configuration_loader import find_configuration  # ленивый импорт — круг узла V44

    card = find_configuration(configuration_uuid)
    if isinstance(card, dict) and card.get("error"):
        return None, f"Ошибка запроса: {card['error']}"
    if not card:
        return None, (
            f"Строка заголовка конфигурации с uuid {configuration_uuid} в базе не найдена. "
            "Сначала загрузите каталог точкой входа load_1c_catalog_tool(source_path=…): "
            "иначе свойства регламентных заданий остались бы ни на что не указывающими, а "
            "внешний ключ в схеме не поставлен осознанно (узел V20.1)."
        )
    return card, None


def _stage_failure(reason: str, header: Optional[Dict] = None,
                   status: str = STATUS_ERROR,
                   extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Отказ стадии в форме закрытого контракта (C1, C3).

    Причина кладётся в ключ `error` замкнутого словаря `scheduled_jobs_defaults()`, а статус —
    в `status`: вызывающий отличает «стадия не выполнялась» от «слой отказал» (C2). Если
    заголовок к моменту отказа уже разрешён, он называется: по `configuration_id` карточка
    отличает «заголовка нет» от «заголовок есть, слой отказал по файлам». Подсказка о том, чем
    продолжить, кладётся и в отказ, и в успех: у стадии есть отдельный вход
    `load_scheduled_jobs_tool` (шаг П5), и вызывающий обязан знать это из ответа, а не из
    молчания.
    """
    result = scheduled_jobs_defaults()
    result.update({
        "status": status,
        "success": False,
        "error": reason,
        "reason": reason,
    })
    if header:
        result["configuration_id"] = header.get("id")
        result["configuration_uuid"] = header.get("uuid")
        result["configuration_name"] = header.get("name")
    warnings = list(extra or [])
    warnings.append(SCHEDULED_JOBS_REPEAT_HINT)
    result["warnings"] = warnings
    return result


def observation_counts(observations: List[Any]) -> Dict[str, int]:
    """Счётчик наблюдений круга по роду (`counts_by_observation` контракта).

    Пары `[род, подробности]` даёт разбор (`iter_registration_files` и
    `read_registration_file`); без счётчика «каталог отсутствует» и «в каталоге файл не того
    вида» различались бы только перечнем, а карточка обязана называть и число по каждому роду
    (C1). Пустой ответ означает «наблюдений нет» — это состояние, а не пропуск. Родов больше,
    чем у V53: у вида есть содержимое, и его раскладка сторожится наблюдениями
    `unexpected_schedule_file`, `schedule_dir_without_file`, `day_times_present` (граница
    узла, названная планом), а `index_depth` и `index_pseudo_entries` сторожат ногу
    индекса содержимого.
    """
    counts: Dict[str, int] = {}
    for item in observations or []:
        kind = str(item[0]) if isinstance(item, (list, tuple)) and item else "unknown"
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def circle_discrepancy_counts(index_only: List[Any], file_only: List[Any],
                              uuid_mismatch: List[Any]) -> Dict[str, int]:
    """Числа расхождений ноги вида по замкнутому словарю состояний (C1).

    Перечисленные списки дают примеры (`MAX_EXAMPLES` разбора), а число обязано быть полным:
    `*_total` отдельно от длины примеров — приём V48. Нули являются ответом: четыре
    замеренные выгрузки дают ноль по всем трём состояниям (замер 1.3), и молчать об этом
    значило бы не отличать «расхождений нет» от «сверку не делали». Словарь состояний
    берётся замкнутой константой разбора (`CIRCLE_DISCREPANCIES`), а не списком имён здесь:
    второе перечисление состояний в проекте разъезжается с первым.
    """
    listed = dict(zip(CIRCLE_DISCREPANCIES, (index_only, file_only, uuid_mismatch)))
    return {state: len(listed.get(state) or []) for state in CIRCLE_DISCREPANCIES}


def content_discrepancy_counts(schedule_index_only: List[Any], schedule_file_only: List[Any],
                               schedule_uuid_mismatch: List[Any]) -> Dict[str, int]:
    """Числа расхождений ноги содержимого (`Ext/Schedule.xml` ↔ запись `.Schedule`).

    Отличие от ноги вида названо планом (раздел 3): файл содержимого не является объектом
    метаданных и в перечень заголовка не входит, поэтому нога сверяется с индексом состава
    ДВУМЯ состояниями и отдельно от вида. Расхождение `schedule_file_only` — не ошибка
    выгрузки, а следствие того, что у 43 заданий расписания нет ни файлом, ни индексом
    (замер 1.3, состояние `absent` строки вида, M4); расхождение `schedule_index_only`
    означает обратное: запись `.Schedule` есть, а файла нет. Словарь состояний держится
    константой контракта (`SCHEDULED_JOB_CONTENT_DISCREPANCIES`), а не списком имён здесь.
    """
    listed = dict(zip(SCHEDULED_JOB_CONTENT_DISCREPANCIES,
                      (schedule_index_only, schedule_file_only, schedule_uuid_mismatch)))
    return {state: len(listed.get(state) or []) for state in SCHEDULED_JOB_CONTENT_DISCREPANCIES}


def method_summary(rows: List[Dict]) -> Dict[str, int]:
    """Число заполненных обработчиков, уникальные пары и уникальные модули по ЗАПИСАННЫМ строкам.

    Три числа держит ответ стадии, а не комментарий, потому что именно они являются основанием
    отсутствия внешнего ключа: связь обработчика не один-к-одному (замер 2.1 — 344 различные
    пары модуль+метод при 346 строках, Q3, вариант A). Строки с состояниями `absent`,
    `empty_value` и `unknown_form` в подсчёт не входят: значения у них нет (CHECK
    `scheduled_jobs_method_state_matches_value` держит это структурой строки), и «модуля нет»
    нельзя считать уникальным модулем. `method_modules_distinct` — отдельная мера: вопрос
    «сколько общих модулей вообще затронуто заданиями» читается колонкой `method_module`, а не
    разбором текста обработчика (мера V53).
    """
    pairs = set()
    modules = set()
    total = 0
    for row in rows:
        method = row.get("method_name")
        if not method:
            continue
        total += 1
        pairs.add(str(method))
        if row.get("method_module"):
            modules.add(str(row["method_module"]))
    return {"total": total, "distinct": len(pairs), "modules_distinct": len(modules)}


def schedule_summary(schedule_rows: List[Dict]) -> Dict[str, Any]:
    """Число заданий с записями расписания и максимум записей на задание по ЗАПИСАННЫМ строкам.

    `schedule_jobs_distinct` отвечает на вопрос, которого у разбора нет: сколько СТРОК вида
    получили расписание (303 из 346 — замер 1.1), тогда как `files_with_schedule` описывает круг
    выгрузки. Максимум записей на пару (задание, файл) сторожит обещание разбора: CHECK
    `scheduled_jobs_schedule_record_count_matches_state` согласовывает счётчик на строке вида с
    его состоянием, а число строк круга сверяет проверка П6 обходом выгрузки (замер 2.3 даёт
    максимум 3 записи в одном файле).
    """
    per_job: Dict[Tuple[str, str], int] = {}
    jobs = set()
    for row in schedule_rows:
        key = (str(row.get("job_full_name")), str(row.get("file_path")))
        per_job[key] = per_job.get(key, 0) + 1
        jobs.add(str(row.get("job_full_name")))
    return {
        "jobs_distinct": len(jobs),
        "max_records_per_job": max(per_job.values()) if per_job else 0,
        "per_job": per_job,
    }


def load_scheduled_jobs(source_path: str,
                        configuration_uuid: Optional[str] = None,
                        changed_at=None) -> Dict[str, Any]:
    """Загрузить свойства регламентных заданий конфигурации (узел V54, стадия S4i).

    Порядок: каталог → uuid из `Configuration.xml` (или сверка переданного) → проверка, что
    заголовок загружен → индекс состава из `configuration_objects` (сверка двух ног круга, Н6) →
    перечень общих модулей текущей ревизии (разрешение обработчика, Q3) → тексты общих модулей
    из витрины текущего состояния (состояние объявления метода, Q8) → разбор каталога вида →
    **одна транзакция**: `DELETE` по uuid + вставки строк вида и пакетов расписания →
    отдельной транзакцией `ANALYZE` (мера V46).

    Групп `kinds` у стадии нет (Q5, вариант A): запись расписания существует только через id
    строки вида (Q2, вариант A), поэтому частичная запись круга описывала бы состав, которого
    в выгрузке нет; порога цены, при котором круг стоило бы резать, замер 1.1/2.2 не дал.

    Отказ разбора любого файла круга останавливает стадию ДО записи: половина круга в базе
    читалась бы как полный состав вида (приём V12/V46/V48/V49/V50/V51/V52/V53). Отсутствие
    каталога `ScheduledJobs/` — не отказ, а ответ о выгрузке: `files_found = 0` с наблюдением
    `directory_missing`, потому что у конфигурации без регламентных заданий их действительно нет
    (KomMag даёт каталог без файлов — замер 1.1, и это тоже ответ о выгрузке, а не отказ).

    `changed_at` передаёт конвейер: строки одной загрузки обязаны нести одну метку (M2), а не
    время своей транзакции. Пустое значение — своя метка вызова (одиночный прогон слоя).
    Записи расписания метку не несут: колонок ревизии у таблицы нет
    (`CONFIGURATION_UNVERSIONED_TABLES`), их текущность читается витриной связкой по
    `scheduled_job_id` (Q2, вариант A).

    Порядок записи держится иерархией данных, а не удобством: сначала строки вида
    (`insert_ids`, `RETURNING id`), затем пакеты расписания по возрастанию глубины — сначала
    корневые записи, по id которых `schedule_batches` связывает родителей вложенных. Всё это
    одной транзакцией: отказ на середине оставил бы в базе задания без расписания, то есть
    состав, которого в выгрузке нет.
    """
    uuid_info = configuration_uuid_from_layout(source_path)
    if "uuid" not in uuid_info:
        return _stage_failure(uuid_info.get("error")
                             or f"Каталог выгрузки не читается: {source_path}")
    layout_uuid = str(uuid_info["uuid"])
    if configuration_uuid and str(configuration_uuid).strip().lower() != layout_uuid.lower():
        # Два источника одного факта указали на разные конфигурации: молча выбрать один —
        # значит записать свойства чужой конфигурации (тот же отказ, что у слоёв
        # V44/V46/V48/V49/V50/V52/V53).
        return _stage_failure(
            f"Передан configuration_uuid={configuration_uuid}, а каталог {source_path} "
            f"описывает конфигурацию с uuid={layout_uuid}. Загрузка не выполнена: укажите "
            "путь каталога этой конфигурации или уберите configuration_uuid."
        )
    configuration_uuid = layout_uuid

    header, reason = _require_header(configuration_uuid)
    if header is None:
        return _stage_failure(reason)

    warnings: List[str] = []
    index_info: Dict[str, Any] = {"available": False, "row_count": 0, "kind_count": 0,
                                  "child_count": 0, "reason": None, "rows": []}
    modules_info: Dict[str, Any] = {"available": False, "count": 0, "reason": None,
                                    "names": set()}
    texts_info: Dict[str, Any] = {"available": False, "count": 0, "without_text": 0,
                                    "reason": None, "methods": {}}
    # Три ноги чтения читаются отдельными транзакциями: отказ одной из них не обязан лишать
    # вторую уже прочитанного — стадия обязана назвать каждое состояние отдельно (C2).
    try:
        with transaction() as cur:
            index_info = read_index_records(cur, int(header["id"]))
    except Exception as exc:  # noqa: BLE001 — индекс читается до записи, отказ называется им
        index_info["reason"] = f"чтение {OBJECTS_TABLE} не удалось: {exc}"
    try:
        with transaction() as cur:
            modules_info = read_common_module_names(cur, configuration_uuid)
    except Exception as exc:  # noqa: BLE001 — перечень читается до записи, тем же порядком
        modules_info["reason"] = f"чтение {COMMON_MODULES_VIEW} не удалось: {exc}"
    try:
        with transaction() as cur:
            texts_info = read_common_module_methods(cur, configuration_uuid)
    except Exception as exc:  # noqa: BLE001 — тексты читаются до записи, тем же порядком
        texts_info["reason"] = f"чтение {BSL_MODULES_VIEW} не удалось: {exc}"

    collected = collect_scheduled_jobs(
        source_path,
        index_rows=index_info["rows"],
        common_module_names=modules_info["names"],
        common_module_methods=texts_info["methods"],
    )
    if not collected["success"]:
        failures = collected.get("files_failed") or []
        detail = "; ".join(f"{item.get('source_path')}: {item.get('reason')}"
                           for item in failures[:10])
        return _stage_failure(
            f"Круг не записан: {len(failures)} файл(ов) каталога "
            f"{collected.get('directory')} не разобраны — {detail}. Ни одной строки круга "
            "в базу не записано: половина круга читалась бы как полный состав вида (приём "
            "V12/V46), прежние строки этой конфигурации не сняты",
            header=header,
        )

    # Ключ конфигурации знает вызывающий, а не XML файла — тот же порядок, что у писателей
    # свойств V46, модулей корня V44, параметров сеанса V48, ролей V49, общих реквизитов V50,
    # критериев отбора V52 и подписок V53. Строки расписания получают тот же ключ: запись
    # обязана сниматься той же ногой, что таблица вида, а не через связку с ней (M7).
    job_rows = [dict(row, configuration_uuid=configuration_uuid)
                for row in (collected.get("rows") or [])]
    schedule_rows = [dict(row, configuration_uuid=configuration_uuid)
                     for row in (collected.get("schedule_rows") or [])]

    job_rows, unwritable = prepare_scheduled_jobs_rows(job_rows)
    if unwritable:
        return _stage_failure(
            f"Круг не записан: {len(unwritable)} файл(ов) регистрации не дают строки вида — "
            f"{'; '.join(unwritable[:5])}. Разбор обязан был отказать на таком файле "
            "(правило R3), поэтому это внутреннее противоречие разбора, а не состояние "
            "выгрузки; ни одна строка круга не записана",
            header=header,
        )

    # Связь строки расписания со строкой вида держится индексным именем задания — его несёт
    # колонка `job_full_name` (прецедент `subscription_full_name` V53, `criterion_full_name`
    # V52, `attribute_full_name` V50); иерархии раскладки у вида нет, поэтому имя совпадает с
    # `object_name` (замер 1.2). Проверка связности выполняется ДО транзакции: вставка
    # половины круга назвала бы полный состав, а половина получилась бы из внутренней
    # несвязности разбора, а не из состояния выгрузки.
    link_keys = [str(row.get("object_name") or "") for row in job_rows]
    known = set(link_keys)
    if len(known) != len(link_keys):
        duplicated = sorted({key for key in link_keys if link_keys.count(key) > 1})
        return _stage_failure(
            f"Круг не записан: разбор дал {len(link_keys)} строк задания с "
            f"повторяющимися именами ({', '.join(duplicated[:5])}) — записи расписания "
            "нельзя связать однозначно (замер 1.3 даёт уникальность имён внутри выгрузки), "
            "ни одна строка круга не записана",
            header=header,
        )
    unbound = sorted({str(row.get("job_full_name")) for row in schedule_rows
                      if row.get("job_full_name") not in known})
    if unbound:
        return _stage_failure(
            f"Круг не записан: {len(unbound)} запись(ей) расписания остались без строки "
            f"задания ({', '.join(unbound[:5])}) — это внутреннее противоречие разбора, а не "
            "состояние выгрузки; ни одна строка круга не записана",
            header=header,
        )

    # Один штамп времени на всё событие загрузки (M2): версионируемая таблица одной загрузки
    # не должна нести две метки. Записи расписания метку не получают — колонок ревизии у них
    # нет (`CONFIGURATION_UNVERSIONED_TABLES`).
    moment = stamp_revision_rows(job_rows, revision_no=FIRST_REVISION,
                                 changed_by=CHANGED_BY_LOAD, changed_at=changed_at)

    removed: Dict[str, int] = {}
    written: Dict[str, int] = {table: 0 for table in SCHEDULED_JOBS_TABLES}
    try:
        with transaction() as cur:
            removed = remove_scheduled_jobs(cur, configuration_uuid)
            # Строки задания — по одной с RETURNING id: запись расписания ссылается на
            # ЧИСЛОВОЙ id этой ревизии (Q2, вариант A), а `insert_many` id не возвращает.
            # Порядок `insert_ids` совпадает с порядком `job_rows` — связь держится им, а не
            # угадыванием. Прецедент — `insert_ids` слоёв V49/V50/V52/V53.
            job_ids_list = SJ_WRITERS[JOBS_TABLE].insert_ids(cur, job_rows)
            if len(job_ids_list) != len(job_rows):
                raise RuntimeError(
                    f"писатель вернул {len(job_ids_list)} id для {len(job_rows)} строк "
                    f"таблицы {JOBS_TABLE} — связать записи расписания нечем"
                )
            written[JOBS_TABLE] = len(job_ids_list)
            job_ids = dict(zip(link_keys, job_ids_list))
            # Пакеты по возрастанию глубины: родителем вложенной записи может быть только
            # уже вставленная запись того же файла (композиция `parent_id` + `scheduled_job_id`
            # замкнута ссылкой `scheduled_job_schedules_parent_same_job`), поэтому числовые id
            # родителей собираются по ходу вставки, а не заранее.
            batches, unbound_now = schedule_batches(schedule_rows, job_ids)
            if unbound_now:
                raise RuntimeError("; ".join(unbound_now))
            inserted: Dict[Tuple[str, str, str, int], int] = {}
            for batch in batches:
                for row in batch:
                    if row.get("parent_kind") is None:
                        row["parent_id"] = None
                        continue
                    parent_id = inserted.get(
                        (str(row["job_full_name"]), str(row["file_path"]),
                         str(row["parent_kind"]), int(row["parent_ordinal"])))
                    if parent_id is None:
                        raise RuntimeError(
                            f"{row['file_path']}: запись {row['kind']}#{row['ordinal']} "
                            f"(глубина {row['depth']}) ссылается на родителя "
                            f"{row['parent_kind']}#{row['parent_ordinal']}, числовой id "
                            "которого не получен: родителем может быть только запись того же "
                            "файла, вставленная до потомка"
                        )
                    row["parent_id"] = parent_id
                schedule_ids = SJ_WRITERS[SCHEDULES_TABLE].insert_ids(cur, batch)
                if len(schedule_ids) != len(batch):
                    raise RuntimeError(
                        f"писатель вернул {len(schedule_ids)} id для {len(batch)} записей "
                        f"таблицы {SCHEDULES_TABLE} — связать вложенные записи нечем"
                    )
                written[SCHEDULES_TABLE] += len(schedule_ids)
                for row, record_id in zip(batch, schedule_ids):
                    inserted[(str(row["job_full_name"]), str(row["file_path"]),
                              str(row["kind"]), int(row["ordinal"]))] = int(record_id)
    except Exception as exc:  # noqa: BLE001 — заголовок уже разрешён, отказ называется им
        return _stage_failure(
            f"Ошибка записи: {exc}. Транзакция отменена целиком: в базе остались прежние "
            f"строки круга (снятые этим вызовом — {sum(removed.values())}), новых нет",
            header=header,
        )

    # ── статистика записанных таблиц (мера V46) ─────────────────────────────────────────
    # Отдельная транзакция ПОСЛЕ фиксации записи: планировщик обязан увидеть строки, иначе
    # первый читатель витрин текущего состояния платит минутами за счётчик (замер V46 на
    # BGU2: 8 мин 25 с против 7 мс после ANALYZE). Отказ статистики отказом загрузки не
    # является: строки зафиксированы, и это называется предупреждением, а не молчанием.
    statistics_refreshed = 0
    try:
        with transaction() as cur:
            refresh_table_statistics(cur, SCHEDULED_JOBS_TABLES)
            statistics_refreshed = len(SCHEDULED_JOBS_TABLES)
    except Exception as exc:  # noqa: BLE001 — ответ описывает запись, а не статистику
        warnings.append(
            f"статистика таблиц {', '.join(SCHEDULED_JOBS_TABLES)} не обновлена: {exc}. "
            "Строки записаны, но читатель витрин текущего состояния получит план по пустой "
            "статистике: счётчики на большой выгрузке выполняются минутами вместо "
            "миллисекунд"
        )

    # ── ответ о круге ────────────────────────────────────────────────────────────────────
    # Ответ строится из контракта стадии (`scheduled_jobs_defaults`), сводки разбора
    # (только перечисленные ключи — `SUMMARY_KEYS`) и чисел, полученных при ЧТЕНИИ БД и при
    # записи: агрегатов, которых разбор дать не мог, стадия не прячет — они считаются по
    # ЗАПИСАННЫМ строкам, потому что ответ обязан описывать содержимое базы, а не круг
    # выгрузки (приём `separation_summary` V50, `events_summary` V53). Словари состояний
    # замкнуты контрактом, поэтому пустой словарь — состояние «записей нет», а не пропуск
    # блока (C1); Пустой ответ по позиции вида нулём не читается: `files_found = 0` с
    # наблюдением `directory_missing` является ответом о выгрузке (Q9).
    result = scheduled_jobs_defaults()
    for key in SUMMARY_KEYS:
        if key in collected:
            result[key] = collected[key]
    result.update({
        "status": STATUS_OK,
        "success": True,
        "configuration_id": header["id"],
        "configuration_uuid": configuration_uuid,
        "configuration_name": header.get("name"),
        "index_available": bool(index_info["available"]),
        "index_kind_records": int(index_info["kind_count"]),
        "index_child_records": int(index_info["child_count"]),
        "common_modules_available": bool(modules_info["available"]),
        "module_texts_available": bool(texts_info["available"]),
        "rows_written": int(sum(written.values())),
        "scheduled_jobs_written": int(written[JOBS_TABLE]),
        "schedule_records_written": int(written[SCHEDULES_TABLE]),
        "removed_previous": int(sum(removed.values())),
        "removed_by_table": removed,
        "written_by_table": written,
        "statistics_refreshed": statistics_refreshed,
    })

    result["counts_by_observation"] = observation_counts(result["observations"])
    result["counts_by_circle_discrepancy"] = circle_discrepancy_counts(
        result["index_only"], result["file_only"], result["uuid_mismatch"])
    result["counts_by_content_discrepancy"] = content_discrepancy_counts(
        result["schedule_index_only"], result["schedule_file_only"],
        result["schedule_uuid_mismatch"])
    methods = method_summary(job_rows)
    result["methods_total"] = methods["total"]
    result["methods_distinct"] = methods["distinct"]
    result["method_modules_distinct"] = methods["modules_distinct"]
    result["schedule_jobs_distinct"] = schedule_summary(schedule_rows)["jobs_distinct"]

    # Подсказка о том, чем продолжить, кладётся и в успех, и в отказ: у стадии есть
    # отдельный вход `load_scheduled_jobs_tool` (шаг П5), и вызывающий обязан знать это из
    # ответа, а не из молчания (прецедент COMMON_ATTRIBUTES_REPEAT_HINT V50,
    # EVENT_SUBSCRIPTIONS_REPEAT_HINT V53).
    warnings.append(SCHEDULED_JOBS_REPEAT_HINT)
    if not index_info["available"] and index_info.get("reason"):
        warnings.append(
            f"Индекс состава: {index_info['reason']} — состояния `index_only`, `file_only`, "
            f"`schedule_index_only` и `schedule_file_only` при этом невыразимы, а ссылки "
            "расписания остаются неразрешёнными записями (Q3): «объекта нет в перечне» от "
            "«перечень этой конфигурации не загружен» не отличить. Загружите конфигурацию "
            "точкой входа load_1c_catalog_tool(source_path=…) и повторите стадию"
        )
    if not modules_info["available"] and modules_info.get("reason"):
        warnings.append(
            f"Перечень общих модулей: {modules_info['reason']} — все {result['methods_total']} "
            "обработчиков остались в состоянии `unresolved`: это «нечем разрешить», а не "
            "«модуля нет в конфигурации» (правило C2). Загружите свойства общих модулей "
            "точкой входа load_configuration_object_properties_tool(source_path=…) и "
            "повторите стадию"
        )
    if not texts_info["available"] and texts_info.get("reason"):
        warnings.append(
            f"Перечень текстов модулей: {texts_info['reason']} — ни один метод не подтверждён "
            "текстом, все обработчики доступного модуля названы состоянием `text_unavailable`. "
            "Это граница слоя V46 (Q12): он хранит дескрипторы файлов модулей, а тексты "
            "читает отдельным вызовом с `with_module_content=True`. Состояние называется, а не "
            "читается как «метода нет»: метод существует, текста его в базе нет"
        )

    for observation, detail in (result["observations"] or []):
        if observation == "directory_missing":
            warnings.append(
                f"Каталог {result['directory']}/ в выгрузке отсутствует — регламентных заданий у "
                "этой конфигурации нет, и нули таблиц являются ответом о выгрузке, а не отказом "
                "стадии (замер 1.1 даёт именно такой вид выгрузки — Q9)"
            )
        elif observation in ("unexpected_dir", "unexpected_file"):
            warnings.append(
                f"Круг шире перечня вида: {observation} — {detail}. У задания нет детей, кроме "
                "расписания, поэтому объект вне перечня является наблюдением, а не строкой "
                "круга: колонок для него в схеме нет, и молчать о нём нельзя (M2)"
            )
        elif observation in ("index_child_entry", "index_depth"):
            warnings.append(
                f"Запись индекса состава содержимого: {observation} — {detail}. Нога `…."
                f"{SCHEDULE_CHILD_KIND}` сверяется отдельно (Н6): {len(result['schedule_index_only'])} "
                f"записей индекса без файла и {len(result['schedule_file_only'])} файлов без "
                "записи — одна цифра скрыла бы, что ноги расходятся"
            )
        elif observation == "child_objects_block":
            warnings.append(
                f"Блок <ChildObjects> непустой: {detail}. Замер 1.2 даёт пустой блок во всех "
                "346 файлах вида, поэтому дети этим узлом не читаются — наблюдение называется, "
                "а не обходится молчанием"
            )
        elif observation == "day_times_present":
            warnings.append(
                f"Есть записи <DayTimes>: {detail}. На четырёх измеренных выгрузках их ноль "
                "(замер 1.3: 7 записей на весь корпус), колонок и словарей под них в схеме нет — "
                "состояние `day_time` называется записью и остаётся открытым узлом (O1); "
                f"число записей — {result['day_times_total']}"
            )

    # Круги обязан сверять сам прогон: равенство ног является замером, а не предположением
    # (замер 1.3 даёт равенство файлов регистрации и записей вида на четырёх выгрузках).
    if index_info["available"] and int(result["index_kind_records"]) != int(
            result["files_found"]):
        warnings.append(
            f"Записей `ScheduledJob.<Имя>` в индексе состава {result['index_kind_records']}, "
            f"файлов регистрации {result['files_found']} — круги различаются (замер 1.3 даёт "
            "равенство на четырёх выгрузках, поэтому расхождение требует объяснения этим "
            "прогоном; расхождения перечислены ключами `index_only` / `file_only`)"
        )
    if index_info["available"] and int(result["index_child_records"]) != int(
            result["files_with_schedule"]):
        warnings.append(
            f"Записей `ScheduledJob.<Имя>.{SCHEDULE_CHILD_KIND}` в индексе состава "
            f"{result['index_child_records']}, файлов `Ext/{SCHEDULE_FILE_NAME}` "
            f"{result['files_with_schedule']} — ноги содержимого расходятся (замер 1.3 даёт "
            "равенство 303 = 303 на BGU2/BP3 и ноль на MinCfg/KomMag; расхождения перечислены "
            "ключами `schedule_index_only` / `schedule_file_only`)"
        )
    if int(result["scheduled_jobs_written"]) != int(result["files_read"]):
        warnings.append(
            f"Разбор прочитал {result['files_read']} файла регистрации, записано строк задания "
            f"{result['scheduled_jobs_written']} — часть строк в {JOBS_TABLE} не попала; связь "
            "расписания держится числовым id ревизии (Q2 вариант A), и молчать об этом нельзя"
        )
    if int(result["schedule_records_written"]) != int(result["schedules_total"]):
        warnings.append(
            f"Разбор дал {result['schedules_total']} записей расписания, записано "
            f"{result['schedule_records_written']} — часть записей в {SCHEDULES_TABLE} не "
            "попала; CHECK scheduled_jobs_schedule_count_matches_state сверяет счётчик на строке "
            "задания с числом её записей, и расхождение обязан назвать прогон"
        )
    if int(result["methods_unresolved_total"] or 0) and modules_info["available"]:
        warnings.append(
            f"{result['methods_unresolved_total']} обработчик(ов) названы `unresolved` при "
            "доступном перечне модулей — форма значения корректна, но общего модуля нет среди "
            "модулей ТЕКУЩЕЙ ревизии этой конфигурации (замер 1.3 даёт ноль таких случаев, "
            "поэтому расхождение требует объяснения этим прогоном); примеры — ключ "
            "`methods_unresolved`"
        )
    if int(result["methods_not_declared_total"] or 0):
        warnings.append(
            f"{result['methods_not_declared_total']} обработчик(ов) названы `not_declared`: "
            "модуль доступен, метода в его тексте нет (замер 1.3 даёт 3 таких случая на BP3 — "
            "пример `МодульОтчета.ТестМетодаИзВнешнегоОтчета`). Значение остаётся записанным "
            "как в выгрузке, потому что отсутствующий метод является состоянием выгрузки, а не "
            "ошибкой разбора (Q11); примеры — ключ `methods_not_declared`"
        )
    if result["duplicate_names"]:
        warnings.append(
            f"{len(result['duplicate_names'])} имя задания встречается в выгрузке более раза — "
            "ключ цепочки (configuration_uuid, object_name, revision_no) принял бы вторую "
            "строку новой ревизией, и стадия называет это отдельно (замер 1.3 даёт "
            "уникальность имён внутри выгрузки)"
        )
    if any(removed.values()):
        warnings.append(
            "Прежние строки плана сеанса этой конфигурации сняты перед записью: "
            f"{', '.join(f'{table}={count}' for table, count in removed.items())}. "
            "Идемпотентность держится явным DELETE по configuration_uuid в порядке "
            f"{list(SCHEDULED_JOBS_REMOVE_ORDER)}: внешнего ключа и каскада по конфигурации в "
            "схеме нет осознанно (прецедент V20.1), а каскад по строке задания снял бы записи "
            "расписания молча и число в ответе было бы неправдой (M7). Новая ревизия на "
            "повторную загрузку той же выгрузки не заводится — история состояний принадлежит "
            "узлу правки объекта, которого в схеме ещё нет")
    if job_rows:
        warnings.append(
            f"Момент загрузки строк задания — {moment}: той же меткой помечены строки "
            "заголовка и других стадий этого события (M2); записи расписания метку не несут "
            "(своей цепи ревизий у них нет, Q2 вариант A), их текущность читается витриной "
            f"`v_current_{SCHEDULES_TABLE}` связкой по числовому id строки задания")
    else:
        warnings.append(
            "Строк задания этим вызовом не записано: каталог вида пуст или отсутствует "
            f"(файлов {result['files_found']}), поэтому и общего момента загрузки вида у этого "
            "события нет — нули таблиц являются ответом о выгрузке")
    for text in (collected.get("warnings") or [])[:10]:
        warnings.append(f"разбор: {text}")
    result["warnings"] = warnings
    return result














