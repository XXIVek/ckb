#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_v52_o1_link_semantics.py — замер позиции O1 узла V52: связаны ли ссылки других слоёв
на вид `FilterCriterion.*` со строкой самого вида (позиция Q9/O1 плана).

Зачем. Ссылки на критерии отбора лежат в кругах ДРУГИХ узлов: перечень подсистем
(`subsystem_content`, узел V46) и права ролей (`role_rights`, узел V49). Узел V52 строки этих
таблиц не трогал и не утверждал, что ссылка указывает на строку вида, — позиция открыта
планом (`docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md`, раздел 6 Q9 и раздел 8): эталон 14/17
называется, а утверждение «ссылка связана со строкой вида» — нет. Прежний зонд
`_v52_q9_links_probe.sql` на вопрос не отвечал: он спрашивал про наличие таблиц вида в схеме
(до узла V52 — «нет», после — «есть»), а связку со строкой вида не проверял вовсе.

Как измеряется. Семь фактов, каждый — отдельной сверкой с числом в детали:

  Ф1 — сколько ссылок каждой ноги и сколько строк вида лежит по каждой конфигурации;
  Ф2 — в каком состоянии разрешения записаны ссылки и разрешаются ли их uuid записями
       индекса состава той же конфигурации (тем самым механизмом, который означает состояние);
  Ф3 — связывается ли ссылка со строкой вида витрины текущего состояния по паре
       (`configuration_uuid`, `object_uuid`) и сколько остаётся висящих;
  Ф4 — симметричны ли ноги: покрыты ли цели прав включениями в подсистемы — это «механизм
       подсистем» конфигуратора (пакетная операция разработчика), а не отношение модели;
  Ф5 — зависит ли состояние ссылки от наличия строки вида: круг вида одной конфигурации
       снимается в SAVEPOINT, замер повторяется, точка сохранения откатывается;
  Ф6 — какие имена и значения прав выданы на вид (закрытые словари имени и значения V49);
  Ф7 — есть ли внешний ключ между кругами (почему связку держит вывод, а не схема).

Чего замер НЕ доказывает. Он не утверждает правомочие ролей и не трактует значения `<value>`
(позиция O1 узла V49 закрыта своим замером). Он не утверждает, что цель ссылки существует в
выгрузке как объект метаданных, — состояние разрешения говорит про индекс состава. Он не делает
вывода о смысле отсутствия ссылок: у конфигурации без включений вида в подсистемы их
действительно нет (KomMag даёт нули при одной строке вида). Числа Ф1…Ф4 — живой замер на дату
прогона и эталоном не становятся (правило `rules:core-rules:functional:answer-and-evidence`,
пункт 3: числа в правилах датированы и друг друга не подменяют).

Запуск:
    python _v52_o1_link_semantics.py        # все семь фактов по всей базе
Только чтение: единственная запись (Ф5) выполняется в SAVEPOINT и откатывается, соединение
закрывается откатом.

Код возврата 0 — все семь фактов измерены и противоречий нет; 1 — хотя бы один факт не
измерен (нет таблиц чужих кругов, нет строк вида, отказ запроса) или сверка не пройдена.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from external_db import connect  # noqa: E402

VIEW_NAME = "v_current_filter_criteria"
SUBSYSTEM_TABLE = "subsystem_content"
ROLE_RIGHTS_TABLE = "role_rights"
CRITERION_TYPE = "FilterCriterion"
RESOLVED_STATES = ("resolved=true", "target_resolve_state=exact")
LINKS_CTE = f"""
WITH links AS (
    SELECT '{SUBSYSTEM_TABLE}' AS source, sc.configuration_uuid,
           sc.target_object_uuid AS target_uuid, sc.target_full_name,
           CASE WHEN sc.resolved THEN 'resolved=true' ELSE 'resolved=false' END AS link_state
    FROM {SUBSYSTEM_TABLE} sc
    WHERE sc.target_object_type = '{CRITERION_TYPE}'
    UNION ALL
    SELECT '{ROLE_RIGHTS_TABLE}', rr.configuration_uuid, rr.target_object_uuid,
           rr.target_full_name, 'target_resolve_state=' || rr.target_resolve_state
    FROM {ROLE_RIGHTS_TABLE} rr
    WHERE rr.target_kind = '{CRITERION_TYPE}'
)"""

PASSED: list[str] = []
FAILED: list[str] = []
SKIPPED: list[tuple[str, str]] = []
INFO: list[str] = []


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"\n       {detail}" if detail else ""))
    return bool(ok)


def skip(name, reason):
    SKIPPED.append((name, reason))
    print(f"SKIP {name}\n       {reason}")


def info(text):
    INFO.append(text)
    print("INFO " + text)


def section(title):
    print("\n" + "=" * 78)
    print(title)
    print("-" * 78)


def table_exists(cur, table):
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
    return cur.fetchone() is not None


def rows(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchall()


def one_value(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


# ═══ Ф1…Ф3 — числа, состояния и связка со строкой вида ══════════════════════════════════
def fact_counts(cur):
    """Ф1 — ссылки по ногам и конфигурациям против строк вида той же конфигурации."""
    section("Ф1 — сколько ссылок на вид и сколько строк вида по каждой конфигурации")
    if not (table_exists(cur, SUBSYSTEM_TABLE) and table_exists(cur, ROLE_RIGHTS_TABLE)
            and table_exists(cur, VIEW_NAME)):
        skip("Ф1 — числа круга",
             f"таблиц нет в живой базе ({SUBSYSTEM_TABLE} / {ROLE_RIGHTS_TABLE} / {VIEW_NAME}) "
             "— круги узлов V46, V49 или V52 в этой базе не загружались")
        return None
    per_config = rows(cur, f"""
        SELECT c.name, c.uuid,
               (SELECT count(*) FROM {SUBSYSTEM_TABLE} sc
                 WHERE sc.target_object_type = '{CRITERION_TYPE}'
                   AND sc.configuration_uuid = c.uuid) AS subsystem_links,
               (SELECT count(*) FROM {ROLE_RIGHTS_TABLE} rr
                 WHERE rr.target_kind = '{CRITERION_TYPE}'
                   AND rr.configuration_uuid = c.uuid) AS role_links,
               (SELECT count(*) FROM {VIEW_NAME} fc
                 WHERE fc.configuration_uuid = c.uuid) AS view_rows
        FROM configurations c
        ORDER BY c.name""")
    totals = [sum(int(row[i]) for row in per_config) for i in (2, 3, 4)]
    for name, _uuid, subs, rights_, views in per_config:
        info(f"{name}: ссылок подсистем {subs}, прав ролей {rights_}, строк вида {views}")
    check("Ф1: числа названы по каждой ноге и по каждой конфигурации отдельно, а не одним "
          "итогом", len(per_config) > 0,
          f"конфигураций {len(per_config)}, всего: подсистем {totals[0]}, прав {totals[1]}, "
          f"строк вида {totals[2]}")
    return per_config, totals


def fact_states(cur):
    """Ф2 — состояние ссылки означает разрешение индексом состава, а не строку вида."""
    section("Ф2 — состояния ссылок и разрешение их uuid индексом состава той же конфигурации")
    if not table_exists(cur, SUBSYSTEM_TABLE) or not table_exists(cur, ROLE_RIGHTS_TABLE):
        skip("Ф2 — состояния ссылок", "таблиц чужих кругов в базе нет")
        return None
    states = rows(cur, LINKS_CTE + """
        SELECT l.source, l.link_state, count(*) AS links,
               count(*) FILTER (WHERE l.target_uuid IS NOT NULL) AS with_target_uuid,
               count(co.uuid) AS matched_index_rows
        FROM links l
        JOIN configurations c ON c.uuid = l.configuration_uuid
        LEFT JOIN configuration_objects co
               ON co.configuration_id = c.id AND co.uuid = l.target_uuid
        GROUP BY 1, 2 ORDER BY 1, 2""")
    if not states:
        skip("Ф2 — состояния ссылок", "ссылок на вид в базе нет — состояний для замера нет")
        return None
    for source, state, links, with_uuid, matched in states:
        info(f"{source}: состояние `{state}`, ссылок {links}, uuid заполнен у {with_uuid}, "
             f"записей индекса состава той же конфигурации нашлось {matched}")
    broken = [f"{source}/{state}: uuid есть, записи индекса нет ({int(with_uuid) - int(matched)})"
              for source, state, _links, with_uuid, matched in states
              if int(with_uuid) > int(matched)]
    check("Ф2: каждая ссылка с uuid имеет запись индекса состава той же конфигурации "
          "(иначе состояние разрешения врёт)", not broken, "; ".join(broken))
    return states


def fact_link_to_view_row(cur):
    """Ф3 — связка «ссылка → строка вида» по паре (configuration_uuid, object_uuid)."""
    section("Ф3 — связывается ли ссылка со строкой вида витрины текущего состояния")
    if not table_exists(cur, VIEW_NAME):
        skip("Ф3 — связка со строкой вида", f"витрины {VIEW_NAME} в базе нет (узел V52 не загружен)")
        return None
    result = rows(cur, LINKS_CTE + f"""
        SELECT l.source, c.name, count(*) AS links,
               count(fc.object_uuid) AS matched_view_rows,
               count(*) - count(fc.object_uuid) AS dangling,
               count(*) FILTER (WHERE l.link_state IN {RESOLVED_STATES}
                                 AND fc.object_uuid IS NULL) AS says_resolved_but_no_row
        FROM links l
        JOIN configurations c ON c.uuid = l.configuration_uuid
        LEFT JOIN {VIEW_NAME} fc
               ON fc.configuration_uuid = l.configuration_uuid
              AND fc.object_uuid = l.target_uuid
        GROUP BY 1, 2 ORDER BY 1, 2""")
    if not result:
        skip("Ф3 — связка со строкой вида", "ссылок на вид в базе нет")
        return None
    dangling_total = 0
    for source, name, links, matched, dangling, says_yes in result:
        dangling_total += int(dangling)
        info(f"{name} / {source}: ссылок {links}, совпало со строкой вида {matched}, "
             f"висящих {dangling}, из них «разрешено, но строки нет» {says_yes}")
    check("Ф3: висящих ссылок на вид нет — каждая цель имеет строку вида по паре "
          "configuration_uuid + object_uuid", dangling_total == 0, f"висящих: {dangling_total}")
    return result


def fact_leg_symmetry(cur):
    """Ф4 — ноги не симметричны: наличие права не влечёт включения в подсистему."""
    section("Ф4 — симметричны ли ноги: цели прав против включений в подсистемы")
    if not (table_exists(cur, SUBSYSTEM_TABLE) and table_exists(cur, ROLE_RIGHTS_TABLE)):
        skip("Ф4 — симметрия ног", "таблиц чужих кругов в базе нет")
        return None
    right_targets = int(one_value(cur, f"""
        SELECT count(*) FROM (SELECT DISTINCT configuration_uuid, target_object_uuid
                              FROM {ROLE_RIGHTS_TABLE}
                              WHERE target_kind = '{CRITERION_TYPE}'
                                AND target_object_uuid IS NOT NULL) t""") or 0)
    covered = int(one_value(cur, f"""
        SELECT count(*) FROM (SELECT DISTINCT rr.configuration_uuid, rr.target_object_uuid
                              FROM {ROLE_RIGHTS_TABLE} rr
                              JOIN {SUBSYSTEM_TABLE} sc
                                ON sc.configuration_uuid = rr.configuration_uuid
                               AND sc.target_object_uuid = rr.target_object_uuid
                               AND sc.target_object_type = '{CRITERION_TYPE}'
                              WHERE rr.target_kind = '{CRITERION_TYPE}'
                                AND rr.target_object_uuid IS NOT NULL) t""") or 0)
    subsystem_targets = int(one_value(cur, f"""
        SELECT count(*) FROM (SELECT DISTINCT configuration_uuid, target_object_uuid
                              FROM {SUBSYSTEM_TABLE}
                              WHERE target_object_type = '{CRITERION_TYPE}'
                                AND target_object_uuid IS NOT NULL) t""") or 0)
    has_rights = int(one_value(cur, f"""
        SELECT count(*) FROM (SELECT DISTINCT sc.configuration_uuid, sc.target_object_uuid
                              FROM {SUBSYSTEM_TABLE} sc
                              JOIN {ROLE_RIGHTS_TABLE} rr
                                ON rr.configuration_uuid = sc.configuration_uuid
                               AND rr.target_object_uuid = sc.target_object_uuid
                               AND rr.target_kind = '{CRITERION_TYPE}'
                              WHERE sc.target_object_type = '{CRITERION_TYPE}'
                                AND sc.target_object_uuid IS NOT NULL) t""") or 0)
    info(f"уникальных целей прав {right_targets}, из них тот же объект включён в подсистемы "
         f"той же конфигурации {covered}; уникальных включений в подсистемы {subsystem_targets}, "
         f"из них право на тот же объект имеет {has_rights}")
    if right_targets == 0 and subsystem_targets == 0:
        skip("Ф4 — симметрия ног", "ни одной ссылки на вид в базе — сравнение неприменимо")
        return None
    check("Ф4: цели прав совпадают с включениями в подсистемы той же конфигурации — след "
          "пакетной операции конфигуратора («механизм подсистем»), а не совпадение двух "
          "загрузчиков", right_targets == covered,
          f"целей прав {right_targets}, покрыто включениями {covered}")
    check("Ф4: наличие права НЕ влечёт включения в подсистему (обратное — не инвариант)",
          has_rights < subsystem_targets,
          f"включений {subsystem_targets}, из них с правом {has_rights}; равенство означало бы, "
          "что ноги — одна и та же нога")
    return right_targets, covered, subsystem_targets, has_rights


# ═══ Ф5 — зависит ли состояние ссылки от наличия строки вида ════════════════════════════
def fact_state_vs_row(cur):
    """Ф5 — снятие строк вида не меняет состояний ссылок: связка выводная, а не хранимая."""
    section("Ф5 — что станет со ссылками, если строк вида не станет (SAVEPOINT + откат)")
    if not (table_exists(cur, VIEW_NAME) and table_exists(cur, SUBSYSTEM_TABLE)
            and table_exists(cur, ROLE_RIGHTS_TABLE)):
        skip("Ф5 — эксперимент со снятием круга вида", "таблиц круга или чужих кругов в базе нет")
        return None
    target = rows(cur, f"""
        SELECT c.name, c.uuid,
               (SELECT count(*) FROM {VIEW_NAME} fc
                 WHERE fc.configuration_uuid = c.uuid) AS views,
               (SELECT count(*) FROM {SUBSYSTEM_TABLE} sc
                 WHERE sc.target_object_type = '{CRITERION_TYPE}'
                   AND sc.configuration_uuid = c.uuid) AS subs,
               (SELECT count(*) FROM {ROLE_RIGHTS_TABLE} rr
                 WHERE rr.target_kind = '{CRITERION_TYPE}'
                   AND rr.configuration_uuid = c.uuid) AS rights
        FROM configurations c
        WHERE EXISTS (SELECT 1 FROM {VIEW_NAME} fc WHERE fc.configuration_uuid = c.uuid)
          AND (EXISTS (SELECT 1 FROM {SUBSYSTEM_TABLE} sc
                        WHERE sc.target_object_type = '{CRITERION_TYPE}'
                          AND sc.configuration_uuid = c.uuid)
               OR EXISTS (SELECT 1 FROM {ROLE_RIGHTS_TABLE} rr
                           WHERE rr.target_kind = '{CRITERION_TYPE}'
                             AND rr.configuration_uuid = c.uuid))
        ORDER BY c.name""")
    if not target:
        skip("Ф5 — эксперимент со снятием круга вида",
             "нет конфигурации, где есть и строки вида, и ссылки на него: круг вида или круг "
             "ссылок в этой базе не загружен — это состояние базы, а не пропуск замера")
        return None
    name, uuid = str(target[0][0]), target[0][1]
    info(f"эксперимент на конфигурации {name}: строк вида {target[0][2]}, ссылок подсистем "
         f"{target[0][3]}, прав ролей {target[0][4]}")

    def measure(tag):
        got = rows(cur, LINKS_CTE + f"""
            SELECT l.source, count(*) AS links,
                   count(*) FILTER (WHERE l.link_state IN {RESOLVED_STATES}) AS resolved,
                   count(fc.object_uuid) AS matched,
                   count(*) FILTER (WHERE l.link_state IN {RESOLVED_STATES}
                                     AND fc.object_uuid IS NULL) AS says_resolved_but_no_row
            FROM links l
            LEFT JOIN {VIEW_NAME} fc
                   ON fc.configuration_uuid = l.configuration_uuid
                  AND fc.object_uuid = l.target_uuid
            WHERE l.configuration_uuid = %s
            GROUP BY 1 ORDER BY 1""", [uuid])
        for source, links, resolved, matched, no_row in got:
            info(f"замер {tag} / {source}: ссылок {links}, состояний «разрешено» {resolved}, "
                 f"совпало со строкой вида {matched}, «разрешено, но строки нет» {no_row}")
        return got

    def view_rows():
        return int(one_value(cur, f"SELECT count(*) FROM {VIEW_NAME} "
                                  "WHERE configuration_uuid = %s", [uuid]) or 0)

    def state_key(got):
        return [(str(r[0]), int(r[1]), int(r[2])) for r in got]

    views_before, before = view_rows(), measure("до снятия круга вида")
    if not before:
        skip("Ф5 — эксперимент", "ссылок этой конфигурации нет")
        return None
    cur.execute("SAVEPOINT v52_o1_probe")
    try:
        cur.execute("DELETE FROM filter_criteria WHERE configuration_uuid = %s", (uuid,))
        removed = int(cur.rowcount or 0)
        during = measure("после снятия круга вида (внутри SAVEPOINT)")
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT v52_o1_probe")
    after, views_after = measure("после ROLLBACK TO SAVEPOINT"), view_rows()
    info(f"в эксперименте снято строк вида {removed} (каскад снял строки условия); после отката "
         f"точки сохранения строк вида снова {views_after}")
    check("Ф5: откат точки сохранения вернул круг вида — проба не меняет базу",
          views_before == views_after, f"до {views_before}, после отката {views_after}")
    lost = sum(int(r[4]) for r in during)
    check("Ф5: после снятия строк вида состояния ссылок НЕ изменились, а связка пропала: "
          "`resolved`/`exact` описывают разрешение индексом состава, а не наличие строки вида",
          state_key(during) == state_key(before) and lost > 0,
          f"«разрешено, но строки вида нет» стало {lost}; состояния до {state_key(before)}, "
          f"в эксперименте {state_key(during)}")
    return before, during, after


# ═══ Ф6, Ф7 — имена прав и отсутствие ключа между кругами ══════════════════════════════
def fact_right_names(cur):
    """Ф6 — какие имена и значения прав выданы на вид (словари имени и значения V49)."""
    section("Ф6 — имена и значения прав, выданных на вид")
    if not table_exists(cur, ROLE_RIGHTS_TABLE):
        skip("Ф6 — имена прав", f"таблицы {ROLE_RIGHTS_TABLE} в базе нет")
        return None
    got = rows(cur, f"""
        SELECT right_name, right_name_state, right_value_state, count(*) AS rights
        FROM {ROLE_RIGHTS_TABLE} WHERE target_kind = '{CRITERION_TYPE}'
        GROUP BY 1, 2, 3 ORDER BY 4 DESC, 1""")
    if not got:
        skip("Ф6 — имена прав", "прав на вид в базе нет — состояние выгрузки, а не потеря данных")
        return None
    for name, name_state, value_state, count in got:
        info(f"право `{name}` (состояние имени `{name_state}`, значение `{value_state}`): {count}")
    unknown = [f"{name} — состояние имени `{state}`"
               for name, state, _value, _count in got if state != "known"]
    check("Ф6: имена прав на вид распознаны словарём узла V49 (состояний `unknown_name` нет)",
          not unknown, "; ".join(unknown))
    return got


def fact_no_foreign_key(cur):
    """Ф7 — внешнего ключа между кругами нет: связку держит вывод по паре, а не схема."""
    section("Ф7 — есть ли внешний ключ между чужими кругами и таблицей вида")
    got = rows(cur, """
        SELECT conrelid::regclass::text AS child, conname, confrelid::regclass::text AS parent
        FROM pg_constraint
        WHERE confrelid IN ('filter_criteria'::regclass,
                            'filter_criterion_content'::regclass)
          AND conrelid IN ('subsystem_content'::regclass, 'role_rights'::regclass)""")
    for child, conname, parent in got:
        info(f"{child} → {parent}: {conname}")
    check("Ф7: внешнего ключа `subsystem_content`/`role_rights` → `filter_criteria` нет "
          "(осознанно, прецедент V20.1: цель бывает `prefix_only` или `unresolved`)",
          not got, f"найдено ключей: {len(got)}")
    return got


def main() -> int:
    print("=== замер позиции O1 узла V52: ссылки других слоёв на вид против строки вида ===")
    print("база ckb_1c_configurations; только чтение, запись Ф5 выполняется в SAVEPOINT "
          "и откатывается")
    conn = connect()
    try:
        cur = conn.cursor()
        for fact in (fact_counts, fact_states, fact_link_to_view_row, fact_leg_symmetry,
                     fact_state_vs_row, fact_right_names, fact_no_foreign_key):
            fact(cur)
        conn.rollback()
    except Exception as exc:  # noqa: BLE001 — отказ замера обязан быть назван, а не оборван
        print(f"FAIL замер прерван исключением: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

    print("\n" + "=" * 78)
    print(f"ИТОГ: пройдено {len(PASSED)}, провалено {len(FAILED)}, пропущено {len(SKIPPED)}, "
          f"заметок {len(INFO)}")
    for name in FAILED:
        print("  ПРОВАЛ: " + name)
    for name, reason in SKIPPED:
        print(f"  ПРОПУСК: {name} — {reason}")
    if not FAILED and not SKIPPED:
        print("вывод замера: ссылки подсистем (V46) и прав ролей (V49) на вид разрешаются "
              "индексом состава той же конфигурации и связываются со строкой вида по паре "
              "(configuration_uuid, object_uuid); связка выводная — ни в выгрузке, ни в схеме "
              "её нет, поэтому состояние ссылки о наличии строки вида не утверждает ничего; "
              "наличие права не влечёт включения в подсистему, а отсутствие ссылок — отсутствия "
              "вида; числа Ф1…Ф4 датированы и эталоном постоянной проверки не становятся")
        return 0
    print("вывод замера: не все факты получены — утверждения позиции в карточке и плане "
          "оставаться в силе не могут, требуется прогон на полном корпусе")
    return 1


if __name__ == "__main__":
    sys.exit(main())




