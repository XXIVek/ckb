# -*- coding: utf-8 -*-
"""_v49_o1_value_semantics.py — замер позиции O1: что означает `<value>` в файле прав (узел V49).

Зачем. Словарь состояний значения права замкнут П2 (`configuration_roles.py`,
`right_value_state`): `true` → `granted`, `false` → `denied`. Имена состояний утверждают
смысл, а не текст выгрузки, — и это открытая позиция O1 плана
(`docs/CONFIGURATION_ROLES_PLAN.md`, раздел 9): KomMag даёт 2 899 прав со значением `false`,
MinCfg — 361 из 362. Если `false` читается как «роль не может», то роль KomMag не даёт
ничего, и это обязано быть проверено, а не принято по имени состояния. Формулировки
карточки правила `rules:core-rules:load-roles-tool` и docstring инструмента обязаны
описывать состояния как значения выгрузки, а не как разрешение действовать, — поэтому замер
делается до карточки, а не после.

Как измеряется (план, раздел 9, O1): роль `АдминистраторСистемы` сравнивается со своим же
описанием `Comment` в BGU2 и BP3 — описание пишет, что роль даёт, а файл прав — что
записано значением. Добавлены и другие системные роли, имя или описание которых называет их
содержание (`Чтение`, `Редактирование`, `ПолныеПрава`, ...): у роли, которую описание
объявляет «только чтение», права на изменение не могут быть записаны выданными, иначе
несогласованно. Разбор берётся существующим слоем (`iter_role_files`, `read_role_metadata`,
`read_rights_file`) — новых разборов замер не заводит; индекс состава не нужен, разрешение
целей на значение `<value>` не влияет.

Чего замер НЕ доказывает: он не читает документацию платформы и не утверждает, как
платформа трактует значение. Он отвечает на один вопрос — противоречат ли значения тексту
описания той же роли. Вывод («согласуются» / «противоречат» / «данных мало») печатается
по наблюдению, а не по имени состояния.

Запуск:
    python _v49_o1_value_semantics.py            # BGU2, BP3 + контрольные MinCfg/KomMag
    python _v49_o1_value_semantics.py BP3        # любой круг по своему выбору
Код возврата 0 — замер выполнен и хотя бы одна роль сравнена с описанием; 1 — сравнивать
не с чем (ролей из списка нет в выгрузке) или разбор отказал.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_roles as CR  # noqa: E402

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DEFAULT_DUMPS = ("BGU2", "BP3", "MinCfg", "KomMag")

# Имена и описания, по которым содержание роли известно из её же текста: у роли «чтение»
# права на изменение не могут быть выданы, у роли «полные права» — не могут быть отказаны.
# Список — кандидаты, а не утверждение: проверяются только те, что есть в выгрузке.
CANDIDATE_ROLES = (
    "АдминистраторСистемы", "ПолныеПрава", "Чтение", "Редактирование", "Добавление",
    "Удаление", "УстановкаПометкиУдаления", "СнятиеПометкиУдаления", "Проведение",
    "ОтменаПроведения",
)

# Права, по которым проверяется смысл имени роли: у «чтения» — Read/View/Output против
# Edit/Insert/Delete/Update. Имена прав — из замкнутого словаря слоя (Q4).
READ_LIKE_RIGHTS = ("Read", "View", "Output", "Get")
WRITE_LIKE_RIGHTS = ("Edit", "Insert", "Update", "Delete", "Set")
ALL_RIGHTS_LIKE = ("Administration", "DataAdministration")

SUPPORTS = "согласуется"
CONTRADICTS = "противоречит"
NO_SIGNAL = "признаков нет"


def value_breakdown(rights: dict) -> dict:
    """`{имя права: {состояние значения: число}}` по одному файлу прав."""
    out: dict = {}
    for target in rights.get("targets") or []:
        for right in target.get("rights") or []:
            per_name = out.setdefault(right["right_name"], {})
            state = right["right_value_state"]
            per_name[state] = per_name.get(state, 0) + 1
    return out


def granted_names(breakdown: dict) -> set:
    """Имена прав, у которых в файле есть значение `true`."""
    return {name for name, states in breakdown.items() if states.get(CR.VALUE_GRANTED)}


def denied_names(breakdown: dict) -> set:
    """Имена прав, у которых в файле есть значение `false` (и нет `true`)."""
    return {name for name, states in breakdown.items()
            if states.get(CR.VALUE_DENIED) and not states.get(CR.VALUE_GRANTED)}


def verdict(role_name: str, comment: str, breakdown: dict, flags: dict):
    """Согласуется ли текст описания роли с записанными значениями прав.

    Возвращает (вердикт, наблюдения). Ни одно наблюдение не додумывается: если текст роли
    ничего не говорит о чтении/записи, вердикт — «признаков нет», а не «согласуется».

    Сравнение идёт по нормализованному тексту (имя без пробелов — `ПолныеПрава`): без
    нормализации имя роли не читалось бы её же утверждением о содержании, и роль с
    названием «ПолныеПрава» осталась бы строкой «признаков нет» при том, что она и есть
    доказательство (замер 30.10.2026).
    """
    text = " ".join(filter(None, [role_name, comment])).lower().replace(" ", "")
    granted, denied = granted_names(breakdown), denied_names(breakdown)
    notes = []

    if any(word in text for word in ("чтение", "просмотр", "толькопоказ")):
        read_granted = sorted(r for r in READ_LIKE_RIGHTS if r in granted)
        write_denied = sorted(r for r in WRITE_LIKE_RIGHTS if r in denied)
        write_granted = sorted(r for r in WRITE_LIKE_RIGHTS if r in granted)
        if read_granted and write_denied and not write_granted:
            notes.append(f"роль названа читающей: выданы {read_granted}, "
                         f"отказано {write_denied} — значения согласуются с названием")
            return SUPPORTS, notes
        if write_granted:
            notes.append(f"роль названа читающей, но выданы права на изменение: "
                         f"{write_granted} — значения противоречат названию")
            return CONTRADICTS, notes
        notes.append("роль названа читающей, но ни читающих, ни пишущих прав "
                     "со значением в файле нет")
        return NO_SIGNAL, notes

    if any(word in text for word in ("полныеправа", "всеправа", "администратор")):
        all_like = sorted(r for r in ALL_RIGHTS_LIKE if r in granted)
        all_denied = sorted(r for r in ALL_RIGHTS_LIKE if r in denied)
        flags_seen = {column: value for column, value in (flags or {}).items()
                      if value is not None}
        notes.append(f"флаги содержимого прав: {flags_seen or '<ни одного флага>'}")
        if all_like and not all_denied:
            notes.append("роль названа дающей всё: права администрирования записаны "
                         f"значением true ({all_like}) — при чтении false=отказано это "
                         "согласуется")
            return SUPPORTS, notes
        if all_denied:
            notes.append("роль названа дающей всё, но её права администрирования "
                         f"({all_denied}) записаны значением false — при чтении "
                         "false=«роль не может» название противоречит значениям")
            return CONTRADICTS, notes
        notes.append("роль названа дающей всё, но прав администрирования в файле нет")
        return NO_SIGNAL, notes

    return NO_SIGNAL, ["ни имя, ни описание роли не говорят о содержании прав"]


def measure_dump(name: str):
    """Замер по одной выгрузке: список (выгрузка, роль, состояния, вердикт)."""
    layout = DUMP_ROOT / name
    if not layout.exists():
        print(f"\n=== {name}: каталога выгрузки нет — {layout}")
        return []
    by_name, observations = CR.iter_role_files(layout)
    print(f"\n=== {name}: метаданных "
          f"{sum(1 for v in by_name.values() if 'metadata' in v)}, файлов прав "
          f"{sum(1 for v in by_name.values() if 'rights' in v)}, наблюдений формы "
          f"{len(observations)}")

    wanted = [role for role in CANDIDATE_ROLES if role in by_name]
    if not wanted:
        print("   ролей из списка в выгрузке нет — сравнивать не с чем")
        return []

    results = []
    for role in wanted:
        files = by_name[role]
        meta_file, rights_file = files.get("metadata"), files.get("rights")
        meta = CR.read_role_metadata(meta_file["path"], role) if meta_file else None
        if not meta or not meta.get("success"):
            print(f"   {role}: метаданные не разобраны — {(meta or {}).get('reason')}")
            continue
        comment = (meta["meta"].get("comment") or "").strip()
        if not rights_file:
            print(f"   {role}: файла прав нет; описание: {comment[:120]}")
            continue
        rights = CR.read_rights_file(rights_file["path"])
        if not rights.get("success"):
            print(f"   {role}: файл прав не разобран — {rights.get('reason')}")
            continue
        breakdown = value_breakdown(rights)
        total = sum(sum(states.values()) for states in breakdown.values())
        states_total: dict = {}
        for states in breakdown.values():
            for state, count in states.items():
                states_total[state] = states_total.get(state, 0) + count
        flags = {column: value for column, value in (rights.get("flags") or {}).items()
                 if value is not None}
        state, notes = verdict(role, comment, breakdown, flags)
        print(f"   роль {role}: прав {total}, состояний {states_total}, флаги {flags}")
        print(f"      описание (Comment): {comment[:200] or '<пусто>'}")
        top = sorted(breakdown.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[:10]
        for right_name, states in top:
            print(f"      {right_name}: {states}")
        for note in notes:
            print(f"      наблюдение: {note}")
        results.append((name, role, states_total, state))
    return results


def main(argv=None) -> int:
    dumps = tuple(argv) or DEFAULT_DUMPS
    found = []
    for name in dumps:
        found.extend(measure_dump(name))

    print("\n" + "=" * 70)
    if not found:
        print("ИТОГ: сравнивать не с чем — ни одной роли из списка не найдено")
        return 1
    supports = [item for item in found if item[3] == SUPPORTS]
    contradicts = [item for item in found if item[3] == CONTRADICTS]
    print(f"ИТОГ: ролей сравнено {len(found)}, согласуется {len(supports)}, "
          f"противоречит {len(contradicts)}")
    for dump, role, states_total, state in found:
        print(f"  • {dump} / {role}: {state} — {states_total}")
    if contradicts:
        print("вывод: значения `<value>` противоречат названиям и описаниям ролей — "
              "состояния `granted`/`denied` описывают текст строки перечисления прав, а "
              "не правомочие роли; карточка правила и docstring обязаны называть значения "
              "выгрузки (true/false), а не «роль может / не может»")
    elif supports:
        print("вывод: значения `<value>` с текстами описаний ролей согласуются; карточка "
              "инструмента всё равно обязана называть состояния значением выгрузки "
              "(true/false), а не правомочием роли — вывод сделан по текстам выгрузок, "
              "а не по документации платформы")
    else:
        print("вывод: данных для вывода о смысле значения нет — состояния в карточке "
              "обязаны называть текст выгрузки, а не интерпретацию")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
