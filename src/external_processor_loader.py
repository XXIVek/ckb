#!/usr/bin/env python3
"""Loader for external processors/reports (DataProcessor, ExternalReport)."""
import os
import re as _re
import subprocess
from pathlib import Path


def _run_config_psql(query, db="configurations"):
    """Run psql query for configurations DB."""
    cmd = [r"C:\Postgres\bin\psql.exe", "-U", "postgres", "-d", db, "-h", "localhost", "-F", "|"]
    env = dict(os.environ)
    env["PGPASSWORD"] = "Sta090860"
    env["PGCLIENTENCODING"] = "UTF8"
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    stdout, stderr = proc.communicate(input=query.encode("utf-8"))
    if proc.returncode != 0:
        return {"error": f"PSQL error: {stderr.decode('cp1251').strip()}"}
    lines = [l for l in stdout.decode("utf-8").split("\n") if l.strip()]
    filtered = [l for l in lines if not (l.strip().startswith("(") and (l.strip().endswith(" rows") or l.strip().endswith(" row")))]
    lines = filtered
    if len(lines) < 3:
        return []
    headers = [h.strip() for h in lines[0].split("|")]
    rows = []
    for line in lines[2:]:
        s = line.strip()
        if s.startswith("(") and s.endswith(")"):
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


def register_external_processor(source_path):
    """Регистрация внешней обработки/отчета из каталога."""
    if not os.path.isdir(source_path):
        return {"success": False, "error": f"Папка не найдена: {source_path}"}

    ext_xml = None
    obj_type = "external_processor"  # по умолчанию
    for xml_file in Path(source_path).rglob("*.xml"):
        try:
            with open(xml_file, "r", encoding="utf-8") as f:
                content = f.read()
            if "<ExternalDataProcessor" in content or "<ExternalReport" in content:
                ext_xml = str(xml_file)
                if "<ExternalReport" in content:
                    obj_type = "external_report"
                break
        except Exception:
            pass

    if not ext_xml:
        return {"success": False, "error": "Внешняя обработка не найдена"}

    name = os.path.splitext(os.path.basename(ext_xml))[0]
    try:
        with open(ext_xml, "r", encoding="utf-8") as f:
            content = f.read()
        m = _re.search(r"<Name[^>]*>([^<]+)</Name>", content)
        if m:
            name = m.group(1).strip()
    except Exception:
        pass

    safe_name = name.replace("'", "''")
    src_escaped = source_path.replace(chr(92), chr(92) + chr(92))

    sql = f"INSERT INTO configuration (name, full_name, vendor, version, uuid, source_path, dump_file, status, object_type) VALUES ('{safe_name}', '', '', '', NULL, '{src_escaped}', '', 'pending', 'external_processor') RETURNING id"
    result = _run_config_psql(sql)
    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result["error"]}

    config_id = result[0]["id"] if result else 0

    bsl_count = 0
    # Ищем папку Ext рядом с XML файлом обработки (внутри каталога объекта)
    base_dir = Path(ext_xml).parent
    ext_folder = base_dir / "Ext"
    if not ext_folder.is_dir():
        # Пробуем найти подкаталог с .bsl файлами
        for sub in base_dir.iterdir():
            if sub.is_dir() and (sub / "Ext").is_dir():
                ext_folder = sub / "Ext"
                break

    # Собираем все папки Ext для поиска BSL-модулей
    ext_folders = []
    if ext_folder.is_dir():
        ext_folders.append(ext_folder)
    # Ищем модули форм: */Forms/*/Ext/Form/Module.bsl (рекурсивно по подкаталогам форм)
    for form_ext in base_dir.rglob("Ext"):
        if form_ext.is_dir():
            parent = form_ext.parent.name
            grandparent = form_ext.parent.parent.name
            # Проверяем что это папка формы: {FormName}/Ext/Form или просто */Ext (корневой)
            if parent == "Forms":
                # base_dir/Forms/Ext - корневая Ext (уже добавлена выше, но дубликат обработится через bsl_seen)
                ext_folders.append(form_ext)
            elif grandparent and grandparent.lower() in ("forms", "template", "шаблон"):
                ext_folders.append(form_ext)

    # Индексируем все найденные BSL-модули
    bsl_seen = set()
    for ef in ext_folders:
        for bsl_file in ef.rglob("*.bsl"):
            if str(bsl_file) in bsl_seen:
                continue
            bsl_seen.add(str(bsl_file))
            safe_fname = bsl_file.name.replace("'", "''")
            rel_path = str(bsl_file.relative_to(Path(source_path))).replace(chr(92), "/")
            try:
                with open(bsl_file, "r", encoding="utf-8") as bf:
                    code_content = bf.read()
                code_escaped = code_content.replace("'", "''")
            except Exception:
                code_escaped = ""
            ins_sql = f"INSERT INTO bsl_modules (configuration_id, module_name, file_path, code) VALUES ({config_id}, '{safe_fname}', '{rel_path}', '{code_escaped}') ON CONFLICT DO NOTHING"
            _run_config_psql(ins_sql)
            bsl_count += 1

    return {"success": True, "id": config_id, "name": name, "status": "pending", "source_path": source_path, "object_type": obj_type, "bsl_modules_indexed": bsl_count}
