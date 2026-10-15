#!/usr/bin/env python3
"""Final validation of the 1C Knowledge Base project."""
import sys
import io
from pathlib import Path

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent / 'src'))

print("=" * 70)
print("1C KNOWLEDGE BASE - PROJECT VALIDATION")
print("=" * 70)

# 1. Check server.py
print("\n[1/7] Checking server.py (1c-knowledge-base)...")
try:
    from server import mcp as mcp_kb
    print("  ✅ server.py imported successfully")
except Exception as e:
    print(f"  ❌ server.py failed: {e}")
    sys.exit(1)

# 2. Проверка «проводки» MCP-инструментов серверов конфигураций (AST, без импорта модулей).
#    Заменило проверку устаревшего server_configurations.py: тот обращается к базе
#    'configurations', которой на сервере нет, и больше не является точкой входа.
#    Смысл проверки: сгенерированные generate_servers.py серверы теряли импорты из src/, и
#    инструменты падали NameError ещё до обращения к БД (замер 13.10.2026: 17/17 и 6/6).
print("\n[2/7] Checking MCP tool wiring (core/enrichment/export servers)...")
try:
    sys.path.insert(0, str(Path(__file__).parent / 'tools'))
    from check_mcp_tool_wiring import DEFAULT_TARGETS, check_file
    wiring_reports = [check_file(path) for path in DEFAULT_TARGETS]
    bad = [r for r in wiring_reports if r["error"] or r["unresolved"]]
    for rep in wiring_reports:
        name = Path(rep["path"]).name
        if rep["error"]:
            print(f"  ❌ {name}: {rep['error']}")
        elif rep["unresolved"]:
            print(f"  ❌ {name}: инструментов {rep['tools']}, нерешённых имён {len(rep['unresolved'])}")
            for item in rep["unresolved"]:
                print(f"       {item['tool']}() строка {item['line']}: {item['name']}()")
        else:
            print(f"  ✅ {name}: инструментов {rep['tools']}, нерешённых имён 0")
    if bad:
        sys.exit(1)
except SystemExit:
    raise
except Exception as e:
    print(f"  ❌ проверка проводки не выполнена: {e}")
    sys.exit(1)

# 3. Живые модули подсистемы: загрузка и обогащение (единственный работающий код).
#    Заменило проверку src/config_tools.py и src/config_extra.py: оба обращались к базе
#    `configurations`, которой на сервере нет, и к таблицам, которых в схеме нет
#    (дефект п. 8 правил .clinerules/1c-configurations-core_Rule.md). Модули удалены 14.10.2026
#    вместе с остальным мёртвым кодом той же эпохи (см. docs/config-scenarios/TOOLS_REVISION_2026-10-13.md).
print("\n[3/7] Checking live loader/enrichment modules...")
try:
    from config_load_router import load_catalog, format_load_result
    from external_report_loader import delete_external_object, read_external_meta
    # узел V25: мост к ibcmd проверяется как живой модуль подсистемы загрузки (импорт без
    # побочных эффектов: ibcmd ищется только в момент вызова).
    from config_load_router import format_binary_load_result
    from ibcmd_bridge import (find_ibcmd, ensure_infobase, load_configuration, export_to_layout,
                              import_from_layout, convert_and_load)
    from enrichment_generator import (generate_enrichment, describe_object, type_brief,
                                     build_object_aliases, build_snippets)
    from enrichment_aliases import (add_config_aliases, search_config_aliases,
                                   resolve_config_alias, list_config_aliases, delete_config_alias)
    from enrichment_snippets import (add_config_snippet, get_config_snippet, list_config_snippets,
                                    search_config_snippets, delete_config_snippet,
                                    get_snippets_for_object, enrichment_stats)
    print("  ✅ загрузка: config_load_router, external_report_loader")
    print("  ✅ разбор бинарных .erf/.epf: ibcmd_bridge + format_binary_load_result")
    print("  ✅ обогащение: generator (generate_enrichment, describe_object), aliases, snippets")
except Exception as e:
    print(f"  ❌ живые модули не импортируются: {e}")
    sys.exit(1)

# 4. Состав инструментов контракта (core 4 / enrichment 18 / export 1) — по разбору шага 2.
#    Лишний инструмент = возврат к неработающим вызовам; недостающий = потерянный контракт.
#    Числа в итоговой строке печатаются из EXPECTED_TOOLS, а не из этой строки-комментария.
print("\n[4/7] Checking MCP tool contract (core/enrichment/export)...")
try:
    from check_mcp_tool_wiring import EXPECTED_TOOLS
    for rep in wiring_reports:
        name = Path(rep["path"]).name
        expected = EXPECTED_TOOLS.get(name)
        if expected is None:
            print(f"  ⚠️ {name}: контракт не задан (проверка только на разрешимость имён)")
            continue
        if rep["missing"] or rep["extra"]:
            print(f"  ❌ {name}: ожидалось {len(expected)}, есть {rep['tools']}")
            if rep["missing"]:
                print(f"       нет: {', '.join(rep['missing'])}")
            if rep["extra"]:
                print(f"       вне контракта: {', '.join(rep['extra'])}")
            sys.exit(1)
        print(f"  ✅ {name}: {len(expected)} инструментов контракта на месте")
except SystemExit:
    raise
except Exception as e:
    print(f"  ❌ контракт не проверен: {e}")
    sys.exit(1)

# 5. Check mcp_tools_api.py and mcp_tools_loader.py
print("\n[5/7] Checking MCP tools...")
try:
    from mcp_tools_api import add_snippet, get_db_state, get_group, search_docs
    from mcp_tools_loader import load_files, load_bsl_docs
    from loader import detect_tags
    print(f"  ✅ 7 functions imported: {', '.join(['add_snippet', 'get_db_state', 'get_group', 'search_docs', 'load_files', 'load_bsl_docs', 'detect_tags'])}")
except Exception as e:
    print(f"  ❌ MCP tools failed: {e}")
    sys.exit(1)

# 6. Check database connections (реальные БД сервера: local_doc и ckb_1c_configurations)
print("\n[6/7] Checking database connections...")
try:
    from mcp_tools_api import get_db_state
    state = get_db_state()
    print(f"  ✅ local_doc DB connected: groups={state.get('groups', 0)}, snippets={state.get('snippets', 0)}, aliases={state.get('aliases', 0)}")
except Exception as e:
    print(f"  ❌ local_doc DB connection failed: {e}")
    sys.exit(1)

try:
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    from external_db import connect as config_connect
    with config_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT (SELECT count(*) FROM external_report), "
                "(SELECT count(*) FROM forms), (SELECT count(*) FROM bsl_modules)"
            )
            reports, forms, modules = cur.fetchone()
    print(f"  ✅ ckb_1c_configurations DB connected: external_report={reports}, "
          f"forms={forms}, bsl_modules={modules}")
except Exception as e:
    print(f"  ❌ ckb_1c_configurations DB connection failed: {e}")
    sys.exit(1)

# Мёртвый код, обращавшийся к базе `configurations` (её на сервере нет: есть
# ckb_1c_configurations и local_doc), удалён 14.10.2026: config_tools, config_extra,
# config_aliases, config_snippets_manager, external_processor_loader, config_change_tracker,
# config_export_manager, config_migration, старые server_configurations*.py, generate_servers.py.
# Проверка держит это состояние: если такой код вернётся, он снова упадёт на FATAL в рантайме,
# и поймать это дешевле здесь, чем живим вызовом MCP.
print("\n[7/7] Checking that no code targets the absent DB 'configurations'...")
try:
    root = Path(__file__).parent
    dead_markers = ("dbname='configurations'", 'dbname="configurations"',
                    '"-d", "configurations"', "'-d', 'configurations'")
    hits = []
    for directory in (root, root / "src", root / "tools"):
        for python_file in sorted(directory.glob("*.py")):
            if python_file.name == Path(__file__).name:
                continue          # собственные маркеры поиска не считаем
            text = python_file.read_text(encoding="utf-8", errors="replace")
            if any(marker in text for marker in dead_markers):
                hits.append(python_file.name)
    if hits:
        print(f"  ❌ код снова обращается к базе 'configurations': {', '.join(hits)}")
        sys.exit(1)
    print("  ✅ ни один модуль не подключается к базе 'configurations' (мёртвый код удалён)")
except SystemExit:
    raise
except Exception as e:
    print(f"  ❌ проверка не выполнена: {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 70)
print("VALIDATION SUMMARY")
print("=" * 70)
print("✅ server.py (1c-knowledge-base): imports OK")
print("✅ MCP-проводка серверов конфигураций (core/enrichment/export): нерешённых имён нет")
_contract = ", ".join(
    f"{name[len('server_configurations_'):-3]} {len(tools)}"
    for name, tools in sorted(EXPECTED_TOOLS.items())
)
print(f"✅ состав инструментов совпадает с контрактом ({_contract})")
print("✅ живые модули загрузки (config_load_router, external_report_loader) и обогащения "
      "(generator/aliases/snippets): imports OK")
print("✅ мёртвый код базы 'configurations' удалён, повторных обращений нет")
print("✅ mcp_tools_api.py + mcp_tools_loader.py + loader.py: imports OK")
print("✅ local_doc DB: connected")
print("✅ ckb_1c_configurations DB: connected (загрузчик внешних объектов)")
print("\n📁 Project structure:")
project_root = Path(__file__).parent
for item in sorted(project_root.iterdir()):
    if item.is_file() and item.suffix in ['.py', '.md']:
        print(f"   {item.name}")
for item in sorted((project_root / 'src').iterdir()):
    if item.is_file() and item.suffix == '.py':
        print(f"   src/{item.name}")

print("\n✅ ALL VALIDATIONS PASSED!")
print("=" * 70)
