#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проба узла V47 П4: стадия модулей объектов внутри конвейера загрузки (28.10.2026).

Чем отличается от `_v47_p3_writer_probe.py`: та проверяла писателя на курсоре чужой
транзакции. Здесь проверяются СЛОЙ И КОНВЕЙЕР: закрытость контракта стадии, отказы точки
входа (чужой `configuration_uuid`, каталог без `Configuration.xml`, незагруженный
заголовок), вызов стадии самим `load_catalog(..., force=True)` БЕЗ флага просьбы
(решение Q4), совмещение чисел ответа с тем, что легло в `bsl_modules`, атом полноты по
группам (принудительный отказ группы — критерий 8 плана), идемпотентность второй загрузки
(строки круга не удваиваются), снятие прежних строк круга узла вместе с заголовком
(граница по `parent_type`, раздел 10 плана), пересборка статистики (`reltuples > 0`) и
неприкосновенность чужих контуров `bsl_modules` (внешний объект, общие модули V46).

Замер времени модульной стадии — обязанность этого прогона (план, раздел 6: «цена варианта
B названа числом 303.9 МиБ; времени такая стадия ещё не меряла»). По умолчанию пробегает
MinCfg; выгрузка задаётся аргументом:

    python _v47_p4_loader_probe.py [MinCfg|BGU2|BP3]

Записи остаются в живой базе: конвейер фиксирует транзакции сам, а строки модулей —
результат загрузки конфигурации. Снять их после пробы — значит оставить конфигурацию без
только что записанного состава, поэтому проба называет базовое состояние до и состояние
после, а не обещает нули.

Принудительный отказ группы проверяется на копии выгрузки в `_scratch/`: файл модуля
портится на байты, которые не раскодировываются строго (правило C5). `PAGE_SIZE` писателя
уменьшается на время этой пробы, иначе для маленькой выгрузки ни одна страница не была бы
записана до отказа, и компенсирующий снятие (`abandon_written_rows`) не был бы проверен.
"""
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC))

from configuration_load_contract import (  # noqa: E402
    OBJECT_MODULES_BOUNDARY,
    OBJECT_MODULES_RELOAD_HINT,
    OBJECT_MODULES_SECTION_HEADER,
    STATUS_ERROR,
    STATUS_NOT_RUN,
    STATUS_OK,
    format_object_module_lines,
)
from configuration_module_slots import (  # noqa: E402
    PARENT_TYPE, SLOTS, STATE_FILE, TARGET_TABLE, iter_module_rows, scope_condition_sql,
    scope_params,
)
import configuration_module_writer as module_writer  # noqa: E402
from configuration_object_modules_loader import (  # noqa: E402
    load_object_modules, mark_index_unavailable, object_modules_defaults,
)
from configuration_root_module_loader import configuration_uuid_from_layout  # noqa: E402
from config_load_router import format_load_result, load_catalog  # noqa: E402
from external_db import connect  # noqa: E402

DUMP_NAMES = ("MinCfg", "BGU2", "BP3")
DUMP_ROOT = Path(r"C:\1C_LLM\LoadDoc\Configurations\XML_files")
DUMP_HINT = {
    "MinCfg": "Минимальная конфигурация (эталон П6 — 79 строк)",
    "BGU2": "Бухгалтерия для государственных учреждений (эталон П6 — 4 461 строка)",
    "BP3": "Бухгалтерия предприятия 3 (эталон П6 — 6 239 строк)",
}
# Ожидаемое число строк по эталону П6 плана — проверяется только у тех выгрузок, чей
# эталон здесь назван: сверять число с числом того же прогона значило бы ничего не
# проверять.
ROW_EXPECTATION = {"MinCfg": 79}
# Каталог выгрузки, которой в базе нет (отказ «заголовка нет») — тот же, что у проб V45/V46.
UNLOADED_DUMP = "UNF3"
# Копия выгрузки для пробы принудительного отказа группы.
BROKEN_DIR = Path(__file__).resolve().parent / "_scratch" / "_v47_p4_broken"
# Байты, не раскодировываемые строго: «не раскодировано» — отказ стадии (C5), а не мусор,
# записанный в базу как код модуля.
BROKEN_BYTES = b"\xed\xa0\x80"
# Выгрузки тяжелее этого порога не копируются: копия BGU2 — 5.3 ГиБ и 79 137 файлов, и на
# прогоне 28.10.2026 её создание стоило дороже самой загрузки. Порог — это цена копии, а
# не свойство выгрузки: MinCfg (6.6 МиБ) копируется, BGU2 и BP3 — нет.
COPY_LIMIT_MIB = 200.0
# Байты испорченного файла сохраняются здесь ДО правки и читаются оттуда же при
# восстановлении: обрыв пробы не оставляет исходную выгрузку битой.
BACKUP_FILE = Path(__file__).resolve().parent / "_scratch" / "_v47_p4_broken_file.bak"

PASSED = 0
FAILED = 0
NOTES: List[str] = []


def check(name: str, ok: bool, detail: Any = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("  [OK]   " + name + (((" — " + str(detail))) if detail else ""))
    else:
        FAILED += 1
        print("  [FAIL] " + name + (((" — " + str(detail))) if detail else ""))


def note(text: str) -> None:
    NOTES.append(text)
    print("       " + text)


def one(cur, sql: str, params: Optional[Any] = None):
    cur.execute(sql, params if params is not None else {})
    row = cur.fetchone()
    return row[0] if row else None


def dump_size_mib(path: Path) -> float:
    """Размер выгрузки в МиБ — по нему решается, копировать её или портить на месте.

    Число называется в выводе пробы: решение «копии нет» обязано быть измеренным, а не
    выбранным по имени каталога — выгрузки меняются на диске.
    """
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return round(total / (1024 * 1024), 1)


# ── независимые измерители состояния базы ────────────────────────────────────────────
def scope_params_for(cfg_uuid: str) -> Dict[str, Any]:
    return {"cfg": str(cfg_uuid), "pt": PARENT_TYPE, "slots": list(SLOTS)}


def scope_where() -> str:
    return "WHERE configuration_uuid = %(cfg)s::uuid AND parent_type = %(pt)s"


def scope_counts(cur, cfg_uuid: str) -> Dict[str, int]:
    """Сколько строк круга узла и чужих контуров лежит в таблице сейчас.

    Чужие контуры считаются здесь же, а не «на глаз»: снятие по `configuration_uuid` без
    границы по `parent_type` сносило бы их целиком — этот дефект уже случался (раздел 10
    плана) и был пойман проверкой V32.
    """
    params = dict(scope_params())
    params["cfg"] = str(cfg_uuid)
    params["pt"] = PARENT_TYPE
    return {
        "rows": int(one(cur, "SELECT count(*) FROM " + TARGET_TABLE + " " + scope_where(),
                        params) or 0),
        "external": int(one(cur, "SELECT count(*) FROM bsl_modules WHERE parent_type IN "
                                 "('external_report', 'external_processing')") or 0),
        "common": int(one(cur, "SELECT count(*) FROM bsl_modules WHERE parent_type = "
                               "'common_modules'") or 0),
        "index_scope": int(one(
            cur,
            "SELECT count(*) FROM configuration_objects o WHERE o.configuration_id = "
            "(SELECT id FROM configurations WHERE uuid = %(cfg)s::uuid) AND "
            + scope_condition_sql(), params) or 0),
    }


def invariant_counts(cur, cfg_uuid: str) -> Dict[str, int]:
    """Нарушения инвариантов строк узла; все обязаны быть нулями.

    Каждый счётчик — отдельный вопрос, а не один общий «всё хорошо»: по одному числу не
    отличить пустой код от чужой ревизии или от строки без родителя.
    """
    params = scope_params_for(cfg_uuid)
    base = "SELECT count(*) FROM " + TARGET_TABLE + " " + scope_where()
    return {
        "bad_revision": int(one(
            cur, base + " AND (revision_no <> 1 OR changed_by <> 'load'"
                        " OR is_committed IS DISTINCT FROM true)", params) or 0),
        "bad_code": int(one(
            cur, base + " AND (code IS NULL OR btrim(code) = ''"
                        " OR code_size IS DISTINCT FROM length(code)"
                        " OR truncated IS DISTINCT FROM false)", params) or 0),
        "bad_slot": int(one(
            cur, base + " AND (NOT (module_type = ANY(%(slots)s))"
                        " OR module_name <> module_type)", params) or 0),
        "bad_path": int(one(
            cur, base + " AND (file_path IS NULL"
                        " OR position('/Ext/' in coalesce(file_path, '')) = 0"
                        " OR position(chr(92) in coalesce(file_path, '')) <> 0)", params) or 0),
        "bad_owner": int(one(
            cur,
            "SELECT count(*) FROM bsl_modules b " + scope_where().replace(
                "configuration_uuid", "b.configuration_uuid").replace(
                "parent_type", "b.parent_type")
            + " AND NOT EXISTS (SELECT 1 FROM configuration_objects o WHERE o.uuid = "
              "b.parent_uuid AND o.configuration_id = (SELECT id FROM configurations "
              "WHERE uuid = %(cfg)s::uuid))", params) or 0),
        "duplicates": int(one(
            cur, "SELECT count(*) FROM (SELECT parent_uuid, file_path FROM " + TARGET_TABLE
                 + " " + scope_where() + " GROUP BY 1, 2 HAVING count(*) > 1) d", params) or 0),
        "moments": int(one(cur, "SELECT count(DISTINCT changed_at) FROM " + TARGET_TABLE
                                + " " + scope_where(), params) or 0),
        "orphans": int(one(
            cur, "SELECT count(*) FROM bsl_modules b WHERE b.parent_type = %(pt)s AND "
                 "b.configuration_uuid = %(cfg)s::uuid AND NOT EXISTS (SELECT 1 FROM "
                 "configurations c WHERE c.uuid = b.configuration_uuid)", params) or 0),
    }


def contract_shape(report: Dict[str, Any], label: str) -> None:
    """Закрытость контракта стадии (C1): ключи ответа — ровно ключи словаря стадии."""
    base = object_modules_defaults()
    check(f"{label}: ответ содержит ровно ключи контракта стадии",
          sorted(report) == sorted(base),
          "лишнее: " + ", ".join(sorted(set(report) - set(base)))
          + "; нет: " + ", ".join(sorted(set(base) - set(report))))
    for key in ("counts_by_state", "refusals", "defects", "groups"):
        check(f"{label}: ключ {key} заполнен, а не отсутствует",
              isinstance(report.get(key), dict) and bool(report.get(key)),
              str(report.get(key)))


def render_lines(report: Dict[str, Any], label: str) -> str:
    """Текст раздела по форматёру контракта — тем же, что печатает карточка загрузки."""
    lines = format_object_module_lines(report, indent="")
    check(f"{label}: форматёр выдал строки", bool(lines), len(lines))
    joined = "\n".join(lines)
    if not report.get("success"):
        check(f"{label}: отказ назван прямо (не нулями)",
              "Стадия не выполнена" in joined or "Стадия не удалась" in joined, joined[:200])
        check(f"{label}: ответ требует полной перезагрузки (Q4.1)",
              OBJECT_MODULES_RELOAD_HINT in joined)
    return joined


# ── контур 1: отказы точки входа стадии (записи быть не должно) ──────────────────────
def contour_refusals(cur, dump_dir: Path, cfg_uuid: str, baseline: Dict[str, int]) -> None:
    """Дешёвые проверки раньше дорогих (следствие правила перезагрузки, Q4.1).

    Каждый отказ обязан быть назван текстом и не оставить в таблице ни строки: «половина
    круга» в ответе об отказе — то же самое, что незакрытая группа в ответе об успехе.
    """
    print("\n=== отказы точки входа (записи быть не должно) ===")

    unloaded = DUMP_ROOT / UNLOADED_DUMP
    if unloaded.is_dir():
        report = load_object_modules(str(unloaded))
        check("отказ: заголовка этой конфигурации в базе нет",
              not report["success"] and report["status"] == STATUS_ERROR,
              report.get("reason"))
        check("отказ называет причину словами «не найдена»",
              "не найдена" in str(report.get("reason") or ""))
        contract_shape(report, "отказ: заголовка нет")
        render_lines(report, "отказ: заголовка нет")
    else:
        note(f"каталога {UNLOADED_DUMP} среди выгрузок нет — контур не пройден, а не "
             "пропущен молча")

    other = one(cur, "SELECT uuid::text FROM configurations WHERE uuid <> %s::uuid "
                     "ORDER BY id LIMIT 1", [str(cfg_uuid)])
    if other:
        report = load_object_modules(str(dump_dir), configuration_uuid=other)
        check("отказ: два источника указали на разные конфигурации",
              not report["success"] and "Передан configuration_uuid" in str(
                  report.get("reason") or ""), report.get("reason"))
        check("отказ называет оба uuid, а не выбирает один молча",
              str(cfg_uuid) in str(report.get("reason") or "")
              and str(other) in str(report.get("reason") or ""))
        contract_shape(report, "отказ: чужой uuid")
        render_lines(report, "отказ: чужой uuid")
    else:
        note("в базе нет другой конфигурации — контур чужого uuid нечем проверить")

    report = load_object_modules(str(DUMP_ROOT))
    check("отказ: в каталоге нет Configuration.xml",
          not report["success"] and report["status"] == STATUS_ERROR, report.get("reason"))
    contract_shape(report, "отказ: каталога нет")
    render_lines(report, "отказ: каталога нет")

    # Индекс состава не разобран → круг не определён: это `not_run`, а не нулевой успех (C2).
    report = mark_index_unavailable("ConfigDumpInfo.xml не найден")
    check("пропуск стадии из-за неразобранного круга помечен not_run, а не нулями",
          report["status"] == STATUS_NOT_RUN and not report["success"]
          and report["error"] is None and bool(report["reason"]), report["reason"])
    contract_shape(report, "пропуск: круга нет")
    text = render_lines(report, "пропуск: круга нет")
    check("текст пропуска отличается от текста отказа записи",
          "Стадия не выполнена" in text, text[:160])

    after = scope_counts(cur, cfg_uuid)
    check("ни один отказ не записал и не снял строк круга",
          after["rows"] == baseline["rows"] and after["external"] == baseline["external"]
          and after["common"] == baseline["common"], f"{baseline} → {after}")


# ── контур 2: конвейер вызывает стадию сам (без флага просьбы) ───────────────────────
def contour_pipeline(cur, dump_dir: Path, cfg_uuid: str, chosen: str,
                    baseline: Dict[str, int]) -> Dict[str, int]:
    """`load_catalog(..., force=True)` обязан вызвать модульную стадию (решение Q4)."""
    print(f"\n=== конвейер: стадия S4b внутри load_catalog ({chosen}, force=True) ===")
    started = time.perf_counter()
    result = load_catalog(str(dump_dir), force=True)
    total_seconds = round(time.perf_counter() - started, 2)
    card = format_load_result(result)

    check("конвейер вернул успех", result.get("success") is True, result.get("error"))
    part = result.get("object_modules") or {}
    check("конвейер вернул раздел стадии (ключа «нет» у ответа быть не может — C1)",
          bool(part))
    contract_shape(part, "конвейер")
    check("стадия выполнена: флага просьбы нет, код читается всегда (Q4)",
          part.get("status") == STATUS_OK and part.get("success") is True,
          part.get("error") or part.get("reason") or part.get("status"))

    counts = scope_counts(cur, cfg_uuid)
    states = part.get("counts_by_state") or {}
    written = int(part.get("written") or 0)
    check("число строк в базе совпано с числом ответа стадии",
          counts["rows"] == written, f"база {counts['rows']}, ответ {written}")
    check("записанное равно состоянию `file` из обхода круга",
          int(states.get("file") or 0) == counts["rows"],
          f"file={states.get('file')}, строк={counts['rows']}")
    closed = (counts["rows"] + int(states.get("empty_file") or 0)
              + int(states.get("indexed_no_file") or 0))
    check("круг замкнут: строки + пустые + без файла = записей индекса в круге",
          closed == counts["index_scope"],
          f"{counts['rows']}+{states.get('empty_file')}+{states.get('indexed_no_file')}"
          f" != {counts['index_scope']}")
    check("файлов без текста после нормализации названы, а не промолчаны",
          int(part.get("empty_after_strip") or 0) <= int(states.get("empty_file") or 0),
          f"empty_after_strip={part.get('empty_after_strip')}, "
          f"empty_file={states.get('empty_file')}")
    check("отказов вывести путь и дефектов данных нет (ожидание прогона — нули)",
          not any(int(v or 0) for v in (part.get("refusals") or {}).values())
          and not any(int(v or 0) for v in (part.get("defects") or {}).values()),
          f"refusals={part.get('refusals')}, defects={part.get('defects')}")
    check("состояние `undecoded` пусто: строгое раскодирование прошло целиком",
          int(states.get("undecoded") or 0) == 0, states.get("undecoded"))
    if chosen in ROW_EXPECTATION:
        check(f"число строк совпано с эталоном плана П6 ({chosen} "
              f"{ROW_EXPECTATION[chosen]})", written == ROW_EXPECTATION[chosen], written)

    groups = part.get("groups") or {}
    check("группы круга названы числом (атом полноты — Q4)",
          int(groups.get("seen") or 0) > 0 and int(groups.get("with_rows") or 0) > 0,
          groups)
    check("символы кода посчитаны и не равны нулю",
          int(part.get("code_chars") or 0) > 0, part.get("code_chars"))

    for key, value in invariant_counts(cur, cfg_uuid).items():
        if key == "moments":
            check("строки одной загрузки несут один штамп времени (M2)", value == 1, value)
        else:
            check(f"инвариант строк узла: {key}", value == 0, value)

    check("чужие контуры bsl_modules конвейер не трогает",
          counts["external"] == baseline["external"]
          and counts["common"] == baseline["common"],
          f"базовое {baseline['external']}/{baseline['common']} → "
          f"{counts['external']}/{counts['common']}")

    reltuples = int(one(cur, "SELECT reltuples FROM pg_class WHERE relname = %s",
                        [TARGET_TABLE]) or 0)
    check("статистика таблицы пересобрана: reltuples > 0 (мера V46)", reltuples > 0,
          reltuples)
    check("стадия сообщила о пересборке статистики",
          int(part.get("statistics_refreshed") or 0) >= 1,
          part.get("statistics_refreshed"))

    check("успешная загрузка не помечена неполной",
          result.get("load_incomplete") is False
          and result.get("incomplete_groups") == [],
          f"{result.get('load_incomplete')} / {result.get('incomplete_groups')}")
    check("карточка содержит раздел стадии S4b", OBJECT_MODULES_SECTION_HEADER in card)
    check("карточка называет границу круга узла", OBJECT_MODULES_BOUNDARY in card)
    check("карточка называет состояния без строк (Q2) числом",
          "Состояния записей круга" in card)
    check("карточка не утверждает незакрытую группу при успехе",
          "Конфигурация неполная" not in card)
    check("прежние стадии конвейера не сломаны (S3, S4)",
          (result.get("root_modules") or {}).get("success") is True
          and (result.get("child_objects") or {}).get("success") is True,
          f"S3={((result.get('root_modules') or {}).get('error'))}, "
          f"S4={((result.get('child_objects') or {}).get('error'))}")

    note(f"ЗАМЕР ВРЕМЕНИ: стадия модулей {part.get('seconds')} с, весь вызов загрузки "
         f"{total_seconds} с; строк {counts['rows']}, символов кода "
         f"{part.get('code_chars')}, групп {groups.get('seen')}")
    return counts


# ── контур 3: вторая загрузка той же выгрузки (идемпотентность) ──────────────────────
def contour_idempotent(cur, dump_dir: Path, cfg_uuid: str, counts: Dict[str, int]) -> None:
    """Повтор не имеет права удвоить строки круга (решение Q4.1, мера V46)."""
    print("\n=== вторая загрузка той же выгрузки: идемпотентность ===")
    # Пауза не «ради паузы»: `changed_at` — TIMESTAMP без долей секунды, и две загрузки
    # внутри одной секунды получили бы одну метку; без паузы проверялись бы часы, а не
    # поведение слоя.
    time.sleep(1.1)
    result = load_catalog(str(dump_dir), force=True)
    part = result.get("object_modules") or {}
    check("вторая загрузка успешна", result.get("success") is True, result.get("error"))
    check("стадия второй загрузки выполнена", part.get("status") == STATUS_OK,
          part.get("error") or part.get("status"))

    again = scope_counts(cur, cfg_uuid)
    check("круг не вырос: повтор той же выгрузки не создаёт дублей",
          again["rows"] == counts["rows"], f"{counts['rows']} → {again['rows']}")
    removed_by_header = int(((result.get("replaced") or {}).get("children_deleted")
                             or {}).get("bsl_modules") or 0)
    check("прежние строки круга узла сняты вместе с заголовком (граница по parent_type)",
          removed_by_header >= counts["rows"], removed_by_header)
    check("стадия повторно ничего не снимала: строки уже сняты с заголовком",
          int(part.get("removed_previous") or 0) == 0, part.get("removed_previous"))
    check("числа второй загрузки совпаны с базой",
          again["rows"] == int(part.get("written") or 0),
          f"база {again['rows']}, ответ {part.get('written')}")
    for key, value in invariant_counts(cur, cfg_uuid).items():
        if key == "moments":
            check("вторая загрузка — один штамп времени, а не смесь двух (M2)",
                  value == 1, value)
        else:
            check(f"инвариант после второй загрузки: {key}", value == 0, value)


# ── контур 4: принудительный отказ группы (критерий 8 плана) ─────────────────────────
def contour_forced_failure(cur, dump_dir: Path, cfg_uuid: str, expected_rows: int,
                          baseline: Dict[str, int]) -> None:
    """Битый файл модуля: стадия обязана отказать и назвать группу (C5, Q4).

    Файл берётся из середины обхода, а `PAGE_SIZE` писателя уменьшается на время пробы:
    иначе для маленькой выгрузки до отказа не была бы записана ни одна страница, и
    компенсирующий снятие (`abandon_written_rows`) остался бы непроверенным.

    Большие выгрузки не копируются: копия BGU2 — 5.3 ГиБ и 79 137 файлов, что дороже всего
    замера (проверено на прогоне 28.10.2026: копирование длилось дольше, чем загрузка).
    У такой выгрузки файл портится на месте, а его байты сохраняются в `_scratch/` ДО
    правки и восстанавливаются из файла, а не из памяти: обрыв пробы не должен оставить
    исходную выгрузку битой, и путь бэкапа называется в выводе.
    """
    print("\n=== принудительный отказ группы: файл, который не раскодировать ===")
    size_mib = dump_size_mib(dump_dir)
    copy_work = size_mib <= COPY_LIMIT_MIB
    if copy_work:
        if not BROKEN_DIR.parent.exists():
            BROKEN_DIR.parent.mkdir(parents=True, exist_ok=True)
        if BROKEN_DIR.exists():
            shutil.rmtree(BROKEN_DIR)
        shutil.copytree(dump_dir, BROKEN_DIR)
        work_dir = BROKEN_DIR
        note(f"выгрузка {size_mib:.1f} МиБ — копия в {BROKEN_DIR}")
    else:
        work_dir = dump_dir
        note(f"выгрузка {size_mib:.1f} МиБ > {COPY_LIMIT_MIB} МиБ — копия НЕ создаётся "
             f"(цена копии больше цены замера); файл порится на месте {dump_dir.name}, "
             f"байты сохраняются в {BACKUP_FILE}")

    items = [item for item in iter_module_rows(cur, cfg_uuid, None, {},
                                               dump_dir=str(work_dir))
             if item.get("state") == STATE_FILE]
    if len(items) < 3:
        note(f"круг выгрузки слишком мал для отказа в середине ({len(items)} файлов) — "
             "контур не пройден, а не пропущен молча")
        if copy_work:
            shutil.rmtree(BROKEN_DIR, ignore_errors=True)
        return

    target = items[len(items) // 2]
    broken_path = Path(str(target["derived"]["abs_path"]))
    BACKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    original_bytes = broken_path.read_bytes()
    BACKUP_FILE.write_bytes(original_bytes)
    broken_path.write_bytes(BROKEN_BYTES)
    page_default = module_writer.PAGE_SIZE
    module_writer.PAGE_SIZE = 10
    restored_same = False
    try:
        result = load_catalog(str(work_dir), force=True)
    finally:
        module_writer.PAGE_SIZE = page_default
        broken_path.write_bytes(BACKUP_FILE.read_bytes())
        restored_same = broken_path.read_bytes() == original_bytes
        BACKUP_FILE.unlink(missing_ok=True)
    check("файл выгрузки восстановлен байт в байт (проба не оставляет битой выгрузки)",
          restored_same, f"{broken_path} ({len(original_bytes)} байт)")
    card = format_load_result(result)
    part = result.get("object_modules") or {}

    check("заголовок и прежние стадии зафиксированы (смысл границы D7 не отменён)",
          result.get("success") is True
          and (result.get("root_modules") or {}).get("success") is True
          and (result.get("child_objects") or {}).get("success") is True,
          result.get("error"))
    contract_shape(part, "отказ группы")
    check("стадия отказала, а не отчиталась нулями",
          part.get("status") == STATUS_ERROR and part.get("success") is False,
          part.get("status"))
    check("отказ назван состоянием чтения `undecoded`, а не потерянной строкой",
          int((part.get("counts_by_state") or {}).get("undecoded") or 0) == 1,
          part.get("counts_by_state"))
    check("причина отказа — строгое раскодирование (C5)",
          "не раскодирован" in str(part.get("refusal") or ""), part.get("refusal"))
    check("отказ называет и число групп круга, а не только ту, что не закрыта",
          int((part.get("groups") or {}).get("seen") or 0) > 0, part.get("groups"))
    check("названа именно та группа, чей файл испорчен",
          part.get("failed_group") == target.get("group"),
          f"ответ: {part.get('failed_group')}, ожидалось: {target.get('group')}")
    check("названа запись, на которой остановились",
          part.get("failed_record") == target.get("name"),
          f"ответ: {part.get('failed_record')}, ожидалось: {target.get('name')}")
    check("вставленное до отказа снято компенсирующим удалением (Q4)",
          int(part.get("compensated_rows") or 0) > 0, part.get("compensated_rows"))
    counts_after = scope_counts(cur, cfg_uuid)
    check("в таблице не осталось ни одной строки круга — половины группы нет",
          counts_after["rows"] == 0, counts_after["rows"])
    check("ответ загрузки помечен как неполный (критерий 8)",
          result.get("load_incomplete") is True
          and target.get("group") in (result.get("incomplete_groups") or []),
          result.get("incomplete_groups"))
    check("карточка говорит «Конфигурация неполная» и называет группу",
          "Конфигурация неполная" in card and str(target.get("group")) in card)
    check("карточка требует полную перезагрузку и не обещает повтор стадии отдельно",
          OBJECT_MODULES_RELOAD_HINT in card and "load_1c_catalog_tool" in card)
    check("карточка называет незакрытую группу в разделе стадии",
          "Группа объектов не загружена" in card)
    check("чужие контуры не пострадали и от отказа",
          counts_after["external"] == baseline["external"], counts_after["external"])

    print("\n=== восстановление: полная перезагрузка исправленной выгрузки ===")
    restored = load_catalog(str(dump_dir), force=True)
    final = scope_counts(cur, cfg_uuid)
    check("после исправления полная перезагрузка закрывает круг",
          restored.get("success") is True and final["rows"] == expected_rows,
          f"строк {final['rows']}, ожидалось {expected_rows}")
    check("после восстановления загрузка снова не помечена неполной",
          restored.get("load_incomplete") is False, restored.get("load_incomplete"))
    if copy_work:
        shutil.rmtree(BROKEN_DIR, ignore_errors=True)
        note(f"копия выгрузки снята: {BROKEN_DIR}")
    else:
        note(f"копии не было; файл {broken_path.name} восстановлен, бэкап снят")


def main() -> int:
    chosen = next((arg for arg in sys.argv[1:] if arg in DUMP_NAMES), "MinCfg")
    dump_dir = DUMP_ROOT / chosen
    if not dump_dir.is_dir():
        print(f"Каталог выгрузки не найден: {dump_dir}")
        return 2
    info = configuration_uuid_from_layout(str(dump_dir))
    if "uuid" not in info:
        print(f"uuid конфигурации из каталога не получен: {info.get('error')}")
        return 2
    cfg_uuid = str(info["uuid"])
    print(f"Проба V47 П4: стадия модулей объектов внутри конвейера — {chosen} "
          f"({DUMP_HINT.get(chosen, '')}), uuid={cfg_uuid}")
    print("Конвейер вызывает стадию без флага просьбы (Q4); строки круга остаются в базе — "
          "это результат загрузки конфигурации, а не мусор пробы.")

    conn = connect()
    try:
        cur = conn.cursor()
        loaded_name = one(cur, "SELECT name FROM configurations WHERE uuid = %s::uuid "
                               "ORDER BY id LIMIT 1", [cfg_uuid])
        baseline = scope_counts(cur, cfg_uuid)
        note(f"базовое состояние: {baseline}"
             + (f"; заголовок загружен как «{loaded_name}»" if loaded_name
                else "; заголовка этой конфигурации в базе нет — первая загрузка создаст "
                   "его, а не перезапишет"))
        if loaded_name and not baseline["index_scope"]:
            note("записей индекса в круге у загруженной конфигурации нет: круг пуст, и "
                 "стадия обязана сказать это, а не отчитаться нулями")

        contour_refusals(cur, dump_dir, cfg_uuid, baseline)
        counts = contour_pipeline(cur, dump_dir, cfg_uuid, chosen, baseline)
        contour_idempotent(cur, dump_dir, cfg_uuid, counts)
        contour_forced_failure(cur, dump_dir, cfg_uuid, counts["rows"], baseline)

        final = scope_counts(cur, cfg_uuid)
        note(f"итоговое состояние: {final}")
        conn.commit()
    finally:
        conn.close()
    return _summary()


def _summary() -> int:
    """Итог пробы: число проваленных проверок, а не общее «успешно»."""
    print("\n" + "=" * 72)
    print(f"ИТОГ: пройдено {PASSED}, провалено {FAILED}")
    if FAILED:
        print("Проваленные проверки перечислены выше строками [FAIL]; причина называется "
              "там же — молчать про них итог не должен.")
    return FAILED


if __name__ == "__main__":
    sys.exit(main())






