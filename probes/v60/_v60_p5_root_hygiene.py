#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V60, шаг П5: правило состава корня называет класс файлов значений.

Зачем. Проверка `tools/check_root_hygiene.py` ведёт перечень файлов корня и обязана назвать новый
класс, иначе прогон говорит «место не названо: класс файла неизвестен» — то есть проверка не различает
файл значений и случайно брошенный в корень мусор. Карточка `rules:checks:root-hygiene` описывает тот
же перечень текстом, поэтому правка делается парой: константа `ROOT_VALUE_FILES` в проверке и текст
карточки. Менять только код — значит оставить правило, которое утверждает меньшее, чем сторож.

Правка точечная: каждый фрагмент ищется ровно один раз, и если ровно одного совпадения нет, строка
не меняется вовсе. Замена текста карточки целиком по шаблону стёрла бы то, чего скрипт не касался,
а историческая часть карточки (разбор 05.11.2026 с числами) правке не подлежит (пункт 4 самой
карточки).

Слой `rules` ведётся файловым исходником `docs/rules/rules.md`, а проверка
`tools/check_rules_layer.py` сверяет текст строки БД с исходником: правка только строки БД даёт
провал «текст БД совпадает с исходником». Поэтому правку вносят в файл и переносят мигратором
`tools/migrate_rules_to_layer.py --file docs/rules/rules.md --apply`; тот же список замен доступен
для файла режимом `--file`, чтобы тексты не разъезжались.

Запуск:
    python probes/v60/_v60_p5_root_hygiene.py                     # разбор (БД)
    python probes/v60/_v60_p5_root_hygiene.py --write             # применить к строке БД
    python probes/v60/_v60_p5_root_hygiene.py --file --write      # применить к docs/rules/rules.md
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database import get_cursor  # noqa: E402
from mcp_tools_api import update_snippet  # noqa: E402

ADDRESS = "rules:checks:root-hygiene"
# Файловый исходник слоя `rules`: его текст является эталоном для строки БД (проверка слоя сверяет
# их), поэтому правку вносят в файл, а в БД переносит мигратор.
SOURCE_FILE = ROOT / "docs" / "rules" / "rules.md"

REPLACEMENTS = [
    ("""   `ALLOWED_ROOT_FILES` проверки `tools/check_root_hygiene.py`; новый файл в корне возможен
   только внесённым в этот список сознательно.""",
     """   `ALLOWED_ROOT_FILES` проверки `tools/check_root_hygiene.py`; новый файл в корне возможен
   только внесённым в этот список сознательно. Файлы значений — отдельный класс того же списка
   (`ROOT_VALUE_FILES` той же проверки): `.env` со значениями подключения к PostgreSQL (в репозиторий
   не входит, читает его `src/db_env.py`) и отслеживаемый шаблон `.env.example`. Проверка называет их
   числом и назначением: молча пропущенный файл значений неотличим от пропущенного хлама, а именно
   это и проверялось в разборе."""),

    ("""   и экономия возможна только внешней упаковкой (замер: дамп одной таблицы 324.7 МБ → 30.3 МБ).

===FORBID""",
     """   и экономия возможна только внешней упаковкой (замер: дамп одной таблицы 324.7 МБ → 30.3 МБ).

7. Файл значений — не точка входа: его читают, а не запускают. Значение держит один файл, а не каждая
   точка подключения (замер узла V60, 06.11.2026: одно и то же значение стояло в 53 отслеживаемых
   файлах и попадало в историю git); код читает его единственной точкой `src/db_env.py`, правило
   обращения к базе — карточка `rules:kb-rules:functional:db-access`.

===FORBID"""),

    ("""- класть в корень замер, дамп прогона, снимок карточки, документ-одиночку или фикстуру чужого узла;""",
     """- класть в корень замер, дамп прогона, снимок карточки, документ-одиночку или фикстуру чужого узла;
- держать в корне файл значений, не внеся его в `ROOT_VALUE_FILES`, или назвать файл значений точкой
  входа;"""),

    ("""класс определяется по использованию файла, а не по имени). Числа разбора и перечень перенесённого —
снимок rules:journal:node:root-files.""",
     """класс определяется по использованию файла, а не по имени). Числа разбора и перечень перенесённого —
снимок rules:journal:node:root-files.

Узел V60 (06.11.2026): перечень пополнился классом файлов значений (`.env`, `.env.example`) —
замер узла и обоснование класса: rules:kb-rules:journal:ref:11."""),
]


def apply_replacements(text, label):
    """Вернуть текст со всеми заменами или None: каждое совпадение обязано быть единственным."""
    for old, _new in REPLACEMENTS:
        hits = text.count(old)
        if hits != 1:
            print(f"❌ {label}: фрагмент встречается {hits} раз (нужно ровно одно совпадение): "
                  f"{old[:60]!r}…")
            return None
    updated = text
    for old, new in REPLACEMENTS:
        updated = updated.replace(old, new, 1)
    return updated


def patch_file(write):
    """Правка файлового исходника слоя. Перенос строк сохраняется: иначе diff на весь файл."""
    raw = SOURCE_FILE.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    updated = apply_replacements(text, "исходник слоя")
    if updated is None:
        return 1
    rel = SOURCE_FILE.relative_to(ROOT)
    print(f"• {rel} — {len(text)} → {len(updated)} симв., правок: {len(REPLACEMENTS)}, "
          f"перенос строк: {'CRLF' if eol == chr(13) + chr(10) else 'LF'}")
    if not write:
        print("  разбор: применится с --write")
        return 0
    SOURCE_FILE.write_text(updated.replace("\n", eol), encoding="utf-8", newline="")
    print("  файл записан; перенос в строку БД: "
          "python tools/migrate_rules_to_layer.py --file docs/rules/rules.md --apply")
    return 0


def main():
    args = sys.argv[1:]
    write = "--write" in args
    if "--file" in args:
        return patch_file(write)

    with get_cursor() as cur:
        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question = %s", (ADDRESS,))
        row = cur.fetchone()
    if not row:
        print(f"❌ карточки `{ADDRESS}` нет")
        return 1
    answer, snippet_id = row["answer"], row["id"]
    updated = apply_replacements(answer, ADDRESS)
    if updated is None:
        return 1
    print(f"• {ADDRESS} — id={snippet_id}, {len(answer)} → {len(updated)} симв., "
          f"правок: {len(REPLACEMENTS)}")
    if not write:
        print("  разбор: применится с --write")
        return 0
    result = update_snippet(snippet_id, new_answer=updated,
                            reason="узел V60 П5 (06.11.2026): правило состава корня называет класс "
                                   "файлов значений ROOT_VALUE_FILES (.env, .env.example) — иначе "
                                   "сторож не различает файл значений и брошенный в корень мусор")
    print("  ", str(result)[:160])
    return 0


if __name__ == "__main__":
    sys.exit(main())
