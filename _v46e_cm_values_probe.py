# -*- coding: utf-8 -*-
"""_v46e_cm_values_probe.py — словарь значений свойств CommonModule по выгрузкам.

Зонд только читает файлы регистрации (в БД не пишет). Нужен для DDL узла V46:
CHECK по словарю значений объявляется только когда значения названы замером,
а не по памяти о одном файле MinCfg.

Что измеряется:
  A. какие теги свойств встречаются у CommonModule и сколько раз;
  B. полные значения `ReturnValuesReuse` — словарь будущей enum-колонки;
  C. булевы свойства — распределение значений (пустое значение встречается реже
     явного, поэтому NULL и false в схеме различимы).
"""
import collections
import json
import pathlib
import re

BASE = pathlib.Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")
PROPS = (
    "Global", "Privileged", "Server", "ServerCall", "ExternalConnection",
    "ClientManagedApplication", "ClientOrdinaryApplication", "ReturnValuesReuse",
    "Comment",
)
BOOL_PROPS = PROPS[:7]

TAG_RE = re.compile(
    r"<(?:\w+:)?(%s)\b[^>]*>(.*?)</(?:\w+:)?\1>" % "|".join(PROPS), re.S
)


def main():
    report = {}
    for dump in DUMPS:
        cat = BASE / dump / "CommonModules"
        if not cat.exists():
            report[dump] = {"dir": False}
            continue
        tags = collections.Counter()
        enum_vals = collections.Counter()
        bools = collections.Counter()
        files = 0
        for path in cat.rglob("*.xml"):
            if path.parent.name == "Ext":
                continue
            files += 1
            text = path.read_bytes().decode("utf-8-sig", "replace")
            for m in TAG_RE.finditer(text):
                name, body = m.group(1), " ".join(m.group(2).split())
                tags[name] += 1
                if name == "ReturnValuesReuse":
                    enum_vals[body or "<EMPTY>"] += 1
                elif name in BOOL_PROPS:
                    bools[f"{name}={body or '<EMPTY>'}"] += 1
        report[dump] = {
            "dir": True,
            "files": files,
            "tags": dict(tags),
            "ReturnValuesReuse": dict(enum_vals),
            "bool_values": dict(bools),
        }
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
