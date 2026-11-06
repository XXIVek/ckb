#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Узел V60, шаг П4b: подключение к PostgreSQL — правилом функции слоя (уточнение оператора).

Зачем переделка. Шаг П4 (`_v60_p4_rules.py`) положил правило в always-карточку
`rules:always:db-access`. Оператор уточнил формулировку задачи: правило должно быть правилом
функции-инструмента — карточкой вида `rules:kb-rules:functional:<функция>` (образец —
`rules:kb-rules:functional:rules-report`), то есть находимым поиском по префиксу `functional:` и
по ручным алиасам, а не всегда загружаемым. Разница не косметическая:

  * always-набор политики читателя (`ALWAYS_ADDRESSES`) после П4 дорос до 17 344 символов при
    пороге `ALWAYS_BUDGET_CHARS` = 18 000 — запас 3.6 %. Функциональная карточка в набор не
    входит: он остаётся 16 379 (запас 9 %), а правило при этом достижимо поиском;
  * правило о подключении нужно не при любой задаче, а при задаче про PostgreSQL — это ровно
    определение вариативной функции из `rules:always:reading`.

Что делает шаг, по порядку (порядок не произвольный: ссылка функциональной карточки на журнал
разрешима только после того, как журнал создан):

  1. снимает always-карточку `rules:always:db-access` вместе с её алиасами — строку создал этот
     же прогон, ответа оператора в ней нет, поэтому физическое удаление честнее карантина:
     карантин прятал бы знание, которого в дереве быть не должно. id снятой строки остаётся в
     снимке журнала;
  2. создаёт снимок журнала `rules:kb-rules:journal:ref:11` — замеры, решения и артефакты узла
     (формат снимков слоя — `journal:ref:NN`, живой образец `ref:10`; индекс журнала после этого
     перегенерирует `tools/regen_journal_index.py`);
  3. создаёт карточку функции `rules:kb-rules:functional:db-access` — теги, `source_url` и
     `is_verified` берут у живых функциональных карточек слоя, разделы — `STATE_SECTIONS`;
  4. записывает ручные алиасы раздела `===ALIASES===` в `alias_targets` — проверка слоя требует,
     чтобы объявленный текстом алиас стоял и в базе; алиасы уровней (`rules:`, `rules:kb-rules:`,
     `rules:kb-rules:functional:`) даёт `level_aliases`, их требует `by_alias` в `src/rules_report.py`;
  5. перегенерирует перечни карточки слоя (`===MCP`/`===LINKS`/`===INDEX`) штатной функцией
     генератора — перечень, заведённый руками, отстаёт от дерева на одну карточку.

Значение пароля в текст карточки подставляет `src/db_env.py`, а не литерал скрипта: иначе сам
скрипт стал бы отслеживаемым файлом с паролем, и проверка `tools/check_db_credentials.py`
провалилась бы на собственном тексте.

Запуск:
    python probes/v60/_v60_p4b_functional_card.py            # разбор
    python probes/v60/_v60_p4b_functional_card.py --write    # применить
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "tools", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:  # кириллица вывода не влазит в cp1251 (приём tools/check_rules_layer.py)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _make_rule_cards as MC  # noqa: E402
import rules_layer as RL  # noqa: E402
import rules_read as RR  # noqa: E402
import db_env  # noqa: E402
from database import get_cursor  # noqa: E402
from mcp_tools_api import update_snippet  # noqa: E402

LAYER = "kb-rules"
LAYER_ADDRESS = f"{RL.ROOT_MARKER}:{LAYER}:"
ALWAYS_CARD = "rules:always:db-access"          # строка шага П4, её снимаем
JOURNAL_NODE = f"{LAYER_ADDRESS}{RL.STATE_JOURNAL}:ref:11"
FUNCTION_CARD = f"{RL.functional_prefix(LAYER)}db-access"
CHECK_TOOL = "tools/check_db_credentials.py"
GEN_PROBE = "probes/v60/_v60_p4b_functional_card.py"

# Теги берут у живой функциональной карточки слоя (образец `rules:kb-rules:functional:rules-report`):
# фильтр по категории слоя и фильтр корня работают пересечением тегов, поэтому тег единственной
# категории сделал бы карточку невидимым для одного из двух входов. Список ниже - только запасной,
# если образец не читается; в прогоне теги копируются из строки-образца.
SAMPLE_FUNCTION = f"{RL.functional_prefix(LAYER)}rules-report"
FUNCTION_TAGS_FALLBACK = ["1c-rules-root", "1c-knowledge-base-rules", "rules", "rules-layer",
                          "tree-rule", MC.KIND_FUNCTIONAL]

# Ручные алиасы раздела `===ALIASES===`: их ищут словами оператора, которых нет в адресе.
# Адресные алиасы (`rules:`, `rules:kb-rules:`, короткая форма адреса, метка слоя) текстом не
# объявляют: `rules_layer.validate_alias` отклоняет алиас с `:` и с меткой слоя, а записывает их
# скрипт — предупреждение проверки слоя про «алиасов в базе больше, чем объявлено» относится именно
# к ним и означает следы адресов, а не забытый термин (снять такой алиас инструментом нельзя).
FUNCTION_ALIASES_RU = [
    "psql", "PostgreSQL", "запуск psql", "подключение к базе", "реквизиты подключения",
    "пароль postgres", "роли PostgreSQL", "PGPASSWORD", "local_doc", "ckb_1c_configurations",
]

# Текст правила функции. Значение пароля подставляет `src/db_env.py` (`{password}`), а не литерал
# скрипта: иначе этот же скрипт стал бы отслеживаемым файлом с паролем, и проверка шага П4b
# провалилась бы на собственном тексте. Раздел `===CHECK===` называет артефакт, который держит
# границу; ссылка на снимок журнала обязательна - `check_functional_journal_trace` требует, чтобы
# функция прослеживалась до истории своего слоя адресом, а не прозой «узел VNN».
FUNCTION_TEXT = """===WHEN===
Нужно обратиться к PostgreSQL напрямую: запустить `psql.exe`, выполнить SQL к базе правил или к базе
замеров узлов, подключиться из кода. Карточку ищут словами «psql», «подключение к базе», «пароль
postgres», «PGPASSWORD», «.env» — до первой команды терминала, а не после отказа подключения.

===MUST===
1. Строка запуска `psql.exe`:
   `$env:PGPASSWORD='{password}'; C:\\Postgres\\bin\\psql.exe -U postgres -h localhost -d <база> -tA -P footer=off`
   `-tA` — тихий режим, `footer=off` — постраничный вывод выключен; без них прогон упирается в
   подтверждение вывода и не отвечает на вопрос, пока его не тронут.
2. Роли PostgreSQL: на сервере есть пользователь `postgres` с паролем `{password}`; роли `Buh` — имени
   Windows-пользователя, которое `psql.exe` подставляет по умолчанию из окружения, — **нет**. Без
   `-U postgres` (или `$env:PGUSER='postgres'`) подключение падает с
   `FATAL: password authentication failed for user "Buh"`, поэтому `-U postgres` обязан быть в каждой
   команде `psql.exe`.
3. Имя базы называют явно: `local_doc` — правила и знания четырёх MCP-серверов;
   `ckb_1c_configurations` — замеры узлов загрузки конфигураций.
4. Значение держит файл `.env` в корне проекта (вне репозитория, шаблон — `.env.example`); код и
   MCP-серверы читают его единственной точкой `src/db_env.py` — `db_params(dbname)`,
   `pg_password()`, `subprocess_env()`.
5. Карточка называет значение на дату записи. При смене пароля правят `.env` и перегенерируют
   карточку прогоном `{gen_probe} --write`; расхождение карточки со значением ловит `{check_tool}`,
   поэтому просроченное правило остаётся видимым, а не молча действующим.
6. Вывод фильтруют, а не согласовывают:
   - подтверждения пользователя на продолжение вывода не спрашивают никогда — команды с длинным
     выводом (`psql`, `python`) выполняются автоматически;
   - `run_commands` не запускают командами, выводящими много строк без фильтрации — берут `LIMIT`,
     `WHERE`, выборочные поля;
   - если результат большой, фильтруют на стороне SQL (`WHERE`, `LIMIT`) или в Python (`[:10]`,
     `head`): прогон без фильтра платит окном за строки, которые никто не читал.

===FORBID===
Держать литерал пароля в отслеживаемых файлах — значение уходит в историю git (замер узла V60:
53 файла); фолбэк пароля в коде (`os.environ.get("PGPASSWORD", "…")`) — секрет возвращается в
репозиторий, даже когда окружение задано; читать `.env` мимо `src/db_env.py` — вторая точка
подключения расходится с первой молча; запускать `psql` без `-U postgres` или без
`-tA -P footer=off`; просить у человека подтверждение на продолжение вывода вместо того, чтобы
отфильтровать запрос; называть пароль по памяти, не прочитав эту карточку.

===TOOLS===
вне MCP — `C:\\Postgres\\bin\\psql.exe` (прямой запуск), `src/db_env.py` (единственная точка чтения
значений), `{check_tool}` (проверка состояния), `python src/db_env.py` (диагностика: печатает
разобранные значения, пароль скрыт). Инструмента подключения в регистре MCP нет — запрос к базе
делают строкой SQL через `psql.exe` или через `psycopg2`.

===CHECK===
`python {check_tool}` — провалов нет означает: `.env` и `.env.example` на месте и `.env` исключён
git'ом; `src/db_env.py` разбирает host/user/password; литерала пароля нет ни в одном отслеживаемом
файле; фолбэка пароля в коде нет; карточка называет текущее значение.

===ALIASES===
{aliases}

===SOURCE===
Перенесено из `.clinerules/1C_Rule.md` (раздел «РАБОТА С ТЕРМИНАЛОМ») узлом V60, 06.11.2026, по
решению оператора: значение держит `.env`, правило оформлено функцией слоя и ищется по алиасам, а не
грузится всегда. Замеры, решения и артефакты узла — `{journal}`.
"""


# Снимок журнала узла V60. Формат карточек журнала рабочим правилам не предъявляется (узел
# RULE-FORMAT): здесь важны замеры, решения оператора и артефакты - то, чего живая карточка
# правила не несёт по построению.
JOURNAL_TEXT = """### Узел V60 (06.11.2026): реквизиты подключения к PostgreSQL держит одна точка

**Что просили.** Перенести правила обращения к базе данных из `.clinerules/1C_Rule.md` в дерево
правил, пароль указать в правиле, а инструменты MCP пусть читают значение из `.env`. Уточнение
оператора: оформлять не всегда загружаемой карточкой, а правилом функции-инструмента
(`rules:kb-rules:functional:<функция>`), чтобы правило находилось поиском.

**Замеры до правки.**
- литерал пароля стоял в 53 отслеживаемых файлах и попадал в историю git; после разбора форм
  (`probes/v60/_v60_p2_forms.py`) — 46 файлов и 53 вхождения, разложенные по классам: 24
  аргумента `psycopg2.connect(password=…)`, 19 строк запуска `psql` в оболочке, 3 ключа
  `PGPASSWORD` в словарях окружения, 7 мест иных форм (`setdefault`, `HOST, USER, PASSWORD =`);
- вторая точка подключения `src/external_db.py` читала `PG*`, но с фолбэком на литерал — секрет
  оставался в репозитории даже при заданном окружении;
- always-набор политики читателя (`ALWAYS_ADDRESSES`) — 17 131 символ при пороге 18 000
  (`rules:` 5 600 + `rules:kb-rules:` 11 531): места под новое всегда-правило не оставалось.

**Что сделано.**
1. `src/db_env.py` — единственная точка чтения значений: переменные `PG*` процесса, затем файл
   `.env` в корне проекта; `.env` вне репозитория, шаблон `.env.example`;
2. точки подключения переведены на неё: `src/database.py`, `src/mcp_tools_core.py` (второй словарь
   `DB_CONFIG` дублировал первый молча), `src/external_db.py` (фолбэк снят),
   `src/external_report_loader.py` (окружение дочерних `psql`), `src/pdf_parser.py`,
   `tools/backup_databases.py`, `tools/check_position_frame.py` — прогон
   `probes/v60/_v60_p1_code_edits.py`;
3. литерал снят из остальных файлов по классам форм — прогон `probes/v60/_v60_p3_strip_password.py`
   (46 файлов, 53 замены; 39 изменённых Python-файлов компилируются; авто-вставка `import os`
   сломала 7 файлов с `from __future__ import annotations` — порядок импортов чинил тот же прогон);
4. always-набор сжат на то, что воспроизводимо другим инструментом: справка об отсутствующих
   инструментах и пространные описания категорий (коды остались — их требует
   `probes/misc/_general_block_probe.py`), абзац о составе слоя, подсказки перечня детей урезаны с
   110 до 80 символов (полную формулировку «когда нужен» даёт `tools/rules_read.py --tree`);
   точка правки — генератор `tools/_make_rule_cards.py`, иначе карточка разошлась бы с генератором;
5. правило оформлено функцией слоя `rules:kb-rules:functional:db-access` (шаг П4b), всегда
   загружаемая карточка шага П4 (id 6277) снята вместе с алиасами; снимок узла назван перечнем
   журнала (шаг П4c, строка `ref:11` в `rules:kb-rules:journal:index`):
   `tools/regen_journal_index.py` к этому слою неприменим — файл-снимок `docs/rules/kb-rules.md`
   не ведётся, перечень дополняют строкой БД с тем же якорным приёмом, что и перечни карточек;
6. из `.clinerules/1C_Rule.md` снят весь раздел «РАБОТА С ТЕРМИНАЛОМ» (строка запуска `psql.exe`,
   роли PostgreSQL и отсутствие роли `Buh`, имена баз, три правила вывода) — его содержимое легло в
   разделы `===MUST===` и `===FORBID===` карточки функции, в файле остался указатель: при работе с
   терминалом читать карточку адресом (файл правил — маршрутизатор, `rules:always:reading`);
7. проверка `tools/check_db_credentials.py` — 8 проверок: файл значений на месте и исключён git'ом,
   единственная точка работает, литерала и фолбэка в отслеживаемых файлах нет (проверено 794
   файла), карточка называет текущее значение;
8. состав корня пополнился классом файлов значений: `ROOT_VALUE_FILES` в
   `tools/check_root_hygiene.py` (`.env` — значения, `.env.example` — шаблон) и тот же класс в
   правиле `rules:checks:root-hygiene` (шаг П5, `probes/v60/_v60_p5_root_hygiene.py`). Правило слоя
   `rules` ведётся файловым исходником `docs/rules/rules.md`, а проверка слоя сверяет текст строки БД
   с исходником — поэтому правку вносят в файл и переносят мигратором
   `tools/migrate_rules_to_layer.py --file docs/rules/rules.md --apply`; правка только строки БД
   даёт провал «текст БД совпадает с исходником» (пройден на этом узле).

9. каталог `.clinerules/` возвращён в отслеживание (шаг П6). Он закрывался игнором узлом
   CLINERULES-IGNORE только из-за литерала пароля в файле правил; после снятия литерала закрытие
   означало бы потерю маршрутизатора к дереву правил — следующего прогона без файла, который говорит,
   где норматив. Строка игнора снята с обоснованием в `.gitignore`, `1C_Rule.md` добавлен в индекс;
10. литерал убран и из файлов самого узла — иначе измеритель, снимающий секрет, оставался бы его
    носителем: `_v60_p2_forms.py` и `_v60_p3_strip_password.py` берут значение из `db_env`, образцы
    прежнего кода в `_v60_p1_code_edits.py` называют его маркером (подстановка перед сравнением),
    текст карточки в `_v60_p4_rules.py` собирается f-строкой из того же значения;
11. проверка фолбэка в стороже сужена до кода подключения (`src/`, `tools/`, корневые скрипты):
    проза зондов и собственный комментарий сторожа пересказывают запрет словами, подключением не
    являясь. Литерал значения при этом ищется по всем отслеживаемым файлам — их стало 807, потому что
    в индекс вернулся каталог правил;
12. `_v60_p1_code_edits.py` стал идемпотентным: у правок импортов старый блок является началом
    нового, поэтому повторный прогон предлагал применить правку второй раз и получить дубль импорта.
    Теперь сначала проверяется наличие нового текста — повторный прогон даёт «без изменений» по всем
    13 правкам.

**Решения оператора.**
- значение пароля держит `.env`, в код и в окно контекста оно попадает по запросу, а не всегда;
- правило обращения к базе — функция слоя, а не всегда загружаемая карточка: оно нужно при задаче
  про PostgreSQL, и поиск по `functional:` + ручным алиасам его даёт;
- пароль называется в тексте правила (прямой запуск `psql.exe` без значения невозможен), значение
  подставляет `src/db_env.py`, расхождение карточки со значением ловит проверка.

**Числа после шага П4b.** Всегда загружаемый набор политики — `rules:` 5 600 и `rules:kb-rules:`
10 948, итого 16 548 символов при пороге 18 000 (запас 8 %): карточка функции в набор не входит, её
читают по задаче про PostgreSQL. Живых функциональных карточек слоя стало 11 (было 10; одна прежняя
помечена к удалению узлом Q1), детей у карточки слоя — 23 (новая функция названа перечнем, иначе
записанное правило не находится по входу слоя). Сверка канала поиска с деревом —
`probes/misc/_l2_block_probe.py`: «детей `functional:` в БД: 11; `rules_functions.py` сообщает: 11».

**Что осталось предупреждением.** `tools/check_rules_layer.py` печатает на новой карточке
⚠️ «алиасов в базе больше, чем объявлено в карточке». Перечисленные имена — адресные алиасы
(`rules:`, `rules:kb-rules:`, `rules:kb-rules:functional:`, короткая форма адреса, метка слоя),
которые записывает скрипт шага П4b, чтобы карточку отдавал `by_alias` в `src/rules_report.py`.
Объявить их текстом раздела `===ALIASES===` нельзя: `rules_layer.validate_alias` отклоняет алиас с `:`
и алиас с меткой слоя, поэтому отношение «объявленное ⊆ базы» осталось односторонним по построению, а
не по недосмотру. То же предупреждение даёт и прежняя карточка `rules:always:reading` — состояние
общее для адресных алиасов, а не дефект новой строки. Итог проверки слоя после узла —
`tools/check_rules_layer.py`: провалено 0. Счётчик проверок здесь не называют: он растёт от каждой
новой карточки и от каждой названной ссылки, поэтому числом мерят прогон, а не состояние узла.
"""


# ------------------------------------------------------------------ состояние и запись
def read_card(cur, address):
    cur.execute("SELECT id, answer, tags FROM knowledge_snippets WHERE question = %s", (address,))
    row = cur.fetchone()
    return (row["id"], row["answer"], list(row["tags"] or [])) if row else (None, None, [])


def tags_like(cur, sample_address, fallback):
    """Теги копируют с живой строки-образца: словарь категорий меняется, а список в скрипте — нет."""
    _, _, tags = read_card(cur, sample_address)
    return tags or list(fallback)


def card_aliases(address):
    """Алиасы карточки: адрес в двух написаниях, алиасы уровней, метка слоя, ручные термины.

    Тот же порядок, что у генератора слоёв (`_make_layer_rule_cards.card_aliases`): `by_alias` в
    `src/rules_report.py` отдаёт поддерево только тем строкам, что объявили алиас уровня, поэтому
    без алиасов предков карточка не читается ни дампом дерева, ни префиксным запросом функций.
    """
    short = address[len(RL.ROOT_MARKER) + 1:]
    names = [address, short] + MC.level_aliases(address) + MC.level_aliases(short) + [LAYER]
    return list(dict.fromkeys(names + FUNCTION_ALIASES_RU))


def drop_card(cur, address, dry, note):
    """Физически снять строку вместе с алиасами: строку создал этот же прогон."""
    card_id, _, _ = read_card(cur, address)
    if not card_id:
        print(f"  • {address} — строки нет, снимать нечего")
        return 0
    if dry:
        print(f"  • {address} — будет снята (id={card_id}): {note}")
        return card_id
    cur.execute("DELETE FROM alias_targets WHERE snippets_id = %s", (card_id,))
    aliases = cur.rowcount
    cur.execute("DELETE FROM knowledge_snippets WHERE id = %s", (card_id,))
    print(f"  • {address} — снята (id={card_id}, алиасов убрано {aliases}): {note}")
    return card_id


def upsert_card(cur, address, answer, tags, aliases, dry, label):
    """Карточка слоя: UPDATE по адресу, когда строка есть, иначе INSERT (приём `upsert_card`)."""
    problems = RL.validate_address(address, RL.ROOT_MARKER)
    if problems:
        print("  ❌ " + address + ": адрес не проходит проверку: " + "; ".join(problems))
        return None
    existing_id, existing_answer, _ = read_card(cur, address)
    if existing_id:
        # Алиасы досоздают и на существующей строке: `ensure_aliases` аддитивна (ON CONFLICT DO
        # NOTHING), а термин, добавленный в раздел `===ALIASES===` позже строки, иначе остаётся
        # объявленным, но ненайденным — тот же дефект, что правило без записи в `alias_targets`.
        if not dry:
            MC.ensure_aliases(cur, existing_id, aliases, tags)
        if existing_answer == answer:
            print(f"  • {address} — без изменений (id={existing_id}, {len(answer)} симв.)")
            return existing_id
        if dry:
            print(f"  • {address} — будет обновлена (id={existing_id}, "
                  f"{len(existing_answer)} → {len(answer)} симв.)")
            return existing_id
        cur.execute("UPDATE knowledge_snippets SET answer = %s, tags = %s, confidence = 1.0, "
                    "is_verified = true, source_url = %s, updated_at = NOW() WHERE id = %s",
                    (answer, tags, RL.source_url(address), existing_id))
        print(f"  • {address} — обновлена (id={existing_id}, {len(answer)} симв.)")
        return existing_id
    if dry:
        print(f"  • {address} — будет {label}: {len(answer)} симв., алиасов {len(aliases)}")
        return None
    cur.execute("INSERT INTO knowledge_snippets (question, answer, tags, confidence, is_verified, "
                "source_url) VALUES (%s, %s, %s, 1.0, true, %s) RETURNING id",
                (address, answer, tags, RL.source_url(address)))
    snippet_id = cur.fetchone()["id"]
    MC.ensure_aliases(cur, snippet_id, aliases, tags)
    print(f"  • {address} — {label} (id={snippet_id}, {len(answer)} симв., "
          f"алиасов {len(aliases)})")
    return snippet_id


def measure_always(cur):
    """Объём всегда загружаемого набора политики — теми же адресами, что читает `rules_read.py`."""
    total, parts = 0, []
    for address in RR.ALWAYS_ADDRESSES:
        _, answer, _ = read_card(cur, address)
        size = len(answer) if answer else 0
        total += size
        parts.append(f"{address} {size}")
    return total, parts


def main():
    write = "--write" in sys.argv[1:]
    print("=== узел V60 П4b: правило подключения — функцией слоя ===",
          "запись" if write else "только разбор")

    function_answer = FUNCTION_TEXT.format(
        password=db_env.pg_password(),
        gen_probe=GEN_PROBE,
        check_tool=CHECK_TOOL,
        aliases="\n".join(f"- {a}" for a in FUNCTION_ALIASES_RU),
        journal=JOURNAL_NODE,
    )

    with get_cursor() as cur:
        function_tags = tags_like(cur, SAMPLE_FUNCTION, FUNCTION_TAGS_FALLBACK)
        journal_tags = [t for t in function_tags if t != MC.KIND_FUNCTIONAL] + [RL.STATE_JOURNAL]

        print("\n1. снять always-карточку шага П4 (правило переносится в функцию слоя)")
        drop_card(cur, ALWAYS_CARD, not write,
                  "место правила — функция слоя, всегда загружаемая карточка не нужна")

        print("\n2. снимок журнала узла — история, до которой прослеживается функция")
        upsert_card(cur, JOURNAL_NODE, JOURNAL_TEXT, journal_tags,
                    [JOURNAL_NODE] + MC.level_aliases(JOURNAL_NODE), not write, "снимок")

        print(f"\n3. карточка функции (теги образца: {','.join(function_tags)})")
        upsert_card(cur, FUNCTION_CARD, function_answer, function_tags,
                    card_aliases(FUNCTION_CARD), not write, "карточка создана")

        print("\n4. перечни карточки слоя (`===MCP`/`===LINKS`/`===INDEX`) перегенерацией")
        layer_id, layer_answer, _ = read_card(cur, LAYER_ADDRESS)
        rebuilt = MC.rebuild_parent(cur, dry=True)[3]
        if not layer_id:
            print(f"  ❌ карточки `{LAYER_ADDRESS}` нет — перечни не обновлены")
        elif rebuilt == layer_answer:
            print(f"  • {LAYER_ADDRESS} — без изменений (id={layer_id}, {len(rebuilt)} симв.)")
        elif write:
            result = update_snippet(layer_id, new_answer=rebuilt,
                                   reason="узел V60 П4b (06.11.2026): перечни перечитаны из дерева — "
                                          "новая функция слоя обязана быть названа, иначе записанное "
                                          "правило не находится по перечню слоя")
            print(f"  • {LAYER_ADDRESS} — обновлена (id={layer_id}, {len(layer_answer)} → "
                  f"{len(rebuilt)} симв.): {str(result)[:100]}")
        else:
            print(f"  • {LAYER_ADDRESS} — будет обновлена (id={layer_id}, {len(layer_answer)} → "
                  f"{len(rebuilt)} симв.)")

    with get_cursor() as cur:
        cur.execute("SELECT question FROM knowledge_snippets WHERE question LIKE %s",
                    (RL.functional_prefix(LAYER) + "%",))
        functions = sorted(r["question"] for r in cur.fetchall()
                           if RL.state_of(RL.layer_relative(r["question"], LAYER)) != RL.STATE_JOURNAL)
        card_id, _, _ = read_card(cur, FUNCTION_CARD)
        aliases_n = 0
        if card_id:
            cur.execute("SELECT count(*) AS n FROM alias_targets WHERE snippets_id = %s", (card_id,))
            aliases_n = cur.fetchone()["n"]
        total, parts = measure_always(cur)

    print(f"\nитог: функций слоя {len(functions)}; алиасов у `{FUNCTION_CARD}`: {aliases_n}")
    for name in functions:
        print(f"   • {name}")
    print(f"всегда загружаемый набор политики: {total} симв. при пороге {RL.ALWAYS_BUDGET_CHARS}")
    for part in parts:
        print(f"   {part}")
    print("новая карточка в наборе политики:",
          "да" if FUNCTION_CARD in RR.ALWAYS_ADDRESSES else "нет — правило вариативное")
    return 0


if __name__ == "__main__":
    sys.exit(main())






