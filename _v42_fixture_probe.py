"""Временный зонд (22.10.2026): состав фикстуры MinCfg и записи индекса состава.

Считает каталоги видов, содержимое Ext/, а по ConfigDumpInfo.xml — записи по
корневому виду и формы идентификаторов. Нужен для датированного снимка эталона.
"""
import collections
import io
import os
import re

FIXTURE = r"C:\1C_LLM\LoadDoc\Configurations\XML_files\MinCfg"

dirs = sorted(n for n in os.listdir(FIXTURE) if os.path.isdir(os.path.join(FIXTURE, n)))
views = [d for d in dirs if d != "Ext"]
print("dirs total:", len(dirs), "view dirs:", len(views))
print("Ext:", sorted(os.listdir(os.path.join(FIXTURE, "Ext"))))

text = io.open(os.path.join(FIXTURE, "ConfigDumpInfo.xml"), encoding="utf-8").read()
entries = re.findall(r'<Metadata name="([^"]+)"\s+id="([^"]+)"', text)
print("index entries:", len(entries))
by_root = collections.Counter(n.split(".")[0] for n, _ in entries)
print("root kinds:", len(by_root))
for kind, cnt in sorted(by_root.items()):
    print("   ", kind, cnt)

forms = collections.Counter()
odd = []
for name, ident in entries:
    if re.fullmatch(r"[0-9a-f-]{36}", ident):
        forms["canonical_v4"] += 1
    elif re.fullmatch(r"[0-9a-f-]{36}\.\d+", ident):
        forms["composite"] += 1
    else:
        forms["suffixed"] += 1
        odd.append((name, ident))
print("id forms:", dict(forms))
print("suffixed entries:", odd)
print("configVersion as attribute:", len(re.findall(r'configVersion="', text)))
print("ConfigVersions blocks:", len(re.findall(r"<ConfigVersions", text)))

print("--- root Configuration entries ---")
for name, ident in entries:
    if name.split(".")[0] == "Configuration":
        print("   ", name, ident)

