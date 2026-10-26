"""Одноразовая проверка снимка слоя (в репозиторий не входит).

Сним `layers/core_rules_layer.md` — это рендер карточек, поэтому проверка отвечает на
два вопроса: (1) не начинается ли тело answer со строки заголовка (дефект, который
ловит `collect`), и (2) не повторяется ли заголовок раздела в answer чаще одного раза.
"""
import io
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "layers/core_rules_layer.md"
text = io.open(path, encoding="utf-8").read()
blocks = re.split(r"(?m)^## ", text)[1:]
print("cards", len(blocks))

starts = 0
repeats = 0
for block in blocks:
    title, _, body = block.partition("\n")
    body = body.strip("`")
    # ответ карточки в снимке идёт после строки `source_url=...`
    m = re.search(r"(?m)^source_url=.*$", body)
    answer = body[m.end() + 1:] if m else body
    if answer.lstrip().startswith("#"):
        starts += 1
        print("BODY_STARTS_HEADING", title)
    lines = [ln for ln in answer.split("\n") if ln.strip()]
    if lines:
        head = lines[0]
        cnt = answer.count(head)
        if cnt != 1:
            repeats += 1
            print("HEADING_REPEAT", cnt, title, "|", head[:50])
print("bodies_starting_with_heading", starts)
print("heading_repeats", repeats)
sys.exit(0 if not starts and not repeats else 1)
