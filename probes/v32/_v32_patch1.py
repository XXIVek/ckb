import io

PATH = "src/config_load_router.py"
OLD = """                # Провенанса у строки конфигурации нет (решение D-C): вердикт сравнения
                # источника здесь не вычисляется и выдумывать его нельзя.
"""
NEW = """                # Узел V32: привязки внешних объектов к снятой строке остаются числами
                # configuration_id без строки — внешнего ключа нет (узел V20.1), значит они
                # стали битыми. Карточка обязана это назвать: оператор иначе узнает о битой
                # ссылке только из карточки объекта. Число и имена берём из ответа загрузчика
                # (`bound_external_objects`, `bound_external_object_names`), выдумывать их
                # карточка не вправе.
                bound_objects = int(replaced.get("bound_external_objects") or 0)
                if bound_objects:
                    names = ", ".join(
                        str(name) for name in replaced.get("bound_external_object_names") or []
                    )
                    lines.append(
                        f"\u26a0\ufe0f Привязка к конфигурации станет битой: привязано внешних "
                        f"объектов {bound_objects} ({names}). Перепривяжите их "
                        f"`set_object_configuration_tool(uuid=\u2026, "
                        f"configuration_id={result.get('id')})` или снимите (внешнего ключа нет, "
                        "узел V20.1)"
                    )
                # Провенанса у строки конфигурации нет (решение D-C): вердикт сравнения
                # источника здесь не вычисляется и выдумывать его нельзя.
"""

with io.open(PATH, encoding="utf-8") as fh:
    text = fh.read()
count = text.count(OLD)
print("occurrences:", count)
if count != 1:
    raise SystemExit(2)
with io.open(PATH, "w", encoding="utf-8", newline="") as fh:
    fh.write(text.replace(OLD, NEW, 1))
print("patched ok")
