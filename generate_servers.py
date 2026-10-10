#!/usr/bin/env python3
"""Генератор разделённых MCP-серверов."""
import re
from pathlib import Path

SRC = Path('C:/1C_LLM/ckb')
server_file = SRC / 'server_configurations.py'
content = server_file.read_text(encoding='utf-8')

CORE_TOOLS = {'list_configurations_tool', 'get_configuration_tool', 'find_config_by_name_uuid_tool',
    'count_objects_by_config_tool', 'delete_objects_by_config_tool', 'update_configuration_status_tool',
    'analyze_config_load_tool', 'delete_config_tool', 'register_external_processor_tool',
    'register_configuration_tool_v2', 'batch_index_from_dump_tool', 'search_config_objects_tool',
    'get_object_structure_tool', 'list_config_objects_tool', 'get_enum_values_tool',
    'list_bsl_modules_tool', 'get_bsl_module_code_tool', 'search_bsl_code_tool', 'read_config_file_tool'}

ENRICH_TOOLS = {'register_cross_reference_tool', 'get_cross_references_tool',
    'add_config_alias_tool', 'list_config_aliases_tool', 'get_alias_target_tool',
    'delete_config_alias_tool', 'search_config_by_alias_tool', 'generate_aliases_for_object_tool',
    'add_config_snippet_tool', 'list_config_snippets_tool', 'get_config_snippet_tool',
    'delete_config_snippet_tool', 'get_snippets_for_object_tool', 'add_snippet_dependency_tool',
    'update_dependent_snippets_tool', 'search_config_snippets_tool', 'get_config_snippet_stats_tool'}

EXPORT_TOOLS = {'export_config_changes_tool', 'get_export_log_tool',
    'mark_object_modified_tool', 'get_modified_objects_tool',
    'clear_modified_flag_tool', 'count_modified_objects_tool'}

tool_pattern = r'(@mcp\.tool\(\)\ndef ([a-z_]+_tool).*?(?=\n@mcp\.tool\(\)|\Z))'
tools = re.findall(tool_pattern, content, re.DOTALL)
print(f"Найдено: {len(tools)}")

groups = {'core': [], 'enrichment': [], 'export': []}
for code, name in tools:
    if name in CORE_TOOLS: groups['core'].append((name, code))
    elif name in ENRICH_TOOLS: groups['enrichment'].append((name, code))
    elif name in EXPORT_TOOLS: groups['export'].append((name, code))

for n, t in groups.items(): print(f"{n}: {len(t)}")

headers = {
    'core': '#!/usr/bin/env python3\n"""CORE server."""\nimport sys\nfrom pathlib import Path\nsrc_dir = Path(__file__).parent / \'src\'\nsys.path.insert(0, str(src_dir))\nfrom fastmcp import FastMCP\n',
    'enrichment': '#!/usr/bin/env python3\n"""ENRICHMENT server."""\nimport sys\nfrom pathlib import Path\nsrc_dir = Path(__file__).parent / \'src\'\nsys.path.insert(0, str(src_dir))\nfrom fastmcp import FastMCP\n',
    'export': '#!/usr/bin/env python3\n"""EXPORT server."""\nimport sys\nfrom pathlib import Path\nsrc_dir = Path(__file__).parent / \'src\'\nsys.path.insert(0, str(src_dir))\nfrom fastmcp import FastMCP\n'
}

for name, tools_list in groups.items():
    filename = f'server_configurations_{name}.py'
    header = headers[name]
    tool_codes = [c for n, c in tools_list]
    full = header + '\n\n' + '\n\n'.join(tool_codes) + '\n\ndef main():\n    mcp.run()\n\nif __name__ == "__main__":\n    main()\n'
    (SRC / filename).write_text(full, encoding='utf-8')
    print(f"Created: {filename} ({len(tools_list)} tools)")
