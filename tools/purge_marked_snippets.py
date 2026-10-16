#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел Q2 (16.10.2026): снять карантин жёстким удалением.

Карантин (узел Q1, раздел 14 docs/CONFIGURATIONS_ENRICHMENT_PLAN.md) — мягкая пометка
`mark-for-deletion`: строка остаётся в БД, но скрыта из поиска и списков. Она остаётся
ровно до явного решения оператора: ни генерация обогащения, ни поиск её не снимают.
Этот скрипт — единственный штатный путь превратить пометку в удаление.

По умолчанию работает в режиме просмотра (dry-run): показывает, что будет снято, и ничего
не меняет. Запись выполняется только с `--apply`.

Что снимается и чем:
  * `ckb_1c_configurations.config_snippets` — контрактной операцией
    `src/enrichment_snippets.delete_config_snippet` (тот же путь, что у
    `delete_config_snippet_tool`: сниппет + его алиасы, зависимости и ссылки documentation).
    Дублировать SQL удаления здесь нельзя: семантика должна остаться одной;
  * `local_doc.knowledge_snippets` — прямого MCP-инструмента удаления нет (его не было и до
    карантина), поэтому удаление идёт SQL, а алиасы уходят каскадом FK
    (`alias_targets_snippets_id_fkey ON DELETE CASCADE` — замер 16.10.2026). Строки аудита
    (`audit_log`) по умолчанию снимаются вместе со сниппетом; `--keep-audit` оставляет их,
    отвязав от удалённого сниппета (`snippet_id = NULL`).

Что скрипт показывает отдельно (и это не «удаление не удалось»):
  * указатели `config_cross_references` в `ckb_1c_configurations`, ведущие на снятые строки
    `local_doc`: внешнего ключа через базы нет (FDW нет), поэтому битые ссылки остаются и
    называются при чтении. Снимает их `delete_config_cross_reference_tool`.

Запуск (UTF-8 в консоли обязателен):
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python tools/purge_marked_snippets.py                      # только показать
    python tools/purge_marked_snippets.py --dry-run            # то же, но явно
    python tools/purge_marked_snippets.py --apply              # снять во всех базах
    python tools/purge_marked_snippets.py --db ckb --apply     # только enrich-контур
    python tools/purge_marked_snippets.py --db local_doc --keep-audit --apply
    python tools/purge_marked_snippets.py --uuid <uuid объекта> --limit 5

Код возврата: 0 — работа выполнена (в том числе когда помеченных нет), 1 — шаг записи упал
(в этом случае полный откат по этому шагу, частично ничего не снимается).
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import psycopg2
from psycopg2.extras import RealDictCursor

from external_db import db_config
from enrichment_snippets import delete_config_snippet, list_marked_config_snippets
# Имена — из src/quarantine.py (узел Q3): MARKER — текст метки, MARK_ARRAY — её текстовый
# массив для SQL-параметра %(mark)s, MARK_TAG_PARAM — имя параметра, под которым метку
# передают вместе с reason_expr_named. Таких имён, как MARK_TAG / mark_reason / MARKED_COND,
# в модуле нет: импорт несуществующего имени ронял весь скрипт на старте.
from quarantine import (MARKER, MARK_ARRAY, MARK_TAG_PARAM, MARKED_COND_NAMED,
                        reason_expr_named)

DEFAULT_DB = "all"
DB_CHOICES = ("all", "ckb", "local_doc")

# Имя таблицы аудита local_doc взято из живой схемы (замер 16.10.2026): `audit_log` там нет,
# есть `snippet_audit_log`, а FK snippet_audit_log.snippet_id → knowledge_snippets(id) объявлен
# БЕЗ ON DELETE — то есть шаг аудита обязателен перед удалением сниппета с историей. Имя
# названо один раз: два написания одного объекта означают, что шаг аудита «пропускается» только
# потому, что запрашивали не ту таблицу.
AUDIT_TABLE = "snippet_audit_log"


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# --------------------------------------------------------------------------- local_doc
def find_marked_local(conn, limit=0):
    """Помеченные сниппеты local_doc + число алиасов, которые уйдут вместе с ними.

    Узел Q3, живой замер 16.10.2026 по information_schema:
      * колонки `active` в `alias_targets` нет — условие `a.active` давало
        `column a.active does not exist`, и весь шаг local_doc падал, не дойдя до снятия;
        в живой схеме алиасы снимаются мягким удалением только в `config_aliases` (ckb),
        здесь мягкого снятия нет вовсе;
      * `alias_targets.snippets_id` — FK c `ON DELETE CASCADE`, поэтому алиасы уходят вместе
        со сниппетом сами; число считается только для того, чтобы оператор видел объём.
    """
    sql = f"""
        SELECT s.id, s.question, s.tags, s.groups_id,
               {reason_expr_named(MARK_TAG_PARAM)} AS reason,
               (SELECT count(*) FROM alias_targets a
                 WHERE a.snippets_id = s.id) AS aliases_cascaded
          FROM knowledge_snippets s
         WHERE {MARKED_COND_NAMED}
         ORDER BY s.id
    """
    # Именованные параметры: MARKED_COND_NAMED и reason_expr_named дают только %(name)s,
    # а смешивать %(name)s с позиционным %s в одном запросе нельзя — LIMIT тоже именованный.
    params = {"mark": MARK_ARRAY, MARK_TAG_PARAM: MARKER}
    if limit:
        sql += " LIMIT %(limit)s"
        params["limit"] = int(limit)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def doc_links_to_local(conn, snippet_ids):
    """Указатели ckb -> local_doc на снимаемые строки (останутся битыми после снятия)."""
    if not snippet_ids:
        return []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, local_doc_id, target_type, target_name, target_uuid, parent_uuid
              FROM config_cross_references
             WHERE local_doc_kind = 'snippet' AND local_doc_id = ANY(%s::bigint[])
             ORDER BY id
            """,
            (list(snippet_ids),),
        )
        return [dict(r) for r in cur.fetchall()]


def purge_local_doc(limit, apply_changes, keep_audit):
    """Снятие помеченных сниппетов local_doc. Одна транзакция на весь шаг."""
    section("local_doc — сниппеты, помеченные тегом mark-for-deletion")
    out = {"db": "local_doc", "found": 0, "removed": 0, "aliases_cascaded": 0,
           "audit_removed": 0, "audit_unlinked": 0, "dangling_doc_links": [], "error": None}
    conn = None
    try:
        conn = psycopg2.connect(**db_config("local_doc"))
        rows = find_marked_local(conn, limit)
        out["found"] = len(rows)
        if not rows:
            print("  помеченных нет — снимать нечего")
            return out

        aliases_before = sum(int(r["aliases_cascaded"] or 0) for r in rows)
        print(f"  найдено: {len(rows)}, алиасов уйдёт каскадом: {aliases_before}")
        for row in rows:
            reason = row["reason"] or ""
            print(f"    id={row['id']} aliases={row['aliases_cascaded']} "
                  f"groups_id={row['groups_id']} {reason[:110]}")

        # Имя таблицы аудита — AUDIT_TABLE (живая схема local_doc): `audit_log` там нет, есть
        # snippet_audit_log. FK snippet_audit_log.snippet_id -> knowledge_sn(ID) объявлен
        # БЕЗ ON DELETE, поэтому шаг аудита обязателен: без него удаление сниппета с
        # историей упало бы нарушением внешнего ключа (узел Q3, замер 16.10.2026).
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SELECT to_regclass('public.{AUDIT_TABLE}') AS audit_log")
            has_audit = bool((cur.fetchone() or {}).get("audit_log"))
        if not has_audit:
            print(f"  таблицы аудита {AUDIT_TABLE} в базе нет — шаг аудита пропускается")

        if not apply_changes:
            print("  режим просмотра: ничего не изменено (добавьте --apply)")
            return out

        ids = [int(r["id"]) for r in rows]
        with conn:                                # одна транзакция: либо всё, либо ничего
            with conn.cursor() as cur:
                if has_audit:
                    if keep_audit:
                        # snippet_id допускает NULL (проверено по information_schema),
                        # поэтому «сохранить историю» реализуется отвязкой, а не копией.
                        cur.execute(
                            f"UPDATE {AUDIT_TABLE} SET snippet_id = NULL "
                            "WHERE snippet_id = ANY(%s::int[])", (ids,),
                        )
                        out["audit_unlinked"] = cur.rowcount
                    else:
                        cur.execute(
                            f"DELETE FROM {AUDIT_TABLE} "
                            "WHERE snippet_id = ANY(%s::int[])",
                            (ids,),
                        )
                        out["audit_removed"] = cur.rowcount
                cur.execute(
                    "DELETE FROM knowledge_snippets WHERE id = ANY(%s::int[]) RETURNING id",
                    (ids,),
                )
                out["removed"] = cur.rowcount
        out["aliases_cascaded"] = aliases_before
        print(f"  снято сниппетов: {out['removed']}; "
              f"алиасов ушло каскадом: {out['aliases_cascaded']}; "
              f"аудита снято: {out['audit_removed']}, отвязано: {out['audit_unlinked']}")

        # битые указатели в другой базе — отдельный факт, а не ошибка удаления
        try:
            with psycopg2.connect(**db_config("ckb_1c_configurations")) as cfg_conn:
                out["dangling_doc_links"] = doc_links_to_local(cfg_conn, ids)
        except Exception as exc:
            print(f"  ⚠️ указатели documentation проверить не удалось: {exc}")
        if out["dangling_doc_links"]:
            print(f"  ⚠️ указатели ckb -> local_doc остались битыми "
                  f"({len(out['dangling_doc_links'])}): снимите их "
                  "delete_config_cross_reference_tool")
            for link in out["dangling_doc_links"]:
                print(f"    reference_id={link['id']} -> snippet {link['local_doc_id']} "
                      f"цель {link['target_type']} {link['target_name'] or ''}")
        return out
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        out["error"] = str(exc)
        print(f"  ❌ шаг local_doc не выполнен (откат): {exc}")
        return out
    finally:
        if conn is not None:
            conn.close()


# --------------------------------------------------------------------------- ckb
def purge_ckb(uuid, limit, apply_changes):
    """Снятие помеченных enrich-сниппетов контрактной операцией удаления."""
    section("ckb_1c_configurations — enrich-сниппеты, помеченные тегом mark-for-deletion")
    out = {"db": "ckb_1c_configurations", "found": 0, "removed": 0, "aliases_removed": 0,
           "dependencies_removed": 0, "links_removed": 0, "error": None}
    # Узел Q3: ответ контрактной операции проверяется, а не сводится к `.get("rows", [])`:
    # при ошибке запроса пустой список печатал бы «помеченных нет», хотя запрос не выполнялся.
    res = list_marked_config_snippets(uuid=uuid, limit=limit or 10000)
    if not res.get("success"):
        out["error"] = res.get("error") or "перечень карантина не получен"
        print(f"  ❌ перечень карантина не получен: {out['error']}")
        return out
    rows = res.get("rows", [])
    out["found"] = len(rows)
    if not rows:
        print("  помеченных нет — снимать нечего")
        return out

    print(f"  найдено: {len(rows)}")
    for row in rows:
        # object_kind в ответе list_marked_config_snippets нет (строки выбираются по
        # config_snippets + external_report.name), поэтому вид объекта не печатаем:
        # обращение по row['object_kind'] дало бы KeyError на первом же найденном сниппете.
        print(f"    id={row['id']} {row['object_name'] or ''} "
              f"source={row['source_kind']} verified={row['is_verified']} "
              f"reason={(row['reason'] or '')[:80]}")
        print(f"           {(row['question'] or '')[:90]}")
    if not apply_changes:
        print("  режим просмотра: ничего не изменено (добавьте --apply)")
        return out

    failed = []
    for row in rows:
        res = delete_config_snippet(int(row["id"]))
        if not res.get("success"):
            failed.append((row["id"], res.get("error")))
            continue
        out["removed"] += 1
        # ключи ответа delete_config_snippet — children_deleted: aliases / dependencies /
        # doc_links. Имен вида rows_removed / config_aliases в src нет: счётчики молча
        # остались бы нулями, хотя строки сняты (узел Q3).
        removed = res.get("children_deleted") or {}
        out["aliases_removed"] += int(removed.get("aliases") or 0)
        out["dependencies_removed"] += int(removed.get("dependencies") or 0)
        out["links_removed"] += int(removed.get("doc_links") or 0)
    print(f"  снято сниппетов: {out['removed']}; алиасов: {out['aliases_removed']}; "
          f"зависимостей: {out['dependencies_removed']}; "
          f"ссылок documentation: {out['links_removed']}")
    for snippet_id, error in failed:
        print(f"  ❌ id={snippet_id}: {error}")
    if failed:
        out["error"] = f"не снято {len(failed)}"
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Снять карантин (тег mark-for-deletion) жёстким удалением. "
                    "По умолчанию только показывает, что будет снято.")
    parser.add_argument("--db", default=DEFAULT_DB, choices=DB_CHOICES,
                        help="где работать (по умолчанию all)")
    parser.add_argument("--apply", action="store_true",
                        help="выполнить удаление (без него — только просмотр)")
    parser.add_argument("--dry-run", action="store_true",
                        help="явный просмотр: то же, что вызов без флагов (ничего не меняет); "
                             "с --apply противоречиво и отклоняется")
    parser.add_argument("--uuid", default=None,
                        help="ограничить один объект выгрузки (только ckb)")
    parser.add_argument("--limit", type=int, default=0,
                        help="не более N строк (0 = без ограничения)")
    parser.add_argument("--keep-audit", action="store_true",
                        help="local_doc: оставить строки аудита, отвязав их от сниппета")
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        # Противоречие названо, а не разрешено в пользу одного из флагов: «применить» и
        # «только посмотреть» дают разные последствия для одних и тех же строк.
        parser.error("--apply и --dry-run исключают друг друга: выберите одно")

    print("Узел Q2: снятие карантина жёстким удалением")
    print(f"режим: {'ПРИМЕНЕНИЕ' if args.apply else 'ПРОСМОТР (dry-run)'}; "
          f"база: {args.db}; limit: {args.limit or 'нет'}")

    reports = []
    if args.db in ("all", "ckb"):
        reports.append(purge_ckb(args.uuid, args.limit, args.apply))
    if args.db in ("all", "local_doc"):
        reports.append(purge_local_doc(args.limit, args.apply, args.keep_audit))

    section("ИТОГ")
    errors = 0
    for rep in reports:
        status = "❌ " + rep["error"] if rep["error"] else "ok"
        print(f"  {rep['db']}: найдено {rep['found']}, снято {rep['removed']} :: {status}")
        if rep["error"]:
            errors += 1
    if not args.apply:
        print("  записи не выполнялись: добавьте --apply")
    for rep in reports:
        if rep.get("dangling_doc_links"):
            print(f"  ⚠️ {rep['db']}: битых указателей documentation осталось "
                  f"{len(rep['dangling_doc_links'])}")
    print("=" * 70)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())