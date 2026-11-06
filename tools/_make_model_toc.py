#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_make_model_toc.py — оглавление большого документа порождается прогоном (узел V61, П2).

Зачем. `docs/config-scenarios/01_configuration.md` — 2801 строка и 113 разделов уровня
`##`…`####`. Ручной перечень разделов в таком файле отстаёт от файла при первой же правке
(тот же дефект, что датированные перечни закрытых позиций, снятые шагом П1 этого узла),
а без перечня документ невозможно прочитать по частям: читатель не знает, где искать
нужный раздел.

Что делает прогон:
  1. собирает заголовки уровней `##`…`####`, не заходя внутрь блоков кода (``` … ```);
  2. строит якоря тем же правилом, что рендер Markdown: литеры (включая кириллицу) и цифры
      остаются, пунктуация и эмодзи снимаются, пробелы становятся дефисом; повторному
      заголовку добавляется суффикс `-1`, `-2` — иначе ссылка ведёт не туда;
  3. вставляет перечень между маркерами перед первым разделом `##`; повторный прогон
      заменяет блок, а не добавляет второй (приём `tools/_make_position_frame.py`);
  4. `--check` — ничего не пишет, а сверяет блок в файле со своим выводом: расхождение
      означает, что в документе появился новый раздел и оглавление не перегенерировали.

Сверку держит пункт 9 проверки `python tools/check_position_frame.py` (там же, где пункт 8
сверяет реестр состояния позиций, шаг П1 узла).

Запуск из корня репозитория:
    python tools/_make_model_toc.py                 # сверка (печать, файл не трогает)
    python tools/_make_model_toc.py --write         # перегенерировать блок
    python tools/_make_model_toc.py --check         # код возврата 1 при расхождении
    python tools/_make_model_toc.py --file docs/config-scenarios/02_other.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE = "docs/config-scenarios/01_configuration.md"

MARK_BEGIN = ("<!-- BEGIN generated: оглавление разделов (порождает прогон "
              "tools/_make_model_toc.py, узел V61) -->")
MARK_END = "<!-- END generated: оглавление разделов -->"

HEADING_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
# Якорь Markdown: остаются буквы (любой письменности), цифры, дефис и подчёркивание;
# остальное (в том числе эмодзи и двоеточия) снимается, пробелы становятся дефисом.
SLUG_DROP_RE = re.compile(r"[^\w\s-]", re.UNICODE)


def slugify(title: str, taken: set) -> str:
    slug = SLUG_DROP_RE.sub("", title.strip().lower()).strip()
    slug = re.sub(r"\s+", "-", slug)
    if slug in taken:
        n = 1
        while f"{slug}-{n}" in taken:
            n += 1
        slug = f"{slug}-{n}"
    taken.add(slug)
    return slug


def collect_headings(text: str):
    """(уровень, заголовок, якорь) по порядку файла; блоки кода не смотрим.

    Диапазон между маркерами собственного оглавления пропускается: иначе повторный прогон
    включал бы оглавление в себя и число разделов росло бы на единицу при каждом прогоне.
    """
    headings, taken, in_fence, in_own_block = [], set(), False, False
    for line in text.splitlines():
        if line.startswith(MARK_BEGIN):
            in_own_block = True
            continue
        if line.startswith(MARK_END):
            in_own_block = False
            continue
        if in_own_block:
            continue
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        headings.append((level, title, slugify(title, taken)))
    return headings


def render_block(text: str) -> str:
    """Текст блока между маркерами — ровно то, что обязан содержать документ."""
    headings = collect_headings(text)
    counts = {2: 0, 3: 0, 4: 0}
    for level, _title, _slug in headings:
        counts[level] += 1
    lines = [
        MARK_BEGIN,
        "",
        "### Оглавление разделов — порождается прогоном",
        "",
        "Перечень порождает `python tools/_make_model_toc.py` (шаг П2 узла V61), правит его",
        "только прогон: держать оглавление руками — значит получить перечень, отстающий от",
        "файла при первой же правке (тем же приёмом сняты датированные перечни закрытых",
        "позиций, шаг П1 этого узла). Разделов: **",
        f"{len(headings)}** (`##` — {counts[2]}, `###` — {counts[3]}, `####` — {counts[4]}).",
        "",
    ]
    for level, title, slug in headings:
        lines.append(f"{'  ' * (level - 2)}- [{title}](#{slug})")
    lines += ["", MARK_END]
    return "\n".join(lines) + "\n"


def extract_block(text: str):
    start, end = text.find(MARK_BEGIN), text.find(MARK_END)
    if start == -1 or end == -1:
        return None
    return text[start:end + len(MARK_END)] + "\n"


def write_file(path: Path) -> str:
    """Врезка или замена блока между маркерами (приём `_make_position_frame.py`)."""
    text = path.read_text(encoding="utf-8")
    block = render_block(text)
    old = extract_block(text)
    if old is not None:
        path.write_text(text.replace(old, block), encoding="utf-8")
        return "заменён"
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("## "):
            path.write_text("".join(lines[:index]) + block + "\n"
                            + "".join(lines[index:]), encoding="utf-8")
            return f"вставлен перед разделом строки {index + 1}"
    raise SystemExit(f"в {path} нет раздела `## ` — вставлять оглавление не перед чем")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--write", action="store_true", help="перегенерировать блок в файле")
    ap.add_argument("--check", action="store_true",
                    help="сверить блок в файле с выводом прогона (rc=1 при расхождении)")
    args = ap.parse_args()

    path = (ROOT / args.file).resolve()
    if not path.exists():
        print(f"❌ файл не найден: {path}")
        return 2
    text = path.read_text(encoding="utf-8")
    headings = collect_headings(text)
    print(f"файл: {args.file}")
    print(f"заголовков собрано: {len(headings)} "
          f"(## {sum(1 for h in headings if h[0] == 2)}, "
          f"### {sum(1 for h in headings if h[0] == 3)}, "
          f"#### {sum(1 for h in headings if h[0] == 4)})")

    if args.write:
        print(f"блок оглавления: {write_file(path)}")
        return 0
    if args.check:
        current = extract_block(text)
        if current is None:
            print("FAIL блока оглавления в файле нет — нужен прогон --write")
            return 1
        if current == render_block(text):
            print("PASS оглавление в файле совпадает с выводом прогона")
            return 0
        print(f"FAIL оглавление отстаёт: в файле {len(current)} симв., "
              f"прогон даёт {len(render_block(text))} — нужен прогон --write")
        return 1
    print(render_block(text))
    print("(режим сверки: файл не изменён; запись — --write, код возврата — --check)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

