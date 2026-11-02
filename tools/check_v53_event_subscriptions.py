#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""tools/check_v53_event_subscriptions.py — узел V53: подписки на события (шаг П6).

Это постоянная проверка, а не проба шага: она обязана переживать и перезагрузку выгрузок, и
правки кода загрузки. Источник ожиданий — `docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md`
(раздел 1 — круг и коллизия uuid/имён, раздел 2 — словарь свойств, формы целей и словарь
событий, раздел 5 — M1…M7, раздел 9 — критерии готовности). Числа независимой меры круга сняты
зондом `_v53_p6_counts_probe.py` (регекспой по тексту файла регистрации, без знания о
состояниях разбора) и перенесены в `PLAN_EXPECTATIONS` без правок; вывод зонда —
`_v53_p6_counts_out.txt`. Сглаживать число проверкой — значит подтверждать неверное число
(прецедент узлов V49/V50).

Одна деталь замера названа здесь, а не таблицей 2.2 плана: числа классов целей в плане
(`DocumentObject` 11 907, `CatalogObject` 6 000, `InformationRegisterRecordSet` 3 248) сняты по
ДВУМ большим выгрузкам (BGU2 + BP3), а не по четырём. Четыре выгрузки дают 11 919 / 6 002 /
3 249 — разность 12 / 2 / 1 приходится на MinCfg и KomMag. Три измерения (текст файла, разбор
тем же модулем, строки таблицы — `_v53_p6_db_class_probe.py`) сходятся по каждому классу в
каждой выгрузке, поэтому эталон держит ОБА числа: сумму по BGU2 и BP3 — как строку таблицы
2.2 плана, сумму по четырём выгрузкам — как итог корпуса (контур 6).

Что сторожится — по контурам:

  1. ГРАНИЦА КРУГА (замер 1.1, 1.2). Подписка адресуется четырьмя РАЗНЫМИ источниками:
     каталогом `EventSubscriptions/` (`<Имя>.xml`), индексом состава
     (`EventSubscription.<Имя>`), перечнем `configurations.event_subscriptions[]` (узел V43) и
     строками таблицы `event_subscriptions`. Агрегатный COUNT индекса сверяется с построчным
     обходом (приём V48), множества имён сравниваются попарно во все четыре стороны. Детей
     индекса, подкаталогов и файлов не-XML — ноль: у вида нет детей (замер 1.2, M2), и это
     проверяемое утверждение, а не отсутствие запроса.
  2. СТРОКА ВИДА ↔ РАЗБОР. Каждая колонка строки обязана совпасть с кругом, разобранным
     ТЕМ ЖЕ модулем (`collect_event_subscriptions`), что и загрузка: иначе проверка проверяла
     бы себя, а не то, донёс ли писатель строку.
  3. КЛЮЧ РАЗБОРА ↔ КОЛОНКИ СХЕМЫ. Множества ключей строки разбора и колонок сверяются в обе
     стороны с точностью до колонок ревизии (23 и 18 колонок — эталон шага П1). Отличие от
     V50/V51/V52 названо: плейсхолдеров словаря свойств здесь нет — тег `Source` является
     второй таблицей пары, а не колонкой строки вида.
  4. СТРОКИ БЛОКА `Source` ↔ ФАЙЛ (замер 1.4). Множество (ordinal, тег, `target_raw`, класс,
     форма, состояние разрешения) строк подписки равно множеству элементов `<Source>` её файла;
     `ordinal` — 0..n-1 без пропусков; `source_count` строки вида равен числу строк
     источника; каждая строка источника ссылается на CURRENT-ревизию своей подписки (Q4,
     вариант A) и несёт её `configuration_uuid`, `subscription_object_uuid`,
     `subscription_full_name`. Дополнительно — НЕЗАВИСИМЫЙ подсчёт по тексту файла
     (`v8:Type`, `v8:TypeSet`, именованная и голая формы, максимум записей в файле).
  5. РАЗРЕШИМОСТЬ ЦЕЛЕЙ (замер 2.2). Каждая сохранённая цель разрешается ЗАНОВО по строкам
     индекса состава (`resolve_target_entry`): состояние, `target_object_id`,
     `target_object_uuid` и остаток пути обязаны совпасть с сохранёнными. Распределение
     `exact` / `type_present` / `type_absent` по выгрузкам равно плану (24 835 / 242 / 23 на
     корпусе); `unresolved`, `unknown_class`, `empty_value`, `unknown_form` — ноль, и ноль
     проверяется, а не подразумевается (границы Q3, M5).
  6. СЛОВАРИ И РАЗРЕШЕНИЕ ОБРАБОТЧИКА (замеры 2.1, 2.3). Значения `<Event>` входят в закрытый
     словарь 18 имён, распределение по выгрузкам равно таблице 2.1. Классы целей входят в
     `SOURCE_CLASS_META_TYPES` (30 записей), `target_meta_type` равен значению словаря, а
     распределение классов совпадает с мерой файлов и с обоими эталонами. Форма `Handler` на
     всём корпусе — `CommonModule.<Модуль>.<Метод>` (772 из 772), модуль разрешается ЗАНОВО
     витриной `v_current_common_modules` (`exact` 772). Уникальных обработчиков меньше, чем
     подписок (248 при 311 в BGU2), — это и есть основание не объявлять внешний ключ (Q2),
     поэтому число называется измерением, а не предположением.
  7. СОСТОЯНИЯ СТРОКИ. `properties_state = all_known` на всех строках, неизвестные — ноль;
     `source_state = with_sources` на всех (пустых блоков корпус не давал — M4); пустой
     `Comment` — NULL, и число NULL равно числу пустых тегов по мере файлов. Отдельного
     заголовка у контура нет осознанно: распределения считаются по тем же строкам, что
     сравнивают контуры 2 (принадлежность состояний замкнутым словарям слоя) и 4c
     (распределения против эталона) — третий проход по тем же данным добавил бы только
     повторный заголовок.
   8. ПУСТОЙ КРУГ. У четырёх эталонных выгрузок каталог вида есть (замер 1.1: KomMag — один
      файл), поэтому состояние «каталога нет» проверяется на фикстуре: `success` — истина,
      `files_found` — ноль, наблюдение `directory_missing` названо.
   9. СХЕМА. Числа колонок, ключи `UNIQUE`, индексы, витрины текущего состояния, двусторонняя
      сверка закрытых словарей состояний (`STATE_VOCABULARIES`) с CHECK'ами живой схемы.
  10. ВИТРИНЫ, ЦЕПИ РЕВИЗИЙ, СИРОТЫ И КОЛЛИЗИЯ имени и uuid. Повтор загрузки не заводит вторую
      ревизию (максимум — 1). 192 имени и 162 uuid общие у BGU2 и BP3 (замер 1.3, M1): под
      каждым общим именем обязаны быть строки обеих конфигураций, а не одна. Множества коллизий
      НЕ совпадают: из 162 общих uuid ровно один несёт разные имена (замер
      `_v53_p6_uuid_probe.py`), и называется это число, а не сглаживается; внутри одной
      конфигурации uuid не повторяется — иначе пара (`configuration_uuid`, `object_uuid`) не
      различала бы строки.
  11. КОНТРАКТ. Стадия `s4h_event_subscriptions` стоит между `s4g_filter_criteria` и
      `s4b_object_modules` (порядок позиций 2.7 → 2.8 → модули объектов); круг снятия и
      порядок удаления (`sources` ДО `subscriptions` — иначе `ON DELETE CASCADE` снял бы строки
      молча, и число в ответе было бы неправдой); подсказка продолжения; нулевой ответ стадии;
      вход `load_event_subscriptions_tool` в реестре `EXPECTED_TOOLS` (11 инструментов ядра).
  12. ИТОГ ПО КОРПУСУ и неприкосновенность чужих кругов: сумма по четырём выгрузкам равна
      разделам 1 и 2 плана, таблицы других узлов прогон не меняет.

Запуск:
    python tools/check_v53_event_subscriptions.py          # все четыре выгрузки
    python tools/check_v53_event_subscriptions.py BGU2     # одна выгрузка по имени каталога
Код возврата 0 — провалов нет; пропущенные контуры называются причиной, а не молчанием.
"""
import ast
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "src", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from configuration_event_subscriptions import (  # noqa: E402
    CFG_PREFIX, DIR_NAME, EVENT_NAME_DICTIONARY, EVENT_STATE_KNOWN, EVENT_STATES,
    HANDLER_MODULE_KIND, HANDLER_SEGMENT_COUNT, HANDLER_STATE_EXACT,
    HANDLER_STATE_UNKNOWN_FORM, HANDLER_STATE_UNRESOLVED, HANDLER_STATES,
    INDEX_OBJECT_TYPE, OBJECT_KIND_TAG, PROPERTIES_ALL_KNOWN, PROPERTIES_STATES,
    RESOLVE_EMPTY_VALUE, RESOLVE_EXACT, RESOLVE_TYPE_ABSENT, RESOLVE_TYPE_PRESENT,
    RESOLVE_UNKNOWN_CLASS, RESOLVE_UNKNOWN_FORM, RESOLVE_UNRESOLVED,
    SOURCE_CLASS_META_TYPES, SOURCE_STATE_EMPTY, SOURCE_STATE_WITH, SOURCE_STATES,
    SOURCE_TAGS, STATE_VOCABULARIES, TABLE_NAME, TARGET_FORM_BARE, TARGET_FORMS,
    TARGET_RESOLVE_STATES, XML_PROPERTY_NAMES, collect_event_subscriptions,
    index_meta_types, index_object_name, index_row_key, index_rows_by_name, kind_index_rows,
    read_text_file, resolve_handler_state, resolve_target_entry,
)
from configuration_event_subscriptions_loader import (  # noqa: E402
    REMOVE_ORDER as LAYER_REMOVE_ORDER, read_common_module_names, read_index_records,
)
from configuration_load_contract import (  # noqa: E402
    EVENT_SUBSCRIPTIONS_REMOVE_ORDER, EVENT_SUBSCRIPTIONS_REPEAT_HINT,
    EVENT_SUBSCRIPTIONS_TABLES, FOREIGN_STAGE_TABLES, STAGE_EVENT_SUBSCRIPTIONS,
    STAGE_FILTER_CRITERIA, STAGE_FULL_RELOAD_ONLY, STAGE_OBJECT_MODULES, STAGES,
    event_subscriptions_defaults, stage_resume_hint, stage_title, stages_after,
)
from configuration_module_slots import resolve_dump_dir  # noqa: E402
from current_revision import CONFIGURATION_VERSIONED_TABLES, current_view  # noqa: E402
from external_db import transaction  # noqa: E402
from external_table_writer import CONFIGURATION_UNVERSIONED_TABLES  # noqa: E402

SOURCES_TABLE = "event_subscription_sources"
SUBSCRIPTIONS_VIEW = current_view(TABLE_NAME)
# Строки блока `Source` своей цепи ревизий не имеют (Q4, вариант A), поэтому их витрина не
# порождается реестром `CURRENT_VIEWS`, а построена связкой в DDL: имя называется литералом и
# отдельно проверяется контуром 9 — «витрина живётся» и «таблицы в реестре версионируемых нет
# осознанно» являются разными утверждениями.
SOURCES_VIEW = "v_current_event_subscription_sources"
HEADER_NAME_COLUMN = "event_subscriptions"
COMMON_MODULES_VIEW = "v_current_common_modules"

DUMP_ROOT = r"C:\1C_LLM\LoadDoc\Configurations\XML_files"
DEFAULT_SCOPE = "all"
MAX_NAMES = 10

# Колонки, которые принадлежат цепи ревизий (узел V19), а не узлу V53: их заполняет не
# разбор, и сравнивать их с ключом строки разбора — значит требовать от слоя чужого.
REVISION_COLUMNS = ("id", "configuration_uuid", "created_at", "revision_no", "changed_at",
                    "changed_by", "is_committed")
# Колонки строки источника, которые писатель проставляет сам (связь с ревизией вида и граница
# конфигурации), а не берёт из разбора: они сторожатся контуром 4 отдельно.
SOURCE_WRITER_COLUMNS = ("event_subscription_id", "configuration_uuid", "created_at")

# Числа колонок двух таблиц — эталон шага П1 (миграция V53 + зеркало DDL).
EXPECTED_COLUMN_COUNTS = {TABLE_NAME: 23, SOURCES_TABLE: 18}

PASSED, FAILED, SKIPPED, INFO = [], [], [], []

# ── ожидания проверки (числа плана docs/CONFIGURATION_EVENT_SUBSCRIPTIONS_PLAN.md) ──────────
# Ключ — каталог выгрузки, а не имя строки заголовка: имя заголовка меняется вместе с
# выгрузкой, а каталог — адрес, по которому проверка находит файлы.
#   files / bytes / subdirs / non_xml — каталог `EventSubscriptions/` (плоский, только XML —
#            сторож примитивности вида, замер 1.2);
#   props_block / prop_tags_total / prop_tags_distinct — обёртка `<Properties>` и шесть тегов
#            свойств на файл (замер раздела 2: набор замкнут, min = max = 6);
#   source_block / source_items / tag_Type / tag_TypeSet / target_named / target_bare /
#   target_empty / target_other / typeset_named / sources_max_per_file — блок `<Source>`
#            (замеры 1.4 и 2.2);
#   handler_total / handler_segments / handler_module_kind / handler_distinct — форма и
#            уникальность обработчика (замер 2.3);
#   comment_empty / comment_text — пустой и непустой `<Comment>` (Q7, вариант A);
#   event_<Имя> / class_<Класс> — распределение словарей (замеры 2.1 и 2.2; классы названы не
#            все: полное распределение сравнивает меру файлов со строками БД в контуре 6);
#   index_rows / index_children / header_list / header_is_null — записи индекса состава и
#            перечень заголовка (`header_is_null` = 1, если перечня нет значением NULL);
#   observations / index_only / file_only / uuid_mismatch / directory_missing — круг замкнут во
#            всех четырёх выгрузках (замер 1.1), нули здесь — проверяемое утверждение;
#   db_* — строки двух таблиц (числа плана разделов 1.1, 1.4, 2.1–2.3).
PLAN_EXPECTATIONS = {
    "MinCfg": {
        "files": 2, "bytes": 3322, "subdirs": 0, "non_xml": 0,
        "props_block": 2, "prop_tags_total": 12, "prop_tags_distinct": 12,
        "source_block": 2, "source_items": 5, "tag_Type": 1, "tag_TypeSet": 4,
        "target_named": 1, "target_bare": 4, "target_empty": 0, "target_other": 0,
        "typeset_named": 0, "sources_max_per_file": 3,
        "handler_total": 2, "handler_segments": 2, "handler_module_kind": 2,
        "handler_distinct": 2, "comment_empty": 0, "comment_text": 2,
        "event_FillCheckProcessing": 1, "event_OnWrite": 1,
        "class_CatalogObject": 2, "class_DocumentObject": 2,
        "class_InformationRegisterRecordSet": 1,
        "index_rows": 2, "index_children": 0, "header_list": 2, "header_is_null": 0,
        "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "directory_missing": 0,
        "db_rows": 2, "db_sources": 5,
        "db_resolve_exact": 1, "db_resolve_type_present": 4, "db_resolve_type_absent": 0,
        "db_resolve_unresolved": 0, "db_resolve_unknown_class": 0,
        "db_resolve_empty_value": 0, "db_resolve_unknown_form": 0,
        "db_handler_exact": 2, "db_handler_unresolved": 0, "db_handler_unknown_form": 0,
        "db_handler_distinct": 2, "db_distinct_classes": 3, "db_max_sources": 3,
        "db_properties_all_known": 2, "db_properties_unknown": 0,
        "db_source_with": 2, "db_source_empty": 0,
        "db_comment_null": 0, "db_comment_filled": 2,
    },
    "KomMag": {
        "files": 1, "bytes": 2121, "subdirs": 0, "non_xml": 0,
        "props_block": 1, "prop_tags_total": 6, "prop_tags_distinct": 6,
        "source_block": 1, "source_items": 10, "tag_Type": 10, "tag_TypeSet": 0,
        "target_named": 10, "target_bare": 0, "target_empty": 0, "target_other": 0,
        "typeset_named": 0, "sources_max_per_file": 10,
        "handler_total": 1, "handler_segments": 1, "handler_module_kind": 1,
        "handler_distinct": 1, "comment_empty": 1, "comment_text": 0,
        "event_BeforeDelete": 1, "class_DocumentObject": 10,
        "index_rows": 1, "index_children": 0, "header_list": 1, "header_is_null": 0,
        "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "directory_missing": 0,
        "db_rows": 1, "db_sources": 10,
        "db_resolve_exact": 10, "db_resolve_type_present": 0, "db_resolve_type_absent": 0,
        "db_resolve_unresolved": 0, "db_resolve_unknown_class": 0,
        "db_resolve_empty_value": 0, "db_resolve_unknown_form": 0,
        "db_handler_exact": 1, "db_handler_unresolved": 0, "db_handler_unknown_form": 0,
        "db_handler_distinct": 1, "db_distinct_classes": 1, "db_max_sources": 10,
        "db_properties_all_known": 1, "db_properties_unknown": 0,
        "db_source_with": 1, "db_source_empty": 0,
        "db_comment_null": 1, "db_comment_filled": 0,
    },
    "BGU2": {
        "files": 311, "bytes": 1660546, "subdirs": 0, "non_xml": 0,
        "props_block": 311, "prop_tags_total": 1866, "prop_tags_distinct": 1866,
        "source_block": 311, "source_items": 11706, "tag_Type": 11535, "tag_TypeSet": 171,
        "target_named": 11582, "target_bare": 124, "target_empty": 0, "target_other": 0,
        "typeset_named": 63, "sources_max_per_file": 760,
        "handler_total": 311, "handler_segments": 311, "handler_module_kind": 311,
        "handler_distinct": 248, "comment_empty": 297, "comment_text": 14,
        "event_BeforeDelete": 30, "event_BeforeWrite": 133, "event_FillCheckProcessing": 5,
        "event_Filling": 6, "event_FormGetProcessing": 16, "event_OnCopy": 7,
        "event_OnReceiveDataFromMaster": 1, "event_OnReceiveDataFromSlave": 1,
        "event_OnSendDataToMaster": 1, "event_OnSendDataToSlave": 1,
        "event_OnSendNodeDataToSlave": 1, "event_OnSetNewCode": 1,
        "event_OnSetNewNumber": 4, "event_OnWrite": 94, "event_Posting": 3,
        "event_PresentationFieldsGetProcessing": 3, "event_PresentationGetProcessing": 3,
        "event_UndoPosting": 1,
        "class_DocumentObject": 6601, "class_CatalogObject": 2569,
        "class_InformationRegisterRecordSet": 1131, "class_ConstantValueManager": 804,
        "class_DocumentJournalManager": 1, "class_DefinedType": 63,
        "index_rows": 311, "index_children": 0, "header_list": 311, "header_is_null": 0,
        "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "directory_missing": 0,
        "db_rows": 311, "db_sources": 11706,
        "db_resolve_exact": 11582, "db_resolve_type_present": 108,
        "db_resolve_type_absent": 16,
        "db_resolve_unresolved": 0, "db_resolve_unknown_class": 0,
        "db_resolve_empty_value": 0, "db_resolve_unknown_form": 0,
        "db_handler_exact": 311, "db_handler_unresolved": 0, "db_handler_unknown_form": 0,
        "db_handler_distinct": 248, "db_distinct_classes": 30, "db_max_sources": 760,
        "db_properties_all_known": 311, "db_properties_unknown": 0,
        "db_source_with": 311, "db_source_empty": 0,
        "db_comment_null": 297, "db_comment_filled": 14,
    },
    "BP3": {
        "files": 458, "bytes": 2163686, "subdirs": 0, "non_xml": 0,
        "props_block": 458,
        "prop_tags_total": 2748, "prop_tags_distinct": 2748,
        "source_block": 458, "source_items": 13379, "tag_Type": 13183, "tag_TypeSet": 196,
        "target_named": 13242, "target_bare": 137, "target_empty": 0, "target_other": 0,
        "typeset_named": 76, "sources_max_per_file": 789,
        "handler_total": 458, "handler_segments": 458, "handler_module_kind": 458,
        "handler_distinct": 365, "comment_empty": 446, "comment_text": 12,
        "event_BeforeDelete": 37, "event_BeforeWrite": 168, "event_FillCheckProcessing": 8,
        "event_Filling": 8, "event_FormGetProcessing": 29, "event_OnCopy": 5,
        "event_OnReceiveDataFromMaster": 1, "event_OnReceiveDataFromSlave": 1,
        "event_OnSendDataToMaster": 1, "event_OnSendDataToSlave": 2,
        "event_OnSendNodeDataToSlave": 1, "event_OnSetNewCode": 3,
        "event_OnSetNewNumber": 8, "event_OnWrite": 173, "event_Posting": 5,
        "event_PresentationFieldsGetProcessing": 2, "event_PresentationGetProcessing": 2,
        "event_UndoPosting": 4,
        "class_DocumentObject": 5306, "class_CatalogObject": 3431,
        "class_InformationRegisterRecordSet": 2117, "class_ConstantValueManager": 1326,
        "class_DocumentJournalManager": 26, "class_DefinedType": 76,
        "index_rows": 458, "index_children": 0, "header_list": 458, "header_is_null": 0,
        "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
        "directory_missing": 0,
        "db_rows": 458, "db_sources": 13379,
        "db_resolve_exact": 13242, "db_resolve_type_present": 130,
        "db_resolve_type_absent": 7,
        "db_resolve_unresolved": 0, "db_resolve_unknown_class": 0,
        "db_resolve_empty_value": 0, "db_resolve_unknown_form": 0,
        "db_handler_exact": 458, "db_handler_unresolved": 0, "db_handler_unknown_form": 0,
        "db_handler_distinct": 365, "db_distinct_classes": 30, "db_max_sources": 789,
        "db_properties_all_known": 458, "db_properties_unknown": 0,
        "db_source_with": 458, "db_source_empty": 0,
        "db_comment_null": 446, "db_comment_filled": 12,
    },
}

# ── ожидания по корпусу (четыре выгрузки, 772 файла) ──────────────────────────────────────
# Распределение имён событий (таблица 2.1), тегов и форм блока `<Source>` (1.4, 2.2), классов
# целей (2.2) мерилось по всем четырём выгрузкам. Суммирование осмысленно только когда прогону
# доступны все четыре: сумму по трём сравнивать с итогом по четырём — ложное расхождение
# (прецедент V50/V51/V52), поэтому сравнение включается по полному кругу.
CORPUS_TOTALS = {
    "files": 772, "bytes": 3829675, "subdirs": 0, "non_xml": 0,
    "props_block": 772, "prop_tags_total": 4632, "prop_tags_distinct": 4632,
    "source_block": 772, "source_items": 25100, "tag_Type": 24729, "tag_TypeSet": 371,
    "target_named": 24835, "target_bare": 265, "target_empty": 0, "target_other": 0,
    "typeset_named": 139,
    "handler_total": 772, "handler_segments": 772, "handler_module_kind": 772,
    "comment_empty": 744, "comment_text": 28,
    "event_BeforeDelete": 68, "event_BeforeWrite": 301, "event_FillCheckProcessing": 14,
    "event_Filling": 14, "event_FormGetProcessing": 45, "event_OnCopy": 12,
    "event_OnReceiveDataFromMaster": 2, "event_OnReceiveDataFromSlave": 2,
    "event_OnSendDataToMaster": 2, "event_OnSendDataToSlave": 3,
    "event_OnSendNodeDataToSlave": 2, "event_OnSetNewCode": 4, "event_OnSetNewNumber": 12,
    "event_OnWrite": 268, "event_Posting": 8, "event_PresentationFieldsGetProcessing": 5,
    "event_PresentationGetProcessing": 5, "event_UndoPosting": 5,
    "class_AccountingRegisterManager": 3, "class_AccountingRegisterRecordSet": 18,
    "class_AccumulationRegisterManager": 2, "class_AccumulationRegisterRecordSet": 596,
    "class_BusinessProcessManager": 6, "class_BusinessProcessObject": 35,
    "class_CalculationRegisterManager": 2, "class_CalculationRegisterRecordSet": 7,
    "class_CatalogManager": 353, "class_CatalogObject": 6002,
    "class_ChartOfAccountsManager": 3, "class_ChartOfAccountsObject": 40,
    "class_ChartOfCalculationTypesManager": 2, "class_ChartOfCalculationTypesObject": 32,
    "class_ChartOfCharacteristicTypesManager": 2, "class_ChartOfCharacteristicTypesObject": 130,
    "class_ConstantValueManager": 2130, "class_DataProcessorManager": 45,
    "class_DefinedType": 139, "class_DocumentJournalManager": 27, "class_DocumentManager": 191,
    "class_DocumentObject": 11919, "class_ExchangePlanObject": 46,
    "class_InformationRegisterManager": 68, "class_InformationRegisterRecordSet": 3249,
    "class_RecalculationRecordSet": 4, "class_ReportManager": 11,
    "class_SequenceRecordSet": 7, "class_TaskManager": 2, "class_TaskObject": 29,
    "index_rows": 772, "index_children": 0, "header_list": 772, "header_is_null": 0,
    "observations": 0, "index_only": 0, "file_only": 0, "uuid_mismatch": 0,
    "directory_missing": 0,
    "db_rows": 772, "db_sources": 25100,
    "db_resolve_exact": 24835, "db_resolve_type_present": 242,
    "db_resolve_type_absent": 23, "db_resolve_unresolved": 0, "db_resolve_unknown_class": 0,
    "db_resolve_empty_value": 0, "db_resolve_unknown_form": 0,
    "db_handler_exact": 772, "db_handler_unresolved": 0, "db_handler_unknown_form": 0,
    "db_distinct_classes": 30,
    "db_properties_all_known": 772, "db_properties_unknown": 0,
    "db_source_with": 772, "db_source_empty": 0,
    "db_comment_null": 744, "db_comment_filled": 28,
}
# Несуммируемые величины корпуса: по выгрузкам они не складываются (множество и максимум),
# поэтому считаются отдельно и сравниваются с отдельными эталонами (замеры 1.4, 2.3).
CORPUS_MAX_SOURCES = 789
CORPUS_HANDLER_DISTINCT = 468

# Таблица 2.2 плана мерилась по ДВУМ большим выгрузкам (BGU2 + BP3), а не по четырём: об этом
# говорит расхождение с итогом корпуса (11 919 / 6 002 / 3 249) ровно на записи MinCfg и KomMag
# (12 / 2 / 1). Проверка держит оба числа, потому что иначе одна из двух строк плана читалась
# бы ошибкой: здесь — строка таблицы 2.2, в CORPUS_TOTALS — строка четырёх выгрузок.
PLAN_CLASS_TABLE_TWO_DUMP_SCOPE = {
    "DocumentObject": 11907, "CatalogObject": 6000,
    "InformationRegisterRecordSet": 3248, "ConstantValueManager": 2130,
    "DocumentJournalManager": 27,
}
# Ключи эталона, относящиеся к независимой мере файлов, а не к строкам БД.
RAW_TOTAL_KEYS = (
    "files", "bytes", "subdirs", "non_xml",
    "props_block", "prop_tags_total", "prop_tags_distinct",
    "source_block", "source_items", "tag_Type", "tag_TypeSet",
    "target_named", "target_bare", "target_empty", "target_other", "typeset_named",
    "handler_total", "handler_segments", "handler_module_kind",
    "comment_empty", "comment_text",
)
RAW_PREFIX_KEYS = ("event_", "class_")
# Ключи, которые эталон называет, но мера файлов не даёт (строки БД, индекс, ответ разбора).
# `handler_distinct` — множество: по файлам оно не суммируется и не считается, его даёт
# распределение обработчиков по строкам таблицы (контур 4c, `db_handler_distinct`).
DERIVED_KEYS = ("index_rows", "index_children", "header_list", "header_is_null",
                "observations", "index_only", "file_only", "uuid_mismatch",
                "directory_missing", "sources_max_per_file", "handler_distinct")


# ── форма выдачи: PASS / FAIL / SKIP / INFO, отказ называется, а не обрывает прогон ─────────
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
    return text if len(text) <= 200 else text[:200] + "…"


def counts_diff(actual, expected, label, tag, ignore_prefixes=()):
    """Сравнивает Counter с эталоном по всем ключам эталона и лишним ключам факта.

    `ignore_prefixes` — ключи, которые эталон не перечисляет поимённо: полное распределение
    классов целей замкнуто константой слоя, и его контур 6 сравнивает меру файлов со строками
    БД, а не списком чисел.
    """
    wrong = []
    for key, want in expected.items():
        got = actual.get(key, 0)
        if got != want:
            wrong.append(f"{label} {key}: факт {got}, план {want}")
    extra = sorted(key for key, value in actual.items()
                   if key not in expected and value
                   and not key.startswith(ignore_prefixes))
    if extra:
        wrong.append(f"{label} вне эталона: " + names(extra))
    check(f"{tag}: {label} равны плану", not wrong, "; ".join(wrong))
    return not wrong


def raw_expectations(expect):
    """Ключи эталона, относящиеся к независимой мере файлов, а не к строкам БД."""
    return {key: value for key, value in expect.items()
            if key in RAW_TOTAL_KEYS or key.startswith(RAW_PREFIX_KEYS)}


def db_expectations(expect):
    """Ключи эталона, относящиеся к строкам двух таблиц (префикс `db_`)."""
    return {key: value for key, value in expect.items() if key.startswith("db_")}


def table_columns(cur, table):
    """Колонки таблицы по живой схеме.

    Список берётся из схемы, а не из памяти проверки: проверка обязана назвать колонку,
    которой нет, а не молча получить пустой словарь.
    """
    return [row["column_name"] for row in q(
        cur, "SELECT column_name FROM information_schema.columns WHERE table_name = %s "
             "ORDER BY ordinal_position", (table,))]


def table_check_constraints(cur, table, column):
    """Имена CHECK'ов живой схемы, упоминающих колонку, и значения её закрытого словаря.

    Литералы берутся только из CONSTRAINT'а замкнутости (имя оканчивается на `_known`):
    согласующие CHECK'ы (`*_matches_value`, `*_matches_state`) тоже перечисляют состояния, но
    в условиях связи колонок, и принимать их литералы за словарь — значит назвать словарём то,
    чем он не является. `pg_get_constraintdef` нормализует `IN (…)` в `= ANY (ARRAY[…])`,
    поэтому значения снимаются по литералам, а не по форме списка.
    """
    rows = q(cur, "SELECT conname, pg_get_constraintdef(oid) AS definition "
                  "FROM pg_constraint WHERE conrelid = %s::regclass "
                  "AND contype = 'c' AND pg_get_constraintdef(oid) LIKE %s",
             (table, f"%{column}%"))
    values = set()
    for row in rows:
        if not str(row["conname"]).endswith("_known"):
            continue
        for item in re.findall(r"'([^']*)'", str(row["definition"])):
            values.add(item)
    return [str(row["conname"]) for row in rows], values


def set_diff(label, left, right, tag):
    """Парное сравнение множеств имён — в обе стороны и поимённо."""
    missing = sorted(right - left)
    extra = sorted(left - right)
    ok = not missing and not extra
    detail = ""
    if missing:
        detail += f"есть только в правой части: {names(missing)}"
    if extra:
        detail += ("; " if detail else "") + f"есть только в левой части: {names(extra)}"
    check(f"{tag}: {label}", ok, detail)
    return ok


# Колонки-uuid нормализуются при сравнении: psycopg2 отдаёт uuid.UUID, разбор — строку.
def norm_value(column, value):
    if value is None:
        return None
    if column.endswith("_uuid"):
        return str(value).lower()
    return value


def read_subscription_rows(cur, cfg_uuid):
    """Строки CURRENT-состояния подписок этой конфигурации (полный набор колонок)."""
    return q(cur, f"SELECT * FROM {SUBSCRIPTIONS_VIEW} WHERE configuration_uuid = "
                  f"%(uuid)s::uuid ORDER BY object_name", {"uuid": str(cfg_uuid)})


def read_source_rows(cur, cfg_uuid):
    """Строки блока `Source` текущего состояния (витрина связкой по id ревизии вида, Q4)."""
    return q(cur, f"SELECT * FROM {SOURCES_VIEW} WHERE configuration_uuid = %(uuid)s::uuid "
                  f"ORDER BY subscription_full_name, ordinal", {"uuid": str(cfg_uuid)})


def read_header_name_list(cur, configuration_uuid):
    """Перечень имён вида из строки заголовка (`configurations.event_subscriptions`).

    Иначе сравнение множеств сравнивало бы один набор с самим собой: инвариант четырёх ног
    существует ровно потому, что источник здесь другой. NULL перечня — состояние «значения
    нет», оно возвращается отдельным признаком, а не пустым списком: «перечня нет» и
    «перечень пуст» — разные состояния выгрузки.
    """
    row = one(cur, "SELECT coalesce({column}, '{{}}'::text[]) AS names, "
                   "({column} IS NULL) AS is_null FROM configurations "
                   "WHERE uuid = %(uuid)s::uuid".format(column=HEADER_NAME_COLUMN),
             {"uuid": str(configuration_uuid)})
    return [str(item) for item in (row.get("names") or [])], bool(row.get("is_null"))


# ── независимая мера круга: регулярки по ТЕКСТУ файла регистрации ───────────────────────────
# Знание о состояниях разбора здесь отсутствует намеренно: мера обязана описывать файл, а не
# то, как его прочитал слой. Перечень тегов свойств замкнут константой модуля разбора
# (`XML_PROPERTY_NAMES`), второй перечень разъехался бы с первым при переименовании.
PROPS_BLOCK_RE = re.compile(r"<Properties>(.*?)</Properties>", re.S)
SOURCE_BLOCK_RE = re.compile(r"<Source>(.*?)</Source>", re.S)
TAG_PATTERNS = {name: re.compile(r"<%s[\s/>]" % re.escape(name))
                for name in XML_PROPERTY_NAMES}
RE_EVENT = re.compile(r"<Event>\s*(.*?)\s*</Event>", re.S)
RE_COMMENT = re.compile(r"<Comment>(.*?)</Comment>", re.S)
RE_COMMENT_SELF = re.compile(r"<Comment\s*/>")
RE_HANDLER = re.compile(r"<Handler>\s*(.*?)\s*</Handler>", re.S)
# Форма элемента блока — сам тег (`v8:Type` / `v8:TypeSet`, замер 2.2): атрибута `xsi:type`
# у него нет, в этом отличие от перечня `<Content>` узла V52.
RE_SOURCE_VALUE = {tag: re.compile(r"<v8:%s>\s*(.*?)\s*</v8:%s>" % (tag, tag), re.S)
                   for tag in SOURCE_TAGS}


def measure_file(text: str) -> Counter:
    """Меры одного файла регистрации — такие же, как у зонда `_v53_p6_counts_probe.py`."""
    c = Counter()
    props = PROPS_BLOCK_RE.search(text)
    props_text = props.group(1) if props else ""
    c["props_block"] = 1 if props else 0
    for name, pattern in TAG_PATTERNS.items():
        c["prop_tag_%s" % name] = len(pattern.findall(props_text))
    c["prop_tags_total"] = sum(c["prop_tag_%s" % n] for n in XML_PROPERTY_NAMES)
    c["prop_tags_distinct"] = sum(1 for n in XML_PROPERTY_NAMES if c["prop_tag_%s" % n])
    for value in RE_EVENT.findall(props_text):
        c["event_" + value] += 1
    comment = RE_COMMENT.search(props_text)
    if comment:
        c["comment_empty" if not comment.group(1).strip() else "comment_text"] += 1
    # Самозакрывающийся тег — тоже пустое значение (в BGU2 таких 297 файлов из 311): мера,
    # которая их не видит, описывала бы «комментариев нет», а не «комментарий пустой».
    c["comment_empty"] += len(RE_COMMENT_SELF.findall(props_text))
    for value in RE_HANDLER.findall(props_text):
        c["handler_total"] += 1
        segments = [part for part in value.split(".") if part]
        if len(segments) == HANDLER_SEGMENT_COUNT:
            c["handler_segments"] += 1
        if segments and segments[0] == HANDLER_MODULE_KIND:
            c["handler_module_kind"] += 1
    source = SOURCE_BLOCK_RE.search(text)
    source_text = source.group(1) if source else ""
    c["source_block"] = 1 if source else 0
    for tag, pattern in RE_SOURCE_VALUE.items():
        values = pattern.findall(source_text)
        c["tag_%s" % tag] = len(values)
        c["source_items"] += len(values)
        for value in values:
            body = value[len(CFG_PREFIX) + 1:] if value.startswith(CFG_PREFIX + ":") else ""
            if body:
                if "." in body:
                    c["target_named"] += 1
                    if tag == "TypeSet":
                        c["typeset_named"] += 1
                else:
                    c["target_bare"] += 1
                c["class_" + body.split(".")[0]] += 1
            elif value:
                c["target_other"] += 1
            else:
                c["target_empty"] += 1
    return c


def _iter_files(root: Path):
    """Файлы круга — тот же обход, что делает слой (сторож примитивности смотрит тот же круг)."""
    directory = root / DIR_NAME
    if not directory.exists():
        return [], [("directory_missing", DIR_NAME)]
    files = []
    observations = []
    for entry in sorted(directory.rglob("*")):
        if entry.is_dir():
            observations.append(("unexpected_dir", entry.name))
            continue
        if entry.suffix.lower() != ".xml":
            observations.append(("unexpected_file", entry.name))
            continue
        files.append({"path": entry, "file_name": entry.name})
    return files, observations


def raw_measures(dump_dir):
    """Подсчёт по тексту файлов вида: итоги, меры по каждому файлу, максимум записей блока."""
    entries, observations = _iter_files(Path(dump_dir))
    totals = Counter()
    per_name = {}
    unreadable = []
    max_sources = 0
    for entry in entries:
        text, reason = read_text_file(Path(entry["path"]))
        if text is None:
            unreadable.append((entry["file_name"], reason))
            continue
        counts = measure_file(text)
        counts["bytes"] = Path(entry["path"]).stat().st_size
        per_name[Path(entry["file_name"]).stem] = counts
        max_sources = max(max_sources, counts["source_items"])
        for key, value in counts.items():
            totals[key] += value
    totals["files"] = len(entries)
    totals["unreadable_files"] = len(unreadable)
    directory = Path(dump_dir) / DIR_NAME
    totals["subdirs"] = 0
    totals["non_xml"] = 0
    if directory.is_dir():
        totals["subdirs"] = len([p for p in directory.rglob("*") if p.is_dir()])
        totals["non_xml"] = len([p for p in directory.rglob("*")
                                 if p.is_file() and p.suffix.lower() != ".xml"])
    for kind, _detail in observations:
        totals["obs_" + kind] += 1
    return totals, per_name, max_sources, unreadable, observations


def parse_circle(dump_dir, index_rows, common_module_names):
    """Разобрать круг ТЕМ ЖЕ модулем, что и загрузка.

    Сравнение строки с файлом идёт по разбору, а не по второй реализации чтения XML: иначе
    проверка проверяла бы саму себя, а не то, донёс ли писатель строку.
    """
    return collect_event_subscriptions(Path(dump_dir), index_rows, common_module_names)


def index_aggregates(cur, configuration_id):
    """Две меры записей индекса состава: агрегатным COUNT и построчным обходом (приём V48).

    Своего вида считается одно число (`EventSubscription.<Имя>`): в отличие от V51 и V52, у
    вида нет детей (замер 1.2, M2), поэтому второй ноги круга здесь нет — и ноль детей является
    проверяемым утверждением, а не отсутствием запроса.
    """
    aggregate = int(one(cur, "SELECT count(*) AS c FROM configuration_objects "
                             "WHERE configuration_id = %s AND object_type = %s "
                             "AND (child_type IS NULL OR child_type = '')",
                        (int(configuration_id), INDEX_OBJECT_TYPE)).get("c") or 0)
    children = int(one(cur, "SELECT count(*) AS c FROM configuration_objects "
                             "WHERE configuration_id = %s AND object_type = %s "
                             "AND child_type IS NOT NULL AND child_type <> ''",
                       (int(configuration_id), INDEX_OBJECT_TYPE)).get("c") or 0)
    return aggregate, children


def dump_newer_than_rows(dump_dir, subscription_rows):
    """True, если файлы круга новее строк узла (правило R5); None — если мерить нечем."""
    stamps = [row["changed_at"] for row in subscription_rows if row.get("changed_at")]
    if not stamps:
        return None
    directory = Path(dump_dir) / DIR_NAME
    if not directory.is_dir():
        return None
    newest_file = max((item.stat().st_mtime for item in directory.rglob("*")
                      if item.is_file()), default=None)
    if newest_file is None:
        return None
    return newest_file > max(stamp.timestamp() for stamp in stamps)


# ── контур 1: граница круга — файл, индекс состава, перечень заголовка, строки таблицы ──────
def check_circle(cur, header, dump_dir, index_info, expect, tag):
    """Четыре независимых источника имени подписки сверяются попарно во все стороны."""
    cfg_uuid = str(header["uuid"])
    section(f"Контур 1 — граница круга ({tag})")

    entries, observations = _iter_files(Path(dump_dir))
    file_stems = {Path(entry["file_name"]).stem for entry in entries}
    check(f"{tag}: файлов вида найдено {expect['files']}",
          len(entries) == expect["files"],
          f"факт: {len(entries)}, план: {expect['files']}")

    index_rows = index_info["rows"]
    kind_rows = kind_index_rows(index_rows)
    index_names = {index_row_key(row)[len(INDEX_OBJECT_TYPE) + 1:]
                   for row in kind_rows if index_row_key(row)}
    aggregate, children = index_aggregates(cur, int(header["id"]))
    check(f"{tag}: записей индекса состава вида — {expect['index_rows']} (агрегатным COUNT и "
          f"построчным обходом — две меры)",
          aggregate == expect["index_rows"] and len(kind_rows) == expect["index_rows"],
          f"COUNT: {aggregate}, обход: {len(kind_rows)}, план: {expect['index_rows']}")
    check(f"{tag}: дочерних записей индекса вида — {expect['index_children']} "
          "(у вида нет детей, замер 1.2, M2)",
          children == expect["index_children"], f"факт: {children}")
    check(f"{tag}: наблюдений о структуре каталога — {expect['observations']} "
          "(подкаталогов и файлов не-XML у вида нет, замер 1.2)",
          len(observations) == expect["observations"], _brief(observations))

    header_names, header_is_null = read_header_name_list(cur, cfg_uuid)
    check(f"{tag}: перечень заголовка `configurations.{HEADER_NAME_COLUMN}` — "
          f"{expect['header_list']} имён (узел V43, третья независимая нога)",
          len(header_names) == expect["header_list"] and
          bool(header_is_null) == bool(expect["header_is_null"]),
          f"факт: {len(header_names)}, null: {header_is_null}, "
          f"план: {expect['header_list']}, null: {expect['header_is_null']}")

    subscription_rows = read_subscription_rows(cur, cfg_uuid)
    db_names = {str(row["object_name"]) for row in subscription_rows}
    check(f"{tag}: строк вида в таблице `{TABLE_NAME}` — {expect['db_rows']}",
          len(subscription_rows) == expect["db_rows"],
          f"факт: {len(subscription_rows)}, план: {expect['db_rows']}")

    set_diff("каталог файлов ↔ записи индекса состава (имена)", file_stems, index_names, tag)
    set_diff("записи индекса ↔ перечень заголовка (имена)", index_names,
             {str(name) for name in header_names}, tag)
    set_diff("перечень заголовка ↔ строки таблицы (имена)",
             {str(name) for name in header_names}, db_names, tag)
    set_diff("строки таблицы ↔ каталог файлов (имена)", db_names, file_stems, tag)

    # Расхождения двух ног названы ответом разбора, а не молчанием: нули являются утверждением
    # о выгрузке (замер 1.1), и проверка обязана его подтвердить.
    parsed_probe = collect_event_subscriptions(Path(dump_dir), index_rows)
    check(f"{tag}: расхождений круга нет — `index_only` {expect['index_only']}, "
          f"`file_only` {expect['file_only']}, `uuid_mismatch` {expect['uuid_mismatch']}",
          len(parsed_probe["index_only"]) == expect["index_only"] and
          len(parsed_probe["file_only"]) == expect["file_only"] and
          len(parsed_probe["uuid_mismatch"]) == expect["uuid_mismatch"],
          f"index_only: {names(parsed_probe['index_only'])}; file_only: "
          f"{names(parsed_probe['file_only'])}; uuid_mismatch: "
          f"{_brief(parsed_probe['uuid_mismatch'])}")
    kinds = Counter(kind for kind, _detail in parsed_probe["observations"])
    check(f"{tag}: наблюдений о круге — {expect['observations']} "
          f"(`directory_missing` — {expect['directory_missing']})",
          sum(kinds.values()) == expect["observations"] and
          kinds.get("directory_missing", 0) == expect["directory_missing"],
          _brief(dict(kinds)))
    return {"file_stems": file_stems, "index_names": index_names,
            "index_children": children, "header_names": header_names,
            "header_is_null": header_is_null, "subscription_rows": subscription_rows,
            "db_names": db_names}


# ── контур 2: строка вида ↔ разбор того же файла ───────────────────────────────────────────
def check_subscription_rows(parsed, subscription_rows, subscription_columns, tag):
    """Каждая колонка строки равна значению, которое даёт разбор того же файла."""
    section(f"Контур 2 — строка вида ↔ разбор ({tag})")
    rows_by_name = {str(row["object_name"]): row for row in subscription_rows}
    parse_rows = {str(row["object_name"]): row for row in parsed["rows"]}
    set_diff("разбор ↔ строки таблицы (набор имён)", set(parse_rows), set(rows_by_name), tag)

    parse_keys = set()
    for row in parse_rows.values():
        parse_keys.update(row)
    fields = sorted((set(subscription_columns) & parse_keys) - set(REVISION_COLUMNS))
    mismatched = []
    for name, parse_row in sorted(parse_rows.items()):
        db_row = rows_by_name.get(name)
        if db_row is None:
            continue
        for field in fields:
            if field not in parse_row:
                continue
            db_value = norm_value(field, db_row.get(field))
            parse_value = norm_value(field, parse_row.get(field))
            if db_value != parse_value:
                mismatched.append(f"{name}.{field}: строка {_brief(db_value)} ≠ "
                                  f"разбор {_brief(parse_value)}")
    check(f"{tag}: каждая колонка строки равна разбору того же файла "
          f"(полей сравнения: {len(fields)})", not mismatched, names(mismatched))

    # Состояния строки называются словарём, а не нулём счётчика.
    states_wrong = []
    for name, db_row in sorted(rows_by_name.items()):
        if db_row["properties_state"] not in PROPERTIES_STATES:
            states_wrong.append(f"{name}: properties_state {db_row['properties_state']!r}")
        if db_row["event_state"] not in EVENT_STATES:
            states_wrong.append(f"{name}: event_state {db_row['event_state']!r}")
        if db_row["handler_state"] not in HANDLER_STATES:
            states_wrong.append(f"{name}: handler_state {db_row['handler_state']!r}")
        if db_row["source_state"] not in SOURCE_STATES:
            states_wrong.append(f"{name}: source_state {db_row['source_state']!r}")
        if (db_row["properties_state"] == PROPERTIES_ALL_KNOWN) == bool(
                db_row["unknown_property_names"] or []):
            states_wrong.append(f"{name}: состояние свойств и перечень виновников разошлись")
    check(f"{tag}: состояния строки — из замкнутых словарей слоя, виновники названы",
          not states_wrong, names(states_wrong))
    return rows_by_name, parse_rows


# ── контур 3: ключ разбора ↔ колонки живой схемы ───────────────────────────────────────────
def check_key_shape(cur, parsed, tag):
    """Числа колонок (эталон П1) и сверка ключей разбора с колонками — в обе стороны.

    Строка разбора не носит ключей, которым нет колонки (это сказано в комментарии слоя), а
    колонка, которую слой не заполняет, обязана быть названа: иначе «колонка есть, данных
    нет» читалось бы как «данных в выгрузке нет».
    """
    section(f"Контур 3 — ключ разбора ↔ колонки схемы ({tag})")
    for table, want in EXPECTED_COLUMN_COUNTS.items():
        got = table_columns(cur, table)
        check(f"{tag}: колонок таблицы `{table}` — {want} (эталон шага П1)",
              len(got) == want, f"колонок: {len(got)}, план: {want}")

    subscription_columns = set(table_columns(cur, TABLE_NAME))
    source_columns = set(table_columns(cur, SOURCES_TABLE))
    if not parsed["rows"]:
        # Пустой круг: сравнивать ключ разбора с колонками нечем. Это называется пропуском,
        # а не PASS: «ключей нет» у пустого круга — состояние выгрузки, а не подтверждение
        # формы строки.
        skip(f"{tag}: ключ строки разбора и колонки `{TABLE_NAME}`",
             "файлов вида в выгрузке нет — формы строки разбора не существует, сравнивать "
             "не с чем; числа колонок проверены выше")
        skip(f"{tag}: ключ строки блока `Source` и колонки `{SOURCES_TABLE}`",
             "строк источника в разборе нет — того же круга")
    else:
        parse_keys = set()
        for row in parsed["rows"]:
            parse_keys.update(row)
        content_columns = subscription_columns - set(REVISION_COLUMNS)
        missing = sorted(parse_keys - content_columns)
        unfilled = sorted(content_columns - parse_keys)
        check(f"{tag}: ключ строки разбора и колонки `{TABLE_NAME}` совпадают",
              not missing and not unfilled,
              f"ключей без колонки: {names(missing)}; "
              f"колонок без значения разбора: {names(unfilled)}")

        source_keys = set()
        for row in parsed["source_rows"]:
            source_keys.update(row)
        source_expected = (source_columns - set(REVISION_COLUMNS)
                           - set(SOURCE_WRITER_COLUMNS))
        missing = sorted(source_keys - source_expected)
        unfilled = sorted(source_expected - source_keys)
        check(f"{tag}: ключ строки блока `Source` и колонки `{SOURCES_TABLE}` совпадают",
              not missing and not unfilled,
              f"ключей без колонки: {names(missing)}; "
              f"колонок без значения разбора: {names(unfilled)}")

    # Отличие от V50/V51/V52 названо прямо: плейсхолдеров словаря свойств здесь нет. Тег
    # `Source` является второй таблицей пары, а не колонкой строки вида, поэтому замкнутость
    # перечня плейсхолдеров сверять не с чем — проверяется именно их отсутствие.
    placeholder_like = ((set(XML_PROPERTY_NAMES) | set(SOURCE_TAGS))
                        & subscription_columns)
    check(f"{tag}: плейсхолдеров словаря свойств в колонках `{TABLE_NAME}` нет "
          "(блок `Source` — вторая таблица пары, а не колонка)",
          not placeholder_like, _brief(sorted(placeholder_like)))
    check(f"{tag}: тегов словаря свойств — {len(XML_PROPERTY_NAMES)} (из них `Source` уходит "
          f"в свою таблицу, остальных {len(XML_PROPERTY_NAMES) - 1} заполняет строка вида)",
          len(XML_PROPERTY_NAMES) == 6, f"тегов словаря: {len(XML_PROPERTY_NAMES)}")


# ── контур 4: строки блока `Source` ↔ файл и независимая мера ──────────────────────────────
def parse_source_key(row):
    """Ключ записи блока по разбору — (порядок, тег, значение как в выгрузке).

    Порядок (`ordinal`) входит в ключ, потому что один и тот же текст цели встречается в
    файле несколько раз (замер 1.4: до 789 записей в одном файле), а проверка обязана
    отвечать на вопрос «какая именно запись пропущена», а не «сколько пропущено».
    """
    return (int(row["ordinal"]), str(row["source_tag"]), str(row["target_raw"]))


def check_source_rows(cur, parsed, header, expect, tag):
    """Строки источника против разбора: набор, порядок, счётчик, связь с родителем."""
    section(f"Контур 4 — строки блока `Source` ↔ строки таблицы ({tag})")
    cfg_uuid = str(header["uuid"])
    source_rows = read_source_rows(cur, cfg_uuid)
    check(f"{tag}: строк блока `Source` в таблице `{SOURCES_TABLE}` — {expect['db_sources']}",
          len(source_rows) == expect["db_sources"],
          f"факт: {len(source_rows)}, план: {expect['db_sources']}")

    parsed_by_parent = {}
    for row in parsed["source_rows"]:
        parsed_by_parent.setdefault(str(row["subscription_full_name"]), []).append(row)
    db_by_parent = {}
    for row in source_rows:
        db_by_parent.setdefault(str(row["subscription_full_name"]), []).append(row)
    set_diff("разбор ↔ строки таблицы (имена подписок-родителей)",
             set(parsed_by_parent), set(db_by_parent), tag)

    # 4.1 Набор записей каждой подписки: разбор ↔ строки таблицы.
    mismatched = []
    for full_name, parse_rows in sorted(parsed_by_parent.items()):
        db_rows = db_by_parent.get(full_name, [])
        left = {parse_source_key(row) for row in parse_rows}
        right = {parse_source_key(row) for row in db_rows}
        if left != right:
            only_parse = sorted(left - right)
            only_db = sorted(right - left)
            mismatched.append(f"{full_name}: только в разборе {names(only_parse)}, "
                              f"только в строках {names(only_db)}")
    check(f"{tag}: каждая запись блока равна строке таблицы "
          f"((ordinal, тег, `target_raw`) — по всем подпискам)", not mismatched,
          names(mismatched))

    # 4.2 Порядок записей: 0..n-1 без пропусков и повторов. Уникальность держит и индекс
    # `uq_event_subscription_sources_row` (контур 9), но сам порядок проверяется здесь.
    order_wrong = []
    for full_name, db_rows in sorted(db_by_parent.items()):
        ordinals = sorted(int(row["ordinal"]) for row in db_rows)
        if ordinals != list(range(len(ordinals))):
            order_wrong.append(f"{full_name}: ordinal {names(ordinals[:8])} "
                               f"при {len(ordinals)} записях")
    check(f"{tag}: ordinal строк — 0..n-1 без пропусков и повторов", not order_wrong,
          names(order_wrong))

    # 4.3 Счётчик строки вида равен числу её строк источника: CHECK схемы сверяет число с
    # состоянием, здесь — с фактическим числом дочерних строк.
    rows_by_full_name = {str(row["full_name"]): row for row in
                         read_subscription_rows(cur, cfg_uuid)}
    counter_wrong = []
    for full_name, db_row in sorted(rows_by_full_name.items()):
        count = len(db_by_parent.get(full_name, []))
        if int(db_row["source_count"]) != count:
            counter_wrong.append(f"{full_name}: source_count {db_row['source_count']} ≠ "
                                 f"строк источника {count}")
    check(f"{tag}: `source_count` строки вида равен числу её строк источника",
          not counter_wrong, names(counter_wrong))
    return {"source_rows": source_rows, "db_by_parent": db_by_parent,
            "rows_by_full_name": rows_by_full_name}


def class_expectations(expect):
    """Только те классы целей, которые эталон называет поимённо (остальные замкнуты слоем)."""
    return {key: value for key, value in expect.items() if key.startswith("class_")}


def group_by(rows, key):
    grouped = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(row)
    return grouped


# Колонка состояния разрешения ↔ ключ эталона: одно соответствие, из которого строятся и
# эталон, и факт (два перечня разъехались бы при переименовании состояния).
RESOLVE_KEYS = ((RESOLVE_EXACT, "exact"), (RESOLVE_TYPE_PRESENT, "type_present"),
                (RESOLVE_TYPE_ABSENT, "type_absent"), (RESOLVE_UNRESOLVED, "unresolved"),
                (RESOLVE_UNKNOWN_CLASS, "unknown_class"),
                (RESOLVE_EMPTY_VALUE, "empty_value"), (RESOLVE_UNKNOWN_FORM, "unknown_form"))
HANDLER_KEYS = ((HANDLER_STATE_EXACT, "exact"), ("unresolved", "unresolved"),
                ("unknown_form", "unknown_form"))


def check_raw_measures(raw_totals, max_sources, unreadable, expect, tag):
    """Сравнение независимой меры файлов с эталоном.

    Мера не знает о состояниях разбора, поэтому расхождение меры с эталоном означает, что
    изменилась выгрузка, а расхождение меры со строками — что загрузка донесла не то.
    """
    section(f"Контур 4b — независимая мера файлов ({tag})")
    # `class_` — распределение, замкнутое словарём слоя: эталон называет поимённо только те
    # классы, которые перечисляет таблица 2.2 плана, полное распределение сравнивается в
    # контуре 6 (мера файлов ↔ строки таблицы) и в контуре 12 (итог корпуса по 30 классам).
    counts_diff(raw_totals, raw_expectations(expect), "мера файлов", tag,
                ignore_prefixes=("obs_", "prop_tag_", "class_"))
    check(f"{tag}: файлов круга прочитано без ошибок ({expect['files']}), "
          f"непрочитанных — {len(unreadable)}",
          len(unreadable) == 0 and raw_totals["files"] == expect["files"],
          _brief(names([name for name, _reason in unreadable])))
    check(f"{tag}: максимум записей блока `Source` в одном файле — "
          f"{expect['sources_max_per_file']} (мера 1.4: строка обязана выдерживать такой "
          f"круг)", max_sources == expect["sources_max_per_file"],
          f"факт: {max_sources}, план: {expect['sources_max_per_file']}")


def check_db_distributions(source_rows, subscription_rows, expect, tag):
    """Распределения состояний и словарей по СТРОКАМ таблицы против эталона."""
    section(f"Контур 4c — распределения по строкам ({tag})")
    resolve = Counter(str(row["target_resolve_state"]) for row in source_rows)
    counts_diff({"db_resolve_" + key: value for key, value in resolve.items()},
                {"db_resolve_" + suffix: expect["db_resolve_" + suffix]
                 for _state, suffix in RESOLVE_KEYS},
                "состояния разрешения целей", tag)
    forms = Counter("target_" + str(row["target_form"]) for row in source_rows)
    counts_diff(forms, {"target_named": expect["target_named"],
                        "target_bare": expect["target_bare"],
                        "target_empty": expect["target_empty"],
                        "target_other": expect["target_other"]},
                "формы значения цели", tag)
    tags = Counter("tag_" + str(row["source_tag"]) for row in source_rows)
    counts_diff(tags, {"tag_Type": expect["tag_Type"], "tag_TypeSet": expect["tag_TypeSet"]},
                "теги элемента блока (по строкам)", tag)
    classes = Counter("class_" + str(row["target_class"]) for row in source_rows
                      if row.get("target_class"))
    counts_diff(classes, class_expectations(expect), "классы целей (по строкам)", tag,
                ignore_prefixes=("class_",))

    handlers = Counter(str(row["handler_state"]) for row in subscription_rows)
    counts_diff({"db_handler_" + key: value for key, value in handlers.items()},
                {"db_handler_" + suffix: expect["db_handler_" + suffix]
                 for _state, suffix in HANDLER_KEYS},
                "состояния обработчика", tag)
    properties = Counter(str(row["properties_state"]) for row in subscription_rows)
    counts_diff({"db_properties_all_known": properties.get(PROPERTIES_ALL_KNOWN, 0),
                 "db_properties_unknown": sum(
                     value for key, value in properties.items()
                     if key != PROPERTIES_ALL_KNOWN)},
                {"db_properties_all_known": expect["db_properties_all_known"],
                 "db_properties_unknown": expect["db_properties_unknown"]},
                "состояния свойств", tag)
    source_states = Counter(str(row["source_state"]) for row in subscription_rows)
    counts_diff({"db_source_with": source_states.get(SOURCE_STATE_WITH, 0),
                 "db_source_empty": source_states.get(SOURCE_STATE_EMPTY, 0)},
                {"db_source_with": expect["db_source_with"],
                 "db_source_empty": expect["db_source_empty"]},
                "состояния блока `Source`", tag)
    comment_null = sum(1 for row in subscription_rows if row.get("comment") is None)
    counts_diff({"db_comment_null": comment_null,
                 "db_comment_filled": len(subscription_rows) - comment_null},
                {"db_comment_null": expect["db_comment_null"],
                 "db_comment_filled": expect["db_comment_filled"]},
                "заполненность комментария (пустой тег — NULL, Q7 вариант A)", tag)

    max_sources = max((len(rows) for rows in
                       group_by(source_rows, "subscription_full_name").values()), default=0)
    distinct_classes = len({str(row["target_class"]) for row in source_rows
                            if row.get("target_class")})
    distinct_handlers = len({str(row["handler"]) for row in subscription_rows
                             if row.get("handler")})
    counts_diff({"db_max_sources": max_sources,
                 "db_distinct_classes": distinct_classes,
                 "db_handler_distinct": distinct_handlers},
                {"db_max_sources": expect["db_max_sources"],
                 "db_distinct_classes": expect["db_distinct_classes"],
                 "db_handler_distinct": expect["db_handler_distinct"]},
                "максимум строк на подписку, число классов и уникальных обработчиков", tag)


# ── контур 5: разрешимость целей — разрешение вызывается ЗАНОВО (приём V52) ─────────────────
def check_target_resolution(cur, header, source_rows, index_info, tag):
    """Каждая сохранённая цель разрешается повторно строками индекса состава этой ИБ.

    Разрешение вызывается проверкой повторно (`resolve_target_entry`), а состояние,
    `target_object_id`, `target_object_uuid` и остаток пути сравниваются с сохранёнными:
    иначе проверка утверждала бы, что «в БД лежит то, что посчитал слой», не показывая,
    пересобирается ли вывод из строк индекса.
    """
    section(f"Контур 5 — разрешимость целей ({tag})")
    if not source_rows:
        skip(f"{tag}: повторное разрешение целей",
             "строк блока `Source` в этой выгрузке нет — разрешать нечего")
        return
    index_by_name = index_rows_by_name(index_info["rows"])
    meta_types = index_meta_types(index_info["rows"])
    mismatched = []
    for row in source_rows:
        entry = {
            "ordinal": int(row["ordinal"]),
            "source_tag": str(row["source_tag"]),
            "target_raw": str(row["target_raw"]),
            "target_class": str(row["target_class"] or ""),
            "target_meta_type": row["target_meta_type"],
            "target_object_name": row["target_object_name"],
            "target_full_name": str(row["target_full_name"] or ""),
            "target_form": str(row["target_form"]),
            "reason": None,
        }
        resolve_target_entry(entry, index_by_name, meta_types)
        for column in ("target_resolve_state", "target_object_id", "target_object_uuid",
                       "target_unresolved_path"):
            if norm_value(column, row.get(column)) != norm_value(column, entry.get(column)):
                mismatched.append(
                    f"{row['subscription_full_name']}#{row['ordinal']}.{column}: "
                    f"строка {_brief(row.get(column))} ≠ повторное разрешение "
                    f"{_brief(entry.get(column))}")
    check(f"{tag}: повторное разрешение цели совпадает с сохранённым состоянием и ссылкой "
          f"(строк проверки: {len(source_rows)})", not mismatched, names(mismatched))

    # Голая цель (`cfg:<Класс>`) разрешается состоянием присутствия вида в индексе этой
    # конфигурации (M5): проверка считает присутствие независимо — по строкам таблицы
    # `configuration_objects`, а не по множеству, которое построил слой.
    present_sql = q(cur, "SELECT DISTINCT object_type FROM configuration_objects "
                         "WHERE configuration_id = %s AND (child_type IS NULL OR "
                         "child_type = '')", (int(header["id"]),))
    present_types = {str(row["object_type"]) for row in present_rows_guard(present_sql)}
    bare_wrong = []
    for row in source_rows:
        if str(row["target_form"]) != TARGET_FORM_BARE:
            continue
        meta_type = row["target_meta_type"]
        want = RESOLVE_TYPE_PRESENT if str(meta_type) in present_types else RESOLVE_TYPE_ABSENT
        if str(row["target_resolve_state"]) != want:
            bare_wrong.append(f"{row['subscription_full_name']}#{row['ordinal']}: "
                              f"{row['target_resolve_state']} при виде {meta_type} "
                              f"(по строкам индекса: {want})")
    check(f"{tag}: голая цель получает `type_present`/`type_absent` по присутствию вида в "
          f"индексе (M5; независимая мера — таблица `configuration_objects`)",
          not bare_wrong, names(bare_wrong))
    bare_present = sum(1 for row in source_rows
                       if str(row["target_form"]) == "bare"
                       and str(row["target_resolve_state"]) == RESOLVE_TYPE_PRESENT)
    bare_absent = sum(1 for row in source_rows
                      if str(row["target_form"]) == "bare"
                      and str(row["target_resolve_state"]) == RESOLVE_TYPE_ABSENT)
    check(f"{tag}: голых целей — {bare_present} `type_present` и {bare_absent} `type_absent`, "
          f"сумма равна числу голых целей (строка 2.2 плана: 242/23 на корпусе)",
          bare_present + bare_absent == sum(1 for row in source_rows
                                            if str(row["target_form"]) == TARGET_FORM_BARE),
          f"present: {bare_present}, absent: {bare_absent}")


def present_rows_guard(rows):
    """Строки видов, которые конфигурация действительно содержит (защита от пустого ответа)."""
    return [row for row in rows if row.get("object_type")]


# ── контур 6: словари имён событий и классов целей + разрешение обработчика ─────────────────
def check_dictionaries(cur, header, source_rows, subscription_rows, raw_totals, expect, tag):
    """Значения двух замкнутых словарей и разрешение модуля обработчика."""
    section(f"Контур 6 — словари и разрешение обработчика ({tag})")

    events = Counter(str(row["event"]) for row in subscription_rows)
    outside_dictionary = sorted(name for name in events if name not in EVENT_NAME_DICTIONARY)
    check(f"{tag}: значения `<Event>` входят в закрытый словарь имён "
          f"(словарь — {len(EVENT_NAME_DICTIONARY)} имён, различных значений — "
          f"{len(events)})", not outside_dictionary, names(outside_dictionary))
    check(f"{tag}: каждое имя словаря помечено состоянием `known` (замер 2.1: новых имён "
          f"выгрузка не давала)",
          all(str(row["event_state"]) == EVENT_STATE_KNOWN for row in subscription_rows),
          _brief(Counter(str(row["event_state"]) for row in subscription_rows)))
    counts_diff({"event_" + key: value for key, value in events.items()},
                {key: value for key, value in expect.items() if key.startswith("event_")},
                "распределение имён событий (по строкам ↔ таблица 2.1)", tag)
    counts_diff({key: value for key, value in raw_totals.items()
                 if key.startswith("event_")},
                {key: value for key, value in expect.items() if key.startswith("event_")},
                "распределение имён событий (мера файлов ↔ таблица 2.1)", tag)

    # Классы целей: словарь замкнут константой слоя, поэтому проверяется и принадлежность, и
    # то, что `target_meta_type` равен значению словаря (иначе словарь есть, а связи нет).
    class_wrong = []
    for row in source_rows:
        klass = str(row["target_class"] or "")
        if klass not in SOURCE_CLASS_META_TYPES:
            class_wrong.append(f"{row['subscription_full_name']}#{row['ordinal']}: класс "
                               f"{klass!r} вне словаря {len(SOURCE_CLASS_META_TYPES)} записей")
            continue
        if str(row["target_meta_type"]) != str(SOURCE_CLASS_META_TYPES[klass]):
            class_wrong.append(f"{row['subscription_full_name']}#{row['ordinal']}: "
                               f"target_meta_type {row['target_meta_type']!r} ≠ словарю "
                               f"{SOURCE_CLASS_META_TYPES[klass]!r}")
    check(f"{tag}: класс цели и вид метаданных соответствуют словарю "
          f"`SOURCE_CLASS_META_TYPES` ({len(SOURCE_CLASS_META_TYPES)} записей)",
          not class_wrong, names(class_wrong))
    # Мера файлов и строки таблицы дают одно и то же распределение классов — это и есть та
    # сверка, которая показывает, что таблица 2.2 плана мерилась по двум выгрузкам.
    from_files = {key: value for key, value in raw_totals.items()
                  if key.startswith("class_")}
    from_rows = Counter("class_" + str(row["target_class"]) for row in source_rows
                        if row.get("target_class"))
    check(f"{tag}: распределение классов целей мерой файлов равно распределению по строкам "
          f"(классов: {len(from_files)} / {len(from_rows)})",
          dict(from_files) == dict(from_rows),
          _brief(sorted(set(from_files.items()) ^ set(from_rows.items()))[:12]))


def check_handler_resolution(cur, header, subscription_rows, common_module_names, tag):
    """Разрешение модуля обработчика — ЗАНОВО, перечнем общих модулей текущей ревизии."""
    section(f"Контур 6b — разрешение обработчика ({tag})")
    if not subscription_rows:
        skip(f"{tag}: повторное разрешение обработчика",
             "строк вида в этой выгрузке нет — разрешать нечего")
        return
    names_set = set(common_module_names or ())
    wrong = []
    for row in sorted(subscription_rows, key=lambda item: str(item["full_name"])):
        handler = {"handler": row["handler"], "handler_module": row["handler_module"],
                   "handler_method": row["handler_method"],
                   "handler_state": None if str(row["handler_state"]) in
                   (HANDLER_STATE_EXACT, HANDLER_STATE_UNRESOLVED)
                   else str(row["handler_state"])}
        want = resolve_handler_state(handler, names_set)
        if str(row["handler_state"]) != want:
            wrong.append(f"{row['full_name']}: {row['handler_state']} ≠ повторное "
                         f"разрешение {want}")
    check(f"{tag}: состояние обработчика совпадает с повторным разрешением перечнем "
          f"`{COMMON_MODULES_VIEW}` (строк: {len(subscription_rows)})", not wrong,
          names(wrong))
    check(f"{tag}: модуль и метод разложены из текста обработчика "
          f"(`{HANDLER_MODULE_KIND}.<Модуль>.<Метод>`, замер 2.3)",
          all(str(row["handler"]).startswith(HANDLER_MODULE_KIND + ".") and
              row["handler_module"] and row["handler_method"] and
              f"{row['handler_module']}.{row['handler_method']}" ==
              ".".join(str(row["handler"]).split(".")[1:])
              for row in subscription_rows),
          names([str(row["full_name"]) for row in subscription_rows
                 if not (row["handler_module"] and row["handler_method"])]))





# ── контур 8: пустой круг (отсутствующий каталог вида) — проверяется на фикстуре ────────────
def check_missing_directory():
    """Состояние «каталога вида нет» не встречается ни в одной эталонной выгрузке.

    Замер 1.1 даёт каталог во всех четырёх (KomMag — один файл), поэтому состояние нельзя
    подтвердить прогоном корпуса: оно проверяется на пустой фикстуре. Это не отказ: у
    конфигурации без подписок их действительно нет (прецедент KomMag для V50), и ответ обязан
    быть успешным с названным наблюдением.
    """
    section("Контур 8 — пустой круг (фикстура отсутствующего каталога)")
    with tempfile.TemporaryDirectory(prefix="v53_empty_") as tmp:
        parsed = collect_event_subscriptions(tmp, [])
    kinds = Counter(kind for kind, _detail in parsed["observations"])
    check("фикстура без каталога вида: ответ успешный, `files_found` — 0, строк нет, "
          "наблюдение `directory_missing` названо",
          parsed["success"] is True and parsed["files_found"] == 0
          and parsed["rows"] == [] and parsed["source_rows"] == []
          and kinds.get("directory_missing") == 1,
          f"success: {parsed['success']}, files_found: {parsed['files_found']}, "
          f"observations: {_brief(dict(kinds))}")
    check("фикстура без каталога вида: расхождений двух ног нет — `index_only`, `file_only`, "
          "`uuid_mismatch` пусты",
          not parsed["index_only"] and not parsed["file_only"]
          and not parsed["uuid_mismatch"],
          _brief({key: parsed[key] for key in ("index_only", "file_only", "uuid_mismatch")}))


# ── контур 9: живая схема — ключи, индексы, витрины, замкнутость словарей ───────────────────
EXPECTED_UNIQUE_KEYS = {
    TABLE_NAME: ["event_subscriptions_configuration_object_revision_key"],
    SOURCES_TABLE: ["event_subscription_sources_subscription_ordinal_key"],
}
EXPECTED_INDEXES = [
    "idx_event_subscriptions_object_uuid_revision",
    "idx_event_subscriptions_handler_module",
    "idx_event_subscription_sources_target_full_name",
    "idx_event_subscription_sources_target_object_uuid",
    "idx_event_subscription_sources_target_meta_type",
]


def check_schema(cur):
    """Живая схема против модели узла: ключи, индексы, витрины, реестры цепей.

    Двусторонняя сверка словарей состояний с CHECK'ами — отдельная функция ниже: CHECK без
    словаря слоя пропускает значение, которого слой не порождает, а словарь без CHECK'а
    позволяет записать состояние, которого нет в модели (приём V50/V52).
    """
    section("Контур 9 — живая схема")
    for table, keys in EXPECTED_UNIQUE_KEYS.items():
        got = sorted(str(row["conname"]) for row in q(
            cur, "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass "
                 "AND contype = 'u'", (table,)))
        check(f"`{table}`: ключей UNIQUE — {len(keys)} ({names(keys)})",
              sorted(keys) == got, f"факт: {names(got)}")
    indexes = {str(row["indexname"]) for row in q(
        cur, "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")}
    missing = sorted(name for name in EXPECTED_INDEXES if name not in indexes)
    check(f"индексов узла в схеме — {len(EXPECTED_INDEXES)} (вопросы «какие подписки вызывает "
          f"этот модуль» и «что подписано на этот объект» читаются индексом, а не разбором)",
          not missing, names(missing))
    views = {str(row["table_name"]) for row in q(
        cur, "SELECT table_name FROM information_schema.views WHERE table_schema = 'public'")}
    for view in (SUBSCRIPTIONS_VIEW, SOURCES_VIEW):
        check(f"витрина `{view}` существует", view in views, "витрины нет в схеме")
    check(f"таблица `{SOURCES_TABLE}` НЕ входит в реестр версионируемых (Q4, вариант A: своей "
          f"цепи ревизий у строк источника нет)",
          SOURCES_TABLE not in CONFIGURATION_VERSIONED_TABLES,
          _brief(sorted(CONFIGURATION_VERSIONED_TABLES)))
    check(f"имя витрины `{SOURCES_VIEW}` не порождается реестром `CURRENT_VIEWS` — она "
          f"построена связкой в DDL (прецедент V50/V52)",
          SOURCES_VIEW not in {("v_current_" + table)
                               for table in CONFIGURATION_VERSIONED_TABLES}, "")
    check(f"таблица `{TABLE_NAME}` входит в реестр версионируемых и в круг снятия стадии",
          TABLE_NAME in CONFIGURATION_VERSIONED_TABLES
          and TABLE_NAME in FOREIGN_STAGE_TABLES
          and TABLE_NAME in EVENT_SUBSCRIPTIONS_TABLES,
          _brief({"versioned": TABLE_NAME in CONFIGURATION_VERSIONED_TABLES,
                  "foreign": TABLE_NAME in FOREIGN_STAGE_TABLES}))
    check(f"таблица `{SOURCES_TABLE}` входит в круг снятия `FOREIGN_STAGE_TABLES`",
          SOURCES_TABLE in FOREIGN_STAGE_TABLES, "")
    check(f"таблица `{SOURCES_TABLE}` входит в реестр неверсионируемых "
          f"`CONFIGURATION_UNVERSIONED_TABLES` (иначе писатель искал бы у неё колонки цепи)",
          SOURCES_TABLE in CONFIGURATION_UNVERSIONED_TABLES,
          _brief(sorted(CONFIGURATION_UNVERSIONED_TABLES)))



def check_state_vocabulary_checks(cur):
    """Закрытые словари состояний слоя ↔ CHECK'ы живой схемы — сверка в обе стороны."""
    vocabulary_wrong = []
    for column_key, vocabulary in STATE_VOCABULARIES.items():
        table, column = column_key.split(".", 1)
        constraints, check_values = table_check_constraints(cur, table, column)
        if not constraints:
            vocabulary_wrong.append(f"{column_key}: CHECK'а замкнутости нет")
            continue
        if not check_values:
            vocabulary_wrong.append(f"{column_key}: CHECK есть, перечня значений в нём нет")
            continue
        if check_values != set(vocabulary):
            vocabulary_wrong.append(
                f"{column_key}: словарь слоя и CHECK разошлись — только в словаре "
                f"{names(sorted(set(vocabulary) - check_values))}, только в CHECK "
                f"{names(sorted(check_values - set(vocabulary)))}")
    check(f"закрытых словарей состояний — {len(STATE_VOCABULARIES)}, каждый замкнут CHECK'ом "
          f"живой схемы, значения совпадают", not vocabulary_wrong, names(vocabulary_wrong))
    # Словарь тегов блока держится CHECK'ом, словарь классов целей — нет (его сторожит
    # контур 6 принадлежностью значений), поэтому здесь называется его размер, а не состав.
    tag_constraints, tag_values = table_check_constraints(cur, SOURCES_TABLE, "source_tag")
    check(f"CHECK замкнутости тегов блока `Source` ({len(tag_constraints)}) держит словарь "
          f"слоя {names(list(SOURCE_TAGS))}",
          bool(tag_constraints) and tag_values == set(SOURCE_TAGS),
          _brief(sorted(tag_values)))
    check(f"словарь классов целей замкнут и насчитывает {len(SOURCE_CLASS_META_TYPES)} записей "
          f"(замер 2.2: 30 классов)", len(SOURCE_CLASS_META_TYPES) == 30,
          f"записей: {len(SOURCE_CLASS_META_TYPES)}")


# ── контур 10: витрины, цепи ревизий, сироты и коллизия имени/uuid между конфигурациями ────
def check_revisions_and_views(cur):
    """Повтор не заводит вторую ревизию; строки источника живут только внутри CURRENT.

    Максимальная `revision_no` обязана остаться равной 1: узел дозагружает круг к уже
    загруженной конфигурации, и вторая ревизия означала бы, что проверка читает состояние,
    которого в выгрузке нет.
    """
    section("Контур 10 — цепи ревизий, витрины и сироты")
    rows = q(cur, f"""
        SELECT c.name, max(es.revision_no) AS max_rev, count(*) AS rows_all,
               count(*) FILTER (WHERE es.is_committed) AS rows_committed
        FROM {TABLE_NAME} es
        JOIN configurations c ON c.uuid = es.configuration_uuid
        GROUP BY c.name ORDER BY c.name
    """)
    for row in rows:
        check(f"{row['name']}: максимальная ревизия строк вида — 1 (повтор не заводит "
              f"вторую)", int(row["max_rev"] or 0) <= 1,
              f"ревизия: {row['max_rev']}, строк: {row['rows_all']}, "
              f"committed: {row['rows_committed']}")
    counts = one(cur, f"""
        SELECT (SELECT count(*) FROM {SUBSCRIPTIONS_VIEW}) AS cur_rows,
               (SELECT count(*) FROM {TABLE_NAME} WHERE is_committed) AS committed,
               (SELECT count(*) FROM {SOURCES_VIEW}) AS cur_sources,
               (SELECT count(*) FROM {SOURCES_TABLE}) AS all_sources
    """)
    check(f"витрина `{SUBSCRIPTIONS_VIEW}` отдаёт ровно committed-строки "
          f"({counts['cur_rows']} ↔ {counts['committed']})",
          int(counts["cur_rows"]) == int(counts["committed"]), _brief(counts))
    check(f"витрина `{SOURCES_VIEW}` не шире полной таблицы "
          f"({counts['cur_sources']} ≤ {counts['all_sources']})",
          int(counts["cur_sources"]) <= int(counts["all_sources"]), _brief(counts))
    orphans = one(cur, f"""
        SELECT (SELECT count(*) FROM {SOURCES_TABLE} s
                WHERE NOT EXISTS (SELECT 1 FROM {SUBSCRIPTIONS_VIEW} v
                                  WHERE v.id = s.event_subscription_id)) AS src_outside,
               (SELECT count(*) FROM {TABLE_NAME} es
                WHERE NOT EXISTS (SELECT 1 FROM {SUBSCRIPTIONS_VIEW} v WHERE v.id = es.id)
                  AND es.is_committed) AS es_outside
    """)
    check("сирот нет: каждая строка источника внутри CURRENT-ревизии своей подписки, каждая "
          "committed-строка вида видна витрине (связка Q4 работает)",
          int(orphans["src_outside"]) == 0 and int(orphans["es_outside"]) == 0,
          _brief(orphans))




def check_name_collision(cur, pair):
    """Коллизия имени и uuid между BGU2 и BP3 (замер 1.3, M1) — сторожится построчно.

    192 имени и 162 uuid подписок общие у двух конфигураций. Строки различаются парой
    (`configuration_uuid`, `full_name`), поэтому загрузка второй конфигурации не имеет права
    снять строки первой: под каждым общим именем обязаны быть строки обеих. Иначе проверка
    читала бы один круг как два, а второй прогон — первый как пустой.
    """
    section("Контур 10b — коллизия имени и uuid (замер 1.3, M1)")
    if not pair:
        skip("коллизия имени и uuid между BGU2 и BP3",
             "в круг прогона не входят обе выгрузки пары — сравнивать две конфигурации не с чем")
        return
    left_uuid, right_uuid = str(pair[0]["uuid"]), str(pair[1]["uuid"])
    left, right = str(pair[0]["name"]), str(pair[1]["name"])
    rows = q(cur, f"""
        SELECT full_name, count(DISTINCT configuration_uuid) AS configs, count(*) AS rows_all
        FROM {SUBSCRIPTIONS_VIEW}
        WHERE configuration_uuid IN (%s::uuid, %s::uuid)
        GROUP BY full_name HAVING count(DISTINCT configuration_uuid) > 1
        ORDER BY full_name
    """, (left_uuid, right_uuid))
    shared_names = {str(row["full_name"]) for row in rows}
    check(f"общих имён подписок между `{left}` и `{right}` — 192 (эталон замера 1.3)",
          len(shared_names) == 192, f"факт: {len(shared_names)}, план: 192")
    thin = [str(row["full_name"]) for row in rows if int(row["rows_all"]) < 2]
    check("под каждым общим именем строки обеих конфигураций — загрузка второй не сняла строки "
          "первой (снятие шло предикатом по своей ноге)", not thin, names(thin))
    uuid_rows = q(cur, f"""
        SELECT object_uuid FROM {SUBSCRIPTIONS_VIEW}
        WHERE configuration_uuid IN (%s::uuid, %s::uuid)
        GROUP BY object_uuid HAVING count(DISTINCT configuration_uuid) > 1
    """, (left_uuid, right_uuid))
    check(f"общих uuid подписок между `{left}` и `{right}` — 162 (эталон замера 1.3)",
          len(uuid_rows) == 162, f"факт: {len(uuid_rows)}, план: 162")
    mismatched = q(cur, f"""
        SELECT a.object_uuid, min(a.full_name) AS first_name,
               min(b.full_name) AS second_name
        FROM {SUBSCRIPTIONS_VIEW} a
        JOIN {SUBSCRIPTIONS_VIEW} b ON b.object_uuid = a.object_uuid
             AND b.configuration_uuid > a.configuration_uuid
        WHERE a.configuration_uuid IN (%s::uuid, %s::uuid)
          AND b.configuration_uuid IN (%s::uuid, %s::uuid)
          AND b.full_name <> a.full_name
        GROUP BY a.object_uuid
    """, (left_uuid, right_uuid, left_uuid, right_uuid))
    # Множества коллизий НЕ совпадают: общих имён 192, общих uuid — 162, и один из них несёт
    # разные имена в двух конфигурациях (замер 1.3). Назвать это — обязанность проверки:
    # «коллизия имени» и «коллизия uuid» являются разными состояниями, и строка различается
    # парой (`configuration_uuid`, `full_name`), а не uuid.
    check("общих uuid с разными именами — ровно 1 (192 имени против 162 uuid: множества "
          "коллизий не совпадают, и это называется, а не сглаживается)",
          len(mismatched) == 1,
          _brief([(str(row["object_uuid"]), str(row["first_name"]), str(row["second_name"]))
                  for row in mismatched][:4]))
    dup_same_config = q(cur, f"""
        SELECT object_uuid, configuration_uuid, count(*) AS c FROM {SUBSCRIPTIONS_VIEW}
        WHERE configuration_uuid IN (%s::uuid, %s::uuid)
        GROUP BY object_uuid, configuration_uuid HAVING count(*) > 1
    """, (left_uuid, right_uuid))
    check("внутри одной конфигурации uuid подписки не повторяется (иначе пара "
          "(`configuration_uuid`, `object_uuid`) не различала бы строки одной выгрузки)",
          not dup_same_config,
          _brief([(str(row["object_uuid"]), row["c"]) for row in dup_same_config][:6]))
    info(f"имён с коллизией: {len(shared_names)}; примеры: {names(sorted(shared_names)[:3])}")


def registry_expected_tools():
    """Реестр `EXPECTED_TOOLS` — снятый синтаксически, без импорта модуля-валидатора.

    Импорт `tools/check_mcp_tool_wiring.py` выполнил бы его прогон ради одного словаря, а
    `ast.literal_eval` берёт значение как есть: реестр — закрытый список, а не вычисление.
    """
    source = (ROOT / "tools" / "check_mcp_tool_wiring.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if getattr(target, "id", "") == "EXPECTED_TOOLS":
                return ast.literal_eval(node.value)
    return {}


# ── контур 11: контракт стадии, круг снятия и реестр инструментов ────────────────────────────
def check_contract():
    """Позиция нормативного списка 2.8, порядок снятия, подсказка продолжения, реестр входов.

    Порядок удаления называется отдельно от круга: `sources` обязаны сниматься ДО `subscriptions`,
    иначе `ON DELETE CASCADE` снял бы строки молча, и число в ответе было бы неправдой.
    """
    section("Контур 11 — контракт стадии и реестр инструментов")
    stage_ids = [stage_id for stage_id, _title in STAGES]
    check(f"стадия `{STAGE_EVENT_SUBSCRIPTIONS}` объявлена в `STAGES`",
          STAGE_EVENT_SUBSCRIPTIONS in stage_ids, names(stage_ids))
    if STAGE_EVENT_SUBSCRIPTIONS in stage_ids:
        position = stage_ids.index(STAGE_EVENT_SUBSCRIPTIONS)
        check("стадия стоит сразу за `s4g_filter_criteria` (позиция 2.7 → 2.8 нормативного "
              "списка) и перед `s4b_object_modules` (вторая транзакция, не позиция списка)",
              stage_ids[position - 1] == STAGE_FILTER_CRITERIA
              and stage_ids[position + 1] == STAGE_OBJECT_MODULES,
              f"соседи: {stage_ids[position - 1]} / {stage_ids[position + 1]}")
    title = stage_title(STAGE_EVENT_SUBSCRIPTIONS)
    check("заголовок стадии называет позицию 2.8 и каталог вида (текст ответа ссылается на "
          "нормативный список, а не на выдуманное имя)",
          "2.8" in title and DIR_NAME in title, f"заголовок: {title}")
    check(f"`STAGE_FULL_RELOAD_ONLY[{STAGE_EVENT_SUBSCRIPTIONS}]` — False: узел повторяется "
          f"своим входом, а не полной перезагрузкой",
          STAGE_FULL_RELOAD_ONLY.get(STAGE_EVENT_SUBSCRIPTIONS) is False,
          f"факт: {STAGE_FULL_RELOAD_ONLY.get(STAGE_EVENT_SUBSCRIPTIONS)}")
    hint = stage_resume_hint(STAGE_EVENT_SUBSCRIPTIONS)
    check("подсказка продолжения называет `load_event_subscriptions_tool` без перезагрузки "
          "конфигурации (иначе ответ обещал бы инструмент, которым круг не повторить)",
          "load_event_subscriptions_tool" in hint and "без перезагрузки" in hint,
          f"подсказка: {hint}")
    check(f"круг стадии `EVENT_SUBSCRIPTIONS_TABLES` — ровно две таблицы пары "
          f"({names(list(EVENT_SUBSCRIPTIONS_TABLES))})",
          set(EVENT_SUBSCRIPTIONS_TABLES) == {TABLE_NAME, SOURCES_TABLE}
          and len(EVENT_SUBSCRIPTIONS_TABLES) == 2,
          _brief(sorted(EVENT_SUBSCRIPTIONS_TABLES)))
    check("круг стадии входит в круг снятия чужих стадий (загрузка другой стадии не снимает "
          "строки V53 молча)",
          all(table in FOREIGN_STAGE_TABLES for table in EVENT_SUBSCRIPTIONS_TABLES),
          _brief(sorted(set(EVENT_SUBSCRIPTIONS_TABLES) - set(FOREIGN_STAGE_TABLES))))
    check(f"порядок удаления — сначала `{SOURCES_TABLE}`, затем `{TABLE_NAME}` "
          f"(FK со ссылкой на ревизию вида + `ON DELETE CASCADE`: иначе снятые строки "
          "источника пропали бы из ответа)",
          list(EVENT_SUBSCRIPTIONS_REMOVE_ORDER).index(SOURCES_TABLE)
          < list(EVENT_SUBSCRIPTIONS_REMOVE_ORDER).index(TABLE_NAME),
          _brief(list(EVENT_SUBSCRIPTIONS_REMOVE_ORDER)))
    check("порядок удаления слоя совпадает с порядком контракта (писатель и конвейер снимают "
          "одним и тем же списком)",
          list(LAYER_REMOVE_ORDER) == list(EVENT_SUBSCRIPTIONS_REMOVE_ORDER),
          f"слой: {_brief(list(LAYER_REMOVE_ORDER))}, контракт: "
          f"{_brief(list(EVENT_SUBSCRIPTIONS_REMOVE_ORDER))}")
    defaults = event_subscriptions_defaults()
    check("нулевой ответ стадии содержит нули по всем счётчикам круга (нулевой ответ — ответ о "
          "состоянии, а не молчание)",
          defaults.get("stage") == STAGE_EVENT_SUBSCRIPTIONS
          and defaults.get("directory") == DIR_NAME
          and list(defaults.get("tables") or []) == list(EVENT_SUBSCRIPTIONS_TABLES)
          and int(defaults.get("event_subscriptions_written") or 0) == 0
          and all(int(value or 0) == 0
                  for value in (defaults.get("removed_by_table") or {}).values())
          and all(int(value or 0) == 0
                  for value in (defaults.get("written_by_table") or {}).values()),
          _brief({key: defaults.get(key) for key in
                  ("stage", "directory", "tables", "event_subscriptions_written")}))
    check("групп запроса (`kinds`) у входа нет — это решение Q8, вариант A, а не упущение: "
          "строка источника живёт только через id строки вида",
          "kinds" not in defaults, _brief(sorted(defaults)))
    registry = registry_expected_tools()
    core_tools = list((registry.get("server_configurations_core.py") or []))
    check("вход `load_event_subscriptions_tool` внесён в реестр `EXPECTED_TOOLS` ядра "
          "(узлом V53 П5 круг ядра — 11 инструментов)",
          "load_event_subscriptions_tool" in core_tools, names(core_tools))
    check(f"число инструментов ядра — {len(core_tools)} (эталон реестра: 11)",
          len(core_tools) == 11, f"факт: {len(core_tools)}, эталон: 11")


# ── контур 12: итог по корпусу и неприкосновенность чужих кругов ─────────────────────────────
# Таблицы других узлов: проверка только читает, поэтому их содержимое до и после прогона
# обязано совпадать. Названы таблицы, а не «число строк в базе»: молчаливое снятие чужого
# круга этим прогоном (прецедент узлов V49…V52) — ровно тот класс дефекта, который здесь
# ловится. Отсутствующих таблиц в перечне нет — отсутствие называется наблюдением.
FOREIGN_TABLES = (
    "configurations", "configuration_objects", "subsystems", "subsystem_content",
    "common_modules", "session_parameters", "roles", "role_rights",
    "role_restriction_templates", "common_attributes", "common_attribute_targets",
    "exchange_plans", "exchange_plan_content", "filter_criteria",
    "filter_criterion_content", "attributes", "tabular_sections", "forms", "form_ext",
    "templates", "commands", "bsl_modules",
)


def foreign_state(cur):
    """Число строк чужих таблиц — одно число на таблицу, отсутствующая — None."""
    state = {}
    for table in FOREIGN_TABLES:
        exists = one(cur, "SELECT to_regclass(%s) AS reg", (table,)).get("reg")
        if not exists:
            state[table] = None
            continue
        state[table] = int(one(cur, f"SELECT count(*) AS c FROM {table}").get("c") or 0)
    return state


def check_non_interference(before, after):
    section("Контур 12b — неприкосновенность чужих кругов")
    changed = {table: (before.get(table), after.get(table))
               for table in FOREIGN_TABLES
               if before.get(table) != after.get(table)}
    check(f"чужих таблиц затронуто — 0 (прогон читающий: {len(FOREIGN_TABLES)} таблиц "
          f"сверены до и после)", not changed, _brief(changed))
    missing = sorted(table for table in FOREIGN_TABLES if before.get(table) is None)
    check(f"отсутствующих чужих таблиц в базе — {len(missing)} (названы, а не пропущены)",
          not missing, names(missing))


def check_corpus(accum, max_sources, handler_distinct, full_scope):
    """Сумма по четырём выгрузкам равна разделам 1 и 2 плана; несуммируемые — своим эталонам.

    Сравнение включается только при полном круге: сумму по трём выгрузкам сравнивать с итогом
    по четырём — ложное расхождение (прецедент V50/V51/V52).
    """
    section("Контур 12 — итог по корпусу")
    if not full_scope:
        skip("итог корпуса (772 файла, 25 100 записей блока `<Source>`)",
             "прогону доступны не все четыре выгрузки — сумму по корпусу сравнивать некорректно")
        return
    expected = dict(CORPUS_TOTALS)
    # Число классов целей по корпусу — множество, а не сумма: его считают по накопленным
    # ключам `class_`, а не складывают из трёх выгрузок (в MinCfg их 3, в BGU2 — 24).
    want_classes = expected.pop("db_distinct_classes", 0)
    counts_diff(accum, expected, "итог по четырём выгрузкам ↔ разделы 1 и 2 плана", "корпус")
    got_classes = len([key for key, value in accum.items()
                       if key.startswith("class_") and value])
    check(f"различающихся классов целей по корпусу — {want_classes} (замер 2.2: 30; по "
          f"выгрузкам множество не складывается)", got_classes == want_classes,
          f"факт: {got_classes}, план: {want_classes}")
    check(f"наибольшее число записей `<Source>` в одном файле — {CORPUS_MAX_SOURCES} "
          f"(замер 1.4: 789; максимум по выгрузкам не складывается)",
          max_sources == CORPUS_MAX_SOURCES,
          f"факт: {max_sources}, план: {CORPUS_MAX_SOURCES}")
    check(f"различающихся обработчиков по корпусу — {CORPUS_HANDLER_DISTINCT} "
          f"(замер 2.3: 468 модуль-методов на 772 подписки; множество по выгрузкам не "
          "складывается)", handler_distinct == CORPUS_HANDLER_DISTINCT,
          f"факт: {handler_distinct}, план: {CORPUS_HANDLER_DISTINCT}")
    two_dump = {("class_" + key): value for key, value in
                PLAN_CLASS_TABLE_TWO_DUMP_SCOPE.items()}
    info(f"строка таблицы 2.2 плана мерилась по BGU2+BP3: "
         f"{_brief(two_dump)} — разность с итогом корпуса приходится на MinCfg и KomMag")


# ── сбор фактических чисел выгрузки для итога корпуса ────────────────────────────────────────
def accumulate_corpus(accum, raw_totals, subscription_rows, source_rows, index_info,
                      circle, parsed):
    """Один вклад выгрузки в итог корпуса — по фактическим числам, а не по эталону.

    Суммируются те же величины, что сравнивает контур 12. Складывать множества и максимумы
    нельзя (`CORPUS_MAX_SOURCES`, `CORPUS_HANDLER_DISTINCT`), поэтому они считаются отдельно.
    """
    for key in RAW_TOTAL_KEYS:
        accum[key] += int(raw_totals.get(key) or 0)
    for key, value in raw_totals.items():
        if key.startswith(RAW_PREFIX_KEYS):
            accum[key] += int(value or 0)
    accum["db_rows"] += len(subscription_rows)
    accum["db_sources"] += len(source_rows)
    for row in source_rows:
        accum["db_resolve_" + str(row["target_resolve_state"])] += 1
    for row in subscription_rows:
        accum["db_handler_" + str(row["handler_state"])] += 1
        accum["db_properties_all_known" if str(row["properties_state"]) == PROPERTIES_ALL_KNOWN
               else "db_properties_unknown"] += 1
        accum["db_source_with" if str(row["source_state"]) == SOURCE_STATE_WITH
               else "db_source_empty"] += 1
        accum["db_comment_null" if row.get("comment") is None else "db_comment_filled"] += 1
    accum["index_rows"] += len(kind_index_rows(index_info["rows"]))
    accum["index_children"] += int(circle["index_children"])
    accum["header_list"] += len(circle["header_names"])
    accum["header_is_null"] += 1 if circle["header_is_null"] else 0
    accum["observations"] += len(parsed["observations"])
    accum["index_only"] += len(parsed["index_only"])
    accum["file_only"] += len(parsed["file_only"])
    accum["uuid_mismatch"] += len(parsed["uuid_mismatch"])
    kinds = Counter(kind for kind, _detail in parsed["observations"])
    accum["directory_missing"] += kinds.get("directory_missing", 0)


# ═══ прогон ═════════════════════════════════════════════════════════════════════════════════
def run(cur, scope):
    headers = q(cur, "SELECT id, uuid::text AS uuid, name FROM configurations ORDER BY id")
    if not headers:
        FAILED.append("строк заголовков конфигураций в базе нет — сравнивать не с чем")
        print("FAIL строк заголовков конфигураций в базе нет — сравнивать не с чем")
        return
    before = foreign_state(cur)
    accum = Counter()
    max_sources_all = 0
    handlers = set()
    loaded_tags = set()
    loaded_headers = []
    for header in headers:
        resolved = resolve_dump_dir(header["uuid"], DUMP_ROOT)
        dump_dir = resolved.get("path") or ""
        tag = Path(dump_dir).name if dump_dir else str(header["name"])
        if scope not in (DEFAULT_SCOPE, tag, str(header["name"])):
            continue
        section(f"Конфигурация {tag} (uuid {header['uuid']})")
        if not dump_dir:
            skip(f"{tag}: прогон выгрузки",
                 f"каталог выгрузки по uuid не найден ({resolved.get('reason', 'нет причины')})")
            continue
        expect = PLAN_EXPECTATIONS.get(tag)
        if expect is None:
            skip(f"{tag}: сравнение с эталоном",
                 "PLAN_EXPECTATIONS этой выгрузки не называет — числа пришлось бы придумывать")
            continue
        index_info = read_index_records(cur, int(header["id"]))
        if not index_info.get("available"):
            skip(f"{tag}: разрешимость целей и сверка с индексом",
                 f"индекс состава недоступен: {index_info.get('reason')}")
        modules = read_common_module_names(cur, str(header["uuid"]))
        if not modules.get("available"):
            info(f"{tag}: перечень общих модулей недоступен — {modules.get('reason')}")
        parsed = parse_circle(dump_dir, index_info["rows"], modules["names"])
        check(f"{tag}: разбор круга завершён без отказа разбора ({expect['files']} файлов)",
              parsed["success"] is True and parsed["files_found"] == expect["files"]
              and parsed["files_read"] == expect["files"],
              f"success: {parsed['success']}, found: {parsed['files_found']}, read: "
              f"{parsed['files_read']}, failed: {_brief(parsed['files_failed'])}")

        circle = check_circle(cur, header, dump_dir, index_info, expect, tag)
        subscription_rows = circle["subscription_rows"]
        check_subscription_rows(parsed, subscription_rows, table_columns(cur, TABLE_NAME), tag)
        check_key_shape(cur, parsed, tag)
        sources = check_source_rows(cur, parsed, header, expect, tag)
        source_rows = sources["source_rows"]
        raw_totals, _per_name, max_sources, unreadable, _observations = raw_measures(dump_dir)
        check_raw_measures(raw_totals, max_sources, unreadable, expect, tag)
        check_db_distributions(source_rows, subscription_rows, expect, tag)
        check_target_resolution(cur, header, source_rows, index_info, tag)
        check_dictionaries(cur, header, source_rows, subscription_rows, raw_totals, expect, tag)
        check_handler_resolution(cur, header, subscription_rows, modules["names"], tag)

        accumulate_corpus(accum, raw_totals, subscription_rows, source_rows, index_info,
                          circle, parsed)
        max_sources_all = max(max_sources_all, max_sources)
        handlers.update(str(row["handler"]) for row in subscription_rows if row.get("handler"))
        loaded_tags.add(tag)
        loaded_headers.append({"uuid": str(header["uuid"]), "name": str(header["name"]),
                               "tag": tag})

    check_missing_directory()
    check_schema(cur)
    check_state_vocabulary_checks(cur)
    check_revisions_and_views(cur)
    pair = [item for item in loaded_headers if item["tag"] in ("BGU2", "BP3")]
    check_name_collision(cur, pair if len(pair) == 2 else None)
    check_contract()
    check_corpus(accum, max_sources_all, len(handlers),
                 loaded_tags == set(PLAN_EXPECTATIONS))
    check_non_interference(before, foreign_state(cur))



def main(argv):
    scope = str(argv[1]) if len(argv) > 1 else DEFAULT_SCOPE
    try:
        with transaction() as cur:
            run(cur, scope)
    except Exception as exc:  # noqa: BLE001 — отказ прогона обязан быть назван, а не оборвать вывод
        FAILED.append(f"прогон прерван исключением: {exc}")
        import traceback
        traceback.print_exc()
    total = len(PASSED) + len(FAILED) + len(SKIPPED)
    print(f"\nИТОГО: проверок {total}, PASS {len(PASSED)}, FAIL {len(FAILED)}, "
          f"SKIP {len(SKIPPED)}, INFO {len(INFO)}")
    if FAILED:
        print("ПРОВАЛЫ:")
        for item in FAILED:
            print(f"  - {item}")
        return 1
    print("ПРОВАЛОВ НЕТ")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

