"""
Сверка текстов правил со слоями `local_doc` — с регистрами инструментов MCP и с кодом поиска.

Узел RULE-LAYER (24.10.2026) меняет предмет сверки. Раньше текстами правил были файлы
(`SEARCH_RULES.md`, `LOAD_RULES_Config.md`, `.clinerules/1c-*_Rule.md`), и скрипт сверял файлы.
Теперь тексты правил — карточки слоёв, их исходники — `docs/rules/<метка>.md`, а нормативы
переехали в `docs/rules/` и инструментами чтения больше не отдаются (сняты
`get_search_rules_tool`, `get_load_rules_tool`, `get_load_config_rules_tool`). Поэтому здесь
сверяются карточки и регистры:

  1. имя → регистрация: любой токен вида `*_tool`, названный в карточке слоя, обязан быть в
     регистре `@mcp.tool` какого-нибудь сервера либо в списке снятых имён. Это класс дефекта
     «правило обещает инструмент, которого нет» (20.10.2026 — ровно он и был);
  2. живая карточка → снятые имена: в тексте карточек состояний `always` / `optional` /
     `checks` снятое имя стоять не вправе — живое правило не имеет права учить пользоваться
     тем, чего нет. В `journal` / `reserved` и в тексте истории (строки с `→`, «прежн»,
     «удал», «снял») имя обязано остаться: молчаливое исчезновение строки об удалённом
     инструменте теряет историю так же, как и его возврат;
  3. регистрация → слой: каждый инструмент контракта сервера обязан быть назван слоем, который
     этот сервер документирует (23.10.2026 — контракт стал пятиинструментным, а правила
     остались четырёхинструментными, потому что обратную сторону никто не смотрел);
  4. описание поиска закрыто конкретными карточками слоя `kb-rules`: их адреса обязательны, и
     в тексте слоя обязаны стоять формулировки, закрывающие поведение кода (алиас = точное
     совпадение всем запросом, выдача = id + превью, категории, карантин, префикс слоя, порог
     усечения `answer`);
  5. сводка `.clinerules/1C_Rule.md` не вправе утверждать число инструментов контракта, не
     совпадающее с регистрацией (строки истории с `→` и со словами «прежн/удал/снял» — не
     утверждение текущего состояния, они пропускаются).

Границы проверки — чего она НЕ проверяет:
  - совпадение ОПИСАНИЯ инструмента с его реализацией: сравниваются имена, числа и маркеры;
  - содержимое БД и приведённые в правилах замеры (для этого есть сами прогоны);
  - «живость» карточек в слоях формата 1 (`core-rules`, `enrich-rules`, `export-rules`): у
    карточек переноса состояний нет, поэтому снятые имена в них разрешены как история, а вот
    неназванный инструмент контракта — провал и там;
  - прежняя проверка чисел по всему тексту снята: в слоях числа — часть истории
    («контракт 17 → 18»). Проверяется только каноническая форма утверждения —
    «контракт — N инструмент».

Запуск:

    python tools/check_search_rules_sync.py

Кодировку вывода скрипт настраивает сам (UTF-8): 24.10.2026 прогон с перенаправлением в файл
на cp1251 оборвался на печати `↔` и дал rc=1 при исправных правилах — ложный провал.
"""

import re
import sys
from pathlib import Path

try:  # кириллица и служебные символы вывода (❌, ↔) не влазят в cp1251 — ни в консоль Windows,
      # ни в перенаправление вывода в файл
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # сбой настройки потока не имеет права менять итог сверки
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import rules_layer as RL  # noqa: E402  (разбор карточек один на миграцию и проверку)

ROUTER = PROJECT_ROOT / ".clinerules" / "1C_Rule.md"

SERVER_FILES = {
    "server.py": PROJECT_ROOT / "server.py",
    "server_configurations_core.py": PROJECT_ROOT / "server_configurations_core.py",
    "server_configurations_enrichment.py": PROJECT_ROOT / "server_configurations_enrichment.py",
    "server_configurations_export.py": PROJECT_ROOT / "server_configurations_export.py",
}

# Слой правил -> серверы, которые он документирует полностью. Обратная проверка («каждый
# инструмент контракта назван») ставится только этой паре: сводка `.clinerules/1C_Rule.md`
# даёт таблицы выборочно, поэтому для неё проверяются только снятые имена и числа контракта.
LAYER_SERVERS = {
    "kb-rules": ["server.py"],
    "core-rules": ["server_configurations_core.py"],
    "enrich-rules": ["server_configurations_enrichment.py"],
    "export-rules": ["server_configurations_export.py"],
}

# Карточки, которыми описан живой поиск. Список адресами, а не маркерами разделов: адрес —
# единственное, чем правило находится, и именно адрес обязывает знание лежать в нужной
# карточке, а не в произвольной строке слоя.
REQUIRED_KB_CARDS = [
    "kb-rules:index",
    "kb-rules:always:index",
    "kb-rules:always:search-first",
    "kb-rules:always:two-phase-reading",
    "kb-rules:optional:search-ranking",
    "kb-rules:optional:alias-coverage",
    "kb-rules:optional:quarantine",
    "kb-rules:checks:search-sync",
]

# Формулировки, которые обязан содержать слой knowledge-base: каждая закрывает одно утверждение
# кода поиска. Отсутствующая формулировка = правила описывают другой поиск (20.10.2026:
# алиасный шаг был описан «по началу слова», тогда как код берёт точное совпадение всем
# запросом).
REQUIRED_FORMULAS = [
    "LOWER(alias_name)",
    "всем запросом целиком",
    "превью",
    "категор",
    "TITLE_LAYER_MARKERS",
    "MAX_ANSWER_CHARS",
    "mark-for-deletion",
]

# Утверждения, которых в правилах быть не должно: они описывают поведение, которого код не
# выполняет.
FORBIDDEN_PHRASES = [
    ("алиасный шаг ищет по началу слова", "алиасный шаг берёт точное совпадение"),
    ("полнотекстовый поиск по подстроке", "полнотекстовый поиск по лексемам"),
]

# Строки истории: в них число инструментов — описание прежнего состояния, а не текущего.
HISTORY_MARKERS = ("→", "прежн", "был", "удал", "сня", "ранее", "до перехода")

# Числа, названные словами: «контракт — четыре инструмента» проверяется наравне с цифрой,
# иначе ровно такая форма и проскакивает (дефект 23.10.2026 — сводка осталась
# четырёхинструментной при работающей точке входа загрузки файла).
NUM_WORDS = {
    "один": 1, "два": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7,
    "восемь": 8, "девять": 9, "десять": 10, "одиннадцать": 11, "двенадцать": 12,
    "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16,
    "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19, "двадцать": 20,
}

CONTRACT_NUMBER_RE = re.compile(
    r"контракт[^\n]{0,30}?(?P<num>\d{1,3}|один|два|три|четыре|пять|шесть|семь|восемь|"
    r"девять|десять|одиннадцать|двенадцать|тринадцать|четырнадцать|пятнадцать|"
    r"шестнадцать|семнадцать|восемнадцать|девятнадцать|двадцать)\s+инструмент",
    re.IGNORECASE,
)

TOOL_TOKEN_RE = re.compile(r"\b[a-z][a-z0-9_]*_tool\b")

# Инструменты, снятые 14.10.2026 с core- и enrichment-серверов. Имена снятого export-сервера
# и три имени инструментов чтения правил (узел RULE-LAYER) берутся из DELETED_TOOLS
# tools/check_mcp_tool_wiring.py, чтобы два скрипта не держали по два списка одних и тех же
# имён: расхождение списков дало бы «для одной проверки имя снятое, для другой — неизвестное».
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

# Состояния слоя формата 2, чьи карточки описывают действующее поведение. Индекс состояния
# правилу не принадлежит — он таблица адресов.
LIVE_STATES = (RL.STATE_ALWAYS, RL.STATE_OPTIONAL, RL.STATE_CHECKS)


def registered_tool_names():
    """Имена @mcp.tool каждого сервера — то, что реально отдаёт MCP, а не то, что обещают
    правила. Парсер тот же, что у tools/check_mcp_tool_wiring.py: два разных разбора
    регистрации дали бы две разные правды об одном регистре."""
    result = {}
    for fname, path in SERVER_FILES.items():
        if not path.exists():
            result[fname] = []
            continue
        text = path.read_text(encoding="utf-8")
        names = []
        for m in re.finditer(
            r"@mcp\.tool(?:\([^)]*\))?\s*\n\s*(?:@\w[^\n]*\n\s*)*async\s+def\s+(\w+)|"
            r"@mcp\.tool(?:\([^)]*\))?\s*\n\s*(?:@\w[^\n]*\n\s*)*def\s+(\w+)",
            text,
        ):
            names.append(m.group(1) or m.group(2))
        result[fname] = names
    return result


def historical_tool_names():
    """Снятые имена инструментов. Список один на два скрипта (см. REMOVED_SERVER_TOOLS):
    «удалено» и «не существует» — одно состояние для правил."""
    import check_mcp_tool_wiring
    return set(REMOVED_SERVER_TOOLS) | set(check_mcp_tool_wiring.DELETED_TOOLS)


def layer_document(marker):
    """Карточки исходника слоя + ошибки разбора. Путь берётся из RL.RULES_DIR, а не из
    литерала: каталог слоёв один в src/rules_layer.py, и здесь он обязан читаться тем же
    знанием, иначе переезд каталога рассинхронизирует проверку с переносом."""
    path = PROJECT_ROOT / RL.RULES_DIR / f"{marker}.md"
    if not path.exists():
        return [], [], f"нет исходника слоя: {RL.RULES_DIR / marker!s}.md"
    cards, errors, fatal = RL.load_document(path)
    if fatal:
        return [], [], fatal
    return cards, errors, None


def is_history_line(line):
    """Строка описывает прежнее состояние, а не действующее правило."""
    low = line.lower()
    return any(m in low for m in HISTORY_MARKERS)


def check_layer(marker, names, registered_all, historical):
    """Сверка одного слоя с регистрами. Возвращает (список расхождений, счётчики).

    Счётчики печатаются всегда, включая нулевые: «проверок нет» и «проверок не нашли» —
    разные ответы, и пустая выдача без счётчиков читается как «всё хорошо»."""
    problems = []
    cards, errors, fatal = layer_document(marker)
    if fatal:
        return [f"[{marker}] {fatal}"], None
    problems += [f"[{marker}] разбор исходника: {e}" for e in errors]

    layer_text = "\n".join(card["answer"] for card in cards)
    addresses = {card["address"] for card in cards}

    unknown_count = stale_count = 0
    for card in cards:
        tokens = set(TOOL_TOKEN_RE.findall(card["answer"]))
        unknown = sorted(tokens - registered_all - historical)
        if unknown:
            unknown_count += len(unknown)
            problems.append(
                f"[{marker}] {card['address']}: названы инструменты вне контракта и не "
                f"снятые: {', '.join(unknown)} — правила обещают то, чего сервер не "
                f"регистрирует (класс дефекта 20.10.2026)"
            )
        if card["state"] in LIVE_STATES:
            stale = sorted(tokens & historical)
            if stale:
                stale_count += len(stale)
                problems.append(
                    f"[{marker}] {card['address']} (состояние {card['state']}): живой "
                    f"текст называет снятые инструменты: {', '.join(stale)} — имя "
                    f"допустимо только в истории (journal/reserved) и в строке с явной "
                    f"пометкой снятия"
                )

    # Обратная сторона: добавленный в контракт инструмент не находится правилами, если слой о
    # нём молчит. Именно так 23.10.2026 контракт стал пятиинструментным в коде и
    # четырёхинструментным в правилах.
    missing = []
    for server in LAYER_SERVERS.get(marker, []):
        for tool in names.get(server, []):
            if tool not in layer_text:
                missing.append(f"{tool} ({server})")
    if missing:
        problems.append(
            f"[{marker}] инструменты контракта не названы ни в одной карточке слоя: "
            f"{', '.join(missing)} — добавленный в сервер инструмент перестаёт "
            f"документироваться, потому что обратную сторону сверки никто не смотрел"
        )

    if marker == "kb-rules":
        absent_cards = [a for a in REQUIRED_KB_CARDS if a not in addresses]
        if absent_cards:
            problems.append(
                f"[kb-rules] нет карточек, которыми описан поиск: {', '.join(absent_cards)} "
                f"— описание поиска лежит адресом; без карточки знание ищется по случайной "
                f"строке слоя или не ищется вовсе"
            )
        absent_formulas = [f for f in REQUIRED_FORMULAS if f not in layer_text]
        if absent_formulas:
            problems.append(
                f"[kb-rules] в слое нет формулировок поведения поиска: {absent_formulas} — "
                f"правила описывают другой поиск (20.10.2026: алиасный шаг был описан "
                f"«по началу слова», код берёт точное совпадение)"
            )

    for phrase, why in FORBIDDEN_PHRASES:
        if phrase in layer_text:
            problems.append(f"[{marker}] в тексте правила есть утверждение «{phrase}», "
                            f"а код делает иначе: {why}")

    counters = {
        "cards": len(cards),
        "unknown": unknown_count,
        "stale": stale_count,
        "missing": len(missing),
    }
    return problems, counters


def check_contract_numbers(names):
    """Число инструментов в сводке `.clinerules/1C_Rule.md` ↔ регистрация.

    Проверяется только каноническая форма утверждения («контракт — N инструмент»): числа внутри
    истории («контракт 17 → 18», «18 внеконтрактных инструментов удалены») текущему состоянию
    равняться не обязаны и строки с пометкой истории пропускаются. Строка без пометки истории,
    называющая число вне регистра, — ровно тот дефект, который 23.10.2026 остался незамеченным:
    код стал пятиинструментным, а сводка — нет."""
    problems = []
    if not ROUTER.exists():
        return [f"нет сводки правил: {ROUTER}"], None
    allowed = {len(v) for v in names.values()}
    for num, line in enumerate(ROUTER.read_text(encoding="utf-8").splitlines(), 1):
        for match in CONTRACT_NUMBER_RE.finditer(line):
            if is_history_line(line):
                continue
            raw = match.group("num")
            value = int(raw) if raw.isdigit() else NUM_WORDS[raw.lower()]
            if value not in allowed:
                problems.append(
                    f"[1C_Rule.md] L{num}: названо {value} инструментов контракта, "
                    f"регистрации дают {sorted(allowed)} — сводка утверждает состояние, "
                    f"которого в коде нет: {line.strip()[:120]}"
                )
    return problems, allowed


def main():
    names = registered_tool_names()
    for fname, tools in names.items():
        print(f"{fname}: зарегистрировано {len(tools)} инструментов")
    registered_all = set()
    for tools in names.values():
        registered_all |= set(tools)
    historical = historical_tool_names()
    print(f"снятых имён инструментов известно: {len(historical)}")

    problems = []
    print("\n=== СЛОИ ПРАВИЛ ↔ РЕГИСТРЫ ===")
    for marker in RL.markers():
        layer_problems, counters = check_layer(marker, names, registered_all, historical)
        problems += layer_problems
        if counters is None:
            print(f"[{marker}] ❌ слой не читается")
            continue
        print(f"[{marker}] карточек {counters['cards']}, вне контракта имён: "
              f"{counters['unknown']}, снятых в живых карточках: {counters['stale']}, "
              f"неназванных инструментов: {counters['missing']}")

    print("\n=== СВОДКА ↔ РЕГИСТРЫ ===")
    router_problems, allowed = check_contract_numbers(names)
    problems += router_problems
    if router_problems:
        print(f"[1C_Rule.md] ❌ расхождений: {len(router_problems)}")
    else:
        print(f"[1C_Rule.md] ✅ числа контракта совпадают с регистрами {sorted(allowed)}")

    print("\n=== ИТОГ ===")
    if problems:
        print(f"❌ РАСХОЖДЕНИЙ: {len(problems)}")
        for p in problems:
            print("   " + p)
        print(
            "\nПорядок исправления: правится исходник слоя docs/rules/<метка>.md (или сводка "
            ".clinerules/1C_Rule.md), затем tools/migrate_rules_to_layer.py --apply, затем "
            "tools/check_rules_layer.py. Правка только строк БД рассинхронизирует слой с "
            "исходником — её ловит проверка слоя."
        )
        return 1
    print("✅ тексты правил совпадают с регистрами инструментов MCP-серверов")
    return 0


if __name__ == "__main__":
    sys.exit(main())




