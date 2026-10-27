#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узлы журнала core-слоя, которых не хватало (план docs/RULES_CONTEXT_PLAN.md, П2-Ф-4).

Зачем: замер `_journal_code_history.py` и разбор ссылок показали разрыв — в коде core упоминаются
узлы V44 и V45, закрытые 23.10.2026 коммитом `31b0722f`, а карточек `journal:node:v44` /
`journal:node:v45` в базе нет; снятие трёх инструментов чтения правил (реестр 24.10.2026, код снят
`d957ee2e` 26.10.2026) узлом журнала тоже не оформлено. Живые карточки ссылаются на эти решения
прозой («узел V44»), а прозаическое упоминание адресом не является и проверке не разрешается.

Что делает:
  1. пишет три карточки журнала (ключ идемпотентности — `source_url`, теги берутся у прежнего узла
     той же серии, чтобы новая строка не отличалась от ряда, в который входит);
  2. дописывает строки в перечень журнала `rules:core-rules:journal:index` (перечень ведёт
     `tools/regen_journal_index.py`, но он отбирает строки тегом `journal` и пишет в черновик
     `docs/rules/<метка>.md` — для дерева адресов 27.10.2026 это не рабочий путь, поэтому строки
     добавляет этот скрипт, а содержимое снимков не трогает).

Тексты узлов — снимок: дата, файлы, решение, числа прогона, остаток. Ни одно число не выдумано:
всё взято из сообщений коммитов `31b0722f`, `d957ee2e` и из `src/configuration_load_contract.py`.

Запуск:
    python _add_core_journal_nodes.py            # что будет сделано
    python _add_core_journal_nodes.py --write    # записать
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

MARKER = "core-rules"
INDEX_ADDRESS = f"{RL.ROOT_MARKER}:{MARKER}:{RL.STATE_JOURNAL}:{RL.INDEX_LEAF}"

V44 = """Модули предопределённых программ корня не загружались: код `SessionModule`,
`ManagedApplicationModule`, `OrdinaryApplicationModule`, `ExternalConnectionModule` нигде не
хранился (узел V44, группа C; закрыт 23.10.2026 коммитом `31b0722f`).

**Файлы:** `create_1c_configurations_db.sql` и шаг 2 DDL-источника,
`migrate_v44_configuration_root_modules.sql` (новый), `src/configuration_root_modules.py` (новый:
разбор `ConfigDumpInfo.xml` и `Ext/<имя>.bsl`), `src/configuration_root_module_loader.py` (новый:
запись в БД), `src/configuration_loader.py` (снятие строк по uuid заголовка),
`server_configurations_core.py` (`load_configuration_root_modules_tool`).

**Решение:** таблица `configuration_root_modules` — 13 колонок, внешний ключ `configuration_id`,
`UNIQUE (configuration_uuid, module_kind)`; строка подтверждается записью индекса состава, а не
наличием файла. Состояния различают пустой модуль и отсутствующий: `file`, `empty_file`,
`indexed_no_file` (запись индекса без файла), `file_not_in_index` (файл без записи индекса);
вида, которого нет ни файлом, ни записью индекса, в таблице нет — в карточке он назван `absent`
(тот же контракт, что «манифеста нет» / «манифест пуст» у V19 и `===EMPTY` у V39/V42).

**Числа прогона:** `_cmp_ddl.py` rc=0 (570 колонок, 74 индекса, 56 ограничений, 13 витрин),
`tools/check_v42_configuration_header.py` 51/0, `tools/check_v32_zero_configuration.py` 242/0,
`tools/check_mcp_tool_wiring.py` core 5, `validate_project.py` 24/0; живой прогон по четырём
заголовкам (`MinCfg`, `BGU2`, `BP3`, `KomMag`) без отказов.

**Остаток узла (перенесён):** `tools/check_v44_configuration_root_modules.py` не написан;
отдельного раздела о слоях загрузки конфигурации в правилах не было, ссылка в docstring была
битая — закрыто 28.10.2026 карточкой `rules:core-rules:functional:goal-and-stages` (план
`docs/RULES_CONTEXT_PLAN.md`, П2); слой модулей объектов и содержимого зафиксирован файлами
`_handoff_second_layer_2026-10-23.md`, `_handoff_object_modules_2026-10-24.md` — по нему только
зонды `_v46*`, `_v47*`, схема и загрузчик не менялись."""

V45 = """Результат загрузки конфигурации не был закрытым контрактом: форматёр карточки держал ключи
`counts`, `rows`, `forms`, `TABLE_MODULES`, которых у загрузчика нет (узел V45, 22.10.2026; закрыт
23.10.2026 коммитом `31b0722f`).

**Файлы:** `src/configuration_load_contract.py` (новый — этапы конвейера и сводка),
`src/config_load_router.py` (`load_catalog` S1–S4), `src/configuration_loader.py`,
`server_configurations_core.py` (итоговая строка карточки, предупреждения,
`format_binary_load_result`).

**Конвейер первого слоя:** S1 разбор каталога → S2 заголовок (свойства V42, перечни имён V43,
индекс состава V33) → S3 модули предопределённых программ корня (V44) → S4 содержимое дочерних
объектов (V38, **заглушка**). Первая ошибка останавливает конвейер. S5 (анализ загруженной
конфигурации по уже сохранённым строкам, построение `config_*` сниппетов и при необходимости
перекрёстных ссылок на документацию) дополнением оператора 23.10.2026 **не согласована**: в
`STAGES` её нет, план зафиксирован разделом 16 `docs/CONFIGURATIONS_ENRICHMENT_PLAN.md`.

**Правила контракта:** C1 незаполненный ключ читается нулём (`0`, `[]`, `{}`, `False`), ключей
«нет» в ответе быть не может; C2 невыполненная стадия имеет статус `not_run`, а не нули — «модулей
нет» и «модули не загружались» суть разные факты; C3 ответ каждой стадии вложен в свой ключ
(`root_modules`, `child_objects`) без переименования, standalone-инструмент отдаёт свой плоский
контракт; C4 исходы `already_exists` / `name_conflict` / `kind_conflict` — не ошибка стадии, а
точка остановки диалога (правило R5); C5 останавливают конвейер только отказы — нет каталога или
`Configuration.xml`, пустой или кривой uuid (R3), ошибка записи в БД, файл модуля не раскодирован
(`undecoded`), запись индекса вне словаря (`index_unmatched`) — состояния конкретной выгрузки
(`absent`, `empty_file`) остаются предупреждениями.

**Числа:** контракт `server_configurations_core.py` 4 → 5: в цепочке стадия вызывается самим
загрузчиком, отдельного инструмента для неё не заводили (прецедент «S3 в цепочке +
standalone-инструмент»). Проверки — те же, что у V44.

**Остаток:** S4 — заглушка, S5 вне `STAGES`, `tools/check_v44_configuration_root_modules.py` не
написан. Состояние стадий и слоёв загрузки читает карточка
`rules:core-rules:functional:goal-and-stages`."""

RULE_TOOLS = """Инструменты чтения правил остались в регистре MCP, хотя правила читают скрипты
(реестр 24.10.2026, узел RULE-LAYER; код снят коммитом `d957ee2e` 26.10.2026).

**Сняты:** `get_load_rules_tool`, `get_search_rules_tool` (контракт `server.py` 17 → 15) и
`get_load_config_rules_tool` (контракт `server_configurations_core.py` 5 → 4). Имена внесены в
`DELETED_TOOLS` файла `tools/check_mcp_tool_wiring.py`: снять имя совсем — значит позволить текстам
правил назвать снятый инструмент живым (это сторожит `tools/check_search_rules_sync.py`).

**Чем заменены:** `tools/rules_read.py` (читать правило адресом: `--always`, `--layers`, `--tree`,
`--marked`), `tools/rules_functions.py` (состав функций сервера и регистр `@mcp.tool()` в шапке
ответа), `src/rules_report.py` (снимок дерева). Основание: цена вызова инструмента превысила цену
проверяемого знания (замер `tools/check_rule_tool_coverage.py --brief` — 1 776 симв. против 6 865
за вызов), а правила живут деревом адресов, а не категорией поиска.

**Следствие для правил слоя:** живые карточки обязаны называть снятые имена снятыми, а число
инструментов брать прогоном регистра, а не памятью. Числа регистров на дату замера: `server.py`
— 15, `server_configurations_core.py` — 4 (после V44/V45 было 5)."""

NODES = [
    (f"{RL.ROOT_MARKER}:{MARKER}:{RL.STATE_JOURNAL}:node:v44", V44,
     "git:31b0722f (23.10.2026)", "V44 — модули предопределённых программ корня"),
    (f"{RL.ROOT_MARKER}:{MARKER}:{RL.STATE_JOURNAL}:node:v45", V45,
     "git:31b0722f (23.10.2026)", "V45 — закрытый контракт загрузки, конвейер S1-S4"),
    (f"{RL.ROOT_MARKER}:{MARKER}:{RL.STATE_JOURNAL}:node:rule-tools", RULE_TOOLS,
     "git:d957ee2e (26.10.2026)", "снятие инструментов чтения правил, контракты 17-15 и 5-4"),
]

def existing_tags(cur):
    """Теги прежнего узла той же серии — новый узел обязан выглядеть как строка ряда."""
    cur.execute("SELECT tags FROM knowledge_snippets WHERE question=%s",
                (f"{RL.ROOT_MARKER}:{MARKER}:{RL.STATE_JOURNAL}:node:v43:add2210",))
    row = cur.fetchone()
    if not row:
        raise SystemExit("нет узла-образца для тегов: ряд журнала не найден")
    return list(row["tags"] or [])


def append_index_rows(cur, rows):
    """Строки перечня журнала: дописать отсутствующие, существующие не трогать."""
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (INDEX_ADDRESS,))
    card = cur.fetchone()
    if not card:
        return "перечень журнала не найден — строки не добавлены"
    text = card["answer"] or ""
    lines = text.splitlines()
    last = max((i for i, line in enumerate(lines) if line.lstrip().startswith("| `")), default=None)
    if last is None:
        return "в перечне нет таблицы — строки не добавлены"
    added = []
    for address, _text, source, section in rows:
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
        tags = existing_tags(cur)
        for address, text, _source, _section in NODES:
            key = f"{RL.SOURCE_SCHEME}{address}"
            cur.execute("SELECT id FROM knowledge_snippets WHERE source_url=%s", (key,))
            known = cur.fetchone()
            print(f"{'обновлено' if known else 'создано  '}  {address}  {len(text)} симв.")
            if not write:
                continue
            # Уникального ограничения на `source_url` в схеме нет (замер 28.10.2026:
            # `ON CONFLICT (source_url)` даёт InvalidColumnReference), поэтому идемпотентность
            # строится явным поиском по ключу — тот же приём, что у `migrate_rules_to_layer.py`
            # (он снимает строку и вставляет заново; здесь строка обновляется, снимков это не
            # касается: тексты карточек журнала правкой не меняются).
            if known:
                cur.execute("UPDATE knowledge_snippets SET answer=%s, tags=%s WHERE id=%s",
                            (text, tags, known["id"]))
            else:
                cur.execute(
                    "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url,"
                    " tags, confidence, is_verified) VALUES (NULL, %s, %s, %s, %s, 1.0, TRUE)",
                    (address, text, key, tags))
        print("перечень:", append_index_rows(cur, NODES) if write else "не тронут (нет --write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


