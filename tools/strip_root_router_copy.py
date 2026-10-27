"""Сторож корневого узла правил: в карточке `rules:` не должно быть текста маршрутизатора.

Зачем. Корневая карточка `rules:` входит в всегда загружаемый набор (`ALWAYS_ADDRESSES` в
tools/rules_read.py), поэтому её содержимое платит за себя в каждом окне контекста. Скрипт
`_move_mcp_rules.py` перенёс в карточку текст `.clinerules/1C_Rule.md` разделом `===MCP`
(19 612 симв. — 80 % карточки). Маршрутизатор с тех пор переписывали, карточку — нет: замер
26.10.2026 дал совпадение 1.3 % строк с живой версией, а в разделе остался прежний двухшаговый
путь чтения правил (`search_docs_tool` -> `get_snippet_tool`), который отменён карточкой
`rules:always:reading` и противоречит разделу `===SUMMARY` той же карточки. Копия always-файла
в always-карточке — это дубль, который никто не синхронизирует; расхождение неизбежно.

Что делает. По умолчанию только проверяет два сигнала: размер карточки (она в каждом окне, поэтому
её размер — бюджет сам по себе, `MAX_ROOT_CARD_CHARS`) и совпадение нормализованных строк карточки
с `.clinerules/1C_Rule.md` (строка считается совпавшей целиком или склейкой с соседней — перенос
текста в карточке меняет перенос, но не содержание). Ненулевой код выхода — если превышен любой
сигнал. Совпадение одно ничего не решает: устаревшая копия с живым файлом уже не совпадает
(замер 26.10.2026: 9 строк из 283 при объёме копии 19 612 симв.), поэтому первым идёт размер.

С `--apply` сначала заменяет абзац-ссылку на снимаемый раздел текстом-указателем, затем снимает
раздел `===MCP` (от заголовка до следующего заголовка `===`). Правка идёт строкой БД с записью
прежнего содержимого в `snippet_audit_log` — тот же контракт, что у `update_snippet_tool`
(узел P6), поэтому история правки карточки остаётся в базе, а не в файле.

Запуск:
    python tools/strip_root_router_copy.py            # проверка (0 — копии нет, 1 — копия есть)
    python tools/strip_root_router_copy.py --apply    # снять копию (повторный вызов — 0)
"""
import argparse
import re
import sys
from pathlib import Path

try:  # кириллица и эмодзи вывода не влазят в cp1251 — приём тот же, что в tools/check_rules_layer.py.
    # Прежняя запись `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, ...)` ломала импорт из
    # validate_project.py: прежняя обёртка терялась из ссылок, сборщик мусора закрывал буфер, и
    # первый print сторожа падал с «I/O operation on closed file» (замер 27.10.2026).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # сбой настройки потока не имеет права менять итог проверки
    pass
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from database import get_cursor  # noqa: E402

ROOT_ADDRESS = "rules:"
ROUTER = PROJECT_ROOT / ".clinerules" / "1C_Rule.md"
# Карточка корня загружается в каждое окно: её размер — бюджет сам по себе. 24 514 симв. карточки
# 26.10.2026 — это 80 % всегда загружаемого набора правил; после снятия копии остаётся ~6.1k,
# порог 8 000 даёт запас на карту слоёв, но не на ещё один раздел-копию.
MAX_ROOT_CARD_CHARS = 8000
# Совпадение со свежим текстом маршрутизатора — второй сигнал: устаревшая копия с живым файлом не
# совпадёт вовсе (замер: 9 строк из 283), поэтому на одном этом сигнале проверка не стоит.
# Строка-указатель на файл остаётся в карточке намеренно; порог отсекает именно копию текста.
MAX_DUP_LINES = 40
SECTION_RE = re.compile(r"^===([A-Za-z_]+)\s*$")
# Абзац конца ===SUMMARY: он ссылался на раздел ===MCP и кончался перед его заголовком.
OLD_POINTER_RE = re.compile(r"Раздел `===MCP` ниже.*?(?=^===MCP)", re.S | re.M)

NEW_POINTER = """Общие записи четырёх MCP-серверов (как пользоваться MCP, критические правила запуска команд,
общие правила правки кода серверов) ведёт `.clinerules/1C_Rule.md` — он попадает в контекст
всегда, и копии его текста в карточке не ведётся. Копия здесь всё же лежала разделом `===MCP`
(19 612 симв., 80 % карточки) и разошлась с файлом: 1.3 % совпавших строк на 26.10.2026, причём
в ней оставался прежний двухшаговый путь чтения правил (`search_docs_tool` -> `get_snippet_tool`),
отменённый карточкой `rules:always:reading` и противоречащий разделу `===SUMMARY` этой же
карточки. Прежний текст остаётся снимком в `Arhiv_Rules/1C_Rule.md` и историей файла в git
(состояние на `c2872bb1`). Карту слоёв несёт раздел `===LINKS` этой карточки, живую карту
печатает `tools/rules_read.py --layers`; прежняя таблица «индекс | категория | исходник» не
переносится: категория нужна была отменённому двухшаговому поиску адресом. Что копия текста
маршрутизатора не вернётся, сторожит `tools/strip_root_router_copy.py`: без `--apply` он
проверяет два сигнала — размер этой карточки (бюджет восемь тысяч символов) и число совпавших
строк с файлом — и возвращает ненулевой код выхода при превышении любого из них.

"""

# Абзац-указатель, который инструмент пишет сам (режим --pointer): текст указателя живёт здесь,
# а не переписывается вручную, иначе описание сторожа в карточке отстаёт от самого сторожа.
POINTER_RE = re.compile(r"Общие записи четырёх MCP-серверов.*?(?=^===LINKS)", re.S | re.M)


def norm_lines(text):
    """Нормализованные строки содержимого: без пустых и без ведущих/концевых пробелов."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def duplicated_lines(card, router):
    """(сколько строк карточки есть в маршрутизаторе, всего строк карточки)."""
    rl = norm_lines(router)
    r_lines = set(rl)
    r_pairs = {rl[i] + " " + rl[i + 1] for i in range(len(rl) - 1)}
    cl = norm_lines(card)
    hits = 0
    for i, line in enumerate(cl):
        nxt = cl[i + 1] if i + 1 < len(cl) else ""
        if line in r_lines or (line + " " + nxt) in r_pairs:
            hits += 1
    return hits, len(cl)


def cut_mcp_section(card):
    """Снять раздел `===MCP`: от его заголовка до следующего заголовка `===` или до конца."""
    lines = card.splitlines(keepends=True)
    start = end = None
    for i, line in enumerate(lines):
        match = SECTION_RE.match(line.strip())
        if not match:
            continue
        if match.group(1).upper() == "MCP" and start is None:
            start = i
        elif start is not None:
            end = i
            break
    if start is None:
        return card, 0
    stop = end if end is not None else len(lines)
    return "".join(lines[:start] + lines[stop:]), len("".join(lines[start:stop]))


def write_card(cur, card_id, old_card, new_card, reason):
    """Записать новое содержимое карточки, оставив прежнее в истории (тот же контракт, что у
    `update_snippet_tool`: action='fix', прежний текст уходит в `snippet_audit_log`)."""
    cur.execute("UPDATE knowledge_snippets SET answer = %s, updated_at = NOW() WHERE id = %s",
                (new_card, card_id))
    cur.execute("INSERT INTO snippet_audit_log (snippet_id, action, old_question, new_question, "
                "old_answer, new_answer, reason) VALUES (%s, 'fix', %s, %s, %s, %s, %s)",
                (card_id, ROOT_ADDRESS, ROOT_ADDRESS, old_card, new_card, reason))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true",
                        help="заменить абзац-ссылку указателем и снять раздел ===MCP")
    parser.add_argument("--pointer", action="store_true",
                        help="переписать только абзац-указатель текущим текстом инструмента")
    args = parser.parse_args(argv)

    with get_cursor() as cur:
        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question = %s",
                    (ROOT_ADDRESS,))
        row = cur.fetchone()
    if not row:
        print(f"❌ карточки `{ROOT_ADDRESS}` в базе нет — корневой узел не найден")
        return 2
    card_id, card = row["id"], row["answer"] or ""
    router = ROUTER.read_text(encoding="utf-8") if ROUTER.exists() else ""

    if args.pointer:
        new_card, n = POINTER_RE.subn(NEW_POINTER, card, count=1)
        if not n:
            print("❌ абзац-указатель в карточке не найден — режим его не создаёт, "
                  "сначала нужен вызов с --apply")
            return 1
        with get_cursor() as cur:
            write_card(cur, card_id, card, new_card,
                       "ROOT-ROUTER-COPY: абзац-указатель переписан текущим текстом инструмента — "
                       "описание сторожа в карточке отстало от его двух сигналов")
        print(f"♻️  абзац-указатель переписан: {len(card)} → {len(new_card)} симв.")
        card = new_card

    hits, total = duplicated_lines(card, router)
    print(f"карточка `{ROOT_ADDRESS}`: id {card_id}, {len(card)} симв., "
          f"содержательных строк {total}")
    print(f"файл {ROUTER.relative_to(PROJECT_ROOT)}: {len(router)} симв.")
    print(f"совпавших строк: {hits} (порог {MAX_DUP_LINES})")
    print(f"размер карточки: {len(card)} (бюджет {MAX_ROOT_CARD_CHARS})")
    why = []
    if len(card) > MAX_ROOT_CARD_CHARS:
        why.append(f"карточка корня превышает бюджет ({len(card)} > {MAX_ROOT_CARD_CHARS}) — "
                   "в ней явно лежит лишний большой раздел")
    if hits > MAX_DUP_LINES:
        why.append(f"в карточке копия текста маршрутизатора ({hits} совпавших строк)")
    if not why:
        print("✅ карточка корня под бюджетом, копии текста маршрутизатора в ней нет")
        return 0
    if not args.apply:
        print("❌ " + "; ".join(why) + " — нужен вызов с --apply")
        return 1

    new_card, n_sub = OLD_POINTER_RE.subn(NEW_POINTER, card, count=1)
    if not n_sub:
        print("❌ абзац-ссылка на `===MCP` не найден — правки нет: оставлять карточку без "
              "объяснения, где теперь общие записи, нельзя")
        return 1
    new_card, removed = cut_mcp_section(new_card)
    with get_cursor() as cur:
        write_card(cur, card_id, card, new_card,
                   "ROOT-ROUTER-COPY: снят раздел ===MCP как копия всегда загружаемого "
                   ".clinerules/1C_Rule.md, разошедшаяся с файлом (1.3 % строк) и "
                   "противоречащая rules:always:reading; прежний текст — Arhiv_Rules/1C_Rule.md "
                   "и история git (c2872bb1)")
    print(f"\n♻️  карточка `{ROOT_ADDRESS}`: {len(card)} → {len(new_card)} симв., "
          f"снято разделом {removed} симв.")
    hits2, _ = duplicated_lines(new_card, router)
    ok = len(new_card) <= MAX_ROOT_CARD_CHARS and hits2 <= MAX_DUP_LINES
    print(f"повторная проверка: {len(new_card)} симв. (бюджет {MAX_ROOT_CARD_CHARS}), "
          f"совпавших строк {hits2} (порог {MAX_DUP_LINES}) — {'✅' if ok else '❌'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
