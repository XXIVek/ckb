import sys
sys.path.insert(0, "src")
from external_db import transaction
from configuration_event_subscriptions import TABLE_NAME
from current_revision import current_view
v = current_view(TABLE_NAME)
with transaction() as cur:
    cur.execute(f"""
        SELECT object_uuid, count(DISTINCT configuration_uuid) AS cfgs,
               count(DISTINCT full_name) AS names, count(*) AS rows_all
        FROM {v} GROUP BY object_uuid
        HAVING count(DISTINCT configuration_uuid) > 1
    """)
    rows = cur.fetchall()
    print("shared uuids:", len(rows))
    print("same name:", sum(1 for r in rows if r[1] == 2 and r[2] == 1))
    print("diff name:", sum(1 for r in rows if r[2] > 1))
    print("more than 2 rows:", sum(1 for r in rows if r[3] > 2))
    cur.execute(f"SELECT count(*) FROM (SELECT object_uuid, configuration_uuid, count(*) c FROM {v} GROUP BY 1,2 HAVING count(*) > 1) t")
    print("uuid twice in same config:", cur.fetchone()[0])
    cur.execute(f"""SELECT c.name, es.object_name FROM {v} es JOIN configurations c ON c.uuid=es.configuration_uuid
                   WHERE es.object_uuid='638fc121-89e1-48a3-8fbc-52ed34f888ba' ORDER BY 1""")
    for r in cur.fetchall():
        print(r)
