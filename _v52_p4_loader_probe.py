#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба шага П4 узла V52: слой свойств критериев отбора (стадия S4g).

Предмет проверки — не разбор файлов (его закрыл П3) и не писатели (проба П4 писателей), а
слой и его контракт ответа:

  1. закрытый контракт `filter_criteria_defaults()` и слой: ключ стадии, круг таблиц вида
     (`FILTER_CRITERIA_TABLES`), порядок снятия `REMOVE_ORDER` (M7 — `form_ext` первой,
     строки вида последней), писатели пяти таблиц (две свои, три — переиспользование V51),
     каждый ключ состояния из `STATE_VOCABULARIES` разбора назван в контракте;
  2. отказ слоя называется состоянием контракта, а не исключением и не нулями (C1, C2):
     каталог не читается, uuid разошлись, строки заголовка нет, файл круга не разбирается;
     ни один отказ не меняет круг таблиц в базе; отказ называет, чем продолжить;
  3. успех: строки пяти таблиц записаны, числа ответа совпадают с тем, что легло в таблицы,
     состояния названы словарями, каждая строка перечня `<Content>` ссылается на CURRENT-
     ревизию своей строки вида (Q2, вариант A), дети вида относятся к своим родителям,
     сверка каталога с индексом состава соответствует независимому запросу к
     `configuration_objects`, разрешение целей перечня держится индекса (Q4), статистика
     затронутых таблиц собрана (мера V46);
  4. повтор той же выгрузки идемпотентен: снятие названо пятью таблицами, дублей нет,
     `revision_no` не растёт (D8), uuid строк не меняются, метка загрузки одна и равна
     названной вызовом (M2);
  5. пустой круг называется состоянием выгрузки, а не отказом (Q9): каталога вида нет —
     `files_found = 0` с наблюдением `directory_missing`, и снятие обязано снять детей тех
     критериев, которых в выгрузке уже нет (файл удалён);
  6. два счётчика одного факта не противоречат друг другу (`module_files_by_kind` против
     `module_files_total`, `form_ext_formats` против числа описаний форм): прогон П3 слоя
     02.11.2026 измерил квадратичное завышение обоих на многофайловых кругах (BGU2: 27 при
     6, BP3: 12 при 3) — правка разбора сделана этим же прогоном;
  7. время слоя называется замером: без `ANALYZE` читатели витрин текущего состояния платят
     минутами (замер V46 на BGU2: 8 мин 25 с против 7 мс), и прогон обязан назвать то, что
     потратил сам.

Граница прогона (называется, а не подразумевается). Внесение стадии в `STAGES` (позиция 2.7
между S4f и S4b), точка входа `load_filter_criteria_tool`, форматтер раздела карточки
`format_filter_criteria_lines` и снятие круга вида в `_remove_rows` конвейера — шаг П5 того
же узла. Раздел конвейера и текст карточки проба проверяет условно: если стадия ещё не
внесена, отсутствие называется строкой [NOTE], а не молчанием и не провалом. Снятие
заголовка кругом вида проверяется фикстурой: если конвейер круг не снимает, дефект сирот
называется и исправляется самой пробой (иначе проба оставила бы в базе то, что ловит).

Эталон — замеры плана `docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md` (разделы 1.1, 1.2, 1.4,
2.1–2.3) и промеры П3/П4 этого узла, а не память ассистента: расхождение с числами
`BASELINE` — провал прогона, а не расхождение двух пересчётов.

Проба работает с живой БД и фиксирует свои транзакции. Строки, записанные слоем, остаются в
базе намеренно: они являются настоящим содержимым выгрузки, а не мусором пробы. Снимается
только то, что проба создала сама: синтетический заголовок-фикстура и её строки. Чужие
круги (другие конфигурации, строки детей внешнего контура) проба обязана оставить
нетронутыми — сравнение идёт снимком по конфигурациям и родителям, а не «таблица пуста».

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    python _v52_p4_loader_probe.py [MinCfg KomMag]        # базовая линия
    python _v52_p4_loader_probe.py BGU2                   # отдельно, замер времени
    python _v52_p4_loader_probe.py BP3                    # отдельно, замер времени
    python _v52_p4_loader_probe.py --no-pipeline ...      # не трогать конвейер

Код возврата 0 — расхождений нет. Прогоны, меняющие общее состояние БД, не параллелят.
"""
import sys
import time
import uuid as uuid_module
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import configuration_filter_criteria as FC  # noqa: E402
import configuration_filter_criteria_loader as FCL  # noqa: E402
from configuration_filter_criteria import (  # noqa: E402
    CHILD_EMPTY_CONTENT, CHILD_WITH_CONTENT, CLASS_OBJECT_REF, CLASS_PRIMITIVE,
    CONTENT_EMPTY_CONTENT, CONTENT_WITH_CONTENT, CONTAINER_TYPE, CONTAINER_TYPE_SET,
    FORM_REF_EMPTY_VALUE, FORM_REF_WITH_REFERENCE, INDEX_NAME_SEPARATOR, INDEX_OBJECT_TYPE,
    MULT_COMPOSITE, MULT_SINGLE, PROPS_ALL_KNOWN, TARGET_EXACT, TYPE_PARSED,
)
from configuration_load_contract import (  # noqa: E402
    CHILD_TABLES as S4_CHILD_TABLES,
    COMMON_ATTRIBUTES_SECTION_HEADER,
    EXCHANGE_PLAN_SECTION_HEADER,
    FILTER_CRITERIA_CIRCLE_BOUNDARY,
    FILTER_CRITERIA_DIR,
    FILTER_CRITERIA_REPEAT_HINT,
    FILTER_CRITERIA_SECTION_HEADER,
    FILTER_CRITERIA_TABLES,
    FOREIGN_STAGE_TABLES,
    OBJECT_MODULES_SECTION_HEADER,
    ROLES_SECTION_HEADER,
    SESSION_PARAMETERS_SECTION_HEADER,
    STAGES,
    STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA,
    STAGE_OBJECT_MODULES,
    STATUS_ERROR,
    STATUS_NOT_RUN,
    STATUS_OK,
    filter_criteria_defaults,
    stage_resume_hint,
    stages_after,
)
from config_load_router import format_load_result, load_catalog  # noqa: E402
from configuration_loader import delete_configuration, find_configuration  # noqa: E402
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from current_revision import (  # noqa: E402
    CHANGED_BY_LOAD, CONFIGURATION_VERSIONED_TABLES, FIRST_REVISION, current_view,
)
from external_db import connect  # noqa: E402
from external_table_writer import (  # noqa: E402
    CONFIGURATION_OBJECT_WRITERS, CommandsRowWriter, ExchangePlanFormsRowWriter,
    FormExtRowWriter,
)

TABLE = FC.TABLE_NAME
CONTENT_TABLE = FC.CONTENT_TABLE_NAME
FORMS_TABLE = FCL.FORMS_TABLE
FORM_EXT_TABLE = FCL.FORM_EXT_TABLE
COMMANDS_TABLE = FCL.COMMANDS_TABLE_NAME
# Порядок снятия круга читается у слоя, а не заводится пробой заново: два списка порядка
# снятия разъезжаются при первой же правке (приём `REMOVE_ORDER` узлов V49–V51).
REMOVE_ORDER = tuple(FCL.REMOVE_ORDER)
PARENT_TYPE = FCL.PARENT_TYPE_CONFIGURATION
CRITERION_VIEW = current_view(TABLE)
# Витрина строк перечня называется явно, а не спросом у `current_view`: своей цепи ревизий у
# таблицы нет (Q2, вариант A), и точка доступа на ней отказывается (прецедент V50).
CONTENT_VIEW = "v_current_" + CONTENT_TABLE

DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DEFAULT_DUMPS = ("MinCfg", "KomMag")
UNLOADED_CANDIDATES = ("Config_NULL", "UNF3", "UT11", "ZUP10")
FIXTURE_DIR = ROOT / "_scratch" / "v52_p4_fixtures"
# Граница времени слоя — та же, что у пробы П4 узла V50 (слой того же круга таблиц).
TIME_LIMIT_S = 120.0

PASSED = 0
FAILED = 0
NOTES = []


# Эталон замера (план, разделы 1.1, 1.2, 1.4, 2.1–2.3 и промеры П3/П4 узла 01–02.11.2026):
# что обязан записать слой на каждой выгрузке. `content` — строки перечня `<Content>`,
# `pseudo` — псевдо-записи индекса (модули, пары `.Form`, `Help`), детьми вида не являющиеся
# (Q7); `resolve` при доступном индексе — `exact` на всех целях (замер 2.2: 1 219 из 1 219);
# `distinct` меньше `content` там, где одну цель называют несколько критериев (BGU2: 723 из
# 727, BP3: 424 из 492) — это состояние выгрузки, а не дефект записи.
BASELINE = {
    "MinCfg": {
        "files": 1, "criteria": 1, "content": 0, "forms": 1, "form_ext": 1, "commands": 1,
        "types_total": 1, "types_resolved": 0, "types_view_wide": 0,
        "containers": {CONTAINER_TYPE: 1, CONTAINER_TYPE_SET: 0},
        "classes": {CLASS_PRIMITIVE: 1, CLASS_OBJECT_REF: 0},
        "multiplicity": {MULT_SINGLE: 1},
        "type_state": {TYPE_PARSED: 1},
        "props": {PROPS_ALL_KNOWN: 1},
        "content_states": {CONTENT_WITH_CONTENT: 0, CONTENT_EMPTY_CONTENT: 1},
        "children": {CHILD_WITH_CONTENT: 1, CHILD_EMPTY_CONTENT: 0},
        "form_ref": {"default_form_state": {FORM_REF_WITH_REFERENCE: 1},
                     "auxiliary_form_state": {FORM_REF_WITH_REFERENCE: 1}},
        "resolve": {TARGET_EXACT: 0},
        "distinct": 0, "max_per_file": 0, "target_types": {},
        # `module_files` = 2, а не 1: индекс состава MinCfg называет для этого критерия и
        # `.ManagerModule`, и `.Command.<Имя>.CommandModule` (замер 1.2; тот же эталон держит
        # независимый обход индекса в `tools/check_v52_filter_criteria.py` — `idx_by_type` +
        # `parse_module_files: 2`). Прежний эталон этой пробы был написан до правки П4,
        # начавшей читать дескрипторы модулей команд (`read_command_module_files`,
        # переиспользование V51), и противоречил собственной строке `pseudo: 3`, где
        # `.CommandModule` уже посчитан.
        "pseudo": 3, "module_files": 2,
        "module_kinds": {"ManagerModule": 1, "CommandModule": 1},
        "form_ext_formats": {"xml": 1}, "ext_observations": {}, "index_rows": 1,
    },
    # KomMag: единственный критерий с `<TypeSet>` (Q6 — вторая ветка разбора блока `<Type>`),
    # пустой `<Content>`, форма есть, команд нет, справочные ресурсы названы наблюдением (Q7).
    "KomMag": {
        "files": 1, "criteria": 1, "content": 0, "forms": 1, "form_ext": 1, "commands": 0,
        "types_total": 1, "types_resolved": 0, "types_view_wide": 1,
        "containers": {CONTAINER_TYPE: 0, CONTAINER_TYPE_SET: 1},
        "classes": {CLASS_PRIMITIVE: 0, CLASS_OBJECT_REF: 1},
        "multiplicity": {MULT_SINGLE: 1},
        "type_state": {TYPE_PARSED: 1},
        "props": {PROPS_ALL_KNOWN: 1},
        "content_states": {CONTENT_WITH_CONTENT: 0, CONTENT_EMPTY_CONTENT: 1},
        "children": {CHILD_WITH_CONTENT: 1, CHILD_EMPTY_CONTENT: 0},
        "form_ref": {"default_form_state": {FORM_REF_WITH_REFERENCE: 1},
                     "auxiliary_form_state": {FORM_REF_EMPTY_VALUE: 1}},
        "resolve": {TARGET_EXACT: 0},
        "distinct": 0, "max_per_file": 0, "target_types": {},
        "pseudo": 2, "module_files": 0, "module_kinds": {},
        "form_ext_formats": {"bin": 1},
        "ext_observations": {"help_file": 1, "help_resources_dir": 1}, "index_rows": 1,
    },
    "BGU2": {
        "files": 7, "criteria": 7, "content": 727, "forms": 0, "form_ext": 0, "commands": 0,
        "types_total": 240, "types_resolved": 240, "types_view_wide": 0,
        "containers": {CONTAINER_TYPE: 240, CONTAINER_TYPE_SET: 0},
        "classes": {CLASS_PRIMITIVE: 0, CLASS_OBJECT_REF: 240},
        "multiplicity": {MULT_SINGLE: 6, MULT_COMPOSITE: 1},
        "type_state": {TYPE_PARSED: 7},
        "props": {PROPS_ALL_KNOWN: 7},
        "content_states": {CONTENT_WITH_CONTENT: 7, CONTENT_EMPTY_CONTENT: 0},
        "children": {CHILD_WITH_CONTENT: 0, CHILD_EMPTY_CONTENT: 7},
        "form_ref": {"default_form_state": {FORM_REF_EMPTY_VALUE: 7},
                     "auxiliary_form_state": {FORM_REF_EMPTY_VALUE: 7}},
        "resolve": {TARGET_EXACT: 727},
        "distinct": 723, "max_per_file": 218, "target_types": {"Document": 727},
        "pseudo": 6, "module_files": 6, "module_kinds": {"ManagerModule": 6},
        "form_ext_formats": {}, "ext_observations": {}, "index_rows": 7,
    },
    "BP3": {
        "files": 6, "criteria": 6, "content": 492, "forms": 0, "form_ext": 0, "commands": 0,
        "types_total": 187, "types_resolved": 187, "types_view_wide": 0,
        "containers": {CONTAINER_TYPE: 187, CONTAINER_TYPE_SET: 0},
        "classes": {CLASS_PRIMITIVE: 0, CLASS_OBJECT_REF: 187},
        "multiplicity": {MULT_SINGLE: 5, MULT_COMPOSITE: 1},
        "type_state": {TYPE_PARSED: 6},
        "props": {PROPS_ALL_KNOWN: 6},
        "content_states": {CONTENT_WITH_CONTENT: 6, CONTENT_EMPTY_CONTENT: 0},
        "children": {CHILD_WITH_CONTENT: 0, CHILD_EMPTY_CONTENT: 6},
        "form_ref": {"default_form_state": {FORM_REF_EMPTY_VALUE: 6},
                     "auxiliary_form_state": {FORM_REF_EMPTY_VALUE: 6}},
        "resolve": {TARGET_EXACT: 492},
        "distinct": 424, "max_per_file": 264, "target_types": {"Document": 492},
        "pseudo": 3, "module_files": 3, "module_kinds": {"ManagerModule": 3},
        "form_ext_formats": {}, "ext_observations": {}, "index_rows": 6,
    },
}

# Сводные эталоны по корпусу (замеры 1.1, 1.4, 2.2) — проверяются суммой прогона четырёх
# выгрузок: 15 файлов вида, 1 219 целей перечня, 429 записей блока `<Type>`, 14 псевдо-
# записей индекса.
CORPUS = {"files": 15, "criteria": 15, "content": 1219, "types_total": 429, "exact": 1219,
          "pseudo": 14}

# Ключ контракта ответа, которым называется каждая колонка состояния разбора. Перечислен
# явно: проверка утверждает имена ключей, а не ищет их по подстроке, иначе переименование
# ключа осталось бы незамеченным, а карточку читает именно имя ключа (C1, C3).
STATE_CONTRACT_KEYS = {
    "properties_state": "counts_by_properties_state",
    "content_state": "counts_by_content_state",
    "children_state": "counts_by_children_state",
    "type_parse_state": "counts_by_type_state",
    "type_multiplicity": "types_multiplicity",
    "default_form_state": "counts_by_form_ref_state",
    "auxiliary_form_state": "counts_by_form_ref_state",
    "target_resolve_state": "counts_by_target_resolve_state",
}
FORM_REF_CONTRACT_KEY = "counts_by_form_ref_state"
FORM_REF_CONTRACT_COLUMNS = ("default_form_state", "auxiliary_form_state")



def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + (((" — " + str(detail)) if detail else "")))
    else:
        FAILED += 1
        print("  [FAIL] " + name + (((" — " + str(detail)) if detail else "")))


def note(text):
    NOTES.append(text)
    print("  [NOTE] " + text)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def group_counts(cur, sql, params=None):
    """Группировка состояния в словарь; нулевых групп у `GROUP BY` нет по построению."""
    cur.execute(sql, params or ())
    return {str(row[0]): int(row[1]) for row in cur.fetchall()}


def nonzero(mapping):
    """Эталон без нулевых позиций — в том виде, в котором их отдаёт `GROUP BY`.

    Нули в эталоне нужны человеку (словарь состояний замкнут), но `GROUP BY` нулевых групп
    не отдаёт; сравнивать словарь замера с группировкой напрямую — значит увидеть
    расхождение там, где его нет (приём проб V49–V51).
    """
    return {str(key): int(value) for key, value in (mapping or {}).items() if int(value)}


def pg_array_items(value):
    """Элементы массива Postgres из того, что вернуло соединение.

    `text[]` psycopg отдаёт списком, `uuid[]` — строкой с литералом массива: typecaster'а
    для массива uuid в psycopg2 нет (замер П4 писателей). Сравнение без разбора литерала
    сравнивало бы символы строки, а не элементы перечня `command_uuids`/`form_names`.
    """
    if isinstance(value, (list, tuple)):
        return [str(item).strip().strip('"') for item in value]
    if value is None:
        # NULL-колонка перечня — пустой перечень, а не перечень из строки 'None'. KomMag
        # (критерий без команд) даёт именно NULL: отсутствие детей выражено отсутствием
        # перечня, и читать из NULL элемент нельзя.
        return []
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("{") and text.endswith("}"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"') for item in inner.split(",")]
    return [text]

def parents_of(cur, cfg_uuid):
    """uuid критериев этого круга — предикат, которым слой снимает детей вида."""
    cur.execute(f"SELECT object_uuid FROM {TABLE} WHERE configuration_uuid = %s::uuid",
                [str(cfg_uuid)])
    return [str(row[0]) for row in cur.fetchall()]


def circle_counts(cur, cfg_uuid):
    """Число строк каждой таблицы круга на эту конфигурацию (таблица, а не витрина).

    Дети считаются предикатом слоя (`parent_type` + uuid родителей круга), а не ногой
    конфигурации: те же `forms`/`commands` пишут строки детей других объектов конфигурации и
    внешнего контура (замер 02.11.2026: у MinCfg 4 формы и 2 команды с той же ногой
    `configuration_uuid`, но другими родителями), и проба не имеет права их считать своими.
    """
    out = {}
    for table in (TABLE, CONTENT_TABLE):
        out[table] = int(one(cur, f"SELECT count(*) FROM {table} "
                                  "WHERE configuration_uuid = %s::uuid",
                             [str(cfg_uuid)]) or 0)
    circle = (f"(SELECT object_uuid FROM {TABLE} WHERE configuration_uuid = %s::uuid)")
    for table in (FORMS_TABLE, COMMANDS_TABLE):
        out[table] = int(one(cur, f"SELECT count(*) FROM {table} "
                                  "WHERE parent_type = %s AND parent_uuid IN " + circle,
                             [PARENT_TYPE, str(cfg_uuid)]) or 0)
    out[FORM_EXT_TABLE] = int(one(
        cur,
        f"SELECT count(*) FROM {FORM_EXT_TABLE} WHERE parent_type = %s AND parent_uuid IN "
        + circle,
        [PARENT_TYPE, str(cfg_uuid)]) or 0)
    return out


def view_counts(cur, cfg_uuid):
    """Строки витрин текущего состояния: текущность читается витриной, а не таблицей."""
    return {
        TABLE: int(one(cur, f"SELECT count(*) FROM {CRITERION_VIEW} "
                            "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0),
        CONTENT_TABLE: int(one(cur, f"SELECT count(*) FROM {CONTENT_VIEW} "
                                    "WHERE configuration_uuid = %s::uuid",
                               [str(cfg_uuid)]) or 0),
    }


def expected_counts(baseline):
    """Ожидаемое число строк каждой таблицы круга по эталону — пятью таблицами, не одним."""
    return {
        TABLE: baseline["criteria"],
        CONTENT_TABLE: baseline["content"],
        FORM_EXT_TABLE: baseline["form_ext"],
        FORMS_TABLE: baseline["forms"],
        COMMANDS_TABLE: baseline["commands"],
    }


def foreign_counts(cur, own_cfg, own_parents):
    """Строки круговых таблиц, НЕ относящиеся к кругам пробы (чужие круги).

    Глобальное «таблица пуста» пробой не было и не является: строки других конфигураций и
    строки детей внешнего контура — штатное состояние базы. `own_parents` — uuid критериев
    проверяемых конфигураций: у `form_ext` ноги конфигурации нет, её область видимости
    задаёт строка формы (шаг 1.5 миграции V51).
    """
    cfgs = [str(item) for item in own_cfg]
    parents = [str(item) for item in own_parents]
    out = {}
    for table in (TABLE, CONTENT_TABLE):
        cur.execute(f"SELECT COALESCE(configuration_uuid::text, '-'), count(*) FROM {table} "
                    "WHERE NOT (configuration_uuid = ANY(%s::uuid[])) GROUP BY 1", [cfgs])
        out[table] = {str(row[0]).lower(): int(row[1]) for row in cur.fetchall()}
    for table in (FORMS_TABLE, COMMANDS_TABLE, FORM_EXT_TABLE):
        cur.execute(f"SELECT parent_type || '|' || COALESCE(parent_uuid::text, '-'), "
                    f"count(*) FROM {table} "
                    "WHERE NOT (parent_uuid = ANY(%s::uuid[])) GROUP BY 1", [parents])
        out[table] = {str(row[0]).lower(): int(row[1]) for row in cur.fetchall()}
    return out



# ── статическая часть: контракт слоя, круг таблиц, порядок снятия, писатели ─────────────
def check_layer_contract():
    """Слой и контракт: закрытый ответ, круг таблиц, порядок снятия, писатели, словари.

    Здесь же проверяется, что каждый словарь состояний, который умеет называть разбор
    (`STATE_VOCABULARIES`), назван и контрактом ответа: состояние, которого нет в ответе,
    читается нулём и маскируется под «такого состояния нет» (M5, C1).
    """
    print("\n=== контракт слоя: ответ, круг таблиц, порядок снятия, писатели ===")
    defaults = filter_criteria_defaults()
    check("ответ стадии называется ключом стадии узла (правило C3)",
          defaults.get("stage") == STAGE_FILTER_CRITERIA, str(defaults.get("stage")))
    check("круг таблиц вида объявлен контрактом и это именно две таблицы вида",
          tuple(FILTER_CRITERIA_TABLES) == (TABLE, CONTENT_TABLE),
          ", ".join(FILTER_CRITERIA_TABLES))
    check("таблицы вида названы чужим кругом стадии (`FOREIGN_STAGE_TABLES`), круг S4 их не "
          "называет своим (правило C3)",
          all(table in FOREIGN_STAGE_TABLES for table in FILTER_CRITERIA_TABLES)
          and not (set(FILTER_CRITERIA_TABLES) & set(S4_CHILD_TABLES)),
          "чужих: " + ", ".join(FOREIGN_STAGE_TABLES))
    check("строка вида стоит в круге версионности, строки перечня — вне его (Q2, вариант A)",
          TABLE in CONFIGURATION_VERSIONED_TABLES
          and CONTENT_TABLE not in CONFIGURATION_VERSIONED_TABLES,
          ", ".join(CONFIGURATION_VERSIONED_TABLES))
    check("порядок снятия начинается с описаний форм и заканчивается строками вида (M7)",
          REMOVE_ORDER[0] == FORM_EXT_TABLE and REMOVE_ORDER[-1] == TABLE
          and REMOVE_ORDER.index(CONTENT_TABLE) < REMOVE_ORDER.index(TABLE),
          ", ".join(REMOVE_ORDER))
    check("пять таблиц круга снимаются и пишутся одним списком, дублей нет",
          len(set(REMOVE_ORDER)) == len(REMOVE_ORDER) == 5, ", ".join(REMOVE_ORDER))
    for table in REMOVE_ORDER:
        writer = FCL.TABLE_WRITERS.get(table)
        if writer is None:
            check(f"{table}: писатель круга объявлен", False, "в словаре слоя нет класса")
            continue
        check(f"{table}: TABLE писателя совпадает с ключом словаря слоя",
              writer.TABLE == table, writer.TABLE)
    check("формы вида пишет писатель узла V51 (второго писателя таблицы быть не должно)",
          FCL.TABLE_WRITERS[FORMS_TABLE] is ExchangePlanFormsRowWriter)
    check("описания форм пишет общий `FormExtRowWriter` (своей таблицы у описаний нет)",
          FCL.TABLE_WRITERS[FORM_EXT_TABLE] is FormExtRowWriter)
    check("команды вида пишет общий `CommandsRowWriter`",
          FCL.TABLE_WRITERS[COMMANDS_TABLE] is CommandsRowWriter)
    check("две таблицы вида пишутся писателями общего реестра (своего реестра узла нет)",
          FCL.TABLE_WRITERS[TABLE] is CONFIGURATION_OBJECT_WRITERS[TABLE]
          and FCL.TABLE_WRITERS[CONTENT_TABLE]
          is CONFIGURATION_OBJECT_WRITERS[CONTENT_TABLE])
    missing_state_keys = [column for column in FC.STATE_VOCABULARIES
                          if STATE_CONTRACT_KEYS.get(column) not in defaults]
    check("каждая колонка состояния разбора названа ключом контракта ответа (M5, C1)",
          not missing_state_keys, ", ".join(missing_state_keys))
    # Ключ контракта, которым называется каждая колонка состояния, перечислен здесь явно:
    # проверка утверждает имена ключей, а не ищет их по подстроке — иначе переименование
    # ключа осталось бы незамеченным, а карточка читает именно имена.
    for column, states in FC.STATE_VOCABULARIES.items():
        key = STATE_CONTRACT_KEYS.get(column)
        holder = defaults.get(key) if key else None
        if column in FORM_REF_CONTRACT_COLUMNS:
            holder = (defaults.get(FORM_REF_CONTRACT_KEY) or {}).get(column)
        check(f"словарь состояний `{column}` замкнут в контракте ответа (ключ `{key}`)",
              isinstance(holder, dict) and set(states) <= set(holder),
              "словарь контракта: "
              + (", ".join(sorted(holder)) if isinstance(holder, dict) else repr(holder)))
    hint = stage_resume_hint(STAGE_FILTER_CRITERIA)
    check("подсказка продолжения для стадии называется слоем, а не выдумывается",
          hint == FILTER_CRITERIA_REPEAT_HINT and "load_filter_criteria" in str(hint),
          str(hint)[:120])


def check_stage_registration():
    """Состояние внесённости стадии в конвейер называется прогоном, а не решается за слой.

    П4 закрывает слой и его контракт; `STAGES`, MCP-точка входа `load_filter_criteria_tool`,
    форматтер раздела карточки и снятие круга вида в `_remove_rows` — шаг П5 того же узла.
    До П5 отсутствие называется строкой [NOTE]: проба не считает отсутствующую стадию
    провалом и не делает вид, что она есть. Когда шаг П5 сделан, эта же проба проверяет
    позицию (2.7 — сразу после S4f и до S4b) и раздел конвейера.
    """
    print("\n=== внесённость стадии в конвейер (граница П4/П5) ===")
    stage_ids = [stage_id for stage_id, _ in STAGES]
    if STAGE_FILTER_CRITERIA not in stage_ids:
        note(f"стадия `{STAGE_FILTER_CRITERIA}` в `STAGES` ещё НЕ внесена — это шаг П5 того "
             "же узла (позиция 2.7 нормативного списка между S4f и S4b); раздел карточки и "
             "конвейер этим прогоном не проверены: пропуск назван, а не снят молча")
        return False
    check("стадия внесена в `STAGES` ровно один раз",
          stage_ids.count(STAGE_FILTER_CRITERIA) == 1, ", ".join(stage_ids))
    index = stage_ids.index(STAGE_FILTER_CRITERIA)
    check("позиция держит порядок нормативного списка: сразу после S4f и до S4b",
          index > 0 and stage_ids[index - 1] == STAGE_EXCHANGE_PLANS
          and stage_ids[index + 1] == STAGE_OBJECT_MODULES, ", ".join(stage_ids))
    note("стадия уже в `STAGES` (шаг П5 сделан): конвейер и раздел карточки проверяются "
         "этим прогоном ниже")
    return True


def make_broken_fixture(dump_dir):
    """Фикстура «файл круга не разбирается» (каталог плоский — примитивность вида, замер 1.1).

    uuid фикстуры совпадает с uuid выгрузки-источника, поэтому заголовок находится, и отказ
    обязан быть про файл, а не про заголовок (приём фикстур V48–V51).
    """
    import shutil

    fixture = FIXTURE_DIR / "BrokenFilterCriteria"
    if fixture.exists():
        shutil.rmtree(fixture)
    (fixture / FC.DIR_NAME).mkdir(parents=True, exist_ok=True)
    shutil.copy(dump_dir / "Configuration.xml", fixture / "Configuration.xml")
    files = sorted((dump_dir / FC.DIR_NAME).glob("*.xml"))
    if not files:
        return None
    shutil.copy(files[0], fixture / FC.DIR_NAME / files[0].name)
    (fixture / FC.DIR_NAME / "БитыйКритерийОтбора.xml").write_text(
        "<MetaDataObject><FilterCriterion><Name", encoding="utf-8")
    return fixture


def make_empty_circle_fixture(dump_dir):
    """Фикстура «выгрузка без каталога вида» — состояние, которого четыре выгрузки не дают.

    Круг вида пуст: `FilterCriteria/` нет, есть только `Configuration.xml` той же
    конфигурации. Ответ обязан быть успехом с нулями и наблюдением `directory_missing`
    (прецедент Q9 узла V48), а не отказом: у конфигурации без критериев отбора их
    действительно нет.
    """
    import shutil

    fixture = FIXTURE_DIR / "NoFilterCriteria"
    if fixture.exists():
        shutil.rmtree(fixture)
    fixture.mkdir(parents=True)
    shutil.copy(dump_dir / "Configuration.xml", fixture / "Configuration.xml")
    return fixture


def check_contract_shape(report, label):
    """Ответ слоя держит закрытый контракт: ключей нет ни больше, ни меньше (C1, C3).

    Лишний ключ — разрыв контракта для читающего карточку; недостающий читается нулём и
    маскируется под «данных нет». Оба варианта правкой не лечатся, поэтому провал здесь
    дороже, чем кажется.
    """
    defaults = filter_criteria_defaults()
    extra = sorted(set(report) - set(defaults))
    missing = sorted(set(defaults) - set(report))
    check(f"{label}: ответ слоя не привносит ключей сверх контракта", not extra,
          "лишние: " + ", ".join(extra))
    check(f"{label}: каждый ключ контракта присутствует в ответе (C1)", not missing,
          "нет: " + ", ".join(missing))
    check(f"{label}: ключ стадии назван тем же адресом, что в контракте",
          report.get("stage") == STAGE_FILTER_CRITERIA, str(report.get("stage")))
    check(f"{label}: таблицы ответа — две таблицы вида, порядок контракта сохранён",
          report.get("tables") == list(FILTER_CRITERIA_TABLES), str(report.get("tables")))
    for column, states in FC.STATE_VOCABULARIES.items():
        key = STATE_CONTRACT_KEYS[column]
        holder = report.get(key)
        if column in FORM_REF_CONTRACT_COLUMNS:
            holder = (holder or {}).get(column)
        check(f"{label}: словарь состояний `{column}` в ответе замкнут и полон (M5)",
              isinstance(holder, dict) and set(holder) == set(states),
              "получено: " + (", ".join(sorted(holder)) if isinstance(holder, dict)
                              else repr(holder)))


def check_refusals(cur, dump_dir, cfg_uuid):
    """Отказы слоя называются состоянием контракта и не меняют круг таблиц (C1, C2)."""
    print("\n=== отказы: каталог, расхождение uuid, отсутствие заголовка, битый файл ===")
    missing_dir = FCL.load_filter_criteria(str(DUMP_ROOT / "_нет_такого_каталога"))
    check("каталог, которого нет, отклонён, а не сведён к нулям",
          missing_dir["status"] == STATUS_ERROR and missing_dir["success"] is False,
          str(missing_dir.get("error"))[:160])
    check_contract_shape(missing_dir, "отказ «каталога нет»")

    other_uuid = str(uuid_module.uuid4())
    mismatch = FCL.load_filter_criteria(str(dump_dir), configuration_uuid=other_uuid)
    check("расхождение uuid каталога и переданного — отказ, а не выбор одного",
          mismatch["status"] == STATUS_ERROR and other_uuid in (mismatch.get("error") or ""),
          str(mismatch.get("error"))[:160])

    unloaded = None
    for name in UNLOADED_CANDIDATES:
        candidate = DUMP_ROOT / name
        if not candidate.is_dir():
            continue
        info = configuration_uuid_from_layout(str(candidate))
        if "uuid" in info and not find_configuration(str(info["uuid"])):
            unloaded = candidate
            break
    if unloaded is None:
        note("выгрузки без строки заголовка среди кандидатов нет — отказ «заголовка нет» "
             "этим прогоном не проверен; отсутствие проверки названо, а не снято молча")
    else:
        no_header = FCL.load_filter_criteria(str(unloaded))
        check("без строки заголовка слой отказывает и называет точку входа",
              no_header["status"] == STATUS_ERROR
              and "load_1c_catalog_tool" in (no_header.get("error") or ""),
              str(no_header.get("error"))[:200])
        check("отказ без заголовка не называет конфигурацию, которой нет",
              no_header.get("configuration_id") is None, str(no_header)[:160])

    before = circle_counts(cur, cfg_uuid)
    fixture = make_broken_fixture(dump_dir)
    if fixture is None:
        note("выгрузка без файлов вида — фикстура битого файла не построена; случай отказа "
             "разбора на этом прогоне не проверен")
        return before
    broken = FCL.load_filter_criteria(str(fixture))
    check("битый файл круга останавливает стадию", broken["status"] == STATUS_ERROR,
          (broken.get("error") or "")[:200])
    check("отказ разбора называет файл и причину",
          "БитыйКритерийОтбора.xml" in (broken.get("error") or ""),
          (broken.get("error") or "")[:200])
    after = circle_counts(cur, cfg_uuid)
    check("ни одна строка круга не записана и прежние не сняты (приём V12/V46)",
          after == before, f"до {before}, после {after}")
    check("отказ называет, чем продолжить",
          any("load_filter_criteria" in w for w in broken.get("warnings") or []),
          str(broken.get("warnings"))[:160])
    check_contract_shape(broken, "отказ «битый файл»")
    return before

    fixture.mkdir(parents=True)
    shutil.copy(dump_dir / "Configuration.xml", fixture / "Configuration.xml")
    return fixture


def check_written(cur, cfg_uuid, report, baseline, label):
    """Числа ответа равны строкам таблиц, а строки таблиц равны эталону замера.

    Сверяются три круга, а не один: ответ ↔ таблицы ↔ эталон. Ответ, равный самому себе,
    ничего не утверждает; таблицы без ответа не читает карточка (приём проб V49–V51).
    """
    counts = circle_counts(cur, cfg_uuid)
    want = expected_counts(baseline)
    check(f"{label}: строки пяти таблиц равны эталону замера", counts == want,
          f"база {counts}, эталон {want}")
    from_answer = {
        TABLE: int(report.get("filter_criteria_written") or 0),
        CONTENT_TABLE: int(report.get("content_written") or 0),
        FORM_EXT_TABLE: int(report.get("form_ext_written") or 0),
        FORMS_TABLE: int(report.get("forms_written") or 0),
        COMMANDS_TABLE: int(report.get("commands_written") or 0),
    }
    check(f"{label}: числа ответа равны строкам таблиц (пятью таблицами, не одним итогом)",
          from_answer == counts, f"ответ {from_answer}, база {counts}")
    written_map = {str(key): int(value)
                   for key, value in (report.get("written_by_table") or {}).items()}
    check(f"{label}: written_by_table называет те же пять таблиц и те же числа",
          written_map == counts, str(report.get("written_by_table")))
    total = int(report.get("rows_written") or 0)
    check(f"{label}: итог rows_written равен сумме пяти таблиц",
          total == sum(counts.values()), f"ответ {total}, сумма {sum(counts.values())}")
    views = view_counts(cur, cfg_uuid)
    check(f"{label}: витрины текущего состояния отдают весь круг (одна ревизия, D8)",
          views == {TABLE: counts[TABLE], CONTENT_TABLE: counts[CONTENT_TABLE]}, str(views))
    check(f"{label}: файлов круга найдено и прочитано — по эталону (замер 1.1)",
          int(report.get("files_found") or 0) == baseline["files"]
          and int(report.get("files_read") or 0) == baseline["files"],
          f"найдено {report.get('files_found')}, прочитано {report.get('files_read')}")
    return counts


# Группировка, которой проверяется каждая колонка состояния: запрос строится по таблице,
# которой принадлежит колонка (`STATE_VOCABULARY_TABLES` разбора), а не по одной таблице.
STATE_GROUP_SQL = {
    "properties_state": f"SELECT properties_state, count(*) FROM {TABLE} "
                        "WHERE configuration_uuid = %s::uuid GROUP BY 1",
    "content_state": f"SELECT content_state, count(*) FROM {TABLE} "
                     "WHERE configuration_uuid = %s::uuid GROUP BY 1",
    "children_state": f"SELECT children_state, count(*) FROM {TABLE} "
                      "WHERE configuration_uuid = %s::uuid GROUP BY 1",
    "type_parse_state": f"SELECT type_parse_state, count(*) FROM {TABLE} "
                        "WHERE configuration_uuid = %s::uuid GROUP BY 1",
    "type_multiplicity": f"SELECT type_multiplicity, count(*) FROM {TABLE} "
                         "WHERE configuration_uuid = %s::uuid GROUP BY 1",
    "default_form_state": f"SELECT default_form_state, count(*) FROM {TABLE} "
                          "WHERE configuration_uuid = %s::uuid GROUP BY 1",
    "auxiliary_form_state": f"SELECT auxiliary_form_state, count(*) FROM {TABLE} "
                            "WHERE configuration_uuid = %s::uuid GROUP BY 1",
    "target_resolve_state": f"SELECT target_resolve_state, count(*) FROM {CONTENT_TABLE} "
                            "WHERE configuration_uuid = %s::uuid GROUP BY 1",
}
# Ключ эталона, под которым лежат числа этой колонки (вложенный — только для ссылок на форму).
STATE_BASELINE_KEY = {
    "properties_state": "props",
    "content_state": "content_states",
    "children_state": "children",
    "type_parse_state": "type_state",
    "type_multiplicity": "multiplicity",
    "default_form_state": "form_ref",
    "auxiliary_form_state": "form_ref",
    "target_resolve_state": "resolve",
}


def check_state_maps(cur, cfg_uuid, report, baseline, label):
    """Состояния: ответ = строки таблиц = эталон замера (двумя равенствами, не одним).

    Одно только равенство ответа таблице ничего не утверждает про выгрузку, а одно равенство
    эталону не утверждает, что ответ эти строки назвал.
    """
    for column in FC.STATE_VOCABULARIES:
        got = group_counts(cur, STATE_GROUP_SQL[column], [str(cfg_uuid)])
        holder = baseline[STATE_BASELINE_KEY[column]]
        want = nonzero(holder.get(column) if column in FORM_REF_CONTRACT_COLUMNS else holder)
        check(f"{label}: состояния `{column}` в таблицах равны эталону замера",
              got == want, f"база {got}, эталон {want}")
        answer_map = report.get(STATE_CONTRACT_KEYS[column])
        if column in FORM_REF_CONTRACT_COLUMNS:
            answer_map = (answer_map or {}).get(column)
        check(f"{label}: ответ называет `{column}` теми же числами, что лежат в таблицах",
              nonzero(answer_map) == got, f"ответ {nonzero(answer_map)}, база {got}")



def check_type_block(cur, cfg_uuid, report, baseline, label):
    """Блок `<Type>` записан и назван: записи jsonb, классы, контейнеры, разрешение ссылок.

    Отдельной колонки под форму контейнера схема не заводит (Q6), поэтому факт `TypeSet`
    держат запись jsonb и ответ стадии: без сверки с таблицей ответ о контейнере был бы
    необязательным.
    """
    entries = int(one(
        cur, f"SELECT COALESCE(sum(jsonb_array_length(COALESCE(types, '[]'::jsonb))), 0) "
             f"FROM {TABLE} WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0)
    check(f"{label}: записей блока `<Type>` в jsonb — по эталону (замер 2.1)",
          entries == baseline["types_total"],
          f"база {entries}, эталон {baseline['types_total']}")
    check(f"{label}: ответ называет записей типа столько же, сколько в jsonb",
          int(report.get("types_total") or 0) == entries,
          f"ответ {report.get('types_total')}, база {entries}")
    containers = group_counts(
        cur, f"SELECT elem->>'container', count(*) FROM {TABLE} CROSS JOIN LATERAL "
             f"jsonb_array_elements(COALESCE(types, '[]'::jsonb)) AS elem "
             "WHERE configuration_uuid = %s::uuid GROUP BY 1", [str(cfg_uuid)])
    check(f"{label}: формы контейнера (Type/TypeSet) в jsonb равны эталону (Q6)",
          containers == nonzero(baseline["containers"]),
          f"база {containers}, эталон {nonzero(baseline['containers'])}")
    check(f"{label}: ответ называет контейнеры теми же числами, что и jsonb",
          nonzero(report.get("types_by_container")) == containers,
          f"ответ {nonzero(report.get('types_by_container'))}, база {containers}")
    classes = group_counts(
        cur, f"SELECT elem->>'class', count(*) FROM {TABLE} CROSS JOIN LATERAL "
             f"jsonb_array_elements(COALESCE(types, '[]'::jsonb)) AS elem "
             "WHERE configuration_uuid = %s::uuid GROUP BY 1", [str(cfg_uuid)])
    check(f"{label}: классов записей типа в jsonb — ровно эталон (замер 2.1, Q6)",
          classes == nonzero(baseline["classes"]),
          f"база {classes}, эталон {nonzero(baseline['classes'])}")
    resolved = int(one(
        cur, f"SELECT count(*) FROM {TABLE} CROSS JOIN LATERAL "
             f"jsonb_array_elements(COALESCE(types, '[]'::jsonb)) AS elem "
             "WHERE configuration_uuid = %s::uuid AND elem->>'resolved' = 'true'",
        [str(cfg_uuid)]) or 0)
    check(f"{label}: ссылок типа, разрешённых индексом состава, — по эталону (Q4, замер 2.3)",
          resolved == baseline["types_resolved"],
          f"база {resolved}, эталон {baseline['types_resolved']}")
    check(f"{label}: ответ называет разрешённые ссылки тем же числом",
          int(report.get("types_object_ref_resolved") or 0) == resolved,
          f"ответ {report.get('types_object_ref_resolved')}, база {resolved}")
    object_refs = nonzero(baseline["classes"]).get(CLASS_OBJECT_REF, 0)
    check(f"{label}: каждая ссылка object_ref разрешена индексом или ведёт на вид целиком "
          "(TypeSet) — третьего состояния круг не даёт (Q6)",
          resolved + baseline["types_view_wide"] == object_refs,
          f"разрешено {resolved}, вид целиком {baseline['types_view_wide']}, ссылок "
          f"{object_refs}")
    check(f"{label}: неразрешённых ссылок типа ответ не называет (замер 2.3)",
          int(report.get("types_unresolved_total") or 0) == 0,
          str(report.get("types_unresolved"))[:160])



def check_content_block(cur, cfg_uuid, report, baseline, label):
    """Перечень `<Content>`: строки, порядок, связь с ревизией вида, разрешение целей (Q4).

    Строка условия существует только через числовой id строки критерия (Q1, Q2 вариант A),
    поэтому проверка идёт через витрину текущего состояния: условие, висящее на не-текущей
    ревизии, карточкой не читается и является сиротой.
    """
    content_total = int(one(cur, f"SELECT count(*) FROM {CONTENT_TABLE} "
                                "WHERE configuration_uuid = %s::uuid",
                            [str(cfg_uuid)]) or 0)
    check(f"{label}: строк перечня в таблице — по эталону (замер 1.4: "
          f"{baseline['content']})", content_total == baseline["content"],
          f"база {content_total}, эталон {baseline['content']}")
    linked = int(one(cur, f"SELECT count(*) FROM {CONTENT_TABLE} c JOIN {CRITERION_VIEW} v "
                          "ON v.id = c.filter_criterion_id "
                          "WHERE c.configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0)
    check(f"{label}: каждая строка перечня ссылается на CURRENT-ревизию своего критерия "
          "(Q2, вариант A)", linked == content_total,
          f"связано {linked}, всего {content_total}")
    orphans = int(one(cur, f"SELECT count(*) FROM {CONTENT_TABLE} c LEFT JOIN "
                           f"{CRITERION_VIEW} v ON v.id = c.filter_criterion_id "
                           "WHERE c.configuration_uuid = %s::uuid AND v.id IS NULL",
                       [str(cfg_uuid)]) or 0)
    check(f"{label}: условий, висящих на не-текущей или чужой ревизии критерия, нет",
          orphans == 0, f"сирот: {orphans}")
    broken_link = int(one(cur,
        f"SELECT count(*) FROM {CONTENT_TABLE} c JOIN {TABLE} p "
        "ON p.id = c.filter_criterion_id WHERE c.configuration_uuid = %s::uuid "
        "AND (c.criterion_object_uuid IS DISTINCT FROM p.object_uuid "
        "OR c.criterion_full_name IS DISTINCT FROM p.full_name)",
        [str(cfg_uuid)]) or 0)
    check(f"{label}: указатель строки условия на критерий совпадает с его строкой "
          "(индексное имя, а не короткое)", broken_link == 0,
          f"расхождений: {broken_link}")
    bad_ordinal = int(one(cur,
        f"SELECT count(*) FROM (SELECT filter_criterion_id, count(*) AS cnt, "
        "min(ordinal) AS lo, max(ordinal) AS hi, count(DISTINCT ordinal) AS dist "
        f"FROM {CONTENT_TABLE} WHERE configuration_uuid = %s::uuid GROUP BY 1) s "
        "WHERE s.cnt <> s.hi - s.lo + 1 OR s.lo <> 0 OR s.dist <> s.cnt",
        [str(cfg_uuid)]) or 0)
    check(f"{label}: порядок целей внутри критерия непрерывен и не повторяется (ordinal)",
          bad_ordinal == 0, f"критериев с дефектом порядка: {bad_ordinal}")
    distinct = int(one(cur, f"SELECT count(DISTINCT target_full_name) FROM {CONTENT_TABLE} "
                             "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) or 0)
    check(f"{label}: различных целей перечня — по эталону (замер 2.2: {baseline['distinct']})",
          distinct == baseline["distinct"], f"база {distinct}, эталон {baseline['distinct']}")
    check(f"{label}: ответ называет различных целей тем же числом",
          int(report.get("targets_distinct") or 0) == distinct,
          f"ответ {report.get('targets_distinct')}, база {distinct}")
    check(f"{label}: одна цель называется несколькими критериями ровно там, где это измерено "
          "(состояние выгрузки, а не дубль записи)",
          content_total - distinct == baseline["content"] - baseline["distinct"],
          f"повторов в базе {content_total - distinct}, по эталону "
          f"{baseline['content'] - baseline['distinct']}")

    max_per_file = int(one(cur, f"SELECT COALESCE(max(content_count), 0) FROM {TABLE} "
                                 "WHERE configuration_uuid = %s::uuid",
                            [str(cfg_uuid)]) or 0)
    check(f"{label}: наибольший перечень на один критерий — по эталону (замер 1.4)",
          max_per_file == baseline["max_per_file"],
          f"база {max_per_file}, эталон {baseline['max_per_file']}")
    pair_state = int(one(cur, f"SELECT count(*) FROM {TABLE} "
                              "WHERE configuration_uuid = %s::uuid "
                              "AND (content_state = %s) <> (content_count > 0)",
                          [str(cfg_uuid), CONTENT_WITH_CONTENT]) or 0)
    check(f"{label}: состояние перечня и его счётчик образуют пару (CHECK схемы)",
          pair_state == 0, f"нарушений пары: {pair_state}")
    check(f"{label}: индекс состава доступен ответу (иначе цели не разрешались бы, Q4)",
          report.get("index_available") is True, str(report.get("index_available")))
    if baseline["content"]:
        incomplete = int(one(cur,
            f"SELECT count(*) FROM {CONTENT_TABLE} WHERE configuration_uuid = %s::uuid "
            "AND target_resolve_state = %s AND (target_object_uuid IS NULL "
            "OR target_object_type IS NULL OR target_object_id IS NULL)",
            [str(cfg_uuid), TARGET_EXACT]) or 0)
        check(f"{label}: каждая разрешённая цель названа типом, id и uuid объекта индекса (Q4)",
              incomplete == 0, f"неполных строк: {incomplete}")
        by_type = group_counts(cur,
            f"SELECT target_object_type, count(*) FROM {CONTENT_TABLE} "
            "WHERE configuration_uuid = %s::uuid GROUP BY 1", [str(cfg_uuid)])
        check(f"{label}: состав целей по видам метаданных равен эталону (замер 2.2)",
              by_type == nonzero(baseline["target_types"]),
              f"база {by_type}, эталон {nonzero(baseline['target_types'])}")
        check(f"{label}: ответ называет цели по видам метаданных теми же числами",
              nonzero(report.get("targets_by_object_type")) == by_type,
              f"ответ {nonzero(report.get('targets_by_object_type'))}, база {by_type}")
        check(f"{label}: целей, оставшихся неразрешёнными при доступном индексе, нет "
              "(замер 2.2: все цели exact)",
              int(report.get("content_unresolved_total") or 0) == 0,
              str(report.get("unresolved_targets"))[:160])



def check_children(cur, cfg_uuid, report, baseline, label):
    """Дети вида: формы, их описания и команды относятся своим родителям (Q3, замер 1.2).

    Таблицы `forms`, `form_ext`, `commands` общие для внешнего контура и для видов
    конфигурации, поэтому проверка идёт по предикату родителя: строка обязана называть
    `parent_type` вида конфигурации и uuid конкретного критерия, а перечни `form_names` и
    `command_uuids` строки вида обязаны совпадать с фактическими детьми.
    """
    forms_ok = int(one(cur, f"SELECT count(*) FROM {FORMS_TABLE} f JOIN {CRITERION_VIEW} v "
                            "ON v.object_uuid = f.parent_uuid WHERE f.configuration_uuid = "
                            "%s::uuid AND f.parent_type = %s",
                        [str(cfg_uuid), PARENT_TYPE]) or 0)
    check(f"{label}: каждая строка формы ссылается на CURRENT-ревизию своего критерия",
          forms_ok == baseline["forms"], f"связано {forms_ok}, ожидается {baseline['forms']}")
    form_ext_ok = int(one(cur,
        f"SELECT count(*) FROM {FORM_EXT_TABLE} e "
        f"JOIN {current_view(FORMS_TABLE)} cf ON cf.id = e.form_id "
        f"JOIN {CRITERION_VIEW} v ON v.object_uuid = e.parent_uuid "
        "WHERE e.parent_type = %s AND v.configuration_uuid = %s::uuid",
        [PARENT_TYPE, str(cfg_uuid)]) or 0)
    check(f"{label}: каждое описание формы ссылается на CURRENT-ревизию своей формы (V14/V51)",
          form_ext_ok == baseline["form_ext"],
          f"связано {form_ext_ok}, ожидается {baseline['form_ext']}")
    commands_ok = int(one(cur,
        f"SELECT count(*) FROM {COMMANDS_TABLE} c JOIN {CRITERION_VIEW} v "
        "ON v.object_uuid = c.parent_uuid WHERE c.configuration_uuid = %s::uuid "
        "AND c.parent_type = %s", [str(cfg_uuid), PARENT_TYPE]) or 0)
    check(f"{label}: каждая команда ссылается на CURRENT-ревизию своего критерия",
          commands_ok == baseline["commands"],
          f"связано {commands_ok}, ожидается {baseline['commands']}")
    cur.execute(f"SELECT form_names FROM {TABLE} WHERE configuration_uuid = %s::uuid",
                [str(cfg_uuid)])
    names = sorted(item for row in cur.fetchall() for item in pg_array_items(row[0]))
    cur.execute(f"SELECT name FROM {FORMS_TABLE} WHERE parent_type = %s "
                "AND parent_uuid IN (SELECT object_uuid FROM " + TABLE
                + " WHERE configuration_uuid = %s::uuid)", [PARENT_TYPE, str(cfg_uuid)])
    real_forms = sorted(str(row[0]) for row in cur.fetchall())
    check(f"{label}: перечень `form_names` строки вида совпадает с фактическими формами",
          names == real_forms, f"перечень {names}, строк {real_forms}")
    cur.execute(f"SELECT command_uuids FROM {TABLE} WHERE configuration_uuid = %s::uuid",
                [str(cfg_uuid)])
    listed = sorted(str(item).lower() for row in cur.fetchall()
                    for item in pg_array_items(row[0]))
    cur.execute(f"SELECT uuid FROM {COMMANDS_TABLE} WHERE parent_type = %s "
                "AND parent_uuid IN (SELECT object_uuid FROM " + TABLE
                + " WHERE configuration_uuid = %s::uuid)", [PARENT_TYPE, str(cfg_uuid)])
    actual = sorted(str(row[0]).lower() for row in cur.fetchall())
    check(f"{label}: перечень `command_uuids` строки вида совпадает с командами (uuid[] "
          "читается разбором литерала массива)", listed == actual,
          f"перечень {listed}, фактических {actual}")
    child_state_bad = int(one(cur,
        f"SELECT count(*) FROM {TABLE} p WHERE p.configuration_uuid = %s::uuid AND (("
        f"p.children_state = %s AND NOT (EXISTS (SELECT 1 FROM {FORMS_TABLE} f "
        f"WHERE f.parent_uuid = p.object_uuid AND f.parent_type = %s) OR EXISTS "
        f"(SELECT 1 FROM {COMMANDS_TABLE} c WHERE c.parent_uuid = p.object_uuid "
        f"AND c.parent_type = %s))) OR (p.children_state = %s AND (EXISTS "
        f"(SELECT 1 FROM {FORMS_TABLE} f WHERE f.parent_uuid = p.object_uuid) OR EXISTS "
        f"(SELECT 1 FROM {COMMANDS_TABLE} c WHERE c.parent_uuid = p.object_uuid))))",
        [str(cfg_uuid), CHILD_WITH_CONTENT, PARENT_TYPE, PARENT_TYPE,
         CHILD_EMPTY_CONTENT]) or 0)
    check(f"{label}: состояние детей образует пару с фактическим наличием детей (M5)",
          child_state_bad == 0, f"нарушений пары: {child_state_bad}")



def check_index_reconciliation(cur, cfg_uuid, cfg_id, report, baseline, label):
    """Сверка двух ног круга с независимым запросом к индексу состава (Н6, Q5, Q7).

    Ответ слоя считает записи `FilterCriterion.<Имя>` по строкам `configuration_objects`;
    проба считает их тем же запросом напрямую — совпадение двух чисел и есть проверка того,
    что разрешение целей и сверка файлов держатся индекса, а не повторного разбора
    `ConfigDumpInfo.xml`.
    """
    # Верхняя запись вида — строка индекса без `parent_name`: индекс моделирует детей вида
    # тем же `object_type` и точечным именем (замер 1.2: 17 строк вида на 15 верхних), и
    # именно верхние записи сравнимы с числом файлов регистрации (тот же критерий, что у
    # `kind_root_index_rows` разбора).
    index_rows = int(one(cur, "SELECT count(*) FROM configuration_objects "
                              "WHERE configuration_id = %s AND object_type = %s "
                              "AND COALESCE(parent_name, '') = ''",
                          [int(cfg_id), INDEX_OBJECT_TYPE]) or 0)
    check(f"{label}: записей вида в индексе состава — по эталону (замер 1.1)",
          index_rows == baseline["index_rows"],
          f"база {index_rows}, эталон {baseline['index_rows']}")
    check(f"{label}: ответ называет записей индекса своего вида столько же, сколько в БД",
          int(report.get("index_kind_records") or 0) == index_rows,
          f"ответ {report.get('index_kind_records')}, база {index_rows}")
    check(f"{label}: файлов регистрации ровно столько, сколько записей индекса (замер 1.1)",
          int(report.get("files_found") or 0) == index_rows,
          f"файлов {report.get('files_found')}, записей {index_rows}")
    for key in ("index_only", "file_only", "uuid_mismatch"):
        check(f"{label}: расхождений круга `{key}` нет (замер 1.1 даёт равенство кругов)",
              not (report.get(key) or []), str(report.get(key))[:160])
    check(f"{label}: расхождений детей вида с индексом нет (замер 1.2)",
          not (report.get("child_mismatches") or [])
          and int(report.get("child_mismatch_total") or 0) == 0,
          str(report.get("child_mismatches"))[:160])
    check(f"{label}: псевдо-записей индекса названо — по эталону (замер 1.2: {baseline['pseudo']})",
          int(report.get("index_pseudo_entries_total") or 0) == baseline["pseudo"],
          f"ответ {report.get('index_pseudo_entries_total')}, эталон {baseline['pseudo']}")
    check(f"{label}: псевдо-записи названы ключами и не являются детьми вида (Q7)",
          len(report.get("index_pseudo_entries") or []) == baseline["pseudo"],
          str(report.get("index_pseudo_entries"))[:160])
    check(f"{label}: расхождений объявления вида с его каталогом нет",
          int(report.get("declaration_mismatch_total") or 0) == 0
          and not (report.get("declaration_mismatches") or []),
          str(report.get("declaration_mismatches"))[:160])
    check(f"{label}: ни одного неназванного свойства или значения круг не даёт (замер 2.4)",
          not (report.get("unknown_properties") or {})
          and not (report.get("unknown_value_properties") or {}),
          str(report.get("unknown_properties")))


def check_revision_stamp(cur, cfg_uuid, baseline, label, moment=None):
    """Версионность и метка загрузки: одна ревизия, один штамп события, автор — загрузка.

    `moment` задаётся повторным прогоном: строки одного события обязаны нести одну метку
    (M2), и проверить это можно только сравнением с названным значением, а не с часами двух
    прогонов (колонка хранит секунды, и два вызова в пределах секунды дали бы равную метку).
    """
    if not baseline["criteria"]:
        note(f"{label}: круг пуст — цепь ревизий и метку загрузки по нему не проверяют; "
             "пустой круг назван, а не скрыт")
        return
    check(f"{label}: max(revision_no) = {FIRST_REVISION} (D8: история состояний не заводится)",
          one(cur, f"SELECT max(revision_no) FROM {TABLE} "
                   "WHERE configuration_uuid = %s::uuid", [str(cfg_uuid)]) == FIRST_REVISION)
    authors = group_counts(cur, f"SELECT changed_by, count(*) FROM {TABLE} "
                                "WHERE configuration_uuid = %s::uuid GROUP BY 1",
                           [str(cfg_uuid)])
    check(f"{label}: автором строк названа загрузка ({CHANGED_BY_LOAD})",
          authors == {CHANGED_BY_LOAD: baseline["criteria"]}, str(authors))
    stamps = group_counts(cur, f"SELECT changed_at::text, count(*) FROM {TABLE} "
                               "WHERE configuration_uuid = %s::uuid GROUP BY 1",
                          [str(cfg_uuid)])
    check(f"{label}: строки вида несут одну метку загрузки (M2)", len(stamps) == 1,
          str(stamps))
    if moment is not None and stamps:
        check(f"{label}: метка равна названной вызовом, а не часам транзакции (M2)",
              next(iter(stamps)) == moment.strftime("%Y-%m-%d %H:%M:%S"), str(stamps))
    check(f"{label}: каждая строка вида помечена зафиксированной (is_committed)",
          one(cur, f"SELECT count(*) FROM {TABLE} WHERE configuration_uuid = %s::uuid "
                   "AND is_committed", [str(cfg_uuid)]) == baseline["criteria"])
    for table in (FORMS_TABLE, COMMANDS_TABLE):
        count = int(one(cur, f"SELECT count(*) FROM {table} WHERE parent_type = %s "
                              "AND revision_no = %s AND changed_by = %s AND is_committed "
                              "AND parent_uuid IN (SELECT object_uuid FROM " + TABLE
                              + " WHERE configuration_uuid = %s::uuid)",
                          [PARENT_TYPE, FIRST_REVISION, CHANGED_BY_LOAD,
                           str(cfg_uuid)]) or 0)
        expected = baseline["forms"] if table == FORMS_TABLE else baseline["commands"]
        check(f"{label}: {table}: каждая строка детей — ревизия {FIRST_REVISION}, автор "
              f"{CHANGED_BY_LOAD}, зафиксирована", count == expected,
              f"правильных {count}, ожидается {expected}")



def module_rows_of(cur, cfg_uuid):
    """Строк `bsl_modules` с путями этого каталога вида (тела пишет узел V47, Q8).

    Область счёта держится `configuration_uuid` + префикса пути, а не круга вида: строки
    тел принадлежат узлу V47 и живут независимо от того, есть ли в базе строки вида, —
    считать их по `parent_uuid` круга значило бы получить ноль до загрузки и «прирост» после
    (замер 02.11.2026: V47 пишет 2 строки для MinCfg, 6 для BGU2, 3 для BP3, 0 для KomMag).
    Число сравнивается до загрузки и после неё: узел вида не имеет права ни добавить, ни
    снять текст модуля — два узла одно чтение одного файла не делают.
    """
    return int(one(cur, "SELECT count(*) FROM bsl_modules WHERE configuration_uuid = "
                        "%s::uuid AND file_path LIKE %s",
                    [str(cfg_uuid), FC.DIR_NAME + "/%"]) or 0)


def check_answer_consistency(cur, report, baseline, label):
    """Ответ описывает один факт одними числами и называет то, чего он не делает (M7, Q8).

    Два счётчика одного факта в ответе расходятся — карточка показывает оба, и читатель не
    обязан догадываться, какому верить. Граница круга (тела модулей, справочные ресурсы)
    называется предупреждением, а не молчанием: «не делали» и «сделали пустым» — разные
    ответы.
    """
    kinds = report.get("module_files_by_kind") or {}
    check(f"{label}: файлы модулей по родам согласованы с их общим числом",
          sum(int(value) for value in kinds.values())
          == int(report.get("module_files_total") or 0) == baseline["module_files"],
          f"по родам {kinds}, всего {report.get('module_files_total')}, эталон "
          f"{baseline['module_files']}")
    formats = report.get("form_ext_formats") or {}
    check(f"{label}: форматы описаний форм согласованы с числом строк form_ext",
          sum(int(value) for value in formats.values())
          == int(report.get("form_ext_total") or 0) == baseline["form_ext"],
          f"форматы {formats}, эталон {baseline['form_ext']}")
    check(f"{label}: наблюдения круга названы, а не промолчаны (Q7)",
          nonzero(report.get("counts_by_ext_observation"))
          == nonzero(baseline["ext_observations"]),
          f"ответ {nonzero(report.get('counts_by_ext_observation'))}, эталон "
          f"{nonzero(baseline['ext_observations'])}")
    if baseline["module_files"]:
        check(f"{label}: ответ называет, что тела модулей пишет узел V47 (Q8 — граница круга)",
              any("V47" in warning for warning in report.get("warnings") or []),
              str(report.get("warnings"))[:200])
    for kind in baseline["ext_observations"]:
        check(f"{label}: справочные ресурсы названы наблюдением `{kind}` в ответе (Q7)",
              any(str(kind) in warning for warning in report.get("warnings") or []),
              str(report.get("warnings"))[:200])
    check(f"{label}: статистика затронутых таблиц пересобрана (мера V46)",
          int(report.get("statistics_refreshed") or 0) == len(REMOVE_ORDER),
          f"пересобрано {report.get('statistics_refreshed')} из {len(REMOVE_ORDER)}")
    check(f"{label}: подсказка продолжения есть в ответе успеха",
          any(FILTER_CRITERIA_REPEAT_HINT in warning
              for warning in report.get("warnings") or []),
          str(report.get("warnings"))[:200])
    check(f"{label}: отказа или предупреждения о недоступном индексе ответа нет (Н6)",
          report.get("error") is None
          and not any("Индекс состава" in warning
                      for warning in report.get("warnings") or []),
          str(report.get("error"))[:160])
    if baseline["criteria"]:
        check(f"{label}: ответ называет момент загрузки строк круга (M2 — одна метка)",
              any("Момент загрузки строк круга" in warning
                  for warning in report.get("warnings") or []),
              str(report.get("warnings"))[:200])



def check_idempotency(cur, dump_dir, cfg_uuid, baseline, label):
    """Повтор той же выгрузки даёт тот же круг (критерий идемпотентности раздела 7 плана).

    Снятое и записанное обязаны равняться эталону, строки — не удваиваться, `revision_no` —
    не расти (D8), uuid строк — оставаться прежними: на них ссылается строка перечня и
    читатель. Формулировка плана «снимает прежние строки и пишет заново» проверяется числом
    снятых строк по каждой из пяти таблиц, а не только итогом.
    """
    before = circle_counts(cur, cfg_uuid)
    uuids_before = sorted(parents_of(cur, cfg_uuid))
    check(f"{label}: до повтора в таблицах ровно круг выгрузки",
          before == expected_counts(baseline), f"до {before}")
    # Метка повторной загрузки называется вызовом явно: строки одного события обязаны нести
    # одну метку (M2), и проверить это можно только сравнением с названным значением.
    moment = datetime.now().replace(microsecond=0) + timedelta(days=1)
    started = time.monotonic()
    second = FCL.load_filter_criteria(str(dump_dir), configuration_uuid=str(cfg_uuid),
                                     changed_at=moment)
    elapsed = time.monotonic() - started
    check(f"{label}: повторный вызов возвращает успех",
          second.get("success") is True and second.get("status") == STATUS_OK,
          str(second.get("error"))[:200])
    check_contract_shape(second, f"{label} ответ")
    counts2 = check_written(cur, cfg_uuid, second, baseline, f"{label} после")
    check_state_maps(cur, cfg_uuid, second, baseline, f"{label} после")
    check(f"{label}: повтор называет снятые строки прежним кругом по каждой таблице (M7)",
          {str(key): int(value)
           for key, value in (second.get("removed_by_table") or {}).items()} == before,
          f"снято {second.get('removed_by_table')}, было {before}")
    check(f"{label}: снятое и записанное на повторе равны кругу",
          int(second.get("removed_previous") or 0) == int(second.get("rows_written") or 0)
          == sum(expected_counts(baseline).values()),
          f"снято {second.get('removed_previous')}, записано {second.get('rows_written')}")
    check(f"{label}: строки не удваиваются", counts2 == before, f"после {counts2}")
    uuids_after = sorted(parents_of(cur, cfg_uuid))
    check(f"{label}: uuid строк вида не меняются при повторе (на них ссылается перечень)",
          uuids_after == uuids_before,
          f"до {len(uuids_before)}, после {len(uuids_after)}")
    check_revision_stamp(cur, cfg_uuid, baseline, f"{label}", moment=moment)
    check(f"{label}: повтор предупреждает, что прежние строки сняты (M7 — снятие названо)",
          any("сняты перед записью" in warning for warning in second.get("warnings") or []),
          str(second.get("warnings"))[:200])
    note(f"{label}: время повторной загрузки слоя — {elapsed:.2f} с на "
         f"{baseline['criteria']} критериев и {baseline['content']} условий")
    return second


def check_empty_circle(cur, cfg_uuid, dump_dir, baseline):
    """Пустой круг выгрузки — состояние, а не отказ (Q9), и снятие детей удалённого вида.

    Фикстура — каталог той же конфигурации без `FilterCriteria/`. Ни одна из четырёх
    замеренных выгрузок такого не даёт, поэтому случай держится фикстурой. Проба проверяет
    три вещи: ответ — успех с нулями и наблюдением `directory_missing`; снятие снимает
    круг целиком, включая детей критериев, которых в выгрузке больше нет (иначе формы и
    команды остались бы сиротами); нули названы, а не промолчаны.
    """
    print("\n=== пустой круг: каталога вида нет — нули названы, дети сняты (Q9, Q7) ===")
    fixture = make_empty_circle_fixture(dump_dir)
    before = circle_counts(cur, cfg_uuid)
    parents_before = sorted(parents_of(cur, cfg_uuid))
    check("перед фикстурой круг выгрузки в базе есть", any(before.values()), str(before))
    answer = FCL.load_filter_criteria(str(fixture))
    check("пустой круг — успех стадии, а не отказ (Q9)",
          answer.get("success") is True and answer.get("status") == STATUS_OK,
          str(answer.get("error"))[:200])
    check_contract_shape(answer, "пустой круг")
    check("файлов вида найдено ноль, записей не записано (нули названы)",
          int(answer.get("files_found") or 0) == 0
          and int(answer.get("rows_written") or 0) == 0
          and all(int(value or 0) == 0 for value in
                  (answer.get("written_by_table") or {}).values()),
          str(answer.get("written_by_table")))
    # Наблюдение `directory_missing` слой называет предупреждением (loader строка 631), а не
    # счётчиком `counts_by_ext_observation`: тот считает наблюдения разобранных ФАЙЛОВ круга
    # (справочные ресурсы), а здесь файла нет. Проверка держится текста предупреждения —
    # перефразировка без упоминания отсутствующего каталога была бы молчанием.
    check("отсутствие каталога вида названо наблюдением `directory_missing` (Q9)",
          any("FilterCriteria/ в выгрузке отсутствует" in warning
              for warning in answer.get("warnings") or []),
          str(answer.get("warnings"))[:200])
    check("счётчик наблюдений файлов круга при пустом круге пуст: файлов не разбирали",
          not (answer.get("counts_by_ext_observation") or {}),
          str(answer.get("counts_by_ext_observation")))
    check("снимание названо прежним кругом по каждой таблице (M7)",
          {str(key): int(value)
           for key, value in (answer.get("removed_by_table") or {}).items()} == before,
          f"снято {answer.get('removed_by_table')}, было {before}")
    after = circle_counts(cur, cfg_uuid)
    check("после пустого круга круг пуст целиком — детей сироты не остались",
          not any(after.values()), f"после {after}")
    check("uuid снятых критериев названы предикатом снятия: детей снимают и у удалённого "
          "из выгрузки вида (прецедент existing_plan_revisions V51)",
          len(parents_before) == int(answer.get("removed_by_table", {}).get(TABLE) or 0),
          f"родителей {parents_before}")
    check("ответ о пустом круге объясняет, что нули являются ответом о выгрузке",
          any("ответом о выгрузке" in warning for warning in answer.get("warnings") or []),
          str(answer.get("warnings"))[:200])
    # Фикстура сняла круг этой конфигурации — проба обязана вернуть настоящее содержимое,
    # иначе она оставила бы в базе пустой круг вместо выгруженного (приём П4 узлов V48–V51:
    # за пробой остаётся то, что в базе было, а не то, что она проверила).
    restored = FCL.load_filter_criteria(str(dump_dir))
    check("после фикстуры круг выгрузки восстановлен загрузкой настоящего каталога",
          restored.get("success") is True
          and circle_counts(cur, cfg_uuid) == expected_counts(baseline),
          str(restored.get("error") or "")[:160])
    return before



def check_no_orphans(cur):
    """Сирот в круге быть не должно: строки вида привязаны к заголовку, дети — к родителям.

    Для двух таблиц вида проверка идёт по заголовку (внешнего ключа в схеме нет осознанно,
    V20.1). Для общих таблиц детей проверка идёт по родителю: строка `forms`/`commands`
    внешнего контура несёт `configuration_uuid` самого объекта, а не строку `configurations`
    (замер 02.11.2026), поэтому «ссылается на заголовок» для них было бы неверным
    утверждением — верным является «родитель существует в индексе состава».
    """
    for table in (TABLE, CONTENT_TABLE):
        check(f"сирот нет: каждая строка {table} ссылается на строку заголовка",
              one(cur, f"SELECT count(*) FROM {table} t LEFT JOIN configurations c "
                       "ON c.uuid = t.configuration_uuid "
                       "WHERE t.configuration_uuid IS NOT NULL AND c.id IS NULL") == 0)
    for table in (FORMS_TABLE, COMMANDS_TABLE):
        check(f"сирот нет: каждый родителя вида в {table} называет индекс состава",
              one(cur, f"SELECT count(*) FROM {table} f WHERE f.parent_type = %s "
                       "AND f.parent_uuid IN (SELECT object_uuid FROM " + TABLE + ") "
                       "AND NOT EXISTS (SELECT 1 FROM configuration_objects o "
                       "WHERE o.uuid = f.parent_uuid)", [PARENT_TYPE]) == 0)
    check("сирот нет: каждое описание формы ссылается на строку формы",
          one(cur, f"SELECT count(*) FROM {FORM_EXT_TABLE} e LEFT JOIN {FORMS_TABLE} f "
                   "ON f.id = e.form_id WHERE f.id IS NULL") == 0)


def check_removal_with_header(cur):
    """Снятие заголовка обязано снять строки вида: сирот в схеме без FK быть не должно (V20.1).

    Фикстура — синтетический заголовок и по одной строке каждой из пяти таблиц круга.
    Настоящие заголовки проба не снимает: их состав проверяют проверки других узлов.
    Снятие круга конвейером (`_remove_rows`) относится к шагу П5: если его ещё нет, дефект
    сирот называется прямо и исправляется самой пробой — иначе проба оставила бы в базе то,
    что поймала.
    """
    print("\n=== снятие заголовка снимает строки вида (дефект сирот) ===")
    fixture_uuid = str(uuid_module.uuid4())
    criterion_uuid = str(uuid_module.uuid4())
    form_uuid = str(uuid_module.uuid4())
    command_uuid = str(uuid_module.uuid4())
    cur.execute("INSERT INTO configurations (name, uuid) VALUES (%s, %s::uuid) RETURNING id",
                [f"_v52_p4_fixture_{fixture_uuid[:8]}", fixture_uuid])
    fixture_id = int(cur.fetchone()[0])
    cur.execute(
        f"INSERT INTO {TABLE} (configuration_uuid, object_uuid, object_name, full_name,"
        " type_multiplicity, type_parse_state, default_form_state, auxiliary_form_state,"
        " content_state, content_count, children_state, properties_state, source_path,"
        " revision_no, changed_at, changed_by, is_committed)"
        " VALUES (%s::uuid, %s::uuid, %s, %s, 'absent', 'absent', 'absent', 'absent',"
        " 'empty_content', 0, 'empty_content', 'all_known', %s, 1, now(), %s, TRUE)"
        " RETURNING id",
        [fixture_uuid, criterion_uuid, "ФикстураКритерий",
         INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + "ФикстураКритерий",
         "FilterCriteria/ФикстураКритерий.xml", CHANGED_BY_LOAD])
    criterion_id = int(cur.fetchone()[0])
    cur.execute(
        f"INSERT INTO {CONTENT_TABLE} (filter_criterion_id, configuration_uuid,"
        " criterion_object_uuid, criterion_full_name, ordinal, target_tag, target_full_name,"
        " target_object_type, target_resolve_state, target_unresolved_path)"
        " VALUES (%s, %s::uuid, %s::uuid, %s, 0, 'Item', 'Справочник.Фикстура', 'Catalog',"
        " 'unresolved', 'Справочник.Фикстура')",
        [criterion_id, fixture_uuid, criterion_uuid,
         INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR + "ФикстураКритерий"])
    cur.execute(
        f"INSERT INTO {FORMS_TABLE} (uuid, parent_uuid, name, configuration_uuid,"
        " parent_type, revision_no, changed_at, changed_by, is_committed)"
        " VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s, 1, now(), %s, TRUE) RETURNING id",
        [form_uuid, criterion_uuid, "ФикстураФорма", fixture_uuid, PARENT_TYPE,
         CHANGED_BY_LOAD])
    form_id = int(cur.fetchone()[0])
    cur.execute(
        f"INSERT INTO {FORM_EXT_TABLE} (form_id, form_uuid, parent_uuid, parent_type,"
        " revision_no, changed_at, changed_by, is_committed)"
        " VALUES (%s, %s::uuid, %s::uuid, %s, 1, now(), %s, TRUE)",
        [form_id, form_uuid, criterion_uuid, PARENT_TYPE, CHANGED_BY_LOAD])
    cur.execute(
        f"INSERT INTO {COMMANDS_TABLE} (configuration_uuid, parent_uuid, parent_type, uuid,"
        " name, properties_state, revision_no, changed_at, changed_by, is_committed)"
        " VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s, 'all_known', 1, now(), %s, TRUE)",
        [fixture_uuid, criterion_uuid, PARENT_TYPE, command_uuid, "ФикстураКоманда",
         CHANGED_BY_LOAD])
    cur.connection.commit()
    before = circle_counts(cur, fixture_uuid)
    check("фикстура: строки всех пяти таблиц круга записаны",
          all(before[table] == 1 for table in (TABLE, CONTENT_TABLE, FORMS_TABLE,
                                               FORM_EXT_TABLE, COMMANDS_TABLE)), str(before))
    removed = delete_configuration(cfg_id=fixture_id)
    deleted = removed.get("children_deleted") or {}
    named = {table: int(deleted.get(table) or 0) for table in REMOVE_ORDER}
    if not any(named.values()):
        note("конвейер (`_remove_rows`) круг вида НЕ снимает: снятие заголовка оставило бы "
             "строки вида сиротами. Это относится к шагу П5 того же узла; проба называет "
             "дефект и убирает его за собой, а не оставляет в базе")
    else:
        for table in REMOVE_ORDER:
            check(f"delete_configuration назвал снятие строк {table}",
                  named[table] == 1, str(deleted)[:220])
    left = circle_counts(cur, fixture_uuid)
    if any(left.values()):
        FCL.remove_filter_criteria(cur, fixture_uuid, [criterion_uuid])
        cur.connection.commit()
        left = circle_counts(cur, fixture_uuid)
    check("после снятия заголовка (с правкой пробы) строк вида не осталось",
          not any(left.values()), str(left))
    check_no_orphans(cur)




def run_dump(cur, name):
    """Полный прогон слоя на одной выгрузке: загрузка → сверка → повтор → идемпотентность.

    Время слоя замеряется и называется числом (критерий раздела 7 плана): без `ANALYZE`
    читатели витрин текущего состояния платят минутами, и прогон обязан назвать то, что
    потратил сам. Граница узла V52 (тела модулей пишет V47, Q8) проверяется сравнением
    числа строк `bsl_modules` у родителей круга до и после загрузки.
    """
    dump_dir = DUMP_ROOT / name
    if not dump_dir.is_dir():
        check(f"{name}: каталог выгрузки существует", False, str(dump_dir))
        return None
    info = configuration_uuid_from_layout(str(dump_dir))
    if "uuid" not in info:
        check(f"{name}: uuid конфигурации прочитан из Configuration.xml", False,
              info.get("error"))
        return None
    cfg_uuid = str(info["uuid"])
    header = find_configuration(cfg_uuid)
    if not header:
        check(f"{name}: заголовок этой конфигурации загружен в базу", False, cfg_uuid)
        return None
    cfg_id = int(header["id"])
    baseline = BASELINE[name]
    print(f"\n=== выгрузка {name}: uuid={cfg_uuid}, configuration_id={cfg_id} ===")

    modules_before = module_rows_of(cur, cfg_uuid)
    print("--- загрузка №1 (одна транзакция на пять таблиц круга) ---")
    started = time.time()
    report = FCL.load_filter_criteria(str(dump_dir))
    first_seconds = time.time() - started
    check(f"{name}: загрузка №1 успешна",
          report.get("status") == STATUS_OK and report.get("success") is True,
          str(report.get("error"))[:300])
    if report.get("status") != STATUS_OK:
        return None
    check_contract_shape(report, f"{name} загрузка №1")
    counts = check_written(cur, cfg_uuid, report, baseline, f"{name} загрузка №1")
    check_state_maps(cur, cfg_uuid, report, baseline, f"{name} загрузка №1")
    check_type_block(cur, cfg_uuid, report, baseline, f"{name} загрузка №1")
    check_content_block(cur, cfg_uuid, report, baseline, f"{name} загрузка №1")
    check_children(cur, cfg_uuid, report, baseline, f"{name} загрузка №1")
    check_index_reconciliation(cur, cfg_uuid, cfg_id, report, baseline,
                               f"{name} загрузка №1")
    check_revision_stamp(cur, cfg_uuid, baseline, f"{name} загрузка №1")
    check_answer_consistency(cur, report, baseline, f"{name} загрузка №1")
    check(f"{name}: время слоя первой загрузки меньше границы замера (раздел 7 плана)",
          first_seconds < TIME_LIMIT_S, f"{first_seconds:.2f} с")
    note(f"{name}: время стадии S4g (загрузка №1) — {first_seconds:.2f} с на "
         f"{baseline['criteria']} критериев, {baseline['content']} условий, "
         f"{baseline['forms']} форм и {baseline['commands']} команд")
    modules_after = module_rows_of(cur, cfg_uuid)
    check(f"{name}: узел не добавил и не снял тел модулей этого каталога (Q8 — пишет V47)",
          modules_after == modules_before, f"до {modules_before}, после {modules_after}")
    note(f"{name}: тел модулей вида в `bsl_modules` — {modules_after} (их пишет узел V47; "
         f"файлов круга слой назвал {baseline['module_files']}, тексты не читал — Q8)")
    check(f"{name}: записанные строки детей относятся только родителям круга",
          counts[FORMS_TABLE] == baseline["forms"]
          and counts[COMMANDS_TABLE] == baseline["commands"], str(counts))

    print("--- загрузка №2 (идемпотентность: снял и записал заново) ---")
    second = check_idempotency(cur, dump_dir, cfg_uuid, baseline, f"{name} загрузка №2")
    check_type_block(cur, cfg_uuid, second, baseline, f"{name} загрузка №2")
    check_content_block(cur, cfg_uuid, second, baseline, f"{name} загрузка №2")
    check_children(cur, cfg_uuid, second, baseline, f"{name} загрузка №2")
    check_index_reconciliation(cur, cfg_uuid, cfg_id, second, baseline,
                               f"{name} загрузка №2")
    check_answer_consistency(cur, second, baseline, f"{name} загрузка №2")
    return cfg_uuid



def check_pipeline(cur, cfg_uuid, dump_dir, baseline, label):
    """Конвейер целиком: стадию S4g вызывает `load_catalog` (force=True по уже загруженному).

    Отдельный слой и стадия — один и тот же код, поэтому проверяется и карточка: раздел
    стадии есть, порядок разделов повторяет порядок стадий (S4f → S4g → S4b), соседние
    стадии S4f (V51) и S4b (V47) не сломаны. Порядок разделов проверяется именно в тексте
    карточки: порядок стадий в `STAGES` ещё не значит, что карточка печатает разделы в нём.
    """
    print(f"\n=== конвейер: стадия S4g внутри load_catalog ({label}) ===")
    started = time.time()
    result = load_catalog(str(dump_dir), force=True)
    pipeline_seconds = time.time() - started
    card = format_load_result(result)
    check(f"{label}: конвейер вернул успех", result.get("success") is True,
          str(result.get("error"))[:200])
    part = result.get("filter_criteria") or {}
    check(f"{label}: конвейер вернул раздел S4g закрытым контрактом стадии (C3)",
          sorted(part) == sorted(filter_criteria_defaults()),
          "лишнее: " + ", ".join(sorted(set(part) - set(filter_criteria_defaults())))
          + "; нет: " + ", ".join(sorted(set(filter_criteria_defaults()) - set(part))))
    check(f"{label}: стадия S4g конвейера успешна", part.get("status") == STATUS_OK,
          str(part.get("error"))[:200])
    check(f"{label}: числа конвейера равны эталону прямой загрузки",
          {table: int((part.get("written_by_table") or {}).get(table) or 0)
           for table in REMOVE_ORDER} == expected_counts(baseline),
          str(part.get("written_by_table")))
    check_written(cur, cfg_uuid, part, baseline, f"конвейер {label}")
    check_state_maps(cur, cfg_uuid, part, baseline, f"конвейер {label}")
    check(f"{label}: карточка загрузки содержит раздел стадии S4g",
          FILTER_CRITERIA_SECTION_HEADER in card)
    check(f"{label}: карточка называет границу круга узла V52",
          FILTER_CRITERIA_CIRCLE_BOUNDARY in card)
    order = [card.find(needle) for needle in
             (EXCHANGE_PLAN_SECTION_HEADER, FILTER_CRITERIA_SECTION_HEADER,
              OBJECT_MODULES_SECTION_HEADER)]
    check(f"{label}: порядок разделов карточки повторяет порядок стадий: S4f → S4g → S4b",
          all(index >= 0 for index in order) and order == sorted(order),
          f"позиции разделов: {order}")
    plans = result.get("exchange_plans") or {}
    modules = result.get("object_modules") or {}
    check(f"{label}: стадия S4f (V51) после встраивания S4g работает",
          plans.get("status") == STATUS_OK, str(plans.get("error"))[:200])
    check(f"{label}: стадия S4b (V47) осталась последней и работает",
          modules.get("status") in (STATUS_OK, STATUS_NOT_RUN),
          str(modules.get("error"))[:200])
    check(f"{label}: продолжение после остановки на S4g называется отдельным входом",
          "load_filter_criteria" in str(stage_resume_hint(STAGE_FILTER_CRITERIA))
          and STAGE_FILTER_CRITERIA in stages_after(STAGE_EXCHANGE_PLANS),
          str(stages_after(STAGE_EXCHANGE_PLANS))[:200])
    note(f"{label}: время конвейера целиком — {pipeline_seconds:.2f} с; время стадии S4g "
         "той же выгрузки измерена отдельно выше (сравнение называется, а не подразумевается)")


def check_corpus(cur, own_cfg):
    """Сводные числа эталона равны замерам корпуса; строки в базе — им же (замеры 1.1, 1.4).

    Проверка пишется только на полном корпусе из четырёх выгрузок: на двух выгрузках
    корпусных чисел нет, и отсутствие проверки называется в main.
    """
    print("\n=== корпус: суммарные эталоны четырёх выгрузок (замеры 1.1, 1.4, 2.2) ===")
    totals = {key: sum(entry[key] for entry in BASELINE.values())
              for key in ("files", "criteria", "content", "types_total", "pseudo")}
    check("эталон пробы по четырём выгрузкам равен корпусным замерам плана",
          totals["files"] == CORPUS["files"] and totals["criteria"] == CORPUS["criteria"]
          and totals["content"] == CORPUS["content"]
          and totals["types_total"] == CORPUS["types_total"]
          and totals["pseudo"] == CORPUS["pseudo"], str(totals))
    loaded = [str(item) for item in own_cfg]
    got_criteria = int(one(cur, "SELECT count(*) FROM " + TABLE
                             + " WHERE configuration_uuid = ANY(%s::uuid[])",
                           [loaded]) or 0)
    got_content = int(one(cur, "SELECT count(*) FROM " + CONTENT_TABLE
                             + " WHERE configuration_uuid = ANY(%s::uuid[])",
                          [loaded]) or 0)
    check(f"критериев в базе по проверенным конфигурациям = {CORPUS['criteria']} (замер 1.1)",
          got_criteria == CORPUS["criteria"], f"получено {got_criteria}")
    check(f"строк перечня в базе по проверенным конфигурациям = {CORPUS['content']} "
          "(замер 1.4)", got_content == CORPUS["content"], f"получено {got_content}")


def check_final_state(cur, own_cfg, own_parents, foreign_before):
    """Чужие круги не тронуты; состояние своих кругов называется числом (приём V50).

    Строки, записанные слоем, остаются в базе намеренно — это настоящее содержимое
    выгрузки. Сравнивается то, что обязано быть неизменным: строки других конфигураций и
    строки детей внешнего контура.
    """
    print("\n=== состояние базы после пробы: чужие круги не тронуты ===")
    for cfg_uuid in own_cfg:
        counts = circle_counts(cur, cfg_uuid)
        note(f"круг {cfg_uuid[:8]}: " + ", ".join(f"{table}={counts[table]}"
                                                  for table in REMOVE_ORDER))
    foreign_after = foreign_counts(cur, own_cfg, sorted(own_parents))
    for table in REMOVE_ORDER:
        check(f"чужие конфигурации и внешний контур проба не тронула ({table})",
              foreign_after[table] == foreign_before[table],
              f"до: {foreign_before[table]}, после: {foreign_after[table]}")
    check_no_orphans(cur)



def main() -> int:
    chosen = tuple(arg for arg in sys.argv[1:] if arg in BASELINE) or DEFAULT_DUMPS
    skip_pipeline = "--no-pipeline" in sys.argv
    print("Проба V52 П4: слой свойств критериев отбора (стадия S4g) — " + ", ".join(chosen))
    print("Загрузчик фиксирует свои транзакции. Строки слоя остаются в базе намеренно: они "
          "являются содержимым выгрузки. За пробой остаются только её фикстуры. Раздел "
          "конвейера и текст карточки проверяются, только когда стадия уже внесена в "
          "`STAGES` (шаг П5 того же узла); до этого отсутствие называется замечанием.")
    conn = connect()
    try:
        cur = conn.cursor()
        for table in REMOVE_ORDER:
            note(f"базовое состояние {table}: строк по всей базе — "
                 f"{int(one(cur, f'SELECT count(*) FROM {table}') or 0)}")
        own_cfg = []
        for name in chosen:
            info = configuration_uuid_from_layout(str(DUMP_ROOT / name))
            if "uuid" in info:
                own_cfg.append(str(info["uuid"]))
        own_parents = set()
        for cfg_uuid in own_cfg:
            own_parents.update(parents_of(cur, cfg_uuid))
        foreign_before = foreign_counts(cur, own_cfg, sorted(own_parents))
        check_layer_contract()
        registered = check_stage_registration()
        min_dir = DUMP_ROOT / "MinCfg"
        min_info = configuration_uuid_from_layout(str(min_dir))
        if "uuid" not in min_info:
            check("MinCfg доступен для отказов и фикстур", False, min_info.get("error"))
            return _summary()
        min_uuid = str(min_info["uuid"])
        check_refusals(cur, min_dir, min_uuid)
        check_removal_with_header(cur)
        tested = [cfg for cfg in (run_dump(cur, name) for name in chosen) if cfg]
        if not tested:
            check("хотя бы одна выгрузка проверена", False, "проверяемых выгрузок нет")
            return _summary()
        # Пустой круг проверяется на первой прогнанной выгрузке: фикстура снимает её круг,
        # и проба обязана вернуть настоящее содержимое (приём Q9 узла V48).
        first = chosen[0]
        first_uuid = str(configuration_uuid_from_layout(str(DUMP_ROOT / first)).get("uuid"))
        if first_uuid in tested:
            check_empty_circle(cur, first_uuid, DUMP_ROOT / first, BASELINE[first])
        else:
            note("пустой круг этим прогоном не проверен: первая выбранная выгрузка "
                 "не прошла основной прогон — отсутствие проверки названо, а не снято")
        if len(chosen) == len(BASELINE):
            check_corpus(cur, own_cfg)
        else:
            note(f"корпусные эталоны не проверяются: выбрано {len(chosen)} из "
                 f"{len(BASELINE)} выгрузок — названо, а не снято молча")
        check_final_state(cur, own_cfg, sorted(own_parents), foreign_before)
        if skip_pipeline:
            note("конвейер пропущен флагом --no-pipeline: раздел карточки и порядок стадий "
                 "этим прогоном не проверены — пропуск назван, а не снят молча")
        elif not registered:
            note("конвейер и карточка не проверяются: стадия S4g ещё не внесена в `STAGES` "
                 "(шаг П5 узла V52) — вызов load_catalog не писал бы круг вида")
        else:
            for name in chosen:
                info = configuration_uuid_from_layout(str(DUMP_ROOT / name))
                if "uuid" in info:
                    check_pipeline(cur, str(info["uuid"]), DUMP_ROOT / name, BASELINE[name],
                                   name)
        return _summary()
    finally:
        conn.close()


def _summary() -> int:
    """Итог пробы: число проваленных проверок, а не общее «успешно»."""
    print("\n" + "=" * 72)
    print(f"ИТОГ: пройдено {PASSED}, провалено {FAILED}, замечаний {len(NOTES)}")
    if FAILED:
        print("Проваленные проверки перечислены выше строками [FAIL].")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

