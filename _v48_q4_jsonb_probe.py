#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Q4 узла V48: форма jsonb («каждый тип — одна запись») — что в ней работает и что нет.

Оператор предлагает хранить значения типа записью на каждый тип в колонке jsonb. Зонд проверяет это
на живой БД в ОТКАТАННОЙ транзакции (данные таблицы не меняются):

  1. строится ли запрос «какие параметры сеанса указывают на Catalog.Организации» через
     containment-оператор `@>` и используется ли GIN-индекс (плюс план без индекса для сравнения);
  2. можно ли ограничить CHECK-ом форму записи (ключи элемента массива) — ожидание: нельзя,
     подзапрос в CHECK запрещён; фиксруется текстом ошибки, а не мнением;
  3. можно ли запретить дубликаты одного и того же типа у параметра (уникальный индекс по
     элементу jsonb) — против варианта с таблицей, где ключ `(…, ordinal)` это запрещает;
  4. разрешает ли БД вложенность форм, которые узел не ждал (дубли, лишние ключи, null вместо
     цели) — то есть что именно придётся сторожить постоянной проверкой (Q6).

Данные берутся из корпуса: 22 файла параметров сеанса с 24 ссылочными значениями (те же, что в 2.5).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from external_db import connect  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
RE_NAME = re.compile(r"<Name>([^<]*)</Name>")
RE_TYPE_BLOCK = re.compile(r"<Type>.*?</Type>", re.S)
RE_TYPE_VALUE = re.compile(r"<v8:Type(?:\s[^>]*)?>([^<]*)</v8:Type>")
RE_CFG = re.compile(r"^cfg:([A-Za-z]+)Ref\.([^.]*)")


def collect() -> list[tuple[str, list[dict]]]:
    rows: list[tuple[str, list[dict]]] = []
    for dump in DUMPS:
        directory = DUMP_ROOT / dump / "SessionParameters"
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.xml")):
            text = path.read_text(encoding="utf-8", errors="replace")
            block = RE_TYPE_BLOCK.search(text)
            if not block:
                continue
            entries = []
            for raw in RE_TYPE_VALUE.findall(block.group(0)):
                raw = raw.strip()
                match = RE_CFG.match(raw)
                if not match:
                    continue
                entries.append({
                    "value": raw,
                    "class": "object_ref",
                    "resolved": True,
                    "target_object_type": match.group(1),
                    "target_full_name": f"{match.group(1)}.{match.group(2)}",
                })
            if not entries:
                continue
            name = RE_NAME.search(text)
            rows.append((f"{dump}\\{name.group(1) if name else path.name}", entries))
    return rows


def main() -> int:
    rows = collect()
    total_entries = sum(len(entries) for _, entries in rows)
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute("begin")
        cur.execute("drop table if exists tmp_v48_sp")
        cur.execute("create temp table tmp_v48_sp (object_name text, types jsonb not null)")
        for name, entries in rows:
            cur.execute("insert into tmp_v48_sp (object_name, types) values (%s, %s::jsonb)",
                        (name, json.dumps(entries, ensure_ascii=False)))
        print(f"строок параметра: {len(rows)}, записей типа в jsonb: {total_entries}")

        cur.execute("create index tmp_v48_sp_types_gin on tmp_v48_sp using gin (types jsonb_path_ops)")
        cur.execute("analyze tmp_v48_sp")
        query = ("select object_name from tmp_v48_sp "
                 "where types @> %s::jsonb")
        for target in ("Catalog.Организации", "Catalog.НаборыГруппДоступа"):
            cur.execute("set enable_seqscan = on")
            cur.execute("explain " + query,
                        (json.dumps([{"target_full_name": target}], ensure_ascii=False),))
            plan_default = [row[0] for row in cur.fetchall()]
            cur.execute("set enable_seqscan = off")
            cur.execute("explain " + query,
                        (json.dumps([{"target_full_name": target}], ensure_ascii=False),))
            plan_forced = [row[0] for row in cur.fetchall()]
            cur.execute(query, (json.dumps([{"target_full_name": target}], ensure_ascii=False),))
            hits = [row[0] for row in cur.fetchall()]
            print(f"\nзапрос по цели {target}: параметров {len(hits)}")
            print("  план как выбрал планировщик: " + plan_default[0])
            print("  план с включённым индексом:  " + plan_forced[0])
        # 2. Что берёт CHECK, а что — нет.
        attempts = [
            ("CHECK формы верхнего уровня (массив)",
             "alter table tmp_v48_sp add constraint c_shape "
             "check (jsonb_typeof(types) = 'array')"),
            ("CHECK наличия ключа value у КАЖДОЙ записи (через подзапрос)",
             "alter table tmp_v48_sp add constraint c_entry check (not exists "
             "(select 1 from jsonb_array_elements(types) e where not (e ? 'value')))"),
            ("CHECK «если class=object_ref, то target_full_name не null»",
             "alter table tmp_v48_sp add constraint c_target check (not exists "
             "(select 1 from jsonb_array_elements(types) e "
             "where e->>'class' = 'object_ref' and not (e ? 'target_full_name')))"),
        ]
        print()
        for title, sql in attempts:
            cur.execute("savepoint attempt")
            try:
                cur.execute(sql)
                print(f"  ДОПУСТИМО:  {title}")
            except Exception as error:
                cur.execute("rollback to savepoint attempt")
                print(f"  ОТКЛОНЕНО:  {title}\n      {str(error).strip().splitlines()[0]}")

        # 3. Дубликаты записи одного и того же типа у одного параметра.
        cur.execute("insert into tmp_v48_sp (object_name, types) values (%s, %s::jsonb)",
                    ("BGU2\\Дубль", json.dumps([
                        {"value": "cfg:CatalogRef.Организации", "class": "object_ref",
                         "target_full_name": "Catalog.Организации"},
                        {"value": "cfg:CatalogRef.Организации", "class": "object_ref",
                         "target_full_name": "Catalog.Организации"}], ensure_ascii=False)))
        cur.execute("select count(*) from tmp_v48_sp where jsonb_array_length(types) <> "
                    "(select count(distinct e->>'value') from jsonb_array_elements(types) e)")
        print(f"\n  дубликаты значения внутри одного параметра: принято без отказа, "
              f"строк с дублем: {cur.fetchone()[0]}")
        cur.execute("create unique index tmp_v48_sp_first_value_key on tmp_v48_sp "
                    "((types -> 0 ->> 'value'), object_name)")
        print("  уникальный индекс возможен только по ПЕРВОЙ записи массива "
              "(`(types->0->>'value')`) — остальные в нём не участвуют")

        # 4. Лишние и отсутствующие ключи.
        cur.execute("insert into tmp_v48_sp (object_name, types) values (%s, %s::jsonb)",
                    ("BGU2\\ЛишнийКлюч", json.dumps(
                        [{"value": "cfg:CatalogRef.Организации", "class": "object_ref",
                          "extra": 1, "target_full_name": None}], ensure_ascii=False)))
        cur.execute("select count(*) from tmp_v48_sp where types->0->>'target_full_name' is null")
        print(f"  лишний ключ и null вместо цели: приняты без отказа, строк: {cur.fetchone()[0]}")
        # 5. Определение оператора (29.10.2026): одна запись — одиночный тип,
        #    несколько записей — составной. Проверяемо ли это ограничение БД.
        cur.execute("alter table tmp_v48_sp add column multiplicity text not null default 'absent'")
        cur.execute("update tmp_v48_sp set multiplicity = case "
                    "when jsonb_array_length(types) = 1 then 'single' "
                    "when jsonb_array_length(types) > 1 then 'composite' else 'absent' end")
        multiplicity_checks = [
            ("CHECK согласованности multiplicity с числом записей в jsonb",
             "alter table tmp_v48_sp add constraint c_multiplicity check (multiplicity = case "
             "when jsonb_array_length(types) = 1 then 'single' "
             "when jsonb_array_length(types) > 1 then 'composite' else 'absent' end)"),
            ("CHECK словаря состояний (IN по списку)",
             "alter table tmp_v48_sp add constraint c_known check (multiplicity in "
             "('absent', 'single', 'composite'))"),
            ("CHECK эквивалентности «нет блока» и «нет записей»",
             "alter table tmp_v48_sp add constraint c_absent_pair check "
             "((types = '[]'::jsonb) = (multiplicity = 'absent'))"),
        ]
        print()
        for title, sql in multiplicity_checks:
            cur.execute("savepoint attempt2")
            try:
                cur.execute(sql)
                print(f"  ДОПУСТИМО:  {title}")
            except Exception as error:
                cur.execute("rollback to savepoint attempt2")
                print(f"  ОТКЛОНЕНО:  {title}\n      {str(error).strip().splitlines()[0]}")
        cur.execute("savepoint attempt3")
        try:
            cur.execute("insert into tmp_v48_sp (object_name, types, multiplicity) values "
                        "('BGU2\\НевернаяМультипликативность', %s::jsonb, 'single')",
                        (json.dumps([{"value": "xs:string"}, {"value": "xs:boolean"}],
                                    ensure_ascii=False),))
            cur.execute("rollback to savepoint attempt3")
            print("  ОТКЛОНЕНО:  строка «2 записи, но single» прошла — CHECK не работает")
        except Exception as error:
            cur.execute("rollback to savepoint attempt3")
            print("  ОТКЛОНЕНА вставкой: строка «2 записи, но single» — CHECK работает, "
                  f"текст: {str(error).strip().splitlines()[0]}")
        cur.execute("select multiplicity, count(*) from tmp_v48_sp group by 1 order by 2 desc")
        print("  распределение по 22 файлам со ссылочным значением (тестовая таблица зонда, "
              "включая две строки-исключения): " + ", ".join(
                  f"{value} {count}" for value, count in cur.fetchall())
              + "; по корпусу 207 файлов — 201 с одним значением и 6 с двумя (2.4.3)")

        # 6. Частичный индекс по признаку составного типа.
        cur.execute("create index tmp_v48_sp_composite_idx on tmp_v48_sp (object_name) "
                    "where multiplicity = 'composite'")
        cur.execute("select count(*) from pg_indexes where tablename = 'tmp_v48_sp' "
                    "and indexname = 'tmp_v48_sp_composite_idx'")
        print(f"  частичный индекс WHERE multiplicity = 'composite': создан, "
              f"строк в pg_indexes: {cur.fetchone()[0]}")
        print("  вывод: форма записи и связь цели сторожат постоянная проверка (Q6) и код разбора, "
              "CHECK — форма верхнего уровня и согласованность мультипликативности")
        return 0

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
