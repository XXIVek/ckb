"""Одноразовый пробник (V29): где в эталонной выгрузке объявлены пространства имён xr."""
import re
import sys

sys.path.insert(0, ".")
import validate_create_external_processing as v

ref = v.read_root_xml(v.reference_root_xml())
root = v.root_open_line(ref)
print("REF_PATH:", v.reference_root_xml())
print("XR_DECLS:", re.findall(r'xmlns:xr="[^"]+"', ref))
print("DEFAULT_DECLS:", re.findall(r'xmlns="[^"]+"', ref))
print("ROOT_LINE_CHARS:", len(root))
print("ROOT_HAS_XR:", "xmlns:xr=" in root)
