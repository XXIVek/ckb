"""Проба П8 (вторая половина) узла V52: продолжение стадии S4g отдельным входом.

Первая половина — `_v52_p8_stop_probe.py` — доказывает, что конвейер останавливается на
новой стадии и называет, чем продолжить. Этот файл доказывает вторую половину решения Q8
(п. 3–4): подсказка продолжения работает. Порядок прогонов тот же, что у пробы узла V51
(`_v51_p8_resume_probe.py`), — он и есть проверяемое:

1. базовая полная загрузка выгрузки (`force=True`) — снимок круга вида пятью таблицами,
   снимок круга ЧУЖИХ конфигураций, снимок строки заголовка и индекса состава;
2. прогон конвейера с искусственным отказом стадии S4g: предыдущие стадии подменены
   пустым успехом (иначе остановка была бы на более ранней стадии), S4b — обёрткой со
   счётчиком (её вызов после отказа и есть поломка механизма);
3. продолжение ОТДЕЛЬНЫМ входом `load_filter_criteria(source_path=…, configuration_uuid=…)`
   без перезагрузки конфигурации — круг восстановлен ровно базовыми числами;
4. повторный вызов того же входа — идемпотентность: снятое равно записанному, витрина
   текущего состояния даёт по одной ревизии на строку вида;
5. завершающая полная загрузка — проба не оставляет общую БД неполной.

Что именно доказывает проба и чем она отличается от пробы V51:

* C1/C2 — ответ отдельного входа читается по закрытому контракту
  `filter_criteria_defaults()`: числа по таблицам (`written_by_table`/`removed_by_table`)
  названы по пяти таблицам круга, отсутствие снятия читается нулём, а не молчанием;
* Q8 п. 2 — остановка не откат: после отказа S4g заголовок и индекс состава на месте, а
  круг вида пуст (его снимает перезаголовок `force=True` — вызов `_remove_rows` в
  `configuration_loader.py`);
* Q8 п. 3 — продолжение возможно БЕЗ полной перезагрузки: строка заголовка и индекс
  состава за вызовы отдельного входа не меняются вовсе (тот же числовой `id`, `uuid`,
  `name`, `created_at`);
* Q8 п. 4 — подсказка остановки и текст отдельного входа держат одну формулировку
  (`FILTER_CRITERIA_REPEAT_HINT`), а не две разные;
* отличие круга V52 от кругов V48/V49/V50/V51: таблицы детей (`forms`, `form_ext`,
  `commands`) общие с контуром внешних объектов и с видом планов обмена. Поэтому почти
  каждая проверка раздела 2–4 имеет пару — «строки детей ЧУЖИХ конфигураций не изменились»,
  а подсчёт круга держит функцию слоя `count_criterion_child_rows` (тот же предикат, что и
  снятие), а не копию предиката в пробе;
* в отличие от пробы V51, здесь нет ветви пустого круга: замер 1.1 плана
  `docs/CONFIGURATION_FILTER_CRITERIA_PLAN.md` даёт каталог `FilterCriteria/` на всех
  четырёх выгрузках (1/1/7/6 файлов), поэтому `KomMag` не является пустым кругом по этому
  виду. Пустой круг проверяется фикстурой в `_v52_p8_stop_probe.py` (раздел 4).

Проба меняет только память процесса (подмена функций стадий в модуле загрузчика) и состояние
БД теми же прогонами, которые делает обычный конвейер; выгрузка на диске не правится.
Прогоны, меняющие общую БД, не параллелят с другими пробами (наблюдение П8 узла V50).

Запуск:

    [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'
    cd C:\\1C_LLM\\ckb
    python _v52_p8_resume_probe.py [MinCfg]
    python _v52_p8_resume_probe.py KomMag

Код возврата 0 — расхождений нет.
"""

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

import configuration_loader as CL  # noqa: E402  — подмена функций стадий читается им
from config_load_router import format_load_result, load_catalog  # noqa: E402
from configuration_filter_criteria_loader import (  # noqa: E402
    REMOVE_ORDER as CIRCLE_REMOVE_ORDER,
    count_criterion_child_rows,
    load_filter_criteria,
)
from configuration_load_contract import (  # noqa: E402
    FILTER_CRITERIA_CIRCLE_BOUNDARY,
    FILTER_CRITERIA_DIR,
    FILTER_CRITERIA_REPEAT_HINT,
    FILTER_CRITERIA_SECTION_HEADER,
    OBJECT_MODULES_SECTION_HEADER,
    STAGE_CHILD_OBJECTS,
    STAGE_COMMON_ATTRIBUTES,
    STAGE_EXCHANGE_PLANS,
    STAGE_FILTER_CRITERIA,
    STAGE_OBJECT_MODULES,
    STAGE_ROLES,
    STAGE_ROOT_MODULES,
    STAGE_SESSION_PARAMETERS,
    STATUS_ERROR,
    STATUS_OK,
    STOP_STAGE_SECTION_HEADER,
    child_objects_defaults,
    common_attributes_defaults,
    exchange_plans_defaults,
    filter_criteria_defaults,
    format_filter_criteria_lines,
    roles_defaults,
    root_modules_defaults,
    session_parameters_defaults,
    stage_title,
)
from external_db import connect  # noqa: E402


DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMPS = ("MinCfg", "KomMag", "BGU2", "BP3")

# Стадии, подменяемые пустым успехом, чтобы конвейер дошёл ровно до S4g и остановился на
# ней: тот же приём, что в `_v52_p8_stop_probe.py` (подмена в модуле загрузчика, а не
# локальной копии). S4b НЕ подменяется ответом: после отказа S4g она обязана не вызываться,
# и доказывается это счётчиком вызовов, а не совпадением со статусом `not_run` (прецедент
# пробы V51). Обёртка S4b зовёт настоящую функцию и лишь помечает вызов — подмена ответа
# скрыла бы реальный прогон стадии.
EARLIER_STAGES = (
    STAGE_ROOT_MODULES, STAGE_CHILD_OBJECTS, STAGE_SESSION_PARAMETERS, STAGE_ROLES,
    STAGE_COMMON_ATTRIBUTES, STAGE_EXCHANGE_PLANS,
)
LATER_STAGES = (STAGE_OBJECT_MODULES,)
STAGE_FUNCTIONS = {
    STAGE_ROOT_MODULES: "load_root_modules",
    STAGE_CHILD_OBJECTS: "load_object_properties",
    STAGE_SESSION_PARAMETERS: "load_session_parameters",
    STAGE_ROLES: "load_roles",
    STAGE_COMMON_ATTRIBUTES: "load_common_attributes",
    STAGE_EXCHANGE_PLANS: "load_exchange_plans",
    STAGE_FILTER_CRITERIA: "load_filter_criteria",
    STAGE_OBJECT_MODULES: "load_object_modules",
}
DEFAULTS = {
    STAGE_ROOT_MODULES: root_modules_defaults,
    STAGE_CHILD_OBJECTS: child_objects_defaults,
    STAGE_SESSION_PARAMETERS: session_parameters_defaults,
    STAGE_ROLES: roles_defaults,
    STAGE_COMMON_ATTRIBUTES: common_attributes_defaults,
    STAGE_EXCHANGE_PLANS: exchange_plans_defaults,
    STAGE_FILTER_CRITERIA: filter_criteria_defaults,
}
# Круг стадии — перечень снятия писателя (`REMOVE_ORDER`), а не переписанный список: проба
# обязана считать те же пять таблиц, которые загрузчик снимает и пишет. Числа по всем пяти
# таблицам ответ держит в словарях пар `written_by_table` / `removed_by_table` (проверка 3.6
# читает их и сверяет с отдельными счётчиками `*_written` — одно число в двух местах обязано
# совпадать). Урок первого прогона этой пробы двоякий: `FILTER_CRITERIA_TABLES` — две
# таблицы самого вида, а не пять (брать их за круг было бы правкой круга), а нулевой словарь
# контракта `filter_criteria_defaults()` засеивает парами только эти две таблицы — ответ о
# прогоне заполняет словарь пятью таблицами, и проба называет это наблюдением, а не молчит.
CIRCLE_TABLES = tuple(CIRCLE_REMOVE_ORDER)
# Отдельные счётчики записанных детей (дублируют числа словаря пар — совпадение проверяется).
CHILD_COUNTERS = {"forms": "forms_written", "form_ext": "form_ext_written",
                  "commands": "commands_written"}
# Числа разбора, по которым отдельный вход сверяется со стадией конвейера: один и тот же
# код обязан давать один и тот же состав (шаги П4 и П5 узла V52).
PARSE_COUNTERS = ("files_found", "files_read", "index_kind_records", "targets_total",
                  "forms_total", "form_ext_total", "commands_total", "rows_written")
# Слова, которыми форматёр называет состояние стадии (правило C2), — читаются проверкой 2.6;
# текст держит форматёр, здесь только строка сравнения (прецедент пробы остановки V52).
SKIPPED_PHRASE = "Стадия не выполнялась"

PASSED = 0
FAILED = 0
NOTES = []


def check(name, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + (((" — " + str(detail))) if detail else ""))
    else:
        FAILED += 1
        print("  [FAIL] " + name + (((" — " + str(detail))) if detail else ""))


def note(text):
    NOTES.append(text)
    print("  [NOTE] " + text)


def one(cur, sql, params=None):
    cur.execute(sql, params or ())
    row = cur.fetchone()
    return row[0] if row else None


def diff(before, after):
    """Только разошедшиеся таблицы — деталь отказа не тонет в нулях совпадений."""
    return {table: (before.get(table), after.get(table)) for table in CIRCLE_TABLES
            if before.get(table) != after.get(table)}



def circle_counts(cur, cfg_uuid):
    """Строки круга вида этой конфигурации по пяти таблицам.

    Общий круг детей считается функцией слоя (`count_criterion_child_rows`) — тем же
    предикатом, что и снятие. Подсчёт только по ноге `configuration_uuid` собрал бы детей
    всех объектов конфигурации и чужих видов (те же таблицы пишут внешний контур V13/V14 и
    вид V51): сравнение «до/после» перестало бы что-либо доказывать.
    """
    return {table: count_criterion_child_rows(cur, cfg_uuid, table)
            for table in CIRCLE_TABLES}


def other_circle_counts(cur, cfg_uuid):
    """Дети ЧУЖИХ конфигураций — неприкосновенность чужого круга (тот же круг родителей)."""
    return {table: count_criterion_child_rows(cur, cfg_uuid, table,
                                              other_configurations=True)
            for table in CIRCLE_TABLES}


def header_snapshot(cur, cfg_uuid):
    """Снимок строки заголовка: что не имеет права изменить ОДИНОЧНЫЙ вход слоя.

    Ноги, по которым строка конфигурации является той же самой: числовой `id`, `uuid`,
    `name`, `created_at`. Наблюдение П8 (повторено узлом V52): конвейер при `force=True`
    строку заголовка НЕ обновляет — он снимает прежнюю и вставляет новую с тем же uuid,
    поэтому числовой `id` и `created_at` меняются на каждой перезагрузке (провенанс строк
    конфигурации в БД не ведётся — решение D-C). Отсечкой для проверок 3.3 и 4.8 служит
    снимок ПОСЛЕ раздела 2: одиночный вход слоя не имеет права трогать заголовок вовсе.
    """
    cur.execute("SELECT id, uuid, name, created_at FROM configurations "
                "WHERE uuid = %s::uuid ORDER BY id", [str(cfg_uuid)])
    return [tuple(str(part) for part in row) for row in cur.fetchall()]


def header_identity(cur, cfg_uuid):
    """Тот же ли это объект конфигурации: `uuid` и `name` (ноги, общие для двух строк)."""
    cur.execute("SELECT uuid, name FROM configurations WHERE uuid = %s::uuid ORDER BY id",
                [str(cfg_uuid)])
    return [tuple(str(part) for part in row) for row in cur.fetchall()]


def index_count(cur, cfg_id):
    return int(one(cur, "SELECT count(*) FROM configuration_objects "
                        "WHERE configuration_id = %s", [cfg_id]) or 0)


def by_table(answer, key):
    """Числа по таблицам круга сведены к одному перечню: пропущенная таблица — ноль.

    Ответ называет снятые и записанные строки по всем пяти таблицам круга (C1), но перечень
    нулей в нём не обязан быть: сравнение «снято равно записанному» на словарях разной
    полноты дало бы расхождение там, где его нет. Поэтому сравнение идёт по `REMOVE_ORDER` —
    тем же перечню, по которому писатель снимает строки. Таблицы вне круга — не шумы: они
    называются ответом, и проба их показывает, а не выбрасывает.
    """
    raw = answer.get(key) or {}
    unknown = sorted(set(raw) - set(CIRCLE_TABLES))
    if unknown:
        note(f"ответ называет таблицы вне круга снятия: {unknown}")
    return {table: int(raw.get(table) or 0) for table in CIRCLE_TABLES}


def stop_at_s4g(dump_dir, reason):
    """Один прогон конвейера с отказом S4g: предыдущие стадии — пустой успех, S4g — отказ.

    S4b не подменяется ответом: после отказа S4g конвейер обязан её не звать, и это
    проверяется счётчиком вызовов (`calls`). Обёртка зовёт настоящую функцию и лишь помечает
    вызов — подмена ответа скрыла бы реальный прогон (или реальный пропуск) стадии хвоста.
    Подмена держится модуля загрузчика, а не локальной копии: `register_configuration`
    обращается к имени в модуле (приём `_v52_p8_stop_probe.py`).
    """
    calls = {}
    originals = {}
    for stage in EARLIER_STAGES:
        originals[stage] = getattr(CL, STAGE_FUNCTIONS[stage])

        def _ok(*args, _stage=stage, **kwargs):
            calls[_stage] = calls.get(_stage, 0) + 1
            answer = DEFAULTS[_stage]()
            answer["success"] = True
            if "status" in answer:
                answer["status"] = STATUS_OK
            answer["reason"] = None
            return answer
        setattr(CL, STAGE_FUNCTIONS[stage], _ok)

    originals[STAGE_FILTER_CRITERIA] = getattr(CL, STAGE_FUNCTIONS[STAGE_FILTER_CRITERIA])

    def _broken(*args, **kwargs):
        calls[STAGE_FILTER_CRITERIA] = calls.get(STAGE_FILTER_CRITERIA, 0) + 1
        answer = filter_criteria_defaults()
        answer["success"] = False
        answer["status"] = STATUS_ERROR
        answer["error"] = reason
        answer["reason"] = reason
        return answer
    setattr(CL, STAGE_FUNCTIONS[STAGE_FILTER_CRITERIA], _broken)

    for stage in LATER_STAGES:
        originals[stage] = getattr(CL, STAGE_FUNCTIONS[stage])
        real = originals[stage]

        def _spy(*args, _stage=stage, _real=real, **kwargs):
            calls[_stage] = calls.get(_stage, 0) + 1
            return _real(*args, **kwargs)
        setattr(CL, STAGE_FUNCTIONS[stage], _spy)

    try:
        result = load_catalog(str(dump_dir), force=True)
    finally:
        for stage, fn in originals.items():
            setattr(CL, STAGE_FUNCTIONS[stage], fn)
    return result, calls



def main() -> int:
    chosen = next((arg for arg in sys.argv[1:] if arg in DUMPS), "MinCfg")
    dump_dir = DUMP_ROOT / chosen
    if not dump_dir.is_dir():
        print(f"Каталог выгрузки не найден: {dump_dir}")
        return 2

    print(f"\n=== 1. Базовая загрузка каталога ({chosen}, force=True) ===")
    seeded_pairs = sorted((filter_criteria_defaults().get("written_by_table") or {}))
    if seeded_pairs != sorted(CIRCLE_TABLES):
        note("наблюдение П8: нулевой словарь контракта `filter_criteria_defaults()` засеивает "
             f"словари пар `written_by_table`/`removed_by_table` таблицами {seeded_pairs} — "
             "двумя таблицами самого вида, тогда как ответ прогона заполняет их пятью "
             "таблицами круга. Состоянием это не является (неперечисленные ключи читаются "
             "нулями — C1), но перечень чисел в тексте пропущенной стадии отличается от "
             "перечня успешной; засеивать ли пятью — правка контракта, а не П8, поэтому "
             "позиция называется, а не правится молча")
    base = load_catalog(str(dump_dir), force=True)
    check("1.1 базовая загрузка успешна", base.get("success") is True, base.get("error"))
    base_stage = base.get("filter_criteria") or {}
    conn = connect()
    try:
        cur = conn.cursor()
        cfg_uuid = base.get("uuid")
        cfg_id = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                     [str(cfg_uuid)])
        baseline = circle_counts(cur, cfg_uuid)
        other_baseline = other_circle_counts(cur, cfg_uuid)
        header_before = header_snapshot(cur, cfg_uuid)
        identity_before = header_identity(cur, cfg_uuid)
        index_before = index_count(cur, cfg_id)
        check("1.2 круг вида непустой строкой самого вида, иначе восстанавливать нечем "
              "(замер 1.1 плана: каталог `FilterCriteria/` есть на всех четырёх выгрузках — "
              "ветви пустого круга, как в пробе V51 по планам обмена, здесь нет; пустой круг "
              "проверяется фикстурой `_v52_p8_stop_probe.py`, раздел 4)",
              baseline["filter_criteria"] > 0, baseline)
        check("1.3 базовая загрузка даёт ровно одну строку заголовка по uuid и индекс "
              "состава (иначе продолжение не с чем сверять)",
              len(header_before) == 1 and index_before > 0,
              f"строк заголовка {len(header_before)}, индекс {index_before}")
        check("1.4 стадия S4g отработала в базовой загрузке: продолжение проверяется после "
              "её отказа, а не вместо неё",
              base_stage.get("success") is True
              and int(base_stage.get("rows_written") or 0) > 0,
              base_stage.get("rows_written"))
        note(f"базовый круг: {baseline}; чужие круги: {other_baseline}")
        if not baseline["filter_criterion_content"]:
            note("перечень `<Content>` этого критерия пуст состоянием `empty_content` "
                 "(замер 1.1: целей перечня 0/7/727/492 на четырёх выгрузках) — ноль таблицы "
                 "условий является ответом о выгрузке, а не отсутствием строк загрузки; "
                 "сверка «до/после» держит тот же круг, поэтому ноль остаётся нулём")
        empty_children = [table for table in ("forms", "form_ext", "commands")
                          if not baseline[table]]
        if empty_children:
            note(f"общие таблицы детей пусты по {empty_children}: сравнение «до/после» "
                 "держит круг вида (тот же предикат, что у снятия), а не факт непустоты "
                 "таблицы — пустая таблица чужих строк не доказывает")

        print(f"\n=== 2. Остановка конвейера на S4g ({chosen}) ===")
        reason = f"искусственный отказ стадии {STAGE_FILTER_CRITERIA} (проба П8)"
        stopped_result, calls = stop_at_s4g(dump_dir, reason)
        stopped = stopped_result.get("stopped_stage") or {}
        # `format_load_result` возвращает готовую строку карточки (а не список строк),
        # поэтому её не склеивают: join по строке разбил бы её на символы, и сравнение
        # подстрок перестало бы находить любой заголовок (урок первого прогона этой пробы).
        card = format_load_result(stopped_result)
        check("2.1 конвейер остановлен именно на S4g и подсказывает отдельный вход "
              "(критерий П8)",
              stopped.get("stage") == STAGE_FILTER_CRITERIA
              and "load_filter_criteria_tool" in str(stopped.get("resume_with")),
              str(stopped.get("resume_with"))[:80])
        check("2.1а текст подсказки — общий с текстом стадии: одна формулировка "
              "продолжения на карточку остановки и на ответ отдельного входа (прецедент "
              "V45; урок П8 узла V51 — без ветви `stage_resume_hint` подсказка молчала бы "
              "«полная перезагрузка», и проверка 2.1 проходила бы по значению по умолчанию)",
              FILTER_CRITERIA_REPEAT_HINT in str(stopped.get("resume_with")),
              FILTER_CRITERIA_REPEAT_HINT[:70])
        check("2.2 стадия S4b модулей объектов после отказа S4g НЕ вызывалась — S4g стоит "
              "последней среди стадий детей, поэтому в перечне пропущенных она одна",
              all(calls.get(stage) in (None, 0) for stage in LATER_STAGES),
              {stage: calls.get(stage, 0) for stage in LATER_STAGES})
        check("2.2а отказавшая стадия вызвана ровно один раз (остановка идёт по её ответу, "
              "а не по исключению)",
              calls.get(STAGE_FILTER_CRITERIA) == 1, calls.get(STAGE_FILTER_CRITERIA))
        after_stop = circle_counts(cur, cfg_uuid)
        check("2.3 круг вида снят и не заполнен — остановка не откат (Q8 п. 2); снятие "
              "делает перезаголовок `force=True` через `_remove_rows`, а не стадия",
              all(value == 0 for value in after_stop.values()), after_stop)
        cfg_id_stop = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                          [str(cfg_uuid)])
        header_after_stop = header_snapshot(cur, cfg_uuid)
        check("2.4 заголовок на месте (одна строка по тому же uuid, то же имя) и индекс "
              "состава не изменился — остановка не откат",
              len(header_after_stop) == 1
              and header_identity(cur, cfg_uuid) == identity_before
              and index_count(cur, cfg_id_stop) == index_before,
              f"строк заголовка {len(header_after_stop)}, индекс "
              f"{index_count(cur, cfg_id_stop)} из {index_before}")
        other_after_stop = other_circle_counts(cur, cfg_uuid)
        check("2.5 строки детей ЧУЖИХ конфигураций не изменились: таблицы детей общие с "
              "контуром внешних объектов и видом V51, разделение держат ноги предиката",
              other_after_stop == other_baseline, diff(other_baseline, other_after_stop))
        check("2.6 карточка называет раздел остановки, раздел отказавшей стадии и пропуск "
              "S4b словами формата (C2: «не выполнялась» — не нули); строку пропуска печатает "
              "форматёр пары `stage — title`, поэтому сравнение держит адрес стадии",
              STOP_STAGE_SECTION_HEADER in card
              and FILTER_CRITERIA_SECTION_HEADER in card
              and f"{SKIPPED_PHRASE}: {STAGE_OBJECT_MODULES} — "
              f"{stage_title(STAGE_OBJECT_MODULES)}" in card,
              [line.strip() for line in card.splitlines()
               if SKIPPED_PHRASE in line][:2])


        note("между разделами 2 и 3: строка заголовка после `force=True` — новая (снимок "
             f"раздела 1 имел id {header_before[0][0]}, после остановки id "
             f"{header_after_stop[0][0]}). Продолжение отдельным входом привязано к uuid, а "
             "не к числовому id, и править заголовок оно не имеет права — сравнение идёт со "
             "снимком после остановки (наблюдение П8 узла V51, повторено здесь)")
        cfg_id = cfg_id_stop or cfg_id

        print("\n=== 3. Продолжение отдельным входом без перезагрузки конфигурации ===")
        first = load_filter_criteria(str(dump_dir), configuration_uuid=str(cfg_uuid))
        check("3.1 ответ отдельного входа успешен и называет свой статус (не `not_run`)",
              first.get("success") is True
              and first.get("status") not in (None, STATUS_ERROR),
              first.get("error"))
        restored = circle_counts(cur, cfg_uuid)
        check("3.2 круг вида восстановлен ровно базовыми числами — продолжение заменяет "
              "полную перезагрузку (Q8 п. 3)",
              restored == baseline, diff(baseline, restored))
        cfg_id_now = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                         [str(cfg_uuid)])
        check("3.3 строка заголовка НЕ тронута продолжением — перезагрузка конфигурации для "
              "него не требуется (тот же `id`, `uuid`, `name`, `created_at`; строка "
              "заголовка по-прежнему одна)",
              header_snapshot(cur, cfg_uuid) == header_after_stop,
              f"после остановки {header_after_stop[0][0]}, стало "
              f"{header_snapshot(cur, cfg_uuid)[0][0]}")
        check("3.4 индекс состава не изменился и не перечитывался",
              index_count(cur, cfg_id_now) == index_before,
              f"{index_count(cur, cfg_id_now)} из {index_before}")
        check("3.5 снятых строк нет — остановка уже сняла круг, и ответ называет это нулём "
              "по каждой таблице круга, а не молчанием (C1, C2)",
              int(first.get("removed_previous") or 0) == 0
              and all(value == 0 for value in by_table(first, "removed_by_table").values()),
              first.get("removed_previous"))
        first_written = by_table(first, "written_by_table")
        check("3.6 записанное названо словарём пар по всему кругу пяти таблиц и совпадает с "
              "тем, что лежит в базе (числа ответа и числа БД проверяются вместе)",
              all(first_written[table] == restored[table] for table in CIRCLE_TABLES),
              {table: (first_written[table], restored[table]) for table in CIRCLE_TABLES
               if first_written[table] != restored[table]})
        counter_written = {table: int(first.get(counter) or 0)
                           for table, counter in CHILD_COUNTERS.items()}
        check("3.6а те же числа записанных детей названы вторым способом — отдельными "
              "счётчиками `forms_written` / `form_ext_written` / `commands_written` (C1): одно "
              "число в двух местах обязано совпадать, иначе читатель выбирает, кому верить",
              counter_written == {table: first_written[table] for table in CHILD_COUNTERS},
              {table: (counter_written[table], first_written[table])
               for table in CHILD_COUNTERS
               if counter_written[table] != first_written[table]})
        first_card = "\n".join(format_filter_criteria_lines(first, indent="   "))
        check("3.7 текст ответа отдельного входа называет записанные строки, число файлов "
              "вида и границу круга — ответ читается человеком, а не только машиной (C2); "
              "граница сверяется с текстом контракта, а не с выдуманной фразой",
              "Записано строк по таблицам" in first_card
              and "Файлов регистрации вида:" in first_card
              and FILTER_CRITERIA_DIR in first_card
              and "Граница:" in first_card
              and FILTER_CRITERIA_CIRCLE_BOUNDARY in first_card,
              f"{len(first_card.splitlines())} строк текста")
        check("3.8 отдельный вход даёт тот же состав разбора, что стадия конвейера: числа "
              "файлов, индекса состава, перечня, детей и итога совпадают с базовой "
              "загрузкой (один код — один результат, шаги П4 и П5)",
              {key: first.get(key) for key in PARSE_COUNTERS}
              == {key: base_stage.get(key) for key in PARSE_COUNTERS},
              {key: (base_stage.get(key), first.get(key)) for key in PARSE_COUNTERS
               if first.get(key) != base_stage.get(key)})
        other_after_first = other_circle_counts(cur, cfg_uuid)
        check("3.9 строки детей ЧУЖИХ конфигураций не изменились за продолжение",
              other_after_first == other_baseline, diff(other_baseline, other_after_first))
        current = int(one(cur, "SELECT count(*) FROM v_current_filter_criteria "
                              "WHERE configuration_uuid = %s::uuid",
                          [str(cfg_uuid)]) or 0)
        duplicates = int(one(cur, "SELECT count(*) FROM (SELECT object_name "
                                 "FROM v_current_filter_criteria "
                                 "WHERE configuration_uuid = %s::uuid "
                                 "GROUP BY object_name HAVING count(*) > 1) t",
                             [str(cfg_uuid)]) or 0)
        check("3.10 витрина текущего состояния после продолжения отдаёт ровно базовый состав "
              "вида и не даёт дублей ревизий (цепь состояния ведётся по ключу вида)",
              current == baseline["filter_criteria"] and duplicates == 0,
              f"текущих {current} из {baseline['filter_criteria']}, дублей {duplicates}")


        print("\n=== 4. Повторный вызов: идемпотентность и названные снятые строки ===")
        second = load_filter_criteria(str(dump_dir), configuration_uuid=str(cfg_uuid))
        check("4.1 повтор успешен", second.get("success") is True, second.get("error"))
        again = circle_counts(cur, cfg_uuid)
        check("4.2 состав в базе тот же, что после первого вызова", again == restored,
              diff(restored, again))
        removed_second = by_table(second, "removed_by_table")
        other_after = other_circle_counts(cur, cfg_uuid)
        check("4.3 снятое повтором равно записанному первым по всем пяти таблицам круга: "
              "идемпотентность держится явным `DELETE` круга, а не каскадом (внешнего ключа "
              "в схеме нет осознанно — прецедент V20.1)",
              removed_second == first_written,
              {"снято": removed_second, "записано первым": first_written})
        check("4.4 записанное повтором совпадает с записанным первым по всем таблицам круга "
              "— повтор не создаёт второго комплекта строк",
              by_table(second, "written_by_table") == first_written,
              {"первый": first_written, "второй": by_table(second, "written_by_table")})
        current = int(one(cur, "SELECT count(*) FROM v_current_filter_criteria "
                              "WHERE configuration_uuid = %s::uuid",
                          [str(cfg_uuid)]) or 0)
        duplicates = int(one(cur, "SELECT count(*) FROM (SELECT object_name "
                                 "FROM v_current_filter_criteria "
                                 "WHERE configuration_uuid = %s::uuid "
                                 "GROUP BY object_name HAVING count(*) > 1) t",
                             [str(cfg_uuid)]) or 0)
        check("4.5 витрина текущего состояния: по одной ревизии на строку вида, дублей нет "
              "после двух записей круга (строка условия версионируется не своей цепью — Q2 "
              "вариант A, её снимает каскад по id ревизии вида)",
              current == baseline["filter_criteria"] and duplicates == 0,
              f"текущих {current} из {baseline['filter_criteria']}, дублей {duplicates}")
        second_card = "\n".join(format_filter_criteria_lines(second, indent="   "))
        check("4.6 ответ повтора называет снятые прежние строки строкой формата — ровно "
              "когда снятие было (C2: ноль не печатается как факт)",
              ("Снято прежних строк этой конфигурации" in second_card)
              == (sum(removed_second.values()) > 0),
              f"снято {sum(removed_second.values())}")
        check("4.7 строки ЧУЖИХ конфигураций не изменились за оба вызова",
              other_after == other_baseline, diff(other_baseline, other_after))
        check("4.8 строка заголовка и индекс состава за оба вызова не менялись",
              header_snapshot(cur, cfg_uuid) == header_after_stop
              and index_count(cur, cfg_id_now) == index_before,
              header_snapshot(cur, cfg_uuid)[0][0])
        note(f"{chosen}: подсказка остановки продолжена отдельным входом без полной "
             f"перезагрузки; повтор идемпотентен (снято {sum(removed_second.values())}, "
             f"записано {sum(first_written.values())})")


        print("\n=== 5. Восстановление: проба не оставляет общую БД неполной ===")
        # Разделы 2–4 оставляют выгрузку в состоянии «круг вида есть, остальных стадий
        # нет»: заглушки S3…S4f ничего не пишут. Оставлять так общую БД нельзя — контуры
        # прежних узлов (`check_v48`, `check_v49`, `check_v50`, `check_v51`) читают строки
        # своих стадий и называют отсутствующие строки провалом: проба, которая правит общую
        # базу, обязана вернуть её в эталонное состояние тем же полным прогоном, которым
        # начинала (прецедент раздела 5 пробы `_v51_p8_resume_probe.py`).
        full = load_catalog(str(dump_dir), force=True)
        check("5.1 завершающая полная загрузка успешна",
              full.get("success") is True, full.get("error"))
        final = circle_counts(cur, cfg_uuid)
        check("5.2 круг вида восстановлен базовыми числами базовой загрузки",
              final == baseline, diff(baseline, final))
        other_final = other_circle_counts(cur, cfg_uuid)
        check("5.3 строки ЧУЖИХ конфигураций не изменились за все разделы пробы",
              other_final == other_baseline, diff(other_baseline, other_final))
        cfg_id_final = one(cur, "SELECT id FROM configurations WHERE uuid = %s::uuid",
                           [str(cfg_uuid)])
        check("5.4 индекс состава после полного прогона тот же",
              index_count(cur, cfg_id_final) == index_before,
              f"{index_count(cur, cfg_id_final)} из {index_before}")
        check("5.5 заголовок по-прежнему один и тот же по uuid и имени",
              header_identity(cur, cfg_uuid) == identity_before,
              str(header_identity(cur, cfg_uuid))[:120])
        final_card = format_load_result(full)
        check("5.6 завершающий прогон дошёл до конца: карточка печатает раздел S4g и раздел "
              "S4b и не печатает раздела остановки — состояние базы эталонное, а не "
              "«остановленное» (проба не оставляет следов в общей БД)",
              FILTER_CRITERIA_SECTION_HEADER in final_card
              and OBJECT_MODULES_SECTION_HEADER in final_card
              and STOP_STAGE_SECTION_HEADER not in final_card,
              [line.strip() for line in final_card.splitlines()
               if STOP_STAGE_SECTION_HEADER in line][:2])
    finally:
        conn.close()

    print(f"\nИТОГ: пройдено {PASSED}, расхождений {FAILED}")
    for text in NOTES:
        print("  · " + text)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

