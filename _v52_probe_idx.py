import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from configuration_filter_criteria import INDEX_OBJECT_TYPE  # noqa: E402
from external_db import transaction  # noqa: E402

with transaction() as cur:
    print("INDEX_OBJECT_TYPE:", INDEX_OBJECT_TYPE)
    cur.execute(
        "SELECT c.name, o.child_type, count(*) AS c FROM configuration_objects o "
        "JOIN configurations c ON c.id = o.configuration_id "
        "WHERE o.object_type = %s GROUP BY 1, 2 ORDER BY 1, 3 DESC", (INDEX_OBJECT_TYPE,))
    for row in cur.fetchall() or []:
        print("ROW", row)
