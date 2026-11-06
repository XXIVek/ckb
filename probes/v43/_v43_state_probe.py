#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V43: живое состояние перечней состава в строках `configurations`.

Зонд отвечает на три вопроса, которые без замера читались бы как догадка:
какие ARRAY-колонки есть в таблице (и чем из них не является узлом V43),
сколько перечней заполнено в каждой строке заголовка и сколько в них имён.
Числа для журнала позиции берутся отсюда, а не из памяти.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402

from configuration_child_properties import (  # noqa: E402
    CHILD_COUNT, CHILD_PROPERTIES, header_array_columns,
)

V43 = list(header_array_columns())


def main():
    conn = psycopg2.connect(dbname="ckb_1c_configurations", user="postgres",
                            password=os.environ["PGPASSWORD"], host="127.0.0.1")
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'configurations' AND data_type = 'ARRAY'
        ORDER BY ordinal_position
    """)
    array_cols = [r[0] for r in cur.fetchall()]
    legacy = [c for c in array_cols if c not in set(V43)]
    print(f"ARRAY-колонок в таблице: {len(array_cols)}; "
          f"из них узла V43: {len([c for c in array_cols if c in set(V43)])}; "
          f"не узла V43: {legacy}")
    print(f"словарь модуля: колонок {CHILD_COUNT}, порядок совпадает с живой схемой: "
          f"{sorted(V43) == sorted(c for c in array_cols if c in set(V43))}")

    cur.execute("""
        SELECT id, name FROM configurations ORDER BY id
    """)
    headers = cur.fetchall()

    bad = 0
    for header_id, header_name in headers:
        # записи верхнего уровня индекса по виду (K1: depth = 0, корень не кладётся)
        cur.execute("""
            SELECT object_type, COUNT(*) FROM configuration_objects
            WHERE configuration_id = %s AND depth = 0 GROUP BY object_type
        """, (header_id,))
        counts = dict(cur.fetchall())
        depth0 = sum(counts.values())
        roots = counts.get("Configuration", 0)

        cur2 = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur2.execute(
            f"SELECT {', '.join(c for (_t, c, _n) in CHILD_PROPERTIES)} "
            "FROM configurations WHERE id = %s", (header_id,)
        )
        row = cur2.fetchone()
        cur2.close()

        filled = 0
        total = 0
        empty_arrays = 0
        absent_types = []
        mismatch = []
        for object_type, column, _n in CHILD_PROPERTIES:
            value = row[column]
            expected = counts.get(object_type, 0)
            got = 0 if value is None else len(value)
            filled += 1 if value is not None else 0
            total += got
            empty_arrays += 1 if value is not None and got == 0 else 0
            if got != expected:
                mismatch.append(f"{object_type}: массив {got}, индекс {expected}")
            if expected == 0:
                absent_types.append(object_type)
        ok = not mismatch and total == (depth0 - roots)
        bad += 0 if ok else 1
        print(f"{header_id:>5} {header_name[:40]:<40} {filled:>6}/{CHILD_COUNT} "
              f"{total:>8} {empty_arrays:>7} {depth0:>7} {roots:>7} "
              f"{'OK' if ok else 'РАСХОЖДЕНИЕ':>10}")
        if mismatch:
            print(f"       {'; '.join(mismatch[:6])}")
        print(f"       видов без объектов (перечень NULL): {len(absent_types)} — "
              f"{', '.join(absent_types)}")
    print(f"строк с расхождением перечня с индексом состава: {bad}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
