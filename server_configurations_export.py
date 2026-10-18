#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP-сервер `1c-configurations-export` — реверс-инжиниринг конфигурации в файлы.

ВЕДЁТСЯ ВРУЧНУЮ. Прежний генератор `generate_servers.py` удалён 14.10.2026: он писал шапку только
с sys/pathlib/fastmcp и терял импорты из `src/`, а тела инструментов брал из устаревшего монолита
`server_configurations.py` — у сгенерированной версии было 6 инструментов, вызывающих
несуществующие `_export_config_changes`, `_get_export_log`, `_mark_object_modified`,
`_get_modified_objects`, `_clear_modified_flag`, `_count_modified_objects` (замер 13.10.2026: 6/6
падают `NameError`).

Сценарий экспорта НЕ реализован, инструментов экспорта здесь больше нет. Причины (проверено
по живой схеме `ckb_1c_configurations`, а не по описанию):

  * код `src/config_export_manager.py` и `src/config_change_tracker.py` подключался к базе
    `configurations`, которой на сервере нет (есть `ckb_1c_configurations` и `local_doc`) — оба
    модуля удалены 14.10.2026 вместе с мёртвым кодом `src/config_tools.py`;
  * они читали таблицы `configuration`, `configuration_objects`, `config_export_log` —
    в живой схеме их нет;
  * главное: в текущей схеме нет объектов, которые изменяются В БАЗЕ. Загрузчик пишет
    содержимое выгрузки как есть, обогащение (config_aliases, config_snippets) метаданные
    тоже не меняет. Возвращать «изменённые объекты» в XML нечего.

Что осталось полезным: один инструмент диагностики `export_readiness_tool()`. Он не обещает
экспорт, а по живой схеме показывает, чего именно не хватает, чтобы сценарий появился
(узел V18: таблица объектов конфигурации с их XML + отслеживание изменений + сборка XML).
"""
import sys
from pathlib import Path

src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))
from fastmcp import FastMCP  # noqa: E402
from external_db import transaction  # noqa: E402
# Узел V19, закрытие S2 (18.10.2026): счётчик внешних объектов читается из витрины текущего
# состояния. С историей `COUNT(*) FROM external_report` посчитал бы каждое состояние каждого
# объекта, а не число объектов; формулировку даёт только src/current_revision.py (S1).
from current_revision import current_view  # noqa: E402

mcp = FastMCP("1c-configurations-export")

# что должно существовать, чтобы экспорт имел смысл: объекты, изменяемые в базе, и журнал
REQUIRED_TABLES = ("configuration_objects", "modified_objects", "config_export_log")


def _table_exists(cur, table):
    cur.execute("SELECT to_regclass(%s) IS NOT NULL AS ok", (f"public.{table}",))
    return bool(cur.fetchone()[0])


@mcp.tool()
def export_readiness_tool():
    """Готов ли сценарий экспорта (реверс-инжиниринга) и чего для него не хватает.

    Отвечает честно вместо шести неработающих инструментов: показывает, каких таблиц нет в
    живой схеме и сколько объектов конфигурации в базе вообще есть. Экспорт предполагает,
    что объект был ИЗМЕНЁН в базе и его нужно собрать обратно в XML; в текущей схеме
    изменений объектов нет, поэтому выгружать нечего.
    """
    try:
        with transaction() as cur:
            present = {table: _table_exists(cur, table) for table in REQUIRED_TABLES}
            cur.execute("SELECT count(*) FROM configurations")
            configs = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM " + current_view("external_report"))
            reports = cur.fetchone()[0]
    except Exception as exc:
        return f"❌ Готовность экспорта не проверена: {exc}"

    missing = [table for table, ok in present.items() if not ok]
    lines = ["❌ Сценарий «экспорт изменений конфигурации» не реализован.",
             f"Таблица конфигураций (configurations): строк {configs}; внешних объектов "
             f"в базе: {reports}.",
             "Отсутствующие таблицы: " + (", ".join(missing) if missing
                                          else "все есть, но сценарий всё равно не реализован"),
             "Причина не в обёртке: объекты выгрузки в текущей схеме только читаются из БД, "
             "изменять в базе нечего, поэтому и выгружать в XML нечего.",
             "Что нужно для экспорта (узел V18): таблица объектов конфигурации с их XML, "
             "отслеживание изменённых объектов, сборка XML по схеме и сравнение с выгрузкой.",
             "Загрузка каталогов — 1c-configurations-core (load_1c_catalog_tool); "
             "обогащение сохранённого содержимого — 1c-configurations-enrichment."]
    return "\n".join(lines)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
