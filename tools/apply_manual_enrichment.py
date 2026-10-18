#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V19 / открытый вопрос B3: восстановить ручной слой обогащения после `force=True`.

Зачем. `load_1c_catalog_tool(..., force=True)` снимает строку внешнего объекта вместе с ручными
алиасами, ручными сниппетами и ссылками на documentation (обогащение чистится при удалении
объекта). Авто-строки генератор построит заново, ручные - нечем. Снимок делает
`tools/export_manual_enrichment.py`, этот скрипт его применяет.

Почему восстановление идёт через `src/`, а не прямым SQL. Ручная строка обязана пройти те же
проверки, что и вызов инструмента контракта: несуществующая цель - отказ, а не связь вникуда
(правило 5); дубликаты не создаются; `is_verified=true` и `origin='manual'` проставляет код, а не
скрипт. Свой INSERT означал бы второй, никем не проверяемый путь записи тех же строк - ровно тот
дефект, из-за которого удалили `src/config_aliases.py` и компанию.

Как восстанавливаются цели после перезагрузки:
  * цель «сам объект» - `target_type` не передаётся: вид цели берётся из строки заголовка
    (узел V22), правильными будут и вид цели, и `parent_type` строк;
  * цель содержимого - парой `target_type` + `target_name`, `target_uuid` подставит резолвер
    стабильного ключа (узел E). Снимок поэтому хранит ИМЕНА целей: `module:<id>` и `snippet:<id>`
    после `force=True` или перегенерации другие (разметка stable/unstable в снимке);
  * зависимости сниппетов - строка `Type:Name`: она проверяется по текущему составу и укрепляется
    ключом тем же кодом.

Что называется прямо, а не делается молча: объект не загружен - отказ с подсказкой; цель-сниппет
(`target_snippet_id`) - id сниппетов после перезагрузки другие, строка пропускается с
объяснением; карантиная пометка, алиас с запятой, несовпадение вида объекта со снимком.

Режим по умолчанию - просмотр (то же соглашение, что у `tools/purge_marked_snippets.py`):
показывается план и разбор целей; запись выполняется только с `--apply`.

Запуск (UTF-8 в консоли обязателен):
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python tools/apply_manual_enrichment.py                       # план по всем снимкам
    python tools/apply_manual_enrichment.py --apply               # восстановить
    python tools/apply_manual_enrichment.py <файл-снимок.json> --apply
    python tools/apply_manual_enrichment.py --uuid <uuid> --apply # снимок одного объекта

Код возврата: 0 - план построен либо всё восстановлено и счётчики сошлись со снимком;
1 - есть отказ (объект не загружен, цель не найдена, шаг записи упал, счётчики не сошлись).
"""
from __future__ import annotations

import argparse
import io
import json
import sys
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
from enrichment_aliases import add_config_aliases  # noqa: E402
from enrichment_snippets import (add_config_cross_reference,  # noqa: E402
                                 add_config_snippet)

SNAPSHOT_DIR = ROOT / "snapshots" / "manual_enrichment"
SNAPSHOT_KIND = "manual_enrichment_snapshot"
SELF_TARGETS = ("ExternalReport", "ExternalProcessing")


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def load_snapshots(paths, uuid_filter=None):
    """Снимки из явных файлов или из каталога по умолчанию; фильтр по uuid объекта."""
    files = [Path(p) for p in paths] if paths else (
        sorted(SNAPSHOT_DIR.glob("*.json")) if SNAPSHOT_DIR.is_dir() else [])
    out = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"❌ снимок {path} не читается: {exc}")
            continue
        if data.get("kind") != SNAPSHOT_KIND:
            print(f"❌ {path}: kind={data.get('kind')!r}, ожидался {SNAPSHOT_KIND!r}")
            continue
        if uuid_filter and str(data.get("object", {}).get("uuid")) != str(uuid_filter):
            continue
        out.append((path, data))
    return out


def current_object(cur, obj_uuid):
    """Текущее состояние объекта (витрина V19) - чтобы понять, есть ли куда наносить."""
    cur.execute("SELECT id, uuid, name, object_kind, revision_no, "
                "       (children_manifest IS NULL) AS manifest_missing "
                "FROM v_current_external_report WHERE uuid = %s::uuid", (obj_uuid,))
    row = cur.fetchone()
    return dict(row) if row else None


def manual_counts(cur, obj_uuid):
    """Что реально лежит в БД после восстановления - сравнивается со снимком."""
    cur.execute(
        "SELECT (SELECT COUNT(*) FROM config_aliases WHERE parent_uuid = %s::uuid "
        "                AND origin = 'manual' AND active) AS aliases, "
        "       (SELECT COUNT(*) FROM config_snippets WHERE parent_uuid = %s::uuid "
        "                AND is_verified) AS snippets, "
        "       (SELECT COUNT(*) FROM config_snippet_dependencies d "
        "          JOIN config_snippets s ON s.id = d.snippet_id "
        "         WHERE s.parent_uuid = %s::uuid AND s.is_verified) AS dependencies, "
        "       (SELECT COUNT(*) FROM config_cross_references WHERE parent_uuid = %s::uuid) "
        "       AS doc_links", (obj_uuid, obj_uuid, obj_uuid, obj_uuid))
    return dict(cur.fetchone())


def alias_call(group):
    """Вызов add_config_aliases для группы алиасов одной цели.

    Для цели «сам объект» target_type/target_name не передаются: вид цели возьмётся из строки
    заголовка (узел V22). Для цели содержимого target_uuid не переносится, когда он нестабилен
    (module:<id>, snippet:<id>) или отсутствовал в БД, - цель разрешится по имени (узел E).
    """
    kwargs = {"aliases": ",".join(group["aliases"]), "weight": group["weight"],
              "description": group["description"]}
    target_type = group.get("target_type")
    if target_type in SELF_TARGETS or not target_type:
        return kwargs, "(цель - сам объект)"
    kwargs["target_type"] = target_type
    kwargs["target_name"] = group.get("target_name")
    if group.get("target_key_stability") == "stable" and group.get("target_uuid"):
        kwargs["target_uuid"] = group["target_uuid"]
    return kwargs, f"{target_type}:{group.get('target_name') or ''}"


def snippet_call(item):
    """Вызов add_config_snippet для ручного сниппета.

    Основная цель переносится только когда её ключ стабилен: `target_uuid` вида `module:<id>`
    или `snippet:<id>` после перезагрузки указывает бы на чужую строку, а молча оставить
    неверную цель - значит получить сниппет «о другом». Без основной цели сниппет остаётся
    привязанным к объекту через зависимости (это и есть обязательная связь по правилу 5).
    """
    kwargs = {"question": item["question"], "answer": item["answer"],
              "source_kind": item.get("source_kind") or "manual",
              "source_uuid": item.get("source_uuid"),
              "source_file": item.get("source_path"),
              "tags": item.get("tags") or [], "confidence": item.get("confidence") or 1.0,
              "dependencies": "; ".join(item.get("dependencies") or [])}
    if item.get("target_key_stability") == "stable" and item.get("target_uuid"):
        kwargs["target_type"] = item.get("target_type")
        kwargs["target_uuid"] = item["target_uuid"]
        return kwargs, f"{item.get('target_type')}:{item['target_uuid']}"
    return kwargs, "(основная цель не переносится: ключ нестабилен или его не было)"


def reference_call(item):
    """Вызов add_config_cross_reference для указателя на documentation."""
    kwargs = {"local_doc_kind": item.get("local_doc_kind") or "group",
              "local_doc_id": item.get("local_doc_id"),
              "reference_type": item.get("reference_type") or "linked_to"}
    target_type = item.get("target_type")
    if target_type in SELF_TARGETS or not target_type:
        return kwargs, "(цель - сам объект)"
    kwargs["target_type"] = target_type
    kwargs["target_name"] = item.get("target_name")
    if item.get("target_key_stability") == "stable" and item.get("target_uuid"):
        kwargs["target_uuid"] = item["target_uuid"]
    return kwargs, f"{target_type}:{item.get('target_name') or ''}"


def apply_snapshot(conn, path, data, apply):
    """Восстановить один снимок. True - если отказов нет и счётчики сошлись со снимком."""
    obj_snap = data.get("object", {})
    obj_uuid = str(obj_snap.get("uuid"))
    section(f"ВОССТАНОВЛЕНИЕ РУЧНОГО СЛОЯ: {path.name} -> uuid={obj_uuid}")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        current = current_object(cur, obj_uuid)
    if not current:
        print(f"  ❌ объект uuid={obj_uuid} не загружен: сначала load_1c_catalog_tool("
              "source_path=...) или tools/restore_reference_pair.py")
        return False
    print(f"  объект [{current['id']}] {current['name']} (вид={current['object_kind']}, "
          f"ревизия {current['revision_no']}, children_manifest "
          f"{'НЕТ' if current['manifest_missing'] else 'записан'})")
    problems = []
    if current["object_kind"] != obj_snap.get("object_kind"):
        problems.append(f"вид объекта разошёлся со снимком: было {obj_snap.get('object_kind')!r}, "
                        f"стало {current['object_kind']!r} - цель «сам объект» разрешится по "
                        "текущему виду (узел V22)")
    stats = {"aliases": 0, "snippets": 0, "dependencies": 0, "references": 0, "skipped": 0,
             "failed": 0}

    for group in data.get("aliases", []):
        count = len(group.get("aliases") or [])
        if not group.get("active", True):
            print(f"  ⏸️ группа алиасов снята мягко (active=false), не восстанавливаем: "
                  f"{group.get('aliases')}")
            stats["skipped"] += count
            continue
        if group.get("target_snippet_id"):
            print(f"  ⏸️ алиасы к сниппету id={group['target_snippet_id']}: id сниппетов после "
                  "перезагрузки другие - наносите заново по цели сниппета")
            stats["skipped"] += count
            continue
        kwargs, target = alias_call(group)
        if not apply:
            print(f"  план: {count} алиасов -> {target}")
            stats["aliases"] += count
            continue
        res = add_config_aliases(uuid=obj_uuid, **kwargs)
        if not res.get("success"):
            print(f"  ❌ алиасы -> {target}: {res.get('error')}")
            problems.append(str(res.get("error")))
            stats["failed"] += 1
            continue
        print(f"  ✅ алиасы -> {target}: создано {res.get('created')}, уже было "
              f"{res.get('already_present')} (запрошено {count})")
        stats["aliases"] += res.get("created", 0)

    for item in data.get("snippets", []):
        kwargs, target = snippet_call(item)
        deps = len([d for d in (kwargs.get("dependencies") or "").split(";") if d.strip()])
        if not apply:
            print(f"  план: сниппет «{item['question'][:50]}» (зависимостей {deps})")
            stats["snippets"] += 1
            stats["dependencies"] += deps
            continue
        res = add_config_snippet(uuid=obj_uuid, **kwargs)
        if not res.get("success"):
            if res.get("already_exists"):
                print(f"  ⏸️ сниппет уже есть (id={res.get('id')}): {item['question'][:50]}")
                stats["skipped"] += 1
                continue
            print(f"  ❌ сниппет «{item['question'][:50]}»: {res.get('error')}")
            problems.append(str(res.get("error")))
            stats["failed"] += 1
            continue
        print(f"  ✅ сниппет id={res.get('id')}: зависимостей создано "
              f"{res.get('dependencies')}, основная цель: {target}")
        stats["snippets"] += 1
        stats["dependencies"] += res.get("dependencies", 0)

    for item in data.get("cross_references", []):
        kwargs, target = reference_call(item)
        if not apply:
            print(f"  план: ссылка documentation "
                  f"{item.get('local_doc_kind')}#{item.get('local_doc_id')} -> {target}")
            stats["references"] += 1
            continue
        res = add_config_cross_reference(uuid=obj_uuid, **kwargs)
        if not res.get("success"):
            if res.get("already_exists"):
                print(f"  ⏸️ ссылка documentation #{item.get('local_doc_id')} уже есть")
                stats["skipped"] += 1
                continue
            print(f"  ❌ ссылка documentation #{item.get('local_doc_id')}: {res.get('error')}")
            problems.append(str(res.get("error")))
            stats["failed"] += 1
            continue
        print(f"  ✅ ссылка documentation {item.get('local_doc_kind')}#{res.get('local_doc_id')}"
              f" -> {target}")
        stats["references"] += 1

    snap = data.get("counts", {})
    if not apply:
        print(f"  план по снимку: алиасов {snap.get('manual_aliases')}, сниппетов "
              f"{snap.get('manual_snippets')}, зависимостей {snap.get('manual_dependencies')}, "
              f"ссылок {snap.get('cross_references')}")
        print("  запись выполняется только с --apply")
        return not problems

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        after = manual_counts(cur, obj_uuid)
    print("  СВЕРКА СНИМКА С БАЗОЙ ПОСЛЕ ЗАПИСИ:")
    ok = True
    for name, live, wanted in (("алиасы", after["aliases"], snap.get("manual_aliases")),
                               ("сниппеты", after["snippets"], snap.get("manual_snippets")),
                               ("зависимости", after["dependencies"],
                                snap.get("manual_dependencies")),
                               ("ссылки documentation", after["doc_links"],
                                snap.get("cross_references"))):
        mark = "OK" if live == wanted else "РАСХОЖДЕНИЕ"
        print(f"    {name}: в БД {live}, в снимке {wanted} — {mark}")
        if live != wanted:
            ok = False
            problems.append(f"{name}: в БД {live}, ожидалось {wanted}")
    if stats["failed"]:
        ok = False
    if not ok:
        print("  ⚠️ часть целей могла измениться вместе с содержимым объекта: состав целей "
              "даёт config_enrichment_stats_tool(uuid=..., card=True)")
    return ok


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Восстановить ручное обогащение из снимка (по умолчанию только план).")
    parser.add_argument("snapshots", nargs="*",
                        help="файлы снимков (по умолчанию каталог snapshots/manual_enrichment/)")
    parser.add_argument("--uuid", help="применить только снимок этого объекта")
    parser.add_argument("--apply", action="store_true", help="записать (по умолчанию план)")
    args = parser.parse_args(argv)

    pairs = load_snapshots(args.snapshots, args.uuid)
    if not pairs:
        print("❌ снимков нет: сначала python tools/export_manual_enrichment.py")
        return 1
    conn = connect()
    failed = 0
    try:
        for path, data in pairs:
            if not apply_snapshot(conn, path, data, args.apply):
                failed += 1
    finally:
        conn.close()
    section("ИТОГ")
    print(f"  снимков: {len(pairs)}, с отказом или расхождением: {failed}; режим: "
          f"{'запись' if args.apply else 'план (--apply для записи)'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())



