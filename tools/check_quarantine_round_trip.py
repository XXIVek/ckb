#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка карантина сниппетов (узел Q3): метка, причина, скрытие, перенос при перегенерации.

Зачем. Узел Q1 (мягкий карантин зарезервированным тегом `mark-for-deletion`) реализован в
`src/`, но ни одна проверка его не выполняла: `validate_project.py` спотыкался о импорт
несуществующих имён на шаге 3 и обрывался до всех остальных шагов, поэтому код карантина не
запускался ни разу. Первая же живая попытка прочитать карантин нашла два дефекта, которые без
этого скрипта остались бы в работе:

  1. `reason_expr_named` / `reason_expr_positional` строили `split_part(строка, разделитель)` —
     у `split_part` ровно три аргумента, база отвечала «function split_part(text, text)
     does not exist», и запрос не выполнялся вовсе. Молчали об этом две вещи:
     `list_marked_config_snippets` возвращал error (а чистка печатала «помеченных нет»), а
     карточка объекта падала на разделе «ЧТО ДЕЛАЕТ КОД» — он читает причину тем же
     выражением. Номер части обязан быть 2: причина лежит ПОСЛЕ префикса, часть 1 — это
     теги строки до него.
  2. Имена в `validate_project.py` и `tools/purge_marked_snippets.py` не совпадали с живыми
     (`MARK_TAG`, `mark_reason`, `rows_removed`, `row['object_kind']`). Часть таких расхождений
     падает сразу, часть молча даёт нули вместо счётчиков — поэтому проверка обращается к
     живым инструментам контракта, а не к их описанию в правилах.

Что проверяет. Одна обратимая пометка реальной строки + только чтение. Порядок: базовое
состояние → пометка с причиной → карточка сниппета по id → перечень карантина (причину
разбирает сама база — это и есть исправленный `split_part`) → скрытие из поиска, списков и
ответа «что известно про цель» → флаг и отдельный счётчик в карточке объекта → перенос метки
при перегенерации (узел Q2) → снятие → возврат исходного числа помеченных в обеих базах.
Отдельно проверяется то же SQL-выражение на стороне `local_doc`: своих помеченных строк там
нет, поэтому запрос идёт к литералу, а не к таблице (в `local_doc` скрипт не пишет).

Скрипт снимает только свой признак и ничего не создаёт; эталонную пару и ручные строки не
трогает, кроме перегенерации обогащения одного объекта (идемпотентна, узел V17).
Запуск: python tools/check_quarantine_round_trip.py
"""

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
sys.path.insert(0, str(ROOT / "tools"))

import psycopg2  # noqa: E402

from external_db import connect, db_config, transaction  # noqa: E402
from enrichment_generator import describe_object, generate_enrichment  # noqa: E402
from enrichment_snippets import (get_config_snippet, get_snippets_for_object,  # noqa: E402
                                 list_config_snippets,
                                 list_marked_config_snippets, mark_config_snippet,
                                 search_config_snippets, unmark_config_snippet)
from quarantine import (MARK_PARAM, MARKER, MARK_TAG_PARAM, REASON_PREFIX,  # noqa: E402
                        REASON_SUFFIX, reason_expr_named, reason_expr_positional, reason_of)

REASON = "узел Q3: проверочная пометка, черновик"
PASSED, FAILED, SKIPPED = [], [], []


def check(name, ok, note=""):
    (PASSED if ok else FAILED).append(name)
    print(f"  {'✅' if ok else '❌'} {name}" + (f" — {note}" if note else ""))
    return bool(ok)


def skip(name, note=""):
    SKIPPED.append(name)
    print(f"  ⏭️ {name} — пропущено: {note}")


def marked_total():
    """Сколько сниппетов ckb сейчас в карантине (инвариант «после нас — как до нас»)."""
    with transaction() as cur:
        cur.execute("SELECT count(*) FROM config_snippets WHERE %s = ANY(tags)", (MARKER,))
        return int(cur.fetchone()[0])


def pick_snippet():
    """Объект со сниппетами и его авто-сниппет (с зависимостями — приоритетнее)."""
    with transaction() as cur:
        cur.execute(
            "SELECT e.uuid::text, e.name, COALESCE(e.object_kind, 'external_report'), "
            "       count(s.id) AS snippets "
            "  FROM external_report e JOIN config_snippets s ON s.parent_uuid = e.uuid "
            " GROUP BY e.uuid, e.name, e.object_kind "
            " ORDER BY count(s.id) DESC LIMIT 1")
        obj = cur.fetchone()
        if not obj:
            return None
        cur.execute(
            "SELECT s.id, s.question, s.source_kind "
            "  FROM config_snippets s "
            " WHERE s.parent_uuid = %s::uuid AND NOT s.is_verified "
            "   AND NOT (%s = ANY(s.tags)) "
            " ORDER BY (SELECT count(*) FROM config_snippet_dependencies d "
            "           WHERE d.snippet_id = s.id) DESC, s.id LIMIT 1",
            (obj[0], MARKER))
        snippet = cur.fetchone()
    if not snippet:
        return None
    return {"uuid": obj[0], "name": obj[1], "kind": obj[2], "snippets": obj[3],
            "id": int(snippet[0]), "question": snippet[1] or "", "source_kind": snippet[2]}



def ids_of(payload):
    """Множество id в выдаче инструмента (для проверок «видна / не видна строка»)."""
    return {int(row["id"]) for row in (payload or {}).get("rows", []) if row.get("id") is not None}


def rows_of(payload):
    return (payload or {}).get("rows", [])


def find_by_id(payload, snippet_id):
    for row in rows_of(payload):
        if row.get("id") is not None and int(row["id"]) == int(snippet_id):
            return row
    return None


def check_reason_tag_order():
    """Живая проверка на БД: причина читается при любом порядке тегов (замер 16.10.2026).

    Дефект порядка тегов не давал ни ошибки, ни пустого перечня — только искажённую
    причину (`'a=1,mark-for-deletion'` вместо `'a=1'`), то есть весь предыдущий прогон
    его не замечал. Поэтому раскладки тегов проверяются прямым запросом к живому серверу
    и сверяются с Python-разбором `reason_of` — он и есть эталон.
    """
    layouts = [
        [MARKER, f"{MARKER}:reason=одна"],
        [f"{MARKER}:reason=одна", MARKER],
        [f"{MARKER}:reason=одна", MARKER, "прочий-тег"],
        ["прочий-тег", f"{MARKER}:reason=одна", MARKER],
        ["a,b", f"{MARKER}:reason=причина, с запятой", MARKER],
        [f"{MARKER}:reason=", MARKER],
        ["прочий-тег", MARKER],
    ]

    def sql_array(tags):
        return "ARRAY[" + ",".join("'" + t.replace("'", "''") + "'" for t in tags) + "]::text[]"

    values = ",\n".join(f"({n + 1}, {sql_array(tags)})" for n, tags in enumerate(layouts))
    sql = (
        f"SELECT n, tags, {reason_expr_named()} AS reason "
        f"FROM (VALUES\n{values}\n) AS t(n, tags) ORDER BY n"
    )
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, {MARK_TAG_PARAM: MARKER})
        rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        check("запрос разбора причины по раскладкам тегов выполняется", False, str(exc)[:160])
        return
    finally:
        conn.close()
    check("раскладок тегов разобрано столько же, сколько задано", len(rows) == len(layouts),
          f"ожидалось {len(layouts)}, получено {len(rows)}")
    for n, tags, sql_reason in rows:
        want = reason_of(tags)
        got = sql_reason or ""
        check(f"раскладка {n}: причина читается как в Python ({want or 'пусто'})", got == want,
              f"SQL: {got!r}, Python: {want!r}, теги: {tags}")


def check_static_invariants():
    """Статические инварианты модуля карантина: имена параметров и совпадение выражений.

    Класс ошибок, из-за которого карантин не работал вовсе: SQL-выражение ссылалось на
    `%(mark)s`, а словарь параметров содержал только `mark_tag` (KeyError в инструменте),
    либо именованная и позиционная версии выражения различались текстом (разные ответы у
    инструментов контракта и у скриптов-валидаторов).
    """
    named, positional = reason_expr_named(), reason_expr_positional()
    check("выражение не использует split_part (он не отделяет причину от хвоста тега)",
          "split_part" not in named and "split_part" not in positional)
    check("причина ищется по каждому тегу отдельно (unnest)",
          "unnest" in named and "unnest" in positional)
    check("префикс причины собран из метки и REASON_SUFFIX (один параметр на оба стиля)",
          f"%({MARK_TAG_PARAM})s || '{REASON_SUFFIX}'" in named
          and f"%s || '{REASON_SUFFIX}'" in positional)
    check("плейсхолдеров ровно столько, сколько значений передаёт вызывающий",
          named.count(f"%({MARK_TAG_PARAM})s") == 1 and positional.count("%s") == 1,
          f"named: {named.count(f'%({MARK_TAG_PARAM})s')}, "
          f"positional: {positional.count('%s')}")
    check("именованная и позиционная версии совпадают текстом",
          named % {MARK_TAG_PARAM: "@P@"} == positional.replace("%s", "@P@", 1),
          "расхождение двух версий одного выражения")
    check("REASON_PREFIX выведен из MARKER (тег и разбор не разъедутся)",
          REASON_PREFIX == MARKER + REASON_SUFFIX)
    check("параметр массива тегов и параметр текстовой метки различаются",
          MARK_PARAM != MARK_TAG_PARAM,
          f"{MARK_PARAM!r} и {MARK_TAG_PARAM!r}: один параметр не может быть "
          "и массивом, и строкой")


# ------------------------------------------------------------------------ ckb
def run_ckb(target):
    obj_uuid, snippet_id = target["uuid"], target["id"]
    print("\n" + "=" * 70)
    print("ckb_1c_configurations — enrich-сниппеты (инструменты контракта)")
    print("=" * 70)

    card = get_config_snippet(snippet_id)
    check("карточка сниппета по id читается до пометки", bool(card.get("success")),
          card.get("error") or "")
    row = card.get("row") or {}
    check("до пометки строка не в карантине", row.get("marked") is False)
    deps = [dep for dep in (row.get("dependencies") or []) if dep.get("target_name")]

    base = list_marked_config_snippets(uuid=obj_uuid, limit=500)
    check("перечень карантина выполняется и на пустом карантине (исправленный split_part)",
          bool(base.get("success")), base.get("error") or f"строк: {base.get('found')}")

    word = max((w for w in target["question"].split() if len(w) >= 5), key=len, default="")

    marked = mark_config_snippet(snippet_id, REASON)
    if not check("метка проставлена инструментом контракта", bool(marked.get("success")),
                 marked.get("error") or ""):
        return None
    check("ответ пометки читает причину обратно", marked.get("reason") == REASON,
          f"получено: {marked.get('reason')!r}")
    check("ответ пометки называет объект и его вид (узел V22)",
          bool(marked.get("object_name")) and bool(marked.get("object_kind")),
          f"{marked.get('object_name')} [{marked.get('object_kind')}]")

    card = get_config_snippet(snippet_id)
    row = card.get("row") or {}
    check("карточка по id отдаёт флаг карантина (скрытая строка не должна быть тайной)",
          row.get("marked") is True)
    check("карточка по id отдаёт причину (Python-разбор тегов)",
          row.get("marked_reason") == REASON, f"получено: {row.get('marked_reason')!r}")

    listing = list_marked_config_snippets(uuid=obj_uuid, limit=500)
    check("перечень карантина выполняется после пометки", bool(listing.get("success")),
          listing.get("error") or "")
    mine = find_by_id(listing, snippet_id)
    check("помеченная строка есть в перечне карантина", mine is not None)
    check("причину разбирает сама база (номер части 2, а не 1)",
          mine is not None and mine.get("reason") == REASON,
          f"база отдала: {(mine or {}).get('reason')!r}")
    check("в перечне есть флаг и признак объекта", bool(mine and mine.get("marked")),
          f"объект: {(mine or {}).get('object_name')}")

    if word:
        hidden = search_config_snippets(word, uuid=obj_uuid, limit=50)
        shown = search_config_snippets(word, uuid=obj_uuid, limit=50, include_marked=True)
        check("поиск по умолчанию не отдаёт помеченную строку",
              bool(hidden.get("success")) and snippet_id not in ids_of(hidden),
              f"режим {hidden.get('mode')}, найдено {hidden.get('found')}")
        hit = find_by_id(shown, snippet_id)
        check("поиск с include_marked отдаёт её и с явным флагом",
              bool(shown.get("success")) and hit is not None and hit.get("marked") is True)
    else:
        skip("скрытие из поиска",
             f"в вопросе нет слова длиннее 4 символов: {target['question'][:40]!r}")

    plain = list_config_snippets(uuid=obj_uuid, limit=500)
    withm = list_config_snippets(uuid=obj_uuid, limit=500, include_marked=True)
    check("список сниппетов объекта по умолчанию без помеченной строки",
          bool(plain.get("success")) and snippet_id not in ids_of(plain))
    rows = rows_of(withm)
    pos = next((i for i, item in enumerate(rows) if int(item["id"]) == snippet_id), None)
    check("список с include_marked отдаёт строку с флагом",
          pos is not None and rows[pos].get("marked") is True)
    check("помеченные строки идут в конце перечня",
          pos is not None and all(bool(item.get("marked")) == (i >= pos)
                                  for i, item in enumerate(rows)))

    if deps:
        dep = deps[0]
        off = get_snippets_for_object(uuid=obj_uuid, target_type=dep["target_type"],
                                      target_name=dep["target_name"])
        on = get_snippets_for_object(uuid=obj_uuid, target_type=dep["target_type"],
                                     target_name=dep["target_name"], include_marked=True)
        check("ответ «что известно про цель» по умолчанию без помеченной строки",
              bool(off.get("success")) and snippet_id not in ids_of(off),
              f"цель {dep['target_type']}:{dep['target_name']}")
        hit = find_by_id(on, snippet_id)
        check("тот же ответ с include_marked отдаёт её с флагом",
              bool(on.get("success")) and hit is not None and hit.get("marked") is True)
    else:
        skip("скрытие из ответа «что известно про цель»", "у сниппета нет зависимостей")

    described = describe_object(uuid=obj_uuid, limit=500)
    check("карточка объекта читается целиком (раздел «ЧТО ДЕЛАЕТ КОД» читает причину)",
          bool(described.get("success")), described.get("error") or "")
    counts = (described or {}).get("counts") or {}
    check("карточка считает помеченные сниппеты отдельным счётчиком",
          int(counts.get("snippets_marked") or 0) >= 1,
          f"snippets_marked={counts.get('snippets_marked')}, всего={counts.get('snippets')}")
    card_row = find_by_id({"rows": (described or {}).get("snippets") or []}, snippet_id)
    check("карточка объекта оставляет строку в перечне, но помечает её",
          card_row is not None and card_row.get("marked") is True)
    check("карточка объекта отдаёт причину строки (тот же исправленный фрагмент)",
          card_row is not None and card_row.get("marked_reason") == REASON,
          f"получено: {(card_row or {}).get('marked_reason')!r}")

    gen = generate_enrichment(uuid=obj_uuid)
    check("перегенерация обогащения выполнена", bool(gen.get("success")), gen.get("error") or "")
    after = list_marked_config_snippets(uuid=obj_uuid, limit=500)
    same = next((item for item in rows_of(after)
                 if item.get("question") == target["question"]), None)
    check("метка перенесена на строку той же идентичности (узел Q2)",
          bool(after.get("success")) and same is not None)
    check("причина перенесена вместе с меткой",
          same is not None and same.get("reason") == REASON,
          f"получено: {(same or {}).get('reason')!r}")
    new_id = int(same["id"]) if same else snippet_id

    unmark = unmark_config_snippet(new_id)
    check("снятие метки выполнено", bool(unmark.get("success")), unmark.get("error") or "")
    cleared = list_marked_config_snippets(uuid=obj_uuid, limit=500)
    check("после снятия строки в перечне карантина нет",
          bool(cleared.get("success")) and not any(
              item.get("question") == target["question"] for item in rows_of(cleared)))
    if word:
        back = search_config_snippets(word, uuid=obj_uuid, limit=50)
        # искаться должен новый id: после перегенерации строка той же идентичности лежит
        # под другим id (узел Q2), и проверка на старом id утверждала бы обратное.
        check("после снятия строка снова видна поиску",
              bool(back.get("success")) and new_id in ids_of(back),
              f"искалось по {word!r}, id в выдаче: {sorted(ids_of(back))[:10]}")
    repeat = unmark_config_snippet(new_id)
    check("повторное снятие возвращает already_unmarked, а не ошибку",
          bool(repeat.get("already_unmarked")), repeat.get("error") or "")
    return new_id


# -------------------------------------------------------------------- local_doc
def check_local_doc():
    """Тот же SQL-фрагмент на стороне local_doc: только чтение, литерал вместо таблицы."""
    print("\n" + "=" * 70)
    print("local_doc — сниппеты документации (только чтение)")
    print("=" * 70)
    conn = None
    sys.path.insert(0, str(ROOT / "tools"))
    from purge_marked_snippets import AUDIT_TABLE, find_marked_local  # noqa: E402
    try:
        conn = psycopg2.connect(**db_config("local_doc"))
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {reason_expr_named(MARK_TAG_PARAM)} AS reason "
                "  FROM (SELECT ARRAY['code', %(marktag)s, "
                "               %(marktag)s || ':reason=черновик']::text[] AS tags) t",
                {MARK_TAG_PARAM: MARKER})
            got = cur.fetchone()[0]
            check("local_doc: база разбирает причину помеченной строки",
                  got == "черновик", f"получено: {got!r}")
            cur.execute(
                f"SELECT {reason_expr_named(MARK_TAG_PARAM)} AS reason "
                "  FROM (SELECT ARRAY['code', %(marktag)s]::text[] AS tags) t",
                {MARK_TAG_PARAM: MARKER})
            empty = cur.fetchone()[0]
            check("local_doc: без тега причины разбирается пустая строка, а не текст тегов",
                  empty == "", f"получено: {empty!r}")
            # имя таблицы аудита проверяется по живой схеме: `audit_log` в local_doc нет, и
            # первая же запись в аудит ушла бы ошибкой ровно там, где она и должна быть —
            # при удалении строки.
            cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{AUDIT_TABLE}",))
            check(f"таблица аудита local_doc существует ({AUDIT_TABLE})",
                  bool(cur.fetchone()[0]), "чистка писала бы в аудит ошибкой")
            cur.execute("SELECT to_regclass('public.audit_log') IS NOT NULL")
            check("ошибочного имени audit_log в живой схеме нет (замер, а не догадка)",
                  not cur.fetchone()[0])
        rows = find_marked_local(conn, limit=5)
        check("чистка local_doc читает перечень карантина тем же фрагментом",
              isinstance(rows, list), f"строк: {len(rows)}")
        bad = [row for row in rows
               if row.get("reason", "") != reason_of(row.get("tags") or [])]
        check("причина в выдаче чистки совпадает с Python-разбором тега строки",
              not bad, f"расхождений: {len(bad)} из {len(rows)}")
    except Exception as exc:
        check("local_doc: чтение карантина выполнено", False, str(exc).splitlines()[0])
    finally:
        if conn is not None:
            conn.close()


def cleanup(obj_uuid):
    """Снять свой признак со всех строк объекта — аварийный путь не оставляет карантина."""
    listing = list_marked_config_snippets(uuid=obj_uuid, limit=500)
    for row in rows_of(listing):
        if row.get("reason") == REASON:
            unmark_config_snippet(int(row["id"]))


def main():
    print("Узел Q3: карантин сниппетов — метка, причина, скрытие, перенос при перегенерации")
    check_static_invariants()
    total_before = marked_total()
    print(f"помеченных сниппетов в ckb до проверки: {total_before}")
    check_reason_tag_order()
    target = pick_snippet()
    if not target:
        print("❌ в базе нет внешнего объекта с авто-сниппетами — загрузите эталонную пару: "
              "python tools/restore_reference_pair.py")
        return 1
    print(f"объект: {target['name']} [{target['kind']}] uuid={target['uuid']} "
          f"сниппетов: {target['snippets']}")
    print(f"сниппет: id={target['id']} source={target['source_kind']} "
          f"вопрос={target['question'][:70]!r}")
    try:
        run_ckb(target)
    finally:
        cleanup(target["uuid"])
    check_local_doc()

    total_after = marked_total()
    check("число помеченных сниппетов в БД вернулось к исходному",
          total_after == total_before, f"до={total_before}, после={total_after}")

    print("\n" + "=" * 70)
    print("ИТОГ")
    print("=" * 70)
    print(f"проверок: {len(PASSED) + len(FAILED)}, провалено: {len(FAILED)}, "
          f"пропущено: {len(SKIPPED)}")
    for name in FAILED:
        print(f"  ❌ {name}")
    for name in SKIPPED:
        print(f"  ⏭️ {name}")
    if FAILED:
        print("❌ Карантин работает не целиком.")
        return 1
    print("✅ Карантин сниппетов: метка, причина, скрытие, перенос и снятие работают.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


