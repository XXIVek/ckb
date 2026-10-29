#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П0 узла V48: сверка файлов `SessionParameters` с индексом состава живой БД.

Зачем. Узел V46 строил ключ строки по цепочке раскладки, а содержимое сверял с индексом
состава; для параметров сеанса раскладки-иерархии нет (объект лежит одним файлом в каталоге
вида), поэтому единственным естественным ключом остаётся uuid метаданных. Прежде чем выбирать
его, нужно знать: совпадает ли uuid из файла с записью индекса, и нет ли записей индекса без
файла (у V47 таких было 47).

Заодно замеряются вещи, от которых зависит форма колонок: многоязычность `Synonym`, непустой
`Comment`, длина исходного блока `<Type>`, присутствие `ObjectBelonging` (в модели он значится
свойством вида — в этих выгрузках его нет ни разу).

Ничего в БД зонд не пишет.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from external_db import connect  # noqa: E402  (src/external_db.py)

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "BGU2", "BP3", "KomMag")
DIR_NAME = "SessionParameters"
RE_CONFIG_UUID = re.compile(r'<Configuration\s+uuid="([0-9a-fA-F-]{36})"')

RE_ROOT = re.compile(r'<SessionParameter\s+uuid="([0-9a-fA-F-]{36})">\s*<Properties>(.*?)'
                     r'</Properties>', re.S)
RE_NAME = re.compile(r"<Name>([^<]*)</Name>")
RE_TYPE_BLOCK = re.compile(r"<Type>(.*?)</Type>", re.S)
RE_LANGS = re.compile(r"<v8:lang>([^<]*)</v8:lang>")
RE_COMMENT = re.compile(r"<Comment>(.*?)</Comment>", re.S)


def main() -> int:
    problems = 0
    conn = connect()
    try:
        cur = conn.cursor()
        for dump in DUMPS:
            directory = DUMP_ROOT / dump / DIR_NAME
            if not directory.exists():
                print(f"{dump}: каталога вида нет — пропуск")
                continue
            config_xml = DUMP_ROOT / dump / "Configuration.xml"
            config_uuid = ""
            if config_xml.exists():
                found = RE_CONFIG_UUID.search(
                    config_xml.read_text(encoding="utf-8", errors="replace"))
                config_uuid = found.group(1).lower() if found else ""
            files = {}
            for path in sorted(directory.glob("*.xml")):
                text = path.read_text(encoding="utf-8", errors="replace")
                root = RE_ROOT.search(text)
                if not root:
                    print(f"  {dump}: НЕ РАЗОЗНАН корневой тег — {path.name}")
                    problems += 1
                    continue
                body = root.group(2)
                name = (RE_NAME.search(body) or [None, ""])[1] if RE_NAME.search(body) else ""
                files[root.group(1).lower()] = {
                    "file": path.name,
                    "name": name,
                    "type_len": len(RE_TYPE_BLOCK.search(body).group(1))
                    if RE_TYPE_BLOCK.search(body) else 0,
                    "langs": len(set(RE_LANGS.findall(body))),
                    "comment": bool((RE_COMMENT.search(body) or [None, ""])[1].strip()
                                    if RE_COMMENT.search(body) else False),
                    "object_belonging": "<ObjectBelonging>" in body,
                }

            cur.execute("select name from configurations where uuid = %s::uuid", (config_uuid,))
            header_row = cur.fetchone()
            header_name = header_row[0] if header_row else f"<заголовка нет: {config_uuid}>"
            cur.execute(
                "select co.uuid, co.object_name, co.name from configuration_objects co "
                "join configurations c on c.id = co.configuration_id "
                "where c.uuid = %s::uuid and co.object_type = 'SessionParameter'",
                (config_uuid,),
            )
            index_rows = cur.fetchall()
            index_uuids = {str(r[0]).lower() for r in index_rows}
            file_uuids = set(files)
            only_files = file_uuids - index_uuids
            only_index = index_uuids - file_uuids
            name_mismatch = [
                (files[u]["file"], r[1])
                for u, r in ((u, next(x for x in index_rows if str(x[0]).lower() == u))
                            for u in (file_uuids & index_uuids))
                if files[u]["name"] and files[u]["name"] != r[1]
            ]
            print(f"\n{dump} (заголовок {header_name!r}): файлов {len(files)}, "
                  f"записей индекса {len(index_rows)}")
            print(f"  uuid только в файлах: {len(only_files)}; "
                  f"только в индексе: {len(only_index)}; "
                  f"расхождений имени: {len(name_mismatch)}")
            if only_files or only_index or name_mismatch:
                problems += 1
                for u in sorted(only_files)[:5]:
                    print(f"    файл без индекса: {files[u]['file']} {u}")
                for u in sorted(only_index)[:5]:
                    print(f"    индекс без файла: {u}")
            langs = sum(1 for v in files.values() if v["langs"] > 1)
            comments = sum(1 for v in files.values() if v["comment"])
            type_max = max((v["type_len"] for v in files.values()), default=0)
            type_total = sum(v["type_len"] for v in files.values())
            print(f"  синонимов > 1 языка: {langs}; непустых Comment: {comments}; "
                  f"ObjectBelonging: {sum(1 for v in files.values() if v['object_belonging'])}")
            print(f"  блок <Type>: байт всего {type_total}, максимум на файл {type_max}")
    finally:
        conn.close()
    print(f"\nПРОБЛЕМНЫХ ВЫГРУЗОК: {problems}")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
