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
    python tools/check_mcp_tool_wiring.py                # три сервера конфигураций
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

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGETS = [
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
EXPECTED_TOOLS = {
    "server_configurations_core.py": [
        "delete_external_report_tool", "get_load_config_rules_tool", "load_1c_catalog_tool",
        "load_external_object_file_tool",
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
}

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
                        help="файлы для проверки; по умолчанию — три сервера конфигураций")
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

