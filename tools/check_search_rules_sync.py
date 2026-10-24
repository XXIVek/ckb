"""
Сверка текстов правил с кодом поиска и с контрактами инструментов MCP-серверов.

Проверяет три вещи:
  1. SEARCH_RULES.md содержит разделы/маркеры, описывающие текущий поиск:
     алиас = точное совпадение, двухфазное чтение, категории, карантин,
     служебный префикс слоя правил `core-rules:`, пороги и веса.
  2. Тексты правил не называют инструменты, которых нет в регистрах MCP-серверов,
     и называют все инструменты тех серверов, которые они документируют
     (реальное разрешение имён берётся из tools/check_mcp_tool_wiring.py).
  3. .clinerules/1c-knowledge-base_Rule.md не противоречит SEARCH_RULES.md
     по числу инструментов и по описанию алиасного шага.

Границы проверки — что она НЕ проверяет:
  - совпадение ОПИСАНИЯ инструмента с его реализацией: сравниваются имена, число
    инструментов и маркеры текста; формулировки остаются на ревью;
  - правила загрузки конфигураций как сценарий (правила R1–R17, четыре исхода,
    норматив docs/config-scenarios/FLOWCHART_1c-configurations-core.md) — их
    сторожат validate_load_flow.py, validate_project.py и
    tools/check_mcp_tool_wiring.py; LOAD_RULES_Config.md и правила серверов
    участвуют здесь только как текст, который обязан называть инструменты
    документируемого сервера и не называть снятые инструменты как живые;
  - содержимое БД и приведённые в правилах замеры чисел — не проверяются.

Почему это отдельный скрипт: 20.10.2026 текст правил разошёлся с кодом — в
SEARCH_RULES.md и в .clinerules/1c-knowledge-base_Rule.md алиасный шаг
описывался как «по началу слова», тогда как `mcp_search_docs` сопоставляет с
alias_name только точное совпадение всего запроса (LIKE используется лишь для
подсказки «см. также»). 23.10.2026 расхождение повторилось в обратную сторону и
в другом месте: контракт `server_configurations_core.py` стал пятиинструментным
(добавлен `load_configuration_root_modules_tool`, узел V44), а правила загрузки
(`LOAD_RULES_Config.md`) и сводка `.clinerules/1C_Rule.md` остались
четырёхинструментными — потому что ни одна проверка не сравнивала тексты правил с
регистрами инструментов: `check_mcp_tool_wiring.py` сверяет серверы между собой и
с `EXPECTED_TOOLS`, а `check_search_rules_sync.py` смотрел только два файла про
поиск и потому проходил молча, когда контракт изменился в другом сервере. Скрипт
сравнивает обе стороны: имена из правил → регистрация (не говорит ли правило об
инструменте, который сняли) и регистрация → правила (назван ли инструмент,
добавленный в контракт).
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

SEARCH_RULES = PROJECT_ROOT / "SEARCH_RULES.md"
KB_RULE = PROJECT_ROOT / ".clinerules" / "1c-knowledge-base_Rule.md"
SERVER_PY = PROJECT_ROOT / "server.py"

# Обязательные маркеры SEARCH_RULES.md: каждый закрывает одно утверждение
# контракта поиска; отсутствие маркера означает, что правила описывают другой
# поиск. Префиксы и константа добавлены 23.10.2026: поиск по слою правил
# (`core-rules:`) и порог усечения `answer` — то, что описание не имеет права
# терять.
REQUIRED_MARKERS = [
    "Алиас = точное совпадение",
    "Что отдаёт поиск",
    "Двухфазное чтение",
    "Ранжирование",
    "Категории",
    "Карантин",
    "Пороги и веса",
    "Порядок шагов",
    "Пустая выдача",
    "Противоречие двух строк",
    "Правило вывода",
    "core-rules:",
    "TITLE_LAYER_MARKERS",
    "MAX_ANSWER_CHARS",
]

# Утверждения, которых в правилах быть не должно: они описывают поведение,
# которого код не выполняет.
FORBIDDEN_PHRASES = [
    ("алиасный шаг ищет по началу слова", "алиасный шаг берёт точное совпадение"),
    ("полнотекстовый поиск по подстроке", "полнотекстовый поиск по лексемам"),
]

# --- контракты инструментов ------------------------------------------------
# Имена файлов серверов — те же, что в tools/check_mcp_tool_wiring.py.
SERVER_FILES = {
    "server.py": SERVER_PY,
    "server_configurations_core.py": PROJECT_ROOT / "server_configurations_core.py",
    "server_configurations_enrichment.py": PROJECT_ROOT / "server_configurations_enrichment.py",
    "server_configurations_export.py": PROJECT_ROOT / "server_configurations_export.py",
}

# Какие серверы какой текст документирует полностью. Обратная проверка («каждый
# инструмент контракта назван в правилах») ставится только паре «файл ↔ сервер,
# который этот файл описывает»: сводка .clinerules/1C_Rule.md даёт таблицу
# knowledge-base выборочно (полная таблица — в .clinerules/1c-knowledge-base_Rule.md),
# поэтому для server.py она идёт только в сторону «нет ли снятых имён».
DOCUMENTED_SERVERS = {
    "SEARCH_RULES.md": ["server.py"],
    ".clinerules/1c-knowledge-base_Rule.md": ["server.py"],
    "LOAD_RULES_Config.md": ["server_configurations_core.py"],
    ".clinerules/1c-configurations-core_Rule.md": ["server_configurations_core.py"],
    ".clinerules/1c-configurations-enrichment_Rule.md": ["server_configurations_enrichment.py"],
    ".clinerules/1c-configurations-export_Rule.md": ["server_configurations_export.py"],
    ".clinerules/1C_Rule.md": [
        "server_configurations_core.py",
        "server_configurations_enrichment.py",
        "server_configurations_export.py",
    ],
}

# Файлы живого контракта поиска: исторические имена инструментов в них
# запрещены — это правило «возвращать снятые инструменты нельзя» из
# tools/check_mcp_tool_wiring.py. В файлах истории (.clinerules/*, правила
# загрузки) эти имена обязаны стоять как удалённые: молчаливое исчезновение
# строки об удалённом инструменте теряет историю так же, как и его возврат.
SEARCH_CONTRACT_FILES = ["SEARCH_RULES.md", ".clinerules/1c-knowledge-base_Rule.md"]

# Инструменты, снятые 14.10.2026 с core- и enrichment-серверов. Шесть имён
# снятого export-сервера берутся из DELETED_TOOLS tools/check_mcp_tool_wiring.py,
# чтобы два скрипта не держали по два списка одних и тех же имён.
REMOVED_SERVER_TOOLS = [
    "add_config_alias_tool",
    "add_snippet_dependency_tool",
    "analyze_config_load_tool",
    "batch_index_from_dump_tool",
    "count_objects_by_config_tool",
    "delete_config_tool",
    "delete_objects_by_config_tool",
    "find_config_by_name_uuid_tool",
    "generate_aliases_for_object_tool",
    "get_alias_target_tool",
    "get_bsl_module_code_tool",
    "get_config_snippet_stats_tool",
    "get_configuration_tool",
    "get_enum_values_tool",
    "get_object_structure_tool",
    "get_snippets_for_object_tool",
    "list_bsl_modules_tool",
    "list_config_objects_tool",
    "list_configurations_tool",
    "read_config_file_tool",
    "register_cross_reference_tool",
    "register_external_report_tool",
    "search_bsl_code_tool",
    "search_config_by_alias_tool",
    "search_config_objects_tool",
    "update_configuration_status_tool",
    "update_dependent_snippets_tool",
]

TOOL_TOKEN_RE = re.compile(r"\b[a-z][a-z0-9_]*_tool\b")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def registered_tool_names() -> dict[str, list[str]]:
    """Имена инструментов из регистрации `@mcp.tool` в каждом сервере.

    Источник — те же файлы, что читает tools/check_mcp_tool_wiring.py: список
    задаёт не этот скрипт, иначе проверка подтверждала бы свой собственный список.
    """
    out: dict[str, list[str]] = {}
    for name, path in SERVER_FILES.items():
        if not path.exists():
            out[name] = []
            continue
        text = read_text(path)
        out[name] = re.findall(r"@mcp\.tool\(\)\s*\ndef\s+([a-z_][a-z0-9_]*)", text)
    return out


def historical_tool_names() -> set[str]:
    """Снятые имена: свой список + шесть имён export-сервера из соседнего скрипта."""
    import check_mcp_tool_wiring

    return set(REMOVED_SERVER_TOOLS) | set(check_mcp_tool_wiring.DELETED_TOOLS)


def check_markers(text: str) -> list[str]:
    problems = []
    for marker in REQUIRED_MARKERS:
        if marker not in text:
            problems.append(f"в SEARCH_RULES.md нет маркера «{marker}»")
    return problems


def check_phrases(*texts: str) -> list[str]:
    problems = []
    for bad, good in FORBIDDEN_PHRASES:
        for text in texts:
            if bad in text:
                problems.append(f"в тексте есть «{bad}» (код делает: {good})")
                break
    return problems


def check_contracts(names: dict[str, list[str]]) -> list[str]:
    """Две стороны: имена из правил → регистрация, регистрация → имена правил."""
    problems = []
    historical = historical_tool_names()
    registered_all: set[str] = set()
    for tools in names.values():
        registered_all.update(tools)

    texts = {}
    for rel in DOCUMENTED_SERVERS:
        path = PROJECT_ROOT / rel
        if not path.exists():
            problems.append(f"нет файла правил: {rel}")
            continue
        texts[rel] = read_text(path)

    print("\n=== КОНТРАКТ ИНСТРУМЕНТОВ В ПРАВИЛАХ ===")
    for rel in sorted(DOCUMENTED_SERVERS):
        if rel not in texts:
            continue
        text = texts[rel]
        tokens = set(TOOL_TOKEN_RE.findall(text))
        unknown = sorted(tokens - registered_all - historical)
        if unknown:
            problems.append(
                f"{rel}: названы инструменты вне контракта и не в списке снятых: "
                + ", ".join(unknown)
            )
        stale = sorted(t for t in tokens if t in historical)

        if rel in SEARCH_CONTRACT_FILES:
            if stale:
                problems.append(
                    f"{rel}: в описании живого поиска названы снятые инструменты: "
                    + ", ".join(stale)
                )
            print(f"  {rel}: снятых имён нет, неизвестных {len(unknown)}")
            continue

        print(
            f"  {rel}: исторических имён {len(stale)} (разрешены как история), "
            f"неизвестных {len(unknown)}"
        )
        for server in DOCUMENTED_SERVERS[rel]:
            tools = names.get(server)
            if not tools:
                problems.append(f"{rel}: сервер {server} не найден или без инструментов")
                continue
            missing = [t for t in tools if t not in text]
            if missing:
                problems.append(
                    f"{rel}: в правилах {server} не названо {len(missing)} из {len(tools)} "
                    "инструментов контракта: " + ", ".join(missing)
                )
            print(
                f"  {rel} ↔ {server}: названо {len(tools) - len(missing)}/{len(tools)}"
            )
    return problems


def check_rule_numbers(text: str, tools: list[str]) -> list[str]:
    """Число инструментов, названное в SEARCH_RULES.md, обязано равняться регистрации.

    Только для SEARCH_RULES.md: в правилах серверов числа — часть истории
    («прежний контракт — три инструмента», «контракт 17 → 18»), и равняться
    текущему состоянию они не обязаны; там проверяются имена, а не числа.
    """
    problems = []
    for match in re.finditer(r"(\d+)\s+инструмент", text):
        named = int(match.group(1))
        if named != len(tools):
            problems.append(
                f"в SEARCH_RULES.md названо {named} инструментов, "
                f"в регистрации server.py их {len(tools)}"
            )
    return problems


ALIAS_FORMULA = "Точное совпадение LOWER(alias_name) со **всем запросом целиком**"


def check_kb_rule(kb_text: str) -> list[str]:
    """Точная формулировка алиасного шага в правилах knowledge-base."""
    if ALIAS_FORMULA not in kb_text:
        return [
            "в .clinerules/1c-knowledge-base_Rule.md нет точной формулировки "
            "алиасного шага (она расходится с кодом)"
        ]
    return []


def main() -> int:
    if not SEARCH_RULES.exists():
        print(f"❌ нет файла: {SEARCH_RULES}")
        return 1
    rules_text = read_text(SEARCH_RULES)
    kb_text = read_text(KB_RULE) if KB_RULE.exists() else ""

    problems = []
    print("=== SEARCH_RULES.md ===")
    marker_problems = check_markers(rules_text)
    problems += marker_problems
    print(f"маркеров проверено {len(REQUIRED_MARKERS)}, отсутствует {len(marker_problems)}")
    phrase_problems = check_phrases(rules_text, kb_text)
    problems += phrase_problems
    print(f"утверждений вопреки коду: {len(phrase_problems)}")

    names = registered_tool_names()
    print("\n=== РЕГИСТРАЦИЯ ИНСТРУМЕНТОВ ===")
    for server, tools in names.items():
        print(f"  {server}: {len(tools)}")
    core = names.get("server_configurations_core.py", [])
    if "load_configuration_root_modules_tool" not in core:
        problems.append(
            "в server_configurations_core.py нет load_configuration_root_modules_tool "
            "(узел V44) — контракт не соответствует правилам"
        )
    problems += check_rule_numbers(rules_text, names.get("server.py", []))
    problems += check_contracts(names)

    print("\n=== 1c-knowledge-base_Rule.md ===")
    kb_problems = check_kb_rule(kb_text)
    problems += kb_problems
    print(f"расхождений с кодом поиска: {len(kb_problems)}")

    print("\n=== ИТОГ ===")
    if problems:
        for p in problems:
            print(f"❌ {p}")
        print(f"расхождений: {len(problems)}")
        return 1
    print(
        "расхождений нет: тексты правил соответствуют коду поиска "
        "и контрактам инструментов"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
