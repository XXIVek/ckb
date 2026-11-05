#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q2 узла V48: чем измеряется ключ цепочки состояния строки `session_parameters`.

Вопрос (план `docs/CONFIGURATION_SESSION_PARAMETERS_PLAN.md`, раздел 3, Q2): ключом цепочки
брать имя объекта или uuid метаданных. Решение принимает оператор; зонд даёт только факты:

  A. однозначность короткого имени внутри конфигурации — если дублей нет, имя годится как ключ
     правки (прецедент V46: `uq_subsystems_configuration_full_name_revision`);
  B. пересечение uuid метаданных МЕЖДУ конфигурациями — если одно и то же uuid встречается в
     нескольких конфигурациях, ключ без границы по конфигурации дал бы столкновение строк разных
     баз (дефект ссылки включения узла V47 П1.1);
  C. чем фактически является `full_name` для вида без иерархии: совпадает ли индексное имя с
     коротким, есть ли дети (`depth > 0`, `child_type`, `parent_name`).

Живая база читается целиком, а не по четырём выгрузкам плана: ключ проверяется на всём, что уже
загружено. Зонд ничего не пишет и к писателям не обращается.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from external_db import connect  # noqa: E402  (src/external_db.py)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OBJECT_TYPE = "SessionParameter"


def one(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def main() -> int:
    problems = 0
    conn = connect()
    try:
        cur = conn.cursor()

        print(f"=== A. круг индекса состава по виду {OBJECT_TYPE} ===")
        cur.execute(
            "SELECT c.id, c.name, c.uuid, count(*), count(*) FILTER (WHERE co.depth > 0), "
            "       count(DISTINCT co.object_name), count(DISTINCT co.uuid), "
            "       count(DISTINCT co.object_id) "
            "FROM configurations c JOIN configuration_objects co ON co.configuration_id = c.id "
            "WHERE co.object_type = %s "
            "GROUP BY c.id, c.name, c.uuid ORDER BY c.name", (OBJECT_TYPE,))
        rows = cur.fetchall()
        if not rows:
            print("  строк вида в индексе состава нет — измерять нечего")
            return 1
        total = 0
        for cfg_id, cfg_name, cfg_uuid, n, deep, names, uuids, obj_ids in rows:
            total += n
            flag = "" if (names == n and uuids == n and obj_ids == n) else "  ⚠️ различаются"
            print(f"  config id={cfg_id} {cfg_name!r}: строк {n}, depth>0 {deep}, "
                  f"distinct object_name {names}, distinct uuid {uuids}, "
                  f"distinct object_id {obj_ids}{flag}")
            if names != n or uuids != n or obj_ids != n:
                problems += 1
        print(f"  всего строк вида: {total}, конфигураций с видом: {len(rows)}")

        print("\n=== A2. дубли внутри конфигурации (решают вариант A) ===")
        for label, cols in (("object_name", "co.object_name"), ("uuid", "co.uuid"),
                            ("object_id", "co.object_id")):
            dup = one(cur, "SELECT count(*) FROM (SELECT co.configuration_id, %s "
                           "FROM configuration_objects co WHERE co.object_type = %%s "
                           "GROUP BY 1, 2 HAVING COUNT(*) > 1) d" % (cols,), (OBJECT_TYPE,))
            print(f"  дублей (configuration_id, {label}): {dup}")
            if dup:
                problems += 1
        dup_all = one(cur, "SELECT count(*) FROM (SELECT configuration_id, name "
                           "FROM configuration_objects GROUP BY 1, 2 "
                           "HAVING COUNT(*) > 1) d")
        print(f"  дублей (configuration_id, name) по всем видам — факт ограничения "
              f"configuration_objects_name_unique: {dup_all}")

        print("\n=== B. пересечение идентификаторов МЕЖДУ конфигурациями (решают вариант B) ===")
        for label, col in (("uuid", "co.uuid::text"), ("object_id", "co.object_id"),
                           ("object_name", "co.object_name")):
            shared = one(cur, "SELECT count(*) FROM (SELECT %s AS ident "
                              "FROM configuration_objects co WHERE co.object_type = %%s "
                              "GROUP BY 1 HAVING count(DISTINCT co.configuration_id) > 1) d"
                         % (col,), (OBJECT_TYPE,))
            distinct = one(cur, "SELECT count(DISTINCT %s) FROM configuration_objects co "
                                "WHERE co.object_type = %%s" % (col,), (OBJECT_TYPE,))
            cur.execute(
                "SELECT %s AS ident, count(DISTINCT co.configuration_id) AS cfgs, "
                "       array_agg(DISTINCT c.name ORDER BY c.name) "
                "FROM configuration_objects co JOIN configurations c ON c.id = co.configuration_id "
                "WHERE co.object_type = %%s GROUP BY 1 "
                "HAVING count(DISTINCT co.configuration_id) > 1 "
                "ORDER BY cfgs DESC, ident LIMIT 5" % (col,), (OBJECT_TYPE,))
            print(f"  {label}: различных значений {distinct}, из них в двух и более "
                  f"конфигурациях: {shared}")
            for ident, cfgs, names in cur.fetchall():
                print(f"    {ident} → {cfgs} конфигураций: {', '.join((names or [])[:4])}")

        print("\n=== C. чем является full_name для вида без иерархии ===")
        mismatch = one(cur, "SELECT count(*) FROM configuration_objects co "
                            "WHERE co.object_type = %s "
                            "AND co.name <> 'SessionParameter.' || co.object_name", (OBJECT_TYPE,))
        deep = one(cur, "SELECT count(*) FROM configuration_objects co WHERE co.object_type = %s "
                        "AND co.depth > 0", (OBJECT_TYPE,))
        child = one(cur, "SELECT count(*) FROM configuration_objects co WHERE co.object_type = %s "
                        "AND co.child_type IS NOT NULL AND co.child_type <> ''", (OBJECT_TYPE,))
        parent = one(cur, "SELECT count(*) FROM configuration_objects co WHERE co.object_type = %s "
                          "AND co.parent_name IS NOT NULL AND co.parent_name <> ''", (OBJECT_TYPE,))
        print(f"  индексное имя != 'SessionParameter.'||object_name: {mismatch}")
        print(f"  строк с depth > 0: {deep}; с заполненным child_type: {child}; "
              f"с заполненным parent_name: {parent}")
        if mismatch or deep or child or parent:
            print("  ⚠️ допущение «full_name = object_name» фактом не подтверждено")
            problems += 1

        print("\n=== D. состояние целевой таблицы (дельта, не пустота) ===")
        exists = one(cur, "SELECT count(*) FROM information_schema.tables "
                          "WHERE table_name = 'session_parameters'")
        if exists:
            print(f"  таблица `session_parameters` существует, строк: "
                  f"{one(cur, 'SELECT count(*) FROM session_parameters')} "
                  f"— проверка писателя меряет дельту, а не пустоту")
        else:
            print("  таблицы `session_parameters` в живой схеме нет — П1 не начинался")
    finally:
        conn.close()
    print(f"\nПРОБЛЕМНЫХ ФАКТОВ: {problems}")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
