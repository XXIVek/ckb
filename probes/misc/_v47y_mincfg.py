"""_v47y_mincfg.py — сравнение индекса состава MinCfg на диске со строкой БД.

Зонд только читает. Нужен ровно один ответ: фикстура на диске новее загруженной
строки или нет (предупреждение handoff про `configurations id=244`).
"""
import os
import re

import psycopg2

SLOTS = ("ManagerModule", "ObjectModule", "Module", "CommandModule",
         "RecordSetModule", "ValueManagerModule")
PATH = r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg\ConfigDumpInfo.xml"

raw = open(PATH, encoding="utf-8-sig").read()
rows = re.findall(r'<Metadata name="([^"]+)" id="([^"]+)"', raw)
print(f"записей индекса MinCfg на диске: {len(rows)}")
comp = [n for n, i in rows if "." in i.split("-", 4)[-1]]
print(f"  составных object_id: {len(comp)}")
mods = [n for n, _ in rows if n.rsplit(".", 1)[-1] in SLOTS]
print(f"  модульных записей шести слотов: {len(mods)}")

conn = psycopg2.connect(host="localhost", user="postgres",
                        password=os.environ["PGPASSWORD"], dbname="ckb_1c_configurations")
cur = conn.cursor()
cur.execute("SELECT count(*) FROM configuration_objects WHERE configuration_id=244")
db_total = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM configuration_objects WHERE configuration_id=244 "
            "AND child_type = ANY(%s)", (list(SLOTS),))
db_mods = cur.fetchone()[0]
cur.execute("SELECT id, name, uuid FROM configurations WHERE id=244")
print("строка БД:", cur.fetchone())
conn.close()
print(f"строки БД: записей индекса {db_total}, модульных {db_mods}")
print(f"расхождение: индекс на диске минус строка БД = {len(rows) - db_total} "
      f"(модулей: {len(mods) - db_mods})")
