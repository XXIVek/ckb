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

Чтения идут через psycopg2 (`src/external_db.py`), а не psql-подпроцессом: `_run_psql` /
`_psql_fields` унаследованы от прежнего загрузчика, многоколоночные выборки разбирают
текст по '|', а URL и комментарий конфигурации — как раз значения с '|'.
"""
import re
from pathlib import Path

import psycopg2.extras

from config_dump_info_parser import find_config_dump_info, parse_config_dump_info
from configuration_meta_parser import parse_configuration_meta
from external_db import connect, transaction
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
       (SELECT COUNT(*) FROM external_report e
         WHERE e.configuration_id = c.id) AS bound_external_objects,
       (SELECT COUNT(*) FROM bsl_modules b
         WHERE b.configuration_id = c.id) AS bsl_modules_count,
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
        "SELECT id, name, uuid::text AS uuid FROM external_report "
        "WHERE configuration_id = %s ORDER BY id",
        [int(cfg_id)],
    )
    return [] if isinstance(rows, dict) else rows


def _remove_rows(cur, cfg_id):
    """Снять строку заголовка и связанные строки ВНУТРИ текущей транзакции.

    Каскада нет: FK `bsl_modules.configuration_id` и `config_extensions.configuration_id`
    объявлены без `ON DELETE` (шаг 2 установки), `external_report.configuration_id` —
    ссылка без FK вовсе (узел V20.1). Поэтому модули и расширения снимаются явным
    `DELETE` (иначе удаление упадёт FK), а привязки внешних объектов остаются числами.

    Узел V33: строки индекса состава (`configuration_objects`) ссылаются на заголовок FK
    без `ON DELETE` (шаг 2 установки, тот же порядок, что у расширений и модулей), поэтому
    без явного `DELETE` здесь же `force=True` и `delete_configuration` падают с
    `configuration_objects_configuration_id_fkey` — при 122 000 строк это означало бы, что
    конфигурацию нельзя ни перезагрузить, ни снять.

    Функция принимает курсор, а не открывает свою транзакцию, намеренно: `force=True`
    обязан выполняться одной транзакцией со вставкой новой строки, иначе неудачная вставка
    оставила бы конфигурацию снятой без замены.
    """
    children = {}
    # Таблицы индекса может не быть в базе, где миграцию V33 не применяли: снимать нечего,
    # и отказывать загрузке заголовка из-за этого нельзя (заголовок — узел V32).
    tables = [OBJECTS_TABLE] if _table_present(cur, OBJECTS_TABLE) else []
    tables += ["config_extensions", "bsl_modules"]
    for table in tables:
        cur.execute(f"DELETE FROM {table} WHERE configuration_id = %s", [cfg_id])
        children[table] = cur.rowcount
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
            children = _remove_rows(cur, cfg_id)
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

    try:
        with transaction() as cur:
            if existing:
                # снятие прежней строки и вставка новой — ОДНА транзакция: при ошибке
                # вставки откатывается всё, конфигурация не остаётся снятой без замены
                replaced["children_deleted"] = _remove_rows(cur, existing["id"])
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

    result = {
        "success": True,
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
    }
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

