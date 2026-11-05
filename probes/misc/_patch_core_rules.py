"""Одноразовая правка исходников слоя core-rules: снятый инструмент чтения правил.

Узел RULE-LAYER (24.10.2026) снял `get_load_config_rules_tool`; ссылки на него остаются в двух
исходниках плана (`1c-configurations-core_Rule.md`, `LOAD_RULES_Config.md`). Правка одна на оба,
потому что править нужно одинаково: расхождение формулировок дало бы два разных правила об одном
шаге — тот дефект, из-за которого тексты правил и сверяются с кодом.

Скрипт одноразовый: он меняет тексты, а не поведение. Каждая замена обязана найтись ровно один
раз; ненайденная замена — прогон с rc=1, а не молчаливый пропуск (иначе «правило поправили»
оказалось бы незаписанным).
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]

READ_RULES = """### Чтение правил слоя (КРИТИЧНО!)

> ⚠️ **ВАЖНО:** Перед началом работы с конфигурацией **ВСЕГДА** читайте индекс слоя правил:
> `search_docs_tool(query="core-rules:index", category="1c-configurations-core")`, затем
> `get_snippet_tool(snippet_id)` по id из выдачи. Это инструменты `1c-knowledge-base`, не
> core-MCP: правила читаются там, а отдельного инструмента «отдай файл правил целиком» в
> контракте больше нет (узел RULE-LAYER, 24.10.2026) — он возвращал сплошной текст и обходил
> категорию, то есть подмешивал чужие строки.

| Что читать | Чем | Зачем |
|---|---|---|
| `core-rules:index` | `search_docs_tool` + `get_snippet_tool` | оглавление слоя: адрес нужного раздела |
| `core-rules:ref:11` | те же | compact-правила загрузки (прежний `LOAD_RULES_Config.md`, теперь архив) |"""

STEP0 = """# Шаг 0 (обязательный): прочитать индекс слоя правил (это НЕ инструмент core-MCP):
#   search_docs_tool(query="core-rules:index", category="1c-configurations-core")
#   затем get_snippet_tool(snippet_id) по id из выдачи"""

CONTRACT_NOTE = ("(три утверждены 12.10.2026, четвёртый добавлен узлом V25 15.10.2026, пятый — "
                 "узлом V44 22.10.2026; узел RULE-LAYER 24.10.2026 снял инструмент чтения "
                 "правил, и контракт снова четыре)")

EDITS = [
    ("docs/rules/1c-configurations-core_Rule.md",
     "## 🎯 Контракт загрузки — пять инструментов (три утверждены 12.10.2026, четвёртый добавлен "
     "узлом V25 15.10.2026, пятый — узлом V44 22.10.2026)",
     "## 🎯 Контракт загрузки — четыре инструмента " + CONTRACT_NOTE),
    ("docs/rules/1c-configurations-core_Rule.md",
     "| `get_load_config_rules_tool` | `()` | Шаг 0: компактные правила загрузки "
     "(`LOAD_RULES_Config.md`) |\n",
     ""),
    ("docs/rules/1c-configurations-core_Rule.md",
     "### Загрузка правил (КРИТИЧНО!)\n\n"
     "> ⚠️ **ВАЖНО:** Перед началом работы с конфигурацией **ВСЕГДА** загружайте правила через "
     "`get_load_config_rules_tool()`. Это обязательный первый шаг!\n\n"
     "| Инструмент | Параметры | Назначение |\n"
     "|-----------|-----------|------------|\n"
     "| `get_load_config_rules_tool()` (core-MCP) | — | Загрузить `LOAD_RULES_Config.md` — "
     "компактные правила загрузки каталогов. **Всегда вызывайте перед началом работы с "
     "конфигурациями!** |\n"
     "| `get_search_rules_tool()` (**1c-knowledge-base**, не core) | — | Правила поиска по "
     "`local_doc`; в core-MCP этого инструмента нет |",
     READ_RULES),
    ("docs/rules/1c-configurations-core_Rule.md",
     "# Шаг 0 (обязательный): правила загрузки\nget_load_config_rules_tool()",
     STEP0),
    ("docs/rules/1c-configurations-core_Rule.md",
     "1. **ВСЕГДА загружайте правила через `get_load_config_rules_tool()`** перед началом работы.",
     "1. **ВСЕГДА читайте индекс слоя правил `core-rules:index`** перед началом работы: правила "
     "больше\n   не отдаются отдельным инструментом (узел RULE-LAYER, 24.10.2026), а сплошной "
     "файл правил\n   обходил категорию и подмешивал чужие строки."),
    ("docs/rules/LOAD_RULES_Config.md",
     "## Контракт MCP `1c-configurations-core` — пять инструментов\n\n"
     "(три утверждены 12.10.2026, четвёртый добавлен узлом V25 15.10.2026, пятый — узлом V44 "
     "22.10.2026)",
     "## Контракт MCP `1c-configurations-core` — четыре инструмента\n\n" + CONTRACT_NOTE),
    ("docs/rules/LOAD_RULES_Config.md",
     "| `get_load_config_rules_tool()` | Шаг 0, перед любой загрузкой |\n",
     ""),
]


def main():
    failures = []
    for rel, old, new in EDITS:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            failures.append(f"{rel}: замена найдена {count} раз (ожидался 1): {old[:70]!r}")
            continue
        path.write_text(text.replace(old, new), encoding="utf-8")
        print(f"OK {rel}: {old[:70]!r}")
    if failures:
        print("\nНЕ ВЫПОЛНЕНО:")
        for f in failures:
            print("  - " + f)
        return 1
    print("\nвсе замены применены по одному разу")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
