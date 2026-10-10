import json
import os
import subprocess
from typing import Optional


def parse_psql_output(query, db="configurations"):
    """Execute SQL query and parse results with proper encoding."""
    cmd = [
        r"C:\Postgres\bin\psql.exe",
        "-U", "postgres",
        "-d", db,
        "-h", "localhost",
        "-F", "|",
        "-c", query
    ]
    env = dict(os.environ)
    env["PGPASSWORD"] = "Sta090860"
    # Use stdin to pass query for proper UTF-8 handling on Windows
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    stdout, stderr = proc.communicate(input=query.encode("utf-8"))
    if proc.returncode != 0:
        raise Exception(stderr.decode("cp1251").strip())
    
    lines = stdout.decode("utf-8").split("\n")
    lines = [l for l in lines if l.strip()]
    if len(lines) < 3:
        return []
    
    headers = [h.strip() for h in lines[0].split("|")]
    rows = []
    for line in lines[2:]:
        values = [v.strip() for v in line.split("|")]
        row = {}
        for h, v in zip(headers, values):
            if not v:
                row[h] = None
            elif v.lower() == "t":
                row[h] = True
            elif v.lower() == "f":
                row[h] = False
            else:
                try:
                    row[h] = int(v)
                except ValueError:
                    try:
                        row[h] = float(v)
                    except ValueError:
                        row[h] = v
        rows.append(row)
    return rows


def list_configurations(status=None):
    """List all loaded 1C configurations."""
    query = "SELECT id, name, full_name, vendor, version, uuid, source_path, status, loaded_at FROM configuration"
    if status:
        safe_status = status.replace("'", "''")
        query += f" WHERE status = '{safe_status}'"
    query += " ORDER BY created_at DESC"
    return parse_psql_output(query)


def get_configuration(config_id):
    """Get detailed information about a configuration."""
    query = (f"SELECT id, name, full_name, vendor, version, compatibility_mode, "
             f"script_language, uuid, source_path, dump_file, status, loaded_at "
             f"FROM configuration WHERE id = {config_id}")
    configs = parse_psql_output(query)
    if not configs:
        return {"error": f"Configuration with ID {config_id} not found"}
    
    config = configs[0]
    
    count_query = (f"SELECT type, count(*) as obj_count FROM configuration_objects "
                   f"WHERE configuration_id = {config_id} GROUP BY type ORDER BY obj_count DESC")
    config["objects_by_type"] = parse_psql_output(count_query)
    
    bsl_query = (f"SELECT count(*) as module_count FROM bsl_modules bm "
                 f"JOIN configuration_objects co ON bm.configuration_object_id = co.id "
                 f"WHERE co.configuration_id = {config_id}")
    config["bsl_module_count"] = parse_psql_output(bsl_query)
    
    return config


def search_config_objects(query, config_id=None, object_type=None, limit=50):
    """Search configuration objects by name or description (full-text)."""
    sq = query.replace("'", "''")
    sql = (f"SELECT co.id, co.type, co.name, co.description, "
           f"c.name as config_name, c.full_name as config_full_name "
           f"FROM configuration_objects co "
           f"JOIN configuration c ON co.configuration_id = c.id "
           f"WHERE to_tsvector('russian', COALESCE(co.name, '')) || "
           f"' ' || "
           f"to_tsvector('russian', COALESCE(co.description, '')) @@ "
           f"plainto_tsquery('russian', '{sq}')")
    
    if config_id:
        sql += f" AND co.configuration_id = {config_id}"
    if object_type:
        st = object_type.replace("'", "''")
        sql += f" AND co.type = '{st}'"
    
    sql += (f" ORDER BY ts_rank(to_tsvector('russian', COALESCE(co.name, '')), "
            f"plainto_tsquery('russian', '{sq}')) DESC LIMIT {limit}")
    return parse_psql_output(sql)


def get_object_structure(config_id, object_name):
    """Get full structure of a configuration object."""
    sn = object_name.replace("'", "''")
    
    oq = (f"SELECT co.id, co.type, co.name, co.description, "
          f"c.name as config_name, c.full_name as config_full_name "
          f"FROM configuration_objects co JOIN configuration c ON co.configuration_id = c.id "
          f"WHERE co.configuration_id = {config_id} AND co.name = '{sn}'")
    objects = parse_psql_output(oq)
    
    if not objects:
        return {"error": f"Object '{object_name}' not found in configuration ID={config_id}"}
    
    obj = objects[0]
    oid = obj["id"]
    
    obj["attributes"] = parse_psql_output(
        f"SELECT name, type, ismeasurement, isresource, description "
        f"FROM object_attributes WHERE configuration_object_id = {oid}")
    
    obj["dimensions"] = parse_psql_output(
        f"SELECT name, type, used, isfilter FROM register_dimensions "
        f"WHERE configuration_object_id = {oid}")
    
    obj["resources"] = parse_psql_output(
        f"SELECT name, type, description FROM register_resources "
        f"WHERE configuration_object_id = {oid}")
    
    obj["modules"] = parse_psql_output(
        f"SELECT module_name, file_path, object_type, object_name "
        f"FROM bsl_modules WHERE configuration_object_id = {oid}")
    
    obj["module_codes"] = parse_psql_output(
        f"SELECT module_name, file_path, length(code) as code_length "
        f"FROM bsl_modules WHERE configuration_object_id = {oid}")
    
    return obj


def list_config_objects(config_id, object_type=None):
    """List configuration objects with type filter."""
    sql = (f"SELECT id, type, name, description, created_at "
           f"FROM configuration_objects WHERE configuration_id = {config_id}")
    
    if object_type:
        st = object_type.replace("'", "''")
        sql += f" AND type = '{st}'"
    
    sql += " ORDER BY type, name LIMIT 200"
    return parse_psql_output(sql)


def search_bsl_code(query, config_id=None, limit=20):
    """Search BSL module code (full-text)."""
    sq = query.replace("'", "''")
    
    sql = (f"SELECT bm.module_name, bm.file_path, bm.object_type, bm.object_name, "
           f"co.name as object_config_name, c.name as config_name, "
           f"substring(bm.code, 1, 500) as code_preview, length(bm.code) as code_length, "
           f"ts_rank(to_tsvector('russian', bm.code), plainto_tsquery('russian', '{sq}')) as rank "
           f"FROM bsl_modules bm "
           f"JOIN configuration_objects co ON bm.configuration_object_id = co.id "
           f"JOIN configuration c ON co.configuration_id = c.id "
           f"WHERE to_tsvector('russian', bm.code) @@ plainto_tsquery('russian', '{sq}')")
    
    if config_id:
        sql += f" AND co.configuration_id = {config_id}"
    
    sql += (f" ORDER BY rank DESC LIMIT {limit}")
    return parse_psql_output(sql)


def get_enum_values(config_id, enum_name=None):
    """Get enumeration values."""
    sql = (f"SELECT e.value, e.description, co.name as enum_name, co.id as enum_id "
           f"FROM enum_values e "
           f"JOIN configuration_objects co ON e.configuration_object_id = co.id "
           f"JOIN configuration c ON co.configuration_id = c.id "
           f"WHERE co.configuration_id = {config_id} AND co.type = 'enum'")
    
    if enum_name:
        en = enum_name.replace("'", "''")
        sql += f" AND co.name = '{en}'"
    
    sql += " ORDER BY co.name, e.value LIMIT 500"
    return parse_psql_output(sql)


def register_cross_reference(local_doc_element_id=None, local_doc_snippet_id=None,
                              configuration_id=None, target_object_type=None,
                              target_object_name=None, reference_type=None):
    """Link a local_doc element with a configuration object."""
    if not local_doc_element_id and not local_doc_snippet_id:
        return {"error": "Need to specify local_doc_element_id or local_doc_snippet_id"}
    if not configuration_id or not target_object_name:
        return {"error": "Need to specify configuration_id and target_object_name"}
    
    srt = (reference_type or "linked_to").replace("'", "''")
    stn = target_object_name.replace("'", "''")
    
    sql = (f"INSERT INTO cross_references "
           f"(local_doc_element_id, local_doc_snippet_id, configuration_id, "
           f"target_object_type, target_object_name, cross_reference_type) "
           f"VALUES ({local_doc_element_id}, {local_doc_snippet_id}, {configuration_id}, "
           f"'{target_object_type}', '{stn}', '{srt}') "
           f"RETURNING id, created_at")
    
    return parse_psql_output(sql, db="local_doc")


def get_cross_references(local_doc_element_id=None):
    """Get all links of a local_doc element with configuration objects."""
    sql = (f"SELECT cr.id, cr.local_doc_element_id, cr.configuration_id, "
           f"c.name as config_name, c.full_name as config_full_name, "
           f"cr.target_object_type, cr.target_object_name, "
           f"cr.cross_reference_type, cr.metadata, cr.created_at "
           f"FROM cross_references cr "
           f"JOIN configuration c ON cr.configuration_id = c.id "
           f"WHERE cr.local_doc_element_id = {local_doc_element_id} "
           f"ORDER BY cr.created_at DESC")
    
    return parse_psql_output(sql, db="local_doc")


class ConfigurationsMCPServer:
    """MCP Server for working with configuration database."""
    
    TOOLS = [
        {"name": "list_configurations", 
         "description": "List all loaded 1C configurations. Optional status filter."},
        {"name": "get_configuration", 
         "description": "Get detailed config info including object counts by type."},
        {"name": "search_config_objects", 
         "description": "Search configuration objects by name/description (full-text)."},
        {"name": "get_object_structure", 
         "description": "Get full object structure: attributes, dimensions, resources, modules."},
        {"name": "list_config_objects", 
         "description": "List configuration objects with type filter."},
        {"name": "search_bsl_code", 
         "description": "Search BSL module code (full-text)."},
        {"name": "get_enum_values", 
         "description": "Get enumeration values of a configuration."},
        {"name": "register_cross_reference", 
         "description": "Link local_doc element with configuration object."},
        {"name": "get_cross_references", 
         "description": "Get all links of a local_doc element with config objects."}
    ]
    
    def handle_call(self, tool_name, arguments):
        """Handle tool call."""
        try:
            if tool_name == "list_configurations":
                return list_configurations(status=arguments.get("status"))
            
            elif tool_name == "get_configuration":
                return get_configuration(arguments["config_id"])
            
            elif tool_name == "search_config_objects":
                return search_config_objects(
                    query=arguments["query"],
                    config_id=arguments.get("config_id"),
                    object_type=arguments.get("object_type"),
                    limit=arguments.get("limit", 50)
                )
            
            elif tool_name == "get_object_structure":
                return get_object_structure(
                    config_id=arguments["config_id"],
                    object_name=arguments["object_name"]
                )
            
            elif tool_name == "list_config_objects":
                return list_config_objects(
                    config_id=arguments["config_id"],
                    object_type=arguments.get("object_type")
                )
            
            elif tool_name == "search_bsl_code":
                return search_bsl_code(
                    query=arguments["query"],
                    config_id=arguments.get("config_id"),
                    limit=arguments.get("limit", 20)
                )
            
            elif tool_name == "get_enum_values":
                return get_enum_values(
                    config_id=arguments["config_id"],
                    enum_name=arguments.get("enum_name")
                )
            
            elif tool_name == "register_cross_reference":
                return register_cross_reference(
                    local_doc_element_id=arguments.get("local_doc_element_id"),
                    local_doc_snippet_id=arguments.get("local_doc_snippet_id"),
                    configuration_id=arguments["configuration_id"],
                    target_object_type=arguments.get("target_object_type"),
                    target_object_name=arguments["target_object_name"],
                    reference_type=arguments.get("reference_type")
                )
            
            elif tool_name == "get_cross_references":
                return get_cross_references(
                    local_doc_element_id=arguments["local_doc_element_id"]
                )
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    server = ConfigurationsMCPServer()
    print("Configurations MCP Server started.")
    print(f"Available tools ({len(server.TOOLS)}):")
    for tool in server.TOOLS:
        print(f"  - {tool['name']}: {tool['description']}")
