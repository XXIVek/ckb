#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_fix_root_journal_index.py — оглавление журнала корневого слоя без чужих ссылок.

Что случилось. `tools/regen_journal_index.py --layer rules` собирает перечень по префиксу метки
(`rules:%`), а под этот префикс попадают журнальные карточки всех слоёв (`rules:kb-rules:journal:*`).
Для слоя-потомка это верно, для корня — нет: оглавление журнала корня начинает ссылаться на
карточки чужих слоёв, и `tools/migrate_rules_to_layer.py` правомерно отвечает
«ссылка индекса в никуда» (карточки чужого слоя не входят в состав корневого).

Что делает скрипт. Заменяет блок `## rules:journal:index` в исходнике `docs/rules/rules.md`
коротким текстом без перечня: перечень журнала корня порождается по составу его собственного
поддерева, а не по префиксу `rules:%`. Тот же текст лежит строкой БД (ключ —
`rules-layer://rules:journal:index`), поэтому файл и строка остаются одинаковыми.

Запуск: python _fix_root_journal_index.py [--dry-run]
"""
import argparse
import io
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

FILE = ROOT_DIR / "docs" / "rules" / "rules.md"
ADDRESS = f"{RL.ROOT_MARKER}:journal:index"
HEADING = f"## {ADDRESS}"

BLOCK = """## rules:journal:index

===WHEN===
Нужен обзор снимка прежних текстов корневого слоя правил — что именно перенесено из карточек
дерева и где читать замер или причину решения. Формат карточек журнала рабочим правилам не
предъявляется, их тексты не правятся.

Карточка-оглавление журнала корневого слоя. Это перечень снимка: по строке берут карточку
адресом (`python tools/rules_read.py <адрес>`).

| Адрес | Откуда взят снимок | Что в нём |
|---|---|---|
| `rules:journal:node:router-copy-removal` | корневая карточка `rules:` до правки 27.10.2026 | копия текста `.clinerules/1C_Rule.md` разделом `===MCP` (19 612 симв.), цена расхождения и чем проверяется возврат |

Перечень порождает `python tools/regen_journal_index.py --layer rules --write` по фактическому
составу БД; править таблицу вручную — значит оставить строку после удаления карточки.

"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    text = io.open(FILE, encoding="utf-8").read()
    if HEADING not in text:
        print(f"• блок {HEADING} в файле не найден — файл не менялся")
        return 1
    head = text[:text.index(HEADING)]
    fixed = head + BLOCK
    if args.dry_run:
        print(f"• {FILE}: {len(text)} → {len(fixed)} симв. (снято {len(text) - len(fixed)})")
    else:
        io.open(FILE, "w", encoding="utf-8", newline="\n").write(fixed)
        print(f"• {FILE}: {len(text)} → {len(fixed)} симв.")

    with get_cursor() as cur:
        cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question = %s AND source_url = %s",
                    (ADDRESS, RL.source_url(ADDRESS)))
        row = cur.fetchone()
        body = BLOCK.split("\n", 1)[1].strip() + "\n"
        if not row:
            print("• строки БД нет — карточка журнала корня не записана")
            return 1
        if row["answer"] == body:
            print(f"• строка id={row['id']} уже совпадает с блоком ({len(body)} симв.)")
        elif args.dry_run:
            print(f"• строка id={row['id']}: {len(row['answer'])} → {len(body)} симв. (dry-run)")
        else:
            cur.execute("UPDATE knowledge_snippets SET answer = %s, updated_at = NOW() WHERE id = %s",
                        (body, row["id"]))
            print(f"• строка id={row['id']}: {len(row['answer'])} → {len(body)} симв.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
