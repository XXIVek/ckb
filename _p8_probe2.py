# -*- coding: utf-8 -*-
"""ПРОВЕРКА П2-Ф-8, шаг 2: чем был прежний инструмент (П2-Ф-8, 29.10.2026).

Про `_p8_probe.py` имена разведены по коммитам; здесь берётся то, что делал прежний
инструмент — первая строка его docstring из состояния реестра НЕПОСРЕДСТВЕННО перед снятием
(`<снимающий коммит>^`). Без этого пара «прежнее имя → теперешнее» оставалась бы догадкой по
сходству имён: узел журнала обязан называть замену по назначению инструмента, а не по подстроке.
"""
from __future__ import annotations

import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

CASES = [
    ("enrich-rules", "server_configurations_enrichment.py", "a71e7b0d",
     ["add_config_alias_tool", "get_alias_target_tool", "search_config_by_alias_tool",
      "get_cross_references_tool", "get_snippets_for_object_tool",
      "get_config_snippet_stats_tool", "add_snippet_dependency_tool",
      "update_dependent_snippets_tool", "generate_aliases_for_object_tool"]),
    ("kb-rules", "server.py", "342a213f",
     ["search_fragments_tool", "get_fragment_by_name_tool", "get_import_log_tool",
      "import_html_files_tool", "import_markdown_files_tool", "detect_category_tool",
      "fix_snippet_tool", "load_from_folder_tool", "load_from_url_tool"]),
    ("kb-rules", "server.py", "e043843a",
     ["create_element_tool", "update_element_tool", "create_group_tool", "update_group_tool",
      "search_elements_tool", "search_groups_tool", "search_snippets_tool",
      "get_element_details_tool", "get_group_hierarchy_tool"]),
]

DEF_RE = re.compile(r"^(?:async\s+)?def\s+(\w+_tool)\b", re.MULTILINE)


def body_of(text: str, name: str) -> str:
    """Первая строка docstring функции — назначение прежнего инструмента."""
    m = re.search(rf"^(?:async\s+)?def\s+{name}\b[^\n]*\n", text, re.MULTILINE)
    if not m:
        return "<в этом состоянии реестра имени нет>"
    tail = text[m.end(): m.end() + 1200]
    for line in tail.splitlines():
        s = line.strip()
        if not s or s.startswith(("@", "#")):
            continue
        if s.startswith(('"""', "'''")):
            s = s.lstrip("'\"").strip()
            if s:
                return s[:220]
            continue
        return s[:220]
    return "<docstring пуст>"


for marker, fname, drop_sha, names in CASES:
    res = subprocess.run(["git", "show", f"{drop_sha}^:{fname}"], capture_output=True,
                        encoding="utf-8", errors="replace")
    text = res.stdout or ""
    print(f"\n=== {marker} {fname} состояние перед {drop_sha} ===")
    print(f"    зарегистрировано инструментов: {len(DEF_RE.findall(text))}")
    for name in names:
        print(f"  {name}\n      ← {body_of(text, name)}")
