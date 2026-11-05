#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V50: индекс состава, разрешимость целей `<Content>` и состояние живой схемы.

Зачем. У общего реквизита два рода знания: свойства (замер `_v50_p0_probe.py` закрыл словарь
из 38 свойств) и применение — `<Content>` со ссылками на объекты метаданных (1 512 строк на
корпус) плюс три ссылки разделения (`SessionParameter.*`, `Constant.*`). Модель хранения
выбирается теми же вопросами, что у V48 и V49:

1. есть ли у вида строки индекса состава и какой формы (`CommonAttribute.<Имя>`, дети, uuid);
2. разрешаются ли цели применения индексом ЦЕЛИКОМ, только ПРЕФИКСОМ или ничем — это будущие
   колонки `target_*` и их состояния (прецедент Q3 узла V49);
3. разрешаются ли ссылки разделения — `SessionParameter.*` относится к виду, закрытому узлом
   V48, `Constant.*` — к слоям, которые ещё не загружены;
4. сходится ли круг: файлы каталога ↔ строки индекса ↔ перечень имён в строке заголовка
   (есть ли такой перечень колонкой в `configurations` — меряется, а не предполагается);
5. что уже есть в живой схеме (таблиц и витрин вида быть не должно — это точка отсчёта).

Ничего в БД зонд не пишет.
"""
from __future__ import annotations

import collections
import re
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

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
DIR_NAME = "CommonAttributes"
INDEX_KIND = "CommonAttribute"

if len(sys.argv) > 1:
    DUMPS = tuple(d for d in DUMPS if d in set(sys.argv[1:]))

RE_CONFIG_UUID = re.compile(r'<Configuration\s+uuid="([0-9a-fA-F-]{36})"')
RE_PROPS = re.compile(r"<Properties>(.*?)</Properties>", re.S)
RE_CONTENT = re.compile(r"<Content>(.*?)</Content>", re.S)
RE_XR_METADATA = re.compile(r"<xr:Metadata>(.*?)</xr:Metadata>", re.S)
RE_SEPARATION = re.compile(
    r"<(DataSeparationValue|DataSeparationUse|ConditionalSeparation)>(.*?)</\1>", re.S
)
OUT = ROOT / "_scratch" / "v50_p0_index.txt"


def dict_rows(cur) -> list[dict]:
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def main() -> int:
    lines: list[str] = []

    def emit(text: str = "") -> None:
        lines.append(text)

    conn = connect()
    cur = conn.cursor()

    emit("=== состояние живой схемы до узла V50")
    cur.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' "
        "AND (table_name LIKE '%%common%%' OR table_name LIKE '%%attribute%%') ORDER BY 1"
    )
    emit(f"  таблиц с 'common' или 'attribute' в имени: {[r[0] for r in cur.fetchall()]}")
    cur.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' "
        "AND table_name IN ('roles','role_rights','role_sources','role_restriction_templates',"
        "'session_parameters','subsystems','common_modules') ORDER BY 1"
    )
    emit(f"  таблиц закрытых узлов (сверка, что база живая): {[r[0] for r in cur.fetchall()]}")
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='configurations' AND (column_name LIKE '%%common%%' "
        "OR column_name LIKE '%%attribute%%') ORDER BY 1"
    )
    header_cols = cur.fetchall()
    emit(f"  колонок заголовка с 'common'/'attribute': {[(r[0], r[1]) for r in header_cols]}")

    totals: collections.Counter = collections.Counter()
    for dump in DUMPS:
        emit()
        emit(f"=== {dump}")
        directory = DUMP_ROOT / dump / DIR_NAME
        config_xml = DUMP_ROOT / dump / "Configuration.xml"
        if not config_xml.is_file():
            emit("  Configuration.xml нет")
            continue
        text = config_xml.read_text(encoding="utf-8", errors="replace")
        m = RE_CONFIG_UUID.search(text)
        cfg_uuid = m.group(1) if m else None
        if not cfg_uuid:
            emit("  ⚠️ uuid конфигурации не прочитан из Configuration.xml")
            continue
        cur.execute("SELECT id, uuid FROM configurations WHERE uuid = %s::uuid", (cfg_uuid,))
        header = cur.fetchall()
        if not header:
            emit(f"  ⚠️ конфигурация {cfg_uuid} в БД не загружена — круг индекса недоступен")
            continue
        config_id = header[0][0]
        emit(f"  configurations.id={config_id}")

        cur.execute(
            "SELECT name, object_name, object_type, child_type, depth, parent_name, object_id, uuid "
            "FROM configuration_objects WHERE configuration_id = %s AND object_type = %s "
            "ORDER BY depth, name",
            (config_id, INDEX_KIND),
        )
        rows = dict_rows(cur)
        top = [r for r in rows if not r["child_type"]]
        children = [r for r in rows if r["child_type"]]
        emit(f"  строк индекса вида: {len(rows)} (верхнего уровня {len(top)}, детей {len(children)})")
        if children:
            kinds = collections.Counter(r["child_type"] for r in children)
            emit(f"  ⚠️ дети индекса вида: {dict(kinds)}")
        mismatch = [r["name"] for r in top if r["name"] != f"{INDEX_KIND}.{r['object_name']}"]
        emit(f"  имя индекса ≠ 'CommonAttribute.'||object_name: {len(mismatch)}")
        uuid_filled = sum(1 for r in rows if r["uuid"])
        emit(f"  заполненных uuid строк вида: {uuid_filled} из {len(rows)}")
        deep = sum(1 for r in rows if (r["depth"] or 0) > 0)
        emit(f"  строк вида глубже 0 уровня: {deep}")
        for r in top[:3]:
            emit(f"    образец: name={r['name']} object_id={r['object_id']} "
                 f"uuid={(str(r['uuid']) or '—')[:8]} depth={r['depth']}")

        file_names = {p.stem for p in directory.glob("*.xml")} if directory.is_dir() else set()
        index_names = {r["object_name"] for r in top}
        emit(f"  файлов каталога: {len(file_names)}; строк индекса верхнего уровня: {len(top)}")
        emit(f"  файлы без строки индекса: {sorted(file_names - index_names)}")
        emit(f"  строки индекса без файла: {sorted(index_names - file_names)}")

        for col_name, _t in header_cols:
            cur.execute(f'SELECT "{col_name}" FROM configurations WHERE id = %s', (config_id,))
            value = cur.fetchone()[0]
            if value is None:
                emit(f"  колонка заголовка {col_name}: NULL")
            else:
                emit(f"  колонка заголовка {col_name}: {len(value)} значений {sorted(value)[:10]}")

        cur.execute("SELECT name FROM configuration_objects WHERE configuration_id = %s",
                    (config_id,))
        all_index_names = {r[0] for r in cur.fetchall()}

        if not directory.is_dir():
            emit("  каталога CommonAttributes нет — целей применения в этой конфигурации нет")
            continue

        exact = prefix = unresolved = 0
        kinds: collections.Counter = collections.Counter()
        distinct: set[str] = set()
        sep_states: dict[str, collections.Counter] = {
            "DataSeparationValue": collections.Counter(),
            "DataSeparationUse": collections.Counter(),
            "ConditionalSeparation": collections.Counter(),
        }
        for path in sorted(directory.glob("*.xml")):
            body = path.read_text(encoding="utf-8", errors="replace")
            props = RE_PROPS.search(body)
            if not props:
                continue
            content = RE_CONTENT.search(props.group(1))
            if content:
                for target in RE_XR_METADATA.findall(content.group(1)):
                    target = target.strip()
                    distinct.add(target)
                    kinds[target.split(".", 1)[0]] += 1
                    if target in all_index_names:
                        exact += 1
                        continue
                    parent = ".".join(target.split(".")[:-1])
                    if parent in all_index_names:
                        prefix += 1
                    else:
                        unresolved += 1
            for tag, value in RE_SEPARATION.findall(props.group(1)):
                value = value.strip()
                if not value:
                    sep_states[tag]["пустого значения (самозакрыв.)"] += 1
                elif value in all_index_names:
                    sep_states[tag]["разрешается индексом целиком"] += 1
                else:
                    sep_states[tag]["НЕ разрешается"] += 1
        emit(f"  целей применения: строк {exact + prefix + unresolved}, различных имён {len(distinct)}")
        emit(f"  разрешение целей: индексом целиком {exact}, только префиксом {prefix}, "
             f"ничем {unresolved}")
        emit(f"  виды целей: {dict(sorted(kinds.items(), key=lambda kv: -kv[1]))}")
        for tag, counter in sep_states.items():
            if counter:
                emit(f"  ссылки {tag}: {dict(counter)}")
        totals.update({"exact": exact, "prefix": prefix, "unresolved": unresolved})

    emit()
    emit(f"=== итог по корпусу: цели применения — целиком {totals['exact']}, "
         f"префиксом {totals['prefix']}, ничем {totals['unresolved']}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"отчёт: {OUT}  строк: {len(lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


