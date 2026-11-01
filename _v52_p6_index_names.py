import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
import psycopg2  # noqa: E402

conn = psycopg2.connect(host="localhost", dbname="ckb_1c_configurations", user="postgres",
                        password="Sta090860")
cur = conn.cursor()
cur.execute("""
    SELECT c.id, c.name, c.uuid::text, c.revision_no, c.is_committed,
           (SELECT count(*) FROM configuration_objects o WHERE o.configuration_id = c.id
             AND o.name LIKE 'FilterCriterion%') AS idx_singular,
           (SELECT count(*) FROM configuration_objects o WHERE o.configuration_id = c.id
             AND o.name LIKE 'FilterCriteria%') AS idx_plural,
           (SELECT count(*) FROM filter_criteria f WHERE f.configuration_uuid = c.uuid) AS rows_v52
    FROM configurations c
    WHERE EXISTS (SELECT 1 FROM configuration_objects o WHERE o.configuration_id = c.id
                  AND (o.name LIKE 'FilterCriterion%' OR o.name LIKE 'FilterCriteria%'))
    ORDER BY c.name, c.revision_no
""")
for row in cur.fetchall():
    print(" | ".join(str(part) for part in row))
