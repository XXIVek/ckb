"""Одноразовая проверка примитивов дерева (узел RULE-TREE): уровни, типы узлов, границы."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "src")
import rules_layer as RL

CASES = [
    "rules",
    "rules:index",
    "rules:always:authoring",
    "kb-rules:index",
    "kb-rules:optional:quarantine",
    "kb-rules:journal:ref:06:4",
    "export-rules:checks",
    "core-rules:ref:06:2",
    "rules:kb-rules:get_rules_report",
    "rules:kb-rules:get_rules_report:ref:001",
    "rules:kb-rules:get_rules_report:ref:001:4",
    "rules:kb-rules:journal:001:ref:001:4",
    "rules:kb-rules:get_rules_report:ref:001:4:5",
]
for address in CASES:
    errors = RL.validate_address(address, RL.marker_of(address))
    print(f"{address:52} ур.{RL.levels_of(address)} {RL.node_kind(address):8} "
          f"H{RL.heading_level(address)} parent={RL.parent_prefix(address)!r}")
    for e in errors:
        print("   ⚠️", e)
print("\nродитель для вершины:", repr(RL.parent_prefix("rules")), "| kinds:",
      RL.KIND_ROOT, RL.KIND_LAYER, RL.KIND_RULE, RL.KIND_PART, RL.KIND_JOURNAL, RL.KIND_CHECKS)
