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
print("\n[1/6] Checking server.py (1c-knowledge-base)...")
try:
    from server import mcp as mcp_kb
    print("  ✅ server.py imported successfully")
except Exception as e:
    print(f"  ❌ server.py failed: {e}")
    sys.exit(1)

# 2. Check server_configurations.py
print("\n[2/6] Checking server_configurations.py (1c-configurations-base)...")
try:
    from server_configurations import mcp as mcp_cfg
    print("  ✅ server_configurations.py imported successfully")
except Exception as e:
    print(f"  ❌ server_configurations.py failed: {e}")
    sys.exit(1)

# 3. Check config_tools.py
print("\n[3/6] Checking config_tools.py...")
try:
    from config_tools import (
        list_configurations,
        get_configuration,
        search_config_objects,
        get_object_structure,
        list_config_objects,
    )
    print(f"  ✅ 5 functions imported: {', '.join(['list_configurations', 'get_configuration', 'search_config_objects', 'get_object_structure', 'list_config_objects'])}")
except Exception as e:
    print(f"  ❌ config_tools.py failed: {e}")
    sys.exit(1)

# 4. Check config_extra.py
print("\n[4/6] Checking config_extra.py...")
try:
    from config_extra import (
        search_bsl_code,
        get_enum_values,
        register_configuration,
        batch_index_from_dump,
        register_cross_reference,
        get_cross_references,
    )
    print(f"  ✅ 6 functions imported: {', '.join(['search_bsl_code', 'get_enum_values', 'register_configuration', 'batch_index_from_dump', 'register_cross_reference', 'get_cross_references'])}")
except Exception as e:
    print(f"  ❌ config_extra.py failed: {e}")
    sys.exit(1)

# 5. Check mcp_tools_api.py and mcp_tools_loader.py
print("\n[5/6] Checking MCP tools...")
try:
    from mcp_tools_api import add_snippet, get_db_state, get_group, search_docs
    from mcp_tools_loader import load_files, load_bsl_docs
    from loader import detect_tags
    print(f"  ✅ 7 functions imported: {', '.join(['add_snippet', 'get_db_state', 'get_group', 'search_docs', 'load_files', 'load_bsl_docs', 'detect_tags'])}")
except Exception as e:
    print(f"  ❌ MCP tools failed: {e}")
    sys.exit(1)

# 6. Check database connections (реальные БД сервера: local_doc и ckb_1c_configurations)
print("\n[6/6] Checking database connections...")
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

# Известный дефект (п. 8 правил .clinerules/1c-configurations-core_Rule.md): модули
# src/config_tools.py, src/config_extra.py, src/config_aliases.py,
# src/config_snippets_manager.py, src/external_processor_loader.py подключаются к базе
# 'configurations', которой на сервере нет. Проверка не считается ошибкой сборки -
# эти модули вне контракта загрузки и будут заменены (docs/CONFIGURATIONS_ENRICHMENT_PLAN.md).
try:
    from config_tools import list_configurations
    if "Найдено" in list_configurations():
        print("  ✅ legacy 'configurations' DB reachable")
    else:
        print("  ⚠️ legacy 'configurations' DB: нет данных (база отсутствует на сервере - дефект п. 8)")
except Exception as e:
    print(f"  ⚠️ legacy 'configurations' DB unreachable (ожидаемо, дефект п. 8 правил): {e}")

# Summary
print("\n" + "=" * 70)
print("VALIDATION SUMMARY")
print("=" * 70)
print("✅ server.py (1c-knowledge-base): imports OK")
print("✅ server_configurations.py (legacy): imports OK")
print("✅ config_tools.py / config_extra.py: imports OK (БД 'configurations' вне контракта)")
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
