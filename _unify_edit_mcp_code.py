"""Приведение карточек правки кода MCP к одному адресу — `rules:<слой>:functional:edit-mcp-code`.

Почему один лист, а не три. Карточку правки кода называют текстом другой карточки: «правило правки
кода MCP — <адрес>». Три конфигурационных слоя называли её тремя разными листьями —
`edit-core-code`, `edit-enrich-code`, `edit`, — и адрес нельзя было вывести из метки слоя: его
приходилось помнить или искать перечислением. Тот же приём, который держит карточки инструментов
(лист = имя инструмента, `leaf_of`), даёт и карточку правки кода: лист `edit-mcp-code` один для
четырёх слоёв, адрес выводится из метки. Разнобой листов — не косметика:
`rules:export-rules:functional:edit` совпадает с началом других листьев этого же сегмента, а
`edit-core-code`/`edit-enrich-code` требуют помнить, какой слой как назван.

Про теги. Вид карточки читается из адреса (префикс `functional:`, узел RESTRUCTURE-KB), тег
`functional` — следствие адреса, его порождают `card_tags` и `RL.tags_for` по первому сегменту после
метки. Смена листа вид не меняет, поэтому скрипт теги не трогает и ничего под них не подстраивает:
перечень функций даёт `tools/rules_functions.py`, берущий префикс адреса, а не фильтр по тегам.

Что делает скрипт (по образцу `_move_functions_under_functional.py`):
1. переименовывает строку — вопрос и `source_url` вместе образуют ключ карточки;
2. добавляет алиасы нового адреса в двух написаниях и алиасы уровней адреса; старый адрес остаётся
   алиасом — строку, ищущую по-старому, находят, а не теряют;
3. правит живые ссылки на старый адрес в текстах прочих карточек, включая `===LINKS`/`===INDEX`
   карточки слоя (снять строку из оглавления — значит потерять карточку для того, кто читает слой
   по указателю).

Чего скрипт не правит: раздел `===SOURCE===` (там назван адрес, из которого текст брали в тот день,
— это история, правка соврёт про прошлое) и карточки `journal`/`checks` (снимок прежних текстов и
перечень проверок действующим правилом не являются, и по ним ссылка ведёт именно в прежний адрес).

Скрипт идемпотентен: повторный прогон старых адресов не находит и ничего не меняет.
Запуск: python _unify_edit_mcp_code.py [--dry-run]
"""
import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
for _p in (ROOT_DIR / "src", ROOT_DIR / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402
from _make_layer_rule_cards import (  # noqa: E402
    KIND_FUNCTIONAL, card_aliases, ensure_aliases, layer_prefix, section_spans,
)

# Новый общий лист карточки правки кода — один для четырёх слоёв.
NEW_LEAF = f"{KIND_FUNCTIONAL}:edit-mcp-code"
# (метка слоя, прежний лист). `kb-rules` в списке нет намеренно: её карточка уже лежит по
# стандартному адресу `rules:kb-rules:functional:edit-mcp-code` — именно он и стал образцом.
MOVE = (
    ("core-rules", "edit-core-code"),
    ("enrich-rules", "edit-enrich-code"),
    ("export-rules", "edit"),
)


def old_address(marker, leaf):
    return f"{layer_prefix(marker)}{KIND_FUNCTIONAL}:{leaf}"


def new_address(marker):
    return f"{layer_prefix(marker)}{NEW_LEAF}"


# Каждая пара привязана к своему слою: лист `edit` слоя `export-rules` иначе зацепил бы
# `edit-core-code` другого слоя. Граница `(?![a-z0-9_-])` не даёт заменить начало более длинного
# адреса тем же шаблоном.
PATTERNS = [(old_address(marker, leaf),
             re.compile(re.escape(old_address(marker, leaf)) + r"(?![a-z0-9_-])"),
             new_address(marker))
            for marker, leaf in MOVE]


def rename_cards(cur, dry):
    """Строка переименовывается целиком: вопрос и source_url образуют один ключ карточки."""
    moved = []
    for marker, leaf in MOVE:
        old, new = old_address(marker, leaf), new_address(marker)
        cur.execute("SELECT id, tags FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                    (old, RL.source_url(old)))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT id FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                        (new, RL.source_url(new)))
            at_new = cur.fetchone()
            note = (f" (уже по стандартному адресу id={at_new['id']})" if at_new
                    else " — нет ни там, ни здесь")
            print(f"• {old} — переносить нечего{note}")
            continue
        if dry:
            print(f"  • {old} → {new} (id={row['id']})")
            moved.append(row["id"])
            continue
        cur.execute("UPDATE knowledge_snippets SET question = %s, source_url = %s, updated_at = NOW() "
                    "WHERE id = %s", (new, RL.source_url(new), row["id"]))
        # Алиасы нового адреса. Старый адрес уже лежит в alias_targets и остаётся: по нему строку
        # найдут и после переименования. Русские термины функции добавляются тем же генератором,
        # что создавал карточку, и к адресу не привязаны — второй раз их писать не нужно.
        ensure_aliases(cur, row["id"], card_aliases(marker, NEW_LEAF, ()), row["tags"])
        print(f"  • {old} → {new} (id={row['id']}), алиасы нового адреса добавлены")
        moved.append(row["id"])
    return moved


def sub_outside_source(answer, pattern, replacement):
    """Замена по всей карточке, кроме разделов SOURCE (там исторический адрес-источник).

    Куски склеиваются обратно вместе с разделами SOURCE — иначе карточка лишилась бы их текста,
    а не только правки.
    """
    blocked = [(start, end) for name, start, end in section_spans(answer)
               if name.upper() == "SOURCE"]
    parts = []
    pos = hits = 0
    for start, end in blocked + [(len(answer), len(answer))]:
        part, count = pattern.subn(lambda m: replacement, answer[pos:start])
        hits += count
        parts.append(part)
        parts.append(answer[start:end])
        pos = end
    return "".join(parts), hits


def fix_references(cur, dry):
    """Живые ссылки на старый адрес в текстах прочих карточек дерева."""
    olds = [old for old, _, _ in PATTERNS]
    cur.execute(
        "SELECT id, question, answer FROM knowledge_snippets WHERE source_url LIKE %s "
        "AND NOT (question = ANY(%s))" + sql_not_marked() + " AND ("
        + " OR ".join(["answer LIKE %s"] * len(olds)) + ") ORDER BY question",
        (RL.SOURCE_SCHEME + "%", olds, MARK_ARRAY, *[f"%{old}%" for old in olds]),
    )
    total = 0
    for row in cur.fetchall():
        if RL.node_kind(row["question"]) in (RL.KIND_JOURNAL, RL.KIND_CHECKS):
            print(f"• {row['question']} — снимок журнала или перечень проверок: прежний адрес "
                  "назван исторически, не правим")
            continue
        answer = row["answer"]
        hits = 0
        for _, pattern, new in PATTERNS:
            answer, count = sub_outside_source(answer, pattern, new)
            hits += count
        if not hits:
            print(f"• {row['question']} — адрес назван только в SOURCE, ссылок не правим")
            continue
        total += hits
        if dry:
            print(f"  • {row['question']} — ссылок к правке: {hits}")
            continue
        cur.execute("UPDATE knowledge_snippets SET answer = %s, updated_at = NOW() WHERE id = %s",
                    (answer, row["id"]))
        print(f"  • {row['question']} — заменено ссылок: {hits}")
    return total


def main():
    parser = argparse.ArgumentParser(
        description="Приведение карточек правки кода MCP к адресу "
                    f"`rules:<слой>:{NEW_LEAF}`")
    parser.add_argument("--dry-run", action="store_true", help="только показать, ничего не писать")
    args = parser.parse_args()

    with get_cursor() as cur:
        print(f"=== приведение {len(MOVE)} карточек к листу {NEW_LEAF} "
              f"{'(dry)' if args.dry_run else ''} ===")
        moved = rename_cards(cur, args.dry_run)
        if not args.dry_run:
            cur.connection.commit()
        hits = fix_references(cur, args.dry_run)
    print(f"\nпереименовано карточек: {len(moved)} | заменено ссылок: {hits}"
          + ("" if args.dry_run else " | изменения записаны"))
    print("Тексты карточек этот скрипт не правит — их порождает "
          "`python _make_layer_rule_cards.py --layer <метка>`; порядок: сначала этот скрипт, "
          "затем генератор.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


