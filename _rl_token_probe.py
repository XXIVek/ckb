"""Временный зонд (узел R-LAYER): какие токены инструментов живут в файлах правил
поиска и какие зарегистрированы. Цель — заранее видеть, какие имена правила обещают,
а какие упоминают как удалённые, прежде чем расширять EXPECTED_TOOLS на core-контракт."""
import sys

sys.path.insert(0, "tools")
import check_search_rules_sync as s

sys.stdout.reconfigure(encoding="utf-8")
names = s.registered_tool_names()
found = set()
for path in s.RULE_FILES:
    found |= set(s.TOOL_TOKEN.findall(s.read(path)))
print("registered:", len(names))
print("in rules NOT registered:", sorted(found - names))
print("registered NOT in rules:", sorted(names - found))
