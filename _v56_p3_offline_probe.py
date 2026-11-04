#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""П3 узла V56: офлайн-проверка парсера круга `FunctionalOptions` (БД не трогает).

Зачем. П4 (писатель) и П5 (стадия) начинают писать код только когда разбор круга назван
числами и состояниями. Парсер проверяется на трёх рядах доказательств.

1. Синтетические fixtures — случаи, которых в эталонных выгрузках нет (замеры 2.1…2.3
   плана дают один наблюдённый словарь форм): ссылка `Location` с состояниями
   `prefix_only`, `unresolved`, `empty_value`, `absent` и формой `other`; тег свойства вне
   словаря; значение флага вне `true`/`false`; отсутствующий флаг `PrivilegedGetMode`;
   пустой перечень `<Content/>` и отсутствие самого тега; элемент перечня чужого тега и
   элемент без имени цели; повтор цели внутри перечня; повтор тега свойства; битый XML;
   пустой `Name`; расхождения с индексом состава (`index_only` / `file_only` /
   `uuid_mismatch`); вид-сосед `FunctionalOptionsParameter` в индексе (не должен попасть в
   круг — раздел 1.2 плана); отсутствие каталога вида и непереданный индекс состава.
   В эталонных корпусах этих состояний нет, поэтому проверка состояний обязана быть своей,
   а не выведенной из корпусов.

2. Четыре эталонные выгрузки — ожидаемые числа берутся из П0/M1 (`_v56_p0_probe.py`,
   `_v56_m1_probe.py`, разделы 1–2 плана): файлы 2/0/224/539 (всего 765), цели перечня
   0/0/3 274/6 789 (всего 10 063, максимум 438 на файл, 21 класс цели), состояния ссылки
   `Location` (`exact` 765, формы `single` 605 / `register_resource` 154 / `attribute` 6),
   состояния перечня (`with_content` 562, `empty_content` 203), флаг `PrivilegedGetMode`
   (`true` 764, `false` 1 — единственный `false` в MinCfg), расхождений с индексом — ноль.
   Расхождение с П0 — сигнал о том, что парсер или замер разошлись; цифру плана она не
   меняет, но обязана быть названа.

3. Инварианты строк — проверки, которые кладёт схема (`functional_options_*`,
   `functional_option_content_*`), прогоняются по строкам разбора ДО открытия базы.
   Писатель П4 иначе падал бы на CHECK после записи половины круга. Плюс словарь ключей
   строк сверяется со списком колонок `functional_options` / `functional_option_content`
   из текста `migrate_v56_functional_options.sql` (БД не открывается): несуществующая
   колонка всплывает здесь, а не на середине записи.

Ничего в БД зонд не пишет и ничего не чинит молча: провал — строка отчёта и ненулевой код
выхода.
"""
from __future__ import annotations

import re
import sys
import tempfile
import uuid as uuid_lib
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
# Тот же порядок, что у офлайн-зондов V49/V50: корень проекта и каталог `src`
# (модули слоя импортируются как верхние имена, а не как `src.`).
for _path in (str(ROOT), str(ROOT / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# Отчёт печатается кириллицей со стрелками состояний: консоль Windows по умолчанию
# cp1251, и печать падала бы на коде страницы, а не на разборе.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from config_dump_info_parser import find_config_dump_info, parse_config_dump_info  # noqa: E402
from configuration_functional_options import (  # noqa: E402
    CONTENT_EMPTY, CONTENT_WITH, DIR_NAME, LOCATION_ABSENT, LOCATION_EMPTY_VALUE,
    LOCATION_FORM_ATTRIBUTE, LOCATION_FORM_OTHER, LOCATION_FORM_REGISTER_RESOURCE,
    LOCATION_FORM_SINGLE, OPTION_LINK_KEY, PROPS_ABSENT, PROPS_ALL_KNOWN,
    PROPS_UNKNOWN_TAG, PROPS_UNKNOWN_VALUE, TARGET_EXACT, TARGET_PREFIX_ONLY,
    TARGET_UNRESOLVED, collect_functional_options, read_registration_file,
)

# Ожидаемые числа — разделы 1–2 плана docs/CONFIGURATION_FUNCTIONAL_OPTIONS_PLAN.md
# (`_v56_p0_probe.py`, `_v56_m1_probe.py`). У `KomMag` каталога вида нет ни файлом, ни
# строкой индекса (замер 1.1) — ответ обязан быть пустым кругом с наблюдением
# directory_missing, а не отказом.
EXPECTED = {
    "MinCfg": {"files": 2, "targets": 0, "distinct": 0, "max_targets": 0,
               "loc_exact": 2, "single": 2, "register_resource": 0, "attribute": 0,
               "other": 0, "content_with": 0, "content_empty": 2,
               "priv_true": 1, "priv_false": 1},
    "KomMag": {"files": 0, "targets": 0, "distinct": 0, "max_targets": 0,
               "loc_exact": 0, "single": 0, "register_resource": 0, "attribute": 0,
               "other": 0, "content_with": 0, "content_empty": 0,
               "priv_true": 0, "priv_false": 0},
    "BGU2": {"files": 224, "targets": 3274, "distinct": 3144, "max_targets": 438,
             "loc_exact": 224, "single": 209, "register_resource": 14, "attribute": 1,
             "other": 0, "content_with": 161, "content_empty": 63,
             "priv_true": 224, "priv_false": 0},
    "BP3": {"files": 539, "targets": 6789, "distinct": 5704, "max_targets": 402,
            "loc_exact": 539, "single": 394, "register_resource": 140, "attribute": 5,
            "other": 0, "content_with": 401, "content_empty": 138,
            "priv_true": 539, "priv_false": 0},
}

# Классы целей перечня `<Content>` по всему корпусу (раздел 2.2 плана, M1): 21 вид
# метаданных, 10 063 цели. Сумма значений равна числу целей — это и есть проверка полноты
# словаря, а не отдельное число.
EXPECTED_KINDS = {
    "Document": 4881, "InformationRegister": 1261, "Catalog": 1112, "CommonCommand": 596,
    "DataProcessor": 516, "Report": 504, "Enum": 324, "AccumulationRegister": 266,
    "Subsystem": 240, "Constant": 96, "DocumentJournal": 93, "CommonForm": 89,
    "ChartOfCharacteristicTypes": 24, "Task": 16, "AccountingRegister": 13,
    "ChartOfAccounts": 11, "CommonAttribute": 8, "BusinessProcess": 5,
    "ExchangePlan": 3, "ChartOfCalculationTypes": 3, "FilterCriterion": 2,
}
CORPUS_TOTALS = {"files": 765, "targets": 10063, "single": 605,
                 "register_resource": 154, "attribute": 6, "content_with": 562,
                 "content_empty": 203, "priv_true": 764, "priv_false": 1, "kinds": 21}

FAILURES: list = []
REPORT: list = []


def emit(text: str = "") -> None:
    REPORT.append(text)


def check(name: str, ok: bool, detail: str = "") -> None:
    emit(("  OK   " if ok else "  FAIL ") + name + ((" — " + detail) if detail else ""))
    if not ok:
        FAILURES.append(name)


def row_by(rows: List[Dict], name: str) -> Dict:
    for row in rows:
        if row["object_name"] == name:
            return row
    return {}


def targets_of(targets: List[Dict], option_index_name: str) -> List[Dict]:
    """Строки применения одной опции — по ключу строки вида, а не по uuid.

    Ключом служит индексное имя `FunctionalOption.<Имя>`: uuid у двух конфигураций
    совпадает (замер 1.3: 135 общих uuid), поэтому связка по uuid давала бы смешение
    опций разных выгрузок (M1).
    """
    return [target for target in targets
            if target[OPTION_LINK_KEY] == option_index_name]


# ─── синтетические файлы круга ────────────────────────────────────────────────
# Пространства имён — те же, что у файла выгрузки вида (замер: `MinCfg/FunctionalOptions/
# ФункциональнаяОпция2.xml`): разбор снимает префиксы (`_local`), поэтому фикстура обязана
# давать именованные формы, а не «удобные» — иначе проверялся бы разбор своего текста.
HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
        'xmlns:v8="http://v8.1c.ru/8.1/data/core" '
        'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xr="http://v8.1c.ru/8.3/xcf/readable">\n')
TAIL = "</FunctionalOption>\n</MetaDataObject>\n"

# Фикстура обязана быть ближе к форме выгрузки, чем к удобству теста: порядок тегов внутри
# `<Properties>` — порядок замера 2 плана (Name, Synonym, Comment, Location,
# PrivilegedGetMode, Content), потому что пропуск позиции в словаре свойств означал бы
# молчаливую потерю свойства.
def fo_file(obj_uuid: str, body: str, tail: str = "") -> str:
    return (HEAD + f'<FunctionalOption uuid="{obj_uuid}">\n'
            f"\t<Properties>\n{body}\t</Properties>\n{tail}{TAIL}")


def name_tag(name: str) -> str:
    return f"\t\t\t<Name>{name}</Name>\n"


def synonym_tag(text: str) -> str:
    return (f"\t\t\t<Synonym>\n\t\t\t\t<v8:item>\n\t\t\t\t\t<v8:lang>ru</v8:lang>\n"
            f"\t\t\t\t\t<v8:content>{text}</v8:content>\n\t\t\t\t</v8:item>\n"
            f"\t\t\t</Synonym>\n")


def comment_tag(text: str) -> str:
    return f"\t\t\t<Comment>{text}</Comment>\n"


def location_tag(address: str) -> str:
    if address is None:
        return ""
    return f"\t\t\t<Location>{address}</Location>\n"


def privileged_tag(value) -> str:
    if value is None:
        return ""
    return f"\t\t\t<PrivilegedGetMode>{value}</PrivilegedGetMode>\n"


def content_tag(items: str) -> str:
    if items is None:
        return ""
    if not items:
        return "\t\t\t<Content/>\n"
    return f"\t\t\t<Content>\n{items}\t\t\t</Content>\n"


def object_item(target: str, tag: str = "xr:Object") -> str:
    return f"\t\t\t\t<{tag}>{target}</{tag}>\n"


# Адрес типичной фикстуры и цели перечня — значения, которые индекс состава фикстуры
# содержит целиком (замеры 2.1, 2.2 дают `exact` для 765/765 ссылок и 10 063/10 063
# целей, поэтому «нормальный» файл обязан разрешаться целиком, а не состоянием).
# Константы объявлены ДО `full_body`: значения по умолчанию вычисляются при объявлении
# функции, а не при вызове, и объявление их ниже давало бы NameError на строке def.
LOCATION_ADDRESS = "Constant.ИспользоватьОпцию"
ONE_ITEM = object_item("Catalog.Товары")
TWO_ITEMS = ONE_ITEM + object_item("Document.Реализация.Attribute.Контракт")


def full_body(name: str, address: str = LOCATION_ADDRESS, privileged="true",
              items: str = ONE_ITEM, extra: str = "", comment: str = "") -> str:
    """Тело файла с полным набором свойств (позиции 1–6 словаря замера 2)."""
    return (name_tag(name) + synonym_tag(name) + comment_tag(comment or name) + extra
            + location_tag(address) + privileged_tag(privileged) + content_tag(items))


def dump_index(entries) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<ConfigDumpInfo xmlns="http://v8.1c.ru/8.3/xcf/dumpinfo">', "\t<ConfigVersions>"]
    for name, obj_id in entries:
        # configVersion — не идентификатор объекта, а версия метаданий: форма замера V33 —
        # 40 шестнадцатеричных символов, иначе индекс читался бы выдумкой, а не замером.
        version = uuid_lib.uuid4().hex + uuid_lib.uuid4().hex[:8]
        lines.append(f'\t\t<Metadata name="{name}" id="{obj_id}" configVersion="{version}"/>')
    lines += ["\t</ConfigVersions>", "</ConfigDumpInfo>"]
    return "\n".join(lines) + "\n"


DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DDL_FILE = ROOT / "migrate_v56_functional_options.sql"


def build_fixtures(root: Path) -> Dict[str, Tuple[str, str]]:
    """Круг фиктивных выгрузок: по одному файлу на состояние-исключение.

    Возвращает `{ключ: (имя файла, uuid)}` — имена нужны и для записи файлов, и для
    построения индекса состава (в нём задаются расхождения `index_only`, `file_only`,
    `uuid_mismatch`, вид-сосед и чужие виды целей).
    """
    directory = root / DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)

    files = {
        # 1. Полный файл словаря свойств: ссылка разрешается целиком, три цели перечня в
        #    порядке файла, флаг `true` (наблюдённая форма 764 файлов из 765).
        "typical": ("Типичная", "a0000000-0000-0000-0000-000000000001", fo_file(
            "a0000000-0000-0000-0000-000000000001", full_body(
                "Типичная", items=(object_item("Catalog.Товары")
                                   + object_item(
                                       "Document.Реализация.Attribute.Контракт")
                                   + object_item("Subsystem.Раздел"))))),

        # 2. Тег свойства вне словаря (замер 2: ровно 6 тегов в 765/765, XSD вида нет —
        #    замер 1.5): состояние `unknown_tag` с именем виновником; разобранное значение
        #    флага при этом в строку не пишется (CHECK), и потеря называется.
        "unknown_property": ("НеизвестноеСвойство",
                             "a0000000-0000-0000-0000-000000000002", fo_file(
                                 "a0000000-0000-0000-0000-000000000002", full_body(
                                     "НеизвестноеСвойство",
                                     extra="\t\t\t<UnknownProperty>текст</UnknownProperty>\n"))),

        # 3. Значение флага вне `true`/`false` — `unknown_value`, колонка флага остаётся NULL.
        "unknown_value": ("НеизвестноеЗначение",
                          "a0000000-0000-0000-0000-000000000003", fo_file(
                              "a0000000-0000-0000-0000-000000000003", full_body(
                                  "НеизвестноеЗначение", privileged="Да"))),

        # 4. Флага `PrivilegedGetMode` в файле нет — `absent` с перечнем виновников;
        #    корпус такого не давал (тег есть в 765/765), но CHECK требует пустой колонки.
        "no_flag": ("БезФлага", "a0000000-0000-0000-0000-000000000004", fo_file(
            "a0000000-0000-0000-0000-000000000004", full_body("БезФлага",
                                                               privileged=None))),

        # 5. Тега `Location` нет — `absent` (пустая форма и пустой тип цели).
        "no_location": ("БезЛокации", "a0000000-0000-0000-0000-000000000005", fo_file(
            "a0000000-0000-0000-0000-000000000005", full_body("БезЛокации",
                                                               address=None))),

        # 6. `<Location/>` пустой — `empty_value`: пустая строка ссылки, а не NULL
        #    (CHECK различает эти состояния именно так).
        "empty_location": ("ПустаяЛокация", "a0000000-0000-0000-0000-000000000006", fo_file(
            "a0000000-0000-0000-0000-000000000006", full_body("ПустаяЛокация",
                                                               address=""))),

        # 7. Адрес среза регистра, строки которого в индексе нет: форма
        #    `register_resource`, состояние `prefix_only`, остаток пути называется, uuid
        #    цели отсутствует (uuid строки-префикса о цели не говорит).
        "prefix_resource": ("ПрефиксРесурса", "a0000000-0000-0000-0000-000000000007", fo_file(
            "a0000000-0000-0000-0000-000000000007", full_body(
                "ПрефиксРесурса",
                address="InformationRegister.Настройки.Resource.Отсутствует"))),

        # 8. Тот же случай для адреса реквизита — форма `attribute` (корпус даёт 6 таких
        #    ссылок, все `exact`; здесь она неразрешима намеренно).
        "prefix_attribute": ("ПрефиксРеквизита", "a0000000-0000-0000-0000-000000000008",
                             fo_file("a0000000-0000-0000-0000-000000000008", full_body(
                                 "ПрефиксРеквизита",
                                 address="Catalog.Организации.Attribute.Отсутствует"))),

        # 9. Ни адреса, ни его префикса в индексе нет — `unresolved` с полным остатком
        #    пути; форма вычисляется по структуре адреса (`single`), потому что форма и
        #    разрешение — разные факты.
        "unresolved_location": ("НеразрешимаяЛокация",
                                "a0000000-0000-0000-0000-000000000009", fo_file(
                                    "a0000000-0000-0000-0000-000000000009", full_body(
                                        "НеразрешимаяЛокация",
                                        address="Constant.ТакойНет"))),

        # 10. Адрес вне трёх наблюдённых форм (три сегмента без среза) — форма `other`,
        #     разрешён префиксом: граница разбора называется, а не нормализуется молча.
        "other_form": ("ПрочаяФорма", "a0000000-0000-0000-0000-00000000000a", fo_file(
            "a0000000-0000-0000-0000-00000000000a", full_body(
                "ПрочаяФорма", address="AccumulationRegister.Продажи.RecordType"))),

        # 11. Пустой перечень `<Content/>` (203 файла из 765) — состояние строки вида
        #     `empty_content`, а не пустая строка таблицы и не отсутствие опции.
        "empty_content": ("ПустойПеречень", "a0000000-0000-0000-0000-00000000000b", fo_file(
            "a0000000-0000-0000-0000-00000000000b", full_body("ПустойПеречень", items=""))),

        # 12. Тега `<Content>` нет вовсе — то же состояние перечня, но отсутствие тега
        #     называется отдельным предупреждением: «перечень пуст» и «тега перечня нет» —
        #     разные наблюдения о файле.
        "no_content": ("БезПеречня", "a0000000-0000-0000-0000-00000000000c", fo_file(
            "a0000000-0000-0000-0000-00000000000c", full_body("БезПеречня",
                                                               items=None))),

        # 13. Элемент перечня чужого тега (`xr:Metadata`, а не `xr:Object`): строкой
        #     применения он не становится, наблюдаемый тег называется.
        "foreign_item": ("ЧужойТегЭлемента", "a0000000-0000-0000-0000-00000000000d", fo_file(
            "a0000000-0000-0000-0000-00000000000d", full_body(
                "ЧужойТегЭлемента",
                items=object_item("Catalog.Товары", tag="xr:Metadata")))),

        # 14. Повтор цели внутри перечня: дедупликации нет (уникальный ключ по
        #     (строка вида, ordinal) это допускает), повтор называется диагностикой.
        "duplicate_target": ("ДубльЦели", "a0000000-0000-0000-0000-00000000000e", fo_file(
            "a0000000-0000-0000-0000-00000000000e", full_body(
                "ДубльЦели", items=ONE_ITEM + ONE_ITEM))),

        # 15. Цель вне индекса состава (`unresolved`) и цель, разрешённая только префиксом
        #     (`prefix_only` — индекс содержит `Catalog.Товары`, но не псевдозапись
        #     колонки): состояния различимы структурой строки.
        "target_unresolved": ("ЦельВнеИндекса", "a0000000-0000-0000-0000-00000000000f",
                              fo_file("a0000000-0000-0000-0000-00000000000f", full_body(
                                  "ЦельВнеИндекса",
                                  items=(object_item("Catalog.ТакойНет")
                                         + object_item(
                                             "Catalog.Товары.Attribute.Цена"))))),

        # 16. Повтор тега свойства: берётся первое значение, повтор называется (молча
        #     выбрать второе — значит солгать о файле). `full_body` ставит `Comment` из
        #     параметра `comment` ПЕРВЫМ, а `extra` — вторым, поэтому первый текст задаётся
        #     параметром, а повтор — `extra` (иначе фикстура проверяла бы обратное).
        "duplicate_property": ("ДубльТега", "a0000000-0000-0000-0000-000000000010", fo_file(
            "a0000000-0000-0000-0000-000000000010", full_body(
                "ДубльТега", comment="первый", extra=comment_tag("второй")))),

        # 17. Файла нет в индексе состава — `file_only` называется поимённо.
        "file_only": ("ВнеИндекса", "a0000000-0000-0000-0000-000000000011", fo_file(
            "a0000000-0000-0000-0000-000000000011", full_body("ВнеИндекса"))),

        # 18. uuid файла ≠ uuid строки индекса — `uuid_mismatch` (замер 1.1 даёт
        #     совпадение 765/765, случай — граница).
        "uuid_mismatch": ("НесовпадениеUUID", "a0000000-0000-0000-0000-000000000012",
                          fo_file("a0000000-0000-0000-0000-000000000012",
                                  full_body("НесовпадениеUUID"))),

        # 19. Элемент перечня без имени цели — отказ файла с причиной: строку применения
        #     нечем ключить (CHECK `functional_option_content_names_not_blank`).
        "item_without_name": ("ЭлементБезИмени",
                              "a0000000-0000-0000-0000-000000000013", fo_file(
                                  "a0000000-0000-0000-0000-000000000013", full_body(
                                      "ЭлементБезИмени", items=object_item("")))),

        # 20. Битый XML — та же граница отказа с текстом причины.
        "broken": ("Битый", "a0000000-0000-0000-0000-000000000014",
                   HEAD + '<FunctionalOption uuid="a0000000-0000-0000-0000-000000000014">\n'
                          "\t<Properties>\n"),

        # 21. `<Name>` пустой — строку опции нечем ключить (NOT BLANK по схеме).
        "no_name": ("БезИмени", "a0000000-0000-0000-0000-000000000015", fo_file(
            "a0000000-0000-0000-0000-000000000015", full_body("БезИмени")).replace(
                name_tag("БезИмени"), name_tag(""))),

        # 22. Атрибут `uuid` не является uuid — правило R3: строку нечем версионировать.
        "bad_uuid": ("НевалидныйUUID", "a0000000-0000-0000-0000-000000000016",
                     fo_file("не uuid", full_body("НевалидныйUUID"))),
    }

    for file_name, _obj_uuid, text in files.values():
        (directory / f"{file_name}.xml").write_text(text, encoding="utf-8")
    return {key: (file_name, obj_uuid)
            for key, (file_name, obj_uuid, _text) in files.items()}


def fixture_index_rows(fixtures: Dict[str, Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Записи индекса состава той же фиктивной выгрузки парами `(имя, id)`.

    Индекс строится отдельно от файлов и по другому основанию: стадия П5 получает строки
    `configuration_objects`, то есть индекс выгрузки, а не её файлы. Разбор обязан сверять
    их как два независимых источника (правило V43), поэтому и здесь круг задаётся списком
    имён, а не обходом каталога.
    """
    # строки вида: все файлы, кроме отсутствующего в индексе (`file_only`);
    index = [("FunctionalOption." + name, obj_uuid)
             for key, (name, obj_uuid) in fixtures.items() if key != "file_only"]
    # запись индекса без файла:
    index.append(("FunctionalOption.ИндексБезФайла",
                  "a0000000-0000-0000-0000-0000000000ee"))
    # uuid строки индекса другой, чем в файле:
    index = [entry for entry in index if entry[0] != "FunctionalOption.НесовпадениеUUID"]
    index.append(("FunctionalOption.НесовпадениеUUID",
                  "a0000000-0000-0000-0000-0000000000ef"))
    # Вид-сосед позиции 2.12: в круг вида попасть не должен (раздел 1.2 плана) — сравнение
    # ведётся точным `object_type`, а не префиксом имени.
    index.append(("FunctionalOptionsParameter.ПараметрОпции",
                  "a0000000-0000-0000-0000-0000000000f0"))
    # Цели перечня и адреса `Location` — другие виды метаданных; псевдозаписей колонок у
    # фикстуры нет намеренно: случаи `prefix_only` и `unresolved` корпус не давал (замеры
    # 2.1, 2.2 дают только `exact`).
    index += [("Constant.ИспользоватьОпцию", "b0000000-0000-0000-0000-0000000000a1"),
              ("InformationRegister.Настройки", "b0000000-0000-0000-0000-0000000000a2"),
              ("Catalog.Организации", "b0000000-0000-0000-0000-0000000000a3"),
              ("AccumulationRegister.Продажи", "b0000000-0000-0000-0000-0000000000a4"),
              ("Catalog.Товары", "b0000000-0000-0000-0000-0000000000a5"),
              ("Document.Реализация.Attribute.Контракт",
               "b0000000-0000-0000-0000-0000000000a6"),
              ("Subsystem.Раздел", "b0000000-0000-0000-0000-0000000000a7")]
    return index



# ─── проверка 1: фикстуры ─────────────────────────────────────────────────────
def load_index_rows(root: Path) -> List[Dict]:
    """Строки индекса состава фиктивной выгрузки (тот же разбор, что у стадии П5)."""
    path = find_config_dump_info(root)
    if path is None:
        raise SystemExit("фикстура: ConfigDumpInfo.xml не создан")
    parsed = parse_config_dump_info(path)
    if not parsed["success"]:
        raise SystemExit("фикстура: индекс состава не разобран: %s" % parsed["error"])
    return parsed["objects"]


def check_fixtures(root: Path) -> Dict:
    emit("=== фикстуры (состояния, которых корпус не даёт)")
    fixtures = build_fixtures(root)
    (root / "ConfigDumpInfo.xml").write_text(
        dump_index(fixture_index_rows(fixtures)), encoding="utf-8")
    index_rows = load_index_rows(root)
    result = collect_functional_options(root, index_rows)
    rows = result["rows"]
    targets = result["targets"]

    check("фиктур записано 22", len(fixtures) == 22, str(len(fixtures)))
    check("круг: файлов найдено 22", result["files_found"] == 22,
          "found=%d" % result["files_found"])
    check("круг: разобрано 18, пропущено 4 с причиной",
          result["files_read"] == 18 and len(result["files_failed"]) == 4,
          "read=%d failed=%s" % (result["files_read"],
                                 [(f["source_path"], f["reason"])
                                  for f in result["files_failed"]]))
    check("отказ называется текстом причины (битый XML, пустой Name, элемент без имени, "
          "не-uuid)",
          all(f["reason"] for f in result["files_failed"])
          and any("XML не разобран" in (f["reason"] or "")
                  for f in result["files_failed"])
          and any("нечем ключить" in (f["reason"] or "")
                  for f in result["files_failed"])
          and any("пустое имя цели" in (f["reason"] or "")
                  for f in result["files_failed"])
          and any("uuid" in (f["reason"] or "") for f in result["files_failed"]),
          str([(f["source_path"], f["reason"]) for f in result["files_failed"]]))
    check("наблюдений о составе каталога нет (круг плоский)",
          result["observations"] == [], str(result["observations"]))
    check("сводка success=False при пропущенных файлах", result["success"] is False)
    check("расхождения круга: index_only / file_only / uuid_mismatch названы поимённо",
          result["index_only"] == ["FunctionalOption.ИндексБезФайла"]
          and result["file_only"] == [f"{DIR_NAME}/ВнеИндекса.xml"]
          and [item["source_path"] for item in result["uuid_mismatch"]]
          == [f"{DIR_NAME}/НесовпадениеUUID.xml"],
          "index_only=%s file_only=%s uuid_mismatch=%s"
          % (result["index_only"], result["file_only"], result["uuid_mismatch"]))
    check("вид-сосед FunctionalOptionsParameter в круг не попал (сверка точным видом, "
          "раздел 1.2 плана)",
          not any("FunctionalOptionsParameter" in name for name in result["index_only"])
          and not any("FunctionalOptionsParameter" in row["object_name"] for row in rows),
          str(result["index_only"]))

    # Замкнутые словари состояний называются целиком: «состояния нет» и «состояние не
    # считалось» — разные ответы (C2 узла V47). Суммы по словарю равны числу разобранных
    # строк: состояние обязано быть названо на каждой строке.
    check("словари состояний полные, суммы равны числу строк",
          sum(result["counts_by_location_state"].values()) == result["files_read"]
          and sum(result["counts_by_location_form"].values()) == result["files_read"]
          and sum(result["counts_by_content_state"].values()) == result["files_read"]
          and sum(result["counts_by_properties_state"].values()) == result["files_read"],
          "loc=%s form=%s content=%s props=%s"
          % (result["counts_by_location_state"], result["counts_by_location_form"],
             result["counts_by_content_state"], result["counts_by_properties_state"]))
    check("состояния ссылки, которых корпус не давал, названы: prefix_only 3, "
          "unresolved 1, empty_value 1, absent 1",
          result["counts_by_location_state"][TARGET_PREFIX_ONLY] == 3
          and result["counts_by_location_state"][TARGET_UNRESOLVED] == 1
          and result["counts_by_location_state"][LOCATION_EMPTY_VALUE] == 1
          and result["counts_by_location_state"][LOCATION_ABSENT] == 1,
          str(result["counts_by_location_state"]))
    check("формы адреса различимы: single 13, register_resource 1, attribute 1, other 1, "
          "пустая 2",
          result["counts_by_location_form"][LOCATION_FORM_SINGLE] == 13
          and result["counts_by_location_form"][LOCATION_FORM_REGISTER_RESOURCE] == 1
          and result["counts_by_location_form"][LOCATION_FORM_ATTRIBUTE] == 1
          and result["counts_by_location_form"][LOCATION_FORM_OTHER] == 1
          and result["counts_by_location_form"][""] == 2,
          str(result["counts_by_location_form"]))
    check("состояния свойств названы с виновниками: unknown_tag 1, unknown_value 1, "
          "absent 1, all_known 15",
          result["counts_by_properties_state"][PROPS_UNKNOWN_TAG] == 1
          and result["counts_by_properties_state"][PROPS_UNKNOWN_VALUE] == 1
          and result["counts_by_properties_state"][PROPS_ABSENT] == 1
          and result["counts_by_properties_state"][PROPS_ALL_KNOWN] == 15,
          str(result["counts_by_properties_state"]))
    check("пустой перечень и перечень с чужим элементом — состояние empty_content (3)",
          result["counts_by_content_state"][CONTENT_EMPTY] == 3
          and result["counts_by_content_state"][CONTENT_WITH] == 15,
          str(result["counts_by_content_state"]))

    # ─── типичный файл: полный словарь свойств ────────────────────────────────
    full = row_by(rows, "Типичная")
    check("типичный файл разобран", bool(full))
    if full:
        check("uuid, полное имя и путь источника взяты из файла",
              full["object_uuid"] == "a0000000-0000-0000-0000-000000000001"
              and full["full_name"] == "Типичная"
              and full["object_name"] == "Типичная"
              and full["source_path"] == f"{DIR_NAME}/Типичная.xml", str(full)[:200])
        check("синоним читается языковой картой, комментарий — текстом",
              full["synonym"] == {"ru": "Типичная"}
              and full["comment"] == "Типичная", str(full["synonym"]))
        check("флаг PrivilegedGetMode читается логическим (true → True)",
              full["privileged_get_mode"] is True)
        check("ссылка Location разрешена индексом целиком (замер 2.1: 765/765 exact)",
              full["location_state"] == TARGET_EXACT
              and full["location_ref"] == LOCATION_ADDRESS
              and full["location_full_name"] == LOCATION_ADDRESS
              and full["location_object_type"] == "Constant"
              and full["location_object_id"] == "b0000000-0000-0000-0000-0000000000a1"
              and full["location_object_uuid"] == "b0000000-0000-0000-0000-0000000000a1"
              and full["location_unresolved_path"] is None, str(full["location_state"]))
        check("форма адреса `single` вычислена по числу сегментов (M5)",
              full["location_target_form"] == LOCATION_FORM_SINGLE)
        check("состояние свойств all_known, когда тегов и значений вне словаря нет",
              full["properties_state"] == PROPS_ALL_KNOWN
              and full["unknown_property_names"] is None)
    option_targets = targets_of(targets, "FunctionalOption.Типичная")
    check("перечень применения: три цели в порядке файла (ordinal 0,1,2)",
          len(option_targets) == 3 and [t["ordinal"] for t in option_targets] == [0, 1, 2],
          str([t["ordinal"] for t in option_targets]))
    check("тип цели = верхний сегмент имени, тег элемента называется",
          bool(option_targets)
          and [t["target_object_type"] for t in option_targets]
          == ["Catalog", "Document", "Subsystem"]
          and all(t["target_tag"] == "Object" for t in option_targets),
          str([t["target_object_type"] for t in option_targets]))
    check("цели разрешены индексом целиком (замер 2.2: 10 063/10 063 exact)",
          all(t["target_resolve_state"] == TARGET_EXACT
              and t["target_unresolved_path"] is None for t in option_targets))
    check("строка применения несёт ключ строки вида (писатель П4 заменит его на id)",
          bool(option_targets)
          and all(t["option_full_name"] == "FunctionalOption.Типичная"
                  and t["option_object_uuid"]
                  == "a0000000-0000-0000-0000-000000000001" for t in option_targets))

    # ─── состояния свойств: виновник называется, а не теряется ─────────────────
    unknown_tag_row = row_by(rows, "НеизвестноеСвойство")
    check("тег вне словаря: unknown_tag с именем виновником",
          unknown_tag_row.get("properties_state") == PROPS_UNKNOWN_TAG
          and unknown_tag_row.get("unknown_property_names") == ["UnknownProperty"],
          str(unknown_tag_row.get("unknown_property_names")))
    check("разобранное значение флага при неизвестном словаре не пишется и потеря "
          "называется (CHECK privileged_get_mode_declared)",
          unknown_tag_row.get("privileged_get_mode") is None
          and any("PrivilegedGetMode" in warning and "не записано" in warning
                  for warning in result["warnings"]),
          str([w for w in result["warnings"] if "PrivilegedGetMode" in w][:2]))
    unknown_value_row = row_by(rows, "НеизвестноеЗначение")
    check("значение флага вне true/false: unknown_value, колонка флага пуста",
          unknown_value_row.get("properties_state") == PROPS_UNKNOWN_VALUE
          and unknown_value_row.get("privileged_get_mode") is None
          and unknown_value_row.get("unknown_property_names") == ["PrivilegedGetMode"],
          str(unknown_value_row.get("unknown_property_names")))
    no_flag_row = row_by(rows, "БезФлага")
    check("тега флага нет: absent с перечнем виновников, флаг не подставлен ложью",
          no_flag_row.get("properties_state") == PROPS_ABSENT
          and no_flag_row.get("unknown_property_names") == ["PrivilegedGetMode"]
          and no_flag_row.get("privileged_get_mode") is None,
          str(no_flag_row.get("unknown_property_names")))

    # ─── состояния ссылки Location, которых корпус не давал ────────────────────
    no_location_row = row_by(rows, "БезЛокации")
    check("тега Location нет: absent с пустой формой и пустым типом цели",
          no_location_row.get("location_state") == LOCATION_ABSENT
          and no_location_row.get("location_ref") is None
          and no_location_row.get("location_full_name") is None
          and no_location_row.get("location_object_type") == ""
          and no_location_row.get("location_target_form") == ""
          and any("<Location>" in warning for warning in result["warnings"]))
    empty_location_row = row_by(rows, "ПустаяЛокация")
    check("пустой Location: empty_value держит пустую строку, а не NULL (CHECK различает "
          "эти состояния)",
          empty_location_row.get("location_state") == LOCATION_EMPTY_VALUE
          and empty_location_row.get("location_ref") == ""
          and empty_location_row.get("location_full_name") is None
          and empty_location_row.get("location_object_id") is None
          and empty_location_row.get("location_target_form") == "")

    prefix_row = row_by(rows, "ПрефиксРесурса")
    check("адрес среза регистра разрешён префиксом: форма register_resource, остаток пути "
          "назван, uuid цели отсутствует",
          prefix_row.get("location_state") == TARGET_PREFIX_ONLY
          and prefix_row.get("location_target_form") == LOCATION_FORM_REGISTER_RESOURCE
          and prefix_row.get("location_object_type") == "InformationRegister"
          and prefix_row.get("location_object_id") == "b0000000-0000-0000-0000-0000000000a2"
          and prefix_row.get("location_object_uuid") is None
          and prefix_row.get("location_unresolved_path") == "Resource.Отсутствует",
          str({k: prefix_row.get(k) for k in ("location_state", "location_object_uuid",
                                              "location_unresolved_path")}))
    attribute_row = row_by(rows, "ПрефиксРеквизита")
    check("адрес реквизита различается формой attribute (M5: носитель значения разный)",
          attribute_row.get("location_target_form") == LOCATION_FORM_ATTRIBUTE
          and attribute_row.get("location_state") == TARGET_PREFIX_ONLY
          and attribute_row.get("location_unresolved_path") == "Attribute.Отсутствует",
          str(attribute_row.get("location_target_form")))
    unresolved_row = row_by(rows, "НеразрешимаяЛокация")
    check("адреса и его префикса нет в индексе: unresolved с полным остатком пути и без "
          "строк индекса",
          unresolved_row.get("location_state") == TARGET_UNRESOLVED
          and unresolved_row.get("location_object_id") is None
          and unresolved_row.get("location_object_uuid") is None
          and unresolved_row.get("location_unresolved_path") == "Constant.ТакойНет"
          and unresolved_row.get("location_target_form") == LOCATION_FORM_SINGLE,
          str(unresolved_row.get("location_unresolved_path")))
    other_row = row_by(rows, "ПрочаяФорма")
    check("адрес вне трёх наблюдённых форм: other + prefix_only, граница названа",
          other_row.get("location_target_form") == LOCATION_FORM_OTHER
          and other_row.get("location_state") == TARGET_PREFIX_ONLY
          and other_row.get("location_unresolved_path") == "RecordType"
          and any("вне трёх наблюдённых форм" in warning
                  for warning in result["warnings"]),
          str({k: other_row.get(k) for k in ("location_target_form",
                                             "location_unresolved_path")}))

    # ─── состояния перечня применения ─────────────────────────────────────────
    for name in ("ПустойПеречень", "БезПеречня", "ЧужойТегЭлемента"):
        row = row_by(rows, name)
        check("%s: перечень пуст состоянием empty_content с обнулённым счётчиком, строк "
              "применения нет" % name,
              row.get("content_state") == CONTENT_EMPTY
              and row.get("targets_count") == 0
              and not targets_of(targets, "FunctionalOption." + name),
              str({k: row.get(k) for k in ("content_state", "targets_count")}))
    check("отсутствие тега <Content> называется отдельно от пустого перечня",
          any("свойства <Content> нет в файле" in warning
              for warning in result["warnings"]))
    check("чужой тег элемента перечня называется наблюдаемым, строкой применения не "
          "становится",
          result["unexpected_tags"] == {"Metadata": 1}
          and any("вне словаря замера 2.2" in warning for warning in result["warnings"]),
          str(result["unexpected_tags"]))
    duplicate_rows = targets_of(targets, "FunctionalOption.ДубльЦели")
    check("повтор цели внутри перечня: две строки с ordinal 0,1 и названной диагностикой",
          len(duplicate_rows) == 2 and [t["ordinal"] for t in duplicate_rows] == [0, 1]
          and result["duplicate_targets"]
          == [{"source_path": f"{DIR_NAME}/ДубльЦели.xml",
               "target_full_name": "Catalog.Товары"}],
          str(result["duplicate_targets"]))

    unresolved_rows = targets_of(targets, "FunctionalOption.ЦельВнеИндекса")
    check("цель вне индекса: unresolved без строк индекса, остаток пути = всё имя цели",
          len(unresolved_rows) == 2
          and unresolved_rows[0]["target_resolve_state"] == TARGET_UNRESOLVED
          and unresolved_rows[0]["target_object_id"] is None
          and unresolved_rows[0]["target_object_uuid"] is None
          and unresolved_rows[0]["target_unresolved_path"] == "Catalog.ТакойНет",
          str(unresolved_rows[:1]))
    check("цель, разрешённая префиксом: prefix_only с остатком пути и идентификатором "
          "строки-префикса",
          len(unresolved_rows) == 2
          and unresolved_rows[1]["target_resolve_state"] == TARGET_PREFIX_ONLY
          and unresolved_rows[1]["target_object_id"]
          == "b0000000-0000-0000-0000-0000000000a5"
          and unresolved_rows[1]["target_unresolved_path"] == "Attribute.Цена",
          str(unresolved_rows[1:2]))
    check("число неразрешённых целей и ссылок называется целиком, примеры ограничены",
          result["unresolved_targets_total"] == 2
          and len(result["unresolved_targets"]) == 2
          and result["unresolved_locations_total"] == 4,
          "targets=%d locations=%d" % (result["unresolved_targets_total"],
                                       result["unresolved_locations_total"]))
    repeated_row = row_by(rows, "ДубльТега")
    check("повтор тега свойства: берётся первое значение, повтор назван предупреждением",
          repeated_row.get("comment") == "первый"
          and any("встречается в файле 2-й раз" in warning
                  for warning in result["warnings"]),
          str(repeated_row.get("comment")))

    # ─── сводка круга ─────────────────────────────────────────────────────────
    check("сводка целей сходится: 19 строк применения, 5 различных имён, максимум 3",
          result["targets_total"] == 19 and result["targets_distinct"] == 5
          and result["max_targets_per_file"] == 3,
          "total=%d distinct=%d max=%d" % (result["targets_total"],
                                          result["targets_distinct"],
                                          result["max_targets_per_file"]))
    check("счётчик состояний разрешения целей равен числу строк применения",
          sum(result["counts_by_target_resolve_state"].values()) == result["targets_total"]
          and result["counts_by_target_resolve_state"][TARGET_EXACT] == 17,
          str(result["counts_by_target_resolve_state"]))
    check("классы целей считаются по верхнему сегменту имени",
          result["targets_by_kind"].get("Catalog") == 17
          and result["targets_by_kind"].get("Document") == 1
          and result["targets_by_kind"].get("Subsystem") == 1
          and sum(result["targets_by_kind"].values()) == result["targets_total"],
          str(result["targets_by_kind"]))
    check("счётчик целей в строке вида равен числу её строк применения (CHECK "
          "content_state_matches_targets)",
          all(row["targets_count"] == len(targets_of(targets, "FunctionalOption."
                                                    + row["object_name"]))
              for row in rows),
          str([(row["object_name"], row["targets_count"]) for row in rows
               if row["targets_count"] != len(targets_of(
                   targets, "FunctionalOption." + row["object_name"]))][:3]))

    # Прямой вызов разбора одного файла: сверка с индексом состава и офлайн-граница
    # «индекс не передан» («не разрешалось» и «не разрешилось» различаются).
    single = read_registration_file(root / DIR_NAME / "Типичная.xml",
                                   source_path=f"{DIR_NAME}/Типичная.xml",
                                   index_by_name=None)
    check("без индекса состава сверка называется not_checked, а не matched",
          single["index_check"]["state"] == "not_checked")
    check("без индекса состава цели и ссылка остаются unresolved (не «не разрешались»)",
          all(t["target_resolve_state"] == TARGET_UNRESOLVED for t in single["targets"])
          and len(single["targets"]) == 3
          and single["row"]["location_state"] == TARGET_UNRESOLVED,
          str(single["index_check"]))

    # Отсутствие каталога вида — ответ о выгрузке, а не отказ (Q9 прецедентов V48…V55);
    # непереданный индекс называется наблюдением, а не пустым разрешением.
    with tempfile.TemporaryDirectory(prefix="v56_p3_empty_") as empty_tmp:
        empty = collect_functional_options(Path(empty_tmp))
        check("каталога вида нет: files_found 0 с наблюдением directory_missing, не отказ",
              empty["success"] and empty["files_found"] == 0
              and ("directory_missing", DIR_NAME) in empty["observations"],
              str(empty["observations"]))
        check("индекс состава не передан: наблюдение index_not_provided, сверка "
              "not_checked",
              ("index_not_provided", "configuration_objects") in empty["observations"])
        no_index = collect_functional_options(root)
        # Без индекса не разрешается то, что требует индекса: значения адресов становятся
        # `unresolved`, но `empty_value` (пустое значение) и `absent` (тега нет) от
        # индекса не зависят и остаются своими состояниями — 16 + 1 + 1 = 18 строк.
        # Смешать их значило бы потерять наблюдение о файле ради «всё unresolved».
        check("круг без индекса состава разбирается, ссылки и цели остаются unresolved с "
              "названным наблюдением, сверка круга не ведётся",
              no_index["files_found"] == 22
              and ("index_not_provided", "configuration_objects") in no_index["observations"]
              and no_index["counts_by_location_state"][TARGET_UNRESOLVED] == 16
              and no_index["counts_by_location_state"][LOCATION_EMPTY_VALUE] == 1
              and no_index["counts_by_location_state"][LOCATION_ABSENT] == 1
              and no_index["counts_by_target_resolve_state"][TARGET_UNRESOLVED] == 19
              and no_index["index_only"] == [] and no_index["file_only"] == [],
              str(no_index["counts_by_location_state"]))
    return result



# ─── проверка 2: инварианты строк (те же предикаты, что кладёт схема) ─────────
# CHECK живёт в SQL и в офлайн-прогоне недоступен, но его предикаты — обычный текст:
# прогон по строкам разбора показывает нарушение ДО записи половины круга (писатель П4
# иначе падал бы на ограничении в середине транзакции). Предикаты взяты из
# `migrate_v56_functional_options.sql`: functional_options_names_not_blank,
# _properties_state_known, _properties_state_matches_unknown,
# _privileged_get_mode_declared, _location_target_form_known, _location_state_known,
# _location_state_matches_value, _location_type_matches_name, _location_form_matches_name,
# _location_uuid_only_when_resolved, _content_state_known, _content_state_matches_targets;
# для применения — functional_option_content_names_not_blank, _resolve_state_known,
# _resolve_matches_reference, _type_matches_name, _ordinal_non_negative.
def split_part(value: str, position: int) -> str:
    """Аналог `split_part(value, '.', n)` из CHECK (n — с 1, как в SQL)."""
    parts = (value or "").split(".")
    index = position - 1
    return parts[index] if 0 <= index < len(parts) else ""


def row_violations(row: Dict) -> List[str]:
    bad: List[str] = []
    if not (row["object_name"] and row["full_name"] and row["source_path"]):
        bad.append("names_not_blank")
    state = row["properties_state"]
    offenders = row["unknown_property_names"] or []
    if state not in ("all_known", "unknown_value", "unknown_tag", "absent"):
        bad.append("properties_state_known")
    elif (state == "all_known" and offenders) or (state != "all_known" and not offenders):
        bad.append("properties_state_matches_unknown")
    if (state == "all_known") != (row["privileged_get_mode"] is not None):
        bad.append("privileged_get_mode_declared")

    location_state = row["location_state"]
    form = row["location_target_form"]
    if location_state not in ("exact", "prefix_only", "unresolved", "empty_value",
                              "absent"):
        bad.append("location_state_known")
    if form not in ("single", "register_resource", "attribute", "other", ""):
        bad.append("location_target_form_known")
    ref = row["location_ref"]
    full = row["location_full_name"]
    object_id = row["location_object_id"]
    unresolved_path = row["location_unresolved_path"]
    if location_state == "exact" and not (
            ref and full and row["location_object_type"] and object_id
            and unresolved_path is None):
        bad.append("location_state_matches_value:exact")
    if location_state == "prefix_only" and not (
            ref and full and row["location_object_type"] and object_id and unresolved_path):
        bad.append("location_state_matches_value:prefix_only")
    if location_state == "unresolved" and not (
            ref and full and row["location_object_type"]
            and object_id is None and row["location_object_uuid"] is None
            and unresolved_path):
        bad.append("location_state_matches_value:unresolved")

    if location_state == "empty_value" and not (
            ref == "" and row["location_object_type"] == "" and form == ""
            and full is None and object_id is None
            and row["location_object_uuid"] is None and unresolved_path is None):
        bad.append("location_state_matches_value:empty_value")
    if location_state == "absent" and not (
            ref is None and row["location_object_type"] == "" and form == ""
            and full is None and object_id is None
            and row["location_object_uuid"] is None and unresolved_path is None):
        bad.append("location_state_matches_value:absent")
    if location_state in ("empty_value", "absent"):
        if row["location_object_type"] != "":
            bad.append("location_type_matches_name")
    elif full is None or row["location_object_type"] != split_part(full, 1):
        bad.append("location_type_matches_name")
    # форма адреса согласно его структуре (`%.%.Resource.%` и `%.%.Attribute.%` из CHECK
    # проверяются здесь по сегментам, а не по подстроке: подстрока ловила бы
    # `Catalog.X.ResourceY` как срез регистра)
    segments = (full or "").split(".")
    if form == "single" and not (full and len(segments) == 2):
        bad.append("location_form_matches_name:single")
    if form == "register_resource" and "Resource" not in segments[2:]:
        bad.append("location_form_matches_name:register_resource")
    if form == "attribute" and "Attribute" not in segments[2:]:
        bad.append("location_form_matches_name:attribute")
    if form == "other" and not full:
        bad.append("location_form_matches_name:other")
    if form == "" and location_state not in ("empty_value", "absent"):
        bad.append("location_form_matches_name:empty")
    if row["location_object_uuid"] is not None and location_state != "exact":
        bad.append("location_uuid_only_when_resolved")

    content_state = row["content_state"]
    if content_state not in ("with_content", "empty_content"):
        bad.append("content_state_known")
    elif (content_state == "with_content") != (row["targets_count"] > 0):
        bad.append("content_state_matches_targets")
    return bad


def target_violations(target: Dict) -> List[str]:
    bad: List[str] = []
    if not (target["option_full_name"] and target["target_full_name"]
            and target["target_tag"] and target["target_object_type"]):
        bad.append("names_not_blank")
    state = target["target_resolve_state"]
    if state not in ("exact", "prefix_only", "unresolved"):
        bad.append("resolve_state_known")
    object_id = target["target_object_id"]
    object_uuid = target["target_object_uuid"]
    unresolved_path = target["target_unresolved_path"]
    if state == "exact" and not (object_id and object_uuid and unresolved_path is None):
        bad.append("resolve_matches_reference:exact")
    if state == "prefix_only" and not (object_id and unresolved_path):
        bad.append("resolve_matches_reference:prefix_only")
    if state == "unresolved" and not (
            object_id is None and object_uuid is None and unresolved_path):
        bad.append("resolve_matches_reference:unresolved")
    if target["target_object_type"] != split_part(target["target_full_name"], 1):
        bad.append("type_matches_name")
    if target["ordinal"] < 0:
        bad.append("ordinal_non_negative")
    return bad


def check_row_invariants(rows: List[Dict], targets: List[Dict], label: str) -> None:
    violations = {}
    for row in rows:
        problems = row_violations(row)
        if problems:
            violations[row["object_name"]] = problems
    broken_targets = {}
    for target in targets:
        problems = target_violations(target)
        if problems:
            broken_targets["%s|%d" % (target["option_full_name"],
                                      target["ordinal"])] = problems
    keys = [(target["option_full_name"], target["ordinal"]) for target in targets]
    check("%s: ни одна строка опции не нарушает предикаты CHECK схемы" % label,
          not violations, str(list(violations.items())[:3]))
    check("%s: ни одна строка применения не нарушает предикаты CHECK схемы" % label,
          not broken_targets, str(list(broken_targets.items())[:3]))
    check("%s: ключ (строка вида, ordinal) применения уникален (UNIQUE в схеме)" % label,
          len(set(keys)) == len(keys),
          str([key for key in set(keys) if keys.count(key) > 1][:3]))



# ─── проверка 3: словарь строк парсера против DDL ─────────────────────────────
# Колонки, которые заполняет писатель (П4), а не разбор: суррогатный ключ, ссылка на
# строку заголовка конфигурации, номер ревизии, служебные колонки витрин и связь строки
# применения со строкой вида (`functional_option_id` — id конкретной ревизии, которого
# разбор знать не может). Разбор работает без живой базы и эти ключи не выдумывает.
WRITER_COLUMNS = {"id", "configuration_uuid", "created_at", "revision_no", "changed_at",
                  "changed_by", "is_committed", "functional_option_id"}


def ddl_table_body(table: str) -> str:
    """Тело `CREATE TABLE` таблицы из текста миграции V56 (БД не открывается).

    Список колонок читается текстом, потому что П3 обязан работать без живой базы:
    несуществующая колонка всплывает у писателя на середине записи, а не до неё.
    """
    text = DDL_FILE.read_text(encoding="utf-8")
    match = re.search(r"CREATE TABLE(?: IF NOT EXISTS)?\s+" + table + r"\s*\((.*?)\n\);",
                      text, re.S)
    return match.group(1) if match else ""


def ddl_code_lines(body: str):
    """Строки тела без комментариев.

    `--` в теле — пояснение, а не элемент таблицы; в комментариях стоят и тексты
    значений (`location_state = 'exact'`), и имена состояний. Чтение их колонками дало бы
    ложные имена, поэтому комментарии снимаются ДО обоих разборов — колонок и имён из
    ограничений.
    """
    for line in body.splitlines():
        stripped = line.split("--")[0].strip()
        if stripped:
            yield stripped


def ddl_columns(table: str) -> set:
    """Колонки таблицы из текста миграции.

    Колонку отличает форма строки — `имя ТИП[...]` (имя строчными, тип прописными);
    ограничения и их продолжения такой формы не имеют. Списка-«пропуска» здесь нет
    намеренно: имена колонок открыты, и пропуск по целому слову — колонка `comment`
    (проверка V50 падала на этом же).
    """
    columns = set()
    for line in ddl_code_lines(ddl_table_body(table)):
        found = re.match(r"([a-z][a-z0-9_]*)\s+[A-Z]", line)
        if found:
            columns.add(found.group(1))
    return columns


def ddl_constraint_columns(table: str) -> set:
    """Колонки, которые называют ограничения таблицы (CHECK).

    Ограничение ссылается только на существующую колонку, поэтому перечень служит мерой
    полноты чтения текста: пропущенная колонка всплывает здесь, а не в сравнении со
    строками разбора — там она выглядела бы как «колонка не заполняется разбором», и
    чинили бы разбор вместо чтения DDL.
    """
    names = set()
    for line in ddl_code_lines(ddl_table_body(table)):
        names.update(re.findall(
            r"([a-z_][a-z0-9_]*)\s*(?:>=|<=|<>|!=|=|IS\s+NOT\s+NULL|IS\s+NULL|IS\b|IN\s*\()",
            line))
    return names


def check_ddl_columns(rows: List[Dict], targets: List[Dict]) -> None:
    emit()
    emit("=== словарь строк парсера против DDL (миграция читается текстом)")
    for table, records in (("functional_options", rows),
                          ("functional_option_content", targets)):
        columns = ddl_columns(table)
        check("DDL: таблицы %s в миграции не найдено" % table, bool(columns))
        if not columns:
            continue
        not_seen = sorted(ddl_constraint_columns(table) - columns)
        check("%s: текст CREATE TABLE прочитан целиком — колонки из ограничений найдены"
              % table, not not_seen, "не извлечены: %s" % not_seen)
        if not records:
            continue
        keys = set()
        for record in records:
            keys.update(record.keys())
        extra = sorted(keys - columns)
        check("%s: каждому ключу строки разбора соответствует колонка" % table, not extra,
              "лишние ключи: %s" % extra)
        missing = sorted((columns - WRITER_COLUMNS) - keys)
        check("%s: каждая смысловая колонка DDL заполняется разбором" % table, not missing,
              "не заполняются: %s" % missing)



# ─── проверка 4: эталонные выгрузки ───────────────────────────────────────────
def check_corpora() -> None:
    emit()
    emit("=== эталонные выгрузки (числа разделов 1–2 плана)")
    corpus_kinds: Dict[str, int] = {}
    totals = {"files": 0, "targets": 0, "single": 0, "register_resource": 0,
              "attribute": 0, "content_with": 0, "content_empty": 0,
              "priv_true": 0, "priv_false": 0}
    for dump in ("MinCfg", "KomMag", "BGU2", "BP3"):
        expected = EXPECTED[dump]
        root = DUMP_ROOT / dump
        emit("-- %s" % dump)
        if not root.exists():
            check("%s: каталог выгрузки доступен" % dump, False, str(root))
            continue
        index_path = find_config_dump_info(root)
        if index_path is None:
            check("%s: индекс состава найден" % dump, False, str(root))
            continue
        parsed_index = parse_config_dump_info(index_path)
        if not parsed_index["success"]:
            check("%s: индекс состава разобран" % dump, False, parsed_index["error"])
            continue
        result = collect_functional_options(root, parsed_index["objects"])
        check("разбор круга завершён без пропущенных файлов", result["success"],
              str(result["files_failed"]))
        check("файлов вида ровно столько, сколько измеряет план: %d" % expected["files"],
              result["files_found"] == expected["files"]
              and result["files_read"] == expected["files"],
              "found=%d read=%d" % (result["files_found"], result["files_read"]))
        if not expected["files"]:
            check("отсутствие каталога вида — наблюдение directory_missing, а не отказ",
                  ("directory_missing", DIR_NAME) in result["observations"],
                  str(result["observations"]))
            check("пустой круг назван нулями по всем словарям состояний",
                  all(count == 0 for counts in (result["counts_by_location_state"],
                                               result["counts_by_location_form"],
                                               result["counts_by_content_state"],
                                               result["counts_by_properties_state"])
                      for count in counts.values()),
                  str(result["counts_by_location_state"]))
            continue

        check("целей применения %d, различных имён %d, максимум %d на файл (замер 2.2)"
              % (expected["targets"], expected["distinct"], expected["max_targets"]),
              result["targets_total"] == expected["targets"]
              and result["targets_distinct"] == expected["distinct"]
              and result["max_targets_per_file"] == expected["max_targets"],
              "total=%d distinct=%d max=%d" % (result["targets_total"],
                                              result["targets_distinct"],
                                              result["max_targets_per_file"]))
        check("ссылка Location разрешена индексом целиком: exact %d, прочих состояний "
              "ноль (замер 2.1)" % expected["loc_exact"],
              result["counts_by_location_state"][TARGET_EXACT] == expected["loc_exact"]
              and all(result["counts_by_location_state"][state] == 0
                      for state in (TARGET_PREFIX_ONLY, TARGET_UNRESOLVED,
                                    LOCATION_EMPTY_VALUE, LOCATION_ABSENT)),
              str(result["counts_by_location_state"]))
        check("формы адреса соответствуют замеру 2.1: single %d, register_resource %d, "
              "attribute %d, other 0" % (expected["single"], expected["register_resource"],
                                         expected["attribute"]),
              result["counts_by_location_form"][LOCATION_FORM_SINGLE] == expected["single"]
              and result["counts_by_location_form"][LOCATION_FORM_REGISTER_RESOURCE]
              == expected["register_resource"]
              and result["counts_by_location_form"][LOCATION_FORM_ATTRIBUTE]
              == expected["attribute"]
              and result["counts_by_location_form"][LOCATION_FORM_OTHER] == 0
              and result["counts_by_location_form"][""] == 0,
              str(result["counts_by_location_form"]))
        check("перечень применения: with_content %d, empty_content %d (замер 2.2)"
              % (expected["content_with"], expected["content_empty"]),
              result["counts_by_content_state"][CONTENT_WITH] == expected["content_with"]
              and result["counts_by_content_state"][CONTENT_EMPTY]
              == expected["content_empty"],
              str(result["counts_by_content_state"]))
        flags_true = sum(1 for row in result["rows"] if row["privileged_get_mode"] is True)
        flags_false = sum(1 for row in result["rows"]
                          if row["privileged_get_mode"] is False)
        check("флаг PrivilegedGetMode читается логическим: true %d, false %d (замер 2.3)"
              % (expected["priv_true"], expected["priv_false"]),
              flags_true == expected["priv_true"] and flags_false == expected["priv_false"],
              "true=%d false=%d" % (flags_true, flags_false))
        check("свойств вида вне замкнутого словаря нет (замеры 2, 2.3: ноль)",
              result["counts_by_properties_state"][PROPS_ALL_KNOWN] == expected["files"]
              and not result["unknown_properties"]
              and not result["unknown_value_properties"]
              and not result["unexpected_tags"]
              and not result["duplicate_targets"],
              "unknown=%s values=%s tags=%s dup=%s"
              % (result["unknown_properties"], result["unknown_value_properties"],
                 result["unexpected_tags"], result["duplicate_targets"]))
        check("цели перечня разрешены индексом целиком (замер 2.2: %d из %d)"
              % (expected["targets"], expected["targets"]),
              result["counts_by_target_resolve_state"][TARGET_EXACT]
              == expected["targets"]
              and result["counts_by_target_resolve_state"][TARGET_PREFIX_ONLY] == 0
              and result["counts_by_target_resolve_state"][TARGET_UNRESOLVED] == 0
              and not result["unresolved_targets"]
              and not result["unresolved_locations"],
              str(result["counts_by_target_resolve_state"]))
        check("круг сходится: расхождений с индексом состава нет (замер 1.1: 765/765)",
              not result["index_only"] and not result["file_only"]
              and not result["uuid_mismatch"],
              "index_only=%s file_only=%s uuid=%s" % (result["index_only"],
                                                      result["file_only"],
                                                      result["uuid_mismatch"]))
        check("предупреждений разбора нет: словарь круга замкнут на корпусе",
              not result["warnings"], "%d: %s" % (len(result["warnings"]),
                                                 result["warnings"][:3]))
        check_row_invariants(result["rows"], result["targets"], dump)

        totals["files"] += result["files_found"]
        totals["targets"] += result["targets_total"]
        totals["single"] += result["counts_by_location_form"][LOCATION_FORM_SINGLE]
        totals["register_resource"] += \
            result["counts_by_location_form"][LOCATION_FORM_REGISTER_RESOURCE]
        totals["attribute"] += result["counts_by_location_form"][LOCATION_FORM_ATTRIBUTE]
        totals["content_with"] += result["counts_by_content_state"][CONTENT_WITH]
        totals["content_empty"] += result["counts_by_content_state"][CONTENT_EMPTY]
        totals["priv_true"] += flags_true
        totals["priv_false"] += flags_false
        for kind, count in result["targets_by_kind"].items():
            corpus_kinds[kind] = corpus_kinds.get(kind, 0) + count

    emit("-- корпус")
    check("корпус: файлов %d, целей %d — числа раздела 1.1 и 2.2 плана"
          % (CORPUS_TOTALS["files"], CORPUS_TOTALS["targets"]),
          totals["files"] == CORPUS_TOTALS["files"]
          and totals["targets"] == CORPUS_TOTALS["targets"],
          str(totals))
    check("корпус: формы ссылки %d/%d/%d, перечней %d/%d, флаг %d/%d (замеры 2.1–2.3)"
          % (CORPUS_TOTALS["single"], CORPUS_TOTALS["register_resource"],
             CORPUS_TOTALS["attribute"], CORPUS_TOTALS["content_with"],
             CORPUS_TOTALS["content_empty"], CORPUS_TOTALS["priv_true"],
             CORPUS_TOTALS["priv_false"]),
          totals["single"] == CORPUS_TOTALS["single"]
          and totals["register_resource"] == CORPUS_TOTALS["register_resource"]
          and totals["attribute"] == CORPUS_TOTALS["attribute"]
          and totals["content_with"] == CORPUS_TOTALS["content_with"]
          and totals["content_empty"] == CORPUS_TOTALS["content_empty"]
          and totals["priv_true"] == CORPUS_TOTALS["priv_true"]
          and totals["priv_false"] == CORPUS_TOTALS["priv_false"],
          str(totals))
    check("корпус: классы целей совпадают с замером 2.2 (21 вид, суммы равны числу целей)",
          corpus_kinds == EXPECTED_KINDS
          and len(corpus_kinds) == CORPUS_TOTALS["kinds"]
          and sum(corpus_kinds.values()) == CORPUS_TOTALS["targets"],
          "различие: %s" % sorted({kind for kind in set(corpus_kinds) | set(EXPECTED_KINDS)
                                   if corpus_kinds.get(kind) != EXPECTED_KINDS.get(kind)}))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v56_p3_") as tmp:
        fixture_result = check_fixtures(Path(tmp))
    check_row_invariants(fixture_result["rows"], fixture_result["targets"], "фикстуры")
    check_ddl_columns(fixture_result["rows"], fixture_result["targets"])
    check_corpora()
    emit()
    emit("=== итог")
    if FAILURES:
        emit("ПРОВАЛЕНО ПРОВЕРОК: %d" % len(FAILURES))
        for name in FAILURES:
            emit("  - " + name)
    else:
        emit("все проверки пройдены")
    text = "\n".join(REPORT)
    print(text)
    out = ROOT / "_scratch" / "v56_p3_offline_probe.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())


