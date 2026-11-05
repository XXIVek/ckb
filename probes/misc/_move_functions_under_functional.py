"""Перенос функциональных карточек слоя под уровень `functional:` — с правкой ссылок на них.

Почему перенос, а не таблица соответствий: фильтр «что относится к задаче» строится по префиксу
адреса. Функции слоя лежали уровнем 3 рядом с карточками инструментов (`rules:kb-rules:loading` и
`rules:kb-rules:load-doc-tool` различаются одним суффиксом `-tool`), и отличить их приходилось по
признаку, который надо помнить. После переноса адрес сам называет вид: `rules:kb-rules:always:*` —
общее, `rules:kb-rules:functional:*` — функция, `rules:kb-rules:load-doc-tool` — карточка
инструмента. Тот же порядок уже держался для двух карточек (`alias-coverage`, `knowledge-layer`),
и именно он даёт предсказуемый перечень вида в дампе.

Что делает скрипт:
1. переименовывает строку (вопрос и `source_url`: ключ карточки — и то и другое);
2. добавляет алиасы нового адреса; старый адрес остаётся алиасом — строку, ищущую по-старому,
   находят, а не теряют;
3. правит ссылки на адрес в текстах прочих живых карточек. Раздел `===SOURCE===` не правится: там
   назван адрес, из которого текст брали в тот день, — это история, а не живая ссылка (править её
   значит соврать про прошлое).

Скрипт идемпотентен: повторный прогон старых адресов не находит и ничего не меняет.
Запуск: python _move_functions_under_functional.py [--dry-run]
"""
import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
for _p in (ROOT_DIR / "src", ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _make_rule_cards as M  # noqa: E402
import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402
from quarantine import MARK_ARRAY, sql_not_marked  # noqa: E402

# Листья, которые лежали уровнем 3 и переезжают под `functional:`. Теги не снимаются: вид карточки
# с адресом не менялся, теги `rules,kb-rules,functional` остаются теми же.
MOVE = ["write-knowledge", "quarantine", "loading", "state", "rules-work"]
PARENT = M.LAYER_ADDRESS  # rules:kb-rules:
PATTERN = re.compile(
    r"rules:kb-rules:(" + "|".join(re.escape(leaf) for leaf in MOVE) + r")(?![a-z0-9_-])")


def moved_address(leaf):
    return f"{PARENT}functional:{leaf}"


def old_addresses():
    return [f"{PARENT}{leaf}" for leaf in MOVE] + [moved_address(leaf) for leaf in MOVE]


def rename_cards(cur, dry):
    """Строка переименовывается целиком: вопрос и source_url образуют один ключ карточки."""
    moved = []
    for leaf in MOVE:
        old, new = f"{PARENT}{leaf}", moved_address(leaf)
        cur.execute("SELECT id, tags FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                    (old, RL.source_url(old)))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT id FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                        (new, RL.source_url(new)))
            at_new = cur.fetchone()
            note = f" (уже на новом месте id={at_new['id']})" if at_new else " — нет ни там, ни здесь"
            print(f"• {old} — переносить нечего{note}")
            continue
        if dry:
            print(f"  • {old} → {new} (id={row['id']})")
            moved.append(row["id"])
            continue
        cur.execute("UPDATE knowledge_snippets SET question = %s, source_url = %s, updated_at = NOW() "
                    "WHERE id = %s", (new, RL.source_url(new), row["id"]))
        # Алиасы нового адреса. Старый адрес уже лежит в alias_targets и остаётся: по нему строку
        # найдут и после переноса.
        M.ensure_aliases(cur, row["id"], M.rule_aliases(leaf), row["tags"])
        print(f"  • {old} → {new} (id={row['id']}), алиасы нового адреса добавлены")
        moved.append(row["id"])
    return moved


def sub_outside_source(answer, pattern, repl):
    """Замена по всей карточке, кроме разделов SOURCE (там исторический адрес-источник).

    Куски склеиваются обратно вместе с разделами SOURCE — иначе карточка лишилась бы их текста,
    а не только правки.
    """
    blocked = [(start, end) for name, start, end in M.section_spans(answer)
               if name.upper() == "SOURCE"]
    parts = []
    pos = hits = 0
    for start, end in blocked + [(len(answer), len(answer))]:
        part, count = pattern.subn(repl, answer[pos:start])
        hits += count
        parts.append(part)
        parts.append(answer[start:end])
        pos = end
    return "".join(parts), hits


def fix_references(cur, dry):
    """Живые ссылки на старый адрес в текстах прочих карточек дерева."""
    like = [f"%{PARENT}{leaf}%" for leaf in MOVE]
    cur.execute(
        "SELECT id, question, answer FROM knowledge_snippets WHERE source_url LIKE %s "
        "AND NOT (question = ANY(%s))" + sql_not_marked() + " AND ("
        + " OR ".join(["answer LIKE %s"] * len(like)) + ") ORDER BY question",
        (RL.SOURCE_SCHEME + "%", old_addresses(), MARK_ARRAY, *like),
    )
    total = 0
    for row in cur.fetchall():
        rebuilt, hits = sub_outside_source(row["answer"], PATTERN, rf"{PARENT}functional:\1")
        if not hits:
            print(f"• {row['question']} — адрес назван только в SOURCE, ссылок не правим")
            continue
        total += hits
        if dry:
            print(f"  • {row['question']} — ссылок к правке: {hits}")
            continue
        cur.execute("UPDATE knowledge_snippets SET answer = %s, updated_at = NOW() WHERE id = %s",
                    (rebuilt, row["id"]))
        print(f"  • {row['question']} — заменено ссылок: {hits}")
    return total


def main():
    parser = argparse.ArgumentParser(description="Перенос функциональных карточек под `functional:`")
    parser.add_argument("--dry-run", action="store_true", help="только показать, ничего не писать")
    args = parser.parse_args()

    with get_cursor() as cur:
        print(f"=== перенос {len(MOVE)} карточек под {PARENT}functional: "
              f"{'(dry)' if args.dry_run else ''} ===")
        moved = rename_cards(cur, args.dry_run)
        if not args.dry_run:
            cur.connection.commit()
        hits = fix_references(cur, args.dry_run)
    print(f"\nперенесено карточек: {len(moved)} | заменено ссылок: {hits}"
          + ("" if args.dry_run else " | изменения записаны"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

