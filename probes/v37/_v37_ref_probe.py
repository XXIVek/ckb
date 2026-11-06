"""_v37_ref_probe.py — на какие объекты конфигурации опирается загруженный внешний объект.

Зачем: чтобы выбрать первый срез загрузки содержимого конфигурации не «на глаз», а по
фактическим ссылкам уже загруженного внешнего отчёта. Источник — только строки БД
(атрибуты, макеты, модули, модули форм), файлы выгрузки не читаются.

Запуск: python _v37_ref_probe.py [id_внешнего_объекта]
"""
import os
import collections
import re
import sys

import psycopg2

PAT = re.compile(r"(?:cfg:|d4p1:)([A-Za-z][A-Za-z0-9]*\.[^\s\"'<>&]+)")


def main():
    obj_id = int(sys.argv[1]) if len(sys.argv) > 1 else 505
    conn = psycopg2.connect(dbname="ckb_1c_configurations", user="postgres",
                            password=os.environ["PGPASSWORD"], host="localhost")
    cur = conn.cursor()
    cur.execute("SELECT uuid, name, object_kind FROM external_report WHERE id=%s", (obj_id,))
    row = cur.fetchone()
    if not row:
        print(f"внешний объект id={obj_id} не найден")
        return 1
    uuid, name, kind = row
    print(f"объект id={obj_id} {name} ({kind})")

    texts = []
    for sql in (
        "SELECT type FROM attributes WHERE parent_uuid=%s",
        "SELECT ext FROM templates WHERE parent_uuid=%s",
        "SELECT code FROM bsl_modules WHERE parent_uuid=%s",
        "SELECT ext FROM form_ext WHERE parent_uuid=%s",
    ):
        cur.execute(sql, (uuid,))
        texts.extend(r[0] or "" for r in cur.fetchall())

    counts = collections.Counter()
    for text in texts:
        for ref in PAT.findall(text):
            counts[ref] += 1

    kinds = collections.Counter(r.split(".", 1)[0] for r in counts)
    print(f"строк содержимого прочитано: {len(texts)}")
    print(f"уникальных ссылок на объекты конфигурации: {len(counts)}")
    print("разбивка по видам:", dict(kinds))
    for ref, cnt in counts.most_common(60):
        print(f"  {ref}  x{cnt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
