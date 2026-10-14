#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_v22_inspect.py — компактно показать, что нужно для ручных алиасов и ссылок на документацию.

Печатает по эталонным объектам: заголовок (uuid, name, object_kind), состав макета-СКД
(наборы данных, связи, параметры с флагом использования, вычисляемые поля, итоги),
объявления из модулей (объект/форма) — только имена и строки, без полных текстов.

Запуск:
    python _v22_inspect.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from external_db import connect  # noqa: E402
from enrichment_dcs import parse_dcs, template_rows  # noqa: E402

CATALOGS = [
    r"C:\1C_LLM\LoadDoc\Test1_Otchet",
    r"C:\1C_LLM\LoadDoc\Test2_Otchet",
]
DECL_RE = re.compile(r"^\s*(?:Процедура|Функция|Procedure|Function)\s+([А-Яа-яA-Za-z0-9_]+)", re.M)


def main():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT uuid, name, object_kind, synonym::text, comment, "
        "main_data_composition_schema, default_form FROM external_report ORDER BY id")
    headers = cur.fetchall()
    for uuid, name, kind, synonym, comment, dcs_name, default_form in headers:
            print("=" * 70)
            print(f"OBJECT {name} uuid={uuid} kind={kind}")
            print(f"  synonym={synonym}")
            print(f"  comment={comment}")
            print(f"  main_dcs={dcs_name} default_form={default_form}")
            for tpl in template_rows(cur, uuid):
                print(f"  TEMPLATE {tpl.get('name')} root={tpl.get('ext_root_tag')} "
                      f"chars={tpl.get('ext_chars')} truncated={tpl.get('ext_truncated')}")
                parsed = parse_dcs(tpl.get("ext") or "", tpl.get("name") or "", tpl.get("uuid"),
                                   bool(tpl.get("ext_truncated")))
                if not parsed.get("success"):
                    print(f"    dcs parse failed: {parsed.get('reason')}")
                    continue
                for ds in parsed.get("datasets") or []:
                    has_query = bool(ds.get("query"))
                    print(f"    dataset={ds.get('name')} type={ds.get('kind')} "
                          f"fields={len(ds.get('fields') or [])} query={has_query}")
                for dl in parsed.get("dataset_links") or []:
                    print(f"    link {dl.get('source_dataset')} -> {dl.get('destination_dataset')} "
                          f"join={dl.get('join_type')} left_expr={dl.get('source_expression')} "
                          f"right_expr={dl.get('destination_expression')}")
                for p in parsed.get("parameters") or []:
                    print(f"    param={p.get('name')} type={p.get('value_type')} "
                          f"usage={p.get('usage')} settings_usage={len(p.get('settings_usage') or [])}")
                for cf in parsed.get("calculated_fields") or []:
                    print(f"    calc={cf.get('data_path')} kind={cf.get('kind')} use={cf.get('use')}")
                for tf in parsed.get("total_fields") or []:
                    print(f"    total={tf.get('data_path')} ver={tf.get('total_ver')}")
                for sv in parsed.get("settings_variants") or []:
                    counts = sv.get("counts") or {}
                    print(f"    settings_variant={sv.get('name')} "
                          f"structure_levels={counts.get('structure_levels')} filters={counts.get('filters')} "
                          f"orders={counts.get('orders')} data_parameters={counts.get('data_parameters')} "
                          f"output_parameters={counts.get('output_parameters')}")
                print(f"    unparsed={parsed.get('unparsed')}")
            cur.execute(
                "SELECT f.name, fe.ext FROM forms f JOIN form_ext fe ON fe.form_id = f.id "
                "WHERE f.parent_uuid = %s::uuid", (uuid,))
            for fname, ext in cur.fetchall():
                decls = DECL_RE.findall(ext or "")
                print(f"  FORM {fname} module_decls={decls}")
            cur.execute(
                "SELECT module_type, code FROM bsl_modules WHERE parent_uuid = %s::uuid", (uuid,))
            for mtype, code in cur.fetchall():
                print(f"  MODULE {mtype} decls={DECL_RE.findall(code or '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
