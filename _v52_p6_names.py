# -*- coding: utf-8 -*-
"""Служебная сверка имён узла П6 (временный файл): что экспортирует слой разбора."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_filter_criteria as m  # noqa: E402

NAMES = [
    "CHILD_COMMAND", "CHILD_FORM", "CLASS_DEFINED_TYPE_REF", "CLASS_OBJECT_REF",
    "CLASS_PRIMITIVE", "CLASS_UNKNOWN", "CONTENT_EMPTY_CONTENT", "CONTENT_ELEMENT_TAG",
    "CONTENT_ITEM_ATTR", "CONTENT_ITEM_TAG", "CONTENT_ITEM_TYPE_VALUE", "CONTENT_TABLE_NAME",
    "CONTENT_WITH_CONTENT", "CONTAINER_TYPE", "CONTAINER_TYPE_SET", "DIR_NAME",
    "FILTER_CRITERION_PROPERTIES", "FILTER_CRITERION_PROPERTY_COUNT", "INDEX_NAME_SEPARATOR",
    "INDEX_OBJECT_TYPE", "MULT_ABSENT", "MULT_COMPOSITE", "MULT_SINGLE",
    "OBSERVATION_DIRECTORY_MISSING", "OBSERVATION_HELP_FILE", "OBSERVATION_HELP_RESOURCES",
    "OBJECT_KIND_TAG", "TARGET_PREFIX_ONLY", "TARGET_STATES", "TARGET_UNRESOLVED",
    "TABLE_NAME", "TYPE_ABSENT", "TYPE_PARSED", "TYPE_PARTIAL", "TYPE_UNKNOWN_FORM",
    "STATE_VOCABULARIES", "STATE_VOCABULARY_TABLES", "PROPERTIES_STATES", "CONTENT_STATES",
    "CHILD_STATES", "TYPE_BLOCK_STATES", "MULTIPLICITY_VALUES", "FORM_REF_STATES",
    "TYPE_CLASS_VALUES", "FORM_REF_WITH_REFERENCE", "FORM_REF_EMPTY_VALUE", "PROPS_ALL_KNOWN",
    "PROPS_UNKNOWN_VALUE", "TYPE_ENTRY_REASON_KEY", "CHILD_LIST_FORM_NAMES",
    "CHILD_LIST_COMMAND_UUIDS", "SUBDIR_FORMS", "SUBDIR_EXT", "QUALIFIER_TAGS",
    "CIRCLE_INDEX_ONLY", "CIRCLE_FILE_ONLY", "CIRCLE_UUID_MISMATCH", "TARGET_EXACT",
    "CHILD_INDEXED_NO_FILE", "CHILD_FILE_NOT_IN_INDEX", "PROPS_ABSENT", "FORM_REF_ABSENT",
    "FORM_REF_UNKNOWN_FORM", "collect_filter_criteria", "index_row_key", "index_rows_by_name",
    "property_records", "resolve_target", "state_vocabulary", "state_vocabulary_table",
    "kind_root_index_rows", "split_index_child_name", "index_object_name", "property_columns",
    "multi_column_tags", "value_dictionary", "raw_type_block", "count_container_tags",
]
missing = [name for name in NAMES if not hasattr(m, name)]
print("MISSING:", missing)
print("PROPERTY_TAGS:", [row[0] for row in m.property_records()])
print("PROPERTY_COLUMNS:", m.property_columns())
print("STATE_VOCABULARIES:", {k: list(v) for k, v in m.STATE_VOCABULARIES.items()})
print("TYPE_CLASS_VALUES:", m.TYPE_CLASS_VALUES)
print("TYPE_ENTRY_REASON_KEY:", m.TYPE_ENTRY_REASON_KEY)
print("QUALIFIER_TAGS:", m.QUALIFIER_TAGS)
print("CONTRACT:", end=" ")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from configuration_load_contract import (  # noqa: E402
    FILTER_CRITERIA_TABLES, STAGE_FILTER_CRITERIA, STAGES, stage_resume_hint,
)
print([s["key"] for s in STAGES])
print("FILTER_CRITERIA_TABLES:", FILTER_CRITERIA_TABLES)
print("STAGE:", STAGE_FILTER_CRITERIA, "hint:", stage_resume_hint(STAGE_FILTER_CRITERIA))
