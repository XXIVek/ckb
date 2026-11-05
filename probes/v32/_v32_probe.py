import io
import re
import sys

sys.path.insert(0, "src")
from configuration_meta_parser import parse_configuration_meta  # noqa: E402

FIXTURE = r"C:\1C_LLM\LoadDoc\Configurations\XML_files\Config_NULL\Configuration.xml"

raw = io.open(FIXTURE, encoding="utf-8").read()
print("file chars:", len(raw))
m = re.search(r"<MetaDataObject[^>]*>", raw)
print("root tag:", (m.group()[:150] if m else "NONE"))

parsed = parse_configuration_meta(FIXTURE)
print("success:", parsed.get("success"), "error:", parsed.get("error"))
print("uuid:", parsed.get("uuid"))
print("name:", parsed.get("name"))
row = parsed.get("configuration") or {}
for key in sorted(row):
    value = row[key]
    if value in (None, "", [], {}):
        continue
    print("  field", key, "=", str(value)[:120])
print("counts:")
for key, value in sorted((parsed.get("counts") or {}).items()):
    print("  ", key, "=", str(value)[:200])
print("warnings:")
for w in parsed.get("warnings") or []:
    print("  -", w)
