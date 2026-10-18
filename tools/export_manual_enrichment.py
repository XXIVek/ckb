#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V19 / открытый вопрос B3: снять ручной слой обогащения перед разрушительной операцией.

Зачем. Правило 10 `1C_Rule.md`: правим мы только строками БД, каталог выгрузки - транспорт.
При этом `load_1c_catalog_tool(..., force=True)` (и `tools/restore_reference_pair.py`, и все
загрузочные регрессы) вызывает `delete_external_object()`, который снимает строку объекта и
ВМЕСТЕ с ней ручные строки обогащения: `config_aliases (origin='manual')`,
`config_snippets (is_verified=true)`, `config_cross_references`. Перегенерация их не трогает,
перезагрузка - удаляет (проверено 14.10.2026: после `validate_enrichment_flow.py` ручные строки
эталонной пары исчезли, их наносили заново по приложениям A и C плана правки).

Ручные строки - вывод оператора, а не производные данные: авто-алиасы и авто-сниппеты генератор
построит заново, а формулировку «параметры объявлены, но в варианте „Основной“ выключены
(use=false)» построить нечем. Значит перед `force=True` слой нужно снимать в файл. До этого шага
снимок вели руками в тексте плана (приложения A и C `docs/EXTERNAL_OBJECT_EDIT_PLAN.md`), и он
расходился с базой хотя бы датой. Скрипт строит снимок по живой БД и ничего не пишет в неё.

Читается: `v_current_external_report` (карточка ТЕКУЩЕГО состояния - узел V19, правило S5: по
базовой таблице `WHERE uuid = ?` вернул бы все ревизии), `config_aliases WHERE origin='manual'`
(с группировкой по цели - ровно так их и наносят, одним вызовом на группу),
`config_snippets WHERE is_verified` с зависимостями (зависимости пишутся строкой `Type:Name` по
`target_name`, а не по сохранённому `target_uuid`) и `config_cross_references`.

Стабильность ключей целей - то, что нужно знать при восстановлении: стабилен ключ, построенный на
uuid из выгрузки (объект, реквизит, макет, форма, `form_item:<uuid формы>:…`,
`module:form:<uuid формы>`, `dcs:<uuid макета>:…); НЕ стабилен `module:<id>` (id строки
`bsl_modules` меняется после `force=True` или новой ревизии) и `snippet:<id>` (id авто-сниппетов
меняются при каждой перегенерации) - такие цели наносят парой `target_type` + `target_name`, а
`target_uuid` подставит инструмент (узел E, правило 9 обогащения). Скрипт помечает их явно.

Не теряется молча, а называется: алиас с запятой внутри термина (`add_config_aliases` режет
список по запятой); алиас с пустым `target_key` (слепая зона, раздел 16 инвентаря); ручной
сниппет в карантине (`add_config_snippet` выбрасывает зарезервированные теги - пометку после
восстановления ставят заново).

Запуск (UTF-8 в консоли обязателен):
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python tools/export_manual_enrichment.py                    # все объекты с ручными строками
    python tools/export_manual_enrichment.py --uuid <uuid>      # один объект
    python tools/export_manual_enrichment.py --out <файл.json>  # куда писать (по умолчанию
                                                                snapshots/manual_enrichment/)

Код возврата: 0 - снимок снят (в том числе когда ручных строк нет: это тоже ответ),
1 - объект не найден или чтение не удалось.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from psycopg2.extras import RealDictCursor  # noqa: E402

from external_db import connect  # noqa: E402
from quarantine import MARKER, reason_of  # noqa: E402

SNAPSHOT_DIR = ROOT / "snapshots" / "manual_enrichment"
SNAPSHOT_KIND = "manual_enrichment_snapshot"
SNAPSHOT_VERSION = 1

# Типы цели, означающие «сам объект»: при восстановлении target_type не указывают - вид цели
# берётся из строки заголовка (узел V22), иначе вид мог бы разойтись с видом объекта.
SELF_TARGETS = ("ExternalReport", "ExternalProcessing")


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def target_stability(target_type, target_uuid):
    """Код и пояснение: переживёт ли сохранённый ключ цели `force=True` и перегенерацию.

    Кодов ровно три: "stable" - ключ переносим как есть; "unstable" - ключ содержит id строки,
    который меняется, поэтому цель наносят парой target_type + target_name (узел E); "name" -
    сохранённого ключа нет (алиас заводили по имени цели), так и наносим.
    """
    key = str(target_uuid or "")
    if not key:
        return "name", ("ключа цели в БД нет; цель наносится парой target_type + target_name "
                        "(узел E)")
    if key.startswith("module:form:"):
        return "stable", "ключ модуля формы построен на uuid формы - он из XML выгрузки"
    if key.startswith("module:"):
        return "unstable", ("ключ модуля содержит id строки bsl_modules: после force=True или "
                            "новой ревизии он другой - разрешать цель по имени")
    if key.startswith("snippet:"):
        return "unstable", ("id авто-сниппета меняется при каждой перегенерации - цель-сниппет "
                            "привязывают к ручному сниппету или к цели по имени")
    if key.startswith("form_item:"):
        return "stable", "ключ элемента формы - uuid формы + имя элемента"
    if key.startswith("dcs:"):
        return "stable", "ключ элемента макета-СКД - uuid макета + вид + имя"
    return "stable", "ключ - uuid строки метаданных из выгрузки"


def read_object(cur, obj_uuid):
    """Карточка текущего состояния объекта из витрины V19 (не из базовой таблицы)."""
    cur.execute(
        "SELECT id, uuid, name, object_kind, revision_no, changed_at, changed_by, "
        "       (children_manifest IS NULL) AS manifest_missing, origin_kind, configuration_id "
        "FROM v_current_external_report WHERE uuid = %s::uuid", (obj_uuid,))
    row = cur.fetchone()
    return dict(row) if row else None


def list_objects(cur):
    """Объекты, у которых есть хоть одна ручная строка обогащения."""
    cur.execute(
        "SELECT o.uuid FROM v_current_external_report o "
        "WHERE EXISTS (SELECT 1 FROM config_aliases a WHERE a.parent_uuid = o.uuid "
        "                AND a.origin = 'manual') "
        "   OR EXISTS (SELECT 1 FROM config_snippets s WHERE s.parent_uuid = o.uuid "
        "                AND s.is_verified) "
        "   OR EXISTS (SELECT 1 FROM config_cross_references r WHERE r.parent_uuid = o.uuid) "
        "ORDER BY o.id")
    return [str(r["uuid"]) for r in cur.fetchall()]


def read_aliases(cur, obj_uuid):
    """Ручные алиасы двумя вещами: группами по цели (для восстановления) и строками (для числа).

    Группировка - не украшение: `add_config_aliases` принимает список через запятую и на весь
    список одну цель, поэтому снимок повторяет форму вызова. Разные цели одного термина -
    разные группы, и это верно: частичный индекс uq_config_aliases_alias_target держит
    уникальность по (alias_norm, target_key), то есть один термин на две цели - две строки.
    """
    cur.execute(
        "SELECT id, alias_name, target_type, target_name, target_uuid, target_snippet_id, "
        "       weight, description, active "
        "FROM config_aliases WHERE parent_uuid = %s::uuid AND origin = 'manual' "
        "ORDER BY target_type NULLS LAST, target_name NULLS LAST, id", (obj_uuid,))
    rows = [dict(r) for r in cur.fetchall()]
    groups, order = {}, []
    for row in rows:
        key = (str(row["target_type"]), str(row["target_name"]), str(row["target_uuid"]),
               str(row["target_snippet_id"]), repr(row["weight"]), str(row["description"]),
               bool(row["active"]))
        if key not in groups:
            code, why = target_stability(row["target_type"], row["target_uuid"])
            groups[key] = {
                "target_type": row["target_type"],
                "target_name": row["target_name"],
                "target_uuid": row["target_uuid"],
                "target_snippet_id": row["target_snippet_id"],
                "target_key_stability": code,
                "stability_note": why,
                "weight": row["weight"],
                "description": row["description"],
                "active": bool(row["active"]),
                "source_alias_ids": [],
                "aliases": [],
            }
            order.append(key)
        groups[key]["source_alias_ids"].append(row["id"])
        groups[key]["aliases"].append(row["alias_name"])
    return [groups[k] for k in order], rows


def read_snippets(cur, obj_uuid):
    """Ручные сниппеты с зависимостями. Зависимости - по ИМЕНАМ целей, не по ключам."""
    cur.execute(
        "SELECT id, question, answer, source_kind, source_uuid, source_path, target_type, "
        "       target_uuid, tags, confidence "
        "FROM config_snippets WHERE parent_uuid = %s::uuid AND is_verified ORDER BY id",
        (obj_uuid,))
    out = []
    for raw in cur.fetchall():
        row = dict(raw)
        cur.execute(
            "SELECT dependency_type, target_type, target_name, target_uuid "
            "FROM config_snippet_dependencies WHERE snippet_id = %s "
            "ORDER BY target_type, target_name", (row["id"],))
        deps = [dict(d) for d in cur.fetchall()]
        code, why = target_stability(row["target_type"], row["target_uuid"])
        tags = list(row["tags"] or [])
        out.append({
            "source_snippet_id": row["id"],
            "question": row["question"],
            "answer": row["answer"],
            "answer_size": len(row["answer"] or ""),
            "source_kind": row["source_kind"],
            "source_uuid": row["source_uuid"],
            "source_path": row["source_path"],
            "target_type": row["target_type"],
            "target_uuid": row["target_uuid"],
            "target_key_stability": code,
            "stability_note": why,
            "tags": tags,
            "confidence": row["confidence"],
            "dependencies": [f"{d['target_type']}:{d['target_name']}" for d in deps],
            "quarantined": MARKER in tags,
            "quarantine_reason": reason_of(tags) if MARKER in tags else None,
        })
    return out


def read_cross_references(cur, obj_uuid):
    cur.execute(
        "SELECT id, local_doc_kind, local_doc_id, target_type, target_name, target_uuid, "
        "       reference_type FROM config_cross_references WHERE parent_uuid = %s::uuid "
        "ORDER BY id", (obj_uuid,))
    out = []
    for raw in cur.fetchall():
        row = dict(raw)
        code, why = target_stability(row["target_type"], row["target_uuid"])
        row["target_key_stability"] = code
        row["stability_note"] = why
        out.append(row)
    return out


def build_warnings(obj, alias_groups, alias_rows, snippets):
    """Всё, что восстановление не умеет, - названо, а не потеряно молча."""
    warnings = []
    if obj["manifest_missing"]:
        warnings.append(
            "у строки объекта нет children_manifest (снимок до узла V19): строгий состав детей "
            "карточка не отдаёт; после загрузки текущим кодом манифест появится")
    for group in alias_groups:
        for alias in group["aliases"]:
            if "," in alias:
                ids = ", ".join(map(str, group["source_alias_ids"]))
                warnings.append(f"алиас id={ids} содержит запятую ({alias!r}): "
                                "add_config_aliases режет список по запятой - термин нужно "
                                "наносить отдельно или переформулировать")
    blind = [r for r in alias_rows
             if r["target_type"] not in SELF_TARGETS
             and not r["target_uuid"] and not r["target_snippet_id"]]
    if blind:
        warnings.append(f"алиасов с пустым target_key: {len(blind)} (слепая зона, раздел 16 "
                        "инвентаря); при восстановлении цель разрешается по имени, поэтому "
                        "пустой ключ не повторится")
    for snippet in snippets:
        if snippet["quarantined"]:
            warnings.append(
                f"ручной сниппет id={snippet['source_snippet_id']} в карантине (причина: "
                f"{snippet['quarantine_reason'] or 'не указана'}): add_config_snippet "
                "выбрасывает зарезервированные теги - пометку после восстановления ставят "
                "заново mark_config_snippet_tool")
        if snippet["target_key_stability"] == "unstable":
            warnings.append(
                f"основная цель сниппета id={snippet['source_snippet_id']} описана нестабильным "
                f"ключом ({snippet['target_uuid']}): {snippet['stability_note']}")
    return warnings


def snapshot_for(conn, obj_uuid):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        obj = read_object(cur, obj_uuid)
        if not obj:
            return None
        alias_groups, alias_rows = read_aliases(cur, obj_uuid)
        snippets = read_snippets(cur, obj_uuid)
        cross_references = read_cross_references(cur, obj_uuid)
    return {
        "kind": SNAPSHOT_KIND,
        "version": SNAPSHOT_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "object": {
            "id": obj["id"],
            "uuid": str(obj["uuid"]),
            "name": obj["name"],
            "object_kind": obj["object_kind"],
            "revision_no": obj["revision_no"],
            "manifest_missing": obj["manifest_missing"],
            "origin_kind": obj["origin_kind"],
            "configuration_id": obj["configuration_id"],
        },
        "counts": {
            "manual_alias_groups": len(alias_groups),
            "manual_aliases": len(alias_rows),
            "manual_snippets": len(snippets),
            "manual_dependencies": sum(len(s["dependencies"]) for s in snippets),
            "cross_references": len(cross_references),
        },
        "aliases": alias_groups,
        "snippets": snippets,
        "cross_references": cross_references,
        "warnings": build_warnings(obj, alias_groups, alias_rows, snippets),
    }


def default_out_path(snapshot):
    name = "".join(ch if ch.isalnum() or ch in "-_" else "_"
                   for ch in str(snapshot["object"]["name"] or "object"))[:40]
    return SNAPSHOT_DIR / f"manual_{str(snapshot['object']['uuid'])[:8]}_{name}.json"


def print_snapshot(snapshot, out_path):
    obj, counts = snapshot["object"], snapshot["counts"]
    section(f"СНИМОК РУЧНОГО ОБОГАЩЕНИЯ: [{obj['id']}] {obj['name']} "
            f"(uuid={obj['uuid']}, вид={obj['object_kind']})")
    print(f"  ревизия {obj['revision_no']}; children_manifest: "
          f"{'НЕТ (снимок до узла V19)' if obj['manifest_missing'] else 'записан'}")
    print(f"  ручных алиасов {counts['manual_aliases']} (групп по цели "
          f"{counts['manual_alias_groups']}), ручных сниппетов {counts['manual_snippets']} "
          f"(зависимостей {counts['manual_dependencies']}), ссылок documentation "
          f"{counts['cross_references']}")
    for group in snapshot["aliases"]:
        target = group["target_type"] or "(цель - сам объект)"
        flag = "" if group["target_key_stability"] == "stable" else \
            f" [{group['target_key_stability']}]"
        print(f"  алиасы -> {target}:{group['target_name'] or ''} "
              f"(вес {group['weight']}, терминов {len(group['aliases'])}){flag}")
        if group["target_key_stability"] != "stable":
            print(f"      {group['stability_note']}")
    for snippet in snapshot["snippets"]:
        print(f"  сниппет «{snippet['question'][:60]}» ({snippet['answer_size']} симв., "
              f"зависимостей {len(snippet['dependencies'])})")
    if snapshot["warnings"]:
        print("  ПРЕДУПРЕЖДЕНИЯ СНИМКА:")
        for warning in snapshot["warnings"]:
            print(f"    ⚠️ {warning}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  файл: {out_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Снять ручное обогащение внешнего объекта в JSON (только чтение).")
    parser.add_argument("--uuid", help="uuid объекта; без него - все объекты с ручными строками")
    parser.add_argument("--out", help="файл снимка (по умолчанию snapshots/manual_enrichment/)")
    args = parser.parse_args(argv)

    conn = connect()
    try:
        if args.uuid:
            uuids = [args.uuid]
        else:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                uuids = list_objects(cur)
        if not uuids:
            section("РУЧНЫХ СТРОК ОБОГАЩЕНИЯ НЕТ")
            print("  ни config_aliases (origin='manual'), ни config_snippets (is_verified), ни "
                  "config_cross_references записей не содержат - снимать нечего")
            return 0
        failed = 0
        for obj_uuid in uuids:
            snapshot = snapshot_for(conn, str(obj_uuid))
            if snapshot is None:
                print(f"❌ объект uuid={obj_uuid} в v_current_external_report не найден")
                failed += 1
                continue
            out_path = (Path(args.out) if args.out and len(uuids) == 1
                        else default_out_path(snapshot))
            print_snapshot(snapshot, out_path)
        return 1 if failed else 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())



