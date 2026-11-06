#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V60, шаг П4: карточка `rules:always:db-access` и сжатие always-набора.

Зачем шаг нужен. Оператор перевёл правила обращения к базе из `.clinerules/1C_Rule.md` в
дерево правил: ассистенту нужны логин и пароль для прямого `psql`, а файл `.env` для этого не
подходит - `psql.exe` его не читает. Значит значение обязано быть в карточке, которую читают
всегда.

Почему always-набор пришлось сжимать раньше. Политика читателя (`ALWAYS_ADDRESSES`) до узла
занимала 17 131 символ из `ALWAYS_BUDGET_CHARS` = 18 000: `rules:` 5 600 и `rules:kb-rules:`
11 531. Новая карточка добавляет ~1.1k, и порог был бы превышен. Снято то, что воспроизводимо
другим инструментом и потому не является правилом:

  * абзац с именами снятых инструментов (`get_search_rules_tool`, `get_load_rules_tool`,
    `get_rules_report_tool`) - справка о том, чего нет; состав инструментов называет регистр
    `@mcp.tool()`, а живость имён сторожит `_general_block_probe.py`;
  * пространные описания категорий в перечне. Сами коды остаются: `REQUIRED_CATEGORIES` прогона
    их требует, а счётчики и полный перечень печатает `list_categories_tool()`.

Точка правки - генератор `tools/_make_rule_cards.py`: `_general_block_probe.py` требует точного
совпадения раздела `===MCP` с `mcp_section()`, поэтому править только строку БД значило бы
получить расхождение генератора и карточки. Здесь раздел перегенерируется из генератора.

Что делает шаг:
  1. перегенерирует `===MCP` карточки `rules:kb-rules:` из правленного генератора;
  2. создаёт карточку `rules:always:db-access` (теги как у прочих always-карточек);
  3. вносит её в индекс always-ветки `rules:always:index`;
  4. печатает итог always-набора против порога - цифрой, а не утверждением.

Правки карточек идут через `update_snippet`/`add_snippet` из `src/mcp_tools_api.py`: прежний
текст уходит в `snippet_audit_log` (узел P6), история правки остаётся в базе.

Запуск:
    python probes/v60/_v60_p4_rules.py            # разбор
    python probes/v60/_v60_p4_rules.py --write    # применить
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _make_rule_cards as MC  # noqa: E402
import rules_layer as RL  # noqa: E402
import rules_read as RR  # noqa: E402
from database import get_cursor  # noqa: E402
from mcp_tools_api import add_snippet, update_snippet  # noqa: E402

LAYER = MC.LAYER_ADDRESS              # `rules:kb-rules:`
DB_ACCESS = "rules:always:db-access"  # новая always-карточка
ALWAYS_INDEX = "rules:always:index"
DB_ACCESS_TAGS = "1c-rules-root,rules,rules-layer,always"
# Алиасы задаются списком, а не строкой: `add_snippet` перебирает переданный `aliases`
# итератором, и строка дала бы алиасы по одному символу (замер узла V60: 55 алиасов, из них
# `-`, `,`, `:`, `№`). Первые два - алиасы предков: `by_alias` в `src/rules_report.py` отдаёт
# поддерево только тем строкам, что объявили алиас уровня, поэтому без них карточка always-ветки
# не читается дампом дерева (правило RESTRUCTURE-KB).
DB_ACCESS_ALIASES = [
    "rules:", "rules:always:", "rules:always:db-access",
    "psql", "запуск psql", "psql.exe", "подключение к базе", "реквизиты подключения",
    "пароль postgres", "PGPASSWORD", "роли PostgreSQL", "local_doc", "ckb_1c_configurations",
]

CARD_DB_ACCESS = """===WHEN
Прямая работа с PostgreSQL: запуск `psql.exe`, запрос к базе правил и знаний, подключение из кода.
Карточку поднимают до первой команды `psql`, а не после отказа подключения.

===TERMINAL
    $env:PGPASSWORD='Sta090860'; C:\\Postgres\\bin\\psql.exe -U postgres -h localhost -tA -P footer=off
`-tA` - тихий режим, `footer=off` - постраничный вывод выключен. Роли `Buh` (имя Windows-пользователя,
которое `psql.exe` подставляет по умолчанию) на сервере нет: без `-U postgres` подключение падает с
`FATAL: password authentication failed for user "Buh"`, поэтому `-U postgres` обязателен в каждой
команде. Базы: `local_doc` - правила и знания, `ckb_1c_configurations` - замеры узлов.

===ENV
Код и MCP-серверы читают `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD` через `src/db_env.py`; он же читает
файл `.env` в корне проекта (вне репозитория, шаблон - `.env.example`). Литерала пароля в
отслеживаемых файлах нет: до узла V60 он был в 53 файлах и попадал в историю git."""

REASON_REGEN = ("узел V60 (06.11.2026): раздел `===MCP` перегенерирован из правленного генератора - "
                "снята справка об отсутствующих инструментах и пространные описания категорий; "
                "коды категорий остаются, их требует `_general_block_probe.py`")


def card_state(cur, address):
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question = %s", (address,))
    row = cur.fetchone()
    return (row["id"], row["answer"]) if row else (None, None)


def always_measure(cur, addresses):
    """Собрать объём always-набора так же, как его мерит читатель правил."""
    total, parts = 0, []
    for address in addresses:
        card_id, answer = card_state(cur, address)
        size = len(answer) if answer else 0
        total += size
        parts.append(f"{address} {size}" if card_id else f"{address} НЕТ В БАЗЕ")
    return total, parts


def main():
    write = "--write" in sys.argv[1:]
    print("=== узел V60 П4: always-карточка подключения и сжатие always-набора ===",
          "запись" if write else "только разбор")

    with get_cursor() as cur:
        layer_id, answer = card_state(cur, LAYER)
        if not layer_id:
            print(f"карточка `{LAYER}` не найдена")
            return 1
        # Пересборку ведёт штатная функция генератора: `===MCP`, `===LINKS` и `===INDEX`
        # читаются из дерева, а не из текста скрипта, - перечень, заведённый руками, отстаёт
        # от дерева на одну карточку и врёт про покрытие слоя. `force_summary=True` здесь нужен
        # потому, что узел V60 сжал абзац о составе слоя в тексте `LAYER_SUMMARY`: без этого
        # раздела правка генератора в карточку не попала бы.
        rebuilt = MC.rebuild_parent(cur, dry=True, force_summary=True)[3]
        print(f"\n1. `{LAYER}` (id {layer_id}): `===MCP` "
              f"{len(MC.section_text(answer, 'MCP'))} -> "
              f"{len(MC.section_text(rebuilt, 'MCP'))} симв.; "
              f"карточка {len(answer)} -> {len(rebuilt)}")
        if rebuilt == answer:
            print("   изменений нет: карточка уже соответствует генератору")
        elif write:
            result = update_snippet(layer_id, new_answer=rebuilt, reason=REASON_REGEN)
            print(f"   записано update_snippet, прежний текст - в snippet_audit_log: "
                  f"{str(result)[:120]}")
        else:
            print("   будет записано")

    with get_cursor() as cur:
        existing_id, _ = card_state(cur, DB_ACCESS)
    if existing_id:
        print(f"\n2. `{DB_ACCESS}`: существует (id {existing_id}) - повторный пропуск")
    else:
        print(f"\n2. `{DB_ACCESS}`: карточка новая ({len(CARD_DB_ACCESS)} симв., "
              f"теги `{DB_ACCESS_TAGS}`)")
        if write:
            created = add_snippet(DB_ACCESS, CARD_DB_ACCESS, tags=DB_ACCESS_TAGS, confidence=1,
                                  aliases=DB_ACCESS_ALIASES)
            print(f"   создана: {str(created)[:150]}")

    index_row = (f"| `{DB_ACCESS}` | прямое подключение к PostgreSQL: запуск `psql.exe`, роли, "
                 f"имена баз, файл `.env` для кода | check_db_credentials.py |")
    with get_cursor() as cur:
        index_id, index_answer = card_state(cur, ALWAYS_INDEX)
        if not index_id:
            print(f"\n3. `{ALWAYS_INDEX}` не найдена - индекс не изменён")
        elif DB_ACCESS in (index_answer or ""):
            print(f"\n3. `{ALWAYS_INDEX}`: строка индекса уже внесена")
        else:
            print(f"\n3. `{ALWAYS_INDEX}`: строка индекса будет добавлена")
            if write:
                lines = (index_answer or "").split("\n")
                last = max((i for i, line in enumerate(lines)
                            if line.startswith("| `rules:always:")), default=-1)
                if last == -1:
                    print("   таблица индекса не найдена - строка не вставлена")
                else:
                    lines.insert(last + 1, index_row)
                    result = update_snippet(
                        index_id, new_answer="\n".join(lines),
                        reason="узел V60: индекс always-ветки называет карточку подключения - "
                               "записанное и не названное правило перестаёт существовать для "
                               "того, кто читает ветку по указателю")
                    print(f"   записано: {str(result)[:150]}")

    with get_cursor() as cur:
        addresses = list(RR.ALWAYS_ADDRESSES)
        if DB_ACCESS not in addresses:
            addresses.append(DB_ACCESS)
        total, parts = always_measure(cur, addresses)
    print(f"\n4. always-набор политики читателя с новой карточкой: {total} симв. при пороге "
          f"{RL.ALWAYS_BUDGET_CHARS}")
    for part in parts:
        print(f"   {part}")
    print("   итог:", "в пределах порога" if total <= RL.ALWAYS_BUDGET_CHARS
          else "ПРЕВЫШЕНИЕ ПОРОГА")
    return 0


if __name__ == "__main__":
    sys.exit(main())
