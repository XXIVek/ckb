#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел EDIT-CODE-TRIGGER (27.10.2026): триггер карточки правки кода MCP в корне дерева.

Что делает и почему.
1. В карточку корня `rules:` добавляется абзац «Триггеры подъёма правила по намерению»:
   намерение править код MCP-сервера поднимает карточку `rules:<слой>:functional:edit-mcp-code`.
   Без указателя из всегда читаемого корня правило есть в слое, но к нему не идут: агент узнаёт о
   нём, только если вспомнит адрес или пойдёт перечислением. Лист `edit-mcp-code` общий для
   четырёх слоёв (узел EDIT-ADDRESS-UNIFY), поэтому адрес выводится из метки слоя.
2. История снятия копии маршрутизатора из корневой карточки переносится в узел журнала
   `rules:journal:node:router-copy-removal`, а в карточке остаётся рабочая часть: где ведутся
   общие записи и чем возврат копии проверяется. Корневая карточка читается всегда, и её размер
   сторожит `tools/strip_root_router_copy.py` (бюджет 8 000 симв.); снимок прежнего текста
   действующим правилом не является (состояние `journal`).
3. Оглавление журнала корня `rules:journal:index` заводится по образцу оглавлений слоёв и
   перегенерируется штатным `tools/regen_journal_index.py`.

Скрипт идемпотентен: повторный прогон находит уже добавленные абзацы и ничего не меняет.
Запуск: python _add_code_edit_trigger.py [--dry-run]
"""
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
for _p in (ROOT_DIR / "src", ROOT_DIR / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from _make_layer_rule_cards import card_tags, ensure_aliases, level_aliases  # noqa: E402

ROOT_ADDRESS = f"{RL.ROOT_MARKER}:"                   # `rules:`
JOURNAL_INDEX = f"{RL.ROOT_MARKER}:journal:index"     # оглавление журнала корня
JOURNAL_NODE = f"{RL.ROOT_MARKER}:journal:node:router-copy-removal"

# Границы переносимого абзаца в тексте корневой карточки (первое и последнее вхождение).
HISTORY_START = "Общие записи четырёх MCP-серверов (как пользоваться MCP"
HISTORY_END = "при превышении любого из них."

# Что остаётся в карточке: рабочая часть плюс указатель на снимок.
HISTORY_REPLACEMENT = """Общие записи четырёх MCP-серверов (как пользоваться MCP, критические правила запуска команд,
общие правила правки кода серверов) ведёт `.clinerules/1C_Rule.md` — он попадает в контекст
всегда, и копии его текста в карточке не ведётся; история снятия копии и цена расхождения — узел
журнала `rules:journal:node:router-copy-removal`, а возврат копии проверяет
`tools/strip_root_router_copy.py` (без `--apply` он смотрит размер этой карточки и число
совпавших строк с файлом)."""

TRIGGER_PARAGRAPH = """Триггеры подъёма правила по намерению. Намерение править код MCP-сервера —
добавить, изменить или снять инструмент, шаг поиска, теги, формат выдачи — поднимает карточку
правки кода этого слоя `rules:<слой>:functional:edit-mcp-code`: лист адреса один для четырёх
слоёв, адрес выводится из метки слоя и не требует помнить, в каком слое как он назван. Править
код, не прочитав её, значит пропустить шаги, которые она предписывает (регистр `@mcp.tool()`,
`EXPECTED_TOOLS`, перезапуск сервера, узел журнала о составе)."""

TRIGGER_MARK = "Триггеры подъёма правила по намерению"

# Абзац вставляется после абзаца, который заканчивается этими словами.
TRIGGER_ANCHOR_END = "лишний текст\nстоит внимания и ничего не добавляет."

# Строка ===INDEX=== корневой карточки, после которой перечисляется оглавление журнала.
INDEX_ANCHOR = "\nrules:export-rules:"

JOURNAL_NODE_TEXT = """===WHEN===
Снимок прежнего состояния корневой карточки `rules:`: раздел `===MCP` с копией текста
`.clinerules/1C_Rule.md` и история его снятия. Карточка журнала — снимок, а не действующее
правило; тексты журнала не правятся.

===SNAPSHOT===
Копия текста маршрутизатора лежала в корневой карточке разделом `===MCP` — 19 612 симв., 80 %
карточки — и разошлась с файлом: 1.3 % совпавших строк на 26.10.2026. В копии оставался прежний
двухшаговый путь чтения правил (`search_docs_tool` → `get_snippet_tool`), отменённый карточкой
`rules:always:reading` и противоречащий разделу `===SUMMARY` той же карточки.

Прежний текст остаётся снимком в `Arhiv_Rules/1C_Rule.md` и историей файла в git (состояние на
`c2872bb1`). Карту слоёв несёт раздел `===LINKS` корневой карточки, живую карту печатает
`tools/rules_read.py --layers`; прежняя таблица «индекс | категория | исходник» не переносилась:
категория нужна была отменённому двухшаговому поиску адресом.

===GUARD===
Что копия текста маршрутизатора не вернётся, сторожит `tools/strip_root_router_copy.py`: без
`--apply` он проверяет два сигнала — размер корневой карточки (бюджет восемь тысяч символов) и
число совпавших строк с файлом — и возвращает ненулевой код выхода при превышении любого из них.

===SOURCE===
Перенос сделан узлом EDIT-CODE-TRIGGER (27.10.2026) при разгрузке всегда читаемого набора
правил; абзац взят из карточки `rules:` до правки (снимок прежнего текста — `snippet_audit_log`,
action=fix).
"""

JOURNAL_INDEX_TEXT = """===WHEN===
Нужен обзор снимка прежних текстов корневого слоя правил — что именно перенесено из карточек
дерева и где читать замер или причину решения. Формат карточек журнала рабочим правилам не
предъявляется, их тексты не правятся.

Карточка-оглавление журнала корневого слоя. Это перечень снимка: по строке берут карточку
адресом (`python tools/rules_read.py <адрес>`).

Перечень порождает `python tools/regen_journal_index.py --layer rules --write` по фактическому
составу БД; править таблицу вручную — значит оставить строку после удаления карточки.
"""


def journal_tags():
    """Теги карточки журнала корня: категории корня, признаки дерева, состояние `journal`."""
    return card_tags(RL.ROOT_MARKER, RL.STATE_JOURNAL)


def journal_aliases(address):
    return list(dict.fromkeys([address] + level_aliases(address) + [f"{RL.ROOT_MARKER}:"]))


def upsert_card(cur, address, answer, aliases_ru=(), dry=False):
    """Карточка корневого слоя: UPDATE по адресу, если строка есть, иначе INSERT."""
    tags = journal_tags()
    aliases = journal_aliases(address) + list(aliases_ru)
    cur.execute("SELECT id, length(answer) AS len FROM knowledge_snippets"
                " WHERE question = %s AND source_url = %s", (address, RL.source_url(address)))
    existing = cur.fetchone()
    if existing:
        print(f"  • {address} — уже есть (id={existing['id']}, {existing['len']} симв.), не трогаем")
        return existing["id"]
    if dry:
        print(f"  • {address} — будет {len(answer)} симв., алиасов {len(aliases)}")
        return None
    cur.execute(
        "INSERT INTO knowledge_snippets (question, answer, tags, confidence, is_verified, source_url)"
        " VALUES (%s, %s, %s, 1.0, false, %s) RETURNING id",
        (address, answer, tags, RL.source_url(address)))
    snippet_id = cur.fetchone()["id"]
    ensure_aliases(cur, snippet_id, aliases, tags)
    print(f"  • {address} — добавлена (id={snippet_id}, {len(answer)} симв., алиасов {len(aliases)})")
    return snippet_id


def patch_root_card(cur, dry=False):
    """Корневая карточка: история → снимок, добавляется абзац триггера, индекс пополняется."""
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                (ROOT_ADDRESS, RL.source_url(ROOT_ADDRESS)))
    row = cur.fetchone()
    if not row:
        print("  • корневая карточка не найдена — правка не сделана")
        return None
    answer = row["answer"] or ""
    before = len(answer)
    notes = []

    if HISTORY_START in answer and HISTORY_END in answer:
        start = answer.index(HISTORY_START)
        end = answer.index(HISTORY_END) + len(HISTORY_END)
        answer = answer[:start] + HISTORY_REPLACEMENT + answer[end:]
        notes.append("история заменена указателем на узел журнала")
    elif JOURNAL_NODE in answer:
        notes.append("история уже перенесена")
    else:
        notes.append("абзац истории не найден — не заменён")

    if TRIGGER_MARK not in answer:
        if TRIGGER_ANCHOR_END in answer:
            at = answer.index(TRIGGER_ANCHOR_END) + len(TRIGGER_ANCHOR_END)
            answer = answer[:at] + "\n\n" + TRIGGER_PARAGRAPH + answer[at:]
            notes.append("абзац триггера добавлен")
        else:
            notes.append("якорь абзаца триггера не найден — абзац НЕ добавлен")
    else:
        notes.append("абзац триггера уже есть")

    if JOURNAL_INDEX not in answer:
        if INDEX_ANCHOR in answer:
            at = answer.index(INDEX_ANCHOR) + len(INDEX_ANCHOR)
            answer = answer[:at] + "\n" + JOURNAL_INDEX + answer[at:]
            notes.append("оглавление журнала добавлено в ===INDEX===")
        else:
            notes.append("строка индекса не найдена — оглавление журнала не перечислено")

    if dry:
        print(f"  • {ROOT_ADDRESS} — {before} → {len(answer)} симв.: {'; '.join(notes)}")
        return row["id"]
    cur.execute("UPDATE knowledge_snippets SET answer = %s, updated_at = NOW() WHERE id = %s",
                (answer, row["id"]))
    print(f"  • {ROOT_ADDRESS} — {before} → {len(answer)} симв.: {'; '.join(notes)}")
    return row["id"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="только показать, что будет сделано")
    args = ap.parse_args(argv)

    with get_cursor() as cur:
        print("-- карточки журнала --")
        upsert_card(cur, JOURNAL_NODE, JOURNAL_NODE_TEXT,
                    ("история корневой карточки", "снимок копии маршрутизатора"), args.dry_run)
        upsert_card(cur, JOURNAL_INDEX, JOURNAL_INDEX_TEXT,
                    ("журнал правил корня", "снимки прежних текстов правил"), args.dry_run)
        print("-- корневая карточка --")
        patch_root_card(cur, args.dry_run)

    if args.dry_run:
        print("\n--dry-run: изменений в БД нет")
    else:
        print("\nготово; оглавление журнала перегенерируют: "
              "python tools/regen_journal_index.py --layer rules --write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())