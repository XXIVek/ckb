#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API сниппетов, зависимостей и ссылок на documentation (узлы V17).

Пришёл на смену src/config_snippets_manager.py (он подключался к базе `configurations`,
которой на сервере нет). Разделение как в src/enrichment_aliases.py:

  * src/enrichment_generator.py - АВТОМАТИЧЕСКИЕ сниппеты (is_verified=false): их он снимает
    и пишет заново;
  * этот модуль - РАБОТА ОПЕРАТОРА и анализ: добавить сниппет вручную (is_verified=true,
    перегенерация его не трогает), найти, посмотреть, удалить; прочитать зависимости;
    поставить и прочитать ссылку на documentation local_doc; посчитать статистику.

Цель сниппета и его источник описаны отдельными колонками (source_kind/source_uuid/
source_path - ОТКУДА код, target_type/target_uuid - О ЧЁМ он). Порог отбора объявлений
(MIN_BODY_LINES) принадлежит генератору, здесь он не применяется: ручной сниппет оператор
сознательно короче или длиннее автоматного.

Удаление сниппета - hard-delete. Единственный FK подсистемы (config_snippet_dependencies.
snippet_id) уводит зависимости каскадом; алиасы с target_snippet_id снимаются явно, потому
что FK на них нет (связь полиморфная, решение E3).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from external_db import connect, transaction  # noqa: E402

from external_table_writer import (  # noqa: E402
    ConfigCrossReferenceRowWriter,
    ConfigSnippetDependencyRowWriter,
    ConfigSnippetRowWriter,
)
from enrichment_generator import (  # noqa: E402
    fetch_rows,
    fetch_value,
    norm_alias,
    object_row,
    resolve_object,
)

MAX_LIST_LIMIT = 500
TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё_]+")



def _resolve_uuid(cur, uuid, source_path):
    """Разобрать адрес объекта и убедиться, что он в external_report. (uuid, карточка) или ошибка."""
    resolved = resolve_object(uuid=uuid, source_path=source_path)
    if not resolved.get("success"):
        return None, resolved
    obj = object_row(cur, resolved["uuid"])
    if not obj:
        return None, {"success": False,
                      "error": f"Внешний объект с uuid={resolved['uuid']} в external_report не найден",
                      "hint": "Загрузите каталог load_1c_catalog_tool(source_path=...), затем "
                              "generate_config_enrichment_tool(source_path=...)."}
    return resolved["uuid"], obj


def _parse_dependencies(text):
    """Разобрать строку зависимостей 'Type:Name; Type:Name' в список словарей."""
    rows = []
    for part in str(text or "").replace("\n", ";").split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        target_type, target_name = part.split(":", 1)
        target_type, target_name = target_type.strip(), target_name.strip()
        if not target_type or not target_name:
            continue
        rows.append({"dependency_type": "references", "target_type": target_type,
                     "target_name": target_name, "target_uuid": None})
    return rows




TARGET_TABLES = {
    "Attribute": ("attributes", "name"),
    "TabularSection": ("tabular_sections", "name"),
    "Form": ("forms", "name"),
    "Template": ("templates", "name"),
}


def _known_target(cur, obj_uuid, target_type, target_name, target_uuid):
    """Проверить, что цель зависимости реально есть в сохранённом содержимом объекта.

    Ручные зависимости оператор задаёт по имени; без проверки опечатка создала бы связь,
    которая ни на что не указывает. Для целей вне таблиц выгрузки (FormItem, Module,
    ConfigSnippet, ExternalReport) проверка идёт по своим источникам.
    """
    if target_type in TARGET_TABLES:
        table, column = TARGET_TABLES[target_type]
        rows = fetch_rows(cur, f"SELECT 1 AS ok FROM {table} WHERE parent_uuid = %s::uuid "
                               f"AND lower({column}) = lower(%s) LIMIT 1", (obj_uuid, target_name))
        return bool(rows)
    if target_type in ("FormItem", "Module"):
        # Единый источник проверки - та же функция, что проставляет target_uuid (R: одна цель
        # не должна описываться двумя запросами). Раньше здесь был свой запрос, и он расходился
        # с _resolve_target_uuid: для Module принимались только module_type/file_path из
        # bsl_modules, поэтому зависимость "Module:<ИмяФормы>" (модуль формы лежит в form_ext,
        # а не в bsl_modules) отклонялась, хотя резолвилась она корректно. Разбор FormItem
        # (qualified 'Форма.Элемент' и голое имя) в _resolve_target_uuid уже полный.
        return _resolve_target_uuid(cur, obj_uuid, target_type, target_name) is not None
    if target_type == "ConfigSnippet":
        try:
            rows = fetch_rows(cur, "SELECT 1 AS ok FROM config_snippets WHERE id = %s LIMIT 1",
                              (int(target_uuid),))
        except (TypeError, ValueError):
            return False
        return bool(rows)
    if target_type == "ExternalReport":
        return norm_alias(target_uuid or "") == norm_alias(obj_uuid)
    return False


def _resolve_target_uuid(cur, obj_uuid, target_type, target_name):
    """Стабильный ключ цели зависимости по её имени (или None, если цели нет).

    Формат ключей совпадает с src/enrichment_generator.py, иначе одна и та же цель
    описывалась бы по-разному в алиасах, зависимостях и витрине: uuid строки таблицы
    выгрузки для реквизита/ТЧ/формы/макета, 'form_item:<uuid формы>:<элемент>' для
    элемента формы, 'module:form:<uuid формы>' или 'module:<id bsl_modules>' для модуля.
    Без target_uuid зависимость остаётся «именной» и не находится при обращении по uuid.
    """
    if target_type in TARGET_TABLES:
        table, column = TARGET_TABLES[target_type]
        return fetch_value(cur, f"SELECT uuid::text FROM {table} "
                                f"WHERE parent_uuid = %s::uuid AND lower({column}) = lower(%s) "
                                "LIMIT 1", (obj_uuid, target_name))
    if target_type == "FormItem":
        # имя цели принимается и qualified ('Форма.Элемент'), и bare ('Элемент'):
        # витрина и генератор отдают qualified, но голое имя тоже удобно оператору
        form_name, _, item_name = str(target_name or "").partition(".")
        if not item_name:
            form_name, item_name = "", target_name
        sql = """
            SELECT f.uuid::text AS form_uuid, e->>'name' AS item_name
            FROM form_ext fe
            JOIN forms f ON f.id = fe.form_id
            CROSS JOIN LATERAL jsonb_array_elements(fe.items) AS e
            WHERE fe.parent_uuid = %s::uuid AND jsonb_typeof(fe.items) = 'array'
        """
        params = [obj_uuid]
        if form_name:
            sql += " AND lower(coalesce(fe.name, '')) = lower(%s)"
            params.append(form_name)
        sql += " AND lower(coalesce(e->>'name', '')) = lower(%s) LIMIT 1"
        params.append(item_name)
        rows = fetch_rows(cur, sql, tuple(params))
        if not rows:
            return None
        return f"form_item:{rows[0]['form_uuid']}:{rows[0]['item_name']}"
    if target_type == "Module":
        form_key = fetch_value(cur, "SELECT 'module:form:' || f.uuid::text AS key FROM forms f "
                                    "WHERE f.parent_uuid = %s::uuid "
                                    "AND lower(coalesce(f.name, '')) = lower(%s) LIMIT 1",
                               (obj_uuid, target_name))
        if form_key:
            return form_key
        module_id = fetch_value(cur, "SELECT id FROM bsl_modules WHERE parent_uuid = %s::uuid "
                                     "AND (lower(coalesce(module_name, '')) = lower(%s) "
                                     "OR lower(coalesce(module_type, '')) = lower(%s) "
                                     "OR lower(coalesce(file_path, '')) = lower(%s)) LIMIT 1",
                                (obj_uuid, target_name, target_name, target_name))
        return f"module:{module_id}" if module_id else None
    return None


def add_config_snippet(question, answer, uuid=None, source_path=None, source_kind="manual",
                       source_uuid=None, source_file=None, target_type=None, target_uuid=None,
                       tags=None, confidence=1.0, dependencies=None):
    """Добавить сниппет вручную (is_verified=true) - перегенерация его не снимает.

    Порог MIN_BODY_LINES генератора здесь не применяется: фрагмент оператор подбирает сам.
    Зависимости задаются строкой 'Type:Name; Type:Name' и проверяются по сохранённому
    содержимому объекта, чтобы опечатка не создала связь вникуда.
    """
    if not str(question or "").strip() or not str(answer or "").strip():
        return {"success": False, "error": "Нужны непустые question и answer"}
    parsed_deps = _parse_dependencies(dependencies)
    # повторы в списке зависимостей не роняют добавление: уникальность держит индекс
    # uq_config_snippet_deps, а оператор мог указать одну цель в двух написаниях
    dep_rows, duplicate_deps, _seen = [], [], set()
    for dep in parsed_deps:
        key = (dep["dependency_type"], dep["target_type"], norm_alias(dep["target_name"]))
        if key in _seen:
            duplicate_deps.append(f"{dep['target_type']}:{dep['target_name']}")
            continue
        _seen.add(key)
        dep_rows.append(dep)
    if isinstance(tags, str):
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    else:
        tag_list = [str(t).strip() for t in (tags or []) if str(t).strip()]
    try:
        with transaction() as cur:
            obj_uuid, obj = _resolve_uuid(cur, uuid, source_path)
            if obj_uuid is None:
                return obj
            dup = fetch_rows(cur, "SELECT id FROM config_snippets WHERE parent_uuid = %s::uuid "
                                  "AND source_kind = %s AND COALESCE(source_uuid, '') = "
                                  "COALESCE(%s, '') AND question = %s LIMIT 1",
                             (obj_uuid, source_kind, source_uuid, question))
            if dup:
                return {"success": False, "already_exists": True, "id": dup[0]["id"],
                        "error": "Сниппет с таким question и источником у объекта уже есть",
                        "hint": "Создайте сниппет с другим question или удалите старый "
                                "delete_config_snippet_tool."}
            bad = [dep for dep in dep_rows
                   if not _known_target(cur, obj_uuid, dep["target_type"], dep["target_name"],
                                        dep.get("target_uuid"))]
            if bad:
                return {"success": False,
                        "error": "Цели зависимостей не найдены среди сохранённого содержимого "
                                 "объекта: " + "; ".join(f"{d['target_type']}:{d['target_name']}"
                                                         for d in bad),
                        "hint": "Список целей: v_config_enrichment, таблицы attributes, "
                                "tabular_sections, forms, form_ext (items), templates, "
                                "bsl_modules."}
            # цель существует - укрепляем её стабильным ключом. Зависимость, заведённую по
            # имени, ищут и по target_uuid; ключ тот же, что у генератора и витрины,
            # иначе одна цель описывается по-разному в алиасах, зависимостях и витрине.
            for dep in dep_rows:
                if not dep.get("target_uuid"):
                    dep["target_uuid"] = _resolve_target_uuid(cur, obj_uuid, dep["target_type"],
                                                              dep["target_name"])
            # Вторая волна дублей - по стабильному ключу, а не по написанию имени. Индекс
            # uq_config_snippet_deps держит уникальность по (snippet_id, dependency_type,
            # target_type, target_name), поэтому 'FormItem:Форма.Элемент' и 'FormItem:Элемент'
            # (одна цель, один target_uuid, разные target_name) прошли бы как две разных
            # зависимости. Для целей без стабильного ключа остаётся сравнение по имени.
            unique_rows, stable_seen = [], set()
            for dep in dep_rows:
                stable = (dep["target_type"],
                          str(dep.get("target_uuid") or norm_alias(dep["target_name"])).lower())
                if stable in stable_seen:
                    duplicate_deps.append(f"{dep['target_type']}:{dep['target_name']}")
                    continue
                stable_seen.add(stable)
                unique_rows.append(dep)
            dep_rows = unique_rows
            row = {
                "parent_uuid": obj_uuid,
                "parent_type": "external_report",
                "question": str(question).strip(),
                "answer": str(answer),
                "source_kind": source_kind,
                "source_uuid": source_uuid,
                "source_path": source_file,
                "target_type": target_type,
                "target_uuid": target_uuid,
                "tags": tag_list,
                "confidence": float(confidence),
                "is_verified": True,
            }
            snippet_id = ConfigSnippetRowWriter.insert(cur, row)
            for dep in dep_rows:
                dep["snippet_id"] = snippet_id
            deps_inserted = ConfigSnippetDependencyRowWriter.insert_many(cur, dep_rows)
            return {"success": True, "id": snippet_id, "uuid": obj_uuid,
                    "object_name": obj.get("name"), "source_kind": source_kind,
                    "is_verified": True, "question": row["question"],
                    "answer_size": len(row["answer"]), "dependencies": deps_inserted,
                    "duplicate_dependencies": duplicate_deps,
                    "note": "помечен is_verified=true, переживает перегенерацию"}
    except Exception as exc:
        return {"success": False, "error": f"Сниппет не добавлен (полный откат): {exc}"}


def _snippet_dependencies(cur, snippet_id):
    """Зависимости сниппета - отдельный запрос, чтобы карточка читалась по частям."""
    return fetch_rows(cur, "SELECT dependency_type, target_type, target_name, target_uuid "
                           "FROM config_snippet_dependencies WHERE snippet_id = %s "
                           "ORDER BY target_type, target_name", (snippet_id,))


def get_config_snippet(snippet_id):
    """Полная карточка сниппета: код целиком, зависимости, алиасы, ссылки на documentation."""
    try:
        with transaction() as cur:
            rows = fetch_rows(cur, """
                SELECT s.id, s.parent_uuid::text AS parent_uuid, s.parent_type, s.question,
                       s.answer, s.source_kind, s.source_uuid, s.source_path, s.target_type,
                       s.target_uuid, s.tags, s.confidence, s.is_verified,
                       e.name AS object_name
                FROM config_snippets s
                LEFT JOIN external_report e ON e.uuid = s.parent_uuid
                WHERE s.id = %s
            """, (int(snippet_id),))
            if not rows:
                return {"success": False, "error": f"Сниппет id={snippet_id} не найден"}
            card = rows[0]
            card["dependencies"] = _snippet_dependencies(cur, int(snippet_id))
            card["aliases"] = fetch_rows(cur, "SELECT id, alias_name, weight, origin "
                                              "FROM config_aliases WHERE target_snippet_id = %s "
                                              "AND active ORDER BY weight DESC, alias_name",
                                         (int(snippet_id),))
            card["doc_links"] = fetch_rows(cur, "SELECT id, local_doc_kind, local_doc_id, "
                                                "target_type, reference_type "
                                                "FROM config_cross_references "
                                                "WHERE parent_uuid = %s::uuid AND target_uuid = %s "
                                                "ORDER BY id",
                                           (card["parent_uuid"], f"snippet:{snippet_id}"))
            return {"success": True, "found": 1, "row": card}
    except Exception as exc:
        return {"success": False, "error": f"Сниппет не получен: {exc}"}


def list_config_snippets(uuid=None, source_kind=None, limit=20, only_verified=False):
    """Список сниппетов объекта БЕЗ кода целиком (размер и начало): код бывает десятки КБ.

    only_verified=True - только ручные (is_verified=true), их перегенерация не снимает;
    source_kind='manual' даёт тот же результат для сниппетов, добавленных оператором.
    """
    limit = max(1, min(int(limit or 20), MAX_LIST_LIMIT))
    where = ["TRUE"]
    params = {"limit": limit}
    if uuid:
        where.append("s.parent_uuid = %(uuid)s::uuid")
        params["uuid"] = str(uuid)
    if source_kind:
        where.append("s.source_kind = %(source_kind)s")
        params["source_kind"] = source_kind
    if only_verified:
        where.append("s.is_verified")
    sql = (f"SELECT s.id, s.parent_uuid::text AS parent_uuid, s.source_kind, s.source_uuid, "
           f"s.source_path, s.question, s.tags, s.confidence, s.is_verified, "
           f"length(s.answer) AS answer_size, left(s.answer, 300) AS answer_preview, "
           f"e.name AS object_name, "
           f"(SELECT count(*) FROM config_snippet_dependencies d WHERE d.snippet_id = s.id) "
           f"AS dependencies "
           f"FROM config_snippets s LEFT JOIN external_report e ON e.uuid = s.parent_uuid "
           f"WHERE {' AND '.join(where)} "
           f"ORDER BY s.parent_uuid, s.source_kind, s.question LIMIT %(limit)s")
    try:
        with transaction() as cur:
            rows = fetch_rows(cur, sql, params)
            return {"success": True, "found": len(rows), "rows": rows}
    except Exception as exc:
        return {"success": False, "error": f"Список сниппетов не получен: {exc}"}


def search_config_snippets(query, uuid=None, limit=10):
    """Найти сниппеты: полнотекстовый поиск по tsv; при пустом результате - подстрока.

    tsv построена базой по конфигу simple (идентификаторы 1С не склоняются), поэтому запрос
    собирается из токенов с оператором начала слова 'токен:*' - без него префикс не работает
    (проверено на FTS local_doc: форма 'слово*' оператор * теряет).
    Подстрока - запасной путь: она находит то, чего FTS не видит (часть идентификатора).
    """
    tokens = [token.lower() for token in TOKEN_RE.findall(str(query or "")) if len(token) >= 3]
    if not tokens:
        return {"success": False,
                "error": f"Из запроса {repr(query)} не получилось ни одного слова "
                         "длиннее 2 символов"}
    limit = max(1, min(int(limit or 10), MAX_LIST_LIMIT))
    scope_where = []
    params = {"limit": limit}
    if uuid:
        scope_where.append("s.parent_uuid = %(uuid)s::uuid")
        params["uuid"] = str(uuid)
    scope = (" AND " + " AND ".join(scope_where)) if scope_where else ""
    columns = ("s.id, s.parent_uuid::text AS parent_uuid, s.source_kind, s.source_path, "
               "s.question, s.tags, s.is_verified, length(s.answer) AS answer_size, "
               "left(s.answer, 300) AS answer_preview, e.name AS object_name")
    fts_sql = (f"SELECT {columns}, ts_rank(s.tsv, %(tsq)s::tsquery) AS rank "
               f"FROM config_snippets s LEFT JOIN external_report e ON e.uuid = s.parent_uuid "
               f"WHERE s.tsv @@ %(tsq)s::tsquery{scope} "
               f"ORDER BY rank DESC, s.question LIMIT %(limit)s")
    sub_sql = (f"SELECT {columns}, 0.0 AS rank "
               f"FROM config_snippets s LEFT JOIN external_report e ON e.uuid = s.parent_uuid "
               f"WHERE position(%(word)s IN lower(s.question || ' ' || s.answer)) > 0{scope} "
               f"ORDER BY s.question LIMIT %(limit)s")
    try:
        with transaction() as cur:
            tsquery = " & ".join(f"{token}:*" for token in tokens)
            rows = fetch_rows(cur, fts_sql, dict(params, tsq=tsquery))
            mode = "fts"
            if not rows:
                mode = "substring"
                rows = fetch_rows(cur, sub_sql, dict(params, word=tokens[0]))
            return {"success": True, "query": query, "mode": mode, "tsquery": tsquery,
                    "found": len(rows), "rows": rows}
    except Exception as exc:
        return {"success": False, "error": f"Поиск сниппетов не выполнен: {exc}"}


def delete_config_snippet(snippet_id):
    """Удалить сниппет (hard-delete). Зависимости уходят FK-каскадом, алиасы - явно.

    Алиасы с target_snippet_id удаляются отдельно: FK на них нет, связь полиморфная (E3).
    Если удалить авто-сниппет (is_verified=false), следующая генерация создаст его заново -
    он построен из исходного кода выгрузки. Чтобы строка осталась удалённой навсегда,
    нужен ручной сниппет (is_verified=true) или правка исходника.
    """
    try:
        with transaction() as cur:
            rows = fetch_rows(cur, "SELECT id, question, is_verified, source_kind, "
                                   "parent_uuid::text AS parent_uuid FROM config_snippets "
                                   "WHERE id = %s", (int(snippet_id),))
            if not rows:
                return {"success": False, "error": f"Сниппет id={snippet_id} не найден"}
            card = rows[0]
            cur.execute("DELETE FROM config_aliases WHERE target_snippet_id = %s RETURNING id",
                        (int(snippet_id),))
            aliases_removed = len(cur.fetchall())
            cur.execute("SELECT count(*) FROM config_snippet_dependencies WHERE snippet_id = %s",
                        (int(snippet_id),))
            dependencies_removed = cur.fetchone()[0]
            cur.execute("DELETE FROM config_cross_references WHERE parent_uuid = %s::uuid "
                        "AND target_uuid = %s RETURNING id",
                        (card["parent_uuid"], f"snippet:{snippet_id}"))
            links_removed = len(cur.fetchall())
            cur.execute("DELETE FROM config_snippets WHERE id = %s RETURNING id",
                        (int(snippet_id),))
            if not cur.fetchone():
                return {"success": False, "error": f"Сниппет id={snippet_id} не удалён"}
            return {"success": True, "id": int(snippet_id), "question": card["question"],
                    "is_verified": card["is_verified"], "source_kind": card["source_kind"],
                    "children_deleted": {"aliases": aliases_removed,
                                         "dependencies": dependencies_removed,
                                         "doc_links": links_removed},
                    "note": ("это авто-сниппет (is_verified=false): следующая генерация "
                             "создаст его заново из исходного кода"
                             if not card["is_verified"] else
                             "ручной сниппет (is_verified=true): перегенерация его не создаёт")}
    except Exception as exc:
        return {"success": False, "error": f"Сниппет не удалён: {exc}"}


def get_snippets_for_object(uuid=None, source_path=None, target_type=None, target_name=None):
    """Найти сниппеты, которые ссылаются на указанную цель (через config_snippet_dependencies)."""
    if not target_type:
        return {"success": False, "error": "Нужен target_type цели (Attribute, FormItem, ...)"}
    try:
        with transaction() as cur:
            obj_uuid, obj = _resolve_uuid(cur, uuid, source_path)
            if obj_uuid is None:
                return obj
            if not target_name:
                return {"success": False,
                        "error": f"Нужен target_name цели для target_type='{target_type}'"}
            rows = fetch_rows(cur, """
                SELECT s.id, s.question, s.source_kind, s.source_path, s.is_verified,
                       length(s.answer) AS answer_size, left(s.answer, 300) AS answer_preview,
                       d.dependency_type, d.target_type, d.target_name, d.target_uuid
                FROM config_snippet_dependencies d
                JOIN config_snippets s ON s.id = d.snippet_id
                WHERE s.parent_uuid = %s::uuid AND d.target_type = %s
                  AND lower(d.target_name) = lower(%s)
                ORDER BY s.question
            """, (obj_uuid, target_type, target_name))
            return {"success": True, "uuid": obj_uuid, "object_name": obj.get("name"),
                    "target_type": target_type, "target_name": target_name,
                    "found": len(rows), "rows": rows}
    except Exception as exc:
        return {"success": False, "error": f"Сниппеты цели не получены: {exc}"}


LOCAL_DOC_TABLES = {"group": ("groups", "pagetitle", "name"),
                    "snippet": ("knowledge_snippets", "question", "question")}


def _check_local_doc(local_doc_kind, local_doc_id):
    """Проверить указатель в ДРУГУЮ базу local_doc: (найдено?, заголовок, примечание).

    FK через границы баз не работает (FDW/dblink в кластере нет, решение E5), поэтому
    целостность проверяет этот отдельный запрос. Если local_doc недоступна, указатель всё
    равно сохраняется: связь нужна для последующего чтения, а недоступная база - не причина
    отказывать, но в ответе это честно указано.
    """
    if local_doc_kind not in LOCAL_DOC_TABLES:
        return False, None, (f"local_doc_kind='{local_doc_kind}' недопустима: "
                             "ожидается 'group' или 'snippet'")
    table, title_column, fallback_column = LOCAL_DOC_TABLES[local_doc_kind]
    try:
        conn = connect("local_doc")
    except Exception as exc:
        return None, None, f"local_doc недоступна ({exc}), указатель сохранён без проверки"
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT coalesce({title_column}, {fallback_column}) FROM {table} "
                       "WHERE id = %s", (int(local_doc_id),))
        record = cursor.fetchone()
    except Exception as exc:
        return None, None, f"указатель не проверен ({exc}), строка сохранена"
    finally:
        conn.close()
    if not record:
        return False, None, (f"в базе local_doc строки {table}.id={local_doc_id} нет - "
                             "ссылка битая, схема её через границы баз не проверяет")
    return True, record[0], None


def add_config_cross_reference(uuid=None, source_path=None, local_doc_kind="group",
                               local_doc_id=None, target_type="ExternalReport",
                               target_name=None, target_uuid=None,
                               reference_type="linked_to"):
    """Поставить указатель documentation (local_doc) -> конкретная цель объекта выгрузки.

    Цель по умолчанию - сам внешний объект; для сниппета указывают
    target_type='ConfigSnippet' и target_uuid='snippet:<id>' (ту же запись цели читает
    get_config_snippet). Дубликат (та же пара local_doc + цель) не создаётся.
    """
    if not local_doc_id:
        return {"success": False, "error": "Нужен local_doc_id - id строки в базе local_doc"}
    try:
        doc_id = int(local_doc_id)
    except (TypeError, ValueError):
        return {"success": False, "error": f"local_doc_id={repr(local_doc_id)} не целое число"}
    if local_doc_kind not in LOCAL_DOC_TABLES:
        return {"success": False,
                "error": f"local_doc_kind='{local_doc_kind}' недопустима: "
                         "ожидается 'group' или 'snippet'"}
    try:
        with transaction() as cur:
            obj_uuid, obj = _resolve_uuid(cur, uuid, source_path)
            if obj_uuid is None:
                return obj
            resolved_uuid = target_uuid or (obj_uuid if target_type == "ExternalReport" else None)
            resolved_name = target_name or (obj.get("name")
                                           if target_type == "ExternalReport" else None)
            exists = fetch_rows(cur, "SELECT id FROM config_cross_references WHERE "
                                     "local_doc_kind = %s AND local_doc_id = %s "
                                     "AND target_type = %s AND COALESCE(target_uuid, '') = "
                                     "COALESCE(%s, '') LIMIT 1",
                                (local_doc_kind, doc_id, target_type, resolved_uuid))
            if exists:
                return {"success": False, "already_exists": True, "id": exists[0]["id"],
                        "error": "Такая связь documentation с этой целью уже есть"}
            found, title, note = _check_local_doc(local_doc_kind, doc_id)
            if found is False:
                return {"success": False, "error": note,
                        "hint": "Указатель не сохранён: связь вникуда только замусоривает "
                                "анализ. Проверьте id по базе local_doc."}
            row = {"local_doc_kind": local_doc_kind, "local_doc_id": doc_id,
                   "target_type": target_type, "target_name": resolved_name,
                   "target_uuid": resolved_uuid, "parent_uuid": obj_uuid,
                   "reference_type": reference_type}
            ref_id = ConfigCrossReferenceRowWriter.insert(cur, row)
            result = {"success": True, "id": ref_id, "uuid": obj_uuid,
                      "object_name": obj.get("name"), "local_doc_kind": local_doc_kind,
                      "local_doc_id": doc_id, "target_type": target_type,
                      "target_name": resolved_name, "target_uuid": resolved_uuid,
                      "reference_type": reference_type}
            if title:
                result["local_doc_title"] = title
            if note:
                result["warning"] = note
            return result
    except Exception as exc:
        return {"success": False, "error": f"Связь не создана (полный откат): {exc}"}


def get_config_cross_references(uuid=None, local_doc_id=None, limit=50):
    """Прочитать связи: по объекту выгрузки (uuid) или по элементу documentation (local_doc_id).

    Каждая строка сопровождается проверкой указателя в local_doc: связь могла остаться после
    пересоздания базы документации, и молча отдавать её как валидную - значит врать.
    """
    limit = max(1, min(int(limit or 50), MAX_LIST_LIMIT))
    where = ["TRUE"]
    params = {"limit": limit}
    if uuid:
        where.append("x.parent_uuid = %(uuid)s::uuid")
        params["uuid"] = str(uuid)
    if local_doc_id:
        where.append("x.local_doc_id = %(doc_id)s")
        params["doc_id"] = int(local_doc_id)
    sql = (f"SELECT x.id, x.local_doc_kind, x.local_doc_id, x.target_type, x.target_name, "
           f"x.target_uuid, x.parent_uuid::text AS parent_uuid, x.reference_type, "
           f"e.name AS object_name FROM config_cross_references x "
           f"LEFT JOIN external_report e ON e.uuid = x.parent_uuid "
           f"WHERE {' AND '.join(where)} ORDER BY x.local_doc_kind, x.local_doc_id "
           f"LIMIT %(limit)s")
    try:
        with transaction() as cur:
            rows = fetch_rows(cur, sql, params)
            for row in rows:
                found, title, note = _check_local_doc(row["local_doc_kind"], row["local_doc_id"])
                row["local_doc_found"] = found
                if title:
                    row["local_doc_title"] = title
                if note:
                    row["local_doc_note"] = note
            return {"success": True, "found": len(rows), "rows": rows}
    except Exception as exc:
        return {"success": False, "error": f"Связи не получены: {exc}"}


def delete_config_cross_reference(reference_id):
    """Снять связь documentation (указатель нужен для чтения, FK здесь ни при чём)."""
    try:
        with transaction() as cur:
            cur.execute("DELETE FROM config_cross_references WHERE id = %s "
                        "RETURNING id, local_doc_kind, local_doc_id, target_type",
                        (int(reference_id),))
            gone = cur.fetchone()
            if not gone:
                return {"success": False, "error": f"Связь id={reference_id} не найдена"}
            return {"success": True, "mode": "hard", "id": gone[0],
                    "local_doc_kind": gone[1], "local_doc_id": gone[2],
                    "target_type": gone[3]}
    except Exception as exc:
        return {"success": False, "error": f"Связь не удалена: {exc}"}


def enrichment_stats(uuid=None, limit=20):
    """Сводка по обогащению: счётчики витрины v_config_enrichment плюс разбивка по объектам.

    Для одного объекта (uuid) добавляется разбивка: алиасы по происхождению (generated/manual)
    и типам целей, сниппеты по источникам и по is_verified, зависимости по типам целей, а также
    сироты - алиасы, оставшиеся после удаления сниппета. Витрина считает только то, что видно
    из БД; она не знает, сколько терминов знал пользователь и не покрыл генератор.
    """
    limit = max(1, min(int(limit or 20), MAX_LIST_LIMIT))
    where = ["TRUE"]
    params = {"limit": limit}
    if uuid:
        where.append("v.report_uuid = %(uuid)s::uuid")
        params["uuid"] = str(uuid)
    try:
        with transaction() as cur:
            objects = fetch_rows(cur, f"SELECT v.* FROM v_config_enrichment v "
                                      f"WHERE {' AND '.join(where)} "
                                      f"ORDER BY v.report_name LIMIT %(limit)s", params)
            result = {"success": True, "objects": objects}
            # Узел V20.1: привязки к конфигурации. Витрина v_config_enrichment говорит только
            # про обогащение и о конфигурации ничего не знает, поэтому привязки читаются
            # отдельным запросом к external_report с тем же CASE, что у карточки объекта:
            # сводка и карточка обязаны называть состояние одинаково. Обратный перечень нужен
            # потому, что снятие FK делает возможным состояние «битая ссылка», и его чем-то
            # надо искать: перепривязка начинается со вопроса «какие объекты привязаны к N» и
            # «где ссылки битые».
            cfg_where = ["TRUE"]
            if uuid:
                cfg_where.append("er.uuid = %(uuid)s::uuid")
            result["configuration_links"] = fetch_rows(
                cur,
                "SELECT er.id AS report_id, er.uuid::text AS report_uuid, "
                "       er.name AS report_name, er.configuration_id, "
                "       cfg.name AS configuration_name, cfg.version AS configuration_version, "
                "       CASE WHEN er.configuration_id IS NULL THEN 'not_declared' "
                "            WHEN cfg.id IS NULL THEN 'dangling' "
                "            ELSE 'bound' END AS configuration_state "
                "FROM external_report er "
                "LEFT JOIN configurations cfg ON cfg.id = er.configuration_id "
                f"WHERE {' AND '.join(cfg_where)} ORDER BY er.name LIMIT %(limit)s", params)
            if uuid:
                result["configuration"] = (result["configuration_links"] or [{}])[0]
            if not uuid:
                totals = fetch_rows(cur, "SELECT count(*) AS objects, "
                                         "coalesce(sum(aliases_total), 0) AS aliases, "
                                         "coalesce(sum(snippets), 0) AS snippets, "
                                         "coalesce(sum(snippet_dependencies), 0) AS dependencies, "
                                         "coalesce(sum(doc_links), 0) AS doc_links "
                                         "FROM v_config_enrichment")
                result["totals"] = totals[0] if totals else {}
                # счётчики состояний привязки по всей базе: «битых» обязано быть 0 в healthy
                # состоянии, и именно их показывает инвентарная SQL-сверка
                binding = fetch_rows(cur,
                    "SELECT count(*) FILTER (WHERE er.configuration_id IS NULL) "
                    "           AS configuration_not_declared, "
                    "       count(*) FILTER (WHERE er.configuration_id IS NOT NULL "
                    "                            AND cfg.id IS NOT NULL) AS configuration_bound, "
                    "       count(*) FILTER (WHERE er.configuration_id IS NOT NULL "
                    "                            AND cfg.id IS NULL) AS configuration_dangling "
                    "FROM external_report er "
                    "LEFT JOIN configurations cfg ON cfg.id = er.configuration_id")
                result["totals"].update(binding[0] if binding else {})
                result["configurations"] = fetch_rows(
                    cur, "SELECT c.id, c.name, c.version, "
                         "(SELECT count(*) FROM external_report er "
                         "  WHERE er.configuration_id = c.id) AS bound_objects "
                         "FROM configurations c ORDER BY c.name LIMIT %(l)s",
                    {"l": MAX_LIST_LIMIT})
                return result
            obj_uuid = str(uuid)
            result["aliases_by_origin"] = fetch_rows(
                cur, "SELECT origin, count(*) AS cnt FROM config_aliases "
                     "WHERE parent_uuid = %s::uuid GROUP BY origin ORDER BY origin", (obj_uuid,))
            result["aliases_by_target"] = fetch_rows(
                cur, "SELECT target_type, count(*) AS cnt FROM config_aliases "
                     "WHERE parent_uuid = %s::uuid AND active "
                     "GROUP BY target_type ORDER BY cnt DESC, target_type", (obj_uuid,))
            result["snippets_by_source"] = fetch_rows(
                cur, "SELECT source_kind, is_verified, count(*) AS cnt, "
                     "sum(length(answer)) AS answer_chars FROM config_snippets "
                     "WHERE parent_uuid = %s::uuid "
                     "GROUP BY source_kind, is_verified ORDER BY source_kind", (obj_uuid,))
            result["dependencies_by_target"] = fetch_rows(
                cur, "SELECT d.target_type, count(*) AS cnt FROM config_snippet_dependencies d "
                     "JOIN config_snippets s ON s.id = d.snippet_id "
                     "WHERE s.parent_uuid = %s::uuid GROUP BY d.target_type "
                     "ORDER BY cnt DESC, d.target_type", (obj_uuid,))
            result["orphans"] = fetch_rows(
                cur, "SELECT count(*) AS aliases_without_snippet FROM config_aliases a "
                     "WHERE a.parent_uuid = %s::uuid AND a.target_snippet_id IS NOT NULL "
                     "AND NOT EXISTS (SELECT 1 FROM config_snippets s "
                     "WHERE s.id = a.target_snippet_id)", (obj_uuid,))
            return result
    except Exception as exc:
        return {"success": False, "error": f"Сводка не получена: {exc}"}










