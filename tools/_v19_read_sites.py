r"""Замер цены узла V19: сколько мест рантайм-кода обращаются к версионируемым таблицам.

Зачем. Раздел 11 `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md` оценивает объём правок V19
числом обращений к семи версионируемым таблицам: каждое из них обязано читать **текущую
ревизию**, а не произвольную строку `uuid`. Числа в нормативе обязаны быть замерными,
поэтому замер живёт в проекте, а не в `C:\TMP` (его чистит внешний процесс — п. «C:\TMP
для проб больше не годится» норматива).

Что считается. Одно совпадение = одно SQL-обращение к таблице (`FROM` / `JOIN` /
`INSERT INTO` / `UPDATE` / `DELETE FROM`). Считаются только модули рантайм-кода: `src/*.py`
кроме DDL-источников (`generate_ddl.py` — это описание схемы, а не место чтений: правится
миграцией и проверяется `_cmp_ddl.py`) и три MCP-сервера. Витрины (`v_form_elements`,
`v_form_events`, `v_config_enrichment`, `v_config_alias_targets`) и SQL-сверки в счёт не
входят: они перечислены в нормативе отдельно и выводятся из своего DDL/файлов.

Запуск: `python tools/_v19_read_sites.py` (только чтение файлов, БД не трогает).
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

TABLES = [
    "external_report", "attributes", "tabular_sections",
    "forms", "form_ext", "templates", "bsl_modules",
]
PAT = re.compile(
    r"(FROM|JOIN|INSERT INTO|UPDATE|DELETE FROM)\s+(" + "|".join(TABLES) + r")\b",
    re.I,
)

# DDL-источники и вспомогательные модулы без SQL-чтений объектов выгрузки:
# это описание схемы, а не места чтений — их правит миграция, их сверяет _cmp_ddl.py.
EXCLUDE = {"generate_ddl.py", "ddl_external_report.sql", "ddl_enrichment.sql"}

SERVERS = (
    "server_configurations_core.py",
    "server_configurations_enrichment.py",
    "server_configurations_export.py",
)


def targets():
    files = sorted(p for p in (ROOT / "src").glob("*.py") if p.name not in EXCLUDE)
    files += [ROOT / n for n in SERVERS if (ROOT / n).exists()]
    return files


def main():
    total = 0
    rows = []
    for path in targets():
        hits = PAT.findall(path.read_text(encoding="utf-8", errors="ignore"))
        if hits:
            rows.append((path.name, len(hits)))
            total += len(hits)
    for name, count in rows:
        print(f"{name}: {count}")
    print(f"МОДУЛЕЙ С ОБРАЩЕНИЯМИ: {len(rows)}")
    print(f"ИТОГО SQL-обращений к семи версионируемым таблицам в рантайм-коде: {total}")
    print("ВИТРИНЫ (правятся вместе с чтениями): v_form_elements, v_form_events, "
          "v_config_enrichment, v_config_alias_targets")


if __name__ == "__main__":
    main()