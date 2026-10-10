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

    # =====================================================
    # АЛИАСЫ КОНФИГУРАЦИЙ (аналог alias_targets из local_doc)
    # =====================================================

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
    # СНИППЕТЫ КОНФИГУРАЦИЙ (аналог knowledge_snippets из local_doc)
    # =====================================================

    @mcp.tool()
    def add_config_snippet_tool(config_id: int, question: str, answer: str, tags: str = 'bsl,config', confidence: float = 0.9, source_url: str = None):
        """Add snippet for configuration (analog add_snippet from local_doc)."""
        from config_snippets_manager import add_config_snippet as _add_config_snippet
        try:
            result = _add_config_snippet(config_id=config_id, question=question, answer=answer, tags=tags, confidence=confidence, source_url=source_url)
            if result.get('success'):
                return f"Snippet added! ID: {result['snippet_id']}\nAliases created: {result['aliases_created']}"
            return f"Error: {result.get('error')}"
        except Exception as e:
            return f"Error adding snippet: {str(e)}"

    @mcp.tool()
    def list_config_snippets_tool(config_id: int = None):
        """Get list of snippets filtered by configuration."""
        from config_snippets_manager import list_config_snippets as _list_config_snippets
        try:
            result = _list_config_snippets(config_id=config_id)
            if not result or (len(result) == 1 and 'error' in result[0]):
                return f"Error: {result[0].get('error')}"
            if not result:
                return "Snippets not found"
            lines = [f"Configuration snippets ({len(result)} items):"]
            for snippet in result[:30]:
                lines.append(f"  [{snippet['id']}] {snippet['question'][:80]}... | tags: {snippet['tags']}")
            if len(result) > 30:
                lines.append(f"\n... and {len(result) - 30} more snippets")
            return '\n'.join(lines)
        except Exception as e:
            return f"Error listing snippets: {str(e)}"

    @mcp.tool()
    def get_config_snippet_tool(snippet_id: int):
        """Get full snippet by ID."""
        from config_snippets_manager import get_config_snippet as _get_config_snippet
        try:
            result = _get_config_snippet(snippet_id=snippet_id)
            if not result.get('success'):
                return f"Error: {result.get('error')}"
            lines = [f"Snippet #{result['id']}", f"Configuration: {result['config_id']}", f"Question: {result['question'][:200]}", f"Tags: {', '.join(result['tags'])}", f"Confidence: {result['confidence']:.2f}", f"Created: {result['created_at']}", f"Updated: {result['updated_at']}", "", "Answer:", result['answer'][:3000]]
            return '\n'.join(lines)
        except Exception as e:
            return f"Error getting snippet: {str(e)}"

    @mcp.tool()
    def delete_config_snippet_tool(snippet_id: int):
        """Delete snippet (hard-delete, CASCADE removes dependencies)."""
        from config_snippets_manager import delete_config_snippet as _delete_config_snippet
        try:
            result = _delete_config_snippet(snippet_id=snippet_id)
            if result.get('success'):
                return f"Snippet deleted: {result['deleted_question'][:100]}"
            return f"Error: {result.get('error')}"
        except Exception as e:
            return f"Error deleting snippet: {str(e)}"

    @mcp.tool()
    def get_snippets_for_object_tool(config_id: int, target_type: str, target_name: str):
        """Get snippets linked to configuration object (via dependencies)."""
        from config_snippets_manager import get_snippets_for_object as _get_snippets_for_object
        try:
            result = _get_snippets_for_object(config_id=config_id, target_type=target_type, target_name=target_name)
            if not result or (len(result) == 1 and 'error' in result[0]):
                return f"Error: {result[0].get('error')}"
            if not result:
                return f"No snippets for {target_type}:{target_name}"
            lines = [f"Snippets for {target_type}:{target_name} ({len(result)} items):"]
            for snippet in result[:20]:
                lines.append(f"  [{snippet['id']}] {snippet['question'][:80]}... | conf: {snippet['confidence']}")
            if len(result) > 20:
                lines.append(f"\n... and {len(result) - 20} more snippets")
            return '\n'.join(lines)
        except Exception as e:
            return f"Error getting object snippets: {str(e)}"

    @mcp.tool()
    def add_snippet_dependency_tool(snippet_id: int, dependency_type: str, target_type: str, target_name: str):
        """Add snippet dependency on configuration object."""
        from config_snippets_manager import add_snippet_dependency as _add_snippet_dependency
        try:
            result = _add_snippet_dependency(snippet_id=snippet_id, dependency_type=dependency_type, target_type=target_type, target_name=target_name)
            if result.get('success'):
                return "Dependency already exists" if result.get('existing') else f"Dependency added (ID: {result['dependency_id']})"
            return f"Error: {result.get('error')}"
        except Exception as e:
            return f"Error adding dependency: {str(e)}"

    @mcp.tool()
    def update_dependent_snippets_tool(config_id: int, old_target_type: str, old_target_name: str, new_target_type: str, new_target_name: str):
        """Update snippet dependencies on object rename."""
        from config_snippets_manager import update_dependent_snippets as _update_dependent_snippets
        try:
            result = _update_dependent_snippets(config_id=config_id, old_target_type=old_target_type, old_target_name=old_target_name, new_target_type=new_target_type, new_target_name=new_target_name)
            if result.get('success'):
                return f"Updated dependencies: {result['updated_dependencies']}"
            return f"Error: {result.get('error')}"
        except Exception as e:
            return f"Error updating dependencies: {str(e)}"

    @mcp.tool()
    def search_config_snippets_tool(query: str, config_id: int = None):
        """Full-text search across configuration snippets."""
        from config_snippets_manager import search_config_snippets as _search_config_snippets
        try:
            result = _search_config_snippets(query=query, config_id=config_id)
            if not result or (len(result) == 1 and 'error' in result[0]):
                return f"Error: {result[0].get('error')}"
            if not result:
                return "Snippets not found"
            lines = [f"Search snippets: '{query}' ({len(result)} items):"]
            for snippet in result[:20]:
                lines.append(f"  [{snippet['id']}] {snippet['question'][:80]}... | conf: {snippet['confidence']}")
            if len(result) > 20:
                lines.append(f"\n... and {len(result) - 20} more snippets")
            return '\n'.join(lines)
        except Exception as e:
            return f"Error searching snippets: {str(e)}"

    @mcp.tool()
    def get_config_snippet_stats_tool(config_id: int):
        """Get snippet statistics for configuration."""
        from config_snippets_manager import get_config_snippet_stats as _get_config_snippet_stats
        try:
            result = _get_config_snippet_stats(config_id=config_id)
            if 'error' in result:
                return f"Error: {result['error']}"
            lines = [f"Snippet statistics for configuration {config_id}", "", f"  Snippets: {result['snippets_count']}", f"  Dependencies: {result['dependencies_count']}"]
            if result.get('targets_by_type'):
                lines.append("  Targets by type:")
                for target in result['targets_by_type']:
                    lines.append(f"    * {target['target_type']}: {target['object_count']} objects")
            if result.get('tags'):
                lines.append("  Tags:")
                for tag in result['tags'][:10]:
                    lines.append(f"    * {tag['tag']}: {tag['count']}")
            return '\n'.join(lines)
        except Exception as e:
            return f"Error getting stats: {str(e)}"

    # =====================================================
    # ЭКСПОРТ ИЗМЕНЕНИЙ (reverse engineering)
    # =====================================================

    @mcp.tool()
    def export_config_changes_tool(config_id: int, target_path: str):
        """Export configuration changes from DB to files (reverse engineering)."""
        from config_export_manager import export_config_changes as _export_config_changes
        try:
            result = _export_config_changes(config_id=config_id, target_path=target_path)
            if result.get('success'):
                return f"Export completed!\nFile: {result['export_file']}\nObjects: {result['objects_count']}\nSnippets: {result['snippets_count']}"
            return f"Error: {result.get('error')}"
        except Exception as e:
            return f"Error exporting: {str(e)}"

    @mcp.tool()
    def get_export_log_tool(config_id: int = None, limit: int = 20):
        """Get export log."""
        from config_export_manager import get_export_log as _get_export_log
        try:
            result = _get_export_log(config_id=config_id, limit=limit)
            if not result or (len(result) == 1 and 'error' in result[0]):
                return f"Error: {result[0].get('error')}"
            if not result:
                return "Export log is empty"
            lines = [f"Export log ({len(result)} records):"]
            for log in result:
                status_icon = "+" if log['status'] == 'success' else "-"
                lines.append(f"  [{status_icon}] #{log['id']} | {log['config_id']} | {log['objects_count']} obj. | {log['status']} | {log['exported_at']}")
            return '\n'.join(lines)
        except Exception as e:
            return f"Error getting export log: {str(e)}"
