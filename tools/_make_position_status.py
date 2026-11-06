#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_make_position_status.py — состояние позиций нормативного списка порождается прогоном.

Узел V61, шаг П1 (06.11.2026).

Зачем. Модель сценария `docs/config-scenarios/01_configuration.md` держала закрытие
позиций прозой: абзацы «Дополнено узлом VNN» повторяли перечень «С <дата> закрытыми
являются …» — шесть датированных копий одного состояния, расходящихся с каждым новым
узлом. Шаг П7 узла V58 правил ровно этот класс расхождений в тринадцати местах живого
документа, и план узла называл правку текстов отдельным шагом. Причина не в тексте, а в
том, что выводимое состояние хранилось как проза: позиция, стадия, узел, таблица и
витрина уже есть в коде контракта и в живой схеме, а перечень в модели — вторая копия.

Здесь состояние выводится из источников, которые его задают:

  * нормативный список оператора (файл вне репозитория, читается `read_normative` из
    `tools/check_stage_order_against_normative_list.py`) — круг позиций, их порядок и
    метатег вида;
  * `STAGES` (`src/configuration_load_contract.py`) — какая позиция закрыта какой стадией;
  * `ordered_specs()` (`src/configuration_position_spec.py`) — таблицы и витрины позиций
    пакета V59 и их круг по четырём выгрузкам;
  * живая схема `ckb_1c_configurations` — есть ли таблица и витрина позиции на самом деле;
  * имена постоянных проверок `tools/check_vNN_<таблица>.py` — каким узлом доказана позиция.

Чего прогон НЕ выдумывает:
  * числа круга позиций V46…V58 — они живут в проверке позиции, и генератор называет
    файл проверки, а не копирует числа (правило слоя: число обязывает источник);
  * позиции без стадии не получают ни таблицы, ни узла — вердикт «не закрыта»;
  * двух позиций с единой таблицей нет (2.1, 2.2 — содержимое детей): это названо
    исключением с причиной в `POSITION_TABLE_EXCEPTIONS`, а не оставлено пустой клеткой.

Что делает прогон:
  1. `--print` — печатает блок в консоль, файл не трогает (режим замера П0);
  2. `--write` — заменяет блок между маркерами в модели (повторный прогон заменяет,
     а не добавляет второй — приём `tools/_make_position_frame.py`);
  3. печатает числа: позиций, закрытых, закрытых без таблицы в живой схеме (расхождение
     называется, а не сглаживается).

Сверку «текст раздела в модели равен выводу генератора» держит пункт 8 проверки
`python tools/check_position_frame.py` — тот же приём, что сверка DDL с `_make_position_frame.py`.

Запуск из корня репозитория:
    python tools/_make_position_status.py --print
    python tools/_make_position_status.py --write
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from db_env import subprocess_env  # noqa: E402  (узел V60: значения подключения из .env)
from configuration_position_spec import (  # noqa: E402
    FRAME_NODE, MEASURE_DATE, ordered_specs, expected_total,
)
from check_stage_order_against_normative_list import (  # noqa: E402
    NORMATIVE_LIST, position_sort_key, read_normative, stage_positions,
)
from configuration_load_contract import STAGES  # noqa: E402

PSQL = r"C:\Postgres\bin\psql.exe"
DATABASE = "ckb_1c_configurations"
MODEL = ROOT / "docs" / "config-scenarios" / "01_configuration.md"

MARK_BEGIN = ("<!-- BEGIN generated: состояние позиций нормативного списка "
              "(порождает прогон tools/_make_position_status.py, узел V61) -->")
MARK_END = "<!-- END generated: состояние позиций -->"

# Позиции, у которых нет одной таблицы позиции: закрытие разложено по нескольким таблицам
# содержимого. Причина держится здесь, потому что пустая клетка в таблице неотличима от
# «позабыли» (тот же приём, что `NON_POSITION_STAGES` в проверке порядка).
POSITION_TABLE_EXCEPTIONS = {
    "2.1": ("несколько таблиц содержимого детей конфигурации (реквизиты, табличные части, "
            "формы, макеты)", "V46"),
    "2.2": ("несколько таблиц содержимого детей конфигурации (команды, права, индексы "
            "состава)", "V46"),
}

# Имя таблицы позиции выводится из метатега, но у одной позиции вывод промахивается — и это
# назвал прогон узла V61 (замер 06.11.2026 по живой схеме), а не память об узле V57:
# метатег каталога `FunctionalOptionsParameters` даёт `functional_options_parameters`, а
# узел V57 построил таблицу от единственного числа вида метаданных
# (`FunctionalOptionsParameter`) — `functional_option_parameters`. Переименования схемы не
# было, поэтому расхождение держится здесь именованным исключением с причиной: молчаливая
# подмена имени в генераторе скрыла бы, что правило вывода имени не универсально.
# Исключение НЕ отключает сверку с живой схемой — отношение по-прежнему ищется в базе.
POSITION_TABLE_OVERRIDES = {
    "2.12": ("functional_option_parameters", "v_current_functional_option_parameters",
             "имя построено узлом V57 от единственного числа вида метаданных, а не от "
             "метатега каталога (замер живой схемы 06.11.2026)",
             "tools/check_v57_functional_options_parameters.py"),
}


# Акронимы (`XDTO`, `WS`) остаются слитными: без этого `XDTOPackages` дал бы
# `x_d_t_o_packages`, и живой поиск таблицы промахнулся бы молча.
_CAMEL_RE = re.compile(r"([A-Z]+)(?=[A-Z][a-z])|([A-Z][a-z0-9]*)|([A-Z]+)")


def table_name_of(metatag: str) -> str:
    """Имя таблицы позиции выводится из метатега вида (прецедент имён V48…V59)."""
    parts = [g.lower() for m in _CAMEL_RE.finditer(metatag)
             for g in m.groups() if g]
    return "_".join(parts)


def psql(query: str) -> list:
    """Строки ответа базы. Роль `postgres` названа явно: роли Windows-пользователя нет."""
    result = subprocess.run(
        [PSQL, "-U", "postgres", "-h", "localhost", "-tA", "-P", "pager=off",
         "-P", "footer=off", "-d", DATABASE, "-c", query],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=subprocess_env())
    if result.returncode != 0:
        raise RuntimeError(f"psql rc={result.returncode}: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def live_relations() -> dict:
    """Имя отношения → вид (`r` таблица, `v` витрина) по живой схеме."""
    rows = psql("SELECT c.relname, c.relkind FROM pg_class c "
                "JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind IN ('r','v')")
    return {name: kind for name, kind in (row.split("|") for row in rows)}


def check_file_of(table: str) -> str:
    """Постоянная проверка позиции — по имени файла (`tools/check_vNN_<таблица>.py`)."""
    matches = sorted(ROOT.glob(f"tools/check_v*_{table}.py"))
    return f"tools/{matches[0].name}" if matches else "—"


def node_of_position(check_file: str) -> str:
    """Узел позиции — по имени её постоянной проверки.

    Имя файла проверки совпадает с именем таблицы позиции по построению узлов V48…V58,
    поэтому узел выводится, а не переписывается памятью. Для пакета V59 узел даёт
    спецификация (`FRAME_NODE`), для позиции без проверки — вердикт «не назван».
    """
    if check_file == "—":
        return "не назван"
    m = re.search(r"check_v(\d+)_", Path(check_file).name)
    return f"V{m.group(1)}" if m else "не назван"


def build_rows():
    """Строки реестра состояний и его счётчики. Ни одного числа не берётся из памяти."""
    if not NORMATIVE_LIST.exists():
        raise SystemExit(
            f"нормативный список не найден: {NORMATIVE_LIST} — пустой прогон означал бы, "
            "что позиций не существует")
    positions = read_normative(NORMATIVE_LIST)
    stage_of = {}
    for stage_id, nums in stage_positions():
        for num in nums:
            stage_of[num] = stage_id
    specs = {spec["position"]: spec for spec in ordered_specs()}
    live = live_relations()

    rows = []
    counters = {"closed": 0, "open": 0, "no_table": 0, "no_view": 0}
    for num in sorted(positions, key=position_sort_key):
        kind_name, metatag = positions[num]
        stage_id = stage_of.get(num)
        if stage_id is None:
            counters["open"] += 1
            rows.append((num, f"{kind_name.strip()} (`{metatag}`)", "—", "—", "—", "—",
                         "позиция не закрыта: стадии в `STAGES` нет"))
            continue
        counters["closed"] += 1
        spec = specs.get(num)
        exception = POSITION_TABLE_EXCEPTIONS.get(num)
        if spec is not None:
            table, view = spec["table"], spec["view"]
            node, check_file = FRAME_NODE, "tools/check_position_frame.py"
        elif exception is not None:
            table, view, node, check_file = exception[0], "—", exception[1], "—"
        else:
            override = POSITION_TABLE_OVERRIDES.get(num)
            if override is not None:
                table, view, _reason, check_file = override
            else:
                table = table_name_of(metatag)
                view = f"v_current_{table}"
                check_file = check_file_of(table)
            node = node_of_position(check_file)
            if live.get(table) != "r":
                counters["no_table"] += 1
                table = f"`{table}` — ⚠️ таблицы нет в живой схеме"
            else:
                table = f"`{table}`"
            if live.get(view) != "v":
                counters["no_view"] += 1
                view = f"`{view}` — ⚠️ витрины нет в живой схеме"
            else:
                view = f"`{view}`"
        rows.append((num, f"{kind_name.strip()} (`{metatag}`)", f"`{stage_id}`", node,
                     table, view, check_file))
    return rows, counters, len(positions)


def render_block() -> str:
    """Текст раздела между маркерами — ровно то, что обязана содержать модель."""
    rows, counters, total = build_rows()
    lines = [
        MARK_BEGIN,
        "",
        "### Состояние позиций нормативного списка — реестр, порождается прогоном",
        "",
        "Раздел порождается прогоном `python tools/_make_position_status.py` и правится только",
        "им: править строки таблицы вручную — значит завести вторую копию состояния, что и было",
        "причиной тринадцати правок шага П7 узла V58. Столбцы выводятся из нормативного списка",
        "оператора, `STAGES`, спецификации позиций пакета V59, живой схемы",
        f"`ckb_1c_configurations` и имён постоянных проверок. Дата замера круга пакета — {MEASURE_DATE}.",
        "",
        "| позиция | вид (метатег) | стадия | узел | таблица | витрина | проверка позиции |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    if POSITION_TABLE_OVERRIDES:
        lines += ["", "Имена отношений, которые НЕ выводятся из метатега вида (держатся",
                  "`POSITION_TABLE_OVERRIDES` с причиной, а не подменяются молча):", ""]
        for num, (table, view, reason, _check_file) in sorted(
                POSITION_TABLE_OVERRIDES.items(), key=lambda kv: position_sort_key(kv[0])):
            lines.append(f"- позиция **{num}** — таблица `{table}`, витрина `{view}`: {reason};")
    lines += [
        "",
        f"Закрыто позицией или стадией: **{counters['closed']} из {total}**; без стадии — "
        f"{counters['open']}.",
        f"Закрытых позиций без таблицы в живой схеме: {counters['no_table']}, без витрины: "
        f"{counters['no_view']}. Нуль означает, что таблица и витрина позиции есть в базе, "
        "а не обещаны текстом.",
        "",
        "Числа круга по выгрузкам здесь не переписываются: для пакета V59 их держит "
        "спецификация `src/configuration_position_spec.py` и сверяет `tools/check_position_frame.py`, "
        "для позиций V48…V58 — проверка из последнего столбца.",
        "",
        MARK_END,
    ]
    return "\n".join(lines) + "\n"


def extract_block(text: str):
    """Текст между маркерами в файле — или None, если раздел ещё не вставлен."""
    start = text.find(MARK_BEGIN)
    end = text.find(MARK_END)
    if start == -1 or end == -1:
        return None
    return text[start:end + len(MARK_END)] + "\n"


def write_model() -> str:
    """Врезка или замена блока между маркерами (приём `_make_position_frame.py`)."""
    text = MODEL.read_text(encoding="utf-8")
    block = render_block()
    old = extract_block(text)
    if old is not None:
        MODEL.write_text(text.replace(old, block), encoding="utf-8")
        return "заменён"
    anchor = "Ниже — сверка плана с реальной XML-выгрузкой конфигурации BGU2"
    if anchor not in text:
        raise SystemExit(f"якорь вставки не найден: {anchor!r} — раздел не вставлялся")
    MODEL.write_text(text.replace(anchor, block + "\n" + anchor, 1), encoding="utf-8")
    return "вставлен перед разделом сверки плана с выгрузкой"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="заменить блок между маркерами в модели (по умолчанию — печать)")
    args = ap.parse_args()

    print(render_block())
    if args.write:
        action = write_model()
        print(f"Раздел в модели: {MODEL.relative_to(ROOT)} — блок {action}")
    else:
        print("(режим замера: файл не изменён; запись — флагом --write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
