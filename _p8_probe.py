#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор непокрытых имён инструментов (основание для П2-Ф-8).

Измеритель `_journal_code_history.py` называет имена, которые не читаются слоем, но не говорит,
чем они являются: снятым инструментом, прежним именем теперешнего или ссылкой на чужой контракт.
Решение по каждому имени принимается по git: где имя появилось, где пропало и что появилось вместе
с пропаданием.

Запуск: python _p8_probe.py [kb-rules enrich-rules]
"""
import subprocess
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "tools")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _journal_code_history as J  # noqa: E402
from check_mcp_tool_wiring import DELETED_TOOLS  # noqa: E402


def signs(sha, path):
    """Имена, добавленные и снятые в изменённых строках коммита."""
    res = subprocess.run(
        ["git", "--no-pager", "show", "--format=", "--unified=0", sha, "--", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    added, removed = set(), set()
    for line in res.stdout.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.update(J.TOOL_NAME.findall(line))
        elif line.startswith("-"):
            removed.update(J.TOOL_NAME.findall(line))
    return added, removed


def main(argv=None):
    markers = list(sys.argv[1:] if argv is None else argv) or ["kb-rules", "enrich-rules"]
    for marker in markers:
        server = J.LAYER_SERVER[marker]
        commits = J.composition_commits(server) or []
        signed = [(day, sha, *signs(sha, server)) for day, sha, _names in commits]
        names = set()
        for _day, _sha, added, removed in signed:
            names |= added | removed
        foreign = J.foreign_names(server)
        live, journal = J.layer_texts(marker)
        lf, jf = J.compact(live), J.compact(journal)
        demanded = names - foreign
        uncovered = sorted(n for n in demanded if n not in lf and n not in jf)
        print(f"\n=== {marker} / {server}: имён в диффах {len(names)}, "
              f"чужих {len(names & foreign)}, требуются {len(demanded)}, непокрытых {len(uncovered)}")
        for name in uncovered:
            where = []
            for day, sha, added, removed in signed:
                if name in removed:
                    replaced_by = sorted(added - {name})
                    where.append(f"{day} {sha} снято"
                                 + (f" → добавлено: {', '.join(replaced_by)}" if replaced_by else ""))
                elif name in added:
                    where.append(f"{day} {sha} добавлено")
            kind = "в DELETED_TOOLS" if name in DELETED_TOOLS else "вне DELETED_TOOLS"
            print(f"\n{name}  [{kind}]")
            for line in where[:6]:
                print(f"    {line}")
            if not where:
                print("    коммитов регистра с этим именем нет (имя из текста, а не из регистра?)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
