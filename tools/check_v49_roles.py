#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v49_roles.py — узел V49: роли конфигурации и их права (шаг П6).

Это постоянная проверка, а не проба шага: она обязана переживать и перезагрузку выгрузок,
и правки кода загрузки. Источник ожиданий — `docs/CONFIGURATION_ROLES_PLAN.md` (раздел 2 —
замеры базовой линии, раздел 7 — критерии готовности), числа названы по каталогу выгрузки,
потому что имя строки заголовка меняется вместе с выгрузкой, а каталог — адрес, по которому
проверка находит файлы.

Что сторожится — по контурам:

  1. ГРАНИЦА КРУГА (контур 1; инвариант Q7). Роль адресуется четырьмя РАЗНЫМИ источниками:
     каталогом `Roles/` (`<Имя>.xml` и `<Имя>/Ext/Rights.xml`), индексом состава
     (`Role.<Имя>` и дочерняя запись `Role.<Имя>.Rights`), перечнем `configurations.roles[]`
     и строками таблицы `roles`. Агрегатный COUNT индекса сверяется с построчным обходом
     (приём V48), множества имён сравниваются попарно во все четыре стороны. Сравнение
     одного множества с самим собой инвариант не сторожит — поэтому каждый источник
     читается отдельно.
  2. СТРОКА РОЛИ ↔ РАЗБОР (контур 2). Каждая колонка строки `roles` обязана совпадать с
     кругом, разобранным ТЕМ ЖЕ модулем (`collect_roles`), что и загрузка: иначе проверка
     проверяла бы себя, а не то, донёс ли писатель строку.
  3. ДЕСКРИПТОР ФАЙЛА ↔ ФАЙЛ И ИНДЕКС (контур 3). `role_sources` обязана называть
     фактический размер файла и путь `<Имя>/Ext/Rights.xml`; запись индекса содержимого
     подтверждается `object_id = '<uuid роли>.0'` (замер 2.2) — иначе «подтверждается
     индексом» осталось бы словом.
  4. ПРАВО ↔ ФАЙЛ (контур 4). Множество пар (цель, право) строки роли равно множеству пар
     её файла, дубликатов нет; колонки состояний совпадают с разбором. Дополнительно —
     НЕЗАВИСИМЫЙ подсчёт по тексту файла (`<object>`, `<right>`, `<value>`,
     `<restrictionByCondition>`, `<restrictionTemplate>`, `<field>`, трёх флагов): CHECK
     сторожит противоречие внутри строки, а потерю строки или прочитанное не то значение —
     только сравнение с файлом.
  5. РАЗРЕШИМОСТЬ ЦЕЛЕЙ (контур 5; замер 2.6). Две меры различаются и называются обе: число
     ВХОЖДЕНИЙ целей, разрешённых только префиксом имени (план: 0/353/1053/3666), и число
     СТРОК ПРАВ таких целей (факт: 0/541/1527/4337). Различие объясняется тем, что у одной
     цели до 27 прав (замер 2.4); проверка выводит вторую меру из первой — суммой прав по
     целям, — и требует равенства с числом строк БД. Неразрешимых целей в корпусе нет;
     неразрешимый остаток — стандартные реквизиты (позиция O4), он называется состоянием
     строки, а не нулём ссылки.
  6. ДЕДУПЛИКАЦИЯ ШАБЛОНОВ ОГРАНИЧЕНИЙ (контур 6; замер 2.7, позиция O6). Отображение
     «имя → текст» не инъективно в обе стороны, поэтому ключ — пара (имя, отпечаток). Корпус
     даёт 18 строк при 10 различных именах и 9 различных текстах: строки 1/0/8/9 по
     выгрузкам. Сверяются и пересчёты: `digest` = `condition_digest(condition_text)`,
     `name_signature` = `template_signature(name)`, длина = длине текста, перечень носителей
     = носителям разбора и ⊆ перечню заголовка, а каждое имя из
     `role_rights.restriction_template_names` разрешается в строку шаблона той же
     конфигурации.
  7. СОСТОЯНИЯ И ФЛАГИ (контур 7). Пустое содержимое прав (`empty_content` — BGU2 2, BP3 9)
     обязано называться состоянием, а не отсутствием строки (2.8); счётчики такой роли
     нулевые, строк прав у неё нет. Словари состояний (`unknown_name`, `unknown_form`,
     `unresolved`) пустуют — и это проверяется, а не предполагается. Значения трёх флагов
     сравниваются с файлом: раздел 2.5 плана ошибался (см. ниже), факт — текст выгрузки.
  8. ВИТРИНЫ, КЛЮЧ, ОТКАЗ ЦЕПИ (контур 8). Витрины называются реестром `current_view()`; на
     ключ цепочки приходится ровно одна текущая строка; `v_current_role_rights` читается
     связкой с `v_current_roles` (своей цепи у `role_rights` нет — Q2, вариант A), а
     `current_view("role_rights")` обязан отказать. Имя роли, общее для двух конфигураций,
     остаётся в витрине двумя строками — факт, ради которого в ключ входит
     `configuration_uuid` (271 такое имя).
  9. ГРАНИЦА R5, СИРОТЫ, НЕПРИКОСНОВЕННОСТЬ (контур 9). Строки обязаны быть свежее файлов
     (иначе отдельный SKIP с причиной); прав, висящих не на CURRENT-ревизии роли, нет; чужие
     слои за прогон не меняются — проверка только читает.
 10. ИТОГ (контур 10). Суммы по сравненным конфигурациям равны числам плана; корпусные числа
     сравниваются только при полном круге из четырёх выгрузок. Одиночный прогон называет,
     чего он не сравнивает.

Расхождение с текстом плана, названное прогоном П6 (30.10.2026): раздел 2.5 утверждал, что в
MinCfg и KomMag «все три флага true». Файлы выгрузки дают другое:
`independentRightsOfChildObjects` = false у обеих ролей MinCfg и у одной из четырёх в KomMag;
в BP3 `setForAttributesByDefault` = false у пяти ролей. Числа плана исправлены по факту
файлов, а не сглажены проверкой — иначе проверка подтверждала бы неверное число.

Запуск:
    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\1C_LLM\ckb
    python tools/check_v49_roles.py [MinCfg|KomMag|BGU2|BP3|all]
По умолчанию — `all`: все строки заголовков, для которых находится каталог выгрузки. Код
возврата 0 — расхождений нет. Пропуск контура называется причиной (нет строки заголовка, нет
выгрузки, строк узла не загружалось, выгрузка новее записей): ноль проверок не читается как
«всё хорошо».
"""

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:  # кириллица в консоли Windows (cp1251) — как в остальных валидаторах
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from configuration_load_contract import ROLE_TABLES, ROLE_TABLES_BY_KIND  # noqa: E402
from configuration_module_slots import resolve_dump_dir  # noqa: E402
from configuration_roles import (  # noqa: E402
    CONDITION_NO_CALL, CONDITION_WITH_CALL, DECLARATION_FILE_AND_INDEX, DIR_NAME,
    FLAG_ELEMENT_NAMES, INDEX_NAME_SEPARATOR, INDEX_OBJECT_TYPE, INDEX_RIGHTS_CHILD_TYPE,
    KNOWN_RIGHT_NAME_COUNT, RIGHTS_EXT_DIR, RIGHTS_FILE_NAME, TARGET_PREFIX_ONLY,
    collect_roles, condition_digest, file_size, index_row_key, iter_role_files,
    kind_index_rows, read_text_file, rights_index_rows, template_signature,
)
from configuration_roles_loader import read_index_records  # noqa: E402
from current_revision import current_view  # noqa: E402
from external_db import transaction  # noqa: E402

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_SCOPE = "all"
MAX_NAMES = 10          # сколько расхождений называется именами (дальше — только число)

# ── ожидания проверки (числа плана docs/CONFIGURATION_ROLES_PLAN.md) ──────────────────
# Разделы 2.1–2.8 и 7, снятые перед написанием проверки зондом `_v49_p6_counts_probe.py`
# (по живой базе) и переснятые по файлам выгрузки независимым подсчётом контура 4. Ключ —
# каталог выгрузки, а не имя строки заголовка.
#   meta_files / rights_files — файлы каталога `Roles/` (метаданные и `Ext/Rights.xml`);
#   index_roles / index_rights — записи индекса состава `Role.<Имя>` и `Role.<Имя>.Rights`;
#   header / role_rows / source_rows / rights_rows — перечень заголовка и строки таблиц;
#   tag_* — независимый подсчёт по ТЕКСТУ файла прав (см. контур 4): `<object>`, `<right>`,
#            `<value>true|false</value>`, `<restrictionByCondition>`,
#            `<restrictionTemplate>`, `<field>`;
#   targets / targets_distinct / right_names_distinct — меры разбора (планы 2.1, 2.4);
#   resolve_* — разрешение цели индексом (план 2.6, МЕРЯЕТСЯ ПО ВХОЖДЕНИЯМ ЦЕЛЕЙ),
#   prefix_rights_rows — то же состояние, но посчитанное по СТРОКАМ ПРАВ (одна цель даёт
#            до 27 прав, замер 2.4): две меры различаются, и проверка выводит вторую из
#            первой суммой прав по целям;
#   cond_call / cond_no_call — состояния условия права (план 2.7: 4 744 = 4 735 + 9 в BGU2,
#            4 170 = 4 152 + 18 в BP3); пустой `<condition/>` KomMag не даёт ни того, ни
#            другого — он называется отдельной строкой, а не нулём;
#   tpl_rows / tpl_names / tpl_digests — строки шаблонов, различных имён и различных
#            текстов (позиция O6: 18 строк при 10 именах и 9 текстах по корпусу);
#   flag_*_true — значения трёх флагов содержимого (план 2.5, исправленный прогоном П6);
#   observations / index_only / file_only / uuid_mismatch / name_file_mismatch — состояния
#            круга: в четырёх выгрузках круг замкнут (замер 2.2), и нули здесь — проверяемое
#            утверждение, а не предположение.
PLAN_EXPECTATIONS = {
    "MinCfg": {
        "meta_files": 2, "rights_files": 2, "index_roles": 2, "index_rights": 2,
        "header": 2, "role_rows": 2, "source_rows": 2, "rights_rows": 362,
        "tag_objects": 67, "tag_rights": 362, "tag_value_true": 0,
        "tag_value_false": 362, "tag_rbc": 0, "tag_rtpl": 1, "tag_field": 0,
        "targets": 67, "targets_distinct": 61, "right_names_distinct": 57,
        "resolve_exact": 67, "resolve_prefix": 0, "resolve_unresolved": 0,
        "prefix_rights_rows": 0,
        "empty_content": 0, "with_rights": 2,
        "cond_call": 0, "cond_no_call": 0, "cond_empty": 0, "field_rows": 0,
        "tpl_rows": 1, "tpl_names": 1, "tpl_digests": 1, "tpl_occurrences": 1,
        "flag_snf_true": 2, "flag_sfa_true": 2, "flag_ind_true": 0,
        "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "name_file_mismatch": 0,
    },
    "KomMag": {
        "meta_files": 4, "rights_files": 4, "index_roles": 4, "index_rights": 4,
        "header": 4, "role_rows": 4, "source_rows": 4, "rights_rows": 2899,
        "tag_objects": 1126, "tag_rights": 2899, "tag_value_true": 1,
        "tag_value_false": 2898, "tag_rbc": 1, "tag_rtpl": 0, "tag_field": 1,
        "targets": 1126, "targets_distinct": 902, "right_names_distinct": 44,
        "resolve_exact": 773, "resolve_prefix": 353, "resolve_unresolved": 0,
        "prefix_rights_rows": 541,
        "empty_content": 0, "with_rights": 4,
        "cond_call": 0, "cond_no_call": 0, "cond_empty": 1, "field_rows": 1,
        "tpl_rows": 0, "tpl_names": 0, "tpl_digests": 0, "tpl_occurrences": 0,
        "flag_snf_true": 4, "flag_sfa_true": 4, "flag_ind_true": 3,
        "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "name_file_mismatch": 0,
    },
    "BGU2": {
        "meta_files": 514, "rights_files": 514, "index_roles": 514, "index_rights": 514,
        "header": 514, "role_rows": 514, "source_rows": 514, "rights_rows": 60565,
        "tag_objects": 19246, "tag_rights": 60565, "tag_value_true": 47097,
        "tag_value_false": 13468, "tag_rbc": 4744, "tag_rtpl": 664, "tag_field": 1,
        "targets": 19246, "targets_distinct": 8922, "right_names_distinct": 64,
        "resolve_exact": 18193, "resolve_prefix": 1053, "resolve_unresolved": 0,
        "prefix_rights_rows": 1527,
        "empty_content": 2, "with_rights": 512,
        "cond_call": 4735, "cond_no_call": 9, "cond_empty": 0, "field_rows": 1,
        "tpl_rows": 8, "tpl_names": 8, "tpl_digests": 7, "tpl_occurrences": 664,
        "flag_snf_true": 1, "flag_sfa_true": 513, "flag_ind_true": 2,
        "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "name_file_mismatch": 0,
    },
    "BP3": {
        "meta_files": 682, "rights_files": 682, "index_roles": 682, "index_rights": 682,
        "header": 682, "role_rows": 682, "source_rows": 682, "rights_rows": 76332,
        "tag_objects": 32283, "tag_rights": 76332, "tag_value_true": 51084,
        "tag_value_false": 25248, "tag_rbc": 4170, "tag_rtpl": 721, "tag_field": 1,
        "targets": 32283, "targets_distinct": 18675, "right_names_distinct": 65,
        "resolve_exact": 28617, "resolve_prefix": 3666, "resolve_unresolved": 0,
        "prefix_rights_rows": 4337,
        "empty_content": 9, "with_rights": 673,
        "cond_call": 4152, "cond_no_call": 18, "cond_empty": 0, "field_rows": 1,
        "tpl_rows": 9, "tpl_names": 9, "tpl_digests": 8, "tpl_occurrences": 721,
        "flag_snf_true": 1, "flag_sfa_true": 677, "flag_ind_true": 1,
        "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "name_file_mismatch": 0,
    },
}

# Корпусные числа (сверяются только при полном круге из четырёх выгрузок): разделы 2.1, 2.4,
# 2.7 и 7 плана. `right_names_union` — закрытый словарь имён права по объединению выгрузок
# (69, замер 2.4); `tpl_*` — 18 строк при 10 именах и 9 текстах (позиция O6);
# `shared_names` — имён ролей, общих для двух и более конфигураций (271): именно ради них в
# ключ цепочки входит `configuration_uuid`.
CORPUS_EXPECTATIONS = {
    "role_rows": 1202, "source_rows": 1202, "rights_rows": 140158,
    "tag_objects": 52722, "tag_rights": 140158,
    "tpl_rows": 18, "tpl_names": 10, "tpl_digests": 9,
    "prefix_rights_rows": 6405, "cond_text_rows": 8914,
    "granted": 98182, "denied": 41976,
    "empty_content": 11, "right_names_union": 69,
    "comments": 41, "empty_synonym": 1, "shared_names": 271,
}

# Живые определения схемы (проверка читает pg_indexes/pg_constraint, а не файл DDL — его
# сверяет `_cmp_ddl.py`). Ключ прав начинается с `role_id`: своей цепи ревизий у таблицы
# нет (Q2, вариант A), текущность права выводится из текущности строки роли.
KEY_DEFINITIONS = [
    ("roles_configuration_object_revision_key",
     "(configuration_uuid, object_name, revision_no)"),
    ("role_sources_configuration_object_revision_key",
     "(configuration_uuid, object_name, revision_no)"),
    ("role_restriction_templates_config_name_digest_revision_key",
     "(configuration_uuid, name, digest, revision_no)"),
    ("role_rights_role_target_right_key",
     "(role_id, target_full_name, right_name)"),
]
RIGHTS_INDEXES = ("idx_role_rights_target_full_name", "idx_role_rights_right_name",
                  "idx_role_rights_target_object_uuid")

PASSED, FAILED, SKIPPED, INFO = [], [], [], []


def check(name, ok, detail=""):
    (PASSED if ok else FAILED).append(name)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f"\n      {detail}"))


def skip(name, reason):
    SKIPPED.append(name)
    print(f"SKIP {name}\n      {reason}")


def info(text):
    INFO.append(text)
    print("INFO " + text)


def section(title):
    print("\n" + title)
    print("-" * len(title))


def q(cur, sql, params=None):
    cur.execute(sql, params or ())
    if not cur.description:
        return []
    columns = [d[0] for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def one(cur, sql, params=None):
    rows = q(cur, sql, params)
    return rows[0] if rows else {}


def names(sample):
    """Сколько расхождений называется именами — дальше только число."""
    shown = list(sample)[:MAX_NAMES]
    tail = "" if len(sample) <= MAX_NAMES else f" … ещё {len(sample) - MAX_NAMES}"
    return ", ".join(str(item) for item in shown) + tail


def _brief(value):
    text = repr(value)
    return text if len(text) <= 160 else text[:160] + "…"


# ── имена витрин и таблицы берутся реестром, а не литералом (приём V48) ─────────────
ROLE_VIEW = current_view("roles")
SOURCE_VIEW = current_view("role_sources")
TEMPLATE_VIEW = current_view("role_restriction_templates")
RIGHTS_VIEW = "v_current_role_rights"   # связка с ROLE_VIEW, своей цепи у таблицы нет

# Колонки витрин перечислены явно: проверка обязана назвать колонку, которую писатель не
# донёс, а не молча получить пустой словарь.
ROLE_FIELDS = ("id", "configuration_uuid", "object_uuid", "object_name", "full_name",
               "comment", "synonym", "set_for_new_objects",
               "set_for_attributes_by_default", "independent_rights_of_child_objects",
               "content_state", "source_path", "targets_count", "rights_count",
               "conditions_count", "templates_count", "revision_no", "changed_at",
               "changed_by", "is_committed")
ROLE_COMPARE_FIELDS = ("object_uuid", "object_name", "full_name", "comment", "synonym",
                       "set_for_new_objects", "set_for_attributes_by_default",
                       "independent_rights_of_child_objects", "content_state",
                       "source_path", "targets_count", "rights_count",
                       "conditions_count", "templates_count")
RIGHT_FIELDS = ("id", "role_id", "configuration_uuid", "target_kind", "target_full_name",
                "target_object_id", "target_object_uuid", "target_resolve_state",
                "target_unresolved_path", "right_name", "right_name_state",
                "right_value_state", "restriction_field_name", "condition_text",
                "condition_state", "restriction_template_names", "target_ordinal",
                "right_ordinal")
RIGHT_COMPARE_FIELDS = ("target_kind", "target_full_name", "target_object_id",
                        "target_object_uuid", "target_resolve_state",
                        "target_unresolved_path", "right_name", "right_name_state",
                        "right_value_state", "restriction_field_name", "condition_text",
                        "condition_state", "restriction_template_names", "target_ordinal",
                        "right_ordinal")
SOURCE_FIELDS = ("id", "configuration_uuid", "object_name", "object_uuid", "source_path",
                 "file_size", "declaration_state", "revision_no")
TEMPLATE_FIELDS = ("id", "configuration_uuid", "name", "name_signature", "digest",
                   "condition_text", "condition_length", "holder_role_names",
                   "holders_count", "revision_no")


def _select(view, fields, alias="x"):
    return ", ".join(f"{alias}.{field}" for field in fields)


def read_role_rows(cur, cfg_uuid):
    return q(cur, f"SELECT {_select(ROLE_VIEW, ROLE_FIELDS, 'r')} FROM {ROLE_VIEW} r "
                  f"WHERE r.configuration_uuid = %(uuid)s::uuid "
                  f"ORDER BY r.object_name, r.id", {"uuid": str(cfg_uuid)})


def read_source_rows(cur, cfg_uuid):
    return q(cur, f"SELECT {_select(SOURCE_VIEW, SOURCE_FIELDS, 's')} FROM {SOURCE_VIEW} s "
                  f"WHERE s.configuration_uuid = %(uuid)s::uuid "
                  f"ORDER BY s.object_name, s.id", {"uuid": str(cfg_uuid)})


def read_rights_rows(cur, cfg_uuid):
    return q(cur, f"SELECT {_select(RIGHTS_VIEW, RIGHT_FIELDS, 'rr')} FROM {RIGHTS_VIEW} rr "
                  f"WHERE rr.configuration_uuid = %(uuid)s::uuid "
                  f"ORDER BY rr.role_id, rr.target_ordinal, rr.right_ordinal, rr.id",
             {"uuid": str(cfg_uuid)})


def read_template_rows(cur, cfg_uuid):
    return q(cur, f"SELECT {_select(TEMPLATE_VIEW, TEMPLATE_FIELDS, 't')} "
                  f"FROM {TEMPLATE_VIEW} t "
                  f"WHERE t.configuration_uuid = %(uuid)s::uuid "
                  f"ORDER BY t.name, t.digest, t.id", {"uuid": str(cfg_uuid)})


def read_header_role_list(cur, configuration_uuid):
    """Перечень имён ролей из строки заголовка (колонка V43, а не таблица узла).

    Иначе сравнение множеств сравнивало бы один набор с самим собой: инвариант Q7
    существует ровно потому, что источник здесь другой.
    """
    row = one(cur, "SELECT coalesce(roles, '{}'::text[]) AS names FROM configurations "
                   "WHERE uuid = %(uuid)s::uuid", {"uuid": str(configuration_uuid)})
    return [str(item) for item in (row.get("names") or [])]


# ── круг на диске: файлы, разбор тем же модулем, независимый подсчёт тегов ────────────
def short_index_name(object_name, strip_content_suffix=False):
    """Короткое имя роли по ключу индекса состава (`Role.<Имя>` / `Role.<Имя>.Rights`).

    Суффикс `.Rights` снимается только у записей содержимого: роль с именем `Rights`
    существует, и снятие суффикса у её собственной записи дало бы пустое имя.
    """
    prefix = INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR
    key = str(object_name or "")
    if not key.startswith(prefix):
        return ""
    tail = key[len(prefix):]
    if strip_content_suffix:
        suffix = INDEX_NAME_SEPARATOR + INDEX_RIGHTS_CHILD_TYPE
        if tail.endswith(suffix):
            tail = tail[:-len(suffix)]
    return tail


def parse_circle(dump_dir, index_rows):
    """Разобрать круг ТЕМ ЖЕ модулем, что и загрузка.

    Сравнение строки с файлом идёт по разбору, а не по второй реализации чтения XML: иначе
    проверка проверяла бы саму себя, а не то, донёс ли писатель строку.
    """
    return collect_roles(Path(dump_dir), index_rows)


# Независимая мера круга — регулярками по тексту файла прав, без знания о состояниях.
# Сравнение строки БД с разбором проверяет ПИСАТЕЛЯ; этот подсчёт проверяет САМ РАЗБОР:
# совпадение двух реализаций и есть доказательство, что в строку легло то, что в файле, а
# не то, что ожидалось. Закрытые элементы (`<condition/>`) считаются отдельно — пустое
# условие KomMag (замер П2) иначе читалось бы как «условия нет вообще».
RE_ELEMENT = {
    "tag_objects": re.compile(r"<object[ />]"),
    "tag_rights": re.compile(r"<right[ />]"),
    "tag_rbc": re.compile(r"<restrictionByCondition[ />]"),
    "tag_rtpl": re.compile(r"<restrictionTemplate[ />]"),
    "tag_field": re.compile(r"<field[ />]"),
}
RE_VALUE_TRUE = re.compile(r"<value>\s*true\s*</value>")
RE_VALUE_FALSE = re.compile(r"<value>\s*false\s*</value>")
RE_VALUE_EMPTY = re.compile(r"<value\s*/>")
RE_CONDITION_EMPTY = re.compile(r"<condition\s*/>")
RE_FLAG_TRUE = {element: re.compile(r"<%s>\s*true\s*</%s>" % (element, element))
                for element in FLAG_ELEMENT_NAMES}
RE_FLAG_FALSE = {element: re.compile(r"<%s>\s*false\s*</%s>" % (element, element))
                 for element in FLAG_ELEMENT_NAMES}
FLAG_COLUMN_BY_ELEMENT_LOCAL = {
    "setForNewObjects": "flag_snf_true",
    "setForAttributesByDefault": "flag_sfa_true",
    "independentRightsOfChildObjects": "flag_ind_true",
}


def raw_measures(dump_dir):
    """Подсчёт по тексту файлов прав: итоги по конфигурации и по каждой роли отдельно."""
    by_name, _observations = iter_role_files(Path(dump_dir))
    totals = Counter()
    per_role = {}
    unreadable = []
    for role_name, entry in sorted(by_name.items()):
        rights = entry.get("rights")
        if not rights:
            continue
        text, reason = read_text_file(rights["path"])
        if text is None:
            unreadable.append((role_name, reason))
            continue
        counts = {key: len(pattern.findall(text)) for key, pattern in RE_ELEMENT.items()}
        counts["tag_value_true"] = len(RE_VALUE_TRUE.findall(text))
        counts["tag_value_false"] = len(RE_VALUE_FALSE.findall(text))
        counts["tag_value_empty"] = len(RE_VALUE_EMPTY.findall(text))
        counts["tag_condition_empty"] = len(RE_CONDITION_EMPTY.findall(text))
        for element, column in FLAG_COLUMN_BY_ELEMENT_LOCAL.items():
            counts[column] = len(RE_FLAG_TRUE[element].findall(text))
            counts[column + "_false"] = len(RE_FLAG_FALSE[element].findall(text))
        per_role[role_name] = counts
        for key, value in counts.items():
            totals[key] += value
    totals["unreadable_files"] = len(unreadable)
    totals["measured_files"] = len(per_role)
    return totals, per_role, unreadable


# ── контур 1: граница круга (инвариант Q7) ───────────────────────────────────────────
def check_circle(cur, header, dump_dir, index_info, expect, tag):
    """Каталог ↔ индекс состава ↔ перечень заголовка ↔ строки таблиц (четыре источника)."""
    cfg_uuid = str(header["uuid"])
    role_rows = read_role_rows(cur, cfg_uuid)
    source_rows = read_source_rows(cur, cfg_uuid)
    rights_rows = read_rights_rows(cur, cfg_uuid)
    template_rows = read_template_rows(cur, cfg_uuid)
    header_names = read_header_role_list(cur, cfg_uuid)

    aggregate = int(one(cur, "SELECT count(*) AS c FROM configuration_objects "
                             "WHERE configuration_id = %s AND object_type = %s "
                             "AND (child_type IS NULL OR child_type = '')",
                        (int(header["id"]), INDEX_OBJECT_TYPE)).get("c") or 0)
    aggregate_rights = int(one(cur, "SELECT count(*) AS c FROM configuration_objects "
                                   "WHERE configuration_id = %s AND object_type = %s "
                                   "AND child_type = %s",
                               (int(header["id"]), INDEX_OBJECT_TYPE,
                                INDEX_RIGHTS_CHILD_TYPE)).get("c") or 0)
    index_role_records = kind_index_rows(index_info["rows"])
    index_rights_records = rights_index_rows(index_info["rows"])
    index_role_names = {short_index_name(index_row_key(row)) for row in index_role_records}
    index_role_names.discard("")
    index_rights_names = {short_index_name(index_row_key(row), strip_content_suffix=True)
                          for row in index_rights_records}
    index_rights_names.discard("")

    # `iter_role_files` сам спускается в каталог вида (root → `Roles/`), поэтому ему
    # отдаётся корень выгрузки, а не каталог вида.
    files_by_name, observations = iter_role_files(Path(dump_dir))
    meta_files = {name for name, entry in files_by_name.items() if entry.get("metadata")}
    rights_files = {name for name, entry in files_by_name.items() if entry.get("rights")}
    table_names = {row["object_name"] for row in role_rows}
    source_names = {row["object_name"] for row in source_rows}

    check(f"{tag}: записи индекса состава вида агрегатом и построчным обходом дают одно "
          f"число ({aggregate})", aggregate == len(index_role_records),
          f"агрегат: {aggregate}, обход: {len(index_role_records)}")
    check(f"{tag}: записей `Role.<Имя>` в индексе состава ровно {expect['index_roles']}",
          len(index_role_records) == expect["index_roles"],
          f"факт: {len(index_role_records)}")
    check(f"{tag}: записей `Role.<Имя>.Rights` агрегатом и обходом ровно "
          f"{expect['index_rights']}",
          aggregate_rights == len(index_rights_records) == expect["index_rights"],
          f"агрегат: {aggregate_rights}, обход: {len(index_rights_records)}")
    check(f"{tag}: файлов метаданных в каталоге `Roles/` ровно {expect['meta_files']}, файлов "
          f"`Ext/Rights.xml` ровно {expect['rights_files']}, прочего в круге нет",
          len(meta_files) == expect["meta_files"]
          and len(rights_files) == expect["rights_files"] and not observations,
          f"метаданных: {len(meta_files)}, прав: {len(rights_files)}, "
          f"наблюдений: {len(observations)} — {_brief(list(observations)[:MAX_NAMES])}")
    check(f"{tag}: имён файла без записи индекса и записи без файла нет (замер 2.2)",
          meta_files == index_role_names == rights_files == index_rights_names,
          f"файлы^индекс: {names(meta_files ^ index_role_names)}; "
          f"прав^индекс-прав: {names(rights_files ^ index_rights_names)}")
    check(f"{tag}: множество имён таблицы `roles` равно перечню заголовка, индексу состава и "
          f"файлам каталога (инвариант Q7)",
          table_names == set(header_names) == index_role_names == meta_files,
          f"таблица: {len(table_names)}, заголовок: {len(header_names)}, "
          f"индекс: {len(index_role_names)}, файлы: {len(meta_files)}; расхождения: "
          f"таблица^заголовок={names(table_names ^ set(header_names))}; "
          f"таблица^индекс={names(table_names ^ index_role_names)}")
    check(f"{tag}: строк роли ровно {expect['role_rows']}, дескрипторов файла "
          f"{expect['source_rows']}, имён в перечне заголовка {expect['header']}",
          len(role_rows) == expect["role_rows"] and len(source_rows) == expect["source_rows"]
          and len(header_names) == expect["header"],
          f"ролей: {len(role_rows)}, дескрипторов: {len(source_rows)}, "
          f"перечень: {len(header_names)}")
    check(f"{tag}: дескриптор файла существует ровно для той же роли, что и строка роли "
          f"(Q6: круг по каталогу и круг по индексу — один круг)",
          source_names == table_names,
          f"расхождения: {names(source_names ^ table_names)}")
    return {"role_rows": role_rows, "source_rows": source_rows,
            "rights_rows": rights_rows, "template_rows": template_rows,
            "header_names": header_names, "files_by_name": files_by_name,
            "observations": observations, "index_role_records": index_role_records,
            "index_rights_records": index_rights_records,
            "index_by_key": {index_row_key(row): row for row in index_info["rows"]}}


# ── контур 2: строка роли ↔ разбор круга ─────────────────────────────────────────────
def check_role_rows(parsed, db_rows, expect, tag):
    """Каждая колонка строки `roles` обязана совпадать с разбором того же круга."""
    by_name = {row["object_name"]: row for row in db_rows}
    parsed_rows = {row["object_name"]: row for row in parsed["role_rows"]}

    check(f"{tag}: отказов разбора файлов круга нет ({len(parsed_rows)} ролей разобраны)",
          not parsed["files_failed"] and len(parsed_rows) == expect["role_rows"],
          _brief(parsed["files_failed"][:MAX_NAMES]))
    missing = sorted(set(parsed_rows) - set(by_name))
    extra = sorted(set(by_name) - set(parsed_rows))
    check(f"{tag}: файла без строки и строки без файла нет", not missing and not extra,
          f"файл без строки: {names(missing)}; строка без файла: {names(extra)}")

    diffs = {}
    for name, parsed_row in sorted(parsed_rows.items()):
        row = by_name.get(name)
        if row is None:
            continue
        for field in ROLE_COMPARE_FIELDS:
            if row.get(field) != parsed_row.get(field):
                diffs.setdefault(field, []).append(
                    (name, _brief(row.get(field)), _brief(parsed_row.get(field))))
    check(f"{tag}: все колонки строк `roles` совпадают с разбором круга (писатель не терял "
          f"полей)", not diffs,
          "; ".join(f"{field}: {len(items)} — {_brief(items[0])}"
                    for field, items in sorted(diffs.items())) or "")

    states = parsed["counts_by_content_state"]
    check(f"{tag}: состояний содержимого ровно `empty_content` {expect['empty_content']}, "
          f"`with_rights` {expect['with_rights']} (пустые права — состояние, а не отсутствие "
          f"строки, 2.8)",
          states.get("empty_content", -1) == expect["empty_content"]
          and states.get("with_rights", -1) == expect["with_rights"],
          f"разбор: {_brief(dict(states))}")
    db_states = Counter(row["content_state"] for row in db_rows)
    check(f"{tag}: состояния содержимого в таблице равны состояниям разбора",
          dict(db_states) == {state: count for state, count in states.items() if count},
          f"таблица: {_brief(dict(db_states))}; разбор: {_brief(dict(states))}")

    empty_named = sorted(name for name, row in by_name.items()
                         if row["content_state"] == "empty_content")
    check(f"{tag}: пустых ролей в таблице {expect['empty_content']}, все они названы "
          f"состоянием, а не отсутствием строки", len(empty_named) == expect["empty_content"],
          names(empty_named))
    broken = [name for name, row in by_name.items()
              if row["content_state"] == "empty_content"
              and any(row[field] for field in ("targets_count", "rights_count",
                                               "conditions_count", "templates_count"))]
    check(f"{tag}: у роли с пустым содержимым все счётчики нулевые", not broken, names(broken))

    observations = parsed["observations"]
    check(f"{tag}: наблюдений о форме круга нет (ожидалось {expect['observations']})",
          len(observations) == expect["observations"], _brief(observations[:MAX_NAMES]))
    for key in ("index_only", "file_only", "uuid_mismatch", "name_file_mismatch"):
        check(f"{tag}: состояний `{key}` круга ровно {expect[key]}",
              len(parsed[key]) == expect[key], _brief(parsed[key][:MAX_NAMES]))
    return by_name, parsed_rows


# ── контур 3: дескриптор файла ↔ файл на диске ↔ запись индекса содержимого ──────────
def check_sources(parsed, circle, role_by_name, expect, dump_dir, tag):
    """`role_sources` обязана называть фактический файл и подтверждаться индексом (Q6)."""
    db_rows = circle["source_rows"]
    parsed_rows = {row["object_name"]: row for row in parsed["source_rows"]}
    check(f"{tag}: строк-дескрипторов `role_sources` ровно {expect['source_rows']}",
          len(db_rows) == len(parsed_rows) == expect["source_rows"],
          f"таблица: {len(db_rows)}, разбор: {len(parsed_rows)}")

    db_by_name = {row["object_name"]: row for row in db_rows}
    diffs = {}
    for name, parsed_row in sorted(parsed_rows.items()):
        row = db_by_name.get(name)
        if row is None:
            continue
        for field in ("object_uuid", "source_path", "file_size", "declaration_state"):
            if row.get(field) != parsed_row.get(field):
                diffs.setdefault(field, []).append(
                    (name, _brief(row.get(field)), _brief(parsed_row.get(field))))
    check(f"{tag}: колонки дескриптора совпадают с разбором круга", not diffs,
          "; ".join(f"{field}: {len(items)} — {_brief(items[0])}"
                    for field, items in sorted(diffs.items())) or "")

    # Независимая часть: путь выводится из имени роли, а размер берётся с диска — ни то, ни
    # другое не берётся у разбора и не берётся из строки.
    wrong_path, wrong_size, missing_file = [], [], []
    for row in db_rows:
        expected = f"{DIR_NAME}/{row['object_name']}/{RIGHTS_EXT_DIR}/{RIGHTS_FILE_NAME}"
        if row["source_path"] != expected:
            wrong_path.append((row["object_name"], row["source_path"]))
            continue
        path = Path(dump_dir) / DIR_NAME / row["object_name"] / RIGHTS_EXT_DIR \
            / RIGHTS_FILE_NAME
        actual = file_size(path)
        if actual is None:
            missing_file.append(row["object_name"])
        elif actual != row["file_size"]:
            wrong_size.append((row["object_name"], row["file_size"], actual))
    check(f"{tag}: путь дескриптора выводится из имени роли (`<Имя>/Ext/Rights.xml`)",
          not wrong_path, _brief(wrong_path[:MAX_NAMES]))
    check(f"{tag}: `file_size` равен фактическому размеру файла на диске", not wrong_size,
          _brief(wrong_size[:MAX_NAMES]))
    check(f"{tag}: файла по названному пути нет только там, где состояние это называет",
          not missing_file, names(missing_file))

    states = Counter(row["declaration_state"] for row in db_rows)
    check(f"{tag}: состояний дескриптора ровно `file_and_index` {expect['source_rows']} "
          f"(состояний `indexed_no_file`/`file_not_in_index` корпус не даёт — 0)",
          states.get(DECLARATION_FILE_AND_INDEX, 0) == expect["source_rows"]
          and parsed["counts_by_declaration_state"].get(DECLARATION_FILE_AND_INDEX, 0)
          == expect["source_rows"],
          f"таблица: {_brief(dict(states))}; разбор: "
          f"{_brief(dict(parsed['counts_by_declaration_state']))}")

    # Подтверждение записью индекса: `Role.<Имя>.Rights` существует и держит
    # `object_id = '<uuid роли>.0'` (замер 2.2); uuid самой роли берётся записью
    # `Role.<Имя>` — иначе «подтверждается индексом» оставалось словом.
    index_by_key = circle["index_by_key"]
    no_record, bad_object_id, bad_uuid = [], [], []
    for row in db_rows:
        name = row["object_name"]
        content = index_by_key.get(f"{INDEX_OBJECT_TYPE}.{name}.{INDEX_RIGHTS_CHILD_TYPE}")
        if content is None:
            no_record.append(name)
            continue
        role_record = index_by_key.get(f"{INDEX_OBJECT_TYPE}.{name}")
        role_uuid = (role_record or {}).get("uuid")
        expected_id = f"{role_uuid}.0" if role_uuid else None
        if str(content.get("object_id") or "") != str(expected_id or ""):
            bad_object_id.append((name, content.get("object_id"), expected_id))
        owner = role_by_name.get(name)
        if owner is not None and str(owner["object_uuid"]).lower() != str(
                row["object_uuid"]).lower():
            bad_uuid.append(name)
        if role_uuid and str(row["object_uuid"]).lower() != str(role_uuid).lower():
            bad_uuid.append(name)
    check(f"{tag}: запись `Role.<Имя>.Rights` есть для каждого дескриптора", not no_record,
          names(no_record))
    check(f"{tag}: `object_id` записи содержимого равен `<uuid роли>.0` (замер 2.2)",
          not bad_object_id, _brief(bad_object_id[:MAX_NAMES]))
    check(f"{tag}: uuid дескриптора и строки роли равен uuid записи индекса `Role.<Имя>`",
          not bad_uuid, names(bad_uuid))


# ── контур 4: права ↔ разбор и ↔ независимому подсчёту тегов по файлу ────────────────
def check_rights(parsed, circle, role_by_name, raw_totals, raw_per_role, expect, tag):
    """Строки `role_rights` против разбора круга и против текста файлов прав.

    Разбор проверяет писателя, подсчёт регуляркой по файлу проверяет разбор: три независимые
    меры (таблица, `collect_roles`, теги файла) обязаны сойтись числом и множеством пар
    (цель, право). Равенство только двух из них не замечало бы потерю строки.
    """
    db_rows = circle["rights_rows"]
    parsed_rights = parsed["right_rows"]

    check(f"{tag}: строк прав ровно {expect['rights_rows']} — таблица, разбор и подсчёт "
          f"тегов `<right>` по файлам дают одно число",
          len(db_rows) == expect["rights_rows"]
          and len(parsed_rights) == expect["rights_rows"]
          and raw_totals["tag_rights"] == expect["rights_rows"],
          f"таблица: {len(db_rows)}, разбор: {len(parsed_rights)}, "
          f"тегов в файлах: {raw_totals['tag_rights']}")

    # 4.1 — счётчик строки роли против строк прав и против тега файла (для каждой роли).
    db_per_role = Counter(row["role_id"] for row in db_rows)
    parsed_per_role = Counter(row["role_name"] for row in parsed_rights)
    bad_counts, bad_tag_counts, bad_target_counts = [], [], []
    for name, role in sorted(role_by_name.items()):
        raw = raw_per_role.get(name, {})
        if db_per_role.get(role["id"], 0) != role["rights_count"] or \
                parsed_per_role.get(name, 0) != role["rights_count"]:
            bad_counts.append((name, role["rights_count"], db_per_role.get(role["id"], 0),
                               parsed_per_role.get(name, 0)))
        if raw.get("tag_rights", 0) != role["rights_count"]:
            bad_tag_counts.append((name, role["rights_count"], raw.get("tag_rights", 0)))
        if role["targets_count"] != raw.get("tag_objects", 0):
            bad_target_counts.append((name, role["targets_count"],
                                      raw.get("tag_objects", 0)))
    check(f"{tag}: `rights_count` строки роли равен числу её строк прав и разбору",
          not bad_counts, _brief(bad_counts[:MAX_NAMES]))
    check(f"{tag}: `rights_count` равен числу тегов `<right>` в файле прав роли (разбор не "
          f"теряет и не добавляет прав)", not bad_tag_counts, _brief(bad_tag_counts[:MAX_NAMES]))
    check(f"{tag}: `targets_count` равен числу тегов `<object>` в файле прав роли",
          not bad_target_counts, _brief(bad_target_counts[:MAX_NAMES]))
    empty_without_rights = [name for name, role in role_by_name.items()
                            if role["content_state"] == "empty_content"
                            and db_per_role.get(role["id"], 0)]
    check(f"{tag}: у пустых ролей строк прав нет ни одной (2.8)",
          not empty_without_rights, names(empty_without_rights))

    # 4.2 — множество пар (роль, цель, право) и его уникальность.
    role_name_by_id = {role["id"]: name for name, role in role_by_name.items()}
    db_pairs = Counter((role_name_by_id.get(row["role_id"], f"#{row['role_id']}"),
                        row["target_full_name"], row["right_name"]) for row in db_rows)
    parsed_pairs = Counter((row["role_name"], row["target_full_name"], row["right_name"])
                           for row in parsed_rights)
    duplicated = sorted(key for key, count in db_pairs.items() if count > 1)
    check(f"{tag}: пар (роль, цель, право) в таблице по одной (ключ "
          f"`(role_id, target_full_name, right_name)` работает)", not duplicated,
          _brief(duplicated[:MAX_NAMES]))
    only_db = sorted(set(db_pairs) - set(parsed_pairs))
    only_parsed = sorted(set(parsed_pairs) - set(db_pairs))
    check(f"{tag}: множество пар таблицы равно множеству пар разбора",
          not only_db and not only_parsed,
          f"только таблица: {names(only_db)}; только разбор: {names(only_parsed)}")

    # 4.3 — колонки строки права против разбора (по той же паре).
    parsed_by_key = {(row["role_name"], row["target_full_name"], row["right_name"]): row
                     for row in parsed_rights}
    diffs = {}
    for row in db_rows:
        key = (role_name_by_id.get(row["role_id"], ""), row["target_full_name"],
               row["right_name"])
        parsed_row = parsed_by_key.get(key)
        if parsed_row is None:
            continue
        for field in RIGHT_COMPARE_FIELDS:
            left, right = row.get(field), parsed_row.get(field)
            if field == "target_object_uuid":
                left = str(left).lower() if left is not None else None
                right = str(right).lower() if right is not None else None
            if left != right:
                diffs.setdefault(field, []).append(
                    (key[0], key[1], _brief(left), _brief(right)))
    check(f"{tag}: все колонки строк прав совпадают с разбором круга", not diffs,
          "; ".join(f"{field}: {len(items)} — {_brief(items[0])}"
                    for field, items in sorted(diffs.items())) or "")

    # 4.4 — значение права против текста `<value>` в файле: состояние называется фактом
    # файла, а не выводом «роль может/не может» (позиция O1, закрытая замером П5).
    value_states = Counter(row["right_value_state"] for row in db_rows)
    check(f"{tag}: значений права ровно `granted` {expect['tag_value_true']}, `denied` "
          f"{expect['tag_value_false']} — и столько же тегов `<value>true|false</value>` в "
          f"файлах (позиция O1)",
          value_states.get("granted", 0) == expect["tag_value_true"]
          and value_states.get("denied", 0) == expect["tag_value_false"]
          and raw_totals["tag_value_true"] == expect["tag_value_true"]
          and raw_totals["tag_value_false"] == expect["tag_value_false"],
          f"таблица: {_brief(dict(value_states))}; тегов true: "
          f"{raw_totals['tag_value_true']}, false: {raw_totals['tag_value_false']}")
    check(f"{tag}: пустых `<value/>` и состояний `unknown_form` нет (замер 2.4 — 0)",
          raw_totals["tag_value_empty"] == 0
          and parsed["counts_by_right_value_state"].get("unknown_form", 0) == 0
          and value_states.get("unknown_form", 0) == 0,
          f"пустых тегов: {raw_totals['tag_value_empty']}, состояний: "
          f"{_brief(dict(value_states))}")

    # 4.5 — закрытый словарь имён права (замер 2.4: 69 имён по объединению выгрузок).
    name_states = Counter(row["right_name_state"] for row in db_rows)
    check(f"{tag}: состояний `unknown_name` нет — словарь имён права исчерпан (замер 2.4)",
          name_states.get("unknown_name", 0) == 0
          and parsed["counts_by_right_name_state"].get("unknown_name", 0) == 0
          and not parsed["unknown_right_names"],
          f"таблица: {_brief(dict(name_states))}; неизвестных имён: "
          f"{len(parsed['unknown_right_names'])}")
    distinct_names = len({row["right_name"] for row in db_rows})
    distinct_targets = len({row["target_full_name"] for row in db_rows})
    check(f"{tag}: различных имён права ровно {expect['right_names_distinct']} (замер 2.4)",
          distinct_names == expect["right_names_distinct"], f"факт: {distinct_names}")
    check(f"{tag}: различных целей ровно {expect['targets_distinct']} (замер 2.4)",
          distinct_targets == expect["targets_distinct"], f"факт: {distinct_targets}")
    check(f"{tag}: разбор даёт тех же целей, что таблица "
          f"(разбор: {parsed['targets_distinct']})",
          parsed["targets_distinct"] == distinct_targets,
          f"разбор: {parsed['targets_distinct']}, таблица: {distinct_targets}")

    # 4.6 — порядки соответствуют порядку файла: цель посчитана один раз, дубликатов
    # (роль, ordinal цели, ordinal права) нет.
    bad_ordinals = [row for row in db_rows
                    if int(row["target_ordinal"]) < 0 or int(row["right_ordinal"]) < 0]
    ordinal_keys = Counter((row["role_id"], row["target_ordinal"], row["right_ordinal"])
                           for row in db_rows)
    duplicated_ordinals = sorted(key for key, count in ordinal_keys.items() if count > 1)
    check(f"{tag}: отрицательных порядков нет, пар (роль, ordinal цели, ordinal права) по "
          f"одной", not bad_ordinals and not duplicated_ordinals,
          _brief(duplicated_ordinals[:MAX_NAMES]))
    ordinals_match = []
    for name, role in sorted(role_by_name.items()):
        keys = {(role["id"], ordinal) for ordinal in {
            row["target_ordinal"] for row in db_rows if row["role_id"] == role["id"]}}
        if len(keys) != role["targets_count"]:
            ordinals_match.append((name, role["targets_count"], len(keys)))
    check(f"{tag}: различных `target_ordinal` у роли равно её `targets_count` (цель "
          f"посчитана один раз)", not ordinals_match, _brief(ordinals_match[:MAX_NAMES]))
    return db_rows


# ── контур 5: разрешение цели индексом состава (замер 2.6) ───────────────────────────
def check_targets(parsed, circle, index_by_key, expect, tag):
    """Цель права разрешается индексом той же конфигурации; две меры различаются.

    План 2.6 меряет ВХОЖДЕНИЯ ЦЕЛЕЙ (`<object>`), таблица держит СТРОКИ ПРАВ: одна цель
    даёт до 27 прав (замер 2.4). Проверка считает обе меры и требует, чтобы вторая
    выводилась из первой, — иначе число из плана читалось бы как число строк таблицы.
    """
    db_rows = circle["rights_rows"]

    # 5.1 — состояния по ВХОЖДЕНИЯМ ЦЕЛЕЙ: группа строк с одним (role_id, target_ordinal)
    # — это одна цель файла.
    target_state = {}
    for row in db_rows:
        target_state.setdefault((row["role_id"], row["target_ordinal"]),
                                row["target_resolve_state"])
    by_target = Counter(target_state.values())
    parse_states = parsed["counts_by_target_resolve_state"]
    check(f"{tag}: состояний разрешения целей ровно `exact` {expect['resolve_exact']}, "
          f"`prefix_only` {expect['resolve_prefix']}, `unresolved` "
          f"{expect['resolve_unresolved']} (замер 2.6, по вхождениям целей)",
          by_target.get("exact", 0) == expect["resolve_exact"]
          and by_target.get(TARGET_PREFIX_ONLY, 0) == expect["resolve_prefix"]
          and by_target.get("unresolved", 0) == expect["resolve_unresolved"],
          f"таблица по целям: {_brief(dict(by_target))}")
    check(f"{tag}: разрешение целей разбором равно разрешению, посчитанному по строкам "
          f"таблицы",
          by_target == {state: count for state, count in parse_states.items() if count},
          f"таблица: {_brief(dict(by_target))}; разбор: {_brief(dict(parse_states))}")

    # 5.2 — те же состояния, но посчитанные по СТРОКАМ ПРАВ: вторая мера.
    by_right = Counter(row["target_resolve_state"] for row in db_rows)
    check(f"{tag}: строк прав с состоянием `prefix_only` ровно "
          f"{expect['prefix_rights_rows']} (вторая мера: целей "
          f"{expect['resolve_prefix']}, а их прав {expect['prefix_rights_rows']} — у цели до "
          f"27 прав, замер 2.4)",
          by_right.get(TARGET_PREFIX_ONLY, 0) == expect["prefix_rights_rows"]
          and by_right.get("unresolved", 0) == expect["resolve_unresolved"],
          f"таблица по правам: {_brief(dict(by_right))}")
    info(f"{tag}: две меры разрешения цели различаются осознанно — целей `prefix_only` "
         f"{by_target.get(TARGET_PREFIX_ONLY, 0)}, их прав "
         f"{by_right.get(TARGET_PREFIX_ONLY, 0)}; неразрешимых целей "
         f"{by_target.get('unresolved', 0)}")

    # 5.3 — ссылка цели совпадает с записью индекса той же конфигурации (для `exact` —
    # самой цели, для `prefix_only` — записи префикса, остаток называется колонкой).
    seen_targets = {}
    for row in db_rows:
        seen_targets.setdefault(row["target_full_name"], row)
    bad_reference, bad_prefix, bad_unresolved = [], [], []
    for target_full_name, row in sorted(seen_targets.items()):
        record = index_by_key.get(target_full_name)
        state = row["target_resolve_state"]
        if state == "exact":
            if record is None:
                bad_reference.append((target_full_name, "записи индекса нет"))
                continue
            if str(row["target_object_id"] or "") != str(record.get("object_id") or ""):
                bad_reference.append((target_full_name, "object_id",
                                      row["target_object_id"], record.get("object_id")))
            row_uuid = (str(row["target_object_uuid"]).lower()
                        if row["target_object_uuid"] is not None else None)
            rec_uuid = str(record.get("uuid")).lower() if record.get("uuid") else None
            if row_uuid != rec_uuid:
                bad_reference.append((target_full_name, "uuid", row_uuid, rec_uuid))
            if row["target_unresolved_path"] is not None:
                bad_reference.append((target_full_name, "остаток у точной цели"))
        elif state == TARGET_PREFIX_ONLY:
            if record is not None:
                bad_prefix.append((target_full_name, "цель есть в индексе целиком"))
            if not row["target_unresolved_path"]:
                bad_prefix.append((target_full_name, "остаток не назван"))
            segments = str(target_full_name).split(INDEX_NAME_SEPARATOR)
            prefix_record = None
            for cut in range(len(segments) - 1, 0, -1):
                prefix_record = index_by_key.get(INDEX_NAME_SEPARATOR.join(segments[:cut]))
                if prefix_record is not None:
                    break
            if prefix_record is None:
                bad_prefix.append((target_full_name, "префикс в индексе не найден"))
                continue
            if str(row["target_object_id"] or "") != str(
                    prefix_record.get("object_id") or ""):
                bad_prefix.append((target_full_name, "object_id префикса",
                                   row["target_object_id"], prefix_record.get("object_id")))
        else:
            bad_unresolved.append(target_full_name)
    check(f"{tag}: `target_object_id`/`target_object_uuid` точной цели равны записи индекса "
          f"состава этой же конфигурации", not bad_reference,
          _brief(bad_reference[:MAX_NAMES]))
    check(f"{tag}: `prefix_only` называет остаток и ссылается на запись префикса",
          not bad_prefix, _brief(bad_prefix[:MAX_NAMES]))
    check(f"{tag}: неразрешимых целей нет (замер 2.6 — 0; неразрешимый остаток только "
          f"стандартные реквизиты, позиция O4)", not bad_unresolved, names(bad_unresolved))

    # 5.4 — вид цели выводится из первого сегмента имени (колонка `target_kind`); целей
    # вида `Role.*` среди прав в корпусе нет (замер 2.4).
    bad_kind = [name for name, row in sorted(seen_targets.items())
                if row["target_kind"] != str(name).split(INDEX_NAME_SEPARATOR)[0]]
    check(f"{tag}: `target_kind` равен первому сегменту полного имени цели", not bad_kind,
          names(bad_kind))
    role_targets = sorted(name for name in seen_targets
                          if name.startswith(INDEX_OBJECT_TYPE + INDEX_NAME_SEPARATOR))
    check(f"{tag}: целей вида `Role.*` среди прав нет (замер 2.4 — 0)", not role_targets,
          names(role_targets))


# ── контур 6: условия права и шаблоны ограничений (замер 2.7, позиция O6) ─────────────
def check_conditions(parsed, circle, raw_totals, expect, tag):
    """Состояния условия против текста файла: `<restrictionByCondition>`, `<field>`."""
    db_rights = circle["rights_rows"]
    states = Counter(row["condition_state"] for row in db_rights)
    with_text = sum(1 for row in db_rights if row["condition_text"] is not None)

    check(f"{tag}: состояний условия права ровно `with_call` {expect['cond_call']}, `no_call` "
          f"{expect['cond_no_call']} (замер 2.7: 4 744 = 4 735 + 9 в BGU2, 4 170 = 4 152 + 18 "
          f"в BP3)",
          states.get(CONDITION_WITH_CALL, 0) == expect["cond_call"]
          and states.get(CONDITION_NO_CALL, 0) == expect["cond_no_call"],
          f"таблица: {_brief(dict(states))}")
    check(f"{tag}: состояний условия разбора равны состояниям таблицы",
          {state: count for state, count in parsed["counts_by_condition_state"].items()
           if count} == {state: count for state, count in states.items() if count},
          f"разбор: {_brief(dict(parsed['counts_by_condition_state']))}; таблица: "
          f"{_brief(dict(states))}")
    check(f"{tag}: прав с текстом условия ровно {expect['cond_call'] + expect['cond_no_call']}",
          with_text == expect["cond_call"] + expect["cond_no_call"], f"факт: {with_text}")
    check(f"{tag}: тегов `<restrictionByCondition>` в файлах ровно {expect['tag_rbc']} — и "
          f"они распределены между состояниями и пустыми `<condition/>` без потерь",
          raw_totals["tag_rbc"] == expect["tag_rbc"]
          and raw_totals["tag_rbc"] == states.get(CONDITION_WITH_CALL, 0)
          + states.get(CONDITION_NO_CALL, 0) + raw_totals["tag_condition_empty"],
          f"тегов: {raw_totals['tag_rbc']}, состояний: "
          f"{states.get(CONDITION_WITH_CALL, 0) + states.get(CONDITION_NO_CALL, 0)}, пустых "
          f"условий: {raw_totals['tag_condition_empty']}")
    check(f"{tag}: пустых `<condition/>` ровно {expect['cond_empty']} (KomMag — 1, замер П2), "
          f"разбор называет их счётчиком `empty_condition_elements`",
          raw_totals["tag_condition_empty"] == expect["cond_empty"]
          and parsed["empty_condition_elements"] == expect["cond_empty"],
          f"тегов: {raw_totals['tag_condition_empty']}, разбора: "
          f"{parsed['empty_condition_elements']}")

    field_rows = sum(1 for row in db_rights if row["restriction_field_name"])
    check(f"{tag}: прав с полем `<field>` ровно {expect['field_rows']} (замер П2: 1/1/1 по "
          f"BGU2/BP3/KomMag) — и столько же тегов `<field>` в файлах",
          field_rows == expect["field_rows"] == raw_totals["tag_field"],
          f"таблица: {field_rows}, тегов: {raw_totals['tag_field']}")
    field_without_condition = [
        (row["target_full_name"], row["right_name"]) for row in db_rights
        if row["restriction_field_name"] and row["condition_state"] == "no_condition"]
    if field_rows:
        info(f"{tag}: прав с полем `<field>` без текста условия — {len(field_without_condition)}"
             f" из {field_rows}: поле бывает и без условия (KomMag, замер П2), и это "
             f"состояние строки, а не отброшенные данные")
    empty_field_names = [row["target_full_name"] for row in db_rights
                         if row["restriction_field_name"] == ""]
    check(f"{tag}: пустых имён поля права нет — пустой элемент остаётся состоянием "
          f"разбора, а не строкой с пустым именем (CHECK "
          f"`role_rights_field_name_not_blank`)", not empty_field_names,
          _brief(empty_field_names[:MAX_NAMES]))


def check_templates(parsed, circle, raw_totals, expect, header_names, tag):
    """Дедупликация шаблонов ограничений: ключ — пара (имя, отпечаток текста).

    Отображение «имя → текст» не инъективно в обе стороны (позиция O6): корпус даёт 18 строк
    при 10 именах и 9 текстах. Проверка считает строки, имена и тексты раздельно: равенство
    любого из них двум другим было бы потерей различия.
    """
    db_rows = circle["template_rows"]
    parsed_rows = {(row["name"], row["digest"]): row for row in parsed["template_rows"]}
    check(f"{tag}: строк шаблонов ровно {expect['tpl_rows']} (разбор и таблица)",
          len(db_rows) == expect["tpl_rows"] == len(parsed_rows),
          f"таблица: {len(db_rows)}, разбор: {len(parsed_rows)}")

    keys = Counter((row["name"], row["digest"]) for row in db_rows)
    duplicated = sorted(key for key, count in keys.items() if count > 1)
    check(f"{tag}: пар (имя, отпечаток) в таблице по одной — ключ работает", not duplicated,
          _brief(duplicated[:MAX_NAMES]))
    distinct_names = len({row["name"] for row in db_rows})
    distinct_digests = len({row["digest"] for row in db_rows})
    check(f"{tag}: различных имён шаблонов ровно {expect['tpl_names']}, различных текстов "
          f"ровно {expect['tpl_digests']} (позиция O6: имена и тексты не совпадают)",
          distinct_names == expect["tpl_names"] and distinct_digests == expect["tpl_digests"],
          f"имён: {distinct_names}, текстов: {distinct_digests}")
    check(f"{tag}: вхождений `<restrictionTemplate>` в файлах ровно "
          f"{expect['tpl_occurrences']} (замер 2.7) — разбор и файл дают одно число",
          parsed["template_occurrences"] == expect["tpl_occurrences"]
          and raw_totals["tag_rtpl"] == expect["tpl_occurrences"],
          f"разбор: {parsed['template_occurrences']}, тегов: {raw_totals['tag_rtpl']}")

    bad_digest, bad_signature, bad_length = [], [], []
    for row in db_rows:
        if row["digest"] != condition_digest(row["condition_text"]):
            bad_digest.append(row["name"])
        if row["name_signature"] != template_signature(row["name"]) or not row[
                "name"].startswith(row["name_signature"]):
            bad_signature.append((row["name"], row["name_signature"],
                                  template_signature(row["name"])))
        if row["condition_length"] != len(row["condition_text"]):
            bad_length.append((row["name"], row["condition_length"],
                               len(row["condition_text"])))
    check(f"{tag}: `digest` равен пересчёту `condition_digest(condition_text)` (отпечаток — "
          f"ключ дедупликации)", not bad_digest, names(bad_digest))
    check(f"{tag}: `name_signature` равен пересчёту `template_signature(name)` и является "
          f"префиксом имени", not bad_signature, _brief(bad_signature[:MAX_NAMES]))
    check(f"{tag}: `condition_length` равен фактической длине текста", not bad_length,
          _brief(bad_length[:MAX_NAMES]))

    holders_bad, holders_outside = [], []
    known_roles = set(header_names)
    for row in db_rows:
        parsed_row = parsed_rows.get((row["name"], row["digest"]))
        if parsed_row is None:
            holders_bad.append((row["name"], "пары нет в разборе"))
            continue
        if sorted(row["holder_role_names"] or []) != sorted(parsed_row["holder_role_names"]):
            holders_bad.append((row["name"], _brief(row["holder_role_names"]),
                                _brief(parsed_row["holder_role_names"])))
        if row["holders_count"] != len(row["holder_role_names"] or []):
            holders_bad.append((row["name"], "носителей", row["holders_count"],
                                len(row["holder_role_names"] or [])))
        for holder in row["holder_role_names"] or []:
            if holder not in known_roles:
                holders_outside.append((row["name"], holder))
    check(f"{tag}: перечень носителей шаблона равен носителям разбора и своей длине",
          not holders_bad, _brief(holders_bad[:MAX_NAMES]))
    check(f"{tag}: носителем шаблона названа только роль этой конфигурации из перечня "
          f"заголовка", not holders_outside, _brief(holders_outside[:MAX_NAMES]))

    # Связь условия права с шаблоном: имя из `restriction_template_names` разрешается строкой
    # шаблона той же конфигурации; `with_call` держит имена, `no_call` — нет. CHECK
    # `role_rights_condition_matches_state` соблюдается данными, а не только ограничением.
    declared = {row["name"] for row in db_rows}
    unresolved_calls, state_mismatch = [], []
    for row in circle["rights_rows"]:
        called = row["restriction_template_names"] or []
        for name in called:
            if name not in declared:
                unresolved_calls.append((row["target_full_name"], row["right_name"], name))
        state = row["condition_state"]
        if state == CONDITION_WITH_CALL and not called:
            state_mismatch.append((row["target_full_name"], row["right_name"],
                                   "with_call без имени шаблона"))
        if state == CONDITION_NO_CALL and called:
            state_mismatch.append((row["target_full_name"], row["right_name"],
                                   "no_call с именем шаблона"))
    check(f"{tag}: каждое имя шаблона из условия права разрешается строкой шаблона той же "
          f"конфигурации", not unresolved_calls, _brief(unresolved_calls[:MAX_NAMES]))
    check(f"{tag}: состояние условия согласовано с перечнем имён шаблона (CHECK "
          f"`role_rights_condition_matches_state` соблюдается данными)", not state_mismatch,
          _brief(state_mismatch[:MAX_NAMES]))


# ── контур 7: флаги содержимого роли (план 2.5, исправленный прогоном П6) ─────────────
def check_flags(role_by_name, raw_per_role, expect, tag):
    """Значения трёх флагов сравниваются с файлом, а не с текстом плана.

    Раздел 2.5 плана утверждал «MinCfg и KomMag — все три флага true»; файлы дают другое
    (`independentRightsOfChildObjects` = false у обеих ролей MinCfg и у одной из четырёх в
    KomMag, в BP3 `setForAttributesByDefault` = false у пяти). Факт — текст выгрузки, поэтому
    сравнение идёт с независимым подсчётом тегов, а ожидание снято этим замером.
    """
    columns = {"set_for_new_objects": ("flag_snf_true", "setForNewObjects"),
               "set_for_attributes_by_default": ("flag_sfa_true",
                                                "setForAttributesByDefault"),
               "independent_rights_of_child_objects": ("flag_ind_true",
                                                       "independentRightsOfChildObjects")}
    for column, (key, element) in columns.items():
        db_true = sum(1 for role in role_by_name.values() if role[column] is True)
        db_null = sum(1 for role in role_by_name.values() if role[column] is None)
        file_true = sum(raw.get(key, 0) for raw in raw_per_role.values())
        check(f"{tag}: флагов `{column}` = true ровно {expect[key]} — и столько же "
              f"`<{element}>true</{element}>` в файлах прав (план 2.5 исправлен замером П6)",
              db_true == expect[key] == file_true,
              f"таблица: {db_true}, файлов: {file_true}")
        check(f"{tag}: флагов `{column}` без значения нет (по одному на файл, замер 2.5)",
              db_null == 0, f"NULL: {db_null}")


# ── контур 8: витрины текущего состояния, ключ цепочки, отказ цепи ────────────────────
def check_views(cur, cfg_uuid, role_by_name, circle, tag):
    """Витрины называются реестром; на ключ — одна текущая строка; цепи прав нет."""
    for table in ("roles", "role_sources", "role_restriction_templates"):
        view = current_view(table)
        exists = int(one(cur, "SELECT count(*) AS c FROM information_schema.views "
                              "WHERE table_schema = 'public' AND table_name = %s",
                         (view,)).get("c") or 0)
        check(f"витрина `{table}` называется реестром `current_view()` ({view}) и существует",
              exists == 1, f"строк определения: {exists}")

    refused = ""
    try:
        current_view("role_rights")
    except ValueError as exc:
        refused = str(exc)
    check("`current_view(\"role_rights\")` отказывает: своей цепи ревизий у таблицы нет "
          "(Q2, вариант A)", bool(refused), "модуль вернул имя витрины вместо отказа")
    check("витрина прав строится связкой, а не поиском максимума по своей цепи",
          RIGHTS_VIEW.startswith("v_current_") and "role_rights" in RIGHTS_VIEW, RIGHTS_VIEW)

    role_rows = circle["role_rows"]
    view_rows = int(one(cur, f"SELECT count(*) AS c FROM {ROLE_VIEW} "
                             "WHERE configuration_uuid = %(uuid)s::uuid",
                        {"uuid": str(cfg_uuid)}).get("c") or 0)
    keys = len({row["object_name"] for row in role_rows})
    check(f"{tag}: витрина ролей отдаёт ровно по одной текущей строке на ключ цепочки "
          f"({len(role_rows)} строк, {keys} ключей)",
          view_rows == len(role_rows) == keys,
          f"витрина: {view_rows}, таблица: {len(role_rows)}, ключей: {keys}")
    duplicated = q(cur, f"SELECT object_name, count(*) AS c FROM {ROLE_VIEW} "
                        "WHERE configuration_uuid = %(uuid)s::uuid "
                        "GROUP BY object_name HAVING count(*) > 1",
                   {"uuid": str(cfg_uuid)})
    check(f"{tag}: дубликатов текущих строк роли по одному ключу в витрине нет",
          not duplicated, _brief(duplicated[:MAX_NAMES]))

    rights = circle["rights_rows"]
    joined = int(one(cur, f"SELECT count(*) AS c FROM {RIGHTS_VIEW} rr "
                          f"JOIN {ROLE_VIEW} r ON r.id = rr.role_id "
                          "WHERE rr.configuration_uuid = %(uuid)s::uuid",
                     {"uuid": str(cfg_uuid)}).get("c") or 0)
    counters = sum(int(role["rights_count"]) for role in role_by_name.values())
    check(f"{tag}: витрина прав читается связкой с витриной ролей и отдаёт ровно "
          f"{len(rights)} строк (столько же держат счётчики CURRENT-ролей)",
          joined == len(rights) == counters,
          f"связка: {joined}, выборка: {len(rights)}, счётчики: {counters}")
    stale_rights = int(one(cur, f"SELECT count(*) AS c FROM role_rights rr "
                                f"LEFT JOIN {ROLE_VIEW} r ON r.id = rr.role_id "
                                "WHERE rr.configuration_uuid = %(uuid)s::uuid "
                                "AND r.id IS NULL",
                           {"uuid": str(cfg_uuid)}).get("c") or 0)
    check(f"{tag}: прав, висящих не на CURRENT-ревизии роли, нет", stale_rights == 0,
          f"таких строк: {stale_rights}")


def check_key_definitions(cur):
    """Живые определения ключей цепочки и ключа прав читаются из схемы, а не из DDL."""
    for index_name, columns in KEY_DEFINITIONS:
        definition = str(one(cur, "SELECT indexdef AS def FROM pg_indexes "
                                  "WHERE indexname = %s", (index_name,)).get("def") or "")
        normalized = " ".join(definition.split()).lower()
        check(f"ключ `{index_name}` называет `{columns}`", columns in normalized,
              f"живое определение: {definition[:200] or 'индекса нет'}")
        check(f"определение `{index_name}` не содержит мёртвого предиката WHERE",
              " where " not in normalized, f"живое определение: {definition[:200]}")
    for index_name in RIGHTS_INDEXES:
        definition = str(one(cur, "SELECT indexdef AS def FROM pg_indexes "
                                  "WHERE indexname = %s", (index_name,)).get("def") or "")
        check(f"индекс `{index_name}` существует (вопросы «какие роли дают Edit на цель» "
              f"и «какие права даёт роль» идут по нему)", bool(definition),
              "индекса нет")


def check_shared_names(cur):
    """Имя роли, общее для двух конфигураций, остаётся в витрине по строке на конфигурацию.

    Факт, а не рассуждение: именно ради него в ключ цепочки входит `configuration_uuid`
    (271 такое имя по корпусу). Если бы витрина схлопывала такую пару, вторая конфигурация
    потеряла бы состав прав молча.
    """
    shared = q(cur, f"""
        SELECT object_name, count(DISTINCT configuration_uuid) AS configs
          FROM {ROLE_TABLES[0]}
         GROUP BY object_name
        HAVING count(DISTINCT configuration_uuid) >= 2
    """)
    if not shared:
        skip("имена ролей, общие для нескольких конфигураций, различаются витриной",
             "в таблице нет имени, встречающегося в двух конфигурациях: различение "
             "доказать нечем")
        return 0
    collapsed = q(cur, f"""
        SELECT s.object_name, s.configs, count(v.id) AS in_view
          FROM (SELECT object_name, count(DISTINCT configuration_uuid) AS configs
                  FROM {ROLE_TABLES[0]}
                 GROUP BY object_name
                HAVING count(DISTINCT configuration_uuid) >= 2) s
          LEFT JOIN {ROLE_VIEW} v ON v.object_name = s.object_name
         GROUP BY s.object_name, s.configs
        HAVING count(v.id) <> s.configs
    """)
    check(f"{len(shared)} имён ролей встречаются в двух и более конфигурациях — каждое "
          f"остаётся в витрине по строке на конфигурацию", not collapsed,
          _brief(collapsed[:MAX_NAMES]))
    return len(shared)


# ── контур 9: сироты, граница R5, неприкосновенность чужого круга ─────────────────────
def check_orphans(cur):
    """Строк узла без строки заголовка нет — каскада в схеме нет осознанно (V20.1)."""
    total = 0
    for table in ROLE_TABLES:
        orphans = int(one(cur, f"SELECT count(*) AS c FROM {table} x "
                               "LEFT JOIN configurations c ON c.uuid = x.configuration_uuid "
                               "WHERE c.id IS NULL").get("c") or 0)
        check(f"сирот по заголовку в таблице `{table}` нет (снятие держит `_remove_rows`, "
              f"каскада нет)", orphans == 0, f"сирот: {orphans}")
        total += orphans
    return total


def dump_newer_than_rows(dump_dir, role_rows):
    """True, если файлы круга новее строк узла (правило R5); None — если мерить нечем."""
    stamps = [row["changed_at"] for row in role_rows if row.get("changed_at")]
    if not stamps:
        return None
    directory = Path(dump_dir) / DIR_NAME
    if not directory.is_dir():
        return None
    newest_file = max((item.stat().st_mtime for item in directory.rglob("*")
                      if item.is_file()), default=None)
    if newest_file is None:
        return None
    newest_row = max(stamp.timestamp() for stamp in stamps)
    return newest_file > newest_row


def foreign_state(cur):
    """Снимок того, что узел V49 трогать не должен (сверяется до и после прогона)."""
    watched = [
        ("configurations", "count(*)"),
        ("configuration_objects", "count(*)"),
        ("session_parameters", "count(*)"),
        ("subsystems", "count(*)"),
        ("common_modules", "count(*)"),
        ("bsl_modules", "count(*)"),
        ("external_report", "count(*)"),
        ("config_aliases", "count(*)"),
        ("config_snippets", "count(*)"),
    ]
    state = {}
    for table, expression in watched:
        try:
            state[table] = one(cur, f"SELECT {expression} AS c FROM {table}").get("c")
        except Exception:  # noqa: BLE001 — чужого слоя может не быть в этой базе
            cur.connection.rollback()
            state[table] = "нет таблицы"
    return state


def check_untouched(before, after):
    changed = [table for table in before if before[table] != after.get(table)]
    check("чужие слои за прогон не изменились — проверка только читает "
          f"({len(before)} таблиц)", not changed, _brief(changed))


# ── контур 10: итог по сравненным конфигурациям и корпусные числа ─────────────────────
def aggregate_queries():
    """Корпусные меры одним запросом на величину (витрины, а не таблицы).

    Каждый запрос обязан называть колонку `c`: `one()` читает по имени, а `count(*)` без
    алиаса даёт колонку `count` — мера молча читалась бы нулём.
    """
    return {
        "role_rows": f"SELECT count(*) AS c FROM {ROLE_VIEW}",
        "source_rows": f"SELECT count(*) AS c FROM {SOURCE_VIEW}",
        "rights_rows": f"SELECT count(*) AS c FROM {RIGHTS_VIEW}",
        "tpl_rows": f"SELECT count(*) AS c FROM {TEMPLATE_VIEW}",
        "tpl_names": f"SELECT count(DISTINCT name) AS c FROM {TEMPLATE_VIEW}",
        "tpl_digests": f"SELECT count(DISTINCT digest) AS c FROM {TEMPLATE_VIEW}",
        "prefix_rights_rows": f"SELECT count(*) AS c FROM {RIGHTS_VIEW} "
                              "WHERE target_resolve_state = 'prefix_only'",
        "cond_text_rows": f"SELECT count(*) AS c FROM {RIGHTS_VIEW} "
                          "WHERE condition_text IS NOT NULL",
        "granted": f"SELECT count(*) AS c FROM {RIGHTS_VIEW} "
                   "WHERE right_value_state = 'granted'",
        "denied": f"SELECT count(*) AS c FROM {RIGHTS_VIEW} "
                  "WHERE right_value_state = 'denied'",
        "empty_content": f"SELECT count(*) AS c FROM {ROLE_VIEW} "
                         "WHERE content_state = 'empty_content'",
        "right_names_union": f"SELECT count(DISTINCT right_name) AS c FROM {RIGHTS_VIEW}",
        "comments": f"SELECT count(*) AS c FROM {ROLE_VIEW} "
                    "WHERE comment IS NOT NULL AND comment <> ''",
        "empty_synonym": f"SELECT count(*) AS c FROM {ROLE_VIEW} "
                         "WHERE synonym IS NULL OR synonym = '{}'::jsonb",
        "shared_names": f"SELECT count(*) AS c FROM (SELECT object_name FROM {ROLE_VIEW} "
                        "GROUP BY object_name "
                        "HAVING count(DISTINCT configuration_uuid) > 1) d",
    }



def check_aggregate(cur, totals, run_tags, skipped_tags):
    """Суммы по сравненным конфигурациям равны суммам их строк плана (раздел 7)."""
    expected = Counter()
    for tag in run_tags:
        for key, value in PLAN_EXPECTATIONS[tag].items():
            if isinstance(value, int):
                expected[key] += value
    compared = ("meta_files", "rights_files", "index_roles", "index_rights", "header",
                "role_rows", "source_rows", "rights_rows", "tag_objects", "tag_rights",
                "tag_value_true", "tag_value_false", "tag_rbc", "tag_rtpl", "tag_field",
                "resolve_exact", "resolve_prefix", "resolve_unresolved",
                "prefix_rights_rows", "empty_content", "cond_call", "cond_no_call",
                "field_rows", "tpl_rows", "tpl_digests", "tpl_occurrences",
                "flag_snf_true", "flag_sfa_true", "flag_ind_true")
    mismatched = {key: (expected.get(key, 0), totals.get(key, 0)) for key in compared
                  if expected.get(key, 0) != totals.get(key, 0)}
    check(f"суммы по {len(run_tags)} сравненным конфигурациям равны числам их строк плана",
          not mismatched, "; ".join(f"{key}: план {plan}, прогон {fact}"
                                    for key, (plan, fact) in sorted(mismatched.items())))
    info(f"сравнены: {', '.join(run_tags) or 'ничего'}"
         + (f"; пропущены: {', '.join(skipped_tags)}" if skipped_tags else ""))

    if set(run_tags) != set(PLAN_EXPECTATIONS):
        skip("корпусные числа (разделы 2.1, 2.4, 2.7, 7 плана)",
             f"сравнены не все четыре выгрузки ({', '.join(sorted(run_tags))} из "
             f"{len(PLAN_EXPECTATIONS)}): корпусная сумма считалась бы по неполному кругу")
        return
    corpus = {}
    for key, sql in aggregate_queries().items():
        corpus[key] = int(one(cur, sql).get("c") or 0)
    # Теги файлов измеряются по выгрузкам (контуры 4) — корпусной суммы по ним база не
    # держит, поэтому она берётся из мер сравненных конфигураций, а не выдумывается.
    corpus["tag_objects"] = totals["tag_objects"]
    corpus["tag_rights"] = totals["tag_rights"]
    mismatched = {key: (CORPUS_EXPECTATIONS[key], corpus.get(key))
                  for key, value in CORPUS_EXPECTATIONS.items() if corpus.get(key) != value}
    check(f"корпусные числа равны числам плана: ролей {CORPUS_EXPECTATIONS['role_rows']}, "
          f"прав {CORPUS_EXPECTATIONS['rights_rows']}, целей "
          f"{CORPUS_EXPECTATIONS['tag_objects']}, шаблонов "
          f"{CORPUS_EXPECTATIONS['tpl_rows']} при {CORPUS_EXPECTATIONS['tpl_names']} именах "
          f"и {CORPUS_EXPECTATIONS['tpl_digests']} текстах (позиция O6)",
          not mismatched,
          "; ".join(f"{key}: план {plan}, база {fact}"
                    for key, (plan, fact) in sorted(mismatched.items())))
    check(f"закрытый словарь имён права по объединению выгрузок — "
          f"{CORPUS_EXPECTATIONS['right_names_union']} имён (замер 2.4), константа модуля "
          f"KNOWN_RIGHT_NAME_COUNT та же",
          corpus.get("right_names_union") == KNOWN_RIGHT_NAME_COUNT
          == CORPUS_EXPECTATIONS["right_names_union"],
          f"словарь модуля: {KNOWN_RIGHT_NAME_COUNT}, база: "
          f"{corpus.get('right_names_union')}")


def check_stage_groups(cur):
    """Круг групп отдельного входа назван контрактом — и он равен таблицам узла."""
    declared = {table for tables in ROLE_TABLES_BY_KIND.values() for table in tables}
    check("группы круга `load_roles_tool` (kinds) покрывают ровно таблицы узла V49",
          declared == set(ROLE_TABLES) and len(ROLE_TABLES_BY_KIND) == 3,
          f"по группам: {sorted(declared)}; узел: {sorted(ROLE_TABLES)}")


def add_totals(totals, circle, parsed, raw_totals, role_by_name):
    """Меры сравненной конфигурации входят в итог — иначе итог считался бы по словам."""
    totals["meta_files"] += sum(1 for entry in circle["files_by_name"].values()
                                if entry.get("metadata"))
    totals["rights_files"] += sum(1 for entry in circle["files_by_name"].values()
                                  if entry.get("rights"))
    totals["index_roles"] += len(circle["index_role_records"])
    totals["index_rights"] += len(circle["index_rights_records"])
    totals["header"] += len(circle["header_names"])
    totals["role_rows"] += len(circle["role_rows"])
    totals["source_rows"] += len(circle["source_rows"])
    totals["rights_rows"] += len(circle["rights_rows"])
    for key in ("tag_objects", "tag_rights", "tag_value_true", "tag_value_false",
                "tag_rbc", "tag_rtpl", "tag_field"):
        totals[key] += raw_totals[key]
    parse_states = parsed["counts_by_target_resolve_state"]
    totals["resolve_exact"] += parse_states.get("exact", 0)
    totals["resolve_prefix"] += parse_states.get(TARGET_PREFIX_ONLY, 0)
    totals["resolve_unresolved"] += parse_states.get("unresolved", 0)
    by_right = Counter(row["target_resolve_state"] for row in circle["rights_rows"])
    totals["prefix_rights_rows"] += by_right.get(TARGET_PREFIX_ONLY, 0)
    totals["empty_content"] += sum(1 for row in circle["role_rows"]
                                   if row["content_state"] == "empty_content")
    cond = Counter(row["condition_state"] for row in circle["rights_rows"])
    totals["cond_call"] += cond.get(CONDITION_WITH_CALL, 0)
    totals["cond_no_call"] += cond.get(CONDITION_NO_CALL, 0)
    totals["field_rows"] += sum(1 for row in circle["rights_rows"]
                                if row["restriction_field_name"])
    totals["tpl_rows"] += len(circle["template_rows"])
    totals["tpl_digests"] += len({row["digest"] for row in circle["template_rows"]})
    totals["tpl_occurrences"] += parsed["template_occurrences"]
    for column, key in (("set_for_new_objects", "flag_snf_true"),
                        ("set_for_attributes_by_default", "flag_sfa_true"),
                        ("independent_rights_of_child_objects", "flag_ind_true")):
        totals[key] += sum(1 for role in role_by_name.values() if role[column] is True)


def run(cur, scope):
    headers = q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations ORDER BY id")
    if not headers:
        print("FAIL строк заголовков конфигураций в базе нет — сравнивать не с чем")
        FAILED.append("нет строк заголовков")
        return
    before = foreign_state(cur)
    totals = Counter()
    run_tags, skipped_tags = [], []
    for header in headers:
        resolved = resolve_dump_dir(header["uuid"], DUMP_ROOT)
        dump_dir = resolved.get("path") or ""
        tag = Path(dump_dir).name if dump_dir else str(header["name"])
        if scope not in (DEFAULT_SCOPE, tag, str(header["name"])):
            continue
        section(f"Конфигурация {tag} (uuid {header['uuid']})")
        if not dump_dir:
            skipped_tags.append(tag)
            skip(f"{tag}: все контуры узла",
                 resolved.get("reason") or "каталог выгрузки не найден")
            continue
        expect = PLAN_EXPECTATIONS.get(tag)
        if expect is None:
            skipped_tags.append(tag)
            skip(f"{tag}: все контуры узла",
                 f"каталога `{tag}` нет в перечне ожиданий проверки — числа круга этой "
                 f"выгрузки надо переснять и записать в план прежде, чем сравнивать с ними")
            continue
        index_info = read_index_records(cur, int(header["id"]))
        if not index_info["available"]:
            skipped_tags.append(tag)
            skip(f"{tag}: контуры круга, разрешения целей и словаря состояний",
                 index_info.get("reason") or "индекс состава этой конфигурации не загружен: "
                                            "сверка файлов с перечнем и разрешение целей "
                                            "невыразимы")
            continue
        circle = check_circle(cur, header, dump_dir, index_info, expect, tag)
        role_rows = circle["role_rows"]
        if not role_rows:
            skipped_tags.append(tag)
            skip(f"{tag}: контуры «файл ↔ строка», прав, целей, условий и шаблонов",
                 "строк узла в таблице нет — конфигурацию не перезагружали после узла V49 "
                 "(стадия `s4d_roles` входит в загрузку каталога, отдельный вход группы — "
                 "`load_roles_tool`)")
            continue
        if dump_newer_than_rows(dump_dir, role_rows):
            skipped_tags.append(tag)
            skip(f"{tag}: контуры «файл ↔ строка» и мер файла",
                 "файлы выгрузки новее строк узла (правило R5): сохранённые права описывают "
                 "прошлое состояние, сравнение с ним было бы сравнением с прошлым")
            continue
        role_by_name = {row["object_name"]: row for row in role_rows}
        parsed = parse_circle(dump_dir, index_info["rows"])
        raw_totals, raw_per_role, unreadable = raw_measures(dump_dir)
        check(f"{tag}: файлов прав, которые не удалось прочитать, нет", not unreadable,
              _brief(unreadable[:MAX_NAMES]))
        check(f"{tag}: круг файлов прав измерен полностью",
              raw_totals["measured_files"] == expect["rights_files"],
              f"измерено файлов: {raw_totals['measured_files']}, "
              f"ожидается: {expect['rights_files']}")
        check_role_rows(parsed, role_rows, expect, tag)
        check_sources(parsed, circle, role_by_name, expect, dump_dir, tag)
        check_rights(parsed, circle, role_by_name, raw_totals, raw_per_role, expect, tag)
        check_targets(parsed, circle, circle["index_by_key"], expect, tag)
        check_conditions(parsed, circle, raw_totals, expect, tag)
        check_templates(parsed, circle, raw_totals, expect, circle["header_names"], tag)
        check_flags(role_by_name, raw_per_role, expect, tag)
        check_views(cur, header["uuid"], role_by_name, circle, tag)
        add_totals(totals, circle, parsed, raw_totals, role_by_name)
        # В перечень сравнения конфигурация входит только после того, как её числа легли в
        # суммы: иначе итог сравнивал бы суммы по четырём строкам плана с фактом по трём.
        run_tags.append(tag)

    after = foreign_state(cur)
    section("Итог узла V49")
    check_orphans(cur)
    check_key_definitions(cur)
    check_stage_groups(cur)
    totals["shared_names"] = check_shared_names(cur)
    check_untouched(before, after)
    check_aggregate(cur, totals, run_tags, skipped_tags)


def main(argv):
    scope = str(argv[1]) if len(argv) > 1 else DEFAULT_SCOPE
    try:
        with transaction() as cur:
            run(cur, scope)
    except Exception as exc:  # отказ прогона обязан быть назван, а не оборвать вывод
        FAILED.append(f"прогон прерван исключением: {exc}")
        print(f"FAIL прогон прерван исключением: {type(exc).__name__}: {exc}")
    print("\n" + "=" * 72)
    print(f"ИТОГ: пройдено {len(PASSED)}, провалено {len(FAILED)}, "
          f"пропущено {len(SKIPPED)}, заметок {len(INFO)}")
    for name in FAILED:
        print("  ПРОВАЛ: " + name)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))




















