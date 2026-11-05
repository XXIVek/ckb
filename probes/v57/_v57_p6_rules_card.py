#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""Узел V57, шаг П6: регистрация постоянной проверки в слое core-rules.

Правятся пять карточек (строки БД через `mcp_tools_api.update_snippet` — прежнее
содержимое уходит в `snippet_audit_log`, а не теряется):

* `rules:core-rules:checks:index` (6158) — снимается ДУБЛЬ строки проб V57 (его внёс
  неидемпотентный шаг П5: тот же дефект, что назван guard'ом узла V52), хвост строки
  приводится к факту П6, ниже вставляется строка постоянной проверки;
* `rules:core-rules:functional:load-catalog` (6148),
  `rules:core-rules:functional:goal-and-stages` (6225),
  `rules:core-rules:load-functional-options-parameters-tool` (6261) — разделы `CHECK`
  больше не обещают проверку будущего времени: файл существует и прогнан;
* `rules:core-rules:journal:node:v57` (6262) — абзац шага П6 и правка перечня
  незакрытого (П6 больше не незакрыт).

Идемпотентность: каждая правка ищется гибким образцом (переносы строк читаются как `\s+`);
отсутствие образца после повторного прогона — норма для уже внесённой правки, а не удвоение
текста (прецедент guard'а узла V52, названный планом раздела 7 П5).

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python _v57_p6_rules_card.py            # применяет правки
    python _v57_p6_rules_card.py --check    # только ищет образцы, ничего не пишет
"""
import re
import sys

sys.path.insert(0, "src")
from mcp_tools_core import _get_pool          # noqa: E402
from mcp_tools_api import update_snippet      # noqa: E402

CHECK = "tools/check_v57_functional_options_parameters.py"
PROBE_ROW_HEAD = ("| `python _v57_p1_ddl_probe.py`, `python _v57_p3_offline_probe.py`, "
                  "`python _v57_p5_stage_probe.py`")

TAIL_COMMON_OLD = ("её заводит шаг П6 плана узла, эталоном ей служит замер 1.1 и замер 2.1 "
                   "плана (2/0/5/7 по трём ногам круга, 14 строк вида и 34 строки применения), "
                   "а на шаге П5 имя названо планом, а не работающей проверкой")
TAIL_COMMON_NEW = ("постоянная проверка узла заведена шагом П6 05.11.2026 — 397 сверок / "
                   "0 провалов / 0 пропусков по четырём выгрузкам, одиночный прогон выгрузки — "
                   "170 / 0 / 1 с названной причиной пропуска; эталоном ей служат замер 1.1 и "
                   "замер 2.1 плана (2/0/5/7 по трём ногам круга, 14 строк вида и 34 строки "
                   "применения)")

PROBE_TAIL_OLD = ("Постоянная проверка узла `tools/check_v57_functional_options_parameters.py` "
                  "этим шагом не заводится: её заводит шаг П6 плана узла, эталоном ей служит "
                  "замер 1.1 и замер 2.1 плана")
PROBE_TAIL_NEW = ("Постоянная проверка узла заведена шагом П6 — строкой ниже (прогон "
                  "05.11.2026 — 397 сверок / 0 провалов / 0 пропусков); эталоном ей служат "
                  "замер 1.1 и замер 2.1 плана")

LOAD_CATALOG_OLD = ("Постоянная проверка узла `tools/check_v57_functional_options_parameters.py` "
                    "этим шагом не заводится: " + TAIL_COMMON_OLD + ".")
LOAD_CATALOG_NEW = ("Постоянная " + TAIL_COMMON_NEW + ".")

GOAL_STAGES_OLD = ("постоянная проверка узла `tools/check_v57_functional_options_parameters.py` "
                   "этим шагом не заводится: " + TAIL_COMMON_OLD + ";")
GOAL_STAGES_NEW = (TAIL_COMMON_NEW + ";")

TOOL_CARD_OLD = ("постоянная проверка узла `tools/check_v57_functional_options_parameters.py` "
                 "этим шагом не заводится: " + TAIL_COMMON_OLD + ";")
TOOL_CARD_NEW = (TAIL_COMMON_NEW + ";")

JOURNAL_TAIL_OLD = ("Постоянной проверки узла `tools/check_v57_functional_options_parameters.py` "
                    "(шаг П6) на этом шаге нет — она заводится шагом П6 планом узла, и тексты "
                    "правил не обещают прогона, которого нет.")
JOURNAL_TAIL_NEW = ("Постоянная проверка узла `tools/check_v57_functional_options_parameters.py` "
                    "заведена следующим шагом П6 — абзацем ниже.")

JOURNAL_NOT_DONE_OLD = ("Что узлом НЕ закрыто: шаги П6–П9 (постоянная проверка узла, модель A–H "
                        "и документ сценариев, регрессия стоп-проб V48–V56 к пятнадцати стадиям, "
                        "итог узла);")
JOURNAL_NOT_DONE_NEW = ("Что узлом НЕ закрыто: шаги П7–П9 (модель A–H и документ сценариев, "
                        "регрессия стоп-проб V48–V56 к пятнадцати стадиям, итог узла);")

PERMANENT_ROW = (
    "| `python tools/check_v57_functional_options_parameters.py` (по кругу выгрузок или одной "
    "выгрузке: MinCfg, KomMag, BGU2, BP3) | свойства параметров функциональных опций и круг их "
    "применения `<Use>` (узел V57, шаг П6): инвариант четырёх ног круга «файлы "
    "`FunctionalOptionsParameters/` ↔ индекс состава (`FunctionalOptionsParameter.<Имя>`) ↔ "
    "перечень `configurations.functional_options_parameters` ↔ имена в корне `Configuration.xml`» "
    "и строки таблицы как пятая сторона того же множества — сравнение попарно во все стороны; "
    "строка вида и строки применения против разбора круга ТЕМ ЖЕ модулем и против независимой "
    "меры по тексту файла (четыре тега свойств, блок `<Use>`, элемент `xr:Item` с атрибутом "
    "`xsi:type` — того, что CHECK не выражает); ключ пары (`functional_option_parameter_id`, "
    "`ordinal`) и отсутствие отдельного ключа по цели — осознанно (Q7); словари состояний "
    "сверяются с CHECK'ом КОНКРЕТНОЙ таблицы по имени колонки, а `target_resolve_state` — с "
    "ограничением `..._resolve_matches_ref`, потому что отдельного `*_known` в DDL нет "
    "осознанно; повторное разрешение целей индексом СВОЕЙ конфигурации полным точечным именем "
    "записи (`index_row_key`, а не `object_name` — короткое имя давало бы ложные промахи на "
    "срезах и псевдозаписях, урок V48/V50/V56), состояние, `object_id`, `object_uuid` и остаток "
    "пути обязаны совпасть с сохранёнными; формы адреса цели `dimension` 30 / `object` 4 и "
    "классы `InformationRegister` 30 / `Catalog` 4 пересчитываются по адресу, а не берутся из "
    "состояния (M5); маска `FunctionalOption%` против точного предиката — 4/229/546 против "
    "2/5/7, разница равна ровно записям позиции 2.11 (число плана раздела 1.2 «16» исправлено "
    "этим же шагом: прогон по живой БД даёт 4); пустой круг `KomMag` читается ответом с "
    "наблюдением `directory_missing` и `NULL` перечня заголовка, а не отказом; витрины "
    "текущности, сироты, строки вне витрин и дублирующая строка применения; контракт стадии S4l "
    "— порядок `s4k → s4l → s4b`, круг снятия с применением первым (M7), нулевой контракт со "
    "ВСЕМИ ключами расхождений ног `index_only`/`file_only`/`uuid_mismatch` (эти три ключа "
    "нулевым контрактом не назывались — вскрыто самой проверкой и исправлено тем же шагом), "
    "отсутствие групп `kinds` названо решением Q5, а не молчанием; реестр из 15 инструментов "
    "ядра читается текстом файла, а не памятью проверки; неприкосновенность чужих кругов, "
    "включая витрины позиции 2.11 (765 опций, 10 063 цели) и `bsl_modules`. Прогон 05.11.2026 — "
    "397 сверок / 0 провалов / 0 пропусков по четырём выгрузкам; одиночный прогон `MinCfg` или "
    "`KomMag` — 170 / 0 / 1 (пропуск назван причиной: суммы корпуса при неполном круге)|")

JOURNAL_P6_ANCHOR = "Своя текстовая находка шага: аудит `_named_artifacts_audit.py`"
JOURNAL_P6_TEXT = r"""Шаг П6 (05.11.2026) — постоянная проверка узла `tools/check_v57_functional_options_parameters.py`:
девять контуров по образцу `tools/check_v56_functional_options.py` (две таблицы узла, а не одна;
отдельным контуром — инвариант пары «строка вида ↔ строки применения», который CHECK
`functional_option_parameters_use_state_matches_targets` выражает, а человек — нет). Прогон по
четырём выгрузкам — 397 сверок / 0 провалов / 0 пропусков (7 строк INFO — наблюдения, а не
проверки: строки витрин, объёмы чужих индексов, отсутствие строк второй ревизии); одиночный
прогон `MinCfg` и `KomMag` — 170 / 0 / 1, пропуск назван причиной (суммы корпуса при неполном
круге).

Три позиции вскрыла сама проверка, а не пробы шагов П1/П3/П5:

1. нулевой контракт стадии S4l не перечислял ключей расхождений ног `index_only`, `file_only`,
   `uuid_mismatch` — «расхождений нет» и «расхождения не сравнивались» читались одним ответом
   (правило C2); ключи внесены в нулевой контракт `src/configuration_load_contract.py` тем же
   шагом;
2. разрешение целей индексом по короткому имени (`object_name`) давало бы ложные промахи на
   срезах и псевдозаписях — ключом служит полное точечное имя записи индекса (`index_row_key`):
   урок V48/V50/V56 и правило V43 (индекс состава вторым источником не становится);
3. регулярное выражение имени элемента перечня (`ITEM_TAG_RE`) теряло префикс пространства имён,
   из-за чего `item_tag` читался как `Item` вместо `xr:Item`; состояние `md_object_ref` при этом
   оставалось верным — ошибка пряталась за правильным ответом.

План раздела 1.2 называл маску по началу имени «16 / 229 / 546»; прогон по живой БД даёт
4 / 229 / 546 (MinCfg 2+2, BGU2 224+5, BP3 539+7), и разница с точным предикатом 2 / 5 / 7 равна
ровно записям позиции 2.11. Число плана исправлено тем же шагом, различие названо отдельной
проверкой контура 3: сгладить его — значит подтвердить неверное число.

Правка карточек слоя вскрыла дефект прежнего шага: строка реестра
`rules:core-rules:checks:index` была записана дважды (неидемпотентная вставка
`_v57_p5_rules_card.py` — тот же класс дефекта, что назван guard'ом узла V52). Дубль снят шагом
П6, повторный прогон патчера — «без изменений»; разделы `CHECK` трёх живых карточек приведены к
настоящему времени, потому что файл проверки существует и прогнан.

"""


def flex(text):
    """Гибкий образец поиска: переносы строк и пропуски пробелов читаются как `\\s+`."""
    return r"\s+".join(re.escape(part) for part in text.split())


def dedupe_line(text, head):
    """Оставить первую строку, начинающуюся с head, снять её повторы."""
    kept, seen, removed = [], 0, 0
    for line in text.split("\n"):
        if line.startswith(head):
            if seen:
                removed += 1
                continue
            seen += 1
        kept.append(line)
    return "\n".join(kept), seen, removed


def insert_after_line(text, head, block):
    lines = text.split("\n")
    index = next((i for i, line in enumerate(lines) if line.startswith(head)), None)
    if index is None:
        return text, False
    lines.insert(index + 1, block.rstrip("\n"))
    return "\n".join(lines), True


def insert_before_line(text, anchor, block):
    lines = text.split("\n")
    index = next((i for i, line in enumerate(lines) if anchor in line), None)
    if index is None:
        return text, False
    lines.insert(index, block.rstrip("\n"))
    return "\n".join(lines), True


PLAN = {
    6158: [
        ("dedupe", PROBE_ROW_HEAD, "дубль строки проб П5"),
        ("sub", PROBE_TAIL_OLD, PROBE_TAIL_NEW, "хвост строки проб — П6 сделан"),
        ("insert_after", PROBE_ROW_HEAD, PERMANENT_ROW, "строка постоянной проверки V57"),
    ],
    6148: [("sub", LOAD_CATALOG_OLD, LOAD_CATALOG_NEW, "CHECK карточки конвейера")],
    6225: [("sub", GOAL_STAGES_OLD, GOAL_STAGES_NEW, "CHECK карточки стадий")],
    6261: [("sub", TOOL_CARD_OLD, TOOL_CARD_NEW, "CHECK карточки инструмента")],
    6262: [
        ("sub", JOURNAL_TAIL_OLD, JOURNAL_TAIL_NEW, "хвост абзаца П5 — ссылка на П6"),
        ("sub", JOURNAL_NOT_DONE_OLD, JOURNAL_NOT_DONE_NEW, "перечень незакрытого"),
        ("insert_before", JOURNAL_P6_ANCHOR, JOURNAL_P6_TEXT, "абзац шага П6"),
    ],
}

CHECK_ONLY = "--check" in sys.argv[1:]
REASON = ("узел V57 шаг П6: постоянная проверка tools/check_v57_functional_options_parameters.py "
          "заведена и прогнана (397 сверок / 0 провалов / 0 пропусков по четырём выгрузкам, "
          "одиночный прогон 170 / 0 / 1); снят дубль строки реестра, внесённый П5; нулевой "
          "контракт стадии дополнен ключами расхождений ног")

pool = _get_pool()
conn = pool.getconn()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT id, question, answer FROM knowledge_snippets WHERE id = ANY(%s) "
                    "ORDER BY id", (list(PLAN),))
        rows = cur.fetchall()
finally:
    pool.putconn(conn)

missing = 0
for sid, question, answer in rows:
    print("=" * 78)
    print(f"id={sid} {question} было: {len(answer)}")
    text = answer
    for op in PLAN[sid]:
        kind = op[0]
        if kind == "dedupe":
            new_text, found, removed = dedupe_line(text, op[1])
            changed = removed > 0
            status = f"снято дублей: {removed}" if changed else f"дублей нет (строк: {found})"
        elif kind == "sub":
            hit = re.search(flex(op[1]), text)
            if hit:
                new_text = text[:hit.start()] + op[2] + text[hit.end():]
                changed, status = True, "внесено"
            elif re.search(flex(op[2]), text):
                new_text, changed = text, False
                status = "уже внесено"
            else:
                new_text, changed = text, False
                status = "ОБРАЗЕЦ НЕ НАЙДЕН"
                missing += 1
        elif kind == "insert_after":
            if re.search(flex("| `python " + CHECK + "` (по кругу"), text):
                new_text, changed = text, False
                status = "уже внесено"
            else:
                new_text, ok = insert_after_line(text, op[1], op[2])
                changed = ok
                status = "внесено" if ok else "ЯКОРЬ НЕ НАЙДЕНА"
                if not ok:
                    missing += 1
        elif kind == "insert_before":
            if re.search(flex("Шаг П6 (05.11.2026) — постоянная проверка узла"), text):
                new_text, changed = text, False
                status = "уже внесено"
            else:
                new_text, ok = insert_before_line(text, op[1], op[2])
                changed = ok
                status = "внесено" if ok else "ЯКОРЬ НЕ НАЙДЕНА"
                if not ok:
                    missing += 1
        else:
            raise SystemExit(f"неизвестная операция: {kind}")
        print(f"  [{op[-1]}] {kind}: {status}")
        text = new_text
    if text == answer:
        print("  итог: без изменений")
        continue
    print(f"  стало: {len(text)}")
    if CHECK_ONLY:
        print("  запись не выполнена (--check)")
        continue
    print("  " + str(update_snippet(sid, new_answer=text, reason=REASON)))

print("=" * 78)
print(f"несовпадения образцов: {missing}")
sys.exit(1 if missing else 0)

