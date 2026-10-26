import sys; sys.path.insert(0, 'src')
from pathlib import Path
import psycopg2
ROOT = Path(r'C:\1C_LLM\LoadDoc\Configurations\XML_files\BGU2')
DIRS = {'Catalog': 'Catalogs'}
conn = psycopg2.connect(dbname='ckb_1c_configurations', user='postgres', password='Sta090860', host='localhost')
cur = conn.cursor()
cur.execute("""SELECT name, object_name, object_id FROM configuration_objects
               WHERE configuration_id=242 AND depth=2 AND child_type='CommandModule'""")
rows = cur.fetchall()
print('записей CommandModule depth=2:', len(rows))
by_name = miss_name = 0
by_obj = 0
misses = []
for full, obj_name, oid in rows:
    parts = full.split('.')
    kind, top, child_kind, own = parts[0], parts[1], parts[2], parts[3]
    # вариант B: путь из сегментов name (единственный источник имени команды)
    p = ROOT / DIRS.get(kind, kind) / top / child_kind.capitalize() if False else None
    p = ROOT / DIRS.get(kind, kind) / top / ('Commands' if child_kind == 'Command' else child_kind) / own / 'Ext' / 'CommandModule.bsl'
    if p.is_file(): by_name += 1
    else:
        miss_name += 1
        if len(misses) < 4: misses.append(str(p.relative_to(ROOT)))
    # вариант A: путь так, как его можно собрать по колонкам (object_name вместо имени команды)
    q = ROOT / DIRS.get(kind, kind) / obj_name / 'Commands' / obj_name / 'Ext' / 'CommandModule.bsl'
    if q.is_file(): by_obj += 1
print('путь из name: файл есть', by_name, '| нет', miss_name)
print('путь из object_name (имя владельца вместо имени команды): файл есть', by_obj, '| нет', len(rows) - by_obj)
for m in misses: print('  нет файла:', m)
