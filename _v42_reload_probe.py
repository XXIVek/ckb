"""Одноразовый зонд (22.10.2026): сравнить разбор Configuration.xml с живой строкой
configurations по 33 колонкам узла V42 для КАЖДОГО заголовка в БД.

Раздел 5 tools/check_v42_configuration_header.py считает заполненность, но не знает путь
источника (провенанса строк конфигурации нет, решение D-C) - поэтому сопоставление идёт по
uuid строки с разбором того же Configuration.xml из XML_files.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
import psycopg2  # noqa: E402
from configuration_meta_parser import parse_configuration_meta  # noqa: E402

V42 = (
    "configuration_extension_compatibility_mode", "database_tablespaces_use_mode",
    "main_client_application_window_mode", "object_autonumeration_mode",
    "use_managed_form_in_ordinary_application", "use_ordinary_form_in_managed_application",
    "mobile_application_functionalities", "allowed_incoming_share_request_types",
    "common_settings_storage", "reports_variants_storage", "reports_user_settings_storage",
    "form_data_settings_storage", "dynamic_lists_user_settings_storage", "default_report_form",
    "default_report_variant_form", "default_report_settings_form", "default_style",
    "default_interface", "default_constants_form", "default_search_form",
    "default_dynamic_list_settings_form", "default_collaboration_system_users_choice_form",
    "default_data_history_change_history_form", "default_data_history_version_data_form",
    "default_data_history_version_differences_form", "default_report_appearance_template",
    "url_external_data_storage", "name_prefix", "mobile_application_urls",
    "required_mobile_application_permissions", "standalone_configuration_restriction_roles",
    "additional_full_text_search_dictionaries", "content",
)
XML_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")


def main():
    conn = psycopg2.connect(dbname="ckb_1c_configurations", user="postgres",
                            password="Sta090860", host="localhost")
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, uuid, to_jsonb(c) FROM configurations c ORDER BY id")
        rows = cur.fetchall()
    by_uuid = {str(r[2]): r for r in rows}

    failed = 0
    for cat in sorted(p for p in XML_ROOT.iterdir() if p.is_dir()):
        xml = cat / "Configuration.xml"
        if not xml.exists():
            continue
        parsed = parse_configuration_meta(str(xml))
        if not parsed.get("success"):
            print(f"SKIP {cat.name}: разбор не выполнен - {parsed.get('reason')}")
            continue
        row = parsed["configuration"]
        counts = parsed["counts"]
        db = by_uuid.get(str(parsed["uuid"]))
        if db is None:
            print(f"SKIP {cat.name}: строки с uuid={parsed['uuid']} в БД нет")
            continue
        db_id, db_name, _, db_json = db
        p_set = {c for c in V42 if row.get(c) is not None}
        d_set = {c for c in V42 if db_json.get(c) is not None}
        missing, extra = sorted(p_set - d_set), sorted(d_set - p_set)
        unstored = counts.get("properties_unstored", 0)
        ok = not missing and not extra and not unstored
        failed += 0 if ok else 1
        print(f"{'OK  ' if ok else 'FAIL'} id={db_id} {cat.name}: разбор={len(p_set)}/33 "
              f"БД={len(d_set)}/33 props={counts['properties_total']} "
              f"mapped={counts['properties_mapped']} unstored={unstored}")
        if missing:
            print(f"     потеряно разбором в БД: {missing}")
        if extra:
            print(f"     в БД есть, разбор не давал: {extra}")
        for w in parsed.get("warnings", []):
            if "не разобрана" in w or "UNKNOWN" in w or "без колонки" in w:
                print(f"     WARN {w}")
    print(f"\nИТОГ: строк конфигурации проверено {len(rows)}, расхождений {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
