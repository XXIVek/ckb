#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 узла V48: сколько ссылок у параметра сеанса и разрешаются ли они индексом состава.

Вопрос (план, раздел 3, Q4): разрешать ли ссылочный тип индексом. Прежний зонд
`_v48_p0_ref_probe.py` считал ПЕРВОЕ значение `<v8:Type>` в файле и дал «22 из 22». После Q3
(значение типа — массив, 2.4.3) считать надо ВСЕ значения: у 2 файлов их по два, и именно
множественность ссылки решает, класть цель в колонки той же строки или в отдельную таблицу по
образцу `subsystem_content`.

Зонд измеряет: все значения `cfg:*`; разрешимость правилом перехода `cfg:<Вид>Ref.<Имя>` →
`<Вид>.<Имя>` индексом состава живой БД (отдельно все строки индекса и только признанные
текущими); заполнимость `ref_target_uuid`; файлы с двумя и более ссылками; вес целей.

Выгрузка, не загруженная в БД, называется отдельно: «ссылок нет» и «конфигурация не загружена,
разрешить нечем» — разные состояния (прецедент D3 узла V46). Зонд ничего не пишет.
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from external_db import connect  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
DIR_NAME = "SessionParameters"

RE_CONFIG_UUID = re.compile(r'<Configuration\s+uuid="([0-9a-fA-F-]{36})"')
RE_NAME = re.compile(r"<Name>([^<]*)</Name>")
RE_TYPE_BLOCK = re.compile(r"<Type>(.*?)</Type>", re.S)
RE_TYPE_VALUE = re.compile(r"<v8:Type(?:\s[^>]*)?>([^<]*)</v8:Type>")
RE_CFG = re.compile(r"^cfg:([A-Za-z]+)Ref\.([^.]*)")

STANDARD_TAILS = ("Ссылка", "ПометкаУдаления", "ЭтоНовый", "Представление", "Владелец")


def candidates(raw: str) -> list[str]:
    """Индексные имена, которые может описывать ссылочный тип `cfg:…Ref.…`."""
    match = RE_CFG.match(raw)
    if not match:
        return []
    kind, object_name = match.group(1), match.group(2)
    base = f"{kind}.{object_name}"
    out = [base]
    tail = raw.split(f"cfg:{kind}Ref.{object_name}", 1)[1].lstrip(".")
    if tail and tail not in STANDARD_TAILS:
        out.append(f"{base}.{tail}")
    return out


def dict_rows(cur) -> list[dict]:
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def main() -> int:
    conn = connect()
    total_values = 0
    ref_files: Counter = Counter()
    target_in: dict[str, list[str]] = defaultdict(list)
    resolved_all = 0
    resolved_current = 0
    unresolved: list[tuple[str, str, list[str]]] = []
    uuid_filled = 0
    not_loaded: list[str] = []
    notes: list[str] = []

    try:
        cur = conn.cursor()
        for dump in DUMPS:
            directory = DUMP_ROOT / dump / DIR_NAME
            config_xml = DUMP_ROOT / dump / "Configuration.xml"
            if not directory.exists() or not config_xml.exists():
                continue
            match = RE_CONFIG_UUID.search(
                config_xml.read_text(encoding="utf-8", errors="replace"))
            if not match:
                not_loaded.append(f"{dump}: uuid конфигурации не прочитан из Configuration.xml")
                continue
            cur.execute("select id, name from configurations where uuid = %s::uuid",
                        (match.group(1),))
            header = cur.fetchall()
            if not header:
                not_loaded.append(f"{dump}: конфигурация {match.group(1)} в БД не загружена")
                continue
            config_id = header[0][0]
            cur.execute("select * from configuration_objects where configuration_id = %s",
                        (config_id,))
            rows = dict_rows(cur)
            if not rows:
                not_loaded.append(f"{dump}: индекс состава пуст (configurations.id={config_id})")
                continue
            columns = set(rows[0])
            name_key = next((k for k in ("full_name", "name") if k in columns), None)
            if name_key is None:
                notes.append(f"{dump}: в configuration_objects нет name/full_name — "
                             f"есть {sorted(columns)}")
                continue
            uuid_key = "uuid" if "uuid" in columns else None
            all_names = {str(r[name_key]) for r in rows}
            current_names = all_names
            if "is_committed" in columns:
                current_names = {str(r[name_key]) for r in rows if r.get("is_committed")}
                notes.append(f"{dump}: строк индекса {len(all_names)}, "
                             f"признанных текущими {len(current_names)}")
            by_name = {str(r[name_key]): r for r in rows}

            for path in sorted(directory.glob("*.xml")):
                text = path.read_text(encoding="utf-8", errors="replace")
                block = RE_TYPE_BLOCK.search(text)
                if not block:
                    continue
                values = [v.strip() for v in RE_TYPE_VALUE.findall(block.group(1))]
                refs = [v for v in values if v.startswith("cfg:")]
                if not refs:
                    continue
                ref_files[f"{dump}\\{path.name}"] = len(refs)
                name_match = RE_NAME.search(text)
                parameter = name_match.group(1) if name_match else path.name
                for raw in refs:
                    total_values += 1
                    cands = candidates(raw)
                    hit = next((c for c in cands if c in all_names), None)
                    if next((c for c in cands if c in current_names), None):
                        resolved_current += 1
                    if hit:
                        resolved_all += 1
                        row = by_name[hit]
                        if uuid_key and row.get(uuid_key):
                            uuid_filled += 1
                        target_in[hit].append(f"{dump}\\{parameter}")
                    else:
                        unresolved.append((dump, f"{parameter} → {raw}", cands))
    finally:
        conn.close()

    print("=== разрешимость ссылок индексом состава (живая БД) ===")
    print(f"  значений `cfg:*` во всех файлах: {total_values} "
          f"(прежний зонд считал первое значение в файле — 22)")
    print(f"  разрешено по всем строкам индекса: {resolved_all}, "
          f"по признанным текущими: {resolved_current}, не разрешено: {len(unresolved)}")
    print(f"  из разрешённых имеют uuid цели (заполнима ref_target_uuid): {uuid_filled}")
    for note in notes:
        print(f"  {note}")
    for note in not_loaded:
        print(f"  СОСТОЯНИЕ: {note}")
    for dump, line, cands in unresolved[:15]:
        print(f"  НЕ РАЗРЕШЕНО {dump}: {line}; проверялись имена {cands}")

    multi = {name: count for name, count in ref_files.items() if count > 1}
    print("\n=== множественность ссылки у одного параметра ===")
    print(f"  файлов со ссылочным типом: {len(ref_files)}, "
          f"из них с ДВУМЯ ссылками: {len(multi)}")
    for name, count in sorted(multi.items()):
        print(f"    {name}: ссылок {count}")

    print("\n=== цели и их вес (запрос «какие параметры указывают на объект») ===")
    print(f"  различных целей: {len(target_in)}")
    for target, parameters in sorted(target_in.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"  {target}: ссылок {len(parameters)}")
        for parameter in parameters[:4]:
            print(f"      {parameter}")

    print("\nЧисла для решения Q4 сняты своим прогоном; решение — за оператором.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


