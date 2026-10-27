#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узлы журнала о прежних именах инструментов (план docs/RULES_CONTEXT_PLAN.md, П2-Ф-8).

Зачем: замер `_journal_code_history.py` 27.10.2026 показал 18 имён `server.py` и 9 имён
`server_configurations_enrichment.py`, которые не читает ни одна запись слоя. Разбор git
(`_p8_probe.py` — в каком коммите имя добавлялось и снималось; `_p8_probe2.py` — что делал
прежний инструмент по его docstring) показал: это не потерянные инструменты, а две прежние модели
knowledge-base и прежняя модель именования enrichment-сервера. Имена внесены в `DELETED_TOOLS`
(снят дефект дублирования: прежний `REMOVED_SERVER_TOOLS` перенесён в тот же список), а чем именно
заменено каждое имя — записывает этот узел: перечень имён отвечает на вопрос «чего нет», узел
отвечает на вопрос «чем это делают теперь».

Что делает:
  1. пишет карточки `journal:node:*` (ключ идемпотентности — `source_url`, теги берутся у прежней
     карточки журнала того же слоя, чтобы новая строка не отличалась от ряда);
  2. дописывает строки в перечни `rules:kb-rules:journal:index` и
     `rules:enrich-rules:journal:index` — узла, которого нет в перечне, не читается: проверка
     достижимости журнал намеренно исключает, а `check_functional_journal_trace` (узел П2-Ф-5)
     требует, чтобы каждый `journal:node:*` назвал живой карточкой или перечнем.

Числа и имена не выдуманы: составы регистра берутся из `git show <коммит>:<файл>` тем же разбором,
что у `tools/check_mcp_tool_wiring.py`; назначения прежних инструментов — из их docstring в
состоянии реестра непосредственно перед снятием.

Запуск:
    python _p8_journal_nodes.py            # что будет сделано
    python _p8_journal_nodes.py --write    # записать
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

# (адрес узла, метка слоя, карточка журнала, дающая теги ряда, исходник строки перечня,
#  что снимает строка перечня, текст узла)
NODES = [
    (
        f"{RL.ROOT_MARKER}:kb-rules:{RL.STATE_JOURNAL}:node:fragments-2026-09",
        "kb-rules",
        f"{RL.ROOT_MARKER}:kb-rules:{RL.STATE_JOURNAL}:hdr:10",
        "git:342a213f (02.10.2026)",
        "модель «фрагментов»: 9 имён, сняты при переходе к группам и сниппетам",
        """Модель «фрагментов» knowledge-base: реестр `server.py` держал девять инструментов поиска
и загрузки по фрагментам документации (добавлены 30.09.2026 коммитами `0249cabd`, `06a662bf`, сняты
02.10.2026 коммитом `342a213f`; состав регистра 14 → 15 инструментов).

**Имена и что они делали** (назначения взяты из docstring состояния реестра перед снятием):
`search_fragments_tool` — поиск фрагментов (методы, типы, свойства) по тексту;
`get_fragment_by_name_tool` — найти фрагмент по имени; `get_import_log_tool` — журнал выполненных
импортов; `import_html_files_tool`, `import_markdown_files_tool`, `load_from_folder_tool`,
`load_from_url_tool` — импорт файлов из папки и загрузка по URL; `detect_category_tool` — определить
категорию по содержимому; `fix_snippet_tool` — исправить существующую запись.

**Чем заменено** (добавлены тем же коммитом `342a213f`, если не сказано иное): поиск фрагментов и
поиск по имени — `search_docs_tool`, комбинированный поиск по группам и сниппетам; загрузка папки и
одиночных файлов — `load_doc_tool`, `load_single_html_tool`, `load_bsl_tool`; категория перестала
определяться инструментом — её задаёт параметр `category` инструментов загрузки; `get_import_log_tool`
заменён не был: журнала импортов в теперешней модели нет. `fix_snippet_tool` был снят этим коммитом,
возвращён им же и снят снова 07.10.2026 (узел `rules:kb-rules:journal:node:elements-2026-10`);
инструмент исправления строки появился только 20.10.2026 — `update_snippet_tool` (узел P6), и
восемнадцать дней между снятием и появлением преемника правка знания шла второй строкой вместо первой.

**Остаток узла:** имена держит в `DELETED_TOOLS` `tools/check_mcp_tool_wiring.py` — живая карточка
назвать их не вправе (сторожит `tools/check_search_rules_sync.py`), а снять имя из списка — значит
вернуть ему статус неизвестного, и `_journal_code_history.py` снова посчитает его непокрытым.""",
    ),
    (
        f"{RL.ROOT_MARKER}:kb-rules:{RL.STATE_JOURNAL}:node:elements-2026-10",
        "kb-rules",
        f"{RL.ROOT_MARKER}:kb-rules:{RL.STATE_JOURNAL}:hdr:10",
        "git:e043843a (07.10.2026)",
        "модель «элементов и групп»: 9 имён, сняты при переходе к `search_docs_tool`",
        """Модель «элементов и групп» knowledge-base: реестр `server.py` держал девять инструментов
раздельной работы с элементами справки и группами (добавлены 02.10.2026 коммитом `342a213f`, сняты
07.10.2026 коммитом `e043843a`; состав регистра 15 → 11 инструментов).

**Имена и что они делали** (назначения — из docstring состояния реестра перед снятием):
`create_element_tool` / `update_element_tool` — создать и обновить элемент справки в группе;
`create_group_tool` / `update_group_tool` — создать и обновить группу, `parent_id` задавал дерево;
`search_elements_tool`, `search_groups_tool`, `search_snippets_tool` — три отдельных поиска (по
элементам, по группам, по сниппетам кода); `get_element_details_tool` — детали элемента со
сниппетами и алиасами; `get_group_hierarchy_tool` — дерево групп.

**Чем заменено** (добавлены тем же коммитом `e043843a`): три поиска сведены в один
`search_docs_tool` — раздельный поиск по элементам, группам и сниппетам давал три разных ответа об
одном знании; детали элемента — `get_doc_tool` (полная группа), содержимое сниппета второй фазой —
`get_snippet_tool` (добавлен 20.10.2026, узел P6); создание и правка элемента — `add_snippet_tool` и
`update_snippet_tool` (тот же узел P6); группы перестали правиться из MCP — их создаёт загрузчик
документа (`load_doc_tool`, `load_single_html_tool`); `get_group_hierarchy_tool` заменён не был:
дерево групп отдельным инструментом не читается.

**Почему это записано, а не забыто:** две снятые модели дают ровно те восемнадцать имён, которые
прогон `_journal_code_history.py` 27.10.2026 назвал непокрытыми. Молчание слоя о них означало, что
следующая правка реестра вправе переоткрыть элементную модель как новый инструмент — против этого и
записан узел, а имена держит `DELETED_TOOLS`.""",
    ),
    (
        f"{RL.ROOT_MARKER}:enrich-rules:{RL.STATE_JOURNAL}:node:naming-2026-10",
        "enrich-rules",
        f"{RL.ROOT_MARKER}:enrich-rules:{RL.STATE_JOURNAL}:ref:11",
        "git:a71e7b0d (14.10.2026)",
        "прежняя модель имён инструментов обогащения: 9 имён и чем заменено каждое",
        """Прежняя модель имён инструментов обогащения: состав `server_configurations_enrichment.py`
от 10.10.2026 (коммит `0515dbe4`, 17 инструментов) называл инструменты в единственном числе и без
общего корня `config_`. Состав снят 14.10.2026 коммитом `a71e7b0d` (узлы V17-V20.1), реестр
17 → 18 инструментов; имена переименованы в теперешний контракт тем же коммитом.

**Пары «прежнее имя → чем заменено»** (назначения прежних инструментов — из их docstring в состоянии
реестра перед снятием; соответствие установлено по назначению, а не по сходству имён):
`add_config_alias_tool` (добавить алиас объекта) → `add_config_aliases_tool` — тот же контракт
`alias_targets`, во множественном числе, потому что алиасы объекту добавляют одной строкой через
запятую; `get_alias_target_tool` (разрешить цель алиаса) → `resolve_config_alias_tool` — точное
разрешение по нормализованной форме; `search_config_by_alias_tool` (поиск целей по алиасу) →
`search_config_aliases_tool` — начало и середина термина; `get_cross_references_tool` (связи элемента
документации) → `get_config_cross_references_tool`; `get_snippets_for_object_tool` (сниппеты объекта
через зависимости) → `get_config_snippets_for_object_tool`; `get_config_snippet_stats_tool`
(статистика сниппетов конфигурации) → `config_enrichment_stats_tool` — сводка обогащения плюс
карточка свойств объекта; `add_snippet_dependency_tool` (добавить зависимость сниппета) →
`add_config_snippet_tool(dependencies=…)` — зависимость задают при создании сниппета, отдельная
строка зависимости без сниппета оставалась сиротой; `update_dependent_snippets_tool` (перепривязка
зависимостей при переименовании объекта) и `generate_aliases_for_object_tool` (генерация алиасов
объекта) → `generate_config_enrichment_tool` — пересборка алиасов и сниппетов объекта одной
транзакцией из сохранённого содержимого.

**Остаток узла:** имена держит `DELETED_TOOLS` `tools/check_mcp_tool_wiring.py`. До узла П2-Ф-8
(27.10.2026) восемь из них числились снятым локальным списком `REMOVED_SERVER_TOOLS` внутри
`tools/check_search_rules_sync.py`, а девятое — `get_cross_references_tool` — не числилось ни в одном
списке. Два перечня одних и тех же имён и есть причина, по которой прогон П1 считал имена
непокрытыми: измеритель читает один список.""",
    ),
]


def tags_of(cur, sample_address):
    """Теги ряда — у существующей карточки журнала того же слоя."""
    cur.execute("SELECT tags FROM knowledge_snippets WHERE question=%s", (sample_address,))
    row = cur.fetchone()
    if not row:
        raise SystemExit(f"теги ряда не взяты: карточка {sample_address} не найдена")
    return row["tags"]


def append_index_rows(cur, marker, rows):
    """Строки перечня журнала — та же операция, что у `_add_core_journal_nodes.py`."""
    index_address = RL.journal_index_address(marker)
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (index_address,))
    card = cur.fetchone()
    if not card:
        return "перечень журнала не найден — строки не добавлены"
    text = card["answer"] or ""
    lines = text.splitlines()
    last = max((i for i, line in enumerate(lines) if line.lstrip().startswith("| `")), default=None)
    if last is None:
        return "в перечне нет таблицы — строки не добавлены"
    added = []
    for row in rows:
        address, _marker, _sample, source, section, _body = row
        if address in text:
            continue
        lines.insert(last + 1 + len(added), f"| `{address}` | {source} | {section} |")
        added.append(address)
    if not added:
        return "перечень уже содержит все строки"
    cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                ("\n".join(lines) + "\n", card["id"]))
    return f"строк добавлено: {len(added)}"


def main(argv=None):
    write = "--write" in (argv or sys.argv[1:])
    with get_cursor() as cur:
        by_marker = {}
        for node in NODES:
            by_marker.setdefault(node[1], []).append(node)
            address, _marker, sample, _source, _section, body = node
            key = f"{RL.SOURCE_SCHEME}{address}"
            cur.execute("SELECT id FROM knowledge_snippets WHERE source_url=%s", (key,))
            known = cur.fetchone()
            print(f"{'обновлено' if known else 'создано  '}  {address}  {len(body)} симв.")
            if not write:
                continue
            tags = tags_of(cur, sample)
            # Уникального ограничения на `source_url` в схеме нет (замер 27.10.2026), поэтому
            # идемпотентность строится явным поиском по ключу — тот же приём, что у
            # `_add_core_journal_nodes.py`.
            if known:
                cur.execute("UPDATE knowledge_snippets SET answer=%s, tags=%s WHERE id=%s",
                            (body, tags, known["id"]))
            else:
                cur.execute(
                    "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url,"
                    " tags, confidence, is_verified) VALUES (NULL, %s, %s, %s, %s, 1.0, TRUE)",
                    (address, body, key, tags))
        for marker, rows in by_marker.items():
            print(f"перечень {marker}:", append_index_rows(cur, marker, rows) if write
                  else "не тронут (нет --write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
