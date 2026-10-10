#!/usr/bin/env python3
"""Новые MCP инструменты для системы сниппетов и алиасов конфигураций.

Заимствована архитектура у documentation server (server.py):
- Aliases: resolve_aliases, add_alias, list_aliases, search_by_alias
- Snippets: add_snippet, list_snippets, get_snippet, delete_snippet, search_snippets
- Export: export_config_changes, get_export_log

Адаптировано для БД configurations и таблицы configuration_aliases.
"""

from fastmcp import FastMCP


def register_new_tools(mcp):
    """Зарегистрировать все новые инструменты в MCP сервере."""

    @mcp.tool()
    def add_config_alias_tool(configuration_id: int, alias_name: str, target_type: str, target_name: str, weight: float = 1.0, description: str = None):
        """Добавить алиас для объекта конфигурации (аналог alias_targets)."""
        from config_aliases import add_alias as _add_alias
        try:
            result = _add_alias(configuration_id=configuration_id, alias_name=alias_name, target_type=target_type, target_name=target_name, weight=weight, description=description)
            if result.get('success'):
                return f"Alias added: {result['alias_name']} (ID: {result['alias_id']})"
            return f"Error: {result.get('error')}"
        except Exception as e:
            return f"Error adding alias: {str(e)}"

    @mcp.tool()
    def list_config_aliases_tool(configuration_id: int = None, target_type: str = None):
        """Get list of aliases with filtering (analog alias_targets)."""
        from config_aliases import list_aliases as _list_aliases
        try:
            result = _list_aliases(configuration_id=configuration_id, target_type=target_type)
            if not result or (len(result) == 1 and 'error' in result[0]):
                return f"Error: {result[0].get('error')}"
            
            if not result:
                return "Aliases not found"
            
            lines = [f"Configuration aliases ({len(result)} items):"]
            for alias in result[:30]:
                active_marker = "+" if alias.get('active') else "-"
                lines.append(f"  [{active_marker}] {alias['alias_name']} -> {alias['target_type']}:{alias['target_name']} (weight: {alias['weight']})")
            
            if len(result) > 30:
                lines.append(f"\n... and {len(result) - 30} more aliases")
            return '\n'.join(lines)
        except Exception as e:
            return f"Error listing aliases: {str(e)}"

    @mcp.tool()
    def get_alias_target_tool(alias_name: str):
        """Get alias target by name (analog resolve_aliases)."""
        from config_aliases import get_alias_target as _get_alias_target
        try:
            result = _get_alias_target(alias_name=alias_name)
            if not result.get('success'):
                return f"Error: {result.get('error')}"
            return f"Alias: {result['alias_name']}\nType: {result['target_type']}\nName: {result['target_name']}\nWeight: {result['weight']}\nDescription: {result.get('description', 'N/A')}"
        except Exception as e:
            return f"Error getting alias target: {str(e)}"

    @mcp.tool()
    def delete_config_alias_tool(alias_id: int):
        """Delete alias (soft-delete, active = false)."""
        from config_aliases import delete_alias as _delete_alias
        try:
            result = _delete_alias(alias_id=alias_id)
            if result.get('success'):
                return f"Alias deleted: {result['deleted_alias']}"
            return f"Error: {result.get('error')}"
        except Exception as e:
            return f"Error deleting alias: {str(e)}"

    @mcp.tool()
    def search_config_by_alias_tool(query: str):
        """Search targets by alias (full-text, analog resolve_aliases)."""
        from config_aliases import search_by_alias as _search_by_alias
        try:
            result = _search_by_alias(query=query)
            if not result.get('success'):
                return f"Error: {result.get('error')}"
            
            lines = [f"Search by alias: '{query}'", f"Aliases found: {result['aliases_count']}", ""]
            if result.get('targets'):
                lines.append("Targets:")
                seen = set()
                for target in result['targets']:
                    key = f"{target['target_type']}:{target['target_name']}"
                    if key not in seen:
                        seen.add(key)
                        lines.append(f"  * {target['target_type']}:{target['target_name']} (weight: {target['weight']})")
            else:
                lines.append("No targets found")
            return '\n'.join(lines)
        except Exception as e:
            return f"Error searching by alias: {str(e)}"

    @mcp.tool()
    def generate_aliases_for_object_tool(configuration_id: int, target_type: str, target_name: str, description: str = None):
        """Generate and add aliases for configuration object (analog generate_bsl_aliases)."""
        from config_aliases import generate_aliases_for_object as _generate_aliases_for_object
        try:
            result = _generate_aliases_for_object(configuration_id=configuration_id, target_type=target_type, target_name=target_name, description=description)
            if 'error' in result:
                return f"Error: {result['error']}"
            
            added = result.get('added', 0)
            aliases = result.get('aliases', [])
            lines = [f"Generated aliases for {target_type}:{target_name}:"]
            if added > 0:
                lines.append(f"  + Added new: {added}")
                for alias in aliases[:15]:
                    lines.append(f"    * {alias}")
                if len(aliases) > 15:
                    lines.append(f"    ... and {len(aliases) - 15} more")
            else:
                lines.append("  i Aliases already exist")
            return '\n'.join(lines)
        except Exception as e:
            return f"Error generating aliases: {str(e)}"

    # =====================================================
    # СНИППЕТЫ КОНФИГУРАЦИЙ (аналог local_doc knowledge_snippets)
    # =====================================================

    @mcp.tool()
    def add_config_snippet_tool(config_id: int, question: str, answer: str, tags: str = "bsl,config", confidence: float = 0.9, source_url: str = None):
        \"\"\"Add snippet for configuration (analog add_snippet from local_doc).\"\"\"
        from config_snippets_manager import add_config_snippet as _add_config_snippet
        try:
            result = _add_config_snippet(config_id=config_id, question=question, answer=answer, tags=tags, confidence=confidence, source_url=source_url)
            if result.get("success"):
                return f"Snippet added! ID: {result[\"snippet_id\"]}\nAliases created: {result[\"aliases_created\"]}"
            return f"Error: {result.get(\"error\")}"
        except Exception as e:
            return f"Error adding snippet: {str(e)}"

