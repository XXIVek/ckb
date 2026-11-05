import io

s = io.open("src/config_load_router.py", encoding="utf-8").read()
markers = [
    "from configuration_loader import register_configuration",
    "NOT_IMPLEMENTED_VARIANTS = (VARIANT_CONFIGURATION,",
    "VARIANT_CONFIGURATION: register_configuration",
    'status = "name_conflict"',
    "def _configuration_card",
    'existing.get("row_kind") == "configuration"',
    'result.get("existing") or {}',
    "Тот же Name при другом UUID",
    "Инструмента удаления конфигурации в контракте нет",
    "bound_external_object_names",
    "для конфигурации и расширения",
    "заглушку узлом V32",
]
for k in markers:
    print(("OK  " if k in s else "MISS"), k)
print("lines:", len(s.splitlines()))
