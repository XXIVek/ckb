#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loader for external reports/processing (ERF/EPF) in ckb_1c_configurations."""
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def _run_psql(query, db="ckb_1c_configurations"):
    """Execute SQL query on ckb_1c_configurations database."""
    cmd = [r"C:\Postgres\bin\psql.exe", "-U", "postgres", "-d", db, "-h", "localhost", "-tA"]
    env = dict(os.environ)
    env["PGPASSWORD"] = "Sta090860"
    env["PGCLIENTENCODING"] = "UTF8"
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    stdout, stderr = proc.communicate(input=query.encode("utf-8"))
    if proc.returncode != 0:
        err_msg = stderr.decode("cp1251").strip() if stderr else "Unknown error"
        return {"error": f"PSQL error: {err_msg}"}
    
    if not stdout or not stdout.strip():
        return []
    
    lines = [l for l in stdout.decode("utf-8").split("\n") if l.strip()]
    if not lines:
        return []
    try:
        val = int(lines[0])
        return [{"result": val}]
    except ValueError:
        pass
    headers = [h.strip() for h in lines[0].split("|")]
    rows = []
    for line in lines[1:]:
        s = line.strip()
        if not s or s.startswith("CREATE") or s.startswith("SELECT"):
            continue
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


def _extract_text(element, tag, ns=None):
    """Extract text from XML element by tag name."""
    if ns is None:
        ns = {'md': 'http://v8.1c.ru/8.3/MDClasses'}
    child = element.find(f'.//{ns["md"]}:{tag}', ns) if ns else element.find(f'.//{{http://v8.1c.ru/8.3/MDClasses}}{tag}')
    if child is None:
        return ''
    text = child.text
    if not text:
        for sub in child:
            if 'content' in sub.tag.lower() and sub.text:
                text = sub.text
                break
    return (text or '').strip()


def _parse_child_objects(root, ns):
    """Parse ChildObjects from ExternalReport/ExternalDataProcessor."""
    attributes = []
    tabular_sections = []
    forms = []
    templates = []
    
    child_objects = root.find('.//md:ChildObjects', ns)
    if child_objects is None:
        return attributes, tabular_sections, forms, templates
    
    for obj in child_objects:
        tag_name = obj.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
        
        if tag_name == 'Attribute':
            attr_uuid = obj.get('uuid')
            props_obj = obj.find('.//md:Properties', ns)
            attr_data = {'uuid': attr_uuid}
            if props_obj is not None:
                for prop in props_obj:
                    p_name = prop.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
                    p_text = prop.text
                    if not p_text:
                        for sub in prop:
                            if 'content' in sub.tag.lower() and sub.text:
                                p_text = sub.text
                                break
                    attr_data[p_name] = (p_text or '').strip()
            attributes.append(attr_data)
            
        elif tag_name == 'TabularSection':
            ts_uuid = obj.get('uuid')
            props_obj = obj.find('.//md:Properties', ns)
            ts_data = {'uuid': ts_uuid}
            if props_obj is not None:
                for prop in props_obj:
                    p_name = prop.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
                    p_text = prop.text
                    if not p_text:
                        for sub in prop:
                            if 'content' in sub.tag.lower() and sub.text:
                                p_text = sub.text
                                break
                    ts_data[p_name] = (p_text or '').strip()
            child_objs = obj.find('.//md:ChildObjects', ns)
            columns = []
            if child_objs is not None:
                for col in child_objs:
                    c_name = col.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
                    if c_name == 'Attribute':
                        col_uuid = col.get('uuid')
                        col_props = col.find('.//md:Properties', ns)
                        col_data = {'uuid': col_uuid}
                        if col_props is not None:
                            for cp in col_props:
                                cn = cp.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
                                ct = cp.text
                                if not ct:
                                    for sub in cp:
                                        if 'content' in sub.tag.lower() and sub.text:
                                            ct = sub.text
                                            break
                                col_data[cn] = (ct or '').strip()
                        columns.append(col_data)
            ts_data['columns'] = columns
            tabular_sections.append(ts_data)
            
        elif tag_name == 'Form':
            forms.append({'name': obj.text or ''})
        elif tag_name == 'Template':
            templates.append({'name': obj.text or ''})
    
    return attributes, tabular_sections, forms, templates


def register_external_report(source_path):
    """Register external report/processing from directory into ckb_1c_configurations."""
    if not os.path.isdir(source_path):
        return {"success": False, "error": f"Folder not found: {source_path}"}
    
    ext_xml = None
    obj_type = "external_processing"
    
    for xml_file in Path(source_path).rglob("*.xml"):
        try:
            with open(xml_file, "r", encoding="utf-8-sig") as f:
                content = f.read()
            if "<ExternalDataProcessor " in content or "<ExternalReport " in content:
                ext_xml = str(xml_file)
                if "<ExternalReport " in content:
                    obj_type = "external_report"
                break
        except Exception:
            pass
    
    if not ext_xml:
        return {"success": False, "error": "External report/processing XML not found"}
    
    tree = ET.parse(ext_xml)
    root = tree.getroot()
    ns = {'md': 'http://v8.1c.ru/8.3/MDClasses'}
    
    report_uuid = root.get('uuid')
    if obj_type == "external_report":
        report_tag = root.find('.//md:ExternalReport', ns)
    else:
        report_tag = root.find('.//md:ExternalDataProcessor', ns)
    
    if report_tag is None:
        return {"success": False, "error": f"Could not find {obj_type} element in XML"}
    
    if not report_uuid:
        report_uuid = report_tag.get('uuid', root.get('uuid'))
    
    properties = report_tag.find('.//md:Properties', ns)
    props = {}
    if properties is not None:
        for prop in properties:
            p_name = prop.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
            p_text = prop.text or ''
            if not p_text:
                for sub in prop:
                    if 'content' in sub.tag.lower() and sub.text:
                        p_text = sub.text
                        break
            props[p_name] = p_text.strip()
    
    name = props.get('Name', Path(ext_xml).stem)
    synonym = props.get('Synonym', '')
    comment = props.get('Comment', '')
    
    attributes, tabular_sections, forms, templates = _parse_child_objects(root, ns)
    
    # Helper functions for SQL escaping
    def sql_escape(s):
        return (s or '').replace("'", "''")
    
    def sql_val(s):
        if not s:
            return "NULL"
        return "'" + sql_escape(s) + "'"
    
    # Insert into external_report or external_processing
    if obj_type == "external_report":
        mds = sql_val(props.get("MainDataCompositionSchema", "").split(".")[-1] if props.get("MainDataCompositionSchema") else None)
        df = sql_val(props.get("DefaultForm", "").split(".")[-1] if props.get("DefaultForm") else None)
        af = sql_val(props.get("AuxiliaryForm", "").split(".")[-1] if props.get("AuxiliaryForm") else None)
        dsf = sql_val(props.get("DefaultSettingsForm", "").split(".")[-1] if props.get("DefaultSettingsForm") else None)
        asf = sql_val(props.get("AuxiliarySettingsForm", "").split(".")[-1] if props.get("AuxiliarySettingsForm") else None)
        dvf = sql_val(props.get("DefaultVariantForm", "").split(".")[-1] if props.get("DefaultVariantForm") else None)
        vs = sql_val(props.get("VariantsStorage", "").split(".")[-1] if props.get("VariantsStorage") else None)
        ss = sql_val(props.get("SettingsStorage", "").split(".")[-1] if props.get("SettingsStorage") else None)
        
        sql = (f"INSERT INTO external_report (name, synonym, comment, version, uuid, class_id, "
               f"main_data_composition_schema, default_form, auxiliary_form, "
               f"default_settings_form, auxiliary_settings_form, default_variant_form, "
               f"variants_storage, settings_storage) VALUES ("
               f"'{sql_escape(name)}', '{sql_escape(synonym)}', '{sql_escape(comment)}', "
               f"'1.0.0.0', '{report_uuid}'::uuid, 'e41aff26-25cf-4bb6-b6c1-3f478a75f374', "
               f"{mds}, {df}, {af}, {dsf}, {asf}, {dvf}, {vs}, {ss}) RETURNING id")
        result = _run_psql(sql)
    else:
        sql = (f"INSERT INTO external_processing (name, synonym, comment, version, uuid, class_id) "
               f"VALUES ('{sql_escape(name)}', '{sql_escape(synonym)}', '{sql_escape(comment)}', "
               f"'1.0.0.0', '{report_uuid}'::uuid, 'e41aff26-25cf-4bb6-b6c1-3f478a75f374') RETURNING id")
        result = _run_psql(sql)
    
    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"]}
    
    object_id = 0
    if isinstance(result, list) and len(result) > 0:
        if "result" in result[0]:
            object_id = result[0]["result"]
        elif isinstance(result[0], dict):
            for k, v in result[0].items():
                if isinstance(v, int):
                    object_id = v
                    break
    
    if object_id == 0:
        return {"success": False, "error": f"Failed to get object ID from INSERT result: {result}"}
    
    # Insert attributes
    for attr in attributes:
        sql = (f"INSERT INTO report_attributes (report_id, uuid, name, synonym, type, password_mode, fill_checking) "
               f"VALUES ({object_id}, '{attr.get('uuid')}', "
               f"'{sql_escape(attr.get('Name', ''))}', '{sql_escape(attr.get('Synonym') or '')}', "
               f"'{sql_escape(attr.get('Type') or '')}', "
               f"{'false' if attr.get('PasswordMode') == 'true' else 'true'}, "
               f"'{sql_escape(attr.get('FillChecking', 'DontCheck'))}')")
        res = _run_psql(sql)
        if isinstance(res, dict) and "error" in res:
            print(f"Warning: attribute insert failed: {res['error']}")
    
    # Insert tabular sections and columns
    tsection_ids = {}
    for ts in tabular_sections:
        sql = (f"INSERT INTO report_tabular_sections (report_id, uuid, name, synonym) "
               f"VALUES ({object_id}, '{ts.get('uuid')}', "
               f"'{sql_escape(ts.get('Name', ''))}', '{sql_escape(ts.get('Synonym') or '')}') RETURNING id")
        ts_result = _run_psql(sql)
        tsection_id = 0
        if isinstance(ts_result, list) and len(ts_result) > 0:
            tsection_id = ts_result[0].get("result", 0)
        tsection_ids[ts.get('Name', '')] = tsection_id
        
        for col in ts.get('columns', []):
            sql = (f"INSERT INTO tabular_section_attributes (tsection_id, uuid, name, synonym, type) "
                   f"VALUES ({tsection_id}, '{col.get('uuid')}', "
                   f"'{sql_escape(col.get('Name', ''))}', '{sql_escape(col.get('Synonym') or '')}', "
                   f"'{sql_escape(col.get('Type') or '')}')")
            _run_psql(sql)
    
    # Insert forms
    base_path = Path(ext_xml).parent / Path(ext_xml).stem
    for form_info in forms:
        form_name = form_info['name']
        form_xml_path = base_path / "Forms" / f"{form_name}.xml"
        
        if not form_xml_path.exists():
            continue
        
        form_tree = ET.parse(str(form_xml_path))
        form_root = form_tree.getroot()
        form_uuid = form_root.get('{http://v8.1c.ru/8.3/MDClasses}uuid') or form_root.attrib.get('uuid', '')
        form_props = form_root.find('.//md:Properties', ns)
        
        fname = ''
        fsynonym = ''
        ftype = 'Managed'
        
        if form_props is not None:
            for prop in form_props:
                p_name = prop.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
                p_text = prop.text or ''
                if not p_text:
                    for sub in prop:
                        if 'content' in sub.tag.lower() and sub.text:
                            p_text = sub.text
                            break
                if p_name == 'Name':
                    fname = (p_text or '').strip()
                elif p_name == 'Synonym':
                    fsynonym = (p_text or '').strip()
                elif p_name == 'FormType':
                    ftype = (p_text or '').strip()
        
        module_path = base_path / form_name / "Ext" / "Form" / "Module.bsl"
        module_code = ''
        if module_path.exists():
            with open(module_path, 'r', encoding='utf-8-sig') as f:
                module_code = f.read()[:5000]
        
        sql = (f"INSERT INTO report_forms (report_id, uuid, name, synonym, form_type, xml_file_path, module_code) "
               f"VALUES ({object_id}, '{form_uuid}', '{sql_escape(fname)}', "
               f"'{sql_escape(fsynonym)}', '{ftype}', '{str(form_xml_path).replace(chr(92), chr(47))}', "
               f"'{sql_escape(module_code)}')")
        _run_psql(sql)
    
    # Insert templates
    for template_info in templates:
        template_name = template_info['name']
        template_xml_path = base_path / "Templates" / f"{template_name}.xml"
        
        if not template_xml_path.exists():
            continue
        
        template_tree = ET.parse(str(template_xml_path))
        template_root = template_tree.getroot()
        template_uuid = template_root.get('{http://v8.1c.ru/8.3/MDClasses}uuid') or template_root.attrib.get('uuid', '')
        template_props = template_root.find('.//md:Properties', ns)
        
        tname = ''
        tsynonym = ''
        ttype = 'MXL'
        
        if template_props is not None:
            for prop in template_props:
                p_name = prop.tag.replace('{http://v8.1c.ru/8.3/MDClasses}', '')
                p_text = prop.text or ''
                if not p_text:
                    for sub in prop:
                        if 'content' in sub.tag.lower() and sub.text:
                            p_text = sub.text
                            break
                if p_name == 'Name':
                    tname = (p_text or '').strip()
                elif p_name == 'Synonym':
                    tsynonym = (p_text or '').strip()
                elif p_name == 'TemplateType':
                    ttype = (p_text or '').strip()
        
        content_path = base_path / template_name / "Ext" / "Template.xml"
        content_path_str = str(content_path).replace(chr(92), chr(47)) if content_path.exists() else None
        
        xml_path_str = str(template_xml_path).replace(chr(92), chr(47))
        
        if content_path_str:
            sql = (f"INSERT INTO report_templates (report_id, uuid, name, synonym, template_type, xml_file_path, content_path) "
                   f"VALUES ({object_id}, '{template_uuid}', '{sql_escape(tname)}', "
                   f"'{sql_escape(tsynonym)}', '{ttype}', '{xml_path_str}', '{sql_escape(content_path_str)}')")
        else:
            sql = (f"INSERT INTO report_templates (report_id, uuid, name, synonym, template_type, xml_file_path) "
                   f"VALUES ({object_id}, '{template_uuid}', '{sql_escape(tname)}', "
                   f"'{sql_escape(tsynonym)}', '{ttype}', '{xml_path_str}')")
        _run_psql(sql)
    
    # Index BSL modules
    ext_folders = []
    ext_folder = base_path / "Ext"
    if ext_folder.is_dir():
        ext_folders.append(ext_folder)
    
    for form_ext in base_path.rglob("Ext"):
        if form_ext.is_dir():
            parent = form_ext.parent.name
            grandparent = form_ext.parent.parent.name
            if parent == "Forms":
                ext_folders.append(form_ext)
            elif grandparent and grandparent.lower() in ("forms", "template", "шаблон"):
                ext_folders.append(form_ext)
    
    bsl_seen = set()
    bsl_count = 0
    for ef in ext_folders:
        for bsl_file in ef.rglob("*.bsl"):
            if str(bsl_file) in bsl_seen:
                continue
            bsl_seen.add(str(bsl_file))
            rel_path = str(bsl_file.relative_to(Path(source_path))).replace(chr(92), chr(47))
            
            with open(bsl_file, 'r', encoding='utf-8-sig') as bf:
                code_content = bf.read()[:50000]
            
            obj_module_type = 'ObjectModule'
            if '/Form/' in str(bsl_file) or 'Form' in str(bsl_file.parent):
                obj_module_type = 'FormModule'
            
            sql = (f"INSERT INTO bsl_modules (configuration_id, module_name, file_path, code, object_type, object_name, report_id) "
                   f"VALUES (NULL, '{bsl_file.name}', '{rel_path}', '{sql_escape(code_content)}', "
                   f"'{obj_module_type}', '{sql_escape(name)}', {object_id})")
            _run_psql(sql)
            bsl_count += 1
    
    return {
        "success": True,
        "id": object_id,
        "name": name,
        "object_type": obj_type,
        "attributes_count": len(attributes),
        "tabular_sections_count": len(tabular_sections),
        "forms_count": len(forms),
        "templates_count": len(templates),
        "bsl_modules_indexed": bsl_count,
    }

