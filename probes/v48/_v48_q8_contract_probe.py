"""Зонд V48 (замер поведения по закрытому вопросу Q8 и позиции O9): состояние конвейера при отказе стадии.

Три факта, все читаются из кода, а не из плана:

1. что конвейер делает при отказе стадии — `src/configuration_loader.py`: ищутся ветки
   `if not <stage>.get("success")` и то, чем они заканчиваются (`warnings.append`,
   `load_incomplete`, вызов `_stop_here(...)` — остановка по решению Q8, вариант A);
2. итог: сколько строк `"success": True` осталось и сколько раз в модуле встречается ключ
   `stopped_stage` (признак остановки);
3. дублирования определений в модуле контракта — `src/configuration_load_contract.py` через
   `ast`: имена `FunctionDef`, встречающиеся более одного раза (позиция O9 плана; удалением
   мёртвого определения закрыт критерий 6б шага П8).

Зонд ничего не пишет и ничего не утверждает нормой: он называет состояние кода на дату
пробега. Действующий норматив — карточки `rules:core-rules:functional:load-catalog` и
`…:goal-and-stages`, проверка — `_v48_p8_stop_probe.py`. Запуск:
`python _v48_q8_contract_probe.py`.
"""
import ast
import io
import re
import sys

LOADER = r"src\configuration_loader.py"
CONTRACT = r"src\configuration_load_contract.py"
STAGES = ("root_modules", "child_objects", "session_parameters", "object_modules")


def read(path: str) -> str:
    return io.open(path, encoding="utf-8", errors="replace").read()


def main() -> int:
    loader = read(LOADER)
    lines = loader.splitlines()

    print("=== 1. что конвейер делает при отказе стадии ===")
    for index, line in enumerate(lines, 1):
        if re.search(r"if not (\w+)\.get\(\"success\"\)", line):
            stage = re.search(r"if not (\w+)\.get\(\"success\"\)", line).group(1)
            body = lines[index:index + 30]
            actions = []
            if any("warnings.append" in b for b in body):
                actions.append("warnings.append")
            if any("load_incomplete = True" in b for b in body):
                actions.append("load_incomplete = True")
            if any("_stop_here(" in b or "_stage_stop(" in b for b in body):
                actions.append("остановка конвейера (Q8, вариант A)")
            if any(re.search(r"^\s*return \{", b) for b in body):
                actions.append("return (остановка слоя заголовка)")
            print(f"строка {index}: отказ {stage} -> {actions or ['нет ветки отказа']}")
    prints = [i for i, l in enumerate(lines, 1) if '"success": True' in l]
    print(f'строк `"success": True` в итоговом ответе: {len(prints)} {prints}')
    print(f'ключ `stopped_stage` в модуле: {loader.count("stopped_stage")} '
          f"(0 = признака остановки нет)")
    print(f'вызовов остановки `_stop_here(`: {loader.count("_stop_here(")} '
          f"(0 = стадия не останавливает конвейер)")
    print(f'ответ стадии создаётся до вызова: '
          f'{sum(1 for name in ("root_modules_defaults()", "child_objects_defaults()", "session_parameters_defaults()", "object_modules_defaults()") if f"= {name}" in loader)} из {len(STAGES)}')

    print()
    print("=== 2. дублирования определений в модуле контракта ===")
    tree = ast.parse(read(CONTRACT))
    counts = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            counts.setdefault(node.name, []).append(node.lineno)
    duplicates = {name: linenos for name, linenos in counts.items() if len(linenos) > 1}
    if not duplicates:
        print("дублирований нет")
    for name, linenos in sorted(duplicates.items()):
        print(f"⚠️ {name}: {len(linenos)} определения — строки {linenos}")
    interesting = {name: linenos for name, linenos in counts.items() if "defaults" in name}
    print("функции контракта *_defaults():",
          {name: linenos[0] for name, linenos in sorted(interesting.items())})
    return 0


if __name__ == "__main__":
    sys.exit(main())
