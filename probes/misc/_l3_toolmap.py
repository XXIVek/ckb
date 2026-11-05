"""Карта «инструмент → карточка, которая его называет», по слоям и разделам.

`_l3_coverage.py` отвечает на вопрос «назван ли инструмент вообще»; этот — «где именно», потому что
«назван в поддереве» и «назван в карточке слоя» для читателя карточки слоя — разные вещи: в
карточку слоя он не попадает и маршрут к нему не виден.
"""

import ast
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "src"))

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

SECTION_RE = re.compile(r"(?m)^===[ \t]*([A-ZА-Я][A-ZА-Я_]*)")


def registered(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(target, ast.Attribute) and target.attr == "tool":
                names.append(node.name)
    return names


def sections(answer):
    marks = [(m.group(1), m.start()) for m in SECTION_RE.finditer(answer or "")]
    return [(name, start, marks[i + 1][1] if i + 1 < len(marks) else len(answer))
            for i, (name, start) in enumerate(marks)]


names = registered(ROOT_DIR / "server.py")
with get_cursor() as cur:
    cur.execute(
        "SELECT question, answer FROM knowledge_snippets "
        "WHERE question LIKE %s AND source_url LIKE %s ORDER BY question",
        ("rules:kb-rules%", RL.SOURCE_SCHEME + "%"),
    )
    rows = cur.fetchall()

where = {}
for row in rows:
    hits = {}
    for name in names:
        in_answer = [sec for sec, start, end in sections(row["answer"])
                     if name in row["answer"][start:end]]
        if name in row["answer"]:
            hits[name] = in_answer or ["вне разделов"]
    where[row["question"]] = hits

print("=== где назван каждый инструмент регистра ===")
for name in names:
    cards = [f"{q} ({','.join(where[q][name])})" for q in sorted(where) if name in where[q]]
    print(f"{name}\n    " + ("\n    ".join(cards) if cards else "НЕ НАЗВАН НИГДЕ"))

print("\n=== сколько инструментов названо каждой карточкой ===")
for q in sorted(where):
    listed = sorted(where[q])
    print(f"{q}: {len(listed)}")
    for name in listed:
        print(f"    {name} -> {','.join(where[q][name])}")

print("\n=== итог ===")
named = [n for n in names if any(n in where[q] for q in where)]
layer = "rules:kb-rules:"
print(f"регистра: {len(names)} | названо поддеревом: {len(named)} | "
      f"названо карточкой слоя: {len(where.get(layer, {}))}")
for name in names:
    if name not in where.get(layer, {}):
        print(f"  вне карточки слоя: {name}")
