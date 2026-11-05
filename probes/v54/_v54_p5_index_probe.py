"""Одноразовое действие: как устроен индекс состава вида `ScheduledJob` в MinCfg и BP3
(типы записей, глубина, родители) и колонка перечня заголовка `configurations.scheduled_jobs`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from external_db import transaction  # noqa: E402

with transaction() as cur:
    cur.execute("""
        SELECT c.name, co.object_type, count(*), min(co.depth), max(co.depth),
               count(*) FILTER (WHERE co.parent_name IS NULL) AS no_parent,
               count(*) FILTER (WHERE co.parent_name IS NOT NULL) AS with_parent
        FROM configuration_objects co JOIN configurations c ON c.id = co.configuration_id
        WHERE co.object_type LIKE 'ScheduledJob%%' AND c.name IN ('MinCfg', 'BP3')
        GROUP BY c.name, co.object_type ORDER BY c.name, co.object_type""")
    for row in cur.fetchall():
        print("индекс:", row)
    cur.execute("""
        SELECT c.name, co.object_name, co.parent_name, co.depth
        FROM configuration_objects co JOIN configurations c ON c.id = co.configuration_id
        WHERE co.object_type LIKE 'ScheduledJob%%' AND c.name = 'MinCfg'
        ORDER BY co.object_name LIMIT 8""")
    for row in cur.fetchall():
        print("строка:", row)
    cur.execute("""
        SELECT c.name, array_length(c.scheduled_jobs, 1) AS n, c.scheduled_jobs
        FROM configurations c WHERE c.name IN ('MinCfg','KomMag') ORDER BY c.name""")
    for row in cur.fetchall():
        print("перечень заголовка:", row)

