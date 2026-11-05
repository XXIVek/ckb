#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел журнала `rules:journal:node:root-files` — снимок разбора состава корня.

Зачем: карточка `rules:checks:root-hygiene` называет числа разбора и ссылается на этот узел
(прозаическое упоминание адресом не является, а ссылка на несуществующую карточку — провал
проверки адресной достижимости). Снимок нужен и потому, что действующая карточка правила
намеренно не держит чисел: она описывает состояние, а числа — запись прогона на дату.

Формат — ряд журнала этого же слоя (`rules:journal:node:probes-layout`): разделы
`===WHEN===` / `===SNAPSHOT===` / `===GUARD===` / `===SOURCE===`, теги берутся у строки ряда,
ключ идемпотентности — `source_url` (уникального ограничения на него в схеме нет, приём взят у
`probes/misc/_add_core_journal_nodes.py`). Строка оглавления добавляется в `rules:journal:index`
до перегенерации — так требует раздел GUARD прежнего узла.

Запуск:
    python probes/misc/_add_root_files_journal_node.py            # что будет сделано
    python probes/misc/_add_root_files_journal_node.py --write    # записать
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import rules_layer as RL  # noqa: E402
from database import get_cursor  # noqa: E402

ADDRESS = "rules:journal:node:root-files"
SERIES = "rules:journal:node:probes-layout"   # строка ряда: тот же слой, та же дата
INDEX = "rules:journal:index"


TEXT = """===WHEN===
Снимок узла ROOT-FILES (05.11.2026): продолжение разбора корня репозитория узлом
ROOT-RESTRUCTURE (05.11.2026). Карточка журнала — снимок, а не действующее правило; тексты
журнала не правятся. Действующее правило размещения — `rules:checks:root-hygiene`.

===SNAPSHOT===
Прежнее состояние (замер `_scratch/root_nonpy_inventory.py`, 05.11.2026): в корне 332 файла
рядом с 14 точками входа. Из них 34 файла поставки схемы (`create_1c_configurations_db.sql`,
`migrate_v*.sql`, `check_external_report_*.sql`), 39 измерителей и фикстур чужих узлов
(`_v22_invariants.sql`, `_d1_*.ps1/.vbs`, `_v46_props_*.json`, `_v54_p5_card_min.cfg`),
3 документа-одиночки (`XSD-INSTRUCTIONS.md`, промпт узла V52, handoff от 24.10.2026),
238 файлов вывода замеров (`.txt`, `.log`, `.err` и снятые `.json`), 3 черновых запроса
(`_q.sql`, `_q2.sql`, `_q3.sql`) и дамп базы 108 МБ. Узел ROOT-RESTRUCTURE разложил только
`.py`: остальные классы никто не считал, поэтому и разложения у них не было.

Что сделано (признак класса — использование файла, а не имя; тот же признак, что у узла
ROOT-RESTRUCTURE). Всего 318 действий: `git mv` 76, `git rm` 3 (черновые запросы), перенос в
`_scratch/` 234, перенос с постановкой на учёт 4 (фикстуры зондов), снятие с учёта и перенос
1 (дамп базы — он и не отслеживался, `git rm --cached` на него ответил «pathspec did not
match», файл перенесён вне git).

- `sql/` — поставка схемы, 34 файла. Их открывает код: `tools/check_v32_zero_configuration.py`,
  `tools/check_v42_configuration_header.py`, `tools/check_v31_provenance.py`, зонды узлов V43,
  V50, V51, V55, V56, V57. Каталог был назван в текстах правил (`sql/check_external_report_*.sql`)
  и в `.gitignore`, но отсутствовал.
- `probes/<узел>/` — измеритель рядом с зондом, который его читает; фикстуры трекаются, потому
  что без них замер узла не воспроизвести.
- `docs/` — документ; промпт-задание узла в `docs/prompts/`, прежний текст в `docs/legacy/`.
- `_scratch/` — вывод замера. Правки путей — 29 замен, отказов 0: 17 путей поставки (добавлен
  сегмент `sql/`), 9 путей вывода, 3 чтения фикстур от своего файла
  (`Path(__file__).with_name(...)` вместо пути от каталога запуска). Генераторы зондов П8 узлов
  V54–V56 писали порождённый зонд в корень — направлены в каталог узла; `_v43_gen_sql.py`,
  `_d10_state_note.py`, `_d8_ib_bp3_with_bp3.py`, `_d9_session_meta_check.py`, `_ibcmd_probe.py`
  писали вывод в корень — направлены в `_scratch/`.
- Резолвер имён дополнен, а не переписан: `rules_layer.artifact_exists` читает `sql/` так же,
  как читал `probes/*/`. Строки правил и планов называют артефакты голыми именами — это запись
  замера на дату, менять их новым путём значит стереть вид замера.
Очистка вывода тем же признаком (`probes/misc/_root_files_scratch_clean.py`, 05.11.2026):
файл хранится, если на него есть ссылка норматива; неназванный вывод не доказывает ни одного
числа, а повторный прогон зонда даёт его заново. Ссылки собраны из двух мест, и оба
обязательны: `git grep` по отслеживаемым файлам (150 токенов) и карточки обеих баз (9 токенов;
в `ckb_1c_configurations` обращений `_scratch/` ноль — это проверено запросом, а не принято на
веру). Токен трактуется как префикс, потому что путь в коде собирается сегментами
(`BASE / "_scratch" / "<имя>.txt"`) и единого токена в строке нет.

Итог: удалено 898 файлов, 17.6 МБ; оставлено 734 файла, 15.3 МБ — вывод, названный планом,
правилом или кодом проверки (крупнейший 0.4 МБ). Не тронуты два дампа баз, 613.8 МБ
(`_backup_ckb_1c_configurations_2026-10-31.dump` 510.4 МБ, `_backup_local_doc_2026-10-27.sql`
103.4 МБ): дамп — точка восстановления, а не вывод замера, и решение о его удалении принимает
оператор. Признак дампа — имя `_backup_`, а не расширение: дамп `local_doc` лежит как `.sql`,
фильтр по расширению `.dump` пропустил бы его и удалил вместе с мусором. Каталоги фикстур и
копии конфигураций (`v48_p2_fixtures`, `v51_head`, `v52_head`) не удаляются: каталог может быть
входными данными зонда, а отсутствие ссылки в тексте этого не проверяет.

Два дефекта самой чистки найдены ею же на первом прогоне и названы, потому что это тот же
класс ошибки, что и перенос файлов: скрипт удалял файл, в который сам писал отчёт
(перенаправление `> _scratch/report.txt` делает отчёт неназванным выводом; `PermissionError`,
удаление оборвалось на середине), и мерял объём уже удалённых файлов (`FileNotFoundError`).
Исправлено: свой вывод пропускается, размер считается до `unlink`, занятый файл не роняет прогон,
а повторный прогон продолжает удаление — остаток 0 неназванных файлов.

Разбор остатка закрыт тем же днём: в репозитории копии баз не нужны вовсе. Точка восстановления
обеих баз создаётся штатным инструментом `tools/backup_databases.py` (узел ARCHIVE-BD,
03.11.2026) в каталог вне репозитория `C:\\1C_LLM\\Arhiv_BD`, где уже лежали точки 24.10, 26.10
и 03.11 с описанием `RESTORE_<база>.md` и манифестом `manifest.tsv` (sha256, состав оглавления,
контрольные счётчики, время дампа и восстановления, признак `verify=ok`). Ручная копия в
`_scratch/` — вторая, не связанная с процедурой россыпь дампов: снято четыре файла на 1292.3 МБ
(две копии 05.11 и две прежние — от 27 и 31 октября), после чего каталог весит 15.3 МБ — только
названное доказательство. Новая штатная точка снята и проверена:
`ckb_1c_configurations_2026-11-05.dump` 573.3 МБ (база 1279.9 МБ, 44 таблицы, 539 215 строк,
контрольное восстановление 30.1 с, счётчики совпали, тестовая база снята),
`local_doc_2026-11-05.dump` 106.4 МБ (база 203.1 МБ, 6 таблиц, 241 051 строка, восстановление
11.0 с). Попутно измерено ограничение сборки: `pg_dump` 17.2 собран без поддержки сжатия —
`-Z 6` даёт `invalid compression specification: this build does not support compression with
gzip`, zstd тоже отсутствует, поэтому дамп несжатый по необходимости (контракт ARCHIVE-BD держит
`-Z0`, и описание точки от 24.10 об этом уже говорит). Внешняя упаковка работает: замер —
тестовый дамп одной таблицы 324.7 МБ сжат в 30.3 МБ; это предложение оператору, а не изменение
процедуры. Постоянная защита заведена в той же проверке: `check_root_hygiene.py` держит пятый
класс — дамп базы в репозитории (`*.dump`, `*.bak`, `_backup*`) является провалом с указанием
места, где точка создаётся штатно.

===GUARD===
Чем сторожится состояние, а не только факт переноса:

- `python tools/check_root_hygiene.py` — 161 проверка, провалено 0, одно наблюдение (`INFO`):
  путь к снятому `.clinerules/1c-configurations-core_Rule.md` в миграторе — происхождение
  текста, а не битая ссылка (файл снят коммитом `d957ee2e`, узел RESTRUCTURE-LAYERS).
  Проверка держит четыре класса: файлы корня (только точки входа), каталоги корня (исходники
  требуются, рабочие материалы — числом), состав `probes/`, пути кода от основания корня
  (поставка и измерители обязаны существовать, вывод — строиться от `_scratch/`).
- `python validate_project.py` — шаг 10 из 11 вызывает эту проверку; шаг слоёв правил перестал
  быть десятым, и карточка `rules:checks:project-integration` называла номер шага числом,
  которое отстало от прогона, — число из текста снято.
- `python tools/check_rules_layer.py` — провалов 0. Число проверок здесь не называется: оно
  меняется от самой записи этой карточки и карточки правила, и называть его снимком — значит
  обязать следующий прогон совпасть с числом, зависящим от записи о прогоне.

Границы и остаток (названы, а не промолчаны):
- измеритель `_scratch/paths_resolve.py` посчитал 149 конструкций пути и 122 неразрешённых — он
  брал основания любого вида (текущий каталог, каталог зонда) и файлы вывода, которых нет между
  прогонами. Постоянная проверка на это не претендует: она разбирает только основания
  `ROOT`/`BASE`/`REPO_ROOT`, то есть ровно то, что ломается при переносе класса файлов.
- не разобрано: пути от текущего каталога (`os.path.join("src", "configuration_child_properties.py")`
  в `probes/v43/_v43_style_fix.py`, `probes/v45/_v45_probe.py`) — такие скрипты работают только
  при запуске из корня; постоянной проверкой они не покрыты, потому что текущий каталог не является
  основанием, закреплённым правилом.
- рабочие каталоги (`_ibcmd_work/`, `logs/`, `layers/`, `Arhiv_Rules/`, `_v54_raw/` и др.)
  проверка считает числом и провалом не считает: удаляет их оператор, а не проверка.

===SOURCE===
Запрос оператора от 05.11.2026: «в каталоге C:\\1C_LLM\\ckb всё ещё больше 300 файлов, с этим
надо что-то делать». Разбор и перенос — 05.11.2026; скрипты разбора и переноса —
`_scratch/root_nonpy_inventory.py`, `_scratch/path_uses.py`, `_scratch/root_io.py`,
`_scratch/sql_ast.py`, `_scratch/move_root_files.py`, `_scratch/patch_paths_after_move.py`,
`_scratch/paths_resolve.py`, `_root_files_scratch_clean.py` (очистка вывода). Действующее
правило — `rules:checks:root-hygiene`, проверка —
`tools/check_root_hygiene.py`, встройка в прогон — `validate_project.py` (карточка
`rules:checks:project-integration`)."""


# Строка оглавления журнала: формат тот же, что у строк ряда (обратные кавычки вокруг адреса
# и источника), добавляется до перегенерации — так требует GUARD прежнего узла журнала.
INDEX_ROW = ("| `rules:journal:node:root-files` | `разбор состава корня репозитория "
             "(узел ROOT-FILES, 05.11.2026): 332 файла разложены по классам (sql/, "
             "probes/<узел>/, docs/, _scratch/), заведены постоянная проверка "
             "check_root_hygiene.py и шаг прогона` | что лежало в корне и по какому признаку "
             "рассовано, какие пути правились, чем сторожится состояние и что осталось "
             "неразобранным |")


def existing_tags(cur):
    """Теги строки ряда — новый узел обязан выглядеть как строка ряда, а не как правило."""
    cur.execute("SELECT tags FROM knowledge_snippets WHERE question=%s", (SERIES,))
    row = cur.fetchone()
    if not row:
        raise SystemExit("нет строки ряда для тегов: узел журнала не найден")
    return list(row["tags"] or [])


def append_index_row(cur):
    cur.execute("SELECT id, answer FROM knowledge_snippets WHERE question=%s", (INDEX,))
    card = cur.fetchone()
    if not card:
        return "оглавление журнала не найдено — строка не добавлена"
    text = card["answer"] or ""
    if ADDRESS in text:
        return "оглавление уже содержит строку"
    lines = text.splitlines()
    last = max((i for i, line in enumerate(lines) if line.lstrip().startswith("| `rules:journal:")),
               default=None)
    if last is None:
        return "в оглавлении нет таблицы — строка не добавлена"
    lines.insert(last + 1, INDEX_ROW)
    cur.execute("UPDATE knowledge_snippets SET answer=%s WHERE id=%s",
                ("\n".join(lines), card["id"]))
    return "строка добавлена"


def main(argv=None):
    write = "--write" in (argv or sys.argv[1:])
    with get_cursor() as cur:
        tags = existing_tags(cur)
        key = f"{RL.SOURCE_SCHEME}{ADDRESS}"
        cur.execute("SELECT id FROM knowledge_snippets WHERE source_url=%s", (key,))
        known = cur.fetchone()
        print(f"{'обновлено' if known else 'создано  '}  {ADDRESS}  {len(TEXT)} симв.  теги {tags}")
        if write:
            if known:
                cur.execute("UPDATE knowledge_snippets SET answer=%s, tags=%s WHERE id=%s",
                            (TEXT, tags, known["id"]))
            else:
                cur.execute(
                    "INSERT INTO knowledge_snippets (groups_id, question, answer, source_url,"
                    " tags, confidence, is_verified) VALUES (NULL, %s, %s, %s, %s, 1.0, TRUE)",
                    (ADDRESS, TEXT, key, tags))
            print("оглавление:", append_index_row(cur))
        else:
            print("оглавление: не тронуто (нет --write)")
    print("готово" if write else "черновик: запуск без --write ничего не записал")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

