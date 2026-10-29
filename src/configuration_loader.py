#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузчик заголовка конфигурации и индекса её состава (узлы V32, V33).

Граница узла (FLOWCHART_1c-configurations-core.md, правило R7 +
.clinerules/1c-configurations-core_Rule.md, позиции V32/V33):

  * реализуется ровно R1-переход `configuration`: в корне каталога есть `Configuration.xml`
    → одна строка в `configurations`. Таблиц `configuration_child_*`/`config_languages`/
    `config_modules` в схеме нет (замер 17.10.2026, раздел 3.2) — узел V32 НЕ создаёт ни одной
    из этих таблиц и не обещает счётчики детей;
  * `force=True` снимает старую строку заголовка и пишет новую (обновления по uuid нет):
    id меняется, а `external_report.configuration_id` (внешнего ключа нет, узел V20.1)
    остаётся числом без строки заголовка. Это состояние `dangling`, и он обязан быть
    назван в ответе — иначе оператор теряет привязку молча;
  * коллизия `name` (UNIQUE живой схемы, узел V32) — отдельный статус `name_conflict`:
    `force=True` здесь не предлагается, потому что снятие чужой строки удалило бы
    другой заголовок;
  * провенанс строки конфигурации не ведётся (решение D-C по умолчанию, граница V31):
    путь источника в БД не пишется, и ответ прямо об этом говорит.

Узел V33 (17.10.2026): состав конфигурации перестаёт быть слепой зоной. Если в корне каталога
есть `ConfigDumpInfo.xml`, его индекс объектов (`src/config_dump_info_parser.py`) пишется в
таблицу `configuration_objects` — одна строка на запись индекса, `configuration_id` ссылается
на ТОЛЬКО что вставленный заголовок. Правила узла:

  * индекс — производные данные выгрузки, а не редактируемое состояние (M-правило узла V19 не
    задевается: версионности у этих строк нет, повторная загрузка снимает их и пишет заново);
  * разбор выполняется ДО транзакции: кривой `ConfigDumpInfo.xml` — отказ до первой записи,
    а не наполовину заполненная таблица (тот же порядок, что у разбора заголовка);
  * отсутствие файла — предупреждение, а не отказ: заголовок загружается, и ответ называет
    причину, по которой состава нет (внешние объекты индекса не имеют в принципе);
  * частично заполненный индекс — ложь: если таблица индексов в базе не создана, разбор не
    выполняется вовсе, а ответ требует применить `migrate_v33_configuration_objects.sql`.

Узел V43 (22.10.2026): строка заголовка начинает держать перечни имён объектов состава —
48 колонок `TEXT[]` (`catalogs_names` не входит: виды, чей состав уже описан нормализованно,
из контракта исключены). Правила K1–K6 (глубина 0, NULL вместо пустого массива, короткие
имена, порядок по полному точечному имени в байтовом порядке UTF-8) задаёт
`src/configuration_child_properties.py`; имена колонок и SQL бэкфилла генерируются из того же
словаря. Границы узла:

  * источник — ТОЛЬКО разобранный `ConfigDumpInfo.xml` (тот же объект, из которого пишутся
    строки `configuration_objects`): второго чтения файла нет, иначе заголовок описывал бы
    состав, которого в таблице индекса может не оказаться;
  * индекс не разобран (нет файла или нет таблицы индекса) → все 48 колонок читаются NULL, и
    это состояние загрузки, а не ответ о конфигурации; предупреждение называет это прямо;
  * содержимое объектов (реквизиты, формы, макеты, модули) узлом V43 не заполняется —
    перечень ≠ содержимое, модель групп A–H (узел V38) не реализована.

Узел V44 (22.10.2026, группа C): модули предопределённых программ корня — отдельный слой
и отдельная точка входа (`src/configuration_root_module_loader.py`,
`load_configuration_root_modules_tool`). Здесь, в загрузчике заголовка, у этого слоя ровно
две границы:

  * строки четырёх таблиц снимаются вместе с заголовком (`_remove_rows`): внешнего ключа и
    каскада в схеме нет осознанно, поэтому очистка обязана быть явной здесь же, где снимаются
    `configuration_objects` и `bsl_modules` (прецедент — п. 10 правил core); без этого после
    удаления заголовка строки модулей остались бы сиротами;
  * узел V45 (стадия S3): после коммита транзакции заголовка конвейер сам вызывает
    `configuration_root_module_loader.load_root_modules` — `force=True` больше не оставляет
    конфигурацию без модулей корня. Стадия идёт в СВОЕЙ транзакции (новая `transaction()`
    не увидела бы незакоммиченный заголовок в той же), ключ ответа — `root_modules`;
    отказ стадии не отменяет уже записанный заголовок, но карточка и ответ называют
    остановившую стадию прямо (аналог R13: отказ секции — не отказ загрузки).

Узел V47 (28.10.2026, слой 2 — модули объектов конфигурации): после стадии S4 конвейер
вызывает `configuration_object_modules_loader.load_object_modules` — тексты шести слотов
`Ext/` пишутся в `bsl_modules` (`parent_type = 'configuration_objects'`) ВТОРОЙ
транзакцией после фиксации содержимого конфигурации (решение Q6, граница D7 узла V46).
Правила узла (`docs/CONFIGURATION_OBJECT_MODULES_PLAN.md`):

  * флага просьбы нет (решение Q4): стадия выполняется в том же вызове всегда —
    конфигурация без модулей такая же битая, как без свойств, а разделение загрузки
    свойств и загрузки модулей означает риск ошибок и повторное чтение всей конфигурации;
  * атомом полноты является группа объектов. В отличие от S3/S4 отказ такой стадии
    загрузку останавливает: ответ помечается `load_incomplete`, незакрытая группа
    называется прямо (`incomplete_groups`), а уже зафиксированные S1–S4 остаются
    зафиксированными — смысл границы D7 этим не отменяется (критерий 8 плана);
  * отдельного инструмента и дозагрузки нет (решение Q4.1): правило оператора — «ошибка
    загрузки влечёт перезагрузку всей конфигурации», предупреждение требует
    `load_1c_catalog_tool(source_path=…, force=True)`;
  * индекс состава не разобран → стадия снимается в `not_run` (правило C2): круг модулей
    задают записи `configuration_objects`, а их нет — нули читались бы как «модулей нет»;
  * строки круга узла снимаются вместе с заголовком тем же `DELETE` по
    `configuration_uuid` с явной границей по `parent_type` (раздел 10 плана), отдельной
    ветки в `_remove_rows` для них нет;
  * обогащение (S5) загрузчик не вызывает — отдельный вызов (позиция оператора
    28.10.2026), в `STAGES` этой стадии нет.

Узел V48 (29.10.2026, позиция 2.3 нормативного списка — свойства параметров сеанса): между
стадиями S4 и S4b конвейер вызывает
`configuration_session_parameters_loader.load_session_parameters` — свойства вида
`SessionParameters` пишутся в таблицу `session_parameters` своей транзакцией. Правила узла
(`docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md`):

  * стадия отдельная, а не третий вид S4 (решение Q5): ответ лежит в собственном ключе
    `session_parameters`, а не внутри `child_objects` (правило C3), порядок `STAGES`
    повторяет порядок нормативного списка (2.3 идёт сразу за 2.1–2.2);
  * отказ стадии, как у S3/S4, записанный заголовок и индекс состава не отменяет (C5) и
    называется предупреждением: остановка конвейера по первой ошибке (решение Q8, вариант A)
    является шагом П8 того же узла;
  * круг пишется одной транзакцией и только целиком: неразобранный файл круга останавливает
    стадию ДО записи, чтобы половина круга не читалась как полный состав вида (приём V12/V46);
  * строки вида снимаются вместе с заголовком явным `DELETE` по `configuration_uuid`
    (`remove_session_parameters` в `_remove_rows`): внешнего ключа и каскада в схеме нет
    осознанно (прецедент V20.1);
  * отдельная точка входа группы есть — `load_session_parameters_tool` того же слоя (шаг П5
    того же узла): повтор стадии не требует пересоздания конфигурации `force=True`.



Чтения идут через psycopg2 (`src/external_db.py`), а не psql-подпроцессом: `_run_psql` /
`_psql_fields` унаследованы от прежнего загрузчика, многоколоночные выборки разбирают
текст по '|', а URL и комментарий конфигурации — как раз значения с '|'.
"""
import re
from datetime import datetime
from pathlib import Path

import psycopg2.extras

from config_dump_info_parser import find_config_dump_info, parse_config_dump_info
# Узел V43: правила перечней имён объектов состава (K1–K6) задаёт один модуль —
# src/configuration_child_properties.py. Загрузчик не имеет права придумывать свой фильтр
# глубины, своё имя колонки или свою сортировку: тот же контракт читает бэкфилл
# `migrate_v43_configuration_child_arrays.sql`, и расхождение двух реализаций
# выглядело бы как два разных ответа об одном и том же составе.
from configuration_child_properties import collect_header_arrays, header_array_columns
from configuration_meta_parser import parse_configuration_meta
# Узел V44: строки модулей предопределённых программ корня снимаются вместе с заголовком.
# Внешнего ключа и каскада в схеме нет осознанно (прецедент V20.1), поэтому очистка обязана
# быть явной здесь же, где снимаются `configuration_objects` и `bsl_modules`. Список четырёх
# таблиц задаёт один модуль-словарь (src/configuration_root_modules.py) — загрузчик не имеет
# права держать свой перечень, иначе снятие и загрузка назвали бы разные таблицы.
from configuration_root_modules import TABLES as ROOT_MODULE_TABLES
from configuration_root_module_loader import load_root_modules, remove_root_modules
# Узел V46 (стадия S4): свойства подсистем и общих модулей. Точка входа одна — тот же
# слой, что отдельный инструмент `load_configuration_object_properties_tool`; контракт и
# форматёр текста тоже общие (прецедент V45: карточка и инструмент описывают слой одинаково).
from configuration_object_properties_loader import (
    load_object_properties,
    remove_object_properties,
)
# Узел V48 (стадия S4c, позиция 2.3 списка): свойства параметров сеанса. Точка входа одна —
# тот же слой, что и отдельный инструмент `load_session_parameters_tool` (шаг П5); контракт
# стадии и форматёр текста общие
# (прецедент V45/V46). Снятие строк по uuid заголовка держит этот же слой: внешнего ключа и
# каскада в схеме нет осознанно (прецедент V20.1), поэтому `_remove_rows` обязан вызвать его
# явно — иначе force=True оставил бы в базе прежний состав вида.
from configuration_session_parameters_loader import (
    load_session_parameters,
    remove_session_parameters,
)
# Узел V47 (стадия S4b): модули объектов конфигурации — вторая транзакция после фиксации
# содержимого (Q6, граница D7). Точка входа стадии одна и отдельного инструмента у неё нет
# (Q4.1), поэтому здесь импортируется и ответ «стадия не выполнялась» (`mark_index_unavailable`):
# право снять стадию в `not_run` имеет только загрузчик — он знает, разбирался ли в этом
# вызове `ConfigDumpInfo.xml`.
from configuration_object_modules_loader import (
    load_object_modules,
    mark_index_unavailable,
    object_modules_defaults,
)
from configuration_load_contract import (
    CHILD_OBJECTS_REPEAT_HINT,
    CHILD_SECTION_HEADER,
    NOT_RUN_STOPPED_REASON,
    OBJECT_MODULES_SECTION_HEADER,
    ROOT_MODULES_REPEAT_HINT,
    ROOT_MODULES_SECTION_HEADER,
    SESSION_PARAMETERS_REPEAT_HINT,
    SESSION_PARAMETERS_SECTION_HEADER,
    SESSION_PARAMETER_TABLE,
    STAGE_CHILD_OBJECTS,
    STAGE_INCOMPLETE_GROUPS,
    STAGE_OBJECT_MODULES,
    STAGE_ROOT_MODULES,
    STAGE_SESSION_PARAMETERS,
    STATUS_ERROR,
    STATUS_NOT_RUN,
    build_stopped_stage,
    child_objects_defaults,
    root_modules_defaults,
    session_parameters_defaults,
    stage_title,
    stopped_stage_defaults,
)
from external_db import connect, transaction
# Узел V19, закрытие S2 (18.10.2026): счётчики и перечень внешних объектов читаются из
# витрин текущего состояния. С историей `COUNT(*) FROM external_report WHERE
# configuration_id = c.id` посчитал бы все состояния каждого объекта, а не число
# привязанных объектов; `bsl_modules` версионируется той же цепочкой, что и содержимое
# внешнего объекта (модули конфигурации — parent_uuid IS NULL, витрина отдаёт их как есть).
from current_revision import current_view
from external_table_writer import ConfigurationObjectRowWriter, ConfigurationRowWriter

TABLE = "configurations"
OBJECTS_TABLE = "configuration_objects"
VARIANT_TITLE = "конфигурация"
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")

# Граница провенанса (D-C по умолчанию): ответ обязан сказать её сам, а не молчать.
PROVENANCE_BOUNDARY = (
    "Провенанс строки конфигурации не ведётся: колонок origin_* в таблицах конфигурации нет "
    "(решение D-C по умолчанию, граница узла V31) — путь источника в БД не записан, поэтому "
    "по данным базы нельзя подтвердить, что повторная загрузка идёт тем же каталогом."
)

CARD_SQL = """
SELECT c.id, c.uuid::text AS uuid, c.name, c.synonym, c.version, c.vendor_name,
       c.main_mode, c.usage_purpose, c.embedded_language, c.default_language,
       c.compatibility_mode, c.modality_mode, c.ext_comp_sync_mode,
       c.interface_compat_mode, c.help_included,
       COALESCE(array_length(c.main_roles, 1), 0) AS main_roles_count,
       to_char(c.created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
       (SELECT COUNT(*) FROM """ + current_view("external_report") + """ e
         WHERE e.configuration_id = c.id) AS bound_external_objects,
       (SELECT COUNT(*) FROM """ + current_view("bsl_modules") + """ b
         WHERE b.configuration_uuid = c.uuid) AS bsl_modules_count,
       (SELECT COUNT(*) FROM config_extensions x
         WHERE x.configuration_id = c.id) AS extensions_count
FROM configurations c
"""


def _read_rows(sql, params=None):
    """Одна выборка через psycopg2: список dict либо {"error": ...}.

    Отличать отказ от пустого результата важно: «строк нет» — это состояние базы,
    «запрос упал» — состояние инструмента (то же правило, что у `_psql_fields`).
    """
    conn = None
    try:
        conn = connect()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, tuple(params or ()))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.commit()
        return rows
    except Exception as exc:
        try:
            if conn is not None:
                conn.rollback()
        except Exception:
            pass
        return {"error": f"SQL error: {exc}"}
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def _row_card(row):
    """Карточка строки заголовка (её печатает и карточка дубликата, и тест узла V32)."""
    card = dict(row)
    card["row_kind"] = "configuration"
    card["table"] = TABLE
    card["variant_title"] = VARIANT_TITLE
    card["provenance_state"] = "not_maintained"
    # узел V33: карточка заголовка обязана отвечать и на вопрос «её состав в базе есть
    # или нет» — иначе дубликат выглядит целым при пустой таблице индекса.
    card["configuration_objects"] = _objects_counts(card["id"])
    return card


def _table_present(cur, table):
    """Есть ли таблица в схеме (узел V33).

    Вопрос задаётся до работы с ней: парсить 122 000 записей индекса, чтобы упасть на
    несозданной таблице, — значит потратить минуту ради отказа.
    """
    cur.execute("SELECT to_regclass('public.%s') IS NOT NULL" % str(table))
    record = cur.fetchone()
    return bool(record and record[0])


def _objects_counts(configuration_id):
    """Счётчики индекса состава по строке заголовка (узел V33).

    «Индекса нет» и «индекс пустой» — разные факты, поэтому отказ запроса возвращается
    отдельной записью с причиной, а не нулями: нули в карточке читались бы как «состава
    нет в выгрузке».

    Числа «объектов» и «дочерних» держатся раздельно намеренно: сумма записей индекса
    BGU2 — 122 313 при 35 934 объектах (замер 17.10.2026,
    tools/_v33_probe_configdumpinfo.py); одно общее число читалось бы как «объектов
    122 тысячи».
    """
    rows = _read_rows(
        "SELECT COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE depth = 0) AS objects, "
        "COUNT(*) FILTER (WHERE depth > 0) AS children "
        f"FROM {OBJECTS_TABLE} WHERE configuration_id = %s",
        [int(configuration_id)],
    )
    if isinstance(rows, dict):
        error = str(rows.get("error", ""))
        reason = (
            f"таблицы индекса состава ({OBJECTS_TABLE}) в базе нет — "
            "примените migrate_v33_configuration_objects.sql"
            if OBJECTS_TABLE in error else error
        )
        return {"available": False, "reason": reason}
    record = rows[0]
    return {"available": True, "total": int(record["total"]),
            "objects": int(record["objects"]), "children": int(record["children"])}


def find_configuration_xml(source_dir):
    """Найти `Configuration.xml` в корне каталога выгрузки (правило R1, без рекурсии)."""
    root = Path(source_dir)
    if not root.exists() or not root.is_dir():
        return None
    for name in ("Configuration.xml", "configuration.xml"):
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None



def find_configuration(uuid_val=None):
    """Найти строку заголовка по uuid метаданных конфигурации.

    Возвращает карточку, None (строк нет — это состояние базы) или {"error": ...}
    (отказ запроса — состояние инструмента). `uuid` в `configurations` НЕ уникален
    (уникален `name`), поэтому при нескольких строках отдаётся первая по id, а их число
    и id видны в карточке: молчать о дубле заголовка нельзя.
    """
    if not uuid_val or not UUID_RE.match(str(uuid_val)):
        return None
    rows = _read_rows(CARD_SQL + "WHERE c.uuid = %s::uuid ORDER BY c.id", [str(uuid_val)])
    if isinstance(rows, dict):
        return rows
    if not rows:
        return None
    card = _row_card(rows[0])
    if len(rows) > 1:
        card["duplicate_rows"] = len(rows)
        card["duplicate_ids"] = [row["id"] for row in rows]
    return card


def find_configuration_by_name(name, exclude_id=None):
    """Найти строку заголовка с тем же `name` (UNIQUE живой схемы, узел V32)."""
    if not name:
        return None
    sql = CARD_SQL + "WHERE c.name = %s"
    params = [name]
    if exclude_id is not None:
        sql += " AND c.id <> %s"
        params.append(int(exclude_id))
    rows = _read_rows(sql, params)
    if isinstance(rows, dict):
        return rows
    return _row_card(rows[0]) if rows else None


def bound_external_objects(cfg_id):
    """Внешние объекты, привязанные к этому заголовку (после снятия строки — битые)."""
    rows = _read_rows(
        "SELECT id, name, uuid::text AS uuid FROM " + current_view("external_report") + " "
        "WHERE configuration_id = %s ORDER BY id",
        [int(cfg_id)],
    )
    return [] if isinstance(rows, dict) else rows


def _remove_rows(cur, cfg_id, configuration_uuid=None):
    """Снять строку заголовка и связанные строки ВНУТРИ текущей транзакции.

    Каскада нет: FK `config_extensions.configuration_id` и
    `configuration_objects.configuration_id` объявлены без `ON DELETE` (шаг 2 установки),
    `external_report.configuration_id` — ссылка без FK вовсе (узел V20.1). С узла V46 (П2)
    FK нет и у `bsl_modules`: числовой `configuration_id` снят, строки модулей адресуются
    uuid заголовка (тот же ключ, что у таблиц модулей предопределённых программ корня,
    узел V44). Поэтому индекс, расширения и модули снимаются явным `DELETE` (для первых
    двух иначе удаление падает на FK), а привязки внешних объектов остаются числами.

    Узел V33: строки индекса состава (`configuration_objects`) ссылаются на заголовок FK
    без `ON DELETE` (шаг 2 установки, тот же порядок, что у расширений и модулей), поэтому
    без явного `DELETE` здесь же `force=True` и `delete_configuration` падают с
    `configuration_objects_configuration_id_fkey` — при 122 000 строк это означало бы, что
    конфигурацию нельзя ни перезагрузить, ни снять.

    Узел V44 (группа C): таблицы модулей предопределённых программ корня адресуются
    **uuid заголовка**, а не его id, и внешнего ключа на `configurations` в схеме нет
    осознанно (тот же контракт, что V20.1 у привязок, — ключ блокировал бы пересоздание
    строки заголовка). Значит снятие обязан выполнить этот же явный DELETE: без него
    строки пережили бы снятие заголовка и остались бы в базе сиротами без ссылки — ровно
    тот дефект, который у `bsl_modules` лечится п. 10 правил core. Число снятых строк
    возвращается в `children` под именами самих таблиц, потому что вызывающий обязан
    назвать оператору полное состояние, снятое `force=True` (M7), а не только индекс.
    `configuration_uuid` пуст только у строки заголовка без uuid: вызывающий, а не этот
    код, обязан назвать такое состояние, потому что по отсутствующим ключам в `children`
    нельзя решить, что ничего не снималось.

    Функция принимает курсор, а не открывает свою транзакцию, намеренно: `force=True`
    обязан выполняться одной транзакцией со вставкой новой строки, иначе неудачная вставка
    оставила бы конфигурацию снятой без замены.
    """
    children = {}
    # Таблицы индекса может не быть в базе, где миграцию V33 не применяли: снимать нечего,
    # и отказывать загрузке заголовка из-за этого нельзя (заголовок — узел V32).
    tables = [OBJECTS_TABLE] if _table_present(cur, OBJECTS_TABLE) else []
    tables += ["config_extensions"]
    for table in tables:
        cur.execute(f"DELETE FROM {table} WHERE configuration_id = %s", [cfg_id])
        children[table] = cur.rowcount
    # Узел V46 (П2): `bsl_modules` больше не снимается по числовому id заголовка — строки
    # модулей адресуются его uuid (тот же ключ, что у таблиц модулей корня, узел V44),
    # поэтому и снятие идёт по uuid. Модули внешнего объекта (`parent_uuid IS NOT NULL`) к
    # конфигурации не относятся и сняты быть не должны. Пустой `configuration_uuid` — то же
    # состояние, что ниже у V44: ключа нет, снимать нечем, и называет его вызывающий, а не
    # этот код; ключа `bsl_modules` в `children` при этом нет — отсутствующий ключ и есть
    # ответ «снимать было нечем», а не «снято ноль строк».
    # Узел V47 (П1): та же граница становится ЯВНОЙ в запросе. До миграции
    # migrate_v47_bsl_modules_totality.sql строки внешнего контура имели пустой
    # configuration_uuid, и фильтр по uuid заголовка их не касался — требование абзаца выше
    # держалось самими данными, а не запросом. По решению оператора (28.10.2026) у строки
    # внешнего контура оба uuid совпадают и равны uuid самого объекта, поэтому фикстура
    # проверки V32, где uuid конфигурации совпадает с uuid внешнего объекта, снесла модуль
    # чужого контура (замер 28.10.2026: пропала строка id 306 модуля внешнего объекта
    # «СравнениеУСНИ90_2»; инвариант чистоты check_v32_zero_configuration.py это и поймал).
    # Тот же приём с границей по parent_type держит узел V46 (`remove_common_module_texts`).
    if configuration_uuid:
        cur.execute(
            "DELETE FROM bsl_modules WHERE configuration_uuid = %s::uuid "
            "AND parent_type NOT IN ('external_report', 'external_processing')",
            [str(configuration_uuid)],
        )
        children["bsl_modules"] = cur.rowcount
    # Узел V44: модули предопределённых программ корня снимются по uuid заголовка (снимок
    # имени не заводится, ключа нет), поэтому вызов здесь, а не в `configurations`-ветке
    # выше: этих таблиц в списке `tables` нет и по `configuration_id` они не снимаются.
    # Функция возвращает сама счётчики по таблицам — их и кладём в `children`, второй
    # обёртки-словаря у неё нет.
    if configuration_uuid:
        children.update(remove_root_modules(cur, configuration_uuid))
    # Узел V46 (стадия S4): строки свойств подсистем и общих модулей тоже адресуются uuid
    # заголовка, а внешнего ключа и каскада в схеме нет осознанно (прецедент V20.1). Значит
    # снятие обязан выполнить этот же явный DELETE: без него `force=True` оставил бы в базе
    # строки, которые ни к какой конфигурации не относятся и не читаются ни одной карточкой.
    # Здесь снимаются ВСЕ четыре таблицы, а не таблицы «запрошенных видов»: запрошенных видов
    # в этом пути нет — снимается сама конфигурация целиком (круг задаёт CONTRACT-слой).
    if configuration_uuid:
        children.update(remove_object_properties(cur, configuration_uuid))
    # Узел V48 (стадия S4c): строки свойств параметров сеанса тоже адресуются uuid заголовка,
    # а внешнего ключа и каскада в схеме нет осознанно (прецедент V20.1). Значит снятие обязан
    # выполнить этот же явный DELETE: без него force=True оставил бы в базе строки, которые ни
    # к какой конфигурации не относятся и не читаются ни одной карточкой (тот же дефект, что у
    # модулей корня и свойств V46 до соответствующих шагов).
    if configuration_uuid:
        children[SESSION_PARAMETER_TABLE] = remove_session_parameters(cur, configuration_uuid)
    cur.execute("DELETE FROM configurations WHERE id = %s", [cfg_id])
    children["configurations"] = cur.rowcount
    return children


def delete_configuration(cfg_id=None, uuid_val=None):
    """Снять строку заголовка конфигурации и явно почистить связанные строки.

    Привязки внешних объектов (`external_report.configuration_id`, внешнего ключа нет)
    остаются числами без строки — их перечень отдаётся в `dangling_bindings`, потому что
    оператору нужно назвать, что именно стало битым.
    """
    if cfg_id is not None:
        rows = _read_rows(CARD_SQL + "WHERE c.id = %s", [int(cfg_id)])
    elif uuid_val:
        rows = _read_rows(CARD_SQL + "WHERE c.uuid = %s::uuid ORDER BY c.id", [str(uuid_val)])
    else:
        return {"success": False, "error": "Нужен cfg_id или uuid_val"}
    if isinstance(rows, dict):
        return {"success": False, "error": rows.get("error")}
    if not rows:
        return {"success": False, "error": "Строка конфигурации не найдена",
                "looked_by": {"cfg_id": cfg_id, "uuid": uuid_val}}
    target = rows[0]
    cfg_id = int(target["id"])

    bound = bound_external_objects(cfg_id)
    try:
        with transaction() as cur:
            # uuid обязателен: строки группы C (модули предопределённых программ корня,
            # узел V44) адресуются uuid заголовка, а не его id; внешнего ключа со снятием
            # по каскаду в схеме нет, поэтому снятие обязано быть явным здесь.
            children = _remove_rows(cur, cfg_id, target["uuid"])
    except Exception as exc:
        return {"success": False, "error": f"Ошибка удаления: {exc}"}

    result = {
        "success": True,
        "id": cfg_id,
        "uuid": target["uuid"],
        "name": target["name"],
        "table": TABLE,
        "children_deleted": children,
        "dangling_bindings": bound,
        "warnings": [],
    }
    if bound:
        names = ", ".join(f"id={item['id']} {item['name']}" for item in bound)
        result["warnings"].append(
            f"Привязки внешних объектов к снятому заголовку остались числами configuration_id "
            f"без строки (внешнего ключа нет, узел V20.1) — состояние `dangling`, требуется "
            f"перепривязка или снятие: {names}"
        )
    removed_root = {t: children.get(t, 0) for t in ROOT_MODULE_TABLES if children.get(t)}
    if removed_root:
        # Снятие названо по таблицам и числам: строки группы C адресуются uuid снятого
        # заголовка и снимались явно (внешнего ключа в схеме нет, узел V44) — молчать о
        # них значило бы не ответить на вопрос «что ещё ушло вместе с заголовком».
        result["warnings"].append(
            "Сняты строки модулей предопределённых программ корня: "
            + ", ".join(
                f"{t}={removed_root[t]}"
                for t in ROOT_MODULE_TABLES
                if removed_root.get(t)
            )
            + ". Снимались явно по uuid снятого заголовка: внешнего ключа и каскада в схеме "
            "нет (группа C, узел V44)."
        )
    if not target["uuid"]:
        # Ключа нет — значит строки группы C по этой строке не снимались и могли остаться.
        # Назвать это обязан этот вызов: в `children_deleted` соответствующих ключей нет,
        # и по их отсутствию нельзя решить, что ничего не снималось.
        result["warnings"].append(
            "У снятой строки заголовка пуст uuid: строки модулей предопределённых программ "
            "(четыре таблицы группы C, узел V44) адресуются именно uuid, поэтому по этой "
            "строке они не снимались и могли остаться в базе. Их снимает только загрузка по "
            "uuid (`load_configuration_root_modules_tool`) либо явный DELETE по "
            "`configuration_uuid` — проверить их наличие иначе, чем запросом к этим таблицам, "
            "нельзя."
        )
    return result


def _objects_table_available():
    """Создана ли таблица индекса состава (узел V33) — вопрос вне транзакции загрузки.

    Отвечать нужно ДО разбора: парсить 122 313 записей индекса BGU2 (~1 мин), чтобы упасть
    на несозданной таблице, — значит потратить минуту ради отказа, который можно назвать
    заранее.
    """
    rows = _read_rows("SELECT to_regclass('public.%s') IS NOT NULL AS present" % OBJECTS_TABLE)
    if isinstance(rows, dict):
        return False
    return bool(rows and rows[0]["present"])


def _written_before_stop_note(new_id, objects_written, header_arrays_filled,
                              root_modules, child_objects, session_parameters):
    """Что реально лежит в базе на момент остановки конвейера (узел V48, шаг П8).

    Строка обязана быть: остановка стадии откатом не является (стадии S3+ идут после коммита
    транзакции заголовка), и `success: false` без неё прочитался бы как «в базе ничего нет».
    Перечисляется только то, что записано этим вызовом и подтверждено ответом стадии, — не
    «обычно бывает так», а факт текущего прогона.
    """
    parts = [f"заголовок конфигурации id={new_id}"]
    if objects_written:
        parts.append(f"индекс состава: {objects_written} записей в {OBJECTS_TABLE}")
    if header_arrays_filled:
        parts.append(f"перечни имён объектов состава: {header_arrays_filled} колонок")
    if root_modules.get("success"):
        parts.append("модули предопределённых программ корня: "
                     f"{int(root_modules.get('written') or 0)} строк")
    if child_objects.get("success"):
        parts.append("свойства подсистем и общих модулей: "
                     f"{int(child_objects.get('objects_written') or 0)} объектов")
    if session_parameters.get("success"):
        parts.append(f"свойства параметров сеанса: "
                     f"{int(session_parameters.get('rows_written') or 0)} строк")
    return "; ".join(parts)


def _stage_stop(stage_id, stage_result, written_note, warnings, incomplete_groups):
    """Остановить конвейер на отказавшей стадии (узел V48, решение Q8 вариант A).

    Делает три вещи и только они отделены от текста самой стадии:
      1. собирает закрытый ответ `stopped_stage` (адрес стадии, причина, чем продолжить,
         перечень оставшихся `not_run` стадий) — контракт держит `configuration_load_contract`;
      2. называет незакрытую группу состава в `incomplete_groups` (машиночитаемый признак
         неполного состава, прецедент S4b узла V47);
      3. кладёт строку об остановке: без неё предупреждение стадии читается как частная
         жалоба, а не как причина, по которой последующие группы не выполнялись.

    Текст причины отказа и подсказку повтора стадия назвала сама — здесь они только
    пересылаются, второй формулировки об одном отказе в модуле нет.
    """
    stopped = build_stopped_stage(stage_id, stage_result, written_note)
    group = stopped.get("incomplete_group")
    if group and group not in incomplete_groups:
        incomplete_groups.append(group)
    warnings.append(
        f"Загрузка остановлена на стадии {stage_id} «{stage_title(stage_id)}» "
        f"(решение Q8, вариант A): {stopped.get('reason')}. "
        f"{stopped.get('written_before_stop')}"
    )
    return stopped


def register_configuration(source_path, force=False, xml_path=None):
    """Загрузить заголовок конфигурации и индекс её состава из каталога выгрузки.

    Порядок (совпадает с загрузчиком внешнего объекта, чтобы исход читался одинаково):
    каталог → `Configuration.xml` → разбор (пустой/кривой uuid = ошибка R3) → поиск
    строки по uuid → исходы `already_exists` / `name_conflict` → при `force=True` снятие
    старой строки → вставка одной транзакцией. Писатель выбирается один
    (`ConfigurationRowWriter`), поэтому список колонок не разъедется со схемой.

    Узел V33 добавляет один шаг перед транзакцией: `ConfigDumpInfo.xml` из корня каталога
    разбирается парсером состава (`src/config_dump_info_parser.py`) и пишется вторым
    писателем (`ConfigurationObjectRowWriter`) уже после вставки заголовка — `configuration_id`
    берётся из ТОЛЬКО что полученного id. Разбор идёт после проверок дубликата и имени,
    чтобы отказ R5 не платил минуту за индекс, и до транзакции, чтобы кривой индекс не оставил
    половину строк записанной.
    """
    source_dir = Path(source_path)
    if not source_dir.exists() or not source_dir.is_dir():
        return {"success": False, "error": f"Каталог не найден: {source_path}"}

    xml = Path(xml_path) if xml_path else find_configuration_xml(source_dir)
    if xml is None or not xml.is_file():
        return {"success": False,
                "error": f"В корне каталога нет Configuration.xml: {source_path}"}

    parsed = parse_configuration_meta(xml)
    if not parsed.get("success"):
        return parsed

    row = dict(parsed["configuration"])
    warnings = list(parsed.get("warnings") or [])
    warnings.append(PROVENANCE_BOUNDARY)

    if not row.get("name"):
        fallback = source_dir.resolve().name
        row["name"] = fallback
        warnings.append(
            f"<Name> пуст — имя заголовка взято из имени каталога выгрузки: {fallback} "
            f"(для конфигурации имя файла Configuration.xml неинформативно, узел V32)"
        )

    overlong = ConfigurationRowWriter.overlong_fields(row)
    if overlong:
        listed = ", ".join(f"{column} (VARCHAR({limit}) < {length})"
                           for column, limit, length in overlong)
        return {
            "success": False,
            "error": f"Значения не помещаются в колонки таблицы configurations: {listed}",
            "overlong_fields": [{"column": column, "limit": limit, "length": length}
                                for column, limit, length in overlong],
            "hint": "Обрезка значения исказила бы содержимое конфигурации, поэтому загрузка "
                    "не выполнена. Расширение колонок — отдельная задача со сменой схемы "
                    "(миграция + зеркало в create_1c_configurations_db.sql + _cmp_ddl.py).",
        }

    existing = find_configuration(row["uuid"])
    if isinstance(existing, dict) and existing.get("error"):
        return {"success": False, "error": existing["error"]}

    conflict = find_configuration_by_name(
        row["name"], exclude_id=existing["id"] if existing else None
    )
    if isinstance(conflict, dict) and conflict.get("error"):
        return {"success": False, "error": conflict["error"]}
    if conflict:
        return {
            "success": False,
            "name_conflict": True,
            "existing": conflict,
            "error": (
                f"Имя конфигурации уже занято строкой id={conflict['id']} "
                f"(uuid {conflict['uuid']}): в таблице UNIQUE (name), а uuid у двух строк "
                f"различаются. Загрузка не выполнена."
            ),
            "hint": "force=True здесь не предлагается: снятие чужой строки удалило бы другой "
                    "заголовок. Проверьте <Name> в Configuration.xml или снимите занявшую "
                    "строку delete_configuration(cfg_id=...).",
        }

    replaced = None
    if existing:
        if not force:
            return {
                "success": False,
                "already_exists": True,
                "existing": existing,
                "error": (
                    f"Конфигурация с uuid {row['uuid']} уже загружена (id={existing['id']}, "
                    f"name={existing['name']}). Загрузка НЕ выполнена."
                ),
            }
        bound = bound_external_objects(existing["id"])
        replaced = {
            "old_id": existing["id"],
            "old_uuid": existing["uuid"],
            "old_name": existing["name"],
            "bound_external_objects": len(bound),
            "bound_external_object_names": [item["name"] for item in bound],
            "dangling_names": ", ".join(
                f"id={item['id']} {item['name']}" for item in bound
            ),
        }

    # ── узел V33: индекс состава метаданных из ConfigDumpInfo.xml ─────────────────────
    # Место выбора — после исходов `already_exists`/`name_conflict` и до транзакции:
    # отказ R5 не должен платить минуту за разбор 122 000 записей, а кривой индекс не должен
    # оставить половину строк записанной (тот же порядок, что у разбора заголовка).
    index_source = find_config_dump_info(source_dir)
    index_info = None
    if index_source is None:
        warnings.append(
            "ConfigDumpInfo.xml в корне каталога не найден — перечень объектов метаданных "
            f"в {OBJECTS_TABLE} не заполняется, иерархия состава остаётся слепой зоной "
            "(узел V33). Для конфигурации это не норма: выгрузка без индекса неполная."
        )
    elif not _objects_table_available():
        warnings.append(
            f"ConfigDumpInfo.xml найден ({index_source.name}), но таблица {OBJECTS_TABLE} "
            "в базе не создана — индекс состава НЕ разобран и НЕ записан; примените "
            "migrate_v33_configuration_objects.sql и перезагрузите конфигурацию (force=True). "
            "Разбор ради отказа не запускался: 122 000 записей парсятся минуту."
        )
    else:
        parsed_index = parse_config_dump_info(index_source)
        if not parsed_index.get("success"):
            return {
                "success": False,
                "error": f"Индекс состава не разобран: {parsed_index.get('error')}",
                "hint": parsed_index.get("hint")
                        or "Узел V33 не заполняет configuration_objects частично: пока индекс "
                           "не разобран целиком, загрузка не выполнена; прежняя строка при этом "
                           "не снята.",
                "index_source": str(index_source),
            }
        index_info = parsed_index
        for index_warning in parsed_index.get("warnings") or []:
            warnings.append(f"ConfigDumpInfo: {index_warning}")

    # ── узел V43: перечни имён объектов состава в строке заголовка ───────────────────────
    # Источник — ТОТ ЖЕ разобранный индекс, что и строки `configuration_objects`: второго
    # чтения ConfigDumpInfo.xml нет. Два независимых чтения одного файла разошлись бы при
    # любом сбое между ними, и заголовок начал бы утверждать состав, которого в таблице
    # индекса нет. Правила K1–K6 (глубина 0, NULL вместо пустого массива, короткие имена,
    # порядок по полному точечному имени в байтовом порядке UTF-8) задаёт один модуль —
    # `src/configuration_child_properties.py`, тот же контракт читает бэкфилл миграции.
    header_arrays_filled = 0
    header_array_items = 0
    header_array_anomalies = {}
    if index_info is not None:
        # `collect_header_arrays` отвечает не только значениями: он же называет аномалии
        # (вид без колонки, имя длиннее K3, пустое имя). Значения лежат в ключе `values` —
        # брать весь ответ и класть в строку нельзя: `counts`/`warnings` не являются
        # колонками, а писатель молчит про лишние ключи, и состав заголовка просто
        # не лёг бы в БД (проверено чтением кода писателя: INSERT строится по COLUMNS).
        header_agg = collect_header_arrays(index_info["objects"])
        header_arrays = header_agg["values"]
        # пустой перечень приходит отсутствием ключа, а не пустым списком, и ложится в
        # колонку как NULL (K2): «объектов такого вида в конфигурации нет» — это ответ о
        # конфигурации, а пустой массив `'{}'::text[]` читался бы как «перечень есть, но
        # пустой».
        row.update(header_arrays)
        header_arrays_filled = header_agg["columns_filled"]
        header_array_items = header_agg["objects_total"]
        header_array_anomalies = {
            "unknown_types": header_agg["unknown_types"],
            "overlong": len(header_agg["overlong"]),
            "empty_object_name": header_agg["empty_object_name"],
            "top_level_entries": header_agg["top_level_entries"],
        }
        for header_warning in header_agg["warnings"]:
            warnings.append(header_warning)
    else:
        warnings.append(
            "Перечни имён объектов состава (48 колонок `*_names` строки заголовка) НЕ "
            "заполняются — все они останутся NULL: источником служит индекс состава, а он не "
            "разобран. Пустой массив вместо NULL означал бы «таких объектов в конфигурации "
            "нет», то есть был бы ложью о конфигурации (узел V43, K2)."
        )

    try:
        with transaction() as cur:
            if existing:
                # снятие прежней строки и вставка новой — ОДНА транзакция: при ошибке
                # вставки откатывается всё, конфигурация не остаётся снятой без замены
                # uuid передаётся обязательно: по нему снимаются строки группы C (модулей
                # предопределённых программ, узел V44); id — только индекс строки заголовка,
                # каскада по нему нет.
                replaced["children_deleted"] = _remove_rows(
                    cur, existing["id"], existing["uuid"]
                )
            new_id = ConfigurationRowWriter.insert(cur, row)
            objects_written = 0
            if index_info is not None and new_id is not None:
                # узел V33: `configuration_id` подставляется здесь, а не в парсере: парсер
                # не знает, под каким id ляжет заголовок (force меняет id — узел V32).
                for entry in index_info["objects"]:
                    entry["configuration_id"] = new_id
                objects_written = ConfigurationObjectRowWriter.insert_many(
                    cur, index_info["objects"]
                )
    except Exception as exc:
        return {"success": False, "error": f"Ошибка записи: {exc}"}
    if new_id is None:
        return {"success": False, "error": "Не получен ID записи из INSERT RETURNING id"}

    if replaced:
        deleted = replaced["children_deleted"] or {}
        removed_root = {t: deleted.get(t, 0) for t in ROOT_MODULE_TABLES if deleted.get(t)}
        if removed_root:
            # `force=True` снял строки группы C и не заполнил их заново: заголовок этого не
            # делает — содержимое модулей существует файлами Ext/, а не свойствами XML.
            # О пропавшем состоянии карточка обязана сказать прямо: иначе по ней нельзя
            # ответить, были ли эти модули в базе до перезагрузки (граница описана в
            # docstring модуля, п. V44).
            warnings.append(
                "Сняты строки модулей предопределённых программ корня: "
                + ", ".join(
                    f"{t}={removed_root[t]}"
                    for t in ROOT_MODULE_TABLES
                    if removed_root.get(t)
                )
                + ". Текущая загрузка заполняет их заново на стадии модулей "
                "предопределённых программ (узел V45, S3) — результат в разделе "
                "`root_modules` ответа; отдельная точка входа "
                "`load_configuration_root_modules_tool` остаётся для случая «изменились "
                "только файлы Ext/» (решение V45: заголовок не меняется, заново разбирать "
                "индекс состава не нужно)."
            )
        if replaced["bound_external_objects"]:
            warnings.append(
                f"Прежняя строка заголовка id={replaced['old_id']} снята; привязки внешних "
                f"объектов остались числами configuration_id без строки — состояние "
                f"`dangling`, требуется перепривязка set_object_configuration_tool(uuid=…, "
                f"configuration_id=<новый id>) или снятие: {replaced['dangling_names']}"
            )
        else:
            warnings.append(
                f"Прежняя строка заголовка id={replaced['old_id']} снята, привязок внешних "
                f"объектов к ней не было."
            )

    # Узел V45 (стадия S3): модули предопределённых программ корня. Вызов — ПОСЛЕ коммита
    # транзакции заголовка: `transaction()` каждый раз открывает новое соединение, и в
    # собственной транзакции заголовка слой модулей не увидел бы только что вставленную
    # строку (`_require_header` → `find_configuration`). Ключ — uuid, а не id: `force=True`
    # меняет id, uuid остаётся прежним (V44). Если XML передан явно (тестовые фикстуры),
    # слой обязан искать `Ext/` рядом с этим XML, а не рядом с аргументом каталога.
    #
    # Узел V48 (шаг П8, решение Q8 вариант A) меняет поведение конвейера при отказе:
    #   * ответ каждой стадии создаётся ДО вызова — стадия, которую не позвали, обязана
    #     читаться `not_run` (правило C2), а не отсутствовать в ответе и не нести нули
    #     выполненной стадии;
    #   * первая ошибка стадии останавливает конвейер: последующие стадии не вызываются
    #     вовсе, их ответы остаются на `*_defaults()` со статусом `not_run`;
    #   * остановка откатом не является — заголовок, индекс состава и перечни вида, а также
    #     записи выполненных до отказа стадий остаются в базе (граница D7), поэтому ответ
    #     обязан назвать и остановленную стадию, и то, что сохранилось;
    #   * `load_incomplete`/`incomplete_groups` — машиночитаемый признак неполного состава
    #     (прецедент S4b узла V47), `success: false` — признак остановки. Два разных факта,
    #     два разных ключа ответа: смешивать их нельзя, но при остановке проставляются оба.
    root_source = Path(xml_path).parent if xml_path else source_path
    root_modules = root_modules_defaults()
    child_objects = child_objects_defaults()
    session_parameters = session_parameters_defaults()
    object_modules = object_modules_defaults()
    # Узел V48 (шаг П8, правило C2): пропущенная стадия называет причину пропуска. Без неё
    # форматёр стадии печатает «загрузчик не назвал причину», и читатель карточки видит
    # «Стадия не выполнена» без объяснения. Статус нулевого ответа S4b приходит из контракта
    # писателя (`ok`, описывающего результат записи, а не состояние стадии), поэтому статус
    # пропущенной стадии ставит загрузчик — право назвать состояние стадии принадлежит ему
    # (тот же приём, что `mark_index_unavailable` узла V47). Причина — в `reason`, а не в
    # `error`: «не выполнялась» и «отказала после начала работы» различаются именно так.
    for _empty_stage in (child_objects, session_parameters, object_modules):
        _empty_stage["reason"] = NOT_RUN_STOPPED_REASON
    object_modules["status"] = STATUS_NOT_RUN
    stopped_stage = stopped_stage_defaults()
    stopped = False
    load_incomplete = False
    incomplete_groups = []
    # Один штамп времени на событие загрузки (M2): строки детей несут то же время, что и
    # заголовок и строки выполненных стадий, а не время своей транзакции. Штамп ставится до
    # первой стадии детей, потому что с шагом П8 стадия может и не вызываться — у пропущенной
    # стадии своего времени загрузки нет.
    load_moment = datetime.now()

    def _stop_here(stage_id, stage_result):
        """Остановка на отказавшей стадии с перечнем того, что уже записано."""
        return _stage_stop(
            stage_id, stage_result,
            _written_before_stop_note(new_id, objects_written, header_arrays_filled,
                                      root_modules, child_objects, session_parameters),
            warnings, incomplete_groups)

    if not stopped:
        try:
            root_modules = load_root_modules(root_source, configuration_uuid=row["uuid"])
        except Exception as exc:  # noqa: BLE001 — отказ стадии называется, а не бросается
            root_modules = root_modules_defaults()
            root_modules["configuration_id"] = new_id
            root_modules["configuration_uuid"] = row["uuid"]
            root_modules["configuration_name"] = row["name"]
            root_modules["error"] = (
                f"исключение слоя модулей предопределённых программ: {exc}"
            )
        if not root_modules.get("success"):
            # Заголовок и индекс уже записаны, и отказ стадии их не отменяет — но молчать о
            # пропавшем после force=True состоянии нельзя (дефект, описанный в docstring V44):
            # стадия называется прямо, вместе со способом повторить её отдельно.
            warnings.append(
                "Модули предопределённых программ корня не загружены — причина названа "
                "строкой «Стадия не выполнена» в разделе «"
                + ROOT_MODULES_SECTION_HEADER
                + "» карточки. Чем продолжить: "
                + f"{ROOT_MODULES_REPEAT_HINT} (configuration_uuid={row['uuid']})."
            )
            stopped_stage = _stop_here(STAGE_ROOT_MODULES, root_modules)
            stopped = True
            load_incomplete = True

    # Узел V46 (стадия S4): свойства дочерних объектов — подсистемы и общие модули.
    # Порядок вызова повторяет стадию V44: ПОСЛЕ коммита транзакции заголовка (соединение
    # стадии не увидело бы незакоммиченного заголовка и строк индекса состава), ключ — uuid,
    # а не id (`force=True` меняет id, uuid остаётся). Каталог тот же `root_source`: если XML
    # передан явно, файлы ищутся рядом с ним.
    # Тексты модулей общих модулей стадия НЕ читает (решение D-S4: замер 2.6 плана даёт
    # 188 МБ на BGU2 и 294 МБ на BP3): S4 отвечает свойства и дескрипторы, содержимое модулей
    # запрашивается явно — `with_module_content=True` у отдельного инструмента. Разница названа
    # и в ответе стадии (строка форматёра про тексты), а не молчанием.
    if not stopped:
        try:
            child_objects = load_object_properties(
                root_source, configuration_uuid=row["uuid"])
        except Exception as exc:  # noqa: BLE001 — отказ стадии называется, а не бросается
            child_objects = child_objects_defaults()
            child_objects["configuration_id"] = new_id
            child_objects["configuration_uuid"] = row["uuid"]
            child_objects["configuration_name"] = row["name"]
            child_objects["error"] = f"исключение слоя свойств дочерних объектов: {exc}"
        if not child_objects.get("success"):
            # Заголовок, индекс и модули корня уже записаны, и отказ этой стадии их не отменяет
            # (C5). Молчать нельзя по той же причине, что у V44: после force=True прежние строки
            # сняты, и «загружено» без этой строки читалось бы как полный состав.
            warnings.append(
                "Свойства подсистем и общих модулей не загружены — причина названа строкой "
                "«Стадия не выполнена» в разделе «" + CHILD_SECTION_HEADER
                + "» карточки. Чем продолжить: "
                + f"{CHILD_OBJECTS_REPEAT_HINT} (configuration_uuid={row['uuid']})."
            )
            stopped_stage = _stop_here(STAGE_CHILD_OBJECTS, child_objects)
            stopped = True
            load_incomplete = True

    # ── узел V48 (стадия S4c, позиция 2.3 списка): свойства параметров сеанса ─────────
    # Порядок вызова повторяет S3/S4: ПОСЛЕ коммита транзакции заголовка (своим соединением
    # стадия не увидела бы незакоммиченного заголовка и строк индекса состава), ключ — uuid,
    # каталог тот же `root_source`. Стадия отдельная, а не третий вид S4 (решение Q5), и
    # ответ её лежит в собственном ключе `session_parameters` (правило C3); порядок стадий
    # повторяет порядок нормативного списка (2.3 идёт сразу за 2.1–2.2). Отказ стадии, как у
    # S3/S4, записанный заголовок не отменяет (C5) — но с шагом П8 того же узла (решение Q8,
    # вариант A) он останавливает конвейер: S4b после отказа S4c не выполняется и читается
    # `not_run`, а не нулями.
    #
    # Один штамп времени на событие загрузки (M2): строки свойств несут то же время, что и
    # остальные строки этой загрузки, а не время своей транзакции.
    if not stopped:
        try:
            session_parameters = load_session_parameters(
                root_source, configuration_uuid=row["uuid"], changed_at=load_moment)
        except Exception as exc:  # noqa: BLE001 — отказ стадии называется, а не бросается
            session_parameters = session_parameters_defaults()
            session_parameters["configuration_id"] = new_id
            session_parameters["configuration_uuid"] = row["uuid"]
            session_parameters["configuration_name"] = row["name"]
            session_parameters["status"] = STATUS_ERROR
            session_parameters["error"] = (
                f"исключение слоя свойств параметров сеанса: {exc}")
            session_parameters["reason"] = session_parameters["error"]
        for parameter_warning in session_parameters.get("warnings") or []:
            warnings.append(f"параметры сеанса: {parameter_warning}")
        if not session_parameters.get("success"):
            # Заголовок, индекс состава, модули корня и свойства подсистем с общими модулями
            # уже записаны, и отказ этой стадии их не отменяет (C5). Молчать нельзя по той же
            # причине, что у V44/V46: после force=True прежние строки сняты, и «загружено» без
            # этой строки читалось бы как полный состав конфигурации.
            warnings.append(
                "Свойства параметров сеанса не загружены — причина названа строкой "
                "«Стадия не выполнена» в разделе «" + SESSION_PARAMETERS_SECTION_HEADER
                + "» карточки. Чем продолжить: "
                + f"{SESSION_PARAMETERS_REPEAT_HINT} (configuration_uuid={row['uuid']})."
            )
            stopped_stage = _stop_here(STAGE_SESSION_PARAMETERS, session_parameters)
            stopped = True
            load_incomplete = True

    # ── узел V47 (стадия S4b): модули объектов конфигурации ────────────────────────────
    # Вторая транзакция ПОСЛЕ фиксации содержимого конфигурации (решение Q6, граница D7
    # узла V46): отказ стадии не откатывает заголовок, индекс состава, модули корня и
    # свойства дочерних объектов. Порядок вызова повторяет S3/S4 — после коммита
    # транзакции заголовка (стадия своим соединением не увидела бы незакоммиченного
    # заголовка и строк индекса), ключ — uuid, каталог тот же `root_source`. Флагов нет
    # (решение Q4): стадия выполняется всегда, права «не читать код» у неё нет.
    #
    # Штамп времени общий с остальными стадиями этой загрузки (M2) — `load_moment` задан
    # выше, где начинается событие детей заголовка.
    #
    # Узел V48 (шаг П8, решение Q8 вариант A): отказ этой стадии, как и отказ любой другой,
    # делает итог `success: false`; различие двух состояний сохраняет статус стадии (C2):
    #   * `error` — круг читался и отказал: это остановка, и она называется ключом
    #     `stopped_stage` (для S4b продолжения нет, кроме полной перезагрузки, Q4.1);
    #   * `not_run` — круг не определён (индекс состава не разобран, узел V33): стадии не
    #     было, останавливать нечего, итог остаётся прежним, но состав помечается неполным.
    if not stopped:
        if index_info is None:
            # Круг не определён: его задают записи `configuration_objects`, а их этой
            # загрузкой не создавалось (V33). Стадия НЕ выполнялась (C2) — её нули
            # читались бы как ответ о конфигурации: «модулей нет» вместо «круг не читался».
            object_modules = mark_index_unavailable(
                "ConfigDumpInfo.xml не найден или индекс состава не разобран (узел V33)")
        else:
            try:
                object_modules = load_object_modules(
                    root_source, configuration_uuid=row["uuid"], changed_at=load_moment)
            except Exception as exc:  # noqa: BLE001 — отказ стадии не бросается, а называется
                object_modules = object_modules_defaults()
                object_modules["status"] = STATUS_ERROR
                object_modules["error"] = (
                    f"исключение слоя модулей объектов конфигурации: {exc}")
                object_modules["reason"] = object_modules["error"]
        for module_warning in object_modules.get("warnings") or []:
            warnings.append(f"модули объектов конфигурации: {module_warning}")
        if not object_modules.get("success"):
            # Атомом полноты является группа объектов (Q4), и «✅ загружено» без этой строки
            # утверждало бы состав, которого в базе нет (критерий 8 плана) — независимо от
            # того, отказала стадия или не выполнялась вовсе. Отдельного входа для повтора
            # стадии нет (Q4.1) — требуется полная перезагрузка.
            load_incomplete = True
            failed_group = object_modules.get("failed_group")
            if failed_group and failed_group not in incomplete_groups:
                incomplete_groups.append(failed_group)
            warnings.append(
                "Модули объектов конфигурации не загружены — причина названа строкой "
                "«Стадия не удалась» в разделе «" + OBJECT_MODULES_SECTION_HEADER
                + "» карточки"
                + (f", незакрытая группа объектов: {failed_group}" if failed_group else "")
                + ". Заголовок, индекс состава, модули предопределённых программ и "
                  "свойства дочерних объектов записаны; повторить стадию отдельно нельзя "
                  "(решение Q4.1) — требуется полная перезагрузка: "
                  "load_1c_catalog_tool(source_path=..., force=True)."
            )
            if object_modules.get("status") == STATUS_ERROR:
                # Отказ круга — остановка конвейера (Q8). `not_run` остановкой не является:
                # стадии не было, и её состояние описывает только раздел стадии (C2).
                stopped_stage = _stop_here(STAGE_OBJECT_MODULES, object_modules)
                stopped = True

    result = {
        # узел V48 (шаг П8, решение Q8 вариант A): итог зависит от отказа стадии. Раньше
        # `success: True` ставился безусловно после записи заголовка, и отказ любой стадии
        # детей оставался предупреждением. Теперь первая ошибка стадии даёт `false`; при этом
        # `load_incomplete`/`incomplete_groups` — отдельный признак неполного состава, а не
        # копия признака остановки (два разных факта, два разных ключа).
        "success": not stopped,
        "id": new_id,
        "uuid": row["uuid"],
        "name": row["name"],
        "table": TABLE,
        "variant_title": VARIANT_TITLE,
        "counts": parsed.get("counts") or {},
        "not_filled_columns": parsed.get("not_filled_columns") or {},
        "replaced": replaced,
        "warnings": warnings,
        # узел V33: карточка обязана назвать и индекс состава — что разобрано, что записано
        # и почему состава нет, если его нет. Молчать про индекс значило бы оставить
        # вопрос «а он вообще загрузился?» без ответа (тот же принцип, что с
        # not_filled_columns у заголовка).
        "configuration_objects_written": objects_written,
        "index_found": index_source is not None,
        "index_source": str(index_source) if index_source is not None else None,
        # узел V43: карточка обязана назвать и состояние перечней вида — сколько колонок
        # получило значения и сколько имён в них легло. Молчать про них нельзя: по нулям в
        # колонках нельзя отличить «видов таких в конфигурации нет» от «индекс не разобран»,
        # а именно это и есть граница K2.
        "header_arrays_filled": header_arrays_filled,
        "header_array_columns_total": len(header_array_columns()),
        "header_array_items": header_array_items,
        "header_array_anomalies": header_array_anomalies,
        # узел V45: машинная часть ответа стадии S3 — полная, её читают проверки;
        # текст отдаёт общий форматёр контракта (configuration_load_contract),
        # карточка и отдельный инструмент описывают один слой одинаково.
        "root_modules": root_modules,
        # узел V46: машинная часть стадии S4 — полная (тот же закрытый контракт, что отдаёт
        # отдельный инструмент); текст раздела даёт общий форматёр контракта.
        "child_objects": child_objects,
        # узел V48: машинная часть стадии S4c (позиция 2.3 списка) — полная; ответ лежит в
        # собственном ключе, а не внутри `child_objects` (правило C3, решение Q5). Текст
        # раздела даёт общий форматёр контракта — тот же, что отдаёт отдельный инструмент
        # `load_session_parameters_tool` (шаг П5).
        "session_parameters": session_parameters,
        # узел V47: машинная часть стадии S4b — полная (тот же закрытый контракт, который
        # читают проба П4 и проверка П5); текст раздела даёт общий форматёр контракта.
        # `load_incomplete`/`incomplete_groups` — признак того, что состав в БД неполный
        # (решение Q4): карточка обязана назвать это сразу после строки исхода, а не только
        # внутри раздела стадии, иначе «✅ загружено» читалось бы как полная конфигурация.
        "object_modules": object_modules,
        "load_incomplete": load_incomplete,
        "incomplete_groups": incomplete_groups,
        # узел V48 (шаг П8, решение Q8 вариант A): чем остановлен конвейер. Нулевой словарь
        # означает «конвейер не останавливался»; ненулевой называет остановленную стадию, её
        # причину, чем продолжить и что осталось в базе. Последующие стадии при этом не
        # вызывались вовсе и читаются `not_run` своими ответами (правило C2).
        "stopped_stage": stopped_stage,
    }
    if stopped:
        # Обязательная строка: остановка откатом не является, и `false` без неё читался бы
        # как «в базе ничего нет» — неправда, заголовок и индекс состава зафиксированы.
        result["error"] = (
            f"Загрузка остановлена на стадии {stopped_stage['stage']} "
            f"«{stopped_stage['title']}»: {stopped_stage['reason']}"
        )
        result["hint"] = (
            f"{stopped_stage['written_before_stop']}. "
            f"Чем продолжить: {stopped_stage['resume_with']}"
        )
    if index_info is not None:
        index_counts = index_info.get("counts") or {}
        result["index_counts"] = {
            key: index_counts.get(key)
            for key in ("entries_total", "root_entries", "child_entries", "max_depth",
                        "config_versions", "config_versions_missing", "parent_unresolved")
        }
        result["index_types"] = len(index_counts.get("types") or {})
        result["index_id_forms"] = index_counts.get("id_forms") or {}
    if index_info is not None and objects_written != index_counts.get("entries_total"):
        # Разошлись числа разобранного и записанного — значит часть строк не легла
        # (например, нарушение уникальности), и молчать об этом нельзя.
        warnings.append(
            f"Разобрано записей индекса {index_counts.get('entries_total')}, записано "
            f"{objects_written} — часть строк в {OBJECTS_TABLE} не попала."
        )
    if replaced:
        result["reloaded"] = True
    return result

