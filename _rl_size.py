"""Временный замер: карточки слоёв правил, их адреса и размеры (для разметки always/optional)."""
import sys

sys.path.insert(0, "src")
import rules_layer as rl  # noqa: E402

for m in rl.markers():
    text = open(f"docs/rules/{m}.md", encoding="utf-8").read()
    cards, errs = rl.parse_document(text, m)
    total = sum(len(c["answer"]) for c in cards)
    print(f"=== {m}: cards={len(cards)} chars={total} errors={len(errs)}")
    for c in cards:
        print(f"  {len(c['answer']):6d}  {c['address']}")
    for e in errs:
        print(f"  ERR {e}")
