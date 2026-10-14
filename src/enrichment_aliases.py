#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API алиасов обогащения (config_aliases) - узел V17.

Пришёл на смену src/config_aliases.py: тот модуль подключался к базе `configurations`,
которой на сервере нет, и работал с колонкой configuration_id, которой нет в схеме V17
(объект адресуется парой parent_uuid + uuid). Модуль удалён, его функции переписаны сюда.

Разделение ответственности:
  * src/enrichment_generator.py - АВТОМАТИЧЕСКИЕ алиасы (origin='generated'): генератор
    снимает их и пишет заново;
  * этот модуль - РАБОТА ОПЕРАТОРА: добавить недостающий алиас (origin='manual'), найти,
    посмотреть, снять отметку активности. Ручные алиасы перегенерация не трогает.

Зачем ручной алиас (решение E6, п. 3 плана): автоматические алиасы строятся из сохранённого
содержимого - имя объекта, синоним, реквизиты, элементы формы, объявления модулей. Они
покрывают только те термины, которые реально есть в выгрузке. Пользователь же ищет по
русским формулировкам («средний возраст», «сравнение с прошлым годом»), аббревиатурам и
английским транслитам - их в выгрузке нет. add_config_aliases_tool закрывает этот разрыв,
и лимита на количество ручных алиасов нет (в отличие от автоалиасов сниппета, где стоит
порог MAX_AUTO_ALIASES_PER_SNIPPET = 10).

Уникальность: частичный уникальный индекс uq_config_aliases_alias_target
(alias_norm, target_key) WHERE active. Колонку target_key считает база, поэтому все вставки
идут через insert_many_skip_duplicates (ON CONFLICT DO NOTHING): повторный вызов не создаёт
дублей и не прерывает транзакцию.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from external_db import transaction  # noqa: E402
from external_table_writer import ConfigAliasRowWriter  # noqa: E402
from external_meta_parser import OBJECT_KIND_TITLES  # noqa: E402
from enrichment_generator import (  # noqa: E402
    MIN_ALIAS_WORD_LEN,
    WEIGHTS,
    build_object_aliases,
    collect_source_data,
    fetch_rows,
    norm_alias,
    object_kind_of,
    object_row,
    object_target_type,
    resolve_object,
)


MAX_LIST_LIMIT = 500


def _resolve_uuid(cur, uuid, source_path):
    """Разобрать адрес объекта и убедиться, что он лежит в external_report.

    Возвращает пару (uuid, карточка_объекта) либо (None, карточка_ошибки).
    """
    resolved = resolve_object(uuid=uuid, source_path=source_path)
    if not resolved.get("success"):
        return None, resolved
    obj = object_row(cur, resolved["uuid"])
    if not obj:
        return None, {"success": False,
                      "error": f"Внешний объект с uuid={resolved['uuid']} в external_report не найден",
                      "hint": "Сначала загрузите каталог: load_1c_catalog_tool(source_path=...), "
                              "затем generate_config_enrichment_tool(source_path=...)."}
    return resolved["uuid"], obj


def _alias_row(alias, obj_uuid, target_type, target_name, target_uuid, target_snippet_id,
               weight, description, origin, parent_type="external_report"):
    """Собрать строку config_aliases (target_key не заполняется - её считает база)."""
    text = " ".join(str(alias or "").split()).strip()
    return {
        "alias_name": text,
        "alias_norm": norm_alias(text),
        "target_type": target_type,
        "target_name": target_name,
        "target_uuid": target_uuid,
        "target_snippet_id": target_snippet_id,
        "parent_uuid": obj_uuid,
        "parent_type": parent_type,
        "weight": weight,
        "description": description,
        "origin": origin,
        "active": True,
    }


def add_config_aliases(aliases, uuid=None, source_path=None, target_type=None,
                       target_name=None, target_uuid=None, target_snippet_id=None,
                       description=None, weight=None):
    """Добавить ручные алиасы (origin='manual') - аналог add_aliases_tool из local_doc.

    Цель по умолчанию - сам внешний отчёт: если target_* не указаны, алиас ведёт на объект.
    Это тот инструмент, которого не хватало при автоматической генерации: русские
    формулировки, аббревиатуры и английские термины, которых в выгрузке нет.
    Количество не ограничено (в отличие от автоалиасов сниппета).
    """
    parts = [item for item in str(aliases or "").split(",") if item.strip()]
    if not parts:
        return {"success": False,
                "error": "Список aliases пуст: передайте строку через запятую "
                        "(как add_aliases_tool в local_doc)"}
    if target_snippet_id is not None and target_type not in (None, "ConfigSnippet"):
        return {"success": False,
                "error": f"target_type='{target_type}' не согласуется с target_snippet_id="
                        f"{target_snippet_id}: для цели-сниппета указывайте "
                        "target_type='ConfigSnippet'"}
    try:
        with transaction() as cur:
            obj_uuid, obj = _resolve_uuid(cur, uuid, source_path)
            if obj_uuid is None:
                return obj
            if target_snippet_id is not None:
                found = fetch_rows(cur, "SELECT id, question FROM config_snippets WHERE id = %s",
                                   (int(target_snippet_id),))
                if not found:
                    return {"success": False,
                            "error": f"Сниппет id={target_snippet_id} в config_snippets не найден"}
                resolved_type = "ConfigSnippet"
                resolved_name = found[0]["question"]
                resolved_uuid = None
                resolved_snippet = int(target_snippet_id)
            else:
                # Узел V22: цель «сам объект» обязана быть того же вида, что и строка заголовка.
                # Для внешней обработки алиас на ExternalReport вёл бы в несуществующий объект:
                # таблицы external_processing больше нет, а uuid принадлежит обработке.
                object_kind = object_kind_of(obj)
                object_type = object_target_type(obj)
                if target_type and target_type != object_type and target_type in (
                        "ExternalReport", "ExternalProcessing"):
                    return {"success": False,
                            "error": f"Цель '{target_type}' не совпадает с видом объекта: "
                                     f"uuid={obj_uuid} — {OBJECT_KIND_TITLES[object_kind]} "
                                     f"(object_kind='{object_kind}'). Укажите target_type="
                                     f"'{object_type}' или опустите target_type — цель на сам "
                                     "объект подставляется по его виду."}
                resolved_type = target_type or object_type
                resolved_name = target_name or obj.get("name")
                resolved_uuid = target_uuid or (obj_uuid if resolved_type == object_type
                                               else None)
                resolved_snippet = None
            weight_value = float(weight) if weight is not None else WEIGHTS.get(
                f"{resolved_type}.name", 1.0)
            rows = [_alias_row(part, obj_uuid, resolved_type, resolved_name, resolved_uuid,
                               resolved_snippet, weight_value,
                               description or "алиас, добавленный оператором", "manual",
                               parent_type=object_kind_of(obj))
                    for part in parts]
            inserted, skipped = ConfigAliasRowWriter.insert_many_skip_duplicates(cur, rows)
            return {"success": True, "uuid": obj_uuid, "object_name": obj.get("name"),
                    "requested": len(rows), "created": inserted, "already_present": skipped,
                    "target_type": resolved_type, "target_name": resolved_name,
                    "target_uuid": resolved_uuid, "target_snippet_id": resolved_snippet,
                    "weight": weight_value,
                    "aliases": [row["alias_name"] for row in rows]}
    except Exception as exc:
        return {"success": False, "error": f"Алиасы не добавлены (полный откат): {exc}"}


def generate_object_aliases(uuid=None, source_path=None, target_type=None, target_name=None):
    """Точечно сгенерировать алиасы для ОДНОЙ цели (аналог generate_aliases_for_object_tool).

    Берёт ровно те строки, которые построил бы генератор для этой цели, и вставляет их,
    не удаляя остальные: нужно, когда объект уже обогащён, а алиас нужен по одному
    реквизиту или элементу формы.
    """
    if not target_type:
        return {"success": False,
                "error": "Нужен target_type цели (Attribute, TabularSection, FormItem, "
                        "Template, Module, ...)"}
    try:
        with transaction() as cur:
            obj_uuid, obj = _resolve_uuid(cur, uuid, source_path)
            if obj_uuid is None:
                return obj
            data = collect_source_data(cur, obj_uuid)
            rows = [row for row in build_object_aliases(obj, data)
                    if row["target_type"] == target_type
                    and (not target_name
                         or norm_alias(row["target_name"] or "") == norm_alias(target_name))]
            if not rows:
                return {"success": False,
                        "error": f"Цель target_type='{target_type}'"
                                 f"{'' if not target_name else ' с именем ' + repr(target_name)} "
                                 "среди сохранённого содержимого объекта не найдена",
                        "hint": "Состав целей: generate_config_enrichment_tool, затем витрины "
                                "v_config_enrichment / таблицы attributes, forms, form_ext, "
                                "templates."}
            inserted, skipped = ConfigAliasRowWriter.insert_many_skip_duplicates(cur, rows)
            return {"success": True, "uuid": obj_uuid, "object_name": obj.get("name"),
                    "target_type": target_type, "target_name": target_name,
                    "created": inserted, "already_present": skipped,
                    "aliases": [row["alias_name"] for row in rows]}
    except Exception as exc:
        return {"success": False, "error": f"Алиасы не сгенерированы (полный откат): {exc}"}


def search_config_aliases(query, uuid=None, target_type=None, limit=20):
    """Найти алиасы: сначала точное совпадение, затем префикс, затем подстрока.

    Полнотекстового индекса на алиасах нет намеренно: алиас - короткий идентификатор, его
    ищут как имя. Подстрока идёт через position(), а не через to_tsquery: FTS по конфигу
    simple не ищет по середине слова (идентификатор 1С - одна лексема), а поиск по
    середине/хвосту потребовал бы pg_trgm (в кластере доступен, но не установлен).
    """
    text = norm_alias(query)
    if len(text) < MIN_ALIAS_WORD_LEN:
        return {"success": False,
                "error": f"Запрос {repr(query)} короче {MIN_ALIAS_WORD_LEN} символов - "
                         "по такому алиасу искать бессмысленно"}
    limit = max(1, min(int(limit or 20), MAX_LIST_LIMIT))
    where = ["a.active"]
    params = {"q": text, "limit": limit}
    if uuid:
        where.append("a.parent_uuid = %(uuid)s::uuid")
        params["uuid"] = str(uuid)
    if target_type:
        where.append("a.target_type = %(target_type)s")
        params["target_type"] = target_type
    where.append("(a.alias_norm = %(q)s OR a.alias_norm LIKE %(q)s || '%%' "
                 "OR position(%(q)s IN a.alias_norm) > 0)")
    sql = f"""
        SELECT a.id, a.alias_name, a.target_type, a.target_name, a.target_uuid,
               a.target_snippet_id, a.parent_uuid::text AS parent_uuid, a.parent_type,
               a.weight, a.origin, a.description, e.name AS object_name,
               CASE WHEN a.alias_norm = %(q)s THEN 3
                    WHEN a.alias_norm LIKE %(q)s || '%%' THEN 2
                    ELSE 1 END AS rank
        FROM config_aliases a
        LEFT JOIN external_report e ON e.uuid = a.parent_uuid
        WHERE {' AND '.join(where)}
        ORDER BY rank DESC, a.weight DESC, a.alias_name
        LIMIT %(limit)s
    """
    try:
        with transaction() as cur:
            rows = fetch_rows(cur, sql, params)
            return {"success": True, "query": query, "found": len(rows), "rows": rows}
    except Exception as exc:
        return {"success": False, "error": f"Поиск алиасов не выполнен: {exc}"}


def resolve_config_alias(alias):
    """Разрешить алиас в цель (аналог get_alias_target_tool): только точное совпадение."""
    text = norm_alias(alias)
    if len(text) < MIN_ALIAS_WORD_LEN:
        return {"success": False, "error": f"Алиас {repr(alias)} слишком короткий"}
    try:
        with transaction() as cur:
            rows = fetch_rows(cur, """
                SELECT id, alias_name, target_type, target_name, target_uuid,
                       target_snippet_id, parent_uuid::text AS parent_uuid, parent_type,
                       weight, origin, description
                FROM config_aliases
                WHERE active AND alias_norm = %(q)s
                ORDER BY weight DESC, alias_name
            """, {"q": text})
            if not rows:
                return {"success": False, "alias": alias,
                        "error": "Активного алиаса с таким точным именем нет",
                        "hint": "Поиск по началу/середине - search_config_aliases_tool; "
                                "добавить алиас - add_config_aliases_tool."}
            return {"success": True, "alias": alias, "found": len(rows), "rows": rows}
    except Exception as exc:
        return {"success": False, "error": f"Алиас не разрешён: {exc}"}


def list_config_aliases(uuid=None, target_type=None, origin=None, limit=50,
                       include_inactive=False):
    """Список алиасов объекта (или всех) с фильтрами по цели и происхождению.

    По умолчанию только активные. include_inactive=True - чтобы оператор увидел
    снятые мягко строки (active=false) и убедился, что они не удалены физически.
    """
    limit = max(1, min(int(limit or 50), MAX_LIST_LIMIT))
    where = [] if include_inactive else ["a.active"]
    params = {"limit": limit}
    if uuid:
        where.append("a.parent_uuid = %(uuid)s::uuid")
        params["uuid"] = str(uuid)
    if target_type:
        where.append("a.target_type = %(target_type)s")
        params["target_type"] = target_type
    if origin:
        where.append("a.origin = %(origin)s")
        params["origin"] = origin
    sql = (f"SELECT a.id, a.alias_name, a.target_type, a.target_name, a.target_uuid, "
           f"a.target_snippet_id, a.parent_uuid::text AS parent_uuid, a.parent_type, "
           f"a.weight, a.origin, a.active, a.description, e.name AS object_name "
           f"FROM config_aliases a LEFT JOIN external_report e ON e.uuid = a.parent_uuid "
           f"{'WHERE ' + ' AND '.join(where) if where else ''} "
           f"ORDER BY a.parent_uuid, a.target_type, a.weight DESC, a.alias_name "
           f"LIMIT %(limit)s")
    try:
        with transaction() as cur:
            rows = fetch_rows(cur, sql, params)
            return {"success": True, "found": len(rows), "rows": rows}
    except Exception as exc:
        return {"success": False, "error": f"Список алиасов не получен: {exc}"}


def delete_config_alias(alias_id, hard=False):
    """Снять алиас. По умолчанию soft-delete (active=false) - как в local_doc.

    Soft-delete сохраняет строку: её видно в истории, и перегенерация её не восстанавливает.
    Жёсткое удаление (hard=True) - чтобы убрать ошибочный ручной алиас без следа.
    """
    try:
        with transaction() as cur:
            if hard:
                cur.execute("DELETE FROM config_aliases WHERE id = %s RETURNING id, alias_name",
                            (int(alias_id),))
                gone = cur.fetchone()
                if not gone:
                    return {"success": False, "error": f"Алиас id={alias_id} не найден"}
                return {"success": True, "mode": "hard", "id": gone[0], "alias_name": gone[1]}
            cur.execute("UPDATE config_aliases SET active = false WHERE id = %s "
                        "AND active RETURNING id, alias_name", (int(alias_id),))
            gone = cur.fetchone()
            if not gone:
                return {"success": False,
                        "error": f"Активный алиас id={alias_id} не найден "
                                 "(возможно, он уже снят с отметки)"}
            return {"success": True, "mode": "soft", "id": gone[0], "alias_name": gone[1],
                    "note": "строка осталась в таблице с active=false; поиск её не отдаёт, "
                            "перегенерация не восстанавливает и не удаляет"}
    except Exception as exc:
        return {"success": False, "error": f"Алиас не удалён: {exc}"}



