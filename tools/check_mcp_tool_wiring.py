#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Статическая проверка «проводки» MCP-инструментов: каждый вызов внутри @mcp.tool() разрешим.

Зачем: `server_configurations_enrichment.py` и `server_configurations_export.py` были
сгенерированы `generate_servers.py`, который пишет шапку только с `sys/pathlib/fastmcp` и
теряет блок импортов из `src/`. В итоге 17/17 и 6/6 инструментов падали на NameError ещё до
обращения к БД (замер 13.10.2026). Проверка ловит тот же класс дефектов до запуска сервера:
AST-разбором собираются имена, вызываемые внутри инструментов, и сверяютcя с тем, что модуль
действительно определяет или импортирует.

Что проверяется (только статика, файлы НЕ импортируются — stdio-транспорт не поднимается):
  1. кто объявлен инструментом (`@mcp.tool()` или `@mcp.tool`);
  2. какие имена вызываются внутри инструментов;
  3. разрешается ли каждое имя: модульные def/class/присваивания/импорты, аргументы и
     локальные привязки самого инструмента, встроенные имена Python.

Код возврата 0 — нерешённых имён нет; 1 — есть (печатаются имя и строка вызова).

Запуск:
    python tools/check_mcp_tool_wiring.py                # knowledge-base + три сервера конфигураций
    python tools/check_mcp_tool_wiring.py server.py      # любой список файлов
    python tools/check_mcp_tool_wiring.py --json         # машиночитаемый вывод

Норматив: docs/config-scenarios/TOOLS_REVISION_2026-10-13.md (п. 2: не запускать
generate_servers.py, пока он не сохраняет импорты).
"""
from __future__ import annotations

import argparse
import ast
import builtins
import json
import sys
from pathlib import Path

try:  # кириллица и служебные символы вывода (❌, ↔) не влазят в cp1251: без этого провал
      # проверки печатается исключением UnicodeEncodeError вместо перечня расхождений —
      # дефект оказывался незаметен (замер 27.10.2026). Приём тот же, что в
      # tools/check_rules_layer.py и tools/check_search_rules_sync.py
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # сбой настройки потока не имеет права менять итог проверки
    pass


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGETS = [
    ROOT / "server.py",
    ROOT / "server_configurations_core.py",
    ROOT / "server_configurations_enrichment.py",
    ROOT / "server_configurations_export.py",
]

# Контракт инструментов (зафиксирован: core — 4, enrichment — 21, export — 1; норматив
# docs/config-scenarios/FLOWCHART_1c-configurations-core.md и docs/CONFIGURATIONS_ENRICHMENT_PLAN.md).
# Проверка нужна потому, что в серверах уже лежали 18 и 6 инструментов вне контракта, которые
# обращались к базе `configurations` и таблицам, которых в схеме нет: они падали на FATAL,
# TypeError или NameError. Лишний инструмент = регрессия контракта; недостающий = потерянный.
# Узел B (макеты СКД) добавил get_config_template_tool: 16 → 17.
# Узел V20.2 (привязка к конфигурации) добавил set_object_configuration_tool: 17 → 18 —
# решение оператора 14.10.2026, тем же решением из схемы снят FK на configurations(id).
# Узел V25 (бинарные .erf/.epf) добавил load_external_object_file_tool: core 3 → 4.
# Узел Q1 (карантин сниппетов, 16.10.2026) добавил в enrichment mark_config_snippet_tool,
# unmark_config_snippet_tool, list_marked_config_snippets_tool: 18 → 21. Схема БД при этом
# не менялась: пометка живёт тегом в tags (раздел 14 docs/CONFIGURATIONS_ENRICHMENT_PLAN.md).
# Точка входа загрузки каталога при этом не меняется: новый инструмент только готовит
# каталог выгрузки и вызывает тот же load_catalog (docs/CONFIGURATIONS_ENRICHMENT_PLAN.md,
# раздел 13.7).
# Узел V44 (22.10.2026) добавил load_configuration_root_modules_tool: core 4 → 5. Отдельная
# точка входа нужна потому, что модули предопределённых программ корня имеют ДВА источника
# (файлы Ext/<вид>.bsl и запись индекса состава), и оба обязаны сходиться со строкой таблицы;
# вызывать загрузчик приходится, не пересоздавая заголовок конфигурации force=True (M7 снимает
# историю состояний, а id заголовка при этом меняется).
# Узел RULE-LAYER (24.10.2026) снял get_load_config_rules_tool: core 5 → 4. Правила загрузки
# читаются слоем `core-rules:` адресно, а не вызовом, который отдаёт LOAD_RULES_Config.md
# целиком; снятое имя добавлено в DELETED_TOOLS, чтобы тексты правил называли его снятым,
# а не живым. Тот же узел снял в knowledge-base get_load_rules_tool и get_search_rules_tool:
# контракт 17 → 15 — держать их здесь нельзя, потому что проверка требовала бы инструмента,
# который правила слоя называют снятым (замер 27.10.2026: сервер даёт 15, список требовал 17 —
# провал «нет инструментов контракта: get_load_rules_tool, get_search_rules_tool»).
# Узел V46 (П5, 28.10.2026) добавил load_configuration_object_properties_tool: core 4 → 5.
# Отдельная точка входа нужна по той же причине, что у V44: свойства подсистем и общих
# модулей меняются вместе с файлами регистрации, а заголовок и индекс состава при этом не
# меняются — пересоздавать конфигурацию force=True ради них значило бы снять историю
# состояний (M7). Стадия S4 конвейера вызывает тот же слой, поэтому отдельного контракта у
# инструмента нет: закрытый словарь и текст даёт configuration_load_contract.
# Узел V48 (П5, 29.10.2026) добавил load_session_parameters_tool: core 5 → 6. Причина та же
# (решение оператора Q5.2 — свой вход на каждую позицию нормативного списка): файлы
# регистрации параметров сеанса меняются, а заголовок и индекс состава — нет. Стадия S4c
# конвейера и инструмент вызывают одну и ту же функцию слоя
# (src/configuration_session_parameters_loader.load_session_parameters); отдельного
# контракта у инструмента нет — закрытый словарь session_parameters_defaults() и текст
# раздела даёт configuration_load_contract.
# Узел V49 (П5, 30.10.2026) добавил load_roles_tool: core 6 → 7. Причина та же (решение
# оператора Q5 узла V48 — свой вход на каждую позицию нормативного списка): файлы вида
# `Roles/` меняются, а заголовок и индекс состава — нет. Стадия S4d конвейера и инструмент
# вызывают одну и ту же функцию слоя (src/configuration_roles_loader.load_roles); отдельного
# контракта у инструмента нет — закрытый словарь roles_defaults() и текст раздела даёт
# configuration_load_contract. Отличие от входов V44/V46/V48 — параметр `kinds` (три группы
# круга): FK `role_rights_role_id_fkey` с `ON DELETE CASCADE` не даёт писать роли без их
# прав, поэтому круг разрезан по границе внешних ключей, а не по удобству.
# Узел V50 (П5, 31.10.2026) добавил load_common_attributes_tool: core 7 → 8. Причина та же
# (решение оператора Q5 узла V48 — свой вход на каждую позицию нормативного списка): файлы
# регистрации вида `CommonAttributes/` (позиция 2.5) меняются, а заголовок и индекс состава —
# нет. Стадия S4e конвейера и инструмент вызывают одну и ту же функцию слоя
# (src/configuration_common_attributes_loader.load_common_attributes); отдельного контракта у
# инструмента нет — закрытый словарь common_attributes_defaults() и текст раздела даёт
# configuration_load_contract. Отличие от входа V49 — групп `kinds` нет (решение Q10,
# вариант A): строка применения существует только через числовой id строки реквизита (Q1,
# вариант A), поэтому частичная запись круга описывала бы состав, которого в выгрузке нет.
# Узел V51 (П5, 31.10.2026) добавил load_exchange_plans_tool: core 8 → 9. Причина та же
# (решение оператора Q5 узла V48 — свой вход на каждую позицию нормативного списка): файлы
# регистрации вида `ExchangePlans/` (позиция 2.6) меняются, а заголовок и индекс состава —
# нет. Стадия S4f конвейера и инструмент вызывают одну и ту же функцию слоя
# (src/configuration_exchange_plans_loader.load_exchange_plans); отдельного контракта у
# инструмента нет — закрытый словарь exchange_plans_defaults() и текст раздела даёт
# configuration_load_contract. Отличие от входа V50 — группы `kinds` есть (решение Q5 узла
# V51, раздел 5.4 плана): круг вида несимметричен по цене (46 строк свойств против 22 515
# строк перечня `<Content>` и 33.2 МБ текстов макетов), а риск V50 отсутствует физически —
# перечни детей выводятся из атрибутов uuid выгрузки, а не из записанных строк детей.
EXPECTED_TOOLS = {
    "server_configurations_core.py": [
        "delete_external_report_tool", "load_1c_catalog_tool",
        "load_common_attributes_tool",
        "load_configuration_object_properties_tool",
        "load_configuration_root_modules_tool", "load_external_object_file_tool",
        "load_exchange_plans_tool",
        "load_roles_tool", "load_session_parameters_tool",
    ],
    "server_configurations_enrichment.py": [
        "add_config_aliases_tool", "add_config_cross_reference_tool", "add_config_snippet_tool",
        "config_enrichment_stats_tool", "delete_config_alias_tool",
        "delete_config_cross_reference_tool", "delete_config_snippet_tool",
        "generate_config_enrichment_tool", "get_config_cross_references_tool",
        "get_config_snippet_tool", "get_config_snippets_for_object_tool",
        "get_config_template_tool",
        "list_config_aliases_tool", "list_config_snippets_tool", "list_marked_config_snippets_tool",
        "mark_config_snippet_tool", "resolve_config_alias_tool",
        "search_config_aliases_tool", "search_config_snippets_tool",
        "set_object_configuration_tool", "unmark_config_snippet_tool",
    ],
    "server_configurations_export.py": ["export_readiness_tool"],
    # Узел 20.10.2026: knowledge-base добавлен в сверку, потому что текст правил поиска
    # (`SEARCH_RULES.md`, который отдавал снятый `get_search_rules_tool`) перечислял инструменты,
    # которых в сервере нет, и молчал об тех, что есть (карантин узла Q1, инструменты правил).
    # Пока `server.py` не входил в EXPECTED_TOOLS, класс дефекта «правило обещает инструмент,
    # которого нет» не ловился ничем.
    # Узел P6 (20.10.2026) добавил get_snippet_tool и update_snippet_tool: 15 → 17. Причина
    # не в удобстве: содержимое сниппета по ID не читалось ни одним инструментом контракта
    # (вывод строился по превью в 200 символов), а «исправить знание» было можно только новой
    # строкой — в базе оставались два противоречащих знания, и поиск отдавал обе.
    # Узел RULE-LAYER (24.10.2026) снял get_load_rules_tool и get_search_rules_tool: 17 → 15.
    # Их имена — в DELETED_TOOLS ниже, поэтому в контракте их быть не может: список требовал
    # инструмента, который правила слоя называют снятым (замер 27.10.2026 — провал «нет
    # инструментов контракта»). Состав — 15 инструментов регистра `server.py`.
    "server.py": [
        "add_aliases_tool", "add_snippet_tool", "detect_tags_tool", "get_db_state_tool",
        "get_doc_tool", "get_snippet_tool", "list_categories_tool", "list_marked_snippets_tool",
        "load_bsl_tool", "load_doc_tool", "load_single_html_tool",
        "mark_snippet_for_deletion_tool", "search_docs_tool",
        "unmark_snippet_for_deletion_tool", "update_snippet_tool",
    ],
}

# Снятые имена инструментов (14.10.2026): шесть инструментов export-сервера, которые
# падали NameError, потому что их функции-источники в монолите server_configurations.py
# отсутствовали, а таблиц `modified_objects` / `config_export_log` в схеме нет. Список живёт
# здесь, а не в tools/check_search_rules_sync.py: тексты правил обязаны называть снятый
# инструмент как снятый (история), но не как живой, и для этого нужен один список на оба
# скрипта. Возвращать эти имена в регистры нельзя — их отсутствие сторожит EXPECTED_TOOLS.
# Узел RULE-LAYER (24.10.2026) добавил три имени чтения правил: get_load_rules_tool и
# get_search_rules_tool (knowledge-base) и get_load_config_rules_tool (core). Причина удаления
# не в том, что они падали (после переезда нормативов в docs/rules/ они как раз падали), а в
# том, что вызов «отдай весь файл правил» обходит и категорию, и двухфазное чтение, то есть
# противоречит организации правил слоем. Имена остались здесь намеренно: тексты правил обязаны
# упоминать их как снятые (история), но живая карточка состояния always/optional/checks назвать
# их не вправе — это сторожит tools/check_search_rules_sync.py.
DELETED_TOOLS = [
    # --- узел RULE-LAYER (24.10.2026): инструменты чтения правил ---
    "get_load_config_rules_tool",
    "get_load_rules_tool",
    "get_search_rules_tool",
    # --- прежний export-сервер (14.10.2026): функции-источники отсутствовали ---
    "clear_modified_flag_tool",
    "count_modified_objects_tool",
    "export_config_changes_tool",
    "get_export_log_tool",
    "get_modified_objects_tool",
    "mark_object_modified_tool",
    # --- узел П2-Ф-8 (29.10.2026): сюда перенесён REMOVED_SERVER_TOOLS из
    # tools/check_search_rules_sync.py. Комментарий того файла требовал один список на два
    # скрипта, а держались два; измеритель `_journal_code_history.py` сверялся только с этим,
    # поэтому 8 имён прежнего состава enrichment-сервера (сняты 14.10.2026 коммитом a71e7b0d,
    # узлы V17-V20.1) были для него «вне DELETED_TOOLS», хотя для правил они уже числились
    # снятыми. Два списка одних имён — это и есть причина, по которой Ф-8 выглядел несделанным.
    # Пары «прежнее имя → чем заменено» — узел `rules:enrich-rules:journal:node:naming-2026-10`.
    "add_config_alias_tool",           # → add_config_aliases_tool (ед. ч. → мн. ч.)
    "add_snippet_dependency_tool",     # → add_config_snippet_tool(dependencies=…)
    "analyze_config_load_tool",
    "batch_index_from_dump_tool",
    "count_objects_by_config_tool",
    "delete_config_tool",
    "delete_objects_by_config_tool",
    "find_config_by_name_uuid_tool",
    "generate_aliases_for_object_tool",  # → generate_config_enrichment_tool
    "get_alias_target_tool",           # → resolve_config_alias_tool
    "get_bsl_module_code_tool",
    "get_config_snippet_stats_tool",   # → config_enrichment_stats_tool
    "get_configuration_tool",
    "get_cross_references_tool",       # → get_config_cross_references_tool
    "get_enum_values_tool",
    "get_object_structure_tool",
    "get_snippets_for_object_tool",    # → get_config_snippets_for_object_tool
    "list_bsl_modules_tool",
    "list_config_objects_tool",
    "list_configurations_tool",
    "read_config_file_tool",
    "register_cross_reference_tool",
    "register_external_report_tool",
    "search_bsl_code_tool",
    "search_config_by_alias_tool",     # → search_config_aliases_tool
    "search_config_objects_tool",
    "update_configuration_status_tool",
    "update_dependent_snippets_tool",  # → generate_config_enrichment_tool
    # --- узел П2-Ф-8: две прежние модели knowledge-base (`server.py`), которых ни один
    # список не помнил. Модель «фрагментов» добавлена 30.09.2026 (207185f3), снята
    # 02.10.2026 (342a213f) при переходе к группам и сниппетам; модель «элементов/групп»
    # добавлена 02.10.2026 (8424a735), снята 07.10.2026 (e043843a) при переходе к
    # комбинированному поиску. Узлы журнала: `rules:kb-rules:journal:node:fragments-2026-09`
    # и `rules:kb-rules:journal:node:elements-2026-10`. Возвращать эти имена в регистр нельзя:
    # теперешний состав сторожит EXPECTED_TOOLS. ---
    "search_fragments_tool",
    "get_fragment_by_name_tool",
    "get_import_log_tool",
    "import_html_files_tool",
    "import_markdown_files_tool",
    "detect_category_tool",
    "fix_snippet_tool",                # → update_snippet_tool (появился 20.10.2026, узел P6)
    "load_from_folder_tool",
    "load_from_url_tool",
    "create_element_tool",
    "update_element_tool",
    "create_group_tool",
    "update_group_tool",
    "search_elements_tool",
    "search_groups_tool",
    "search_snippets_tool",            # → search_docs_tool (добавлен тем же коммитом)
    "get_element_details_tool",
    "get_group_hierarchy_tool",
]

BUILTIN_NAMES = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__package__", "__spec__", "__loader__",
    "__builtins__", "__debug__", "__path__", "mcp",
}


def _target_names(node):
    """Имена, которые связывает присваивание / цель for / и т.п."""
    names = set()
    if isinstance(node, ast.Name):
        names.add(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for elt in node.elts:
            names |= _target_names(elt)
    elif isinstance(node, ast.Starred):
        names |= _target_names(node.value)
    return names


def _binding_names(tree):
    """Имена верхнего уровня модуля: def/class/присваивания/импорты/global."""
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                names |= _target_names(target)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Global):
            names.update(node.names)
    return names


def _local_names(func):
    """Имена, доступные внутри тела функции: параметры и локальные привязки."""
    names = set()
    args = func.args
    for group in (args.posonlyargs, args.args, args.kwonlyargs):
        names.update(a.arg for a in group)
    for field in ("vararg", "kwarg"):
        if getattr(args, field, None):
            names.add(getattr(args, field).arg)
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                names |= _target_names(target)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            names |= _target_names(node.target)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            names |= _target_names(node.target)
        elif isinstance(node, ast.comprehension):
            names |= _target_names(node.target)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            names |= _target_names(node.optional_vars)
        elif isinstance(node, ast.NamedExpr):
            names |= _target_names(node.target)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
    return names


def _is_tool_decorator(dec):
    """`@mcp.tool()` или `@mcp.tool` (в том числе `@mcp.tool(name=...)`)."""
    target = dec.func if isinstance(dec, ast.Call) else dec
    if not isinstance(target, ast.Attribute) or target.attr != "tool":
        return False
    owner = target.value
    return isinstance(owner, ast.Name) and owner.id == "mcp"


def _tool_functions(tree):
    tools = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(_is_tool_decorator(dec) for dec in node.decorator_list):
                tools.append(node)
    return tools


def check_file(path):
    """Разобрать файл: число инструментов, их имена, нерешённые вызовы и сверка контракта."""
    path = Path(path)
    report = {"path": str(path), "tools": 0, "tool_names": [], "missing": [], "extra": [],
              "unresolved": [], "error": None}
    if not path.is_file():
        report["error"] = "файл не найден"
        return report
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        report["error"] = f"не разбирается: {exc}"
        return report

    module_names = _binding_names(tree)
    tools = _tool_functions(tree)
    report["tools"] = len(tools)
    names = sorted(tool.name for tool in tools)
    report["tool_names"] = names
    expected = EXPECTED_TOOLS.get(path.name)
    if expected is not None:
        report["missing"] = [name for name in expected if name not in names]
        report["extra"] = [name for name in names if name not in expected]

    seen = set()
    for tool in tools:
        local = _local_names(tool)
        for node in ast.walk(tool):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue  # вызовы методов (obj.method()) не проверяем
            name = node.func.id
            if name in module_names or name in local or name in BUILTIN_NAMES:
                continue
            key = (tool.name, name, node.lineno)
            if key in seen:
                continue
            seen.add(key)
            report["unresolved"].append({"tool": tool.name, "name": name,
                                         "line": node.lineno, "col": node.col_offset + 1})
    report["unresolved"].sort(key=lambda item: (item["tool"], item["line"]))
    return report


def _rel(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _bad(report):
    """Провалом считается ошибка разбора, нерешённое имя и любое расхождение контракта."""
    return bool(report["error"] or report["unresolved"] or report["missing"] or report["extra"])


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Проверка разрешимости имён внутри @mcp.tool() и состава контракта (AST, модули не импортируются)")
    parser.add_argument("paths", nargs="*",
                        help="файлы для проверки; по умолчанию — knowledge-base и три сервера конфигураций")
    parser.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    args = parser.parse_args(argv)

    targets = [Path(p) for p in args.paths] or DEFAULT_TARGETS
    reports = [check_file(p) for p in targets]

    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        print("Проверка проводки и контракта MCP-инструментов (AST-разбор, модули не импортируются)")
        print("=" * 70)
        for rep in reports:
            name = _rel(rep["path"])
            if rep["error"]:
                print(f"❌ {name}: {rep['error']}")
                continue
            problems = []
            if rep["unresolved"]:
                problems.append(f"нерешённых имён {len(rep['unresolved'])}")
                for item in rep["unresolved"]:
                    problems.append(f"     {item['tool']}() строка {item['line']}: вызов не определённого "
                                    f"имени {item['name']}()")
            if rep["missing"]:
                problems.append("нет инструментов контракта: " + ", ".join(rep["missing"]))
            if rep["extra"]:
                problems.append("инструменты вне контракта: " + ", ".join(rep["extra"]))
            if problems:
                print(f"❌ {name}: инструментов {rep['tools']}")
                print("\n".join(problems))
            else:
                expected = EXPECTED_TOOLS.get(Path(rep["path"]).name)
                note = f", контракт совпадает ({len(expected)})" if expected is not None else ""
                print(f"✅ {name}: инструментов {rep['tools']}, нерешённых имён 0{note}")
        print("=" * 70)
        if any(_bad(r) for r in reports):
            print("❌ Есть расхождения. Типовые причины — потерянный блок импортов из src/ "
                  "или инструмент вне контракта (см. EXPECTED_TOOLS).")
        else:
            print("✅ Все вызовы разрешимы, состав инструментов совпадает с контрактом.")
    return 1 if any(_bad(r) for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())

